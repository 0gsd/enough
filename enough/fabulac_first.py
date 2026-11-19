"""Fabulac-first's helpers as plain functions (0.8, F6: pins section 4, "three doors"): what the routes
(`enough/routes/fabulac.py`), the command line (`python -m enough.fabulac`) and the readvisor's `fabulac` tool all call.

Each function takes the project's folder and a project-relative path (`tally`, or `tally.fabulac.cosm`), does one
thing, and returns plain data (JSON-able, paths relative to the project). A refusal before anything is written raises
`FirstError` with the HTTP status a route answers it with and a sentence for the person.

Only an **authored** fabulac is taken here (its `source.kind` is `authored`): a fabulac decompiled from a folder is
changed through its questions and its code is read, never run (MacroCOSM OES 18.4.7, the run rule).

What runs code: `test` (the entailed tests) and `run` (the tool), both through `enough.sandbox` alone. They block;
the routes run them in a job thread, where Stop and the app's shutdown call `sandbox.stop` / `sandbox.stop_all`. A
service is authored and entailed, and refused at run with the sandbox's sentence (serving comes in a later minor).

What asks a model: `begin` (with `mode: model`), `entail` (only a model writes sources), `take_back` (the read
stage). The functions take the model's `complete` (or a Thym `runtime`) from the caller; `RUNTIME`, when a test sets
it, is used by every entailment and take-back that is given neither.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from . import fabulac_author_job as _aj
from . import fabulac_entail as _fe
from . import fabulac_job as _fj
from . import macrocosm as _mc
from . import sandbox as _sb

#: Where the starters live: one authored fabulac per kind, each passing its checks (`defaults/fabulac-starters/`).
STARTERS = Path(__file__).resolve().parent.parent / "defaults" / "fabulac-starters"
KINDS = ("tool", "library", "service")
ADD_AS = ("requirement", "decision", "case", "interface")
#: A Thym runtime factory every entailment and take-back uses when it is given none (tests set it).
RUNTIME: Callable | None = None
#: What the last test or run of each program gave (the fabulac's resolved path → a summary), for `status`.
LAST_RUNS: dict[str, dict] = {}


class FirstError(_fj.BuildError):
    """A refusal before anything is written, with the HTTP status a route answers it with."""


def _wrap(e: Exception) -> FirstError:
    if isinstance(e, FirstError):
        return e
    if isinstance(e, _fj.BuildError):
        return FirstError(str(e), e.status)
    if isinstance(e, _sb.Refusal):
        return FirstError(e.sentence, 409)
    return FirstError(str(e), 409)


# ---------------------------------------------------------------------------
# Paths and the source kind
# ---------------------------------------------------------------------------

def fabulac_path(project_dir: Path, rel: str) -> Path:
    """The fabulac a request names (`tally` or `tally.fabulac.cosm`), held inside the project; it may not exist."""
    try:
        return _aj.author_path(Path(project_dir), rel)
    except _fj.BuildError as e:
        raise _wrap(e) from None


def authored(project_dir: Path, rel: str) -> Path:
    """The authored fabulac a request names: 404 when there is none, 409 when it was decompiled from a folder."""
    fab = fabulac_path(project_dir, rel)
    if not fab.is_file():
        raise FirstError(f"there is no {fab.name}: begin it first", 404)
    if not _aj.is_authored(fab):
        raise FirstError(f"{fab.name} was decompiled from a folder, not authored: its code is read, never run, and it "
                         "changes through its questions", 409)
    return fab


def _rel(project_dir: Path, p: Path) -> str:
    return _fj.rel_of(Path(project_dir), p)


def _doc(fab: Path) -> dict:
    return _mc.yaml_load(fab.read_text(encoding="utf-8")) or {}


def _program(doc: dict) -> dict:
    p = doc.get("program")
    return dict(p) if isinstance(p, dict) else {}


def _jsonable(v: Any) -> Any:
    return json.loads(json.dumps(_mc.jsonable(v), default=str))


# ---------------------------------------------------------------------------
# Starters
# ---------------------------------------------------------------------------

def starters() -> list[dict]:
    """The starters, one per kind: `[{kind, name, path, line, cases}]`."""
    out = []
    for kind in KINDS:
        for p in sorted((STARTERS / kind).glob("*" + _fj.FABULAC_SUFFIX)):
            doc = _doc(p)
            cases = [n["id"] for n in doc.get("nodes") or [] if isinstance(n, dict)
                     and str(n.get("id", "")).startswith("P:case/")]
            out.append({"kind": kind, "name": doc.get("name"), "path": f"defaults/fabulac-starters/{kind}/{p.name}",
                        "line": (doc.get("atem") or {}).get("line"), "cases": cases})
    return out


def _starter(kind: str) -> Path:
    if kind not in KINDS:
        raise FirstError(f"a starter is tool, library or service, not {kind!r}")
    found = sorted((STARTERS / kind).glob("*" + _fj.FABULAC_SUFFIX))
    if not found:
        raise FirstError(f"no {kind} starter is installed", 404)
    return found[0]


def from_starter(kind: str, name: str, *, licence: str | None = None, by: str | None = None,
                 now: dt.datetime | None = None) -> str:
    """A starter's text made the person's: its name (every whole word of it, so a command's own words follow), the
    catalog's `id` and the module it starts as; the day; who authored it and the licence when given."""
    from .thym.moves import author as _author
    src = _starter(kind)
    old = _doc(src)
    old_name = str(old.get("name"))
    text = src.read_text(encoding="utf-8")
    if name != old_name:
        text = re.sub(rf"(?<![\w-]){re.escape(old_name)}(?![\w-])", name, text)
    doc = _mc.yaml_load(text)
    at = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    stamp = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["id"] = f"fabula/{_author.slug(name, 80)}"
    doc["name"] = name
    prog = _program(doc)
    if prog.get("start"):
        prog["start"] = ["-m", _author.module_name(name)]
    doc["program"] = prog
    src_block = dict(doc.get("source") or {})
    src_block["at"] = stamp[:10]
    derived = dict(doc.get("derived") or {})
    derived["at"] = stamp
    derived["by"] = "person"
    doc["derived"] = derived
    for n in doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "R:maker/author" and by and by.strip():
            n["name"] = by.strip()
            n["summary"] = f"{by.strip()} authored {name}."
        if n.get("id") == "R:licence/licence":
            if licence and licence.strip():
                n["identifier"] = licence.strip()
            if by and by.strip():
                n["summary"] = f"The terms {by.strip()} offers {name} on."
    if licence and licence.strip():
        src_block["licence"] = licence.strip()
    doc["source"] = src_block
    return _mc.dump(json.loads(json.dumps(doc)))


# ---------------------------------------------------------------------------
# Authoring
# ---------------------------------------------------------------------------

def folder_there(project_dir: Path, fab: Path) -> None:
    """A program is begun in a folder that is there; none is made for it. Refused in words (404) otherwise: 0.8, W4-X7
    (W4-FP found a bare FileNotFoundError from the atomic write, by rules and from a starter alike)."""
    if not fab.parent.is_dir():
        raise FirstError(f"there is no folder {_rel(project_dir, fab.parent)}/ to begin {fab.name} in: make the folder "
                         "first, or begin it in one that is there", 404)


def begin(project_dir: Path, rel: str, *, kind: str = "tool", licence: str | None = None, brief: str | None = None,
          by: str | None = None, starter: str | None = None, mode: str = "rules", **kw: Any) -> dict:
    """Begin an authored fabulac, or take one up again. From a starter (`starter: tool | library | service`): the
    starter copied under the program's name, at once. Else the authoring job (`fabulac_author_job.run_author`): the
    catalog and the first stage's questions, or, when it is there, what is next (settle the answers, raise the next
    stage). Blocking; `kw` is the job's (`complete`, `runtime`, `progress`, `should_stop`, `now`, …)."""
    project_dir = Path(project_dir)
    fab = fabulac_path(project_dir, rel)
    folder_there(project_dir, fab)
    if starter:
        if fab.exists():
            raise FirstError(f"{fab.name} is there already; take it up again, or choose another name", 409)
        folder = _fj.folder_of(fab)
        if folder is not None and folder.exists():
            raise FirstError(f"{folder.name}/ is there already and has no fabulac: choose another name", 409)
        name = folder.name if folder is not None else fab.name
        _fj.write_atomic(fab, from_starter(starter, name, licence=licence, by=by, now=kw.get("now")))
        st = status(project_dir, _rel(project_dir, fab))
        return {"fabulac": _rel(project_dir, fab), "starter": starter, "state": st["interview"],
                "complete": st["interview"]["complete"], "waiting": st["interview"]["shown"],
                "message": f"{fab.name} begun from the {starter} starter: change it to say your program, then entail"}
    if kind not in KINDS:
        raise FirstError(f"a program is a tool, a library or a service, not {kind!r}")
    allowed = {k: v for k, v in kw.items() if k in ("why", "route", "model", "calls", "llm_url", "runtime", "complete",
                                                     "progress", "should_stop", "now")}
    try:
        return _jsonable(_aj.run_author(project_dir, _rel(project_dir, fab), kind=kind, brief=brief, licence=licence,
                                        by=by, mode=mode, **allowed))
    except _fj.BuildError as e:
        raise _wrap(e) from None


def answer(project_dir: Path, rel: str, answers: Any, *, through: str = "person", who: str | None = None) -> dict:
    """A sitting: the person's answers to the questions shown (`[{question, says}]`, or `unknown`/`declined`/`skip`
    flags), written beside the fabulac; `begin` again settles them and raises what follows."""
    fab = authored(project_dir, rel)
    try:
        return _jsonable(_aj.answer(Path(project_dir), _rel(project_dir, fab), answers, through=through, who=who))
    except Exception as e:  # noqa: BLE001 - the dialectic's refusals carry their words
        raise FirstError(str(e), getattr(e, "status", 422)) from None


def add(project_dir: Path, rel: str, *, as_: str, says: str, fields: dict | None = None) -> dict:
    """The `add` move as one call: the person's sentence as a new requirement, decision, case or interface (`as`), in
    their words (`summary`), `stance: axiom`, `provenance.mode: manual`; `fields` sets fields of it as data (a
    requirement's `force` and `checked-by`, a case's `of`, `given`, `expect`, an interface's `surface` and
    `signature`); what is required and not given is left `{pending: …}` for the interview."""
    from . import dialectic as _dl
    from .thym.moves import author as _author
    fab = authored(project_dir, rel)
    word = str(as_ or "").strip().lower()
    if word not in ADD_AS:
        raise FirstError(f"add writes a requirement, a decision, a case or an interface, not {as_!r}")
    said = _author.fold(str(says or ""))
    if not said:
        raise FirstError("add needs the sentence to write: the person's own words")
    if fields is not None and not isinstance(fields, dict):
        raise FirstError("fields is a mapping of the item's fields")
    twin = _dl.open_twin(fab)
    nodes = twin.doc.get("nodes") if isinstance(twin.doc.get("nodes"), list) else []
    mod, kind = _author.ADD_KINDS[word]
    taken = {str(n.get("id")) for n in nodes if isinstance(n, dict)}
    item = _author.make_item(mod, kind, said, taken=taken, asks=_author.ADD_ASKS, sets=dict(fields or {}),
                             provenance={"mode": "manual", "sources": ["the author, in their own words"],
                                         "confidence": 1})
    nodes.append(item)
    twin.doc["nodes"] = nodes
    _fj.write_atomic(fab, twin.render())
    return {"fabulac": _rel(project_dir, fab), "added": item["id"], "item": _jsonable(item),
            "message": f"added {item['id']} to {fab.name}"}


def check(project_dir: Path, rel: str) -> dict:
    """The fabulac's checks (`fabula.lint`: errors and warnings), the requirements of force *must* no case shows
    (`uncovered`), what the authored source lacks, and, once entailed, whether the entailment is in step."""
    fab = authored(project_dir, rel)
    out = _aj.check(Path(project_dir), _rel(project_dir, fab))
    ent = _fe.step_state(fab) if _fe.entailed_path(fab).is_dir() or _doc(fab).get("entailed") else None
    out["entailment"] = None if ent is None else {k: ent[k] for k in ("entailed", "moved", "edited", "gone", "new",
                                                                      "kept", "tell")}
    return _jsonable(out)


def status(project_dir: Path, rel: str) -> dict:
    """Where an authored fabulac stands: the interview (`author_state`), its program, its entailment file by file
    (`step_state`, once entailed), and the last test or run."""
    fab = authored(project_dir, rel)
    doc = _doc(fab)
    ent = _fe.step_state(fab, doc) if doc.get("entailed") or _fe.entailed_path(fab).is_dir() else None
    return _jsonable({"fabulac": _rel(project_dir, fab), "name": doc.get("name"), "program": _program(doc),
                      "interview": _aj.author_state(Path(project_dir), fab), "entailment": ent,
                      "last_run": LAST_RUNS.get(str(fab.resolve()))})


def moved(project_dir: Path, rel: str) -> dict:
    """What moved since the last entailment, and every file changed by hand, file by file (`step_state`)."""
    fab = authored(project_dir, rel)
    st = _fe.step_state(fab)
    st["fabulac"] = _rel(project_dir, fab)
    return _jsonable(st)


# ---------------------------------------------------------------------------
# Entailing and keeping in step
# ---------------------------------------------------------------------------

def _model_kw(kw: dict) -> dict:
    out = {k: v for k, v in kw.items() if k in ("why", "route", "model", "calls", "llm_url", "runtime", "complete",
                                                 "progress", "should_stop", "now")}
    if out.get("runtime") is None and RUNTIME is not None:
        out["runtime"] = RUNTIME
    return out


def entail(project_dir: Path, rel: str, *, overwrite: Iterable[str] = (), mode: str = "model", **kw: Any) -> dict:
    """Entail the fabulac as its program: `<name>/` beside it (`fabulac_entail.run_entail`). Done again, only what
    moved is told again. A file changed by hand refuses it (409, named) unless it is in `overwrite`, kept or taken
    back. Only a model writes sources: agent-free is refused (409). Blocking."""
    fab = authored(project_dir, rel)
    try:
        out = _fe.run_entail(Path(project_dir), fab, mode=mode, overwrite=list(overwrite or ()), **_model_kw(kw))
    except _fj.BuildError as e:
        raise _wrap(e) from None
    return _jsonable({**out, "fabulac": _rel(project_dir, fab)})


def keep(project_dir: Path, rel: str, files: Iterable[str], *, because: str | None = None,
         by: str = "the person") -> dict:
    """Keep files changed by hand: a recorded decision each; never asked or written again until let go."""
    fab = authored(project_dir, rel)
    try:
        return _jsonable(_fe.keep(Path(project_dir), fab, list(files), because=because, by=by))
    except _fj.BuildError as e:
        raise _wrap(e) from None


def let_go(project_dir: Path, rel: str, files: Iterable[str]) -> dict:
    """Let kept files go: the next entailment tells them again."""
    fab = authored(project_dir, rel)
    try:
        return _jsonable(_fe.let_go(Path(project_dir), fab, list(files)))
    except _fj.BuildError as e:
        raise _wrap(e) from None


def take_back(project_dir: Path, rel: str, file: str, *, read: Callable | None = None, **kw: Any) -> dict:
    """Take a hand edit back into the fabulac: the file read as the read stage reads one (a model), and what it adds
    or changes put to the person as questions (`take it back` / `leave it out`). Blocking."""
    fab = authored(project_dir, rel)
    try:
        return _jsonable(_fe.take_back(Path(project_dir), fab, str(file), read=read, **_model_kw(
            {k: v for k, v in kw.items() if k not in ("progress", "should_stop")})))
    except _fj.BuildError as e:
        raise _wrap(e) from None


# ---------------------------------------------------------------------------
# The head
# ---------------------------------------------------------------------------

def head(project_dir: Path, rel: str, parts: Iterable[str], *, name: str | None = None, licence: str | None = None,
         by: str | None = None, does: dict | None = None) -> dict:
    """Make a head fabulac over parts (`fabulac_head.make_head`): one component per part, and `head` set in each."""
    from . import fabulac_head as _fh
    project_dir = Path(project_dir)
    hp = fabulac_path(project_dir, rel)
    paths = [fabulac_path(project_dir, p) for p in parts or ()]
    if not paths:
        raise FirstError("a head names its parts: the part fabulacs, one or more")
    for p in paths:
        if not p.is_file():
            raise FirstError(f"there is no {p.name}", 404)
    try:
        out = _fh.make_head(hp, paths, name=name, licence=licence, by=by, does=does)
    except FileExistsError:
        raise FirstError(f"{hp.name} is there already", 409) from None
    except ValueError as e:
        raise FirstError(str(e), 409) from None
    return _jsonable({**out, "head": _rel(project_dir, hp),
                      "parts": [_rel(project_dir, p) for p in paths]})


def parts_moved(project_dir: Path, rel: str) -> dict:
    """Which parts of a head moved (`fabulac_head.parts_moved`)."""
    from . import fabulac_head as _fh
    hp = fabulac_path(project_dir, rel)
    if not hp.is_file():
        raise FirstError(f"there is no {hp.name}", 404)
    return _jsonable({**_fh.parts_moved(hp), "head": _rel(project_dir, hp)})


# ---------------------------------------------------------------------------
# Running: the sandbox alone
# ---------------------------------------------------------------------------

def prepare(project_dir: Path, rel: str, *, what: str, root: Path | None = None) -> tuple[Path, _sb.Run]:
    """The sandbox run of an authored fabulac's entailment (`what`: tests or tool), refused before anything is copied
    when enough will not run it: not authored (read, never run), not entailed, a service (serving comes in a later
    minor), a library started as a tool, a need outside the standard library. Only `standard-library` is offered."""
    fab = authored(project_dir, rel)
    doc = _doc(fab)
    prog = _program(doc)
    name = str(doc.get("name") or fab.name)
    if prog.get("kind") == "service":
        raise FirstError(_sb.SERVING_LATER.format(name=name), 409)
    if what == "tool" and prog.get("kind") != "tool":
        raise FirstError(f"{name} is a {prog.get('kind') or 'program'}, not a tool: there is nothing to start; run its "
                         "tests instead", 409)
    folder = _fe.entailed_path(fab)
    if not folder.is_dir() or not doc.get("entailed"):
        raise FirstError(f"{name} is not entailed yet: entail it first", 409)
    src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    try:
        run = _sb.prepare(folder, source_kind=str(src.get("kind") or ""), root=root)
    except _sb.Refusal as e:
        raise FirstError(e.sentence, 409) from None
    return fab, run


def _hand_over(project_dir: Path, paths: Iterable[str]) -> list[Path]:
    out = []
    for raw in paths or ():
        try:
            p = _fj.project_path(Path(project_dir), str(raw), what="file to hand over")
        except _fj.BuildError as e:
            raise _wrap(e) from None
        if not p.exists():
            raise FirstError(f"there is no {raw} to hand over", 404)
        out.append(p)
    return out


def args_for(args: Iterable[str], hand_over: Iterable[str], given: Iterable[Path]) -> list[str]:
    """The tool's arguments, an argument that names a handed-over file as the person gave it (`notes.md`) put as
    the path the sandbox knows it by, so it reaches the read-only copy."""
    names = {str(raw): str(p) for raw, p in zip(hand_over or (), given or ())}
    return [names.get(str(a), str(a)) for a in args or ()]


def _summary(what: str, res: _sb.Result) -> dict:
    d = res.as_dict()
    d["ok"] = res.exit_code == 0 and not res.stopped_by
    if what == "tests":
        m = re.search(r"Ran (\d+) tests?", res.stderr or "")
        d["ran"] = int(m.group(1)) if m else None
    d["message"] = ((f"stopped: {res.stopped}" if res.stopped_by else
                     ("the tests passed" if d["ok"] else "the tests failed") if what == "tests" else
                     f"the tool exited with {res.exit_code}")
                    + ("" if res.enforced else "; the box did not hold this run"))
    return d


def execute(project_dir: Path, fab: Path, run: _sb.Run, *, what: str, args: Iterable[str] = (), stdin: str = "",
            hand_over: Iterable[Path] = (), should_stop: Callable[[], bool] | None = None,
            limits: _sb.Limits = _sb.Limits()) -> dict:
    """Run a prepared sandbox run (blocking): the tests, or the tool with its arguments; a watcher stops it when
    `should_stop` says so (the job's Stop). Returns the sandbox's result with `ok`, `message`, `fabulac`, `run`."""
    import threading
    done = threading.Event()

    def watch() -> None:
        while not done.wait(0.1):
            if should_stop is not None and should_stop():
                _sb.stop(run.run_id)
                return
    if should_stop is not None:
        threading.Thread(target=watch, name=f"sandbox-stop-{run.run_id}", daemon=True).start()
    try:
        if what == "tests":
            res = _sb.run_tests(run, limits=limits)
        else:
            res = _sb.run_tool(run, list(args), stdin=str(stdin or "").encode("utf-8"),
                               handed_over=list(hand_over), limits=limits)
    except _sb.Refusal as e:
        raise FirstError(e.sentence, 409) from None
    finally:
        done.set()
        _sb.discard(run)                # the result is read and the run is over: its folder goes (unless kept)
    out = _summary(what, res)
    out["fabulac"] = _rel(project_dir, fab)
    out["run"] = run.run_id
    LAST_RUNS[str(fab.resolve())] = {k: out[k] for k in ("what", "run", "ok", "exit_code", "message", "wall_time",
                                                          "stopped_by", "enforced") if k in out} | (
        {"ran": out.get("ran")} if what == "tests" else {})
    return _jsonable(out)


def test(project_dir: Path, rel: str, *, should_stop: Callable[[], bool] | None = None,
         root: Path | None = None) -> dict:
    """The entailed tests, in the sandbox (blocking)."""
    fab, run = prepare(project_dir, rel, what="tests", root=root)
    return execute(project_dir, fab, run, what="tests", should_stop=should_stop)


def run(project_dir: Path, rel: str, args: Iterable[str] = (), *, stdin: str = "", hand_over: Iterable[str] = (),
        should_stop: Callable[[], bool] | None = None, root: Path | None = None) -> dict:
    """The tool with its arguments, in the sandbox (blocking); files handed over are copied in, read-only."""
    given = _hand_over(project_dir, hand_over)
    fab, r = prepare(project_dir, rel, what="tool", root=root)
    return execute(project_dir, fab, r, what="tool", args=args_for(args, hand_over, given), stdin=stdin,
                   hand_over=given,
                   should_stop=should_stop)


def stop(run_id: str) -> dict:
    """Stop a sandbox run by its id (from any thread)."""
    return {"run": run_id, "stopped": bool(_sb.stop(str(run_id)))}


def stop_all() -> None:
    """Every sandbox run stopped: the app's shutdown."""
    _sb.stop_all()


__all__ = ["ADD_AS", "FirstError", "KINDS", "LAST_RUNS", "RUNTIME", "STARTERS", "add", "answer", "authored", "begin",
           "check", "entail", "execute", "fabulac_path", "folder_there", "from_starter", "head", "keep", "let_go", "moved",
           "parts_moved", "prepare", "run", "starters", "status", "stop", "stop_all", "take_back", "test"]
