"""The head fabulam and its parts, by rule: where a fabulam lives, what the host knows before a survey, and how a
part's summary goes upward (0.9; MacroCOSM OES 18.4.10 "A head fabulam and its parts"; Thym 20.13; the design's 4.1,
4.3 and 6).

Nothing here asks a model, and nothing here runs Lean. Four things:

- **Where a fabulam lives** (`home`, `fabulam_path`, `part_path`): beside the folder that holds the source's
  `lean-toolchain` file, never inside a clone; a loose Lean file's, beside the file. A head's parts sit in
  `<name>.fabulam.parts/`, the source's folders mirrored.
- **The catalog alone** (`catalog_alone`): what the host can read from disk and what the person entered, written by
  rule before a survey and handed to it as `survey … with h`: the Lean version the source names (`toolchain`), the
  module, the path, the clone's commit and origin, the licence, the targets, the public wording, and what is said
  about checking and who says it. A move reads a file only as its inputs hold it, so this is how those facts reach
  one. It holds no item.
- **Summaries upward** (`copy_upward`): after a part lands, the head gains, by rule, the part's crossing
  declarations in words (`says`, `quantifiers`, a structure's `fields`, the part's `role-there` and `why-there`),
  the part's component (`does`, `stages`, `counts`, `completeness`) and, from the part that holds a target, its
  yield and its worked example, each with `told-in`.
- **Tying a part in** (`tie_part`, `stamp_parts`): once a part's file is there, the head names it in `parts`
  (`{uri, path, sha256}`) and says `told-in` on its component and its crossing items. A head's survey names no part,
  because `parts-resolve` reads a part from disk.

Every write keeps every byte outside what it changes (`dialectic.write_back`), and lands all at once.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import dialectic as _dl
from . import fabula_names as _names
from . import macrocosm as _mc
from .thym.folder import clone_of
from .thym.moves import proof as _proof

SUFFIX = _names.FABULAM_SUFFIX                         # `.fabulam.cosm`
PARTS_SUFFIX = _names.FABULAM_PARTS_SUFFIX             # `.fabulam.parts`
TOOLCHAIN_FILE = "lean-toolchain"
#: How far above a source the host looks for its `lean-toolchain` file.
LEVELS_UP = 12
#: The catalog's `source` fields the person's entries write, and the checking fields among them.
ENTRIES = ("target", "wording", "obtained", "licence")
SAID = ("said", "said-by", "said-at")
DECL_KINDS = _proof.DECL_KINDS


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    """A fabulam's file as a mapping; `{}` when it is not there or does not read."""
    try:
        data = _mc.yaml_load(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001 - a file that does not read holds nothing
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Where a fabulam lives
# ---------------------------------------------------------------------------

def toolchain_root(source: Path) -> Path | None:
    """The nearest folder at or above a Lean file or folder that holds a `lean-toolchain` file, or None."""
    source = Path(source).absolute()
    cur = source if source.is_dir() else source.parent
    for _ in range(LEVELS_UP):
        if (cur / TOOLCHAIN_FILE).is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def home(source: Path) -> tuple[Path | None, Path]:
    """`(the toolchain's folder or None, the folder a fabulam of this source sits in)`: beside the folder that holds
    `lean-toolchain`, never inside it; a loose file's, beside the file; a loose folder's, beside the folder."""
    source = Path(source).absolute()
    root = toolchain_root(source)
    if root is not None:
        return root, root.parent
    return None, source.parent


def fabulam_path(source: Path, name: str | None = None) -> Path:
    """Where the fabulam of a Lean file or folder lands: `<name>.fabulam.cosm` in its home (`home`). `<name>` is the
    person's, or the source's name respelled by rule."""
    _root, where = home(source)
    return where / _names.fabulam_name(name or _names.fabulam_stem(Path(source).name))


def part_path(head: Path, file_path: str) -> Path:
    """Where the part of one file of a head's folder lands: under `<name>.fabulam.parts/`, the folders mirrored."""
    name = Path(head).name[: -len(SUFFIX)]
    return Path(head).parent / _proof.part_path(name, file_path)


def module_of(source: Path, root: Path | None) -> str:
    """A Lean file's (or folder's) dotted module name: its path below the folder that holds `lean-toolchain`; a
    loose one's, its own name."""
    source = Path(source).absolute()
    rel = source.relative_to(root) if root is not None else Path(source.name)
    parts = list(rel.parts)
    if parts and parts[-1].endswith(".lean"):
        parts[-1] = parts[-1][:-5]
    return ".".join(parts)


def _toolchain(root: Path | None) -> str | None:
    if root is None:
        return None
    try:
        said = (root / TOOLCHAIN_FILE).read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return None
    return said[0].strip() if said and said[0].strip() else None


def _licence_of(root: Path | None) -> str | None:
    """The licence a clone's own licence file names, by the rule the fabulac's survey reads one with."""
    if root is None:
        return None
    from .thym.moves import code as _code
    for p in sorted(root.iterdir()):
        if p.is_file() and not p.is_symlink() and _code.is_licence_file(p.name):
            try:
                return _code.read_licence(p.read_text(encoding="utf-8", errors="replace")).get("identifier")
            except OSError:
                return None
    return None


def catalog_alone(source: Path, *, fab: Path | None = None, name: str | None = None, before: dict | None = None,
                  target: list[str] | None = None, wording: str | None = None, said: str | None = None,
                  said_by: str | None = None, said_at: str | None = None, obtained: str | None = None,
                  licence: str | None = None) -> dict:
    """A fabulam of the catalog alone for a Lean file or a folder of them: what the host reads from disk by rule and
    what the person entered, and no item. An entry left out keeps what the fabulam there before said (`before`, its
    catalog): a target the person gave, the wording, what is said about checking. A target found by rule is not
    carried: the rule finds it again."""
    source = Path(source).absolute()
    root, where = home(source)
    fab = Path(fab) if fab is not None else fabulam_path(source, name)
    stem = name or fab.name[: -len(SUFFIX)]
    old = (before or {}).get("source") if isinstance((before or {}).get("source"), dict) else {}
    try:
        rel = source.relative_to(fab.parent.absolute()).as_posix()
    except ValueError:
        rel = source.name
    src: dict = {"path": rel + ("/" if source.is_dir() else ""), "kind": "folder" if source.is_dir() else "text",
                 "language": "lean"}
    tc = _toolchain(root)
    if tc:
        src["toolchain"] = tc
    src["module"] = module_of(source, root)
    commit, origin = clone_of(root) if root is not None else (None, None)
    if commit:
        src["commit"] = commit
    if origin:
        src["origin"] = origin
    lic = licence or (old.get("licence") if isinstance(old.get("licence"), str) else None) or _licence_of(root)
    if lic:
        src["licence"] = lic
    if obtained or old.get("obtained"):
        src["obtained"] = obtained or old["obtained"]
    kept = old.get("target") if old.get("target-by") == "given" else None
    if target or kept:
        src["target"] = [str(x) for x in (target or kept)]
        src["target-by"] = "given"
    if wording or old.get("wording"):
        src["wording"] = wording or old["wording"]
    was = old.get("checking") if isinstance(old.get("checking"), dict) else {}
    says = {"said": said or was.get("said"), "said-by": said_by or was.get("said-by"),
            "said-at": said_at or was.get("said-at")}
    if says["said"] and says["said-by"]:
        src["checking"] = {k: v for k, v in says.items() if v}
    del where
    return {"oes": "fabula/1", "flavour": "fabulam", "id": f"fabula/{stem}", "name": stem, "source": src,
            "nodes": []}


# ---------------------------------------------------------------------------
# A head read from disk: its files, its parts, where it stands
# ---------------------------------------------------------------------------

def components(head_doc: dict) -> list[dict]:
    """A head's Lean files in the order of the imports, each `{id, name, file (its path in the folder), sha256,
    reached (how many of its declarations the targets reach), told-in, offers}`."""
    nodes = [n for n in head_doc.get("nodes") or [] if isinstance(n, dict)]
    files = {n["id"]: n for n in nodes if str(n.get("id", "")).startswith("C:file/")}
    out = []
    for n in nodes:
        if not str(n.get("id", "")).startswith("C:component/"):
            continue
        f = files.get((n.get("files") or [None])[0]) or {}
        out.append({"id": n["id"], "name": n.get("name"), "file": f.get("path"), "sha256": f.get("sha256"),
                    "module": f.get("module"), "reached": int((n.get("counts") or {}).get("reached") or 0),
                    "told-in": n.get("told-in"), "offers": list(n.get("offers") or []),
                    "completeness": n.get("completeness")})
    return [c for c in out if c["file"]]


def summary(head_doc: dict) -> dict:
    """What a head's card says of its files: `{files, read, unreached}` ("k of n files read; m not reached and left
    as outlines")."""
    comps = components(head_doc)
    return {"files": len(comps), "read": sum(1 for c in comps if c["reached"] and c["completeness"] == "full"),
            "unreached": sum(1 for c in comps if not c["reached"])}


# ---------------------------------------------------------------------------
# Summaries upward, and a part tied in
# ---------------------------------------------------------------------------

def _twin(path: Path) -> Any:
    return _dl.twin_from_text(Path(path).read_bytes().decode("utf-8"), filename=Path(path).name)


def _items(doc: dict) -> list[dict]:
    return [n for n in doc.get("nodes") or [] if isinstance(n, dict)]


def _kind(it: dict) -> str:
    return str(it.get("type") or str(it.get("id", "")).split("/", 1)[0].split(":", 1)[-1])


def _place(doc: dict, part_doc: dict) -> dict | None:
    """The head's component for a part, found by the part's file (its sha256 as the head's survey recorded it)."""
    sha = (part_doc.get("source") or {}).get("sha256")
    return next((c for c in components(doc) if c["sha256"] == sha), None)


def copy_upward(head: Path, part: Path) -> dict:
    """After a part lands, what the head gains from it, by rule (the design's 4.3, step 1). Returns `{crossing: [ids],
    component, yields: [ids], moved: [ids]}`; `moved` lists the crossing declarations whose `digest` in the part is
    not the one the head's survey recorded (the file changed since: survey the folder again)."""
    twin = _twin(head)
    doc = twin.doc
    pdoc = load(part)
    comp = _place(doc, pdoc)
    if comp is None:
        raise ValueError(f"{Path(part).name} is no part of {Path(head).name}: its file is not in the head's survey")
    part_uri = f"oes:{pdoc.get('id')}"
    mine = {it.get("lean"): it for it in _items(pdoc) if _kind(it) in DECL_KINDS and it.get("lean")}
    by_id = {it.get("id"): it for it in _items(doc)}
    out: dict = {"crossing": [], "component": comp["id"], "yields": [], "moved": []}
    for iid in comp["offers"]:
        hit = by_id.get(iid)
        src = mine.get((hit or {}).get("lean"))
        if hit is None or src is None:
            continue
        if hit.get("digest") != src.get("digest"):
            out["moved"].append(iid)
            continue
        for k in ("says", "quantifiers", "fields"):
            if k in src and not _mc.is_pending(src[k]):
                hit[k] = src[k]
        if src.get("role"):
            hit["role-there"] = src["role"]
            if src.get("why"):
                hit["why-there"] = src["why"]
        out["crossing"].append(iid)
    pitems = _items(pdoc)
    stages = {it.get("id"): it for it in pitems if _kind(it) == "part" and it.get("division") == "stage"}
    target = by_id.get(comp["id"])
    if target is not None:
        line = (pdoc.get("atem") or {}).get("line") if isinstance(pdoc.get("atem"), dict) else None
        reached = [it for it in mine.values() if it.get("reached") == "yes"]
        if isinstance(line, str) and line.strip():
            target["does"] = line
        target["stages"] = [str(stages[s].get("name")) for s in pdoc.get("teaching") or [] if s in stages]
        target["counts"] = {"declarations": len(mine), "reached": len(reached),
                            "spine": sum(1 for it in reached if it.get("role") == "spine")}
        target["completeness"] = str((pdoc.get("derived") or {}).get("completeness") or "outline")
    # the yield of each target the part holds, and its worked example, with told-in
    nodes = doc.get("nodes")
    have = {it.get("id") for it in _items(doc)}
    statements = {it.get("id") for it in _items(doc) if _kind(it) == "statement"}
    for y in [it for it in pitems if _kind(it) == "yield" and it.get("of") in statements]:
        st = by_id[y["of"]]
        lines = str((st.get("span") or {}).get("lines") or "1")
        up = {k: v for k, v in y.items() if k not in ("provenance", "made")}
        up["grounds"] = [{"of": y["of"], "lines": lines}]
        up["chooses"] = [{**c, "where": c.get("where") if c.get("where") in have else y["of"]}
                         for c in y.get("chooses") or [] if isinstance(c, dict)]
        up["told-in"] = _proof.item_uri(part_uri, y["id"])
        up["provenance"] = {"mode": "derived", "sources": [up["told-in"]],
                            "confidence": (y.get("provenance") or {}).get("confidence", 0.35), "state": "known"}
        cases = [it for it in pitems if _kind(it) == "case" and it.get("from") == "worked" and it.get("of") == y["id"]]
        for it in [up] + [{**{k: v for k, v in c.items() if k not in ("provenance", "made")},
                           "told-in": _proof.item_uri(part_uri, c["id"]),
                           "provenance": {"mode": "derived", "sources": [_proof.item_uri(part_uri, c["id"])],
                                          "confidence": (c.get("provenance") or {}).get("confidence", 0.35),
                                          "state": "known"}} for c in cases]:
            old = next((i for i, n in enumerate(nodes) if isinstance(n, dict) and n.get("id") == it["id"]), None)
            if old is None:
                nodes.append(it)
            else:
                nodes[old] = it
            out["yields"].append(it["id"])
    if twin.changed:
        _dl.write_atomic(Path(head), twin.render())
    return out


def tie_part(head: Path, part: Path) -> dict:
    """Name a landed part in its head: its entry in `parts` (`{uri, path, sha256}`, the sha256 the part's file has
    now), `told-in` on its component and on the crossing items the part tells. Returns the entry."""
    twin = _twin(head)
    doc = twin.doc
    pdoc = load(part)
    comp = _place(doc, pdoc)
    if comp is None:
        raise ValueError(f"{Path(part).name} is no part of {Path(head).name}: its file is not in the head's survey")
    uri = f"oes:{pdoc.get('id')}"
    rel = Path(part).absolute().relative_to(Path(head).absolute().parent).as_posix()
    entry = {"uri": uri, "path": rel, "sha256": _sha(Path(part))}
    parts = [p for p in doc.get("parts") or [] if isinstance(p, dict) and p.get("uri") != uri]
    order = [_proof.part_uri(str(doc.get("id")), str(c["module"] or c["file"][:-5].replace("/", ".")))
             for c in components(doc)]
    parts.append(entry)
    parts.sort(key=lambda p: order.index(p["uri"]) if p["uri"] in order else len(order))
    mine = {it.get("lean"): it for it in _items(pdoc) if _kind(it) in DECL_KINDS and it.get("lean")}
    for it in _items(doc):
        if it.get("id") == comp["id"]:
            it["told-in"] = uri
        elif it.get("id") in comp["offers"] and it.get("lean") in mine:
            it["told-in"] = _proof.item_uri(uri, str(mine[it["lean"]]["id"]))
    # `parts` sits before the items, where the catalog's other lists do
    if "parts" in doc:
        doc["parts"] = parts
    else:
        nodes = doc.pop("nodes", [])
        doc["parts"] = parts
        doc["nodes"] = nodes
    _dl.write_atomic(Path(head), twin.render())
    return entry


def refresh_neighbours(head: Path, part: Path) -> list[str]:
    """A part's reliances on other parts, told again from the head as it stands: each `gives` is the `says` of the
    head's item it is stated in. A part surveyed before its neighbours were read holds the question of them; this
    answers it, by rule, before the part is read. Returns the ids it changed."""
    hdoc = load(head)
    said = {str(it.get("lean")): it.get("says") for it in _items(hdoc) if _kind(it) in DECL_KINDS}
    twin = _twin(part)
    changed = []
    for it in _items(twin.doc):
        if _kind(it) != "reliance" or not it.get("stated-in"):
            continue
        lean = it.get("lean")
        lean = lean[0] if isinstance(lean, list) and lean else lean
        says = said.get(str(lean))
        if isinstance(says, str) and it.get("gives") != says:
            it["gives"] = says
            changed.append(str(it.get("id")))
    if changed:
        _dl.write_atomic(Path(part), twin.render())
    return changed


def stamp_parts(head: Path) -> list[dict]:
    """Each part's sha256 in the head's `parts`, written again from the files as they are now. Returns the entries."""
    twin = _twin(head)
    parts = [p for p in twin.doc.get("parts") or [] if isinstance(p, dict)]
    for p in parts:
        f = Path(head).parent / str(p.get("path"))
        if f.is_file():
            p["sha256"] = _sha(f)
    if twin.changed:
        _dl.write_atomic(Path(head), twin.render())
    return parts


__all__ = ["ENTRIES", "PARTS_SUFFIX", "SAID", "SUFFIX", "TOOLCHAIN_FILE", "catalog_alone", "components",
           "copy_upward", "fabulam_path", "home", "load", "module_of", "part_path", "refresh_neighbours",
           "stamp_parts", "summary", "tie_part", "toolchain_root"]
