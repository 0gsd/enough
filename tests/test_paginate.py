"""Unit pass over enough/paginate.py: the option schema, the size table,
output naming, the imposition arithmetic, the `.typ` surgery — and the real
pandoc + typst compile.

pandoc and typst are base dependencies, so the compile tests run
unconditionally. The bundled fonts are wave C's and may not be on disk yet,
so anything that needs them skips rather than fails; `enough/footnotes.py` is
wave A's and gets a private stub here when it isn't there, so that the same
assertions hold before and after it lands.

Everything below tmp_path.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from enough import convert, paginate


@pytest.fixture(autouse=True)
def scratch_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_EXTRAS_STATE", str(tmp_path / "state" / "extras.json"))
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(tmp_path / "state" / "weights"))
    convert.reset_engines()
    yield
    convert.reset_engines()


@pytest.fixture
def footnotes_module(monkeypatch: pytest.MonkeyPatch):
    """The real `enough.footnotes` when wave A has landed, otherwise a private
    stub with the same signature. Never writes the module to disk — that file
    belongs to the other wave."""
    try:
        from enough import footnotes  # noqa: PLC0415 — presence is the point
        return footnotes
    except ImportError:
        pass
    stub = types.ModuleType("enough.footnotes")

    def renumber(text: str) -> tuple[str, dict[str, str]]:
        return text, {}

    stub.renumber = renumber  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "enough.footnotes", stub)
    return stub


def pandoc_typ(md: str, work: Path) -> str:
    """Real pandoc output for `md`, the way the worker asks for it."""
    exe = convert.pandoc_path()
    if not exe:
        pytest.skip("pandoc unavailable in this environment")
    src = work / "src.md"
    src.write_text(md, encoding="utf-8")
    out = subprocess.run([exe, "-f", "gfm+footnotes", "-t", "typst",
                          "--standalone", src.name],
                         cwd=work, capture_output=True, text=True, check=True)
    return out.stdout


CHAPTERED_MD = """# Chapter One

Prose with a note.[^1] And a second one.[^2]

## A subsection

```python
= not a heading
x = [1, 2]
```

# Chapter Two

The last chapter.[^3]

