"""cacheawl — the global file-management store at ``~/enough/cacheawl/``.

A **cachebox** is a ROOT-LEVEL folder inside ``~/enough/cacheawl/``. Only
direct children of the store are cacheboxes; folders nested deeper are
plain folders. A cachebox holds text files the user wants to keep forever
plus two backend-owned sidecars:

- ``.cachebox.json``     — hidden metadata (origin request, status,
                           timestamps, a cheap tree fingerprint used by
                           the reconcile check). Never shown in trees.
- ``_cachebox.merirmaid`` — an auto-generated ``modality: mirror`` diagram
                           of the box's contents + a metadata node, per
                           docs/merirmaid-plan.md's "cachebox mirror
                           contract". Regenerated on every mutation the
                           backend makes; read-only to the agent/UI.

Some cacheboxes are plain folders; others are "cached replicas" ingested
from a source (a local path, a website URL, or a set of wikisink
articles) to a user-chosen depth.

This module owns everything under the store. The root is resolvable via
``ENOUGH_CACHEAWL_ROOT`` (a test/dev hook, mirroring the
``ENOUGH_WIKISINK_CONFIG`` precedent) so suites never touch the real
``~/enough/cacheawl``.

Path-traversal safety: every path that crosses the store boundary is
``.resolve()``d and verified to sit under its declared root before any
filesystem op — the same ``/var`` vs ``/private/var`` discipline
``cloud.pipeline_run()`` uses.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
import shutil
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("enough.cacheawl")

# ENOUGH_CACHEAWL_ROOT overrides the store location — the test/dev hook so
# suites and smoke runs never mutate the real ~/enough/cacheawl.
DEFAULT_ROOT = Path.home() / "enough" / "cacheawl"

META_NAME = ".cachebox.json"
MIRROR_NAME = "_cachebox.merirmaid"

# Presentation depth cap for the mirror. A subtree deeper than this
# collapses into a single "[N items]" node so a huge box can't produce a
# multi-thousand-node diagram.
MIRROR_MAX_DEPTH = 4

# Hard caps for ingest runs.
INGEST_URL_PAGE_CAP = 500
INGEST_WIKI_ARTICLE_CAP = 200
INGEST_PATH_FILE_CAP = 20000

# Files a text ingest should skip on extension alone (binary by nature).
_BINARY_EXTS = frozenset({
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".ico",
    ".webp", ".heic", ".heif", ".svg",  # svg is text but usually chrome noise
    # audio / video
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".mp4", ".mov",
    ".avi", ".mkv", ".webm", ".wmv", ".m4v",
    # archives / disk images
    ".zip", ".gz", ".bz2", ".xz", ".tar", ".7z", ".rar", ".dmg", ".iso",
    ".jar", ".war",
    # executables / objects
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".bin", ".class",
    ".wasm", ".pyc", ".pyo",
    # fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # office / pdf (binary containers)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".key", ".numbers", ".pages",
    # data blobs
    ".db", ".sqlite", ".sqlite3", ".parquet", ".npy", ".npz", ".pkl",
    ".h5", ".hdf5", ".onnx", ".gguf", ".safetensors", ".zim",
})

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")


class CacheawlError(ValueError):
    """Raised for a bad request or a forbidden op. Messages are written
    for the agent's eyes — actionable, name the fix."""


# ---------------------------------------------------------------------------
# Root + small helpers
# ---------------------------------------------------------------------------

def root() -> Path:
    """The cacheawl store root, honoring ENOUGH_CACHEAWL_ROOT. Created on
    demand (the store is a flat dir of cacheboxes)."""
    raw = os.environ.get("ENOUGH_CACHEAWL_ROOT") or str(DEFAULT_ROOT)
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise CacheawlError("a cachebox needs a name.")
    if name in (".", ".."):
        raise CacheawlError(f"{name!r} is not a valid cachebox name.")
    if not _NAME_RE.match(name):
        raise CacheawlError(
            f"invalid cachebox name {name!r} — use letters, digits, spaces, "
            f"hyphens or underscores (must not start with a symbol; 64 chars max)."
        )
    return name


def box_dir(name: str) -> Path:
    """Absolute path of a cachebox folder (not required to exist)."""
    return root() / _validate_name(name)


def _is_cachebox(name: str) -> bool:
    try:
        return box_dir(name).is_dir()
    except CacheawlError:
        return False


def _require_box(name: str) -> Path:
    d = box_dir(name)
    if not d.is_dir():
        raise CacheawlError(
            f"no cachebox named {name!r}. list cacheboxes first (cachebox_list) "
            f"or create it (cachebox_create)."
        )
    return d


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (s[:max_len].strip("-")) or "x"


def _sizeof_human(n: int) -> str:
    step = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if step < 1024 or unit == "TB":
            return f"{step:.0f} {unit}" if unit == "B" else f"{step:.1f} {unit}"
        step /= 1024
    return f"{n} B"


def _is_sidecar(p: Path) -> bool:
    """The backend-owned files that never count toward item/size totals and
    never appear as ordinary tree entries: the metadata json and any
    dotfile. The mirror IS shown in trees (it opens in the merirmaid
    viewer) but is excluded from content fingerprints/totals."""
    return p.name == META_NAME or p.name.startswith(".")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def _meta_path(name: str) -> Path:
    return box_dir(name) / META_NAME


def _default_meta(name: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "name": name,
        "origin": {"type": "folder", "value": None, "depth": None},
        "status": "complete",     # complete | ingesting | failed
        "created_at": now,
        "updated_at": now,
        "ingest": None,           # progress payload while/after an ingest
        "fingerprint": "",        # cheap content hash for the reconcile check
    }


def load_meta(name: str) -> dict[str, Any]:
    """Metadata for a cachebox, defaulted for any missing key. A box with
    no ``.cachebox.json`` (e.g. a manually-created folder) still returns a
    sane default so callers never handle KeyError."""
    base = _default_meta(name)
    p = _meta_path(name)
    if p.is_file():
        try:
            on_disk = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                for k in base:
                    if k in on_disk:
                        base[k] = on_disk[k]
        except (OSError, json.JSONDecodeError) as e:
            log.warning("cachebox meta read failed for %s (%s); defaulting", name, e)
    base["name"] = name
    return base


