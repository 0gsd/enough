"""The conversion/export worker: `sys.executable -m enough.convert_worker`.

One job in on stdin as JSON, newline-delimited JSON records out on stdout,
exit. Nothing in here is imported by the server process (plan §1 decision 6):
torch is heavy, a converter crash must not take the server down, the server
needn't restart after the `pdf` extra is installed, and cancelling a job is a
`kill` rather than a cooperative flag nobody can honour mid-`pandoc`.

Records
-------
    {"event": "progress", "pct": 0-100|null, "message": "…"}
    {"event": "done",  "result": {…}}
    {"event": "error", "error": "…"}

Anything this process writes to stderr is folded into the same stream by the
caller and kept only as a diagnostic tail, so a stray pandoc warning can never
be mistaken for a result — which matters more with docling in the picture,
since torch and transformers narrate their own warm-up onto stderr.

Two engines answer the `convert` op: pandoc shells out for the office/ebook
family, docling runs **in this process** for PDF, decks and workbooks. That
asymmetry is deliberate — docling is a Python API, and putting it here is the
whole reason the worker exists.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

# pandoc reader name per extension. The twin is written as gfm, never pandoc-markdown:
# the twin has to render in the UI's `renderMarkdown` and survive the agent's
# edits, and gfm alone has no footnote syntax to put a docx's footnotes in.
PANDOC_READERS = {".docx": "docx", ".odt": "odt", ".rtf": "rtf", ".epub": "epub"}
PANDOC_WRITERS = {".docx": "docx", ".odt": "odt", ".epub": "epub",
                  ".html": "html", ".rtf": "rtf"}
# `-raw_html` because the gfm writer otherwise falls back to raw HTML for
# anything markdown can't express — <figure>/<figcaption> around captioned
# images, odt's empty <span id="anchor"> bookmarks — and renderMarkdown
# escapes raw HTML, so every such fragment would show as literal angle
# brackets in the read face. With the extension off, pandoc expresses the
# content in plain markdown or drops the wrapper: a captioned image becomes
# `![alt](src)` plus a plain-text caption paragraph, and the anchors vanish.
# (_normalize_images stays as belt-and-braces for pandocs that differ.)
TWIN_FORMAT = "gfm-raw_html+footnotes"

# Writers that produce a fragment unless told otherwise. The binary containers
# are standalone by construction; html and rtf are not.
NEEDS_STANDALONE = {".html", ".rtf"}

# docling reader name per extension — the mirror of PANDOC_READERS, and the
# other half of the registry's `reader` column.
DOCLING_FORMATS = {".pdf": "PDF", ".pptx": "PPTX", ".xlsx": "XLSX"}

# Picture crops are lifted at 2× (144 dpi). The default 1.0 gives a 72-dpi
# crop that looks like a thumbnail next to the twin's text, and anything
# higher costs memory per page for no visible gain in the read face.
DOCLING_IMAGE_SCALE = 2.0

# The same 900 s discipline `_run` gives pandoc, expressed the way docling
# takes it: this runs in-process, so there is no subprocess to time out.
DOCLING_TIMEOUT = 900.0

# Only used to shape the progress bar. Measured on the QA Mac (M-series,
# arm64): a 107-page digital PDF read in 96 s, ~0.9 s/page steady state after
# the one-off model load. A scanned page through Apple Vision is faster, a
# dense multi-column page slower. It is an estimate, and the bar says
# "elapsed", never "remaining".
DOCLING_SECONDS_PER_PAGE = 0.9

# stdout is one stream shared with the progress heartbeat's thread, and half
# a JSON record is worse than a missing one.
_emit_lock = threading.Lock()


def emit(**rec: Any) -> None:
    line = json.dumps(rec) + "\n"
    with _emit_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


def progress(pct: int | None, message: str) -> None:
    emit(event="progress", pct=pct, message=message)


class WorkerError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# pandoc
# ---------------------------------------------------------------------------

def _pandoc() -> str:
    from .convert import pandoc_path
    exe = pandoc_path()
    if not exe:
        raise WorkerError("pandoc is not available in this environment")
    return exe


def _run(args: list[str], cwd: Path, *, timeout: float = 900.0) -> str:
    try:
        proc = subprocess.run(args, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise WorkerError(f"could not run {args[0]}: {e}") from None
    except subprocess.TimeoutExpired:
        raise WorkerError(f"{Path(args[0]).name} timed out after {timeout:.0f}s") from None
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = " / ".join(tail[-3:]) if tail else f"exit {proc.returncode}"
        raise WorkerError(f"{Path(args[0]).name}: {detail}")
    return proc.stdout


def _flatten_media(twin: Path, assets: Path, workdir: Path) -> int:
    """Move `report.pdf.assets/media/**` up into `report.pdf.assets/` and
    rewrite the twin's links to match.

    pandoc's `--extract-media` mirrors whatever internal folder structure the
    container had, so a docx yields `…assets/media/image1.png` and an epub can
    yield several levels. The twin's links are rewritten to the flat form
    `report.pdf.assets/image1.png` — the shape the plan specifies, the shape
    `_relink_docling_assets` lands the other engine on, and one that survives
    the user moving the pair around together.

    Links are replaced by exact string match on what pandoc actually wrote
    (raw and percent-encoded), rather than by parsing markdown: the twin is the
    user's document from here on and a regex sweep over it would be a much
    bigger promise than "swap these known paths"."""
    if not assets.is_dir():
        return 0
    text = twin.read_text(encoding="utf-8")
    moved = 0
    for src in sorted(p for p in assets.rglob("*") if p.is_file()):
        if src.parent == assets:
            continue                      # already flat
        dest = assets / src.name
        n = 2
        while dest.exists():
            dest = assets / f"{src.stem}-{n}{src.suffix}"
            n += 1
        old = src.relative_to(workdir).as_posix()
        new = dest.relative_to(workdir).as_posix()
        shutil.move(str(src), str(dest))
        moved += 1
        text = text.replace(old, new)
        # pandoc percent-encodes link targets containing spaces and friends;
        # the encoded form is a different string and needs its own pass.
        text = text.replace(urllib.parse.quote(old), urllib.parse.quote(new))
    # Prune the now-empty scaffolding pandoc left behind (deepest first).
    for d in sorted((p for p in assets.rglob("*") if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    if moved:
        twin.write_text(text, encoding="utf-8")
    return moved


_IMG_TAG_RE = re.compile(r"<img\b[^>]*?/?>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([a-zA-Z_:][-\w:.]*)\s*=\s*"([^"]*)"')


def _normalize_images(twin: Path) -> int:
    """Rewrite pandoc's raw `<img …>` tags as `![alt](src)`.

    pandoc's gfm writer falls back to raw HTML whenever an image carries
    attributes, and every image lifted out of a docx carries the width and
    height Word recorded. The UI's `renderMarkdown` escapes raw HTML, so those
    tags would render as literal angle brackets in the read face — and the
    plan's twin-content rule is plain markdown anyway. The display size is the
    only thing lost, and markdown has nowhere to put it."""
    text = twin.read_text(encoding="utf-8")

    def repl(m: re.Match[str]) -> str:
        attrs = dict(_ATTR_RE.findall(m.group(0)))
        src = attrs.get("src")
        if not src:
            return m.group(0)
        alt = attrs.get("alt", "").replace("]", r"\]")
        return f"![{alt}]({src})"

    new, n = _IMG_TAG_RE.subn(repl, text)
    if n:
        twin.write_text(new, encoding="utf-8")
    return n


# ---------------------------------------------------------------------------
# docling
# ---------------------------------------------------------------------------

def _docling_ocr_options() -> tuple[Any, str]:
    """The OCR engine is chosen per platform, never left to default.

    With the slim extras there is no easyocr sitting behind an unset option to
    quietly pick up the slack, so "unset" is an error waiting to surface as a
    blank scanned page. macOS gets Apple Vision through `ocrmac` — it is part
    of the OS, needs no weights, and is the reason the mac extra is the small
    one; everywhere else gets RapidOCR's ONNX models, which the installer
    prefetches alongside the layout model."""
    if sys.platform == "darwin":
        from docling.datamodel.pipeline_options import OcrMacOptions
        return OcrMacOptions(), "ocrmac"
    from docling.datamodel.pipeline_options import RapidOcrOptions
    return RapidOcrOptions(), "rapidocr"


def _pdf_page_count(pdf: Path) -> int | None:
    """Page count for the progress line, or None if it can't be had cheaply.
    pypdfium2 comes in with docling-parse, so this costs no new dependency and
    no full parse."""
    try:
        import pypdfium2
        doc = pypdfium2.PdfDocument(pdf)
        try:
            return len(doc)
        finally:
            doc.close()
    except Exception:  # noqa: BLE001 — a page count is a nicety, never a failure
        return None


class _Heartbeat:
    """A moving progress bar for work that offers no progress hook.

    docling 2.119 has no progress callback: `convert()` goes in and a finished
    document comes out, which for a 100-page PDF is minutes of silence, and
    `download_models()` is the same story for two thirds of a gigabyte. So a
    daemon thread ticks every few seconds with a number that is actually
    true — seconds elapsed, megabytes on disk — and drives the bar from `low`
    toward `high` on an estimate. The estimate is allowed to be wrong: the
    curve is asymptotic, so a slow job eases toward `high` and parks just
    short of the next step instead of pinning there and looking hung, and the
    message never claims to know what is left. `DECAY` is tuned so a job that
    takes exactly as long as its estimate is ~90% of the way through the
    band — pessimistic enough to never lie, generous enough that a document
    finishing on schedule doesn't look stalled at a third.

    `describe(elapsed)` writes the line; the class owns only the timing."""

    TICK = 3.0
    DECAY = 0.1

    def __init__(self, describe: Callable[[float], str], estimate: float,
                 low: int = 15, high: int = 65):
        self._describe = describe
        self._estimate = max(4.0, estimate)
        self._low, self._high = low, high
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> _Heartbeat:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        started = time.monotonic()
        while not self._stop.wait(self.TICK):
            elapsed = time.monotonic() - started
            frac = 1.0 - self.DECAY ** (elapsed / self._estimate)
            pct = int(self._low + (self._high - self._low) * frac)
            progress(pct, self._describe(elapsed))


def _relink_docling_assets(twin: Path, assets: Path) -> int:
    """Rewrite docling's picture links into the layout pandoc produces.

    `save_as_markdown(artifacts_dir=…)` writes **absolute** paths and names
    each file `image_000000_<64 hex chars>.png`. Neither survives contact with
    this design: the twin has to be movable with its assets folder, and
    `renderMarkdown`'s blob rewrite expects `report.pdf.assets/<file>` relative
    to the twin — the shape the pandoc reader already lands on. So the files
    are renamed `img-1.png`, `img-2.png`, … in document order (the numeric
    prefix docling writes *is* document order) and the absolute path strings
    are replaced in place, raw and percent-encoded, exactly as `_flatten_media`
    does for pandoc. Re-converts are stable because the assets dir is cleared
    first, so the same document always lands on the same names."""
    if not assets.is_dir():
        return 0
    files = sorted(p for p in assets.iterdir() if p.is_file())
    if not files:
        return 0
    text = twin.read_text(encoding="utf-8")
    for n, src in enumerate(files, 1):
        dest = assets / f"img-{n}{src.suffix.lower()}"
        if dest != src:
            src.rename(dest)
        old = src.as_posix()
        new = f"{assets.name}/{dest.name}"
        text = text.replace(old, new)
        text = text.replace(urllib.parse.quote(old), new)
    twin.write_text(text, encoding="utf-8")
    return len(files)


def _convert_docling(original: Path, twin: Path, assets: Path,
                     artifacts_dir: str | None) -> dict[str, Any]:
    """PDF, deck and workbook → markdown, in this process.

    In-process is the point of the worker (plan §1 decision 6): torch and the
    layout model are far too heavy to import into the server, a crash here
    must not take the server down, and cancelling is the caller's `kill`.
    Everything the engine needs — including where the weights live — arrives
    in the job dict, so nothing in here reads the server's configuration."""
    ext = original.suffix.lower()
    fmt = DOCLING_FORMATS.get(ext)
    if fmt is None:
        raise WorkerError(f"the PDF reader does not read {ext} in this build")

    progress(3, "starting the document reader")
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import ImageRefMode
    except ImportError as e:
        raise WorkerError(
            "the PDF reader isn't installed in this environment — install the "
            f"pdf extra from the UI window → extras and try again ({e})") from None

    ocr_options, ocr_name = _docling_ocr_options()
    input_format = getattr(InputFormat, fmt)
    format_options: dict[Any, Any] = {}
    if ext == ".pdf":
        format_options[InputFormat.PDF] = PdfFormatOption(
            pipeline_options=PdfPipelineOptions(
                do_ocr=True, ocr_options=ocr_options, do_table_structure=True,
                artifacts_path=Path(artifacts_dir) if artifacts_dir else None,
                # REFERENCED image export has nothing to write without this.
                generate_picture_images=True, images_scale=DOCLING_IMAGE_SCALE,
                document_timeout=DOCLING_TIMEOUT,
            ))
    progress(8, "loading the layout and table models")
    converter = DocumentConverter(allowed_formats=[input_format],
                                  format_options=format_options)

    pages = _pdf_page_count(original) if ext == ".pdf" else None
    where = f"{pages} pages of {original.name}" if pages else original.name
    try:
        with _Heartbeat(lambda s: f"reading {where} — {int(s)}s elapsed",
                        (pages or 8) * DOCLING_SECONDS_PER_PAGE):
            result = converter.convert(original)
    except WorkerError:
        raise
    except Exception as e:  # noqa: BLE001 — docling raises its own error classes
        raise WorkerError(
            f"the document reader could not read {original.name}: "
            f"{type(e).__name__}: {e}") from None
    doc = result.document
    if doc is None:
        raise WorkerError(f"the document reader produced nothing for {original.name}")

    progress(70, "writing the markdown twin")
    # `image_placeholder=""` because the default is an HTML comment, and
    # renderMarkdown escapes raw HTML — a picture docling couldn't lift would
    # otherwise show as a literal `<!-- image -->` in the read face.
    doc.save_as_markdown(twin, artifacts_dir=assets, image_placeholder="",
                         image_mode=ImageRefMode.REFERENCED)

    progress(85, "tidying extracted images")
    images = _relink_docling_assets(twin, assets)
    _normalize_images(twin)
    if assets.is_dir() and not any(assets.iterdir()):
        try:
            assets.rmdir()               # no pictures in this document
        except OSError:
            pass

    from .convert import docling_version
    progress(100, "done")
    return {"twin": twin.name, "assets": assets.name if assets.is_dir() else None,
            "images": images,
            # Only the PDF pipeline has an OCR stage; a deck and a workbook
            # carry their text as text, and recording an engine that never ran
            # would be a lie the manifest then repeats to the help center.
            "engine": {"name": "docling", "version": docling_version(),
                       "ocr": ocr_name if ext == ".pdf" else None}}


