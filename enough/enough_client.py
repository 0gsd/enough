"""enough_client: drive a running enough from another Python program (0.8, fabulac-first F6: the HTTP door).

One file, Python's standard library only (`urllib`), so it can be copied out of enough and into any program: put it
beside your code and `import enough_client`. It speaks enough's API promise 1 (`enough/api_promise.py`): it sends
the header `X-Enough-Api: 1` with every request (enough refuses a promised route that starts a run or writes
without it), and `check_promise()` refuses an enough that keeps another promise.

    import enough_client
    e = enough_client.Enough()                      # http://127.0.0.1:3456, or ENOUGH_URL
    e.begin("tally", starter="tool", licence="MIT")
    e.add("tally", "requirement", "tally never writes to the file it counts.", fields={"force": "must"})
    print(e.check("tally")["ok"])
    e.entail("tally")                               # a job: waits for it, and gives its result
    print(e.test("tally")["message"])               # the entailed tests, in enough's sandbox
    print(e.run("tally", ["count", "notes.md"], hand_over=["notes.md"])["stdout"])

A job route (begin, entail, take back, test, run) answers a job; the client polls `/api/canon/job/<id>` until it is
done and gives its result (`wait=False` gives the snapshot at once). A refusal is `EnoughError` with the status and
enough's own sentence.

What enough runs, it runs only in its sandbox: a folder of its own, no network, limits on time, output and disk, and
a stop. A service is authored and entailed, and refused at run (serving comes in a later minor).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterable, Optional

PROMISE = 1
HEADER = "X-Enough-Api"
DEFAULT_URL = "http://127.0.0.1:3456"
DONE = ("done", "failed", "cancelled")

#: `transport(method, url, headers, body) -> (status, body)`: how a request is sent. The default is urllib's; a test
#: may hand in another (an in-process app).
Transport = Callable[[str, str, dict, Optional[bytes]], "tuple[int, bytes]"]


class EnoughError(Exception):
    """enough refused, or a job did not finish well: `status` (HTTP, or the job's state) and enough's sentence."""

    def __init__(self, status: Any, detail: str, answer: Any = None):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail
        self.answer = answer


def urllib_transport(timeout: float) -> Transport:
    def send(method: str, url: str, headers: dict, body: Optional[bytes]) -> "tuple[int, bytes]":
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 - the person's own enough
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
    return send


class Enough:
    """One running enough (one project). Every method is one promised route."""

    def __init__(self, url: Optional[str] = None, *, timeout: float = 60.0, transport: Optional[Transport] = None,
                 poll: float = 0.2):
        self.url = (url or os.environ.get("ENOUGH_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.poll = poll
        self._send = transport or urllib_transport(timeout)

    # -- the wire --------------------------------------------------------------------------------------------------

    def request(self, method: str, path: str, body: Optional[dict] = None, query: Optional[dict] = None) -> Any:
        url = self.url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        headers = {HEADER: str(PROMISE), "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps({k: v for k, v in body.items() if v is not None}).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, raw = self._send(method, url, headers, data)
        try:
            answer = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            answer = raw.decode("utf-8", "replace")
        if status >= 400:
            detail = answer.get("detail") if isinstance(answer, dict) else answer
            raise EnoughError(status, str(detail), answer)
        return answer

    def _get(self, where: str, /, **query: Any) -> Any:
        return self.request("GET", where, query=query)

    def _post(self, where: str, /, **body: Any) -> Any:
        return self.request("POST", where, body=body)

    # -- jobs ------------------------------------------------------------------------------------------------------

    def job(self, job_id: str) -> dict:
        return self._get(f"/api/canon/job/{urllib.parse.quote(str(job_id))}")

    def wait(self, answer: dict, timeout: Optional[float] = None) -> dict:
        """The result of the job an answer names, once it is done; EnoughError when it failed or was cancelled. An
        answer that is no job is given back as it is."""
        snap = answer.get("job") if isinstance(answer, dict) else None
        if not isinstance(snap, dict):
            return answer
        deadline = time.monotonic() + (timeout if timeout is not None else max(self.timeout, 600.0))
        while snap.get("state") not in DONE:
            if time.monotonic() > deadline:
                raise EnoughError("timeout", f"job {snap.get('id')} is still {snap.get('state')}", snap)
            time.sleep(self.poll)
            snap = self.job(snap["id"])
        if snap["state"] != "done":
            raise EnoughError(snap["state"], str(snap.get("error") or snap.get("message")), snap)
        return snap.get("result") if isinstance(snap.get("result"), dict) else {"result": snap.get("result")}

    def _maybe_wait(self, answer: dict, wait: bool) -> dict:
        return self.wait(answer) if wait else answer

    # -- the promise -----------------------------------------------------------------------------------------------

    def promise(self) -> dict:
        return self._get("/api/fabulac/promise")

    def check_promise(self) -> dict:
        """The promise this enough keeps; EnoughError when it is not this client's."""
        p = self.promise()
        if p.get("version") != PROMISE:
            raise EnoughError("promise", f"this enough keeps API promise {p.get('version')}; this client speaks "
                                         f"{PROMISE}", p)
        return p

    # -- authoring -------------------------------------------------------------------------------------------------

    def starters(self) -> list:
        return self._get("/api/fabulac/starters")["starters"]

    def begin(self, path: str, *, kind: Optional[str] = None, licence: Optional[str] = None,
              brief: Optional[str] = None, by: Optional[str] = None, starter: Optional[str] = None,
              mode: Optional[str] = None, route: Optional[str] = None, wait: bool = True) -> dict:
        """Begin an authored fabulac (or from a starter), or take its interview up again."""
        return self._maybe_wait(self._post("/api/fabulac/begin", path=path, kind=kind, licence=licence, brief=brief,
                                           by=by, starter=starter, mode=mode, route=route), wait)

    def answer(self, path: str, answers: Iterable[dict]) -> dict:
        """The person's answers: `[{"question": id, "says": their words}]`."""
        return self._post("/api/fabulac/answer", path=path, answers=list(answers))

    def status(self, path: str) -> dict:
        return self._get("/api/fabulac/status", path=path)

    def add(self, path: str, as_: str, says: str, *, fields: Optional[dict] = None) -> dict:
        return self._post("/api/fabulac/add", path=path, **{"as": as_}, says=says, fields=fields)

    def check(self, path: str) -> dict:
        return self._get("/api/fabulac/check", path=path)

    # -- entailing and keeping in step -----------------------------------------------------------------------------

    def entail(self, path: str, *, overwrite: Iterable[str] = (), route: Optional[str] = None,
               model: Optional[str] = None, wait: bool = True) -> dict:
        return self._maybe_wait(self._post("/api/fabulac/entail", path=path, overwrite=list(overwrite) or None,
                                           route=route, model=model), wait)

    def moved(self, path: str) -> dict:
        return self._get("/api/fabulac/moved", path=path)

    def keep(self, path: str, files: Iterable[str], *, because: Optional[str] = None) -> dict:
        return self._post("/api/fabulac/keep", path=path, files=list(files), because=because)

    def let_go(self, path: str, files: Iterable[str]) -> dict:
        return self._post("/api/fabulac/let-go", path=path, files=list(files))

    def take_back(self, path: str, file: str, *, route: Optional[str] = None, wait: bool = True) -> dict:
        return self._maybe_wait(self._post("/api/fabulac/take-back", path=path, file=file, route=route), wait)

    # -- running, in the sandbox -----------------------------------------------------------------------------------

    def test(self, path: str, *, wait: bool = True) -> dict:
        return self._maybe_wait(self._post("/api/fabulac/test", path=path), wait)

    def run(self, path: str, args: Iterable[str] = (), *, stdin: str = "", hand_over: Iterable[str] = (),
            wait: bool = True) -> dict:
        return self._maybe_wait(self._post("/api/fabulac/run", path=path, args=list(args), stdin=stdin or None,
                                           hand_over=list(hand_over) or None), wait)

    def stop(self, path: Optional[str] = None, *, run: Optional[str] = None) -> dict:
        return self._post("/api/fabulac/stop", path=path, run=run)

    # -- a program of parts ----------------------------------------------------------------------------------------

    def head(self, path: str, parts: Iterable[str], *, name: Optional[str] = None, licence: Optional[str] = None,
             by: Optional[str] = None) -> dict:
        return self._post("/api/fabulac/head", path=path, parts=list(parts), name=name, licence=licence, by=by)

    def parts_moved(self, path: str) -> dict:
        return self._get("/api/fabulac/parts-moved", path=path)


#: The promised routes this client calls, as (method, path): `tests/test_api_promise.py` holds them to the table.
CALLS: tuple = (
    ("GET", "/api/fabulac/promise"), ("GET", "/api/fabulac/starters"), ("POST", "/api/fabulac/begin"),
    ("POST", "/api/fabulac/answer"), ("GET", "/api/fabulac/status"), ("POST", "/api/fabulac/add"),
    ("GET", "/api/fabulac/check"), ("POST", "/api/fabulac/entail"), ("GET", "/api/fabulac/moved"),
    ("POST", "/api/fabulac/keep"), ("POST", "/api/fabulac/let-go"), ("POST", "/api/fabulac/take-back"),
    ("POST", "/api/fabulac/test"), ("POST", "/api/fabulac/run"), ("POST", "/api/fabulac/stop"),
    ("POST", "/api/fabulac/head"), ("GET", "/api/fabulac/parts-moved"), ("GET", "/api/canon/job/{job_id}"),
)

__all__ = ["CALLS", "DEFAULT_URL", "Enough", "EnoughError", "HEADER", "PROMISE", "urllib_transport"]
