"""The readvisor's Thym tools: `thym_check` and `thym_run` (0.5.0, wave 2, R1; docs/THYM.md 11.3, 12.1, 12.5, 19).

Registered into `tools._DISPATCH` the way `canon_tools` is, and traced under the universal toggle like the other
MacroCOSM tools. Their tags are in `prompt.CANON_TOOL_INSTRUCTIONS` (the owner's 1,000-character block), and their
guide is the `macrocosm-oes` skill.

**Behind the skill.** The owner decided (docs/thym-050-plan.md §3) that both tools sit behind the `macrocosm-oes`
skill: with the skill off in this project, a runner answers with the one line that says how to switch it on, and
runs nothing. The skill's body then rides in the turn, so the details the block has no room for are there whenever
the tools can be used.

**The same steps as the command line.** `thym_check` is `python -m enough.thym check` followed by a plan, so the
answer carries the one-line estimate `plan` prints (`cli.plan_atem`, word for word). `thym_run` is `cli.cmd_run`:
check, plan, preflight, run. A program is found by `thym_host.find_program` (the rule the routes and the viewers
share: the project's own programs, then the Canon store's, then the shipped ones); a path is read by the routes'
rule (`canon_tools.resolve`: project-relative or `canon:<volume>/...`, never absolute, never `..`).

**Never the lock.** A tool runs inside a chat turn, and the turn already holds `session.generation_lock`, so
`thym_run` asks the model through `canon_tools.model()`, the closure the MacroCOSM tools use, and takes no lock and
starts no job. With no model answering, or with agent-free on (THYM.md 19), a plan whose steps ask a model is refused
at plan time with their count; a plan with none runs on code alone. Rules-mode scaffolds are left to the reader's
run-with, which labels what they make: a chat turn says no rather than hand back a pending stand-in.

**The landing.** A run lands under the Thym root (`thym_host.host_root()`, the `ENOUGH_THYM_ROOT` seam) and nowhere
else: outputs in `runs/<run-id>/outputs/`, the trace beside them. Copying the outputs beside the text is the routes'
landing (the reader's run-with), not the tool's, and the answer says so. The run is announced as a finished job of
kind `thym` in `canon_jobs`' shape (the `canon` event; runs are CanonJobs of kind `thym`, per the wave-2 contract),
whose `result` names the run id and the trace path.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("enough.thym_tools")

TOOL_NAMES: tuple[str, ...] = ("thym_check", "thym_run")

#: The skill both tools answer to (the owner's decision, docs/thym-050-plan.md §3).
SKILL_NAME = "macrocosm-oes"

#: The job kind a run is announced as (the wave-2 contract: runs are CanonJobs of kind `thym`).
JOB_KIND = "thym"

#: What a landed run's answer says about where its outputs are.
OUTPUTS_NOTE = "the outputs are in the run; the reader's run-with lands them beside the text"

#: Program names listed when a program is not found.
PROGRAMS_SHOWN = 12


# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------

def _ct():
    from . import canon_tools
    return canon_tools


def _result(name: str, key: str, ok: bool, body: str, side_effects: dict | None = None) -> Any:
    return _ct()._result(name, key, ok, body, side_effects)


def _err(name: str, key: str, message: str) -> Any:
    return _ct()._err(name, key, message)


def skill_on(project_dir: Path) -> bool:
    """Is the `macrocosm-oes` skill switched on in this project? Read as the prompt reads it, so the tools and the
    Skills section never disagree."""
    from . import prompt
    return prompt._skill_enabled(Path(project_dir) / "rness", SKILL_NAME)


def _skill_off(name: str, key: str) -> Any:
    return _err(name, key, f"{name} comes with the {SKILL_NAME} skill, which is off in this project: ask the user to "
                           "switch it on under Skills, then call it again.")


def _program_ref(project_dir: Path, raw: str | None) -> str:
    """A program reference as `find_program` takes it: a name, or a path made project-relative when the model echoed
    a full path inside the project."""
    return _ct()._tool_path(project_dir, (raw or "").strip())


def shown(path: Path, project_dir: Path) -> str:
    """How a program or an input is named in an answer: project-relative, `canon:<volume>/...` for the store, the
    file name for a shipped program; the full path only when it is none of those."""
    from . import canon
    from . import thym_host
    p = Path(path)
    for root, prefix in ((Path(project_dir), ""), (canon.root(), "canon:"), (thym_host.SHIPPED_PROGRAMS, "")):
        for r in {root, root.resolve()}:
            try:
                return prefix + p.relative_to(r).as_posix()
            except ValueError:
                continue
    return str(p)


def program_names(project_dir: Path) -> list[str]:
    """The names a bare program reference resolves to here, in `list_programs`' order, each once."""
    from . import thym_host
    out: list[str] = []
    for row in thym_host.list_programs(project_dir):
        if row.get("name") and row["name"] not in out:
            out.append(row["name"])
    return out


