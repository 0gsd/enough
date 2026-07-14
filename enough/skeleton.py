"""Generate the `rness/` skeleton for a new project.

v0.0.3+ layout:

- `~/enough/defaults/` holds the source-of-truth default files (shipped
  with the repo at `<install_root>/defaults/`).
- On first run in a project, `rness/` is populated with a mix of:
    - **symlinks** into `~/enough/defaults/...` — for files whose
      semantics are "global convention, upgradable centrally" (paradigms,
      policies, skills, roles).
    - **copies** — for files that diverge per project from the start
      (AGENT.md, MOTIVATION.md, knowledge/project-profile.md).
The old per-project `infoworld` symlink (into `~/enough/infoworld/`) is
gone: that shared library is dissolved into the global **cacheawl** store
(`~/enough/cacheawl/{personal,public,wiki}` cacheboxes). `ensure_skeleton`
prunes the dead link from existing projects; the one-time folder move runs
at server startup via `cacheawl.migrate_infoworld`.

If `~/enough/` doesn't exist (dev setup, or enough run before running
bootstrap.sh), the installer defaults directory is located relative to
this package's install path.
"""

from __future__ import annotations

import os
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


def cloud_sync_provider(path: Path) -> str | None:
    """Human label for the cloud-sync service hosting `path`, or None.

    enough's project skeleton is built from POSIX symlinks, and its
    double-click launcher relies on the Unix executable bit. Google Drive,
    Dropbox, iCloud Drive, and OneDrive preserve neither across machines —
    symlinks come back blanked or as alias files, and `.command` files lose
    `+x` on sync. A project run from inside one of these roots will see its
    skeleton links (and launcher) break when shared between Macs. The UI
    calls this to surface a launch-time warning."""
    s = str(path).lower()
    # macOS File-Provider mounts (Drive for Desktop, Dropbox, OneDrive, etc.).
    if "/library/cloudstorage/googledrive" in s:
        return "Google Drive"
    if "/library/cloudstorage/dropbox" in s:
        return "Dropbox"
    if "/library/cloudstorage/onedrive" in s:
        return "OneDrive"
    if "/library/cloudstorage/icloud" in s:
        return "iCloud Drive"
    if "/library/cloudstorage/" in s:
        return "a cloud-synced folder"
    # iCloud Drive's on-disk location, plus legacy non-File-Provider roots.
    if "/library/mobile documents/com~apple~clouddocs" in s:
        return "iCloud Drive"
    if "/google drive/" in s or "/googledrive-" in s:
        return "Google Drive"
    if "/dropbox/" in s:
        return "Dropbox"
    return None


# ---------------------------------------------------------------------------
# Per-file policy: how each default file should appear in a new rness/.
# ---------------------------------------------------------------------------

# (src_rel_to_defaults, dst_rel_to_project, mode)
# mode: "symlink" | "copy"
_SKELETON_PLAN: tuple[tuple[str, str, str], ...] = (
    ("AGENT.md",                       "rness/AGENT.md",                        "copy"),
    ("MOTIVATION.md",                  "rness/MOTIVATION.md",                   "copy"),
    # NOTE: paradigms are no longer in this plan. They're synced dynamically
    # on every launch by `_populate_paradigm_symlinks` so newly-shipped
    # paradigm files appear in existing projects automatically — same
    # lifecycle as skills and roles. See ensure_skeleton() below.
    ("policies/requests.md",            "rness/policies/requests.md",            "symlink"),
    ("policies/context-management.md",  "rness/policies/context-management.md",  "symlink"),
    ("policies/allowlists.md",          "rness/policies/allowlists.md",          "symlink"),
    ("policies/profile-maintenance.md", "rness/policies/profile-maintenance.md", "symlink"),
    ("knowledge/rosetta-primers",      "rness/knowledge/rosetta-primers",       "symlink"),
)

# Project-local files not sourced from defaults/ (generated inline).
_PROJECT_LOCAL_FILES: dict[str, str] = {
    "rness/knowledge/project-profile.md": (
        "# Project Profile\n"
        "\n"
        "Living notes about *this specific project* — the user's preferences\n"
        "and working style as observed in this folder, the kind of work that\n"
        "happens here, the conventions you've adopted, the recurring people /\n"
        "places / files that matter. Project-local memory, not a user dossier;\n"
        "different projects get different profiles.\n"
        "\n"
        "Starts empty. The harness pipes this file into your system prompt\n"
        "on every turn, so anything written here is in your working memory.\n"
        "Update it via `write_file` per the `profile-maintenance` policy:\n"
        "concrete observations, not labels; pruned when stale; never bloated.\n"
    ),
    "rness/active-paradigm": "default\n",
}

