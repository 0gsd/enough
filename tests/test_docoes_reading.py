"""Two DocOES reading debts left after 0.6 (tracker enough-small-debts-after-0-6), each in the shapes the manual's
translators had to word around in the fabula round (docs/fabula-landed-D2b-*.md):

- a paragraph that opens with a bold label glued to a bold button ("**Leerlo.** **abrir el fabulac** …") read the
  label as the paragraph's one optional lead word and the button as a defined-term candidate, so a translated
  section had one candidate more than the English and its terms fell back to English — or, where the counts still
  matched, the translation's term came from the wrong paragraph;
- the section linker skipped a citation into another document ("Thym (…), its section 4") only in English, so
  "ihrem Abschnitt 4", "sa section 4", "su sección 4", "仕様書のセクション 4" and "它的第 4 节" linked to the
  manual's own section 4.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import docoes as D
from enough import docoes_html as X

REPO = Path(__file__).resolve().parents[1]


def _cat(text: str, lang: str, reference: str | None = None) -> dict:
    return D.enumerate_markdown(text, doc_id="doc/guide", lang=lang, source_path=f"guide.{lang}.md",
                                reference_text=reference, version="1")


def _terms(text: str, lang: str, reference: str | None = None) -> dict:
    return {n["id"]: n for n in _cat(text, lang, reference)["nodes"] if n["type"] == "term"}


# ------------------------------------------------------------------------------------------------ glued bolds

# 12.7 of the manual, in miniature: the term, then a paragraph led by a bold label and a bold button. In English the
# label has a space in it ("Reading it."), so it was never taken for a lead word; a one-word label was.
EN_FABULAC = """# Guide

## 1. A folder's fabulac

A **fabulac** is a folder read as a whole: what it holds, who wrote it, and what it is for.

**Reading it.** **open the fabulac** opens it in the cosm viewer, with its runs on the left.

## 2. More

The end.
"""

ES_FABULAC = """# Guía

## 1. El fabulac de una carpeta

Un **fabulac** es una carpeta leída entera: lo que tiene, quién la escribió y para qué sirve.

**Leerlo.** **abrir el fabulac** lo abre en el visor cosm, con sus pasadas a la izquierda.

## 2. Más

Fin.
"""

ZH_FABULAC = """# 指南

## 1. 一个文件夹的 fabulac

**fabulac** 是被整个读过的一个文件夹：里面有什么，谁写的，拿来做什么。

**读它。** **打开 fabulac** 会在 cosm 查看器里打开它，运行记录在左边。

## 2. 更多

完。
"""

FR_ISOGRAPH = """# Guide

## 1. Le holograph

Un **holograph** est le volume où vos parts sont gardées, chacune avec son côté et sa force.

**L'isograph.** **l'isograph…**, dans la barre d'outils, fait sa face publique.

## 2. Plus

Fin.
"""

EN_ISOGRAPH = """# Guide

## 1. The holograph

A **holograph** is the volume your parts are kept in, each with its side and its strength.

**The isograph.** **isograph…**, in the toolbar, makes its public face.

## 2. More

The end.
"""


@pytest.mark.parametrize("text, lang", [(ES_FABULAC, "es"), (ZH_FABULAC, "zh")])
def test_a_bold_label_glued_to_a_bold_button_is_no_term_candidate(text, lang):
    """"**Leerlo.** **abrir el fabulac** …" (es) and "**读它。** **打开 fabulac** …" (zh): the label ends in a stop, so
    the paragraph defines nothing, as its English does; the term before it is told in the translation's words."""
    en = _terms(EN_FABULAC, "en")
    assert list(en) == ["T:term/fabulac"]
    got = _terms(text, lang, EN_FABULAC)
    assert list(got) == ["T:term/fabulac"]
    t = got["T:term/fabulac"]
    assert not t.get("fallback"), t
    assert t["name"] == "fabulac" and t["defined_in"] == "S:section/1"
    assert t["summary"] != en["T:term/fabulac"]["summary"]               # the translation's sentence, not the author's


