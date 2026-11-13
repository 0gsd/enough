"""A poem decompiled into its fabulap in steps, as one resumable job (0.7; Thym 20.9; MacroCOSM OES 18.4.6, 18.4.7).

**The job.** `defaults/thym/decompile-verse.thym` holds five programs, and its header comment is the job's
specification: the host runs them in the order they are written (`scan-the-poem`, `hear-the-poem`, `read-the-poem`,
`read-closely`, `raise-the-questions`), as one job, each one atomic Thym run, filling each program's `f` with the
fabulap the program before it landed. After each program the fabulap so far is written beside the poem as
`<poem>.fabulap.cosm` (all at once, never half a file). A job that stops, for any reason, takes up again after the
last program that landed, and everything it needs is read from disk: the fabulap's `derived.runs`, where each program
names itself (`scan` and `construe` write their own entries, `derive … as verse with f` its own; for the questions the
host writes it). It takes up again only while the poem's digest equals the fabulap's `source.sha256`; a poem that
changed is scanned again from the start.

This is `fabulac_job`'s pattern for a poem: the plain functions are what the routes translate and what a test or the
agent's tool calls without the app; `build_router` closes over what `create_app` owns.

**Three steps on the page.** The person sees three: **scan** (`scan-the-poem`: stanzas, lines, stresses, metre, by
rule), **hear** (`hear-the-poem`: rhyme, sound, recurrence, form, by rule) and **read closely** (the three programs that
ask a model: what the poem says, the seven axes of `construe`, and the questions). `STEP_OF` maps a program to its step.

**Models.** The mode is decided once, before the job starts, as the fabulac's is. The first two programs ask nothing and
always run. With no model answering, agent-free on, or `mode: rules` asked, the job stops after them with the outline
(`completeness: outline`), and the program that would ask a model is refused in the words the host uses for a plan that
asks ("1 step asks a model on the local route, the first `…` (line 36); agent-free is on").
"""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import canon_tools as _canon_tools
from . import fabula_names as _fabula_names
from . import fabulac_job as _fj
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .fabulac_job import BuildError
from .thym import Refusal

PROGRAM_FILE = "decompile-verse.thym"
#: The five programs of the shipped file, in the order the job runs them.
STAGES: tuple[str, ...] = ("scan-the-poem", "hear-the-poem", "read-the-poem", "read-closely", "raise-the-questions")
STAGE_WORDS = {"scan-the-poem": "scan", "hear-the-poem": "hear", "read-the-poem": "read",
               "read-closely": "read closely", "raise-the-questions": "question"}
#: The page's three steps, and the program each is made of.
STEPS: tuple[str, ...] = ("scan", "hear", "read-closely")
STEP_OF = {"scan-the-poem": "scan", "hear-the-poem": "hear", "read-the-poem": "read-closely",
           "read-closely": "read-closely", "raise-the-questions": "read-closely"}
#: The programs that ask no model (the outline): a build with no model runs these and stops (MacroCOSM OES 18.4.7).
RULES_STAGES = 2
ASKING_STAGES = len(STAGES) - RULES_STAGES
#: The output each program gives (scan gives `f`, the others `g`).
OUTPUT = {"scan-the-poem": "f"}
JOB_KIND = "fabulap"
FABULAP_SUFFIX = _fabula_names.suffix("fabulap")            # `.fabulap.cosm`
#: The seven axes of `construe`, in the order read-closely asks them (Thym 20.9).
AXES = ("figure", "image", "allusion", "voice", "turn", "meaning", "ambiguity")


def program_path() -> Path:
    """The shipped program file (never a project's file of the same name: the job is enough's)."""
    return _host.SHIPPED_PROGRAMS / PROGRAM_FILE


def job_ceiling(calls: int | None, job_calls: int | None) -> int | None:
    """The ceiling on the job's model calls (`fabulac_job.job_ceiling`'s rule, over the three programs that ask)."""
    if job_calls is not None:
        return job_calls
    return calls * ASKING_STAGES if calls is not None else None


# ---------------------------------------------------------------------------
# Paths: the poem and its fabulap
# ---------------------------------------------------------------------------

