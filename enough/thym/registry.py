"""Move implementations by name: the registry the runtime calls (docs/THYM.md 6, 11.2, 12.1, 17.6, 19).

A manifest declares a move (its `moves:` block, section 17.6); this registry holds the code that runs it. The
moves lane's modules (`enough/thym/moves/`) register themselves when imported, and `load_all` imports every module a
declaration's `code: module:function` names, registering the function itself when the module did not. Scaffolds (the
rules-mode stand-ins of section 19) are registered under `<move>.scaffold` or under the scaffold's own name
(`rules-twin`, `outline`); prompt builders for the model coprocessor under `<move>.prompt` (`prompt_for`).

The calling convention, frozen for the moves lane:

    fn(ctx, *operands: Value, **modifiers) -> Value | Request | None

- `ctx` is the run's `MoveContext` (`enough.thym.run`): `ctx.run` (the run id `made` names), `ctx.node` (the plan
  node), `ctx.decls` (the declarations, by name), `ctx.coprocessor`, `ctx.rules`, `ctx.now` (the run's start, UTC),
  `ctx.emitted` and `ctx.slots` (what `emit` collected), `ctx.withheld` (item key -> item: `values.item_key`, `values.is_withheld`) and `ctx.withhold(*items)`,
  `ctx.inputs_root`, `ctx.root`, `ctx.stage`, `ctx.trace()` (the run's trace so far, as a value).
- `operands` are values (`enough.thym.values.Value`), in the order the call writes them.
- `modifiers` are keyed by the modifier word itself (`as`, `by`, `with`, `to`, `against`, `of`, `in`, `where`), so a
  move reads `modifiers.get("as")`. `as` gives a word (`str`) or a list of words; `by` a word; `with`, `against`,
  `of` and `in` a value; `to` an `Amount(n, unit)`; `where` a `Where` (`.text`, `.test(item) -> bool`,
  `.select(value) -> list[Value]`). `marked` never arrives: the planner makes it a `mark` node of its own.
- A deterministic move returns its value (or None for nothing; any other payload is wrapped in the declaration's
  `gives` type). A model-backed move returns a `Request`; the runtime sends it to the coprocessor, turns the
  candidate's output into a value with `parse`, checks it against the move's contract, repairs and retries within
  the node's attempts, and stamps `made`. A scaffold is called the same way and returns a value.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from enough import macrocosm as mc

MoveFn = Callable[..., Any]


@dataclass
class Request:
    """What a model-backed move asks of the coprocessor (THYM.md 12.2). `contract` holds what the move knows of its
    contract: `schema` (`{format: yaml | markdown, ...}`, what it needs back) and `repair` (the narrow repairs it
    allows, a list of names); the runtime fills in `move` and `checks` (the declaration's `contract`). `inputs` are
    the values the model reads, by name. `budget` overrides the node's (`attempts`, `output_words`, `seconds`).
    `parse(output)` turns a candidate's output into the value (a `Value`, or a payload the runtime wraps); a raise or
    None is a failed reading, retried like a failed check. `repair(value, failed)` is the move's narrow repair: given
    the value and the failed checks (`[{name, ok, why}]`) it returns a repaired value, or None to ask again."""
    contract: dict
    inputs: dict
    budget: dict | None = None
    parse: Callable[[Any], Any] | None = None
    repair: Callable[[Any, list], Any] | None = None


class Moves:
    """A registry of move implementations, scaffolds and prompt builders, by name. The module-level `MOVES` is the
    one the moves lane registers into; a test builds its own and passes it to `run(..., moves=)`."""

    def __init__(self) -> None:
        self._fns: dict[str, MoveFn] = {}

    def implements(self, name: str, *, replace: bool = True) -> Callable[[MoveFn], MoveFn]:
        def deco(fn: MoveFn) -> MoveFn:
            self.add(name, fn, replace=replace)
            return fn
        return deco

    def add(self, name: str, fn: MoveFn, *, replace: bool = True) -> None:
        if not callable(fn):
            raise TypeError(f"{name}: a move implementation is a callable")
        if replace or name not in self._fns:
            self._fns[name] = fn

    def lookup(self, name: str) -> MoveFn | None:
        return self._fns.get(name)

    def remove(self, name: str) -> None:
        self._fns.pop(name, None)

    def names(self) -> list[str]:
        return sorted(self._fns)

    def copy(self) -> "Moves":
        other = Moves()
        other._fns = dict(self._fns)
        return other

    def scaffold(self, decl: Any) -> MoveFn | None:
        """The rules-mode stand-in of a declared move: `<move>.scaffold`, else the scaffold's own name."""
        name = decl_get(decl, "name")
        fn = self.lookup(f"{name}.scaffold") if name else None
        sc = decl_get(decl, "scaffold")
        return fn or (self.lookup(str(sc)) if sc else None)

    def prompt(self, move: str) -> MoveFn | None:
        """The prompt builder the model coprocessor uses for a move: `fn(contract, inputs) -> messages`."""
        return self.lookup(f"{move}.prompt")


MOVES = Moves()


def implements(name: str, *, replace: bool = True) -> Callable[[MoveFn], MoveFn]:
    """Register a move implementation (or a scaffold, as `<move>.scaffold`) in the default registry."""
    return MOVES.implements(name, replace=replace)


def prompt_for(move: str) -> Callable[[MoveFn], MoveFn]:
    """Register a prompt builder for a model-backed move: `fn(contract, inputs) -> [{role, content}, ...]`."""
    return MOVES.implements(f"{move}.prompt")


def lookup(name: str) -> MoveFn | None:
    return MOVES.lookup(name)


# ---------------------------------------------------------------------------
# Declarations and their `code:` paths
# ---------------------------------------------------------------------------

def decl_get(decl: Any, key: str, default: Any = None) -> Any:
    """One key of a declaration, whether it is the compiler's `MoveDecl` (attributes) or a mapping."""
    if decl is None:
        return default
    if isinstance(decl, dict):
        v = decl.get(key, default)
    else:
        v = getattr(decl, key, default)
    return default if v is None else v


def resolve(code: str) -> MoveFn | None:
    """The callable a `module:function` path names, importing the module; None when it cannot be imported or holds
    no such callable."""
    if not isinstance(code, str) or ":" not in code:
        return None
    mod, _, fn = code.partition(":")
    try:
        m = importlib.import_module(mod)
    except Exception:  # noqa: BLE001 - a module that does not import is reported by load_all
        return None
    obj = getattr(m, fn, None)
    return obj if callable(obj) else None


_TRIED: dict[str, str | None] = {}


def load_all(decls: dict | Iterable, *, moves: Moves | None = None) -> list[str]:
    """Import every module the declarations' `code:` keys name, so that their moves register themselves; register
    the named function under the move's name where nothing did. Returns one line per module that could not be
    imported or function that is not there (`derive: enough.thym.moves.emf: No module named ...`); never raises."""
    reg = moves if moves is not None else MOVES
    items = decls.values() if isinstance(decls, dict) else decls
    problems: list[str] = []
    for d in items:
        name, code = decl_get(d, "name"), decl_get(d, "code")
        if not isinstance(code, str) or ":" not in code:
            continue
        mod, _, fn = code.partition(":")
        if mod not in _TRIED:
            try:
                importlib.import_module(mod)
                _TRIED[mod] = None
            except Exception as e:  # noqa: BLE001 - the moves lane's modules may not exist yet
                _TRIED[mod] = f"{type(e).__name__}: {e}"
        if _TRIED[mod] is not None:
            problems.append(f"{name}: {mod}: {_TRIED[mod]}")
            continue
        if name and reg.lookup(name) is None:
            obj = resolve(code)
            if obj is None:
                problems.append(f"{name}: {code}: no such function")
            else:
                reg.add(name, obj, replace=False)
    return problems


def read_declarations(dirs: list[Path] | None = None) -> dict[str, dict]:
    """Every move the manifests declare, by name, read straight from their `moves:` blocks and the `*.moves.cosm`
    sidecars (THYM.md 17.6; the manifest's block wins over a sidecar). The runtime's own reader, used when the
    compiler's `declarations.load` is not there; each mapping gains `owner`, the MiniCOSM that declared it."""
    found: dict[str, dict] = {}
    sidecar: dict[str, dict] = {}
    for d in (dirs or [mc.DEFAULT_MANIFEST_DIR]):
        d = Path(d)
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.cosm")):
            try:
                data = mc.yaml_load(mc.read_text(p))
            except Exception:  # noqa: BLE001 - an unreadable manifest declares nothing here; the reader reports it
                continue
            if not isinstance(data, dict) or not isinstance(data.get("moves"), list):
                continue
            is_sidecar = p.name.endswith(".moves.cosm")
            owner = str(data.get("moves-of") or f"{data.get('name')}/{data.get('version')}")
            target = sidecar if is_sidecar else found
            for m in data["moves"]:
                if isinstance(m, dict) and isinstance(m.get("name"), str):
                    target.setdefault(m["name"], {**m, "owner": owner})
    for name, m in sidecar.items():
        found.setdefault(name, m)
    return found


def declarations(registry: Any = None) -> dict:
    """The declarations the runtime resolves moves against: the compiler's (`enough.thym.declarations.load`) when
    it is there, else `read_declarations`."""
    try:
        from enough.thym import declarations as _decls     # the compiler lane's module
        loaded = _decls.load(registry) if registry is not None else _decls.load()
        if isinstance(loaded, dict) and loaded:
            return loaded
    except Exception:  # noqa: BLE001 - absent, or mid-build in the compiler lane: the runtime's own reader stands in
        pass
    return read_declarations()


@dataclass(frozen=True)
class Amount:
    """A `to` modifier's argument: `300 words`, `12 sentences`."""
    n: int
    unit: str

    def to_dict(self) -> dict:
        return {"n": self.n, "unit": self.unit}


@dataclass
class Where:
    """A `where` modifier's condition, ready to use: `.text` as written, `.test(item)`, `.select(value)`."""
    text: str
    test: Callable[[Any], bool] = field(repr=False)

    def select(self, value: Any) -> list:
        from enough.thym.values import members
        rows = members(value) or []
        return [r for r in rows if self.test(r)]