def test_the_same_in_french_with_an_elided_label():
    """"**L'isograph.** **l'isograph…**" (fr 13.8, where the holograph fell back to English)."""
    got = _terms(FR_ISOGRAPH, "fr", EN_ISOGRAPH)["T:term/holograph"]
    assert not got.get("fallback") and got["summary"].startswith("Un holograph est le volume")


def test_a_glued_label_never_gives_the_wrong_term():
    """When the counts happen to match, the place decides: English had a candidate from its glued label and
    paragraph ("**Shorts.** **compile a short** …"), the French had one elsewhere ("**Relire.** **ouvrir** …"), so
    the French term "short" came from the paragraph about the button. Now neither paragraph is a candidate."""
    en = """# Guide

## 1. Shorts

**Shorts.** **compile a short** writes the twin back out as prose.

A **short** is the same meaning told again, as a markdown file.

**Reading one again.** **open** shows it beside the text.
"""
    fr = """# Guide

## 1. Les shorts

**Les shorts.** **compiler un short** réécrit le jumeau en prose.

Un **short** est le même sens raconté à nouveau, dans un fichier markdown.

**Relire.** **ouvrir** le montre à côté du texte.
"""
    t = _terms(fr, "fr", en)["T:term/short"]
    assert not t.get("fallback") and t["name"] == "short", t
    assert t["summary"].startswith("Un short est le même sens"), t["summary"]


def test_a_lead_word_is_still_one_plain_word():
    """What the lead word is for stays: an article before the bold ("Der **Ordner** ist …", "La **forme** …"), and
    a bold that is not a label ("**Audit** reads …") is still the candidate; a bold label with a stop is not."""
    lines, _fences = D._scan("Der **Ordner** ist ein Ort.\n\n**Audit** liest etwas.\n\n**Faces.** Zoom far out.\n\n"
                             "**Lenses.** **lens…** draws a volume.\n\nA**b** **c** d.\n")
    blocks = D._blocks(lines, 0, len(lines) - 1)
    names = [c["name"] for c in D._candidates(blocks, False)["sentence"]]
    assert names == ["Ordner", "Audit"], names


def test_the_manual_s_tellings_keep_their_terms():
    """The real manual: zh 12.7 and 12.8 (fabulac, cshort, catem) and fr 13.8 (holograph) fell back to English
    because of a glued label; they are told in their own words now."""
    for lang, ids in (("zh", ("T:term/fabulac", "T:term/cshort", "T:term/catem")), ("fr", ("T:term/holograph",))):
        cat = D.catalog_for("help-center", lang)
        by = {n["id"]: n for n in cat["nodes"]}
        for tid in ids:
            assert not by[tid].get("fallback"), (lang, tid)


# ------------------------------------------------------------------------------------------------ "its section N"

# Each telling of "the whole of both grammars is in Thym's specification, in its section 4; section 2 says where to
# read it", written the way the translations would write it if nothing linked it wrongly (docs/I18N.md).
CITES = {
    "en": "Both grammars are in Thym's specification (https://thym.cosmoes.org/), in its section 4; section 2 says "
          "where to read it.",
    "de": "Beide Grammatiken stehen in der Spezifikation von Thym, in ihrem Abschnitt 4; Abschnitt 2 sagt, wo du sie "
          "liest.",
    "fr": "Les deux grammaires sont dans la spécification de Thym, en sa section 4 ; la section 2 dit où la lire.",
    "es": "Las dos gramáticas están en la especificación de Thym, en su sección 4; la sección 2 dice dónde leerla.",
    "ja": "二つの文法の全体は、Thym の仕様書のセクション 4 にあります。どこで読めるかは、セクション 2 が言っています。",
    "zh": "两种语法的全部内容都写在 Thym 的规范里，就在那份规范的第 4 节；第 2 节说了去哪里读它。",
}
# More of each language's ways of saying it: inflections, plurals, lists, and the word for "its" itself.
MORE = {
    "de": ["seinem Abschnitt 4", "ihre Abschnitte 4 und 5", "dessen Abschnitt 4", "Ihr Abschnitt 4"],
    "fr": ["ses sections 4 et 5", "leur section 4", "Sa section 4"],
    "es": ["sus secciones 4 y 5", "Su sección 4"],
    "ja": ["そのセクション 4", "仕様のセクション 4", "仕様書の セクション 4"],
    "zh": ["它的第 4 节", "其第 4 节", "规范第 4 节"],
}
# And what must still link: the manual's own sections, however the sentence runs up to them.
STILL = {
    "de": ["in Abschnitt 4", "Abschnitte 4 und 5"],
    "fr": ["la section 4", "visa section 4"],
    "es": ["la sección 4", "menu sección 4"],
    "ja": ["ヘルプセンターのセクション 4", "セクション 4 と 5"],
    "zh": ["见第 4 节", "规范化第 4 节"],
}
HEAD = {"en": "Guide", "de": "Anleitung", "fr": "Guide", "es": "Guía", "ja": "ガイド", "zh": "指南"}


