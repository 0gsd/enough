"""A poem decompiled in steps (0.7, `enough/fabulap_job.py`; Thym 20.9; MacroCOSM OES 18.4.6, 18.4.7): the five
programs of `decompile-verse.thym` run in order as one job, each landing `<poem>.fabulap.cosm`; under rules or
agent-free the job stops after scan and hear and says why; a stopped build taken up again from disk; a poem that
changed scanned again; a fabulap decompiled in one call rebuilt in steps only when asked; what the card draws; the
routes under `/api/fabula/verse/`; the `fabulap` tool.

No model: a scripted coprocessor stands in at the function level, and the routes run with a dead model URL, so the app
is in rules mode. FEED is the verse fixtures' rows (`tests/test_verse_moves.py`). Every seam points inside tmp_path.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon, macrocosm as mc, models, skeleton
from enough import fabula_tools as FT
from enough import fabulap_job as P
from enough import thym_host as H
from enough.canon_derive import DeriveCancelled
from enough.server import create_app
from enough.thym.coprocessor import candidate
from tests.test_canon_tools import run, tool
from tests.test_prompt_weight import enable_skill
from tests.test_verse_moves import (ALLUSION, ATEM, FIGURE, FIX, MEANING, SENSE, VOICE, _engines, pron_c)

NOW = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)
TURN = ('nodes:\n  - {id: C:device/turn-5, type: device, name: The turn at line 5, summary: The poem turns from the pact '
        'to scorn., stance: deduced, figure: turn, cue: How dreary, where: [C:line/5], effect: from a whispered pact to '
        'scorn, span: {lines: "8"}, provenance: {mode: derived, sources: [\'nobody.txt#L8\'], confidence: 0.6, '
        'state: known}}\n')


class Model:
    """Answers by move: derive (a passage, then the poem's atem), the seven construe axes in turn, a question step
    that proposes nothing."""

    def __init__(self) -> None:
        self.axes = [FIGURE, "nodes: []", ALLUSION, VOICE, TURN, MEANING, "nodes: []"]
        self.sent: list[str] = []

    def complete(self, contract, inputs, *, budget):
        move = contract.get("move")
        self.sent.append(str(move))
        if move == "derive":
            msgs = inputs["messages"]
            msgs = msgs[0] if isinstance(msgs, tuple) else msgs
            return candidate(ATEM if "You write the atem" in msgs.text() else SENSE, engine="model:scripted-1",
                             tokens=10)
        if move == "construe":
            return candidate(self.axes.pop(0), engine="model:scripted-1", tokens=10)
        return candidate("questions: []", engine="model:scripted-1", tokens=5)


def runtime(cp=None):
    def make(stage, plan, info, mode, scaffolds, program):
        from enough.thym.coprocessor import RefusingCoprocessor
        return {"coprocessor": cp if (mode == "model" and cp is not None) else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if mode == "model" else {},
                "root": H.host_root(), "engines": _engines(pron_c), "calls": None}
    return make


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    for name in ("nobody.txt", "lantern-song.txt", "sonnet-116.txt"):
        shutil.copyfile(FIX / name, proj / name)
    return proj


def fabulap(project: Path, name: str = "nobody.txt") -> dict:
    return mc.yaml_load((project / f"{name}.fabulap.cosm").read_text(encoding="utf-8"))


def build(project: Path, name: str = "nobody.txt", **kw):
    kw.setdefault("mode", "model")
    kw.setdefault("runtime", runtime(Model()))
    return P.run_build(project, project / name, now=NOW, **kw)


# ---------------------------------------------------------------------------
# The job, at the function level
# ---------------------------------------------------------------------------

def test_the_stages_are_the_shipped_files_programs_in_order():
    text = P.program_path().read_text(encoding="utf-8")
    assert tuple(re.findall(r"^program (\S+)", text, re.M)) == P.STAGES
    assert P.program_path().parent == H.SHIPPED_PROGRAMS
    assert [P.STEP_OF[s] for s in P.STAGES] == ["scan", "hear", "read-closely", "read-closely", "read-closely"]
    assert P.RULES_STAGES == 2 and P.ASKING_STAGES == 3
    assert P.job_ceiling(None, None) is None and P.job_ceiling(4, None) == 12 and P.job_ceiling(4, 2) == 2


def test_rules_scans_and_hears_and_says_why_read_closely_waits(project: Path):
    out = build(project, mode="rules", why="the model is not running")
    assert not out["complete"] and [r["stage"] for r in out["ran"]] == ["scan", "hear"]
    doc = fabulap(project)
    assert doc["flavour"] == "fabulap" and doc["derived"]["completeness"] == "outline"
    assert [r["program"] for r in doc["derived"]["runs"]] == ["scan-the-poem"] + ["hear-the-poem"] * 4
    r = out["refusal"]
    assert r["check"] == "no-model" and r["program"] == "read-the-poem"
    assert "ask a model on the local route" in r["message"] or "asks a model on the local route" in r["message"]
    assert r["message"].endswith("; no model is running")
    assert out["message"].startswith("nobody.txt.fabulap.cosm: scan, hear landed; read-the-poem waits: ")
    state = out["state"]
    assert state["landed"] == 2 and state["next"] == "read-the-poem" and state["built"]
    assert [s["landed"] for s in state["steps"]] == [1, 1, 0] and [s["of"] for s in state["steps"]] == [1, 1, 3]


def test_agent_free_stops_after_hear_in_the_agent_free_words(project: Path):
    out = build(project, mode="rules", why=agent_free.REASON)
    assert [r["stage"] for r in out["ran"]] == ["scan", "hear"]
    assert out["refusal"]["check"] == "agent-free" and out["refusal"]["message"].endswith("; agent-free is on")


def test_mode_rules_asked_stops_at_the_outline(project: Path):
    out = build(project, mode="rules", scaffolds=True)
    assert out["refusal"]["check"] == "rules" and "outline only (scan and hear)" in out["refusal"]["message"]


def test_a_build_with_a_model_lands_every_program_and_the_card_reads_it(project: Path):
    cp = Model()
    out = build(project, runtime=runtime(cp))
    assert out["complete"], out
    assert [r["program"] for r in out["ran"]] == list(P.STAGES)
    assert cp.sent.count("construe") == 7
    doc = fabulap(project)
    progs = [r["program"] for r in doc["derived"]["runs"]]
    assert progs[0] == "scan-the-poem" and progs[-1] == "raise-the-questions"
    assert set(progs) == set(P.STAGES)
    q = [r for r in doc["derived"]["runs"] if r["program"] == "raise-the-questions"]
    assert q[-1]["model"] == "scripted-1" and q[-1]["route"] == "local"
    state = P.build_state(project, project / "nobody.txt")
    assert state["complete"] and state["landed"] == 5 and state["next"] is None
    card = state["card"]
    assert card["form"]["id"] == "C:form/common-metre" and card["form"]["departures"]
    devs = {d["id"]: d for d in card["devices"]}
    assert devs["C:device/simile-frog"]["cue"] == "like a frog"
    assert devs["C:device/turn-5"]["figure"] == "turn" and card["readings"] >= 3 and card["voices"] == 2


def test_a_stopped_build_takes_up_again_from_disk(project: Path):
    def stop() -> bool:
        return P.build_state(project, project / "nobody.txt")["landed"] >= 3
    with pytest.raises(DeriveCancelled) as e:
        build(project, should_stop=stop)
    assert "landed before it: scan, hear, read" in str(e.value) and "takes up again from read closely" in str(e.value)
    state = P.build_state(project, project / "nobody.txt")
    assert state["landed"] == 3 and state["next"] == "read-closely"
    assert P.start_index(state) == 3 and P.start_index(state, resume_only=True) == 3
    out = build(project, resume_only=True)
    assert [r["stage"] for r in out["ran"]] == ["read closely", "question"] and out["complete"]


def test_a_poem_that_changed_is_scanned_again(project: Path):
    build(project, mode="rules", why="no model")
    poem = project / "nobody.txt"
    poem.write_text(poem.read_text(encoding="utf-8") + "\nAnd one line more.\n", encoding="utf-8")
    state = P.build_state(project, poem)
    assert state["moved"] and state["next"] == "scan-the-poem" and P.start_index(state) == 0
    with pytest.raises(P.BuildError) as e:
        P.start_index(state, resume_only=True)
    assert e.value.status == 409 and "changed since its fabulap was scanned" in str(e.value)


def test_a_fabulap_decompiled_in_one_call_is_rebuilt_in_steps_only_when_asked(project: Path):
    shutil.copyfile(FIX.parent / "poems" / "the-sick-rose.txt.fabulap.cosm", project / "x.fabulap.cosm")
    build(project, mode="rules", why="no model")
    fab = project / "nobody.txt.fabulap.cosm"
    doc = mc.yaml_load(fab.read_text(encoding="utf-8"))
    doc["derived"]["runs"] = [{"program": "decompile-verse", "run": "2026-11-01-0000-abcd"}]
    fab.write_text(mc.dump(doc), encoding="utf-8")
    state = P.build_state(project, project / "nobody.txt")
    assert state["exists"] and not state["built"] and state["landed"] == 0
    with pytest.raises(P.BuildError) as e:
        P.start_index(state)
    assert e.value.status == 409 and "decompiled in one call" in str(e.value) and "restart" in str(e.value)
    assert P.start_index(state, restart=True) == 0
    out = build(project, mode="rules", why="no model", restart=True)
    assert [r["stage"] for r in out["ran"]] == ["scan", "hear"]


def test_a_complete_build_is_built_again_only_when_asked(project: Path):
    build(project)
    with pytest.raises(P.BuildError) as e:
        P.start_index(P.build_state(project, project / "nobody.txt"))
    assert e.value.status == 409 and "already built" in str(e.value)


def test_the_card_holds_the_form_its_rules_the_lyrics_parts_and_its_hook(project: Path):
    build(project, "sonnet-116.txt", mode="rules", why="no model")
    card = P.build_state(project, project / "sonnet-116.txt")["card"]
    form = card["form"]
    assert form["name"] == "Shakespearean sonnet" and form["scheme"] == "ababcdcdefefbb"
    helds = {r["rule"]: r["held"] for r in form["rules"]}
    assert helds["fourteen lines"] == "held" and "open" in helds.values()
    assert not card["lyric"] and card["hook"] is None
    build(project, "lantern-song.txt", mode="rules", why="no model")
    card = P.build_state(project, project / "lantern-song.txt")["card"]
    assert card["lyric"] and [p["division"] for p in card["parts"]] == ["verse", "chorus", "verse", "chorus", "other"]
    assert card["parts"][3]["again"] == "C:part/chorus" and card["parts"][4]["heading"] == "Outro"
    assert card["hook"]["cue"] == "Carry the light" and card["hook"]["intended"] is None
    allit = next(d for d in card["devices"] if d["figure"] == "alliteration")
    assert allit["cue"] and allit["senses"] == []


def test_targets_out_of_the_project_or_not_a_poem_are_refused(project: Path, tmp_path: Path):
    for bad, status in (("", 400), ("nowhere.txt", 404), ("../x.txt", 400), ("canon:v/x.txt", 400)):
        with pytest.raises(P.BuildError) as e:
            P.target_of(project, bad)
        assert e.value.status == status, (bad, e.value)
    (project / "folder").mkdir()
    with pytest.raises(P.BuildError, match="is a folder"):
        P.target_of(project, "folder")
    outside = tmp_path / "outside.txt"
    outside.write_text("a line\n", encoding="utf-8")
    (project / "link.txt").symlink_to(outside)
    with pytest.raises(P.BuildError, match="link"):
        P.target_of(project, "link.txt")
    poem, fab, _t = P.target_of(project, "nobody.txt")
    assert (poem.name, fab.name) == ("nobody.txt", "nobody.txt.fabulap.cosm")
    build(project, mode="rules", why="no model")
    poem2, fab2, _t = P.target_of(project, "nobody.txt.fabulap.cosm")
    assert (poem2, fab2) == (poem, fab)


# ---------------------------------------------------------------------------
# The routes (rules: the model URL is dead) and the tool
# ---------------------------------------------------------------------------

def wait_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {snap}")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "lantern-song.txt", proj / "lantern-song.txt")
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), canon.root(), H.host_root()):
        assert str(where).startswith(str(tmp_path)), where
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        c._project = proj  # type: ignore[attr-defined]
        yield c
    FT.configure()


def test_the_build_route_scans_and_hears_without_a_model_and_says_what_waits(client: TestClient):
    r = client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["from"] == "scan-the-poem" and body["job"]["kind"] == "fabulap" and body["job"]["mode"] == "rules"
    snap = wait_job(client, body["job"]["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert [x["stage"] for x in res["ran"]] == ["scan", "hear"] and res["refusal"]["check"] == "no-model"
    assert res["fabulap"] == "lantern-song.txt.fabulap.cosm" and "read-the-poem waits" in res["message"]
    st = client.get("/api/fabula/verse/build", params={"path": "lantern-song.txt"}).json()
    assert st["state"]["landed"] == 2 and st["state"]["next"] == "read-the-poem" and st["job"] is None
    assert st["state"]["card"]["hook"]["cue"] == "Carry the light"
    by_twin = client.get("/api/fabula/verse/build", params={"path": "lantern-song.txt.fabulap.cosm"}).json()
    assert by_twin["state"]["landed"] == 2
    r = client.post("/api/fabula/verse/resume", json={"path": "lantern-song.txt"})
    assert r.status_code == 200 and r.json()["from"] == "read-the-poem"
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["result"]["ran"] == [] and snap["result"]["refusal"]["program"] == "read-the-poem"
    # the questions: the bank, raised by rule, through the dialectic's own route
    q = client.post("/api/dialectic/raise", json={"path": "lantern-song.txt.fabulap.cosm", "dry": True})
    assert q.status_code == 200 and q.json()["count"] > 0, q.text


def test_the_build_routes_refusals(client: TestClient):
    r = client.post("/api/fabula/verse/resume", json={"path": "lantern-song.txt"})
    assert r.status_code == 409 and "nothing to take up again" in r.json()["detail"]
    assert client.post("/api/fabula/verse/build", json={"path": "nowhere.txt"}).status_code == 404
    r = client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt", "route": "moon"})
    assert r.status_code == 400 and "route is local or cloud" in r.json()["detail"]
    r = client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt", "job_calls": 0})
    assert r.status_code == 400 and "job_calls is a ceiling" in r.json()["detail"]
    assert client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt", "route": "cloud"}).status_code == 403
    r = client.post("/api/fabula/verse/cancel", json={"path": "lantern-song.txt"})
    assert r.status_code == 409 and "no decompile of lantern-song.txt is running" in r.json()["detail"]
    r = client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt", "mode": "model"})
    assert r.status_code == 409 and "no model is running" in r.json()["detail"]


def test_the_build_route_under_agent_free(client: TestClient):
    path = agent_free.ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({agent_free.KEY: True}), encoding="utf-8")
    body = client.post("/api/fabula/verse/build", json={"path": "lantern-song.txt"}).json()
    snap = wait_job(client, body["job"]["id"])
    assert snap.get("reason") == "agent-free" and snap["result"]["refusal"]["check"] == "agent-free"
    assert [x["stage"] for x in snap["result"]["ran"]] == ["scan", "hear"]
    assert snap["result"]["refusal"]["message"].endswith("; agent-free is on")


def test_the_fabulap_tool_starts_and_follows_a_build_through_the_app(client: TestClient):
    project = client._project  # type: ignore[attr-defined]
    r = run(project, tool("fabulap", path="lantern-song.txt"))
    assert not r.ok and "macrocosm-oes skill" in r.body
    enable_skill(project, "macrocosm-oes")
    r = run(project, tool("fabulap", path="lantern-song.txt"))
    assert r.ok and "has no fabulap yet" in r.body, r.body
    r = run(project, tool("fabulap", path="lantern-song.txt", do="build"))
    assert r.ok and r.body.startswith("job cn"), r.body
    snap = wait_job(client, r.body.split()[1].rstrip(":"))
    assert snap["state"] == "done" and snap["kind"] == "fabulap"
    r = run(project, tool("fabulap", path="lantern-song.txt"))
    assert r.ok and "scan, hear landed; next read" in r.body, r.body
    r = run(project, tool("fabulap", path="lantern-song.txt", do="cancel"))
    assert not r.ok and "is running" in r.body
    r = run(project, tool("fabulap", path="lantern-song.txt", do="paint"))
    assert not r.ok and "<do>" in r.body
