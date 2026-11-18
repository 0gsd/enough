"""What several route groups share: the context `create_app` builds them from, and the project-path helpers.

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `build_shared` is
the old factory's closure for these helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import canon as _canon
from ..server import _store_prefix


class AppContext:
    """What `create_app` hands every route module: the names its routes used to close over, and the
    helpers one group defines and another (or the factory) reads. Plain attributes; set once at build."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


def build_shared(ctx: AppContext) -> None:
    project_dir = ctx.project_dir

    def _resolve_project_path(path: str) -> Path:
        """Shared path-safety helper for /api/file{,/raw} and POST writes.

        Containment check is done on the LOGICAL path (composition) so that
        symlinks living at a valid relative location inside rness/ and
        pointing outside the project — intentional, used for global
        defaults — aren't rejected. The tool layer has its own allowlist
        for follow-through reads; this helper guards only against path-
        string traversal (absolute paths and `..` components).

        A `canon:<volume>/<rel>` prefix addresses the machine-global Canon store
        instead of the project — that's how Canon mode launches store files
        into read/edit, girraph, and merirmaid modes. Same traversal rules
        apply inside the store; the catalog and sidecar write-guards
        downstream see the resolved target and keep applying."""
        prefix = _store_prefix(path)
        if prefix:
            rel = Path(path[len(prefix):].lstrip("/"))
            if rel.is_absolute() or ".." in rel.parts or not rel.parts:
                raise HTTPException(400, "invalid path")
            return _canon.root().resolve() / rel
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise HTTPException(400, "invalid path")
        # Compose against the resolved project root so we don't end up with
        # /tmp-vs-/private/tmp mismatches on macOS. Don't resolve the final
        # target — that would follow symlinks and break containment checks
        # for in-tree symlinks.
        project_root = project_dir.resolve()
        return project_root / p

    def _is_request_file(path: str) -> bool:
        p = Path(path)
        parts = p.parts
        # Active request = directly under rness/requests/ (not /done/).
        return (
            len(parts) >= 3
            and parts[0] == "rness"
            and parts[1] == "requests"
            and parts[2] != "done"
            and parts[-1].endswith(".md")
        )

    def _is_skill_file(path: str) -> bool:
        parts = Path(path).parts
        return len(parts) >= 2 and parts[0] == "rness" and parts[1] == "skills"

    def _is_role_file(path: str) -> bool:
        # Both folder names: `readvisors` since 0.3.5, `roles` on a project
        # whose rename could not run. See skeleton._migrate_roles_to_readvisors.
        parts = Path(path).parts
        return (len(parts) >= 2 and parts[0] == "rness"
                and parts[1] in ("readvisors", "roles"))

    def _is_external_symlink(path_str: str) -> tuple[bool, Path | None]:
        """Is `path` a symlink whose resolved target lives outside the project?
        Returns (yes_external, target_abs) for the truthy case."""
        raw = project_dir / path_str
        if not raw.is_symlink():
            return False, None
        target = raw.resolve(strict=False)
        try:
            target.relative_to(project_dir.resolve())
            return False, target  # resolves inside the project — treat as normal
        except ValueError:
            return True, target

    ctx._is_external_symlink = _is_external_symlink
    ctx._is_request_file = _is_request_file
    ctx._is_role_file = _is_role_file
    ctx._is_skill_file = _is_skill_file
    ctx._resolve_project_path = _resolve_project_path