def _doc(lang: str, sentence: str) -> str:
    return f"# {HEAD[lang]}\n\n## 1. A\n\n{sentence}\n\n## 2. B\n\nx\n\n## 4. D\n\ny\n\n## 5. E\n\nz\n"


@pytest.mark.parametrize("lang", list(CITES))
def test_its_section_is_another_document_s_in_every_language(lang):
    """The core (`_SEC_REF`, `_ZH_REF`): the citation into Thym's text is no mention of this text's section 4; the
    plain "section 2" in the same sentence still is."""
    by = {n["id"]: n for n in _cat(_doc(lang, CITES[lang]), lang)["nodes"]}
    assert by["S:section/1"]["mentions"] == ["S:section/2"], (lang, by["S:section/1"].get("mentions"))


@pytest.mark.parametrize("lang", list(MORE))
def test_its_section_in_its_other_forms(lang):
    for s in MORE[lang]:
        by = {n["id"]: n for n in _cat(_doc(lang, s + "."), lang)["nodes"]}
        assert not by["S:section/1"].get("mentions"), (lang, s, by["S:section/1"].get("mentions"))
    for s in STILL[lang]:
        by = {n["id"]: n for n in _cat(_doc(lang, s + "."), lang)["nodes"]}
        assert "S:section/4" in (by["S:section/1"].get("mentions") or []), (lang, s)


@pytest.mark.parametrize("lang", list(CITES))
def test_the_exporter_skips_it_too(lang):
    """The exporter's `XREF_RE` (what the static pages link): the same citation is plain words, "section 2" a link."""
    def hits(s: str) -> list[str]:
        return [n for m in X.XREF_RE.finditer(s) for n in X._NUM_RE.findall(m.group(1) or m.group(2) or "")]
    assert hits(CITES[lang]) == ["2"], (lang, hits(CITES[lang]))
    for s in MORE.get(lang, []):
        assert hits(s) == [], (lang, s)
    for s in STILL.get(lang, []):
        assert "4" in hits(s), (lang, s)


def test_the_words_are_one_list():
    """The core and the exporter read one list of "its" words per language (docoes.OTHER_DOC_WORDS)."""
    assert set(D.OTHER_DOC_WORDS) == {"en", "de", "fr", "es", "ja", "zh"}
    for lang, words in D.OTHER_DOC_WORDS.items():
        for w in words:
            assert w in D._SEC_REF.pattern + D._ZH_REF.pattern, (lang, w)
            assert w in X.XREF_RE.pattern, (lang, w)


def test_the_page_skips_the_same_words():
    """The docs viewer's `DOCS_XREF_RE` (index.html) carries the same words: one word of each language is looked for
    (the page spells the list as one alternation: "ihr(?:e|em|en|er|es)?", "仕様書?の")."""
    html = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const DOCS_XREF_RE"):html.index("const DOCS =", html.index("const DOCS_XREF_RE"))]
    for lang, word in {"en": "its", "de": "dessen", "fr": "ses", "es": "sus", "ja": "その", "zh": "它的"}.items():
        assert word in block, (lang, word)
