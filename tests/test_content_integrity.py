"""Content drift guards — the pure-Python half of the pre-commit suite.

Everything here runs everywhere (no browser, no server, no network), which
is why it lives in `tests/` and therefore in CI: the browser harness
(`scripts/ui_check.py`) can be skipped on a machine without Chrome, but
*content* drift — a UI label whose catalog entry no longer matches, a help
bubble nobody can open, a manual section renumbered out from under its own
cross-references — is cheap to catch and expensive to ship.

`scripts/i18n_check.py` already compares key *sets*. This module compares
the things sets cannot see:

  * the en catalog's *values* against the inline English in index.html —
    docs/I18N.md has always claimed byte-identity there, and until now
    nothing enforced it;
  * placeholder/markup parity across the five translations;
  * the help-bubble id space (index.html ∪ server._HELP_IDS) against the
    `## <id>` sections of help-docs.md, both directions;
  * HELP_CENTER.md's numbering and its own "section N" cross-references;
  * the seven places that name the version;
  * every icon name the frontend asks for against the built SVG pair.

**KNOWN_FINDINGS.** Some of these checks fail against today's tree. Those
failures are real and are meant to be fixed in a later lane, not hidden, so
they are listed explicitly below by a *stable key* (never by a line number
or a byte offset). The list is load-bearing in three directions:

  a. the suite is green today, so the pre-commit hook is usable now;
  b. a NEW finding is not on the list, so it fails immediately;
  c. FIXING a listed finding without deleting its entry also fails —
     `test_known_findings_still_present` is the one that catches that, and
     its failure message tells you to delete the line.

Keep the list tiny. A finding that has been sitting here for a release is
a finding nobody is going to fix.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "enough" / "static"
I18N = STATIC / "i18n"
INDEX = STATIC / "index.html"
HELP_DOCS = STATIC / "help-docs.md"
HELP_CENTER = REPO / "docs" / "HELP_CENTER.md"
AGENT_GUIDE = REPO / "docs" / "AGENT_GUIDE.md"
ICONS_BUILD = STATIC / "icons" / "build"
ICONS_SRC = STATIC / "icons"
ICONS_BBOX = REPO / "scripts" / "icons-bbox.json"

LANGS = ("fr", "es", "de", "zh", "ja")  # en is the baked-in source


# ---------------------------------------------------------------------------
# KNOWN_FINDINGS — see the module docstring. key -> why it is tolerated.
# ---------------------------------------------------------------------------

KNOWN_FINDINGS: dict[str, str] = {
    # (empty) — the AGENT_GUIDE v0.2.8 title-line entry was removed when the
    # guide was bumped to 0.3.0 in the working tree: the check demands that a
    # finding which stops being true stops being listed, or the list quietly
    # becomes a place drift goes to hide.
}


# ---------------------------------------------------------------------------
# Untranslated-value allowlist
# ---------------------------------------------------------------------------
# A translated value byte-equal to its English is usually a missed string.
# Two allowlists cover the cases where identical IS the translation.
#
# The first is language-independent: the names docs/I18N.md's contract
# tells translators to leave alone (products, modes, subsystems) plus the
# symbols and glyphs the UI uses as labels. Matching is case-insensitive
# on the *whole* stripped value — these are complete strings, not
# substrings.
SAME_IN_EVERY_LANGUAGE = frozenset(s.casefold() for s in (
    # Product, mode and subsystem names — I18N.md: "product names … stay
    # as-is". `broker` is one of those: it names a component, not a job.
    "enough", "wikisink", "cacheawl", "cachebox", "girraph", "merirmaid",
    "composure", "readvisor", "readvisors", "rness", "broker", "infoworld",
    "OpenRouter", "MADLAD", "Wikipedia", "markdown", "PDF", "HTML",
    "URL", "AGENT.md", "MOTIVATION.md", "FEED",
    # Symbols, units and single glyphs used as labels.
    "OK", "×", "?", "+", "−", "-", "…", "¶", "W", "C", "⌘", "⇧",
    "a–z", "z–a",       # the dictionary's sort-direction toggle
))

# The second is per-language and much more interesting: a word that really
# is spelled the same in that language. Each entry is a claim about the
# language, so add one only when you can defend it — otherwise you are
# allowlisting a missed translation.
COGNATES: dict[str, frozenset[str]] = {
    "fr": frozenset((
        "attribution", "portrait", "description", "type", "format",
        " page", " pages", "page {n} / {total}", "image · {name}",
        "image",            # the French noun, spelled the same
        "module",           # likewise — "un module" is the French word
    )),
    "es": frozenset((
        "roles",            # plural of "rol"
        "chat",             # the RAE-accepted loan-word
        "wip · editable",   # "editable" is the Spanish word too
    )),
    "de": frozenset((
        "pink",             # German for pink
        "live",             # the German loan-word, already standard
        "text",             # "Text", lowercased the way this UI lowercases
    )),
    "zh": frozenset(),
    "ja": frozenset(),
}


# ---------------------------------------------------------------------------
# index.html: the i18n usage sites
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Usage:
    """One place index.html declares an English string with an i18n key."""
    key: str
    english: str
    kind: str   # "data-i18n" | "data-i18n-title" | … | "t()"
    line: int

    @property
    def where(self) -> str:
        return f"{self.kind}@{self.line}"


# HTML void elements. HTMLParser has no idea about them, so a
# `<input data-i18n-placeholder=…>` would otherwise sit on the capture
# stack forever.
_VOID = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
))

_ATTR_KINDS = {
    "data-i18n-title": "data-i18n-title",
    "data-i18n-placeholder": "data-i18n-placeholder",
    "data-i18n-aria": "data-i18n-aria",
}


class _I18nMarkupParser(HTMLParser):
    """Collect every `data-i18n*` declaration and its inline English.

    `applyI18n()` memoizes `el.textContent` verbatim into `data-i18n-src`
    — no trim, no collapse — so the catalog value has to be the raw text
    including whatever indentation the markup happens to carry. That is
    why nothing here strips anything.

    The engine's contract is that `data-i18n` goes on **text-only**
    elements ("an element with inline markup gets the attribute on its
    text-only children instead"). Rather than build a DOM to honour that,
    this parser captures until the matching end tag and records an
    `anomalies` entry if any markup shows up inside — which both enforces
    the contract and keeps the parser trivial.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.usages: list[Usage] = []
        self.anomalies: list[str] = []
        self._cap_tag: str | None = None
        self._cap_key: str | None = None
        self._cap_line: int = 0
        self._cap_buf: list[str] = []

    # -- capture bookkeeping -------------------------------------------
    def _finish(self) -> None:
        if self._cap_key is not None:
            self.usages.append(Usage(self._cap_key, "".join(self._cap_buf),
                                     "data-i18n", self._cap_line))
        self._cap_tag = self._cap_key = None
        self._cap_buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        line = self.getpos()[0]

        for attr, kind in _ATTR_KINDS.items():
            if attr in d:
                target = {"data-i18n-title": "title",
                          "data-i18n-placeholder": "placeholder",
                          "data-i18n-aria": "aria-label"}[attr]
                if target not in d:
                    self.anomalies.append(
                        f"line {line}: <{tag}> has {attr}='{d[attr]}' but no "
                        f"inline {target} attribute to fall back to")
                else:
                    self.usages.append(Usage(d[attr], d[target], kind, line))

        if "data-i18n" in d:
            if tag in _VOID:
                self.anomalies.append(
                    f"line {line}: data-i18n='{d['data-i18n']}' on void "
                    f"<{tag}> — there is no textContent to translate")
                return
            if self._cap_key is not None:
                # Nested i18n element: the outer one is not text-only.
                self.anomalies.append(
                    f"line {line}: data-i18n='{d['data-i18n']}' nested inside "
                    f"data-i18n='{self._cap_key}' (line {self._cap_line})")
                self._finish()
            self._cap_tag, self._cap_key = tag, d["data-i18n"]
            self._cap_line, self._cap_buf = line, []
        elif self._cap_key is not None and tag not in _VOID:
            self.anomalies.append(
                f"line {self._cap_line}: data-i18n='{self._cap_key}' wraps "
                f"markup (<{tag}> at line {line}); applyI18n() would erase it")

    def handle_startendtag(self, tag, attrs) -> None:   # <br/> etc.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._cap_key is not None and tag == self._cap_tag:
            self._finish()

    def handle_data(self, data: str) -> None:
        if self._cap_key is not None:
            self._cap_buf.append(data)


# --- t('key', 'english') call sites ----------------------------------------
# `(?<![\w$.])` keeps this off `format(`, `.at(`, `split(` and friends.
_T_CALL = re.compile(r"(?<![\w$.])t\(")

_JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
               "v": "\v", "0": "\0", "'": "'", '"': '"', "\\": "\\",
               "`": "`", "/": "/"}


