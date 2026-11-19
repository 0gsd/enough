"""cosmoes.org's library: the registry's rules, the section splitters and the index builder. One file, standard library
only, used by the site (cosmoes/library.py renders pages from the same blocks), by scripts/fetch_library.py (which
writes SHA256SUMS and the change note with it), and by enough, which vendors it byte for byte as
enough/library_index.py.

The shelf (library/ in cosmoes-site):

    library/library.json                       the registry: shelves, and one entry per kept or pinned text
    library/<shelf>/<text>/<version>/NOTICE    the licence and the copyright notice, written at fetch time
    library/<shelf>/<text>/<version>/FETCHED   when, from where, the archive's sha256
    library/<shelf>/<text>/<version>/SHA256SUMS  every file under files/, `<sha256>  files/<path>`
    library/<shelf>/<text>/<version>/files/... the publisher's files as they came, never edited

The index is one SQLite file built from those files alone and never edited by hand:

    python client/library_index.py build --library library --out library.sqlite
    python client/library_index.py build --library library --out library.sqlite --check   # exit 1 when stale
    python client/library_index.py verify --library library                               # exit 1 on a problem

Tables: meta(key, value); texts(...); files(text_id, path, sha256, bytes); sections(id, text_id, file, page, path,
anchor, heading, kind, level, line_from, line_to, sha256, parent); anchors(text_id, file, anchor, section_id);
sections_fts (FTS5: heading, body; rowid = sections.id). A section's sha256 is over its bytes in the publisher's file
(lines line_from to line_to, 1-based, inclusive), so a citation that carries it still resolves after a path moves.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

FORMAT = 'cosmoes-library/1'
INDEX_FORMAT = 'cosmoes-library-index/1'
REGISTRY = 'library.json'
FILES = 'files'
META_FILES = ('NOTICE', 'FETCHED', 'SHA256SUMS')
GAP = '[OWNER:'                                    # a marked gap: a version folder that holds one is not served
LANES = ('open', 'bound', 'closed')                # MacroCOSM's R:licence lane
WHAT = ('text', 'standard', 'data', 'tests', 'implementation', 'draft')
KINDS = ('language', 'standard')                   # a shelf is a language or a standard: the same kind of thing
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
VERSION_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+-]*$')
RESERVED_IDS = frozenset({'main'})                 # ids the site's own page uses; a text's anchor never takes one

# How each form is kept, which of its files are pages, and the note of what was changed in form that every page and
# every NOTICE carries. One place for the wording: the fetch script writes it into NOTICE, the site shows it.
FORMS: dict[str, dict] = {
    'text': {'pages': ('.txt',), 'changed': (
        "Rendered as HTML from the publisher's plain-text build, by rule: titles from their underlines, paragraphs as "
        "paragraphs, indented blocks as preformatted text, anchors from the titles and from the definition lines. No "
        "word is changed, and the publisher's file is kept unchanged beside the page.")},
    'rst': {'pages': ('.rst', '.txt'), 'changed': (
        "Rendered as HTML from the publisher's reStructuredText source, by the plain-text rule: titles from their "
        "underlines, paragraphs as paragraphs, indented blocks as preformatted text, labels and paragraph ids as "
        "anchors; other markup is shown as written, not interpreted. The publisher's file is kept unchanged beside "
        "the page.")},
    'markdown': {'pages': ('.md',), 'changed': (
        "Rendered as HTML from the publisher's Markdown source, by rule: headings from their # marks, fenced blocks as "
        "preformatted text, rule markers as anchors, other lines as paragraphs shown as written. The publisher's file "
        "is kept unchanged beside the page.")},
    'html': {'pages': ('.html', '.htm', '.xhtml'), 'changed': (
        "Rendered as HTML from a text extraction of the publisher's HTML, by rule: headings, paragraphs, list items, "
        "table cells and preformatted blocks kept in order with their ids; scripts, styles, images, navigation and "
        "all other markup dropped. The publisher's file is kept unchanged beside the page.")},
    'data': {'pages': ('.txt',), 'changed': (
        "Each data file is shown whole as preformatted text. Nothing in it is changed.")},
    'unchanged': {'pages': (), 'changed': (
        "Not changed in any way: served only as the publisher's own file, never as a page.")},
}


# ----------------------------------------------------------------------------------------------- digests and folders

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_dir(root: Path, entry: dict) -> Path:
    return Path(root) / entry['shelf'] / entry['text'] / entry['version']


def address(entry: dict, base: str = 'https://cosmoes.org') -> str:
    return f"{base}/library/{entry['shelf']}/{entry['text']}/{entry['version']}/"


def walk_files(version_dir: Path) -> list[str]:
    """Every regular file under files/, as `files/<path>` with forward slashes, sorted."""
    base = Path(version_dir) / FILES
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for name in filenames:
            p = Path(dirpath) / name
            out.append(p.relative_to(version_dir).as_posix())
    return sorted(out)


def sums_text(version_dir: Path) -> str:
    """SHA256SUMS for a version folder: one `<sha256>  files/<path>` line per file under files/, sorted (the format
    `shasum -a 256 -c` reads)."""
    return ''.join(f'{sha256((Path(version_dir) / rel).read_bytes())}  {rel}\n' for rel in walk_files(version_dir))


def read_sums(version_dir: Path) -> dict[str, str]:
    sums = {}
    for line in (Path(version_dir) / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        if line.strip():
            digest, rel = line.split('  ', 1)
            sums[rel] = digest
    return sums


def folder_digest(version_dir: Path) -> str:
    """The text's digest in the registry: the sha256 of its SHA256SUMS file, which lists every file it keeps."""
    return 'sha256:' + sha256((Path(version_dir) / 'SHA256SUMS').read_bytes())


