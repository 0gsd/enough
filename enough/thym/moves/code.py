"""The fabulac moves: a folder of Python decompiled into a fabulac, and a fabulac compiled back into a cshort and its
catems (THYM 6.3, 7.3, 20; MacroCOSM OES 18.4.1, 18.4.7, 18.4.8).

- `survey repo` (rules only): the outline. A `C:file` per file the folder rule keeps, a `C:component` per module and
  package, a `C:interface` per public function, class, method and command line with its exact signature, a
  `C:dependency` per import from outside the tree and per declared requirement, a `C:setting` per environment variable
  read, command-line option and module constant, the licence (`source.licence` and an `R:licence`) and the means.
- `history repo with f` (rules only): the clone's commits as changes, grouped into episodes, its tags as releases, its
  authors as makers (roles and counts; a name only where the repository's own licence or authors file states it).
- `derive t as code with f` (asks, once per file): that file's behaviours, structures, cases, terms, concepts, claims
  and events, read against the outline.
- `derive repo with f` (asks): the fold, aims, audience, uses, requirements, decisions, exclusions, inspiration and
  the atem, each grounded in what the fabulac and the documents hold.
- `tell f as code` (asks, once per file): the cshort, a folder with `CSHORT.md`; `tell f as line | overview | manual`:
  the catem at that depth.

`emf.py`'s `derive` and `tell` reach the four asking branches here; `survey` and `history` are declared with their
own `code:`. The checks of THYM 7.3 these moves keep are registered here: `files-found`, `code-span`,
`licence-recorded`, `outline-cited`, `fold-grounded`, `history-grounded`, `parses`, `interfaces-present`,
`files-present`, `uses-told`, `flavour`, and the code readings of `coverage`, `footer` and `atem-shape` that
`emf.py`'s checks hand on to.

**Nothing in a repository is run.** The moves read a folder only as the folder value holds it (in a replay, its
snapshot), and reach anything else only through `ctx.engines`: `repo` (a clone's history and MacroCOSM's file
counts) and `syntax` (a file's outline, a parse, a packaging file), which the host provides and the runtime records,
so that a replay needs neither the repository, nor git, nor a parser. Without those engines a move refuses, saying
which engine is missing. Nothing told is run either: `parses` and `interfaces-present` read the syntax engine's
answers about the cshort's text.

Standalone: the standard library, PyYAML and the MacroCOSM reader the package already uses.
"""
from __future__ import annotations

import copy
import hashlib
import re
import tomllib
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import CHECKS as _CHECKS
from enough.thym.checks import check
from enough.thym.folder import Folder, digest_of, lines_in, path_key
from enough.thym.moves import (LADDER, MoveError, answer_mapping, engine, fabula_doc, fold, item_kind, model_of,
                               short_value, telling_of, utc_day, words_in)
from enough.thym.registry import Request, implements
from enough.thym.values import Value, plain

#: The band this edition reads (THYM 20.6, MacroCOSM OES 18.4.7): pure Python a person could read in an afternoon.
BAND_FILES = 60
BAND_LINES = 6000
#: A file longer than this is read in chunks, cut at a top-level definition (one request each).
CHUNK_LINES = 600
#: What a rules pass says it has not read (MacroCOSM OES 18.4.3).
NOT_READ = "a model has not read this file"
NOT_FOLDED = "a model has not read this program as a whole"
CATEM_DEPTHS = ("line", "overview", "manual")
READ_KINDS = {"behaviours": ("C", "behaviour"), "structures": ("C", "structure"), "cases": ("P", "case"),
              "terms": ("L", "term"), "concepts": ("K", "concept"), "claims": ("P", "claim"),
              "events": ("T", "event")}
FOLD_KINDS = {"aims": ("N", "aim"), "audiences": ("N", "audience"), "uses": ("N", "use"),
              "requirements": ("N", "requirement"), "decisions": ("N", "decision"),
              "exclusions": ("N", "exclusion"), "influences": ("I", "influence"), "occasions": ("I", "occasion")}
#: The ceiling a model's own judgement may claim, by stance (MacroCOSM OES 18.4.3: an opinion at most 0.5).
CONFIDENCE_CAP = {"observed": 0.9, "deduced": 0.7, "opinion": 0.5, "assumed": 0.3, "hearsay": 0.5, "axiom": 0.9}
REF_FIELDS = ("of", "defined-in", "for", "via", "met-by", "checked-by", "by", "changed-in", "agent", "patient",
              "before", "after", "defined-by", "component", "files", "exposes", "uses", "used-by", "read-by",
              "touches", "release", "phase", "changes", "who")
_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._@-]*[A-Za-z0-9_@-])?$")
_SLUG_BAD = re.compile(r"[^a-z0-9-]")
_ID = re.compile(r"^([A-Z]):([a-z][a-z0-9-]*)/(.+)$")
_LOC = re.compile(r"^(?P<path>[^#\s]+)#L(?P<a>\d+)(?:-L?(?P<b>\d+))?$")


# ---------------------------------------------------------------------------
# Small things every move here shares
# ---------------------------------------------------------------------------

def _yaml(x: Any) -> str:
    """Plain data as YAML for a model to read: block style, keys in their order, any top level."""
    import yaml
    return yaml.safe_dump(plain(x), sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None)


def slug(text: str) -> str:
    """The Canon rule (MacroCOSM OES 18.3.3): `/` → `--`, `.` → `-`, lowercased, anything outside `a-z0-9-` → `-`,
    a hyphen at either end trimmed; nothing left takes the first six hex digits of the text's sha256."""
    s = _SLUG_BAD.sub("-", text.replace("/", "--").replace(".", "-").lower()).strip("-")
    return s or hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]


def name_slug(dotted: str) -> str:
    """A Python name's slug: its dotted name (`tally.cli.main`) when the id grammar takes it, else the Canon rule."""
    return dotted if _SLUG.match(dotted) else slug(dotted)


def stamp_at(ctx: Any) -> str:
    now = getattr(ctx, "now", None)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ") if now is not None else "1970-01-01T00:00:00Z"


def prov(sources: list, confidence: Any = 1, state: str = "known") -> dict:
    return {"mode": "derived", "sources": [str(s) for s in sources if s], "confidence": confidence, "state": state}


def loc(path: str, a: int | None = None, b: int | None = None) -> str:
    if not a:
        return path
    return f"{path}#L{a}" if not b or b == a else f"{path}#L{a}-L{b}"


def span(path: str, a: int, b: int | None = None) -> dict:
    return {"file": path, "lines": f"{a}" if not b or b == a else f"{a}-{b}"}


