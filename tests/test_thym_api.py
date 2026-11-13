"""The Thym routes (0.5.0, `enough/thym_api.py`): `/api/thym/programs|program|compile|plan|run|runs|trace` and
`/api/canon/package|unpack|read`, through the app.

TestClient over `create_app(..., supervise=False)` with a dead llm_url (port 9), so `llm.reachable` reports no model
and every run is in rules mode unless a test stands in for the model (`llm.reachable` and `llm.complete`
monkeypatched). Every seam points inside tmp_path (conftest), the Thym root among them: no run lands in
~/enough/thym. No model is started.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon, llm, macrocosm as mc, models, skeleton
from enough import thym_host as H
from enough.server import create_app
from enough.thym import vault
from enough.thym.values import digest_path, list_digest

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "tests" / "fixtures" / "thym"
INPUTS = SUITE / "inputs"

COUNT = """thym 0

program count-words
  why: how long a text is, in words.

  takes story: text
  gives n: number

  give words story
end
"""

#: How a plan that asks is refused when no model answers (THYM.md 19): the count, the route, the first statement.
STORY_ASKS = "3 steps ask a model on the local route, the first `let f = derive story` (line 12)"

PACK = """thym 0

program pack-it
  why: a text and its twin, packaged as they are.

  takes story: text, f: fabula
  gives out: package

  give package story, f, nothing, nothing, nothing