def _read_js_string(text: str, i: int) -> tuple[str | None, int]:
    """Decode the JS string literal starting at `text[i]`.

    Returns `(value, index-after-the-closing-quote)`, or `(None, i)` when
    `text[i]` does not start a plain single/double-quoted literal. Template
    literals deliberately return None: a `${…}` interpolation cannot be
    compared against a catalog entry, and the caller reports those rather
    than dropping them.
    """
    quote = text[i]
    if quote not in "'\"":
        return None, i
    out: list[str] = []
    j = i + 1
    while j < len(text):
        c = text[j]
        if c == "\\":
            nxt = text[j + 1] if j + 1 < len(text) else ""
            if nxt == "u":
                if j + 2 < len(text) and text[j + 2] == "{":
                    end = text.index("}", j + 2)
                    out.append(chr(int(text[j + 3:end], 16)))
                    j = end + 1
                else:
                    out.append(chr(int(text[j + 2:j + 6], 16)))
                    j += 6
            elif nxt == "x":
                out.append(chr(int(text[j + 2:j + 4], 16)))
                j += 4
            elif nxt == "\n":
                j += 2                      # line continuation
            else:
                out.append(_JS_ESCAPES.get(nxt, nxt))
                j += 2
            continue
        if c == quote:
            return "".join(out), j + 1
        if c == "\n":
            return None, i                  # unterminated — not a literal
        out.append(c)
        j += 1
    return None, i


