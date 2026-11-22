"""The fabulam's routes (0.9; pins section 10; the design's 6): `/api/fabulam/*`, thin wrappers over the entry
functions of `enough/fabulam_job.py` (`file_state`, `run_file_build`, `archive_state`, `run_archive_build`,
`run_entail`), and nothing else of the fabulam's.

- `GET  /api/fabulam/state?path=` where the fabulam of a `.lean` file, a folder of them, or a `.fabulam.cosm`
  stands, read from disk alone, and the job running for it, if any.
- `POST /api/fabulam/build` a build as a job (kind `fabulam`): the survey by rule, then the stages that ask a model.
  It also takes a stopped build up again. A file that ends in more than three results and names no `target` builds
  nothing: the answer says so and lists them (`pick`), with no job.
- `POST /api/fabulam/resume` the same build, only when there is something to take up again.
- `POST /api/fabulam/entail` a fabulam's pshorts as a job, all three densities or one (`density`). With no model the
  route refuses before a job starts, in the entailment's own words: a pshort has no scaffold.
- `POST /api/fabulam/cancel` the job running for that source.

The person's entries reach the build as its arguments (`target`, `wording`, `said`, `said_by`, `said_at`,
`obtained`, `name`): the card's two fields write what is said about checking and who says it, and the public
wording's file, through the job and never through a model. A changed entry starts the build again from the survey.

A build runs as a fabulac's does: a CanonJob in the background with its progress, and after a restart of the app it
takes up again from disk while the Lean file's sha256 is the one the fabulam recorded. Nothing of Lean is installed,
built or run here. Every POST sits behind the promise header (`api_promise.MODEL_RUN_PREFIXES`) and the Origin gate.

`router.start(do, body)` is what the readvisor's `fabulam` tool starts through: the same code as the routes."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from .. import canon_tools as _canon_tools
from .. import fabulac_job as _fj
from .. import fabulam_job as _J
from .. import fabulam_head as _head
from .. import thym_host as _host
from ..fabulac_job import BuildError
from ..thym.moves import proof as _proof
from .common import AppContext
from .fabulac import decide_mode, route_of

JOB_KIND = "fabulam"
PARTS_MARK = ".fabulam.parts/"
DOES = ("build", "resume", "entail", "status", "cancel")


# ---------------------------------------------------------------------------
# What a request's path names
# ---------------------------------------------------------------------------

def target_of(project_dir: Path, rel: str) -> dict:
    """`{kind: file | folder, source, fab, rel, key, part}` for a request's `path`: a `.lean` file, a folder of them,
    or a `.fabulam.cosm` (its source read from its own `source.path`). Held inside the project, no link on the way.
    `fab` is None when the default place is meant (`fabulam_job.fabulam_path`). Raises BuildError (status, words)."""
    project_dir = Path(project_dir)
    raw = _canon_tools.tidy_rel(str(rel or ""))
    if not raw:
        raise BuildError("missing path: a .lean file, a folder of them, or a .fabulam.cosm")
    if _canon_tools.store_prefix(raw):
        raise BuildError("a fabulam is built from Lean in the project, not from the Canon store")
    p = _fj.project_path(project_dir, raw)
    fab: Path | None = None
    part = PARTS_MARK in (raw + "/")
    if p.name.endswith(_J.SUFFIX):
        if not p.is_file():
            raise BuildError(f"no such fabulam: {raw}", 404)
        doc = _head.load(p)
        if doc.get("flavour") != "fabulam":
            raise BuildError(f"{p.name} is not a fabulam")
        src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
        spath = str(src.get("path") or "").rstrip("/")
        if not spath:
            raise BuildError(f"{p.name} names no source")
        fab = p
        whole = Path(os.path.normpath(p.parent.absolute() / spath))       # a part names its file from below the head
        source = _fj.project_path(project_dir, _fj.rel_of(project_dir.absolute(), whole))
        kind = "folder" if src.get("kind") == "folder" else "file"
    else:
        source = p
        if p.is_symlink():
            raise BuildError(f"{p.name} is a link; nothing is read through a link")
        if p.is_dir():
            if not any(x.is_file() for x in p.rglob("*.lean")):
                raise BuildError(f"{p.name}/ holds no Lean file; a fabulam is built from .lean files")
            kind = "folder"
        elif p.suffix == ".lean":
            kind = "file"
            if not p.is_file() and not _J.fabulam_path(p).is_file():
                raise BuildError(f"no such Lean file: {raw}", 404)
        elif not p.exists():
            raise BuildError(f"no such file or folder: {raw}", 404)
        else:
            raise BuildError(f"{p.name} is no Lean file; a fabulam is built from a .lean file, a folder of them, or "
                             "its .fabulam.cosm")
    return {"kind": kind, "source": source, "fab": fab, "rel": _fj.rel_of(project_dir, source),
            "key": "fabulam:" + str(source.resolve()), "part": part}


def state_of(project_dir: Path, t: dict) -> dict:
    """Where the fabulam stands (M3's `file_state` or `archive_state`), with `kind` said."""
    if t["kind"] == "folder":
        st = _J.archive_state(project_dir, t["source"], **({"head": t["fab"]} if t["fab"] is not None else {}))
    else:
        st = _J.file_state(project_dir, t["source"], **({"fab": t["fab"]} if t["fab"] is not None else {}))
    return {**st, "kind": t["kind"], "part": bool(t.get("part"))}


def band_refusal(t: dict) -> str | None:
    """The band's words (`thym.moves.proof`), said before a job starts: sixty files, twelve thousand lines."""
    src = Path(t["source"])
    files = [src] if t["kind"] == "file" else [x for x in sorted(src.rglob("*.lean")) if x.is_file()]
    if len(files) > _proof.BAND_FILES:
        return "more than sixty Lean files: past what this build reads"
    lines = 0
    for f in files:
        try:
            lines += f.read_text(encoding="utf-8-sig", errors="replace").count("\n")
        except OSError:
            continue
    if lines > _proof.BAND_LINES:
        return "more than twelve thousand lines of Lean: past what this build reads"
    return None


def folder_pick(project_dir: Path, t: dict, target: list[str] | None) -> list[str] | None:
    """A folder whose head names no target, given none: the final theorems the rule finds across its files when they
    are more than three (the archive job's own condition), else None."""
    if target:
        return None
    head = t["fab"] or _J.fabulam_path(t["source"])
    if head.is_file() and (_head.load(head).get("source") or {}).get("target"):
        return None
    found = [x for p in sorted(Path(t["source"]).rglob("*.lean")) if p.is_file() for x in _J.targets_by_rule(p)]
    return found if len(found) > _J.PICK_PAST else None


def _targets(v: Any) -> list[str] | None:
    if v is None or v == "":
        return None
    if isinstance(v, str):
        got = [w.strip() for w in v.replace("\n", ",").split(",") if w.strip()]
        return got or None
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return [x.strip() for x in v if x.strip()] or None
    raise HTTPException(400, "target is the full name of a final theorem, or a list of them")


def _entry(body: dict, key: str) -> str | None:
    v = body.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise HTTPException(400, f"{key} is a sentence")
    return v.strip() or None


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------

def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    project_dir = Path(ctx.project_dir)
    jobs = ctx.canon_jobs
    start_job = ctx._start_canon_job
    canon_mode = ctx._canon_mode
    model_complete = ctx._model_complete
    catalog_after = ctx._canon_catalog_after
    llm_url = ctx.session.llm_url

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise HTTPException(400, "the body is a JSON object")
        return body

    async def resolved(rel: Any) -> dict:
        try:
            return await asyncio.to_thread(target_of, project_dir, str(rel or ""))
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None

    def complete_for(route: str, model: str | None) -> Callable[..., Any]:
        from .. import llm as _llm
        if route == "local" and _llm._current_slot() != "opro-api":
            return model_complete
        return _host.route_complete(route, model=model, llm_url=llm_url, project_dir=project_dir)

    def job_kw(route: str | None, **more: Any) -> dict:
        kw = {"route": route} if _host._accepts(start_job, {"route": route}) else {}
        for k, v in more.items():
            if v is not None and _host._accepts(start_job, {k: v}):
                kw[k] = v
        return kw

    def after(rel: str) -> None:
        try:
            catalog_after(rel)
        except Exception:  # noqa: BLE001 - a catalog is never worth a failed job
            pass

    def running(t: dict) -> str | None:
        return jobs.running_for(t["key"]) if jobs is not None else None

    async def start_build(body: dict, *, resume_only: bool = False) -> dict:
        route, model, calls = route_of(body)
        job_calls = body.get("job_calls")
        if job_calls is not None and (isinstance(job_calls, bool) or not isinstance(job_calls, int) or job_calls < 1):
            raise HTTPException(400, f"job_calls is a ceiling of at least 1 model call, not {job_calls!r}")
        t = await resolved(body.get("path"))
        if t["part"]:
            raise HTTPException(409, "a part is built with its head: build the folder, or its head fabulam")
        target = _targets(body.get("target"))
        entries = {k: _entry(body, k) for k in ("wording", "said", "said_by", "said_at", "obtained", "name")}
        restart = bool(body.get("restart"))
        state = await asyncio.to_thread(state_of, project_dir, t)
        if state["state"] == "gone":
            raise HTTPException(404, state["line"])
        too_big = await asyncio.to_thread(band_refusal, t)
        if too_big:
            raise HTTPException(413, too_big)
        if resume_only and (not state["exists"] or state["moved"] or state["state"] in ("none", "pick")
                            or (t["kind"] == "file" and not state.get("landed"))):
            raise HTTPException(409, f"nothing to take up again: {state['line']}")
        # A file (or folder) that ends in more than three results, given no target: nothing is built.
        pick =(list(state.get("targets") or []) if t["kind"] == "file" and state["state"] == "pick" and not target
                else (await asyncio.to_thread(folder_pick, project_dir, t, target) if t["kind"] == "folder"
                      and state["state"] in ("none", "moved") else None))
        if pick:
            line = (state["line"] if t["kind"] == "file"
                    else f"this folder ends in {len(pick)} results: choose the ones to tell")
            return {"job": None, "state": {**state, "state": "pick", "line": line, "targets": pick},
                    "targets": pick, "refusal": {"stage": "plan", "check": "pick", "line": None, "message": line},
                    "message": f"nothing was built; {line}"}
        if state["complete"] and not restart and not (target or any(entries[k] for k in
                                                                     ("wording", "said", "said_by", "said_at"))):
            raise HTTPException(409, f"already built: {state['name']} holds every stage; pass restart to build it "
                                     "again")
        mode, why = await decide_mode(canon_mode, body, route)
        scaffolds = str(body.get("mode") or "").strip().lower() == "rules"
        complete = complete_for(route, model) if mode == "model" and not scaffolds else None
        rel = t["rel"]
        kw = dict(mode=mode, why=why, route=route, model=model, calls=calls, llm_url=llm_url, scaffolds=scaffolds,
                  restart=restart, complete=complete, job_calls=job_calls, target=target, **entries)

        def work(jctx: Any) -> dict:
            prog = dict(progress=lambda f: jctx.progress(f), should_stop=jctx.should_stop)
            if t["kind"] == "folder":
                out = _J.run_archive_build(project_dir, t["source"], **kw, **prog)
            else:
                out = _J.run_file_build(project_dir, t["source"], resume_only=resume_only, **kw, **prog,
                                        **({"fab": t["fab"]} if t["fab"] is not None else {}))
            after(out.get("fabulam") or rel)
            return out

        name = Path(t["source"]).name + ("/" if t["kind"] == "folder" else "")
        doing = (f"taking up the fabulam of {name} from {state.get('next') or 'the survey'}"
                 if state["exists"] and not state["moved"] and not restart and state.get("landed")
                 else f"building the fabulam of {name}")
        snap = start_job(kind=JOB_KIND, path=rel, mode=mode, why=why if not scaffolds else "", work=work,
                         key=t["key"], doing=doing + (" on the cloud" if mode == "model" and route == "cloud" else ""),
                         **job_kw(route if mode == "model" else None, flavour="fabulam"))
        return {**snap, "state": state}

    async def start_entail(body: dict) -> dict:
        route, model, calls = route_of(body)
        density = body.get("density")
        if density in ("", None):
            density = None
        elif density not in _J.DENSITIES:
            raise HTTPException(400, f"density is expert, student or everyone, not {density!r}")
        t = await resolved(body.get("path"))
        state = await asyncio.to_thread(state_of, project_dir, t)
        if not state["exists"]:
            raise HTTPException(404, f"no fabulam yet: {state['line']}")
        fab = project_dir / state["fabulam"]
        mode, why = await decide_mode(canon_mode, body, route)
        if mode != "model":
            # No model answers: the entailment refuses in its own words, and nothing starts.
            try:
                await asyncio.to_thread(_J.run_entail, project_dir, fab, density=density, mode=mode, why=why,
                                        route=route)
            except BuildError as e:
                raise HTTPException(e.status, str(e)) from None
            except RuntimeError as e:
                raise HTTPException(409, str(e)) from None
            raise HTTPException(409, "no model answers; a pshort has no scaffold")
        try:
            doc = await asyncio.to_thread(_head.load, fab)
        except Exception:  # noqa: BLE001 - an unreadable fabulam is refused by the entailment's own check
            doc = {}
        if not doc.get("teaching"):
            raise HTTPException(409, f"{fab.name} is an outline; a pshort is entailed once its stages have landed")
        complete = complete_for(route, model)
        rel = state["fabulam"]

        def work(jctx: Any) -> dict:
            out = _J.run_entail(project_dir, fab, density=density, mode=mode, why=why, route=route, model=model,
                                calls=calls, llm_url=llm_url, complete=complete,
                                progress=lambda f: jctx.progress(f), should_stop=jctx.should_stop)
            after(rel)
            return out

        said = density or "expert, student and everyone"
        snap = start_job(kind=JOB_KIND, path=rel, mode=mode, why=why, work=work, key=t["key"],
                         doing=f"entailing {fab.name} as {said}" + (" on the cloud" if route == "cloud" else ""),
                         **job_kw(route, flavour="fabulam", what="pshort"))
        return {**snap, "state": state}

    def cancel_body(body: dict) -> dict:
        try:
            t = target_of(project_dir, str(body.get("path") or ""))
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None
        jid = running(t)
        if not jid:
            raise HTTPException(409, f"nothing of the fabulam of {Path(t['source']).name} is running")
        try:
            return {"job": jobs.cancel(jid)}
        except Exception as e:  # noqa: BLE001 - CanonJobError carries its status
            raise HTTPException(getattr(e, "status", 409), str(e)) from None

    def state_body(rel: str) -> dict:
        try:
            t = target_of(project_dir, rel)
        except BuildError as e:
            raise HTTPException(e.status, str(e)) from None
        st = state_of(project_dir, t)
        jid = running(t)
        return {"state": st, "job": jobs.snapshot(jid) if jid else None}

    async def start(do: str, body: dict) -> dict:
        """The tool's door: build, resume, entail or cancel, as the routes do them."""
        if do == "build":
            return await start_build(body)
        if do == "resume":
            return await start_build(body, resume_only=True)
        if do == "entail":
            return await start_entail(body)
        if do == "cancel":
            return cancel_body(body)
        raise HTTPException(400, f"no job starts with {do!r}")

    router.start = start                      # type: ignore[attr-defined]
    router.state = state_body                 # type: ignore[attr-defined]

    @router.get("/api/fabulam/state")
    def fabulam_state(path: str = Query(...)) -> dict:
        return state_body(path)

    @router.post("/api/fabulam/build")
    async def fabulam_build(request: Request) -> dict:
        return await start_build(await body_of(request))

    @router.post("/api/fabulam/resume")
    async def fabulam_resume(request: Request) -> dict:
        return await start_build(await body_of(request), resume_only=True)

    @router.post("/api/fabulam/entail")
    async def fabulam_entail(request: Request) -> dict:
        return await start_entail(await body_of(request))

    @router.post("/api/fabulam/cancel")
    async def fabulam_cancel(request: Request) -> dict:
        return cancel_body(await body_of(request))

    return router


__all__ = ["DOES", "JOB_KIND", "band_refusal", "build_router", "folder_pick", "state_of", "target_of"]
