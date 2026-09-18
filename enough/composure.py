"""Composure: the `.comp` canvas format, its node-level ops, and its sidecars.

A **composure** is enough's base-layer canvas: an unbounded plane holding
**modules** (boxes — text cards, full pages, links into project files, wiki
articles, web pages) and freehand **ink**. A **form** is a composure
template; a **page** is one page inside a module. This module owns the
format — parser, serializer, sanitizer, node-level ops, the JSON document
model the frontend renders from, and the comments sidecar. Nothing else
parses or writes `.comp` content.

Why it is shaped the way it is
------------------------------

- **`.comp` is HTML5, not a bespoke format.** A composure opens in any
  browser as a static rendering — the serializer emits a generated
  `<style>` block so an orphaned file is still readable ten years from now
  with no enough installed. Metadata rides in `<meta name="composure:*">`
  tags and `data-*` attributes, which are exactly the parts a browser
  ignores and a parser needs.

- **One door (the girraph model).** Content changes ONLY through validated
  node-level ops applied by `apply_ops()` under a per-path write lock. The
  UI and the readvisor tools use the same op vocabulary, so a user typing
  in a module and a readvisor rewriting a different one both land. Whole-
  file writes to `*.comp` are refused at both existing write doors. The
  server parses → mutates → sanitizes → serializes; nothing a client or a
  model sends is ever written through verbatim.

- **The sanitizer is the security boundary, and it runs on READ as well as
  on write.** A hand-edited or hostile `.comp` — dropped in by a sync
  client, written by a confused model, mailed to the user — can never
  inject anything: `loads()` sanitizes every page it reads, so the JSON
  document model the frontend gets is allowlisted by construction. The
  frontend re-sanitizes anyway (defense in depth), but it is not the thing
  standing between a `.comp` and the user.

- **Round-trip stability.** `dumps(loads(x)) == x` for anything `dumps`
  produced. Unknown `composure:*` meta keys and unknown `data-*`
  attributes on modules and pages survive a round trip (so a file written
  by a newer enough is not silently downgraded by an older one), while
  anything not expressible in the allowlist is dropped.

- **Never a whole-file diff.** Ops are atomic per batch (validate all,
  apply all, one tmp+rename write) and each batch bumps `rev`. Clients
  send `base_rev`; a stale base is not an error, it is a merge — the reply
  names the modules that moved under them.

Geometry
--------

World units: 1 unit = 1 CSS px at zoom 1. A **fullport** module is
816×1056 (US Letter at 96 dpi). Coordinates may be negative; the canvas is
unbounded. Geometry is rounded to 2 decimals on write, ink points to 1 —
enough precision for anything a pointer can express, few enough digits
that a diff stays readable.

See docs/composure-landed-P4b.md for the wire contract (JSON model,
endpoints, op vocabulary, caps) and docs/composure-plan.md for the round's
spec.
"""

from __future__ import annotations

import copy
import datetime as _dt
import html as _html
import json
import logging
import os
import re
import secrets
import threading
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("enough.composure")

SUFFIX = ".comp"
FORMAT_VERSION = 1

#: The SSE event name every applied op batch emits. It lives here rather
#: than in the API module so the readvisor tools can name it without
#: importing FastAPI.
EVENT = "composure"

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: Module types. `doc` links a project file (any type — routed to the right
#: mode on open, including another `.comp`, which is how boards drill down).
MODULE_TYPES: tuple[str, ...] = (
    "text", "doc", "wiki", "weblink", "webframe", "image",
)

#: Named background swatches. NEVER a raw color — the frontend maps these
#: to theme-aware values, so a composure written in the light theme is not
#: unreadable in the dark one.
BG_SWATCHES: tuple[str, ...] = (
    "paper", "yellow", "pink", "blue", "green", "orange", "lilac", "gray",
    "ink", "clear",
)

#: Ink colors (also named, same reason).
INK_COLORS: tuple[str, ...] = ("ink", "red", "blue", "green", "yellow")

#: Named highlight colors for `span[data-hl]` — the same four review mode
#: paints, so a highlight means one thing across the whole product.
HL_COLORS: tuple[str, ...] = ("yellow", "green", "blue", "pink")

#: `composure:kind` — drives fit-zoom behavior in the canvas.
KINDS: tuple[str, ...] = ("page", "board")

#: Shipped + project form names that `new_composure` understands. Any other
#: name is looked up as a project form file.
SHIPPED_FORMS: tuple[str, ...] = (
    "blank", "cards", "scaffold", "journal", "council",
)

#: Webframe refresh policies.
REFRESH_MODES: tuple[str, ...] = ("manual", "open", "daily")

#: Base sizes per module type, before `data-scale` is applied.
BASE_SIZE: dict[str, tuple[float, float]] = {
    "text": (360.0, 240.0),
    "doc": (320.0, 120.0),
    "wiki": (320.0, 120.0),
    "weblink": (320.0, 120.0),
    "webframe": (480.0, 600.0),
    "image": (360.0, 240.0),
}

#: A fullport module: US Letter at 96 dpi, with 72 units of inner padding.
FULLPORT = (816.0, 1056.0)
FULLPORT_PAD = 72.0

#: The scale ladder (`data-scale`): 0.5 – 6, step ×1.125.
SCALE_MIN = 0.5
SCALE_MAX = 6.0
SCALE_STEP = 1.125

#: Placement grid and gutter, in world units.
GRID = 24.0
GUTTER = 48.0


# ---------------------------------------------------------------------------
# Caps. Enforced server-side with messages that name the fix — a small local
# model that blows one of these has to be able to act on the refusal.
# ---------------------------------------------------------------------------

MAX_MODULES = 200
MAX_PAGES_PER_MODULE = 500
MAX_PAGE_CHARS = 400_000          # 400 KB of rich text per page
MAX_RICH_INPUT_CHARS = 2_000_000  # what the sanitizer will even look at
MAX_STROKES = 5_000
MAX_POINTS_PER_STROKE = 2_000
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32                    # rich-text nesting depth
MAX_TAGS_PER_PAGE = 20_000        # nested-formatting-bomb ceiling
MAX_TITLE_CHARS = 200
MAX_ATTR_CHARS = 2_000
MAX_EXTRA_ATTRS = 24              # unknown data-* preserved per element

CAPS: dict[str, int] = {
    "modules": MAX_MODULES,
    "pages_per_module": MAX_PAGES_PER_MODULE,
    "page_chars": MAX_PAGE_CHARS,
    "strokes": MAX_STROKES,
    "points_per_stroke": MAX_POINTS_PER_STROKE,
    "file_bytes": MAX_FILE_BYTES,
    "depth": MAX_DEPTH,
    "title_chars": MAX_TITLE_CHARS,
}


class ComposureError(ValueError):
    """Unusable input, or an op the format forbids.

    The message is written for a reader who has to fix it without seeing
    this file — a small local model or a frontend error toast. Name the
    thing, name the allowed values, name the door."""


# ---------------------------------------------------------------------------
# The rich-text allowlist
# ---------------------------------------------------------------------------

#: Tags allowed inside `.comp-page`. Everything else is dropped.
RICH_TAGS: frozenset[str] = frozenset({
    "p", "br", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote",
    "pre", "code", "b", "strong", "i", "em", "u", "s", "mark", "hr", "a",
    "span",
})

#: Void tags inside the allowlist (emitted as `<br>` / `<hr>`, never closed).
RICH_VOID: frozenset[str] = frozenset({"br", "hr"})

#: Per-tag attribute allowlist. An attribute not named here is dropped even
#: when the tag survives — that is what makes `<p onclick=…>` safe.
RICH_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href"}),
    "li": frozenset({"data-check"}),
    "span": frozenset({"data-hl"}),
}

#: Tags whose CONTENT is dropped along with the tag. Everything else that
#: is not on the allowlist keeps its text (a stray `<div>` should not eat a
#: paragraph) — but these carry executable or foreign-namespace payloads,
#: so their text is exactly the thing that must not survive.
RICH_DROP_CONTENT: frozenset[str] = frozenset({
    "script", "style", "template", "noscript", "iframe", "object",
    "embed", "svg", "math", "applet", "frame", "frameset", "base", "link",
    "meta", "form", "input", "button", "select", "textarea", "option",
})

#: Block-level members of the allowlist — used only to decide where
#: `rich_to_md` puts blank lines.
_RICH_BLOCK: frozenset[str] = frozenset({
    "p", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "pre", "hr",
})

_CONTROL_CHARS = frozenset(
    chr(c) for c in list(range(0x00, 0x20)) + [0x7F]
)

