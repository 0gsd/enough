"""A folder of Python decompiled into its fabulac as one resumable job, and the fabulac compiled into a cshort and its
catems (0.6, the fabula round: pins P7; MacroCOSM OES 18.4.1, 18.4.7; THYM 20.6 to 20.8).

**The job.** `defaults/thym/decompile-python.thym` holds five programs, and its header comment is the job's
specification: the host runs them in the order they are written, as one job, each one atomic Thym run, filling each
program's `fabula` input with the fabulac the program before it landed. After each stage the fabulac so far is written
beside the folder as `<folder>.fabulac.cosm` (all at once, never half a file), and the run joins the fabulac's
`derived.runs` (the moves of survey, history and fold write their own entry; for the read and the question stages the
host writes it). A job that stops, for any reason (a cancel, a refusal, a crash, the app quitting), takes up again after
the last stage that landed, and everything it needs is read from disk: the fabulac's `derived.runs` (one entry per
stage, the program `decompile-python.thym`) and each run's trace under the Thym root, never from memory. A job takes up
again only while the folder's tree digest equals the fabulac's `source.tree` (18.4.7); a folder that moved is built
again from the survey.

**Models.** The job's mode is decided once, before it starts, as a derivation's is: `model` when a model answers on
the job's route (`local` by default; `cloud` only when the request says so and the broker's gate is open), else `rules`.
The first two stages ask nothing and always run. In rules (no model answering, agent-free on, or `mode: rules` asked)
the build stops after them with the outline (`derived.completeness: outline`, 18.4.7: "a build with no model runs the
first two stages only"), and the stage that would ask a model is refused in the words the host already uses for a plan
that asks ("3 steps ask a model on the local route, the first `…` (line 51); agent-free is on").

**Compiling.** `compile-python.thym` tells the fabulac as code and as its manual: the code lands beside the fabulac as
the folder `<name>.cshort-<YYYY-MM-DD-HHMM>/` and the manual as `<name>.catem-<YYYY-MM-DD-HHMM>.md` (UTC, `-2`, `-3` on a
collision), and the host records them in the fabulac's `shorts:` and `catems:` (18.4.1; the moves give the values, the
host writes the entries). A catem at one depth (`line`, `overview`, `manual`) runs `tell f as <depth>` alone. Nothing
told is ever run, imported or installed: the cshort is read here, as text.

The plain functions are what the routes translate, and what a test or a tool calls without the app; `build_router`
closes over what `create_app` owns, as `thym_api.build_router` does.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import agent_free as _agent_free
from . import canon_tools as _canon_tools
from . import fabula_names as _fabula_names
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .thym import Refusal

log = logging.getLogger("enough.fabulac_job")

#: The five programs of the shipped file, in the order the job runs them, and the stage each one is.
PROGRAM_FILE = "decompile-python.thym"
COMPILE_FILE = "compile-python.thym"
STAGES: tuple[str, ...] = ("survey-the-repo", "read-the-history", "read-every-file", "fold-the-whole",
                           "raise-the-questions")
STAGE_WORDS = {"survey-the-repo": "survey", "read-the-history": "history", "read-every-file": "read",
               "fold-the-whole": "fold", "raise-the-questions": "question"}
#: The stages that ask no model (the outline): a build with no model runs these and stops (MacroCOSM OES 18.4.7).
RULES_STAGES = 2
#: The output each program gives (survey gives `f`, the others `g`).
OUTPUT = {"survey-the-repo": "f"}
DEPTHS = ("line", "overview", "manual")
JOB_KIND = "fabulac"
FABULAC_SUFFIX = _fabula_names.suffix("fabulac")              # `.fabulac.cosm`
CSHORT_MARK = ".cshort-"
CATEM_MARK = ".catem-"
#: The largest file of a cshort read back as text.
CSHORT_FILE_MAX = 1_000_000
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}(?:-\d+)?$")


class BuildError(Exception):
    """A refusal before anything runs, with the HTTP status a route answers it with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def program_path(name: str = PROGRAM_FILE) -> Path:
    """The shipped program file (never a project's file of the same name: the job is enough's)."""
    return _host.SHIPPED_PROGRAMS / name


def _stamp(now: dt.datetime | None = None) -> str:
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Paths: the folder, its fabulac, and the files compiled beside it
# ---------------------------------------------------------------------------