def is_test(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    return (any(p in ("tests", "test", "testing") for p in parts[:-1]) or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


#: Folders whose Python is the repository's own tooling (documentation builds, release scripts, examples), not the
#: program: no component, no interface, no dependency of the program, and no file of a cshort.
TOOLING_DIRS = ("docs", "doc", "dev", "scripts", "tools", "examples", "example", "benchmarks", "bench", ".github")


def is_tooling(path: str) -> bool:
    return "/" in path and path.split("/", 1)[0] in TOOLING_DIRS


def is_readme(path: str) -> bool:
    return "/" not in path and re.match(r"(?i)^readme(\.(md|rst|txt|markdown))?$", path) is not None


def is_licence_file(path: str) -> bool:
    return "/" not in path and re.match(r"(?i)^(licen[cs]e|copying|unlicense)([.-].*)?$", path) is not None


def is_packaging(path: str) -> bool:
    return "/" not in path and (path in ("pyproject.toml", "setup.cfg")
                                or re.fullmatch(r"requirements[\w.-]*\.txt", path) is not None)


def _folder_of(v: Value, what: str) -> Folder:
    if not isinstance(v, Value) or not isinstance(v.payload, Folder):
        raise MoveError(f"{what} reads a folder, not a {getattr(v, 'type', 'value')}")
    return v.payload


def _fabula(v: Any, what: str) -> tuple[dict, list[dict]]:
    """A fabulac's catalog and items, as plain mappings; a MoveError in the program's words for anything else."""
    if not isinstance(v, Value) or v.type != "fabula":
        raise MoveError(f"{what}")
    cat, items = fabula_doc(v)
    cat = {k: plain(x) for k, x in cat.items() if k != "nodes"}
    return cat, [plain(it) for it in items]


def flavour_of(cat: dict) -> str:
    f = cat.get("flavour")
    return f if isinstance(f, str) and f else "fabulan"


def _need_fabulac(cat: dict, name: str, what: str) -> None:
    fl = flavour_of(cat)
    if fl != "fabulac":
        said = {"fabulap": "a poem's fabula", "fabulan": "the fabula of a text"}.get(fl, "not a fabulac")
        raise MoveError(f"{name} is a {fl}, {said}; {what}")


def _by_id(items: list[dict]) -> dict[str, dict]:
    return {str(it.get("id")): it for it in items if isinstance(it, dict) and it.get("id")}


def _refs(it: Any) -> list[str]:
    """Every id an item points at: its reference fields, its links, its roles (MacroCOSM OES 18.4.2)."""
    out: list[str] = []

    def add(v: Any) -> None:
        if isinstance(v, str) and _ID.match(v):
            out.append(v.split("#", 1)[0])
        elif isinstance(v, list):
            for x in v:
                add(x)
        elif isinstance(v, dict) and isinstance(v.get("to"), str):
            add(v["to"])
    if not isinstance(it, dict):
        return out
    for k in REF_FIELDS:
        add(it.get(k))
    for ln in it.get("links") or []:
        add(ln)
    roles = it.get("roles")
    if isinstance(roles, dict):
        for v in roles.values():
            add(v)
    return out


def _file_items(items: list[dict]) -> dict[str, dict]:
    return {str(it.get("path")): it for it in items if item_kind(it) == "file" and it.get("path")}


def _defined_in_path(it: dict, files_by_id: dict[str, dict]) -> str | None:
    f = files_by_id.get(str(it.get("defined-in") or ""))
    return str(f.get("path")) if f else None


def module_name(path: str, top: set[str]) -> str:
    """A Python file's dotted module name: its path without `.py`, `/` as `.`, `__init__` dropped, a leading `src`
    dropped when `src` is no package of its own."""
    p = path[:-3] if path.endswith(".py") else path
    parts = [x for x in p.split("/") if x]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if parts and parts[0] == "src" and "src" not in top:
        parts = parts[1:]
    return ".".join(parts) or "__init__"


# ---------------------------------------------------------------------------
# The licence (MacroCOSM OES 18.4.7, "The source folder and its licence")
# ---------------------------------------------------------------------------

_LICENCES = (
    ("MIT", ("permission is hereby granted, free of charge",)),
    ("Apache-2.0", ("apache license", "version 2.0")),
    ("AGPL-3.0", ("gnu affero general public license",)),
    ("LGPL-3.0", ("gnu lesser general public license", "version 3")),
    ("LGPL-2.1", ("gnu lesser general public license", "version 2.1")),
    ("GPL-3.0", ("gnu general public license", "version 3")),
    ("GPL-2.0", ("gnu general public license", "version 2")),
    ("MPL-2.0", ("mozilla public license", "2.0")),
    ("BSD-3-Clause", ("redistribution and use in source and binary forms", "neither the name")),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",)),
    ("ISC", ("permission to use, copy, modify, and/or distribute this software for any purpose",)),
    ("Unlicense", ("this is free and unencumbered software released into the public domain",)),
)
_SPDX_LINE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)")
_COPYRIGHT = re.compile(r"(?i)copyright\s*(?:\(c\)|©)?\s*((?:\d{4}\s*[-–,]\s*)*\d{4})[,\s]+(.+?)\s*$")


def read_licence(text: str) -> dict:
    """What a licence file says: `{identifier, first-line, holder, year, lines}`, the identifier only when the text
    is one this rule knows (never a guess)."""
    low = " ".join(text.lower().split())
    out: dict = {}
    m = _SPDX_LINE.search(text)
    if m:
        out["identifier"] = m.group(1)
    else:
        for ident, needles in _LICENCES:
            if all(n in low for n in needles):
                out["identifier"] = ident
                break
    lines = text.splitlines()
    first = next((ln.strip() for ln in lines if ln.strip()), "")
    if first:
        out["first-line"] = first[:200]
    for i, ln in enumerate(lines[:40], 1):
        c = _COPYRIGHT.search(ln)
        if c and not c.group(2).lower().startswith(("holder", "<", "[")):
            out["year"] = c.group(1)
            holder = re.sub(r"<[^>]*>|\([^)]*@[^)]*\)|\S+@\S+", "", c.group(2))   # never an address
            out["holder"] = " ".join(holder.split()).rstrip(".,; ").strip()[:120]
            out["line"] = i
            break
    out["lines"] = lines_in(text)
    return out


def _licence_from_packaging(manifests: dict[str, dict]) -> tuple[str | None, str | None]:
    for path, m in manifests.items():
        lic = m.get("licence") if isinstance(m, dict) else None
        if isinstance(lic, str) and lic.strip():
            return lic.strip(), path
        cls = m.get("licence_classifier") if isinstance(m, dict) else None
        if isinstance(cls, str):
            for ident, word in (("MIT", "MIT License"), ("Apache-2.0", "Apache Software License"),
                                ("BSD-3-Clause", "BSD License"), ("GPL-3.0", "GPLv3"), ("ISC", "ISC License")):
                if word in cls:
                    return ident, path
    return None, None


# ---------------------------------------------------------------------------
# survey: the outline (THYM 20.6, rules only)
# ---------------------------------------------------------------------------

def _usage(prog: str, args: list[dict], sub: dict | None = None, subs: list[str] | None = None) -> str:
    """A command's usage line as argparse would print it, built from the arguments as written."""
    parts = [prog, "[-h]"]
    pos = []
    for a in args:
        names = a.get("names") or []
        if not names:
            continue
        nargs = str(a.get("nargs") or "")
        if names[0].startswith("-"):
            opt = max(names, key=len) if any(n.startswith("--") for n in names) else names[0]
            flag = str(a.get("action") or "") in ("store_true", "store_false", "version", "count", "help",
                                                  "store_const")
            meta = a.get("metavar") or str(a.get("dest") or opt.lstrip("-")).upper().replace("-", "_")
            one = opt if flag else f"{opt} {meta}"
            parts.append(one if str(a.get("required") or "") == "True" else f"[{one}]")
        else:
            n = names[0]
            pos.append(f"[{n}]" if nargs == "?" else f"[{n} ...]" if nargs == "*" else
                       f"{n} [{n} ...]" if nargs == "+" else n)
    if subs:
        pos.append("{" + ",".join(subs) + "} ...")
    return " ".join(parts + pos)


def _takes_of_args(args: list[dict]) -> list[dict]:
    out = []
    for a in args:
        names = a.get("names") or []
        if not names:
            continue
        name = max(names, key=len) if names[0].startswith("-") else names[0]
        row: dict = {"name": name}
        act = str(a.get("action") or "")
        if a.get("type"):
            row["type"] = str(a["type"])
        elif act in ("store_true", "store_false"):
            row["type"] = "flag"
        if a.get("default") is not None:
            row["default"] = str(a["default"])
        if not names[0].startswith("-"):
            row["required"] = str(a.get("nargs") or "") not in ("?", "*")
        elif str(a.get("required") or "") == "True":
            row["required"] = True
        if a.get("help"):
            row["means"] = str(a["help"])
        elif act == "version":
            row["means"] = "print the version and exit"
        if a.get("choices"):
            row["means"] = (row.get("means", "") + f" (one of {a['choices']})").strip()
        if a.get("metavar"):
            row["metavar"] = str(a["metavar"])
        out.append(row)
    return out


def _params_takes(params: list[dict], method: bool) -> list[dict]:
    out = []
    for i, p in enumerate(params or []):
        if method and i == 0 and p.get("name") in ("self", "cls"):
            continue
        row: dict = {"name": ("*" if p.get("kind") == "var-positional" else
                              "**" if p.get("kind") == "var-keyword" else "") + str(p.get("name"))}
        if p.get("annotation"):
            row["type"] = p["annotation"]
        if "default" in p:
            row["default"] = p["default"]
        row["required"] = "default" not in p and p.get("kind") not in ("var-positional", "var-keyword")
        out.append(row)
    return out


def _public(name: str, names_all: list | None) -> bool:
    if names_all is not None:
        return name in names_all
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


class _Outline:
    """The outline being built: items by id in the order they were made."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, it: dict) -> dict:
        iid = it["id"]
        if iid in self.items:
            n = 2
            while f"{iid}-{n}" in self.items:
                n += 1
            it["id"] = f"{iid}-{n}"
        self.items[it["id"]] = it
        return it


def _component(o: _Outline, mod: str, path: str, file_id: str, doc: str | None, n_lines: int = 0) -> str:
    cid = f"C:component/{name_slug(mod)}"
    if cid not in o.items:
        it = {"id": cid, "type": "component", "name": mod,
              "summary": f"The Python module {mod}" + (f": {doc}" if doc else "."), "stance": "observed",
              "files": [file_id], "does": {"pending": f"what is {mod} responsible for? ({NOT_READ})"}}
        if n_lines:
            it["span"] = span(path, 1, n_lines)
        it["provenance"] = prov([path])
        o.add(it)
    else:
        o.items[cid].setdefault("files", []).append(file_id)
    return cid


@implements("survey")
def survey(ctx: Any, repo: Value, **_: Any) -> Value:
    """A folder of Python read by its syntax into a fabulac outline (THYM 6.3, 20.6), nothing run or imported."""
    f = _folder_of(repo, "survey")
    py = [e for e in f.texts() if e.suffix == "py"]
    if not py:
        raise MoveError("there is no Python file here: this edition builds a fabulac of Python only")
    if len(py) > BAND_FILES:
        raise MoveError("more than sixty Python files: past what this build reads")
    if sum(lines_in(f.text(e.path)) for e in py) > BAND_LINES:
        raise MoveError("more than six thousand lines of Python: past what this build reads")
    syn, rp = engine(ctx, "syntax"), engine(ctx, "repo")
    counts = rp.tree(repo)
    if counts.get("tree") != f.tree:
        raise MoveError(f"{f.path} changed while it was surveyed: its tree is now {str(counts.get('tree'))[:12]}…")
    paths = [e.path for e in f.entries]
    slugs = _file_slugs(paths)
    top = {p.split("/", 1)[0] for p in paths if p.endswith("/__init__.py") and p.count("/") == 1}
    outlines = {e.path: syn.outline(e.path, f.text(e.path)) for e in py}
    manifests = {e.path: syn.manifest(e.path, f.text(e.path)) for e in f.texts() if is_packaging(e.path)}
    manifests = {p: m for p, m in manifests.items() if isinstance(m, dict) and m.get("ok")}
    o = _Outline()
    file_ids = {p: f"C:file/{slugs[p]}" for p in paths}
    mods = {e.path: module_name(e.path, top) for e in py}
    internal = set(mods.values()) | {m.split(".", 1)[0] for m in mods.values()}
    # -- files
    for e in f.entries:
        o.add(_file_item(f, e, file_ids[e.path], outlines.get(e.path)))
    # -- components, interfaces, settings
    scripts = [s for m in manifests.values() for s in m.get("scripts") or []]
    reached = _reached_names(outlines, mods)
    for e in py:
        _survey_module(o, f, e.path, outlines[e.path], file_ids, mods, scripts, reached.get(mods[e.path], set()))
    # packages: a package component per folder holding an __init__.py, the modules `of` it
    for e in py:
        if e.path.endswith("__init__.py"):
            pkg = mods[e.path]
            for p2, m2 in mods.items():
                cid = f"C:component/{name_slug(m2)}"
                if m2 != pkg and m2.rsplit(".", 1)[0] == pkg and cid in o.items:
                    o.items[cid]["of"] = f"C:component/{name_slug(pkg)}"
    # -- dependencies
    req_python = next((m.get("requires_python") for m in manifests.values() if m.get("requires_python")), None)
    _survey_dependencies(o, outlines, mods, internal, manifests, req_python)
    # -- the licence and the means
    licence = _survey_licence(o, f, manifests)
    _survey_means(o, manifests, req_python, outlines)
    src: dict = {"path": f"{f.name}/", "kind": "folder", "language": "python", "files": counts["files"],
                 "bytes": counts["bytes"], "skipped": counts["skipped"], "tree": f.tree}
    if f.commit:
        src["commit"] = f.commit
    if f.origin:
        src["origin"] = f.origin
    src["licence"] = licence
    at = stamp_at(ctx)
    run = {"program": _program(ctx), "run": getattr(ctx, "run", None), "at": at}
    cat = {"oes": "fabula/1", "macrocosm": mc.MACROCOSM_VERSION, "flavour": "fabulac", "id": f"fabula/{slug(f.name)}",
           "name": f.name, "source": src,
           "derived": {"at": at, "by": "person", **({"program": run["program"]} if run["program"] else {}),
                       **({"run": run["run"]} if run["run"] else {}), "mode": "rules", "completeness": "outline",
                       "chunks": 0, "runs": [{k: v for k, v in run.items() if v}]},
           "atem": {k: {"pending": f"{NOT_FOLDED}: what is its {k}?"} for k in ("line", "focus", "push", "pull")},
           "nodes": [_prov_last(it) for it in o.items.values()]}
    return Value("fabula", cat)


def _import_target(imp: dict, mod: str, path: str) -> str:
    """The dotted module an import names, a relative one resolved against the importing module."""
    m = str(imp.get("module") or "")
    level = int(imp.get("level") or 0)
    if not level:
        return m
    base = mod.split(".")
    pkg = ".".join(base[:len(base) - level + (1 if path.endswith("__init__.py") else 0)])
    return f"{pkg}.{m}" if m and pkg else (m or pkg)


def _reached_names(outlines: dict, mods: dict) -> dict[str, set[str]]:
    """For each module of the tree, the names other modules of the tree and the tests import from it by name
    (`from .keys import _hashkey`, `from vulture.noqa import _parse_error_codes`): a caller reaches them, public or
    not."""
    known = set(mods.values())
    out: dict[str, set[str]] = {}
    for path, ol in outlines.items():
        if not isinstance(ol, dict) or not ol.get("ok"):
            continue
        mod = mods[path]
        for imp in ol.get("imports") or []:
            target = _import_target(imp, mod, path)
            if target in known and target != mod:
                out.setdefault(target, set()).update(n for n in imp.get("names") or [] if n != "*")
    return out


def _prov_last(it: dict) -> dict:
    """An item with its provenance written last, as every example of the text writes it."""
    if "provenance" in it:
        it = {**{k: v for k, v in it.items() if k != "provenance"}, "provenance": it["provenance"]}
    return it


def _program(ctx: Any) -> str | None:
    p = getattr(ctx, "program", None)
    if p is None:
        return None
    return getattr(p, "name", None) or str(p).replace("\\", "/").rsplit("/", 1)[-1]


def _file_slugs(paths: list[str]) -> dict[str, str]:
    base = {p: slug(p) for p in paths}
    seen: dict[str, int] = {}
    for s in base.values():
        seen[s] = seen.get(s, 0) + 1
    return {p: (f"{s}-{hashlib.sha256(p.encode('utf-8')).hexdigest()[:6]}" if seen[s] > 1 else s)
            for p, s in base.items()}


def _holds(path: str, ol: dict | None, binary: bool) -> Any:
    if binary:
        return "binary data, never read as text"
    if ol is not None:
        if ol.get("ok") is False:
            return {"pending": f"it does not parse as Python: line {ol.get('line')}: {ol.get('message')}"}
        names = [d["name"] for d in ol.get("defs") or [] if d.get("kind") != "method"]
        names += [c["name"] for c in ol.get("constants") or [] if c["name"].isupper() or c["name"] == "__version__"]
        if is_test(path):
            return "tests"
        if is_tooling(path):
            return f"the repository's own tooling ({path.split('/', 1)[0]}/), not part of the program"
        if names:
            s = ", ".join(names)
            return s if len(s) <= 300 else s[:299] + "…"
        if ol.get("main"):
            return "the code run when the module is run directly"
        return ol.get("doc") or "no definitions"
    name = path.rsplit("/", 1)[-1].lower()
    if is_readme(path):
        return "the user's introduction"
    if is_licence_file(path):
        return "the licence"
    if re.match(r"(changes|changelog|history|news)", name):
        return "the change log"
    if is_packaging(path) or name in ("setup.py", "manifest.in"):
        return "packaging metadata"
    return "documentation" if name.endswith((".md", ".rst", ".txt")) else "a file the program carries"


def _file_item(f: Folder, e: Any, fid: str, ol: dict | None) -> dict:
    lang = "binary" if e.binary else _language(e.path)
    it: dict = {"id": fid, "type": "file", "name": e.path}
    holds = _holds(e.path, ol, e.binary)
    doc = ol.get("doc") if isinstance(ol, dict) else None
    if e.binary:
        summary = f"{e.path}, a binary file of {e.size} bytes."
    elif doc:
        summary = f"{e.path}: {doc}"
    elif isinstance(holds, str):
        summary = f"{e.path}: {holds}."
    else:
        summary = f"{e.path}, a {lang} file."
    it.update({"summary": summary, "stance": "observed", "path": e.path, "language": lang, "holds": holds})
    length: dict = {"bytes": e.size}
    if not e.binary:
        length = {"lines": lines_in(f.text(e.path)), "bytes": e.size}
    it["length"] = length
    if length.get("lines"):
        it["span"] = span(e.path, 1, length["lines"])
    it["sha256"] = e.sha256
    if isinstance(ol, dict) and (ol.get("main") or e.path.endswith("__main__.py")):
        it["entry"] = True
    it["provenance"] = prov([e.path])
    return it


_LANG = {"py": "python", "pyi": "python", "md": "markdown", "rst": "restructuredtext", "txt": "text", "toml": "toml",
         "cfg": "ini", "ini": "ini", "json": "json", "yaml": "yaml", "yml": "yaml", "sh": "shell", "html": "html",
         "css": "css", "js": "javascript", "in": "text"}


def _language(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return "text"
    return _LANG.get(name.rsplit(".", 1)[1].lower(), "other")


def _base_names(d: dict) -> list[str]:
    return [re.sub(r"\[.*$", "", str(b)).rsplit(".", 1)[-1] for b in d.get("bases") or []]


def _chosen(ol: dict, reached: set[str]) -> dict[str, tuple[bool, str | None]]:
    """The definitions of a module the outline names as interfaces: `{qual: (exported, why)}`. Public ones (in
    `__all__` when there is one, else no leading underscore; dunder methods count), and three kinds a caller reaches
    though they are not public: a name another module of the tree or a test imports, a private class a public class
    inherits from (its public methods are the subclass's), and the classes nested in a chosen class."""
    names_all = ol.get("all")
    defs = ol.get("defs") or []
    top = {str(d["qual"]): d for d in defs if "." not in str(d["qual"])}
    out: dict[str, tuple[bool, str | None]] = {}
    for q, d in top.items():
        if _public(d["name"], names_all):
            out[q] = (names_all is None or d["name"] in names_all, None)
        elif d["name"] in reached:
            out[q] = (False, "it is not public, but other modules of the tree or its tests import it")
    grew = True
    while grew:                                     # private bases of chosen classes, and their bases in turn
        grew = False
        for q in list(out):
            for b in _base_names(top.get(q, {})):
                if b in top and top[b].get("kind") == "class" and b not in out:
                    out[b] = (False, f"it is private, and {q} inherits its methods")
                    grew = True
    for d in defs:                                  # nested classes and methods, in order (outer before inner)
        q = str(d["qual"])
        if "." not in q:
            continue
        owner = q.rsplit(".", 1)[0]
        if owner not in out:
            continue
        if _public(d["name"], None) or d["name"] in reached:
            out[q] = (out[owner][0], None)
    return out


def _notes(d: dict, why: str | None) -> list[str]:
    """What the outline says of a definition beyond its signature, in plain words."""
    notes = []
    if why:
        notes.append(f"Not exported: {why}.")
    if d.get("cond"):
        notes.append(f"Defined only under `{d['cond']}`.")
    if d.get("overloads"):
        notes.append("Typed by overloads: " + "; ".join(f"`{s}`" for s in d["overloads"]) + ".")
    if d.get("attrs"):
        notes.append("Class attributes: " + "; ".join(f"`{a['name']} = {a['value']}`" for a in d["attrs"]) + ".")
    if d.get("setter") or d.get("deleter"):
        notes.append("A property that can also be " + " and ".join(
            w for w, k in (("set", "setter"), ("deleted", "deleter")) if d.get(k)) + ".")
    return notes


def _docstring_items(o: _Outline, d: dict, mod: str, path: str, iid: str) -> None:
    """What a public definition's docstring says beyond its first paragraph (its arguments, returns, raises, notes),
    as a behaviour in the docstring's words, and each doctest example in it as a case, exactly as written: the
    behaviour a rebuild must keep, read by rules, whatever a model later makes of the code."""
    sp, src = span(path, d["line"], d.get("end")), [loc(path, d["line"], d.get("end"))]
    base = f"{name_slug(mod + '.' + str(d['qual']))}"
    if d.get("docstring"):
        o.add({"id": f"C:behaviour/{base}.doc", "type": "behaviour", "name": f"What the docstring of {d['qual']} says",
               "summary": f"The docstring of {d['qual']} of {mod}, as written.", "stance": "observed", "of": [iid],
               "when": f"{d['qual']} is used", "does": d["docstring"], "span": sp, "provenance": prov(src)})
    for n, ex in enumerate(d.get("examples") or [], 1):
        o.add({"id": f"P:case/{base}.example-{n}", "type": "case", "name": f"Example {n} of {d['qual']}",
               "summary": f"A doctest example in the docstring of {d['qual']}, as written (never run here).",
               "stance": "observed", "of": [iid], "given": {"calls": ex["source"].splitlines()},
               "expect": {"value": ex["want"]}, "span": sp, "provenance": prov(src)})


def _decorated(d: dict) -> str:
    """The definition's line with its decorators before it, on one line: `@property def maxsize(self)`."""
    decs = d.get("decorators") or []
    return " ".join([f"@{x}" for x in decs] + [str(d.get("signature"))])


def _survey_module(o: _Outline, f: Folder, path: str, ol: dict, file_ids: dict, mods: dict, scripts: list,
                   reached: set[str] | None = None) -> None:
    if not isinstance(ol, dict) or not ol.get("ok") or is_test(path) or is_tooling(path):
        return
    mod = mods[path]
    fid = file_ids[path]
    o.items[fid]["component"] = cid = _component(o, mod, path, fid, ol.get("doc"), int(ol.get("lines") or 0))
    entry = _entry_function(ol, mod, scripts)
    names_all = ol.get("all")
    exposes: list[str] = []
    chosen = _chosen(ol, reached or set())
    named = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", " ".join(str(d.get("signature")) for d in ol.get("defs") or []
                                                            if str(d.get("qual")) in chosen)))
    for d in ol.get("defs") or []:
        kind = d.get("kind")
        qual = str(d.get("qual"))
        if qual not in chosen:
            continue
        exported, why = chosen[qual]
        surface = {"function": "function", "class": "class", "method": "method"}[kind]
        iid = f"C:interface/{name_slug(f'{mod}.{qual}')}"
        summary = " ".join([d.get("doc") or f"The {surface} {qual} of {mod}."] + _notes(d, why))
        it: dict = {"id": iid, "type": "interface", "name": qual,
                    "summary": summary, "stance": "observed",
                    "surface": surface, "signature": _decorated(d), "defined-in": fid}
        if kind != "class":
            takes = _params_takes(d.get("params") or [], kind == "method")
            if takes:
                it["takes"] = takes
            if d.get("returns"):
                it["gives"] = {"type": d["returns"]}
            raises = _raises(d)
            if raises:
                it["raises"] = raises
        it["exported"] = exported
        it["span"] = span(path, d["line"], d.get("end"))
        it["provenance"] = prov([loc(path, d.get("line"), d.get("end"))])
        o.add(it)
        exposes.append(it["id"])
        _docstring_items(o, d, mod, path, it["id"])
        if kind == "class" and d.get("shape"):
            o.add(_structure(d, mod, path, fid))
    if exposes:
        o.items[cid]["exposes"] = exposes
    owners = {str(d.get("qual")): f"C:interface/{name_slug(mod + '.' + str(d.get('qual')))}"
              for d in ol.get("defs") or []}
    # -- environment variables
    for env in ol.get("env") or []:
        key = env["key"]
        reader = owners.get(str(env.get("in") or ""))
        sid = f"C:setting/env.{name_slug(key)}"
        if sid in o.items:
            if reader and reader in o.items:
                rb = o.items[sid].setdefault("read-by", [])
                if reader not in rb:
                    rb.append(reader)
            continue
        it = {"id": sid, "type": "setting", "name": key, "summary": f"The environment variable {key}, read by {mod}.",
              "stance": "observed", "key": key, "set-in": "environment"}
        if env.get("default") is not None:
            it["default"] = env["default"]
        if reader and reader in o.items:
            it["read-by"] = [reader]
        it["span"] = span(path, env["line"])
        it["provenance"] = prov([loc(path, env["line"])])
        o.add(it)
    # -- module constants: a value that shapes behaviour, by convention in capitals; a type alias the module names
    for c in ol.get("constants") or []:
        name = c["name"]
        listed = names_all is not None and name in names_all
        if c.get("literal") is False:
            if c.get("alias") and (listed or name in named or (names_all is None and not name.startswith("_"))):
                o.add({"id": f"C:structure/{name_slug(f'{mod}.{name}')}", "type": "structure", "name": name,
                       "summary": f"The type {name} of {mod}: {c['value']}." + (
                           f" Defined only under `{c['cond']}`." if c.get("cond") else ""),
                       "stance": "observed", "defined-in": fid, "shape": f"a type alias: {c['value']}",
                       "span": span(path, c["line"]), "provenance": prov([loc(path, c["line"])])})
                continue
            if not (re.fullmatch(r"_?[A-Z][A-Z0-9_]*", name) or listed or name in (reached or ())):
                continue
        else:
            message = c["value"][:1] in "\"'" and len(words_in(c["value"])) >= 3
            if not (re.fullmatch(r"_?[A-Z][A-Z0-9_]*", name) or name == "__version__" or message or listed
                    or not name.startswith("_") or name in (reached or ())):
                continue
        said = f"set to {c['value']}" + (f" under `{c['cond']}`" if c.get("cond") else "")
        for alt in c.get("also") or []:
            said += f"; to {alt['value']}" + (f" under `{alt['cond']}`" if alt.get("cond") else "")
        it = {"id": f"C:setting/{name_slug(f'{mod}.{name}')}", "type": "setting", "name": name,
              "summary": f"The constant {name} of {mod}, {said}." + (" It is exported." if listed else ""),
              "stance": "observed", "key": name,
              "set-in": "constant", "default": c["value"], "span": span(path, c["line"]),
              "provenance": prov([loc(path, c["line"])])}
        o.add(it)
    # -- the words each function shows a user, and the errors it raises from a function that is no interface
    for d in ol.get("defs") or []:
        if d.get("kind") != "class":
            b = _words_behaviour(d, mod, path, owners, o, cid)
            if b:
                o.add(b)
    # -- command lines: argparse's parsers, named by their prog, a console script or the module
    parsers = ol.get("argparse") or []
    if not parsers:
        return
    script = next((s["name"] for s in scripts if str(s.get("target", "")).split(":", 1)[0] == mod), None)
    by_var = {p["var"]: p for p in parsers}
    roots = [p for p in parsers if not p.get("parent")]
    for root in roots:
        prog = root.get("prog") or script or (f"python -m {mod.rsplit('.', 1)[0]}"
                                               if path.endswith("__main__.py") else f"python {path}")
        subs = [p for p in parsers if p.get("parent") == root["var"]]
        cmd_id = f"C:interface/command.{name_slug(slug(prog))}"
        it = {"id": cmd_id, "type": "interface", "name": prog,
              "summary": root.get("help") or f"The command line {prog}.", "stance": "observed",
              "surface": "command", "signature": _usage(prog, root.get("args") or [], subs=[
                  str(s.get("command")) for s in subs if s.get("command")]), "defined-in": fid}
        takes = _takes_of_args(root.get("args") or [])
        if subs:
            sc = root.get("subcommands") or {}
            takes.append({"name": sc.get("dest") or "command", "required": sc.get("required") == "True",
                          "means": " or ".join(str(s.get("command")) for s in subs)})
        if takes:
            it["takes"] = takes
        exits = _exits(entry)
        if exits:
            it["gives"] = {"exit": ", ".join(str(x) for x in exits) + f" (what {entry['qual']} returns or exits with)"}
        it["exported"] = True
        last = max([root.get("line") or 1] + [a.get("line") or 1 for a in root.get("args") or []] +
                   [x.get("line") or 1 for s2 in subs for x in [s2] + list(s2.get("args") or [])])
        it["span"] = span(path, root.get("line") or 1, last)
        it["provenance"] = prov([loc(path, root.get("line"), last)])
        o.add(it)
        if root.get("epilog"):
            o.add({"id": f"C:behaviour/{cmd_id.split('/', 1)[1]}.help", "type": "behaviour",
                   "name": f"The help of {prog}", "summary": f"{prog} --help ends with its epilog.",
                   "stance": "observed", "of": [cmd_id], "when": f"{prog} --help",
                   "does": f'Prints the usage, "{root.get("help") or ""}", the arguments, and last: '
                           f'"{root["epilog"]}"', "span": span(path, root.get("line") or 1),
                   "provenance": prov([loc(path, root.get("line"))])})
        _option_settings(o, path, prog, cmd_id, root.get("args") or [])
        for s in subs:
            name = str(s.get("command"))
            sid = f"{cmd_id}.{name_slug(slug(name))}"
            st = {"id": sid, "type": "interface", "name": f"{prog} {name}",
                  "summary": s.get("help") or f"The sub-command {name} of {prog}.", "stance": "observed",
                  "surface": "command", "signature": _usage(f"{prog} {name}", s.get("args") or []), "defined-in": fid}
            t2 = _takes_of_args(s.get("args") or [])
            if t2:
                st["takes"] = t2
            st["exported"] = True
            sl = max([s.get("line") or 1] + [a.get("line") or 1 for a in s.get("args") or []])
            st["span"] = span(path, s.get("line") or 1, sl)
            st["provenance"] = prov([loc(path, s.get("line"), sl)])
            o.add(st)
            _option_settings(o, path, f"{prog} {name}", sid, s.get("args") or [])
    del by_var


