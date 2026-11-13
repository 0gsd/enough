"""The readvisor's Thym tools: `thym_check`, `thym_run` (0.5.0, wave 2, R1; docs/THYM.md 11.3, 12.1, 12.5, 19) and
`thym_moves` (0.6: the moves a program of a version may use, so an agent writes one without guessing).

**Models in a run** (THYM.md 23). `thym_check` and `thym_run` take `<model>`: `local` (the default: this machine's
model, whatever slot the chat is on), `cloud` (the cloud model the broker names) or `cloud:<model id>`, and
`thym_run` takes `<calls>`, a ceiling on the run's model requests. The check answers the plan's `models` line as the
command line prints it; the run refuses a shut gate in the gate's words, a cloud plan whose count is open without
`<calls>`, and agent-free on both routes, before anything is asked. A cloud run takes no lock either way.

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

TOOL_NAMES: tuple[str, ...] = ("thym_check", "thym_run", "thym_moves")

#: How a tool call gives a run's ceiling, in the refusal that asks for one.
CEILING = "<calls>"

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


def _gives(checked: Any) -> list[tuple[str, str]]:
    """Every output the program gives, `(name, type)`, in its `gives` order (several in `thym 1`)."""
    progs = checked.programs()
    if not progs:
        return []
    outs = list(getattr(progs[0], "outputs", None) or ([progs[0].gives] if progs[0].gives else []))
    return [(g.name, g.type) for g in outs]


def _plan_line(plan: dict) -> str:
    """The plan's lines exactly as `python -m enough.thym plan` prints them (THYM.md 11.3, 23.2): its atem, and its
    `models` line when it asks a model."""
    from .thym.cli import models_line, plan_atem
    line = models_line(plan)
    return plan_atem(plan) + (f"\n{line}" if line else "")


def _route(extra: dict) -> tuple[str, str | None, int | None] | str:
    """`(route, model, calls)` from `<model>` and `<calls>`; a problem as a string."""
    from .thym.cli import parse_model
    from .thym import Refusal
    got = parse_model(extra.get("model") or "local")
    if isinstance(got, Refusal):
        return "<model> is local, cloud or cloud:<model id>, not " + repr(extra.get("model"))
    raw = (extra.get("calls") or "").strip()
    calls = None
    if raw:
        if not raw.isdigit() or int(raw) < 1:
            return f"<calls> is a ceiling of at least 1 model call, not {raw!r}"
        calls = int(raw)
    return got[0], got[1], calls


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
    `takes` as `cli._inputs` does; also each input's name as the readvisor wrote it. An input whose type is a list is
    given by its name once per member, in order (`xs=a.md`, `xs=b.md`), each member held to what one input of the
    member type takes and named `xs[n]`; its row is the routes' (`{name, type, members: [{path, sha256}], path,
    sha256}`) and its label its members' paths joined by ", ". A problem as a string."""
    from .thym.values import digest_path, guess_type, list_digest, list_member_type, member_name
    ct = _ct()
    types = dict(takes)
    rows: list[dict] = []
    labels: dict[str, str] = {}
    seen: dict[str, str] = {}
    lists: dict[str, dict] = {}

    def one(name: str, raw: str, typ: str | None) -> tuple[str, Path, str, str] | str:
        rel = ct.tidy_rel(ct._tool_path(project_dir, raw))
        if not rel or rel in ct.STORE_PREFIXES:
            return f"the input {name} has no path"
        try:
            target = ct.resolve(project_dir, rel)
        except ct.TextTargetError:
            return (f"invalid path {raw!r} for {name}: give a project-relative path, or canon:<volume>/<path> for "
                    "the Canon store")
        if not target.exists():
            return f"no such file: {rel} (the input {name})"
        typ = typ or guess_type(target)
        if typ is not None:
            from . import thym_host
            problem = thym_host.check_input(target, typ, name=name, shown=rel) if name.split("[")[0] in types \
                else None
            if problem:
                return problem
        try:
            sha = digest_path(target, typ if typ == "folder" else None) or ""
        except OSError as e:
            return f"{rel} could not be read ({e.strerror or e})"
        return rel, target, typ, sha

    for name, raw in pairs:
        typ = types.get(name)
        if isinstance(typ, str) and (typ == "list" or typ.startswith("list of ")):
            row = lists.get(name)
            if row is None:
                row = lists[name] = {"name": name, "type": typ, "path": "", "sha256": "", "members": []}
                rows.append(row)
            n = len(row["members"]) + 1
            got = one(member_name(name, n), raw, list_member_type(typ) or None)
            if isinstance(got, str):
                return got
            rel, target, _, sha = got
            row["members"].append({"path": str(target), "sha256": sha})
            row["path"] = row["members"][0]["path"]
            row["sha256"] = list_digest([m["sha256"] for m in row["members"]])
            labels[name] = f"{labels[name]}, {rel}" if name in labels else rel
            continue
        rel = ct.tidy_rel(ct._tool_path(project_dir, raw))
        if name in seen and seen[name] != rel:
            return f"{name} is given twice ({seen[name]} and {rel}); give each input once"
        if name in seen:
            continue
        seen[name] = rel
        got = one(name, raw, typ)
        if isinstance(got, str):
            return got
        rel, target, typ, sha = got
        rows.append({"name": name, "type": typ, "path": str(target), "sha256": sha})
        labels[name] = rel
    return rows, labels