def _not_found(name: str, ref: str, project_dir: Path) -> Any:
    names = program_names(project_dir)
    listed = ", ".join(names[:PROGRAMS_SHOWN]) + (f" ({len(names) - PROGRAMS_SHOWN} more)"
                                                   if len(names) > PROGRAMS_SHOWN else "")
    tail = (f"the programs here: {listed}" if names else "there are no programs here")
    return _err(name, ref, f"no program {ref!r}: give a program's name or the path of a .thym file; {tail}.")


def _named(r: Any, label: str) -> Any:
    """A refusal named after the file the readvisor knows (`orchard/x.thym`, not the full path)."""
    return dataclasses.replace(r, file=label)


def _checked(path: Path) -> Any:
    """Stages 1 to 4 of THYM.md 11.1, as `cli.cmd_check` runs them: a `Checked`, or the `Refusal`."""
    from .thym import check_file
    return check_file(path)


def _takes(checked: Any) -> list[tuple[str, str]]:
    progs = checked.programs()
    return [(p.name, p.type) for p in progs[0].takes] if progs else []


def _gives(checked: Any) -> tuple[str, str] | None:
    progs = checked.programs()
    g = progs[0].gives if progs else None
    return (g.name, g.type) if g is not None else None


def _plan_line(plan: dict) -> str:
    """The plan's one line exactly as `python -m enough.thym plan` prints it (THYM.md 11.3)."""
    from .thym.cli import plan_atem
    return plan_atem(plan)


def _inputs_lines(raw: str | None) -> list[tuple[str, str]] | str:
    """`<inputs>` as `name=path` lines (the command line's form); a problem as a string."""
    out: list[tuple[str, str]] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        name, eq, path = line.partition("=")
        if not eq or not name.strip() or not path.strip():
            return f"an <inputs> line is name=path, one per line, not {line!r}"
        out.append((name.strip(), path.strip()))
    return out


def _resolve_inputs(project_dir: Path, pairs: list[tuple[str, str]],
                    takes: list[tuple[str, str]]) -> tuple[list[dict], dict[str, str]] | str:
    """The plan's inputs `[{name, type, path, sha256}]` from `(name, path)` pairs, each path read by the routes' rule
    and recorded absolute (the plan's digest is over the file the run will read), with its type from the program's
    `takes` as `cli._inputs` does; also each input's name as the readvisor wrote it. A problem as a string."""
    from .thym.values import digest_path, guess_type
    ct = _ct()
    types = dict(takes)
    rows: list[dict] = []
    labels: dict[str, str] = {}
    seen: dict[str, str] = {}
    for name, raw in pairs:
        rel = ct.tidy_rel(ct._tool_path(project_dir, raw))
        if name in seen and seen[name] != rel:
            return f"{name} is given twice ({seen[name]} and {rel}); give each input once"
        if name in seen:
            continue
        seen[name] = rel
        if not rel or rel in ct.STORE_PREFIXES:
            return f"the input {name} has no path"
        try:
            target = ct.resolve(project_dir, rel)
        except ct.TextTargetError:
            return (f"invalid path {raw!r} for {name}: give a project-relative path, or canon:<volume>/<path> for "
                    "the Canon store")
        if not target.exists():
            return f"no such file: {rel} (the input {name})"
        try:
            sha = digest_path(target) or ""
        except OSError as e:
            return f"{rel} could not be read ({e.strerror or e})"
        rows.append({"name": name, "type": types.get(name) or guess_type(target), "path": str(target),
                     "sha256": sha})
        labels[name] = rel
    return rows, labels