def verify(version_dir: Path, entry: dict | None = None) -> list[str]:
    """What is wrong with a version folder ([] when nothing): the three files ours, every file under files/ listed in
    SHA256SUMS with its digest and nothing else listed, no link, no marked gap in NOTICE, and (with the registry's
    entry) the entry's digest and file count."""
    d = Path(version_dir)
    problems = []
    if not d.is_dir():
        return [f'{d}: no such folder']
    for name in META_FILES:
        if not (d / name).is_file():
            problems.append(f'{name} is missing')
    if not (d / FILES).is_dir():
        problems.append('files/ is missing')
    if problems:
        return problems
    if GAP in (d / 'NOTICE').read_text(encoding='utf-8'):
        problems.append('NOTICE holds a marked gap for the owner')
    for dirpath, dirnames, filenames in os.walk(d / FILES):
        for name in dirnames + filenames:
            if (Path(dirpath) / name).is_symlink():
                problems.append(f'{(Path(dirpath) / name).relative_to(d).as_posix()} is a link')
    try:
        sums = read_sums(d)
    except ValueError:
        return problems + ['SHA256SUMS is not in the form `<sha256>  files/<path>`']
    present = walk_files(d)
    for rel in present:
        if rel not in sums:
            problems.append(f'{rel} is not in SHA256SUMS')
        elif sha256((d / rel).read_bytes()) != sums[rel]:
            problems.append(f'{rel} does not match its sha256')
    for rel in sorted(set(sums) - set(present)):
        problems.append(f'{rel} is in SHA256SUMS but not on disk')
    if entry is not None:
        if entry.get('digest') != folder_digest(d):
            problems.append("the registry's digest is not the sha256 of SHA256SUMS")
        if entry.get('files') != len(present):
            problems.append(f"the registry says {entry.get('files')} files, the folder holds {len(present)}")
    return problems


# ----------------------------------------------------------------------------------------------- the registry

def load_registry(root: Path) -> dict:
    return json.loads((Path(root) / REGISTRY).read_text(encoding='utf-8'))


def validate_registry(reg: dict) -> list[str]:
    """What is wrong with library.json ([] when nothing). Pinned entries (`aboard: false`) need only their names;
    a kept entry needs everything a page's notice shows."""
    problems = []
    if reg.get('format') != FORMAT:
        problems.append(f'format is not {FORMAT}')
    shelves = {}
    for s in reg.get('shelves', []):
        if not SLUG_RE.match(str(s.get('slug', ''))):
            problems.append(f"shelf {s.get('slug')!r}: not a slug")
        if s.get('slug') in shelves:
            problems.append(f"shelf {s.get('slug')}: twice")
        if s.get('kind') not in KINDS:
            problems.append(f"shelf {s.get('slug')}: kind is not one of {', '.join(KINDS)}")
        if not s.get('title'):
            problems.append(f"shelf {s.get('slug')}: no title")
        shelves[s.get('slug')] = s
    seen = set()
    for e in reg.get('texts', []):
        key = f"{e.get('shelf')}/{e.get('text')}/{e.get('version')}"
        if e.get('shelf') not in shelves:
            problems.append(f'{key}: no such shelf')
        if not SLUG_RE.match(str(e.get('text', ''))) or not VERSION_RE.match(str(e.get('version', ''))):
            problems.append(f'{key}: text or version is not a slug')
        if key in seen:
            problems.append(f'{key}: twice')
        seen.add(key)
        if not isinstance(e.get('aboard'), bool):
            problems.append(f'{key}: aboard is not true or false')
        if e.get('lane') not in LANES:
            problems.append(f"{key}: lane is not one of {', '.join(LANES)}")
        if e.get('what') not in WHAT:
            problems.append(f"{key}: what is not one of {', '.join(WHAT)}")
        for k in ('name', 'publisher'):
            if not e.get(k):
                problems.append(f'{key}: no {k}')
        if e.get('aboard'):
            if e.get('form') not in FORMS:
                problems.append(f"{key}: form is not one of {', '.join(FORMS)}")
            lic = e.get('licence') or {}
            if not lic.get('name') or not str(lic.get('url', '')).startswith('https://'):
                problems.append(f'{key}: the licence needs a name and an https url')
            if not e.get('copyright') or GAP in e.get('copyright', ''):
                problems.append(f'{key}: no copyright notice')
            for k in ('from', 'publisher_page'):
                if not str(e.get(k, '')).startswith('https://'):
                    problems.append(f'{key}: {k} is not an https url')
            if not str(e.get('digest', '')).startswith('sha256:') or not isinstance(e.get('files'), int):
                problems.append(f'{key}: no digest or file count')
            if not e.get('obtained'):
                problems.append(f'{key}: no obtained time')
    return problems


