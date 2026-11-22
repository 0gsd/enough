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
import signal
# Not read here since 0.8 (the routes that run programs live in enough/routes/), but tests reach
# `subprocess.Popen` through this module.
import subprocess  # noqa: F401
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import agent_free as _agent_free
from .wikisink import config as _wikisink_config
from .llm import LLMError, stream_chat
from . import cloud as _cloud
from . import canon as _canon
from . import retired_names as _retired_names
from . import convert as _convert
from . import specs as _specs
from . import home as _home
from . import models as _models
from . import paginate as _paginate
from . import intro as _intro
from . import pal_tools as _pal
from . import preflight as _preflight
from .logger import ExchangeLog, log_exchange
from . import prompt as prompt_mod
from .prompt import assemble_system_prompt
from .supervisor import LlamaSupervisor
from .tools import (
    ToolCall,
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
    mirroring the ENOUGH_WIKISINK_CONFIG / ENOUGH_CANON_ROOT precedent) so
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


# The exit status this process should leave behind, and the live uvicorn
# Server that `run()` is driving. Both exist for the home handoff (home-plan
# §1.7): the desktop shell distinguishes **exit code 42** ("I wrote
# .home-open — open what it names, or home if it's absent") from every other
# exit, which keeps today's behavior.
_EXIT_CODE: dict[str, int] = {}
_UVICORN: dict[str, Any] = {}


def request_process_exit(delay: float = 0.25, code: int | None = None) -> None:
    """Ask this uvicorn process to exit shortly after the current response.

    With no `code`, SIGTERM to ourselves is uvicorn's own graceful-shutdown
    path: it drains connections and runs the lifespan teardown, which is what
    stops an *owned* llama-server and closes the httpx client. The small delay
    lets the shutdown response actually reach the shell first.

    With a `code`, SIGTERM is no good: uvicorn's `capture_signals` re-raises
    the captured signal once it has shut down, so the process dies *by the
    signal* and there is no exit status left to set. Instead we set
    `Server.should_exit` directly — the same graceful path, minus the signal
    (sse-starlette watches that flag too, so open SSE streams still drain) —
    and `run()` returns the code afterwards.

    Module-level (rather than inline in the handler) so tests can swap it
    out — the real thing would take the test runner down with it.
    """
    loop = asyncio.get_running_loop()
    if code is None:
        loop.call_later(delay, lambda: os.kill(os.getpid(), signal.SIGTERM))
        return
    _EXIT_CODE["code"] = code
    server = _UVICORN.get("server")
    if server is None:
        # No `run()` around us (a TestClient, say) — fall back to the signal
        # so the process still stops; the code is simply not observable.
        loop.call_later(delay, lambda: os.kill(os.getpid(), signal.SIGTERM))
        return
    loop.call_later(delay, lambda: setattr(server, "should_exit", True))


# What a home handoff exits with. Any other status keeps today's meaning, so
# the shell's existing "the backend died" handling is untouched.
HANDOFF_EXIT_CODE = 42


def request_process_exec(argv: list[str], delay: float = 0.25) -> None:
    """Replace this process with `argv` shortly after the current response.

    The CLI half of the home handoff (home-plan §1.7): the browser tab stays
    open on the same port and reconnects once the new server binds, with the
    loader page in between — the update flow's restart pattern. `execv`
    rather than spawn-and-exit so the port is never held by two processes and
    the shell (if any) still has exactly one child.

    Module-level for the same reason as `request_process_exit`: a test that
    ran the real thing would replace the test runner.
    """
    loop = asyncio.get_running_loop()

    def _go() -> None:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except (OSError, ValueError):
            pass
        os.execv(argv[0], argv)

    loop.call_later(delay, _go)


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
    # picker, skills toggle, readvisors toggle) — hidden here to avoid
    # duplicating UI affordances. Both readvisor folder names are listed:
    # the 0.3.5 rename fails soft, so a project on a read-only parent can
    # still be sitting on `rness/roles/` and shouldn't suddenly sprout a
    # duplicate tree section for it.
    "rness/paradigms",
    # The texts for two or three paradigms on together (0.8): chosen for
    # the person by the paradigm picker's toggles, never picked directly.
    "rness/metaparadigms",
    "rness/readvisors",
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


# The virtual path prefix that addresses the Canon store instead of the
# project: `canon:<volume>/<rel>` (0.4.3; the pre-0.4.3 `cacheawl:` spelling
# was removed in 0.6).
STORE_PREFIXES: tuple[str, ...] = ("canon:",)


def _store_prefix(path: str) -> str | None:
    """The Canon prefix ``path`` starts with, or None for a project path."""
    for prefix in STORE_PREFIXES:
        if path.startswith(prefix):
            return prefix
    return None