[^1]: First note, with [brackets] and `code[x]`.
[^2]: Second note.
[^3]: Third note.
"""


# ---------------------------------------------------------------------------
# Options (plan §2.2)
# ---------------------------------------------------------------------------

def test_validate_defaults_everything_but_the_path():
    opts = paginate.validate({"path": "notes/book.md"})
    assert opts["path"] == "notes/book.md"
    assert opts["name"] == "book"            # the source's stem, when unnamed
    for key, value in paginate.DEFAULTS.items():
        assert opts[key] == value
    assert opts["custom_size"] is None
    assert opts["headers"] == {"enabled": False,
                               "left": {"text": "", "chapter": False},
                               "right": {"text": "", "chapter": False}}


def test_validate_rejects_every_bad_enum():
    for bad in ({"footnotes": "margin"}, {"size": "tabloid"},
                {"orientation": "sideways"}, {"layout": "threeup"},
                {"font": "Comic Sans"}):
        with pytest.raises(paginate.PaginateError) as e:
            paginate.validate({"path": "a.md", **bad})
        assert e.value.status == 400


def test_validate_needs_a_path():
    with pytest.raises(paginate.PaginateError) as e:
        paginate.validate({})
    assert e.value.status == 400


def test_validate_margin_bounds_and_the_page_it_has_to_fit():
    with pytest.raises(paginate.PaginateError):
        paginate.validate({"path": "a.md", "margin_mm": 0.0})
    with pytest.raises(paginate.PaginateError):
        paginate.validate({"path": "a.md", "margin_mm": 500.0})
    with pytest.raises(paginate.PaginateError) as e:
        # 55mm all round on a 105mm-wide pocket page leaves nothing.
        paginate.validate({"path": "a.md", "size": "pocket", "margin_mm": 55.0})
    assert "leaves no page" in str(e.value)
    with pytest.raises(paginate.PaginateError):
        paginate.validate({"path": "a.md", "margin_mm": "20"})


def test_validate_custom_size():
    opts = paginate.validate({"path": "a.md", "size": "custom",
                              "custom_size": {"w": 140, "h": 216, "unit": "mm"}})
    assert paginate.page_size_mm(opts) == (140.0, 216.0)
    # Landscape swaps, custom or not.
    opts["orientation"] = "landscape"
    assert paginate.page_size_mm(opts) == (216.0, 140.0)

    with pytest.raises(paginate.PaginateError) as e:
        paginate.validate({"path": "a.md", "size": "custom"})
    assert "custom_size is required" in str(e.value)
    for bad in ({"w": 1, "h": 216, "unit": "mm"},        # too small
                {"w": 140, "h": 216, "unit": "cubits"},
                {"w": "wide", "h": 216, "unit": "mm"}):
        with pytest.raises(paginate.PaginateError):
            paginate.validate({"path": "a.md", "size": "custom", "custom_size": bad})


def test_validate_export_name_is_a_plain_filename():
    for bad in ("../escape", "sub/book", ".hidden", "x" * 200):
        with pytest.raises(paginate.PaginateError) as e:
            paginate.validate({"path": "a.md", "name": bad})
        assert e.value.status == 400
    assert paginate.validate({"path": "a.md", "name": " my book "})["name"] == "my book"


def test_validate_headers_normalize():
    opts = paginate.validate({"path": "a.md", "headers": {
        "enabled": 1, "left": {"text": "  Title\x07 ", "chapter": 0},
        "right": {"text": "", "chapter": "yes"}}})
    assert opts["headers"]["enabled"] is True
    assert opts["headers"]["left"] == {"text": "Title", "chapter": False}
    assert opts["headers"]["right"]["chapter"] is True
    with pytest.raises(paginate.PaginateError):
        paginate.validate({"path": "a.md", "headers": {"left": "Title"}})


# ---------------------------------------------------------------------------
# The size table (plan §2.2)
# ---------------------------------------------------------------------------

def test_size_table_matches_the_plan():
    assert set(paginate.SIZES) == {"letter", "half-letter", "legal", "a4", "a5",
                                   "b5", "trade", "digest", "pocket"}
    # digest is half-letter under the name print shops use; both stay.
    assert paginate.SIZES["digest"] == paginate.SIZES["half-letter"]
    assert paginate.SIZES["letter"] == (8.5, 11.0, "in")
    assert paginate.SIZES["a4"] == (210.0, 297.0, "mm")
    for _name, (w, h, unit) in paginate.SIZES.items():
        assert unit in ("in", "mm") and 0 < w < h        # every named size is portrait


def test_page_size_mm_and_the_view_agree():
    letter = paginate.validate({"path": "a.md", "size": "letter"})
    w, h = paginate.page_size_mm(letter)
    assert round(w, 1) == 215.9 and round(h, 1) == 279.4
    landscape = paginate.validate({"path": "a.md", "size": "letter",
                                   "orientation": "landscape"})
    assert paginate.page_size_mm(landscape) == (h, w)
    view = paginate.sizes_view()
    assert set(view) == set(paginate.SIZES)
    assert view["letter"]["w_mm"] == round(w, 2)
    assert 0 < view["a5"]["ratio"] < 1


# ---------------------------------------------------------------------------
# Naming (plan §2.4)
# ---------------------------------------------------------------------------

def test_output_naming_and_collisions(tmp_path: Path):
    when = dt.datetime(2026, 8, 23, 14, 32)
    src = tmp_path / "book.md"
    src.write_text("x", encoding="utf-8")
    first = paginate.output_pdf(src, "book", when)
    assert first.name == "book-2026-08-23.pdf"
    first.write_bytes(b"%PDF")
    second = paginate.output_pdf(src, "book", when)
    assert second.name == "book-2026-08-23-1.pdf"
    second.write_bytes(b"%PDF")
    assert paginate.output_pdf(src, "book", when).name == "book-2026-08-23-2.pdf"
    # A leftover viewer folder counts as taken too — merging into it would
    # mix two runs' pages.
    paginate.pages_dir(tmp_path / "other-2026-08-23.pdf").mkdir()
    assert paginate.output_pdf(src, "other", when).name == "other-2026-08-23-1.pdf"


def test_sidecar_naming(tmp_path: Path):
    pdf = tmp_path / "book-2026-08-23.pdf"
    assert paginate.pages_dir(pdf).name == "book-2026-08-23.pdf.pages"
    assert paginate.viewer_manifest_path(pdf).name == \
        ".book-2026-08-23.pdf.paginate.json"
    assert paginate.page_svg_name(7) == "page-0007.svg"
    assert paginate.is_viewer_manifest(paginate.viewer_manifest_path(pdf))


def test_the_pages_dir_is_only_ours_when_the_manifest_says_so(tmp_path: Path):
    pdf = tmp_path / "notes.pdf"
    mine = paginate.pages_dir(pdf)
    mine.mkdir()
    # Somebody's own folder named that way: not hidden from the tree.
    assert paginate.is_pages_dir(mine) is False
    paginate.write_viewer_manifest(pdf, pages=3, source="notes.md", options={})
    assert paginate.is_pages_dir(mine) is True
    man = paginate.read_viewer_manifest(pdf)
    assert man["version"] == 1 and man["pages"] == 3
    assert man["source"] == "notes.md" and man["created"].endswith("Z")
    # A schema we don't know reads as absent, like the convert manifest.
    p = paginate.viewer_manifest_path(pdf)
    p.write_text(json.dumps({**man, "version": 99}), encoding="utf-8")
    assert paginate.read_viewer_manifest(pdf) is None


# ---------------------------------------------------------------------------
# Imposition arithmetic (plan §2.5.6)
# ---------------------------------------------------------------------------

def test_twoup_page_order():
    assert paginate.sheet_order(1, "twoup") == [(1, None)]
    assert paginate.sheet_order(4, "twoup") == [(1, 2), (3, 4)]
    assert paginate.sheet_order(5, "twoup") == [(1, 2), (3, 4), (5, None)]
    assert paginate.sheet_order(8, "twoup") == [(1, 2), (3, 4), (5, 6), (7, 8)]
    assert paginate.sheet_order(0, "twoup") == []


def test_booklet_page_order():
    # One folded leaf: 4 and 1 on the front, 2 and 3 on the back.
    assert paginate.sheet_order(4, "booklet") == [(4, 1), (2, 3)]
    assert paginate.sheet_order(8, "booklet") == [(8, 1), (2, 7), (6, 3), (4, 5)]
    # 5 pages pads to 8; the padding is blank, never a repeat.
    assert paginate.sheet_order(5, "booklet") == \
        [(None, 1), (2, None), (None, 3), (4, 5)]
    assert paginate.sheet_order(1, "booklet") == [(None, 1), (None, None)]
    for n in (1, 4, 5, 8, 13):
        placed = [p for sheet in paginate.sheet_order(n, "booklet") for p in sheet
                  if p is not None]
        assert sorted(placed) == list(range(1, n + 1))   # each page exactly once
        assert len(paginate.sheet_order(n, "booklet")) == (n + (-n % 4)) // 2


def test_an_unimposed_layout_is_not_a_sheet_order():
    with pytest.raises(paginate.PaginateError):
        paginate.sheet_order(4, "single")


def test_placement_rects():
    w, h = 100.0, 200.0
    assert paginate.sheet_size(w, h) == (200.0, 100.0)
    assert paginate.slot_scale(w, h) == 0.5
    left = paginate.slot_rect(0, w, h)
    right = paginate.slot_rect(1, w, h)
    assert left == (25.0, 0.0, 50.0, 100.0)
    assert right == (125.0, 0.0, 50.0, 100.0)
    # Both halves hold the same page, mirrored across the fold.
    assert right[0] - paginate.sheet_size(w, h)[0] / 2 == left[0]
    # A tall page is limited by the sheet's height instead, and is centred
    # horizontally in its half rather than filling it.
    x, y, pw, ph = paginate.slot_rect(0, 100.0, 300.0)
    assert round(pw, 3) == 33.333 and round(ph, 3) == 100.0
    assert round(x, 3) == 58.333 and round(y, 3) == 0.0


# ---------------------------------------------------------------------------
# `.typ` surgery: the pandoc template boundary
# ---------------------------------------------------------------------------

def test_split_template_against_real_pandoc(tmp_path: Path):
    """The one external contract in this module.

    pandoc's standalone typst template ends with `#show: doc => conf(…)`, and
    `conf` sets a US-letter page before any set rule in the body could take
    effect — so the rule is cut out, not appended to. If a future pandoc moves
    this boundary, this test is what says so."""
    raw = pandoc_typ(CHAPTERED_MD, tmp_path)
    assert paginate.TEMPLATE_MARKER in raw
    head, body = paginate.split_template(raw)
    # The helpers pandoc's body may reference stay above the cut...
    assert "#let horizontalrule" in head
    assert "#let conf(" in head
    # ...the wrapper itself is gone from both halves...
    assert paginate.TEMPLATE_MARKER not in head
    assert paginate.TEMPLATE_MARKER not in body
    assert "doc,\n)" not in body
    # ...and the body starts at the document's first content.
    assert body.startswith("= Chapter One")
    assert "#footnote[" in body


def test_split_template_refuses_a_template_it_does_not_know():
    with pytest.raises(paginate.PaginateError) as e:
        paginate.split_template("#set page(paper: \"a4\")\n= Hello\n")
    assert e.value.status == 500


def test_chapter_level_detection(tmp_path: Path):
    _head, body = paginate.split_template(pandoc_typ(CHAPTERED_MD, tmp_path))
    assert paginate.chapter_level(body) == 1
    levels = [h["level"] for h in paginate.typ_headings(body)]
    assert levels == [1, 2, 1]
    titles = [h["title"] for h in paginate.typ_headings(body)]
    assert titles == ["Chapter One", "A subsection", "Chapter Two"]
    # `= not a heading` lives inside a code fence and is not one.
    assert "not a heading" not in " ".join(titles)

    # H1-less document: the chapter level is the smallest level present.
    deep = "## Alpha\n\ntext\n\n### Deeper\n\n## Beta\n\nmore\n"
    _h, deep_body = paginate.split_template(pandoc_typ(deep, tmp_path))
    assert paginate.chapter_level(deep_body) == 2
    # No headings at all: one chapter, no page breaks.
    _h, flat = paginate.split_template(pandoc_typ("just prose\n", tmp_path))
    assert paginate.chapter_level(flat) is None


# ---------------------------------------------------------------------------
# `.typ` surgery: balanced-bracket footnote extraction
# ---------------------------------------------------------------------------

def test_extract_footnotes_handles_nesting_and_escapes():
    body = ("Plain.#footnote[a #link(\"http://x\")[nested] body] "
            "and.#footnote[an escaped \\] bracket] end.\n")
    out, bodies, positions = paginate.extract_footnotes(body)
    assert bodies == ['a #link("http://x")[nested] body',
                      "an escaped \\] bracket"]
    assert out == "Plain.#super[1] and.#super[2] end.\n"
    assert [out[p:p + len("#super[1]")] for p in positions] == \
        ["#super[1]", "#super[2]"]


def test_extract_footnotes_leaves_raw_spans_alone():
    # A bracket inside a raw span is text, and `#footnote[` inside one is not
    # a footnote at all.
    body = "A.#footnote[see `f(x[0]` there] and `#footnote[not one]` after.\n"
    out, bodies, _pos = paginate.extract_footnotes(body)
    assert bodies == ["see `f(x[0]` there"]
    assert out == "A.#super[1] and `#footnote[not one]` after.\n"


def test_extract_footnotes_on_real_pandoc_output(tmp_path: Path):
    _head, body = paginate.split_template(pandoc_typ(CHAPTERED_MD, tmp_path))
    out, bodies, positions = paginate.extract_footnotes(body)
    assert len(bodies) == 3 and len(positions) == 3
    assert "#footnote[" not in out
    assert "#super[3]" in out
    # pandoc escapes the brackets it writes into a body; the scanner has to
    # step over them rather than close on them.
    assert "\\[brackets\\]" in bodies[0] and "`code[x]`" in bodies[0]
    assert bodies[1] == "Second note."


def test_a_document_with_no_footnotes_is_untouched():
    body = "= Title\nJust prose.\n"
    out, bodies, positions = paginate.extract_footnotes(body)
    assert (out, bodies, positions) == (body, [], [])
    assert paginate.place_endnotes(body, [], [], "book", 1) == body


# ---------------------------------------------------------------------------
# `.typ` surgery: endnote placement
# ---------------------------------------------------------------------------

def test_chapter_placement_puts_each_chapters_notes_at_its_end(tmp_path: Path):
    raw = pandoc_typ(CHAPTERED_MD, tmp_path)
    opts = paginate.validate({"path": "a.md", "footnotes": "chapter"})
    built, moved = paginate.build_typ(raw, opts)
    assert moved == 3
    assert "#footnote[" not in built
    _head, body = built.split("= Chapter One", 1)
    body = "= Chapter One" + body
    first, second = body.split("= Chapter Two", 1)
    # Notes 1 and 2 belong to chapter one and land before chapter two starts;
    # note 3 lands at the end.
    assert "#super[1] First note" in first and "#super[2] Second note" in first
    assert "#super[3] Third note" in second
    assert first.index("#super[1] First note") > first.index("A subsection")


def test_book_placement_groups_the_notes_under_chapter_subheads(tmp_path: Path):
    raw = pandoc_typ(CHAPTERED_MD, tmp_path)
    opts = paginate.validate({"path": "a.md", "footnotes": "book"})
    built, moved = paginate.build_typ(raw, opts)
    assert moved == 3
    section = built[built.index("= Footnotes"):]
    assert section.index("== Chapter One") < section.index("#super[1] First note")
    assert section.index("== Chapter Two") < section.index("#super[3] Third note")
    # One section, at the end, at chapter level so the show rule breaks a page.
    assert built.count("= Footnotes") == 1
    assert built.index("= Footnotes") > built.index("= Chapter Two")


def test_page_placement_leaves_typsts_own_footnotes_in_place(tmp_path: Path):
    raw = pandoc_typ(CHAPTERED_MD, tmp_path)
    built, moved = paginate.build_typ(
        raw, paginate.validate({"path": "a.md", "footnotes": "page"}))
    assert moved == 0
    assert built.count("#footnote[") == 3
    assert "#super[" not in built


def test_notes_without_chapters_land_at_the_end(tmp_path: Path):
    raw = pandoc_typ("Prose with a note.[^1]\n\n[^1]: the note.\n", tmp_path)
    built, moved = paginate.build_typ(
        raw, paginate.validate({"path": "a.md", "footnotes": "chapter"}))
    assert moved == 1
    assert built.rstrip().endswith("]")
    assert "#super[1] the note." in built
    assert "= Footnotes" not in built


# ---------------------------------------------------------------------------
# The preamble
# ---------------------------------------------------------------------------

def test_preamble_page_and_text():
    opts = paginate.validate({"path": "a.md", "size": "a5", "margin_mm": 18,
                              "font": "Inter"})
    text = paginate.preamble(opts, 1)
    assert "#set page(width: 148mm, height: 210mm, margin: 18mm" in text
    assert '#set text(font: "Inter", size: 11pt' in text
    assert "footer: context align(center)" in text and "counter(page)" in text
    assert "header: none" in text
    assert "#show heading.where(level: 1): it => pagebreak(weak: true) + it" in text
    # No headings in the document → no chapter rule to apply.
    assert "pagebreak" not in paginate.preamble(opts, None)


def test_preamble_page_numbers_off():
    opts = paginate.validate({"path": "a.md", "page_numbers": False})
    assert "footer: none" in paginate.preamble(opts, 1)
    assert "counter(page)" not in paginate.preamble(opts, 1)


def test_preamble_headers_single_uses_the_left_field_only():
    opts = paginate.validate({"path": "a.md", "headers": {
        "enabled": True,
        "left": {"text": 'The "Book"', "chapter": False},
        "right": {"text": "ignored", "chapter": False}}})
    text = paginate.preamble(opts, 1)
    assert 'The \\"Book\\"' in text            # quotes survive as a typst string
    assert "ignored" not in text
    assert "calc.odd" not in text              # one running head, no verso/recto


def test_preamble_headers_imposed_split_odd_and_even():
    opts = paginate.validate({"path": "a.md", "layout": "booklet", "headers": {
        "enabled": True,
        "left": {"text": "My Book", "chapter": False},
        "right": {"text": "", "chapter": True}}})
    text = paginate.preamble(opts, 2)
    assert "calc.odd(here().page())" in text
    assert "My Book" in text
    # "use chapter name" resolves to a typst query at the chapter's level.
    assert "query(heading.where(level: 2))" in text
    assert "h.location().page() <= here().page()" in text


def test_a_chapter_header_with_no_chapters_falls_back_to_empty():
    opts = paginate.validate({"path": "a.md", "headers": {
        "enabled": True, "left": {"text": "", "chapter": True}}})
    text = paginate.preamble(opts, None)
    assert "query(" not in text and "header: context align(left)" in text


# ---------------------------------------------------------------------------
# Fonts (wave C fills the directory; skip cleanly until it does)
# ---------------------------------------------------------------------------

def test_fonts_dir_points_at_the_install_defaults():
    from enough.skeleton import _install_defaults_root
    assert paginate.fonts_dir() == _install_defaults_root() / "fonts"
    assert paginate.font_paths() == \
        ([str(paginate.fonts_dir())] if paginate.fonts_bundled() else [])


def test_a_tree_without_bundled_fonts_still_paginates(project: Path,
                                                      monkeypatch):
    """Dev-tree grace: with no bundled families the worker must let typst
    fall back to the machine's own fonts rather than compile every glyph
    blank against `ignore_system_fonts`."""
    monkeypatch.setattr(paginate, "font_paths", list)
    out = paginate.run_paginate(project, {"path": "book.md", "name": "nf",
                                          "size": "a5"})
    from pypdf import PdfReader
    assert "A first chapter" in PdfReader(
        str(project / out["pdf"])).pages[0].extract_text()


def test_the_bundled_families_are_the_names_typst_sees(tmp_path: Path):
    if not paginate.fonts_bundled():
        pytest.skip("bundled fonts not installed in this tree")
    import typst
    for family in paginate.FONTS:
        probe = tmp_path / "probe.typ"
        probe.write_text(f'#set text(font: "{family}")\nAa Bb 123\n',
                         encoding="utf-8")
        _pdf, warnings = typst.compile_with_warnings(
            str(probe), root=str(tmp_path),
            font_paths=paginate.font_paths(), ignore_system_fonts=True)
        assert not [w for w in warnings if "font" in str(w).lower()], family


# ---------------------------------------------------------------------------
# Footnote reconciliation seam (wave A owns the rules)
# ---------------------------------------------------------------------------

def test_renumber_source_delegates_to_the_footnotes_module(footnotes_module,
                                                           monkeypatch):
    seen: list[str] = []

    def spy(text: str) -> tuple[str, dict[str, str]]:
        seen.append(text)
        return text.replace("[^9]", "[^1]"), {"9": "1"}

    monkeypatch.setattr(footnotes_module, "renumber", spy)
    assert paginate.renumber_source("a[^9]\n\n[^9]: x\n") == "a[^1]\n\n[^1]: x\n"
    assert seen == ["a[^9]\n\n[^9]: x\n"]


# ---------------------------------------------------------------------------
# The real pipeline (pandoc + typst are base dependencies)
# ---------------------------------------------------------------------------

BOOK_MD = """# One