def target_of(project_dir: Path, rel: str) -> tuple[Path, Path, dict]:
    """`(poem, fabulap, target)` for a request's `path`: the poem itself, or its `<poem>.fabulap.cosm`. The poem is
    vetted as a decompile's text is (`canon_tools.text_target`: a text kind, not empty, no Holotype, no `.cosm`), in the
    project, with no link on the way."""
    raw = _canon_tools.tidy_rel(str(rel or ""))
    if not raw:
        raise BuildError("missing path")
    if _canon_tools.store_prefix(raw):
        raise BuildError("a poem is decompiled in steps from the project, not from the Canon store")
    p = _fj.project_path(project_dir, raw)
    if p.name.endswith(FABULAP_SUFFIX) and len(p.name) > len(FABULAP_SUFFIX):
        poem = p.with_name(p.name[: -len(FABULAP_SUFFIX)])
        raw = _fj.rel_of(project_dir, poem)
        p = _fj.project_path(project_dir, raw)
    if p.is_symlink():
        raise BuildError(f"{p.name} is a link; nothing is read through a link")
    if p.is_dir():
        raise BuildError(f"{p.name} is a folder; a poem is a text, and a folder of Python is built as a fabulac")
    try:
        t = _canon_tools.text_target(Path(project_dir), raw, "fabulap")
    except _canon_tools.TextTargetError as e:
        raise BuildError(str(e), e.status) from None
    return t["target"], Path(t["new_twin"]), t


def _digest(poem: Path) -> str | None:
    from .thym.values import read_value
    try:
        return read_value(poem, "text").sha256
    except Exception:  # noqa: BLE001 - a poem that cannot be read has no digest
        return None


# ---------------------------------------------------------------------------
# The state, read from disk: the fabulap's runs
# ---------------------------------------------------------------------------

def _runs(doc: dict) -> list[dict]:
    d = doc.get("derived") if isinstance(doc.get("derived"), dict) else {}
    runs = d.get("runs") if isinstance(d.get("runs"), list) else []
    return [r for r in runs if isinstance(r, dict)]


def _held(v: Any) -> str:
    if _macrocosm.is_pending(v):
        return "open"
    return "held" if v is True else ("not held" if v is False else "open")


def _intended(v: Any) -> Any:
    return v if isinstance(v, bool) else ("open" if _macrocosm.is_pending(v) else None)


def card_of(doc: dict) -> dict:
    """What the fabulap card draws (plain data): the `C:form` (its name, scheme, each rule held, not held or open, its
    departures), the metre, each device with its `cue` and `senses`, a lyric's labelled parts and its hook, and the
    counts of lines, readings and voices."""
    nodes = [it for it in (doc.get("nodes") or []) if isinstance(it, dict)]

    def kind(it: dict) -> str:
        return str(it.get("type") or str(it.get("id", "")).split("/", 1)[0].split(":")[-1])

    def plain(v: Any) -> Any:
        return _macrocosm.jsonable(v)

    form = next((it for it in nodes if kind(it) == "form"), None)
    out: dict = {"form": None, "metre": None, "devices": [], "parts": [], "hook": None, "lyric": False}
    if form is not None:
        out["form"] = {
            "id": form.get("id"), "name": plain(form.get("name")), "form": plain(form.get("form")),
            "scheme": plain(form.get("scheme")), "stance": form.get("stance"),
            "rules": [{"rule": plain(r.get("rule")), "held": _held(r.get("held"))}
                      for r in (form.get("rules") or []) if isinstance(r, dict)],
            "departures": [{"at": plain(d.get("at")), "what": plain(d.get("what"))}
                           for d in (form.get("departures") or []) if isinstance(d, dict)],
            "intended": _intended(form.get("intended")),
            "confidence": (form.get("provenance") or {}).get("confidence") if isinstance(form.get("provenance"), dict)
            else None}
    metre = next((it for it in nodes if kind(it) == "metre"), None)
    if metre is not None:
        out["metre"] = {"id": metre.get("id"), "name": plain(metre.get("name")),
                        "departures": len([d for d in (metre.get("departures") or []) if isinstance(d, dict)])}
    for it in nodes:
        k = kind(it)
        if k == "device":
            row = {"id": it.get("id"), "figure": plain(it.get("figure")), "name": plain(it.get("name")),
                   "cue": plain(it.get("cue")), "senses": [str(s) for s in it.get("senses") or []
                                                         if isinstance(s, str)],
                   "where": [str(w) for w in (it.get("where") or []) if isinstance(w, str)],
                   "stance": it.get("stance"), "intended": _intended(it.get("intended"))}
            out["devices"].append(row)
            if row["figure"] == "hook" and out["hook"] is None:
                out["hook"] = row
        elif k == "part":
            again = next((ln.get("to") for ln in (it.get("links") or []) if isinstance(ln, dict)
                          and ln.get("rel") == "is-a"), None)
            out["parts"].append({"id": it.get("id"), "name": plain(it.get("name")),
                                 "division": plain(it.get("division")), "heading": plain(it.get("heading")),
                                 "again": again})
    out["lyric"] = any(p["division"] not in ("stanza", None) for p in out["parts"])
    lines = [it for it in nodes if kind(it) == "line"]
    out["lines"] = len(lines)
    out["unscanned"] = sum(1 for it in lines if _macrocosm.is_pending(it.get("stresses")))
    out["readings"] = sum(1 for it in nodes if kind(it) == "reading")
    out["voices"] = sum(1 for it in nodes if kind(it) == "voice")
    return out