end
"""


def wait_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished: {snap}")


def set_agent_free(on: bool) -> None:
    path = agent_free.ui_config_path()
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    cfg[agent_free.KEY] = on
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    for name in ("notes.md", "notes.md.cosm", "plain-letter.morph.cosm", "on-the-train.context.cosm"):
        shutil.copyfile(INPUTS / name, proj / name)
    shutil.copytree(INPUTS / "orchard-notes.thym", proj / "orchard-notes.thym")
    (proj / "tools").mkdir()
    (proj / "tools" / "count-words.thym").write_text(COUNT, encoding="utf-8")
    (proj / "tools" / "pack-it.thym").write_text(PACK, encoding="utf-8")
    (proj / "broken.thym").write_text("thym 0\n\nprogram oops\n", encoding="utf-8")
    (proj / "hello.md").write_text("# Hello\n\nA short note about the lane by the orchard.\n", encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), canon.root(), H.host_root(), models.LIVE_STATE):
        assert str(where).startswith(str(tmp_path)), where
    assert canon.emf_state(proj / "notes.md", proj / "notes.md.cosm") == "fresh"
    return proj


@pytest.fixture
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c


def start(client: TestClient, url: str, body: dict) -> dict:
    r = client.post(url, json=body)
    assert r.status_code == 200, r.text
    return r.json()["job"]


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------

def test_programs_lists_the_projects_and_the_shipped_three(client: TestClient):
    rows = client.get("/api/thym/programs").json()["programs"]
    by = {(r["where"], r["rel"]): r for r in rows}
    assert {r["rel"] for r in rows if r["where"] == "shipped"} >= {"open-house.thym", "publish-story.thym",
                                                                  "read-my-way.thym"}
    count = by[("project", "tools/count-words.thym")]
    assert count == {"name": "count-words", "where": "project", "rel": "tools/count-words.thym", "problem": None,
                     "version": 0, "steps": 1, "asks": 0,
                     "takes": [{"name": "story", "type": "text", "accepts": "a text (a markdown or plain file)"}],
                     "gives": {"name": "n", "type": "number"}, "outputs": [{"name": "n", "type": "number"}],
                     "why": "how long a text is, in words."}
    ps = by[("shipped", "publish-story.thym")]
    assert (ps["name"], ps["steps"], ps["asks"]) == ("publish-story", 7, 3)
    assert ps["gives"] == {"name": "out", "type": "package"} and ps["why"].startswith("a story leaves the house")
    broken = by[("project", "broken.thym")]
    assert set(broken) == {"name", "where", "rel", "problem"} and broken["problem"] and broken["name"] is None


def test_program_gives_its_source_and_its_volume(client: TestClient):
    r = client.get("/api/thym/program", params={"path": "publish-story.thym"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["name"], p["rel"]) == ("publish-story", "publish-story.thym")
    assert p["source"] == (SUITE / "programs" / "publish-story.thym").read_text(encoding="utf-8")
    assert p["why"].startswith("a story leaves the house")
    vol = p["volume"]
    assert vol["minicosm"] == "thym" and vol["catalog"]["kind"] == "program" and vol["refused"] is None
    kinds = {k["kind"] for m in vol["modules"] for k in m["kinds"]}
    assert {"program", "step"} <= kinds
    assert client.get("/api/thym/program", params={"path": "tools/count-words.thym"}).json()["name"] == "count-words"
    assert client.get("/api/thym/program", params={"path": "count-words"}).json()["rel"] == "tools/count-words.thym"
    assert client.get("/api/thym/program", params={"path": "nothing-like-it"}).status_code == 404
    # the cosm viewer's own routes load a program's volume by its file, and draw it
    assert client.get("/api/cosm", params={"path": "tools/count-words.thym"}).json()["catalog"]["kind"] == "program"


def test_compile_answers_ok_or_the_refusal_with_its_line(client: TestClient):
    ok = client.post("/api/thym/compile", json={"path": "tools/count-words.thym"}).json()
    assert ok == {"ok": True, "name": "count-words", "refusal": None, "refusals": [],
                  "estimate": {"steps": 1, "asks": 0, "largest_prompt": 0, "output_words": 0}, "version": 0,
                  "takes": [{"name": "story", "type": "text", "accepts": "a text (a markdown or plain file)"}],
                  "outputs": [{"name": "n", "type": "number"}]}
    bad = (SUITE / "bad" / "type.thym").read_text(encoding="utf-8")
    first = bad.split("\n", 1)[0].split()             # -- refused: compile type line 9
    r = client.post("/api/thym/compile", json={"text": bad}).json()
    assert r["ok"] is False and r["name"] is None
    assert (r["refusal"]["stage"], r["refusal"]["check"], r["refusal"]["line"]) == (first[2], first[3], int(first[5]))
    assert r["refusal"]["message"]
    assert client.post("/api/thym/compile", json={"path": "none.thym"}).status_code == 404


def test_plan_takes_the_shorthand_and_says_its_cost(client: TestClient):
    r = client.post("/api/thym/plan", json={"program": "count-words", "path": "notes.md"}).json()
    assert r["ok"] is True and r["refusal"] is None and r["mode"] == "rules" and r["fits"] is True
    assert r["atem"] == "count-words: 1 nodes, 0 ask a model; largest prompt 0 tokens, output budget 0 words"
    assert r["plan"]["kind"] == "plan" and r["plan"]["inputs"][0]["name"] == "story"
    assert r["plan"]["inputs"][0]["sha256"] == digest_path(INPUTS / "notes.md")
    asks = client.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md"}).json()
    assert asks["ok"] is False and asks["atem"].startswith("publish-story: 7 nodes, 3 ask a model")
    assert (asks["refusal"]["stage"], asks["refusal"]["check"]) == ("plan", "no-model")
    assert asks["refusal"]["message"] == STORY_ASKS + "; no model is running"
    assert client.post("/api/thym/plan", json={"program": "count-words", "path": "missing.md"}).status_code == 404
    assert client.post("/api/thym/plan", json={"program": "count-words",
                                               "inputs": {"nope": "notes.md"}}).status_code == 400


def test_bundle_gives_the_page_what_its_runtime_reads_and_writes_nothing(client: TestClient, project: Path):
    before = sorted(p.name for p in project.iterdir())
    b = client.post("/api/thym/bundle", json={"program": "count-words", "path": "notes.md"})
    assert b.status_code == 200, b.text
    b = b.json()
    assert set(b) >= {"plan", "program", "version", "decls", "inputs", "manifests", "route", "environment"}
    assert b["plan"]["kind"] == "plan" and b["program"] == COUNT and b["version"] == 0
    story = b["inputs"]["story"]
    assert story["type"] == "text" and story["path"].endswith("notes.md")
    assert story["text"] == (INPUTS / "notes.md").read_text(encoding="utf-8")
    assert "words" in b["decls"] and b["route"] == "local"
    assert b["environment"]["agent_free"] is True and b["environment"]["model"] == "none"
    # a plan that asks is bundled all the same: the page's runtime refuses it in the server's words
    asks = client.post("/api/thym/bundle", json={"program": "publish-story", "path": "notes.md"}).json()
    assert any(n.get("asks") is True for n in asks["plan"]["nodes"] if isinstance(n, dict))
    assert client.post("/api/thym/bundle", json={"program": "count-words", "path": "missing.md"}).status_code == 404
    assert client.post("/api/thym/bundle", json={"program": "count-words",
                                                 "inputs": {"nope": "notes.md"}}).status_code == 400
    assert client.post("/api/thym/bundle", json={"program": "count-words", "path": "notes.md",
                                                 "route": "elsewhere"}).status_code == 400
    assert sorted(p.name for p in project.iterdir()) == before
    assert not H.host_root().exists(), "a bundle runs nothing, so it makes no runs folder"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_the_page_runs_a_bundle_to_the_same_bytes_as_the_server(client: TestClient, project: Path):
    import subprocess
    b = client.post("/api/thym/bundle", json={"program": "count-words", "path": "notes.md"}).json()
    req = {"bundle": b, "runId": "2026-11-12-0000-abcd", "now": "2026-11-12T00:00:00Z"}
    p = subprocess.run([shutil.which("node"), str(REPO / "tests" / "thym_js_harness.js")], input=json.dumps(req),
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    page = json.loads(p.stdout)
    assert page["outcome"] == "landed" and page["refusal"] is None
    job = start(client, "/api/thym/run", {"program": "count-words", "path": "notes.md"})
    done = wait_job(client, job["id"])
    landed = Path(done["result"]["outputs"][0]["path"]).read_bytes()
    import base64
    (name, raw), = page["files"].items()
    assert name == "outputs/n.txt" and base64.b64decode(raw) == landed
    asks = client.post("/api/thym/bundle", json={"program": "publish-story", "path": "notes.md"}).json()
    p = subprocess.run([shutil.which("node"), str(REPO / "tests" / "thym_js_harness.js")],
                       input=json.dumps({"bundle": asks}), capture_output=True, text=True, timeout=120)
    refused = json.loads(p.stdout)
    assert refused["outcome"] == "refused" and refused["refusal"]["check"] == "agent-free"
    assert refused["refusal"]["message"] == STORY_ASKS + "; agent-free is on"


# ---------------------------------------------------------------------------
# Runs, the runs list, traces
# ---------------------------------------------------------------------------

def test_a_deterministic_run_lands_beside_its_input_and_is_listed(client: TestClient, project: Path):
    assert client.get("/api/thym/runs").json() == {"runs": []}
    assert not H.host_root().exists(), "asking for runs never makes the root"
    job = start(client, "/api/thym/run", {"program": "count-words", "path": "notes.md"})
    assert job["kind"] == "thym" and job["path"] == "notes.md" and job["mode"] == "rules"
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    res = done["result"]
    assert res["outcome"] == "landed" and res["mode"] == "rules"
    assert res["atem"].startswith("ran count-words on notes.md in ") and "all checks green" in res["atem"]
    out = res["outputs"]
    assert [o["name"] for o in out] == ["n"] and out[0]["rel"] == "notes.n.txt"
    assert (project / "notes.n.txt").read_text(encoding="utf-8") == Path(out[0]["path"]).read_text(encoding="utf-8")
    assert Path(res["trace"]).is_file() and str(Path(res["trace"])).startswith(str(H.host_root()))
    assert done["progress"] == {"node": 1, "of": 1, "name": "words story", "move": "words", "state": "done"}
    runs = client.get("/api/thym/runs").json()["runs"]
    assert runs[0]["run"] == res["run"] and runs[0]["program"] == "count-words"
    assert runs[0]["inputs"] == [{"name": "story", "rel": "notes.md", "path": str((project / "notes.md").resolve())}]
    assert runs[0]["outcome"] == "landed" and runs[0]["atem"] == res["atem"] and runs[0]["replay_of"] is None
    tr = client.get("/api/thym/trace", params={"run": res["run"]}).json()
    assert tr["run"] == res["run"] and tr["outcome"] == "landed" and tr["atem"] == res["atem"]
    assert tr["volume"]["catalog"]["kind"] == "trace" and tr["volume"]["minicosm"] == "thym"
    assert client.get("/api/cosm", params={"path": tr["path"]}).json()["catalog"]["kind"] == "trace"
    assert client.get("/api/thym/trace", params={"run": "no-such-run"}).status_code == 404
    assert client.get("/api/thym/trace", params={"run": "../etc"}).status_code == 400


def test_a_package_a_run_makes_lands_in_both_forms(client: TestClient, project: Path):
    job = start(client, "/api/thym/run", {"program": "tools/pack-it.thym",
                                          "inputs": {"story": "notes.md", "f": "notes.md.cosm"}})
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    out = done["result"]["outputs"][0]
    assert (out["rel"], out["folder"]) == ("notes.package.cosm", "notes.thym")
    assert (project / "notes.package.cosm").read_bytes() == Path(out["path"]).read_bytes()
    assert sorted(p.name for p in (project / "notes.thym").iterdir()) == ["fabula.cosm", "package.cosm", "text.md"]
    cat = mc.yaml_load(canon.project_catalog(project, write=False))
    notes = next(n for n in cat["nodes"] if n["path"] == "notes.md")
    assert notes["package"] == {"path": "notes.package.cosm", "folder": "notes.thym"}


def test_a_plan_that_asks_is_refused_in_rules_mode_and_scaffolds_run_when_asked(client: TestClient, project: Path):
    r = client.post("/api/thym/run", json={"program": "publish-story", "path": "notes.md"})
    assert r.status_code == 409 and r.json()["detail"] == (STORY_ASKS + "; no model is running")
    job = start(client, "/api/thym/run", {"program": "publish-story", "path": "notes.md", "mode": "rules"})
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    res = done["result"]
    assert res["outcome"] == "landed" and res["outputs"][0]["rel"] == "notes.package.cosm"
    assert "rules" in res["atem"]
    r = client.post("/api/thym/run", json={"program": "read-my-way", "mode": "rules",
                                           "inputs": {"p": "orchard-notes.thym", "mine": "plain-letter.morph.cosm",
                                                      "now": "on-the-train.context.cosm"}})
    assert r.status_code == 409 and "no scaffold" in r.json()["detail"]
    assert client.post("/api/thym/run", json={"program": "count-words", "path": "notes.md",
                                              "mode": "model"}).status_code == 409


def test_agent_free_refuses_a_reading_and_a_plan_that_asks_and_runs_one_that_does_not(project: Path):
    set_agent_free(True)
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        r = c.post("/api/canon/read", json={"path": "notes.md", "morph": "plain-letter.morph.cosm"})
        assert r.status_code == 409 and r.json()["detail"].startswith("agent-free mode:")
        r = c.post("/api/thym/run", json={"program": "publish-story", "path": "notes.md"})
        assert r.status_code == 409 and r.json()["detail"] == STORY_ASKS + "; agent-free is on"
        plan = c.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md"}).json()
        assert plan["refusal"]["check"] == "agent-free"
        job = start(c, "/api/thym/run", {"program": "count-words", "path": "notes.md"})
        assert job["mode"] == "rules" and job["reason"] == "agent-free"
        done = wait_job(c, job["id"])
        assert done["state"] == "done" and done["result"]["reason"] == "agent-free"
        assert c.get("/api/thym/programs").status_code == 200
        assert c.post("/api/thym/compile", json={"path": "tools/count-words.thym"}).status_code == 200


# ---------------------------------------------------------------------------
# Packages: export and import
# ---------------------------------------------------------------------------

def test_export_needs_a_fresh_twin(client: TestClient, project: Path):
    r = client.post("/api/canon/package", json={"path": "hello.md"})
    assert r.status_code == 409 and r.json()["detail"].startswith("derive the twin first")
    (project / "notes.md").write_text((INPUTS / "notes.md").read_text(encoding="utf-8") + "\nOne more line.\n",
                                      encoding="utf-8")
    r = client.post("/api/canon/package", json={"path": "notes.md"})
    assert r.status_code == 409 and "stale" in r.json()["detail"]
    assert not (project / "notes.package.cosm").exists()


def test_export_writes_both_forms_through_the_package_move(client: TestClient, project: Path):
    r = client.post("/api/canon/package", json={"path": "notes.md"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["package"], out["folder"]) == ("notes.package.cosm", "notes.thym") and "key" not in out
    single = mc.yaml_load((project / "notes.package.cosm").read_text(encoding="utf-8"))
    assert [c["role"] for c in single["contents"]] == ["text", "fabula", "context"]
    assert single["contents"][0]["text"].encode("utf-8") == (INPUTS / "notes.md").read_bytes()
    assert single["made"]["program"]["name"] == "export" and single["made"]["trace"]["run"] == out["run"]
    ctx = mc.yaml_load(single["contents"][2]["text"])
    surrounding = ctx["nodes"][0]["surrounding"]
    assert surrounding["volume"]["scope"] == "project" and surrounding["text"]["path"] == "notes.md"
    assert "hello.md" in {n["path"] for n in surrounding["neighbours"]}
    folder = mc.yaml_load((project / "notes.thym" / "package.cosm").read_text(encoding="utf-8"))
    assert [c["sha256"] for c in folder["contents"]] == [c["sha256"] for c in single["contents"]]
    for c in folder["contents"]:
        assert digest_path(project / "notes.thym" / c["path"]) == c["sha256"]
    assert Path(out["trace"]).is_file()
    runs = client.get("/api/thym/runs").json()["runs"]
    assert runs[0]["run"] == out["run"] and runs[0]["program"] == "export"


def test_export_with_a_morph_seals_and_shows_the_key_once(client: TestClient, project: Path):
    r = client.post("/api/canon/package", json={"path": "notes.md", "morph": "plain-letter.morph.cosm",
                                                "encrypt": True})
    assert r.status_code == 200, r.text
    out = r.json()
    key, sealed = out["key"], project / "notes.thym.enc"
    assert out["sealed"] == "notes.thym.enc" and sealed.is_file()
    data = sealed.read_bytes()
    assert key.encode() not in data and key.replace("-", "").encode() not in data
    single = (project / "notes.package.cosm").read_bytes()
    assert [c["role"] for c in mc.yaml_load(single.decode())["contents"]] == ["text", "fabula", "morph", "context"]
    assert vault.open(data, key) == single
    for f in project.rglob("*"):
        if f.is_file() and f != sealed:
            assert key.encode() not in f.read_bytes(), f"the key is written nowhere ({f})"
    assert key.encode() not in b"".join(p.read_bytes() for p in H.host_root().rglob("*") if p.is_file())
    cat = mc.yaml_load(canon.project_catalog(project, write=False))
    notes = next(n for n in cat["nodes"] if n["path"] == "notes.md")
    assert notes["package"] == {"path": "notes.package.cosm", "folder": "notes.thym", "sealed": "notes.thym.enc"}
    kinds = {n["path"]: n.get("kind") for n in cat["nodes"]}
    assert (kinds["notes.package.cosm"], kinds["notes.thym"], kinds["notes.thym.enc"]) == ("package", "package",
                                                                                         "sealed")
    assert not any(n["path"].startswith("notes.thym/") for n in cat["nodes"]), "a package folder is one item"


def test_unpack_verifies_and_writes_the_text_and_its_twin(client: TestClient, project: Path):
    assert client.post("/api/canon/package", json={"path": "notes.md"}).status_code == 200
    (project / "inbox").mkdir()
    shutil.copyfile(project / "notes.package.cosm", project / "inbox" / "notes.package.cosm")
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.package.cosm"})
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "inbox/notes.md", "twin": "inbox/notes.md.cosm", "context": "inbox/notes.context.cosm",
                        "verified": True}
    assert (project / "inbox" / "notes.md").read_bytes() == (INPUTS / "notes.md").read_bytes()
    assert canon.emf_state(project / "inbox" / "notes.md", project / "inbox" / "notes.md.cosm") == "fresh"
    twin = mc.yaml_load((project / "inbox" / "notes.md.cosm").read_text(encoding="utf-8"))
    assert twin["source"]["path"] == "notes.md"
    assert all(s.startswith("notes.md#") for it in twin["nodes"] for s in it["provenance"]["sources"])
    again = client.post("/api/canon/unpack", json={"path": "inbox/notes.package.cosm"})
    assert again.status_code == 200, "the same bytes again are not a conflict"
    (project / "inbox" / "notes.md").write_text("Something else.\n", encoding="utf-8")
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.package.cosm"})
    assert r.status_code == 409 and "never overwritten" in r.json()["detail"]
    assert (project / "inbox" / "notes.md").read_text(encoding="utf-8") == "Something else.\n"
    # the folder form unpacks the same way
    (project / "box").mkdir()
    shutil.copytree(project / "notes.thym", project / "box" / "notes.thym")
    r = client.post("/api/canon/unpack", json={"path": "box/notes.thym"})
    assert r.status_code == 200 and r.json()["text"] == "box/notes.md"


def test_unpack_refuses_a_bad_digest_and_writes_nothing(client: TestClient, project: Path):
    assert client.post("/api/canon/package", json={"path": "notes.md"}).status_code == 200
    (project / "inbox").mkdir()
    pkg = mc.yaml_load((project / "notes.package.cosm").read_text(encoding="utf-8"))
    pkg["contents"][0]["text"] = pkg["contents"][0]["text"].replace("orchard", "garden", 1)
    (project / "inbox" / "notes.package.cosm").write_text(mc.dump(pkg), encoding="utf-8")
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.package.cosm"})
    assert r.status_code == 409 and "digest" in r.json()["detail"]
    assert sorted(p.name for p in (project / "inbox").iterdir()) == ["notes.package.cosm"]


def test_unpack_a_sealed_package_needs_its_key(client: TestClient, project: Path):
    key = client.post("/api/canon/package", json={"path": "notes.md", "encrypt": True}).json()["key"]
    (project / "inbox").mkdir()
    shutil.copyfile(project / "notes.thym.enc", project / "inbox" / "notes.thym.enc")
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.thym.enc"})
    assert r.status_code == 400 and "sealed" in r.json()["detail"]
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.thym.enc", "key": "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF"})
    assert r.status_code == 400 and "does not open" in r.json()["detail"]
    assert sorted(p.name for p in (project / "inbox").iterdir()) == ["notes.thym.enc"]
    r = client.post("/api/canon/unpack", json={"path": "inbox/notes.thym.enc", "key": key.lower()})
    assert r.status_code == 200, r.text
    assert (project / "inbox" / "notes.md").read_bytes() == (INPUTS / "notes.md").read_bytes()


# ---------------------------------------------------------------------------
# Readings
# ---------------------------------------------------------------------------

def test_a_reading_needs_a_model(client: TestClient, project: Path):
    job = start(client, "/api/canon/read", {"path": "notes.md", "morph": "plain-letter.morph.cosm"})
    assert job["kind"] == "read" and job["mode"] == "rules"
    done = wait_job(client, job["id"])
    assert done["state"] == "failed" and done["message"].startswith("a reading needs a model")
    assert not list(project.glob("notes.read-*"))
    r = client.post("/api/canon/read", json={"path": "hello.md", "morph": None})
    assert r.status_code == 409 and r.json()["detail"].startswith("derive the twin first")
    r = client.post("/api/canon/read", json={"path": "notes.md", "morph": "isomorph"})
    assert r.status_code == 400


def test_a_reading_with_a_model_is_saved_beside_the_text_and_labelled(client: TestClient, project: Path,
                                                                     monkeypatch: pytest.MonkeyPatch):
    from tests.test_thym_moves import GOOD_READING
    asked: list = []

    def complete(messages, *, llm_url=None, max_tokens=None, **kw):
        asked.append(messages)
        return mc.dump(GOOD_READING), {"model": "g40-04"}

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", complete)
    before = (project / "notes.md").read_bytes()
    job = start(client, "/api/canon/read", {"path": "notes.md", "morph": "plain-letter.morph.cosm"})
    assert job["mode"] == "model"
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    res = done["result"]
    assert res["label"] == "read through plain-letter"
    assert res["reading"].startswith("notes.read-plain-letter-") and res["reading"].endswith(".md")
    text = (project / res["reading"]).read_text(encoding="utf-8")
    assert text.startswith("---\nread_through: plain-letter\n---\n")
    assert text.rstrip().endswith("by g40-04; the text stands unchanged*")
    assert "*a reading of notes.md through plain-letter, made here on " in text
    assert (project / "notes.md").read_bytes() == before
    assert len(asked) == 1


def test_a_package_folder_is_a_volume_not_a_program(project: Path, client) -> None:
    """`/api/cosm?path=<stem>.thym` on a package's folder form draws the package catalog (THYM.md 15.1); only a
    `.thym` file is a program."""
    import shutil
    src = REPO / "tests" / "fixtures" / "thym" / "replay" / "publish-story" / "2026-11-01-2148-35b5" / "outputs" / "notes.thym"
    shutil.copytree(src, project / "notes.thym")
    r = client.get("/api/cosm", params={"path": "notes.thym"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body.get("refused") and body.get("declaration", "").startswith("oes: thym") or "thym" in str(body)[:400]
    r = client.get("/api/cosm", params={"path": "nothing-here.thym"})
    assert r.status_code == 404 and "no program" in r.json()["detail"]



# ---------------------------------------------------------------------------
# Models in a run (THYM.md 23): the route on plan and run, the plan's models block, the gate, the ceiling, the lock;
# every input of every type; folder inputs and several outputs
# ---------------------------------------------------------------------------

ALL_TYPES = """thym 0

