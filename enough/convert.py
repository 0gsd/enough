"""Document conversion: the format registry, the engines, the state machine.

A binary container the UI can't render — `report.pdf`, `memo.docx` — is
converted to an editable markdown **twin** beside it (`report.pdf.md`),
with extracted images in `report.pdf.assets/` and a hidden **manifest**
(`.report.pdf.convert.json`) recording what came from what. The original is
never rewritten except by an explicit **export**. Full design:
docs/convert-plan.md.

What lives here vs. in the worker
---------------------------------
This module is deliberately light: the registry, path naming, the manifest,
the divergence state machine, engine probing, and the thin subprocess driver.
It is imported by `server.py` on every tree build, so it may not import
pandoc/docling/typst — those live in `convert_worker.py`, which runs in a
`sys.executable -m enough.convert_worker` subprocess (plan §1 decision 6: a
heavy import must not live in the server process, a crash must not take the
server down, and cancellation is a `kill`).

Divergence is detected, never watched. enough has no file polling and this
design doesn't add any: the (size, mtime_ns) of both sides is compared against
the manifest at tree-build / open / save / export time, and sha256 is computed
only when those moved — so a Finder "touch" that leaves the bytes alone
refreshes the manifest instead of crying `stale`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("enough.convert")

MANIFEST_SCHEMA = 1
WORKER_MODULE = "enough.convert_worker"
CODE_ROOT = Path(__file__).resolve().parent.parent

# SSE event names. `convert` carries job + sync progress for the tree and the
# open document; `convert-install` streams uv's output during an extra install.
EVENT = "convert"
INSTALL_EVENT = "convert-install"


# ---------------------------------------------------------------------------
# The registry — ONE table. /api/convert/formats and {{convert-formats}}
# render it, prompt.py renders it, the help center expands it. Nothing
# hand-lists extensions anywhere else.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FormatSpec:
    """One convertible container type.

    `writer` is what an *overwrite* would use — `None` means overwrite is
    never offered for this type and the export modal shows "export as …"
    only. `notes` is one honest sentence about what the round trip costs;
    it is shown in the intro modal and in every generated formats table, so
    it is user-facing copy, not a code comment.
    """

    label: str
    reader: str                  # "pandoc" | "docling"
    writer: str | None           # "pandoc" | "typst" | None
    sync_ok: bool                # is "keep original in sync" offered
    notes: str = ""


FORMATS: dict[str, FormatSpec] = {
    ".docx": FormatSpec(label="Word document", reader="pandoc", writer="pandoc", sync_ok=True,
                        notes="tracked changes are accepted on import"),
    ".odt":  FormatSpec(label="OpenDocument text", reader="pandoc", writer="pandoc", sync_ok=True),
    ".rtf":  FormatSpec(label="Rich Text", reader="pandoc", writer="pandoc", sync_ok=True),
    ".epub": FormatSpec(label="EPUB ebook", reader="pandoc", writer="pandoc", sync_ok=True,
                        notes="one twin for the whole book; chapters become headings"),
    ".pdf":  FormatSpec(label="PDF", reader="docling", writer="typst", sync_ok=False,
                        notes="export re-typesets from markdown — it will not look like the original"),
    ".pptx": FormatSpec(label="PowerPoint deck", reader="docling", writer=None, sync_ok=False,
                        notes="slides become headed sections; export to docx/pdf only"),
    ".xlsx": FormatSpec(label="Excel workbook", reader="docling", writer=None, sync_ok=False,
                        notes="each sheet becomes a markdown table; export to docx/pdf only"),
}

# NOT in the registry: images (viewer, not conversion — plan §5.10) and the
# text formats pandoc could read but that already open as text.
IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"})

# What any twin (or any plain markdown file) can export to.
EXPORT_TARGETS = [".docx", ".odt", ".epub", ".html", ".pdf"]

# Markdown extensions that can be exported without being anyone's twin.
MARKDOWN_EXTS = frozenset({".md", ".markdown"})

# `/api/file/blob` serves these and nothing else. An explicit extension →
# type table rather than `mimetypes.guess_type` so no future OS mime
# registration can quietly widen the hole; `text/html` in particular must
# never be reachable, because a same-origin HTML document would run script
# with the app's origin.
BLOB_MEDIA_TYPES: dict[str, str] = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".svg": "image/svg+xml", ".avif": "image/avif", ".ico": "image/x-icon",
    ".tif": "image/tiff", ".tiff": "image/tiff",
    ".pdf": "application/pdf",
    # The paginated viewer reads its page manifest through this route
    # (paginate-plan §2.4). JSON, unlike text/html, has no script vector.
    ".json": "application/json",
    ".woff": "font/woff", ".woff2": "font/woff2",
    ".ttf": "font/ttf", ".otf": "font/otf",
}

# A crafted .svg opened as a top-level URL would otherwise be a script
# vector; inside <img> it never could be. Belt and braces: no subresources
# at all, inline styles only.
SVG_CSP = "default-src 'none'; style-src 'unsafe-inline'"

STATES = ("fresh", "edited", "stale", "conflict", "unconverted", "engine-missing")


class ConvertError(RuntimeError):
    """User- and agent-readable refusal or failure. `status` is the HTTP code
    the endpoint should answer with — 409 for a state conflict (a job already
    running, the original changed underneath us), 400 for a request we can't
    satisfy, 503 when the engine simply isn't installed. Carried as an
    attribute rather than matched out of the prose: the strings are user-facing
    copy that will get reworded."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Engine probing (once per process, cached; `reset_engines()` after an install)
# ---------------------------------------------------------------------------

_engine_cache: dict[str, Any] = {}


def reset_engines() -> None:
    """Drop the probe cache. Called after `/api/convert/install` finishes so
    the engines flip available without restarting the server."""
    _engine_cache.clear()
    from . import paginate
    paginate.reset_embed_cache()


