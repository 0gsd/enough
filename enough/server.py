"""FastAPI app: UI + chat (with SSE streaming) + file-tree + preview.

Architecture
------------

- One `Session` per server process. v0.01 is localhost-only, single-user.
- The browser opens a persistent SSE connection to `/api/stream`. Every chunk
  the model generates — plus tool-call indicators — goes onto a per-session
  event queue, and the SSE coroutine drains it.
- POSTing to `/api/chat` appends a user message to the in-memory history and
  kicks off a generation task. The task streams from llama-server, watches for
  complete `<tool name="...">...</tool>` blocks, executes them, loops.
- Tool iterations are capped at 10 per user turn (per spec).
- System prompt is re-assembled from `rness/` on every user turn (no cache).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import __version__
from . import broker as _broker
from .wikisink import config as _wikisink_config
from .llm import LLMError, stream_chat
from . import cloud as _cloud
from . import models as _models
from .logger import ExchangeLog, log_exchange
from .prompt import (
    assemble_system_prompt,
    get_active_paradigm,
    get_help_bubbles,
    list_paradigms,
    list_roles,
    list_skills,
    set_active_paradigm,
    set_help_bubbles,
    set_role_enabled,
    set_skill_enabled,
)
from .supervisor import LlamaSupervisor
from .tools import (
    ToolCall,
    _read_allowlist,
    _under_any,
    execute,
    first_tool_call_end,
    parse_tool_calls,
)

log = logging.getLogger("enough")

STATIC_DIR = Path(__file__).parent / "static"
INSTALL_ROOT = Path(__file__).resolve().parents[1]
UI_CONFIG_TEMPLATE = INSTALL_ROOT / "defaults" / "ui-config.json"
_DEFAULT_UI_CONFIG_LIVE = Path.home() / "enough" / "config" / "ui.json"


def _ui_config_live_path() -> Path:
    """Live ui.json location, honoring ENOUGH_UI_CONFIG (a test/dev hook,
    mirroring the ENOUGH_WIKISINK_CONFIG / ENOUGH_CACHEAWL_ROOT precedent) so
    suites never touch the real ~/enough/config/ui.json."""
    env = os.environ.get("ENOUGH_UI_CONFIG")
    return Path(env).expanduser() if env else _DEFAULT_UI_CONFIG_LIVE

WHISPER_DIR = Path.home() / "enough" / "weights" / "whisper"
WHISPER_DEFAULT_MODEL = "ggml-base.en.bin"

# --- Desktop shell (enough.app) hooks --------------------------------------
# `POST /api/shutdown` exists only for a server the desktop shell spawned.
# The shell sets ENOUGH_DESKTOP=1 in the child's environment; without it the
# endpoint 404s, so a plain `enough` in a terminal can never be killed by a
# stray POST from some page the user happens to have open. The shell also
# sets a per-launch ENOUGH_DESKTOP_TOKEN and sends it back in a custom
# header — a custom header can't ride along on a cross-origin form POST
# without a CORS preflight this app never answers.
DESKTOP_ENV = "ENOUGH_DESKTOP"
DESKTOP_TOKEN_ENV = "ENOUGH_DESKTOP_TOKEN"
DESKTOP_TOKEN_HEADER = "x-enough-desktop-token"


def request_process_exit(delay: float = 0.25) -> None:
    """Ask this uvicorn process to exit shortly after the current response.

    SIGTERM to ourselves is uvicorn's own graceful-shutdown path: it drains
    connections and runs the lifespan teardown, which is what stops an
    *owned* llama-server and closes the httpx client. The small delay lets
    the shutdown response actually reach the shell first.

    Module-level (rather than inline in the handler) so tests can swap it
    out — the real thing would take the test runner down with it.
    """
    loop = asyncio.get_running_loop()
    loop.call_later(delay, lambda: os.kill(os.getpid(), signal.SIGTERM))


ORCHESTRATOR_CONFIG = Path.home() / "enough" / "config" / "orchestrator.json"
# Defaults are intentionally conservative: auto-reset off until the user
# opts in. Threshold sits below the wall (max ~85%) to give the
# checkpoint write itself enough headroom to complete.
ORCHESTRATOR_DEFAULTS = {"auto_reset": False, "threshold_pct": 75}

IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".llama-server",
}

# Paths hidden from the file-tree sidebar. The files themselves still
# exist and the agent can read/write them normally — this is purely a
# tree-rendering filter to keep the sidebar focused on user content.
HIDDEN_TREE_PATHS: frozenset[str] = frozenset({
    # Surfaced via dedicated sidebar sections at the top (paradigm
    # picker, skills toggle, roles toggle) — hidden here to avoid
    # duplicating UI affordances.
    "rness/paradigms",
    "rness/roles",
    "rness/skills",
    # Internal machinery the user shouldn't need to touch directly: the
    # launcher shortcut, the active-paradigm pointer (set via the
    # paradigm picker), and the project metadata (name + description,
    # edited via the project title/description UI).
    "enough-on.command",
    "rness/active-paradigm",
    "rness/project.json",
})
DEFAULT_MAX_TOOL_ITERS = 50

# How long we'll wait between streamed tokens before assuming llama-server
# has wedged. Long enough to ride out big-prefill pauses on slow hardware,
# short enough that a stuck process surfaces instead of leaving the UI
# spinning forever. Hit the limit and the user gets a real error message,
# not silence.
LLM_STREAM_INACTIVITY_TIMEOUT = 180.0


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class Session:
    project_dir: Path
    llm_url: str
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS
    history: list[dict[str, str]] = field(default_factory=list)  # OpenAI format
    # One queue per connected EventSource. A single shared queue would cause
    # zombie connections (e.g. after a page reload before the server notices)
    # to race living ones and steal events. Per-subscriber fan-out avoids
    # that at the cost of N*payload-size memory — negligible for v0.02.
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    generation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    client: httpx.AsyncClient | None = None
    # Most recent llama-server usage report. Populated after every
    # stream_chat call; powers the token-pressure gauge in the UI.
    # Keys: prompt_tokens, completion_tokens, total_tokens, ctx (snapshot
    # of the live ctx-size at the time the usage was recorded).
    last_usage: dict[str, int] = field(default_factory=dict)
    supervisor: Any = None  # LlamaSupervisor; stays Any to avoid forward-ref churn

    async def emit(self, event: str, data: Any) -> None:
        payload = {"event": event, "data": json.dumps(data)}
        for q in list(self.subscribers):  # snapshot — subscribers may unregister mid-iter
            await q.put(payload)


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------

def _wikisink_storage_real() -> frozenset[Path]:
    """Resolved wikisink dirs — the data dir plus every registered
    install's storage dir. Archives and sidecar stores (overlay,
    comments, preserved, …) must never render in the file tree — only
    articles explicitly saved into a project's wiki/ (or the global wiki
    cachebox) are user-visible files. Resolved fresh per tree build: cheap (one
    tiny JSON read) and always honors just-changed locations."""
    cfg = _wikisink_config.load_config()
    dirs = [_wikisink_config.data_dir(cfg)]
    dirs += [Path(i.get("storage_dir") or "").expanduser()
             for i in _wikisink_config.installs(cfg)]
    out = set()
    for d in dirs:
        try:
            if d != Path(".") and d.exists():
                out.add(d.resolve())
        except OSError:
            continue
    return frozenset(out)


def _walk_tree(
    root: Path,
    rel_parts: tuple[str, ...],
    visited: frozenset[Path],
    wikisink_real: frozenset[Path] = frozenset(),
) -> list[dict[str, Any]]:
    """Walk the project tree to arbitrary depth, with symlink-cycle protection.

    `visited` carries the set of canonical paths already in the current
    recursion chain. We snapshot it as we descend so sibling branches stay
    independent — if two in-tree symlinks (e.g. under `rness/skills/`) both
    happen to point into `~/enough/`, walking one doesn't poison the other."""
    abs_dir = root.joinpath(*rel_parts)
    try:
        real = abs_dir.resolve()
    except OSError:
        return []
    if real in visited:
        return []
    visited = visited | {real}
    try:
        entries = sorted(abs_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for p in entries:
        if p.name.startswith("."):
            continue
        if p.name in IGNORE_DIRS:
            continue
        rel = "/".join(rel_parts + (p.name,))
        if rel in HIDDEN_TREE_PATHS:
            continue
        if wikisink_real and p.is_dir():
            try:
                if p.resolve() in wikisink_real:
                    continue
            except OSError:
                pass
        node = {
            "name": p.name,
            "path": rel,
            "is_dir": p.is_dir(),
            "is_symlink": p.is_symlink(),
        }
        if p.is_dir():
            # Saved wikisink articles are folders shaped {article.html,
            # _manifest.md, .meta.json}; the tree marks them so the UI
            # can route clicks into the reader and offer unsave.
            try:
                if (p / "article.html").is_file() and (p / ".meta.json").is_file():
                    node["wiki_saved"] = True
            except OSError:
                pass
            node["children"] = _walk_tree(root, rel_parts + (p.name,), visited, wikisink_real)
        elif p.name == "article.html":
            try:
                if (p.parent / ".meta.json").is_file():
                    node["wiki_article"] = True
            except OSError:
                pass
        out.append(node)
    return out


def _hidden_global_dirs() -> frozenset[Path]:
    """Resolved global dirs that must never render in a project's file tree:
    the wikisink storage/data dirs plus the cacheawl store root. cacheawl is
    a global store (like wikisink) accessed through its own UI/tools, not a
    per-project artifact — hide it the same way, in case a project ever
    symlinks to or sits near it."""
    dirs = set(_wikisink_storage_real())
    try:
        from . import cacheawl as _cacheawl
        r = _cacheawl.root()
        if r.exists():
            dirs.add(r.resolve())
    except OSError:
        pass
    return frozenset(dirs)


def build_file_tree(root: Path) -> list[dict[str, Any]]:
    return _walk_tree(root, (), frozenset(), _hidden_global_dirs())


# Paths in the project tree that get a [?] help affordance on hover.
# IDs match the keys in HELP_DOCS in static/index.html.
_HELP_IDS: dict[str, str] = {
    "rness": "rness",
    "rness/AGENT.md": "agent-md",
    "rness/MOTIVATION.md": "motivation-md",
    "rness/policies": "policies",
    "rness/knowledge": "knowledge",
    "rness/requests": "requests",
    "rness/io": "io",
    "wiki": "project-wiki",
}


def _tree_to_html(nodes: list[dict[str, Any]]) -> str:
    out = ['<ul class="tree">']
    for n in nodes:
        path = n["path"].replace('"', "&quot;")
        name_attr = n["name"].replace('"', "&quot;")
        sym_cls = " symlink" if n.get("is_symlink") else ""
        help_id = _HELP_IDS.get(n["path"])
        help_attr = f' data-help="{help_id}"' if help_id else ""
        # `data-path` + `data-name` on the row's <li> are read by the
        # tree context menu (option-click) so the JS can identify the
        # target without parsing the inner DOM. Folder rows already
        # need `data-path` for other reasons; file rows pick it up here.
        if n["is_dir"]:
            has_kids = bool(n.get("children"))
            dir_state_cls = " has-children" if has_kids else " empty-folder"
            saved_attr = ' data-wiki-saved="1"' if n.get("wiki_saved") else ""
            # Zippy glyph: ▾ (expanded, default) if has children; nothing if empty.
            zippy = '<span class="zippy">▾</span>' if has_kids else '<span class="zippy-spacer"></span>'
            out.append(
                f'<li class="dir{sym_cls}{dir_state_cls}" '
                f'data-path="{path}" data-name="{name_attr}" data-kind="dir"{saved_attr}>'
                f'<span class="dir-row"{help_attr}>{zippy}<span class="dir-name">{n["name"]}/</span></span>'
            )
            if has_kids:
                out.append(_tree_to_html(n["children"]))
            out.append("</li>")
        elif n.get("wiki_article"):
            # Saved article: opens in the wikisink reader, not the file
            # preview — the HTML is a verbatim archive copy, not a doc
            # to edit.
            out.append(
                f'<li class="file{sym_cls}" '
                f'data-path="{path}" data-name="{name_attr}" data-kind="file">'
                f'<span class="file-row"><span class="zippy-spacer"></span>'
                f'<a href="#" data-wiki-article="{path}" '
                f'onclick="openSavedWikiArticle(\'{path}\'); return false;"'
                f'>{n["name"]}</a></span></li>'
            )
        else:
            out.append(
                f'<li class="file{sym_cls}" '
                f'data-path="{path}" data-name="{name_attr}" data-kind="file">'
                f'<span class="file-row"{help_attr}><span class="zippy-spacer"></span>'
                f'<a href="#" '
                f'hx-get="/api/file?path={path}" hx-target="#preview-body" '
                f'hx-swap="innerHTML" '
                f'onclick="document.getElementById(\'preview\').classList.add(\'open\')"'
                f'>{n["name"]}</a></span></li>'
            )
    out.append("</ul>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Chat generation
# ---------------------------------------------------------------------------

def _load_orchestrator_config() -> dict[str, Any]:
    """Read the orchestrator config (auto-reset toggle + threshold). Falls
    back to defaults for missing keys; never raises."""
    try:
        cfg = json.loads(ORCHESTRATOR_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = {}
    out = dict(ORCHESTRATOR_DEFAULTS)
    if isinstance(cfg, dict):
        if isinstance(cfg.get("auto_reset"), bool):
            out["auto_reset"] = cfg["auto_reset"]
        # Clamp threshold to a sane range so a typo can't make the gauge
        # unreachable (1) or fire trivially (0).
        try:
            t = int(cfg.get("threshold_pct", out["threshold_pct"]))
            out["threshold_pct"] = max(40, min(95, t))
        except (TypeError, ValueError):
            pass
    return out


def _save_orchestrator_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Persist a sanitized orchestrator config and return the saved view."""
    current = _load_orchestrator_config()
    if "auto_reset" in cfg and isinstance(cfg["auto_reset"], bool):
        current["auto_reset"] = cfg["auto_reset"]
    if "threshold_pct" in cfg:
        try:
            current["threshold_pct"] = max(40, min(95, int(cfg["threshold_pct"])))
        except (TypeError, ValueError):
            pass
    ORCHESTRATOR_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ORCHESTRATOR_CONFIG.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def _estimate_total_tokens(session: "Session", system_prompt: str) -> int:
    """Char-based token estimate, used when llama-server didn't ship a
    `usage` payload on the stream (older llama.cpp builds, pre-stream
    errors, etc.). Conservative ratio (~3 chars/token, slightly under
    the typical English norm) so we err toward triggering auto-reset
    earlier rather than later — better to pause one turn early than to
    overflow the context window mid-job."""
    chars = len(system_prompt or "")
    for msg in session.history:
        chars += len(msg.get("content", "") or "")
    return chars // 3


def _pressure_pct(session: "Session", system_prompt: str) -> int:
    """Best-effort context-window pressure as an integer percentage.
    Prefers the most recent llama-server usage report; falls back to
    `_estimate_total_tokens` when usage data isn't available. Returns 0
    if we can't even determine the ctx-size (e.g. external llama-server
    in --no-supervise mode where current_ctx is None)."""
    ctx = _current_ctx_size(session) or session.last_usage.get("ctx")
    if not ctx:
        return 0
    total = session.last_usage.get("total_tokens") or 0
    if not total:
        total = _estimate_total_tokens(session, system_prompt)
    return min(100, int((total / ctx) * 100))


def _should_auto_reset(session: "Session", system_prompt: str) -> bool:
    """Decide whether to fire auto-reset based on live config + current
    pressure. Pressure prefers real usage but falls back to a char-count
    estimate so that older llama.cpp builds (which may not ship `usage`
    on the stream) don't silently disable the safety net."""
    cfg = _load_orchestrator_config()
    if not cfg["auto_reset"]:
        return False
    return _pressure_pct(session, system_prompt) >= cfg["threshold_pct"]


def _current_ctx_size(session: "Session") -> int | None:
    """Best-effort lookup of llama-server's current ctx-size, used to scale
    the token-pressure gauge. Returns None if we can't determine it (no
    supervisor, server still booting); the gauge then renders absolute
    counts only."""
    sup = session.supervisor
    if sup is None:
        return None
    ctx = getattr(sup, "current_ctx", None)
    return int(ctx) if ctx else None


def _render_turn_from_history(history: list[dict[str, str]]) -> str:
    """Render the saved history as HTML for initial page load."""
    out: list[str] = []
    for msg in history:
        role = msg.get("role")
        text = msg.get("content", "") or ""
        if role == "user":
            # Strip tool_result wrappers for display
            if text.lstrip().startswith("<tool_result"):
                continue
            out.append(f'<div class="msg user"><div class="role">user</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
        elif role == "assistant":
            out.append(f'<div class="msg assistant"><div class="role">agent</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
    return "".join(out)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Empty-hint rendering
# ---------------------------------------------------------------------------
#
# The empty-state pane (shown when the conversation is empty) is the
# right place to surface launch-time information the user actually needs
# to see — e.g. "new defaults are available, type /update-enough to
# apply". Terminal output is too easy to miss; an inline banner that
# tracks server state isn't.
#
# Each branch returns HTML for the contents of `<div id="empty-hint">`.
# The default branch keeps the original italic-faint hint; "notice"
# branches use the `.empty-hint--notice` class for bright, structured
# rendering. Add new branches as new launch states emerge (first-launch
# onboarding, model-not-running advisory, etc.).

_DEFAULT_EMPTY_HINT = (
    '<div class="empty-hint" id="empty-hint">'
    'awaiting your first message.<br>'
    'say hi, or ask me what i can do.'
    '</div>'
)


def _render_empty_hint(project_dir: Path) -> str:
    """Return the HTML for the empty-conversation pane. Picks the most
    salient state-aware notice if any apply; otherwise falls back to the
    default 'awaiting your first message' italic hint."""
    # Cloud-sync root: highest-priority warning. enough's skeleton (symlinks)
    # and launcher (executable bit) don't survive Google Drive / Dropbox /
    # iCloud sync between machines, so flag it up front and let the user
    # decide how to handle it.
    from .skeleton import cloud_sync_provider, detect_drift
    provider = cloud_sync_provider(project_dir)
    if provider:
        return (
            '<div class="empty-hint empty-hint--notice" id="empty-hint">'
            f'<div class="notice-title">heads up — this project is inside '
            f'{_escape_html(provider)}</div>'
            '<ul class="notice-list">'
            '<li>cloud sync can’t preserve the symlinks enough uses for '
            'its <code>rness/</code> skeleton, or the executable bit on '
            '<code>enough-on.command</code>, across machines</li>'
            '<li>enough re-heals broken skeleton links on each launch, but '
            'shared multi-Mac use here is still fragile</li>'
            '</ul>'
            '<div class="notice-cta">'
            'for multi-Mac setups, keep projects on local disk — or use a '
            'plain-file notes app (e.g. Obsidian) for the prose. otherwise, '
            'carry on; this is just a heads up.'
            '</div>'
            '</div>'
        )

    # Drift: ~/enough/defaults/ has shared defaults this rness/ is
    # missing. Surface them prominently with the /update-enough hook.
    missing = detect_drift(project_dir)
    if missing:
        n = len(missing)
        items = "".join(
            f'<li>{_escape_html(dst)}</li>'
            for (_src, dst, _mode) in missing
        )
        return (
            '<div class="empty-hint empty-hint--notice" id="empty-hint">'
            f'<div class="notice-title">'
            f'{n} new default{"s" if n != 1 else ""} '
            f'available from <code>~/enough/defaults/</code>'
            '</div>'
            f'<ul class="notice-list">{items}</ul>'
            '<div class="notice-cta">'
            'type <code>/update-enough</code> in the chat box to apply, '
            'or ignore.'
            '</div>'
            '</div>'
        )

    return _DEFAULT_EMPTY_HINT


# ---------------------------------------------------------------------------
# UI config (themes / fonts / zoom)
# ---------------------------------------------------------------------------

def _load_ui_config_template() -> dict[str, Any]:
    """Fallback config for when neither the live file nor the shipped
    template exists. Keeps the server usable in broken setups."""
    return {
        "current": {"theme": "enough-default", "font": "mono"},
        "fonts": {"mono": {"label": "Monospace", "stack": "ui-monospace, monospace"}},
        "themes": {"enough-default": {"label": "Enough Default", "colors": {}}},
    }


def _ensure_live_ui_config() -> Path:
    """Make sure ~/enough/config/ui.json exists. Seeds from the shipped
    template on first run; otherwise leaves it alone. Returns the path."""
    live = _ui_config_live_path()
    if not live.exists():
        live.parent.mkdir(parents=True, exist_ok=True)
        if UI_CONFIG_TEMPLATE.is_file():
            live.write_text(
                UI_CONFIG_TEMPLATE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            live.write_text(
                json.dumps(_load_ui_config_template(), indent=2),
                encoding="utf-8",
            )
    return live


# The four themes that ship in defaults/ui-config.json. Only these get the
# merge-on-read treatment below — user-authored custom themes are never
# touched (we can't know what an unshipped theme "should" contain).
_SHIPPED_THEMES = ("enough-default", "pastel", "wireframe", "darknest")


def _merge_shipped_theme_keys(cfg: dict[str, Any]) -> dict[str, Any]:
    """Merge-on-read backfill for the four SHIPPED themes.

    Existing users' live ~/enough/config/ui.json predates the 0.1.6
    theme-level `icons` key and the `btn-bg` color, so their copies of the
    shipped themes lack them. Fill those in from the defaults template
    WITHOUT ever overwriting a value the user customized, and without
    touching any custom theme they added. Purely a read-time view — no
    config rewrite — so /api/ui-config serves a complete theme even for a
    config file written by an older enough.

    Missing template → return `cfg` unchanged (nothing to merge from)."""
    if not UI_CONFIG_TEMPLATE.is_file():
        return cfg
    try:
        template = json.loads(UI_CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cfg
    tmpl_themes = template.get("themes") or {}
    user_themes = cfg.get("themes")
    if not isinstance(user_themes, dict):
        return cfg
    for name in _SHIPPED_THEMES:
        tmpl = tmpl_themes.get(name)
        user = user_themes.get(name)
        if not isinstance(tmpl, dict) or not isinstance(user, dict):
            continue
        # Fill theme-level `icons` only if the user's theme lacks it.
        if "icons" not in user and "icons" in tmpl:
            user["icons"] = tmpl["icons"]
        # Fill any missing `colors` entries (e.g. btn-bg); never clobber
        # a color the user already set.
        tmpl_colors = tmpl.get("colors")
        if isinstance(tmpl_colors, dict):
            user_colors = user.get("colors")
            if not isinstance(user_colors, dict):
                user_colors = {}
                user["colors"] = user_colors
            for key, value in tmpl_colors.items():
                if key not in user_colors:
                    user_colors[key] = value
    return cfg


def _read_ui_config() -> dict[str, Any]:
    path = _ensure_live_ui_config()
    try:
        return _merge_shipped_theme_keys(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        log.exception("failed to read live ui config; falling back to template")
        if UI_CONFIG_TEMPLATE.is_file():
            try:
                return json.loads(UI_CONFIG_TEMPLATE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return _load_ui_config_template()


def _write_ui_config(cfg: dict[str, Any]) -> None:
    path = _ensure_live_ui_config()
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def _validate_current(cfg: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed {theme, font} against the available options in
    `cfg`. Returns a sanitized dict — falls back to existing values for
    any unknown entries. Unknown keys in `selection` are silently ignored
    (e.g. legacy 'zoom' field from pre-0.0.5 configs — we just drop it)."""
    current = dict(cfg.get("current") or {})
    # Strip any legacy fields so they don't stick around in the saved file.
    current.pop("zoom", None)
    themes = cfg.get("themes") or {}
    fonts = cfg.get("fonts") or {}
    if "theme" in selection:
        t = str(selection["theme"])
        if t in themes:
            current["theme"] = t
    if "font" in selection:
        f = str(selection["font"])
        if f in fonts:
            current["font"] = f
    return current


CHECKPOINT_PROMPT = (
    "[rness] context window is approaching the auto-reset threshold. "
    "Before we lose continuity, do this in one short response:\n"
    "1. Run `ls rness/requests/*.md` to find your active request file. "
    "If none exists, create one at "
    "`rness/requests/<slug>_<YYYY-MM-DD_HH-MM>.md` with a minimal "
    "Request + Continuation block.\n"
    "2. You MUST call the `write_file` tool to update (or create) that "
    "file with a fresh `## Continuation` section containing: what you "
    "just did, what to do next, any file paths/hashes the next turn "
    "must know, and any caveats. Narrating the update in chat does "
    "NOT persist it — only `write_file` does. The chat history is "
    "about to be wiped.\n"
    "3. End with a one-sentence summary of where things stand.\n"
    "Keep this whole reply under ~250 tokens. The conversation will be "
    "reset immediately after."
)

CONTINUE_PROMPT = (
    "[rness] the conversation has been reset to free up context. Resume the "
    "active work: list `rness/requests/*.md`, read the most recent one's "
    "Continuation section, and pick up from there."
)


async def _drive_message(
    session: Session,
    user_message: str,
    system_prompt: str,
    *,
    is_synthetic: bool = False,
    tool_calls_for_log: list[tuple[str, str]] | None = None,
    assistant_text_for_log: list[str] | None = None,
) -> None:
    """Drive a single user message through the LLM tool loop.

    Pulls the existing per-turn semantics out of `_run_turn` so synthetic
    messages (auto-reset checkpoint + continue) can reuse them without
    re-implementing the streaming, tool dispatch, and usage capture.

    Synthetic messages emit a `system_prompt` event (for the harness-driven
    user-side bubble) instead of `user`, so the UI can render them in a
    distinct style and the user understands they didn't type that. The
    message text still goes onto session.history under the `user` role —
    that's how llama-server learns what was asked. Errors propagate; the
    caller frames them.
    """
    assert session.client is not None
    client = session.client

    session.history.append({"role": "user", "content": user_message})
    await session.emit(
        "system_prompt" if is_synthetic else "user",
        {"text": user_message},
    )

    for _iter in range(session.max_tool_iters):
        messages = [{"role": "system", "content": system_prompt}] + session.history
        await session.emit("turn_start", {})
        buffer = ""
        usage_sink: dict[str, int] = {}
        # Routing: when the active model is OPRO-API (the OpenRouter cloud
        # slot) the chat completion is streamed from cloud.py with the api
        # key injected at the http layer; otherwise the existing local
        # llama-server path runs. Both generators yield content tokens and
        # populate usage_sink the same way, so the downstream loop is
        # untouched. Failure raises (LLMError or CloudHTTPError); the
        # caller's existing exception handling catches both.
        try:
            _active_model = _models.load_state().get("current")
        except Exception:  # noqa: BLE001
            _active_model = None
        if _active_model == "opro-api":
            agen = _cloud.stream_chat_completion(
                messages, client=client, usage_sink=usage_sink,
            )
        else:
            agen = stream_chat(
                session.llm_url, messages, client=client, usage_sink=usage_sink,
            )
        stopped_at_tool = False
        try:
            # Iterate by hand so we can apply a per-chunk inactivity
            # timeout. If llama-server stops emitting tokens (a real
            # symptom we've seen when the KV cache is over-pressured),
            # an `async for` would just hang and the UI would spin
            # forever with no error. wait_for() turns that silence
            # into a visible failure.
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        agen.__anext__(),
                        timeout=LLM_STREAM_INACTIVITY_TIMEOUT,
                    )
                except StopAsyncIteration:
                    break
                buffer += chunk
                await session.emit("token", {"text": chunk})
                end = first_tool_call_end(buffer)
                if end is not None:
                    # Truncate assistant message to end of tool call, stop stream.
                    buffer = buffer[:end]
                    stopped_at_tool = True
                    await agen.aclose()
                    break
        finally:
            # Ensure the generator is closed on any exit path.
            await agen.aclose()

        # Record the assistant turn (possibly truncated at the tool call).
        session.history.append({"role": "assistant", "content": buffer})
        if assistant_text_for_log is not None:
            assistant_text_for_log.append(buffer)
        # When the turn ran against OPRO-API, durably cache the completion
        # under rness/io/cloud-cache/ so a future local-LLM agent (or this
        # agent in a later session) can read what the cloud said. Failure
        # here never breaks the turn — a missing cache file is a UX
        # regression, not a correctness one.
        if _active_model == "opro-api" and buffer:
            try:
                _cloud.cache_completion(
                    session.project_dir,
                    messages=messages,
                    response_text=buffer,
                    model=_cloud.load_cloud_config()["model_id"],
                    usage=usage_sink,
                    source="chat",
                )
            except Exception as e:  # noqa: BLE001
                log.warning("cloud-cache write failed: %s", e)
        # Persist usage from this completion + emit a live update.
        # llama-server reports prompt + completion tokens; for the
        # gauge, total_tokens is what was actually loaded into the
        # KV cache, so it's the truest pressure signal.
        #
        # When the stream was cut at a tool call (or the build doesn't
        # ship `usage`), `usage_sink` is empty — fall back to the same
        # char-based estimate that `_pressure_pct` uses, so the UI
        # gauge stays in sync with the threshold logic instead of
        # frozen at zero. We mark the synthetic payload `estimated`
        # and do NOT write it into `session.last_usage` (which stays
        # reserved for real numbers, so a future real reading wins).
        ctx = _current_ctx_size(session)
        if usage_sink:
            session.last_usage = {**usage_sink, "ctx": ctx} if ctx else dict(usage_sink)
            await session.emit("usage", session.last_usage)
        else:
            est_total = _estimate_total_tokens(session, system_prompt)
            est_payload: dict[str, Any] = {
                "prompt_tokens": est_total,
                "completion_tokens": 0,
                "total_tokens": est_total,
                "estimated": True,
            }
            if ctx:
                est_payload["ctx"] = ctx
            await session.emit("usage", est_payload)
        await session.emit("turn_end", {})

        if not stopped_at_tool:
            return  # natural end — no tool call

        calls = parse_tool_calls(buffer)
        if not calls:
            # Shouldn't happen — first_tool_call_end said yes but parse failed.
            return
        call = calls[-1]  # the call we stopped at
        await _handle_tool(session, call, tool_calls_for_log if tool_calls_for_log is not None else [])

        # Mid-turn pressure check. Auto-reset's end-of-turn check is no
        # help during long tool loops (the agent never voluntarily ends
        # the turn — it just keeps emitting more tool calls). So after
        # each tool result is appended to history, evaluate pressure
        # against the threshold and exit early if we're at/over it. The
        # caller (_run_turn) will then decide whether to fire auto-reset
        # or just end the turn quietly.
        cfg = _load_orchestrator_config()
        pct = _pressure_pct(session, system_prompt)
        if pct >= cfg["threshold_pct"]:
            if not cfg["auto_reset"]:
                # Auto-reset is OFF. _run_turn won't fire anything; the
                # turn just stops. Emit a heads-up so the user knows
                # why and what to do.
                await session.emit("system", {
                    "kind": "pressure_pause",
                    "message": (
                        f"context at {pct}% (threshold {cfg['threshold_pct']}%) "
                        "— pausing mid-turn to avoid overflowing the window. "
                        "send a follow-up message to continue, or enable "
                        "auto-reset in the model modal for hands-free "
                        "continuation on long jobs."
                    ),
                })
            return
    else:
        await session.emit(
            "error",
            {"message": f"tool loop cap ({session.max_tool_iters}) reached"},
        )


async def _do_auto_reset(
    session: Session,
    system_prompt: str,
    *,
    tool_calls_for_log: list[tuple[str, str]] | None = None,
    assistant_text_for_log: list[str] | None = None,
) -> None:
    """Run the checkpoint → reset → continue sequence inside the active
    generation lock. Emits `system` events with progress so the UI can
    explain what just happened, and a `reset` event so the conversation
    pane clears between the checkpoint and continuation.

    The caller's log sinks are threaded through to the synthetic
    checkpoint + continue turns so the day's session log captures
    write_file calls and the agent's checkpoint/resume notes — that's
    the only record of what happened across the reset boundary.

    Re-entry is blocked by `session._in_auto_reset` — without that flag,
    the synthetic continue turn could itself trip the threshold and
    recurse forever.
    """
    cfg = _load_orchestrator_config()
    pct = _pressure_pct(session, system_prompt)
    await session.emit(
        "system",
        {
            "kind": "auto_reset_starting",
            "message": f"context at {pct}% (threshold {cfg['threshold_pct']}%) — "
                       "writing a checkpoint, then resetting to keep going.",
        },
    )

    session._in_auto_reset = True
    try:
        # 1. Checkpoint turn — agent writes Continuation block to its
        #    active request file. We let the existing tool loop handle
        #    write_file via the agent's own response.
        await _drive_message(
            session, CHECKPOINT_PROMPT, system_prompt,
            is_synthetic=True,
            tool_calls_for_log=tool_calls_for_log,
            assistant_text_for_log=assistant_text_for_log,
        )

        # 2. Hard reset of in-memory state. On-disk state (the request
        #    file the agent just updated) is what carries us over.
        session.history.clear()
        session.last_usage = {}
        await session.emit("reset", {"reason": "auto_reset"})
        await session.emit(
            "usage",
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        await session.emit(
            "system",
            {"kind": "auto_reset_continuing",
             "message": "reset complete — continuing from the checkpoint."},
        )

        # 3. Continue turn — agent reads the request file and resumes.
        await _drive_message(
            session, CONTINUE_PROMPT, system_prompt,
            is_synthetic=True,
            tool_calls_for_log=tool_calls_for_log,
            assistant_text_for_log=assistant_text_for_log,
        )
    finally:
        session._in_auto_reset = False


async def _run_turn(session: Session, user_message: str) -> None:
    """Drive one user turn: send to LLM, handle tool loop, emit SSE events.

    Emits:
      - event: user           { "text": <user msg> }  (ack to all listeners)
      - event: system_prompt  { "text": <synthetic harness-driven prompt> }
      - event: system         { "kind": ..., "message": ... }  (auto-reset chrome)
      - event: turn_start     { }
      - event: token          { "text": <chunk> }
      - event: tool           { "name": ..., "key": ..., "ok": ... }
      - event: turn_end       { }
      - event: usage          { prompt_tokens, completion_tokens, total_tokens, ctx }
      - event: reset          { "reason": ... }
      - event: done           { }
      - event: error          { "message": ... }
    """
    async with session.generation_lock:
        # Re-assemble system prompt fresh per spec.
        system_prompt = assemble_system_prompt(session.project_dir)

        tool_calls_for_log: list[tuple[str, str]] = []
        assistant_text_for_log: list[str] = []

        try:
            await _drive_message(
                session,
                user_message,
                system_prompt,
                is_synthetic=False,
                tool_calls_for_log=tool_calls_for_log,
                assistant_text_for_log=assistant_text_for_log,
            )
            # Auto-reset only fires for real user turns (not when we're
            # already in the middle of one) and only when the threshold
            # is breached + the toggle is on.
            if not getattr(session, "_in_auto_reset", False) and _should_auto_reset(session, system_prompt):
                await _do_auto_reset(
                    session, system_prompt,
                    tool_calls_for_log=tool_calls_for_log,
                    assistant_text_for_log=assistant_text_for_log,
                )
        except asyncio.TimeoutError:
            await session.emit("error", {"message": (
                f"the model went silent for over "
                f"{int(LLM_STREAM_INACTIVITY_TIMEOUT)}s mid-stream.\n"
                "this usually means the context window filled up while "
                "generating and llama-server stalled. things to try:\n"
                "  • type `/reset` in the chat input to clear the "
                "conversation, then re-state the task more compactly\n"
                "  • open the model modal and enable auto-reset (or pick "
                "a larger ctx) — that's what it's for\n"
                "  • disable skills you aren't using in the sidebar to "
                "shrink the system prompt"
            )})
            log.warning("llm stream timed out after %ss of silence", LLM_STREAM_INACTIVITY_TIMEOUT)
        except LLMError as e:
            # llama-server returned a 4xx/5xx before the stream began —
            # detect context-window exhaustion and give concrete remedies.
            low = e.detail.lower()
            looks_like_overflow = any(
                k in low for k in ("context", "exceed", "n_ctx", "too many tokens", "token limit")
            )
            if looks_like_overflow:
                msg = (
                    f"context window full (llm {e.status}): {e.detail}\n"
                    "things to try:\n"
                    "  • type `/reset` in the chat input to clear the "
                    "conversation, then re-state the task more compactly\n"
                    "  • open the model modal and enable auto-reset (or "
                    "pick a larger ctx, or switch to a model that fits "
                    "more context)\n"
                    "  • disable skills you aren't using in the sidebar to "
                    "shrink the system prompt"
                )
            else:
                msg = f"llm {e.status}: {e.detail}"
            await session.emit("error", {"message": msg})
            log.exception("llm error")
        except httpx.HTTPError as e:
            await session.emit("error", {"message": f"llm transport error: {e}"})
            log.exception("llm error")
        except Exception as e:  # noqa: BLE001
            await session.emit("error", {"message": f"server error: {e}"})
            log.exception("generation error")
        finally:
            await session.emit("done", {})

        # Persist to session log.
        try:
            log_exchange(
                session.project_dir,
                ExchangeLog(
                    user=user_message,
                    assistant="\n\n".join(t.strip() for t in assistant_text_for_log if t.strip()),
                    tool_calls=tool_calls_for_log,
                ),
                now=dt.datetime.now(),
            )
        except Exception:  # noqa: BLE001
            log.exception("failed to write session log")


async def _handle_tool(session: Session, call: ToolCall, sink: list[tuple[str, str]]) -> None:
    key = call.path or call.command or ""
    await session.emit(
        "tool",
        {"name": call.name, "key": key, "status": "running"},
    )
    # Run blocking tool exec in a thread so we don't stall the event loop.
    result = await asyncio.to_thread(execute, session.project_dir, call)
    sink.append((call.name, key))
    await session.emit(
        "tool",
        {"name": call.name, "key": key, "status": "ok" if result.ok else "error"},
    )
    # Side effects: tools whose ToolResult.side_effects is non-empty
    # are asking the server layer to do something the agent itself
    # can't (emit an SSE event, mutate a session field, etc.).
    # Currently used by `navigate_to_highlight` to ask the UI to
    # scroll the open review pane to a saved highlight.
    for kind, payload in (result.side_effects or {}).items():
        await session.emit(kind, payload)
    session.history.append({"role": "user", "content": result.render()})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    project_dir: Path,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    *,
    supervise: bool = True,
) -> FastAPI:
    session = Session(project_dir=project_dir, llm_url=llm_url, max_tool_iters=max_tool_iters)
    supervisor = LlamaSupervisor(llm_url=llm_url) if supervise else None
    session.supervisor = supervisor  # so _run_turn can read current ctx for the usage gauge

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        session.client = httpx.AsyncClient()
        # Wikisink update runs execute in worker threads (agent tool /
        # endpoint); this hook lets them fan wiki_sink progress events
        # out over SSE without touching the loop directly.
        from .wikisink import update as _wiki_update
        loop = asyncio.get_running_loop()

        def _wiki_progress(data: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(session.emit("wiki_sink", data), loop)

        _wiki_update.PROGRESS_EMITTER = _wiki_progress
        # One-time, idempotent dissolve of ~/enough/infoworld/ into cacheawl
        # cacheboxes (personal/public/wiki). Missing infoworld = no-op; a box
        # of the same name already present = skipped. Move-only.
        try:
            from . import cacheawl as _cacheawl
            report = await asyncio.to_thread(_cacheawl.migrate_infoworld)
            if report.get("migrated"):
                log.info("cacheawl: migrated infoworld folders %s",
                         report["migrated"])
        except Exception:  # noqa: BLE001 — never block startup on migration
            log.exception("cacheawl infoworld migration failed")
        if supervisor is not None:
            try:
                await supervisor.bootstrap()
            except Exception:  # noqa: BLE001
                log.exception("supervisor bootstrap failed")
        try:
            yield
        finally:
            _wiki_update.PROGRESS_EMITTER = None
            if supervisor is not None:
                await supervisor.stop(only_if_owned=True)
            await session.client.aclose()

    app = FastAPI(title="enough", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        # Render any existing history so a page refresh doesn't lose the transcript.
        html = html.replace(
            "<!-- HISTORY -->",
            _render_turn_from_history(session.history),
        )
        # State-aware empty-hint (drift notice, etc.). Empty-when-history-
        # exists semantics are still handled by the post-send htmx hook.
        html = html.replace(
            "<!-- EMPTY_HINT -->",
            _render_empty_hint(session.project_dir),
        )
        html = html.replace("<!-- VERSION -->", f"v{__version__}")
        # Project display name in the header (folder basename unless the user
        # set a custom one). Templated so there's no first-paint flash.
        from . import project_meta
        html = html.replace(
            "<!-- PROJECT_NAME -->",
            _escape_html(project_meta.load(session.project_dir)["name"]),
        )
        # No-cache so edits-in-place don't require force-reload during dev.
        return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate"})

    @app.get("/api/project")
    async def api_project_get() -> dict[str, Any]:
        """Project display metadata: editable name + description + the
        read-only on-disk path. Powers the header title and its edit modal."""
        from . import project_meta
        return project_meta.load(session.project_dir)

    @app.post("/api/project")
    async def api_project_set(request: Request) -> dict[str, Any]:
        """Persist the project's display name and/or description. Body:
        {"name": "...", "description": "..."}. The folder on disk is never
        renamed — only `rness/project.json` is written. Returns the refreshed
        metadata so the UI can update the header in place."""
        from . import project_meta
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return project_meta.save(
            session.project_dir,
            (body or {}).get("name"),
            (body or {}).get("description"),
        )

    @app.get("/api/files", response_class=HTMLResponse)
    async def api_files() -> HTMLResponse:
        tree = build_file_tree(project_dir)
        return HTMLResponse(_tree_to_html(tree))

    @app.get("/api/paradigm", response_class=HTMLResponse)
    async def api_paradigm() -> HTMLResponse:
        from .skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        rness = project_dir / "rness"
        items = list_paradigms(rness)
        if not items:
            return HTMLResponse('<div class="empty-note">no paradigms in rness/paradigms/</div>')
        active = get_active_paradigm(rness)
        rows = []
        for name, desc, tooltip in items:
            is_active = name == active
            cls = "on" if is_active else "off"
            marker = "●" if is_active else "○"
            # Prefer the user-facing tooltip; fall back to the agent-facing
            # description so existing paradigms don't lose their hover text
            # until each one's `enough-tooltip-text:` is populated.
            tip_text = tooltip if tooltip else desc
            tip = _escape_html(tip_text) if tip_text else ""
            rows.append(
                f'<li class="paradigm-row {cls}" title="{tip}">'
                f'  <button class="paradigm-toggle" '
                f'    hx-post="/api/paradigm/set" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}"}}\' '
                f'    hx-target="#paradigm-list" hx-swap="innerHTML">'
                f'    {marker}'
                f'  </button>'
                f'  <span class="paradigm-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="paradigms">' + "".join(rows) + "</ul>")

    @app.post("/api/paradigm/set", response_class=HTMLResponse)
    async def api_paradigm_set(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        rness = project_dir / "rness"
        # Validate: only allow names that resolve to an existing paradigm file.
        valid_names = {n for n, _d, _t in list_paradigms(rness)}
        if name not in valid_names:
            raise HTTPException(400, f"unknown paradigm: {name}")
        set_active_paradigm(rness, name)
        return await api_paradigm()  # type: ignore[return-value]

    @app.get("/api/skills", response_class=HTMLResponse)
    async def api_skills() -> HTMLResponse:
        from .skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        items = list_skills(project_dir / "rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no skills in rness/skills/</div>')
        rows = []
        for name, enabled, tooltip in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            tip = _escape_html(tooltip) if tooltip else ""
            title_attr = f' title="{tip}"' if tip else ""
            rows.append(
                f'<li class="skill-row {cls}"{title_attr}>'
                f'  <button class="skill-toggle" '
                f'    hx-post="/api/skills/toggle" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}", "enabled": "{next_val}"}}\' '
                f'    hx-target="#skills-list" hx-swap="innerHTML">'
                f'    {"●" if enabled else "○"}'
                f'  </button>'
                f'  <span class="skill-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="skills">' + "".join(rows) + "</ul>")

    @app.post("/api/skills/toggle", response_class=HTMLResponse)
    async def api_skills_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        set_skill_enabled(project_dir / "rness", name, enabled_raw == "1")
        return await api_skills()  # type: ignore[return-value]

    @app.get("/api/roles", response_class=HTMLResponse)
    async def api_roles() -> HTMLResponse:
        from .skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        items = list_roles(project_dir / "rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no roles in rness/roles/</div>')
        rows = []
        for name, enabled, tooltip in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            tip = _escape_html(tooltip) if tooltip else ""
            title_attr = f' title="{tip}"' if tip else ""
            rows.append(
                f'<li class="role-row {cls}"{title_attr}>'
                f'  <button class="role-toggle" '
                f'    hx-post="/api/roles/toggle" '
                f'    hx-vals=\'{{"name": "{_escape_html(name)}", "enabled": "{next_val}"}}\' '
                f'    hx-target="#roles-list" hx-swap="innerHTML">'
                f'    {"●" if enabled else "○"}'
                f'  </button>'
                f'  <span class="role-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        return HTMLResponse('<ul class="roles">' + "".join(rows) + "</ul>")

    @app.post("/api/roles/toggle", response_class=HTMLResponse)
    async def api_roles_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        set_role_enabled(project_dir / "rness", name, enabled_raw == "1")
        return await api_roles()  # type: ignore[return-value]

    @app.get("/api/help/defaults")
    async def api_help_defaults() -> dict[str, Any]:
        """Installed skills / roles / paradigms (name + description) for the
        help viewer's {{skills-list}} / {{roles-list}} / {{paradigms-list}}
        tokens, so the default lists in help stay in sync with what's actually
        present instead of drifting hand-maintained prose."""
        rness = project_dir / "rness"

        def _build() -> dict[str, Any]:
            from .skeleton import resync_globals
            resync_globals(project_dir)  # pick up globals added since launch
            skills = [{"name": n, "desc": t} for n, _en, t in list_skills(rness)]
            roles = [{"name": n, "desc": t} for n, _en, t in list_roles(rness)]
            # Paradigms carry an agent-facing description; prefer the
            # user-facing tooltip when present (same rule as the sidebar).
            paradigms = [{"name": n, "desc": (t or d)}
                         for n, d, t in list_paradigms(rness)]
            return {"skills": skills, "roles": roles, "paradigms": paradigms}

        return await asyncio.to_thread(_build)

    @app.get("/api/help/bubbles")
    async def api_help_bubbles_get() -> dict[str, Any]:
        """Whether the sidebar's ``(?)`` help bubbles are shown for this
        project — a sticky per-folder boolean stored in the multipurpose
        `rness/active-paradigm` file, default on."""
        rness = project_dir / "rness"
        enabled = await asyncio.to_thread(get_help_bubbles, rness)
        return {"enabled": enabled}

    @app.post("/api/help/bubbles")
    async def api_help_bubbles_post(request: Request) -> dict[str, Any]:
        """Set the per-project help-bubble on/off state. Body
        ``{"enabled": bool}``; 400 on a non-boolean."""
        body = await request.json()
        enabled = body.get("enabled") if isinstance(body, dict) else None
        if not isinstance(enabled, bool):
            raise HTTPException(400, "enabled must be a boolean")
        await asyncio.to_thread(set_help_bubbles, project_dir / "rness", enabled)
        return {"enabled": enabled}

    @app.get("/api/help-center", response_class=PlainTextResponse)
    async def api_help_center() -> PlainTextResponse:
        """The full help-center manual (docs/HELP_CENTER.md in the install
        checkout), served as raw markdown for the read-only reference mode."""
        doc = Path(__file__).resolve().parent.parent / "docs" / "HELP_CENTER.md"
        text = await asyncio.to_thread(
            lambda: doc.read_text(encoding="utf-8") if doc.is_file() else None)
        if text is None:
            raise HTTPException(
                404,
                "HELP_CENTER.md not found in this install — run /update-enough "
                "to pick up the bundled manual.")
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

    @app.post("/api/requests/done", response_class=HTMLResponse)
    async def api_requests_done(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        if not _is_request_file(path):
            raise HTTPException(400, "not an active request file")
        target = _resolve_project_path(path)
        if not target.is_file():
            raise HTTPException(404, "not found")
        done_dir = project_dir / "rness" / "requests" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        dest = done_dir / target.name
        # If a file with the same name already exists in done/, disambiguate.
        if dest.exists():
            dest = done_dir / (target.stem + "_dup.md")
        target.rename(dest)
        # No body needed — the caller closes the preview pane and refreshes
        # the file tree itself; this response just confirms the move.
        return HTMLResponse("")

    def _resolve_project_path(path: str) -> Path:
        """Shared path-safety helper for /api/file{,/raw} and POST writes.

        Containment check is done on the LOGICAL path (composition) so that
        symlinks living at a valid relative location inside rness/ and
        pointing outside the project — intentional, used for global
        defaults — aren't rejected. The tool layer has its own allowlist
        for follow-through reads; this helper guards only against path-
        string traversal (absolute paths and `..` components).

        A `cacheawl:<box>/<rel>` prefix addresses the machine-global
        cachebox store instead of the project — that's how cacheawl mode
        launches store files into read/edit, girraph, and merirmaid
        modes. Same traversal rules apply inside the store; the mirror
        and sidecar write-guards downstream see the resolved target and
        keep applying."""
        if path.startswith("cacheawl:"):
            rel = Path(path[len("cacheawl:"):].lstrip("/"))
            if rel.is_absolute() or ".." in rel.parts or not rel.parts:
                raise HTTPException(400, "invalid path")
            from . import cacheawl as _cacheawl
            return _cacheawl.root().resolve() / rel
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise HTTPException(400, "invalid path")
        # Compose against the resolved project root so we don't end up with
        # /tmp-vs-/private/tmp mismatches on macOS. Don't resolve the final
        # target — that would follow symlinks and break containment checks
        # for in-tree symlinks.
        project_root = project_dir.resolve()
        return project_root / p

    def _is_request_file(path: str) -> bool:
        p = Path(path)
        parts = p.parts
        # Active request = directly under rness/requests/ (not /done/).
        return (
            len(parts) >= 3
            and parts[0] == "rness"
            and parts[1] == "requests"
            and parts[2] != "done"
            and parts[-1].endswith(".md")
        )

    def _is_skill_file(path: str) -> bool:
        parts = Path(path).parts
        return len(parts) >= 2 and parts[0] == "rness" and parts[1] == "skills"

    def _is_role_file(path: str) -> bool:
        parts = Path(path).parts
        return len(parts) >= 2 and parts[0] == "rness" and parts[1] == "roles"

    def _is_external_symlink(path_str: str) -> tuple[bool, Path | None]:
        """Is `path` a symlink whose resolved target lives outside the project?
        Returns (yes_external, target_abs) for the truthy case."""
        raw = project_dir / path_str
        if not raw.is_symlink():
            return False, None
        target = raw.resolve(strict=False)
        try:
            target.relative_to(project_dir.resolve())
            return False, target  # resolves inside the project — treat as normal
        except ValueError:
            return True, target

    @app.get("/api/reveal", response_class=HTMLResponse)
    async def api_reveal(path: str = Query(...)) -> HTMLResponse:
        """Pop open the platform file manager at the given path — Finder
        via `open -R` on macOS, whatever `xdg-open` resolves to on Linux.
        Used by the agent to drop clickable links into chat completions —
        e.g. "your new skill lives here:
        [Open in Finder](/api/reveal?path=rness/skills/foo)".

        Path-safety rules mirror `read_file`: project-relative paths are
        always OK; absolute (or `~`-prefixed) paths must resolve under
        the read-allowlist from `rness/policies/allowlists.md` (which
        transparently includes file-rw prefixes too)."""
        if not (sys.platform == "darwin" or sys.platform.startswith("linux")):
            raise HTTPException(
                501,
                f"reveal-in-file-manager needs macOS (`open -R`) or Linux "
                f"(`xdg-open`); this machine reports {sys.platform!r}.",
            )
        raw = path.strip()
        if not raw:
            raise HTTPException(400, "missing path")
        # Resolve to an absolute path. `~` expansion is convenient for
        # the agent when emitting `~/enough/...` links.
        p = Path(raw).expanduser()
        if p.is_absolute():
            target = p.resolve(strict=False)
            project_root = project_dir.resolve(strict=False)
            try:
                target.relative_to(project_root)
                inside_project = True
            except ValueError:
                inside_project = False
            if not inside_project:
                allowlist = _read_allowlist(project_dir)
                if not _under_any(target, allowlist):
                    raise HTTPException(
                        403,
                        f"{raw} is outside the project and off the read-"
                        "allowlist. add its prefix to rness/policies/"
                        "allowlists.md or use a project-relative path.",
                    )
        else:
            if ".." in p.parts:
                raise HTTPException(400, "invalid path")
            target = (project_dir / p).resolve(strict=False)
            try:
                target.relative_to(project_dir.resolve(strict=False))
            except ValueError:
                raise HTTPException(400, "path escapes project root")
        if not target.exists():
            raise HTTPException(404, f"not found: {target}")
        if sys.platform == "darwin":
            # `open` opens files in the default app and reveals folders in
            # Finder. Use `-R` to highlight a file in its parent folder
            # rather than opening it directly (more useful for "go check
            # out this newly-created file" cases).
            manager = "Finder"
            cmd = ["/usr/bin/open"]
            if target.is_file():
                cmd.extend(["-R", str(target)])
            else:
                cmd.append(str(target))
        else:
            import shutil as _shutil
            xdg = _shutil.which("xdg-open")
            if not xdg:
                raise HTTPException(
                    501,
                    "xdg-open isn't installed, so there's no way to ask this "
                    "desktop to open a folder. `sudo apt install xdg-utils` "
                    "(Debian/Ubuntu) or `sudo dnf install xdg-utils` (Fedora).",
                )
            # xdg-open has no `-R` equivalent — there is no cross-desktop
            # "select this file in its folder" verb. Opening a file would
            # launch it in its default application, which is emphatically
            # not what "reveal" means, so a file reveals as its PARENT
            # folder. Same intent, one click of divergence from macOS.
            manager = "your file manager"
            cmd = [xdg, str(target if target.is_dir() else target.parent)]
        try:
            subprocess.Popen(cmd)
        except OSError as e:
            raise HTTPException(500, f"open failed: {e}")
        # Tiny auto-closing page so the user's click doesn't leave a
        # blank tab behind. Falls back to a manual close-this-tab note.
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8>"
            f"<title>Opened in {_escape_html(manager)}</title>"
            "<style>body{font-family:system-ui;padding:24px;color:#555}</style>"
            "<p>Opened <code>" + _escape_html(str(target)) + "</code> "
            f"in {_escape_html(manager)}. You can close this tab.</p>"
            "<script>setTimeout(()=>window.close(), 200)</script>"
        )

    @app.get("/api/file", response_class=HTMLResponse)
    async def api_file(path: str = Query(...)) -> HTMLResponse:
        target = _resolve_project_path(path)
        if not target.exists():
            raise HTTPException(404, "not found")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return HTMLResponse(
                f'<div class="binary-file">binary file — {target.stat().st_size} bytes</div>'
            )
        # Preview chrome: path header, body, and context-sensitive action buttons.
        external, sym_target = _is_external_symlink(path)
        mark_done_btn = (
            f'<button class="mark-done" onclick="markRequestDone(\'{_escape_html(path)}\')">mark done</button>'
            if _is_request_file(path)
            else ""
        )
        if _is_skill_file(path):
            # Skills are global. No in-UI edit or customize — edit at the
            # source under ~/enough/defaults/skills/<name>/ instead.
            sym_note = (
                '<div class="symlink-note">'
                'skill file — edit globally at '
                '<code>~/enough/defaults/skills/</code>; '
                'toggle on/off for this project in the sidebar.'
                '</div>'
            )
            action_btn = ""
        elif _is_role_file(path):
            # Same pattern as skills — roles are global, edited at source.
            sym_note = (
                '<div class="symlink-note">'
                'role file — edit globally at '
                '<code>~/enough/defaults/roles/</code>; '
                'toggle on/off for this project in the sidebar.'
                '</div>'
            )
            action_btn = ""
        elif external:
            sym_note = (
                f'<div class="symlink-note">symlink → '
                f'<code>{_escape_html(str(sym_target))}</code></div>'
            )
            action_btn = (
                f'<button class="customize-btn" '
                f'onclick="customizeForProject(\'{_escape_html(path)}\')">'
                f'customize for this project</button>'
            )
        else:
            sym_note = ""
            action_btn = (
                '<button class="edit-btn" onclick="enterEditMode()">edit mode</button>'
            )
        # Review-mode button: only meaningful for markdown-ish text files.
        # Renders LEFT of the edit button, with a contrasting accent fill
        # so it stands out from the muted action row. Plain-text files
        # would technically render fine too (no markdown ⇒ paragraphs),
        # but for v1 we gate to .md/.markdown to keep the button's
        # promise honest.
        review_btn = ""
        lower = path.lower()
        if lower.endswith((".md", ".markdown")) and not _is_skill_file(path) and not _is_role_file(path):
            review_btn = (
                f'<button class="review-btn" '
                f'onclick="enterReviewMode(\'{_escape_html(path)}\')">'
                f'review mode</button>'
            )
        if lower.endswith(".girraph"):
            # Girraphs get their own editable panel; raw edit mode is
            # blocked for them (node-level ops only), so the girraph
            # button replaces the edit button.
            review_btn = (
                f'<button class="review-btn" '
                f'onclick="enterGirraphMode(\'{_escape_html(path)}\')">'
                f'🦒 girraph panel</button>'
            )
            action_btn = ""
        return HTMLResponse(
            f'<div class="file-path" data-path="{_escape_html(path)}">{_escape_html(path)}</div>'
            f'{sym_note}'
            f'<div class="preview-actions">'
            f'  {mark_done_btn}'
            f'  {review_btn}'
            f'  {action_btn}'
            f'</div>'
            f'<pre class="file-body">{_escape_html(text)}</pre>'
        )

    @app.post("/api/file/customize", response_class=HTMLResponse)
    async def api_file_customize(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        raw = project_dir / path
        if not raw.is_symlink():
            raise HTTPException(400, "not a symlink — nothing to customize")
        external, sym_target = _is_external_symlink(path)
        if not external or sym_target is None:
            raise HTTPException(400, "symlink resolves inside the project")
        # Read the current target content, drop the symlink, write a copy.
        try:
            content = sym_target.read_text(encoding="utf-8")
        except OSError as e:
            raise HTTPException(500, f"could not read symlink target: {e}") from None
        try:
            raw.unlink()
        except OSError as e:
            raise HTTPException(500, f"could not remove symlink: {e}") from None
        raw.write_text(content, encoding="utf-8")
        # Return the refreshed preview fragment (now editable).
        return await api_file(path=path)  # type: ignore[return-value]

    @app.get("/api/file/raw", response_class=PlainTextResponse)
    async def api_file_raw(path: str = Query(...)) -> PlainTextResponse:
        target = _resolve_project_path(path)
        if not target.exists():
            raise HTTPException(404, "not found")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "not utf-8 text") from None
        return PlainTextResponse(text)

    # ---------- Tree create operations (new folder / new file) ----------
    #
    # Backing for the option-click context menu in the sidebar tree.
    # Validation is intentionally strict: names are single path segments
    # (no slashes, no `..`, no leading dot beyond the dotfile pattern,
    # no NUL). The parent must already exist as a directory inside the
    # project root (or inside an in-tree symlink target).
    # Existing entries are never clobbered.

    def _validate_new_name(name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise HTTPException(400, "name is required")
        if "/" in name or "\\" in name or "\x00" in name:
            raise HTTPException(400, "name may not contain path separators")
        if name in (".", ".."):
            raise HTTPException(400, "invalid name")
        if len(name) > 255:
            raise HTTPException(400, "name too long")
        return name

    @app.post("/api/file/new-folder")
    async def api_file_new_folder(request: Request) -> dict[str, Any]:
        """Create a new directory at `<parent>/<name>`. Body JSON:
        {"parent": "rness/io/output", "name": "drafts"}. Parent must be
        an existing directory inside the project. Returns the new
        project-relative path."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        parent_rel = (body.get("parent") or "").strip()
        name = _validate_new_name(body.get("name") or "")
        # Empty parent means project root, which is fine.
        parent = _resolve_project_path(parent_rel) if parent_rel else project_dir.resolve()
        if not parent.exists() or not parent.is_dir():
            raise HTTPException(404, "parent directory not found")
        target = parent / name
        if target.exists():
            raise HTTPException(409, f"already exists: {name}")
        try:
            target.mkdir()
        except OSError as e:
            raise HTTPException(500, f"could not create folder: {e}") from None
        return {"ok": True, "path": f"{parent_rel.rstrip('/')}/{name}" if parent_rel else name}

    @app.post("/api/file/new-file")
    async def api_file_new_file(request: Request) -> dict[str, Any]:
        """Create a new empty file at `<parent>/<name>`. Same shape as
        new-folder. The client may pass a bare name (e.g. `notes`); we
        append `.md` if no `.md`/`.markdown` extension is present, since
        the context-menu entry is "new md file" by intent."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        parent_rel = (body.get("parent") or "").strip()
        name = _validate_new_name(body.get("name") or "")
        lower = name.lower()
        if not (lower.endswith(".md") or lower.endswith(".markdown")):
            name = name + ".md"
        parent = _resolve_project_path(parent_rel) if parent_rel else project_dir.resolve()
        if not parent.exists() or not parent.is_dir():
            raise HTTPException(404, "parent directory not found")
        target = parent / name
        if target.exists():
            raise HTTPException(409, f"already exists: {name}")
        try:
            target.write_text("", encoding="utf-8")
        except OSError as e:
            raise HTTPException(500, f"could not create file: {e}") from None
        return {"ok": True, "path": f"{parent_rel.rstrip('/')}/{name}" if parent_rel else name}

    # ---------- Highlights (review-mode color metadata) ----------
    #
    # Per-doc CRUD over the dotted JSON sidecar managed by
    # `enough.highlights`. The review-mode JS calls these on entry
    # (GET) and on every color-button toggle (POST/DELETE). Returns
    # plain JSON; the journal entry is written by the highlights
    # module so each call shows up alongside tool-call traces in
    # `rness/knowledge/session-logs/<date>-broker.md`.
    from . import highlights as _highlights

    @app.get("/api/highlights")
    async def api_highlights_get(path: str = Query(...)) -> dict[str, Any]:
        # Resolve through the same path-safety helper as /api/file so
        # off-allowlist paths get the same 4xx behavior. We don't need
        # the resolved path itself — load_highlights uses doc_rel.
        _resolve_project_path(path)
        items = _highlights.load_highlights(project_dir, path)
        return {"path": path, "highlights": items}

    @app.post("/api/highlights")
    async def api_highlights_post(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        _resolve_project_path(path)
        color = (form.get("color") or "").strip()
        snippet = form.get("snippet") or ""
        if not snippet:
            raise HTTPException(400, "missing snippet")
        before_anchor = form.get("before_anchor") or ""
        after_anchor = form.get("after_anchor") or ""
        # src_start / src_end are optional ints; missing/blank ⇒ None.
        def _maybe_int(name: str) -> int | None:
            v = form.get(name)
            if v is None or v == "":
                return None
            try:
                return int(v)
            except ValueError:
                raise HTTPException(400, f"{name} must be int") from None
        try:
            entry = _highlights.add_highlight(
                project_dir, path,
                color=color,
                snippet=snippet,
                before_anchor=before_anchor,
                after_anchor=after_anchor,
                src_start=_maybe_int("src_start"),
                src_end=_maybe_int("src_end"),
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"path": path, "highlight": entry}

    @app.delete("/api/highlights")
    async def api_highlights_delete(
        path: str = Query(...),
        id: str = Query(...),
    ) -> dict[str, Any]:
        _resolve_project_path(path)
        ok = _highlights.delete_highlight(project_dir, path, id)
        if not ok:
            raise HTTPException(404, "no such highlight id")
        return {"path": path, "id": id, "removed": True}

    @app.patch("/api/highlights")
    async def api_highlights_patch(request: Request) -> dict[str, Any]:
        """Mutate fields on an existing highlight — primarily the
        color, used by the per-highlight handle popup (Phase 5c) when
        the user clicks a different circle. Whitelist of safe fields
        is enforced inside highlights.update_highlight."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        hl_id = (form.get("id") or "").strip()
        if not path or not hl_id:
            raise HTTPException(400, "missing path or id")
        _resolve_project_path(path)
        changes: dict[str, Any] = {}
        if (color := form.get("color")):
            color = color.strip().lower()
            if color not in _highlights.ALLOWED_COLORS:
                raise HTTPException(
                    400,
                    f"unknown color {color!r}; allowed: "
                    + ", ".join(_highlights.ALLOWED_COLORS),
                )
            changes["color"] = color
        if not changes:
            raise HTTPException(400, "no updatable fields supplied")
        updated = _highlights.update_highlight(project_dir, path, hl_id, **changes)
        if updated is None:
            raise HTTPException(404, "no such highlight id")
        return {"path": path, "highlight": updated}

    # ---------- Girraph (plain-text IBIS map) node ops ----------
    #
    # The editable girraph panel calls these. Both this API and the
    # agent's girraph tools go through `enough.girraph`'s node-level ops
    # under the same per-path lock — that's the whole concurrency story
    # for simultaneous user-panel and agent edits (last-write-wins at
    # node granularity). Every mutation is journaled via broker.trace so
    # panel edits show up alongside tool calls in the session log.
    from . import girraph as _girraph

    def _girraph_path(path: str) -> Path:
        target = _resolve_project_path(path)
        if not path.endswith(".girraph"):
            raise HTTPException(400, "not a .girraph path")
        return target

    def _merirmaid_echo(path: str) -> str:
        """The sibling `.merirmaid` path in the SAME scheme the request used —
        so a `cacheawl:`-prefixed girraph answers with a `cacheawl:`-prefixed
        mirror, and an in-tree girraph with an in-tree mirror."""
        if path.endswith(".girraph"):
            return path[: -len(".girraph")] + ".merirmaid"
        return path

    def _girraph_node_json(g: "_girraph.Girraph", n: "_girraph.Node") -> dict[str, Any]:
        ref_kind = ""
        ref_broken = False
        if n.ref:
            ref_kind = "girraph" if n.ref.endswith(".girraph") else "doc"
            ref_broken = not (project_dir / n.ref).exists()
        return {
            "id": n.id,
            "type": n.type,
            "sigil": n.sigil,
            "emoji": n.emoji,
            "label": n.label,
            "parent": n.parent,
            "cross": n.cross,
            "ref": n.ref,
            "ref_kind": ref_kind,
            "ref_broken": ref_broken,
            "by": n.by,
            "detail": n.detail,
        }

    def _girraph_tree_json(path: str, g: "_girraph.Girraph") -> dict[str, Any]:
        return {
            "path": path,
            "title": g.title,
            "warnings": g.warnings,
            "roots": [n.id for n in g.roots()],
            "nodes": [
                _girraph_node_json(g, g.nodes[v])
                for k, v in g.order if k == "node" and v in g.nodes
            ],
        }

    @app.get("/api/girraph")
    async def api_girraph_get(path: str = Query(...)) -> dict[str, Any]:
        target = _girraph_path(path)
        try:
            g = _girraph.load(target)
        except _girraph.GirraphError as e:
            raise HTTPException(404, str(e)) from None
        out = _girraph_tree_json(path, g)
        # The linked-mirror state, so the frontend's add/open-merirmaid
        # button needs no extra round trip. Echoed in the request's own path
        # scheme (cacheawl: prefix preserved).
        out["merirmaid"] = _merirmaid_echo(path) if _girraph.has_mirror(target) else None
        return out

    @app.post("/api/girraph/node")
    async def api_girraph_add_node(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        target = _girraph_path(path)
        label = (form.get("label") or "").strip()
        parent = (form.get("parent") or "").strip() or None
        with _girraph.path_lock(target):
            if target.is_file():
                g = _girraph.load(target)
            elif parent:
                raise HTTPException(404, "girraph does not exist yet")
            else:
                g = _girraph.new_girraph(label)
            try:
                node = _girraph.add_node(
                    g,
                    type=(form.get("type") or "").strip(),
                    label=label,
                    parent=parent,
                    ref=(form.get("ref") or "").strip() or None,
                    by=(form.get("by") or "").strip() or None,
                    detail=form.get("detail") or "",
                )
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="add node (panel)",
            args={"path": path, "id": node.id, "label": node.label[:60]},
            result_ok=True, result_summary=f"added {node.id}",
        )
        return {"path": path, "node": _girraph_node_json(g, node)}

    @app.patch("/api/girraph/node")
    async def api_girraph_update_node(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        node_id = (form.get("id") or "").strip()
        if not node_id:
            raise HTTPException(400, "missing id")
        target = _girraph_path(path)
        # Field absent from the form ⇒ untouched; present-but-empty ⇒ clear.
        patch = {
            f: form.get(f)
            for f in ("label", "detail", "ref", "by", "parent")
            if f in form
        }
        if not patch:
            raise HTTPException(400, "no updatable fields supplied")
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                node = _girraph.update_node(g, node_id, **patch)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="update node (panel)",
            args={"path": path, "id": node_id, "fields": ",".join(sorted(patch))},
            result_ok=True, result_summary=f"patched {node_id}",
        )
        return {"path": path, "node": _girraph_node_json(g, node)}

    @app.delete("/api/girraph/node")
    async def api_girraph_remove_node(
        path: str = Query(...),
        id: str = Query(...),
        cascade: bool = Query(False),
    ) -> dict[str, Any]:
        # The panel's delete button shows its own are-you-sure dialog —
        # a user-initiated DELETE is the confirmation, mirroring how
        # "mark done" works for requests.
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                removed = _girraph.remove_node(g, id, cascade=cascade)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        _broker.trace(
            project_dir, tool="girraph", decision="remove node (panel)",
            args={"path": path, "id": id, "cascade": cascade},
            result_ok=True, result_summary=f"removed {', '.join(removed)}",
        )
        return {"path": path, "removed": removed}

    @app.post("/api/girraph/link")
    async def api_girraph_link(request: Request) -> dict[str, Any]:
        form = await request.form()
        path = (form.get("path") or "").strip()
        from_id = (form.get("from") or "").strip()
        to_id = (form.get("to") or "").strip()
        remove = (form.get("remove") or "").strip().lower() in ("true", "1", "yes")
        if not from_id or not to_id:
            raise HTTPException(400, "missing from/to")
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                g = _girraph.load(target)
                if remove:
                    _girraph.unlink_nodes(g, from_id, to_id)
                else:
                    _girraph.link_nodes(g, from_id, to_id)
            except _girraph.GirraphError as e:
                raise HTTPException(400, str(e)) from None
            _girraph.save(target, g)
        verb = "unlink" if remove else "link"
        _broker.trace(
            project_dir, tool="girraph", decision=f"{verb} (panel)",
            args={"path": path, "from": from_id, "to": to_id},
            result_ok=True, result_summary=f"{verb}ed {from_id} -> {to_id}",
        )
        return {"path": path, "from": from_id, "to": to_id, "removed": remove}

    @app.post("/api/girraph/merirmaid")
    async def api_girraph_merirmaid(request: Request) -> dict[str, Any]:
        """Create (or idempotently regenerate) the sibling `.merirmaid` mirror
        for a girraph. 404 if the girraph is missing/unparsable; 409 if a
        `.merirmaid` already claims the sibling name but is NOT a
        girraph-mirror (a hand-authored diagram — we won't clobber it). When
        the sibling already IS a girraph-mirror this just regenerates it.
        Returns ``{"merirmaid": "<sibling path in the request's scheme>"}``."""
        body = await request.json()
        path = (body.get("path") or "").strip() if isinstance(body, dict) else ""
        target = _girraph_path(path)
        with _girraph.path_lock(target):
            try:
                _girraph.load(target)
            except _girraph.GirraphError as e:
                raise HTTPException(404, str(e)) from None
            mp = _girraph.mirror_path(target)
            if mp.exists() and not _girraph.has_mirror(target):
                raise HTTPException(
                    409,
                    f"{mp.name} already exists and is not a girraph mirror "
                    f"(modality/kind mismatch) — rename or remove it first.",
                )
            _girraph.create_mirror(target, path)
        _broker.trace(
            project_dir, tool="girraph", decision="create merirmaid (panel)",
            args={"path": path}, result_ok=True,
            result_summary=f"mirror for {path}",
        )
        return {"merirmaid": _merirmaid_echo(path)}

    @app.get("/api/girraph/ref-candidates")
    async def api_girraph_ref_candidates(name: str = Query(...)) -> dict[str, Any]:
        """Repair helper for broken refs: same-basename matches anywhere
        in the project (skipping dotdirs), in the spirit of the broker
        index. The panel offers these as one-click re-points."""
        base = Path(name).name
        if not base:
            raise HTTPException(400, "missing name")
        hits: list[str] = []
        root = project_dir.resolve()
        for p in root.rglob(base):
            if any(part.startswith(".") for part in p.relative_to(root).parts):
                continue
            hits.append(str(p.relative_to(root)))
            if len(hits) >= 20:
                break
        return {"name": base, "candidates": sorted(hits)}

    # ------------------------------------------------------------------
    # Wikisink — local Wikipedia (🚰)
    # ------------------------------------------------------------------

    from .wikisink import download as _wiki_download
    from .wikisink import overlay as _wiki_overlay
    from .wikisink import zim as _wiki_zim

    wiki_dl = _wiki_download.DownloadManager(emit=session.emit)

    def _wiki_503(e: Exception) -> HTTPException:
        # WikisinkUnavailable messages are user-facing and actionable.
        return HTTPException(503, str(e))

    @app.get("/api/wiki/status")
    async def api_wiki_status() -> dict[str, Any]:
        def _status() -> dict[str, Any]:
            cfg = _wikisink_config.load_config()
            installed = _wikisink_config.installed(cfg)
            info = None
            if installed:
                try:
                    info = _wiki_zim.snapshot_info()
                except (_wiki_zim.WikisinkUnavailable, RuntimeError) as e:
                    # libzim wheel missing, or the file is corrupt/truncated
                    # (a real possibility with removable drives)
                    installed = False
                    info = {"error": str(e)}
            try:
                comment_count = len(list(_wikisink_config.comments_dir(cfg).glob("*.json")))
            except OSError:
                comment_count = 0
            active_meta = _wikisink_config.active_zim_meta(cfg)
            install_rows = [{
                **i,
                "size_human": _wiki_download.bytes_to_human(i.get("size_bytes") or 0),
                "available": _wikisink_config.install_available(i),
                "active": i.get("id") == cfg.get("active_install"),
            } for i in _wikisink_config.installs(cfg)]
            return {
                # installed = the active archive is servable right now;
                # configured = installs exist, reachable or not. A detached
                # drive is configured-but-not-installed, and the reason
                # explains that in user words.
                "installed": installed,
                "configured": _wikisink_config.configured(cfg),
                "unavailable_reason": (None if installed
                                       else _wikisink_config.unavailable_reason(cfg)),
                "installs": install_rows,
                "active_install": cfg.get("active_install"),
                "zim": info,
                "flavor": active_meta.get("flavor"),
                "snapshot": active_meta.get("snapshot"),
                "storage_dir": str(active_meta.get("storage_dir")
                                   or _wikisink_config.DEFAULT_STORAGE_DIR),
                "data_dir": str(_wikisink_config.data_dir(cfg)),
                "download": cfg.get("download"),
                "download_active": wiki_dl.active,
                "last_viewed": cfg.get("last_viewed"),
                "last_wikisink_at": cfg.get("last_wikisink_at"),
                # cached_only: status must stay instant; the flavors call
                # made when the setup modal opens warms this cache.
                "newer_snapshot": _wiki_download.newer_snapshot_available(
                    cfg, cached_only=True) if installed else None,
                "counts": {
                    "watched": len(cfg.get("watched", [])),
                    "comments": comment_count,
                    "overrides": len(cfg.get("overrides", [])),
                },
                "overrides": cfg.get("overrides", []),
            }
        return await asyncio.to_thread(_status)

    @app.post("/api/wiki/installs/activate")
    async def api_wiki_install_activate(request: Request) -> dict[str, Any]:
        """Switch which registered archive is served. Switching to a
        currently unreachable install is allowed (the user may be about
        to plug the drive in) — the UI warns, nothing breaks."""
        body = await request.json()
        install = (body.get("id") or "").strip()
        entry = await asyncio.to_thread(_wikisink_config.set_active_install, install)
        if entry is None:
            raise HTTPException(404, f"no install {install!r}")
        _wiki_zim.reset_archive()
        _broker.trace(project_dir, tool="wiki_install", decision="allowed",
                      args={"op": "activate", "id": install},
                      result_ok=True, result_summary=entry.get("filename") or "")
        return {"ok": True, "active": entry,
                "available": _wikisink_config.install_available(entry)}

    @app.delete("/api/wiki/installs")
    async def api_wiki_install_forget(id: str = Query(...)) -> dict[str, Any]:
        """Forget an install (registry only). The archive file always
        stays on disk — deleting gigabytes is the user's own act."""
        removed = await asyncio.to_thread(_wikisink_config.remove_install, id)
        if removed is None:
            raise HTTPException(404, f"no install {id!r}")
        _wiki_zim.reset_archive()
        _broker.trace(project_dir, tool="wiki_install", decision="allowed",
                      args={"op": "forget", "id": id},
                      result_ok=True,
                      result_summary=f"file kept: {removed.get('filename')}")
        return {"ok": True, "file_kept": str(_wikisink_config.install_zim_path(removed))}

    @app.get("/api/wiki/article")
    async def api_wiki_article(
        path: str | None = Query(None), title: str | None = Query(None)
    ) -> dict[str, Any]:
        if not path and not title:
            raise HTTPException(400, "missing path or title")

        def _fetch() -> dict[str, Any]:
            art = _wiki_overlay.resolve_article(path=path, title=title)
            art["html"] = _wiki_zim.sanitize_and_rewrite(art["html"], art["path"])
            _wikisink_config.record_viewed(art["path"], art["title"])
            cfg = _wikisink_config.load_config()
            art["snapshot"] = (cfg.get("zim") or {}).get("snapshot")
            art["overridden"] = _wikisink_config.is_overridden(art["path"], cfg)
            return art

        try:
            return await asyncio.to_thread(_fetch)
        except KeyError:
            raise HTTPException(404, f"no article for {path or title!r} in the local archive") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @app.get("/api/wiki/search")
    async def api_wiki_search(
        q: str = Query(...), offset: int = Query(0, ge=0), n: int = Query(20, ge=1, le=50)
    ) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_wiki_zim.search, q, offset, n)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @app.get("/api/wiki/suggest")
    async def api_wiki_suggest(
        q: str = Query(...), n: int = Query(10, ge=1, le=25)
    ) -> dict[str, Any]:
        try:
            return {"results": await asyncio.to_thread(_wiki_zim.suggest, q, n)}
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    @app.get("/api/wiki/random")
    async def api_wiki_random() -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_wiki_zim.random_article)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None

    from .wikisink import comments as _wiki_comments

    @app.get("/api/wiki/comments")
    async def api_wiki_comments_get(path: str = Query(...)) -> dict[str, Any]:
        return await asyncio.to_thread(_wiki_comments.load_comments, path)

    @app.post("/api/wiki/comments")
    async def api_wiki_comments_post(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        text = (body.get("body") or "").strip()
        if not path or not text:
            raise HTTPException(400, "missing path or body")
        entry = await asyncio.to_thread(
            _wiki_comments.add_comment, path,
            (body.get("title") or "").strip(), text, body.get("anchor"))
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "add", "id": entry["id"]},
                      result_ok=True, result_summary=text[:120])
        return entry

    @app.patch("/api/wiki/comments")
    async def api_wiki_comments_patch(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        cid = (body.get("id") or "").strip()
        try:
            entry = await asyncio.to_thread(
                _wiki_comments.update_comment, path, cid,
                body=body.get("body"), resolved=body.get("resolved"),
                state=body.get("state"))
        except KeyError:
            raise HTTPException(404, f"no comment {cid!r}") from None
        # State reconciliation (anchored/paragraph/orphaned) happens on
        # every render — journaling those would flood the log; only real
        # edits get traced.
        if body.get("body") is not None or body.get("resolved") is not None:
            _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                          args={"path": path, "op": "edit", "id": cid},
                          result_ok=True, result_summary="")
        return entry

    @app.post("/api/wiki/comments/reply")
    async def api_wiki_comments_reply(request: Request) -> dict[str, Any]:
        body = await request.json()
        path = (body.get("path") or "").strip()
        cid = (body.get("id") or "").strip()
        text = (body.get("body") or "").strip()
        if not text:
            raise HTTPException(400, "missing body")
        try:
            reply = await asyncio.to_thread(_wiki_comments.add_reply, path, cid, text)
        except KeyError:
            raise HTTPException(404, f"no comment {cid!r}") from None
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "reply", "id": cid},
                      result_ok=True, result_summary=text[:120])
        return reply

    @app.delete("/api/wiki/comments")
    async def api_wiki_comments_delete(
        path: str = Query(...), id: str = Query(...)
    ) -> dict[str, Any]:
        try:
            await asyncio.to_thread(_wiki_comments.delete_comment, path, id)
        except KeyError:
            raise HTTPException(404, f"no comment {id!r}") from None
        _broker.trace(project_dir, tool="wiki_comment", decision="allowed",
                      args={"path": path, "op": "delete", "id": id},
                      result_ok=True, result_summary="")
        return {"ok": True}

    @app.post("/api/wiki/save")
    async def api_wiki_save(request: Request) -> dict[str, Any]:
        from .wikisink import save as _wiki_save

        body = await request.json()
        path = (body.get("path") or "").strip()
        dest = (body.get("dest") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        try:
            result = await asyncio.to_thread(
                _wiki_save.save_article, project_dir, path, dest)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except KeyError:
            raise HTTPException(404, f"no article for {path!r}") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wiki_save", decision="allowed",
                      args={"path": path, "dest": dest},
                      result_ok=True, result_summary=result["saved_path"])
        return result

    @app.get("/api/wiki/saved")
    async def api_wiki_saved(file: str = Query(...)) -> dict[str, Any]:
        """A saved article folder, rendered for the reader. Serves the
        stored verbatim copy through the same sanitize pipeline as live
        browsing — works even when no archive is installed/reachable
        (that's much of the point of saving)."""
        from .wikisink import save as _wiki_save

        def _load() -> dict[str, Any]:
            art = _wiki_save.read_saved(project_dir, file)
            art["html"] = _wiki_zim.sanitize_and_rewrite(art["html"], art["path"])
            if art["path"]:
                _wikisink_config.record_viewed(art["path"], art["title"])
                cfg = _wikisink_config.load_config()
                art["overridden"] = _wikisink_config.is_overridden(art["path"], cfg)
            return art

        try:
            return await asyncio.to_thread(_load)
        except ValueError as e:
            raise HTTPException(404, str(e)) from None
        except OSError as e:
            raise HTTPException(500, f"couldn't read the saved article: {e}") from None

    @app.post("/api/wiki/unsave")
    async def api_wiki_unsave(request: Request) -> dict[str, Any]:
        """Delete a saved-article folder (user-initiated from the tree's
        trash affordance). Only the saved copy goes; the archive copy,
        comments, and overrides are untouched."""
        from .wikisink import save as _wiki_save

        body = await request.json()
        ref = (body.get("dir") or "").strip()
        if not ref:
            raise HTTPException(400, "missing dir")
        try:
            result = await asyncio.to_thread(_wiki_save.unsave_article, project_dir, ref)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except OSError as e:
            raise HTTPException(500, f"unsave failed: {e}") from None
        _broker.trace(project_dir, tool="wiki_save", decision="allowed",
                      args={"dir": ref, "op": "unsave"},
                      result_ok=True, result_summary=result["removed"])
        return result

    @app.get("/api/wiki/flavors")
    async def api_wiki_flavors(force: bool = Query(False)) -> dict[str, Any]:
        return await asyncio.to_thread(_wiki_download.list_flavors, force)

    @app.get("/api/wiki/diskspace")
    async def api_wiki_diskspace(dir: str = Query(...)) -> dict[str, Any]:
        """Free-space readout for the setup modal's storage-dir field.
        Walks up to the nearest existing ancestor so a not-yet-created
        default like ~/enough/wikisink still reports its volume."""
        p = Path(dir).expanduser()
        probe = p
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            free = shutil.disk_usage(probe).free
        except OSError as e:
            raise HTTPException(400, f"can't inspect {p}: {e}") from None
        return {"dir": str(p), "free_bytes": free,
                "free_human": _wiki_download.bytes_to_human(free)}

    @app.post("/api/wiki/setup")
    async def api_wiki_setup(request: Request) -> dict[str, Any]:
        body = await request.json()
        flavor = (body.get("flavor") or "").strip()
        storage_dir = (body.get("storage_dir") or "").strip() or None
        replace_id = (body.get("replace_id") or "").strip() or None
        listing = await asyncio.to_thread(_wiki_download.list_flavors)
        entry = next((f for f in listing["flavors"] if f["flavor"] == flavor), None)
        if entry is None:
            raise HTTPException(404, f"unknown flavor {flavor!r}")
        # Same file into the same place = the install that's already
        # registered; switching to it beats re-downloading 16-49 GB.
        target = str(Path(storage_dir or str(
            _wikisink_config.DEFAULT_STORAGE_DIR)).expanduser())
        dupe = _wikisink_config.get_install(
            _wikisink_config.install_id(target, entry["filename"]))
        if dupe is not None and not replace_id:
            raise HTTPException(409, (
                f"{entry['filename']} is already installed at {target} — "
                "switch to it in the installs list instead of downloading again."
                if _wikisink_config.install_available(dupe) else
                f"{entry['filename']} is already registered at {target} but "
                "unreachable — reattach that drive, or forget the install "
                "first if it's gone for good."))
        try:
            wiki_dl.start(flavor=entry["flavor"], filename=entry["filename"],
                          url=entry["url"], size_bytes=entry["size_bytes"],
                          snapshot=entry["date"], storage_dir=storage_dir,
                          replace_id=replace_id)
        except _wiki_download.DownloadError as e:
            code = 409 if "already running" in str(e) else 400
            raise HTTPException(code, str(e)) from None
        await session.emit("system", {
            "kind": "wikisink_setup",
            "message": (
                f"wikisink: downloading {entry['label']} "
                f"({entry['size_human']}, snapshot {entry['date']}) from "
                "download.kiwix.org. this can take a while — it's resumable, "
                "survives restarts, and the 🚰 button shows progress. "
                "everything else keeps working meanwhile."
            ),
        })
        return {"started": True, "filename": entry["filename"],
                "size_bytes": entry["size_bytes"]}

    @app.get("/api/wiki/overrides")
    async def api_wiki_overrides_get() -> dict[str, Any]:
        cfg = _wikisink_config.load_config()
        return {"overrides": cfg.get("overrides", [])}

    @app.post("/api/wiki/override")
    async def api_wiki_override_post(request: Request) -> dict[str, Any]:
        """Deletion override: preserve this article's local copy forever
        and stop trying to update it. User-initiated only (the agent has
        deliberately no tool for this)."""
        body = await request.json()
        path = (body.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        try:
            entry = await asyncio.to_thread(
                _wiki_overlay.preserve, path, body.get("title") or None,
                reason=(body.get("reason") or "").strip(),
                deletion_log_excerpt=(body.get("deletion_log_excerpt") or "").strip())
        except KeyError:
            raise HTTPException(404, f"no local copy of {path!r} to preserve") from None
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wiki_override", decision="allowed",
                      args={"path": path, "op": "preserve"},
                      result_ok=True, result_summary=entry["preserved_file"])
        return entry

    @app.delete("/api/wiki/override")
    async def api_wiki_override_delete(path: str = Query(...)) -> dict[str, Any]:
        removed = await asyncio.to_thread(_wikisink_config.remove_override, path)
        if removed is None:
            raise HTTPException(404, f"no override for {path!r}")
        # The preserved file stays on disk — deleting bytes is a separate,
        # user-confirmed act; un-overriding just resumes normal serving.
        _broker.trace(project_dir, tool="wiki_override", decision="allowed",
                      args={"path": path, "op": "remove"},
                      result_ok=True, result_summary="preserved file kept")
        return {"ok": True, "preserved_file_kept": removed.get("preserved_file")}

    @app.post("/api/wiki/wikisink")
    async def api_wiki_wikisink(request: Request) -> dict[str, Any]:
        """UI-triggered update run — same engine as the agent's wikisink
        tool. Progress streams over SSE `wiki_sink`; the report lands in
        chat as a copyable system message."""
        from .wikisink import update as _wiki_update

        body = await request.json() if int(request.headers.get("content-length") or 0) else {}
        scope = body.get("scope") if body.get("scope") in ("watched", "report-only") else "watched"
        try:
            report = await asyncio.to_thread(
                _wiki_update.run_wikisink, project_dir, scope)
        except _wiki_zim.WikisinkUnavailable as e:
            raise _wiki_503(e) from None
        _broker.trace(project_dir, tool="wikisink", decision="allowed",
                      args={"scope": scope, "trigger": "ui"},
                      result_ok=True, result_summary=f"report {len(report)} chars")
        await session.emit("system", {"kind": "wikisink_report", "message": report})
        return {"ok": True, "report": report}

    @app.post("/api/wiki/download/{action}")
    async def api_wiki_download_ctl(action: str) -> dict[str, Any]:
        try:
            if action == "pause":
                wiki_dl.pause()
            elif action == "resume":
                wiki_dl.resume()
            elif action == "cancel":
                wiki_dl.cancel()
            else:
                raise HTTPException(404, f"unknown action {action!r}")
        except _wiki_download.DownloadError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True, "action": action}

    # -----------------------------------------------------------------
    # cacheawl — the global file store. Backend for the (future) split-view
    # cachebox UI. Contract documented in docs/cacheawl-plan.md.
    # -----------------------------------------------------------------
    _ingest_tasks: set[asyncio.Task[Any]] = set()

    @app.get("/api/cacheawl/tree")
    async def api_cacheawl_tree() -> dict[str, Any]:
        """Project tree + every cachebox tree in one payload for the split
        view. Triggers a cheap reconcile per box first so manual file drops
        the backend didn't see are reflected."""
        from . import cacheawl as _cacheawl

        def _build() -> dict[str, Any]:
            _cacheawl.reconcile_all()
            boxes = []
            for summary in _cacheawl.list_cacheboxes():
                # A box can vanish (rename/delete race) or error between
                # the listing and its tree scan — skip it rather than
                # 500ing the whole two-pane view.
                try:
                    boxes.append(_cacheawl.cachebox_tree(summary["name"]))
                except (_cacheawl.CacheawlError, OSError):
                    log.warning("cacheawl tree: skipping box %r", summary["name"])
            return {
                "root": str(_cacheawl.root()),
                "project": build_file_tree(project_dir),
                "cacheboxes": boxes,
            }

        return await asyncio.to_thread(_build)

    @app.post("/api/cacheawl/create")
    async def api_cacheawl_create(request: Request) -> dict[str, Any]:
        from . import cacheawl as _cacheawl
        body = await request.json()
        name = (body.get("name") or "").strip()
        try:
            summary = await asyncio.to_thread(_cacheawl.create_cachebox, name)
        except _cacheawl.CacheawlError as e:
            raise HTTPException(400, str(e)) from None
        return summary

    @app.post("/api/cacheawl/rename")
    async def api_cacheawl_rename(request: Request) -> dict[str, Any]:
        from . import cacheawl as _cacheawl
        body = await request.json()
        name = (body.get("name") or "").strip()
        new_name = (body.get("new_name") or "").strip()
        try:
            return await asyncio.to_thread(_cacheawl.rename_cachebox, name, new_name)
        except _cacheawl.CacheawlError as e:
            raise HTTPException(400, str(e)) from None

    @app.post("/api/cacheawl/delete")
    async def api_cacheawl_delete(request: Request) -> dict[str, Any]:
        """Delete a cachebox and its contents. Requires an explicit
        {confirm: true} — the no-deletes-without-confirmation discipline."""
        from . import cacheawl as _cacheawl
        body = await request.json()
        name = (body.get("name") or "").strip()
        confirm = bool(body.get("confirm"))
        try:
            return await asyncio.to_thread(
                _cacheawl.delete_cachebox, name, confirm=confirm)
        except _cacheawl.CacheawlError as e:
            # A missing box is a 404; an unconfirmed delete is a 400.
            code = 404 if "no cachebox" in str(e) else 400
            raise HTTPException(code, str(e)) from None

    @app.post("/api/cacheawl/transfer")
    async def api_cacheawl_transfer(request: Request) -> dict[str, Any]:
        """Copy/move a file or folder between the project dir and a cachebox
        (either direction) or within/between cacheboxes. Body:
        {op, src:{root,box?,path}, dst:{root,box?,path}, overwrite?}."""
        from . import cacheawl as _cacheawl
        body = await request.json()
        op = (body.get("op") or "").strip()
        src = body.get("src") or {}
        dst = body.get("dst") or {}
        try:
            return await asyncio.to_thread(
                _cacheawl.transfer, project_dir, op=op,
                src_kind=(src.get("root") or "").strip(),
                src_box=(src.get("box") or None),
                src_path=(src.get("path") or ""),
                dst_kind=(dst.get("root") or "").strip(),
                dst_box=(dst.get("box") or None),
                dst_path=(dst.get("path") or ""),
                overwrite=bool(body.get("overwrite")),
            )
        except _cacheawl.CacheawlError as e:
            raise HTTPException(400, str(e)) from None

    @app.post("/api/cacheawl/ingest")
    async def api_cacheawl_ingest(request: Request) -> dict[str, Any]:
        """Start an ingest into a cachebox. Long-running work runs in the
        background; poll /api/cacheawl/ingest-status. Obvious input errors
        fail fast with a 400."""
        from . import cacheawl as _cacheawl
        body = await request.json()
        box = (body.get("box") or "").strip()
        source_type = (body.get("type") or "").strip().lower()
        value = (body.get("value") or "").strip()
        depth = body.get("depth", 1)
        all_flag = bool(body.get("all"))
        # Register the box (status 'ingesting') synchronously so a malformed
        # request 400s up front and ingest-status is pollable immediately —
        # no window where the box doesn't exist yet.
        try:
            origin = await asyncio.to_thread(
                _cacheawl.register_ingest, box=box, source_type=source_type,
                value=value, depth=depth, all_flag=all_flag)
        except _cacheawl.CacheawlError as e:
            raise HTTPException(400, str(e)) from None

        loop = asyncio.get_running_loop()

        def _run() -> None:
            try:
                _cacheawl.run_ingest(
                    project_dir, box=box, source_type=source_type,
                    value=value, depth=depth, all_flag=all_flag)
            except Exception:  # noqa: BLE001 — status file records the failure
                log.exception("cacheawl ingest failed for box %s", box)

        task = loop.create_task(asyncio.to_thread(_run))
        _ingest_tasks.add(task)
        task.add_done_callback(_ingest_tasks.discard)
        return {"box": box, "status": "ingesting", "origin": origin}

    @app.get("/api/cacheawl/ingest-status")
    async def api_cacheawl_ingest_status(box: str = Query(...)) -> dict[str, Any]:
        from . import cacheawl as _cacheawl
        try:
            _cacheawl._require_box(box)
        except _cacheawl.CacheawlError as e:
            raise HTTPException(404, str(e)) from None
        return await asyncio.to_thread(_cacheawl.ingest_status, box)

    @app.get("/api/cacheawl/mirror")
    async def api_cacheawl_mirror(
        box: str = Query(...), path: str = Query(""),
    ) -> dict[str, Any]:
        """Read-only mirror diagram for a cachebox (``path`` empty) or a
        subfolder within it (``path`` set). The box root returns the
        persisted ``_cachebox.merirmaid`` content (reconciled first so
        manual drops are reflected); a subfolder returns an **on-demand
        virtual mirror** generated from current contents and never written.
        Payload: ``{text, node_map, modality, subpath}`` — ``node_map`` maps
        each rendered node id to ``{path, is_dir}`` (path relative to the box
        root) so the viewer's shift-click menu can resolve nodes to disk."""
        from . import cacheawl as _cacheawl

        def _build() -> dict[str, Any]:
            subpath = (path or "").strip().strip("/")
            if not subpath:
                # Keep the persisted root mirror fresh (fingerprint check).
                _cacheawl.reconcile(box)
            text, node_map = _cacheawl.build_mirror(box, subpath)
            return {"text": text, "node_map": node_map,
                    "modality": "mirror", "subpath": subpath,
                    "box_path": str(_cacheawl.box_dir(box))}

        try:
            return await asyncio.to_thread(_build)
        except _cacheawl.CacheawlError as e:
            msg = str(e)
            code = 404 if ("no cachebox" in msg or "no such folder" in msg) else 400
            raise HTTPException(code, msg) from None

    @app.post("/api/file", response_class=HTMLResponse)
    async def api_file_write(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        content = form.get("content")
        if content is None:
            raise HTTPException(400, "missing content")
        if not path:
            raise HTTPException(400, "missing path")
        if _is_skill_file(path):
            raise HTTPException(
                403,
                "skill files are not editable from the project UI — "
                "edit globally at ~/enough/defaults/skills/",
            )
        if _is_role_file(path):
            raise HTTPException(
                403,
                "role files are not editable from the project UI — "
                "edit globally at ~/enough/defaults/roles/",
            )
        if path.endswith(".girraph"):
            # Same rule as the agent's write_file: girraphs change via
            # node-level ops only, so panel edits and agent edits can
            # interleave without clobbering. (Outside the harness, a
            # text editor can of course still edit the file directly —
            # files are the source of truth.)
            raise HTTPException(
                403,
                "girraph files are edited through the girraph panel "
                "(node ops), not whole-file writes",
            )
        target = _resolve_project_path(path)
        # Cachebox mirror guard: the same rule as the agent's write_file —
        # a modality:mirror file under ~/enough/cacheawl/ is backend-owned
        # and regenerated from the box contents, so whole-file edits are
        # refused (in-tree paths never reach cacheawl, but a symlink or an
        # allowlisted path could).
        from . import cacheawl as _cacheawl
        if (why := _cacheawl.mirror_write_denial(target)):
            raise HTTPException(403, why)
        if target.name == ".cachebox.json":
            # Box metadata is backend-owned like the mirror; a corrupted
            # sidecar breaks ingest-status and origin tracking.
            raise HTTPException(
                403, "cachebox metadata is backend-owned — not editable")
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Stash the previous contents so the user-side "undo last
        # edit" affordance (Phase 4b) can revert. Cheap; no-op when
        # the file doesn't exist yet.
        from . import tools as _tools
        _tools.stash_for_undo(target)
        target.write_text(str(content), encoding="utf-8")
        # Return the re-rendered preview fragment so the UI can swap it in.
        return await api_file(path=path)  # type: ignore[return-value]

    @app.post("/api/file/undo", response_class=HTMLResponse)
    async def api_file_undo(request: Request) -> HTMLResponse:
        """Restore a file from its `.<filename>.undo` sibling and
        delete the stash. Returns the re-rendered preview fragment so
        the UI can swap it in just like a save would. 404 when no
        undo is available — the UI uses that to grey out the button."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(path)
        from . import tools as _tools
        undo = _tools._undo_path(target)
        if not undo.is_file():
            raise HTTPException(404, "no undo stash for this path")
        try:
            prior = undo.read_bytes()
        except OSError as e:
            raise HTTPException(500, f"undo unreadable: {e}") from None
        try:
            target.write_bytes(prior)
        except OSError as e:
            raise HTTPException(500, f"could not restore: {e}") from None
        try:
            undo.unlink()
        except OSError:
            pass    # leaving a stale stash is harmless; just log via the warning above if needed
        return await api_file(path=path)  # type: ignore[return-value]

    @app.post("/api/file/dismiss-undo")
    async def api_file_dismiss_undo(request: Request) -> dict[str, Any]:
        """Drop the `.undo` stash without restoring — the user clicked
        "save" / "looks good", and we honor that by closing the door
        on undoing this edit later. Idempotent."""
        form = await request.form()
        path = (form.get("path") or "").strip()
        if not path:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(path)
        from . import tools as _tools
        undo = _tools._undo_path(target)
        removed = False
        if undo.is_file():
            try:
                undo.unlink()
                removed = True
            except OSError as e:
                raise HTTPException(500, f"could not dismiss: {e}") from None
        return {"path": path, "dismissed": removed}

    @app.post("/api/chat", response_class=HTMLResponse)
    async def api_chat(request: Request) -> HTMLResponse:
        form = await request.form()
        message = (form.get("message") or "").strip()
        if not message:
            return HTMLResponse("")
        # Fire-and-forget generation. The SSE stream delivers output.
        asyncio.create_task(_run_turn(session, message))
        # Return an HTML fragment htmx will swap into the conversation:
        # the user's message bubble + an empty assistant bubble the SSE will fill.
        return HTMLResponse(
            f'<div class="msg user"><div class="role">user</div>'
            f'<div class="body">{_escape_html(message)}</div></div>'
            f'<div class="msg assistant pending" id="current-response">'
            f'<div class="role">agent</div>'
            f'<div class="body"></div>'
            f'<div class="tool-indicators"></div>'
            f'</div>'
        )

    @app.get("/api/stream")
    async def api_stream(request: Request):
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        session.subscribers.append(q)

        async def event_gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield item
                    except asyncio.TimeoutError:
                        # Heartbeat so proxies don't close the connection.
                        yield {"event": "ping", "data": "{}"}
            finally:
                try:
                    session.subscribers.remove(q)
                except ValueError:
                    pass

        return EventSourceResponse(event_gen())

    @app.get("/api/reset", response_class=HTMLResponse)
    async def api_reset() -> HTMLResponse:
        session.history.clear()
        session.last_usage = {}
        # Echo a usage event so the gauge zeroes out without waiting for
        # the user to send their first post-reset turn.
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return HTMLResponse("")

    @app.get("/api/update-enough")
    async def api_update_enough() -> dict[str, Any]:
        """Pull in any missing default files (paradigms, policies,
        knowledge dirs) from ~/enough/defaults/ that this project's
        `rness/` is missing. Idempotent: safe to call when nothing's
        missing.

        Returns a JSON summary the JS slash-command handler renders
        inline as a system notice."""
        from .skeleton import apply_drift, detect_drift
        # Detect first so we have a "what changed" view independent of
        # the apply step. The two should match in normal flow.
        before = detect_drift(session.project_dir)
        applied = apply_drift(session.project_dir)
        return {
            "applied": [
                {"src": src, "dst": dst, "mode": mode}
                for (src, dst, mode) in applied
            ],
            "remaining": [
                {"src": src, "dst": dst, "mode": mode}
                for (src, dst, mode) in detect_drift(session.project_dir)
            ],
            "had_drift": bool(before),
        }

    @app.get("/api/broker", response_class=HTMLResponse)
    async def api_broker_toggles() -> HTMLResponse:
        """Render the broker pane's toggle list. Each row is a clickable
        button that POSTs to /api/broker/toggle and re-renders this same
        list via htmx. Grouped by tool so additions to the catalog stay
        readable as the list grows."""
        cfg = _broker.load_config()
        rows: list[str] = []
        last_group: str | None = None
        for t in _broker.TOGGLES:
            if t.group != last_group:
                heading = {
                    "general": "general",
                    "read_file": "read_file",
                    "write_file": "write_file",
                    "shell": "shell",
                    "fetch_url": "fetch_url",
                }.get(t.group, t.group)
                rows.append(
                    f'<div class="broker-group-head">{_escape_html(heading)}</div>'
                )
                last_group = t.group
            on = cfg.get(t.key, t.default)
            cls = "on" if on else "off"
            marker = "●" if on else "○"
            rows.append(
                f'<div class="broker-row {cls}" title="{_escape_html(t.description)}">'
                f'  <button class="broker-toggle" '
                f'    hx-post="/api/broker/toggle" '
                f'    hx-vals=\'{{"key": "{_escape_html(t.key)}"}}\' '
                f'    hx-target="#broker-toggles" hx-swap="innerHTML">'
                f'    {marker}'
                f'  </button>'
                f'  <div class="broker-meta">'
                f'    <div class="broker-label">{_escape_html(t.label)}</div>'
                f'    <div class="broker-desc">{_escape_html(t.description)}</div>'
                f'  </div>'
                f'</div>'
            )
        return HTMLResponse("".join(rows))

    @app.post("/api/broker/toggle", response_class=HTMLResponse)
    async def api_broker_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        key = (form.get("key") or "").strip()
        if not key:
            raise HTTPException(400, "missing key")
        valid = {t.key for t in _broker.TOGGLES}
        if key not in valid:
            raise HTTPException(400, f"unknown toggle: {key}")
        cfg = _broker.load_config()
        cfg[key] = not cfg.get(key, True)
        _broker.save_config(cfg)
        return await api_broker_toggles()  # type: ignore[return-value]

    @app.get("/api/broker/journal-path")
    async def api_broker_journal_path() -> dict[str, str]:
        """Return the relative path to today's broker journal, for the UI
        to open in the file preview pane. Creates the file (empty) if
        missing so the preview pane has something to load."""
        now = dt.datetime.now()
        rel = f"rness/knowledge/session-logs/{now:%Y-%m-%d}-broker.md"
        target = project_dir / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                f"# broker journal — {now:%Y-%m-%d}\n\n"
                "_(no broker activity logged yet today)_\n",
                encoding="utf-8",
            )
        return {"path": rel}

    @app.get("/api/usage")
    async def api_usage() -> dict[str, Any]:
        """Latest token-usage snapshot for the gauge. Used on modal open
        and on page load — SSE pushes keep it live during a session."""
        return {
            **session.last_usage,
            "ctx": _current_ctx_size(session),
        }

    @app.get("/api/orchestrator")
    async def api_orchestrator_get() -> dict[str, Any]:
        """Current auto-reset config (auto_reset bool + threshold_pct int)."""
        return _load_orchestrator_config()

    @app.post("/api/orchestrator")
    async def api_orchestrator_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        return _save_orchestrator_config(body or {})

    @app.get("/api/ui-config")
    async def api_ui_config_get() -> dict[str, Any]:
        return _read_ui_config()

    @app.post("/api/ui-config")
    async def api_ui_config_post(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cfg = _read_ui_config()
        cfg["current"] = _validate_current(cfg, body or {})
        _write_ui_config(cfg)
        return cfg

    # ---------------------- OpenRouter (OPRO-API) ------------------------
    # The fifth model slot. Gated by the `local_models_only` broker toggle
    # (default on); these endpoints work regardless of the toggle but the
    # UI only surfaces them when the toggle is off. The api key never
    # transits these endpoints in either direction except for the one-time
    # POST to /api/cloud/set-key — from there it lives in the OS keyring
    # and is accessed only by enough.cloud.

    @app.get("/api/cloud/status")
    async def api_cloud_status() -> dict[str, Any]:
        """Current OpenRouter status: enablement flag, model id, whether a
        key is present in the keyring, last verified result. NEVER returns
        the api key value itself."""
        from . import cloud as _cloud
        return _cloud.status_snapshot()

    @app.post("/api/cloud/set-key")
    async def api_cloud_set_key(request: Request) -> dict[str, Any]:
        """Store or update the OpenRouter api key in the OS keyring, then
        run a fresh health check. Body: {"api_key": "sk-or-..."}. The key
        is validated against the OpenRouter prefix format before storage.
        Returns {"status": status_snapshot, "health": health_check_result}
        so the wizard / settings UI can show both in one round-trip."""
        from . import cloud as _cloud
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        api_key = ((body or {}).get("api_key") or "").strip()
        if not api_key:
            raise HTTPException(400, "missing api_key")
        try:
            _cloud.set_api_key(api_key)
        except _cloud.CloudKeyringUnavailable as e:
            raise HTTPException(500, str(e)) from None
        except _cloud.CloudError as e:
            raise HTTPException(400, str(e)) from None
        health = _cloud.health_check()
        return {"status": _cloud.status_snapshot(), "health": health}

    @app.post("/api/cloud/clear-key")
    async def api_cloud_clear_key() -> dict[str, Any]:
        """Remove the OpenRouter api key from the OS keyring and reset
        the verified-state metadata. Idempotent — safe to call when no
        key is present. Returns the post-clear status snapshot."""
        from . import cloud as _cloud
        _cloud.clear_api_key()
        return _cloud.status_snapshot()

    @app.post("/api/cloud/health-check")
    async def api_cloud_health_check() -> dict[str, Any]:
        """Re-test the currently-stored api key against OpenRouter via the
        zero-cost `openrouter/free` auto-selector. Updates the on-disk
        last-verified metadata. Returns both the health result and the
        updated status snapshot."""
        from . import cloud as _cloud
        health = _cloud.health_check()
        return {"status": _cloud.status_snapshot(), "health": health}

    @app.post("/api/cloud/set-model")
    async def api_cloud_set_model(request: Request) -> dict[str, Any]:
        """Update which OpenRouter model id chat completions go to. Body:
        {"model_id": "openrouter/auto"} or any slug from openrouter.ai/models.
        No client-side validation — OpenRouter has hundreds of models and the
        canonical list changes; unrecognized ids fail at request time with a
        clear 404 message."""
        from . import cloud as _cloud
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        model_id = ((body or {}).get("model_id") or "").strip()
        if not model_id:
            raise HTTPException(400, "missing model_id")
        try:
            _cloud.set_model_id(model_id)
        except _cloud.CloudError as e:
            raise HTTPException(400, str(e)) from None
        return _cloud.status_snapshot()

    # ------------------------------------------------------------------
    # Models — the picker's view, the switch, and the in-app manager's
    # download/delete side. Download progress streams over the `model-dl`
    # SSE event; contract in docs/seven-models-plan.md §4.
    # ------------------------------------------------------------------

    from . import model_download as _model_download

    model_dl = _model_download.ModelDownloadManager(emit=session.emit)

    @app.get("/api/models")
    async def api_models() -> dict[str, Any]:
        """Registry + per-model installed/recommended view + total RAM +
        supervisor status + the download manager's snapshot. When the
        `local_models_only` broker toggle is off, also injects a virtual
        OPRO-API entry at the end of the model list so the modal renders it
        as a fifth slot. The OPRO-API entry carries `cloud: True` plus
        cloud-specific status fields so the frontend can render and dispatch
        it differently from local models."""
        from . import models as _models  # late import: avoid circular
        views = _models.all_models_view()
        payload: dict[str, Any] = {
            "total_ram_gb": _models.total_ram_gb(),
            "current": _models.load_state().get("current"),
            "models": views,
            "ctx_overrides": _models.load_state().get("ctx_overrides") or {},
            # Same shape as the `model-dl` event, so a page that loads
            # mid-download renders from this and then keeps up over SSE.
            "download": model_dl.state(views),
            # The installed llama.cpp b-release. Wave 3 addition: each entry
            # already carries `llama_cpp_min_release`, but that number means
            # nothing to the picker without what's actually on this machine to
            # compare it against — the model manager renders "needs llama.cpp
            # ≥ bNNNN" in place of the switch affordance off the pair. One
            # number for the whole payload rather than a per-model
            # `release_gate()` sentence, because release_gate() re-probes the
            # binary per call and seven subprocess spawns per picker open is
            # not worth a prettier string. Off-thread: it shells out to
            # `llama-server --version` (10 s timeout), and 0 means "no
            # llama.cpp on PATH", which gates every gated model — correctly.
            "llama_release": await asyncio.to_thread(_models.llama_release),
        }
        payload["supervisor"] = supervisor.status() if supervisor else {"mode": "off"}

        # Inject OPRO-API when cloud is unlocked. The model list is the
        # only frontend surface that needs to know about it; everything
        # else flows through /api/cloud/*.
        if not _broker.is_enabled("local_models_only"):
            from . import cloud as _cloud
            cloud_status = _cloud.status_snapshot()
            payload["models"] = list(payload["models"]) + [{
                "cute": "opro-api",
                "label": "OpenRouter (cloud)",
                "family": "cloud",
                # `installed` doubles as the "can switch to this" flag in
                # the UI — true only when a key is present AND the most
                # recent health check passed.
                "installed": bool(
                    cloud_status["key_present"]
                    and cloud_status["last_verified_ok"]
                ),
                "path": None,
                "disk_gb_approx": None,
                "ram_gb_recommended_min": None,
                "ctx_max": None,
                "ctx_recommended": None,
                # cloud-only fields the frontend uses for rendering
                "cloud": True,
                "cloud_model_id": cloud_status["model_id"],
                "cloud_key_present": cloud_status["key_present"],
                "cloud_healthy": cloud_status["last_verified_ok"],
                "cloud_last_verified_at": cloud_status["last_verified_at"],
                "cloud_last_error": cloud_status["last_error"],
            }]
        return payload

    @app.get("/api/llm-status")
    async def api_llm_status() -> dict[str, Any]:
        """Lightweight poll target for the UI: is llama-server alive, what
        model is loaded, ready-for-requests? When OPRO-API is the active
        model, the supervisor's local-llama state is irrelevant — what
        matters is whether the cloud key is healthy."""
        # Short-circuit: OPRO-API mode. Local llama-server may or may not
        # be running in the background; we report cloud-readiness instead.
        try:
            current = _models.load_state().get("current")
        except Exception:  # noqa: BLE001
            current = None
        if current == "opro-api":
            cloud_status = _cloud.status_snapshot()
            return {
                "mode": "cloud",
                "ready": bool(cloud_status["key_present"] and cloud_status["last_verified_ok"]),
                "cute": "opro-api",
                "ctx": None,
                "cloud_model_id": cloud_status["model_id"],
                "cloud_healthy": cloud_status["last_verified_ok"],
                "cloud_last_error": cloud_status["last_error"],
            }
        if supervisor is None:
            # Non-supervised mode: best-effort probe of /health.
            try:
                async with httpx.AsyncClient(timeout=2.0) as c:
                    r = await c.get(llm_url.rstrip("/") + "/health")
                return {"mode": "external", "ready": r.status_code == 200, "cute": None, "ctx": None}
            except httpx.HTTPError:
                return {"mode": "external", "ready": False, "cute": None, "ctx": None}
        return supervisor.status()

    @app.post("/api/model")
    async def api_model_switch(request: Request) -> dict[str, Any]:
        """Swap the loaded model and/or ctx. Body: {"cute": "g40-04",
        "ctx": 16384 (optional)}. Returns supervisor status; the UI
        should poll /api/llm-status for readiness.

        Special case for "opro-api" (the OpenRouter cloud slot): there's
        no llama-server to restart — we just persist the selection via
        `models.save_state` and return a synthetic status. The supervisor
        keeps running its existing local model in the background; the
        actual cloud-routing of chat completions lands when llm.py is
        extended in phase 3. For phase 2 the selection is recorded so the
        UI flow is testable end-to-end."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        cute = (body or {}).get("cute")
        ctx = (body or {}).get("ctx")
        if not cute:
            raise HTTPException(400, "missing 'cute' field")

        if cute == "opro-api":
            # gating: refuse if cloud is locked or the key isn't healthy.
            if _broker.is_enabled("local_models_only"):
                raise HTTPException(400, _broker.denial_local_models_only())
            from . import cloud as _cloud
            from . import models as _models  # late import: avoid circular
            status = _cloud.status_snapshot()
            if not status["key_present"]:
                raise HTTPException(400, _broker.denial_cloud_key_missing())
            if not status["last_verified_ok"]:
                raise HTTPException(
                    400,
                    _broker.denial_cloud_unhealthy(status["last_error"] or "unverified"),
                )
            # persist the selection. don't touch the supervisor — the
            # local llama-server keeps running for now. routing of chat
            # completions to OpenRouter is wired in phase 3.
            state = _models.load_state()
            state["current"] = "opro-api"
            _models.save_state(state)
            session.history.clear()
            session.last_usage = {}
            await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            return {
                "mode": "cloud",
                "ready": True,
                "cute": "opro-api",
                "cloud_model_id": status["model_id"],
                "note": (
                    "OPRO-API selected. agent routing to OpenRouter is "
                    "wired in the next update — until then, the model "
                    "badge reflects the selection but chat completions "
                    "still use the local model in the background."
                ),
            }

        if supervisor is None:
            raise HTTPException(
                400,
                "llama-server isn't supervised by this enough process — "
                "restart enough without --no-supervise to enable switching.",
            )
        try:
            await supervisor.switch(str(cute), int(ctx) if ctx is not None else None)
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from None
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"switch failed: {e}") from None
        # Also clear in-memory conversation history — new model = fresh brain.
        session.history.clear()
        session.last_usage = {}
        await session.emit("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return supervisor.status()

    @app.post("/api/models/download/{cute}")
    async def api_model_download(cute: str) -> dict[str, Any]:
        """Download a model's weights into ~/enough/weights: the main GGUF,
        then its MTP draft file automatically when the registry entry
        declares one. Returns `{"started": true, ...}` plus the opening
        progress snapshot; the rest arrives on the `model-dl` SSE event.

        Resumable — a `.part` file left by a cancel or a quit is continued
        with a ranged GET rather than re-fetched, across restarts. 404 for an
        unknown model, 409 when it's already installed or another download is
        running, 400 when the volume can't hold what's left."""
        try:
            snap = model_dl.start(cute)
        except KeyError:
            raise HTTPException(404, f"unknown model {cute!r}") from None
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None
        return {"started": True, **snap}

    @app.post("/api/models/download/{cute}/cancel")
    async def api_model_download_cancel(cute: str) -> dict[str, Any]:
        """Stop the running download and KEEP its partial file, so starting
        the same model again resumes from where it stopped. 409 when nothing
        is running, or when what's running is a different model. The stop
        itself lands at the next chunk boundary — the `model-dl` event with
        `status: "cancelled"` is what confirms it."""
        try:
            return model_dl.cancel(cute)
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None

    @app.post("/api/models/delete/{cute}")
    async def api_model_delete(cute: str) -> dict[str, Any]:
        """Remove a model's weights: main GGUF, MTP draft file, and any
        partial download. 404 for an unknown model or one with nothing on
        disk, 409 when it's the model currently in use (switch away first) or
        the one being downloaded (cancel first)."""
        try:
            return await asyncio.to_thread(model_dl.delete, cute)
        except KeyError:
            raise HTTPException(404, f"unknown model {cute!r}") from None
        except _model_download.ModelDownloadError as e:
            raise HTTPException(e.status, str(e)) from None

    @app.post("/api/transcribe")
    async def api_transcribe(request: Request) -> dict[str, Any]:
        """Speech-to-text via whisper.cpp. Accepts a multipart/form-data POST
        with an 'audio' field containing a 16 kHz mono WAV blob. Returns
        {"text": "transcribed words"} on success."""
        import shutil as _shutil
        import subprocess as _sp
        import tempfile as _tempfile

        whisper_bin = _shutil.which("whisper-cli")
        if not whisper_bin:
            from . import models as _m
            raise HTTPException(
                503,
                "whisper-cli not found on PATH. "
                + _m.install_hint(
                    mac="install it with `brew install whisper-cpp` or re-run bootstrap.sh.",
                    linux=(
                        "no distro packages whisper.cpp yet — build it from "
                        "https://github.com/ggml-org/whisper.cpp and put "
                        "`whisper-cli` on your PATH. Voice input is optional; "
                        "everything else works without it."
                    ),
                ),
            )
        model_path = WHISPER_DIR / WHISPER_DEFAULT_MODEL
        if not model_path.is_file():
            raise HTTPException(
                503,
                f"whisper model not found at {model_path}. re-run bootstrap.sh step 7 "
                "to download it.",
            )

        form = await request.form()
        blob = form.get("audio")
        if blob is None or not hasattr(blob, "read"):
            raise HTTPException(400, "missing 'audio' file part")
        data = await blob.read()
        if not data:
            raise HTTPException(400, "empty audio upload")

        # whisper-cli needs a file on disk. Temp-file the upload, pipe through,
        # discard.
        with _tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(data)
            in_path = Path(f.name)
        try:
            proc = await asyncio.to_thread(
                _sp.run,
                [
                    whisper_bin,
                    "-m", str(model_path),
                    "-f", str(in_path),
                    "-nt",              # no timestamps in output
                    "--no-prints",      # suppress progress spam
                    "-l", "en",         # English (matches base.en)
                    "--output-txt",     # write .txt next to the wav
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise HTTPException(
                    500,
                    f"whisper-cli failed (code {proc.returncode}): "
                    f"{proc.stderr[-400:] if proc.stderr else 'no stderr'}",
                )
            # whisper-cli writes <basename>.wav.txt alongside the input.
            txt_path = in_path.with_suffix(".wav.txt")
            if txt_path.is_file():
                text = txt_path.read_text(encoding="utf-8").strip()
                txt_path.unlink(missing_ok=True)
            else:
                # Fallback: some builds print to stdout.
                text = (proc.stdout or "").strip()
            return {"text": text}
        finally:
            in_path.unlink(missing_ok=True)

    @app.post("/api/shutdown")
    async def api_shutdown(request: Request) -> dict[str, Any]:
        """Graceful stop — the desktop shell's quit path.

        Gated on ENOUGH_DESKTOP=1 (404 otherwise) plus, when the shell set
        one, a matching ENOUGH_DESKTOP_TOKEN in the X-Enough-Desktop-Token
        header (403 otherwise). See the DESKTOP_ENV block above for why.

        Order matters: stop the llama-server *first* with
        `only_if_owned=True` so an adopted one survives — quitting the app
        must behave exactly like ctrl-c'ing the CLI — then ask uvicorn to
        exit. The lifespan teardown repeats the stop; it's idempotent.
        """
        if os.environ.get(DESKTOP_ENV) != "1":
            raise HTTPException(404, "Not Found")
        token = os.environ.get(DESKTOP_TOKEN_ENV) or ""
        if token and request.headers.get(DESKTOP_TOKEN_HEADER) != token:
            raise HTTPException(403, "bad desktop token")
        if supervisor is not None:
            try:
                await supervisor.stop(only_if_owned=True)
            except Exception:  # noqa: BLE001 — never block the quit path
                log.exception("supervisor stop during /api/shutdown failed")
        request_process_exit()
        log.info("shutdown requested by the desktop shell")
        return {"ok": True, "stopping": True}

    @app.get("/favicon.ico")
    async def favicon():
        f = STATIC_DIR / "favicon.ico"
        if f.exists():
            return FileResponse(f)
        return HTMLResponse("", status_code=204)

    return app


def run(
    *,
    project_dir: Path,
    port: int,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    supervise: bool = True,
) -> None:
    app = create_app(project_dir, llm_url, max_tool_iters=max_tool_iters, supervise=supervise)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
