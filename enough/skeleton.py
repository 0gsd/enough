"""Generate the `rness/` skeleton for a new project.

v0.0.3+ layout:

- `~/enough/defaults/` holds the source-of-truth default files (shipped
  with the repo at `<install_root>/defaults/`).
- On first run in a project, `rness/` is populated with a mix of:
    - **symlinks** into `~/enough/defaults/...` — for files whose
      semantics are "global convention, upgradable centrally" (paradigms,
      policies, skills, readvisors).
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

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("enough.skeleton")

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
    # lifecycle as skills and readvisors. See ensure_skeleton() below.
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
    "rness/active-paradigm": "text-planning\n",
}

# Empty dirs to create in every project.
# `skills/`, `requests/`, and `readvisors/` are surfaced through dedicated
# sidebar sections (since they're configuration rather than artifacts) but
# still live in the file tree so they're easy to discover.
_EMPTY_DIRS: tuple[str, ...] = (
    "rness/skills",
    "rness/knowledge/session-logs",
    "rness/requests",
    "rness/requests/done",
    "rness/readvisors",
    "rness/io/input",
    "rness/io/output",
    # Where new composures land (composure round, P4b). `rness/composure-forms`
    # is NOT here — it is created on the first save-as-form, so a project that
    # never made a form has no empty folder to explain.
    "rness/io/composure",
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
# `default` was folded into `text-planning` in 0.4.1; the name stays for
# importers, the content is the home paradigm's.
PARADIGM_DEFAULT_MD = _read_default("paradigms/text-planning.md")
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

    # 1.5 Heal materialized copies of shipped skills. Cloud-sync filesystems
    #     and link-dereferencing copies (zip, cp -RL) turn the skill symlinks
    #     into real directories when a project travels between machines — and
    #     a real dir is untrusted by design, so the other Mac's install then
    #     audits (and quarantines) skills enough itself shipped. When the
    #     copy's bytes are IDENTICAL to this install's global of the same
    #     name it provably is the shipped skill, so swap it back to a
    #     symlink. One byte of difference and it's left alone: a fork or a
    #     3P import is the user's, not ours to repair (0.2.8; the fingerprint
    #     ignores mtimes/permissions precisely so a faithful copy matches).
    if src_skills.is_dir():
        try:
            from . import skillaudit
            for entry in sorted(dst_skills.iterdir()):
                if entry.is_symlink() or entry.name.startswith("."):
                    continue
                src = src_skills / entry.name
                if entry.is_dir() != src.is_dir() or not (src.is_dir() or src.is_file()):
                    continue
                if skillaudit.fingerprint(entry) != skillaudit.fingerprint(src):
                    continue
                # Swap via a rename so a crash can't lose the skill: the
                # worst interruption leaves `<name>.healing` beside a
                # missing entry, and the next launch's step 2 resyncs.
                stash = entry.with_name(entry.name + ".healing")
                try:
                    entry.rename(stash)
                    entry.symlink_to(src.resolve())
                    if stash.is_dir() and not stash.is_symlink():
                        shutil.rmtree(stash)
                    else:
                        stash.unlink()
                    log.info("healed materialized skill %s -> symlink", entry.name)
                except OSError:
                    try:  # roll back so the project keeps a working copy
                        if not entry.exists() and stash.exists():
                            stash.rename(entry)
                    except OSError:
                        pass
        except Exception:  # noqa: BLE001 — healing must never break a launch
            log.exception("skill heal pass failed")

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

    # 3. Untrusted skills (real dirs, or symlinks pointing outside defaults —
    #    a 3P import, or one the agent wrote itself) also default OFF. Skills
    #    are "enabled unless named in .disabled", so without this an
    #    unaudited stranger would be live in the system prompt without ever
    #    passing through the toggle. See skillaudit.quarantine_untrusted.
    try:
        from . import skillaudit
        skillaudit.quarantine_untrusted(project_dir)
    except Exception:  # noqa: BLE001 — never let this break a launch
        log.exception("untrusted-skill quarantine failed")


# ---------------------------------------------------------------------------
# Readvisors — two global sources, one project folder
# ---------------------------------------------------------------------------
#
# Shipped readvisors live in the install's `defaults/readvisors/`. On a
# desktop build that folder is inside the sealed .app bundle and is NOT
# writable, so the `readvisory` skill (P7) cannot install anything there.
# Hence a second, user-owned global source: `~/enough/readvisors/`. Both are
# symlinked into every project exactly the same way; the only difference is
# who may write to them.

#: Test/dev hook, mirroring ENOUGH_CACHEAWL_ROOT / ENOUGH_UI_CONFIG, so a
#: suite (or a scratch server) never installs into the developer's real
#: `~/enough/readvisors/`.
_READVISORS_ROOT_ENV = "ENOUGH_READVISORS_ROOT"


def user_readvisors_root() -> Path:
    """The user-global readvisors dir, honoring `ENOUGH_READVISORS_ROOT`.

    NOT created here — a machine that has never installed a readvisor has
    no reason to carry an empty folder, and every writer (the install tool)
    builds its own parents."""
    raw = os.environ.get(_READVISORS_ROOT_ENV)
    if raw and raw.strip():
        return Path(raw).expanduser()
    return Path.home() / "enough" / "readvisors"


def shipped_readvisors_root(defaults_root: Path) -> Path:
    """The install's shipped readvisors dir.

    Falls back to the pre-0.3.5 `defaults/roles/` when the new name is
    absent, which is what a *sibling* older install looks like from here —
    the same "an install, not this install" reasoning skillaudit uses for
    trust. Returns the new path when neither exists, so callers can use it
    as a plain `is_dir()` probe."""
    new = defaults_root / "readvisors"
    if new.is_dir():
        return new
    old = defaults_root / "roles"
    if old.is_dir():
        return old
    return new


def _readvisor_sources(defaults_root: Path) -> list[tuple[str, Path, str]]:
    """Every global readvisor available to a project, as
    `[(name, source_dir, origin), ...]` in **precedence order**.

    Precedence is user-global before shipped, so a readvisor the user forged
    with the `readvisory` skill shadows a shipped one of the same name
    rather than the other way round — they asked for theirs by name. The
    third rank, a project-local real directory, is not listed here at all:
    it wins by simply existing, because the populator never overwrites a
    real dir with a symlink."""
    out: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for root, origin in ((user_readvisors_root(), "global"),
                         (shipped_readvisors_root(defaults_root), "shipped")):
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            if entry.name in seen:
                continue
            seen.add(entry.name)
            out.append((entry.name, entry, origin))
    return out


def _is_managed_readvisor_link(link: Path) -> bool:
    """True when `link` is a symlink this populator is entitled to re-point.

    "Managed" means it resolves into *some* install's readvisors folder (or
    the pre-rename `roles/` one, or a user-global root): the parent
    directory is named `roles` or `readvisors`. A link the user aimed
    somewhere else entirely is theirs, and we leave it exactly where it
    points — the same posture `_symlink_is_broken` takes."""
    if not link.is_symlink():
        return False
    try:
        target = link.resolve(strict=False)
    except OSError:
        return False
    return target.parent.name in ("roles", "readvisors")


def _populate_role_symlinks(project_dir: Path, defaults_root: Path) -> None:
    """Sync global readvisors into `rness/readvisors/` and prune dangling
    symlinks. Same shape and lifecycle as skills: each readvisor is a folder
    containing AGENT.md + MOTIVATION.md, default-off (added to .disabled
    on first sync), togglable per-project via the sidebar.

    Two global sources feed it (see `_readvisor_sources`), and three ranks
    resolve a name clash: a project-local **real** directory beats the
    user-global `~/enough/readvisors/`, which beats the shipped defaults.

    Re-pointing, not just creating, is what heals a project carried between
    machines or installs: a link into a sibling install's `defaults/roles/`
    still names the right readvisor, so it is aimed at this install's copy
    instead of being left dangling."""
    dst_roles = project_dir / "rness" / "readvisors"
    try:
        dst_roles.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only parent (a locked project, a permissions accident). The
        # migration below fails soft in the same situation and the project
        # keeps reading its old `roles/` folder; refusing to launch over it
        # would be worse than launching without the sync.
        return

    # 1. Prune dangling symlinks (target removed globally).
    #
    # Remember their names. A name pruned here and re-created below is the
    # SAME readvisor arriving through a new path — the 0.3.5 rename, or a
    # project carried from another install — and re-creating it must not
    # reset the user's toggle. Without this, every shipped readvisor a user
    # had switched ON came back switched OFF the first time they launched
    # after the rename, which is the one thing a migration must not do.
    pruned: set[str] = set()
    for entry in sorted(dst_roles.iterdir()):
        if entry.is_symlink() and not entry.exists():
            try:
                entry.unlink()
                pruned.add(entry.name)
            except OSError:
                pass

    # 2. Sync in any new globals (default-off), and re-aim managed links
    #    that point at the wrong source.
    disabled_names: list[str] = []
    for name, src, _origin in _readvisor_sources(defaults_root):
        dst = dst_roles / name
        target = src.resolve()
        if dst.is_symlink():
            try:
                if dst.resolve(strict=False) == target:
                    continue
            except OSError:
                pass
            if not _is_managed_readvisor_link(dst):
                continue  # the user aimed this one somewhere on purpose
            try:
                dst.unlink()
            except OSError:
                continue
            # A heal, not an arrival: the project already had an opinion
            # about this name, so its .disabled entry is left alone.
            try:
                dst.symlink_to(target)
            except OSError:
                pass
            continue
        if dst.exists():
            continue  # project-local real dir — rank 1, never touched
        try:
            dst.symlink_to(target)
        except OSError:
            continue
        if name not in pruned:
            # Genuinely new here, so it arrives switched off, per the
            # standing rule for new globals. A name we pruned a moment ago
            # is a re-aim, and keeps whatever the user already decided.
            disabled_names.append(name)

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

    Paradigms differ from skills/readvisors in two ways:
      - they're single files (`paradigms/*.md`), not folders.
      - they're always selectable — there is no `.disabled` notion.
        Exactly one is active at a time, named in `rness/active-paradigm`.

    If the currently-active paradigm gets removed from
    `defaults/paradigms/`, the dangling symlink is pruned here and
    `get_active_paradigm()` falls back to the home paradigm
    (`text-planning`) on the next read.
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

    Symlinks survive a rename of their parent dir, so global skill/readvisor
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


def _read_disabled_file(f: Path) -> set[str]:
    """The names in a `.disabled` file, comments and blanks dropped."""
    if not f.is_file():
        return set()
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.startswith("#")}


def _migrate_roles_to_readvisors(project_dir: Path) -> None:
    """0.3.5 migration: `rness/roles/` → `rness/readvisors/`.

    The rename is the visible half of the readvisor vocabulary change: the
    folder a user opens in Finder should say what the thing is called. Run
    from `ensure_skeleton` BEFORE the populators, so the rest of the launch
    only ever sees the new path.

    Three shapes, in order of how common they are:

    - **Only `roles/`** — the ordinary upgrade. One atomic `rename()`, which
      carries `.disabled`, `.gitkeep`, project-local real readvisor dirs and
      the symlinks alike. The symlinks now point into the old
      `defaults/roles/` and are dangling; `_populate_role_symlinks` prunes
      and re-creates them a moment later, which is exactly the path a
      sibling-install link takes too.
    - **Both** — an older install re-created `roles/` after a first
      migration (they share a project folder; this really happens). Merge
      *into* `readvisors/`, which is authoritative: project-local real dirs
      that the new folder lacks are moved over, the two `.disabled` files
      are unioned (a readvisor switched off under either name stays off —
      the safe direction), leftover symlinks and `.gitkeep` are dropped
      because the populator re-creates them, and `roles/` is then removed
      with `rmdir`, which **refuses** if anything unexpected is still in
      there. Nothing non-empty is ever deleted.
    - **Neither, or only `readvisors/`** — nothing to do.

    Idempotent and fail-soft throughout: a read-only parent leaves `roles/`
    in place and every reader falls back to it (see
    `prompt._readvisors_dir`), so the worst case is a project that keeps
    working under the old name until the permissions are fixed."""
    rness = project_dir / "rness"
    old = rness / "roles"
    new = rness / "readvisors"

    old_is_dir = old.is_dir() and not old.is_symlink()
    if not old_is_dir:
        return

    if not (new.exists() or new.is_symlink()):
        try:
            old.rename(new)
        except OSError:
            log.warning("could not rename %s to %s — the project keeps using "
                        "the old folder", old, new, exc_info=True)
        return

    if not (new.is_dir() and not new.is_symlink()):
        # `readvisors` exists but is a file or a symlink — someone did
        # something deliberate. Don't guess; leave both alone.
        return

    # Both are real directories: merge old into new.
    try:
        entries = sorted(old.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.name == ".disabled":
            continue
        if entry.is_symlink():
            # Never moved: the populator re-creates global links against
            # the current defaults path a few lines later.
            try:
                entry.unlink()
            except OSError:
                pass
            continue
        if entry.name == ".gitkeep":
            try:
                entry.unlink()
            except OSError:
                pass
            continue
        if not entry.is_dir():
            # A readvisor is a directory. Anything else in here is something
            # the user put there, and moving a stray file into a folder they
            # did not choose is worse than leaving it — `rmdir` will then
            # decline, which is the honest outcome.
            continue
        dest = new / entry.name
        if dest.exists() or dest.is_symlink():
            continue  # the new folder already has this one — it wins
        try:
            entry.rename(dest)
        except OSError:
            pass  # leave it behind; rmdir below will decline, which is right

    union = _read_disabled_file(old / ".disabled") | _read_disabled_file(new / ".disabled")
    if union:
        try:
            (new / ".disabled").write_text("\n".join(sorted(union)) + "\n",
                                           encoding="utf-8")
        except OSError:
            pass
    try:
        (old / ".disabled").unlink()
    except OSError:
        pass
    try:
        old.rmdir()  # refuses when anything survived the loop above
    except OSError:
        pass


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

    The per-launch `_populate_*` pass already self-heals skills/readvisors/
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
    sync global skills/readvisors on every call (idempotent). Returns True on
    first-time `rness/` creation, False if it already existed.

    The skill/readvisor sync runs on every launch so newly-installed globals
    appear in existing projects too — with default-off status, per the
    policy. It's idempotent: already-symlinked entries and already-
    disabled names are left alone."""
    # Run the un-dot migration FIRST so an existing project still on the
    # legacy `.rness/` layout gets renamed to `rness/` before we decide
    # whether this is a new project. Without this, an existing `.rness/`
    # would be invisible to the `rness.exists()` check below and we'd
    # spuriously re-run first-time setup.
    _migrate_undot(project_dir)
    # Then the readvisor rename, still BEFORE the populators: everything
    # downstream (the populators, the prompt loader, the tree filter) is
    # written against `rness/readvisors/` and only falls back to the old
    # name when this could not run.
    _migrate_roles_to_readvisors(project_dir)

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

        # Seed the multipurpose active-paradigm file: the home paradigm,
        # help bubbles on (the sticky per-folder default for a first launch).
        from .prompt import seed_multipurpose_file
        seed_multipurpose_file(project_dir / "rness")

    # ALWAYS run (idempotent): remove the dead per-project `infoworld`
    # symlink. infoworld is dissolved into the global cacheawl store
    # (personal/public/wiki cacheboxes); the actual folder move happens
    # once at server startup (cacheawl.migrate_infoworld).
    _prune_infoworld_link(project_dir)

    # ALWAYS run (idempotent): sync global skills/readvisors/paradigms into the
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
    for rel in ("rness/io/input", "rness/io/output", "rness/io/composure"):
        d = project_dir / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()

    # ALWAYS ensure rness/active-paradigm exists AND is in the multipurpose
    # markdown form. New projects were seeded just above (with highlights when
    # enabled); existing projects get a one-time upgrade from the legacy bare
    # form — WITHOUT seeding highlights, since they aren't new folders.
    from .prompt import ensure_multipurpose_file
    ensure_multipurpose_file(project_dir / "rness")

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

    # ALWAYS run (idempotent): put this project on the home screen. This is
    # one of the registry's exactly two write points (home-plan §1.3) and it
    # covers every way a folder becomes a project — the home screen's add
    # button, `enough --dir` on a fresh folder, and the desktop picker alike.
    # Never fatal: a project must still open when the registry can't be
    # written (a read-only ~/enough, a full disk).
    try:
        from .home import register
        register(project_dir)
    except Exception:  # noqa: BLE001
        log.warning("could not add %s to the project registry", project_dir,
                    exc_info=True)

    return new_project


def resync_globals(project_dir: Path) -> None:
    """Re-run the global skill/readvisor/paradigm sync for an existing project,
    without the rest of the first-launch skeleton pass.

    `ensure_skeleton()` only runs at launch, so a global dropped into
    `~/enough/defaults/{skills,readvisors,paradigms}/` while a project is already
    open wouldn't appear until the next restart. The sidebar list endpoints
    call this first so a plain refresh picks up newly-added globals live.

    Identical semantics to the launch-time sync: idempotent, cheap (symlink
    existence checks only), and new skills/readvisors still arrive default-off
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
