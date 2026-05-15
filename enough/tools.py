"""Tool execution: read_file, write_file, shell, fetch_url.

All paths are resolved under the project directory. Absolute paths and
`../` traversal are rejected. Shell commands run with the project dir as cwd,
no sandbox, full stdout/stderr capture. `fetch_url` is the canonical way
for the agent to read from the web — handles internet-allowlist routing,
Tor fallback for off-list domains, markdown conversion, and caching into
`rness/io/input/`.

The tool-call parser (regex over the XML-ish tags defined in prompt.py) lives
here too, so callers (server.py) can do: `for call in parse_tool_calls(text): ...`.

Each call is also passed through the broker (broker.py) for trace logging
to `rness/knowledge/session-logs/<date>-broker.md`, gated by user-controlled
toggles in `~/enough/config/broker.json`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import re
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from . import broker, highlights

log = logging.getLogger("enough.tools")

# Regex for a complete tool call. Non-greedy body so we stop at the first
# </tool>. We don't use an XML parser because the model's output isn't
# guaranteed to be well-formed XML.
_TOOL_BLOCK_RE = re.compile(
    r'<tool\s+name="([a-zA-Z_][a-zA-Z0-9_]*)"\s*>(.*?)</tool>',
    re.DOTALL,
)
_PATH_RE = re.compile(r"<path>(.*?)</path>", re.DOTALL)
_CONTENT_RE = re.compile(r"<content>(.*?)</content>", re.DOTALL)
_COMMAND_RE = re.compile(r"<command>(.*?)</command>", re.DOTALL)
_URL_RE = re.compile(r"<url>(.*?)</url>", re.DOTALL)
# Catches any other inner tag so new tools can ship without re-touching
# the parser; `ToolCall.extra` exposes them by name.
_INNER_TAG_RE = re.compile(r"<([a-zA-Z_][a-zA-Z0-9_-]*)>(.*?)</\1>", re.DOTALL)
_KNOWN_INNER_TAGS = frozenset({"path", "content", "command", "url"})

# Detection-only (partial-text) pattern for streaming: is there a closing tag
# at or near the end of the buffer?
_CLOSING_TOOL_RE = re.compile(r"</tool>")


@dataclass
class ToolCall:
    name: str                 # read_file | write_file | shell | fetch_url | read_highlights | navigate_to_highlight | ...
    path: str | None
    content: str | None
    command: str | None
    url: str | None
    extra: dict[str, str]     # any other inner tags (e.g. <color>green</color>) — keeps the schema open
    raw: str                  # full matched <tool>...</tool> substring
    span: tuple[int, int]     # (start, end) indices into the source text


@dataclass
class ToolResult:
    name: str
    key: str                  # path for file ops, command for shell
    ok: bool
    body: str                 # stdout-like; for write_file a confirmation
    side_effects: dict[str, Any] = field(default_factory=dict)
    # Optional: a name → payload map for things the tool wants the
    # server layer to do AFTER the result is recorded. Currently used
    # by `navigate_to_highlight` to ask the UI (via SSE) to scroll to
    # a specific highlight without going through the agent's tool-result
    # text. Existing tools leave this empty and behave exactly as before.

    def render(self) -> str:
        """Format for injection into the conversation as a user message."""
        if self.name in ('read_file', 'write_file'):
            attr = 'path'
        elif self.name == 'fetch_url':
            attr = 'url'
        else:
            attr = 'command'
        safe_key = self.key.replace('"', "&quot;")
        return (
            f'<tool_result name="{self.name}" {attr}="{safe_key}">\n'
            f'{self.body}\n'
            f'</tool_result>'
        )


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Find all complete <tool>...</tool> blocks in `text`."""
    calls: list[ToolCall] = []
    for m in _TOOL_BLOCK_RE.finditer(text):
        name, body = m.group(1), m.group(2)
        path_m = _PATH_RE.search(body)
        content_m = _CONTENT_RE.search(body)
        command_m = _COMMAND_RE.search(body)
        url_m = _URL_RE.search(body)
        # Sweep for any non-standard inner tags so new tools (e.g.
        # read_highlights with <color>green</color>) work without
        # touching the parser. We only collect tags we don't already
        # extract via the named regexes above.
        extra: dict[str, str] = {}
        for tag_m in _INNER_TAG_RE.finditer(body):
            tag, value = tag_m.group(1), tag_m.group(2)
            if tag in _KNOWN_INNER_TAGS:
                continue
            extra[tag] = value.strip()
        calls.append(
            ToolCall(
                name=name,
                path=path_m.group(1).strip() if path_m else None,
                content=content_m.group(1) if content_m else None,  # preserve whitespace
                command=command_m.group(1).strip() if command_m else None,
                url=url_m.group(1).strip() if url_m else None,
                extra=extra,
                raw=m.group(0),
                span=(m.start(), m.end()),
            )
        )
    return calls


