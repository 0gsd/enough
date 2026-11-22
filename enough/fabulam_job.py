"""A Lean file taken apart into its fabulam as one resumable job, a folder of them under a head, and a fabulam
entailed as its pshorts (0.9; MacroCOSM OES 18.4.10; Thym 20.13; the design's 4.3, 5.2, 5.4 and 6).

**The file job.** `defaults/thym/decompile-lean.thym` holds six programs, and its header comment is the job's
specification: the host runs them in the order they are written, as one job, each one atomic Thym run, each landing
the fabulam so far (all at once, never half a file) with its run in `derived.runs`. A job that stops takes up again
after the last program that landed, read from disk alone, while the Lean file's sha256 is the one the fabulam
recorded (`source.sha256`); a file that changed is built again from the survey. `fit-the-wording` runs only when a
public wording was given. Only when the last program has landed does the job write `derived.completeness: full`,
and it then reads the whole fabulam's checks once more.

**Models.** The survey asks nothing and always runs. With no model (none answering, agent-free on, or rules asked)
the build stops after it with the outline, and the program that would ask is refused in the words the host uses for
any plan that asks.

**Before the survey**, the job writes by rule a fabulam of the catalog alone (`fabulam_head.catalog_alone`): what
it read from disk and what the person entered (the targets, the wording, what is said about checking and who says
it). The survey takes it as `survey t with h`. A part of an archive is surveyed with its head instead.

**The archive job.** `decompile-lean-archive.thym` holds a head's two programs. The job surveys the folder; then,
for each file in the order of the imports, runs the file job (a file the targets do not reach is surveyed and left
as an outline, never read by a model), copies the part's summary upward and ties the part into its head
(`fabulam_head`); then, when every reached part is whole, folds the head.

**Entailing.** `entail-pshort.thym` entails the three pshorts; one density runs `entail f as <density>` alone. Each
lands beside the fabulam as `<name>.pshort-<density>-<YYYY-MM-DD-HHMM>.md` and is recorded in the fabulam's
`shorts:` with its density and `entailed: apart`. The Lean is never read there.

enough installs, builds and runs nothing of Lean, and no state, message or pshort written here says a proof is
machine-checked: `checking` in every state is the sentence of `P:claim/checking`, as rules wrote it.

The plain functions are what a card and a route call (`file_state`, `archive_state`, `run_file_build`,
`run_archive_build`, `run_entail`); no route is declared here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
from pathlib import Path
from typing import Any, Callable

from . import fabula as _fabula
from . import fabula_names as _names
from . import fabulac_job as _fj
from . import fabulam_head as _head
from . import macrocosm as _macrocosm
from . import thym_api as _thym_api
from . import thym_host as _host
from .canon_derive import DeriveCancelled
from .fabulac_job import BuildError, Runtime
from .thym import Refusal
from .thym.moves import proof as _proof

log = logging.getLogger("enough.fabulam_job")

PROGRAM_FILE = "decompile-lean.thym"
ARCHIVE_FILE = "decompile-lean-archive.thym"
PSHORT_FILE = "entail-pshort.thym"
#: The six programs of the file job, in the order they run, and the word a card says for each.
STAGES: tuple[str, ...] = ("survey-the-proof", "read-the-proof", "audit-the-comments", "fit-the-wording",
                           "fold-the-argument", "raise-the-questions")
STAGE_WORDS = {"survey-the-proof": "survey", "read-the-proof": "read", "audit-the-comments": "audit",
               "fit-the-wording": "fit", "fold-the-argument": "fold", "raise-the-questions": "question"}
#: The head's two programs.
HEAD_STAGES: tuple[str, ...] = ("survey-the-archive", "fold-the-head")
#: The output each program gives (the surveys give `f`, the others `g`).
OUTPUT = {"survey-the-proof": "f", "survey-the-archive": "f"}
DENSITIES = _proof.DENSITIES
SUFFIX = _head.SUFFIX
PSHORT_MARK = ".pshort-"
#: A file's rule may find several final theorems; past this many the person picks before anything is built.
PICK_PAST = 3
#: The states of a card (the design's 6), and the line each says.
STATE_LINES = {
    "none": "no fabulam yet: building it writes {name}",
    "pick": "this file ends in {n} results: choose the one to tell",
    "outline": "an outline: the survey landed by rules; reading waits for a model",
    "partway": "{n} of {m} stages landed; the build can take up again from {next}",
    "complete": "built: every stage landed",
    "moved": "the Lean file has changed since its fabulam was surveyed: a build starts again from the survey",
    "gone": "the Lean file is not there any more; its fabulam stays as it is",
}
HEAD_LINE = "{k} of {n} files read; {m} not reached and left as outlines"


def program_path(name: str = PROGRAM_FILE) -> Path:
    return _host.SHIPPED_PROGRAMS / name


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _digest(p: Path, typ: str | None = None) -> str:
    from .thym.values import digest_path
    return digest_path(p, typ) or ""


def fabulam_path(source: Path, name: str | None = None) -> Path:
    """Where the fabulam of a Lean file or folder lands (`fabulam_head.fabulam_path`)."""
    return _head.fabulam_path(source, name)


def _outline(lean: Path) -> dict:
    """The reader's outline of a Lean file, for the host's own rules (the pick): read as text, nothing run."""
    from . import repo_engine as _re
    try:
        ol = _re.SYNTAX.outline(lean.name, lean.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001 - a file the reader cannot read has no targets by rule
        return {}
    return ol if isinstance(ol, dict) and ol.get("ok") else {}


def targets_by_rule(lean: Path) -> list[str]:
    """The final theorems the rule finds in one Lean file (the design's 1.1)."""
    ol = _outline(lean)
    return _proof.targets_by_rule(ol) if ol else []


# ---------------------------------------------------------------------------
# The state, read from disk
# ---------------------------------------------------------------------------

def _runs(doc: dict, stages: tuple[str, ...]) -> dict[str, dict]:
    d = doc.get("derived") if isinstance(doc.get("derived"), dict) else {}
    out: dict[str, dict] = {}
    for r in d.get("runs") or []:
        if isinstance(r, dict) and r.get("program") in stages:
            out[str(r["program"])] = r
    return out


def stages_for(wording: Any) -> tuple[str, ...]:
    """The programs a file's build runs: the six, less `fit-the-wording` when no public wording was given."""
    return tuple(s for s in STAGES if s != "fit-the-wording" or wording)


def _when(x: Any) -> dt.datetime | None:
    """A moment a catalog holds, as YAML read it or as text, in UTC; None for anything else."""
    if isinstance(x, dt.datetime):
        return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
    try:
        got = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=dt.timezone.utc)


