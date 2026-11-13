"""The fabulac job (0.6, `enough/fabulac_job.py`; MacroCOSM OES 18.4.1, 18.4.7; THYM 20.6 to 20.8): the five programs
of `decompile-python.thym` run in order as one job over `tests/fixtures/thym/inputs/tiny-tool/`, each stage landing
`<folder>.fabulac.cosm` and its run in `derived.runs`; a stopped build taken up again from disk; the compile into a
cshort and its catems, recorded in `shorts:` and `catems:`; the read-only views; and the routes under `/api/fabula/`.

No model: the scripted coprocessor of `tests/test_thym_code.py` stands in for one at the function level (the runtime is
handed in), and the routes run with a dead model URL, so the app is in rules mode. Every seam points inside tmp_path
(conftest). Nothing in tiny-tool, and nothing a scripted answer holds, is ever run: a canary proves it.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon, macrocosm as mc, models, skeleton
from enough import fabulac_job as F
from enough import thym_host as H
from enough.canon_derive import DeriveCancelled
from enough.server import create_app
from enough.thym.coprocessor import candidate
from tests.test_thym_code import TINY, Scripted, answers, code_answer, engines

NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)


class Model(Scripted):
    """tiny-tool's scripted readings, fold and cshort; a question step proposes nothing."""

    def complete(self, contract, inputs, *, budget):
        if contract.get("move") == "question" or "question" in str(contract.get("name") or ""):
            self.sent.append(("question", "", contract))
            return candidate("questions: []", engine="model:scripted-1", tokens=5)
        try:
            return super().complete(contract, inputs, budget=budget)
        except AssertionError:
            self.sent.append(("question", "", contract))
            return candidate("questions: []", engine="model:scripted-1", tokens=5)


def runtime(cp=None, root: Path | None = None):
    """A stage's run kwargs as the app's would give them, with the scripted model and the repo engines."""
    def make(stage, plan, info, mode, scaffolds, program):
        from enough.thym.coprocessor import RefusingCoprocessor
        return {"coprocessor": cp if (mode == "model" and cp is not None) else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if mode == "model" else {},
                "root": root or H.host_root(), "engines": engines(), "calls": None}
    return make


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copytree(TINY, proj / "tiny-tool")
    return proj


def fabulac(project: Path) -> dict:
    return mc.yaml_load((project / "tiny-tool.fabulac.cosm").read_text(encoding="utf-8"))


def build(project: Path, **kw):
    kw.setdefault("mode", "model")
    kw.setdefault("runtime", runtime(Model(answers())))
    return F.run_build(project, project / "tiny-tool", now=NOW, **kw)


# ---------------------------------------------------------------------------
# The job, at the function level
# ---------------------------------------------------------------------------

def test_names_on_disk():
    assert F.fabulac_path(Path("p/tool")) == Path("p/tool.fabulac.cosm")
    assert F.folder_of(Path("p/tool.fabulac.cosm")) == Path("p/tool")
    assert F.folder_of(Path("p/tool.cosm")) is None
    assert F.STAGES == ("survey-the-repo", "read-the-history", "read-every-file", "fold-the-whole",
                        "raise-the-questions")
    assert F.program_path().name == "decompile-python.thym" and F.program_path().parent == H.SHIPPED_PROGRAMS


def test_a_build_with_a_model_lands_every_stage_and_records_every_run(project: Path):
    out = build(project)
    assert out["complete"], out
    doc = fabulac(project)
    assert (doc["oes"], doc["flavour"], doc["id"]) == ("fabula/1", "fabulac", "fabula/tiny-tool")
    runs = F.build_runs(doc)
    assert len(runs) == 5 and [r["run"] for r in runs] == [r["run"] for r in out["ran"]]
    # every stage has its entry, named by its program (the conductor's ruling), the read and the question included
    assert [r["program"] for r in runs] == list(F.STAGES)
    # the read stage's run was written by the host (gather writes none) and names the model that read
    read = runs[2]
    assert read["model"] == "scripted-1" and read["route"] == "local"
    assert doc["derived"]["completeness"] == "full"
    state = F.build_state(project, project / "tiny-tool")
    assert state["complete"] and state["landed"] == 5 and state["next"] is None and not state["moved"]
    assert [s["stage"] for s in state["stages"] if s["landed"]] == ["survey", "history", "read", "fold", "question"]
    assert out["calls"]["made"] >= 6 and out["calls"]["files_read"] == 5


