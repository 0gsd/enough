"""Generate the `.rness/` skeleton for a new project.

v0.0.3+ layout:

- `~/enough/defaults/` holds the source-of-truth default files (shipped
  with the repo at `<install_root>/defaults/`).
- On first run in a project, `.rness/` is populated with a mix of:
    - **symlinks** into `~/enough/defaults/...` — for files whose
      semantics are "global convention, upgradable centrally" (paradigms,
      policies, models/providers.md, skills, roles).
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
    ("paradigms/translation.md",       ".rness/paradigms/translation.md",        "symlink"),
    ("policies/requests.md",           ".rness/policies/requests.md",            "symlink"),
    ("policies/context-management.md", ".rness/policies/context-management.md",  "symlink"),
    ("policies/allowlists.md",         ".rness/policies/allowlists.md",          "symlink"),
    ("models/providers.md",            ".rness/models/providers.md",             "symlink"),
    ("knowledge/rosetta-primers",      ".rness/knowledge/rosetta-primers",       "symlink"),
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
# Dotted dirs (`.skills`, `.requests`, `.roles`) are intentionally hidden
# from the file tree — they're surfaced through dedicated sidebar
# sections instead, since they're configuration rather than artifacts.
_EMPTY_DIRS: tuple[str, ...] = (
    ".rness/.skills",
    ".rness/knowledge/session-logs",
    ".rness/.requests",
    ".rness/.requests/done",
    ".rness/.roles",
    ".rness/io/input",
    ".rness/io/output",
)


# ---------------------------------------------------------------------------
# Drift detection / opt-in update
# ---------------------------------------------------------------------------
#
# `_SKELETON_PLAN` runs only on first-time `.rness/` creation. That keeps
# us from clobbering project-local edits — but it also means a new shared
# default added to ~/enough/defaults/ (e.g. a new paradigm, a new
# knowledge dir) won't appear in projects whose `.rness/` predates it.
#
# These helpers detect that drift and let the user opt in to receive the
# new defaults via the `/update-enough` slash command. We never overwrite
# anything that already exists in the project — only ADD missing entries.

def _is_skeleton_item_present(project_dir: Path, dst_rel: str, mode: str) -> bool:
    """True iff the skeleton-plan destination already exists. For symlink
    mode we accept any existing file/dir/symlink as 'present' — we don't
    second-guess the user if they replaced a symlink with a real file."""
    dst = project_dir / dst_rel
    return dst.exists() or dst.is_symlink()


def _apply_missing_skeleton_items(
    project_dir: Path,
    defaults: Path,
    plan: tuple[tuple[str, str, str], ...],
) -> list[tuple[str, str, str]]:
    """Apply every plan entry whose destination doesn't already exist.

    Returns the list of entries actually applied. Idempotent: re-running
    on the same project does nothing once everything's in place.
    Never overwrites: an existing file at a destination is left alone."""
    applied: list[tuple[str, str, str]] = []
    for src_rel, dst_rel, mode in plan:
        src = defaults / src_rel
        # symlink targets can be files or dirs; copy needs a file.
        if mode == "copy" and not src.is_file():
            continue
        if mode == "symlink" and not src.exists():
            continue
        if _is_skeleton_item_present(project_dir, dst_rel, mode):
            continue
        dst = project_dir / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "symlink":
            dst.symlink_to(src.resolve())
        elif mode == "copy":
            shutil.copy2(src, dst)
        applied.append((src_rel, dst_rel, mode))
    return applied


def detect_drift(project_dir: Path) -> list[tuple[str, str, str]]:
    """Return skeleton-plan entries whose destinations are missing in
    `project_dir/.rness/`. Empty list = the project is up to date with
    `~/enough/defaults/`.

    This is a read-only check; nothing is mutated. Use `apply_drift` to
    actually pull the missing defaults in."""
    defaults = _install_defaults_root()
    if not defaults.is_dir():
        return []
    missing: list[tuple[str, str, str]] = []
    for src_rel, dst_rel, mode in _SKELETON_PLAN:
        src = defaults / src_rel
        if mode == "copy" and not src.is_file():
            continue
        if mode == "symlink" and not src.exists():
            continue
        if _is_skeleton_item_present(project_dir, dst_rel, mode):
            continue
        missing.append((src_rel, dst_rel, mode))
    return missing


def apply_drift(project_dir: Path) -> list[tuple[str, str, str]]:
    """Pull in any missing skeleton-plan entries from `~/enough/defaults/`.
    Returns what was actually applied. Safe to call on a fully-up-to-date
    project (returns an empty list)."""
    defaults = _install_defaults_root()
    if not defaults.is_dir():
        return []
    return _apply_missing_skeleton_items(project_dir, defaults, _SKELETON_PLAN)

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
    """Sync global skills into `.rness/skills/` and prune dangling symlinks.

    - For each skill in `<defaults>/skills/`: if the project doesn't
      already have an entry with that name, symlink it in and add to
      `.disabled` (new globals default off).
    - For each existing entry in `.rness/skills/`: if it's a symlink whose
      target no longer exists (dangling — usually because the skill was
      removed globally), unlink it. Project-local entries (real dirs or
      files, not symlinks) are never touched.

    The latter makes removal propagate automatically: `rm -rf
    ~/enough/defaults/skills/foo` on the next `enough` launch cleans `foo`
    out of every project using the (now-dangling) symlink."""
    src_skills = defaults_root / "skills"
    dst_skills = project_dir / ".rness" / ".skills"
    dst_skills.mkdir(parents=True, exist_ok=True)

    # 1. Prune dangling symlinks.
    for entry in sorted(dst_skills.iterdir()):
        if entry.is_symlink() and not entry.exists():
            try:
                entry.unlink()
            except OSError:
                pass

    # 2. Sync in any new globals (default-off).
    if not src_skills.is_dir():
        return
    disabled_names: list[str] = []
    for entry in sorted(src_skills.iterdir()):
        if entry.name.startswith("."):
            continue
        dst = dst_skills / entry.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(entry.resolve())
        disabled_names.append(entry.name)

    if disabled_names:
        disabled_file = dst_skills / ".disabled"
        existing = set()
        if disabled_file.is_file():
            existing = {
                ln.strip() for ln in disabled_file.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")
            }
        existing.update(disabled_names)
        disabled_file.write_text("\n".join(sorted(existing)) + "\n", encoding="utf-8")


def _populate_role_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """Sync global Role agents into `.rness/.roles/` and prune dangling
    symlinks. Same shape and lifecycle as skills: each role is a folder
    containing AGENT.md + MOTIVATION.md, default-off (added to .disabled
    on first sync), togglable per-project via the sidebar."""
    src_roles = defaults_root / "roles"
    dst_roles = project_dir / ".rness" / ".roles"
    dst_roles.mkdir(parents=True, exist_ok=True)

    # 1. Prune dangling symlinks (target removed globally).
    for entry in sorted(dst_roles.iterdir()):
        if entry.is_symlink() and not entry.exists():
            try:
                entry.unlink()
            except OSError:
                pass

    # 2. Sync in any new globals (default-off).
    if not src_roles.is_dir():
        return
    disabled_names: list[str] = []
    for entry in sorted(src_roles.iterdir()):
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        dst = dst_roles / entry.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(entry.resolve())
        disabled_names.append(entry.name)

    if disabled_names:
        disabled_file = dst_roles / ".disabled"
        existing = set()
        if disabled_file.is_file():
            existing = {
                ln.strip() for ln in disabled_file.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")
            }
        existing.update(disabled_names)
        disabled_file.write_text("\n".join(sorted(existing)) + "\n", encoding="utf-8")


def _migrate_to_dotted(project_dir: Path) -> None:
    """v0.0.9-B migration: rename `.rness/skills/` → `.rness/.skills/`,
    `.rness/requests/` → `.rness/.requests/`. Idempotent: skips when the
    new path already exists. Preserves contents (symlinks survive a
    rename of their parent dir, and request markdown moves with the
    folder)."""
    rness = project_dir / ".rness"
    pairs = (
        (rness / "skills",   rness / ".skills"),
        (rness / "requests", rness / ".requests"),
    )
    for old, new in pairs:
        if not (old.exists() or old.is_symlink()):
            continue
        if new.exists() or new.is_symlink():
            # User is mid-migrated or did something custom; don't clobber.
            continue
        try:
            old.rename(new)
        except OSError:
            # Different fs / permissions / etc. Skip silently — the
            # _populate_* functions will create the new dirs as needed,
            # and the user can move legacy contents manually.
            pass


def ensure_skeleton(project_dir: Path) -> bool:
    """Create `.rness/` + `infoworld` symlink if missing, AND sync global
    skills/roles on every call (idempotent). Returns True on first-time
    `.rness/` creation, False if it already existed.

    The skill/role sync runs on every launch so newly-installed globals
    appear in existing projects too — with default-off status, per the
    policy. It's idempotent: already-symlinked entries and already-
    disabled names are left alone."""
    rness = project_dir / ".rness"
    new_project = not rness.exists()

    defaults = _install_defaults_root()
    if not defaults.is_dir():
        raise FileNotFoundError(
            f"enough defaults not found at {defaults}. "
            "The installation looks broken — re-run bootstrap.sh."
        )

    # Always ensure global infoworld exists (per user, not per project).
    infoworld_root = ensure_global_infoworld()

    if new_project:
        # First-time setup: copies, symlinks, empty dirs, infoworld link.
        _apply_missing_skeleton_items(project_dir, defaults, _SKELETON_PLAN)

        for rel, body in _PROJECT_LOCAL_FILES.items():
            target = project_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")

        for rel in _EMPTY_DIRS:
            d = project_dir / rel
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

        infoworld_link = project_dir / "infoworld"
        if not infoworld_link.exists() and not infoworld_link.is_symlink():
            infoworld_link.symlink_to(
                infoworld_root.resolve(), target_is_directory=True
            )

    # ALWAYS run (idempotent): migrate skills/, requests/ to the new
    # dotted layout BEFORE populating, so the populators target the
    # post-migration paths.
    _migrate_to_dotted(project_dir)

    # ALWAYS run (idempotent): sync global skills/roles into the project.
    # Picks up any new globals added after this project was first created.
    _populate_skill_symlinks(project_dir, defaults)
    _populate_role_symlinks(project_dir, defaults)

    # ALWAYS ensure the io/ scratch dirs exist — back-fills into projects
    # created before these were added to the skeleton.
    for rel in (".rness/io/input", ".rness/io/output"):
        d = project_dir / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

    # ALWAYS run (idempotent): clean up the legacy `.rness/routines/` dir
    # left over from pre-0.0.9 projects. Routines were a pre-built
    # abstraction with no working surface; nothing read them, no UI
    # showed them, no scheduler triggered them. We rmdir() so projects
    # that did somehow populate the dir keep their content; only the
    # empty default state goes away.
    #
    # Removable contents: symlinks (we made them via the old populator)
    # and the `.gitkeep` placeholder (we put it there ourselves). If
    # anything else is in the dir, rmdir() will fail and we leave the
    # whole thing alone.
    legacy_routines = project_dir / ".rness" / "routines"
    if legacy_routines.is_dir():
        for entry in legacy_routines.iterdir():
            if entry.is_symlink() or entry.name == ".gitkeep":
                try:
                    entry.unlink()
                except OSError:
                    pass
        try:
            legacy_routines.rmdir()
        except OSError:
            pass  # not empty — leave the user's stuff alone

    # ALWAYS run (idempotent): migrate read-allowlist.md → allowlists.md.
    # The new file has three sections (read, r/w, internet) but the tools
    # layer still parses the legacy `## allowlisted prefixes` heading, so
    # a renamed-but-otherwise-untouched project-local copy keeps working.
    _migrate_allowlist(project_dir, defaults)

    return new_project


def _migrate_allowlist(project_dir: Path, defaults: Path) -> None:
    """v0.0.9-A migration: read-allowlist.md → allowlists.md.

    Three cases:
    - Both files exist: do nothing (user has done something custom; don't
      clobber — they'll resolve manually).
    - Only new file exists: nothing to do.
    - Only old file exists, and it's a symlink to defaults/...read-allowlist.md:
      replace it with a symlink to defaults/...allowlists.md (the
      authoritative new content).
    - Only old file exists, and it's a real file (project-customized):
      rename it in place to allowlists.md so the user's customizations
      carry over."""
    pol = project_dir / ".rness" / "policies"
    old = pol / "read-allowlist.md"
    new = pol / "allowlists.md"
    if new.exists() or new.is_symlink():
        return
    if not (old.exists() or old.is_symlink()):
        return
    if old.is_symlink():
        try:
            old.unlink()
        except OSError:
            return
        new_default = (defaults / "policies" / "allowlists.md").resolve()
        if new_default.is_file():
            try:
                new.symlink_to(new_default)
            except OSError:
                pass
    else:
        try:
            old.rename(new)
        except OSError:
            pass
