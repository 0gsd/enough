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
from enough.thym.values import digest_path

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
    assert {r["rel"] for r in rows if r["where"] == "shipped"} == {"open-house.thym", "publish-story.thym",
                                                                  "read-my-way.thym"}
    count = by[("project", "tools/count-words.thym")]
    assert count == {"name": "count-words", "where": "project", "rel": "tools/count-words.thym", "problem": None,
                     "steps": 1, "asks": 0, "takes": [{"name": "story", "type": "text"}],
                     "gives": {"name": "n", "type": "number"}, "why": "how long a text is, in words."}
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
    assert ok == {"ok": True, "name": "count-words", "refusal": None,
                  "estimate": {"steps": 1, "asks": 0, "largest_prompt": 0, "output_words": 0}}
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
    assert asks["refusal"]["message"] == "3 steps ask a model; no model is running"
    assert client.post("/api/thym/plan", json={"program": "count-words", "path": "missing.md"}).status_code == 404
    assert client.post("/api/thym/plan", json={"program": "count-words",
                                               "inputs": {"nope": "notes.md"}}).status_code == 400


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
    assert r.status_code == 409 and r.json()["detail"] == "3 steps ask a model; no model is running"
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
        assert r.status_code == 409 and r.json()["detail"] == "3 steps ask a model; agent-free is on"
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

