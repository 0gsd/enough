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

# Every `ENOUGH_*` seam, from the one list `scripts/smoke_boot.py`'s
# `build_env()` reads too (that script is the other half of the same rule, for
# the subprocess servers the pre-commit suite boots): the path seams, each
# under tmp_path (the registry a copy of defaults/models.json, so a test that
# rewrites it cannot corrupt the checkout); the fixed ones (no test may reach
# huggingface.co or cosmoes.org, and the specifications' launch check is off;
# tests of the check or of a download set them for themselves); and the
# behaviour seams, which must be *absent*, not redirected — a developer who
# happens to export one would otherwise get a different run than CI, and the
# tests that need one (the desktop-shutdown gate, the llama-server lookup
# ladder) set it themselves. `tests/test_seams.py` keeps the list whole.
from enough import seams as _seams  # noqa: E402

_STATE_SEAMS = _seams.PATH_SEAMS
_FIXED_SEAMS = _seams.FIXED_SEAMS
_BEHAVIOUR_SEAMS = _seams.BEHAVIOUR_SEAMS


# The environment as the *process* found it, captured at import time —
# before any fixture has run — and then moved onto the session floor's values
# by `session_floor` below. `_still_pristine()` is the difference between "the
# developer exported this, or the floor set it" (isolate it per test) and
# "another fixture moved it on purpose" (leave it alone); see the docstring.
_GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX")

_ENV_AT_START = dict(os.environ)


def _still_pristine(var: str) -> bool:
    return os.environ.get(var) == _ENV_AT_START.get(var)


def _redirect_home_bound_paths(mp: pytest.MonkeyPatch, home: Path) -> None:
    """Three paths are bound to `Path.home()` when their modules import, which happens at collection, before any
    fixture moves `$HOME`: without these the broker's, the cloud slot's and the orchestrator's config files are the
    developer's real ones (wave 2 of 0.5.0: `~/enough/config/broker.json` was found rewritten during a round of
    test runs)."""
    from enough import broker as _broker, cloud as _cloud, server as _server
    config = home / "enough" / "config"
    mp.setattr(_broker, "CONFIG_PATH", config / "broker.json")
    mp.setattr(_cloud, "CONFIG_PATH", config / "openrouter.json")
    mp.setattr(_server, "ORCHESTRATOR_CONFIG", config / "orchestrator.json")


@pytest.fixture(scope="session", autouse=True)
def session_floor(tmp_path_factory: pytest.TempPathFactory):
    """The floor under every fixture: `$HOME` and every seam pointed at one session scratch folder.

    `isolated_state` below is function-scoped, so a module- or session-scoped fixture is made before it and saw the
    real `$HOME` and whatever the developer had exported (test_docoes' module fixture read the real ~/enough/specs
    the day 0.6.0 went live). This one is session-scoped and autouse in the root conftest, so pytest makes it before
    any other fixture of any scope, and nothing a wider fixture reads or writes can be the developer's.

    It then makes its own values the baseline `_still_pristine()` compares against, so the per-test redirection
    still happens under it, and a wider fixture that moves a seam on purpose (test_convert_docling's real weights
    dir) is still left alone. Values read at import time, during collection, are before any fixture and are not
    its business: test_convert_docling reads the real weights dir that way, deliberately."""
    floor = tmp_path_factory.mktemp("session-floor")
    mp = pytest.MonkeyPatch()
    moved = {"HOME": str(floor / "home")}
    moved.update(_seams.scratch_values(floor / "state"))
    _seams.fill_registry(floor / "state")
    before = {var: _ENV_AT_START.get(var) for var in (*moved, *_BEHAVIOUR_SEAMS)}
    for var, value in moved.items():
        mp.setenv(var, value)
        _ENV_AT_START[var] = value
    for var in _BEHAVIOUR_SEAMS:
        mp.delenv(var, raising=False)
        _ENV_AT_START.pop(var, None)
    _redirect_home_bound_paths(mp, floor / "home")
    try:
        yield floor
    finally:
        mp.undo()
        for var, value in before.items():
            if value is None:
                _ENV_AT_START.pop(var, None)
            else:
                _ENV_AT_START[var] = value


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
        # The paths bound to `Path.home()` at import, moved with it, in every test that does not patch them itself.
        _redirect_home_bound_paths(monkeypatch, tmp_path / "home")

    state = tmp_path / "state"
    for var, value in _seams.scratch_values(state).items():
        if _still_pristine(var):
            monkeypatch.setenv(var, value)
            if var == "ENOUGH_MODELS_REGISTRY":
                _seams.fill_registry(state)

    for var in _BEHAVIOUR_SEAMS:
        if _still_pristine(var):
            monkeypatch.delenv(var, raising=False)

    # Git's own location seams. Git sets them for a hook it runs (GIT_INDEX_FILE always, GIT_DIR in a linked
    # worktree), and the commit hook runs this suite: inherited, they point every `git` a test runs in a scratch
    # folder at the checkout being committed, so "the miniature is not a checkout" read the checkout's commit.
    for var in _GIT_LOCATION:
        monkeypatch.delenv(var, raising=False)
    # The keychain (0.7): a listing's private key and Connect's token live in the OS keychain, and no test may read
    # or write the real one. `allograph_registry.KEYCHAIN` is the one seam every use of it goes through.
    from enough import allograph_registry as _allograph_registry
    monkeypatch.setattr(_allograph_registry, "KEYCHAIN", _allograph_registry.MemoryKeychain())
    monkeypatch.setattr(_allograph_registry, "_PENDING", {})
    monkeypatch.setattr(_allograph_registry, "_SESSIONS", {})


@pytest.fixture(autouse=True)
def unwired_pal_seam(monkeypatch: pytest.MonkeyPatch):
    """Every test starts with `council.PAL_CALL` unwired, and gets back whatever was there after.

    `create_app` wires that module global to the project it serves (`council_api.build_router`) and nothing
    unwires it: in the app that is one process, one project, but in the suite the binding outlived the test that
    made it — `tests/test_pal.py`'s `client` fixture left it bound to a deleted tmp project, and
    `tests/test_council_pal.py::test_create_app_wires_pal_call_to_the_pal_lanes_one_shot_call` (which checks
    that `create_app` is what wires it) failed whenever test_pal ran first in the same process."""
    from enough import council as _council
    monkeypatch.setattr(_council, "PAL_CALL", _council._pal_not_wired)


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
