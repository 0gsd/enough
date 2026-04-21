"""Generate the `.rness/` skeleton for a new project.

v0.0.3+ layout:

- `~/enough/defaults/` holds the source-of-truth default files (shipped
  with the repo at `<install_root>/defaults/`).
- On first run in a project, `.rness/` is populated with a mix of:
    - **symlinks** into `~/enough/defaults/...` — for files whose
      semantics are "global convention, upgradable centrally" (paradigms,
      policies, models/providers.md, skills, routines).
    - **copies** — for files that diverge per project from the start
      (AGENT.md, MOTIVATION.md, knowledge/user-profile.md).
- `{project}/infoworld` is a symlink to `~/enough/infoworld/` so all
  projects share a common grounded-knowledge store. The infoworld tree
  is auto-created if missing.

If `~/enough/` doesn't exist (dev setup, or enough run before running
bootstrap.sh), the installer defaults directory is located relative to
this package's install path, and `~/enough/infoworld/` is created on
demand.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def _install_defaults_root() -> Path:
    """Return the `defaults/` directory shipped with this install of enough.

    Resolves relative to this package file, so it works whether enough is
    run from ~/enough, a dev clone, or any other location."""
    return Path(__file__).resolve().parents[1] / "defaults"


def _global_infoworld_root() -> Path:
    """The per-user shared infoworld directory. Lives at `~/enough/infoworld/`
    regardless of where the enough package itself is installed."""
    return Path.home() / "enough" / "infoworld"


# ---------------------------------------------------------------------------
# Per-file policy: how each default file should appear in a new .rness/.
# ---------------------------------------------------------------------------

# (src_rel_to_defaults, dst_rel_to_project, mode)
# mode: "symlink" | "copy"
_SKELETON_PLAN: tuple[tuple[str, str, str], ...] = (
    ("AGENT.md",                       ".rness/AGENT.md",                        "copy"),
    ("MOTIVATION.md",                  ".rness/MOTIVATION.md",                   "copy"),
    ("paradigms/default.md",           ".rness/paradigms/default.md",            "symlink"),
    ("policies/requests.md",           ".rness/policies/requests.md",            "symlink"),
    ("policies/context-management.md", ".rness/policies/context-management.md",  "symlink"),
    ("policies/read-allowlist.md",     ".rness/policies/read-allowlist.md",      "symlink"),
    ("models/providers.md",            ".rness/models/providers.md",             "symlink"),
)

# Project-local files not sourced from defaults/ (generated inline).
_PROJECT_LOCAL_FILES: dict[str, str] = {
    ".rness/knowledge/user-profile.md": (
        "# User Profile\n"
        "\n"
        "This file stores information about the user that helps you work with them\n"
        "effectively.\n"
        "\n"
        "It starts empty. Update it as you learn about the user's preferences,\n"
        "expertise, communication style, and goals.\n"
    ),
}

# Empty dirs to create in every project.
_EMPTY_DIRS: tuple[str, ...] = (
    ".rness/skills",
    ".rness/routines",
    ".rness/knowledge/session-logs",
    ".rness/requests",
    ".rness/requests/done",
)

# Infoworld README lives at the GLOBAL infoworld root so it appears once
# across all projects sharing that symlinked directory.
_INFOWORLD_README = """\
# infoworld/

A grounded truth store shared across every enough project on this machine.
It lives at `~/enough/infoworld/` and is symlinked into each project as
`{project}/infoworld`. The model is instructed to check these files for
relevant knowledge before answering from training data.

## Subdirectories

- `wiki/` — Wikipedia article dumps (user-populated; see the enough README
  for how to download and extract plaintext from ZIM files or database
  dumps).
- `personal/` — Whatever reference material YOU want the agent to treat as
  authoritative: meeting notes, project docs, reading excerpts, bibles, etc.
- `public/` — Reference material that could reasonably be shared or
  published (same behavior as `personal/` for now; the distinction becomes
  meaningful in a future release).

