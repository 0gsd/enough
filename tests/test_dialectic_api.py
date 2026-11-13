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


def test_the_retired_tool_name_and_routes_are_gone(client: TestClient, project: Path):
    from enough import retired_names
    assert "emf_derive" not in retired_names.TOOLS and "what" not in retired_names.WORDS
    assert not any(old.startswith("/api/canon/") and old.rsplit("/", 1)[1] in ("emf", "derive", "compile")
               for _m, old, _n in retired_names.ROUTES)
    assert "emf_derive" not in T._DISPATCH and "fabula_derive" in T._DISPATCH
    r = run(project, tool("emf_derive", path="notes.md"))
    assert not r.ok and "unknown tool" in r.body
    for method, path in (("get", "/api/canon/emf"), ("post", "/api/canon/derive"), ("post", "/api/canon/compile")):
        kw = {"params": {"path": "notes.md"}} if method == "get" else {"json": {"path": "notes.md"}}
        assert getattr(client, method)(path, **kw).status_code == 404, path
    r = client.post("/api/fabula/derive", json={"path": "notes.md", "what": "emf"})
    assert r.status_code == 400                       # `what: emf` is no longer read as `what: fabula`

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


def test_an_allograph_is_made_by_the_holders_program_and_sent_nowhere(client: TestClient, project: Path):
    """`project h as allograph` through the route (Ascribe 14.6): the release recorded first, the allograph written
    beside the holograph under its run, the holograph's state given; a second in one epoch is allowed."""
    import shutil
    from enough import ascribe as A
    from tests.test_ascribe_module import OPEN_FOR_WORK, SAMPLE, _for_work
    root = project / "work-self"
    shutil.copytree(SAMPLE, root)
    _for_work(root)
    (project / "open-for-work.thym").write_text(OPEN_FOR_WORK, encoding="utf-8")
    r = client.post("/api/ascribe/allograph", json={"path": "work-self", "program": "open-for-work.thym"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["allograph"] == f"work-self.allograph-{out['run']}.json" and (project / out["allograph"]).is_file()
    assert out["document"]["expertise"] == [{"form": "sourdough", "kind": "skill", "marking": "stated",
                                             "strength": "strong"}]
    assert out["holograph"] == A.holograph_state(root)
    rel, = A.releases(root)
    assert rel["as"] == "allograph" and rel["trace"]["run"] == out["run"]
    assert rel["sha256"] == __import__("hashlib").sha256((project / out["allograph"]).read_bytes()).hexdigest()
    again = client.post("/api/ascribe/allograph", json={"path": "work-self", "program": "open-for-work.thym"})
    assert again.status_code == 200, again.text                     # more than one allograph in an epoch
    assert [r["as"] for r in A.releases(root)] == ["allograph", "allograph"]
    r = client.post("/api/ascribe/allograph", json={"path": "work-self", "program": "open-self.thym"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Lane S3: the state recorded, a candidate's source, closed questions, a dry raise, the event, the refusal's words
# ---------------------------------------------------------------------------

def _events(client: TestClient):
    """A queue on the app's server-sent stream, as a page's EventSource has one, and a reader of what reached it."""
    import asyncio
    q: asyncio.Queue = asyncio.Queue()
    client.app.state.session.subscribers.append(q)

    def seen(name: str, n: int = 1, timeout: float = 5.0) -> list[dict]:
        got: list[dict] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            while not q.empty():
                ev = q.get_nowait()
                if ev["event"] == name:
                    got.append(json.loads(ev["data"]))
            if len(got) >= n:
                return got
            time.sleep(0.02)
        return got
    return seen


def test_an_address_answered_i_dont_know_or_declined_is_reported_as_it_was_recorded(client: TestClient,
                                                                                     project: Path):
    shutil.copyfile(project / "notes.md.cosm", project / "again.cosm")      # the same open field, twice
    first = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    field = next(c["about"] for c in first["open"] if c["form"] == "pending" and "#" in c["about"])
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [
        {"question": field, "dont_know": True, "says": "no idea"}]})
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] == [{"question": field, "state": "unknown"}]
    r = client.post("/api/dialectic/answers", json={"path": "again.cosm", "answers": [
        {"question": field, "declined": True}]})
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] == [{"question": field, "state": "declined"}]
    assert D._state_of_entry({"about": field, "answers": [{"says": "compost", "value": "compost"}]}) == "answered"
    # a question asked by its id: as it was (its entry carries its state)
    client.post("/api/dialectic/raise", json={"path": "notes.md"})
    cards = [c["id"] for c in client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()["open"]
             if c["form"] == "question"]
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [
        {"question": cards[0], "dont_know": True}, {"question": cards[1], "declined": True}]})
    assert r.status_code == 200, r.text
    assert {x["question"]: x["state"] for x in r.json()["recorded"]} == {cards[0]: "unknown", cards[1]: "declined"}