_MODULE_ID_RE = re.compile(r"^m[0-9a-z]{1,15}$")
_STROKE_ID_RE = re.compile(r"^s[0-9a-z]{1,15}$")
_DATA_ATTR_RE = re.compile(r"^data-[a-z][a-z0-9-]{0,40}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return _dt.date.today().isoformat()


def _new_module_id() -> str:
    return "m" + secrets.token_hex(4)


def _new_stroke_id() -> str:
    return "s" + secrets.token_hex(4)


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _num(value: object, default: float = 0.0) -> float:
    """A finite float, or `default`. Bools are not numbers here — a JSON
    `true` reaching a geometry field is a client bug, not a 1."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _fmt(value: float, places: int = 2) -> str:
    """Deterministic short decimal: 2 places, trailing zeros trimmed, and
    never `-0`. Geometry uses 2 places, ink points 1."""
    r = round(float(value), places)
    if r == 0:
        return "0"
    s = f"{r:.{places}f}"
    if "." in s:
        # Trim the FRACTION only — `"360.00".rstrip("0")` would eat a
        # significant zero and put a card at x=36.
        whole, frac = s.split(".", 1)
        frac = frac.rstrip("0")
        s = f"{whole}.{frac}" if frac else whole
    return s or "0"


def _clamp(value: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, value))


def _clean_text(value: object, limit: int = MAX_ATTR_CHARS) -> str:
    """One line of plain text: control characters removed, whitespace
    collapsed, length-capped. Used for titles, speaker names, and every
    short `data-*` value."""
    s = "" if value is None else str(value)
    s = "".join(ch for ch in s if ch not in _CONTROL_CHARS or ch in "\t\n")
    return " ".join(s.split())[:limit]


def slugify(text: str, max_len: int = 48) -> str:
    """Filename-safe slug. Unicode is folded to ASCII where it decomposes
    (so `Café` becomes `cafe`, not `caf`), everything else becomes a
    hyphen."""
    folded = unicodedata.normalize("NFKD", text or "")
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    s = _SLUG_STRIP_RE.sub("-", ascii_only).strip("-")
    return s[:max_len].strip("-") or "untitled"


def scale_ladder() -> list[float]:
    """The allowed `data-scale` values, ascending.

    **Anchored at 1.0**, not at the minimum: 1 is the default scale and the
    thing every other rung is relative to, so it has to be exactly on the
    ladder — a ladder built upward from 0.5 by ×1.125 misses it by 1.4 %,
    and every new module would then be saved at 1.0136."""
    rungs = {SCALE_MIN, SCALE_MAX}
    step = 1.0
    while step <= SCALE_MAX:
        rungs.add(round(step, 4))
        step *= SCALE_STEP
    step = 1.0 / SCALE_STEP
    while step >= SCALE_MIN:
        rungs.add(round(step, 4))
        step /= SCALE_STEP
    return sorted(rungs)


def snap_scale(value: object) -> float:
    """Clamp a text scale into [0.5, 6] and snap it to the ×1.125 ladder so
    the inspector's A−/A+ steppers and an op from a readvisor land on the
    same values."""
    f = _clamp(_num(value, 1.0), SCALE_MIN, SCALE_MAX)
    return min(scale_ladder(), key=lambda rung: (abs(rung - f), rung))


def _href_ok(raw: str) -> str | None:
    """Return a cleaned href, or None when the URL must be dropped.

    Order matters and is the whole point: decode entities (repeatedly —
    `&amp;#106;avascript:` is one decode away from a scheme), strip
    whitespace and control characters (a browser ignores `java\\tscript:`,
    so the check must too), and only then look at the scheme. Allowed:
    `http`, `https`, `mailto`, and project-relative paths. Everything else
    — including `javascript:`, `data:`, `vbscript:`, `file:` and
    protocol-relative `//host` — is dropped."""
    s = raw or ""
    for _ in range(4):                       # entity-decode to a fixed point
        nxt = _html.unescape(s)
        if nxt == s:
            break
        s = nxt
    s = "".join(ch for ch in s if ch not in _CONTROL_CHARS).strip()
    if not s or len(s) > MAX_ATTR_CHARS:
        return None
    # The scheme probe strips *all* whitespace, not just the edges: browsers
    # tolerate `j a v a s c r i p t :` in an href, so our check has to see
    # the same string they do.
    probe = "".join(s.split()).lower()
    if probe.startswith(("http://", "https://", "mailto:")):
        return s
    if probe.startswith("//"):
        return None                          # protocol-relative → whatever we are
    head = probe.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if ":" in head:
        return None                          # any other scheme
    if probe.startswith(("/", "\\")):
        return None                          # absolute filesystem-ish path
    if ".." in Path(probe.split("?", 1)[0].split("#", 1)[0]).parts:
        return None                          # traversal
    return s


# ---------------------------------------------------------------------------
# The sanitizer
#
# `_RichBuilder` is the allowlist engine, driven by tag/data events rather
# than by a string, so the same code sanitizes (a) rich text arriving from a
# client or a readvisor, and (b) rich text being read back out of a `.comp`
# file mid-parse. One implementation, one place to get it wrong.
# ---------------------------------------------------------------------------

class _RichBuilder:
    """Rebuilds an allowlisted, well-formed HTML fragment from tag events.

    Unknown tags are dropped but their text is kept; the handful of tags in
    `RICH_DROP_CONTENT` take their text with them. Attributes are
    allowlisted per tag. Depth, tag count and output size are capped."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip_depth = 0          # >0 while inside a drop-content tag
        self.skip_tag: str | None = None
        self.tags = 0
        self.dropped: set[str] = set()

    # -- events ------------------------------------------------------------

    def start(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth += 1
            return
        if tag in RICH_DROP_CONTENT:
            self.skip_depth = 1
            self.skip_tag = tag
            self.dropped.add(tag)
            return
        if tag not in RICH_TAGS:
            self.dropped.add(tag)
            return                    # unknown tag: drop the tag, keep the text
        if tag in RICH_VOID:
            self._emit_void(tag, attrs)
            return
        if tag == "a" and not self._attrs("a", attrs):
            # A link whose href did not survive the scheme check is not a
            # link; keep the words, drop the empty anchor. The stray `</a>`
            # is ignored by `end()` because `a` never reached the stack.
            self.dropped.add("a")
            return
        if len(self.stack) >= MAX_DEPTH:
            self.dropped.add(tag)
            return                    # too deep: drop the tag, keep the text
        self.tags += 1
        if self.tags > MAX_TAGS_PER_PAGE:
            raise ComposureError(
                f"rich text has more than {MAX_TAGS_PER_PAGE} elements — "
                f"split it across pages or modules."
            )
        self.out.append(self._open_tag(tag, attrs))
        self.stack.append(tag)

    def startend(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        """`<br/>`-style self-closing. Only the void tags survive it; for
        anything else HTML has no such thing, so treat it as start+end."""
        tag = tag.lower()
        if tag in RICH_VOID:
            self.start(tag, attrs)
            return
        self.start(tag, attrs)
        self.end(tag)

    def end(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = None
            return
        if tag in RICH_VOID or tag not in RICH_TAGS:
            return
        if tag not in self.stack:
            return                    # stray close: ignore
        # Close everything above it too, so the output is well-formed even
        # when the input was not (`<b><i></b></i>`).
        while self.stack:
            open_tag = self.stack.pop()
            self.out.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    def data(self, text: str) -> None:
        if self.skip_depth or not text:
            return
        self.out.append(_html.escape(text, quote=False))

    # -- output ------------------------------------------------------------

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        s = "".join(self.out)
        if len(s) > MAX_PAGE_CHARS:
            raise ComposureError(
                f"page text is {len(s)} characters, over the {MAX_PAGE_CHARS} "
                f"cap — split it with add_page (a module holds up to "
                f"{MAX_PAGES_PER_MODULE} pages)."
            )
        return s

    # -- internals ---------------------------------------------------------

    def _open_tag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> str:
        rendered = self._attrs(tag, attrs)
        return f"<{tag}{rendered}>"

    def _emit_void(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        self.tags += 1
        if self.tags > MAX_TAGS_PER_PAGE:
            raise ComposureError(
                f"rich text has more than {MAX_TAGS_PER_PAGE} elements — "
                f"split it across pages or modules."
            )
        self.out.append(f"<{tag}{self._attrs(tag, attrs)}>")

    def _attrs(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> str:
        allowed = RICH_ATTRS.get(tag)
        if not allowed:
            return ""
        kept: list[tuple[str, str]] = []
        for raw_name, raw_value in attrs:
            name = (raw_name or "").lower()
            if name not in allowed:
                continue
            value = raw_value or ""
            if name == "href":
                cleaned = _href_ok(value)
                if cleaned is None:
                    continue
                kept.append((name, cleaned))
            elif name == "data-check":
                kept.append((name, "1" if str(value).strip() in ("1", "true", "yes") else "0"))
            elif name == "data-hl":
                v = str(value).strip().lower()
                if v in HL_COLORS:
                    kept.append((name, v))
            else:  # pragma: no cover — every allowlisted attr is handled above
                continue
        # Sorted so the same input always serializes the same way; a
        # duplicate attribute keeps its first value, like a browser.
        seen: set[str] = set()
        parts = []
        for name, value in sorted(kept):
            if name in seen:
                continue
            seen.add(name)
            parts.append(f' {name}="{_html.escape(value, quote=True)}"')
        return "".join(parts)


class _RichParser(HTMLParser):
    """Drives a `_RichBuilder` from an HTML string. Comments, declarations,
    processing instructions and CDATA never reach the builder — they are
    simply not forwarded."""

    def __init__(self, builder: _RichBuilder) -> None:
        super().__init__(convert_charrefs=True)
        self.builder = builder

    def handle_starttag(self, tag, attrs):        # noqa: D102
        self.builder.start(tag, attrs)

    def handle_startendtag(self, tag, attrs):     # noqa: D102
        self.builder.startend(tag, attrs)

    def handle_endtag(self, tag):                 # noqa: D102
        self.builder.end(tag)

    def handle_data(self, data):                  # noqa: D102
        self.builder.data(data)

    # Everything below is deliberately a no-op: dropped, never emitted.
    def handle_comment(self, data): ...
    def handle_decl(self, decl): ...
    def handle_pi(self, data): ...
    def unknown_decl(self, data): ...


def sanitize_rich(raw: str) -> str:
    """Return an allowlisted, well-formed rich-text fragment.

    Idempotent: `sanitize_rich(sanitize_rich(x)) == sanitize_rich(x)`, which
    is what lets `loads`/`dumps` round-trip without the text drifting.

    This is the only function that produces rich text stored in a `.comp`.
    Everything — client input, readvisor markdown, a hand-edited file being
    read back, a fetched web page — goes through it."""
    text = raw or ""
    if len(text) > MAX_RICH_INPUT_CHARS:
        raise ComposureError(
            f"rich text input is {len(text)} characters, over the "
            f"{MAX_RICH_INPUT_CHARS} parse limit — send less at a time."
        )
    builder = _RichBuilder()
    parser = _RichParser(builder)
    parser.feed(text)
    parser.close()
    return builder.result()


def rich_text(rich: str) -> str:
    """Plain text of a rich fragment — tags stripped, entities decoded,
    block boundaries turned into newlines. Used for outlines, faces and
    first-line previews; never stored."""
    out: list[str] = []

    class _Strip(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in _RICH_BLOCK or tag == "br":
                out.append("\n")

        def handle_startendtag(self, tag, attrs):
            if tag == "br" or tag == "hr":
                out.append("\n")

        def handle_endtag(self, tag):
            if tag in _RICH_BLOCK:
                out.append("\n")

        def handle_data(self, data):
            out.append(data)

    p = _Strip(convert_charrefs=True)
    p.feed(rich or "")
    p.close()
    text = "".join(out)
    lines = [" ".join(ln.split()) for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def first_line(rich: str, limit: int = 200) -> str:
    """The first non-empty line of a rich fragment, length-capped. This is
    what a module shows as its face when the canvas is zoomed out, and what
    the readvisor outline quotes."""
    text = rich_text(rich)
    line = text.split("\n", 1)[0] if text else ""
    return line[:limit]


# ---------------------------------------------------------------------------
# Markdown ⇄ rich
#
# `markdown-it-py` is reachable from a BASE dependency
# (enough → huggingface-hub → typer → rich → markdown-it-py), verified with
# `uv tree`, so it is imported rather than reimplemented — lazily, because a
# server that never touches a composure should not pay for it. The fallback
# below exists for a broken venv, not for a supported configuration.
# ---------------------------------------------------------------------------

_MD_CACHE: dict[str, Any] = {}

# markdown-it renders `- [x] done` as a literal `[x]` in the `<li>`; the
# checklist is ours, so we lift it into `li[data-check]` before sanitizing.
_TASK_RE = re.compile(
    r"(<li>)(\s*(?:<p>)?\s*)\[([ xX])\]\s+", re.MULTILINE)

# `<img>` is not on the allowlist (an image lives in an `image` module, not
# in a paragraph), but the alt text is the author's words — keep them rather
# than letting the whole picture vanish silently.
_IMG_RE = re.compile(r"<img\b[^>]*?\balt=\"([^\"]*)\"[^>]*>")
_IMG_BARE_RE = re.compile(r"<img\b[^>]*>")

# markdown-it separates block elements with newlines. Those become text
# nodes inside the page, so they are stripped here rather than stored.
_BLOCK_WS_RE = re.compile(r">\s*\n\s*<")
_PRE_SPLIT_RE = re.compile(r"(<pre\b.*?</pre>)", re.DOTALL)


def _tidy_block_whitespace(html: str) -> str:
    """Drop the newlines markdown-it puts between block tags — outside
    `<pre>`, where every character is the author's."""
    parts = _PRE_SPLIT_RE.split(html)
    return "".join(
        part if part.startswith("<pre") else _BLOCK_WS_RE.sub("><", part)
        for part in parts
    ).strip()


def _markdown_renderer():
    md = _MD_CACHE.get("md")
    if md is not None:
        return md
    try:
        from markdown_it import MarkdownIt
    except ImportError:  # pragma: no cover — a broken venv, not a config
        log.warning("markdown-it-py unavailable; using the paragraph fallback")
        _MD_CACHE["md"] = False
        return False
    md = MarkdownIt("commonmark", {"html": False, "linkify": False,
                                   "typographer": False})
    _MD_CACHE["md"] = md
    return md


def _fallback_md(markdown: str) -> str:
    """Paragraphs only. Reached only when markdown-it-py is missing, i.e.
    when the install is broken — text survives, formatting does not."""
    blocks = [b.strip() for b in (markdown or "").split("\n\n")]
    return "".join(
        "<p>" + _html.escape(b, quote=False).replace("\n", "<br>") + "</p>"
        for b in blocks if b
    )


def md_to_rich(markdown: str) -> str:
    """CommonMark → sanitized rich text.

    Everything the allowlist cannot express (images, tables, raw HTML, h5/h6)
    degrades to its text rather than disappearing. `- [ ]` / `- [x]` list
    items become `li[data-check]`, which is the checklist the canvas draws."""
    md = _markdown_renderer()
    if md is False:
        return sanitize_rich(_fallback_md(markdown))
    rendered = md.render(markdown or "")
    rendered = _TASK_RE.sub(
        lambda m: f'<li data-check="{"1" if m.group(3).lower() == "x" else "0"}">{m.group(2)}',
        rendered,
    )
    rendered = _IMG_RE.sub(lambda m: m.group(1), rendered)
    rendered = _IMG_BARE_RE.sub("", rendered)
    return sanitize_rich(_tidy_block_whitespace(rendered))


class _MdWriter(HTMLParser):
    """Rich text → markdown. Deliberately small: it only has to handle the
    allowlist, because the allowlist is all that can be stored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.list_stack: list[dict[str, Any]] = []
        self.pre = 0
        self.quote = 0
        self.pending_check: str | None = None

    def _w(self, s: str) -> None:
        self.out.append(s)

    def _block_break(self) -> None:
        text = "".join(self.out)
        if text and not text.endswith("\n\n"):
            self._w("\n" if text.endswith("\n") else "\n\n")

    def handle_starttag(self, tag, attrs):
        attrd = {k: (v or "") for k, v in attrs}
        if tag in ("h1", "h2", "h3", "h4"):
            self._block_break()
            self._w("#" * int(tag[1]) + " ")
        elif tag == "p":
            self._block_break()
            if self.quote:
                self._w("> ")
        elif tag == "blockquote":
            self._block_break()
            self.quote += 1
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self._w("\n" if not "".join(self.out).endswith("\n") else "")
            else:
                self._block_break()
            self.list_stack.append({"kind": tag, "n": 0})
        elif tag == "li":
            depth = max(0, len(self.list_stack) - 1)
            cur = self.list_stack[-1] if self.list_stack else {"kind": "ul", "n": 0}
            cur["n"] = cur.get("n", 0) + 1
            text = "".join(self.out)
            if text and not text.endswith("\n"):
                self._w("\n")
            marker = f"{cur['n']}. " if cur["kind"] == "ol" else "- "
            box = ""
            if "data-check" in attrd:
                box = "[x] " if attrd["data-check"] == "1" else "[ ] "
            self._w("  " * depth + marker + box)
        elif tag == "pre":
            self._block_break()
            self._w("```\n")
            self.pre += 1
        elif tag == "code":
            if not self.pre:
                self._w("`")
        elif tag in ("b", "strong"):
            self._w("**")
        elif tag in ("i", "em"):
            self._w("*")
        elif tag == "s":
            self._w("~~")
        elif tag == "a":
            self._w("[")
            self.pending_check = attrd.get("href", "")
        elif tag == "br":
            self._w("\n")
        elif tag == "hr":
            self._block_break()
            self._w("---\n\n")

    def handle_startendtag(self, tag, attrs):
        if tag in ("br", "hr"):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "p"):
            self._w("\n\n")
        elif tag == "blockquote":
            self.quote = max(0, self.quote - 1)
            self._w("\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            if not self.list_stack:
                self._w("\n")
        elif tag == "li":
            self._w("\n")
        elif tag == "pre":
            self.pre = max(0, self.pre - 1)
            text = "".join(self.out)
            self._w("" if text.endswith("\n") else "\n")
            self._w("```\n\n")
        elif tag == "code":
            if not self.pre:
                self._w("`")
        elif tag in ("b", "strong"):
            self._w("**")
        elif tag in ("i", "em"):
            self._w("*")
        elif tag == "s":
            self._w("~~")
        elif tag == "a":
            href = self.pending_check or ""
            self.pending_check = None
            self._w(f"]({href})" if href else "]")

    def handle_data(self, data):
        if self.pre:
            self._w(data)
            return
        text = data.replace("\n", " ")
        if not text.strip() and "".join(self.out).endswith("\n"):
            return          # the source HTML's inter-block whitespace
        self._w(text)

    def result(self) -> str:
        text = "".join(self.out)
        # Collapse runs of blank lines; trailing whitespace on a line is
        # meaningful in markdown (hard break) only as exactly two spaces,
        # which we never emit, so strip it.
        lines = [ln.rstrip() for ln in text.split("\n")]
        out: list[str] = []
        for ln in lines:
            if not ln and out and not out[-1]:
                continue
            out.append(ln)
        return "\n".join(out).strip() + "\n" if any(out) else ""


def rich_to_md(rich: str) -> str:
    """Sanitized rich text → markdown. The readvisor reads composures in
    markdown, so this is the shape every tool result is in."""
    w = _MdWriter()
    w.feed(rich or "")
    w.close()
    return w.result()


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------

@dataclass
class Page:
    """One page inside a module. `filed` is the journal's lock: once a page
    is filed it is immutable to every content op forever (comments still
    work) — that is the whole promise of a journal."""
    n: int = 1
    rich: str = ""
    date: str | None = None
    filed: bool = False
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class Module:
    """A box on the canvas."""
    id: str = ""
    type: str = "text"
    x: float = 0.0
    y: float = 0.0
    w: float = 360.0
    h: float = 240.0
    z: int = 1
    bg: str = "paper"
    scale: float = 1.0
    title: str = ""
    cur: int = 1
    # Type-specific fields. `href` is a project-relative path (doc/image),
    # `url` an external address (weblink/webframe), `article` a wikisink
    # article path with the optional `install` it came from, `refresh` a
    # webframe policy, `cache` the project-relative path of its last fetch.
    href: str = ""
    url: str = ""
    article: str = ""
    install: str = ""
    refresh: str = ""
    cache: str = ""
    # Council (P5): engine-owned transcript modules.
    speaker: str = ""
    speaker_kind: str = ""
    turn: str = ""
    pages: list[Page] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def locked(self) -> bool:
        """Engine-owned: a council transcript statement. Users and tools may
        move it and comment on it; only the council engine writes its text."""
        return bool(self.speaker)


@dataclass
class Stroke:
    """One ink polyline, in world units."""
    id: str = ""
    width: float = 2.0
    color: str = "ink"
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Composure:
    title: str = "Untitled"
    version: int = FORMAT_VERSION
    form: str = "blank"
    kind: str = "page"
    rev: int = 0
    created: str = ""
    modified: str = ""
    view: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "zoom": 1.0})
    council: dict[str, Any] | None = None
    lang: str = "en"
    generator: str = ""
    modules: list[Module] = field(default_factory=list)
    strokes: list[Stroke] = field(default_factory=list)
    #: Unknown `composure:*` meta keys, preserved verbatim so a file written
    #: by a newer enough survives a round trip through an older one.
    meta_extra: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def module(self, module_id: str) -> Module | None:
        return next((m for m in self.modules if m.id == module_id), None)

    def stroke_ids(self) -> set[str]:
        return {s.id for s in self.strokes}

    def bounds(self) -> dict[str, float]:
        """The bounding box of every module and stroke point, or a zero box
        for an empty composure. The frontend's fit-all reads this."""
        xs: list[float] = []
        ys: list[float] = []
        for m in self.modules:
            xs += [m.x, m.x + m.w]
            ys += [m.y, m.y + m.h]
        for s in self.strokes:
            for px, py in s.points:
                xs.append(px)
                ys.append(py)
        if not xs:
            return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
        return {"x": min(xs), "y": min(ys),
                "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_KNOWN_MODULE_ATTRS = {
    "data-id", "data-type", "data-x", "data-y", "data-w", "data-h", "data-z",
    "data-bg", "data-scale", "data-title", "data-cur", "data-href",
    "data-url", "data-article", "data-install", "data-refresh", "data-cache",
    "data-speaker", "data-speaker-kind", "data-turn",
}
_KNOWN_PAGE_ATTRS = {"data-n", "data-date", "data-filed"}


def _extra_attrs(attrs: dict[str, str], known: set[str]) -> dict[str, str]:
    """Unknown `data-*` attributes, kept so a newer enough's extra fields
    survive being opened by an older one. Non-`data-*` attributes (class,
    style, id) are regenerated by the serializer and never preserved."""
    out: dict[str, str] = {}
    for name, value in sorted(attrs.items()):
        if name in known or not _DATA_ATTR_RE.match(name):
            continue
        out[name] = _clean_text(value)
        if len(out) >= MAX_EXTRA_ATTRS:
            break
    return out


class _CompParser(HTMLParser):
    """Reads a `.comp` document. Rich text inside `.comp-page` is fed
    straight into a `_RichBuilder`, so a file is sanitized as it is read —
    there is no window in which unsanitized markup exists in memory."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.comp = Composure()
        self._in_title = False
        self._title_parts: list[str] = []
        self._module: Module | None = None
        self._page: Page | None = None
        self._builder: _RichBuilder | None = None
        self._page_divs = 0          # <div> nesting INSIDE the open page
        self._saw_root = False

    # -- events ------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attrd = {(k or "").lower(): (v or "") for k, v in attrs}
        if self._builder is not None:
            # Inside a page everything is content. `div` is counted (never
            # kept — it is not on the allowlist) so that a hand-written
            # `<div>` inside a page cannot make its `</div>` look like the
            # page's own close and truncate the rest of the module.
            if tag == "div":
                self._page_divs += 1
            self._builder.start(tag, attrs)
            return
        if tag == "html":
            self._saw_root = True
            self.comp.lang = _clean_text(attrd.get("lang") or "en", 16) or "en"
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._meta(attrd)
        elif tag == "section" and "comp-module" in attrd.get("class", "").split():
            self._start_module(attrd)
        elif tag == "div" and "comp-page" in attrd.get("class", "").split():
            self._start_page(attrd)
        elif tag == "polyline":
            self._stroke(attrd)

    def handle_startendtag(self, tag, attrs):
        attrd = {(k or "").lower(): (v or "") for k, v in attrs}
        if self._builder is not None:
            self._builder.startend(tag, attrs)
            return
        if tag == "meta":
            self._meta(attrd)
        elif tag == "polyline":
            self._stroke(attrd)
        elif tag == "div" and "comp-page" in attrd.get("class", "").split():
            self._start_page(attrd)
            self._end_page()

    def handle_endtag(self, tag):
        if self._builder is not None:
            if tag == "div":
                if self._page_divs > 0:
                    self._page_divs -= 1
                    self._builder.end(tag)
                else:
                    self._end_page()
                return
            if tag == "section":
                # An unbalanced page (a hand-edited file) must not swallow
                # the module: close both and carry on.
                self._end_page()
                self._end_module()
                return
            self._builder.end(tag)
            return
        if tag == "title":
            self._in_title = False
        elif tag == "section" and self._module is not None:
            self._end_module()

    def handle_data(self, data):
        if self._builder is not None:
            self._builder.data(data)
        elif self._in_title:
            self._title_parts.append(data)

    def handle_comment(self, data): ...
    def handle_decl(self, decl): ...
    def handle_pi(self, data): ...
    def unknown_decl(self, data): ...

    # -- pieces ------------------------------------------------------------

    def _meta(self, attrd: dict[str, str]) -> None:
        name = (attrd.get("name") or "").strip().lower()
        content = attrd.get("content") or ""
        if name == "generator":
            self.comp.generator = _clean_text(content, 120)
            return
        if not name.startswith("composure:"):
            return
        key = name[len("composure:"):]
        c = self.comp
        if key == "version":
            c.version = int(_num(content, FORMAT_VERSION))
        elif key == "form":
            c.form = _clean_text(content, 64) or "blank"
        elif key == "kind":
            k = _clean_text(content, 16)
            c.kind = k if k in KINDS else "page"
        elif key == "rev":
            c.rev = max(0, int(_num(content, 0)))
        elif key == "created":
            c.created = _clean_text(content, 40)
        elif key == "modified":
            c.modified = _clean_text(content, 40)
        elif key == "view":
            c.view = _clean_view(_json_or_none(content))
        elif key == "council":
            c.council = _json_or_none(content) if isinstance(
                _json_or_none(content), dict) else None
        else:
            if len(c.meta_extra) < MAX_EXTRA_ATTRS:
                c.meta_extra[key] = _clean_text(content, MAX_ATTR_CHARS)

    def _start_module(self, attrd: dict[str, str]) -> None:
        m = Module()
        m.id = (attrd.get("data-id") or "").strip().lower()
        m.type = _clean_text(attrd.get("data-type") or "text", 32) or "text"
        m.x = _num(attrd.get("data-x"))
        m.y = _num(attrd.get("data-y"))
        m.w = max(1.0, _num(attrd.get("data-w"), 360.0))
        m.h = max(1.0, _num(attrd.get("data-h"), 240.0))
        m.z = int(_num(attrd.get("data-z"), 1))
        m.bg = _clean_text(attrd.get("data-bg") or "paper", 24) or "paper"
        m.scale = _clamp(_num(attrd.get("data-scale"), 1.0), SCALE_MIN, SCALE_MAX)
        m.title = _clean_text(attrd.get("data-title"), MAX_TITLE_CHARS)
        m.cur = max(1, int(_num(attrd.get("data-cur"), 1)))
        m.href = _clean_text(attrd.get("data-href"))
        m.url = _clean_text(attrd.get("data-url"))
        m.article = _clean_text(attrd.get("data-article"))
        m.install = _clean_text(attrd.get("data-install"))
        m.refresh = _clean_text(attrd.get("data-refresh"), 16)
        m.cache = _clean_text(attrd.get("data-cache"))
        m.speaker = _clean_text(attrd.get("data-speaker"), 64)
        m.speaker_kind = _clean_text(attrd.get("data-speaker-kind"), 32)
        m.turn = _clean_text(attrd.get("data-turn"), 16)
        m.extra = _extra_attrs(attrd, _KNOWN_MODULE_ATTRS)
        self._module = m

    def _end_module(self) -> None:
        m = self._module
        self._module = None
        if m is None:
            return
        c = self.comp
        if not _MODULE_ID_RE.match(m.id) or c.module(m.id) is not None:
            bad = m.id or "(missing)"
            m.id = _new_module_id()
            c.warnings.append(
                f"module id {bad!r} was missing, malformed or duplicated — "
                f"reassigned {m.id}.")
        if m.type not in MODULE_TYPES:
            c.warnings.append(
                f"module {m.id} has unknown type {m.type!r} — kept as-is; "
                f"this enough renders it as a text card.")
        if m.bg not in BG_SWATCHES:
            c.warnings.append(
                f"module {m.id} has unknown background {m.bg!r} — kept "
                f"as-is; this enough renders it as paper.")
        # Renumber pages to 1..N: `data-n` is a convenience for a human
        # reading the file, not an identity, and a hand-edited file with
        # duplicate or missing numbers must still open.
        for i, page in enumerate(m.pages, start=1):
            page.n = i
        if not m.pages:
            m.pages = [Page(n=1)]
        m.cur = min(max(1, m.cur), len(m.pages))
        if len(c.modules) >= MAX_MODULES:
            c.warnings.append(
                f"more than {MAX_MODULES} modules in the file — the rest were "
                f"dropped on read.")
            return
        c.modules.append(m)

    def _start_page(self, attrd: dict[str, str]) -> None:
        if self._module is None:
            return
        page = Page()
        page.n = max(1, int(_num(attrd.get("data-n"), len(self._module.pages) + 1)))
        date = _clean_text(attrd.get("data-date"), 16)
        page.date = date if _DATE_RE.match(date or "") else None
        page.filed = str(attrd.get("data-filed") or "").strip() in ("1", "true", "yes")
        page.extra = _extra_attrs(attrd, _KNOWN_PAGE_ATTRS)
        self._page = page
        self._builder = _RichBuilder()
        self._page_divs = 0

    def _end_page(self) -> None:
        page, builder = self._page, self._builder
        self._page, self._builder = None, None
        self._page_divs = 0
        if page is None or builder is None or self._module is None:
            return
        page.rich = builder.result()
        if len(self._module.pages) >= MAX_PAGES_PER_MODULE:
            self.comp.warnings.append(
                f"module {self._module.id or '?'} has more than "
                f"{MAX_PAGES_PER_MODULE} pages — the rest were dropped on read.")
            return
        self._module.pages.append(page)

    def _stroke(self, attrd: dict[str, str]) -> None:
        c = self.comp
        if len(c.strokes) >= MAX_STROKES:
            return
        s = Stroke()
        s.id = (attrd.get("data-id") or "").strip().lower()
        if not _STROKE_ID_RE.match(s.id) or s.id in c.stroke_ids():
            s.id = _new_stroke_id()
        s.width = _clamp(_num(attrd.get("data-w"), 2.0), 0.1, 64.0)
        color = _clean_text(attrd.get("data-color") or "ink", 16)
        s.color = color if color in INK_COLORS else "ink"
        s.points = _parse_points(attrd.get("points") or "")
        if len(s.points) >= 2:
            c.strokes.append(s)

    def finish(self) -> Composure:
        c = self.comp
        title = " ".join("".join(self._title_parts).split())
        c.title = _clean_text(title, MAX_TITLE_CHARS) or "Untitled"
        if not c.created:
            c.created = _now_iso()
        if not c.modified:
            c.modified = c.created
        if not c.generator:
            c.generator = _generator()
        return c


def _parse_points(raw: str) -> list[tuple[float, float]]:
    """`"10,10 14,12"` → `[(10.0, 10.0), (14.0, 12.0)]`. Tolerant of the
    comma/space soup SVG permits; silently drops malformed pairs and caps
    the count."""
    nums: list[float] = []
    for tok in re.split(r"[,\s]+", (raw or "").strip()):
        if not tok:
            continue
        try:
            nums.append(float(tok))
        except ValueError:
            return _pair_up(nums)
        if len(nums) >= MAX_POINTS_PER_STROKE * 2:
            break
    return _pair_up(nums)


def _pair_up(nums: list[float]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i in range(0, len(nums) - 1, 2):
        x, y = nums[i], nums[i + 1]
        if x != x or y != y:
            continue
        out.append((x, y))
    return out[:MAX_POINTS_PER_STROKE]


def _json_or_none(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _jnum(value: float, places: int = 2) -> float | int:
    """A JSON number that survives a round trip and reads cleanly: `0`, not
    `0.0`. Stable because `json.loads` gives an int back and this returns
    the same int for it."""
    r = round(float(value), places)
    return int(r) if r == int(r) else r


def _clean_view(raw: Any) -> dict[str, float | int]:
    v = raw if isinstance(raw, dict) else {}
    return {
        "x": _jnum(_num(v.get("x"), 0.0), 2),
        "y": _jnum(_num(v.get("y"), 0.0), 2),
        "zoom": _jnum(_clamp(_num(v.get("zoom"), 1.0), 0.05, 8.0), 4),
    }


def _generator() -> str:
    from . import __version__
    return f"enough {__version__}"


def loads(text: str) -> Composure:
    """Parse `.comp` text into a `Composure`, sanitizing every page.

    Raises `ComposureError` only when the document is not a composure at all
    (no `data-composure` root) — malformed *content* is repaired and
    reported in `Composure.warnings`, never fatal, because refusing to open
    a file the user can see in their tree is the one failure mode with no
    recovery path."""
    raw = text or ""
    if len(raw.encode("utf-8", "ignore")) > MAX_FILE_BYTES:
        raise ComposureError(
            f"composure file is over the {MAX_FILE_BYTES // (1024 * 1024)} MB "
            f"cap — split it into linked composures (a `doc` module pointing "
            f"at another .comp drills down)."
        )
    if 'data-composure' not in raw[:4096]:
        raise ComposureError(
            "not a composure: the <html> tag must carry data-composure=\"1\". "
            "create one with new_composure instead of writing the file."
        )
    parser = _CompParser()
    parser.feed(raw)
    parser.close()
    return parser.finish()


def load(path: Path) -> Composure:
    try:
        return loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ComposureError(
            f"no composure at {path.name} — create one with new_composure "
            f"(form: {', '.join(SHIPPED_FORMS)})."
        ) from None


# ---------------------------------------------------------------------------
# Serialization
#
# Deterministic and readable: one module per block, pages indented one level
# inside it, attributes always in the same order. The `<style>` block is
# GENERATED on every write and never parsed back — it exists so that a
# `.comp` double-clicked in a file manager renders as the board it is.
# ---------------------------------------------------------------------------

_STYLE = """\
/* Generated by enough on every write — edits here are discarded.
   It exists so a .comp opened directly in a browser still reads as the
   board it is: absolutely-positioned modules, named swatch colors, ink on
   top. enough itself renders from the JSON model and ignores this. */
:root{--comp-fg:#1b1b1b;--comp-bg:#f4f2ee;--comp-line:#c9c4bb;
--sw-paper:#fffdf8;--sw-yellow:#fdf1a8;--sw-pink:#fbd5e2;--sw-blue:#d4e6f7;
--sw-green:#d6ecd2;--sw-orange:#fadcc0;--sw-lilac:#e2dcf5;--sw-gray:#e6e4e0;
--sw-ink:#2b2b2b;--sw-clear:transparent;
--ink-ink:#1b1b1b;--ink-red:#c0392b;--ink-blue:#2b6cb0;--ink-green:#3fa34d;
--ink-yellow:#c9a227}
@media (prefers-color-scheme:dark){:root{--comp-fg:#eceae6;--comp-bg:#1d1c1a;
--comp-line:#4a4742;--sw-paper:#282623;--sw-ink:#f2f0ec}}
html,body{margin:0;background:var(--comp-bg);color:var(--comp-fg);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.comp-canvas{position:relative;display:block;min-height:100vh}
.comp-ink{position:absolute;left:0;top:0;width:100%;height:100%;
overflow:visible;pointer-events:none;fill:none;stroke-linecap:round;
stroke-linejoin:round;z-index:2}
.comp-ink polyline{stroke:var(--ink-ink)}
.comp-ink polyline[data-color=red]{stroke:var(--ink-red)}
.comp-ink polyline[data-color=blue]{stroke:var(--ink-blue)}
.comp-ink polyline[data-color=green]{stroke:var(--ink-green)}
.comp-ink polyline[data-color=yellow]{stroke:var(--ink-yellow)}
.comp-module{position:absolute;box-sizing:border-box;overflow:hidden;
padding:16px;border:1px solid var(--comp-line);border-radius:6px;
background:var(--sw-paper)}
.comp-module[data-bg=yellow]{background:var(--sw-yellow)}
.comp-module[data-bg=pink]{background:var(--sw-pink)}
.comp-module[data-bg=blue]{background:var(--sw-blue)}
.comp-module[data-bg=green]{background:var(--sw-green)}
.comp-module[data-bg=orange]{background:var(--sw-orange)}
.comp-module[data-bg=lilac]{background:var(--sw-lilac)}
.comp-module[data-bg=gray]{background:var(--sw-gray)}
.comp-module[data-bg=ink]{background:var(--sw-ink);color:var(--comp-bg)}
.comp-module[data-bg=clear]{background:none;border-color:transparent}
.comp-module[data-w="816"]{padding:72px}
.comp-module[data-title]:not([data-title=""])::before{content:attr(data-title);
display:block;font-weight:600;margin-bottom:.4em;opacity:.75}
.comp-page{white-space:normal}
.comp-page+.comp-page{margin-top:1em;border-top:1px dashed var(--comp-line);
padding-top:1em}
.comp-page p{margin:0 0 .6em}
.comp-page h1,.comp-page h2,.comp-page h3,.comp-page h4{margin:.4em 0 .3em}
.comp-page pre{white-space:pre-wrap;background:rgba(0,0,0,.05);padding:.5em;
border-radius:4px}
.comp-page li[data-check]{list-style:none;margin-left:-1.2em}
.comp-page li[data-check="0"]::before{content:"\\2610  "}
.comp-page li[data-check="1"]::before{content:"\\2611  "}
.comp-page span[data-hl=yellow]{background:var(--sw-yellow)}
.comp-page span[data-hl=green]{background:var(--sw-green)}
.comp-page span[data-hl=blue]{background:var(--sw-blue)}
.comp-page span[data-hl=pink]{background:var(--sw-pink)}\
"""


def _attr(name: str, value: str) -> str:
    return f' {name}="{_html.escape(value, quote=True)}"'


def _meta_line(name: str, content: str) -> str:
    return f'<meta name="composure:{name}" content="{_html.escape(content, quote=True)}">'


def _meta_json(name: str, obj: Any) -> str:
    """A JSON-valued meta. Single-quoted like the format spec, with `'`
    entity-escaped so the attribute can never be closed early, and
    `sort_keys` so the same object always serializes to the same bytes."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False)
    safe = (raw.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace("'", "&#39;"))
    return f"<meta name=\"composure:{name}\" content='{safe}'>"


def _module_style(m: Module) -> str:
    """The inline `style` mirroring `data-*`, so a browser opening the file
    directly puts the box where it belongs. Regenerated on every write;
    never parsed back."""
    bits = [
        f"left:{_fmt(m.x)}px", f"top:{_fmt(m.y)}px",
        f"width:{_fmt(m.w)}px", f"height:{_fmt(m.h)}px",
        f"z-index:{m.z}",
    ]
    if abs(m.scale - 1.0) > 1e-9:
        bits.append(f"font-size:{_fmt(16 * m.scale)}px")
    return ";".join(bits)


def dumps(comp: Composure) -> str:
    """Serialize to `.comp` text. Deterministic: the same `Composure` always
    produces the same bytes, and `dumps(loads(x)) == x` for anything this
    function produced."""
    out: list[str] = [
        "<!doctype html>",
        f'<html lang="{_html.escape(comp.lang or "en", quote=True)}" data-composure="1">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_html.escape(comp.title or 'Untitled', quote=False)}</title>",
        f'<meta name="generator" content="'
        f'{_html.escape(comp.generator or _generator(), quote=True)}">',
        _meta_line("version", str(comp.version or FORMAT_VERSION)),
        _meta_line("form", comp.form or "blank"),
        _meta_line("kind", comp.kind if comp.kind in KINDS else "page"),
        _meta_line("rev", str(max(0, int(comp.rev)))),
        _meta_line("created", comp.created or _now_iso()),
        _meta_line("modified", comp.modified or comp.created or _now_iso()),
        _meta_json("view", _clean_view(comp.view)),
    ]
    if comp.council is not None:
        out.append(_meta_json("council", comp.council))
    for key in sorted(comp.meta_extra):
        out.append(_meta_line(key, comp.meta_extra[key]))
    out.append(f"<style>\n{_STYLE}\n</style>")
    out.append("</head>")
    out.append("<body>")
    out.append('<main class="comp-canvas">')

    out.append('<svg class="comp-ink" xmlns="http://www.w3.org/2000/svg">')
    for s in comp.strokes:
        pts = " ".join(f"{_fmt(x, 1)},{_fmt(y, 1)}" for x, y in s.points)
        out.append(
            f'<polyline{_attr("data-id", s.id)}{_attr("data-w", _fmt(s.width))}'
            f'{_attr("data-color", s.color)}{_attr("points", pts)}/>'
        )
    out.append("</svg>")

    for m in comp.modules:
        attrs = [
            _attr("data-id", m.id),
            _attr("data-type", m.type),
            _attr("data-x", _fmt(m.x)),
            _attr("data-y", _fmt(m.y)),
            _attr("data-w", _fmt(m.w)),
            _attr("data-h", _fmt(m.h)),
            _attr("data-z", str(int(m.z))),
            _attr("data-bg", m.bg),
            _attr("data-scale", _fmt(m.scale, 4)),
            _attr("data-title", m.title),
            _attr("data-cur", str(int(m.cur))),
        ]
        for name, value in (
            ("data-href", m.href), ("data-url", m.url),
            ("data-article", m.article), ("data-install", m.install),
            ("data-refresh", m.refresh), ("data-cache", m.cache),
            ("data-speaker", m.speaker), ("data-speaker-kind", m.speaker_kind),
            ("data-turn", m.turn),
        ):
            if value:
                attrs.append(_attr(name, value))
        for name in sorted(m.extra):
            attrs.append(_attr(name, m.extra[name]))
        attrs.append(_attr("style", _module_style(m)))
        out.append(f'<section class="comp-module"{"".join(attrs)}>')
        for page in m.pages:
            page_attrs = [_attr("data-n", str(int(page.n)))]
            if page.date:
                page_attrs.append(_attr("data-date", page.date))
            if page.filed:
                page_attrs.append(_attr("data-filed", "1"))
            for name in sorted(page.extra):
                page_attrs.append(_attr(name, page.extra[name]))
            out.append(
                f'  <div class="comp-page"{"".join(page_attrs)}>'
                f'{page.rich}</div>'
            )
        out.append("</section>")

    out += ["</main>", "</body>", "</html>", ""]
    return "\n".join(out)


def save(path: Path, comp: Composure) -> None:
    """Write atomically (tmp + rename), so a crash mid-write can never leave
    a half-parsed composure where a whole one was."""
    text = dumps(comp)
    size = len(text.encode("utf-8"))
    if size > MAX_FILE_BYTES:
        raise ComposureError(
            f"this change would make the file {size} bytes, over the "
            f"{MAX_FILE_BYTES} cap — remove modules or split the composure."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{secrets.token_hex(4)}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# The JSON document model — the frontend's contract
# ---------------------------------------------------------------------------

def page_model(page: Page) -> dict[str, Any]:
    return {
        "n": int(page.n),
        "rich": page.rich,
        "first_line": first_line(page.rich),
        "chars": len(page.rich),
        "date": page.date,
        "filed": bool(page.filed),
        "locked": bool(page.filed),
        "data": dict(page.extra),
    }


def module_model(m: Module) -> dict[str, Any]:
    return {
        "id": m.id,
        "type": m.type,
        "known_type": m.type in MODULE_TYPES,
        "x": round(m.x, 2), "y": round(m.y, 2),
        "w": round(m.w, 2), "h": round(m.h, 2),
        "z": int(m.z),
        "bg": m.bg,
        "known_bg": m.bg in BG_SWATCHES,
        "scale": round(m.scale, 4),
        "title": m.title,
        "cur": int(m.cur),
        "fields": {
            "href": m.href or None,
            "url": m.url or None,
            "article": m.article or None,
            "install": m.install or None,
            "refresh": m.refresh or None,
            "cache": m.cache or None,
        },
        "speaker": m.speaker or None,
        "speaker_kind": m.speaker_kind or None,
        "turn": m.turn or None,
        "locked": m.locked,
        "page_count": len(m.pages),
        "pages": [page_model(p) for p in m.pages],
        "data": dict(m.extra),
    }


def model(comp: Composure) -> dict[str, Any]:
    """The JSON document the frontend renders from.

    Every string in `pages[].rich` has been through `sanitize_rich`. The
    frontend still walks it with its own allowlist before insertion (decision
    3 in the plan) — that is belt and braces, not the only belt."""
    return {
        "version": int(comp.version or FORMAT_VERSION),
        "title": comp.title,
        "form": comp.form,
        "kind": comp.kind if comp.kind in KINDS else "page",
        "rev": int(comp.rev),
        "created": comp.created,
        "modified": comp.modified,
        "view": _clean_view(comp.view),
        "council": comp.council,
        "bounds": {k: round(v, 2) for k, v in comp.bounds().items()},
        "modules": [module_model(m) for m in comp.modules],
        "strokes": [
            {
                "id": s.id,
                "color": s.color,
                "width": round(s.width, 2),
                "points": [[round(x, 1), round(y, 1)] for x, y in s.points],
            }
            for s in comp.strokes
        ],
        "meta": dict(comp.meta_extra),
        "warnings": list(comp.warnings),
        "caps": dict(CAPS),
    }


# ---------------------------------------------------------------------------
# Placement and defaults
# ---------------------------------------------------------------------------

def _snap_up(value: float, grid: float = GRID) -> float:
    import math
    return math.ceil(value / grid) * grid


def _overlaps(a: tuple[float, float, float, float],
              b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def place_module(comp: Composure, w: float, h: float,
                 near: str | None = None) -> tuple[float, float]:
    """Pick a free slot for a `w × h` module: scan rightward, then down, on a
    24-unit grid, keeping a 48-unit gutter from every existing module.

    Starts at the bounding box of what is already there — or immediately to
    the right of `near`, when the caller has a module the new one belongs
    beside. Deterministic, so the same canvas always answers the same, which
    is what lets the frontend predict placement while a request is in
    flight. Falls back to "below everything" rather than overlapping."""
    boxes = [(m.x, m.y, m.w, m.h) for m in comp.modules]
    if not boxes:
        return (0.0, 0.0)
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[0] + b[2] for b in boxes)
    maxy = max(b[1] + b[3] for b in boxes)

    anchor = comp.module(near) if near else None
    if anchor is not None:
        start_x, start_y = anchor.x + anchor.w + GUTTER, anchor.y
    else:
        start_x, start_y = minx, miny

    def free(x: float, y: float) -> bool:
        cand = (x - GUTTER, y - GUTTER, w + 2 * GUTTER, h + 2 * GUTTER)
        return not any(_overlaps(cand, b) for b in boxes)

    y = _snap_up(start_y)
    y_limit = maxy + h + GUTTER * 2
    while y <= y_limit:
        x = _snap_up(start_x)
        x_limit = maxx + w + GUTTER * 2
        while x <= x_limit:
            if free(x, y):
                return (float(x), float(y))
            x += GRID
        y += GRID
    return (float(_snap_up(minx)), float(_snap_up(maxy + GUTTER)))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return 0.0
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def default_scale(comp: Composure) -> float:
    """A new module reads like the ones around it: the median scale of the
    existing modules, or 1 on an empty canvas."""
    if not comp.modules:
        return 1.0
    return snap_scale(_median([m.scale for m in comp.modules]))


def default_size(comp: Composure, mtype: str, scale: float) -> tuple[float, float]:
    """Median size of existing same-type modules, else the type's base size
    times the scale. Also the rule that keeps a board of cards tidy without
    anybody specifying geometry."""
    same = [m for m in comp.modules if m.type == mtype]
    if same:
        return (round(_median([m.w for m in same]), 2),
                round(_median([m.h for m in same]), 2))
    base_w, base_h = BASE_SIZE.get(mtype, BASE_SIZE["text"])
    return (round(base_w * scale, 2), round(base_h * scale, 2))


# --- the height heuristic -------------------------------------------------
#
# The server places modules, so it has to guess how tall a piece of text
# wants to be. It cannot measure — it has no font, no line-breaker and no
# idea what the user's ui scale is. So it estimates, deliberately generously,
# and the frontend corrects with an ordinary geometry `update_module` when it
# has laid the text out for real. Both the council transcript and
# `from_outline` use this one function, so a card and a statement are wrong
# in the same direction by the same amount, which is what keeps a column
# looking deliberate even before the correction lands.

#: Average glyph advance as a fraction of the em. 0.5 is a touch wide for a
#: humanist sans, which is the direction we want to be wrong in.
_EM_ADVANCE = 0.5
#: Line box as a multiple of the em — the static sheet's `line-height:1.5`.
_LINE_HEIGHT = 1.5
#: Rendered `data-title` above the body, when the module carries one.
_TITLE_BAND = 28.0
HEIGHT_MIN = 120.0
HEIGHT_MAX = 2400.0


def estimate_height(text: str, width: float, *, scale: float = 1.0,
                    pad: float | None = None, title: bool = False,
                    minimum: float = HEIGHT_MIN,
                    maximum: float = HEIGHT_MAX) -> float:
    """Guess the height a plain-text body wants inside a `width`-wide module.

    Wraps each paragraph at the character count that fits, adds a blank line
    between paragraphs, multiplies by the line box, and adds the padding the
    static sheet applies (72 for a fullport-width module, 16 otherwise —
    those are the two numbers in `_STYLE`). Rounded UP to the 24-unit grid so
    a column of statements lands on grid lines.

    Deterministic and monotone: more text is never shorter."""
    em = 16.0 * max(0.25, scale)
    if pad is None:
        pad = FULLPORT_PAD if width >= FULLPORT[0] else 16.0
    inner = max(em * 8, width - 2 * pad)
    per_line = max(8, int(inner / (em * _EM_ADVANCE)))
    lines = 0
    paragraphs = [p for p in re.split(r"\n\s*\n", (text or "").strip())]
    for i, para in enumerate(paragraphs):
        body = para.strip()
        if not body:
            continue
        # A hard-wrapped paragraph still has its own newlines; count the
        # longest of "what the source says" and "what the wrap needs".
        source_lines = body.count("\n") + 1
        lines += max(source_lines, -(-len(body) // per_line))
        if i < len(paragraphs) - 1:
            lines += 1
    lines = max(1, lines)
    h = 2 * pad + lines * em * _LINE_HEIGHT + (_TITLE_BAND if title else 0.0)
    h = _clamp(h, minimum, maximum)
    return float(_snap_up(h, GRID))


# ---------------------------------------------------------------------------
# Ops
#
# Every mutation is a validated dict. `apply_ops` is the single entry point:
# it validates the whole batch against a copy, applies it, and writes once.
# All or nothing — a batch that fails halfway leaves the file untouched.
# ---------------------------------------------------------------------------

OP_NAMES: tuple[str, ...] = (
    "add_module", "update_module", "remove_module",
    "set_page", "add_page", "remove_page", "file_page",
    "add_strokes", "remove_strokes", "replace_strokes",
    "set_meta", "set_council", "arrange",
)

#: Ops that write a module's text. Refused on a filed journal page and on an
#: engine-owned council statement (unless the council engine is the source).
_CONTENT_OPS = frozenset({"set_page", "add_page", "remove_page"})

SOURCES: tuple[str, ...] = ("ui", "readvisor", "council", "enough")


def _need(op: dict[str, Any], key: str, name: str) -> Any:
    if key not in op or op[key] in (None, ""):
        raise ComposureError(f"{name} needs a {key!r} field.")
    return op[key]


def _module_for(comp: Composure, op: dict[str, Any], key: str,
                op_name: str) -> Module:
    mid = str(_need(op, key, op_name)).strip()
    m = comp.module(mid)
    if m is None:
        known = ", ".join(x.id for x in comp.modules) or "(none)"
        raise ComposureError(
            f"no module {mid!r} on this composure. module ids: {known}.")
    return m


def _rich_from(op: dict[str, Any], op_name: str) -> str:
    """`rich` (already HTML) or `markdown` (converted). Exactly one; a call
    with both is a client bug worth naming rather than guessing about."""
    has_rich = "rich" in op and op["rich"] is not None
    has_md = "markdown" in op and op["markdown"] is not None
    if has_rich and has_md:
        raise ComposureError(
            f"{op_name} takes either 'rich' or 'markdown', not both.")
    if has_md:
        return md_to_rich(str(op["markdown"]))
    if has_rich:
        return sanitize_rich(str(op["rich"]))
    return ""


def _check_writable(comp: Composure, m: Module, page: Page | None,
                    source: str, op_name: str) -> None:
    if page is not None and page.filed:
        raise ComposureError(
            f"page {page.n} of module {m.id} was filed on {page.date} and is "
            f"permanently read-only — add a new page instead. (Comments on a "
            f"filed page are still allowed.)"
        )
    if m.locked and source != "council":
        raise ComposureError(
            f"module {m.id} is a council statement by {m.speaker!r} — the "
            f"council engine owns its text. You can move it, restyle it and "
            f"comment on it, but not rewrite it."
        )


def _claim_module_id(comp: Composure, raw: object) -> str:
    """Server-assigned unless the client supplies a valid, unused id — the
    canvas needs optimistic ids so a card can be dragged before the round
    trip lands."""
    if raw in (None, ""):
        return _new_module_id()
    mid = str(raw).strip().lower()
    if not _MODULE_ID_RE.match(mid):
        raise ComposureError(
            f"module id {mid!r} is not usable — ids look like 'm' followed by "
            f"1–15 lowercase letters or digits (e.g. m4f2a91c). Omit the field "
            f"to have one assigned."
        )
    if comp.module(mid) is not None:
        raise ComposureError(f"module id {mid!r} is already taken on this composure.")
    return mid


def _claim_stroke_id(comp: Composure, raw: object, taken: set[str]) -> str:
    if raw in (None, ""):
        sid = _new_stroke_id()
        while sid in taken:
            sid = _new_stroke_id()
        return sid
    sid = str(raw).strip().lower()
    if not _STROKE_ID_RE.match(sid):
        raise ComposureError(
            f"stroke id {sid!r} is not usable — ids look like 's' followed by "
            f"1–15 lowercase letters or digits.")
    if sid in taken:
        raise ComposureError(f"stroke id {sid!r} is already taken.")
    return sid


def _apply_one(comp: Composure, op: dict[str, Any], source: str) -> list[str]:
    """Apply one validated op, returning the module ids it touched.

    Ink ops report the sentinel id `"ink"` so an SSE consumer can tell
    "redraw the ink layer" from "refresh module m3" without diffing."""
    if not isinstance(op, dict):
        raise ComposureError("each op must be a JSON object with an 'op' field.")
    name = str(op.get("op") or "").strip()
    if name not in OP_NAMES:
        raise ComposureError(
            f"unknown op {name!r}. known ops: {', '.join(OP_NAMES)}.")

    if name == "add_module":
        return [_op_add_module(comp, op)]
    if name == "update_module":
        return [_op_update_module(comp, op, source)]
    if name == "remove_module":
        m = _module_for(comp, op, "id", "remove_module")
        _check_writable(comp, m, None, source, name)
        comp.modules = [x for x in comp.modules if x.id != m.id]
        return [m.id]
    if name in ("set_page", "add_page", "remove_page", "file_page"):
        return [_op_page(comp, op, name, source)]
    if name in ("add_strokes", "remove_strokes", "replace_strokes"):
        _op_strokes(comp, op, name)
        return ["ink"]
    if name == "set_meta":
        _op_set_meta(comp, op)
        return []
    if name == "set_council":
        _op_set_council(comp, op, source)
        return []
    if name == "arrange":
        return _op_arrange(comp, op)
    raise ComposureError(f"unknown op {name!r}.")  # pragma: no cover


def _op_add_module(comp: Composure, op: dict[str, Any]) -> str:
    if len(comp.modules) >= MAX_MODULES:
        raise ComposureError(
            f"this composure already holds {MAX_MODULES} modules, the cap. "
            f"Start a second composure and link to it with a `doc` module.")
    mtype = str(_need(op, "type", "add_module")).strip().lower()
    if mtype not in MODULE_TYPES:
        raise ComposureError(
            f"unknown module type {mtype!r}. types: {', '.join(MODULE_TYPES)}.")
    m = Module(id=_claim_module_id(comp, op.get("id")), type=mtype)
    m.scale = snap_scale(op["scale"]) if "scale" in op else default_scale(comp)
    if op.get("fullport"):
        m.w, m.h = FULLPORT
    else:
        dw, dh = default_size(comp, mtype, m.scale)
        m.w = round(max(1.0, _num(op.get("w"), dw)), 2)
        m.h = round(max(1.0, _num(op.get("h"), dh)), 2)
    if "x" in op or "y" in op:
        m.x = round(_num(op.get("x")), 2)
        m.y = round(_num(op.get("y")), 2)
    else:
        near = op.get("near")
        m.x, m.y = place_module(comp, m.w, m.h, str(near) if near else None)
    m.z = int(_num(op.get("z"), (max((x.z for x in comp.modules), default=0) + 1)))
    _set_common_fields(comp, m, op, creating=True)
    pages = op.get("pages")
    if isinstance(pages, list) and pages:
        if len(pages) > MAX_PAGES_PER_MODULE:
            raise ComposureError(
                f"a module holds at most {MAX_PAGES_PER_MODULE} pages.")
        m.pages = [
            Page(n=i, rich=_rich_from(p if isinstance(p, dict) else {}, "add_module"))
            for i, p in enumerate(pages, start=1)
        ]
    else:
        m.pages = [Page(n=1, rich=_rich_from(op, "add_module"))]
    m.cur = 1
    comp.modules.append(m)
    return m.id


def _set_common_fields(comp: Composure, m: Module, op: dict[str, Any],
                       *, creating: bool) -> None:
    """Apply the fields `add_module` and `update_module` share. Only keys
    actually present are touched, so a partial update is a patch."""
    if "bg" in op:
        bg = _clean_text(op["bg"], 24).lower()
        if bg not in BG_SWATCHES:
            raise ComposureError(
                f"unknown background {bg!r}. named swatches: "
                f"{', '.join(BG_SWATCHES)} (never a raw color — the frontend "
                f"maps names to theme-aware values).")
        m.bg = bg
    if "title" in op:
        m.title = _clean_text(op["title"], MAX_TITLE_CHARS)
    if "scale" in op and not creating:
        m.scale = snap_scale(op["scale"])
    if "refresh" in op:
        r = _clean_text(op["refresh"], 16).lower()
        if r and r not in REFRESH_MODES:
            raise ComposureError(
                f"unknown refresh mode {r!r}. modes: {', '.join(REFRESH_MODES)}.")
        m.refresh = r
    for key in ("href", "url", "article", "install", "cache",
                "speaker", "speaker_kind", "turn"):
        if key in op:
            setattr(m, key, _clean_text(op[key]))
    if m.type == "webframe" and not m.refresh:
        m.refresh = "manual"
    _validate_module_fields(m)


def _validate_module_fields(m: Module) -> None:
    """Per-type requirements, checked at the op door so a half-configured
    module never reaches disk."""
    if m.type in ("doc", "image") and m.href:
        if _href_ok(m.href) is None or m.href.lower().startswith(("http://", "https://", "mailto:")):
            raise ComposureError(
                f"a {m.type} module's href must be a project-relative path "
                f"(got {m.href!r}). Use a weblink module for an external URL.")
    if m.type in ("weblink", "webframe") and m.url:
        cleaned = _href_ok(m.url)
        if cleaned is None or not cleaned.lower().startswith(("http://", "https://")):
            raise ComposureError(
                f"a {m.type} module's url must be http(s) (got {m.url!r}).")


def _op_update_module(comp: Composure, op: dict[str, Any], source: str = "ui") -> str:
    m = _module_for(comp, op, "id", "update_module")
    # The speaker fields ARE the lock (`Module.locked` is `bool(speaker)`), so
    # only the council engine may set or clear them on an existing module.
    # Without this a `ui` batch could blank `speaker`, unlocking a statement,
    # and rewrite it on the next op — which would make the transcript a
    # suggestion rather than a record. Geometry, background, scale, title and
    # z are deliberately NOT gated: moving, restyling and re-sizing a
    # statement is exactly what the canvas is for (see `auto-height`).
    if source != "council":
        for key in ("speaker", "speaker_kind", "turn"):
            if key in op and _clean_text(op[key]) != getattr(m, key):
                raise ComposureError(
                    f"module {m.id}'s {key!r} is a council field — only the "
                    f"council engine sets it. You can move it, restyle it and "
                    f"comment on it.")
    if "type" in op:
        mtype = str(op["type"]).strip().lower()
        if mtype not in MODULE_TYPES:
            raise ComposureError(
                f"unknown module type {mtype!r}. types: {', '.join(MODULE_TYPES)}.")
        m.type = mtype
    for key in ("x", "y", "w", "h"):
        if key in op:
            value = round(_num(op[key], getattr(m, key)), 2)
            setattr(m, key, max(1.0, value) if key in ("w", "h") else value)
    if "z" in op:
        m.z = int(_num(op["z"], m.z))
    if "cur" in op:
        m.cur = int(_clamp(_num(op["cur"], m.cur), 1, len(m.pages)))
    _set_common_fields(comp, m, op, creating=False)
    return m.id


def _op_page(comp: Composure, op: dict[str, Any], name: str, source: str) -> str:
    m = _module_for(comp, op, "module", name)
    if name == "add_page":
        if len(m.pages) >= MAX_PAGES_PER_MODULE:
            raise ComposureError(
                f"module {m.id} already holds {MAX_PAGES_PER_MODULE} pages, "
                f"the cap — start a new module.")
        _check_writable(comp, m, None, source, name)
        rich = _rich_from(op, name)
        at = int(_num(op.get("n"), len(m.pages) + 1))
        at = int(_clamp(at, 1, len(m.pages) + 1))
        page = Page(n=at, rich=rich)
        if op.get("date"):
            date = _clean_text(op["date"], 16)
            if not _DATE_RE.match(date):
                raise ComposureError("page date must look like YYYY-MM-DD.")
            page.date = date
        m.pages.insert(at - 1, page)
        for i, p in enumerate(m.pages, start=1):
            p.n = i
        m.cur = at
        return m.id

    n = int(_num(_need(op, "n", name), 0))
    page = next((p for p in m.pages if p.n == n), None)
    if page is None:
        raise ComposureError(
            f"module {m.id} has no page {n} (it has {len(m.pages)}).")

    if name == "set_page":
        _check_writable(comp, m, page, source, name)
        page.rich = _rich_from(op, name)
        return m.id
    if name == "remove_page":
        _check_writable(comp, m, page, source, name)
        if len(m.pages) == 1:
            raise ComposureError(
                f"module {m.id} has one page — remove the module instead of "
                f"its last page.")
        m.pages = [p for p in m.pages if p.n != n]
        for i, p in enumerate(m.pages, start=1):
            p.n = i
        m.cur = int(_clamp(m.cur, 1, len(m.pages)))
        return m.id
    # file_page — the journal's one-way door.
    if page.filed:
        raise ComposureError(
            f"page {n} of module {m.id} was already filed on {page.date}.")
    date = _clean_text(op.get("date") or _today(), 16)
    if not _DATE_RE.match(date):
        raise ComposureError("file_page date must look like YYYY-MM-DD.")
    page.date = date
    page.filed = True
    return m.id


def _op_strokes(comp: Composure, op: dict[str, Any], name: str) -> None:
    remove_ids: list[str] = []
    add_raw: list[Any] = []
    if name == "add_strokes":
        add_raw = op.get("strokes") or []
    elif name == "remove_strokes":
        remove_ids = [str(i).strip().lower() for i in (op.get("ids") or [])]
    else:  # replace_strokes — the eraser's split, atomic by construction
        remove_ids = [str(i).strip().lower() for i in (op.get("remove") or [])]
        add_raw = op.get("add") or []
    if not isinstance(add_raw, list):
        raise ComposureError(f"{name} expects a list of strokes.")
    if remove_ids:
        drop = set(remove_ids)
        comp.strokes = [s for s in comp.strokes if s.id not in drop]
    taken = comp.stroke_ids()
    for raw in add_raw:
        if not isinstance(raw, dict):
            raise ComposureError("each stroke must be a JSON object.")
        points = _coerce_points(raw.get("points"))
        if len(points) < 2:
            raise ComposureError(
                "a stroke needs at least 2 points, as [[x,y], [x,y], …].")
        if len(comp.strokes) >= MAX_STROKES:
            raise ComposureError(
                f"this composure already holds {MAX_STROKES} strokes, the cap.")
        color = _clean_text(raw.get("color") or "ink", 16).lower()
        if color not in INK_COLORS:
            raise ComposureError(
                f"unknown ink color {color!r}. colors: {', '.join(INK_COLORS)}.")
        sid = _claim_stroke_id(comp, raw.get("id"), taken)
        taken.add(sid)
        comp.strokes.append(Stroke(
            id=sid,
            width=round(_clamp(_num(raw.get("width"), 2.0), 0.1, 64.0), 2),
            color=color,
            points=points,
        ))


def _coerce_points(raw: object) -> list[tuple[float, float]]:
    if isinstance(raw, str):
        return _parse_points(raw)
    if not isinstance(raw, list):
        return []
    out: list[tuple[float, float]] = []
    for item in raw[:MAX_POINTS_PER_STROKE]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((round(_num(item[0]), 1), round(_num(item[1]), 1)))
        elif isinstance(item, dict) and "x" in item and "y" in item:
            out.append((round(_num(item["x"]), 1), round(_num(item["y"]), 1)))
    return out


def _op_set_meta(comp: Composure, op: dict[str, Any]) -> None:
    if "title" in op:
        comp.title = _clean_text(op["title"], MAX_TITLE_CHARS) or "Untitled"
    if "kind" in op:
        kind = _clean_text(op["kind"], 16).lower()
        if kind not in KINDS:
            raise ComposureError(
                f"unknown kind {kind!r}. kinds: {', '.join(KINDS)}.")
        comp.kind = kind
    if "view" in op:
        comp.view = _clean_view(op["view"])


def _op_set_council(comp: Composure, op: dict[str, Any], source: str) -> None:
    """Write the `composure:council` meta. Engine-only.

    `set_meta` deliberately refuses `form` and `council`; this is the council
    engine's own door, and it is closed to every other source for the same
    reason a statement's text is: the setup card, the participant list and
    the status are the engine's state machine, not decoration a client can
    edit underneath it. Pass `null` to clear it (which is how a composure
    stops being a council)."""
    if source != "council":
        raise ComposureError(
            "set_council is the council engine's op — use the "
            "/api/council/* endpoints, which own the state machine.")
    if "council" not in op:
        raise ComposureError("set_council needs a 'council' object (or null).")
    value = op["council"]
    if value is None:
        comp.council = None
        return
    if not isinstance(value, dict):
        raise ComposureError("set_council's 'council' must be a json object.")
    # Round-tripped verbatim through `dumps`/`loads`; the engine validates
    # its own shape before it ever gets here.
    comp.council = json.loads(json.dumps(value, sort_keys=True))


def _op_arrange(comp: Composure, op: dict[str, Any]) -> list[str]:
    """Grid or single-column auto-layout of a named module list. The ids
    keep their order, which is what makes `arrange` a reorder tool as well
    as a tidy-up: the list you pass is the reading order you get.

    `pack: true` (column mode only) stacks each module directly under the
    previous one using its OWN height instead of a uniform row height. That
    is what a council transcript needs — statements are wildly different
    lengths, and a uniform row leaves a short one floating in a pool of
    whitespace the size of the longest."""
    ids = op.get("ids")
    if not isinstance(ids, list) or not ids:
        raise ComposureError("arrange needs a non-empty 'ids' list.")
    mods = []
    for raw in ids:
        mid = str(raw).strip()
        m = comp.module(mid)
        if m is None:
            raise ComposureError(f"arrange: no module {mid!r} on this composure.")
        mods.append(m)
    mode = str(op.get("mode") or "grid").strip().lower()
    if mode not in ("grid", "column"):
        raise ComposureError("arrange mode must be 'grid' or 'column'.")
    gutter = _clamp(_num(op.get("gutter"), GUTTER), 0.0, 1000.0)
    origin_x = round(_num(op.get("x"), mods[0].x), 2)
    origin_y = round(_num(op.get("y"), mods[0].y), 2)
    if mode == "column":
        cols = 1
    else:
        import math
        cols = int(_num(op.get("cols"), 0)) or max(1, int(math.ceil(len(mods) ** 0.5)))
    if mode == "column" and op.get("pack"):
        y = origin_y
        for m in mods:
            m.x = round(origin_x, 2)
            m.y = round(y, 2)
            y += m.h + gutter
        return [m.id for m in mods]
    col_w = max(m.w for m in mods)
    row_h = max(m.h for m in mods)
    for i, m in enumerate(mods):
        m.x = round(origin_x + (i % cols) * (col_w + gutter), 2)
        m.y = round(origin_y + (i // cols) * (row_h + gutter), 2)
    return [m.id for m in mods]


# ---------------------------------------------------------------------------
# Concurrency: per-path write locks + a short rev history for stale merges
# ---------------------------------------------------------------------------

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

#: rev → the module ids that batch changed, per path. Bounded; a client
#: whose `base_rev` has fallen out of the window is told to refresh whole.
_HISTORY: dict[str, deque[tuple[int, list[str]]]] = {}
_HISTORY_LIMIT = 200


def path_lock(path: Path) -> threading.Lock:
    """The write lock for one composure file. Hold it across the whole
    load → mutate → save. Same contract as `girraph.path_lock`."""
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def _record_history(path: Path, rev: int, changed: list[str]) -> None:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        ring = _HISTORY.setdefault(key, deque(maxlen=_HISTORY_LIMIT))
        ring.append((rev, list(changed)))


def changed_since(path: Path, base_rev: int, current_rev: int) -> list[str] | None:
    """Module ids changed in (base_rev, current_rev], or None when the
    window no longer covers `base_rev` (server restart, or a very stale
    client) and the caller must refresh everything."""
    key = str(path.resolve())
    with _LOCKS_GUARD:
        ring = list(_HISTORY.get(key) or ())
    if base_rev >= current_rev:
        return []
    covered = [r for r, _ids in ring if r > base_rev]
    if not covered or min(covered) > base_rev + 1:
        return None
    out: list[str] = []
    for rev, ids in ring:
        if rev > base_rev:
            for i in ids:
                if i not in out:
                    out.append(i)
    return out


@dataclass
class OpsResult:
    """What one applied batch tells its caller (and, through it, the SSE
    event and the HTTP reply)."""
    path: str
    rev: int
    changed: list[str]
    stale: bool
    stale_changed: list[str] | None
    created: bool
    composure: Composure


def apply_ops(
    path: Path,
    base_rev: int | None,
    ops: list[dict[str, Any]],
    *,
    source: str = "ui",
    create: bool = False,
    form: str = "blank",
    title: str = "",
    project_dir: Path | None = None,
    rel_path: str = "",
) -> OpsResult:
    """Apply a batch of ops to the composure at `path`, atomically.

    The single write door. Everything — the canvas, the readvisor tools, the
    council engine — comes through here.

    - The whole batch is validated and applied against a **copy**; only a
      batch that succeeds end to end is written (tmp + rename).
    - One batch bumps `rev` by one, whatever it contains.
    - `base_rev` behind the file's rev is **not an error**. Ops are
      last-writer-wins per module, so the batch still lands; the result
      carries `stale=True` plus the module ids that moved under the caller,
      and the client refreshes those.
    - `create=True` materializes a composure that `POST /api/composure/new`
      only ever described — the lazy-create rule that keeps a
      never-edited new composure from writing a file.
    """
    if source not in SOURCES:
        raise ComposureError(
            f"unknown op source {source!r}. sources: {', '.join(SOURCES)}.")
    if not isinstance(ops, list):
        raise ComposureError("'ops' must be a list of op objects.")
    if not ops:
        raise ComposureError("'ops' is empty — nothing to apply.")

    created = False
    with path_lock(path):
        if path.exists():
            comp = load(path)
        elif create:
            comp = new_composure(form=form, title=title,
                                 project_dir=project_dir)
            created = True
        else:
            raise ComposureError(
                f"no composure at {rel_path or path.name} — send create:true "
                f"with the first op batch, or call new_composure first.")

        file_rev = comp.rev
        stale = base_rev is not None and int(base_rev) < file_rev
        stale_changed = (
            changed_since(path, int(base_rev), file_rev) if stale else []
        )

        draft = copy.deepcopy(comp)
        changed: list[str] = []
        for i, op in enumerate(ops):
            try:
                for mid in _apply_one(draft, op, source):
                    if mid not in changed:
                        changed.append(mid)
            except ComposureError as e:
                raise ComposureError(
                    f"op {i + 1} of {len(ops)} ({(op or {}).get('op', '?')}) "
                    f"failed and the whole batch was discarded: {e}"
                ) from None

        draft.rev = file_rev + 1
        draft.modified = _now_iso()
        draft.generator = _generator()
        save(path, draft)
        _record_history(path, draft.rev, changed)
        return OpsResult(
            path=rel_path or path.name,
            rev=draft.rev,
            changed=changed,
            stale=bool(stale),
            stale_changed=stale_changed,
            created=created,
            composure=draft,
        )


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

SHIPPED_FORMS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "composure-forms"
PROJECT_FORMS_REL = "rness/composure-forms"
COMPOSURE_DIR_REL = "rness/io/composure"


def shipped_forms_dir() -> Path:
    return SHIPPED_FORMS_DIR


def project_forms_dir(project_dir: Path) -> Path:
    return project_dir / PROJECT_FORMS_REL


def list_forms(project_dir: Path | None = None) -> list[dict[str, Any]]:
    """Shipped forms first, then project forms. A project form with the same
    name as a shipped one wins — the override pattern enough uses
    everywhere (defaults + project-local)."""
    out: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for origin, folder in (("shipped", shipped_forms_dir()),
                           ("project", project_forms_dir(project_dir) if project_dir else None)):
        if folder is None or not folder.is_dir():
            continue
        for p in sorted(folder.glob(f"*{SUFFIX}")):
            name = p.stem
            try:
                comp = load(p)
            except (ComposureError, OSError) as e:
                log.warning("composure form %s unreadable (%s)", p, e)
                continue
            if name not in out:
                order.append(name)
            out[name] = {
                "name": name,
                "origin": origin,
                "title": comp.title,
                "kind": comp.kind,
                "modules": len(comp.modules),
                "path": str(p),
            }
    return [out[name] for name in order]


def form_path(name: str, project_dir: Path | None = None) -> Path | None:
    """Resolve a form name to a file, project-local winning. Name-validated:
    a form name is a plain slug, never a path."""
    slug = _clean_text(name, 64)
    if not slug or slug != slugify(slug, 64):
        return None
    if project_dir is not None:
        candidate = project_forms_dir(project_dir) / f"{slug}{SUFFIX}"
        if candidate.is_file():
            return candidate
    candidate = shipped_forms_dir() / f"{slug}{SUFFIX}"
    return candidate if candidate.is_file() else None


def new_composure(form: str = "blank", title: str = "",
                  project_dir: Path | None = None) -> Composure:
    """A fresh composure from a form. Nothing is written — the caller
    decides whether this one ever reaches disk."""
    src = form_path(form or "blank", project_dir)
    if src is None:
        known = ", ".join(f["name"] for f in list_forms(project_dir)) or "(none)"
        raise ComposureError(
            f"no composure form named {form!r}. available forms: {known}.")
    comp = load(src)
    comp.form = src.stem
    comp.rev = 0
    comp.created = _now_iso()
    comp.modified = comp.created
    comp.generator = _generator()
    clean = _clean_text(title, MAX_TITLE_CHARS)
    if clean:
        comp.title = clean
    if comp.form == "journal" and not clean:
        comp.title = "Journal"
    return comp


def new_path(project_dir: Path, title: str, when: str = "") -> str:
    """The project-relative path a new composure gets:
    `rness/io/composure/<slug>-<YYYY-MM-DD>[-n].comp`. Never overwrites."""
    folder = project_dir / COMPOSURE_DIR_REL
    stamp = when or _today()
    base = f"{slugify(title or 'untitled')}-{stamp}"
    candidate = folder / f"{base}{SUFFIX}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{base}-{n}{SUFFIX}"
        n += 1
        if n > 999:  # pragma: no cover — a thousand composures in one day
            raise ComposureError(
                "too many composures with that name today — give it a title.")
    return f"{COMPOSURE_DIR_REL}/{candidate.name}"


def save_as_form(project_dir: Path, comp: Composure, name: str) -> Path:
    """Write a copy of `comp` into `rness/composure-forms/` as a reusable
    form. The rev/dates are reset so every composure made from it starts
    clean."""
    slug = slugify(name, 48)
    if not slug or slug == "untitled" and not (name or "").strip():
        raise ComposureError("a form needs a name.")
    folder = project_forms_dir(project_dir)
    folder.mkdir(parents=True, exist_ok=True)
    clone = copy.deepcopy(comp)
    clone.form = slug
    clone.rev = 0
    clone.created = _now_iso()
    clone.modified = clone.created
    dest = folder / f"{slug}{SUFFIX}"
    save(dest, clone)
    return dest


def list_composures(project_dir: Path) -> list[dict[str, Any]]:
    """Every `.comp` in the project, newest first. Cheap: the head of each
    file carries everything the list needs, but the files are small enough
    that a full parse is simpler and still instant at any plausible count."""
    out: list[dict[str, Any]] = []
    root = project_dir.resolve()
    for p in sorted(root.rglob(f"*{SUFFIX}")):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        try:
            comp = load(p)
            stat = p.stat()
        except (ComposureError, OSError) as e:
            log.warning("composure %s unreadable (%s)", p, e)
            continue
        out.append({
            "path": str(p.relative_to(root)).replace(os.sep, "/"),
            "title": comp.title,
            "form": comp.form,
            "kind": comp.kind,
            "rev": comp.rev,
            "modules": len(comp.modules),
            "modified": comp.modified,
            "mtime": stat.st_mtime,
        })
    out.sort(key=lambda r: (r["modified"] or "", r["mtime"]), reverse=True)
    return out


# ---------------------------------------------------------------------------
# Comments — a sidecar beside the file, like highlights
# ---------------------------------------------------------------------------

COMMENT_STATES: tuple[str, ...] = ("anchored", "module", "orphaned")


def comments_path(comp_path: Path) -> Path:
    """`board.comp` → `.board.comp.comments.json`, in the same directory.
    Hidden (so the tree walker skips it) and co-located (so moving or
    deleting the composure through the app can carry or drop exactly its
    own comments)."""
    return comp_path.parent / f".{comp_path.name}.comments.json"


def load_comments(comp_path: Path, doc_rel: str = "") -> dict[str, Any]:
    p = comments_path(comp_path)
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("comments"), list):
                doc.setdefault("version", 1)
                doc.setdefault("doc_path", doc_rel or comp_path.name)
                return doc
        except (OSError, json.JSONDecodeError) as e:
            log.warning("composure comments unreadable at %s (%s)", p, e)
    return {"version": 1, "doc_path": doc_rel or comp_path.name, "comments": []}


def _save_comments(comp_path: Path, doc: dict[str, Any]) -> None:
    p = comments_path(comp_path)
    if not doc.get("comments"):
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _normalize_anchor(anchor: dict[str, Any] | None) -> dict[str, Any]:
    """Two anchor kinds, mirroring wikisink's degrade story: a `quote`
    anchor pins to selected text inside one page (with prefix/suffix to
    break ties), a `module` anchor pins to the box itself. A quote that no
    longer matches degrades to its module; a module that is gone leaves the
    comment orphaned, listed but unplaced. Comments are never auto-deleted."""
    a = anchor or {}
    kind = a.get("type") if a.get("type") in ("quote", "module") else "module"
    return {
        "type": kind,
        "module": _clean_text(a.get("module"), 32),
        "page": int(_num(a.get("page"), 1)),
        "quote": str(a.get("quote") or "")[:2000],
        "prefix": str(a.get("prefix") or "")[-60:],
        "suffix": str(a.get("suffix") or "")[:60],
    }


def add_comment(comp_path: Path, body: str, anchor: dict[str, Any] | None,
                doc_rel: str = "") -> dict[str, Any]:
    doc = load_comments(comp_path, doc_rel)
    a = _normalize_anchor(anchor)
    entry = {
        "id": f"c_{secrets.token_hex(4)}",
        "body": str(body or ""),
        "created_at": _now_iso(),
        "updated_at": None,
        "resolved": False,
        "replies": [],
        "anchor": a,
        "state": "anchored" if (a["type"] == "quote" and a["quote"]) else "module",
    }
    doc["comments"].append(entry)
    _save_comments(comp_path, doc)
    return entry


def update_comment(comp_path: Path, comment_id: str, *, body: str | None = None,
                   resolved: bool | None = None, state: str | None = None,
                   doc_rel: str = "") -> dict[str, Any]:
    doc = load_comments(comp_path, doc_rel)
    entry = next((c for c in doc["comments"] if c.get("id") == comment_id), None)
    if entry is None:
        raise KeyError(comment_id)
    if body is not None:
        entry["body"] = str(body)
        entry["updated_at"] = _now_iso()
    if resolved is not None:
        entry["resolved"] = bool(resolved)
    if state is not None and state in COMMENT_STATES:
        entry["state"] = state
    _save_comments(comp_path, doc)
    return entry


def add_reply(comp_path: Path, comment_id: str, body: str,
              doc_rel: str = "") -> dict[str, Any]:
    doc = load_comments(comp_path, doc_rel)
    entry = next((c for c in doc["comments"] if c.get("id") == comment_id), None)
    if entry is None:
        raise KeyError(comment_id)
    reply = {"id": f"r_{secrets.token_hex(4)}", "body": str(body or ""),
             "created_at": _now_iso()}
    entry.setdefault("replies", []).append(reply)
    _save_comments(comp_path, doc)
    return reply


def delete_comment(comp_path: Path, comment_id: str, doc_rel: str = "") -> None:
    doc = load_comments(comp_path, doc_rel)
    before = len(doc["comments"])
    doc["comments"] = [c for c in doc["comments"] if c.get("id") != comment_id]
    if len(doc["comments"]) == before:
        raise KeyError(comment_id)
    _save_comments(comp_path, doc)


def write_denial(target: Path) -> str | None:
    """Why a whole-file write to `target` is refused, or None.

    Both existing write doors (`POST /api/file` and the `write_file` tool)
    call this. `.comp` files change only through node-level ops, so a user
    typing in one module and a readvisor rewriting another never clobber
    each other; the comments sidecar is backend-owned like every other
    sidecar in enough."""
    name = target.name
    if name.endswith(".comp.comments.json") and name.startswith("."):
        return (
            "error: composure comments are backend-owned metadata, not a "
            "file to write. use the composure comment endpoints (the comments "
            "slider in the canvas) instead."
        )
    if target.suffix == SUFFIX:
        return (
            "error: .comp (composure) files are edited module-by-module, "
            "never written whole — that is what lets you and the user work on "
            "the same canvas at once. use comp_add_module / comp_set_page / "
            "comp_update_module / comp_remove_module / comp_arrange, and "
            "read_composure to see the current state. to start a new one, "
            "call new_composure with a form "
            f"({', '.join(SHIPPED_FORMS)})."
        )
    return None


def move_sidecars(src: Path, dest: Path) -> None:
    """Carry a composure's comments sidecar alongside a rename or move. The
    app owns both files; a rename that left the comments behind would orphan
    every thread on the document."""
    src_side = comments_path(src)
    if src_side.is_file():
        dest_side = comments_path(dest)
        dest_side.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src_side, dest_side)


# ---------------------------------------------------------------------------
# Outline — what a small local model reads
# ---------------------------------------------------------------------------

def outline(comp: Composure, path_rel: str = "") -> str:
    """A compact, stable text view of a composure.

    Written for a 16K-context local model: one line per module, ids it can
    quote back in an op, geometry rounded to whole units, and the first line
    of page 1 as the content hint. Never grows with page text — that is what
    `read_composure <path> <module> <page>` is for."""
    head = [
        f"composure: {comp.title}",
        f"path: {path_rel or '(unsaved)'}",
        f"form: {comp.form} · kind: {comp.kind} · rev: {comp.rev} · "
        f"{len(comp.modules)} module(s) · {len(comp.strokes)} ink stroke(s)",
    ]
    if comp.council:
        status = comp.council.get("status") if isinstance(comp.council, dict) else None
        head.append(f"council: status {status or 'unknown'}")
    lines = [*head, ""]
    if not comp.modules:
        lines.append("(no modules yet — comp_add_module puts the first one down)")
        return "\n".join(lines)
    for m in comp.modules:
        where = f"({_fmt(m.x, 0)},{_fmt(m.y, 0)} {_fmt(m.w, 0)}×{_fmt(m.h, 0)})"
        bits = [f"{m.id}  {m.type:<8} {where} {m.bg}"]
        if m.title:
            bits.append(f'"{m.title}"')
        target = m.href or m.url or m.article
        if target:
            bits.append(f"→ {target}")
        if len(m.pages) > 1:
            bits.append(f"{len(m.pages)} pages")
        if m.locked:
            bits.append(f"[{m.speaker}, turn {m.turn or '?'} — read-only]")
        filed = [p for p in m.pages if p.filed]
        if filed:
            bits.append(f"[{len(filed)} filed]")
        snippet = first_line(m.pages[0].rich, 80) if m.pages else ""
        if snippet:
            bits.append(f"— {snippet}")
        lines.append("  ".join(bits))
    return "\n".join(lines)


def page_markdown(comp: Composure, module_id: str, n: int | None = None) -> str:
    """Full text of one module (or one of its pages) as markdown — what the
    readvisor gets when it asks past the outline."""
    m = comp.module(module_id)
    if m is None:
        known = ", ".join(x.id for x in comp.modules) or "(none)"
        raise ComposureError(f"no module {module_id!r}. module ids: {known}.")
    pages = m.pages if n is None else [p for p in m.pages if p.n == n]
    if not pages:
        raise ComposureError(
            f"module {module_id} has no page {n} (it has {len(m.pages)}).")
    chunks: list[str] = []
    for p in pages:
        header = f"### page {p.n}"
        if p.date:
            header += f" — {p.date}{' (filed)' if p.filed else ''}"
        chunks.append(header + "\n\n" + (rich_to_md(p.rich) or "(empty)\n"))
    title = m.title or m.id
    return f"## {title} ({m.type}, {m.id})\n\n" + "\n".join(chunks)


# ---------------------------------------------------------------------------
# Outline → composure (P5b)
#
# Small local models are unreliable at long chains of module tool calls — ask
# for fourteen cards and you get nine, two of them in the wrong group and one
# a duplicate. So structure is produced as MARKDOWN, in one shot, and turned
# into a board deterministically here. The grammar is exactly the one
# `defaults/skills/scaffold/SKILL.md` teaches; its two worked examples are
# test fixtures, which is what keeps the skill and the parser honest about
# each other.
# ---------------------------------------------------------------------------

#: A card at this width reads as a card. Everything in the scaffold/cards
#: layouts is a multiple of it.
CARD_W = 320.0
#: The group's name card. Short, fixed, and `gray` so a column reads as a
#: column even at the zoom where bodies have greeked out to their faces.
HEADER_H = 96.0
#: Between cards in a stack, between columns, and between bands.
CARD_GAP = 24.0
COL_GAP = 48.0
BAND_GAP = 72.0
#: Past this a group is two columns rather than a mile-high stack. Twelve
#: cards at ~200 units each is already 2 400 units of scrolling; the wrap is
#: what keeps a fifty-beat act readable on one screen at fit-all.
MAX_CARDS_PER_COLUMN = 12
#: A single card never gets taller than this — a long body is a signal the
#: writer has a scene where they meant to have a beat, and letting one card
#: run to 2 000 units would hide that by making it look normal.
CARD_H_MAX = 600.0

#: Group names that span the top band of a `scaffold` composure, and those
#: that form the bottom row. Taken from SKILL.md's rule ("premise, logline or
#: thesis" / "ending, endings, denouement or resolution"); `close` is in the
#: bottom set because `references/structure.md`'s worked example B says in so
#: many words that `Close` sits along the bottom.
TOP_GROUPS: frozenset[str] = frozenset({"premise", "logline", "thesis"})
BOTTOM_GROUPS: frozenset[str] = frozenset(
    {"ending", "endings", "denouement", "denouements", "resolution",
     "resolutions", "close"})

#: A card whose text starts with this is the writer's own open question.
GAP_PREFIX = "[gap"
GAP_TITLE = "gap"
GAP_BG = "orange"

OUTLINE_FORMS: tuple[str, ...] = ("scaffold", "cards", "blank")

_OUTLINE_BULLET_RE = re.compile(r"^(\s*)(?:[-*+]|\d{1,3}[.)])\s+(.*)$")
_OUTLINE_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class OutlineCard:
    title: str = ""
    body: str = ""

    @property
    def is_gap(self) -> bool:
        probe = (self.title or self.body).lstrip().lower()
        return probe.startswith(GAP_PREFIX)

    def text(self) -> str:
        """What goes on the card. A gap card keeps its bracketed question as
        the first line of the body — the title becomes the word "gap", and
        losing the question would make the most useful card on the canvas the
        only blank one."""
        if self.is_gap:
            head = self.title.strip()
            return f"{head}\n\n{self.body}".strip() if self.body else head
        return self.body.strip()


@dataclass
class OutlineGroup:
    name: str = ""
    cards: list[OutlineCard] = field(default_factory=list)


@dataclass
class OutlineDoc:
    title: str = ""
    groups: list[OutlineGroup] = field(default_factory=list)
    source: str = ""

    def card_count(self) -> int:
        return sum(len(g.cards) for g in self.groups)


def parse_outline(markdown: str) -> OutlineDoc:
    """Parse the scaffold skill's outline grammar. Four rules and nothing
    else:

    - one `# ` line is the composure title;
    - each `## ` is a group;
    - each `### `, and each top-level list item under a group, is a card;
    - everything under a card until the next heading or top-level item is
      that card's body.

    `####` and deeper, tables, front matter and nested list items are not
    structure — they stay in the body as the text they are. A `### ` before
    any `## ` opens an implicit group named "Cards", because refusing an
    outline over a missing header helps nobody."""
    doc = OutlineDoc(source=markdown or "")
    group: OutlineGroup | None = None
    card: OutlineCard | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal card, body
        if card is not None:
            card.body = "\n".join(body).strip()
            body = []
            card = None
        else:
            body = []

    def ensure_group() -> OutlineGroup:
        nonlocal group
        if group is None:
            group = OutlineGroup(name="Cards")
            doc.groups.append(group)
        return group

    for raw in (markdown or "").splitlines():
        line = raw.rstrip()
        heading = _OUTLINE_HEADING_RE.match(line.strip()) if line.strip() else None
        if heading and len(heading.group(1)) == 1:
            flush()
            if not doc.title:
                doc.title = heading.group(2).strip()
            continue
        if heading and len(heading.group(1)) == 2:
            flush()
            group = OutlineGroup(name=heading.group(2).strip())
            doc.groups.append(group)
            continue
        if heading and len(heading.group(1)) == 3:
            flush()
            card = OutlineCard(title=heading.group(2).strip())
            ensure_group().cards.append(card)
            continue
        bullet = _OUTLINE_BULLET_RE.match(raw)
        if bullet and not bullet.group(1):      # top level only
            flush()
            card = OutlineCard(title=bullet.group(2).strip())
            ensure_group().cards.append(card)
            continue
        if card is not None:
            # Strip the indent a list item's continuation lines carry, so a
            # body written under a bullet is not read back as a code block.
            body.append(raw[4:] if raw.startswith("    ") else
                        (raw[2:] if raw.startswith("  ") else raw))
        # Text before the first card is preamble and is dropped — the skill's
        # own examples never put any there, and guessing where it belongs is
        # how an outline turns into a surprise.
    flush()
    doc.groups = [g for g in doc.groups if g.cards or g.name]
    return doc


def _outline_card_ops(card: OutlineCard, mid: str, x: float, y: float,
                      w: float) -> dict[str, Any]:
    text = card.text()
    gap = card.is_gap
    h = estimate_height(text, w, pad=16.0, title=True,
                        minimum=HEIGHT_MIN, maximum=CARD_H_MAX)
    return {
        "op": "add_module", "type": "text", "id": mid,
        "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": h,
        "bg": GAP_BG if gap else "paper",
        "title": GAP_TITLE if gap else card.title,
        "markdown": text,
    }


def _outline_header_op(name: str, mid: str, x: float, y: float,
                       w: float) -> dict[str, Any]:
    return {
        "op": "add_module", "type": "text", "id": mid,
        "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": HEADER_H,
        "bg": "gray", "title": name, "markdown": "",
    }


def _column_slots(group: OutlineGroup) -> int:
    """How many column slots a group needs. Over twelve cards it wraps into
    a second (or third) column beside itself rather than growing downward."""
    return max(1, -(-len(group.cards) // MAX_CARDS_PER_COLUMN))


def outline_ops(doc: OutlineDoc, form: str = "scaffold",
                *, clear_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """The op batch that turns a parsed outline into a board.

    Deterministic: every id, coordinate and size is a function of the text.
    `clear_ids` are removed first — a form ships placeholder modules, and a
    scaffolded composure wants the form's kind and styling, not its prompts.
    """
    form = (form or "scaffold").strip().lower()
    if form not in OUTLINE_FORMS:
        raise ComposureError(
            f"unknown outline form {form!r}. forms: {', '.join(OUTLINE_FORMS)} "
            f"(scaffold = columns, cards = rows, blank = one page).")
    if not doc.groups and form != "blank":
        raise ComposureError(
            "that outline has no groups. The grammar is: one '# ' title, a "
            "'## ' per group, and a '### ' (or a top-level list item) per "
            "card. Nothing else is parsed.")
    ops: list[dict[str, Any]] = [
        {"op": "remove_module", "id": mid} for mid in (clear_ids or [])
    ]
    if doc.title:
        ops.append({"op": "set_meta", "title": doc.title})

    if form == "blank":
        ops.append({"op": "set_meta", "kind": "page"})
        ops.append({"op": "add_module", "type": "text", "id": "m1",
                    "x": 0, "y": 0, "fullport": True, "bg": "paper",
                    "title": doc.title, "markdown": doc.source.strip()})
        return ops

    ops.append({"op": "set_meta", "kind": "board"})
    counter = [0]

    def nid() -> str:
        counter[0] += 1
        return f"m{counter[0]}"

    if form == "cards":
        y = 0.0
        for group in doc.groups:
            ops.append(_outline_header_op(group.name or "Cards", nid(), 0.0, y,
                                          CARD_W))
            row_h = HEADER_H
            x = CARD_W + COL_GAP
            for card in group.cards:
                op = _outline_card_ops(card, nid(), x, y, CARD_W)
                row_h = max(row_h, float(op["h"]))
                ops.append(op)
                x += CARD_W + CARD_GAP
            y += row_h + BAND_GAP
        _check_outline_caps(ops)
        return ops

    # scaffold — bands top and bottom, columns in between
    top = next((g for g in doc.groups if g.name.strip().lower() in TOP_GROUPS), None)
    bottom = next((g for g in doc.groups
                   if g is not top and g.name.strip().lower() in BOTTOM_GROUPS), None)
    columns = [g for g in doc.groups if g is not top and g is not bottom]
    slots = sum(_column_slots(g) for g in columns) or 1
    span = slots * CARD_W + (slots - 1) * COL_GAP

    y = 0.0
    if top is not None:
        ops.append(_outline_header_op(top.name, nid(), 0.0, y, span))
        band_y = y + HEADER_H + CARD_GAP
        band, band_h = _band_ops(top, nid, band_y, span)
        ops += band
        y = band_y + band_h + BAND_GAP

    col_top = y
    col_bottom = y
    x = 0.0
    for group in columns:
        slot_count = _column_slots(group)
        for slot in range(slot_count):
            chunk = group.cards[slot * MAX_CARDS_PER_COLUMN:
                                (slot + 1) * MAX_CARDS_PER_COLUMN]
            name = group.name if slot == 0 else f"{group.name} (cont.)"
            ops.append(_outline_header_op(name or "Cards", nid(), x, col_top,
                                          CARD_W))
            cy = col_top + HEADER_H + CARD_GAP
            for card in chunk:
                op = _outline_card_ops(card, nid(), x, cy, CARD_W)
                cy += float(op["h"]) + CARD_GAP
                ops.append(op)
            col_bottom = max(col_bottom, cy)
            x += CARD_W + COL_GAP

    if bottom is not None:
        by = col_bottom + BAND_GAP
        ops.append(_outline_header_op(bottom.name, nid(), 0.0, by, span))
        band_y = by + HEADER_H + CARD_GAP
        band, _h = _band_ops(bottom, nid, band_y, span)
        ops += band
    _check_outline_caps(ops)
    return ops


def _band_ops(group: OutlineGroup, nid: Any, y: float,
              span: float) -> tuple[list[dict[str, Any]], float]:
    """A band's cards, in one row, sharing the span. One card fills it.
    Returns the ops and the band's height."""
    n = max(1, len(group.cards))
    w = max(CARD_W, (span - (n - 1) * CARD_GAP) / n)
    out: list[dict[str, Any]] = []
    x = 0.0
    tallest = 0.0
    for card in group.cards:
        op = _outline_card_ops(card, nid(), x, y, w)
        tallest = max(tallest, float(op["h"]))
        out.append(op)
        x += w + CARD_GAP
    return out, tallest


def _check_outline_caps(ops: list[dict[str, Any]]) -> None:
    adds = sum(1 for o in ops if o.get("op") == "add_module")
    if adds > MAX_MODULES:
        raise ComposureError(
            f"that outline would make {adds} cards and a composure holds "
            f"{MAX_MODULES}. Split it: one composure per part, linked with "
            f"`doc` modules, or fewer cards per group.")


def from_outline(title: str, form: str, markdown: str) -> Composure:
    """`title` + `form` + a markdown outline → a laid-out composure.

    The pure half of the `composure_from_outline` tool: no file, no project,
    no ops door — a `Composure` you can render, diff or assert about. The
    tool applies the same ops (from `outline_ops`) through `apply_ops` so the
    write goes through the one door like everything else.

    The form supplies the kind and the styling, not its placeholder modules:
    those are removed, because a scaffold of somebody's actual story should
    not arrive with "Act one goes here" still sitting on it."""
    doc = parse_outline(markdown)
    clean = _clean_text(title, MAX_TITLE_CHARS)
    if clean:
        doc.title = clean
    if not doc.title:
        doc.title = "Untitled"
    comp = new_composure(form if form in OUTLINE_FORMS else "blank", doc.title)
    ops = outline_ops(doc, form, clear_ids=[m.id for m in comp.modules])
    for i, op in enumerate(ops):
        try:
            _apply_one(comp, op, "readvisor")
        except ComposureError as e:
            raise ComposureError(
                f"outline op {i + 1} of {len(ops)} ({op.get('op')}) failed: {e}"
            ) from None
    comp.form = form if form in OUTLINE_FORMS else comp.form
    return comp