For v0.0.x, the model greps these files using the `shell` tool. Future
versions will provide indexed search.
"""


# ---------------------------------------------------------------------------
# Legacy constants (kept for back-compat with amanuensis/test scripts that
# import them by name). New code should not rely on these.
# ---------------------------------------------------------------------------

def _read_default(rel: str) -> str:
    p = _install_defaults_root() / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


AGENT_MD = _read_default("AGENT.md")
MOTIVATION_MD = _read_default("MOTIVATION.md")
PARADIGM_DEFAULT_MD = _read_default("paradigms/default.md")
POLICY_REQUESTS_MD = _read_default("policies/requests.md")
POLICY_CONTEXT_MGMT_MD = _read_default("policies/context-management.md")
MODELS_PROVIDERS_MD = _read_default("models/providers.md")
USER_PROFILE_MD = _PROJECT_LOCAL_FILES[".rness/knowledge/user-profile.md"]
INFOWORLD_README = _INFOWORLD_README


# ---------------------------------------------------------------------------
# Skeleton creation
# ---------------------------------------------------------------------------

def ensure_global_infoworld() -> Path:
    """Create `~/enough/infoworld/{wiki,personal,public}` with README if missing.
    Returns the absolute path to the infoworld root."""
    root = _global_infoworld_root()
    for sub in ("wiki", "personal", "public"):
        (root / sub).mkdir(parents=True, exist_ok=True)
        (root / sub / ".gitkeep").touch(exist_ok=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(_INFOWORLD_README, encoding="utf-8")
    return root


def _populate_skill_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """For each skill in ~/enough/defaults/skills/, symlink it into the
    project's .rness/skills/. Individual skills can be 'customized' by
    replacing their symlink with a copy. Skills that don't exist in
    defaults/ are ignored here; users can still drop project-local skills
    into `.rness/skills/` directly."""
    src_skills = defaults_root / "skills"
    if not src_skills.is_dir():
        return
    dst_skills = project_dir / ".rness" / "skills"
    dst_skills.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src_skills.iterdir()):
        if entry.name.startswith("."):
            continue
        dst = dst_skills / entry.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(entry.resolve())


def _populate_routine_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """Same shape as skills: any .md file in defaults/routines/ gets symlinked."""
    src = defaults_root / "routines"
    if not src.is_dir():
        return
    dst_dir = project_dir / ".rness" / "routines"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.glob("*.md")):
        dst = dst_dir / entry.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(entry.resolve())


def ensure_skeleton(project_dir: Path) -> bool:
    """Create `.rness/` + `infoworld` symlink if missing. Returns True on
    first-time creation, False if `.rness/` already existed."""
    rness = project_dir / ".rness"
    if rness.exists():
        # Even on re-entry, make sure the global infoworld root exists — it's
        # per-user, not per-project.
        ensure_global_infoworld()
        return False

    defaults = _install_defaults_root()
    if not defaults.is_dir():
        raise FileNotFoundError(
            f"enough defaults not found at {defaults}. "
            "The installation looks broken — re-run bootstrap.sh."
        )

    # Ensure global infoworld exists (per user).
    infoworld_root = ensure_global_infoworld()

    # Symlinks + copies from defaults.
    for src_rel, dst_rel, mode in _SKELETON_PLAN:
        src = defaults / src_rel
        if not src.is_file():
            continue  # missing default = skip this entry (e.g. custom fork)
        dst = project_dir / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "symlink":
            dst.symlink_to(src.resolve())
        elif mode == "copy":
            shutil.copy2(src, dst)

    # Per-project files.
    for rel, body in _PROJECT_LOCAL_FILES.items():
        target = project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    # Empty dirs with .gitkeep.
    for rel in _EMPTY_DIRS:
        d = project_dir / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()

    # Skills / routines symlink fan-out (from defaults/skills, defaults/routines).
    _populate_skill_symlinks(project_dir, defaults)
    _populate_routine_symlinks(project_dir, defaults)

    # infoworld/ symlink at project root.
    infoworld_link = project_dir / "infoworld"
    if not infoworld_link.exists() and not infoworld_link.is_symlink():
        infoworld_link.symlink_to(infoworld_root.resolve(), target_is_directory=True)

    return True
