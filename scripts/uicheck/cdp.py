"""A minimal Chrome DevTools Protocol client — the whole browser stack.

There is no playwright here, and no selenium, and no node. The pre-commit
suite adds **zero** dependencies: CDP is a JSON-RPC protocol over one
WebSocket, and `websockets` is already locked into the venv as a transitive
of `uvicorn[standard]`. That is the entire trick. About 200 lines buys
everything the layout probes need — navigate, evaluate, emulate a viewport,
capture a screenshot — and nothing they don't.

Two objects:

* `Browser` owns the Chrome process and its user-data dir. It launches
  headless with `--remote-debugging-port=0` (the kernel picks the port, so
  parallel runs and a developer's own Chrome never collide), reads the port
  back out of the `DevToolsActivePort` file Chrome writes into that dir, and
  is a context manager whose `__exit__` always kills the process group. It
  is deliberately hard to leak a Chrome from here.
* `Page` is one tab: `send(method, params)` with id-matched replies and a
  buffer for the unsolicited events that arrive in between.

`find_chrome()` is a pure function over a `exists` predicate so the locator
order can be unit-tested without a browser (tests/test_ui_check.py).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from websockets.sync.client import connect as ws_connect

# Where a browser lives on each platform, in the order the spec fixes:
# an explicit override first, then the macOS bundles, then whatever is on
# PATH. Chrome first in both halves — it is the one this harness is
# developed against; the rest are there so a Linux CI box or a developer
# who only has Brave still gets a real run instead of a SKIP.
MAC_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
PATH_CANDIDATES = ("google-chrome", "chromium", "chromium-browser")


def find_chrome(
    *,
    env: dict[str, str] | None = None,
    exists: Callable[[str], bool] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    """The first usable browser binary, or None.

    `$ENOUGH_CHROME` → the macOS bundle paths → the PATH names. The three
    injectable callables are what let the order be asserted against a fake
    filesystem instead of against whatever this machine happens to have
    installed.
    """
    env = os.environ if env is None else env
    exists = (lambda p: Path(p).is_file()) if exists is None else exists
    which = shutil.which if which is None else which

    override = (env.get("ENOUGH_CHROME") or "").strip()
    if override:
        # An override that does not exist is a configuration error worth
        # seeing, not something to quietly fall through.
        return override if exists(override) else None
    for path in MAC_CANDIDATES:
        if exists(path):
            return path
    for name in PATH_CANDIDATES:
        found = which(name)
        if found:
            return found
    return None


class CDPError(RuntimeError):
    pass


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Page:
    """One tab's WebSocket. Not thread-safe, and does not need to be."""

    def __init__(self, ws_url: str, *, timeout: float = 12.0,
                 target_id: str = "") -> None:
        self.target_id = target_id
        # max_size=None: a full-page PNG comes back as one base64 string and
        # blows straight through the 1 MiB default frame cap.
        # proxy=None: a developer's exported http_proxy must not be consulted
        # for a loopback connection.
        self._ws = ws_connect(ws_url, max_size=None, proxy=None,
                              open_timeout=timeout, close_timeout=2)
        self._next_id = 0
        self._events: list[dict[str, Any]] = []
        self.dialogs: list[dict[str, Any]] = []
        self.timeout = timeout

    # -- plumbing -------------------------------------------------------
    def _pump(self, deadline: float) -> dict[str, Any]:
        remaining = max(0.05, deadline - time.monotonic())
        try:
            raw = self._ws.recv(timeout=remaining)
        except TimeoutError as e:
            # Every caller already has a CDPError branch; letting the
            # websockets TimeoutError escape would take the whole run down
            # over one slow page.
            raise CDPError(f"no reply within {remaining:.1f}s") from e
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def send(self, method: str, params: dict[str, Any] | None = None,
             *, timeout: float | None = None) -> dict[str, Any]:
        """Call `method` and return its `result`. Events that arrive while
        we wait are buffered, not dropped — `wait_for_event` reads them."""
        self._next_id += 1
        msg_id = self._next_id
        self._ws.send(json.dumps(
            {"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            if time.monotonic() > deadline:
                raise CDPError(f"{method} timed out after {timeout or self.timeout}s")
            msg = self._pump(deadline)
            if msg.get("id") != msg_id:
                if "method" in msg:
                    self._note_event(msg)
                continue
            if "error" in msg:
                raise CDPError(f"{method}: {msg['error'].get('message')}")
            return msg.get("result") or {}

    def _note_event(self, msg: dict[str, Any]) -> None:
        """Buffer an event — and dismiss a native dialog the instant one opens.

        An `alert()` or `confirm()` does not merely freeze the renderer that
        raised it. Chrome runs the dialog in a **nested message loop in the
        BROWSER process**, so while one is up: no tab answers
        `Runtime.evaluate`, `Page.reload` never replies, and the DevTools
        HTTP endpoint (`/json/list`, `/json/new`) stops accepting
        connections — which means the recovery path cannot recover either.
        That is the whole of the `--quick` wedge P4c-1 and P5c reported.

        Accepting it immediately keeps the run alive, and the dialog is
        recorded in `dialogs` so the run can still say it happened.

        **This only fires on the socket somebody is reading.** The harness
        drives two tabs, so the other half of the fix is `pump_pending()`,
        which the run calls on every idle page, and the third half is
        `probes.js`, which replaces `alert`/`confirm`/`prompt` in the page
        so a dialog never opens at all.
        """
        if msg.get("method") == "Page.javascriptDialogOpening":
            self.dialogs.append(dict(msg.get("params") or {}))
            self._ws.send(json.dumps({
                "id": 10_000_000 + len(self.dialogs),
                "method": "Page.handleJavaScriptDialog",
                "params": {"accept": True},
            }))
            return
        self._events.append(msg)

    def drain(self) -> None:
        self._events.clear()

    def pump_pending(self, *, budget: float = 0.0) -> int:
        """Read whatever has already arrived on this socket, and stop.

        **This is what keeps a second tab from taking the run down.** A
        native dialog blocks Chrome's BROWSER process, not just the tab that
        raised it (see `_note_event`), and the auto-accept that unblocks it
        only happens on the socket somebody is reading. The harness drives
        two tabs and reads exactly one of them at a time, so a dialog raised
        in the tab nobody is looking at is never answered — and then the
        *other* tab's `Page.reload` never returns and `/json/list` stops
        answering too, which is the failure P4c-1 and P5c both hit.

        Called on every OTHER page before each screen and each scenario, it
        costs one non-blocking `recv` per idle tab and closes that hole.
        Returns how many messages it consumed, so a caller can log it.
        """
        seen = 0
        deadline = time.monotonic() + max(0.0, budget)
        while True:
            try:
                raw = self._ws.recv(timeout=max(0.0,
                                                deadline - time.monotonic()))
            except TimeoutError:
                return seen
            except Exception:                                    # noqa: BLE001
                # A closed or broken socket has nothing pending by
                # definition; the caller's next real `send` will report it.
                return seen
            seen += 1
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "method" in msg:
                self._note_event(msg)

    def abort(self) -> None:
        """Break whatever this page is blocked on, from another thread.

        The watchdog in `driver.py` calls this. Every ordinary path here is
        already bounded by a deadline, but "bounded" is not the same as
        "cannot hang": a `send()` whose socket buffer never drains, or a
        recv inside a C call, has no deadline of its own. Closing the
        socket underneath makes the blocked call raise, which the caller
        turns into a named FAIL instead of a silent stop.
        """
        try:
            self._ws.close_socket()
        except Exception:                                        # noqa: BLE001
            try:
                self._ws.close()
            except Exception:                                    # noqa: BLE001
                pass

    def wait_for_event(self, method: str, *, timeout: float = 30.0) -> dict[str, Any]:
        for i, ev in enumerate(self._events):
            if ev.get("method") == method:
                return self._events.pop(i)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self._pump(deadline)
            if msg.get("method") == method:
                return msg
            if "method" in msg:
                self._note_event(msg)
        raise CDPError(f"no {method} event within {timeout}s")

    # -- the handful of calls the harness actually makes -----------------
    def enable_domains(self) -> None:
        for domain in ("Page", "Runtime", "DOM"):
            self.send(f"{domain}.enable")

    def evaluate(self, expression: str, *, await_promise: bool = True,
                 timeout: float | None = None) -> Any:
        res = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
        }, timeout=timeout)
        if res.get("exceptionDetails"):
            detail = res["exceptionDetails"]
            text = ((detail.get("exception") or {}).get("description")
                    or detail.get("text") or "unknown")
            raise CDPError(f"page threw: {text}")
        return (res.get("result") or {}).get("value")

    def _await_document(self, *, ready: str, timeout: float) -> None:
        """Poll until the document is complete and `ready` evaluates truthy.

        NOT `Page.loadEventFired`. That event carries no frame or loader id,
        so the `about:blank` a fresh tab starts on can fire its load *after*
        the navigate command goes out, and the harness would then measure a
        document whose inline script has not run — which is exactly the bug
        this replaced (globals reported `undefined`, then TDZ, then fine,
        depending on how the race landed). A poll on the page's own state
        cannot be fooled that way.
        """
        deadline = time.monotonic() + timeout
        # `__uicheck_nav` was stamped on the OUTGOING document; its absence is
        # what proves we are looking at the new one rather than at an old
        # document that is, of course, already "complete".
        expr = ("(!window.__uicheck_nav) && (document.readyState === 'complete')"
                f" && !!({ready})")
        while time.monotonic() < deadline:
            try:
                if self.evaluate(expr, await_promise=False, timeout=10):
                    return
            except CDPError:
                pass            # mid-navigation: the context is being swapped
            time.sleep(0.05)
        raise CDPError(f"document never became ready ({ready}) in {timeout:.0f}s")

    def _stamp_outgoing(self) -> None:
        try:
            self.evaluate("window.__uicheck_nav = 1", await_promise=False,
                          timeout=10)
        except CDPError:
            pass

    def navigate(self, url: str, *, ready: str = "true",
                 timeout: float = 45.0) -> None:
        self.drain()
        self._stamp_outgoing()
        self.send("Page.navigate", {"url": url}, timeout=timeout)
        self._await_document(ready=ready, timeout=timeout)

    def reload(self, *, ready: str = "true", timeout: float = 45.0) -> None:
        self.drain()
        self._stamp_outgoing()
        self.send("Page.reload", {"ignoreCache": False}, timeout=timeout)
        self._await_document(ready=ready, timeout=timeout)

    def set_viewport(self, width: int, height: int, dpr: float) -> None:
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height,
            "deviceScaleFactor": dpr, "mobile": False,
        })

    def screenshot_png(self) -> bytes:
        import base64
        res = self.send("Page.captureScreenshot", {"format": "png"}, timeout=60)
        return base64.b64decode(res["data"])

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:                                    # noqa: BLE001
            pass


