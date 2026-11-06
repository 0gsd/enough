"""DocOES export: a doc volume as static HTML at the three densities (Thym 0.5.0, lane X1).

    python -m enough.docoes export <doc> <out-dir> [--lang en] [--densities short,atem,fabula]
        [--page short=short.html] [--page atem=atem.html] [--page fabula=fabula.html]
        [--standalone] [--slug S] [--name N] [--version V] [--no-marks] [--reference]
        [--sources ROOT] [--docs-root DIR]

`<doc>` is a registered document (`macrocosm-oes`, `help-center`) or a markdown path inside the sources root
(`docs/THYM.md`): a path whose default slug names a registered document exports that document (chapters, reference
and all); any other is exported ad hoc, and so is a path given with an explicit `--slug`, even one that names a
registered document (cosmoes-site builds the public editions that way, from texts kept outside enough). `--no-marks`
leaves out the margin marks (`◂ N` mentioned in N places, `❏ N` examples: the in-app viewer's buttons, inert in a
static page); `--reference` joins the reference generated from the MiniCOSM manifests to an ad hoc document, as the
registered MacroCOSM OES carries it. The volume is built fresh — into a temporary directory unless `--docs-root`
is given, never into `docs_root()` — and read back through `macrocosm.load_volume`, so the export sees exactly what
the app would. Written to `<out-dir>`:

    manifest.json            merged across runs: one entry per exported document (format docoes-export/1)
    docs.css                 the fragments' styles (everything under .docoes)
    <slug>/short.html        the readable manual: every section, xrefs, term links, margin marks, the glossary
    <slug>/atem.html         one line per section: the outline, the glossary, the reference and the checks
    <slug>/fabula.html       every item of the volume as a static card

A fragment is one `<article class="docoes docoes-<density>">`: no <html>, <head>, <script>, <style> or style=
attribute, exactly one <h1>, every id unique, every in-page `href="#…"` resolving inside it, no timestamp (the
manifest alone carries one), so unchanged sources give byte-identical fragments. The rules of the short density are
the in-app viewer's (enough/static/index.html, "The docs viewer": `docsIndex`, `DOCS_XREF_RE`, `DOCS_XREF_RULES`,
`docsXrefResolve`, `docsLinkTerms`), ported here; the in-app viewer is unchanged and nothing in the app calls this.

The standard library, markdown-it-py (imported when an export runs; it is in enough's uv.lock via rich),
`enough.docoes` and `enough.macrocosm`.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import docoes as D
from . import macrocosm as mc

FORMAT = "docoes-export/1"
DENSITIES = ("short", "atem", "fabula")
DEFAULT_PAGES = {d: f"{d}.html" for d in DENSITIES}
CSS_NAME = "docs.css"
MANIFEST_NAME = "manifest.json"


class ExportError(Exception):
    """A refusal with an exit code: 2 for a bad document, telling, density or out-dir; 1 for a refused volume."""

    def __init__(self, msg: str, code: int = 2):
        super().__init__(msg)
        self.code = code


def _esc(s: Any) -> str:
    """Text and double-quoted attribute values escaped as markdown-it escapes them: & < > and "."""
    return html.escape("" if s is None else str(s), quote=False).replace('"', "&quot;")


def item_id(key: str) -> str:
    """The HTML id of an item, the same at every density: `docs-item-` + the key lower-cased, every run of
    non-alphanumerics a hyphen (`T:term/part` → `docs-item-t-term-part`)."""
    return "docs-item-" + (re.sub(r"[^a-z0-9]+", "-", str(key).lower()).strip("-") or "x")


# ---------------------------------------------------------------------------
# The app's rules, ported (index.html, "The docs viewer")
# ---------------------------------------------------------------------------

def strip_comments(src: str) -> str:
    """`docsStripComments`: whole-line `<!-- … -->` outside fenced code dropped (the enumeration's markers); a
    fence keeps its comments (the spec quotes the markers in its examples)."""
    out, fence = [], False
    for line in str(src).split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        if not fence and re.match(r"^\s*<!--.*-->\s*$", line):
            continue
        out.append(line)
    return "\n".join(out)


# `DOCS_XREF_RULES`: where "§N", "README §N" and "P.N" point, by the scope a sentence is written in ('' = the
# document, else a chapter's prefix). An unlisted document or scope links all three forms to its own scope.
XREF_RULES: dict[str, dict[str, dict[str, str | None]]] = {
    # MacroCOSM OES: §N, README §N and P.N name sections of other documents (Comprise OES, the paradigm map, both
    # published at their own homes since 0.5.4): never linked to its own sections.
    "macrocosm-oes": {"": {"para": None, "readme": None, "letter": None}},
    # Comprise OES: § only for other documents (never linked); P.N its own chapter P.
    "comprise-oes": {"": {"para": None, "readme": None, "letter": ""}},
}

# `DOCS_XREF_RE`: "section 7.3" and its five translations, lists and ranges ("sections 4 to 14", "4, 5 and 7"),
# "第 3 节", "§4.1" (+ "README §3"), a lettered "P.3.1". Groups: 1 the "section" list, 2 the zh number, 3 "README ",
# 4 the § list, 5-6 letter + number. JS's \b and \d are ASCII: spelled out so Python's Unicode classes do not widen.
_NUM = r"[0-9]+(?:\.[0-9]+)*"
_JOIN = (r"\s*(?:,|–|—|-|~|～|〜|、|and|or|to|through|bis|und|oder|à|et|ou|a|y|o|al|hasta"
         r"|から|と|至|到|和|及|与)\s*")
_LIST = _NUM + "(?:" + _JOIN + _NUM + ")*"
_WB_BEFORE = r"(?<![A-Za-z0-9_])"
_WB_AFTER = r"(?![A-Za-z0-9_])"
# "its section N" (0.5.4) is another document's section — "Thym (https://thym.cosmoes.org/), its section 15" — and is
# never linked to the citing document's own; the core's `_SEC_REF` skips the same form.
_NOT_ITS = r"(?<![Ii]ts )"
XREF_RE = re.compile(
    r"(?:" + _NOT_ITS + _WB_BEFORE + r"(?:sections?|secci[oó]n(?:es)?|Abschnitt(?:en|e)?)\s+|セクション\s*)(" + _LIST + ")"
    r"|第\s*(" + _NUM + r")\s*节"
    r"|(README\s+)?§§?\s*(" + _LIST + ")"
    r"|" + _WB_BEFORE + r"([A-Z])\.(" + _NUM + ")" + _WB_AFTER, re.I)
_NUM_RE = re.compile(_NUM)
_CJK = re.compile("[぀-ヿ㐀-鿿豈-﫿]")