def pandoc_path() -> str | None:
    """The one pandoc resolver for the whole codebase.

    `which("pandoc")` first — a Homebrew pandoc the user chose stays
    preferred, because it may well be newer than the wheel's. Then
    `pypandoc.get_pandoc_path()`, the copy `pypandoc-binary` ships, which is
    a base dependency and therefore always present. `None` only in a broken
    venv, which is why the "pandoc unavailable" fallback branches in
    tools.py/wikisink survive as defensive code and are now a real anomaly
    signal rather than a normal state.
    """
    if "pandoc" in _engine_cache:
        return _engine_cache["pandoc"]
    found = shutil.which("pandoc")
    where = "path"
    if not found:
        try:
            import pypandoc  # noqa: PLC0415 — probe-time import, cached
            found = pypandoc.get_pandoc_path()
            where = "bundled"
        except Exception:  # noqa: BLE001 — a missing/broken wheel is just "no pandoc"
            found = None
            where = None
    _engine_cache["pandoc"] = found
    _engine_cache["pandoc_where"] = where
    return found


def pandoc_version() -> str | None:
    """First line of `pandoc --version`, minus the leading "pandoc "."""
    if "pandoc_version" in _engine_cache:
        return _engine_cache["pandoc_version"]
    exe = pandoc_path()
    ver = None
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True,
                                 text=True, timeout=15.0)
            if out.returncode == 0:
                ver = out.stdout.splitlines()[0].replace("pandoc", "", 1).strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            ver = None
    _engine_cache["pandoc_version"] = ver
    return ver


def typst_path() -> str | None:
    """A `typst` executable pandoc can exec as its `--pdf-engine`.

    `which` first (a newer CLI the user installed wins), then the console
    script the `typst` wheel drops into the venv's `bin/` — same base
    dependency, same "broken venv only" failure mode as pandoc."""
    if "typst" in _engine_cache:
        return _engine_cache["typst"]
    found = shutil.which("typst")
    where = "path" if found else None
    if not found:
        # The wheel's console script lands next to the interpreter that will
        # run the worker, which is not necessarily on PATH (uv venvs usually
        # aren't activated).
        cand = Path(sys.executable).parent / "typst"
        if cand.is_file() and os.access(cand, os.X_OK):
            found, where = str(cand), "bundled"
    _engine_cache["typst"] = found
    _engine_cache["typst_where"] = where
    return found


def typst_available() -> bool:
    """PDF export works either through the CLI (`--pdf-engine=typst`) or
    through the wheel's Python API (`typst.compile()`); the worker picks the
    CLI when there is one. Either counts as available."""
    if typst_path():
        return True
    if "typst_module" not in _engine_cache:
        try:
            import importlib.util
            _engine_cache["typst_module"] = importlib.util.find_spec("typst") is not None
        except (ImportError, ValueError):
            _engine_cache["typst_module"] = False
    return bool(_engine_cache["typst_module"])


def typst_version() -> str | None:
    if "typst_version" in _engine_cache:
        return _engine_cache["typst_version"]
    ver = None
    exe = typst_path()
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True,
                                 text=True, timeout=15.0)
            if out.returncode == 0:
                ver = out.stdout.strip().replace("typst", "", 1).strip()
        except (OSError, subprocess.SubprocessError):
            ver = None
    if ver is None:
        # No CLI: the wheel is the engine, so its distribution version is the
        # honest answer for the status pane.
        try:
            from importlib.metadata import version as _dist_version
            ver = _dist_version("typst")
        except Exception:  # noqa: BLE001 — absent wheel = no version
            ver = None
    _engine_cache["typst_version"] = ver
    return ver


def weights_dir() -> Path:
    """`ENOUGH_WEIGHTS_DIR/docling`, same dir family (and same scratch seam)
    as the GGUFs. Model weights are prefetched at the end of the extra's
    install — the first conversion never downloads silently."""
    env = os.environ.get("ENOUGH_WEIGHTS_DIR")
    base = Path(env).expanduser() if env else Path.home() / "enough" / "weights"
    return base / "docling"


# The docling wave's switch, thrown. Kept as a named constant rather than
# deleted: it is the one place to turn PDF/deck/workbook reading off again if
# the engine ever has to be pulled, and `engines()` reports it so the status
# pane can tell "no engine in this build" apart from "engine present, models
# missing".
DOCLING_ENGINE_WIRED = True


def docling_installed() -> bool:
    """Is the `pdf` extra present in this environment? Distinct from
    `docling_available()` so the installer UI can say "installed" honestly
    while the engine is still Phase 2."""
    if "docling" not in _engine_cache:
        try:
            import importlib.util
            _engine_cache["docling"] = importlib.util.find_spec("docling") is not None
        except (ImportError, ValueError):
            _engine_cache["docling"] = False
    return bool(_engine_cache["docling"])


def docling_version() -> str | None:
    """What goes in the manifest's `engine.version`. `docling-slim` is the
    distribution the `pdf` extra actually pins; plain `docling` is a thin
    metapackage over it, so try the one we ask for first and fall back for an
    environment that got there another way."""
    if "docling_version" in _engine_cache:
        return _engine_cache["docling_version"]
    ver = None
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _dist_version
    for dist in ("docling-slim", "docling"):
        try:
            ver = _dist_version(dist)
            break
        except PackageNotFoundError:
            continue
        except Exception:  # noqa: BLE001 — a broken dist-info is just "no version"
            break
    _engine_cache["docling_version"] = ver
    return ver


def docling_available() -> bool:
    """Installed *and* fed. The weights are prefetched by the extra's
    installer precisely so the first conversion never downloads silently, so
    an install whose artifacts dir is empty is not a working engine — it is a
    conversion that would stall on a 669 MB download the user never asked
    for. Reporting it unavailable routes the click into the intro modal,
    whose button runs the installer, which is where the download belongs."""
    return DOCLING_ENGINE_WIRED and docling_installed() and docling_models_present()


def docling_models_present() -> bool:
    """Are the layout/TableFormer weights already on disk? A populated
    artifacts dir, not a version check — docling is happy with whatever it
    finds there and we never want it fetching mid-conversion."""
    d = weights_dir()
    try:
        return d.is_dir() and any(d.iterdir())
    except OSError:
        return False