def do_convert(job: dict[str, Any]) -> dict[str, Any]:
    original = Path(job["original"])
    twin = Path(job["twin"])
    assets = Path(job["assets"])
    engine = job.get("engine")
    if engine not in ("pandoc", "docling"):
        raise WorkerError(f"unknown engine {engine!r}")

    if assets.is_dir():
        # A re-convert regenerates the assets dir from the original, and
        # clearing it first keeps extracted names stable (rId9.png stays
        # rId9.png instead of colliding into rId9-2.png forever, img-1.png
        # stays img-1.png). The dir is backend-owned — hidden from the tree,
        # populated only by extraction — so nothing user-authored lives here
        # to protect.
        for stale in assets.iterdir():
            try:
                stale.unlink()
            except OSError:
                pass

    if engine == "docling":
        return _convert_docling(original, twin, assets, job.get("artifacts_dir"))

    ext = original.suffix.lower()
    reader = PANDOC_READERS.get(ext)
    if reader is None:
        raise WorkerError(f"pandoc does not read {ext} in this build")

    workdir = original.parent
    progress(5, f"reading {original.name}")
    args = [_pandoc(), "-f", reader, "-t", TWIN_FORMAT, "--wrap=none",
            f"--extract-media={assets.name}"]
    if ext == ".docx":
        # Only the docx reader honours this, and accepting is the honest
        # default: the twin is what the user will edit, and leaving insertions
        # marked up as raw XML would make it unreadable.
        args.append("--track-changes=accept")
    args += ["-o", twin.name, original.name]
    _run(args, workdir)

    progress(70, "tidying extracted images")
    images = _flatten_media(twin, assets, workdir)
    _normalize_images(twin)
    if assets.is_dir():
        try:
            assets.rmdir()               # no media in this document
        except OSError:
            pass

    from .convert import pandoc_version
    progress(100, "done")
    return {"twin": twin.name, "assets": assets.name if assets.is_dir() else None,
            "images": images,
            "engine": {"name": "pandoc", "version": pandoc_version(), "ocr": None}}


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def _export_pdf(twin: Path, out: Path, resource_path: Path) -> None:
    """markdown → PDF, in two steps through typst.

    Spiked both routes the plan allowed. `--pdf-engine=typst` needs a `typst`
    *executable* for pandoc to exec, and the `typst` wheel we now depend on
    ships a Python module with no console script — so on a plain install that
    route is simply unavailable. `-t typst` + `typst.compile()` works on every
    install with no PATH assumptions, so it is the only route implemented;
    a user's own typst CLI buys nothing here.

    The intermediate `.typ` is written beside the twin so the relative image
    paths pandoc emits resolve for typst too (typst roots itself at the
    source file's directory)."""
    typ = twin.parent / f".{twin.name}.export.typ"
    try:
        _run([_pandoc(), "-f", "gfm+footnotes", "-t", "typst",
              f"--resource-path={resource_path}", "--standalone",
              "-o", typ.name, twin.name], twin.parent)
        progress(60, "typesetting PDF")
        try:
            import typst
        except ImportError as e:
            raise WorkerError(f"typst is not available in this environment: {e}") from None
        try:
            typst.compile(str(typ), output=str(out), root=str(twin.parent))
        except Exception as e:  # noqa: BLE001 — typst raises its own error class
            raise WorkerError(f"typst could not typeset the document: {e}") from None
    finally:
        try:
            typ.unlink()
        except OSError:
            pass


