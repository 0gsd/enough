"""Per-project display metadata: an editable name + free-text description.

Stored at `rness/project.json` (a plain copy file — no symlinks — so it
survives cloud-sync filesystems just fine). The *display name* is purely
cosmetic: it never renames the folder on disk. The *description* is
user-authored project intent and is injected into the agent's system
prompt by `prompt.assemble_system_prompt`.

Shape on disk:

    {"name": "My Book", "description": "A memoir about ...",
     "ui": {"ui_scale": 1.2, "text_scale": 1.0}}

An empty/absent `name` means "fall back to the folder's basename", so the
user can reset to the folder name by clearing the field.

The optional `ui` block holds the per-project display scales (the prefs
modal's "ui scale" / "text scale" steppers). Per-project on purpose: a
manuscript folder read on a TV wants different sizing than a notes folder
on a laptop, and neither should drag the other along. The client owns the
smart, resolution-aware limits; this module only refuses garbage.
"""

from __future__ import annotations

import json
from pathlib import Path

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
DEFAULT_UI = {"ui_scale": 1.0, "text_scale": 1.0}


def _clean_scale(value: object) -> float:
    """One display scale: float, rounded to the 0.1 grid, clamped, and 1.0
    for anything unparseable (None, strings, NaN, bools)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    f = float(value)
    if f != f:  # NaN
        return 1.0
    return min(UI_SCALE_MAX, max(UI_SCALE_MIN, round(f, 1)))


def _clean_ui(raw: object) -> dict:
    ui = raw if isinstance(raw, dict) else {}
    return {
        "ui_scale": _clean_scale(ui.get("ui_scale")),
        "text_scale": _clean_scale(ui.get("text_scale")),
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
      - ui:          display scales, always populated ({"ui_scale": 1.0,
                     "text_scale": 1.0} when unset)
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


def save_ui(project_dir: Path, ui_scale: object, text_scale: object) -> dict:
    """Persist the per-project display scales and return the refreshed
    `load()` view. Values are rounded to the 0.1 grid and hard-clamped to
    [0.3, 4.0]; unparseable input resets that scale to 1.0."""
    data = _read_raw(project_dir)
    data["ui"] = {
        "ui_scale": _clean_scale(ui_scale),
        "text_scale": _clean_scale(text_scale),
    }

    path = _meta_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return load(project_dir)
