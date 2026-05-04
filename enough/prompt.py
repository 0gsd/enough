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

## Where to put files you produce or consume

- **Outputs** (anything you produce that the user might want to read, keep,
  or share — drafts, chapters, analyses, generated code, exports): write to
  `.rness/io/output/`. If the user names a subfolder ("put it in /chapters/"
  or "save under research/"), mirror that under `.rness/io/output/` —
  e.g. `.rness/io/output/chapters/01.md`,
  `.rness/io/output/research/notes.md`. Default to a flat layout when no
  subfolder is named.
- **Inputs** (files the user hands you for one task — pasted text, source
  documents, transcripts to work from): expect them in `.rness/io/input/`.
  This is for per-task reference material; durable knowledge belongs in
  `infoworld/`.
- **`.rness/requests/`** is reserved for the request-tracking markdown files
  you write per the requests policy. Don't put user artifacts there. If the
  user asks you to "put X in requests/", redirect: write the artifact under
  `.rness/io/output/` and only put a tracking entry in `.rness/requests/`.
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
    """Names listed (one per line) in .rness/.skills/.disabled are skipped."""
    f = rness / ".skills" / ".disabled"
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def list_skills(rness: Path) -> list[tuple[str, bool]]:
    """Return [(name, enabled), ...] for every skill present, in stable order."""
    skills_dir = rness / ".skills"
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
    """Add or remove `name` from .rness/.skills/.disabled."""
    f = rness / ".skills" / ".disabled"
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


def _skill_root_note(root: str) -> str:
    """Preamble that tells the model where a skill's companion files live,
    so it prefixes relative paths (e.g. ``scripts/foo.py``) correctly when
    using the ``shell`` or ``read_file`` tools."""
    return (
        f"> **Skill root:** `{root}`  \n"
        f"> Any relative path referenced in this skill's docs (e.g. "
        f"`scripts/foo.py`, `reference/bar.md`) resolves under that root. "
        f"When you invoke `shell` or `read_file`, prefix the path with "
        f"`{root}` — `shell` runs in the project root, not the skill root."
    )


