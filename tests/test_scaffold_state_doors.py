"""The scaffold's two doors in enough (0.9, lane S3): its state out as the skill's one state file, and a state
file's layout and words in, as the person's own ops.

- Out: `GET /api/composure/scaffold/state` and `POST …/state/out` give exactly the bytes the skill's
  `scaffold_state.py` writes from the same scaffold (one writer, loaded from `defaults/` by `scaffolder.state_module`),
  locked or open; `out` writes a new file beside the composure and never one written over.
- In: `POST …/state/in` reads the person's file with the one parser and refuses what does not parse, a plectrum, a
  state for another thing than the scaffold holds, and a locked scaffold. It previews first (how many boxes match,
  how many are new, how many of the scaffold's boxes it has no words for), never writes over words already in a box
  without naming the boxes and being told which, applies as one batch whose source the server sets (`ui`), and hands
  the page one undo step. A locked state comes in locked, with its findings (`state.md`: nothing lost).
- The three small fixes from the trials: the lock's empty list leaves out the notes box; the check's done toast says
  a count of findings, not their ids.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import composure as C
from enough import scaffolder as SC
from enough.server import create_app

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold_fixtures as F  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "enough" / "static" / "index.html"
DECK_REL = "rness/io/composure/a-garden-on-mill-lane.comp"
FRESH_REL = "rness/io/composure/fresh.comp"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"),
                     ("ENOUGH_CANON_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    return proj


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app, headers={"X-Enough-Api": "1"}) as c:
        yield c


@pytest.fixture()
def deck(project: Path) -> Path:
    path = F.deck(project)
    assert path == project / DECK_REL
    return path


def _state(client: TestClient, rel: str) -> str:
    r = client.get("/api/composure/scaffold/state", params={"path": rel})
    assert r.status_code == 200, r.text
    return r.json()["text"]


def _bring(client: TestClient, rel: str, text: str, **extra) -> tuple[int, dict]:
    r = client.post("/api/composure/scaffold/state/in", json={"path": rel, "text": text, **extra})
    return r.status_code, r.json()


def _fresh(client: TestClient, title: str = "Fresh") -> None:
    r = client.post("/api/composure/ops", json={
        "path": FRESH_REL, "base_rev": 0, "create": True, "form": "scaffold", "title": title,
        "ops": [{"op": "set_meta", "title": title}]})
    assert r.status_code == 200, r.text


def _layout_and_words(model) -> dict:
    """What a scaffold is, for comparing two of them: the front matter, every frame and every box with its words.
    `plec_by` is left out: an undo or a redo sends plecs through the person's door, which makes them the person's."""
    data = SC.state_module().to_dict(model)
    meta = {k: v for k, v in data["meta"].items() if k not in ("locked", "checked")}
    frames = []
    for f in data["frames"]:
        boxes = [{k: v for k, v in b.items() if k != "plec_by"} for b in f["boxes"]]
        frames.append({**{k: v for k, v in f.items() if k != "boxes"}, "boxes": boxes})
    return {"meta": meta, "frames": frames}


def _lock(path: Path) -> None:
    C.apply_ops(path, None, [{"op": "lock_scaffold", "empty": C.empty_boxes(C.load(path))}], source="ui")


# ---------------------------------------------------------------------------
# State out: one writer
# ---------------------------------------------------------------------------

def test_the_state_out_is_the_skills_own_writer_byte_for_byte(client: TestClient, deck: Path, project: Path):
    S = SC.state_module()
    text = _state(client, DECK_REL)
    assert text.startswith("---\nscaffold: 1\n")
    # the skill's writer, from the same scaffold, makes the same bytes; and they read and write back unchanged
    comp = C.load(deck)
    plectrum = SC.loads(SC.plectrum_path(deck).read_text(encoding="utf-8"))
    assert text == S.dumps(SC.state_from_composure(comp, plectrum, C.load_comments(deck, DECK_REL)), "scaffold")
    assert S.dumps(S.loads(text)) == text
    assert "We ask the comittee to lease" in text
    # out: a new file beside the composure, then a second, never one written over
    r1 = client.post("/api/composure/scaffold/state/out", json={"path": DECK_REL}).json()
    r2 = client.post("/api/composure/scaffold/state/out", json={"path": DECK_REL}).json()
    assert r1["path"] == "rness/io/composure/a-garden-on-mill-lane.scaffold.md"
    assert r2["path"] == "rness/io/composure/a-garden-on-mill-lane-2.scaffold.md"
    assert (project / r1["path"]).read_text(encoding="utf-8") == text == (project / r2["path"]).read_text("utf-8")


def test_the_state_out_works_on_a_locked_scaffold_and_carries_its_findings(client: TestClient, deck: Path):
    _lock(deck)
    C.record_check(deck, [{"box": SC.module_id("the-ask-in-one-sentence"), "kind": "spelling",
                           "quote": "comittee", "fix": "committee", "status": "open", "version": 1}],
                   {"at": "2026-11-22T10:00:00Z", "version": 1, "mode": "rules"}, DECK_REL)
    text = _state(client, DECK_REL)
    model = SC.state_module().loads(text)
    assert model.meta["locked"] and model.meta["checked"] == "2026-11-22T10:00:00Z"
    assert [(f["box"], f["quote"], f["fix"]) for f in model.findings] == [
        ("the-ask-in-one-sentence", "comittee", "committee")]
    r = client.post("/api/composure/scaffold/state/out", json={"path": DECK_REL})
    assert r.status_code == 200 and r.json()["written"]


# ---------------------------------------------------------------------------
# State in: the round trip
# ---------------------------------------------------------------------------

def test_a_round_trip_out_of_one_scaffold_and_into_a_fresh_one(client: TestClient, deck: Path, project: Path):
    S = SC.state_module()
    text = _state(client, DECK_REL)
    parsed = S.loads(text)
    # a fresh scaffold from the form, made on the page
    _fresh(client)
    code, preview = _bring(client, FRESH_REL, text)
    assert code == 200, preview
    assert preview["preview"] and preview["matching"] == 0 and preview["new"] == len(parsed.boxes())
    assert preview["replace"] == [] and preview["thing"] == "deck"
    assert not (project / FRESH_REL).with_name("fresh.plectrum.md").exists()  # a preview writes nothing
    code, done = _bring(client, FRESH_REL, text, apply=True, base_rev=preview["rev"])
    assert code == 200, done
    assert done["applied"] and done["undo"]
    fresh = project / FRESH_REL
    again = SC.state_from_composure(C.load(fresh), SC.side_plectrum(fresh), C.load_comments(fresh, FRESH_REL))
    assert _layout_and_words(again) == _layout_and_words(parsed)
    # and the fresh scaffold's own state out is the same file, byte for byte (who wrote each plec included)
    assert _state(client, FRESH_REL) == text


def test_a_state_comes_into_a_composure_not_made_yet_when_the_page_says_create(client: TestClient, deck: Path,
                                                                               project: Path):
    text = _state(client, DECK_REL)
    code, body = _bring(client, FRESH_REL, text, apply=True)
    assert code == 404 and "no composure" in body["detail"]
    code, done = _bring(client, FRESH_REL, text, apply=True, create=True)
    assert code == 200, done
    assert done["created"] and C.scaffold_view(C.load(project / FRESH_REL))["thing"] == "deck"


def test_the_batch_is_the_persons_and_the_readvisor_still_never_writes_text(client: TestClient, deck: Path,
                                                                           project: Path):
    text = _state(client, DECK_REL)
    _fresh(client)
    # the server sets the source (ui); a body that names one has no say
    code, done = _bring(client, FRESH_REL, text, apply=True, source="readvisor")
    assert code == 200, done
    fresh = project / FRESH_REL
    comp = C.load(fresh)
    assert C.rich_to_md(comp.module(SC.module_id("cover-title")).pages[0].rich).strip() == "A garden on Mill Lane"
    # who wrote each plec is as the file says (the readvisor wrote these), not who carried it in
    assert comp.module(SC.module_id("cover-title")).plec_by == "readvisor"
    # the same text ops from the readvisor are refused at the core, as ever
    words = [op for op in done["ops"] if op["op"] == "set_page"]
    assert words
    with pytest.raises(C.ComposureError, match="readvisor|person"):
        C.apply_ops(deck, None, words[:1], source="readvisor")


# ---------------------------------------------------------------------------
# State in: refusals
# ---------------------------------------------------------------------------

def test_what_cannot_come_in_is_refused_with_a_sentence(client: TestClient, deck: Path, project: Path):
    before = (project / DECK_REL).read_bytes()
    code, body = _bring(client, DECK_REL, "hello, this is not a state")
    assert code == 400 and "not a scaffold's state enough can read" in body["detail"]
    plectrum = (F.EXAMPLES / "ten-slide-deck.md").read_text(encoding="utf-8")
    code, body = _bring(client, DECK_REL, plectrum)
    assert code == 400 and "plectrum" in body["detail"] and "scaffold: 1" in body["detail"]
    # a page's state into the deck, which holds words already: another thing than it can hold
    page = F.page(project)
    page_text = _state(client, str(page.relative_to(project)))
    code, body = _bring(client, DECK_REL, page_text)
    assert code == 400 and "for a page" in body["detail"] and "makes a deck" in body["detail"]
    code, body = _bring(client, DECK_REL, "")
    assert code == 400 and "'text'" in body["detail"]
    assert (project / DECK_REL).read_bytes() == before


def test_a_locked_scaffold_takes_nothing_in(client: TestClient, deck: Path, project: Path):
    text = _state(client, DECK_REL)
    _lock(deck)
    before = deck.read_bytes()
    code, body = _bring(client, DECK_REL, text)
    assert code == 409 and "locked" in body["detail"]
    code, body = _bring(client, DECK_REL, text, apply=True, replace=[])
    assert code == 409 and deck.read_bytes() == before


# ---------------------------------------------------------------------------
# State in: never a silent overwrite
# ---------------------------------------------------------------------------

def test_words_already_in_a_box_are_never_written_over_without_asking(client: TestClient, deck: Path,
                                                                       project: Path):
    S = SC.state_module()
    model = S.loads(_state(client, DECK_REL))
    ask = model.box("the-ask-in-one-sentence")
    ask["text"] = "We ask the committee for the plot."
    model.box("close-call")["text"] = "Thank you all"
    text = S.dumps(model)
    ask_id, close_id = SC.module_id("the-ask-in-one-sentence"), SC.module_id("close-call")
    code, preview = _bring(client, DECK_REL, text)
    assert code == 200
    assert {r["id"] for r in preview["replace"]} == {ask_id, close_id}
    assert preview["matching"] == len(model.boxes()) and preview["new"] == 0
    # applying without saying which is refused, naming the boxes, and nothing changes
    before = deck.read_bytes()
    code, body = _bring(client, DECK_REL, text, apply=True)
    assert code == 409 and "The ask in one sentence" in body["detail"] and deck.read_bytes() == before
    # an empty list keeps the person's words in both
    code, done = _bring(client, DECK_REL, text, apply=True, replace=[])
    assert code == 200, done
    assert len(done["kept"]) == 2 and "The ask in one sentence" in done["kept"]
    comp = C.load(deck)
    assert "comittee to lease" in C.rich_to_md(comp.module(ask_id).pages[0].rich)
    # naming one replaces that one only
    code, done = _bring(client, DECK_REL, text, apply=True, replace=[ask_id])
    assert code == 200, done
    comp = C.load(deck)
    assert C.rich_to_md(comp.module(ask_id).pages[0].rich).strip() == "We ask the committee for the plot."
    assert C.rich_to_md(comp.module(close_id).pages[0].rich).strip() == "Thank you"


def test_a_state_with_no_words_for_a_box_leaves_that_box_as_it_is(client: TestClient, deck: Path):
    S = SC.state_module()
    model = S.loads(_state(client, DECK_REL))
    model.box("plan-body")["text"] = ""
    code, preview = _bring(client, DECK_REL, S.dumps(model))
    assert code == 200, preview
    plan_name = C.load(deck).module(SC.module_id("plan-body")).title
    assert plan_name in preview["names"]["no_words"]
    assert preview["no_words"] == len(preview["names"]["no_words"])
    code, done = _bring(client, DECK_REL, S.dumps(model), apply=True, replace=[])
    assert code == 200
    plan = C.load(deck).module(SC.module_id("plan-body"))
    assert "Twelve raised beds" in C.rich_to_md(plan.pages[0].rich)


# ---------------------------------------------------------------------------
# State in: one undo step
# ---------------------------------------------------------------------------

def test_bringing_a_state_in_is_undone_in_one_step(client: TestClient, deck: Path, project: Path):
    text = _state(client, DECK_REL)
    _fresh(client)
    fresh = project / FRESH_REL
    before = C.model(C.load(fresh))
    code, done = _bring(client, FRESH_REL, text, apply=True)
    assert code == 200
    rev = done["rev"]
    # the page sends the undo as one batch through the one door
    r = client.post("/api/composure/ops", json={"path": FRESH_REL, "base_rev": rev, "ops": done["undo"]})
    assert r.status_code == 200, r.text
    assert r.json()["rev"] == rev + 1
    after = C.model(C.load(fresh))

    def shape(m: dict) -> list:
        return sorted((x["id"], x["type"], x.get("title"), x["x"], x["y"], x["w"], x["h"],
                       tuple(p["rich"] for p in x["pages"])) for x in m["modules"])
    assert shape(after) == shape(before)
    assert after["scaffold"]["frames"] == before["scaffold"]["frames"]
    assert after["scaffold"]["thing"] == before["scaffold"]["thing"]
    assert after["title"] == before["title"]
    # and the redo (the same ops again) brings it back
    r = client.post("/api/composure/ops", json={"path": FRESH_REL, "base_rev": rev + 1, "ops": done["ops"]})
    assert r.status_code == 200, r.text
    again = SC.state_from_composure(C.load(fresh), SC.side_plectrum(fresh))
    assert _layout_and_words(again) == _layout_and_words(SC.state_module().loads(text))


def test_the_page_puts_the_whole_bring_on_the_undo_stack_as_one_entry():
    src = INDEX.read_text(encoding="utf-8")
    start = src.index("async function compScaffoldStateIn(")
    body = src[start:src.index("\n    }\n", start)]
    assert "/api/composure/scaffold/state/in" in body
    assert body.count("COMP.undo.push(") == 1
    assert "reload: true" in body
    assert "confirmOverlay" in body and "replace" in body


# ---------------------------------------------------------------------------
# A locked state with findings: nothing lost
# ---------------------------------------------------------------------------

def test_a_locked_state_comes_in_locked_with_its_findings(client: TestClient, deck: Path, project: Path):
    _lock(deck)
    C.record_check(deck, [{"box": SC.module_id("the-ask-in-one-sentence"), "kind": "spelling",
                           "quote": "comittee", "fix": "committee", "status": "open", "version": 1},
                          {"box": SC.module_id("the-total"), "kind": "truth", "quote": "Four thousand pounds",
                           "fix": None, "status": "cannot be checked", "version": 1, "why": "a sum we cannot see"}],
                   {"at": "2026-11-22T10:00:00Z", "version": 1, "mode": "rules"}, DECK_REL)
    text = _state(client, DECK_REL)
    _fresh(client)
    code, preview = _bring(client, FRESH_REL, text)
    assert code == 200 and preview["locked"] and preview["findings"] == 2 and preview["findings_brought"] == 2
    code, done = _bring(client, FRESH_REL, text, apply=True)
    assert code == 200, done
    assert done["undo"] is None  # a locked scaffold is undone by unlocking, never by undo
    fresh = project / FRESH_REL
    assert C.scaffold_locked(C.load(fresh))
    found = C.list_findings(fresh, FRESH_REL)
    assert [(f["id"], f["status"]) for f in found] == [("f1", "open"), ("f2", "cannot be checked")]
    assert found[0]["box"] == SC.module_id("the-ask-in-one-sentence")
    # the carried finding can be accepted here, as any finding
    r = client.post("/api/composure/scaffold/accept", json={"path": FRESH_REL, "finding": "f1"})
    assert r.status_code == 200, r.text
    out = SC.state_module().loads(_state(client, FRESH_REL))
    assert out.meta["checked"] == "2026-11-22T10:00:00Z"
    assert "committee to lease" in out.box("the-ask-in-one-sentence")["text"]


# ---------------------------------------------------------------------------
# The small fixes from the trials
# ---------------------------------------------------------------------------

def test_the_locks_empty_list_leaves_out_the_notes_box(project: Path):
    path = F.deck(project)
    empty = C.empty_boxes(C.load(path))
    notes = SC.module_id("notes-to-the-readvisor")
    assert C.load(path).module(notes).as_ == "notes"
    assert notes not in empty
    assert SC.module_id("plot-picture") in empty
    # and the lock takes the list without it
    C.apply_ops(path, None, [{"op": "lock_scaffold", "empty": empty}], source="ui")
    assert C.scaffold_locked(C.load(path))


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    return node


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start:src.index("\n    }\n", start) + 6]


def test_the_checks_done_message_says_a_count_not_the_ids():
    src = INDEX.read_text(encoding="utf-8")
    fn = _function(src, "compScaffoldFoundCount")
    script = fn + "\nconsole.log(JSON.stringify(["
    script += "compScaffoldFoundCount({findings: 8, added: ['f1','f2','f3','f4','f5','f6','f7','f8']}),"
    script += "compScaffoldFoundCount({findings: [{id: 'f1'}, {id: 'f2'}]}),"
    script += "compScaffoldFoundCount({added: ['f1', 'f2', 'f3']}),"
    script += "compScaffoldFoundCount({})]));"
    out = subprocess.run([_node(), "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [8, 2, 3, 0]
    toast = _function(src, "compScaffoldJobToast")
    assert "compScaffoldFoundCount(res)" in toast
    assert "res.added || 0" not in toast
