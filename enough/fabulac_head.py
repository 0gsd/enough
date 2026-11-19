"""The head fabulac and its parts, and which parts moved (0.8: pins section 4; MacroCOSM OES 18.4.1 `head` and
`parts`, 18.4.7 "A head fabulac and its parts", 18.4.8 `parts-resolve` and `interfaces-agree`; Thym 20.11).

A program too large for one fabulac is told in parts, each a fabulac of its own, under a **head** that names them:

- the head's catalog lists them in `parts`, each `{uri, path, sha256}` (the part's URI, `oes:fabula/tally-core`; its
  file's path relative to the head; the sha256 of that file when the head last checked it);
- the head holds one `C:component` per part whose `told-in` is the part's URI, and states once, as its own
  `C:interface` items, every interface between two parts;
- each part names its head in its catalog's `head`, and each of its `C:interface` items that keeps or calls an
  interface between parts says `stated-in`, the URI of the head's item (`oes:fabula/tally/C/interface/count-lines`).
- An interface between two programs is the same rule across two heads: stated once in the head of the program that
  offers it, and cited with `stated-in` by the other program's head.

These URIs are text fields, not references: the reader's reference fields stay within one volume and nothing here adds
a reference form. They are resolved by `Fabulacs`, a small resolver over the fabulacs one reader knows, by database
name (the catalog id without `fabula/`): the folder of the fabulac being checked and the folders above it, each read at
its top level, and every path a head's `parts` names. `problems(volume)` runs the two checks for `enough/fabula.py`:

- `parts-resolve` (error): in a head, every part is a fabulac the reader knows at its `path`, whose catalog names this
  head in `head`, with one `C:component` told in it, and every `told-in` names one of the parts; in a part, its `head`
  is a fabulac the reader knows, and every `stated-in` names an interface of its head that exists; in a head, a
  `stated-in` names an interface of another head that exists.
- `interfaces-agree` (error): every `C:interface` that says `stated-in` has the same name, surface, signature and
  parameters as the item it names; a part whose file's sha256 differs from the head's `parts` entry is reported as
  moved, with a note.

**Which parts moved.** `which_moved(recorded, now)` is the one comparison keeping in step makes: names to the digest
recorded and to the digest now, sorted into in step, moved, gone, new and unread. `enough/fabulac_entail.py` uses it
for an entailment's files (their bytes and their briefs); `parts_moved(head)` uses it for a head's parts, each part's
source tree now (`macrocosm.tree_digest`) against the `source.tree` its fabulac recorded, and each part's file against
the head's `parts` entry: the rule `enough-fabulac` and `comprise-fabulac` run at a release.

`make_head(head, parts)` writes a head from a set of part fabulacs: its catalog with `parts`, one `C:component` per
part, the interfaces given, and `head` set in each part's catalog.

Standalone like the reader: the standard library, PyYAML (through the reader) and `enough.macrocosm`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import macrocosm as mc

CHECKS = ("parts-resolve", "interfaces-agree")
SEVERITY = {"parts-resolve": "error", "interfaces-agree": "error"}
FABULAC_SUFFIX = ".fabulac.cosm"
#: How far above a fabulac's own folder the resolver looks for the fabulacs it may name (a part's head).
LEVELS_UP = 3
#: The fields of an interface that must agree between a part (or a citing head) and the item it is stated in.
AGREE = ("name", "surface", "signature", "takes")
_URI = re.compile(r"^oes:(?:fabula|emf)/([^/#\s]+)(?:/(\S+))?$")
_TOP_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$")


# ---------------------------------------------------------------------------
# URIs and the resolver
# ---------------------------------------------------------------------------

def split_uri(uri: Any) -> tuple[str, str] | None:
    """`oes:fabula/<database>[/<path>]` (or the old spelling `oes:emf/…`) -> (database, path or ''); None when it is
    not a fabula's URI."""
    m = _URI.match(uri.strip()) if isinstance(uri, str) else None
    return (m.group(1), m.group(2) or "") if m else None


