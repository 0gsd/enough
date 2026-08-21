"""enough home: the project registry, its cached stats, and the launch screen.

**home** is the no-project launch screen — a *mode* of this same server and
this same index.html, not a separate app (docs/home-plan.md §1.1). A server
started with `enough --home` has no project, no Session, no llama
supervision and no broker; it serves `/` in home mode plus `/api/home/*`,
and every project-scoped route 404s.

What lives here
---------------
- **The registry** (`~/enough/config/projects.json`, seam
  `ENOUGH_PROJECTS_STATE`): every folder enough has ever put an `rness/`
  into, plus cached metadata. Backend-owned, one writer, tmp+rename. The
  desktop's `desktop.json` `known_projects` stays the *shell's* MRU — we
  seed from it once and never write it.
- **The counters**: paragraphs / words / characters over the project's
  visible markdown, using the top bar's exact rules (§1.4), cached behind a
  cheap fingerprint so a list render never re-reads a whole project.
- **The project mirror**: the same `modality: mirror` merirmaid contract the
  cachebox mirrors use, built by the shared flowchart helper in
  `cacheawl.py`.
- **The open/close handshake**: a `.home-open` handoff file plus exit code
  42 for the desktop shell, or an `os.execv` re-exec for the CLI (§1.7).

Registration happens in exactly two places — `skeleton.ensure_skeleton()`
(any enough-ification, however it was triggered) and project-server boot
(which also stamps `last_opened`, so projects that predate the registry
appear in home after their first open).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("enough.home")

REGISTRY_SCHEMA = 1

# The handoff file the desktop shell reads after an exit-42 (§1.7). It lives
# beside the registry — so a scratch QA run that seams ENOUGH_PROJECTS_STATE
# into a scratch config dir gets a scratch handoff file for free.
HANDOFF_NAME = ".home-open"

# The shell's own MRU, read exactly once to seed the registry. Same dir
# derivation as the handoff file, and never written by us.
DESKTOP_CONFIG_NAME = "desktop.json"

_DEFAULT_PROJECTS_STATE = "config/projects.json"

# Markdown, as the counters and the tree understand it.
MARKDOWN_SUFFIXES = (".md", ".markdown")

# How long the native folder chooser may stay up before we give up on it and
# tell the UI to show its typed-path fallback. Long enough for someone to
# actually browse, short enough that a wedged osascript doesn't pin a thread.
DIALOG_TIMEOUT_S = 180.0


class HomeError(ValueError):
    """A refusal with a reason the user should read verbatim — the add
    guards (§1.8), a path that isn't a project, an unregistered open."""


class DialogUnavailable(RuntimeError):
    """No native folder chooser here (not macOS, no osascript, or it
    failed). The UI falls back to a typed-path field."""


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def projects_state_path() -> Path:
    """`~/enough/config/projects.json`, or `ENOUGH_PROJECTS_STATE` when set —
    the same test/dev seam shape as `ENOUGH_UI_CONFIG` / `ENOUGH_EXTRAS_STATE`,
    so a QA server can never register a scratch folder in the real install."""
    env = os.environ.get("ENOUGH_PROJECTS_STATE")
    if env:
        return Path(env).expanduser()
    return Path.home() / "enough" / _DEFAULT_PROJECTS_STATE


def config_dir() -> Path:
    """The dir the registry lives in — everything else home writes (the
    handoff file) or reads (desktop.json) is derived from it, so one seam
    moves the whole set."""
    return projects_state_path().parent


def handoff_path() -> Path:
    return config_dir() / HANDOFF_NAME