def _parse_t_calls(text: str) -> tuple[list[Usage], list[str]]:
    """Every `t(key, english)` call site, plus the ones we could not read."""
    usages: list[Usage] = []
    unparseable: list[str] = []
    for m in _T_CALL.finditer(text):
        i = m.end()
        while i < len(text) and text[i] in " \t\n":
            i += 1
        key, i = _read_js_string(text, i)
        if key is None:
            continue                        # not a t(key, …) call at all
        line = text.count("\n", 0, m.start()) + 1
        while i < len(text) and text[i] in " \t\n":
            i += 1
        if i >= len(text) or text[i] != ",":
            unparseable.append(f"line {line}: t('{key}', …) has no second argument")
            continue
        i += 1
        while i < len(text) and text[i] in " \t\n":
            i += 1
        english, j = _read_js_string(text, i)
        if english is None:
            snippet = text[i:i + 48].split("\n")[0]
            unparseable.append(
                f"line {line}: t('{key}', …) fallback is not a plain string "
                f"literal: {snippet!r}")
            continue
        # Reject `t('k', 'a' + b)` — the literal is only part of the value.
        k = j
        while k < len(text) and text[k] in " \t\n":
            k += 1
        if k < len(text) and text[k] not in ",)":
            unparseable.append(
                f"line {line}: t('{key}', …) fallback is an expression, not a "
                f"literal (next char {text[k]!r})")
            continue
        usages.append(Usage(key, english, "t()", line))
    return usages, unparseable


@lru_cache(maxsize=1)
def index_html() -> str:
    return INDEX.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def i18n_usages() -> tuple[list[Usage], list[str], list[str]]:
    """(usages, markup anomalies, unparseable t() call sites)."""
    p = _I18nMarkupParser()
    p.feed(index_html())
    p.close()
    t_usages, unparseable = _parse_t_calls(index_html())
    return p.usages + t_usages, p.anomalies, unparseable