def page_files(version_dir: Path, entry: dict) -> dict[str, str]:
    """The pages a kept text has: page path (the file's path under files/ and under the entry's `pages` prefix,
    without its suffix) to the file (`files/<path>`). A form without pages has none; on a clash the first file in
    sorted order is the page and the other is served raw only."""
    form = FORMS.get(entry.get('form'), {})
    suffixes = form.get('pages', ())
    under = entry.get('pages', '') or ''
    out: dict[str, str] = {}
    if not suffixes:
        return out
    for rel in walk_files(version_dir):
        inner = rel[len(FILES) + 1:]
        if not inner.startswith(under):
            continue
        for suf in suffixes:
            if inner.endswith(suf):
                out.setdefault(inner[len(under):-len(suf)], rel)
                break
    return out


# ----------------------------------------------------------------------------------------------- blocks

@dataclass
class Block:
    """One piece of a page, in the file's order. kind: heading (text, level), sig (a definition: `lines`, the first
    carrying `anchor`, each with its own id in `ids`, and `children`, its body), rule (an anchor line), para, pre.
    line and end are 1-based lines of the publisher's file, end inclusive."""
    kind: str
    text: str = ''
    line: int = 0
    end: int = 0
    level: int = 0
    anchor: str = ''
    ids: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    children: list = field(default_factory=list)


UNDERLINE_RE = re.compile(r'^([=\-~^"#*+`\':.<>_])\1{2,}\s*$')
SIG_PREFIX = r'(?:(?:class|exception|classmethod|staticmethod|abstractmethod|async|await|coroutine|property|decorator)\s+)*@?'
SIG_RE = re.compile(r'^' + SIG_PREFIX + r'(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*(?P<rest>(?:\[[^\]]*\])?\(.*\)(?:\s*->.*)?|:\s.*|\s=\s.*)?$')
KEYWORD_RE = re.compile(r'^(?:class|exception|classmethod|staticmethod|abstractmethod|async|await|coroutine|property|decorator)\s|^@')
ITEM_RE = re.compile(r'^(?:[*+•-]|\d+\.|#\.|\(\d+\)|\[\d+\]|\[#\])\s+\S')    # a list item or a footnote
TABLE_RE = re.compile(r'^(?:\+[-=+]+\+\s*$|=+(?:\s+=+)+\s*$)')     # a grid or simple table's border: kept as laid out
DP_RE = re.compile(r'^:dp:`([A-Za-z0-9_]+)`')
LABEL_RE = re.compile(r'^\.\. _([^:]+):\s*$')


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip(' '))


def _sig_name(line: str) -> str | None:
    """The object id a definition line names (`str.splitlines(keepends=False)` gives `str.splitlines`), or None when
    the line is not one: it needs a call, a dot or a keyword before it, so a one-word paragraph is not taken."""
    m = SIG_RE.match(line)
    if not m:
        return None
    name, rest = m.group('name'), m.group('rest') or ''
    if '(' in rest or '.' in name or KEYWORD_RE.match(line):
        return name
    return None


def _decode_lines(data: bytes) -> list[str]:
    return [ln.decode('utf-8', 'replace').rstrip('\r') for ln in data.split(b'\n')]


def parse_text(data: bytes, rst: bool = False) -> list[Block]:
    """The plain-text rule (Python's text build; with rst=True, reStructuredText source as well): a title is a line
    with an underline at least as long, its level the order in which its underline's character first appears in the
    file; a definition is a group of lines at the margin that name an object, followed by an indented body (parsed
    again, its lines' objects named within it: `sort(...)` in `class list`'s body is `list.sort`); a paragraph is lines
    at the margin; an indented block is preformatted."""
    lines = _decode_lines(data)
    styles: list[str] = []
    return _parse_text_lines(lines, 0, len(lines), 0, '', styles, rst)


