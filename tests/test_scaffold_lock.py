"""The scaffold's lock and its findings (0.8, lane W3-E5; pins 6 and 11).

One lock for the whole scaffold: while it is closed every op from every source is refused (removing a module
included), except `accept_fix` from the person, applied to the quoted span and recorded on the finding. Unlocking
makes the next version as a new file with `parent`, and the locked file stays as it was. Findings are comments with
a fix attached, and they round-trip through the adapter to the state file's `# Findings`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from enough import composure as C
from enough import scaffolder as SC
from enough.composure import ComposureError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold_fixtures as F  # noqa: E402


def ops(path: Path, *op_list, source: str = "ui") -> C.OpsResult:
    return C.apply_ops(path, None, list(op_list), source=source)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


@pytest.fixture()
def deck(project: Path) -> Path:
    return F.deck(project)


def ask_box() -> str:
    return SC.module_id("the-ask-in-one-sentence")


def lock(path: Path) -> None:
    ops(path, {"op": "lock_scaffold", "empty": C.empty_boxes(C.load(path))})


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

def test_only_the_person_locks(deck: Path):
    for source in ("readvisor", "council", "enough"):
        with pytest.raises(ComposureError, match="the person's"):
            ops(deck, {"op": "lock_scaffold", "empty": C.empty_boxes(C.load(deck))}, source=source)
    assert not C.scaffold_locked(C.load(deck))


def test_empty_boxes_lock_only_once_they_are_named(deck: Path):
    empty = C.empty_boxes(C.load(deck))
    # the deck leaves its two pictures, two speaker boxes and the notes box empty
    assert SC.module_id("plot-picture") in empty and SC.module_id("notes-to-the-readvisor") in empty
    assert ask_box() not in empty
    with pytest.raises(ComposureError, match="still empty") as e:
        ops(deck, {"op": "lock_scaffold", "empty": empty[1:]})
    assert empty[0] in str(e.value)
    ops(deck, {"op": "lock_scaffold", "empty": empty})
    view = C.scaffold_view(C.load(deck))
    assert view["locked"]["by"] == "ui" and view["locked"]["empty"] == empty
    with pytest.raises(ComposureError, match="locked"):
        ops(deck, {"op": "lock_scaffold", "empty": empty})


def test_a_scaffold_with_every_box_written_locks_with_nothing_named(project: Path):
    path = F.build(project, "ten-slide-deck.md", "All written",
                   {k: "Words." for k in F.DECK_WORDS})
    empty = C.empty_boxes(C.load(path))
    for bid in empty:  # the pictures, speakers and notes: fill them in as the person
        m = C.load(path).module(bid)
        if m.kind == "graphic":
            ops(path, {"op": "update_module", "id": bid, "href": "pic.png"})
        else:
            ops(path, {"op": "set_page", "module": bid, "n": 1, "markdown": "Said."})
    assert C.empty_boxes(C.load(path)) == []
    ops(path, {"op": "lock_scaffold"})
    assert C.scaffold_locked(C.load(path))


def test_the_person_marks_a_box_written_and_the_readvisor_cannot(deck: Path):
    mid = SC.module_id("plot-headline")
    with pytest.raises(ComposureError, match="person's mark"):
        ops(deck, {"op": "update_module", "id": mid, "state": "written"}, source="readvisor")
    ops(deck, {"op": "update_module", "id": mid, "state": "written"})
    assert C.load(deck).module(mid).state == "written"


# ---------------------------------------------------------------------------
# While locked: every source, every op, refused; accept_fix the one exception
# ---------------------------------------------------------------------------

def every_op(comp: C.Composure) -> list[dict]:
    box, frame = ask_box(), C.scaffold_view(comp)["frames"][0]
    other = SC.module_id("cover-who")
    return [
        {"op": "add_module", "type": "scaffold-box", "frame": frame},
        {"op": "add_module", "type": "text"},
        {"op": "update_module", "id": box, "x": 10},
        {"op": "update_module", "id": box, "plec": "new plec"},
        {"op": "update_module", "id": box, "state": "written"},
        {"op": "remove_module", "id": other},
        {"op": "remove_module", "id": SC.module_id("plot-picture")},
        {"op": "set_page", "module": box, "n": 1, "markdown": "rewritten"},
        {"op": "add_page", "module": box, "markdown": "more"},
        {"op": "remove_page", "module": box, "n": 1},
        {"op": "file_page", "module": box, "n": 1},
        {"op": "add_strokes", "strokes": [{"points": [[0, 0], [1, 1]]}]},
        {"op": "remove_strokes", "ids": ["s1"]},
        {"op": "replace_strokes", "strokes": []},
        {"op": "set_meta", "title": "Another title"},
        {"op": "set_council", "council": None},
        {"op": "arrange", "ids": [box, other]},
        {"op": "make_scaffold"},
        {"op": "set_scaffold", "thing": "page"},
        {"op": "add_frame"},
        {"op": "reorder_frames", "order": list(reversed(C.scaffold_view(comp)["frames"]))},
        {"op": "move_to_frame", "id": box, "frame": frame},
        {"op": "lock_scaffold"},
    ]


@pytest.mark.parametrize("source", C.SOURCES)
def test_a_locked_scaffold_refuses_every_op_from_every_source(deck: Path, source: str):
    lock(deck)
    before = deck.read_bytes()
    comp = C.load(deck)
    named = {o["op"] for o in every_op(comp)}
    assert named | {"accept_fix"} == set(C.OP_NAMES)       # every op is tried
    for op in every_op(comp):
        with pytest.raises(ComposureError, match="locked"):
            ops(deck, op, source=source)
    assert deck.read_bytes() == before


def test_accept_fix_is_the_one_op_a_locked_scaffold_takes_and_only_from_the_person(deck: Path):
    lock(deck)
    fix = {"op": "accept_fix", "module": ask_box(), "quote": "comittee", "fix": "committee"}
    for source in ("readvisor", "council", "enough"):
        with pytest.raises(ComposureError, match="person's"):
            ops(deck, fix, source=source)
    r = ops(deck, fix)
    assert r.changed == [ask_box()]
    comp = C.load(deck)
    assert C.box_text(comp.module(ask_box())) == (
        "We ask the committee to lease the Mill Lane plot to us for five years.")
    assert C.scaffold_locked(comp)
    # a batch that sneaks anything else in beside it is refused whole
    with pytest.raises(ComposureError, match="locked"):
        ops(deck, {"op": "accept_fix", "module": ask_box(), "quote": "five", "fix": "ten"},
            {"op": "set_page", "module": ask_box(), "n": 1, "markdown": "x"})
    assert "five years" in C.box_text(C.load(deck).module(ask_box()))


def test_a_pan_still_saves_on_a_locked_scaffold(deck: Path):
    lock(deck)
    ops(deck, {"op": "set_meta", "view": {"x": 10, "y": 20, "zoom": 1.5}})
    assert C.load(deck).view["zoom"] == 1.5


def test_accept_fix_touches_the_quoted_span_and_nothing_else(deck: Path):
    mid = ask_box()
    ops(deck, {"op": "set_page", "module": mid, "n": 1,
               "markdown": "The comittee **met**. The comittee agreed."})
    lock(deck)
    with pytest.raises(ComposureError, match="2 places"):
        ops(deck, {"op": "accept_fix", "module": mid, "quote": "comittee", "fix": "committee"})
    with pytest.raises(ComposureError, match="crosses formatting"):
        ops(deck, {"op": "accept_fix", "module": mid, "quote": "comittee met", "fix": "x"})
    with pytest.raises(ComposureError, match="no longer in"):
        ops(deck, {"op": "accept_fix", "module": mid, "quote": "council", "fix": "x"})
    ops(deck, {"op": "accept_fix", "module": mid, "quote": "comittee", "suffix": " agreed",
               "fix": "committee"})
    rich = C.load(deck).module(mid).pages[0].rich
    assert rich == "<p>The comittee <strong>met</strong>. The committee agreed.</p>"


# ---------------------------------------------------------------------------
# Unlocking: a new file, the old one kept as it is
# ---------------------------------------------------------------------------

def test_unlock_makes_the_next_version_as_a_new_file(project: Path, deck: Path):
    C.add_finding(deck, {"box": ask_box(), "kind": "spelling", "quote": "comittee", "fix": "committee"})
    lock(deck)
    locked_bytes = deck.read_bytes()
    dest, comp = C.unlock_scaffold(deck, project)
    assert dest.name == "a-garden-on-mill-lane-v2.comp" and dest.parent == deck.parent
    assert deck.read_bytes() == locked_bytes and C.scaffold_locked(C.load(deck))
    view = C.scaffold_view(C.load(dest))
    assert view["locked"] is None and view["version"] == 2
    assert view["parent"] == "rness/io/composure/a-garden-on-mill-lane.comp"
    assert C.load(dest).rev == 0
    # the person's words, the findings and the plectrum come along
    assert C.box_text(C.load(dest).module(ask_box())).startswith("We ask the comittee")
    carried = C.list_findings(dest)
    assert [(f["id"], f["status"], f["version"]) for f in carried] == [("f1", "open", 1)]
    assert SC.plectrum_path(dest).read_text() == SC.plectrum_path(deck).read_text()
    # the new version is open for writing; the old refuses
    ops(dest, {"op": "set_page", "module": ask_box(), "n": 1, "markdown": "New words."})
    with pytest.raises(ComposureError, match="locked"):
        ops(deck, {"op": "set_page", "module": ask_box(), "n": 1, "markdown": "New words."})
    with pytest.raises(ComposureError, match="not locked"):
        C.unlock_scaffold(dest, project)
    # the third version is named from the second, and nothing is written over
    lock(dest)
    dest3, _ = C.unlock_scaffold(dest, project)
    assert dest3.name == "a-garden-on-mill-lane-v3.comp"
    assert C.scaffold_view(C.load(dest3))["parent"] == "rness/io/composure/a-garden-on-mill-lane-v2.comp"
    dest3b, _ = C.unlock_scaffold(deck, project)
    assert dest3b.name == "a-garden-on-mill-lane-v2-2.comp"


# ---------------------------------------------------------------------------
# Findings: comments with a fix
# ---------------------------------------------------------------------------

def test_a_finding_is_a_comment_with_a_fix(deck: Path):
    entry = C.add_finding(deck, {"box": ask_box(), "kind": "spelling", "quote": "comittee",
                                 "fix": "committee", "why": "FEED does not know this word"})
    assert entry["by"] == "check" and entry["anchor"]["type"] == "quote"
    assert entry["anchor"]["module"] == ask_box() and entry["state"] == "anchored"
    f = entry["finding"]
    assert (f["id"], f["kind"], f["status"], f["version"], f["fix"]) == ("f1", "spelling", "open", 1, "committee")
    assert "comittee" in entry["body"] and "committee" in entry["body"]
    second = C.add_finding(deck, {"box": ask_box(), "kind": "truth", "quote": "", "status": "cannot be checked",
                                  "fix": "ignored", "why": "about the group itself"})
    assert second["finding"]["id"] == "f2" and second["finding"]["fix"] is None
    assert second["anchor"]["type"] == "module" and second["state"] == "module"
    with pytest.raises(ComposureError, match="finding kind"):
        C.add_finding(deck, {"box": ask_box(), "kind": "claim"})
    with pytest.raises(ComposureError, match="record"):
        C.delete_comment(deck, entry["id"])


def test_accepting_applies_the_fix_as_the_person_and_records_it(deck: Path):
    f1 = C.add_finding(deck, {"box": ask_box(), "kind": "spelling", "quote": "comittee", "fix": "committee"})
    f2 = C.add_finding(deck, {"box": ask_box(), "kind": "grammar", "quote": "to us", "fix": "to us,"})
    f3 = C.add_finding(deck, {"box": ask_box(), "kind": "truth", "quote": "five years",
                              "status": "cannot be checked"})
    lock(deck)
    finding, result = C.answer_finding(deck, f1["finding"]["id"], "accept")
    assert finding["status"] == "accepted" and finding["answered_at"] and finding["rev"] == result.rev
    assert "committee" in C.box_text(C.load(deck).module(ask_box()))
    declined, none = C.answer_finding(deck, f2["finding"]["id"], "decline")
    assert declined["status"] == "declined" and none is None
    assert "to us for" in C.box_text(C.load(deck).module(ask_box()))
    with pytest.raises(ComposureError, match="final"):
        C.answer_finding(deck, f3["finding"]["id"], "decline")
    with pytest.raises(ComposureError, match="accepted already"):
        C.answer_finding(deck, f1["finding"]["id"], "accept")
    with pytest.raises(KeyError):
        C.answer_finding(deck, "f99", "decline")
    doc = C.load_comments(deck)
    by_id = {c["finding"]["id"]: c for c in doc["comments"]}
    assert by_id["f1"]["resolved"] and by_id["f1"]["anchor"]["quote"] == "committee"
    assert by_id["f2"]["resolved"] and not by_id["f3"]["resolved"]
    assert C.scaffold_locked(C.load(deck))


def test_a_check_lands_once_and_a_second_run_replaces_only_what_was_open(deck: Path):
    first = C.record_check(deck, [
        {"box": ask_box(), "kind": "spelling", "quote": "comittee", "fix": "committee"},
        {"box": ask_box(), "kind": "truth", "quote": "five years", "status": "cannot be checked"},
    ], {"at": "2026-11-18T21:41:12Z", "version": 1, "mode": "model"})
    assert first["added"] == ["f1", "f2"]
    C.answer_finding(deck, "f1", "decline")
    again = C.record_check(deck, [
        {"box": ask_box(), "kind": "spelling", "quote": "comittee", "fix": "committee"},
        {"box": ask_box(), "kind": "truth", "quote": "five years", "status": "cannot be checked"},
        {"box": ask_box(), "kind": "grammar", "quote": "to us", "fix": "to us,"},
    ], {"at": "2026-11-18T22:00:00Z", "version": 1, "mode": "model"})
    assert again["added"] == ["f3"]
    statuses = {f["id"]: f["status"] for f in C.list_findings(deck)}
    assert statuses == {"f1": "declined", "f2": "cannot be checked", "f3": "open"}
    third = C.record_check(deck, [], {"at": "2026-11-18T22:10:00Z", "version": 1, "mode": "rules"})
    assert [f["id"] for f in third["findings"]] == ["f1", "f2"]
    assert C.load_comments(deck)["check"]["at"] == "2026-11-18T22:10:00Z"
    # an id is never reused
    assert C.add_finding(deck, {"box": ask_box(), "kind": "grammar"})["finding"]["id"] == "f4"


def test_findings_round_trip_through_the_state_file(deck: Path):
    C.record_check(deck, [
        {"box": ask_box(), "kind": "spelling", "quote": "comittee", "fix": "committee",
         "why": "FEED does not know this word"},
        {"box": ask_box(), "kind": "truth", "quote": "", "status": "cannot be checked",
         "why": "about the group itself"},
        {"box": SC.module_id("the-total"), "kind": "grammar", "quote": "Four", "prefix": "", "suffix": " thousand",
         "fix": "Four\\n", "why": "a backslash and a \"quote\""},
    ], {"at": "2026-11-18T21:41:12Z", "version": 1, "mode": "model"})
    C.answer_finding(deck, "f1", "accept")
    comp = C.load(deck)
    plectrum = SC.loads(SC.plectrum_path(deck).read_text())
    state = SC.state_from_composure(comp, plectrum, C.load_comments(deck))
    assert state.meta["checked"] == "2026-11-18T21:41:12Z"
    assert [(f["id"], f["box"], f["status"]) for f in state.findings] == [
        ("f1", "the-ask-in-one-sentence", "accepted"), ("f2", "the-ask-in-one-sentence", "cannot be checked"),
        ("f3", "the-total", "open")]
    text = SC.state_module().dumps(state)
    assert "# Findings" in text and "kind: truth" in text
    back = SC.loads(text)
    got = SC.findings_from_state(back, comp)
    want = [{k: f[k] for k in ("id", "box", "kind", "quote", "prefix", "suffix", "fix", "why", "status", "version")}
            for f in C.list_findings(deck)]
    assert got == want
