"""DocOES: one document enumerated into a doc volume (MacroCOSM OES section 18.5, `oes: doc/1`).

A doc volume is a document's fabula. The markdown the owner writes stays the authoring surface; this module
decompiles it into items — its sections, the terms it defines, its complete ```cosm examples, its decisions — and
joins them to the reference generated from the MiniCOSM manifests (every MiniCOSM, module, kind, closed list, check
and lens) and, for the Help Center, to the help bubbles beside the controls. Compiled "as told" (`compile_doc`), the
section bodies give the markdown back byte for byte: that round trip is the manual density, and a test holds it.

Charter:

- **Deterministic and idempotent.** The same sources give the same volume; nothing here asks a model. Every item
  has an `atem`, its one line: a `<!-- atem: … -->` marker under a heading, or the first sentence, cut by rule.
- **Built at runtime, never committed.** `build` writes `<docs_root>/<doc>.<lang>.doc.cosm` (env
  `ENOUGH_DOCS_ROOT`, default `~/enough/docoes/`) atomically; `ensure_built` rebuilds only when the digest over the
  sources, every manifest and enough's version differs from the one the volume records under `built:`; `load_built`
  is ensure + load, the loaded volume cached by the file's mtime and size (the server and `doc_lookup` share it).
- **Bodies are verbatim.** A section's `body` is the text between its heading and the next, never re-flowed.
- **The reader wins.** The volume is read and generically checked by `enough/macrocosm.py`; DocOES's own checks
  (`lint_doc`) live here, beside it.

Standalone like the reader: the standard library, PyYAML and `enough.macrocosm`, nothing else from enough.

    python -m enough.docoes build     <doc> [--lang L] [--force]
    python -m enough.docoes lint      <doc> [--lang L] [--json]
    python -m enough.docoes compile   <doc> [--lang L] [--chapter SLUG]
    python -m enough.docoes inventory <doc> [--lang L] [--json]

Documents: `macrocosm-oes` (English, with Comprise's spec and paradigm map as chapters) and `help-center` (six
tellings: en de es fr ja zh, written by Rosa).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from . import macrocosm as mc

try:                                                    # the package's version; vendored, the caller's
    from . import __version__ as ENOUGH_VERSION
except ImportError:                                     # pragma: no cover
    ENOUGH_VERSION = "0"

INSTALL_ROOT = Path(__file__).resolve().parents[1]
# Where the documents are read from when a caller names no `sources`: an install root laid out like the repo. None
# means INSTALL_ROOT. Tests point it at a miniature install so they do not enumerate the real 2,000-line spec.
SOURCES: Path | None = None
# Bump when the enumeration rules change, so every built volume rebuilds even within one enough version.
FORMAT = 1
OES = "doc/1"
LANGS = ("en", "de", "es", "fr", "ja", "zh")
CJK = ("ja", "zh")
ATEM_WORDS = (2, 15)
ATEM_CJK_CHARS = (2, 45)
CHAPTERS_DIR = "defaults/cosm/chapters"
MANIFESTS_DIR = "defaults/cosm/manifests"

# DocOES's own checks, run by `lint_doc` after the generic ones (a generic reader lists them as not run).
DOC_CHECKS = ("atem-shape", "numbering", "term-defined-once", "unlinked-mentions", "empty-section",
              "stale-provenance-hash", "xref-unresolved")
DOC_SEVERITY = {"atem-shape": "error", "numbering": "error", "term-defined-once": "warning",
                "unlinked-mentions": "note", "empty-section": "note", "stale-provenance-hash": "warning",
                "xref-unresolved": "error"}


# ---------------------------------------------------------------------------
# The documents enough enumerates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Chapter:
    """A synced, read-only document inside a doc volume: Comprise's own words, under its own id prefix."""
    file: str                    # its copy under defaults/cosm/chapters/
    slug: str                    # S:chapter/<slug>
    prefix: str                  # S:section/<prefix>.4.1; also its inventory's name (comprise@1:section:4.1)
    source: str                  # where the sync copied it from, in the Comprise checkout
    label: str                   # whose words: "Comprise"
    version: str                 # the chapter's own version, for its inventory
    xref: tuple = ()             # (marker, inventory) pairs: what its § and P.N name; an empty inventory: not linked


@dataclass(frozen=True)
class Document:
    slug: str
    name: str
    sources: dict                # lang -> the markdown, relative to the install
    bubbles: dict = field(default_factory=dict)     # lang -> help-docs, relative to the install
    voice: str | None = None
    chapters: tuple = ()
    reference: bool = False      # join the R: items generated from the manifests
    version: str = ""
    xref: dict = field(default_factory=dict)        # how this document's own words point at a chapter
    plain_mentions: str = "all"  # all: every plain use of a term is a mention; distinctive: only distinctive names


# Comprise's spec uses § only for other documents (HELP_CENTER §8, plan/comprise-model.md §5): never linked. Its
# paradigm map's § and P.N name sections of the spec: cross-volume references into the comprise chapter.
_COMPRISE = Chapter("comprise-oes.md", "comprise-oes", "comprise", "oes/comprise-oes.md", "Comprise", "1",
                    (("§", ""),))
_PARADIGM_MAP = Chapter("comprise-paradigm-map.md", "comprise-paradigm-map", "comprise-map", "oes/README.md",
                        "Comprise", "1", (("§", "comprise"), ("P.", "comprise")))

DOCUMENTS: dict[str, Document] = {
    "macrocosm-oes": Document(
        "macrocosm-oes", "MacroCOSM OES", {"en": "docs/MACROCOSM_OES.md"},
        chapters=(_COMPRISE, _PARADIGM_MAP), reference=True, version=mc.MACROCOSM_VERSION,
        # In the spec, § always names a section of Comprise OES 1, "README §" one of its paradigm map, and P.N a
        # section of its chapter P: all three become cross-volume references into the chapters (xrefs).
        xref={"§": "comprise", "README §": "comprise-map", "P.": "comprise"}),
    "help-center": Document(
        "help-center", "the enough help center",
        {"en": "docs/HELP_CENTER.md", **{lang: f"enough/static/i18n/{lang}/help-center.md" for lang in LANGS[1:]}},
        bubbles={"en": "enough/static/help-docs.md",
                 **{lang: f"enough/static/i18n/{lang}/help-docs.md" for lang in LANGS[1:]}},
        voice="rosa", version=ENOUGH_VERSION, plain_mentions="distinctive"),
}

# A bubble that describes another document: its "section N" names that document's sections (cross-volume).
# The docs viewer's bubble (0.4.4, which took over 0.4.3's `cosmspec` bubble) points into the specification; a
# bubble about the Help Center itself names no section number, so nothing of the manual is misread as the spec's.
BUBBLE_DOCUMENT = {"docs": "macrocosm-oes"}


def docs_root() -> Path:
    """Where built doc volumes live: `ENOUGH_DOCS_ROOT`, else `~/enough/docoes/` (a state folder of its own: an
    install's `~/enough/docs/` is its code tree's documentation, not a place to build into)."""
    env = os.environ.get("ENOUGH_DOCS_ROOT")
    return Path(env).expanduser() if env else Path.home() / "enough" / "docoes"


def sources_root() -> Path:
    """The install the documents are read from: `SOURCES` when set, else this package's own install."""
    return Path(SOURCES) if SOURCES is not None else INSTALL_ROOT


def volume_path(doc: str, lang: str = "en", root: Path | None = None) -> Path:
    return Path(root or docs_root()) / f"{doc}.{lang}.doc.cosm"


def tellings(doc: str) -> list[str]:
    return [lang for lang in LANGS if lang in _document(doc).sources]


def _document(doc: str) -> Document:
    d = DOCUMENTS.get(doc.removeprefix("doc/"))
    if d is None:
        raise KeyError(f"no document {doc!r}; enough enumerates {', '.join(DOCUMENTS)}")
    return d


# ---------------------------------------------------------------------------
# Text: plain words, sentences, atems
# ---------------------------------------------------------------------------

_HTML_TAG = re.compile(r"</?(?:strong|em|code|b|i|br|kbd|span|a|sup|sub|small|u|s|mark|abbr|p|div)\b[^>\n]*>",
                       re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_ABBR = {"e.g", "i.e", "etc", "vs", "cf", "fig", "approx", "dr", "mr", "mrs", "st", "no"}
_ID_RE = re.compile(r"\b[A-Z]:[a-z][a-z0-9-]*/[A-Za-z0-9]|\boes:[a-z]")
_MARKUP_RE = re.compile(r"\*\*|`|\]\(|<!--|^#|\|")


def _plain(md: str) -> str:
    """Markdown and inline HTML to plain words: links to their text, code spans to their content, emphasis and
    tags dropped, entities decoded, whitespace collapsed."""
    s = _COMMENT.sub("", md)
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"(`+)(.+?)\1", r"\2", s)
    s = _HTML_TAG.sub("", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)", r"\1", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>])", r"\1", s)
    if "&" in s:
        s = html.unescape(s)
    return " ".join(s.split())


def _sentences(text: str, lang: str = "en") -> list[str]:
    """Plain text split into sentences: at . ! ? before a space (not after an abbreviation), or at 。！？."""
    out, start = [], 0
    rx = r"[。！？]" if lang in CJK else r"[.!?](?=\s|$)"
    for m in re.finditer(rx, text):
        if lang not in CJK:
            words = text[start:m.start()].split()
            if words and words[-1].lower().rstrip(".") in _ABBR:
                continue
        piece = text[start:m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    if lang in CJK and len(out) <= 1 and re.search(r"[.!?]\s", text):      # English inside a CJK telling
        return _sentences(text, "en")
    return out


def _count(text: str, lang: str) -> int:
    if lang in CJK:
        return len(re.sub(r"\s", "", text))
    return len(text.split())


def _atem_cut(text: str, lang: str = "en") -> str:
    """One sentence made an atem: at most 15 words (45 characters in Japanese and Chinese), cut at the last
    clause break that keeps at least three words, else at the limit with an ellipsis; no final period."""
    s = " ".join(text.split()).strip()
    s = re.sub(r"[.。:：;；,，]+$", "", s).strip()
    if lang in CJK:
        hi = ATEM_CJK_CHARS[1]
        if len(re.sub(r"\s", "", s)) <= hi:
            return s
        head = s[:hi]
        cut = max(head.rfind(c) for c in "、，：；（(—")
        s = head[:cut].rstrip() if cut >= 6 else head.rstrip() + "…"
        return re.sub(r"[。:：;；,，、]+$", "", s)
    words = s.split()
    hi = ATEM_WORDS[1]
    if len(words) <= hi:
        return s
    # Clause breaks inside the limit, outside parentheses and braces: a semicolon, a dash or an opening
    # parenthesis (strong); the first colon (medium); the last comma (weak). The strongest that keeps six words wins.
    strong, medium, weak = 0, 0, 0
    depth = 0
    for i, w in enumerate(words[:hi + 1]):
        if i >= 6 and depth == 0 and (w in ("—", "–") or w[0] in "({"):
            strong = i
        depth += w.count("(") + w.count("{") - w.count(")") - w.count("}")
        depth = max(depth, 0)
        if 3 <= i + 1 <= hi and depth == 0:
            if w.endswith(";"):
                strong = i + 1
            elif w.endswith(":") and not medium:
                medium = i + 1
            elif w.endswith(",") and i + 1 >= 8:
                weak = i + 1
    best = strong or medium or weak
    if best:
        return re.sub(r"[,;:—–({]+$", "", " ".join(words[:best])).strip()
    keep = words[:hi]
    while len(keep) > 3 and keep[-1].lower().strip(",;:") in _TRAILING:
        keep.pop()
    return re.sub(r"[,;:—–({]+$", "", " ".join(keep)).strip() + "…"


_TRAILING = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with",
             "would", "is", "are"}


def _shorten(text: str, room: int, lang: str) -> str:
    """At most `room` words: cut at the last clause break that fits, else at the limit, never on a word that
    leaves a phrase hanging (and, of, the …)."""
    if lang in CJK or _count(text, lang) <= room:
        return text
    words = text.split()
    cut = max((i + 1 for i, w in enumerate(words[:room]) if re.search(r"[,;:]$", w) and i + 1 >= 2), default=0)
    out = words[:cut] if cut else words[:max(room, 2)]
    while len(out) > 2 and out[-1].lower().strip(",;:") in _TRAILING:
        out.pop()
    return " ".join(out).rstrip(",;:")


