"""Structural guards for the CSS inside our HTML pages.

A browser never reports a CSS syntax error; it recovers silently, and the
recovery can take a neighbour down with it. 0.3.5 inserted the composure
block directly above `.conversation {` and the selector line went with the
edit: its declarations were left standing at rule-list level with nothing
to apply to. The parser then swallowed them — and the closing brace, and
the `.empty-hint` selector after it — as one long invalid prelude, so two
rules vanished and the chat lost its padding, its scroller and its centred
empty hint for two releases while every test stayed green.

So this walks every `<style>` element of every page under enough/static
with a small tokenizer that knows comments, strings, url()/parens and the
two at-rule shapes we use (a block of rules: @media, @supports, @container,
@layer, @keyframes…; a block of declarations: @font-face, @page…), and
fails on:

  * a declaration run at rule-list level — a `;` before any `{`, which is
    exactly what an orphaned block looks like (selectors never contain one
    outside a string or a bracket);
  * a prelude that runs into a `}` (an extra closing brace);
  * an empty selector (`{` with nothing in front of it);
  * a `{` inside a declaration block (a lost `}` makes the next rule a
    child of the previous one) — the file does not use CSS nesting, and
    the day it does this check should learn `&`;
  * a declaration without a colon (a selector left inside a block);
  * an unclosed block, comment or string.

Every message carries the page and the line number in that page.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "enough" / "static"

# At-rules whose block holds rules (anything else with a block holds
# declarations). Vendor prefixes are stripped before the lookup.
_RULE_LIST_AT = frozenset((
    "media", "supports", "container", "layer", "document", "scope",
    "starting-style", "keyframes",
))


class CSSStructureError(ValueError):
    pass


class _Walker:
    """A deliberately small recursive-descent pass over one stylesheet."""

    def __init__(self, css: str, line0: int, label: str) -> None:
        self.s = css
        self.n = len(css)
        self.line0 = line0
        self.label = label
        self.errors: list[str] = []

    # -- positions -----------------------------------------------------
    def line(self, i: int) -> int:
        return self.line0 + self.s.count("\n", 0, i)

    def err(self, i: int, msg: str) -> None:
        self.errors.append(f"{self.label}:{self.line(i)}: {msg}")

    # -- lexical skips -------------------------------------------------
    def skip_comment(self, i: int) -> int:
        """`i` is at `/*`; return the index after `*/`."""
        j = self.s.find("*/", i + 2)
        if j < 0:
            self.err(i, "unclosed comment")
            return self.n
        return j + 2

    def skip_string(self, i: int) -> int:
        q = self.s[i]
        j = i + 1
        while j < self.n:
            c = self.s[j]
            if c == "\\":
                j += 2
                continue
            if c == q:
                return j + 1
            if c == "\n":
                break
            j += 1
        self.err(i, "unclosed string")
        return j

    def skip_ws(self, i: int) -> int:
        while i < self.n:
            if self.s[i].isspace():
                i += 1
            elif self.s.startswith("/*", i):
                i = self.skip_comment(i)
            else:
                break
        return i

    def scan_prelude(self, i: int, stops: str) -> tuple[int, str, str]:
        """Read until one of `stops` at bracket depth 0. Returns (index of
        the stop or n, the stop char or '', the prelude text with comments
        removed)."""
        depth = 0
        out: list[str] = []
        while i < self.n:
            c = self.s[i]
            if self.s.startswith("/*", i):
                i = self.skip_comment(i)
                out.append(" ")
                continue
            if c in "\"'":
                j = self.skip_string(i)
                out.append(self.s[i:j])
                i = j
                continue
            if c in "([":
                depth += 1
            elif c in ")]":
                depth = max(0, depth - 1)
            elif depth == 0 and c in stops:
                return i, c, "".join(out)
            out.append(c)
            i += 1
        return i, "", "".join(out)

    # -- grammar -------------------------------------------------------
    def rule_list(self, i: int, nested_at: int | None) -> int:
        """Rules until EOF (top level) or the `}` closing `nested_at`."""
        while True:
            i = self.skip_ws(i)
            if i >= self.n:
                if nested_at is not None:
                    self.err(nested_at, "block opened here is never closed")
                return i
            c = self.s[i]
            if c == "}":
                if nested_at is not None:
                    return i + 1
                self.err(i, "stray '}' at the top level (unbalanced braces)")
                i += 1
                continue
            if c == "@":
                i = self.at_rule(i)
                continue
            i = self.qualified_rule(i)

    def at_rule(self, i: int) -> int:
        j = i + 1
        while j < self.n and (self.s[j].isalnum() or self.s[j] in "-_"):
            j += 1
        name = self.s[i + 1:j].lower()
        bare = name.split("-", 2)[-1] if name.startswith("-") else name
        stop_i, stop, _ = self.scan_prelude(j, "{;}")
        if stop == ";":
            return stop_i + 1                      # @import, @charset, …
        if stop != "{":
            self.err(i, f"@{name} has no block")
            return stop_i + (1 if stop == "}" else 0)
        if bare in _RULE_LIST_AT:
            return self.rule_list(stop_i + 1, stop_i)
        return self.declaration_block(stop_i + 1, stop_i)

    def qualified_rule(self, i: int) -> int:
        stop_i, stop, prelude = self.scan_prelude(i, "{;}")
        text = " ".join(prelude.split())
        if stop == ";":
            self.err(i, "declarations outside any rule (a selector line went "
                        f"missing?): {text[:70]!r}")
            return stop_i + 1
        if stop == "}":
            self.err(i, f"selector runs into '}}' (unbalanced braces): {text[:70]!r}")
            return stop_i + 1
        if stop == "":
            self.err(i, f"selector with no block: {text[:70]!r}")
            return stop_i
        if not text:
            self.err(stop_i, "empty selector before '{'")
        return self.declaration_block(stop_i + 1, stop_i)

    def declaration_block(self, i: int, opened_at: int) -> int:
        while True:
            i = self.skip_ws(i)
            if i >= self.n:
                self.err(opened_at, "block opened here is never closed")
                return i
            if self.s[i] == "}":
                return i + 1
            if self.s[i] == ";":
                i += 1
                continue
            stop_i, stop, decl = self.scan_prelude(i, "{;}")
            text = " ".join(decl.split())
            if stop == "{":
                self.err(i, "a block inside a declaration block (missing '}' "
                            f"before {text[:60]!r}?)")
                # Recover by treating it as a nested declaration block.
                i = self.declaration_block(stop_i + 1, stop_i)
                continue
            if ":" not in text:
                self.err(i, f"declaration without a colon: {text[:70]!r}")
            if stop == "":
                self.err(opened_at, "block opened here is never closed")
                return stop_i
            i = stop_i + (1 if stop == ";" else 0)


def check_css(css: str, *, line0: int = 1, label: str = "<css>") -> list[str]:
    w = _Walker(css, line0, label)
    w.rule_list(0, None)
    return w.errors


class _StyleCollector(HTMLParser):
    """Real `<style>` elements only. HTMLParser keeps `<script>` content
    opaque, so a "<style>" inside JS (a comment, a template) is not one."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.blocks: list[tuple[int, str]] = []
        self._in: int | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag == "style":
            self._in = self.getpos()[0]
            self._buf = []

    def handle_data(self, data):  # noqa: ANN001
        if self._in is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag == "style" and self._in is not None:
            self.blocks.append((self._in, "".join(self._buf)))
            self._in = None


