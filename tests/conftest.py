"""Shared fixtures: the project-registry isolation every test gets, and the
convert suite's generated `.docx`.

The `.docx` fixture is **built at test time**, not checked in as bytes.
pandoc is a base dependency now, so any machine that can run the suite can
also make the file — and a generated fixture can't drift away from the pandoc
that has to read it back. It carries the three things the round trip has to
survive: an inline image, a footnote, and a header/footer.

The header/footer is injected into the zip afterwards because pandoc has no
way to emit one; that is also precisely why it is the interesting assertion.
Markdown cannot express a running header, so if one comes out the far side of
an overwrite-export it can only have come from `--reference-doc` — which makes
this fixture the test of plan Decision 4.
"""

from __future__ import annotations

import base64
import re
import subprocess
import zipfile
from pathlib import Path

import pytest

# 4x4 PNG. Small enough to inline, real enough for pandoc to extract.
FIXTURE_PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFklEQVR4nGP8z8Dwn4"
    b"GKgImahg0bAwFdvQIFcCkjWQAAAABJRU5ErkJggg==")

FIXTURE_HEADER = "ENOUGH-FIXTURE-HEADER"
FIXTURE_FOOTER = "ENOUGH-FIXTURE-FOOTER"
FIXTURE_FOOTNOTE = "the footnote body."

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml"

_HDR_XML = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:hdr xmlns:w="{_W}"><w:p><w:r><w:t>{FIXTURE_HEADER}</w:t>'
            f'</w:r></w:p></w:hdr>')
_FTR_XML = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{_W}"><w:p><w:r><w:t>{FIXTURE_FOOTER}</w:t>'
            f'</w:r></w:p></w:ftr>')

@pytest.fixture(autouse=True)
def isolated_project_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point `ENOUGH_PROJECTS_STATE` at tmp_path for **every** test.

    `ensure_skeleton()` registers the project it just built (home-plan §6),
    and half the suite calls it — so without this the test run would file the
    developer's tmp dirs on their real home screen. Autouse rather than
    opt-in for exactly that reason: the seam has to be closed by default, not
    by remembering.
    """
    monkeypatch.setenv("ENOUGH_PROJECTS_STATE",
                       str(tmp_path / "state" / "projects.json"))


FIXTURE_MD = (
    "# Fixture\n\n"
    "A paragraph with a footnote.[^1]\n\n"
    "![a tiny square](fixture-img.png)\n\n"
    f"[^1]: {FIXTURE_FOOTNOTE}\n"
)


def build_docx_fixture(dest: Path, pandoc: str) -> Path:
    """Write a `.docx` at `dest` containing an image, a footnote, and a
    header/footer. `dest.parent` is used as scratch space."""
    work = dest.parent
    (work / "fixture-img.png").write_bytes(FIXTURE_PNG)
    src = work / "_fixture-src.md"
    src.write_text(FIXTURE_MD, encoding="utf-8")
    base = work / "_fixture-base.docx"
    subprocess.run([pandoc, "-f", "gfm+footnotes", "-t", "docx",
                    "-o", base.name, src.name], cwd=work, check=True,
                   capture_output=True)
    with zipfile.ZipFile(base) as zin:
        names = zin.namelist()
        items = {n: zin.read(n) for n in names}

    rels = items["word/_rels/document.xml.rels"].decode("utf-8").replace(
        "</Relationships>",
        f'<Relationship Id="rIdHdrX" Type="{_REL}/header" Target="header1.xml"/>'
        f'<Relationship Id="rIdFtrX" Type="{_REL}/footer" Target="footer1.xml"/>'
        "</Relationships>")
    ct = items["[Content_Types].xml"].decode("utf-8").replace(
        "</Types>",
        f'<Override PartName="/word/header1.xml" ContentType="{_CT}.header+xml"/>'
        f'<Override PartName="/word/footer1.xml" ContentType="{_CT}.footer+xml"/>'
        "</Types>")
    doc = items["word/document.xml"].decode("utf-8")
    assert "<w:sectPr" in doc, "pandoc emitted no sectPr to hang the header off"
    doc = re.sub(r"(<w:sectPr[^>]*>)",
                 r'\1<w:headerReference w:type="default" r:id="rIdHdrX"/>'
                 r'<w:footerReference w:type="default" r:id="rIdFtrX"/>',
                 doc, count=1)

    items["word/document.xml"] = doc.encode("utf-8")
    items["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    items["[Content_Types].xml"] = ct.encode("utf-8")
    items["word/header1.xml"] = _HDR_XML.encode("utf-8")
    items["word/footer1.xml"] = _FTR_XML.encode("utf-8")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in list(names) + ["word/header1.xml", "word/footer1.xml"]:
            zout.writestr(name, items[name])
    for scratch in (base, src, work / "fixture-img.png"):
        scratch.unlink()
    return dest


def docx_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


@pytest.fixture
def make_docx():
    """Factory: `make_docx(path)` → a fixture .docx at `path`. Skips the test
    when pandoc is missing, which on a healthy install never happens (it is a
    base dependency) but keeps a broken venv from reading as a failure."""
    from enough import convert

    pandoc = convert.pandoc_path()
    if not pandoc:
        pytest.skip("pandoc unavailable in this environment")

    def _make(dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        return build_docx_fixture(dest, pandoc)

    return _make
