"""Shared fixtures: the state isolation every test gets, and the convert
suite's generated `.docx`.

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
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

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

# Every `ENOUGH_*` seam that names a path into the developer's real state,
# mapped to its home under tmp_path. Mirrors `scripts/smoke_boot.py`'s
# `build_env()` — keep the two in step; that script is the other half of the
# same rule, for the subprocess servers the pre-commit suite boots.
_STATE_SEAMS = {
    "ENOUGH_WEIGHTS_DIR": "weights",
    "ENOUGH_LIVE_STATE": "live-models.json",
    "ENOUGH_CACHEAWL_ROOT": "cacheawl",
    "ENOUGH_INFOWORLD_ROOT": "no-infoworld",
    "ENOUGH_WIKISINK_CONFIG": "wikisink.json",
    "ENOUGH_UI_CONFIG": "ui.json",
    "ENOUGH_EXTRAS_STATE": "extras.json",
    "ENOUGH_PROJECTS_STATE": "config/projects.json",
    # The user-global readvisors dir (P7): a test that installs one at
    # global scope would otherwise file it in the developer's real
    # ~/enough/readvisors/ and symlink it into every project they open.
    "ENOUGH_READVISORS_ROOT": "readvisors",
    # FEED (0.4.1): the built dictionary + the user's own entries. And its
    # source dir, pointed at nothing: every app a test boots would otherwise
    # start a 380 MB background build from reflib/dict. Dictionary tests
    # write a small fixture source and point the seam at it themselves.
    "ENOUGH_DICT_ROOT": "dict",
    "ENOUGH_DICT_SOURCE": "no-dict-source",
}

# Seams that must be *absent*, not redirected. Each of these changes
# behaviour rather than location — a developer who happens to export one in
# their shell would otherwise get a different test run than CI, and tests
# that need them (the desktop-shutdown gate, the llama-server lookup ladder)
# set them for themselves.
_BEHAVIOUR_SEAMS = (
    "ENOUGH_LLAMA_SERVER", "ENOUGH_DESKTOP", "ENOUGH_DESKTOP_TOKEN",
    "ENOUGH_DESKTOP_CODE", "ENOUGH_DESKTOP_UV", "ENOUGH_DESKTOP_LLM_URL",
    "ENOUGH_VULKAN_ICD_DIRS", "ENOUGH_TOOLTIP_RE", "ENOUGH_REPO_URL",
)


# The environment as the *process* found it, captured at import time —
# before any fixture has run. `_still_pristine()` below is the difference
# between "the developer exported this" (isolate it) and "another fixture
# moved it on purpose" (leave it alone); see the docstring.
_ENV_AT_START = dict(os.environ)


def _still_pristine(var: str) -> bool:
    return os.environ.get(var) == _ENV_AT_START.get(var)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect `$HOME` and every `ENOUGH_*` state seam into `tmp_path`.

    Two layers, for the same reason `smoke_boot.build_env()` needs two:
    about half of enough's state has an env hook, and the other half —
    `~/enough/config/broker.json`, `openrouter.json`, `orchestrator.json`,
    `~/enough/.llama-server/server.pid` — is reachable only through `$HOME`.
    `ensure_skeleton()` registers the project it just built (home-plan §6)
    and half the suite calls it, so without this a test run files the
    developer's tmp dirs on their real home screen and can, on a bad day,
    write into `~/enough`.

    Autouse rather than opt-in precisely because that has to be true by
    default and not by remembering. Individual tests still set whichever
    seam they are actually asserting on — this fixture is function-scoped
    autouse, so it runs before their own fixtures and a test-local
    `monkeypatch.setenv` always wins.

    The one subtlety is `_still_pristine()`. A *session*-scoped fixture
    runs before this one and cannot be overridden by it, so blindly
    redirecting would silently undo a deliberate choice —
    `tests/test_convert_docling.py` pins `ENOUGH_WEIGHTS_DIR` at the real
    weights dir for the whole session because the docling models are the
    one thing those tests cannot fabricate. So a seam is redirected only
    while it still holds the value the *process* started with; anything
    already moved was moved for a reason this fixture cannot see.

    Nothing here creates `$HOME`. Every writer in enough builds its own
    parents, and a pre-made directory would collide with the several test
    modules that do `(tmp_path / "home").mkdir()` for themselves.
    """
    if _still_pristine("HOME"):
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

    state = tmp_path / "state"
    for var, rel in _STATE_SEAMS.items():
        if _still_pristine(var):
            monkeypatch.setenv(var, str(state / rel))

    # A read-only file, but "every ENOUGH_* points inside tmp_path" is a rule
    # worth being able to state without exceptions — and a copy also means a
    # test that rewrites the registry cannot corrupt the checkout.
    if _still_pristine("ENOUGH_MODELS_REGISTRY"):
        registry = state / "models.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / "defaults" / "models.json", registry)
        monkeypatch.setenv("ENOUGH_MODELS_REGISTRY", str(registry))

    # Nothing in the suite may reach huggingface.co. Port 1 is never
    # listening, so a stray download fails instantly and loudly instead of
    # quietly pulling gigabytes.
    if _still_pristine("ENOUGH_MODELS_URL_BASE"):
        monkeypatch.setenv("ENOUGH_MODELS_URL_BASE", "http://127.0.0.1:1/weights")

    for var in _BEHAVIOUR_SEAMS:
        if _still_pristine(var):
            monkeypatch.delenv(var, raising=False)


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