def _parse_text_lines(lines, start, stop, dedent, context, styles, rst) -> list[Block]:
    out: list[Block] = []
    pending: list[str] = []                                     # rst labels waiting for the next block
    i = start

    def body(k):                                                # the line with the indent taken off
        return lines[k][dedent:] if len(lines[k]) >= dedent else lines[k].lstrip(' ')

    def blank(k):
        return not lines[k].strip()

    while i < stop:
        if blank(i):
            i += 1
            continue
        cur = body(i)
        if _indent(cur) == 0:
            # an overlined title
            if (UNDERLINE_RE.match(cur) and i + 2 < stop and not blank(i + 1) and UNDERLINE_RE.match(body(i + 2))
                    and body(i + 2).strip()[0] == cur.strip()[0]):
                style = 'o' + cur.strip()[0]
                if style not in styles:
                    styles.append(style)
                out.append(Block('heading', body(i + 1).strip(), i + 1, i + 3, styles.index(style) + 1, ids=pending))
                pending = []
                i += 3
                continue
            # an underlined title
            if i + 1 < stop and UNDERLINE_RE.match(body(i + 1)) and not UNDERLINE_RE.match(cur) \
                    and len(body(i + 1).rstrip()) >= len(cur.rstrip()) * 0.5:
                style = body(i + 1).strip()[0]
                if style not in styles:
                    styles.append(style)
                out.append(Block('heading', cur.strip(), i + 1, i + 2, styles.index(style) + 1, ids=pending))
                pending = []
                i += 2
                continue
            if rst:
                m = LABEL_RE.match(cur)
                if m:
                    pending = pending + [m.group(1).strip()]
                    i += 1
                    continue
            # a definition: lines naming objects, then a blank line and an indented body
            j = i
            names = []
            while j < stop and not blank(j) and _indent(body(j)) == 0 and _sig_name(body(j)):
                names.append(_sig_name(body(j)))
                j += 1
            if names and j < stop and blank(j):
                k = j
                while k < stop and blank(k):
                    k += 1
                if k < stop and _indent(body(k)) > 0:
                    end = k
                    while end < stop and (blank(end) or _indent(body(end)) > 0):
                        end += 1
                    last = end - 1
                    while last > i and blank(last):
                        last -= 1
                    ids = [n if '.' in n or not context else f'{context}.{n}' for n in names]
                    inner = dedent + min(_indent(body(x)) for x in range(k, last + 1) if not blank(x))
                    blk = Block('sig', line=i + 1, end=last + 1, lines=[body(x) for x in range(i, j)], ids=ids,
                                anchor=ids[0])
                    blk.children = _parse_text_lines(lines, k, last + 1, inner, ids[0], styles, rst)
                    out.append(blk)
                    i = end
                    continue
            # a list item or footnote with its hanging indent
            if ITEM_RE.match(cur):
                j = i + 1
                while j < stop and not blank(j) and _indent(body(j)) > 0:
                    j += 1
                out.append(Block('para', '\n'.join([cur] + [body(x).strip() for x in range(i + 1, j)]), i + 1, j,
                                 ids=pending))
                pending = []
                i = j
                continue
            # a paragraph
            j = i
            while j < stop and not blank(j) and _indent(body(j)) == 0:
                if j > i and (ITEM_RE.match(body(j)) or (j + 1 < stop and UNDERLINE_RE.match(body(j + 1)))):
                    break
                j += 1
            text = '\n'.join(body(x) for x in range(i, j))
            blk = Block('pre' if TABLE_RE.match(body(i)) else 'para', text, i + 1, j, ids=pending)
            pending = []
            if rst:
                m = DP_RE.match(text)
                if m:
                    blk.ids = blk.ids + [m.group(1)]
            out.append(blk)
            i = j
            continue
        # an indented block
        j = i
        while j < stop and (blank(j) or _indent(body(j)) > 0):
            j += 1
        last = j - 1
        while blank(last):
            last -= 1
        chunk = [body(x) for x in range(i, last + 1)]
        cut = min(_indent(c) for c in chunk if c.strip())
        out.append(Block('pre', '\n'.join(c[cut:] for c in chunk), i + 1, last + 1))
        i = j
    return out


ATX_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
FENCE_RE = re.compile(r'^(```+|~~~+)')
RULE_RE = re.compile(r'^r\[([^\]\s]+)\]\s*$')