def build_state(project_dir: Path, poem: Path, fab: Path | None = None) -> dict:
    """Where a build of `poem` stands, read from disk alone: `{poem, fabulap, exists, built, moved, poem_exists,
    stages: [{name, stage, step, landed, run, at, model, route}], steps: [{step, landed, of}], landed, next, complete,
    completeness, card}`. A program has landed when the fabulap's `derived.runs` holds an entry it wrote (named by the
    program); the programs run in order, so the build stands after the first one that has not. `built` is false for a
    fabulap decompiled in one call (none of the five wrote it)."""
    fab = fab or _fabula_names.twin_path(poem, "fabulap")
    doc = _fj._load(fab) if fab.is_file() else {}
    exists = bool(doc) and str(doc.get("oes") or "").split("/")[0] in ("fabula", "emf") \
        and doc.get("flavour") == "fabulap"
    by: dict[str, dict] = {}
    if exists:
        for r in _runs(doc):
            if r.get("program") in STAGES:
                by[str(r["program"])] = r             # the last entry a program wrote
    landed = 0
    for s in STAGES:
        if s not in by:
            break
        landed += 1
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    built_sha = src.get("sha256") if exists else None
    sha = _digest(poem) if poem.is_file() else None
    moved = bool(exists and built_sha and sha and built_sha != sha)
    stages = []
    for i, n in enumerate(STAGES):
        r = by.get(n) or {}
        stages.append({"name": n, "stage": STAGE_WORDS[n], "step": STEP_OF[n], "landed": i < landed,
                       "run": r.get("run"), "at": _macrocosm.jsonable(r.get("at")), "model": r.get("model"),
                       "route": r.get("route")})
    steps = [{"step": st, "of": sum(1 for s in STAGES if STEP_OF[s] == st),
              "landed": sum(1 for s in stages if s["step"] == st and s["landed"])} for st in STEPS]
    built = exists and bool(by)
    nxt = STAGES[landed] if landed < len(STAGES) else None
    derived = doc.get("derived") if isinstance(doc.get("derived"), dict) else {}
    return {"poem": _fj.rel_of(project_dir, poem), "fabulap": _fj.rel_of(project_dir, fab) if fab.exists() else None,
            "exists": exists, "built": built, "moved": moved, "poem_exists": poem.is_file(), "stages": stages,
            "steps": steps, "landed": landed if built and not moved else 0,
            "next": nxt if built and not moved else STAGES[0],
            "complete": built and nxt is None and not moved,
            "completeness": derived.get("completeness") if exists else None,
            "card": card_of(doc) if exists else None}


def start_index(state: dict, *, restart: bool = False, resume_only: bool = False) -> int:
    """Where a build starts: after the last program that landed, as long as the poem has not changed; the scan when
    asked to start again, when there is no fabulap, or when the poem changed. Refused (409): a complete build without
    `restart`; a fabulap decompiled in one call without `restart` (building it in steps replaces it); with
    `resume_only`, a build with nothing to take up again."""
    if not state["poem_exists"]:
        raise BuildError(f"no such poem: {state['poem']}", 404)
    if restart:
        return 0
    if resume_only:
        if not state["built"]:
            raise BuildError(f"nothing to take up again: {state['poem']} has no fabulap built in steps yet; build it",
                             409)
        if state["moved"]:
            raise BuildError(f"nothing to take up again: {state['poem']} changed since its fabulap was scanned; "
                             "build it again from the scan", 409)
    if state["exists"] and not state["built"] and not state["moved"]:
        raise BuildError(f"{state['fabulap']} was decompiled in one call; building it in steps starts again from the "
                         "scan and replaces it: pass restart", 409)
    if state["complete"]:
        raise BuildError(f"already built: {state['fabulap']} holds every step; pass restart to build it again", 409)
    if not state["exists"] or state["moved"]:
        return 0
    return state["landed"]