def test_a_candidates_card_says_where_the_reading_saw_it(client: TestClient, project: Path):
    from tests.test_ascribe_module import JOURNAL_SHA, _land_journal
    assert client.post("/api/dialectic/raise", json={"path": "self"}).status_code == 200    # the bank's, beside
    got = _land_journal(project / "self")
    skill = next(i for i in got if i["id"] == "S:skill/splicing-an-eye-by-hand")
    listed = client.get("/api/dialectic/questions", params={"path": "self"}).json()
    card = next(c for c in listed["open"] if (c["item"] or {}).get("id") == skill["id"])
    assert card["candidate"] == {"text": "journal.md", "sha256": JOURNAL_SHA, "span": skill["span"],
                                 "confidence": skill["provenance"]["confidence"],
                                 "made": {"move": "propose", "run": "r1"}}
    from enough import ascribe as A
    led = A.Holograph(project / "self").led
    assert all((c["candidate"] is not None) == A._is_candidate(led.item((c["item"] or {}).get("id")) or {})
               for c in listed["open"])
    assert any(c["candidate"] is None for c in listed["open"])
    # anything else: null
    assert D.candidate_of({"id": "x", "provenance": {"mode": "manual", "state": "pending"}}) is None
    assert D.candidate_of({"id": "x", "provenance": {"mode": "derived", "state": "pending"}}) == {
        "text": None, "sha256": None, "span": None, "confidence": None, "made": None}


def test_the_listing_carries_closed_questions_newest_first_and_bounded(client: TestClient, project: Path,
                                                                       monkeypatch: pytest.MonkeyPatch):
    client.post("/api/dialectic/raise", json={"path": "notes.md"})
    listed = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert listed["closed"] == [] and listed["closed_total"] == 0
    a, b, c = [x["id"] for x in listed["open"] if x["form"] == "question"][:3]
    for q, extra in ((a, {"says": "the parish council"}), (b, {"dont_know": True})):
        r = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [{"question": q, **extra}]})
        assert r.status_code == 200, r.text
        time.sleep(1.1)                    # each sitting its own stamp: the order is the answers' time
    r = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [{"question": c,
                                                                                     "declined": True}]})
    assert r.status_code == 200, r.text
    # declined: closed at once (it may be asked again); answered and unknown: once settled
    mid = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert [x["id"] for x in mid["closed"]] == [c] and mid["closed"][0]["state"] == "declined"
    assert wait_job(client, client.post("/api/dialectic/settle", json={"path": "notes.md"}).json()["job"]["id"]
                    )["state"] == "done"
    after = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert after["closed_total"] == 3 and [x["id"] for x in after["closed"]] == [c, b, a]
    assert {x["state"] for x in after["closed"]} == {"answered", "unknown", "declined"}
    monkeypatch.setattr(D, "CLOSED_SHOWN", 2)
    cut = client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    assert [x["id"] for x in cut["closed"]] == [c, b] and cut["closed_total"] == 3


def test_a_dry_raise_counts_and_lands_nothing(client: TestClient, project: Path):
    twin = project / "notes.md.cosm"
    before = twin.read_bytes()
    r = client.post("/api/dialectic/raise", json={"path": "notes.md", "dry": True})
    assert r.status_code == 200, r.text
    dry = r.json()
    assert dry["dry"] is True and dry["count"] > 0 and sum(dry["by"].values()) == dry["count"]
    assert "raised" not in dry and twin.read_bytes() == before
    assert not list(project.glob("notes.md.answers-*"))
    real = client.post("/api/dialectic/raise", json={"path": "notes.md"}).json()
    assert real["count"] == dry["count"]
    assert client.post("/api/dialectic/raise", json={"path": "notes.md", "dry": True}).status_code == 409
    assert client.post("/api/dialectic/raise", json={"path": "notes.md", "dry": "yes"}).status_code == 400
    # a holograph: Ascribe's bank, of the holder alone, counted by bank entry; nothing written
    files = {p: p.read_bytes() for p in (project / "self").rglob("*") if p.is_file()}
    h = client.post("/api/dialectic/raise", json={"path": "self", "dry": True}).json()
    assert h["count"] >= 44 and sum(h["by"].values()) == h["count"]
    assert sum(n for k, n in h["by"].items() if k.startswith("ascribe")) == 44, h["by"]
    assert {p: p.read_bytes() for p in (project / "self").rglob("*") if p.is_file()} == files