def _readvisor_origin(project_dir: Path, name: str) -> str:
    """Where a readvisor visible in this project actually lives:
    `"project"`, `"global"` or `"shipped"` (P7).

    The sidebar needs it to decide whether to offer a remove control, and
    the remove endpoint needs it to decide what to delete. Read from the
    filesystem rather than recorded anywhere, because the filesystem is the
    record: a real directory is this project's, a link into
    `~/enough/readvisors/` is the user's own global one, and anything else
    resolves into an install's `defaults/` and is ours. An unreadable or
    missing entry reads as `shipped`, the one origin with no destructive
    affordance attached."""
    from . import prompt as _prompt
    from . import skeleton as _skeleton
    entry = _prompt._readvisors_dir(project_dir / "rness") / name
    try:
        if not entry.is_symlink():
            return "project" if entry.is_dir() else "shipped"
        target = entry.resolve(strict=False)
        user_root = _skeleton.user_readvisors_root().resolve(strict=False)
        if target.parent == user_root:
            return "global"
    except OSError:
        return "shipped"
    return "shipped"


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
    # True for exactly as long as a `/pal` turn is running (P8). Set and
    # cleared by `pal_tools.pal_turn()`, never by hand: it is what stands
    # between "the user asked for one outside opinion" and "the model may
    # send whatever it likes off this machine".
    pal_turn: bool = False
    # The context-window preflight (0.4.3): does enough's default system
    # prompt fit the live window? `preflight.Preflight`; None in home mode.
    preflight: Any = None

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
    volume in Canon) are user-visible files. Resolved fresh per tree build:
    cheap (one tiny JSON read) and always honors just-changed locations."""
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
    # A text's twins (`notes.md.fabulan.cosm`, `.fabulap.cosm`, or the old
    # `notes.md.cosm`, declaring `oes: fabula/1` or `emf/1`) hide behind their
    # texts, which carry `emf: {path, state, flavour, others?}` (the wire name
    # is kept) — the same one-row-per-document rule as convert twins
    # (canon-043 plan §6.3). An old twin a flavour-named one superseded is an
    # ordinary row with `old_twin: {of, twin}`.
    emf_found = _canon.fabula_twins(entries)
    emf_hidden = emf_found.hidden
    out: list[dict[str, Any]] = []
    for p in entries:
        if p.name.startswith("."):
            continue
        if p.name in IGNORE_DIRS:
            continue
        rel = "/".join(rel_parts + (p.name,))
        if rel in HIDDEN_TREE_PATHS:
            continue
        if p.name in emf_hidden:
            continue
        if wikisink_real and p.is_dir():
            try:
                if p.resolve() in wikisink_real:
                    continue
            except OSError:
                pass
        # A converted document renders as ONE row — the original — so the
        # twin and its assets folder are hidden. `has_twin` insists on the
        # manifest as well as the twin, which is what keeps a `notes.pdf.md`
        # somebody wrote by hand from vanishing out of their tree.
        if p.is_dir() and p.name.endswith(".assets"):
            if _convert.has_twin(p.parent / p.name[: -len(".assets")]):
                continue
        elif not p.is_dir() and p.name.endswith(".md"):
            if _convert.has_twin(p.parent / p.name[: -len(".md")]):
                continue
        # Same rule for a paginated PDF: the artifact is the PDF, so its
        # viewer pages are hidden (the `.…paginate.json` manifest beside
        # them is a dotfile and never made it this far). `is_pages_dir`
        # insists on the manifest for the same reason `has_twin` insists on
        # its own — somebody's folder named `notes.pdf.pages` is theirs.
        if p.is_dir() and _paginate.is_pages_dir(p):
            continue
        node = {
            "name": p.name,
            "path": rel,
            "is_dir": p.is_dir(),
            "is_symlink": p.is_symlink(),
        }
        # A Thym package (0.5.0, THYM.md 15.1) is kept whole: its folder form
        # `<stem>.thym/` is one row with no children (never opened up as loose
        # texts), its single file `<stem>.package.cosm` and its sealed form
        # `<stem>.thym.enc` carry their kind, so the page draws them as Canon's
        # listing does and routes a click to the package card.
        if p.is_dir() and _canon.is_package_folder(p):
            node["kind"] = "package"
            node["children"] = []
            out.append(node)
            continue
        if not p.is_dir() and _canon.is_sealed_package(p):
            node["kind"] = "sealed"
        elif not p.is_dir() and _canon.is_package_file(p):
            node["kind"] = "package"
        if p.is_dir():
            # Saved wikisink articles are folders shaped {article.html,
            # _manifest.md, .meta.json}; the tree marks them so the UI
            # can route clicks into the reader and offer unsave.
            try:
                if (p / "article.html").is_file() and (p / ".meta.json").is_file():
                    node["wiki_saved"] = True
            except OSError:
                pass
            # A Comprise Holotype: flagged so the UI can badge it and open it
            # in the cosm viewer; the sidebar still shows its files.
            if _canon.is_holotype_folder(p):
                node["holotype"] = True
            # 0.8 (fabulac-first, the twin guard): the folder an authored fabulac entailed; the page offers to
            # entail it again and run it, never to build a fabulac of it.
            twin = p.with_name(p.name + _FABULAC_SUFFIX)
            if twin.is_file() and not twin.is_symlink() and _fabulac_authored(twin):
                node["fabulac_twin"] = "/".join(rel_parts + (twin.name,))
            node["children"] = _walk_tree(root, rel_parts + (p.name,), visited, wikisink_real)
            # 0.9: a folder that holds Lean, here or below (its card builds a fabulam), read from the walk itself.
            if any((c.get("is_dir") and c.get("lean")) or (not c.get("is_dir") and str(c.get("name", "")).endswith(
                    ".lean")) for c in node["children"]):
                node["lean"] = True
        elif p.name == "article.html":
            try:
                if (p.parent / ".meta.json").is_file():
                    node["wiki_article"] = True
            except OSError:
                pass
        elif p.suffix == ".comp":
            # A composure opens in the base layer, not in read/edit mode —
            # the tree marks it so the click routes there. Its comments
            # sidecar is a dotfile and never reached this far.
            node["composure"] = True
        elif _convert.is_convertible(p):
            # Both the converted and the not-yet-converted case: the tree
            # draws a badge from `convert_state` and routes the click into
            # the twin (or the intro modal) instead of the binary preview.
            try:
                st = _convert.state(p)
            except (OSError, _convert.ConvertError):
                st = None
            if st:
                node["convertible"] = True
                node["convert_state"] = st
                if st in ("fresh", "edited", "stale", "conflict"):
                    node["converted"] = True
                    node["twin"] = f"{rel}.md"
            # A PDF enough paginated with "bring it in": the click opens the
            # paged viewer instead of the blob preview, and the manifest names
            # its SVG pages.
            man = _paginate.read_viewer_manifest(p)
            if man:
                node["paginated"] = "/".join(
                    rel_parts + (_paginate.viewer_manifest_path(p).name,))
                node["pages"] = man.get("pages", 0)
        elif _convert.is_image(p):
            node["image"] = True        # opens in the viewer, not the preview
        if not p.is_dir():
            # The project's catalog (kept by enough, write-refused) and any
            # other .cosm file (opens in the cosm viewer).
            if rel == _canon.PROJECT_CATALOG:
                node["catalog"] = True
            elif p.suffix == ".cosm":
                node["cosm"] = True
                # 0.8: a fabulac the person authored (its card entails and runs it)
                if p.name.endswith(_FABULAC_SUFFIX) and not p.is_symlink() and _fabulac_authored(p):
                    node["fabulac_authored"] = True
            entry = _canon.listing_entry(p, "/".join(rel_parts), emf_found)
            if entry is not None:
                node["emf"] = entry
            old_twin = _canon.superseded_entry(p.name, "/".join(rel_parts), emf_found)
            if old_twin is not None:
                node["old_twin"] = old_twin
        out.append(node)
    return out


_FABULAC_SUFFIX = ".fabulac.cosm"
#: Whether a fabulac is authored, by path, kept while its size and time stay (the tree is drawn every 3 s).
_AUTHORED_SEEN: dict[str, tuple[int, int, bool]] = {}


def _fabulac_authored(p: Path) -> bool:
    """Whether the fabulac at `p` is authored (its `source.kind`, MacroCOSM OES 18.4.1), read once per change."""
    try:
        st = p.stat()
    except OSError:
        return False
    key = str(p)
    seen = _AUTHORED_SEEN.get(key)
    if seen is not None and seen[:2] == (st.st_mtime_ns, st.st_size):
        return seen[2]
    from . import fabulac_job as _fj
    src = _fj._load(p).get("source")
    got = isinstance(src, dict) and src.get("kind") == "authored"
    if len(_AUTHORED_SEEN) > 4096:
        _AUTHORED_SEEN.clear()
    _AUTHORED_SEEN[key] = (st.st_mtime_ns, st.st_size, got)
    return got


def _hidden_global_dirs() -> frozenset[Path]:
    """Resolved global dirs that must never render in a project's file tree:
    the wikisink storage/data dirs plus the Canon store root (and the old
    `~/enough/cacheawl/`, should it still sit beside a migrated store). Canon
    is a global store (like wikisink) accessed through its own UI/tools, not
    a per-project artifact — hide it the same way, in case a project ever
    symlinks to or sits near it."""
    dirs = set(_wikisink_storage_real())
    try:
        for r in (_canon.root(), Path.home() / "enough" / "cacheawl"):
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
        # `_HELP_IDS` is path-keyed, but a converted document's help bubble
        # belongs to its state, not its name — any converted row gets it.
        if not help_id and n.get("converted"):
            help_id = "converted-file"
        help_attr = f' data-help="{help_id}"' if help_id else ""
        # Convert-mode data attributes, read by the tree's click routing and
        # the badge CSS (frontend wave). `data-convert-state` is one of
        # convert.STATES; `data-twin` is the markdown file the click opens.
        conv_attr = ""
        if n.get("convertible"):
            conv_attr = (f' data-convertible="1"'
                         f' data-convert-state="{n.get("convert_state", "")}"')
            if n.get("converted"):
                twin_attr = str(n.get("twin", "")).replace('"', "&quot;")
                conv_attr += f' data-converted="1" data-twin="{twin_attr}"'
        elif n.get("image"):
            conv_attr = ' data-image="1"'
        if n.get("paginated"):
            # A PDF enough paginated with its pages brought in: the click
            # opens the paged viewer, and `data-paginated` is the manifest
            # that names them.
            man_attr = str(n["paginated"]).replace('"', "&quot;")
            conv_attr += (f' data-paginated="{man_attr}"'
                          f' data-pages="{n.get("pages", 0)}"')
        # Canon flags (0.4.3): the project catalog, any other .cosm, and a
        # text's EMF twin (hidden from the tree, named here with its state).
        if n.get("catalog"):
            conv_attr += ' data-catalog="1"'
        elif n.get("cosm"):
            conv_attr += ' data-cosm="1"'
        if isinstance(n.get("emf"), dict):
            emf_path = str(n["emf"].get("path", "")).replace('"', "&quot;")
            conv_attr += (f' data-emf="{emf_path}"'
                          f' data-emf-state="{n["emf"].get("state", "")}"')
        if n.get("fabulac_authored"):
            conv_attr += ' data-fab-authored="1"'
        if isinstance(n.get("old_twin"), dict):
            # An old-named twin kept beside the flavour-named one that superseded
            # it (0.6, S2): the row says which twin replaced it and of which text.
            new_twin = str(n["old_twin"].get("twin", "")).replace('"', "&quot;")
            of_text = str(n["old_twin"].get("of", "")).replace('"', "&quot;")
            conv_attr += f' data-old-twin="{new_twin}" data-old-twin-of="{of_text}"'

        # `data-path` + `data-name` on the row's <li> are read by the
        # tree context menu (option-click) so the JS can identify the
        # target without parsing the inner DOM. Folder rows already
        # need `data-path` for other reasons; file rows pick it up here.
        if n["is_dir"]:
            has_kids = bool(n.get("children"))
            dir_state_cls = " has-children" if has_kids else " empty-folder"
            saved_attr = ' data-wiki-saved="1"' if n.get("wiki_saved") else ""
            if n.get("holotype"):
                saved_attr += ' data-holotype="1"'
            if n.get("fabulac_twin"):
                twin_rel = str(n["fabulac_twin"]).replace('"', "&quot;")
                saved_attr += f' data-fab-twin="{twin_rel}"'
            if n.get("lean"):
                saved_attr += ' data-lean="1"'
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
                f'data-path="{path}" data-name="{name_attr}" data-kind="file"{conv_attr}>'
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


def _render_pal_bubbles(tool_result: str) -> list[str]:
    """The two bubbles a pal exchange leaves behind, rebuilt from the
    `ask_pal` tool result sitting in the history.

    Same shape, same order and the same class names the live
    `pal_exchange` SSE event asks the frontend for (P8): the sent prompt
    first, under `→ pal · <model id>`, then the reply under
    `pal · <model id>`. Anything that is not a pal result renders as
    nothing, exactly as every other tool result does."""
    body = tool_result.strip()
    if not body.startswith('<tool_result name="ask_pal"'):
        return []
    _, _, rest = body.partition("\n")
    inner = rest.rsplit("</tool_result>", 1)[0]
    parsed = _pal.parse_result_body(inner.strip())
    if parsed is None:
        return []
    model = _escape_html(parsed["model_id"])
    return [
        f'<div class="msg pal-sent"><div class="role">'
        f'{_escape_html(_pal.RESULT_HEADER)}{model}</div>'
        f'<div class="body">{_escape_html(parsed["prompt"])}</div></div>',
        f'<div class="msg pal"><div class="role">pal · {model}</div>'
        f'<div class="body">{_escape_html(parsed["reply"])}</div></div>',
    ]


def _render_turn_from_history(history: list[dict[str, str]]) -> str:
    """Render the saved history as HTML for initial page load.

    The assistant byline is the chief readvisor's CURRENT name, not whatever
    it was when the turn was spoken. That is the deliberate choice: the name
    is what the user calls this readvisor, and a history where a rename
    makes the same voice answer under two names would read as two people."""
    speaker = _escape_html(prompt_mod.chief_name())
    out: list[str] = []
    for msg in history:
        role = msg.get("role")
        text = msg.get("content", "") or ""
        if role == "user":
            # Strip tool_result wrappers for display — except a pal's, which
            # is the one tool result that is not plumbing. What left this
            # machine and what came back are shown live, and a reload that
            # quietly dropped them would make the record depend on whether
            # the user had refreshed the page.
            # `show_intro`'s result likewise stands for the intro bubble.
            if text.lstrip().startswith("<tool_result"):
                out.extend(_render_pal_bubbles(text))
                out.extend(_intro.render_tool_result(text))
                continue
            out.append(f'<div class="msg user"><div class="role">user</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
        elif role == "assistant":
            if _intro.is_intro_text(text):
                # Answered without a model call (`/api/chat`'s intro match):
                # drawn as the same markdown bubble it was live.
                out.append(_intro.bubble(text.strip(), prompt_mod.chief_name()))
                continue
            out.append(f'<div class="msg assistant"><div class="role">{speaker}</div>'
                       f'<div class="body">{_escape_html(text)}</div></div>')
    return "".join(out)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _user_bubble(text: str) -> str:
    """The user's own message, as `/api/chat` hands it back for htmx to swap
    in. What they typed, not what was sent — a `/pal` turn strips the token
    on the way to the model and the conversation should still show it."""
    return (f'<div class="msg user"><div class="role">user</div>'
            f'<div class="body">{_escape_html(text)}</div></div>')


async def _reply_without_turn(session: "Session", html: str) -> HTMLResponse:
    """A `/api/chat` answer that starts no model turn (a refusal, a usage
    hint, the intro). The composer disables itself when the form posts and
    re-enables only on the `done` event a turn ends with, so a reply with no
    turn has to send one itself — unless a chat turn really is running, whose
    own `done` is the one that counts. (A council holds the same lock but
    never sends `done`, so it does not count.)"""
    from . import council as _council
    if not session.generation_lock.locked() or _council.turn_in_flight():
        await session.emit("done", {})
    return HTMLResponse(html)


def _system_bubble(text: str) -> str:
    """enough speaking for itself: a refusal, a usage hint, a note about
    what just happened to the message. Never a readvisor's voice."""
    return (f'<div class="msg system"><div class="role">enough</div>'
            f'<div class="body">{_escape_html(text)}</div></div>')


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

