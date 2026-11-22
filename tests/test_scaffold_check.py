"""The scaffold's check as a job (0.8, lane W3-E5): FEED flags the words it does not know and invents no fix; a
model under the contract proposes fixes, flags grammar and judges every claim, and a claim it cannot check is
marked so, never passed; agent-free runs the rules pass and says so; the job lands every finding at once, and a
cancel writes none. The routes are driven through the real app (the model's URL is dead, so it runs by rules)."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import agent_free, broker
from enough import canon_jobs as CJ
from enough import composure as C
from enough import scaffold_check as K
from enough import scaffolder as SC
from enough.canon_derive import DeriveCancelled
from enough.server import create_app

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaffold_fixtures as F  # noqa: E402

#: The words FEED "knows" in these tests (FEED is not built in a test's home).
KNOWN = set("""a ask the to lease mill lane plot us for five years garden growers planning committee empty since
from october we have run school three and raised money its shed twelve beds tool store path wide enough wheelchair
four thousand pounds half parish fund our own members what town gets fresh food bank every week place learn outside
tidy instead of fenced off one who pays water do locks up two each evening sign in january built by march first
harvest july thank you forty neighbours already grow things raise raised pause here let them read before saying
anything else""".split())


def fake_known(words: set[str]) -> set[str]:
    return {w for w in words if w.lower() in KNOWN or w.lower().rstrip(".") in KNOWN}


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


@pytest.fixture()
def deck(project: Path) -> Path:
    path = F.deck(project)
    C.apply_ops(path, None, [{"op": "lock_scaffold", "empty": C.empty_boxes(C.load(path))}], source="ui")
    return path


ASK = SC.module_id("the-ask-in-one-sentence")
TOTAL = SC.module_id("the-total")


# ---------------------------------------------------------------------------
# The rules pass
# ---------------------------------------------------------------------------

def test_feed_flags_unknown_words_and_invents_no_fix(deck: Path):
    findings, notes = K.rules_pass(C.load(deck), known=fake_known)
    flagged = [(f["box"], f["quote"]) for f in findings]
    assert (ASK, "comittee") in flagged
    assert all(f["kind"] == "spelling" and f["fix"] is None and f["status"] == "open" for f in findings)
    # names, acronyms, web and mail addresses are not looked up
    assert not any(q in ("Mill", "Lane", "growers@example.org", "example") for _b, q in flagged)
    assert notes["not_checked"] == {} and notes["unknown"] == len(findings)


def test_words_of_leaves_out_names_acronyms_and_addresses():
    words = [w for _at, w in K.words_of("Mill Lane is near the BBC. See www.x.org or a@b.com; Ten more.")]
    assert words == ["Mill", "is", "near", "the", "See", "or", "more"]   # a sentence's first word is looked up


def test_feed_not_built_means_spelling_was_not_checked(deck: Path):
    findings, notes = K.rules_pass(C.load(deck), known=lambda _w: None)
    assert findings == [] and "FEED is not built" in notes["not_checked"]["spelling"]


def test_another_language_is_marked_not_checked_for_spelling(deck: Path):
    findings, _ = K.rules_pass(C.load(deck), known=fake_known, lang="fr")
    assert findings and all(f["status"] == C.CANNOT and f["quote"] == "" and f["fix"] is None for f in findings)
    assert all("not checked for spelling" in f["why"] for f in findings)
    assert len(findings) == len(K.written_boxes(C.load(deck)))


def test_a_box_mostly_unknown_to_feed_is_not_checked_rather_than_flagged_word_by_word(project: Path):
    path = F.build(project, "ten-slide-deck.md", "Mixed", {"the-total": "Wir bitten den Rat um diesen Garten hier."})
    findings, _ = K.rules_pass(C.load(path), known=fake_known)
    assert [(f["quote"], f["status"]) for f in findings if f["box"] == TOTAL] == [("", C.CANNOT)]


# ---------------------------------------------------------------------------
# The model pass, under the contract (a fake model)
# ---------------------------------------------------------------------------

def fake_model(answers: dict[str, object]):
    """A model that answers by the box text it is shown; anything it was not told about gets empty lists."""
    seen: list[list[dict]] = []

    def complete(messages, **kw):
        seen.append(messages)
        assert messages[0]["content"] == K.CONTRACT and kw.get("max_tokens") == K.MODEL_MAX_TOKENS
        user = messages[1]["content"]
        for needle, answer in answers.items():
            if needle in user:
                return (answer if isinstance(answer, str) else json.dumps(answer)), {}
        return json.dumps({"spelling": [], "grammar": [], "claims": []}), {}

    complete.seen = seen  # type: ignore[attr-defined]
    return complete


ANSWERS = {
    "We ask the comittee": {
        "spelling": [{"quote": "comittee", "fix": "committee", "why": "a double m"}],
        "grammar": [{"quote": "to us for", "fix": "to us, for", "why": "a pause"},
                    {"quote": "not in the text", "fix": "x"}],
        "claims": [{"quote": "five years", "verdict": "cannot be checked", "why": "the group's own plan"}]},
    "Empty since 2019": {"spelling": [], "grammar": [],
                         "claims": [{"quote": "Empty since 2019", "verdict": "wrong", "fix": "Empty since 2018",
                                     "why": "the council minutes say 2018"},
                                    {"quote": "2019", "verdict": "holds"}]},
    "Four thousand pounds": "I think this box is fine!",
    "Fresh food": {"spelling": [], "grammar": [],
                   "claims": [{"quote": "every week", "verdict": "probably"},
                              {"quote": "a misquote", "verdict": "cannot be checked", "why": "local"}]},
}


def test_the_model_pass_follows_the_contract(deck: Path):
    comp = C.load(deck)
    spelling, _ = K.rules_pass(comp, known=fake_known)
    model = fake_model(ANSWERS)
    found, counts = K.model_pass(comp, model, spelling)
    assert counts["boxes"] == len(K.written_boxes(comp)) == len(model.seen)
    ask_spell = next(f for f in spelling if f["box"] == ASK and f["quote"] == "comittee")
    assert ask_spell["fix"] == "committee" and ask_spell["pass"] == "model"
    by = [(f["kind"], f["quote"], f["status"], f["fix"]) for f in found]
    assert ("grammar", "to us for", "open", "to us, for") in by
    assert not any(q == "not in the text" for _k, q, _s, _f in by)          # a misquote is dropped
    assert ("truth", "five years", C.CANNOT, None) in by
    assert ("truth", "Empty since 2019", "open", "Empty since 2018") in by
    # an answer that cannot be read: the whole box's truth is not checked, never passed
    assert ("truth", "", C.CANNOT, None) in [(f["kind"], f["quote"], f["status"], f["fix"])
                                              for f in found if f["box"] == TOTAL]
    # a verdict outside the contract is not a pass; a misquoted claim is about the whole box
    fresh = [f for f in found if f["box"] == SC.module_id("gets-1")]
    assert [(f["quote"], f["status"]) for f in fresh] == [("every week", C.CANNOT), ("", C.CANNOT)]
    assert counts["holds"] == 1 and counts["unread"] == 1 and counts["claims"] == 5
    # the unknown words FEED flagged are named to the model
    assert "comittee" in next(m[1]["content"] for m in model.seen if "We ask" in m[1]["content"])


def test_parse_answer_reads_a_fenced_object_and_refuses_anything_else():
    assert K.parse_answer('```json\n{"claims": [], "grammar": [{"quote": "a"}]}\n```')["grammar"] == [{"quote": "a"}]
    assert K.parse_answer('Sure: {"claims": []} done') == {"spelling": [], "grammar": [], "claims": []}
    assert K.parse_answer('{"grammar": []}') is None            # no claims list: the contract was not kept
    assert K.parse_answer("no json") is None


# ---------------------------------------------------------------------------
# The job
# ---------------------------------------------------------------------------

def test_the_job_with_a_fake_model_lands_every_finding_at_once(deck: Path):
    out = K.run_check(deck, "rness/io/composure/a-garden-on-mill-lane.comp", mode="model", why="ok",
                      complete=fake_model(ANSWERS), known=fake_known)
    assert out["mode"] == "model" and out["passes"] == ["rules", "model"] and out["not_checked"] == {}
    fs = C.list_findings(deck)
    assert len(fs) == out["findings"] == len(out["added"])
    assert {f["kind"] for f in fs} == {"spelling", "grammar", "truth"}
    stamp = C.load_comments(deck)["check"]
    assert stamp["mode"] == "model" and stamp["version"] == 1 and stamp["at"].endswith("Z")
    # the person takes the spelling fix on the locked scaffold
    fid = next(f["id"] for f in fs if f["quote"] == "comittee")
    C.answer_finding(deck, fid, "accept")
    assert "the committee to" in C.box_text(C.load(deck).module(ASK))
    # a second run does not add again what was answered or cannot be checked
    again = K.run_check(deck, "x.comp", mode="model", why="ok", complete=fake_model(ANSWERS), known=fake_known)
    cannot = [f for f in C.list_findings(deck) if f["status"] == C.CANNOT]
    assert len(cannot) == len({(f["box"], f["quote"]) for f in cannot})
    assert fid not in again["added"]


def test_agent_free_runs_the_rules_pass_and_says_so(deck: Path):
    out = K.run_check(deck, "x.comp", mode="rules", why=agent_free.REASON, complete=None, known=fake_known)
    assert out["mode"] == "rules" and out["passes"] == ["rules"]
    assert out["message"].startswith("agent-free: ") and "grammar and truth not checked" in out["message"]
    assert "no claim was passed" in out["not_checked"]["truth"] and "agent-free" in out["not_checked"]["grammar"]
    assert {f["kind"] for f in C.list_findings(deck)} == {"spelling"}
    assert C.load_comments(deck)["check"]["reason"] == agent_free.REASON


def test_the_check_reads_only_a_locked_scaffold(project: Path):
    path = F.deck(project)
    with pytest.raises(K.CheckError, match="lock it first") as e:
        K.run_check(path, "x.comp", mode="rules", known=fake_known)
    assert e.value.status == 409


def test_a_cancelled_check_writes_nothing(deck: Path):
    calls = {"n": 0}

    def check() -> None:
        calls["n"] += 1
        if calls["n"] >= 3:
            raise DeriveCancelled()

    with pytest.raises(DeriveCancelled, match="after box 2 of"):
        K.run_check(deck, "x.comp", mode="model", why="ok", complete=fake_model(ANSWERS), known=fake_known,
                    check=check)
    assert C.list_findings(deck) == [] and "check" not in C.load_comments(deck)


def test_the_job_runs_as_a_canon_job_of_kind_scaffold(deck: Path):
    assert K.JOB_KIND in CJ.KINDS
    seen: list[dict] = []

    async def go() -> dict:
        jobs = CJ.CanonJobs(emit=lambda _e, snap: seen.append(snap))
        snap = jobs.start(kind="scaffold", path="x.comp", mode="model", key=str(deck),
                          work=lambda ctx: K.run_check(deck, "x.comp", mode="model", why="ok",
                                                       complete=fake_model(ANSWERS), known=fake_known,
                                                       progress=ctx.progress, check=ctx.check))
        for _ in range(400):
            await asyncio.sleep(0.01)
            snap = jobs.snapshot(snap["id"])
            if snap["state"] not in CJ.ACTIVE:
                return snap
        raise AssertionError(snap)

    snap = asyncio.run(go())
    assert snap["state"] == "done" and snap["kind"] == "scaffold", snap
    assert snap["result"]["passes"] == ["rules", "model"] and snap["message"].startswith("checked ")
    assert any(s.get("phase") == "model" for s in seen)


# ---------------------------------------------------------------------------
# The routes, through the real app
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"), ("ENOUGH_CANON_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"), ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    monkeypatch.setattr(K, "feed_known", fake_known)
    proj = tmp_path / "project"
    proj.mkdir()
    F.deck(proj)
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app, headers={"X-Enough-Api": "1"}) as c:
        c._project = proj  # type: ignore[attr-defined]
        yield c


REL = "rness/io/composure/a-garden-on-mill-lane.comp"


def wait_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {snap}")


def test_the_routes_lock_check_accept_decline_and_unlock(client: TestClient):
    st = client.get("/api/composure/scaffold", params={"path": REL}).json()
    assert st["locked"] is False and st["exports"] == ["pptx", "pdf"] and st["empty"]
    assert client.post("/api/composure/scaffold/check", json={"path": REL}).status_code == 409
    r = client.post("/api/composure/scaffold/lock", json={"path": REL, "empty": st["empty"][1:]})
    assert r.status_code == 400 and "still empty" in r.json()["detail"]
    r = client.post("/api/composure/scaffold/lock", json={"path": REL, "empty": st["empty"]})
    assert r.status_code == 200 and r.json()["locked"] is True
    # the ops door refuses a change while locked, and a readvisor at all
    r = client.post("/api/composure/ops", json={"path": REL, "ops": [{"op": "remove_module", "id": ASK}]})
    assert r.status_code == 400 and "locked" in r.json()["detail"]
    r = client.post("/api/composure/scaffold/check", json={"path": REL})
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert job["kind"] == "scaffold" and job["mode"] == "rules"
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and "grammar and truth not checked" in snap["message"], snap
    st = client.get("/api/composure/scaffold", params={"path": REL}).json()
    assert st["check"]["mode"] == "rules" and st["job"] is None
    spell = next(f for f in st["findings"] if f["quote"] == "comittee")
    assert spell["fix"] is None
    r = client.post("/api/composure/scaffold/accept", json={"path": REL, "finding": spell["id"]})
    assert r.status_code == 409 and "no fix" in r.json()["detail"]
    r = client.post("/api/composure/scaffold/decline", json={"path": REL, "finding": spell["id"]})
    assert r.status_code == 200 and r.json()["finding"]["status"] == "declined"
    assert client.post("/api/composure/scaffold/decline", json={"path": REL, "finding": "f99"}).status_code == 404
    # a fix the person accepts (a finding with one, as a model would have proposed)
    added = C.add_finding(client._project / REL, {"box": ASK, "kind": "spelling", "quote": "comittee",
                                                  "fix": "committee"})
    r = client.post("/api/composure/scaffold/accept", json={"path": REL, "finding": added["finding"]["id"]})
    assert r.status_code == 200 and r.json()["changed"] == [ASK], r.text
    r = client.delete("/api/composure/comments", params={"path": REL, "id": added["id"]})
    assert r.status_code == 409
    r = client.post("/api/composure/scaffold/unlock", json={"path": REL})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"].endswith("-v2.comp") and body["parent"] == REL and body["version"] == 2
    assert body["state"]["locked"] is False and len(body["state"]["findings"]) == len(st["findings"]) + 1


def test_the_check_route_under_agent_free(client: TestClient):
    path = agent_free.ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({agent_free.KEY: True}), encoding="utf-8")
    st = client.get("/api/composure/scaffold", params={"path": REL}).json()
    client.post("/api/composure/scaffold/lock", json={"path": REL, "empty": st["empty"]})
    r = client.post("/api/composure/scaffold/check", json={"path": REL, "mode": "auto"})
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap.get("reason") == "agent-free" and snap["result"]["reason"] == "agent-free", snap
    assert snap["message"].startswith("agent-free: ")
    r = client.post("/api/composure/scaffold/check", json={"path": REL, "mode": "model"})
    assert r.status_code == 409