def _atem_of(text: str, lang: str = "en") -> str | None:
    """The atem a passage of plain text gives: its first sentence of at least two words, cut."""
    for sent in _sentences(text, lang)[:3]:
        a = _atem_cut(sent, lang)
        if not atem_problems(a, lang):
            return a
    return None


def atem_problems(atem: Any, lang: str = "en") -> list[str]:
    """Why an atem fails the atem lint (empty when it passes): one line, one phrase, 2 to 15 words (2 to 45
    characters in Japanese and Chinese), no final period, no ids, no markup."""
    if not isinstance(atem, str) or not atem.strip():
        return ["no atem: every item has one line"]
    out = []
    if "\n" in atem:
        out.append("an atem is one line")
    lo, hi = ATEM_CJK_CHARS if lang in CJK else ATEM_WORDS
    n = _count(atem, lang)
    if not lo <= n <= hi:
        unit = "characters" if lang in CJK else "words"
        out.append(f"{n} {unit}: an atem has {lo} to {hi}")
    if re.search(r"(?<!\.)[.。]$", atem.strip()):
        out.append("no final period: an atem is a phrase")
    if len(_sentences(atem, lang)) > 1:
        out.append("one phrase, not sentences")
    if _ID_RE.search(atem):
        out.append("no ids in an atem")
    if _MARKUP_RE.search(atem) or _HTML_TAG.search(atem):
        out.append("no markup in an atem")
    return out


def _slug(s: str, n: int = 60) -> str:
    """An ASCII id slug: lowercased, every run outside a-z and 0-9 a hyphen."""
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    a = re.sub(r"[^a-z0-9]+", "-", a).strip("-")[:n].strip("-")
    return a or "h" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:6]


def anchor_of(heading_text: str) -> str:
    """The anchor the reader's `slugifyHeadings` gives a heading, without its prefix: `sec-18-4` for a numbered
    one, else its text lowercased with every run of non-letters a hyphen (48 characters at most)."""
    txt = _plain(heading_text)
    m = re.match(r"^(\d+(?:\.\d+)*)\.?(?:\s|$)", txt)
    if m:
        return "sec-" + m.group(1).replace(".", "-")
    s = unicodedata.normalize("NFKC", txt.lower())
    return re.sub(r"[\W_]+", "-", s).strip("-")[:48] or "section"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(p: Path) -> str | None:
    try:
        return _sha(p.read_bytes())
    except OSError:
        return None


def _span(a: int, b: int) -> str:
    return str(a) if a == b else f"{a}-{b}"


def _loc(path: str, a: int, b: int) -> str:
    return f"{path}#L{a}" if a == b else f"{path}#L{a}-L{b}"


def _derived(path: str, a: int, b: int) -> dict:
    return {"mode": "derived", "sources": [_loc(path, a, b)], "confidence": 1, "state": "known"}


# ---------------------------------------------------------------------------
# Markdown, read line by line
# ---------------------------------------------------------------------------

@dataclass
class _Line:
    no: int                      # 1-based
    start: int                   # offset of its first character
    end: int                     # offset just past its newline
    text: str                    # without the newline (and without a CR before it)
    eol: str                     # "\n", "\r\n" or "" at the end of the text
    code: bool = False           # inside a fenced block (the fences included)
    comment: bool = False        # inside a multi-line HTML comment
    fence_end: int = -1          # on a fence's opening line: the index of its closing line


_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_NUMBER = re.compile(r"^((?:\d+|[A-Z](?=\.\d))(?:\.\d+)*)\.?(?:[ \t]+(.*))?$")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])[ \t]+")


@dataclass
class _Fence:
    open: int                    # line index of the opening fence
    close: int                   # line index of the closing fence (the last line when unclosed)
    info: str
    content: str


def _scan(text: str) -> tuple[list[_Line], list[_Fence]]:
    lines: list[_Line] = []
    i, n, no = 0, len(text), 0
    while i < n:
        j = text.find("\n", i)
        end = n if j < 0 else j + 1
        raw = text[i:end]
        eol = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
        no += 1
        lines.append(_Line(no, i, end, raw[:len(raw) - len(eol)], eol))
        i = end
    fences: list[_Fence] = []
    k = 0
    in_comment = False
    while k < len(lines):
        ln = lines[k]
        if in_comment:
            ln.comment = True
            if "-->" in ln.text:
                in_comment = False
            k += 1
            continue
        m = _FENCE_OPEN.match(ln.text)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            ch, width, info = m.group(1)[0], len(m.group(1)), m.group(2).strip()
            close_rx = re.compile(rf"^ {{0,3}}{re.escape(ch)}{{{width},}}[ \t]*$")
            e = k + 1
            while e < len(lines) and not close_rx.match(lines[e].text):
                e += 1
            last = min(e, len(lines) - 1)
            for x in range(k, last + 1):
                lines[x].code = True
            ln.fence_end = last
            body_end = lines[e].start if e < len(lines) else len(text)
            fences.append(_Fence(k, last, info, text[ln.end:body_end] if k + 1 <= last or e < len(lines) else ""))
            k = last + 1
            continue
        t = ln.text
        if "<!--" in t and "-->" not in t[t.rfind("<!--"):]:
            in_comment = True
        k += 1
    return lines, fences


@dataclass
class _Block:
    kind: str                    # para | list | table | quote | code | comment | hr
    first: int                   # line index
    last: int
    lines: list = field(default_factory=list)   # the _Line objects


def _blocks(lines: list[_Line], a: int, b: int) -> list[_Block]:
    """Lines a..b (inclusive indices) grouped into blocks separated by blank lines; a fence is one code block."""
    out: list[_Block] = []
    cur: list[_Line] = []

    def flush():
        if not cur:
            return
        t0 = cur[0].text.lstrip()
        if t0.startswith("|"):
            kind = "table"
        elif t0.startswith(">"):
            kind = "quote"
        elif re.fullmatch(r"(?:[-*_][ \t]*){3,}", t0):
            kind = "hr"
        elif _LIST_ITEM.match(cur[0].text):
            kind = "list"
        else:
            kind = "para"
        out.append(_Block(kind, cur[0].no - 1, cur[-1].no - 1, list(cur)))
        cur.clear()

    k = a
    while k <= b:
        ln = lines[k]
        if ln.code:
            flush()
            e = min(max(ln.fence_end, k), b)             # a fence is one block, opening line to closing line
            out.append(_Block("code", k, e, lines[k:e + 1]))
            k = e + 1
            continue
        if not ln.text.strip():
            flush()
        elif ln.comment or ln.text.strip().startswith("<!--"):
            flush()                                     # an HTML comment is a block of its own (a marker)
            s = k
            while k + 1 <= b and lines[k + 1].comment:
                k += 1
            out.append(_Block("comment", s, k, lines[s:k + 1]))
        else:
            cur.append(ln)
        k += 1
    flush()
    return out


def _block_text(b: _Block) -> str:
    return "\n".join(x.text for x in b.lines)


def _list_items(b: _Block) -> list[tuple[int, str, str]]:
    """(line index, marker, text) for each item of a list block, continuation lines joined to their item."""
    items: list[list] = []
    for ln in b.lines:
        m = _LIST_ITEM.match(ln.text)
        if m and (not items or len(m.group(1)) <= len(items[-1][3])):
            items.append([ln.no - 1, m.group(2), ln.text[m.end():], m.group(1)])
        elif items:
            items[-1][2] += " " + ln.text.strip()
    return [(i, mk, t) for i, mk, t, _ in items]


def _table_rows(b: _Block) -> list[list[str]]:
    rows = []
    for ln in b.lines:
        t = ln.text.strip()
        if not t.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", t.strip("|"))]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def _mask_code(text: str) -> str:
    """One line with inline code spans, inline HTML comments and link targets blanked: what mentions skip."""
    s = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), text)
    s = re.sub(r"(`+)(.+?)\1", lambda m: " " * len(m.group(0)), s)
    s = re.sub(r"\]\([^)]*\)", lambda m: "]" + " " * (len(m.group(0)) - 1), s)
    s = re.sub(r"<code>.*?</code>", lambda m: " " * len(m.group(0)), s)
    return s


# ---------------------------------------------------------------------------
# Section references and term uses
# ---------------------------------------------------------------------------

_NUM = r"\d+(?:\.\d+)*"
_JOIN = r"(?:\s*(?:,|、|and|or|und|oder|et|ou|y|o|to|bis|à|a|–|—|-|〜|～|から)\s*)"
_SEC_REF = re.compile(
    rf"(?P<its>\bits\s+)?(?<![\w-])(?:[Ss]ections?|[Ss]ecci[oó]n(?:es)?|Abschnitt(?:en|e)?|セクション)\s*"
    rf"(?P<list>{_NUM}(?:{_JOIN}(?:§\s*)?{_NUM})*)")
_ZH_REF = re.compile(rf"第\s*({_NUM})\s*节")
_SIGN_REF = re.compile(rf"(?P<readme>README\s+)?§\s*(?P<list>{_NUM}(?:\s*(?:,|–|—|-|to|and)\s*§?\s*{_NUM})*)")
_P_REF = re.compile(r"(?<![\w.:/-])P\.(\d+(?:\.\d+)*)(?![\w-]|\.\w)")
_RANGE = {"to", "bis", "à", "a", "–", "—", "-", "〜", "～", "から"}


def _numbers(listing: str) -> list[str]:
    """'4 to 14' -> 4..14; '2.1, 2.2 and 2.4' -> each; a range expands only between two whole numbers."""
    parts = re.split(rf"({_JOIN})", listing)
    nums: list[str] = []
    pending_range = False
    for p in parts:
        p = p.strip().lstrip("§").strip()
        if not p:
            continue
        if re.fullmatch(_NUM, p):
            if pending_range and nums and nums[-1].isdigit() and p.isdigit() and 0 < int(p) - int(nums[-1]) <= 40:
                nums += [str(x) for x in range(int(nums[-1]) + 1, int(p) + 1)]
            else:
                nums.append(p)
            pending_range = False
        else:
            pending_range = p.lower() in _RANGE
    return nums


@dataclass
class _Refs:
    sections: list = field(default_factory=list)    # numbers in this document
    xrefs: list = field(default_factory=list)       # (inventory, kind, id)


def _refs_in(masked: str, doc_xref: dict, *, own_p: bool) -> _Refs:
    """The section references in one passage of masked prose. `doc_xref` maps § / README § / P. to a chapter's
    inventory (the spec's convention); without it § names this document's own sections. `own_p`: P.N names this
    document's own chapter P (inside Comprise's spec)."""
    out = _Refs()
    for m in _SEC_REF.finditer(masked):
        if m.group("its"):
            continue                                    # "its section 10": another document's section
        out.sections += _numbers(m.group("list"))
    for m in _ZH_REF.finditer(masked):
        out.sections.append(m.group(1))
    for m in _SIGN_REF.finditer(masked):
        nums = _numbers(m.group("list"))
        key = "README §" if m.group("readme") else "§"
        target = doc_xref.get(key)
        if (m.group("readme") and not target) or target == "":
            continue                                    # another document's sections: not linked
        if target:
            out.xrefs += [(target, "section", x) for x in nums]
        else:
            out.sections += nums
    for m in _P_REF.finditer(masked):
        if own_p:
            out.sections.append("P." + m.group(1))
        elif doc_xref.get("P."):
            out.xrefs.append((doc_xref["P."], "section", "P." + m.group(1)))
    return out


def _distinctive(name: str) -> bool:
    """A term name whose plain use is unlikely to be ordinary prose: several words, or a capital, digit or
    symbol inside it."""
    return " " in name.strip() or bool(re.search(r".[A-Z0-9]|[^\w\s]", name.strip()))