def has_complete_tool_call(buffered_text: str) -> bool:
    """Used by the streaming loop to decide when to stop-and-execute."""
    return bool(_TOOL_BLOCK_RE.search(buffered_text))


def first_tool_call_end(buffered_text: str) -> int | None:
    """Return the end-index of the first complete tool call in the buffer,
    or None if no complete call yet."""
    m = _TOOL_BLOCK_RE.search(buffered_text)
    return m.end() if m else None


_ALLOWLIST_RE = re.compile(
    r"^\s*-\s+`?(?P<path>[^`\s][^`]*?)`?\s*$"
)

# Section headings recognized in policies/allowlists.md.
# `read-allowlist.md`'s legacy `## allowlisted prefixes` heading is treated
# as file-read for back-compat; it'll keep working until the file fully
# migrates to allowlists.md.
_ALLOWLIST_SECTION_KEYS: dict[str, str] = {
    "## file-read prefixes":       "file_read",
    "## file-read-write prefixes": "file_rw",
    "## internet domains":         "internet",
    "## allowlisted prefixes":     "file_read",  # legacy
}


def _read_allowlists(project_dir: Path) -> dict[str, list[str]]:
    """Parse the three allowlists from `rness/policies/allowlists.md`,
    falling back to legacy `read-allowlist.md` if the new file is absent.

    Returns a dict with keys `file_read`, `file_rw`, `internet`. Each
    value is a list of raw entries (paths or domains, lowercased for
    domains, ~ unexpanded for paths). Missing file → empty lists.
    Path-prefix lookups should call `_resolve_path_allowlist` to get
    canonical absolute Paths."""
    rness = project_dir / "rness" / "policies"
    candidates = [rness / "allowlists.md", rness / "read-allowlist.md"]
    policy = next((p for p in candidates if p.is_file()), None)
    out: dict[str, list[str]] = {"file_read": [], "file_rw": [], "internet": []}
    if policy is None:
        return out
    current: str | None = None
    for line in policy.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## "):
            current = _ALLOWLIST_SECTION_KEYS.get(stripped)
            continue
        if current is None:
            continue
        m = _ALLOWLIST_RE.match(line)
        if not m:
            continue
        entry = m.group("path").strip()
        if not entry:
            continue
        if current == "internet":
            out[current].append(entry.lower())
        else:
            out[current].append(entry)
    return out


def _resolve_path_allowlist(entries: list[str]) -> list[Path]:
    """Turn raw path entries (`~/foo/`, `/etc/`) into canonical Paths,
    silently dropping any that won't resolve."""
    out: list[Path] = []
    for raw in entries:
        try:
            out.append(Path(raw).expanduser().resolve(strict=False))
        except OSError:
            continue
    return out


def _read_allowlist(project_dir: Path) -> list[Path]:
    """Back-compat shim — file-read prefixes only. Existing callers (and
    tests) that imported this name keep working.

    The "read" allowlist transparently includes file-rw prefixes too,
    since anything writable is implicitly readable."""
    raw = _read_allowlists(project_dir)
    return _resolve_path_allowlist(raw["file_read"] + raw["file_rw"])


def _read_write_allowlist(project_dir: Path) -> list[Path]:
    """Just the file-rw prefixes — destinations writes are allowed to."""
    raw = _read_allowlists(project_dir)
    return _resolve_path_allowlist(raw["file_rw"])