@lru_cache(maxsize=1)
def catalog(lang: str = "en") -> dict[str, str]:
    data = json.loads((I18N / lang / "ui.json").read_text(encoding="utf-8"))
    return dict(data.get("strings") or {})


def _lang_catalog(lang: str) -> dict[str, str]:
    return catalog(lang)


# ---------------------------------------------------------------------------
# help-docs.md
# ---------------------------------------------------------------------------

@dataclass
class HelpSection:
    hid: str
    line: int
    fields: dict[str, str]
    bodies: list[str]           # the `### x` names, in document order
    text: str


def parse_help_docs(path: Path) -> list[HelpSection]:
    """`## <id>` sections with their `name:`/`path:` lines and `### x` bodies."""
    out: list[HelpSection] = []
    cur: HelpSection | None = None
    buf: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## ") and not line.startswith("###"):
            if cur:
                cur.text = "\n".join(buf)
                out.append(cur)
            cur = HelpSection(line[3:].strip(), n, {}, [], "")
            buf = []
            continue
        if cur is None:
            continue
        buf.append(line)
        if line.startswith("### "):
            cur.bodies.append(line[4:].strip())
        elif not cur.bodies:
            m = re.match(r"^([a-z]+):\s*(.*)$", line)
            if m:
                cur.fields.setdefault(m.group(1), m.group(2).strip())
    if cur:
        cur.text = "\n".join(buf)
        out.append(cur)
    return out


@lru_cache(maxsize=1)
def implemented_help_tokens() -> frozenset[str]:
    """The `{{token}}`s `_helpExpandTokens()` actually replaces.

    Scraped from index.html rather than hard-coded, so adding a token to
    the JS is enough and adding one to the prose alone is caught.
    """
    html = index_html()
    start = html.index("function _helpExpandTokens(")
    # The function ends at the next top-level `function ` declaration at the
    # same indentation; a brace counter is overkill for a file this regular.
    end = html.index("\n    function ", start + 1)
    body = html[start:end]
    return frozenset(re.findall(r"\\\{\\\{([a-z-]+)\\\}\\\}", body))


@lru_cache(maxsize=1)
def reachable_help_ids() -> frozenset[str]:
    """Every id `openHelp(id)` can be called with.

    Three sources, and there are only three: the static `data-help`
    attributes in index.html, the server's path-keyed `_HELP_IDS`, and the
    `"converted-file"` id `_tree_to_html()` attaches to any converted row.
    `openHelp()` is never called with a literal — its only call site reads
    `row.dataset.help` — so scraping those covers the space.
    """
    from enough import server as server_mod

    static = set(re.findall(r'data-help="([^"]+)"', index_html()))
    return frozenset(static | set(server_mod._HELP_IDS.values()) | {"converted-file"})


# Sections with no trigger in today's UI. They are kept (and translated)
# because the concepts they document are real and the rows that would carry
# them are planned; deleting the prose would be the wrong fix. Each line
# says which surface is missing.
UNREACHED_SECTIONS: dict[str, str] = {
    "wikisink": "no data-help on the wikisink topbar button",
    "wiki-comments": "no data-help on the wikisink comment rail",
    "paradigms": "the sidebar row carries paradigm-active, not paradigms",
    "infoworld": "infoworld has no sidebar row until a root is configured",
    "mode-system": "no data-help on #mode-stack",
    "merirmaid": "no data-help on the merirmaid chrome",
    "cacheawl": "no data-help on the cacheawl topbar button",
    "footnotes": "no data-help on the footnote rail",
    "paginate": "no data-help on the paginate button",
}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

