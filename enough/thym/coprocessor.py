"""The coprocessor: the model behind a move's contract, and the two implementations that need no model (docs/THYM.md
12.2, 12.4, 19).

One interface, `Coprocessor.complete(contract, inputs, *, budget) -> Candidate`, with the shapes of section 12.2:

    Contract  = {move, schema, checks, repair}                         what the move needs back and what must hold
    Inputs    = {name: (value, digest)}                                the node's operands, by name
    Budget    = {attempts, output_words, prompt_tokens_max, seconds}   the node's budget and the machine's limits
    Candidate = {output, engine, attempts, tokens, seconds, checks: [{name, ok, why}]}

`schema` says what comes back (`{format: yaml | markdown, ...}`); `repair` is a mapping, `{allowed: [the narrow repairs
the move allows], failed: [the checks the last attempt failed, {name, ok, why}]}`, so that a second attempt can ask
again with the failures listed. One call is one attempt: the runtime owns the loop, runs the contract's checks on each
candidate and stops at the node's `attempts`. A coprocessor may say no by returning a `Refusal`.

Three implementations live here: `RefusingCoprocessor` (agent-free: the runtime refuses a plan that asks before any
call, so this one only ever answers a call that slipped through, with a refusal), `ReplayCoprocessor` (answers from the
candidates a run recorded, and refuses when the contract or an input's digest differs from the record's), and
`RecordingCoprocessor` (wraps any coprocessor and records every candidate for replay). The model-backed one,
`ModelCoprocessor`, is enough's and lives outside the package, in `enough/thym_host.py`.

A recorded candidate is `candidates/<key>.<attempt>.cosm` under the run's folder: `{contract: {move, schema, checks},
inputs: {name: sha256}, engine, attempts, tokens, seconds, output}`. The key comes from the node's call counter
(`engines.CallCounter`): `<node>` for the node's first request, `<node>-<k>` for every later request and every model
call an engine makes, so that no two calls of a node collide; the engine calls themselves are recorded beside them as
`<node>-e<k>` (`engines.py`). The runtime passes `at=(key, attempt)` to a coprocessor whose `complete` takes it.

`prose_problem(text)` is the reading THYM.md 12.2 asks of a schema'd answer: an answer that is to be YAML and has
prose before, after or instead of it fails `schema` on that attempt (the runtime asks again, "only the YAML"), so a
model that narrates never reaches the contract's slower checks.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import inspect
import os
import re
import threading
from pathlib import Path
from typing import Any, Protocol, TypedDict, runtime_checkable

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym.values import plain


class Contract(TypedDict):
    move: str
    schema: Any
    checks: list
    repair: Any


class Budget(TypedDict):
    attempts: int
    output_words: int
    prompt_tokens_max: int
    seconds: int


class Candidate(TypedDict):
    output: Any
    engine: str
    attempts: int
    tokens: int
    seconds: int
    checks: list


Inputs = dict          # {name: (Value, sha256)}


@runtime_checkable
class Coprocessor(Protocol):
    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget) -> Candidate | Refusal: ...


def candidate(output: Any, *, engine: str, attempts: int = 1, tokens: int = 0, seconds: int = 0,
              checks: list | None = None) -> Candidate:
    """A candidate with every field of section 12.2 (integers only: no floats reach a `.cosm`)."""
    return Candidate(output=output, engine=str(engine), attempts=int(attempts), tokens=int(tokens),
                     seconds=int(seconds), checks=list(checks or []))


def contract_key(contract: Contract) -> dict:
    """The part of a contract a replay compares: the move, the schema and the checks (not the repair state)."""
    return {"move": contract.get("move"), "schema": plain(contract.get("schema")),
            "checks": [str(c) for c in contract.get("checks") or []]}


def input_digests(inputs: Inputs) -> dict:
    return {str(k): (v[1] if isinstance(v, tuple) else getattr(v, "sha256", None)) for k, v in (inputs or {}).items()}


def ask(coprocessor: Any, contract: Contract, inputs: Inputs, *, budget: Budget,
        at: tuple[str, int] | None = None) -> Candidate | Refusal:
    """Call a coprocessor, passing `at` only when its `complete` takes it (the recording and replay ones do)."""
    fn = coprocessor.complete
    if at is not None and _takes_at(fn):
        return fn(contract, inputs, budget=budget, at=at)
    return fn(contract, inputs, budget=budget)


def _takes_at(fn: Any) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "at" in params or any(p.kind == p.VAR_KEYWORD for p in params.values())


_FENCE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\n(.*?)\n?[ \t]*```", re.S)
_KEY_LINE = re.compile(r"^[a-z_][a-z0-9_-]*[ \t]*:(?:[ \t]|$)")


def _said(text: str, limit: int = 60) -> str:
    one = " ".join(text.split())
    return one if len(one) <= limit else one[: limit - 1] + "…"


def prose_problem(text: str) -> str | None:
    """Why an answer that is to be one YAML mapping is not only that (THYM.md 12.2), or None when it is. The answer
    may sit in one fence; anything outside the fence, a second block, a fence left open (an answer cut off), or a
    first line that is not a lowercase YAML key (`Thinking Process:`, `Here is the YAML:`) is prose."""
    s = (text or "").strip()
    if not s:
        return "the answer is empty: give only the YAML, nothing before or after"
    blocks = list(_FENCE.finditer(s))
    if len(blocks) > 1:
        return "the answer holds more than one block: give only the YAML, nothing before or after"
    if blocks:
        b = blocks[0]
        outside = (s[: b.start()] + " " + s[b.end():]).strip()
        if outside:
            return f"prose around the YAML ({_said(outside)!r}): give only the YAML, nothing before or after"
        body = b.group(1)
    elif "```" in s:
        return "the answer opens a block it never closes (cut off?): give only the YAML, nothing before or after"
    else:
        body = s
    lines = [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#") and ln.strip() != "---"]
    if not lines:
        return "the answer holds no YAML: give only the YAML, nothing before or after"
    if not _KEY_LINE.match(lines[0]):
        return f"the answer starts with prose, not a YAML key ({_said(lines[0])!r}): give only the YAML, nothing " \
               "before or after"
    return None


def candidate_path(run_dir: Path, key: str, attempt: int) -> Path:
    return Path(run_dir) / "candidates" / f"{key}.{attempt}.cosm"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


class RefusingCoprocessor:
    """Agent-free's coprocessor (THYM.md 19). The runtime refuses a plan with model-backed nodes at plan time, with
    their count, so this answers only a call that reached it anyway: with a refusal, never a guess."""
    engine = "none"

    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget) -> Refusal:
        return Refusal("run", "agent-free", f"{contract.get('move')} asks a model; agent-free is on")


class RecordingCoprocessor:
    """Any coprocessor, with every candidate it gives written under `run_dir/candidates/` so the run replays."""

    def __init__(self, inner: Any, run_dir: Path) -> None:
        self.inner = inner
        self.run_dir = Path(run_dir)
        self._n = 0

    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget,
                 at: tuple[str, int] | None = None) -> Candidate | Refusal:
        cand = ask(self.inner, contract, inputs, budget=budget, at=at)
        if isinstance(cand, Refusal):
            return cand
        self._n += 1
        key, attempt = at if at is not None else (f"call-{self._n}", 1)
        record = {"contract": contract_key(contract), "inputs": input_digests(inputs),
                  "engine": cand.get("engine"), "attempts": int(cand.get("attempts") or 1),
                  "tokens": int(cand.get("tokens") or 0), "seconds": int(cand.get("seconds") or 0),
                  "output": plain(cand.get("output"))}
        _write_atomic(candidate_path(self.run_dir, key, attempt), mc.dump(record).encode("utf-8"))
        return cand


class ReplayCoprocessor:
    """The conformance suite's coprocessor (THYM.md 12.4): each call answered with the candidate recorded for that
    node and attempt, refused when the contract or an input's digest differs from the record's."""
    engine = "replay"

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)

    def complete(self, contract: Contract, inputs: Inputs, *, budget: Budget,
                 at: tuple[str, int] | None = None) -> Candidate | Refusal:
        if at is None:
            return Refusal("run", "replay", "a replay needs to know which node and attempt asks")
        key, attempt = at
        path = candidate_path(self.run_dir, key, attempt)
        if not path.is_file():
            return Refusal("run", "replay", f"no candidate was recorded for node {key}, attempt {attempt}")
        try:
            rec = mc.yaml_load(mc.read_text(path))
        except Exception as e:  # noqa: BLE001 - a broken record is a refusal, not a crash
            return Refusal("run", "replay", f"the candidate for node {key}, attempt {attempt} could not be read: {e}")
        if not isinstance(rec, dict):
            return Refusal("run", "replay", f"the candidate for node {key}, attempt {attempt} is not a mapping")
        want = rec.get("contract") or {}
        got = contract_key(contract)
        for k in ("move", "schema", "checks"):
            if plain(want.get(k)) != got[k]:
                return Refusal("run", "replay", f"node {key}: the contract's {k} differs from the record's "
                                                f"({got[k]!r}, recorded {want.get(k)!r})")
        rec_in = rec.get("inputs") or {}
        now_in = input_digests(inputs)
        if set(rec_in) != set(now_in):
            return Refusal("run", "replay", f"node {key}: the inputs are {sorted(now_in)}, the record's "
                                            f"{sorted(rec_in)}")
        for name, sha in now_in.items():
            if rec_in.get(name) != sha:
                return Refusal("run", "replay", f"node {key}: input {name} has sha256 {str(sha)[:12]}, the record's "
                                                f"{str(rec_in.get(name))[:12]}")
        return candidate(rec.get("output"), engine=str(rec.get("engine") or "replay"),
                         attempts=int(rec.get("attempts") or 1), tokens=int(rec.get("tokens") or 0),
                         seconds=int(rec.get("seconds") or 0))
