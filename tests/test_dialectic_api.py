"""The dialectic's routes and the agent's tools (0.6, `enough/dialectic_api.py`, `enough/fabula_tools.py`; MacroCOSM
OES 18.6; THYM 22; Ascribe 8): a volume's questions listed for the card, a value checked, a sitting written as an
answers volume beside the twin (the card never writes the twin), the sitting settled by `settle.thym` (rules here: the
model URL is dead), a bank raised, a question asked again; a holograph through Ascribe's own functions (the holder alone
answers; words that read like personal data are refused); `cosm_lint` by format; the `dialectic` and `fabulac` tools.
Every seam points inside tmp_path (conftest). No model runs.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import canon, macrocosm as mc, models, skeleton
from enough import dialectic as dl
from enough import dialectic_api as D
from enough import fabula_tools as FT
from enough import thym_host as H
from enough import tools as T
from enough.server import create_app
from tests.test_canon_tools import run, tool
from tests.test_prompt_weight import enable_skill
from tests.test_thym_code import TINY

REPO = Path(__file__).resolve().parent.parent
INPUTS = REPO / "tests" / "fixtures" / "thym" / "inputs"
SAMPLE = REPO / "tests" / "fixtures" / "ascribe" / "sample-self"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    for name in ("notes.md", "notes.md.cosm"):
        shutil.copyfile(INPUTS / name, proj / name)
    shutil.copytree(SAMPLE, proj / "self")
    shutil.copytree(TINY, proj / "tiny-tool")
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), canon.root(), H.host_root()):
        assert str(where).startswith(str(tmp_path)), where
    return proj


@pytest.fixture
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c
    FT.configure()


def wait_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {snap}")


# ---------------------------------------------------------------------------
# A text's fabula
# ---------------------------------------------------------------------------

def test_the_whole_life_of_a_question_through_the_routes(client: TestClient, project: Path):
    twin = project / "notes.md.cosm"
    # before any question: the bare pendings are the open questions (18.6.5), answered by their address
    first = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert first["path"] == "notes.md.cosm" and first["fabula"] and not first["holograph"]
    assert first["open"] and {c["form"] for c in first["open"]} == {"pending"}
    # the bank, raised by rules on a volume that has none yet
    r = client.post("/api/dialectic/raise", json={"path": "notes.md"})
    assert r.status_code == 200, r.text
    raised = r.json()["raised"]
    assert raised and all(q.startswith("D:question/") for q in raised)
    assert client.post("/api/dialectic/raise", json={"path": "notes.md"}).status_code == 409
    listed = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    cards = [c for c in listed["open"] if c["form"] == "question"]
    assert cards and all(c["asks"] and c["state"] == "open" and c["raised"] for c in cards)
    assert set(cards[0]) >= {"id", "about", "asks", "why", "kind", "to", "hint", "options", "item", "field"}
    a, b, c, d = cards[0]["id"], cards[1]["id"], cards[2]["id"], cards[3]["id"]
    # a value checked before it is sent
    ok = client.post("/api/dialectic/check", json={"path": "notes.md", "question": a, "value": "the parish"}).json()
    assert ok["ok"] and ok["value"] == "the parish"
    assert client.post("/api/dialectic/check", json={"path": "notes.md", "question": "D:question/nope",
                                                     "value": "x"}).status_code == 404
    before = twin.read_bytes()
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "who": "the orchard's keeper", "answers": [
        {"question": a, "says": "the parish council"}, {"question": b, "dont_know": True, "says": "no idea"},
        {"question": c, "declined": True}, {"question": d, "skip": True}]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["written"].startswith("notes.md.answers-") and out["written"].endswith(".cosm")
    assert {x["question"]: x["state"] for x in out["recorded"]} == {a: "answered", b: "unknown", c: "declined"}
    assert out["skipped"] == [d]
    assert twin.read_bytes() == before                          # the card never writes the twin
    av = dl.read_answers_volume(project / out["written"])
    assert av.session["through"] == "person" and av.session["with"]["who"] == "the orchard's keeper"
    # listed again: the three wait in the sitting, the skipped one is still open; none can be answered twice
    again = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert {w["id"] for w in again["waiting"]} == {a, b, c} and all(w["waiting_in"] for w in again["waiting"])
    assert d in [x["id"] for x in again["open"]] and a not in [x["id"] for x in again["open"]]
    assert again["sittings"][0]["path"] == out["written"]
    twice = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [{"question": a, "says": "x"}]})
    assert twice.status_code == 422 and "not open" in twice.json()["detail"]
    r = client.post("/api/dialectic/ask-again", json={"path": "notes.md", "question": a})
    assert r.status_code == 409 and "settle it first" in r.json()["detail"]
    # settled by settle.thym, under rules (no model answers here)
    r = client.post("/api/dialectic/settle", json={"path": "notes.md"})
    assert r.status_code == 200, r.text
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert snap["kind"] == "dialectic" and res["mode"] == "rules" and len(res["runs"]) == 1
    assert res["sittings"] == [out["written"]]
    vol = dl.open_twin(twin).ledger
    assert av.session["id"] in {s["id"] for s in vol.sessions()}
    assert {q["id"]: q["state"] for q in vol.questions() if q["id"] in (a, b, c)} == {
        a: "answered", b: "unknown", c: "declined"}
    assert client.post("/api/dialectic/settle", json={"path": "notes.md"}).status_code == 409
    # asked again once it is settled
    r = client.post("/api/dialectic/ask-again", json={"path": "notes.md", "question": b})
    assert r.status_code == 200 and r.json()["state"] == "open"


def test_what_the_routes_refuse(client: TestClient, project: Path):
    assert client.get("/api/dialectic/questions", params={"path": "nope.md"}).status_code == 404
    (project / "plain.md").write_text("a text", encoding="utf-8")
    r = client.get("/api/dialectic/questions", params={"path": "plain.md"})
    assert r.status_code == 404 and "has no fabula yet" in r.json()["detail"]
    r = client.get("/api/dialectic/questions", params={"path": "tiny-tool"})
    assert r.status_code == 400 and "no volume to answer" in r.json()["detail"]
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": []})
    assert r.status_code == 400
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "through": "post",
                                                     "answers": [{"question": "x", "says": "y"}]})
    assert r.status_code == 400 and "through is" in r.json()["detail"]
    r = client.post("/api/dialectic/settle", json={"path": "notes.md"})
    assert r.status_code == 409 and "nothing to settle" in r.json()["detail"]


def test_a_fabulac_is_answered_like_any_fabula(client: TestClient, project: Path):
    snap = wait_job(client, client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()["job"]["id"])
    assert snap["state"] == "done"
    listed = client.get("/api/dialectic/questions", params={"path": "tiny-tool"}).json()
    assert listed["path"] == "tiny-tool.fabulac.cosm" and listed["flavour"] == "fabulac" and listed["open"]


# ---------------------------------------------------------------------------
# A holograph: Ascribe's rules
# ---------------------------------------------------------------------------

def test_a_holograph_is_answered_by_its_holder_alone_and_never_with_personal_data(client: TestClient,
                                                                                    project: Path):
    listed = client.get("/api/dialectic/questions", params={"path": "self"}).json()
    assert listed["holograph"] and listed["to"] == "holder"
    if not [q for q in listed["open"] if q["form"] == "question"]:
        r = client.post("/api/dialectic/raise", json={"path": "self"})
        assert r.status_code == 200, r.text and r.json()["count"] >= 44
        listed = client.get("/api/dialectic/questions", params={"path": "self/holograph.cosm"}).json()
    cards = listed["open"]
    assert cards and all(c["to"] == "holder" for c in cards)
    q = cards[0]["id"]
    bad = client.post("/api/dialectic/check", json={"path": "self", "question": q,
                                                    "value": "write to me at ann@example.org"}).json()
    assert not bad["ok"] and "personal data" in bad["refusal"]
    r = client.post("/api/dialectic/answers", json={"path": "self", "answers": [
        {"question": q, "says": "write to me at ann@example.org"}]})
    assert r.status_code == 422 and "personal data" in r.json()["detail"]
    r = client.post("/api/dialectic/answers", json={"path": "self", "who": "Ann Example", "answers": [
        {"question": q, "says": "baking bread on a Sunday morning"}]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["written"] == "self" and out["recorded"] == [{"question": q, "state": "answered"}]
    led = dl.ledger_from_volume(mc.load_volume(project / "self"))
    sess = [s for s in led.sessions() if s["id"] == out["session"]]
    assert sess and sess[0]["with"] == {"to": "holder", "who": "the holder"}     # never the name the page sent
    r = client.post("/api/dialectic/settle", json={"path": "self"})
    assert r.status_code == 200, r.text
    snap = r.json()["job"]
    assert snap["state"] == "done" and snap["kind"] == "dialectic" and snap["result"]["mode"] == "rules"


# ---------------------------------------------------------------------------
# cosm_lint by format, and the tools
# ---------------------------------------------------------------------------

def test_cosm_lint_runs_a_fabulas_own_checks_and_a_holographs(project: Path):
    r = run(project, tool("cosm_lint", path="self"))
    assert r.ok and "ascribe/1" in r.body and "not run" not in r.body, r.body
    r = run(project, tool("cosm_lint", path="notes.md"))
    assert r.ok and "not run" not in r.body, r.body


def test_the_dialectic_tool_puts_one_or_two_and_records_the_persons_words(project: Path):
    r = run(project, tool("dialectic", path="notes.md"))
    assert not r.ok and "macrocosm-oes skill" in r.body
    enable_skill(project, "macrocosm-oes")
    r = run(project, tool("dialectic", path="notes.md", do="raise"))
    assert r.ok and r.body.startswith("raised "), r.body
    r = run(project, tool("dialectic", path="notes.md"))
    assert r.ok and r.body.count("  asks: ") == 2 and "Never answer for them" in r.body, r.body
    qid = r.body.split("\n- ", 1)[1].split(" ", 1)[0]
    r = run(project, tool("dialectic", path="notes.md", question=qid, says="the parish council"))
    assert r.ok and "recorded in notes.md.answers-" in r.body, r.body
    sitting = next(project.glob("notes.md.answers-*.cosm"))
    av = dl.read_answers_volume(sitting)
    assert av.session["through"] == "agent" and av.entries[0]["answers"][0]["says"] == "the parish council"
    r = run(project, tool("dialectic", path="notes.md", question=qid, says="again"))
    assert not r.ok and "not open" in r.body
    r = run(project, tool("dialectic", path="notes.md", question=qid, state="maybe"))
    assert not r.ok and "<state>" in r.body
    r = run(project, tool("dialectic", path="notes.md", do="settle"))
    assert not r.ok and "no reader is running" in r.body


def test_the_fabulac_tool_starts_and_follows_a_build_through_the_app(client: TestClient, project: Path):
    enable_skill(project, "macrocosm-oes")
    r = run(project, tool("fabulac", path="tiny-tool"))
    assert r.ok and "has no fabulac yet" in r.body, r.body
    r = run(project, tool("fabulac", path="tiny-tool", do="build"))
    assert r.ok and r.body.startswith("job cn"), r.body
    job = r.body.split()[1].rstrip(":")
    snap = wait_job(client, job)
    assert snap["state"] == "done" and snap["kind"] == "fabulac"
    r = run(project, tool("fabulac", path="tiny-tool"))
    assert r.ok and "survey, history landed; next read" in r.body, r.body
    r = run(project, tool("fabulac", path="tiny-tool", do="compile", what="code"))
    assert not r.ok and "a cshort needs a model" in r.body
    r = run(project, tool("fabulac", path="tiny-tool", do="cancel"))
    assert not r.ok and "is running" in r.body
    r = run(project, tool("fabulac", path="tiny-tool", do="paint"))
    assert not r.ok and "<do>" in r.body


def test_an_old_tool_name_runs_the_new_ones_runner_and_is_documented_nowhere(project: Path):
    from enough import prompt, retired_names
    for old, new in retired_names.TOOLS.items():
        assert old not in T._DISPATCH and new in T._DISPATCH
        enable_skill(project, "macrocosm-oes")
        text = prompt.tool_instructions(project, pal=True)
        assert f'<tool name="{old}">' not in text and f"`{old}`" not in text
    r = run(project, tool("emf_derive", path="notes.md"))
    assert r.name == "emf_derive"                     # said back under the name it was called by
    assert "unknown tool" not in r.body


def test_an_isograph_is_made_by_the_holders_program_and_its_release_recorded_first(client: TestClient,
                                                                                   project: Path):
    from enough import ascribe as A
    from tests.test_ascribe_module import OPEN_SELF, _blocks, _spec_holograph, write_nodes
    root = _spec_holograph(project)                                   # project/spec-self
    frag = next(b for b in _blocks("yaml") if b.startswith("# A/affinities.cosm"))
    nodes = mc.yaml_load(frag)["nodes"]
    nodes[0]["visibility"] = "public"
    write_nodes(root, "A/affinities.cosm", *nodes)
    (project / "open-self.thym").write_text(OPEN_SELF.format(v="1"), encoding="utf-8")
    r = client.post("/api/ascribe/isograph", json={"path": "spec-self", "program": "open-self.thym"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["isograph"].startswith("spec-self.isograph-") and (project / out["isograph"]).is_file()
    rel, = A.releases(root)
    assert rel["as"] == "isograph" and rel["trace"]["run"] == out["run"] and rel["items"]
    assert rel["sha256"] == __import__("hashlib").sha256((project / out["isograph"]).read_bytes()).hexdigest()
    again = client.post("/api/ascribe/isograph", json={"path": "spec-self", "program": "open-self.thym"})
    assert again.status_code == 409 and "epoch" in again.json()["detail"]
    assert client.post("/api/ascribe/isograph", json={"path": "notes.md",
                                                      "program": "open-self.thym"}).status_code == 400
    assert client.post("/api/ascribe/isograph", json={"path": "spec-self", "program": "nope"}).status_code == 404