_SHAPES = {"frozen dataclass": "a dataclass whose instances cannot change", "dataclass": "a dataclass",
           "NamedTuple": "a NamedTuple", "TypedDict": "a TypedDict, a mapping with these keys",
           "enum": "an Enum: these members, each with its value", "class": "a class with annotated attributes"}


def _structure(d: dict, mod: str, path: str, fid: str) -> dict:
    """A data shape read from its class (THYM 20.6, rules): each field with its type and default as written."""
    fields = []
    for f in d.get("fields") or []:
        row: dict = {"name": f["name"]}
        if f.get("annotation"):
            row["type"] = f["annotation"]
        if "default" in f:
            row["default"] = f["default"]
        if d.get("shape") != "enum":
            row["required"] = "default" not in f and d.get("shape") != "TypedDict"
        fields.append(row)
    it: dict = {"id": f"C:structure/{name_slug(mod + '.' + d['qual'])}", "type": "structure", "name": d["qual"],
                "summary": d.get("doc") or f"The {d['shape']} {d['qual']} of {mod}.", "stance": "observed",
                "defined-in": fid, "shape": _SHAPES.get(d["shape"], d["shape"])}
    if fields:
        it["fields"] = fields
    it["span"] = span(path, d["line"], d.get("end"))
    it["provenance"] = prov([loc(path, d["line"], d.get("end"))])
    return it


def _raises(d: dict) -> list[dict]:
    """The errors a function raises with a literal message, as written (an f-string as its template), in order."""
    out, seen = [], set()
    for w in d.get("words") or []:
        if w["kind"] == "raise" and (w["error"], w["text"]) not in seen:
            seen.add((w["error"], w["text"]))
            out.append({"error": w["error"], "message": w["text"]})
    return out


def _entry_function(ol: dict, mod: str, scripts: list) -> dict | None:
    defs = {d["qual"]: d for d in ol.get("defs") or [] if d.get("kind") == "function"}
    for s in scripts:
        target = str(s.get("target") or "")
        if target.split(":", 1)[0] == mod and target.split(":", 1)[-1] in defs:
            return defs[target.split(":", 1)[-1]]
    for name in ["main"] + list(ol.get("main_calls") or []):
        if name in defs:
            return defs[name]
    return None


def _exits(d: dict | None) -> list[int]:
    if not d:
        return []
    codes = set(d.get("returns_int") or [])
    codes |= {w["code"] for w in d.get("words") or [] if w["kind"] == "exit" and isinstance(w.get("code"), int)}
    codes |= {w["exit"] for w in d.get("words") or [] if isinstance(w.get("exit"), int)}
    return sorted(codes)


def _words_behaviour(d: dict, mod: str, path: str, owners: dict, o: _Outline, cid: str) -> dict | None:
    """What a function shows a user, by rules: its printed and logged lines and its exits, as written (an f-string
    as its template), in line order. It lives on a behaviour (`does` for what is printed, `errors` for what goes to
    standard error or ends the program, each with its exit status when one follows at once); the messages of the
    errors a public function raises live on its interface's `raises` instead, and a private function's here."""
    iid = owners.get(str(d.get("qual")))
    public = iid in o.items
    said, errors = [], []
    for w in d.get("words") or []:
        if w["kind"] == "print" and w["stream"] == "stdout":
            said.append(f'"{w["text"]}"')
        elif w["kind"] in ("print", "log"):
            row: dict = {"when": f"{d['qual']}, line {w['line']}" + (f" ({w['level']})" if w.get("level") else ""),
                         "message": w["text"]}
            if isinstance(w.get("exit"), int):
                row["exit"] = w["exit"]
            errors.append(row)
        elif w["kind"] == "exit" and w.get("text") is not None:
            errors.append({"when": f"{d['qual']}, line {w['line']}", "message": w["text"], "exit": 1})
        elif w["kind"] == "raise" and not public:
            errors.append({"when": f"{d['qual']} raises {w['error']}", "message": w["text"]})
    if not said and not errors:
        return None
    of = [iid] if public else [cid]
    does = (f"{d['qual']} prints these lines as its code writes them: " + "; ".join(said) + ".") if said else \
        f"{d['qual']} shows these words when something goes wrong, as its code writes them."
    it: dict = {"id": f"C:behaviour/{name_slug(mod + '.' + str(d['qual']))}.words", "type": "behaviour",
                "name": f"What {d['qual']} says", "summary": f"The words {d['qual']} of {mod} shows a user, as written.",
                "stance": "observed", "of": of, "does": does}
    if errors:
        it["errors"] = errors
    it["span"] = span(path, d["line"], d.get("end"))
    it["provenance"] = prov([loc(path, d["line"], d.get("end"))])
    return it


def _option_settings(o: _Outline, path: str, prog: str, cmd_id: str, args: list[dict]) -> None:
    for a in args:
        names = a.get("names") or []
        if not names or not names[0].startswith("-") or str(a.get("action") or "") in ("help", "version"):
            continue
        opt = max(names, key=len)
        it: dict = {"id": f"C:setting/option.{name_slug(slug(prog))}.{slug(opt)}", "type": "setting",
                    "name": f"{prog} {opt}", "summary": a.get("help") or f"The option {opt} of {prog}.",
                    "stance": "observed", "key": opt, "set-in": "option"}
        if a.get("default") is not None:
            it["default"] = str(a["default"])
        elif str(a.get("action") or "") == "store_true":
            it["default"] = "False"
        if a.get("help"):
            it["means"] = a["help"]
        it["read-by"] = [cmd_id]
        it["span"] = span(path, a["line"])
        it["provenance"] = prov([loc(path, a["line"])])
        o.add(it)


def _norm(pkg: str) -> str:
    return re.sub(r"[-_.]+", "-", pkg).lower()


def _survey_dependencies(o: _Outline, outlines: dict, mods: dict, internal: set, manifests: dict,
                         req_python: str | None) -> None:
    std_users: dict[str, set] = {}
    std_first: dict = {}
    third: dict[str, dict] = {}
    comp_uses: dict[str, set] = {}
    for path, ol in sorted(outlines.items(), key=lambda kv: (is_test(kv[0]), kv[0])):
        if not isinstance(ol, dict) or not ol.get("ok") or is_tooling(path):
            continue
        mod = mods[path]
        cid = f"C:component/{name_slug(mod)}"
        user = cid if cid in o.items else None
        for imp in ol.get("imports") or []:
            m = str(imp.get("module") or "")
            level = int(imp.get("level") or 0)
            if m == "__future__":
                continue
            if level > 0:
                base = mod.split(".")
                pkg = ".".join(base[:len(base) - level + (1 if path.endswith("__init__.py") else 0)])
                targets = [f"{pkg}.{m}" if m else pkg]
                if not m:
                    targets = [f"{pkg}.{n}" for n in imp.get("names") or []] + [pkg]
                for t in targets:
                    tid = f"C:component/{name_slug(t)}"
                    if user and tid in o.items and tid != user:
                        comp_uses.setdefault(user, set()).add(tid)
                        break
                continue
            topname = m.split(".", 1)[0]
            if m in internal or topname in internal:
                for t in (m, topname):
                    tid = f"C:component/{name_slug(t)}"
                    if user and tid in o.items and tid != user:
                        comp_uses.setdefault(user, set()).add(tid)
                        break
                continue
            if imp.get("stdlib"):
                if is_test(path):                 # what the tests use is not what the program needs
                    continue
                std_users.setdefault(topname, set()).update({user} if user else set())
                std_first.setdefault("at", (path, int(imp.get("line") or 1)))
                continue
            row = third.setdefault(_norm(topname), {"import": topname, "users": set(), "tests": True,
                                                     "line": int(imp.get("line") or 1), "path": path})
            if user:
                row["users"].add(user)
            if not is_test(path):
                row["tests"] = False
    declared = {}
    for mpath, m in manifests.items():
        for d in m.get("dependencies") or []:
            declared.setdefault(_norm(d["package"]), {**d, "file": mpath})
    if std_users or req_python:
        users = sorted({u for s in std_users.values() for u in s if u})
        it = {"id": "C:dependency/python", "type": "dependency", "name": "Python and its standard library",
              "summary": "The program needs Python" + (f" {req_python}" if req_python else "") +
                         (f" and uses, from its standard library: {', '.join(sorted(std_users))}." if std_users
                          else "."),
              "stance": "observed", "package": "python",
              "version": req_python or {"pending": "which Python versions is it meant to run on?"},
              "scope": "standard", "needed-for": "everything"}
        if users:
            it["used-by"] = users
        if std_first:
            it["span"] = span(*std_first["at"])
        it["provenance"] = prov(sorted({p for p, ol in outlines.items() if isinstance(ol, dict) and ol.get("ok")})
                                + sorted(manifests))
        o.add(it)
    for key in sorted(set(third) | set(declared)):
        row, dec = third.get(key), declared.get(key)
        name = dec["package"] if dec else row["import"]
        scope = dec.get("scope") if dec else ("test" if row and row["tests"] else "run-time")
        if scope == "build" and row and row["tests"]:          # a development group only the tests import
            scope = "test"
        it = {"id": f"C:dependency/{slug(name)}", "type": "dependency", "name": name,
              "summary": f"{name}, a package from outside the tree" + (
                  f", imported as {row['import']}" if row and row["import"] != name else "") + ".",
              "stance": "observed", "package": name, "scope": scope}
        if dec and dec.get("version"):
            it["version"] = dec["version"]
        elif dec:
            it["version"] = "any"
        if row and row["users"]:
            it["used-by"] = sorted(row["users"])
            it["needed-for"] = "imported by " + ", ".join(sorted(o.items[u]["name"] for u in row["users"]))
        elif row and row["tests"]:
            it["needed-for"] = "the tests"
        else:
            it["needed-for"] = {"pending": f"what is {name} needed for? It is declared and never imported"}
        sources = ([loc(dec["file"], dec.get("line"))] if dec else []) + ([row["path"]] if row else [])
        if row:
            it["span"] = span(row["path"], row["line"])
        elif dec and dec.get("line"):
            it["span"] = span(dec["file"], int(dec["line"]))
        it["provenance"] = prov(sources)
        o.add(it)
        for u in (row["users"] if row else ()):
            comp_uses.setdefault(u, set()).add(it["id"])
    for u in std_users.values():
        for c in u:
            if c and "C:dependency/python" in o.items:
                comp_uses.setdefault(c, set()).add("C:dependency/python")
    for cid, uses in comp_uses.items():
        if cid in o.items:
            o.items[cid]["uses"] = sorted(uses)


def _survey_licence(o: _Outline, f: Folder, manifests: dict) -> Any:
    lic_files = [e for e in f.texts() if is_licence_file(e.path)]
    read = read_licence(f.text(lic_files[0].path)) if lic_files else None
    ident = read.get("identifier") if read else None
    pkg_ident, pkg_file = _licence_from_packaging(manifests)
    it: dict = {"type": "licence", "stance": "observed"}
    if read:
        it["file"] = lic_files[0].path
    if ident or pkg_ident:
        value: Any = ident or pkg_ident
    elif read and read.get("first-line"):
        value = read["first-line"]
    else:
        value = {"pending": "no licence file was found: under which licence may it be used?"}
    it["id"] = f"R:licence/{slug(value) if isinstance(value, str) else 'unknown'}"
    it["name"] = value if isinstance(value, str) else "The licence"
    if isinstance(value, str):
        holder = f", copyright {read['year']} {read['holder']}" if read and read.get("holder") else ""
        it["summary"] = f"{f.name} is under the licence {value}{holder}."
        it["identifier"] = value if (ident or pkg_ident) else {"pending": f"which licence is this: {value}?"}
    else:
        it["summary"] = f"No licence file was found in {f.name}, and its packaging names none."
        it["identifier"] = value
    if read:
        for k in ("holder", "year", "first-line"):
            if read.get(k):
                it[k] = read[k]
        last = max(int(read.get("line") or 1), 1)
        it["span"] = span(lic_files[0].path, 1, min(max(last, 1), read["lines"]) if read["lines"] else 1)
        it["provenance"] = prov([loc(lic_files[0].path, 1, last if last > 1 else None)] +
                                ([pkg_file] if pkg_ident and not ident else []))
    else:
        it["provenance"] = prov([pkg_file] if pkg_file else [f"{f.name}/"],
                                confidence=1, state="known" if pkg_ident else "pending")
    o.add(it)
    return value


def _survey_means(o: _Outline, manifests: dict, req_python: str | None, outlines: dict) -> None:
    o.add({"id": "R:means/python", "type": "means", "name": "Python", "summary": "The program is written in Python.",
           "stance": "observed", "what": "Python", "used-for": "the program",
           "version": req_python or {"pending": "which Python versions is it written for?"},
           "provenance": prov(sorted(outlines)[:3] + sorted(manifests))})
    for path, m in manifests.items():
        b = m.get("build") or {}
        backend = b.get("backend")
        if backend:
            name = str(backend).split(".", 1)[0]
            o.add({"id": f"R:means/{slug(name)}", "type": "means", "name": name,
                   "summary": f"The package is built with {name}.", "stance": "observed", "what": name,
                   "used-for": "building the package", "provenance": prov([path])})
    uses_pytest = any(isinstance(ol, dict) and any(i.get("module") == "pytest" for i in ol.get("imports") or [])
                      for ol in outlines.values())
    if uses_pytest:
        o.add({"id": "R:means/pytest", "type": "means", "name": "pytest", "summary": "The tests are written for pytest.",
               "stance": "observed", "what": "pytest", "used-for": "tests",
               "provenance": prov(sorted(p for p, ol in outlines.items() if isinstance(ol, dict) and any(
                   i.get("module") == "pytest" for i in ol.get("imports") or [])))})