def _term_norm(s: str) -> str:
    """`docsTermNorm`: lower-cased, NFKC, whitespace collapsed."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s).lower())).strip()


def _distinctive(word: str) -> bool:
    """`docsTermDistinctive`: a space, an inner capital or digit, or a symbol."""
    return bool(re.search(r"\s", word) or re.search(r".[A-Z0-9]", word)
                or any(not (c.isalnum() or c.isspace()) for c in word))


@dataclass
class _Matchers:
    names: dict                      # normalised form -> (term item, form as written)
    latin: re.Pattern | None
    wide: re.Pattern | None

    def lookup(self, text: str):
        k = _term_norm(text)
        return (self.names.get(k) or (self.names.get(k[:-2]) if k.endswith("es") else None)
                or (self.names.get(k[:-1]) if k.endswith("s") else None))


@dataclass
class _Ctx:
    key: str                         # the section being rendered
    scope: str                       # '' or its chapter's prefix
    done: set = field(default_factory=set)
    stats: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# markdown-it-py, lazily
# ---------------------------------------------------------------------------

def _markdown():
    try:
        from markdown_it import MarkdownIt
        from markdown_it.token import Token
    except ImportError as e:                            # pragma: no cover - the lock installs it
        raise ExportError("the export needs markdown-it-py (it is in enough's uv.lock, via rich): run "
                          "`uv sync --frozen` in the checkout, or `pip install markdown-it-py`", 1) from e
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    md.disable("lheading")       # DocOES knows ATX headings only: "text\n---" stays a paragraph and a rule

    def table_open(self, tokens, idx, options, env):
        return '<div class="docs-table">\n' + self.renderToken(tokens, idx, options, env)

    def table_close(self, tokens, idx, options, env):
        return self.renderToken(tokens, idx, options, env) + "</div>\n"

    md.add_render_rule("table_open", table_open)
    md.add_render_rule("table_close", table_close)
    return md, Token


# ---------------------------------------------------------------------------
# One volume, three densities
# ---------------------------------------------------------------------------

_CONVERT = "{{convert-formats}}"
_CONVERT_MARK = "DOCOESCONVERTFORMATSNOTE"
_CONVERT_NOTE = "(the formats table is drawn in the app)"
_TREE_FIELDS = frozenset({"parts", "parent", "chapter"})
_MENTION_FIELDS = frozenset({"mentions", "about", "see", "same_as", "also_defined_in"})
_CARD_SKIP = frozenset({"name", "atem", "body", "heading", "eol", "lines", "order"})


def _order(it: mc.Item) -> int:
    o = it.data.get("order")
    return o if isinstance(o, int) and not isinstance(o, bool) else 0


#: How the texts name the two groups of formats (MacroCOSM OES 18, 19): a format is a built-in of the core, or a MiniCOSM.
FORMAT_GROUPS = {True: "built-ins", False: "MiniCOSMs"}


def _format_group(it: Any) -> str:
    """The group of a reference format item (`R:minicosm/<name>`): its `core` says which."""
    return FORMAT_GROUPS[it.data.get("core") is True]


def _plural(kind: str) -> str:
    return kind + ("es" if kind.endswith(("s", "x", "ch", "sh")) else "s")


class Exporter:
    """The three fragments of one loaded doc volume. `pages` maps a density to the href the fragments use for
    links across densities; `densities` are the ones this run writes (a link to one it does not is left out)."""

    def __init__(self, vol: mc.Volume, doc: D.Document, lang: str, *, pages: dict | None = None,
                 densities: tuple = DENSITIES, marks: bool = True):
        self.vol, self.doc, self.lang = vol, doc, lang
        self.marks = marks
        self.pages = {**DEFAULT_PAGES, **(pages or {})}
        self.densities = tuple(densities)
        self.md, self.Token = _markdown()
        self.distinctive = doc.plain_mentions == "distinctive"
        self.rules = XREF_RULES.get(doc.slug, {})
        items = list(vol.items.values())
        self.items = items
        self.by_key = {it.key: it for it in items}
        self.by_id = {it.id: it for it in items}
        self.chapters = [c for c in vol.catalog.get("chapters") or [] if isinstance(c, dict)]
        self.prefix = {str(c.get("id")): str(c.get("prefix") or str(c.get("id")).split("/")[-1])
                       for c in self.chapters}
        self.secs = sorted((it for it in items if it.kind == "section"), key=_order)
        self.terms = [it for it in items if it.kind == "term"]
        # `docsIndex`: heading ids from the anchors, scoped by chapter; numbers by (scope, number).
        self.scope: dict[str, str] = {}
        self.dom: dict[str, str] = {}
        self.num: dict[tuple, str] = {}
        used: set[str] = set()
        for s in self.secs:
            ch = s.data.get("chapter")
            scope = (self.prefix.get(ch) or "chapter") if ch else ""
            self.scope[s.key] = scope
            base = "docs-" + (scope + "-" if scope else "") + str(s.data.get("anchor") or "section")
            hid, n = base, 2
            while hid in used:
                hid, n = f"{base}-{n}", n + 1
            used.add(hid)
            self.dom[s.key] = hid
            if s.data.get("number") is not None and str(s.data.get("number")) != "":
                self.num[(scope, str(s.data["number"]))] = s.key
        # Item ids, unique across the volume (a collision of two keys' spellings takes -2, -3 in volume order).
        self.iid: dict[str, str] = {}
        taken = set(used)
        for it in items:
            base = item_id(it.key)
            iid, n = base, 2
            while iid in taken:
                iid, n = f"{base}-{n}", n + 1
            taken.add(iid)
            self.iid[it.key] = iid
        # Margin marks, as the server's short payload counts them.
        self.mentioned: dict[str, set] = {}
        for it in items:
            for a, b, label, style in mc._edges(vol, {}, it):
                if style == "tree" or label in _TREE_FIELDS or a.key == b.key:
                    continue
                lab = label if style == "ref" else f"link:{label}"
                if lab in _MENTION_FIELDS or lab.startswith("link:"):
                    self.mentioned.setdefault(b.key, set()).add(a.key)
        self.examples: dict[str, list] = {}
        for it in items:
            if it.kind == "example" and isinstance(it.data.get("in"), str):
                self.examples.setdefault(it.data["in"], []).append(it.id)
        self.root = next((s for s in self.secs if not s.data.get("chapter") and s.data.get("level") == 1), None)
        self._matchers: dict[str, _Matchers | None] = {}
        # What a markdown `#…` link may land on in the short fragment (others lose their link).
        self._all_ids = set(self.dom.values()) | {self.iid[t.key] for t in self.terms}

    # ---- helpers ----

    def _page(self, density: str) -> str | None:
        return self.pages.get(density, DEFAULT_PAGES[density]) if density in self.densities else None

    def _name(self) -> str:
        """The document's name: the catalog's (a registered document's, `--name`, else the H1's text)."""
        return self.vol.name

    def _title(self) -> str:
        """The page's h1 at atem and fabula, as the app's: the root heading's name (a telling's own words)."""
        return (self.root.name if self.root is not None else "") or self.vol.name

    def _sec_label(self, sec: mc.Item) -> str:
        num = sec.data.get("number")
        return (f"§{num} " if num not in (None, "") else "") + sec.name

    def _wrap(self, density: str, contents: list, body: str) -> str:
        return (f'<article class="docoes docoes-{density}" data-doc="{_esc(self.doc.slug)}" '
                f'data-density="{density}" data-lang="{_esc(self.lang)}">\n'
                + self._contents(contents) + '\n<div class="docoes-body">\n' + body + '\n</div>\n</article>\n')

    @staticmethod
    def _contents(entries: list) -> str:
        """`docsBuildToc`: lvl2 entries with their lvl3 nested."""
        out = ['<nav class="docoes-contents" aria-label="Contents"><ol>']
        open_li = in_sub = False
        for lvl, hid, label, chapter in entries:
            a = f'<a href="#{_esc(hid)}">{_esc(label)}</a>'
            if lvl == 2:
                if in_sub:
                    out.append("</ol>")
                    in_sub = False
                if open_li:
                    out.append("</li>")
                out.append(f'<li class="lvl2{" chapter" if chapter else ""}">{a}')
                open_li = True
            elif not open_li:
                out.append(f'<li class="lvl3">{a}</li>')
            else:
                if not in_sub:
                    out.append("<ol>")
                    in_sub = True
                out.append(f'<li class="lvl3">{a}</li>')
        if in_sub:
            out.append("</ol>")
        if open_li:
            out.append("</li>")
        out.append("</ol></nav>")
        return "".join(out)

    # ---- term matching (`docsTermMatchers`) ----

    def _term_scope(self, tm: mc.Item) -> str:
        ch = tm.data.get("chapter")
        return (self.prefix.get(ch) or "chapter") if ch else ""

    def matchers(self, scope: str) -> _Matchers | None:
        if scope in self._matchers:
            return self._matchers[scope]
        own = [t for t in self.terms if self._term_scope(t) == scope]
        doc = [t for t in self.terms if scope != "" and self._term_scope(t) == ""]
        names: dict[str, tuple] = {}
        for tm in own + doc:
            name = str(tm.data.get("name") or "").strip()
            if not name:
                continue
            forms = [name]
            bare = re.sub(r"^(the|a|an)\s+", "", name, flags=re.I)
            if bare != name and len(bare) > 2:
                forms.append(bare)
            for f in forms:
                k = _term_norm(f)
                if k not in names:
                    names[k] = (tm, f)

        def esc(n: str) -> str:
            return r"\s+".join(re.escape(p) for p in n.split(" "))

        keys = sorted(names, key=len, reverse=True)
        latin = [n for n in keys if not _CJK.search(n)]
        wide = [n for n in keys if _CJK.search(n)]
        mt = None
        if latin or wide:
            mt = _Matchers(
                names,
                re.compile(r"(^|\W)(" + "|".join(esc(n) + ("(?:e?s)?" if n[-1:].isalpha() else "") for n in latin)
                           + r")(?!\w)", re.I) if latin else None,
                re.compile(r"()(" + "|".join(esc(n) for n in wide) + ")") if wide else None)
        self._matchers[scope] = mt
        return mt

    # ---- inline text: xrefs, then terms ----

    def _id_of(self, scope: str | None, num: str) -> str | None:
        if scope is None:
            return None
        key = self.num.get((scope, num))
        return self.dom.get(key) if key else None

    def _xref_spans(self, text: str, scope: str) -> list[tuple]:
        """`docsXrefResolve` over every match: (at, length, target id, a later number of a list)."""
        rules = {"para": scope, "readme": scope, "letter": scope, **self.rules.get(scope, {})}
        out: list[tuple] = []
        for m in XREF_RE.finditer(text):
            def listing(g: int, sc: str | None) -> None:
                first = True
                for k in _NUM_RE.finditer(m.group(g)):
                    hid = self._id_of(sc, k.group(0))
                    at = m.start(g) + k.start()
                    if hid:
                        out.append((m.start(), at + len(k.group(0)) - m.start(), hid, False) if first
                                   else (at, len(k.group(0)), hid, True))
                    first = False
            if m.group(1):
                listing(1, scope)
            elif m.group(2):
                hid = self._id_of(scope, m.group(2))
                if hid:
                    out.append((m.start(), len(m.group(0)), hid, False))
            elif m.group(4):
                listing(4, rules["readme"] if m.group(3) else rules["para"])
            elif m.group(5) and re.fullmatch("[A-Z]", m.group(5)):
                hid = self._id_of(rules["letter"], m.group(5) + "." + m.group(6))
                if hid:
                    out.append((m.start(), len(m.group(0)), hid, False))
        return out

    def _terms_html(self, text: str, ctx: _Ctx, bold: bool) -> str:
        """`docsLinkTerms` on one text node."""
        mt = self.matchers(ctx.scope)
        if mt is None or not text:
            return _esc(text)
        hits: list[tuple] = []
        for rx in (mt.latin, mt.wide):
            if rx is None:
                continue
            for m in rx.finditer(text):
                word, at = m.group(2), m.start(2)
                hit = mt.lookup(word)
                tm = hit[0] if hit else None
                if tm is None or tm.key in ctx.done or tm.data.get("defined_in") == ctx.key:
                    continue
                if self.distinctive and not _distinctive(word) and \
                        not (bold and at == 0 and word[:1] == hit[1][:1]):
                    continue
                if any(at < h[0] + h[1] and h[0] < at + len(word) for h in hits):
                    continue
                hits.append((at, len(word), tm))
                ctx.done.add(tm.key)
        if not hits:
            return _esc(text)
        hits.sort(key=lambda h: h[0])
        out, last = [], 0
        for at, n, tm in hits:
            out.append(_esc(text[last:at]))
            title = tm.data.get("atem") or tm.data.get("summary") or ""
            out.append(f'<a class="docs-term" href="#{self.iid[tm.key]}" data-term="{_esc(tm.key)}" '
                       f'title="{_esc(title)}">{_esc(text[at:at + n])}</a>')
            ctx.stats["term_links"] = ctx.stats.get("term_links", 0) + 1
            last = at + n
        out.append(_esc(text[last:]))
        return "".join(out)

    def _linked(self, text: str, ctx: _Ctx, bold: bool) -> str:
        out, last = [], 0
        for at, n, hid, later in self._xref_spans(text, ctx.scope):
            if at < last:
                continue
            out.append(self._terms_html(text[last:at], ctx, bold))
            cls = "ref-xref ref-xref-num" if later else "ref-xref"
            out.append(f'<a class="{cls}" href="#{hid}">{_esc(text[at:at + n])}</a>')
            ctx.stats["xref_links"] = ctx.stats.get("xref_links", 0) + 1
            last = at + n
        out.append(self._terms_html(text[last:], ctx, bold))
        return "".join(out)

    def _inline(self, children: list, ctx: _Ctx) -> list:
        """An inline token's children with every text node outside a link (runs of text and soft breaks: one DOM
        text node) linked."""
        out: list = []
        run: list = []
        links: list[bool] = []                          # per open link: kept (True) or dropped
        strong = 0

        def flush() -> None:
            if run:
                text = "".join(t.content if t.type == "text" else "\n" for t in run)
                out.append(self.Token("html_inline", "", 0, content=self._linked(text, ctx, strong > 0)))
                run.clear()

        for t in children or []:
            if t.type in ("text", "softbreak") and not links:
                run.append(t)
                continue
            flush()
            if t.type == "link_open":
                href = t.attrGet("href") or ""
                keep = True
                if isinstance(href, str) and href.startswith("#"):
                    frag = href[1:]
                    target = frag if frag in self._all_ids else ("docs-" + frag if "docs-" + frag in self._all_ids
                                                                 else None)
                    if target:
                        t.attrSet("href", "#" + target)
                    else:
                        keep = False
                links.append(keep)
                if not keep:
                    t.hidden = True
            elif t.type == "link_close" and links:
                if not links.pop():
                    t.hidden = True
            elif t.type == "strong_open":
                strong += 1
            elif t.type == "strong_close":
                strong = max(0, strong - 1)
            out.append(t)
        flush()
        return out

    # ---- short ----

    def _heading_level(self, sec: mc.Item) -> int:
        level = sec.data.get("level") if isinstance(sec.data.get("level"), int) else 2
        if sec.data.get("chapter"):
            return min(level + 1, 6)                    # a chapter's "#" is a part of this volume: h2
        if level == 1 and sec is not self.root:
            return 2
        return max(1, min(level, 6))

    def _toc_level(self, sec: mc.Item) -> int:
        level = sec.data.get("level")
        if sec.data.get("chapter"):
            return 2 if level == 1 else 3 if level == 2 else 0
        return 2 if level == 2 else 3 if level == 3 else 0

    def _marks(self, sec: mc.Item) -> str:
        if not self.marks:
            return ""
        m = len(self.mentioned.get(sec.key, ()))
        x = len(self.examples.get(sec.id, []))
        if not (m or x):
            return ""
        spans = []
        if m:
            spans.append(f'<span class="docs-mark" title="mentioned in {m} place{"" if m == 1 else "s"}">◂ {m}</span>')
        if x:
            spans.append(f'<span class="docs-mark" title="{x} example{"" if x == 1 else "s"}">❏ {x}</span>')
        return '<p class="docs-marks">' + " ".join(spans) + "</p>\n"

    def _section(self, sec: mc.Item, contents: list, stats: dict) -> str:
        d = sec.data
        heading = d.get("heading") if isinstance(d.get("heading"), str) else None
        src = strip_comments((heading + "\n" if heading is not None else "") + str(d.get("body") or ""))
        convert = _CONVERT in src
        if convert:
            src = src.replace(_CONVERT, _CONVERT_MARK)
        env: dict = {}
        tokens = self.md.parse(src, env)
        ctx = _Ctx(sec.key, self.scope[sec.key], stats=stats)
        hid = self.dom[sec.key]
        has_head = heading is not None and bool(tokens) and tokens[0].type == "heading_open"
        for i, t in enumerate(tokens):
            if t.type == "inline" and not (i > 0 and tokens[i - 1].type == "heading_open"):
                t.children = self._inline(t.children, ctx)
        pre, post = "", ""
        ch = d.get("chapter")
        if ch and d.get("level") == 1:
            c = next((c for c in self.chapters if c.get("id") == ch), None)
            if c is not None:
                pre = (f'<p class="docs-chapter-note">a chapter of this volume, synced read-only from '
                       f'{_esc(c.get("source") or c.get("path") or "")} @ {_esc(c.get("commit") or "?")}</p>\n')
        if has_head:
            tag = f"h{self._heading_level(sec)}"
            tokens[0].tag = tag
            for t in tokens[1:]:
                if t.type == "heading_close":
                    t.tag = tag
                    break
            tokens[0].attrSet("id", hid)
            lvl = self._toc_level(sec)
            if lvl:
                tokens[0].attrSet("data-toc", str(lvl))
                label = " ".join(self.md.renderer.renderInlineAsText(tokens[1].children or [], self.md.options,
                                                                     env).split())
                contents.append((lvl, hid, label or sec.name, bool(ch and d.get("level") == 1)))
            post = self._marks(sec)
            if d.get("fallback"):
                post += '<p class="docs-fb">told in English</p>\n'
            close = next(i for i, t in enumerate(tokens) if t.type == "heading_close")
            if post:
                tokens.insert(close + 1, self.Token("html_block", "", 0, content=post))
        body = self.md.renderer.render(tokens, self.md.options, env)
        if convert:
            body = body.replace(f"<p>{_CONVERT_MARK}</p>", f'<p class="docs-note">{_esc(_CONVERT_NOTE)}</p>')
            body = body.replace(_CONVERT_MARK, _esc(_CONVERT_NOTE))
        attrs = f' id="{hid}"' if not has_head else ""
        return (f'<section class="docs-sec" data-key="{_esc(sec.key)}" data-scope="{_esc(self.scope[sec.key])}"'
                f'{attrs}>\n{pre}{body}</section>')

    def _glossary_groups(self) -> list[tuple]:
        """(chapter id or None, chapter name, [terms alphabetical]) — the document's first, then each chapter's."""
        def alpha(ts):
            return sorted(ts, key=lambda t: (t.name.casefold(), t.key))
        groups = [(None, "", alpha([t for t in self.terms if not t.data.get("chapter")]))]
        for c in self.chapters:
            cid = c.get("id")
            citem = self.by_id.get(cid)
            groups.append((cid, citem.name if citem is not None else str(cid),
                           alpha([t for t in self.terms if t.data.get("chapter") == cid])))
        return [g for g in groups if g[2]]

    def _gloss_dl(self, terms: list, *, short_href: str | None) -> str:
        out = ['<dl class="docs-gloss">']
        for t in terms:
            what = t.data.get("atem") or t.data.get("summary") or ""
            dd = _esc(what)
            sec = self.by_key.get(t.data.get("defined_in")) if isinstance(t.data.get("defined_in"), str) else None
            if sec is not None and sec.key in self.dom and short_href is not None:
                dd += (f' — <a class="ref-xref" href="{_esc(short_href)}#{self.dom[sec.key]}">defined in '
                       f'{_esc(self._sec_label(sec))}</a>')
            elif sec is not None:
                dd += f" — defined in {_esc(self._sec_label(sec))}"
            if t.data.get("fallback"):
                dd += ' <span class="docs-fb">told in English</span>'
            out.append(f'<dt id="{self.iid[t.key]}">{_esc(t.name)}</dt><dd>{dd}</dd>')
        out.append("</dl>")
        return "".join(out)

    def _glossary(self, *, prefix: str, contents: list, short_href: str | None) -> str:
        out = []
        for cid, cname, terms in self._glossary_groups():
            if cid is not None:
                gid = f"{prefix}-{re.sub(r'[^a-z0-9]+', '-', self.prefix.get(cid, str(cid)).lower()).strip('-')}"
                label = f"{cname}'s terms"
                out.append(f'<h3 id="{gid}" data-toc="3">{_esc(label)}</h3>')
                contents.append((3, gid, label, False))
            out.append(self._gloss_dl(terms, short_href=short_href))
        return "\n".join(out)

    def short(self) -> tuple[str, dict]:
        contents: list = []
        stats: dict = {"sections": len(self.secs), "terms": len(self.terms), "xref_links": 0, "term_links": 0}
        parts = []
        if self.root is None:
            parts.append(f'<h1 class="docs-title">{_esc(self.vol.name)}</h1>')
        for s in self.secs:
            parts.append(self._section(s, contents, stats))
        if self.terms:
            gid = "docs-glossary" if "docs-glossary" not in self.dom.values() else "docs-glossary-terms"
            contents.append((2, f"{gid}-h", "Terms", False))
            parts.append(f'<section class="docs-sec docs-glossary" id="{gid}"><h2 id="{gid}-h" data-toc="2">'
                         f'Terms</h2>\n' + self._glossary(prefix=gid, contents=contents, short_href="")
                         + "\n</section>")
        return self._wrap("short", contents, "\n".join(parts)), stats

    # ---- atem ----

    def atem(self) -> tuple[str, dict]:
        contents: list = []
        short = self._page("short")
        fabula = self._page("fabula")
        stats = {"sections": len(self.secs), "terms": len(self.terms)}
        h = [f"<h1>{_esc(self._title())}</h1>"]
        if self.root is not None and self.root.data.get("atem"):
            h.append(f'<p class="docs-atem-lead">{_esc(self.root.data["atem"])}</p>')

        def same(a: str, b: str) -> bool:
            return _term_norm(a).rstrip(".:;,") == _term_norm(b).rstrip(".:;,")

        h.append('<h2 id="docs-atem-outline" data-toc="2">Outline</h2>')
        contents.append((2, "docs-atem-outline", "Outline", False))
        h.append('<ol class="docs-outline">')
        for s in self.secs:
            if s is self.root:
                continue
            level = s.data.get("level") if isinstance(s.data.get("level"), int) else 0
            chap = bool(s.data.get("chapter"))
            depth = max(0, (level or 1) - 1) if chap else max(0, (level or 2) - 2)
            depth = min(depth, 5)
            cls = " ".join(c for c in ("docs-ol-top" if depth == 0 else "",
                                       "docs-ol-chapter" if chap and level == 1 else "") if c)
            num = s.data.get("number")
            row = (f'<span class="docs-ol-num">{_esc(num)}</span> ' if num not in (None, "") else "") + \
                f'<span class="docs-ol-name">{_esc(s.name)}</span>'
            atem = s.data.get("atem")
            if atem and not same(str(atem), s.name):
                row += f' <span class="docs-ol-atem">— {_esc(atem)}</span>'
            inner = (f'<a class="docs-ol-row" href="{_esc(short)}#{self.dom[s.key]}">{row}</a>' if short is not None
                     else f'<span class="docs-ol-row">{row}</span>')
            klass = f' class="{cls}"' if cls else ""
            h.append(f'<li{klass} data-depth="{depth}">{inner}</li>')
        h.append("</ol>")
        if self.terms:
            h.append('<h2 id="docs-atem-glossary" data-toc="2">Glossary</h2>')
            contents.append((2, "docs-atem-glossary", "Glossary", False))
            h.append(self._glossary(prefix="docs-atem-glossary", contents=contents, short_href=short))
        R = [it for it in self.items if it.module == "R"]
        stats["reference"] = len(R)
        if R:
            h.append('<h2 id="docs-atem-reference" data-toc="2">Reference</h2>')
            contents.append((2, "docs-atem-reference", "Reference", False))

            def link(it: mc.Item, text: str, cls: str = "docs-r-name") -> str:
                if fabula is None:
                    return f'<span class="{cls}">{_esc(text)}</span>'
                return f'<a class="{cls}" href="{_esc(fabula)}#{self.iid[it.key]}">{_esc(text)}</a>'

            def atem_of(it: mc.Item) -> str:
                a = it.data.get("atem")
                return f' <span class="docs-r-atem">— {_esc(a)}</span>' if a else ""

            def of(key: str, kind: str) -> list:
                return [i for i in R if i.data.get("of") == key and i.kind == kind]

            # the formats as the texts group them (0.6): the core's built-ins first, then the MiniCOSMs; the items keep
            # their kind and ids (`R:minicosm/<name>`), so volumes built before and links from the help still resolve
            formats = [i for i in R if i.kind == "minicosm"]
            grouped = [i for i in formats if i.data.get("core") is True] + \
                [i for i in formats if i.data.get("core") is not True]
            said_group = None
            for mini in grouped:
                group = _format_group(mini)
                if group != said_group:
                    n = sum(1 for i in formats if _format_group(i) == group)
                    h.append(f'<p class="docs-r-group">{_esc(group)} ({n})</p>')
                    said_group = group
                decl = mini.data.get("declaration")
                title = mini.name + (f" · {decl}" if decl else "")
                hid = self.iid[mini.key]
                h.append(f'<h3 id="{hid}" data-toc="3">{_esc(title)}</h3>')
                contents.append((3, hid, title, False))
                if mini.data.get("atem"):
                    h.append(f'<p class="docs-atem-line">{_esc(mini.data["atem"])}</p>')
                rows = []
                for mod in of(mini.key, "module"):
                    kinds = of(mod.key, "kind")
                    letter = mod.data.get("letter") or str(mod.key).split(".")[-1]
                    li = (f'<li><span class="docs-r-kind">{_esc(letter)}</span> {link(mod, mod.name)}{atem_of(mod)}')
                    if kinds:
                        li += ": " + ", ".join(link(k, k.name, "docs-r-sub") for k in kinds)
                    rows.append(li + "</li>")
                for kind in ("list", "lens"):
                    for it in of(mini.key, kind):
                        rows.append(f'<li><span class="docs-r-kind">{kind}</span> {link(it, it.name)}'
                                    f'{atem_of(it)}</li>')
                if rows:
                    h.append('<ul class="docs-ref">' + "".join(rows) + "</ul>")
            checks = [i for i in R if i.kind == "check"]
            if checks:
                h.append('<h3 id="docs-atem-checks" data-toc="3">Checks</h3>')
                contents.append((3, "docs-atem-checks", "Checks", False))
                h.append('<ul class="docs-ref">' + "".join(
                    f'<li>{link(c, c.name)}{atem_of(c)}'
                    + (f' <span class="docs-r-sev">({_esc(c.data["severity"])})</span>' if c.data.get("severity")
                       else "") + "</li>" for c in checks) + "</ul>")
        return self._wrap("atem", contents, "\n".join(h)), stats

    # ---- fabula ----

    def _value(self, v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            it = self.by_key.get(v) or self.by_id.get(v)
            return f'<a href="#{self.iid[it.key]}">{_esc(v)}</a>' if it is not None else _esc(v)
        if isinstance(v, (int, float)):
            return _esc(v)
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                it = (self.by_key.get(x) or self.by_id.get(x)) if isinstance(x, str) else None
                if it is not None:
                    out.append(f'<a href="#{self.iid[it.key]}">{_esc(x)}</a>')
                else:
                    out.append(f"<code>{_esc(x if isinstance(x, str) else self._json(x))}</code>")
            return ", ".join(out)
        if isinstance(v, dict):
            return f"<code>{_esc(self._json(v))}</code>"
        if v is None:
            return "—"
        return _esc(mc.jsonable(v))

    @staticmethod
    def _json(v: Any) -> str:
        return json.dumps(mc.jsonable(v), ensure_ascii=False, separators=(",", ":"))

    def _card(self, it: mc.Item, short: str | None) -> str:
        d = it.data
        out = [f'<article class="docs-card" id="{self.iid[it.key]}" data-kind="{_esc(it.kind or "")}">',
               f'<h4><code class="docs-card-id">{_esc(it.key)}</code> {_esc(it.name)}</h4>']
        if d.get("atem"):
            out.append(f'<p class="docs-card-atem">{_esc(d["atem"])}</p>')
        fields = [(k, v) for k, v in d.items() if k not in _CARD_SKIP]
        if fields:
            out.append('<dl class="docs-card-fields">' + "".join(
                f"<dt>{_esc(k)}</dt><dd>{self._value(v)}</dd>" for k, v in fields) + "</dl>")
        if it.kind == "section" and short is not None:
            out.append(f'<p class="docs-card-read"><a class="ref-xref" href="{_esc(short)}#{self.dom[it.key]}">'
                       f'read it at short</a></p>')
        elif it.kind == "example" and isinstance(d.get("body"), str):
            out.append(f'<pre><code class="language-cosm">{_esc(d["body"])}</code></pre>')
        elif it.kind == "decision" and isinstance(d.get("body"), str):
            out.append('<div class="docs-card-body">' + self.md.render(strip_comments(d["body"])) + "</div>")
        out.append("</article>")
        return "\n".join(out)

    def fabula(self) -> tuple[str, dict]:
        contents: list = []
        short = self._page("short")
        h = [f"<h1>{_esc(self._title())}</h1>",
             '<p class="docs-fab-note">Every item of this volume as a card: its fields as the volume holds them. '
             "The app's fabula density adds facets, live examples and the local graph.</p>"]
        man = self.vol.manifest
        cards = 0
        for letter, kinds in self.vol.by_module().items():
            mod = man.module(letter) if man is not None else {}
            mname = (mod or {}).get("name") or letter
            mid = "docs-fab-" + re.sub(r"[^a-z0-9]+", "-", (letter or "x").lower())
            label = f"{letter} · {mname}"
            h.append(f'<h2 id="{mid}" data-toc="2">{_esc(label)}</h2>')
            contents.append((2, mid, label, False))
            order = list(man.kinds(letter)) if man is not None else []
            for kind in sorted(kinds, key=lambda k: (order.index(k) if k in order else len(order), 0)):
                its = sorted(kinds[kind], key=lambda it: (0, _order(it)) if "order" in it.data else (1, 0))
                groups = [(kind, _plural(kind), its)]
                if letter == "R" and kind == "minicosm":
                    # the formats as the texts group them (0.6): the core's built-ins, then the MiniCOSMs
                    groups = [(g, g, [i for i in its if _format_group(i) == g])
                              for g in (FORMAT_GROUPS[True], FORMAT_GROUPS[False])]
                for key, name, group in groups:
                    if not group:
                        continue
                    kid = f"{mid}-{re.sub(r'[^a-z0-9]+', '-', (key or 'x').lower()).strip('-')}"
                    label = f"{name} ({len(group)})"
                    h.append(f'<h3 id="{kid}" data-toc="3">{_esc(label)}</h3>')
                    contents.append((3, kid, label, False))
                    for it in group:
                        h.append(self._card(it, short))
                        cards += 1
        return self._wrap("fabula", contents, "\n".join(h)), {"cards": cards}

    def render(self, density: str) -> tuple[str, dict]:
        return getattr(self, density)()


# ---------------------------------------------------------------------------
# docs.css and the standalone page
# ---------------------------------------------------------------------------

DOCS_CSS = """/* DocOES export (enough): the fragments' styles. Everything is scoped under .docoes; the tokens
   read the host page's variables when it has them. Single column: the host lays out the contents beside
   the body. */