# Empty dirs to create in every project.
# `skills/`, `requests/`, and `roles/` are surfaced through dedicated
# sidebar sections (since they're configuration rather than artifacts) but
# still live in the file tree so they're easy to discover.
_EMPTY_DIRS: tuple[str, ...] = (
    "rness/skills",
    "rness/knowledge/session-logs",
    "rness/requests",
    "rness/requests/done",
    "rness/roles",
    "rness/io/input",
    "rness/io/output",
)


# ---------------------------------------------------------------------------
# Drift detection / opt-in update
# ---------------------------------------------------------------------------
#
# `_SKELETON_PLAN` runs only on first-time `rness/` creation. That keeps
# us from clobbering project-local edits — but it also means a new shared
# default added to ~/enough/defaults/ (e.g. a new paradigm, a new
# knowledge dir) won't appear in projects whose `rness/` predates it.
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
    `project_dir/rness/`. Empty list = the project is up to date with
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
PROJECT_PROFILE_MD = _PROJECT_LOCAL_FILES["rness/knowledge/project-profile.md"]
# Back-compat alias for tooling that imported the old name.
USER_PROFILE_MD = PROJECT_PROFILE_MD


# ---------------------------------------------------------------------------
# Skeleton creation
# ---------------------------------------------------------------------------

def _populate_skill_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """Sync global skills into `rness/skills/` and prune dangling symlinks.

    - For each skill in `<defaults>/skills/`: if the project doesn't
      already have an entry with that name, symlink it in and add to
      `.disabled` (new globals default off).
    - For each existing entry in `rness/skills/`: if it's a symlink whose
      target no longer exists (dangling — usually because the skill was
      removed globally), unlink it. Project-local entries (real dirs or
      files, not symlinks) are never touched.

    The latter makes removal propagate automatically: `rm -rf
    ~/enough/defaults/skills/foo` on the next `enough` launch cleans `foo`
    out of every project using the (now-dangling) symlink."""
    src_skills = defaults_root / "skills"
    dst_skills = project_dir / "rness" / "skills"
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
    """Sync global Role agents into `rness/roles/` and prune dangling
    symlinks. Same shape and lifecycle as skills: each role is a folder
    containing AGENT.md + MOTIVATION.md, default-off (added to .disabled
    on first sync), togglable per-project via the sidebar."""
    src_roles = defaults_root / "roles"
    dst_roles = project_dir / "rness" / "roles"
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


def _populate_paradigm_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """Sync global paradigms into `rness/paradigms/` and prune dangling
    symlinks.

    Paradigms differ from skills/roles in two ways:
      - they're single files (`paradigms/*.md`), not folders.
      - they're always selectable — there is no `.disabled` notion.
        Exactly one is active at a time, named in `rness/active-paradigm`.

    If the currently-active paradigm gets removed from
    `defaults/paradigms/`, the dangling symlink is pruned here and
    `get_active_paradigm()` falls back to 'default' on the next read.
    Project-local paradigm files (real files, not symlinks) are never
    touched."""
    src_paradigms = defaults_root / "paradigms"
    dst_paradigms = project_dir / "rness" / "paradigms"
    dst_paradigms.mkdir(parents=True, exist_ok=True)

    # 1. Prune dangling symlinks (target removed globally).
    for entry in sorted(dst_paradigms.iterdir()):
        if entry.is_symlink() and not entry.exists():
            try:
                entry.unlink()
            except OSError:
                pass

    # 2. Sync in any new globals.
    if not src_paradigms.is_dir():
        return
    for entry in sorted(src_paradigms.glob("*.md")):
        if entry.name.startswith("."):
            continue
        dst = dst_paradigms / entry.name
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(entry.resolve())


