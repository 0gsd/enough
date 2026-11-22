"""The ledger: an append-only log of entries, one JSON object per line.

Nothing already written is ever changed or removed. An add appends one
entry; an undo appends the opposite of the entry it cancels. Every total
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
    """TALLY_FILE (stripped, ~ expanded) when set and not blank, else ~/.tally.jsonl."""
    env = os.environ if env is None else env
    raw = env.get("TALLY_FILE", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / DEFAULT_NAME


def read(path: Path) -> list[Entry]:
    """Every entry of a ledger, in the order written; [] when it does not exist."""
    if not path.exists():
        return []
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            undoes = obj.get("undoes")
            entries.append(Entry(float(obj["at"]), str(obj["name"]), int(obj["delta"]),
                                 None if undoes is None else int(undoes)))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise LedgerError(f"{path}: line {number} is not a tally entry") from error
    return entries


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
    entry = Entry(time.time() if now is None else now, name, delta)
    _append(path, entry)
    return entry


def undo(path: Path, now: float | None = None) -> Entry | None:
    """Cancel the latest entry that can be cancelled, by appending its opposite."""
    entries = read(path)
    named = {e.undoes for e in entries if e.undoes is not None}
    for place in range(len(entries), 0, -1):
        e = entries[place - 1]
        if e.undoes is None and place not in named:
            entry = Entry(time.time() if now is None else now, e.name, -e.delta, undoes=place)
            _append(path, entry)
            return entry
    return None


def totals(entries: list[Entry]) -> dict[str, int]:
    """Each name's total (totals of 0 included), names in code-point order."""
    out: dict[str, int] = {}
    for e in entries:
        out[e.name] = out.get(e.name, 0) + e.delta
    return dict(sorted(out.items()))
