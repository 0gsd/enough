"""The ledger: an append-only log of entries, one JSON object per line.

No line already written is ever changed or removed. An add appends one
line; an undo appends the opposite of the entry it cancels. Every total
is folded from the whole log when it is needed.
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_NAME = ".tally.jsonl"


class LedgerError(Exception):
    """The one error tally raises on purpose; its message is shown as it is."""


@dataclass(frozen=True)
class Entry:
    at: float
    name: str
    delta: int
    undoes: int | None = None


def ledger_path(env: dict | None = None) -> Path:
    """The ledger's path: TALLY_FILE when set and not blank, else ~/.tally.jsonl."""
    env = os.environ if env is None else env
    value = (env.get("TALLY_FILE") or "").strip()
    if value:
        return Path(value).expanduser()
    return Path.home() / DEFAULT_NAME


def _read_numbered(path: Path) -> list[tuple[int, Entry]]:
    """Every entry with its line number (from 1, blank lines counted)."""
    if not path.exists():
        return []
    numbered = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            undoes = obj.get("undoes")
            entry = Entry(
                at=float(obj["at"]),
                name=str(obj["name"]),
                delta=int(obj["delta"]),
                undoes=None if undoes is None else int(undoes),
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LedgerError(f"{path}: line {n} is not a tally entry") from exc
        numbered.append((n, entry))
    return numbered


def read(path: Path) -> list[Entry]:
    """Every entry of a ledger, in the order written; [] when it does not exist."""
    return [entry for _, entry in _read_numbered(path)]


def _append(path: Path, entry: Entry) -> None:
    record = {"at": entry.at, "delta": entry.delta, "name": entry.name}
    if entry.undoes is not None:
        record["undoes"] = entry.undoes
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def add(path: Path, name: str, delta: int = 1, now: float | None = None) -> Entry:
    """Append one count to the ledger and return the entry written."""
    name = name.strip()
    if not name or any(c.isspace() for c in name):
        raise LedgerError("a name is one word, with no spaces")
    if delta == 0:
        raise LedgerError("adding 0 changes nothing")
    entry = Entry(at=time.time() if now is None else float(now), name=name, delta=delta)
    _append(path, entry)
    return entry


def undo(path: Path, now: float | None = None) -> Entry | None:
    """Cancel the latest entry that can be cancelled, by appending its opposite."""
    numbered = _read_numbered(path)
    undone = {e.undoes for _, e in numbered if e.undoes is not None}
    for n, e in reversed(numbered):
        if e.undoes is None and n not in undone:
            entry = Entry(
                at=time.time() if now is None else float(now),
                name=e.name,
                delta=-e.delta,
                undoes=n,
            )
            _append(path, entry)
            return entry
    return None


def totals(entries: list[Entry]) -> dict[str, int]:
    """Each name's total, totals of 0 included, names in code-point order."""
    sums: dict[str, int] = {}
    for e in entries:
        sums[e.name] = sums.get(e.name, 0) + e.delta
    return dict(sorted(sums.items()))
