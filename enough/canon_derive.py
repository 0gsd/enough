"""The derivation engine (0.4.3, plan §7): a text → its EMF twin (decompile), an EMF twin → markdown (compile), any
text or passage → its atem.

Pure functions. Nothing here imports the server, starts a job, holds a lock or decides whether a model is up: the
caller passes `complete` — a callable `complete(messages) -> (text, meta)`, in the app a closure over
`llm.complete` — or None, which is **rules mode**: a labelled scaffold built from the text and FEED alone, never a
guess dressed as a reading (spec §18.4.3). Readvisor tools call the same functions with `by=<readvisor name>`.

Nothing runs on import, ingest, listing, reconcile or startup. Twins are written by `write_atomic` (tmp +
`os.replace`), declaration first (`macrocosm.dump` puts `oes:` first), and every twin this module writes passes
`macrocosm.lint` with no errors in both modes: what a model wrote that still fails after one repair turn is dropped
and counted in `derived.dropped`, and references left dangling become open questions, `{pending: "..."}`.

The shape written is docs/MACROCOSM_OES.md §18.4 (the `emf/1` MiniCOSM, defaults/cosm/manifests/emf.manifest.cosm);
an atem's four parts are the owner's definitions (§18.3.5).
"""

from __future__ import annotations

import bisect
import datetime as dt
import hashlib
import inspect
import json
import os
import re
import tempfile
import threading
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

from . import canon as _canon
from . import canon_prompts as P
from . import macrocosm

EMF_OES = "emf/1"
EML_OES = EMF_OES                     # the name before EMF (plan §16), kept one release
PENDING_NO_MODEL = "a model has not read this passage"
PENDING_NOT_IN_FEED = "not in FEED"
RULES_CONFIDENCE = 0.3
STANCES = ("axiom", "observed", "deduced", "opinion", "assumed", "hearsay")
SALIENCE = ("critical", "high", "normal", "low")
MODULE_ORDER = ("L", "E", "K", "P", "T", "X")

# Chunking (plan §7.3 A step 1): by headings, then ~1,200-token windows. Tokens are reckoned as chars / 3, the
# estimator server.py and the skill audit use.
CHARS_PER_TOKEN = 3
CHUNK_TOKENS = 1_200
CHUNK_CHARS = CHUNK_TOKENS * CHARS_PER_TOKEN
# The whole-text atem reads the chunk atems plus the first and last ~800 tokens.
ATEM_EDGE_CHARS = 800 * CHARS_PER_TOKEN
# A text up to this long gets its atem from one completion; a longer one is read passage by passage first.
ATEM_ONE_SHOT_CHARS = 4 * CHUNK_CHARS

# The lexical pre-pass (plan §7.2): top 40 candidate terms per 2,000 words, scaled to the text — at least 6, at
# most 60 (a 330-word note gets 6 or 7, not 40).
TERMS_PER_WINDOW = 40
TERMS_WINDOW_WORDS = 2_000
TERMS_MIN = 6
TERMS_MAX = 60
# A word FEED does not hold ranks with FEED's "Rare" band (2): rarer than most, never above the truly rare.
UNKNOWN_BAND = 2
TERM_MIN_LETTERS = 4
# An EMF completion's output budget: this, or less when the model's window is smaller (llm.completion_budget).
EMF_MAX_TOKENS = 4_096
EML_MAX_TOKENS = EMF_MAX_TOKENS       # the name before EMF (plan §16), kept one release
# A model item that says nothing of its confidence (or no provenance at all) is written with this.
MODEL_CONFIDENCE = 0.7
# The lexicon floor in model mode: a FEED-grounded term the model did not discuss says so.
PENDING_FLOOR = "found in the text by rules; the model gave no sense for it here"
# How many FEED words of a passage go into its user message, and how long each definition may run.
PASSAGE_TERMS = 15
PASSAGE_TERM_CHARS = 90

LINE_MAX_WORDS = 25
FOCUS_MAX_WORDS = 80
SLUG_MAX = 48
SNIPPET = 60                     # span start/end, the highlights anchor length

# Texts derive reads: markdown and plain text (a converted original is read through its markdown twin).
TEXT_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd", ".txt", ".text")

CompleteFn = Callable[[list], Any]
LookupFn = Callable[[list], dict]
ProgressFn = Callable[[dict], None]
StopFn = Callable[[], bool]


class DeriveCancelled(Exception):
    """A cooperative cancel was seen between two passages; nothing was written."""


class DeriveError(RuntimeError):
    """A derivation could not go on (an unreadable twin, an empty answer where one was needed)."""


# ---------------------------------------------------------------------------
# Words: the stop list, the closed vocabularies
# ---------------------------------------------------------------------------

# Words of four letters or more that a text leans on only grammatically. Shorter words never become terms, so
# they are not listed. About 300, as plan §7.2 asks; ordinary English, no domain words.
STOP_WORDS = frozenset("""
able about above according across actually after afterwards again against almost alone along already also
although always among amongst another anybody anyhow anyone anything anyway anywhere around aside away back
became because become becomes becoming been before beforehand behind being believe below beside besides best
better between beyond both brief came cannot certain certainly clearly come comes coming could course currently
definitely described despite does doing done down during each eight either else elsewhere enough entirely
especially even ever every everybody everyone everything everywhere exactly example except fairly first five
followed following follows former formerly forth four from further furthermore gave gets getting give given gives
giving goes going gone gotten greetings had hardly have having hello help hence here hereafter hereby herein
hereupon hers herself himself hither hopefully however indeed inner insofar instead into inward itself just keep
keeps kept know known knows last lately later latter latterly least less lest like liked likely little look
looking looks made mainly make makes many maybe mean meanwhile merely might mine more moreover most mostly much
must myself name namely near nearly necessary need needs neither never nevertheless next nine nobody none
noone normally nothing novel now nowhere obviously often okay once ones only onto other others otherwise ought
ours ourselves outside over overall own particular particularly perhaps placed please plus possible presumably
probably provides quite rather really reasonably regarding regardless regards relatively respectively right said
same saying says second secondly seeing seem seemed seeming seems seen self selves sensible sent serious
seriously seven several shall should since some somebody somehow someone something sometime sometimes somewhat
somewhere soon sorry specified specify specifying still such sure take taken tell tends than thank thanks
thanx that thats their theirs them themselves then thence there thereafter thereby therefore therein theres
thereupon these they think third this thorough thoroughly those though three through throughout thru thus
together took toward towards tried tries truly trying twice under unfortunately unless unlikely until unto upon
used useful uses using usually value various very want wants was wasn welcome well went were what whatever when
whence whenever where whereafter whereas whereby wherein whereupon wherever whether which while whither whoever
whole whom whose will willing wish with within without wonder would year years yes yet your yours yourself
yourselves zero also just thing things lot lots really around today tomorrow yesterday
""".split())

MONTHS_AND_DAYS = frozenset("""
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())

HONORIFICS = frozenset("mr mrs ms miss dr prof professor sir dame lord lady saint captain judge president "
                       "king queen".split())
ORG_WORDS = frozenset("council company inc ltd llc corporation corp university college school committee "
                      "association society team group department ministry agency foundation institute bank party "
                      "church club board commission office union trust press court parliament congress senate "
                      "army navy".split())
PLACE_WORDS = frozenset("lane street road avenue way drive valley river lake mountain mount hill hills city town "
                        "county park square bay island islands sea ocean forest wood woods bridge station airport "
                        "harbour harbor beach coast desert canyon falls gardens province kingdom republic".split())
# Lowercase words a capitalised name may carry inside it (Bank of England, Ludwig van Beethoven).
NAME_CONNECTORS = frozenset("of the de du la le von van der den del da di".split())
# Leading words stripped from a capitalised run when they only start the sentence.
_LEADERS = frozenset("the a an this that these those our my his her their its we every each some in on at for "
                     "from to by with if when while after before because but and or so then".split())
_ABBREVIATIONS = frozenset("mr mrs ms dr prof st vs etc eg ie jr sr no fig".split())

_RESERVED_SLUGS = frozenset(["con", "prn", "aux", "nul"] + [f"com{i}" for i in range(10)]
                            + [f"lpt{i}" for i in range(10)])


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now(now: dt.datetime | None) -> dt.datetime:
    """`now` as an aware UTC datetime without microseconds: what `derived.at` writes (a YAML timestamp)."""
    when = now or dt.datetime.now(dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(dt.timezone.utc).replace(microsecond=0)


def _sha6(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:6]


def _fold(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def item_slug(name: str) -> str:
    """An item's slug from its name: diacritics folded, lowercased, words joined by hyphens, a leading article
    dropped ("the Support Lead" → `support-lead`, as the spec's example spells it), cut at a word boundary past
    48 characters. Nothing left → a short hash; a Windows reserved name takes one too (the path grammar refuses
    `con`)."""
    words = re.findall(r"[a-z0-9]+", _fold(str(name)).lower().replace("'", "").replace("’", ""))
    if len(words) > 1 and words[0] in ("the", "a", "an"):
        words = words[1:]
    out = "-".join(words)
    if len(out) > SLUG_MAX:
        cut = out[:SLUG_MAX + 1].rfind("-")
        out = out[:cut] if cut > 0 else out[:SLUG_MAX]
    if not out:
        return _sha6(str(name))
    if out in _RESERVED_SLUGS:
        return f"{out}-{_sha6(str(name))}"
    return out


def _span(a: int, b: int | None = None) -> dict:
    return {"lines": f"{a}" if b is None or b == a else f"{a}-{b}"}


def _locator(source: str, a: int, b: int | None = None) -> str:
    return f"{source}#L{a}" if b is None or b == a else f"{source}#L{a}-L{b}"


def parse_lines(v: Any) -> tuple[int, int] | None:
    """`(first, last)` from a span's `lines`, however it is written: `"3"`, `"12-18"`, `"L12-L18"`, `"4, 17"` and
    `"4,17,20"` (→ 4-20), `3`, `[12, 18]`, `["4", "7"]`. None when it names no line."""
    if isinstance(v, bool) or v is None:
        return None
    nums: list[int] = []
    for x in (v if isinstance(v, (list, tuple)) else [v]):
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            nums.append(x)
        elif isinstance(x, float) and x.is_integer():
            nums.append(int(x))
        elif isinstance(x, str):
            nums += [int(n) for n in re.findall(r"\d+", x)]
    nums = [n for n in nums if n > 0]
    return (min(nums), max(nums)) if nums else None


def clean_span(span: Any) -> dict | None:
    """A span as the twin writes it — `{lines: "a-b"}` and/or `{start, end}` (≤ 60 characters each, the highlights
    anchor shape) — or None when nothing usable is in it."""
    if not isinstance(span, dict):
        return None
    out: dict[str, Any] = {}
    ab = parse_lines(span.get("lines"))
    if ab:
        out.update(_span(*ab))
    for key in ("start", "end"):
        v = span.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = " ".join(v.split())[:SNIPPET]
    return out or None


def passage_span(text: str, selection: dict) -> dict | None:
    """Where a selected passage sits in its text, as a span a pin can carry: `lines` from the selection's own
    `lines`, else from its `start`/`end` character offsets, else by finding its text (exactly, then ignoring
    runs of whitespace); `start`/`end` snippets from the selection's first and last 60 characters (or the
    snippets it brought). None when nothing places it."""
    if not isinstance(selection, dict):
        return None
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    sel = selection.get("text") if isinstance(selection.get("text"), str) else ""
    flat = " ".join(sel.split())
    span: dict[str, Any] = {}
    ab = parse_lines(selection.get("lines"))
    a0, b0 = selection.get("start"), selection.get("end")
    if not ab and isinstance(a0, int) and isinstance(b0, int) and not isinstance(a0, bool) \
            and 0 <= a0 <= b0 <= len(norm):
        ab = (norm.count("\n", 0, a0) + 1, norm.count("\n", 0, max(a0, b0 - 1)) + 1)
    if not ab and flat:
        idx, end = norm.find(sel.strip()), -1
        if idx >= 0:
            end = idx + len(sel.strip())
        elif len(flat) <= 20_000:
            m = re.search(r"\s+".join(map(re.escape, flat.split())), norm)
            if m:
                idx, end = m.start(), m.end()
        if idx >= 0:
            ab = (norm.count("\n", 0, idx) + 1, norm.count("\n", 0, max(idx, end - 1)) + 1)
    if ab:
        span.update(_span(*ab))
    for key, cut in (("start", flat[:SNIPPET].strip()), ("end", flat[-SNIPPET:].strip())):
        v = selection.get(key)
        if isinstance(v, str) and v.strip():
            span[key] = " ".join(v.split())[:SNIPPET]
        elif cut:
            span[key] = cut
    return span or None


def _plain(v: Any) -> Any:
    """A deep copy that never shares a dict or list (a model's YAML with anchors would otherwise make
    `macrocosm.dump` refuse to write)."""
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _accepts(fn: Callable, kw: dict) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return True
    return all(k in params for k in kw)


def _call(complete: CompleteFn, messages: list[dict], **kw: Any) -> tuple[str, dict]:
    """`complete(messages, **kw) -> (text, meta)` (a bare text is read as `(text, {})`); keyword arguments such
    as `max_tokens` go only to a callable that takes them."""
    r = complete(messages, **kw) if kw and _accepts(complete, kw) else complete(messages)
    if isinstance(r, tuple):
        text, meta = r[0], (r[1] if len(r) > 1 and isinstance(r[1], dict) else {})
    else:
        text, meta = r, {}
    return (text if isinstance(text, str) else ""), meta


def _default_lookup(words: list) -> dict:
    from . import dictionary as _dictionary
    return _dictionary.lookup_many(words)


def _feed_key(word: str) -> str:
    """The key `dictionary.lookup_many` files a word under (its first `normalize` candidate)."""
    from . import dictionary as _dictionary
    cands = _dictionary.normalize(word)
    return cands[0] if cands else ""


class _FlowMap(dict):
    """A small mapping the twin writes on one line, as the spec's examples do (`span: {lines: "3"}`,
    `provenance: {mode: derived, ...}`): shorter twins, and a header that stays inside the 30 lines
    `canon.twin_header` reads for listings."""


def _represent_flow(dumper: Any, data: dict) -> Any:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)


# Registered on macrocosm's own dumper (its class, not PyYAML's SafeDumper), for this one type only.
macrocosm._Dumper.add_representer(_FlowMap, _represent_flow)

_FLOW_ITEM_KEYS = ("span", "provenance", "feed", "roles")
_FLOW_SCALARS = (str, int, float, bool, type(None))


def _flow_safe(v: Any) -> bool:
    """Only plain scalars (and lists of them) go in a flow mapping: PyYAML can't write a timestamp plain in flow
    context and would tag it, which the COSM subset forbids."""
    if isinstance(v, dict):
        return all(_flow_safe(x) for x in v.values())
    if isinstance(v, list):
        return all(isinstance(x, _FLOW_SCALARS) for x in v)
    return isinstance(v, _FLOW_SCALARS)


def _flow(v: Any) -> Any:
    return _FlowMap(v) if isinstance(v, dict) and v and _flow_safe(v) else v


def _compact(doc: dict) -> dict:
    """The twin as it is written: `source`, open questions, and each item's span, provenance, feed, roles, link
    entries and open questions on one line each; everything else in block style."""
    out = _plain(doc)
    if isinstance(out.get("source"), dict):
        out["source"] = _flow(out["source"])
    if isinstance(out.get("atem"), dict):
        out["atem"] = {k: (_flow(v) if macrocosm.is_pending(v) else v) for k, v in out["atem"].items()}
    nodes = out.get("nodes")
    for i, it in enumerate(nodes if isinstance(nodes, list) else []):
        if not isinstance(it, dict):
            continue
        for k, v in list(it.items()):
            if k in _FLOW_ITEM_KEYS or macrocosm.is_pending(v):
                it[k] = _flow(v)
            elif k == "links" and isinstance(v, list):
                it[k] = [_flow(x) for x in v]
            elif isinstance(v, list) and any(macrocosm.is_pending(x) for x in v):
                it[k] = [_flow(x) if macrocosm.is_pending(x) else x for x in v]
        nodes[i] = it
    return out


def _dump(doc: dict) -> str:
    return macrocosm.dump(_compact(doc))


def _lines(text: str) -> list[str]:
    """The text's lines as an editor numbers them (LF, CRLF or CR; a final newline adds no line)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines


