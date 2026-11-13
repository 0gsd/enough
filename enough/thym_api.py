"""The Thym routes (0.5.0): programs, plans, runs and traces under `/api/thym/*`, and a text's packages and readings
under `/api/canon/package`, `/api/canon/unpack` and `/api/canon/read` (docs/THYM.md 11.3, 12, 14, 15, 16, 19).

The same split as `composure_api.py` and `dictionary_api.py`: the language is `enough/thym/` (it imports nothing of
enough), enough's side of it `enough/thym_host.py`, and this file the HTTP translation. The plain functions above the
router (`program_row`, `compile_payload`, `make_plan`, `export_package`, `unpack_package`, `list_runs`, `land_beside`)
are what it translates; a test or a tool calls them without the app. The router closes over what `create_app` owns
and passes in: the project, the session's model URL, Canon's job table and its helpers (`canon_mode`, `start_job`,
`text_target`, `catalog_after`, `model_complete`), and the cosm viewer's payload builder (`cosm_payload`).

**Modes.** A run's mode is decided once, before it starts, as a derivation's is (`canon_mode`): `model` when a model
answers, else `rules`. In `rules` a plan that asks a model is refused at plan time with the count and the reason,
check `agent-free` ("3 steps ask a model; agent-free is on") or `no-model` ("...; no model is running"), and a plan
that asks nothing runs (THYM.md 19). A request may say `mode: rules` to run the declared scaffolds instead (`--rules`:
a step whose move has no scaffold still refuses, check `rules`), or `mode: model` to insist on the model (409 when
none answers). A run in model mode holds the generation lock, as a derivation does.

**Where things land.** Runs live under the Thym root (`ENOUGH_THYM_ROOT`, `~/enough/thym/`), which nothing here
creates by asking: a listing of a root that is not there is empty. A run's outputs are copied beside its first input
when that input is a project or store file, as `<stem>.<output>.<ext>`; a package lands as `<stem>.package.cosm` with
its folder form `<stem>.thym/`, the names Canon's export uses. Every copy is made all at once or not at all.

**Packages.** Export runs a program, `export`, written here for the request (`package story, f, m, c, g`), so the
package is made by the `package` move's own code under its contract, its catalog names the program and the run, and
its two forms are byte for byte what any run of `package` lands. The twin must be fresh: export derives nothing (409
"derive the twin first"). `encrypt` seals the single file as `<stem>.thym.enc` (`enough.thym.vault`) and returns the
key once; it is written nowhere. Import verifies every digest and every span before it writes anything, and never
writes over a file that differs.

**Readings.** A reading runs a program, `reading` (`read f with mine`), whose output is copied beside the text as
`<text-stem>.read-<morph>-YYYY-MM-DD-HHMM.md` (local time; `-2`, `-3` on a collision), carrying its label and footer
(THYM.md 14). `read` has no scaffold, so a reading needs a model.
"""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import logging
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import agent_free as _agent_free
from . import canon as _canon
from . import canon_tools as _canon_tools
from . import fabula_names as _fabula_names
from . import macrocosm as _macrocosm
from . import thym_host as _host
from .thym import Refusal
from .thym import run as _run
from .thym import trace as _trace
from .thym import vault as _vault
from .thym.cli import plan_atem
from .thym.coprocessor import RefusingCoprocessor
from .thym.values import Value, digest_path, read_value, sha256_bytes

log = logging.getLogger("enough.thym_api")

RUNS_LISTED = 200                       # the newest runs a listing reads
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
_MORPH_SLUG = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Paths: project files, store files, and the names a path is reported by
# ---------------------------------------------------------------------------

def resolve(project_dir: Path, rel: str) -> Path:
    """A route path as a file: `canon:<volume>/...` in the store, anything else in the project (absolute paths and
    `..` refused, 400), by `canon_tools.resolve`, the rule every Canon route uses."""
    rel = _canon_tools.tidy_rel(str(rel or ""))
    if not rel or rel in _canon_tools.STORE_PREFIXES:
        raise HTTPException(400, "missing path")
    try:
        return _canon_tools.resolve(Path(project_dir), rel)
    except _canon_tools.TextTargetError as e:
        raise HTTPException(e.status, str(e)) from None


def rel_of(project_dir: Path, path: Path | str) -> str | None:
    """How the app names a file: project-relative, `canon:<volume>/...` in the store, or None for anywhere else."""
    try:
        real = Path(path).absolute().resolve()
    except OSError:
        return None
    for base, prefix in ((Path(project_dir), ""), (_canon.root(), "canon:")):
        try:
            return prefix + real.relative_to(base.resolve()).as_posix()
        except (ValueError, OSError):
            continue
    return None


def stem_of(path: Path) -> str:
    """The stem outputs beside a file take: a package's (`notes.thym`, `notes.package.cosm` -> `notes`); else the name
    less `.cosm` and one extension (`notes.md` and `notes.md.cosm` -> `notes`, `mine.morph.cosm` -> `mine`)."""
    name = path.name
    stem = _canon.package_stem(name)
    if stem:
        return stem
    got = _fabula_names.parse(name)
    if got is not None and got[1] is not None:              # notes.md.fabulan.cosm -> notes (a short's stem)
        return _fabula_names.short_stem(name)
    if name.endswith(".cosm") and len(name) > len(".cosm"):
        name = name[: -len(".cosm")]
    base, dot, _ext = name.rpartition(".")
    return base if dot and base else name


def refusal_dict(r: Refusal | None) -> dict | None:
    if r is None:
        return None
    return {"stage": r.stage, "check": r.check, "line": r.line, "message": r.message}


# ---------------------------------------------------------------------------
# Programs: listed, compiled, estimated
# ---------------------------------------------------------------------------

def _checked(path: Path | None = None, text: str | None = None) -> Any:
    from .thym import check as _check
    from .thym import parse as _parse
    if text is None:
        try:
            text = Path(path).read_bytes().decode("utf-8")
        except OSError as e:
            return Refusal("compile", "unknown-uri", f"{Path(path).name} cannot be read: {e.strerror or e}")
        except UnicodeDecodeError:
            return Refusal("compile", "parse", f"{Path(path).name} is not UTF-8")
    module = _parse.parse(text, path=str(path) if path is not None else None)
    return module if isinstance(module, Refusal) else _check.check(module)


def _block(checked: Any) -> Any:
    progs = checked.programs()
    return progs[0] if progs else None


def estimate(checked: Any) -> dict:
    """What a program costs before its inputs are known (THYM.md 11.1, stage 5): its nodes, those that ask a model,
    the largest prompt (0 until the inputs' sizes are known: `plan` gives it) and the output budget in words."""
    from .thym import plan as _plan
    nodes = _plan.build(checked)
    if isinstance(nodes, Refusal):
        return {"steps": 0, "asks": 0, "largest_prompt": 0, "output_words": 0}
    return {"steps": len(nodes), "asks": sum(1 for n in nodes if n.asks), "largest_prompt": 0,
            "output_words": max((n.output_words for n in nodes), default=0)}


def _why(block: Any) -> str | None:
    return " ".join(block.why.text.split()) if block is not None and block.why is not None else None


def version_of(checked: Any) -> int:
    """The grammar a compiled program is written in: 0 or 1 (its `thym <n>` line)."""
    v = getattr(getattr(checked, "module", None), "version", 0)
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else 0


def takes_rows(block: Any) -> list[dict]:
    """A program's inputs as the page's pickers read them: `{name, type, accepts}`, `accepts` saying in words what
    the input takes (`thym_host.accepts`: a text, a fabula, a folder, a volume, a morph, a context, a package)."""
    return [{"name": p.name, "type": p.type, "accepts": _host.accepts(p.type)} for p in block.takes] if block else []


def outputs_rows(block: Any) -> list[dict]:
    """Every output a program gives, `{name, type}`, in its `gives` order (THYM 8.2: several in `thym 1`)."""
    if block is None:
        return []
    outs = list(getattr(block, "outputs", None) or ([block.gives] if block.gives else []))
    return [{"name": p.name, "type": p.type} for p in outs]


