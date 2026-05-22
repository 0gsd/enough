"""Assemble the system prompt fresh from `rness/` on every request.

Spec: edits to AGENT.md, MOTIVATION.md, or paradigm files take effect on the
next message. No caching.
"""

from __future__ import annotations

import re
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

<tool name="fetch_url">
<url>https://example.com/some-article</url>
</tool>

<tool name="read_highlights">
<path>relative/path/to/file.md</path>
<color>green</color>
</tool>

<tool name="navigate_to_highlight">
<path>relative/path/to/file.md</path>
<color>green</color>
<index>2</index>
</tool>

<tool name="cloud_pipeline">
<content>
{
  "steps": [
    {"prompt": "Write chapter 1 of a novel about …"},
    {"prompt": "Write chapter 2, picking up from chapter 1 …"},
    {"prompt": "Write chapter 3 …"}
  ],
  "compile": {"method": "concat", "separator": "\n\n---\n\n"},
  "final_pass": {
    "prompt": "Proofread the following manuscript for typos, internal consistency, and prose flow. Return the corrected text only.\n\n{compiled}"
  },
  "output_path": "rness/io/output/cloud-pipeline/novel-draft.md",
  "model": "openrouter/auto"
}
</content>
</tool>

Rules:
- All paths are relative to the project directory. Absolute paths and `../`
  traversal are rejected.
- `write_file` creates parent directories automatically.
- `shell` executes in the project directory. stdout and stderr are captured
  and returned. There is no sandbox — be deliberate.
- `fetch_url` is the canonical way to read from the web — prefer it over
  `shell` + `curl`. It handles internet-allowlist routing (direct fetch
  for allowlisted domains; transparent Tor anonymization for off-allowlist
  ones), converts HTML to markdown via pandoc, caches the result under
  `rness/io/input/<timestamp>-<hash>-<slug>.md`, and indexes it in
  `rness/io/input/_broker-index.md`. The tool result is just a short
  preview + the cache path — read the full content with `read_file` if
  needed. This keeps fetched documents out of your context window.
