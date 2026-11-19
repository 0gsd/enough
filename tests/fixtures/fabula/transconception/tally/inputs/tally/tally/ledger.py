"""The ledger: an append-only log of counts, one JSON object per line.

Nothing in a ledger is ever rewritten. Adding appends an entry; undoing appends the opposite of an earlier entry
and names it. Totals are folded from the whole log each time they are needed.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_NAME = ".tally.jsonl"


class LedgerError(Exception):
    """A ledger that cannot be read or an entry that cannot be made; the message is shown to the user as it is."""


@dataclass(frozen=True)
class Entry:
    at: float                  # seconds since the epoch
    name: str
    delta: int
    undoes: int | None = None  # the line number (from 1) of the entry this one cancels


def ledger_path(env: dict | None = None) -> Path:
    """$TALLY_FILE when it is set and not empty, else ~/.tally.jsonl."""
    env = os.environ if env is None else env
    given = env.get("TALLY_FILE", "").strip()
    return Path(given).expanduser() if given else Path.home() / DEFAULT_NAME


def read(path: Path) -> list[Entry]:
    """Every entry, in the order written. A missing file is an empty ledger; blank lines are skipped."""
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append(Entry(float(d["at"]), str(d["name"]), int(d["delta"]), d.get("undoes")))
        except (ValueError, KeyError, TypeError) as e:
            raise LedgerError(f"{path}: line {n} is not a tally entry") from e
    return out


def _append(path: Path, entry: Entry) -> None:
    record = {"at": entry.at, "name": entry.name, "delta": entry.delta}
    if entry.undoes is not None:
        record["undoes"] = entry.undoes
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def add(path: Path, name: str, delta: int = 1, now: float | None = None) -> Entry:
    """Append one count. A name is one word; a delta may be negative but never 0."""
    name = name.strip()
    if not name or any(c.isspace() for c in name):
        raise LedgerError("a name is one word, with no spaces")
    if delta == 0:
        raise LedgerError("adding 0 changes nothing")
    entry = Entry(time.time() if now is None else now, name, delta)
    _append(path, entry)
    return entry


def undo(path: Path, now: float | None = None) -> Entry | None:
    """Cancel the latest entry that is neither an undo nor already undone, by appending its opposite.
    None when there is nothing left to undo."""
    entries = read(path)
    cancelled = {e.undoes for e in entries if e.undoes is not None}
    for n in range(len(entries), 0, -1):
        e = entries[n - 1]
        if e.undoes is None and n not in cancelled:
            back = Entry(time.time() if now is None else now, e.name, -e.delta, undoes=n)
            _append(path, back)
            return back
    return None


def totals(entries: list[Entry]) -> dict[str, int]:
    """Each name's total, names in alphabetical order."""
    out: dict[str, int] = {}
    for e in entries:
        out[e.name] = out.get(e.name, 0) + e.delta
    return dict(sorted(out.items()))