def _pages() -> list[Path]:
    return sorted(p for p in STATIC.rglob("*.html"))


@pytest.mark.parametrize("page", _pages(), ids=lambda p: str(p.relative_to(STATIC)))
def test_style_blocks_are_well_formed(page: Path) -> None:
    parser = _StyleCollector()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    errors: list[str] = []
    for line, css in parser.blocks:
        # The `<style>` tag's own line is where the CSS text begins.
        errors += check_css(css, line0=line, label=str(page.relative_to(REPO)))
    assert not errors, "CSS structure:\n  " + "\n  ".join(errors)


def test_index_html_has_its_stylesheet() -> None:
    """Guard the guard: if the collector ever stops seeing the main block,
    the test above would pass vacuously."""
    parser = _StyleCollector()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    assert parser.blocks and max(len(css) for _, css in parser.blocks) > 100_000


# ---------------------------------------------------------------------------
# The checker itself
# ---------------------------------------------------------------------------

def test_catches_the_0_3_5_orphaned_conversation_rule() -> None:
    css = """
    .comp-pal-prompt[hidden] {
      display: none;
    }
      flex: 1 1 auto;
      overflow-y: auto;
      margin: 0 auto;
    }

    .empty-hint {
      color: var(--fg-faint);
    }
    """
    errors = check_css(css)
    assert errors and "declarations outside any rule" in errors[0]
    assert ":5:" in errors[0]          # the line of `flex: 1 1 auto;`


@pytest.mark.parametrize("css, needle", [
    (".a { color: red; }\n}\n.b { color: blue; }", "stray '}'"),
    (".a { color: red;\n.b { color: blue; }", "block inside a declaration"),
    (".a { color: red; ", "never closed"),
    ("{ color: red; }", "empty selector"),
    (".a { color red; }", "without a colon"),
    (".a { content: 'x }", "unclosed string"),
    ("/* never ends .a { }", "unclosed comment"),
    ("@media (max-width: 10px) { .a { color: red; }", "never closed"),
])
def test_flags_broken_shapes(css: str, needle: str) -> None:
    errors = check_css(css)
    assert any(needle in e for e in errors), errors


def test_accepts_what_the_app_really_writes() -> None:
    css = r"""
    /* braces { and } and ; in a comment */
    :root { --x: 1; }
    a[href^="#"], a[title='a;b{c}'] { color: red; }
    .x::before { content: "}"; }
    .y::after { content: '\'' ; }
    .bg { background: url(data:image/svg+xml;utf8,<svg></svg>); }
    :is(.a, .b) > .c:not(.d) { margin: 0 auto }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) { --x: 2; }
      @supports (display: grid) { .g { display: grid; } }
    }
    @keyframes blink { 50% { opacity: 0; } from { opacity: 1 } }
    @-webkit-keyframes spin { to { transform: rotate(1turn); } }
    @font-face { font-family: "X"; src: url("x.woff2") format("woff2"); }
    @import url("x.css");
    .last { color: blue }
    """
    assert check_css(css) == []