class _TermMatcher:
    """Whole-word, case-insensitive uses of a set of term names (and their plurals), outside code."""

    def __init__(self, terms: dict[str, str], lang: str, plain: str):
        self.by: dict[str, str] = {}
        self.bold_only: set[str] = set()
        for name, tid in terms.items():
            key = name.casefold()
            if key and key not in self.by:
                self.by[key] = tid
                if plain == "distinctive" and not _distinctive(name):
                    self.bold_only.add(key)
        names = sorted(self.by, key=len, reverse=True)
        self.rx = None
        if names:
            alt = "|".join(re.escape(n) for n in names)
            if lang in CJK:
                self.rx = re.compile(rf"(?P<b>\*\*)?(?P<t>{alt})", re.I)
            else:
                self.rx = re.compile(rf"(?P<b>\*\*)?(?<![\w-])(?P<t>(?:{alt})(?:e?s)?)(?![\w-])", re.I)

    def find(self, masked: str) -> list[str]:
        out: list[str] = []
        if self.rx is None:
            return out
        for m in self.rx.finditer(masked):
            t = m.group("t").casefold()
            key = t if t in self.by else (t[:-2] if t.endswith("es") and t[:-2] in self.by else
                                          (t[:-1] if t.endswith("s") and t[:-1] in self.by else None))
            if key is None:
                continue
            if key in self.bold_only and not m.group("b"):
                continue
            tid = self.by[key]
            if tid not in out:
                out.append(tid)
        return out


# ---------------------------------------------------------------------------
# Enumerating one markdown document
# ---------------------------------------------------------------------------

_ATEM_MARK = re.compile(r"^\s*<!--\s*atem:\s*(.*?)\s*-->\s*$")
_TERM_MARK = re.compile(r"^\s*<!--\s*term:\s*(.*?)\s*-->\s*$")
_BOLD_LABEL = re.compile(r"^\*\*([^*]+?[.:：])\*\*\s*")
_SEP = r"(?:—|–|--|:|：|——|-)"
_BULLET_TERM = re.compile(rf"^\*\*(?P<t>[^*]+?)\*\*\s*(?P<sep>{_SEP})\s*(?P<rest>.*)$")
_SENTENCE_TERM = re.compile(
    r"^(?:(?:A|An|The) )?\*\*(?P<t>[^*]+?)\*\*(?P<paren> \([^)]*\))?,? "
    r"(?P<verb>is|are|means|stands for|turns|holds|names) (?P<rest>.*)$")
_LOOSE_LEAD = re.compile(r"^(?:\S+\s)?\*\*(?P<t>[^*]+?)\*\*")


def _term_name(bold: str) -> str:
    return _plain(bold).strip().rstrip(".:：").strip()


@dataclass
class _Sec:
    """One section while enumerating: its heading and body lines, and what its body holds."""
    sid: str
    kind: str                    # front | heading
    level: int
    number: str | None
    name: str
    heading: str | None
    eol: str
    first: int                   # line index of the heading (or the first line of the front)
    a: int                       # first body line index
    b: int                       # last body line index (a - 1 when empty)
    body: str
    parent: str | None = None
    parts: list = field(default_factory=list)


@dataclass
class _Aux:
    """What a translated telling needs from the author's: each term's place among the loose candidates."""
    term_pos: dict = field(default_factory=dict)    # term id -> (section id, class, index)
    terms: dict = field(default_factory=dict)       # term id -> its item
    cands: dict = field(default_factory=dict)       # section id -> {class: [candidates]}
    sections: dict = field(default_factory=dict)    # section id -> its item


def _candidates(blocks: list[_Block], how_to_read: bool) -> dict[str, list[dict]]:
    """Every place in a section that could define a term, in order, by class, whatever the language: bold first
    cells of table rows; bullets that open with a bold phrase and a separator; paragraphs that open with a bold
    phrase; the first column of a "How to read this" table; and `<!-- term: x -->` markers."""
    out: dict[str, list[dict]] = {"table": [], "bullet": [], "sentence": [], "glossary": [], "marker": []}
    marker: str | None = None
    for blk in blocks:
        if blk.kind == "comment":
            m = _TERM_MARK.match(blk.lines[0].text) if len(blk.lines) == 1 else None
            if m:
                marker = m.group(1)
            continue
        if marker is not None and blk.kind in ("para", "list", "quote"):
            text = _block_text(blk)
            out["marker"].append({"name": marker.strip(), "rest": text, "line": blk.first, "full": text})
            marker = None
            continue
        marker = None
        if blk.kind == "table":
            rows = _table_rows(blk)
            for r, row in enumerate(rows[1:], start=1):
                if not row:
                    continue
                line = blk.first + _row_line(blk, row)
                if how_to_read:
                    out["glossary"].append({"name": _term_name(row[0]), "rest": row[1] if len(row) > 1 else "",
                                            "example": row[2] if len(row) > 2 else "", "line": line})
                m = re.fullmatch(r"\*\*(.+)\*\*", row[0])
                if m:
                    out["table"].append({"name": _term_name(m.group(1)), "rest": row[1] if len(row) > 1 else "",
                                         "line": line})
        elif blk.kind == "list":
            for idx, marker_char, text in _list_items(blk):
                if marker_char[0].isdigit():
                    continue
                m = _BULLET_TERM.match(text)
                if m and not m.group("t").rstrip().endswith((".", ":", "：", "。")):
                    out["bullet"].append({"name": _term_name(m.group("t")), "rest": m.group("rest"), "line": idx,
                                          "sep": m.group("sep")})
        elif blk.kind == "para":
            text = " ".join(x.text.strip() for x in blk.lines)
            m = _LOOSE_LEAD.match(text)
            if m and not m.group("t").rstrip().endswith((".", ":", "：", "。", "!", "?")):
                out["sentence"].append({"name": _term_name(m.group("t")), "rest": text, "line": blk.first,
                                        "full": text})
    return out


def _row_line(blk: _Block, row: list[str]) -> int:
    for k, ln in enumerate(blk.lines):
        if ln.text.strip().startswith("|") and row[0] in ln.text:
            return k
    return 0


def _strict(cls: str, cand: dict, lang: str) -> dict | None:
    """The author's conventions, which decide what is a term in the author's telling: every table, glossary,
    marker and bullet candidate; a paragraph only when it reads `(A|An|The) **term** is …`."""
    if cls != "sentence":
        return cand
    m = _SENTENCE_TERM.match(cand["full"])
    if not m:
        return None
    return {**cand, "name": _term_name(m.group("t")), "verb": m.group("verb"), "pred": m.group("rest")}


def _term_meaning(cls: str, cand: dict, lang: str) -> tuple[str, str]:
    """(summary, atem) for one term definition."""
    if cls == "sentence":
        sents = _sentences(_plain(cand["full"]), lang)
        summary = sents[0] if sents else _plain(cand["full"])
        pred = cand.get("pred")
        if pred is not None and lang == "en":
            pred_plain = _plain(pred)
            verb = cand.get("verb", "is")
            pred_first = (_sentences(pred_plain, lang) or [pred_plain])[0]
            atem = _atem_cut(pred_first if verb in ("is", "are", "means") else f"{verb} {pred_first}", lang)
        else:
            atem = _atem_of(_plain(re.sub(r"^\S*\s*\*\*[^*]+\*\*", "", cand["full"])), lang) or \
                _atem_cut(summary, lang)
        return summary, atem
    rest = _plain(cand.get("rest", ""))
    summary = (_sentences(rest, lang) or [rest])[0] if rest else cand["name"]
    atem = _atem_of(rest, lang) if rest and _count(rest, lang) >= 3 else None
    if not atem and cls == "glossary" and rest:
        atem = _atem_cut(f"{cand['name']}, called {rest} in the files", lang) if lang == "en" else \
            _atem_cut(f"{cand['name']}: {rest}", lang)
    if not atem or atem_problems(atem, lang):
        atem = _atem_cut(f"{cand['name']}, {rest}" if rest else f"the term {cand['name']}", lang)
    return summary, atem


def _first_prose(blocks: list[_Block], lang: str) -> tuple[str | None, str | None]:
    """(summary, atem) from a section's first prose: a paragraph (not one wholly in italics), a quote, or the
    first item of an unordered list; tables, code, ordered lists and comments are skipped. A bold lead label
    (`**What it enumerates.**`) is not part of the sentence."""
    for blk in blocks:
        if blk.kind in ("para", "quote"):
            text = " ".join(x.text.strip().lstrip(">").strip() for x in blk.lines)
            if re.fullmatch(r"\*[^*].*\*|_[^_].*_", text.strip()):
                continue
            text = _BOLD_LABEL.sub("", text)
        elif blk.kind == "list":
            items = _list_items(blk)
            if not items or items[0][1][0].isdigit():
                continue
            text = items[0][2]
        else:
            continue
        plain = _plain(text)
        if not plain:
            continue
        atem = _atem_of(plain, lang)
        if atem:
            sents = _sentences(plain, lang)
            return (sents[0] if sents else plain), atem
    return None, None


