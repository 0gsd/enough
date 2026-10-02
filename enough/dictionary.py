"""FEED, the first-party enough english dictionary: build, read, and the user's own entries.

Two SQLite files under the state root (env `ENOUGH_DICT_ROOT`, default `~/enough/dict/`):

- `feed.sqlite`, the official dictionary, built from the shipped text form in `reflib/dict/` (env
  `ENOUGH_DICT_SOURCE` overrides the source dir; `scripts/sync_dictionary.py` writes it). Disposable: rebuilt
  whenever `manifest.json`'s digest differs from the one stamped into its `meta` table, always to a temp file in
  the same dir and then `os.replace`d, so a reader never sees half a dictionary.
- `user-dictionary.sqlite`, the user's own entries. Precious: created lazily on the first write, from the same
  `schema.sql`, and never rebuilt or deleted by code. Every write in this module goes there and nowhere else.

Reads open a fresh connection per call (tool runners and endpoints run on worker threads): the official DB
read-only, the user DB ATTACHed as `u` when it exists. A word in both is the user's. Every entry carries
`origin: "feed" | "user"`.

Both DBs keep the exact shipped schema. The two orderings the schema has no column for, chronological `era`
(from `first_use`) and `syllables` (from `hyphenation`), are SQL functions registered on each connection.
`entries()` and `index()` sort the whole headword list once per (sort, filters, DB versions) and keep the
order in a small in-process cache, so paging and a deep jump are a slice.

Spec: docs/feed-041-plan.md ("FEED runtime").
"""

from __future__ import annotations

import datetime as _dt
import functools
import json
import logging
import os
import re
import sqlite3
import string
import tempfile
import threading
import time
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

log = logging.getLogger("enough.dictionary")

INSTALL_ROOT = Path(__file__).resolve().parents[1]

FEED_DB = "feed.sqlite"
USER_DB = "user-dictionary.sqlite"

SMALL = ("meta", "labels", "frequency_bands")
SPLIT = ("words", "forms", "synonyms")

# Columns holding JSON text. Parsed on the way out, accepted as lists on the way in.
JSON_COLUMNS = frozenset({
    "synonyms", "forms", "form_labels", "parents", "perfect_rhymes", "slant_rhymes", "homophones",
    "examples", "related", "antonyms",
    "fr_compare", "es_compare", "de_compare", "zh_compare", "ja_compare",
})

# The list view's short entry. `hyphenation` draws the syllable-dotted headword, `pos_primary` and `added_on`
# the margin keys the dictionary page shows under those sorts.
SHORT_COLUMNS = ("word", "pronunciation", "pos", "pos_primary", "definition", "usage_note", "related", "synonyms",
                 "domain", "first_use", "frequency_rank", "length", "hyphenation", "added_on")

# A user entry derives or stamps these itself; whatever a caller passes for them is ignored.
DERIVED = frozenset({"word", "letter", "length", "is_headword", "pos_primary", "ipa", "source", "added_on",
                     "updated_on", "status", "corrected_on", "form_of", "form_labels", "parents"})
REQUIRED = ("definition", "pos", "pronunciation")
# The columns a user entry is "missing" while empty: the ones a conversation can fill. Rhymes are derived by
# a later job; the per-language pairs wait for the owner.
REPORTED = ("pronunciation", "pos", "definition", "usage_note", "domain", "etymology", "examples", "synonyms",
            "related", "antonyms", "hyphenation", "frequency_rank", "first_use", "forms")

WORD_RE = re.compile(r"^[a-z]+$")

SORT_KEYS = ("alpha", "length", "domain", "era", "pos", "frequency", "syllables", "added", "origin")
_SORT_EXPR = {
    "alpha": "word", "length": "length", "domain": "domain", "era": "era(first_use)", "pos": "pos_primary",
    "frequency": "frequency_rank", "syllables": "syllables(hyphenation)", "added": "added_on",
    "origin": "origin",
}
# What a group (an index entry, a section header) is keyed on, per primary sort.
_GROUP_EXPR = dict(_SORT_EXPR, alpha="letter", era="first_use")
# What a grouped primary sort compares instead (see `entries(grouped=)`): the two sorts whose value is finer
# than their group.
_GROUPED_EXPR = {"alpha": "letter", "era": "era_group(first_use)"}
# The build-time covering index (feed.sqlite only) and the columns `_ordered` reads: keep the two in step.
_SORT_INDEX = ("word", "letter", "length", "domain", "first_use", "pos_primary", "frequency_rank", "hyphenation",
               "added_on")
FILTER_KEYS = ("domain", "pos", "band", "origin")
_FILTER_COL = {"domain": "domain", "pos": "pos_primary", "band": "frequency_rank", "origin": "origin"}
MAX_LIMIT = 500


class DictionaryUnavailable(RuntimeError):
    """No built dictionary to read (source missing, or the first build still running)."""


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def source_dir() -> Path:
    env = os.environ.get("ENOUGH_DICT_SOURCE")
    return Path(env).expanduser() if env else INSTALL_ROOT / "reflib" / "dict"


def state_root() -> Path:
    env = os.environ.get("ENOUGH_DICT_ROOT")
    return Path(env).expanduser() if env else Path.home() / "enough" / "dict"


def feed_path() -> Path:
    return state_root() / FEED_DB


def user_path() -> Path:
    return state_root() / USER_DB


def _manifest(src: Path | None = None) -> dict | None:
    src = src or source_dir()
    try:
        man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (src / "schema.sql").is_file() or not man.get("digest"):
        return None
    return man