# ---------------------------------------------------------------------------
# history: the clone's log and tags (THYM 20.6, rules only)
# ---------------------------------------------------------------------------

#: Two commits more than this many days apart start a new episode (THYM 20.6).
EPISODE_GAP_DAYS = 14
_NATURE = (("fix", re.compile(r"(?i)^(fix|bug|hotfix|repair|correct)|\bfix(es|ed)?\b")),
           ("removal", re.compile(r"(?i)^(remove|delete|drop)\b")),
           ("refactor", re.compile(r"(?i)^(refactor|rename|move|tidy|clean)")),
           ("docs", re.compile(r"(?i)^docs?\b|readme")),
           ("tests", re.compile(r"(?i)^tests?\b")),
           ("build", re.compile(r"(?i)^(build|ci|release|bump|chore)\b")),
           ("feature", re.compile(r"(?i)^(add|new|feat|support|implement|introduce|allow)")))


def _days(stamp: str) -> int:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stamp or "")
    if not m:
        return 0
    import datetime as _dt
    return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).toordinal()


def _nature(c: dict) -> str:
    paths = c.get("paths") or []
    if re.match(r"(?i)(release|prepare|bump)\b|v?\d+(\.\d+)+\W*$", str(c.get("subject") or "").strip()):
        return "build"
    if paths and all(re.search(r"(?i)\.(md|rst|txt)$|^docs/", p) for p in paths):
        return "docs"
    if paths and all(is_test(p) for p in paths):
        return "tests"
    subj = re.sub(r"^\w+(\([^)]*\))?!?:\s*", lambda m: m.group(0).split("(")[0].rstrip(":! ") + " ",
                  str(c.get("subject") or ""))
    for nature, rx in _NATURE:
        if rx.search(subj):
            return nature
    return "revision"


def _because(body: str) -> str | None:
    text = " ".join(str(body or "").split())
    if not text:
        return None
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= 200 else first[:199] + "…"


def _named_holders(f: Folder) -> set[str]:
    """The names the repository itself states as its makers: a licence's copyright holder, an AUTHORS file's lines,
    the `authors` and `maintainers` of its `pyproject.toml` (their names only, never an address)."""
    names: set[str] = set()
    for e in f.texts():
        if "/" in e.path:
            continue
        if is_licence_file(e.path):
            r = read_licence(f.text(e.path))
            if r.get("holder"):
                names.add(r["holder"])
        elif e.path == "pyproject.toml":
            try:
                proj = (tomllib.loads(f.text(e.path)) or {}).get("project") or {}
            except (tomllib.TOMLDecodeError, ValueError):
                proj = {}
            for who in list(proj.get("authors") or []) + list(proj.get("maintainers") or []):
                if isinstance(who, dict) and isinstance(who.get("name"), str) and who["name"].strip():
                    names.add(who["name"].strip())
        elif re.match(r"(?i)^(authors|contributors|maintainers)(\.(md|txt|rst))?$", e.path):
            for ln in f.text(e.path).splitlines():
                s = re.sub(r"<[^>]*>|\([^)]*@[^)]*\)", "", ln).strip(" -*\t")
                if s and not s.startswith("#") and len(s) < 80:
                    names.add(s)
    return names


@implements("history")
def history(ctx: Any, repo: Value, **mods: Any) -> Value:
    """The fabula so far with the clone's history (THYM 6.3, 20.6): changes in episodes, releases from tags, makers."""
    f = _folder_of(repo, "history")
    w = mods.get("with")
    cat, items = _fabula(w, "history needs the fabula it adds to: history repo with f")
    _need_fabulac(cat, "f", "history adds to a fabulac")
    h = engine(ctx, "repo").history(repo)
    at = stamp_at(ctx)
    ids = {it.get("id") for it in items}
    new: list[dict] = []
    files_by_path = {p: it["id"] for p, it in _file_items(items).items()}
    grounds: dict = {"commits": [], "tags": [], "authors": []}
    if not isinstance(h, dict) or not h.get("clone"):
        why = (h or {}).get("why") if isinstance(h, dict) else None
        new.append({"id": "D:question/history", "type": "question", "about": "R",
                    "asks": f"{f.name} has no history this build can read ({why or 'it is not a clone'}): how did it "
                            "come to be, who made it, and when was it released?",
                    "why": "missing", "kind": "text", "to": "maker",
                    "raised": {"by": "move", "from": "history", "at": at,
                               **({"run": ctx.run} if getattr(ctx, "run", None) else {})},
                    "state": "open"})
    else:
        new += _history_items(f, h, files_by_path, grounds)
    new = [it for it in new if it["id"] not in ids]
    cat = copy.deepcopy(cat)
    d = cat.setdefault("derived", {})
    run = {"program": _program(ctx), "run": getattr(ctx, "run", None), "at": at}
    d.setdefault("runs", []).append({k: v for k, v in run.items() if v})
    return Value("fabula", {**cat, "nodes": items + new}, origin={"history": grounds})


def _release_index(commits: list[dict], tags: list[dict]) -> tuple[list[tuple[int, dict, str]], list[dict]]:
    """Where each tag stands in the history read (oldest first): `[(index, tag, how)]` and the tags it cannot place.
    A tag on a commit read stands there (`how` "tag"); a tag whose commit is not among those read (a history rewritten
    after the tag, a tag on a release branch) stands at the newest commit read whose subject names its version as a
    release ("Release v6.2.6.", "Bump version to 6.2.6", "6.2.6"), `how` "subject"; any other is left unplaced."""
    order = {c["sha"]: i for i, c in enumerate(commits)}
    placed, loose = [], []
    for t in tags:
        if t.get("sha") in order:
            placed.append((order[t["sha"]], t, "tag"))
            continue
        version = re.sub(r"^[vV](?=\d)", "", str(t["name"]))
        ver = re.escape(version)
        rx = re.compile(rf"^(?:(?:release|prepare|bump(?: version)?(?: to)?|version)[\s:]*)?v?{ver}\W*$"
                        rf"|^release\s+v?{ver}\b", re.I)
        hits = [i for i, c in enumerate(commits) if rx.search(str(c.get("subject") or "").strip())]
        if hits:
            placed.append((hits[-1], t, "subject"))
        else:
            loose.append(t)
    placed.sort(key=lambda x: (x[0], x[1]["at"]))
    return placed, loose


#: The history kept item by item: the newest changes, each release's own commit; the rest are counted in their
#: episode and release (MacroCOSM OES 18.4.7: the history serves the fabulac, it does not drown it).
KEEP_CHANGES = 40
MAX_EPISODES = 20
MAX_MAKERS = 12
MAX_RELEASES = 30


def _episodes(commits: list[dict], release_of: dict) -> tuple[list[list[dict]], str]:
    """The episodes, oldest first, and the rule that made them: the commits between two tags, split again where two
    commits stand more than EPISODE_GAP_DAYS apart (THYM 20.6); where that gives more than MAX_EPISODES, the commits
    between two tags alone; where that still does, one episode per calendar year."""
    def cut(same) -> list[list[dict]]:
        eps: list[list[dict]] = []
        cur: list[dict] = []
        for c in commits:
            if cur and not same(cur[-1], c):
                eps.append(cur)
                cur = []
            cur.append(c)
        return eps + ([cur] if cur else [])
    eps = cut(lambda a, b: release_of.get(a["sha"]) == release_of.get(b["sha"])
              and abs(_days(b["at"]) - _days(a["at"])) <= EPISODE_GAP_DAYS)
    if len(eps) <= MAX_EPISODES:
        return eps, "tags and gaps"
    eps = cut(lambda a, b: release_of.get(a["sha"]) == release_of.get(b["sha"]))
    if len(eps) <= MAX_EPISODES:
        return eps, "tags"
    years: dict[str, list[dict]] = {}
    for c in commits:
        years.setdefault(c["at"][:4], []).append(c)
    return [years[y] for y in sorted(years)], "years"


def _tally(cs: list[dict]) -> str:
    n: dict[str, int] = {}
    for c in cs:
        k = _nature(c)
        n[k] = n.get(k, 0) + 1
    return ", ".join(f"{v} {k}" for k, v in sorted(n.items(), key=lambda kv: (-kv[1], kv[0])))


def _history_items(f: Folder, h: dict, files_by_path: dict, grounds: dict) -> list[dict]:
    commits = [c for c in h.get("commits") or [] if isinstance(c, dict) and c.get("sha")]
    commits = list(reversed(commits))                       # oldest first
    tags = [t for t in h.get("tags") or [] if isinstance(t, dict) and t.get("name")]
    tag_at, loose = _release_index(commits, tags)
    grounds["commits"] = [c["sha"] for c in commits]
    grounds["tags"] = [t["name"] for t in tags]
    grounds["authors"] = sorted({str(c.get("author")) for c in commits})
    out: list[dict] = []
    # releases: each tag, and the commits since the previous tag up to it
    release_of: dict[str, str] = {}
    start = 0
    releases = []
    for idx, t, how in tag_at:
        rid = f"R:release/{slug(t['name'])}"
        for c in commits[start:idx + 1]:
            release_of.setdefault(c["sha"], rid)
        releases.append((rid, t, commits[start:idx + 1], commits[idx], how))
        start = max(start, idx + 1)
    episodes, rule = _episodes(commits, release_of)
    phase_of = {}
    for n, ep in enumerate(episodes, 1):
        for c in ep:
            phase_of[c["sha"]] = f"R:phase/episode-{n}"
    # makers: roles and counts; a name only where the repository states it (its licence holder, its AUTHORS file,
    # its packaging's authors); past MAX_MAKERS, the rest as one group
    named = _named_holders(f)
    counts: dict[str, int] = {}
    for c in commits:
        counts[c["author"]] = counts.get(c["author"], 0) + 1
    ranked = sorted(counts, key=lambda a: (-counts[a], a))
    maker_of: dict[str, str] = {}
    for n, a in enumerate(ranked[:MAX_MAKERS], 1):
        shown = a if a in named else None
        mid = f"R:maker/{slug(shown)}" if shown else f"R:maker/contributor-{n}"
        maker_of[a] = mid
        mine = [c for c in commits if c["author"] == a]
        cap = "author" if n == 1 else "contributor"
        who = shown or ("the main contributor" if n == 1 else f"contributor {n}")
        out.append({"id": mid, "type": "maker", "name": shown or f"Contributor {n}",
                    "summary": f"{who[:1].upper() + who[1:]} made {len(mine)} of the {len(commits)} commits read, "
                               f"from {mine[0]['at'][:10]} to {mine[-1]['at'][:10]}.",
                    "stance": "observed", "capacity": cap,
                    "provenance": prov([f"commit:{c['sha']}" for c in mine[-5:]])})
    rest = ranked[MAX_MAKERS:]
    if rest:
        mine = [c for c in commits if c["author"] in rest]
        for a in rest:
            maker_of[a] = "R:maker/others"
        out.append({"id": "R:maker/others", "type": "maker", "name": f"{len(rest)} other contributors",
                    "summary": f"{len(rest)} other contributors made {len(mine)} of the {len(commits)} commits read, "
                               f"at most {max(counts[a] for a in rest)} each.",
                    "stance": "observed", "capacity": "contributor",
                    "provenance": prov([f"commit:{c['sha']}" for c in mine[-5:]])})
    # changes: the newest KEEP_CHANGES; the others are counted in their episode and their release
    keep = {c["sha"] for c in commits[-KEEP_CHANGES:]}
    shown_commits = [c for c in commits if c["sha"] in keep]
    for c in shown_commits:
        subject = str(c.get("subject") or "").strip() or "(no subject)"
        it: dict = {"id": f"R:change/{c['sha'][:12]}", "type": "change", "name": subject[:80],
                    "summary": f"On {c['at'][:10]}: {subject}", "stance": "observed", "at": c["at"][:10],
                    "by": maker_of[c["author"]], "nature": _nature(c)}
        because = _because(c.get("body") or "")
        if because:
            it["because"] = because
        touches = sorted({files_by_path[p] for p in c.get("paths") or [] if p in files_by_path})
        if touches:
            it["touches"] = touches
        if c["sha"] in release_of:
            it["release"] = release_of[c["sha"]]
        it["phase"] = phase_of[c["sha"]]
        it["commit"] = c["sha"]
        it["provenance"] = prov([f"commit:{c['sha']}"])
        out.append(it)
    shown_ids = {f"R:change/{c['sha'][:12]}" for c in shown_commits}
    for n, ep in enumerate(episodes, 1):
        rel = release_of.get(ep[-1]["sha"])
        name = (f"{ep[0]['at'][:4]}" if rule == "years" else
                f"Up to {next(r[1]['name'] for r in releases if r[0] == rel)}" if rel else f"Episode {n}")
        days = sorted(c["at"][:10] for c in ep)
        firsts = "; ".join(str(c.get("subject") or "")[:60] for c in ep[:2])
        out.append({"id": f"R:phase/episode-{n}", "type": "phase", "name": name,
                    "summary": f"{len(ep)} commit{'s' if len(ep) != 1 else ''} from {days[0]} to {days[-1]} "
                               f"({_tally(ep)}), beginning with: {firsts}",
                    "stance": "observed", "began": days[0], "ended": days[-1],
                    "changes": [f"R:change/{c['sha'][:12]}" for c in ep if f"R:change/{c['sha'][:12]}" in shown_ids],
                    "provenance": prov([f"commit:{ep[0]['sha']}", f"commit:{ep[-1]['sha']}"])})
    tagged = sorted([(r[1]["at"], r) for r in releases] + [(t["at"], (None, t, [], None, "loose")) for t in loose],
                    key=lambda x: (x[0], x[1][1]["name"]))
    older = [r for _, r in tagged[:-MAX_RELEASES]] if len(tagged) > MAX_RELEASES else []
    if older:
        names = [r[1]["name"] for r in older]
        out.append({"id": "R:phase/earlier-releases", "type": "phase", "name": "Earlier releases",
                    "summary": f"{len(older)} earlier tags, from {names[0]} ({older[0][1]['at'][:10]}) to {names[-1]} "
                               f"({older[-1][1]['at'][:10]}): {', '.join(names)}.",
                    "stance": "observed", "began": older[0][1]["at"][:10], "ended": older[-1][1]["at"][:10],
                    "provenance": prov([f"tag:{n}" for n in names])})
    old_names = {r[1]["name"] for r in older}
    releases = [r for r in releases if r[1]["name"] not in old_names]
    loose = [t for t in loose if t["name"] not in old_names]
    for rid, t, cs, at_c, how in releases:
        version = re.sub(r"^[vV](?=\d)", "", t["name"])
        where = "" if how == "tag" else (f" Its tag stands on a commit outside the history read; the release is "
                                          f"placed at the commit named \"{str(at_c.get('subject') or '')[:60]}\".")
        out.append({"id": rid, "type": "release", "name": t["name"],
                    "summary": f"The tag {t['name']}, made on {t['at'][:10]}, after {len(cs)} commit"
                               f"{'s' if len(cs) != 1 else ''} ({_tally(cs)}).{where}", "stance": "observed",
                    "version": version, "at": t["at"][:10], "tag": t["name"],
                    "changes": [f"R:change/{c['sha'][:12]}" for c in cs if f"R:change/{c['sha'][:12]}" in shown_ids],
                    "provenance": prov([f"tag:{t['name']}", f"commit:{at_c['sha']}"])})
    for t in loose:
        out.append({"id": f"R:release/{slug(t['name'])}", "type": "release", "name": t["name"],
                    "summary": f"The tag {t['name']}, made on {t['at'][:10]}, on a commit outside the history read.",
                    "stance": "observed", "version": re.sub(r"^[vV](?=\d)", "", t["name"]), "at": t["at"][:10],
                    "tag": t["name"], "provenance": prov([f"tag:{t['name']}"])})
    for it in out:
        if it.get("changes") == []:
            it.pop("changes")
    if h.get("truncated") or h.get("shallow"):
        out.append({"id": "R:phase/before-the-record", "type": "phase", "name": "Before what was read",
                    "summary": "The history read here does not reach the first commit.", "stance": "observed",
                    "began": {"pending": "when did the work begin?"}, "ended": commits[0]["at"][:10] if commits else
                    {"pending": "when?"}, "provenance": prov(["commit:" + commits[0]["sha"]] if commits else [])})
    return out


# ---------------------------------------------------------------------------
# derive t as code with f: one file read against the outline (asks)
# ---------------------------------------------------------------------------

READ_SAYS = ("a YAML mapping of lists: behaviours, structures, cases, terms, concepts, claims, events; each entry a "
             "mapping with slug, name, summary, lines and the fields of its kind")


