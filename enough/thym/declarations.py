"""The moves the registry declares: every manifest's `moves:` block and every `*.moves.cosm` sidecar (THYM.md 6.4,
17.6).

The compiler hard-codes no move. It reads the `moves:` list of each manifest in a `macrocosm.Registry` (the bundled
one by default), and each sidecar `<name>.moves.cosm` in the registry's folders, a mapping `{moves-of:
<minicosm>/<major>, moves: [...]}` for a MiniCOSM whose manifest enough never edits (Comprise's). When a manifest
and a sidecar both declare moves for one MiniCOSM, the manifest's list wins and the sidecar is reported. A move name
declared twice across the registry is reported too, and the first declaration, in registry order, wins.

`load` never raises for a bad declaration: what it cannot read goes into the result's `problems` list and is left
out, as the reader treats a bad manifest.

**Two views** (THYM 4.9, 17.6). An entry may say `since: 1`, and then only `thym 1` programs see the move; and it may
carry a `thym-1:` mapping of the keys a `thym 1` program sees in place of its own (`takes`, `gives`, `modifiers`,
`contract`, `scaffold`). `load` gives each declaration as written (its own keys, `since` and `thym-1` kept beside
them); `MoveDecl.view(version)` and `Declarations.view(version)` give what a program of that version sees: a
`thym 0` program sees each entry without its `thym-1:` mapping and no entry that says `since: 1`, its view frozen; a
`thym 1` program sees every entry whole, its `thym-1:` keys in place of its own. `view_of` does the same for a
declaration written as a mapping (the runtime's own reader's).
"""
from __future__ import annotations

import dataclasses
import functools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from enough import macrocosm as mc

from . import types as ty

SIDECAR_GLOB = "*.moves.cosm"
_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_MOVES_OF = re.compile(r"^([a-z][a-z0-9-]*)/([0-9]+)$")
#: The keys a `thym-1:` mapping may hold in this compiler, by the `MoveDecl` field each replaces (THYM 17.6). The
#: table's other keys (`gives-when`, `contract-when`, `scaffold-when`) are read by a later part of the compiler.
THYM1_KEYS = {"takes": "takes", "gives": "gives", "modifiers": "modifiers", "contract": "contract",
              "scaffold": "scaffold"}
#: The grammar versions a declaration may name in `since` (the versions this compiler reads, THYM 4.9).
VERSIONS = (0, 1)


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
    #: the first grammar version that sees the move (`since:`, THYM 4.9); 0 when the entry does not say
    since: int = 0
    #: the `thym-1:` mapping, read into the fields it replaces (`THYM1_KEYS`); empty when the entry has none
    thym1: dict = field(default_factory=dict, hash=False, compare=False)
    #: which view this is: None for the entry as written, else the grammar version it was viewed for
    version: int | None = field(default=None, hash=False, compare=False)

    def view(self, version: int) -> "MoveDecl | None":
        """What a program of grammar `version` sees of this move: None when the move is not there for it (`since`
        names a later version); for `thym 0` the entry without its `thym-1:` mapping; for `thym 1` the entry whole,
        each `thym-1:` key in place of its own. Taken of a view, it is taken of the entry as written."""
        base = self.base
        if base is not self:
            return base.view(version)
        if self.since > version:
            return None
        if version < 1:
            out = dataclasses.replace(self, version=version)
        else:
            out = dataclasses.replace(self, **self.thym1, version=version)
        object.__setattr__(out, "_base", self)
        return out

    @property
    def base(self) -> "MoveDecl":
        """The entry as written, from any view of it (a `thym 1` view replaced its own keys; the entry keeps them)."""
        return self.__dict__.get("_base", self)

    def frozen_view(self) -> "MoveDecl | None":
        """The `thym 0` view of this move, whichever view this is: what a `thym 0` program sees of it (None when it
        is not there for one)."""
        return self.base.view(0)


def view_of(decl: Any, version: int) -> Any:
    """A declaration as a program of grammar `version` sees it, whatever form it comes in: a `MoveDecl` by its
    `view`; a mapping (the runtime's own reader's) by its `since` and `thym-1` keys; anything else as it is. None
    when the move is not there for that version."""
    if isinstance(decl, MoveDecl):
        return decl.view(version)
    if isinstance(decl, dict):
        since = decl.get("since")
        if isinstance(since, int) and not isinstance(since, bool) and since > version:
            return None
        over = decl.get("thym-1") if isinstance(decl.get("thym-1"), dict) else {}
        out = {k: v for k, v in decl.items() if k != "thym-1"}
        if version >= 1:
            out.update({k: v for k, v in over.items() if k in THYM1_KEYS})
        return out
    return decl