def test_the_job_ceiling_defaults_to_the_stage_ceiling_times_the_stages_that_ask():
    assert F.ASKING_STAGES == 3
    assert F.job_ceiling(None, None) is None                     # no ceiling given: none, as before
    assert F.job_ceiling(4, None) == 12
    assert F.job_ceiling(4, 5) == 5 and F.job_ceiling(None, 7) == 7


def test_a_build_stops_at_its_ceiling_across_the_whole_job(project: Path, tmp_path: Path):
    """0.7: each stage's run had a ceiling on its model calls and the job none; the job has one now."""
    whole = build(project)
    n = whole["calls"]["made"]
    assert whole["complete"] and whole["calls"]["at_most"] is None
    # reached while a stage runs: refused in the job's words, nothing of that stage written
    other = tmp_path / "other"
    other.mkdir()
    shutil.copytree(TINY, other / "tiny-tool")
    seen: list[dict] = []
    with pytest.raises(RuntimeError) as e:
        F.run_build(other, other / "tiny-tool", mode="model", runtime=runtime(Model(answers())), now=NOW,
                    job_calls=2, progress=seen.append)
    said = str(e.value)
    assert "the build reached its ceiling of 2 model calls across the whole job" in said
    assert "read was refused" in said and "the build takes up again from read" in said
    assert {p["progress"].get("job_at_most") for p in seen if "progress" in p} == {2}
    # reached between stages: the next stage does not start, and the result says why
    third = tmp_path / "third"
    third.mkdir()
    shutil.copytree(TINY, third / "tiny-tool")
    out = F.run_build(third, third / "tiny-tool", mode="model", runtime=runtime(Model(answers())), now=NOW,
                      job_calls=n - 1)
    assert not out["complete"] and out["calls"]["made"] == n - 1 and out["calls"]["at_most"] == n - 1
    assert out["refusal"]["check"] == "calls" and out["refusal"]["program"] == "raise-the-questions"
    assert f"the build reached its ceiling of {n - 1} model calls across the whole job" in out["message"]
    assert [r["program"] for r in out["ran"]] == list(F.STAGES[:-1])


def test_rules_writes_the_outline_and_the_read_waits_in_the_hosts_words(project: Path):
    out = build(project, mode="rules", why="the model is not running")
    assert not out["complete"]
    assert [r["stage"] for r in out["ran"]] == ["survey", "history"]
    assert fabulac(project)["derived"]["completeness"] == "outline"
    r = out["refusal"]
    assert r["check"] == "no-model" and r["program"] == "read-every-file"
    assert r["message"].startswith("1 step asks a model on the local route, the first `") or \
        "ask a model on the local route" in r["message"]
    assert r["message"].endswith("; no model is running")
    assert "read-every-file waits" in out["message"]


def test_agent_free_refuses_in_the_agent_free_words(project: Path):
    out = build(project, mode="rules", why=agent_free.REASON)
    assert out["refusal"]["check"] == "agent-free" and out["refusal"]["message"].endswith("; agent-free is on")
    assert [r["stage"] for r in out["ran"]] == ["survey", "history"]


def test_mode_rules_asked_stops_at_the_outline(project: Path):
    out = build(project, mode="rules", scaffolds=True)
    assert out["refusal"]["check"] == "rules" and "outline only" in out["refusal"]["message"]


def test_a_stopped_build_takes_up_again_from_disk_after_the_last_stage_that_landed(project: Path):
    """A cancel during the read: nothing of it lands, the outline stays; a new call (no memory of the first)
    reads where the build stands from the fabulac and the traces, and runs from the read."""
    asked = {"n": 0}

    def stop() -> bool:
        asked["n"] += 1
        return F.build_state(project, project / "tiny-tool")["landed"] >= 2
    with pytest.raises(DeriveCancelled) as e:
        build(project, should_stop=stop)
    assert "landed before it: survey, history" in str(e.value) and "takes up again from read" in str(e.value)
    state = F.build_state(project, project / "tiny-tool")
    assert state["landed"] == 2 and state["next"] == "read-every-file"
    assert F.start_index(state) == 2 and F.start_index(state, resume_only=True) == 2
    out = build(project, resume_only=True)
    assert [r["stage"] for r in out["ran"]] == ["read", "fold", "question"] and out["complete"]
    assert len(F.build_runs(fabulac(project))) == 5