def _enumerate(text: str, *, doc_id: str, lang: str, source_path: str, chapter: Chapter | None = None,
               reference: tuple | None = None, xref: dict | None = None, plain_mentions: str = "all",
               registry: mc.Registry | None = None, order_start: int = 0, doc_name: str | None = None
               ) -> tuple[list[dict], _Aux, int]:
    """(items, aux, next order) for one document. `reference` is the author's telling's (items, aux) when this is
    a translation: ids come from it, words from this text."""
    lines, fences = _scan(text)
    prefix = f"{chapter.prefix}." if chapter else ""
    chap_id = f"S:chapter/{chapter.slug}" if chapter else None

    # Sections: every ATX heading outside a fence or a comment.
    heads = []
    for k, ln in enumerate(lines):
        if ln.code or ln.comment:
            continue
        m = _HEADING.match(ln.text)
        if m:
            raw = m.group(2) or ""
            raw = re.sub(r"[ \t]+#+$", "", raw)
            if re.fullmatch(r"#+", raw):
                raw = ""
            heads.append((k, len(m.group(1)), raw))
    secs: list[_Sec] = []
    used: set[str] = set()

    def unique(base: str) -> str:
        sid, n = base, 2
        while sid in used:
            sid, n = f"{base}-{n}", n + 1
        used.add(sid)
        return sid

    first_head = heads[0][0] if heads else len(lines)
    if first_head > 0 and text[:lines[first_head].start if heads else len(text)]:
        end = lines[first_head].start if heads else len(text)
        secs.append(_Sec(unique(f"{prefix}front"), "front", 0, None, "front matter", None, "", 0, 0,
                         first_head - 1, text[:end]))
    root_taken = False
    for h, (k, level, raw) in enumerate(heads):
        nxt = heads[h + 1][0] if h + 1 < len(heads) else len(lines)
        body_start = lines[k].end
        body_end = lines[nxt].start if nxt < len(lines) else len(text)
        m = _NUMBER.match(raw.strip())
        number, name = (m.group(1), (m.group(2) or m.group(1)).strip()) if m else (None, raw.strip())
        if number is not None:
            base = prefix + number
        elif level == 1 and not root_taken:
            base = prefix + "root"
            root_taken = True
        else:
            base = prefix + _slug(_plain(name))
        sec = _Sec(unique(base), "heading", level, number, _plain(name) or (number or "untitled"),
                   lines[k].text, lines[k].eol, k, k + 1, nxt - 1, text[body_start:body_end])
        secs.append(sec)

    # The tree: a heading's parent is the nearest heading above it with a lower level.
    stack: list[_Sec] = []
    tops: list[str] = []
    for s in secs:
        if s.kind == "front":
            tops.append(s.sid)
            continue
        while stack and stack[-1].level >= s.level:
            stack.pop()
        if stack:
            s.parent = stack[-1].sid
            stack[-1].parts.append(s.sid)
        else:
            tops.append(s.sid)
            s.parent = chap_id
        stack.append(s)

    by_sid = {s.sid: s for s in secs}
    blocks_of = {s.sid: _blocks(lines, s.a, s.b) if s.b >= s.a else [] for s in secs}

    # In a translation, sections take the author's ids by number (and front/root by place).
    ref_items, ref_aux = reference if reference else (None, None)

    order = order_start
    items: list[dict] = []
    aux = _Aux()
    anchors: set[str] = set()

    # Terms first, so section mentions can find them.
    term_items: dict[str, dict] = {}
    term_cands: dict[str, dict] = {}
    for s in secs:
        how = s.name.casefold() == "how to read this"
        term_cands[s.sid] = _candidates(blocks_of[s.sid], how)

    def add_term(tid: str, name: str, cls: str, cand: dict, sec: _Sec) -> None:
        summary, atem = _term_meaning(cls, cand, lang)
        ln = cand["line"] + 1
        it = {"id": tid, "type": "term", "name": name, "summary": summary, "atem": atem,
              "defined_in": f"S:section/{sec.sid}"}
        if cls == "glossary":
            if cand.get("rest"):
                it["in_the_files"] = _plain(cand["rest"])
            if cand.get("example"):
                it["example"] = _plain(cand["example"])
        it["convention"] = cls
        if chap_id:
            it["chapter"] = chap_id
        it["lines"] = str(ln)
        it["provenance"] = _derived(source_path, ln, ln)
        term_items[tid] = it

    if ref_aux is None:
        # The author's telling: strong conventions define; a glossary row defines only what nothing else does.
        weak: list[tuple] = []
        for s in secs:
            for cls, cands in term_cands[s.sid].items():
                for idx, cand in enumerate(cands):
                    st = _strict(cls, cand, lang)
                    if st is None or not st["name"]:
                        continue
                    tid = f"T:term/{prefix}{_slug(st['name'])}"
                    if cls == "glossary":
                        weak.append((tid, st, s, idx))
                        continue
                    if tid in term_items:
                        again = term_items[tid].setdefault("also_defined_in", [])
                        if f"S:section/{s.sid}" not in again:
                            again.append(f"S:section/{s.sid}")
                        continue
                    add_term(tid, st["name"], cls, st, s)
                    aux.term_pos[tid] = (s.sid, cls, idx)
        for tid, st, s, idx in weak:
            if tid in term_items:
                files = _plain(st.get("rest", ""))
                if files and "in_the_files" not in term_items[tid]:
                    term_items[tid]["in_the_files"] = files
                continue
            add_term(tid, st["name"], "glossary", st, s)
            aux.term_pos[tid] = (s.sid, "glossary", idx)
    else:
        ref_terms = {it["id"]: it for it in ref_items if it.get("type") == "term"}
        ref_cands = ref_aux.cands
        for tid, (sid, cls, idx) in ref_aux.term_pos.items():
            en = ref_terms[tid]
            mine = term_cands.get(sid, {}).get(cls, [])
            theirs = ref_cands.get(sid, {}).get(cls, [])
            sec = by_sid.get(sid)
            if sec is not None and len(mine) == len(theirs) and idx < len(mine) and mine[idx]["name"]:
                cand = mine[idx]
                add_term(tid, cand["name"], cls, cand, sec)
                if en.get("also_defined_in"):                # the fabula's facts are the author's
                    term_items[tid]["also_defined_in"] = list(en["also_defined_in"])
            else:                                       # told from the author's telling, and marked so
                term_items[tid] = {**{k: v for k, v in en.items() if k != "order"}, "fallback": "en"}
    aux.cands = term_cands

    term_names = {it["name"]: tid for tid, it in term_items.items()}
    matcher = _TermMatcher(term_names, lang, plain_mentions)
    doc_xref = dict(xref or {}) or (dict(chapter.xref) if chapter else {})
    own_p = chapter is not None and chapter.prefix == "comprise"

    # Examples: every ```cosm block, numbered in order through the document.
    reg = registry or mc.default_registry()
    example_n = 0
    examples_in: dict[str, list[dict]] = {}
    for f in fences:
        words = f.info.split()
        if not words or words[0] != "cosm":
            continue
        example_n += 1
        owner = next((s for s in reversed(secs) if s.first <= f.open), None)
        if owner is None:
            continue
        examples_in.setdefault(owner.sid, []).append({"n": example_n, "fence": f})

    for s in secs:
        blocks = blocks_of[s.sid]
        order += 1
        sec_order = order
        # Words: the atem marker, else the first prose, else the section's place.
        marker = None
        for k in range(s.a, s.b + 1):
            if lines[k].text.strip():
                m = _ATEM_MARK.match(lines[k].text)
                marker = m.group(1).strip() if m else None
                break
        summary, atem = _first_prose(blocks, lang)
        parent_name = by_sid[s.parent].name if s.parent in by_sid else (doc_name or "")
        if not atem:
            if s.parts:
                kids = ", ".join(by_sid[p].name for p in s.parts[:4])
                atem = _atem_cut(f"{s.name}: {kids}", lang)
            else:
                atem = _atem_cut(f"{s.name}, in {parent_name}" if parent_name else f"{s.name}", lang)
            if _count(atem, lang) < ATEM_WORDS[0]:
                atem = _atem_cut(f"the section {s.name}", lang)
        if marker:
            atem = marker
        if not summary:
            summary = atem
        it: dict = {"id": f"S:section/{s.sid}", "type": "section", "name": s.name, "summary": summary,
                    "atem": atem}
        if s.number is not None:
            it["number"] = s.number
        it["level"] = s.level
        if s.heading is not None:
            it["heading"] = s.heading
            if s.eol != "\n":
                it["eol"] = s.eol
        if s.parent:
            it["parent"] = f"S:section/{s.parent}" if s.parent in by_sid else s.parent
        if s.parts:
            it["parts"] = [f"S:section/{p}" for p in s.parts]
        # Mentions: section references and term uses in the section's own prose, outside code.
        masked = "\n".join(_mask_code(lines[k].text) for k in range(s.a, s.b + 1)
                           if not lines[k].code and not lines[k].comment)
        refs = _refs_in(masked, doc_xref, own_p=own_p)
        mentions: list[str] = []
        for num in refs.sections:
            target = f"S:section/{prefix}{num}"
            if target != it["id"] and target not in mentions:
                mentions.append(target)
        for tid in matcher.find(masked):
            if term_items[tid]["defined_in"] != it["id"] and tid not in mentions:
                mentions.append(tid)
        if mentions:
            it["mentions"] = mentions
        xrefs = []
        for inv, kind, ident in refs.xrefs:
            x = f"{inv}@{_inventory_version(inv)}:{kind}:{ident}"
            if x not in xrefs:
                xrefs.append(x)
        if xrefs:
            it["xrefs"] = xrefs
        if chap_id:
            it["chapter"] = chap_id
        it["order"] = sec_order
        a_line = s.first + 1
        b_line = max(s.b + 1, a_line)
        it["lines"] = _span(a_line, b_line)
        anc = anchor_of(s.heading.lstrip("# ") if s.heading else "front")
        a2, n2 = anc, 2
        while a2 in anchors:
            a2, n2 = f"{anc}-{n2}", n2 + 1
        anchors.add(a2)
        it["anchor"] = a2
        it["provenance"] = _derived(source_path, a_line, b_line)
        it["body"] = s.body
        items.append(it)
        aux.sections[it["id"]] = it

        # The terms this section defines, the examples it holds, the decisions it records — after it, in order.
        local: list[tuple[int, dict]] = []
        for tid, t in term_items.items():
            if t["defined_in"] == f"S:section/{s.sid}" and not t.get("fallback"):
                local.append((int(t["lines"]), t))
        for ex in examples_in.get(s.sid, []):
            local.append((ex["fence"].open + 1, _example(ex, s, blocks, lines, prefix, source_path, reg, lang,
                                                         chap_id)))
        if s.name.casefold().startswith("decisions"):
            for d in _decisions(s, blocks, lines, prefix, source_path, lang, doc_xref, own_p, matcher,
                                term_items, chap_id):
                local.append((int(d["lines"].split("-")[0]), d))
        for _, x in sorted(local, key=lambda p: p[0]):
            order += 1
            items.append(_with_order(x, order))
    for tid, t in list(term_items.items()):              # a translation's terms told from the author's telling
        if t.get("fallback"):
            order += 1
            term_items[tid] = _with_order(t, order)
            items.append(term_items[tid])
    aux.term_pos = aux.term_pos if ref_aux is None else ref_aux.term_pos
    for t in term_items.values():
        aux.terms[t["id"]] = t
    return items, aux, order


def _with_order(it: dict, order: int) -> dict:
    """`order` set in place, just before `lines` (the item's place in the telling, beside where it is)."""
    rest = {k: v for k, v in it.items() if k != "order"}
    it.clear()
    for k, v in rest.items():
        if k == "lines":
            it["order"] = order
        it[k] = v
    if "order" not in it:
        it["order"] = order
    return it


def _example(ex: dict, s: _Sec, blocks: list[_Block], lines: list[_Line], prefix: str, source_path: str,
             reg: mc.Registry, lang: str, chap_id: str | None) -> dict:
    f: _Fence = ex["fence"]
    n = ex["n"]
    body = f.content
    decl, label = None, None
    try:
        data = mc.yaml_load(body)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        d = reg.identify(data)
        decl = d.value if isinstance(d, mc.Declaration) else None
        brand = data.get("brand") if isinstance(data.get("brand"), dict) else {}
        label = data.get("name") or brand.get("name") or data.get("id")
    lead = None
    prev = [b for b in blocks if b.last < f.open]
    if prev and prev[-1].kind == "para" and prev[-1].last >= f.open - 2:
        text = _BOLD_LABEL.sub("", " ".join(x.text.strip() for x in prev[-1].lines))
        lead = _atem_of(_plain(text), lang)
        lead_summary = (_sentences(_plain(text), lang) or [None])[0]
    else:
        lead_summary = None
    atem = lead or _atem_cut(f"a complete {decl or 'cosm'} file, in {s.name}", lang)
    name = f"example {n}" + (f": {_plain(str(label))}" if label else "")
    it: dict = {"id": f"S:example/{prefix}{n}", "type": "example", "name": name,
                "summary": lead_summary or atem, "atem": atem, "in": f"S:section/{s.sid}"}
    if decl:
        it["declaration"] = decl
    if chap_id:
        it["chapter"] = chap_id
    a, b = f.open + 1, f.close + 1
    it["lines"] = _span(a, b)
    it["provenance"] = _derived(source_path, a, b)
    it["body"] = body
    return it


def _decisions(s: _Sec, blocks: list[_Block], lines: list[_Line], prefix: str, source_path: str, lang: str,
               doc_xref: dict, own_p: bool, matcher: _TermMatcher, terms: dict, chap_id: str | None) -> list[dict]:
    out = []
    for blk in blocks:
        if blk.kind != "list":
            continue
        raw_items: list[list] = []
        for ln in blk.lines:
            m = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*(.*)$", ln.text)
            if m:
                raw_items.append([m.group(1), m.group(2), [ln]])
            elif raw_items:
                raw_items[-1][2].append(ln)
        for num, lead, item_lines in raw_items:
            text = " ".join(x.text.strip() for x in item_lines)
            rest = _plain(re.sub(r"^\d+\.\s+\*\*.+?\*\*", "", text))
            name = _plain(lead).rstrip(".").strip()
            summary = (_sentences(rest, lang) or [name])[0] if rest.strip(" ,.") else name
            atem = _atem_cut(name, lang)
            if atem_problems(atem, lang):
                atem = _atem_of(rest, lang) or _atem_of(_plain(text), lang) or \
                    _atem_cut(f"decision {num} of {s.name}", lang)
            masked = "\n".join(_mask_code(x.text) for x in item_lines)
            refs = _refs_in(masked, doc_xref, own_p=own_p)
            about = [f"S:section/{prefix}{x}" for x in dict.fromkeys(refs.sections)]
            about += [t for t in matcher.find(masked) if t not in about]
            a, b = item_lines[0].no, item_lines[-1].no
            it: dict = {"id": f"S:decision/{prefix}{num}", "type": "decision", "name": name, "summary": summary,
                        "atem": atem, "number": num, "in": f"S:section/{s.sid}"}
            if about:
                it["about"] = about
            xr = [f"{inv}@{_inventory_version(inv)}:{k}:{i}" for inv, k, i in refs.xrefs]
            if xr:
                it["xrefs"] = list(dict.fromkeys(xr))
            if chap_id:
                it["chapter"] = chap_id
            it["lines"] = _span(a, b)
            it["provenance"] = _derived(source_path, a, b)
            it["body"] = "".join(x.text + x.eol for x in item_lines)
            out.append(it)
    return out


def _inventory_version(inv: str) -> str:
    """The version a cross-volume reference names: a chapter's own, or a document's."""
    for d in DOCUMENTS.values():
        for c in d.chapters:
            if c.prefix == inv:
                return c.version
        if d.slug == inv:
            return d.version
    return "1"