.docoes {
  --dx-ink: var(--ink, #1a1f2b);
  --dx-ink2: var(--ink2, #4c5566);
  --dx-ink3: var(--ink3, #606878);
  --dx-line: var(--line, #d9dde5);
  --dx-surface: var(--surface, #fff);
  --dx-surface2: var(--surface-2, #f4f5f8);
  --dx-blue: var(--blue, #2457d6);
  --dx-sans: var(--fg-sans, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif);
  --dx-mono: var(--fg-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace);
  --dx-r2: var(--r2, 8px);
  color: var(--dx-ink);
  font-family: var(--dx-sans);
  font-size: 1rem;
  line-height: 1.6;
  overflow-wrap: break-word;
}
.docoes *, .docoes *::before, .docoes *::after { box-sizing: border-box; }
.docoes .docoes-body { min-width: 0; }

/* the contents */
.docoes .docoes-contents {
  border: 1px solid var(--dx-line);
  border-radius: var(--dx-r2);
  background: var(--dx-surface);
  padding: 0.75rem 0.9rem;
  margin: 0 0 1.5rem;
  font-size: 0.85rem;
  line-height: 1.4;
}
.docoes .docoes-contents ol { list-style: none; margin: 0; padding: 0; }
.docoes .docoes-contents ol ol { margin: 0.15rem 0 0.35rem 0.9rem; }
.docoes .docoes-contents li { margin: 0.15rem 0; }
.docoes .docoes-contents li.lvl2 { font-weight: 600; }
.docoes .docoes-contents li.lvl3 { font-weight: 400; }
.docoes .docoes-contents li.lvl2.chapter {
  margin-top: 0.6rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--dx-line);
}
.docoes .docoes-contents a { color: var(--dx-ink2); text-decoration: none; }
.docoes .docoes-contents a:hover { color: var(--dx-blue); text-decoration: underline; }

/* headings and prose */
.docoes h1, .docoes h2, .docoes h3, .docoes h4, .docoes h5, .docoes h6 {
  font-weight: 700;
  line-height: 1.25;
  margin: 1.6em 0 0.6em;
  color: var(--dx-ink);
  scroll-margin-top: 1rem;
}
.docoes h1 { font-size: 2rem; margin-top: 0; padding-bottom: 0.3em; border-bottom: 1px solid var(--dx-line); }
.docoes h2 { font-size: 1.5rem; padding-bottom: 0.2em; border-bottom: 1px solid var(--dx-line); }
.docoes h3 { font-size: 1.22rem; }
.docoes h4 { font-size: 1.06rem; }
.docoes h5, .docoes h6 { font-size: 1rem; font-style: italic; }
.docoes p { margin: 0.85em 0; line-height: 1.6; }
.docoes ul, .docoes ol { margin: 0.7em 0 0.7em 1.4em; padding-left: 0.4em; }
.docoes li { margin: 0.25em 0; }
.docoes li > p { margin: 0.35em 0; }
.docoes strong { font-weight: 700; }
.docoes em { font-style: italic; }
.docoes del, .docoes s { color: var(--dx-ink3); }
.docoes a { color: var(--dx-blue); }
.docoes blockquote {
  margin: 1em 0;
  padding: 0.2em 0.9em;
  border-left: 3px solid var(--dx-line);
  color: var(--dx-ink2);
}
.docoes hr { border: none; border-top: 1px solid var(--dx-line); margin: 2em 0; }
.docoes img { max-width: 100%; }

/* code */
.docoes code {
  font-family: var(--dx-mono);
  font-size: 0.88em;
  background: var(--dx-surface2);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.docoes pre {
  font-family: var(--dx-mono);
  font-size: 0.84rem;
  line-height: 1.5;
  background: var(--dx-surface2);
  border: 1px solid var(--dx-line);
  border-radius: var(--dx-r2);
  padding: 0.85em 1em;
  margin: 1em 0;
  overflow-x: auto;
  white-space: pre;
}
.docoes pre code { background: transparent; padding: 0; border-radius: 0; font-size: inherit; }

/* tables */
.docoes .docs-table { width: 100%; overflow-x: auto; margin: 1.2em 0; }
.docoes table { width: 100%; border-collapse: collapse; font-size: 0.88rem; line-height: 1.45; }
.docoes th, .docoes td {
  border: 1px solid var(--dx-line);
  padding: 0.4em 0.7em;
  text-align: left;
  vertical-align: top;
}
.docoes thead th { background: var(--dx-surface2); font-weight: 700; }

/* the section furniture */
.docoes .docs-sec { margin: 0; }
.docoes .docs-chapter-note, .docoes .docs-note, .docoes .docs-fb {
  color: var(--dx-ink3);
  font-size: 0.88rem;
  font-style: italic;
}
.docoes .docs-chapter-note { margin: 2.5em 0 -1em; padding-top: 1em; border-top: 2px solid var(--dx-line); }
.docoes .docs-marks { float: right; margin: -0.3em 0 0.4em 1em; font-size: 0.78rem; color: var(--dx-ink3); }
.docoes .docs-mark { display: inline-block; margin-left: 0.5em; white-space: nowrap; }
.docoes a.ref-xref { color: var(--dx-blue); text-decoration: none; }
.docoes a.ref-xref:hover { text-decoration: underline; }
.docoes a.ref-xref-num { display: inline-block; min-width: 1.2em; text-align: center; }
.docoes a.docs-term {
  color: inherit;
  text-decoration: underline dotted var(--dx-ink3);
  text-underline-offset: 0.18em;
}
.docoes a.docs-term:hover { color: var(--dx-blue); text-decoration-color: var(--dx-blue); }

/* the glossary */
.docoes .docs-gloss { margin: 0.6em 0 1.2em; }
.docoes .docs-gloss dt { font-weight: 700; margin-top: 0.7em; scroll-margin-top: 1rem; }
.docoes .docs-gloss dd { margin: 0.15em 0 0 1.4em; color: var(--dx-ink2); }
.docoes .docs-gloss dt:target, .docoes .docs-gloss dt:target + dd { background: var(--dx-surface2); }

/* the atem density */
.docoes .docs-atem-lead { font-size: 1.1rem; color: var(--dx-ink2); }
.docoes .docs-outline { list-style: none; margin: 0.5em 0 1.5em; padding: 0; }
.docoes .docs-outline li { margin: 0; }
.docoes .docs-outline .docs-ol-row {
  display: block;
  padding: 0.2em 0.4em;
  border-radius: 4px;
  color: var(--dx-ink);
  text-decoration: none;
}
.docoes .docs-outline a.docs-ol-row:hover { background: var(--dx-surface2); }
.docoes .docs-outline li.docs-ol-top { margin-top: 0.35em; }
.docoes .docs-outline li.docs-ol-top > .docs-ol-row .docs-ol-name { font-weight: 600; }
.docoes .docs-outline li.docs-ol-chapter { margin-top: 1em; padding-top: 0.5em; border-top: 1px solid var(--dx-line); }
.docoes .docs-outline [data-depth="1"] { padding-left: 1.2em; }
.docoes .docs-outline [data-depth="2"] { padding-left: 2.4em; }
.docoes .docs-outline [data-depth="3"] { padding-left: 3.6em; }
.docoes .docs-outline [data-depth="4"] { padding-left: 4.8em; }
.docoes .docs-outline [data-depth="5"] { padding-left: 6em; }
.docoes .docs-ol-num { color: var(--dx-ink3); font-variant-numeric: tabular-nums; margin-right: 0.3em; }
.docoes .docs-ol-atem, .docoes .docs-r-atem, .docoes .docs-r-sev { color: var(--dx-ink3); }
.docoes .docs-r-group { color: var(--dx-ink3); font-variant: small-caps; letter-spacing: .03em; margin: 1.4em 0 .2em; }
.docoes .docs-atem-line { color: var(--dx-ink2); margin-top: -0.3em; }
.docoes .docs-ref { list-style: none; margin: 0.4em 0 1.2em; padding: 0; }
.docoes .docs-ref li { margin: 0.3em 0; padding-left: 1.2em; text-indent: -1.2em; }
.docoes .docs-r-kind {
  display: inline-block;
  min-width: 1.6em;
  font-family: var(--dx-mono);
  font-size: 0.82em;
  color: var(--dx-ink3);
  text-indent: 0;
}
.docoes .docs-r-name { font-weight: 600; }
.docoes a.docs-r-name, .docoes a.docs-r-sub { color: var(--dx-ink); text-decoration: none; }
.docoes a.docs-r-name:hover, .docoes a.docs-r-sub:hover { color: var(--dx-blue); text-decoration: underline; }
.docoes .docs-r-sub { font-family: var(--dx-mono); font-size: 0.85em; }

/* the fabula density */
.docoes .docs-fab-note { color: var(--dx-ink2); }
.docoes .docs-card {
  border: 1px solid var(--dx-line);
  border-radius: var(--dx-r2);
  background: var(--dx-surface);
  padding: 0.75em 1em;
  margin: 0.8em 0;
  scroll-margin-top: 1rem;
}
.docoes .docs-card:target { border-color: var(--dx-blue); box-shadow: 0 0 0 2px var(--dx-surface2); }
.docoes .docs-card h4 { margin: 0 0 0.3em; font-size: 1rem; }
.docoes .docs-card-id { font-weight: 400; color: var(--dx-ink2); margin-right: 0.3em; }
.docoes .docs-card-atem { margin: 0.2em 0 0.6em; color: var(--dx-ink2); }
.docoes .docs-card-fields {
  display: grid;
  grid-template-columns: minmax(6em, max-content) minmax(0, 1fr);
  gap: 0.2em 0.9em;
  margin: 0.4em 0;
  font-size: 0.86rem;
}
.docoes .docs-card-fields dt { color: var(--dx-ink3); font-family: var(--dx-mono); font-size: 0.92em; }
.docoes .docs-card-fields dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.docoes .docs-card-fields code { font-size: 0.92em; }
.docoes .docs-card-fields a { text-decoration: none; }
.docoes .docs-card-read { margin: 0.4em 0 0; font-size: 0.88rem; }
.docoes .docs-card-body { font-size: 0.92rem; }
.docoes .docs-card pre { margin: 0.6em 0 0.2em; }

@media (max-width: 600px) {
  .docoes h1 { font-size: 1.6rem; }
  .docoes h2 { font-size: 1.3rem; }
  .docoes .docs-marks { float: none; margin: 0 0 0.4em; }
  .docoes .docs-card-fields { grid-template-columns: minmax(0, 1fr); }
  .docoes .docs-card-fields dd { margin-bottom: 0.3em; }
}

/* --standalone pages only (the site never serves them) */
body.docoes-page {
  margin: 0;
  background: var(--surface-2, #f4f5f8);
  color: var(--ink, #1a1f2b);
  font-family: var(--fg-sans, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif);
}
body.docoes-page > .docoes-head, body.docoes-page > .docoes, body.docoes-page > .docoes-foot {
  max-width: 980px;
  margin: 0 auto;
  padding: 1rem 16px;
}
body.docoes-page > .docoes { background: var(--surface, #fff); border-radius: var(--r2, 8px); padding: 1.5rem 16px; }
.docoes-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.6rem; }
.docoes-head .docoes-doc { margin: 0; font-weight: 600; }
.docoes-densities { display: flex; gap: 0.25rem; }
.docoes-densities a {
  padding: 0.25rem 0.7rem;
  border: 1px solid var(--line, #d9dde5);
  border-radius: 999px;
  color: var(--ink2, #4c5566);
  text-decoration: none;
  font-size: 0.9rem;
}
.docoes-densities a[aria-current="page"] {
  background: var(--ink, #1a1f2b);
  border-color: var(--ink, #1a1f2b);
  color: #fff;
}
.docoes-foot { color: var(--ink3, #606878); font-size: 0.85rem; }
"""


def standalone(fragment: str, *, name: str, version: str, density: str, lang: str, pages: dict,
               densities: tuple) -> str:
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{_esc(pages[d])}"{current if d == density else ""}>{d}</a>'
                  for d in ("atem", "short", "fabula") if d in densities)
    head = name + (f" · {version}" if version else "")
    return ("<!doctype html>\n"
            f'<html lang="{_esc(lang)}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="robots" content="noindex">\n'
            f"<title>{_esc(name)} · {density}</title>\n"
            f'<link rel="stylesheet" href="../{CSS_NAME}">\n</head>\n'
            '<body class="docoes-page">\n'
            f'<header class="docoes-head"><p class="docoes-doc">{_esc(head)}</p>'
            f'<nav class="docoes-densities" aria-label="Density">{nav}</nav></header>\n'
            + fragment
            + f'<footer class="docoes-foot">exported by enough/{_esc(D.ENOUGH_VERSION)}</footer>\n'
            "</body>\n</html>\n")


# ---------------------------------------------------------------------------
# Which document, the build, the manifest
# ---------------------------------------------------------------------------

def default_slug(path: str | Path) -> str:
    """`THYM.md` → `thym`, `MACROCOSM_OES.md` → `macrocosm-oes`: the stem lower-cased, `_` a hyphen, anything
    else outside a-z, 0-9 and `-` dropped."""
    stem = Path(path).stem.lower().replace("_", "-")
    return re.sub(r"[^a-z0-9-]", "", stem)


def _h1(text: str) -> str:
    lines, _ = D._scan(text)
    for ln in lines:
        if ln.code or ln.comment:
            continue
        m = D._HEADING.match(ln.text)
        if m and len(m.group(1)) == 1:
            return D._plain(re.sub(r"[ \t]+#+$", "", m.group(2) or ""))
    return ""


def resolve_document(arg: str, *, sources: Path, lang: str | None = None, slug: str | None = None,
                     name: str | None = None, version: str | None = None) -> tuple[D.Document, str]:
    """(the Document, the telling) for a registered slug or a markdown path inside `sources`. A path is exported
    as the registered document its default slug names unless `slug` is given: an explicit slug, a registered one
    included, makes an ad hoc document of the path's text alone (no chapters; the reference only when asked)."""
    reg_slug = arg.removeprefix("doc/")
    if reg_slug in D.DOCUMENTS and not arg.endswith(".md"):
        d = D.DOCUMENTS[reg_slug]
        lang = lang or "en"
    else:
        p = Path(arg)
        full = (p if p.is_absolute() else sources / p).resolve()
        if not full.is_relative_to(Path(sources).resolve()):
            raise ExportError(f"{arg}: not inside the sources root {sources}")
        if not full.is_file():
            raise ExportError(f"no document {arg!r}: neither a registered one ({', '.join(D.DOCUMENTS)}) "
                              f"nor a file under {sources}")
        rel = full.relative_to(Path(sources).resolve()).as_posix()
        own = default_slug(full)
        if slug is None and own in D.DOCUMENTS:
            d = D.DOCUMENTS[own]
            mine = [lg for lg, src in d.sources.items() if src == rel]
            lang = lang or (mine[0] if mine else "en")
        else:
            s = slug or own
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", s or ""):
                raise ExportError(f"{s!r} is not a slug (a-z, 0-9 and -)")
            # A registered slug given explicitly is allowed: the Exporter keys its cross-reference rules
            # (XREF_RULES) by slug, so the spec's own conventions still hold for a text exported from elsewhere.
            lang = lang or "en"
            if version is None:
                m = D._registry(sources).by_name(s)          # a format's name, or an old spelling's (emf)
                version = str(m.version) if m is not None and m.version is not None else ""
            text = full.read_bytes().decode("utf-8")
            d = D.Document(s, name or _h1(text) or s, {lang: rel}, version=version)
            return d, lang
    if lang not in d.sources:
        raise ExportError(f"{d.slug} has no {lang} telling; it has {', '.join(D.tellings(d))}")
    if name is not None or version is not None:
        d = dataclasses.replace(d, **({"name": name} if name is not None else {}),
                                **({"version": version} if version is not None else {}))
    return d, lang


def _git(root: Path) -> dict:
    """`{commit, dirty}` of the sources root, best effort; nulls when it is not a checkout. Read-only: no
    optional locks, so not even the index's stat cache is refreshed."""
    try:
        head = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        if head.returncode != 0:
            return {"commit": None, "dirty": None}
        st = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
        return {"commit": head.stdout.strip() or None, "dirty": bool(st.stdout.strip()) if st.returncode == 0
                else None}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(out: Path) -> dict | None:
    path = out / MANIFEST_NAME
    if not path.exists():
        return None
    try:
        man = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ExportError(f"{path}: not a manifest this export can merge into ({e}); choose another out-dir") \
            from None
    if not isinstance(man, dict) or man.get("format") != FORMAT:
        raise ExportError(f"{path}: format {man.get('format') if isinstance(man, dict) else None!r}, not "
                          f"{FORMAT}; refusing to overwrite it")
    return man


def _write(path: Path, text: str) -> bytes:
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)                            # mkstemp's 0600 is not what a site's files want
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return data


def link_check(fragment: str) -> dict:
    """Ids, in-page links and the ones that do not resolve, for a self-check (and the tests)."""
    ids = re.findall(r'\sid="([^"]+)"', fragment)
    hrefs = re.findall(r'\shref="#([^"]*)"', fragment)
    known = set(ids)
    return {"ids": len(ids), "duplicate_ids": len(ids) - len(known), "anchors": len(hrefs),
            "dangling": sorted({h for h in hrefs if h not in known})}


def export(doc: str | D.Document, out_dir: Path, *, lang: str | None = None, densities: tuple = DENSITIES,
           pages: dict | None = None, standalone_pages: bool = False, slug: str | None = None,
           name: str | None = None, version: str | None = None, sources: Path | None = None,
           docs_root: Path | None = None, marks: bool = True, reference: bool = False) -> dict:
    """Export one document into `out_dir` and merge its entry into the manifest. Returns the entry plus `stats`
    (per density: the counts and the link self-check) and `seconds`. `marks=False` leaves the margin marks out of
    the short density; `reference=True` joins the manifests' reference (R: items) whatever the document says."""
    t0 = time.monotonic()
    root = Path(sources or D.sources_root())
    densities = tuple(densities)
    bad = [x for x in densities if x not in DENSITIES]
    if bad or not densities:
        raise ExportError(f"unknown densit{'ies' if len(bad) > 1 else 'y'} {', '.join(bad) or '(none)'}; "
                          f"choose from {', '.join(DENSITIES)}")
    if lang is not None and lang not in D.LANGS:
        raise ExportError(f"no telling {lang!r}; DocOES knows {', '.join(D.LANGS)}")
    if isinstance(doc, D.Document):
        d, lg = doc, lang or "en"
        if lg not in d.sources:
            raise ExportError(f"{d.slug} has no {lg} telling")
    else:
        d, lg = resolve_document(doc, sources=root, lang=lang, slug=slug, name=name, version=version)
    if reference and not d.reference:
        d = dataclasses.replace(d, reference=True)
    out = Path(out_dir)
    previous = _read_manifest(out)                      # refuse a foreign out-dir before anything is written
    pages = {**DEFAULT_PAGES, **(pages or {})}
    with tempfile.TemporaryDirectory(prefix="docoes-export-") as tmp:
        built_in = Path(docs_root) if docs_root is not None else Path(tmp)
        try:
            path = D.build(d, lg, docs_root=built_in, sources=root)
        except (OSError, KeyError, UnicodeDecodeError) as e:
            raise ExportError(f"{d.slug}.{lg}: cannot build: {type(e).__name__}: {e}", 1) from None
        vol = mc.load_volume(path, D._registry(root))
        if vol.refused is not None:
            raise ExportError(f"{d.slug}.{lg}: the volume is refused: {vol.refused}", 1)
        ex = Exporter(vol, d, lg, pages=pages, densities=densities, marks=marks)
        files, stats = {}, {}
        for dens in densities:
            frag, st = ex.render(dens)
            st.update(link_check(frag))
            text = standalone(frag, name=ex._name(), version=str(d.version or ""), density=dens, lang=lg,
                              pages=pages, densities=densities) if standalone_pages else frag
            rel = f"{d.slug}/{dens}.html"
            data = _write(out / rel, text)
            files[dens] = {"path": rel, "sha256": _sha(data), "bytes": len(data)}
            st["bytes"] = len(data)
            stats[dens] = st
    _write(out / CSS_NAME, DOCS_CSS)
    cat = vol.catalog
    document = cat.get("document") if isinstance(cat.get("document"), dict) else {}
    kinds = [it.kind for it in vol.items.values()]
    entry = {
        "slug": d.slug, "name": ex._name(), "version": str(document.get("version") or d.version or ""),
        "lang": lg, "id": vol.id, "oes": vol.oes,
        "lead": (ex.root.data.get("atem") if ex.root is not None else None) or "",
        "source": {"path": document.get("path"), "sha256": document.get("sha256")},
        "chapters": [{"id": c.get("id"), "name": ex.by_id[c["id"]].name if c.get("id") in ex.by_id else c.get("id"),
                      "source": c.get("source"), "commit": c.get("commit"), "sha256": c.get("sha256"),
                      "prefix": c.get("prefix"), "version": str(c.get("version") or "")} for c in ex.chapters],
        "counts": {"sections": kinds.count("section"), "terms": kinds.count("term"),
                   "examples": kinds.count("example"), "decisions": kinds.count("decision"),
                   "reference": sum(1 for it in vol.items.values() if it.module == "R")},
        "files": files,
    }
    docs = [x for x in (previous or {}).get("documents") or [] if isinstance(x, dict)]
    at = next((i for i, x in enumerate(docs) if x.get("slug") == d.slug), None)
    if at is None:
        docs.append(entry)
    else:
        docs[at] = entry
    manifest = {
        "format": FORMAT,
        "exported": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by": f"enough/{D.ENOUGH_VERSION}",
        "source": _git(root),
        "css": CSS_NAME,
        "pages": {k: pages[k] for k in DENSITIES},
        "standalone": bool(standalone_pages),
        "documents": docs,
    }
    _write(out / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {**entry, "stats": stats, "seconds": round(time.monotonic() - t0, 3)}


# ---------------------------------------------------------------------------
# CLI (`python -m enough.docoes export …`)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m enough.docoes export",
        description="Export a DocOES document as static HTML fragments at the three densities (short, atem, "
                    "fabula), with docs.css and a merged manifest.json.")
    ap.add_argument("doc", help=f"a registered document ({', '.join(D.DOCUMENTS)}) or a markdown path inside the "
                                "sources root (docs/THYM.md)")
    ap.add_argument("out_dir", type=Path, help="where the fragments, docs.css and manifest.json go")
    ap.add_argument("--lang", default=None, help="the telling (default: en, or the telling the path is)")
    ap.add_argument("--densities", default=",".join(DENSITIES), help="a comma-separated subset of short,atem,fabula")
    ap.add_argument("--page", action="append", default=[], metavar="DENSITY=HREF",
                    help="the href links across densities use (default short.html, atem.html, fabula.html)")
    ap.add_argument("--standalone", action="store_true", help="wrap each fragment in a full page, for eyeballing")
    ap.add_argument("--slug", help="an ad hoc document's slug (default: the file stem)")
    ap.add_argument("--name", help="the document's name (default: its H1)")
    ap.add_argument("--version", help="the document's version (default: its manifest's, else none)")
    ap.add_argument("--no-marks", action="store_true",
                    help="leave out the margin marks (mentioned in N places, N examples) of the short density")
    ap.add_argument("--reference", action="store_true",
                    help="join the reference generated from the MiniCOSM manifests (an ad hoc document has none)")
    ap.add_argument("--sources", type=Path, help="the install the documents are read from (default: this one)")
    ap.add_argument("--docs-root", type=Path,
                    help="build the volume here (default: a temporary directory, removed afterwards)")
    args = ap.parse_args(argv)
    pages: dict = {}
    for p in args.page:
        k, sep, v = p.partition("=")
        if not sep or k not in DENSITIES or not v:
            print(f"--page {p!r}: expected DENSITY=HREF with DENSITY one of {', '.join(DENSITIES)}", file=sys.stderr)
            return 2
        pages[k] = v
    densities = tuple(x.strip() for x in args.densities.split(",") if x.strip())
    try:
        r = export(args.doc, args.out_dir, lang=args.lang, densities=densities, pages=pages,
                   standalone_pages=args.standalone, slug=args.slug, name=args.name, version=args.version,
                   sources=args.sources, docs_root=args.docs_root, marks=not args.no_marks,
                   reference=args.reference)
    except ExportError as e:
        print(str(e), file=sys.stderr)
        return e.code
    c = r["counts"]
    print(f"{r['slug']} ({r['lang']}, v{r['version'] or '-'}): {c['sections']} sections, {c['terms']} terms, "
          f"{c['examples']} examples, {c['decisions']} decisions, {c['reference']} reference — {r['seconds']} s")
    dangling = 0
    for dens, st in r["stats"].items():
        extra = ""
        if dens == "short":
            extra = f", {st.get('xref_links', 0)} xref links, {st.get('term_links', 0)} term links"
        elif dens == "fabula":
            extra = f", {st.get('cards', 0)} cards"
        print(f"  {dens:6} {r['files'][dens]['path']}  {st['bytes']} bytes, {st['ids']} ids, {st['anchors']} in-page "
              f"links{extra}, {len(st['dangling'])} dangling")
        dangling += len(st["dangling"]) + st["duplicate_ids"]
    if dangling:
        print(f"warning: {dangling} dangling in-page links or duplicate ids", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
