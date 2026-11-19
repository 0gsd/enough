"""The page's card of an authored fabulac (0.8, lane W4-FP: pins section 4; survey `v080-survey-fabulac-first.md`
section 6): what the page sends and what the tree tells it.

- Every POST the page makes to `/api/fabulac/*` goes through one function that sends the promise header
  (`enough/api_promise.py`), and every route it posts to is a gated route of the promise.
- The tree marks an authored fabulac (`data-fab-authored`) and the folder it entailed (`data-fab-twin`), so the
  folder's menu offers entail and run, never "build its fabulac…" (the twin guard); a fabulac decompiled from a
  folder, and its folder, are marked neither.
- Nothing on the page posts a run of a cshort: the sandbox's routes are called from the authored card alone.

The card's behaviour in a browser is the uicheck stage's (`fabulac-*` screens, the `fabulac-first` scenario).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from enough import api_promise as P
from enough import fabulac_first as FF
from enough import server as S

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    """The text of one function of the page's script."""
    m = re.search(r"\n    (?:async )?function " + re.escape(name) + r"\(", HTML)
    assert m, name
    end = HTML.index("\n    }\n", m.end())
    return HTML[m.start():end]


def test_every_fabulac_post_sends_the_promise_header():
    post = _fn("fapPost")
    assert "method: 'POST'" in post and "[FAP_HEADER]: '1'" in post
    assert f"const FAP_HEADER = '{P.HEADER}';" in HTML and P.VERSION == 1
    # no other way of posting reaches the fabulac routes
    assert not re.search(r"canonPost\(\s*'/api/fabulac/", HTML)
    assert not re.search(r"fetch\(\s*'/api/fabulac/", HTML)
    posted = set(re.findall(r"fapPost\(\s*'(/api/fabulac/[a-z-]+)'", HTML))
    # the run's two routes are chosen by a ternary
    posted |= set(re.findall(r"'(/api/fabulac/(?:run|test|keep|let-go))'", HTML))
    gated = {r.path for r in P.ROUTES if r.gated}
    assert posted and posted <= gated, posted - gated
    assert {"/api/fabulac/begin", "/api/fabulac/answer", "/api/fabulac/add", "/api/fabulac/entail",
            "/api/fabulac/keep", "/api/fabulac/let-go", "/api/fabulac/take-back", "/api/fabulac/test",
            "/api/fabulac/run", "/api/fabulac/stop", "/api/fabulac/head"} <= posted
    # and the reads it makes are the promise's reads, which need no header
    read = set(re.findall(r"canonJSON\('(/api/fabulac/[a-z-]+)\?", HTML)) | set(
        re.findall(r"canonJSON\('(/api/fabulac/[a-z-]+)'\)", HTML))
    assert read and read <= {r.path for r in P.ROUTES if not r.gated}, read


def test_the_sandbox_is_called_from_the_authored_card_alone():
    """A cshort (code the person did not author) is read, never run: the only callers of test and run are the
    authored card's, and the cshort viewer and its menu items offer nothing that runs."""
    callers = [m.start() for m in re.finditer(r"/api/fabulac/(?:test|run)'", HTML)]
    run_go = _fn("fapRunGo")
    assert callers and all(HTML.find(run_go) <= c < HTML.find(run_go) + len(run_go) for c in callers)
    viewer = _fn("fabViewPaint")
    assert "data-fap" not in viewer and "/api/fabulac/" not in viewer
    menu = _fn("fabMenuItems")
    cshort_line = next(ln for ln in menu.splitlines() if "FAB_CSHORT_RE.test(p)" in ln)
    assert "fab-view" in cshort_line and "fap-" not in cshort_line


def test_the_menu_keeps_the_twin_guard():
    menu = _fn("fabMenuItems")
    guard = menu[menu.index("target.fabTwin"):menu.index("fab.menu.build")]
    assert "fap-entail" in guard and "fap-run" in guard and "fap-moved" in guard and "return" in guard
    assert "fabTwin: li.dataset.fabTwin" in HTML and "fabAuthored: li.dataset.fabAuthored === '1'" in HTML


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = (tmp_path / "project").resolve()
    (proj / "made").mkdir(parents=True)
    FF.begin(proj, "made/tally", starter="tool", licence="MIT", by="Ada")
    (proj / "made" / "tally").mkdir()                     # the folder its entailment writes
    # a fabulac decompiled from a folder, beside its folder
    src = REPO / "tests" / "fixtures" / "fabula" / "tally.fabulac.cosm"
    (proj / "read").mkdir()
    (proj / "read" / "tool").mkdir()
    (proj / "read" / "tool.fabulac.cosm").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return proj


def _li(html: str, path: str) -> str:
    m = re.search(r'<li [^>]*data-path="' + re.escape(path) + r'"[^>]*>', html)
    assert m, path
    return m.group(0)


def test_the_tree_marks_an_authored_fabulac_and_its_entailment(project: Path):
    html = S._tree_to_html(S.build_file_tree(project))
    assert 'data-fab-authored="1"' in _li(html, "made/tally.fabulac.cosm")
    assert 'data-fab-twin="made/tally.fabulac.cosm"' in _li(html, "made/tally")
    assert "data-fab-authored" not in _li(html, "read/tool.fabulac.cosm")
    assert "data-fab-twin" not in _li(html, "read/tool")
    # read once per change of the file
    fab = project / "made" / "tally.fabulac.cosm"
    assert S._AUTHORED_SEEN[str(fab)][2] is True
    text = fab.read_text(encoding="utf-8").replace("kind: authored", "kind: folder", 1)
    fab.write_text(text + "\n", encoding="utf-8")
    html = S._tree_to_html(S.build_file_tree(project))
    assert "data-fab-twin" not in _li(html, "made/tally")