def local_outline(items: list[dict], path: str) -> list[dict]:
    """The outline's items about one file: its `C:file`, the components holding it, the interfaces and structures
    defined in it, the settings read in it, and the dependencies its components use."""
    by = _by_id(items)
    files_by_id = {i: it for i, it in by.items() if item_kind(it) == "file"}
    fid = next((i for i, it in files_by_id.items() if it.get("path") == path), None)
    if fid is None:
        return []
    out = [by[fid]]
    comps = [it for it in items if item_kind(it) == "component" and fid in (it.get("files") or [])]
    out += comps
    local = [it for it in items if item_kind(it) in ("interface", "structure") and it.get("defined-in") == fid]
    out += local
    lids = {it["id"] for it in local}
    out += [it for it in items if item_kind(it) == "setting" and (
        (isinstance(it.get("span"), dict) and it["span"].get("file") == path) or set(it.get("read-by") or []) & lids)]
    used = {u for c in comps for u in c.get("uses") or []}
    out += [it for it in items if item_kind(it) == "dependency" and it["id"] in used]
    seen: set = set()
    return [it for it in out if not (it["id"] in seen or seen.add(it["id"]))]


def _compact(it: dict) -> dict:
    """An item as a model is shown it: without provenance and made."""
    return {k: v for k, v in it.items() if k not in ("provenance", "made", "stance")}


#: What a reader is not shown of an outline item: the bookkeeping it cannot use (the file is the one it reads, the
#: kind is in the id, the component's list of what it exposes is the interfaces that follow).
_NOT_SHOWN = ("provenance", "made", "stance", "type", "defined-in", "sha256", "length", "exposes", "holds", "files",
              "component", "language")


def _shown(it: dict, path: str) -> dict:
    """An outline item as a reader of `path` is shown it: its own fields, a span in this file as its lines."""
    out = {k: v for k, v in it.items() if k not in _NOT_SHOWN}
    sp = out.get("span")
    if isinstance(sp, dict) and sp.get("file") == path:
        out.pop("span")
        out["lines"] = sp.get("lines")
    if out.get("exported") is True:
        out.pop("exported")
    return out


def _numbered(text: str, first: int = 1) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    w = len(str(first + len(lines)))
    return "\n".join(f"{str(n).rjust(w)}| {ln}" for n, ln in enumerate(lines, first))


