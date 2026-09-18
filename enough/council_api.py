"""The `/api/council*` routes, as one `APIRouter` `create_app` mounts.

The same split `composure_api.py` uses: `enough/council.py` is the engine and
imports no FastAPI, this file is the HTTP translation over it. Every refusal
is a `CouncilError` (or a `ComposureError`) message from the engine, so the
setup card, a readvisor and the log all read the same sentence.

Two exclusions live here rather than in the engine, because they are about
the server's one session:

- a council control while an ordinary chat turn is streaming → **409**, with
  a sentence saying which one is in the way; and
- `/api/chat` while a council turn is streaming → a polite system bubble,
  wired in `server.api_chat` against `council.turn_in_flight()`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from . import composure as comp_core
from . import council as engine
from .composure import ComposureError
from .council import CouncilError

log = logging.getLogger("enough.council")

EVENT = engine.EVENT

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]
Resolve = Callable[[str], Path]


def build_router(*, project_dir: Path, resolve_path: Resolve, emit: Emit,
                 session: Any) -> APIRouter:
    """Build the council router. One call in `create_app` wires it all."""
    router = APIRouter()

    # ---------------------------------------------------------------- paths

    def _target(path: str) -> Path:
        rel = (path or "").strip()
        if not rel:
            raise HTTPException(400, "missing path")
        if not rel.endswith(comp_core.SUFFIX):
            raise HTTPException(
                400, f"not a composure path: {rel!r} must end in "
                     f"{comp_core.SUFFIX}")
        return resolve_path(rel)

    def _rel(target: Path) -> str:
        try:
            return str(target.resolve().relative_to(project_dir.resolve())
                       ).replace(os.sep, "/")
        except ValueError:
            return target.name

    def _council(path: str) -> engine.Council:
        target = _target(path)
        return engine.Council(
            target, project_dir=project_dir, rel_path=_rel(target),
            emit=emit, llm_url=getattr(session, "llm_url", ""), session=session)

    async def _body(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001 — any malformed body is the same 400
            raise HTTPException(400, "expected a json body") from None
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------ exclusion

    def _guard_chat() -> None:
        """A council control while the main chat is mid-turn is a 409, not a
        queue. Queueing would be worse than refusing: the user would press
        `next turn`, see nothing happen, and get a statement minutes later
        against a transcript they have since changed."""
        lock = getattr(session, "generation_lock", None)
        if lock is not None and lock.locked() and not engine.turn_in_flight():
            raise HTTPException(409, (
                "your readvisor is answering in the chat right now — councils "
                "and the chat share one model, so wait for that turn to finish "
                "(or stop it) and try again."))

    def _guard_council() -> None:
        if engine.turn_in_flight():
            raise HTTPException(409, (
                "a council turn is already streaming. wait for it to finish, "
                "or press pause — you can still add a statement of your own "
                "with the composer, and it will take the next slot."))

    def _running_task(c: engine.Council) -> "asyncio.Task[Any] | None":
        task = engine._RUNS.get(c.key)
        return task if task is not None and not task.done() else None

    def _err(e: Exception) -> HTTPException:
        return HTTPException(400, str(e))

    # ----------------------------------------------------------------- read

    @router.get("/api/council/state")
    async def api_council_state(path: str = Query(...)) -> dict[str, Any]:
        c = _council(path)
        try:
            return await asyncio.to_thread(c.state)
        except (CouncilError, ComposureError) as e:
            raise HTTPException(404 if not c.path.exists() else 400,
                                str(e)) from None

    # ---------------------------------------------------------------- setup

    @router.post("/api/council/setup")
    async def api_council_setup(request: Request) -> dict[str, Any]:
        """Write (or rewrite) the brief, the participant list, the output and
        the round cap. `setup` → `ready`. Creates the composure from the
        `council` form when the path does not exist yet."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        existing: dict[str, Any] | None = None
        title = str(body.get("title") or "").strip()
        create = not c.path.exists()
        if not create:
            comp = await asyncio.to_thread(comp_core.load, c.path)
            existing = comp.council if isinstance(comp.council, dict) else None
            if existing is not None:
                try:
                    existing = engine.validate_meta(existing)
                except CouncilError:
                    existing = None
            if (existing or {}).get("status") == "concluded":
                raise HTTPException(409, (
                    "this council has already concluded — its transcript is "
                    "the record now. Start a new one to ask the next "
                    "question."))
        try:
            meta = await asyncio.to_thread(
                engine.setup_meta, existing, body, project_dir)
        except CouncilError as e:
            raise _err(e) from None
        doc = _check_output_path(meta, resolve_path, project_dir,
                                 bool(body.get("overwrite")))
        meta["output"]["overwrite"] = doc
        ops: list[dict[str, Any]] = []
        if title:
            ops.append({"op": "set_meta", "title": title})
        if create:
            ops.append({"op": "set_meta", "kind": "page"})
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops, c.path, None,
                ops + [{"op": "set_council", "council": meta}],
                source="council", create=create, form="council",
                title=title or "Council", project_dir=project_dir,
                rel_path=c.rel)
        except ComposureError as e:
            raise _err(e) from None
        await _announce_composure(emit, c.rel, result)
        state = await asyncio.to_thread(c.state)
        await _status(emit, c.rel, state)
        return state

    @router.get("/api/council/participants")
    async def api_council_participants() -> dict[str, Any]:
        """The setup card's starting checklist: the chief, every enabled
        readvisor, and the user."""
        rows = await asyncio.to_thread(engine.default_participants, project_dir)
        return {"participants": engine.validate_participants(rows)}

    # -------------------------------------------------------------- driving

    @router.post("/api/council/convene")
    async def api_council_convene(request: Request) -> dict[str, Any]:
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        return await _set_status(c, "running", from_=("ready", "paused",
                                                      "running", "setup"))

    @router.post("/api/council/pause")
    async def api_council_pause(request: Request) -> dict[str, Any]:
        """Stop a `/run`. The turn that is already streaming finishes and is
        committed — a half-written statement thrown away would be a worse
        surprise than one extra paragraph."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        task = _running_task(c)
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        return await _set_status(c, "paused", from_=("running", "ready",
                                                     "paused"))

    @router.post("/api/council/next")
    async def api_council_next(request: Request) -> dict[str, Any]:
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        _guard_council()
        await _require_runnable(c)
        async with engine._turn_lock(c.key):
            try:
                out = await c.take_turn()
            except CouncilError as e:
                raise _err(e) from None
        return {"path": c.rel, "spoke": out.speaker, "turn": out.turn,
                "module": out.module, "rev": out.rev,
                **(await asyncio.to_thread(c.state))}

    @router.post("/api/council/round")
    async def api_council_round(request: Request) -> dict[str, Any]:
        """One full round: every speaking participant once, plus whatever the
        user has queued."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        _guard_council()
        await _require_runnable(c)
        async with engine._turn_lock(c.key):
            spoke = await _one_round(c)
        return {"path": c.rel, "spoke": spoke,
                **(await asyncio.to_thread(c.state))}

    @router.post("/api/council/run")
    async def api_council_run(request: Request) -> dict[str, Any]:
        """Run to `max_rounds` in the background. Returns at once; progress
        arrives on the `council` SSE channel and `/pause` cancels it."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        if _running_task(c) is not None:
            raise HTTPException(409, "this council is already running.")
        _guard_council()
        await _require_runnable(c)
        await _set_status(c, "running", from_=("ready", "paused", "running"))
        task = asyncio.create_task(_run_to_end(c))
        engine._RUNS[c.key] = task
        return {"path": c.rel, "running": True,
                **(await asyncio.to_thread(c.state))}

    @router.post("/api/council/say")
    async def api_council_say(request: Request) -> dict[str, Any]:
        """The user's own statement. Always queued; drained immediately when
        no turn is streaming, so the common case is "it appears now" and the
        racy one is "it appears next" rather than "it is lost"."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "a statement needs some text.")
        try:
            queued = await asyncio.to_thread(_queue, c, text)
        except (CouncilError, ComposureError) as e:
            raise _err(e) from None
        await _status(emit, c.rel, await asyncio.to_thread(c.state))
        if engine.turn_in_flight() or _running_task(c) is not None:
            return {"path": c.rel, "queued": True, "pending": queued}
        async with engine._turn_lock(c.key):
            try:
                out = await c._drain_user_statement()
            except CouncilError as e:
                raise _err(e) from None
        return {"path": c.rel, "queued": False, "turn": out.turn,
                "module": out.module, "rev": out.rev,
                **(await asyncio.to_thread(c.state))}

    # ------------------------------------------------------------- conclude

    @router.post("/api/council/conclude")
    async def api_council_conclude(request: Request) -> dict[str, Any]:
        """One chief turn that produces the output, then the export.

        `answer` → a final module tinted `ink`. `document` → a markdown file
        through the same write door `write_file` uses, guards and all.
        `composure` validates at setup and is refused here, naming the
        release it lands in."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        _guard_council()
        _comp, meta = await asyncio.to_thread(_load, c)
        if meta["status"] == "concluded":
            raise HTTPException(409, "this council has already concluded.")
        out_spec = dict(meta["output"])
        if out_spec["kind"] not in engine.OUTPUT_KINDS_LANDED:
            raise HTTPException(501, (
                f"the {out_spec['kind']!r} council output lands in 0.4.0 — "
                f"conclude with 'answer' or 'document' for now, or change the "
                f"output kind in the setup card."))
        if bool(body.get("overwrite")):
            out_spec["overwrite"] = True
        if out_spec["kind"] == "document":
            _check_output_path({"output": out_spec}, resolve_path, project_dir,
                               bool(out_spec.get("overwrite")))
        async with engine._turn_lock(c.key):
            try:
                turn = await c.take_turn(conclude=out_spec)
            except CouncilError as e:
                raise _err(e) from None
        written: str | None = None
        detail = ""
        if out_spec["kind"] == "document":
            written, detail = await asyncio.to_thread(
                _write_document, project_dir, out_spec, turn.text)
            if written:
                result = await asyncio.to_thread(
                    _link_document, c, written)
                await _announce_composure(emit, c.rel, result)
        transcript = await asyncio.to_thread(
            c.export_transcript, output_path=written or "")
        await asyncio.to_thread(_finish, c, written, transcript)
        state = await asyncio.to_thread(c.state)
        await _status(emit, c.rel, state)
        return {"path": c.rel, "output": out_spec["kind"],
                "document": written, "detail": detail,
                "transcript": transcript, "module": turn.module,
                "text": turn.text, **state}

    # ------------------------------------------------------------- helpers

    async def _require_runnable(c: engine.Council) -> None:
        _comp, meta = await asyncio.to_thread(_load, c)
        if meta["status"] == "concluded":
            raise HTTPException(409, (
                "this council has concluded — its transcript is the record "
                "now. Start a new one to carry on."))
        if meta["status"] == "setup":
            raise HTTPException(409, (
                "this council has not been set up yet — fill in the brief and "
                "press convene."))
        if not engine.speakers(meta):
            raise HTTPException(400, (
                "this council has nobody who can speak — add the chief "
                "readvisor or a readvisor to the participants."))

    async def _set_status(c: engine.Council, status: str,
                          *, from_: tuple[str, ...]) -> dict[str, Any]:
        def _apply() -> dict[str, Any]:
            _comp, meta = _load(c)
            if meta["status"] not in from_:
                raise CouncilError(
                    f"a council cannot go from {meta['status']!r} to "
                    f"{status!r}.")
            meta["status"] = status
            nxt = engine.next_speaker(meta)
            meta["next"] = nxt["id"] if nxt else None
            c._commit([{"op": "set_meta"}], meta)
            return c.state()
        try:
            state = await asyncio.to_thread(_apply)
        except (CouncilError, ComposureError) as e:
            raise _err(e) from None
        await _status(emit, c.rel, state)
        return state

    async def _one_round(c: engine.Council) -> list[str]:
        """Turns until the rotation wraps. A queued user statement is
        committed in the slot it lands in and does not count against the
        round — it is an interjection, not a participant's turn."""
        spoke: list[str] = []
        _comp, meta = await asyncio.to_thread(_load, c)
        order = engine.speakers(meta)
        budget = len(order) + len(meta.get("queue") or []) + 2
        start_round = meta["round"]
        for _ in range(budget):
            _comp, meta = await asyncio.to_thread(_load, c)
            if meta["status"] == "concluded":
                break
            if meta["round"] > start_round:
                break
            try:
                out = await c.take_turn()
            except CouncilError as e:
                raise _err(e) from None
            spoke.append(out.speaker)
        return spoke

    async def _run_to_end(c: engine.Council) -> None:
        """The `/run` body. Cancellation lands between turns, so a statement
        is never half-committed; the status then settles on `paused`."""
        try:
            while True:
                _comp, meta = await asyncio.to_thread(_load, c)
                if meta["status"] != "running":
                    break
                if meta["round"] >= meta["max_rounds"] and not meta.get("queue"):
                    break
                async with engine._turn_lock(c.key):
                    await c.take_turn()
        except asyncio.CancelledError:
            await _quiet_status(c, "paused")
            raise
        except Exception as e:  # noqa: BLE001 — a background task must report
            log.exception("council run failed")
            await emit(EVENT, {"path": c.rel, "phase": "error",
                               "text": str(e)})
            await _quiet_status(c, "paused")
        else:
            await _quiet_status(c, "ready")
        finally:
            engine._RUNS.pop(c.key, None)

    async def _quiet_status(c: engine.Council, status: str) -> None:
        def _apply() -> dict[str, Any] | None:
            try:
                _comp, meta = _load(c)
            except (CouncilError, ComposureError):
                return None
            if meta["status"] == "concluded":
                return None
            meta["status"] = status
            c._commit([{"op": "set_meta"}], meta)
            return c.state()
        try:
            state = await asyncio.to_thread(_apply)
        except (CouncilError, ComposureError):
            return
        if state:
            await _status(emit, c.rel, state)

    return router