A first chapter with a note.[^1]

# Two

A second chapter with another.[^2]

[^1]: the first note.
[^2]: the second note.
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "book.md").write_text(BOOK_MD, encoding="utf-8")
    return proj


def test_paginate_writes_a_pdf_with_both_attachments(project: Path,
                                                     footnotes_module):
    out = paginate.run_paginate(project, {"path": "book.md", "name": "book",
                                          "size": "a5"})
    assert out["ok"] is True and out["viewer"] is None
    pdf = project / out["pdf"]
    assert pdf.read_bytes().startswith(b"%PDF")
    assert out["pages"] == out["sheets"] == 2      # one chapter per page

    found = paginate.embedded_source(pdf)
    assert found is not None
    source, meta = found
    # Byte-exact: this is the whole point of the round trip. The fixture's
    # numbering is already canonical, so renumbering is a no-op on it.
    assert source == BOOK_MD
    assert meta["version"] == 1
    assert meta["size"] == "a5" and meta["footnotes"] == "page"
    assert meta["name"] == "book" and meta["path"] == "book.md"

    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    assert set(reader.attachments) == {paginate.ATTACH_SOURCE,
                                       paginate.ATTACH_OPTIONS}
    assert float(reader.pages[0].mediabox.width) == pytest.approx(419.5, abs=1)


