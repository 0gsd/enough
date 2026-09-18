"""Terminology lint for the composure round's shared vocabulary.

`docs/composure-plan.md` → "Shared vocabulary (binding for every phase)"
renamed the product's nouns:

  * the assistant is the **chief readvisor** (named Ed out of the box, and
    user-renamable — never hard-coded in prose),
  * what used to be "roles" are **readvisors**,
  * anything mechanical is done by **enough** ("enough saves the file"),
    never by "the agent".

So no English user-facing surface may still say "agent" or say "role" in
the old sense. This module is that check, over:

  * `enough/static/i18n/en/ui.json`  — the interface catalog's values,
  * `enough/static/help-docs.md`     — the in-product help bubbles,
  * `docs/HELP_CENTER.md`            — the manual,
  * `README.md`,
  * `defaults/**/*.md`               — shipped AGENT.md / MOTIVATION.md,
    paradigms, policies, skills, readvisors,
  * `enough/static/index.html`       — visible text only: the element text
    of `data-i18n` elements plus `t('key', 'English')` fallbacks.

Only **prose** is scanned. Fenced code blocks are dropped, and no `.py`,
`.js` or `.json` source is read apart from the English catalog's values —
so the OpenAI message-role sense (`{"role": "user"}`), python function
names and CSS custom properties are out of scope by construction rather
than by allowlist.

`docs/AGENT_GUIDE.md` is deliberately absent: its audience is an external
coding agent and it keeps that wording (composure-plan, P4).

The five translations get the same lint, with their own legacy renderings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "enough" / "static"
I18N = STATIC / "i18n"
INDEX = STATIC / "index.html"
HELP_DOCS = STATIC / "help-docs.md"
HELP_CENTER = REPO / "docs" / "HELP_CENTER.md"
README = REPO / "README.md"
DEFAULTS = REPO / "defaults"

LANGS = ("fr", "es", "de", "zh", "ja")


# ---------------------------------------------------------------------------
# The allowlist
# ---------------------------------------------------------------------------
# Every entry is an exact phrase or a tightly-scoped context, with the reason
# it is exempt. Matches are deleted from the line *before* the lint looks at
# it, so an exempt phrase can never shadow a real hit elsewhere on that line.
#
# Add to this list only for identifiers, filenames, or the external-agent
# sense — never to excuse prose that should have been swept.

ALLOWLIST: tuple[tuple[str, str], ...] = (
    # --- filenames, which do not get renamed (composure-plan, "Shared
    #     vocabulary"): AGENT.md, AGENTS.md, AGENT_GUIDE.md, and the
    #     readvisory skill's AGENT.draft.md.
    (r"\bAGENTS?(?:_GUIDE)?\.(?:draft\.)?md\b",
     "on-disk filename, never renamed"),

    # --- the HTTP header and its lowercase prose form ("sites that reject
    #     blank/botty user agents"), in anything-finder.
    (r"\bUser-Agent\b", "HTTP request header"),
    (r"\buser agents?\b", "HTTP User-Agent, in prose"),

    # --- agents that are not enough's: an external coding/LLM agent.
    (r"\b(?:coding|LLM|external|frontier|browser)\s+agents?\b",
     "an agent that is not enough's assistant"),
    # Graham's byline in the manual's first paragraph, and the same sentence
    # in each translated manual.
    (r"maintained primarily by agents",
     "HELP_CENTER intro: Graham on who writes the manual"),
    (r"maintenu principalement par des agents", "fr: the same byline"),
    (r"mantenido principalmente por agentes", "es: the same byline"),
    (r"vor allem von Agenten geschrieben", "de: the same byline"),
    (r"主要由智能体撰写", "zh: the same byline"),
    (r"主にエージェントたちが書き", "ja: the same byline"),

    # --- legal boilerplate quoted verbatim by anything-finder's patent
    #     playbook: "a registered patent attorney / or agent." (wrapped, so
    #     the phrase reaches the lint split across two quoted lines).
    (r"^>\s*or agent\b", "patent attorney or agent (quoted disclaimer)"),
    (r"\bpatent attorney\s+or\s+agent\b", "patent attorney or agent"),

    # --- macOS/systemd launch agents, in analyzer's audit references.
    (r"\blaunch\s+agents?(?:/daemon)?\b", "launchd/systemd launch agent"),

    # --- girraph's on-disk attribution value: `by:` is `user`, `agent`, or a
    #     readvisor slug. A backticked bare token is an identifier, not voice.
    (r"`agents?`", "girraph `by: agent` on-disk value"),
    (r"`roles?`", "on-disk/API identifier"),

    # --- ARIA and CSS, wherever prose quotes markup.
    (r"""\brole\s*=\s*["'][^"']*["']""", "ARIA role attribute"),
    (r"""\bclass\s*=\s*["'][^"']*\brole\b[^"']*["']""", "CSS class"),

    # --- identifiers that stay (composure-plan, "Shared vocabulary").
    (r"\{\{roles-list\}\}", "help-docs expansion token"),
    (r"\bsidebar\.roles\b", "catalog key"),
    (r"/api/roles[\w*]*", "API route"),
    (r"#roles-list\b", "DOM id"),

    # --- `rness/roles` survives in exactly one place: the migration note
    #     that explains the rename to people whose projects predate it
    #     (HELP_CENTER §8, and the same sentence summarized at the top).
    #     Anywhere else it is a stale path and should fail.
    (r"`rness/roles/` folder rather than `rness/readvisors/`",
     "HELP_CENTER §8: the rename migration note"),
    (r"`rness/roles/` folder renamed to `rness/readvisors/`",
     "HELP_CENTER intro: the same migration note, summarized"),
    (r"\*\*readvisors\*\*, which is what roles are called now",
     "HELP_CENTER intro: names the old word in order to retire it"),
    #     the same gloss, in each translated manual's header.
    (r"le nouveau nom des rôles", "fr: names the old word in order to retire it"),
    (r"como se llaman ahora los roles", "es: the same gloss"),
    (r"wie die Rollen jetzt heißen", "de: the same gloss"),
    (r"从前那个「角色」现在的名字", "zh: the same gloss"),
    (r"これはロールの新しい呼び名", "ja: the same gloss"),
    #     the old path quoted beside the new one — the migration note as the
    #     translations phrase it. A bare `rness/roles/` still fails.
    (r"`rness/roles/`[^`]*`rness/readvisors/`",
     "the rename migration note, old path named alongside the new"),

    # --- katakana collisions: the ja legacy word ロール is a substring of
    #     ordinary vocabulary. Nothing here is the readvisor sense.
    (r"スクロール", "ja: スクロール = scroll / scrollback"),
    (r"クロール", "ja: クロール = crawl, the web ingest"),
)