def enumerate_markdown(text: str, *, doc_id: str, lang: str = "en", voice: str | None = None,
                       source_path: str, chapter: Chapter | dict | None = None, reference_text: str | None = None,
                       name: str | None = None, version: str | None = None, xref: dict | None = None,
                       plain_mentions: str = "all", registry: mc.Registry | None = None,
                       chapter_meta: dict | None = None) -> dict:
    """One markdown document as a doc catalog (a mapping with `nodes`): its sections (`S:section/<n>`, `root` for
    the title, `front` for any text before it, a slug for an unnumbered heading) with their bodies verbatim, the
    terms it defines, the section references and term uses each section makes (`mentions`), its ```cosm examples
    and its decisions. `reference_text` is the author's telling when this is a translation: ids come from it,
    words from `text`. With `chapter`, the items carry the chapter's prefix and the mapping holds the chapter item
    first; `chapter_meta` gives its commit and hash."""
    slug = doc_id.removeprefix("doc/")
    chap = Chapter(**chapter) if isinstance(chapter, dict) else chapter
    reference = None
    if reference_text is not None:
        ref_items, ref_aux, _ = _enumerate(reference_text, doc_id=slug, lang="en", source_path=source_path,
                                           chapter=chap, xref=xref, plain_mentions=plain_mentions,
                                           registry=registry, doc_name=name)
        reference = (ref_items, ref_aux)
    items, _aux, _ = _enumerate(text, doc_id=slug, lang=lang, source_path=source_path, chapter=chap,
                                reference=reference, xref=xref, plain_mentions=plain_mentions, registry=registry,
                                doc_name=name)
    if reference is not None:
        _take_author_ids(items, reference[0])
    root = next((it for it in items if it["id"].endswith("/root") or it["id"].endswith(".root")), None)
    title = name or (root["name"] if root else slug)
    if chap is not None:
        meta = chapter_meta or {}
        tops = [it["id"] for it in items if it.get("type") == "section" and it.get("parent") ==
                f"S:chapter/{chap.slug}"]
        prov = {"mode": "catalogue", "sources": [f"comprise-dev {chap.source} @ {meta.get('commit') or 'unknown'}"],
                "confidence": 1, "state": "known"}
        if meta.get("sha256"):
            prov["hash"] = meta["sha256"]
        rtitle = root["name"] if root else chap.slug
        citem = {"id": f"S:chapter/{chap.slug}", "type": "chapter", "name": rtitle,
                 "summary": f"{rtitle}, synced read-only from comprise-dev {chap.source}"
                            + (f" at {meta['commit']}" if meta.get("commit") else "") + ".",
                 "atem": _atem_cut(f"{rtitle}, in {chap.label}'s own words"),
                 "parts": tops, "path": source_path, "source": chap.source, "commit": meta.get("commit"),
                 "sha256": meta.get("sha256"), "prefix": chap.prefix, "version": chap.version,
                 "provenance": prov}
        return {"nodes": [citem] + items}
    telling = {"lang": lang, **({"voice": voice} if voice else {})}
    cat = {"oes": OES, "macrocosm": mc.MACROCOSM_VERSION, "id": f"doc/{slug}", "name": title,
           "document": {"path": source_path, "sha256": _sha(text.encode("utf-8")), "version": version or ""},
           "telling": telling, "nodes": items}
    return cat


def _take_author_ids(items: list[dict], ref_items: list[dict]) -> None:
    """A translation's unnumbered headings (anything but the title and the front) take the author's ids by place
    among the unnumbered headings; numbered ones already match."""
    def unnumbered(xs):
        return [x for x in xs if x.get("type") == "section" and "number" not in x
                and not re.search(r"(^|[/.])(root|front)$", x["id"])]
    mine, theirs = unnumbered(items), unnumbered(ref_items)
    if len(mine) != len(theirs):
        return
    remap = {a["id"]: b["id"] for a, b in zip(mine, theirs)}
    for it in items:
        if it["id"] in remap:
            it["id"] = remap[it["id"]]
        for k in ("parent", "defined_in", "in"):
            if isinstance(it.get(k), str) and it[k] in remap:
                it[k] = remap[it[k]]
        for k in ("parts", "mentions", "about", "also_defined_in", "see"):
            if isinstance(it.get(k), list):
                it[k] = [remap.get(x, x) for x in it[k]]


# ---------------------------------------------------------------------------
# Bubbles: static/help-docs.md
# ---------------------------------------------------------------------------

def enumerate_bubbles(help_docs_text: str, lang: str = "en", *,
                      source_path: str = "enough/static/help-docs.md") -> list[dict]:
    """Every `## <id>` section of a help-docs file as `B:bubble/<id>`: `what`, `how` and `ideas` verbatim, `about`
    the data-help id, `see` the Help Center sections its text names (or, for a bubble that describes another
    document, `xrefs` into that document); its atem is the first sentence of `what`."""
    lines, _fences = _scan(help_docs_text)
    out: list[dict] = []
    cur: dict | None = None
    part: str | None = None
    buf: list[_Line] = []

    def close_part():
        nonlocal buf
        if cur is not None and part is not None:
            texts = [x.text for x in buf]
            while texts and not texts[0].strip():
                texts.pop(0)
            while texts and not texts[-1].strip():
                texts.pop()
            cur[part] = "\n".join(texts)
        buf = []

    def close_bubble(last: int):
        if cur is None:
            return
        close_part()
        cur["_b"] = last
        out.append(cur)

    for k, ln in enumerate(lines):
        if ln.comment or (ln.text.lstrip().startswith("<!--") and cur is None):
            continue
        m = re.match(r"^## (\S+)\s*$", ln.text)
        if m and not ln.code:
            close_bubble(k)
            cur, part = {"_id": m.group(1), "_a": k + 1}, None
            continue
        if cur is None:
            continue
        m = re.match(r"^### (what|how|ideas)\s*$", ln.text)
        if m:
            close_part()
            part = m.group(1)
            continue
        if part is None:
            m = re.match(r"^(name|path):\s*(.*)$", ln.text)
            if m:
                cur["_" + m.group(1)] = m.group(2).strip()
            continue
        buf.append(ln)
    close_bubble(len(lines))

    items = []
    for b in out:
        bid = b["_id"]
        what = b.get("what", "")
        plain_what = _plain(what)
        atem = _atem_of(plain_what, lang) or _atem_cut(f"the {b.get('_name') or bid} bubble", lang)
        summary = (_sentences(plain_what, lang) or [atem])[0]
        it: dict = {"id": f"B:bubble/{_slug(bid) if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', bid) else bid}",
                    "type": "bubble", "name": b.get("_name") or bid, "summary": summary, "atem": atem,
                    "about": bid}
        if b.get("_path"):
            it["path"] = b["_path"]
        masked = "\n".join(_mask_code(_HTML_TAG.sub(" ", b.get(k, ""))) for k in ("what", "how", "ideas"))
        refs = _refs_in(masked, {}, own_p=False)
        nums = list(dict.fromkeys(refs.sections))
        other = BUBBLE_DOCUMENT.get(bid)
        if other:
            it["xrefs"] = [f"{other}@{_inventory_version(other)}:section:{x}" for x in nums]
        elif nums:
            it["see"] = [f"S:section/{x}" for x in nums]
        a, z = b["_a"], b["_b"]
        it["lines"] = _span(a, z)
        it["provenance"] = _derived(source_path, a, z)
        for k in ("what", "how", "ideas"):
            if k in b:
                it[k] = b[k]
        items.append(it)
    return items


# ---------------------------------------------------------------------------
# The reference: R: items generated from the manifests
# ---------------------------------------------------------------------------

def _subtree_hash(value: Any) -> str:
    return _sha(json.dumps(mc.jsonable(value), sort_keys=True, ensure_ascii=False).encode("utf-8"))[:16]


def _manifest_rel(m: mc.Manifest, root: Path) -> str:
    try:
        return m.path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, AttributeError, OSError):
        return f"{MANIFESTS_DIR}/{m.path.name}" if m.path else f"{MANIFESTS_DIR}/{m.name}.manifest.cosm"


def _list_source(field_path: str) -> str:
    return {"status": "envelope.status", "visibility": "envelope.visibility",
            "provenance.mode": "envelope.provenance.modes", "provenance.state": "envelope.provenance.states",
            "links.rel": "links.rels"}.get(field_path, f"closed-lists.{field_path}")


@dataclass
class SpecTables:
    """The hand-written lines the spec gives generated items, joined by id in a table's first cell: the checks
    (§12.2, §18.5.4: Check | Default severity | Catches), the lenses (§14.5: MiniCOSM | Lens | Draws), the
    MiniCOSMs (§18: MiniCOSM | … | Enumerates), the kinds (Kind | … | What it is, inside a MiniCOSM's section),
    and closed lists' values (a table whose first column is the list's field)."""
    checks: dict = field(default_factory=dict)       # id -> (severity, catches)
    lenses: dict = field(default_factory=dict)       # (minicosm, lens) -> draws
    minicosms: dict = field(default_factory=dict)    # name -> enumerates
    kinds: dict = field(default_factory=dict)        # (minicosm, kind) -> what it is
    lists: dict = field(default_factory=dict)        # (minicosm, field) -> {value: meaning}


def spec_tables(text: str) -> SpecTables:
    """Read the overlay tables out of the spec's markdown."""
    lines, _ = _scan(text)
    out = SpecTables()
    names_rx = re.compile(r"^#{3,4} (18\.\d+)(?:\.\d+)* ")
    mini_at: dict[str, str] = {}
    blocks = _blocks(lines, 0, len(lines) - 1) if lines else []
    heads = [(i, ln.text) for i, ln in enumerate(lines) if not ln.code and _HEADING.match(ln.text)]
    for i, t in heads:
        m = re.match(r"^### (18\.\d+) ([a-z][a-z0-9-]*):", t)
        if m:
            mini_at[m.group(1)] = m.group(2)

    def mini_for(line_idx: int) -> str | None:
        last = None
        for i, t in heads:
            if i > line_idx:
                break
            m = names_rx.match(t)
            if m:
                last = mini_at.get(m.group(1))
            elif re.match(r"^#{2,3} ", t):
                last = None
        return last

    for blk in blocks:
        if blk.kind != "table":
            continue
        rows = _table_rows(blk)
        if len(rows) < 2:
            continue
        head = [_plain(c).casefold() for c in rows[0]]
        body = rows[1:]
        if head[:3] == ["check", "default severity", "catches"]:
            for r in body:
                if len(r) >= 3:
                    out.checks[_plain(r[0])] = (_plain(r[1]), _plain(r[2]))
        elif head[:3] == ["minicosm", "lens", "draws"]:
            for r in body:
                if len(r) >= 3:
                    lens = _plain(r[1]).split(" ")[0]
                    for mini in re.split(r"\s*,\s*", _plain(r[0])):
                        out.lenses.setdefault((mini, lens), _plain(r[2]))
        elif head and head[0] == "minicosm" and "enumerates" in head:
            col = head.index("enumerates")
            for r in body:
                if len(r) > col:
                    out.minicosms[_plain(r[0])] = _plain(r[col])
        elif head and head[0] == "kind" and "what it is" in head:
            col = head.index("what it is")
            mini = mini_for(blk.first)
            if mini:
                for r in body:
                    if len(r) > col:
                        out.kinds[(mini, _plain(r[0]))] = _plain(r[col])
        elif len(head) >= 2:
            mini = mini_for(blk.first)
            if mini:
                key = head[0].strip()
                out.lists.setdefault((mini, key), {})
                for r in body:
                    if len(r) >= 2:
                        out.lists[(mini, key)][_plain(r[0])] = _plain(r[1])
    return out


