"""Assemble the system prompt fresh from `.rness/` on every request.

Spec: edits to AGENT.md, MOTIVATION.md, or paradigm files take effect on the
next message. No caching.
"""

from __future__ import annotations

from pathlib import Path

TOOL_INSTRUCTIONS = """\
You have access to the following tools. To use a tool, emit exactly the XML
tag format shown below. The harness will detect the tool call, execute it, and
return the result as a user message starting with `<tool_result name="...">`.
After receiving the result, continue your response.

Do not wrap tool tags inside code fences; the harness parses them as raw text.

Available tools:

<tool name="read_file">
<path>relative/path/to/file</path>
</tool>

<tool name="write_file">
<path>relative/path/to/file</path>
<content>
file contents here
</content>
</tool>

<tool name="shell">
<command>ls -la</command>
</tool>

Rules:
- All paths are relative to the project directory. Absolute paths and `../`
  traversal are rejected.
- `write_file` creates parent directories automatically.
- `shell` executes in the project directory. stdout and stderr are captured
  and returned. There is no sandbox — be deliberate.
- After a tool call, the harness will send back:
  <tool_result name="toolname" path="..." (or command="...")>
  [result or error]
  </tool_result>
- You may chain tool calls across turns. The harness caps a single user turn
  at 10 tool iterations.
"""

HARNESS_CONTEXT_TMPL = """\
You are running inside an "enough" harness — a paradigmless personal computer
that the user configures through plain-text conventions.

- Project directory: {project_dir}
- Your own configuration files ALL live under `.rness/`. Canonical paths:
    - `.rness/AGENT.md`             — your identity
    - `.rness/MOTIVATION.md`        — evolving drive
    - `.rness/paradigms/default.md` — active interaction paradigm
    - `.rness/knowledge/user-profile.md` — what you know about the user
  When editing any of these, always use the full path (e.g.
  `<path>.rness/AGENT.md</path>`, not just `AGENT.md`). Tool paths are
  resolved from the project root, so a bare `AGENT.md` would create a NEW
  file at the project root — almost never what you or the user want.
- The `infoworld/` directory contains grounded knowledge (offline reference
  material). When the user asks something that could be answered from stored
  knowledge, prefer grepping or reading from `infoworld/` over relying on
  training data. Use `shell` with `grep -r` for discovery.
- All exchanges are logged to `.rness/knowledge/session-logs/`. You do not
  need to write the log yourself; the harness handles it.
"""


def _read_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def _section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"# {title}\n\n{body}\n"


def _read_disabled_skills(rness: Path) -> set[str]:
    """Names listed (one per line) in .rness/skills/.disabled are skipped."""
    f = rness / "skills" / ".disabled"
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def list_skills(rness: Path) -> list[tuple[str, bool]]:
    """Return [(name, enabled), ...] for every skill present, in stable order."""
    skills_dir = rness / "skills"
    if not skills_dir.is_dir():
        return []
    names: list[str] = []
    seen: set[str] = set()
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name not in seen:
            seen.add(name); names.append(name)
    for flat in sorted(skills_dir.glob("*.md")):
        name = flat.stem
        if name not in seen:
            seen.add(name); names.append(name)
    disabled = _read_disabled_skills(rness)
    return [(n, n not in disabled) for n in names]


def set_skill_enabled(rness: Path, name: str, enabled: bool) -> None:
    """Add or remove `name` from .rness/skills/.disabled."""
    f = rness / "skills" / ".disabled"
    current = _read_disabled_skills(rness)
    if enabled:
        current.discard(name)
    else:
        current.add(name)
    f.parent.mkdir(parents=True, exist_ok=True)
    if current:
        f.write_text("\n".join(sorted(current)) + "\n", encoding="utf-8")
    else:
        # Keep the file absent when nothing is disabled — less clutter.
        if f.exists():
            f.unlink()


def _load_skills(rness: Path) -> str:
    """Concatenate every ENABLED skill's content into one block.

    Two layouts supported:
      .rness/skills/<name>/SKILL.md   — folder-based (Claude Code convention)
      .rness/skills/<name>.md         — flat
    Skills listed in .rness/skills/.disabled are skipped.
    """
    skills_dir = rness / "skills"
    if not skills_dir.is_dir():
        return ""
    disabled = _read_disabled_skills(rness)
    parts: list[str] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name in disabled:
            continue
        text = _read_or_empty(skill_md)
        if text:
            parts.append(f"## {name}\n\n{text}")
    for flat in sorted(skills_dir.glob("*.md")):
        name = flat.stem
        if name in disabled:
            continue
        text = _read_or_empty(flat)
        if text:
            parts.append(f"## {name}\n\n{text}")
    return "\n\n".join(parts)


def _load_policies(rness: Path) -> str:
    """Concatenate every policy under .rness/policies/ into one block."""
    policies_dir = rness / "policies"
    if not policies_dir.is_dir():
        return ""
    parts: list[str] = []
    for p in sorted(policies_dir.glob("*.md")):
        text = _read_or_empty(p)
        if text:
            parts.append(f"## {p.stem}\n\n{text}")
    return "\n\n".join(parts)


def assemble_system_prompt(project_dir: Path, active_paradigm: str = "default") -> str:
    """Build the system prompt fresh from .rness/ files.

    Concatenates: AGENT.md, MOTIVATION.md, active paradigm, optional INTENTION.md,
    tool instructions, and the harness-context block.
    """
    rness = project_dir / ".rness"

    agent = _read_or_empty(rness / "AGENT.md")
    motivation = _read_or_empty(rness / "MOTIVATION.md")
    paradigm = _read_or_empty(rness / "paradigms" / f"{active_paradigm}.md")
    if not paradigm and active_paradigm != "default":
        paradigm = _read_or_empty(rness / "paradigms" / "default.md")
    intention = _read_or_empty(rness / "INTENTION.md")

    parts = [
        _section("Identity", agent),
        _section("Motivation", motivation),
        _section("Paradigm", paradigm),
    ]
    policies_block = _load_policies(rness)
    if policies_block:
        parts.append(_section("Policies", policies_block))
    skills_block = _load_skills(rness)
    if skills_block:
        parts.append(_section("Skills", skills_block))
    if intention:
        parts.append(_section("Current Intention", intention))
    parts.append(_section("Tools", TOOL_INSTRUCTIONS))
    parts.append(_section("Context", HARNESS_CONTEXT_TMPL.format(project_dir=project_dir)))

    return "\n".join(p for p in parts if p).strip() + "\n"