def do_export(job: dict[str, Any]) -> dict[str, Any]:
    twin = Path(job["twin"])
    out = Path(job["out"])
    target = job["target"]
    resource_path = Path(job.get("resource_path") or twin.parent)
    reference = job.get("reference_doc")

    progress(10, f"writing {out.name}")
    if target == ".pdf":
        _export_pdf(twin, out, resource_path)
    else:
        writer = PANDOC_WRITERS.get(target)
        if writer is None:
            raise WorkerError(f"pandoc does not write {target} in this build")
        args = [_pandoc(), "-f", "gfm+footnotes", "-t", writer,
                f"--resource-path={resource_path}"]
        if target in NEEDS_STANDALONE:
            args.append("--standalone")
        if target == ".html":
            # An exported .html should be one portable file, not a page that
            # breaks the moment it leaves the assets folder behind.
            args.append("--embed-resources")
        if reference:
            # Decision 4 — styles, page size/margins, headers and footers come
            # from the original document. Not optional: it is what makes an
            # overwrite still look like the user's document.
            args.append(f"--reference-doc={reference}")
        args += ["-o", str(out), twin.name]
        _run(args, twin.parent)

    progress(100, "done")
    if not out.is_file():
        raise WorkerError(f"the converter produced no {out.name}")
    return {"written": out.name, "path": str(out), "bytes": out.stat().st_size,
            "reference_doc": bool(reference)}