def enumerate_manifests(registry: mc.Registry | None = None, *, tables: SpecTables | None = None,
                        root: Path | None = None) -> list[dict]:
    """The reference, generated: for every manifest in the registry `R:minicosm/<name>`, `R:module/<name>.<L>`,
    `R:kind/<name>.<L>.<kind>` (its reference fields, checked fields, required fields and closed lists),
    `R:list/<name>.<field>` for each closed list, `R:lens/<name>.<lens>`; and `R:check/<id>` for each generic
    check and each of DocOES's own, with the MiniCOSMs that select it. Each carries `provenance: {mode:
    catalogue, sources: [<manifest>#<field path>], hash}`; its atem is the spec's line for it when the spec's
    tables have one, else the manifest's subtitle or a sentence made from its place."""
    reg = registry or mc.default_registry()
    tables = tables or SpecTables()
    root = Path(root or INSTALL_ROOT)
    items: list[dict] = []
    check_sel: dict[str, list[str]] = {}

    def prov(m: mc.Manifest, fpath: str, value: Any) -> dict:
        return {"mode": "catalogue", "sources": [f"{_manifest_rel(m, root)}#{fpath}"], "confidence": 1,
                "state": "known", "hash": _subtree_hash(value)}

    for m in reg.manifests.values():
        name, title = m.name, m.title
        mods = m.modules()
        lens_ids = []
        declared = {spec["id"]: (i, spec) for i, spec in enumerate(m.data.get("renderers") or [])
                    if isinstance(spec, dict) and isinstance(spec.get("lens"), dict) and isinstance(spec.get("id"), str)}
        generic = []
        if "map" not in declared:
            generic.append("map")
        if "tree" not in declared and any(r in ("parts", "parent") for L in mods for k in m.kinds(L)
                                          for r in m.refs(L, k)):
            generic.append("tree")
        lens_ids = list(declared) + generic
        summ = m.data.get("summary") if isinstance(m.data.get("summary"), str) else title
        atem = tables.minicosms.get(name)
        atem = _atem_cut(atem) if atem else (_atem_of(summ) or _atem_cut(f"the {title} MiniCOSM"))
        head = {k: m.data.get(k) for k in ("name", "title", "version", "summary", "declaration", "volume")}
        items.append({"id": f"R:minicosm/{name}", "type": "minicosm", "name": title, "summary": summ,
                      "atem": atem, "declaration": mc._decl_value(m), "version": m.version,
                      "modules": [f"R:module/{name}.{L}" for L in mods],
                      "lenses": [f"R:lens/{name}.{x}" for x in lens_ids],
                      "provenance": prov(m, "declaration", head)})
        lists = m.closed_lists()
        for L in mods:
            mod = m.module(L)
            mname = str(mod.get("name") or L)
            sub = mod.get("subtitle") if isinstance(mod.get("subtitle"), str) else None
            items.append({"id": f"R:module/{name}.{L}", "type": "module", "name": mname,
                          "summary": f"{title}'s module {L}, {mname}" + (f": {sub}." if sub else "."),
                          "atem": _atem_cut(sub) if sub and _count(sub, "en") >= 2 else
                          _atem_cut(f"the {mname} module of {title}"),
                          "letter": L, "of": f"R:minicosm/{name}",
                          "kinds": [f"R:kind/{name}.{L}.{k}" for k in m.kinds(L)],
                          "provenance": prov(m, f"modules.{L}", mod)})
            for k, spec in m.kinds(L).items():
                refs = m.refs(L, k)
                checked = [str(x) for x in mc._list(spec.get("checked"))]
                req = m.required_fields(L, k)
                fields_seen = set(refs) | set(checked) | set(req) | set(mc._strs(m.envelope.get("fields")))
                klists = [f"R:list/{name}.{f}" for f in lists if f in fields_seen or f.split(".")[0] in fields_seen]
                what = tables.kinds.get((name, k))
                katem = _atem_cut(what) if what and _count(_atem_cut(what), "en") >= 2 else \
                    f"the {k} kind of {title}'s {mname} module"
                it = {"id": f"R:kind/{name}.{L}.{k}", "type": "kind", "name": k,
                      "summary": f"An item of the kind {k} in {title}'s module {L}, {mname}.",
                      "atem": katem, "of": f"R:module/{name}.{L}", "refs": refs, "fields": checked,
                      "required": req}
                if klists:
                    it["lists"] = klists
                declared_keys = {x: mc.jsonable(spec[x]) for x in spec if x not in ("refs", "checked", "required")}
                if declared_keys:
                    it["declared"] = declared_keys   # the manifest's own keys for the kind (level, stored, status…)
                it["provenance"] = prov(m, f"modules.{L}.kinds.{k}", spec)
                items.append(it)
        for fpath, values in lists.items():
            meanings = {}
            short = fpath.split(".")[-1]
            for key in (fpath, short, f"`{short}`", f"{short}s"):
                tbl = tables.lists.get((name, key.strip("`").casefold()))
                if tbl and all(str(v) in tbl for v in values if str(v) in tbl) and \
                        any(str(v) in tbl for v in values):
                    meanings = {str(v): tbl[str(v)] for v in values if str(v) in tbl}
                    break
            it = {"id": f"R:list/{name}.{fpath}", "type": "list", "name": fpath,
                  "summary": f"The values {title} allows for {fpath}: {', '.join(map(str, values))}.",
                  "atem": _atem_cut(f"the {len(values)} values {title} allows for {fpath}"),
                  "of": f"R:minicosm/{name}", "field": fpath, "values": [str(v) for v in values]}
            if meanings:
                it["meanings"] = meanings
            it["provenance"] = prov(m, _list_source(fpath), values)
            items.append(it)
        for lens in lens_ids:
            if lens in declared:
                i, spec = declared[lens]
                lspec = spec["lens"]
                inc = [str(x) for x in mc._list(lspec.get("include"))] or mods
                draws = tables.lenses.get((name, lens)) or spec.get("makes")
                summary = f"{title}'s lens {lens}: " + (str(spec.get("makes")) if spec.get("makes") else
                                                        f"a {lspec.get('kind', 'mermaid')} {lspec.get('diagram', '')}".strip()) + "."
                src = prov(m, f"renderers[{i}]", spec)
            else:
                lspec = {"kind": "mermaid", "diagram": "flowchart", "generic": True}
                if lens == "tree":
                    lspec["edges"] = ["parts", "parent"]
                inc = mods
                draws = tables.lenses.get((name, lens))
                summary = f"{title}'s generic lens {lens}, drawn by the reader from the manifest alone."
                src = {"mode": "catalogue", "sources": ["enough/macrocosm.py#lenses"], "confidence": 1,
                       "state": "known", "hash": _subtree_hash({"lens": lens, "modules": mods})}
            items.append({"id": f"R:lens/{name}.{lens}", "type": "lens", "name": lens, "summary": summary,
                          "atem": _atem_cut(str(draws)) if draws else _atem_cut(f"the {lens} lens of {title}"),
                          "of": f"R:minicosm/{name}", "draws": [f"R:module/{name}.{L}" for L in inc if L in mods],
                          "lens": mc.jsonable(lspec), "provenance": src})
        for c in m.checks():
            check_sel.setdefault(c, []).append(name)
    vocab = list(mc.CHECKS) + list(DOC_CHECKS)
    for c in vocab:
        sev, catches = tables.checks.get(c, (None, None))
        severity = (DOC_SEVERITY.get(c) if c in DOC_CHECKS else mc.SEVERITY.get(c)) or (sev or "error")
        sel = check_sel.get(c, [])
        owner = "DocOES's own check" if c in DOC_CHECKS else "a generic check"
        it = {"id": f"R:check/{c}", "type": "check", "name": c,
              "summary": f"The {c} check, {owner}: " + (catches + "." if catches else "see the spec."),
              "atem": _atem_cut(catches) if catches else _atem_cut(f"the {c} check, {owner}"),
              "severity": severity, "selected_by": [f"R:minicosm/{x}" for x in sel],
              "provenance": {"mode": "catalogue",
                             "sources": [f"{_manifest_rel(reg.get(x), root)}#checks" for x in sel]
                             or ["enough/macrocosm.py#CHECKS"],
                             "confidence": 1, "state": "known", "hash": _subtree_hash({"check": c, "by": sel})}}
        items.append(it)
    return items


# ---------------------------------------------------------------------------
# Atems: one line each, told apart among items of the same name
# ---------------------------------------------------------------------------

def _disambiguate(items: list[dict], lang: str, doc_name: str = "") -> None:
    """Two items of the same name never share an atem: the ones that would say where they are, by the first
    context that tells them all apart — the MiniCOSM (for the reference), the document or chapter, the section."""
    names = {it["id"]: _plain(str(it.get("name", ""))) for it in items}
    titles = {it["id"]: it.get("name") for it in items if it.get("type") == "minicosm"}

    def mini(it):
        of = it.get("of") if isinstance(it.get("of"), str) else ""
        if of in titles:
            return titles[of]
        if of.startswith("R:module/"):
            return titles.get("R:minicosm/" + of.split("/", 1)[1].split(".", 1)[0])
        return None

    def where(it):
        return names.get(it.get("chapter")) if it.get("chapter") else (doc_name or None)

    def place(it):
        p = it.get("parent") or it.get("defined_in") or it.get("in")
        return names.get(p) if isinstance(p, str) else None

    by_name: dict[str, list[dict]] = {}
    for it in items:
        by_name.setdefault(str(it.get("name", "")).casefold(), []).append(it)
    lo, hi = (ATEM_CJK_CHARS if lang in CJK else ATEM_WORDS)
    for group in by_name.values():
        if len(group) < 2:
            continue
        atems: dict[str, list[dict]] = {}
        for it in group:
            atems.setdefault(it.get("atem", ""), []).append(it)
        for atem, same in atems.items():
            if len(same) < 2:
                continue
            for ctx_of in (mini, where, place):
                ctxs = [ctx_of(it) for it in same]
                if all(ctxs) and len(set(ctxs)) == len(ctxs):
                    for it, ctx in zip(same[1:], ctxs[1:]):     # the first keeps its line; the others say where
                        extra = f", in {_plain(str(ctx))}"
                        it["atem"] = _atem_cut(_shorten(atem, hi - _count(extra, lang), lang) + extra, lang)
                    break
            else:
                for k, it in enumerate(same[1:], start=2):
                    it["atem"] = _atem_cut(f"{atem} ({k})", lang)


# ---------------------------------------------------------------------------
# Building a doc volume
# ---------------------------------------------------------------------------

class _Dumper(yaml.SafeDumper):
    """safe_dump's dumper with no anchors, and markdown bodies as literal blocks where YAML can hold them so."""

    def ignore_aliases(self, data):
        return True


def _str_rep(dumper: yaml.SafeDumper, s: str):
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None)


_Dumper.add_representer(str, _str_rep)


def dump(catalog: dict) -> str:
    """A doc catalog as COSM text: the declaration first, no anchors, bodies as `|` blocks where they can be."""
    mc._refuse_shared(catalog)
    first = "oes"
    if next(iter(catalog)) != first and first in catalog:
        catalog = {first: catalog[first], **{k: v for k, v in catalog.items() if k != first}}
    return yaml.dump(catalog, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110,
                     default_flow_style=False)


def _registry(sources: Path) -> mc.Registry:
    if Path(sources).resolve() == INSTALL_ROOT.resolve():
        return mc.default_registry()
    return mc.Registry([Path(sources) / MANIFESTS_DIR])


def _source_files(d: Document, lang: str) -> list[str]:
    out = [d.sources[lang]]
    if lang != "en" and "en" in d.sources:
        out.append(d.sources["en"])                     # a translation takes its ids from the author's telling
    if d.bubbles.get(lang):
        out.append(d.bubbles[lang])
    for c in d.chapters:
        out.append(f"{CHAPTERS_DIR}/{c.file}")
    if d.chapters:
        out.append(f"{CHAPTERS_DIR}/manifest.json")
    return out


def digest(doc: str, lang: str = "en", *, sources: Path | None = None,
           registry: mc.Registry | None = None) -> str:
    """What a doc volume is built from, as one sha256: DocOES's rules (FORMAT), enough's version, each source
    file's sha256 and every manifest's sha256."""
    d = _document(doc)
    root = Path(sources or sources_root())
    reg = registry or _registry(root)
    parts = [f"docoes {FORMAT}", f"enough {ENOUGH_VERSION}", f"doc {d.slug} {lang}"]
    for rel in _source_files(d, lang):
        parts.append(f"{rel} {_file_sha(root / rel) or 'missing'}")
    for m in reg.manifests.values():
        parts.append(f"manifest {m.name} {m.version} {_file_sha(m.path) if m.path else 'none'}")
    return _sha("\n".join(parts).encode("utf-8"))


def _read(root: Path, rel: str) -> str:
    """A source as written: utf-8, no newline translation, so a body is exactly its bytes."""
    return (root / rel).read_bytes().decode("utf-8")