def pshorts(project_dir: Path, fab: Path) -> list[dict]:
    """A fabulam's pshorts, from its `shorts:`: one row per density, the newest of each, `{density, path, at,
    exists, stale}`; `stale` when the fabulam was derived after it."""
    doc = _head.load(fab)
    derived = _when((doc.get("derived") or {}).get("at"))
    rows: dict[str, dict] = {}
    for e in doc.get("shorts") or []:
        if not isinstance(e, dict) or e.get("density") not in DENSITIES:
            continue
        p = fab.parent / str(e.get("path") or "")
        at = _when(e.get("at"))
        rows[e["density"]] = {"density": e["density"], "path": _fj.rel_of(project_dir, p),
                              "at": _macrocosm.jsonable(e.get("at")), "exists": p.is_file(),
                              "stale": bool(derived and at and at < derived)}
    return [rows.get(d) or {"density": d, "path": None, "at": None, "exists": False, "stale": False}
            for d in DENSITIES]


def file_state(project_dir: Path, lean: Path, *, fab: Path | None = None, target: list[str] | None = None) -> dict:
    """Where the fabulam of one Lean file stands, read from disk alone: `{source, fabulam, name, exists, state, line,
    stages: [{name, stage, landed, run, at, model}], landed, of, next, complete, moved, targets, target_by,
    wording, said, said_by, said_at, checking, pshorts}`. `state` is one of the design's seven (`STATE_LINES`), and
    `line` its sentence. `checking` is the `says` of `P:claim/checking`, in full, or None before the survey."""
    lean = Path(lean)
    fab = Path(fab) if fab is not None else fabulam_path(lean)
    doc = _head.load(fab) if fab.is_file() else {}
    exists = doc.get("flavour") == "fabulam"
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    stages = stages_for(src.get("wording"))
    runs = _runs(doc, STAGES) if exists else {}
    landed = [s for s in stages if s in runs]
    k = next((i for i, s in enumerate(stages) if s not in runs), len(stages))
    here = lean.is_file()
    moved = bool(exists and here and src.get("sha256") and src["sha256"] != _sha(lean))
    full = exists and (doc.get("derived") or {}).get("completeness") == "full"
    by_rule = targets_by_rule(lean) if here and not exists else []
    if exists and not here:
        state = "gone"
    elif moved:
        state = "moved"
    elif not exists or k == 0:
        state = "pick" if (len(by_rule) > PICK_PAST and not target) else "none"
    elif full and k == len(stages):
        state = "complete"
    elif k == 1:
        state = "outline"
    else:
        state = "partway"
    nxt = stages[k] if k < len(stages) else None
    if moved or not exists:
        nxt = stages[0]
    checking = next((n.get("says") for n in doc.get("nodes") or [] if isinstance(n, dict)
                     and n.get("id") == "P:claim/checking"), None) if exists else None
    chk = src.get("checking") if isinstance(src.get("checking"), dict) else {}
    line = STATE_LINES[state].format(name=fab.name, n=len(by_rule) if state == "pick" else k, m=len(stages),
                                     next=STAGE_WORDS.get(nxt or "", "the survey"))
    return {"source": _fj.rel_of(project_dir, lean), "fabulam": _fj.rel_of(project_dir, fab), "name": fab.name,
            "exists": exists, "state": state, "line": line,
            "stages": [{"name": s, "stage": STAGE_WORDS[s], "landed": s in landed and not moved,
                        "run": (runs.get(s) or {}).get("run"), "at": _macrocosm.jsonable((runs.get(s) or {}).get("at")),
                        "model": (runs.get(s) or {}).get("model")} for s in stages],
            "landed": 0 if moved else k, "of": len(stages), "next": nxt, "complete": state == "complete",
            "moved": moved, "targets": list(src.get("target") or by_rule), "target_by": src.get("target-by"),
            "wording": src.get("wording"), "said": chk.get("said"), "said_by": chk.get("said-by"),
            "said_at": _macrocosm.jsonable(chk.get("said-at")), "checking": checking,
            "pshorts": pshorts(project_dir, fab) if exists else []}


# ---------------------------------------------------------------------------
# One program: its inputs, its plan, its run, its landing
# ---------------------------------------------------------------------------

def _row(name: str, typ: str, path: Path) -> dict:
    return {"name": name, "type": typ, "path": str(path), "sha256": _digest(path, "folder" if typ == "folder" else
                                                                             None)}


def _work(name: str, doc: dict) -> Path:
    """A fabulam of the catalog alone written under the Thym root, an input of the survey and nothing more."""
    text = _macrocosm.dump(doc)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    folder = _host.host_root() / "fabulam"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}-{sha}.catalog.fabulam.cosm"
    if not path.is_file():
        _fj.write_atomic(path, text)
    return path