def test_paginate_brings_the_viewer_pages_in(project: Path, footnotes_module):
    out = paginate.run_paginate(project, {"path": "book.md", "name": "book",
                                          "size": "a5", "bring_in": True})
    pdf = project / out["pdf"]
    pages = paginate.pages_dir(pdf)
    svgs = sorted(p.name for p in pages.iterdir())
    assert svgs == ["page-0001.svg", "page-0002.svg"]
    assert svgs[0] == paginate.page_svg_name(1)
    assert pages.joinpath(svgs[0]).read_text(encoding="utf-8").lstrip()\
        .startswith("<svg")
    man = paginate.read_viewer_manifest(pdf)
    assert man["pages"] == 2 and man["source"] == "book.md"
    assert man["options"]["bring_in"] is True
    assert out["viewer"] == paginate.viewer_manifest_path(pdf).name


def test_paginate_imposes_twoup_and_booklet(project: Path, footnotes_module):
    from pypdf import PdfReader

    single = paginate.run_paginate(project, {"path": "book.md", "name": "s",
                                             "size": "a5"})
    logical = PdfReader(str(project / single["pdf"])).pages[0].mediabox

    twoup = paginate.run_paginate(project, {"path": "book.md", "name": "t",
                                            "size": "a5", "layout": "twoup"})
    reader = PdfReader(str(project / twoup["pdf"]))
    assert twoup["pages"] == 2 and twoup["sheets"] == 1
    assert len(reader.pages) == 1
    # The sheet is the page turned sideways.
    assert float(reader.pages[0].mediabox.width) == pytest.approx(
        float(logical.height), abs=0.5)
    assert float(reader.pages[0].mediabox.height) == pytest.approx(
        float(logical.width), abs=0.5)

    booklet = paginate.run_paginate(project, {"path": "book.md", "name": "b",
                                              "size": "a5", "layout": "booklet"})
    # Two logical pages pad to one four-page signature: two printed sides.
    assert booklet["pages"] == 2 and booklet["sheets"] == 2
    assert len(PdfReader(str(project / booklet["pdf"])).pages) == 2
    # An imposed PDF still carries its source.
    assert paginate.embedded_source(project / booklet["pdf"])[0] == BOOK_MD