def _version_sources() -> dict[str, str | None]:
    """Everywhere the product names its own version. None = not found."""
    out: dict[str, str | None] = {}

    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    out["pyproject.toml"] = (pyproject.get("project") or {}).get("version")

    m = re.search(r'__version__\s*=\s*"([^"]+)"',
                  (REPO / "enough" / "__init__.py").read_text(encoding="utf-8"))
    out["enough/__init__.py"] = m.group(1) if m else None

    tauri = REPO / "desktop" / "src-tauri" / "tauri.conf.json"
    if tauri.is_file():
        out["tauri.conf.json"] = json.loads(tauri.read_text(encoding="utf-8")).get("version")

    cargo = REPO / "desktop" / "src-tauri" / "Cargo.toml"
    if cargo.is_file():
        pkg = tomllib.loads(cargo.read_text(encoding="utf-8")).get("package") or {}
        if pkg.get("version"):
            out["Cargo.toml"] = pkg["version"]

    m = re.search(r"enough v(\d+\.\d+\.\d+)",
                  (REPO / "bootstrap.sh").read_text(encoding="utf-8"))
    out["bootstrap.sh"] = m.group(1) if m else None

    m = re.search(r"^#\s.*\(v(\d+\.\d+\.\d+)\)",
                  AGENT_GUIDE.read_text(encoding="utf-8"), re.M)
    out["docs/AGENT_GUIDE.md title line"] = m.group(1) if m else None

    m = re.search(r"Written against enough \*\*(\d+\.\d+\.\d+)\*\*",
                  HELP_CENTER.read_text(encoding="utf-8"))
    out["docs/HELP_CENTER.md header"] = m.group(1) if m else None
    return out


# ---------------------------------------------------------------------------
# HELP_CENTER numbering
# ---------------------------------------------------------------------------

def check_manual_numbering(text: str, label: str) -> list[tuple[str, str]]:
    """`## N.` contiguous from 1; `### N.M` contiguous inside its parent."""
    findings: list[tuple[str, str]] = []
    sections: list[int] = []
    subs: dict[int, list[int]] = defaultdict(list)
    parent: int | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m and not line.startswith("###"):
            parent = int(m.group(1))
            sections.append(parent)
            continue
        m = re.match(r"^###\s+(\d+)\.(\d+)", line)
        if m:
            n, sub = int(m.group(1)), int(m.group(2))
            if n != parent:
                findings.append((
                    f"manual:{label}:sub-under-wrong-parent:{n}.{sub}",
                    f"{label}: '### {n}.{sub}' sits under '## {parent}.'"))
            subs[parent if parent is not None else n].append(sub)
    if sections != list(range(1, len(sections) + 1)):
        findings.append((f"manual:{label}:section-numbering",
                         f"{label}: '## N.' numbering is {sections}, "
                         f"expected 1..{len(sections)}"))
    for n, got in sorted(subs.items()):
        if got != list(range(1, len(got) + 1)):
            findings.append((f"manual:{label}:sub-numbering:{n}",
                             f"{label}: section {n} subsections are {got}, "
                             f"expected 1..{len(got)}"))
    return findings


# ---------------------------------------------------------------------------
# The checks. Each returns [(stable key, human detail)].
# ---------------------------------------------------------------------------

def check_catalog_byte_identity() -> list[tuple[str, str]]:
    usages, _anom, _unp = i18n_usages()
    en = catalog("en")
    out: list[tuple[str, str]] = []
    for u in usages:
        if u.key not in en:
            continue            # i18n_check.py owns the key-set assertion
        if en[u.key] != u.english:
            out.append((f"en-value:{u.key}",
                        f"en/ui.json[{u.key!r}] = {en[u.key]!r} but index.html "
                        f"({u.where}) says {u.english!r}"))
    return out


def check_conflicting_duplicates() -> list[tuple[str, str]]:
    usages, _anom, _unp = i18n_usages()
    by_key: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for u in usages:
        by_key[u.key][u.english].append(u.where)
    out: list[tuple[str, str]] = []
    for key, variants in sorted(by_key.items()):
        if len(variants) > 1:
            detail = "; ".join(f"{eng!r} at {', '.join(where)}"
                               for eng, where in sorted(variants.items()))
            out.append((f"dup-key:{key}", f"key {key!r} carries {len(variants)} "
                                          f"different English strings: {detail}"))
    return out


