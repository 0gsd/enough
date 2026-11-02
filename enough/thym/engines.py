"""Engine calls, counted, recorded and replayed (docs/THYM.md 12.3, 12.4).

A move may reach one of enough's engines through `ctx.engines` (THYM.md 11.2): FEED's batch lookup (`feed`), Canon's
derivation (`canon.derive_passages`, `canon.derive_finish`, `canon.read_atem`, ...), DocOES (`docoes.enumerate`), the
surrounding catalog (`catalog`). What an engine answers depends on the machine (a dictionary built or not, a newer
enough), so a run that is to replay anywhere records every engine call beside its model calls, and a replay answers
each one from the record without running any engine: a replay needs no dictionary and no engine.

**The call counter.** Each node has one `CallCounter`, on the run context (`ctx.calls`), so that every call a node
makes has its own key and no two collide:

- the node's first request to the coprocessor takes the bare key, `<node>` (`candidates/3.1.cosm`);
- every other model call takes the next suffix, `<node>-<k>`, counted from 1 across the node's later requests and the
  model calls its engines make (Canon reads each passage through the coprocessor: `candidates/1-1.1.cosm`);
- every engine call the node makes takes the next engine number, `<node>-e<k>` (`candidates/1-e1.1.cosm`).

A recorded call is one candidate file, written once, at attempt 1 (an engine call has no attempts):

    candidates/<node>-e<k>.1.cosm   {engine: <name>[.<function>], inputs: {call: <sha256>}, keys: [<model keys>],
                                     tokens, seconds, output}   (or `raised: <what it raised>` instead of `output`)

`engine` names the engine and the function called; `inputs.call` is the sha256 of the call's arguments in canonical
form (positional, then keyword, a callable argument written `<engine>`, a path as a path relative to the run's inputs
root where it lies under it); `keys` are the model calls the engine made while it ran, by key, whose own candidates
sit beside it; `tokens` and `seconds` what they cost. Only a node's top-level engine calls are recorded: an engine
that calls another (Canon's derivation looks words up in FEED) records the outer call, whose answer holds the inner.

**Replay.** A replay of a run that recorded its engine calls (its trace's root item names them, `engines: [...]`)
answers each one from its record, by node, number and digest, and refuses at once when the engine or the digest
differs (check `replay`), before any engine or model work: the record is the whole of what the engine said. It
advances the node's counter past the model calls the engine made, so the keys after it agree with the record. A run
recorded before engine calls were (its trace names no `engines`) replays with the host's live engines, as it did.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Iterator

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym.values import Value, plain, sha256_bytes

CALLABLE = "<engine>"                  # how a callable argument is written in a call's digest


class EngineRefusal(Exception):
    """A replayed engine call that does not match its record: the run refuses with `refusal` (never a guess)."""

    def __init__(self, refusal: Refusal) -> None:
        super().__init__(str(refusal))
        self.refusal = refusal


class CallCounter:
    """One node's calls, numbered in the order it makes them (the keys of THYM.md 12.4; this module's docstring)."""

    def __init__(self, node: str) -> None:
        self.node = str(node)
        self.requests = 0                  # requests the node sent to the coprocessor
        self.suffix = 0                    # model calls with a suffixed key
        self.engine = 0                    # top-level engine calls
        self.tokens = 0                    # what the node's engine-made model calls cost
        self.depth = 0                     # above 0 while an engine call runs: its inner calls are its own
        self.made: list[str] = []          # every model key, in order

    def request_key(self) -> str:
        """The key of the node's next request: the bare node number the first time, a suffix after."""
        self.requests += 1
        if self.requests == 1:
            key = self.node
        else:
            self.suffix += 1
            key = f"{self.node}-{self.suffix}"
        self.made.append(key)
        return key

    def model_key(self) -> str:
        """The key of a model call an engine makes for the node (`EngineAdapter`)."""
        self.suffix += 1
        key = f"{self.node}-{self.suffix}"
        self.made.append(key)
        return key

    def engine_key(self) -> str:
        self.engine += 1
        return f"{self.node}-e{self.engine}"

    def skip(self, keys: list) -> None:
        """Advance past model calls a replayed engine call made when it was recorded."""
        for k in keys or []:
            k = str(k)
            if k == self.node:
                self.requests += 1
            else:
                self.suffix += 1
            self.made.append(k)

    def spend(self, tokens: Any) -> None:
        try:
            self.tokens += int(tokens or 0)
        except (TypeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# A call's digest, and its answer as a record holds it
# ---------------------------------------------------------------------------

def _arg(x: Any, inputs_root: Path | None) -> Any:
    if callable(x) and not isinstance(x, (str, bytes, Value)):
        return CALLABLE
    if isinstance(x, Value):
        return {"value": x.type, "sha256": x.sha256}
    if isinstance(x, Path):
        p = x
        if inputs_root is not None:
            try:
                return p.absolute().relative_to(Path(inputs_root).absolute()).as_posix()
            except ValueError:
                pass
        return p.as_posix()
    if isinstance(x, dict):
        return {str(k): _arg(v, inputs_root) for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        items = sorted(x, key=str) if isinstance(x, (set, frozenset)) else x
        return [_arg(v, inputs_root) for v in items]
    if isinstance(x, bytes):
        return {"bytes": sha256_bytes(x)}
    return x


def call_digest(name: str, args: tuple, kwargs: dict, *, inputs_root: Path | None = None) -> str:
    """The sha256 of one engine call: its name, its positional and its keyword arguments, in canonical form."""
    doc = {"engine": name, "args": [_arg(a, inputs_root) for a in args],
           "kwargs": {str(k): _arg(v, inputs_root) for k, v in sorted(kwargs.items())}}
    return sha256_bytes(mc.dump(doc).encode("utf-8"))


def _encode(x: Any) -> Any:
    """An engine's answer as YAML holds it: plain data; a path as text; a set as a sorted list."""
    if isinstance(x, Value):
        return plain(x.payload)
    if isinstance(x, dict):
        return {str(k): _encode(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_encode(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return [_encode(v) for v in sorted(x, key=str)]
    if isinstance(x, Path):
        return x.as_posix()
    if isinstance(x, bytes):
        return x.decode("utf-8", errors="replace")
    return x


def _write(path: Path, record: dict) -> None:
    from enough.thym.trace import write_atomic
    write_atomic(path, mc.dump(record).encode("utf-8"))


def _candidate(run_dir: Path, key: str) -> Path:
    return Path(run_dir) / "candidates" / f"{key}.1.cosm"


# ---------------------------------------------------------------------------
# `ctx.engines` during a run
# ---------------------------------------------------------------------------

class _Namespace:
    """An engine that is a set of functions (`canon`, `docoes`): each function reached through the wrapper."""

    def __init__(self, owner: "Engines", name: str, inner: Any) -> None:
        self._owner = owner
        self._name = name
        self._inner = inner

    def __getattr__(self, attr: str) -> Any:
        if attr.startswith("_"):
            raise AttributeError(attr)
        target = getattr(self._inner, attr)
        if not callable(target):
            return target
        return self._owner._call(f"{self._name}.{attr}", target)


class Engines(Mapping):
    """The engines a run's moves reach, by name, every call going through `call(name, fn, args, kwargs)`:
    `Recording` runs it live and records it, `Replaying` answers it from the record."""

    def __init__(self, names: list[str], counter: Callable[[], CallCounter | None], *,
                 inputs_root: Path | None = None) -> None:
        self._names = list(names)
        self._counter = counter
        self.inputs_root = Path(inputs_root) if inputs_root is not None else None

    def __getitem__(self, name: str) -> Any:
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def names(self) -> list[str]:
        return sorted(self._names)

    def _call(self, name: str, fn: Any) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            return self.call(name, fn, args, kwargs)
        call.__name__ = name.replace(".", "_")
        return call

    def call(self, name: str, fn: Any, args: tuple, kwargs: dict) -> Any:
        return fn(*args, **kwargs)


def _is_namespace(x: Any) -> bool:
    """A set of functions (`canon`, a SimpleNamespace) rather than one function (`feed`)."""
    return not callable(x)


class Recording(Engines):
    """Live engines, every top-level call recorded as `candidates/<node>-e<k>.1.cosm` under the run's folder."""

    def __init__(self, engines: Mapping, run_dir: Path, counter: Callable[[], CallCounter | None], *,
                 inputs_root: Path | None = None) -> None:
        super().__init__([str(k) for k in engines.keys()], counter, inputs_root=inputs_root)
        self._engines = dict(engines)
        self.run_dir = Path(run_dir)

    def __getitem__(self, name: str) -> Any:
        inner = self._engines[name]
        if _is_namespace(inner):
            return _Namespace(self, name, inner)
        return self._call(name, inner)

    def call(self, name: str, fn: Any, args: tuple, kwargs: dict) -> Any:
        counter = self._counter()
        if counter is None or counter.depth > 0:
            return fn(*args, **kwargs)             # outside a node, or inside another engine call: the outer records it
        key = counter.engine_key()
        record: dict = {"engine": name,
                        "inputs": {"call": call_digest(name, args, kwargs, inputs_root=self.inputs_root)}}
        first, spent = len(counter.made), counter.tokens
        counter.depth += 1
        t0 = time.monotonic()
        try:
            out = fn(*args, **kwargs)
        except EngineRefusal:
            raise
        except Exception as e:  # noqa: BLE001 - recorded, then raised again: a replay raises it at the same place
            counter.depth -= 1
            record.update(keys=counter.made[first:], tokens=counter.tokens - spent,
                          seconds=int(time.monotonic() - t0), raised=f"{type(e).__name__}: {e}")
            _write(_candidate(self.run_dir, key), record)
            raise
        counter.depth -= 1
        record.update(keys=counter.made[first:], tokens=counter.tokens - spent, seconds=int(time.monotonic() - t0),
                      output=_encode(out))
        _write(_candidate(self.run_dir, key), record)
        return out


class Replaying(Engines):
    """The engines of a recorded run, answered from its records: no engine runs (this module's docstring)."""

    def __init__(self, run_dir: Path, names: list[str], counter: Callable[[], CallCounter | None] | None = None, *,
                 inputs_root: Path | None = None) -> None:
        super().__init__([str(n) for n in names], counter or (lambda: None), inputs_root=inputs_root)
        self.run_dir = Path(run_dir)

    def bind(self, counter: Callable[[], CallCounter | None], inputs_root: Path | None = None) -> "Replaying":
        return Replaying(self.run_dir, self._names, counter,
                         inputs_root=inputs_root if inputs_root is not None else self.inputs_root)

    def __getitem__(self, name: str) -> Any:
        if name not in self._names:
            raise KeyError(name)
        return _ReplayEngine(self, name)

    def call(self, name: str, fn: Any, args: tuple, kwargs: dict) -> Any:
        counter = self._counter()
        if counter is None:
            raise EngineRefusal(Refusal("run", "replay", f"an engine call ({name}) outside any node"))
        key = counter.engine_key()
        path = _candidate(self.run_dir, key)
        if not path.is_file():
            raise EngineRefusal(Refusal("run", "replay", f"node {key}: the run calls {name} here and the record "
                                                         "holds no engine call"))
        try:
            rec = mc.yaml_load(mc.read_text(path))
        except Exception as e:  # noqa: BLE001 - a broken record is a refusal
            raise EngineRefusal(Refusal("run", "replay", f"node {key}: the engine record cannot be read: {e}")) from None
        if not isinstance(rec, dict):
            raise EngineRefusal(Refusal("run", "replay", f"node {key}: the engine record is not a mapping"))
        if rec.get("engine") != name:
            raise EngineRefusal(Refusal("run", "replay", f"node {key}: the run calls {name}, the record "
                                                         f"{rec.get('engine')}"))
        want = (rec.get("inputs") or {}).get("call")
        got = call_digest(name, args, kwargs, inputs_root=self.inputs_root)
        if want != got:
            raise EngineRefusal(Refusal("run", "replay", f"node {key}: the call to {name} has sha256 {got[:12]}, the "
                                                         f"record's {str(want)[:12]}"))
        counter.skip(rec.get("keys") or [])
        counter.spend(rec.get("tokens"))
        if "raised" in rec:
            raise RuntimeError(str(rec["raised"]))
        return rec.get("output")


class _ReplayEngine:
    """A recorded engine: callable (FEED's lookup) and a namespace of functions (Canon's) at once, since a replay
    cannot tell which it was without running it; the record says which function was called."""

    def __init__(self, owner: Replaying, name: str) -> None:
        self._owner = owner
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._owner.call(self._name, None, args, kwargs)

    def __getattr__(self, attr: str) -> Any:
        if attr.startswith("_"):
            raise AttributeError(attr)
        return self._owner._call(f"{self._name}.{attr}", None)


def recorded_names(trace_root_item: dict) -> list[str] | None:
    """The engines a recorded run's trace names (its root item's `engines`), or None for a run recorded before
    engine calls were."""
    names = trace_root_item.get("engines") if isinstance(trace_root_item, dict) else None
    return [str(n) for n in names] if isinstance(names, list) else None


__all__ = ["CALLABLE", "CallCounter", "EngineRefusal", "Engines", "Recording", "Replaying", "call_digest",
           "recorded_names"]