def parse_markdown(data: bytes) -> list[Block]:
    """The Markdown rule: ATX headings, fenced blocks preformatted, rule markers (`r[expr.call.intro]`, the Rust
    Reference's) as anchors `r-<id>` like the publisher's own pages, other runs of lines as paragraphs."""
    lines = _decode_lines(data)
    out: list[Block] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        f = FENCE_RE.match(ln)
        if f:
            j = i + 1
            while j < len(lines) and not lines[j].startswith(f.group(1)):
                j += 1
            out.append(Block('pre', '\n'.join(lines[i + 1:j]), i + 1, min(j + 1, len(lines))))
            i = j + 1
            continue
        h = ATX_RE.match(ln)
        if h:
            out.append(Block('heading', h.group(2), i + 1, i + 1, len(h.group(1))))
            i += 1
            continue
        r = RULE_RE.match(ln)
        if r:
            out.append(Block('rule', r.group(1), i + 1, i + 1, anchor='r-' + r.group(1)))
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].strip() and not ATX_RE.match(lines[j]) and not FENCE_RE.match(lines[j]) \
                and not RULE_RE.match(lines[j]):
            j += 1
        out.append(Block('para', '\n'.join(lines[i:j]), i + 1, j))
        i = j
    return out


class _HTMLText(HTMLParser):
    """The text extraction of a publisher's HTML: block elements in order with their text and the ids on them or on
    the containers just opened before them; the rest of the markup dropped."""
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'noscript', 'svg', 'template', 'head', 'title', 'button',
            'form', 'select', 'math', 'iframe', 'object'}
    BLOCK = {'p': 'para', 'li': 'para', 'dt': 'para', 'dd': 'para', 'td': 'para', 'th': 'para', 'caption': 'para',
             'figcaption': 'para', 'blockquote': 'para', 'pre': 'pre',
             'h1': 'heading', 'h2': 'heading', 'h3': 'heading', 'h4': 'heading', 'h5': 'heading', 'h6': 'heading'}
    CONTAINERS = {'ul', 'ol', 'dl', 'table', 'tbody', 'thead', 'tr', 'section', 'article', 'div', 'body', 'html',
                  'main', 'aside', 'emu-clause', 'emu-annex'}
    VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'wbr', 'col', 'area', 'base', 'source', 'track', 'embed'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.skip = 0                                        # inside a dropped element: how deep in its own tag
        self.skip_tag = ''
        self.cur: Block | None = None
        self.cur_tag = ''
        self.parts: list[str] = []
        self.pending: list[str] = []
        self.depth = 0                                       # the current block's tag opened again inside it

    def _close(self):
        text = ''.join(self.parts)
        if self.cur.kind == 'pre':
            text = text.strip('\n')
        else:
            text = re.sub(r'[ \t\r\n]+', ' ', text).strip()
        self.cur.text = text
        self.cur.end = self.getpos()[0]
        if text or self.cur.ids:
            self.blocks.append(self.cur)
        self.cur, self.depth = None, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            if tag == 'br' and self.cur is not None:
                self.parts.append('\n')
            return
        if self.skip:
            if tag == self.skip_tag:
                self.skip += 1
            return
        if tag in self.SKIP:
            self.skip, self.skip_tag = 1, tag
            return
        ident = dict(attrs).get('id')
        if self.cur is not None and tag in self.BLOCK:
            # a <p> holds no block, and a list item or definition left open ends at the next one
            if self.cur_tag == 'p' or (tag == self.cur_tag and tag in ('li', 'dt', 'dd') and not self.depth) \
                    or (self.cur_tag in ('dt', 'dd') and tag in ('dt', 'dd')) \
                    or (self.BLOCK[tag] == 'heading' and self.cur.kind != 'heading'):
                self._close()
            elif tag == self.cur_tag:
                self.depth += 1
        if tag in self.BLOCK and self.cur is None:
            kind = self.BLOCK[tag]
            self.cur = Block(kind, line=self.getpos()[0], level=int(tag[1]) if kind == 'heading' else 0,
                             ids=self.pending + ([ident] if ident else []))
            self.pending = []
            self.cur_tag = tag
            self.parts = []
        elif ident:
            if self.cur is not None:
                self.cur.ids.append(ident)
            else:
                self.pending.append(ident)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.skip:
            if tag == self.skip_tag:
                self.skip -= 1
            return
        if self.cur is not None and tag == self.cur_tag:
            if self.depth:
                self.depth -= 1
            else:
                self._close()
        elif self.cur is not None and tag in self.CONTAINERS:
            self._close()                                    # a list or section that ends ends what was left open in it

    def close(self):
        super().close()
        if self.cur is not None:
            self._close()

    def handle_data(self, data):
        if not self.skip and self.cur is not None:
            self.parts.append(data)


def parse_html(data: bytes) -> list[Block]:
    p = _HTMLText()
    p.feed(data.decode('utf-8', 'replace'))
    p.close()
    return p.blocks


def parse_data(data: bytes) -> list[Block]:
    n = data.count(b'\n') + (0 if data.endswith(b'\n') else 1)
    return [Block('pre', data.decode('utf-8', 'replace'), 1, max(n, 1))]