def desktop_config_path() -> Path:
    return config_dir() / DESKTOP_CONFIG_NAME


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_from_ns(mtime_ns: int) -> str:
    return dt.datetime.fromtimestamp(
        mtime_ns / 1_000_000_000, dt.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(path: Path | str) -> Path:
    """The registry's key: an absolute, symlink-resolved path. Resolution is
    non-strict so an entry on an unmounted drive still normalizes."""
    return Path(path).expanduser().resolve(strict=False)


def is_project(path: Path) -> bool:
    """A folder is an enough project iff it holds an `rness/` — the same test
    the desktop shell's `is_enough_project` makes."""
    try:
        return (path / "rness").is_dir()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# The registry file
# ---------------------------------------------------------------------------

def _empty_registry() -> dict[str, Any]:
    return {"schema": REGISTRY_SCHEMA, "projects": []}


def read_registry() -> dict[str, Any]:
    """The registry, always a usable dict.

    A missing, unreadable, corrupt or foreign-schema file reads as *empty*
    and is **not** rewritten — that only happens on a real save. Losing a
    user's project list to a stray parse error would be worse than running
    one session on defaults; it is the same rule the desktop shell applies to
    desktop.json.
    """
    try:
        data = json.loads(projects_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty_registry()
    if not isinstance(data, dict) or data.get("schema") != REGISTRY_SCHEMA:
        return _empty_registry()
    projects = data.get("projects")
    if not isinstance(projects, list):
        data["projects"] = []
    else:
        data["projects"] = [p for p in projects
                            if isinstance(p, dict) and p.get("path")]
    return data


def save_registry(reg: dict[str, Any]) -> None:
    """Write the registry tmp+rename. Unknown top-level keys survive, so a
    newer enough's additions aren't dropped by an older one."""
    reg["schema"] = REGISTRY_SCHEMA
    path = projects_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f"{path.name}.tmp"
    tmp.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _find(reg: dict[str, Any], key: str) -> dict[str, Any] | None:
    for entry in reg["projects"]:
        if entry.get("path") == key:
            return entry
    return None


def entry_for(project_dir: Path | str) -> dict[str, Any] | None:
    """The registry entry for a path, or None. Read-only."""
    return _find(read_registry(), str(canonical(project_dir)))


def _new_entry(key: str, created_at: str) -> dict[str, Any]:
    return {
        "path": key,
        "created_at": created_at,
        "last_opened": None,
        "last_edited": None,
        "counts": None,
        "fingerprint": None,
    }


def register(project_dir: Path | str, *, created_at: str | None = None) -> dict[str, Any]:
    """Create-or-touch the entry for `project_dir`. Returns it.

    Idempotent and cheap: no walk, no counting. The first
    `GET /api/home/projects` fills the stats in (a missing fingerprint can
    never match, so the refresh picks it up on its own).
    """
    key = str(canonical(project_dir))
    reg = read_registry()
    existing = _find(reg, key)
    if existing is not None:
        return existing
    entry = _new_entry(key, created_at or _utc_now())
    reg["projects"].append(entry)
    save_registry(reg)
    return entry


def touch_opened(project_dir: Path | str) -> dict[str, Any]:
    """Stamp `last_opened`, registering the project first if it isn't yet.
    This is the project-server boot hook (§6): projects that predate the
    registry show up in home after their first open."""
    key = str(canonical(project_dir))
    reg = read_registry()
    entry = _find(reg, key)
    if entry is None:
        entry = _new_entry(key, _utc_now())
        reg["projects"].append(entry)
    entry["last_opened"] = _utc_now()
    save_registry(reg)
    return entry


def set_hidden(project_dir: Path | str, hidden: bool) -> bool:
    """Hide (or unhide) a project on the home screen. **Registry only** —
    nothing on disk is touched, ever (§1.10: the user's word for dropping an
    entry was "forget", which sounds like deleting rness/, so the affordance
    is a hide flag instead; the entry, its metadata, and the folder all stay).
    Returns False when the path isn't registered."""
    key = str(canonical(project_dir))
    reg = read_registry()
    for e in reg["projects"]:
        if e.get("path") == key:
            e["hidden"] = bool(hidden)
            save_registry(reg)
            return True
    return False


# ---------------------------------------------------------------------------
# Seeding from the desktop shell's MRU (§1.3)
# ---------------------------------------------------------------------------

def _created_at_from_disk(project_dir: Path) -> str:
    """A seeded entry's `created_at`: when the `rness/` was made. macOS gives
    us a real birth time; elsewhere mtime is the closest honest answer."""
    try:
        st = (project_dir / "rness").stat()
    except OSError:
        return _utc_now()
    born = getattr(st, "st_birthtime", None)
    if born:
        return _iso_from_ns(int(born * 1_000_000_000))
    return _iso_from_ns(st.st_mtime_ns)


def seed_from_desktop(path: Path | None = None) -> int:
    """One-time seed of the registry from the shell's `known_projects`.

    Only entries that still exist *and* still contain an `rness/` are taken —
    a folder the user deleted or un-enough-ified never enters the registry in
    the first place. Returns how many were added.

    "Once" is enforced with a `seeded` flag rather than by relying on the
    add-if-absent logic: without it, hiding-then-unregistering a project that is
    still in the shell's MRU would resurrect it on the next home boot.
    """
    reg = read_registry()
    if reg.get("seeded"):
        return 0
    src = path or desktop_config_path()
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        known = data.get("known_projects") or []
    except (OSError, ValueError, AttributeError):
        known = []
    added = 0
    for raw in known if isinstance(known, list) else []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        project_dir = canonical(raw)
        if not project_dir.is_dir() or not is_project(project_dir):
            continue
        key = str(project_dir)
        if _find(reg, key) is not None:
            continue
        reg["projects"].append(_new_entry(key, _created_at_from_disk(project_dir)))
        added += 1
    reg["seeded"] = True
    save_registry(reg)
    return added


# ---------------------------------------------------------------------------
# The counters (§1.4) — the top bar's rules, ported verbatim
# ---------------------------------------------------------------------------

def count_text(src: str) -> dict[str, int]:
    """Paragraphs / words / characters for one document.

    A verbatim port of `updateDocCounters()` in index.html — the three
    readouts pinned to the right of the top bar:

    ```js
    const paras = source.split(/\\n\\s*\\n/).filter(p => p.trim()).length;
    const trimmed = source.trim();
    const words = trimmed ? trimmed.split(/\\s+/).length : 0;
    const chars = source.length;
    ```

    Python's `re.split` and bare `str.split()` behave identically on these
    inputs, so opening every counted file and adding up the top bar has to
    produce the registry's numbers — which is exactly what the test asserts.
    (One knowing difference: `len()` counts code points where JS counts
    UTF-16 units, so a document full of astral emoji would disagree on
    `c` alone.)
    """
    paras = len([p for p in re.split(r"\n\s*\n", src) if p.strip()])
    words = len(src.strip().split())
    return {"p": paras, "w": words, "c": len(src)}


def _counted_files(project_dir: Path) -> list[tuple[Path, os.stat_result]]:
    """Every markdown file that counts toward a project's P/W/C, with its
    stat (the fingerprint needs the same walk).

    The rule (§1.4) is "every `.md`/`.markdown` the file tree would SHOW",
    with two deliberate departures:

    - **twins are counted** even though the tree hides them behind their
      original. A `report.pdf.md` is the user's text; hiding it is a display
      decision, not a statement about who wrote it.
    - **`rness/` is not counted**, anywhere it appears. Scaffolding — the
      agent's brief, the policies, the skills — is not the user's writing.

    Everything else matches `server._walk_tree`: dotfiles, `IGNORE_DIRS`,
    `HIDDEN_TREE_PATHS`, the wikisink/cacheawl store dirs, and the same
    symlink-cycle protection.
    """
    # Lazy: server imports us, so a module-level import would cycle. Reaching
    # into server for the rules (rather than copying them) is the point — the
    # counters must never drift from what the sidebar shows.
    from . import server as _server

    hidden_global = _server._hidden_global_dirs()
    out: list[tuple[Path, os.stat_result]] = []

    def walk(rel_parts: tuple[str, ...], visited: frozenset[Path]) -> None:
        here = project_dir.joinpath(*rel_parts)
        try:
            real = here.resolve()
        except OSError:
            return
        if real in visited:
            return
        visited = visited | {real}
        try:
            entries = sorted(here.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for p in entries:
            if p.name.startswith(".") or p.name in _server.IGNORE_DIRS:
                continue
            rel = "/".join(rel_parts + (p.name,))
            if rel in _server.HIDDEN_TREE_PATHS:
                continue
            if p.is_dir():
                if p.name == "rness":
                    continue
                try:
                    if hidden_global and p.resolve() in hidden_global:
                        continue
                except OSError:
                    pass
                walk(rel_parts + (p.name,), visited)
            elif p.suffix.lower() in MARKDOWN_SUFFIXES:
                try:
                    out.append((p, p.stat()))
                except OSError:
                    continue

    walk((), frozenset())
    return out


def fingerprint_of(scanned: list[tuple[Path, os.stat_result]]) -> dict[str, int]:
    """The cheap change detector (§1.5): how many files, the newest mtime,
    and the total size. Computed from stats alone — no file is opened."""
    return {
        "files": len(scanned),
        "max_mtime_ns": max((st.st_mtime_ns for _p, st in scanned), default=0),
        "bytes": sum(st.st_size for _p, st in scanned),
    }


def counts_of(scanned: list[tuple[Path, os.stat_result]]) -> dict[str, int]:
    """Sum `count_text` over the scanned files. Unreadable bytes are replaced
    rather than skipped — a mangled character shouldn't lose a whole file."""
    total = {"p": 0, "w": 0, "c": 0}
    for path, _st in scanned:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        one = count_text(src)
        for key in total:
            total[key] += one[key]
    return total


def refresh_entry(entry: dict[str, Any]) -> bool:
    """Recompute an entry's stats **only if the fingerprint moved** (§1.5).

    Returns True when the entry changed and the registry wants saving. A
    missing or gone project is left exactly as it was — its last known counts
    are more useful than zeroes while the drive is unmounted.
    """
    project_dir = Path(entry["path"])
    if not project_dir.is_dir() or not is_project(project_dir):
        return False
    scanned = _counted_files(project_dir)
    fp = fingerprint_of(scanned)
    if entry.get("fingerprint") == fp and entry.get("counts"):
        return False
    entry["fingerprint"] = fp
    entry["counts"] = counts_of(scanned)
    entry["last_edited"] = _iso_from_ns(fp["max_mtime_ns"]) if fp["max_mtime_ns"] else None
    return True


# ---------------------------------------------------------------------------
# The list the launch screen renders
# ---------------------------------------------------------------------------

def row(entry: dict[str, Any]) -> dict[str, Any]:
    """One project as `GET /api/home/projects` returns it.

    Display name and description are read **live** from `rness/project.json`
    (§2) rather than cached, so a rename shows up the instant the user makes
    it. Counts are always a dict — a never-scanned or missing project reads
    as zeroes rather than making the frontend branch."""
    from . import project_meta

    project_dir = Path(entry["path"])
    missing = not (project_dir.is_dir() and is_project(project_dir))
    meta = project_meta.load(project_dir)
    return {
        "path": entry["path"],
        "name": meta["name"],
        "description": meta["description"],
        "created_at": entry.get("created_at"),
        "last_opened": entry.get("last_opened"),
        "last_edited": entry.get("last_edited"),
        "counts": entry.get("counts") or {"p": 0, "w": 0, "c": 0},
        "missing": missing,
        "hidden": bool(entry.get("hidden")),
    }


def list_projects() -> list[dict[str, Any]]:
    """Every registered project, stats refreshed where the fingerprint moved,
    newest-opened first. Blocking (it walks); callers run it in a thread."""
    reg = read_registry()
    dirty = False
    for entry in reg["projects"]:
        try:
            dirty |= refresh_entry(entry)
        except OSError:  # a drive that vanished mid-walk, say
            log.debug("home: could not refresh %s", entry.get("path"))
    if dirty:
        save_registry(reg)
    rows = [row(e) for e in reg["projects"]]
    rows.sort(key=lambda r: (r["last_opened"] or r["last_edited"] or r["created_at"] or ""),
              reverse=True)
    return rows


# ---------------------------------------------------------------------------
# The project mirror (§1.6)
# ---------------------------------------------------------------------------

def _mirror_skip(project_dir: Path):
    """The tree's visibility rules as a predicate the flowchart helper can
    use: dotfiles, IGNORE_DIRS, HIDDEN_TREE_PATHS, the global store dirs, and
    a converted document's twin + assets folder (one row per document, same
    as the sidebar). Unlike the counters, this one keeps `rness/` — the
    sidebar shows it, so the mirror of what the sidebar shows does too."""
    from . import convert as _convert
    from . import server as _server

    hidden_global = _server._hidden_global_dirs()

    def skip(p: Path) -> bool:
        if p.name.startswith(".") or p.name in _server.IGNORE_DIRS:
            return True
        try:
            rel = p.relative_to(project_dir).as_posix()
        except ValueError:
            return True
        if rel in _server.HIDDEN_TREE_PATHS:
            return True
        if p.is_dir():
            try:
                if hidden_global and p.resolve() in hidden_global:
                    return True
            except OSError:
                pass
            if p.name.endswith(".assets"):
                return _convert.has_twin(p.parent / p.name[: -len(".assets")])
            return False
        if p.name.endswith(".md"):
            return _convert.has_twin(p.parent / p.name[: -len(".md")])
        return False

    return skip


def build_project_mirror(project_dir: Path) -> str:
    """The merirmaid source for a project's visible contents.

    Same `modality: mirror` contract, node shapes and depth cap as a cachebox
    mirror — it *is* the cachebox machinery, called through the shared
    `cacheawl.folder_flowchart` helper with a project's frontmatter. Pure
    generation: nothing is written, here or anywhere.
    """
    from . import cacheawl as _cacheawl
    from . import project_meta

    if not project_dir.is_dir():
        raise HomeError(f"no folder at {project_dir}")
    meta = project_meta.load(project_dir)
    entry = entry_for(project_dir) or {}
    counts = entry.get("counts") or {}
    fp = entry.get("fingerprint") or {}
    meta_lines = [
        f"path: {project_dir}",
        "markdown: {} files · {} ¶ · {} words".format(
            fp.get("files", "?"), counts.get("p", "?"), counts.get("w", "?")),
        f"created: {entry.get('created_at') or '?'}",
        f"last opened: {entry.get('last_opened') or 'never'}",
        f"last edited: {entry.get('last_edited') or '?'}",
    ]
    body, _node_map = _cacheawl.folder_flowchart(
        project_dir,
        f"📁 {meta['name']}",
        meta_lines=meta_lines,
        skip=_mirror_skip(project_dir),
    )
    frontmatter = "\n".join([
        "---",
        "merirmaid: 1",
        f"title: project: {meta['name']}",
        "modality: mirror",
        "node-char-limit: 48",
        f"source: project:{project_dir}",
        f"generated: {_utc_now()}",
        "---",
    ]) + "\n"
    return frontmatter + body


# ---------------------------------------------------------------------------
# Adding a project (§1.8)
# ---------------------------------------------------------------------------

def check_addable(raw: str | Path) -> Path:
    """Guard a folder the user picked, returning its canonical path.

    Three refusals, all with the reason spelled out for the modal to show
    verbatim: the install dir (an `rness/` there would collide with the
    global defaults — the same refusal `enough --dir` makes), a cloud-synced
    root (Drive/Dropbox/iCloud/OneDrive break the skeleton's symlinks and the
    launcher's exec bit), and anything that isn't an existing folder.
    """
    from .skeleton import cloud_sync_provider

    if not str(raw).strip():
        raise HomeError("no folder chosen.")
    project_dir = canonical(raw)
    if project_dir.exists() and not project_dir.is_dir():
        raise HomeError(f"{project_dir} is a file, not a folder.")
    if not project_dir.is_dir():
        # Deliberately not created: the dialog only ever hands back an
        # existing folder, so a path that isn't there came from the typed
        # fallback and is far more likely to be a typo than an intention.
        raise HomeError(f"there's no folder at {project_dir} — make it first, "
                        f"then add it.")
    install_root = canonical(Path.home() / "enough")
    try:
        project_dir.relative_to(install_root)
    except ValueError:
        pass
    else:
        raise HomeError(
            f"{project_dir} is inside the enough install directory "
            f"({install_root}). enough refuses to create a rness/ here because "
            f"its files would collide with the global defaults. Pick any other "
            f"folder.")
    provider = cloud_sync_provider(project_dir)
    if provider:
        raise HomeError(
            f"{project_dir} lives in {provider}. enough builds a project from "
            f"symlinks and a launcher that needs its executable bit, and "
            f"cloud sync preserves neither between machines — the project "
            f"would break the first time it synced. Keep projects on the "
            f"local disk.")
    return project_dir


def add_project(raw: str | Path) -> dict[str, Any]:
    """Enough-ify a folder and register it. Returns the new row.

    Raises `HomeError` for the §1.8 guards. An already-registered folder is
    *not* an error here — the caller (the route) turns it into a 409 that
    carries the existing row, because "already registered" means "just open
    it", not "something went wrong".
    """
    from .skeleton import ensure_skeleton

    project_dir = check_addable(raw)
    ensure_skeleton(project_dir)   # registers on its own (§6)
    register(project_dir)          # belt and braces if that hook ever fails
    reg = read_registry()
    entry = _find(reg, str(project_dir)) or _new_entry(str(project_dir), _utc_now())
    if refresh_entry(entry):
        save_registry(reg)
    return row(entry)


# The native folder chooser. `activate` (wrapped in a try, so a sandbox that
# refuses it doesn't take the whole script down) brings the dialog to the
# front — without it osascript's window can open behind the enough window.
_CHOOSE_FOLDER_SCRIPT = """try
	activate
end try
set chosen to choose folder with prompt "Choose a folder for your enough project"
return POSIX path of chosen
"""


def choose_folder(timeout: float = DIALOG_TIMEOUT_S) -> str | None:
    """Raise the macOS folder chooser and return the chosen POSIX path.

    Returns None when the user cancelled. Raises `DialogUnavailable` when
    there is no dialog to raise (not macOS, no osascript, or osascript
    failed) — the modal then shows its typed-path field instead. The backend
    raises this rather than the shell because the shell's WKWebView page
    cannot open Tauri dialogs, and because it makes the CLI work identically.
    """
    if sys.platform != "darwin":
        raise DialogUnavailable(
            "a native folder chooser is only available on macOS — type the "
            "folder's path instead.")
    exe = shutil.which("osascript")
    if not exe:
        raise DialogUnavailable(
            "osascript isn't on the PATH, so enough can't open a folder "
            "chooser — type the folder's path instead.")
    try:
        proc = subprocess.run([exe, "-e", _CHOOSE_FOLDER_SCRIPT],
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DialogUnavailable(f"the folder chooser didn't open ({exc}).") from None
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if "-128" in err or "cancel" in err.lower():
            return None            # the user closed the dialog; not an error
        raise DialogUnavailable(
            err or f"the folder chooser exited with status {proc.returncode}.")
    chosen = (proc.stdout or "").strip()
    if not chosen:
        return None
    return chosen.rstrip("/") or "/"


# ---------------------------------------------------------------------------
# The open/close handshake (§1.7)
# ---------------------------------------------------------------------------

def write_handoff(project_dir: Path | str) -> Path:
    """Write `.home-open` (tmp+rename) with the project the shell should
    launch after we exit 42. Plain text, one absolute path, trailing newline —
    the shell reads it as a string and deletes it."""
    path = handoff_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f"{path.name}.tmp"
    tmp.write_text(f"{canonical(project_dir)}\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_handoff(*, consume: bool = True) -> Path | None:
    """Read (and by default delete) the handoff file. The shell does this
    itself in Rust; this is the Python half of the contract, used by the
    tests and by anything that needs to know what home asked for."""
    path = handoff_path()
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if consume:
        try:
            path.unlink()
        except OSError:
            pass
    return Path(raw) if raw else None


def exec_argv(
    *,
    project_dir: Path | None,
    port: int,
    llm_url: str,
    max_tool_iters: int,
    supervise: bool,
) -> list[str]:
    """The argv for re-exec'ing ourselves into the other mode (§1.7, CLI).

    Canonical form rather than a copy of `sys.argv`: `-m enough` runs the
    same install whether this process was started by the console script, by
    `python -m`, or by `uv run`, and `sys.executable` is that install's
    python in all three cases. Port and flags are preserved so the browser
    tab that is already open reconnects to the same URL; `--no-browser`
    because that tab exists.

    Every flag rides along in **both** directions, `--llm-url` included, even
    though home itself has no llm: a QA run pointed at a scratch llama-server
    must not come back from a round trip pointed at the machine's real one.
    """
    argv = [sys.executable, "-m", "enough", "--port", str(port), "--no-browser",
            "--llm-url", llm_url, "--max-tool-iters", str(max_tool_iters)]
    if not supervise:
        argv.append("--no-supervise")
    argv += ["--home"] if project_dir is None else ["--dir", str(project_dir)]
    return argv
