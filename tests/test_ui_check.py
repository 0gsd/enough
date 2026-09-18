"""The browser harness's own tests.

Two halves, and the split is the point.

**Always on** — the pure-Python parts of `scripts/uicheck/`: the rect
arithmetic and the is-this-a-finding rules (`geometry.py`), the baseline
key (`findings.py`), the Chrome locator order (`cdp.find_chrome`), and the
screen registry's own invariants. None of this needs a browser, so all of it
runs in CI on both platforms, on every `pytest -q`. That is deliberate: the
rules that decide what counts as a layout bug are exactly the code you do
NOT want to be able to change without a test noticing.

**Opt-in** — the real thing. `ENOUGH_UI_CHECK=1 uv run pytest
tests/test_ui_check.py` runs the quick matrix end to end (Chrome, two
scratch servers, the whole sweep). It is off by default because it takes
minutes and needs a browser; `scripts/precommit.py` runs the script
directly rather than through pytest, so nothing is lost by the skip.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from uicheck import geometry, screens                             # noqa: E402
from uicheck.cdp import MAC_CANDIDATES, PATH_CANDIDATES, find_chrome  # noqa: E402
from uicheck.findings import (SEVERITY, Finding, FindingSet,      # noqa: E402
                              from_measurement)


# ---------------------------------------------------------------------------
# geometry: rect arithmetic
# ---------------------------------------------------------------------------

def R(x, y, w, h) -> geometry.Rect:
    return geometry.Rect(x, y, w, h)


def test_intersection_is_signed_so_callers_can_see_the_gap():
    ox, oy = geometry.intersection(R(0, 0, 10, 10), R(20, 0, 10, 10))
    assert ox == -10 and oy == 10


@pytest.mark.parametrize("a,b,expected", [
    # Plain overlap, comfortably past the slop on both axes.
    (R(0, 0, 100, 40), R(50, 10, 100, 40), True),
    # Sharing one pixel of border is touching, not overlapping — this is the
    # case that would otherwise flood the report from every adjacent chip.
    (R(0, 0, 100, 40), R(99, 0, 100, 40), False),
    # 2px is the slop boundary itself: strictly greater, so 2 is not enough.
    (R(0, 0, 100, 40), R(98, 0, 100, 40), False),
    (R(0, 0, 100, 40), R(97, 0, 100, 40), True),
    # Overlapping on one axis only is two things side by side.
    (R(0, 0, 100, 40), R(50, 60, 100, 40), False),
])
def test_overlaps_needs_both_axes_and_more_than_the_slop(a, b, expected):
    assert geometry.overlaps(a, b) is expected


def test_contains_tolerates_a_pixel_of_rounding():
    outer, inner = R(0, 0, 100, 100), R(-0.5, 0.5, 100, 99)
    assert geometry.contains(outer, inner)
    assert not geometry.contains(outer, R(-5, 0, 100, 100))


def test_inside_viewport_and_tiny():
    assert geometry.inside_viewport(R(0, 0, 100, 100), 1024, 640)
    assert not geometry.inside_viewport(R(1000, 0, 100, 100), 1024, 640)
    assert geometry.is_tiny(R(0, 0, 15, 40))
    assert geometry.is_tiny(R(0, 0, 40, 15))
    assert not geometry.is_tiny(R(0, 0, 16, 16))


# ---------------------------------------------------------------------------
# geometry: the judgements
# ---------------------------------------------------------------------------

def item(path, rect, *, layer="page", hit_self=True, covered_by=None,
         covered_layer=None, in_view=True, scroller=None, text="",
         out_of_scroller=False):
    return {"path": path, "text": text, "rect": {"x": rect.x, "y": rect.y,
                                                 "w": rect.w, "h": rect.h},
            "inView": in_view, "hitSelf": hit_self, "coveredBy": covered_by,
            "coveredByLayer": covered_layer, "layer": layer,
            "inScroller": scroller, "outOfScroller": out_of_scroller}


def test_overlap_needs_the_hit_test_to_agree():
    """Rects alone never make a finding — someone has to lose a click."""
    a = item("#a", R(0, 0, 100, 40))
    b = item("#b", R(50, 0, 100, 40))
    assert geometry.find_overlaps([a, b]) == []

    a_lost = item("#a", R(0, 0, 100, 40), hit_self=False, covered_by="#b",
                  covered_layer="page")
    found = geometry.find_overlaps([a_lost, b])
    assert len(found) == 1
    assert found[0]["hidden"] == "#a" and found[0]["overlapW"] == 50


def test_a_modal_covering_the_page_is_the_design_not_a_finding():
    """The rule that keeps the report readable: cross-layer coverage is how
    a stacking UI is supposed to work."""
    behind = item("#broker-btn", R(0, 0, 100, 40), layer="page",
                  hit_self=False, covered_by="#ui-modal>div.modal-backdrop",
                  covered_layer="ui-modal")
    assert geometry.find_covered([behind]) == []

    sibling = item("#broker-btn", R(0, 0, 100, 40), layer="page",
                   hit_self=False, covered_by="#ui-btn", covered_layer="page")
    assert [f["path"] for f in geometry.find_covered([sibling])] == ["#broker-btn"]


def test_a_modal_backdrop_is_never_a_finding():
    """The click-outside layer is meant to be behind the panel."""
    backdrop = item("#ui-modal>div.modal-backdrop", R(0, 0, 900, 600),
                    layer="ui-modal", hit_self=False,
                    covered_by="#ui-modal>div.modal-panel",
                    covered_layer="ui-modal")
    panel = item("#ui-modal>div.modal-panel", R(100, 100, 400, 300),
                 layer="ui-modal")
    assert geometry.find_covered([backdrop, panel]) == []
    assert geometry.find_overlaps([backdrop, panel]) == []


def test_containment_is_not_overlap():
    outer = item("#panel", R(0, 0, 200, 200), hit_self=False,
                 covered_by="#chip", covered_layer="page")
    inner = item("#chip", R(10, 10, 40, 40))
    assert geometry.find_overlaps([outer, inner]) == []


def test_covered_ignores_a_control_that_is_merely_scrolled_past():
    """A height-capped modal whose body scrolls is not a modal with 12 dead
    controls in it. `find_offscreen` has always known this; P6c taught the
    two coverage rules the same thing, after capping the model modal made
    `#apply-model-btn` report as "covered by the modal foot"."""
    below = item("#apply-model-btn", R(100, 700, 120, 28),
                 scroller="#model-modal>div.modal-panel>div.modal-body",
                 out_of_scroller=True, hit_self=False,
                 covered_by="#model-modal>div.modal-panel>div.modal-foot",
                 covered_layer="page")
    assert geometry.scrolled_past(below)
    assert geometry.find_covered([below]) == []

    # …but a control covered by a NEIGHBOUR it shares the scroller with is
    # still a finding: it is on screen, and the click still goes elsewhere.
    inside = item("#ctx-input", R(100, 200, 120, 28), scroller="#body",
                  hit_self=False, covered_by="#sibling", covered_layer="page")
    assert not geometry.scrolled_past(inside)
    assert [f["path"] for f in geometry.find_covered([inside])] == ["#ctx-input"]


def test_overlap_ignores_a_pair_where_the_loser_is_scrolled_past():
    scrolled = item("#a", R(0, 0, 100, 40), scroller="#body",
                    out_of_scroller=True, hit_self=False, covered_by="#b",
                    covered_layer="page")
    other = item("#b", R(50, 0, 100, 40))
    assert geometry.find_overlaps([scrolled, other]) == []


def test_offscreen_ignores_anything_inside_a_scroller():
    below = item("#row", R(0, 900, 100, 40), scroller="#tree")
    loose = item("#stray", R(0, 900, 100, 40))
    paths = [f["path"] for f in geometry.find_offscreen([below, loose], 1024, 640)]
    assert paths == ["#stray"]


def test_tiny_skips_targets_the_user_cannot_reach_right_now():
    reachable = item("#x", R(0, 0, 12, 12))
    behind = item("#y", R(0, 0, 12, 12), hit_self=False,
                  covered_by="#ui-modal", covered_layer="ui-modal")
    assert [f["path"] for f in geometry.find_tiny([reachable, behind])] == ["#x"]


# ---------------------------------------------------------------------------
# findings: the baseline key
# ---------------------------------------------------------------------------

def test_the_key_names_elements_not_pixels_or_viewports():
    """The baseline has to survive a re-layout and die with the element."""
    f = Finding("read-full", "overlap", "#a", "detail", other="#b")
    assert f.key == "read-full | overlap | #a | #b"
    same_bug_elsewhere = Finding("read-full", "overlap", "#a",
                                 "a completely different wording", other="#b")
    assert same_bug_elsewhere.key == f.key


def test_one_key_accumulates_every_place_it_was_seen():
    fs = FindingSet()
    fs.add(Finding("s", "tiny", "#x", "12x12"), viewport="1024x640@1", lang="en")
    fs.add(Finding("s", "tiny", "#x", "12x12"), viewport="1024x640@1", lang="ja")
    fs.add(Finding("s", "tiny", "#x", "12x12"), viewport="3440x1440@1", lang="en")
    assert len(fs) == 1
    assert len(next(iter(fs)).seen) == 3


def test_findings_sort_worst_first():
    fs = FindingSet()
    for kind in ("tiny", "covered", "clipped"):
        fs.add(Finding("s", kind, f"#{kind}", ""), viewport="v", lang="en")
    assert [f.kind for f in fs] == ["covered", "clipped", "tiny"]
    assert SEVERITY.index("covered") < SEVERITY.index("tiny")


def test_from_measurement_runs_every_rule():
    data = {
        "viewport": {"w": 1024, "h": 640},
        "items": [
            item("#a", R(0, 0, 100, 40), hit_self=False, covered_by="#b",
                 covered_layer="page"),
            item("#b", R(50, 0, 100, 40)),
            item("#small", R(0, 300, 10, 10)),
            item("#gone", R(0, 900, 40, 40)),
        ],
        "clipped": [{"path": "#t", "text": "hello", "kind": "clipped",
                     "overW": 20, "overH": 0}],
    }
    kinds = sorted({f.kind for f in from_measurement("screen", data)})
    assert kinds == ["clipped", "covered", "offscreen", "overlap", "tiny"]


# ---------------------------------------------------------------------------
# cdp: the Chrome locator
# ---------------------------------------------------------------------------

def test_locator_order_env_then_bundles_then_path():
    """A fake filesystem, so the assertion is about the ORDER and not about
    what happens to be installed on the machine running the tests."""
    on_disk = {MAC_CANDIDATES[1], MAC_CANDIDATES[0]}
    exists = on_disk.__contains__
    which = {"chromium": "/usr/bin/chromium"}.get

    # Chrome wins over Chromium when both bundles are present.
    assert find_chrome(env={}, exists=exists, which=which) == MAC_CANDIDATES[0]
    # PATH is the last resort, not the first.
    assert find_chrome(env={}, exists=lambda p: False,
                       which=which) == "/usr/bin/chromium"
    # The override beats everything…
    assert find_chrome(env={"ENOUGH_CHROME": "/opt/my-chrome"},
                       exists=lambda p: True, which=which) == "/opt/my-chrome"
    # …but an override that does not exist is a misconfiguration, and
    # falling through to a different browser would hide it.
    assert find_chrome(env={"ENOUGH_CHROME": "/opt/nope"},
                       exists=exists, which=which) is None
    # Nothing anywhere: the caller SKIPs rather than fails.
    assert find_chrome(env={}, exists=lambda p: False,
                       which=lambda n: None) is None


def test_path_candidates_cover_the_three_linux_names():
    assert set(PATH_CANDIDATES) == {"google-chrome", "chromium", "chromium-browser"}


# ---------------------------------------------------------------------------
# the screen registry's own invariants
# ---------------------------------------------------------------------------

def test_screen_names_are_unique_and_modes_are_known():
    names = [s.name for s in screens.ALL_SCREENS]
    assert len(names) == len(set(names)), "a duplicate screen name would make "\
                                          "the baseline ambiguous"
    assert {s.mode for s in screens.ALL_SCREENS} == {"project", "home"}


def test_every_step_verb_is_one_the_driver_implements():
    from uicheck.driver import Driver

    # `eval_await` joined the vocabulary with the composure round: an entry
    # point that returns a promise and settles on its own (compOpenNew) has
    # to be awaited, or the step after it runs against the document the
    # open is about to replace.
    known = {"click", "key", "eval", "eval_await",
             "wait_for", "wait_gone", "wait_idle"}
    for screen in screens.ALL_SCREENS:
        for verb, _arg in tuple(screen.setup) + tuple(screen.teardown):
            assert verb in known, f"{screen.name} uses unknown step {verb!r}"
    assert callable(Driver.run_steps)


def test_the_matrix_covers_the_extremes_and_quick_is_a_subset():
    names = {v.name for v in screens.VIEWPORTS}
    assert "1024x640@1" in names, "the smallest supported laptop"
    assert "3440x1440@1" in names, "the 21:9 ultrawide"
    assert "1080x1920@1" in names, "a portrait orientation"
    assert set(screens.QUICK_VIEWPORTS) <= set(screens.VIEWPORTS)
    assert set(screens.QUICK_LANGUAGES) <= set(screens.LANGUAGES)
    assert len(screens.LANGUAGES) == 6


def test_tauri_minimum_size_joins_the_matrix_when_one_is_declared():
    assert screens.tauri_min_viewport({"app": {"windows": [{"width": 1200}]}}) is None
    vp = screens.tauri_min_viewport(
        {"app": {"windows": [{"minWidth": 900, "minHeight": 600}]}})
    assert (vp.w, vp.h) == (900, 600)


def test_todays_tauri_conf_is_read_without_raising():
    conf = REPO / "desktop" / "src-tauri" / "tauri.conf.json"
    if not conf.is_file():
        pytest.skip("no tauri config in this checkout")
    screens.tauri_min_viewport(json.loads(conf.read_text(encoding="utf-8")))


def test_baseline_is_committed_and_readable():
    from uicheck.findings import BASELINE_PATH, load_baseline

    assert BASELINE_PATH.is_file(), (
        "scripts/uicheck/baseline.json is committed on purpose — regenerate "
        "it with `uv run python scripts/ui_check.py --update-baseline`")
    accepted = load_baseline()
    for key in accepted:
        assert key.count(" | ") in (2, 3), f"malformed baseline key: {key!r}"


# ---------------------------------------------------------------------------
# the real thing, opt-in
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("ENOUGH_UI_CHECK") != "1",
                    reason="set ENOUGH_UI_CHECK=1 to run the quick browser "
                           "matrix (minutes, needs Chrome); scripts/precommit.py "
                           "runs the script directly instead")
def test_quick_matrix_is_green():
    proc = subprocess.run(
        [sys.executable, "scripts/ui_check.py", "--quick", "--no-shots"],
        cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