def _run_stage(project_dir: Path, prog: Path, checked: Any, stage: str, rows: list[dict], *, words: dict, i: int,
               total: int, mode: str, why: str, route: str, model: str | None, calls: int | None,
               llm_url: str | None, scaffolds: bool, make: Runtime, tally: dict, ceiling: int | None,
               progress: Callable[[dict], Any] | None, should_stop: Callable[[], bool] | None,
               now: dt.datetime | None) -> tuple[Any, dict | None]:
    """One program planned and run. Returns `(the trace, None)` when it landed, `(None, refusal)` when a program
    that asks waits for a model; raises DeriveCancelled on a cancel and RuntimeError when the run is refused."""
    from .thym import plan as _plan
    from .thym import run as _run
    word = words[stage]
    if should_stop is not None and should_stop():
        raise DeriveCancelled(f"cancelled before {word}; nothing of it was written")
    asks = _fj.plan_asks(checked, stage)
    if asks and (mode != "model" or scaffolds):
        plan = _plan.plan(checked, rows, program=stage, inputs_root=project_dir)
        if isinstance(plan, Refusal):
            r: Any = plan
        elif scaffolds:
            r = Refusal("plan", "rules", f"a build by rules writes the outline only (the survey); {stage} asks a "
                                         "model")
        else:
            r = _thym_api.asks_refusal(plan, why, route=route, program=prog)
        refusal = _thym_api.refusal_dict(r) or {"stage": "plan", "check": "rules", "line": None,
                                                "message": f"{stage} asks a model"}
        refusal["program"] = stage
        return None, refusal
    left = None if ceiling is None or not asks else ceiling - tally.get("calls", 0)
    if left is not None and left <= 0:
        return None, {"stage": "run", "check": "calls", "line": None, "program": stage,
                      "message": f"the build reached its ceiling of {ceiling} model calls across the whole job "
                                 f"({tally.get('calls', 0)} made); {stage} did not start"}
    info = None
    if asks:
        plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, program=stage,
                                    inputs_root=project_dir)
    else:
        plan = _plan.plan(checked, rows, program=stage, inputs_root=project_dir)
    if isinstance(plan, Refusal):
        raise RuntimeError(_stopped(word, plan))
    if asks:
        r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
        if r is not None:
            raise RuntimeError(_stopped(word, r))
    if progress is not None:
        progress({"phase": word, "chunk": i + 1, "chunks": total, "message": f"stage {i + 1} of {total}: {word}",
                  "progress": {"stage": word, "program": stage, "n": i + 1, "of": total,
                               "calls": tally.get("calls", 0), "job_at_most": ceiling,
                               "route": route if asks else None}})
    kw = make(stage, plan, info, mode if asks else "rules", False, prog)
    if asks and kw.get("coprocessor") is not None:
        kw["coprocessor"] = _fj.Counting(kw["coprocessor"], tally)
    if left is not None:
        kw["calls"] = left if kw.get("calls") is None else min(kw["calls"], left)
    t = _run.run(plan, inputs_root=project_dir, program=prog, should_stop=should_stop,
                 **({"now": now} if now is not None else {}), **kw)
    if isinstance(t, Refusal):
        raise RuntimeError(_stopped(word, t))
    if not t.landed:
        if t.refusal is not None and t.refusal.check == "cancelled":
            raise DeriveCancelled(f"cancelled during {word}; nothing of it was written")
        raise RuntimeError(_stopped(word, t.refusal))
    return t, None


def _stopped(word: str, r: Any) -> str:
    said = (f"{r.check}, {r.message}" + (f" (line {r.line})" if getattr(r, "line", None) else "")) if r is not None \
        else "refused"
    return f"{word} was refused ({said}); nothing of it was written; the build takes up again from {word}"


def own_errors(text: str, dest: Path) -> list[str]:
    """The errors of a fabulam's own checks (`enough/fabulam.py`, the design's 2.A; `parts-resolve` and
    `statements-agree` among them), read where the fabulam will land, so that a part finds its head and a head its
    parts on disk. A Thym run's `fabula-checks` holds the generic checks; these are the host's to hold."""
    vol = _macrocosm.load_volume_text(text, filename=dest.name)
    if vol.refused is not None:
        return [str(vol.refused)]
    vol.root, vol.catalog_file, vol.path = dest.parent, dest.name, dest
    return [str(p) for p in _fabula.lint(vol).errors]


