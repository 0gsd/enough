"""Canon's jobs and the fabula routes: derive, atem, twin, suggest, models (`/api/fabula/*`, `/api/canon/atem*`, `/api/canon/job/*`), and the helpers the Thym, fabulac, fabulap and dialectic routers are built with.

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from .. import agent_free as _agent_free
from .. import canon as _canon
from .. import canon_derive as _canon_derive
from .. import canon_jobs as _canon_jobs
from .. import canon_tools as _canon_tools
from .. import cloud as _cloud
from .. import convert as _convert
from .. import fabula_names as _fabula_names
from .. import llm as _llm
from .. import macrocosm as _macrocosm
from .. import model_route as _model_route
from .. import retired_names as _retired_names
from .common import AppContext
from ..server import STORE_PREFIXES, _store_prefix, log


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    _cosm_payload = ctx._cosm_payload
    _emit_threadsafe = ctx._emit_threadsafe
    _resolve_project_path = ctx._resolve_project_path
    home = ctx.home
    project_dir = ctx.project_dir
    session = ctx.session

    # ------------------------------------------------------------------
    # Canon derivations (0.4.3, P3): EMF twins, atems, compile. The engine is
    # canon_derive.py (pure functions); the job table and the generation-lock
    # rule are canon_jobs.py. Every route here runs only because a person
    # asked: nothing derives on its own. Progress and results stream on the
    # `canon` SSE event (payload = the job snapshot). Contract:
    # docs/canon-043-plan.md §6.4 and §7, docs/canon-landed-P3.md.
    # ------------------------------------------------------------------

    canon_jobs = _canon_jobs.CanonJobs(emit=_emit_threadsafe)
    # (`app.state.canon_jobs` is set by `create_app`, from `ctx.canon_jobs`.)
    if not home:
        # The readvisor's MacroCOSM tools (P6) run inside a chat turn, which
        # already holds the generation lock: they call the engine directly at
        # this session's model and honour this table's per-file claims rather
        # than starting jobs (a lock-taking job would wait for the very turn
        # that is waiting for the tool).
        _canon_tools.configure(llm_url=session.llm_url, jobs=canon_jobs)
    # A pasted or selected passage longer than this is a file's work: derive the file.
    CANON_ATEM_TEXT_MAX = 200_000

    def _canon_job_http(e: "_canon_jobs.CanonJobError") -> HTTPException:
        return HTTPException(e.status, str(e))

    async def _json_body(request: Request) -> dict[str, Any]:
        # Before the split this name was defined twice in one scope and the
        # later definition (the launch screen's) won, so these routes read
        # `{}` on any failure to read the body. Kept so the move changes
        # nothing (0.8 build, W2-SV).
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return {}
        return body if isinstance(body, dict) else {}

    def _canon_rel(path: str) -> str:
        """A request path tidied the way the routes report it back: project-
        relative, or `canon:` + the path in the store."""
        path = (path or "").strip()
        prefix = _store_prefix(path) or ""
        parts = [p for p in path[len(prefix):].replace("\\", "/").split("/") if p not in ("", ".")]
        return prefix + "/".join(parts)

    def _rel_beside(rel: str, name: str) -> str:
        prefix = _store_prefix(rel) or ""
        head = rel[len(prefix):].rpartition("/")[0]
        return f"{prefix}{head}/{name}" if head else f"{prefix}{name}"

    def _canon_where(rel: str) -> tuple[str | None, str | None]:
        """`(volume, path in its volume)` for a store path, `(None, rel)` for a
        project path — the catalog to regenerate, and the EMF catalog id's
        path (P0 decision 16). A file at the store's root has no volume."""
        prefix = _store_prefix(rel)
        if not prefix:
            return None, rel
        parts = rel[len(prefix):].split("/")
        return (parts[0], "/".join(parts[1:])) if len(parts) > 1 else (None, parts[0])

    def _canon_catalog_after(rel: str) -> None:
        """After a twin, pin or compile is written: the Canon volume's catalog
        (store paths) or the project catalog (project paths), through canon.py's
        own writers (each writes only when its bytes change)."""
        volume, _ = _canon_where(rel)
        try:
            if _store_prefix(rel):
                if volume:
                    _canon.require_volume(volume)
                    _canon.regenerate_catalog(volume)
            else:
                _canon.project_catalog(project_dir)
        except _canon.CanonError:
            pass
        except Exception:  # noqa: BLE001 — the write landed; a catalog hiccup heals at the next reconcile
            log.exception("canon: catalog after a derivation write failed")

    def _text_target(path: str, flavour: str | None = None) -> dict[str, Any]:
        """Resolve and vet the text a derive, atem or pin names (blocking).
        The rules and their words live in `canon_tools.text_target` (P6), so
        the readvisor's tools refuse exactly what these routes refuse: a
        missing file (404), a folder, a Holotype or anything in one, a catalog
        or meta enough keeps, any `.cosm`, binaries, kinds that aren't
        markdown or plain text, an empty file, a flavour a text cannot take
        (400), and a `X.<flavour>.cosm` beside the text that is not a fabula
        (409). A converted original is read through its markdown twin, or
        refused with "convert it first". The result carries the flavour (the
        one asked, else the twin's, else the suggestion) and the suggestion."""
        try:
            return _canon_tools.text_target(project_dir, path, flavour)
        except _canon_tools.TextTargetError as e:
            raise HTTPException(e.status, str(e)) from None

    def _twin_already_fresh(t: dict[str, Any], what: str) -> bool:
        if _canon_derive.twin_state(t["target"], t["flavour"]) != "fresh":
            return False
        hdr = _canon.twin_header(t["twin"])
        if what == "atem":
            atem = hdr.get("atem") if isinstance(hdr.get("atem"), dict) else {}
            return isinstance(atem.get("line"), str) and bool(atem["line"].strip())
        derived = hdr.get("derived") if isinstance(hdr.get("derived"), dict) else {}
        return derived.get("completeness") == "full"

    def _body_route(body: dict[str, Any]) -> str:
        """The request's `route` (`local` | `cloud`); `local` when it says none
        (pins P6: nothing reaches a cloud model that the person did not choose
        for that job, whatever slot the chat is on); 400 for anything else."""
        try:
            return _canon_tools.check_route(body.get("route")) or "local"
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    def _local_reachable() -> tuple[bool, str]:
        if _agent_free.enabled():
            return False, _agent_free.REASON
        ok, why = _llm.check_llm_reachable(session.llm_url or _llm.DEFAULT_LLM_URL)
        if ok and why == "loading":
            return False, "the model is still loading"
        return ok, why

    async def _canon_mode(route: str | None = None) -> tuple[str, str]:
        """Model or rules, decided once, before the job starts (plan §3.8).
        Agent-free mode is rules with `why == "agent-free"` (`llm.reachable`).

        `route` (pins P6): None is `local` (0.6, S2: a job no one chose the
        cloud for never asks it); `local` asks llama-server whatever slot the
        chat is on; `cloud` asks the broker's gate and, when it is shut,
        refuses the request (403) in the gate's own words — never a silent
        fall back to a scaffold or to the local model."""
        route = route or "local"
        if route == "cloud":
            if _agent_free.enabled():
                return "rules", _agent_free.REASON
            try:
                gate = await asyncio.to_thread(_cloud.gate_status)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(403, f"the cloud gate could not be read ({e})") from None
            if not gate.get("open"):
                raise HTTPException(403, gate.get("denial") or gate.get("reason") or "the cloud gate is shut")
            return "model", f"cloud ({gate.get('model_id') or 'openrouter'})"
        if _llm._current_slot() == "opro-api":
            ok, why = await asyncio.to_thread(_local_reachable)
            return ("model", why) if ok else ("rules", why)
        ok, why = await asyncio.to_thread(_llm.reachable, session.llm_url)
        return ("model", why) if ok else ("rules", why)

    def _agent_free_reason(mode: str, why: str) -> str | None:
        """`"agent-free"` for a rules job agent-free mode chose, else None —
        the job's `reason`, which the UI labels "agent-free" rather than
        "scaffold, no model"."""
        return _agent_free.REASON if mode == "rules" and why == _agent_free.REASON else None

    def _canon_start_message(mode: str, why: str, doing: str) -> str:
        if mode == "model":
            return doing
        if _agent_free_reason(mode, why):
            return f"agent-free: {doing} by rules"
        return f"no model is answering ({why}); writing an outline"

    def _rules_note(why: str) -> str:
        return (" (by rules: agent-free)" if why == _agent_free.REASON
                else " (an outline: no model read it)")

    def _model_complete(messages: list[dict[str, str]], **kw: Any) -> tuple[str, dict[str, Any]]:
        """The engine's `complete`: `llm.complete` at the session's model
        (looked up at call time, so tests can stand in for it), with the
        engine's own `max_tokens` when it gives one (EMF passages: 4,096,
        bounded by the model's window). A model that stops answering mid-job
        fails the job in words; the engine never falls back to rules halfway.

        Always this machine's model (0.6, S2, pins P6): while the chat runs on
        the cloud slot it is llama-server through `model_route`'s local route,
        never `llm.complete`'s cloud path (Thym's reading takes this too)."""
        kw = {k: v for k, v in kw.items() if k == "max_tokens"}
        try:
            if _llm._current_slot() == "opro-api":
                return _model_route.make_complete("local", llm_url=session.llm_url or _llm.DEFAULT_LLM_URL)(
                    messages, **kw)
            return _llm.complete(messages, llm_url=session.llm_url, **kw)
        except _llm.LLMUnavailable as e:
            raise RuntimeError(f"the model became unavailable ({e}); nothing was written, run it again") from e
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"the model stopped answering ({e}); nothing was written, run it again") from e

    def _job_complete(route: str | None, source: str) -> Callable[..., tuple[str, dict[str, Any]]]:
        """The `complete` one job uses, by its route (pins P6, `model_route`):
        None is `local` (0.6, S2); `local` while the chat is local is
        `_model_complete` (`llm.complete`, whose meta says `route: local`);
        `local` while the chat runs on the cloud slot is llama-server through
        the factory; `cloud` is the factory's cloud route (gate, cache with
        `source`, the broker's journal). A refusal (agent-free, a gate shut
        mid-job) fails the job in the refusal's own words; nothing is written."""
        route = route or "local"
        if route == "local" and _llm._current_slot() != "opro-api":
            return _model_complete
        inner = _model_route.make_complete(route, llm_url=session.llm_url, project_dir=project_dir,
                                           source=source)

        def complete(messages: list[dict[str, str]], **kw: Any) -> tuple[str, dict[str, Any]]:
            kw = {k: v for k, v in kw.items() if k == "max_tokens"}
            try:
                return inner(messages, **kw)
            except _model_route.RouteRefused as e:
                raise RuntimeError(f"{e}; nothing was written") from e
            except _llm.LLMUnavailable as e:
                raise RuntimeError(f"the model became unavailable ({e}); nothing was written, run it again") from e
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"the model stopped answering ({e}); nothing was written, run it again") from e

        return complete

    def _emf_work(t: dict[str, Any], mode: str, why: str = "",
                  route: str | None = None) -> Callable[[Any], dict[str, Any]]:
        """Decompile the text into its twin of `t["flavour"]`, written under the
        flavour's name (`replace_twin`): an old-named twin is the `previous`
        (its pinned atems and its `shorts:` carried over) and is removed once
        the new one loads clean."""
        complete = _job_complete(route, "fabula") if mode == "model" else None

        def work(ctx: Any) -> dict[str, Any]:
            text, stat = _canon_derive.read_source(t["target"])
            twin = t["twin"]
            previous = twin.read_text(encoding="utf-8") if _canon.is_emf_twin(twin) else None
            cosm, info = _canon_derive.derive_emf(
                text, source_name=t["target"].name, source_stat=stat, rel_path=t["id_rel"],
                complete=complete, by="person", on_progress=ctx.progress, should_stop=ctx.should_stop,
                previous=previous, flavour=t["flavour"], route=_job_route(mode, route),
                copyable=bool(t.get("copyable")))
            ctx.check()
            ctx.progress(phase="writing", message=f"writing {t['new_twin'].name}")
            wrote = _canon_derive.replace_twin(t["target"], t["flavour"], cosm)
            _canon_catalog_after(t["text_rel"])
            note = _rules_note(why) if info["mode"] == "rules" else ""
            return {"twin_path": t["new_twin_rel"], "text_path": t["text_rel"], "mode": info["mode"],
                    "model": info["model"], "route": info.get("route"), "provider": info.get("provider"),
                    "flavour": t["flavour"], "suggested": t["suggested"], "replaced": wrote["removed"],
                    "chunks": info["chunks"], "items": info["items"],
                    "counts": info["counts"], "dropped": info["dropped"], "normalized": info["normalized"],
                    "continued": info["continued"], "atem": info["atem"],
                    "state": _canon_derive.twin_state(t["target"], t["flavour"]),
                    "message": f"wrote {t['new_twin'].name}{note}"}
        return work

    def _file_atem_work(t: dict[str, Any], mode: str,
                        route: str | None = None) -> Callable[[Any], dict[str, Any]]:
        complete = _job_complete(route, "atem") if mode == "model" else None

        def work(ctx: Any) -> dict[str, Any]:
            text, stat = _canon_derive.read_source(t["target"])
            title = _canon_derive.text_title(text, t["target"].name)
            atem = _canon_derive.derive_atem(
                text, context=f"the whole of {title}", complete=complete,
                on_progress=ctx.progress, should_stop=ctx.should_stop)
            ctx.check()
            ctx.progress(phase="writing", message=f"writing the atem into {t['twin'].name}")
            twin = t["twin"]
            existing = twin.read_text(encoding="utf-8") if _canon.is_emf_twin(twin) else None
            cosm = _canon_derive.set_file_atem(
                existing, atem, source_name=t["target"].name, source_stat=stat, rel_path=t["id_rel"],
                by="person", model=atem.get("model"), title=title, flavour=t["flavour"],
                route=atem.get("route") or _job_route(atem["mode"], route), provider=atem.get("provider"))
            _canon_derive.write_twin(twin, cosm)
            _canon_catalog_after(t["text_rel"])
            return {"twin_path": t["twin_rel"], "text_path": t["text_rel"], "mode": atem["mode"],
                    "model": atem.get("model"), "route": atem.get("route"), "flavour": t["flavour"],
                    "suggested": t["suggested"], "atem": _canon_derive.atem_block(atem),
                    "stance_profile": atem.get("stance_profile") or {}, "written": True,
                    "state": _canon_derive.twin_state(t["target"], t["flavour"]),
                    "message": f"wrote the atem into {twin.name}"}
        return work

    def _passage_atem_work(text: str, mode: str, *, t: dict[str, Any] | None,
                           selection: dict[str, Any] | None,
                           why: str = "", route: str | None = None) -> Callable[[Any], dict[str, Any]]:
        complete = _job_complete(route, "atem") if mode == "model" else None

        def work(ctx: Any) -> dict[str, Any]:
            context = None
            span = None
            if t is not None:
                whole, _stat = _canon_derive.read_source(t["target"])
                context = f"a passage of {_canon_derive.text_title(whole, t['target'].name)}"
                span = _canon_derive.passage_span(whole, selection or {"text": text})
            atem = _canon_derive.derive_atem(
                text, context=context, complete=complete,
                on_progress=ctx.progress, should_stop=ctx.should_stop)
            out = {**_canon_derive.atem_block(atem), "stance_profile": atem.get("stance_profile") or {},
                   "mode": atem["mode"], "model": atem.get("model"), "route": atem.get("route"), "written": False,
                   "pinnable": t is not None, "path": t["text_rel"] if t else None, "span": span,
                   "message": "the atem is ready" + (_rules_note(why)
                                                     if atem["mode"] == "rules" else "")}
            return out
        return work

    def _job_route(mode: str, route: str | None) -> str | None:
        """The route a job's record says: none in rules mode; the one asked; else
        `local` (0.6, S2: no route is the local route)."""
        if mode != "model":
            return None
        return route or "local"

    def _start_canon_job(*, kind: str, path: str | None, mode: str, why: str, work: Any,
                         key: str | None, doing: str, route: str | None = None,
                         flavour: str | None = None, what: str | None = None,
                         extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start one job. A model-mode job holds the generation lock (llama-server's
        one slot) unless it runs on the cloud route (`model_route.holds_generation_lock`);
        a job with no route asked is local (it holds the lock). The
        record says the job's `route` (model mode) and `flavour` (a decompile,
        a compile), and for a compile `what` (`code`, `line`, `overview`,
        `manual`, `short`: 0.6, S2); `extra` adds fields of the caller's (a
        build's first `progress`), each said only when known."""
        reason = _agent_free_reason(mode, why)
        if reason:
            # The result says why too, beside its `mode: rules`.
            inner = work

            def work(ctx: Any) -> Any:
                out = inner(ctx)
                if isinstance(out, dict):
                    out["reason"] = reason
                return out
        try:
            snap = canon_jobs.start(
                kind=kind, path=path, mode=mode, work=work, key=key,
                lock=(session.generation_lock if mode == "model"
                      and _model_route.holds_generation_lock(route or "local") else None),
                message=_canon_start_message(mode, why, doing), reason=reason,
                extra=({"route": _job_route(mode, route), "flavour": flavour, "what": what, **(extra or {})}
                       if kind in ("emf", "atem", "compile", "fabulac", "dialectic", "fabulap", "fabulam")
                       else None))   # Thym's runs: their lane's
        except _canon_jobs.CanonJobError as e:
            raise _canon_job_http(e) from None
        return {"job": snap}

    @router.post("/api/fabula/derive")
    async def api_canon_derive(request: Request) -> dict[str, Any]:
        """Derive a text's twin, its fabula (`what: fabula`), or its file atem (`what: atem`) as a background
        job: `{path, what,
        force?, flavour?, route?}` → `{job, flavour, suggested}`. `flavour` is
        `fabulan` or `fabulap` (absent: the twin's own, else the suggestion;
        `fabulac` is refused for a text); `route` is `local` or `cloud`
        (absent: `local`, this machine's model whatever slot the chat is on;
        `cloud` only with the broker's gate open, else 403 in the gate's
        words). 409 when the twin is already fresh (pass
        `force`), or a job for the file is queued or running. Model or rules is
        decided here, once."""
        body = await _json_body(request)
        what = str(body.get("what") or "fabula").strip().lower()
        what = _retired_names.word("what", what)
        if what not in ("fabula", "atem"):
            raise HTTPException(400, "what must be fabula or atem")
        what = "emf" if what == "fabula" else what            # the job's kind keeps its 0.4 name for the page
        route = _body_route(body)
        t = await asyncio.to_thread(_text_target, str(body.get("path") or ""), body.get("flavour"))
        t["copyable"] = body.get("copyable") is True          # a fabulap's lines keep their words (18.4.6)
        if not body.get("force") and await asyncio.to_thread(_twin_already_fresh, t, what):
            said = "its atem is" if what == "atem" else f"{t['twin'].name} is"
            raise HTTPException(409, f"already fresh: {said} up to date with {t['target'].name}; "
                                     "pass force to derive it again")
        mode, why = await _canon_mode(route)
        work = _emf_work(t, mode, why, route) if what == "emf" else _file_atem_work(t, mode, route)
        doing = (f"deriving the fabula of {t['target'].name}" if what == "emf"
                 else f"writing the atem of {t['target'].name}")
        out = _start_canon_job(kind=what, path=t["text_rel"], mode=mode, why=why, work=work,
                               key=t["key"], doing=doing, route=route, flavour=t["flavour"])
        return {**out, "flavour": t["flavour"], "suggested": t["suggested"]}

    @router.post("/api/canon/atem")
    async def api_canon_atem(request: Request) -> dict[str, Any]:
        """An atem, as a job: `{path}` = the whole file's (written into its
        twin's `atem:` block; a minimal twin when there is none); `{path,
        selection: {text, start?, end?, lines?}}` = a passage's (not written;
        the result is `pinnable` and carries a `span` for the pin); `{text}`
        (or a selection with no path) = an atem of that text, nothing written."""
        body = await _json_body(request)
        route = _body_route(body)
        path = str(body.get("path") or "").strip()
        selection = body.get("selection")
        if selection is not None and not isinstance(selection, dict):
            raise HTTPException(400, "selection must be {text, start?, end?, lines?}")
        sel_text = selection.get("text") if isinstance(selection, dict) else None
        if sel_text is not None and not isinstance(sel_text, str):
            raise HTTPException(400, "selection.text must be text")
        if path and not (sel_text or "").strip():
            t = await asyncio.to_thread(_text_target, path, body.get("flavour"))
            mode, why = await _canon_mode(route)
            return _start_canon_job(kind="atem", path=t["text_rel"], mode=mode, why=why,
                                    work=_file_atem_work(t, mode, route), key=t["key"],
                                    doing=f"writing the atem of {t['target'].name}", route=route,
                                    flavour=t["flavour"])
        text = sel_text if (sel_text or "").strip() else body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(400, "nothing to make an atem of: give a path, a selection or a text")
        if len(text) > CANON_ATEM_TEXT_MAX:
            raise HTTPException(400, "that passage is too long for an atem on the spot; derive the file instead")
        t = await asyncio.to_thread(_text_target, path, body.get("flavour")) if path else None
        mode, why = await _canon_mode(route)
        return _start_canon_job(kind="atem", path=t["text_rel"] if t else None, mode=mode, why=why,
                                work=_passage_atem_work(text, mode, t=t, selection=selection, why=why, route=route),
                                key=None,
                                doing="writing the atem of the passage", route=route)

    @router.post("/api/canon/atem/pin")
    async def api_canon_atem_pin(request: Request) -> dict[str, Any]:
        """Pin a passage's atem into the text's twin as `X:atem/<n>`:
        `{path, atem: {line, focus, push, pull}, span, of?}` → `{twin_path,
        item_id, job}` (synchronous; a minimal twin when there is none). 409
        while a job for the file is queued or running."""
        body = await _json_body(request)
        atem = body.get("atem")
        if not isinstance(atem, dict) or not isinstance(atem.get("line"), str) or not atem["line"].strip():
            raise HTTPException(400, "atem must be {line, focus, push, pull} with a line")
        for part in ("focus", "push", "pull"):
            v = atem.get(part)
            if v is not None and not isinstance(v, str) and not _macrocosm.is_pending(v):
                raise HTTPException(400, f"atem.{part} must be text or {{pending: \"...\"}}")
        span = _canon_derive.clean_span(body.get("span"))
        if span is None:
            raise HTTPException(400, 'span must say where the passage is: {lines: "a-b"} or {start, end}')
        of = body.get("of")
        if of is not None and not (isinstance(of, list) and all(isinstance(x, str) for x in of)):
            raise HTTPException(400, "of must be a list of item ids")
        t = await asyncio.to_thread(_text_target, str(body.get("path") or ""), body.get("flavour"))

        def _pin() -> str:
            with canon_jobs.holding(t["key"], t["text_rel"]):
                text, stat = _canon_derive.read_source(t["target"])
                twin = t["twin"]
                existing = twin.read_text(encoding="utf-8") if _canon.is_emf_twin(twin) else None
                item_id = _canon_derive.next_atem_id(existing)
                cosm = _canon_derive.pin_atem(
                    existing, atem, span, source_name=t["target"].name, source_stat=stat,
                    rel_path=t["id_rel"], of=of, by="person",
                    title=_canon_derive.text_title(text, t["target"].name), flavour=t["flavour"])
                _canon_derive.write_twin(twin, cosm)
                _canon_catalog_after(t["text_rel"])
                return item_id

        try:
            item_id = await asyncio.to_thread(_pin)
        except _canon_jobs.CanonJobError as e:
            raise _canon_job_http(e) from None
        except _canon_derive.DeriveError as e:
            raise HTTPException(400, str(e)) from None
        block = _canon_derive.atem_block(atem)
        mode = "rules" if any(_macrocosm.is_pending(block[p]) for p in ("push", "pull")) else "model"
        result = {"twin_path": t["twin_rel"], "item_id": item_id, "text_path": t["text_rel"]}
        snap = canon_jobs.record(kind="pin", path=t["text_rel"], mode=mode, result=result,
                                 message=f"pinned {item_id} to {t['twin'].name}")
        return {"twin_path": t["twin_rel"], "item_id": item_id, "job": snap}

    @router.get("/api/fabula/twin")
    async def api_canon_emf(path: str = Query(...), flavour: str | None = Query(None)) -> dict[str, Any]:
        """A text's twin for the reader and the viewer : `{twin_path, state:
        fresh|stale, flavour, twins: {flavour: {path, state}}, suggested, cosm:
        <the /api/cosm payload>}`; 404 when the text has none. Takes the text
        (or a twin itself, `.fabulan.cosm`, `.fabulap.cosm` or the old `.cosm`;
        a converted original is read through its markdown twin). A text with
        a twin of each flavour shows the one derived last (or the one named,
        `flavour=`); `twins` names both."""

        def _build() -> dict[str, Any]:
            rel = _canon_rel(path)
            if not rel or rel in STORE_PREFIXES:
                raise HTTPException(400, "missing path")
            target = _resolve_project_path(rel)
            asked = (flavour or "").strip().lower() or None
            if asked is not None and asked not in _fabula_names.TEXT_FLAVOURS:
                raise HTTPException(400, "flavour must be fabulan or fabulap")
            of_twin = _fabula_names.text_of_twin(target) if target.name.endswith(".cosm") else None
            if of_twin is not None:
                text, head = of_twin, rel[: len(rel) - len(target.name)]
                twin = target
            else:
                if not target.exists():
                    raise HTTPException(404, f"no such file: {rel}")
                text_rel = rel
                if (target.is_file() and target.suffix.lower() not in _canon_derive.TEXT_SUFFIXES
                        and _convert.is_convertible(target) and _convert.twin_path(target).is_file()):
                    target, text_rel = _convert.twin_path(target), rel + ".md"
                text, head = target, text_rel[: len(text_rel) - len(target.name)]
                twin = _fabula_names.find_twin(target, asked)
            if twin is None or not _canon.is_emf_twin(twin):
                raise HTTPException(404, f"{rel} has no fabula yet")
            twins = _fabula_names.text_twins(text)
            fl = next((f for f, p in twins.items() if p == twin), _fabula_names.flavour_of_twin(twin))
            twin_rel = head + twin.name
            try:
                raw = text.read_bytes().decode("utf-8-sig", errors="replace")
                suggested = _fabula_names.suggest_flavour(raw)
            except OSError:
                suggested = None
            vol = _macrocosm.load_volume(twin)
            return {"twin_path": twin_rel, "state": _canon.emf_state(text, twin), "flavour": fl,
                    "twins": {f: {"path": head + p.name, "state": _canon.emf_state(text, p)}
                              for f, p in twins.items()},
                    "suggested": suggested, "cosm": _cosm_payload(vol, twin_rel)}

        return await asyncio.to_thread(_build)

    @router.get("/api/fabula/transconception")
    async def api_fabula_transconception(path: str = Query(...)) -> dict[str, Any]:
        """0.8 (lane W4-X7): the transconception card of a fabulac (`enough.transconception.card`), read only: the two
        gates with each check held or not and why, the rulings queue, the ground with what came of each citation in
        the language library, the targets with their twelve points and gaps, and each cshort with its target, apart or
        beside, its layout and its evidence. Takes the fabulac or the folder it was built from; a fabulac kept for no
        transconception answers `{transconception: false}`. Nothing is run, built or written."""
        from .. import fabulac_job as _fj
        from .. import transconception as _tc

        def _build() -> dict[str, Any]:
            try:
                fab = _fj.fabulac_of(Path(project_dir), path)
            except _fj.BuildError as e:
                raise HTTPException(e.status, str(e)) from None
            return {"path": _fj.rel_of(Path(project_dir), fab), **_tc.card(fab)}

        return await asyncio.to_thread(_build)

    @router.get("/api/fabula/suggest")
    async def api_fabula_suggest(path: str = Query(...)) -> dict[str, Any]:
        """The flavour suggested for a text (0.6, S2), twin or none: `{path,
        suggested: fabulan | fabulap, why}` by the one rule
        (`fabula_names.suggest_flavour`). The text is the one the twin route
        reads (a twin's path reads its text; a converted original its
        markdown twin). Refusals as the twin route's for a bad path (400
        missing or invalid, 404 no such file), and 400 for a folder or a file
        that is not text."""

        def _build() -> dict[str, Any]:
            rel = _canon_rel(path)
            if not rel or rel in STORE_PREFIXES:
                raise HTTPException(400, "missing path")
            target = _resolve_project_path(rel)
            of_twin = _fabula_names.text_of_twin(target) if target.name.endswith(".cosm") else None
            if of_twin is not None:
                target = of_twin
            if not target.exists():
                raise HTTPException(404, f"no such file: {rel}")
            if target.is_dir():
                raise HTTPException(400, f"{rel} is a folder; a flavour is suggested for a text")
            if (target.suffix.lower() not in _canon_derive.TEXT_SUFFIXES
                    and _convert.is_convertible(target) and _convert.twin_path(target).is_file()):
                target = _convert.twin_path(target)
            try:
                raw = target.read_bytes().decode("utf-8-sig")
            except (OSError, UnicodeDecodeError):
                raise HTTPException(400, f"{rel} could not be read as text") from None
            suggested = _fabula_names.suggest_flavour(raw)
            why = ("it reads as verse: short lines in stanzas, with no heading, code fence or table"
                   if suggested == "fabulap" else "it reads as prose")
            return {"path": rel, "suggested": suggested, "why": why}

        return await asyncio.to_thread(_build)

    @router.get("/api/fabula/models")
    async def api_fabula_models() -> dict[str, Any]:
        """The model line's facts in one call (0.6, S2), read as
        `thym_host.route_info` reads them: `{agent_free, local: {running,
        model, window}, cloud: {open, model, window, reason}}`. Agent-free
        reads nothing (no gate, no llama-server). The cloud gate is read once;
        its model and window are said only while it is open. Never a key or
        a secret; a model that is down is a fact here, not an error."""
        from .. import thym_host as _host

        def _build() -> dict[str, Any]:
            if _agent_free.enabled():
                return {"agent_free": True,
                        "local": {"running": False, "model": None, "window": None},
                        "cloud": {"open": False, "model": None, "window": None,
                                  "reason": "agent-free mode is on"}}
            running, _why = _local_reachable()
            local = _host.route_info("local", llm_url=session.llm_url) if running else {}
            if not running:
                slot = _host.current_model()
                local = {"model": slot} if slot not in ("none", "opro-api") else {}
            cloud = _host.route_info("cloud")
            gate = cloud.get("gate") or {}
            is_open = bool(gate.get("open"))
            reason = None if is_open else _plain_gate_reason(gate.get("reason"))
            return {"agent_free": False,
                    "local": {"running": bool(running), "model": local.get("model"),
                              "window": local.get("window")},
                    "cloud": {"open": is_open, "model": cloud.get("model") if is_open else None,
                              "window": cloud.get("window") if is_open else None, "reason": reason}}

        return await asyncio.to_thread(_build)

    def _plain_gate_reason(reason: Any) -> str:
        """The gate's short clause, with no provider named (a reply's prose names no vendor)."""
        import re
        said = str(reason or "the cloud is shut")
        return re.sub(r"\bno \S+ key is configured\b", "no cloud key is configured", said)

    async def _compile_short(body: dict[str, Any]) -> dict[str, Any]:
        """Compile a text's fabula (`fabula/1`, or `emf/1`) into a SHORT as a job (plan §15);
        `POST /api/fabula/compile` (enough/fabulac_job.py) hands it every fabula that is not a fabulac:
        `{path, order?}` → `{job}`, result `{written, emf_path, mode, order,
        model, recorded}`. `order` is `told` (the author's order, by span) or
        `weight` (by salience); absent, `told` when the EMF names a source
        text that can be read, else `weight`. The short is a new file beside
        the EMF, `<stem>.short-YYYY-MM-DD-HHMM.md` (`-2`, `-3`: never an
        overwrite); the text is never touched, and the EMF only gains the
        short in its `shorts:` list (`record_short`, byte-stable otherwise).
        A twin's compile holds its text's claim, the one a decompile of that
        text holds, so the two never write the twin at once."""
        route = _body_route(body)
        order = body.get("order")
        if order is not None and not isinstance(order, str):
            raise HTTPException(400, "order must be told or weight")
        order = (order or "").strip().lower() or None
        if order is not None and order not in _canon_derive.ORDERS:
            raise HTTPException(400, f"order must be told or weight, not {order!r}")
        rel = _canon_rel(str(body.get("path") or ""))
        if not rel or rel in STORE_PREFIXES:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(rel)

        def _vet() -> tuple[Path | None, str, str]:
            if not target.exists():
                raise HTTPException(404, f"no such file: {rel}")
            if target.is_dir() or not target.name.endswith(".cosm"):
                raise HTTPException(400, f"{target.name} is not a fabula; compile reads a fabula's .cosm file")
            said = _macrocosm.sniff_declaration(target)
            if said not in _canon_derive.FABULA_DECLARATIONS:
                raise HTTPException(400, f"{target.name} is not a fabula (it declares {said or 'nothing'}); "
                                         "compile reads a fabula (fabula/1, or its old spelling emf/1)")
            vol = _macrocosm.load_volume(target)
            if vol.refused is not None:
                raise HTTPException(400, str(vol.refused))
            text = _canon_derive.source_path(target, vol)
            readable = False
            if text is not None:
                try:
                    _canon_derive.read_source(text)
                    readable = True
                except OSError:
                    readable = False
            fl = _canon.twin_header(target).get("flavour")
            fl = fl if fl in _fabula_names.TEXT_FLAVOURS else "fabulan"      # emf/1, or a fabula that says none
            return (text if readable else None), _canon_derive.default_order(vol, source_readable=readable), fl

        text_path, default, flavour = await asyncio.to_thread(_vet)
        order = order or default
        mode, why = await _canon_mode(route)
        complete = _job_complete(route, "compile") if mode == "model" else None
        # The twin of a text shares the text's claim (canon_tools.text_target's
        # key: the resolved text), so a decompile and a compile never write it
        # at once; a standalone fabula is claimed by its own path.
        of_text = _fabula_names.text_of_twin(target)
        key = str(of_text) if of_text is not None else str(target)

        def work(ctx: Any) -> dict[str, Any]:
            ctx.progress(phase="compiling", message=f"compiling {target.name}")
            now = dt.datetime.now(dt.timezone.utc)
            source_text = None
            if text_path is not None:
                try:
                    source_text, _stat = _canon_derive.read_source(text_path)
                except OSError:
                    source_text = None
            md, info = _canon_derive.compile_short(
                _macrocosm.load_volume(target), complete=complete,
                source_name=target.name, order=order, source_text=source_text, now=now)
            short_route = info.get("route") or (_job_route(mode, route) if info["mode"] == "model" else None)
            ctx.check()
            out = _canon_derive.short_path(target, now)
            ctx.progress(phase="writing", message=f"writing {out.name}")
            _canon_derive.write_atomic(out, md)
            recorded = True
            try:
                twin_text = target.read_bytes().decode("utf-8")       # bytes: CRLF kept as it is
                _canon_derive.write_atomic(target, _canon_derive.record_short(
                    twin_text, path=out.name, at=now, by=info["by"], mode=info["mode"], order=info["order"],
                    route=short_route))
            except (OSError, UnicodeDecodeError, _canon_derive.DeriveError) as e:
                recorded = False
                log.warning("canon: wrote %s but could not record it in %s (%s)", out.name, target.name, e)
            _canon_catalog_after(rel)
            return {"written": _rel_beside(rel, out.name), "fabula_path": rel, "emf_path": rel, "mode": info["mode"],
                    "order": info["order"], "model": info["model"], "route": short_route, "recorded": recorded,
                    "message": f"wrote {out.name}"}

        return _start_canon_job(kind="compile", path=rel, mode=mode, why=why, work=work,
                                key=key, doing=f"compiling {target.name}", route=route,
                                flavour=flavour, what="short")

    @router.get("/api/canon/job/{job_id}")
    async def api_canon_job(job_id: str) -> dict[str, Any]:
        """One derivation job's snapshot (the same payload as its `canon` SSE events)."""
        try:
            return canon_jobs.snapshot(job_id)
        except _canon_jobs.CanonJobError as e:
            raise _canon_job_http(e) from None

    @router.post("/api/canon/job/{job_id}/cancel")
    async def api_canon_job_cancel(job_id: str) -> dict[str, Any]:
        """Cancel a job: a queued one never starts; a running one finishes the
        passage it is reading, then stops without writing (its snapshot says
        `cancelling` until then). 409 when it is not queued or running."""
        try:
            return canon_jobs.cancel(job_id)
        except _canon_jobs.CanonJobError as e:
            raise _canon_job_http(e) from None

    ctx._canon_catalog_after = _canon_catalog_after
    ctx._canon_mode = _canon_mode
    ctx._compile_short = _compile_short
    ctx._model_complete = _model_complete
    ctx._start_canon_job = _start_canon_job
    ctx._text_target = _text_target
    ctx.canon_jobs = canon_jobs
    return router