def volume_uri(database: str) -> str:
    return f"oes:fabula/{database}"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _where(vol: mc.Volume) -> Path | None:
    if not vol.catalog_file:
        return None
    return (Path(vol.root) / vol.catalog_file) if vol.root is not None else Path(vol.catalog_file)


class Fabulacs:
    """The fabulacs one reader knows, by database name. Seeded with folders (each read at its top level for
    `*.fabulac.cosm`) and with files; a head's `parts` paths join as they are named. Each file is loaded once."""

    def __init__(self, folders: Iterable[Path] = (), files: Iterable[Path] = ()) -> None:
        self._folders: list[Path] = []
        self._files: list[Path] = []
        self._vol: dict[Path, mc.Volume | None] = {}
        self._db: dict[str, list[Path]] | None = None
        for f in folders:
            self.add_folder(Path(f))
        for f in files:
            self.add_file(Path(f))

    @classmethod
    def near(cls, fab: Path, *, levels: int = LEVELS_UP, also: Iterable[Path] = ()) -> "Fabulacs":
        """The resolver a check of `fab` uses: its own folder and up to `levels` folders above it, and `also`."""
        fab = Path(fab).absolute()
        folders = [fab.parent] + list(fab.parent.parents)[:levels]
        return cls(folders, [fab, *also])

    def add_folder(self, folder: Path) -> None:
        folder = Path(folder).absolute()
        if folder not in self._folders:
            self._folders.append(folder)
            self._db = None

    def add_file(self, path: Path) -> None:
        path = Path(path).absolute()
        if path not in self._files:
            self._files.append(path)
            self._db = None

    def load(self, path: Path) -> mc.Volume | None:
        """The fabulac at `path`, loaded (None when it is not there or is not a fabulac)."""
        path = Path(path).absolute()
        if path not in self._vol:
            vol = None
            if path.is_file() and not path.is_symlink():
                try:
                    v = mc.load_volume(path)
                    vol = v if v.manifest is not None and v.minicosm == "fabula" else None
                except Exception:  # noqa: BLE001 - a file that does not load is simply not known
                    vol = None
            self._vol[path] = vol
        return self._vol[path]

    def _index(self) -> dict[str, list[Path]]:
        if self._db is None:
            seen: list[Path] = []
            for folder in self._folders:
                try:
                    seen += sorted(p.absolute() for p in folder.glob(f"*{FABULAC_SUFFIX}") if p.is_file())
                except OSError:
                    continue
            seen += self._files
            db: dict[str, list[Path]] = {}
            for p in dict.fromkeys(seen):
                v = self.load(p)
                if v is not None and v.database:
                    db.setdefault(v.database, [])
                    if p not in db[v.database]:
                        db[v.database].append(p)
            self._db = db
        return self._db

    def find(self, database: str) -> tuple[Path | None, mc.Volume | None, str]:
        """The one fabulac whose database is `database`, or (None, None, why)."""
        got = self._index().get(database) or []
        if not got:
            return None, None, f"no fabulac the reader knows is oes:fabula/{database}"
        if len(got) > 1:
            return None, None, (f"{len(got)} fabulacs the reader knows are oes:fabula/{database}: "
                                + ", ".join(p.name for p in got[:4]))
        return got[0], self.load(got[0]), ""

    def item(self, uri: Any) -> tuple[mc.Volume | None, dict | None, str]:
        """The item a URI names: (its volume, its data, '') or (volume or None, None, why)."""
        parts = split_uri(uri)
        if parts is None:
            return None, None, f"{uri!r} is not a fabula's URI (oes:fabula/<database>/<path>)"
        db, path = parts
        _p, vol, why = self.find(db)
        if vol is None:
            return None, None, why
        if not path:
            return vol, None, f"{uri} names a fabulac, not an item in it"
        a = mc.parse_path(vol, f"oes:fabula/{db}/{path}")
        if isinstance(a, mc.Refusal) or not getattr(a, "id", None):
            return vol, None, f"{uri}: " + (a.message if isinstance(a, mc.Refusal) else "names no item")
        found = next((it.data for it in vol.items.values() if it.id == a.id), None)
        if found is None:
            return vol, None, f"{uri}: oes:fabula/{db} holds no {a.id}"
        return vol, found, ""