def engine_available(name: str | None) -> bool:
    if name == "pandoc":
        return pandoc_path() is not None
    if name == "typst":
        return typst_available()
    if name == "docling":
        return docling_available()
    if name == "unpack":
        return True          # pypdf is a base dependency
    return False


def reader_for(original: Path) -> str | None:
    """Which engine reads this file — the registry's, except for a PDF enough
    itself paginated.

    Such a file carries the markdown that produced it as an attachment
    (paginate-plan §2.6), so reading it back is an unzip, not a document
    understanding problem: no docling, no models, no OCR, and the text comes
    back byte-exact. Foreign PDFs are unaffected and still need the reader."""
    spec = spec_for(original)
    if spec is None:
        return None
    if spec.reader == "docling" and Path(original).suffix.lower() == ".pdf":
        from . import paginate
        if paginate.has_embedded_source(Path(original)):
            return "unpack"
    return spec.reader


def engines() -> dict[str, dict[str, Any]]:
    """What `GET /api/convert/status` and `GET /api/convert/formats` report.

    `where` is `"bundled"` for the wheel's copy and `"path"` for a `which()`
    hit — the plan said "brew", but a PATH hit could equally be nix, macports,
    or a hand-built binary, and claiming brew would be a guess.
    """
    pandoc = pandoc_path()
    typst = typst_path()
    return {
        "pandoc": {"available": pandoc is not None, "version": pandoc_version(),
                   "where": _engine_cache.get("pandoc_where"), "path": pandoc},
        "typst": {"available": typst_available(), "version": typst_version(),
                  "where": _engine_cache.get("typst_where"), "path": typst},
        "docling": {"available": docling_available(), "installed": docling_installed(),
                    "models": docling_models_present(), "wired": DOCLING_ENGINE_WIRED,
                    "artifacts_dir": str(weights_dir())},
    }


def formats_view() -> dict[str, Any]:
    """The registry as JSON — the single source the API, the help token, and
    the system prompt all render."""
    rows = []
    for ext, spec in FORMATS.items():
        rows.append({
            "ext": ext, "label": spec.label, "reader": spec.reader,
            "writer": spec.writer, "sync_ok": spec.sync_ok, "notes": spec.notes,
            "available": engine_available(spec.reader),
            "writer_available": engine_available(spec.writer) if spec.writer else False,
        })
    return {"formats": rows, "export_targets": list(EXPORT_TARGETS),
            "image_exts": sorted(IMAGE_EXTS), "engines": engines()}


# ---------------------------------------------------------------------------
# Naming: twin, assets, manifest
# ---------------------------------------------------------------------------

def spec_for(path: Path | str) -> FormatSpec | None:
    return FORMATS.get(Path(path).suffix.lower())


def is_convertible(path: Path | str) -> bool:
    return Path(path).suffix.lower() in FORMATS


