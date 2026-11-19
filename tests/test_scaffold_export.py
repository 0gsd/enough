"""A scaffold exported as the thing it is (0.8, lane W3-E5, E6): a page as HTML and PDF, a deck as PPTX and PDF, a
document as Markdown and PDF, each a new file beside the composure and never one written over. PDFs are counted
with pypdf. The PPTX tests are skipped when pandoc is absent (it ships with enough through pypandoc-binary, so a
skip means a broken environment), and the PPTX is opened back with python-pptx only when that is installed (it
comes with the optional `pdf` extra)."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from enough import composure as C
from enough import convert
from enough import scaffold_export as X
from enough import scaffolder as SC

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold_fixtures as F  # noqa: E402

HAS_PANDOC = convert.pandoc_path() is not None
needs_pandoc = pytest.mark.skipif(not HAS_PANDOC, reason="pandoc is absent, so no PPTX or typst text can be made")

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


def pages(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


def with_picture(project: Path, comp: Path, box: str) -> None:
    (project / "pics").mkdir(exist_ok=True)
    (project / "pics" / "plot.png").write_bytes(PNG)
    C.apply_ops(comp, None, [{"op": "update_module", "id": SC.module_id(box), "href": "pics/plot.png"}])


# ---------------------------------------------------------------------------
# What goes in
# ---------------------------------------------------------------------------

def test_the_thing_leaves_out_notes_empty_boxes_and_never_the_plectrum_words(project: Path):
    path = F.deck(project)
    thing = X.read_thing(path, project)
    assert thing.kind == "deck" and len(thing.frames) == 10            # "Not in the deck" is not exported
    names = {b.name for f in thing.frames for b in f.boxes()}
    assert "Notes to the readvisor" not in names
    assert {x["box"] for x in thing.left_out} >= {"plot-picture", "plan-picture"}
    assert [f.notes for f in thing.frames if f.notes] == [[F.DECK_WORDS["speaker-notes-the-ask"]]]
    every = " ".join(b.text for f in thing.frames for b in f.boxes())
    plecs = [b["plec"] for b in SC.loads(SC.plectrum_path(path).read_text()).boxes()]
    assert not any(p in every for p in plecs if p)


def test_each_thing_offers_its_own_formats(project: Path):
    path = F.deck(project)
    with pytest.raises(X.ExportError, match="a deck exports as pptx or pdf, not html"):
        X.export(path, "html", project_dir=project)
    plain = project / "plain.comp"
    C.save(plain, C.new_composure("cards", "Plain"))
    with pytest.raises(X.ExportError, match="not a scaffold"):
        X.export(plain, "pdf", project_dir=project)


# ---------------------------------------------------------------------------
# A page: HTML and PDF
# ---------------------------------------------------------------------------

def test_a_page_as_one_self_contained_html_file(project: Path):
    path = F.page(project)
    out = X.export(path, "html", project_dir=project)
    html = Path(out["path"]).read_text(encoding="utf-8")
    assert out["written"] == "more-page.html" and out["thing"] == "page"
    assert html.startswith("<!doctype html>") and "<style>" in html
    assert "written by the person" in html
    assert "<script" not in html and "http://" not in html and "https://" not in html
    plecs = [b["plec"] for b in SC.loads(SC.plectrum_path(path).read_text()).boxes() if b["plec"]]
    assert plecs and not any(p in html for p in plecs)                  # the readvisor's words never reach it
    # a second export is a new file beside the first, never one written over
    again = X.export(path, "html", project_dir=project)
    assert again["written"] == "more-page-2.html" and Path(out["path"]).read_text(encoding="utf-8") == html


@needs_pandoc
def test_a_page_as_pdf_one_page_per_frame_written(project: Path):
    path = F.page(project)
    thing = X.read_thing(path, project)
    out = X.export(path, "pdf", project_dir=project)
    assert out["written"] == "more-page.pdf" and out["pages"] == pages(Path(out["path"]))
    assert out["pages"] == len([f for f in thing.frames if f.rows])
    assert "written by the person" in PdfReader(out["path"]).pages[0].extract_text()


# ---------------------------------------------------------------------------
# A deck: PPTX and PDF
# ---------------------------------------------------------------------------

@needs_pandoc
def test_a_deck_as_pdf_at_16_9_one_page_per_slide(project: Path):
    path = F.deck(project)
    with_picture(project, path, "plot-picture")
    out = X.export(path, "pdf", project_dir=project)
    reader = PdfReader(out["path"])
    assert len(reader.pages) == 10 == out["pages"]
    box = reader.pages[0].mediabox
    assert abs(float(box.width) / float(box.height) - 16 / 9) < 0.01
    assert "plot-picture" not in {x["box"] for x in out["left_out"]}
    text = "".join(p.extract_text() for p in reader.pages)
    assert "Mill Lane" in text and "Pause here" not in text               # speaker notes are not on a slide


@needs_pandoc
def test_a_slide_with_too_many_words_shrinks_rather_than_spills(project: Path):
    long = " ".join(["Every word the person wrote stays on the slide."] * 60)
    path = F.build(project, "ten-slide-deck.md", "Long", {"cover-title": "Long", "plan-body": long})
    out = X.export(path, "pdf", project_dir=project)
    assert out["pages"] == 2


@needs_pandoc
def test_a_deck_as_pptx_through_pandoc(project: Path):
    path = F.deck(project)
    with_picture(project, path, "plot-picture")
    out = X.export(path, "pptx", project_dir=project)
    assert out["written"] == "a-garden-on-mill-lane.pptx" and out["bytes"] > 10_000
    assert Path(out["path"]).read_bytes()[:2] == b"PK"
    md = X.deck_markdown(X.read_thing(path, project))
    assert md.startswith('---\ntitle: "A garden on Mill Lane"')
    assert "::: notes\nPause here." in md and ":::::: columns" in md
    pptx = pytest.importorskip("pptx", reason="python-pptx comes with the optional pdf extra; not installed")
    deck = pptx.Presentation(out["path"])
    assert len(deck.slides) == 10
    assert deck.slides[0].slide_layout.name == "Title Slide"
    texts = ["\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) for s in deck.slides]
    assert "We ask the comittee" in texts[1]
    assert deck.slides[1].notes_slide.notes_text_frame.text.startswith("Pause here")
    gets = next(t for t in texts if "What the town gets" in t)
    assert all(w in gets for w in ("Fresh food", "A place for the school", "A tidy plot"))   # three tiles, folded


# ---------------------------------------------------------------------------
# A document: Markdown and PDF
# ---------------------------------------------------------------------------

def test_a_document_as_markdown_by_rule(project: Path):
    path = F.document(project)
    out = X.export(path, "md", project_dir=project)
    md = Path(out["path"]).read_text(encoding="utf-8")
    assert out["written"] == "recipe-book.md"
    assert md.count("written by the person") == F.DOC_WORDS_FIRST
    assert md.startswith("# ")


def test_markdown_by_rule_for_each_as():
    def b(as_: str, text: str, **kw) -> X.Box:
        return X.Box(id="x", name="x", as_=as_, kind="text", text=text, row=1, col=1, **kw)
    assert X.box_markdown(b("title", "A\nbook")) == "# A book"
    assert X.box_markdown(b("headline", "Soup")) == "## Soup"
    assert X.box_markdown(b("deck", "Warm")) == "### Warm"
    assert X.box_markdown(b("quote", "one\n\ntwo")) == "> one\n>\n> two"
    assert X.box_markdown(b("caption", "A bowl")) == "*A bowl*"
    assert X.box_markdown(b("call", "Cook it")) == "**Cook it**"
    assert X.box_markdown(b("body", "Plain *words*.")) == "Plain *words*."
    assert X.box_markdown(b("body", "Words.", fixed="Comprise", chips=["PDF", "PPTX"])) == (
        "Comprise\n\nWords.\n\nPDF · PPTX")


@needs_pandoc
def test_a_document_as_pdf_through_pandoc_and_typst(project: Path):
    path = F.document(project)
    out = X.export(path, "pdf", project_dir=project)
    assert out["written"] == "recipe-book.pdf" and out["pages"] == pages(Path(out["path"])) >= 1
    assert "written by the person" in PdfReader(out["path"]).pages[0].extract_text()


def test_nothing_written_is_refused_with_words(project: Path):
    path = F.build(project, "more-page.md", "Blank page")
    with pytest.raises(X.ExportError, match="nothing written") as e:
        X.export(path, "html", project_dir=project)
    assert e.value.status == 409
    assert not list(path.parent.glob("blank-page.*.html")) and not (path.parent / "blank-page.html").exists()