def blocks(form: str, data: bytes) -> list[Block]:
    """A file's blocks by its form's rule, anchors given (see `assign_anchors`)."""
    if form == 'text':
        out = parse_text(data)
    elif form == 'rst':
        out = parse_text(data, rst=True)
    elif form == 'markdown':
        out = parse_markdown(data)
    elif form == 'html':
        out = parse_html(data)
    else:
        out = parse_data(data)
    assign_anchors(out)
    return out


def slug(text: str) -> str:
    s = unicodedata.normalize('NFKC', text).lower()
    s = re.sub(r'[^\w]+', '-', s).strip('-_')
    return s or 'section'


def assign_anchors(blks: list[Block]) -> None:
    """Every block that names a place gets an anchor unique in its page: a definition its object id, an rst label or
    paragraph id itself, an HTML element its own id, a heading its own id or else the slug of its text (then of its
    path, then numbered). The publisher's own ids are taken first; an id a second time is dropped, never renamed."""
    taken = set(RESERVED_IDS)

    def ok(a):
        return a and a not in taken and not a.startswith('lib-')

    def own(bs):                                            # the publisher's ids first, in order
        for b in bs:
            if b.kind == 'rule' and ok(b.anchor):
                taken.add(b.anchor)
            elif b.kind == 'rule':
                b.anchor = ''
            keep = []
            for x in b.ids:
                if ok(x):
                    taken.add(x)
                    keep.append(x)
                elif b.kind == 'sig':
                    keep.append('')                         # a definition's ids stay one per line
            b.ids = keep
            if b.kind == 'sig':
                b.anchor = next((x for x in keep if x), '')
                own(b.children)
            elif b.ids:
                b.anchor = b.ids[0]
    own(blks)

    path: list[tuple[int, str]] = []

    def made(bs):
        for b in bs:
            if b.kind == 'heading':
                while path and path[-1][0] >= b.level:
                    path.pop()
                path.append((b.level, b.text))
                if not b.anchor:
                    for cand in (slug(b.text), '--'.join(slug(t) for _, t in path)):
                        if ok(cand):
                            b.anchor = cand
                            break
                    else:
                        n = 2
                        while not ok(f'{slug(b.text)}-{n}'):
                            n += 1
                        b.anchor = f'{slug(b.text)}-{n}'
                    taken.add(b.anchor)
            elif b.kind == 'sig':
                made(b.children)
    made(blks)


# ----------------------------------------------------------------------------------------------- sections

@dataclass
class Section:
    kind: str                 # file, heading, sig, rule, para (an rst paragraph id)
    heading: str
    path: list
    anchor: str
    level: int
    line_from: int
    line_to: int
    own_to: int               # the last line before the next section starts: the text the search reads
    parent: int | None        # index into the list
    ids: list = field(default_factory=list)


def sections(form: str, data: bytes, page: str) -> list[Section]:
    """A file's sections: the whole file first (kind `file`), then every heading (spanning to the next heading at its
    level or above), definition (its lines and body), rule marker (to the next marker or heading) and rst paragraph id,
    in the file's order, each with its heading path."""
    raw_lines = data.split(b'\n')
    n = len(raw_lines) - (1 if data.endswith(b'\n') else 0)
    n = max(n, 1)
    out = [Section('file', page, [], '', 0, 1, n, n, None)]
    flat: list[tuple[Block, int]] = []                       # (block, nesting depth of definitions)

    def walk(bs, depth):
        for b in bs:
            flat.append((b, depth))
            if b.kind == 'sig':
                walk(b.children, depth + 1)
    walk(blocks(form, data), 0)

    heads: list[tuple[int, int]] = []                        # (level, section index) of the open headings
    sigs: list[tuple[int, int]] = []                         # (end line, section index) of the open definitions
    starts = []
    for b, depth in flat:
        while sigs and sigs[-1][0] < b.line:
            sigs.pop()
        if b.kind == 'heading':
            while heads and out[heads[-1][1]].level >= b.level:
                heads.pop()
            parent = heads[-1][1] if heads else 0
            sec = Section('heading', b.text, out[parent].path + [b.text], b.anchor, b.level, b.line, n, n, parent,
                          list(b.ids))
            out.append(sec)
            heads.append((b.level, len(out) - 1))
            starts.append(len(out) - 1)
        elif b.kind == 'sig' or (b.kind in ('rule', 'para') and b.anchor):
            parent = sigs[-1][1] if sigs else (heads[-1][1] if heads else 0)
            name = (b.anchor or b.lines[0].strip()) if b.kind == 'sig' else b.anchor
            sec = Section(b.kind, name, out[parent].path + [name], b.anchor, out[parent].level + 1,
                          b.line, b.end if b.kind == 'sig' else n, n, parent, list(b.ids))
            out.append(sec)
            starts.append(len(out) - 1)
            if b.kind == 'sig':
                sigs.append((b.end, len(out) - 1))
    # spans: a heading to the next heading at its level or above; a rule or rst paragraph to the next section of any
    # kind but a definition inside it; every section's own text to the next section's start
    for pos, idx in enumerate(starts):
        sec = out[idx]
        later = [out[k] for k in starts[pos + 1:]]
        if sec.kind == 'heading':
            nxt = next((s for s in later if s.kind == 'heading' and s.level <= sec.level), None)
            sec.line_to = nxt.line_from - 1 if nxt else n
        elif sec.kind in ('rule', 'para'):
            nxt = next((s for s in later if s.kind in ('heading', 'rule', 'para')), None)
            sec.line_to = nxt.line_from - 1 if nxt else n
        nxt_any = later[0] if later else None
        sec.own_to = min(sec.line_to, nxt_any.line_from - 1) if nxt_any else sec.line_to
    for sec in out[1:]:
        while sec.line_to > sec.line_from and not raw_lines[sec.line_to - 1].strip():
            sec.line_to -= 1
        sec.own_to = max(min(sec.own_to, sec.line_to), sec.line_from)
    return out


