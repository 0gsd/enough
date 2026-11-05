"""Packages and their accessors (docs/THYM.md 15, 16): the moves `package`, `unpack`, `fabula`, `context`, `graph`,
`isomorph`, and the check `released`.

A **package** is the self-contained export of a text: the author's text exactly as published, its fabula (every span
resolving into `text.md`, so the fabula's `source.path` and its locators say `text.md`), and, when given, the author's
morph, the context and the released graph, with a catalog, `package.cosm`, that lists every file with its sha256,
names the program and the run that made it, and carries the notice. `package` writes the **folder form**,
`<text-stem>.thym/`, into the run's stage, so it lands with the run or not at all; the value it gives is the
**single-file form** of the same catalog (each file's bytes under `contents[].text`, THYM.md 15.3), which the runtime
lands as the program's output, `<name>.package.cosm`, one file that travels. The trace's own digest is not known until
the run lands, so `made.trace` names the run; and `made.by` names the language version, `thym 0`, never enough's, so
a replay on a later enough gives the same bytes.

The accessors read either form: `fabula of p`, `isomorph of p` (the author's morph, or nothing), `context of p` (the
context a package carries, or nothing), `graph of p` (`graph.cosm`, or nothing). Of a text, `context of t` asks the
host for the surrounding catalog (`ctx.engines["catalog"]`, a callable from a path to a mapping) and gives it as a
`thym/1` context, or nothing; `graph of t` gives nothing this round. `unpack` gives the text back, byte for byte.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check
from enough.thym.moves import MoveError, fabula_doc
from enough.thym.registry import implements
from enough.thym.trace import write_atomic
from enough.thym.values import NOTHING, Value, canonical, plain, read_value, sha256_bytes

NOTICE = ("A Thym package. The text is its author's; the fabula, morph and context describe it. Readings made from it "
          "are the reader's and are labelled.")
ROLES = (("text", "text.md"), ("fabula", "fabula.cosm"), ("morph", "morph.cosm"), ("context", "context.cosm"),
         ("graph", "graph.cosm"))


def _given(v: Any) -> bool:
    return isinstance(v, Value) and not v.is_nothing


def _packaged_fabula(f: Value) -> bytes:
    """The fabula as a package holds it: its `source.path` and its provenance locators say `text.md`."""
    cat, _items = fabula_doc(f)
    if not cat:
        raise MoveError("package needs a fabula, an emf/1 volume")
    doc = copy.deepcopy(plain(cat))
    src = doc.get("source") if isinstance(doc.get("source"), dict) else None
    old = str(src.get("path")) if src and src.get("path") else None
    if src is not None:
        src["path"] = "text.md"
    if old and old != "text.md":
        # every locator in a source, not only the first: a source may hold several, `notes.md#L3, notes.md#L14`
        rx = re.compile(rf"(?<![^\s,]){re.escape(old)}(?=#|,|\s|$)")
        for it in doc.get("nodes") or []:
            prov = it.get("provenance") if isinstance(it, dict) else None
            if isinstance(prov, dict) and isinstance(prov.get("sources"), list):
                prov["sources"] = [rx.sub("text.md", s) if isinstance(s, str) else s for s in prov["sources"]]
    return canonical(doc)


def _slug(t: Value) -> str:
    stem = t.path.stem if t.path is not None else "text"
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "text"


@implements("package")
def package(ctx: Any, text: Value, fabula: Value, morph: Value = NOTHING, context: Value = NOTHING,
            graph: Value = NOTHING, **_: Any) -> Value:
    """A text with its fabula, morph, context and released graph, self-contained (THYM.md 15)."""
    if not _given(fabula) or fabula.type != "fabula":
        raise MoveError("package needs the text's fabula")
    files: dict[str, bytes] = {"text.md": text.bytes(), "fabula.cosm": _packaged_fabula(fabula)}
    for role, v in (("morph", morph), ("context", context), ("graph", graph)):
        if _given(v):
            files[f"{role}.cosm"] = v.bytes()
    cat_f, _ = fabula_doc(fabula)
    slug = _slug(text)
    try:
        prog = (ctx.trace().mapping() or {}).get("program") or {}
    except Exception:  # noqa: BLE001 - a trace that cannot be read names no program
        prog = {}
    rows = [{"path": name, "sha256": sha256_bytes(files[name]), "role": role} for role, name in ROLES if name in files]
    catalog = {"oes": "thym/1", "kind": "package", "id": f"thym/{slug}", "name": str(cat_f.get("name") or slug),
               "contents": rows,
               "made": {"program": {"name": prog.get("name"), "sha256": prog.get("sha256")},
                        "trace": {"run": ctx.run}, "at": ctx.now, "by": "thym 0"},
               "notice": NOTICE, "nodes": []}
    stage = getattr(ctx, "stage", None)
    folder = None
    if stage is not None:
        folder = Path(stage) / f"{slug}.thym"
        for name, data in files.items():
            write_atomic(folder / name, data)
        write_atomic(folder / "package.cosm", canonical(catalog))
    single = copy.deepcopy(catalog)
    for row in single["contents"]:
        row["text"] = files[row["path"]].decode("utf-8")
    return Value("package", single, path=folder)


# ---------------------------------------------------------------------------
# Reading a package, in either form
# ---------------------------------------------------------------------------

def _row(p: Value, role: str) -> dict | None:
    cat = p.mapping() or {}
    return next((r for r in cat.get("contents") or [] if isinstance(r, dict) and r.get("role") == role), None)


def member(p: Value, role: str, typ: str) -> Value:
    """One file of a package as a value of `typ`, read from the single-file form's `text` or the folder form's file;
    nothing when the package does not carry it."""
    if p is None or not isinstance(p, Value) or p.is_nothing:
        return NOTHING
    if p.type != "package":
        raise MoveError(f"a {p.type} is not a package")
    row = _row(p, role)
    if row is None:
        return NOTHING
    if isinstance(row.get("text"), str):
        raw = row["text"].encode("utf-8")
        name = str(row.get("path") or "")
        if name.endswith(".cosm"):
            data = mc.yaml_load(row["text"])
            if not isinstance(data, dict):
                raise MoveError(f"{name} in the package is not a mapping")
            return Value(typ, data, raw=raw, made={"move": "none"})
        return Value(typ, row["text"], raw=raw, made={"move": "none"})
    if p.path is None or not (p.path / str(row.get("path"))).is_file():
        raise MoveError(f"{row.get('path')} is not in the package")
    return read_value(p.path / str(row["path"]), typ)


@implements("unpack")
def unpack(ctx: Any, p: Value, **_: Any) -> Value:
    """The text a package carries, byte for byte (THYM.md 15.4); the contract checks its digests first."""
    v = member(p, "text", "text")
    if v.is_nothing:
        raise MoveError("the package carries no text")
    return v


@implements("fabula")
def fabula_of(ctx: Any, **mods: Any) -> Value:
    """The fabula a package carries."""
    v = member(mods.get("of"), "fabula", "fabula")
    if v.is_nothing:
        raise MoveError("the package carries no fabula")
    return v


@implements("isomorph")
def isomorph_of(ctx: Any, **mods: Any) -> Value:
    """The morph a package carries, its author's shared one, or nothing."""
    return member(mods.get("of"), "morph", "morph")


