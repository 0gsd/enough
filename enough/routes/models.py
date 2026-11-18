"""Models: the cloud slot (`/api/cloud/*`), the local models and their downloads (`/api/models*`, `/api/model`), the llama server's status, and transcription (`/api/transcribe`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from .. import agent_free as _agent_free
from .. import broker as _broker
from .. import cloud as _cloud
from .. import models as _models
from .. import preflight as _preflight
from .common import AppContext
from ..server import WHISPER_DEFAULT_MODEL, WHISPER_DIR


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    llm_url = ctx.llm_url
    preflight = ctx.preflight
    session = ctx.session
    supervisor = ctx.supervisor

    # ---------------------- OpenRouter (OPRO-API) ------------------------
    # The fifth model slot. Gated by the `local_models_only` broker toggle
    # (default on); these endpoints work regardless of the toggle but the
    # UI only surfaces them when the toggle is off. The api key never
    # transits these endpoints in either direction except for the one-time
    # POST to /api/cloud/set-key — from there it lives in the OS keyring
    # and is accessed only by enough.cloud.

    @router.get("/api/cloud/status")
    async def api_cloud_status() -> dict[str, Any]:
        """Current OpenRouter status: enablement flag, model id, whether a
        key is present in the keyring, last verified result. NEVER returns
        the api key value itself."""
        from .. import cloud as _cloud
        return _cloud.status_snapshot()

    @router.post("/api/cloud/set-key")
    async def api_cloud_set_key(request: Request) -> dict[str, Any]:
        """Store or update the OpenRouter api key in the OS keyring, then
        run a fresh health check. Body: {"api_key": "sk-or-..."}. The key
        is validated against the OpenRouter prefix format before storage.
        Returns {"status": status_snapshot, "health": health_check_result}
        so the wizard / settings UI can show both in one round-trip."""
        from .. import cloud as _cloud
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        api_key = ((body or {}).get("api_key") or "").strip()
        if not api_key:
            raise HTTPException(400, "missing api_key")
        try:
            _cloud.set_api_key(api_key)
        except _cloud.CloudKeyringUnavailable as e:
            raise HTTPException(500, str(e)) from None
        except _cloud.CloudError as e:
            raise HTTPException(400, str(e)) from None
        if _agent_free.enabled():
            # Storing a key is configuring, and stays allowed; the check is a
            # prompt to a model, and waits until agent-free is off.
            health = {"ok": False, "model": _cloud.HEALTH_CHECK_MODEL,
                      "checked_at": None, "skipped": _agent_free.REASON,
                      "error": _agent_free.detail("the key is saved; the cloud "
                                                  "check waits until agent-free is off")}
        else:
            health = _cloud.health_check()
        return {"status": _cloud.status_snapshot(), "health": health}

    @router.post("/api/cloud/clear-key")
    async def api_cloud_clear_key() -> dict[str, Any]:
        """Remove the OpenRouter api key from the OS keyring and reset
        the verified-state metadata. Idempotent — safe to call when no
        key is present. Returns the post-clear status snapshot."""
        from .. import cloud as _cloud
        _cloud.clear_api_key()
        return _cloud.status_snapshot()

    @router.post("/api/cloud/health-check")
    async def api_cloud_health_check() -> dict[str, Any]:
        """Re-test the currently-stored api key against OpenRouter via the
        zero-cost `openrouter/free` auto-selector. Updates the on-disk
        last-verified metadata. Returns both the health result and the
        updated status snapshot."""
        from .. import cloud as _cloud
        health = _cloud.health_check()
        return {"status": _cloud.status_snapshot(), "health": health}

    @router.post("/api/cloud/set-model")
    async def api_cloud_set_model(request: Request) -> dict[str, Any]:
        """Update which OpenRouter model id chat completions go to. Body:
        {"model_id": "openrouter/auto"} or any slug from openrouter.ai/models.
        No client-side validation — OpenRouter has hundreds of models and the
        canonical list changes; unrecognized ids fail at request time with a
        clear 404 message."""
        from .. import cloud as _cloud
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        model_id = ((body or {}).get("model_id") or "").strip()
        if not model_id:
            raise HTTPException(400, "missing model_id")
        try:
            _cloud.set_model_id(model_id)
        except _cloud.CloudError as e:
            raise HTTPException(400, str(e)) from None
        return _cloud.status_snapshot()

    # ------------------------------------------------------------------
    # Models — the picker's view, the switch, and the in-app manager's
    # download/delete side. Download progress streams over the `model-dl`
    # SSE event; contract in docs/seven-models-plan.md §4.
    # ------------------------------------------------------------------

    from .. import model_download as _model_download

    model_dl = _model_download.ModelDownloadManager(emit=session.emit)

    @router.get("/api/models")
    async def api_models() -> dict[str, Any]:
        """Registry + per-model installed/recommended view + total RAM +
        supervisor status + the download manager's snapshot. When the
        `local_models_only` broker toggle is off, also injects a virtual
        OPRO-API entry at the end of the model list so the modal renders it
        as a fifth slot. The OPRO-API entry carries `cloud: True` plus
        cloud-specific status fields so the frontend can render and dispatch
        it differently from local models."""
        from .. import models as _models  # late import: avoid circular
        views = _models.all_models_view()
        payload: dict[str, Any] = {
            "total_ram_gb": _models.total_ram_gb(),
            "current": _models.load_state().get("current"),
            "models": views,
            "ctx_overrides": _models.load_state().get("ctx_overrides") or {},
            # Same shape as the `model-dl` event, so a page that loads
            # mid-download renders from this and then keeps up over SSE.
            "download": model_dl.state(views),
            # The installed llama.cpp b-release. Wave 3 addition: each entry
            # already carries `llama_cpp_min_release`, but that number means
            # nothing to the picker without what's actually on this machine to
            # compare it against — the model manager renders "needs llama.cpp
            # ≥ bNNNN" in place of the switch affordance off the pair. One
            # number for the whole payload rather than a per-model
            # `release_gate()` sentence, because release_gate() re-probes the
            # binary per call and seven subprocess spawns per picker open is
            # not worth a prettier string. Off-thread: it shells out to
            # `llama-server --version` (10 s timeout), and 0 means "no
            # llama.cpp on PATH", which gates every gated model — correctly.
            "llama_release": await asyncio.to_thread(_models.llama_release),
        }
        # Agent-free mode (§13): the model window greys its running controls
        # (switch, start) on this flag; downloads and deletes stay live.
        agent_free = _agent_free.enabled()
        payload["agent_free"] = agent_free
        payload["supervisor"] = supervisor.status() if supervisor else {
            "mode": _agent_free.REASON if agent_free else "off", "agent_free": agent_free}

        # Inject OPRO-API when cloud is unlocked. The model list is the
        # only frontend surface that needs to know about it; everything
        # else flows through /api/cloud/*.
        if not _broker.is_enabled("local_models_only"):
            from .. import cloud as _cloud
            cloud_status = _cloud.status_snapshot()
            payload["models"] = list(payload["models"]) + [{
                "cute": "opro-api",
                "label": "OpenRouter (cloud)",
                "family": "cloud",
                # `installed` doubles as the "can switch to this" flag in
                # the UI — true only when a key is present AND the most
                # recent health check passed.
                "installed": bool(
                    cloud_status["key_present"]
                    and cloud_status["last_verified_ok"]
                ),
                "path": None,
                "disk_gb_approx": None,
                "ram_gb_recommended_min": None,
                "ctx_max": None,
                "ctx_recommended": None,
                # cloud-only fields the frontend uses for rendering
                "cloud": True,
                "cloud_model_id": cloud_status["model_id"],
                "cloud_key_present": cloud_status["key_present"],
                "cloud_healthy": cloud_status["last_verified_ok"],
                "cloud_last_verified_at": cloud_status["last_verified_at"],
                "cloud_last_error": cloud_status["last_error"],
            }]
        return payload

    @router.get("/api/llm-status")
    async def api_llm_status() -> dict[str, Any]:
        """Lightweight poll target for the UI: is llama-server alive, what
        model is loaded, ready-for-requests? When OPRO-API is the active
        model, the supervisor's local-llama state is irrelevant — what
        matters is whether the cloud key is healthy."""
        # Agent-free mode first (§13): no model, whatever is installed or
        # chosen; the preflight is skipped, its verdict unknown.
        if _agent_free.enabled():
            return {"mode": _agent_free.REASON, "ready": False, "cute": None,
                    "ctx": None, "agent_free": True,
                    **_preflight_fields(skipped=True)}
        # Short-circuit: OPRO-API mode. Local llama-server may or may not
        # be running in the background; we report cloud-readiness instead.
        try:
            current = _models.load_state().get("current")
        except Exception:  # noqa: BLE001
            current = None
        if current == "opro-api":
            cloud_status = _cloud.status_snapshot()
            return {
                "mode": "cloud",
                "ready": bool(cloud_status["key_present"] and cloud_status["last_verified_ok"]),
                "cute": "opro-api",
                "ctx": None,
                "cloud_model_id": cloud_status["model_id"],
                "cloud_healthy": cloud_status["last_verified_ok"],
                "cloud_last_error": cloud_status["last_error"],
                "agent_free": False,
                # The context preflight does not measure the cloud.
                **_preflight_fields(skipped=True),
            }
        if supervisor is None:
            # Non-supervised mode: best-effort probe of /health.
            try:
                async with httpx.AsyncClient(timeout=2.0) as c:
                    r = await c.get(llm_url.rstrip("/") + "/health")
                return {"mode": "external", "ready": r.status_code == 200, "cute": None, "ctx": None,
                        "agent_free": False, **_preflight_fields()}
            except httpx.HTTPError:
                return {"mode": "external", "ready": False, "cute": None, "ctx": None,
                        "agent_free": False, **_preflight_fields()}
        # The preflight fields (docs/ctx-16gb-plan.md §8.3) ride on every
        # shape of this payload: prompt_tokens, n_ctx, reserve, fits,
        # suggest_ctx, fix, fix_reason, preflight.
        return {**supervisor.status(), **_preflight_fields()}

    def _preflight_fields(*, skipped: bool = False) -> dict[str, Any]:
        """`skipped`: the cloud, or agent-free mode — nothing of ours to measure."""
        # `profile` is the preflight's choice for the empty conversation;
        # `prompt_profile` the one the last turn actually sent (0.5.1).
        sent = {"prompt_profile": getattr(session, "prompt_profile", None)}
        if preflight is None or skipped:
            return {"prompt_tokens": None, "n_ctx": None,
                    "reserve": _preflight.RESERVE, "fits": None,
                    "suggest_ctx": None, "fix": None, "fix_reason": None,
                    "profile": None,
                    "preflight": "skipped" if skipped else "idle", **sent}
        return {**preflight.fields(), **sent}

    @router.post("/api/model")
    async def api_model_switch(request: Request) -> dict[str, Any]:
        """Swap the loaded model and/or ctx. Body: {"cute": "g40-04",
        "ctx": 16384 (optional)}. Returns supervisor status; the UI
        should poll /api/llm-status for readiness.

        Special case for "opro-api" (the OpenRouter cloud slot): there's
        no llama-server to restart — we just persist the selection via
        `models.save_state` and return a synthetic status. The supervisor
        keeps running its existing local model in the background; the
        actual cloud-routing of chat completions lands when llm.py is
        extended in phase 3. For phase 2 the selection is recorded so the
        UI flow is testable end-to-end."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cute = (body or {}).get("cute")
        ctx = (body or {}).get("ctx")
        if not cute:
            raise HTTPException(400, "missing 'cute' field")

        if cute == "opro-api":
            # gating: refuse if cloud is locked or the key isn't healthy.
            if _broker.is_enabled("local_models_only"):
                raise HTTPException(400, _broker.denial_local_models_only())
            from .. import cloud as _cloud
            from .. import models as _models  # late import: avoid circular
            status = _cloud.status_snapshot()
            if not status["key_present"]:
                raise HTTPException(400, _broker.denial_cloud_key_missing())
            if not status["last_verified_ok"]:
                raise HTTPException(
                    400,
                    _broker.denial_cloud_unhealthy(status["last_error"] or "unverified"),
                )
            # persist the selection. don't touch the supervisor — the
            # local llama-server keeps running for now. routing of chat
            # completions to OpenRouter is wired in phase 3.
            state = _models.load_state()
            state["current"] = "opro-api"
            _models.save_state(state)
            if preflight is not None:
                preflight.schedule("cloud")     # → skipped
            session.history.clear()
            session.last_usage = {}
            await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            return {
                "mode": "cloud",
                "ready": True,
                "cute": "opro-api",
                "cloud_model_id": status["model_id"],
                "note": (
                    "OPRO-API selected. routing to OpenRouter is "
                    "wired in the next update — until then, the model "
                    "badge reflects the selection but chat completions "
                    "still use the local model in the background."
                ),
            }

        if supervisor is None:
            raise HTTPException(
                400,
                "llama-server isn't supervised by this enough process — "
                "restart enough without --no-supervise to enable switching.",
            )
        # The verdict belongs to the model being replaced; the new one is
        # measured when it turns ready (supervisor.on_ready).
        if preflight is not None:
            preflight.invalidate()
        try:
            await supervisor.switch(str(cute), int(ctx) if ctx is not None else None)
        except RuntimeError as e:
            if preflight is not None:
                preflight.schedule("switch refused")   # the old model, if still up
            raise HTTPException(400, str(e)) from None
        except Exception as e:  # noqa: BLE001
            if preflight is not None:
                preflight.schedule("switch failed")
            raise HTTPException(500, f"switch failed: {e}") from None
        # Also clear in-memory conversation history — new model = fresh brain.
        session.history.clear()
        session.last_usage = {}
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return supervisor.status()

    @router.post("/api/models/download/{cute}")
    async def api_model_download(cute: str) -> dict[str, Any]:
        """Download a model's weights into ~/enough/weights: the main GGUF,
        then its MTP draft file automatically when the registry entry
        declares one. Returns `{"started": true, ...}` plus the opening
        progress snapshot; the rest arrives on the `model-dl` SSE event.

        Resumable — a `.part` file left by a cancel or a quit is continued
        with a ranged GET rather than re-fetched, across restarts. 404 for an
        unknown model, 409 when it's already installed or another download is
        running, 400 when the volume can't hold what's left."""
        try:
            snap = model_dl.start(cute)
        except KeyError:
            raise HTTPException(404, f"unknown model {cute!r}") from None
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None
        return {"started": True, **snap}

    @router.post("/api/models/download/{cute}/cancel")
    async def api_model_download_cancel(cute: str) -> dict[str, Any]:
        """Stop the running download and KEEP its partial file, so starting
        the same model again resumes from where it stopped. 409 when nothing
        is running, or when what's running is a different model. The stop
        itself lands at the next chunk boundary — the `model-dl` event with
        `status: "cancelled"` is what confirms it."""
        try:
            return model_dl.cancel(cute)
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None

    @router.post("/api/models/delete/{cute}")
    async def api_model_delete(cute: str) -> dict[str, Any]:
        """Remove a model's weights: main GGUF, MTP draft file, and any
        partial download. 404 for an unknown model or one with nothing on
        disk, 409 when it's the model currently in use (switch away first) or
        the one being downloaded (cancel first)."""
        try:
            return await asyncio.to_thread(model_dl.delete, cute)
        except KeyError:
            raise HTTPException(404, f"unknown model {cute!r}") from None
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None

    @router.post("/api/transcribe")
    async def api_transcribe(request: Request) -> dict[str, Any]:
        """Speech-to-text via whisper.cpp. Accepts a multipart/form-data POST
        with an 'audio' field containing a 16 kHz mono WAV blob. Returns
        {"text": "transcribed words"} on success."""
        import shutil as _shutil
        import subprocess as _sp
        import tempfile as _tempfile

        whisper_bin = _shutil.which("whisper-cli")
        if not whisper_bin:
            from .. import models as _m
            raise HTTPException(
                503,
                "whisper-cli not found on PATH. "
                + _m.install_hint(
                    mac="install it with `brew install whisper-cpp` or re-run bootstrap.sh.",
                    linux=(
                        "no distro packages whisper.cpp yet — build it from "
                        "https://github.com/ggml-org/whisper.cpp and put "
                        "`whisper-cli` on your PATH. Voice input is optional; "
                        "everything else works without it."
                    ),
                ),
            )
        model_path = WHISPER_DIR / WHISPER_DEFAULT_MODEL
        if not model_path.is_file():
            raise HTTPException(
                503,
                f"whisper model not found at {model_path}. re-run bootstrap.sh step 7 "
                "to download it.",
            )

        form = await request.form()
        blob = form.get("audio")
        if blob is None or not hasattr(blob, "read"):
            raise HTTPException(400, "missing 'audio' file part")
        data = await blob.read()
        if not data:
            raise HTTPException(400, "empty audio upload")

        # whisper-cli needs a file on disk. Temp-file the upload, pipe through,
        # discard.
        with _tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            in_path = Path(f.name)
        try:
            proc = await asyncio.to_thread(
                _sp.run,
                [
                    whisper_bin,
                    "-m", str(model_path),
                    "-f", str(in_path),
                    "-nt",              # no timestamps in output
                    "--no-prints",      # suppress progress spam
                    "-l", "en",         # English (matches base.en)
                    "--output-txt",     # write .txt next to the wav
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise HTTPException(
                    500,
                    f"whisper-cli failed (code {proc.returncode}): "
                    f"{proc.stderr[-400:] if proc.stderr else 'no stderr'}",
                )
            # whisper-cli writes <basename>.wav.txt alongside the input.
            txt_path = in_path.with_suffix(".wav.txt")
            if txt_path.is_file():
                text = txt_path.read_text(encoding="utf-8").strip()
                txt_path.unlink(missing_ok=True)
            else:
                # Fallback: some builds print to stdout.
                text = (proc.stdout or "").strip()
            return {"text": text}
        finally:
            in_path.unlink(missing_ok=True)

    return router
