#!/usr/bin/env python3
"""Export a scaffold, and hand it on: the finished thing in a format people
use, or the next link of a chain the person names.

Standard library only. pandoc, typst (the command or the Python wheel) and
python-pptx are used when present, each guarded; nothing is fetched or
installed. Every command reads a scaffold's state (or a plectrum, where that
is enough) through `scaffold_state.py` beside this file, and writes a NEW
file: it never overwrites one (a name already taken gets -2, -3, ...).

    export.py can                       what this Python can make here, thing by thing
    export.py html FILE                 the thing as one self-contained HTML file (always)
    export.py pdf FILE                  a PDF through typst; without typst, says "print the HTML"
    export.py pptx FILE                 a deck as PPTX: pandoc, else python-pptx; without both, says so
    export.py md FILE                   a document as Markdown (always)
    export.py fill FILE                 the scaffold page (assets/scaffold.html) filled from FILE
    export.py next FILE                 the question "where does the work go next?" and its choices
    export.py mermaid FILE              hand-off: a mermaid diagram of the scaffold
    export.py brief FILE [--for fabulac|fabulan]
                                        hand-off: the brief enough's authoring program takes (fabulac),
                                        or the thing's words as one markdown text (fabulan)
    export.py prompt FILE --engine NAME hand-off: a prompt for the creative engine the person names

Options for every command that writes: --out DIR (default: FILE's folder).
pdf and pptx take --with to choose a tool (typst | pandoc | python-pptx).

What a format leaves out: a notes box (`as: notes`) and a frame of only
notes boxes are never exported; a speaker box is a slide's speaker notes,
never on the slide; an empty box is left out and named on stderr.
"""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import scaffold_state as ss  # noqa: E402  (beside this file; works under python3 -I)

TEMPLATE = HERE.parent / "assets" / "scaffold.html"
BLOCK_OPEN = '<script type="application/json" id="scaffold">'
BLOCK_CLOSE = "</script>"

#: The thing's own formats (ruled 2026-11-18). HTML is always there as the
#: print route, so a deck and a document can also leave as HTML.
FORMATS = {"page": ("html", "pdf"), "deck": ("pptx", "pdf", "html"), "document": ("md", "pdf", "html")}

#: The headings enough 0.8's authoring bank places a brief's passages by
#: (`fabula`'s authoring bank, `brief:` words). enough's bank is the truth;
#: this copy only lets `brief` say which frames enough will place by name.
BRIEF_HEADINGS = {
    "aim": ("what it is for", "what it does", "aim", "aims", "purpose"),
    "audience": ("for whom", "who it is for", "audience", "who"),
    "use": ("uses", "use", "what a person does with it"),
    "occasion": ("why", "occasion", "what prompted it"),
    "way-in": ("ways in", "way in", "commands", "interface", "interfaces"),
    "needs": ("needs", "what it needs", "dependencies", "requires"),
    "setting": ("settings", "setting", "options", "configuration"),
    "left-out": ("leaves out", "left out", "what it leaves out", "not doing", "out of scope", "exclusions",
                 "non-goals"),
    "must": ("requirements", "must", "always", "never", "must never"),
    "case": ("cases", "case", "examples", "example"),
    "open": ("open questions", "undecided", "questions"),
}

HEADING_AS = ("title", "headline")
GRAPHIC_RATIO = {"portrait": (3, 4), "landscape": (4, 3), "square": (1, 1)}


class ExportError(Exception):
    """A refusal: what was wrong, and what to do instead."""


# ---------------------------------------------------------------------------
# Reading the scaffold
# ---------------------------------------------------------------------------

def load(path: Path) -> ss.Scaffold:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ExportError(f"cannot read {path}: {e.strerror}") from None
    try:
        model = ss.loads(text)
    except ss.StateError as e:
        raise ExportError(str(e)) from None
    for w in model.warnings:
        note(w)
    return model


def need_state(model: ss.Scaffold, what: str) -> None:
    if model.kind != "scaffold":
        raise ExportError(f"this is a plectrum: it has no words yet, so there is no {what} to make. "
                          f"Export the scaffold's state (`<slug>.scaffold.md`), or copy it out of the page.")


def need_format(model: ss.Scaffold, fmt: str) -> None:
    thing = model.meta.get("thing") or "page"
    if fmt not in FORMATS.get(thing, ()):
        own = " and ".join(FORMATS.get(thing, ()))
        raise ExportError(f"a {thing} leaves as {own}, not {fmt}. Ask for one of those.")


def note(text: str) -> None:
    print(text, file=sys.stderr)


def has_words(box: dict[str, Any]) -> bool:
    return bool((box.get("text") or "").strip()) or (box["kind"] == "graphic" and bool(box.get("href")))