# ---------------------------------------------------------------------------
# The two checks
# ---------------------------------------------------------------------------

def _plainish(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.split())
    if isinstance(v, dict):
        return {str(k): _plainish(x) for k, x in v.items() if k != "means"}
    if isinstance(v, list):
        return [_plainish(x) for x in v]
    return v


def disagreements(mine: dict, theirs: dict) -> list[str]:
    """The fields of `AGREE` in which an interface differs from the item it is stated in (white space in text, and
    a parameter's `means`, aside)."""
    out = []
    for f in AGREE:
        a, b = _plainish(mine.get(f)), _plainish(theirs.get(f))
        if a != b:
            out.append(f)
    return out


def _components(items: list[mc.Item]) -> list[mc.Item]:
    return [it for it in items if it.module == "C" and it.kind == "component"]


def problems(vol: mc.Volume, known: Fabulacs | None = None) -> list[tuple[str, mc.Item | None, str, str | None, str]]:
    """`parts-resolve` and `interfaces-agree` over one fabulac: `(check, item or None, message, field, severity)`.
    Nothing for a fabulac that is neither a head nor a part and cites no interface."""
    cat = vol.catalog if isinstance(vol.catalog, dict) else {}
    items = list(vol.items.values())
    citing = [it for it in items if it.module == "C" and it.kind == "interface"
              and isinstance(it.data.get("stated-in"), str)]
    telling = [it for it in _components(items) if it.data.get("told-in") is not None]
    if "parts" not in cat and "head" not in cat and not citing and not telling:
        return []
    where = _where(vol)
    known = known or (Fabulacs.near(where) if where is not None else Fabulacs())
    out: list[tuple[str, mc.Item | None, str, str | None, str]] = []

    def add(check: str, item: mc.Item | None, msg: str, fld: str | None = None, sev: str | None = None) -> None:
        out.append((check, item, msg, fld, sev or SEVERITY[check]))

    me = volume_uri(vol.database) if vol.database else ""
    head_db = None
    if "head" in cat:
        h = split_uri(cat.get("head"))
        if h is None or h[1]:
            add("parts-resolve", None, f"head {cat.get('head')!r} is not a fabulac's URI (oes:fabula/<database>)",
                "head")
        else:
            head_db = h[0]
            _p, hv, why = known.find(head_db)
            if hv is None:
                add("parts-resolve", None, f"its head is not known: {why}", "head")
                head_db = None
    if "parts" in cat:
        out += _head_side(vol, cat, items, where, known, me)
    for it in citing:
        uri = it.data["stated-in"]
        parts = split_uri(uri)
        if parts is not None and "parts" not in cat and head_db is not None and parts[0] != head_db:
            add("parts-resolve", it, f"stated-in names {volume_uri(parts[0])}, not its head {volume_uri(head_db)}",
                "stated-in")
            continue
        if parts is not None and "parts" not in cat and "head" not in cat:
            add("parts-resolve", it, "stated-in in a fabulac that names no head and no parts", "stated-in")
            continue
        _v, theirs, why = known.item(uri)
        if theirs is None:
            add("parts-resolve", it, f"stated-in: {why}", "stated-in")
            continue
        if theirs.get("type") != "interface" or not str(theirs.get("id", "")).startswith("C:interface/"):
            add("parts-resolve", it, f"stated-in names {theirs.get('id')}, which is not a C:interface", "stated-in")
            continue
        diff = disagreements(it.data, theirs)
        if diff:
            add("interfaces-agree", it, f"{it.id} does not agree with {uri} in its " + ", ".join(diff), diff[0])
    return out