# ---------------------------------------------------------------------------
# Module-level helpers (no closure over the router's factory arguments)
# ---------------------------------------------------------------------------

def _load(c: engine.Council) -> tuple[comp_core.Composure, dict[str, Any]]:
    return c.load()


def _queue(c: engine.Council, text: str) -> int:
    comp, meta = c.load()
    queue = list(meta.get("queue") or [])
    queue.append({"text": text})
    meta["queue"] = queue
    nxt = engine.next_speaker(meta)
    meta["next"] = nxt["id"] if nxt else None
    c._commit([{"op": "set_meta"}], meta)
    return len(queue)


async def _status(emit: Emit, rel: str, state: dict[str, Any]) -> None:
    meta = state.get("council") or {}
    await emit(EVENT, {
        "path": rel, "phase": "status", "status": meta.get("status"),
        "round": meta.get("round"), "turn": meta.get("turn"),
        "next": state.get("next"), "next_name": state.get("next_name"),
        "rev": state.get("rev"),
    })


async def _announce_composure(emit: Emit, rel: str,
                              result: comp_core.OpsResult) -> None:
    await emit(comp_core.EVENT, {
        "path": rel, "rev": result.rev, "changed": result.changed,
        "source": "council", "created": result.created,
    })


def _check_output_path(meta: dict[str, Any], resolve_path: Resolve,
                       project_dir: Path, overwrite: bool) -> bool:
    """Validate a `document` output's path the way every other path in this
    app is validated, and refuse to plan a silent overwrite. The UI only
    sends `overwrite: true` after its confirm overlay, so a 409 here is the
    server half of that conversation, not a duplicate of it."""
    out = meta.get("output") or {}
    if out.get("kind") != "document":
        return bool(out.get("overwrite"))
    rel = str(out.get("path") or "")
    try:
        target = resolve_path(rel)
    except Exception as e:  # noqa: BLE001 — HTTPException or ValueError
        raise HTTPException(400, f"that output path will not do: {e}") from None
    if target.is_dir():
        raise HTTPException(400, f"{rel} is a directory, not a document.")
    if target.exists() and not overwrite:
        raise HTTPException(409, (
            f"{rel} already exists. Confirm the overwrite (or choose another "
            f"path) — a council that quietly replaces a file you wrote is not "
            f"a council you would use twice."))
    return bool(overwrite)


