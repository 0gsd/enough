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

    # The pal seam, wired here because here is where a project directory
    # exists. `council.PAL_CALL` is the WHOLE of the contract between the
    # council and `/pal` (P9 §6): the council distils the prompt, this sends
    # it, and `pal_tools.ask_pal_once` is the same gate, the same caps, the
    # same exfiltration patterns, the same cloud cache and the same broker
    # journal entry the `ask_pal` tool gets. A second implementation is how
    # one of the two ends up a check short.
    engine.PAL_CALL = _pal_call_for(project_dir)

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
        # The brief MODULE, from the same four fields. Without this a council
        # set up through the API alone — by a tool, by a script, by anything
        # that is not the setup card — keeps the shipped form's placeholder
        # while the participants argue about something else entirely.
        try:
            written = await asyncio.to_thread(_write_brief, c)
        except (CouncilError, ComposureError):   # pragma: no cover — defensive
            log.warning("council: could not write the brief module of %s",
                        c.rel, exc_info=True)
            written = None
        if written is not None:
            await _announce_composure(emit, c.rel, written)
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

    # ------------------------------------------------------------------ pal

    @router.post("/api/council/pal")
    async def api_council_pal(request: Request) -> dict[str, Any]:
        """`/pal <ask>` from the council composer.

        The chief distils one self-contained prompt out of the brief and the
        transcript, `PAL_CALL` sends it, and the answer is committed as a
        statement tinted gray whose first block is the exact outgoing prompt
        (P9 §6). A pal is an interjection: it takes a turn number but not a
        slot, so whoever was about to speak still speaks next.

        The gate is checked HERE as well as inside the call, before a single
        model token is spent: distilling a prompt that cannot be sent is a
        window's worth of work and a paragraph the user did not ask for."""
        from . import cloud as _cloud
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        ask = str(body.get("ask") or "").strip()
        if not ask:
            raise HTTPException(400, (
                "a pal needs a question — type it after `/pal`, and the "
                "council's chief will turn it into one prompt to send out."))
        gate = await asyncio.to_thread(_cloud.gate_status)
        if not gate["open"]:
            raise HTTPException(409, gate["denial"] or (
                "the cloud slot is not usable right now, so there is no pal "
                "to ask."))
        _guard_chat()
        _guard_council()
        await _require_runnable(c)
        async with engine._turn_lock(c.key):
            try:
                out = await c.ask_pal_turn(ask)
            except NotImplementedError:   # pragma: no cover — wired at build
                raise HTTPException(409, (
                    "this enough was built without a pal — `/pal` is not "
                    "wired up here.")) from None
            except CouncilError as e:
                raise _err(e) from None
        return {"path": c.rel, "spoke": out.speaker, "turn": out.turn,
                "module": out.module, "rev": out.rev, "pal": True,
                "text": out.text,
                **(await asyncio.to_thread(c.state))}

    # ------------------------------------------------------------- conclude

    @router.post("/api/council/conclude")
    async def api_council_conclude(request: Request) -> dict[str, Any]:
        """One chief turn that produces the output, then the export.

        `answer` → a final module tinted `ink`. `document` → a markdown file
        through the same write door `write_file` uses, guards and all.
        `composure` → an outline, parsed into a whole new composure beside
        this one and linked from it; an outline that will not parse twice
        falls back to `answer` and says so in `output_fallback`."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        _guard_council()
        _comp, meta = await asyncio.to_thread(_load, c)
        if meta["status"] == "concluded":
            raise HTTPException(409, "this council has already concluded.")
        out_spec = dict(meta["output"])
        if out_spec["kind"] not in engine.OUTPUT_KINDS_LANDED:
            raise HTTPException(501, (   # pragma: no cover — no kind is unlanded
                f"the {out_spec['kind']!r} council output is not built yet — "
                f"conclude with one of "
                f"{', '.join(sorted(engine.OUTPUT_KINDS_LANDED))}, or change "
                f"the output kind in the setup card."))
        if bool(body.get("overwrite")):
            out_spec["overwrite"] = True
        if out_spec["kind"] == "document":
            _check_output_path({"output": out_spec}, resolve_path, project_dir,
                               bool(out_spec.get("overwrite")))
        written: str | None = None
        detail = ""
        fallback: str | None = None
        extra: dict[str, Any] = {}
        async with engine._turn_lock(c.key):
            try:
                if out_spec["kind"] == "composure":
                    made = await c.conclude_composure(out_spec)
                    turn = made["turn"]
                    written = made["path"]
                    fallback = made["fallback"]
                    extra = {"retried": made["retried"],
                             "form": made["form"]}
                    detail = (f"wrote {written}" if written else
                              "the outline would not parse twice — the "
                              "conclusion was kept as an answer.")
                else:
                    turn = await c.take_turn(conclude=out_spec)
            except CouncilError as e:
                raise _err(e) from None
            except ComposureError as e:
                raise _err(e) from None
        if out_spec["kind"] == "document":
            written, detail = await asyncio.to_thread(
                _write_document, project_dir, out_spec, turn.text)
            if written:
                result = await asyncio.to_thread(
                    _link_doc, c, written,
                    f"The council's document, written to `{written}`.")
                await _announce_composure(emit, c.rel, result)
        transcript = await asyncio.to_thread(
            c.export_transcript, output_path=written or "",
            fallback=fallback or "")
        await asyncio.to_thread(_finish, c, written, transcript,
                                fallback=fallback)
        state = await asyncio.to_thread(c.state)
        await _status(emit, c.rel, state)
        return {"path": c.rel, "output": out_spec["kind"],
                "document": written, "composure": (
                    written if out_spec["kind"] == "composure" else None),
                "output_fallback": fallback, "detail": detail,
                "transcript": transcript, "module": turn.module,
                "text": turn.text, **extra, **state}

    # ------------------------------------------------------------ reconvene

    @router.post("/api/council/reconvene")
    async def api_council_reconvene(request: Request) -> dict[str, Any]:
        """A concluded council, sat again: a NEW composure with the same
        participants, charges, parameters, constraints, output and round cap,
        and a brief that carries the prior output forward as input.

        The old council is not touched beyond the `doc` link-in that points
        at its successor — it is concluded, its transcript is the record, and
        a second run writing into it would destroy exactly the thing a
        reconvene exists to build on."""
        body = await _body(request)
        c = _council(str(body.get("path") or ""))
        _guard_chat()
        prior_comp, prior = await asyncio.to_thread(_load, c)
        if prior["status"] != "concluded":
            raise HTTPException(409, (
                "only a concluded council can be reconvened — this one is "
                f"{prior['status']!r}. Conclude it first, so there is an "
                f"output to carry forward."))
        try:
            meta, rel, title = await asyncio.to_thread(
                _reconvene_meta, c, prior_comp, prior, project_dir,
                str(body.get("title") or ""))
        except (CouncilError, ComposureError) as e:
            raise _err(e) from None
        target = resolve_path(rel)
        nxt = engine.Council(target, project_dir=project_dir, rel_path=rel,
                             emit=emit, llm_url=getattr(session, "llm_url", ""),
                             session=session)
        try:
            result = await asyncio.to_thread(
                comp_core.apply_ops, target, None,
                [{"op": "set_meta", "title": title, "kind": "page"},
                 {"op": "set_council", "council": meta}],
                source="council", create=True, form="council", title=title,
                project_dir=project_dir, rel_path=rel)
        except ComposureError as e:
            raise _err(e) from None
        await _announce_composure(emit, rel, result)
        await asyncio.to_thread(_write_brief, nxt)
        # Both ways: the new council links back to the one it came from, and
        # the old one gains a link forward, so neither end is a dead end.
        await asyncio.to_thread(
            nxt.link_doc, c.rel,
            f"The council this one carries on from: `{c.rel}`.")
        back = await asyncio.to_thread(
            c.link_doc, rel, f"This council was reconvened as `{rel}`.")
        await asyncio.to_thread(_mark_reconvened, c, rel)
        await _announce_composure(emit, c.rel, back)
        state = await asyncio.to_thread(nxt.state)
        await _status(emit, rel, state)
        return {"path": rel, "from": c.rel, "title": title, **state}

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

def _pal_call_for(project_dir: Path) -> Callable[[str], tuple[str, str]]:
    """`PAL_CALL(prompt) -> (model_id, reply)`, bound to one project.

    `pal_tools` is imported lazily: it reaches `enough.cloud` for the gate,
    which drags httpx and keyring in, and `council_api` is imported at app
    build time on machines where the cloud slot is never used."""
    def _call(prompt: str) -> tuple[str, str]:
        from . import pal_tools as _pal
        return _pal.ask_pal_once(project_dir, prompt)
    return _call


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


def _link_doc(c: engine.Council, rel: str, blurb: str) -> comp_core.OpsResult:
    return c.link_doc(rel, blurb)


def _write_brief(c: engine.Council) -> comp_core.OpsResult | None:
    """Write the brief MODULE's page from the four setup fields, and record
    which module that is. The brief module is unlocked (it has no speaker),
    so this is an ordinary `set_page` — the only new thing is that the
    backend now does it instead of only the setup card."""
    comp, meta = c.load()
    mid = c.brief_module_id(comp, meta)
    if not mid:
        return None
    text = engine.brief_markdown(meta)
    if not text:
        return None
    meta["brief_module"] = mid
    return c._commit([{"op": "set_page", "module": mid, "n": 1,
                       "markdown": text}], meta)


def _reconvene_meta(c: engine.Council, comp: comp_core.Composure,
                    prior: dict[str, Any], project_dir: Path,
                    title: str) -> tuple[dict[str, Any], str, str]:
    """The new council's meta, path and title. Reads the prior output —
    the conclusion statement for an `answer`, the file itself for a
    `document` or a `composure` — so the new brief carries something real
    rather than a promise that there was an output."""
    out = prior.get("output") or {}
    kind = out.get("kind") or "answer"
    answer = ""
    excerpt = ""
    if kind == "answer":
        statements = engine.read_statements(comp)
        answer = statements[-1].text if statements else ""
    elif out.get("path"):
        excerpt = _read_head(project_dir / str(out["path"]), kind)
    meta = engine.reconvene_meta(prior, c.rel, answer=answer, excerpt=excerpt)
    meta["reconvened_from"] = c.rel
    name = (title or comp.title or "Council").strip()
    if not name.lower().endswith("reconvened"):
        name = f"{name} · reconvened"
    rel = comp_core.new_path(project_dir, name)
    return meta, rel, name


def _read_head(target: Path, kind: str) -> str:
    """The first of a prior output, as text. A `.comp` is read through the
    composure outline rather than as HTML — the markup is not what the next
    council needs to argue with."""
    try:
        if kind == "composure" and target.suffix == comp_core.SUFFIX:
            return comp_core.outline(comp_core.load(target))
        return target.read_text(encoding="utf-8")
    except (OSError, ComposureError):
        return ""


def _mark_reconvened(c: engine.Council, rel: str) -> None:
    """The one field the concluded council does gain: where it went next."""
    _comp, meta = c.load()
    meta["reconvened_to"] = rel
    c._commit([{"op": "set_meta"}], meta)


def _finish(c: engine.Council, written: str | None, transcript: str,
            *, fallback: str | None = None) -> None:
    _comp, meta = c.load()
    meta["status"] = "concluded"
    meta["next"] = None
    meta["transcript"] = transcript or None
    meta["output_fallback"] = fallback or None
    out = dict(meta.get("output") or {})
    if written:
        out["path"] = written
    meta["output"] = out
    c._commit([{"op": "set_meta"}], meta)


__all__ = ["build_router", "EVENT"]
