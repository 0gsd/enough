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
- System prompt is re-assembled from `.rness/` on every user turn (no cache).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
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

from .llm import LLMError, stream_chat
from .logger import ExchangeLog, log_exchange
from .prompt import assemble_system_prompt, list_skills, set_skill_enabled
from .tools import (
    ToolCall,
    execute,
    first_tool_call_end,
    parse_tool_calls,
)

log = logging.getLogger("enough")

STATIC_DIR = Path(__file__).parent / "static"
IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".llama-server",
}
DEFAULT_MAX_TOOL_ITERS = 50
MAX_FILE_TREE_DEPTH = 4


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

    async def emit(self, event: str, data: Any) -> None:
        payload = {"event": event, "data": json.dumps(data)}
        for q in list(self.subscribers):  # snapshot — subscribers may unregister mid-iter
            await q.put(payload)


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------

def _walk_tree(root: Path, rel_parts: tuple[str, ...], depth: int) -> list[dict[str, Any]]:
    if depth > MAX_FILE_TREE_DEPTH:
        return []
    abs_dir = root.joinpath(*rel_parts)
    try:
        entries = sorted(abs_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for p in entries:
        if p.name.startswith(".") and p.name != ".rness":
            continue
        if p.name in IGNORE_DIRS:
            continue
        rel = "/".join(rel_parts + (p.name,))
        node = {
            "name": p.name,
            "path": rel,
            "is_dir": p.is_dir(),
            "is_symlink": p.is_symlink(),
        }
        # Recurse into directories — including directories reached via a
        # symlink (infoworld/) — but don't recurse through a symlinked
        # directory's OWN children to avoid amplifying the "symlinked"
        # visual: the top-level link is the meaningful UI unit.
        if p.is_dir() and not p.is_symlink():
            node["children"] = _walk_tree(root, rel_parts + (p.name,), depth + 1)
        elif p.is_dir() and p.is_symlink():
            # Walk the symlinked dir's contents but mark the root entry as
            # the symlink; children appear plain (they live in the symlink
            # target, not in the project proper).
            node["children"] = _walk_tree(root, rel_parts + (p.name,), depth + 1)
        out.append(node)
    return out


def build_file_tree(root: Path) -> list[dict[str, Any]]:
    return _walk_tree(root, (), 1)


def _tree_to_html(nodes: list[dict[str, Any]]) -> str:
    out = ['<ul class="tree">']
    for n in nodes:
        path = n["path"].replace('"', "&quot;")
        sym_cls = " symlink" if n.get("is_symlink") else ""
        if n["is_dir"]:
            out.append(
                f'<li class="dir{sym_cls}">'
                f'<span class="dir-name">{n["name"]}/</span>'
            )
            if n.get("children"):
                out.append(_tree_to_html(n["children"]))
            out.append("</li>")
        else:
            out.append(
                f'<li class="file{sym_cls}"><a href="#" '
                f'hx-get="/api/file?path={path}" hx-target="#preview-body" '
                f'hx-swap="innerHTML" '
                f'onclick="document.getElementById(\'preview\').classList.add(\'open\')"'
                f'>{n["name"]}</a></li>'
            )
    out.append("</ul>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Chat generation
# ---------------------------------------------------------------------------

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


async def _run_turn(session: Session, user_message: str) -> None:
    """Drive one user turn: send to LLM, handle tool loop, emit SSE events.

    Emits:
      - event: user         { "text": <user msg> }  (ack to all listeners)
      - event: turn_start   { }
      - event: token        { "text": <chunk> }
      - event: tool         { "name": ..., "key": ..., "ok": ... }
      - event: turn_end     { }
      - event: done         { }
      - event: error        { "message": ... }
    """
    async with session.generation_lock:
        # Re-assemble system prompt fresh per spec.
        system_prompt = assemble_system_prompt(session.project_dir)

        # Append the user turn to history.
        session.history.append({"role": "user", "content": user_message})
        await session.emit("user", {"text": user_message})

        tool_calls_for_log: list[tuple[str, str]] = []
        assistant_text_for_log: list[str] = []

        assert session.client is not None
        client = session.client

        try:
            for _iter in range(session.max_tool_iters):
                messages = [{"role": "system", "content": system_prompt}] + session.history
                await session.emit("turn_start", {})
                buffer = ""
                agen = stream_chat(session.llm_url, messages, client=client)
                stopped_at_tool = False
                try:
                    async for chunk in agen:
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
                assistant_text_for_log.append(buffer)
                await session.emit("turn_end", {})

                if not stopped_at_tool:
                    break  # natural end — no tool call

                calls = parse_tool_calls(buffer)
                if not calls:
                    # Shouldn't happen — first_tool_call_end said yes but parse failed.
                    break
                call = calls[-1]  # the call we stopped at
                await _handle_tool(session, call, tool_calls_for_log)
            else:
                await session.emit(
                    "error",
                    {"message": f"tool loop cap ({session.max_tool_iters}) reached"},
                )
        except LLMError as e:
            # Try to give a hint if it looks like a context overflow.
            hint = ""
            low = e.detail.lower()
            if any(k in low for k in ("context", "exceed", "n_ctx", "too many tokens", "token limit")):
                hint = (
                    "  (this looks like a context-window overflow. raise the "
                    "llama-server -c flag and/or --parallel 1, or /reset the "
                    "conversation, or disable some skills in the sidebar.)"
                )
            await session.emit("error", {"message": f"llm {e.status}: {e.detail}{hint}"})
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
    session.history.append({"role": "user", "content": result.render()})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(project_dir: Path, llm_url: str, max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS) -> FastAPI:
    session = Session(project_dir=project_dir, llm_url=llm_url, max_tool_iters=max_tool_iters)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        session.client = httpx.AsyncClient()
        try:
            yield
        finally:
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
        # No-cache so edits-in-place don't require force-reload during dev.
        return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate"})

    @app.get("/api/files", response_class=HTMLResponse)
    async def api_files() -> HTMLResponse:
        tree = build_file_tree(project_dir)
        return HTMLResponse(_tree_to_html(tree))

    @app.get("/api/skills", response_class=HTMLResponse)
    async def api_skills() -> HTMLResponse:
        items = list_skills(project_dir / ".rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no skills in .rness/skills/</div>')
        rows = []
        for name, enabled in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            rows.append(
                f'<li class="skill-row {cls}">'
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
        set_skill_enabled(project_dir / ".rness", name, enabled_raw == "1")
        return await api_skills()  # type: ignore[return-value]

    @app.get("/api/requests", response_class=HTMLResponse)
    async def api_requests() -> HTMLResponse:
        rdir = project_dir / ".rness" / "requests"
        if not rdir.is_dir():
            return HTMLResponse('<div class="empty-note">no .rness/requests/ yet</div>')
        active = sorted(
            (p for p in rdir.glob("*.md") if p.is_file()),
            key=lambda p: p.name,
            reverse=True,  # newest first (YYYY-MM-DD_HH-MM sorts chronologically)
        )
        if not active:
            return HTMLResponse('<div class="empty-note">no active requests</div>')
        rows = []
        for p in active:
            rel = f".rness/requests/{p.name}"
            label = _escape_html(p.stem)
            rows.append(
                f'<li class="request-row">'
                f'  <a href="#" '
                f'    hx-get="/api/file?path={_escape_html(rel)}" '
                f'    hx-target="#preview-body" hx-swap="innerHTML" '
                f'    onclick="document.getElementById(\'preview\').classList.add(\'open\')">'
                f'    {label}'
                f'  </a>'
                f'</li>'
            )
        return HTMLResponse('<ul class="requests">' + "".join(rows) + "</ul>")

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
        done_dir = project_dir / ".rness" / "requests" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        dest = done_dir / target.name
        # If a file with the same name already exists in done/, disambiguate.
        if dest.exists():
            dest = done_dir / (target.stem + "_dup.md")
        target.rename(dest)
        # Return the new requests list so htmx can refresh the sidebar.
        return await api_requests()  # type: ignore[return-value]

    def _resolve_project_path(path: str) -> Path:
        """Shared path-safety helper for /api/file{,/raw} and POST writes."""
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise HTTPException(400, "invalid path")
        target = (project_dir / p).resolve()
        try:
            target.relative_to(project_dir.resolve())
        except ValueError:
            raise HTTPException(400, "path escapes project dir") from None
        return target

    def _is_request_file(path: str) -> bool:
        p = Path(path)
        parts = p.parts
        # Active request = directly under .rness/requests/ (not /done/).
        return (
            len(parts) >= 3
            and parts[0] == ".rness"
            and parts[1] == "requests"
            and parts[2] != "done"
            and parts[-1].endswith(".md")
        )

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
        if external:
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
                '<button class="edit-btn" onclick="enterEditMode()">edit</button>'
            )
        return HTMLResponse(
            f'<div class="file-path" data-path="{_escape_html(path)}">{_escape_html(path)}</div>'
            f'{sym_note}'
            f'<div class="preview-actions">'
            f'  {mark_done_btn}'
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

    @app.post("/api/file", response_class=HTMLResponse)
    async def api_file_write(request: Request) -> HTMLResponse:
        form = await request.form()
        path = (form.get("path") or "").strip()
        content = form.get("content")
        if content is None:
            raise HTTPException(400, "missing content")
        if not path:
            raise HTTPException(400, "missing path")
        target = _resolve_project_path(path)
        if target.is_dir():
            raise HTTPException(400, "is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        # Return the re-rendered preview fragment so the UI can swap it in.
        return await api_file(path=path)  # type: ignore[return-value]

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
        return HTMLResponse("")

    @app.get("/favicon.ico")
    async def favicon():
        f = STATIC_DIR / "favicon.ico"
        if f.exists():
            return FileResponse(f)
        return HTMLResponse("", status_code=204)

    return app


def run(*, project_dir: Path, port: int, llm_url: str, max_tool_iters: int = DEFAULT_MAX_TOOL_ITERS) -> None:
    app = create_app(project_dir, llm_url, max_tool_iters=max_tool_iters)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
