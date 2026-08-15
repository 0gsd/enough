#!/usr/bin/env python3
"""Headless boot smoke for the enough backend — the Linux port's
definition-of-done check (docs/linux-plan.md §3.4), and a useful 15-second
sanity pass on any platform.

    uv run python scripts/smoke_boot.py            # ephemeral scratch dir
    uv run python scripts/smoke_boot.py --keep     # ...and leave it behind
    uv run python scripts/smoke_boot.py -v         # stream the server log

What it does: starts a real `python -m enough` in a subprocess against a
scratch project, drives a handful of read-only endpoints over HTTP, and
asks it to shut down. Nothing is mocked — that is the point. It is the one
check that proves the whole import graph, uvicorn, the FastAPI app, the
skeleton builder, the model registry, and the supervisor's
nothing-is-installed path all survive contact with this machine.

Isolation, in two layers, because half of enough's state predates the env
hooks:

1. every ``ENOUGH_*`` seam (weights dir, live model state, registry,
   download URL base, cacheawl root, infoworld root, wikisink config, ui
   config, llama-server override) is pointed inside the scratch dir; and
2. ``$HOME`` is pointed there too, which is what actually isolates
   ``~/enough/config/broker.json``, ``openrouter.json``,
   ``orchestrator.json`` and ``~/enough/.llama-server/server.pid`` — none
   of which has an env hook of its own.

``--llm-url`` gets a port nothing is listening on, so the run can never
adopt (or, on shutdown, kill) the developer's real llama-server on 8080.
That is the one piece of shared state the ``ENOUGH_*`` hooks cannot
isolate, and it is the reason this script picks the port rather than
taking a default.

No model weights, no llama.cpp, no network beyond loopback are required —
"graceful degradation with nothing installed" is one of the assertions,
not a limitation of the harness.

Exit status: 0 = every assertion held. Non-zero = the first failure, named
on stderr, with the server's own log dumped after it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Bounds. Generous enough for a cold GitHub-hosted runner, tight enough
# that a hang fails the job instead of burning the six-hour ceiling.
BOOT_TIMEOUT_S = 90.0
SHUTDOWN_TIMEOUT_S = 30.0
REQUEST_TIMEOUT_S = 20.0

DESKTOP_TOKEN = "smoke-boot-token"

_checks = 0


def ok(what: str) -> None:
    global _checks
    _checks += 1
    print(f"  ok  {what}", flush=True)


class SmokeFailure(AssertionError):
    pass


def need(cond: object, what: str) -> None:
    if not cond:
        raise SmokeFailure(what)
    ok(what)


def free_port() -> int:
    """A port nothing is listening on right now. Bind-and-release: the
    kernel hands out an unused one, and we let it go immediately. Racy in
    principle, fine in practice on a single-tenant runner — and the
    consequence of losing the race is a failed smoke, not a corrupted
    install."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ---------------------------------------------------------------------------
# HTTP (stdlib only — the smoke must not depend on the app's own deps)
# ---------------------------------------------------------------------------

