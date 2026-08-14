"""Resumable GGUF downloads for the in-app model manager.

Modeled on [wikisink/download.py](wikisink/download.py) — ranged GET into a
`.part` file, progress fanned out over SSE, one active download per process,
cancel that leaves the partial alone — but written as a separate
implementation rather than a shared helper. The two managers agree on about
forty lines of byte-pump and disagree on everything around it: wikisink
persists progress into `wikisink.json` (a multi-hour archive download has to
survive a crash mid-run), registers an install on completion, and supports
pause; a model download is a two-phase sequence (main GGUF, then the optional
MTP draft), resumes purely off the `.part` file, and has no install registry
to touch. Sharing the pump would have bought ~40 lines at the cost of a shim
over both sets of semantics, and would have put a refactor through the one
download path where a regression costs the user a 49 GB re-fetch. Decision
recorded in docs/seven-models-plan.md under "Wave 2a".

Resume across restarts *is* the `.part` file: the registry supplies the URL
and the filename, so a partial needs no state record. Nothing here writes to
`~/enough/config`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from . import models as _models

log = logging.getLogger("enough.models")

CHUNK_SIZE = 1024 * 1024          # 1 MiB
EMIT_INTERVAL = 0.5               # seconds between SSE progress events
DISK_MARGIN = 1.05                # free-space margin over the remaining bytes
EVENT = "model-dl"                # SSE event name the model picker listens on

_G = 1024 ** 3
_M = 1024 ** 2

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class ModelDownloadError(RuntimeError):
    """User-facing refusal or failure. `status` is the HTTP code the endpoint
    should answer with — 409 for a state conflict (already installed, one
    already running, deleting the model in use), 400 for a request we can't
    satisfy (no room on the volume). Carried as an attribute rather than
    matched out of the prose, because there are four distinct refusals and
    the strings are user-facing copy that will get reworded."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def bytes_to_human(n: int) -> str:
    for suffix, size in (("GB", _G), ("MB", _M), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {suffix}".replace(".0 ", " ")
    return f"{n} B"


# ---------------------------------------------------------------------------
# Paths + what's left to fetch
# ---------------------------------------------------------------------------

def downloads_dir() -> Path:
    """Where `.part` files live. A subdirectory of the weights dir, so a
    partial download can never read as an installed model (`installed` is
    "is there a .gguf named exactly this in the weights dir")."""
    return _models.WEIGHTS_DIR / "downloads"


def part_path(filename: str) -> Path:
    return downloads_dir() / f"{filename}.part"


def _part_bytes(filename: str) -> int:
    try:
        return part_path(filename).stat().st_size
    except OSError:
        return 0


def pending_phases(info: dict) -> list[dict[str, Any]]:
    """The files still to fetch for a resolve()d model, in download order:
    the main GGUF, then the MTP draft when the entry declares one. Files
    already on disk are skipped — so a model whose main GGUF landed before
    the registry grew a draft companion downloads only the draft, and a
    fully-installed model yields an empty list (which start() refuses on).

    `expected_bytes` is the registry's approximation, used for the disk
    preflight and the opening progress anchor; the real total arrives with
    the response's Content-Length."""
    phases: list[dict[str, Any]] = []
    if not info["installed"]:
        phases.append({
            "phase": "main",
            "filename": info["filename"],
            "url": info["url"],
            "expected_bytes": int(float(info.get("disk_gb_approx") or 0.0) * _G),
        })
    if info.get("draft_filename") and not info.get("draft_installed"):
        phases.append({
            "phase": "draft",
            "filename": info["draft_filename"],
            "url": info["draft_url"],
            "expected_bytes": int(float(info.get("draft_disk_gb_approx") or 0.0) * _G),
        })
    return phases


def partials(views: list[dict] | None = None) -> dict[str, int]:
    """`{cute: bytes on disk}` for every model with a partial download —
    what the model picker renders as "resume" rather than "download". Pass
    an already-computed all_models_view() to avoid re-resolving."""
    out: dict[str, int] = {}
    try:
        views = views if views is not None else _models.all_models_view()
    except Exception:  # noqa: BLE001 — a broken registry isn't this call's problem
        return out
    for info in views:
        n = _part_bytes(info["filename"]) if info.get("filename") else 0
        if info.get("draft_filename"):
            n += _part_bytes(info["draft_filename"])
        if n:
            out[info["cute"]] = n
    return out


def _progress(done: int, total: int) -> dict[str, Any]:
    """The five progress fields every `model-dl` event carries."""
    return {
        "bytes_done": done,
        "bytes_total": total,
        "pct": round(100 * done / total, 1) if total else None,
        "human_done": bytes_to_human(done),
        "human_total": bytes_to_human(total) if total else None,
    }


def _idle_snapshot() -> dict[str, Any]:
    return {
        "cute": None, "label": None, "phase": None, "status": "idle",
        "filename": None, "bytes_done": 0, "bytes_total": 0, "pct": None,
        "human_done": None, "human_total": None, "rate_bps": 0, "eta_s": None,
        "installed": None, "draft_installed": None, "error": None,
    }


# ---------------------------------------------------------------------------
# Download manager — one per server process
# ---------------------------------------------------------------------------

class ModelDownloadManager:
    """One active GGUF download per server process.

    `start()` fetches a model's main GGUF and then, when the registry entry
    declares one, its MTP draft file — emitting `model-dl` events throughout.
    `cancel()` stops it and leaves the `.part` file in place, so the next
    `start()` picks up with a ranged GET instead of starting over.
    """

    def __init__(self, emit: EmitFn | None = None):
        self._emit = emit
        self._task: asyncio.Task | None = None
        self._cancel = False
        self._snap: dict[str, Any] = _idle_snapshot()

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    def state(self, views: list[dict] | None = None) -> dict[str, Any]:
        """Snapshot for `GET /api/models`: the same payload shape as the
        `model-dl` event, plus `active` and the resumable-partials map (so a
        reloaded page knows which rows offer "resume")."""
        return {"active": self.active, **self._snap, "partials": partials(views)}

    async def wait(self) -> None:
        """Await the in-flight download; no-op when idle. Never re-raises
        what the task already swallowed — failures land in
        `state()["error"]` and on the event stream."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    # -- control ----------------------------------------------------------

    def start(self, cute: str) -> dict[str, Any]:
        """Begin (or resume) `cute`'s download as a background task on the
        running loop; returns the opening progress snapshot.

        Raises KeyError for an unknown cute name (the endpoint answers 404)
        and ModelDownloadError otherwise, with `.status` set to 409 when the
        model is already installed or another download is running, 400 when
        the volume can't hold what's left."""
        info = _models.resolve(cute)
        if self.active:
            raise ModelDownloadError(
                f"{self._snap['label']} is downloading right now — cancel that "
                "first, or wait for it to finish. one at a time keeps the "
                "bandwidth and the disk predictable.", status=409)
        phases = pending_phases(info)
        if not phases:
            raise ModelDownloadError(
                f"{info['label']} is already installed", status=409)
        self.preflight(phases)
        self._cancel = False
        first = phases[0]
        self._snap = _idle_snapshot()
        snap = self._update(
            cute=info["cute"], label=info["label"], phase=first["phase"],
            filename=first["filename"], status="downloading",
            **_progress(_part_bytes(first["filename"]), first["expected_bytes"]),
        )
        self._task = asyncio.get_running_loop().create_task(self._run(info, phases))
        return snap

    def cancel(self, cute: str | None = None) -> dict[str, Any]:
        """Stop the running download, keeping its `.part` file for resume.
        `cute` guards a stale UI against cancelling a download the user
        started for some other model; None cancels whatever is running.

        Asynchronous by nature — the flag is noticed at the next chunk
        boundary, and the `model-dl` event with `status: "cancelled"` is what
        actually says it stopped."""
        if not self.active:
            raise ModelDownloadError("no model download is running", status=409)
        if cute is not None and cute != self._snap["cute"]:
            raise ModelDownloadError(
                f"{self._snap['cute']} is the download that's running, not {cute}",
                status=409)
        self._cancel = True
        return {"ok": True, "cute": self._snap["cute"], "cancelling": True}

    def delete(self, cute: str) -> dict[str, Any]:
        """Remove a model's weights: main GGUF, MTP draft, and any partial
        download. Blocking — call through asyncio.to_thread.

        The partial goes too: leaving an invisible 18 GB `.part` behind after
        the user asked for the model to be gone would be a nasty surprise the
        next time they looked at their disk."""
        info = _models.resolve(cute)
        if cute == _models.load_state().get("current"):
            raise ModelDownloadError(
                f"{info['label']} is the model you're using right now — switch "
                "to another one first, then delete it.", status=409)
        if self.active and self._snap["cute"] == cute:
            raise ModelDownloadError(
                f"{info['label']} is downloading — cancel that first.", status=409)
        targets = [_models.WEIGHTS_DIR / info["filename"], part_path(info["filename"])]
        if info.get("draft_filename"):
            targets += [_models.WEIGHTS_DIR / info["draft_filename"],
                        part_path(info["draft_filename"])]
        removed: list[str] = []
        freed = 0
        for target in targets:
            try:
                size = target.stat().st_size
            except OSError:
                continue          # not on disk — nothing to do
            try:
                target.unlink()
            except OSError as e:
                raise ModelDownloadError(
                    f"couldn't remove {target.name}: {e}", status=500) from None
            removed.append(target.name)
            freed += size
        if not removed:
            raise ModelDownloadError(f"{info['label']} isn't installed", status=404)
        log.info("model %s deleted (%s)", cute, ", ".join(removed))
        return {"ok": True, "cute": cute, "removed": removed,
                "freed_bytes": freed, "freed_human": bytes_to_human(freed)}

    def preflight(self, phases: list[dict[str, Any]]) -> None:
        """Refuse before writing a byte when the volume can't hold what's
        left to fetch. Judged on the registry's approximate sizes minus
        whatever the `.part` files already hold — the real Content-Length
        only arrives with the response, and a refusal after 13 GB of
        downloading is worse than a conservative one now."""
        remaining = sum(max(0, p["expected_bytes"] - _part_bytes(p["filename"]))
                        for p in phases)
        if remaining <= 0:
            return
        free = int(_models.free_disk_gb() * _G)
        needed = int(remaining * DISK_MARGIN)
        if free < needed:
            raise ModelDownloadError(
                f"not enough free space in {_models.WEIGHTS_DIR}: need about "
                f"{bytes_to_human(needed)}, have {bytes_to_human(free)}.",
                status=400)

    # -- the run ----------------------------------------------------------

    def _update(self, **fields: Any) -> dict[str, Any]:
        self._snap = {**self._snap, **fields}
        return dict(self._snap)

    async def _fire(self, data: dict[str, Any]) -> None:
        if self._emit is None:
            return
        try:
            await self._emit(EVENT, data)
        except Exception:  # noqa: BLE001 — progress must never kill the download
            log.exception("model-dl emit failed")

    async def _run(self, info: dict, phases: list[dict[str, Any]]) -> None:
        try:
            for phase in phases:
                if not await self._phase(phase):
                    await self._fire(self._update(
                        status="cancelled", rate_bps=0, eta_s=None,
                        **_progress(_part_bytes(phase["filename"]),
                                    self._snap["bytes_total"]),
                    ))
                    log.info("model %s download cancelled (partial kept)", info["cute"])
                    return
            fresh = _models.resolve(info["cute"])
            await self._fire(self._update(
                status="done", rate_bps=0, eta_s=None, error=None,
                installed=fresh["installed"], draft_installed=fresh["draft_installed"],
            ))
            log.info("model %s installed", info["cute"])
        except Exception as e:  # noqa: BLE001 — surfaced to the UI, not into the loop
            log.exception("model download failed")
            await self._fire(self._update(
                status="error", error=str(e), rate_bps=0, eta_s=None))

    async def _phase(self, phase: dict[str, Any]) -> bool:
        """Fetch one file to completion, resuming from its `.part` if there
        is one, then move it into the weights dir. False — with the `.part`
        left behind — when cancel landed mid-stream. A cancel that arrives
        after the last chunk still returns True: the file is on disk, and
        reporting that as cancelled would contradict `installed`."""
        part = part_path(phase["filename"])
        part.parent.mkdir(parents=True, exist_ok=True)
        done = _part_bytes(phase["filename"])
        total = phase["expected_bytes"]
        # Anchor the UI immediately rather than at the first emit interval:
        # a 19 GB file resuming from 18 GB should say so before it says 0%.
        await self._fire(self._update(
            phase=phase["phase"], filename=phase["filename"],
            status="downloading", rate_bps=0, eta_s=None, error=None,
            **_progress(done, total)))
        headers = {"Range": f"bytes={done}-"} if done else {}
        mode = "ab" if done else "wb"
        last_emit = 0.0
        rate_anchor = (time.monotonic(), done)
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=120),
                                     follow_redirects=True) as client:
            async with client.stream("GET", phase["url"], headers=headers) as resp:
                if done and resp.status_code == 416:
                    # Our range starts past the end: the `.part` already holds
                    # the whole file (a cancel that landed on the last chunk).
                    total = done
                else:
                    if done and resp.status_code == 200:
                        # Server ignored the Range header — start over.
                        done, mode = 0, "wb"
                        rate_anchor = (time.monotonic(), 0)
                    resp.raise_for_status()
                    length = resp.headers.get("Content-Length")
                    total = done + int(length) if length else 0
                    self._update(**_progress(done, total))
                    with part.open(mode) as fh:
                        async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                            if self._cancel:
                                return False
                            fh.write(chunk)
                            done += len(chunk)
                            now = time.monotonic()
                            if now - last_emit < EMIT_INTERVAL:
                                continue
                            last_emit = now
                            span = now - rate_anchor[0]
                            rate = (done - rate_anchor[1]) / span if span > 0 else 0
                            if span > 30:
                                rate_anchor = (now, done)
                            await self._fire(self._update(
                                status="downloading", rate_bps=int(rate),
                                eta_s=(int((total - done) / rate)
                                       if rate > 0 and total else None),
                                **_progress(done, total)))
        final = _models.WEIGHTS_DIR / phase["filename"]
        final.parent.mkdir(parents=True, exist_ok=True)
        part.rename(final)
        # Land the bar on full before the next phase (or the done event)
        # re-anchors it — otherwise it freezes wherever the last interval left it.
        await self._fire(self._update(
            status="downloading", rate_bps=0, eta_s=None,
            **_progress(done, total or done)))
        return True