def program_row(entry: dict) -> dict:
    """One row of `GET /api/thym/programs`: `{name, where, rel, problem, version, steps, asks, takes, gives, outputs,
    why}` for a program that compiles (`takes` rows `{name, type, accepts}`; `gives` the first output, `outputs` every
    one); `{name, where, rel, problem}` for one that does not (the problem is the refusal, with its line)."""
    row = {"name": entry.get("name"), "where": entry.get("where"), "rel": entry.get("rel"),
           "problem": entry.get("problem")}
    if row["problem"]:
        return row
    checked = _checked(Path(entry["path"]))
    if isinstance(checked, Refusal):
        row["problem"] = f"line {checked.line}: {checked.message}" if checked.line else checked.message
        return row
    block = _block(checked)
    est = estimate(checked)
    row.update(version=version_of(checked), steps=est["steps"], asks=est["asks"], takes=takes_rows(block),
               gives={"name": block.gives.name, "type": block.gives.type} if block and block.gives else None,
               outputs=outputs_rows(block), why=_why(block))
    return row


def compile_payload(*, path: Path | None = None, text: str | None = None) -> dict:
    """`POST /api/thym/compile`: `{ok, name, refusal, refusals, estimate}`. `refusal` is the first fault, where it
    always was; `refusals` (0.7) every independent fault the checker found, the first first (`[]` when it compiles),
    which the editor's strip steps through."""
    checked = _checked(path, text)
    if isinstance(checked, Refusal):
        return {"ok": False, "name": None, "refusal": refusal_dict(checked),
                "refusals": [refusal_dict(r) for r in checked.all()],
                "estimate": {"steps": 0, "asks": 0, "largest_prompt": 0, "output_words": 0}}
    block = _block(checked)
    if block is None:
        r = Refusal("plan", "no-program", "there is nothing to run: the file has no program block")
        return {"ok": False, "name": None, "refusal": refusal_dict(r), "refusals": [refusal_dict(r)],
                "estimate": estimate(checked)}
    return {"ok": True, "name": block.name, "refusal": None, "refusals": [], "estimate": estimate(checked),
            "version": version_of(checked), "takes": takes_rows(block), "outputs": outputs_rows(block)}


def program_volume(path: Path) -> dict | Refusal:
    """The program volume of a `.thym` file (THYM.md 10): its items, as `python -m enough.thym enumerate` writes."""
    from .thym import enumerate as _en
    return _en.enumerate_file(path)


def volume_from(mapping: dict, filename: str) -> "_macrocosm.Volume":
    from .thym import enumerate as _en
    return _macrocosm.load_volume_text(_en.dump(mapping), filename=filename)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

def _said(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _given(v: Any) -> bool:
    """Whether a request gave an input: a path that is not blank, or a list with at least one such path."""
    if isinstance(v, list):
        return any(str(x or "").strip() for x in v)
    return bool(str(v or "").strip())


def _one_input(project_dir: Path, rel: str, typ: str, name: str) -> tuple[Path, str]:
    """One path held to what an input of type `typ` takes, as every input is (a list's members each in turn): 404 for
    a path that is not there; 400 in words for one of the wrong kind or a folder with no catalog. `(path, sha256)`."""
    shown = _canon_tools.tidy_rel(rel)
    p = resolve(project_dir, rel)
    if not p.exists() and not p.is_symlink():
        raise HTTPException(404, f"no such file: {shown}")
    problem = _host.check_input(p, typ, name=name, shown=shown)
    if problem:
        raise HTTPException(400, problem)
    sha = digest_path(p, typ if typ == "folder" else None)
    if sha is None:
        raise HTTPException(400, f"{shown} is a folder with no catalog; {name} takes {_host.accepts(typ)}")
    return p, sha


def plan_inputs(project_dir: Path, checked: Any, inputs: dict[str, Any]) -> list[dict]:
    """The plan's inputs from `{<takes name>: <path>}`: every input the program takes, each in the program's order,
    with its type, its absolute path and its sha256 (a folder's tree digest; THYM.md 12.1, 20.3). Each path is held to
    what its input takes (`thym_host.check_input`: a text, a fabula, a folder, a volume, a morph, a context, a
    package). 404 for a path that is not there; 400 for a name the program does not take, an input missing, or a
    path of the wrong kind, in words.

    An input whose type is `list of T` is given as a list of paths (`{xs: ["a.md", "b.md"]}`): each member is held
    to what an input of type T takes, in order, with the refusals a single path gets (the input named `xs[2]` for
    the third); its row is `{name, type, members: [{path, sha256}], path, sha256}` (`path` the first member's, which
    outputs land beside; `sha256` over the members' in order). A list given for an input that is not a list, and a
    single path for one that is, are refused in words that name the input and its type."""
    from .thym import types as _ty
    block = _block(checked)
    takes = {p.name: p.type for p in block.takes} if block is not None else {}
    prog = block.name if block else "the program"
    unknown = [n for n in inputs if n not in takes]
    if unknown:
        raise HTTPException(400, f"{prog} takes no {unknown[0]}; it takes {_said(list(takes)) if takes else 'nothing'}")
    missing = [n for n in takes if not _given(inputs.get(n))]
    if missing:
        wants = _said([f"{n} ({_host.accepts(takes[n])})" for n in takes])
        raise HTTPException(400, f"{prog} takes {wants}; give {_said(missing)}")
    rows = []
    for name in takes:
        typ, given = takes[name], inputs[name]
        if _ty.is_list(typ):
            if not isinstance(given, list):
                raise HTTPException(400, f"{name} is a {typ}: it takes {_host.accepts(typ)}, given as a list of "
                                         f"paths ([\"a.md\", \"b.md\"]), and one path was given "
                                         f"({_canon_tools.tidy_rel(str(given))})")
            member = _ty.element(typ)
            members = []
            for i, rel in enumerate(str(x or "") for x in given):
                if not rel.strip():
                    raise HTTPException(400, f"{name}[{i + 1}] is blank; every member of {name} names a path")
                p, sha = _one_input(project_dir, rel, member, f"{name}[{i + 1}]")
                members.append({"path": str(p), "sha256": sha})
            joined = sha256_bytes("".join(m["sha256"] for m in members).encode("utf-8"))
            rows.append({"name": name, "type": typ, "path": members[0]["path"], "sha256": joined,
                         "members": members})
            continue
        if isinstance(given, list):
            raise HTTPException(400, f"{name} is a {typ}: it takes {_host.accepts(typ)}, one path, and a list of "
                                     f"{len(given)} was given")
        p, sha = _one_input(project_dir, str(given or ""), typ, name)
        rows.append({"name": name, "type": typ, "path": str(p), "sha256": sha})
    return rows


def make_plan(checked: Any, rows: list[dict]) -> dict | Refusal:
    from .thym import plan as _plan
    return _plan.plan(checked, rows)


def asks_refusal(plan: dict, why: str, *, route: str | None = "local", program: Any = None) -> Refusal | None:
    """In rules mode, a plan whose nodes ask a model is refused at plan time (THYM.md 19), in the text's words: how
    many steps ask a model on which route, and the first one's statement and line ("3 steps ask a model on the local
    route, the first `let f = derive story` (line 11); agent-free is on"). Check `agent-free` when agent-free mode
    chose rules, `no-model` when no model answers. `program` (its path or text) names the statement."""
    said = _host.asks_said(plan, route=route, program=program)
    if said is None:
        return None
    many, line = said
    if why == _agent_free.REASON:
        return Refusal("plan", "agent-free", f"{many}; agent-free is on", line=line)
    return Refusal("plan", "no-model", f"{many}; no model is running", line=line)


def scaffold_refusal(plan: dict) -> Refusal | None:
    """With `mode: rules`, the steps whose move asks a model and declares no scaffold (THYM.md 19), counted; a step
    that calls a move the program defines is left to the runtime, which looks inside it."""
    from .thym import registry as _registry
    decls = _registry.declarations()
    _head, nodes = _run.plan_parts(plan)
    bare = [n for n in nodes if n.get("asks") is True and n.get("move") in decls
            and not _registry.decl_get(decls[n.get("move")], "scaffold")]
    if not bare:
        return None
    k = len(bare)
    return Refusal("plan", "rules", f"{k} step{'s' if k != 1 else ''} ask{'' if k != 1 else 's'} a model and "
                                    f"{'have' if k != 1 else 'has'} no scaffold; rules runs no model",
                   line=bare[0].get("line"))


# ---------------------------------------------------------------------------
# Running, and landing beside the first input
# ---------------------------------------------------------------------------

def runtime(project_dir: Path, *, mode: str, why: str, scaffolds: bool, complete: Callable | None,
            n_ctx: int | None, route: str | None = None, model: str | None = None, calls: int | None = None,
            info: dict | None = None, program: Any = None) -> dict:
    """The keyword arguments `enough.thym.run.run` takes for one run from the app (`thym_host.runtime_kwargs`'s, with
    the mode decided by the route rather than read again): the model coprocessor in model mode, the refusing one
    otherwise; the preflight; the environment with the model's window; the root; the engines, the surrounding catalog
    among them; the ceiling on model calls.

    With a `route` (THYM.md 23): the coprocessor is on that route (`complete` is the route's), its candidates say the
    route and the provider; the preflight refuses a shut gate, an open count without `calls`, a step the route's
    window cannot hold; the environment names the model that answered, the route and the provider."""
    af = why == _agent_free.REASON or _agent_free.enabled()
    use = mode == "model" and not scaffolds
    if route is None:
        return {"coprocessor": _host.ModelCoprocessor(complete) if use else RefusingCoprocessor(),
                "agent_free": af, "rules": scaffolds,
                "preflight": _host.preflight_hook(n_ctx if n_ctx else (lambda: None)) if use else None,
                "environment": _host.environment(agent_free=af, n_ctx=n_ctx if use else None),
                "root": _host.host_root(), "engines": _host.engines(catalog=_host.catalog_engine(project_dir)),
                "calls": calls}
    provider = _host.CLOUD_PROVIDER if route == "cloud" else None
    planned = (info or {}).get("model") or (model if route == "cloud" else None)
    cop = (_host.ModelCoprocessor(complete, route=route, provider=provider, model_id=planned) if use
           else RefusingCoprocessor())
    window = n_ctx or (info or {}).get("window") or (_host.CLOUD_WINDOW if route == "cloud" else None)
    return {"coprocessor": cop, "agent_free": af, "rules": scaffolds,
            "preflight": (_host.route_preflight(route, model=model, window=window, calls=calls, ceiling="calls",
                                                info=info, program=program) if use else None),
            "environment": _host.environment(agent_free=af, n_ctx=window if use else None,
                                             route=route if use else None, provider=provider,
                                             model=cop.model_seen if use else None),
            "root": _host.host_root(), "engines": _host.engines(catalog=_host.catalog_engine(project_dir)),
            "calls": calls}


def _tmp_beside(dst: Path) -> Path:
    return dst.with_name(f".{dst.name}.thym-{secrets.token_hex(3)}.tmp")


def copy_all(pairs: list[tuple[Path, Path]]) -> None:
    """Copy every `(source, destination)` at once or not at all: each source to a hidden name beside its destination
    first, then every destination replaced (a folder moved aside, swapped, then removed). A failure removes what it
    made and puts back what it moved."""
    staged: list[tuple[Path, Path]] = []
    try:
        for src, dst in pairs:
            tmp = _tmp_beside(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, tmp)
            else:
                shutil.copyfile(src, tmp)
            staged.append((tmp, dst))
    except Exception:
        for tmp, _dst in staged:
            shutil.rmtree(tmp, ignore_errors=True) if tmp.is_dir() else tmp.unlink(missing_ok=True)
        raise
    moved: list[tuple[Path, Path]] = []                     # (old copy kept aside, where it was)
    done: list[Path] = []
    try:
        for tmp, dst in staged:
            if dst.is_dir():
                aside = _tmp_beside(dst)
                os.replace(dst, aside)
                moved.append((aside, dst))
            os.replace(tmp, dst)
            done.append(dst)
    except Exception:
        for dst in done:
            shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink(missing_ok=True)
        for aside, dst in moved:
            if not dst.exists():
                os.replace(aside, dst)
        for tmp, _dst in staged:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True) if tmp.is_dir() else tmp.unlink(missing_ok=True)
        raise
    for aside, _dst in moved:
        shutil.rmtree(aside, ignore_errors=True)


