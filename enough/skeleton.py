"""Generate the `.rness/` and `infoworld/` skeleton in a fresh project directory.

Called at startup by `enough.__main__`. If `.rness/` already exists, the function
is a no-op and returns False. Otherwise it writes the seed files specified in the
v0.01 bootstrap spec and returns True.
"""

from __future__ import annotations

from pathlib import Path

AGENT_MD = """\
# Agent Identity

You are a fresh "enough" agent. You have no specific identity at creation, but
you exist to assist the user in defining UX paradigms and then using them to
complete whatever complex knowledge work their hearts desire.

Your first job is to help the user figure out what they want this instance of
enough to be. Ask them:

- What kind of work will they do in this project directory?
- What should your personality and communication style be?
- What tools or skills would be most useful?

Once you understand their needs, help them edit this file (AGENT.md) to define
your identity. You can use the `write_file` tool to update this file directly.

Remember: you are one instance of enough. If the user needs a different agent
for a different purpose, they can launch another instance in another directory.
"""

MOTIVATION_MD = """\
# Motivation

This file tracks your evolving drive and accumulated learning across sessions.

It starts empty. The user can add things directly or ask you to add them. After
each meaningful session, propose updates to this file that capture:

- What you learned about the user's preferences and working style
- What approaches worked well or poorly
- What priorities have emerged
- What you should remember for next time

The user approves or edits your proposed updates before they're saved.
"""

PARADIGM_DEFAULT_MD = """\
# Default Paradigm

This is the base interaction paradigm. It defines how sessions work.

## Session Structure
- Single agent, conversational mode
- No specific phase structure — freeform interaction

## Output Conventions
- Respond in plain text unless the user requests a specific format
- When creating files, explain what you're creating and why before doing it
- When using shell commands, show the command before executing it

## Archival Policy
- All exchanges are logged to session-logs/
- MOTIVATION.md updates are proposed at session end, not applied automatically

## Security Posture
- Tool use is unrestricted within the project directory
- No network access (you are offline)
- No access outside the project directory
"""

USER_PROFILE_MD = """\
# User Profile

This file stores information about the user that helps you work with them
effectively.

It starts empty. Update it as you learn about the user's preferences,
expertise, communication style, and goals.
"""

MODELS_PROVIDERS_MD = """\
# Model Providers

## Local (default)
- Provider: llama-server (llama.cpp)
- URL: http://localhost:8080
- Model: [detected at runtime or configured by user]
"""

INFOWORLD_README = """\
# infoworld/

A grounded truth store. The model is instructed to check this directory for
relevant knowledge before answering from training data.

## Subdirectories

- `wiki/` — Wikipedia article dumps (user-populated; see the enough README for
  how to download and extract plaintext from ZIM files or database dumps).
- `personal/` — Whatever reference material you want the agent to treat as
  authoritative: meeting notes, project docs, reading excerpts, bibles, etc.

For v0.01, the model greps these files using the `shell` tool. Future versions
will provide indexed search.
"""

SKELETON_FILES: dict[str, str] = {
    ".rness/AGENT.md": AGENT_MD,
    ".rness/MOTIVATION.md": MOTIVATION_MD,
    ".rness/paradigms/default.md": PARADIGM_DEFAULT_MD,
    ".rness/knowledge/user-profile.md": USER_PROFILE_MD,
    ".rness/models/providers.md": MODELS_PROVIDERS_MD,
    "infoworld/README.md": INFOWORLD_README,
}

EMPTY_DIRS: tuple[str, ...] = (
    ".rness/skills",
    ".rness/routines",
    ".rness/policies",
    ".rness/knowledge/session-logs",
    "infoworld/wiki",
    "infoworld/personal",
)


def ensure_skeleton(project_dir: Path) -> bool:
    """Create `.rness/` and `infoworld/` scaffolding if missing.

    Returns True if we created anything, False if `.rness/` already existed.
    """
    rness = project_dir / ".rness"
    if rness.exists():
        return False

    for rel, body in SKELETON_FILES.items():
        target = project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    for rel in EMPTY_DIRS:
        (project_dir / rel).mkdir(parents=True, exist_ok=True)
        # A .gitkeep in empty dirs so they survive `git add`.
        (project_dir / rel / ".gitkeep").touch()

    return True
