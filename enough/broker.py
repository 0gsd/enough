"""The broker: config + trace logging + denial messaging.

The broker is the layer the agent's tool calls flow through. Three jobs:

1. **Regulate.** Allowlists in `rness/policies/allowlists.md` decide what's
   reachable; the broker enforces them and returns elegant canned denials
   when something's off-list, pointing the user at how to enable.
2. **Trace.** Every tool call gets a timestamped entry in
   `rness/knowledge/session-logs/<YYYY-MM-DD>-broker.md` — a human-readable
   journal of what the agent did, separate from the chat transcript.
3. **Configure.** A small JSON config at `~/enough/config/broker.json`
   lets the user toggle individual broker behaviors on or off, per-tool.

The `fetch_url` tool itself (with Tor routing, markdown conversion, and
io/input caching) lives in `tools.py` alongside the other tool runners
— this module is everything else.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("enough.broker")


# ---------------------------------------------------------------------------
# Config — global, lives at ~/enough/config/broker.json
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / "enough" / "config" / "broker.json"


@dataclass(frozen=True)
class Toggle:
    """One brokered behavior the user can flip on or off."""
    key: str
    label: str
    description: str
    default: bool
    group: str  # rendering hint: "general" | "read_file" | "write_file" | "shell" | "fetch_url"


# The full toggle catalog. Add to this list to grow the broker — the UI
# renders whatever's here, so adding a row needs no UI changes.
TOGGLES: tuple[Toggle, ...] = (
    Toggle(
        key="trace_log_enabled",
        label="trace logging (all tools)",
        description=(
            "Write every brokered tool call to "
            "rness/knowledge/session-logs/<date>-broker.md. Useful for audit "
            "and debugging. Turn off if you want a quieter filesystem."
        ),
        default=True,
        group="general",
    ),
    Toggle(
        key="read_file_brokered",
        label="read_file: brokered",
        description=(
            "Route read_file through the broker for allowlist enforcement "
            "and trace logging. (Allowlists stay enforced even if you "
            "disable this — the toggle just affects logging.)"
        ),
        default=True,
        group="read_file",
    ),
    Toggle(
        key="write_file_brokered",
        label="write_file: brokered",
        description=(
            "Route write_file through the broker for allowlist enforcement, "
            "protected-dir checks, and trace logging."
        ),
        default=True,
        group="write_file",
    ),
    Toggle(
        key="shell_brokered",
        label="shell: brokered",
        description=(
            "Trace-log shell commands (the agent's nuclear option). Doesn't "
            "restrict what shell can do — there's no path allowlist for "
            "shell by design — but the journal entry is your accountability."
        ),
        default=True,
        group="shell",
    ),
    Toggle(
        key="fetch_url_enabled",
        label="fetch_url: enabled",
        description=(
            "Allow the agent to use the fetch_url tool. When off, the agent "
            "falls back to curl-via-shell for web reads — no Tor, no "
            "markdown conversion, no caching."
        ),
        default=True,
        group="fetch_url",
    ),
    Toggle(
        key="fetch_url_tor_for_offlist",
        label="fetch_url: Tor for off-allowlist domains",
        description=(
            "When fetch_url targets a domain that isn't on the internet "
            "allowlist, route the request through the local Tor proxy at "
            "127.0.0.1:9050. Allowlist domains are fetched directly. Turn "
            "this off to deny off-allowlist fetches outright."
        ),
        default=True,
        group="fetch_url",
    ),
    Toggle(
        key="fetch_url_cache_and_convert",
        label="fetch_url: cache + markdown convert",
        description=(
            "Convert fetched HTML to markdown via pandoc and store the "
            "result in rness/io/input/<timestamp>-<hash>-<slug>.md, plus "
            "a row in _broker-index.md. The agent gets a short preview "
            "instead of the full body — saves context window space."
        ),
        default=True,
        group="fetch_url",
    ),
)


def _toggle_defaults() -> dict[str, bool]:
    return {t.key: t.default for t in TOGGLES}


def load_config() -> dict[str, bool]:
    """Return the merged broker config: defaults overlaid with any
    user-set values from disk. Missing file or missing keys fall through
    to defaults. Always returns a complete dict so callers don't have to
    handle KeyError."""
    cfg = _toggle_defaults()
    if CONFIG_PATH.is_file():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                for key, value in on_disk.items():
                    if key in cfg and isinstance(value, bool):
                        cfg[key] = value
        except (OSError, json.JSONDecodeError) as e:
            log.warning("broker config read failed (%s); using defaults", e)
    return cfg


def save_config(cfg: dict[str, bool]) -> None:
    """Persist the broker config. Only writes recognized keys, dropping
    anything stale."""
    safe = {t.key: bool(cfg.get(t.key, t.default)) for t in TOGGLES}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")


def is_enabled(key: str) -> bool:
    """Quick lookup for a single toggle. Cheap; no caching for now —
    config rarely changes and the JSON file is tiny."""
    return load_config().get(key, False)


# ---------------------------------------------------------------------------
# Trace logging — broker journal at rness/knowledge/session-logs/<date>-broker.md
# ---------------------------------------------------------------------------

def _journal_path(project_dir: Path, now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now()
    return (
        project_dir / "rness" / "knowledge" / "session-logs"
        / f"{now:%Y-%m-%d}-broker.md"
    )


def _summarize_arg(value: Any, max_len: int = 400) -> str:
    """Truncate long values for the journal. We never want full file
    contents bloating the log — a few hundred chars + size suffices to
    reconstruct what happened."""
    if value is None:
        return "(none)"
    s = str(value)
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"… (+{len(s) - max_len} chars truncated)"


def trace(
    project_dir: Path,
    *,
    tool: str,
    decision: str,
    args: dict[str, Any] | None = None,
    result_ok: bool | None = None,
    result_summary: str = "",
    now: dt.datetime | None = None,
) -> None:
    """Append one entry to today's broker journal.

    - `tool` — name of the tool (read_file, write_file, shell, fetch_url).
    - `decision` — what the broker decided: "allowed", "denied: <reason>",
      "routed via tor", etc. Human-readable; one short line.
    - `args` — relevant inputs (path, command, url, …). Long values are
      truncated by `_summarize_arg`.
    - `result_ok` / `result_summary` — outcome of the call after the
      decision. None for pre-action logs that don't have an outcome yet.

    Silently skipped when trace logging is disabled in broker config.
    Errors during journaling are logged but never re-raised — the agent's
    tool call must not fail because the journal is unwritable.
    """
    if not is_enabled("trace_log_enabled"):
        return
    now = now or dt.datetime.now()
    path = _journal_path(project_dir, now)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        header_new = not path.exists()
        lines: list[str] = []
        if header_new:
            lines.append(f"# broker journal — {now:%Y-%m-%d}\n")
        lines.append(f"## {now:%H:%M:%S} — `{tool}` — {decision}")
        if args:
            for k, v in args.items():
                lines.append(f"- **{k}:** {_summarize_arg(v)}")
        if result_ok is not None:
            status = "ok" if result_ok else "fail"
            lines.append(f"- **outcome:** {status}")
        if result_summary:
            lines.append(f"- **result:** {_summarize_arg(result_summary)}")
        lines.append("")  # blank line between entries
        with path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        log.warning("broker journal write failed (%s)", e)


# ---------------------------------------------------------------------------
# Canned denial messages — return these from the tool runners so the
# agent gets actionable, consistent feedback when something's off-limits.
# ---------------------------------------------------------------------------

def denial_off_read_allowlist(path: str) -> str:
    return (
        f"error: cannot read {path} — its prefix isn't on the file-read "
        f"allowlist. add the prefix to rness/policies/allowlists.md "
        f"(under '## File-read prefixes') if this path should be reachable, "
        f"then retry."
    )


def denial_off_write_allowlist(path: str) -> str:
    return (
        f"error: cannot write to {path} — its prefix isn't on the "
        f"file-read-write allowlist. add the prefix to "
        f"rness/policies/allowlists.md (under '## File-read-write prefixes') "
        f"if writes here should be allowed. note this is the stricter list "
        f"— read-only prefixes don't imply writability."
    )


def denial_protected_dir(reason: str) -> str:
    return f"error: {reason}"


def denial_off_internet_allowlist_no_tor(host: str) -> str:
    return (
        f"error: cannot fetch from {host} — it's not on the internet "
        f"allowlist, and the broker's Tor-for-off-allowlist toggle is off. "
        f"add {host} to rness/policies/allowlists.md (under '## Internet "
        f"domains') for direct fetches, or re-enable Tor routing in the "
        f"broker pane (top-nav 'broker' button) to fetch arbitrary domains "
        f"anonymously."
    )


def denial_tool_disabled(tool: str) -> str:
    return (
        f"error: the {tool} tool is disabled in the broker config. "
        f"re-enable it in the broker pane (top-nav 'broker' button), "
        f"or use a different tool to achieve the same end."
    )