def _placeholders(takes: list[tuple[str, str]]) -> list[dict]:
    """Inputs that stand for the program's `takes` when none are given: the plan's shape (nodes, asks, output budget)
    is the same, and its largest prompt, which is counted from the inputs' sizes, reads 0."""
    return [{"name": n, "type": t, "path": n, "sha256": "", "size": 0} for n, t in takes]


def _asks_refusal(plan: dict, why: str, check: str, *, route: str = "local", program: Any = None) -> Any:
    """The plan-time refusal of THYM.md 19, in the text's words (`thym_host.asks_said`): how many steps ask a model on
    which route, and the first one's statement and line."""
    from . import thym_host
    from .thym import Refusal
    said = thym_host.asks_said(plan, route=route, program=program)
    if said is None:
        return None
    many, line = said
    return Refusal("plan", check, f"{many}; {why}", line=line)


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
    path = thym_host.find_program(ref, project_dir)
    if path is None:
        return _not_found("thym_check", ref, project_dir)
    label = shown(path, project_dir)
    try:
        checked = _checked(path)
    except Exception as e:  # noqa: BLE001 — a compiler fault is said in words, never as a trace
        log.exception("thym_check failed")
        return _err("thym_check", ref, f"{label} could not be checked ({type(e).__name__}).")
    if isinstance(checked, Refusal):                 # every fault the checker found, one line each, first first
        return _result("thym_check", ref, True, "\n".join(str(_named(r, label)) for r in checked.all()))
    takes, gives = _takes(checked), _gives(checked)
    route = _route(extra)
    if isinstance(route, str):
        return _err("thym_check", ref, route)
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
        plan, info = thym_host.plan_for(checked, inputs, route=route[0], model=route[1], llm_url=_ct()._llm_url)
    except Exception as e:  # noqa: BLE001
        log.exception("thym_check: the plan failed")
        return _err("thym_check", ref, f"{label} compiles, and its plan could not be made ({type(e).__name__}).")
    if isinstance(plan, Refusal):
        lines.append(str(_named(plan, label)))
    else:
        lines.append(_plan_line(plan))
        said = thym_host.route_refusal(plan, info, calls=route[2], ceiling=CEILING, program=path)
        if said is not None:
            lines.append(str(_named(said, label)))
    sig = ", ".join(f"{n}: {t}" for n, t in takes) or "nothing"
    lines.append(f"takes {sig}" + (f"; gives {', '.join(f'{n}: {t}' for n, t in gives)}" if gives else ""))
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
    `<path>` is the program's first input; further inputs are `<inputs>` lines, `name=path`, a list input's name once
    per member, in order (`<path>` its first member). The run lands under the
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
    route = _route(extra)
    if isinstance(route, str):
        return _err("thym_run", ref, route)
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

    # The environment (THYM.md 12.1, 19, 23): agent-free first (both routes, before any broker is asked), then
    # whether a model answers on the run's route.
    ct = _ct()
    agent_free = _agent_free.enabled()
    on, model_id, calls = route
    complete = None
    if agent_free:
        no = _asks_refusal(plan, "agent-free is on", "agent-free", route=on, program=path)
        if no is not None:
            return _err("thym_run", ref, _then(str(_named(no, label)), "Turn agent-free off in ui preferences to "
                                                                       "run it, or run a program that asks no model."))
    elif on == "cloud":
        if thym_host.plan_asks(plan):
            complete = thym_host.route_complete("cloud", model=model_id, llm_url=ct._llm_url, project_dir=project_dir)
    else:
        complete, _why = ct.model("local")
        if complete is None:
            no = _asks_refusal(plan, "no model is running", "rules", route=on, program=path)
            if no is not None:
                return _err("thym_run", ref, _then(str(_named(no, label)), "Start the model to run it, or run a "
                                                                           "program that asks no model."))
    info = None
    if complete is not None and thym_host.plan_asks(plan):
        plan, info = thym_host.plan_for(checked, inputs, route=on, model=model_id, llm_url=ct._llm_url)
        if isinstance(plan, Refusal):
            return _err("thym_run", ref, str(_named(plan, label)))
        no = thym_host.route_refusal(plan, info, calls=calls, ceiling=CEILING, program=path)
        if no is not None:
            return _err("thym_run", ref, str(_named(no, label)))
    asks = bool((plan.get("estimate") or {}).get("asks"))
    if asks:
        long = _text_too_long(plan, labels)
        if long:
            return _err("thym_run", ref, long + ".")

    kw = thym_host.runtime_kwargs(rules=complete is None, complete=complete, llm_url=ct._llm_url,
                                  catalog=thym_host.catalog_engine(project_dir),   # `context of` reads it (16.1)
                                  route=on, model=model_id, calls=calls, project_dir=project_dir, info=info,
                                  ceiling=CEILING, program=path)
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
    from .thym.cli import _output_lines
    out = [t.atem()]
    out += _output_lines(t)                        # every output as it landed, a folder output as a directory
    out += [f"trace: {t.path}", OUTPUTS_NOTE]
    return _result("thym_run", ref, True, "\n".join(out), effects)