def test_a_folder_that_moved_is_built_again_from_the_survey(project: Path):
    build(project, mode="rules", why="no model")
    (project / "tiny-tool" / "tiny" / "counting.py").write_text("# changed\n", encoding="utf-8")
    state = F.build_state(project, project / "tiny-tool")
    assert state["moved"] and state["next"] == "survey-the-repo" and F.start_index(state) == 0
    with pytest.raises(F.BuildError) as e:
        F.start_index(state, resume_only=True)
    assert e.value.status == 409 and "tree digest moved" in str(e.value)


def test_a_complete_fabulac_is_built_again_only_when_asked(project: Path):
    build(project)
    state = F.build_state(project, project / "tiny-tool")
    with pytest.raises(F.BuildError) as e:
        F.start_index(state)
    assert e.value.status == 409 and "already built" in str(e.value)
    assert F.start_index(state, restart=True) == 0
    with pytest.raises(F.BuildError) as e:
        F.start_index(F.build_state(project, project / "nothing"))
    assert e.value.status == 404


def test_a_trace_gone_is_read_by_the_runs_place(project: Path):
    out = build(project, mode="rules", why="no model")
    for r in out["ran"]:
        shutil.rmtree(Path(r["trace"]).parent)
    state = F.build_state(project, project / "tiny-tool")
    assert state["landed"] == 2 and state["next"] == "read-every-file"


def test_with_run_adds_the_hosts_entry_once_and_keeps_the_bytes():
    text = ("oes: fabula/1\nflavour: fabulac\nid: fabula/t\nname: t\n# a comment\nderived:\n  at: 2026-11-05T12:00:00Z\n"
            "  runs:\n  - {program: decompile-python.thym, run: r1, at: 2026-11-05T12:00:00Z}\nnodes: []\n")
    entry = {"program": "read-every-file", "run": "r2", "at": "2026-11-05T12:01:00Z", "model": "m"}
    out = F.with_run(text, entry, filename="t.fabulac.cosm")
    assert out.startswith("oes: fabula/1\nflavour: fabulac\nid: fabula/t\nname: t\n# a comment\n")
    assert [r["run"] for r in mc.yaml_load(out)["derived"]["runs"]] == ["r1", "r2"]
    assert F.with_run(out, entry, filename="t.fabulac.cosm") == out


def test_record_entry_keeps_the_catalogs_order_and_every_other_byte():
    text = "oes: fabula/1\nflavour: fabulac\nid: fabula/t\n# the items\nnodes: []\n"
    at = dt.datetime(2026, 11, 5, 15, 30, 12, tzinfo=dt.timezone.utc)
    one = F.record_entry(text, "catems", {"path": "t.catem-2026-11-05-1530.md", "at": at, "by": "m",
                                          "mode": "model", "route": "local", "depth": "overview"})
    two = F.record_entry(one, "shorts", {"path": "t.cshort-2026-11-05-1530/", "at": at, "by": "m", "mode": "model",
                                         "order": "code", "route": "local", "language": "python", "files": 2})
    assert list(mc.yaml_load(two)) == ["oes", "flavour", "id", "shorts", "catems", "nodes"]
    assert two.endswith("# the items\nnodes: []\n")
    three = F.record_entry(two, "shorts", {"path": "t.cshort-2026-11-05-1531/", "at": at, "by": "m",
                                           "mode": "model", "order": "code", "language": "python", "files": 2})
    assert [s["path"] for s in mc.yaml_load(three)["shorts"]] == ["t.cshort-2026-11-05-1530/",
                                                                   "t.cshort-2026-11-05-1531/"]


# ---------------------------------------------------------------------------
# Compiling, and reading what was compiled
# ---------------------------------------------------------------------------

@pytest.fixture
def built(project: Path) -> Path:
    build(project)
    return project / "tiny-tool.fabulac.cosm"