def _inside(project_dir: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(Path(project_dir).resolve())
        return True
    except (ValueError, OSError):
        return False


def _no_link_on_the_way(project_dir: Path, p: Path) -> bool:
    """No component between the project and `p` (itself included) is a symbolic link."""
    root = Path(project_dir)
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    cur = root
    for part in rel.parts:
        cur = cur / part
        if cur.is_symlink():
            return False
    return True


def project_path(project_dir: Path, rel: str, *, what: str = "path") -> Path:
    """A project path as the routes take it (`canon_tools.resolve`: project-relative, never absolute, never `..`),
    held inside the project with no link on the way. A fabulac and what is compiled from it live in the project, so a
    `canon:` path is refused."""
    raw = _canon_tools.tidy_rel(str(rel or ""))
    if not raw:
        raise BuildError(f"missing {what}")
    if _canon_tools.store_prefix(raw):
        raise BuildError("a fabulac is built from a folder in the project, not in the Canon store")
    try:
        p = _canon_tools.resolve(Path(project_dir), raw)
    except _canon_tools.TextTargetError as e:
        raise BuildError(str(e), getattr(e, "status", 400)) from None
    if not _no_link_on_the_way(Path(project_dir), p) or (p.exists() and not _inside(project_dir, p)):
        raise BuildError(f"{raw} is reached through a link; nothing is read through a link")
    return p


def rel_of(project_dir: Path, p: Path) -> str:
    try:
        return p.relative_to(Path(project_dir)).as_posix()
    except ValueError:
        return _thym_api.rel_of(project_dir, p) or p.name


def fabulac_path(folder: Path) -> Path:
    """`tool/` → `tool.fabulac.cosm` beside it (pins P3.5)."""
    return _fabula_names.twin_path(Path(folder), "fabulac")


def folder_of(fabulac: Path) -> Path | None:
    """`tool.fabulac.cosm` → the folder `tool` beside it, or None for another name."""
    name = Path(fabulac).name
    if not name.endswith(FABULAC_SUFFIX) or len(name) == len(FABULAC_SUFFIX):
        return None
    return Path(fabulac).with_name(name[: -len(FABULAC_SUFFIX)])


def target_of(project_dir: Path, rel: str) -> tuple[Path, Path]:
    """`(folder, fabulac)` for a request's `path`: the folder itself, or its `<folder>.fabulac.cosm`."""
    p = project_path(project_dir, rel)
    if p.name.endswith(FABULAC_SUFFIX):
        folder = folder_of(p)
        assert folder is not None
        return folder, p
    if p.is_symlink():
        raise BuildError(f"{p.name} is a link; a fabulac is built from a folder, and a folder is never read through "
                         "a link")
    if not p.exists():
        raise BuildError(f"no such folder: {rel_of(project_dir, p)}", 404)
    if not p.is_dir():
        raise BuildError(f"{p.name} is a file; a fabulac is built from a folder of Python")
    if p.resolve() == Path(project_dir).resolve():
        raise BuildError("name a folder inside the project; the project itself is not built as a fabulac")
    if p.name == "rness" and p.parent.resolve() == Path(project_dir).resolve():
        raise BuildError("rness/ is enough's own folder, not a program to build a fabulac of")
    return p, fabulac_path(p)


def _load(path: Path) -> dict:
    try:
        data = _macrocosm.yaml_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return {}
    except Exception:  # noqa: BLE001 - a fabulac that does not parse holds no stage
        return {}
    return data if isinstance(data, dict) else {}


def _tree(folder: Path) -> str | None:
    from .thym.values import digest_path
    try:
        return digest_path(folder, "folder")
    except Exception:  # noqa: BLE001 - a folder that cannot be walked has no tree
        return None


# ---------------------------------------------------------------------------
# The state, read from disk: the fabulac's runs and the runs' traces
# ---------------------------------------------------------------------------

def _trace_program(run_id: str) -> str | None:
    """The program a run ran, from its trace under the Thym root, or None when the trace is not there."""
    from .thym import trace as _trace
    try:
        found = _trace.find(run_id, root=_host.host_root())
    except Exception:  # noqa: BLE001
        return None
    if found is None:
        return None
    tv = _trace.load(found)
    if isinstance(tv, Refusal):
        return None
    name = (tv.get("program") or {}).get("name")
    return str(name) if name else None


def build_runs(doc: dict) -> list[dict]:
    """The entries of `derived.runs` the build wrote (a program of `decompile-python.thym`, by its name; an entry that
    names the file is read too), in order."""
    d = doc.get("derived") if isinstance(doc.get("derived"), dict) else {}
    runs = d.get("runs") if isinstance(d.get("runs"), list) else []
    return [r for r in runs if isinstance(r, dict)
            and (str(r.get("program") or "").endswith(PROGRAM_FILE) or r.get("program") in STAGES)]


def build_state(project_dir: Path, folder: Path) -> dict:
    """Where a build of `folder` stands, read from disk alone: `{folder, fabulac, exists, flavour, tree, built_tree,
    moved, stages: [{name, stage, landed, run, at, model, route, provider}], landed, next, complete, completeness,
    python_files}`. A stage has landed when the fabulac's `derived.runs` holds a build run that ran it: named by the
    run's trace (its program), else, when the trace is gone, by its place among the build's runs (the stages run in
    order, and a build that starts again starts from a fresh survey)."""
    fab = fabulac_path(folder)
    doc = _load(fab) if fab.is_file() else {}
    exists = bool(doc) and str(doc.get("oes") or "").split("/")[0] in ("fabula", "emf")
    landed: dict[str, dict] = {}
    if exists:
        for i, r in enumerate(build_runs(doc)):
            name = _trace_program(str(r.get("run") or "")) if r.get("run") else None
            if name not in STAGES and r.get("program") in STAGES:
                name = r["program"]
            if name not in STAGES:
                name = STAGES[i] if i < len(STAGES) else None
            if name:
                landed[name] = r
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    built_tree = src.get("tree") if exists else None
    tree = _tree(folder) if folder.is_dir() else None
    moved = bool(exists and built_tree and tree and built_tree != tree)
    last = max((STAGES.index(n) for n in landed), default=-1)
    stages = []
    for n in STAGES:
        r = landed.get(n) or {}
        stages.append({"name": n, "stage": STAGE_WORDS[n], "landed": n in landed, "run": r.get("run"),
                       "at": _macrocosm.jsonable(r.get("at")), "model": r.get("model"), "route": r.get("route"),
                       "provider": r.get("provider")})
    nxt = STAGES[last + 1] if last + 1 < len(STAGES) else None
    derived = doc.get("derived") if isinstance(doc.get("derived"), dict) else {}
    nodes = doc.get("nodes") if isinstance(doc.get("nodes"), list) else []
    return {"folder": rel_of(project_dir, folder), "fabulac": rel_of(project_dir, fab) if fab.exists() else None,
            "exists": exists, "flavour": doc.get("flavour") if exists else None, "tree": tree,
            "built_tree": built_tree, "moved": moved, "folder_exists": folder.is_dir(), "stages": stages,
            "landed": last + 1, "next": nxt if not moved else STAGES[0], "complete": exists and nxt is None and not moved,
            "completeness": derived.get("completeness") if exists else None,
            "python_files": sum(1 for it in nodes if isinstance(it, dict)
                                and str(it.get("id", "")).startswith("C:file/")
                                and str(it.get("language") or "").lower() == "python") if exists else None}


def start_index(state: dict, *, restart: bool = False, resume_only: bool = False) -> int:
    """Where a build starts: after the last stage that landed, as long as the tree has not moved; the survey when
    asked to start again, when there is no fabulac, or when the folder moved. Refused (409): a complete fabulac without
    `restart`; with `resume_only`, a build with nothing to take up again."""
    if not state["folder_exists"]:
        raise BuildError(f"no such folder: {state['folder']}", 404)
    if restart:
        return 0
    if resume_only:
        if not state["exists"] or state["landed"] == 0:
            raise BuildError(f"nothing to take up again: {state['folder']} has no fabulac yet; build it", 409)
        if state["moved"]:
            raise BuildError(f"nothing to take up again: {state['folder']} changed since its fabulac was surveyed (its "
                             "tree digest moved); build it again from the survey", 409)
    if state["complete"]:
        raise BuildError(f"already built: {state['fabulac']} holds every stage; pass restart to build it again", 409)
    if not state["exists"] or state["moved"]:
        return 0
    return state["landed"]


# ---------------------------------------------------------------------------
# Writing the fabulac: a stage's output, its run in derived.runs, and the compiled files in shorts:/catems:
# ---------------------------------------------------------------------------

def _run_entry(t: Any, stage: str) -> dict:
    """A run as `derived.runs` names it (18.4.1): `{program, run, at, model, route, provider}` (`program` the program's
    name), the last three only when a model ran."""
    env = getattr(t, "environment", None) or {}
    models = sorted({str(r.get("engine"))[len("model:"):] for r in (getattr(t, "records", None) or [])
                     if str(r.get("engine", "")).startswith("model:")})
    entry: dict = {"program": stage, "run": t.run_id, "at": _stamp(t.started)}
    if models:
        entry["model"] = ", ".join(models)
        route = env.get("route") if isinstance(env, dict) else None
        if route:
            entry["route"] = route
        provider = env.get("provider") if isinstance(env, dict) else None
        if provider:
            entry["provider"] = provider
    return entry


def with_run(text: str, entry: dict, *, filename: str) -> str:
    """The fabulac's text with `entry` in `derived.runs` when no entry there names its run already (the survey, the
    history and the fold write their own); every byte outside the change kept (`dialectic.write_back`)."""
    from . import dialectic as _dl
    twin = _dl.twin_from_text(text, filename=filename)
    d = twin.doc.get("derived")
    if not isinstance(d, dict):
        d = twin.doc["derived"] = {}
    runs = d.get("runs")
    if not isinstance(runs, list):
        runs = d["runs"] = []
    hit = next((r for r in runs if isinstance(r, dict) and r.get("run") == entry["run"]), None)
    # `program` is the program's NAME as its `program` line gives it (`survey-the-repo`), not the file's: one file
    # holds five programs (the conductor's ruling, 2026-11-05). The moves write it so; the host writes it so.
    if hit is not None:
        for k in ("model", "route", "provider"):          # a move's own entry gains what only the host knows
            if entry.get(k) and not hit.get(k):
                hit[k] = entry[k]
        if not twin.changed:
            return text
    else:
        runs.append(entry)
    return twin.render()


def write_atomic(path: Path, text: str) -> None:
    from . import dialectic as _dl
    _dl.write_atomic(path, text)


_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:(.*)$")
#: The catalog's keys that come after each list, in 18.4.1's order: a new list is made just above the first of them.
_AFTER = {"shorts": ("catems", "nodes"), "catems": ("nodes",)}


def record_entry(text: str, key: str, entry: dict) -> str:
    """The fabulac's text with one entry appended to `shorts:` or `catems:` (made in its place in 18.4.1's order when
    absent); every other byte kept. Raises BuildError when the result would not read back as the same volume with one
    more entry."""
    from . import canon_derive as _cd
    before = _macrocosm.yaml_load(text)
    if not isinstance(before, dict):
        raise BuildError("the fabulac does not read as a volume; nothing was recorded", 409)
    old = before.get(key)
    if old is not None and not isinstance(old, list):
        raise BuildError(f"the fabulac's {key}: is not a list; fix it by hand", 409)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += nl
    tops = [(i, m) for i, line in enumerate(lines) if (m := _TOP_KEY.match(line.lstrip("﻿")))]
    flow = _cd._flow_entry(entry)
    here = next(((i, m) for i, m in tops if m.group(1) == key), None)
    if here is not None:
        i, m = here
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
            lines[k:k] = [f"{lead}- {flow}{nl}"]
        else:
            entries = [e for e in (old or []) if isinstance(e, dict)] + [entry]
            lines[i:k] = [f"{key}:{nl}"] + [f"  - {_cd._flow_entry(e)}{nl}" for e in entries]
    else:
        at = next((i for i, m in tops if m.group(1) in _AFTER[key]), len(lines))
        while at > 0 and lines[at - 1].lstrip().startswith("#"):
            at -= 1
        lines[at:at] = [f"{key}:{nl}", f"  - {flow}{nl}"]
    out = "".join(lines)
    after = _macrocosm.yaml_load(out)
    got = after.get(key) if isinstance(after, dict) else None
    if (not isinstance(got, list) or len(got) != len(old or []) + 1
            or {k: v for k, v in after.items() if k != key} != {k: v for k, v in before.items() if k != key}):
        raise BuildError(f"the compile could not be recorded in the fabulac's {key}: without changing it; it was "
                         "left as it was", 409)
    return out


# ---------------------------------------------------------------------------
# One stage: its inputs, its plan, its run, its landing
# ---------------------------------------------------------------------------

def _checked(path: Path | None = None, text: str | None = None) -> Any:
    checked = _thym_api._checked(path, text)
    if isinstance(checked, Refusal):                       # the program is enough's: a fault, said plainly
        raise BuildError(f"the build's program does not compile: {checked}", 500)
    return checked


def stage_rows(folder: Path, fab: Path, stage: str) -> list[dict]:
    """The inputs of one stage's program: `repo` the folder (its tree digest), `f` the fabulac so far."""
    from .thym.values import digest_path
    rows = []
    if stage != "raise-the-questions":
        rows.append({"name": "repo", "type": "folder", "path": str(folder), "sha256": digest_path(folder, "folder")})
    if stage != "survey-the-repo":
        rows.append({"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)})
    return rows


def plan_asks(checked: Any, stage: str | None) -> bool:
    from .thym import plan as _plan
    nodes = _plan.build(checked, program=stage)
    return not isinstance(nodes, Refusal) and any(n.asks for n in nodes)


class Counting:
    """The run's coprocessor, counted: every request (re-asks included) and every file a reading asked about. Every
    other attribute is the coprocessor's own."""

    def __init__(self, inner: Any, tally: dict):
        self._inner = inner
        self._tally = tally

    def complete(self, contract: Any, inputs: Any, *, budget: Any, **kw: Any) -> Any:
        self._tally["calls"] = self._tally.get("calls", 0) + 1
        try:
            step = inputs.get("fabulac") if isinstance(inputs, dict) else None
            step = step[0] if isinstance(step, tuple) else step
            step = step.text() if hasattr(step, "text") else step
            p = inputs.get("path") if isinstance(inputs, dict) else None
            p = p[0] if isinstance(p, tuple) else p
            p = p.text() if hasattr(p, "text") else p
            if step == "read" and isinstance(p, str):
                self._tally.setdefault("read", set()).add(p)
        except Exception:  # noqa: BLE001 - counting never stops a run
            pass
        from .thym.coprocessor import _takes_at
        if "at" in kw and not _takes_at(self._inner.complete):
            kw.pop("at")                         # passed on only to a coprocessor that takes it (coprocessor.ask)
        return self._inner.complete(contract, inputs, budget=budget, **kw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


#: `runtime(stage, plan, info, mode, scaffolds) -> run kwargs` (without `progress`/`should_stop`): how a stage's run is
#: given its coprocessor, preflight, environment, root and engines. The app's is `app_runtime`; a test passes its own.
Runtime = Callable[..., dict]


def app_runtime(project_dir: Path, *, why: str, route: str, model: str | None, calls: int | None,
                complete: Callable | None) -> Runtime:
    def make(stage: str, plan: dict, info: dict | None, mode: str, scaffolds: bool, program: Any) -> dict:
        return _thym_api.runtime(project_dir, mode=mode, why=why, scaffolds=scaffolds, complete=complete,
                                 n_ctx=(info or {}).get("window"), route=route, model=model, calls=calls, info=info,
                                 program=program)
    return make


def run_build(project_dir: Path, folder: Path, *, mode: str, why: str = "", route: str = "local",
              model: str | None = None, calls: int | None = None, llm_url: str | None = None,
              scaffolds: bool = False, restart: bool = False, resume_only: bool = False,
              runtime: Runtime | None = None, complete: Callable | None = None,
              progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
              now: dt.datetime | None = None) -> dict:
    """The job's work (blocking): the stages from where the build stands (`start_index`), each planned, run and
    landed in turn. Returns the result `{folder, fabulac, ran: [{stage, run, trace}], state, complete, refusal?,
    calls, message}`; raises DeriveCancelled on a cancel (the stages that landed stay) and RuntimeError when a stage
    is refused while it runs (in the refusal's words, naming the stage the build takes up again from)."""
    from .thym import run as _run
    project_dir = Path(project_dir)
    fab = fabulac_path(folder)
    state = build_state(project_dir, folder)
    first = start_index(state, restart=restart, resume_only=resume_only)
    prog = program_path()
    checked = _checked(prog)
    make = runtime or app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    tally: dict = {"calls": 0}
    ran: list[dict] = []
    refusal: dict | None = None
    stop_note = ""
    total = len(STAGES)

    def say(**fields: Any) -> None:
        if progress is not None:
            progress(fields)

    for i in range(first, total):
        stage = STAGES[i]
        word = STAGE_WORDS[stage]
        if should_stop is not None and should_stop():
            raise DeriveCancelled(_cancelled_words(stage, i))
        asks = plan_asks(checked, stage)
        if asks and (mode != "model" or scaffolds):
            # The outline is what a build without a model writes (18.4.7); the stage that asks is refused in the
            # words a plan that asks is refused with, and the build waits there.
            rows = stage_rows(folder, fab, stage)
            from .thym import plan as _plan
            plan = _plan.plan(checked, rows, program=stage, inputs_root=project_dir)
            r = None
            if not isinstance(plan, Refusal):
                if scaffolds:
                    r = Refusal("plan", "rules", f"a build by rules writes the outline only (survey and history); "
                                                 f"{stage} asks a model")
                else:
                    r = _thym_api.asks_refusal(plan, why, route=route, program=prog)
            else:
                r = plan
            refusal = _thym_api.refusal_dict(r) or {"stage": "plan", "check": "rules", "line": None,
                                                    "message": f"{stage} asks a model"}
            refusal["program"] = stage
            stop_note = f"; {stage} waits: {refusal['message']}"
            break
        rows = stage_rows(folder, fab, stage)
        info = None
        if asks:
            plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, program=stage,
                                        inputs_root=project_dir)
        else:
            from .thym import plan as _plan
            plan = _plan.plan(checked, rows, program=stage, inputs_root=project_dir)
        if isinstance(plan, Refusal):
            raise RuntimeError(_stopped(stage, plan, i))
        if asks:
            r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
            if r is not None:
                raise RuntimeError(_stopped(stage, r, i))
        models = plan.get("models") if isinstance(plan.get("models"), dict) else {}
        at_most = models.get("at_most")
        say(phase=word, chunk=i + 1, chunks=total, message=f"stage {i + 1} of {total}: {word}",
            progress=_progress(stage, i, tally, at_most, route if asks else None, state))
        kw = make(stage, plan, info, mode if asks else "rules", False, prog)
        if asks and kw.get("coprocessor") is not None:
            kw["coprocessor"] = Counting(kw["coprocessor"], tally)

        def step(s: dict, _stage: str = stage, _i: int = i, _at: Any = at_most) -> None:
            say(phase=STAGE_WORDS[_stage], chunk=_i + 1, chunks=total,
                message=f"stage {_i + 1} of {total}: {STAGE_WORDS[_stage]}"
                        + (f", {len(tally.get('read', ()))} of {state.get('python_files') or '?'} files read"
                           if _stage == "read-every-file" else ""),
                progress={**_progress(_stage, _i, tally, _at, route if asks else None, state), "step": s})
        t = _run.run(plan, inputs_root=project_dir, program=prog, progress=step, should_stop=should_stop,
                     **({"now": now} if now is not None else {}), **kw)
        if isinstance(t, Refusal):
            raise RuntimeError(_stopped(stage, t, i))
        if not t.landed:
            if t.refusal is not None and t.refusal.check == "cancelled":
                raise DeriveCancelled(_cancelled_words(stage, i))
            raise RuntimeError(_stopped(stage, t.refusal, i))
        out = Path(t.outputs[OUTPUT.get(stage, "g")])
        text = out.read_text(encoding="utf-8")
        text = with_run(text, _run_entry(t, stage), filename=fab.name)
        write_atomic(fab, text)
        ran.append({"stage": word, "program": stage, "run": t.run_id, "trace": str(t.path)})
        state = build_state(project_dir, folder)
    final = build_state(project_dir, folder)
    landed_words = ", ".join(r["stage"] for r in ran) or "nothing"
    done = final["complete"]
    msg = (f"{fab.name}: every stage landed" if done else f"{fab.name}: {landed_words} landed{stop_note}")
    out = {"folder": final["folder"], "fabulac": final["fabulac"], "ran": ran, "state": final, "complete": done,
           "calls": {"made": tally.get("calls", 0), "files_read": len(tally.get("read", ()))},
           "message": msg}
    if refusal is not None:
        out["refusal"] = refusal
    return out


def _progress(stage: str, i: int, tally: dict, at_most: Any, route: str | None, state: dict) -> dict:
    """A running build's status (the job's `progress`): the stage, files read n of m, model calls made and at most,
    the route."""
    return {"stage": STAGE_WORDS[stage], "program": stage, "n": i + 1, "of": len(STAGES),
            "files_read": len(tally.get("read", ())), "files": state.get("python_files"),
            "calls": tally.get("calls", 0), "at_most": at_most, "route": route}


def _cancelled_words(stage: str, i: int) -> str:
    landed = ", ".join(STAGE_WORDS[s] for s in STAGES[:i]) or "nothing"
    return (f"cancelled during {STAGE_WORDS[stage]}; nothing of it was written; landed before it: {landed}; the "
            f"build takes up again from {STAGE_WORDS[stage]}")


def _stopped(stage: str, r: Any, i: int) -> str:
    said = (f"{r.check}, {r.message}" + (f" (line {r.line})" if getattr(r, "line", None) else "")) if r is not None \
        else "refused"
    landed = ", ".join(STAGE_WORDS[s] for s in STAGES[:i]) or "nothing"
    return (f"{STAGE_WORDS[stage]} was refused ({said}); nothing of it was written; landed before it: {landed}; "
            f"the build takes up again from {STAGE_WORDS[stage]}")


# ---------------------------------------------------------------------------
# Compiling: the cshort, the catems, and their entries in the fabulac
# ---------------------------------------------------------------------------

def catem_program(depth: str) -> str:
    """The program a catem at one depth runs: `tell f as <depth>` (THYM 20.7)."""
    if depth not in DEPTHS:
        raise BuildError(f"a catem's depth is line, overview or manual, not {depth!r}")
    return ("thym 1\n\nprogram catem\n"
            f"  why: a fabulac told at depth {depth}, the catem a person reads.\n"
            "  must: nothing told is run, imported or installed.\n\n"
            "  takes f: fabula\n  gives c: short\n\n"
            f"  give tell f as {depth}\nend\n")


def compiled_name(fab: Path) -> str:
    """The name a cshort and a catem take: the fabulac's file name less `.fabulac.cosm` (`days`)."""
    return fab.name[: -len(FABULAC_SUFFIX)] if fab.name.endswith(FABULAC_SUFFIX) else Path(fab).stem


def free_path(parent: Path, base: str, ext: str = "") -> Path:
    """`<base><ext>`, else `<base>-2<ext>`, `-3`…: never over anything there."""
    target, n = parent / f"{base}{ext}", 1
    while target.exists() or target.is_symlink():
        n += 1
        target = parent / f"{base}-{n}{ext}"
    return target


def _files_of(folder: Path) -> list[Path]:
    return sorted((p for p in folder.rglob("*") if p.is_file() and not p.is_symlink()),
                  key=lambda p: p.relative_to(folder).as_posix())


def fabulac_of(project_dir: Path, rel: str) -> Path:
    """The fabulac a compile or a listing names: the `.fabulac.cosm` file, or the folder it was built from."""
    p = project_path(project_dir, rel)
    if not p.name.endswith(FABULAC_SUFFIX) and p.is_dir() and not p.is_symlink():
        p = fabulac_path(p)
    if not p.name.endswith(FABULAC_SUFFIX):
        raise BuildError(f"{p.name} is not a fabulac; a fabulac is <folder>.fabulac.cosm")
    if not p.is_file():
        raise BuildError(f"no fabulac yet: {rel_of(project_dir, p)}; build it first", 404)
    head = _load(p)
    if head.get("flavour") != "fabulac":
        raise BuildError(f"{p.name} is not a fabulac (its flavour is {head.get('flavour') or 'fabulan'}); only a "
                         "fabulac is told as code or as a catem")
    return p


def run_compile(project_dir: Path, fab: Path, *, what: str, mode: str, why: str = "", route: str = "local",
                model: str | None = None, calls: int | None = None, llm_url: str | None = None,
                scaffolds: bool = False, runtime: Runtime | None = None, complete: Callable | None = None,
                progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
                now: dt.datetime | None = None) -> dict:
    """The compile's work (blocking). `what` is `code` (`compile-python.thym`: the cshort and the manual catem) or a
    depth (`line`, `overview`, `manual`: that catem alone). The outputs land beside the fabulac all at once, and the
    fabulac records them in `shorts:` and `catems:`. Returns `{fabulac, cshort?, catems: [...], run, trace, mode,
    route, model, recorded, message}`; raises RuntimeError in the refusal's words when the run does not land."""
    from .thym import plan as _plan
    from .thym import run as _run
    project_dir = Path(project_dir)
    if what == "code":
        prog: Any = program_path(COMPILE_FILE)
        checked = _checked(prog)
        source: Any = prog
    else:
        source = catem_program(what)
        checked = _checked(None, source)
        prog = source
    from .thym.values import digest_path
    rows = [{"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)}]
    asks = plan_asks(checked, None)
    use_model = asks and mode == "model" and not scaffolds
    if use_model:
        plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, inputs_root=project_dir)
    else:
        plan, info = _plan.plan(checked, rows, inputs_root=project_dir), None
    if isinstance(plan, Refusal):
        raise RuntimeError(f"the compile was refused ({plan.check}): {plan.message}")
    if asks and not use_model:
        r = _thym_api.scaffold_refusal(plan) if (scaffolds or mode != "model") else None
        if r is not None and not scaffolds:
            # No model: a catem by its scaffold, a cshort refused (`tell … as code` has no scaffold), as a run with
            # --rules is; the words say why there is no model.
            no = _thym_api.asks_refusal(plan, why, route=route, program=prog)
            if no is not None:
                r = Refusal("plan", no.check, f"{no.message}; {r.message}", line=no.line)
        if r is not None:
            raise RuntimeError(r.message)
    elif use_model:
        r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
        if r is not None:
            raise RuntimeError(r.message)
    make = runtime or app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    kw = make("compile", plan, info, "model" if use_model else "rules", asks and not use_model, prog)
    if progress is not None:
        progress({"phase": "compiling", "message": f"compiling {fab.name}" + (" as code" if what == "code"
                                                                               else f" at depth {what}")})
    t = _run.run(plan, inputs_root=project_dir, program=source, should_stop=should_stop,
                 **({"now": now} if now is not None else {}), **kw)
    if isinstance(t, Refusal):
        raise RuntimeError(f"the compile was refused ({t.check}): {t.message}")
    if not t.landed:
        r = t.refusal
        if r is not None and r.check == "cancelled":
            raise DeriveCancelled("cancelled; nothing was written")
        raise RuntimeError(f"the compile was refused ({r.check}): {r.message}" if r else "the compile was refused")
    when = t.started if isinstance(t.started, dt.datetime) else dt.datetime.now(dt.timezone.utc)
    when = when.astimezone(dt.timezone.utc)
    stamp = when.strftime("%Y-%m-%d-%H%M")
    name = compiled_name(fab)
    models = sorted({str(r.get("engine"))[len("model:"):] for r in t.records
                     if str(r.get("engine", "")).startswith("model:")})
    run_mode = "model" if models else "rules"
    by = ", ".join(models) if models else "rules"
    env = t.environment if isinstance(t.environment, dict) else {}
    run_route = (env.get("route") or route) if run_mode == "model" else None
    pairs: list[tuple[Path, Path]] = []
    out: dict = {"fabulac": rel_of(project_dir, fab), "run": t.run_id, "trace": str(t.path), "mode": run_mode,
                 "route": run_route, "model": by if run_mode == "model" else None, "catems": [], "cshort": None}
    entries: list[tuple[str, dict]] = []
    at = when.replace(microsecond=0)
    if what == "code":
        code = Path(t.outputs["code"])
        dst = free_path(fab.parent, f"{name}{CSHORT_MARK}{stamp}")
        pairs.append((code, dst))
        files = [p for p in _files_of(code) if p.relative_to(code).as_posix() != "CSHORT.md"]
        entry = {"path": f"{dst.name}/", "at": at, "by": by, "mode": run_mode, "order": "code"}
        if run_route:
            entry["route"] = run_route
        entry.update({"language": "python", "files": len(files)})
        entries.append(("shorts", entry))
        out["cshort"] = {"path": rel_of(project_dir, dst) + "/", "files": len(files)}
        manual = Path(t.outputs["manual"])
        cdst = free_path(fab.parent, f"{name}{CATEM_MARK}{stamp}", ".md")
        pairs.append((manual, cdst))
        entries.append(("catems", _catem_entry(cdst, at, by, run_mode, run_route, "manual")))
        out["catems"].append({"path": rel_of(project_dir, cdst), "depth": "manual"})
    else:
        c = Path(t.outputs["c"])
        cdst = free_path(fab.parent, f"{name}{CATEM_MARK}{stamp}", ".md")
        pairs.append((c, cdst))
        entries.append(("catems", _catem_entry(cdst, at, by, run_mode, run_route, what)))
        out["catems"].append({"path": rel_of(project_dir, cdst), "depth": what})
    _thym_api.copy_all(pairs)
    recorded = True
    try:
        text = fab.read_bytes().decode("utf-8")
        for key, entry in entries:
            text = record_entry(text, key, entry)
        write_atomic(fab, text)
    except (OSError, UnicodeDecodeError, BuildError) as e:
        recorded = False
        log.warning("fabulac: wrote the compile beside %s but could not record it (%s)", fab.name, e)
    out["recorded"] = recorded
    wrote = ", ".join(Path(d).name + ("/" if Path(s).is_dir() else "") for s, d in pairs)
    out["message"] = f"wrote {wrote}" + ("" if recorded else f"; {fab.name} could not record it")
    return out


def _catem_entry(path: Path, at: dt.datetime, by: str, mode: str, route: str | None, depth: str) -> dict:
    entry: dict = {"path": path.name, "at": at, "by": by, "mode": mode}
    if route:
        entry["route"] = route
    entry["depth"] = depth
    return entry


# ---------------------------------------------------------------------------
# Reading what was compiled: read-only, as text, never run
# ---------------------------------------------------------------------------

def compiled(project_dir: Path, fab: Path) -> dict:
    """A fabulac's cshorts and catems, from its catalog: `{fabulac, name, shorts: [entry + {exists, kind}], catems:
    [entry + {exists}]}` (entries as 18.4.1 writes them; `rel` the project path of each)."""
    doc = _load(fab)

    def rows(key: str) -> list[dict]:
        out = []
        for e in doc.get(key) or []:
            if not isinstance(e, dict):
                continue
            row = _macrocosm.jsonable(dict(e))
            p = fab.parent / str(e.get("path") or "").rstrip("/")
            row["rel"] = rel_of(project_dir, p) + ("/" if str(e.get("path") or "").endswith("/") else "")
            row["exists"] = p.exists() and not p.is_symlink()
            if key == "shorts":
                row["kind"] = "cshort" if e.get("order") == "code" else "short"
            out.append(row)
        return out
    return {"fabulac": rel_of(project_dir, fab), "name": compiled_name(fab), "shorts": rows("shorts"),
            "catems": rows("catems")}


def cshort_of(project_dir: Path, rel: str) -> Path:
    p = project_path(project_dir, rel.rstrip("/"))
    if CSHORT_MARK not in p.name:
        raise BuildError(f"{p.name} is not a cshort; a cshort is the folder <name>.cshort-<stamp>/")
    if p.is_symlink() or not p.is_dir():
        raise BuildError(f"no such cshort: {rel_of(project_dir, p)}/", 404)
    return p


def cshort_tree(project_dir: Path, rel: str) -> dict:
    """A cshort's files, read-only: `{path, files: [{path, bytes}], cshort_md, footer, licence}`. A link inside it is
    listed as a link and never followed."""
    root = cshort_of(project_dir, rel)
    files: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if not (d / n).is_symlink())
        for n in sorted(filenames):
            f = d / n
            r = f.relative_to(root).as_posix()
            if f.is_symlink():
                files.append({"path": r, "link": True})
                continue
            try:
                files.append({"path": r, "bytes": f.stat().st_size})
            except OSError:
                continue
    files.sort(key=lambda x: x["path"])
    md_path = root / "CSHORT.md"
    md = md_path.read_text(encoding="utf-8", errors="replace") if md_path.is_file() and not md_path.is_symlink() \
        else None
    lines = [ln for ln in (md or "").splitlines() if ln.strip()]
    return {"path": rel_of(project_dir, root) + "/", "files": files, "cshort_md": md,
            "footer": lines[0] if lines else None,
            "licence": lines[-1] if lines and lines[-1].startswith("Licence of the source") else None}


def cshort_file(project_dir: Path, rel: str, file: str) -> dict:
    """One file of a cshort, as text: `{path, file, text, bytes}`. Refused: a path out of the cshort, a link, a file
    that is not UTF-8 text, one over CSHORT_FILE_MAX bytes. It is read, never run."""
    root = cshort_of(project_dir, rel)
    name = (file or "").replace("\\", "/").strip().strip("/")
    parts = [x for x in name.split("/") if x not in ("", ".")]
    if not parts or any(x == ".." for x in parts) or name.startswith("/"):
        raise BuildError("name a file inside the cshort, by its path there")
    f = root.joinpath(*parts)
    cur = root
    for x in parts:
        cur = cur / x
        if cur.is_symlink():
            raise BuildError(f"{name} is a link; nothing in a cshort is read through a link")
    if not f.is_file():
        raise BuildError(f"no such file in the cshort: {name}", 404)
    try:
        f.resolve().relative_to(root.resolve())
    except ValueError:
        raise BuildError(f"{name} is not inside the cshort") from None
    size = f.stat().st_size
    if size > CSHORT_FILE_MAX:
        raise BuildError(f"{name} is {size:,} bytes, over {CSHORT_FILE_MAX:,}: too long to show")
    try:
        text = f.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise BuildError(f"{name} is not UTF-8 text, so it is not shown") from None
    return {"path": rel_of(project_dir, root) + "/", "file": name, "text": text, "bytes": size}


def catem_text(project_dir: Path, rel: str) -> dict:
    """A catem, read-only: `{path, text, depth, footer}` (the depth read from its footer line)."""
    p = project_path(project_dir, rel)
    if CATEM_MARK not in p.name or not p.name.endswith(".md"):
        raise BuildError(f"{p.name} is not a catem; a catem is <name>.catem-<stamp>.md")
    if p.is_symlink() or not p.is_file():
        raise BuildError(f"no such catem: {rel_of(project_dir, p)}", 404)
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    footer = lines[-1] if lines else None
    m = re.search(r"at depth (line|overview|manual)", footer or "")
    return {"path": rel_of(project_dir, p), "text": text, "depth": m.group(1) if m else None, "footer": footer}


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------

def _http(e: BuildError) -> HTTPException:
    return HTTPException(e.status, str(e))


def build_router(*, project_dir: Path, llm_url: str | None, jobs: Any,
                 canon_mode: Callable[..., Awaitable[tuple[str, str]]], start_job: Callable[..., dict],
                 model_complete: Callable[..., Any], catalog_after: Callable[[str], None],
                 compile_short: Callable[[dict], Awaitable[dict]] | None = None) -> APIRouter:
    """The fabulac's routes under `/api/fabula/` (build, resume, status, cancel, compile, and the read-only views of
    what was compiled). `compile_short` is the server's compile of a text's fabula into a short, which
    `/api/fabula/compile` hands every fabula that is not a fabulac."""
    router = APIRouter()
    project_dir = Path(project_dir)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        return body if isinstance(body, dict) else {}

    def route_of(body: dict) -> tuple[str, str | None, int | None]:
        raw = str(body.get("route") or "local").strip().lower()
        model = body.get("model")
        if raw.startswith("cloud:"):
            raw, model = "cloud", raw[len("cloud:"):]
        if raw not in _host.ROUTES:
            raise HTTPException(400, f"route is local or cloud (or cloud:<model id>), not {raw!r}")
        model = (str(model).strip() or None) if model not in (None, "") else None
        if raw == "local" and model:
            raise HTTPException(400, "a local build uses this machine's model; model names a cloud model, with route "
                                     "cloud")
        calls = body.get("calls")
        if calls is not None and (isinstance(calls, bool) or not isinstance(calls, int) or calls < 1):
            raise HTTPException(400, f"calls is a ceiling of at least 1 model call, not {calls!r}")
        return raw, model, calls

    async def decide(body: dict, route: str) -> tuple[str, str, bool]:
        """`(mode, why, scaffolds)`, decided once before the job starts. Cloud: the gate is read here (403 in the
        gate's own words when it is shut, as a derivation's); agent-free gives rules on either route."""
        want = str(body.get("mode") or "auto").strip().lower()
        if want not in ("auto", "model", "rules"):
            raise HTTPException(400, "mode is model, rules, or left out")
        if want == "rules":
            return "rules", "asked", True
        try:
            mode, why = await canon_mode(route)
        except TypeError:
            mode, why = await canon_mode()
        if want == "model" and mode != "model":
            raise HTTPException(409, f"no model is running ({why})")
        return mode, why, False

    def complete_for(route: str, model: str | None) -> Callable[..., Any]:
        from . import llm as _llm
        if route == "local" and _llm._current_slot() != "opro-api":
            return model_complete
        return _host.route_complete(route, model=model, llm_url=llm_url, project_dir=project_dir)

    def job_kw(route: str, mode: str) -> dict:
        return {"route": route} if _host._accepts(start_job, {"route": route}) else {}

    async def start_build(body: dict, *, resume_only: bool = False) -> dict:
        route, model, calls = route_of(body)
        try:
            folder, fab = await asyncio.to_thread(target_of, project_dir, str(body.get("path") or ""))
            state = await asyncio.to_thread(build_state, project_dir, folder)
            first = start_index(state, restart=bool(body.get("restart")), resume_only=resume_only)
        except BuildError as e:
            raise _http(e) from None
        mode, why, scaffolds = await decide(body, route)
        complete = complete_for(route, model) if mode == "model" and not scaffolds else None
        rel = state["folder"]

        def work(ctx: Any) -> dict:
            out = run_build(project_dir, folder, mode=mode, why=why, route=route, model=model, calls=calls,
                            llm_url=llm_url, scaffolds=scaffolds, restart=bool(body.get("restart")),
                            resume_only=resume_only, complete=complete, progress=lambda f: ctx.progress(f),
                            should_stop=ctx.should_stop)
            catalog_after(rel)
            return out

        from_words = (f"taking up the build of {folder.name}/ from {STAGE_WORDS[STAGES[first]]}"
                      if first else f"building the fabulac of {folder.name}/")
        snap = start_job(kind=JOB_KIND, path=rel, mode=mode, why=why if not scaffolds else "", work=work,
                         key=str(folder.resolve()), doing=from_words + (" on the cloud" if mode == "model"
                                                                        and route == "cloud" else ""),
                         **job_kw(route if mode == "model" else None, mode))
        return {**snap, "state": state, "from": STAGES[first]}

    @router.post("/api/fabula/build")
    async def fabula_build(request: Request) -> dict:
        return await start_build(await body_of(request), resume_only=False)

    @router.post("/api/fabula/resume")
    async def fabula_resume(request: Request) -> dict:
        return await start_build(await body_of(request), resume_only=True)

    @router.get("/api/fabula/build")
    def fabula_build_state(path: str = Query(...)) -> dict:
        try:
            folder, _fab = target_of(project_dir, path)
        except BuildError as e:
            raise _http(e) from None
        state = build_state(project_dir, folder)
        job_id = jobs.running_for(str(folder.resolve())) if jobs is not None else None
        return {"state": state, "job": jobs.snapshot(job_id) if job_id else None}

    @router.post("/api/fabula/cancel")
    async def fabula_cancel(request: Request) -> dict:
        body = await body_of(request)
        try:
            folder, _fab = target_of(project_dir, str(body.get("path") or ""))
        except BuildError as e:
            raise _http(e) from None
        job_id = jobs.running_for(str(folder.resolve())) if jobs is not None else None
        if not job_id:
            raise HTTPException(409, f"no build or compile of {folder.name}/ is running")
        try:
            return jobs.cancel(job_id)
        except Exception as e:  # noqa: BLE001 - CanonJobError carries its status
            raise HTTPException(getattr(e, "status", 409), str(e)) from None

    @router.post("/api/fabula/compile")
    async def fabula_compile(request: Request) -> dict:
        """A fabula compiled: a fabulac into its cshort and manual (`what: code`, the default) or a catem at one depth
        (`what: line | overview | manual`); any other fabula into a short (the text's compile, `order`)."""
        return await start_compile(await body_of(request))

    async def start_compile(body: dict) -> dict:
        raw = str(body.get("path") or "")
        p = None
        try:
            p = project_path(project_dir, raw)
        except BuildError:
            p = None
        is_fabulac = p is not None and (p.name.endswith(FABULAC_SUFFIX)
                                        or (p.is_dir() and not p.is_symlink() and fabulac_path(p).is_file()))
        if not is_fabulac:
            if compile_short is None:
                raise HTTPException(400, "compile reads a fabulac here: <folder>.fabulac.cosm")
            return await compile_short(body)
        what = str(body.get("what") or "code").strip().lower()
        if what not in ("code",) + DEPTHS:
            raise HTTPException(400, f"what is code, line, overview or manual, not {what!r}")
        route, model, calls = route_of(body)
        try:
            fab = await asyncio.to_thread(fabulac_of, project_dir, raw)
        except BuildError as e:
            raise _http(e) from None
        mode, why, scaffolds = await decide(body, route)
        if what == "code" and (mode != "model" or scaffolds):
            plan_words = ("tell … as code has no scaffold, so a cshort needs a model" if scaffolds else
                          f"a cshort needs a model, and none is answering ({'agent-free is on' if why == _agent_free.REASON else why})")
            raise HTTPException(409, plan_words)
        complete = complete_for(route, model) if mode == "model" and not scaffolds else None
        folder = folder_of(fab)
        key = str(folder.resolve()) if folder is not None else str(fab)

        def work(ctx: Any) -> dict:
            out = run_compile(project_dir, fab, what=what, mode=mode, why=why, route=route, model=model, calls=calls,
                              llm_url=llm_url, scaffolds=scaffolds or mode != "model", complete=complete,
                              progress=lambda f: ctx.progress(f), should_stop=ctx.should_stop)
            catalog_after(rel_of(project_dir, fab))
            return out

        doing = f"compiling {fab.name}" + (" as code" if what == "code" else f" at depth {what}")
        return start_job(kind="compile", path=rel_of(project_dir, fab), mode=mode, why=why if not scaffolds else "",
                         work=work, key=key, doing=doing + (" on the cloud" if mode == "model" and route == "cloud"
                                                           else ""),
                         **job_kw(route if mode == "model" else None, mode))

    # what the agent's tools start through (enough/fabula_tools.py), the same code as the routes
    router.start_build = start_build            # type: ignore[attr-defined]
    router.start_compile = start_compile        # type: ignore[attr-defined]

    @router.get("/api/fabula/compiled")
    def fabula_compiled(path: str = Query(...)) -> dict:
        try:
            return compiled(project_dir, fabulac_of(project_dir, path))
        except BuildError as e:
            raise _http(e) from None

    @router.get("/api/fabula/cshort")
    def fabula_cshort(path: str = Query(...)) -> dict:
        try:
            return cshort_tree(project_dir, path)
        except BuildError as e:
            raise _http(e) from None

    @router.get("/api/fabula/cshort/file")
    def fabula_cshort_file(path: str = Query(...), file: str = Query(...)) -> dict:
        try:
            return cshort_file(project_dir, path, file)
        except BuildError as e:
            raise _http(e) from None

    @router.get("/api/fabula/catem")
    def fabula_catem(path: str = Query(...)) -> dict:
        try:
            return catem_text(project_dir, path)
        except BuildError as e:
            raise _http(e) from None

    return router


__all__ = ["BuildError", "COMPILE_FILE", "DEPTHS", "PROGRAM_FILE", "STAGES", "STAGE_WORDS", "build_router",
           "build_runs", "build_state", "catem_program", "catem_text", "compiled", "cshort_file", "cshort_tree",
           "fabulac_of", "fabulac_path", "folder_of", "record_entry", "run_build", "run_compile", "start_index",
           "target_of", "with_run"]
