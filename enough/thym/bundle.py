"""What the page's runtime reads: a plan, its program and its inputs as one JSON document (the 0.7 build's in-page
runtime, `enough/static/thym/`, THYM 12.6).

The page cannot read the disk, so the host reads every input the way `run` does (`values.load_input`, with the same
plan-time refusals for a missing or changed input) and hands the page what it read: a text's bytes, a `.cosm`
mapping, a folder volume's catalog and items (with each item's module name, which the manifest says), a folder's
files with their digests and texts, a list's members. The page's runtime then walks the plan exactly as `run` walks
it in agent-free mode, and lands its outputs in memory.

JSON has no dates, no floats apart from numbers, and no mapping keys that are not strings; YAML has all three, and a
digest is over YAML's dump. So `jsonable` tags what JSON would lose: `{"$date": "2026-11-01"}`, `{"$datetime":
"<isoformat with a space>", "iso": "<isoformat>"}`, `{"$float": "<YAML's spelling>"}`, and `{"$map": [[k, v], ...]}`
for a mapping whose keys are not all plain strings (or would be reordered by a JavaScript object: `"7"`). The page's
`ThymJS.revive` turns them back.

`page_bundle(plan, inputs_root=..., program=...)` returns `{plan, program, version, decls, inputs, manifests}`.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import base64
import datetime as _dt
import re
from pathlib import Path
from typing import Any

import yaml

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym import folder as _folder
from enough.thym import registry as _registry
from enough.thym.values import (Value, is_list_input, list_member_type, load_input, member_name, posix_path)

_INDEX_LIKE = re.compile(r"^(?:0|[1-9][0-9]*)$")


def _yaml_float(x: float) -> str:
    """A float as PyYAML's safe dumper spells it."""
    return yaml.SafeDumper.represent_float(yaml.SafeDumper(None), x).value


def jsonable(x: Any) -> Any:
    """A loaded value as tagged JSON (the module's docstring)."""
    if isinstance(x, dict):
        keys = list(x)
        if all(isinstance(k, str) and not _INDEX_LIKE.match(k) for k in keys):
            return {k: jsonable(v) for k, v in x.items()}
        return {"$map": [[jsonable(k), jsonable(v)] for k, v in x.items()]}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return {"$float": _yaml_float(x)}
    if isinstance(x, _dt.datetime):
        return {"$datetime": x.isoformat(" "), "iso": x.isoformat()}
    if isinstance(x, _dt.date):
        return {"$date": x.isoformat()}
    return str(x)


def _b64(data: bytes | None) -> str | None:
    return base64.b64encode(data).decode("ascii") if data is not None else None


def _refusal(r: Refusal) -> dict:
    return {"refusal": {"stage": r.stage, "check": r.check, "message": r.message, "line": r.line}}


def _module_names(manifest: Any) -> dict:
    if manifest is None:
        return {}
    out = {}
    for letter, block in (manifest._modules_block() or {}).items():
        name = block.get("name") if isinstance(block, dict) else None
        out[str(letter)] = name.strip().lower() if isinstance(name, str) and name.strip() else str(letter)
    return out


def value_bundle(v: Value, manifests: dict) -> dict:
    """One value read from disk, as the page's runtime takes it."""
    p = v.payload
    out: dict[str, Any] = {"type": v.type}
    if isinstance(p, _folder.Folder):
        binaries = {}
        for e in p.entries:
            if e.binary and p.root is not None:
                try:
                    binaries[e.path] = _b64(p.raw(e.path))
                except _folder.FolderError:
                    pass
        out["folder"] = {"path": p.path, "name": p.name, "tree": p.tree, "commit": p.commit, "origin": p.origin,
                         "entries": [{"path": e.path, "sha256": e.sha256, "size": e.size, "binary": e.binary,
                                      "tree": e.tree} for e in p.entries],
                         "texts": {e.path: p.text(e.path) for e in p.entries if not e.binary},
                         "binaries": binaries}
        return out
    if isinstance(p, mc.Volume):
        man = p.manifest
        if p.minicosm and p.minicosm not in manifests:
            manifests[p.minicosm] = _module_names(man)
        names = manifests.get(p.minicosm or "", {})
        out["volume"] = {"oes": p.oes, "catalog": jsonable(p.catalog),
                         "items": [{"id": it.id, "key": it.key, "kind": it.kind, "letter": it.module,
                                    "module": names.get(it.module, it.module) if it.module else it.module,
                                    "data": jsonable(it.data)} for it in p.items.values()]}
        out["raw"] = _b64(v.raw)
        return out
    if isinstance(p, dict):
        oes = p.get("oes")
        if isinstance(oes, str) and "/" in oes:
            mini = oes.split("/", 1)[0]
            if mini not in manifests:
                manifests[mini] = _module_names(mc.default_registry().get(mini))
        out["data"] = jsonable(p)
        out["raw"] = _b64(v.raw)
        return out
    if isinstance(p, str):
        out["text"] = p
        out["raw"] = _b64(v.raw)
        return out
    out["data"] = jsonable(p)
    return out


