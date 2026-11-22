"""The scaffolder's four page leftovers from 0.8 (lane S1 of the 0.9 build).

- 2. a box's resize stays inside its frame (`compResizeRect`, run under node);
- 3. a box's `as` is on the composure module: saved as `data-as`, read back, carried by the adapter, and
  read by the state (so by the export) before the plectrum's;
- 4. what the scaffold becomes is one undoable op on the page, and over HTTP the server sets its source.

The (?) bubble of item 1 is held by `test_content_integrity.py` (every reachable help id has a section).
"""
from __future__ import annotations

import json
import re
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
REL = "rness/io/composure/plane.comp"


# ---------------------------------------------------------------------------
# 3. `as` on the module
# ---------------------------------------------------------------------------

def _scaffold_with_box(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "s.comp"
    C.save(path, C.new_composure("scaffold", "S"))
    fid = C.load(path).modules[0].id
    res = C.apply_ops(path, None, [{"op": "add_module", "type": C.BOX, "id": "mbox1", "frame": fid,
                                    "plec": "the name", "target": "40c"}], source="ui")
    assert res.rev >= 1
    return path, fid


def test_as_is_saved_as_data_as_and_read_back(tmp_path: Path):
    path, _ = _scaffold_with_box(tmp_path)
    C.apply_ops(path, None, [{"op": "update_module", "id": "mbox1", "as": "Headline"}], source="ui")
    text = path.read_text(encoding="utf-8")
    assert 'data-as="headline"' in text
    m = C.load(path).module("mbox1")
    assert m.as_ == "headline"
    assert C.module_model(m)["fields"]["as"] == "headline"


def test_as_takes_any_word_and_refuses_what_is_not_one(tmp_path: Path):
    path, fid = _scaffold_with_box(tmp_path)
    # A word the page does not know is kept (plectrum.md: shown as body, never refused for being new).
    C.apply_ops(path, None, [{"op": "update_module", "id": "mbox1", "as": "pull-quote"}], source="readvisor")
    assert C.load(path).module("mbox1").as_ == "pull-quote"
    for bad in ("two words", "9lives", "x" * 33, "<b>"):
        with pytest.raises(C.ComposureError, match="one word"):
            C.apply_ops(path, None, [{"op": "update_module", "id": "mbox1", "as": bad}], source="ui")
    with pytest.raises(C.ComposureError, match="frame takes a shape"):
        C.apply_ops(path, None, [{"op": "update_module", "id": fid, "as": "title"}], source="ui")
    # '' clears it: the plectrum's word, else body.
    C.apply_ops(path, None, [{"op": "update_module", "id": "mbox1", "as": ""}], source="ui")
    assert C.load(path).module("mbox1").as_ == ""
    assert "data-as" not in path.read_text(encoding="utf-8")


def test_as_on_a_locked_scaffold_is_refused(tmp_path: Path):
    path, _ = _scaffold_with_box(tmp_path)
    C.apply_ops(path, None, [{"op": "lock_scaffold", "empty": ["mbox1"]}], source="ui")
    with pytest.raises(C.ComposureError, match="locked"):
        C.apply_ops(path, None, [{"op": "update_module", "id": "mbox1", "as": "title"}], source="ui")


def test_the_adapter_puts_the_plectrums_as_on_each_box_and_a_second_run_is_quiet(tmp_path: Path):
    path = F.deck(tmp_path)
    comp = C.load(path)
    model = SC.loads(SC.plectrum_path(path).read_text(encoding="utf-8"))
    for b in model.boxes():
        assert (comp.module(SC.module_id(b["id"])).as_ or "body") == b["as"], b["id"]
    assert SC.plectrum_ops(model, comp).ops == []


def test_the_state_reads_the_modules_as_before_the_plectrums(tmp_path: Path):
    path = F.deck(tmp_path)
    model = SC.loads(SC.plectrum_path(path).read_text(encoding="utf-8"))
    mid = SC.module_id("plot-headline")
    assert model.box("plot-headline")["as"] == "headline"
    C.apply_ops(path, None, [{"op": "update_module", "id": mid, "as": "caption"}], source="ui")
    state = SC.state_from_composure(C.load(path), model)
    assert state.box("plot-headline")["as"] == "caption"
    # The writer's form carries it, so a scaffold carried to another harness keeps the person's choice.
    assert "as: caption" in SC.state_module().dumps(state)


def test_a_box_made_before_09_still_takes_the_plectrums_as(tmp_path: Path):
    path = F.deck(tmp_path)
    text = path.read_text(encoding="utf-8")
    old = re.sub(r' data-as="[^"]*"', "", text)
    assert old != text
    path.write_text(old, encoding="utf-8")
    model = SC.loads(SC.plectrum_path(path).read_text(encoding="utf-8"))
    state = SC.state_from_composure(C.load(path), model)
    assert state.box("plot-headline")["as"] == "headline"
    # The next run of the tool fills the field in.
    ops = SC.plectrum_ops(model, C.load(path)).ops
    assert {"op": "update_module", "id": SC.module_id("plot-headline"), "as": "headline"} in ops


# ---------------------------------------------------------------------------
# 3 and 4 over HTTP, the way the page reaches them
# ---------------------------------------------------------------------------

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


def _ops(client: TestClient, ops: list, **extra) -> dict:
    rev = client.get("/api/composure", params={"path": REL}).json()["rev"]
    r = client.post("/api/composure/ops", json={"path": REL, "base_rev": rev, "source": "ui",
                                                "ops": ops, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _model(client: TestClient) -> dict:
    return client.get("/api/composure", params={"path": REL}).json()["model"]


def _seed_scaffold(client: TestClient) -> str:
    r = client.post("/api/composure/ops", json={
        "path": REL, "base_rev": 0, "create": True, "form": "scaffold", "title": "Plane",
        "ops": [{"op": "set_meta", "title": "Plane"}]})
    assert r.status_code == 200, r.text
    return _model(client)["modules"][0]["id"]


def test_as_survives_a_reload_over_http(client: TestClient):
    fid = _seed_scaffold(client)
    _ops(client, [{"op": "add_module", "type": "scaffold-box", "id": "mbox1", "frame": fid}])
    _ops(client, [{"op": "update_module", "id": "mbox1", "as": "lede"}])
    box = next(m for m in _model(client)["modules"] if m["id"] == "mbox1")
    assert box["fields"]["as"] == "lede"
    # The page's undo sends the inverse through the same door.
    _ops(client, [{"op": "update_module", "id": "mbox1", "as": ""}])
    box = next(m for m in _model(client)["modules"] if m["id"] == "mbox1")
    assert box["fields"]["as"] is None


def test_what_it_becomes_and_its_undo_are_ops_whose_source_the_server_sets(client: TestClient):
    _seed_scaffold(client)
    _ops(client, [{"op": "set_scaffold", "thing": "deck"}])
    assert _model(client)["scaffold"]["thing"] == "deck"
    _ops(client, [{"op": "set_scaffold", "thing": "page"}])      # the page's undo entry
    assert _model(client)["scaffold"]["thing"] == "page"
    # No source sent is the person's too (the page sends `ui`; the server sets it either way).
    rev = client.get("/api/composure", params={"path": REL}).json()["rev"]
    r = client.post("/api/composure/ops", json={"path": REL, "base_rev": rev,
                                                "ops": [{"op": "set_scaffold", "thing": "deck"}]})
    assert r.status_code == 200, r.text
    _ops(client, [{"op": "set_scaffold", "thing": "page"}])
    # A client may not claim another source for it; nothing changes.
    rev = client.get("/api/composure", params={"path": REL}).json()["rev"]
    for claimed in ("readvisor", "enough", "council"):
        r = client.post("/api/composure/ops", json={"path": REL, "base_rev": rev, "source": claimed,
                                                    "ops": [{"op": "set_scaffold", "thing": "document"}]})
        assert r.status_code == 403, r.text
    assert _model(client)["scaffold"]["thing"] == "page"


# ---------------------------------------------------------------------------
# 4. the page side: one undoable op
# ---------------------------------------------------------------------------

def _function(src: str, name: str) -> str:
    """One top-level function of the page's main script, by its four-space indent."""
    m = re.search(r"\n    (?:async )?function " + re.escape(name) + r"\(.*?\n    \}\n", src, re.S)
    assert m, name
    return m.group(0)


def test_the_page_sends_what_it_becomes_through_the_undo_stack():
    src = INDEX.read_text(encoding="utf-8")
    body = _function(src, "compScaffoldSetThing")
    assert "compDo(" in body and "compCommit(" not in body
    assert re.search(r"undo:\s*\[\{\s*op: 'set_scaffold', thing: s\.thing", body)
    # The local mirror knows the op, so undo and redo repaint the chrome and the export menu.
    apply_local = _function(src, "compApplyOpLocal")
    assert "op.op === 'set_scaffold'" in apply_local
    assert "compScaffoldThingChanged()" in _function(src, "compApplyOps")
    # The one body every composure batch leaves in names the person's source and no other.
    assert re.findall(r"source:\s*'([a-z]+)'", _function(src, "compBatchBody")) == ["ui"]


def test_the_page_carries_as_like_the_other_box_fields():
    src = INDEX.read_text(encoding="utf-8")
    for fn in ("compMirrorScaffoldFields", "compSnapshot"):
        assert "'as'" in _function(src, fn), fn
    assert "data-sfield" in src and "'as'" in _function(src, "compSFieldValue")
    assert "name === 'as'" in _function(src, "compScaffoldField")


# ---------------------------------------------------------------------------
# 2. a box's resize stays inside its frame
# ---------------------------------------------------------------------------

NODE = shutil.which("node")


def _resize(cases: list) -> list:
    src = INDEX.read_text(encoding="utf-8")
    fn = _function(src, "compResizeRect")
    js = ("const COMP_MIN_W = 96, COMP_MIN_H = 64;\n" + fn
          + f"\nconst cases = {json.dumps(cases)};\n"
          "console.log(JSON.stringify(cases.map(c => compResizeRect(c[0], c[1], c[2], c[3], c[4]))));\n")
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not on PATH")
def test_a_box_resize_stops_at_its_frame_on_every_side():
    frame = {"x0": 0, "y0": 0, "x1": 816, "y1": 1056}
    box = {"x": 100, "y": 100, "w": 300, "h": 200}
    se, nw, e_free, shrink = _resize([
        [box, "se", 5000, 5000, frame],
        [box, "nw", -5000, -5000, frame],
        [box, "e", 5000, 0, None],              # no frame: as before
        [box, "se", -100, -50, frame],
    ])
    assert se == {"x": 100, "y": 100, "w": 716, "h": 956}
    assert nw == {"x": 0, "y": 0, "w": 400, "h": 300}
    assert e_free["w"] == 5300
    assert shrink == {"x": 100, "y": 100, "w": 200, "h": 150}


@pytest.mark.skipif(NODE is None, reason="node is not on PATH")
def test_a_box_already_past_its_frame_may_shrink_but_not_grow():
    frame = {"x0": 0, "y0": 0, "x1": 816, "y1": 1056}
    wide = {"x": 600, "y": 900, "w": 400, "h": 300}         # past the right and the foot
    grow, smaller, tiny = _resize([
        [wide, "se", 50, 50, frame],
        [wide, "se", -100, -100, frame],
        [{"x": 800, "y": 0, "w": 100, "h": 100}, "e", -500, 0, frame],
    ])
    assert grow == {"x": 600, "y": 900, "w": 400, "h": 300}
    assert smaller == {"x": 600, "y": 900, "w": 300, "h": 200}
    assert tiny["w"] == 96                                   # never under the legible minimum


def test_the_resize_gesture_carries_the_frame_bound():
    src = INDEX.read_text(encoding="utf-8")
    assert "bound: compBoxResizeBound(m)" in src
    assert "compResizeRect(d.start, d.handle, w.x - d.w0.x, w.y - d.w0.y, d.bound)" in src