def _load_skills(rness: Path) -> str:
    """Concatenate every ENABLED skill's content into one block.

    Two layouts supported:
      .rness/.skills/<name>/SKILL.md   — folder-based (Claude Code convention)
      .rness/.skills/<name>.md         — flat
    Skills listed in .rness/.skills/.disabled are skipped.
    Each folder-based skill's section begins with a path-hint preamble so
    the agent knows where companion files live.
    """
    skills_dir = rness / ".skills"
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
            root = f".rness/.skills/{name}/"
            parts.append(f"## {name}\n\n{_skill_root_note(root)}\n\n{text}")
    for flat in sorted(skills_dir.glob("*.md")):
        name = flat.stem
        if name in disabled:
            continue
        text = _read_or_empty(flat)
        if text:
            # Flat skills have no companion-files root, so no path note.
            parts.append(f"## {name}\n\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Roles — toggleable consultant personas the orchestrator can confer with.
# Same on/off file model as skills, different placement in the prompt:
# roles aren't capabilities you stack, they're voices you can summon.
# ---------------------------------------------------------------------------

def _read_disabled_roles(rness: Path) -> set[str]:
    """Names listed (one per line) in .rness/.roles/.disabled are skipped."""
    f = rness / ".roles" / ".disabled"
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def list_roles(rness: Path) -> list[tuple[str, bool]]:
    """Return [(name, enabled), ...] for every role present, in stable order."""
    roles_dir = rness / ".roles"
    if not roles_dir.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(roles_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        names.append(entry.name)
    disabled = _read_disabled_roles(rness)
    return [(n, n not in disabled) for n in names]


def set_role_enabled(rness: Path, name: str, enabled: bool) -> None:
    """Add or remove `name` from .rness/.roles/.disabled."""
    f = rness / ".roles" / ".disabled"
    current = _read_disabled_roles(rness)
    if enabled:
        current.discard(name)
    else:
        current.add(name)
    f.parent.mkdir(parents=True, exist_ok=True)
    if current:
        f.write_text("\n".join(sorted(current)) + "\n", encoding="utf-8")
    else:
        if f.exists():
            f.unlink()


_ROLES_FRAMING = (
    "You have access to the following Role agents as **consultants**, not "
    "as facets of yourself. They are voices with their own values, blind "
    "spots, and ways of pushing back. You — the core agent defined above — "
    "remain the orchestrator: you make the decisions, you talk to the "
    "user, you do the work. Roles are advisors you can summon when a "
    "decision deserves a second perspective.\n\n"
    "Ways to use them:\n"
    "- Solicit input: \"Let me check this with <role>...\" then answer in "
    "their voice, citing what they'd flag.\n"
    "- Stage a debate: when two enabled roles would disagree, sketch the "
    "exchange briefly before resolving as yourself.\n"
    "- Spot-check decisions: at meaningful inflection points (committing to "
    "an approach, finalizing a plan), ask whether any active role would "
    "object.\n\n"
    "Do not *become* a role unless explicitly asked to roleplay. Default "
    "to channeling them as quoted advisors. Final decisions, tool calls, "
    "and direct address to the user are always yours."
)


def _load_roles(rness: Path) -> str:
    """Concatenate every ENABLED role's AGENT.md + MOTIVATION.md into one
    block, framed as the consultant model above. Each role gets a `## Role:
    <name>` heading so the model can address them by name."""
    roles_dir = rness / ".roles"
    if not roles_dir.is_dir():
        return ""
    disabled = _read_disabled_roles(rness)
    sections: list[str] = []
    for entry in sorted(roles_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        name = entry.name
        if name in disabled:
            continue
        agent_md = _read_or_empty(entry / "AGENT.md")
        motiv_md = _read_or_empty(entry / "MOTIVATION.md")
        if not agent_md and not motiv_md:
            continue
        body_parts: list[str] = []
        if agent_md:
            body_parts.append(f"### Identity\n\n{agent_md}")
        if motiv_md:
            body_parts.append(f"### Motivation\n\n{motiv_md}")
        sections.append(f"## Role: {name}\n\n" + "\n\n".join(body_parts))
    if not sections:
        return ""
    return _ROLES_FRAMING + "\n\n" + "\n\n".join(sections)


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
    ]
    roles_block = _load_roles(rness)
    if roles_block:
        # Sit between Motivation and Paradigm — close to identity (these
        # are voices you have access to) but distinct from it (you aren't
        # them; you can consult them).
        parts.append(_section("Active Role Consultants", roles_block))
    parts.append(_section("Paradigm", paradigm))
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

    drift_note = _drift_notice(project_dir)
    if drift_note:
        parts.append(_section("Available Updates", drift_note))

    return "\n".join(p for p in parts if p).strip() + "\n"


def _drift_notice(project_dir: Path) -> str:
    """Build a system-prompt section that nudges the agent to offer the
    user a project update when `~/enough/defaults/` has new entries this
    `.rness/` is missing. Returns "" when there's no drift — most
    projects, most of the time."""
    # Imported lazily so the module-level import graph stays clean
    # (skeleton imports Path & shutil, doesn't pull in prompt.py).
    from .skeleton import detect_drift
    missing = detect_drift(project_dir)
    if not missing:
        return ""
    listed = "\n".join(
        f"- `{dst}` ({mode}, from `defaults/{src}`)"
        for (src, dst, mode) in missing
    )
    return (
        "A newer version of enough has been installed at `~/enough/`, and "
        "this project's `.rness/` is missing some defaults that have since "
        "been added:\n\n"
        f"{listed}\n\n"
        "On your FIRST response to the user this session, mention that "
        "these updates are available and offer to apply them. If the user "
        "agrees, instruct them to type `/update-enough` into the chat box "
        "(it's a slash command intercepted by the harness — not something "
        "you can run yourself). If the user declines or says \"not now\", "
        "tell them they can run `/update-enough` any time later. Do NOT "
        "raise this again on subsequent turns — once is enough.\n\n"
        "(If the user has already responded and you've already mentioned "
        "this earlier in the session, don't bring it up again — drop "
        "straight into whatever they're asking about.)"
    )