@implements("context")
def context_of(ctx: Any, **mods: Any) -> Value:
    """Of a text, the surrounding volume's catalog around it, read-only, or nothing (THYM.md 16.1); of a package, the
    context it carries, or nothing."""
    of = mods.get("of")
    if isinstance(of, Value) and of.type == "package":
        return member(of, "context", "context")
    catalog = (getattr(ctx, "engines", None) or {}).get("catalog")
    if catalog is None or not isinstance(of, Value) or of.path is None:
        return NOTHING
    try:
        got = catalog(of.path)
    except Exception:  # noqa: BLE001 - a catalog that cannot be read gives no context
        got = None
    if not isinstance(got, dict) or not got:
        return NOTHING
    slug = re.sub(r"[^a-z0-9]+", "-", of.path.stem.lower()).strip("-") or "text"
    item = {"id": "C:context/surrounding", "type": "context", "name": "surrounding",
            "summary": f"The catalog around {of.path.name}, read-only.", "surrounding": plain(got),
            "provenance": {"mode": "derived", "sources": [of.path.name]}}
    return Value("context", {"oes": "thym/1", "kind": "context", "id": f"thym/{slug}-context",
                             "name": f"{slug} context", "nodes": [item]})


@implements("graph")
def graph_of(ctx: Any, **mods: Any) -> Value:
    """What the holograph released for a text: the `graph.cosm` a package carries, else nothing (THYM.md 15, 16);
    a text's graph is nothing this round, until Ascribe's module is in enough."""
    of = mods.get("of")
    if isinstance(of, Value) and of.type == "package":
        return member(of, "graph", "graph")
    return NOTHING


@check("released")
def _released(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Nothing is in `graph.cosm` without a release recorded in the holograph (THYM.md 15.4): a graph carries
    `release:`, the release it came from (THYM.md 5.1). Nothing passes: no graph, nothing released."""
    graphs: list[Value] = []
    if output.type == "graph" and not output.is_nothing:
        graphs.append(output)
    if output.type == "package":
        g = member(output, "graph", "graph")
        if not g.is_nothing:
            graphs.append(g)
    graphs += [v for v in inputs.values() if isinstance(v, Value) and v.type == "graph" and not v.is_nothing]
    if not graphs:
        return True, "no graph: nothing was released, and nothing travels"
    for g in graphs:
        data = g.mapping() or {}
        rel = data.get("release")
        if not rel:
            return False, "the graph carries no release recorded in the holograph"
    return True, ""


__all__ = ["context_of", "fabula_of", "graph_of", "isomorph_of", "member", "package", "unpack"]