program every-kind
  why: one input of every kind a picker offers, counted.

  takes a: text, b: fabula, c: morph, d: context, e: package, f: volume
  gives n: number

  give words a
end
"""


def gate(monkeypatch: pytest.MonkeyPatch, open_: bool) -> list:
    from enough import cloud
    asked: list = []

    def status() -> dict:
        asked.append(1)
        return {"open": open_, "reason": None if open_ else "'local models only' is on in the broker",
                "denial": None if open_ else "error: the broker's copy", "model_id": "vendor/large-model" if open_
                else None}
    monkeypatch.setattr(cloud, "gate_status", status)

    def no_cloud(*a, **kw):
        raise AssertionError("the cloud was asked")
    monkeypatch.setattr(cloud, "chat_completion", no_cloud)
    return asked


def test_a_cloud_plan_says_so_plainly_before_anything_runs(client: TestClient, monkeypatch):
    gate(monkeypatch, True)
    r = client.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md", "route": "cloud"}).json()
    assert r["ok"] is True and r["mode"] == "model" and r["route"] == "cloud" and r["calls"] is None
    assert r["models"] == {"route": "cloud", "provider": "openrouter", "model": "vendor/large-model", "calls": 3,
                           "at_most": 9, "calls_open": [], "window": H.CLOUD_WINDOW}
    assert r["models_line"] == "3 model calls, at most 9, on the cloud (openrouter: vendor/large-model)"
    assert r["inputs"] == [{"name": "story", "type": "text", "rel": "notes.md",
                            "sha256": digest_path(INPUTS / "notes.md"),
                            "accepts": "a text (a markdown or plain file)"}]
    assert r["outputs"] == [{"name": "out", "type": "package"}] and r["version"] == 0
    other = client.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md",
                                                "route": "cloud:vendor/other", "calls": 12}).json()
    assert other["models"]["model"] == "vendor/other" and other["calls"] == 12


def test_a_shut_gate_refuses_the_cloud_plan_and_run_in_its_words(client: TestClient, monkeypatch):
    asked = gate(monkeypatch, False)
    r = client.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md", "route": "cloud"}).json()
    assert r["ok"] is False and (r["refusal"]["check"], r["refusal"]["line"]) == ("cloud", 12)
    assert r["refusal"]["message"] == "the cloud is not open for this run: 'local models only' is on in the broker"
    run = client.post("/api/thym/run", json={"program": "publish-story", "path": "notes.md", "route": "cloud"})
    assert run.status_code == 409 and run.json()["detail"].startswith("the cloud is not open for this run")
    assert asked and not H.host_root().exists(), "nothing ran"


def test_agent_free_refuses_the_cloud_without_asking_the_broker(project: Path, monkeypatch):
    from enough import cloud
    monkeypatch.setattr(cloud, "gate_status", lambda: (_ for _ in ()).throw(AssertionError("the broker was asked")))
    set_agent_free(True)
    with TestClient(create_app(project, "http://127.0.0.1:9", supervise=False)) as c:
        r = c.post("/api/thym/plan", json={"program": "publish-story", "path": "notes.md", "route": "cloud"}).json()
        assert r["refusal"]["check"] == "agent-free"
        assert r["refusal"]["message"] == ("3 steps ask a model on the cloud route, the first `let f = derive story` "
                                           "(line 12); agent-free is on")


def test_route_and_calls_are_checked(client: TestClient):
    def plan(**extra) -> int:
        return client.post("/api/thym/plan", json={"program": "count-words", "path": "notes.md", **extra}).status_code
    assert plan(route="sky") == 400 and plan(calls=0) == 400 and plan(calls="7") == 400
    assert plan(route="local", model="vendor/x") == 400
    assert plan(route="local", calls=3) == 200


def test_a_cloud_run_holds_no_lock_and_a_local_one_does(client: TestClient, monkeypatch):
    from enough import model_route
    seen: list = []
    original = model_route.holds_generation_lock

    def spy(route):
        seen.append(route)
        return original(route)
    monkeypatch.setattr(model_route, "holds_generation_lock", spy)
    gate(monkeypatch, True)
    job = start(client, "/api/thym/run", {"program": "count-words", "path": "notes.md", "route": "cloud"})
    done = wait_job(client, job["id"])
    assert done["state"] == "done" and done["result"]["route"] == "cloud" and seen == ["cloud"]
    assert done["result"]["models"] is None, "a run that asks nothing makes no model calls"


def test_every_input_of_every_type_is_filled_and_held_to_its_kind(client: TestClient, project: Path):
    (project / "tools" / "every-kind.thym").write_text(ALL_TYPES, encoding="utf-8")
    good = {"a": "notes.md", "b": "notes.md.cosm", "c": "plain-letter.morph.cosm", "d": "on-the-train.context.cosm",
            "e": "orchard-notes.thym", "f": "notes.md.cosm"}
    r = client.post("/api/thym/plan", json={"program": "every-kind", "inputs": good})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert [(i["name"], i["type"]) for i in r.json()["inputs"]] == [
        ("a", "text"), ("b", "fabula"), ("c", "morph"), ("d", "context"), ("e", "package"), ("f", "volume")]
    row = next(p for p in client.get("/api/thym/programs").json()["programs"] if p["name"] == "every-kind")
    assert [t["accepts"] for t in row["takes"]] == [H.accepts(t) for t in ("text", "fabula", "morph", "context",
                                                                           "package", "volume")]
    for name, wrong, words in (("a", "notes.md.cosm", "notes.md.cosm is a volume; a takes a text"),
                               ("b", "notes.md", "notes.md is not a fabula; b takes a fabula"),
                               ("c", "on-the-train.context.cosm", "is not a morph; c takes a morph"),
                               ("d", "plain-letter.morph.cosm", "is not a context; d takes a context"),
                               ("e", "notes.md", "notes.md is not a package; e takes a package"),
                               ("f", "notes.md", "notes.md is not a volume; f takes a volume")):
        bad = client.post("/api/thym/plan", json={"program": "every-kind", "inputs": {**good, name: wrong}})
        assert bad.status_code == 400 and words in bad.json()["detail"], (name, bad.text)
    missing = client.post("/api/thym/plan", json={"program": "every-kind", "inputs": {"a": "notes.md"}})
    assert missing.status_code == 400
    assert missing.json()["detail"].startswith("every-kind takes a (a text (a markdown or plain file)), b (a fabula")
    assert missing.json()["detail"].endswith("; give b, c, d, e and f")


def test_a_folder_input_and_several_outputs_land_beside_it(client: TestClient, project: Path):
    shutil.copytree(INPUTS / "little-tool", project / "tool")
    shutil.copyfile(SUITE / "programs" / "split-a-folder.thym", project / "tools" / "split-a-folder.thym")
    listed = next(r for r in client.get("/api/thym/programs").json()["programs"] if r["name"] == "split-a-folder")
    assert listed["version"] == 1 and [o["name"] for o in listed["outputs"]] == ["code", "prose", "size"]
    p = client.post("/api/thym/plan", json={"program": "split-a-folder", "inputs": {"repo": "tool"}}).json()
    assert p["ok"] is True and p["version"] == 1
    assert p["outputs"] == [{"name": "code", "type": "folder"}, {"name": "prose", "type": "folder"},
                            {"name": "size", "type": "number"}]
    (row,) = p["inputs"]
    assert (row["name"], row["type"], row["rel"], row["accepts"]) == ("repo", "folder", "tool", "a folder")
    assert row["files"] == 7 and row["sha256"] == digest_path(project / "tool", "folder")
    bad = client.post("/api/thym/plan", json={"program": "split-a-folder", "inputs": {"repo": "notes.md"}})
    assert bad.status_code == 400 and bad.json()["detail"] == "notes.md is a file; repo takes a folder"
    job = start(client, "/api/thym/run", {"program": "split-a-folder", "path": "tool"})
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    outs = done["result"]["outputs"]
    assert [(o["name"], o["type"], o["rel"]) for o in outs] == [("code", "folder", "tool.code"),
                                                                ("prose", "folder", "tool.prose"),
                                                                ("size", "number", "tool.size.txt")]
    assert outs[0]["files"] == ["little/__init__.py", "little/cli.py", "little/count.py"]
    assert sorted(p.relative_to(project / "tool.code").as_posix() for p in (project / "tool.code").rglob("*")
                  if p.is_file()) == outs[0]["files"]
    assert "files" not in outs[2] and (project / "tool.size.txt").is_file()


# ---------------------------------------------------------------------------
# Lane S4 (0.6): the moves, a list as an input, where outputs land, a shipped program beside a project file
# ---------------------------------------------------------------------------

def test_moves_lists_every_move_of_a_version_as_the_tool_does(client: TestClient, project: Path):
    from enough import thym_tools as TT
    from enough.thym import declarations
    one = client.get("/api/thym/moves", params={"version": 1})
    assert one.status_code == 200, one.text
    body = one.json()
    assert body["version"] == 1
    names = [m["name"] for m in body["moves"]]
    assert sorted(names) == sorted(declarations.load().view(1)) and len(names) == len(set(names))
    owners = list(dict.fromkeys(m["owner"] for m in body["moves"]))
    assert owners[:3] == ["thym", "fabula", "doc"], owners           # THYM 6.2's order, each owner's moves together
    assert len(owners) == len({m["owner"] for m in body["moves"]})
    tell = next(m for m in body["moves"] if m["name"] == "entail")
    assert set(tell) == {"name", "owner", "format", "source", "since", "versions", "signature", "takes", "of",
                         "modifiers", "gives", "asks", "scaffold", "contract", "says", "extended"}
    assert tell["format"] == "fabula/1" and tell["versions"] == [0, 1] and tell["asks"] is True
    assert tell["signature"].startswith("entail <fabula | item | volume") and tell["source"].endswith(".cosm")
    ctx = next(m for m in body["moves"] if m["name"] == "context")
    assert ctx["takes"] == [] and ctx["of"] and "of" not in ctx["modifiers"]
    project_move = next(m for m in body["moves"] if m["name"] == "project")
    assert {"owner": "ascribe", "as": ["isograph", "allograph"]} in project_move["extended"]   # a second format's kinds
    assert {"isograph", "allograph"} <= set(project_move["modifiers"]["as"])
    zero = client.get("/api/thym/moves", params={"version": 0}).json()
    zero_project = next(m for m in zero["moves"] if m["name"] == "project")
    assert not {"isograph", "allograph"} & set(zero_project["modifiers"].get("as", []))
    assert zero_project["extended"] == []
    assert len(zero["moves"]) < len(body["moves"])
    assert all(m["versions"] == [1] for m in body["moves"] if m["name"] not in {z["name"] for z in zero["moves"]})
    assert client.get("/api/thym/moves").json() == body                       # 1 by default
    for bad in ("2", "x", "-1"):
        r = client.get("/api/thym/moves", params={"version": bad})
        assert r.status_code == 400 and "version is 0 or 1" in r.json()["detail"]
    assert names == [d.name for d in TT.listed_moves(1)]                     # the listing the tool reads too


LIST_JOIN = """thym 1