def _default_empty_hint() -> str:
    """The plain, neutral hint (0.4.1: the "say hi, or ask what they can do"
    line went). The chat adds its own "a brief introduction to enough"
    affordance inside `#empty-hint`, which sends `/intro` through the chat."""
    return '<div class="empty-hint" id="empty-hint">awaiting your first message.</div>'


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

    return _default_empty_hint()


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


# The UI languages that ship translated chrome + help content (i18n
# round). Keys are the folder names under enough/static/i18n/; "en" is
# the source language baked into index.html and docs/HELP_CENTER.md, so
# it has no folder of its own (only the canonical string catalog).
# docs/I18N.md documents the update process across all of them.
UI_LANGUAGES: frozenset[str] = frozenset({"en", "fr", "es", "de", "zh", "ja"})


def _ui_language(cfg: dict[str, Any] | None = None) -> str:
    """The validated UI language from the live config; absent/unknown ⇒ en."""
    lang = (cfg if cfg is not None else _read_ui_config()).get("ui_language")
    return lang if isinstance(lang, str) and lang in UI_LANGUAGES else "en"


def _read_ui_config() -> dict[str, Any]:
    path = _ensure_live_ui_config()
    try:
        cfg = _merge_shipped_theme_keys(json.loads(path.read_text(encoding="utf-8")))
        # Agent-free mode (0.4.4): the read view always says what the switch
        # IS — false for a file that predates it (or holds anything but a
        # literal true), exactly as `agent_free.enabled()` reads it.
        if isinstance(cfg, dict):
            cfg[_agent_free.KEY] = _agent_free.value(cfg)
        return cfg
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
        # `speaker` is the chief readvisor's name: the live bubble gets the
        # byline the server-rendered ones already carry, without the frontend
        # having to hold a copy of the name and keep it fresh across renames.
        await session.emit("turn_start", {"speaker": prompt_mod.chief_name()})
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