def test_a_recorded_sitting_and_a_landed_settle_send_the_dialectic_event(client: TestClient, project: Path):
    seen = _events(client)
    client.post("/api/dialectic/raise", json={"path": "notes.md"})
    assert seen("dialectic") == [{"path": "notes.md.cosm", "session": None, "what": "raised"}]
    q = next(c["id"] for c in client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()["open"]
             if c["form"] == "question")
    out = client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [
        {"question": q, "says": "the parish council"}]}).json()
    assert seen("dialectic") == [{"path": "notes.md.cosm", "session": out["session"], "what": "recorded"}]
    # a refused sitting (nothing recorded) sends nothing
    assert client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [
        {"question": q, "says": "again"}]}).status_code == 422
    assert seen("dialectic", timeout=0.3) == []
    assert wait_job(client, client.post("/api/dialectic/settle", json={"path": "notes.md"}).json()["job"]["id"]
                    )["state"] == "done"
    assert seen("dialectic") == [{"path": "notes.md.cosm", "session": None, "what": "settled"}]
    # a holograph's settle, at once by rules
    client.post("/api/dialectic/raise", json={"path": "self"})
    assert seen("dialectic") == [{"path": "self", "session": None, "what": "raised"}]
    hq = next(c["id"] for c in client.get("/api/dialectic/questions", params={"path": "self"}).json()["open"])
    rec = client.post("/api/dialectic/answers", json={"path": "self", "answers": [
        {"question": hq, "says": "baking bread on a Sunday morning"}]}).json()
    assert client.post("/api/dialectic/settle", json={"path": "self"}).status_code == 200
    assert seen("dialectic", 2) == [{"path": "self", "session": rec["session"], "what": "recorded"},
                                    {"path": "self", "session": None, "what": "settled"}]
    # the agent's tool, recording through the app
    enable_skill(project, "macrocosm-oes")
    client.post("/api/dialectic/raise", json={"path": "notes.md"})
    nxt = next((c["id"] for c in client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()["open"]
                if c["form"] == "question"), None)
    assert nxt is not None
    r = run(project, tool("dialectic", path="notes.md", question=nxt, says="a parish in the hills"))
    assert r.ok, r.body
    got = seen("dialectic")
    assert len(got) == 1 and got[0]["what"] == "recorded" and got[0]["path"] == "notes.md.cosm" and got[0]["session"]
    # a question asked again (0.7): the same shape, no session
    assert client.post("/api/dialectic/ask-again", json={"path": "notes.md", "question": q}).status_code == 200
    assert seen("dialectic") == [{"path": "notes.md.cosm", "session": None, "what": "asked-again"}]
    # one refused sends nothing
    assert client.post("/api/dialectic/ask-again", json={"path": "notes.md", "question": "no-such"}).status_code == 404
    assert seen("dialectic", timeout=0.3) == []
    assert D.notify(None, "x", None, "recorded") is None                   # no app: nothing sent, nothing fails


def test_the_personal_data_refusal_says_how_to_name_people_without_the_retired_word(client: TestClient,
                                                                                     project: Path):
    from enough import ascribe as A
    assert "role" not in A.REFUSED_PII.lower() and "describe people by what they are to you" in A.REFUSED_PII
    assert "pseudonym" in A.REFUSED_PII and "nothing was written" in A.REFUSED_PII
    listed = client.get("/api/dialectic/questions", params={"path": "self"}).json()
    if not listed["open"]:
        client.post("/api/dialectic/raise", json={"path": "self"})
        listed = client.get("/api/dialectic/questions", params={"path": "self"}).json()
    bad = client.post("/api/dialectic/check", json={"path": "self", "question": listed["open"][0]["id"],
                                                    "value": "write to me at ann@example.org"}).json()
    assert not bad["ok"] and "describe people by what they are to you" in bad["refusal"]