def test_compile_lands_the_cshort_and_the_manual_and_records_both(project: Path, built: Path, tmp_path: Path):
    canary = tmp_path / "canary"
    loud = f"import pathlib\npathlib.Path({str(canary)!r}).write_text('ran')\n"

    def told(inputs):
        return "```\n" + loud + code_answer(inputs).strip("`\n") + "\n```\n"
    cp = Model(answers({("code", "*"): told}))
    out = F.run_compile(project, built, what="code", mode="model", runtime=runtime(cp), now=NOW)
    assert out["cshort"]["path"] == "tiny-tool.cshort-2026-11-05-1200/" and out["recorded"]
    cshort = project / "tiny-tool.cshort-2026-11-05-1200"
    assert (cshort / "CSHORT.md").read_text().startswith("*a cshort of tiny-tool.fabulac.cosm, in Python")
    assert (project / "tiny-tool.catem-2026-11-05-1200.md").is_file()
    doc = mc.yaml_load(built.read_text(encoding="utf-8"))
    keys = list(doc)
    assert keys.index("shorts") < keys.index("catems") < keys.index("nodes")
    short, = doc["shorts"]
    assert {k: short[k] for k in ("path", "by", "mode", "order", "route", "language", "files")} == {
        "path": "tiny-tool.cshort-2026-11-05-1200/", "by": "scripted-1", "mode": "model", "order": "code",
        "route": "local", "language": "python", "files": 6}    # the packaging file written by rules is one of them
    catem, = doc["catems"]
    assert (catem["path"], catem["depth"], catem["mode"]) == ("tiny-tool.catem-2026-11-05-1200.md", "manual", "model")
    assert not canary.exists()                                    # nothing told was run or imported
    # a second compile in the same minute takes -2, never over the first
    again = F.run_compile(project, built, what="overview", mode="model", runtime=runtime(Model(answers())), now=NOW)
    assert again["catems"][0]["path"] == "tiny-tool.catem-2026-11-05-1200-2.md"
    assert len(mc.yaml_load(built.read_text(encoding="utf-8"))["catems"]) == 2

    # read-only views
    listed = F.compiled(project, built)
    assert listed["name"] == "tiny-tool" and listed["shorts"][0]["kind"] == "cshort" and listed["shorts"][0]["exists"]
    tree = F.cshort_tree(project, "tiny-tool.cshort-2026-11-05-1200/")
    assert "tiny/cli.py" in [f["path"] for f in tree["files"]] and tree["footer"].startswith("*a cshort of")
    assert tree["licence"] == "Licence of the source: MIT"
    f = F.cshort_file(project, "tiny-tool.cshort-2026-11-05-1200", "tiny/cli.py")
    assert "def main" in f["text"] and not canary.exists()
    for bad, status in (("../tiny-tool.fabulac.cosm", 400), ("nope.py", 404)):
        with pytest.raises(F.BuildError) as e:
            F.cshort_file(project, "tiny-tool.cshort-2026-11-05-1200", bad)
        assert e.value.status == status
    (cshort / "link.py").symlink_to(project / "tiny-tool" / "tiny" / "cli.py")
    with pytest.raises(F.BuildError) as e:
        F.cshort_file(project, "tiny-tool.cshort-2026-11-05-1200", "link.py")
    assert "link" in str(e.value)
    assert {"path": "link.py", "link": True} in F.cshort_tree(project, "tiny-tool.cshort-2026-11-05-1200")["files"]
    cat = F.catem_text(project, "tiny-tool.catem-2026-11-05-1200-2.md")
    assert cat["depth"] == "overview" and "## Count the words of a file" in cat["text"]


def test_a_catem_by_rules_is_its_scaffold_and_a_cshort_needs_a_model(project: Path, built: Path):
    out = F.run_compile(project, built, what="manual", mode="rules", scaffolds=True, runtime=runtime(), now=NOW)
    cat = F.catem_text(project, out["catems"][0]["path"])
    assert out["mode"] == "rules" and "## Count the words of a file" in cat["text"]
    assert mc.yaml_load(built.read_text(encoding="utf-8"))["catems"][0]["by"] == "rules"
    with pytest.raises(RuntimeError) as e:
        F.run_compile(project, built, what="code", mode="rules", scaffolds=True, runtime=runtime(), now=NOW)
    assert "no scaffold" in str(e.value)


def test_paths_out_of_the_project_or_through_a_link_are_refused(project: Path, tmp_path: Path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (project / "linked").symlink_to(outside)
    for raw, words in (("../elsewhere", "invalid path"), ("linked", "link"), ("canon:lib/x", "Canon store"),
                       ("tiny-tool/README.md", "is a file")):
        with pytest.raises(F.BuildError) as e:
            F.target_of(project, raw)
        assert words in str(e.value), (raw, str(e.value))


# ---------------------------------------------------------------------------
# The routes (rules: the model URL is dead)
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
    shutil.copytree(TINY, proj / "tiny-tool")
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), canon.root(), H.host_root()):
        assert str(where).startswith(str(tmp_path)), where
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        c._project = proj  # type: ignore[attr-defined]
        yield c