def catalog_for(doc: str, lang: str = "en", *, sources: Path | None = None,
                registry: mc.Registry | None = None) -> dict:
    """The whole doc catalog for one telling, in memory: the document, its chapters, the reference, the bubbles."""
    d = _document(doc)
    if lang not in d.sources:
        raise KeyError(f"{d.slug} has no {lang} telling; it has {', '.join(tellings(d.slug))}")
    root = Path(sources or sources_root())
    reg = registry or _registry(root)
    text = _read(root, d.sources[lang])
    ref_text = _read(root, d.sources["en"]) if lang != "en" else None
    cat = enumerate_markdown(text, doc_id=d.slug, lang=lang, voice=d.voice, source_path=d.sources[lang],
                             reference_text=ref_text, name=d.name, version=d.version, xref=d.xref,
                             plain_mentions=d.plain_mentions, registry=reg)
    nodes = cat["nodes"]
    cat["tellings"] = tellings(d.slug)
    order = max((it.get("order", 0) for it in nodes), default=0)
    chapters_meta = {}
    if d.chapters:
        try:
            chapters_meta = json.loads(_read(root, f"{CHAPTERS_DIR}/manifest.json"))
        except (OSError, ValueError):
            chapters_meta = {}
        cat["chapters"] = []
        for c in d.chapters:
            rel = f"{CHAPTERS_DIR}/{c.file}"
            try:
                ctext = _read(root, rel)
            except OSError:
                continue
            entry = (chapters_meta.get("chapters") or {}).get(c.file) or {}
            meta = {"commit": chapters_meta.get("source_commit"), "sha256": entry.get("sha256")}
            sub = enumerate_markdown(ctext, doc_id=d.slug, lang="en", source_path=rel, chapter=c,
                                     plain_mentions="all", registry=reg, chapter_meta=meta)
            for it in sub["nodes"]:
                if "order" in it:
                    it["order"] += order
            order = max((it.get("order", 0) for it in sub["nodes"]), default=order)
            nodes += sub["nodes"]
            cat["chapters"].append({"id": f"S:chapter/{c.slug}", "path": rel, "source": c.source,
                                    "commit": meta["commit"], "sha256": _sha(ctext.encode("utf-8")),
                                    "prefix": c.prefix, "version": c.version})
            # Chapter terms that share a name with a term of the document are the same word.
            mine = {it["name"].casefold(): it["id"] for it in nodes if it.get("type") == "term" and
                    "chapter" not in it}
            for it in sub["nodes"]:
                if it.get("type") == "term" and it["name"].casefold() in mine:
                    it["same_as"] = [mine[it["name"].casefold()]]
    if d.reference:
        tables = spec_tables(text)
        rs = enumerate_manifests(reg, tables=tables, root=root)
        nodes += rs
        minis = {it["id"] for it in rs if it["type"] == "minicosm"}
        for it in nodes:
            if it.get("type") == "example" and it.get("declaration"):
                target = f"R:minicosm/{it['declaration'].split('/', 1)[0]}"
                if target in minis:
                    it["declares"] = target
                    order_keys = list(it)
                    # keep `declares` beside `in`
                    it_copy = {}
                    for k in order_keys:
                        if k == "declares":
                            continue
                        it_copy[k] = it[k]
                        if k == "in":
                            it_copy["declares"] = target
                    it.clear()
                    it.update(it_copy)
    if d.bubbles.get(lang):
        bpath = d.bubbles[lang]
        try:
            nodes += enumerate_bubbles(_read(root, bpath), lang, source_path=bpath)
        except OSError:
            pass
    _disambiguate(nodes, lang, cat.get("name", ""))
    return cat


def build(doc: str, lang: str = "en", *, docs_root: Path | None = None, sources: Path | None = None) -> Path:
    """Build one telling's doc volume, unconditionally, and write it atomically to
    `<docs_root>/<doc>.<lang>.doc.cosm`. Returns the path."""
    d = _document(doc)
    root = Path(sources or sources_root())
    reg = _registry(root)
    cat = catalog_for(d.slug, lang, sources=root, registry=reg)
    nodes = cat.pop("nodes")
    cat["built"] = {"at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "by": f"enough/{ENOUGH_VERSION}", "digest": digest(d.slug, lang, sources=root, registry=reg),
                    "manifests": [{"name": m.name, "version": m.version, "sha256": _file_sha(m.path) if m.path else None}
                                  for m in reg.manifests.values()]}
    cat["nodes"] = nodes
    out_dir = Path(docs_root or docs_root_default())
    out_dir.mkdir(parents=True, exist_ok=True)
    target = volume_path(d.slug, lang, out_dir)
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(dump(cat))
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def docs_root_default() -> Path:
    return docs_root()


_DIGEST_LINE = re.compile(r"^\s+digest:\s*['\"]?([0-9a-f]{64})")


def recorded_digest(path: Path) -> str | None:
    """The digest a built volume records under `built:`, read from its head without parsing the file."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            in_built = False
            for _ in range(400):
                line = fh.readline()
                if not line or line.startswith("nodes:"):
                    break
                if line.startswith("built:"):
                    in_built = True
                    continue
                if in_built:
                    if not line.startswith(" "):
                        in_built = False
                        continue
                    m = _DIGEST_LINE.match(line)
                    if m:
                        return m.group(1)
    except OSError:
        return None
    return None


# One lock per volume file: two threads asking for the same telling at once (the server's route and a readvisor's
# `doc_lookup`) build it once, the second finding it fresh.
_BUILD_LOCKS: dict[str, threading.Lock] = {}
_BUILD_LOCKS_GUARD = threading.Lock()


def _build_lock(path: Path) -> threading.Lock:
    with _BUILD_LOCKS_GUARD:
        return _BUILD_LOCKS.setdefault(str(path), threading.Lock())


def ensure_built(doc: str | None = None, lang: str | None = None, *, docs_root: Path | None = None,
                 sources: Path | None = None, on_step: Any = None) -> dict:
    """Build each doc volume whose recorded digest is not the current one (all documents and tellings when
    `doc`/`lang` are not given). Idempotent; a source that cannot be read is reported, never raised. `on_step`,
    when given, is called as `on_step(done, total, "<doc>.<lang>")` before each telling is looked at."""
    root = Path(sources or sources_root())
    out_dir = Path(docs_root or docs_root_default())
    reg = _registry(root)
    out = {"root": str(out_dir), "built": [], "fresh": [], "errors": []}
    docs = [_document(doc).slug] if doc else list(DOCUMENTS)
    todo = [(slug, lg) for slug in docs for lg in ([lang] if lang else tellings(slug))]
    for i, (slug, lg) in enumerate(todo):
        if on_step is not None:
            on_step(i, len(todo), f"{slug}.{lg}")
        path = volume_path(slug, lg, out_dir)
        try:
            with _build_lock(path):
                want = digest(slug, lg, sources=root, registry=reg)
                if recorded_digest(path) == want:
                    out["fresh"].append(f"{slug}.{lg}")
                    continue
                build(slug, lg, docs_root=out_dir, sources=root)
                out["built"].append(f"{slug}.{lg}")
        except (OSError, KeyError, UnicodeDecodeError) as e:
            out["errors"].append(f"{slug}.{lg}: {type(e).__name__}: {e}")
    return out


def is_fresh(doc: str, lang: str = "en", *, docs_root: Path | None = None, sources: Path | None = None) -> bool:
    """Whether a telling's built volume records the current digest (hashes the sources; parses nothing)."""
    root = Path(sources or sources_root())
    path = volume_path(_document(doc).slug, lang, Path(docs_root or docs_root_default()))
    have = recorded_digest(path)
    return have is not None and have == digest(doc, lang, sources=root)


class DocsUnavailable(Exception):
    """A telling that has no built volume and cannot be built (its source is missing or unreadable)."""


# Loaded volumes by file, kept while the file's (mtime_ns, size) stays the same. A Volume is read-only to every caller.
_LOADED: dict[str, tuple[tuple[int, int], mc.Volume]] = {}
_LOADED_GUARD = threading.Lock()
_LOADED_MAX = 16


def load_built(doc: str, lang: str = "en", *, docs_root: Path | None = None, sources: Path | None = None,
               ensure: bool = True) -> mc.Volume:
    """A telling's volume: built first when stale (unless `ensure=False`), then read through the reference reader,
    cached by the file's mtime and size so a second call costs one `stat`. Raises `DocsUnavailable` when there is no
    volume to read; a stale volume whose source has gone missing is still served."""
    d = _document(doc)
    root = Path(sources or sources_root())
    out_dir = Path(docs_root or docs_root_default())
    errors: list[str] = []
    if ensure:
        errors = ensure_built(d.slug, lang, docs_root=out_dir, sources=root)["errors"]
    path = volume_path(d.slug, lang, out_dir)
    try:
        st = path.stat()
    except OSError:
        raise DocsUnavailable("; ".join(errors) or f"{d.slug}.{lang} is not built yet ({path})") from None
    stamp = (st.st_mtime_ns, st.st_size)
    with _LOADED_GUARD:
        hit = _LOADED.get(str(path))
    if hit is not None and hit[0] == stamp:
        return hit[1]
    vol = mc.load_volume(path, _registry(root))
    with _LOADED_GUARD:
        _LOADED.pop(str(path), None)
        _LOADED[str(path)] = (stamp, vol)
        while len(_LOADED) > _LOADED_MAX:                 # seven tellings in a real install; tests make many roots
            _LOADED.pop(next(iter(_LOADED)))
    return vol


def status(*, docs_root: Path | None = None, sources: Path | None = None) -> dict:
    """Every document's tellings: where the volume is, whether it exists, whether it is fresh."""
    root = Path(sources or sources_root())
    out_dir = Path(docs_root or docs_root_default())
    reg = _registry(root)
    rows = []
    for slug in DOCUMENTS:
        for lg in tellings(slug):
            path = volume_path(slug, lg, out_dir)
            have = recorded_digest(path)
            rows.append({"doc": slug, "lang": lg, "path": str(path), "exists": path.is_file(),
                         "fresh": have is not None and have == digest(slug, lg, sources=root, registry=reg)})
    return {"root": str(out_dir), "documents": rows, "ready": all(r["fresh"] for r in rows)}


def load(doc: str, lang: str = "en", *, docs_root: Path | None = None, sources: Path | None = None) -> mc.Volume:
    """A telling's volume, built first when stale, read through the reference reader."""
    root = Path(sources or sources_root())
    ensure_built(doc, lang, docs_root=docs_root, sources=root)
    return mc.load_volume(volume_path(_document(doc).slug, lang, Path(docs_root or docs_root_default())),
                          _registry(root))


# ---------------------------------------------------------------------------
# Compiling: the round trip
# ---------------------------------------------------------------------------

def _nodes(volume: mc.Volume | dict) -> list[dict]:
    if isinstance(volume, mc.Volume):
        return [it.data for it in volume.items.values()]
    if isinstance(volume, dict):
        return [n for n in volume.get("nodes") or [] if isinstance(n, dict)]
    raise TypeError("compile_doc takes a loaded Volume or a doc catalog mapping")


def compile_doc(volume: mc.Volume | dict, *, order: str = "told", chapter: str | None = None) -> str:
    """The document again: its sections in `order` (told: as the author told it), each its heading line and its
    body, verbatim. For the main document this is the markdown it was enumerated from, byte for byte; with
    `chapter` (a slug or an `S:chapter/…` id), that chapter's."""
    if order != "told":
        raise ValueError(f"a doc volume compiles as told; {order!r} is an EMF twin's order")
    cid = None if chapter is None else (chapter if chapter.startswith("S:chapter/") else f"S:chapter/{chapter}")
    secs = [d for d in _nodes(volume) if d.get("type") == "section" and d.get("chapter") == cid]
    secs.sort(key=lambda d: (d.get("order") if isinstance(d.get("order"), int) else 0))
    out = []
    for d in secs:
        if isinstance(d.get("heading"), str):
            out.append(d["heading"])
            out.append(d["eol"] if isinstance(d.get("eol"), str) else "\n")
        out.append(d.get("body") or "")
    return "".join(out)


# ---------------------------------------------------------------------------
# The inventory and cross-volume references
# ---------------------------------------------------------------------------

_XREF = re.compile(r"^(?P<inv>[a-z][a-z0-9-]*)@(?P<ver>[^:\s]+):(?P<kind>[a-z][a-z0-9-]*):(?P<id>\S+)$")


def _catalog(volume: mc.Volume | dict) -> dict:
    return volume.catalog if isinstance(volume, mc.Volume) else volume