def _placeholders(takes: list[tuple[str, str]]) -> list[dict]:
    """Inputs that stand for the program's `takes` when none are given: the plan's shape (nodes, asks, output budget)
    is the same, and its largest prompt, which is counted from the inputs' sizes, reads 0."""
    return [{"name": n, "type": t, "path": n, "sha256": "", "size": 0} for n, t in takes]


def _asks_refusal(plan: dict, why: str, check: str) -> Any:
    """The plan-time refusal of THYM.md 19, in the runtime's words (`run._environment`): the count of the steps that
    ask a model and the first one's line."""
    from .thym import Refusal
    asks = [n for n in plan.get("nodes") or [] if isinstance(n, dict) and n.get("type") == "node"
            and n.get("asks") is True]
    if not asks:
        return None
    k = len(asks)
    many = f"{k} step{'s' if k != 1 else ''} ask{'' if k != 1 else 's'} a model"
    return Refusal("plan", check, f"{many}; {why}", line=asks[0].get("line"))


def _then(said: str, more: str) -> str:
    """Two sentences of an answer, with the stop between them the first one may lack."""
    said = said.rstrip()
    return f"{said}{'' if said.endswith(('.', '!', '?')) else '.'} {more}"


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# thym_check
# ---------------------------------------------------------------------------

def run_thym_check(project_dir: Path, call: Any) -> Any:
    """`thym_check <path>` — compile a Thym program and plan it: "ok" and the plan's one line, as `python -m
    enough.thym check` and `plan` print them, or the refusal with its file, line and check. Read-only; allowed in
    every mode, agent-free included. `<inputs>` lines (`name=path`) plan it on real files, so the largest prompt is
    measured; without them the program's `takes` stand in and the line says the prompt was not measured."""
    extra = getattr(call, "extra", None) or {}
    ref = _program_ref(project_dir, call.path or extra.get("program"))
    if not skill_on(project_dir):
        return _skill_off("thym_check", ref)
    if not ref:
        return _err("thym_check", "", "thym_check needs a <path>: a .thym file (or a program's name).")
    from . import thym_host
    from .thym import Refusal
    from .thym import plan as _plan
    path = thym_host.find_program(ref, project_dir)
    if path is None:
        return _not_found("thym_check", ref, project_dir)
    label = shown(path, project_dir)
    try:
        checked = _checked(path)
    except Exception as e:  # noqa: BLE001 — a compiler fault is said in words, never as a trace
        log.exception("thym_check failed")
        return _err("thym_check", ref, f"{label} could not be checked ({type(e).__name__}).")
    if isinstance(checked, Refusal):
        return _result("thym_check", ref, True, str(_named(checked, label)))
    takes, gives = _takes(checked), _gives(checked)
    pairs = _inputs_lines(extra.get("inputs"))
    if isinstance(pairs, str):
        return _err("thym_check", ref, pairs)
    if pairs:
        got = _resolve_inputs(project_dir, pairs, takes)
        if isinstance(got, str):
            return _err("thym_check", ref, got)
        inputs, measured = got[0], True
    else:
        inputs, measured = _placeholders(takes), False
    lines = ["ok"]
    try:
        plan = _plan.plan(checked, inputs)
    except Exception as e:  # noqa: BLE001
        log.exception("thym_check: the plan failed")
        return _err("thym_check", ref, f"{label} compiles, and its plan could not be made ({type(e).__name__}).")
    if isinstance(plan, Refusal):
        lines.append(str(_named(plan, label)))
    else:
        lines.append(_plan_line(plan))
    sig = ", ".join(f"{n}: {t}" for n, t in takes) or "nothing"
    lines.append(f"takes {sig}" + (f"; gives {gives[0]}: {gives[1]}" if gives else ""))
    if not measured and not isinstance(plan, Refusal) and (plan.get("estimate") or {}).get("asks"):
        lines.append("planned without inputs, so the largest prompt is not measured: add <inputs> lines "
                     "(name=path) to measure it on files")
    return _result("thym_check", ref, True, "\n".join(lines))