async def _first_turn_overflow(session: Session, system_prompt: str,
                               detail: str) -> str | None:
    """The overflow advice for a first turn — or for any turn whose
    instructions alone leave no room — else None (the caller keeps the
    later-turn "things to try"). A first turn is one with no assistant
    reply in the history yet: failed earlier attempts leave only user
    messages behind. The numbers are exact when llama-server can tokenize
    (one quick /tokenize), else ~chars/3.7; the window comes from the 400
    itself, then the preflight, then the supervisor."""
    first_turn = not any(m.get("role") == "assistant" for m in session.history)
    cached = session.preflight.fields() if session.preflight is not None else {}
    n_ctx = (_preflight.n_ctx_from_error(detail) or cached.get("n_ctx")
             or _current_ctx_size(session))
    tokens: int | None = None
    if session.client is not None:
        try:
            tokens = await _preflight.count_tokens(
                session.client, session.llm_url, system_prompt, timeout=5.0)
        except Exception:  # noqa: BLE001 — fall back to the estimate
            tokens = None
    estimated = tokens is None
    if tokens is None:
        tokens = int(len(system_prompt or "") / 3.7)
    alone = bool(n_ctx) and tokens + _preflight.RESERVE > int(n_ctx)
    if not (first_turn or alone):
        return None
    return _preflight.first_turn_advice(tokens, int(n_ctx) if n_ctx else None,
                                        estimated=estimated)