def _write_document(project_dir: Path, out_spec: dict[str, Any],
                    text: str) -> tuple[str | None, str]:
    """Write the concluding document through `tools.run_write_file` — the
    same door, the same guards (the cachebox mirror rule, the allowlists, the
    protected prefixes, the `.comp`/`.girraph` refusals, the undo stash and
    the convert twin sync). A council does not get its own write path."""
    from . import tools as _tools
    rel = str(out_spec.get("path") or "")
    body = (text or "").rstrip() + "\n"
    call = _tools.ToolCall(name="write_file", path=rel, content=body,
                           command=None, url=None, extra={}, raw="",
                           span=(0, 0))
    result = _tools.run_write_file(project_dir, call)
    if not result.ok:
        return None, result.body
    return rel, result.body


def _link_document(c: engine.Council, rel: str) -> comp_core.OpsResult:
    """A `doc` link-in module under the conclusion, so the document the
    council produced is one click from the council that produced it."""
    comp, meta = c.load()
    ops = [{"op": "add_module", "type": "doc", "href": rel,
            "title": rel.rsplit("/", 1)[-1], "bg": "paper",
            "markdown": f"The council's document, written to `{rel}`."}]
    return c._commit(ops, meta)


def _finish(c: engine.Council, written: str | None, transcript: str) -> None:
    _comp, meta = c.load()
    meta["status"] = "concluded"
    meta["next"] = None
    meta["transcript"] = transcript or None
    out = dict(meta.get("output") or {})
    if written:
        out["path"] = written
    meta["output"] = out
    c._commit([{"op": "set_meta"}], meta)


__all__ = ["build_router", "EVENT"]
