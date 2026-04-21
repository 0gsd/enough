"""Tool execution: read_file, write_file, shell.

All paths are resolved under the project directory. Absolute paths and
`../` traversal are rejected. Shell commands run with the project dir as cwd,
no sandbox, full stdout/stderr capture.

The tool-call parser (regex over the XML-ish tags defined in prompt.py) lives
here too, so callers (server.py) can do: `for call in parse_tool_calls(text): ...`.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

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

# Detection-only (partial-text) pattern for streaming: is there a closing tag
# at or near the end of the buffer?
_CLOSING_TOOL_RE = re.compile(r"</tool>")


@dataclass
class ToolCall:
    name: str                 # read_file | write_file | shell
    path: str | None
    content: str | None
    command: str | None
    raw: str                  # full matched <tool>...</tool> substring
    span: tuple[int, int]     # (start, end) indices into the source text


@dataclass
class ToolResult:
    name: str
    key: str                  # path for file ops, command for shell
    ok: bool
    body: str                 # stdout-like; for write_file a confirmation

    def render(self) -> str:
        """Format for injection into the conversation as a user message."""
        attr = 'path' if self.name in ('read_file', 'write_file') else 'command'
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
        calls.append(
            ToolCall(
                name=name,
                path=path_m.group(1).strip() if path_m else None,
                content=content_m.group(1) if content_m else None,  # preserve whitespace
                command=command_m.group(1).strip() if command_m else None,
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


def _read_allowlist(project_dir: Path) -> list[Path]:
    """Parse absolute-path prefixes from `.rness/policies/read-allowlist.md`.

    Matches markdown bullets of the form:
        - `~/enough/`
        - `/Users/whoever/stuff/`

    Non-matching lines (prose, headers) are ignored. Returns resolved Paths.
    Missing policy file → empty list (strict containment).
    """
    policy = project_dir / ".rness" / "policies" / "read-allowlist.md"
    if not policy.is_file():
        return []
    out: list[Path] = []
    in_section = False
    for line in policy.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## "):
            in_section = stripped.startswith("## allowlisted prefixes")
            continue
        if not in_section:
            continue
        m = _ALLOWLIST_RE.match(line)
        if not m:
            continue
        raw = m.group("path").strip()
        if not raw:
            continue
        expanded = Path(raw).expanduser()
        try:
            out.append(expanded.resolve(strict=False))
        except OSError:
            continue
    return out


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
) -> Path:
    """Resolve `rel` under `project_dir`. Raise ValueError on escape.

    With `allow_outside_read=True`, ABSOLUTE paths matching the read
    allowlist (`.rness/policies/read-allowlist.md`) are permitted. Relative
    `../` escapes are always rejected — the agent should use absolute
    paths when reaching outside the project.
    """
    if not rel:
        raise ValueError("empty path")
    p = Path(rel).expanduser()
    if p.is_absolute():
        if not allow_outside_read:
            raise ValueError(f"absolute paths rejected: {rel!r}")
        target = p.resolve(strict=False)
        allowlist = _read_allowlist(project_dir)
        if not _under_any(target, allowlist):
            pretty = ", ".join(str(a) for a in allowlist) or "(empty)"
            raise ValueError(
                f"path {rel!r} is outside the project and not on the read "
                f"allowlist. allowlisted prefixes: {pretty}. to add a prefix, "
                f"edit .rness/policies/read-allowlist.md."
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
    (".rness", "requests", "done"),
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
    targets `.rness/requests/<slug>_<ts>.md` and another file with the same
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
    if rel_parts[:2] != (".rness", "requests") or len(rel_parts) != 3:
        return None
    m = _REQUEST_FILENAME_RE.match(rel_parts[-1])
    if not m:
        return None
    target_ts = m.group("ts")
    target_real = target.resolve(strict=False)
    reqs_dir = project_dir / ".rness" / "requests"
    for other in reqs_dir.glob("*.md"):
        if other.resolve() == target_real:
            continue  # same file → legitimate update
        other_m = _REQUEST_FILENAME_RE.match(other.name)
        if other_m and other_m.group("ts") == target_ts:
            return (
                f"a request with timestamp {target_ts} already exists at "
                f".rness/requests/{other.name}. that's probably the file you "
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


def run_write_file(project_dir: Path, call: ToolCall) -> ToolResult:
    if not call.path:
        return ToolResult("write_file", "", False, "error: missing <path>")
    if call.content is None:
        return ToolResult("write_file", call.path, False, "error: missing <content>")
    try:
        target = _safe_join(project_dir, call.path)
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


_DISPATCH = {
    "read_file": run_read_file,
    "write_file": run_write_file,
    "shell": run_shell,
}


def execute(project_dir: Path, call: ToolCall) -> ToolResult:
    fn = _DISPATCH.get(call.name)
    if fn is None:
        return ToolResult(
            call.name, "", False,
            f"error: unknown tool {call.name!r}. "
            f"available: {', '.join(_DISPATCH)}",
        )
    return fn(project_dir, call)