def chunks_of(text: str, size: int = CHUNK_LINES) -> list[tuple[int, int]]:
    """The line ranges a long file is read in: at most `size` lines each, cut before a top-level `def`, `class` or
    decorator where one stands in the last third of the range (the rule a replay holds to: it is the same text)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    n = len(lines)
    out, a = [], 1
    while a <= n:
        b = min(n, a + size - 1)
        if b < n:
            for k in range(b, a + size * 2 // 3 - 1, -1):
                if re.match(r"(def |class |async def |@)", lines[k - 1]):
                    b = k - 1
                    break
        out.append((a, b))
        a = b + 1
    return out or [(1, max(n, 1))]


def _yaml_list(text_or_map: Any) -> dict:
    data = answer_mapping(text_or_map)
    return data


def _clean_slug(s: Any) -> str:
    s = str(s or "").strip()
    s = s.split("/", 1)[1] if _ID.match(s) else s
    s = re.sub(r"[^A-Za-z0-9._@-]+", "-", s).strip("-._@")
    return s or "item"


def _lines_of(row: dict, a: int, b: int, n: int) -> tuple[int, int] | None:
    v = row.get("lines")
    nums = [int(x) for x in re.findall(r"\d+", str(v if v is not None else ""))]
    if not nums:
        return None
    return min(nums), max(nums)


def parse_reading(out: Any, *, path: str, module: str, n_lines: int, taken: set[str], feed: Any = None,
                  base: list[dict] | None = None) -> list[dict]:
    """A model's reading of one file as items (strict: a ValueError says what is wrong, and the answer is asked
    again). Every entry is a mapping with a `slug`, a `name`, a `summary` and `lines`; its id is made here, in the
    file's own namespace (`C:behaviour/<module>.<slug>`), so that two files' readings never collide; its span is
    `{file: <path>, lines}`; behaviours, structures, cases and events are `observed` (read in the code) unless the
    entry says `deduced`; a claim keeps the stance it gives."""
    data = answer_mapping(out)
    unknown = [k for k in data if k not in READ_KINDS and k not in ("engine", "enrich")]
    if unknown:
        raise ValueError(f"the answer has sections this reading does not take: {', '.join(map(str, unknown))}; "
                         f"use {', '.join(READ_KINDS)}, enrich")
    items: list[dict] = enrichments(data.get("enrich"), base or [], path, n_lines)
    used = set(taken)
    for section, (letter, kind) in READ_KINDS.items():
        rows = data.get(section) or []
        if not isinstance(rows, list):
            raise ValueError(f"{section} must be a list")
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"{section} entry {i} is not a mapping")
            _broken_keys(section, i, row)
            for need in ("name", "summary"):
                if not isinstance(row.get(need), str) or not row[need].strip():
                    raise ValueError(f"{section} entry {i} has no {need}")
            base = f"{letter}:{kind}/{name_slug(module + '.' + _clean_slug(row.get('slug') or row.get('id') or row['name']))}"
            iid, k = base, 2
            while iid in used:
                iid, k = f"{base}-{k}", k + 1
            used.add(iid)
            it: dict = {"id": iid, "type": kind, "name": fold(row["name"])[:120], "summary": fold(row["summary"])}
            ab = _lines_of(row, 1, n_lines, n_lines)
            if kind not in ("term", "concept", "event"):
                st = str(row.get("stance") or "").strip()
                if kind == "claim":
                    it["stance"] = st if st in LADDER else "observed"
                else:
                    it["stance"] = st if st in ("observed", "deduced") else "observed"
            if kind == "claim":
                sal = str(row.get("salience") or "normal")
                it["salience"] = sal if sal in ("critical", "high", "normal", "low") else "normal"
            fields = _READ_FIELDS[kind]
            for fk in fields:
                if fk in row and row[fk] not in (None, "", []):
                    it[fk] = plain(row[fk])
            if kind == "behaviour" and not it.get("does"):
                raise ValueError(f"behaviours entry {i} ({row['name']}) has no does")
            if kind == "case":
                for need in ("of", "given", "expect"):
                    if not it.get(need):
                        raise ValueError(f"cases entry {i} ({row['name']}) has no {need}")
            if kind in ("behaviour", "case") and isinstance(it.get("of"), str):
                it["of"] = [it["of"]]
            if kind == "term":
                it["feed"] = _ground(feed, str(row.get("word") or row["name"]), row.get("pos"))
                if row.get("sense"):
                    it["sense"] = fold(row["sense"])
            if ab is not None:
                it["span"] = span(path, ab[0], ab[1])
            it["provenance"] = prov([loc(path, ab[0], ab[1]) if ab else path],
                                    0.9 if it.get("stance", "observed") == "observed" else 0.7)
            items.append(it)
    return items


#: What a reading may add to an outline item of its own file (MacroCOSM OES 18.4.2's fields of those kinds).
ENRICH_FIELDS = {"interface": ("takes", "gives", "raises"), "structure": ("fields", "invariants"),
                 "component": ("does",), "setting": ("means",)}


def _by_name(base_rows: Any, rows: Any, what: str, iid: str) -> list[dict]:
    """A list of named entries (`takes`, `fields`) as a reading adds to it: the base's entries in their order, each
    with its name and the `means` the reading gives; a name the base lacks is refused."""
    base_rows = base_rows if isinstance(base_rows, list) else []
    means = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("name"):
            raise ValueError(f"enrich {iid}: every entry of {what} names its name")
        name = str(r["name"]).lstrip("*")
        if name not in {str(b.get("name")).lstrip("*") for b in base_rows}:
            raise ValueError(f"enrich {iid}: {what} has no entry {name}")
        if r.get("means"):
            means[name] = fold(r["means"])
    return [{"name": b["name"], **({"means": means[str(b["name"]).lstrip("*")]}
                                   if str(b["name"]).lstrip("*") in means else {})} for b in base_rows]


def enrichments(rows: Any, base: list[dict], path: str, n_lines: int) -> list[dict]:
    """What a reading adds to the outline's own items of its file (THYM 20.6, as built here): for each entry `{id,
    <fields>, lines}`, the item's id with only the fields of `ENRICH_FIELDS` the code shows and the outline lacks, or
    with what it adds inside them (a parameter's `means`, an error's `when`), shaped so that `gather` merges them
    without changing anything a rules pass read. A ValueError names an entry that is not the file's or not a field the
    kind takes."""
    if not rows:
        return []
    if not isinstance(rows, list):
        raise ValueError("enrich must be a list")
    local = {it["id"]: it for it in local_outline(base, path)}
    out = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"enrich entry {i} names no id")
        _broken_keys("enrich", i, row)
        iid = row["id"]
        b = local.get(iid)
        if b is None:
            raise ValueError(f"enrich {iid}: it is not an item of the outline for {path}")
        kind = item_kind(b)
        allowed = ENRICH_FIELDS.get(kind, ())
        extra = [k for k in row if k not in allowed and k not in ("id", "lines")]
        if extra:
            raise ValueError(f"enrich {iid}: a {kind} takes {', '.join(allowed) or 'nothing'} here, not "
                             f"{', '.join(extra)}")
        it: dict = {"id": iid}
        if "takes" in row and b.get("takes"):
            it["takes"] = _by_name(b["takes"], row["takes"], "takes", iid)
        if "fields" in row and b.get("fields"):
            it["fields"] = _by_name(b["fields"], row["fields"], "fields", iid)
        if isinstance(row.get("gives"), dict):
            g = {k: plain(v) for k, v in row["gives"].items() if k in ("type", "means", "output", "exit") and v}
            for k in list(g):
                if isinstance(b.get("gives"), dict) and k in b["gives"] and b["gives"][k] != g[k]:
                    g.pop(k)                                   # what rules read stands; the reading only adds
            if g:
                it["gives"] = g
        if isinstance(row.get("raises"), list):
            have = [dict(r) for r in b.get("raises") or [] if isinstance(r, dict)]
            more = []
            for r in row["raises"]:
                if not isinstance(r, dict) or not r.get("error"):
                    raise ValueError(f"enrich {iid}: every entry of raises names its error")
                r = {k: fold(v) if isinstance(v, str) else plain(v) for k, v in r.items()
                     if k in ("error", "message", "when")}
                hit = next((h for h in have if h.get("error") == r["error"] and
                            (not r.get("message") or h.get("message") == r.get("message")) and "when" not in h), None)
                if hit is not None:
                    if r.get("when"):
                        hit["when"] = r["when"]
                else:
                    more.append(r)
            if more or any("when" in h for h in have):
                it["raises"] = have + more
        if isinstance(row.get("invariants"), list) and not b.get("invariants"):
            it["invariants"] = [fold(x) for x in row["invariants"] if isinstance(x, str) and x.strip()]
        for k in ("does", "means"):
            if isinstance(row.get(k), str) and row[k].strip() and k in allowed and (
                    k not in b or mc.is_pending(b.get(k))):
                it[k] = fold(row[k])
        ab = _lines_of(row, 1, n_lines, n_lines)
        if len(it) > 1:
            it["provenance"] = {"sources": [loc(path, ab[0], ab[1]) if ab else path]}
            out.append(it)
    return out


_READ_FIELDS = {
    "behaviour": ("of", "when", "does", "edges", "errors"),
    "structure": ("shape", "fields", "invariants"),
    "case": ("of", "given", "expect"),
    "term": (),
    "concept": ("defined-by",),
    "claim": ("roles",),
    "event": ("agent", "patient", "before", "after", "when"),
}


def _ground(feed: Any, word: str, pos: Any) -> dict:
    """A term's `feed` block: FEED's entry when the host's FEED holds the word, `{pending: "not in FEED"}` when it
    does not; with no FEED here, the model's word and part of speech, as Canon writes them without a dictionary."""
    w = word.strip().lower()
    if feed is not None:
        try:
            found = feed([w]) or {}
        except Exception:  # noqa: BLE001 - a FEED that cannot be read grounds nothing
            found = {}
        entry = found.get(w) if isinstance(found, dict) else None
        if isinstance(entry, dict):
            p = entry.get("pos") or pos
            if isinstance(p, list):
                p = pos if pos in p else (p[0] if p else None)
            return {"word": w, "pos": str(p or "noun"), "origin": "feed"}
        return {"pending": "not in FEED"}
    return {"word": w, "pos": str(pos or "noun"), "origin": "feed"}


def _definitions(ol: Any) -> str:
    """Every function, class and method of a file, private and nested ones too, one per line with its lines and
    its decorated signature: what a reader of one chunk of a long file needs to name the helpers the other chunks
    define."""
    if not isinstance(ol, dict) or not ol.get("ok"):
        return "(the file does not parse)"
    rows = [f"{d['line']}-{d.get('end', d['line'])} {d.get('qual')}: {_decorated(d)}" for d in ol.get("defs") or []]
    return "\n".join(rows) or "(none)"


def reading_value(cat: dict, items: list[dict], path: str, new: list[dict]) -> dict:
    """A reading as a fabula: the outline's catalog and only what the reading adds for its file, its new items and
    its enrichments of the outline's own items of that file. Its references resolve against the fabula it was read
    with; `fabula-checks` lints the two together (`joined`)."""
    return {**copy.deepcopy(cat), "nodes": list(new)}


def read_file(ctx: Any, t: Value, **mods: Any) -> Request | Value:
    """`derive t as code with f`: one Python file read against the outline (THYM 20.6, read), one model request per
    file (several, keyed in order, for a file longer than `CHUNK_LINES`)."""
    w = mods.get("with")
    if not isinstance(w, Value) or w.type != "fabula":
        raise MoveError("derive … as code reads a file against its outline: derive t as code with f")
    cat, items = _fabula(w, "derive … as code reads against a fabula")
    _need_fabulac(cat, "the fabula it reads against", "a file is read as code against a fabulac's outline")
    path = str(t.field("path") or (t.path.name if t.path is not None else ""))
    files = _file_items(items)
    if path not in files:
        raise MoveError(f"{path or 'the text'} is not in the outline: survey the folder first, and read its own files")
    if files[path].get("language") != "python":
        raise MoveError(f"{path} is {files[path].get('language')}; this edition reads Python files as code")
    text = t.text()
    n = lines_in(text)
    top = set()
    module = module_name(path, top)
    local = local_outline(items, path)
    taken = {str(it.get("id")) for it in items}
    terms = [{"id": it["id"], "name": it.get("name")} for it in items if item_kind(it) == "term"][:80]
    others = [{"id": it["id"], "signature": it.get("signature")} for it in items if item_kind(it) == "interface"
              and it.get("defined-in") != files[path]["id"]][:120]
    feed = (getattr(ctx, "engines", None) or {}).get("feed")
    parts = chunks_of(text)
    defs = _definitions(engine(ctx, "syntax").outline(path, text))

    def inputs(a: int, b: int) -> dict:
        lines = text.replace("\r\n", "\n").split("\n")
        return {"fabulac": Value("string", "read"), "path": Value("string", path),
                "lines": Value("string", f"{a}-{b} of {n}"),
                "code": Value("string", _numbered("\n".join(lines[a - 1:b]), a)),
                "outline": Value("string", _yaml([_shown(x, path) for x in local])),
                "terms": Value("string", _yaml(terms) if terms else "[]"),
                "elsewhere": Value("string", _yaml(others) if others else "[]"),
                "definitions": Value("string", defs),
                "test": Value("string", "yes" if is_test(path) else "no")}

    schema = {"format": "yaml", "stamp": "engine", "says": READ_SAYS}
    if len(parts) == 1:
        def parse(out: Any) -> Value:
            new = parse_reading(out, path=path, module=module, n_lines=n, taken=taken, feed=feed, base=items)
            return Value("fabula", reading_value(cat, items, path, new), origin={"reading": {"path": path}})
        return Request(contract={"schema": schema, "repair": ["drop-unresolved-refs"]}, inputs=inputs(1, n),
                       parse=parse, repair=lambda v, failed: _drop_unresolved(v, failed, items))
    # a long file: one request per chunk, through ctx.ask (keyed <node>, <node>-1, … and replayed in order)
    new: list[dict] = []
    for a, b in parts:
        last_err = None
        for _try in range(2):
            # ctx.ask takes `repair` as the list of repairs allowed, and carries only the runtime's failed verdicts;
            # the reason this move could not read the last answer rides in the inputs, so the prompt says it
            ins = inputs(a, b)
            if last_err:
                ins["failed"] = Value("string", last_err)
            cand = ctx.ask({"schema": schema, "repair": []}, ins)
            try:
                got = parse_reading(cand.get("output"), path=path, module=module, n_lines=n,
                                    taken=taken | {i["id"] for i in new}, feed=feed, base=items)
                break
            except ValueError as e:
                last_err = str(e)
        else:
            raise MoveError(f"{path}, lines {a} to {b}: the reading could not be read: {last_err}")
        new += got
    return Value("fabula", reading_value(cat, items, path, new), origin={"reading": {"path": path}})


def _drop_unresolved(v: Value, failed: list, base: list[dict] | None = None) -> Value | None:
    """The narrow repair a reading allows: a reference a new item makes to nothing is dropped (a list entry) or
    becomes an open question; a span outside the file is not repaired (the answer is asked again)."""
    names = {f.get("name") for f in failed}
    if "fabula-checks" not in names:
        return None
    cat, items = fabula_doc(v)
    ids = {it.get("id") for it in items} | {it.get("id") for it in base or []}
    changed = False
    out = []
    for it in items:
        it = copy.deepcopy(it)
        for k in ("defined-by", "agent", "patient", "before", "after"):
            x = it.get(k)
            if isinstance(x, list):
                keep = [r for r in x if not (isinstance(r, str) and _ID.match(r) and r not in ids)]
                if keep != x:
                    changed = True
                    it[k] = keep or {"pending": f"what is {it.get('name')} about?"}
            elif isinstance(x, str) and _ID.match(x) and x not in ids:
                changed = True
                it[k] = {"pending": f"{k}: {x} is not in the fabula"}
        out.append(it)
    if not changed:
        return None
    return Value("fabula", {**{k: x for k, x in cat.items() if k != "nodes"}, "nodes": out}, origin=v.origin)


@implements("file-outline")
def file_outline(ctx: Any, t: Value, **mods: Any) -> Value:
    """`file-outline`, the scaffold of `derive t as code`: the outline's own items for the file and nothing beyond,
    the value marked pending (a model has not read the file)."""
    w = mods.get("with")
    cat, items = _fabula(w, "derive … as code reads a file against its outline: derive t as code with f")
    path = str(t.field("path") or "")
    local = local_outline(items, path)
    if not local:
        raise MoveError(f"{path} is not in the outline: survey the folder first")
    return Value("fabula", reading_value(cat, items, path, copy.deepcopy(local)), state="pending",
                 origin={"reading": {"path": path}})


# ---------------------------------------------------------------------------
# derive repo with f: the fold (asks)
# ---------------------------------------------------------------------------

FOLD_SAYS = ("a YAML mapping: atem {line, focus, push, pull, cites}, and lists aims, audiences, uses, requirements, "
             "decisions, exclusions, influences, occasions; each entry with slug, name, summary, stance, confidence, "
             "sources and the fields of its kind")
DOC_BUDGET = 40_000


def _documents(f: Folder, items: list[dict]) -> str:
    """The repository's own words, for the fold: its README, its other documents and change log, each line
    numbered, longest first cut at `DOC_BUDGET` characters."""
    docs = []
    for e in f.texts():
        if e.path.endswith((".md", ".rst", ".txt")) and not is_licence_file(e.path) and not is_packaging(e.path):
            docs.append(e.path)
    docs.sort(key=lambda p: (not is_readme(p), "/" in p, p))
    out, used = [], 0
    for p in docs:
        body = _numbered(f.text(p))
        if used + len(body) > DOC_BUDGET:
            body = body[: max(0, DOC_BUDGET - used)]
            if not body:
                break
        out.append(f"=== {p}\n{body}")
        used += len(body)
    return "\n\n".join(out) or "(no documents)"


def _fold_outline(items: list[dict]) -> str:
    """The fabulac so far as the fold sees it: every item with its id and kind, its name, summary and the few fields
    that carry meaning (signatures, steps, what a behaviour does), one block per kind."""
    keep = {"interface": ("surface", "signature"), "behaviour": ("of", "when", "does"), "case": ("of",),
            "structure": ("shape",), "setting": ("key", "set-in", "default"), "dependency": ("package", "scope"),
            "component": ("does",), "release": ("version", "at"), "change": ("at", "because"),
            "file": ("path", "holds"), "term": ("sense",), "maker": ("capacity",), "licence": ("identifier",)}
    rows = []
    for it in items:
        k = item_kind(it)
        if k in ("question", "session", "atem", "event"):
            continue
        row = {"id": it.get("id"), "name": it.get("name"), "summary": it.get("summary")}
        for fk in keep.get(k, ()):
            if fk in it:
                row[fk] = it[fk]
        rows.append(row)
    return _yaml(plain(rows))


def fold_folder(ctx: Any, repo: Value, **mods: Any) -> Request:
    """`derive repo with f`: the fold (THYM 20.6): intent and inspiration, and the atem, read as a whole from the
    fabulac so far and the repository's own documents."""
    w = mods.get("with")
    if not isinstance(w, Value) or w.type != "fabula":
        raise MoveError("derive of a folder folds what the stages found: derive repo with f")
    f = _folder_of(repo, "derive")
    cat, items = _fabula(w, "derive of a folder folds what the stages found: derive repo with f")
    _need_fabulac(cat, "f", "derive of a folder folds a fabulac")
    taken = {str(it.get("id")) for it in items}
    paths = {str(it.get("path")) for it in items if item_kind(it) == "file"}
    inputs = {"fabulac": Value("string", "fold"), "name": Value("string", str(cat.get("name") or f.name)),
              "outline": Value("string", _fold_outline(items)), "documents": Value("string", _documents(f, items))}

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        new, atem, cites = parse_fold(data, taken=taken, paths=paths)
        all_ids = taken | {it["id"] for it in new}
        model = model_of(data)
        c2 = copy.deepcopy(cat)
        c2["atem"] = atem
        d = c2.setdefault("derived", {})
        at = stamp_at(ctx)
        read = {s.split("#", 1)[0] for it in items if item_kind(it) in ("behaviour", "structure", "case")
                for s in (it.get("provenance") or {}).get("sources") or []}
        run = {"program": _program(ctx), "run": getattr(ctx, "run", None), "at": at, "model": model}
        d.update({"at": at, "by": d.get("by") or "person", **({"model": model} if model else {}),
                  **({"program": run["program"]} if run["program"] else {}),
                  **({"run": run["run"]} if run["run"] else {}), "mode": "model", "completeness": "full",
                  "chunks": len(read)})
        d.setdefault("runs", []).append({k: v for k, v in run.items() if v})
        bad = [r for it in new for r in _refs(it) if r not in all_ids]
        del bad
        return Value("fabula", {**c2, "nodes": items + new}, origin={"fold": {"atem-cites": cites,
                                                                              "before": sorted(taken)}})

    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": FOLD_SAYS},
                             "repair": ["drop-unresolved-refs"]},
                   inputs=inputs, parse=parse, repair=lambda v, failed: _drop_unresolved_fold(v, failed, taken))


_FOLD_FIELDS = {
    "aim": ("measure", "roles"), "audience": ("who", "needs"), "use": ("for", "via", "steps", "gets"),
    "requirement": ("force", "met-by", "checked-by"), "decision": ("chose", "over", "because", "by", "changed-in"),
    "exclusion": ("horizon", "because"), "influence": ("roles", "how"), "occasion": ("roles", "when"),
}


def _broken_keys(section: str, i: int, row: dict) -> None:
    """A key with no value in an entry is the mark of a flow mapping split at an unquoted comma (`summary: Standard,
    HTML and …` reads as `summary: Standard` and a key `HTML and …`): refused, so the answer is asked again with the
    reason, instead of a summary silently cut short."""
    bad: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            bad.extend(str(k) for k, v in x.items() if v is None and " " in str(k))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(row)
    if bad:
        raise ValueError(f"{section} entry {i} has a key with no value, {bad[0][:60]!r}: a value holding a comma "
                         "inside { } must be quoted")


def parse_fold(data: dict, *, taken: set[str], paths: set[str]) -> tuple[list[dict], dict, list[str]]:
    """The fold's answer as items, the atem and the uses the atem's line cites; ValueError on a shape it cannot
    take. A stance of `observed` stands only on an entry that cites a document's lines; a model's inference is
    `deduced`, `opinion` or `assumed`, its confidence capped by `CONFIDENCE_CAP`."""
    unknown = [k for k in data if k not in FOLD_KINDS and k not in ("atem", "engine")]
    if unknown:
        raise ValueError(f"the answer has sections the fold does not take: {', '.join(map(str, unknown))}")
    a = data.get("atem")
    if not isinstance(a, dict):
        raise ValueError("the answer has no atem: line, focus, push, pull and cites")
    atem = {}
    for k in ("line", "focus", "push", "pull"):
        v = a.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"the atem has no {k}")
        atem[k] = fold(v)
    cites = [str(c) for c in (a.get("cites") or []) if isinstance(c, str)]
    items: list[dict] = []
    used = set(taken)
    for section, (letter, kind) in FOLD_KINDS.items():
        rows = data.get(section) or []
        if not isinstance(rows, list):
            raise ValueError(f"{section} must be a list")
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"{section} entry {i} is not a mapping")
            _broken_keys(section, i, row)
            for need in ("name", "summary"):
                if not isinstance(row.get(need), str) or not row[need].strip():
                    raise ValueError(f"{section} entry {i} has no {need}")
            base = f"{letter}:{kind}/{name_slug(_clean_slug(row.get('slug') or row.get('id') or row['name']).lower())}"
            iid, k = base, 2
            while iid in used:
                iid, k = f"{base}-{k}", k + 1
            used.add(iid)
            if row.get("id") and str(row["id"]) != iid and str(row["id"]) in cites:
                cites = [iid if c == row["id"] else c for c in cites]
            _rename(data, str(row.get("id") or ""), iid)
            sources = [str(s) for s in (row.get("sources") or []) if isinstance(s, (str, int))]
            doc_locs = [s for s in sources if (m := _LOC.match(s)) and m.group("path") in paths]
            st = str(row.get("stance") or "deduced")
            if st not in LADDER:
                st = "deduced"
            if st == "observed" and not doc_locs:
                st = "deduced"
            try:
                conf = float(row.get("confidence"))
            except (TypeError, ValueError):
                conf = 0.6
            conf = round(max(0.1, min(conf, CONFIDENCE_CAP.get(st, 0.5))), 2)
            it: dict = {"id": iid, "type": kind, "name": fold(row["name"])[:120], "summary": fold(row["summary"]),
                        "stance": st}
            for fk in _FOLD_FIELDS[kind]:
                if fk in row and row[fk] not in (None, "", []):
                    it[fk] = plain(row[fk])
            if kind == "requirement" and it.get("force") not in ("must", "should", "may"):
                raise ValueError(f"requirements entry {i} ({row['name']}) has no force: must, should or may")
            if kind == "decision" and not it.get("chose"):
                raise ValueError(f"decisions entry {i} ({row['name']}) has no chose")
            if kind == "exclusion" and it.get("horizon") not in (None, "never", "later") and not mc.is_pending(
                    it.get("horizon")):
                it["horizon"] = {"pending": "is this left out for good, or for now?"}
            for rk in ("via", "met-by", "checked-by", "changed-in"):
                if isinstance(it.get(rk), str):
                    it[rk] = [it[rk]]
            if doc_locs:
                m = _LOC.match(doc_locs[0])
                it["span"] = span(m.group("path"), int(m.group("a")), int(m.group("b") or m.group("a")))
            it["provenance"] = {"mode": "derived", "sources": sources, "confidence": conf,
                                "state": "known" if st in ("observed", "deduced") else "pending"}
            items.append(it)
    return items, atem, cites


def _rename(data: dict, old: str, new: str) -> None:
    """A model's own id for an entry, wherever the answer used it, becomes the id made here."""
    if not old or old == new:
        return
    for section in FOLD_KINDS:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            for k, v in list(row.items()):
                if v == old:
                    row[k] = new
                elif isinstance(v, list):
                    row[k] = [new if x == old else x for x in v]
                elif isinstance(v, dict):
                    row[k] = {kk: (new if vv == old else vv) for kk, vv in v.items()}


def _drop_unresolved_fold(v: Value, failed: list, taken: set[str]) -> Value | None:
    names = {f.get("name") for f in failed}
    if "fabula-checks" not in names:
        return None
    cat, items = fabula_doc(v)
    ids = {it.get("id") for it in items}
    out, changed = [], False
    for it in items:
        if it.get("id") in taken:
            out.append(it)
            continue
        it = copy.deepcopy(it)
        for k in ("for", "via", "met-by", "checked-by", "changed-in", "by"):
            x = it.get(k)
            if isinstance(x, list):
                keep = [r for r in x if not (isinstance(r, str) and _ID.match(r) and r not in ids)]
                if keep != x:
                    changed = True
                    if keep:
                        it[k] = keep
                    else:
                        it.pop(k)
            elif isinstance(x, str) and _ID.match(x) and x not in ids:
                changed = True
                it.pop(k)
        out.append(it)
    if not changed:
        return None
    return Value("fabula", {**{k: x for k, x in cat.items() if k != "nodes"}, "nodes": out}, origin=v.origin)


# ---------------------------------------------------------------------------
# tell f as code: the cshort (asks, once per file)
# ---------------------------------------------------------------------------

def fabulac_file(cat: dict, fab: Value) -> str:
    """The fabulac's file name, as a footer names it: the file it was read from, else `<folder>.fabulac.cosm`."""
    if fab.path is not None and fab.path.name.endswith(".cosm"):
        return fab.path.name
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    p = str(src.get("path") or cat.get("name") or "fabula").rstrip("/")
    return f"{p.rsplit('/', 1)[-1]}.fabulac.cosm"


def rebuilt(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """(the `C:file`s a cshort rebuilds, the rest): every file in a programming language that is not a test, and
    the README (MacroCOSM OES 18.4.7)."""
    files = [it for it in items if item_kind(it) == "file"]
    want = [it for it in files if (it.get("language") == "python" and not is_test(str(it.get("path")))
                                   and not is_tooling(str(it.get("path"))) and str(it.get("path")).endswith(".py"))
            or is_readme(str(it.get("path")))]
    rest = [it for it in files if it not in want]
    return sorted(want, key=lambda it: path_key(str(it["path"]))), rest


def file_brief(items: list[dict], it: dict) -> dict:
    """What one file's request carries (THYM 20.7): the file, its components, its interfaces with their parameters,
    the structures defined in it, the behaviours and cases about them, the settings and dependencies it touches;
    the shared terms and concepts; and the other files' interfaces it may call. For the README: the uses, aims,
    requirements, commands, settings and cases."""
    by = _by_id(items)
    fid = it["id"]
    path = str(it.get("path"))
    if is_readme(path):
        kinds = ("aim", "audience", "use", "requirement", "exclusion", "setting", "dependency", "case", "release",
                 "licence")
        mine = [x for x in items if item_kind(x) in kinds] + [x for x in items if item_kind(x) == "interface"
                                                             and x.get("surface") == "command"]
        return {"file": _compact(it), "items": [_compact(x) for x in mine], "shared": [], "elsewhere": []}
    local = local_outline(items, path)
    lids = {x["id"] for x in local}
    about = [x for x in items if item_kind(x) in ("behaviour", "case", "structure", "event", "claim")
             and (set(_refs(x)) & lids or (isinstance(x.get("span"), dict) and x["span"].get("file") == path))]
    shared = [x for x in items if item_kind(x) in ("term", "concept")]
    comps = [x for x in local if item_kind(x) == "component"]
    used_comps = {u for c in comps for u in c.get("uses") or [] if u.startswith("C:component/")}
    elsewhere = [{"id": x["id"], "signature": x.get("signature"), "in": by.get(str(x.get("defined-in")), {}).get("path")}
                 for x in items if item_kind(x) == "interface" and x.get("defined-in") != fid and (
                     not used_comps or any(by.get(c, {}).get("files") and x.get("defined-in") in by[c]["files"]
                                           for c in used_comps))]
    return {"file": _compact(it), "items": [_compact(x) for x in local[1:] + about],
            "shared": [_compact(x) for x in shared], "elsewhere": elsewhere}


def _failed_paths(failed: list, paths: list[str]) -> set[str]:
    out = set()
    for f in failed or []:
        why = str(f.get("why") or "")
        out |= {p for p in paths if p in why}
    return out


def tell_code(ctx: Any, fab: Value, **mods: Any) -> Value:
    """`tell f as code`: the cshort (THYM 20.7): one request per file it rebuilds, the files assembled into a folder
    with `CSHORT.md`. Called again with what failed, it asks again only for the files the failures name."""
    cat, items = _fabula(fab, "tell … as code tells a fabulac")
    _need_fabulac(cat, "f", "only a fabulac is told as code")
    want, rest = rebuilt(items)
    if not [x for x in want if x.get("language") == "python"]:
        raise MoveError("the fabulac names no Python file to rebuild")
    paths = [str(x["path"]) for x in want]
    prev = getattr(ctx, "previous", None)
    texts: dict[str, str] = {}
    meta = {}
    if isinstance(prev, Value) and isinstance(prev.payload, Folder):
        texts = {p: prev.payload.text(p) for p in paths if prev.payload.entry(p) is not None}
        meta = dict((prev.origin or {}).get("cshort") or {})
    redo = _failed_paths(getattr(ctx, "failed", None) or [], paths) if texts else set(paths)
    if texts and not redo:
        redo = set(paths)
    name = str(cat.get("name") or "the program")
    for it in want:
        p = str(it["path"])
        if p not in redo and p in texts:
            continue
        brief = file_brief(items, it)
        inputs = {"fabulac": Value("string", "readme" if is_readme(p) else "code"), "path": Value("string", p),
                  "name": Value("string", name), "brief": Value("string", _yaml(plain(brief))),
                  "atem": Value("string", _yaml(plain(cat.get("atem") or {})))}
        cand = ctx.ask({"schema": {"format": "markdown", "says": f"the whole of {p}, nothing else"}}, inputs)
        out = cand.get("output") if isinstance(cand, dict) else None
        texts[p] = _file_text(out)
        eng = str(cand.get("engine") or "") if isinstance(cand, dict) else ""
        if eng.startswith("model:") and eng[6:] not in ("", "unknown"):
            meta.setdefault("model", eng[6:])
        for k in ("route", "provider"):
            if isinstance(cand, dict) and cand.get(k):
                meta.setdefault(k, cand[k])
    syn = engine(ctx, "syntax")
    syntax = {}
    for p in paths:
        if p.endswith(".py"):
            ol = syn.outline(p, texts[p])
            syntax[p] = {"sha256": hashlib.sha256(texts[p].encode("utf-8")).hexdigest(), "outline": ol}
    readme_rows = [(str(x["path"]), x["id"]) for x in want]
    texts["CSHORT.md"] = cshort_md(ctx, cat, fab, readme_rows, texts, rest, meta)
    folder = folder_of_texts(f"{fabulac_file(cat, fab).rsplit('.fabulac.cosm', 1)[0]}.cshort/", texts)
    return Value("folder", folder, origin={"cshort": {**meta, "syntax": syntax, "day": utc_day(ctx)}})


def _file_text(out: Any) -> str:
    s = out if isinstance(out, str) else (_yaml(out) if isinstance(out, dict) else str(out or ""))
    s = s.replace("\r\n", "\n")
    m = re.match(r"^\s*```[A-Za-z0-9_+-]*\n(.*?)\n?```\s*$", s, re.S)
    if m:
        s = m.group(1)
    return s.rstrip("\n") + "\n"


def folder_of_texts(path: str, texts: dict[str, str]) -> Folder:
    from enough.thym.folder import Entry
    entries = []
    for p in sorted(texts, key=path_key):
        b = texts[p].encode("utf-8")
        entries.append(Entry(p, hashlib.sha256(b).hexdigest(), len(b), False, True))
    return Folder(path, tuple(entries), digest_of([(e.path, e.sha256) for e in entries]), root=None,
                  _texts=dict(texts))


def licence_line(cat: dict) -> str:
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    lic = src.get("licence")
    if isinstance(lic, str) and lic.strip():
        return f"Licence of the source: {lic.strip()}"
    q = lic.get("pending") if isinstance(lic, dict) else None
    return f"Licence of the source: not recorded ({q or 'a question for the maker'})"


def _who(meta: dict) -> str:
    who = str(meta.get("model") or "a model")
    extra = ", ".join(str(meta[k]) for k in ("route", "provider") if meta.get(k))
    return f"{who} ({extra})" if extra else who


def cshort_md(ctx: Any, cat: dict, fab: Value, rows: list[tuple[str, str]], texts: dict, rest: list[dict],
              meta: dict) -> str:
    """`CSHORT.md` (MacroCOSM OES 18.4.7): the footer line first, the files written with their `C:file` and sha256,
    what was not rebuilt, and last the source's licence line."""
    head = (f"*a cshort of {fabulac_file(cat, fab)}, in Python, compiled on {utc_day(ctx)} by {_who(meta)}; "
            "never run*")
    out = [head, "", "| file | from | sha256 |", "|---|---|---|"]
    for p, fid in rows:
        out.append(f"| {p} | {fid} | {hashlib.sha256(texts[p].encode('utf-8')).hexdigest()} |")
    out.append("")
    if rest:
        out.append("Not rebuilt: " + ", ".join(str(x["path"]) for x in sorted(rest, key=lambda x: path_key(
            str(x["path"])))) + ".")
        out.append("")
    out.append(licence_line(cat))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# tell f as line | overview | manual: the catem
# ---------------------------------------------------------------------------

CATEM_SAYS = ("a YAML mapping: intro, a list of sentences; sections, a list of {heading, sentences}; every sentence "
              "{say, cites}")


def reached(items: list[dict]) -> list[dict]:
    """The interfaces a person reaches (THYM 20.7): the command lines and formats; and the exported functions and
    classes, when the program has no command line (a library's public interface)."""
    cmds = [it for it in items if item_kind(it) == "interface" and it.get("surface") in ("command", "format")]
    if cmds:
        return cmds
    return [it for it in items if item_kind(it) == "interface" and it.get("surface") in ("function", "class")
            and it.get("exported") is not False]


def must_tell(items: list[dict], depth: str) -> list[str]:
    uses = [it["id"] for it in items if item_kind(it) == "use"]
    if depth == "manual":
        return uses + [it["id"] for it in reached(items)]
    return uses if depth == "overview" else []


def catem_footer(cat: dict, fab: Value, depth: str, day: str, who: str) -> str:
    return f"*a catem of {fabulac_file(cat, fab)}, at depth {depth}, compiled on {day} by {who}*"


def _catem_outline(items: list[dict], depth: str) -> str:
    kinds = {"use", "aim", "audience", "requirement", "exclusion", "setting", "case", "behaviour", "event"}
    rows = [_compact(it) for it in items if item_kind(it) in kinds]
    rows += [_compact(it) for it in reached(items)]
    return _yaml(plain(rows))


def tell_catem(ctx: Any, fab: Value, depth: str, **mods: Any) -> Request | Value:
    """`tell f as line | overview | manual`: the catem (THYM 20.7). `line` is the atem's line, asked of no model;
    the other two are told, sentence by sentence with the ids each says, and composed under headings."""
    cat, items = _fabula(fab, f"tell … as {depth} tells a fabulac")
    _need_fabulac(cat, "f", "a catem is told from a fabulac")
    atem = cat.get("atem") if isinstance(cat.get("atem"), dict) else {}
    uses = [it["id"] for it in items if item_kind(it) == "use"]
    if depth == "line":
        line = atem.get("line")
        if not isinstance(line, str) or not line.strip():
            raise MoveError("the fabulac has no atem line yet: fold it first (derive repo with f)")
        foot = catem_footer(cat, fab, "line", utc_day(ctx), "rules, from its atem")
        cites = uses or [it["id"] for it in items if item_kind(it) == "aim"][:3]
        return short_value(f"{fold(line)}\n\n{foot}\n", fabula=fab, sentences=[fold(line)], covers=[cites],
                           order="told", depth="line")
    inputs = {"fabulac": Value("string", "catem"), "depth": Value("string", depth),
              "name": Value("string", str(cat.get("name") or "the program")),
              "atem": Value("string", _yaml(plain(atem))), "outline": Value("string", _catem_outline(items, depth)),
              "must": Value("string", _yaml(must_tell(items, depth)))}

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        intro, sections = _catem_answer(data)
        model = model_of(data)
        foot = catem_footer(cat, fab, depth, utc_day(ctx), model or "a model")
        name = str(cat.get("name") or "the program")
        md = [f"# What you can do with {name}", ""]
        sents, covers = [], []
        if intro:
            md.append(" ".join(s for s, _ in intro))
            md.append("")
            for s, c in intro:
                sents.append(s)
                covers.append(c)
        for heading, rows in sections:
            md += [f"## {heading}", "", " ".join(s for s, _ in rows), ""]
            for s, c in rows:
                sents.append(s)
                covers.append(c)
        md.append(foot)
        return short_value("\n".join(md) + "\n", fabula=fab, sentences=sents, covers=covers, order="told",
                           depth=depth)
    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": CATEM_SAYS}, "repair": []},
                   inputs=inputs, parse=parse)


def _sentence(row: Any) -> tuple[str, list[str]]:
    if isinstance(row, str):
        say, cites = row, []
    elif isinstance(row, dict):
        say, cites = row.get("say") or "", row.get("cites") or []
    else:
        raise ValueError("a sentence is a mapping {say, cites}")
    say = fold(say)
    if not say:
        raise ValueError("a sentence says nothing")
    if say[-1] not in ".!?…\"”'’)`":
        say += "."
    if isinstance(cites, str):
        cites = [c for c in re.split(r"[,\s]+", cites) if c]
    return say, [fold(c) for c in cites if fold(c)]


