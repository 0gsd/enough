"""enough's API promise (0.8, fabulac-first F6: pins section 4): the routes another program may drive enough by,
named, versioned and tested as one.

`ROUTES` is the one table: each promised route's method, path, what it takes and what it gives, and whether it
starts a run or writes. `VERSION` is the promise's version, and the value of the header `X-Enough-Api` that
`enough_client` sends with every request. A route outside this table is free to change between releases; a promised
one changes only with a new version (and its old name kept for one release through `retired_names`).

**The header gate.** Every promised route that starts a run or writes (`gated`: each POST here) requires the header
`X-Enough-Api: 1`. It is the client's version and the CSRF gate at once: a page on another site cannot send a custom
header to `127.0.0.1` without a CORS preflight, which enough never answers, so a form or a fetch from elsewhere can
start nothing. A request without it, or with another version, is answered 403 with a sentence (`PromiseGate`, raw
ASGI beside `ModeGate`). The page sends the header too.

`tests/test_api_promise.py` holds this table, the app's routes and `enough/enough_client.py` to each other.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from starlette.responses import JSONResponse

VERSION = 1
HEADER = "X-Enough-Api"
_HEADER_KEY = HEADER.lower().encode("latin-1")

MISSING = ("this route is part of enough's API promise and starts a run or writes: send the header "
           f"{HEADER}: {VERSION} (the page and enough_client do)")
WRONG = ("this enough keeps API promise {have}; the request speaks {said}. Use a client of promise {have}, or the "
         "page")


@dataclasses.dataclass(frozen=True)
class Promised:
    method: str
    path: str
    takes: tuple[str, ...]
    gives: tuple[str, ...]
    does: str
    gated: bool
    since: int = 1


def _p(method: str, path: str, takes: str, gives: str, does: str) -> Promised:
    return Promised(method, path, tuple(takes.split()), tuple(gives.split()), does, gated=method == "POST")


#: The promise, version 1. `takes`: the body's keys (POST) or the query's (GET), `?` marking optional ones; `gives`:
#: the answer's keys a client may rely on (a job route gives `job`, the CanonJob snapshot, and its `result` once done).
ROUTES: tuple[Promised, ...] = (
    _p("GET", "/api/fabulac/promise", "", "name version header routes",
       "the promise itself: its version and every promised route"),
    _p("GET", "/api/fabulac/starters", "", "starters",
       "the starters to begin from: a tool, a library, a service"),
    _p("POST", "/api/fabulac/begin", "path kind? licence? brief? by? starter? mode? route?", "job|fabulac",
       "begin an authored fabulac (a job), or from a starter (at once); again, take it up"),
    _p("POST", "/api/fabulac/answer", "path answers", "path recorded refused",
       "record the person's answers to the questions shown"),
    _p("GET", "/api/fabulac/status", "path", "fabulac program interview entailment last_run",
       "where an authored fabulac stands"),
    _p("POST", "/api/fabulac/add", "path as says fields?", "fabulac added item",
       "add a requirement, decision, case or interface in the person's words"),
    _p("GET", "/api/fabulac/check", "path", "ok errors warnings uncovered source entailment",
       "the fabulac's checks, and the requirements no case shows"),
    _p("POST", "/api/fabulac/entail", "path overwrite? route? model? calls?", "job",
       "entail it as its program (a job; only a model writes sources)"),
    _p("GET", "/api/fabulac/moved", "path", "folder entailed files moved edited gone kept new tell",
       "what moved since the last entailment, and every hand edit"),
    _p("POST", "/api/fabulac/keep", "path files because?", "kept",
       "keep files changed by hand (a recorded decision)"),
    _p("POST", "/api/fabulac/let-go", "path files", "released",
       "let kept files go: the next entailment tells them again"),
    _p("POST", "/api/fabulac/take-back", "path file route? model?", "job",
       "take a hand edit back into the fabulac as questions (a job)"),
    _p("POST", "/api/fabulac/test", "path", "job",
       "run the entailed tests in the sandbox (a job)"),
    _p("POST", "/api/fabulac/run", "path args? stdin? hand_over?", "job",
       "run the tool in the sandbox (a job); a service is refused"),
    _p("POST", "/api/fabulac/stop", "path? run?", "stopped",
       "stop a run, a test or a job of that fabulac"),
    _p("POST", "/api/fabulac/head", "path parts name? licence? by?", "head uri parts",
       "make a head fabulac over parts"),
    _p("GET", "/api/fabulac/parts-moved", "path", "head parts moved",
       "which parts of a head moved"),
    _p("GET", "/api/canon/job/{job_id}", "", "id kind state message result error",
       "a job's snapshot: poll it until its state is done, failed or cancelled"),
)

_GATED: frozenset[tuple[str, str]] = frozenset((r.method, r.path) for r in ROUTES if r.gated)


def payload() -> dict[str, Any]:
    """What `GET /api/fabulac/promise` answers."""
    return {"name": "enough", "version": VERSION, "header": HEADER,
            "routes": [{"method": r.method, "path": r.path, "takes": list(r.takes), "gives": list(r.gives),
                        "does": r.does, "gated": r.gated, "since": r.since} for r in ROUTES]}


def gated(method: str, path: str) -> bool:
    return (method.upper(), path) in _GATED


#: 0.9 (route guards, pins section 5): the older routes that start a model run take the header too. They are not
#: promised (another program may not rely on their shape), but the page sends the header on every API call, so a
#: page elsewhere, which cannot send it without a preflight enough never answers, starts no model. Exact POST paths,
#: and every POST under `MODEL_RUN_PREFIXES` but `MODEL_RUN_OPEN` (stopping a council is always allowed).
#: `POST /api/model` is not here: it loads a model and starts no run, and the desktop shell's first-run wizard posts
#: it from Rust without the header. The Origin gate (`enough/origin_gate.py`) covers it as it covers every write.
MODEL_RUNS: frozenset[str] = frozenset({
    "/api/chat",
    "/api/cloud/health-check",
    "/api/transcribe",
    "/api/canon/read",
    "/api/canon/atem",
    "/api/thym/run",
    "/api/fabula/derive",
    "/api/fabula/build",
    "/api/fabula/resume",
    "/api/fabula/compile",
    "/api/fabula/verse/build",
    "/api/fabula/verse/resume",
    "/api/dialectic/settle",
    "/api/composure/scaffold/check",
})
MODEL_RUN_PREFIXES: tuple[str, ...] = ("/api/council/",)
MODEL_RUN_OPEN: frozenset[str] = frozenset({"/api/council/pause"})

MODEL_RUN_MISSING = (f"this route starts a model run: send the header {HEADER}: {VERSION} (the page and "
                     "enough_client do)")


def model_run(method: str, path: str) -> bool:
    """True for an older route that starts a model run (0.9): it takes the header as a promised route does."""
    if method.upper() != "POST" or path in MODEL_RUN_OPEN:
        return False
    return path in MODEL_RUNS or path.startswith(MODEL_RUN_PREFIXES)


def refusal(method: str, path: str, said: str | None) -> str | None:
    """The 403 sentence for a request the gate refuses, else None. Pure."""
    promised = gated(method, path)
    if not promised and not model_run(method, path):
        return None
    if said is None or not said.strip():
        return MISSING if promised else MODEL_RUN_MISSING
    if said.strip() != str(VERSION):
        return WRONG.format(have=VERSION, said=said.strip())
    return None


class PromiseGate:
    """403 a promised route that starts a run or writes, without `X-Enough-Api: 1`. Raw ASGI, as `ModeGate` is, so
    the SSE stream's receive channel stays untouched; a request the table does not gate costs one set lookup."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        method, path = scope.get("method", "GET"), scope.get("path", "")
        if scope.get("type") == "http" and (gated(method, path) or model_run(method, path)):
            said = None
            for k, v in scope.get("headers") or ():
                if k.lower() == _HEADER_KEY:
                    said = v.decode("latin-1")
                    break
            why = refusal(scope.get("method", "GET"), scope.get("path", ""), said)
            if why:
                await JSONResponse({"detail": why}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


__all__ = ["HEADER", "MODEL_RUNS", "PromiseGate", "Promised", "ROUTES", "VERSION", "gated", "model_run", "payload",
           "refusal"]
