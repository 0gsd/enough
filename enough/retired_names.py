"""The one table of names a release retired, kept for a release so that what learnt an old name is still understood.

When a route, a tool or a word in a request body is renamed, the old name goes into the table below and is served
by the new name's code for ONE release; nothing documents an old name, and the page calls none. Each entry is removed
one release after it is added (an entry added in 0.7 goes in 0.8). The mechanism stays, emptied, so the next rename
needs only a line:

- `ROUTES`: `(method, old path, new path)`; `server.create_app` serves the old path with the new path's handler.
- `TOOLS`: `{old tool name: new tool name}`; `tools.execute` runs the new name's runner for a call by the old name.
- `WORDS`: `{field: {old word: new word}}`; a handler that reads the field maps the old word to the new one.
- `FIELDS`: `{old key: new key}`, for a key itself renamed in a query, a request body or an answer: a handler reads
  the new key through `field()`, which falls back to the old one, and an answer passed through `answer()` carries
  the old key beside the new one.

Removed in 0.7: the 0.6 fabula renames (`/api/canon/emf`, `/derive`, `/compile`; the tool `emf_derive`; `what: emf`).

Added in 0.7, to go in 0.8: the composure kind `board`, now `plane` (a `.comp` that says `composure:kind board` is read
as `plane` and saved back as `plane`; a `set_meta` op may still say `board`), so that "board" is free for Thymop's
governing body. The Canon routes' `box` (query and body, a transfer's `src`/`dst` included) and the tree's
`cacheboxes`, now `volume` and `volumes`: a request may still say `box`, and the tree, an ingest's answer and a
transfer's answer still carry the old keys beside the new.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: `(method, old path, new path)`: the old path is served by the new path's handler.
ROUTES: tuple[tuple[str, str, str], ...] = ()

#: `{old tool name: new tool name}`: a call by the old name runs the new name's runner.
TOOLS: dict[str, str] = {}

#: `{field: {old word: new word}}`: old words a request's fields may still say.
WORDS: dict[str, dict[str, str]] = {
    "kind": {"board": "plane"},      # composure:kind, in a .comp and in a set_meta op (0.7)
}

#: `{old key: new key}`: keys a request may still send, and an answer still carries, under their old name.
FIELDS: dict[str, str] = {
    "box": "volume",                 # the Canon routes' query, body, src/dst and answers (0.7)
    "cacheboxes": "volumes",         # GET /api/canon/tree (0.7)
}


def tool(name: str) -> str:
    """The name a tool call runs under: the new name for a retired one, else the name as called."""
    return TOOLS.get(name, name)


def word(field: str, value: str) -> str:
    """A request field's value, with a retired word read as its new word."""
    return WORDS.get(field, {}).get(value, value)


def field(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """A request's value under `key`, else under a retired key that `FIELDS` maps to it, else `default`."""
    if key in data:
        return data[key]
    for old, new in FIELDS.items():
        if new == key and old in data:
            return data[old]
    return default


def answer(data: dict[str, Any]) -> dict[str, Any]:
    """`data` with each retired key beside the new key it maps to, for what still reads the old name. In place."""
    for old, new in FIELDS.items():
        if new in data and old not in data:
            data[old] = data[new]
    return data


__all__ = ["FIELDS", "ROUTES", "TOOLS", "WORDS", "answer", "field", "tool", "word"]