_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}|%[sd]|%\d\$[sd]")
_INLINE_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")


def check_placeholder_parity() -> list[tuple[str, str]]:
    en = catalog("en")
    out: list[tuple[str, str]] = []
    for lang in LANGS:
        loc = _lang_catalog(lang)
        for key, en_val in sorted(en.items()):
            if key not in loc:
                continue        # i18n_check.py owns missing keys
            for what, rx in (("placeholder", _PLACEHOLDER), ("tag", _INLINE_TAG)):
                want = Counter(rx.findall(en_val))
                got = Counter(rx.findall(loc[key]))
                if want != got:
                    out.append((
                        f"parity:{lang}:{key}:{what}",
                        f"{lang}/ui.json[{key!r}] {what} mismatch: en has "
                        f"{dict(want)}, {lang} has {dict(got)}"))
    return out


def check_untranslated_values() -> list[tuple[str, str]]:
    en = catalog("en")
    out: list[tuple[str, str]] = []
    for lang in LANGS:
        loc = _lang_catalog(lang)
        for key, en_val in sorted(en.items()):
            if key not in loc or loc[key] != en_val:
                continue
            stripped = en_val.strip()
            if not stripped or stripped.casefold() in SAME_IN_EVERY_LANGUAGE:
                continue
            if en_val in COGNATES.get(lang, frozenset()):
                continue
            out.append((f"untranslated:{lang}:{key}",
                        f"{lang}/ui.json[{key!r}] is byte-equal to the English "
                        f"{en_val!r}"))
    return out


def check_help_id_bijection() -> list[tuple[str, str]]:
    sections = {s.hid for s in parse_help_docs(HELP_DOCS)}
    reachable = reachable_help_ids()
    out: list[tuple[str, str]] = []
    for hid in sorted(reachable - sections):
        out.append((f"help-id:missing-section:{hid}",
                    f"help id {hid!r} is reachable in the UI but has no "
                    f"'## {hid}' section in help-docs.md"))
    for hid in sorted(sections - reachable - set(UNREACHED_SECTIONS)):
        out.append((f"help-id:unreachable:{hid}",
                    f"help-docs.md '## {hid}' is not reachable from the UI and "
                    f"is not in UNREACHED_SECTIONS"))
    for hid in sorted(set(UNREACHED_SECTIONS) - sections):
        out.append((f"help-id:stale-allowlist:{hid}",
                    f"UNREACHED_SECTIONS lists {hid!r} but help-docs.md has no "
                    f"such section — delete the entry"))
    for hid in sorted(set(UNREACHED_SECTIONS) & reachable):
        out.append((f"help-id:now-reachable:{hid}",
                    f"{hid!r} is reachable now — delete its UNREACHED_SECTIONS "
                    f"entry"))
    return out


def check_help_section_shape() -> list[tuple[str, str]]:
    implemented = implemented_help_tokens()
    out: list[tuple[str, str]] = []
    for s in parse_help_docs(HELP_DOCS):
        for field in ("name", "path"):
            if field not in s.fields:
                out.append((f"help-shape:{s.hid}:no-{field}",
                            f"help-docs.md '## {s.hid}' (line {s.line}) has no "
                            f"'{field}:' line"))
        if s.bodies != ["what", "how", "ideas"]:
            out.append((f"help-shape:{s.hid}:bodies",
                        f"help-docs.md '## {s.hid}' has bodies {s.bodies}, "
                        f"expected ['what', 'how', 'ideas'] in that order"))
        for tok in sorted(set(re.findall(r"\{\{([a-z-]+)\}\}", s.text))):
            if tok not in implemented:
                out.append((f"help-shape:{s.hid}:token:{tok}",
                            f"help-docs.md '## {s.hid}' uses {{{{{tok}}}}}, which "
                            f"_helpExpandTokens() does not implement "
                            f"(implemented: {sorted(implemented)})"))
    return out