_ALLOWLIST = tuple((re.compile(p, re.IGNORECASE), why) for p, why in ALLOWLIST)

# The old vocabulary, English.
ENGLISH_LEGACY = re.compile(r"\bagents?\b|\broles?\b", re.IGNORECASE)

# The old vocabulary, per language (composure-plan P4).
LEGACY_BY_LANG: dict[str, re.Pattern[str]] = {
    "fr": re.compile(r"\bagents?\b|\brôles?\b", re.IGNORECASE),
    "es": re.compile(r"\bagentes?\b|\brol(?:es)?\b", re.IGNORECASE),
    "de": re.compile(r"\bAgenten?\b|\bRollen?\b", re.IGNORECASE),
    "zh": re.compile(r"智能体|角色"),
    "ja": re.compile(r"エージェント|ロール"),
}


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Hit:
    where: str      # "path:line" or "path:key"
    match: str      # the offending word
    text: str       # the line it sat on

    def __str__(self) -> str:
        line = self.text.strip()
        if len(line) > 140:
            line = line[:137] + "…"
        return f"{self.where}: {self.match!r} — {line}"


def _exempt(line: str) -> str:
    """The line with every allowlisted phrase removed."""
    for pattern, _why in _ALLOWLIST:
        line = pattern.sub(" ", line)
    return line


def _scan(where: str, line: str, legacy: re.Pattern[str]) -> list[Hit]:
    return [Hit(where, m.group(0), line) for m in legacy.finditer(_exempt(line))]


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _prose_lines(path: Path) -> list[tuple[int, str]]:
    """Numbered lines of a markdown file, fenced code blocks dropped."""
    out: list[tuple[int, str]] = []
    fence: str | None = None
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            continue
        out.append((n, line))
    return out


def _scan_markdown(path: Path, legacy: re.Pattern[str]) -> list[Hit]:
    return [h for n, line in _prose_lines(path)
            for h in _scan(f"{_rel(path)}:{n}", line, legacy)]


def _scan_help_docs(path: Path, legacy: re.Pattern[str]) -> list[Hit]:
    """`name:` values and `### what`/`### how`/`### ideas` bodies.

    `## <id>` headings and `path:` values are identifiers — `scripts/
    i18n_check.py` compares them across languages — so they are not prose
    and are not scanned.
    """
    hits: list[Hit] = []
    for n, line in _prose_lines(path):
        if line.startswith("## ") and not line.startswith("### "):
            continue
        if re.match(r"^path:", line):
            continue
        hits += _scan(f"{_rel(path)}:{n}", line, legacy)
    return hits