def _migrate_undot(project_dir: Path) -> None:
    """Migration: drop the dots from project skeleton paths.

    Renames (each idempotent, skipping when the new path already exists):
      - `.rness/`          → `rness/`
      - `rness/.skills/`   → `rness/skills/`
      - `rness/.requests/` → `rness/requests/`
      - `rness/.roles/`    → `rness/roles/`

    Symlinks survive a rename of their parent dir, so global skill/role
    targets stay valid. Run BEFORE any populator/skeleton step so the
    rest of the launch sees the new paths."""
    pairs = (
        (project_dir / ".rness",            project_dir / "rness"),
        (project_dir / "rness" / ".skills",   project_dir / "rness" / "skills"),
        (project_dir / "rness" / ".requests", project_dir / "rness" / "requests"),
        (project_dir / "rness" / ".roles",    project_dir / "rness" / "roles"),
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


def _migrate_user_profile_to_project_profile(project_dir: Path) -> None:
    """v0.0.9-B migration: rness/knowledge/user-profile.md → project-profile.md.

    The file was renamed to reflect what it actually is: per-project working
    memory, not a per-user dossier (a user with five enough projects has
    five different profiles — they're profiles of how this project gets
    worked on, not of the user themselves).

    Idempotent and conservative:
    - If only the old file exists, rename in place (preserves any content
      the agent or user wrote into it).
    - If the new file already exists, do nothing (assume the user / agent
      has resolved it manually).
    - If neither exists, do nothing (skeleton-creation handles the new
      project case).
    """
    k = project_dir / "rness" / "knowledge"
    old = k / "user-profile.md"
    new = k / "project-profile.md"
    if new.exists() or new.is_symlink():
        return
    if not (old.exists() or old.is_symlink()):
        return
    try:
        old.rename(new)
    except OSError:
        pass  # different fs / permissions / etc. — leave manual cleanup to user


def _symlink_is_broken(link: Path) -> bool:
    """True iff `link` is a symlink that doesn't usefully resolve — i.e.
    dangling (target missing, e.g. an absolute path into another machine's
    home dir) or blanked (empty target, which cloud-sync filesystems sometimes
    leave behind). A symlink that resolves to a real file/dir is NOT broken,
    even if it points somewhere unexpected — we don't second-guess a working
    link. Non-symlinks always return False: a real file/dir (or a Finder
    alias the user might be relying on) is theirs, not ours to repair."""
    if not link.is_symlink():
        return False
    try:
        target = os.readlink(link)
    except OSError:
        return True
    if not target.strip():
        return True  # blanked target — classic cloud-sync corruption
    return not link.exists()  # follows the link; True == dangling


def _heal_skeleton_symlinks(project_dir: Path, defaults: Path) -> list[str]:
    """Repair skeleton symlinks broken by a cloud-sync filesystem (Google
    Drive, Dropbox, iCloud) syncing them between machines.

    The per-launch `_populate_*` pass already self-heals skills/roles/
    paradigms (it prunes dangling links and resyncs). The surface it does
    NOT cover is `_SKELETON_PLAN` symlink entries (policies/*, knowledge
    primers): `_is_skeleton_item_present()` counts a *broken* symlink as
    'present', so drift-detection never repairs it. We re-point broken ones
    here.

    (The old top-level `infoworld` link is no longer created or healed —
    infoworld is dissolved into cacheawl. `_prune_infoworld_link` removes
    the dead link from existing projects.)

    Only *broken* symlinks (dangling or blanked) are touched; working links
    and real files (e.g. a 'customize for this project' copy) are left alone.
    A cloud filesystem that turned the link into an alias *file* is also left
    alone — we won't delete a real file we can't positively identify as junk.
    Returns the destinations repaired (for logging / tests)."""
    repaired: list[str] = []

    for src_rel, dst_rel, mode in _SKELETON_PLAN:
        if mode != "symlink":
            continue
        src = defaults / src_rel
        if not src.exists():
            continue
        dst = project_dir / dst_rel
        if _symlink_is_broken(dst):
            try:
                dst.unlink()
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src.resolve())
                repaired.append(dst_rel)
            except OSError:
                pass

    return repaired


def _prune_infoworld_link(project_dir: Path) -> bool:
    """Remove the per-project `infoworld` symlink left over from before the
    dissolve. infoworld is now the cacheawl `personal`/`public`/`wiki`
    cacheboxes — a global store with no per-project symlink. Only a symlink
    is removed (that's the artifact this package created); a real
    `infoworld/` directory the user made themselves is left untouched.
    Returns True iff a link was pruned."""
    link = project_dir / "infoworld"
    if link.is_symlink():
        try:
            link.unlink()
            return True
        except OSError:
            pass
    return False