def request(
    url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if method == "POST":
        req.data = b""
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def get_json(url: str) -> dict:
    status, body = request(url)
    if status != 200:
        raise SmokeFailure(f"GET {url} → {status}: {body[:400]}")
    return json.loads(body)


# ---------------------------------------------------------------------------
# The scratch environment
# ---------------------------------------------------------------------------

def build_env(scratch: Path) -> dict[str, str]:
    home = scratch / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    (home / "enough" / "bin").mkdir(parents=True, exist_ok=True)
    weights = scratch / "weights"
    weights.mkdir(exist_ok=True)

    # The registry is read-only, but copy it anyway: "every ENOUGH_* points
    # into the scratch dir" is a rule worth being able to state without
    # exceptions, and a copy also proves the hook itself works.
    registry = scratch / "models.json"
    shutil.copyfile(REPO_ROOT / "defaults" / "models.json", registry)

    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        # Model layer.
        "ENOUGH_WEIGHTS_DIR": str(weights),
        "ENOUGH_LIVE_STATE": str(scratch / "live-models.json"),
        "ENOUGH_MODELS_REGISTRY": str(registry),
        # Nothing may reach huggingface.co from a smoke run. Port 1 is
        # never listening; a download attempt fails instantly and loudly
        # instead of quietly pulling gigabytes.
        "ENOUGH_MODELS_URL_BASE": "http://127.0.0.1:1/weights",
        # A dead rung-1 override: exercises the documented fall-through
        # (warn, then try ~/enough/bin, then PATH) on every run.
        "ENOUGH_LLAMA_SERVER": str(scratch / "no-such-llama-server"),
        # Stores.
        "ENOUGH_CACHEAWL_ROOT": str(scratch / "cacheawl"),
        "ENOUGH_INFOWORLD_ROOT": str(scratch / "no-infoworld"),
        "ENOUGH_WIKISINK_CONFIG": str(scratch / "wikisink.json"),
        "ENOUGH_UI_CONFIG": str(scratch / "ui.json"),
        # Desktop capability gate — so the shutdown route exists and its
        # token check is exercised. Not an isolation hook; see AGENT_GUIDE.
        "ENOUGH_DESKTOP": "1",
        "ENOUGH_DESKTOP_TOKEN": DESKTOP_TOKEN,
        # Unbuffered child output, so a crash log isn't lost in a pipe.
        "PYTHONUNBUFFERED": "1",
    })
    # The shell-side desktop vars, if the developer happens to have them
    # exported, would redirect which checkout and which uv the run uses.
    env.pop("ENOUGH_DESKTOP_CODE", None)
    env.pop("ENOUGH_DESKTOP_UV", None)
    env.pop("ENOUGH_DESKTOP_LLM_URL", None)
    return env


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def check_project(base: str, project: Path) -> None:
    payload = get_json(f"{base}/api/project")
    # `enough` resolves --dir, and on macOS /var is a symlink to /private/var,
    # so compare resolved paths rather than strings.
    need(Path(payload.get("path") or "/nope").resolve() == project.resolve(),
         "/api/project reports the scratch project")
    need((project / "rness" / "AGENT.md").is_file(),
         "the rness/ skeleton was built on first launch")

    status, body = request(f"{base}/")
    need(status == 200 and "<html" in body.lower(), "GET / serves the UI shell")


def check_models(base: str) -> None:
    payload = get_json(f"{base}/api/models")
    entries = payload.get("models") or []
    need(len(entries) == 7, f"/api/models lists 7 local models (got {len(entries)})")

    verdicts = {}
    for e in entries:
        f = (e or {}).get("feasibility") or {}
        v = f.get("verdict")
        if v not in ("good", "tight", "no"):
            raise SmokeFailure(
                f"model {e.get('cute')!r} has no usable feasibility verdict: {f!r}"
            )
        if not isinstance(f.get("reasons"), list):
            raise SmokeFailure(f"model {e.get('cute')!r} verdict has no reasons list")
        verdicts[e.get("cute")] = v
    ok(f"every model carries a feasibility verdict ({verdicts})")

    ram = payload.get("total_ram_gb")
    need(isinstance(ram, int) and ram > 0,
         f"total_ram_gb is a positive integer on this host ({ram} GB)")
    need(payload.get("current"), "a current model is selected (state seeded)")
    need(isinstance(payload.get("llama_release"), int),
         "llama_release probed without raising")
    need((payload.get("supervisor") or {}).get("mode") == "off",
         "supervisor reports mode=off with nothing installed")


def check_degraded(base: str) -> None:
    """No llama-server anywhere: the app must say so calmly."""
    payload = get_json(f"{base}/api/llm-status")
    need(payload.get("mode") in ("off", "external"),
         f"/api/llm-status answers 200 with no llama-server (mode={payload.get('mode')!r})")
    need(payload.get("ready") is False, "…and reports ready=False rather than erroring")

    status, _body = request(f"{base}/api/broker")
    need(status == 200, "/api/broker renders with a scratch config")


