"""A scaffold exported as the thing it is (0.8, E6; pins 6; survey section 4).

Each export is a new file beside the composure, never one written over: `<name>.<ext>`, then `<name>-2.<ext>`,
`-3` … (`new_path`'s rule). What is made, by thing:

| thing | formats | how |
|---|---|---|
| page | `html`, `pdf` | HTML written directly, one self-contained file (styles inline, pictures as data URIs); PDF from typst generated from the state: each frame one page (US Letter wide, as tall as it needs), its boxes in rows and columns |
| deck | `pptx`, `pdf` | PPTX through pandoc (one slide per frame, two columns at most: pandoc's own layouts, not the scaffold's geometry; an optional reference deck for the look); PDF from generated typst at 16:9, one page per frame, boxes by row and column or by `place`, text shrunk to fit a slide rather than cut |
| document | `md`, `pdf` | Markdown by rule (below); PDF through pandoc to typst, the twins' route |

What goes in, read from the state (`scaffolder.state_from_composure`, the plectrum beside the composure supplying
each box's `as`):

- A box `as: notes`, and a frame of only notes boxes, are never exported (they are not part of the thing).
- A box `as: speaker` is a slide's speaker notes: the PPTX's notes, and nowhere else.
- A box with nothing in it (no words; a graphic with no picture) is left out, and named in the result's `left_out`.
- The person's words and nothing else: frame names (the plectrum's) and plecs never reach the thing. A `fixed`
  label and `chips` do (they are the thing's own fixed words), on a page.

Markdown by rule: `title` → `# `, `headline` → `## `, `deck` → `### `, `quote` → `> `, `caption` → `*…*`, `call`
→ `**…**`; everything else as written. A document with no title box opens with the composure's title as `# `.

The PDFs render out of the server's process: a child Python runs `typst.compile` with a time limit
(`RENDER_TIMEOUT`), as the convert worker does for the twins. pandoc runs as its own process too.
"""
from __future__ import annotations

import base64
import html as _html
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import composure as C

#: What each thing exports as.
FORMATS: dict[str, tuple[str, ...]] = {"page": ("html", "pdf"), "deck": ("pptx", "pdf"),
                                       "document": ("md", "pdf")}
RENDER_TIMEOUT = 300.0
#: The pandoc reader for the person's markdown: GitHub's, so an `@name` is never a citation, with fenced divs for a
#: slide's columns and notes.
PANDOC_FROM = "gfm+fenced_divs"
#: A picture larger than this is left out of a self-contained HTML page (named in `left_out`).
MAX_INLINE_IMAGE = 8 * 1024 * 1024
#: pandoc's PPTX layouts hold two columns; a row of more is folded into two.
PPTX_COLUMNS = 2
#: A slide's type is the page's, this much larger (a slide is read across a room).
DECK_SCALE = 2.0