def check_manuals() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    en_text = HELP_CENTER.read_text(encoding="utf-8")
    out += check_manual_numbering(en_text, "docs/HELP_CENTER.md")

    # Cross-references: "section 7", "section 6.8", "§9".
    top = {int(m.group(1)) for m in re.finditer(r"^##\s+(\d+)\.", en_text, re.M)}
    subs = {(int(m.group(1)), int(m.group(2)))
            for m in re.finditer(r"^###\s+(\d+)\.(\d+)", en_text, re.M)}
    for m in re.finditer(r"(?:section|§)\s*(\d+)(?:\.(\d+))?", en_text, re.I):
        n = int(m.group(1))
        if m.group(2) is not None:
            if (n, int(m.group(2))) not in subs:
                out.append((f"manual:xref:{n}.{m.group(2)}",
                            f"HELP_CENTER.md refers to section {n}.{m.group(2)}, "
                            f"which does not exist"))
        elif n not in top:
            out.append((f"manual:xref:{n}",
                        f"HELP_CENTER.md refers to section {n}, which does not exist"))

    for lang in LANGS:
        path = I18N / lang / "help-center.md"
        if path.is_file():
            out += check_manual_numbering(path.read_text(encoding="utf-8"),
                                          f"i18n/{lang}/help-center.md")
    return out


def check_version_lockstep() -> list[tuple[str, str]]:
    found = _version_sources()
    canonical = found["pyproject.toml"]
    out: list[tuple[str, str]] = []
    for name, got in sorted(found.items()):
        if got is None:
            out.append((f"version:{name}",
                        f"{name} names no version (the regex found nothing)"))
        elif got != canonical:
            out.append((f"version:{name}",
                        f"{name} says {got!r}, pyproject.toml says {canonical!r}"))
    return out


def _icon_names() -> set[str]:
    html = index_html()
    names = set(re.findall(r'data-icon="([a-z0-9_-]+)"', html))
    names |= set(re.findall(r"setIcon\([^,()]+,\s*'([a-z0-9_-]+)'", html))
    names |= set(re.findall(r"\bicon:\s*'([a-z0-9_-]+)'", html))
    names |= set(re.findall(r"iconSrc\(\s*'([a-z0-9_-]+)'", html))
    return names


def check_icons() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name in sorted(_icon_names()):
        for variant in (f"{name}.svg", f"{name}-dark.svg"):
            if not (ICONS_BUILD / variant).is_file():
                out.append((f"icon:missing-build:{variant}",
                            f"index.html asks for icon {name!r} but "
                            f"static/icons/build/{variant} does not exist"))
    bbox = json.loads(ICONS_BBOX.read_text(encoding="utf-8"))
    for src in sorted(ICONS_SRC.glob("*.svg")):
        if src.name not in bbox:
            out.append((f"icon:no-bbox:{src.name}",
                        f"static/icons/{src.name} has no scripts/icons-bbox.json "
                        f"entry, so build_icons.py cannot square it"))
    for name in sorted(k for k in bbox if k != "_doc"):
        if not (ICONS_SRC / name).is_file():
            out.append((f"icon:stale-bbox:{name}",
                        f"scripts/icons-bbox.json lists {name} but there is no "
                        f"such source SVG"))
    return out


def check_markup_anomalies() -> list[tuple[str, str]]:
    _usages, anomalies, unparseable = i18n_usages()
    return ([(f"markup:{a.split(':')[0]}:{a}", a) for a in anomalies]
            + [(f"t-call:{u}", u) for u in unparseable])


ALL_CHECKS = {
    "catalog-byte-identity": check_catalog_byte_identity,
    "conflicting-duplicates": check_conflicting_duplicates,
    "placeholder-parity": check_placeholder_parity,
    "untranslated-values": check_untranslated_values,
    "help-id-bijection": check_help_id_bijection,
    "help-section-shape": check_help_section_shape,
    "manuals": check_manuals,
    "version-lockstep": check_version_lockstep,
    "icons": check_icons,
    "markup-anomalies": check_markup_anomalies,
}