def check_shutdown(base: str, proc: subprocess.Popen) -> None:
    status, _ = request(f"{base}/api/shutdown", method="POST")
    need(status == 403, "POST /api/shutdown without the desktop token → 403")

    status, body = request(
        f"{base}/api/shutdown", method="POST",
        headers={"X-Enough-Desktop-Token": DESKTOP_TOKEN},
    )
    need(status == 200 and json.loads(body).get("ok") is True,
         "POST /api/shutdown with the token → 200 {ok: true}")

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_S
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    need(proc.poll() is not None,
         f"the server process exited within {SHUTDOWN_TIMEOUT_S:.0f}s")
    # `request_process_exit` SIGTERMs the process, and uvicorn's
    # `capture_signals` re-raises the captured signal after its graceful
    # shutdown completes and the default handlers are back — so the POSIX
    # wait status is "terminated by SIGTERM", not "exited 0". Both are
    # clean; a non-zero *exit* code (a traceback out of the lifespan
    # teardown, say) is what would not be.
    need(proc.returncode in (0, -signal.SIGTERM),
         f"…cleanly: exit 0 or SIGTERM, never a crash (got {proc.returncode})")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(scratch: Path, *, verbose: bool) -> None:
    project = scratch / "project"
    project.mkdir(parents=True, exist_ok=True)
    port = free_port()
    llm_port = free_port()
    env = build_env(scratch)
    base = f"http://127.0.0.1:{port}"
    log_path = scratch / "server.log"

    cmd = [
        sys.executable, "-m", "enough",
        "--dir", str(project),
        "--port", str(port),
        # Nothing listens here — never 8080, never the developer's server.
        "--llm-url", f"http://127.0.0.1:{llm_port}",
        "--no-browser",
    ]
    print(f"smoke: {' '.join(cmd)}", flush=True)
    print(f"smoke: scratch {scratch}", flush=True)

    log = open(log_path, "wb")
    proc = subprocess.Popen(
        cmd, cwd=str(REPO_ROOT), env=env,
        stdout=(None if verbose else log),
        stderr=(subprocess.STDOUT if not verbose else None),
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        booted = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise SmokeFailure(
                    f"the server exited during boot with status {proc.returncode}"
                )
            try:
                status, _ = request(f"{base}/api/project")
                if status == 200:
                    booted = True
                    break
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
            time.sleep(0.25)
        need(booted, f"the server answered /api/project within {BOOT_TIMEOUT_S:.0f}s")

        check_project(base, project)
        check_models(base)
        check_degraded(base)
        check_shutdown(base, proc)
    except BaseException:
        log.flush()
        if log_path.is_file() and not verbose:
            print("\n--- server log " + "-" * 55, file=sys.stderr)
            sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace"))
            print("--- end server log " + "-" * 51 + "\n", file=sys.stderr)
        raise
    finally:
        log.close()
        if proc.poll() is None:
            # Belt and braces: the whole session, so nothing is orphaned.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scratch", type=Path, default=None,
                    help="scratch dir to use (default: a fresh temp dir)")
    ap.add_argument("--keep", action="store_true",
                    help="don't delete the scratch dir on success")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="stream the server's log instead of capturing it")
    args = ap.parse_args(argv)

    made = args.scratch is None
    scratch = args.scratch or Path(tempfile.mkdtemp(prefix="enough-smoke-"))
    scratch.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        run(scratch, verbose=args.verbose)
    except SmokeFailure as e:
        print(f"\nSMOKE FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"\nSMOKE ERRORED: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        if made and not args.keep:
            shutil.rmtree(scratch, ignore_errors=True)
    print(f"\nsmoke passed — {_checks} checks in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
