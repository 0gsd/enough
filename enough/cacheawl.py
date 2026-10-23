"""cacheawl — the pre-0.4.3 name of Canon, kept as a shim for one release.

Cacheawl became Canon in 0.4.3 (docs/canon-043-plan.md §6.1): the store
moved to ``~/enough/canon/``, a cachebox is now a **volume**, and the module
is ``enough/canon.py``. This file exists so code written against the old
names keeps importing for one release; it holds no logic. Every public name
the old module had is re-exported here, mapped to its Canon counterpart:

- ``box_dir`` → ``canon.volume_dir``; ``cachebox_summary`` / ``list_cacheboxes``
  / ``cachebox_tree`` / ``create_cachebox`` / ``rename_cachebox`` /
  ``delete_cachebox`` → the ``*_volume`` / ``list_volumes`` functions;
- ``regenerate_mirror`` → ``canon.regenerate_catalog`` (the mirror is no
  longer persisted; the catalog ``canon.cosm`` is what reconcile writes);
- ``is_mirror_file`` / ``mirror_write_denial`` → ``canon.is_catalog_file`` /
  ``canon.catalog_write_denial`` (which still refuse ``modality: mirror``
  files and the old ``.cachebox.json``);
- ``CacheawlError`` → ``canon.CanonError``;
- the constants, with ``META_NAME`` now ``.canon.json`` and ``MIRROR_NAME``
  the old ``_cachebox.merirmaid`` (never written, only cleaned up).

New code imports ``enough.canon``. Delete this file in the release after
0.4.3.
"""

from __future__ import annotations

from . import canon as _canon
from .canon import (  # noqa: F401 — re-exports
    DEFAULT_ROOT,
    INGEST_PATH_FILE_CAP,
    INGEST_URL_PAGE_CAP,
    INGEST_WIKI_ARTICLE_CAP,
    META_NAME,
    MIRROR_MAX_DEPTH,
    MIRROR_NAME,
    build_mirror,
    folder_flowchart,
    ingest_status,
    load_meta,
    migrate_infoworld,
    posix_dirname,
    reconcile,
    reconcile_all,
    register_ingest,
    root,
    run_ingest,
    save_meta,
    transfer,
)

CacheawlError = _canon.CanonError

box_dir = _canon.volume_dir
regenerate_mirror = _canon.regenerate_catalog
is_mirror_file = _canon.is_catalog_file
mirror_write_denial = _canon.catalog_write_denial
cachebox_summary = _canon.volume_summary
list_cacheboxes = _canon.list_volumes
cachebox_tree = _canon.volume_tree
create_cachebox = _canon.create_volume
rename_cachebox = _canon.rename_volume
delete_cachebox = _canon.delete_volume

# Private helpers the old module's tests and callers reached for.
_require_box = _canon._require_volume
_node_id = _canon._node_id
_content_files = _canon._content_files

__all__ = [
    "CacheawlError", "DEFAULT_ROOT", "INGEST_PATH_FILE_CAP", "INGEST_URL_PAGE_CAP",
    "INGEST_WIKI_ARTICLE_CAP", "META_NAME", "MIRROR_MAX_DEPTH", "MIRROR_NAME",
    "box_dir", "build_mirror", "cachebox_summary", "cachebox_tree", "create_cachebox",
    "delete_cachebox", "folder_flowchart", "ingest_status", "is_mirror_file", "list_cacheboxes",
    "load_meta", "migrate_infoworld", "mirror_write_denial", "posix_dirname", "reconcile",
    "reconcile_all", "regenerate_mirror", "register_ingest", "rename_cachebox", "root",
    "run_ingest", "save_meta", "transfer",
]