def available() -> bool:
    """FEED's source ships with this install (built or not). Cheap: one small
    file read, so the prompt assembler can ask it every turn."""
    return _manifest() is not None


def _uri(path: Path, mode: str = "ro") -> str:
    return f"file:{quote(str(path))}?mode={mode}"


# ---------------------------------------------------------------------------
# era and syllables (also registered as SQL functions)
# ---------------------------------------------------------------------------

# Named periods sort before the numbered centuries, in the order the plan fixes:
# Old English < late Old English < Middle English < late Middle English < 13th century < ...
_PERIODS = {
    "old english": 900.0, "late old english": 1000.0,
    "middle english": 1100.0, "late middle english": 1150.0,
}
_WITHIN = {None: 0.0, "early": 15.0, "mid": 50.0, "late": 85.0}
_CENTURY_RE = re.compile(r"(?:(early|mid|late)[\s-]+)?(\d{1,2})(?:st|nd|rd|th)\s+century")
_DECADE_RE = re.compile(r"(\d{3,4})s")
_YEAR_RE = re.compile(r"(\d{3,4})")


@functools.lru_cache(maxsize=4096)
def _era_parts(first_use: str | None) -> tuple[float, str, str] | None:
    """(ordinal, group key, group label), or None when the string names no date. Cached: the whole
    dictionary uses fewer than a hundred distinct strings, and a sort calls this once per headword."""
    if not first_use:
        return None
    t = " ".join(first_use.strip().lower().rstrip(".").split())
    by = 0.0
    if t.startswith("by the "):
        # "by the 17th century" sorts with the 17th century, just after the bare one.
        t, by = t[len("by the "):], 0.5
    if t in _PERIODS:
        period = "old english" if "old" in t else "middle english"
        return _PERIODS[t] + by, period.replace(" ", "-"), period
    m = _CENTURY_RE.fullmatch(t)
    if m:
        n = int(m.group(2))
        return (n - 1) * 100 + _WITHIN[m.group(1)] + by, f"c{n:02d}", _century(n)
    m = _DECADE_RE.fullmatch(t) or _YEAR_RE.fullmatch(t)
    if m:
        year = int(m.group(1))
        n = year // 100 + 1
        # A decade sits at its middle, among the century's early/mid/late.
        return year + (5.0 if t.endswith("s") else 0.0), f"c{n:02d}", _century(n)
    return None


def _century(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix} century"


def era_ord(first_use: str | None) -> float | None:
    """Chronological ordinal of a `first_use` string; None (sorted last) when it names no date."""
    parts = _era_parts(first_use)
    return parts[0] if parts else None


def syllable_count(hyphenation: str | None) -> int | None:
    if not hyphenation:
        return None
    return hyphenation.count("·") + 1


def era_group_ord(first_use: str | None) -> float | None:
    """Chronological ordinal of the GROUP a `first_use` falls in (old english, middle english, a century):
    what a grouped sort compares when a sub-sort orders the words inside each group."""
    parts = _era_parts(first_use)
    if not parts:
        return None
    key = parts[1]
    if key == "old-english":
        return _PERIODS["old english"]
    if key == "middle-english":
        return _PERIODS["middle english"]
    return (int(key[1:]) - 1) * 100 + 0.25


def _register(con: sqlite3.Connection) -> None:
    con.create_function("era", 1, era_ord, deterministic=True)
    con.create_function("era_group", 1, era_group_ord, deterministic=True)
    con.create_function("syllables", 1, syllable_count, deterministic=True)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_build: dict[str, Any] = {"thread": None, "building": False, "progress": 0.0, "error": None, "seconds": None}
_cancel = threading.Event()


class _Cancelled(Exception):
    pass