def land_beside(project_dir: Path, t: Any, first: Path | None) -> list[dict]:
    """A landed run's outputs, every one in the program's order, `[{name, type, path, rel}]`: `path` the output in the
    run's folder; `rel` the copy made beside the first input when that input is a project or store file
    (`<stem>.<output>.<ext>`; a folder output as the folder `<stem>.<output>/`; a package as `<stem>.package.cosm`,
    with `folder` naming its folder form `<stem>.thym`), else None. A folder output also lists its `files` (paths
    inside it, sorted). All copies or none."""
    rows: list[dict] = []
    pairs: list[tuple[Path, Path]] = []
    beside = first is not None and rel_of(project_dir, first) is not None
    for name, out in t.outputs.items():
        out = Path(out)
        v = t.values.get(name)
        typ = v.type if isinstance(v, Value) else ("folder" if out.is_dir() else None)
        row: dict[str, Any] = {"name": name, "type": typ, "path": str(out), "rel": None}
        folder_out = typ == "folder" or (typ != "package" and out.is_dir())
        if folder_out:
            row["files"] = sorted(f.relative_to(out).as_posix() for f in out.rglob("*") if f.is_file())
        if beside:
            if folder_out:
                dst, _ = landing(first, name, "folder")
                pairs.append((out, dst))
                row["rel"] = rel_of(project_dir, dst)
            elif isinstance(v, Value) and v.type == "package":
                single, folder = landing(first, name, "package")
                pairs.append((out, single))
                row["rel"] = rel_of(project_dir, single)
                folder_src = t.dir / "outputs" / v.path.name if v.path is not None else None
                if folder_src is not None and folder_src.is_dir():
                    pairs.append((folder_src, folder))
                    row["folder"] = rel_of(project_dir, folder)
            else:
                ext = v.ext if isinstance(v, Value) else out.name.split(".", 1)[-1]
                dst, _ = landing(first, name, "file", ext)
                pairs.append((out, dst))
                row["rel"] = rel_of(project_dir, dst)
        rows.append(row)
    if pairs:
        copy_all(pairs)
    return rows


def landing(first: Path, name: str, kind: str, ext: str | None = None) -> tuple[Path, Path | None]:
    """Where an output named `name` lands beside the first input `first` (`land_beside` and a plan's `writes` both
    ask here): `kind` folder → the folder `<stem>.<name>/`; package → `<stem>.package.cosm`, with its folder form
    `<stem>.thym/` second; file → `<stem>.<name>.<ext>`."""
    parent, stem = first.parent, stem_of(first)
    if kind == "folder":
        return parent / f"{stem}.{name}", None
    if kind == "package":
        return parent / f"{stem}{_canon.PACKAGE_FILE_SUFFIX}", parent / f"{stem}{_canon.PACKAGE_FOLDER_SUFFIX}"
    return parent / f"{stem}.{name}.{ext}", None


#: The types whose values are written as plain characters (`Value.ext`: md for a text or a short, txt for the rest).
_CHARACTER_TYPES = ("text", "short", "line", "word", "string", "number", "bool", "date", "nothing")


def output_ext(typ: str | None) -> str | None:
    """The extension an output of declared type `typ` is written with, asked of `Value.ext` (the property the run
    lands it by) for a value of that type: md for a text or a short, txt for a plain value or a line, `<kind>.cosm`
    or cosm for a mapping, a volume, an item or a list. None for a type that does not say (`any`)."""
    from .thym import types as _ty
    if not typ or typ in (_ty.ANY, "list"):
        return Value("list", []).ext if typ == "list" else None
    if _ty.is_list(typ):
        return Value("list", []).ext
    return Value(typ, "" if typ in _CHARACTER_TYPES else {}).ext