def section_bytes(data: bytes | list, line_from: int, line_to: int) -> bytes:
    """Lines line_from to line_to (1-based, inclusive) of the file as they are, each with its line end. `data` is the
    file's bytes, or those bytes already split at b'\\n'."""
    raw = data.split(b'\n') if isinstance(data, bytes) else data
    chunk = b'\n'.join(raw[line_from - 1:line_to])
    return chunk + b'\n' if line_to < len(raw) else chunk


# ----------------------------------------------------------------------------------------------- the index

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE texts (id INTEGER PRIMARY KEY, shelf TEXT NOT NULL, text TEXT NOT NULL, version TEXT NOT NULL,
  name TEXT NOT NULL, publisher TEXT, what TEXT, form TEXT, lane TEXT, aboard INTEGER NOT NULL, licence TEXT,
  licence_url TEXT, digest TEXT, "from" TEXT, obtained TEXT, address TEXT, swhid TEXT,
  UNIQUE (shelf, text, version));
CREATE TABLE files (text_id INTEGER NOT NULL REFERENCES texts(id), path TEXT NOT NULL, page TEXT, sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL, PRIMARY KEY (text_id, path));
CREATE TABLE sections (id INTEGER PRIMARY KEY, text_id INTEGER NOT NULL REFERENCES texts(id), file TEXT NOT NULL,
  page TEXT, path TEXT NOT NULL, anchor TEXT, heading TEXT, kind TEXT NOT NULL, level INTEGER NOT NULL,
  line_from INTEGER NOT NULL, line_to INTEGER NOT NULL, sha256 TEXT NOT NULL, parent INTEGER REFERENCES sections(id));
CREATE INDEX sections_sha ON sections(sha256);
CREATE TABLE anchors (text_id INTEGER NOT NULL, file TEXT NOT NULL, anchor TEXT NOT NULL, section_id INTEGER NOT NULL,
  PRIMARY KEY (text_id, file, anchor));
