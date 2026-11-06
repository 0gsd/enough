"""The readvisor's fabula-round tools (0.6): `dialectic` and `fabulac`.

**`dialectic`** (pins P4.7): a readvisor puts one or two questions at a time to the person and records what they say.
Called with a `<path>` alone it shows the next one or two open questions of that volume (a text's fabula, a fabulac, a
holograph, any volume), each with what a person needs to answer it; called with `<question>` and `<says>` it records the
person's words, verbatim, as the page's card does (`dialectic_api.record`, `through: agent` with the model's id): for a
single-file volume an answers volume beside it, never the volume itself; for a holograph into the holograph, by
Ascribe's rules (the holder alone answers; words that read like personal data are refused, and nothing of them is
written). `<state>` says "I don't know" (`unknown`), a refusal to say (`declined`) or a skip (`skip`). `<do>settle</do>`
folds the sittings in (a job, as the page's settle), `<do>raise</do>` raises the format's bank on a volume with no
questions yet.

**`fabulac`**: a folder of Python decompiled into its fabulac (`<do>build</do>`, which also takes a stopped build up
again), how it stands (`status`, the default), compiled (`compile`, `<what>` code or a catem's depth) or cancelled.
A build and a compile run as jobs, the same jobs the page starts (`fabulac_job`): started from the chat turn's worker
thread, they wait for the model the turn holds (local) and run when the turn ends. `<model>cloud` asks the cloud, only
when the person chose it for this job and the gate is open. Nothing told is ever run.

Registered into `tools._DISPATCH` the way `canon_tools` is, documented in `prompt.FABULA_TOOL_INSTRUCTIONS`, beside the
MacroCOSM block in both profiles while the `macrocosm-oes` skill is on (their guide, as for Thym's tools: with it off a
runner says how to switch it on and runs nothing, and a fresh project's prompt pays nothing for them).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("enough.fabula_tools")

TOOL_NAMES: tuple[str, ...] = ("dialectic", "fabulac")
#: Questions shown at a time: one or two (P4.7, Ascribe 8.2).
SHOWN = 2
STATES = {"unknown": "dont_know", "dont-know": "dont_know", "i don't know": "dont_know", "declined": "declined",
          "decline": "declined", "skip": "skip", "skipped": "skip", "answered": None, "": None}

# The seams (`configure`), as `canon_tools`' are: what create_app hands the tools to start a job with.
_conf: dict[str, Any] = {}


def configure(*, project_dir: Path | None = None, start: Callable | None = None, build: Callable | None = None,
              compile: Callable | None = None, settle: Callable | None = None, jobs: Any = None,
              emit: Callable | None = None) -> None:
    """Hand the tools the app's job starters and its event sender (`emit(event, data)`, for the `dialectic` event a
    recorded sitting sends); `configure()` with nothing resets them: tests."""
    _conf.clear()
    _conf.update({k: v for k, v in {"project_dir": project_dir, "start": start, "build": build, "compile": compile,
                                     "settle": settle, "jobs": jobs, "emit": emit}.items() if v is not None})


def _ct():
    from . import canon_tools
    return canon_tools


def _result(name: str, key: str, ok: bool, body: str, side: dict | None = None) -> Any:
    return _ct()._result(name, key, ok, body, side)


def _err(name: str, key: str, message: str) -> Any:
    return _ct()._err(name, key, message)


def _skill_on(project_dir: Path) -> bool:
    from . import thym_tools
    return thym_tools.skill_on(project_dir)


def _skill_off(name: str, key: str) -> Any:
    from . import thym_tools
    return thym_tools._skill_off(name, key)


def _model_id() -> str | None:
    from . import thym_host
    try:
        return thym_host.local_model_id(_ct()._llm_url) or thym_host.current_model()
    except Exception:  # noqa: BLE001
        return None


def _start(kind: str, body: dict) -> dict | str:
    """A job started through the app (`build`, `compile`, `settle`), or the words that say why not."""
    starter, fn = _conf.get("start"), _conf.get(kind)
    if starter is None or fn is None:
        return "this runs as a job in the reader, and no reader is running here; ask the person to start it there"
    try:
        return starter(lambda: fn(body))
    except Exception as e:  # noqa: BLE001 - an HTTPException carries the route's words
        detail = getattr(e, "detail", None)
        return str(detail or e)


def _job_line(snap: dict) -> str:
    job = snap.get("job") if isinstance(snap.get("job"), dict) else snap
    return f"job {job.get('id')}: {job.get('message') or job.get('state')} ({job.get('state')})"


# ---------------------------------------------------------------------------
# dialectic
# ---------------------------------------------------------------------------

def _card_lines(c: dict) -> list[str]:
    head = c.get("id") or c.get("about")
    shape = c.get("kind") or "text"
    if c.get("options"):
        shape += ": " + " | ".join(str(o) for o in c["options"]) + (" (or another word)" if c.get("options_open")
                                                                     else "")
    lines = [f"- {head} (to {c.get('to') or 'anyone'}; {shape})", f"  asks: {c.get('asks')}"]
    item = c.get("item") or {}
    if item.get("name") or item.get("summary"):
        lines.append(f"  about: {item.get('id')}: {item.get('name') or item.get('summary')}")
    if c.get("hint"):
        lines.append(f"  hint: {c['hint']}")
    return lines


def run_dialectic(project_dir: Path, call: Any) -> Any:
    from . import dialectic_api as D
    extra = getattr(call, "extra", None) or {}
    raw = _ct()._tool_path(project_dir, call.path)
    if not _skill_on(project_dir):
        return _skill_off("dialectic", raw)
    if not raw:
        return _err("dialectic", "", "dialectic needs a <path>: a text, its fabula, a fabulac or a holograph.")
    do = (extra.get("do") or "").strip().lower()
    try:
        if do == "settle":
            got = _start("settle", {"path": raw, **({"route": extra["model"]} if extra.get("model") else {})})
            if isinstance(got, str):
                return _err("dialectic", raw, got)
            return _result("dialectic", raw, True, _job_line(got))
        if do == "raise":
            out = D.raise_bank(project_dir, raw)
            return _result("dialectic", raw, True, f"raised {out['count']} question{'s' if out['count'] != 1 else ''} "
                                                   f"in {out['path']}; call dialectic again to see the first.")
        if do not in ("", "ask", "record", "answer"):
            return _err("dialectic", raw, f"<do> is settle or raise, or left out; not {do!r}")
        q = (extra.get("question") or "").strip()
        if q:
            return _record(project_dir, raw, q, extra)
        listed = D.listing(project_dir, raw)
    except D.DialecticRouteError as e:
        return _err("dialectic", raw, str(e))
    opened = listed["open"]
    if not opened:
        more = (f"; {len(listed['waiting'])} answered, waiting to be settled (<do>settle</do>)"
                if listed["waiting"] else "")
        none = "no open question" if listed["counts"].get("open", 0) or listed["sessions"] or listed["waiting"] \
            else "no questions yet (<do>raise</do> asks the format's bank)"
        return _result("dialectic", raw, True, f"{listed['path']}: {none}{more}.")
    lines = [f"{listed['path']}: {len(opened)} open; put these to the person, one at a time, in your own words:"]
    for c in opened[:SHOWN]:
        lines += _card_lines(c)
    lines.append("Record each with <question> and <says> (their words, verbatim), or <state> unknown, declined or "
                 "skip. Never answer for them.")
    if listed["holograph"]:
        lines.append("A holograph: only its holder answers, and nothing that reads like personal data is kept.")
    return _result("dialectic", raw, True, "\n".join(lines))


def _record(project_dir: Path, raw: str, q: str, extra: dict) -> Any:
    from . import dialectic_api as D
    state = (extra.get("state") or "").strip().lower()
    if state not in STATES:
        return _err("dialectic", raw, f"<state> is unknown, declined or skip (or left out for an answer), not "
                                      f"{state!r}")
    says = extra.get("says") or ""
    flag = STATES[state]
    if flag is None and not says.strip():
        return _err("dialectic", raw, "an answer needs <says>: the person's words, as they said them")
    a: dict[str, Any] = {"question": q, "says": says}
    if flag:
        a[flag] = True
    try:
        out = D.record(project_dir, raw, [a], through="agent", model=_model_id())
    except D.DialecticRouteError as e:
        return _err("dialectic", raw, str(e))
    if out.get("recorded") or out.get("skipped"):
        D.notify(_conf.get("emit"), out.get("path") or raw, out.get("session"), "recorded")
    if out["refused"]:
        return _err("dialectic", raw, "; ".join(f"{r['question']}: {r['why']}" for r in out["refused"]))
    done = ", ".join(f"{r['question']} {r['state']}" for r in out["recorded"]) or \
        ", ".join(f"{s} skipped" for s in out["skipped"])
    where = out.get("written") or out.get("path")
    return _result("dialectic", raw, True, f"recorded in {where}: {done}. It is settled into the volume when "
                                           "someone settles (<do>settle</do>).")


# ---------------------------------------------------------------------------
# fabulac
# ---------------------------------------------------------------------------

def _state_lines(state: dict) -> list[str]:
    from . import fabulac_job as F
    if not state.get("exists"):
        return [f"{state['folder']}/ has no fabulac yet."]
    landed = [s["stage"] for s in state["stages"] if s["landed"]]
    lines = [f"{state['fabulac']}: {', '.join(landed) or 'nothing'} landed"
             + ("; every stage" if state["complete"] else f"; next {F.STAGE_WORDS.get(state['next'], state['next'])}")]
    if state.get("moved"):
        lines.append("the folder changed since the survey: a build starts again from the survey")
    return lines


def run_fabulac(project_dir: Path, call: Any) -> Any:
    from . import fabulac_job as F
    extra = getattr(call, "extra", None) or {}
    raw = _ct()._tool_path(project_dir, call.path)
    if not _skill_on(project_dir):
        return _skill_off("fabulac", raw)
    if not raw:
        return _err("fabulac", "", "fabulac needs a <path>: a folder of Python in the project, or its .fabulac.cosm.")
    do = (extra.get("do") or "status").strip().lower()
    route = (extra.get("model") or "").strip() or None
    body: dict[str, Any] = {"path": raw, **({"route": route} if route else {})}
    try:
        if do == "status":
            folder, _fab = F.target_of(project_dir, raw)
            state = F.build_state(project_dir, folder)
            lines = _state_lines(state)
            jobs = _conf.get("jobs")
            jid = jobs.running_for(str(folder.resolve())) if jobs is not None else None
            if jid:
                snap = jobs.snapshot(jid)
                prog = snap.get("progress") or {}
                lines.append(_job_line(snap) + (f"; {prog.get('files_read')} of {prog.get('files')} files read, "
                                                 f"{prog.get('calls')} model calls" if prog else ""))
            return _result("fabulac", raw, True, "\n".join(lines))
        if do == "build":
            got = _start("build", body)
        elif do == "compile":
            what = (extra.get("what") or "code").strip().lower()
            got = _start("compile", {**body, "what": what})
        elif do == "cancel":
            folder, _fab = F.target_of(project_dir, raw)
            jobs = _conf.get("jobs")
            jid = jobs.running_for(str(folder.resolve())) if jobs is not None else None
            if not jid:
                return _err("fabulac", raw, f"no build or compile of {folder.name}/ is running")
            got = {"job": jobs.cancel(jid)}
        else:
            return _err("fabulac", raw, f"<do> is build, status, compile or cancel, not {do!r}")
    except F.BuildError as e:
        return _err("fabulac", raw, str(e))
    if isinstance(got, str):
        return _err("fabulac", raw, got)
    return _result("fabulac", raw, True, _job_line(got) + (". It runs after this turn; ask for its status later."
                                                           if do in ("build", "compile") else ""))


_RUNNERS = {"dialectic": run_dialectic, "fabulac": run_fabulac}


def register() -> None:
    """Add the tools to `tools._DISPATCH` and `_TRACE_TOGGLE`. Idempotent."""
    from . import tools as _t
    for name, runner in _RUNNERS.items():
        _t._DISPATCH.setdefault(name, runner)
        _t._TRACE_TOGGLE.setdefault(name, "trace_log_enabled")


__all__ = ["TOOL_NAMES", "configure", "register", "run_dialectic", "run_fabulac"]
