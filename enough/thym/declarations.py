"""The moves the registry declares: every manifest's `moves:` block and every `*.moves.cosm` sidecar (THYM.md 6.4,
17.6).

The compiler hard-codes no move. It reads the `moves:` list of each manifest in a `macrocosm.Registry` (the bundled
one by default), and each sidecar `<name>.moves.cosm` in the registry's folders, a mapping `{moves-of:
<minicosm>/<major>, moves: [...]}` for a MiniCOSM whose manifest enough never edits (Comprise's). When a manifest
and a sidecar both declare moves for one MiniCOSM, the manifest's list wins and the sidecar is reported. A move name
declared twice across the registry is reported too, and the first declaration, in registry order, wins.

`load` never raises for a bad declaration: what it cannot read goes into the result's `problems` list and is left
out, as the reader treats a bad manifest.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

from enough import macrocosm as mc

from . import types as ty

SIDECAR_GLOB = "*.moves.cosm"
_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_MOVES_OF = re.compile(r"^([a-z][a-z0-9-]*)/([0-9]+)$")


@dataclass(frozen=True)
class MoveDecl:
    """One declared move. `takes` holds each operand's alternatives in order (empty when the move's argument is its
    `of`); `gives` the alternatives of what it gives (one, except for a move that gives the same as it takes);
    `modifiers` maps each modifier word to its alternatives, in the declared order (the order a call writes them);
    `contract` the names of its checks (THYM.md 7.3). `source` is the file that declared it."""
    name: str
    owner: str
    takes: tuple[tuple[str, ...], ...]
    gives: tuple[str, ...]
    modifiers: dict[str, tuple[str, ...]] = field(hash=False)
    asks: bool = False
    contract: tuple[str, ...] = ()
    scaffold: str | None = None
    code: str | None = None
    says: str = ""
    source: str | None = None


class Declarations(dict):
    """The declared moves by name, in registry order, with the `problems` met while reading them."""

    def __init__(self, *args, problems: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.problems: list[str] = list(problems or [])

    def copy(self) -> "Declarations":
        return Declarations(self, problems=self.problems)


def _decl(owner: str, entry, source: str, problems: list[str]) -> MoveDecl | None:
    where = f"{Path(source).name}"
    if not isinstance(entry, dict):
        problems.append(f"{where}: a moves: entry is not a mapping: {entry!r}")
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        problems.append(f"{where}: a move's name must be a lowercase name, not {name!r}")
        return None
    takes = entry.get("takes", [])
    if not isinstance(takes, list) or not all(isinstance(t, str) for t in takes):
        problems.append(f"{where}: move {name}: takes must be a list of type strings")
        return None
    gives = entry.get("gives")
    if not isinstance(gives, str) or not gives.strip():
        problems.append(f"{where}: move {name}: gives must name a type")
        return None
    mods = entry.get("modifiers") or {}
    if not isinstance(mods, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mods.items()):
        problems.append(f"{where}: move {name}: modifiers must map each word to a type string")
        return None
    contract = entry.get("contract") or []
    if not isinstance(contract, list) or not all(isinstance(c, str) for c in contract):
        problems.append(f"{where}: move {name}: contract must be a list of check names")
        return None
    asks = entry.get("asks", False)
    if asks not in (None, True, False):
        problems.append(f"{where}: move {name}: asks must be true or false")
        return None
    return MoveDecl(
        name=name, owner=owner,
        takes=tuple(tuple(ty.alternatives(t)) for t in takes),
        gives=tuple(ty.alternatives(gives)),
        modifiers={str(k): tuple(ty.alternatives(v)) for k, v in mods.items()},
        asks=bool(asks), contract=tuple(contract),
        scaffold=entry.get("scaffold") if isinstance(entry.get("scaffold"), str) else None,
        code=entry.get("code") if isinstance(entry.get("code"), str) else None,
        says=str(entry.get("says") or ""), source=source)


def _sidecars(reg: mc.Registry, problems: list[str]) -> list[tuple[str, str, list]]:
    """(owner, path, moves) for every readable sidecar in the registry's folders."""
    out: list[tuple[str, str, list]] = []
    for d in reg.dirs:
        try:
            paths = sorted(Path(d).glob(SIDECAR_GLOB)) if Path(d).is_dir() else []
        except OSError as e:
            problems.append(f"{d}: cannot read: {e}")
            continue
        for p in paths:
            try:
                data = mc.yaml_load(mc.read_text(p))
            except Exception as e:                       # noqa: BLE001  (a bad sidecar is a problem, never a crash)
                problems.append(f"{p.name}: cannot read: {e}")
                continue
            if not isinstance(data, dict):
                problems.append(f"{p.name}: a sidecar's top level is a mapping")
                continue
            mt = _MOVES_OF.match(str(data.get("moves-of") or ""))
            if not mt:
                problems.append(f"{p.name}: moves-of must name <minicosm>/<major>, not {data.get('moves-of')!r}")
                continue
            moves = data.get("moves")
            if not isinstance(moves, list):
                problems.append(f"{p.name}: moves must be a list")
                continue
            out.append((mt.group(1), str(p), moves))
    return out


def _load(reg: mc.Registry) -> Declarations:
    problems: list[str] = []
    blocks: dict[str, tuple[str, list]] = {}
    for m in reg.manifests.values():
        moves = m.data.get("moves")
        if moves is None:
            continue
        if not isinstance(moves, list):
            problems.append(f"{m.path.name if m.path else m.name}: moves must be a list")
            continue
        blocks[m.name] = (str(m.path) if m.path else m.name, moves)
    from_sidecar: set[str] = set()
    for owner, path, moves in _sidecars(reg, problems):
        if owner in blocks:
            if owner in from_sidecar:                    # the first sidecar for a MiniCOSM wins, in the folders' order
                problems.append(f"{Path(path).name}: an earlier sidecar for {owner} ({blocks[owner][0]}) is read; "
                                "this sidecar is not read")
            else:
                problems.append(f"{Path(path).name}: {owner}'s manifest declares its own moves, which win; "
                                "this sidecar is not read")
            continue
        from_sidecar.add(owner)
        if owner not in reg.manifests:
            problems.append(f"{Path(path).name}: a sidecar for {owner}, which the registry does not know; "
                            "its moves are read")
        blocks[owner] = (path, moves)
    order = [n for n in reg.manifests if n in blocks] + sorted(n for n in blocks if n not in reg.manifests)
    out = Declarations()
    for owner in order:
        path, moves = blocks[owner]
        for entry in moves:
            d = _decl(owner, entry, path, problems)
            if d is None:
                continue
            if d.name in out:
                problems.append(f"{Path(path).name}: move {d.name} is declared again; the first, by "
                                f"{out[d.name].owner}, is kept")
                continue
            out[d.name] = d
    out.problems = problems
    return out


@functools.lru_cache(maxsize=1)
def _default() -> Declarations:
    return _load(mc.default_registry())


def load(registry: mc.Registry | None = None) -> Declarations:
    """Every move the registry declares, by name (the bundled registry when none is given; read once per process
    then). The result is a dict of `MoveDecl` with a `problems` list."""
    if registry is None:
        return _default().copy()
    return _load(registry)


def names(registry: mc.Registry | None = None) -> frozenset[str]:
    """The declared move names: what the parser needs to read a call (THYM.md 4.5)."""
    return frozenset(load(registry))