def _under_any(target: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            target.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _safe_join(
    project_dir: Path,
    rel: str,
    *,
    allow_outside_read: bool = False,
    allow_outside_write: bool = False,
) -> Path:
    """Resolve `rel` under `project_dir`. Raise ValueError on escape.

    With `allow_outside_read=True`, ABSOLUTE paths matching the file-read
    or file-rw allowlist are permitted.

    With `allow_outside_write=True`, ABSOLUTE paths matching the file-rw
    allowlist (only) are permitted — for `write_file`. Reading a path
    requires only `allow_outside_read`; writing requires the stricter
    `allow_outside_write`.

    Relative `../` escapes are always rejected — the agent should use
    absolute paths when reaching outside the project."""
    if not rel:
        raise ValueError("empty path")
    p = Path(rel).expanduser()
    if p.is_absolute():
        target = p.resolve(strict=False)
        project_root = project_dir.resolve(strict=False)
        # If the absolute path actually resolves to somewhere inside the
        # project, accept it directly — no allowlist consultation needed.
        # Users (and agents that echo paths back to themselves) commonly
        # supply the full absolute path of a file they already have a
        # relative handle to; that's a typing-style preference, not a
        # containment violation. The allowlist exists to gate paths that
        # are GENUINELY outside the project.
        try:
            target.relative_to(project_root)
            return target
        except ValueError:
            pass
        # Genuinely outside the project — fall through to allowlist
        # enforcement.
        if not (allow_outside_read or allow_outside_write):
            raise ValueError(f"absolute paths rejected: {rel!r}")
        if allow_outside_write:
            allowlist = _read_write_allowlist(project_dir)
            if not _under_any(target, allowlist):
                pretty = ", ".join(str(a) for a in allowlist) or "(empty)"
                raise ValueError(
                    f"path {rel!r} is outside the project and not on the "
                    f"file-read-write allowlist. allowlisted r/w prefixes: "
                    f"{pretty}. to add a prefix, edit "
                    f"rness/policies/allowlists.md."
                )
        else:
            allowlist = _read_allowlist(project_dir)
            if not _under_any(target, allowlist):
                pretty = ", ".join(str(a) for a in allowlist) or "(empty)"
                raise ValueError(
                    f"path {rel!r} is outside the project and not on the "
                    f"file-read allowlist. allowlisted read prefixes: "
                    f"{pretty}. to add a prefix, edit "
                    f"rness/policies/allowlists.md."
                )
        return target
    # Relative path — contained in project, as before.
    target = (project_dir / p).resolve(strict=False)
    root = project_dir.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError(f"path escapes project directory: {rel!r}") from e
    return target


# Paths the agent cannot write to directly, regardless of intent. These are
# locations whose semantics belong to the user/harness — writing here bypasses
# UI affordances that represent user approval.
_WRITE_PROTECTED_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("rness", "requests", "done"),
)


def _protected_write_reason(project_dir: Path, target: Path) -> str | None:
    """Return an error message if `target` is a write-protected location, else None."""
    try:
        rel_parts = target.resolve(strict=False).relative_to(project_dir.resolve(strict=False)).parts
    except ValueError:
        return None  # Path safety will reject this separately.
    for prefix in _WRITE_PROTECTED_PREFIXES:
        if rel_parts[: len(prefix)] == prefix:
            path_str = "/".join(prefix) + "/"
            return (
                f"writes under {path_str} are blocked by the harness. "
                f"this is where the user confirms a request as complete — use "
                f"the 'mark done' button in the preview pane instead of writing "
                f"here yourself."
            )
    return None


# Pattern for request filenames: <slug>_YYYY-MM-DD_HH-MM.md
_REQUEST_FILENAME_RE = re.compile(
    r"^(?P<slug>.+)_(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.md$"
)


def _duplicate_request_reason(project_dir: Path, target: Path) -> str | None:
    """Catch slug-drift: agent regenerates a request filename with a different
    spelling (e.g. `decentralized` → `decentralative`) on a later turn,
    creating a new file instead of updating the existing one. When a write
    targets `rness/requests/<slug>_<ts>.md` and another file with the same
    `<ts>` but a different `<slug>` already exists, point the agent at the
    canonical filename."""
    try:
        rel_parts = target.resolve(strict=False).relative_to(
            project_dir.resolve(strict=False)
        ).parts
    except ValueError:
        return None
    # Only the flat active-requests dir; ignore done/ (already protected)
    # and any deeper nesting.
    if rel_parts[:2] != ("rness", "requests") or len(rel_parts) != 3:
        return None
    m = _REQUEST_FILENAME_RE.match(rel_parts[-1])
    if not m:
        return None
    target_ts = m.group("ts")
    target_real = target.resolve(strict=False)
    reqs_dir = project_dir / "rness" / "requests"
    for other in reqs_dir.glob("*.md"):
        if other.resolve() == target_real:
            continue  # same file → legitimate update
        other_m = _REQUEST_FILENAME_RE.match(other.name)
        if other_m and other_m.group("ts") == target_ts:
            return (
                f"a request with timestamp {target_ts} already exists at "
                f"rness/requests/{other.name}. that's probably the file you "
                f"meant to update — your slug spelling may have drifted "
                f"between turns. `read_file` or `ls` first, then write to the "
                f"exact existing filename. if you really need a parallel "
                f"request, use a different minute in the timestamp."
            )
    return None


