"""LlamaSupervisor — enough's lifecycle manager for llama-server.

Responsibilities
----------------
- On enough startup: if llama-server is already listening on the target
  port, ADOPT it (read /props to identify its model, match against the
  models registry). Otherwise OWN it (Popen a subprocess with the current
  model + ctx from config).
- On model/ctx switch: stop whatever's running (owned or adopted), start
  a fresh owned subprocess with the new parameters.
- On enough shutdown: terminate only if OWNED. Adopted processes stay
  running so the user's prior manual setup survives.
- Non-blocking startup: the supervisor returns immediately; a background
  task polls /health and flips `ready` to True when llama-server responds.

The supervisor is intentionally ignorant of FastAPI — server.py wires it
into the lifespan. Tests can instantiate it directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from . import models as _models

log = logging.getLogger("enough.supervisor")


class LlamaSupervisor:
    def __init__(
        self,
        *,
        llm_url: str = "http://127.0.0.1:8080",
        port: int = 8080,
        host: str = "127.0.0.1",
        ngl: int = 99,
        parallel: int = 1,
    ) -> None:
        self.llm_url = llm_url.rstrip("/")
        self.host = host
        self.port = port
        self.ngl = ngl
        self.parallel = parallel

        self.proc: subprocess.Popen[bytes] | None = None    # set iff OWNED
        self.adopted_pid: int | None = None                  # set iff ADOPTED
        self.current_cute: str | None = None
        self.current_ctx: int | None = None
        self.ready: bool = False
        self.last_error: str | None = None
        self._healthwatch_task: asyncio.Task[None] | None = None

    # -----------------------------------------------------------------------
    # State
    # -----------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        mode = "owned" if self.proc else ("adopted" if self.adopted_pid else "off")
        return {
            "mode": mode,
            "ready": self.ready,
            "cute": self.current_cute,
            "ctx": self.current_ctx,
            "url": self.llm_url,
            "error": self.last_error,
        }

    # -----------------------------------------------------------------------
    # Startup
    # -----------------------------------------------------------------------

    async def bootstrap(self) -> None:
        """Adopt-or-launch. Safe to call once during FastAPI lifespan."""
        # Case 1: llama-server already up → adopt.
        pid = await self._probe_existing()
        if pid is not None:
            self.adopted_pid = pid
            self.ready = await self._is_healthy()
            await self._identify_adopted()
            self._start_healthwatch()
            log.info("adopted existing llama-server (pid=%s, model=%s)", pid, self.current_cute)
            return

        # Case 2: need to start our own.
        cute, ctx = _resolve_startup_choice()
        if not cute:
            self.last_error = "no model configured and no llama-server running"
            log.warning(self.last_error)
            return
        try:
            self._launch(cute, ctx)
        except Exception as e:  # noqa: BLE001
            self.last_error = f"launch failed: {e}"
            log.exception("launch failed")
            return
        self._start_healthwatch()

    async def _probe_existing(self) -> int | None:
        """Return pid if something is listening on our port, else None."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(self.llm_url + "/health")
            if r.status_code in (200, 503):
                return _find_pid_on_port(self.port)
        except httpx.HTTPError:
            pass
        return None

    async def _identify_adopted(self) -> None:
        """Ask /props for the model path; match against the registry."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(self.llm_url + "/props")
            if r.status_code != 200:
                return
            d = r.json()
            path = d.get("model_path") or ""
            ctx = (d.get("default_generation_settings") or {}).get("n_ctx")
            if ctx:
                self.current_ctx = int(ctx)
            # Match model_path against registered filenames.
            fname = Path(path).name
            try:
                reg = _models.load_registry()
            except FileNotFoundError:
                return
            for cute, entry in (reg.get("models") or {}).items():
                if entry.get("gguf_filename") == fname:
                    self.current_cute = cute
                    break
        except Exception:  # noqa: BLE001
            log.exception("could not identify adopted llama-server")

    # -----------------------------------------------------------------------
    # Launch / stop (owned lifecycle)
    # -----------------------------------------------------------------------

    def _launch(self, cute: str, ctx: int) -> None:
        info = _models.resolve(cute)
        if not info["installed"]:
            raise RuntimeError(
                f"model {cute} isn't installed at {info['filename']}. "
                "install via bootstrap.sh or drop the gguf into ~/enough/weights/."
            )
        binary = shutil.which("llama-server")
        if not binary:
            raise RuntimeError(
                "llama-server not on PATH. install with `brew install llama.cpp`."
            )

        state_dir = Path.home() / "enough" / ".llama-server"
        state_dir.mkdir(parents=True, exist_ok=True)
        log_path = state_dir / "server.log"
        pid_path = state_dir / "server.pid"

        cmd = [
            binary,
            "-m", info["path"],
            "--host", self.host,
            "--port", str(self.port),
            "-ngl", str(self.ngl),
            "-c", str(ctx),
            "--parallel", str(self.parallel),
            "--jinja",
        ]
        log.info("launching llama-server: %s", " ".join(cmd))
        f = open(log_path, "ab", buffering=0)  # noqa: SIM115  (intentionally leaked to subprocess)
        self.proc = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=f,
            stdin=subprocess.DEVNULL,
            env=os.environ.copy(),
            start_new_session=True,  # isolate signal group
        )
        pid_path.write_text(str(self.proc.pid))
        self.current_cute = cute
        self.current_ctx = ctx
        self.ready = False
        self.adopted_pid = None
        self.last_error = None

    async def _wait_ready(self, timeout_s: float = 300.0) -> bool:
        """Poll /health until 200 or timeout. Populates self.ready."""
        deadline = time.time() + timeout_s
        async with httpx.AsyncClient(timeout=3.0) as c:
            while time.time() < deadline:
                try:
                    r = await c.get(self.llm_url + "/health")
                    if r.status_code == 200:
                        self.ready = True
                        return True
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(1.0)
        self.last_error = f"health poll timed out after {timeout_s}s"
        return False

    def _start_healthwatch(self) -> None:
        if self._healthwatch_task and not self._healthwatch_task.done():
            return
        loop = asyncio.get_event_loop()
        self._healthwatch_task = loop.create_task(self._wait_ready())

    async def stop(self, *, only_if_owned: bool = False) -> None:
        """Terminate the llama-server, owned or adopted. If only_if_owned,
        do nothing for adopted processes (use during enough shutdown)."""
        if self.proc is not None:
            try:
                self.proc.terminate()
                try:
                    await asyncio.to_thread(self.proc.wait, timeout=10.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    await asyncio.to_thread(self.proc.wait, timeout=5.0)
            except Exception:  # noqa: BLE001
                log.exception("proc stop error")
            finally:
                self.proc = None
        elif self.adopted_pid and not only_if_owned:
            pid = self.adopted_pid
            try:
                os.kill(pid, signal.SIGTERM)
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if not _pid_alive(pid):
                        break
                else:
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # already dead
            except Exception:  # noqa: BLE001
                log.exception("adopted stop error")
            finally:
                self.adopted_pid = None
        # Cancel any outstanding health watch.
        if self._healthwatch_task and not self._healthwatch_task.done():
            self._healthwatch_task.cancel()
            try:
                await self._healthwatch_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self.ready = False

    # -----------------------------------------------------------------------
    # Switch
    # -----------------------------------------------------------------------

    async def switch(self, cute: str, ctx: int | None = None) -> None:
        """Swap in a new model (and optionally a new ctx). Stops whatever's
        running, then launches fresh. Persists the choice to the live
        model state."""
        info = _models.resolve(cute)
        if not info["installed"]:
            raise RuntimeError(f"model {cute} is not installed; cannot switch to it.")
        resolved_ctx = int(ctx) if ctx else _preferred_ctx(cute)

        await self.stop()

        # Persist BEFORE launching, so crashes still leave valid state.
        state = _models.load_state()
        state["current"] = cute
        overrides = state.get("ctx_overrides") or {}
        overrides[cute] = resolved_ctx
        state["ctx_overrides"] = overrides
        _models.save_state(state)

        self._launch(cute, resolved_ctx)
        self._start_healthwatch()

    # -----------------------------------------------------------------------
    # Health introspection
    # -----------------------------------------------------------------------

    async def _is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(self.llm_url + "/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours
    except OSError:
        return False


def _find_pid_on_port(port: int) -> int | None:
    """macOS: lsof -iTCP:<port> -sTCP:LISTEN -t. Also checks our state
    dir's pidfile for the common case of script-launched llama-server."""
    pidfile = Path.home() / "enough" / ".llama-server" / "server.pid"
    if pidfile.is_file():
        try:
            pid = int(pidfile.read_text().strip())
            if _pid_alive(pid):
                return pid
        except (OSError, ValueError):
            pass
    try:
        out = subprocess.check_output(
            ["lsof", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"],
            text=True, stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _preferred_ctx(cute: str) -> int:
    """Per-model ctx override (if the user set one) else the RAM-tiered
    recommendation."""
    state = _models.load_state()
    overrides = (state.get("ctx_overrides") or {})
    if cute in overrides:
        try:
            return int(overrides[cute])
        except (TypeError, ValueError):
            pass
    info = _models.resolve(cute)
    return int(info.get("ctx_recommended") or 16384)


def _resolve_startup_choice() -> tuple[str | None, int]:
    """Pick which (cute, ctx) to launch with on enough startup."""
    try:
        state = _models.load_state()
    except Exception:  # noqa: BLE001
        return (None, 16384)
    cute = state.get("current")
    if not cute:
        return (None, 16384)
    try:
        info = _models.resolve(cute)
    except KeyError:
        return (None, 16384)
    if not info["installed"]:
        return (None, 16384)
    return (cute, _preferred_ctx(cute))