def _catem_answer(data: dict) -> tuple[list, list]:
    intro = [_sentence(r) for r in (data.get("intro") or [])]
    sections = []
    for i, sec in enumerate(data.get("sections") or [], 1):
        if not isinstance(sec, dict) or not isinstance(sec.get("heading"), str):
            raise ValueError(f"section {i} has no heading")
        rows = [_sentence(r) for r in sec.get("sentences") or []]
        if not rows:
            raise ValueError(f"section {i} ({sec['heading']}) has no sentences")
        sections.append((fold(sec["heading"]), rows))
    if not intro and not sections:
        raise ValueError("the answer holds no sentences")
    return intro, sections


@implements("uses-outline")
def uses_outline(ctx: Any, fab: Value, **mods: Any) -> Value:
    """`uses-outline`, the catem's scaffold: the uses and the interfaces a person reaches, in told order, in their
    own words, with a footer that says rules made it."""
    depth = mods.get("as") if mods.get("as") in CATEM_DEPTHS else "overview"
    cat, items = _fabula(fab, "a catem is told from a fabulac")
    _need_fabulac(cat, "f", "a catem is told from a fabulac")
    name = str(cat.get("name") or "the program")
    md, sents, covers = [f"# What you can do with {name}", ""], [], []
    atem = cat.get("atem") if isinstance(cat.get("atem"), dict) else {}
    if depth == "line":
        line = atem.get("line") if isinstance(atem.get("line"), str) else f"{name}, as its outline lists it."
        md = [fold(line), ""]
        sents, covers = [fold(line)], [[]]
    else:
        rows = [it for it in items if item_kind(it) == "use"]
        if depth == "manual":
            rows += reached(items)
        for it in rows:
            s = fold(it.get("summary") or it.get("name") or it["id"])
            md += [f"## {fold(it.get('name') or it['id'])}", "", s, ""]
            if it.get("steps"):
                md += [f"    {fold(x)}" for x in it["steps"] if isinstance(x, str)] + [""]
            if it.get("signature"):
                md += [f"    {it['signature']}", ""]
            sents.append(s)
            covers.append([it["id"]])
    md.append(catem_footer(cat, fab, depth, utc_day(ctx), "rules, without a model"))
    v = short_value("\n".join(md) + "\n", fabula=fab, sentences=sents, covers=covers, order="told", depth=depth)
    v.state = "pending"
    return v


# ---------------------------------------------------------------------------
# The checks (THYM 7.3; MacroCOSM OES 18.4.8)
# ---------------------------------------------------------------------------

def _first(inputs: dict, *types: str) -> Value | None:
    for v in inputs.values():
        if isinstance(v, Value) and v.type in types:
            return v
    return None


def _with_fabula(inputs: dict) -> Value | None:
    w = inputs.get("with")
    if isinstance(w, Value) and w.type == "fabula":
        return w
    return _first(inputs, "fabula")


@check("files-found")
def _files_found(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every file the folder rule keeps has a `C:file` whose sha256 is the file's, and no `C:file` names a file the
    tree lacks (THYM 7.3)."""
    repo = _first(inputs, "folder")
    if repo is None or not isinstance(repo.payload, Folder):
        return False, "no folder to find the files of"
    _cat, items = fabula_doc(output)
    files = _file_items(items)
    for e in repo.payload.entries:
        it = files.get(e.path)
        if it is None:
            return False, f"{e.path} has no C:file item"
        if it.get("sha256") != e.sha256:
            return False, f"{e.path}: its C:file says sha256 {str(it.get('sha256'))[:12]}…, the file's is {e.sha256[:12]}…"
    have = {e.path for e in repo.payload.entries}
    extra = [p for p in files if p not in have]
    if extra:
        return False, f"C:file {extra[0]} names a file the folder does not hold"
    return True, ""


def code_span_problem(items: list[dict], tree: set[str] | None = None, more_files: list[dict] | None = None) -> str | None:
    """MacroCOSM OES 18.4.8's `code-span`, read as THYM 7.3 has it: every span is `{file, lines}`, its file a
    `C:file`'s path (and, with the tree, a file of the tree), its lines `n` or `n-m`, n ≤ m, inside the file. A
    reading's spans are read against the files of the fabula it was read with (`more_files`)."""
    files = {**_file_items(more_files or []), **_file_items(items)}
    for it in items:
        sp = it.get("span")
        if sp is None:
            continue
        iid = it.get("id")
        if not isinstance(sp, dict) or "file" not in sp or "lines" not in sp:
            return f"{iid}: a span in a fabulac is {{file, lines}}"
        f = str(sp["file"])
        if f not in files:
            return f"{iid}: its span names {f}, which is no C:file of the fabulac"
        if tree is not None and f not in tree:
            return f"{iid}: its span names {f}, which the folder does not hold"
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(sp["lines"]))
        if not m:
            return f"{iid}: its span's lines {sp['lines']!r} are not n or n-m"
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        n = ((files[f].get("length") or {}).get("lines")) if isinstance(files[f].get("length"), dict) else None
        if a < 1 or b < a:
            return f"{iid}: its span's lines {sp['lines']} are not a range from 1"
        if isinstance(n, int) and b > n:
            return f"{iid}: its span's lines {sp['lines']} lie outside {f}, which has {n} lines"
    return None


