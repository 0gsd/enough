"""Per-project display metadata: an editable name + free-text description.

Stored at `rness/project.json` (a plain copy file — no symlinks — so it
survives cloud-sync filesystems just fine). The *display name* is purely
cosmetic: it never renames the folder on disk. The *description* is
user-authored project intent and is injected into the agent's system
prompt by `prompt.assemble_system_prompt`.

Shape on disk:

    {"name": "My Book", "description": "A memoir about ..."}

An empty/absent `name` means "fall back to the folder's basename", so the
user can reset to the folder name by clearing the field.
"""

from __future__ import annotations

import json
from pathlib import Path

META_REL = "rness/project.json"

# Generous cap so the description can be a few hundred words without ever
# becoming a system-prompt bloat hazard. ~8k chars ≈ 1,200-1,500 words.
MAX_DESCRIPTION_CHARS = 8000
MAX_NAME_CHARS = 120


def _meta_path(project_dir: Path) -> Path:
    return project_dir / META_REL


def load(project_dir: Path) -> dict:
    """Return the project's display metadata, always populated.

    Keys:
      - name:        display name (falls back to the folder basename)
      - description: user-authored description ("" when unset)
      - path:        absolute folder path on disk (read-only, never edited)
      - folder:      the folder's basename (what `name` defaults to)
    """
    name, description = "", ""
    path = _meta_path(project_dir)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                name = str(data.get("name") or "").strip()
                description = str(data.get("description") or "")
        except (OSError, json.JSONDecodeError):
            # Corrupt/unreadable metadata is non-fatal: fall back to defaults
            # rather than breaking the whole project load.
            pass
    return {
        "name": name or project_dir.name,
        "description": description,
        "path": str(project_dir),
        "folder": project_dir.name,
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

    path = _meta_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": clean_name, "description": clean_desc}, indent=2) + "\n",
        encoding="utf-8",
    )
    return load(project_dir)