def plan_writes(project_dir: Path, block: Any, first: Path | None) -> list[dict]:
    """A plan's `writes`: every output the program gives, `{name, type, rel}` in `gives` order, `rel` the path it
    will land at relative to the project (or `canon:`), its extension included, by `landing` (the run's own naming);
    a package also `folder`, its folder form. `rel` is None when the first input is not a project or store file
    (outputs then stay with the run) or the type does not say its extension."""
    beside = first is not None and rel_of(project_dir, first) is not None
    rows = []
    for o in outputs_rows(block):
        name, typ = o["name"], o["type"]
        row: dict[str, Any] = {"name": name, "type": typ, "rel": None}
        if beside:
            kind = "folder" if typ == "folder" else "package" if typ == "package" else "file"
            ext = output_ext(typ) if kind == "file" else ""
            if ext is not None:
                dst, folder = landing(first, name, kind, ext)
                row["rel"] = rel_of(project_dir, dst)
                if folder is not None:
                    row["folder"] = rel_of(project_dir, folder)
        rows.append(row)
    return rows


def run_result(project_dir: Path, t: Any, first: Path | None, mode: str, *, route: str | None = None,
               plan: dict | None = None) -> dict:
    """A finished run as a job's result: `{run, trace, atem, outcome, mode, outputs}`, with `refusal` when it did
    not land; with a route, `route` (model mode only) and the plan's `models` block."""
    outputs = land_beside(project_dir, t, first) if t.landed else []
    out = {"run": t.run_id, "trace": str(t.path), "atem": t.atem(), "outcome": t.outcome, "mode": mode,
           "outputs": outputs}
    if route is not None:
        out["route"] = route if mode == "model" else None
        out["models"] = (plan or {}).get("models")
    if not t.landed:
        out["refusal"] = refusal_dict(t.refusal)
    return out


# ---------------------------------------------------------------------------
# Runs and traces, read from the Thym root
# ---------------------------------------------------------------------------

def _input_rows(project_dir: Path, run_dir: Path, rid: str, inputs_root: Any) -> list[dict]:
    plan_file = run_dir / f"{rid}.plan.cosm"
    try:
        plan = _macrocosm.yaml_load(_macrocosm.read_text(plan_file)) if plan_file.is_file() else {}
    except Exception:  # noqa: BLE001 - a plan that cannot be read lists no inputs
        plan = {}
    rows = []
    # the trace's inputs root: absolute in a trace before 0.7, relative to the run's root since, `.` when the inputs
    # lay elsewhere (an app run's are read against the project, as here)
    base = _trace.recorded_inputs_root(inputs_root, run_dir) or Path(project_dir)
    for row in (plan or {}).get("inputs") or []:
        if not isinstance(row, dict):
            continue
        p = Path(str(row.get("path") or ""))
        if not p.is_absolute():
            p = base / p
        rows.append({"name": row.get("name"), "rel": rel_of(project_dir, p), "path": str(p)})
    return rows


def run_row(project_dir: Path, trace_path: Path) -> dict | None:
    tv = _trace.load(trace_path)
    if isinstance(tv, Refusal):
        return None
    head = _trace.root_item(tv)
    rid = trace_path.name[: -len(".trace.cosm")]
    started, ended = _trace.parse_utc(tv.get("started")), _trace.parse_utc(tv.get("ended"))
    seconds = max(0, int((ended - started).total_seconds())) if started and ended else 0
    return {"run": rid, "program": (tv.get("program") or {}).get("name"),
            "inputs": _input_rows(project_dir, trace_path.parent, rid, head.get("inputs_root")),
            "started": _trace.utc(started) if started else None, "seconds": seconds, "outcome": tv.get("outcome"),
            "atem": head.get("summary"), "trace": str(trace_path), "replay_of": head.get("replay_of")}


def list_runs(project_dir: Path, *, limit: int = RUNS_LISTED) -> list[dict]:
    """`GET /api/thym/runs`: the runs under the Thym root, newest first (none when the root is not there; it is never
    made by asking)."""
    runs = _trace.runs_dir(_host.host_root())
    if not runs.is_dir():
        return []
    rows = []
    for d in sorted((p for p in runs.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)[:limit]:
        tp = d / f"{d.name}.trace.cosm"
        if tp.is_file():
            row = run_row(project_dir, tp)
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda r: (str(r.get("started") or ""), r["run"]), reverse=True)
    return rows


def trace_file(run_id: str) -> Path:
    if not _RUN_ID.match(run_id or "") or ".." in run_id:
        raise HTTPException(400, "a run id is the name of a run's folder")
    found = _trace.find(run_id, root=_host.host_root())
    if found is None:
        raise HTTPException(404, f"no run {run_id}")
    return found


def thym_volume(project_dir: Path, path: str) -> "_macrocosm.Volume | None":
    """A volume `/api/cosm` and `/api/cosm/lens` can load beyond the project's and the store's files, or None: a
    run's plan or trace as `thym:runs/<run>/<file>.cosm` (read under the Thym root, never written), and a program's
    volume as its `.thym` file (a project path, a `canon:` path, or a shipped program's name), enumerated in memory."""
    path = (path or "").strip()
    if path.startswith("thym:"):
        rel = Path(path[len("thym:"):].lstrip("/"))
        if rel.is_absolute() or ".." in rel.parts or len(rel.parts) != 3 or rel.parts[0] != "runs" \
                or not rel.name.endswith((".trace.cosm", ".plan.cosm")):
            raise HTTPException(400, "a thym: path is thym:runs/<run>/<run>.trace.cosm or .plan.cosm")
        target = _host.host_root() / rel
        if not target.is_file():
            raise HTTPException(404, f"no such file: {path}")
        return _macrocosm.load_volume(target)
    if path.endswith(_host.PROGRAM_SUFFIX):
        found = _host.find_program(path, project_dir)
        if found is None:
            # a package's folder form is `<stem>.thym/` (THYM.md 15.1): not a program, so the ordinary volume load
            # draws its catalog (U1's finding in wave 2)
            try:
                if resolve(project_dir, path).is_dir():
                    return None
            except HTTPException:
                pass
            raise HTTPException(404, f"no program {path}")
        vol = program_volume(found)
        if isinstance(vol, Refusal):
            raise HTTPException(400, str(vol.message))
        return volume_from(vol, f"{found.name[: -len('.thym')]}.thym.cosm")
    return None


# ---------------------------------------------------------------------------
# Packages: export and import (THYM.md 15)
# ---------------------------------------------------------------------------

def export_program(*, morph: bool, context: str) -> str:
    """The program export runs: the text, its twin, the author's morph (or nothing), its context (the surrounding
    catalog by `context of`, a context file, or nothing) and the released graph (`graph of`), packaged."""
    takes = "story: text, f: fabula" + (", m: morph" if morph else "") + (", c: context" if context == "file" else "")
    lets = ("  let c = context of story\n" if context == "surrounding" else "") + "  let g = graph of story\n"
    c = "c" if context in ("surrounding", "file") else "nothing"
    return ("thym 0\n\nprogram export\n"
            "  why: a text leaves the house with its fabula, its author's morph and what surrounds it,\n"
            "       exactly as Canon's export gives them; the twin is derived first, never here.\n\n"
            f"  takes {takes}\n  gives out: package\n\n{lets}"
            f"  give package story, f, {'m' if morph else 'nothing'}, {c}, g\nend\n")


def morph_beside(text: Path) -> Path | None:
    """The author's morph kept beside a text: `<text>.morph.cosm`, else `<stem>.morph.cosm`."""
    for name in (f"{text.name}.morph.cosm", f"{stem_of(text)}.morph.cosm"):
        p = text.parent / name
        if p.is_file():
            return p
    return None


def _kind_of(path: Path) -> str | None:
    try:
        data = _macrocosm.yaml_load(_macrocosm.read_text(path))
    except Exception:  # noqa: BLE001
        return None
    return data.get("kind") if isinstance(data, dict) and data.get("oes") == "thym/1" else None