# ---------------------------------------------------------------------------
# model prefetch (the tail of the `pdf` extra's install)
# ---------------------------------------------------------------------------

def _dir_bytes(d: Path) -> int:
    try:
        return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
    except OSError:
        return 0


def do_prefetch(job: dict[str, Any]) -> dict[str, Any]:
    """Fetch docling's layout and table weights into the artifacts dir.

    Runs at the end of `/api/convert/install` (plan §6) so that the *first*
    conversion never stops to download two thirds of a gigabyte behind a
    progress bar the user didn't ask for. Only what the pipeline in
    `_convert_docling` actually loads: layout and TableFormer, plus RapidOCR's
    ONNX models off macOS. No easyocr, no VLMs, no picture classifier, no
    code/formula enrichment — those are docling defaults this worker turns
    off, and each is another hundred megabytes of weights nothing here reads.

    Idempotent: the downloader compares against what's on disk, so re-running
    a complete install is a handful of HTTP HEADs."""
    out = Path(job["artifacts_dir"])
    try:
        from docling.utils import model_downloader
    except ImportError as e:
        raise WorkerError(
            f"the PDF reader isn't installed in this environment ({e})") from None
    out.mkdir(parents=True, exist_ok=True)
    before = _dir_bytes(out)
    progress(5, f"fetching the layout and table models into {out}")

    def line(elapsed: float) -> str:
        mb = _dir_bytes(out) / 1e6
        return f"fetching document models — {mb:,.0f} MB on disk, {int(elapsed)}s elapsed"

    with _Heartbeat(line, 90.0, low=5, high=95):
        try:
            model_downloader.download_models(
                output_dir=out, progress=False,
                with_layout=True, with_tableformer=True,
                # docling's own defaults; off because the pipeline never
                # loads them.
                with_code_formula=False, with_picture_classifier=False,
                with_easyocr=False,
                # macOS OCRs through Apple Vision, which is the OS and has no
                # weights to fetch; every other platform runs RapidOCR.
                with_rapidocr=sys.platform != "darwin",
            )
        except Exception as e:  # noqa: BLE001 — hub errors are many and all fatal here
            raise WorkerError(
                f"the document models could not be downloaded: "
                f"{type(e).__name__}: {e}") from None
    after = _dir_bytes(out)
    progress(100, f"document models ready ({after / 1e6:,.0f} MB)")
    return {"artifacts_dir": str(out), "bytes": after,
            "fetched": max(0, after - before)}


# ---------------------------------------------------------------------------

_OPS = {"convert": do_convert, "export": do_export, "prefetch": do_prefetch}


def main(argv: list[str] | None = None) -> int:
    raw = sys.stdin.read()
    try:
        job = json.loads(raw)
    except ValueError as e:
        emit(event="error", error=f"malformed job: {e}")
        return 2
    fn = _OPS.get(job.get("op"))
    if fn is None:
        emit(event="error", error=f"unknown op {job.get('op')!r}")
        return 2
    try:
        result = fn(job)
    except WorkerError as e:
        emit(event="error", error=str(e))
        return 1
    except Exception as e:  # noqa: BLE001 — the caller only ever sees this stream
        emit(event="error", error=f"{type(e).__name__}: {e}")
        return 1
    emit(event="done", result=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
