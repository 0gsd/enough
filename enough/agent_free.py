"""Agent-free mode (0.4.4, docs/docoes-044-plan.md §13).

Everything enough has done until now is **free-agent mode**. One machine-global
switch, `agent_free` in `~/enough/config/ui.json` (beside the theme, the UI
language and the chief readvisor's name), turns on **agent-free mode**: no model
at all. The supervisor never starts llama-server, every route that would talk to
a model answers 409, the derivations (decompile / atem / compile) take their
rules path, and the context preflight never runs. Install is unchanged and the
switch defaults to off: an absent key, an unreadable file and anything but a
literal `true` all read as off.

This module is the one reader of the switch. It is stdlib only and imports
nothing from enough, so `llm`, `cloud`, `supervisor`, `preflight`, `tools` and
`server` can all ask it without an import cycle; the write side is
`POST /api/ui-config`, which also stops or starts the model.

Read on every ask, not once at import: the switch can flip while the server
runs. A stat per ask keeps that cheap — the file is parsed again only when its
mtime or size moved.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

#: The ui.json key.
KEY = "agent_free"
#: The machine-readable reason every refusal and every rules-mode job carries
#: (`reason` on a canon job, `mode` on `/api/llm-status` and the supervisor).
REASON = "agent-free"

_lock = threading.Lock()
_cache: tuple[tuple[str, int, int] | None, bool] = (None, False)


def ui_config_path() -> Path:
    """Live `ui.json`, honoring `ENOUGH_UI_CONFIG`.

    A third copy of `server._ui_config_live_path()` (after `prompt.
    _ui_config_path()`), for the reason `prompt` gives: the layers that ask
    this must stay importable without the web layer, and six lines of path
    logic are a cheaper dependency than FastAPI."""
    raw = os.environ.get("ENOUGH_UI_CONFIG")
    if raw and raw.strip():
        return Path(raw).expanduser()
    return Path.home() / "enough" / "config" / "ui.json"


def value(cfg: object) -> bool:
    """The switch as a parsed ui.json holds it: on only for a literal `true`."""
    return isinstance(cfg, dict) and cfg.get(KEY) is True


def enabled() -> bool:
    """Is agent-free mode on? Off whenever the file cannot say otherwise."""
    global _cache
    path = ui_config_path()
    try:
        st = path.stat()
    except OSError:
        return False
    sig = (str(path), st.st_mtime_ns, st.st_size)
    with _lock:
        if _cache[0] == sig:
            return _cache[1]
    try:
        on = value(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        on = False
    with _lock:
        _cache = (sig, on)
    return on


def detail(what: str = "") -> str:
    """The sentence a 409 carries: `agent-free mode: <what> …`."""
    what = what or "this needs a model, and none runs while agent-free is on"
    return f"agent-free mode: {what} — turn agent-free off in ui preferences to use it"