@check("code-span")
def _code_span(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every code span `{file, lines}` names a file of the tree and lines inside it (THYM 7.3)."""
    _cat, items = fabula_doc(output)
    repo = _first(inputs, "folder")
    tree = {e.path for e in repo.payload.entries} if repo is not None and isinstance(repo.payload, Folder) else None
    w = _with_fabula(inputs) if (output.origin or {}).get("reading") else None
    files = [it for it in fabula_doc(w)[1] if item_kind(it) == "file"] if w is not None else []
    why = code_span_problem(items, tree, files)
    return (False, why) if why else (True, "")


@check("licence-recorded")
def _licence_recorded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The fabulac's `source.licence` is a value or a question, never absent, and it holds an `R:licence` item
    (THYM 7.3; MacroCOSM OES 18.4.8). A question holds, and says so: a viewer shows it as one."""
    cat, items = fabula_doc(output)
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    lic = src.get("licence")
    if lic is None or (isinstance(lic, str) and not lic.strip()):
        return False, "source.licence is absent: record the licence, or the question of it"
    if not any(item_kind(it) == "licence" for it in items):
        return False, "the fabulac holds no R:licence item"
    if mc.is_pending(lic):
        return True, f"the licence is a question: {lic.get('pending')}"
    if not isinstance(lic, str):
        return False, "source.licence is neither a licence nor a question"
    return True, ""


def _owner_files(items: list[dict]) -> dict[str, str]:
    """Each interface's and component's file path."""
    by = _by_id(items)
    out = {}
    for it in items:
        k = item_kind(it)
        if k in ("interface", "structure"):
            p = (by.get(str(it.get("defined-in"))) or {}).get("path")
            if p:
                out[it["id"]] = str(p)
        elif k == "component":
            fs = [by.get(x, {}).get("path") for x in it.get("files") or []]
            if len(fs) == 1 and fs[0]:
                out[it["id"]] = str(fs[0])
    return out


def _reading_parts(output: Value, inputs: dict) -> tuple[list[dict], list[dict], str | None]:
    """(the reading's new items, the outline's items, the file read)."""
    _cat, items = fabula_doc(output)
    w = _with_fabula(inputs)
    before = {it.get("id") for it in fabula_doc(w)[1]} if w is not None else set()
    new = [it for it in items if it.get("id") not in before]
    path = ((output.origin or {}).get("reading") or {}).get("path")
    if path is None:
        t = _first(inputs, "text")
        path = str(t.field("path")) if t is not None and t.field("path") else None
    return new, (fabula_doc(w)[1] if w is not None else items), path


@check("outline-cited")
def _outline_cited(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every behaviour, structure and case a file's reading gives names the interfaces or components of the outline
    it is about, and they belong to that file (THYM 7.3). A test file's cases test other files: they name the
    outline's interfaces, components or behaviours of any file."""
    if output.state == "pending":
        return True, "a scaffold gives the outline's own items"
    new, outline, path = _reading_parts(output, inputs)
    owners = _owner_files(outline)
    test = is_test(path or "")
    for it in new:
        k = item_kind(it)
        if k not in ("behaviour", "structure", "case"):
            continue
        if k == "structure":
            continue                                   # defined in the file read: its span says where
        of = it.get("of")
        cited = [r for r in (of if isinstance(of, list) else [of]) if isinstance(r, str)]
        outline_ids = [r for r in cited if r in owners]
        if not outline_ids:
            if test and k == "case" and any(r for r in cited):
                continue
            return False, (f"{it.get('id')} names no interface or component of the outline"
                           + (f" (it names {', '.join(cited)})" if cited else ""))
        if not test:
            other = [r for r in outline_ids if owners[r] != path]
            if other:
                return False, f"{it.get('id')} names {other[0]}, which belongs to {owners[other[0]]}, not {path}"
    return True, ""


def code_coverage(output: Value, inputs: dict) -> tuple[bool, str]:
    """`coverage` read for a file's reading (THYM 20.6): every interface and component the outline lists for the
    file is the subject of a behaviour or a structure."""
    if output.state == "pending":
        return True, "a scaffold makes no coverage promise: a model has not read the file"
    new, outline, path = _reading_parts(output, inputs)
    if path is None:
        return False, "no file to read the coverage of"
    local = local_outline(outline, path)
    subjects = {r for it in new if item_kind(it) == "behaviour" for r in (it.get("of") or []) if isinstance(r, str)}
    struct_names = {str(it.get("id")).split("/", 1)[1] for it in new + outline if item_kind(it) == "structure"}
    missing = []
    for it in local:
        k = item_kind(it)
        if k not in ("interface", "component"):
            continue
        tail = str(it["id"]).split("/", 1)[1]
        if it["id"] in subjects or tail in struct_names:
            continue
        missing.append(it["id"])
    if missing:
        return False, (f"{path}: {len(missing)} of the outline's interfaces and components is the subject of no "
                       f"behaviour or structure: {', '.join(missing[:6])}")
    return True, ""


@check("fold-grounded")
def _fold_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every intent and inspiration item the fold gives cites at least one item of the fabula so far (an id, or a
    locator into one of its files), an `observed` one cites a document's lines, and the atem's line cites at least
    one use (THYM 7.3)."""
    w = _with_fabula(inputs)
    if w is None:
        return False, "no fabula so far to ground the fold in"
    _c0, before_items = fabula_doc(w)
    before = {str(it.get("id")) for it in before_items}
    paths = {str(it.get("path")) for it in before_items if item_kind(it) == "file"}
    _cat, items = fabula_doc(output)
    new = [it for it in items if str(it.get("id")) not in before and str(it.get("id"))[:1] in ("N", "I")]
    for it in new:
        srcs = [str(s) for s in ((it.get("provenance") or {}).get("sources") or [])]
        refs = [r for r in _refs(it) if r in before]
        locs = [s for s in srcs if (m := _LOC.match(s)) and m.group("path") in paths]
        ids = [s for s in srcs if s in before]
        if not (refs or locs or ids):
            return False, f"{it.get('id')} cites nothing the fabulac or its documents hold"
        if it.get("stance") == "observed" and not locs:
            return False, f"{it.get('id')} is observed but cites no document's lines; say deduced"
    uses = {it["id"] for it in items if item_kind(it) == "use"}
    cites = ((output.origin or {}).get("fold") or {}).get("atem-cites")
    if cites is None:
        return False, "the atem's line says no use it rests on"
    if uses and not set(cites) & uses:
        return False, "the atem's line cites no use"
    return True, ""


@check("history-grounded")
def _history_grounded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every change cites commits the clone's log answered, every release a tag it answered, every maker a name in
    those commits (THYM 7.3)."""
    g = (output.origin or {}).get("history")
    if not isinstance(g, dict):
        return False, "the fabula carries no record of what the clone's log answered"
    commits, tags = set(g.get("commits") or []), set(g.get("tags") or [])
    w = _with_fabula(inputs)
    before = {str(it.get("id")) for it in fabula_doc(w)[1]} if w is not None else set()
    _cat, items = fabula_doc(output)
    for it in items:
        if str(it.get("id")) in before:
            continue
        k = item_kind(it)
        srcs = [str(s) for s in ((it.get("provenance") or {}).get("sources") or [])]
        if k == "change":
            if it.get("commit") not in commits:
                return False, f"{it.get('id')} cites the commit {str(it.get('commit'))[:12]}, which the log did not answer"
        elif k == "release":
            if it.get("tag") not in tags:
                return False, f"{it.get('id')} cites the tag {it.get('tag')}, which the clone does not have"
        elif k == "maker":
            shas = [s.split(":", 1)[1] for s in srcs if s.startswith("commit:")]
            if not shas or not set(shas) <= commits:
                return False, f"{it.get('id')} rests on no commit the log answered"
            if "@" in str(it.get("name")) or "@" in str(it.get("summary")):
                return False, f"{it.get('id')} carries an address"
    return True, ""


def _cshort_parts(output: Value, inputs: dict) -> tuple[Folder | None, dict, list[dict], Value | None]:
    fab = _first(inputs, "fabula")
    if fab is None:
        t = telling_of(output)
        fab = t.get("fabula") if t else None
    f = output.payload if isinstance(output.payload, Folder) else None
    cat, items = fabula_doc(fab) if fab is not None else ({}, [])
    return f, cat, items, fab


def _syntax_of(output: Value, ctx: Any, path: str, text: str) -> dict:
    """The syntax engine's outline of a cshort file: the one the move recorded when the text is the same, else
    asked of the engine now."""
    rec = (((output.origin or {}).get("cshort") or {}).get("syntax") or {}).get(path)
    if isinstance(rec, dict) and rec.get("sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest():
        return rec.get("outline") or {}
    syn = (getattr(ctx, "engines", None) or {}).get("syntax")
    if syn is None:
        return {"ok": None, "why": "the syntax engine is not here"}
    return syn.outline(path, text)


@check("parses")
def _parses(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every file of the cshort in a language the fabulac names is read by that language's parser without a syntax
    error; parsing is not running (THYM 7.3, 20.8)."""
    f, _cat, _items, _fab = _cshort_parts(output, inputs)
    if f is None:
        return False, "the output is not a folder"
    bad = []
    for e in f.entries:
        if not e.path.endswith(".py"):
            continue
        ol = _syntax_of(output, ctx, e.path, f.text(e.path))
        if ol.get("ok") is None:
            return False, f"{e.path} could not be parsed: {ol.get('why')}"
        if not ol.get("ok"):
            bad.append(f"{e.path}: line {ol.get('line')}: {ol.get('message')}")
    if bad:
        return False, "; ".join(bad[:5])
    return True, ""


def _sig_names(takes: Any) -> list[str]:
    return [str(t.get("name")).lstrip("*") for t in takes or [] if isinstance(t, dict) and t.get("name")]


@check("interfaces-present")
def _interfaces_present(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every interface of the fabulac is defined in the cshort's file it is defined in, with the same name, the same
    kind and the same parameter names in the same order (THYM 7.3), read from the syntax engine's outline."""
    f, _cat, items, _fab = _cshort_parts(output, inputs)
    if f is None:
        return False, "the output is not a folder"
    by = _by_id(items)
    problems = []
    for it in items:
        if item_kind(it) != "interface":
            continue
        fi = by.get(str(it.get("defined-in"))) or {}
        path = str(fi.get("path") or "")
        if not path or is_test(path) or fi.get("language") != "python":
            continue
        if f.entry(path) is None:
            problems.append(f"{path}: the file is missing, so {it['id']} is not there")
            continue
        ol = _syntax_of(output, ctx, path, f.text(path))
        if not ol.get("ok"):
            problems.append(f"{path}: it does not parse, so {it['id']} cannot be found")
            continue
        surface = it.get("surface")
        if surface == "command":
            why = _command_present(it, ol)
        elif surface in ("function", "method", "class"):
            why = _def_present(it, ol)
        else:
            why = None
        if why:
            problems.append(f"{path}: {why}")
    if problems:
        return False, "; ".join(problems[:6]) + (f" (and {len(problems) - 6} more)" if len(problems) > 6 else "")
    return True, ""


def _def_present(it: dict, ol: dict) -> str | None:
    qual = str(it.get("name"))
    want = it.get("surface")
    d = next((x for x in ol.get("defs") or [] if x.get("qual") == qual), None)
    if d is None:
        return f"{qual} ({it['id']}) is not defined"
    if d.get("kind") != want:
        return f"{qual} is a {d.get('kind')}, and the fabulac says {want}"
    if want == "class":
        return None
    have = [str(p.get("name")) for i, p in enumerate(d.get("params") or [])
            if not (want == "method" and i == 0 and p.get("name") in ("self", "cls"))]
    need = _sig_names(it.get("takes"))
    if have != need:
        return f"{qual} takes ({', '.join(have)}), and the fabulac says ({', '.join(need)})"
    return None


def _command_present(it: dict, ol: dict) -> str | None:
    parsers = ol.get("argparse") or []
    name = str(it.get("name"))
    parts = name.split()
    target = None
    for p in parsers:
        if len(parts) > 1 and p.get("command") == parts[-1]:
            target = p
            break
        if not p.get("parent") and (p.get("prog") == name or len(parts) == 1 or name.startswith("python ")):
            target = target or p
    if target is None:
        return f"the command line {name} ({it['id']}) is not built there"
    have = {n for a in target.get("args") or [] for n in a.get("names") or []}
    if target.get("subcommands"):
        have.add(str((target["subcommands"] or {}).get("dest") or "command"))
    missing = [n for n in _sig_names(it.get("takes")) if n not in have and n != "command"]
    if missing:
        return f"the command line {name} has no {', '.join(missing)}"
    return None


@check("files-present")
def _files_present(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The cshort holds every file it is required to rebuild, at its path, with `CSHORT.md`, and the digests
    `CSHORT.md` lists are the files' (THYM 7.3)."""
    f, _cat, items, _fab = _cshort_parts(output, inputs)
    if f is None:
        return False, "the output is not a folder"
    want, _rest = rebuilt(items)
    missing = [str(x["path"]) for x in want if f.entry(str(x["path"])) is None]
    if missing:
        return False, f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing"
    if f.entry("CSHORT.md") is None:
        return False, "CSHORT.md is missing"
    listed = re.findall(r"^\| (.+?) \| .+? \| ([0-9a-f]{64}) \|$", f.text("CSHORT.md"), re.M)
    for p, sha in listed:
        e = f.entry(p)
        if e is None:
            return False, f"CSHORT.md lists {p}, which is not there"
        if e.sha256 != sha:
            return False, f"CSHORT.md lists {p} with another sha256 than the file's"
    if {p for p, _ in listed} != {str(x["path"]) for x in want}:
        return False, "CSHORT.md does not list exactly the files rebuilt"
    return True, ""


_CSHORT_FOOT = re.compile(r"^\*a cshort of (?P<f>\S.*?), in (?P<lang>[A-Za-z][\w+ #-]*), compiled on "
                          r"(?P<day>\d{4}-\d{2}-\d{2}) by (?P<who>.+); never run\*$")
_CATEM_FOOT = re.compile(r"^\*a catem of (?P<f>\S.*?), at depth (?P<depth>line|overview|manual), compiled on "
                         r"(?P<day>\d{4}-\d{2}-\d{2}) by (?P<who>.+)\*$")


def footer_problem(output: Value, inputs: dict, ctx: Any) -> str | None:
    """`footer` for a cshort and a catem (THYM 7.3, MacroCOSM OES 18.4.7). A cshort: `CSHORT.md`'s first line names
    the fabulac's file, the language, the run's day in UTC and the model, and its last line is the licence line,
    agreeing with `source.licence`. A catem: it ends with the line that names its depth."""
    f, cat, _items, fab = _cshort_parts(output, inputs)
    if f is not None:
        if f.entry("CSHORT.md") is None:
            return "CSHORT.md is missing"
        lines = [ln for ln in f.text("CSHORT.md").split("\n") if ln.strip()]
        m = _CSHORT_FOOT.match(lines[0]) if lines else None
        if not m:
            return f"CSHORT.md's first line is not a cshort's footer: {lines[0][:80] if lines else ''}"
        if fab is not None and m.group("f") != fabulac_file(cat, fab):
            return f"the footer names {m.group('f')}, not {fabulac_file(cat, fab)}"
        if m.group("day") != utc_day(ctx):
            return f"the footer's day is {m.group('day')}, the run's {utc_day(ctx)}"
        if fab is not None and lines[-1] != licence_line(cat):
            return f"CSHORT.md's last line is not the licence line: {lines[-1][:80]}"
        return None
    t = telling_of(output)
    lines = [ln.strip() for ln in output.text().replace("\r\n", "\n").split("\n") if ln.strip()]
    m = _CATEM_FOOT.match(lines[-1]) if lines else None
    if not m:
        return f"the last line is not a catem's footer: {lines[-1][:80] if lines else ''}"
    depth = (t or {}).get("depth")
    if depth and m.group("depth") != depth:
        return f"the footer says depth {m.group('depth')}, and the catem is told at {depth}"
    return None


def is_code_telling(output: Value) -> bool:
    """A cshort (a folder) or a catem (a short that carries its depth): what `footer` reads with this module's rule."""
    return isinstance(output.payload, Folder) or bool((telling_of(output) or {}).get("depth"))


@check("uses-told")
def _uses_told(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A catem tells everything its depth asks for: at `overview` every use, at `manual` every use and every
    interface a person reaches (THYM 7.3)."""
    t = telling_of(output) or {}
    depth = t.get("depth")
    fab = t.get("fabula") if isinstance(t.get("fabula"), Value) else _first(inputs, "fabula")
    if depth not in CATEM_DEPTHS or fab is None:
        return False, "the telling is no catem"
    _cat, items = fabula_doc(fab)
    told = {c for cs in t.get("covers") or [] for c in cs}
    missing = [i for i in must_tell(items, depth) if i not in told]
    if missing:
        return False, f"the catem at depth {depth} does not tell {', '.join(missing[:6])}"
    return True, ""


@check("flavour")
def _flavour(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The fabula's flavour is one the move takes: only a fabulac is told as code or at a catem's depth (THYM 7.3)."""
    fab = _first(inputs, "fabula")
    if fab is None:
        return True, ""
    fl = flavour_of(fabula_doc(fab)[0])
    as_ = ((node or {}).get("modifiers") or {}).get("as")
    if (as_ == "code" or as_ in CATEM_DEPTHS) and fl != "fabulac":
        return False, f"the fabula is a {fl}; only a fabulac is told as {as_}"
    return True, ""


def atem_of(output: Value) -> dict | None:
    """A fabula's atem (its catalog's), for `atem-shape` on the fold's output."""
    if output.type != "fabula":
        return None
    cat, _items = fabula_doc(output)
    a = cat.get("atem")
    return a if isinstance(a, dict) else {}


def joined(output: Value, inputs: dict) -> Value | None:
    """A file's reading laid into the fabula it was read with (`gather`'s merge), or None when the output is no
    reading: the volume a reading's `fabula-checks` lints, since a reading holds only what it adds."""
    if not (output.origin or {}).get("reading") or output.type != "fabula":
        return None
    w = _with_fabula(inputs)
    if w is None:
        return None
    from enough.thym.moves.edit import MergeConflict, merge_nodes
    cat, base = fabula_doc(w)
    _c, mine = fabula_doc(output)
    try:
        nodes = merge_nodes([plain(n) for n in base], [[plain(n) for n in mine]])
    except MergeConflict as e:
        raise ValueError(f"the reading cannot be laid into its fabula: {e}") from None
    return Value("fabula", {**{k: plain(v) for k, v in cat.items() if k != "nodes"}, "nodes": nodes})


_CORE_FABULA_CHECKS = getattr(_CHECKS.lookup("fabula-checks"), "_core", None) or _CHECKS.lookup("fabula-checks")


@check("emf-checks")
@check("fabula-checks")
def _fabula_checks_joined(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`fabula-checks` (THYM 7.3), as the core runs it; for a file's reading (`derive t as code with f`), on the
    reading together with the fabula it was read with, since a reading holds only what it adds for its file and its
    references resolve in that fabula (docs/fabula-landed-T1-code.md, the follow-up pass)."""
    try:
        whole = joined(output, inputs)
    except ValueError as e:
        return False, str(e)
    return _CORE_FABULA_CHECKS(whole if whole is not None else output, inputs, node, decl, ctx)


_fabula_checks_joined._core = _CORE_FABULA_CHECKS          # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Dispatch: what `derive` and `tell` hand on to this module (emf.py calls these)
# ---------------------------------------------------------------------------

def derive_branch(ctx: Any, x: Value, mods: dict) -> Any:
    """The code branch of `derive` for this call, or None when the call is a text read as prose or verse."""
    if isinstance(x, Value) and x.type == "folder":
        return fold_folder(ctx, x, **mods)
    if mods.get("as") == "code":
        return read_file(ctx, x, **mods)
    return None


def derive_scaffold_branch(ctx: Any, x: Value, mods: dict) -> Any:
    if isinstance(x, Value) and x.type == "folder":
        raise MoveError("derive of a folder has no scaffold: nothing but a model reads intent, so a run with --rules "
                        "cannot fold it")
    if mods.get("as") == "code":
        return file_outline(ctx, x, **mods)
    return None


def tell_branch(ctx: Any, x: Value, mods: dict) -> Any:
    a = mods.get("as")
    if a == "code":
        return tell_code(ctx, x, **mods)
    if a in CATEM_DEPTHS:
        return tell_catem(ctx, x, a, **mods)
    if isinstance(x, Value) and x.type == "fabula" and flavour_of(fabula_doc(x)[0]) == "fabulac" and a is None:
        return None
    return None


def tell_scaffold_branch(ctx: Any, x: Value, mods: dict) -> Any:
    a = mods.get("as")
    if a == "code":
        raise MoveError("tell … as code has no scaffold: only a model writes code, so a run with --rules cannot tell "
                        "it")
    if a in CATEM_DEPTHS:
        return uses_outline(ctx, x, **mods)
    return None


__all__ = ["BAND_FILES", "BAND_LINES", "CHUNK_LINES", "atem_of", "chunks_of", "code_coverage", "code_span_problem",
           "derive_branch", "derive_scaffold_branch", "file_brief", "file_outline", "fold_folder", "footer_problem",
           "history", "is_code_telling", "is_test", "local_outline", "module_name", "must_tell", "parse_fold",
           "parse_reading", "read_file", "read_licence", "rebuilt", "slug", "survey", "tell_branch", "tell_catem",
           "tell_code", "tell_scaffold_branch", "uses_outline"]
