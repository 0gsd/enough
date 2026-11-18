"""A fabulac authored as one resumable job: begun from a brief or from nothing, then the interview, stage by stage
(0.8, fabulac-first F1: pins section 4; MacroCOSM OES 18.4.1, 18.4.7, 18.6; THYM 20.11).

A sibling of the decompile job (`enough/fabulac_job.py`), which it leaves alone, as the fabulap's job was in 0.7.

**The job.** `defaults/thym/author-python.thym` is the text's program file: one program with two ways in,
`begin-from-a-brief` and `begin-by-interview` (each `author …` then `question`, landing the catalog and the first
stage's questions), and its helpers. The interview then goes on as the dialectic's pair of runs (THYM 22.4):
`settle-the-answers` (`settle.thym`) folds a sitting's answers in, and `raise-the-questions` raises the next questions,
which the bank `fabulac-authored` gives one stage at a time (`dialectic.raise_questions`): what the program is for and
for whom; the ways in; what it needs and the settings it reads; what it leaves out on purpose; the cases; the open
questions. The person answers between runs (`answer`, an answers volume beside the fabulac, one or two questions at a
time on the page); nothing waits inside a run.

**Each step lands whole, and the job takes up again from disk.** Every step is one Thym run whose output replaces
`<name>.fabulac.cosm` all at once, its run joining `derived.runs`. What to do next is read from disk alone
(`author_state`): no fabulac, begin; a sitting beside it not yet settled, settle it; no question open and the bank
has more to ask, raise them; questions open, wait for the person; nothing left, done. A job that stops anywhere is
started again and does what is next.

**Agent-free.** With no model to ask (agent-free on, or `mode: rules`), every step runs by rules. A brief is then read
by rules alone (`thym.moves.author.read_brief`, the move's own first part): the catalog lands from the one-move
program `begin-the-catalog` (`author as <kind>`), the brief's placed passages join it as the person's own words, and
what its headings do not place is named in the result and left for the interview. The result says so. With a model,
`begin-from-a-brief` runs as the text has it, and the model only places what the rules could not.

**The twin rule.** The folder beside an authored fabulac of the same name is its entailment (MacroCOSM OES 18.4.1):
`begin` refuses a name whose folder holds a program not entailed from this fabulac, and the decompile job refuses that
folder in turn (`fabulac_job.authored_twin`).

The plain functions are what a route, a tool or a test calls; no route is added here (the fabulac-first helpers lane
puts the routes behind the promise header).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Callable

from . import dialectic as _dl
from . import dialectic_api as _dapi
from . import fabulac_job as _fj
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .thym import Refusal
from .thym.moves import author as _author

PROGRAM_FILE = "author-python.thym"
#: The interview's raise, the dialectic's own program (THYM 22.4), as the decompile file holds it.
RAISE_FILE = _fj.PROGRAM_FILE
RAISE_PROGRAM = "raise-the-questions"
JOB_KIND = "fabulac-author"
FABULAC_SUFFIX = _fj.FABULAC_SUFFIX
#: The steps a job may take, in the words its status uses.
STEPS = ("begin", "settle", "raise", "answer", "done")
#: How many questions the page shows at once (the owner's ruling: one or two at a time).
SHOWN = 2
#: A job takes at most this many runs before it stops and says so (a stage that cannot land would loop).
MAX_STEPS = 40
AGENT_FREE_WORDS = "agent-free: no model was asked; the brief was read by rules alone"


class AuthorError(_fj.BuildError):
    """A refusal before anything runs, with the HTTP status a route answers it with."""


def begin_the_catalog(kind: str) -> str:
    """The one-move program an agent-free begin from a brief runs: the catalog alone, by rules (THYM 20.11's `author
    as <kind>`); the brief's placed passages join it after, by the same rules the move reads them with."""
    if kind not in _author.KINDS:
        raise AuthorError(f"a program is a tool, a library or a service, not {kind!r}")
    return ("thym 1\n\nprogram begin-the-catalog\n"
            "  why: an authored fabulac's catalog, begun by rules: the brief is read by rules beside it.\n"
            "  must: nothing is fetched; the brief is the person's own.\n\n"
            "  gives f: fabula\n\n"
            f"  give author as {kind}\nend\n")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def author_path(project_dir: Path, rel: str) -> Path:
    """The fabulac a request names: `<name>.fabulac.cosm`, or a bare name (`tally`) for the one beside it."""
    raw = str(rel or "").strip().rstrip("/")
    if not raw:
        raise AuthorError("missing path: name the program, or its <name>.fabulac.cosm")
    if not raw.endswith(FABULAC_SUFFIX):
        raw = raw + FABULAC_SUFFIX
    p = _fj.project_path(project_dir, raw)
    if _fj.folder_of(p) is None:
        raise AuthorError(f"{p.name} is not a fabulac's name: <name>.fabulac.cosm")
    return p


def _load(fab: Path) -> dict:
    return _fj._load(fab) if fab.is_file() else {}


def is_authored(fab: Path) -> bool:
    """Whether the fabulac at `fab` is authored (its source the authored form)."""
    return _author.is_authored(_load(fab))


def _brief_path(project_dir: Path, fab: Path, brief: str | None) -> Path | None:
    if not brief:
        return None
    p = _fj.project_path(project_dir, brief, what="brief")
    if not p.is_file():
        raise AuthorError(f"no such brief: {_fj.rel_of(project_dir, p)}", 404)
    if p.suffix.lower() not in (".md", ".markdown", ".txt"):
        raise AuthorError(f"{p.name} is not a brief: a brief is a markdown text the person wrote")
    return p


# ---------------------------------------------------------------------------
# The state, read from disk
# ---------------------------------------------------------------------------

def _target(project_dir: Path, fab: Path) -> _dapi.Target:
    return _dapi.target(project_dir, _fj.rel_of(project_dir, fab))


def author_state(project_dir: Path, fab: Path) -> dict:
    """Where an authored fabulac stands, from disk alone: `{fabulac, exists, authored, name, kind, licence, stages:
    [{stage, n, asked, open, landed}], stage, open, shown, sittings, next, complete}`. `next` is what the job does
    next (`STEPS`): `begin` with no fabulac; `settle` while a sitting beside it is not settled; `answer` while a
    question waits for the person; `raise` while the bank has more to ask; `done` when nothing is left."""
    project_dir = Path(project_dir)
    doc = _load(fab)
    exists = bool(doc) and str(doc.get("oes") or "").split("/")[0] in ("fabula", "emf")
    order = _author.stages()
    base = {"fabulac": _fj.rel_of(project_dir, fab), "exists": exists, "authored": False, "name": None,
            "kind": None, "licence": None, "stages": [{"stage": s, "n": i + 1, "asked": 0, "open": 0, "landed": False}
                                                      for i, s in enumerate(order)],
            "stage": None, "open": [], "shown": [], "sittings": 0, "next": "begin", "complete": False}
    if not exists:
        return base
    authored = _author.is_authored(doc)
    base.update(authored=authored, name=doc.get("name"),
                kind=(doc.get("program") or {}).get("kind") if isinstance(doc.get("program"), dict) else None,
                licence=_macrocosm.jsonable((doc.get("source") or {}).get("licence")))
    if not authored:
        base["next"] = "done"
        return base
    twin = _dl.open_twin(fab)
    led = twin.ledger
    t = _target(project_dir, fab)
    waiting = _dapi.unsettled(t, led)
    open_q = [q for q in led.questions() if q.get("state") == "open"]
    by_stage: dict[str, list[dict]] = {}
    for q in led.questions():
        st = _dl.stage_of_question(led, q)
        if st:
            by_stage.setdefault(st, []).append(q)
    unsettled = _dl.unsettled_questions(led)
    more = _dl.raise_questions(led.copy(), rules=True).questions if not unsettled and not waiting else []
    reached = max((order.index(s) for s in by_stage if s in order), default=-1)
    current = None
    for i, s in enumerate(order):
        qs = by_stage.get(s, [])
        row = base["stages"][i]
        row["asked"] = len(qs)
        row["open"] = sum(1 for q in qs if q.get("state") == "open")
        row["landed"] = i < reached or (i == reached and not unsettled and not waiting
                                        and not any(_dl.stage_of_question(led, q) == s for q in more))
        if current is None and not row["landed"] and (i <= reached or more):
            current = s
    if waiting:
        nxt = "settle"
    elif any(q.get("state") in _dl.ANSWERED and not q.get("settled") for q in led.questions()):
        nxt = "settle"
    elif open_q:
        nxt = "answer"
    elif more:
        nxt = "raise"
    else:
        nxt = "done"
        for row in base["stages"]:
            row["landed"] = True
        current = None
    base.update(stage=current, open=[q["id"] for q in open_q], sittings=len(waiting), next=nxt,
                shown=[{"id": q["id"], "asks": q.get("asks"), "kind": q.get("kind"), "hint": q.get("hint"),
                        "stage": _dl.stage_of_question(led, q)} for q in open_q[:SHOWN]],
                complete=nxt == "done")
    return base


# ---------------------------------------------------------------------------
# One step: a Thym run, landed whole
# ---------------------------------------------------------------------------

def _request(name: str, *, licence: str | None, by: str | None, brief: str | None, model: bool) -> Callable[[], dict]:
    """The `authoring` engine: what the person said in beginning it, as the move reads it (recorded per call)."""
    req = {"name": name, "licence": licence, "by": by, "brief": brief, "model": model}
    req = {k: v for k, v in req.items() if v is not None}

    def authoring() -> dict:
        return dict(req)
    return authoring


def _run_step(project_dir: Path, fab: Path, *, checked: Any, program: str | None, prog: Any, rows: list[dict],
              output: str, mode: str, why: str, route: str, model: str | None, calls: int | None,
              llm_url: str | None, runtime: Any, complete: Callable | None, extra_engines: dict | None,
              should_stop: Callable[[], bool] | None, now: dt.datetime | None, label: str) -> dict:
    """Plan, run and land one program of the job: its output replaces the fabulac all at once, its run in
    `derived.runs`. RuntimeError in the refusal's words when it does not land (nothing of it was written)."""
    from .thym import plan as _plan
    from .thym import run as _run
    asks = _fj.plan_asks(checked, program)
    use_model = asks and mode == "model"
    info = None
    if use_model:
        plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, program=program,
                                    inputs_root=project_dir)
    else:
        plan = _plan.plan(checked, rows, program=program, inputs_root=project_dir)
    if isinstance(plan, Refusal):
        raise RuntimeError(f"{label} was refused ({plan.check}): {plan.message}; nothing of it was written")
    if use_model:
        r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
        if r is not None:
            raise RuntimeError(f"{label} was refused ({r.check}): {r.message}; nothing of it was written")
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    kw = make(program or label, plan, info, "model" if use_model else "rules", asks and not use_model, prog)
    if extra_engines:
        kw["engines"] = {**dict(kw.get("engines") or {}), **extra_engines}
    t = _run.run(plan, inputs_root=project_dir, program=prog, should_stop=should_stop,
                 **({"now": now} if now is not None else {}), **kw)
    if isinstance(t, Refusal):
        raise RuntimeError(f"{label} was refused ({t.check}): {t.message}; nothing of it was written")
    if not t.landed:
        if t.refusal is not None and t.refusal.check == "cancelled":
            raise DeriveCancelled(f"cancelled during {label}; nothing of it was written")
        r = t.refusal
        raise RuntimeError(f"{label} was refused ({r.check if r else 'run'}): {r.message if r else 'it did not land'}; "
                           "nothing of it was written")
    text = Path(t.outputs[output]).read_text(encoding="utf-8")
    text = _fj.with_run(text, _fj._run_entry(t, program or label), filename=fab.name)
    _fj.write_atomic(fab, text)
    return {"step": label, "program": program or label, "run": t.run_id, "trace": str(t.path)}


def _with_brief_by_rules(fab: Path, brief: Path, brief_rel: str) -> dict:
    """An agent-free begin's second half: the brief's passages its headings place, read by rules, written into the
    landed fabulac as the person's own words; what they do not place is named, not written."""
    text = brief.read_text(encoding="utf-8")
    twin = _dl.open_twin(fab)
    nodes = twin.doc.get("nodes") if isinstance(twin.doc.get("nodes"), list) else []
    placed, unplaced = _author.read_brief(text)
    new = _author.brief_items(placed, nodes, brief_rel)
    if new:
        nodes.extend(new)
        twin.doc["nodes"] = nodes
        _fj.write_atomic(fab, twin.render())
    return {"placed": len(placed), "unplaced": [{"lines": [p["first"], p["last"]], "heading": p["heading"],
                                                 "text": _author.fold(p["text"])[:200]} for p in unplaced]}


def _licence_into_source(fab: Path) -> bool:
    """The licence the interview gave (`R:licence`'s identifier) carried into `source.licence` while that is still a
    question: the catalog says it as the folder form does (MacroCOSM OES 18.4.1). Every other byte kept."""
    twin = _dl.open_twin(fab)
    src = twin.doc.get("source")
    if not isinstance(src, dict) or not _macrocosm.is_pending(src.get("licence")):
        return False
    ident = next((n.get("identifier") for n in twin.doc.get("nodes") or []
                  if isinstance(n, dict) and n.get("id") == "R:licence/licence"), None)
    if not (isinstance(ident, str) and ident.strip()):
        return False
    src["licence"] = ident.strip()
    _fj.write_atomic(fab, twin.render())
    return True


def begin(project_dir: Path, fab: Path, *, kind: str = "tool", brief: str | None = None, licence: str | None = None,
          by: str | None = None, mode: str = "rules", **kw: Any) -> dict:
    """The job's first step: the authored fabulac begun, its catalog and the first stage's questions landed beside it
    (`begin-from-a-brief` or `begin-by-interview`; agent-free with a brief, `begin-the-catalog` and the brief by
    rules, then the first raise). Refused (409) when a fabulac is there already, or when the folder of the same name
    holds a program this fabulac did not entail."""
    project_dir = Path(project_dir)
    if kind not in _author.KINDS:
        raise AuthorError(f"a program is a tool, a library or a service, not {kind!r}")
    if fab.exists():
        raise AuthorError(f"{fab.name} is there already; take it up again, or choose another name", 409)
    folder = _fj.folder_of(fab)
    if folder is not None and folder.exists():
        raise AuthorError(f"{folder.name}/ is there already and has no fabulac: decompile it to make its fabulac, or "
                          "choose another name for the program you mean to author", 409)
    name = folder.name if folder is not None else fab.name
    bp = _brief_path(project_dir, fab, brief)
    brief_rel = None
    if bp is not None:
        import os
        brief_rel = Path(os.path.relpath(bp.resolve(), fab.parent.resolve())).as_posix()
    use_model = mode == "model"
    engines = {_author.ENGINE: _request(name, licence=licence, by=by, brief=brief_rel, model=use_model)}
    from .thym.values import digest_path
    common = dict(mode=mode, why=kw.get("why", ""), route=kw.get("route", "local"), model=kw.get("model"),
                  calls=kw.get("calls"), llm_url=kw.get("llm_url"), runtime=kw.get("runtime"),
                  complete=kw.get("complete"), should_stop=kw.get("should_stop"), now=kw.get("now"))
    if bp is not None and not use_model:
        checked = _fj._checked(text=begin_the_catalog(kind))
        ran = _run_step(project_dir, fab, checked=checked, program="begin-the-catalog", prog=begin_the_catalog(kind),
                        rows=[], output="f", extra_engines=engines, label="begin", **common)
        ran["brief"] = _with_brief_by_rules(fab, bp, brief_rel)
        ran["says"] = AGENT_FREE_WORDS
        return ran
    prog = _host.SHIPPED_PROGRAMS / PROGRAM_FILE
    checked = _fj._checked(prog)
    text = prog.read_text(encoding="utf-8")
    program = "begin-from-a-brief" if bp is not None else "begin-by-interview"
    # the text's programs say `as tool`; another kind runs the same program with its `as` word
    if kind != "tool":
        text = text.replace("author brief as tool", f"author brief as {kind}").replace("author as tool",
                                                                                       f"author as {kind}")
        checked = _fj._checked(text=text)
        prog = text
    rows = [{"name": "brief", "type": "text", "path": str(bp), "sha256": digest_path(bp)}] if bp is not None else []
    ran = _run_step(project_dir, fab, checked=checked, program=program, prog=prog, rows=rows, output="f",
                    extra_engines=engines, label="begin", **common)
    if not use_model:
        ran["says"] = "agent-free: no model was asked"
    return ran


def raise_next(project_dir: Path, fab: Path, **kw: Any) -> dict:
    """The next stage's questions raised and landed (`raise-the-questions`, by the bank's rules)."""
    prog = _host.SHIPPED_PROGRAMS / RAISE_FILE
    checked = _fj._checked(prog)
    from .thym.values import digest_path
    rows = [{"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)}]
    return _run_step(project_dir, fab, checked=checked, program=RAISE_PROGRAM, prog=prog, rows=rows, output="g",
                     mode="rules", why=kw.get("why", ""), route=kw.get("route", "local"), model=None,
                     calls=None, llm_url=None, runtime=kw.get("runtime"), complete=None, extra_engines=None,
                     should_stop=kw.get("should_stop"), now=kw.get("now"), label="raise")


def settle_next(project_dir: Path, fab: Path, *, mode: str = "rules", **kw: Any) -> dict:
    """Every sitting beside the fabulac settled (`settle.thym`, one run per sitting, each landing whole), then the
    licence the interview gave carried into the catalog."""
    t = _target(project_dir, fab)
    out = _dapi.settle_fabula(project_dir, t, mode=mode, why=kw.get("why", ""), route=kw.get("route", "local"),
                              model=kw.get("model"), calls=kw.get("calls"), llm_url=kw.get("llm_url"),
                              scaffolds=mode != "model", complete=kw.get("complete"), runtime=kw.get("runtime"),
                              should_stop=kw.get("should_stop"), now=kw.get("now"))
    out["licence"] = _licence_into_source(fab)
    return {"step": "settle", "program": "settle-the-answers", "runs": out.get("runs") or [],
            "settled": out.get("settled") or [], "counters": out.get("counters") or [],
            "waiting": out.get("waiting") or [], "licence": out["licence"]}


# ---------------------------------------------------------------------------
# The job's work
# ---------------------------------------------------------------------------

def run_author(project_dir: Path, rel: str, *, kind: str = "tool", brief: str | None = None,
               licence: str | None = None, by: str | None = None, mode: str = "rules", why: str = "",
               route: str = "local", model: str | None = None, calls: int | None = None, llm_url: str | None = None,
               runtime: Any = None, complete: Callable | None = None,
               progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
               now: dt.datetime | None = None) -> dict:
    """The job's work (blocking): every step it can take without the person, from where the fabulac stands
    (`author_state`), each landing whole: begin, settle what was answered, raise the next stage; it stops when the
    person has questions to answer, or when nothing is left. Returns `{fabulac, ran: [...], state, complete, waiting,
    message}` (`waiting`: the questions to show, one or two). Raises DeriveCancelled on a cancel (the steps that
    landed stay) and RuntimeError when a step is refused (in its words)."""
    project_dir = Path(project_dir)
    fab = author_path(project_dir, rel)
    if fab.exists() and not is_authored(fab):
        raise AuthorError(f"{fab.name} was decompiled from a folder, not authored: its questions are the "
                          "decompile's", 409)
    common = dict(why=why, route=route, model=model, calls=calls, llm_url=llm_url, runtime=runtime,
                  complete=complete, should_stop=should_stop, now=now)
    ran: list[dict] = []
    says: list[str] = []
    for _ in range(MAX_STEPS):
        state = author_state(project_dir, fab)
        step = state["next"]
        if step in ("answer", "done"):
            break
        if should_stop is not None and should_stop():
            raise DeriveCancelled(f"cancelled before {step}; what landed stays, and the job takes up again from {step}")
        if progress is not None:
            progress({"phase": step, "message": f"{fab.name}: {step}"
                      + (f", stage {state['stage']}" if state.get("stage") else "")})
        if step == "begin":
            r = begin(project_dir, fab, kind=kind, brief=brief, licence=licence, by=by, mode=mode, **common)
            if r.get("says"):
                says.append(r["says"])
        elif step == "settle":
            r = settle_next(project_dir, fab, mode=mode, **common)
        else:
            r = raise_next(project_dir, fab, **common)
        ran.append(r)
    else:
        says.append(f"stopped after {MAX_STEPS} steps; take it up again")
    final = author_state(project_dir, fab)
    if final["complete"]:
        msg = f"{fab.name}: every stage of the interview has landed"
    elif final["next"] == "answer":
        msg = (f"{fab.name}: {len(final['open'])} question{'s' if len(final['open']) != 1 else ''} wait for you"
               + (f" (stage: {final['stage']})" if final.get("stage") else ""))
    else:
        msg = f"{fab.name}: next, {final['next']}"
    if says:
        msg += "; " + "; ".join(dict.fromkeys(says))
    return {"fabulac": final["fabulac"], "ran": ran, "state": final, "complete": final["complete"],
            "waiting": final["shown"], "message": msg}


def answer(project_dir: Path, rel: str, answers: Any, *, through: str = "person", who: str | None = None,
           at: Any = None) -> dict:
    """A sitting: the person's answers to the questions shown, written beside the fabulac as an answers volume
    (`dialectic_api.record`); the next `run_author` settles them and raises what follows."""
    fab = author_path(project_dir, rel)
    if not is_authored(fab):
        raise AuthorError(f"{fab.name} is not an authored fabulac", 409)
    return _dapi.record(project_dir, _fj.rel_of(project_dir, fab), answers, through=through, who=who, at=at)


def check(project_dir: Path, rel: str) -> dict:
    """The authored fabulac's checks (`fabula.lint`): `{ok, errors, warnings, uncovered}`, `uncovered` the
    requirements of `force: must` that no case shows yet (THYM 20.11)."""
    from . import fabula as _fabula
    fab = author_path(project_dir, rel)
    rep = _fabula.lint(fab)
    doc = _load(fab)
    return {"fabulac": _fj.rel_of(project_dir, fab), "ok": rep.ok,
            "errors": [str(p) for p in rep.errors], "warnings": [str(p) for p in rep.warnings],
            "uncovered": [d["id"] for d in _author.uncovered_items(doc.get("nodes") or [])],
            "source": _author.source_problems(doc)}


__all__ = ["AGENT_FREE_WORDS", "AuthorError", "JOB_KIND", "PROGRAM_FILE", "SHOWN", "STEPS", "answer", "author_path",
           "author_state", "begin", "begin_the_catalog", "check", "is_authored", "raise_next", "run_author",
           "settle_next"]
