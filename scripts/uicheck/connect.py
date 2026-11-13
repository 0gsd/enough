"""A stand-in Comprise Connect for the browser harness: the Allograph Registry (Ascribe 14.7 to 14.13) and Connect's
device flow, on a loopback port, so the allograph panel can be drawn and driven without reaching compriseconnect.com.

It is `FakeRegistry` from tests/test_allograph_registry.py (the registry the client's tests are held to: nonces per
account, signatures verified against each listing's key, proofs, attestations waiting and accepted, bonds), wrapped in
a small HTTP server on a thread; the scratch project server is pointed at it with both `ENOUGH_CONNECT_URL` and
`ENOUGH_ALLOGRAPH_URL`, as Connect and the registry's own address are one service (http is allowed for a loopback
address only, `allograph_registry.normalize_url`). Two things are added for the screens:

- the device flow approves itself at the second poll, so a sign-in shows its code once and then completes;
- one listing is there from the start, the text's own example (`harbour-baker`, *bread, slowly*, `#ts7de32a5bnz`),
  so a search and a look-up by tag have something to find; and `POST /__attest {of}` makes that listing attest the
  first claim of the listing `of`, so an attestation waits for its holder.

Nothing here touches the OS keychain or the network beyond its own port; it holds everything in memory and is gone
when it stops.
"""

from __future__ import annotations

import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]


def _tests():
    """tests/test_allograph_registry.py (and the allograph registry module), imported from the checkout."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    return importlib.import_module("tests.test_allograph_registry")


class StandInConnect:
    """`start()` serves on 127.0.0.1:<port>; `url` is what `ENOUGH_CONNECT_URL` and `ENOUGH_ALLOGRAPH_URL` take;
    `stop()` ends it."""

    def __init__(self) -> None:
        self.port = 0
        self.url = ""
        self.fake: Any = None
        self._srv: ThreadingHTTPServer | None = None
        self._polls = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        mod = _tests()
        R = mod.R
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self._srv.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        mod.URL = mod.REGISTRY = self.url        # FakeRegistry checks every request is for its own address
        self.fake = mod.FakeRegistry()
        # The text's example listing, as its holder sent it (section 14.8): already listed here.
        self._example_key = R.key_from_seed(mod.SEED)
        signed = R.sign(R.statement("list", self._example_key.tag, "a" * 26, key=self._example_key.key,
                                    name="harbour-baker", allograph=json.loads(mod.SPEC_ALLOGRAPH),
                                    dangler="bread, slowly", owner=None,
                                    show={"faceplaces": "counted", "same_name": True}), self._example_key)
        self.fake.listings[self._example_key.tag] = signed
        threading.Thread(target=self._srv.serve_forever, name="stand-in-connect", daemon=True).start()

    def stop(self) -> None:
        srv, self._srv = self._srv, None
        if srv is not None:
            srv.shutdown()
            srv.server_close()

    # -- what the screens need beyond the registry --------------------------------------------------------------

    def attest(self, of: str) -> str:
        """The example listing attests the first claim of the listing `of` (as a client, named); it waits for `of`'s
        holder. Returns the attestation's digest."""
        mod = _tests()
        R = mod.R
        ls = self.fake.listings[of]["statement"]
        first = ls["allograph"]["expertise"][0]
        st = R.statement("attest", self._example_key.tag, "b" * 26, of=of,
                         claims=[{"kind": first["kind"], "form": first["form"]}], epoch=ls["allograph"]["epoch"],
                         named=True, **{"as": "client"})
        digest = R.attestation_digest(st)
        self.fake.waiting.setdefault(of, {})[digest] = R.sign(st, self._example_key)
        return digest

    def _answer(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        if path == "/__attest":
            of = str((body or {}).get("of") or "")
            if of not in self.fake.listings:
                return 404, {"error": "not_listed", "detail": "No listing."}
            return 200, {"attestation": self.attest(of)}
        if path == "/api/v0/device/token":
            self._polls += 1
            if self._polls >= 2:
                self.fake.approved = True
        if path == "/api/v0/device/code":
            self._polls = 0
            self.fake.approved = False
        return self.fake(method, self.url + path, body, token)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _go(self, method: str) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                try:
                    body = json.loads(raw) if raw else None
                except ValueError:
                    body = None
                auth = self.headers.get("Authorization") or ""
                token = auth[len("Bearer "):] if auth.startswith("Bearer ") else None
                try:
                    with outer._lock:
                        status, got = outer._answer(method, self.path, body, token)
                except Exception as e:  # noqa: BLE001 - a stand-in says what broke, as a 500
                    status, got = 500, {"error": "stand_in", "detail": f"{type(e).__name__}: {e}"}
                data = json.dumps(got).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - the stdlib's names
                self._go("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._go("POST")

            def do_DELETE(self) -> None:  # noqa: N802
                self._go("DELETE")

            def log_message(self, *_a: Any) -> None:
                pass

        return Handler


if __name__ == "__main__":                                    # a stand-in to point a scratch server at by hand
    c = StandInConnect()
    c.start()
    print(c.url, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        c.stop()