def run_read_file(project_dir: Path, call: ToolCall) -> ToolResult:
    if not call.path:
        return ToolResult("read_file", "", False, "error: missing <path>")
    try:
        target = _safe_join(project_dir, call.path, allow_outside_read=True)
    except ValueError as e:
        return ToolResult("read_file", call.path, False, f"error: {e}")
    if not target.exists():
        return ToolResult("read_file", call.path, False, "error: file does not exist")
    if target.is_dir():
        return ToolResult("read_file", call.path, False, "error: path is a directory")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        size = target.stat().st_size
        return ToolResult(
            "read_file", call.path, False,
            f"error: file is not utf-8 text ({size} bytes). use the shell tool to inspect.",
        )
    return ToolResult("read_file", call.path, True, text)


def _undo_path(target: Path) -> Path:
    """Sibling dotfile that holds the file's previous contents so the
    most recent write can be reverted. One-deep stash — Phase 4b ships
    the simplest version of "save or undo"; a future deeper history
    can layer on top without changing the call sites here."""
    return target.parent / f".{target.name}.undo"


def stash_for_undo(target: Path) -> bool:
    """Copy `target`'s current contents to its `.undo` sibling so a
    subsequent revert is possible. No-op when the target doesn't exist
    (a fresh write has nothing to undo back to). Returns True iff a
    stash was actually written.

    Called by both write paths (the agent's `write_file` tool and the
    UI's POST /api/file save) so any write is undoable, not just edits
    initiated from review mode."""
    if not target.is_file():
        return False
    try:
        prior = target.read_bytes()
    except OSError:
        return False
    undo = _undo_path(target)
    try:
        undo.write_bytes(prior)
    except OSError as e:
        log.warning("could not write undo stash for %s: %s", target, e)
        return False
    return True


def run_write_file(project_dir: Path, call: ToolCall) -> ToolResult:
    if not call.path:
        return ToolResult("write_file", "", False, "error: missing <path>")
    if call.content is None:
        return ToolResult("write_file", call.path, False, "error: missing <content>")
    try:
        # Absolute paths require the stricter file-rw allowlist; relative
        # paths are always project-contained as before.
        target = _safe_join(project_dir, call.path, allow_outside_write=True)
    except ValueError as e:
        return ToolResult("write_file", call.path, False, f"error: {e}")
    if (why := _protected_write_reason(project_dir, target)):
        return ToolResult("write_file", call.path, False, f"error: {why}")
    if (why := _duplicate_request_reason(project_dir, target)):
        return ToolResult("write_file", call.path, False, f"error: {why}")
    # The model's <content>...</content> typically has a leading newline from
    # formatting. Strip one leading newline to match expected conventions.
    body = call.content
    if body.startswith("\n"):
        body = body[1:]
    target.parent.mkdir(parents=True, exist_ok=True)
    # Always stash the previous contents so the most recent write can
    # be undone — the user-facing "save or undo?" affordance in
    # review mode reads this. Cheap (one extra small file write per
    # write_file) and safe (no-op for newly-created files).
    stash_for_undo(target)
    try:
        target.write_text(body, encoding="utf-8")
    except OSError as e:
        return ToolResult("write_file", call.path, False, f"error: {e}")
    return ToolResult(
        "write_file", call.path, True,
        f"ok — wrote {len(body)} bytes to {call.path}",
    )