def _land(t: Any, stage: str, dest: Path, word: str) -> None:
    """A program's output written to the fabulam's file, its run in `derived.runs`; refused, and nothing written,
    when the fabulam's own checks do not hold of it."""
    out = Path(t.outputs[OUTPUT.get(stage, "g")])
    text = _fj.with_run(out.read_text(encoding="utf-8"), _fj._run_entry(t, stage), filename=dest.name)
    errs = own_errors(text, dest)
    if errs:
        said = "; ".join(errs[:3]) + (f" (and {len(errs) - 3} more)" if len(errs) > 3 else "")
        raise RuntimeError(_stopped(word, Refusal("run", "fabula-checks", said)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    _fj.write_atomic(dest, text)


def _make_whole(fab: Path) -> list[str]:
    """The last program has landed: the fabulam says `derived.completeness: full`, when its own checks then hold.
    Returns the errors that stop it (none when it was written)."""
    from . import dialectic as _dl
    before = fab.read_bytes().decode("utf-8")
    twin = _dl.twin_from_text(before, filename=fab.name)
    d = twin.doc.setdefault("derived", {})
    if d.get("completeness") == "full":
        return []
    d["completeness"] = "full"
    text = twin.render()
    errs = own_errors(text, fab)
    if not errs:                                        # else not whole: the fabulam stays as the programs left it
        _fj.write_atomic(fab, text)
    return errs


# ---------------------------------------------------------------------------
# The file job
# ---------------------------------------------------------------------------

def run_file_build(project_dir: Path, lean: Path, *, mode: str, why: str = "", route: str = "local",
                   model: str | None = None, calls: int | None = None, llm_url: str | None = None,
                   scaffolds: bool = False, restart: bool = False, resume_only: bool = False,
                   runtime: Runtime | None = None, complete: Callable | None = None,
                   progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
                   now: dt.datetime | None = None, job_calls: int | None = None, name: str | None = None,
                   target: list[str] | None = None, wording: str | None = None, said: str | None = None,
                   said_by: str | None = None, said_at: str | None = None, obtained: str | None = None,
                   head: Path | None = None, fab: Path | None = None, only_survey: bool = False,
                   tally: dict | None = None) -> dict:
    """The file job's work (blocking): the programs of `decompile-lean.thym` from where the build stands, each
    planned, run and landed in turn. Returns `{source, fabulam, ran: [{stage, program, run, trace}], state,
    complete, refusal?, calls, message}`; raises BuildError before anything runs (a file that is not there, a build
    with nothing to take up again), DeriveCancelled on a cancel (what landed stays) and RuntimeError when a program
    is refused while it runs.

    `target`, `wording`, `said`, `said_by`, `said_at` and `obtained` are the person's entries; one left out keeps
    what the fabulam there before said. `head` and `fab` are the archive job's: the file is a part, surveyed with
    its head, landing at `fab`. `only_survey` stops after the survey (a file the targets do not reach)."""
    project_dir, lean = Path(project_dir), Path(lean)
    if not lean.is_file() or lean.is_symlink():
        raise BuildError(f"no such Lean file: {_fj.rel_of(project_dir, lean)}", 404)
    if lean.suffix != ".lean":
        raise BuildError(f"{lean.name} is no Lean file; a fabulam is built from a .lean file")
    dest = Path(fab) if fab is not None else fabulam_path(lean, name)
    before = _head.load(dest) if dest.is_file() else {}
    state = file_state(project_dir, lean, fab=dest, target=target)
    if state["state"] == "pick" and head is None:
        return {"source": state["source"], "fabulam": state["fabulam"], "ran": [], "state": state,
                "complete": False, "calls": {"made": 0, "at_most": None},
                "refusal": {"stage": "plan", "check": "pick", "line": None, "program": STAGES[0],
                            "message": state["line"]},
                "message": f"{dest.name}: nothing was built; {state['line']}"}
    changed = state["exists"] and _entries_changed(before, target, wording, said, said_by, said_at)
    first = 0 if (restart or not state["exists"] or state["moved"] or changed) else state["landed"]
    if resume_only and (not state["exists"] or state["landed"] == 0 or state["moved"]):
        raise BuildError(f"nothing to take up again: {state['line']}", 409)
    if state["complete"] and not (restart or changed):
        raise BuildError(f"already built: {dest.name} holds every stage; pass restart to build it again", 409)
    prog = program_path()
    checked = _fj._checked(prog)
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    tally = tally if tally is not None else {"calls": 0}
    ceiling = _fj.job_ceiling(calls, job_calls)
    # -- what the survey is given: the head, for a part; else a fabulam of the catalog alone, written by rule
    if head is not None:
        given = Path(head)
        said_wording = (_head.load(given).get("source") or {}).get("wording")
        base = given.parent
    else:
        doc = _head.catalog_alone(lean, fab=dest, name=name, before=before, target=target, wording=wording,
                                  said=said, said_by=said_by, said_at=said_at, obtained=obtained)
        given = _work(dest.name[: -len(SUFFIX)], doc) if first == 0 else dest
        said_wording = doc["source"].get("wording")
        base = dest.parent
    stages = stages_for(said_wording)
    ran: list[dict] = []
    refusal: dict | None = None
    for i in range(first, len(stages)):
        stage = stages[i]
        if only_survey and i > 0:
            break
        if stage == "fit-the-wording":
            wpath = (base / str(said_wording)).resolve()
            has_statement = any(isinstance(n, dict) and str(n.get("id", "")).startswith("C:statement/")
                                for n in _head.load(dest).get("nodes") or [])
            if not wpath.is_file():
                raise RuntimeError(f"fit was refused: the public wording {said_wording} is not there; nothing of it "
                                   "was written; the build takes up again from fit")
            if not has_statement:                       # a part that holds no final theorem has nothing to fit
                rows = None
            else:
                rows = [_row("w", "text", wpath), _row("f", "fabula", dest)]
        elif stage == "survey-the-proof":
            rows = [_row("t", "text", lean), _row("h", "fabula", given)]
        elif stage == "raise-the-questions":
            rows = [_row("f", "fabula", dest)]
        else:
            rows = [_row("t", "text", lean), _row("f", "fabula", dest)]
        if rows is None:
            _skip(dest, stage, now)
            continue
        t, refusal = _run_stage(project_dir, prog, checked, stage, rows, words=STAGE_WORDS, i=i, total=len(stages),
                                mode=mode, why=why, route=route, model=model, calls=calls, llm_url=llm_url,
                                scaffolds=scaffolds, make=make, tally=tally, ceiling=ceiling, progress=progress,
                                should_stop=should_stop, now=now)
        if refusal is not None:
            break
        _land(t, stage, dest, STAGE_WORDS[stage])
        ran.append({"stage": STAGE_WORDS[stage], "program": stage, "run": t.run_id, "trace": str(t.path)})
    final = file_state(project_dir, lean, fab=dest)
    note = ""
    if refusal is None and not only_survey and final["landed"] == final["of"] and not final["complete"]:
        errs = _make_whole(dest)
        if errs:
            refusal = {"stage": "run", "check": "fabula-checks", "line": None, "program": stages[-1],
                       "message": "; ".join(errs[:3]) + (f" (and {len(errs) - 3} more)" if len(errs) > 3 else "")}
        final = file_state(project_dir, lean, fab=dest)
    if refusal is not None:
        note = f"; {refusal['program']} waits: {refusal['message']}"
    said_ran = ", ".join(r["stage"] for r in ran) or "nothing"
    out = {"source": final["source"], "fabulam": final["fabulam"], "ran": ran, "state": final,
           "complete": final["complete"], "calls": {"made": tally.get("calls", 0), "at_most": ceiling},
           "message": (f"{dest.name}: every stage landed" if final["complete"] else
                       f"{dest.name}: {said_ran} landed{note}")}
    if refusal is not None:
        out["refusal"] = refusal
    return out


def _entries_changed(before: dict, target: Any, wording: Any, said: Any, said_by: Any, said_at: Any) -> bool:
    """Whether the person's entries given now differ from what the fabulam there holds: then the survey runs again.
    An entry left out (None) changes nothing."""
    src = before.get("source") if isinstance(before.get("source"), dict) else {}
    chk = src.get("checking") if isinstance(src.get("checking"), dict) else {}
    if target is not None and [str(x) for x in target] != [str(x) for x in src.get("target") or []]:
        return True
    return any(new is not None and str(new) != str(old or "")
               for new, old in ((wording, src.get("wording")), (said, chk.get("said")),
                                (said_by, chk.get("said-by")), (said_at, chk.get("said-at"))))


def _skip(fab: Path, stage: str, now: dt.datetime | None) -> None:
    """A program with nothing to do for this file is recorded as landed, by rule, so the build goes on past it."""
    entry = {"program": stage, "at": _fj._stamp(now), "skipped": "nothing to do: the file holds no final theorem"}
    from . import dialectic as _dl
    twin = _dl.twin_from_text(fab.read_bytes().decode("utf-8"), filename=fab.name)
    twin.doc.setdefault("derived", {}).setdefault("runs", []).append(entry)
    _fj.write_atomic(fab, twin.render())


# ---------------------------------------------------------------------------
# The archive job
# ---------------------------------------------------------------------------

def archive_state(project_dir: Path, folder: Path, *, head: Path | None = None) -> dict:
    """Where the head fabulam of a folder of Lean stands, read from disk alone: `{source, fabulam, name, exists,
    state, line, files, read, unreached, head_line, parts: [{file, fabulam, reached, state}], next, complete,
    moved, targets, checking, pshorts}`. `state` is `none`, `outline` (the survey landed), `partway`, `complete`,
    `moved` (the folder's tree is not the one surveyed) or `gone`."""
    folder = Path(folder)
    head = Path(head) if head is not None else fabulam_path(folder)
    doc = _head.load(head) if head.is_file() else {}
    exists = doc.get("flavour") == "fabulam" and (doc.get("source") or {}).get("kind") == "folder"
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    here = folder.is_dir()
    moved = bool(exists and here and src.get("tree") and src["tree"] != _fj._tree(folder))
    parts = []
    for c in (_head.components(doc) if exists else []):
        pfab = _head.part_path(head, c["file"])
        st = file_state(project_dir, folder / c["file"], fab=pfab)
        parts.append({"file": c["file"], "fabulam": _fj.rel_of(project_dir, pfab), "reached": c["reached"],
                      "state": st["state"], "tied": bool(c["told-in"])})
    runs = _runs(doc, HEAD_STAGES) if exists else {}
    full = exists and (doc.get("derived") or {}).get("completeness") == "full" and "fold-the-head" in runs
    undone = [p for p in parts if (p["reached"] and p["state"] != "complete") or not p["tied"]]
    if exists and not here:
        state = "gone"
    elif moved:
        state = "moved"
    elif not exists:
        state = "none"
    elif full:
        state = "complete"
    elif all(p["state"] in ("none", "outline") and not p["tied"] for p in parts):
        state = "outline"
    else:
        state = "partway"
    nxt = HEAD_STAGES[0] if (not exists or moved) else (undone[0]["file"] if undone else
                                                        (None if full else HEAD_STAGES[1]))
    summ = _head.summary(doc) if exists else {"files": 0, "read": 0, "unreached": 0}
    done = len(parts) - len(undone)
    line = {"none": STATE_LINES["none"].format(name=head.name),
            "outline": STATE_LINES["outline"], "complete": STATE_LINES["complete"],
            "moved": "the folder has changed since its fabulam was surveyed: a build starts again from the survey",
            "gone": "the folder is not there any more; its fabulam stays as it is",
            "partway": f"{done} of {len(parts)} files landed; the build can take up again from {nxt}"}[state]
    checking = next((n.get("says") for n in doc.get("nodes") or [] if isinstance(n, dict)
                     and n.get("id") == "P:claim/checking"), None) if exists else None
    return {"source": _fj.rel_of(project_dir, folder), "fabulam": _fj.rel_of(project_dir, head), "name": head.name,
            "exists": exists, "state": state, "line": line, **summ,
            "head_line": HEAD_LINE.format(k=summ["read"], n=summ["files"], m=summ["unreached"]) if exists else None,
            "parts": parts, "next": nxt, "complete": state == "complete", "moved": moved,
            "targets": list(src.get("target") or []), "checking": checking,
            "pshorts": pshorts(project_dir, head) if exists else []}


def run_archive_build(project_dir: Path, folder: Path, *, mode: str, why: str = "", route: str = "local",
                      model: str | None = None, calls: int | None = None, llm_url: str | None = None,
                      scaffolds: bool = False, restart: bool = False, runtime: Runtime | None = None,
                      complete: Callable | None = None, progress: Callable[[dict], Any] | None = None,
                      should_stop: Callable[[], bool] | None = None, now: dt.datetime | None = None,
                      job_calls: int | None = None, name: str | None = None, target: list[str] | None = None,
                      wording: str | None = None, said: str | None = None, said_by: str | None = None,
                      said_at: str | None = None, obtained: str | None = None) -> dict:
    """The archive job's work (blocking): the folder surveyed, each file's job in the order of the imports with its
    summary copied upward and its part tied in, then the head folded. A file the targets do not reach is surveyed
    and left as an outline. A job that stops takes up again from disk: a part that is whole is not built again.
    Returns `{source, fabulam, ran: [{stage, program, run, trace, file?}], parts: [each file job's result], state,
    complete, refusal?, calls, message}`."""
    project_dir, folder = Path(project_dir), Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise BuildError(f"no such folder: {_fj.rel_of(project_dir, folder)}", 404)
    head = fabulam_path(folder, name)
    before = _head.load(head) if head.is_file() else {}
    state = archive_state(project_dir, folder, head=head)
    if state["complete"] and not restart:
        raise BuildError(f"already built: {head.name} holds every stage; pass restart to build it again", 409)
    prog = program_path(ARCHIVE_FILE)
    checked = _fj._checked(prog)
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    tally: dict = {"calls": 0}
    ceiling = _fj.job_ceiling(calls, job_calls)
    words = {"survey-the-archive": "survey", "fold-the-head": "fold"}
    common = dict(mode=mode, why=why, route=route, model=model, calls=calls, llm_url=llm_url, scaffolds=scaffolds,
                  make=make, tally=tally, ceiling=ceiling, progress=progress, should_stop=should_stop, now=now)
    ran: list[dict] = []
    results: list[dict] = []
    refusal: dict | None = None
    changed = state["exists"] and _entries_changed(before, target, wording, said, said_by, said_at)
    if restart or changed or state["state"] in ("none", "moved"):
        doc = _head.catalog_alone(folder, fab=head, name=name, before=before, target=target, wording=wording,
                                  said=said, said_by=said_by, said_at=said_at, obtained=obtained)
        given = _work(head.name[: -len(SUFFIX)], doc)
        lean = [p for p in sorted(folder.rglob("*.lean")) if p.is_file()]
        if not target and "target" not in doc["source"]:
            found = [t for p in lean for t in targets_by_rule(p)]
            if len(found) > PICK_PAST:
                line = f"this folder ends in {len(found)} results: choose the ones to tell"
                return {"source": state["source"], "fabulam": state["fabulam"], "ran": [], "parts": [],
                        "state": {**state, "state": "pick", "line": line, "targets": found}, "complete": False,
                        "calls": {"made": 0, "at_most": ceiling},
                        "refusal": {"stage": "plan", "check": "pick", "line": None, "program": HEAD_STAGES[0],
                                    "message": line},
                        "message": f"{head.name}: nothing was built; {line}"}
        rows = [_row("repo", "folder", folder), _row("h", "fabula", given)]
        t, refusal = _run_stage(project_dir, prog, checked, HEAD_STAGES[0], rows, words=words, i=0, total=2,
                                **common)
        if refusal is None:
            _land(t, HEAD_STAGES[0], head, "survey")
            ran.append({"stage": "survey", "program": HEAD_STAGES[0], "run": t.run_id, "trace": str(t.path)})
            restart = True                                # the parts of a head surveyed again are built again
    if refusal is None:
        for c in _head.components(_head.load(head)):
            src, part = folder / c["file"], _head.part_path(head, c["file"])
            st = file_state(project_dir, src, fab=part)
            whole = st["state"] == "complete" or (not c["reached"] and st["state"] == "outline")
            if whole and c["told-in"] and not restart:
                continue
            if not (whole and not restart):
                if part.is_file() and not restart:      # its neighbours may have been read since it was surveyed
                    _head.refresh_neighbours(head, part)
                res = run_file_build(project_dir, src, mode=mode, why=why, route=route, model=model, calls=calls,
                                     llm_url=llm_url, scaffolds=scaffolds, restart=restart, runtime=make,
                                     progress=progress, should_stop=should_stop, now=now, job_calls=ceiling,
                                     head=head, fab=part, only_survey=not c["reached"], tally=tally)
                results.append({"file": c["file"], **{k: res[k] for k in ("fabulam", "complete", "message")},
                                **({"refusal": res["refusal"]} if res.get("refusal") else {})})
                ran += [{**r, "file": c["file"]} for r in res["ran"]]
            if part.is_file():
                up = _head.copy_upward(head, part)
                _head.tie_part(head, part)
                if up["moved"]:
                    raise RuntimeError(f"{c['file']} changed since the folder was surveyed ({up['moved'][0]} is not "
                                       "the declaration the head recorded); survey the folder again")
            if results and results[-1].get("refusal") and c["reached"]:
                refusal = results[-1]["refusal"]
                # a part that waits for a model does not stop the outlines of the files after it
                mode = "rules" if refusal.get("check") in ("no-model", "agent-free", "rules") else mode
                if refusal.get("check") not in ("no-model", "agent-free", "rules"):
                    break
    final = archive_state(project_dir, folder, head=head)
    if refusal is None and not final["complete"] and final["exists"] and final["next"] == HEAD_STAGES[1]:
        rows = [_row("repo", "folder", folder), _row("h", "fabula", head)]
        t, refusal = _run_stage(project_dir, prog, checked, HEAD_STAGES[1], rows, words=words, i=1, total=2,
                                **common)
        if refusal is None:
            _land(t, HEAD_STAGES[1], head, "fold")
            _head.stamp_parts(head)
            ran.append({"stage": "fold", "program": HEAD_STAGES[1], "run": t.run_id, "trace": str(t.path)})
        final = archive_state(project_dir, folder, head=head)
    note = f"; {refusal['program']} waits: {refusal['message']}" if refusal is not None else ""
    out = {"source": final["source"], "fabulam": final["fabulam"], "ran": ran, "parts": results, "state": final,
           "complete": final["complete"], "calls": {"made": tally.get("calls", 0), "at_most": ceiling},
           "message": (f"{head.name}: every stage landed; {final['head_line']}" if final["complete"] else
                       f"{head.name}: {final['line']}{note}")}
    if refusal is not None:
        out["refusal"] = refusal
    return out


# ---------------------------------------------------------------------------
# A run whose model is an outside agent, or a person: answers from a folder
# ---------------------------------------------------------------------------

class AnswerFolder:
    """A coprocessor whose model is whoever writes the answers into a folder: an outside agent standing in for the
    model in a calibration run, or a person. Each request has a key, the one Thym gives it (`<node>` or
    `<node>-<k>`), and an attempt, and its answer is the file `<key>.<attempt>.cosm` in the folder: a mapping
    `{engine: model:<name>, output: <the answer, as a block>}` (the shape of a recorded candidate, Thym 12.4), or
    the answer alone as text. When the file is not there the request is written beside it as
    `<key>.<attempt>.request.md` (the system prompt, the user message, and what failed in the answer before) and
    the run is refused, nothing landing; the job takes up again once the answer is written. A job run again finds
    the same keys, so every answer already given is given again and only the next request waits."""

    def __init__(self, folder: Path, *, who: str = "outside-agent", moves: Any = None) -> None:
        from .thym import registry as _registry
        self.folder = Path(folder)
        self.who = who
        self.moves = moves if moves is not None else _registry.MOVES
        self._n = 0

    def complete(self, contract: Any, inputs: Any, *, budget: Any, at: Any = None) -> Any:
        from .thym.coprocessor import candidate
        self._n += 1
        key, attempt = at if at else (str(self._n), 1)
        answer = self.folder / f"{key}.{attempt}.cosm"
        if not answer.is_file():
            request = self.folder / f"{key}.{attempt}.request.md"
            self.folder.mkdir(parents=True, exist_ok=True)
            _fj.write_atomic(request, self.request_text(contract, inputs, answer.name))
            return Refusal("run", "answer-wanted", f"no answer yet for request {key}, attempt {attempt}: the request "
                                                   f"is {request}; write {answer.name} beside it and take the build "
                                                   "up again")
        text = answer.read_text(encoding="utf-8")
        engine, out, tokens = f"model:{self.who}", text, 0
        try:
            data = _macrocosm.yaml_load(text)
        except Exception:  # noqa: BLE001 - an answer that is not a mapping is the answer itself, as text
            data = None
        if isinstance(data, dict) and "output" in data:
            out = data["output"]
            said = str(data.get("engine") or "")
            engine = said if said.startswith("model:") and len(said) > 6 else engine
            tokens = int(data.get("tokens") or 0)
        sch = contract.get("schema") if isinstance(contract, dict) else None
        if isinstance(sch, dict) and sch.get("format") == "yaml" and sch.get("stamp") == "engine" and \
                isinstance(out, str):
            try:
                read = _macrocosm.yaml_load(out)
            except Exception:  # noqa: BLE001 - the runtime says why it cannot be read, and asks again
                read = None
            if isinstance(read, dict):
                out = {**read, "engine": engine}           # as the host's coprocessor does: the footer names it
        return candidate(out, engine=engine, tokens=tokens)

    def request_text(self, contract: Any, inputs: Any, answer_name: str) -> str:
        build = self.moves.prompt(str((contract or {}).get("move")))
        msgs = build(contract, inputs) if build is not None else []
        out = [f"# A request of the move `{(contract or {}).get('move')}`", ""]
        failed = ((contract or {}).get("repair") or {}).get("failed") or []
        for m in msgs:
            out += [f"## {m.get('role')}", "", str(m.get("content") or ""), ""]
        if failed:
            out += ["## what did not hold in the answer before", ""]
            out += [f"- {f.get('name')}: {f.get('why')}" if isinstance(f, dict) else f"- {f}" for f in failed] + [""]
        out += ["## where the answer goes", "",
                f"Write `{answer_name}` beside this file: the two lines `engine: model:{self.who}` and `output: |`, "
                "then the answer, each line two spaces in.", ""]
        return "\n".join(out)


def agent_runtime(project_dir: Path, folder: Path, *, who: str = "outside-agent") -> Runtime:
    """The `runtime` of a build or an entailment whose model is an outside agent or a person (`AnswerFolder`): each
    program's requests and answers sit in `<folder>/<the fabulam's name>/<the program>/`. Hand it to
    `run_file_build`, `run_archive_build` or `run_entail` with `mode="model"`."""
    from .thym.coprocessor import RefusingCoprocessor

    def make(stage: str, plan: dict, info: dict | None, mode: str, scaffolds: bool, program: Any) -> dict:
        rows = [r for r in (plan.get("inputs") or []) if isinstance(r, dict)] if isinstance(plan, dict) else []
        fab = next((Path(str(r.get("path"))).name for r in rows if str(r.get("path", "")).endswith(SUFFIX)
                    and r.get("name") in ("f", "h")), None)
        stem = fab[: -len(SUFFIX)] if fab else "run"
        use = mode == "model" and not scaffolds
        return {"coprocessor": AnswerFolder(Path(folder) / stem / stage, who=who) if use else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if use else {}, "root": _host.host_root(),
                "engines": _host.engines(catalog=_host.catalog_engine(Path(project_dir))), "calls": None}
    return make


# ---------------------------------------------------------------------------
# Entailing: the pshorts
# ---------------------------------------------------------------------------

def pshort_program(density: str) -> str:
    """The program one density runs: `entail f as <density>` alone."""
    if density not in DENSITIES:
        raise BuildError(f"a pshort's density is expert, student or everyone, not {density!r}")
    return ("thym 1\n\nprogram entail-a-pshort\n"
            f"  why: a fabulam entailed as a pshort for {_proof.READERS[density]}.\n"
            "  must: the Lean is never read here; nothing is built or run.\n\n"
            f"  takes f: fabula\n  gives {density}: short\n\n"
            f"  give {density}: entail f as {density}\nend\n")


def run_entail(project_dir: Path, fab: Path, *, density: str | None = None, mode: str, why: str = "",
               route: str = "local", model: str | None = None, calls: int | None = None,
               llm_url: str | None = None, runtime: Runtime | None = None, complete: Callable | None = None,
               progress: Callable[[dict], Any] | None = None, should_stop: Callable[[], bool] | None = None,
               now: dt.datetime | None = None) -> dict:
    """The entailment's work (blocking): the three pshorts of a fabulam (`entail-pshort.thym`), or one density's.
    Each lands beside the fabulam as `<name>.pshort-<density>-<YYYY-MM-DD-HHMM>.md` and is recorded in the fabulam's
    `shorts:` (`density`, `entailed: apart`). Returns `{fabulam, pshorts: [{density, path}], run, trace, model,
    recorded, message}`; raises BuildError for a file that is no whole fabulam, and RuntimeError in the refusal's
    words when the run does not land (no model answers: a pshort has no scaffold)."""
    from .thym import plan as _plan
    from .thym import run as _run
    project_dir, fab = Path(project_dir), Path(fab)
    doc = _head.load(fab) if fab.is_file() else {}
    if doc.get("flavour") != "fabulam":
        raise BuildError(f"{fab.name} is not a fabulam; a pshort is entailed from a fabulam", 404 if not doc else 400)
    if not doc.get("teaching"):
        raise BuildError(f"{fab.name} is an outline; a pshort is entailed once its stages have landed", 409)
    if density is None:
        prog: Any = program_path(PSHORT_FILE)
        checked, source, names = _fj._checked(prog), prog, list(DENSITIES)
    else:
        source = pshort_program(density)
        checked, prog, names = _fj._checked(None, source), source, [density]
    rows = [_row("f", "fabula", fab)]
    if mode != "model":
        plan = _plan.plan(checked, rows, inputs_root=project_dir)
        no = _thym_api.asks_refusal(plan, why, route=route, program=prog) if not isinstance(plan, Refusal) else plan
        raise RuntimeError((no.message if no is not None else "no model answers") + "; a pshort has no scaffold")
    plan, info = _host.plan_for(checked, rows, route=route, model=model, llm_url=llm_url, inputs_root=project_dir)
    if isinstance(plan, Refusal):
        raise RuntimeError(f"the entailment was refused ({plan.check}): {plan.message}")
    r = _host.route_refusal(plan, info, calls=calls, ceiling="calls", program=prog)
    if r is not None:
        raise RuntimeError(r.message)
    make = runtime or _fj.app_runtime(project_dir, why=why, route=route, model=model, calls=calls, complete=complete)
    kw = make("entail", plan, info, "model", False, prog)
    if progress is not None:
        progress({"phase": "entailing", "message": f"entailing {fab.name} as " + ", ".join(names)})
    t = _run.run(plan, inputs_root=project_dir, program=source, should_stop=should_stop,
                 **({"now": now} if now is not None else {}), **kw)
    if isinstance(t, Refusal):
        raise RuntimeError(f"the entailment was refused ({t.check}): {t.message}")
    if not t.landed:
        r = t.refusal
        if r is not None and r.check == "cancelled":
            raise DeriveCancelled("cancelled; nothing was written")
        raise RuntimeError(f"the entailment was refused ({r.check}): {r.message}" if r else "the entailment was "
                                                                                           "refused")
    when = (t.started if isinstance(t.started, dt.datetime) else dt.datetime.now(dt.timezone.utc)).astimezone(
        dt.timezone.utc)
    stamp = when.strftime("%Y-%m-%d-%H%M")
    name = fab.name[: -len(SUFFIX)]
    models = sorted({str(x.get("engine"))[len("model:"):] for x in t.records
                     if str(x.get("engine", "")).startswith("model:")})
    by = ", ".join(models) or "model"
    env = t.environment if isinstance(t.environment, dict) else {}
    pairs: list[tuple[Path, Path]] = []
    entries: list[dict] = []
    out: dict = {"fabulam": _fj.rel_of(project_dir, fab), "run": t.run_id, "trace": str(t.path), "model": by,
                 "pshorts": []}
    for d in names:
        base = _names.pshort_name(name, d, stamp)
        dst = _fj.free_path(fab.parent, base[: -len(".md")], ".md")
        pairs.append((Path(t.outputs[d]), dst))
        entry = {"path": dst.name, "at": when.replace(microsecond=0), "by": by, "mode": "model"}
        if env.get("route") or route:
            entry["route"] = env.get("route") or route
        entry.update({"entailed": "apart", "density": d})
        entries.append(entry)
        out["pshorts"].append({"density": d, "path": _fj.rel_of(project_dir, dst)})
    _thym_api.copy_all(pairs)
    recorded = True
    try:
        text = fab.read_bytes().decode("utf-8")
        for entry in entries:
            text = _fj.record_entry(text, "shorts", entry)
        _fj.write_atomic(fab, text)
    except (OSError, UnicodeDecodeError, BuildError) as e:
        recorded = False
        log.warning("fabulam: wrote the pshorts beside %s but could not record them (%s)", fab.name, e)
    out["recorded"] = recorded
    out["message"] = "wrote " + ", ".join(d.name for _s, d in pairs) + ("" if recorded else
                                                                        f"; {fab.name} could not record them")
    return out


__all__ = ["ARCHIVE_FILE", "AnswerFolder", "DENSITIES", "HEAD_LINE", "HEAD_STAGES", "PROGRAM_FILE", "PSHORT_FILE",
           "STAGES", "STAGE_WORDS", "STATE_LINES", "agent_runtime", "archive_state", "own_errors", "fabulam_path", "file_state", "program_path", "pshort_program",
           "pshorts", "run_archive_build", "run_entail", "run_file_build", "stages_for", "targets_by_rule"]