CREATE VIRTUAL TABLE sections_fts USING fts5(heading, body, tokenize = 'unicode61');
"""


def source_digest(root: Path) -> str:
    """What the index was built from, as one digest: library.json's bytes and each kept text's SHA256SUMS."""
    root = Path(root)
    h = hashlib.sha256((root / REGISTRY).read_bytes())
    for e in sorted(load_registry(root).get('texts', []), key=lambda e: (e['shelf'], e['text'], e['version'])):
        if e.get('aboard'):
            sums = text_dir(root, e) / 'SHA256SUMS'
            h.update(f"\n{e['shelf']}/{e['text']}/{e['version']}\n".encode())
            h.update(sums.read_bytes() if sums.is_file() else b'')
    return 'sha256:' + h.hexdigest()


def is_current(root: Path, db: Path) -> bool:
    if not Path(db).is_file():
        return False
    try:
        con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key = 'source'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return bool(row) and row[0] == source_digest(root)


def build(root: Path, out: Path) -> dict:
    """Build the index of the shelf at `root` into `out`, from the files alone: refuses (ValueError, nothing written)
    a registry with a problem or a kept text whose folder does not verify. Returns counts."""
    root, out = Path(root), Path(out)
    reg = load_registry(root)
    problems = validate_registry(reg)
    for e in reg.get('texts', []):
        if e.get('aboard'):
            problems += [f"{e['shelf']}/{e['text']}/{e['version']}: {p}" for p in verify(text_dir(root, e), e)]
    if problems:
        raise ValueError('the library does not verify:\n  ' + '\n  '.join(problems))
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.library-index-', suffix='.sqlite', dir=out.parent)
    os.close(fd)
    counts = {'texts': 0, 'kept': 0, 'files': 0, 'sections': 0}
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        for e in sorted(reg.get('texts', []), key=lambda e: (e['shelf'], e['text'], e['version'])):
            lic = e.get('licence') or {}
            cur = con.execute(
                'INSERT INTO texts (shelf, text, version, name, publisher, what, form, lane, aboard, licence, '
                'licence_url, digest, "from", obtained, address, swhid) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (e['shelf'], e['text'], e['version'], e['name'], e.get('publisher'), e.get('what'), e.get('form'),
                 e.get('lane'), 1 if e.get('aboard') else 0, lic.get('name'), lic.get('url'), e.get('digest'),
                 e.get('from'), e.get('obtained'), address(e) if e.get('aboard') else None, e.get('swhid')))
            counts['texts'] += 1
            if not e.get('aboard'):
                continue
            counts['kept'] += 1
            tid = cur.lastrowid
            d = text_dir(root, e)
            pages = {rel: page for page, rel in page_files(d, e).items()}
            sums = read_sums(d)
            for rel in sorted(sums):
                data = (d / rel).read_bytes()
                page = pages.get(rel)
                con.execute('INSERT INTO files VALUES (?,?,?,?,?)', (tid, rel, page, sums[rel], len(data)))
                counts['files'] += 1
                # a page by its form's rule; a file of a form without pages (the RFC) whole; any other file (a
                # repository's tooling beside its text) is listed with its digest and not split
                if page is None and (e['form'] != 'unchanged' or not _is_text(data)):
                    continue
                form = e['form'] if page is not None else 'data'
                secs = sections(form, data, page if page is not None else rel[len(FILES) + 1:])
                raw = data.split(b'\n')
                ids: list[int] = []
                for s in secs:
                    body = section_bytes(raw, s.line_from, s.own_to).decode('utf-8', 'replace')
                    parent = ids[s.parent] if s.parent is not None else None
                    c = con.execute(
                        'INSERT INTO sections (text_id, file, page, path, anchor, heading, kind, level, line_from, '
                        'line_to, sha256, parent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (tid, rel, page, json.dumps(s.path, ensure_ascii=False), s.anchor or None, s.heading, s.kind,
                         s.level, s.line_from, s.line_to, sha256(section_bytes(raw, s.line_from, s.line_to)), parent))
                    sid = c.lastrowid
                    ids.append(sid)
                    for a in [s.anchor] + [x for x in s.ids if x != s.anchor]:
                        if a:
                            con.execute('INSERT OR IGNORE INTO anchors VALUES (?,?,?,?)', (tid, rel, a, sid))
                    if s.kind != 'file' or len(secs) == 1:
                        con.execute('INSERT INTO sections_fts (rowid, heading, body) VALUES (?,?,?)',
                                    (sid, s.heading, body))
                    counts['sections'] += 1
        con.executemany('INSERT INTO meta VALUES (?,?)', [('format', INDEX_FORMAT), ('library', FORMAT),
                                                          ('source', source_digest(root))])
        con.commit()
    except BaseException:
        con.close()
        os.unlink(tmp)
        raise
    con.close()
    os.replace(tmp, out)
    return counts


def _is_text(data: bytes) -> bool:
    if b'\0' in data[:8192]:
        return False
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


# ----------------------------------------------------------------------------------------------- the command line

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build or check the library's index, or verify the shelf.")
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='build the SQLite index from the files alone')
    b.add_argument('--library', default='library')
    b.add_argument('--out', required=True)
    b.add_argument('--check', action='store_true', help='build nothing; exit 1 when the index is not current')
    v = sub.add_parser('verify', help="check library.json and every kept text's folder")
    v.add_argument('--library', default='library')
    args = ap.parse_args(argv)
    if args.cmd == 'verify':
        reg = load_registry(Path(args.library))
        problems = validate_registry(reg)
        for e in reg.get('texts', []):
            if e.get('aboard'):
                problems += [f"{e['shelf']}/{e['text']}/{e['version']}: {p}"
                             for p in verify(text_dir(Path(args.library), e), e)]
        for p in problems:
            print(p, file=sys.stderr)
        print('ok' if not problems else f'{len(problems)} problems')
        return 1 if problems else 0
    if args.check:
        current = is_current(Path(args.library), Path(args.out))
        print('current' if current else 'stale')
        return 0 if current else 1
    try:
        counts = build(Path(args.library), Path(args.out))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{args.out}: {counts['texts']} texts ({counts['kept']} kept), {counts['files']} files, "
          f"{counts['sections']} sections")
    return 0


if __name__ == '__main__':
    sys.exit(main())
