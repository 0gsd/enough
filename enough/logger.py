"""Session logging to `.rness/knowledge/session-logs/YYYY-MM-DD.md`.

One file per day; a single exchange is one H2 timestamp section containing the
user message, the final assistant response, and a list of tool calls/results.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExchangeLog:
    user: str
    assistant: str                       # final rendered assistant output
    tool_calls: list[tuple[str, str]]    # (tool_name, short_key)  e.g. ("read_file", ".rness/AGENT.md")


def _session_log_path(project_dir: Path, now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now()
    return project_dir / ".rness" / "knowledge" / "session-logs" / f"{now:%Y-%m-%d}.md"


def log_exchange(
    project_dir: Path,
    exchange: ExchangeLog,
    *,
    now: dt.datetime | None = None,
) -> Path:
    """Append an exchange to today's session log. Creates the file if missing."""
    now = now or dt.datetime.now()
    log_path = _session_log_path(project_dir, now)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    header_new_file = not log_path.exists()
    body = []
    if header_new_file:
        body.append(f"# session log — {now:%Y-%m-%d}\n")
    body.append(f"## {now:%H:%M:%S}\n")
    body.append("**User:**\n")
    body.append(exchange.user.strip() + "\n")
    body.append("\n**Agent:**\n")
    body.append(exchange.assistant.strip() + "\n")
    if exchange.tool_calls:
        body.append("\n**Tools used:**\n")
        for name, key in exchange.tool_calls:
            body.append(f"- `{name}`: {key}\n")
    body.append("\n---\n\n")

    with log_path.open("a", encoding="utf-8") as f:
        f.writelines(body)
    return log_path
