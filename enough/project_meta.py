"""Per-project display metadata: an editable name + free-text description.

Stored at `rness/project.json` (a plain copy file — no symlinks — so it
survives cloud-sync filesystems just fine). The *display name* is purely
cosmetic: it never renames the folder on disk. The *description* is
user-authored project intent and is injected into the agent's system
prompt by `prompt.assemble_system_prompt`.

Shape on disk:

    {"name": "My Book", "description": "A memoir about ...",
     "ui": {"ui_scale": 1.2, "text_scale": 1.0,
            "readvisor_panel": "open"}}

An empty/absent `name` means "fall back to the folder's basename", so the
user can reset to the folder name by clearing the field.

The optional `ui` block holds the per-project display scales (the prefs
modal's "ui scale" / "text scale" steppers) and whether the readvisor panel
starts docked. Per-project on purpose: a manuscript folder read on a TV
wants different sizing than a notes folder on a laptop, and neither should
drag the other along. The client owns the smart, resolution-aware limits;
this module only refuses garbage.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

META_REL = "rness/project.json"

# Generous cap so the description can be a few hundred words without ever
# becoming a system-prompt bloat hazard. ~8k chars ≈ 1,200-1,500 words.
MAX_DESCRIPTION_CHARS = 8000
MAX_NAME_CHARS = 120

# Hard sanity clamp for the display scales. The frontend enforces the real
# (screen-aware) limits; these only stop a corrupt/hostile write from
# persisting something unusable.
UI_SCALE_MIN = 0.3
UI_SCALE_MAX = 4.0

# The readvisor panel's docked/closed state (composure round, P3). Only the
# two docked states persist — `rv-full` is a transient "I'm reading the
# conversation right now" gesture, never something a project reopens into.
READVISOR_PANEL_STATES = ("open", "closed")
DEFAULT_READVISOR_PANEL = "open"

DEFAULT_UI = {
    "ui_scale": 1.0,
    "text_scale": 1.0,
    "readvisor_panel": DEFAULT_READVISOR_PANEL,
}

# What the project's base-layer canvas opens with (composure round, P4d).
#   blank — a new, unwritten blank page every time (the default)
#   last  — the composure most recently opened in this project
#   file  — one specific composure, named in `path`
#   form  — a new composure from the form named in `form`
# `last` is bookkeeping, not a setting: `touch_composure` stamps it whenever
# a composure with a real path is opened, whatever the launch mode is, so
# switching TO "last" later has something to resolve.
COMPOSURE_LAUNCH_MODES = ("blank", "last", "file", "form")
DEFAULT_COMPOSURE_LAUNCH = "blank"
DEFAULT_COMPOSURE = {
    "launch": DEFAULT_COMPOSURE_LAUNCH,
    "path": "",
    "form": "",
    "last": "",
}
MAX_COMPOSURE_PATH_CHARS = 400


def _clean_scale(value: object) -> float:
    """One display scale: float, rounded to the 0.1 grid, clamped, and 1.0
    for anything unparseable (None, strings, NaN, bools)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    f = float(value)
    if f != f:  # NaN
        return 1.0
    return min(UI_SCALE_MAX, max(UI_SCALE_MIN, round(f, 1)))


def _clean_panel(value: object) -> str:
    """The readvisor panel state: one of READVISOR_PANEL_STATES, defaulting
    to "open". Anything else (None, a bool, a typo, "full") reads as the
    default — a project should never fail to open over a cosmetic key."""
    if isinstance(value, str) and value in READVISOR_PANEL_STATES:
        return value
    return DEFAULT_READVISOR_PANEL


def _clean_ui(raw: object) -> dict:
    ui = raw if isinstance(raw, dict) else {}
    return {
        "ui_scale": _clean_scale(ui.get("ui_scale")),
        "text_scale": _clean_scale(ui.get("text_scale")),
        "readvisor_panel": _clean_panel(ui.get("readvisor_panel")),
    }


def _clean_comp_rel(value: object) -> str:
    """A project-relative `.comp` path, or "" for anything unusable.

    Absolute paths and `..` are refused here as well as at the endpoint: a
    launch setting is read at boot, before any request has been validated,
    and a hand-edited project.json must never be able to point it outside
    the project."""
    s = str(value or "").strip().replace("\\", "/")[:MAX_COMPOSURE_PATH_CHARS]
    if not s or not s.endswith(".comp"):
        return ""
    parts = PurePosixPath(s).parts
    if s.startswith("/") or ".." in parts or not parts:
        return ""
    return s


def _clean_form_name(value: object) -> str:
    """A form name is a plain slug — never a path, because it is joined to
    a forms directory."""
    s = str(value or "").strip()[:64]
    return s if re.fullmatch(r"[a-z0-9][a-z0-9-]*", s or "") else ""


def _clean_composure(raw: object) -> dict:
    c = raw if isinstance(raw, dict) else {}
    launch = c.get("launch")
    return {
        "launch": launch if launch in COMPOSURE_LAUNCH_MODES else DEFAULT_COMPOSURE_LAUNCH,
        "path": _clean_comp_rel(c.get("path")),
        "form": _clean_form_name(c.get("form")),
        "last": _clean_comp_rel(c.get("last")),
    }


