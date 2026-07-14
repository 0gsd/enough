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

from . import broker, girraph, highlights

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
        elif self.name == 'cloud_pipeline':
            attr = 'output'
        else:
            attr = 'command'
        safe_key = self.key.replace('"', "&quot;")
        return (
            f'<tool_result name="{self.name}" {attr}="{safe_key}">\n'
            f'{self.body}\n'
            f'</tool_result>'
        )


# Shell-command patterns we refuse to execute because they look like
# attempts to extract the OpenRouter api key out of the OS keyring or to
# probe our internal keyring service name. The patterns are intentionally
# very specific — `enough-broker` and `openrouter-api-key` are identifiers
# we coined ourselves, so a shell command referencing them by name has no
# legitimate purpose during agent execution. (If the user wants to debug
# their keyring backend, they can run those commands in a terminal outside
# this session.) Phase 1 defined the denial message; this is its wiring.
_CLOUD_KEY_EXFIL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\benough-broker\b"),
     "shell command references the broker's keyring service name"),
    (re.compile(r"\bopenrouter-api-key\b"),
     "shell command references the keyring account name for the api key"),
    (re.compile(r"keyring\.(get|set|delete)_password"),
     "shell command invokes the Python keyring api directly"),
    (re.compile(r"\bsecret-tool\s+(lookup|search|store)\b"),
     "shell command uses the Linux Secret Service CLI"),
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
    # Cachebox mirror guard: refuse to edit a modality:mirror file under the
    # cacheawl store BEFORE allowlist resolution, so the denial explains the
    # real reason (mirrors are backend-owned) rather than an allowlist miss.
    from . import cacheawl as _cacheawl  # late import: avoid an import cycle
    _raw = Path(call.path).expanduser()
    _cand = _raw.resolve(strict=False) if _raw.is_absolute() \
        else (project_dir / _raw).resolve(strict=False)
    if (why := _cacheawl.mirror_write_denial(_cand)):
        return ToolResult("write_file", call.path, False, why)
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
    if target.suffix == ".girraph":
        # Whole-file clobbering would defeat the node-level concurrency
        # story (the user may be editing the same girraph in its panel).
        return ToolResult(
            "write_file", call.path, False,
            "error: .girraph files are edited node-by-node, never written "
            "whole. use add_node / update_node / link_nodes / remove_node "
            "(and read_girraph to see current state). to start a new "
            "girraph, call add_node with no <parent> — the file is created "
            "and your label becomes its title.",
        )
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
    # Pre-execution scan: refuse anything that looks like an attempt to
    # extract the OpenRouter api key from the keyring. The keyring access
    # itself is OS-level protected on macOS (first-time read by an
    # unknown process prompts the user), but a defense-in-depth shell
    # filter catches the easy case where an injected prompt asks the
    # agent to "just run this one debugging command".
    for pat, reason in _CLOUD_KEY_EXFIL_PATTERNS:
        if pat.search(call.command):
            return ToolResult(
                "shell", call.command, False,
                broker.denial_cloud_key_exfiltration_attempt(reason),
            )
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


class FetchDenied(Exception):
    """A fetch the broker refuses outright: fetch_url disabled, an
    off-allowlist host with Tor routing turned off, or a non-http(s) URL.
    Carries the agent-facing denial string as its message."""


class FetchError(Exception):
    """A permitted fetch that failed at the network layer or blew the size
    cap. Carries an agent-facing message."""


@dataclass
class FetchResponse:
    """Normalized fetch result for callers other than run_fetch_url (e.g.
    the cacheawl url-ingest crawler) so they share one HTTP stack."""
    status: int
    content_type: str       # main MIME type, lowercased, charset stripped
    text: str               # decoded text (empty for binary types)
    content: bytes
    title: str
    final_url: str


