"""Pagination: a finished markdown document typeset into a PDF.

Export (convert.py) answers "give me this text as a .docx/.pdf". Pagination
answers the other question — "set this book". The user picks a trim size, a
bundled font, a margin, where the footnotes go, whether pages impose 2-up or
as a saddle-stitched booklet; the pipeline compiles markdown → typst → PDF,
embeds the markdown back into the PDF so re-importing it is byte-exact, and
optionally renders per-page SVGs for the in-app viewer. Full design:
docs/paginate-plan.md.

What lives here vs. in the worker
--------------------------------
Same split as convert.py, for the same reason: `server.py` imports this on
every tree build (the `.pdf` reader gate asks whether a PDF carries our
markdown), so nothing at module scope may import pandoc, typst or pypdf.
This module owns the option schema, the size table, output naming, the
imposition arithmetic, and the `.typ` surgery — all pure, all unit-testable
without a document. `convert_worker.do_paginate` runs the heavy half.

The `.typ` surgery is the one piece with an external contract. pandoc's
`--standalone` typst template ends with a `#show: doc => conf(…)` rule whose
`conf` sets a US-letter page before any of our settings could take effect —
so `split_template()` cuts the document at exactly that rule, keeps pandoc's
helper definitions above it and the body below, and drops the wrapper. Our
preamble then *is* the document's page and text setup. `tests/test_paginate.py`
pins the boundary against real pandoc output.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("enough.paginate")

SCHEMA = 1

# The two PDF file attachments every paginated PDF carries (plan §2.4). The
# first is what makes re-import exact; the second is what makes "paginate it
# again the same way" possible.
ATTACH_SOURCE = "enough-source.md"
ATTACH_OPTIONS = "enough-paginate.json"


class PaginateError(RuntimeError):
    """User- and agent-readable refusal. `status` is the HTTP code the
    endpoint answers with — 400 for an option we can't satisfy, 404 for a
    missing source, 503 when an engine isn't there. Same shape and same
    reasoning as `convert.ConvertError`."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# The option schema (plan §2.2) — ONE table. The modal, the endpoint and the
# worker all read this; JS hardcodes none of it (`/api/paginate/status`).
# ---------------------------------------------------------------------------

MM_PER_IN = 25.4

# Named trim sizes, portrait W×H, as the user names them. `digest` is an
# alias of `half-letter` and keeps its own label because that is the word
# print shops use for it.
SIZES: dict[str, tuple[float, float, str]] = {
    "letter":      (8.5, 11.0, "in"),
    "half-letter": (5.5, 8.5, "in"),
    "legal":       (8.5, 14.0, "in"),
    "a4":          (210.0, 297.0, "mm"),
    "a5":          (148.0, 210.0, "mm"),
    "b5":          (176.0, 250.0, "mm"),
    "trade":       (6.0, 9.0, "in"),
    "digest":      (5.5, 8.5, "in"),
    "pocket":      (4.25, 6.87, "in"),
}

FOOTNOTE_PLACEMENTS = ("page", "chapter", "book")
ORIENTATIONS = ("portrait", "landscape")
LAYOUTS = ("single", "twoup", "booklet")

# The bundled OFL families (plan §2.7). These strings are what typst must see
# as family names, so they are the same strings the modal offers and the same
# strings the preamble writes.
FONTS = ("EB Garamond", "Source Serif 4", "Source Sans 3", "Inter")

# Body size is fixed: the modal already asks for six decisions, and a point
# size the user can't preview is the seventh nobody wants.
BODY_SIZE_PT = 11.0

MARGIN_MIN_MM = 5.0
MARGIN_MAX_MM = 60.0
CUSTOM_MIN_MM = 40.0
CUSTOM_MAX_MM = 1000.0
NAME_MAX = 80

DEFAULTS: dict[str, Any] = {
    "footnotes": "page",
    "size": "letter",
    "orientation": "portrait",
    "layout": "single",
    "font": "EB Garamond",
    "margin_mm": 20.0,
    "page_numbers": True,
    "bring_in": False,
}

# A filename we are about to stamp a date onto and write beside the user's
# document: single path segment, no separators, no dot leader.
_NAME_BAD = re.compile(r"[/\\\x00-\x1f]")