@lru_cache(maxsize=1)
def _manifest() -> macrocosm.Manifest:
    m = macrocosm.default_registry().get("emf")
    if m is None:
        raise DeriveError("the emf manifest is missing from defaults/cosm/manifests")
    return m


def _kind_module() -> dict[str, str]:
    m = _manifest()
    return {k: letter for letter in m.modules() for k in m.kinds(letter)}


# ---------------------------------------------------------------------------
# Files: the source record, twins, compiled files, atomic writes
# ---------------------------------------------------------------------------

def read_source(path: Path) -> tuple[str, dict]:
    """`(text, source_stat)` for a text: decoded as UTF-8 (a byte-order mark dropped, bad bytes replaced), and
    `{sha256, size, mtime_ns}` of the very bytes decoded — what the twin's `source:` records."""
    path = Path(path)
    st = path.stat()
    data = path.read_bytes()
    return (data.decode("utf-8-sig", errors="replace"),
            {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mtime_ns": st.st_mtime_ns})


def twin_path(text_path: Path | str) -> Path:
    """`notes.md` → `notes.md.cosm` (the convert-twin convention, owner decision 4)."""
    return _canon.emf_twin_path(Path(text_path))


def twin_state(text_path: Path | str) -> str:
    """`fresh`, `stale` or `absent` — P2's rule (`canon.emf_state`), the one the listings use: a twin is fresh
    while the text's size and mtime match its `source:`, or else its sha256 does. Absent when there is no
    `X.cosm` declaring `emf/1` beside the text."""
    text = Path(text_path)
    twin = twin_path(text)
    if not _canon.is_emf_twin(twin):
        return "absent"
    return _canon.emf_state(text, twin)


def short_path(emf_path: Path | str, now: dt.datetime | None = None) -> Path:
    """Where compiling an EMF writes its short (plan §15, owner decision 3): beside it,
    `<stem>.short-YYYY-MM-DD-HHMM.md` in local time, `-2`, `-3` … on a collision, so every compile is a new file
    and never an overwrite. `notes.md.cosm` → `notes.short-…md`; a standalone `rain.cosm` → `rain.short-…md`; the
    stem drops `.cosm` and then one extension. Canon's catalogs recognise the name (`canon.SHORT_RE`)."""
    emf = Path(emf_path)
    name = emf.name[: -len(".cosm")] if emf.name.endswith(".cosm") and len(emf.name) > 5 else emf.name
    stem = Path(name).stem or name
    when = now or dt.datetime.now()
    if when.tzinfo is not None:
        when = when.astimezone()
    stamp = when.strftime("%Y-%m-%d-%H%M")
    cand = emf.parent / f"{stem}.short-{stamp}.md"
    n = 2
    while cand.exists() or cand.is_symlink():
        cand = emf.parent / f"{stem}.short-{stamp}-{n}.md"
        n += 1
    return cand


# The name before SHORT (0.4.3's first landing), kept one release: it is `short_path` now.
compiled_path = short_path


def write_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` through a dotfile beside it and `os.replace`, so a reader never sees half a twin."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


write_twin = write_atomic


def catalog_id(rel_path: str) -> str:
    """`emf/<slug>`: the text's path in its volume or project, slugged by the Canon rule (P0 decision 16):
    `guides/close.md` → `emf/guides--close-md`."""
    return f"emf/{_canon.slug(rel_path)}"


def _catalog(*, rel_path: str, source_name: str, source_stat: dict | None, name: str, derived: dict,
             atem: dict | None, nodes: list) -> dict:
    cat: dict[str, Any] = {
        "oes": EMF_OES,
        "macrocosm": macrocosm.MACROCOSM_VERSION,
        "id": catalog_id(rel_path),
        "name": name,
    }
    if source_stat is not None:
        cat["source"] = {"path": source_name, "sha256": source_stat.get("sha256"),
                         "size": source_stat.get("size"), "mtime_ns": source_stat.get("mtime_ns")}
    cat["derived"] = derived
    if atem is not None:
        cat["atem"] = atem
    cat["nodes"] = nodes
    return cat


def _derived(*, now: dt.datetime | None, by: str, model: str | None, mode: str, completeness: str,
             chunks: int, dropped: int = 0) -> dict:
    d: dict[str, Any] = {"at": _now(now), "by": by or "person"}
    if mode == "model" and model:
        d["model"] = str(model)
    d.update(mode=mode, completeness=completeness, chunks=int(chunks))
    if dropped:
        d["dropped"] = int(dropped)
    return d


# ---------------------------------------------------------------------------
# Tokens, sentences, chunks
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ɏ]+(?:['’][A-Za-zÀ-ɏ]+)?")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
_BLOCK_START_RE = re.compile(r"\n[ \t]*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>)")


@dataclass(frozen=True)
class _Token:
    word: str            # as written, possessive dropped
    line: int            # 1-based
    initial: bool        # starts a sentence or a block
    heading: bool        # sits on a heading line
    gap_before: str      # the text between the previous token and this one
    start: int = 0       # offsets of `word` in the LF-normalized text
    end: int = 0


def _line_kinds(norm: str) -> tuple[set[int], set[int]]:
    """(heading line numbers, fenced code line numbers), 1-based."""
    headings: set[int] = set()
    code: set[int] = set()
    fenced = False
    for n, line in enumerate(norm.split("\n"), 1):
        if _FENCE_RE.match(line):
            fenced = not fenced
            code.add(n)
        elif fenced:
            code.add(n)
        elif _HEADING_RE.match(line):
            headings.add(n)
    return headings, code


def _tokens(text: str) -> list[_Token]:
    """The text's words in order, each with its line and whether it starts a sentence (after `.!?:`, a blank
    line, a heading or a list marker). Words in fenced code are left out."""
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    starts = [0] + [i + 1 for i, ch in enumerate(norm) if ch == "\n"]
    headings, code = _line_kinds(norm)
    out: list[_Token] = []
    prev_end = 0
    prev: _Token | None = None
    for m in _TOKEN_RE.finditer(norm):
        line = bisect.bisect_right(starts, m.start())
        if line in code:
            continue
        gap = norm[prev_end:m.start()]
        word = m.group(0)
        if word.endswith(("'s", "’s")) and len(word) > 2:
            word = word[:-2]
        heading = line in headings
        if prev is None:
            initial = True
        elif prev.word.lower() in _ABBREVIATIONS and gap.strip() == ".":
            initial = False                  # Dr. Okafor: the full stop is the abbreviation's
        else:
            initial = (bool(re.search(r"[.!?:]", gap)) or "\n\n" in gap or bool(_BLOCK_START_RE.search(gap))
                       or (heading and "\n" in gap) or (prev.heading and not heading))
        tok = _Token(word, line, initial, heading, gap, m.start(), m.start() + len(word))
        out.append(tok)
        prev_end = m.end()
        prev = tok
    return out


_INLINE_MD = [
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[\^[^\]]+\]"), ""),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"(\*\*|__)(.+?)\1"), r"\2"),
    (re.compile(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])"), r"\1"),
    (re.compile(r"<[^>]+>"), ""),
]
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+(?=[\"'“‘(\[]?[A-Z0-9])")


def _paragraphs(text: str) -> list[str]:
    """The text's prose paragraphs, markdown stripped: no frontmatter, headings, code, tables or list markers."""
    lines = _lines(text)
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() in ("---", "..."):
                lines = lines[i + 1:]
                break
    paras: list[str] = []
    cur: list[str] = []
    fenced = False
    for raw in lines:
        if _FENCE_RE.match(raw):
            fenced = not fenced
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if fenced:
            continue
        s = raw.strip()
        if not s or _HEADING_RE.match(raw) or s.startswith("|") or re.match(r"^[-=*_]{3,}$", s):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        s = re.sub(r"^(?:>\s*)+", "", s)
        s = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", s)
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    out = []
    for p in paras:
        for rx, rep in _INLINE_MD:
            p = rx.sub(rep, p)
        p = " ".join(p.split())
        if p:
            out.append(p)
    return out


def sentences(text: str, limit: int | None = None) -> list[str]:
    """The text's prose sentences in order (markdown stripped), at most `limit`."""
    out: list[str] = []
    for para in _paragraphs(text):
        parts = _SENTENCE_SPLIT.split(para)
        merged: list[str] = []
        for s in parts:
            last = merged[-1].split()[-1].lower().rstrip(".") if merged else ""
            if merged and last in _ABBREVIATIONS:
                merged[-1] = f"{merged[-1]} {s}"
            else:
                merged.append(s)
        for s in merged:
            out.append(s.strip())
            if limit is not None and len(out) >= limit:
                return out
    return out


def _first_heading(text: str) -> str | None:
    fenced = False
    for raw in _lines(text):
        if _FENCE_RE.match(raw):
            fenced = not fenced
            continue
        if not fenced and _HEADING_RE.match(raw):
            return raw.strip().lstrip("#").strip() or None
    return None


def text_title(text: str, source_name: str) -> str:
    """A twin's `name`: the text's title (its first heading), else its file name (spec §18.4.1)."""
    head = _first_heading(text)
    return _strip_inline(head) if head else source_name


def _strip_inline(s: str) -> str:
    for rx, rep_ in _INLINE_MD:
        s = rx.sub(rep_, s)
    return " ".join(s.split())


def _cut_words(s: str, n: int) -> str:
    words = s.split()
    return s if len(words) <= n else " ".join(words[:n]).rstrip(",;:") + "…"


@dataclass(frozen=True)
class Chunk:
    """One passage the model reads: `id` from 1, its 1-based inclusive line range, and its lines numbered."""
    id: int
    start_line: int
    end_line: int
    text_numbered: str


def _numbered(lines: list[str], a: int, b: int) -> str:
    return "\n".join(f"{n}| {lines[n - 1]}" for n in range(a, b + 1))


def chunk(text: str) -> list[Chunk]:
    """The text's passages: split at headings (outside code fences), consecutive short sections packed together
    up to ~1,200 tokens, a longer section cut into ~1,200-token windows of whole paragraphs with one paragraph of
    overlap (a paragraph longer than a window is cut by lines). Lines are numbered as an editor numbers them."""
    lines = _lines(text)
    if not any(ln.strip() for ln in lines):
        return []
    n = len(lines)
    cost = [len(ln) + 1 for ln in lines]

    def chars(a: int, b: int) -> int:        # 1-based inclusive
        return sum(cost[a - 1:b])

    # Sections: a heading starts one.
    starts = [1]
    fenced = False
    for i, raw in enumerate(lines, 1):
        if _FENCE_RE.match(raw):
            fenced = not fenced
            continue
        if not fenced and i > 1 and _HEADING_RE.match(raw):
            starts.append(i)
    sections = [(s, (starts[k + 1] - 1) if k + 1 < len(starts) else n) for k, s in enumerate(starts)]

    def windows(a: int, b: int) -> list[tuple[int, int]]:
        paras: list[tuple[int, int]] = []
        i = a
        while i <= b:
            if not lines[i - 1].strip():
                i += 1
                continue
            j = i
            while j + 1 <= b and lines[j].strip():
                j += 1
            # a paragraph longer than a window is cut into line runs
            k = i
            while k <= j:
                e = k
                while e + 1 <= j and chars(k, e + 1) <= CHUNK_CHARS:
                    e += 1
                paras.append((k, e))
                k = e + 1
            i = j + 1
        out: list[tuple[int, int]] = []
        p = 0
        while p < len(paras):
            q = p
            while q + 1 < len(paras) and chars(paras[p][0], paras[q + 1][1]) <= CHUNK_CHARS:
                q += 1
            out.append((paras[p][0], paras[q][1]))
            if q + 1 >= len(paras):
                break
            p = q if q > p else q + 1          # one paragraph of overlap, but always forward
        return out

    ranges: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    for a, b in sections:
        if chars(a, b) > CHUNK_CHARS:
            if cur:
                ranges.append(cur)
                cur = None
            ranges.extend(windows(a, b))
            continue
        if cur and chars(cur[0], b) <= CHUNK_CHARS:
            cur = (cur[0], b)
        else:
            if cur:
                ranges.append(cur)
            cur = (a, b)
    if cur:
        ranges.append(cur)

    out: list[Chunk] = []
    for a, b in ranges:
        while a <= b and not lines[a - 1].strip():
            a += 1
        while b >= a and not lines[b - 1].strip():
            b -= 1
        if a > b:
            continue
        out.append(Chunk(len(out) + 1, a, b, _numbered(lines, a, b)))
    return out


# ---------------------------------------------------------------------------
# The lexical pre-pass: candidate terms (FEED-grounded) and entity candidates
# ---------------------------------------------------------------------------

def _term_table(text: str, lookup: LookupFn) -> list[dict]:
    """The ranked candidate terms: `[{word, key, count, first_line, last_line, entry}]`, `word` being FEED's
    headword when FEED resolves the token (forms fold into it), the token otherwise."""
    seen: dict[str, dict] = {}
    n_words = 0
    for t in _tokens(text):
        n_words += 1
        if "'" in t.word or "’" in t.word:
            continue
        key = _fold(t.word).lower()
        if len(key) < TERM_MIN_LETTERS or key in STOP_WORDS or not key.isalpha():
            continue
        rec = seen.setdefault(key, {"count": 0, "first_line": t.line, "last_line": t.line,
                                    "lower": False, "mid_cap": False})
        rec["count"] += 1
        rec["last_line"] = t.line
        if t.heading:
            continue
        if t.word[0].islower():
            rec["lower"] = True
        elif not t.initial:
            rec["mid_cap"] = True
    # Names are entities, never terms (FEED holds no proper nouns, so rarity would rank "Aquinas" first): a word
    # capitalised anywhere but at a sentence start, or part of an entity candidate's name, is left out. And when
    # FEED is there, a word the text only ever capitalises (at sentence starts) that FEED does not know is a name
    # too ("Averroes wrote …").
    named = {_fold(w).lower() for e in _entity_table(text) for w in e["name"].split()}
    keys = [k for k, r in seen.items() if not r["mid_cap"] and k not in named]
    try:
        found = lookup(keys) or {}
    except Exception:  # noqa: BLE001 — no FEED is a scaffold without grounding, never a failure
        found = {}
    if any(isinstance(v, dict) for v in found.values()):
        keys = [k for k in keys if seen[k]["lower"] or isinstance(found.get(_feed_key(k)) or found.get(k), dict)]
    groups: dict[str, dict] = {}
    for k in keys:
        r = seen[k]
        entry = found.get(_feed_key(k)) or found.get(k)
        head = str(entry.get("word")) if isinstance(entry, dict) and entry.get("word") else k
        g = groups.get(head)
        if g is None:
            groups[head] = {"word": head, "key": k, "count": r["count"], "first_line": r["first_line"],
                            "last_line": r["last_line"], "entry": entry if isinstance(entry, dict) else None}
        else:
            g["count"] += r["count"]
            g["first_line"] = min(g["first_line"], r["first_line"])
            g["last_line"] = max(g["last_line"], r["last_line"])
    rows = list(groups.values())
    known = any(r["entry"] is not None for r in rows)

    def band(r: dict) -> int:
        b = (r["entry"] or {}).get("frequency_rank")
        return b if isinstance(b, int) and not isinstance(b, bool) else UNKNOWN_BAND

    if known:
        rows.sort(key=lambda r: (band(r), -r["count"], r["first_line"], r["word"]))
    else:
        rows.sort(key=lambda r: (-r["count"], r["first_line"], r["word"]))
    return rows[:term_limit(n_words)]


def term_limit(n_words: int) -> int:
    """How many candidate terms a text of `n_words` words gets: 40 per 2,000 words, at least 6, at most 60."""
    return min(TERMS_MAX, max(TERMS_MIN, round(TERMS_PER_WINDOW * n_words / TERMS_WINDOW_WORDS)))


def candidate_terms(text: str, *, lookup: LookupFn | None = None) -> list[str]:
    """The words a text leans on, deterministically (plan §7.2): tokens of four letters or more, not stop words,
    not names (a word capitalised other than at a sentence start, or in an entity candidate's name, or only ever
    capitalised and unknown to FEED, belongs to `entity_candidates`); a form folded into its FEED headword; ranked rarest first by FEED's frequency band when FEED
    knows the words (a word FEED lacks ranks as rare), else by how often the text uses them; the top 40 per
    2,000 words, at least 6 and at most 60 (`term_limit`). `lookup` is `dictionary.lookup_many`'s shape (the
    default)."""
    return [r["word"] for r in _term_table(text, lookup or _default_lookup)]


def _entity_table(text: str) -> list[dict]:
    """`[{name, kind, count, first_line}]`: runs of capitalised words that are not merely sentence-initial, in
    order of first appearance; a run that is part of a longer one is folded into it."""
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    runs: list[list[_Token]] = []
    cur: list[_Token] = []
    conn: list[_Token] = []                   # one connector word held until a capitalised word follows it
    for t in _tokens(text):
        cap = t.word[:1].isupper() and not t.heading
        if cap:
            last = conn[-1] if conn else (cur[-1] if cur else None)
            joins = last is not None and (t.gap_before == " " or (
                not conn and t.gap_before.strip() == "." and last.word.lower() in HONORIFICS))
            if joins:
                cur += conn + [t]
            else:
                if cur:
                    runs.append(cur)
                cur = [t]
            conn = []
            continue
        if cur and not conn and t.word.lower() in NAME_CONNECTORS and t.gap_before == " ":
            conn = [t]
            continue
        if cur:
            runs.append(cur)
        cur, conn = [], []
    if cur:
        runs.append(cur)

    found: dict[str, dict] = {}
    order: list[str] = []
    for run in runs:
        # Strip the words that only open the sentence ("The Support Lead" → "Support Lead").
        while run and run[0].initial and run[0].word.lower() in _LEADERS | STOP_WORDS:
            run = run[1:]
        while run and run[-1].word.lower() in NAME_CONNECTORS:
            run = run[:-1]
        if not run:
            continue
        words = [t.word for t in run]
        if all(len(w) < 2 for w in words) or words == ["I"]:
            continue
        if all(w.lower() in MONTHS_AND_DAYS for w in words if w.lower() not in NAME_CONNECTORS):
            continue
        if all(w.lower() in STOP_WORDS or w.lower() in _LEADERS for w in words):
            continue
        if all(t.initial for t in run if t.word[:1].isupper()) and len(run) == 1:
            continue                          # one capitalised word that only starts a sentence
        name = " ".join(norm[run[0].start:run[-1].end].split())     # as written: "Dr. Ada Lovelace"
        rec = found.get(name)
        if rec is None:
            found[name] = {"name": name, "count": 1, "first_line": run[0].line, "at": run[0].start, "words": words}
            order.append(name)
        else:
            rec["count"] += 1
    # A run inside a longer run ("Mara" inside "Mara Okafor") is the same participant: fold it in.
    names = [found[n] for n in order]
    keep: list[dict] = []
    for rec in names:
        longer = next((o for o in names if o is not rec and len(o["words"]) > len(rec["words"])
                       and _is_sub(rec["words"], o["words"])), None)
        if longer is not None:
            longer["count"] += rec["count"]
            longer["first_line"] = min(longer["first_line"], rec["first_line"])
            longer["at"] = min(longer["at"], rec["at"])
            continue
        keep.append(rec)
    keep.sort(key=lambda r: r["at"])
    for rec in keep:
        rec["kind"] = _entity_kind(rec["words"])
        del rec["words"], rec["at"]
    return keep


def _is_sub(short: list[str], long: list[str]) -> bool:
    n = len(short)
    return any(long[i:i + n] == short for i in range(len(long) - n + 1))


def _entity_kind(words: list[str]) -> str:
    first, last = words[0].lower().rstrip("."), words[-1].lower()
    if first in HONORIFICS and len(words) > 1:
        return "person"
    if last in ORG_WORDS:
        return "org"
    if last in PLACE_WORDS:
        return "place"
    return "thing"


def entity_candidates(text: str) -> list[str]:
    """Capitalised words and runs of them that are not merely sentence-initial, in order of first appearance
    (months and weekdays are times, not entities; a shorter run inside a longer one folds into it)."""
    return [r["name"] for r in _entity_table(text)]


def _feed_block(entry: dict | None) -> dict:
    if not entry:
        return {"pending": PENDING_NOT_IN_FEED}
    pos = entry.get("pos_primary") or str(entry.get("pos") or "").split(";")[0].strip()
    out: dict[str, Any] = {"word": str(entry.get("word") or "")}
    if pos:
        out["pos"] = str(pos)
    out["origin"] = "user" if entry.get("origin") == "user" else "feed"
    return out


# ---------------------------------------------------------------------------
# Atems: the rules scaffold, reading a model's answer
# ---------------------------------------------------------------------------

def _pending(question: str) -> dict:
    return {"pending": question}


def rules_atem(text: str) -> dict:
    """The scaffold atem (spec §18.3.5): the line is the first sentence cut to 25 words, the focus the first two
    sentences, push and pull open questions. A text with no prose sentence falls back to its first heading."""
    sents = sentences(text, limit=2)
    if not sents:
        head = _first_heading(text) or next((ln.strip() for ln in _lines(text) if ln.strip()), "")
        sents = [head] if head else []
    if not sents:
        line: Any = _pending("the text is empty")
        focus: Any = _pending("the text is empty")
    else:
        line = _cut_words(sents[0], LINE_MAX_WORDS)
        focus = _cut_words(" ".join(sents[:2]), FOCUS_MAX_WORDS)
    return {"line": line, "focus": focus, "push": _pending(PENDING_NO_MODEL), "pull": _pending(PENDING_NO_MODEL)}


def _strip_fences(text: str) -> str:
    m = re.search(r"```[A-Za-z0-9_-]*\s*\n(.*?)(?:\n```|$)", text, re.S)
    return m.group(1) if m else text


def _yaml(text: str) -> Any:
    try:
        return macrocosm.yaml_load(text)
    except Exception:  # noqa: BLE001 — yaml errors, impossible dates, anything a model can write
        return None


def _read_mapping(text: str, keys: Iterable[str]) -> dict | None:
    body = _strip_fences(text or "")
    data = _yaml(body)
    if not isinstance(data, dict):
        keys = tuple(keys)
        m = re.search(rf"^(?:{'|'.join(map(re.escape, keys))})\s*:", body, re.M)
        data = _yaml(body[m.start():]) if m else None
    return data if isinstance(data, dict) else None


def _atem_part(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return " ".join(v.split())
    return None


def _stance_profile(v: Any) -> dict:
    if not isinstance(v, dict):
        return {}
    out = {}
    for s in STANCES:
        n = v.get(s)
        if isinstance(n, bool):
            continue
        if isinstance(n, (int, float)) and n >= 0:
            out[s] = int(n)
    return out


def _read_atem(text: str) -> dict:
    """A model's atem answer as `{line, focus, push, pull, stance_profile}`; a part it did not give is an open
    question (and the whole answer unreadable is four of them)."""
    data = _read_mapping(text, ("line", "focus", "push", "pull"))
    if data is None:
        q = _pending("the model's answer could not be read")
        return {"line": q, "focus": dict(q), "push": dict(q), "pull": dict(q), "stance_profile": {}}
    out: dict[str, Any] = {}
    for part in ("line", "focus", "push", "pull"):
        v = _atem_part(data.get(part))
        out[part] = v if v is not None else _pending(f"the model gave no {part}")
    out["stance_profile"] = _stance_profile(data.get("stance_profile") or data.get("stances"))
    return out


def atem_block(atem: dict) -> dict:
    """`{line, focus, push, pull}` as a twin writes it: each a string or an open question."""
    out: dict[str, Any] = {}
    for part in ("line", "focus", "push", "pull"):
        v = atem.get(part) if isinstance(atem, dict) else None
        if isinstance(v, str) and v.strip():
            out[part] = " ".join(v.split())
        elif macrocosm.is_pending(v) and isinstance(v.get("pending"), str) and v["pending"].strip():
            out[part] = {"pending": v["pending"].strip()}
        else:
            out[part] = _pending(PENDING_NO_MODEL if part in ("push", "pull") else f"no {part} was given")
    return out


def _atem_is_scaffold(atem: dict) -> bool:
    return any(macrocosm.is_pending(atem.get(p)) for p in ("push", "pull"))


def _atem_messages(text: str, context: str | None) -> list[dict]:
    ctx = f"Context: {context.strip()}\n\n" if context and context.strip() else ""
    return [{"role": "system", "content": P.ATEM_SYSTEM},
            {"role": "user", "content": P.ATEM_USER.format(context=ctx, text=text)}]


def _edges(text: str) -> str:
    if len(text) <= 2 * ATEM_EDGE_CHARS + 400:
        return f"The whole text:\n{text}"
    return (f"How the text begins:\n{text[:ATEM_EDGE_CHARS]}\n\n"
            f"How it ends:\n{text[-ATEM_EDGE_CHARS:]}")


def _check(should_stop: StopFn | None) -> None:
    if should_stop is not None and should_stop():
        raise DeriveCancelled()


def _progress(on_progress: ProgressFn | None, **fields: Any) -> None:
    if on_progress is not None:
        on_progress(fields)


def derive_atem(text: str, *, context: str | None = None, complete: CompleteFn | None = None,
                now: dt.datetime | None = None, on_progress: ProgressFn | None = None,
                should_stop: StopFn | None = None) -> dict:
    """The atem of a text or passage: `{line, focus, push, pull, stance_profile, mode}` (+ `model` in model mode).

    Rules mode (`complete=None`): the scaffold of `rules_atem`, `stance_profile: {}`. Model mode: one completion
    with ATEM_SYSTEM for a text up to ~4,800 tokens; a longer text is read passage by passage (one completion
    each, a cooperative cancel checked between them) and one more completion makes the whole from the passages'
    atems and the text's first and last ~800 tokens. `now` is accepted for symmetry with the other entry points
    (an atem carries no time of its own; the twin's `derived.at` does)."""
    del now
    if complete is None:
        out = rules_atem(text)
        out.update(stance_profile={}, mode="rules")
        return out
    model = None
    if len(text) <= ATEM_ONE_SHOT_CHARS:
        _check(should_stop)
        _progress(on_progress, phase="atem", chunk=1, chunks=1, message="writing the atem")
        reply, meta = _call(complete, _atem_messages(text, context))
        out = _read_atem(reply)
        model = meta.get("model")
    else:
        parts = chunk(text)
        lines_out: list[str] = []
        for c in parts:
            _check(should_stop)
            _progress(on_progress, phase="reading", chunk=c.id, chunks=len(parts),
                      message=f"reading passage {c.id} of {len(parts)}")
            raw = "\n".join(_lines(text)[c.start_line - 1:c.end_line])
            reply, meta = _call(complete, _atem_messages(raw, context))
            model = model or meta.get("model")
            a = _read_atem(reply)
            if isinstance(a.get("line"), str):
                lines_out.append(f"- lines {c.start_line}-{c.end_line}: {a['line']}")
        _check(should_stop)
        _progress(on_progress, phase="atem", chunk=len(parts), chunks=len(parts), message="writing the atem")
        user = P.ATEM_WHOLE_USER.format(name=context or "the text", atems="\n".join(lines_out) or "- (none)",
                                        body=_edges(text))
        reply, meta = _call(complete, [{"role": "system", "content": P.ATEM_SYSTEM},
                                       {"role": "user", "content": user}])
        model = meta.get("model") or model
        out = _read_atem(reply)
    out["mode"] = "model"
    if model:
        out["model"] = str(model)
    return out


# ---------------------------------------------------------------------------
# Model mode: reading a passage's items, normalizing, checking, repairing, merging
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^([A-Z]):([a-z][a-z0-9-]*)/(.+)$")


def _read_nodes(text: str) -> tuple[list[dict] | None, str | None]:
    """`(items, None)` from a model's reply, or `(None, why)` when no list of items can be read from it."""
    body = _strip_fences(text or "")
    data = _yaml(body)
    if not isinstance(data, (dict, list)):
        m = re.search(r"^nodes\s*:", body, re.M)
        data = _yaml(body[m.start():]) if m else None
    if isinstance(data, dict):
        data = data.get("nodes") if "nodes" in data else ([data] if "id" in data else None)
    if not isinstance(data, list):
        return None, "the reply has no YAML `nodes:` list"
    return [_plain(x) for x in data if isinstance(x, dict)], None


def _ref_fields(kind: str) -> list[str]:
    m = _manifest()
    letter = _kind_module().get(kind)
    return m.refs(letter, kind) if letter else ["links"]


def _map_refs(item: dict, fn: Callable[[str, Any], Any]) -> None:
    """Apply `fn(field, value)` to every reference value of an item in place (the manifest's reference fields:
    `links`, `roles.*`, `defined-by`, `agent`, `patient`, `before`, `after`, `of`). For a link the value is the
    whole entry; `fn` returns the replacement (None drops a list entry)."""
    kind = item.get("type") if isinstance(item.get("type"), str) else ""
    for fpath in _ref_fields(kind):
        head, _, tail = fpath.partition(".")
        if head not in item:
            continue
        if fpath == "links":
            v = item["links"]
            seq = v if isinstance(v, list) else [v]
            new = [x for x in (fn("links", e) for e in seq) if x is not None]
            if new:
                item["links"] = new
            else:
                item.pop("links", None)
            continue
        if tail == "*":
            roles = item[head]
            if isinstance(roles, dict):
                for k in list(roles):
                    roles[k] = fn(f"{head}.{k}", roles[k])
            continue
        v = item[head]
        if isinstance(v, list):
            item[head] = [fn(head, x) for x in v]
        else:
            item[head] = fn(head, v)


# Kind words a model reaches for, read as the emf manifest's kinds (owner's list, plus three obvious ones).
KIND_SYNONYMS = {
    "organization": "org", "organisation": "org", "company": "org", "institution": "org",
    "location": "place", "area": "place",
    "people": "person", "human": "person", "individual": "person",
    "book": "work", "document": "work", "article": "work", "report": "work",
    "object": "thing", "item": "thing", "entity": "thing",
    "idea": "concept", "notion": "concept", "theme": "concept",
    "statement": "claim", "assertion": "claim", "proposition": "claim",
    "action": "event", "step": "event", "transition": "event",
    "word": "term",
}
# Words a model uses for a stance or a salience the closed lists spell otherwise.
STANCE_SYNONYMS = {"given": "axiom", "definition": "axiom", "witnessed": "observed", "measured": "observed",
                   "inferred": "deduced", "inference": "deduced", "reasoned": "deduced", "belief": "opinion",
                   "judgement": "opinion", "judgment": "opinion", "presupposed": "assumed", "reported": "hearsay",
                   "claimed": "hearsay", "rumour": "hearsay", "rumor": "hearsay"}
SALIENCE_SYNONYMS = {"medium": "normal", "moderate": "normal", "average": "normal", "major": "high",
                     "important": "high", "key": "high", "central": "critical", "essential": "critical",
                     "minor": "low", "peripheral": "low"}
_CANON_LINES = re.compile(r"^\d+(?:-\d+)?$")


def _closed_match(v: Any, allowed: Iterable[str]) -> str | None:
    """A model's word read against a closed list: lowercased; exact; the one entry it begins (`hig` → high); the
    one entry it begins with (`opinionated` → opinion); else the one entry sharing at least five leading letters
    with it (`observation` → observed, `assumption` → assumed). None when that is not one entry."""
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().lower()
    allowed = list(allowed)
    if s in allowed:
        return s
    for hits in ([a for a in allowed if a.startswith(s)] if len(s) >= 2 else [],
                 [a for a in allowed if s.startswith(a)]):
        if len(hits) == 1:
            return hits[0]
    scored = [(len(os.path.commonprefix([s, a])), a) for a in allowed]
    best = max((n for n, _ in scored), default=0)
    top = [a for n, a in scored if n == best]
    return top[0] if best >= 5 and len(top) == 1 else None


def _confidence(v: Any) -> float | None:
    """A confidence as a number from 0 to 1: a numeric string read, a percentage (2 ≤ n ≤ 100) divided by 100,
    anything else clamped. None when it is not a number at all."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        try:
            v = float(v.strip().rstrip("%"))
        except ValueError:
            return None
    if not isinstance(v, (int, float)) or v != v:
        return None
    v = float(v)
    if 2 <= v <= 100:                         # a percentage
        v /= 100
    return min(1.0, max(0.0, v))


def _kind_of(it: dict, kinds: dict[str, str]) -> tuple[str | None, int]:
    """`(kind, fixes)`: trust a kind the id declares for its own module; else the item's `type`; else the id's kind
    wherever it is declared — each through the synonyms (organization → org …). The id is then rebuilt in the
    kind's own module (`E:concept/x` → `K:concept/x`)."""
    m = _manifest()
    raw = it.get("id").strip() if isinstance(it.get("id"), str) else ""
    idm = _ID_RE.match(raw)
    id_mod, id_kind = (idm.group(1), idm.group(2).lower()) if idm else (None, None)
    t = it.get("type").strip().lower() if isinstance(it.get("type"), str) else None

    def syn(k: str | None) -> str | None:
        return KIND_SYNONYMS.get(k, k) if k else None

    if id_kind and id_mod in m.modules() and id_kind in m.kinds(id_mod):
        kind = id_kind
    elif syn(t) in kinds:
        kind = syn(t)
    elif syn(id_kind) in kinds:
        kind = syn(id_kind)
    else:
        return None, 0
    fixes = int(t != kind) + int(bool(idm) and (id_mod != kinds[kind] or id_kind != kind))
    return kind, fixes


def _normalize_item(it: dict, *, chunk_: Chunk, source: str, kinds: dict[str, str],
                    atem_id: str) -> tuple[dict | None, str | None, int]:
    """One item made checkable without changing what it says: `(item, None, fixes)`, or `(None, why, 0)` when it
    names no kind or no name. Fixes are counted (they go in `info["normalized"]`): a kind read through a synonym
    or the id, a module moved, a name taken from the id, a missing summary (the name), stance/salience/rel words
    matched to the closed lists, a span written any other way than `{lines: "a-b"}`, provenance filled or
    repaired (missing → `{mode: derived, sources: [<file>#La-Lb], confidence: 0.7, state: known}`), a confidence
    read or clamped. What still breaks a check after this goes to the repair turn."""
    kind, fixes = _kind_of(it, kinds)
    raw = it.get("id").strip() if isinstance(it.get("id"), str) else ""
    name = it.get("name")
    if isinstance(name, (int, float)) and not isinstance(name, bool):
        name = it["name"] = str(name)
        fixes += 1
    if not (isinstance(name, str) and name.strip()):
        idm = _ID_RE.match(raw)
        if idm:
            name = idm.group(3).replace("-", " ").strip()
            it["name"] = name
            fixes += 1
    if kind is None or not (isinstance(name, str) and name.strip()):
        return None, ("needs a type from the item shapes" if kind is None else "needs a name"), 0
    it["type"] = kind
    it["id"] = atem_id if kind == "atem" else f"{kinds[kind]}:{kind}/{item_slug(name)}"
    if not (isinstance(it.get("summary"), str) and it["summary"].strip()):
        it["summary"] = name.strip()          # missing, empty, or not text
        fixes += 1
    for field, allowed, synonyms in (("stance", STANCES, STANCE_SYNONYMS),
                                     ("salience", SALIENCE, SALIENCE_SYNONYMS)):
        if field in it and it[field] not in allowed:
            word = it[field].strip().lower() if isinstance(it[field], str) else it[field]
            hit = synonyms.get(word) if isinstance(word, str) else None
            hit = hit or _closed_match(it[field], allowed)
            if hit:
                it[field] = hit
                fixes += 1
    rels = _manifest().link_rels or []
    if isinstance(it.get("links"), list):
        for link in it["links"]:
            if isinstance(link, dict) and link.get("rel") not in rels:
                hit = _closed_match(link.get("rel"), rels)
                if hit:
                    link["rel"] = hit
                    fixes += 1
    it.pop("feed", None)                      # FEED grounding is the engine's to write, after the merge
    # span: {lines: "a-b"} inside the passage, however it came
    span = it.get("span")
    if isinstance(span, dict):
        ab = parse_lines(span.get("lines"))
        if ab and not (isinstance(span.get("lines"), str) and _CANON_LINES.match(span["lines"].strip())):
            fixes += 1
    else:
        ab = parse_lines(span)
        if span is not None:
            fixes += 1
        span = {}
    if not ab and "lines" in it:
        ab = parse_lines(it.get("lines"))
        fixes += 1
    it.pop("lines", None)
    if ab:
        a, b = max(ab[0], chunk_.start_line), min(ab[1], chunk_.end_line)
        if a > b:
            a, b = chunk_.start_line, chunk_.end_line
    else:
        a, b = chunk_.start_line, chunk_.end_line
    new_span = _span(a, b)
    for key in ("start", "end"):
        if isinstance(span.get(key), str) and span[key].strip():
            new_span[key] = " ".join(span[key].split())[:SNIPPET]
    it["span"] = new_span
    # provenance
    closed = _manifest().closed_lists()
    prov = it.get("provenance")
    if not isinstance(prov, dict):
        it["provenance"] = {"mode": "derived", "sources": [_locator(source, a, b)],
                            "confidence": MODEL_CONFIDENCE, "state": "known"}
        return it, None, fixes + 1
    if prov.get("mode") not in closed.get("provenance.mode", ["derived"]):
        prov["mode"] = "derived"
        fixes += 1
    srcs = prov.get("sources")
    if not (isinstance(srcs, list) and srcs and all(isinstance(s, str) for s in srcs)):
        prov["sources"] = [_locator(source, a, b)]
        fixes += 1
    c = _confidence(prov.get("confidence"))
    if c is None:
        prov["confidence"] = MODEL_CONFIDENCE
        fixes += 1
    elif c != prov.get("confidence") or isinstance(prov.get("confidence"), (str, bool)):
        prov["confidence"] = c
        fixes += 1
    if "state" not in prov:
        prov["state"] = "known"
    elif prov["state"] not in closed.get("provenance.state", ["known"]):
        prov["state"] = "known"
        fixes += 1
    return it, None, fixes


def _normalize(items: list[dict], *, chunk_: Chunk, source: str,
               prefix: str) -> tuple[list[dict], dict, list[tuple[dict, str]], int]:
    """A passage's items, normalized (`_normalize_item`): ids `<M>:<kind>/<slug of the name>` with the passage's
    own references remapped and named references given ids; duplicates within the passage merged. Returns
    `(items, {old id: new id}, [(raw item, why)] for items that could not be placed, fixes)`."""
    kinds = _kind_module()
    remap: dict[str, str] = {}
    out: dict[str, dict] = {}
    unplaced: list[tuple[dict, str]] = []
    fixes = 0
    atems = 0
    for raw in items:
        old = raw.get("id").strip() if isinstance(raw.get("id"), str) else None
        it = _plain(raw)
        atem_id = f"X:atem/{prefix}-{atems + 1}"
        item, why, n = _normalize_item(it, chunk_=chunk_, source=source, kinds=kinds, atem_id=atem_id)
        if item is None:
            unplaced.append((raw, why or "cannot be placed"))
            continue
        if item["id"] == atem_id:
            atems += 1
        fixes += n
        if old and old != item["id"]:
            remap.setdefault(old, item["id"])
        if item["id"] in out:
            _merge_into(out[item["id"]], item)
        else:
            out[item["id"]] = item
    result = list(out.values())
    for it in result:
        _map_refs(it, lambda f, v: _remap_value(v, remap))
    fixes += _resolve_names(result)
    return result, remap, unplaced, fixes


def _remap_value(v: Any, remap: dict[str, str]) -> Any:
    if isinstance(v, str):
        return remap.get(v.strip(), v)
    if isinstance(v, dict) and isinstance(v.get("to"), str):
        v["to"] = remap.get(v["to"].strip(), v["to"])
    return v


def _resolve_names(items: list[dict]) -> int:
    """References written as words: a named reference field (`agent: the orchard volunteers`) or a link's `to`
    that holds an item's name is given the item's id; one that names no item of the passage keeps its words as
    an open question (`{pending: "agent: the orchard volunteers is not an item of this twin"}`, a link entry as a
    whole), since a reference field holds ids. Wildcard roles keep plain words as text. Returns how many it fixed."""
    by_name = {}
    for it in items:
        if isinstance(it.get("name"), str):
            by_name.setdefault(" ".join(it["name"].lower().split()), it["id"])
            by_name.setdefault(item_slug(it["name"]), it["id"])
    fixed = [0]

    def lookup(words: str) -> str | None:
        return by_name.get(" ".join(words.lower().split())) or by_name.get(item_slug(words))

    def fix(field: str, v: Any) -> Any:
        if field.startswith("roles."):
            return v
        if field == "links":
            to = v.get("to") if isinstance(v, dict) else v
            if isinstance(to, str) and to.strip() and not _ID_RE.match(to.strip()):
                fixed[0] += 1
                hit = lookup(to)
                if hit and isinstance(v, dict):
                    v["to"] = hit
                    return v
                if hit:
                    return hit
                rel = v.get("rel") if isinstance(v, dict) else None
                return _pending(f"{rel + ' ' if isinstance(rel, str) else ''}{' '.join(to.split())}: "
                                "not an item of this twin")
            return v
        if isinstance(v, str) and v.strip() and not _ID_RE.match(v.strip()):
            fixed[0] += 1
            return lookup(v) or _pending(f"{field}: {' '.join(v.split())} is not an item of this twin")
        return v

    for it in items:
        _map_refs(it, fix)
    return fixed[0]


def _merge_into(first: dict, other: dict) -> None:
    """Duplicates merge: the first wins, its span is extended to cover both, the other's sources are appended."""
    a = parse_lines((first.get("span") or {}).get("lines")) if isinstance(first.get("span"), dict) else None
    b = parse_lines((other.get("span") or {}).get("lines")) if isinstance(other.get("span"), dict) else None
    if a and b:
        first["span"] = {**first["span"], **_span(min(a[0], b[0]), max(a[1], b[1]))}
    elif b and not a:
        first["span"] = dict(other["span"])
    fp, op = first.get("provenance"), other.get("provenance")
    if isinstance(fp, dict) and isinstance(op, dict):
        fs = fp.get("sources") if isinstance(fp.get("sources"), list) else []
        for s in op.get("sources") or []:
            if isinstance(s, str) and s not in fs:
                fs.append(s)
        fp["sources"] = fs


def _lint_items(items: list[dict], workdir: Path, label: str, *, ignore: tuple[str, ...] = ()) -> dict[str, list]:
    """Check items as a throwaway `emf/1` volume in `workdir`: `{item id: [problems]}` for the errors (the key ""
    for problems with no item). `ignore` names checks left for later (a passage's references to items another
    passage holds are resolved after the merge)."""
    doc = {"oes": EMF_OES, "macrocosm": macrocosm.MACROCOSM_VERSION, "id": "emf/derivation", "name": label,
           "nodes": items}
    path = workdir / f"{label}.cosm"
    path.write_text(_dump(doc), encoding="utf-8")
    report = macrocosm.lint(macrocosm.load_volume(path))
    bad: dict[str, list] = {}
    for p in report.errors:
        if p.check in ignore or p.check == "catalog-key":
            continue
        bad.setdefault(p.item, []).append(p)
    return bad


def _problem_lines(bad: dict[str, list], extra: list[str]) -> str:
    lines = list(extra)
    for key, probs in bad.items():
        for p in probs:
            where = f"{key}" + (f" {p.field}" if p.field else "")
            lines.append(f"- {where or 'the list'}: {p.message}")
    return "\n".join(lines[:40]) or "- the reply could not be read"


def _passage_terms(table: list[dict], c: Chunk) -> str:
    rows = [r for r in table if r["entry"] and c.start_line <= r["first_line"] <= c.end_line
            or (r["entry"] and r["first_line"] < c.start_line <= r["last_line"])]
    out = []
    for r in rows[:PASSAGE_TERMS]:
        e = r["entry"]
        definition = " ".join(str(e.get("definition") or "").split())
        if len(definition) > PASSAGE_TERM_CHARS:
            definition = definition[:PASSAGE_TERM_CHARS - 1].rstrip() + "…"
        pos = e.get("pos_primary") or str(e.get("pos") or "").split(";")[0].strip()
        out.append(f"- {r['word']}, {pos or 'word'}: {definition}")
    return "\n".join(out) or "- (none)"


_DASH_RE = re.compile(r"^(\s*)-(?:\s|$)")


def _parse_block(block: str) -> dict | None:
    data = _yaml(block)
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return _plain(data[0])
    return None


def _salvage(text: str, finish: str | None) -> tuple[list[dict], list[str], bool, bool]:
    """`(items, unreadable item texts, cut, a list was there)` from a model's reply (`nodes: []` is a list: the
    passage holds nothing; prose with no list in it is not). A reply cut off by the budget (`finish_reason`
    "length", or — when the reason is unknown — a list whose last item does not parse) keeps every complete item
    before the cut and drops the cut one (`salience: hig` parses, but is not the model's whole item). A reply
    that parses whole is read whole. Otherwise each `- ` item is read on its own; the ones that can't be read are
    returned as text, for the repair turn."""
    body = _strip_fences(text or "")
    cut = finish == "length"
    if not cut:
        whole, _why = _read_nodes(body)
        if whole is not None:
            return whole, [], False, True
    lines = body.split("\n")
    start = next((i + 1 for i, ln in enumerate(lines) if re.match(r"^\s*nodes\s*:\s*$", ln)), 0)
    dashes = [(i, len(m.group(1))) for i in range(start, len(lines)) if (m := _DASH_RE.match(lines[i]))]
    if not dashes:
        return [], [], cut, False
    indent = min(n for _, n in dashes)
    heads = [i for i, n in dashes if n == indent]
    blocks = []
    for k, h in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        blocks.append("\n".join(ln[indent:] if not ln[:indent].strip() else ln for ln in lines[h:end]).rstrip())
    parsed = [_parse_block(b) for b in blocks]
    if not cut and finish is None and parsed and parsed[-1] is None:
        cut = True                            # unknown reason, and the tail does not parse: cut off
    if cut:
        blocks, parsed = blocks[:-1], parsed[:-1]
    return ([p for p in parsed if p is not None],
            [b for b, p in zip(blocks, parsed) if p is None], cut, True)


def _read_passage(c: Chunk, *, complete: CompleteFn, source: str, table: list[dict], workdir: Path,
                  stats: dict, on_progress: ProgressFn | None, chunks: int) -> tuple[list[dict], dict, int]:
    """One passage, in at most three completions, each with an output budget (`EMF_MAX_TOKENS`, bounded by the
    model's window): the reading; ONE continuation when the reading was cut off (after the last complete item);
    ONE repair of only the items that still fail after normalization (or, when the reading held no list at all,
    one retry). Returns `(items that pass, remap, dropped)`: `dropped` counts the items that still fail, an item
    lost to a cut the continuation could not recover, and one per passage with no readable list."""
    prefix = f"c{c.id}"
    system = {"role": "system", "content": P.EMF_SYSTEM.format(source=source)}
    user = P.EMF_USER.format(terms=_passage_terms(table, c), source=source, start=c.start_line, end=c.end_line,
                             passage=c.text_numbered)

    def ask(extra: str = "") -> tuple[str, dict]:
        reply, meta = _call(complete, [system, {"role": "user", "content": user + extra}],
                            max_tokens=EMF_MAX_TOKENS)
        stats["model"] = stats.get("model") or meta.get("model")
        return reply, meta

    reply, meta = ask()
    raw, broken, cut, listed = _salvage(reply, meta.get("finish_reason"))
    lost = 0
    if cut:
        stats["continued"] = stats.get("continued", 0) + 1
        _progress(on_progress, phase="continuing", chunk=c.id, chunks=chunks,
                  message=f"passage {c.id} of {chunks} was cut off; asking for the rest")
        ids = [str(x["id"]).strip() for x in raw if isinstance(x.get("id"), str) and x["id"].strip()]
        extra = (P.EMF_CONTINUE.format(ids="\n".join(f"- {i}" for i in ids), last=ids[-1]) if ids
                 else P.EMF_RESTART)
        reply2, meta2 = ask(extra)
        raw2, broken2, cut2, listed2 = _salvage(reply2, meta2.get("finish_reason"))
        raw, broken, listed = raw + raw2, broken + broken2, listed or listed2
        lost += int(cut2)
    retried = False
    if not listed:
        _progress(on_progress, phase="repairing", chunk=c.id, chunks=chunks,
                  message=f"passage {c.id} of {chunks} had no list; asking once more")
        reply3, meta3 = ask(P.EMF_RETRY)
        raw, broken, cut3, listed = _salvage(reply3, meta3.get("finish_reason"))
        lost += int(cut3)
        if not listed:
            return [], {}, lost + 1
        retried = True
    items, remap, unplaced, fixes = _normalize(raw, chunk_=c, source=source, prefix=prefix)
    stats["normalized"] = stats.get("normalized", 0) + fixes
    bad = _lint_items(items, workdir, f"{prefix}-check", ignore=("ref-unresolved",)) if items else {}
    if "" in bad:                             # a problem with no item: none can be trusted to pass
        bad.update({it["id"]: bad[""] for it in items})
    passing = [it for it in items if it["id"] not in bad]
    failing = [it for it in items if it["id"] in bad]
    n_fail = len(failing) + len(unplaced) + len(broken)
    if not n_fail or retried:
        return passing, remap, lost + n_fail
    _progress(on_progress, phase="repairing", chunk=c.id, chunks=chunks,
              message=f"repairing {n_fail} item{'s' if n_fail != 1 else ''} of passage {c.id} of {chunks}")
    shown = macrocosm.dump({"nodes": failing + [r for r, _ in unplaced]}) if failing or unplaced else ""
    shown += "".join(f"\nThis item could not be read as YAML:\n{b}\n" for b in broken)
    problems = _problem_lines({k: v for k, v in bad.items() if k}, [f"- {r.get('id') or 'an item'}: {why}"
                                                                    for r, why in unplaced]
                              + ["- an item that is not valid YAML"] * bool(broken))
    reply4, meta4 = ask(P.EMF_REPAIR.format(items=shown.strip(), problems=problems))
    raw4, _broken4, _cut4, _listed4 = _salvage(reply4, meta4.get("finish_reason"))
    fixed, remap4, _unplaced4, fixes4 = _normalize(raw4, chunk_=c, source=source, prefix=f"{prefix}r")
    stats["normalized"] += fixes4
    # Only what stands in for a failed item is taken: an item with a failed item's id first, then — for the
    # failed items it did not answer by id (renamed) and the ones that had no usable id (unplaced, unreadable) —
    # as many new ones. Anything the model repeated from the items that passed is ignored.
    have = {it["id"] for it in passing}
    want = {it["id"] for it in failing}
    has_atem = any(it.get("type") == "atem" for it in passing)
    fresh = [it for it in fixed if it["id"] not in have]
    taken = [it for it in fresh if it["id"] in want]
    taken = [it for i, it in enumerate(taken) if it["id"] not in {t["id"] for t in taken[:i]}]
    slots = len(unplaced) + len(broken) + len(want) - len(taken)
    for it in fresh:
        if slots <= 0:
            break
        if it["id"] in want or any(t["id"] == it["id"] for t in taken) or (it.get("type") == "atem" and has_atem):
            continue
        taken.append(it)
        slots -= 1
    bad4 = _lint_items(passing + taken, workdir, f"{prefix}-repair", ignore=("ref-unresolved",)) if taken else {}
    good = [it for it in taken if it["id"] not in bad4]
    for k, v in remap4.items():
        remap.setdefault(k, v)
    return passing + good, remap, lost + max(0, n_fail - len(good))


def _id_shaped(v: Any) -> bool:
    return isinstance(v, str) and bool(_ID_RE.match(v.strip())) and v.strip()[0] in MODULE_ORDER


def _resolve_after_merge(items: list[dict], remap: dict[str, str]) -> None:
    """Cross-passage references, after the merge: an id one passage wrote and another renamed is remapped; one
    that names no item of the twin becomes an open question (a dangling link entry becomes one as a whole)."""
    ids = {it["id"] for it in items}

    def fix(field: str, v: Any) -> Any:
        if field == "links":
            to = v.get("to") if isinstance(v, dict) else v
            if isinstance(to, str):
                to2 = remap.get(to.strip(), to.strip())
                if to2 in ids:
                    if isinstance(v, dict):
                        v["to"] = to2
                        return v
                    return to2
                rel = v.get("rel") if isinstance(v, dict) else None
                return _pending(f"{rel + ' ' if isinstance(rel, str) else ''}{to.strip()}: not an item of this twin")
            return v
        if isinstance(v, str) and _id_shaped(v):
            v2 = remap.get(v.strip(), v.strip())
            return v2 if v2 in ids else _pending(f"{v.strip()} is not an item of this twin")
        return v

    for it in items:
        _map_refs(it, fix)


def _order(items: list[dict]) -> list[dict]:
    rank = {m: i for i, m in enumerate(MODULE_ORDER)}
    return sorted(items, key=lambda it: rank.get(str(it.get("id", " "))[:1], len(rank)))


def _ground_terms(items: list[dict], lookup: LookupFn) -> None:
    """Every `L:term` says where its word stands in FEED (spec §18.4.3), deterministically: `feed: {word, pos,
    origin}` from FEED's row for the name (a form resolves to its headword), else `{pending: "not in FEED"}`. A
    term with no `sense` takes FEED's definition."""
    terms = [it for it in items if it.get("type") == "term"]
    if not terms:
        return
    try:
        found = lookup([str(it.get("name") or "") for it in terms]) or {}
    except Exception:  # noqa: BLE001
        found = {}
    for it in terms:
        name = str(it.get("name") or "")
        entry = found.get(_feed_key(name)) if name else None
        it["feed"] = _feed_block(entry if isinstance(entry, dict) else None)
        if not (isinstance(it.get("sense"), str) and it["sense"].strip()) and isinstance(entry, dict) \
                and entry.get("definition"):
            it["sense"] = " ".join(str(entry["definition"]).split())


def _final_clean(items: list[dict], workdir: Path, remap: dict[str, str]) -> tuple[list[dict], int]:
    """The whole twin's items, checked together; what still fails is dropped and the references to it become open
    questions, until nothing fails (a few rounds at most)."""
    dropped = 0
    for _round in range(4):
        _resolve_after_merge(items, remap)
        bad = _lint_items(items, workdir, "twin-check")
        bad.pop("", None)
        if not bad:
            break
        keep = [it for it in items if it["id"] not in bad]
        dropped += len(items) - len(keep)
        items = keep
    return items, dropped


def derive_emf(text: str, *, source_name: str, source_stat: dict | None, complete: CompleteFn | None = None,
               lookup: LookupFn | None = None, by: str = "person", now: dt.datetime | None = None,
               rel_path: str | None = None, on_progress: ProgressFn | None = None,
               should_stop: StopFn | None = None, previous: str | None = None) -> tuple[str, dict]:
    """Decompile a text into its EMF twin: `(cosm_text, info)` (plan §7.3 A).

    - `source_name` — the text's file name (the twin's `source.path`, provenance locators); `source_stat` —
      `{sha256, size, mtime_ns}` of the bytes read (`read_source`), or None for a standalone EMF; `rel_path` —
      the text's path in its volume or project, for the catalog id (default: `source_name`).
    - `complete` — `complete(messages) -> (text, meta)`, or None for rules mode. `lookup` — FEED batch lookup,
      `dictionary.lookup_many` by default (all None when FEED is not built: terms are then `{pending}`).
    - `by` — `person`, or the readvisor's name. `on_progress(fields)` and `should_stop()` are the job's hooks:
      the stop is checked between passages and before the atem; a passage being read is finished first.
    - `previous` — the twin being replaced, if any: the passage atems a person pinned into it (its `X:atem`
      items) are carried over with their ids; an `of` that no longer names an item becomes an open question.

    Model mode: per passage one completion with an output budget (claims first, capped per kind) → a reply cut
    off by the budget keeps its complete items and gets ONE continuation after the last of them → every item
    normalized deterministically (kinds, modules, synonyms, stance/salience words, spans, provenance, counted in
    `info["normalized"]`) → checked as a throwaway volume against the emf manifest → ONE repair turn for only the
    items that still fail → those still failing are dropped (`derived.dropped`); passages merge (ids
    `<M>:<kind>/<slug of the name>`, the first of two wins, its span extended and the sources appended);
    references are resolved after the merge (dangling ones become `{pending}`); terms are grounded in FEED and
    laid over the deterministic lexicon (the floor: a model twin never has zero terms); one more completion
    writes the whole text's atem from the passages' atems and its opening and closing.

    Rules mode: the lexicon from `candidate_terms` + FEED and the entities from `entity_candidates`, each with
    the line of its first use as its span, `confidence: 0.3`, `state: pending` and `pending: "a model has not
    read this passage"`; no concepts, claims or events (rules cannot read those); the atem scaffold;
    `derived.mode: rules`. `info` = `{mode, model, chunks, items, dropped, normalized, continued, atem,
    counts}`."""
    lookup = lookup or _default_lookup
    source = source_name
    rel = rel_path or source_name
    parts = chunk(text)
    _progress(on_progress, phase="lexicon", chunk=0, chunks=len(parts), message="finding the words it leans on")
    table = _term_table(text, lookup)
    if complete is None:
        nodes = _rules_nodes(text, table, source)
        atem = atem_block(rules_atem(text))
        mode, model, dropped, stats = "rules", None, 0, {"normalized": 0, "continued": 0}
    else:
        nodes, atem, model, dropped, stats = _model_nodes(
            text, parts, complete=complete, lookup=lookup, table=table, source=source, on_progress=on_progress,
            should_stop=should_stop)
        mode = "model"
    _check(should_stop)
    carried = _carried_pins(previous, nodes)
    if carried:                               # a hand-edited pin that no longer checks is not carried
        with tempfile.TemporaryDirectory(prefix="enough-emf-") as tmp:
            bad = _lint_items(nodes + carried, Path(tmp), "carried-check")
        keep = [it for it in carried if it["id"] not in bad]
        dropped += len(carried) - len(keep)
        nodes = nodes + keep
    derived = _derived(now=now, by=by, model=model, mode=mode, completeness="full", chunks=len(parts),
                       dropped=dropped)
    cat = _catalog(rel_path=rel, source_name=source, source_stat=source_stat, name=text_title(text, source_name),
                   derived=derived, atem=atem, nodes=nodes)
    counts: dict[str, int] = {}
    for it in nodes:
        counts[it["id"][:1]] = counts.get(it["id"][:1], 0) + 1
    info = {"mode": mode, "model": model, "chunks": len(parts), "items": len(nodes), "dropped": dropped,
            "normalized": stats["normalized"], "continued": stats["continued"],
            "atem": macrocosm.jsonable(atem), "counts": counts}
    return _dump(cat), info


# The name before EMF (plan §16), kept one release: it is `derive_emf` now.
derive_eml = derive_emf


def _carried_pins(previous: str | None, nodes: list[dict]) -> list[dict]:
    """The pinned passage atems of the twin a derivation replaces, ready to append: ids kept, `of` references
    re-checked against the new items (one that names nothing now is an open question). An unreadable previous
    twin carries nothing."""
    if not previous:
        return []
    data = _yaml(previous)
    old = data.get("nodes") if isinstance(data, dict) and data.get("oes") == EMF_OES else None
    ids = {it["id"] for it in nodes}
    out = []
    for it in old if isinstance(old, list) else []:
        if not (isinstance(it, dict) and re.match(r"^X:atem/[A-Za-z0-9._@-]+$", str(it.get("id") or ""))):
            continue
        it = _plain(it)
        refs = it.get("of")
        if refs is not None:
            seq = refs if isinstance(refs, list) else [refs]
            it["of"] = [r if (not isinstance(r, str) or r in ids or not _id_shaped(r))
                        else _pending(f"{r} is not an item of this twin") for r in seq]
        out.append(it)
    return out


def _rules_prov(source: str, line: int) -> dict:
    return {"mode": "derived", "sources": [_locator(source, line)], "confidence": RULES_CONFIDENCE,
            "state": "pending"}


def _term_nodes(table: list[dict], source: str, *, pending: str) -> list[dict]:
    """The deterministic lexicon: one FEED-grounded `L:term` per candidate term, its first use as its span, the
    rules provenance (`confidence: 0.3`, `state: pending`) and `pending` saying why."""
    nodes: list[dict] = []
    seen: set[str] = set()
    for r in table:
        iid = f"L:term/{item_slug(r['word'])}"
        if iid in seen:
            continue
        seen.add(iid)
        times = "once" if r["count"] == 1 else f"{r['count']} times"
        it: dict[str, Any] = {
            "id": iid, "type": "term", "name": r["word"],
            "summary": f"The word \"{r['word']}\", used {times} in the text, first on line {r['first_line']}.",
            "feed": _feed_block(r["entry"]),
        }
        if r["entry"] and r["entry"].get("definition"):
            it["sense"] = " ".join(str(r["entry"]["definition"]).split())
        it.update(span=_span(r["first_line"]), provenance=_rules_prov(source, r["first_line"]), pending=pending)
        nodes.append(it)
    return nodes


def _with_floor(items: list[dict], floor: list[dict], remap: dict[str, str]) -> list[dict]:
    """Model mode keeps the deterministic lexicon under the model's terms, so a twin never has zero terms: a model
    term that names a floor word (by FEED headword, else by id) takes the floor term's place and id — the model's
    summary, sense (FEED's when it gave none), span and provenance, the floor's FEED grounding, both sources;
    the model's other terms follow the floor; floor terms the model did not discuss stay as they are."""
    by_id = {f["id"]: f for f in floor}
    extra: list[dict] = []
    for t in (it for it in items if it.get("type") == "term"):
        feed = t.get("feed") if isinstance(t.get("feed"), dict) else {}
        head = feed.get("word") if isinstance(feed.get("word"), str) and feed["word"] else None
        target = by_id.get(f"L:term/{item_slug(head)}") if head else None
        target = target or by_id.get(t["id"])
        if target is None:
            extra.append(t)
            continue
        merged = dict(t, id=target["id"], name=target["name"], feed=target["feed"])
        if not (isinstance(t.get("sense"), str) and t["sense"].strip()):
            merged.pop("sense", None)
            if "sense" in target:
                merged["sense"] = target["sense"]
        _merge_into(merged, target)
        if t["id"] != target["id"]:
            remap[t["id"]] = target["id"]
        by_id[target["id"]] = merged
    return list(by_id.values()) + extra + [it for it in items if it.get("type") != "term"]


def _rules_nodes(text: str, table: list[dict], source: str) -> list[dict]:
    nodes = _term_nodes(table, source, pending=PENDING_NO_MODEL)
    seen = {it["id"] for it in nodes}

    def prov(line: int) -> dict:
        return _rules_prov(source, line)

    for e in _entity_table(text):
        iid = f"E:{e['kind']}/{item_slug(e['name'])}"
        if iid in seen:
            continue
        seen.add(iid)
        times = "once" if e["count"] == 1 else f"{e['count']} times"
        nodes.append({
            "id": iid, "type": e["kind"], "name": e["name"],
            "summary": f"\"{e['name']}\", named {times} in the text, first on line {e['first_line']}.",
            "span": _span(e["first_line"]), "provenance": prov(e["first_line"]), "pending": PENDING_NO_MODEL,
        })
    return nodes


def _model_nodes(text: str, parts: list[Chunk], *, complete: CompleteFn, lookup: LookupFn, table: list[dict],
                 source: str, on_progress: ProgressFn | None,
                 should_stop: StopFn | None) -> tuple[list[dict], dict, str | None, int, dict]:
    meta: dict[str, Any] = {"normalized": 0, "continued": 0}
    merged: dict[str, dict] = {}
    remap: dict[str, str] = {}
    dropped = 0
    with tempfile.TemporaryDirectory(prefix="enough-emf-") as tmp:
        work = Path(tmp)
        for c in parts:
            _check(should_stop)
            _progress(on_progress, phase="reading", chunk=c.id, chunks=len(parts),
                      message=f"reading passage {c.id} of {len(parts)}")
            items, rm, lost = _read_passage(c, complete=complete, source=source, table=table, workdir=work,
                                            stats=meta, on_progress=on_progress, chunks=len(parts))
            dropped += lost
            for k, v in rm.items():
                remap.setdefault(k, v)
            for it in items:
                if it["id"] in merged:
                    _merge_into(merged[it["id"]], it)
                else:
                    merged[it["id"]] = it
        _progress(on_progress, phase="merging", chunk=len(parts), chunks=len(parts), message="merging the passages")
        items = list(merged.values())
        # The passages' atems feed the whole text's atem and are not written as items: every X:atem in a twin
        # is one a person pinned, and a re-derive carries those over (`previous`).
        passage_atems = [it for it in items if it.get("type") == "atem"]
        items = [it for it in items if it.get("type") != "atem"]
        _ground_terms(items, lookup)
        items = _with_floor(items, _term_nodes(table, source, pending=PENDING_FLOOR), remap)
        items, lost = _final_clean(_order(items), work, remap)
        dropped += lost
    _check(should_stop)
    _progress(on_progress, phase="atem", chunk=len(parts), chunks=len(parts), message="writing the atem")
    atem_lines = []
    for a in passage_atems:
        line = a.get("line")
        if isinstance(line, str) and line.strip():
            atem_lines.append(f"- lines {(a.get('span') or {}).get('lines', '?')}: {' '.join(line.split())}")
    user = P.ATEM_WHOLE_USER.format(name=source, atems="\n".join(atem_lines) or "- (none)", body=_edges(text))
    reply, m2 = _call(complete, [{"role": "system", "content": P.ATEM_SYSTEM}, {"role": "user", "content": user}])
    atem = atem_block(_read_atem(reply))
    return (items, atem, meta.get("model") or m2.get("model"), dropped,
            {"normalized": meta["normalized"], "continued": meta["continued"]})


# ---------------------------------------------------------------------------
# Atems in the twin: pinning a passage's, setting the file's
# ---------------------------------------------------------------------------

def _load_twin(twin_text: str) -> dict:
    data = _yaml(twin_text)
    if not isinstance(data, dict) or data.get("oes") != EMF_OES:
        raise DeriveError("the EMF twin could not be read; fix it or derive it again")
    nodes = data.get("nodes")
    if nodes is None:
        data["nodes"] = []
    elif not isinstance(nodes, list):
        raise DeriveError("the EMF twin's nodes: is not a list; fix it or derive it again")
    return _plain(data)


def next_atem_id(twin_text: str | None) -> str:
    """The id the next pinned passage atem takes: `X:atem/<n>`, one past the highest number in the twin."""
    n = 0
    if twin_text:
        data = _yaml(twin_text)
        for it in (data.get("nodes") if isinstance(data, dict) else None) or []:
            m = re.match(r"^X:atem/(\d+)$", str(it.get("id") if isinstance(it, dict) else ""))
            if m:
                n = max(n, int(m.group(1)))
    return f"X:atem/{n + 1}"


def pin_atem(twin_text_or_none: str | None, atem: dict, span: dict | None, *, source_name: str,
             source_stat: dict | None, now: dt.datetime | None = None, of: list | None = None,
             rel_path: str | None = None, by: str = "person", model: str | None = None,
             name: str | None = None, title: str | None = None) -> str:
    """Append a passage's atem to the twin as `X:atem/<n>` (with its `span` and the `of` items it centres on) and
    return the twin's new text. No twin yet → a minimal one, `completeness: atem`, holding just this item. An
    atem whose push or pull is still an open question is a scaffold: `confidence: 0.3`, `state: pending`.
    An existing twin's `source:` is left alone (pinning does not make a stale twin fresh)."""
    block = atem_block(atem)
    scaffold = _atem_is_scaffold(block)
    sp = clean_span(span) or {}
    ab = parse_lines(sp.get("lines"))
    iid = next_atem_id(twin_text_or_none)
    where = f"lines {ab[0]}-{ab[1]}" if ab and ab[0] != ab[1] else (f"line {ab[0]}" if ab else "a passage")
    label = (name or "").strip()
    if not label:
        label = where if ab else (_cut_words(block["line"], 6) if isinstance(block["line"], str) else where)
    item: dict[str, Any] = {
        "id": iid, "type": "atem", "name": label,
        "summary": f"The atem of the passage at {where}." if ab else "The atem of a passage of the text.",
        **block,
    }
    refs = [r for r in (of or []) if isinstance(r, str) and r.strip()]
    if refs:
        item["of"] = refs
    if sp:
        item["span"] = sp
    item["provenance"] = {"mode": "derived",
                          "sources": [_locator(source_name, *ab) if ab else source_name],
                          "confidence": RULES_CONFIDENCE if scaffold else 0.8,
                          "state": "pending" if scaffold else "known"}
    if scaffold:
        item["pending"] = PENDING_NO_MODEL
    if twin_text_or_none:
        data = _load_twin(twin_text_or_none)
        ids = {str(it.get("id")) for it in data["nodes"] if isinstance(it, dict)}
        if refs:
            item["of"] = [r if r in ids else _pending(f"{r} is not an item of this twin") for r in refs]
        data["nodes"].append(item)
        return _dump(data)
    if refs:
        item["of"] = [_pending(f"{r} is not an item of this twin") for r in refs]
    derived = _derived(now=now, by=by, model=model, mode="rules" if scaffold else "model", completeness="atem",
                       chunks=1)
    return _dump(_catalog(rel_path=rel_path or source_name, source_name=source_name,
                                   source_stat=source_stat, name=title or source_name, derived=derived, atem=None,
                                   nodes=[item]))


def set_file_atem(twin_text_or_none: str | None, atem: dict, *, source_name: str, source_stat: dict | None,
                  now: dt.datetime | None = None, rel_path: str | None = None, by: str = "person",
                  model: str | None = None, title: str | None = None) -> str:
    """Set the twin's `atem:` block (the file's atem) and return the twin's new text, keeping its nodes. No twin →
    a minimal one (`completeness: atem`, `nodes: []`). A minimal twin is remade around the new atem (its
    `source:` and `derived:` describe the atem, so they are refreshed); a full twin keeps its `source:` and
    `derived:` — only its atem changes."""
    block = atem_block(atem)
    mode = "rules" if _atem_is_scaffold(block) else "model"
    if twin_text_or_none:
        data = _load_twin(twin_text_or_none)
        derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
        if derived.get("completeness") == "atem":
            fresh = _catalog(rel_path=rel_path or source_name, source_name=source_name, source_stat=source_stat,
                             name=str(data.get("name") or title or source_name),
                             derived=_derived(now=now, by=by, model=model, mode=mode, completeness="atem",
                                              chunks=1),
                             atem=block, nodes=data["nodes"])
            for k, v in data.items():          # keep keys this module does not write
                fresh.setdefault(k, v)
            fresh["nodes"] = fresh.pop("nodes")
            return _dump(fresh)
        out = {k: v for k, v in data.items() if k != "nodes"}
        out["atem"] = block                    # in place when there was one; before nodes when there wasn't
        out["nodes"] = data["nodes"]
        return _dump(out)
    derived = _derived(now=now, by=by, model=model, mode=mode, completeness="atem", chunks=1)
    return _dump(_catalog(rel_path=rel_path or source_name, source_name=source_name, source_stat=source_stat,
                                   name=title or source_name, derived=derived, atem=block, nodes=[]))


# ---------------------------------------------------------------------------
# Compile: an EMF twin → markdown
# ---------------------------------------------------------------------------

STANCE_PHRASE = {
    "axiom": "It is taken as given that",
    "observed": "The author observed that",
    "deduced": "It follows that",
    "opinion": "The author holds that",
    "assumed": "It is assumed that",
    "hearsay": "Reportedly,",
}
STANCE_TAG = {"axiom": "taken as given", "observed": "observed", "deduced": "reasoned", "opinion": "an opinion",
              "assumed": "assumed", "hearsay": "reported"}


def _as_doc(volume_or_text: Any) -> tuple[dict, list[dict]]:
    if isinstance(volume_or_text, macrocosm.Volume):
        if volume_or_text.refused is not None:
            raise DeriveError(str(volume_or_text.refused))
        return dict(volume_or_text.catalog), [dict(it.data) for it in volume_or_text.items.values()]
    if isinstance(volume_or_text, dict):
        data = volume_or_text
    else:
        data = _yaml(str(volume_or_text))
    if not isinstance(data, dict) or data.get("oes") != EMF_OES:
        raise DeriveError("not an EMF (oes: emf/1)")
    nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    return data, [n for n in nodes if isinstance(n, dict)]


def _first_line(span: Any) -> int:
    ab = parse_lines(span.get("lines")) if isinstance(span, dict) else None
    return ab[0] if ab else 10 ** 9


def _sentence(s: str) -> str:
    s = " ".join(str(s).split())
    return s if not s or s[-1] in ".!?…" else s + "."


def _lead_lower(s: str, names: set[str]) -> str:
    """Lowercase a summary's first letter after a stance phrase, unless it starts a name ("Mara Okafor …")."""
    first = s.split(" ", 1)[0].strip(",;:")
    if not first or not first[0].isupper() or first.isupper() and len(first) > 1:
        return s
    if any(n.split(" ", 1)[0] == first for n in names):
        return s
    return s[0].lower() + s[1:]


ORDERS = ("told", "weight")
# The order in words, as a short's footer and the compile prompt say it.
ORDER_SAID = {"told": "told as the author told it", "weight": "told by weight"}
ALSO_HEADING = "Also in the fabula"
ENTITY_KINDS = ("person", "org", "place", "work", "thing")
# Within one line of the text: the words, the names, the ideas, then what is claimed and what happens.
_TOLD_RANK = {"term": 0, **{k: 1 for k in ENTITY_KINDS}, "concept": 2, "claim": 3, "event": 4}
# Items no span places, at the end: claims and events first.
_ALSO_RANK = {"claim": 0, "event": 1, "concept": 2, **{k: 3 for k in ENTITY_KINDS}, "term": 4}


def _source_of(cat: dict) -> str | None:
    """The text a twin is of: its `source.path` (a file name beside the twin), or None for a standalone EMF."""
    src = cat.get("source")
    p = src.get("path") if isinstance(src, dict) else None
    return p.strip() if isinstance(p, str) and p.strip() else None


def source_path(emf_path: Path | str, volume_or_text: Any = None) -> Path | None:
    """The text an EMF twin names in its `source:`, beside the twin, when it is there as a file; None for a
    standalone EMF or a text that has gone. `volume_or_text` defaults to the EMF file itself."""
    emf = Path(emf_path)
    try:
        cat, _items = _as_doc(volume_or_text if volume_or_text is not None
                              else emf.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, DeriveError):
        return None
    name = _source_of(cat)
    if not name:
        return None
    text = emf.parent / Path(name.replace("\\", "/")).name
    return text if text.is_file() else None


def default_order(volume_or_text: Any, *, source_readable: bool = True) -> str:
    """The order a compile tells in when nobody chose (owner decision 4): `told`, the author's own order, when
    the EMF has a `source` and its text can be read; `weight` for a standalone EMF (no telling to follow)."""
    cat, _items = _as_doc(volume_or_text)
    return "told" if _source_of(cat) and source_readable else "weight"


def _check_order(order: Any) -> str | None:
    if order is None or order == "":
        return None
    if order not in ORDERS:
        raise DeriveError(f"order must be one of {', '.join(ORDERS)}")
    return str(order)


def outline(volume_or_text: Any, *, order: str = "weight", source_text: str | None = None) -> tuple[str, list[str]]:
    """`(title, markdown lines)`: the rules-mode short, and the outline a model rewrites (plan §7.3 B, §15). The
    atem line leads in both orders. `weight`: the claims in salience order grouped by the concept they mostly
    reference, each claim's stance said in words; the events in before/after order; a closing terms list.
    `told`: every item with a span, in the author's order (`_told_lines`)."""
    cat, items = _as_doc(volume_or_text)
    order = _check_order(order) or "weight"
    by_id = {str(it.get("id")): it for it in items}
    names = {str(it.get("name")) for it in items if it.get("type") in ENTITY_KINDS
             and isinstance(it.get("name"), str)}
    title = str(cat.get("name") or "untitled")
    out = [f"# {title}", ""]
    atem = cat.get("atem") if isinstance(cat.get("atem"), dict) else {}
    if isinstance(atem.get("line"), str) and atem["line"].strip():
        out += [_sentence(atem["line"]), ""]
    if order == "told":
        return title, out + _told_lines(items, by_id, names, title=title, source_text=source_text)
    order = {it_id: i for i, it_id in enumerate(by_id)}
    sal = {s: i for i, s in enumerate(SALIENCE)}
    claims = [it for it in items if it.get("type") == "claim" and isinstance(it.get("summary"), str)]

    def concept_of(c: dict) -> str | None:
        vals: list[Any] = []
        roles = c.get("roles")
        if isinstance(roles, dict):
            vals += list(roles.values())
        for link in c.get("links") or []:
            vals.append(link.get("to") if isinstance(link, dict) else link)
        counts: dict[str, int] = {}
        for v in vals:
            if isinstance(v, str) and v.startswith("K:") and v in by_id:
                counts[v] = counts.get(v, 0) + 1
        if not counts:
            return None
        return sorted(counts, key=lambda k: (-counts[k], order.get(k, 0)))[0]

    def claim_key(c: dict) -> tuple:
        return (sal.get(str(c.get("salience") or "normal"), 2), _first_line(c.get("span")), order[str(c["id"])])

    groups: dict[str | None, list[dict]] = {}
    for c in sorted(claims, key=claim_key):
        groups.setdefault(concept_of(c), []).append(c)
    if claims:
        out += ["## What it claims", ""]
        group_order = sorted(groups, key=lambda g: (g is None, claim_key(groups[g][0])))
        for g in group_order:
            if len(groups) > 1 or g is not None:
                label = str(by_id[g].get("name")) if g else "Other claims"
                out += [f"### {label}", ""]
            for c in groups[g]:
                out.append(f"- {_claim_sentence(c, by_id, names)}")
            out.append("")
    events = [it for it in items if it.get("type") == "event" and isinstance(it.get("summary"), str)]
    if events:
        out += ["## What happens", ""]
        for i, ev in enumerate(_event_order(events), 1):
            out.append(f"{i}. {_event_said(ev)}")
        out.append("")
    terms = [it for it in items if it.get("type") == "term"]
    if terms:
        out += ["## Terms", ""]
        for t in terms:
            sense = t.get("sense") if isinstance(t.get("sense"), str) else t.get("summary")
            feed = t.get("feed")
            note = " (not in FEED)" if macrocosm.is_pending(feed) else ""
            out.append(f"- **{t.get('name')}**{note}: {_sentence(sense) if isinstance(sense, str) else ''}".rstrip())
        out.append("")
    return title, out


def _claim_sentence(c: dict, by_id: dict, names: set[str]) -> str:
    s = _sentence(c["summary"])
    stance = c.get("stance") if c.get("stance") in STANCES else None
    if stance is None:
        return s
    roles = c.get("roles") if isinstance(c.get("roles"), dict) else {}
    teller = None
    for slot in ("holder", "source"):
        ref = roles.get(slot)
        if isinstance(ref, str) and ref in by_id:
            teller = str(by_id[ref].get("name") or "")
    if teller and teller.lower() in s.lower():
        return f"{s[:-1]} ({STANCE_TAG[stance]})."
    return f"{STANCE_PHRASE[stance]} {_lead_lower(s, names)}"


def _event_said(ev: dict) -> str:
    """An event's summary as a sentence, with its `when` in brackets unless the summary already says it."""
    said = " ".join(str(ev.get("summary") or "").split()).rstrip(".")
    when = ev.get("when")
    when = " ".join(when.split()) if isinstance(when, str) else ""
    tail = f" ({when})" if when and when.lower() not in said.lower() else ""
    return f"{said}{tail}."


def _event_order(events: list[dict]) -> list[dict]:
    """Events in before/after order (a stable topological sort), else by where the text tells them."""
    ids = [str(e.get("id")) for e in events]
    idx = {i: n for n, i in enumerate(ids)}
    after: dict[str, set[str]] = {i: set() for i in ids}      # i comes after each of these
    for e in events:
        i = str(e.get("id"))
        for v in (e.get("after") if isinstance(e.get("after"), list) else [e.get("after")]):
            if isinstance(v, str) and v in idx:
                after[i].add(v)
        for v in (e.get("before") if isinstance(e.get("before"), list) else [e.get("before")]):
            if isinstance(v, str) and v in idx:
                after[v].add(i)
    by = {str(e.get("id")): e for e in events}
    done: list[str] = []
    left = sorted(ids, key=lambda i: (_first_line(by[i].get("span")), idx[i]))
    while left:
        ready = [i for i in left if after[i] <= set(done)]
        nxt = ready[0] if ready else left[0]                 # a cycle: tell it as the text does
        done.append(nxt)
        left.remove(nxt)
    return [by[i] for i in done]


# ---------------------------------------------------------------------------
# SHORT: a telling compiled from the fabula (plan §15)
# ---------------------------------------------------------------------------
#
# An EMF twin is the fabula: the order-free material of a text, every item with a `span` saying where in the
# telling it was found. A SHORT (syuzhetic-hermeneutic open readable text) is a telling enough compiles from it:
# an arrangement that says how each thing is known as it tells it, in plain markdown, yours to edit, honest about
# its gaps and open to the reader's own reading. Two orders: `told` (the author's, by span) and `weight` (salience,
# grouped by concept, then events, then terms). The atem leads both and belongs to neither.

@dataclass(frozen=True)
class _Heading:
    line: int | None     # where the text has it (None: a heading an item's span names)
    level: int           # the short's own level, 2 and down
    title: str


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _source_headings(source_text: str | None, title: str) -> list[_Heading]:
    """The text's headings, outside fenced code, as the short's section headings: the first one is the short's
    own `# title` when it is a level-1 heading or says the twin's name (a twin is named from it), so it is left
    out; the rest keep their relative depth, the shallowest becoming `##`."""
    if not source_text:
        return []
    norm = _norm(source_text)
    lines = norm.split("\n")
    heading_lines, _code = _line_kinds(norm)
    found: list[tuple[int, int, str]] = []
    for n in sorted(heading_lines):
        raw = lines[n - 1].strip()
        level = len(raw) - len(raw.lstrip("#"))
        said = _strip_inline(raw.lstrip("#").strip().rstrip("#").strip())
        if said:
            found.append((n, level, said))
    if found and (found[0][1] == 1 or found[0][2] == title):
        found = found[1:]
    if not found:
        return []
    top = min(level for _n, level, _s in found)
    return [_Heading(n, min(6, level - top + 2), said) for n, level, said in found]


def _folded_lines(source_text: str) -> tuple[str, list[int]]:
    """The text with its whitespace folded to single spaces, and where each line starts in it."""
    starts: list[int] = []
    parts: list[str] = []
    pos = 0
    for line in _norm(source_text).split("\n"):
        words = " ".join(line.split())
        starts.append(pos)
        if words:
            parts.append(words)
            pos += len(words) + 1
    return " ".join(parts), starts


def _span_place(span: Any, folded: tuple[str, list[int]] | None) -> tuple[int, int] | None:
    """Where an item sits in the telling, as `(first line, last line)`: its span's `lines`, else (with the text at
    hand) the lines its `start` and `end` quotes are found on. None: the span does not place it."""
    if not isinstance(span, dict):
        return None
    ab = parse_lines(span.get("lines"))
    if ab:
        return ab
    start = span.get("start")
    if folded is None or not isinstance(start, str) or not start.strip():
        return None
    text, starts = folded
    at = text.find(" ".join(start.split()))
    if at < 0:
        return None
    a = bisect.bisect_right(starts, at)
    b = a
    end = span.get("end")
    if isinstance(end, str) and end.strip():
        to = text.find(" ".join(end.split()), at)
        if to >= 0:
            b = bisect.bisect_right(starts, to)
    return a, max(a, b)


def _told_item(it: dict, by_id: dict, names: set[str]) -> str | None:
    """One item of the fabula, said as a line of the telling; None when it has nothing to say."""
    kind = it.get("type")
    summary = it.get("summary") if isinstance(it.get("summary"), str) and it["summary"].strip() else None
    name = str(it.get("name") or "").strip()
    if kind == "claim":
        return _claim_sentence(it, by_id, names) if summary else None
    if kind == "event":
        return _event_said(it) if summary else None
    if kind == "term":
        sense = it.get("sense") if isinstance(it.get("sense"), str) and it["sense"].strip() else summary
        note = " (not in FEED)" if macrocosm.is_pending(it.get("feed")) else ""
        return f"**{name}**{note}: {_sentence(sense)}".rstrip() if sense else (f"**{name}**{note}" if name else None)
    if kind == "concept":
        return f"**{name}**: {_sentence(summary)}" if summary else (f"**{name}**" if name else None)
    if kind in ENTITY_KINDS:
        return _sentence(summary) if summary else (name or None)
    return None


def _told_lines(items: list[dict], by_id: dict, names: set[str], *, title: str,
                source_text: str | None) -> list[str]:
    """The `told` order: every item a span places, in the order the author told them (first line, last line,
    then words, names, ideas, claims, events, then the twin's own order), grouped under the text's headings — the
    one an item's span names (`span.heading`, when a twin records it), else the heading it falls under in the text,
    when the text is at hand, else none; then the items no span places, under "Also in the fabula". The atem is
    not among them: it is the breath of the whole, outside the telling. Pinned passage atems (X) likewise."""
    folded = _folded_lines(source_text) if source_text else None
    heads = _source_headings(source_text, title)
    chains: list[list[_Heading]] = []
    for i, h in enumerate(heads):
        chain = [h]
        level = h.level
        for j in range(i - 1, -1, -1):
            if heads[j].level < level:
                chain.append(heads[j])
                level = heads[j].level
        chains.append(list(reversed(chain)))
    starts = [h.line or 0 for h in heads]
    placed: list[tuple[tuple, dict]] = []
    also: list[tuple[tuple, dict]] = []
    for pos, it in enumerate(items):
        kind = it.get("type")
        if kind not in _TOLD_RANK:
            continue
        where = _span_place(it.get("span"), folded)
        if where is None:
            also.append(((_ALSO_RANK[kind], pos), it))
        else:
            placed.append(((where[0], where[1], _TOLD_RANK[kind], pos), it))
    out: list[str] = []
    current: list[_Heading] = []
    open_list = False
    for key, it in sorted(placed, key=lambda p: p[0]):
        said = _told_item(it, by_id, names)
        if said is None:
            continue
        span = it.get("span") if isinstance(it.get("span"), dict) else {}
        named = span.get("heading")
        if isinstance(named, str) and named.strip():
            chain = [_Heading(None, 2, " ".join(named.split()))]
        else:
            i = bisect.bisect_right(starts, key[0]) - 1
            chain = chains[i] if i >= 0 else []
        k = 0
        while k < min(len(chain), len(current)) and chain[k] == current[k]:
            k += 1
        if chain[k:] or len(chain) < len(current):
            for h in chain[k:]:
                if open_list:
                    out.append("")
                    open_list = False
                out += [f"{'#' * h.level} {h.title}", ""]
            current = chain
        out.append(f"- {said}")
        open_list = True
    tail = [s for _k, it in sorted(also, key=lambda p: p[0]) if (s := _told_item(it, by_id, names))]
    if open_list:
        out.append("")
    if tail:
        out += [f"## {ALSO_HEADING}", ""] + [f"- {s}" for s in tail] + [""]
    return out


def short_footer(*, text_name: str, standalone: bool, order: str, day: str, model: str | None,
                 mode: str) -> str:
    """The one italic line every short ends with (owner decision 6): what it is a short of, in which order, when,
    and by which model or by rules."""
    who = f"by {model or 'a model'}" if mode == "model" else "by rules, without a model"
    said = ORDER_SAID[order]
    if standalone:
        return f"*a short of {text_name}, a standalone EMF, {said}, compiled on {day} {who}*"
    return f"*a short of {text_name}, {said}, compiled from its EMF twin on {day} {who}*"


def _local_day(now: dt.datetime | None) -> str:
    when = now or dt.datetime.now()
    if when.tzinfo is not None:
        when = when.astimezone()
    return when.strftime("%Y-%m-%d")


def compile_short(volume_or_text: Any, *, complete: CompleteFn | None = None, source_name: str | None = None,
                  order: str | None = None, source_text: str | None = None,
                  now: dt.datetime | None = None) -> tuple[str, dict]:
    """An EMF back into a SHORT: gfm markdown in the chosen order (`told` | `weight`; None → `default_order`, the
    text counted readable when `source_text` is given or the twin names no source), ending with the footer line.
    Rules mode: the outline verbatim, each claim's stance said in words. Model mode: one completion that writes
    the outline as prose, told the order. `source_text` (the twin's text) lets `told` group under its headings and
    place spans given as quotes. `source_name` is the EMF's file name (a standalone's footer names it). Returns
    `(markdown, {order, mode, model, by})`, `by` being the model's id or `rules`. Never writes a file."""
    cat, items = _as_doc(volume_or_text)
    doc = {**cat, "nodes": items}
    chosen = _check_order(order) or default_order(doc, source_readable=source_text is not None)
    title, lines = outline(doc, order=chosen, source_text=source_text)
    text_name = _source_of(cat)
    standalone = text_name is None
    if standalone:
        text_name = Path(source_name).name if source_name else str(cat.get("name") or "an EMF")
    else:
        text_name = Path(text_name.replace("\\", "/")).name
    day = _local_day(now)
    if complete is None:
        foot = short_footer(text_name=text_name, standalone=standalone, order=chosen, day=day, model=None,
                            mode="rules")
        body = "\n".join(lines).rstrip()
        return (body + "\n\n---\n\n" + foot + "\n",
                {"order": chosen, "mode": "rules", "model": None, "by": "rules"})
    system = P.COMPILE_SYSTEM.format(order=P.COMPILE_ORDER[chosen])
    user = P.COMPILE_USER.format(name=title, said=ORDER_SAID[chosen], outline="\n".join(lines))
    reply, meta = _call(complete, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    body = reply.strip()
    m = re.match(r"^```(?:markdown|md|gfm)?\s*\n(.*?)\n```\s*$", body, re.S)
    if m:
        body = m.group(1).strip()
    if not body:
        raise DeriveError("the model returned nothing to write")
    model = meta.get("model") if isinstance(meta, dict) and meta.get("model") else None
    foot = short_footer(text_name=text_name, standalone=standalone, order=chosen, day=day, model=model,
                        mode="model")
    return (body + "\n\n---\n\n" + foot + "\n",
            {"order": chosen, "mode": "model", "model": model, "by": model or "a model"})


def compile_text(volume_or_text: Any, *, complete: CompleteFn | None = None, source_name: str | None = None,
                 order: str | None = None, source_text: str | None = None,
                 now: dt.datetime | None = None) -> str:
    """An EMF twin back into a SHORT, the markdown only (`compile_short` without its info)."""
    return compile_short(volume_or_text, complete=complete, source_name=source_name, order=order,
                         source_text=source_text, now=now)[0]


# ---------------------------------------------------------------------------
# The fabula records its tellings: the twin's `shorts:` list
# ---------------------------------------------------------------------------

_PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.@/+-]*$")
_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:(.*)$")
SHORT_FIELDS = ("path", "at", "by", "mode", "order")


def _flow_scalar(v: Any) -> str:
    """A value as a flow mapping writes it: a timestamp in UTC, a safe word plain, anything else double-quoted."""
    if isinstance(v, dt.datetime):
        return _now(v).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    s = str(v)
    if _PLAIN_SCALAR.match(s):
        try:
            if macrocosm.yaml_load(f"k: {s}\n") == {"k": s}:
                return s
        except Exception:  # noqa: BLE001 — quote it instead
            pass
    return json.dumps(s, ensure_ascii=False)


def _flow_entry(entry: dict) -> str:
    return "{" + ", ".join(f"{k}: {_flow_scalar(v)}" for k, v in entry.items()) + "}"


def record_short(twin_text: str, *, path: str, at: dt.datetime | None = None, by: str, mode: str,
                 order: str) -> str:
    """Append one telling to the EMF's `shorts:` list — `{path, at, by, mode, order}`: the short's file name
    beside the twin, when (UTC), the model's id or `rules`, `model` | `rules`, `told` | `weight` — and return the
    EMF's new text. The list is made just above `nodes:` when there is none. Everything else stays byte for byte:
    the change is made in the text, never by loading and dumping the twin (its comments, quoting and order are
    the author's). Raises DeriveError when the result would not read back as the same EMF with one more short."""
    if mode not in ("model", "rules"):
        raise DeriveError("mode must be model or rules")
    _check_order(order)
    if not isinstance(path, str) or not path.strip():
        raise DeriveError("a short needs its path")
    before = _yaml(twin_text)
    if not isinstance(before, dict) or before.get("oes") != EMF_OES:
        raise DeriveError("not an EMF (oes: emf/1)")
    old = before.get("shorts")
    if old is not None and not isinstance(old, list):
        raise DeriveError("the EMF's shorts: is not a list; fix it by hand")
    entry = {"path": path.strip(), "at": _now(at), "by": str(by or mode), "mode": mode, "order": order}
    nl = "\r\n" if "\r\n" in twin_text else "\n"
    lines = twin_text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    tops = [(i, m) for i, line in enumerate(lines) if (m := _TOP_KEY.match(line.lstrip("﻿")))]
    at_shorts = next(((i, m) for i, m in tops if m.group(1) == "shorts"), None)
    if at_shorts is not None:
        i, m = at_shorts
        j = i + 1
        while j < len(lines) and (lines[j][:1] in (" ", "\t", "-") or not lines[j].strip()):
            j += 1
        k = j
        while k > i + 1 and not lines[k - 1].strip():
            k -= 1
        value = m.group(2).split(" #", 1)[0].strip()
        items = [ln for ln in lines[i + 1:k] if ln.strip() and not ln.lstrip().startswith("#")]
        dashes = [ln for ln in items if ln.lstrip().startswith("- ")]
        if not value and items and len(dashes) == len(items):
            lead = dashes[0][: len(dashes[0]) - len(dashes[0].lstrip())]
            lines[k:k] = [f"{lead}- {_flow_entry(entry)}{nl}"]
        else:                                  # `shorts: []`, a flow list, nested blocks: written out again
            entries = [e for e in (old or []) if isinstance(e, dict)] + [entry]
            lines[i:k] = [f"shorts:{nl}"] + [f"  - {_flow_entry(e)}{nl}" for e in entries]
    else:
        at_nodes = next((i for i, m in tops if m.group(1) == "nodes"), None)
        if at_nodes is None:
            at_nodes = len(lines)
        else:
            while at_nodes > 0 and lines[at_nodes - 1].lstrip().startswith("#"):
                at_nodes -= 1                  # a comment just above nodes: belongs to the nodes
        lines[at_nodes:at_nodes] = [f"shorts:{nl}", f"  - {_flow_entry(entry)}{nl}"]
    out = "".join(lines)
    after = _yaml(out)
    got = after.get("shorts") if isinstance(after, dict) else None
    if (not isinstance(got, list) or len(got) != len(old or []) + 1 or not isinstance(got[-1], dict)
            or got[-1].get("path") != entry["path"]
            or {k: v for k, v in after.items() if k != "shorts"} != {k: v for k, v in before.items() if k != "shorts"}):
        raise DeriveError("the short could not be recorded in the EMF without changing it; it was left as it was")
    return out


__all__ = [
    "ALSO_HEADING", "Chunk", "DeriveCancelled", "DeriveError", "ORDERS", "ORDER_SAID", "SHORT_FIELDS", "atem_block",
    "candidate_terms", "catalog_id", "chunk", "clean_span", "compile_short", "compile_text", "compiled_path",
    "default_order", "derive_atem", "derive_emf", "entity_candidates", "item_slug", "next_atem_id", "outline",
    "parse_lines", "passage_span", "pin_atem", "read_source", "record_short", "rules_atem", "sentences",
    "set_file_atem", "short_footer", "short_path", "source_path", "text_title", "twin_path", "twin_state",
    "write_atomic", "write_twin",
]