def _scan_catalog(lang: str, legacy: re.Pattern[str]) -> list[Hit]:
    path = I18N / lang / "ui.json"
    strings = json.loads(path.read_text(encoding="utf-8")).get("strings") or {}
    return [h for key, value in sorted(strings.items())
            if isinstance(value, str)
            for h in _scan(f"{_rel(path)}:{key}", value, legacy)]


# --- index.html visible text ------------------------------------------------
# test_content_integrity.py already scrapes exactly this (and is owned by
# another lane), so borrow it when it imports cleanly and fall back to a
# small scraper of our own when it does not.

_DATA_I18N = re.compile(r'data-i18n="([^"]+)"[^>]*>([^<]*)<')
_T_CALL = re.compile(
    r"""(?<![\w$.])t\(\s*(['"])(?P<key>(?:\\.|(?!\1).)*?)\1\s*,\s*"""
    r"""(['"])(?P<english>(?:\\.|(?!\3).)*?)\3\s*[),]""")


def _index_visible_text() -> list[tuple[str, int, str]]:
    """(key, line, english) for every visible string declared in index.html."""
    try:
        from test_content_integrity import i18n_usages  # type: ignore
        return [(u.key, u.line, u.english) for u in i18n_usages()[0]]
    except Exception:                                   # pragma: no cover
        html = INDEX.read_text(encoding="utf-8")
        out: list[tuple[str, int, str]] = []
        for pattern, group in ((_DATA_I18N, 2), (_T_CALL, "english")):
            for m in pattern.finditer(html):
                english = m.group(group)
                if not english.strip():
                    continue
                key = m.group(1 if group == 2 else "key")
                out.append((key, html.count("\n", 0, m.start()) + 1, english))
        return out


def _scan_index(legacy: re.Pattern[str]) -> list[Hit]:
    return [h for key, line, english in _index_visible_text()
            for h in _scan(f"{_rel(INDEX)}:{line} ({key})", english, legacy)]


def _report(hits: list[Hit], surface: str) -> str:
    return (f"{len(hits)} legacy-vocabulary hit(s) in {surface}. "
            f"Rename to chief readvisor / readvisors / enough, or add an "
            f"exact phrase to ALLOWLIST with its reason:\n  "
            + "\n  ".join(str(h) for h in hits))


# ---------------------------------------------------------------------------
# English — hard failures
# ---------------------------------------------------------------------------

def test_english_catalog_has_no_legacy_vocabulary():
    hits = _scan_catalog("en", ENGLISH_LEGACY)
    assert not hits, _report(hits, "the English ui catalog")


def test_help_docs_has_no_legacy_vocabulary():
    hits = _scan_help_docs(HELP_DOCS, ENGLISH_LEGACY)
    assert not hits, _report(hits, "help-docs.md")


def test_help_center_has_no_legacy_vocabulary():
    hits = _scan_markdown(HELP_CENTER, ENGLISH_LEGACY)
    assert not hits, _report(hits, "HELP_CENTER.md")


def test_readme_has_no_legacy_vocabulary():
    hits = _scan_markdown(README, ENGLISH_LEGACY)
    assert not hits, _report(hits, "README.md")


def test_defaults_prose_has_no_legacy_vocabulary():
    files = sorted(DEFAULTS.rglob("*.md"))
    assert files, "no shipped markdown found under defaults/"
    hits = [h for path in files for h in _scan_markdown(path, ENGLISH_LEGACY)]
    assert not hits, _report(hits, "defaults/**/*.md")


def test_index_html_visible_text_has_no_legacy_vocabulary():
    strings = _index_visible_text()
    assert strings, "scraped no visible strings out of index.html"
    hits = _scan_index(ENGLISH_LEGACY)
    assert not hits, _report(hits, "index.html's visible text")


# ---------------------------------------------------------------------------
# The five translations — hard failures too
# ---------------------------------------------------------------------------
# The translated legacy bubbles were swept in the follow-up round (composure
# round P4), so these carry the same weight as the English cases above.

@pytest.mark.parametrize("lang", LANGS)
def test_translation_has_no_legacy_vocabulary(lang: str):
    legacy = LEGACY_BY_LANG[lang]
    hits = _scan_catalog(lang, legacy)
    for name, scan in (("help-docs.md", _scan_help_docs),
                       ("help-center.md", _scan_markdown)):
        path = I18N / lang / name
        if path.exists():
            hits += scan(path, legacy)
    assert not hits, _report(hits, f"the {lang} surfaces")