def input_bundle(spec: dict, inputs_root: Path, manifests: dict) -> dict:
    """One input of the plan, read as `run` reads it, or the refusal `run` would give at plan time."""
    if is_list_input(spec):
        rows = spec.get("members")
        v = load_input(spec, inputs_root)
        if isinstance(v, Refusal):
            return _refusal(v)
        member = list_member_type(str(spec.get("type") or "list"))
        paths = [posix_path((row if isinstance(row, dict) else {"path": row}).get("path")) for row in rows]
        return {"type": "list", "member": member,
                "members": [value_bundle(m, manifests) for m in v.payload], "paths": paths,
                "names": [member_name(str(spec.get("name")), n) for n in range(1, len(paths) + 1)]}
    v = load_input(spec, inputs_root)
    if isinstance(v, Refusal):
        return _refusal(v)
    out = value_bundle(v, manifests)
    out["path"] = posix_path(spec.get("path"))
    return out


def _decl_row(d: Any) -> dict:
    get = _registry.decl_get
    out: dict[str, Any] = {"name": get(d, "name")}
    for k in ("asks", "scaffold", "since"):
        if get(d, k) is not None:
            out[k] = get(d, k)
    for k in ("gives", "contract"):
        v = get(d, k)
        if v is not None:
            out[k] = [a.strip() for p in ([v] if isinstance(v, str) else list(v)) for a in str(p).split("|")
                      if a.strip()] if k == "gives" else [str(x) for x in v]
    mods = get(d, "modifiers")
    if isinstance(mods, dict):
        out["modifiers"] = {str(w): list(t) if isinstance(t, (list, tuple)) else [t] for w, t in mods.items()}
    cw = get(d, "code_when")
    if cw:
        out["code_when"] = [[list(words), str(code), str(owner)] for words, code, owner in cw]
    for k in ("gives-when", "contract-when", "scaffold-when"):
        if get(d, k) or get(d, k.replace("-", "_")):
            out[k] = True
    return out


def declarations(version: int) -> dict:
    """The declarations a program of grammar `version` sees, as the page's runtime takes them."""
    from enough.thym import run as _run
    return {str(n): _decl_row(d) for n, d in _run._views(_registry.declarations(), version).items()}


def page_bundle(plan: dict, *, inputs_root: Path | str, program: Any = None) -> dict:
    """The plan, its program (source text, or the program volume as tagged JSON), the declarations its version
    sees, and every input as the page's runtime takes it (a refusal in place of an input that is missing or
    changed)."""
    from enough.thym import run as _run
    src = program
    if isinstance(program, (str, Path)) and "\n" not in str(program) and str(program).endswith((".thym", ".cosm")):
        p = Path(program)
        text = p.read_text(encoding="utf-8-sig")
        src = mc.yaml_load(text) if p.suffix == ".cosm" else text
    info = _run.ProgramInfo.from_any(src)
    version = info.version if info.version is not None else 1
    manifests: dict = {}
    inputs = {}
    for spec in plan.get("inputs") or []:
        if isinstance(spec, dict):
            inputs[str(spec.get("name"))] = input_bundle(spec, Path(inputs_root), manifests)
    return {"plan": jsonable(plan), "program": jsonable(src) if isinstance(src, dict) else src,
            "version": version, "decls": declarations(version), "inputs": inputs, "manifests": manifests}


__all__ = ["declarations", "input_bundle", "jsonable", "page_bundle", "value_bundle"]
