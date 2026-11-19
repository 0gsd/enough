"""The routes of an authored fabulac (0.8, fabulac-first F6): `/api/fabulac/*`, thin wrappers over the plain
functions in `enough/fabulac_first.py`, every one listed in the API promise (`enough/api_promise.py`), whose header
gate (`X-Enough-Api: 1`) every POST here passes first.

What blocks runs as a CanonJob: begin and take it up (kind `fabulac-author`), entail and take back (`fabulac-entail`,
model mode holding the generation lock as any model job does), and the sandbox's test and run (`sandbox`, rules mode,
no lock). Stop cancels the job and stops its sandbox run; the app's shutdown stops every run (`server.create_app`'s
lifespan calls `sandbox.stop_all`). Refusals are the plain functions' (`FirstError`: status and sentence); a service
is refused at test and run with the sandbox's sentence.

`router.start(do, body)` is what the readvisor's `fabulac` tool starts through: the same code as the routes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from .. import api_promise as _promise
from .. import fabulac_first as _ff
from .. import thym_host as _host
from .common import AppContext

JOB_AUTHOR = "fabulac-author"
JOB_ENTAIL = "fabulac-entail"
JOB_SANDBOX = "sandbox"


def _http(e: Exception) -> HTTPException:
    status = getattr(e, "status", 409)
    return HTTPException(status, str(e))


def route_of(body: dict) -> tuple[str, str | None, int | None]:
    """`(route, model, calls)` from a body: `local` (this machine's model) or `cloud` (or `cloud:<model id>`)."""
    raw = str(body.get("route") or "local").strip().lower()
    model = body.get("model")
    if raw.startswith("cloud:"):
        raw, model = "cloud", raw[len("cloud:"):]
    if raw not in _host.ROUTES:
        raise HTTPException(400, f"route is local or cloud (or cloud:<model id>), not {raw!r}")
    model = (str(model).strip() or None) if model not in (None, "") else None
    calls = body.get("calls")
    if calls is not None and (isinstance(calls, bool) or not isinstance(calls, int) or calls < 1):
        raise HTTPException(400, f"calls is a ceiling of at least 1 model call, not {calls!r}")
    return raw, model, calls


async def decide_mode(canon_mode: Callable, body: dict, route: str) -> tuple[str, str]:
    """`(mode, why)`, decided once before a job starts: `rules` when asked, else the app's own answer for the route
    (agent-free gives rules). A test replaces this function to stand a scripted model in."""
    want = str(body.get("mode") or "auto").strip().lower()
    if want not in ("auto", "model", "rules"):
        raise HTTPException(400, "mode is model, rules, or left out")
    if want == "rules":
        return "rules", "asked"
    try:
        mode, why = await canon_mode(route)
    except TypeError:
        mode, why = await canon_mode()
    if want == "model" and mode != "model":
        raise HTTPException(409, f"no model is running ({why})")
    return mode, why


def _list(v: Any, what: str) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    raise HTTPException(400, f"{what} is a list of paths")


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

    def path_of(body: dict) -> str:
        p = body.get("path")
        if not isinstance(p, str) or not p.strip():
            raise HTTPException(400, "missing path: the program's name, or its <name>.fabulac.cosm")
        return p

    async def call(fn: Callable, *a: Any, **kw: Any) -> Any:
        try:
            return await asyncio.to_thread(fn, *a, **kw)
        except _ff.FirstError as e:
            raise _http(e) from None

    def complete_for(route: str, model: str | None) -> Callable[..., Any]:
        from .. import llm as _llm
        if route == "local" and _llm._current_slot() != "opro-api":
            return model_complete
        return _host.route_complete(route, model=model, llm_url=llm_url, project_dir=project_dir)

    def fab_of(rel: str, *, must_exist: bool = True) -> Path:
        try:
            return _ff.authored(project_dir, rel) if must_exist else _ff.fabulac_path(project_dir, rel)
        except _ff.FirstError as e:
            raise _http(e) from None

    def after(rel: str) -> None:
        try:
            catalog_after(rel)
        except Exception:  # noqa: BLE001 - a catalog is never worth a failed job
            pass

    # -- the jobs --------------------------------------------------------------------------------------------------

    async def start_begin(body: dict) -> dict:
        rel = path_of(body)
        fab = fab_of(rel, must_exist=False)
        kw = {k: body.get(k) for k in ("licence", "brief", "by") if isinstance(body.get(k), str) and body.get(k)}
        if body.get("starter"):
            return await call(_ff.begin, project_dir, rel, starter=str(body["starter"]), **kw)
        kind = str(body.get("kind") or "tool")
        if kind not in _ff.KINDS:
            raise HTTPException(400, f"kind is tool, library or service, not {kind!r}")
        route, model, calls = route_of(body)
        mode, why = await decide_mode(canon_mode, body, route)
        complete = complete_for(route, model) if mode == "model" else None
        rel = _ff._rel(project_dir, fab)

        def work(job: Any) -> dict:
            out = _ff.begin(project_dir, rel, kind=kind, mode=mode, why=why, route=route, model=model, calls=calls,
                            llm_url=llm_url, complete=complete, progress=lambda f: job.progress(f),
                            should_stop=job.should_stop, **kw)
            after(rel)
            return out
        return start_job(kind=JOB_AUTHOR, path=rel, mode=mode, why=why if mode == "model" else "", work=work,
                         key=str(fab.resolve()), doing=f"authoring {fab.name}", route=route if mode == "model" else None)

    async def model_job(body: dict, what: str, fn: Callable[..., dict], **more: Any) -> dict:
        rel = path_of(body)
        fab = fab_of(rel)
        route, model, calls = route_of(body)
        mode, why = await decide_mode(canon_mode, body, route)
        if mode != "model":
            raise HTTPException(409, f"{what} needs a model, and none is answering ({why})")
        complete = complete_for(route, model)
        rel = _ff._rel(project_dir, fab)

        def work(job: Any) -> dict:
            out = fn(project_dir, rel, why=why, route=route, model=model, calls=calls, llm_url=llm_url,
                     complete=complete, progress=lambda f: job.progress(f), should_stop=job.should_stop, **more)
            after(rel)
            return out
        return start_job(kind=JOB_ENTAIL, path=rel, mode=mode, why=why, work=work, key=str(fab.resolve()),
                         doing=f"{what} {fab.name}", route=route)

    async def start_entail(body: dict) -> dict:
        over = _list(body.get("overwrite"), "overwrite")
        st = await call(_ff.moved, project_dir, path_of(body))        # a hand edit refuses it before a job starts
        edited = [p for p in st["edited"] if p not in over]
        if edited:
            raise HTTPException(409, f"{st['folder']} holds files changed by hand: {', '.join(edited[:8])}. Nothing "
                                     "was written: keep them, write over them (overwrite), or take them back first")
        return await model_job(body, "entailing", _ff.entail, overwrite=over)

    async def start_take_back(body: dict) -> dict:
        f = body.get("file")
        if not isinstance(f, str) or not f.strip():
            raise HTTPException(400, "take-back names the file: its path inside the entailment's folder")
        return await model_job(body, "taking back", _ff.take_back, file=f)

    async def start_run(body: dict, what: str) -> dict:
        rel = path_of(body)
        args = _list(body.get("args"), "args") if what == "tool" else []
        stdin = body.get("stdin") or ""
        if not isinstance(stdin, str):
            raise HTTPException(400, "stdin is text")
        hand = _list(body.get("hand_over"), "hand_over") if what == "tool" else []
        given = await call(_ff._hand_over, project_dir, hand)
        args = _ff.args_for(args, hand, given)
        fab, run = await call(_ff.prepare, project_dir, rel, what="tests" if what == "tests" else "tool")
        rel = _ff._rel(project_dir, fab)

        def work(job: Any) -> dict:
            job.progress({"phase": "running", "message": f"running {'the tests of ' if what == 'tests' else ''}"
                                                         f"{run.program.name} in the sandbox"})
            return _ff.execute(project_dir, fab, run, what=what, args=args, stdin=stdin, hand_over=given,
                               should_stop=job.should_stop)
        try:
            snap = jobs.start(kind=JOB_SANDBOX, path=rel, mode="rules", work=work, key="run:" + str(fab.resolve()),
                              message=f"running {'the tests' if what == 'tests' else run.program.name} in the sandbox",
                              extra={"run": run.run_id, "what": what})
        except Exception as e:  # noqa: BLE001 - CanonJobError carries its status
            raise _http(e) from None
        return {"job": snap, "run": run.run_id}

    def stop_body(body: dict) -> dict:
        run_id = body.get("run")
        if isinstance(run_id, str) and run_id.strip() and not body.get("path"):
            out = _ff.stop(run_id.strip())
            if not out["stopped"]:
                raise HTTPException(409, f"no sandbox run {run_id} is running")
            return out
        rel = path_of(body)
        fab = fab_of(rel)
        stopped: list[dict] = []
        for key in ("run:" + str(fab.resolve()), str(fab.resolve())):
            jid = jobs.running_for(key)
            if not jid:
                continue
            snap = jobs.cancel(jid)
            if snap.get("run"):
                _ff.stop(str(snap["run"]))
            stopped.append(snap)
        if not stopped:
            raise HTTPException(409, f"nothing of {fab.name} is running")
        return {"stopped": stopped, "message": f"stopped {len(stopped)} job{'s' if len(stopped) != 1 else ''} of "
                                               f"{fab.name}"}

    async def start(do: str, body: dict) -> dict:
        """The tool's door: one of begin, entail, take-back, test, run, stop, as the routes do it."""
        if do == "begin":
            return await start_begin(body)
        if do == "entail":
            return await start_entail(body)
        if do == "take-back":
            return await start_take_back(body)
        if do in ("test", "run"):
            return await start_run(body, "tests" if do == "test" else "tool")
        if do == "stop":
            return stop_body(body)
        raise HTTPException(400, f"no job starts with {do!r}")

    router.start = start                      # type: ignore[attr-defined]

    # -- the routes ------------------------------------------------------------------------------------------------

    @router.get("/api/fabulac/promise")
    def fabulac_promise() -> dict:
        return _promise.payload()

    @router.get("/api/fabulac/starters")
    def fabulac_starters() -> dict:
        return {"starters": _ff.starters()}

    @router.post("/api/fabulac/begin")
    async def fabulac_begin(request: Request) -> dict:
        return await start_begin(await body_of(request))

    @router.post("/api/fabulac/answer")
    async def fabulac_answer(request: Request) -> dict:
        body = await body_of(request)
        ans = body.get("answers")
        if not isinstance(ans, list) or not ans:
            raise HTTPException(400, "answers is a list: [{question, says}], or a flag unknown, declined or skip")
        return await call(_ff.answer, project_dir, path_of(body), ans, who=body.get("who"))

    @router.get("/api/fabulac/status")
    async def fabulac_status(path: str = Query(...)) -> dict:
        out = await call(_ff.status, project_dir, path)
        fab = fab_of(path)
        out["jobs"] = [jobs.snapshot(j) for j in (jobs.running_for(k) for k in (str(fab.resolve()),
                                                                                 "run:" + str(fab.resolve()))) if j]
        return out

    @router.post("/api/fabulac/add")
    async def fabulac_add(request: Request) -> dict:
        body = await body_of(request)
        return await call(_ff.add, project_dir, path_of(body), as_=str(body.get("as") or ""),
                          says=str(body.get("says") or ""), fields=body.get("fields"))

    @router.get("/api/fabulac/check")
    async def fabulac_check(path: str = Query(...)) -> dict:
        return await call(_ff.check, project_dir, path)

    @router.post("/api/fabulac/entail")
    async def fabulac_entail(request: Request) -> dict:
        return await start_entail(await body_of(request))

    @router.get("/api/fabulac/moved")
    async def fabulac_moved(path: str = Query(...)) -> dict:
        return await call(_ff.moved, project_dir, path)

    @router.post("/api/fabulac/keep")
    async def fabulac_keep(request: Request) -> dict:
        body = await body_of(request)
        because = body.get("because") if isinstance(body.get("because"), str) else None
        return await call(_ff.keep, project_dir, path_of(body), _list(body.get("files"), "files"), because=because)

    @router.post("/api/fabulac/let-go")
    async def fabulac_let_go(request: Request) -> dict:
        body = await body_of(request)
        return await call(_ff.let_go, project_dir, path_of(body), _list(body.get("files"), "files"))

    @router.post("/api/fabulac/take-back")
    async def fabulac_take_back(request: Request) -> dict:
        return await start_take_back(await body_of(request))

    @router.post("/api/fabulac/test")
    async def fabulac_test(request: Request) -> dict:
        return await start_run(await body_of(request), "tests")

    @router.post("/api/fabulac/run")
    async def fabulac_run(request: Request) -> dict:
        return await start_run(await body_of(request), "tool")

    @router.post("/api/fabulac/stop")
    async def fabulac_stop(request: Request) -> dict:
        return stop_body(await body_of(request))

    @router.post("/api/fabulac/head")
    async def fabulac_head(request: Request) -> dict:
        body = await body_of(request)
        kw = {k: body.get(k) for k in ("name", "licence", "by") if isinstance(body.get(k), str)}
        return await call(_ff.head, project_dir, path_of(body), _list(body.get("parts"), "parts"), **kw)

    @router.get("/api/fabulac/parts-moved")
    async def fabulac_parts_moved(path: str = Query(...)) -> dict:
        return await call(_ff.parts_moved, project_dir, path)

    return router


__all__ = ["JOB_AUTHOR", "JOB_ENTAIL", "JOB_SANDBOX", "build_router", "decide_mode", "route_of"]