def _feed_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        con = sqlite3.connect(_uri(path), uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key = 'manifest_digest'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def _columns(con: sqlite3.Connection, table: str, schema: str = "main") -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA {schema}.table_info({table})")]


def _read_rows(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                yield json.loads(raw)


def build(source: Path | None = None, root: Path | None = None) -> Path:
    """Build `feed.sqlite` from the source dir, unconditionally. Returns its path."""
    src = Path(source) if source else source_dir()
    root = Path(root) if root else state_root()
    man = _manifest(src)
    if man is None:
        raise DictionaryUnavailable(f"no dictionary source at {src}")
    root.mkdir(parents=True, exist_ok=True)
    _sweep_temps(root)
    fd, tmp_name = tempfile.mkstemp(dir=root, prefix=".feed-", suffix=".sqlite.tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    files: list[tuple[str, Path]] = []
    for t in SMALL:
        if (src / f"{t}.jsonl").is_file():
            files.append((t, src / f"{t}.jsonl"))
    for t in SPLIT:
        files += [(t, p) for p in sorted((src / t).glob("*.jsonl"))]
    total = sum(p.stat().st_size for _, p in files) or 1
    done = 0
    started = time.monotonic()
    try:
        con = sqlite3.connect(tmp)
        try:
            con.execute("PRAGMA journal_mode = OFF")
            con.execute("PRAGMA synchronous = OFF")
            con.execute("PRAGMA foreign_keys = OFF")
            con.executescript((src / "schema.sql").read_text(encoding="utf-8"))
            cols = {t: _columns(con, t) for t in SMALL + SPLIT}
            for table, path in files:
                sql = (f"INSERT INTO {table} ({', '.join(cols[table])}) "
                       f"VALUES ({', '.join('?' * len(cols[table]))})")
                batch: list[list] = []
                for row in _read_rows(path):
                    batch.append([row.get(c) for c in cols[table]])
                    if len(batch) >= 5000:
                        if _cancel.is_set():
                            raise _Cancelled()
                        con.executemany(sql, batch)
                        batch.clear()
                if batch:
                    con.executemany(sql, batch)
                done += path.stat().st_size
                _build["progress"] = round(done / total, 4)
            # feed.sqlite is disposable, so it may carry an index the shipped schema doesn't: every column a
            # sort, a group or a filter reads, so ordering the headwords scans this instead of the wide rows.
            con.execute(f"CREATE INDEX feed_sort ON words (is_headword, {', '.join(_SORT_INDEX)})")
            con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('manifest_digest', ?)",
                        (man["digest"],))
            try:
                con.execute(f"PRAGMA user_version = {int(man.get('schema_version') or 0)}")
            except ValueError:
                pass
            con.commit()
            con.execute("ANALYZE")
            con.commit()
        finally:
            con.close()
        target = root / FEED_DB
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _build["seconds"] = round(time.monotonic() - started, 2)
    log.info("dictionary: built %s in %.1fs", root / FEED_DB, _build["seconds"])
    _invalidate()
    return root / FEED_DB


def _sweep_temps(root: Path) -> None:
    """Remove temp builds a crashed process left behind. Only old ones: another enough server (a second
    project) may be building right now."""
    cutoff = time.time() - 3600
    for p in root.glob(".feed-*.sqlite.tmp"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def _needs_build(src: Path, root: Path) -> dict | None:
    man = _manifest(src)
    if man is None:
        return None
    return man if _feed_digest(root / FEED_DB) != man["digest"] else None


def _run_build(src: Path, root: Path) -> None:
    try:
        build(src, root)
        _build["error"] = None
    except _Cancelled:
        log.info("dictionary: build cancelled")
    except Exception as e:  # noqa: BLE001 — a failed build reports through status(), never raises at boot
        log.exception("dictionary: build failed")
        _build["error"] = f"{type(e).__name__}: {e}"
    finally:
        with _lock:
            _build["building"] = False
            _build["thread"] = None


def ensure_built(*, background: bool = False, source: Path | None = None, root: Path | None = None) -> dict:
    """Build `feed.sqlite` if it is missing or stale. Idempotent; never raises for a missing source.

    `background=True` (the server lifespan) starts the build on a daemon thread and returns at once; watch it
    through `status()`. Returns `status()`.
    """
    src = Path(source) if source else source_dir()
    root = Path(root) if root else state_root()
    try:
        if _needs_build(src, root) is None:
            return status()
        with _lock:
            if _build["building"]:
                return status()
            _build.update(building=True, progress=0.0, error=None)
            _cancel.clear()
            if background:
                t = threading.Thread(target=_run_build, args=(src, root), name="dictionary-build", daemon=True)
                _build["thread"] = t
                t.start()
                return status()
        _run_build(src, root)
    except Exception as e:  # noqa: BLE001
        log.exception("dictionary: ensure_built failed")
        _build["error"] = f"{type(e).__name__}: {e}"
    return status()


def cancel_build(timeout: float = 5.0) -> None:
    """Stop a background build (server shutdown). The half-built temp file is removed."""
    t = _build.get("thread")
    if t is None:
        return
    _cancel.set()
    t.join(timeout)


def status() -> dict:
    man = _manifest()
    feed = feed_path()
    digest = _feed_digest(feed)
    out = {
        "available": man is not None,
        "ready": digest is not None,
        "building": bool(_build["building"]),
        "progress": 1.0 if (digest and not _build["building"]) else _build["progress"],
        "version": (man or {}).get("dictionary_version"),
        "headwords": (man or {}).get("headwords"),
        "words": (man or {}).get("words"),
        "user_words": _user_count(),
        "stale": bool(man and digest and digest != man["digest"]),
        "error": _build["error"],
    }
    return out


def _user_count() -> int:
    up = user_path()
    if not up.is_file():
        return 0
    try:
        con = sqlite3.connect(_uri(up), uri=True)
        try:
            return con.execute("SELECT count(*) FROM words").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


# ---------------------------------------------------------------------------
# Read connections
# ---------------------------------------------------------------------------

def _connect() -> tuple[sqlite3.Connection, bool]:
    """(connection, has_user). Official DB read-only; the user DB attached as `u` when it exists."""
    feed = feed_path()
    if not feed.is_file():
        raise DictionaryUnavailable("the dictionary is not built yet")
    con = sqlite3.connect(_uri(feed), uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    _register(con)
    has_user = False
    up = user_path()
    if up.is_file():
        try:
            con.execute("ATTACH DATABASE ? AS u", (_uri(up),))
            has_user = bool(con.execute(
                "SELECT 1 FROM u.sqlite_master WHERE type = 'table' AND name = 'words'").fetchone())
        except sqlite3.Error:
            log.exception("dictionary: could not attach the user dictionary")
    return con, has_user


def _fts_query(text: str, *, prefix: bool = True, column: str | None = None) -> str | None:
    terms = re.findall(r"[0-9a-z]+", _fold(text).lower())
    if not terms:
        return None
    quoted = [f'"{t}"' for t in terms]
    if prefix:
        quoted[-1] += "*"
    body = " ".join(quoted)
    return f"{column}: ({body})" if column else body


def _merged(cols: Iterable[str], has_user: bool, *, q: bool = False, words: int = 0) -> str:
    """Headwords from both DBs as one relation, the user row winning. `q` adds an FTS filter (param :q);
    `words` an `IN` list of that many positional params (repeated for each half)."""
    c = ", ".join(cols)
    feed_where = ["is_headword = 1"]
    user_where = ["is_headword = 1"]
    if has_user:
        feed_where.append("word NOT IN (SELECT word FROM u.words)")
    if q:
        feed_where.append("word IN (SELECT word FROM main.words_fts WHERE words_fts MATCH :q)")
        user_where.append("word IN (SELECT word FROM u.words_fts WHERE words_fts MATCH :q)")
    if words:
        inlist = f"word IN ({', '.join('?' * words)})"
        feed_where.append(inlist)
        user_where.append(inlist)
    sql = f"SELECT {c}, 'feed' AS origin FROM main.words WHERE {' AND '.join(feed_where)}"
    if has_user:
        sql += f" UNION ALL SELECT {c}, 'user' AS origin FROM u.words WHERE {' AND '.join(user_where)}"
    return f"({sql})"


def _versions(has_user: bool) -> tuple:
    def sig(p: Path):
        try:
            st = p.stat()
            return (st.st_mtime_ns, st.st_size, st.st_ino)
        except OSError:
            return None
    return (str(feed_path()), sig(feed_path()), sig(user_path()) if has_user else None, _user_gen[0])


# ---------------------------------------------------------------------------
# Value shaping
# ---------------------------------------------------------------------------

def _parse(col: str, value: Any) -> Any:
    if col in JSON_COLUMNS and isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _shape(row: sqlite3.Row | dict) -> dict:
    d = dict(row)
    return {k: _parse(k, v) for k, v in d.items()}


def _fold(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


_PUNCT = string.punctuation + string.whitespace + "“”‘’«»‹›—–…·¿¡"


def normalize(raw: str) -> list[str]:
    """Lookup candidates for a typed or clicked word, best first: lowercased, diacritics folded, surrounding
    punctuation stripped, a possessive 's (or s') dropped."""
    s = _fold(raw or "").replace("’", "'").replace("‘", "'").lower().strip(_PUNCT)
    if not s:
        return []
    out = [s]
    if s.endswith("'s") and len(s) > 2:
        out.append(s[:-2].strip(_PUNCT))
    return [c for i, c in enumerate(out) if c and c not in out[:i]]


# ---------------------------------------------------------------------------
# Sorting, the order cache, groups
# ---------------------------------------------------------------------------

_ORDER_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_ORDER_CACHE_SIZE = 6
_cache_lock = threading.Lock()
_user_gen = [0]


def _invalidate() -> None:
    with _cache_lock:
        _ORDER_CACHE.clear()
    _user_gen[0] += 1


def _check_sort(sort: str | None, d: str | None, default: str = "alpha") -> tuple[str, str]:
    sort = (sort or default).strip().lower()
    if sort not in SORT_KEYS:
        raise ValueError(f"unknown sort {sort!r}; one of {', '.join(SORT_KEYS)}")
    d = (d or "asc").strip().lower()
    if d not in ("asc", "desc"):
        raise ValueError(f"unknown direction {d!r}; asc or desc")
    return sort, d


def _norm_filters(filters: dict | None) -> tuple:
    out = []
    for k, v in (filters or {}).items():
        if v in (None, "", []):
            continue
        if k not in FILTER_KEYS:
            raise ValueError(f"unknown filter {k!r}; one of {', '.join(FILTER_KEYS)}")
        vals = v if isinstance(v, (list, tuple, set)) else str(v).split(",")
        vals = [str(x).strip() for x in vals if str(x).strip()]
        if k == "band":
            vals = [int(x) for x in vals]
        if vals:
            out.append((k, tuple(sorted(set(vals)))))
    return tuple(sorted(out))


def _group_of(sort: str, raw: Any, bands: dict[int, str]) -> tuple[str, str]:
    if sort == "era":
        parts = _era_parts(raw)
        return (parts[1], parts[2]) if parts else ("undated", "undated")
    if raw is None:
        return ("none", {"domain": "no domain", "pos": "no part of speech", "frequency": "unrecorded",
                         "syllables": "no syllables", "added": "undated"}.get(sort, "none"))
    if sort == "length":
        return (str(raw), f"{raw} letter{'s' if raw != 1 else ''}")
    if sort == "syllables":
        return (str(raw), f"{raw} syllable{'s' if raw != 1 else ''}")
    if sort == "frequency":
        return (str(raw), bands.get(raw, str(raw)).lower())
    return (str(raw), str(raw))


def _view(sort: str | None, then: str | None, d: str | None, then_d: str | None,
          grouped: bool) -> tuple[str, str, str | None, str, bool]:
    """Validate and normalise one view's ordering: (sort, dir, then, then_dir, grouped)."""
    sort, d = _check_sort(sort, d)
    td = "asc"
    if then:
        then, td = _check_sort(then, then_d)
        # The last tie-break is always word ascending, so that sub-sort is no sub-sort (and shares the cache)
        # -- unless it orders whole groups, where "then alphabetical" is a real order.
        if then == sort or (then == "alpha" and td == "asc" and not (grouped and sort in _GROUPED_EXPR)):
            then = None
    grouped = bool(grouped and then and sort in _GROUPED_EXPR)
    return sort, d, then, td, grouped


def _ordered(con: sqlite3.Connection, has_user: bool, *, sort: str, then: str | None, d: str, then_d: str,
             letter: str | None, q: str | None, filters: tuple, grouped: bool = False) -> dict:
    """The full sorted headword list for one view: {words, user, groups}. Cached."""
    key = (sort, then, d, then_d, letter, q, filters, grouped, _versions(has_user))
    with _cache_lock:
        hit = _ORDER_CACHE.get(key)
        if hit is not None:
            _ORDER_CACHE.move_to_end(key)
            return hit
    fts = _fts_query(q) if q else None
    if q and fts is None:
        result = {"words": [], "user": set(), "groups": []}
    else:
        cols = _SORT_INDEX
        where, params = [], {}
        if letter:
            where.append("letter = :letter")
            params["letter"] = letter.strip().lower()[:1]
        for k, vals in filters:
            names = []
            for i, v in enumerate(vals):
                params[f"f_{k}_{i}"] = v
                names.append(f":f_{k}_{i}")
            where.append(f"{_FILTER_COL[k]} IN ({', '.join(names)})")
        if fts:
            params["q"] = fts
        order = []
        for i, (k, kd) in enumerate(((sort, d), (then, then_d))):
            if not k:
                continue
            expr = _GROUPED_EXPR[k] if (grouped and i == 0) else _SORT_EXPR[k]
            if expr != "word":
                order.append(f"({expr}) IS NULL")
            order.append(f"{expr} {kd.upper()}")
        if then != "alpha" and (sort != "alpha" or grouped):
            order.append("word ASC")
        sql = (f"SELECT word, origin, {_GROUP_EXPR[sort]} AS g FROM {_merged(cols, has_user, q=bool(fts))} "
               f"{'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY {', '.join(order)}")
        rows = con.execute(sql, params).fetchall()
        bands = {r[0]: r[1] for r in con.execute("SELECT band, name FROM main.frequency_bands")}
        words = [r[0] for r in rows]
        user = {r[0] for r in rows if r[1] == "user"}
        groups: list[dict] = []
        for i, r in enumerate(rows):
            gk, gl = _group_of(sort, r[2], bands)
            if groups and groups[-1]["key"] == gk:
                groups[-1]["count"] += 1
            else:
                groups.append({"key": gk, "label": gl, "count": 1, "offset": i})
        result = {"words": words, "user": user, "groups": groups}
    with _cache_lock:
        _ORDER_CACHE[key] = result
        while len(_ORDER_CACHE) > _ORDER_CACHE_SIZE:
            _ORDER_CACHE.popitem(last=False)
    return result


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

def entries(sort: str = "alpha", then: str | None = None, dir: str = "asc", then_dir: str = "asc",
            offset: int = 0, limit: int = 100, letter: str | None = None, q: str | None = None,
            filters: dict | None = None, grouped: bool = False) -> dict:
    """One page of headwords in the chosen order: {total, offset, rows, groups}.

    `groups` are the sections (letters under alpha, domains under domain, ...) the page's rows fall in, each
    with its absolute `offset` and `count` in the whole list, so a list view can draw headers.

    `grouped`: the sub-sort orders the words inside each GROUP of the primary sort (a letter, a century)
    instead of only breaking the primary's exact ties. Only alpha and era differ (every other sort's value is
    its group); the dictionary page always asks for it, because a sub-sort under "alphabetical" is otherwise
    a no-op."""
    sort, d, then, then_d, grouped = _view(sort, then, dir, then_dir, grouped)
    flt = _norm_filters(filters)
    offset = max(0, int(offset or 0))
    limit = max(1, min(MAX_LIMIT, int(limit or 100)))
    con, has_user = _connect()
    try:
        order = _ordered(con, has_user, sort=sort, then=then, d=d, then_d=then_d, letter=letter,
                         q=(q or "").strip() or None, filters=flt, grouped=grouped)
        page = order["words"][offset:offset + limit]
        rows: list[dict] = []
        if page:
            sql = f"SELECT * FROM {_merged(SHORT_COLUMNS, has_user, words=len(page))}"
            got = {r["word"]: r for r in con.execute(sql, page + page if has_user else page)}
            rows = [_shape(got[w]) for w in page if w in got]
        end = offset + len(page)
        groups = [dict(g) for g in order["groups"]
                  if g["offset"] < end and g["offset"] + g["count"] > offset] if page else []
        return {"total": len(order["words"]), "offset": offset, "rows": rows, "groups": groups}
    finally:
        con.close()


def index(sort: str = "alpha", dir: str = "asc", filters: dict | None = None, q: str | None = None,
          letter: str | None = None) -> list[dict]:
    """The jump rail: [{key, label, count, offset}] in list order, offsets matching `entries()` with the same
    sort, direction and filters (whatever the sub-sort)."""
    sort, d = _check_sort(sort, dir)
    flt = _norm_filters(filters)
    con, has_user = _connect()
    try:
        order = _ordered(con, has_user, sort=sort, then=None, d=d, then_d="asc", letter=letter,
                         q=(q or "").strip() or None, filters=flt)
        return [dict(g) for g in order["groups"]]
    finally:
        con.close()


def position(word: str, sort: str = "alpha", then: str | None = None, dir: str = "asc", then_dir: str = "asc",
             letter: str | None = None, q: str | None = None, filters: dict | None = None,
             grouped: bool = False) -> dict:
    """Where a word sits in one view of the list, so a page can open at it: {query, headword, matched_form,
    found, offset, total, before, after}. A form resolves to its headword first. `found` is False when the
    headword is not in this view (a filter or search left it out) or not in the dictionary at all; for a
    plain alphabetical view `offset` is then where it would fall, with `before` / `after` its neighbours."""
    sort, d, then, then_d, grouped = _view(sort, then, dir, then_dir, grouped)
    flt = _norm_filters(filters)
    cands = normalize(word)
    out: dict[str, Any] = {"query": cands[0] if cands else "", "headword": None, "matched_form": None,
                           "found": False, "offset": None, "total": 0, "before": None, "after": None}
    con, has_user = _connect()
    try:
        for c in cands:
            row, _origin = _row(con, has_user, c)
            head = None
            if row is not None:
                head = c if row["is_headword"] == 1 else row["form_of"]
            elif has_user:
                r = con.execute("SELECT headword FROM u.forms WHERE form = ? ORDER BY position LIMIT 1",
                                (c,)).fetchone()
                head = r[0] if r else None
            if head:
                out.update(query=c, headword=head, matched_form=(c if head != c else None))
                break
        order = _ordered(con, has_user, sort=sort, then=then, d=d, then_d=then_d, letter=letter,
                         q=(q or "").strip() or None, filters=flt, grouped=grouped)
        words = order["words"]
        out["total"] = len(words)
        if out["headword"] is not None:
            try:
                out.update(found=True, offset=words.index(out["headword"]))
                return out
            except ValueError:
                pass
        if sort == "alpha" and then is None and out["query"]:
            # The list is in word order, so a miss still has a place: bisect for it.
            key = out["headword"] or out["query"]
            lo, hi = 0, len(words)
            while lo < hi:
                mid = (lo + hi) // 2
                if (words[mid] < key) if d == "asc" else (words[mid] > key):
                    lo = mid + 1
                else:
                    hi = mid
            out.update(offset=lo, before=words[lo - 1] if lo > 0 else None,
                       after=words[lo] if lo < len(words) else None)
        return out
    finally:
        con.close()


def _row(con: sqlite3.Connection, has_user: bool, word: str) -> tuple[sqlite3.Row | None, str | None]:
    if has_user:
        r = con.execute("SELECT * FROM u.words WHERE word = ?", (word,)).fetchone()
        if r is not None:
            return r, "user"
    r = con.execute("SELECT * FROM main.words WHERE word = ?", (word,)).fetchone()
    return (r, "feed") if r is not None else (None, None)


def _entry(con: sqlite3.Connection, has_user: bool, word: str) -> dict | None:
    row, origin = _row(con, has_user, word)
    if row is None:
        return None
    e = _shape(row)
    e["origin"] = origin
    e["overrides_feed"] = bool(origin == "user" and con.execute(
        "SELECT 1 FROM main.words WHERE word = ?", (word,)).fetchone())
    labels = {r[0]: r[1] for r in con.execute("SELECT label, meaning FROM main.labels")}
    band = e.get("frequency_rank")
    if band is not None:
        b = con.execute("SELECT band, name, examples FROM main.frequency_bands WHERE band = ?",
                        (band,)).fetchone()
        e["frequency_band"] = dict(b) if b else {"band": band, "name": None, "examples": None}
    else:
        e["frequency_band"] = None
    for col in ("forms", "parents"):
        for item in e.get(col) or []:
            if isinstance(item, dict):
                item["label_meanings"] = [labels.get(lb, lb) for lb in item.get("labels") or []]
    if isinstance(e.get("form_labels"), list):
        e["form_label_meanings"] = [labels.get(lb, lb) for lb in e["form_labels"]]
    e["syllables"] = syllable_count(e.get("hyphenation"))
    parts = _era_parts(e.get("first_use"))
    e["era"] = parts[2] if parts else None
    return e


def entry(word: str) -> dict | None:
    """Every column of one word's row, JSON parsed, band and form labels resolved; None when absent."""
    cands = normalize(word)
    if not cands:
        return None
    con, has_user = _connect()
    try:
        for c in cands:
            e = _entry(con, has_user, c)
            if e is not None:
                return e
        return None
    finally:
        con.close()


def lookup(word: str) -> dict:
    """{found, query, entry, matched_form, suggestions}. A nested form (aahed) resolves to its headword's
    entry with `matched_form` set; a miss suggests near words by prefix and full-text search."""
    cands = normalize(word)
    out = {"found": False, "query": cands[0] if cands else "", "entry": None, "matched_form": None,
           "suggestions": []}
    if not cands:
        return out
    con, has_user = _connect()
    try:
        for c in cands:
            row, origin = _row(con, has_user, c)
            head = None
            if row is not None:
                head = c if row["is_headword"] == 1 else row["form_of"]
            elif has_user:
                r = con.execute("SELECT headword FROM u.forms WHERE form = ? ORDER BY position LIMIT 1",
                                (c,)).fetchone()
                head = r[0] if r else None
            if head:
                e = _entry(con, has_user, head)
                if e is not None:
                    out.update(found=True, query=c, entry=e, matched_form=(c if head != c else None))
                    return out
        out["suggestions"] = _suggest(con, has_user, cands[-1])
        return out
    finally:
        con.close()


def _suggest(con: sqlite3.Connection, has_user: bool, word: str, n: int = 8) -> list[str]:
    seen: list[str] = []

    def add(rows):
        for r in rows:
            w = r[0]
            if w not in seen and len(seen) < n:
                seen.append(w)

    merged = _merged(("word",), has_user)
    letters = re.sub(r"[^a-z]", "", word)
    if letters:
        add(con.execute(f"SELECT word FROM {merged} WHERE word > ? AND word < ? ORDER BY length(word), word "
                        f"LIMIT ?", (letters, letters + "{", n)))
    fts = _fts_query(word, column="word")
    if fts and len(seen) < n:
        merged_q = _merged(("word",), has_user, q=True)
        add(con.execute(f"SELECT word FROM {merged_q} ORDER BY length(word), word LIMIT :n",
                        {"q": fts, "n": n}))
    for cut in range(len(letters) - 1, max(1, len(letters) - 4), -1):
        if len(seen) >= n:
            break
        stem = letters[:cut]
        add(con.execute(f"SELECT word FROM {merged} WHERE word >= ? AND word < ? ORDER BY length(word), word "
                        f"LIMIT ?", (stem, stem + "{", n)))
    fts = _fts_query(word, prefix=False, column="definition")
    if fts and len(seen) < n:
        merged_q = _merged(("word",), has_user, q=True)
        add(con.execute(f"SELECT word FROM {merged_q} LIMIT :n", {"q": fts, "n": n}))
    return seen


def facets() -> dict:
    """What the sort and filter controls offer: sort keys, and domains / parts of speech / bands / origins
    with headword counts."""
    con, has_user = _connect()
    try:
        merged = _merged(("word", "domain", "pos_primary", "frequency_rank"), has_user)

        def counts(col: str) -> list[tuple]:
            return con.execute(f"SELECT {col}, count(*) FROM {merged} GROUP BY {col} "
                               f"ORDER BY count(*) DESC, {col}").fetchall()
        bandc = dict(counts("frequency_rank"))
        return {
            "sort_keys": list(SORT_KEYS),
            "filters": list(FILTER_KEYS),
            "domains": [{"domain": k, "count": c} for k, c in counts("domain") if k is not None],
            "pos": [{"pos": k, "count": c} for k, c in counts("pos_primary") if k is not None],
            "bands": [{"band": r["band"], "name": r["name"], "examples": r["examples"],
                       "count": bandc.get(r["band"], 0)}
                      for r in con.execute("SELECT band, name, examples FROM main.frequency_bands ORDER BY band")],
            "origins": [{"origin": k, "count": c} for k, c in counts("origin")],
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# The user dictionary (the only thing this module ever writes, besides feed.sqlite)
# ---------------------------------------------------------------------------

_write_lock = threading.Lock()


def _schema_sql() -> str:
    path = source_dir() / "schema.sql"
    if not path.is_file():
        raise DictionaryUnavailable(f"no dictionary schema at {path}")
    return path.read_text(encoding="utf-8")


def _user_connect() -> sqlite3.Connection:
    """The user DB, created from schema.sql on first use. Never deleted or rebuilt."""
    up = user_path()
    up.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(up, timeout=5)
    con.row_factory = sqlite3.Row
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'words'").fetchone():
        try:
            con.executescript(_schema_sql())
        except Exception:
            con.close()
            raise
    return con


def _today() -> str:
    return _dt.date.today().isoformat()


def _clean_word(word: Any) -> str:
    cands = normalize(str(word or ""))
    return cands[0] if cands else ""


def _as_json(col: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.startswith("["):
            try:
                value = json.loads(s)
            except ValueError:
                value = [ln.strip() for ln in s.splitlines() if ln.strip()]
        else:
            value = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if isinstance(value, (tuple, set)):
        value = list(value)
    if col == "forms":
        value = [_form_item(v) for v in value if _form_item(v)]
    if isinstance(value, list) and not value:
        return None
    return json.dumps(value, ensure_ascii=False)


def _form_item(v: Any) -> dict | None:
    if isinstance(v, str):
        w = _clean_word(v)
        return {"word": w, "pronunciation": "", "labels": [], "synonyms": []} if w else None
    if isinstance(v, dict) and v.get("word"):
        labels = v.get("labels") or []
        syns = v.get("synonyms") or []
        return {"word": _clean_word(v["word"]), "pronunciation": str(v.get("pronunciation") or ""),
                "labels": [labels] if isinstance(labels, str) else list(labels),
                "synonyms": [syns] if isinstance(syns, str) else list(syns)}
    return None


def _prepare(fields: dict, editable: set[str]) -> tuple[dict, list[str]]:
    """Validate and coerce caller fields. Returns (values, errors)."""
    vals: dict[str, Any] = {}
    errors: list[str] = []
    for k, v in (fields or {}).items():
        if k in DERIVED:
            continue
        if k not in editable:
            errors.append(f"unknown column {k!r}")
            continue
        if k in JSON_COLUMNS:
            vals[k] = _as_json(k, v)
        elif k == "frequency_rank":
            if v in (None, ""):
                vals[k] = None
            else:
                try:
                    band = int(v)
                except (TypeError, ValueError):
                    errors.append("frequency_rank must be a band 0-8")
                    continue
                if not 0 <= band <= 8:
                    errors.append("frequency_rank must be a band 0-8")
                    continue
                vals[k] = band
        else:
            s = None if v is None else str(v).strip()
            vals[k] = s or None
    if vals.get("pos"):
        vals["pos"] = "; ".join(p.strip().lower() for p in re.split(r"[;,]", vals["pos"]) if p.strip())
    return vals, errors


def _derive(word: str, row: dict) -> None:
    row["word"] = word
    row["letter"] = word[0]
    row["length"] = len(word)
    row["is_headword"] = 1
    pos = row.get("pos") or ""
    row["pos_primary"] = pos.split(";")[0].strip() or None
    pron = row.get("pronunciation") or ""
    m = re.search(r"/[^/]+/", pron)
    row["ipa"] = m.group(0) if m else (pron.split(",")[0].strip() or None)
    row["source"] = "user"
    row["status"] = "live"
    row["updated_on"] = _today()
    row["added_on"] = row.get("added_on") or _today()
    for k in ("notes", "corrected_on", "form_of", "form_labels", "parents"):
        row.setdefault(k, None)


def _missing(row: dict) -> list[str]:
    return [c for c in REPORTED if row.get(c) in (None, "", "[]")]


def _write_forms(con: sqlite3.Connection, word: str, forms_json: str | None) -> None:
    con.execute("DELETE FROM forms WHERE headword = ?", (word,))
    for i, f in enumerate(json.loads(forms_json) if forms_json else [], start=1):
        if f.get("word") and f["word"] != word:
            con.execute("INSERT OR REPLACE INTO forms (headword, form, position, pronunciation, labels, synonyms) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (word, f["word"], i, f.get("pronunciation") or "",
                         json.dumps(f.get("labels") or [], ensure_ascii=False),
                         json.dumps(f["synonyms"], ensure_ascii=False) if f.get("synonyms") else None))


def _save(con: sqlite3.Connection, row: dict, exists: bool) -> None:
    cols = [c for c in _columns(con, "words") if c in row]
    if exists:
        sets = ", ".join(f"{c} = ?" for c in cols if c != "word")
        con.execute(f"UPDATE words SET {sets} WHERE word = ?", [row[c] for c in cols if c != "word"] + [row["word"]])
    else:
        con.execute(f"INSERT INTO words ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    [row[c] for c in cols])
    _write_forms(con, row["word"], row.get("forms"))


def _feed_row(word: str) -> dict | None:
    feed = feed_path()
    if not feed.is_file():
        return None
    con = sqlite3.connect(_uri(feed), uri=True)
    con.row_factory = sqlite3.Row
    try:
        r = con.execute("SELECT * FROM words WHERE word = ?", (word,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def _fail(word: str, error: str, missing: list[str] | None = None) -> dict:
    return {"ok": False, "word": word, "error": error, "missing": missing or []}


def user_add(fields: dict) -> dict:
    """Add a new word to the user dictionary. Returns {ok, word, missing} (plus `error` when not ok)."""
    fields = dict(fields or {})
    word = _clean_word(fields.get("word"))
    if not WORD_RE.match(word):
        return _fail(word, "a word is lowercase letters a-z only")
    feed = _feed_row(word)
    if feed is not None and feed.get("is_headword") == 1:
        return _fail(word, f"feed already has {word!r}; update it instead to keep your own version")
    with _write_lock:
        con = _user_connect()
        try:
            if con.execute("SELECT 1 FROM words WHERE word = ?", (word,)).fetchone():
                return _fail(word, f"{word!r} is already in your dictionary; update it instead")
            vals, errors = _prepare(fields, set(_columns(con, "words")))
            absent = [c for c in REQUIRED if not vals.get(c)]
            if errors or absent:
                return _fail(word, "; ".join(errors + [f"{c} is required" for c in absent]), absent)
            row = dict(vals)
            row["added_on"] = None
            _derive(word, row)
            with con:
                _save(con, row, exists=False)
        finally:
            con.close()
    _invalidate()
    return {"ok": True, "word": word, "missing": _missing(row), "overrides_feed": feed is not None}


def user_update(word: str, fields: dict) -> dict:
    """Change a user entry, or make a user version of a feed entry (the user row then wins everywhere)."""
    word = _clean_word(word)
    if not WORD_RE.match(word):
        return _fail(word, "a word is lowercase letters a-z only")
    with _write_lock:
        con = _user_connect()
        try:
            cur = con.execute("SELECT * FROM words WHERE word = ?", (word,)).fetchone()
            exists = cur is not None
            if exists:
                base = dict(cur)
            else:
                feed = _feed_row(word)
                if feed is None or feed.get("is_headword") != 1:
                    return _fail(word, f"{word!r} is in neither feed nor your dictionary; add it instead")
                base = feed
                base["added_on"] = None
            cols = _columns(con, "words")
            vals, errors = _prepare({k: v for k, v in (fields or {}).items() if k != "word"}, set(cols))
            base = {k: base.get(k) for k in cols}
            base.update(vals)
            absent = [c for c in REQUIRED if not base.get(c)]
            if errors or absent:
                return _fail(word, "; ".join(errors + [f"{c} is required" for c in absent]), absent)
            _derive(word, base)
            with con:
                _save(con, base, exists=exists)
        finally:
            con.close()
    _invalidate()
    return {"ok": True, "word": word, "missing": _missing(base), "overrides_feed": _feed_row(word) is not None}


def user_delete(word: str) -> dict:
    """Remove a user entry. A feed entry it was overriding shows again."""
    word = _clean_word(word)
    up = user_path()
    if not up.is_file():
        return _fail(word, f"{word!r} is not in your dictionary")
    with _write_lock:
        con = _user_connect()
        try:
            with con:
                n = con.execute("DELETE FROM words WHERE word = ?", (word,)).rowcount
                con.execute("DELETE FROM forms WHERE headword = ?", (word,))
        finally:
            con.close()
    if not n:
        return _fail(word, f"{word!r} is not in your dictionary")
    _invalidate()
    return {"ok": True, "word": word, "restored_feed": _feed_row(word) is not None}