def export_package(project_dir: Path, t: dict, *, morph: Path | None, context: Any, encrypt: bool,
                   catalog_after: Callable[[str], None] | None = None) -> dict:
    """`POST /api/canon/package`, blocking: `{package, folder, key?, sealed?, run, trace}`. `t` is the text target
    (`canon_tools.text_target`); `morph` a morph volume file or None; `context` True (the surrounding catalog),
    False (none) or a context volume file."""
    text: Path = t["target"]
    twin: Path = t["twin"]
    if not _canon.is_emf_twin(twin):
        raise HTTPException(409, f"derive the twin first: {text.name} has no EMF twin, and export derives nothing")
    if _canon.emf_state(text, twin) != "fresh":
        raise HTTPException(409, f"derive the twin first: {twin.name} is stale, {text.name} changed since it was "
                                 "derived")
    if isinstance(context, Path):
        ctx_mode = "file"
    else:
        ctx_mode = "surrounding" if context else "none"
    source = export_program(morph=morph is not None, context=ctx_mode)
    checked = _checked(None, source)
    if isinstance(checked, Refusal):                                # the program is ours: a bug, said plainly
        raise HTTPException(500, f"the export program does not compile: {checked}")
    rows = [{"name": "story", "type": "text", "path": str(text), "sha256": digest_path(text)},
            {"name": "f", "type": "fabula", "path": str(twin), "sha256": digest_path(twin)}]
    if morph is not None:
        rows.append({"name": "m", "type": "morph", "path": str(morph), "sha256": digest_path(morph)})
    if isinstance(context, Path):
        rows.append({"name": "c", "type": "context", "path": str(context), "sha256": digest_path(context)})
    plan = make_plan(checked, rows)
    if isinstance(plan, Refusal):
        raise HTTPException(500, f"the export program does not plan: {plan}")
    kw = runtime(project_dir, mode="rules", why="", scaffolds=False, complete=None, n_ctx=None)
    tr = _run.run(plan, inputs_root=Path(project_dir), program=source, **kw)
    if isinstance(tr, Refusal):
        raise HTTPException(409, tr.message)
    if not tr.landed:
        r = tr.refusal
        raise HTTPException(409, f"the package was not made ({r.check}): {r.message}" if r else "the package was not "
                                                                                               "made")
    outputs = land_beside(project_dir, tr, text)
    row = outputs[0]
    out: dict[str, Any] = {"package": row["rel"], "folder": row.get("folder"), "run": tr.run_id,
                           "trace": str(tr.path)}
    if encrypt:
        single = text.parent / f"{stem_of(text)}{_canon.PACKAGE_FILE_SUFFIX}"
        sealed, key = _vault.seal(single.read_bytes(), path=single.name,
                                  slug=re.sub(r"[^a-z0-9]+", "-", stem_of(text).lower()).strip("-") or "text")
        target = text.parent / f"{stem_of(text)}{_canon.SEALED_SUFFIX}"
        tmp = _tmp_beside(target)
        tmp.write_bytes(sealed)
        os.replace(tmp, target)
        out["sealed"] = rel_of(project_dir, target)
        out["key"] = key                                            # shown once; written nowhere
    if catalog_after is not None:
        catalog_after(t["text_rel"])
    return out