def test_the_build_route_writes_the_outline_without_a_model_and_says_what_waits(client: TestClient):
    r = client.post("/api/fabula/build", json={"path": "tiny-tool"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["from"] == "survey-the-repo" and body["job"]["kind"] == "fabulac" and body["job"]["mode"] == "rules"
    snap = wait_job(client, body["job"]["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert [x["stage"] for x in res["ran"]] == ["survey", "history"]
    assert res["refusal"]["check"] == "no-model" and res["fabulac"] == "tiny-tool.fabulac.cosm"
    st = client.get("/api/fabula/build", params={"path": "tiny-tool"}).json()
    assert st["state"]["landed"] == 2 and st["state"]["next"] == "read-every-file" and st["job"] is None
    # the same by the fabulac's own name
    assert client.get("/api/fabula/build", params={"path": "tiny-tool.fabulac.cosm"}).json()["state"]["landed"] == 2
    # resuming takes up from the read, which waits again, in the same words
    r = client.post("/api/fabula/resume", json={"path": "tiny-tool"})
    assert r.status_code == 200 and r.json()["from"] == "read-every-file"
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["result"]["ran"] == [] and snap["result"]["refusal"]["program"] == "read-every-file"


def test_the_build_routes_refusals(client: TestClient):
    r = client.post("/api/fabula/resume", json={"path": "tiny-tool"})
    assert r.status_code == 409 and "nothing to take up again" in r.json()["detail"]
    r = client.post("/api/fabula/build", json={"path": "nowhere"})
    assert r.status_code == 404
    r = client.post("/api/fabula/build", json={"path": "tiny-tool", "route": "moon"})
    assert r.status_code == 400 and "route is local or cloud" in r.json()["detail"]
    for bad in (0, "3", True):
        r = client.post("/api/fabula/build", json={"path": "tiny-tool", "job_calls": bad})
        assert r.status_code == 400 and "job_calls is a ceiling" in r.json()["detail"]
    r = client.post("/api/fabula/build", json={"path": "tiny-tool", "route": "cloud"})
    assert r.status_code == 403                                   # the gate's own words (no key here)
    r = client.post("/api/fabula/cancel", json={"path": "tiny-tool"})
    assert r.status_code == 409 and "no build or compile" in r.json()["detail"]
    r = client.post("/api/fabula/build", json={"path": "tiny-tool", "mode": "model"})
    assert r.status_code == 409 and "no model is running" in r.json()["detail"]


def test_the_build_route_under_agent_free(client: TestClient):
    path = agent_free.ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({agent_free.KEY: True}), encoding="utf-8")
    body = client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()
    snap = wait_job(client, body["job"]["id"])
    assert snap.get("reason") == "agent-free" and snap["result"]["refusal"]["check"] == "agent-free"
    assert snap["result"]["refusal"]["message"].endswith("; agent-free is on")


def test_the_compile_route_and_the_read_only_views(client: TestClient):
    proj = client._project  # type: ignore[attr-defined]
    snap = wait_job(client, client.post("/api/fabula/build", json={"path": "tiny-tool"}).json()["job"]["id"])
    assert snap["state"] == "done"
    r = client.post("/api/fabula/compile", json={"path": "tiny-tool.fabulac.cosm"})
    assert r.status_code == 409 and "a cshort needs a model" in r.json()["detail"]
    r = client.post("/api/fabula/compile", json={"path": "tiny-tool", "what": "overview"})
    assert r.status_code == 200, r.text
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["state"] == "done", snap
    catem = snap["result"]["catems"][0]["path"]
    assert catem.startswith("tiny-tool.catem-") and (proj / catem).is_file()
    listed = client.get("/api/fabula/compiled", params={"path": "tiny-tool"}).json()
    assert listed["catems"][0]["depth"] == "overview" and listed["catems"][0]["exists"]
    got = client.get("/api/fabula/catem", params={"path": catem}).json()
    assert got["depth"] == "overview"
    assert client.get("/api/fabula/catem", params={"path": "tiny-tool/README.md"}).status_code == 400
    assert client.get("/api/fabula/cshort", params={"path": "tiny-tool"}).status_code == 400
    r = client.post("/api/fabula/compile", json={"path": "tiny-tool", "what": "poem"})
    assert r.status_code == 400
    r = client.post("/api/fabula/compile", json={"path": "tiny-tool.fabulac.cosm", "what": "line"})
    assert r.status_code == 200, r.text


def test_every_retired_route_in_the_table_answers_with_its_new_routes_handler(client: TestClient):
    from enough import retired_names
    paths = {(m, getattr(r, "path", None)): r.endpoint for r in client.app.router.routes
             for m in (getattr(r, "methods", None) or ())}
    for method, old, new in retired_names.ROUTES:
        assert paths[(method, old)] is paths[(method, new)], old