class ExportError(Exception):
    """A refusal with the HTTP status the route answers with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# What is exported: the state, read for the thing
# ---------------------------------------------------------------------------

@dataclass
class Box:
    id: str
    name: str
    as_: str
    kind: str
    text: str
    row: int
    col: int
    place: str | None = None
    picture: Path | None = None
    fixed: str | None = None
    chips: list[str] = field(default_factory=list)


@dataclass
class Frame:
    id: str
    name: str
    rows: list[list[Box]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def boxes(self) -> list[Box]:
        return [b for row in self.rows for b in row]


@dataclass
class Thing:
    kind: str
    title: str
    lang: str
    frames: list[Frame]
    left_out: list[dict[str, str]]


def _resolve_picture(project_dir: Path | None, href: str | None) -> Path | None:
    if not href or project_dir is None:
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
        return None
    p = (project_dir / href).resolve()
    try:
        p.relative_to(project_dir.resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def read_thing(comp_path: Path, project_dir: Path | None = None) -> Thing:
    """The scaffold as it will be exported."""
    from . import scaffolder as SC
    comp = C.load(comp_path)
    view = C.scaffold_view(comp)
    if view is None:
        raise ExportError(f"{comp_path.name} is not a scaffold, so it has no thing to export.")
    plectrum = None
    pp = SC.plectrum_path(comp_path)
    if pp.is_file():
        try:
            plectrum = SC.loads(pp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a plectrum that does not read only loses the `as` of each box
            plectrum = None
    try:
        state = SC.state_from_composure(comp, plectrum)
    except Exception as e:  # noqa: BLE001 - the parser's StateError, said in its words
        raise ExportError(f"the scaffold could not be read for export: {e}") from None
    frames: list[Frame] = []
    left_out: list[dict[str, str]] = []
    for f in state.frames:
        if all(b["as"] == "notes" for b in f["boxes"]):
            continue
        frame = Frame(id=f["id"], name=f["name"])
        rows: dict[int, list[Box]] = {}
        for b in f["boxes"]:
            if b["as"] == "notes":
                continue
            m = comp.module(b["id"]) or comp.module(SC.module_id(b["id"]))
            text = (b.get("text") or "").strip("\n")
            if b["as"] == "speaker":
                if text.strip():
                    frame.notes.append(text)
                continue
            picture = None
            if b["kind"] == "graphic":
                picture = _resolve_picture(project_dir, (m.href if m is not None else None) or b.get("href"))
                if picture is None:
                    left_out.append({"box": b["id"], "name": b["name"], "why": "no picture in it"})
                    continue
            elif not text.strip():
                left_out.append({"box": b["id"], "name": b["name"], "why": "nothing written in it"})
                continue
            rows.setdefault(int(b["row"] or 1), []).append(Box(
                id=b["id"], name=b["name"], as_=b["as"] or "body", kind=b["kind"], text=text,
                row=int(b["row"] or 1), col=int(b["col"] or 1), place=b.get("place"), picture=picture,
                fixed=b.get("fixed"), chips=list(b.get("chips") or [])))
        frame.rows = [sorted(rows[r], key=lambda x: x.col) for r in sorted(rows)]
        if frame.rows or frame.notes:
            frames.append(frame)
    return Thing(kind=view["thing"], title=comp.title, lang=comp.lang or "en", frames=frames, left_out=left_out)


# ---------------------------------------------------------------------------
# Markdown by rule
# ---------------------------------------------------------------------------

def _oneline(text: str) -> str:
    return " ".join(text.split())


def _role_markdown(b: Box) -> str:
    t = b.text.strip()
    if b.as_ == "title":
        return f"# {_oneline(t)}"
    if b.as_ == "headline":
        return f"## {_oneline(t)}"
    if b.as_ == "deck":
        return f"### {_oneline(t)}"
    if b.as_ == "quote":
        return "\n".join(f"> {line}" if line.strip() else ">" for line in t.splitlines())
    if b.as_ == "caption":
        return f"*{_oneline(t)}*"
    if b.as_ == "call":
        return f"**{_oneline(t)}**"
    return t


def box_markdown(b: Box, core: str | None = None) -> str:
    """One box as markdown, by its `as`, with its fixed label before it and its chips after (both exported as
    they are, never the person's to write)."""
    parts = [b.fixed] if b.fixed else []
    parts.append(_role_markdown(b) if core is None else core)
    if b.chips:
        parts.append(" \u00b7 ".join(b.chips))
    return "\n\n".join(p for p in parts if p)


def document_markdown(thing: Thing, picture_ref: Any = None) -> str:
    """The document's Markdown: every box in reading order, by rule. `picture_ref(path)` gives the reference a
    picture is written with (the default: the path as given)."""
    parts: list[str] = []
    if not any(b.as_ == "title" for f in thing.frames for b in f.boxes()):
        parts.append(f"# {_oneline(thing.title)}")
    for f in thing.frames:
        for b in f.boxes():
            if b.kind == "graphic" and b.picture is not None:
                ref = picture_ref(b.picture) if picture_ref else str(b.picture)
                parts.append(f"![]({ref})")
            else:
                parts.append(box_markdown(b))
    return "\n\n".join(p for p in parts if p.strip()) + "\n"


# ---------------------------------------------------------------------------
# Writing beside the composure
# ---------------------------------------------------------------------------

def out_path(comp_path: Path, ext: str) -> Path:
    """`garden.comp` → `garden.<ext>`, then `garden-2.<ext>` …: a new file, never one written over."""
    stem = comp_path.name[: -len(C.SUFFIX)]
    candidate = comp_path.with_name(f"{stem}.{ext}")
    n = 2
    while candidate.exists():
        candidate = comp_path.with_name(f"{stem}-{n}.{ext}")
        n += 1
        if n > 999:  # pragma: no cover
            raise ExportError("too many exports of this scaffold beside it; move some away first.")
    return candidate


def _write_new(path: Path, data: bytes) -> None:
    """Write `path` only if it does not exist yet (exclusive create), so a race never overwrites."""
    with open(path, "xb") as fh:
        fh.write(data)


def _pandoc() -> str:
    from .convert import pandoc_path
    exe = pandoc_path()
    if not exe:
        raise ExportError("pandoc is not available in this environment (it ships with enough: run update-enough "
                          "to repair it)", status=503)
    return exe


def _run(args: list[str], *, cwd: Path, timeout: float = RENDER_TIMEOUT, what: str = "pandoc") -> str:
    try:
        out = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ExportError(f"{what} took longer than {int(timeout)} seconds and was stopped", status=504) from None
    except OSError as e:
        raise ExportError(f"{what} could not run: {e}", status=503) from None
    if out.returncode != 0:
        tail = (out.stderr or out.stdout or "").strip().splitlines()[-6:]
        raise ExportError(f"{what} failed: {' '.join(tail) or 'no message'}", status=500)
    return out.stdout


_TYPST_COMPILE = ("import sys, typst\n"
                  "typst.compile(sys.argv[1], output=sys.argv[2], root=sys.argv[3])\n")


def compile_typst(source: str, out: Path, root: Path) -> None:
    """Typeset `source` into the PDF `out`, in a child Python with a time limit. `root` is where a picture's
    `/path` is read from (the project). The `.typ` is written beside `out` and removed after."""
    fd, typ_name = tempfile.mkstemp(prefix=f".{out.stem}.", suffix=".typ", dir=str(out.parent))
    typ = Path(typ_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(source)
        tmp_out = out.with_name(f".{out.name}.part")
        _run([sys.executable, "-c", _TYPST_COMPILE, str(typ), str(tmp_out), str(root)], cwd=out.parent,
             what="typst")
        try:
            os.link(tmp_out, out)          # fails if `out` appeared meanwhile: never written over
        except FileExistsError:
            raise ExportError(f"{out.name} appeared while it was being written; export again", status=409) from None
        except OSError:
            if out.exists():
                raise ExportError(f"{out.name} appeared while it was being written; export again",
                                  status=409) from None
            os.replace(tmp_out, out)
    finally:
        typ.unlink(missing_ok=True)
        out.with_name(f".{out.name}.part").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Typst from the state
# ---------------------------------------------------------------------------

_SEP = "ENOUGHSCAFFOLDBOXSEP"


def _typst_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def markdown_to_typst(texts: list[str], cwd: Path) -> list[str]:
    """Each markdown text as typst markup, in one pandoc run (the texts joined by marker paragraphs and split
    again after). Never headings: a box's look comes from its `as`, not from the person's `#`."""
    if not texts:
        return []
    joined = "\n\n".join(f"{t}\n\n{_SEP}{i:04d}" for i, t in enumerate(texts))
    out = subprocess.run([_pandoc(), "-f", PANDOC_FROM, "-t", "typst", "--wrap=none"], input=joined, cwd=str(cwd),
                         capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    if out.returncode != 0:
        raise ExportError(f"pandoc failed: {(out.stderr or '').strip()[-400:]}", status=500)
    parts: list[str] = []
    current: list[str] = []
    for line in out.stdout.splitlines():
        if re.fullmatch(rf"{_SEP}\d{{4}}", line.strip()):
            parts.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    if len(parts) != len(texts):
        raise ExportError("the text could not be set for the PDF (pandoc's output did not split back)", status=500)
    return parts


#: The look of a box by its `as`: (size in points on a page, weight, style, extra).
_LOOK = {
    "title": (30, "bold", "normal"), "headline": (21, "bold", "normal"), "deck": (15, "regular", "italic"),
    "lede": (13, "regular", "normal"), "call": (13, "bold", "normal"), "caption": (9, "regular", "italic"),
    "quote": (12, "regular", "italic"),
}


def _typst_box(b: Box, body: str, scale: float) -> str:
    size, weight, style = _LOOK.get(b.as_, (11, "regular", "normal"))
    if b.kind == "graphic" and b.picture is not None:
        return f"#image({_typst_string('/' + str(b._rel))}, width: 100%)"   # type: ignore[attr-defined]
    content = f"#text(size: {size * scale:.1f}pt, weight: \"{weight}\", style: \"{style}\")[{body}]"
    if b.fixed:
        content = f"#text(size: {8 * scale:.1f}pt, fill: luma(110))[#{_typst_string(b.fixed)}]\n\n" + content
    if b.chips:
        chips = " ".join(f"#box(stroke: 0.5pt + luma(150), inset: 4pt, radius: 3pt)[#{_typst_string(c)}]"
                         for c in b.chips)
        content += f"\n\n{chips}"
    if b.as_ == "quote":
        return f"#block(stroke: (left: 2pt + luma(160)), inset: (left: 10pt, y: 4pt))[{content}]"
    if b.as_ == "tile":
        return f"#block(fill: luma(244), inset: 10pt, radius: 4pt, width: 100%)[{content}]"
    return f"#block(width: 100%)[{content}]"


def _typst_rows(frame: Frame, bodies: dict[str, str], scale: float, gap: float) -> str:
    out: list[str] = []
    for row in frame.rows:
        cells = [f"[{_typst_box(b, bodies.get(b.id, ''), scale)}]" for b in row]
        cols = ", ".join(["1fr"] * len(row))
        out.append(f"#grid(columns: ({cols},), column-gutter: {gap:.0f}pt, {', '.join(cells)})")
    return f"\n#v({gap * 0.7:.0f}pt)\n".join(out)


def _place_box(b: Box, body: str, scale: float) -> str | None:
    """A box with `place` (percent: left top width height) put where the person put it on the slide."""
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", b.place or "")]
    if len(nums) != 4:
        return None
    left, top, width, height = nums
    return (f"#place(top + left, dx: {left}%, dy: {top}%, "
            f"block(width: {width}%, height: {height}%)[{_typst_box(b, body, scale)}])")


_FIT = """#let fit(body) = layout(size => {
  let h = measure(block(width: size.width, body)).height
  if h <= size.height { body } else {
    let k = size.height / h * 100%
    scale(x: k, y: k, origin: top + left, reflow: true, body)
  }
})
"""


def thing_typst(thing: Thing, *, cwd: Path, project_dir: Path | None) -> str:
    """The typst for a page (one US-Letter-wide page per frame, as tall as it needs) or a deck (one 16:9 page
    per frame, the slide's words shrunk to fit it, never cut)."""
    boxes = [b for f in thing.frames for b in f.boxes()]
    for b in boxes:
        if b.picture is not None:
            root = (project_dir or b.picture.parent).resolve()
            b._rel = b.picture.resolve().relative_to(root).as_posix()   # type: ignore[attr-defined]
    texts = [b for b in boxes if b.kind != "graphic"]
    bodies = dict(zip((b.id for b in texts), markdown_to_typst([b.text for b in texts], cwd)))
    lang = re.sub(r"[^a-z]", "", (thing.lang or "en").lower()[:2]) or "en"
    head = [f"#set document(title: {_typst_string(thing.title)})", f"#set text(lang: \"{lang}\")",
            "#set par(justify: false)"]
    pages: list[str] = []
    if thing.kind == "deck":
        head.append("#set page(width: 13.333in, height: 7.5in, margin: 0.55in)")
        head.append(_FIT)
        for f in thing.frames:
            if not f.rows:
                continue
            placed = [_place_box(b, bodies.get(b.id, ""), DECK_SCALE) for b in f.boxes() if b.place]
            if placed and all(placed):
                pages.append("\n".join(placed))
            else:
                pages.append(f"#block(height: 100%, width: 100%)[#fit[\n{_typst_rows(f, bodies, DECK_SCALE, 28)}\n]]")
    else:
        head.append("#set page(width: 8.5in, height: auto, margin: 0.75in)")
        for f in thing.frames:
            if f.rows:
                pages.append(_typst_rows(f, bodies, 1.0, 18))
    if not pages:
        raise ExportError("there is nothing written in this scaffold to export yet.", status=409)
    return "\n".join(head) + "\n\n" + "\n\n#pagebreak()\n\n".join(pages) + "\n"


# ---------------------------------------------------------------------------
# HTML, written directly
# ---------------------------------------------------------------------------

_HTML_STYLE = """
:root { color-scheme: light dark; --ink: #1d1d1f; --paper: #fff; --soft: #6e6e73; --tile: #f3f3f5; --line: #d2d2d7; }
@media (prefers-color-scheme: dark) { :root { --ink: #f5f5f7; --paper: #161617; --soft: #a1a1a6; --tile: #232325;
  --line: #3a3a3c; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 17px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }
section.frame { padding: 28px 0; border-bottom: 1px solid var(--line); }
section.frame:last-child { border-bottom: 0; }
.row { display: grid; gap: 24px; margin: 0 0 20px; }
.box > :first-child { margin-top: 0; } .box > :last-child { margin-bottom: 0; }
.as-title { font-size: 2.4em; font-weight: 700; line-height: 1.15; }
.as-headline { font-size: 1.6em; font-weight: 700; line-height: 1.2; }
.as-deck { font-size: 1.2em; font-style: italic; color: var(--soft); }
.as-lede { font-size: 1.15em; }
.as-call { font-size: 1.1em; font-weight: 700; }
.as-caption { font-size: .85em; font-style: italic; color: var(--soft); }
.as-quote { border-left: 3px solid var(--line); padding-left: 16px; font-style: italic; }
.as-tile { background: var(--tile); border-radius: 10px; padding: 16px; }
.fixed { font-size: .8em; color: var(--soft); text-transform: uppercase; letter-spacing: .04em; margin: 0 0 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.chip { border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; font-size: .9em; }
img { max-width: 100%; height: auto; display: block; border-radius: 6px; }
@media (max-width: 640px) { .row { grid-template-columns: 1fr !important; } }
"""


def _data_uri(path: Path) -> str | None:
    if path.stat().st_size > MAX_INLINE_IMAGE:
        return None
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        return None
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def page_html(thing: Thing) -> str:
    """The page as one self-contained HTML file: frames as bands, rows as grids, pictures inline."""
    esc = _html.escape
    out = ["<!doctype html>", f'<html lang="{esc(thing.lang or "en")}">', "<head>", '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>{esc(thing.title)}</title>", f"<style>{_HTML_STYLE}</style>", "</head>", "<body>", "<main>"]
    for f in thing.frames:
        if not f.rows:
            continue
        out.append(f'<section class="frame" id="{esc(f.id)}">')
        for row in f.rows:
            out.append(f'<div class="row" style="grid-template-columns: repeat({len(row)}, 1fr)">')
            for b in row:
                inner: list[str] = []
                if b.fixed:
                    inner.append(f'<p class="fixed">{esc(b.fixed)}</p>')
                if b.kind == "graphic" and b.picture is not None:
                    uri = _data_uri(b.picture)
                    if uri is None:
                        thing.left_out.append({"box": b.id, "name": b.name,
                                               "why": "the picture is too large or not an image for one HTML file"})
                        continue
                    inner.append(f'<img src="{uri}" alt="{esc(b.name)}">')
                else:
                    inner.append(C.md_to_rich(b.text))
                if b.chips:
                    inner.append('<div class="chips">' + "".join(f'<span class="chip">{esc(c)}</span>'
                                                                 for c in b.chips) + "</div>")
                out.append(f'<div class="box as-{esc(b.as_)}" id="{esc(b.id)}">{"".join(inner)}</div>')
            out.append("</div>")
        out.append("</section>")
    out += ["</main>", "</body>", "</html>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# The deck's PPTX, through pandoc
# ---------------------------------------------------------------------------

def deck_markdown(thing: Thing) -> str:
    """The deck as pandoc slide markdown: one slide per frame. The slide's title is its first title or headline
    box; a slide with none starts with a rule. A row of two or more boxes becomes two columns (pandoc's layouts
    hold two, so a wider row is folded: the first half left, the rest right; the full-width rows go left). A single
    picture with at most one caption becomes a captioned picture; a picture beside text, two columns. Speaker boxes
    are the slide's notes."""
    slides: list[str] = []
    head = ""
    frames = list(thing.frames)
    cover = _cover(frames[0]) if frames else None
    if cover is not None:
        # The first frame holds the deck's title and at most a line or two of words: pandoc's title slide.
        title, sub = cover
        head = "---\n" + f"title: {_yaml_str(title)}\n" + (f"subtitle: {_yaml_str(sub)}\n" if sub else "") + "---"
        if frames[0].notes:
            head += "\n\n::: notes\n" + "\n\n".join(frames[0].notes) + "\n:::"
        frames = frames[1:]
    for f in frames:
        boxes = f.boxes()
        if not boxes and not f.notes:
            continue
        title = next((b for b in boxes if b.as_ in ("title", "headline")), None)
        rest = [b for b in boxes if b is not title]
        parts: list[str] = [f"## {_oneline(title.text)}" if title else "---"]
        pics = [b for b in rest if b.kind == "graphic" and b.picture is not None]
        words = [b for b in rest if b not in pics]

        def md(b: Box) -> str:
            if b.kind == "graphic" and b.picture is not None:
                return f"![]({b.picture.as_posix()})"
            return box_markdown(b, f"**{_oneline(b.text)}**" if b.as_ in ("title", "headline") else None)

        if len(pics) == 1 and len(words) <= 1 and (not words or len(_oneline(words[0].text)) <= 200):
            alt = _oneline(words[0].text).replace("[", "(").replace("]", ")") if words else ""
            parts.append(f"![{alt}]({pics[0].picture.as_posix()})")
        elif pics and words:
            parts.append(_columns([[md(b) for b in pics], [md(b) for b in words]]))
        elif any(len(row) > 1 for row in f.rows):
            left: list[str] = []
            right: list[str] = []
            for row in f.rows:
                row = [b for b in row if b is not title]
                if len(row) == 1:
                    left.append(md(row[0]))
                elif row:
                    half = (len(row) + 1) // 2
                    left += [md(b) for b in row[:half]]
                    right += [md(b) for b in row[half:]]
            parts.append(_columns([left, right]))
        else:
            parts += [md(b) for b in rest]
        if f.notes:
            parts.append("::: notes\n" + "\n\n".join(f.notes) + "\n:::")
        slides.append("\n\n".join(p for p in parts if p))
    if not slides and not head:
        raise ExportError("there is nothing written in this scaffold to export yet.", status=409)
    return "\n\n".join([head] * bool(head) + slides) + "\n"


def _cover(frame: Frame) -> tuple[str, str] | None:
    boxes = frame.boxes()
    title = next((b for b in boxes if b.as_ == "title"), None)
    rest = [b for b in boxes if b is not title]
    if title is None or len(rest) > 2 or any(b.kind == "graphic" for b in rest):
        return None
    return _oneline(title.text), " \u2014 ".join(_oneline(b.text) for b in rest)


def _yaml_str(s: str) -> str:
    import json
    return json.dumps(s, ensure_ascii=False)


def _columns(cols: list[list[str]]) -> str:
    blocks = ["::: column\n" + "\n\n".join(col) + "\n:::" for col in cols if col]
    return ":::::: columns\n" + "\n".join(blocks) + "\n::::::"


# ---------------------------------------------------------------------------
# The door
# ---------------------------------------------------------------------------

def export(comp_path: Path, as_: str, *, project_dir: Path | None = None,
           reference: Path | None = None) -> dict[str, Any]:
    """Export the scaffold at `comp_path` as `as_` (`html`, `pdf`, `pptx` or `md`, by its thing: `FORMATS`).
    Returns `{written, path, as, thing, bytes, left_out, locked, pages?}`."""
    as_ = (as_ or "").strip().lower().lstrip(".")
    comp = C.load(comp_path)
    view = C.scaffold_view(comp)
    if view is None:
        raise ExportError(f"{comp_path.name} is not a scaffold, so it has no thing to export.")
    offered = FORMATS[view["thing"]]
    if as_ not in offered:
        raise ExportError(f"a {view['thing']} exports as {' or '.join(offered)}, not {as_ or '(nothing)'}.")
    thing = read_thing(comp_path, project_dir)
    if not any(f.rows for f in thing.frames) and as_ != "pptx":
        raise ExportError("there is nothing written in this scaffold to export yet.", status=409)
    root = (project_dir or comp_path.parent).resolve()
    out = out_path(comp_path, as_)
    pages: int | None = None
    if as_ == "html":
        _write_new(out, page_html(thing).encode("utf-8"))
    elif as_ == "md":
        def ref(p: Path) -> str:
            return os.path.relpath(p, comp_path.parent).replace(os.sep, "/")
        _write_new(out, document_markdown(thing, ref).encode("utf-8"))
    elif as_ == "pptx":
        if reference is not None and not reference.is_file():
            raise ExportError(f"no reference deck at {reference.name}", status=404)
        md = deck_markdown(thing)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{out.stem}.", suffix=".md", dir=str(out.parent))
        tmp_out = out.with_name(f".{out.name}.part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(md)
            args = [_pandoc(), "-f", PANDOC_FROM + "+yaml_metadata_block", "-t", "pptx", "--slide-level=2", f"--resource-path={root}",
                    "-o", str(tmp_out), tmp_name]
            if reference is not None:
                args.insert(-3, f"--reference-doc={reference}")
            _run(args, cwd=out.parent)
            _write_new(out, tmp_out.read_bytes())
        finally:
            Path(tmp_name).unlink(missing_ok=True)
            tmp_out.unlink(missing_ok=True)
    else:  # pdf
        if thing.kind == "document":
            md = document_markdown(thing, lambda p: "/" + p.resolve().relative_to(root).as_posix())
            source = _document_typst(md, cwd=out.parent)
        else:
            source = thing_typst(thing, cwd=out.parent, project_dir=root)
        compile_typst(source, out, root)
        pages = _page_count(out)
    result: dict[str, Any] = {"written": out.name, "path": str(out), "as": as_, "thing": thing.kind,
                              "bytes": out.stat().st_size, "left_out": thing.left_out,
                              "locked": C.scaffold_locked(comp)}
    if pages is not None:
        result["pages"] = pages
    return result


def _document_typst(md: str, *, cwd: Path) -> str:
    """The twins' route for a document: markdown → `pandoc -t typst --standalone` (the document's own `# `
    title is its first line, so no title is added)."""
    out = subprocess.run([_pandoc(), "-f", PANDOC_FROM, "-t", "typst", "--standalone", "--wrap=none"],
                         input=md, cwd=str(cwd), capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    if out.returncode != 0:
        raise ExportError(f"pandoc failed: {(out.stderr or '').strip()[-400:]}", status=500)
    return out.stdout


def _page_count(pdf: Path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf)).pages)
    except Exception:  # noqa: BLE001 - the count is a courtesy
        return None


__all__ = ["ExportError", "FORMATS", "Thing", "box_markdown", "compile_typst", "deck_markdown", "document_markdown",
           "export", "out_path", "page_html", "read_thing", "thing_typst"]