@lru_cache(maxsize=1)
def all_findings() -> dict[str, str]:
    """key -> detail, across every check. Cached: the parsers are not free."""
    out: dict[str, str] = {}
    for fn in ALL_CHECKS.values():
        out.update(fn())
    return out


def _assert_clean(name: str) -> None:
    found = dict(ALL_CHECKS[name]())
    new = {k: v for k, v in found.items() if k not in KNOWN_FINDINGS}
    assert not new, (
        f"{len(new)} new content finding(s) from the {name!r} check:\n  "
        + "\n  ".join(f"[{k}] {v}" for k, v in sorted(new.items()))
        + "\n\nFix the content. If the finding is deliberate and a later lane "
          "owns it, add its key to KNOWN_FINDINGS in this file with a reason."
    )


@pytest.mark.parametrize("name", sorted(ALL_CHECKS))
def test_content_check(name: str) -> None:
    """One test per check, so a failure names the drift class up front."""
    _assert_clean(name)


def test_known_findings_still_present() -> None:
    """A fixed finding must lose its KNOWN_FINDINGS entry in the same change.

    Without this the list would silently rot into a set of assertions about
    a tree that no longer exists, and the next real finding to land on one
    of those keys would be waved through.
    """
    found = all_findings()
    gone = sorted(k for k in KNOWN_FINDINGS if k not in found)
    assert not gone, (
        "these KNOWN_FINDINGS entries no longer describe anything — the "
        "finding was fixed, so delete the entry:\n  " + "\n  ".join(gone))


# ---------------------------------------------------------------------------
# Soft check: manual UI labels that do not exist in the catalog
# ---------------------------------------------------------------------------
# HELP_CENTER.md quotes button and menu names in **bold** and `code`. Most
# of those should be findable in en/ui.json — when they aren't, either the
# manual is describing a button that was renamed, or it is quoting prose.
# The heuristic is not precise enough to fail a commit on (file paths,
# markdown syntax and generic emphasis all land in the same buckets), so it
# prints and does not assert. Read the list when you rename a control.

_MANUAL_LABEL = re.compile(r"\*\*([a-z][a-z0-9 ⌘⇧→←↑↓/?+-]{1,28})\*\*")


def manual_label_warnings() -> list[str]:
    en_values = {v.strip().casefold() for v in catalog("en").values()}
    text = HELP_CENTER.read_text(encoding="utf-8")
    seen: set[str] = set()
    out: list[str] = []
    for m in _MANUAL_LABEL.finditer(text):
        label = m.group(1).strip()
        fold = label.casefold()
        if fold in seen or fold in en_values:
            continue
        seen.add(fold)
        # A label is only interesting if it reads like a control: short,
        # no sentence punctuation, and not obviously a product name.
        if len(label.split()) > 4 or fold in SAME_IN_EVERY_LANGUAGE:
            continue
        out.append(label)
    return sorted(out)


def test_manual_labels_warning_only(capsys: pytest.CaptureFixture[str]) -> None:
    """Never fails. Prints (with -s) the manual's bold labels that no
    en/ui.json value matches — a rename checklist, not a gate."""
    warnings = manual_label_warnings()
    with capsys.disabled():
        if warnings:
            print(f"\n  [soft] {len(warnings)} bold label(s) in HELP_CENTER.md "
                  f"match no en/ui.json value:")
            for w in warnings[:40]:
                print(f"         · {w}")
            if len(warnings) > 40:
                print(f"         … and {len(warnings) - 40} more")


if __name__ == "__main__":       # `python tests/test_content_integrity.py`
    findings = all_findings()
    known = {k: v for k, v in findings.items() if k in KNOWN_FINDINGS}
    new = {k: v for k, v in findings.items() if k not in KNOWN_FINDINGS}
    print(f"{len(findings)} finding(s): {len(known)} known, {len(new)} new\n")
    for k, v in sorted(new.items()):
        print(f"  NEW   [{k}] {v}")
    for k in sorted(known):
        print(f"  known [{k}] {findings[k]}")
    print(f"\nsoft label warnings: {manual_label_warnings()}")