def _fetch_http(
    project_dir: Path, url: str, *,
    timeout: float = _FETCH_TIMEOUT_S, max_bytes: int = _FETCH_MAX_BYTES,
) -> tuple[httpx.Response, bool, str]:
    """The gating + GET core shared by run_fetch_url and fetch_gated:
    toggle check, scheme check, allowlist→direct / off-list→Tor routing,
    the size cap. Returns (httpx response, used_tor, host). Raises
    FetchDenied for broker refusals and FetchError for network/size
    failures — with the exact strings run_fetch_url historically returned,
    so its output is unchanged."""
    if not broker.is_enabled("fetch_url_enabled"):
        raise FetchDenied(broker.denial_tool_disabled("fetch_url"))
    url = (url or "").strip()
    if not url:
        raise FetchError("error: missing <url>")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FetchDenied("error: only http(s) URLs are supported by fetch_url.")
    host = parsed.hostname.lower()
    allowlist = _read_internet_allowlist(project_dir)
    on_allowlist = _host_on_allowlist(host, allowlist)
    use_tor = not on_allowlist
    if use_tor and not broker.is_enabled("fetch_url_tor_for_offlist"):
        raise FetchDenied(broker.denial_off_internet_allowlist_no_tor(host))
    client_kwargs: dict[str, object] = {
        "timeout": timeout,
        "follow_redirects": True,
        "headers": {"User-Agent": "enough-broker/0.0 (+local research client)"},
    }
    if use_tor:
        client_kwargs["proxy"] = _TOR_PROXY
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
    except httpx.RequestError as e:
        raise FetchError(
            f"error: fetch failed ({type(e).__name__}): {e}. "
            f"{'(via Tor)' if use_tor else '(direct)'}"
        ) from e
    if len(resp.content) > max_bytes:
        raise FetchError(
            f"error: response too large ({len(resp.content)} bytes, cap "
            f"{max_bytes}). use shell + curl with explicit -o to a path you "
            f"control if you really need this."
        )
    return resp, use_tor, host


def fetch_gated(
    project_dir: Path, url: str, *,
    timeout: float = _FETCH_TIMEOUT_S, max_bytes: int = _FETCH_MAX_BYTES,
) -> tuple[FetchResponse, bool]:
    """Public gated-fetch for non-tool callers (cacheawl). Same broker
    gating as fetch_url; returns a normalized (FetchResponse, used_tor).
    Raises FetchDenied / FetchError like _fetch_http."""
    resp, use_tor, _host = _fetch_http(project_dir, url, timeout=timeout,
                                       max_bytes=max_bytes)
    ctype_main = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    is_texty = ctype_main.startswith("text/") or ctype_main in (
        "application/json", "application/xml", "application/xhtml+xml")
    text = resp.text if is_texty else ""
    title = _title_from_html(resp.text) if ctype_main.startswith("text/html") else ""
    return (
        FetchResponse(
            status=resp.status_code, content_type=ctype_main, text=text,
            content=resp.content, title=title, final_url=str(resp.url),
        ),
        use_tor,
    )


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