class Declarations(dict):
    """The declared moves by name, in registry order, with the `problems` met while reading them."""

    def __init__(self, *args, problems: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.problems: list[str] = list(problems or [])

    def copy(self) -> "Declarations":
        return Declarations(self, problems=self.problems)

    def view(self, version: int) -> "Declarations":
        """The moves a program of grammar `version` sees (THYM 4.9), each in its view for that version."""
        return views(self, version)


def views(decls: dict, version: int) -> "Declarations":
    """`decls` as a program of grammar `version` sees them: each declaration's view (`view_of`), and none that is
    not there for that version. The `problems` of a `Declarations` are kept."""
    out = Declarations(problems=getattr(decls, "problems", None))
    for name, d in decls.items():
        v = view_of(d, version)
        if v is not None:
            out[name] = v
    return out


def _signature(entry: dict, keys, what: str, problems: list[str]) -> dict | None:
    """The signature keys of an entry (or of its `thym-1:` mapping) that are present among `keys`, read into
    `MoveDecl` fields; None, with the problem, when one is malformed."""
    out: dict = {}
    if "takes" in keys:
        takes = entry.get("takes", [])
        if not isinstance(takes, list) or not all(isinstance(t, str) for t in takes):
            problems.append(f"{what}: takes must be a list of type strings")
            return None
        out["takes"] = tuple(tuple(ty.alternatives(t)) for t in takes)
    if "gives" in keys:
        gives = entry.get("gives")
        if not isinstance(gives, str) or not gives.strip():
            problems.append(f"{what}: gives must name a type")
            return None
        out["gives"] = tuple(ty.alternatives(gives))
    if "modifiers" in keys:
        mods = entry.get("modifiers") or {}
        if not isinstance(mods, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mods.items()):
            problems.append(f"{what}: modifiers must map each word to a type string")
            return None
        out["modifiers"] = {str(k): tuple(ty.alternatives(v)) for k, v in mods.items()}
    if "contract" in keys:
        contract = entry.get("contract") or []
        if not isinstance(contract, list) or not all(isinstance(c, str) for c in contract):
            problems.append(f"{what}: contract must be a list of check names")
            return None
        out["contract"] = tuple(contract)
    if "scaffold" in keys:
        sc = entry.get("scaffold")
        out["scaffold"] = sc if isinstance(sc, str) else None
    return out


def _decl(owner: str, entry, source: str, problems: list[str]) -> MoveDecl | None:
    where = f"{Path(source).name}"
    if not isinstance(entry, dict):
        problems.append(f"{where}: a moves: entry is not a mapping: {entry!r}")
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        problems.append(f"{where}: a move's name must be a lowercase name, not {name!r}")
        return None
    sig = _signature(entry, ("takes", "gives", "modifiers", "contract", "scaffold"), f"{where}: move {name}",
                     problems)
    if sig is None:
        return None
    asks = entry.get("asks", False)
    if asks not in (None, True, False):
        problems.append(f"{where}: move {name}: asks must be true or false")
        return None
    since = entry.get("since", 0)
    if since is None:
        since = 0
    if isinstance(since, bool) or not isinstance(since, int) or since not in VERSIONS:
        problems.append(f"{where}: move {name}: since names a grammar version, "
                        f"{' or '.join(map(str, VERSIONS))}, not {since!r}")
        return None
    thym1: dict = {}
    over = entry.get("thym-1")
    if over is not None:
        if not isinstance(over, dict):
            problems.append(f"{where}: move {name}: thym-1 must be a mapping of the keys a thym 1 program sees")
            return None
        read = _signature(over, [k for k in THYM1_KEYS if k in over], f"{where}: move {name}: thym-1", problems)
        if read is None:
            return None
        thym1 = {THYM1_KEYS[k]: v for k, v in read.items()}
    return MoveDecl(
        name=name, owner=owner,
        takes=sig["takes"], gives=sig["gives"], modifiers=sig["modifiers"],
        asks=bool(asks), contract=sig["contract"], scaffold=sig["scaffold"],
        code=entry.get("code") if isinstance(entry.get("code"), str) else None,
        says=str(entry.get("says") or ""), source=source, since=since, thym1=thym1)


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


def names(registry: mc.Registry | None = None, *, version: int | None = None) -> frozenset[str]:
    """The declared move names: what the parser needs to read a call (THYM.md 4.5). With `version`, only the moves a
    program of that grammar version sees (THYM 4.9)."""
    found = load(registry)
    return frozenset(found if version is None else found.view(version))