def sizes_view() -> dict[str, dict[str, Any]]:
    """The size table as JSON for the modal's preview pane — millimetres
    alongside the numbers the user recognises, so the CSS page can be drawn
    to ratio without a second table in JS."""
    out: dict[str, dict[str, Any]] = {}
    for name, (w, h, unit) in SIZES.items():
        wm, hm = _to_mm(w, unit), _to_mm(h, unit)
        out[name] = {"w": w, "h": h, "unit": unit,
                     "w_mm": round(wm, 2), "h_mm": round(hm, 2),
                     "ratio": round(wm / hm, 4)}
    return out


def _to_mm(value: float, unit: str) -> float:
    return value * MM_PER_IN if unit == "in" else value


def _one_of(options: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    value = options.get(key, DEFAULTS.get(key))
    if not isinstance(value, str) or value not in allowed:
        raise PaginateError(
            f"{key} must be one of {', '.join(allowed)}", status=400)
    return value


def _number(options: dict[str, Any], key: str, lo: float, hi: float) -> float:
    value = options.get(key, DEFAULTS.get(key))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PaginateError(f"{key} must be a number", status=400)
    value = float(value)
    if not lo <= value <= hi:
        raise PaginateError(f"{key} must be between {lo:g} and {hi:g}", status=400)
    return value


def _header_field(raw: Any, which: str) -> dict[str, Any]:
    if raw is None:
        return {"text": "", "chapter": False}
    if not isinstance(raw, dict):
        raise PaginateError(f"headers.{which} must be an object", status=400)
    text = raw.get("text") or ""
    if not isinstance(text, str):
        raise PaginateError(f"headers.{which}.text must be a string", status=400)
    # Control characters would land inside a typst string literal.
    text = "".join(c for c in text if c >= " " or c == "\t").strip()[:120]
    return {"text": text, "chapter": bool(raw.get("chapter"))}


def validate(options: dict[str, Any]) -> dict[str, Any]:
    """Normalize and check a §2.2 options object. Returns a fresh dict with
    every key present and defaulted — the shape the worker, the manifest and
    the PDF attachment all carry, so what the user chose is recoverable from
    the artifact alone."""
    if not isinstance(options, dict):
        raise PaginateError("expected a paginate options object", status=400)

    path = (options.get("path") or "").strip()
    if not path:
        raise PaginateError("missing path", status=400)

    out: dict[str, Any] = {
        "path": path,
        "footnotes": _one_of(options, "footnotes", FOOTNOTE_PLACEMENTS),
        "size": _one_of(options, "size", (*SIZES, "custom")),
        "orientation": _one_of(options, "orientation", ORIENTATIONS),
        "layout": _one_of(options, "layout", LAYOUTS),
        "font": _one_of(options, "font", FONTS),
        "margin_mm": _number(options, "margin_mm", MARGIN_MIN_MM, MARGIN_MAX_MM),
        "page_numbers": bool(options.get("page_numbers", DEFAULTS["page_numbers"])),
        "bring_in": bool(options.get("bring_in", DEFAULTS["bring_in"])),
    }

    if out["size"] == "custom":
        custom = options.get("custom_size")
        if not isinstance(custom, dict):
            raise PaginateError(
                "custom_size is required when size is 'custom'", status=400)
        unit = custom.get("unit", "mm")
        if unit not in ("mm", "in"):
            raise PaginateError("custom_size.unit must be 'mm' or 'in'", status=400)
        dims: dict[str, Any] = {"unit": unit}
        for key in ("w", "h"):
            value = custom.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PaginateError(f"custom_size.{key} must be a number", status=400)
            mm = _to_mm(float(value), unit)
            if not CUSTOM_MIN_MM <= mm <= CUSTOM_MAX_MM:
                raise PaginateError(
                    f"custom_size.{key} must be between {CUSTOM_MIN_MM:g}mm and "
                    f"{CUSTOM_MAX_MM:g}mm", status=400)
            dims[key] = float(value)
        out["custom_size"] = dims
    else:
        out["custom_size"] = None

    headers = options.get("headers") or {}
    if not isinstance(headers, dict):
        raise PaginateError("headers must be an object", status=400)
    out["headers"] = {
        "enabled": bool(headers.get("enabled")),
        "left": _header_field(headers.get("left"), "left"),
        "right": _header_field(headers.get("right"), "right"),
    }

    name = (options.get("name") or "").strip()
    if not name:
        name = Path(path).stem or "document"
    if _NAME_BAD.search(name) or name.startswith(".") or name in (".", ".."):
        raise PaginateError(
            "name must be a plain filename with no path separators", status=400)
    if len(name) > NAME_MAX:
        raise PaginateError(f"name must be {NAME_MAX} characters or fewer", status=400)
    out["name"] = name

    # Margins that eat the page produce a typst error nobody can read.
    w_mm, h_mm = page_size_mm(out)
    if out["margin_mm"] * 2 >= min(w_mm, h_mm):
        raise PaginateError(
            f"a {out['margin_mm']:g}mm margin leaves no page inside "
            f"{w_mm:.0f}×{h_mm:.0f}mm", status=400)
    return out


def page_size_mm(options: dict[str, Any]) -> tuple[float, float]:
    """(width, height) in millimetres, orientation applied."""
    size = options.get("size")
    if size == "custom":
        custom = options.get("custom_size") or {}
        unit = custom.get("unit", "mm")
        w = _to_mm(float(custom["w"]), unit)
        h = _to_mm(float(custom["h"]), unit)
    else:
        try:
            raw_w, raw_h, unit = SIZES[size]
        except KeyError:
            raise PaginateError(f"unknown size {size!r}", status=400) from None
        w, h = _to_mm(raw_w, unit), _to_mm(raw_h, unit)
    if options.get("orientation") == "landscape":
        w, h = h, w
    return w, h


# ---------------------------------------------------------------------------
# Fonts (wave C fills the directory; this half only has to find it)
# ---------------------------------------------------------------------------

def fonts_dir() -> Path:
    from .skeleton import _install_defaults_root
    return _install_defaults_root() / "fonts"


def fonts_bundled() -> bool:
    """Is there a bundled font set to compile against? A dev tree without one
    still paginates — typst falls back to the system's fonts and the PDF is
    simply set in whatever the machine has (see `font_paths`)."""
    d = fonts_dir()
    try:
        if not d.is_dir():
            return False
        return any(p.suffix.lower() in (".ttf", ".otf") for p in d.rglob("*"))
    except OSError:
        return False


def font_paths() -> list[str]:
    return [str(fonts_dir())] if fonts_bundled() else []


# ---------------------------------------------------------------------------
# Naming (plan §2.4) — date only, `-1`/`-2` on collision
# ---------------------------------------------------------------------------

def output_pdf(source: Path, name: str, when: dt.datetime | None = None) -> Path:
    """`book.md` + name "book" on 2026-08-23 → `book-2026-08-23.pdf` beside
    the source, then `-1`, `-2`, … Local time, like `datestamped_path`: the
    stamp is for the person reading their own folder.

    The pages directory counts as a collision too — a leftover viewer folder
    from an interrupted run must not be merged into the next one's."""
    when = when or dt.datetime.now()
    stamp = when.strftime("%Y-%m-%d")
    cand = source.parent / f"{name}-{stamp}.pdf"
    n = 1
    while cand.exists() or pages_dir(cand).exists():
        cand = source.parent / f"{name}-{stamp}-{n}.pdf"
        n += 1
    return cand


def pages_dir(pdf: Path) -> Path:
    return pdf.parent / f"{pdf.name}.pages"


def viewer_manifest_path(pdf: Path) -> Path:
    return pdf.parent / f".{pdf.name}.paginate.json"


def page_svg_name(index: int) -> str:
    """1-based, zero-padded so the viewer can sort by name."""
    return f"page-{index:04d}.svg"


def is_pages_dir(path: Path) -> bool:
    """Is this the backend-owned viewer folder for a paginated PDF?

    Both halves matter, exactly as `convert.has_twin` insists on the manifest:
    a folder somebody happened to name `notes.pdf.pages` is theirs, and hiding
    it from the tree would make it unreachable."""
    name = path.name
    if not name.endswith(".pdf.pages"):
        return False
    pdf = path.parent / name[: -len(".pages")]
    try:
        return viewer_manifest_path(pdf).is_file()
    except OSError:
        return False


def is_viewer_manifest(path: Path) -> bool:
    return path.name.startswith(".") and path.name.endswith(".paginate.json")


def read_viewer_manifest(pdf: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(viewer_manifest_path(pdf).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != SCHEMA:
        return None
    return data


def write_viewer_manifest(pdf: Path, *, pages: int, source: str,
                          options: dict[str, Any]) -> Path:
    """tmp + rename, like every other sidecar enough owns."""
    p = viewer_manifest_path(pdf)
    data = {"version": SCHEMA, "pages": pages, "source": source,
            "options": options, "created": _utc_now()}
    tmp = p.parent / f"{p.name}.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Embedded source (plan §2.6) — the round trip that makes re-import exact
# ---------------------------------------------------------------------------

# (size, mtime_ns) keyed, because `convert.state()` asks this of every PDF in
# the tree on every tree build and the answer only changes when the file does.
_embed_cache: dict[str, tuple[int, int, bool]] = {}


def reset_embed_cache() -> None:
    _embed_cache.clear()


_pypdf_quiet = False


def embedded_source(pdf_path: Path) -> tuple[str, dict[str, Any]] | None:
    """The markdown and the options a paginated PDF carries, or None for a
    PDF that isn't ours. pypdf is a base dependency; the import is local
    because the server imports this module on every tree build."""
    global _pypdf_quiet
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    if not _pypdf_quiet:
        # This function is a probe run over every PDF in the tree, and "that
        # file is not one of ours" is its ordinary answer — pypdf's warnings
        # about foreign or truncated files are the expected case here, not an
        # anomaly worth a log line per tree build.
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        _pypdf_quiet = True
    try:
        reader = PdfReader(str(pdf_path))
        attachments = reader.attachments
        blobs = attachments.get(ATTACH_SOURCE)
    except Exception:  # noqa: BLE001 — an unreadable/foreign PDF is just "not ours"
        return None
    if not blobs:
        return None
    try:
        text = bytes(blobs[0]).decode("utf-8")
    except (UnicodeDecodeError, TypeError, ValueError):
        return None
    meta: dict[str, Any] = {}
    try:
        raw = attachments.get(ATTACH_OPTIONS)
        if raw:
            loaded = json.loads(bytes(raw[0]).decode("utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
    except Exception:  # noqa: BLE001 — the markdown is the contract; options are a bonus
        meta = {}
    return text, meta


def has_embedded_source(pdf_path: Path) -> bool:
    """Cheap gate for `convert.reader_for`: does this PDF unpack without
    docling? Cached on (size, mtime_ns) — the tree asks it constantly."""
    try:
        st = pdf_path.stat()
    except OSError:
        return False
    key = str(pdf_path)
    hit = _embed_cache.get(key)
    if hit is not None and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
        return hit[2]
    found = embedded_source(pdf_path) is not None
    if len(_embed_cache) > 512:
        _embed_cache.clear()
    _embed_cache[key] = (st.st_size, st.st_mtime_ns, found)
    return found


# ---------------------------------------------------------------------------
# Imposition arithmetic (plan §2.5.6) — pure functions over (N, W, H) so the
# page order and the placement rectangles are testable without a PDF.
# ---------------------------------------------------------------------------

def sheet_order(n: int, layout: str) -> list[tuple[int | None, int | None]]:
    """Which logical pages land on which half of which printed sheet.

    Returns one `(left, right)` tuple per printed side, 1-based logical page
    numbers, `None` for a blank. `twoup` is consecutive pairs. `booklet` is
    saddle stitch: pad to a multiple of four, then front(i) = [N-2i, 1+2i]
    and back(i) = [2+2i, N-1-2i], which printed double-sided (flip on the
    short edge), folded and nested reads 1..N."""
    if n <= 0:
        return []
    if layout == "twoup":
        pages: list[int | None] = list(range(1, n + 1))
        if len(pages) % 2:
            pages.append(None)
        return [(pages[i], pages[i + 1]) for i in range(0, len(pages), 2)]
    if layout == "booklet":
        total = n + (-n % 4)

        def leaf(k: int) -> int | None:
            return k if k <= n else None

        out: list[tuple[int | None, int | None]] = []
        for i in range(total // 4):
            out.append((leaf(total - 2 * i), leaf(1 + 2 * i)))       # front
            out.append((leaf(2 + 2 * i), leaf(total - 1 - 2 * i)))   # back
        return out
    raise PaginateError(f"{layout} is not an imposed layout", status=400)


def sheet_size(w: float, h: float) -> tuple[float, float]:
    """The printed sheet for a W×H logical page: the same paper turned
    sideways, so two pages sit next to each other on it."""
    return h, w


def slot_rect(slot: int, w: float, h: float) -> tuple[float, float, float, float]:
    """`(x, y, width, height)` of logical page `slot` (0 = left, 1 = right)
    on its sheet, in the same units as `w`/`h`. The page is scaled down to
    fit its half and centred there; `s` never exceeds 1 in practice because
    half a sideways sheet is exactly the page turned down."""
    sheet_w, sheet_h = sheet_size(w, h)
    s = min((sheet_w / 2) / w, sheet_h / h)
    pw, ph = w * s, h * s
    half = sheet_w / 2
    x = slot * half + (half - pw) / 2
    y = (sheet_h - ph) / 2
    return x, y, pw, ph


def slot_scale(w: float, h: float) -> float:
    sheet_w, sheet_h = sheet_size(w, h)
    return min((sheet_w / 2) / w, sheet_h / h)


# ---------------------------------------------------------------------------
# `.typ` surgery — the pandoc template boundary, headings, footnotes
# ---------------------------------------------------------------------------

# pandoc's standalone typst template ends with this show rule; everything
# after its closing paren is the document body. `conf` sets a US-letter page
# *before* any set rule inside the body could take effect, which is why the
# rule is dropped rather than appended to. Pinned by a test against real
# pandoc output.
TEMPLATE_MARKER = "#show: doc => conf("

_HEADING_RE = re.compile(r"^(=+)[ \t]+(\S.*)$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def split_template(typ: str) -> tuple[str, str]:
    """`(head, body)` — pandoc's helper definitions, and the document content,
    with the `#show: doc => conf(…)` wrapper removed from between them."""
    i = typ.find(TEMPLATE_MARKER)
    if i < 0:
        raise PaginateError(
            "this pandoc's typst template is not one enough knows how to "
            "paginate — export a plain PDF instead", status=500)
    open_paren = i + len(TEMPLATE_MARKER) - 1
    end = _match_delims(typ, open_paren, "(", ")")
    if end is None:
        raise PaginateError(
            "pandoc's typst template ended mid-expression", status=500)
    return typ[:i], typ[end + 1:].lstrip("\n")


def _skip_raw(text: str, i: int) -> int:
    """`i` is at a backtick. Index just past the raw span it opens."""
    n = len(text)
    j = i
    while j < n and text[j] == "`":
        j += 1
    ticks = "`" * (j - i)
    close = text.find(ticks, j)
    if close < 0:
        return n
    k = close + len(ticks)
    while k < n and text[k] == "`":
        k += 1
    return k


def _match_delims(text: str, start: int, opener: str, closer: str) -> int | None:
    """Index of the delimiter matching the one at `start`, or None.

    Escape- and raw-aware: `\\]` is a literal bracket (pandoc escapes every
    bracket it writes into a footnote body) and a bracket inside a `` ` ``
    span is text, not structure."""
    depth = 0
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            i = _skip_raw(text, i)
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def typ_headings(body: str) -> list[dict[str, Any]]:
    """Every `=`-run heading in a typst body, with its level, its title
    source, and its span. Fenced raw blocks are skipped — pandoc passes a
    markdown code fence through verbatim, and `= not a heading` inside one
    is exactly the hazard."""
    out: list[dict[str, Any]] = []
    pos = 0
    fence: str | None = None
    for line in body.splitlines(keepends=True):
        m_fence = _FENCE_RE.match(line)
        if m_fence:
            tok = m_fence.group(1)[0]
            if fence is None:
                fence = tok
            elif fence == tok:
                fence = None
            pos += len(line)
            continue
        if fence is None:
            m = _HEADING_RE.match(line)
            if m:
                out.append({"level": len(m.group(1)), "title": m.group(2).strip(),
                            "start": pos, "end": pos + len(line)})
        pos += len(line)
    return out


def chapter_level(body: str) -> int | None:
    """The chapter level: the smallest heading level present (plan §1). None
    when the document has no headings — then it is one chapter."""
    headings = typ_headings(body)
    return min(h["level"] for h in headings) if headings else None


def extract_footnotes(body: str) -> tuple[str, list[str], list[int]]:
    """Pull every `#footnote[…]` body out, leaving `#super[n]` behind.

    Returns `(new_body, bodies, positions)` — the bodies in document order and
    the offset of each superscript in `new_body`, which is what tells the
    chapter placement which chapter a note belongs to. Balanced-bracket, not
    a regex: footnote bodies nest brackets (`#link("…")[…]`) and carry
    escaped ones."""
    parts: list[str] = []
    bodies: list[str] = []
    positions: list[int] = []
    out_len = 0
    i, last, n = 0, 0, len(body)
    mark = "#footnote["
    while i < n:
        c = body[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            i = _skip_raw(body, i)
            continue
        if body.startswith(mark, i):
            end = _match_delims(body, i + len(mark) - 1, "[", "]")
            if end is None:
                i += len(mark)
                continue
            bodies.append(body[i + len(mark):end])
            sup = f"#super[{len(bodies)}]"
            parts.append(body[last:i])
            out_len += i - last
            positions.append(out_len)
            parts.append(sup)
            out_len += len(sup)
            last = i = end + 1
            continue
        i += 1
    parts.append(body[last:])
    return "".join(parts), bodies, positions


def place_endnotes(body: str, bodies: list[str], positions: list[int],
                   placement: str, level: int | None) -> str:
    """Emit the extracted footnote bodies where the user asked for them.

    `chapter` drops each chapter's notes just before the next chapter starts
    (and the last chapter's at the end); `book` appends one `= Footnotes`
    section, grouped under chapter subheads when the document has chapters.
    Numbering is continuous 1..N in both, because the source was renumbered
    first and the superscripts have to match it."""
    if not bodies:
        return body
    chapters = [h for h in typ_headings(body) if level and h["level"] == level]
    groups = _group_by_chapter(chapters, bodies, positions)

    if placement == "book":
        return (body.rstrip("\n") + "\n\n"
                + _book_section(chapters, bodies, groups, level))
    if not chapters:
        return body.rstrip("\n") + "\n\n" + _note_block(
            list(enumerate(bodies, 1))) + "\n"

    inserts: list[tuple[int, str]] = []
    for idx, items in groups.items():
        block = _note_block(items)
        if idx + 1 < len(chapters):
            inserts.append((chapters[idx + 1]["start"], block + "\n\n"))
        else:
            inserts.append((len(body), "\n\n" + block + "\n"))
    out = body
    for offset, text in sorted(inserts, reverse=True):
        out = out[:offset] + text + out[offset:]
    return out


def _group_by_chapter(chapters: list[dict[str, Any]], bodies: list[str],
                      positions: list[int]) -> dict[int, list[tuple[int, str]]]:
    """Notes bucketed by the last chapter heading before each superscript.
    Notes ahead of the first heading belong with that first chapter — front
    matter has nowhere else to put them."""
    starts = [c["start"] for c in chapters]
    groups: dict[int, list[tuple[int, str]]] = {}
    for number, (pos, text) in enumerate(zip(positions, bodies), 1):
        idx = 0
        for k, start in enumerate(starts):
            if start < pos:
                idx = k
        groups.setdefault(idx, []).append((number, text))
    return groups


def _note_block(items: list[tuple[int, str]]) -> str:
    """One endnote list. A rule and a smaller size mark it off from the prose
    without inventing a heading the user didn't write."""
    lines = ["#block(above: 1.5em, below: 0.5em, breakable: true)[",
             "  #line(length: 30%, stroke: 0.5pt)", ""]
    for number, text in items:
        lines.append(f"  #text(size: 0.9em)[#super[{number}] {text}]")
        lines.append("")
    lines.append("]")
    return "\n".join(lines)


def _book_section(chapters: list[dict[str, Any]], bodies: list[str],
                  groups: dict[int, list[tuple[int, str]]],
                  level: int | None) -> str:
    """The book-end section: one heading at chapter level (so the chapter
    show-rule gives it its own page), then the notes — under chapter subheads
    when there are chapters to group by."""
    rule = "=" * (level or 1)
    out = [f"{rule} Footnotes", ""]
    if not chapters:
        out.append(_note_block(list(enumerate(bodies, 1))))
        return "\n".join(out) + "\n"
    for idx, chapter in enumerate(chapters):
        items = groups.get(idx)
        if not items:
            continue
        out.append(f"{rule}= {chapter['title']}")
        out.append("")
        out.append(_note_block(items))
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# The preamble
# ---------------------------------------------------------------------------

def _mm(value: float) -> str:
    return f"{value:.4g}mm"


def _typ_string(text: str) -> str:
    """A typst string literal. `json.dumps` escapes exactly what typst
    escapes for the characters that can appear here (validate() already
    dropped control characters), and `ensure_ascii=False` keeps it from
    emitting `\\uXXXX`, which typst spells `\\u{XXXX}`."""
    return json.dumps(text, ensure_ascii=False)


def _chapter_query(level: int) -> str:
    """The running head's "use chapter name": the last chapter heading that
    started on or before this page."""
    return (f'{{ let hs = query(heading.where(level: {level}))'
            f'.filter(h => h.location().page() <= here().page()); '
            f'if hs.len() > 0 {{ hs.last().body }} else {{ [] }} }}')


def _header_content(field: dict[str, Any], level: int | None) -> str:
    if field.get("chapter") and level:
        return _chapter_query(level)
    text = field.get("text") or ""
    return f"[#({_typ_string(text)})]" if text else "[]"


def preamble(options: dict[str, Any], level: int | None = None) -> str:
    """Our `#set`/`#show` block: everything pandoc's dropped `conf` used to
    do, plus the page the user asked for. Written at the top of the body, so
    page one already has the right trim."""
    w, h = page_size_mm(options)
    font = options["font"]
    headers = options["headers"]
    imposed = options["layout"] != "single"

    if options["page_numbers"]:
        footer = ('context align(center)[#text(size: 9pt)'
                  '[#counter(page).display("1")]]')
    else:
        footer = "none"

    if not headers["enabled"]:
        header = "none"
    elif imposed:
        # Verso carries the left field, recto the right — the only layout
        # where two running heads mean anything.
        header = (f'context {{ if calc.odd(here().page()) '
                  f'{{ align(right)[#text(size: 9pt)'
                  f'[#{_header_content(headers["right"], level)}]] }} else '
                  f'{{ align(left)[#text(size: 9pt)'
                  f'[#{_header_content(headers["left"], level)}]] }} }}')
    else:
        header = (f'context align(left)[#text(size: 9pt)'
                  f'[#{_header_content(headers["left"], level)}]]')

    lines = [
        "// enough: paginate preamble",
        f"#set page(width: {_mm(w)}, height: {_mm(h)}, "
        f"margin: {_mm(options['margin_mm'])}, numbering: none,",
        f"  footer: {footer},",
        f"  header: {header})",
        f'#set text(font: {_typ_string(font)}, size: {BODY_SIZE_PT:g}pt, lang: "en")',
        "#set par(justify: true, leading: 0.65em)",
        "#set heading(numbering: none)",
    ]
    if level:
        lines.append(f"#show heading.where(level: {level}): "
                     f"it => pagebreak(weak: true) + it")
    return "\n".join(lines) + "\n"


def build_typ(pandoc_typ: str, options: dict[str, Any]) -> tuple[str, int]:
    """pandoc's standalone `.typ` → the one we compile. Returns the new source
    and the number of footnotes moved out of the flow (0 for `page`)."""
    head, body = split_template(pandoc_typ)
    level = chapter_level(body)
    moved = 0
    if options["footnotes"] in ("chapter", "book"):
        body, bodies, positions = extract_footnotes(body)
        body = place_endnotes(body, bodies, positions, options["footnotes"], level)
        moved = len(bodies)
    return f"{head}{preamble(options, level)}\n{body}", moved


# ---------------------------------------------------------------------------
# Footnote reconciliation (wave A owns the rules; this is the seam)
# ---------------------------------------------------------------------------

def renumber_source(text: str) -> str:
    """Numeric footnotes renumbered 1..N in order of appearance, per plan
    §2.5.1. Paginate time is one of the two moments renumbering is allowed to
    happen, and it is what makes the typeset numbering match the source."""
    try:
        from . import footnotes
    except ImportError:
        return text
    return footnotes.renumber(text)[0]


# ---------------------------------------------------------------------------
# The policy half of a run (mirrors `convert.export`)
# ---------------------------------------------------------------------------

def status(project_dir: Path, rel: str) -> dict[str, Any]:
    """What the modal needs: the font list and the size table come from here
    so the frontend hardcodes neither, plus whether the two engines are
    actually present on this machine."""
    from . import convert
    source = resolve_source(project_dir, rel)
    # Anything already paginated *from this document* — matched on the
    # manifest, not on the filename, because the export name is the user's to
    # choose and need not echo the source's.
    pdfs = sorted(
        p.name for p in source.parent.glob("*.pdf")
        if (read_viewer_manifest(p) or {}).get("source") == source.name)
    return {
        "path": rel,
        "name": source.stem,
        "fonts": list(FONTS),
        "fonts_bundled": fonts_bundled(),
        "sizes": sizes_view(),
        "defaults": dict(DEFAULTS),
        "typst": convert.typst_available(),
        "pandoc": convert.pandoc_path() is not None,
        "paginated": pdfs,
    }


def resolve_source(project_dir: Path, rel: str) -> Path:
    """The markdown to typeset. Containment is checked on the LOGICAL path,
    the same rule `server._resolve_project_path` applies, so an in-tree
    symlink pointing at a global default still works."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise PaginateError("invalid path", status=400)
    source = project_dir.resolve() / p
    if source.suffix.lower() not in (".md", ".markdown"):
        raise PaginateError(
            f"{source.name} is not a markdown file — pagination typesets "
            f"markdown", status=400)
    if not source.is_file():
        raise PaginateError(f"{source.name} does not exist", status=404)
    return source


def run_paginate(project_dir: Path, options: dict[str, Any],
                 *, when: dt.datetime | None = None) -> dict[str, Any]:
    """Validate, run the worker, answer the §2.3 response. Blocking — the
    endpoint calls it through `asyncio.to_thread`, exactly like export."""
    from . import convert

    opts = validate(options)
    source = resolve_source(project_dir, opts["path"])
    if not convert.pandoc_path():
        raise PaginateError(
            convert.engine_missing_message(convert.FORMATS[".docx"]), status=503)
    if not convert.typst_available():
        raise PaginateError(
            "typst could not be found in this environment — it ships with "
            "enough, so this means the Python environment is incomplete; "
            "re-run update-enough (or `uv sync`) to repair it", status=503)

    out = output_pdf(source, opts["name"], when)
    job = {"op": "paginate", "source": str(source), "out": str(out),
           "options": opts, "font_paths": font_paths()}
    try:
        result = convert.run_worker(job, timeout=600)
    except convert.ConvertError as e:
        raise PaginateError(str(e), status=e.status) from None

    root = project_dir.resolve()
    rel_pdf = str(Path(result["path"]).relative_to(root))
    viewer = result.get("viewer")
    return {
        "ok": True,
        "pdf": rel_pdf,
        "pages": result.get("pages", 0),
        "sheets": result.get("sheets", result.get("pages", 0)),
        "viewer": str(Path(viewer).relative_to(root)) if viewer else None,
        "name": out.name,
        "footnotes": opts["footnotes"],
        "layout": opts["layout"],
    }
