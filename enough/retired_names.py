"""The one table of names a release retired, kept for a release so that what learnt an old name is still understood.

When a route, a tool or a word in a request body is renamed, the old name goes into the table below and is served
by the new name's code for ONE release; nothing documents an old name, and the page calls none. Each entry is removed
one release after it is added (an entry added in 0.7 goes in 0.8). The mechanism stays, emptied, so the next rename
needs only a line:

- `ROUTES`: `(method, old path, new path)`; `server.create_app` serves the old path with the new path's handler.
- `TOOLS`: `{old tool name: new tool name}`; `tools.execute` runs the new name's runner for a call by the old name.
- `WORDS`: `{field: {old word: new word}}`; a handler that reads the field maps the old word to the new one.

Removed in 0.7: the 0.6 fabula renames (`/api/canon/emf`, `/derive`, `/compile`; the tool `emf_derive`; `what: emf`).
"""
from __future__ import annotations

#: `(method, old path, new path)`: the old path is served by the new path's handler.
ROUTES: tuple[tuple[str, str, str], ...] = ()

#: `{old tool name: new tool name}`: a call by the old name runs the new name's runner.
TOOLS: dict[str, str] = {}

#: `{field: {old word: new word}}`: old words a request's fields may still say.
WORDS: dict[str, dict[str, str]] = {}


def tool(name: str) -> str:
    """The name a tool call runs under: the new name for a retired one, else the name as called."""
    return TOOLS.get(name, name)


def word(field: str, value: str) -> str:
    """A request field's value, with a retired word read as its new word."""
    return WORDS.get(field, {}).get(value, value)


__all__ = ["ROUTES", "TOOLS", "WORDS", "tool", "word"]