def _head_side(vol: mc.Volume, cat: dict, items: list[mc.Item], where: Path | None, known: Fabulacs,
               me: str) -> list[tuple]:
    out: list[tuple] = []

    def add(check: str, item: mc.Item | None, msg: str, fld: str | None = None, sev: str | None = None) -> None:
        out.append((check, item, msg, fld, sev or SEVERITY[check]))

    parts = cat.get("parts")
    if not isinstance(parts, list) or not parts:
        add("parts-resolve", None, "parts is a list of {uri, path, sha256}, one per part", "parts")
        return out
    uris: list[str] = []
    for i, p in enumerate(parts):
        fld = f"parts[{i}]"
        if not isinstance(p, dict) or not isinstance(p.get("uri"), str) or not isinstance(p.get("path"), str):
            add("parts-resolve", None, f"{fld} is {{uri, path, sha256}}", fld)
            continue
        uri, rel = p["uri"], p["path"]
        u = split_uri(uri)
        if u is None or u[1]:
            add("parts-resolve", None, f"{fld}: {uri!r} is not a fabulac's URI (oes:fabula/<database>)", f"{fld}.uri")
            continue
        uris.append(volume_uri(u[0]))
        if where is None:
            continue
        path = (where.parent / rel)
        known.add_file(path)
        pv = known.load(path)
        if pv is None:
            add("parts-resolve", None, f"{fld}: {rel} is not a fabulac the reader knows", f"{fld}.path")
            continue
        if pv.database != u[0]:
            add("parts-resolve", None, f"{fld}: {rel} is {volume_uri(pv.database)}, not {uri}", f"{fld}.uri")
            continue
        names = pv.catalog.get("head") if isinstance(pv.catalog, dict) else None
        hn = split_uri(names)
        if hn is None or volume_uri(hn[0]) != me:
            add("parts-resolve", None, f"{fld}: {rel} names " + (f"{names} as its head" if names else "no head")
                + f", not {me}", f"{fld}.path")
        sha = p.get("sha256")
        now = _sha(path)
        if isinstance(sha, str) and sha != now:
            add("interfaces-agree", None, f"{fld}: {rel} moved since the head last checked it (its sha256 is "
                                         f"{now[:12]}…, the head's {sha[:12]}…): read it again", f"{fld}.sha256",
                "note")
    told: dict[str, int] = {}
    for it in _components(items):
        t = it.data.get("told-in")
        if t is None:
            continue
        u = split_uri(t)
        if u is None or u[1] or volume_uri(u[0]) not in uris:
            add("parts-resolve", it, f"told-in {t!r} is not one of the head's parts", "told-in")
            continue
        told[volume_uri(u[0])] = told.get(volume_uri(u[0]), 0) + 1
    for uri in uris:
        n = told.get(uri, 0)
        if n != 1:
            add("parts-resolve", None, f"{uri} is told in {n} C:components of the head; a head holds one per part",
                "parts")
    return out


# ---------------------------------------------------------------------------
# Which parts moved
# ---------------------------------------------------------------------------

STATES = ("in-step", "moved", "gone", "new", "unread")


def which_moved(recorded: Mapping[str, Any], now: Mapping[str, Any]) -> dict[str, list[str]]:
    """The one comparison of keeping in step: each name with the digest recorded for it and the digest it has now
    (None: not there now, or never recorded). `{in-step, moved, gone, new, unread}`, each sorted: in step, the same;
    moved, both there and different; gone, recorded and not there now; new, there now and not recorded; unread, named
    with no digest recorded (never read, so it cannot be said to have moved)."""
    out: dict[str, list[str]] = {s: [] for s in STATES}
    for name in sorted(set(recorded) | set(now), key=lambda s: str(s).encode("utf-8")):
        was, got = recorded.get(name), now.get(name)
        if name not in recorded:
            out["new" if got is not None else "gone"].append(name)
        elif was is None:
            out["unread"].append(name)
        elif got is None:
            out["gone"].append(name)
        elif was != got:
            out["moved"].append(name)
        else:
            out["in-step"].append(name)
    return out


