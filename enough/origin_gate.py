"""The Origin gate (0.9, route guards: pins section 5): no page on another site may change enough's state.

enough serves on `127.0.0.1`, and any page the person has open in a browser can send a form or a fetch there. A
browser names the page that sent a request in its `Origin` header, on every POST, PUT, PATCH and DELETE, and on a
fetch of any method from another origin. So every request that changes state (`guarded`) passes only when:

- it carries no `Origin` (a program that is not a browser: the tests, `enough_client`, curl, the desktop shell's
  own Rust client), and no `Sec-Fetch-Site` saying another site sent it; or
- its `Origin` is one of enough's own (`own_origin`): the server's own address as bound, the loopback names
  (`127.0.0.1`, `localhost`, `[::1]`) on the server's own port, or the desktop shell's webview
  (`tauri://localhost`, `http(s)://tauri.localhost`; the shell then navigates the window to
  `http://127.0.0.1:<port>`, so the enough page itself is same-origin there).

Anything else is answered 403 with a sentence. A GET that only reads is never guarded (a browser lets another site
send it but not read its answer); the three GETs that change something (`STATE_GETS`) are. The server-sent-event
stream and `/static` are reads and pass untouched.

Raw ASGI, as `ModeGate` and `PromiseGate` are, so the SSE stream's receive channel stays untouched. The port is
read from the request's own socket (`scope["server"]`), never from the `Host` header a page could choose.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

#: The GETs that change state or start something (each is a link the page or the chat follows).
STATE_GETS: frozenset[str] = frozenset({
    "/api/reset",           # clears the conversation
    "/api/update-enough",   # copies missing default files into the project
    "/api/reveal",          # opens the file manager
})
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})
#: The desktop shell's webview, as Tauri 2 names it: `tauri://localhost` on macOS and Linux, `http(s)://tauri.localhost`
#: on Windows. Its own pages (loading, onboarding) call the backend through Rust, but a webview origin is enough's own.
SHELL_ORIGINS: frozenset[str] = frozenset({"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"})

REFUSED = ("a page at {origin} may not change enough: only enough's own page (or a program that is not a browser) "
           "may write here")
REFUSED_SITE = ("a page on another site may not change enough: only enough's own page (or a program that is not a "
                "browser) may write here")

_ORIGIN = b"origin"
_FETCH_SITE = b"sec-fetch-site"


def guarded(method: str, path: str) -> bool:
    """True for a request that changes state: every write method, and the GETs in `STATE_GETS` (a HEAD of one runs
    the same handler, so it is guarded too)."""
    m = method.upper()
    if m in _READ_METHODS:
        return m != "OPTIONS" and path in STATE_GETS
    return True


def own_origin(origin: str, server: tuple[str, int] | None, port: int | None = None) -> bool:
    """Is `origin` one of enough's own? `server` is the socket's own (host, port); `port` the one the app was made
    for, when known. Pure."""
    o = (origin or "").strip().lower().rstrip("/")
    if o in SHELL_ORIGINS:
        return True
    try:
        parts = urlsplit(o)
        host, oport = parts.hostname, parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host or parts.path or parts.query:
        return False
    if oport is None:
        oport = 443 if parts.scheme == "https" else 80
    ports = {p for p in ((server[1] if server else None), port) if p}
    if oport not in ports:
        return False
    if host in LOOPBACK_HOSTS:
        return True
    # The address the socket is bound to, as itself (a test client's `testserver`, a server bound elsewhere).
    return bool(server) and host == str(server[0]).lower().strip("[]") and oport == server[1]


def refusal(method: str, path: str, origin: str | None, fetch_site: str | None,
            server: tuple[str, int] | None, port: int | None = None) -> str | None:
    """The 403 sentence for a request the gate refuses, else None. Pure."""
    if not guarded(method, path):
        return None
    if origin is None:
        # A browser that leaves Origin off (a link, an image) still says where the request came from.
        if (fetch_site or "").strip().lower() in ("cross-site", "same-site"):
            return REFUSED_SITE
        return None
    if own_origin(origin, server, port):
        return None
    return REFUSED.format(origin=origin.strip() or "(empty)")


class OriginGate:
    """403 a request that changes state from a page that is not enough's own. Raw ASGI; a read costs a set lookup."""

    def __init__(self, app: Any, *, port: int | None = None) -> None:
        self.app = app
        self.port = port

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and guarded(scope.get("method", "GET"), scope.get("path", "")):
            origin = site = None
            for k, v in scope.get("headers") or ():
                key = k.lower()
                if key == _ORIGIN:
                    origin = v.decode("latin-1")
                elif key == _FETCH_SITE:
                    site = v.decode("latin-1")
            server = scope.get("server")
            why = refusal(scope.get("method", "GET"), scope.get("path", ""), origin, site,
                          tuple(server) if server else None, self.port)
            if why:
                await JSONResponse({"detail": why}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


__all__ = ["LOOPBACK_HOSTS", "OriginGate", "SHELL_ORIGINS", "STATE_GETS", "guarded", "own_origin", "refusal"]
