"""The names retired in 0.6 that still answer, in one table (the conductor's ruling: EMF's name is retired).

The routes and the tools the app documents, and the page will call, are named for the fabula. Each old route path and
each old tool name below still dispatches to exactly the same code through 0.6, so the page keeps working until its
own lane moves it, and an agent that learnt an old name is still understood. Nothing documents an old name.

THIS TABLE GOES A RELEASE LATER (0.7): delete it, the loop in `server.create_app` that reads `ROUTES`, and the
lookup in `tools.execute` that reads `TOOLS`.
"""
from __future__ import annotations

#: `(method, old path, new path)`: the old path is served by the new path's handler.
ROUTES: tuple[tuple[str, str, str], ...] = (
    ("GET", "/api/canon/emf", "/api/fabula/twin"),
    ("POST", "/api/canon/derive", "/api/fabula/derive"),
    ("POST", "/api/canon/compile", "/api/fabula/compile"),
)

#: `{old tool name: new tool name}`: a call by the old name runs the new name's runner.
TOOLS: dict[str, str] = {
    "emf_derive": "fabula_derive",
}

#: Old words a request's fields may still say: `what: emf` on the derive route means `what: fabula`.
WORDS: dict[str, dict[str, str]] = {
    "what": {"emf": "fabula"},
}


def tool(name: str) -> str:
    """The name a tool call runs under: the new name for a retired one, else the name as called."""
    return TOOLS.get(name, name)


__all__ = ["ROUTES", "TOOLS", "WORDS", "tool"]