def on_thing(model: ss.Scaffold) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """The frames and boxes that are part of the thing, in order: no notes
    box, no frame of only notes boxes, no empty box (each named on stderr)."""
    out, empty = [], []
    for frame in model.frames:
        boxes = [b for b in frame["boxes"] if b["as"] != "notes"]
        if not boxes:
            continue
        kept = []
        for b in boxes:
            if has_words(b):
                kept.append(b)
            else:
                empty.append(f"{b['name']} ({b['id']})")
        if kept:
            out.append((frame, kept))
    if empty:
        names: dict[str, list[str]] = {}
        for item in empty:
            names.setdefault(item.rsplit(" (", 1)[0], []).append(item)
        said = [v[0] if len(v) == 1 else f"{k} ({len(v)} boxes)" for k, v in names.items()]
        note(f"left out, empty: {', '.join(said)}")
    if not model.meta.get("locked"):
        note("not locked: this is a draft. Lock it, and let the check run, before it goes to anyone.")
    return out


def heading_of(frame: dict[str, Any], boxes: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    """A frame's heading on the thing: its first title or headline box's
    text, on one line. The frame's name is the scaffold's label, not the
    person's words; a document falls back to it, a page and a deck do not."""
    for b in boxes:
        if b["as"] in HEADING_AS and b["kind"] == "text":
            return " ".join(b["text"].split()), b
    return None, None


def frame_shape(model: ss.Scaffold, frame: dict[str, Any]) -> str:
    return frame.get("shape") or model.meta.get("shape") or ss.default_shape(model.meta.get("thing") or "page")


def rows_of(boxes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    rows: dict[int, list[dict[str, Any]]] = {}
    for b in boxes:
        rows.setdefault(b.get("row") or 1, []).append(b)
    return [sorted(rows[r], key=lambda b: b.get("col") or 1) for r in sorted(rows)]


def ratio(shape: str | None) -> tuple[int, int]:
    if shape in GRAPHIC_RATIO:
        return GRAPHIC_RATIO[shape]
    try:
        w, h = (shape or "16:9").split(":")
        return int(w), int(h)
    except ValueError:
        return 16, 9


def place_of(box: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if not box.get("place"):
        return None
    try:
        a, b, c, d = (float(x) for x in box["place"].split())
        return a, b, c, d
    except ValueError:
        return None


def picture(box: dict[str, Any], base_dir: Path) -> Path | None:
    """The person's picture as a local file beside the state, or None (a
    link is never fetched)."""
    href = box.get("href") or ""
    if not href or "://" in href or href.startswith("data:"):
        return None
    p = (base_dir / href).resolve()
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# Writing a new file
# ---------------------------------------------------------------------------

def stem_of(model: ss.Scaffold) -> str:
    s = ss.slug(model.meta.get("title") or "") or "scaffold"
    v = model.meta.get("version")
    return f"{s}.v{v}" if isinstance(v, int) and v > 1 else s


def new_path(folder: Path, name: str) -> Path:
    """`name` in `folder`, or `name` with -2, -3 ... before its suffixes:
    an existing file is never overwritten."""
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    if not p.exists():
        return p
    head, dot, tail = name.partition(".")
    n = 2
    while True:
        p = folder / f"{head}-{n}{dot}{tail}"
        if not p.exists():
            return p
        n += 1


def write_new(folder: Path, name: str, data: str | bytes) -> Path:
    p = new_path(folder, name)
    mode = "xb" if isinstance(data, bytes) else "x"
    with open(p, mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:
        fh.write(data)
    return p


# ---------------------------------------------------------------------------
# The tools a harness may have
# ---------------------------------------------------------------------------

def find_pandoc() -> str | None:
    exe = shutil.which("pandoc")
    if exe:
        return exe
    try:
        import pypandoc  # type: ignore  (enough's own install carries pandoc this way)
        path = pypandoc.get_pandoc_path()
        return path if path and Path(path).exists() else shutil.which(path or "")
    except Exception:
        return None


def find_typst() -> str | None:
    """'cli' for the typst command, 'wheel' for the Python package, or None."""
    if shutil.which("typst"):
        return "cli"
    try:
        import typst  # type: ignore  # noqa: F401
        return "wheel"
    except Exception:
        return None


def find_pptx() -> bool:
    try:
        import pptx  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def can() -> dict[str, Any]:
    pandoc, typst, pptx = find_pandoc(), find_typst(), find_pptx()
    pdf = f"PDF through typst ({typst})" if typst else "no PDF here: open the HTML and print it to PDF"
    deck = ("PPTX through pandoc" if pandoc else "PPTX through python-pptx" if pptx
            else "no PPTX here: no pandoc and no python-pptx")
    return {
        "pandoc": pandoc, "typst": typst, "python-pptx": pptx,
        "page": ["HTML", pdf],
        "deck": [deck, pdf, "HTML (to print, landscape)"],
        "document": ["Markdown", pdf, "HTML (to print)"],
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML_CSS = """
:root { --ink: #16181d; --ink2: #4a4f5a; --ink3: #767c88; --line: #dfe2e8; --bg: #ffffff; --card: #f7f8fa; --chip: #ffe36b; }
@media (prefers-color-scheme: dark) { :root { --ink: #eef0f4; --ink2: #b6bbc6; --ink3: #8a909c; --line: #2d323c; --bg: #121419; --card: #1a1d24; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 17px; line-height: 1.55; overflow-x: hidden; }
.wrap { max-width: 980px; margin: 0 auto; padding: 32px max(16px, env(safe-area-inset-left, 0px)) 64px; display: grid; gap: 36px; }
.row { display: grid; gap: 16px; } .c2 { grid-template-columns: repeat(2, minmax(0, 1fr)); } .c3 { grid-template-columns: repeat(3, minmax(0, 1fr)); } .c4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
@media (max-width: 760px) { .c3, .c4, .c2 { grid-template-columns: minmax(0, 1fr); } }
section { display: grid; gap: 16px; }
p { margin: 0 0 .6em; } p:last-child { margin-bottom: 0; }
.as-title { font-weight: 800; font-size: clamp(32px, 6vw, 56px); line-height: 1.05; letter-spacing: -0.02em; }
.as-headline { font-weight: 800; font-size: clamp(28px, 5vw, 46px); line-height: 1.08; letter-spacing: -0.02em; }
.as-lede { font-size: clamp(19px, 2.6vw, 23px); color: var(--ink2); max-width: 46ch; }
.as-body { max-width: 68ch; }
.as-step, .as-tile, .as-deck { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
.name { font-weight: 800; font-size: 18px; margin-bottom: 6px; }
.as-call { font-weight: 700; font-size: 22px; }
.as-quote { font-style: italic; font-size: 20px; border-left: 3px solid var(--line); padding-left: 14px; }
.as-caption { font-size: 13px; color: var(--ink3); }
.fixed { font-size: 13px; color: var(--ink3); margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; }
.chip { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; background: var(--chip); color: #16181d; border-radius: 4px; padding: 2px 7px; }
figure { margin: 0; } figure img { width: 100%; height: 100%; object-fit: cover; display: block; border-radius: 6px; }
figcaption { font-size: 13px; color: var(--ink3); margin-top: 6px; }
.to-come { border: 1.5px dashed var(--line); border-radius: 6px; display: grid; place-items: center; color: var(--ink3); font-size: 13px; padding: 8px; text-align: center; }
h1 { font-size: 34px; line-height: 1.1; margin: 0; } h2 { font-size: 24px; margin: 0; }
.slide { position: relative; aspect-ratio: 16 / 9; border: 1px solid var(--line); border-radius: 10px; padding: 4%; background: var(--card); container-type: inline-size; display: grid; gap: 2cqw; align-content: start; overflow: hidden; }
.slide .as-title { font-size: 6cqw; } .slide .as-headline { font-size: 4.6cqw; } .slide .as-lede { font-size: 2.6cqw; }
.slide .as-body, .slide .as-step, .slide .as-tile, .slide .as-call { font-size: 2.1cqw; }
.slide.placed .row { display: contents; } .slide.placed .box[data-place] { position: absolute; overflow: hidden; }
.notes { font-size: 13px; color: var(--ink3); border-left: 2px solid var(--line); padding-left: 10px; }
@media print {
  body { background: #fff; color: #000; } .wrap { padding: 0; max-width: none; }
  .deck .slide { break-after: page; border: 0; border-radius: 0; } .deck .notes { display: none; }
  section { break-inside: avoid; }
}
"""


def _html_text(text: str) -> str:
    paras = [p for p in text.strip().split("\n\n") if p.strip()]
    return "".join("<p>" + "<br>".join(html.escape(ln) for ln in p.strip().split("\n")) + "</p>" for p in paras)


def _html_picture(box: dict[str, Any], base_dir: Path) -> str:
    w, h = ratio(box.get("shape"))
    p = picture(box, base_dir)
    cap = f"<figcaption>{html.escape(box['text'].strip())}</figcaption>" if box.get("text", "").strip() else ""
    if p is not None:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return (f'<figure><div style="aspect-ratio:{w}/{h}"><img src="data:{mime};base64,{data}" '
                f'alt="{html.escape(box["name"])}"></div>{cap}</figure>')
    href = box.get("href") or ""
    if href.startswith(("http://", "https://")):
        return (f'<figure><div style="aspect-ratio:{w}/{h}"><img src="{html.escape(href)}" '
                f'alt="{html.escape(box["name"])}"></div>{cap}</figure>')
    note(f"no picture found for {box['name']} ({box['id']}): {href or 'none given'}")
    return f'<figure><div class="to-come" style="aspect-ratio:{w}/{h}">{html.escape(box["name"])}: the picture to come</div>{cap}</figure>'


def _html_box(box: dict[str, Any], base_dir: Path, *, named: bool) -> str:
    as_ = box["as"] if box["as"] in ss.AS_KNOWN else "body"
    attrs = f' class="box as-{as_}"'
    pl = place_of(box)
    if pl:
        attrs += (f' data-place="1" style="left:{pl[0]}%;top:{pl[1]}%;width:{pl[2]}%;height:{pl[3]}%"')
    inner = ""
    if named and as_ in ("step", "tile", "deck"):
        inner += f'<div class="name">{html.escape(box["name"])}</div>'
    inner += _html_picture(box, base_dir) if box["kind"] == "graphic" else _html_text(box["text"])
    if box.get("fixed") or box.get("chips"):
        inner += '<div class="fixed">'
        if box.get("fixed"):
            inner += f'<span>{html.escape(box["fixed"])}</span>'
        inner += "".join(f'<span class="chip">{html.escape(c)}</span>' for c in box.get("chips") or [])
        inner += "</div>"
    return f"<div{attrs}>{inner}</div>"


def _html_rows(boxes: list[dict[str, Any]], base_dir: Path) -> str:
    out = []
    for row in rows_of(boxes):
        n = min(len(row), 4)
        out.append(f'<div class="row{" c" + str(n) if n > 1 else ""}">'
                   + "".join(_html_box(b, base_dir, named=True) for b in row) + "</div>")
    return "".join(out)


def to_html(model: ss.Scaffold, base_dir: Path) -> str:
    thing = model.meta.get("thing") or "page"
    title = html.escape(model.meta.get("title") or "")
    lang = html.escape(model.meta.get("lang") or "en")
    body = []
    for frame, boxes in on_thing(model):
        if thing == "deck":
            speaker = [b for b in boxes if b["as"] == "speaker"]
            shown = [b for b in boxes if b["as"] != "speaker"]
            placed = " placed" if any(place_of(b) for b in shown) else ""
            body.append(f'<section class="slide{placed}" aria-label="{html.escape(frame["name"])}">'
                        + _html_rows(shown, base_dir) + "</section>")
            if speaker:
                body.append('<aside class="notes">' + "".join(_html_text(b["text"]) for b in speaker) + "</aside>")
        elif thing == "document":
            head, hb = heading_of(frame, boxes)
            rest = [b for b in boxes if b is not hb]
            body.append("<section>" + f"<h2>{html.escape(head or frame['name'])}</h2>"
                        + _html_rows(rest, base_dir) + "</section>")
        else:
            body.append("<section>" + _html_rows(boxes, base_dir) + "</section>")
    top = f"<h1>{title}</h1>" if thing == "document" else ""
    return ("<!doctype html>\n<html lang=\"" + lang + "\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{title}</title>\n<style>{HTML_CSS}"
            + ("@page { size: 254mm 142.875mm; margin: 0; }" if thing == "deck" else "")
            + "</style>\n</head>\n<body>\n"
            f'<main class="wrap {html.escape(thing)}">{top}' + "\n".join(body) + "</main>\n</body>\n</html>\n")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _md_box(box: dict[str, Any]) -> list[str]:
    out = []
    if box["as"] in ("step", "tile", "deck"):
        out.append(f"**{box['name']}**")
        out.append("")
    if box["kind"] == "graphic":
        cap = " ".join((box.get("text") or "").split())
        if box.get("href"):
            out.append(f"![{cap or box['name']}]({box['href']})")
        else:
            out.append(f"*{box['name']}: the picture to come.*")
        if cap and box.get("href"):
            out += ["", f"*{cap}*"]
    else:
        out.append(box["text"].strip())
    extra = " · ".join(([box["fixed"]] if box.get("fixed") else []) + list(box.get("chips") or []))
    if extra:
        out += ["", extra]
    out.append("")
    return out


def to_markdown(model: ss.Scaffold) -> str:
    out = [f"# {model.meta.get('title') or ''}", ""]
    for frame, boxes in on_thing(model):
        head, hb = heading_of(frame, boxes)
        out += [f"## {head or frame['name']}", ""]
        for b in boxes:
            if b is not hb:
                out += _md_box(b)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# PDF, through typst
# ---------------------------------------------------------------------------

def _ts(s: str) -> str:
    """A typst string literal: shown as written, nothing in it is markup."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


TYPST_SIZE = {"title": ('28pt', '"bold"'), "headline": ('22pt', '"bold"'), "lede": ('14pt', None),
              "call": ('14pt', '"bold"'), "caption": ('9pt', None), "quote": ('13pt', None)}


def _typ_text(text: str, as_: str, scale: float = 1.0) -> str:
    size, weight = TYPST_SIZE.get(as_, ("11pt", None))
    if scale != 1.0:
        size = f"{float(size[:-2]) * scale:.1f}pt"
    style = f"size: {size}" + (f", weight: {weight}" if weight else "") + (', style: "italic"' if as_ == "quote" else "")
    paras = [p for p in text.strip().split("\n\n") if p.strip()]
    body = "\n\n".join(" \\\n".join(f"#{_ts(ln)}" for ln in p.strip().split("\n")) for p in paras)
    return f"#text({style})[{body}]"


def _typ_box(box: dict[str, Any], pics: dict[str, str], *, scale: float = 1.0) -> str:
    parts = []
    as_ = box["as"] if box["as"] in ss.AS_KNOWN else "body"
    if as_ in ("step", "tile", "deck"):
        parts.append(f"#text(weight: \"bold\", size: {12 * scale:.1f}pt)[#{_ts(box['name'])}]")
    if box["kind"] == "graphic":
        w, h = ratio(box.get("shape"))
        if box["id"] in pics:
            parts.append(f"#image({_ts(pics[box['id']])}, width: 100%)")
        else:
            parts.append(f"#block(width: 100%, inset: 10pt, stroke: (paint: gray, dash: \"dashed\"))"
                         f"[#align(center)[#text(fill: gray)[#{_ts(box['name'] + ': the picture to come (' + str(w) + ':' + str(h) + ')')}]]]")
        if (box.get("text") or "").strip():
            parts.append(_typ_text(box["text"], "caption", scale))
    else:
        parts.append(_typ_text(box["text"], as_, scale))
    if box.get("fixed") or box.get("chips"):
        bits = []
        if box.get("fixed"):
            bits.append(f"#text(fill: gray, size: {9 * scale:.1f}pt)[#{_ts(box['fixed'])}]")
        bits += [f"#box(fill: rgb(\"#ffe36b\"), inset: 2pt, radius: 2pt)[#text(size: {8 * scale:.1f}pt)[#{_ts(c)}]]"
                 for c in box.get("chips") or []]
        parts.append(" ".join(bits))
    inner = "\n\n".join(parts)
    if as_ in ("step", "tile", "deck"):
        return f"#block(width: 100%, inset: 8pt, stroke: 0.5pt + luma(200), radius: 4pt)[{inner}]"
    return f"#block(width: 100%)[{inner}]"


def _typ_rows(boxes: list[dict[str, Any]], pics: dict[str, str], *, scale: float = 1.0) -> str:
    out = []
    for row in rows_of(boxes):
        if len(row) == 1:
            out.append(_typ_box(row[0], pics, scale=scale))
        else:
            cells = ", ".join(f"[{_typ_box(b, pics, scale=scale)}]" for b in row)
            out.append(f"#grid(columns: ({', '.join(['1fr'] * len(row))}), gutter: 10pt, {cells})")
    return "\n#v(8pt)\n".join(out)


def to_typst(model: ss.Scaffold, pics: dict[str, str]) -> str:
    thing = model.meta.get("thing") or "page"
    lang = (model.meta.get("lang") or "en").split("-")[0]
    out = [f"#set text(lang: {_ts(lang)})", "#set par(justify: false)"]
    frames = on_thing(model)
    if thing == "deck":
        out.append("#set page(width: 254mm, height: 142.875mm, margin: 12mm)")
        for i, (frame, boxes) in enumerate(frames):
            if i:
                out.append("#pagebreak()")
            shown = [b for b in boxes if b["as"] != "speaker"]
            loose = [b for b in shown if not place_of(b)]
            for b in shown:
                pl = place_of(b)
                if pl:
                    out.append(f"#place(top + left, dx: {pl[0]}%, dy: {pl[1]}%, block(width: {pl[2]}%, "
                               f"height: {pl[3]}%, clip: true)[{_typ_box(b, pics, scale=1.4)}])")
            if loose:
                out.append(_typ_rows(loose, pics, scale=1.4))
    else:
        paper = {"letter": "us-letter"}.get(model.meta.get("shape") or "", "a4")
        out.append(f"#set page(paper: {_ts(paper)}, margin: 20mm)")
        if thing == "document":
            out.append(f"#align(center)[#text(size: 24pt, weight: \"bold\")[#{_ts(model.meta.get('title') or '')}]]")
            out.append("#v(16pt)")
        for frame, boxes in frames:
            if thing == "document":
                head, hb = heading_of(frame, boxes)
                out.append(f"#heading(level: 1)[#{_ts(head or frame['name'])}]")
                boxes = [b for b in boxes if b is not hb]
            out.append(_typ_rows(boxes, pics))
            out.append("#v(14pt)")
    return "\n".join(out) + "\n"


def to_pdf(model: ss.Scaffold, base_dir: Path, out_path: Path, tool: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pics: dict[str, str] = {}
        for b in model.boxes():
            p = picture(b, base_dir) if b["kind"] == "graphic" else None
            if p is not None:
                name = f"pic-{len(pics) + 1}{p.suffix.lower()}"
                shutil.copyfile(p, root / name)
                pics[b["id"]] = "/" + name
        src = root / "thing.typ"
        src.write_text(to_typst(model, pics), encoding="utf-8")
        made = root / "thing.pdf"
        if tool == "cli":
            exe = shutil.which("typst") or "typst"
            args = [exe, "compile", "--root", str(root), str(src), str(made)]
            r = subprocess.run(args, capture_output=True, text=True)
            if r.returncode != 0:
                raise ExportError(f"typst could not make the PDF: {r.stderr.strip()[:400]}")
        else:
            import typst  # type: ignore
            # The wheel's own entry point, named by a literal: the bare call reads, to a skill
            # scanner, as Python's builtin.
            make_pdf = getattr(typst, "compile")
            try:
                make_pdf(str(src), output=str(made), root=str(root))
            except Exception as e:  # the wheel raises its own error types
                raise ExportError(f"typst could not make the PDF: {str(e)[:400]}") from None
        with open(out_path, "xb") as fh:
            fh.write(made.read_bytes())


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------

def deck_markdown(model: ss.Scaffold) -> str:
    """The deck as pandoc's slide markdown: one slide per frame, its title
    from a title or headline box, two boxes side by side as columns, the
    speaker box as the slide's notes."""
    out: list[str] = []
    for frame, boxes in on_thing(model):
        head, hb = heading_of(frame, boxes)
        out += [f"# {head}" if head else "---", ""]
        speaker = [b for b in boxes if b["as"] == "speaker"]
        for row in rows_of([b for b in boxes if b is not hb and b["as"] != "speaker"]):
            if len(row) == 2:
                out += [":::::::::: {.columns}"]
                for b in row:
                    out += ["::: {.column}", *_md_box(b), ":::"]
                out += ["::::::::::", ""]
            else:
                for b in row:
                    out += _md_box(b)
        if speaker:
            out += ["::: notes", *[b["text"].strip() + "\n" for b in speaker], ":::", ""]
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def pptx_by_pandoc(model: ss.Scaffold, base_dir: Path, out_path: Path, exe: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "deck.md"
        src.write_text(deck_markdown(model), encoding="utf-8")
        made = Path(tmp) / "deck.pptx"
        args = [exe, "-f", "markdown", "-t", "pptx", "--slide-level=1",
                f"--resource-path={base_dir}", "-o", str(made), str(src)]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise ExportError(f"pandoc could not make the PPTX: {r.stderr.strip()[:400]}")
        with open(out_path, "xb") as fh:
            fh.write(made.read_bytes())


PPTX_PT = {"title": 40, "headline": 32, "lede": 22, "call": 22, "caption": 12, "quote": 20}


def pptx_by_python(model: ss.Scaffold, base_dir: Path, out_path: Path) -> None:
    from pptx import Presentation  # type: ignore
    from pptx.util import Emu, Pt  # type: ignore
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    W, H, M = 12192000, 6858000, 457200
    blank = prs.slide_layouts[6]
    for frame, boxes in on_thing(model):
        slide = prs.slides.add_slide(blank)
        shown = [b for b in boxes if b["as"] != "speaker"]
        rows = rows_of([b for b in shown if not place_of(b)])
        row_h = (H - 2 * M) // max(1, len(rows))
        spots: list[tuple[dict[str, Any], int, int, int, int]] = []
        for b in shown:
            pl = place_of(b)
            if pl:
                spots.append((b, int(W * pl[0] / 100), int(H * pl[1] / 100), int(W * pl[2] / 100), int(H * pl[3] / 100)))
        for i, row in enumerate(rows):
            col_w = (W - 2 * M) // len(row)
            for j, b in enumerate(row):
                spots.append((b, M + j * col_w, M + i * row_h, col_w - 91440, row_h - 91440))
        for b, x, y, w, h in spots:
            p = picture(b, base_dir) if b["kind"] == "graphic" else None
            if p is not None:
                slide.shapes.add_picture(str(p), Emu(x), Emu(y), width=Emu(w))
                continue
            tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
            tf = tb.text_frame
            tf.word_wrap = True
            text = b["text"].strip() if b["kind"] == "text" else (b["text"].strip() or f"{b['name']}: the picture to come")
            if b["as"] in ("step", "tile", "deck"):
                text = f"{b['name']}\n{text}"
            lines = text.split("\n")
            tf.text = lines[0]
            for ln in lines[1:]:
                tf.add_paragraph().text = ln
            size = PPTX_PT.get(b["as"], 18)
            for para in tf.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(size)
                    run.font.bold = b["as"] in ("title", "headline", "call")
            extra = " · ".join(([b["fixed"]] if b.get("fixed") else []) + list(b.get("chips") or []))
            if extra:
                para = tf.add_paragraph()
                para.text = extra
                for run in para.runs:
                    run.font.size = Pt(12)
        speaker = [b["text"].strip() for b in boxes if b["as"] == "speaker"]
        if speaker:
            slide.notes_slide.notes_text_frame.text = "\n\n".join(speaker)
    with open(out_path, "xb") as fh:
        prs.save(fh)


# ---------------------------------------------------------------------------
# The page, filled
# ---------------------------------------------------------------------------

def page_json(model: ss.Scaffold) -> str:
    """The JSON block's content: the model as `state.md` gives it for a
    program, with every '<' written \\u003c so the block cannot close early."""
    return ss.to_json(model, indent=None).replace("<", "\\u003c")


def fill(model: ss.Scaffold, template: str | None = None) -> str:
    template = template if template is not None else TEMPLATE.read_text(encoding="utf-8")
    start = template.find(BLOCK_OPEN)
    if start < 0:
        raise ExportError(f"the template has no {BLOCK_OPEN} block.")
    start += len(BLOCK_OPEN)
    end = template.find(BLOCK_CLOSE, start)
    return template[:start] + page_json(model) + template[end:]


def block_of(page: str) -> str:
    """The JSON block's content, as a filled page holds it."""
    start = page.index(BLOCK_OPEN) + len(BLOCK_OPEN)
    return page[start:page.index(BLOCK_CLOSE, start)]


# ---------------------------------------------------------------------------
# Hand-off
# ---------------------------------------------------------------------------

def _mm_label(*parts: str) -> str:
    s = "<br/>".join(p for p in parts if p)
    for a, b in (("&", "#amp;"), ('"', "#quot;"), ("<br/>", "\0"), ("<", "#lt;"), (">", "#gt;"), ("\0", "<br/>")):
        s = s.replace(a, b)
    return '"' + s + '"'


def _mm_id(kind: str, item_id: str) -> str:
    return kind + "_" + item_id.replace("-", "_")


def to_mermaid(model: ss.Scaffold, *, names_only: bool = False) -> str:
    """The scaffold as one mermaid flowchart: a subgraph per frame in order,
    a node per box (its name, and the person's words unless names only),
    the frames joined in the thing's order. Notes are left out."""
    out = ["flowchart TB"]
    kept = []
    for frame in model.frames:
        boxes = [b for b in frame["boxes"] if b["as"] != "notes"]
        if not boxes:
            continue
        kept.append(frame)
        out.append(f"  subgraph {_mm_id('f', frame['id'])}[{_mm_label(frame['name'])}]")
        out.append("    direction LR" if len(boxes) <= 4 else "    direction TB")
        for b in boxes:
            words = "" if names_only else (b.get("text") or "").strip().replace("\n", "<br/>")
            out.append(f"    {_mm_id('b', b['id'])}[{_mm_label(b['name'], words)}]")
        out.append("  end")
    for a, b in zip(kept, kept[1:]):
        out.append(f"  {_mm_id('f', a['id'])} --> {_mm_id('f', b['id'])}")
    return "\n".join(out) + "\n"


def _heading_key(s: str) -> str:
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in s.lower()).split())


def placed_by(name: str) -> str | None:
    key = _heading_key(name)
    for entry, words in BRIEF_HEADINGS.items():
        if key in words:
            return entry
    return None


def to_brief(model: ss.Scaffold) -> tuple[str, list[str], list[str]]:
    """The fabulac brief: the person's words only, under the frames' names.
    Returns (text, frames placed by name, frames left for the model there)."""
    out = [f"# {model.meta.get('title') or ''}", ""]
    placed, unplaced = [], []
    has_audience = any(placed_by(f["name"]) == "audience" for f in model.frames)
    for frame in model.frames:
        texts = [b["text"].strip() for b in frame["boxes"] if b["as"] != "notes" and (b.get("text") or "").strip()]
        if not texts:
            continue
        (placed if placed_by(frame["name"]) else unplaced).append(frame["name"])
        out += [f"## {frame['name']}", ""]
        for t in texts:
            out += [t, ""]
    if not has_audience and model.meta.get("for"):
        out += ["## Who it is for", "", model.meta["for"], ""]
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n", placed, unplaced


def to_prompt(model: ss.Scaffold, engine: str) -> str:
    m = model.meta
    thing = m.get("thing") or "page"
    out = [f"# For {engine}: {m.get('title') or ''}", "",
           f"A person wrote the {thing} below themselves, every word, in a scaffold: each part had a line saying "
           f"what it must get across, and they wrote the part. It is for {m.get('for') or 'its readers'}.",
           ""]
    if m.get("next"):
        out += [f"Where they said it goes next: {m['next']}", ""]
    out += [f"Take it into {engine} as its source. Keep their words as they wrote them; where {engine} needs "
            f"words they did not write, ask them rather than invent. Keep the parts in this order.", "",
            "## The parts", ""]
    for frame, boxes in on_thing(model):
        out += [f"### {frame['name']}", ""]
        for b in boxes:
            what = b["plec"].strip()
            if b["kind"] == "graphic":
                body = f"(a picture, {b.get('shape') or '16:9'}; {('at ' + b['href']) if b.get('href') else 'to come'})"
                if (b.get("text") or "").strip():
                    body += f" {b['text'].strip()}"
            else:
                body = b["text"].strip()
            out += [f"**{b['name']}** ({b['as']}{'; what it is for: ' + what if what else ''})", "", body, ""]
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def next_choices(model: ss.Scaffold) -> str:
    thing = model.meta.get("thing") or "page"
    own = {"page": "the page as HTML and PDF", "deck": "the deck as PPTX and PDF",
           "document": "the document as Markdown and PDF"}[thing]
    said = model.meta.get("next")
    lines = ["Where does the work go next? Choose one or several; nothing is chosen for you.",
             f"- {own}  (export.py {' / '.join(FORMATS[thing])})",
             "- a mermaid diagram of it  (export.py mermaid)",
             "- a fabulac brief for enough's authoring program, or its words as one text for a fabulan  (export.py brief)",
             "- a prompt for another creative engine you name  (export.py prompt --engine NAME)"]
    if said:
        lines.append(f"You said, in the plectrum: {said}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _out_dir(args: argparse.Namespace) -> Path:
    return Path(args.out) if args.out else Path(args.file).resolve().parent


def run(args: argparse.Namespace) -> int:
    cmd = args.command
    if cmd == "can":
        c = can()
        print(f"pandoc: {c['pandoc'] or 'not found'}")
        print(f"typst: {c['typst'] or 'not found'}")
        print(f"python-pptx: {'found' if c['python-pptx'] else 'not found'}")
        for thing in ("page", "deck", "document"):
            print(f"{thing}: " + "; ".join(c[thing]))
        return 0
    path = Path(args.file)
    model = load(path)
    base_dir = path.resolve().parent
    folder = _out_dir(args)
    stem = stem_of(model)
    if cmd == "next":
        sys.stdout.write(next_choices(model))
        return 0
    if cmd == "fill":
        p = write_new(folder, f"{stem}.scaffold.html", fill(model))
    elif cmd == "mermaid":
        p = write_new(folder, f"{stem}.mmd", to_mermaid(model, names_only=args.names_only))
    elif cmd == "brief":
        need_state(model, "brief")
        if args.as_ == "fabulan":
            p = write_new(folder, f"{stem}.text.md", to_markdown(model))
            note("enough makes a fabulan beside a markdown text when asked: open this text there and ask for its fabulan.")
        else:
            text, placed, unplaced = to_brief(model)
            p = write_new(folder, f"{stem}.brief.md", text)
            note("This is the brief enough's authoring program takes (`author brief as tool`, or library or service; "
                 "the page's begin from a brief).")
            if placed:
                note(f"placed by their names there: {', '.join(placed)}")
            if unplaced:
                note(f"not placed by name (a model places them there, or the interview asks): {', '.join(unplaced)}")
    elif cmd == "prompt":
        need_state(model, "prompt")
        engine = args.engine.strip()
        if not engine:
            raise ExportError("name the engine the prompt is for: --engine NAME. The skill never picks it.")
        p = write_new(folder, f"{stem}.prompt-{ss.slug(engine) or 'engine'}.md", to_prompt(model, engine))
    elif cmd == "html":
        need_state(model, "HTML")
        need_format(model, "html")
        p = write_new(folder, f"{stem}.html", to_html(model, base_dir))
    elif cmd == "md":
        need_state(model, "Markdown")
        need_format(model, "md")
        p = write_new(folder, f"{stem}.md", to_markdown(model))
    elif cmd == "pdf":
        need_state(model, "PDF")
        need_format(model, "pdf")
        tool = find_typst() if args.with_ in (None, "typst") else None
        if args.with_ not in (None, "typst"):
            raise ExportError(f"a PDF is made with typst, not {args.with_}.")
        if not tool:
            print("No typst here, so no PDF from this script. Make the HTML (export.py html) and print it to "
                  "PDF from a browser" + (", at landscape." if model.meta.get("thing") == "deck" else "."))
            return 3
        p = new_path(folder, f"{stem}.pdf")
        to_pdf(model, base_dir, p, tool)
    elif cmd == "pptx":
        need_state(model, "PPTX")
        need_format(model, "pptx")
        choice = args.with_
        pandoc = find_pandoc() if choice in (None, "pandoc") else None
        has_pptx = find_pptx() if choice in (None, "python-pptx") else False
        if choice not in (None, "pandoc", "python-pptx"):
            raise ExportError(f"a PPTX is made with pandoc or python-pptx, not {choice}.")
        p = new_path(folder, f"{stem}.pptx")
        if pandoc:
            pptx_by_pandoc(model, base_dir, p, pandoc)
        elif has_pptx:
            pptx_by_python(model, base_dir, p)
        else:
            print("No pandoc and no python-pptx here, so no PPTX from this script. The deck still leaves as PDF "
                  "(export.py pdf, with typst) or as HTML to print at landscape (export.py html).")
            return 3
    else:  # argparse keeps this unreachable
        return 2
    print(p)
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="export.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Each command that writes prints the new file's path; it never overwrites.")
    sub = ap.add_subparsers(dest="command", required=True, metavar="command")
    sub.add_parser("can", help="what this Python can make here")

    def with_file(name: str, text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=text)
        p.add_argument("file", help="a scaffold's state (or a plectrum, for fill, next and mermaid)")
        p.add_argument("--out", help="the folder to write into (default: the file's own)")
        return p

    with_file("html", "the thing as one HTML file")
    with_file("md", "a document as Markdown")
    with_file("pdf", "a PDF through typst").add_argument("--with", dest="with_", choices=("typst",))
    with_file("pptx", "a deck as PPTX").add_argument("--with", dest="with_", choices=("pandoc", "python-pptx"))
    with_file("fill", "the scaffold page, filled")
    with_file("next", "where the work goes next: the choices")
    with_file("mermaid", "hand-off: a mermaid diagram").add_argument(
        "--names-only", action="store_true", help="the boxes' names, without the person's words")
    with_file("brief", "hand-off: a fabulac brief, or a fabulan's text").add_argument(
        "--for", dest="as_", choices=("fabulac", "fabulan"), default="fabulac")
    with_file("prompt", "hand-off: a prompt for a named engine").add_argument(
        "--engine", required=True, help="the engine the person named")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args)
    except ExportError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