def _markdownify_via_pandoc(html: str, *, strip_raw_html: bool = False) -> tuple[str, bool]:
    """Convert HTML to GitHub-flavored markdown via pandoc. Returns
    (markdown_or_original, converted_ok). Falls back to the raw HTML if
    pandoc isn't installed or errors — the journal will note the fallback.

    strip_raw_html: drop tags gfm can't express (divs, spans, …) instead
    of passing them through raw — text content is kept. Wanted for
    wikisink saves, where structural page chrome would otherwise litter
    the markdown."""
    target = "gfm-raw_html" if strip_raw_html else "gfm"
    try:
        proc = subprocess.run(
            ["pandoc", "-f", "html", "-t", target, "--wrap=none"],
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
    url = (call.url or "").strip()
    if not url:
        return ToolResult("fetch_url", "", False, "error: missing <url>")
    try:
        resp, use_tor, host = _fetch_http(project_dir, url)
    except FetchDenied as e:
        return ToolResult("fetch_url", url, False, str(e))
    except FetchError as e:
        return ToolResult("fetch_url", url, False, str(e))
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
# Girraph tools — node-level ops over .girraph files (plain-text IBIS
# maps; format + ops live in girraph.py). Five tools: read_girraph,
# add_node, update_node, link_nodes, remove_node. All writes hold the
# per-path lock across load→mutate→save; whole-file write_file on
# .girraph is denied above. Reads are depth-limited and render refs as
# one-line stubs so the agent can never slurp a girraph tree into its
# context by accident.
# ---------------------------------------------------------------------------

def _girraph_target(
    project_dir: Path, rel: str | None, *, for_write: bool
) -> Path:
    """Resolve + validate a girraph path. Raises ValueError with an
    agent-actionable message."""
    rel = (rel or "").strip()
    if not rel:
        raise ValueError("missing <path>")
    if not rel.endswith(".girraph"):
        raise ValueError(
            f"{rel!r} is not a .girraph file — girraph tools only operate "
            f"on .girraph paths."
        )
    return _safe_join(
        project_dir, rel,
        allow_outside_read=True,
        allow_outside_write=for_write,
    )


def _girraph_warnings_note(g: "girraph.Girraph") -> str:
    if not g.warnings:
        return ""
    listed = "\n".join(f"- {w}" for w in g.warnings[:8])
    more = f"\n(+{len(g.warnings) - 8} more)" if len(g.warnings) > 8 else ""
    return f"\nparse warnings:\n{listed}{more}\n"


def run_read_girraph(project_dir: Path, call: ToolCall) -> ToolResult:
    try:
        target = _girraph_target(project_dir, call.path, for_write=False)
        g = girraph.load(target)
    except (ValueError, girraph.GirraphError) as e:
        return ToolResult("read_girraph", call.path or "", False, f"error: {e}")
    node = (call.extra.get("node") or "").strip() or None
    depth_str = (call.extra.get("depth") or "").strip()
    depth = 1
    if depth_str:
        try:
            depth = max(0, int(depth_str))
        except ValueError:
            return ToolResult(
                "read_girraph", call.path, False,
                f"error: <depth> must be an integer, got {depth_str!r}",
            )
    try:
        art = girraph.ascii_render(g, node=node, depth=depth, project_dir=project_dir)
    except girraph.GirraphError as e:
        return ToolResult("read_girraph", call.path, False, f"error: {e}")
    body = (
        f"{call.path} — {len(g.nodes)} nodes, depth {depth}"
        f"{f', subtree of {node}' if node else ''}\n"
        f"{_girraph_warnings_note(g)}\n{art}\n"
    )
    return ToolResult("read_girraph", call.path, True, body)


def run_girraph_add_node(project_dir: Path, call: ToolCall) -> ToolResult:
    try:
        target = _girraph_target(project_dir, call.path, for_write=True)
    except ValueError as e:
        return ToolResult("add_node", call.path or "", False, f"error: {e}")
    node_type = (call.extra.get("type") or "").strip()
    label = (call.extra.get("label") or "").strip()
    parent = (call.extra.get("parent") or "").strip() or None
    ref = (call.extra.get("ref") or "").strip() or None
    by = (call.extra.get("by") or "").strip() or None
    detail = call.extra.get("detail") or ""
    with girraph.path_lock(target):
        created_file = False
        if target.is_file():
            try:
                g = girraph.load(target)
            except girraph.GirraphError as e:
                return ToolResult("add_node", call.path, False, f"error: {e}")
        else:
            if parent:
                return ToolResult(
                    "add_node", call.path, False,
                    f"error: {call.path} does not exist, so <parent> can't "
                    f"resolve. omit <parent> to create the file — your "
                    f"label becomes its title and its root node.",
                )
            g = girraph.new_girraph(label)
            created_file = True
        try:
            node = girraph.add_node(
                g, type=node_type, label=label, parent=parent,
                ref=ref, by=by, detail=detail,
            )
        except girraph.GirraphError as e:
            return ToolResult("add_node", call.path, False, f"error: {e}")
        girraph.save(target, g)
    note = " (file created)" if created_file else ""
    return ToolResult(
        "add_node", call.path, True,
        f"ok — added {node.id} to {call.path}{note}: "
        f"{node.id} {node.sigil} {node.label}"
        + (f" < {node.parent}" if node.parent else ""),
    )


def run_girraph_update_node(project_dir: Path, call: ToolCall) -> ToolResult:
    try:
        target = _girraph_target(project_dir, call.path, for_write=True)
    except ValueError as e:
        return ToolResult("update_node", call.path or "", False, f"error: {e}")
    node_id = (call.extra.get("id") or "").strip()
    if not node_id:
        return ToolResult("update_node", call.path, False, "error: missing <id>")
    # Only tags PRESENT in the call are patched; an empty tag clears the
    # field. (call.extra only contains tags the model actually emitted.)
    patch: dict[str, str] = {}
    for field_name in ("label", "detail", "ref", "by", "parent"):
        if field_name in call.extra:
            patch[field_name] = call.extra[field_name]
    if not patch:
        return ToolResult(
            "update_node", call.path, False,
            "error: nothing to update — include at least one of <label>, "
            "<detail>, <ref>, <by>, <parent> (empty tag clears the field).",
        )
    with girraph.path_lock(target):
        try:
            g = girraph.load(target)
            node = girraph.update_node(g, node_id, **patch)
        except girraph.GirraphError as e:
            return ToolResult("update_node", call.path, False, f"error: {e}")
        girraph.save(target, g)
    return ToolResult(
        "update_node", call.path, True,
        f"ok — patched {', '.join(sorted(patch))} on {node.id} in {call.path}.",
    )


def run_girraph_link_nodes(project_dir: Path, call: ToolCall) -> ToolResult:
    try:
        target = _girraph_target(project_dir, call.path, for_write=True)
    except ValueError as e:
        return ToolResult("link_nodes", call.path or "", False, f"error: {e}")
    from_id = (call.extra.get("from") or "").strip()
    to_id = (call.extra.get("to") or "").strip()
    if not from_id or not to_id:
        return ToolResult(
            "link_nodes", call.path, False,
            "error: link_nodes needs <from> and <to> node ids.",
        )
    remove = (call.extra.get("remove") or "").strip().lower() in ("true", "yes", "1")
    with girraph.path_lock(target):
        try:
            g = girraph.load(target)
            if remove:
                girraph.unlink_nodes(g, from_id, to_id)
            else:
                girraph.link_nodes(g, from_id, to_id)
        except girraph.GirraphError as e:
            return ToolResult("link_nodes", call.path, False, f"error: {e}")
        girraph.save(target, g)
    verb = "removed cross-edge" if remove else "added cross-edge"
    return ToolResult(
        "link_nodes", call.path, True,
        f"ok — {verb} {from_id} [-> {to_id}] in {call.path}.",
    )


def run_girraph_remove_node(project_dir: Path, call: ToolCall) -> ToolResult:
    try:
        target = _girraph_target(project_dir, call.path, for_write=True)
    except ValueError as e:
        return ToolResult("remove_node", call.path or "", False, f"error: {e}")
    node_id = (call.extra.get("id") or "").strip()
    if not node_id:
        return ToolResult("remove_node", call.path, False, "error: missing <id>")
    confirmed = (call.extra.get("confirmed") or "").strip().lower() in ("yes", "true")
    if not confirmed:
        return ToolResult(
            "remove_node", call.path, False,
            "error: node removal requires explicit user confirmation (the "
            "no-deletes-without-confirmation policy). ask the user, and "
            "only after they confirm in their own words include "
            "<confirmed>yes</confirmed>. never pre-fill it.",
        )
    cascade = (call.extra.get("cascade") or "").strip().lower() in ("true", "yes")
    with girraph.path_lock(target):
        try:
            g = girraph.load(target)
            removed = girraph.remove_node(g, node_id, cascade=cascade)
        except girraph.GirraphError as e:
            return ToolResult("remove_node", call.path, False, f"error: {e}")
        girraph.save(target, g)
    return ToolResult(
        "remove_node", call.path, True,
        f"ok — removed {', '.join(removed)} from {call.path}. "
        f"(ids are never reused; cross-edges to removed nodes were cleaned up.)",
    )


# ---------------------------------------------------------------------------
# cloud_pipeline — broker-driven multi-step batch execution against
# OpenRouter. The agent passes a JSON spec in <content>; the broker
# (via enough.cloud.pipeline_run) runs every step, caches each, optionally
# compiles + final-passes the result, and returns a structured summary.
# Designed for the "write 36 chapters then proofread them" use case where
# letting the agent loop per-step would burn turns and inflate hijack
# surface. Always non-streaming.
# ---------------------------------------------------------------------------

def run_cloud_pipeline(project_dir: Path, call: ToolCall) -> ToolResult:
    # late import: avoid importing httpx/keyring at module top when this
    # tool is never invoked (most sessions).
    from . import cloud as _cloud
    import json as _json

    # Gating chain: local_models_only must be off, key must be present and
    # healthy, spec must parse. Each failure returns a clear denial so the
    # agent can either give up or surface the issue to the user.
    if broker.is_enabled("local_models_only"):
        return ToolResult(
            "cloud_pipeline", "", False,
            broker.denial_local_models_only(),
        )
    cloud_status = _cloud.status_snapshot()
    if not cloud_status["key_present"]:
        return ToolResult(
            "cloud_pipeline", "", False,
            broker.denial_cloud_key_missing(),
        )
    if not cloud_status["last_verified_ok"]:
        return ToolResult(
            "cloud_pipeline", "", False,
            broker.denial_cloud_unhealthy(cloud_status["last_error"] or "unverified"),
        )
    if not call.content:
        return ToolResult(
            "cloud_pipeline", "", False,
            "error: missing <content> with the pipeline spec (json object). "
            "schema: {steps: [{prompt, system?}, …], compile?: {method, separator?}, "
            "final_pass?: {prompt, system?}, output_path?, model?, temperature?, "
            "max_tokens_per_step?}",
        )
    try:
        spec = _json.loads(call.content)
    except _json.JSONDecodeError as e:
        return ToolResult(
            "cloud_pipeline", "", False,
            f"error: <content> must be valid json — {e}",
        )

    try:
        result = _cloud.pipeline_run(project_dir, spec)
    except _cloud.PipelineError as e:
        return ToolResult("cloud_pipeline", "", False, f"pipeline error: {e}")
    except _cloud.CloudError as e:
        return ToolResult("cloud_pipeline", "", False, f"cloud error: {e}")

    # Summary body: keep it small so the agent's context isn't blown out.
    # The actual prose lives on disk; the agent can read_file specific
    # paths if it needs to inspect output.
    totals = result["totals"]
    body_lines = [
        f"pipeline ok — {result['step_count']} steps via {result['model']}",
        f"tokens: prompt {totals['prompt']} / completion {totals['completion']} / total {totals['total']}",
    ]
    if result.get("output_path"):
        body_lines.append(f"output: {result['output_path']}")
    if result.get("final_path"):
        body_lines.append(f"final-pass cache: {result['final_path']}")
    body_lines.append(
        f"per-step caches: {len(result['step_paths'])} files in rness/io/cloud-cache/"
    )
    if result.get("summary_paths"):
        body_lines.append(
            f"per-step summaries (summarize_each): {len(result['summary_paths'])} additional cache files"
        )
    body_lines.append(
        "(read_file any individual cache to see its prompt + response; "
        "the cloud-cache index is at rness/io/cloud-cache/_cloud-index.md)"
    )
    return ToolResult(
        "cloud_pipeline",
        result.get("output_path") or "(no output_path)",
        True,
        "\n".join(body_lines),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

# Wikisink runners live in wikisink/agent.py; these thin wrappers import
# lazily so tools.py and the wikisink package stay import-acyclic (and a
# missing libzim wheel can't break tool dispatch as a whole).
def run_wiki_search(project_dir: Path, call: ToolCall) -> ToolResult:
    from .wikisink import agent as _wiki_agent
    return _wiki_agent.run_wiki_search(project_dir, call)


def run_read_wiki_article(project_dir: Path, call: ToolCall) -> ToolResult:
    from .wikisink import agent as _wiki_agent
    return _wiki_agent.run_read_wiki_article(project_dir, call)


def run_wiki_status(project_dir: Path, call: ToolCall) -> ToolResult:
    from .wikisink import agent as _wiki_agent
    return _wiki_agent.run_wiki_status(project_dir, call)


def run_wikisink(project_dir: Path, call: ToolCall) -> ToolResult:
    from .wikisink import agent as _wiki_agent
    return _wiki_agent.run_wikisink(project_dir, call)


# ---------------------------------------------------------------------------
# cacheawl tools — the global file store at ~/enough/cacheawl/. Three tools:
# cachebox_list (list boxes or a box's contents), cachebox_create (empty
# box), cachebox_ingest (populate a box from a path/url/wikisink source).
# All gated by the `cacheawl_enabled` broker toggle. The module (cacheawl.py)
# owns the store; these runners are thin adapters. url ingests additionally
# honor the fetch_url toggles by construction (they route through
# fetch_gated).
# ---------------------------------------------------------------------------

def _cacheawl_denied(name: str, key: str = "") -> ToolResult:
    return ToolResult(name, key, False, broker.denial_cacheawl_disabled())


def run_cachebox_list(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("cacheawl_enabled"):
        return _cacheawl_denied("cachebox_list")
    from . import cacheawl as _cacheawl
    box = (call.extra.get("box") or "").strip()
    try:
        if box:
            _cacheawl.reconcile(box)
            data = _cacheawl.cachebox_tree(box)
            lines = [
                f"cachebox {box!r} — {data['item_count']} files, "
                f"{data['total_size_human']}, status {data['status']}",
                f"origin: {data.get('origin')}",
                "contents (folders first):",
            ]

            def render(nodes: list[dict[str, Any]], indent: str = "  ") -> None:
                for n in nodes:
                    if n["is_dir"]:
                        lines.append(f"{indent}{n['name']}/")
                        render(n.get("children") or [], indent + "  ")
                    else:
                        lines.append(f"{indent}{n['name']}")

            render(data.get("tree") or [])
            return ToolResult("cachebox_list", box, True, "\n".join(lines))
        _cacheawl.reconcile_all()
        boxes = _cacheawl.list_cacheboxes()
        if not boxes:
            return ToolResult("cachebox_list", "", True,
                              "no cacheboxes yet. create one with cachebox_create.")
        lines = [f"{len(boxes)} cachebox(es) in ~/enough/cacheawl/:"]
        for b in boxes:
            o = b.get("origin") or {}
            lines.append(
                f"- {b['name']} — {b['item_count']} files, {b['total_size_human']}, "
                f"origin {o.get('type', '?')}"
                + (f":{o.get('value')}" if o.get('value') else "")
                + (f" [status: {b['status']}]" if b['status'] != 'complete' else "")
            )
        return ToolResult("cachebox_list", "", True, "\n".join(lines))
    except _cacheawl.CacheawlError as e:
        return ToolResult("cachebox_list", box, False, f"error: {e}")


def run_cachebox_create(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("cacheawl_enabled"):
        return _cacheawl_denied("cachebox_create")
    from . import cacheawl as _cacheawl
    name = (call.extra.get("name") or call.path or "").strip()
    if not name:
        return ToolResult("cachebox_create", "", False,
                          "error: missing <name> for the new cachebox.")
    try:
        summary = _cacheawl.create_cachebox(name)
    except _cacheawl.CacheawlError as e:
        return ToolResult("cachebox_create", name, False, f"error: {e}")
    return ToolResult("cachebox_create", name, True,
                      f"ok — created empty cachebox {name!r} at "
                      f"~/enough/cacheawl/{name}/ (mirror generated).")


def run_cachebox_ingest(project_dir: Path, call: ToolCall) -> ToolResult:
    if not broker.is_enabled("cacheawl_enabled"):
        return _cacheawl_denied("cachebox_ingest")
    from . import cacheawl as _cacheawl
    box = (call.extra.get("box") or "").strip()
    source_type = (call.extra.get("type") or "").strip().lower()
    value = (call.extra.get("value") or "").strip()
    depth_raw = (call.extra.get("depth") or "").strip()
    all_flag = (call.extra.get("all") or "").strip().lower() in ("true", "yes", "1")
    if not box:
        return ToolResult("cachebox_ingest", "", False,
                          "error: missing <box> (the destination cachebox name).")
    if not source_type or not value:
        return ToolResult("cachebox_ingest", box, False,
                          "error: ingest needs <type> (path|url|wikisink) and "
                          "<value> (the source).")
    depth: Any = depth_raw or 1
    try:
        summary = _cacheawl.run_ingest(
            project_dir, box=box, source_type=source_type, value=value,
            depth=depth, all_flag=all_flag)
    except _cacheawl.CacheawlError as e:
        return ToolResult("cachebox_ingest", box, False, f"error: {e}")
    return ToolResult(
        "cachebox_ingest", box, True,
        f"ok — ingested {summary.get('files_written', 0)} file(s) into cachebox "
        f"{box!r} from {source_type}:{value} (depth "
        f"{summary.get('origin', {}).get('depth')}). now "
        f"{summary['item_count']} files, {summary['total_size_human']}.",
    )


_DISPATCH = {
    "read_file": run_read_file,
    "write_file": run_write_file,
    "shell": run_shell,
    "fetch_url": run_fetch_url,
    "read_highlights": run_read_highlights,
    "navigate_to_highlight": run_navigate_to_highlight,
    "cloud_pipeline": run_cloud_pipeline,
    "read_girraph": run_read_girraph,
    "add_node": run_girraph_add_node,
    "update_node": run_girraph_update_node,
    "link_nodes": run_girraph_link_nodes,
    "remove_node": run_girraph_remove_node,
    "wiki_search": run_wiki_search,
    "read_wiki_article": run_read_wiki_article,
    "wiki_status": run_wiki_status,
    "wikisink": run_wikisink,
    "cachebox_list": run_cachebox_list,
    "cachebox_create": run_cachebox_create,
    "cachebox_ingest": run_cachebox_ingest,
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
    # cloud_pipeline is gated by `local_models_only` (off) + a healthy
    # key; we trace it under the universal trace toggle so the journal
    # captures every cloud batch the agent runs.
    "cloud_pipeline": "trace_log_enabled",
    # Girraph ops trace under the universal toggle — node-level edits
    # are exactly the kind of thing the journal exists to reconstruct.
    "read_girraph": "trace_log_enabled",
    "add_node": "trace_log_enabled",
    "update_node": "trace_log_enabled",
    "link_nodes": "trace_log_enabled",
    "remove_node": "trace_log_enabled",
    # Wikisink tools trace under the universal toggle — an update run
    # that rewrites the overlay is exactly what the journal is for.
    "wiki_search": "trace_log_enabled",
    "read_wiki_article": "trace_log_enabled",
    "wiki_status": "trace_log_enabled",
    "wikisink": "trace_log_enabled",
    # cacheawl tools are gated by `cacheawl_enabled`; trace them under the
    # universal toggle so every box mutation lands in the journal.
    "cachebox_list": "trace_log_enabled",
    "cachebox_create": "trace_log_enabled",
    "cachebox_ingest": "trace_log_enabled",
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