# ---------------------------------------------------------------------------
# thym_moves
# ---------------------------------------------------------------------------

def _alts(alts: Any) -> str:
    return " | ".join(str(a) for a in alts) if isinstance(alts, (list, tuple)) else str(alts)


def move_signature(d: Any) -> str:
    """A declared move as a program calls it: `tell <fabula | item | volume> [as <order>] [by <order>] [with
    <morph>]`, then what it gives; a move whose argument is its `of` reads `context of <text | package>`."""
    mods = dict(getattr(d, "modifiers", None) or {})
    parts = [d.name]
    if "of" in mods and not d.takes:
        parts.append(f"of <{_alts(mods.pop('of'))}>")
    parts += [f"<{_alts(t)}>" for t in d.takes]
    parts += [f"[{w} <{_alts(a)}>]" for w, a in mods.items()]
    gives = _alts(d.gives)
    if gives in ("same-as-with", "same-as-in"):
        gives = f"what its {gives.rsplit('-', 1)[1]} is"
    out = " ".join(parts) + f" gives {gives}"
    whens = [(on, what, val) for on, what, val in getattr(d, "gives_when", ()) or ()]
    if whens:
        said = "; ".join(f"{'as' if on == 'as' else 'of'} {_alts(what)}: {_alts(val)}" for on, what, val in whens)
        out += f" ({said})"
    return out


def move_line(d: Any) -> str:
    """One move, as `thym_moves` lists it: its signature; whether it asks a model (and its scaffold); its contract;
    its `says` line."""
    asks = "asks a model" + (f", scaffold {d.scaffold}" if d.scaffold else ", no scaffold") if d.asks \
        else "asks nothing"
    contract = f"; contract {', '.join(d.contract)}" if d.contract else ""
    says = " ".join(str(d.says or "").split())
    return f"- {move_signature(d)}; {asks}{contract}" + (f". {says}" if says else "")


#: The owners in the order THYM 6.2 lists them; an owner it does not list comes after, in the registry's order.
OWNERS_ORDER = ("thym", "fabula", "doc", "comprise", "ascribe")


def listed_moves(version: int) -> list[Any]:
    """Every move a program of grammar `version` (0 or 1) may call, as the compiler sees it (`declarations.load()`,
    the registry the compile reads, in its view for `version`: a move another format `extends` carries the kinds it
    added), in the text's order: by owner as THYM 6.2 lists them, each owner's moves in its manifest's order. The one
    listing `thym_moves` and `GET /api/thym/moves` read. Raises what the declarations raise."""
    from .thym import declarations as _decls
    seen = _decls.load().view(version)
    owners = list(dict.fromkeys(d.owner for d in seen.values()))
    rank = {o: i for i, o in enumerate(list(OWNERS_ORDER) + [o for o in owners if o not in OWNERS_ORDER])}
    return sorted(seen.values(), key=lambda d: rank[d.owner])             # stable: each owner's manifest order kept


def _format_of(owner: str) -> str:
    """`<owner>/<major>`: the major the owner's manifest says (`version:`), 1 when no manifest says."""
    try:
        from . import macrocosm as _mc
        m = _mc.default_registry().manifests.get(owner)
        v = (m.data or {}).get("version") if m is not None else None
    except Exception:  # noqa: BLE001 - a registry that cannot be read names the first major
        v = None
    return f"{owner}/{v if isinstance(v, int) and not isinstance(v, bool) else 1}"