def run_shell(project_dir: Path, call: ToolCall, timeout: float = 60.0) -> ToolResult:
    if not call.command:
        return ToolResult("shell", "", False, "error: missing <command>")
    try:
        proc = subprocess.run(
            call.command,
            shell=True,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as e:
        return ToolResult(
            "shell", call.command, False,
            f"error: command timed out after {timeout}s\n"
            f"stdout (partial):\n{e.stdout or ''}\n"
            f"stderr (partial):\n{e.stderr or ''}",
        )
    except OSError as e:
        return ToolResult("shell", call.command, False, f"error: {e}")

    body = (
        f"exit_code: {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}"
        f"{'' if proc.stdout.endswith(chr(10)) or not proc.stdout else chr(10)}"
        f"--- stderr ---\n{proc.stderr}"
    )
    return ToolResult(
        "shell", call.command, proc.returncode == 0, body,
    )


# ---------------------------------------------------------------------------
# fetch_url — agent's canonical way to read from the web.
# ---------------------------------------------------------------------------
#
# Flow:
#   1. Toggle check: broker.fetch_url_enabled must be on, else canned denial.
#   2. URL parse: extract host, reject anything that doesn't look like http(s).
#   3. Allowlist check on host:
#      - on internet allowlist → direct fetch
#      - off allowlist:
#          - broker.fetch_url_tor_for_offlist=on → fetch via Tor SOCKS5
#          - broker.fetch_url_tor_for_offlist=off → canned denial
#   4. Fetch with size cap and timeout.
#   5. Content-type dispatch:
#      - text/html → pandoc html→markdown (cache as .md)
#      - text/plain, text/markdown → cache as-is
#      - everything else → cache raw bytes with a stub note in the index
#   6. Write cache file under rness/io/input/, append to _broker-index.md.
#   7. Return short preview + cache path to the agent.

_TOR_PROXY = "socks5h://127.0.0.1:9050"  # 'h' = resolve DNS through Tor too
_FETCH_TIMEOUT_S = 30.0
_FETCH_MAX_BYTES = 10 * 1024 * 1024  # 10 MB hard cap
_PREVIEW_CHARS = 500


def _read_internet_allowlist(project_dir: Path) -> list[str]:
    """Return the list of allowlisted internet hostnames. Lowercased,
    leading/trailing whitespace stripped. Empty if the file or section
    is missing."""
    raw = _read_allowlists(project_dir)
    return [h.lower().strip() for h in raw.get("internet", []) if h.strip()]


def _host_on_allowlist(host: str, allowlist: list[str]) -> bool:
    """True iff `host` matches any allowlist entry exactly or as a subdomain.
    e.g. 'en.wikipedia.org' matches an entry 'wikipedia.org' AND
    'en.wikipedia.org'."""
    h = host.lower()
    for entry in allowlist:
        if h == entry or h.endswith("." + entry):
            return True
    return False


def _slugify(text: str, max_len: int = 40) -> str:
    """Conservative slug: alphanum + hyphens, lowercased, deduped hyphens."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not s:
        s = "untitled"
    return s[:max_len].strip("-") or "untitled"


def _short_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:8]


def _markdownify_via_pandoc(html: str) -> tuple[str, bool]:
    """Convert HTML to GitHub-flavored markdown via pandoc. Returns
    (markdown_or_original, converted_ok). Falls back to the raw HTML if
    pandoc isn't installed or errors — the journal will note the fallback."""
    try:
        proc = subprocess.run(
            ["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
            input=html,
            text=True,
            capture_output=True,
            timeout=30.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("pandoc unavailable or timed out (%s); returning raw HTML", e)
        return html, False
    if proc.returncode != 0:
        log.warning("pandoc exit %d: %s", proc.returncode, proc.stderr[:200])
        return html, False
    return proc.stdout, True


def _title_from_html(html: str) -> str:
    """Pull <title> if present; otherwise an empty string. Used for the
    index row's human-readable column."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:120]


def _append_broker_index(
    project_dir: Path,
    *,
    timestamp: str,
    url: str,
    short_hash: str,
    cache_rel: str,
    title: str,
    status: int | str,
) -> None:
    """Append one row to rness/io/input/_broker-index.md, creating the
    file with a header on first call."""
    index = project_dir / "rness" / "io" / "input" / "_broker-index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    if not index.exists():
        index.write_text(
            "# Broker fetch index\n\n"
            "Auto-maintained by `fetch_url`. Newest entries at the bottom.\n"
            "Grep the URL or hash columns to find a cached document.\n\n"
            "| time | hash | url | cache | title | status |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    # Escape pipes so they don't break the table.
    def cell(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ")
    row = (
        f"| {cell(timestamp)} "
        f"| `{cell(short_hash)}` "
        f"| {cell(url)} "
        f"| `{cell(cache_rel)}` "
        f"| {cell(title)} "
        f"| {cell(str(status))} |\n"
    )
    with index.open("a", encoding="utf-8") as f:
        f.write(row)


def run_fetch_url(project_dir: Path, call: ToolCall) -> ToolResult:
    """Fetch a URL with broker semantics: allowlist routing, optional Tor
    fallback, markdown conversion, and io/input caching.

    The agent only ever sees a short preview + cache path in the result —
    full content lives on disk, retrievable via `read_file` if needed."""
    if not broker.is_enabled("fetch_url_enabled"):
        return ToolResult(
            "fetch_url", call.url or "", False,
            broker.denial_tool_disabled("fetch_url"),
        )
    url = (call.url or "").strip()
    if not url:
        return ToolResult("fetch_url", "", False, "error: missing <url>")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ToolResult(
            "fetch_url", url, False,
            "error: only http(s) URLs are supported by fetch_url.",
        )
    host = parsed.hostname.lower()
    allowlist = _read_internet_allowlist(project_dir)
    on_allowlist = _host_on_allowlist(host, allowlist)
    use_tor = not on_allowlist
    if use_tor and not broker.is_enabled("fetch_url_tor_for_offlist"):
        return ToolResult(
            "fetch_url", url, False,
            broker.denial_off_internet_allowlist_no_tor(host),
        )
    client_kwargs: dict[str, object] = {
        "timeout": _FETCH_TIMEOUT_S,
        "follow_redirects": True,
        "headers": {"User-Agent": "enough-broker/0.0 (+local research client)"},
    }
    if use_tor:
        client_kwargs["proxy"] = _TOR_PROXY
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
    except httpx.RequestError as e:
        return ToolResult(
            "fetch_url", url, False,
            f"error: fetch failed ({type(e).__name__}): {e}. "
            f"{'(via Tor)' if use_tor else '(direct)'}",
        )
    if len(resp.content) > _FETCH_MAX_BYTES:
        return ToolResult(
            "fetch_url", url, False,
            f"error: response too large ({len(resp.content)} bytes, cap "
            f"{_FETCH_MAX_BYTES}). use shell + curl with explicit -o to "
            f"a path you control if you really need this.",
        )
    ctype = (resp.headers.get("content-type") or "").lower()
    # Strip charset suffix; just want the MIME prefix.
    ctype_main = ctype.split(";", 1)[0].strip()
    cache_content: str | bytes
    cache_ext: str
    converted_ok = False
    title = ""
    if ctype_main.startswith("text/html"):
        html = resp.text
        title = _title_from_html(html)
        if broker.is_enabled("fetch_url_cache_and_convert"):
            md, converted_ok = _markdownify_via_pandoc(html)
            cache_content = md
            cache_ext = "md" if converted_ok else "html"
        else:
            cache_content = html
            cache_ext = "html"
    elif ctype_main in ("text/plain", "text/markdown", "application/json"):
        cache_content = resp.text
        cache_ext = "md" if ctype_main == "text/markdown" else "txt"
    else:
        cache_content = resp.content
        cache_ext = "bin"
    now = dt.datetime.now()
    timestamp_full = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_short = now.strftime("%Y-%m-%d-%H%M")
    slug_seed = parsed.path.rstrip("/").rsplit("/", 1)[-1] or host
    slug = _slugify(slug_seed)
    short_hash = _short_hash(url + timestamp_full)
    filename = f"{timestamp_short}-{short_hash}-{slug}.{cache_ext}"
    cache_path = project_dir / "rness" / "io" / "input" / filename
    cache_rel = f"rness/io/input/{filename}"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if isinstance(cache_content, str):
            cache_path.write_text(cache_content, encoding="utf-8")
        else:
            cache_path.write_bytes(cache_content)
    except OSError as e:
        return ToolResult(
            "fetch_url", url, False,
            f"error: fetched {len(resp.content)} bytes but could not cache: {e}",
        )
    if broker.is_enabled("fetch_url_cache_and_convert"):
        _append_broker_index(
            project_dir,
            timestamp=timestamp_full,
            url=url,
            short_hash=short_hash,
            cache_rel=cache_rel,
            title=title,
            status=resp.status_code,
        )
    # Preview: first N chars of text content; for binary, just a size note.
    if isinstance(cache_content, str):
        preview = cache_content[:_PREVIEW_CHARS]
        if len(cache_content) > _PREVIEW_CHARS:
            preview += f"\n… (+{len(cache_content) - _PREVIEW_CHARS} chars; full text at {cache_rel})"
    else:
        preview = f"(binary content — {len(cache_content)} bytes; cached at {cache_rel})"
    routing = "via Tor" if use_tor else "direct"
    convert_note = ""
    if ctype_main.startswith("text/html"):
        if converted_ok:
            convert_note = " — converted HTML→markdown via pandoc"
        elif broker.is_enabled("fetch_url_cache_and_convert"):
            convert_note = " — HTML cached raw (pandoc unavailable or errored)"
    # When a Tor-routed fetch comes back 4xx/5xx, the most common cause
    # is exit-node blocking (Google/Cloudflare/etc. block Tor IPs by
    # policy). Without this hint the agent will retry the same URL or
    # nearby variants and burn the context window on identical 429s.
    block_hint = ""
    if use_tor and resp.status_code >= 400:
        block_hint = (
            f"\nhint: {host} returned HTTP {resp.status_code} via a Tor "
            f"exit node. many sites (google.com, cloudflare-fronted sites, "
            f"some news outlets) reject Tor traffic by policy. options: "
            f"(a) try an on-allowlist source for the same info — "
            f"en.wikipedia.org, en.wikisource.org, www.gutenberg.org, "
            f"archive.org all route direct and rarely block; "
            f"(b) add {host} to rness/policies/allowlists.md under "
            f"'## Internet domains' to fetch it directly without Tor "
            f"(only if you trust the site with your real IP); "
            f"(c) stop retrying — the block is likely persistent.\n"
        )
    body = (
        f"ok — fetched {url} ({routing}, HTTP {resp.status_code}, "
        f"{ctype_main}, {len(resp.content)} bytes){convert_note}.\n"
        f"cached at: {cache_rel}\n"
        f"hash: {short_hash} — grep rness/io/input/_broker-index.md to find later."
        f"{block_hint}\n"
        f"--- preview ---\n{preview}\n"
    )
    return ToolResult("fetch_url", url, resp.status_code < 400, body)


# ---------------------------------------------------------------------------
# read_highlights — agent-facing query into the per-doc highlights sidecar.
# ---------------------------------------------------------------------------
#
# Accepts <path> (the document) and optional <color> (yellow / green /
# blue / pink). Returns a brief markdown listing of matching highlights:
# id, color, snippet preview, and source-position hint when available.
# This is what the agent calls when the user says e.g. "the pink words"
# — it gets concrete entries it can then cross-reference with the doc
# text via read_file.

def run_read_highlights(project_dir: Path, call: ToolCall) -> ToolResult:
    path = (call.path or "").strip()
    if not path:
        return ToolResult("read_highlights", "", False, "error: missing <path>")
    color = (call.extra.get("color") or "").strip().lower() or None
    if color and color not in highlights.ALLOWED_COLORS:
        return ToolResult(
            "read_highlights", path, False,
            f"error: unknown color {color!r}. allowed: "
            + ", ".join(highlights.ALLOWED_COLORS),
        )
    items = highlights.load_highlights(project_dir, path)
    if color:
        items = [h for h in items if h.get("color") == color]
    if not items:
        scope = f" ({color})" if color else ""
        return ToolResult(
            "read_highlights", path, True,
            f"no highlights{scope} on {path}.",
        )
    lines = [
        f"highlights on {path}"
        + (f" filtered to {color}" if color else "")
        + f": {len(items)} found.",
        "",
    ]
    for i, h in enumerate(items, 1):
        snippet = (h.get("snippet") or "").replace("\n", " ")
        if len(snippet) > 140:
            snippet = snippet[:140] + "…"
        loc = ""
        if h.get("src_start") is not None:
            loc = f" [src bytes {h['src_start']}–{h.get('src_end', '?')}]"
        stale = " [STALE]" if h.get("stale") else ""
        lines.append(
            f"{i}. {h.get('id', '?')} [{h.get('color', '?')}]{stale}{loc} — \"{snippet}\""
        )
    return ToolResult("read_highlights", path, True, "\n".join(lines))


# ---------------------------------------------------------------------------
# navigate_to_highlight — agent-driven UI navigation. Asks the front-end
# to scroll the open review-mode pane to a specific highlight so a
# multi-step "edit the green sections one by one" workflow has visual
# anchoring. The actual scroll is performed by a JS handler listening
# for the `review_navigate` SSE event the server emits when this tool's
# side_effects payload is non-empty.
# ---------------------------------------------------------------------------

def run_navigate_to_highlight(project_dir: Path, call: ToolCall) -> ToolResult:
    path = (call.path or "").strip()
    if not path:
        return ToolResult("navigate_to_highlight", "", False, "error: missing <path>")
    hl_id = (call.extra.get("id") or "").strip() or None
    color = (call.extra.get("color") or "").strip().lower() or None
    index_str = (call.extra.get("index") or "").strip()
    index: int | None = None
    if index_str:
        try:
            index = int(index_str)
        except ValueError:
            return ToolResult("navigate_to_highlight", path, False,
                              f"error: <index> must be an integer, got {index_str!r}")
    items = highlights.load_highlights(project_dir, path)
    target: dict[str, Any] | None = None
    if hl_id:
        target = next((h for h in items if h.get("id") == hl_id), None)
        if target is None:
            return ToolResult("navigate_to_highlight", path, False,
                              f"no highlight with id {hl_id!r} on {path}")
    elif color:
        if color not in highlights.ALLOWED_COLORS:
            return ToolResult("navigate_to_highlight", path, False,
                              f"error: unknown color {color!r}")
        filtered = [h for h in items if h.get("color") == color]
        if not filtered:
            return ToolResult("navigate_to_highlight", path, False,
                              f"no {color} highlights on {path}")
        if index is not None:
            if index < 1 or index > len(filtered):
                return ToolResult("navigate_to_highlight", path, False,
                                  f"index {index} out of range; {len(filtered)} {color} highlights")
            target = filtered[index - 1]
        else:
            target = filtered[0]
    else:
        return ToolResult(
            "navigate_to_highlight", path, False,
            "error: must specify <id>, or <color> (with optional <index>).",
        )
    snippet = (target.get("snippet") or "").replace("\n", " ")
    if len(snippet) > 120:
        snippet = snippet[:120] + "…"
    body = (
        f"navigating review pane to {target['color']} highlight "
        f"{target['id']} on {path}: \"{snippet}\""
    )
    # The side-effects payload is what server._handle_tool reads to
    # emit the SSE event the front-end consumes.
    return ToolResult(
        "navigate_to_highlight", path, True, body,
        side_effects={
            "review_navigate": {
                "path": path,
                "id": target["id"],
                "color": target["color"],
                "snippet": target.get("snippet") or "",
            },
        },
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "read_file": run_read_file,
    "write_file": run_write_file,
    "shell": run_shell,
    "fetch_url": run_fetch_url,
    "read_highlights": run_read_highlights,
    "navigate_to_highlight": run_navigate_to_highlight,
}

# Map tool name to its per-tool "brokered" toggle. When that toggle is
# OFF, we still run the tool but skip the broker journal entry — the
# allowlist checks live inside the runners themselves and aren't affected.
# Highlight tools always trace (they're tied to the broker journal by
# the highlights module itself, so the entry shows up regardless of
# this map; this entry just keeps the dispatch happy).
_TRACE_TOGGLE = {
    "read_file": "read_file_brokered",
    "write_file": "write_file_brokered",
    "shell": "shell_brokered",
    "fetch_url": "fetch_url_enabled",
    "read_highlights": "trace_log_enabled",
    "navigate_to_highlight": "trace_log_enabled",
}


def _trace_args_for(call: ToolCall) -> dict[str, object]:
    """Build the args dict for the broker journal entry. Skip None fields
    and `content` (always summarized via len rather than dumping the body)."""
    out: dict[str, object] = {}
    if call.path is not None:
        out["path"] = call.path
    if call.command is not None:
        out["command"] = call.command
    if call.url is not None:
        out["url"] = call.url
    # Surface any non-standard inner tags (e.g. <color>green</color>)
    # in the journal so highlight-tool calls show their parameters.
    for k, v in (call.extra or {}).items():
        out[k] = v
    if call.content is not None:
        out["content"] = f"<{len(call.content)} chars>"
    return out


def execute(project_dir: Path, call: ToolCall) -> ToolResult:
    fn = _DISPATCH.get(call.name)
    if fn is None:
        return ToolResult(
            call.name, "", False,
            f"error: unknown tool {call.name!r}. "
            f"available: {', '.join(_DISPATCH)}",
        )
    result = fn(project_dir, call)
    # Trace logging: gated on (a) the per-tool toggle AND (b) the global
    # trace_log_enabled. broker.trace() does the second check internally.
    trace_toggle = _TRACE_TOGGLE.get(call.name)
    if trace_toggle is None or broker.is_enabled(trace_toggle):
        decision = "allowed" if result.ok else "denied/error"
        broker.trace(
            project_dir,
            tool=call.name,
            decision=decision,
            args=_trace_args_for(call),
            result_ok=result.ok,
            result_summary=result.body,
        )
    return result