# ---------------------------------------------------------------------------
# thym_run
# ---------------------------------------------------------------------------

def _text_too_long(plan: dict, labels: dict[str, str]) -> str | None:
    """A plan that asks a model, over a text longer than a chat turn should wait for: the MacroCOSM tools' limit
    (`canon_tools.TEXT_MAX`), with the reader's words for where such a run belongs."""
    ct = _ct()
    for row in plan.get("inputs") or []:
        p = Path(str(row.get("path") or ""))
        if row.get("type") in ("text", "short") and p.is_file():
            try:
                n = len(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if n > ct.TEXT_MAX:
                rel = labels.get(str(row.get("name")), p.name)
                return (f"{rel} is {n:,} characters, over {ct.TEXT_MAX:,} for a model run inside a chat turn: a run "
                        "on a text this long belongs in the reader's run-with, which runs in the background")
    return None


def _snapshot(t: Any, *, path: str, mode: str, started: str, labels: dict[str, str]) -> dict:
    """The run as a finished job of kind `thym` in `canon_jobs`' shape (the `canon` event), naming the run id and
    the trace path; a refused run is `failed`, with the refusal as its error."""
    ct = _ct()
    result = {"run": t.run_id, "trace": str(t.path), "program": t.program.get("name"), "outcome": t.outcome,
              "outputs": {k: str(v) for k, v in (t.outputs or {}).items()}, "inputs": dict(labels),
              "text_path": path}
    snap = ct.snapshot(kind=JOB_KIND, path=path, mode=mode, result=result, message=t.atem(), started=started,
                       by=ct.readvisor_name())
    if not t.landed:
        snap["state"], snap["phase"] = "failed", "failed"
        snap["error"] = str(t.refusal) if t.refusal is not None else t.atem()
    return snap


def run_thym_run(project_dir: Path, call: Any) -> Any:
    """`thym_run <program> <path> [<inputs>]` — run a Thym program on a file, as `python -m enough.thym run` does:
    check, plan, preflight, run (THYM.md 11.3, 12.1). `<program>` is a name or a `.thym` path (`find_program`);
    `<path>` is the program's first input; further inputs are `<inputs>` lines, `name=path`. The run lands under the
    Thym root only, and the answer is the trace's atem, the outputs' paths and the trace's path.

    Refused at plan time, nothing run: a plan whose steps ask a model while agent-free is on or while no model
    answers (with the count); a prompt the model's window cannot hold (preflight, with the number); an asking plan
    over a text longer than a chat turn should wait for. Refused before anything: the skill off, an unknown program
    (with the names there are), a missing input."""
    extra = getattr(call, "extra", None) or {}
    ref = _program_ref(project_dir, extra.get("program"))
    if not skill_on(project_dir):
        return _skill_off("thym_run", ref)
    if not ref:
        return _err("thym_run", "", "thym_run needs a <program>: a name (publish-story) or a .thym path; the "
                                    "first input goes in <path>.")
    from . import agent_free as _agent_free
    from . import thym_host
    from .thym import Refusal
    from .thym import plan as _plan
    from .thym import run as _run
    path = thym_host.find_program(ref, project_dir)
    if path is None:
        return _not_found("thym_run", ref, project_dir)
    label = shown(path, project_dir)
    try:
        checked = _checked(path)
    except Exception as e:  # noqa: BLE001
        log.exception("thym_run: the check failed")
        return _err("thym_run", ref, f"{label} could not be checked ({type(e).__name__}).")
    if isinstance(checked, Refusal):
        return _err("thym_run", ref, str(_named(checked, label)))
    takes = _takes(checked)
    first_path = (call.path or "").strip()
    if first_path and not takes:
        return _err("thym_run", ref, f"{label} takes no input; call it without a <path>.")
    lines = _inputs_lines(extra.get("inputs"))
    if isinstance(lines, str):
        return _err("thym_run", ref, lines)
    pairs = ([(takes[0][0], first_path)] if first_path else []) + lines
    got = _resolve_inputs(project_dir, pairs, takes)
    if isinstance(got, str):
        return _err("thym_run", ref, got)
    inputs, labels = got
    try:
        plan = _plan.plan(checked, inputs)
    except Exception as e:  # noqa: BLE001
        log.exception("thym_run: the plan failed")
        return _err("thym_run", ref, f"{label} compiles, and its plan could not be made ({type(e).__name__}).")
    if isinstance(plan, Refusal):
        said = str(_named(plan, label))
        if plan.check == "input":
            said = _then(said, "The first input goes in <path>, further ones in <inputs> lines (name=path).")
        return _err("thym_run", ref, said)

    # The environment (THYM.md 12.1, 19): agent-free first, then whether a model answers.
    ct = _ct()
    agent_free = _agent_free.enabled()
    complete = None
    if agent_free:
        no = _asks_refusal(plan, "agent-free is on", "agent-free")
        if no is not None:
            return _err("thym_run", ref, _then(str(_named(no, label)), "Turn agent-free off in ui preferences to "
                                                                       "run it, or run a program that asks no model."))
    else:
        complete, _why = ct.model()
        if complete is None:
            no = _asks_refusal(plan, "no model is running", "rules")
            if no is not None:
                return _err("thym_run", ref, _then(str(_named(no, label)), "Start the model to run it, or run a "
                                                                           "program that asks no model."))
    asks = bool((plan.get("estimate") or {}).get("asks"))
    if asks:
        long = _text_too_long(plan, labels)
        if long:
            return _err("thym_run", ref, long + ".")

    kw = thym_host.runtime_kwargs(rules=complete is None, complete=complete, llm_url=ct._llm_url,
                                  catalog=thym_host.catalog_engine(project_dir))   # `context of` reads it (16.1)
    root = kw.pop("root", None) or thym_host.host_root()
    started = _stamp()
    try:
        t = _run.run(plan, inputs_root=project_dir, root=root, rules=False, program=path, **kw)
    except Exception as e:  # noqa: BLE001 — a move that raises is said in words; nothing landed
        log.exception("thym_run: the run failed")
        return _err("thym_run", ref, f"the run of {label} stopped ({type(e).__name__}: {e}); nothing landed.")
    if isinstance(t, Refusal):
        return _err("thym_run", ref, str(_named(t, label)) if not t.file else str(t))
    first = labels.get(takes[0][0], "") if takes else ""
    mode = "model" if t.engine() not in ("code", "rules") else "rules"
    effects = {ct.SIDE_EFFECT: _snapshot(t, path=first, mode=mode, started=started, labels=labels)}
    if not t.landed:
        why = str(_named(t.refusal, label)) if t.refusal is not None and not t.refusal.file else str(t.refusal or "")
        body = "\n".join(x for x in (t.atem(), why, f"trace: {t.path}", "nothing landed") if x)
        return _result("thym_run", ref, False, "error: " + body, effects)
    out = [t.atem()]
    out += [f"{name}: {p}" for name, p in t.outputs.items()]
    out += [f"trace: {t.path}", OUTPUTS_NOTE]
    return _result("thym_run", ref, True, "\n".join(out), effects)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {
    "thym_check": run_thym_check,
    "thym_run": run_thym_run,
}


def register() -> None:
    """Add the two tools to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent, called once at `tools` import time;
    traced under the universal toggle, like the MacroCOSM tools beside them."""
    from . import tools as _t
    for tool_name, runner in _RUNNERS.items():
        _t._DISPATCH.setdefault(tool_name, runner)
        _t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["JOB_KIND", "OUTPUTS_NOTE", "PROGRAMS_SHOWN", "SKILL_NAME", "TOOL_NAMES", "program_names", "register",
           "run_thym_check", "run_thym_run", "shown", "skill_on"]