def part_folder(part: Path, cat: dict) -> Path | None:
    """The folder a part's fabulac was read from: `tally-core/` beside `tally-core.fabulac.cosm`, else its
    `source.path` relative to it; None for an authored part (its entailment is kept in step instead)."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    if src.get("kind") == "authored":
        return None
    beside = part.parent / part.name[: -len(FABULAC_SUFFIX)] if part.name.endswith(FABULAC_SUFFIX) else None
    if beside is not None and beside.is_dir():
        return beside
    sp = src.get("path")
    return (part.parent / sp) if isinstance(sp, str) and sp else beside


def parts_moved(head: Path, *, folders: Mapping[str, Path] | None = None,
                known: Fabulacs | None = None) -> dict:
    """Which parts of a head moved (the rule run at a release): `{parts: [{uri, path, fabulac, source, folder,
    files?}], moved: [uri], fabulacs: which_moved(...), sources: which_moved(...)}`. `fabulac` is the part's file
    against the head's `parts` sha256; `source` its source tree now (`macrocosm.tree_digest`, of `folders[uri]` when
    given, else `part_folder`) against its `source.tree`; for an authored part, its entailment read as
    `fabulac_entail.step_state` reads one (`files`: the files to tell again). `moved` lists the parts whose source
    moved or is gone, or whose entailment has a file to tell again."""
    head = Path(head)
    hv = mc.load_volume(head)
    cat = hv.catalog if isinstance(hv.catalog, dict) else {}
    known = known or Fabulacs.near(head)
    folders = dict(folders or {})
    rec_fab, now_fab, rec_src, now_src = {}, {}, {}, {}
    rows = []
    for p in cat.get("parts") or []:
        if not isinstance(p, dict) or not isinstance(p.get("uri"), str):
            continue
        uri, rel = p["uri"], str(p.get("path") or "")
        path = head.parent / rel
        row: dict = {"uri": uri, "path": rel}
        rec_fab[uri] = p.get("sha256") if isinstance(p.get("sha256"), str) else None
        now_fab[uri] = _sha(path) if path.is_file() else None
        pv = known.load(path)
        pcat = pv.catalog if pv is not None and isinstance(pv.catalog, dict) else {}
        src = pcat.get("source") if isinstance(pcat.get("source"), dict) else {}
        folder = Path(folders[uri]) if uri in folders else (part_folder(path, pcat) if pv is not None else None)
        if src.get("kind") == "authored" and uri not in folders:
            from . import fabulac_entail as _fe
            st = _fe.step_state(path) if pv is not None else {"tell": []}
            row["files"] = list(st.get("tell") or [])
            rec_src[uri] = "entailment"
            now_src[uri] = "entailment" if not row["files"] else "moved"
        else:
            rec_src[uri] = src.get("tree") if isinstance(src.get("tree"), str) else None
            try:
                now_src[uri] = mc.tree_digest(folder)["tree"] if folder is not None and folder.is_dir() else None
            except OSError:
                now_src[uri] = None
        row["folder"] = str(folder) if folder is not None else None
        rows.append(row)
    fabs, srcs = which_moved(rec_fab, now_fab), which_moved(rec_src, now_src)
    state_of = {n: s for s, names in srcs.items() for n in names}
    fstate = {n: s for s, names in fabs.items() for n in names}
    for row in rows:
        row["source"] = state_of.get(row["uri"])
        row["fabulac"] = fstate.get(row["uri"])
    return {"parts": rows, "moved": [r["uri"] for r in rows if r["source"] in ("moved", "gone")],
            "fabulacs": fabs, "sources": srcs}


# ---------------------------------------------------------------------------
# Writing: a catalog key set in place, a head made from parts, the parts' digests stamped
# ---------------------------------------------------------------------------

def _catalog_order() -> list[str]:
    m = mc.default_registry().get("fabula")
    keys = m._block("catalog").get("keys") if m is not None else None
    return [str(k) for k in keys] if isinstance(keys, list) else []


def set_catalog_key(text: str, key: str, value: Any) -> str:
    """The fabulac's text with one top-level catalog key set (replaced in place, or written before the first key
    the manifest orders after it); every other byte kept. Raises ValueError when the result would not read back as
    the same volume with that key."""
    before = mc.yaml_load(text)
    if not isinstance(before, dict):
        raise ValueError("the fabulac does not read as a volume")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    tops = [(i, m.group(1)) for i, line in enumerate(lines) if (m := _TOP_KEY.match(line.lstrip("﻿")))]
    block = mc.dump({key: value}).replace("\n", nl)
    here = next((i for i, k in tops if k == key), None)
    if here is not None:
        j = here + 1
        while j < len(lines) and (lines[j][:1] in (" ", "\t", "-") or not lines[j].strip()):
            j += 1
        lines[here:j] = [block]
    else:
        order = _catalog_order()
        later = set(order[order.index(key) + 1:]) if key in order else {"nodes"}
        at = next((i for i, k in tops if k in later), len(lines))
        while at > 0 and lines[at - 1].lstrip().startswith("#"):
            at -= 1
        lines[at:at] = [block]
    out = "".join(lines)
    after = mc.yaml_load(out)
    plain = mc.yaml_load(mc.dump({"v": value}))["v"]
    if (not isinstance(after, dict) or after.get(key) != plain
            or {k: v for k, v in after.items() if k != key} != {k: v for k, v in before.items() if k != key}):
        raise ValueError(f"{key} could not be set without changing anything else; the fabulac was left as it was")
    return out


def _write(path: Path, text: str) -> None:
    from .dialectic import write_atomic
    write_atomic(path, text)


def stamp_parts(head: Path) -> list[dict]:
    """The head's `parts` with each sha256 taken again from the part's file as it is now (the head has checked them);
    written into the head; returns the new list."""
    head = Path(head)
    text = head.read_text(encoding="utf-8")
    cat = mc.yaml_load(text)
    parts = []
    for p in cat.get("parts") or []:
        p = dict(p)
        f = head.parent / str(p.get("path"))
        if f.is_file():
            p["sha256"] = _sha(f)
        parts.append(p)
    _write(head, set_catalog_key(text, "parts", parts))
    return parts


def _slug(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return out or "part"


def maker_ref(by: str) -> tuple[str, str]:
    """Who made a head, as the reference `source.by` holds and the `R:maker` item it names: `(R:maker/<slug>, name)`.
    A name (`Ada`) becomes `R:maker/ada`; a reference given whole (`R:maker/ada`) is kept."""
    raw = str(by).strip()
    if raw.startswith("R:maker/") and re.fullmatch(r"R:maker/[a-z0-9]+(?:-[a-z0-9]+)*", raw):
        return raw, raw.split("/", 1)[1]
    return f"R:maker/{_slug(raw.split('/', 1)[-1] if raw.startswith('R:maker/') else raw)}", \
        (raw.split("/", 1)[-1] if raw.startswith("R:maker/") else raw)


def make_head(head: Path, parts: Iterable[Path], *, name: str | None = None, licence: Any = None,
              by: str | None = None, at: Any = None, interfaces: Iterable[dict] = (),
              does: Mapping[str, str] | None = None) -> dict:
    """Make a head fabulac at `head` from a set of part fabulacs: its catalog (`flavour: fabulac`, the authored
    source, `parts` with each part's URI, path and sha256), an `R:licence`, one `C:component` per part told in it, and
    the `interfaces` given (`C:interface` items, stated once); and set `head` in each part's catalog (each part's
    sha256 is taken after). Refuses (FileExistsError) a head that is there already, and (ValueError) a part that is
    not a fabulac, or two parts of one database. Returns `{head, uri, parts}`."""
    head = Path(head)
    if head.exists():
        raise FileExistsError(f"{head.name} is there already; a head is made once")
    if not head.name.endswith(FABULAC_SUFFIX):
        raise ValueError(f"a head is a fabulac: <name>{FABULAC_SUFFIX}")
    stem = head.name[: -len(FABULAC_SUFFIX)]
    db = _slug(stem)
    me = volume_uri(db)
    day = (at if isinstance(at, str) else (at or dt.datetime.now(dt.timezone.utc)).date().isoformat())
    known = Fabulacs()
    rows, comps, seen = [], [], set()
    for p in parts:
        p = Path(p)
        v = known.load(p)
        if v is None:
            raise ValueError(f"{p.name} is not a fabulac")
        if v.database in seen or v.database == db:
            raise ValueError(f"two parts are oes:fabula/{v.database}")
        seen.add(v.database)
        rel = Path(p.absolute()).relative_to(head.parent.absolute()).as_posix() \
            if p.absolute().is_relative_to(head.parent.absolute()) else p.absolute().as_posix()
        rows.append((p, {"uri": volume_uri(v.database), "path": rel}))
        pname = str(v.catalog.get("name") or v.database)
        comps.append({"id": f"C:component/{_slug(v.database)}", "type": "component", "name": pname,
                      "summary": (does or {}).get(v.database) or f"{pname}, a part told in a fabulac of its own.",
                      "told-in": volume_uri(v.database), "stance": "axiom",
                      "provenance": {"mode": "manual", "sources": ["the head, made from its parts"], "confidence": 1}})
    if not rows:
        raise ValueError("a head names at least one part")
    for p, row in rows:                                   # each part names its head
        _write(p, set_catalog_key(p.read_text(encoding="utf-8"), "head", me))
        row["sha256"] = _sha(p)
    lic = licence if licence is not None else {"pending": "What licence is the whole program offered under?"}
    src: dict = {"kind": "authored", "language": "python", "licence": lic}
    maker_id, maker_name = maker_ref(by) if by and str(by).strip() else (None, None)
    if maker_id:
        src["by"] = [maker_id]
    src["at"] = day
    makers = [{"id": maker_id, "type": "maker", "name": maker_name, "summary": f"{maker_name} made the head.",
               "capacity": "author", "stance": "axiom",
               "provenance": {"mode": "manual", "sources": ["the head, made from its parts"], "confidence": 1}}] \
        if maker_id else []
    nodes = makers + [{"id": "R:licence/licence", "type": "licence", "name": "licence",
                       "summary": f"The terms {name or stem} is offered on.", "stance": "axiom",
                       "provenance": {"mode": "manual", "sources": ["the head, made from its parts"], "confidence": 1},
                       **({"identifier": licence} if isinstance(licence, str) else {})}]
    nodes += comps + [dict(i) for i in interfaces]
    doc = {"oes": "fabula/1", "flavour": "fabulac", "id": f"fabula/{db}", "name": name or stem, "source": src,
           "derived": {"at": f"{day}T00:00:00Z" if len(day) == 10 else day, "by": "person", "mode": "rules",
                       "completeness": "outline", "chunks": 0},
           "parts": [r for _p, r in rows],
           "atem": {"line": f"{name or stem}, told in {len(rows)} parts.", "focus": "its parts and what passes "
                    "between them", "push": "it is too large for one fabulac", "pull": "each part stays small"},
           "nodes": nodes}
    from .dialectic import dump_text
    _write(head, dump_text(doc))
    return {"head": str(head), "uri": me, "parts": [r for _p, r in rows]}


__all__ = ["AGREE", "CHECKS", "Fabulacs", "SEVERITY", "STATES", "disagreements", "make_head", "maker_ref", "part_folder",
           "parts_moved", "problems", "set_catalog_key", "split_uri", "stamp_parts", "volume_uri", "which_moved"]