def move_row(d: Any, *, versions: list[int]) -> dict:
    """One move as `GET /api/thym/moves` answers it (docs/fabula-landed-S4.md 1): its owner and format, the manifest
    file that declared it, `since`, the grammars that see it, its signature (`move_signature`), `takes` (each
    operand's alternatives), `of` (the alternatives of a move whose argument is its `of`, else None), the other
    modifiers, what it gives, whether it asks a model, its scaffold, its contract, its `says` line, and `extended`:
    the kinds other owners add to it (`[{owner, as: [...]}]`, THYM 6.2), seen in this view."""
    mods = {k: list(v) for k, v in dict(d.modifiers or {}).items()}
    of = mods.pop("of", None) if not d.takes else None
    return {"name": d.name, "owner": d.owner, "format": _format_of(d.owner),
            "source": Path(d.source).name if d.source else None, "since": d.since, "versions": versions,
            "signature": move_signature(d), "takes": [list(t) for t in d.takes], "of": of, "modifiers": mods,
            "gives": list(d.gives), "asks": bool(d.asks), "scaffold": d.scaffold, "contract": list(d.contract),
            "says": " ".join(str(d.says or "").split()),
            "extended": [{"owner": owner, "as": list(words)} for words, _code, owner in (d.code_when or ())]}


def moves_payload(version: int) -> dict:
    """`GET /api/thym/moves?version=`: `{version, moves: [move_row, ...]}` from `listed_moves`. ValueError for a
    version that is not 0 or 1."""
    if version not in (0, 1) or isinstance(version, bool):
        raise ValueError(f"version is 0 or 1 (the grammar's `thym <n>` line), not {version!r}")
    names = {v: {d.name for d in listed_moves(v)} for v in (0, 1)}
    return {"version": version,
            "moves": [move_row(d, versions=[v for v in (0, 1) if d.name in names[v]]) for d in listed_moves(version)]}


def run_thym_moves(project_dir: Path, call: Any) -> Any:
    """`thym_moves [<version>] [<move>]` — the moves a program of grammar `version` (1, the default, or 0) may use,
    each with its signature, whether it asks a model, its contract and its `says` line (THYM.md 6.3, 17.6), read from
    the declarations a compile reads; `<move>` shows only that one. Read-only; allowed in every mode."""
    extra = getattr(call, "extra", None) or {}
    raw = (extra.get("version") or call.path or "1").strip().removeprefix("thym").strip()
    key = f"thym {raw}"
    if not skill_on(project_dir):
        return _skill_off("thym_moves", key)
    if raw not in ("0", "1"):
        return _err("thym_moves", key, f"<version> is 0 or 1 (the grammar's `thym <n>` line), not {raw!r}.")
    version = int(raw)
    try:
        listed = listed_moves(version)                  # the one listing GET /api/thym/moves reads too
    except Exception as e:  # noqa: BLE001 — a manifest that does not read is said in words
        log.exception("thym_moves: the declarations failed")
        return _err("thym_moves", key, f"the moves could not be read ({type(e).__name__}).")
    seen = {d.name: d for d in listed}
    only = (extra.get("move") or "").strip()
    if only:
        if only not in seen:
            near = ", ".join(sorted(seen)[:PROGRAMS_SHOWN * 4])
            return _err("thym_moves", key, f"a thym {version} program has no move {only!r}; it has: {near}.")
        return _result("thym_moves", key, True, move_line(seen[only]))
    lines = [f"the moves a thym {version} program may use ({len(seen)}); a user move or a contract block may be "
             "written beside them:"]
    lines += [move_line(d) for d in listed]
    return _result("thym_moves", key, True, "\n".join(lines))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_RUNNERS = {
    "thym_check": run_thym_check,
    "thym_run": run_thym_run,
    "thym_moves": run_thym_moves,
}


def documented(tool_name: str) -> bool:
    """Is the tool named in the MacroCOSM block the model reads? A dispatchable tool no prompt names can never be
    called (`tests/test_prompt_weight.py`'s guard), so `thym_moves` joins the dispatch table once the block (prompt.py,
    capped at 1,000 characters, not this module's) names it: docs/fabula-landed-T1-models.md section C has the
    wording that fits."""
    from . import prompt
    return tool_name in prompt.CANON_TOOL_INSTRUCTIONS


def register() -> None:
    """Add the tools to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent, called once at `tools` import time;
    traced under the universal toggle, like the MacroCOSM tools beside them. `thym_moves` waits until the block names
    it (`documented`); its runner works now (`run_thym_moves`)."""
    from . import tools as _t
    for tool_name, runner in _RUNNERS.items():
        if tool_name == "thym_moves" and not documented(tool_name):
            continue
        _t._DISPATCH.setdefault(tool_name, runner)
        _t._TRACE_TOGGLE.setdefault(tool_name, "trace_log_enabled")


__all__ = ["CEILING", "JOB_KIND", "OUTPUTS_NOTE", "PROGRAMS_SHOWN", "SKILL_NAME", "TOOL_NAMES", "listed_moves",
           "move_line", "move_row", "move_signature", "moves_payload", "program_names", "register", "run_thym_check", "run_thym_moves", "run_thym_run", "shown",
           "skill_on"]