program join-them
  why: several shorts as one.

  takes xs: list of short
  gives out: short

  give join xs with " "
end
"""


def test_a_list_input_is_given_member_by_member_and_each_checked(client: TestClient, project: Path):
    (project / "tools" / "join-them.thym").write_text(LIST_JOIN, encoding="utf-8")
    row = next(p for p in client.get("/api/thym/programs").json()["programs"] if p["name"] == "join-them")
    assert row["takes"] == [{"name": "xs", "type": "list of short",
                             "accepts": "a list of shorts (each a markdown file)"}]
    r = client.post("/api/thym/plan", json={"program": "join-them", "inputs": {"xs": ["notes.md", "hello.md"]}})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["ok"] is True and not p.get("refusal"), p                     # the core plans a list member by member
    plan_row = p["plan"]["inputs"][0]
    assert [m["sha256"] for m in plan_row["members"]] == [digest_path(project / "notes.md"),
                                                          digest_path(project / "hello.md")]
    assert plan_row["sha256"] == list_digest([m["sha256"] for m in plan_row["members"]])
    (inp,) = p["inputs"]
    assert (inp["name"], inp["type"], inp["rel"]) == ("xs", "list of short", None)
    assert inp["members"] == [{"rel": "notes.md", "sha256": digest_path(project / "notes.md")},
                              {"rel": "hello.md", "sha256": digest_path(project / "hello.md")}]
    assert p["writes"] == [{"name": "out", "type": "short", "rel": "notes.out.md"}]
    one = client.post("/api/thym/plan", json={"program": "join-them", "inputs": {"xs": "notes.md"}})
    assert one.status_code == 400 and one.json()["detail"].startswith("xs is a list of short: it takes a list of "
                                                                       "shorts")
    assert "one path was given (notes.md)" in one.json()["detail"]
    wrong = client.post("/api/thym/plan", json={"program": "join-them", "inputs": {"xs": ["notes.md", "notes.md.cosm"]}})
    assert wrong.status_code == 400 and wrong.json()["detail"] == "notes.md.cosm is a volume; xs[2] takes a short (a " \
                                                                  "markdown file)"
    gone = client.post("/api/thym/plan", json={"program": "join-them", "inputs": {"xs": ["gone.md", "notes.md.cosm"]}})
    assert gone.status_code == 404 and gone.json()["detail"] == "no such file: gone.md"       # in order: the first
    empty = client.post("/api/thym/plan", json={"program": "join-them", "inputs": {"xs": []}})
    assert empty.status_code == 400 and empty.json()["detail"].endswith("; give xs")
    many = client.post("/api/thym/plan", json={"program": "count-words", "inputs": {"story": ["notes.md", "hello.md"]}})
    assert many.status_code == 400
    assert many.json()["detail"] == ("story is a text: it takes a text (a markdown or plain file), one path, and a "
                                     "list of 2 was given")
    done = wait_job(client, start(client, "/api/thym/run", {"program": "join-them",
                                                            "inputs": {"xs": ["notes.md", "hello.md"]}})["id"])
    res = done["result"]
    assert done["state"] == "done" and res["outcome"] == "landed", done
    (out,) = res["outputs"]
    assert out["rel"] == "notes.out.md"                                      # beside the first member, as planned
    landed = (project / "notes.out.md").read_text(encoding="utf-8")
    notes = (project / "notes.md").read_text(encoding="utf-8")
    assert landed.startswith(notes.strip().splitlines()[0]) and "A short note about the lane" in landed


def test_a_plan_says_where_each_output_will_land_as_the_run_lands_it(client: TestClient, project: Path):
    p = client.post("/api/thym/plan", json={"program": "count-words", "path": "notes.md"}).json()
    assert p["writes"] == [{"name": "n", "type": "number", "rel": "notes.n.txt"}]
    done = wait_job(client, start(client, "/api/thym/run", {"program": "count-words", "path": "notes.md"})["id"])
    assert [o["rel"] for o in done["result"]["outputs"]] == [w["rel"] for w in p["writes"]]
    pk = client.post("/api/thym/plan", json={"program": "tools/pack-it.thym",
                                             "inputs": {"story": "notes.md", "f": "notes.md.cosm"}}).json()
    assert pk["writes"] == [{"name": "out", "type": "package", "rel": "notes.package.cosm", "folder": "notes.thym"}]
    done = wait_job(client, start(client, "/api/thym/run", {"program": "tools/pack-it.thym",
                                                            "inputs": {"story": "notes.md", "f": "notes.md.cosm"}})["id"])
    out = done["result"]["outputs"][0]
    assert (out["rel"], out["folder"]) == ("notes.package.cosm", "notes.thym")
    shutil.copytree(INPUTS / "little-tool", project / "tool")
    shutil.copyfile(SUITE / "programs" / "split-a-folder.thym", project / "tools" / "split-a-folder.thym")
    sp = client.post("/api/thym/plan", json={"program": "split-a-folder", "inputs": {"repo": "tool"}}).json()
    assert [(w["name"], w["rel"]) for w in sp["writes"]] == [("code", "tool.code"), ("prose", "tool.prose"),
                                                            ("size", "tool.size.txt")]


def test_output_ext_is_what_a_value_of_the_type_lands_with():
    from enough import thym_api as A
    assert [A.output_ext(t) for t in ("text", "short", "number", "word", "line", "fabula", "atem", "morph",
                                      "context", "volume", "list of item", "change", "any")] == [
        "md", "md", "txt", "txt", "txt", "cosm", "cosm", "morph.cosm", "context.cosm", "cosm", "cosm", "cosm", None]


def test_where_tells_a_shipped_program_from_a_project_file_of_the_same_name(client: TestClient, project: Path):
    mine = COUNT.replace("program count-words", "program my-tighten")
    (project / "tighten.thym").write_text(mine, encoding="utf-8")
    rows = client.get("/api/thym/programs").json()["programs"]
    assert {(r["where"], r["rel"]) for r in rows} >= {("project", "tighten.thym"), ("shipped", "tighten.thym")}
    as_today = client.get("/api/thym/program", params={"path": "tighten.thym"}).json()
    assert (as_today["name"], as_today["where"]) == ("my-tighten", "project")          # unchanged: the project's
    shipped = client.get("/api/thym/program", params={"path": "tighten.thym", "where": "shipped"}).json()
    assert shipped["where"] == "shipped" and shipped["name"] == "tighten"
    assert shipped["source"] == (H.SHIPPED_PROGRAMS / "tighten.thym").read_text(encoding="utf-8")
    assert client.get("/api/thym/program", params={"path": "tighten", "where": "shipped"}).json()["name"] == "tighten"
    assert client.get("/api/thym/program", params={"path": "tighten.thym",
                                                   "where": "project"}).json()["name"] == "my-tighten"
    c = client.post("/api/thym/compile", json={"path": "tighten.thym", "where": "shipped"}).json()
    assert c["ok"] is True and c["name"] == "tighten"
    assert client.post("/api/thym/compile", json={"path": "tighten.thym"}).json()["name"] == "my-tighten"
    pl = client.post("/api/thym/plan", json={"program": "tighten.thym", "where": "project", "path": "notes.md"}).json()
    assert pl["ok"] is True and pl["atem"].startswith("my-tighten:")
    sp = client.post("/api/thym/plan", json={"program": "tighten.thym", "where": "shipped", "path": "hello.md"}).json()
    assert sp["atem"].startswith("tighten:")
    none = client.get("/api/thym/program", params={"path": "count-words.thym", "where": "shipped"})
    assert none.status_code == 404 and none.json()["detail"].startswith("no shipped program count-words.thym; the "
                                                                        "shipped programs are ")
    assert "tighten.thym" in none.json()["detail"]
    nope = client.post("/api/thym/compile", json={"path": "publish-story.thym", "where": "project"})
    assert nope.status_code == 404 and nope.json()["detail"] == "no program publish-story.thym in this project"
    assert client.post("/api/thym/run", json={"program": "publish-story", "where": "project",
                                              "path": "notes.md"}).status_code == 404
    bad = client.get("/api/thym/program", params={"path": "tighten.thym", "where": "elsewhere"})
    assert bad.status_code == 400 and bad.json()["detail"] == "where is shipped, project or canon, not 'elsewhere'"
    assert client.get("/api/thym/program", params={"path": "tools/count-words.thym"}).json()["where"] == "project"