def ensure_skeleton(project_dir: Path) -> bool:
    """Create `rness/` if missing, prune the dead `infoworld` link, AND
    sync global skills/roles on every call (idempotent). Returns True on
    first-time `rness/` creation, False if it already existed.

    The skill/role sync runs on every launch so newly-installed globals
    appear in existing projects too — with default-off status, per the
    policy. It's idempotent: already-symlinked entries and already-
    disabled names are left alone."""
    # Run the un-dot migration FIRST so an existing project still on the
    # legacy `.rness/` layout gets renamed to `rness/` before we decide
    # whether this is a new project. Without this, an existing `.rness/`
    # would be invisible to the `rness.exists()` check below and we'd
    # spuriously re-run first-time setup.
    _migrate_undot(project_dir)

    rness = project_dir / "rness"
    new_project = not rness.exists()

    defaults = _install_defaults_root()
    if not defaults.is_dir():
        raise FileNotFoundError(
            f"enough defaults not found at {defaults}. "
            "The installation looks broken — re-run bootstrap.sh."
        )

    if new_project:
        # First-time setup: copies, symlinks, empty dirs.
        _apply_missing_skeleton_items(project_dir, defaults, _SKELETON_PLAN)

        for rel, body in _PROJECT_LOCAL_FILES.items():
            target = project_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")

        for rel in _EMPTY_DIRS:
            d = project_dir / rel
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

    # ALWAYS run (idempotent): remove the dead per-project `infoworld`
    # symlink. infoworld is dissolved into the global cacheawl store
    # (personal/public/wiki cacheboxes); the actual folder move happens
    # once at server startup (cacheawl.migrate_infoworld).
    _prune_infoworld_link(project_dir)

    # ALWAYS run (idempotent): sync global skills/roles/paradigms into the
    # project. Picks up any new globals added after this project was first
    # created.
    _populate_skill_symlinks(project_dir, defaults)
    _populate_role_symlinks(project_dir, defaults)
    _populate_paradigm_symlinks(project_dir, defaults)

    # ALWAYS run (idempotent): re-point any skeleton symlinks a cloud-sync
    # filesystem broke between machines (the static plan links).
    # No-op on healthy projects.
    _heal_skeleton_symlinks(project_dir, defaults)

    # ALWAYS ensure the io/ scratch dirs exist — back-fills into projects
    # created before these were added to the skeleton.
    for rel in ("rness/io/input", "rness/io/output"):
        d = project_dir / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

    # ALWAYS ensure rness/active-paradigm exists. New projects get this via
    # _PROJECT_LOCAL_FILES; existing projects need the back-fill so the UI
    # paradigm selector renders a definite choice instead of relying on the
    # missing-file fallback.
    active_paradigm = project_dir / "rness" / "active-paradigm"
    if not active_paradigm.exists():
        active_paradigm.parent.mkdir(parents=True, exist_ok=True)
        active_paradigm.write_text("default\n", encoding="utf-8")

    # ALWAYS run (idempotent): clean up the legacy `rness/routines/` dir
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
    legacy_routines = project_dir / "rness" / "routines"
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

    # ALWAYS run (idempotent): migrate knowledge/user-profile.md →
    # project-profile.md. Existing projects predating the rename get
    # their file renamed in place so anything the agent wrote into it
    # carries over.
    _migrate_user_profile_to_project_profile(project_dir)

    # ALWAYS run (idempotent): migrate read-allowlist.md → allowlists.md.
    # The new file has three sections (read, r/w, internet) but the tools
    # layer still parses the legacy `## allowlisted prefixes` heading, so
    # a renamed-but-otherwise-untouched project-local copy keeps working.
    _migrate_allowlist(project_dir, defaults)

    return new_project


def resync_globals(project_dir: Path) -> None:
    """Re-run the global skill/role/paradigm sync for an existing project,
    without the rest of the first-launch skeleton pass.

    `ensure_skeleton()` only runs at launch, so a global dropped into
    `~/enough/defaults/{skills,roles,paradigms}/` while a project is already
    open wouldn't appear until the next restart. The sidebar list endpoints
    call this first so a plain refresh picks up newly-added globals live.

    Identical semantics to the launch-time sync: idempotent, cheap (symlink
    existence checks only), and new skills/roles still arrive default-off
    (added to `.disabled`). No-op if `rness/` doesn't exist yet (nothing to
    sync into) or the install defaults are missing."""
    rness = project_dir / "rness"
    if not rness.is_dir():
        return
    defaults = _install_defaults_root()
    if not defaults.is_dir():
        return
    _populate_skill_symlinks(project_dir, defaults)
    _populate_role_symlinks(project_dir, defaults)
    _populate_paradigm_symlinks(project_dir, defaults)


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
    pol = project_dir / "rness" / "policies"
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