def _read_raw(project_dir: Path) -> dict:
    """The on-disk JSON dict, {} when absent/corrupt. Shared by the two
    writers so each preserves the keys it doesn't own."""
    path = _meta_path(project_dir)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _meta_path(project_dir: Path) -> Path:
    return project_dir / META_REL


def load(project_dir: Path) -> dict:
    """Return the project's display metadata, always populated.

    Keys:
      - name:        display name (falls back to the folder basename)
      - description: user-authored description ("" when unset)
      - path:        absolute folder path on disk (read-only, never edited)
      - folder:      the folder's basename (what `name` defaults to)
      - ui:          display block, always populated ({"ui_scale": 1.0,
                     "text_scale": 1.0, "readvisor_panel": "open"} when
                     unset)
      - composure:   what the base-layer canvas opens with, always populated
                     ({"launch": "blank", "path": "", "form": "",
                     "last": ""} when unset)
    """
    # Corrupt/unreadable metadata is non-fatal: _read_raw falls back to
    # defaults rather than breaking the whole project load.
    data = _read_raw(project_dir)
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "")
    return {
        "name": name or project_dir.name,
        "description": description,
        "path": str(project_dir),
        "folder": project_dir.name,
        "ui": _clean_ui(data.get("ui")),
        "composure": _clean_composure(data.get("composure")),
    }


def save(project_dir: Path, name: str | None, description: str | None) -> dict:
    """Persist name + description to `rness/project.json` and return the
    refreshed `load()` view.

    - `name` is trimmed and length-capped; an empty name is stored as ""
      so it falls back to the folder basename on read (i.e. "reset").
    - `description` is length-capped and right-stripped of trailing
      whitespace, but otherwise preserved verbatim (newlines included).
    """
    clean_name = (name or "").strip()[:MAX_NAME_CHARS]
    clean_desc = (description or "").replace("\r\n", "\n")[:MAX_DESCRIPTION_CHARS].rstrip()

    # Read-modify-write: the name/description editor must not clobber the
    # `ui` block (and vice versa — see save_ui).
    data = _read_raw(project_dir)
    data["name"] = clean_name
    data["description"] = clean_desc

    path = _meta_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load(project_dir)


def save_composure(
    project_dir: Path,
    launch: object,
    path_rel: object = None,
    form: object = None,
) -> dict:
    """Persist the composure launch setting and return the refreshed
    `load()` view.

    Separate writer, same read-modify-write discipline as `save_ui`: the
    "on launch, open…" control and the display steppers are different
    gestures and must not clobber each other's half of
    `rness/project.json`. The `last` key is never written here — it is
    bookkeeping owned by `touch_composure`, so choosing "a specific
    composure" cannot erase the trail that "the last composure used" needs.

    A `launch` this module does not recognize resolves to "blank" rather
    than raising: a project must always open."""
    data = _read_raw(project_dir)
    prior = _clean_composure(data.get("composure"))
    mode = launch if launch in COMPOSURE_LAUNCH_MODES else DEFAULT_COMPOSURE_LAUNCH
    data["composure"] = {
        "launch": mode,
        "path": prior["path"] if path_rel is None else _clean_comp_rel(path_rel),
        "form": prior["form"] if form is None else _clean_form_name(form),
        "last": prior["last"],
    }

    meta = _meta_path(project_dir)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load(project_dir)


def touch_composure(project_dir: Path, path_rel: str) -> dict:
    """Record `path_rel` as the composure most recently opened.

    Called from `GET /api/composure` whenever a composure with a real path
    is opened — whatever the launch mode is, so that switching to "the last
    composure used" later has something to resolve. A no-op (no write at
    all) when the value has not changed, because this runs on every open and
    a project.json that is rewritten on every canvas read would be noise in
    the user's version control."""
    rel = _clean_comp_rel(path_rel)
    if not rel:
        return load(project_dir)
    data = _read_raw(project_dir)
    prior = _clean_composure(data.get("composure"))
    if prior["last"] == rel:
        return load(project_dir)
    prior["last"] = rel
    data["composure"] = prior

    meta = _meta_path(project_dir)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load(project_dir)


def save_ui(
    project_dir: Path,
    ui_scale: object,
    text_scale: object,
    readvisor_panel: object = None,
) -> dict:
    """Persist the per-project display block and return the refreshed
    `load()` view. Scales are rounded to the 0.1 grid and hard-clamped to
    [0.3, 4.0]; unparseable input resets that scale to 1.0.

    `readvisor_panel` left at None means "keep whatever is on disk" — the
    scale steppers and the panel toggle are separate gestures and must not
    clobber each other's half of the block, the same way `save` and
    `save_ui` don't clobber each other's half of the file.
    """
    data = _read_raw(project_dir)
    prior = _clean_ui(data.get("ui"))
    data["ui"] = {
        "ui_scale": _clean_scale(ui_scale),
        "text_scale": _clean_scale(text_scale),
        "readvisor_panel": (
            prior["readvisor_panel"]
            if readvisor_panel is None
            else _clean_panel(readvisor_panel)
        ),
    }

    path = _meta_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load(project_dir)