def inventory(volume: mc.Volume | dict) -> list[dict]:
    """One row per item and inventory: `{inventory, xref, id, kind, version, anchor, atem}`. The document's own
    items are in the document's inventory (`macrocosm-oes@0.0.1:section:18.5`); a chapter's items, and the R:
    items of the MiniCOSM it describes, are in the chapter's (`comprise@1:section:2.5`)."""
    cat = _catalog(volume)
    doc = str(cat.get("id") or "doc/unknown").removeprefix("doc/")
    dver = str((cat.get("document") or {}).get("version") or "")
    chapters = {c.get("id"): c for c in cat.get("chapters") or [] if isinstance(c, dict)}
    by_prefix = {str(c.get("prefix")): c for c in chapters.values()}
    rows = []
    for it in _nodes(volume):
        iid, kind = str(it.get("id", "")), str(it.get("type", ""))
        slug = iid.split("/", 1)[1] if "/" in iid else iid
        homes = []
        ch = chapters.get(it.get("chapter")) if it.get("chapter") else None
        if ch is not None:
            p = str(ch.get("prefix"))
            homes.append((p, str(ch.get("version") or "1"), slug[len(p) + 1:] if slug.startswith(p + ".") else slug))
        else:
            homes.append((doc, dver, slug))
            if iid.startswith("R:"):
                mini = slug.split(".", 1)[0]
                if mini in by_prefix:
                    homes.append((mini, str(by_prefix[mini].get("version") or "1"),
                                  slug[len(mini) + 1:] if slug.startswith(mini + ".") else slug))
        anchor = it.get("anchor") if isinstance(it.get("anchor"), str) else f"{kind}-{re.sub(r'[^A-Za-z0-9]+', '-', slug)}"
        for inv, ver, short in homes:
            rows.append({"inventory": inv, "xref": f"{inv}@{ver}:{kind}:{short}", "id": iid, "kind": kind,
                         "version": ver, "anchor": anchor, "atem": it.get("atem")})
    return rows


def resolve_xref(ref: str, rows: Iterable[dict]) -> dict | None:
    """The inventory row a cross-volume reference `<inventory>@<version>:<kind>:<id>` names, or None."""
    m = _XREF.match(ref or "")
    if not m:
        return None
    for r in rows:
        if r["inventory"] == m["inv"] and r["version"] == m["ver"] and r["kind"] == m["kind"] and \
                r["xref"].split(":", 2)[2] == m["id"]:
            return r
    return None


# ---------------------------------------------------------------------------
# DocOES's own checks
# ---------------------------------------------------------------------------

def lint_doc(volume: mc.Volume, *, registry: mc.Registry | None = None, sources: Path | None = None,
             inventories: Iterable[dict] | None = None) -> mc.Report:
    """The generic checks (`macrocosm.lint`) and DocOES's own, in one report: the atem lint, contiguous
    numbering, a term defined once, unlinked mentions, empty sections, stale provenance hashes and unresolved
    cross-volume references. `inventories` holds other volumes' inventory rows, for references into them."""
    rep = mc.lint(volume)
    if volume.manifest is None or volume.minicosm != "doc":
        return rep
    m = volume.manifest
    selected = [c for c in m.checks() if c in DOC_CHECKS]
    rep.not_run = [c for c in rep.not_run if c not in DOC_CHECKS]
    rep.checks = rep.checks + [c for c in selected if c not in rep.checks]
    override = m._block("checks").get("severity")
    sev = dict(DOC_SEVERITY, **({str(k): str(v) for k, v in override.items()} if isinstance(override, dict) else {}))
    lang = str((volume.catalog.get("telling") or {}).get("lang") or "en")
    root = Path(sources or sources_root())

    def add(check: str, item: mc.Item | None, msg: str, fld: str | None = None, file: str | None = None):
        if check in selected:
            rep.add(mc.Problem(check, sev.get(check, "error"), item.key if item else "",
                               file if file is not None else (item.file if item else volume.catalog_file), msg, fld))

    items = list(volume.items.values())
    # atem-shape
    by_name: dict[str, list[mc.Item]] = {}
    for it in items:
        told = "en" if it.data.get("fallback") == "en" else lang        # told from the author's telling
        for why in atem_problems(it.data.get("atem"), told):
            add("atem-shape", it, why, "atem")
        by_name.setdefault(str(it.data.get("name", "")).casefold(), []).append(it)
    for group in by_name.values():
        seen: dict[str, mc.Item] = {}
        for it in group:
            a = it.data.get("atem")
            if not isinstance(a, str):
                continue
            if a in seen:
                add("atem-shape", it, f"the same atem as {seen[a].id}, which has the same name: say how they "
                                      "differ", "atem")
            else:
                seen[a] = it
    # numbering
    secs = [it for it in items if it.data.get("type") == "section"]
    numbered: dict[tuple, mc.Item] = {}
    for it in secs:
        num = it.data.get("number")
        if not isinstance(num, str):
            continue
        key = (it.data.get("chapter"), num)
        if key in numbered:
            add("numbering", it, f"section {num} is numbered twice (first {numbered[key].id})", "number")
        else:
            numbered[key] = it
    by_parent: dict[Any, list[mc.Item]] = {}
    for it in secs:
        if isinstance(it.data.get("number"), str):
            by_parent.setdefault((it.data.get("chapter"), it.data.get("parent")), []).append(it)
    for (chap, parent), sibs in by_parent.items():
        sibs.sort(key=lambda x: x.data.get("order", 0))
        pnum = volume.items.get(parent).data.get("number") if parent in volume.items else None
        expect = 1
        for it in sibs:
            num = it.data["number"]
            head, _, last = num.rpartition(".")
            if isinstance(pnum, str) and head != pnum:
                add("numbering", it, f"section {num} sits under section {pnum}: its number should start {pnum}.",
                    "number")
            if last.isdigit():
                if int(last) != expect:
                    add("numbering", it, f"section {num} follows {expect - 1 if expect > 1 else 'nothing'}: "
                                         f"numbering skips or repeats", "number")
                expect = int(last) + 1
    # term-defined-once
    for it in items:
        if it.data.get("type") == "term" and it.data.get("also_defined_in"):
            add("term-defined-once", it, f"{it.data.get('name')!r} is defined again in "
                                         f"{', '.join(map(str, it.data['also_defined_in']))}; the first definition "
                                         f"({it.data.get('defined_in')}) is kept", "also_defined_in")
    # unlinked-mentions: a paragraph that opens with a bold phrase reading like a definition, not enumerated
    terms = {str(it.data.get("name", "")).casefold() for it in items if it.data.get("type") == "term"}
    for it in secs:
        body = it.data.get("body")
        if not isinstance(body, str):
            continue
        lines, _ = _scan(body)
        for blk in _blocks(lines, 0, len(lines) - 1) if lines else []:
            if blk.kind != "para":
                continue
            mm = re.match(r"^(?:(?:A|An|The) )?\*\*([^*]+?)\*\*(?=[\s,(])", blk.lines[0].text)
            if not mm:
                continue
            name = _term_name(mm.group(1))
            if mm.group(1).rstrip().endswith((".", ":", "：", "!", "?", "。")) or not name:
                continue
            if name.casefold() in terms or len(name.split()) > 4:
                continue
            add("unlinked-mentions", it, f"**{name}** opens a paragraph like a defined term, but no term is "
                                         f"enumerated for it (mark it <!-- term: {name} --> if it is one)", "body")
    # empty-section
    for it in secs:
        body = it.data.get("body") or ""
        rest = "\n".join(x for x in str(body).splitlines() if not _ATEM_MARK.match(x)).strip()
        if not rest and not it.data.get("parts"):
            add("empty-section", it, "a heading with no body and no sections under it", "body")
    # stale-provenance-hash
    reg = registry or (_registry(root))
    fresh = {r["id"]: r for r in enumerate_manifests(reg, root=root)} if any(
        k.startswith("R:") for k in volume.items) else {}
    for it in items:
        if not it.id.startswith("R:"):
            continue
        prov = it.data.get("provenance") if isinstance(it.data.get("provenance"), dict) else {}
        now = fresh.get(it.id)
        if now is None:
            add("stale-provenance-hash", it, "no manifest declares this any more: rebuild the volume", "provenance")
        elif prov.get("hash") != now["provenance"]["hash"]:
            add("stale-provenance-hash", it, f"{now['provenance']['sources'][0]} changed since this volume was "
                                             "built: rebuild it", "provenance.hash")
    for it in items:
        if it.data.get("type") != "chapter":
            continue
        path = it.data.get("path")
        have = _file_sha(root / path) if isinstance(path, str) else None
        want = (it.data.get("provenance") or {}).get("hash") if isinstance(it.data.get("provenance"), dict) else None
        if have and want and have != want:
            add("stale-provenance-hash", it, f"{path} differs from the copy the sync recorded: rerun "
                                             "scripts/sync_cosm.py", "provenance.hash")
    doc = volume.catalog.get("document") if isinstance(volume.catalog.get("document"), dict) else {}
    if isinstance(doc.get("path"), str) and doc.get("sha256"):
        have = _file_sha(root / doc["path"])
        if have and have != doc["sha256"]:
            add("stale-provenance-hash", None, f"{doc['path']} changed since this volume was built: rebuild it",
                "document.sha256")
    # xref-unresolved
    rows = inventory(volume) + list(inventories or [])
    known = {r["inventory"] for r in rows}
    for it in items:
        for x in it.data.get("xrefs") or []:
            mm = _XREF.match(str(x))
            if not mm:
                add("xref-unresolved", it, f"{x!r} is not <inventory>@<version>:<kind>:<id>", "xrefs")
            elif mm["inv"] not in known:
                rep.add(mc.Problem("xref-unresolved", "note", it.key, it.file,
                                   f"{x}: no inventory of {mm['inv']} was given, so this was not checked", "xrefs"))
            elif resolve_xref(str(x), rows) is None:
                add("xref-unresolved", it, f"{x} names nothing in {mm['inv']}'s inventory", "xrefs")
    return rep


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m enough.docoes",
                                 description="DocOES: enumerate a document into a doc volume, check it, compile it.")
    ap.add_argument("command", choices=["build", "lint", "compile", "inventory", "status"])
    ap.add_argument("doc", nargs="?", default=None, help=f"one of {', '.join(DOCUMENTS)}")
    ap.add_argument("--lang", default="en", help="the telling (default en)")
    ap.add_argument("--chapter", help="compile: a chapter's slug instead of the document")
    ap.add_argument("--force", action="store_true", help="build: even when the volume is fresh")
    ap.add_argument("--json", action="store_true", help="lint, inventory, status: JSON output")
    ap.add_argument("--docs-root", type=Path, help="where volumes are built (default ENOUGH_DOCS_ROOT or ~/enough/docoes)")
    ap.add_argument("--sources", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    root = args.sources or INSTALL_ROOT
    out_dir = args.docs_root or docs_root_default()
    if args.command == "status":
        st = status(docs_root=out_dir, sources=root)
        if args.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            for r in st["documents"]:
                print(f"{'fresh' if r['fresh'] else ('stale' if r['exists'] else 'absent'):7} {r['doc']}.{r['lang']}  {r['path']}")
        return 0
    if not args.doc:
        ap.error("a document is required")
    try:
        d = _document(args.doc)
    except KeyError as e:
        print(str(e).strip("'\""), file=sys.stderr)
        return 2
    if args.lang not in d.sources:
        print(f"{d.slug} has no {args.lang} telling; it has {', '.join(tellings(d.slug))}", file=sys.stderr)
        return 2
    if args.command == "build":
        if args.force:
            path = build(d.slug, args.lang, docs_root=out_dir, sources=root)
            print(f"built {path}")
        else:
            r = ensure_built(d.slug, args.lang, docs_root=out_dir, sources=root)
            for e in r["errors"]:
                print(e, file=sys.stderr)
            print(f"{'built' if r['built'] else 'fresh'} {volume_path(d.slug, args.lang, out_dir)}")
            if r["errors"]:
                return 1
        return 0
    vol = load(d.slug, args.lang, docs_root=out_dir, sources=root)
    if vol.refused is not None:
        print(f"refused: {vol.refused}", file=sys.stderr)
        return 1
    if args.command == "compile":
        sys.stdout.write(compile_doc(vol, chapter=args.chapter))
        return 0
    if args.command == "inventory":
        rows = inventory(vol)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                print(f"{r['xref']}\t{r['id']}\t{r['anchor']}\t{r['atem']}")
        return 0
    others: list[dict] = []
    for slug in DOCUMENTS:
        if slug != d.slug:
            try:
                others += inventory(load(slug, "en", docs_root=out_dir, sources=root))
            except (OSError, KeyError):
                pass
    rep = lint_doc(vol, sources=root, inventories=others)
    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        for p in rep.problems():
            print(f"{p.severity:7} {p}")
        print(f"{vol.oes}: {d.slug}.{args.lang}: {len(vol.items)} items, {len(rep.errors)} errors, "
              f"{len(rep.warnings)} warnings, {len(rep.notes)} notes")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