class Browser:
    """A headless Chrome, its scratch profile, and the pages opened on it."""

    def __init__(self, binary: str, *, headless: bool = True) -> None:
        self.binary = binary
        self._headless = headless
        self._proc: subprocess.Popen[bytes] | None = None
        self._profile = Path(tempfile.mkdtemp(prefix="enough-uicheck-chrome-"))
        self._port: int | None = None
        self._pages: list[Page] = []
        #: Captured at launch, while the process is certainly alive. Looking
        #: it up in `stop()` instead is a trap: once the parent has been
        #: reaped `os.getpgid` raises, and the gpu/network/renderer helpers
        #: — which are still in that group — survive the teardown.
        self._pgid: int | None = None

    # -- lifecycle ------------------------------------------------------
    def __enter__(self) -> Browser:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def start(self, *, timeout: float = 45.0) -> None:
        args = [
            self.binary,
            "--remote-debugging-port=0",
            f"--user-data-dir={self._profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-popup-blocking",
            "--hide-scrollbars",
            # Keep a background tab running at full speed. Without these,
            # requestAnimationFrame stops in whichever tab is not in front,
            # and every "wait until the layout settles" probe there burns
            # its whole timeout (measured: 4-5s a wait, against 0.06s).
            # These flags do it at the browser level; `Emulation
            # .setFocusEmulationEnabled` also works but makes *both* tabs
            # believe they have focus, which Chrome does not enjoy.
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--mute-audio",
            "--force-device-scale-factor=1",
            "about:blank",
        ]
        if self._headless:
            args.insert(1, "--headless=new")
        self._proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            self._pgid = os.getpgid(self._proc.pid)
        except (ProcessLookupError, PermissionError, OSError):
            self._pgid = None

        port_file = self._profile / "DevToolsActivePort"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise CDPError(
                    f"{self.binary} exited with {self._proc.returncode} before "
                    f"it wrote DevToolsActivePort")
            if port_file.is_file():
                lines = port_file.read_text(encoding="utf-8").splitlines()
                if lines and lines[0].strip().isdigit():
                    self._port = int(lines[0].strip())
                    break
            time.sleep(0.05)
        if self._port is None:
            raise CDPError(f"{self.binary} never reported a debugging port")

    def stop(self) -> None:
        for page in self._pages:
            page.close()
        self._pages.clear()
        proc = self._proc
        self._proc = None
        if proc is not None:
            # The whole SESSION, not just the process we spawned: Chrome
            # forks a gpu process, a network service and one renderer per
            # tab, and a stray renderer holding a core is exactly the kind
            # of leak that gets a pre-commit hook deleted. `start_new_session`
            # in `start()` is what makes the group addressable here.
            pgid = self._pgid
            if proc.poll() is None:
                self._signal_group(pgid, proc, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._signal_group(pgid, proc, signal.SIGKILL)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
            # Even after the parent is reaped, helpers can outlive a plain
            # SIGTERM. A second, unconditional SIGKILL to the group costs
            # nothing when the group is already empty and is the difference
            # between a clean exit and a warning line.
            self._signal_group(pgid, proc, signal.SIGKILL)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and self._group_alive(pgid):
                time.sleep(0.1)
        self._sweep_by_profile()
        shutil.rmtree(self._profile, ignore_errors=True)

    def _sweep_by_profile(self) -> None:
        """Last resort: kill anything still holding THIS profile directory.

        Chrome's helpers can outlive the group signal — the parent gets
        reaped, the gpu/network/renderer processes do not, and a pre-commit
        hook that leaves four Chrome processes burning a core is a hook the
        developer turns off. The match is the profile path, which is a fresh
        `mkdtemp` name owned by this run alone, so this can never touch the
        developer's own browser.
        """
        # The bare profile path, NOT "--user-data-dir=<path>": a pattern
        # starting with "--" is read as an option by BSD pkill and the sweep
        # silently matches nothing. The mkdtemp name is unique to this run,
        # so the bare path is specific enough on its own.
        pattern = str(self._profile)
        for sig in ("-TERM", "-KILL"):
            try:
                subprocess.run(["pkill", sig, "-f", pattern], timeout=10,
                               capture_output=True)
            except (OSError, subprocess.SubprocessError):
                return
            for _ in range(20):
                probe = subprocess.run(["pgrep", "-f", pattern],
                                       capture_output=True, text=True)
                if not probe.stdout.strip():
                    return
                time.sleep(0.1)

    @staticmethod
    def _signal_group(pgid: int | None, proc: subprocess.Popen[bytes],
                      sig: int) -> None:
        if pgid is not None:
            try:
                os.killpg(pgid, sig)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            proc.send_signal(sig)
        except (ProcessLookupError, PermissionError, OSError, ValueError):
            pass

    @staticmethod
    def _group_alive(pgid: int | None) -> bool:
        if pgid is None:
            return False
        try:
            os.killpg(pgid, 0)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    # -- targets --------------------------------------------------------
    def _http_json(self, path: str, *, timeout: float = 10.0) -> Any:
        import urllib.request
        url = f"http://127.0.0.1:{self._port}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def close_page(self, page: Page) -> None:
        """Close the TAB, not just our socket.

        `page.close()` only drops the WebSocket; the renderer keeps running,
        and a renderer that is spinning keeps burning a core for the rest of
        the run. `/json/close/<targetId>` goes through the browser process,
        which can kill a tab whose own renderer has stopped answering.
        """
        if page.target_id:
            try:
                self._http_json(f"/json/close/{page.target_id}")
            except Exception:                                    # noqa: BLE001
                pass
        page.close()
        if page in self._pages:
            self._pages.remove(page)

    def new_page(self, *, timeout: float = 30.0) -> Page:
        """Open a tab and attach to it.

        `Target.createTarget` over the browser-level socket would work too,
        but `/json/new` + `/json/list` is two plain HTTP calls and keeps this
        module free of session-id plumbing.
        """
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/json/new?about:blank", method="PUT")
        deadline = time.monotonic() + timeout
        info: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    info = json.loads(r.read().decode("utf-8"))
                break
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(0.1)
        if info is None:
            # Fall back to whatever tab the start URL already opened.
            for entry in self._http_json("/json/list") or []:
                if entry.get("type") == "page" and entry.get("webSocketDebuggerUrl"):
                    info = entry
                    break
        if not info or not info.get("webSocketDebuggerUrl"):
            raise CDPError("could not open a page target")
        page = Page(info["webSocketDebuggerUrl"],
                    target_id=str(info.get("id") or ""))
        page.enable_domains()
        self._pages.append(page)
        return page


def stray_debug_processes(pids: Iterable[int] = ()) -> list[str]:
    """`pgrep -fl remote-debugging-port`, minus the pids we know are ours.

    The harness calls this on the way out and prints anything left, because
    "did that run leak a Chrome?" should be answerable without the developer
    going to look.
    """
    try:
        out = subprocess.run(["pgrep", "-fl", "remote-debugging-port"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    mine = {str(p) for p in pids}
    return [line for line in out.splitlines()
            if line.strip() and line.split(" ", 1)[0] not in mine]