def _package_value(path: Path, key: str | None) -> Value:
    """A package, in any of its three forms, as a value: the folder, the single file, or the sealed file opened with
    its key (400 without one, or with one that does not open it)."""
    if _canon.is_package_folder(path):
        return read_value(path, "package")
    if _canon.is_sealed_package(path):
        if not key:
            raise HTTPException(400, f"{path.name} is sealed: give the key its owner gave you")
        opened = _vault.open(path.read_bytes(), key)
        if isinstance(opened, Refusal):
            raise HTTPException(400 if opened.check == "key" else 409, opened.message)
        data = _macrocosm.yaml_load(opened.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise HTTPException(409, f"{path.name} opens to something that is not a package")
        return Value("package", data, path=None, raw=opened, made={"move": "none"})
    if _canon.is_package_file(path):
        raw = path.read_bytes()
        data = _macrocosm.yaml_load(raw.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise HTTPException(409, f"{path.name} is not a package catalog")
        return Value("package", data, path=None, raw=raw, made={"move": "none"})
    raise HTTPException(400, f"{path.name} is not a package: a package is <name>.thym/, <name>.package.cosm or "
                             "<name>.thym.enc")


def _unpacked_twin(fabula: Value, text_name: str) -> bytes:
    """The package's fabula as the twin of the text written beside it: `source.path` and every locator that said
    `text.md` say the text's name again (THYM.md 15.1, read backwards)."""
    doc = copy.deepcopy(fabula.mapping() or {})
    src = doc.get("source") if isinstance(doc.get("source"), dict) else None
    if src is not None:
        src["path"] = text_name
    rx = re.compile(r"^text\.md(?=#|$)")
    for it in doc.get("nodes") or []:
        prov = it.get("provenance") if isinstance(it, dict) else None
        if isinstance(prov, dict) and isinstance(prov.get("sources"), list):
            prov["sources"] = [rx.sub(text_name, x) if isinstance(x, str) else x for x in prov["sources"]]
    return _macrocosm.dump(doc).encode("utf-8")


def unpack_package(project_dir: Path, path: Path, *, key: str | None = None,
                   catalog_after: Callable[[str], None] | None = None) -> dict:
    """`POST /api/canon/unpack`, blocking: `{text, twin, morph?, context?, graph?, verified: true}`. Every digest is
    verified and every span resolved before anything is written (THYM.md 15.4); a file beside the package that
    differs from what would be written is never overwritten (409), and nothing is written then."""
    from .thym import checks as _checks
    from .thym.moves import pack as _pack
    p = _package_value(path, key)
    ok, why = _checks.verdict("digests", p, {}, {}, None)
    if not ok:
        raise HTTPException(409, f"a digest does not match, so nothing was unpacked: {why}")
    try:
        text = _pack.member(p, "text", "text")
        fabula = _pack.member(p, "fabula", "fabula")
        extra = {role: _pack.member(p, role, role) for role in ("morph", "context", "graph")}
    except Exception as e:  # noqa: BLE001 - a member the catalog names and the package lacks
        raise HTTPException(409, f"the package is incomplete, so nothing was unpacked: {e}") from None
    if text.is_nothing or fabula.is_nothing:
        raise HTTPException(409, "the package carries no text or no fabula, so nothing was unpacked")
    ok, why = _checks.verdict("span-resolves", fabula, {"story": text}, {}, None)
    if not ok:
        raise HTTPException(409, f"a span of the fabula does not resolve into the text, so nothing was unpacked: {why}")
    stem = stem_of(path)
    parent = path.parent
    text_name = f"{stem}.md"
    # The twin is named as its declaration says: a fabula/1 under its flavour's name (`notes.md.fabulan.cosm`), a
    # fabula still saying its old spelling emf/1 under the old name (`notes.md.cosm`), its declaration kept.
    head = fabula.mapping() or {}
    fl = head.get("flavour") if head.get("flavour") in _fabula_names.TEXT_FLAVOURS else "fabulan"
    twin_name = (f"{text_name}{_fabula_names.COSM}" if _fabula_names.is_old_declaration(head.get("oes"))
                 else _fabula_names.twin_name(text_name, fl))
    files: list[tuple[str, Path, bytes]] = [("text", parent / text_name, text.bytes()),
                                            ("twin", parent / twin_name, _unpacked_twin(fabula, text_name))]
    for role, v in extra.items():
        if not v.is_nothing:
            files.append((role, parent / f"{stem}.{role}.cosm", v.bytes()))
    for role, dst, data in files:
        if dst.exists() and (dst.is_dir() or dst.read_bytes() != data):
            raise HTTPException(409, f"{dst.name} is already beside the package and differs from its {role}; it is "
                                     "never overwritten, so nothing was unpacked")
    pairs = []
    scratch = parent / f".unpack-{secrets.token_hex(3)}.tmp"
    try:
        scratch.mkdir()
        for role, dst, data in files:
            if dst.exists():
                continue                                            # the same bytes are there already
            src = scratch / dst.name
            src.write_bytes(data)
            pairs.append((src, dst))
        copy_all(pairs)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    out: dict[str, Any] = {role: rel_of(project_dir, dst) for role, dst, _data in files}
    out["verified"] = True
    if catalog_after is not None:
        catalog_after(out["text"])
    return out


# ---------------------------------------------------------------------------
# Readings (THYM.md 14)
# ---------------------------------------------------------------------------

def reading_program(*, package: bool, morph: str) -> str:
    """The program a reading runs: `read f with mine` over a twin or a package's fabula, in a morph file, the package's
    isomorph, or none (the null morph)."""
    takes = "p: package" if package else "f: fabula"
    lets = "  let f = fabula of p\n" if package else ""
    if morph == "file":
        takes += ", mine: morph"
    elif morph == "isomorph":
        lets += "  let mine = isomorph of p\n"
    give = "read f with mine" if morph in ("file", "isomorph") else "read f"
    return ("thym 0\n\nprogram reading\n"
            "  why: someone else's fabula told in the reader's morph, on the reader's machine,\n"
            "       labelled a reading; the text stands unchanged.\n\n"
            f"  takes {takes}\n  gives r: short\n\n{lets}  give {give}\nend\n")


def reading_path(text: Path, morph: str, now: dt.datetime | None = None) -> Path:
    """`<text-stem>.read-<morph>-YYYY-MM-DD-HHMM.md` beside the text, in local time, `-2`, `-3` on a collision."""
    slug = _MORPH_SLUG.sub("-", (morph or "null").lower()).strip("-") or "null"
    stamp = (now or dt.datetime.now()).astimezone().strftime("%Y-%m-%d-%H%M")
    base = f"{stem_of(text)}.read-{slug}-{stamp}"
    target, n = text.parent / f"{base}.md", 1
    while target.exists():
        n += 1
        target = text.parent / f"{base}-{n}.md"
    return target


def read_through(output: Path) -> str | None:
    """The morph a reading was read through, from its front matter."""
    from .thym.checks import front_matter
    fm, _rest = front_matter(output.read_text(encoding="utf-8"))
    name = fm.get("read_through")
    return str(name) if isinstance(name, str) and name.strip() else None


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------

def build_router(*, project_dir: Path, llm_url: str | None, jobs: Any,
                 canon_mode: Callable[[], Awaitable[tuple[str, str]]], start_job: Callable[..., dict],
                 text_target: Callable[[str], dict], catalog_after: Callable[[str], None],
                 model_complete: Callable[..., Any], cosm_payload: Callable[..., dict]) -> APIRouter:
    """Build the Thym router. One call in `create_app` wires it all."""
    router = APIRouter()
    project_dir = Path(project_dir)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        return body if isinstance(body, dict) else {}

    def program_path(ref: Any, where: Any = None) -> Path:
        """The program a request names; with `where` (`shipped`, `project`, `canon`), in that place only."""
        ref = str(ref or "").strip()
        if not ref:
            raise HTTPException(400, "name a program: its name, its path, or a shipped program's file name")
        place = where_of(where)
        found = _host.find_program(ref, project_dir, where=place)
        if found is None:
            if place == "shipped":
                shipped = sorted(e["rel"] for e in _host.list_programs(None, canon=False, shipped=True))
                raise HTTPException(404, f"no shipped program {ref}; the shipped programs are "
                                         f"{_said(shipped) if shipped else 'none'}")
            if place == "project":
                raise HTTPException(404, f"no program {ref} in this project")
            if place == "canon":
                raise HTTPException(404, f"no program {ref} in the Canon store")
            raise HTTPException(404, f"no program {ref}")
        return found

    def where_of(raw: Any) -> str | None:
        """`where` from a request: None when left out (the program is found as before), else shipped, project or
        canon; 400 in words for anything else."""
        if raw in (None, ""):
            return None
        w = str(raw).strip().lower()
        if w not in _host.WHERES:
            raise HTTPException(400, f"where is shipped, project or canon, not {raw!r}")
        return w

    def where_is(found: Path) -> str:
        """Which place a found program is in: shipped, canon or project."""
        try:
            if found.resolve().parent == _host.SHIPPED_PROGRAMS.resolve():
                return "shipped"
        except OSError:
            pass
        rel = rel_of(project_dir, found) or ""
        return "canon" if rel.startswith("canon:") else "project"

    def route_of(body: dict) -> tuple[str, str | None, int | None]:
        """`(route, model, calls)` from a request (THYM.md 23.1): `route` local (the default) or cloud, or
        `cloud:<model id>`; `model` a cloud model's id; `calls` a ceiling of at least 1. 400 in words otherwise."""
        raw = str(body.get("route") or "local").strip()
        model = body.get("model")
        if raw.startswith("cloud:"):
            raw, model = "cloud", raw[len("cloud:"):]
        if raw not in _host.ROUTES:
            raise HTTPException(400, f"route is local or cloud (or cloud:<model id>), not {raw!r}")
        model = str(model).strip() or None if model not in (None, "") else None
        if raw == "local" and model:
            raise HTTPException(400, "a local run uses this machine's model; model names a cloud model, with route "
                                     "cloud")
        calls = body.get("calls")
        if calls is not None:
            if isinstance(calls, bool) or not isinstance(calls, int) or calls < 1:
                raise HTTPException(400, f"calls is a ceiling of at least 1 model call, not {calls!r}")
        return raw, model, calls

    async def local_mode() -> tuple[str, str]:
        """Model or rules on the local route, whatever slot the chat is on (`canon_mode("local")`)."""
        try:
            return await canon_mode("local")
        except TypeError:                                    # a canon_mode that knows no routes: today's way
            return await canon_mode()

    async def decide(body: dict, route: str = "local") -> tuple[str, str, bool]:
        """`(mode, why, scaffolds)`: the route's mode, decided once before anything runs (module docstring). On the
        cloud route the mode is `model` unless agent-free is on; whether the gate is open is the plan's refusal
        (check `cloud`), so the plan still shows what would run."""
        want = str(body.get("mode") or "auto").strip().lower()
        if want not in ("auto", "model", "rules"):
            raise HTTPException(400, "mode is model, rules, or left out")
        if want == "rules":
            return "rules", "asked", True
        if route == "cloud":
            mode, why = (("rules", _agent_free.REASON) if _agent_free.enabled() else ("model", "cloud"))
        else:
            mode, why = await local_mode()
        if want == "model" and mode != "model":
            raise HTTPException(409, f"no model is running ({why})")
        return mode, why, False

    def inputs_of(body: dict, checked: Any) -> dict[str, Any]:
        """`{name: path}` for every input: `inputs` names each (every one the program takes, of any type; a list of
        paths for an input whose type is a list); `path` alone stands for a program's one input, as the command
        line's bare path does (and for the first input, as before)."""
        inputs = body.get("inputs")
        if isinstance(inputs, dict) and inputs:
            return {str(k): ([str(x) if x is not None else "" for x in v] if isinstance(v, list) else str(v))
                    for k, v in inputs.items()}
        if body.get("path"):
            block = _block(checked)
            if block is None or not block.takes:
                raise HTTPException(400, "the program takes nothing, so a path has nothing to stand for")
            return {block.takes[0].name: str(body.get("path"))}
        raise HTTPException(400, "give inputs: {<name>: <path>}, or a path for the program's first input")

    def prepared(body: dict, *, route: str = "local", model: str | None = None,
                 asks_model: bool = False) -> tuple[Path, Any, dict | Refusal, list[dict], dict | None]:
        """Blocking: the program, its compile, its plan over the request's inputs, and the route as read for it
        (`thym_host.plan_for`: the plan carries `models` when it asks and a model is to answer)."""
        prog = program_path(body.get("program"), body.get("where"))
        checked = _checked(prog)
        if isinstance(checked, Refusal):
            return prog, checked, checked, [], None
        rows = plan_inputs(project_dir, checked, inputs_of(body, checked))
        if asks_model:
            plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url)
            return prog, checked, plan, rows, info
        return prog, checked, make_plan(checked, rows), rows, None

    def plan_refusal(plan: dict, mode: str, why: str, scaffolds: bool, info: dict | None, *, route: str,
                     calls: int | None, prog: Path) -> Refusal | None:
        if scaffolds:
            return scaffold_refusal(plan)
        if mode != "model":
            return asks_refusal(plan, why, route=route, program=prog)
        return _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)

    def inputs_payload(rows: list, block: Any) -> list[dict]:
        """The plan's inputs as the page reads them: `{name, type, rel, sha256, accepts}`, a folder's `files` and
        `bytes`, a list's `members: [{rel, sha256}]` (its `rel` then None)."""
        takes = {r["name"]: r for r in takes_rows(block)}
        inputs = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            listed = isinstance(row.get("members"), list)
            item = {"name": row.get("name"), "type": row.get("type"),
                    "rel": None if listed else rel_of(project_dir, Path(str(row.get("path") or ""))),
                    "sha256": row.get("sha256"),
                    "accepts": (takes.get(row.get("name")) or {}).get("accepts") or _host.accepts(str(row.get("type")))}
            for k in ("files", "bytes"):
                if k in row:
                    item[k] = row[k]
            if listed:
                item["members"] = [{"rel": rel_of(project_dir, Path(str(m.get("path") or ""))),
                                    "sha256": m.get("sha256")} for m in row["members"]]
            inputs.append(item)
        return inputs

    def first_of(rows: list) -> Path | None:
        """The first input's file, which outputs land beside (a list's first member)."""
        return Path(rows[0]["path"]) if rows and rows[0].get("path") else None

    def plan_payload(plan: dict, checked: Any, route: str, calls: int | None, rows: list | None = None) -> dict:
        """What a plan shows before anything runs (THYM.md 23.2): the route, the `models` block and its one line,
        the ceiling, every input with what it takes (a folder's files and bytes), every output, and `writes`: where
        each output will land (`plan_writes`, the run's own naming)."""
        from .thym.cli import models_line
        block = _block(checked) if not isinstance(checked, Refusal) else None
        return {"route": route, "models": _macrocosm.jsonable(plan.get("models")) if plan.get("models") else None,
                "models_line": models_line(plan), "calls": calls, "inputs": inputs_payload(plan.get("inputs"), block),
                "outputs": outputs_rows(block), "writes": plan_writes(project_dir, block, first_of(rows or [])),
                "version": version_of(checked) if block is not None else None}

    # ---------------------------------------------------------------- programs

    @router.get("/api/thym/programs")
    def thym_programs() -> dict:
        return {"programs": [program_row(e) for e in _host.list_programs(project_dir)]}

    @router.get("/api/thym/program")
    def thym_program(path: str = Query(...), where: str | None = Query(None)) -> dict:
        found = program_path(path, where)
        vol = program_volume(found)
        if isinstance(vol, Refusal):
            raise HTTPException(400, f"line {vol.line}: {vol.message}" if vol.line else vol.message)
        prog = next((n for n in vol.get("nodes") or [] if isinstance(n, dict) and n.get("type") == "program"), {})
        entry = next((e for e in _host.list_programs(project_dir) if Path(e["path"]) == found), None)
        rel = entry["rel"] if entry else (rel_of(project_dir, found) or found.name)
        name = found.name[: -len(".thym")]
        return {"name": prog.get("name") or name, "rel": rel, "where": entry["where"] if entry else where_is(found),
                "why": " ".join(str(prog.get("why") or "").split()) or None,
                "source": found.read_text(encoding="utf-8"),
                "volume": cosm_payload(volume_from(vol, f"{name}.thym.cosm"), rel)}

    @router.post("/api/thym/compile")
    async def thym_compile(request: Request) -> dict:
        body = await body_of(request)
        if isinstance(body.get("text"), str):
            return await asyncio.to_thread(compile_payload, text=body["text"])
        return await asyncio.to_thread(lambda: compile_payload(path=program_path(body.get("path"),
                                                                                 body.get("where"))))

    @router.get("/api/thym/moves")
    def thym_moves(version: str = Query("1")) -> dict:
        """Every move a program of grammar `version` (0 or 1) may call, from the declarations a compile reads, in
        the text's order (`thym_tools.moves_payload`, the listing the `thym_moves` tool reads). Read-only."""
        from . import thym_tools as _tt
        raw = str(version).strip().removeprefix("thym").strip()
        if raw not in ("0", "1"):
            raise HTTPException(400, f"version is 0 or 1 (the grammar's `thym <n>` line), not {version!r}")
        return _tt.moves_payload(int(raw))

    # ---------------------------------------------------------------- plans and runs

    def route_complete(route: str, model: str | None) -> Callable[..., Any]:
        """The run's `complete` on its route (pins P6): `local` is the session's `model_complete` while the chat is
        local (llama-server, the same seam as a derivation), else llama-server through the factory, never the cloud
        slot; `cloud` is the factory's cloud route (the gate on every call, the cache under source `thym`, the
        broker's journal), never a fall back to local."""
        from . import llm as _llm
        if route == "local" and _llm._current_slot() != "opro-api":
            return model_complete
        return _host.route_complete(route, model=model, llm_url=llm_url, project_dir=project_dir)

    @router.post("/api/thym/plan")
    async def thym_plan(request: Request) -> dict:
        body = await body_of(request)
        route, model, calls = route_of(body)
        mode, why, scaffolds = await decide(body, route)
        asks_model = mode == "model" and not scaffolds
        prog, checked, plan, rows, info = await asyncio.to_thread(prepared, body, route=route, model=model,
                                                                  asks_model=asks_model)
        out: dict[str, Any] = {"ok": False, "plan": None, "atem": None, "mode": mode, "fits": True, "refusal": None,
                               "route": route, "models": None, "models_line": None, "calls": calls}
        if isinstance(plan, Refusal):
            out["refusal"] = refusal_dict(plan)
            if rows and not isinstance(checked, Refusal):       # inputs checked, the plan held (a list input)
                block = _block(checked)
                out.update(inputs=inputs_payload(rows, block), outputs=outputs_rows(block),
                           writes=plan_writes(project_dir, block, first_of(rows)), version=version_of(checked))
            return out
        r = plan_refusal(plan, mode, why, scaffolds, info, route=route, calls=calls, prog=prog)
        out.update(plan=_macrocosm.jsonable(plan), atem=plan_atem(plan), ok=r is None, refusal=refusal_dict(r))
        out.update(plan_payload(plan, checked, route, calls, rows))
        if r is not None and r.check == "preflight":
            out.update(fits=False, why=r.message)
        return out

    @router.post("/api/thym/run")
    async def thym_run(request: Request) -> dict:
        body = await body_of(request)
        route, model, calls = route_of(body)
        mode, why, scaffolds = await decide(body, route)
        asks_model = mode == "model" and not scaffolds
        prog, checked, plan, rows, info = await asyncio.to_thread(prepared, body, route=route, model=model,
                                                                  asks_model=asks_model)
        if isinstance(plan, Refusal):
            where = f" (line {plan.line})" if plan.line else ""
            raise HTTPException(400, f"{plan.message}{where}")
        r = plan_refusal(plan, mode, why, scaffolds, info, route=route, calls=calls, prog=prog)
        if r is not None:
            raise HTTPException(409, r.message)
        first = Path(rows[0]["path"]) if rows else None
        rel = rel_of(project_dir, first) if first is not None else None
        name = (plan.get("program") or {}).get("name") or prog.stem
        complete = route_complete(route, model) if asks_model else None

        def work(ctx: Any) -> dict:
            def progress(step: dict) -> None:
                ctx.progress(phase="running", chunk=step["node"], chunks=step["of"], progress=step,
                             message=f"step {step['node']} of {step['of']}: {step['move']}")
            kw = runtime(project_dir, mode=mode, why=why, scaffolds=scaffolds, complete=complete,
                         n_ctx=(info or {}).get("window"), route=route, model=model, calls=calls, info=info,
                         program=prog)
            t = _run.run(plan, inputs_root=project_dir, program=prog, progress=progress,
                         should_stop=ctx.should_stop, **kw)
            if isinstance(t, Refusal):
                raise RuntimeError(t.message)
            out = run_result(project_dir, t, first, mode, route=route, plan=plan)
            if out["outputs"] and rel is not None:
                catalog_after(rel)
            out["message"] = t.atem()
            return out

        job_kw: dict[str, Any] = {}
        if _host._accepts(start_job, {"route": route}):
            # the lock is llama-server's: a model run on the local route holds it, a cloud run does not
            job_kw["route"] = route if mode == "model" else None
        return start_job(kind="thym", path=rel, mode=mode, why=why if not scaffolds else "", work=work,
                         key=str(first) if first is not None else None,       # the claim a derivation takes
                         doing=f"running {name} on {first.name if first is not None else 'nothing'}"
                               + (" on the cloud" if mode == "model" and route == "cloud" else ""), **job_kw)

    @router.get("/api/thym/runs")
    def thym_runs() -> dict:
        return {"runs": list_runs(project_dir)}

    @router.get("/api/thym/trace")
    def thym_trace(run: str = Query(...)) -> dict:
        tp = trace_file(run)
        row = run_row(project_dir, tp) or {}
        path = f"thym:runs/{run}/{tp.name}"
        return {"run": run, "atem": row.get("atem"), "outcome": row.get("outcome"),
                "program": row.get("program"), "started": row.get("started"), "seconds": row.get("seconds"),
                "replay_of": row.get("replay_of"), "inputs": row.get("inputs") or [], "path": path,
                "volume": cosm_payload(_macrocosm.load_volume(tp), path)}

    # ---------------------------------------------------------------- packages

    def morph_file(ref: Any, *, beside: Path | None) -> Path | None:
        if ref in (None, ""):
            return morph_beside(beside) if beside is not None else None
        p = resolve(project_dir, str(ref))
        if not p.is_file():
            raise HTTPException(404, f"no such file: {_canon_tools.tidy_rel(str(ref))}")
        if _kind_of(p) != "morph":
            raise HTTPException(400, f"{p.name} is not a morph (a thym/1 volume of kind morph)")
        return p

    @router.post("/api/canon/package")
    async def canon_package(request: Request) -> dict:
        body = await body_of(request)
        t = await asyncio.to_thread(text_target, str(body.get("path") or ""))
        ctx_ref = body.get("context", True)
        if isinstance(ctx_ref, str) and ctx_ref.strip():
            cp = resolve(project_dir, ctx_ref)
            if not cp.is_file():
                raise HTTPException(404, f"no such file: {_canon_tools.tidy_rel(ctx_ref)}")
            if _kind_of(cp) != "context":
                raise HTTPException(400, f"{cp.name} is not a context (a thym/1 volume of kind context)")
            context: Any = cp
        else:
            context = bool(ctx_ref)
        morph = await asyncio.to_thread(morph_file, body.get("morph"), beside=t["target"])

        def go() -> dict:
            try:
                with jobs.holding(t["key"], t["text_rel"]):
                    return export_package(project_dir, t, morph=morph, context=context,
                                          encrypt=bool(body.get("encrypt")), catalog_after=catalog_after)
            except HTTPException:
                raise
            except Exception as e:  # noqa: BLE001 - a claim held by a job is a 409 (canon_jobs.CanonJobError)
                status = getattr(e, "status", None)
                if status:
                    raise HTTPException(status, str(e)) from None
                raise
        return await asyncio.to_thread(go)

    @router.post("/api/canon/unpack")
    async def canon_unpack(request: Request) -> dict:
        body = await body_of(request)
        path = resolve(project_dir, str(body.get("path") or ""))
        if not path.exists():
            raise HTTPException(404, f"no such file: {_canon_tools.tidy_rel(str(body.get('path') or ''))}")
        key = body.get("key")
        return await asyncio.to_thread(unpack_package, project_dir, path, key=str(key) if key else None,
                                       catalog_after=catalog_after)

    # ---------------------------------------------------------------- readings

    @router.post("/api/canon/read")
    async def canon_read(request: Request) -> dict:
        body = await body_of(request)
        raw = str(body.get("path") or "")
        target = resolve(project_dir, raw)
        if not target.exists():
            raise HTTPException(404, f"no such file: {_canon_tools.tidy_rel(raw)}")
        package = _canon.is_package_folder(target) or _canon.is_package_file(target)
        if _canon.is_sealed_package(target):
            raise HTTPException(400, f"{target.name} is sealed: unpack it with its key first, then read the text")
        morph_ref = body.get("morph")
        if morph_ref == "isomorph" and not package:
            raise HTTPException(400, "isomorph is a package's own morph: read a package for it, or name a morph file")
        if package:
            rows = [{"name": "p", "type": "package", "path": str(target), "sha256": digest_path(target)}]
            text_like = target
        else:
            t = await asyncio.to_thread(text_target, raw)
            if not _canon.is_emf_twin(t["twin"]) or _canon.emf_state(t["target"], t["twin"]) != "fresh":
                raise HTTPException(409, f"derive the twin first: a reading reads {t['target'].name}'s fabula, and "
                                         "its twin is missing or stale")
            rows = [{"name": "f", "type": "fabula", "path": str(t["twin"]), "sha256": digest_path(t["twin"])}]
            text_like = t["target"]
        if morph_ref in (None, "", "null"):
            morph_kind = "none"
        elif morph_ref == "isomorph":
            morph_kind = "isomorph"
        else:
            mp = await asyncio.to_thread(morph_file, morph_ref, beside=None)
            rows.append({"name": "mine", "type": "morph", "path": str(mp), "sha256": digest_path(mp)})
            morph_kind = "file"
        source = reading_program(package=package, morph=morph_kind)
        checked = _checked(None, source)
        if isinstance(checked, Refusal):
            raise HTTPException(500, f"the reading program does not compile: {checked}")
        plan = make_plan(checked, rows)
        if isinstance(plan, Refusal):
            raise HTTPException(500, f"the reading program does not plan: {plan}")
        mode, why = await canon_mode()
        rel = rel_of(project_dir, text_like)

        def work(ctx: Any) -> dict:
            if mode != "model":
                raise RuntimeError(f"a reading needs a model, and none is running ({why}); read has no scaffold")
            n_ctx = _host._read_n_ctx(llm_url)
            pre = _host.preflight_hook(n_ctx)(plan) if n_ctx else None
            if pre is not None:
                raise RuntimeError(pre.message)

            def progress(step: dict) -> None:
                ctx.progress(phase="reading", chunk=step["node"], chunks=step["of"], progress=step,
                             message=f"step {step['node']} of {step['of']}: {step['move']}")
            kw = runtime(project_dir, mode="model", why=why, scaffolds=False, complete=model_complete, n_ctx=n_ctx)
            tr = _run.run(plan, inputs_root=project_dir, program=source, progress=progress,
                          should_stop=ctx.should_stop, **kw)
            if isinstance(tr, Refusal):
                raise RuntimeError(tr.message)
            if not tr.landed:
                r = tr.refusal
                raise RuntimeError(f"the reading was refused ({r.check}): {r.message}" if r else "the reading was "
                                                                                                "refused")
            out = Path(tr.outputs["r"])
            label = read_through(out) or "null"
            dst = reading_path(text_like, label)
            copy_all([(out, dst)])
            if rel is not None:
                catalog_after(rel)
            return {"reading": rel_of(project_dir, dst), "label": f"read through {label}", "run": tr.run_id,
                    "trace": str(tr.path), "mode": "model", "message": f"wrote {dst.name}, read through {label}"}

        return start_job(kind="read", path=rel, mode=mode, why=why, work=work,
                         key=str(text_like), doing=f"reading {text_like.name}")

    return router


__all__ = ["build_router", "compile_payload", "export_package", "land_beside", "list_runs", "program_row",
           "thym_volume", "unpack_package"]
