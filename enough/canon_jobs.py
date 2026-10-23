"""Background jobs for the derivation engine (0.4.3, plan §7.5): EMF twins, atems, compiles, and pins.

Modelled on `convert.ConvertJobs`: a snapshot dict that is both the poll payload (`GET /api/canon/job/{id}`) and
the SSE payload (event `canon`), one manager owned by `create_app()`, a per-path claim so a double-click can't
start two writers on one twin. Unlike a conversion, a derivation is many short model calls, so cancelling is a
cooperative flag the work checks between passages: the passage being read finishes, then the job stops, and the
snapshot says so.

Concurrency with chat: a model-mode job runs as an asyncio task that holds `session.generation_lock` (the lock
every chat turn holds) for its whole run and does the blocking work in `asyncio.to_thread`, so a chat turn and a
derivation never share the local model. While it waits for the lock its state is `queued`, message "waiting for
the model". A rules-mode job never takes the lock. Whether a job is model or rules is decided once, before it
starts (`llm.reachable`), and never changes mid-job: if the model stops answering, the job fails with words.

Snapshot: `{id, kind: emf|atem|compile|pin, path, state: queued|running|done|failed|cancelled, phase, chunk,
chunks, message, mode: model|rules, result, error, started_at, finished_at}`.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from .canon_derive import DeriveCancelled

log = logging.getLogger(__name__)

EVENT = "canon"
KINDS = ("emf", "atem", "compile", "pin")
ACTIVE = ("queued", "running")
# Finished jobs kept for polling; the oldest go first past this many.
KEEP_FINISHED = 200

EmitFn = Callable[[str, dict[str, Any]], Any]


class CanonJobError(Exception):
    """A refusal with the HTTP status the route answers with (404 unknown job, 409 busy or not running)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JobContext:
    """What the blocking work sees: `progress(fields)` to report (phase, chunk, chunks, message), `should_stop()`
    for the cooperative cancel, `check()` to raise `DeriveCancelled` when it is set."""

    def __init__(self, jobs: "CanonJobs", job_id: str):
        self._jobs = jobs
        self.job_id = job_id

    def progress(self, fields: dict[str, Any] | None = None, **more: Any) -> None:
        upd = {k: v for k, v in {**(fields or {}), **more}.items() if k in ("phase", "chunk", "chunks", "message")}
        if self.should_stop():
            upd.pop("message", None)          # keep saying "cancelling …" once asked
            upd.pop("phase", None)
        if upd:
            self._jobs._update(self.job_id, **upd)
            self._jobs._fire(self.job_id)

    def should_stop(self) -> bool:
        ev = self._jobs._stops.get(self.job_id)
        return bool(ev and ev.is_set())

    def check(self) -> None:
        if self.should_stop():
            raise DeriveCancelled()