async def _run_turn(
    session: Session,
    user_message: str,
    *,
    pal: bool = False,
    log_user: str | None = None,
) -> None:
    """Drive one user turn: send to LLM, handle tool loop, emit SSE events.

    `pal` opens a pal turn for the whole of this call (P8): the system prompt
    gains the `ask_pal` documentation and `PAL_TURN_INSTRUCTION`, and the tool
    is willing to run. The window is a context manager rather than a pair of
    assignments so that it closes on every exit — a clean return, an LLM
    error, an auto-reset that raised, a cancelled task.

    `log_user` is what the session log records as the user's message, for the
    case where what was typed (`/pal how does X work`) and what was sent to
    the model (`how does X work`) differ. The log is a record of the
    conversation, so it keeps the typed line.

    Emits:
      - event: user           { "text": <user msg> }  (ack to all listeners)
      - event: system_prompt  { "text": <synthetic harness-driven prompt> }
      - event: system         { "kind": ..., "message": ... }  (auto-reset chrome)
      - event: turn_start     { "speaker": <chief readvisor name> }
      - event: token          { "text": <chunk> }
      - event: tool           { "name": ..., "key": ..., "ok": ... }
      - event: turn_end       { }
      - event: usage          { prompt_tokens, completion_tokens, total_tokens, ctx }
      - event: reset          { "reason": ... }
      - event: done           { }
      - event: pal_exchange   { "model_id": ..., "prompt": ..., "reply": ... }
      - event: error          { "message": ... }
    """
    async with session.generation_lock:
        # Re-assemble system prompt fresh per spec.
        # 0.5.1: the lean profile when the full prompt would take more than
        # half the live window (`prompt.choose_profile`); the preflight showed
        # the same choice in the empty conversation. `prompt_profile` is what
        # `/api/llm-status` reports, so a bug report can say which ran.
        system_prompt, session.prompt_profile = prompt_mod.assemble_for_window(
            session.project_dir, _current_ctx_size(session) or session.last_usage.get("ctx"), pal=pal)

        tool_calls_for_log: list[tuple[str, str]] = []
        assistant_text_for_log: list[str] = []
        pal_state: _pal.PalTurn | None = None

        try:
            with _pal.pal_turn(session, active=pal) as pal_state:
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
            kind = None
            first = None
            if looks_like_overflow:
                try:
                    first = await _first_turn_overflow(session, system_prompt, e.detail)
                except Exception:  # noqa: BLE001 — never lose the error itself
                    log.exception("first-turn overflow advice failed")
            if first is not None:
                # A first turn, or instructions that alone leave no room:
                # /reset and "disable skills" cannot help there (plan §8.4).
                msg = f"context window full (llm {e.status}): {e.detail}\n{first}"
                kind = "ctx_overflow"
            elif looks_like_overflow:
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
            # `kind` lets the page put the context notice (and its one-click
            # fix) under a first-turn overflow; absent everywhere else.
            await session.emit("error", {"message": msg, **({"kind": kind} if kind else {})})
            log.exception("llm error")
        except httpx.HTTPError as e:
            await session.emit("error", {"message": f"llm transport error: {e}"})
            log.exception("llm error")
        except Exception as e:  # noqa: BLE001
            await session.emit("error", {"message": f"server error: {e}"})
            log.exception("generation error")
        finally:
            await session.emit("done", {})

        # Persist to session log. A pal exchange is written out in full —
        # the prompt that left this machine and the answer that came back —
        # because the conversation it happened in is cleared on every reset
        # and the log is what is left.
        spoken = [t.strip() for t in assistant_text_for_log if t.strip()]
        for exchange in (pal_state.exchanges if pal_state else []):
            spoken.append(
                f"{_pal.RESULT_HEADER}{exchange['model_id']}\n\n"
                f"{exchange['prompt']}\n\n"
                f"pal · {exchange['model_id']}\n\n"
                f"{exchange['reply']}"
            )
        try:
            log_exchange(
                session.project_dir,
                ExchangeLog(
                    user=log_user if log_user is not None else user_message,
                    assistant="\n\n".join(spoken),
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
# The mode boundary (home-plan §3)
# ---------------------------------------------------------------------------

# Everything a home-mode server answers. One page, one set of prefs, the help
# center and the MacroCOSM spec (both project-independent), the DocOES doc
# volumes (`/api/docs*`, built into the install's state, never a project) and
# the inline cosm reader (`/api/cosm/inline*`: a volume from the text the
# request carries, so the docs viewer's live examples work at home too; Canon's
# `/api/canon/*` are project routes and 404 here), the formats table its {{convert-formats}}
# token expands, the desktop shell's graceful-quit route (a home backend is
# still a backend the shell has to be able to stop), and /api/home/*.
# Everything else is project-scoped, and a home server has no project to scope
# it to.
HOME_PATHS: frozenset[str] = frozenset({
    "/", "/favicon.ico", "/api/ui-config", "/api/help-center",
    # The four specifications' raw markdown (0.5.4: the synced copy when one is in use) and the launch check's report.
    "/api/macrocosm-spec", "/api/thym-spec", "/api/ascribe-spec", "/api/comprise-spec", "/api/specs-status",
    "/api/convert/formats", "/api/shutdown",
    # DocOES (0.4.4): read-only, from the install's own documents.
    "/api/docs", "/api/docs/status", "/api/docs/build", "/api/docs/lens",
    "/api/docs/compile", "/api/docs/inventory",
    "/api/cosm/inline", "/api/cosm/inline/lens",
})
# The language library (0.8): read-only, from the copy synced into the install (`/api/library/*`).
HOME_PREFIXES: tuple[str, ...] = ("/api/home/", "/static/", "/api/library/")


class ModeGate:
    """404 everything that belongs to the other mode.

    One gate instead of a flag on eighty routes: a home server hides the
    project routes, a project server hides `/api/home/*`. `/api/close-project`
    is the one route that crosses — it's the reverse of `/api/home/open`, so
    it lives on the project side and 404s in home mode like everything else
    not on the list.

    Raw ASGI rather than `@app.middleware("http")` on purpose: Starlette's
    `BaseHTTPMiddleware` proxies the receive channel, which is exactly what a
    long-lived SSE response (`/api/stream`) needs untouched.
    """

    def __init__(self, app: Any, *, home: bool) -> None:
        self.app = app
        self.home = home

    def _blocked(self, path: str) -> str | None:
        if self.home:
            if path in HOME_PATHS or path.startswith(HOME_PREFIXES):
                return None
            return ("not available on the enough home screen — open a project "
                    "first")
        if path.startswith("/api/home/"):
            return "this is a project server; the home screen runs its own"
        return None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            why = self._blocked(scope.get("path", ""))
            if why:
                await JSONResponse({"detail": why}, status_code=404)(
                    scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# The agent-free boundary (docs/docoes-044-plan.md §13)
# ---------------------------------------------------------------------------

# Every write route that would start a model, mapped to what the 409 says.
# Exact paths, POST only (each of these is a POST; their GETs, where they
# exist, are reads and stay open). Not here, on purpose:
# - `/api/canon/derive`, `/api/canon/atem`, `/api/canon/compile` run in rules
#   mode instead (`llm.reachable` answers `(False, "agent-free")`), and their
#   jobs carry `reason: agent-free`;
# - `/api/skills/toggle` refuses only a toggle-on that needs the first-use
#   audit (the route itself answers that 409); toggles that need no model work;
# - `/api/models/download/*`, `/api/models/delete/*`, `/api/cloud/set-key`
#   (its health check is skipped), `/api/cloud/clear-key`,
#   `/api/cloud/set-model`: installing and configuring stay allowed;
# - `/api/reset` (clears the history), `/api/intro` (a static text),
#   `/api/canon/ingest` (no model; the ingest bar calls it directly);
# - `/api/council/pause`: stopping is always allowed.
AGENT_FREE_PATHS: dict[str, str] = {
    "/api/chat": "the chat needs a readvisor, and none runs while agent-free is on",
    "/api/model": "no model starts while agent-free is on (installing and "
                  "downloading models still work)",
    "/api/cloud/health-check": "the cloud check sends a prompt to a model",
    # Whisper is a model too, and agent-free means no AI at all (owner, §13).
    "/api/transcribe": "voice input runs a speech model, and none runs while agent-free is on",
    # Thym (0.5.0): a reading is told by a model and `read` has no scaffold (THYM.md 14, 19). A Thym run is not here:
    # a plan that asks nothing runs while agent-free is on, and the run route refuses one that asks, with the count.
    "/api/canon/read": "a reading is told by a model, and none runs while agent-free is on",
}
# Every POST under these prefixes, less AGENT_FREE_OPEN: a council is
# readvisors speaking, so setting one up, convening, driving, a user
# statement, `/pal`, concluding and reconvening are all refused.
AGENT_FREE_PREFIXES: dict[str, str] = {
    "/api/council/": "councils need readvisors, and none runs while agent-free is on",
}
AGENT_FREE_OPEN: frozenset[str] = frozenset({"/api/council/pause"})
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def agent_free_refusal(method: str, path: str) -> str | None:
    """The 409 sentence for a request agent-free mode refuses, else None.
    Pure: whether agent-free is ON is the caller's question."""
    if method.upper() in _READ_METHODS or path in AGENT_FREE_OPEN:
        return None
    what = AGENT_FREE_PATHS.get(path)
    if what is None:
        what = next((w for p, w in AGENT_FREE_PREFIXES.items()
                     if path.startswith(p)), None)
    return _agent_free.detail(what) if what else None


class AgentFreeGate:
    """409 every model route while agent-free mode is on.

    The same raw-ASGI shape as `ModeGate`, for the same reason (the SSE
    stream's receive channel stays untouched). The switch is asked only for
    a request the table would refuse, so every other request costs a dict
    lookup and nothing more."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            why = agent_free_refusal(scope.get("method", "GET"), scope.get("path", ""))
            if why and _agent_free.enabled():
                await JSONResponse({"detail": why}, status_code=409)(
                    scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class _RevalidatingStatic(StaticFiles):
    """`/static` with `Cache-Control: no-cache` (0.5.1).

    Starlette's StaticFiles sends an ETag and Last-Modified but no
    Cache-Control, which leaves freshness to the browser's heuristic — a
    tenth of the file's age — and an icon's URL never changes between
    releases. So the 0.5.0 desktop app, whose snapshot held the new icons
    and whose server sent them, still drew 0.4.4's: the webview had them
    cached as fresh. `no-cache` means "keep it, but ask first": every load
    revalidates with If-None-Match and a 304 costs nothing on loopback.
    (index.html itself is already `no-store` below; the page stamps its
    asset URLs with the version too, see staticUrl() there, so a 0.5.1
    page never even asks for a path the old cache knows.)
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response

def create_app(
    project_dir: Path,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    *,
    supervise: bool = True,
    home: bool = False,
    port: int | None = None,
) -> FastAPI:
    """The app, in one of two modes.

    `home=True` is the launch screen (home-plan §1.1): no project, no llama
    supervision, no broker, no wikisink hook — the lifespan skips all of it,
    `/` serves index.html with `data-mode="home"`, and every project-scoped
    route 404s (`_mode_gate` below). `project_dir` is still required by the
    Session dataclass but nothing in home mode reads it; the CLI passes the
    cwd. `port` is remembered only so the CLI handoff can re-exec on the same
    URL the open browser tab is already pointing at.
    """
    session = Session(project_dir=project_dir, llm_url=llm_url, max_tool_iters=max_tool_iters)
    supervisor = LlamaSupervisor(llm_url=llm_url) if (supervise and not home) else None
    # The running loop, captured at startup so background *threads* (the
    # convert worker's progress callbacks, uv's output pump) can fan events
    # out over SSE. Same trick the wikisink progress emitter uses, hoisted
    # here because two managers now need it.
    _loop: dict[str, Any] = {}

    def _emit_threadsafe(event: str, data: dict[str, Any]) -> None:
        loop = _loop.get("loop")
        if loop is None:
            return
        asyncio.run_coroutine_threadsafe(session.emit(event, data), loop)
    session.supervisor = supervisor  # so _run_turn can read current ctx for the usage gauge
    # The context preflight (docs/ctx-16gb-plan.md §8.3): the default system
    # prompt — built exactly as a chat turn builds it — against the live
    # window, re-measured when the model turns ready (launch, adopt, switch),
    # at project open and on each page load. Background only; never blocks.
    preflight = None if home else _preflight.Preflight(
        llm_url=llm_url,
        build_prompt=lambda: assemble_system_prompt(session.project_dir),
        build_lean_prompt=lambda: assemble_system_prompt(session.project_dir, profile="lean"),
        supervisor=supervisor,
    )
    session.preflight = preflight
    if supervisor is not None and preflight is not None:
        supervisor.on_ready = lambda: preflight.schedule("ready")
    # Startup work the lifespan fires and doesn't await (the project catalog);
    # held here so the tasks aren't garbage-collected mid-run.
    _startup_tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        loop = asyncio.get_running_loop()
        _loop["loop"] = loop
        if home:
            # The launch screen runs none of the below: no llm client, no
            # supervisor, no broker, no wikisink, no Canon migration.
            # It seeds the registry from the shell's MRU (once — the flag
            # lives in the registry) and gets out of the way.
            try:
                added = await asyncio.to_thread(_home.seed_from_desktop)
                if added:
                    log.info("home: seeded %d project(s) from desktop.json", added)
            except Exception:  # noqa: BLE001 — never block the launch screen
                log.exception("home: seeding from desktop.json failed")
            # The specifications' launch check (0.5.4): the home screen opens
            # the docs viewer too. One daemon thread, never awaited; off by
            # the preference or ENOUGH_SPECS_SYNC=0.
            _specs.launch_check(_read_ui_config())
            yield
            return
        session.client = httpx.AsyncClient()
        # 0.8: sandbox run folders a crash or a stopped app left behind, older than a day, are swept (each run's
        # folder is removed as soon as its result is read; ENOUGH_SANDBOX_KEEP keeps them for debugging).
        from . import sandbox as _sandbox_sweep
        try:
            swept = await asyncio.to_thread(_sandbox_sweep.sweep)
            if swept:
                log.info("sandbox: swept %d stale run folder(s)", len(swept))
        except Exception:  # noqa: BLE001 — never block startup on a sweep
            log.exception("sandbox: sweeping stale run folders failed")
        # Opening a project is what stamps `last_opened` — and registers it
        # if it predates the registry, which is how an old project first
        # appears on the home screen (home-plan §6).
        try:
            await asyncio.to_thread(_home.touch_opened, session.project_dir)
        except Exception:  # noqa: BLE001 — never block startup on the registry
            log.exception("home: could not record this project's open")
        # Wikisink update runs execute in worker threads (agent tool /
        # endpoint); this hook lets them fan wiki_sink progress events
        # out over SSE without touching the loop directly.
        from .wikisink import update as _wiki_update

        def _wiki_progress(data: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(session.emit("wiki_sink", data), loop)

        _wiki_update.PROGRESS_EMITTER = _wiki_progress
        # One-time, idempotent dissolve of ~/enough/infoworld/ into Canon
        # volumes (personal/public/wiki). Missing infoworld = no-op; a volume
        # of the same name already present = skipped. Move-only. (Its first
        # `canon.root()` is also where ~/enough/cacheawl/ becomes
        # ~/enough/canon/, once.)
        try:
            report = await asyncio.to_thread(_canon.migrate_infoworld)
            if report.get("migrated"):
                log.info("canon: migrated infoworld folders %s",
                         report["migrated"])
        except Exception:  # noqa: BLE001 — never block startup on migration
            log.exception("canon infoworld migration failed")
        # FEED: build ~/enough/dict/feed.sqlite from reflib/dict when it is
        # missing or its manifest digest moved. Background thread; progress
        # is /api/dict/status. A missing source is "unavailable", not an error.
        from . import dictionary as _dictionary
        try:
            await asyncio.to_thread(_dictionary.ensure_built, background=True)
        except Exception:  # noqa: BLE001 — never block startup on the dictionary
            log.exception("dictionary build could not start")
        # The specifications kept current from cosmoes.org (0.5.4,
        # enough/specs.py): one request for the manifest in a daemon thread,
        # only changed texts fetched, into ENOUGH_SPECS_ROOT; the docs viewer
        # rebuilds a changed volume on its next open. Off by the `specs_sync`
        # preference or ENOUGH_SPECS_SYNC=0 (every test and scratch rig).
        _specs.launch_check(_read_ui_config())
        if _agent_free.enabled():
            # Agent-free mode (§13): the model never starts and the preflight
            # never runs. Turning it off (POST /api/ui-config) bootstraps then.
            log.info("agent-free mode: no model this session until it is turned off")
        elif supervisor is not None:
            try:
                await supervisor.bootstrap()
            except Exception:  # noqa: BLE001
                log.exception("supervisor bootstrap failed")
        elif preflight is not None:
            # Not supervised: nothing will say "ready", so measure at open
            # (a server that is not up yet just leaves the verdict unknown;
            # the next page load asks again).
            preflight.schedule("open")
        # The project's catalog, rness/canon.cosm (plan §6.7): reconciled once
        # at open, in a worker thread that startup doesn't wait for — it
        # writes only when the bytes would change.
        def _project_catalog() -> None:
            try:
                _canon.project_catalog(session.project_dir)
            except Exception:  # noqa: BLE001 — a catalog is never worth a failed open
                log.exception("canon: project catalog at startup failed")

        _startup_tasks.add(loop.create_task(asyncio.to_thread(_project_catalog)))
        try:
            yield
        finally:
            _wiki_update.PROGRESS_EMITTER = None
            # A startup catalog still running finishes in its thread; the task
            # is let go so the loop can close without a pending-task warning.
            for task in list(_startup_tasks):
                task.cancel()
            await asyncio.to_thread(_dictionary.cancel_build)
            if preflight is not None:
                await preflight.cancel()
            if supervisor is not None:
                await supervisor.stop(only_if_owned=True)
            # 0.8: every run of an authored fabulac's entailment in the sandbox is stopped with the app.
            from . import sandbox as _sandbox
            _sandbox.stop_all()
            await session.client.aclose()

    app = FastAPI(title="enough", lifespan=lifespan)
    # The one `Session` this app was built around, reachable from the app
    # object. Everything in here closes over `session` directly and does not
    # need it; a test that has to reason about the generation lock (the
    # council exclusion, P5) has no other way to reach it.
    app.state.session = session
    app.mount("/static", _RevalidatingStatic(directory=str(STATIC_DIR)), name="static")

    app.add_middleware(ModeGate, home=home)
    # 0.8: the API promise's header gate (`enough/api_promise.py`): a promised route that starts a run or writes
    # answers 403 without `X-Enough-Api: 1`.
    from . import api_promise as _api_promise
    app.add_middleware(_api_promise.PromiseGate)
    # Home has no model routes to refuse (ModeGate 404s them all).
    if not home:
        app.add_middleware(AgentFreeGate)
    # 0.9: the Origin gate (`enough/origin_gate.py`), added last so it answers first: a request that changes state
    # from a page that is not enough's own is refused before any other gate or route sees it.
    from . import origin_gate as _origin_gate
    app.add_middleware(_origin_gate.OriginGate, port=port)

    # ---------- The routes (0.8): one module per group, under enough/routes/ ----------
    #
    # Each module's `build_router(ctx)` is this factory's old code for its group, moved unchanged; `ctx` carries
    # what those routes closed over here, and the helpers one group defines and another (or this factory) reads.
    # The routers are included in the order their routes were registered in when they lived here.
    from .routes import canon as _r_canon
    from .routes import chat as _r_chat
    from .routes import common as _r_common
    from .routes import convert as _r_convert
    from .routes import docs as _r_docs
    from .routes import fabula as _r_fabula
    from .routes import files as _r_files
    from .routes import girraph as _r_girraph
    from .routes import help as _r_help
    from .routes import home as _r_home
    from .routes import models as _r_models
    from .routes import paradigm_skills as _r_paradigm_skills
    from .routes import project as _r_project
    from .routes import settings as _r_settings
    from .routes import wiki as _r_wiki
    ctx = _r_common.AppContext(
        app=app, session=session, supervisor=supervisor, preflight=preflight, home=home,
        project_dir=project_dir, llm_url=llm_url, max_tool_iters=max_tool_iters, supervise=supervise,
        port=port, _loop=_loop, _emit_threadsafe=_emit_threadsafe,
    )
    # The project-path helpers several groups (and the composure and council routers below) share.
    _r_common.build_shared(ctx)
    _resolve_project_path = ctx._resolve_project_path

    app.include_router(_r_project.build_router(ctx))          # /, /api/project*, /api/files
    app.include_router(_r_paradigm_skills.build_router(ctx))  # /api/paradigm*, /api/skills*, /api/roles*
    app.include_router(_r_help.build_router(ctx))             # /api/help*, /api/intro, /api/requests/done
    app.include_router(_r_files.build_router(ctx))            # /api/reveal, /api/file*, /api/highlights
    app.include_router(_r_convert.build_router(ctx))          # /api/convert*, /api/file/blob, /api/paginate*

    # ---------- Composure (the .comp canvas) ----------
    #
    # One line, because the whole surface lives in `enough/composure_api.py`
    # over the pure core in `enough/composure.py`. The router closes over
    # exactly three things this factory owns: the project dir, the shared
    # path-safety helper, and the SSE emitter. Home mode registers it too
    # and ModeGate 404s it, like every other project route.
    from . import composure_api as _composure_api
    app.include_router(_composure_api.build_router(
        project_dir=project_dir,
        resolve_path=_resolve_project_path,
        emit=session.emit,
    ))

    # ---------- Councils (the multi-readvisor composure form, P5) ----------
    #
    # Same one line, same reason: `enough/council.py` is the engine and
    # `enough/council_api.py` the HTTP translation. It takes the session as
    # well, because a council turn holds `generation_lock` and reads the
    # supervisor's live ctx-size to divide the window.
    from . import council_api as _council_api
    app.include_router(_council_api.build_router(
        project_dir=project_dir,
        resolve_path=_resolve_project_path,
        emit=session.emit,
        session=session,
    ))

    # ---------- FEED (the free enough enumerated dictionary) ----------
    #
    # Install-wide, not per project: `enough/dictionary.py` is the engine,
    # `enough/dictionary_api.py` the HTTP translation, and the router closes
    # over nothing. Project mode only, like every route not on ModeGate's list.
    from . import dictionary_api as _dictionary_api
    app.include_router(_dictionary_api.build_router())

    # The brief introduction (`show_intro`, the chat's intro match) is served
    # in the UI language, which this module owns the config for.
    _intro.set_language_source(_ui_language)

    app.include_router(_r_girraph.build_router(ctx))          # /api/girraph*
    app.include_router(_r_wiki.build_router(ctx))             # /api/wiki/*
    app.include_router(_r_canon.build_router(ctx))            # /api/canon/* (not jobs), /api/cosm*
    app.include_router(_r_docs.build_router(ctx))             # /api/*-spec, /api/specs-status, /api/docs*
    app.include_router(_r_fabula.build_router(ctx))           # /api/fabula/*, /api/canon/atem*, /api/canon/job/*

    # What the Thym, fabulac, fabulap, dialectic and allograph routers below are built with (`routes/fabula.py`,
    # `routes/canon.py`).
    canon_jobs = ctx.canon_jobs
    app.state.canon_jobs = canon_jobs
    _canon_catalog_after = ctx._canon_catalog_after
    _canon_mode = ctx._canon_mode
    _compile_short = ctx._compile_short
    _cosm_payload = ctx._cosm_payload
    _model_complete = ctx._model_complete
    _start_canon_job = ctx._start_canon_job
    _text_target = ctx._text_target
    # ---------- Thym (0.5.0): programs, plans, runs, traces; packages and readings ----------
    #
    # One line, as for the composure and council routers: `enough/thym/` is the language, `enough/thym_host.py`
    # enough's side of it, `enough/thym_api.py` the HTTP translation. Runs and readings are CanonJobs (kinds `thym`
    # and `read`) started through `_start_canon_job`, so they take the generation lock in model mode and carry the
    # agent-free reason like a derivation; the cosm viewer's payload is `_cosm_payload`, passed in, not copied.
    from . import thym_api as _thym_api
    app.include_router(_thym_api.build_router(
        project_dir=project_dir, llm_url=session.llm_url, jobs=canon_jobs, canon_mode=_canon_mode,
        start_job=_start_canon_job, text_target=_text_target, catalog_after=_canon_catalog_after,
        model_complete=_model_complete, cosm_payload=_cosm_payload,
    ))

    # ---------- The fabula round (0.6): a folder's fabulac, its compiles, and the dialectic ----------
    #
    # Two routers, as for Thym: `enough/fabulac_job.py` (`/api/fabula/build|resume|cancel|compile|compiled|cshort|
    # catem`; a build is a CanonJob of kind `fabulac`, a compile of kind `compile`) and `enough/dialectic_api.py`
    # (`/api/dialectic/questions|check|answers|raise|ask-again|settle`; a settle is a CanonJob of kind `dialectic`).
    from . import dialectic_api as _dialectic_api
    from . import fabulac_job as _fabulac_job
    _fabula_router = _fabulac_job.build_router(
        project_dir=project_dir, llm_url=session.llm_url, jobs=canon_jobs, canon_mode=_canon_mode,
        start_job=_start_canon_job, model_complete=_model_complete, catalog_after=_canon_catalog_after,
        compile_short=_compile_short,
    )
    app.include_router(_fabula_router)
    # 0.7: a poem decompiled in steps, the five programs of decompile-verse.thym (`enough/fabulap_job.py`,
    # `/api/fabula/verse/build|resume|cancel`; a build is a CanonJob of kind `fabulap`, keyed by the poem).
    from . import fabulap_job as _fabulap_job
    _fabulap_router = _fabulap_job.build_router(
        project_dir=project_dir, llm_url=session.llm_url, jobs=canon_jobs, canon_mode=_canon_mode,
        start_job=_start_canon_job, model_complete=_model_complete, catalog_after=_canon_catalog_after,
    )
    app.include_router(_fabulap_router)
    # 0.8: a scaffold's lock, check, findings and export (`composure_api.build_scaffold_router`,
    # `/api/composure/scaffold*`; the check is a CanonJob of kind `scaffold`, keyed by the composure).
    app.include_router(_composure_api.build_scaffold_router(
        project_dir=project_dir, resolve_path=_resolve_project_path, emit=session.emit, jobs=canon_jobs,
        canon_mode=_canon_mode, start_job=_start_canon_job, model_complete=_model_complete,
        llm_url=session.llm_url,
    ))
    _dialectic_router = _dialectic_api.build_router(
        project_dir=project_dir, llm_url=session.llm_url, jobs=canon_jobs, canon_mode=_canon_mode,
        start_job=_start_canon_job, model_complete=_model_complete, catalog_after=_canon_catalog_after,
        emit=_emit_threadsafe,
    )
    app.include_router(_dialectic_router)
    # The Allograph Registry (0.7; Ascribe 14.7 to 14.13): Connect's sign-in, a holograph's subject, and a listing's
    # statements (`enough/allograph_api.py`, over `enough/allograph_registry.py`); the allograph itself is made by
    # `POST /api/ascribe/allograph` above.
    from . import allograph_api as _allograph_api
    app.include_router(_allograph_api.build_router(project_dir=project_dir, jobs=canon_jobs,
                                                   catalog_after=_canon_catalog_after))
    # 0.8, fabulac-first F6: an authored fabulac's routes (`enough/routes/fabulac.py`, `/api/fabulac/*`), every one in
    # the API promise; begin, entail and take back are CanonJobs, and the sandbox's test and run too (kind `sandbox`).
    from .routes import fabulac as _r_fabulac
    _first_router = _r_fabulac.build_router(ctx)
    app.include_router(_first_router)
    # 0.9 (pins section 10): a Lean file's or folder's fabulam and its pshorts (`enough/routes/fabulam.py`,
    # `/api/fabulam/*`); a build or an entailment is a CanonJob of kind `fabulam`, keyed by the source.
    from .routes import fabulam as _r_fabulam
    _fabulam_router = _r_fabulam.build_router(ctx)
    app.include_router(_fabulam_router)

    # The names a release has retired (`enough/retired_names.py`): each old path is served by its new path's handler
    # for one release; nothing documents them. The table is empty in 0.7.
    for _method, _old, _new in _retired_names.ROUTES:
        _hit = next((r for r in app.router.routes
                     if getattr(r, "path", None) == _new and _method in (getattr(r, "methods", None) or ())), None)
        if _hit is not None:
            app.add_api_route(_old, _hit.endpoint, methods=[_method], include_in_schema=False)

    # The agent's fabula tools start a build or a compile as a job from the chat turn's worker thread: they hand
    # the start to the event loop and come back with its first snapshot (a local job then waits for the lock the
    # turn holds, `queued`, and runs when the turn ends).
    def _start_from_tool(fn: Callable[[], Any]) -> Any:
        loop = _loop.get("loop")
        if loop is None:
            raise RuntimeError("the app is not running, so no job can start")

        async def _go() -> Any:
            return await fn()
        return asyncio.run_coroutine_threadsafe(_go(), loop).result(timeout=30)

    if not home:
        from . import fabula_tools as _fabula_tools
        _fabula_tools.configure(project_dir=project_dir, start=_start_from_tool,
                                build=_fabula_router.start_build, compile=_fabula_router.start_compile,
                                verse=_fabulap_router.start_build,
                                settle=_dialectic_router.start_settle, jobs=canon_jobs, emit=_emit_threadsafe,
                                first=_first_router.start, fabulam=_fabulam_router.start)

    app.include_router(_r_chat.build_router(ctx))             # /api/chat, /api/stream, /api/broker*, ...
    app.include_router(_r_settings.build_router(ctx))         # /api/ui-config, /api/readvisor/chief
    app.include_router(_r_models.build_router(ctx))           # /api/cloud/*, /api/models*, /api/transcribe
    app.include_router(_r_home.build_router(ctx))             # /api/home/*, /api/shutdown, /favicon.ico
    return app


def run(
    *,
    project_dir: Path,
    port: int,
    llm_url: str,
    max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS,
    supervise: bool = True,
    home: bool = False,
) -> int:
    """Serve until asked to stop; return the process's exit status.

    Driving `uvicorn.Server` ourselves (rather than `uvicorn.run`, which is
    the same three lines plus the worker/reload machinery we don't use) is
    what lets a home handoff exit **42** — see `request_process_exit`.
    """
    app = create_app(project_dir, llm_url, max_tool_iters=max_tool_iters,
                     supervise=supervise, home=home, port=port)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info"))
    _UVICORN["server"] = server
    try:
        server.run()
    finally:
        _UVICORN.pop("server", None)
    return int(_EXIT_CODE.pop("code", 0))