# ---------------------------------------------------------------------------
# One program: its inputs, its plan, its run, its landing
# ---------------------------------------------------------------------------

def stage_rows(poem: Path, fab: Path, stage: str) -> list[dict]:
    """The inputs of one program: `poem` the text, `f` the fabulap so far."""
    from .thym.values import digest_path
    rows = []
    if stage != "raise-the-questions":
        rows.append({"name": "poem", "type": "text", "path": str(poem), "sha256": digest_path(poem)})
    if stage != "scan-the-poem":
        rows.append({"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)})
    return rows


def _progress(stage: str, i: int, tally: dict, at_most: Any, route: str | None,
              job_at_most: int | None = None) -> dict:
    """A running build's status (the job's `progress`): the program, its step on the page, model calls made (across
    the job) and at most (the program's plan), the job's ceiling, the route."""
    return {"stage": STAGE_WORDS[stage], "program": stage, "step": STEP_OF[stage], "n": i + 1, "of": len(STAGES),
            "calls": tally.get("calls", 0), "at_most": at_most, "job_at_most": job_at_most, "route": route}


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


def run_build(project_dir: Path, poem: Path, *, mode: str, why: str = "", route: str = "local",
              model: str | None = None, calls: int | None = None, llm_url: str | None = None,
              scaffolds: bool = False, restart: bool = False, resume_only: bool = False,
              runtime: _fj.Runtime | None = None, complete: Callable | None = None,
              progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
              now: dt.datetime | None = None, job_calls: int | None = None) -> dict:
    """The job's work (blocking): the programs from where the build stands (`start_index`), each planned, run and
    landed in turn. Returns `{poem, fabulap, ran: [{stage, program, run, trace}], state, complete, refusal?, calls,
    message}`; raises DeriveCancelled on a cancel (what landed stays) and RuntimeError when a program is refused while
    it runs (in the refusal's words, naming where the build takes up again)."""
    from .thym import plan as _plan
    from .thym import run as _run
    project_dir = Path(project_dir)
    fab = _fabula_names.twin_path(poem, "fabulap")
    state = build_state(project_dir, poem, fab)
    first = start_index(state, restart=restart, resume_only=resume_only)
    prog = program_path()
    checked = _fj._checked(prog)
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    tally: dict = {"calls": 0}
    ceiling = job_ceiling(calls, job_calls)
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
        asks = _fj.plan_asks(checked, stage)
        if asks and (mode != "model" or scaffolds):
            # The outline is what a build without a model writes (18.4.7): scan and hear, and the program that asks
            # is refused in the words a plan that asks is refused with; the build waits there.
            plan = _plan.plan(checked, stage_rows(poem, fab, stage), program=stage, inputs_root=project_dir)
            if isinstance(plan, Refusal):
                r = plan
            elif scaffolds:
                r = Refusal("plan", "rules", f"a build by rules writes the outline only (scan and hear); {stage} "
                                             "asks a model")
            else:
                r = _thym_api.asks_refusal(plan, why, route=route, program=prog)
            refusal = _thym_api.refusal_dict(r) or {"stage": "plan", "check": "rules", "line": None,
                                                    "message": f"{stage} asks a model"}
            refusal["program"] = stage
            stop_note = f"; {stage} waits: {refusal['message']}"
            break
        left = None if ceiling is None or not asks else ceiling - tally.get("calls", 0)
        if left is not None and left <= 0:
            refusal = {"stage": "run", "check": "calls", "line": None, "program": stage,
                       "message": f"{_fj._job_ceiling_words(ceiling, tally.get('calls', 0))}; {stage} did not start"}
            stop_note = f"; {stage} waits: {refusal['message']}"
            break
        stage_calls = calls if left is None else (left if calls is None else min(calls, left))
        rows = stage_rows(poem, fab, stage)
        info = None
        if asks:
            plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, program=stage,
                                        inputs_root=project_dir)
        else:
            plan = _plan.plan(checked, rows, program=stage, inputs_root=project_dir)
        if isinstance(plan, Refusal):
            raise RuntimeError(_stopped(stage, plan, i))
        if asks:
            r = _host.route_refusal(plan, info, calls=stage_calls, ceiling="calls", program=prog)
            if r is not None:
                raise RuntimeError(_stopped(stage, r, i))
        models = plan.get("models") if isinstance(plan.get("models"), dict) else {}
        at_most = models.get("at_most")
        say(phase=word, chunk=i + 1, chunks=total, message=f"step {i + 1} of {total}: {word}",
            progress=_progress(stage, i, tally, at_most, route if asks else None, ceiling))
        kw = make(stage, plan, info, mode if asks else "rules", False, prog)
        if asks and kw.get("coprocessor") is not None:
            kw["coprocessor"] = _fj.Counting(kw["coprocessor"], tally)
        if left is not None:
            kw["calls"] = left if kw.get("calls") is None else min(kw["calls"], left)

        def step(s: dict, _stage: str = stage, _i: int = i, _at: Any = at_most, _asks: bool = asks) -> None:
            say(phase=STAGE_WORDS[_stage], chunk=_i + 1, chunks=total,
                message=f"step {_i + 1} of {total}: {STAGE_WORDS[_stage]}",
                progress={**_progress(_stage, _i, tally, _at, route if _asks else None, ceiling), "step_node": s})
        t = _run.run(plan, inputs_root=project_dir, program=prog, progress=step, should_stop=should_stop,
                     **({"now": now} if now is not None else {}), **kw)
        if isinstance(t, Refusal):
            raise RuntimeError(_stopped(stage, t, i))
        if not t.landed:
            if t.refusal is not None and t.refusal.check == "cancelled":
                raise DeriveCancelled(_cancelled_words(stage, i))
            if (t.refusal is not None and t.refusal.check == "calls" and left is not None
                    and kw.get("calls") == left and (calls is None or left < calls)):
                raise RuntimeError(_stopped(stage, Refusal("run", "calls", _fj._job_ceiling_words(
                    ceiling, tally.get("calls", 0)) + "; nothing of this step landed"), i))
            raise RuntimeError(_stopped(stage, t.refusal, i))
        out = Path(t.outputs[OUTPUT.get(stage, "g")])
        text = out.read_text(encoding="utf-8")
        text = _fj.with_run(text, _fj._run_entry(t, stage), filename=fab.name)
        _fj.write_atomic(fab, text)
        ran.append({"stage": word, "program": stage, "run": t.run_id, "trace": str(t.path)})
    final = build_state(project_dir, poem, fab)
    landed_words = ", ".join(r["stage"] for r in ran) or "nothing"
    done = final["complete"]
    msg = f"{fab.name}: every step landed" if done else f"{fab.name}: {landed_words} landed{stop_note}"
    res = {"poem": final["poem"], "fabulap": final["fabulap"], "ran": ran, "state": final, "complete": done,
           "calls": {"made": tally.get("calls", 0), "at_most": ceiling}, "message": msg}
    if refusal is not None:
        res["refusal"] = refusal
    return res


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------

def route_of(body: dict) -> tuple[str, str | None, int | None]:
    """`(route, model, calls)` from a request, as the fabulac's build reads them."""
    raw = str(body.get("route") or "local").strip().lower()
    model = body.get("model")
    if raw.startswith("cloud:"):
        raw, model = "cloud", raw[len("cloud:"):]
    if raw not in _host.ROUTES:
        raise HTTPException(400, f"route is local or cloud (or cloud:<model id>), not {raw!r}")
    model = (str(model).strip() or None) if model not in (None, "") else None
    if raw == "local" and model:
        raise HTTPException(400, "a local build uses this machine's model; model names a cloud model, with route cloud")
    calls = body.get("calls")
    if calls is not None and (isinstance(calls, bool) or not isinstance(calls, int) or calls < 1):
        raise HTTPException(400, f"calls is a ceiling of at least 1 model call, not {calls!r}")
    return raw, model, calls


def build_router(*, project_dir: Path, llm_url: str | None, jobs: Any,
                 canon_mode: Callable[..., Awaitable[tuple[str, str]]], start_job: Callable[..., dict],
                 model_complete: Callable[..., Any], catalog_after: Callable[[str], None]) -> APIRouter:
    """The fabulap's routes under `/api/fabula/verse/` (build, resume, status, cancel), the fabulac's under
    `/api/fabula/` for a poem. A build is a CanonJob of kind `fabulap`, keyed by the poem (so a one-call decompile of
    the same poem and a build never run at once)."""
    router = APIRouter()
    project_dir = Path(project_dir)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        return body if isinstance(body, dict) else {}

    async def decide(body: dict, route: str) -> tuple[str, str, bool]:
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

    def job_kw(route: str | None, **more: Any) -> dict:
        kw = {"route": route} if _host._accepts(start_job, {"route": route}) else {}
        for k, v in more.items():
            if v is not None and _host._accepts(start_job, {k: v}):
                kw[k] = v
        return kw

    async def start_build(body: dict, *, resume_only: bool = False) -> dict:
        route, model, calls = route_of(body)
        job_calls = body.get("job_calls")
        if job_calls is not None and (isinstance(job_calls, bool) or not isinstance(job_calls, int) or job_calls < 1):
            raise HTTPException(400, f"job_calls is a ceiling of at least 1 model call, not {job_calls!r}")
        try:
            poem, fab, t = await asyncio.to_thread(target_of, project_dir, str(body.get("path") or ""))
            state = await asyncio.to_thread(build_state, project_dir, poem, fab)
            first = start_index(state, restart=bool(body.get("restart")), resume_only=resume_only)
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None
        mode, why, scaffolds = await decide(body, route)
        complete = complete_for(route, model) if mode == "model" and not scaffolds else None
        rel = state["poem"]

        def work(ctx: Any) -> dict:
            out = run_build(project_dir, poem, mode=mode, why=why, route=route, model=model, calls=calls,
                            llm_url=llm_url, scaffolds=scaffolds, restart=bool(body.get("restart")),
                            resume_only=resume_only, complete=complete, progress=lambda f: ctx.progress(f),
                            should_stop=ctx.should_stop, job_calls=job_calls)
            catalog_after(rel)
            return out

        from_words = (f"taking up the fabulap of {poem.name} from {STAGE_WORDS[STAGES[first]]}"
                      if first else f"decompiling {poem.name} in steps")
        on_cloud = mode == "model" and route == "cloud"
        snap = start_job(kind=JOB_KIND, path=rel, mode=mode, why=why if not scaffolds else "", work=work,
                         key=t["key"], doing=from_words + (" on the cloud" if on_cloud else ""),
                         **job_kw(route if mode == "model" else None, flavour="fabulap",
                                  extra={"progress": _progress(STAGES[first], first, {}, None,
                                                               route if mode == "model" and first >= RULES_STAGES
                                                               else None, job_ceiling(calls, job_calls))}))
        return {**snap, "state": state, "from": STAGES[first]}

    @router.post("/api/fabula/verse/build")
    async def fabulap_build(request: Request) -> dict:
        return await start_build(await body_of(request), resume_only=False)

    @router.post("/api/fabula/verse/resume")
    async def fabulap_resume(request: Request) -> dict:
        return await start_build(await body_of(request), resume_only=True)

    @router.get("/api/fabula/verse/build")
    def fabulap_build_state(path: str = Query(...)) -> dict:
        try:
            poem, fab, t = target_of(project_dir, path)
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None
        state = build_state(project_dir, poem, fab)
        job_id = jobs.running_for(str(t["key"])) if jobs is not None else None
        return {"state": state, "job": jobs.snapshot(job_id) if job_id else None}

    @router.post("/api/fabula/verse/cancel")
    async def fabulap_cancel(request: Request) -> dict:
        body = await body_of(request)
        try:
            poem, _fab, t = target_of(project_dir, str(body.get("path") or ""))
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None
        job_id = jobs.running_for(str(t["key"])) if jobs is not None else None
        if not job_id:
            raise HTTPException(409, f"no decompile of {poem.name} is running")
        try:
            return jobs.cancel(job_id)
        except Exception as e:  # noqa: BLE001 - CanonJobError carries its status
            raise HTTPException(getattr(e, "status", 409), str(e)) from None

    # what the agent's tool starts through (enough/fabula_tools.py), the same code as the routes
    router.start_build = start_build            # type: ignore[attr-defined]
    return router


__all__ = ["AXES", "JOB_KIND", "PROGRAM_FILE", "STAGES", "STAGE_WORDS", "STEPS", "STEP_OF", "build_router",
           "build_state", "card_of", "run_build", "start_index", "target_of"]