def save_meta(name: str, meta: dict[str, Any]) -> None:
    meta = dict(meta)
    meta["name"] = name
    meta["updated_at"] = _now_iso()
    p = _meta_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tree scanning + stats
# ---------------------------------------------------------------------------

def _scan_tree(box: Path, rel_parts: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Nested tree of a cachebox for the UI icon grid. Folders first, then
    files, each alphabetical. Dotfiles + the metadata json are omitted; the
    mirror file is included (flagged) so the UI can route it to the viewer."""
    here = box.joinpath(*rel_parts)
    try:
        entries = sorted(
            here.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        )
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for p in entries:
        if p.name == META_NAME or (p.name.startswith(".") and p.name != META_NAME):
            continue
        rel = "/".join(rel_parts + (p.name,))
        node: dict[str, Any] = {
            "name": p.name,
            "path": rel,
            "is_dir": p.is_dir(),
        }
        if p.is_dir():
            node["children"] = _scan_tree(box, rel_parts + (p.name,))
        else:
            try:
                node["size"] = p.stat().st_size
            except OSError:
                node["size"] = 0
            if p.name == MIRROR_NAME:
                node["is_mirror"] = True
            elif p.name == "article.html":
                # Saved wikisink article (folder shape: article.html +
                # .meta.json sidecar) — the UI routes these into the
                # wikisink reader, not the raw-text editor.
                try:
                    if (p.parent / ".meta.json").is_file():
                        node["wiki_article"] = True
                except OSError:
                    pass
        out.append(node)
    return out


def _content_files(box: Path) -> list[Path]:
    """Every real content file in the box (recursive), excluding the mirror,
    metadata json, and any dotfile."""
    out: list[Path] = []
    for p in sorted(box.rglob("*")):
        if not p.is_file():
            continue
        if p.name == MIRROR_NAME or p.name == META_NAME:
            continue
        if any(part.startswith(".") for part in p.relative_to(box).parts):
            continue
        out.append(p)
    return out


def _stats(box: Path) -> dict[str, int]:
    files = _content_files(box)
    total = 0
    for f in files:
        try:
            total += f.stat().st_size
        except OSError:
            pass
    dirs = {p for p in box.rglob("*") if p.is_dir()}
    return {"item_count": len(files), "dir_count": len(dirs),
            "total_size": total}


def _fingerprint(box: Path) -> str:
    """Cheap content fingerprint: (relpath, size, mtime-int) of every content
    file, hashed. Changes whenever a file is added/removed/edited — the
    reconcile check compares this against the value stored in metadata to
    catch manual drops the backend didn't perform."""
    h = hashlib.sha256()
    for f in _content_files(box):
        try:
            st = f.stat()
        except OSError:
            continue
        rel = f.relative_to(box).as_posix()
        h.update(f"{rel}\0{st.st_size}\0{int(st.st_mtime)}\n".encode("utf-8", "ignore"))
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Mirror generation (the cachebox mirror contract)
# ---------------------------------------------------------------------------

def _node_id(rel: str) -> str:
    """Stable mermaid node id derived from a relative path — deterministic
    so diffs between regenerations stay readable. The short hash keeps two
    different paths that slugify identically from colliding."""
    if rel == "":
        return "root"
    slug = _slugify(rel, max_len=40)
    digest = hashlib.sha256(rel.encode("utf-8", "ignore")).hexdigest()[:6]
    return f"n_{slug}_{digest}"


def _mm_label(text: str) -> str:
    """Neutralize characters that would break a quoted mermaid node label."""
    return (text.replace("\\", "／").replace('"', "'")
            .replace("[", "(").replace("]", ")")
            .replace("{", "(").replace("}", ")")
            .replace("\n", " ").strip())


def _safe_subrel(box: Path, subpath: str) -> tuple[str, ...]:
    """Validate a box-relative subfolder path and return its parts. ``""``
    (or ``/``) → the box root (empty tuple). Rejects absolute paths, ``..``
    components, and anything resolving outside the box, and requires the
    target to be an existing directory. Raises ``CacheawlError`` otherwise —
    the same traversal discipline the transfer/`cacheawl:` scheme apply."""
    sub = (subpath or "").strip().strip("/")
    if not sub:
        return ()
    p = Path(sub)
    if p.is_absolute() or ".." in p.parts:
        raise CacheawlError(f"invalid subpath: {subpath!r}")
    target = box / p
    try:
        target.resolve(strict=False).relative_to(box.resolve(strict=False))
    except ValueError:
        raise CacheawlError(f"subpath escapes the cachebox: {subpath!r}") from None
    if not target.is_dir():
        raise CacheawlError(f"no such folder in cachebox: {subpath!r}")
    return p.parts


def _mirror_body(name: str, meta: dict[str, Any], box: Path,
                 subpath: str = "") -> tuple[str, dict[str, dict[str, Any]]]:
    """The Mermaid ``flowchart TD`` for a cachebox (``subpath=""``) or a
    subfolder within it: a root node, folder and file nodes mirroring the
    tree (depth-capped), and a metadata node.

    Returns ``(body, node_map)`` where ``node_map`` is ``{node_id: {"path":
    <box-relative path>, "is_dir": bool}}`` — the viewer's shift-click menu
    resolves a rendered node back to its on-disk location through it. Paths
    are relative to the **box root** regardless of ``subpath`` (join with
    the box dir for the absolute path)."""
    subrel = _safe_subrel(box, subpath)
    base = box.joinpath(*subrel)
    lines = ["flowchart TD"]
    edges: list[str] = []
    node_map: dict[str, dict[str, Any]] = {}
    stats = _stats(base)

    root_id = "root"
    root_label = f"📁 {_mm_label(subrel[-1])}" if subrel else f"📦 {_mm_label(name)}"
    lines.append(f'  {root_id}["{root_label}"]')
    node_map[root_id] = {"path": "/".join(subrel), "is_dir": True}

    # Metadata node — full origin for a box root; a lighter folder header
    # for a subfolder (origin is box-level, not per-folder).
    if subrel:
        meta_lines = [
            f"folder: {'/'.join(subrel)}",
            f"in cachebox: {name}",
            f"items: {stats['item_count']} · size: {_sizeof_human(stats['total_size'])}",
        ]
    else:
        origin = meta.get("origin") or {}
        otype = origin.get("type") or "folder"
        oval = origin.get("value")
        odepth = origin.get("depth")
        origin_str = otype
        if oval:
            origin_str += f": {oval}"
        if odepth not in (None, ""):
            origin_str += f" (depth {odepth})"
        meta_lines = [
            f"origin: {origin_str}",
            f"status: {meta.get('status', 'complete')}",
            f"items: {stats['item_count']} · size: {_sizeof_human(stats['total_size'])}",
            f"created: {meta.get('created_at', '?')}",
            f"updated: {meta.get('updated_at', '?')}",
        ]
    meta_label = _mm_label("<br/>".join(meta_lines))
    lines.append(f'  meta["🛈 {meta_label}"]')
    edges.append(f"  {root_id} -.-> meta")

    def walk(rel_parts: tuple[str, ...], parent_id: str, level: int) -> None:
        here = box.joinpath(*rel_parts)
        try:
            entries = sorted(
                here.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return
        entries = [e for e in entries
                   if e.name != META_NAME and e.name != MIRROR_NAME
                   and not e.name.startswith(".")]
        # Depth cap: collapse everything below the cap into one count node.
        if level >= MIRROR_MAX_DEPTH and entries:
            descendants = [p for p in here.rglob("*") if p.is_file()
                           and p.name not in (META_NAME, MIRROR_NAME)]
            cid = _node_id("/".join(rel_parts) + "/…")
            lines.append(f'  {cid}["… {len(descendants)} items"]')
            edges.append(f"  {parent_id} --> {cid}")
            # The collapse node stands in for its (uncollapsed) folder.
            node_map[cid] = {"path": "/".join(rel_parts), "is_dir": True}
            return
        for e in entries:
            rel = "/".join(rel_parts + (e.name,))
            nid = _node_id(rel)
            node_map[nid] = {"path": rel, "is_dir": e.is_dir()}
            if e.is_dir():
                lines.append(f'  {nid}["📁 {_mm_label(e.name)}"]')
                edges.append(f"  {parent_id} --> {nid}")
                walk(rel_parts + (e.name,), nid, level + 1)
            else:
                lines.append(f'  {nid}["📄 {_mm_label(e.name)}"]')
                edges.append(f"  {parent_id} --> {nid}")

    walk(subrel, root_id, 0)
    return "\n".join(lines + edges) + "\n", node_map


def _mirror_frontmatter(name: str, subpath: str = "") -> str:
    """The ``---`` frontmatter block for a mirror. Box root vs a subfolder
    differ only in ``title`` and ``source``."""
    sub = (subpath or "").strip().strip("/")
    if sub:
        title = f"folder: {sub} — cachebox: {name}"
        source = f"cachebox:{name}/{sub}"
    else:
        title = f"cachebox: {name}"
        source = f"cachebox:{name}"
    fm = [
        "---",
        "merirmaid: 1",
        f"title: {title}",
        "modality: mirror",
        "node-char-limit: 48",
        f"source: {source}",
        f"generated: {_now_iso()}",
        "---",
    ]
    return "\n".join(fm) + "\n"


def _mirror_text(name: str, meta: dict[str, Any], box: Path) -> str:
    body, _map = _mirror_body(name, meta, box)
    return _mirror_frontmatter(name) + body


def build_mirror(name: str, subpath: str = "") -> tuple[str, dict[str, dict[str, Any]]]:
    """Return ``(merirmaid_text, node_map)`` for a cachebox (``subpath=""``)
    or a subfolder within it. Pure generation — **never writes**; the
    on-demand sub-folder mirrors that back the cacheawl squircles are not
    persisted (no anonymous ``.merirmaid`` files sprinkled through folders).
    Raises ``CacheawlError`` for a missing box or an invalid subpath."""
    box = _require_box(name)
    meta = load_meta(name)
    body, node_map = _mirror_body(name, meta, box, subpath)
    return _mirror_frontmatter(name, subpath) + body, node_map


def regenerate_mirror(name: str) -> Path:
    """(Re)write ``_cachebox.merirmaid`` from the box's current contents +
    metadata. Called after every backend mutation. Also refreshes the
    fingerprint stored in metadata so the reconcile check has a baseline."""
    box = box_dir(name)
    box.mkdir(parents=True, exist_ok=True)
    meta = load_meta(name)
    text = _mirror_text(name, meta, box)
    (box / MIRROR_NAME).write_text(text, encoding="utf-8")
    # Refresh fingerprint post-write (the mirror itself is excluded).
    meta["fingerprint"] = _fingerprint(box)
    save_meta(name, meta)
    return box / MIRROR_NAME


def is_mirror_file(target: Path) -> bool:
    """True iff ``target`` is a cachebox mirror living under the store root —
    either by name (``_cachebox.merirmaid``) or by ``modality: mirror``
    frontmatter. Used by the write guards in tools.py / server.py."""
    try:
        real = target.resolve(strict=False)
        store = root().resolve(strict=False)
    except OSError:
        return False
    try:
        real.relative_to(store)
    except ValueError:
        return False
    if real.name == MIRROR_NAME:
        return True
    if real.suffix != ".merirmaid" or not real.is_file():
        return False
    try:
        head = real.read_text(encoding="utf-8", errors="ignore")[:600]
    except OSError:
        return False
    lines = head.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    # Scan the frontmatter block only (up to the closing fence).
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if re.match(r"\s*modality:\s*mirror\b", line):
            return True
    return False


def mirror_write_denial(target: Path) -> str | None:
    """Denial message if ``target`` is a cachebox mirror, else None. The
    guard both the agent's ``write_file`` and ``POST /api/file`` apply."""
    if is_mirror_file(target):
        return (
            "error: this is an auto-generated cachebox mirror "
            "(modality: mirror) under ~/enough/cacheawl/. it is regenerated "
            "from the cachebox's contents on every backend change and must "
            "not be edited directly — your edits would be overwritten and "
            "drift from the files it mirrors. to change what the diagram "
            "shows, change the cachebox contents (add/move/remove files via "
            "the cacheawl transfer/ingest ops)."
        )
    return None


# ---------------------------------------------------------------------------
# Cachebox CRUD
# ---------------------------------------------------------------------------

def cachebox_summary(name: str) -> dict[str, Any]:
    """Metadata + live stats for one cachebox (the listing row shape)."""
    box = _require_box(name)
    meta = load_meta(name)
    stats = _stats(box)
    return {
        "name": name,
        "origin": meta.get("origin"),
        "status": meta.get("status", "complete"),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "item_count": stats["item_count"],
        "dir_count": stats["dir_count"],
        "total_size": stats["total_size"],
        "total_size_human": _sizeof_human(stats["total_size"]),
        "ingest": meta.get("ingest"),
    }


def list_cacheboxes() -> list[dict[str, Any]]:
    """Every cachebox (root-level folder in the store), summarized, sorted
    by name."""
    r = root()
    out: list[dict[str, Any]] = []
    for entry in sorted(r.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        try:
            out.append(cachebox_summary(entry.name))
        except CacheawlError:
            continue
    return out


def cachebox_tree(name: str) -> dict[str, Any]:
    """Full nested tree of a cachebox for the icon grid, plus its summary."""
    _require_box(name)
    summary = cachebox_summary(name)
    summary["tree"] = _scan_tree(box_dir(name))
    return summary


def create_cachebox(name: str, *, origin: dict[str, Any] | None = None,
                    status: str = "complete") -> dict[str, Any]:
    """Create an empty cachebox. Errors if one already exists."""
    name = _validate_name(name)
    box = box_dir(name)
    if box.exists():
        raise CacheawlError(f"a cachebox named {name!r} already exists.")
    box.mkdir(parents=True, exist_ok=False)
    meta = _default_meta(name)
    if origin:
        meta["origin"] = origin
    meta["status"] = status
    save_meta(name, meta)
    regenerate_mirror(name)
    return cachebox_summary(name)


def rename_cachebox(name: str, new_name: str) -> dict[str, Any]:
    src = _require_box(name)
    new_name = _validate_name(new_name)
    dst = box_dir(new_name)
    if dst.exists():
        raise CacheawlError(f"a cachebox named {new_name!r} already exists.")
    src.rename(dst)
    meta = load_meta(new_name)
    meta["name"] = new_name
    save_meta(new_name, meta)
    regenerate_mirror(new_name)
    return cachebox_summary(new_name)


def delete_cachebox(name: str, *, confirm: bool) -> dict[str, Any]:
    """Delete a cachebox and everything in it. Deliberate: requires an
    explicit confirm flag (the no-deletes-without-confirmation discipline)."""
    box = _require_box(name)
    if not confirm:
        raise CacheawlError(
            f"deleting the {name!r} cachebox removes it and all its contents "
            f"permanently. this is not reversible from here. re-issue the "
            f"delete with confirmation once the user has agreed in their own "
            f"words."
        )
    shutil.rmtree(box)
    return {"deleted": name}


# ---------------------------------------------------------------------------
# Transfer ops (copy/move between the project dir and cacheboxes)
# ---------------------------------------------------------------------------

def _resolve_endpoint(project_dir: Path, kind: str, box: str | None,
                      rel: str) -> tuple[Path, Path]:
    """Resolve one side of a transfer to (base_root, absolute_target),
    verifying containment. ``kind`` is 'project' or 'cachebox'. Raises
    CacheawlError on traversal escape or a bad box.

    Containment is checked against the resolved base — the /var vs
    /private/var discipline — so a symlinked temp root on macOS still
    passes."""
    rel = (rel or "").strip().lstrip("/")
    if kind == "project":
        base = project_dir
    elif kind == "cachebox":
        if not box:
            raise CacheawlError("a cachebox endpoint needs a <box> name.")
        base = _require_box(box)
    else:
        raise CacheawlError(
            f"unknown transfer endpoint kind {kind!r} — use 'project' or "
            f"'cachebox'."
        )
    if ".." in Path(rel).parts:
        raise CacheawlError(f"path {rel!r} contains a '..' traversal component.")
    base_real = base.resolve(strict=False)
    target = (base_real / rel).resolve(strict=False)
    try:
        target.relative_to(base_real)
    except ValueError:
        raise CacheawlError(
            f"path {rel!r} escapes its {kind} root — refused."
        ) from None
    return base_real, target


def _guard_transfer_file(base: Path, target: Path, *, is_dst: bool) -> None:
    """Refuse to move/overwrite the backend-owned sidecars via transfer."""
    if target.name in (META_NAME, MIRROR_NAME):
        raise CacheawlError(
            f"{target.name} is backend-owned — it can't be a transfer "
            f"{'destination' if is_dst else 'source'}. transfer the cachebox's "
            f"real content files instead."
        )


def _affected_box(project_dir: Path, kind: str, box: str | None) -> str | None:
    return box if kind == "cachebox" else None


def transfer(project_dir: Path, *, op: str,
             src_kind: str, src_box: str | None, src_path: str,
             dst_kind: str, dst_box: str | None, dst_path: str,
             overwrite: bool = False) -> dict[str, Any]:
    """Copy or move a file/folder between the project dir and a cachebox
    (either direction) or within/between cacheboxes.

    ``dst_path`` names the destination path (including the final name). If
    it names an existing directory, the source is placed inside it under
    its own name. Refuses to clobber unless ``overwrite`` is set. Mirrors
    are regenerated for every cachebox the op touches.
    """
    if op not in ("copy", "move"):
        raise CacheawlError(f"transfer op must be 'copy' or 'move', got {op!r}.")

    _sbase, src = _resolve_endpoint(project_dir, src_kind, src_box, src_path)
    if not src.exists():
        raise CacheawlError(f"transfer source does not exist: {src_path!r}.")
    _guard_transfer_file(_sbase, src, is_dst=False)

    dbase, dst = _resolve_endpoint(project_dir, dst_kind, dst_box, dst_path)
    # If dst is an existing dir, drop the source into it under its own name.
    if dst.exists() and dst.is_dir():
        dst = (dst / src.name).resolve(strict=False)
        try:
            dst.relative_to(dbase)
        except ValueError:
            raise CacheawlError("resolved destination escaped its root.") from None
    _guard_transfer_file(dbase, dst, is_dst=True)

    if src.resolve() == dst.resolve():
        raise CacheawlError("source and destination are the same path.")
    if dst.exists() and not overwrite:
        raise CacheawlError(
            f"destination already exists: {dst.name}. pass overwrite to "
            f"replace it, or choose a different name."
        )
    if dst.exists() and overwrite:
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    dst.parent.mkdir(parents=True, exist_ok=True)
    if op == "copy":
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=False)
        else:
            shutil.copy2(src, dst)
    else:  # move
        shutil.move(str(src), str(dst))

    # Regenerate mirrors for any cachebox involved.
    touched = {b for b in (_affected_box(project_dir, src_kind, src_box),
                           _affected_box(project_dir, dst_kind, dst_box)) if b}
    for b in touched:
        if _is_cachebox(b):
            regenerate_mirror(b)

    return {
        "op": op,
        "src": {"kind": src_kind, "box": src_box, "path": src_path},
        "dst": {"kind": dst_kind, "box": dst_box,
                "path": str(dst.relative_to(dbase))},
        "boxes_updated": sorted(touched),
    }


# ---------------------------------------------------------------------------
# Reconcile — the freshness check the listing endpoint triggers
# ---------------------------------------------------------------------------

def reconcile(name: str) -> bool:
    """Cheaply detect manual file drops the backend didn't see (fingerprint
    drift) and regenerate the mirror if stale. Returns True iff the mirror
    was regenerated."""
    box = box_dir(name)
    if not box.is_dir():
        return False
    meta = load_meta(name)
    # Don't fight an in-flight ingest — it owns the mirror while running.
    if meta.get("status") == "ingesting":
        return False
    current = _fingerprint(box)
    if current != meta.get("fingerprint") or not (box / MIRROR_NAME).is_file():
        regenerate_mirror(name)
        return True
    return False


def reconcile_all() -> list[str]:
    """Reconcile every cachebox; return the names that were regenerated."""
    changed = []
    for summary in list_cacheboxes():
        try:
            if reconcile(summary["name"]):
                changed.append(summary["name"])
        except CacheawlError:
            continue
    return changed


# ---------------------------------------------------------------------------
# Ingest engine
# ---------------------------------------------------------------------------

def _normalize_depth(depth: Any, all_flag: bool, *, source_type: str) -> int | str:
    """Return an int 1..3 or the string 'all'. wikisink rejects 'all'."""
    if all_flag:
        if source_type == "wikisink":
            raise CacheawlError(
                "the 'all' depth is invalid for a wikisink ingest — crosslink "
                "expansion is unbounded and would pull in most of the "
                "encyclopedia. pick a depth of 1, 2, or 3."
            )
        return "all"
    try:
        d = int(depth)
    except (TypeError, ValueError):
        raise CacheawlError(
            f"depth must be an integer 1-3 (or set the 'all' flag), got "
            f"{depth!r}."
        ) from None
    if d < 1 or d > 3:
        raise CacheawlError(f"depth must be 1, 2, or 3 (got {d}); or use 'all'.")
    return d


def _set_progress(name: str, **fields: Any) -> None:
    meta = load_meta(name)
    prog = dict(meta.get("ingest") or {})
    prog.update(fields)
    meta["ingest"] = prog
    save_meta(name, meta)


def ingest_status(name: str) -> dict[str, Any]:
    """Pollable status for an ingest (or a plain box). Shape the UI polls."""
    meta = load_meta(name)
    return {
        "name": name,
        "status": meta.get("status", "complete"),
        "origin": meta.get("origin"),
        "ingest": meta.get("ingest"),
        "updated_at": meta.get("updated_at"),
    }


def register_ingest(*, box: str, source_type: str, value: str,
                    depth: Any = 1, all_flag: bool = False) -> dict[str, Any]:
    """Register a cachebox with status 'ingesting' BEFORE the (possibly
    long-running) ingest starts, so ``ingest_status`` is pollable
    immediately and there is never a window where the box doesn't exist.
    Validates input; raises CacheawlError on a bad request or a box that's
    already populated. Returns the origin dict."""
    name = _validate_name(box)
    source_type = (source_type or "").strip().lower()
    if source_type not in ("path", "url", "wikisink"):
        raise CacheawlError(
            f"unknown ingest source type {source_type!r} — use 'path', 'url', "
            f"or 'wikisink'.")
    value = (value or "").strip()
    if not value:
        raise CacheawlError("an ingest needs a non-empty value (the source).")
    norm_depth = _normalize_depth(depth, all_flag, source_type=source_type)
    d = box_dir(name)
    if d.is_dir():
        meta = load_meta(name)
        if meta.get("status") == "complete" and _stats(d)["item_count"] > 0:
            raise CacheawlError(
                f"cachebox {name!r} already exists and is populated — ingest "
                f"into a fresh box name, or delete it first if you mean to "
                f"replace it.")
    else:
        d.mkdir(parents=True, exist_ok=False)
        meta = _default_meta(name)
    origin = {"type": source_type, "value": value, "depth": norm_depth}
    meta["origin"] = origin
    meta["status"] = "ingesting"
    meta["ingest"] = {"phase": "queued", "files_written": 0,
                      "started_at": _now_iso(), "error": None}
    save_meta(name, meta)
    regenerate_mirror(name)
    return origin


def run_ingest(project_dir: Path, *, box: str, source_type: str, value: str,
               depth: Any = 1, all_flag: bool = False) -> dict[str, Any]:
    """Run an ingest into ``box``. Registers the cachebox metadata FIRST
    with status 'ingesting' (no half-registered boxes), then populates it,
    then marks 'complete'. Any failure marks the box 'failed' with the
    error recorded — a resumable/cleanly-failed state, never a phantom
    complete box.

    Three source types:
      - ``path``    — copy text files from a local path to ``depth`` folder
                      levels ('all' = unlimited). Skips binaries; never
                      follows symlinks out of the source root.
      - ``url``     — crawl same-origin pages to ``depth`` link layers
                      ('all' = subdirectory-scoped, capped), converting each
                      to markdown via the fetch_url plumbing; robots.txt
                      disallow is respected.
      - ``wikisink`` — fuzzy-match an article, save it as a wikisink folder,
                      then expand outlinks ``depth`` crosslink layers.
    """
    name = _validate_name(box)
    source_type = (source_type or "").strip().lower()
    if source_type not in ("path", "url", "wikisink"):
        raise CacheawlError(
            f"unknown ingest source type {source_type!r} — use 'path', 'url', "
            f"or 'wikisink'."
        )
    value = (value or "").strip()
    if not value:
        raise CacheawlError("an ingest needs a non-empty value (the source).")
    norm_depth = _normalize_depth(depth, all_flag, source_type=source_type)

    d = box_dir(name)
    existing = d.is_dir()
    if existing:
        meta = load_meta(name)
        if meta.get("status") == "complete" and _stats(d)["item_count"] > 0:
            raise CacheawlError(
                f"cachebox {name!r} already exists and is populated — ingest "
                f"into a fresh box name, or delete it first if you mean to "
                f"replace it."
            )
    else:
        d.mkdir(parents=True, exist_ok=False)
        meta = _default_meta(name)

    meta["origin"] = {"type": source_type, "value": value, "depth": norm_depth}
    meta["status"] = "ingesting"
    meta["ingest"] = {"phase": "starting", "files_written": 0,
                      "started_at": _now_iso(), "error": None}
    save_meta(name, meta)
    regenerate_mirror(name)

    try:
        if source_type == "path":
            written = _ingest_path(project_dir, name, value, norm_depth)
        elif source_type == "url":
            written = _ingest_url(project_dir, name, value, norm_depth)
        else:
            written = _ingest_wikisink(project_dir, name, value, norm_depth)
    except CacheawlError:
        _mark_failed(name)
        raise
    except Exception as e:  # noqa: BLE001 — record + re-raise as CacheawlError
        _mark_failed(name, str(e))
        raise CacheawlError(f"ingest failed: {e}") from e

    meta = load_meta(name)
    meta["status"] = "complete"
    prog = dict(meta.get("ingest") or {})
    prog.update({"phase": "complete", "files_written": written,
                 "finished_at": _now_iso()})
    meta["ingest"] = prog
    save_meta(name, meta)
    regenerate_mirror(name)
    summary = cachebox_summary(name)
    summary["files_written"] = written
    return summary


def _mark_failed(name: str, error: str = "") -> None:
    try:
        meta = load_meta(name)
        meta["status"] = "failed"
        prog = dict(meta.get("ingest") or {})
        prog.update({"phase": "failed", "error": error or prog.get("error"),
                     "finished_at": _now_iso()})
        meta["ingest"] = prog
        save_meta(name, meta)
        regenerate_mirror(name)
    except Exception:  # noqa: BLE001 — best effort
        log.exception("could not mark cachebox %s failed", name)


def _looks_binary(p: Path) -> bool:
    if p.suffix.lower() in _BINARY_EXTS:
        return True
    try:
        with p.open("rb") as f:
            sample = f.read(8192)
    except OSError:
        return True
    return b"\x00" in sample


def _ingest_path(project_dir: Path, name: str, value: str,
                 depth: int | str) -> int:
    """Copy text files from a local path into the cachebox, mirroring the
    source structure to ``depth`` folder levels. Never follows symlinks
    out of the source root."""
    src_root = Path(value).expanduser()
    try:
        src_root = src_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise CacheawlError(f"source path does not exist: {value!r}.") from None
    if not src_root.is_dir():
        # A single file is a legal source too.
        if src_root.is_file():
            if _looks_binary(src_root):
                raise CacheawlError(
                    f"{value!r} looks like a binary file — nothing text to "
                    f"ingest.")
            dest = box_dir(name) / src_root.name
            shutil.copy2(src_root, dest)
            _set_progress(name, phase="copying", files_written=1)
            return 1
        raise CacheawlError(f"source path is not a directory or file: {value!r}.")

    box = box_dir(name)
    written = 0
    unlimited = depth == "all"
    # ``depth`` counts directory levels to include: depth 1 = files directly
    # in the source root (level 0); depth 2 = one subdir level (0, 1); etc.
    max_levels = None if unlimited else int(depth)
    # os.walk(followlinks=False) never recurses into symlinked directories,
    # so a symlinked subdir can't lead the walk out of the source root.
    for cur, dirnames, filenames in os.walk(src_root, followlinks=False):
        cur_path = Path(cur)
        try:
            rel_dir = cur_path.relative_to(src_root)
        except ValueError:
            continue
        level = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        # Files at this level are copied only when the level is within depth.
        copy_here = max_levels is None or level < max_levels
        if max_levels is not None and level >= max_levels:
            dirnames[:] = []  # nothing deeper is in scope
        if not copy_here:
            continue
        for fn in sorted(filenames):
            sf = cur_path / fn
            if sf.is_symlink():
                # Skip a file symlink whose target escapes the source root.
                try:
                    if src_root not in sf.resolve().parents:
                        continue
                except OSError:
                    continue
            if _looks_binary(sf):
                continue
            rel = sf.relative_to(src_root)
            dest = box / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(sf, dest)
                written += 1
            except OSError as e:
                log.warning("cacheawl path ingest skip %s: %s", sf, e)
            if written % 25 == 0:
                _set_progress(name, phase="copying", files_written=written)
            if written >= INGEST_PATH_FILE_CAP:
                _set_progress(name, phase="capped", files_written=written,
                              note=f"hit {INGEST_PATH_FILE_CAP}-file cap")
                return written
    _set_progress(name, phase="copying", files_written=written)
    return written


class _Robots:
    """Thin robots.txt gate for one origin. Fetched through the same broker
    plumbing as page fetches; a missing/unfetchable robots.txt allows all
    (standard behavior)."""

    def __init__(self, origin: str, fetch: Callable[[str], "Any"]):
        self.parser = urllib.robotparser.RobotFileParser()
        self._ok = False
        try:
            res = fetch(origin.rstrip("/") + "/robots.txt")
            if res is not None:
                resp, _used_tor = res
                if resp.status < 400 and resp.text:
                    self.parser.parse(resp.text.splitlines())
                    self._ok = True
        except Exception:  # noqa: BLE001 — absent robots = allow all
            self._ok = False

    def allowed(self, url: str, ua: str = "enough-broker") -> bool:
        if not self._ok:
            return True
        try:
            return self.parser.can_fetch(ua, url)
        except Exception:  # noqa: BLE001
            return True


def _ingest_url(project_dir: Path, name: str, value: str,
                depth: int | str) -> int:
    """Same-origin crawl → markdown files mirroring URL paths. Reuses the
    fetch_url plumbing (allowlist/Tor gating + pandoc) via tools.fetch_gated
    — no parallel HTTP stack."""
    from . import tools as _tools  # late import: avoid import cycle

    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise CacheawlError(f"url ingest needs an http(s) URL, got {value!r}.")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    start_dir = posix_dirname(parsed.path)

    def fetch(u: str):
        try:
            return _tools.fetch_gated(project_dir, u)
        except _tools.FetchDenied as e:
            # Toggle off / off-allowlist with no Tor is fatal for a crawl.
            raise CacheawlError(str(e)) from None
        except _tools.FetchError:
            return None

    robots = _Robots(origin, fetch)
    box = box_dir(name)
    unlimited = depth == "all"
    max_layers = None if unlimited else int(depth)

    seen: set[str] = set()
    written = 0
    # BFS over (url, layer). layer 1 = start page.
    from collections import deque
    queue: deque[tuple[str, int]] = deque([(_canonical_url(value), 1)])
    while queue:
        url, layer = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        if len(seen) > INGEST_URL_PAGE_CAP:
            _set_progress(name, phase="capped", files_written=written,
                          note=f"hit {INGEST_URL_PAGE_CAP}-page cap")
            break
        if not robots.allowed(url):
            continue
        result = fetch(url)
        if result is None:
            continue
        resp, _used_tor = result
        if resp.status >= 400 or "html" not in (resp.content_type or ""):
            # Non-HTML or error: skip crawling, but keep plain text if useful.
            if resp.status < 400 and resp.text and "text/plain" in (resp.content_type or ""):
                written += _write_url_doc(box, url, resp.text, ".txt")
            continue
        md, _ok = _tools._markdownify_via_pandoc(resp.text)
        written += _write_url_doc(box, url, md, ".md")
        _set_progress(name, phase="crawling", files_written=written,
                      pages_seen=len(seen))
        # Enqueue same-origin links for the next layer.
        if max_layers is not None and layer >= max_layers:
            continue
        for link in _extract_links(resp.text, url):
            lp = urllib.parse.urlparse(link)
            if f"{lp.scheme}://{lp.netloc}" != origin:
                continue
            if unlimited and not lp.path.startswith(start_dir):
                continue  # 'all' stays within the starting subdirectory path
            cu = _canonical_url(link)
            if cu not in seen:
                queue.append((cu, layer + 1))
    _set_progress(name, phase="crawling", files_written=written,
                  pages_seen=len(seen))
    return written


def posix_dirname(path: str) -> str:
    import posixpath
    d = posixpath.dirname(path or "/")
    return (d or "/") if d.endswith("/") else d + "/"


def _canonical_url(url: str) -> str:
    """Drop the fragment; keep query. Trailing-slash normalized off."""
    p = urllib.parse.urlparse(url)
    path = p.path or "/"
    return urllib.parse.urlunparse((p.scheme, p.netloc, path, "", p.query, ""))


def _extract_links(html: str, base_url: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r'href\s*=\s*["\']([^"\'#]+)["\']', html, re.IGNORECASE):
        href = m.group(1).strip()
        if href.lower().startswith(("mailto:", "javascript:", "data:", "tel:")):
            continue
        out.append(urllib.parse.urljoin(base_url, href))
    return out


def _write_url_doc(box: Path, url: str, text: str, ext: str) -> int:
    """Write one crawled page as a file mirroring its URL path."""
    p = urllib.parse.urlparse(url)
    rel_path = p.path.strip("/")
    if not rel_path:
        rel_path = "index"
    # Sanitize each path segment; keep the directory structure.
    segs = [_slugify(urllib.parse.unquote(s), max_len=60) for s in rel_path.split("/") if s]
    if not segs:
        segs = ["index"]
    # A path ending in a dir (…/foo/) becomes …/foo/index.
    if p.path.endswith("/"):
        segs.append("index")
    if p.query:
        segs[-1] += "-" + _slugify(p.query, max_len=20)
    rel = Path(*segs).with_suffix(ext)
    dest = box / rel
    try:
        dest.relative_to(box.resolve())
    except ValueError:
        dest = box / (segs[-1] + ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = f"<!-- source: {url} -->\n\n"
    dest.write_text(header + (text or ""), encoding="utf-8")
    return 1


def _ingest_wikisink(project_dir: Path, name: str, value: str,
                     depth: int) -> int:
    """Fuzzy-match an article via wikisink search, save it as a folder in
    the cachebox, then expand outlinks ``depth`` crosslink layers."""
    from .wikisink import config as wconfig
    from .wikisink import zim as wzim
    from .wikisink import overlay as woverlay
    from .wikisink import save as wsave

    if not wconfig.installed():
        reason = wconfig.unavailable_reason() or (
            "no local wikipedia archive is installed.")
        raise CacheawlError(
            f"wikisink ingest needs an installed, reachable archive — {reason}")

    # Fuzzy match: prefer suggestion (title-ish), fall back to full-text.
    match_path = None
    try:
        sugg = wzim.suggest(value, limit=5)
        if sugg:
            match_path = sugg[0]["path"]
    except wzim.WikisinkUnavailable:
        pass
    if match_path is None:
        try:
            res = wzim.search(value, 0, 5)
            if res["results"]:
                match_path = res["results"][0]["path"]
        except wzim.WikisinkUnavailable as e:
            raise CacheawlError(f"wikisink search failed: {e}") from None
    if match_path is None:
        raise CacheawlError(
            f"no wikipedia article matched {value!r} in the local archive.")

    box = box_dir(name)
    depth = int(depth)
    written = 0
    seen: set[str] = set()
    # BFS over (path, layer). layer 1 = the matched article.
    from collections import deque
    queue: deque[tuple[str, int]] = deque([(match_path, 1)])
    while queue:
        path, layer = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        if len(seen) > INGEST_WIKI_ARTICLE_CAP:
            _set_progress(name, phase="capped", files_written=written,
                          note=f"hit {INGEST_WIKI_ARTICLE_CAP}-article cap")
            break
        try:
            art = woverlay.resolve_article(path=path)
        except (KeyError, wzim.WikisinkUnavailable):
            continue
        try:
            wsave.save_article_to_dir(box, art)
            written += 1
        except Exception as e:  # noqa: BLE001
            log.warning("cacheawl wikisink save skip %s: %s", path, e)
            continue
        _set_progress(name, phase="expanding", files_written=written,
                      articles_seen=len(seen))
        if layer >= depth:
            continue
        for link_path in _wiki_outlinks(art["html"], art["path"]):
            if link_path not in seen:
                queue.append((link_path, layer + 1))
    _set_progress(name, phase="expanding", files_written=written,
                  articles_seen=len(seen))
    return written


def _wiki_outlinks(html: str, article_path: str) -> list[str]:
    """Extract internal ZIM article paths this article links to (same-archive
    crosslinks). Best-effort regex over hrefs; external/anchor/special links
    dropped."""
    import posixpath
    base_dir = posixpath.dirname(article_path)
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = m.group(1).strip()
        low = href.lower()
        if low.startswith(("http://", "https://", "//", "mailto:",
                           "javascript:", "data:", "#")):
            continue
        target = href.split("#", 1)[0]
        if not target:
            continue
        target = urllib.parse.unquote(target)
        # Skip non-article namespaces (File:, Category:, Special:, etc.).
        tail = target.rsplit("/", 1)[-1]
        if ":" in tail and not tail.startswith("A/"):
            continue
        resolved = posixpath.normpath(posixpath.join(base_dir, target)).lstrip("./")
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


# ---------------------------------------------------------------------------
# infoworld → cacheawl migration
# ---------------------------------------------------------------------------

def migrate_infoworld(infoworld_root: Path | None = None) -> dict[str, Any]:
    """Dissolve ``~/enough/infoworld/{personal,public,wiki}`` into cacheawl,
    one cachebox per folder of the same name. Idempotent, move-only:
    ``os.rename`` within the same volume; a cross-volume fallback copies
    then verifies before removing the source. A missing infoworld root is a
    clean no-op.

    Runs once at server startup. Never copies-then-deletes across
    filesystems without verifying the copy landed.

    The source root defaults to ``~/enough/infoworld`` but honors
    ``ENOUGH_INFOWORLD_ROOT`` (a test/dev hook, paired with
    ``ENOUGH_CACHEAWL_ROOT``) so suites never move the real install's
    library."""
    if infoworld_root is None:
        env = os.environ.get("ENOUGH_INFOWORLD_ROOT")
        src_root = Path(env).expanduser() if env else (
            Path.home() / "enough" / "infoworld")
    else:
        src_root = infoworld_root
    result: dict[str, Any] = {"migrated": [], "skipped": [], "root": str(src_root)}
    if not src_root.is_dir():
        return result
    store = root()
    for sub in ("personal", "public", "wiki"):
        src = src_root / sub
        if not src.is_dir():
            continue
        dst = store / sub
        if dst.exists():
            # Already migrated (or a box of that name exists). Leave both
            # alone — idempotent. If the old infoworld folder is now empty,
            # tidy it up so the dissolve completes.
            result["skipped"].append(sub)
            _rmdir_if_empty(src)
            continue
        try:
            _move_dir(src, dst)
        except OSError as e:
            log.warning("infoworld migration of %s failed: %s", sub, e)
            result["skipped"].append(sub)
            continue
        # Stamp metadata + mirror so the moved folder is a first-class box.
        meta = _default_meta(sub)
        meta["origin"] = {"type": "infoworld-migration", "value": f"infoworld/{sub}",
                          "depth": None}
        meta["status"] = "complete"
        save_meta(sub, meta)
        try:
            regenerate_mirror(sub)
        except Exception:  # noqa: BLE001
            log.exception("mirror generation failed for migrated box %s", sub)
        result["migrated"].append(sub)
    # If infoworld is now empty of the three known folders, remove leftover
    # .gitkeep husks and the dir itself when nothing real remains.
    _tidy_infoworld_root(src_root)
    return result


def _move_dir(src: Path, dst: Path) -> None:
    """Move a directory. Prefer an atomic same-volume rename; fall back to a
    verified copy+remove across volumes (never delete the source before the
    copy is confirmed present)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(src, dst)
        return
    except OSError:
        pass  # cross-device or non-empty dst edge — verified copy path
    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=False)
    # Verify: every source file exists at the destination before removing.
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(src)
            if not (dst / rel).is_file():
                raise OSError(
                    f"copy verification failed: {rel} missing at destination; "
                    f"leaving source in place.")
    shutil.rmtree(src)


def _rmdir_if_empty(d: Path) -> None:
    try:
        # Drop a lone .gitkeep before checking emptiness.
        gk = d / ".gitkeep"
        if gk.is_file() and sum(1 for _ in d.iterdir()) == 1:
            gk.unlink()
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    except OSError:
        pass


def _tidy_infoworld_root(src_root: Path) -> None:
    if not src_root.is_dir():
        return
    try:
        remaining = list(src_root.iterdir())
    except OSError:
        return
    # Only tidy if what's left is throwaway (gitkeep/empty dirs).
    for entry in remaining:
        if entry.name == ".gitkeep":
            continue
        if entry.is_dir():
            _rmdir_if_empty(entry)
    _rmdir_if_empty(src_root)
