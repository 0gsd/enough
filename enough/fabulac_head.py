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

**The members of a class that crosses.** Stating `class Registry` is not enough: a part that calls it needs what the
class holds and what its methods give (W4-G3: Thym's compiler rebuilt 474 of 968 because `Registry.manifests`, a map
by name, was not stated; W3-G2: `Volume.items`, a map of items). So for every interface of surface `class` it is
given, `make_head` states the class's members, read from the source by rule (`ast`), never guessed:

- each method a person or another part may call (every method not named `_x`; the special methods `__x__` too) as a
  `C:interface` of surface `method`, id `<the class's id>.<method>`, name `<Class>.<method>`, with its signature (its
  decorators before it), `takes`, `gives` and the errors it raises itself; the providing fabulac's own item for that
  method lends its summary and its words when its signature is the one the source has;
- its fields as one `C:structure`, id `C:structure/<the class's id after C:interface/>`: the names the class body
  declares (a record class's fields, with defaults and whether they are required) and every public name its methods
  set on `self`, each with its type as written (or, when none is written, as the value it is set to shows it), its
  plain kind (`map`, `list`, `text` …), and for a map or a list whose type does not say what it holds, what the
  module puts in it (`vol.items[it.key] = it`: "a map from each Item's key to that Item").

The source is found by rule: the fabulac (a part, or one of `providers`, such as another program's) whose own
`C:interface` of that class has `defined-in`, its `C:file`'s path, under the folder the fabulac was read from
(`part_folder`); `sources` names a file outright. A class whose source cannot be read is listed `unread`, its members
not stated. `interfaces-agree` compares members too: when a part's interface is stated in a class of the head, each
of the part's members of it (`<id>.<method>`, and its `C:structure` of the same name) agrees with the head's, a
method in the four fields of `AGREE`, a field in its type and kind.

Standalone like the reader: the standard library, PyYAML (through the reader) and `enough.macrocosm`.
"""
from __future__ import annotations

import ast
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
        if theirs.get("surface") == "class" and _v is not None:
            for item, msg, fld in member_disagreements(items, it.id, list(_v.items.values()), str(theirs["id"]),
                                                       uri):
                add("interfaces-agree", item, msg, fld)
    return out


def _members(items: list[mc.Item], class_id: str) -> tuple[dict[str, mc.Item], mc.Item | None]:
    """A class's members among `items`: its methods (`<class_id>.<name>`, one step down) by name, and its
    `C:structure` of the same name."""
    pre = class_id + "."
    meths = {it.id[len(pre):]: it for it in items
             if it.module == "C" and it.kind == "interface" and it.id.startswith(pre) and "." not in it.id[len(pre):]}
    sid = "C:structure/" + class_id.split("/", 1)[-1]
    struct = next((it for it in items if it.id == sid), None)
    return meths, struct


def member_disagreements(mine: list[mc.Item], my_class: str, theirs: list[mc.Item], their_class: str,
                         uri: str) -> list[tuple[mc.Item, str, str]]:
    """`interfaces-agree` on a class's members: each member a part states of a class stated in the head (its methods
    in `AGREE`, the fields of its structure in type and kind) against the head's; a member the head does not state,
    or one that says its own `stated-in`, is left to the rest of the check."""
    out: list[tuple[mc.Item, str, str]] = []
    my_m, my_s = _members(mine, my_class)
    th_m, th_s = _members(theirs, their_class)
    base = uri.rsplit("/C/interface/", 1)[0]
    for name, it in my_m.items():
        other = th_m.get(name)
        if other is None or isinstance(it.data.get("stated-in"), str):
            continue
        diff = disagreements(it.data, other.data)
        if diff:
            out.append((it, f"{it.id} does not agree with {base}/C/interface/{other.id.split('/', 1)[1]}, a member of "
                            f"{their_class}, in its " + ", ".join(diff), diff[0]))
    if my_s is not None and th_s is not None:
        th_f = {f.get("name"): f for f in th_s.data.get("fields") or [] if isinstance(f, dict)}
        for f in my_s.data.get("fields") or []:
            if not isinstance(f, dict) or f.get("name") not in th_f:
                continue
            g = th_f[f["name"]]
            bad = [k for k in ("type", "kind") if k in f and k in g and _plainish(f[k]) != _plainish(g[k])]
            if bad:
                out.append((my_s, f"{my_s.id} does not agree with {base}/C/structure/{th_s.id.split('/', 1)[1]}, the "
                                  f"fields of {their_class}: {f['name']}'s " + " and ".join(bad)
                                  + f" is {', '.join(repr(f[k]) for k in bad)}, the head's "
                                  + ", ".join(repr(g[k]) for k in bad), "fields"))
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


# ---------------------------------------------------------------------------
# The members of a class that crosses, read from its source by rule
# ---------------------------------------------------------------------------

#: A type's plain kind (MacroCOSM 18.4.2, "The plain kinds"), by the last name of its outer type.
_KIND_OF = {
    **dict.fromkeys(("dict", "Dict", "Mapping", "MutableMapping", "defaultdict", "OrderedDict", "Counter",
                     "ChainMap"), "map"),
    **dict.fromkeys(("list", "List", "tuple", "Tuple", "set", "Set", "frozenset", "FrozenSet", "Sequence",
                     "MutableSequence", "Iterable", "Iterator", "Collection", "deque", "AbstractSet"), "list"),
    "str": "text", "int": "whole number", "float": "number", "Decimal": "number", "bool": "yes-or-no",
    "bytes": "bytes", "bytearray": "bytes", "Path": "path", "PurePath": "path", "PosixPath": "path",
    "datetime": "moment", "date": "moment", "None": "nothing", "NoneType": "nothing",
}
_NOT_A_KIND = {"Any", "object", "TypeVar", "Callable", "Union"}
_SIMPLE = {"str", "int", "float", "bool", "bytes"}


def _split_top(text: str, sep: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return out + [cur.strip()] if cur.strip() else out


def plain_kind(type_text: Any) -> str | None:
    """The plain kind of a type as written (`dict[str, Manifest]` -> `map`, `list[Path] | None` -> `list`,
    `Manifest` -> `record`); None for a type that says nothing (`Any`)."""
    t = str(type_text or "").strip().strip("'\"")
    if not t:
        return None
    alts = [a for a in _split_top(t, "|") if a not in ("None", "NoneType")] or ["None"]
    if len(alts) != 1:
        kinds = {plain_kind(a) for a in alts}
        return kinds.pop() if len(kinds) == 1 else None
    t = alts[0]
    if t.startswith(("Optional[", "typing.Optional[")) and t.endswith("]"):
        return plain_kind(t[t.index("[") + 1:-1])
    base = t.split("[", 1)[0].rsplit(".", 1)[-1]
    if base == "Literal":
        return "text" if ("'" in t or '"' in t) else None
    if base in _NOT_A_KIND:
        return None
    return _KIND_OF.get(base) or ("record" if base[:1].isupper() else None)


def _plain_name(type_text: str) -> str:
    """A type named in plain words when it is the language's own (`str` -> `text`); the program's names stay."""
    k = _KIND_OF.get(type_text)
    return k if k and type_text in _SIMPLE else type_text


def _is_dunder(n: str) -> bool:
    return n.startswith("__") and n.endswith("__") and len(n) > 4


def _named(node: ast.AST) -> str | None:
    """The last name a call or a reference names (`Item(...)`, `mc.Item(...)` -> `Item`)."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _type_of(expr: ast.AST | None, known: Mapping[str, str]) -> str | None:
    """The type a value shows by its form alone: a literal, a call of a class (a name that starts upper-case), a name
    whose type is known in that function, a builtin container built by name. None when the form does not say."""
    if expr is None:
        return None
    if isinstance(expr, ast.Constant):
        return "None" if expr.value is None else type(expr.value).__name__
    if isinstance(expr, ast.JoinedStr):
        return "str"
    if isinstance(expr, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(expr, (ast.List, ast.ListComp)):
        el = _type_of(expr.elt, known) if isinstance(expr, ast.ListComp) else None
        if isinstance(expr, ast.List) and expr.elts:
            got = {_type_of(e, known) for e in expr.elts}
            el = got.pop() if len(got) == 1 else None
        return f"list[{el}]" if el and el != "None" else "list"
    if isinstance(expr, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(expr, ast.Tuple):
        return "tuple"
    if isinstance(expr, ast.IfExp):
        a, b = _type_of(expr.body, known), _type_of(expr.orelse, known)
        if a == b or b in (None, "None"):
            return a
        if a in (None, "None"):
            return b
        if a.split("[")[0] == b.split("[")[0]:             # one container either way: the one that says more
            return a if "[" in a else b
        return None
    if isinstance(expr, ast.Name):
        return known.get(expr.id)
    if isinstance(expr, ast.Call):
        n = _named(expr)
        if n in ("dict", "list", "set", "tuple", "str", "int", "float", "bool", "bytes", "frozenset"):
            return n
        if n in ("defaultdict", "OrderedDict", "Counter", "deque"):
            return n
        if n and n[:1].isupper():
            return n
    return None


def _locals(fn: ast.AST) -> dict[str, str]:
    """The names whose type one function shows: its annotated parameters, its annotated names, and each name it
    sets once to a value whose form says its type."""
    known: dict[str, str] = {}
    args = getattr(fn, "args", None)
    if args is not None:
        for a in args.posonlyargs + args.args + args.kwonlyargs:
            if a.annotation is not None:
                known[a.arg] = ast.unparse(a.annotation)
    seen: dict[str, set] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            known[node.target.id] = ast.unparse(node.annotation)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            seen.setdefault(node.targets[0].id, set()).add(_type_of(node.value, known))
    for n, ts in seen.items():
        if n not in known and len(ts) == 1 and None not in ts:
            known[n] = ts.pop()
    return known


def _is_class(type_text: str | None, cls: str) -> bool:
    if not type_text:
        return False
    return any(a.strip("'\"").rsplit(".", 1)[-1] == cls for a in _split_top(type_text, "|"))


def _fills(tree: ast.Module, cls_node: ast.ClassDef, field: str) -> list[tuple[str, str | None, str | None]]:
    """How the module fills one field of the class: `(how, key, value)` for each `<x>.<field>[k] = v`,
    `<x>.<field>.setdefault(k, v)` (a map) and `<x>.<field>.append(v)` / `.add(v)` (a list), where `<x>` is `self` in
    the class's own methods or a name that function knows to be one of the class. The key is said as `Item.key` when
    it is an attribute of the value set."""
    cls = cls_node.name
    inside = {id(n) for n in ast.walk(cls_node)}
    out: list[tuple[str, str | None, str | None]] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        known = _locals(fn)
        whose = {n for n, t in known.items() if _is_class(t, cls)}
        if id(fn) in inside:
            whose.add("self")

        def ours(node: ast.AST) -> bool:
            return (isinstance(node, ast.Attribute) and node.attr == field and isinstance(node.value, ast.Name)
                    and node.value.id in whose)

        def key_of(k: ast.AST, v: ast.AST) -> str | None:
            if isinstance(k, ast.Attribute) and isinstance(k.value, ast.Name) and isinstance(v, ast.Name) \
                    and k.value.id == v.id and known.get(v.id):
                return f"{known[v.id]}.{k.attr}"
            return _type_of(k, known)

        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and ours(t.value):
                        out.append(("map", key_of(t.slice, node.value), _type_of(node.value, known)))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and ours(node.func.value):
                if node.func.attr in ("append", "add", "insert") and node.args:
                    out.append(("list", None, _type_of(node.args[-1], known)))
                elif node.func.attr == "setdefault" and len(node.args) == 2:
                    out.append(("map", key_of(node.args[0], node.args[1]), _type_of(node.args[1], known)))
    return out


def _holds(kind: str | None, type_text: str | None, fills: list[tuple[str, str | None, str | None]]) -> str | None:
    """What a map or a list holds, in plain words, from its type as written or, when that does not say, from how the
    module fills it; None when neither says one thing."""
    t = (type_text or "").strip()
    alts = [a for a in _split_top(t, "|") if a != "None"]
    t = alts[0] if len(alts) == 1 else t
    if kind == "map" and "[" in t:
        inner = _split_top(t[t.index("[") + 1:t.rindex("]")], ",")
        if len(inner) == 2:
            return f"a map from {_plain_name(inner[0])} to {_plain_name(inner[1])}"
    if kind == "list" and "[" in t:
        inner = _split_top(t[t.index("[") + 1:t.rindex("]")], ",")
        if len(inner) == 1 or (len(inner) == 2 and inner[1] == "..."):
            return f"a list of {_plain_name(inner[0])}"
    mine = [f for f in fills if f[0] == kind]
    vals = {v for _h, _k, v in mine if v and v != "None"}
    if len(vals) != 1:
        return None
    v = vals.pop()
    if kind == "list":
        return f"a list of {_plain_name(v)}"
    keys = {k for _h, k, _v in mine if k}
    if len(keys) != 1:
        return f"a map to {_plain_name(v)}"
    k = keys.pop()
    if k.startswith(v + ".") and "." not in k[len(v) + 1:]:
        return f"a map from each {v}'s {k[len(v) + 1:]} to that {v}"
    return f"a map from {_plain_name(k)} to {_plain_name(v)}"


def _seg(text: str, node: ast.AST) -> str:
    """A node as written in the source, white space folded to one line (as the survey reads it)."""
    s = ast.get_source_segment(text, node)
    return " ".join(s.split()) if s is not None else ast.unparse(node)


def def_line(text: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """A method's line as the survey writes a signature (`repo_engine._signature`, then the decorators before it on
    the same line, as `thym.moves.code` joins them): parameters with their annotations and defaults as written, `= `
    around an annotated parameter's default, `/` and `*` where the source has them, the return annotation."""
    a = node.args
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)

    def one(arg: ast.arg, d: ast.AST | None, star: str = "") -> str:
        s = star + arg.arg
        if arg.annotation is not None:
            s += f": {_seg(text, arg.annotation)}"
            if d is not None:
                s += f" = {_seg(text, d)}"
        elif d is not None:
            s += f"={_seg(text, d)}"
        return s
    parts: list[str] = []
    for i, (arg, d) in enumerate(zip(pos, defaults)):
        parts.append(one(arg, d))
        if a.posonlyargs and i == len(a.posonlyargs) - 1:
            parts.append("/")
    if a.vararg:
        parts.append(one(a.vararg, None, "*"))
    elif a.kwonlyargs:
        parts.append("*")
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        parts.append(one(arg, d))
    if a.kwarg:
        parts.append(one(a.kwarg, None, "**"))
    kw = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    ret = f" -> {_seg(text, node.returns)}" if node.returns is not None else ""
    return " ".join([f"@{_seg(text, d)}" for d in node.decorator_list] + [f"{kw} {node.name}({', '.join(parts)}){ret}"])


def _method_entry(node: ast.FunctionDef | ast.AsyncFunctionDef, text: str) -> dict:
    """One method as an interface reads it: its signature (decorators before it), what it takes (without self or
    cls), what it gives, the errors it raises itself, the first paragraph of its docstring."""
    sig = def_line(text, node)
    a = node.args
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    static = any(_named(d) == "staticmethod" for d in node.decorator_list)
    pairs = list(zip(pos, defaults))
    if pairs and not static and pairs[0][0].arg in ("self", "cls"):
        pairs = pairs[1:]
    takes = []

    def one(arg: ast.arg, dflt: ast.AST | None, name: str | None = None, required: bool | None = None) -> None:
        t: dict = {"name": name or arg.arg}
        if arg.annotation is not None:
            t["type"] = _seg(text, arg.annotation)
        if dflt is not None:
            t["default"] = _seg(text, dflt)
        t["required"] = (dflt is None) if required is None else required
        takes.append(t)

    for arg, dflt in pairs:
        one(arg, dflt)
    if a.vararg is not None:
        one(a.vararg, None, "*" + a.vararg.arg, False)
    for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
        one(arg, dflt)
    if a.kwarg is not None:
        one(a.kwarg, None, "**" + a.kwarg.arg, False)
    raises: list[str] = []
    todo = list(node.body)
    while todo:                                           # its own raises, not those of a function inside it
        n = todo.pop(0)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Raise) and n.exc is not None:
            e = _named(n.exc)
            if e and e[:1].isupper() and e not in raises:
                raises.append(e)
        todo.extend(ast.iter_child_nodes(n))
    doc = (ast.get_docstring(node) or "").split("\n\n")[0]
    return {"name": node.name, "signature": sig, "takes": takes,
            "gives": {"type": _seg(text, node.returns)} if node.returns is not None else None,
            "raises": [{"error": e} for e in raises], "summary": " ".join(doc.split()),
            "lines": f"{node.lineno}-{node.end_lineno}"}


def class_members(source: str | Path, name: str) -> dict | None:
    """The members of the class `name` (a top-level class of the source, by its last name), read by rule (`ast`):
    `{name, record, frozen, lines, methods: [...], fields: [...]}`. Methods are those another part may call: every
    one not named `_x` (the special `__x__` ones too), each `{name, signature, takes, gives, raises, summary, lines}`.
    Fields are the names the class body declares (a record class's fields, `{name, type, default, required}`) and
    every public name its methods set on `self` (its type as written, else as its value shows it), each with its
    plain `kind` and, for a map or a list, what it holds when the type or the module's filling of it says (`means`).
    None when the source holds no such class."""
    text = Path(source).read_text(encoding="utf-8") if isinstance(source, Path) else str(source)
    tree = ast.parse(text)
    cls_name = name.rsplit(".", 1)[-1]
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
    if cls is None:
        return None
    decos = [d for d in cls.decorator_list if _named(d) == "dataclass"]
    record = bool(decos)
    frozen = any(isinstance(d, ast.Call) and any(k.arg == "frozen" and getattr(k.value, "value", False) is True
                                                 for k in d.keywords) for d in decos)
    methods: list[dict] = []
    fields: dict[str, dict] = {}
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not _is_dunder(node.name):
                continue
            methods.append(_method_entry(node, text))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            ann = _seg(text, node.annotation)
            if ann.split("[", 1)[0].rsplit(".", 1)[-1] == "ClassVar":
                continue
            f: dict = {"name": node.target.id, "type": ann}
            dflt: str | None = _seg(text, node.value) if node.value is not None else None
            if record and isinstance(node.value, ast.Call) and _named(node.value) == "field":
                kws = {k.arg: k.value for k in node.value.keywords}   # field(default=…, default_factory=…, …)
                dflt = (_seg(text, kws["default"]) if "default" in kws
                        else f"{_seg(text, kws['default_factory'])}()" if "default_factory" in kws else None)
            if dflt is not None:
                f["default"] = dflt
            if record:
                f["required"] = dflt is None
            fields[node.target.id] = f
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id not in fields:
                    f = {"name": t.id, "default": _seg(text, node.value)}
                    ty = _type_of(node.value, {})
                    if ty and ty != "None":
                        f["type"] = ty
                    fields[t.id] = f
    for fn in cls.body:                                    # the names its methods set on self
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        known = _locals(fn)
        for node in ast.walk(fn):
            targets: list[tuple[ast.AST, ast.AST | None, ast.AST | None]] = []
            if isinstance(node, ast.AnnAssign):
                targets = [(node.target, node.annotation, node.value)]
            elif isinstance(node, ast.Assign):
                targets = [(t, None, node.value) for t in node.targets]
            for t, ann, val in targets:
                if not (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"):
                    continue
                if t.attr.startswith("_"):
                    continue
                ty = _seg(text, ann) if ann is not None else _type_of(val, known)
                f = fields.get(t.attr)
                if f is None:
                    fields[t.attr] = {"name": t.attr, **({"type": ty} if ty and ty != "None" else {})}
                elif ann is not None or ("type" not in f and ty and ty != "None"):
                    f["type"] = ty
    for f in fields.values():
        k = plain_kind(f.get("type"))
        if k:
            f["kind"] = k
        if k in ("map", "list"):
            says = _holds(k, f.get("type"), _fills(tree, cls, f["name"]))
            if says:
                f["means"] = says
    return {"name": cls_name, "record": record, "frozen": frozen, "lines": f"{cls.lineno}-{cls.end_lineno}",
            "methods": methods, "fields": list(fields.values())}


def function_item(source: str | Path, name: str, item_id: str, *, where: str = "") -> dict | None:
    """A top-level function another part calls, stated from its syntax when no fabulac has read it (a private helper
    a part leans on, a name outside the module's `__all__`): a `C:interface` of surface `function` with its line,
    takes, gives and raises read as a method's are. None when the source has no such function."""
    text = Path(source).read_text(encoding="utf-8") if isinstance(source, Path) else str(source)
    node = next((n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == name), None)
    if node is None:
        return None
    m = _method_entry(node, text)
    item: dict = {"id": item_id, "type": "interface", "name": name,
                  "summary": m["summary"] or f"The function {name}.", "surface": "function",
                  "signature": m["signature"]}
    for k in ("takes", "gives", "raises"):
        if m.get(k):
            item[k] = m[k]
    item.update({"stance": "axiom", "provenance": {**_PROV, "sources": [
        f"{where}#L{m['lines'].replace('-', '-L')}" if where else "the function's source, by rule (ast)"]}})
    return item


_LENT = ("summary", "takes", "gives", "raises", "plain")
_PROV = {"mode": "derived", "confidence": 1, "state": "known"}


def member_items(iface: Mapping[str, Any], members: Mapping[str, Any], *, where: str = "",
                 lent: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict]:
    """The items a head states for one class's members (`class_members`): a `C:interface` of surface `method` per
    method, `<the class's id>.<method>`, and one `C:structure` of its fields, `C:structure/<the class's id>`.
    `lent` holds the providing fabulac's own items by method name: one whose signature is the source's lends its
    summary, takes, gives, raises and plain words. `where` is the source's path, for provenance."""
    iid = str(iface["id"])
    cls = members["name"]
    suffix = iid.split("/", 1)[1]
    out: list[dict] = []
    for m in members.get("methods") or []:
        item: dict = {"id": f"{iid}.{m['name']}", "type": "interface", "name": f"{cls}.{m['name']}",
                      "summary": m.get("summary") or f"The method {m['name']} of {cls}.", "surface": "method",
                      "signature": m["signature"]}
        if m.get("takes"):
            item["takes"] = m["takes"]
        if m.get("gives"):
            item["gives"] = m["gives"]
        if m.get("raises"):
            item["raises"] = m["raises"]
        own = (lent or {}).get(m["name"])
        if own is not None and " ".join(str(own.get("signature") or "").split()) == " ".join(m["signature"].split()):
            for k in _LENT:
                if own.get(k) not in (None, "", []):
                    item[k] = own[k]
        item.update({"stance": "axiom", "provenance": {**_PROV, "sources": [
            f"{where}#L{m['lines'].replace('-', '-L')}" if where else "the class's source, by rule (ast)"]}})
        out.append(item)
    fields = members.get("fields") or []
    if fields:
        shape = ("a record class that cannot change" if members.get("frozen") else "a record class"
                 if members.get("record") else "an object: the names its class declares and those its methods set")
        out.append({"id": f"C:structure/{suffix}", "type": "structure", "name": cls,
                    "summary": f"What {cls} holds: its fields, read from its source by rule, each with its type and "
                               f"kind; a map or a list says what it holds where its type or its filling shows it.",
                    "shape": shape, "fields": [dict(f) for f in fields], "stance": "axiom",
                    "provenance": {**_PROV, "sources": [
                        f"{where}#L{members['lines'].replace('-', '-L')}" if where
                        else "the class's source, by rule (ast)"]}})
    return out


def _source_of(path: Path, vol: mc.Volume, it: mc.Item) -> Path | None:
    """The source file an item read from its source names (`defined-in` its `C:file`), under the folder that fabulac
    was read from; None when it is not there."""
    fi = next((x for x in vol.items.values() if x.id == it.data.get("defined-in")), None)
    rel = fi.data.get("path") if fi is not None else None
    folder = part_folder(path, vol.catalog if isinstance(vol.catalog, dict) else {})
    return folder / rel if isinstance(rel, str) and folder is not None and (folder / rel).is_file() else None


def _provider(iid: str, name: str, vols: list[tuple[Path, mc.Volume]], *, surface: str | None = "class",
              ) -> tuple[Path, mc.Volume, mc.Item, Path | None] | None:
    """The fabulac whose own `C:interface` named by `iid` (the same id, or one `iid` ends with after a prefix such as
    `outside.`) has `defined-in`: the one read from its source; with the item and its source file."""
    for path, vol in vols:
        for it in vol.items.values():
            d = it.data
            if not (it.module == "C" and it.kind == "interface" and isinstance(d.get("defined-in"), str)
                    and (surface is None or d.get("surface") == surface)):
                continue
            mine = it.id.split("/", 1)[1]
            if (it.id == iid or iid.endswith("." + mine)) and str(d.get("name")).rsplit(".", 1)[-1] == name:
                return path, vol, it, _source_of(path, vol, it)
    return None


_CAPS = re.compile(r"\b[A-Z][A-Za-z0-9_]*\b")


def _named_types(item: Mapping[str, Any]) -> list[str]:
    """The upper-case names a stated item's types name (its signature, what it takes and gives, its fields)."""
    texts = [str(item.get("signature") or "")]
    texts += [str(t.get("type") or "") for t in item.get("takes") or [] if isinstance(t, dict)]
    g = item.get("gives")
    texts += [str(g.get("type") or "")] if isinstance(g, dict) else []
    texts += [f"{f.get('type') or ''} {f.get('means') or ''}" for f in item.get("fields") or [] if isinstance(f, dict)]
    return list(dict.fromkeys(n for t in texts for n in _CAPS.findall(t)))


def state_members(interfaces: list[dict], fabulacs: Iterable[Path], *,
                  sources: Mapping[str, Path] | None = None) -> tuple[list[dict], dict[str, int], list[str]]:
    """For each interface of surface `class` among `interfaces`, the items stating its members (`member_items`), read
    from the class's source: `sources[id]` when given, else the fabulac among `fabulacs` that read it (`_provider`).
    A class is reached, and stated with its members, when a stated item's types name it (a function that gives a
    `Volume`, a field that holds `Item`s) and the fabulac that provides that item has the class's own interface,
    in the same prefix (`outside.enough.macrocosm.Volume` beside `outside.enough.macrocosm.load_volume`). Items already
    among `interfaces` are not stated twice. Returns `(items, {class id: members stated}, [class ids whose source could
    not be read])`."""
    known = Fabulacs()
    vols = [(Path(p), v) for p in fabulacs if (v := known.load(Path(p))) is not None]
    have = {str(i.get("id")) for i in interfaces}
    added: list[dict] = []
    counts: dict[str, int] = {}
    unread: list[str] = []
    todo = [i for i in interfaces if i.get("type") == "interface"]
    while todo:
        iface = todo.pop(0)
        iid, name = str(iface["id"]), str(iface.get("name") or "").rsplit(".", 1)[-1]
        is_class = iface.get("surface") == "class"
        hit = _provider(iid, name, vols, surface="class" if is_class else None)
        found: list[dict] = []
        if is_class:
            src = Path(sources[iid]) if sources and iid in sources else (hit[3] if hit else None)
            got = class_members(src, name) if src is not None and src.is_file() else None
            if got is None:
                unread.append(iid)
                continue
            lent: dict[str, dict] = {}
            where = src.name
            if hit is not None:
                path, vol, it, _f = hit
                pre = it.id + "."
                lent = {x.id[len(pre):]: x.data for x in vol.items.values()
                        if x.id.startswith(pre) and "." not in x.id[len(pre):]}
                fi = next((x for x in vol.items.values() if x.id == it.data.get("defined-in")), None)
                where = f"{volume_uri(vol.database)}: {fi.data.get('path')}" if fi is not None else where
            found = [x for x in member_items(iface, got, where=where, lent=lent) if x["id"] not in have]
            have |= {x["id"] for x in found}
            added += found
            counts[iid] = len(found)
        if hit is None:
            continue
        _path, vol, it, _src = hit                       # the classes this one's types name, in its provider
        prefix = iid.split("/", 1)[1][: -len(it.id.split("/", 1)[1])]
        classes = {x.data.get("name"): x for x in vol.items.values()
                   if x.module == "C" and x.kind == "interface" and x.data.get("surface") == "class"
                   and isinstance(x.data.get("defined-in"), str)}
        for n in dict.fromkeys(_named_types(iface) + [t for f in found for t in _named_types(f)]):
            c = classes.get(n)
            if c is None:
                continue
            cid = f"C:interface/{prefix}{c.id.split('/', 1)[1]}"
            if cid in have:
                continue
            new = {"id": cid, "type": "interface",
                   **{k: c.data[k] for k in ("name", "summary", "surface", "signature", "takes", "gives", "raises")
                      if k in c.data},
                   "stance": "axiom",
                   "provenance": {**_PROV, "sources": [f"{volume_uri(vol.database)}/{c.id.replace(':', '/', 1)}",
                                                       f"reached from {iid}, whose types name it"]}}
            new["summary"] = (str(c.data.get("summary") or n).rstrip()
                              + f" Reached from {iid.split('/', 1)[1]}: it passes between the parts with it.")
            have.add(cid)
            added.append(new)
            todo.append(new)
    return added, counts, unread


def make_head(head: Path, parts: Iterable[Path], *, name: str | None = None, licence: Any = None,
              by: str | None = None, at: Any = None, interfaces: Iterable[dict] = (),
              does: Mapping[str, str] | None = None, members: bool = True, providers: Iterable[Path] = (),
              sources: Mapping[str, Path] | None = None) -> dict:
    """Make a head fabulac at `head` from a set of part fabulacs: its catalog (`flavour: fabulac`, the authored
    source, `parts` with each part's URI, path and sha256), an `R:licence`, one `C:component` per part told in it, and
    the `interfaces` given (`C:interface` items, stated once), with, for each class among them, its members
    (`state_members`, over the parts and `providers`, `sources` naming a class's file outright; `members=False`
    states none); and set `head` in each part's catalog (each part's sha256 is taken after). Refuses
    (FileExistsError) a head that is there already, and (ValueError) a part that is not a fabulac, or two parts of
    one database. Returns `{head, uri, parts, members: {class id: items}, unread: [class id]}`."""
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
    given = [dict(i) for i in interfaces]
    stated, counts, unread = (state_members(given, [p for p, _r in rows] + [Path(x) for x in providers],
                                            sources=sources) if members else ([], {}, []))
    nodes += comps + given + stated
    doc = {"oes": "fabula/1", "flavour": "fabulac", "id": f"fabula/{db}", "name": name or stem, "source": src,
           "derived": {"at": f"{day}T00:00:00Z" if len(day) == 10 else day, "by": "person", "mode": "rules",
                       "completeness": "outline", "chunks": 0},
           "parts": [r for _p, r in rows],
           "atem": {"line": f"{name or stem}, told in {len(rows)} parts.", "focus": "its parts and what passes "
                    "between them", "push": "it is too large for one fabulac", "pull": "each part stays small"},
           "nodes": nodes}
    from .dialectic import dump_text
    _write(head, dump_text(doc))
    return {"head": str(head), "uri": me, "parts": [r for _p, r in rows], "members": counts, "unread": unread}


__all__ = ["AGREE", "CHECKS", "Fabulacs", "SEVERITY", "STATES", "class_members", "def_line", "disagreements",
           "function_item", "make_head", "maker_ref", "member_disagreements", "member_items", "part_folder",
           "parts_moved", "plain_kind", "problems", "set_catalog_key", "split_uri", "stamp_parts", "state_members",
           "volume_uri", "which_moved"]
