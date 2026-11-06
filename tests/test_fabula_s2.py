"""Lane S2 of the 0.6 fabula round: the server's follow-ups.

1. A job with no route is local (pins P6: "Nothing reaches a cloud model that the person did not choose for that
   job"): with the chat on the cloud slot and the cloud gate open, every entry point that starts a model job without a
   `route` asks llama-server or runs by rules, and never the cloud. One test per entry point.
2. `GET /api/fabula/suggest`; 3. the tree's old twin; 4. a build's outline says `message` in its result; 5. `GET
   /api/fabula/models`; 6. a compile's `flavour` and `what` from the first snapshot; 7. a queued build's first
   `progress`.

The projects, clients and stand-ins are the neighbouring tests' (every seam in tmp_path; tests/conftest.py)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon_tools as CT, cloud, llm, macrocosm, models, server, thym_host
from enough.server import create_app
from tests.test_canon_derive import ATEM_YAML, good
from tests.test_canon_derive_api import FIX, client, project, start, wait_job  # noqa: F401
from tests.test_canon_tools import run, tool
from tests.test_fabula_writers import cloud_open, lock_seen  # noqa: F401

REPO = Path(__file__).resolve().parent.parent
TINY = REPO / "tests" / "fixtures" / "thym" / "inputs" / "tiny-tool"
INPUTS = REPO / "tests" / "fixtures" / "thym" / "inputs"
SICK_ROSE = (FIX.parent / "fabula" / "poems" / "the-sick-rose.txt").read_text(encoding="utf-8")


def head(path: Path) -> dict:
    return macrocosm.yaml_load(path.read_text(encoding="utf-8"))


def on_the_cloud_slot() -> None:
    Path(models.LIVE_STATE).write_text(json.dumps({"current": "opro-api"}), encoding="utf-8")


@pytest.fixture
def cloud_slot(monkeypatch: pytest.MonkeyPatch) -> dict:
    """The chat on the cloud slot with the gate open (every cloud call recorded in `cloud`); `llm.complete` (the
    chat's own door, which would take the cloud) refuses to be called; llama-server answers through
    `llm.complete_local` with the canned fabula and atem (recorded in `local`), or is down when `up` is False."""
    on_the_cloud_slot()
    seen = {"cloud": cloud_open(monkeypatch), "local": [], "up": True}

    def complete_local(messages, *, llm_url, **kw):
        seen["local"].append(messages)
        system = messages[0]["content"]
        if system.startswith("You write the atem"):
            return ATEM_YAML, {"model": "here-model", "route": "local"}
        if system.startswith("You write a text back"):
            return "# The orchard\n\nProse from here.\n", {"model": "here-model", "route": "local"}
        repair = "did not pass the checks" in messages[-1]["content"]
        return good("axiom" if repair else "certain"), {"model": "here-model", "route": "local",
                                                         "finish_reason": "stop"}

    def chat_door(*a, **kw):
        raise AssertionError("a job with no route took the chat's door (the cloud slot)")

    monkeypatch.setattr(llm, "complete_local", complete_local)
    monkeypatch.setattr(llm, "complete", chat_door)
    monkeypatch.setattr(llm, "check_llm_reachable",
                        lambda url, timeout=3.0: (True, "ok") if seen["up"] else (False, "connection refused"))
    return seen


# ---------------------------------------------------------------------------
# 1. No route is local: one test per entry point
# ---------------------------------------------------------------------------

def test_derive_with_no_route_on_the_cloud_slot_runs_here(client: TestClient, project: Path, cloud_slot: dict,
                                                          lock_seen: list):
    job = start(client, "/api/fabula/derive", {"path": "notes.md"})
    assert job["mode"] == "model" and job["route"] == "local" and lock_seen[-1] is not None
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    assert snap["result"]["route"] == "local" and head(project / "notes.md.fabulan.cosm")["derived"]["route"] == "local"
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_derive_with_no_route_and_no_model_here_runs_by_rules_not_on_the_cloud(client: TestClient, project: Path,
                                                                                cloud_slot: dict):
    cloud_slot["up"] = False
    job = start(client, "/api/fabula/derive", {"path": "notes.md"})
    assert job["mode"] == "rules" and "route" not in job
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and snap["result"]["mode"] == "rules", snap
    assert cloud_slot["cloud"] == [] and cloud_slot["local"] == []


def test_a_file_atem_with_no_route_on_the_cloud_slot_runs_here(client: TestClient, cloud_slot: dict):
    for url, body in (("/api/fabula/derive", {"path": "hello.md", "what": "atem"}),
                      ("/api/canon/atem", {"path": "notes.md"})):
        job = start(client, url, body)
        assert job["mode"] == "model" and job["route"] == "local", (url, job)
        snap = wait_job(client, job["id"])
        assert snap["state"] == "done", snap
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_a_passage_atem_with_no_route_on_the_cloud_slot_runs_here(client: TestClient, cloud_slot: dict):
    job = start(client, "/api/canon/atem", {"text": "A passage about the orchard and its long record of trees."})
    assert job["route"] == "local"
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and snap["result"]["route"] == "local", snap
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_a_short_compile_with_no_route_on_the_cloud_slot_runs_here(client: TestClient, project: Path,
                                                                   cloud_slot: dict):
    job = start(client, "/api/fabula/compile", {"path": "rain.cosm"})
    assert job["mode"] == "model" and job["route"] == "local"
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    assert head(project / "rain.cosm")["shorts"][0]["route"] == "local"
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_the_fabula_derive_tool_with_no_route_on_the_cloud_slot_runs_here(project: Path, cloud_slot: dict):
    CT.configure(llm_url="http://127.0.0.1:9")
    r = run(project, tool("fabula_derive", path="notes.md"))
    assert r.ok, r.body
    assert head(project / "notes.md.fabulan.cosm")["derived"]["route"] == "local"
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_the_atem_tool_with_no_route_on_the_cloud_slot_runs_here(project: Path, cloud_slot: dict):
    CT.configure(llm_url="http://127.0.0.1:9")
    r = run(project, tool("atem", path="notes.md"))
    assert r.ok, r.body
    assert cloud_slot["cloud"] == [] and cloud_slot["local"]


def test_the_tools_with_no_route_and_no_model_here_write_a_scaffold_not_a_cloud_call(project: Path,
                                                                                     cloud_slot: dict):
    CT.configure(llm_url="http://127.0.0.1:9")
    cloud_slot["up"] = False
    r = run(project, tool("fabula_derive", path="notes.md"))
    assert r.ok and "scaffold" in r.body, r.body
    assert cloud_slot["cloud"] == [] and cloud_slot["local"] == []


@pytest.fixture
def code_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A project with a folder of Python (`tiny-tool/`) and a text with its old-named fabula (`notes.md`), the
    fabulac tests' and the dialectic tests' fixtures."""
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copytree(TINY, proj / "tiny-tool")
    for name in ("notes.md", "notes.md.cosm"):
        shutil.copyfile(INPUTS / name, proj / name)
    from enough import skeleton
    skeleton.ensure_skeleton(proj)
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        c._project = proj  # type: ignore[attr-defined]
        yield c


def test_a_fabulac_build_with_no_route_on_the_cloud_slot_never_asks_the_cloud(code_client: TestClient,
                                                                              cloud_slot: dict):
    cloud_slot["up"] = False
    body = code_client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()
    assert body["job"]["mode"] == "rules" and "route" not in body["job"]
    snap = wait_job(code_client, body["job"]["id"])
    assert snap["state"] == "done" and snap["result"]["refusal"]["program"] == "read-every-file", snap
    assert "local route" in snap["result"]["refusal"]["message"]
    assert cloud_slot["cloud"] == []


def test_a_fabulac_compile_with_no_route_on_the_cloud_slot_never_asks_the_cloud(code_client: TestClient,
                                                                                cloud_slot: dict):
    cloud_slot["up"] = False
    wait_job(code_client, code_client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()["job"]["id"])
    r = code_client.post("/api/fabula/compile", json={"path": "tiny-tool"})
    assert r.status_code == 409 and "a cshort needs a model" in r.json()["detail"]
    r = code_client.post("/api/fabula/compile", json={"path": "tiny-tool", "what": "line"})
    snap = wait_job(code_client, r.json()["job"]["id"])
    assert snap["state"] == "done" and snap["mode"] == "rules", snap
    assert cloud_slot["cloud"] == []


def test_a_settle_with_no_route_on_the_cloud_slot_never_asks_the_cloud(code_client: TestClient, cloud_slot: dict):
    cloud_slot["up"] = False
    qs = code_client.get("/api/dialectic/questions", params={"path": "notes.md"}).json()
    first = qs["open"][0]
    r = code_client.post("/api/dialectic/answers", json={"path": "notes.md", "answers": [
        {"question": first["id"] or first["about"], "dont_know": True}]})
    assert r.status_code == 200, r.text
    r = code_client.post("/api/dialectic/settle", json={"path": "notes.md"})
    assert r.status_code == 200, r.text
    snap = wait_job(code_client, r.json()["job"]["id"])
    assert snap["state"] == "done" and snap["result"]["mode"] == "rules", snap
    assert cloud_slot["cloud"] == []


def test_route_cloud_said_is_unchanged(client: TestClient, project: Path, cloud_slot: dict, lock_seen: list):
    job = start(client, "/api/fabula/derive", {"path": "notes.md", "route": "cloud"})
    assert job["route"] == "cloud" and lock_seen[-1] is None
    assert wait_job(client, job["id"])["state"] == "done"
    assert cloud_slot["cloud"] and cloud_slot["local"] == []


# ---------------------------------------------------------------------------
# 2. The suggestion for a text with no twin
# ---------------------------------------------------------------------------

def test_the_suggestion_for_a_text_with_no_twin(client: TestClient, project: Path):
    (project / "rose.md").write_text(SICK_ROSE, encoding="utf-8")
    got = client.get("/api/fabula/suggest", params={"path": "rose.md"}).json()
    assert got == {"path": "rose.md", "suggested": "fabulap",
                   "why": "it reads as verse: short lines in stanzas, with no heading, code fence or table"}
    got = client.get("/api/fabula/suggest", params={"path": "hello.md"}).json()
    assert got == {"path": "hello.md", "suggested": "fabulan", "why": "it reads as prose"}
    # the twin route still answers 404 for it
    assert client.get("/api/fabula/twin", params={"path": "rose.md"}).status_code == 404
    # a converted original is read through its markdown twin's text, a twin through its text
    assert client.get("/api/fabula/suggest", params={"path": "memo.pdf"}).json()["suggested"] == "fabulan"
    r = client.get("/api/fabula/suggest", params={"path": "nope.md"})
    assert r.status_code == 404 and r.json()["detail"] == "no such file: nope.md"
    r = client.get("/api/fabula/suggest", params={"path": ""})
    assert r.status_code == 400 and r.json()["detail"] == "missing path"
    r = client.get("/api/fabula/suggest", params={"path": "folder"})
    assert r.status_code == 400 and "is a folder" in r.json()["detail"]
    assert client.get("/api/fabula/suggest", params={"path": "../x.md"}).status_code == 400
    r = client.get("/api/fabula/suggest", params={"path": "pic.png"})
    assert r.status_code == 400 and "could not be read as text" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 3. The tree marks an old twin kept beside a new one
# ---------------------------------------------------------------------------

def test_the_tree_marks_an_old_twin(client: TestClient, project: Path):
    old = (FIX / "emf" / "notes.md.cosm").read_text(encoding="utf-8")
    (project / "notes.md.cosm").write_text(old, encoding="utf-8")
    (project / "notes.md.fabulan.cosm").write_text(
        old.replace("oes: emf/1\n", "oes: fabula/1\nflavour: fabulan\n", 1).replace(
            "id: emf/notes-md", "id: fabula/notes-md", 1), encoding="utf-8")
    nodes = {n["path"]: n for n in server.build_file_tree(project)}
    assert nodes["notes.md.cosm"]["old_twin"] == {"of": "notes.md", "twin": "notes.md.fabulan.cosm"}
    assert "old_twin" not in nodes["notes.md"] and "old_twin" not in nodes["hello.md"]
    html = client.get("/api/files").text
    row = next(li for li in html.split("<li ") if 'data-path="notes.md.cosm"' in li)
    assert 'data-old-twin="notes.md.fabulan.cosm"' in row and 'data-old-twin-of="notes.md"' in row
    assert html.count("data-old-twin=") == 1


# ---------------------------------------------------------------------------
# 4. A build that stops at the outline says so in its result; 6. a compile's flavour and what; 7. first progress
# ---------------------------------------------------------------------------

def test_an_outline_build_says_its_message_in_the_result_and_its_first_progress(code_client: TestClient):
    body = code_client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()
    first = body["job"]
    assert first["progress"]["stage"] == "survey" and first["progress"]["n"] == 1 and first["progress"]["of"] == 5
    snap = wait_job(code_client, first["id"])
    res = snap["result"]
    assert res["message"] == snap["message"] and "survey, history landed" in res["message"]
    assert res["refusal"]["message"] and "read-every-file waits" in res["message"]


def test_a_fabulacs_compile_says_its_flavour_and_what_from_the_first_snapshot(code_client: TestClient):
    wait_job(code_client, code_client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()["job"]["id"])
    job = code_client.post("/api/fabula/compile", json={"path": "tiny-tool", "what": "overview"}).json()["job"]
    assert (job["kind"], job["flavour"], job["what"]) == ("compile", "fabulac", "overview")
    snap = wait_job(code_client, job["id"])
    assert (snap["flavour"], snap["what"]) == ("fabulac", "overview") and snap["result"]["message"] == snap["message"]


def test_a_texts_compile_says_its_flavour_and_what_from_the_first_snapshot(client: TestClient):
    # a text's compile: the fabula's flavour (an emf/1 or one that says none reads fabulan), and `short`
    job = start(client, "/api/fabula/compile", {"path": "rain.cosm"})
    assert (job["kind"], job["flavour"], job["what"]) == ("compile", "fabulan", "short")
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and "message" not in snap["result"], "a text's compile result is as before"


# ---------------------------------------------------------------------------
# 5. The model line's facts in one call
# ---------------------------------------------------------------------------

def test_the_model_line_facts(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # nothing running here, the gate shut for want of a key: no vendor named, no secret
    monkeypatch.setattr(cloud, "gate_status", lambda: {"open": False, "reason": "no OpenRouter key is configured",
                                                       "denial": "error: set a key", "model_id": "cfg/model"})
    got = client.get("/api/fabula/models").json()
    assert got == {"agent_free": False, "local": {"running": False, "model": "g40-04", "window": None},
                   "cloud": {"open": False, "model": None, "window": None, "reason": "no cloud key is configured"}}
    # llama-server up, the gate open
    cloud_open(monkeypatch)
    monkeypatch.setattr(llm, "check_llm_reachable", lambda url, timeout=3.0: (True, "ok"))
    monkeypatch.setattr(thym_host, "local_model_id", lambda llm_url=None: "g40-04")
    monkeypatch.setattr(thym_host, "_read_n_ctx", lambda llm_url: 16384)
    got = client.get("/api/fabula/models").json()
    assert got == {"agent_free": False, "local": {"running": True, "model": "g40-04", "window": 16384},
                   "cloud": {"open": True, "model": "cfg/model", "window": thym_host.CLOUD_WINDOW, "reason": None}}
    assert "key" not in json.dumps(got).replace("cloud key", "")


def test_the_model_line_under_agent_free_asks_nothing(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def asked(*a, **kw):
        raise AssertionError("agent-free asks no gate and no model")

    monkeypatch.setattr(cloud, "gate_status", asked)
    monkeypatch.setattr(llm, "check_llm_reachable", asked)
    path = agent_free.ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({agent_free.KEY: True}), encoding="utf-8")
    got = client.get("/api/fabula/models").json()
    assert got == {"agent_free": True, "local": {"running": False, "model": None, "window": None},
                   "cloud": {"open": False, "model": None, "window": None, "reason": "agent-free mode is on"}}