def test_paginate_endnote_placements_move_the_notes(project: Path,
                                                    footnotes_module):
    from pypdf import PdfReader

    out = paginate.run_paginate(project, {"path": "book.md", "name": "bk",
                                          "size": "a5", "footnotes": "book"})
    pages = [p.extract_text() for p in PdfReader(str(project / out["pdf"])).pages]
    assert "Footnotes" in pages[-1]
    assert "the first note." in pages[-1] and "the second note." in pages[-1]
    # ...and not at the bottom of the pages they were referenced on.
    assert "the first note." not in pages[0]


def test_paginate_refusals(project: Path):
    with pytest.raises(paginate.PaginateError) as e:
        paginate.run_paginate(project, {"path": "missing.md"})
    assert e.value.status == 404
    with pytest.raises(paginate.PaginateError) as e:
        paginate.run_paginate(project, {"path": "../escape.md"})
    assert e.value.status == 400
    (project / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(paginate.PaginateError) as e:
        paginate.run_paginate(project, {"path": "notes.txt"})
    assert e.value.status == 400 and "markdown" in str(e.value)


def test_status_reports_the_table_the_modal_draws(project: Path):
    body = paginate.status(project, "book.md")
    assert body["fonts"] == list(paginate.FONTS)
    assert set(body["sizes"]) == set(paginate.SIZES)
    assert body["pandoc"] is True and body["typst"] is True
    assert body["name"] == "book" and body["paginated"] == []
    paginate.run_paginate(project, {"path": "book.md", "name": "book",
                                    "size": "a5", "bring_in": True})
    assert len(paginate.status(project, "book.md")["paginated"]) == 1


# ---------------------------------------------------------------------------
# Unpack (plan §2.6) — our own PDF read back without docling
# ---------------------------------------------------------------------------

def test_our_pdf_unpacks_without_docling(project: Path, footnotes_module):
    out = paginate.run_paginate(project, {"path": "book.md", "name": "book",
                                          "size": "a5"})
    pdf = project / out["pdf"]
    # docling is unavailable here (the scratch weights dir is empty), and it
    # is still convertible — because the markdown is in the file.
    assert convert.docling_available() is False
    assert convert.reader_for(pdf) == "unpack"
    assert convert.state(pdf) == "unconverted"
    assert convert.convert_job(pdf)["engine"] == "unpack"

    result = convert.run_convert(pdf)
    assert result["engine"]["name"] == "unpack"
    twin = convert.twin_path(pdf)
    assert twin.read_text(encoding="utf-8") == BOOK_MD
    assert result["assets"] is None and result["images"] == 0
    assert convert.state(pdf) == "fresh"
    assert convert.read_manifest(pdf)["engine"]["name"] == "unpack"


def test_a_foreign_pdf_still_needs_the_reader(project: Path):
    foreign = project / "foreign.pdf"
    foreign.write_bytes(b"%PDF-1.7\n%%EOF\n")
    assert paginate.embedded_source(foreign) is None
    assert convert.reader_for(foreign) == "docling"
    assert convert.state(foreign) == "engine-missing"
    with pytest.raises(convert.ConvertError) as e:
        convert.convert_job(foreign)
    assert e.value.status == 503


def test_the_embedded_source_probe_is_cached_on_the_stat(project: Path,
                                                         monkeypatch):
    pdf = project / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%%EOF\n")
    calls: list[Path] = []
    real = paginate.embedded_source
    monkeypatch.setattr(paginate, "embedded_source",
                        lambda p: (calls.append(p), real(p))[1])
    paginate.reset_embed_cache()
    assert paginate.has_embedded_source(pdf) is False
    assert paginate.has_embedded_source(pdf) is False
    assert len(calls) == 1
    pdf.write_bytes(b"%PDF-1.7\n% changed\n%%EOF\n")
    assert paginate.has_embedded_source(pdf) is False
    assert len(calls) == 2