class CanonJobs:
    """The job table. `start` claims, records and schedules; `cancel` asks; the snapshots are the API."""

    def __init__(self, emit: EmitFn | None = None):
        self._emit = emit
        self._snaps: dict[str, dict[str, Any]] = {}
        self._stops: dict[str, threading.Event] = {}
        self._by_key: dict[str, str] = {}
        self._held: set[str] = set()
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._seq = 0
        self._lock = threading.Lock()

    # -- introspection ----------------------------------------------------

    def running_for(self, key: str) -> str | None:
        """The job queued or running for a claim key (a file's resolved path), or None."""
        job_id = self._by_key.get(key)
        if job_id and self._snaps.get(job_id, {}).get("state") in ACTIVE:
            return job_id
        return None

    def busy(self, key: str) -> bool:
        return key in self._held or self.running_for(key) is not None

    def snapshot(self, job_id: str) -> dict[str, Any]:
        snap = self._snaps.get(job_id)
        if snap is None:
            raise CanonJobError(f"no such job {job_id}", status=404)
        return dict(snap)

    def active(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self._snaps.values() if s["state"] in ACTIVE]

    # -- control ----------------------------------------------------------

    def _new(self, *, kind: str, path: str | None, mode: str, state: str, message: str,
             key: str | None) -> str:
        """Record a job under the table lock; 409 when `key` is claimed. Caller holds `self._lock`."""
        if kind not in KINDS:
            raise ValueError(f"unknown job kind {kind!r}")
        if key is not None and self.busy(key):
            raise CanonJobError(f"{path or 'this file'} is already being derived; wait for that job, or cancel it",
                                status=409)
        self._seq += 1
        job_id = f"cn{self._seq}"
        if key is not None:
            self._by_key[key] = job_id
        self._snaps[job_id] = {
            "id": job_id, "kind": kind, "path": path, "state": state,
            "phase": "waiting" if state == "queued" else "starting", "chunk": 0, "chunks": 0,
            "message": message, "mode": mode, "result": None, "error": None,
            "started_at": None, "finished_at": None,
        }
        self._stops[job_id] = threading.Event()
        self._trim()
        return job_id

    def start(self, *, kind: str, path: str | None, mode: str, work: Callable[[JobContext], Any],
              key: str | None = None, lock: asyncio.Lock | None = None, message: str = "") -> dict[str, Any]:
        """Claim `key` (409 when a job for it is queued or running), record the job and schedule it on the running
        loop. `work(ctx)` is blocking and runs in a worker thread; with `lock` (model mode: the session's
        generation lock) the job waits for it first, `queued` meanwhile. Returns the first snapshot."""
        with self._lock:
            waiting = lock is not None and lock.locked()
            job_id = self._new(kind=kind, path=path, mode=mode, state="queued",
                               message="waiting for the model" if waiting else (message or "starting"), key=key)
        self._fire(job_id)
        task = asyncio.get_running_loop().create_task(self._run(job_id, work, lock, message))
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t, j=job_id: self._tasks.pop(j, None))
        return self.snapshot(job_id)

    def record(self, *, kind: str, path: str | None, mode: str, result: Any, message: str) -> dict[str, Any]:
        """A job done on the spot (a pin): recorded finished and announced like any other, so the UI repaints from
        one event."""
        with self._lock:
            job_id = self._new(kind=kind, path=path, mode=mode, state="running", message=message, key=None)
            now = _stamp()
            self._update(job_id, state="done", phase="done", result=result, started_at=now, finished_at=now)
        self._fire(job_id)
        return self.snapshot(job_id)

    @contextmanager
    def holding(self, key: str, path: str | None = None) -> Iterator[None]:
        """Hold a claim for a short synchronous write (a pin): 409 when a job holds it, and no job can claim it
        meanwhile."""
        with self._lock:
            if self.busy(key):
                raise CanonJobError(f"{path or 'this file'} is being derived right now; try again when that job "
                                    "is done", status=409)
            self._held.add(key)
        try:
            yield
        finally:
            with self._lock:
                self._held.discard(key)

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Ask a job to stop. Queued: it never starts (cancelled now). Running: the passage being read finishes,
        then it stops (the snapshot says `cancelling` until it has). Anything else: 409."""
        snap = self.snapshot(job_id)
        if snap["state"] not in ACTIVE:
            raise CanonJobError(f"job {job_id} is not running", status=409)
        self._stops[job_id].set()
        if snap["state"] == "queued":
            task = self._tasks.get(job_id)
            if task is not None and not task.done():
                task.cancel()
            self._finish(job_id, "cancelled", message="cancelled before it started")
        elif snap.get("phase") != "cancelling":
            msg = ("cancelling: the model finishes the passage it is reading, then the job stops"
                   if snap["mode"] == "model" else "cancelling")
            self._update(job_id, phase="cancelling", message=msg)
            self._fire(job_id)
        return self.snapshot(job_id)

    # -- the run ----------------------------------------------------------

    def _update(self, job_id: str, **fields: Any) -> None:
        snap = self._snaps.get(job_id)
        if snap is not None:
            snap.update(fields)

    def _fire(self, job_id: str) -> None:
        if self._emit is None:
            return
        try:
            self._emit(EVENT, dict(self._snaps[job_id]))
        except Exception:  # noqa: BLE001 — progress must never kill the job
            log.exception("canon emit failed")

    def _finish(self, job_id: str, state: str, **fields: Any) -> None:
        snap = self._snaps.get(job_id)
        if snap is None or snap["state"] not in ACTIVE:
            return
        self._update(job_id, state=state, phase=state, finished_at=_stamp(), **fields)
        self._fire(job_id)

    def _trim(self) -> None:
        done = [j for j, s in self._snaps.items() if s["state"] not in ACTIVE]
        for j in done[: max(0, len(done) - KEEP_FINISHED)]:
            self._snaps.pop(j, None)
            self._stops.pop(j, None)

    async def _run(self, job_id: str, work: Callable[[JobContext], Any], lock: asyncio.Lock | None,
                   message: str) -> None:
        try:
            if lock is not None:
                async with lock:
                    if self._stops[job_id].is_set():
                        self._finish(job_id, "cancelled", message="cancelled before it started")
                        return
                    await self._work(job_id, work, message)
            else:
                await self._work(job_id, work, message)
        except asyncio.CancelledError:
            self._finish(job_id, "cancelled", message="cancelled before it started")
        except Exception as e:  # noqa: BLE001 — surfaced to the UI, never to the loop
            log.exception("canon job %s failed", job_id)
            self._finish(job_id, "failed", error=str(e), message=str(e))

    async def _work(self, job_id: str, work: Callable[[JobContext], Any], message: str) -> None:
        self._update(job_id, state="running", phase="starting", started_at=_stamp(),
                     message=message or "starting")
        self._fire(job_id)
        ctx = JobContext(self, job_id)
        try:
            result = await asyncio.to_thread(work, ctx)
        except DeriveCancelled:
            snap = self._snaps.get(job_id, {})
            where = (f" after passage {snap.get('chunk')} of {snap.get('chunks')}"
                     if snap.get("chunks") and snap.get("chunk") else "")
            self._finish(job_id, "cancelled", message=f"cancelled{where}; nothing was written")
            return
        except Exception as e:  # noqa: BLE001
            log.warning("canon job %s failed: %s", job_id, e)
            self._finish(job_id, "failed", error=str(e) or e.__class__.__name__,
                         message=str(e) or e.__class__.__name__)
            return
        done_msg = result.pop("message", None) if isinstance(result, dict) else None
        self._finish(job_id, "done", result=result, message=done_msg or "done")