- `cloud_pipeline` is the broker-driven multi-step batch tool for
  OpenRouter. Use it when the user wants a single large job done by a
  cloud model in many sequential calls — generating long-form content
  by section (e.g. "write 36 chapters"), running per-chunk transformations
  across a corpus, or producing a draft and then a single proofread/
  edit pass over the compiled result. The broker runs every step server-
  side (so you don't have to loop), caches each response under
  `rness/io/cloud-cache/<timestamp>-<slug>.md`, optionally compiles
  them, optionally final-passes, and returns a short structured summary
  plus output path. Pre-conditions: the `local_models_only` broker
  toggle must be OFF and the OpenRouter key must be present + healthy.
  The full per-step text never enters your context window — read
  individual cache files with `read_file` only when you need to inspect
  output. Don't use for one-off chat-style requests; for those, just
  respond normally (the active OPRO-API model will route your reply
  through the cloud automatically).
  - **compile.method** has two options: `"concat"` joins step outputs
    verbatim with a separator; `"summarize_each"` makes a follow-up
    cloud call per step to produce a one-paragraph summary, and the
    compiled artifact (plus any final_pass input) is built from the
    summaries instead of the full step bodies. Full step outputs are
    still cached individually on disk. Use `summarize_each` when a
    final pass over all steps would otherwise blow past the model's
    context — e.g. when arc-level editing a 36-chapter draft where
    each chapter is 5k words. The `summary_prompt` field accepts a
    template containing the literal `{step}` placeholder, which is
    substituted with each step's full text before sending.
- After a tool call, the harness will send back:
  <tool_result name="toolname" path="..." (or command="...", url="..."")>
  [result or error]
  </tool_result>
- You may chain tool calls across turns. The harness caps a single user turn
  at 10 tool iterations.
- All tool calls flow through the broker, which writes a journal entry to
  `rness/knowledge/session-logs/<date>-broker.md`. You don't write that
  file directly; the harness does.

## Working with review-mode color highlights

Review mode (the full-frame markdown reader) lets the user paint
sections of a document in four colors — yellow, green, blue, pink —
which persist across sessions in a per-doc dotted JSON sidecar
(`<dirname>/.<filename>.highlights.json`). When the user references a
color ("the pink words", "all the green sections", "edit the yellow
parts one by one"), they are talking about these highlights.

- `read_highlights` returns the current highlights for a document,
  optionally filtered by color. Use it whenever a color is named —
  don't guess what's highlighted.
- `navigate_to_highlight` asks the UI to scroll the open review pane
  to a specific saved highlight. Use it when working through a set
  ("now the second green one") so the user can see what you're
  about to act on.
- For "edit the green sections one by one" workflows: read all green
  highlights, then for each, navigate to it, propose / apply the
  edit, confirm with the user, navigate to the next.

## Review-mode selection edits (with save/undo theatre)

When the user sends a chat-pill message with an active text selection
in review mode, the harness automatically prepends a context
preamble to their message. It looks like this:

    [review-mode selection in path/to/file.md, line 23]
    ```
    the exact selected text
    ```

    rewrite this to be funnier

When you see that preamble, the user is asking you to operate ONLY
on the quoted snippet, NOT to refactor the whole document.

Workflow:

1. `read_file` the path so you have the full current contents.
2. Locate the selected snippet inside the source. Be exact —
   character-for-character match. (Markdown delimiters around the
   snippet are part of the source you should preserve verbatim.)
3. `write_file` the full document with EXACTLY the selected text
   replaced by your new version. Everything else in the file must
   be byte-identical.
4. End your reply with a one-line summary of what you changed and
   the literal phrase **"save or undo?"** — that's the cue the user
   is watching for.

The harness:
- Always stashes the file's previous contents to a `.undo` sibling
  before any `write_file`, so the user's "undo" button works.
- Surfaces a "✓ save" / "↶ undo" affordance in the chat pill the
  moment the write lands. The user clicks one. You don't need to
  poll — just write and ask.
- Never auto-applies the edit to anything beyond what you wrote.
  If the user undoes, the file is restored byte-for-byte.

Don't undo on the user's behalf. Don't make multiple speculative
edits in one turn. The pattern is: one selection in, one focused
edit out, one explicit save/undo confirmation.

## Keep going until the request is fulfilled

A tool call is never a complete response on its own — it's a step toward
something the user asked for. When a `<tool_result>` arrives, the user is
still waiting for the work that result was leading to. Your next move is
**always** one of:

1. **Emit another tool call** to make further progress (read the next file,
   write the output, run the next shell command, etc.).
2. **Produce the final user-facing answer** that uses what the tool result
   gave you (the analysis, the synthesis, the explanation).

Do NOT end your turn immediately after a `<tool_result>` with empty or
near-empty content. If you find yourself about to do that, ask: "did I
actually do what the user asked, or did I just *prepare* to do it?" If
the answer is "prepared," keep going. The user should not have to nudge
you with "everything ok?" to make you continue work you already started.

**Implicit multi-step asks are the norm, not the exception.** "Use the
analyzer skill on this file," "translate this document," "summarize this
report" all decompose into at least two steps (read the input → produce
the output). Plan to do both before ending the turn. If the work is too
large to finish in one turn, say so explicitly in your final reply and
write a request-tracking file (see the requests policy) — don't just
stop silently.
"""

HARNESS_CONTEXT_TMPL = """\
You are running inside an "enough" harness — a paradigmless personal computer
that the user configures through plain-text conventions.

- Project directory: {project_dir}
- Your own configuration files ALL live under `rness/`. Canonical paths:
    - `rness/AGENT.md`                    — your identity
    - `rness/MOTIVATION.md`               — evolving drive
    - `rness/paradigms/default.md`        — active interaction paradigm
    - `rness/knowledge/project-profile.md` — living notes about this project
                                             (piped into your prompt every
                                             turn; update per the
                                             profile-maintenance policy)
  When editing any of these, always use the full path (e.g.
  `<path>rness/AGENT.md</path>`, not just `AGENT.md`). Tool paths are
  resolved from the project root, so a bare `AGENT.md` would create a NEW
  file at the project root — almost never what you or the user want.
- The `infoworld/` directory contains grounded knowledge (offline reference
  material). When the user asks something that could be answered from stored
  knowledge, prefer grepping or reading from `infoworld/` over relying on
  training data. Use `shell` with `grep -r` for discovery.
- All exchanges are logged to `rness/knowledge/session-logs/`. You do not
  need to write the log yourself; the harness handles it.

## Where to put files you produce or consume

- **Outputs** (anything you produce that the user might want to read, keep,
  or share — drafts, chapters, analyses, generated code, exports): write to
  `rness/io/output/`. If the user names a subfolder ("put it in /chapters/"
  or "save under research/"), mirror that under `rness/io/output/` —
  e.g. `rness/io/output/chapters/01.md`,
  `rness/io/output/research/notes.md`. Default to a flat layout when no
  subfolder is named.
- **Inputs** (files the user hands you for one task — pasted text, source
  documents, transcripts to work from): expect them in `rness/io/input/`.
  This is for per-task reference material; durable knowledge belongs in
  `infoworld/`.
- **`rness/requests/`** is reserved for the request-tracking markdown files
  you write per the requests policy. Don't put user artifacts there. If the
  user asks you to "put X in requests/", redirect: write the artifact under
  `rness/io/output/` and only put a tracking entry in `rness/requests/`.
"""


def _read_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def _is_stock_project_profile(body: str) -> bool:
    """Detect the unmodified seed template shipped by `skeleton.py` so we
    don't waste tokens piping placeholder prose into the system prompt
    every turn. Match on a stable phrase that won't appear once the agent
    has written real observations."""
    return "Starts empty. The harness pipes this file" in body


def _section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    return f"# {title}\n\n{body}\n"


def _read_disabled_skills(rness: Path) -> set[str]:
    """Names listed (one per line) in rness/skills/.disabled are skipped."""
    f = rness / "skills" / ".disabled"
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def list_skills(rness: Path) -> list[tuple[str, bool, str]]:
    """Return [(name, enabled, tooltip), ...] for every skill present, in
    stable order. `tooltip` is the user-facing UI tooltip from the bottom
    `enough-tooltip-text:` field of the skill's SKILL.md (or flat .md);
    "" if not set."""
    skills_dir = rness / "skills"
    if not skills_dir.is_dir():
        return []
    entries: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name not in seen:
            seen.add(name)
            entries.append((name, skill_md))
    for flat in sorted(skills_dir.glob("*.md")):
        name = flat.stem
        if name not in seen:
            seen.add(name)
            entries.append((name, flat))
    disabled = _read_disabled_skills(rness)
    out: list[tuple[str, bool, str]] = []
    for name, path in entries:
        tooltip = _extract_enough_tooltip(_read_or_empty(path))
        out.append((name, name not in disabled, tooltip))
    return out


def set_skill_enabled(rness: Path, name: str, enabled: bool) -> None:
    """Add or remove `name` from rness/skills/.disabled."""
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
      rness/skills/<name>/SKILL.md   — folder-based (Claude Code convention)
      rness/skills/<name>.md         — flat
    Skills listed in rness/skills/.disabled are skipped.
    Each folder-based skill's section begins with a path-hint preamble so
    the agent knows where companion files live.
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
            root = f"rness/skills/{name}/"
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
    """Names listed (one per line) in rness/roles/.disabled are skipped."""
    f = rness / "roles" / ".disabled"
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def list_roles(rness: Path) -> list[tuple[str, bool, str]]:
    """Return [(name, enabled, tooltip), ...] for every role present, in
    stable order. `tooltip` is the user-facing UI tooltip from the bottom
    `enough-tooltip-text:` field of the role's AGENT.md; "" if not set."""
    roles_dir = rness / "roles"
    if not roles_dir.is_dir():
        return []
    entries: list[tuple[str, Path]] = []
    for entry in sorted(roles_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        entries.append((entry.name, entry / "AGENT.md"))
    disabled = _read_disabled_roles(rness)
    out: list[tuple[str, bool, str]] = []
    for name, agent_path in entries:
        text = _read_or_empty(agent_path) if agent_path.is_file() else ""
        tooltip = _extract_enough_tooltip(text)
        out.append((name, name not in disabled, tooltip))
    return out


def set_role_enabled(rness: Path, name: str, enabled: bool) -> None:
    """Add or remove `name` from rness/roles/.disabled."""
    f = rness / "roles" / ".disabled"
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
    roles_dir = rness / "roles"
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
    """Concatenate every policy under rness/policies/ into one block."""
    policies_dir = rness / "policies"
    if not policies_dir.is_dir():
        return ""
    parts: list[str] = []
    for p in sorted(policies_dir.glob("*.md")):
        text = _read_or_empty(p)
        if text:
            parts.append(f"## {p.stem}\n\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Paradigms — exactly one active at a time; the agent and user can switch.
# Each paradigm file may carry a YAML-style frontmatter block:
#     ---
#     name: <slug>
#     description: <one-line when-to-use>
#     ---
# Missing or malformed frontmatter is tolerated: name falls back to the
# filename stem, description to "".
# ---------------------------------------------------------------------------

_ACTIVE_PARADIGM_FILE = "active-paradigm"


# A user-facing UI tooltip can be placed at the bottom of any paradigm/skill/role
# file as a single line of the form:
#     enough-tooltip-text: "Short user-facing description shown on hover."
# Distinct from the agent-facing `description:` in top frontmatter, which the
# model reads. The tooltip is for the human looking at the toggle list.
_ENOUGH_TOOLTIP_RE = re.compile(
    r'^enough-tooltip-text:\s*(.*?)\s*$',
    re.MULTILINE,
)


def _extract_enough_tooltip(text: str) -> str:
    """Pull the user-facing tooltip from a markdown file's trailing metadata.

    Looks for a line of the form `enough-tooltip-text: "..."` (quotes
    optional) and returns the unquoted value. Returns "" if the field is
    missing or its value is empty. Only the first match is honored."""
    m = _ENOUGH_TOOLTIP_RE.search(text)
    if not m:
        return ""
    value = m.group(1).strip()
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"')
        or (value[0] == "'" and value[-1] == "'")
    ):
        value = value[1:-1]
    return value


def _parse_paradigm_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body_without_frontmatter).

    Recognizes a leading `---` line followed by `key: value` lines and a
    closing `---`. Anything else is treated as no frontmatter."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 2:
        return {}, text
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    meta: dict[str, str] = {}
    for raw in lines[1:end_idx]:
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        meta[k.strip()] = v.strip()
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    return meta, body


def list_paradigms(rness: Path) -> list[tuple[str, str, str]]:
    """Return [(name, description, tooltip), ...] for every paradigm file present.

    `name` defaults to the filename stem when frontmatter is missing.
    `description` is the agent-facing one-liner from top frontmatter (used in
    the paradigm catalog the model sees).
    `tooltip` is the user-facing UI tooltip from the bottom
    `enough-tooltip-text:` field, "" if not set.
    Stable alphabetical order."""
    paradigms_dir = rness / "paradigms"
    if not paradigms_dir.is_dir():
        return []
    out: list[tuple[str, str, str]] = []
    for p in sorted(paradigms_dir.glob("*.md")):
        text = _read_or_empty(p)
        meta, _body = _parse_paradigm_frontmatter(text)
        name = meta.get("name") or p.stem
        desc = meta.get("description", "")
        tooltip = _extract_enough_tooltip(text)
        out.append((name, desc, tooltip))
    return out


def get_active_paradigm(rness: Path) -> str:
    """Read the active paradigm name from `rness/active-paradigm`. Falls
    back to 'default' when the file is missing OR names a paradigm that
    doesn't exist on disk."""
    f = rness / _ACTIVE_PARADIGM_FILE
    name = "default"
    if f.is_file():
        try:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                name = content.splitlines()[0].strip()
        except OSError:
            pass
    if not (rness / "paradigms" / f"{name}.md").is_file():
        return "default"
    return name


def set_active_paradigm(rness: Path, name: str) -> None:
    """Write `name` to `rness/active-paradigm`. Caller is responsible for
    validating the paradigm exists; this just records the choice."""
    f = rness / _ACTIVE_PARADIGM_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(name + "\n", encoding="utf-8")


def _load_active_paradigm_body(rness: Path, active: str) -> str:
    """Read the active paradigm's content, stripping its frontmatter so
    the YAML doesn't leak into the system prompt."""
    p = rness / "paradigms" / f"{active}.md"
    text = _read_or_empty(p)
    if not text:
        return ""
    _meta, body = _parse_paradigm_frontmatter(text)
    return body.strip()


def _load_paradigm_catalog(rness: Path, active: str) -> str:
    """Build a brief catalog of available paradigms for the agent — so it
    knows what alternatives exist and how to switch.

    Returns "" if there's only one paradigm (no choice to make)."""
    items = list_paradigms(rness)
    if len(items) <= 1:
        return ""
    lines = [f"Currently active: **{active}**", ""]
    lines.append(
        "Other paradigms available in this project. To switch, write the "
        "paradigm name (no extension) to `rness/active-paradigm` using "
        "`write_file`. The switch takes effect on the NEXT turn — for "
        "the current turn you remain under the active paradigm above."
    )
    lines.append("")
    for name, desc, _tooltip in items:
        if name == active:
            continue
        if desc:
            lines.append(f"- **{name}** — {desc}")
        else:
            lines.append(f"- **{name}**")
    return "\n".join(lines)


def assemble_system_prompt(project_dir: Path) -> str:
    """Build the system prompt fresh from rness/ files.

    The active paradigm is read from `rness/active-paradigm` on every call,
    so an agent-initiated paradigm switch takes effect on the very next
    invocation of this function (i.e. the next user turn).

    Concatenates: AGENT.md, MOTIVATION.md, Project Profile (per-turn
    working memory), active paradigm + catalog, optional INTENTION.md,
    tool instructions, and the rness-context block.
    """
    rness = project_dir / "rness"

    agent = _read_or_empty(rness / "AGENT.md")
    motivation = _read_or_empty(rness / "MOTIVATION.md")
    project_profile = _read_or_empty(rness / "knowledge" / "project-profile.md")
    active_paradigm = get_active_paradigm(rness)
    paradigm = _load_active_paradigm_body(rness, active_paradigm)
    catalog = _load_paradigm_catalog(rness, active_paradigm)
    intention = _read_or_empty(rness / "INTENTION.md")

    parts = [
        _section("Identity", agent),
        _section("Motivation", motivation),
    ]
    # Project Profile sits adjacent to Motivation — both are "what you've
    # learned" memory the agent grows over time. Skipped when the file is
    # only the stock empty template (no real observations yet) so we don't
    # waste tokens on placeholder prose every turn.
    if project_profile and not _is_stock_project_profile(project_profile):
        parts.append(_section("Project Profile", project_profile))
    roles_block = _load_roles(rness)
    if roles_block:
        # Sit between Motivation and Paradigm — close to identity (these
        # are voices you have access to) but distinct from it (you aren't
        # them; you can consult them).
        parts.append(_section("Active Role Consultants", roles_block))
    parts.append(_section(f"Paradigm: {active_paradigm}", paradigm))
    if catalog:
        parts.append(_section("Paradigm Catalog", catalog))
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
    """Build a brief system-prompt section informing the agent that
    `~/enough/defaults/` has shared defaults this `rness/` is missing.

    The user-facing nudge lives in the empty-hint banner the harness
    renders on the chat pane, NOT in the agent's first response. This
    note exists so the agent has context if the user asks about
    `/update-enough` mid-conversation. Don't raise it unprompted.

    Returns "" when there's no drift — most projects, most of the time."""
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
        "FYI only — do not raise this unprompted.\n\n"
        "A newer version of enough has been installed at `~/enough/`, and "
        "this project's `rness/` is missing some defaults that have since "
        "been added:\n\n"
        f"{listed}\n\n"
        "The harness shows the user a notice in the empty-conversation "
        "pane that lists these and points them at `/update-enough`. You "
        "don't need to mention it; if the user asks what `/update-enough` "
        "is or what's new, you can answer based on the list above."
    )