def is_image(path: Path | str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def twin_path(original: Path) -> Path:
    """`report.pdf` → `report.pdf.md`. Pairing is by name, so it can never
    collide with a real `report.md`, and a twin whose original is deleted in
    Finder degrades into an ordinary markdown file in the tree."""
    return original.parent / f"{original.name}.md"


def assets_dir(original: Path) -> Path:
    return original.parent / f"{original.name}.assets"


def manifest_path(original: Path) -> Path:
    return original.parent / f".{original.name}.convert.json"


def original_for_twin(twin: Path) -> Path | None:
    """The convertible original a `<name>.<ext>.md` twin belongs to, or None
    when the file is just markdown."""
    if twin.suffix.lower() != ".md":
        return None
    cand = twin.parent / twin.name[: -len(twin.suffix)]
    return cand if is_convertible(cand) else None


def pair_for(path: Path) -> tuple[Path | None, Path]:
    """`(original, twin)` for a path that is a convertible original, a twin,
    or a plain markdown file (original None — exportable, never overwritable).

    Every convert endpoint accepts either end of the pair so the UI, the agent
    and the sync-on-save hook can all pass whichever handle they hold."""
    if is_convertible(path):
        return path, twin_path(path)
    if path.suffix.lower() in MARKDOWN_EXTS:
        return original_for_twin(path), path
    raise ConvertError(
        f"{path.name} is not a convertible document or a markdown file", status=400)


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_manifest(original: Path) -> dict[str, Any] | None:
    """The manifest beside `original`, or None when absent/unreadable/foreign.
    A schema we don't know reads as absent rather than raising: a newer enough
    that wrote it will read it again, and this one just re-converts."""
    p = manifest_path(original)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
        return None
    return data


def write_manifest(original: Path, data: dict[str, Any]) -> None:
    """tmp + rename, like every other sidecar enough owns — a half-written
    manifest would read as "never converted" and silently re-convert over the
    user's twin."""
    p = manifest_path(original)
    tmp = p.parent / f"{p.name}.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def delete_manifest(original: Path) -> None:
    try:
        manifest_path(original).unlink()
    except OSError:
        pass


def new_manifest(
    original: Path,
    *,
    engine: dict[str, Any],
    assets: str | None,
    sync: bool = False,
    last_export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-1 manifest from what is currently on disk. Both sides'
    (size, mtime_ns) are cached alongside the sha so the tree build can skip
    hashing when nothing moved."""
    twin = twin_path(original)
    ost = original.stat()
    tst = twin.stat()
    return {
        "schema": MANIFEST_SCHEMA,
        "original": original.name,
        "twin": twin.name,
        "assets": assets,
        "engine": engine,
        "converted_at": utc_now(),
        "source": {"sha256": sha256_file(original), "size": ost.st_size,
                   "mtime_ns": ost.st_mtime_ns},
        "twin_sha256": sha256_file(twin),
        "twin_size": tst.st_size,
        "twin_mtime_ns": tst.st_mtime_ns,
        "sync": bool(sync),
        "last_export": last_export,
    }


def _refresh_twin_record(man: dict[str, Any], twin: Path) -> None:
    """Point the manifest's twin fields at the twin as it stands right now —
    used after a conversion and after an export, both of which mean "the twin
    and the original agree from here"."""
    tst = twin.stat()
    man["twin_sha256"] = sha256_file(twin)
    man["twin_size"] = tst.st_size
    man["twin_mtime_ns"] = tst.st_mtime_ns


def _refresh_source_record(man: dict[str, Any], original: Path) -> None:
    ost = original.stat()
    man["source"] = {"sha256": sha256_file(original), "size": ost.st_size,
                     "mtime_ns": ost.st_mtime_ns}


# ---------------------------------------------------------------------------
# The state machine
# ---------------------------------------------------------------------------

def has_twin(original: Path) -> bool:
    """Is there a manifest-backed twin beside `original`?

    Both halves matter, and this is the function the tree's hiding rule asks.
    A `report.pdf.md` with no manifest is *not* a twin — it is somebody's
    ordinary markdown file that happens to be named that way, and hiding it
    would make it unreachable. (The plan states the hiding rule in terms of
    the twin's existence alone; requiring the manifest too is the same rule
    without that hole.)"""
    try:
        return (original.is_file() and is_convertible(original)
                and twin_path(original).is_file()
                and manifest_path(original).is_file())
    except OSError:
        return False


def state(original: Path) -> str:
    """One of `STATES`, for a convertible original. Pure apart from one
    self-heal: when a side's (size, mtime_ns) moved but its sha256 didn't —
    a Finder "touch", a cloud-sync re-stat, a `cp -p` — the manifest's cached
    stat is rewritten and the file counts as unchanged. Without that, every
    such touch would raise a false `stale` and prompt the user to resolve a
    conflict that doesn't exist."""
    spec = spec_for(original)
    if spec is None:
        raise ConvertError(f"{original.name} is not a convertible document", status=400)
    twin = twin_path(original)
    man = read_manifest(original)
    if man is None or not twin.is_file():
        if man is not None and not twin.is_file():
            # Manifest without a twin is garbage — the user deleted the twin
            # in Finder. Drop it lazily rather than resurrecting a ghost.
            delete_manifest(original)
        return ("unconverted" if engine_available(reader_for(original))
                else "engine-missing")

    dirty = False
    stale = False
    src = man.get("source") or {}
    try:
        ost = original.stat()
    except OSError:
        return "unconverted"
    if ost.st_size != src.get("size") or ost.st_mtime_ns != src.get("mtime_ns"):
        if sha256_file(original) != src.get("sha256"):
            stale = True
        else:
            src["size"], src["mtime_ns"] = ost.st_size, ost.st_mtime_ns
            man["source"] = src
            dirty = True

    edited = False
    try:
        tst = twin.stat()
    except OSError:
        return "unconverted"
    if tst.st_size != man.get("twin_size") or tst.st_mtime_ns != man.get("twin_mtime_ns"):
        if sha256_file(twin) != man.get("twin_sha256"):
            edited = True
        else:
            man["twin_size"], man["twin_mtime_ns"] = tst.st_size, tst.st_mtime_ns
            dirty = True

    if dirty:
        try:
            write_manifest(original, man)
        except OSError as e:      # read-only volume — the state is still right
            log.warning("could not refresh manifest for %s: %s", original, e)

    if stale and edited:
        return "conflict"
    if stale:
        return "stale"
    if edited:
        return "edited"
    return "fresh"


def status(original: Path, *, rel: str | None = None) -> dict[str, Any]:
    """The `GET /api/convert/status` payload for one original."""
    spec = spec_for(original)
    if spec is None:
        raise ConvertError(f"{original.name} is not a convertible document", status=400)
    st = state(original)
    man = read_manifest(original)
    twin = twin_path(original)
    reader = reader_for(original)
    return {
        "path": rel if rel is not None else original.name,
        "state": st,
        "twin": twin.name if twin.is_file() else None,
        "manifest": man,
        "spec": {"ext": original.suffix.lower(), "label": spec.label,
                 "reader": reader, "writer": spec.writer,
                 "sync_ok": spec.sync_ok, "notes": spec.notes,
                 "available": engine_available(reader),
                 "writer_available": engine_available(spec.writer) if spec.writer else False},
        "export_targets": export_targets_for(original),
        "sync": bool((man or {}).get("sync")),
    }


def export_targets_for(original: Path | None) -> list[str]:
    """The registry's universal target list, plus the original's own format
    when that format is writable. `.rtf` is the case that needs it: it is
    `sync_ok`, so sync-on-save must be able to write `.rtf` back, but `.rtf`
    isn't a target anybody would pick from a fresh export menu."""
    out = list(EXPORT_TARGETS)
    if original is not None:
        spec = spec_for(original)
        ext = original.suffix.lower()
        if spec and spec.writer and ext not in out:
            out.append(ext)
    return out


def datestamped_path(base: Path, target_ext: str, when: dt.datetime | None = None) -> Path:
    """`report.pdf` + `.docx` → `report-2026-08-19-1432.docx`, beside the
    original, local time. Collisions append `-2`, `-3`, … — a user exporting
    twice inside the same minute gets two files, not a silent clobber."""
    when = when or dt.datetime.now()
    stamp = when.strftime("%Y-%m-%d-%H%M")
    cand = base.parent / f"{base.stem}-{stamp}{target_ext}"
    n = 2
    while cand.exists():
        cand = base.parent / f"{base.stem}-{stamp}-{n}{target_ext}"
        n += 1
    return cand


# ---------------------------------------------------------------------------
# The worker driver
# ---------------------------------------------------------------------------

ProgressFn = Callable[[dict[str, Any]], None]


def worker_argv() -> list[str]:
    return [sys.executable, "-m", WORKER_MODULE]


def run_worker(
    job: dict[str, Any],
    *,
    timeout: float | None = None,
    on_progress: ProgressFn | None = None,
    on_start: Callable[[subprocess.Popen], None] | None = None,
) -> dict[str, Any]:
    """Run one job in `sys.executable -m enough.convert_worker` and return its
    result dict. Blocking — call through `asyncio.to_thread` from the server.

    The job goes in on stdin as JSON (not argv: a path with a quote in it has
    no business in anybody's process listing) and newline-delimited JSON comes
    back on stdout. stderr is folded into stdout deliberately: non-JSON lines
    are collected as diagnostic tail, and a separate pipe nobody drains is a
    deadlock waiting for a long pandoc warning.

    `on_start` receives the Popen so a job manager can `kill()` it — that is
    the whole of cancellation (plan §1 decision 6).
    """
    env = dict(os.environ)
    proc = subprocess.Popen(
        worker_argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, cwd=str(CODE_ROOT), env=env,
    )
    if on_start is not None:
        on_start(proc)
    timer: threading.Timer | None = None
    if timeout is not None:
        timer = threading.Timer(timeout, proc.kill)
        timer.daemon = True
        timer.start()
    result: dict[str, Any] | None = None
    error: str | None = None
    noise: list[str] = []
    try:
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps(job))
        proc.stdin.close()
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                noise.append(line)
                if len(noise) > 60:
                    del noise[:-60]
                continue
            kind = rec.get("event")
            if kind == "progress" and on_progress is not None:
                on_progress(rec)
            elif kind == "done":
                result = rec.get("result") or {}
            elif kind == "error":
                error = rec.get("error") or "conversion failed"
        proc.wait()
    finally:
        if timer is not None:
            timer.cancel()
        try:
            proc.stdout.close()  # type: ignore[union-attr]
        except OSError:
            pass
    if error:
        raise ConvertError(error, status=500)
    if result is None:
        tail = " / ".join(noise[-4:]) if noise else f"exit {proc.returncode}"
        if proc.returncode and proc.returncode < 0:
            raise ConvertError("conversion was cancelled", status=409)
        raise ConvertError(f"the converter exited without a result ({tail})", status=500)
    return result


# ---------------------------------------------------------------------------
# Conversion + export (synchronous; the server calls these off the event loop)
# ---------------------------------------------------------------------------

def convert_job(original: Path, *, force: bool = False) -> dict[str, Any]:
    """Validate and describe a conversion, without running it. Raises the
    refusal the endpoint should answer with."""
    spec = spec_for(original)
    if spec is None:
        raise ConvertError(f"{original.name} is not a convertible document", status=400)
    if not original.is_file():
        raise ConvertError(f"{original.name} does not exist", status=404)
    reader = reader_for(original)
    if not engine_available(reader):
        raise ConvertError(engine_missing_message(spec), status=503)
    twin = twin_path(original)
    if twin.is_file() and not force:
        raise ConvertError(
            f"{twin.name} already exists — pass force to re-convert over it", status=409)
    return {
        "op": "convert", "engine": reader,
        "original": str(original), "twin": str(twin),
        "assets": str(assets_dir(original)),
        "artifacts_dir": str(weights_dir()),
    }


def engine_missing_message(spec: FormatSpec) -> str:
    """What to tell the user (or the agent) when an engine isn't there. The
    docling branch names the extra by the button that installs it; the pandoc
    branch describes a broken venv, because pandoc is a base dependency."""
    if spec.reader == "docling":
        if docling_installed() and DOCLING_ENGINE_WIRED and not docling_models_present():
            # The packages are there but nothing has fetched the layout and
            # table weights. Same button, different sentence — telling the
            # user to "install the extra" they already have would read as a
            # bug rather than a step.
            return (f"the PDF reader is installed but its models aren't — run the "
                    f"install again from the UI window → extras and it will fetch "
                    f"them into {weights_dir()}")
        return (f"opening {spec.label}s needs the PDF extra — install it from the "
                f"UI window → extras (it brings the PDF reader), or ask the agent "
                f"to run it for you")
    return ("pandoc could not be found in this environment — it ships with enough, "
            "so this means the Python environment is incomplete; re-run "
            "update-enough (or `uv sync`) to repair it")


def run_convert(original: Path, *, force: bool = False, sync: bool | None = None,
                on_progress: ProgressFn | None = None,
                on_start: Callable[[subprocess.Popen], None] | None = None,
                timeout: float | None = None) -> dict[str, Any]:
    """Convert `original` into its twin and write the manifest. Blocking.

    A forced re-convert stashes the existing twin through the ordinary undo
    mechanism first, so "re-convert from the new original" is undoable with
    the same save/undo bar as any other write."""
    job = convert_job(original, force=force)
    twin = twin_path(original)
    prior = read_manifest(original)
    if twin.is_file():
        from . import tools as _tools     # late: tools imports convert back
        _tools.stash_for_undo(twin)
    result = run_worker(job, on_progress=on_progress, on_start=on_start, timeout=timeout)
    assets = assets_dir(original)
    if sync is None:
        # A re-convert keeps the user's "keep in sync" opt-in and their last
        # export record; only the twin and the hashes are rebuilt.
        sync = bool((prior or {}).get("sync"))
    man = new_manifest(
        original,
        engine=result.get("engine") or {"name": job["engine"], "version": None, "ocr": None},
        assets=assets.name if assets.is_dir() and any(assets.iterdir()) else None,
        sync=sync,
        last_export=(prior or {}).get("last_export"),
    )
    write_manifest(original, man)
    return {"twin": twin.name, "assets": man["assets"], "engine": man["engine"],
            "images": result.get("images", 0)}


def export(
    *,
    twin: Path,
    original: Path | None,
    target: str,
    mode: str,
    when: dt.datetime | None = None,
    allow_stale: bool = False,
) -> dict[str, Any]:
    """Write the twin's markdown out as `target`, either over the original or
    as a datestamped copy beside it. Blocking.

    Overwrite is the only path that ever touches an original, and it always
    stashes it first — the user gets the same one-deep `.undo` and save/undo
    bar every other write in enough gets."""
    target = target.lower()
    if not twin.is_file():
        raise ConvertError(f"{twin.name} does not exist", status=404)
    if target not in export_targets_for(original):
        allowed = ", ".join(export_targets_for(original))
        raise ConvertError(f"{target} is not an export target (try {allowed})", status=400)
    if mode not in ("overwrite", "copy"):
        raise ConvertError("mode must be 'overwrite' or 'copy'", status=400)

    spec = spec_for(original) if original is not None else None
    if mode == "overwrite":
        if original is None:
            raise ConvertError(
                "there is no original to overwrite — this markdown file isn't a twin; "
                "export a datestamped copy instead", status=400)
        if spec is None or spec.writer is None:
            label = spec.label if spec else original.suffix
            raise ConvertError(
                f"{label} files can't be written back — export to another format instead",
                status=400)
        if target != original.suffix.lower():
            raise ConvertError(
                f"overwrite writes {original.suffix}, not {target} — "
                f"use a datestamped copy for a different format", status=400)
        if not allow_stale:
            st = state(original)
            if st in ("stale", "conflict"):
                raise ConvertError(
                    "original changed outside enough since conversion", status=409)

    if target == ".pdf":
        if not typst_available():
            raise ConvertError(
                "typst could not be found in this environment — it ships with enough, "
                "so this means the Python environment is incomplete; re-run "
                "update-enough (or `uv sync`) to repair it", status=503)
    elif not pandoc_path():
        raise ConvertError(engine_missing_message(FORMATS[".docx"]), status=503)

    base = original if original is not None else twin
    out = original if mode == "overwrite" else datestamped_path(base, target, when)

    reference: str | None = None
    # Decision 4: styles, page size/margins, headers and footers come from the
    # original. It is the single biggest fidelity win in the round trip, and
    # pandoc only accepts it for the docx/odt writers.
    if original is not None and target == original.suffix.lower() and target in (".docx", ".odt"):
        reference = str(original)

    undone = False
    if mode == "overwrite":
        from . import tools as _tools
        undone = _tools.stash_for_undo(out)

    job = {"op": "export", "twin": str(twin), "target": target, "out": str(out),
           "resource_path": str(twin.parent), "reference_doc": reference}
    try:
        run_worker(job, timeout=300.0)
    except ConvertError:
        if mode == "overwrite" and undone:
            # Put the original back: a failed export must not leave a
            # half-written file where the user's document was.
            from . import tools as _tools
            stash = _tools._undo_path(out)
            try:
                if stash.is_file():
                    out.write_bytes(stash.read_bytes())
            except OSError:
                pass
        raise

    record = {"at": utc_now(), "mode": mode, "target": out.name}
    if original is not None:
        man = read_manifest(original)
        if man is not None:
            man["last_export"] = record
            if mode == "overwrite":
                _refresh_source_record(man, original)
                _refresh_twin_record(man, twin)
            try:
                write_manifest(original, man)
            except OSError as e:
                log.warning("could not record export in manifest for %s: %s", original, e)
    return {"written": out.name, "path": str(out), "undo": undone, "mode": mode,
            "target": target, "reference_doc": reference is not None}


def set_sync(original: Path, enabled: bool) -> dict[str, Any]:
    """Flip the manifest's "keep original in sync" opt-in. pandoc-family
    originals only — a PDF's export is a re-typeset, not a round trip, and
    silently re-typesetting the user's PDF on every keystroke-save would be
    exactly the silent overwrite Decision 3 forbids."""
    spec = spec_for(original)
    if spec is None:
        raise ConvertError(f"{original.name} is not a convertible document", status=400)
    if enabled and not spec.sync_ok:
        raise ConvertError(
            f"{spec.label} originals can't be kept in sync — {spec.notes or 'the round trip is lossy'}",
            status=400)
    man = read_manifest(original)
    if man is None:
        raise ConvertError(f"{original.name} hasn't been converted yet", status=409)
    man["sync"] = bool(enabled)
    write_manifest(original, man)
    return {"path": original.name, "sync": man["sync"]}


def accept_external_change(original: Path) -> dict[str, Any]:
    """"Keep my twin": record the original as it now stands so `stale` clears,
    without touching the twin. The twin stays `edited` if it was — export is
    still the way the user's text reaches the original."""
    man = read_manifest(original)
    if man is None:
        raise ConvertError(f"{original.name} hasn't been converted yet", status=409)
    _refresh_source_record(man, original)
    write_manifest(original, man)
    return {"path": original.name, "state": state(original)}


def sync_after_save(twin: Path) -> dict[str, Any] | None:
    """The one rule `POST /api/file` and the agent's `write_file` both grow:
    a twin whose manifest says `sync: true` exports itself over the original
    right after it is saved.

    Returns None when `twin` isn't a syncing twin. Never raises — saving must
    never lose the user's text, so a refusal comes back as
    `{"state": "conflict"|"failed"}` for the caller to surface *after* the
    save has already landed."""
    try:
        original = original_for_twin(twin)
    except Exception:  # noqa: BLE001
        return None
    if original is None or not original.is_file():
        return None
    man = read_manifest(original)
    if not man or not man.get("sync"):
        return None
    st = state(original)
    if st in ("stale", "conflict"):
        return {"state": "conflict", "original": original.name,
                "detail": "original changed outside enough since conversion"}
    try:
        res = export(twin=twin, original=original, target=original.suffix.lower(),
                     mode="overwrite")
    except ConvertError as e:
        return {"state": "failed", "original": original.name, "detail": str(e)}
    return {"state": "synced", "original": original.name, "written": res["written"]}


# ---------------------------------------------------------------------------
# extras.json — which optional dependency groups are installed
# ---------------------------------------------------------------------------

_DEFAULT_EXTRAS_STATE = Path.home() / "enough" / "config" / "extras.json"


def extras_state_path() -> Path:
    """`~/enough/config/extras.json`, or `ENOUGH_EXTRAS_STATE` when set — the
    same test/dev seam shape as `ENOUGH_UI_CONFIG` / `ENOUGH_CACHEAWL_ROOT`,
    so a QA server can never mark the real install as having the extra."""
    env = os.environ.get("ENOUGH_EXTRAS_STATE")
    return Path(env).expanduser() if env else _DEFAULT_EXTRAS_STATE


def read_extras() -> dict[str, Any]:
    try:
        data = json.loads(extras_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def installed_extras() -> list[str]:
    """Every extra `uv sync` must be told to keep.

    This is the whole point of the file: `uv sync` is exact by default and
    would happily *uninstall* the `pdf` extra on the next update. Every sync
    path — update-enough.command, the desktop shell's env sync, and our own
    installer — appends `--extra <name>` for each name in here."""
    return sorted(read_extras().keys())


def lock_sha256() -> str | None:
    lock = CODE_ROOT / "uv.lock"
    try:
        return sha256_file(lock)
    except OSError:
        return None


def record_extra(name: str) -> dict[str, Any]:
    data = read_extras()
    data[name] = {"installed_at": utc_now(), "lock_sha256": lock_sha256()}
    p = extras_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.parent / f"{p.name}.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return data[name]


def forget_extra(name: str) -> None:
    data = read_extras()
    if data.pop(name, None) is None:
        return
    p = extras_state_path()
    tmp = p.parent / f"{p.name}.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Job managers (conversions, and the extras installer)
# ---------------------------------------------------------------------------

EmitFn = Callable[[str, dict[str, Any]], None]


class ConvertJobs:
    """Background conversions, one per project-relative path.

    Modeled on `model_download.ModelDownloadManager` — a snapshot dict that is
    both the poll payload and the SSE payload, and a manager owned by
    `create_app()` — but conversions are per-path rather than one-at-a-time,
    because a user who clicks three documents in a row should get three twins,
    not two refusals. Cancellation kills the worker process; there is no
    cooperative flag, because most of a conversion is spent inside pandoc.
    """

    def __init__(self, emit: EmitFn | None = None):
        self._emit = emit
        self._snaps: dict[str, dict[str, Any]] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._by_path: dict[str, str] = {}
        self._tasks: set[Any] = set()
        self._seq = 0
        self._lock = threading.Lock()

    # -- introspection ----------------------------------------------------

    def running_for(self, rel: str) -> str | None:
        job_id = self._by_path.get(rel)
        if job_id and self._snaps.get(job_id, {}).get("state") == "running":
            return job_id
        return None

    def snapshot(self, job_id: str) -> dict[str, Any]:
        snap = self._snaps.get(job_id)
        if snap is None:
            raise ConvertError(f"no such job {job_id}", status=404)
        return dict(snap)

    def active(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self._snaps.values() if s["state"] == "running"]

    # -- control ----------------------------------------------------------

    def start(self, *, rel: str, original: Path, force: bool = False) -> dict[str, Any]:
        """Validate, claim the path, and run the conversion on a worker
        thread. Raises the refusal the endpoint should answer with — including
        409 when a job for this path is already running, claimed under the
        lock so a double-click can't start two."""
        job = convert_job(original, force=force)   # validates; raises ConvertError
        with self._lock:
            if self.running_for(rel):
                raise ConvertError(
                    f"a conversion of {original.name} is already running", status=409)
            self._seq += 1
            job_id = f"cv{self._seq}"
            self._by_path[rel] = job_id
            self._snaps[job_id] = {
                "job": job_id, "path": rel, "op": "convert", "state": "running",
                "progress": 0, "message": f"converting {original.name}",
                "result": None, "error": None,
            }
        self._fire(job_id)
        import asyncio
        task = asyncio.create_task(asyncio.to_thread(self._run, job_id, original, force))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return self.snapshot(job_id)

    def cancel(self, job_id: str) -> dict[str, Any]:
        snap = self.snapshot(job_id)
        if snap["state"] != "running":
            raise ConvertError(f"job {job_id} is not running", status=409)
        proc = self._procs.get(job_id)
        if proc is not None:
            proc.kill()
        self._update(job_id, state="cancelled", message="cancelled", progress=None)
        return self.snapshot(job_id)

    # -- the run ----------------------------------------------------------

    def _update(self, job_id: str, **fields: Any) -> None:
        snap = self._snaps.get(job_id)
        if snap is None:
            return
        snap.update(fields)

    def _fire(self, job_id: str) -> None:
        if self._emit is None:
            return
        try:
            self._emit(EVENT, dict(self._snaps[job_id]))
        except Exception:  # noqa: BLE001 — progress must never kill the job
            log.exception("convert emit failed")

    def _run(self, job_id: str, original: Path, force: bool) -> None:
        def on_progress(rec: dict[str, Any]) -> None:
            if self._snaps.get(job_id, {}).get("state") != "running":
                return
            self._update(job_id, progress=rec.get("pct"),
                         message=rec.get("message") or "")
            self._fire(job_id)

        try:
            result = run_convert(original, force=force, on_progress=on_progress,
                                 on_start=lambda p: self._procs.__setitem__(job_id, p))
        except ConvertError as e:
            # A kill lands here as "cancelled"; don't overwrite the state the
            # cancel already published.
            if self._snaps.get(job_id, {}).get("state") == "cancelled":
                self._fire(job_id)
            else:
                self._update(job_id, state="failed", error=str(e),
                             message=str(e), progress=None)
                self._fire(job_id)
            return
        except Exception as e:  # noqa: BLE001 — surfaced to the UI, not the loop
            log.exception("conversion of %s failed", original)
            self._update(job_id, state="failed", error=str(e), message=str(e),
                         progress=None)
            self._fire(job_id)
            return
        finally:
            self._procs.pop(job_id, None)
        self._update(job_id, state="done", progress=100, result=result,
                     message=f"converted {original.name}")
        self._fire(job_id)


class ExtraInstaller:
    """`uv sync --extra <name>` in a subprocess, output streamed on the
    `convert-install` SSE event. One install at a time per process.

    Deliberately the same `uv sync` the onboarding wizard runs, against the
    same lockfile — installing an extra is not a second dependency channel,
    it is the first one asked for more (plan §1 decision 5). The recorded
    extras are appended back in on every run because `uv sync` is exact and
    would otherwise uninstall the ones already there."""

    def __init__(self, emit: EmitFn | None = None):
        self._emit = emit
        self._snap: dict[str, Any] = {"job": None, "extra": None, "state": "idle",
                                      "message": "", "error": None}
        self._proc: subprocess.Popen | None = None
        self._tasks: set[Any] = set()
        self._seq = 0

    @property
    def active(self) -> bool:
        return self._snap["state"] == "running"

    def status(self) -> dict[str, Any]:
        rec = read_extras().get("pdf") or {}
        return {
            "installed": docling_installed(),
            "recorded": installed_extras(),
            "lock_hash": rec.get("lock_sha256"),
            "lock_current": lock_sha256(),
            "last_error": self._snap.get("error"),
            "job": dict(self._snap) if self._snap["state"] != "idle" else None,
            "engines": engines(),
        }

    # -- preflight --------------------------------------------------------

    @staticmethod
    def macos_floor_error() -> str | None:
        """torch's arm64 wheels are tagged `macosx_14_0` while the app's own
        floor is 11.0, so on an older Mac `uv sync` would fail deep inside a
        resolution the user can't read. Refuse first, in words. (The
        alternative — pinning torch back to its last macosx_11_0 release —
        was declined: it would drag a two-year-old torch into the lockfile for
        every platform to satisfy a Mac we don't otherwise support.)"""
        if sys.platform != "darwin":
            return None
        try:
            out = subprocess.run(["sw_vers", "-productVersion"], capture_output=True,
                                 text=True, timeout=10.0)
        except (OSError, subprocess.SubprocessError):
            return None          # can't tell — let uv have its go
        try:
            major = int((out.stdout.strip().split(".") or ["0"])[0])
        except ValueError:
            return None
        if major and major < 14:
            return ("document conversion needs macOS 14 or newer — the PDF "
                    "reader's machine-learning runtime ships no wheels for "
                    f"macOS {out.stdout.strip()}")
        return None

    @staticmethod
    def uv_path() -> str | None:
        """The desktop shell sets `ENOUGH_DESKTOP_UV` to the uv it spawned us
        with (its own sidecar, which may not be on PATH at all); a CLI install
        just has uv on PATH."""
        env = os.environ.get("ENOUGH_DESKTOP_UV")
        if env and Path(env).exists():
            return env
        return shutil.which("uv")

    def sync_argv(self, extra: str) -> list[str]:
        uv = self.uv_path()
        if not uv:
            raise ConvertError(
                "uv could not be found — install it (or launch enough from the "
                "desktop app) and try again", status=503)
        args = [uv, "sync", "--project", str(CODE_ROOT)]
        if os.environ.get("ENOUGH_DESKTOP"):
            # The bundled app runs a sealed source snapshot against a
            # committed lockfile; re-resolving there would defeat the
            # exclude-newer cooldown the whole supply-chain posture rests on.
            args.append("--frozen")
        for name in sorted({extra, *installed_extras()}):
            args += ["--extra", name]
        return args

    # -- control ----------------------------------------------------------

    def start(self, extra: str = "pdf") -> dict[str, Any]:
        if extra != "pdf":
            raise ConvertError(f"unknown extra {extra!r}", status=400)
        if self.active:
            raise ConvertError("an install is already running", status=409)
        if (why := self.macos_floor_error()):
            raise ConvertError(why, status=400)
        argv = self.sync_argv(extra)     # raises 503 when uv is missing
        self._seq += 1
        self._snap = {"job": f"ix{self._seq}", "extra": extra, "state": "running",
                      "message": "starting uv sync", "error": None}
        self._fire()
        import asyncio
        task = asyncio.create_task(asyncio.to_thread(self._run, argv, extra))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return dict(self._snap)

    def _fire(self, line: str | None = None) -> None:
        if self._emit is None:
            return
        payload = dict(self._snap)
        if line is not None:
            payload["line"] = line
        try:
            self._emit(INSTALL_EVENT, payload)
        except Exception:  # noqa: BLE001
            log.exception("convert-install emit failed")

    def _run(self, argv: list[str], extra: str) -> None:
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    cwd=str(CODE_ROOT), env=dict(os.environ))
        except OSError as e:
            self._snap.update(state="failed", error=str(e), message=str(e))
            self._fire()
            return
        self._proc = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self._snap["message"] = line
                self._fire(line)
        proc.wait()
        self._proc = None
        if proc.returncode != 0:
            msg = f"uv sync exited {proc.returncode} — see the log above"
            self._snap.update(state="failed", error=msg, message=msg)
            self._fire()
            return
        # The packages are in. Record that *before* the weights are fetched:
        # a network drop halfway through a 670 MB download must not leave the
        # extra unrecorded, because the next `uv sync` reads this file to
        # decide what to keep and would quietly uninstall it.
        record_extra(extra)
        try:
            result = self._prefetch_models()
        except Exception as e:  # noqa: BLE001 — surfaced to the UI, not the loop
            log.exception("model prefetch failed")
            reset_engines()
            why = (f"the packages installed, but the document models did not "
                   f"download ({e}) — run the install again to finish")
            self._snap.update(state="failed", error=why, message=why)
            self._fire()
            return
        reset_engines()
        mb = (result.get("bytes") or 0) / 1e6
        done = f"{extra} extra installed — document models ready ({mb:,.0f} MB)"
        self._snap.update(state="done", message=done, error=None)
        self._fire()

    def _prefetch_models(self) -> dict[str, Any]:
        """The tail of the install: docling's layout and table weights into
        `weights_dir()`, in the worker, streaming onto this same event.

        In the worker and not here because importing docling means importing
        torch, and the server process is the one place this design never lets
        that happen (plan §1 decision 6). The download is slow and the
        downloader has no callback, so the worker's heartbeat reports
        megabytes-on-disk and seconds elapsed — an honest line rather than a
        bar pretending to know what is left."""
        msg = "fetching the document models — this is a large one-time download"
        self._snap["message"] = msg
        self._fire(msg)

        def on_progress(rec: dict[str, Any]) -> None:
            line = rec.get("message") or ""
            if not line:
                return
            self._snap["message"] = line
            self._fire(line)

        job = {"op": "prefetch", "artifacts_dir": str(weights_dir())}
        return run_worker(job, on_progress=on_progress)
