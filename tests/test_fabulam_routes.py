"""The fabulam in the app (0.9, lane M5; pins section 10; the design's 6): the routes `/api/fabulam/*`
(`enough/routes/fabulam.py`, over `enough/fabulam_job.py`'s entry functions and nothing else), the readvisor's
`fabulam` tool (`enough/fabula_tools.py`), and the card's state function on the page.

- Every POST is behind the promise header and the Origin gate; a missing path, a file that is no Lean, and a folder
  past the band are refused before a job starts, in words.
- With no model a build lands the outline (the survey by rule) and says what waits; the sentence of
  `P:claim/checking` is in the state, in full.
- A file that ends in more than three results and names no target builds nothing: the answer lists them.
- The tool runs only with the macrocosm-oes skill on, and starts the same jobs.
- The page's `fmStateLine` says each of the seven states in the job's own words (run under node), and the face has
  nothing that could read as "verified".

No model runs here and nothing of Lean is run: the routes use a dead model URL (the app is in rules mode), and the
states that need a model's stages are made with the hand-recorded answers (`tests/fixtures/fabula/fabulam/recorded/`).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import api_promise as P
from enough import canon, models, skeleton
from enough import fabula_tools as FT
from enough import fabulam_job as J
from enough import thym_host as H
from enough.server import create_app
from tests.test_canon_tools import run, tool
from tests.test_fabulam_moves import DEFAULT_CHECKING, LEAN, NOW, OWN, REC, TARGET, Recorded, runtime
from tests.test_prompt_weight import enable_skill

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")
NODE = shutil.which("node")
MANY = ["Many.one_le_two", "Many.two_le_three", "Many.three_le_four", "Many.four_le_five"]


def wait_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {snap}")


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copy(LEAN, proj / LEAN.name)
    shutil.copy(OWN / "Many.lean", proj / "Many.lean")
    shutil.copytree(OWN / "Parity", proj / "Parity")
    (proj / "notes.md").write_text("# notes\n", encoding="utf-8")
    return proj


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = _project(tmp_path)
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), canon.root(), H.host_root()):
        assert str(where).startswith(str(tmp_path)), where
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app, headers={"X-Enough-Api": "1"}) as c:
        c._project = proj  # type: ignore[attr-defined]
        c._app = app  # type: ignore[attr-defined]
        yield c
    FT.configure()


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------

def test_every_post_takes_the_promise_header_and_the_origin_gate(client: TestClient):
    for path in ("/api/fabulam/build", "/api/fabulam/resume", "/api/fabulam/entail", "/api/fabulam/cancel"):
        assert P.model_run("POST", path), path
    with TestClient(client._app) as bare:  # type: ignore[attr-defined]
        r = bare.post("/api/fabulam/build", json={"path": LEAN.name})
        assert r.status_code == 403 and r.json()["detail"] == P.MODEL_RUN_MISSING
        r = bare.post("/api/fabulam/build", json={"path": LEAN.name}, headers={"X-Enough-Api": "2"})
        assert r.status_code == 403 and "keeps API promise 1" in r.json()["detail"]
    r = client.post("/api/fabulam/build", json={"path": LEAN.name}, headers={"Origin": "https://elsewhere.example"})
    assert r.status_code == 403, r.text
    r = client.post("/api/fabulam/entail", json={"path": LEAN.name}, headers={"Origin": "http://127.0.0.1:1"})
    assert r.status_code == 403, r.text
    assert not (client._project / "primes-congruent-one.fabulam.cosm").exists()  # type: ignore[attr-defined]
    # reads take neither
    assert client.get("/api/fabulam/state", params={"path": LEAN.name},
                      headers={"Origin": "https://elsewhere.example"}).status_code == 200


def test_a_missing_path_a_file_that_is_no_lean_and_a_folder_past_the_band_are_refused(client: TestClient):
    r = client.post("/api/fabulam/build", json={"path": "Nowhere.lean"})
    assert r.status_code == 404 and "no such Lean file" in r.json()["detail"]
    r = client.post("/api/fabulam/build", json={})
    assert r.status_code == 400 and "missing path" in r.json()["detail"]
    assert client.get("/api/fabulam/state", params={"path": "Nowhere.lean"}).status_code == 404
    r = client.post("/api/fabulam/build", json={"path": "notes.md"})
    assert r.status_code == 400 and "is no Lean file" in r.json()["detail"]
    r = client.post("/api/fabulam/build", json={"path": "canon:anything.lean"})
    assert r.status_code == 400 and "not from the Canon store" in r.json()["detail"]
    proj = client._project  # type: ignore[attr-defined]
    (proj / "Big").mkdir()
    for k in range(61):
        (proj / "Big" / f"F{k}.lean").write_text(f"theorem t{k} : True := trivial\n", encoding="utf-8")
    r = client.post("/api/fabulam/build", json={"path": "Big", "target": "t0"})
    assert r.status_code == 413 and r.json()["detail"] == "more than sixty Lean files: past what this build reads"
    (proj / "Long.lean").write_text("theorem t : True := trivial\n" + "-- a line\n" * 12001, encoding="utf-8")
    r = client.post("/api/fabulam/build", json={"path": "Long.lean"})
    assert r.status_code == 413 and "twelve thousand lines" in r.json()["detail"]
    assert not list(proj.glob("*.fabulam.cosm"))
    r = client.post("/api/fabulam/build", json={"path": LEAN.name, "route": "moon"})
    assert r.status_code == 400 and "route is local or cloud" in r.json()["detail"]
    r = client.post("/api/fabulam/build", json={"path": LEAN.name, "target": 7})
    assert r.status_code == 400 and "target is the full name" in r.json()["detail"]


def test_with_no_model_a_build_lands_the_outline_and_the_checking_sentence_in_full(client: TestClient):
    st = client.get("/api/fabulam/state", params={"path": LEAN.name}).json()
    assert (st["state"]["state"], st["state"]["kind"], st["job"]) == ("none", "file", None)
    assert st["state"]["line"] == "no fabulam yet: building it writes primes-congruent-one.fabulam.cosm"
    r = client.post("/api/fabulam/build", json={"path": LEAN.name})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job"]["kind"] == "fabulam" and body["job"]["mode"] == "rules"
    snap = wait_job(client, body["job"]["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert [x["stage"] for x in res["ran"]] == ["survey"] and res["refusal"]["program"] == "read-the-proof"
    assert res["fabulam"] == "primes-congruent-one.fabulam.cosm" and "read-the-proof waits" in res["message"]
    st = client.get("/api/fabulam/state", params={"path": LEAN.name}).json()["state"]
    assert (st["state"], st["landed"], st["next"]) == ("outline", 1, "read-the-proof")
    assert st["line"] == "an outline: the survey landed by rules; reading waits for a model"
    assert st["checking"] == DEFAULT_CHECKING
    assert [p["density"] for p in st["pshorts"]] == ["expert", "student", "everyone"]
    assert not any(p["exists"] for p in st["pshorts"])
    # the same, named by the fabulam itself
    by_fab = client.get("/api/fabulam/state", params={"path": "primes-congruent-one.fabulam.cosm"}).json()["state"]
    assert (by_fab["state"], by_fab["source"]) == ("outline", LEAN.name)
    # taken up again: the read still waits; nothing to take up on a file never surveyed
    r = client.post("/api/fabulam/resume", json={"path": LEAN.name})
    assert r.status_code == 200, r.text
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["result"]["ran"] == [] and snap["result"]["refusal"]["program"] == "read-the-proof"
    r = client.post("/api/fabulam/resume", json={"path": "Many.lean"})
    assert r.status_code == 409 and "nothing to take up again" in r.json()["detail"]
    # an outline has no pshort, with or without a model
    r = client.post("/api/fabulam/entail", json={"path": "primes-congruent-one.fabulam.cosm", "density": "everyone"})
    assert r.status_code == 409 and "is an outline" in r.json()["detail"]
    r = client.post("/api/fabulam/entail", json={"path": LEAN.name, "density": "children"})
    assert r.status_code == 400 and "density is expert, student or everyone" in r.json()["detail"]
    r = client.post("/api/fabulam/cancel", json={"path": LEAN.name})
    assert r.status_code == 409 and "is running" in r.json()["detail"]


def test_a_file_that_ends_in_several_results_builds_nothing_until_one_is_chosen(client: TestClient):
    st = client.get("/api/fabulam/state", params={"path": "Many.lean"}).json()["state"]
    assert (st["state"], st["targets"]) == ("pick", MANY)
    assert st["line"] == "this file ends in 4 results: choose the one to tell"
    r = client.post("/api/fabulam/build", json={"path": "Many.lean"})
    assert r.status_code == 200 and r.json()["job"] is None and r.json()["targets"] == MANY
    assert r.json()["refusal"]["check"] == "pick"
    assert not (client._project / "many.fabulam.cosm").exists()  # type: ignore[attr-defined]
    r = client.post("/api/fabulam/build", json={"path": "Many.lean", "target": ["Many.two_le_three"]})
    snap = wait_job(client, r.json()["job"]["id"])
    assert [x["stage"] for x in snap["result"]["ran"]] == ["survey"]
    st = client.get("/api/fabulam/state", params={"path": "Many.lean"}).json()["state"]
    assert (st["state"], st["targets"], st["target_by"]) == ("outline", ["Many.two_le_three"], "given")


def test_the_persons_entry_on_checking_reaches_the_sentence_through_the_build(client: TestClient):
    r = client.post("/api/fabulam/build", json={"path": LEAN.name, "said": "Mathlib's CI builds this file.",
                                                "said_by": "the owner", "said_at": "2026-11-22"})
    wait_job(client, r.json()["job"]["id"])
    st = client.get("/api/fabulam/state", params={"path": LEAN.name}).json()["state"]
    assert (st["said"], st["said_by"], st["said_at"]) == ("Mathlib's CI builds this file.", "the owner", "2026-11-22")
    assert st["checking"].startswith(DEFAULT_CHECKING) and "the owner says: Mathlib's CI builds this file." in \
        st["checking"]


def test_a_folder_of_lean_is_built_under_a_head(client: TestClient):
    st = client.get("/api/fabulam/state", params={"path": "Parity"}).json()["state"]
    assert (st["kind"], st["state"], st["name"]) == ("folder", "none", "parity.fabulam.cosm")
    r = client.post("/api/fabulam/build", json={"path": "Parity"})
    assert r.status_code == 200, r.text
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["state"] == "done", snap
    st = client.get("/api/fabulam/state", params={"path": "parity.fabulam.cosm"}).json()["state"]
    assert st["kind"] == "folder" and st["exists"] and st["state"] in ("outline", "partway")
    assert st["head_line"].endswith("not reached and left as outlines") and st["checking"]
    parts = sorted(p.relative_to(client._project).as_posix()  # type: ignore[attr-defined]
                   for p in (client._project / "parity.fabulam.parts").rglob("*.fabulam.cosm"))  # type: ignore[attr-defined]
    assert parts, "the parts were written under the head"
    part = client.get("/api/fabulam/state", params={"path": parts[0]}).json()["state"]
    assert part["part"] and part["kind"] == "file" and part["source"].startswith("Parity/")
    r = client.post("/api/fabulam/build", json={"path": parts[0]})
    assert r.status_code == 409 and "a part is built with its head" in r.json()["detail"]


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

def test_the_fabulam_tool_runs_only_with_the_skill_on_and_starts_the_same_jobs(client: TestClient):
    project = client._project  # type: ignore[attr-defined]
    r = run(project, tool("fabulam", path=LEAN.name))
    assert not r.ok and "macrocosm-oes skill" in r.body
    enable_skill(project, "macrocosm-oes")
    r = run(project, tool("fabulam", path=LEAN.name))
    assert r.ok and "no fabulam yet: building it writes primes-congruent-one.fabulam.cosm" in r.body, r.body
    r = run(project, tool("fabulam", path=LEAN.name, do="build"))
    assert r.ok and r.body.startswith("job cn") and "stops at the outline" in r.body, r.body
    snap = wait_job(client, r.body.split()[1].rstrip(":"))
    assert snap["state"] == "done" and snap["kind"] == "fabulam"
    r = run(project, tool("fabulam", path="primes-congruent-one.fabulam.cosm", do="status"))
    assert r.ok and "an outline: the survey landed by rules" in r.body, r.body
    assert f"what is said about checking: {DEFAULT_CHECKING}" in r.body
    assert "pshorts: expert none; student none; everyone none" in r.body
    # several results and no target: the list, and nothing built
    r = run(project, tool("fabulam", path="Many.lean", do="build"))
    assert r.ok and r.body.startswith("nothing was built") and ", ".join(MANY) in r.body and "never pick" in r.body
    assert not (project / "many.fabulam.cosm").exists()
    r = run(project, tool("fabulam", path="Many.lean", do="build", target="Many.one_le_two"))
    assert r.ok and r.body.startswith("job cn"), r.body
    wait_job(client, r.body.split()[1].rstrip(":"))
    # entail wants a density, and an outline has no pshort
    r = run(project, tool("fabulam", path=LEAN.name, do="entail"))
    assert not r.ok and "Offer the three" in r.body
    r = run(project, tool("fabulam", path=LEAN.name, do="entail", density="student"))
    assert not r.ok and "is an outline" in r.body, r.body
    r = run(project, tool("fabulam", path=LEAN.name, do="paint"))
    assert not r.ok and "<do> is build, resume, entail, status or cancel" in r.body
    r = run(project, tool("fabulam", path="notes.md"))
    assert not r.ok and "is no Lean file" in r.body
    r = run(project, tool("fabulam"))
    assert not r.ok and "needs a <path>" in r.body


def test_the_tool_is_in_the_prompt_only_beside_its_skill():
    from enough import prompt
    assert "fabulam" in FT.TOOL_NAMES and FT._RUNNERS["fabulam"] is FT.run_fabulam
    assert "`fabulam` does build (`<target>`), resume, entail (`<density>`)" in prompt.FABULA_TOOL_INSTRUCTIONS
    assert "`fabulam` a Lean file's" in prompt.FABULA_LEAN_INSTRUCTIONS
    assert "`fabulam`" in prompt.FABULA_ABSENT_INSTRUCTIONS


# ---------------------------------------------------------------------------
# The card's state function (the page, under node)
# ---------------------------------------------------------------------------

def _fn(name: str) -> str:
    m = re.search(r"\n    (?:async )?function " + re.escape(name) + r"\(", HTML)
    assert m, name
    end = HTML.index("\n    }\n", m.end())
    return HTML[m.start():end + 6]


def _const(name: str) -> str:
    m = re.search(r"\n    const " + re.escape(name) + r" = ", HTML)
    assert m, name
    end = HTML.index(";\n", m.end())
    return HTML[m.start():end + 2]


def _lines_by_page(states: list[dict]) -> list[str]:
    js = ("const t = (k, d) => d;\n" + _const("FM_PROGRAM_WORD") + _fn("fmStageWord") + _fn("fmStateLine")
          + f"\nconst states = {json.dumps(states)};\n"
          "console.log(JSON.stringify(states.map(fmStateLine)));\n")
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _seven(tmp_path: Path) -> dict[str, dict]:
    """The seven states of one Lean file's fabulam, each made by the job's own functions."""
    out: dict[str, dict] = {}

    def proj(name: str, src: Path = LEAN) -> Path:
        p = tmp_path / name
        p.mkdir()
        shutil.copy(src, p / src.name)
        return p

    p = proj("none")
    out["none"] = J.file_state(p, p / LEAN.name)
    p = proj("pick", OWN / "Many.lean")
    out["pick"] = J.file_state(p, p / "Many.lean")
    p = proj("outline")
    J.run_file_build(p, p / LEAN.name, mode="rules", why="no model", runtime=runtime(), now=NOW)
    out["outline"] = J.file_state(p, p / LEAN.name)
    p = proj("partway")
    with pytest.raises(RuntimeError):
        J.run_file_build(p, p / LEAN.name, mode="model", now=NOW,
                         runtime=runtime(Recorded(REC / "primes-congruent-one", {"comments": "not: an audit"})))
    out["partway"] = J.file_state(p, p / LEAN.name)
    p = proj("complete")
    assert J.run_file_build(p, p / LEAN.name, mode="model", now=NOW,
                            runtime=runtime(Recorded(REC / "primes-congruent-one")))["complete"]
    out["complete"] = J.file_state(p, p / LEAN.name)
    p = proj("moved")
    J.run_file_build(p, p / LEAN.name, mode="rules", why="no model", runtime=runtime(), now=NOW)
    with (p / LEAN.name).open("a", encoding="utf-8") as f:
        f.write("\n-- a line added\n")
    out["moved"] = J.file_state(p, p / LEAN.name)
    p = proj("gone")
    J.run_file_build(p, p / LEAN.name, mode="rules", why="no model", runtime=runtime(), now=NOW)
    (p / LEAN.name).unlink()
    out["gone"] = J.file_state(p, p / LEAN.name)
    return out


@pytest.mark.skipif(NODE is None, reason="node is not on PATH")
def test_the_cards_state_function_says_each_of_the_seven_states_in_the_jobs_words(tmp_path: Path):
    seven = _seven(tmp_path)
    assert [s["state"] for s in seven.values()] == list(seven) == ["none", "pick", "outline", "partway", "complete",
                                                                    "moved", "gone"]
    assert (seven["partway"]["landed"], seven["partway"]["next"]) == (2, "audit-the-comments")
    states = [{**s, "kind": "file"} for s in seven.values()]
    assert _lines_by_page(states) == [s["line"] for s in seven.values()]
    assert all(s["line"] == J.STATE_LINES[k].format(name=s["name"], n=s["landed"] if k != "pick" else 4, m=s["of"],
                                                    next=J.STAGE_WORDS.get(s["next"] or "", "the survey"))
               for k, s in seven.items())
    assert seven["complete"]["checking"] == DEFAULT_CHECKING and seven["complete"]["targets"] == [TARGET]


@pytest.mark.skipif(NODE is None, reason="node is not on PATH")
def test_a_folders_lines_are_its_own():
    lines = _lines_by_page([
        {"kind": "folder", "state": "pick", "targets": ["a", "b", "c", "d", "e"]},
        {"kind": "folder", "state": "partway", "next": "B.lean",
         "parts": [{"reached": True, "state": "complete", "tied": True}, {"reached": True, "state": "outline",
                                                                          "tied": False}]},
        {"kind": "folder", "state": "partway", "next": "fold-the-head", "parts": [{"reached": True,
                                                                                   "state": "complete", "tied": True}]},
        {"kind": "folder", "state": "moved"}, {"kind": "folder", "state": "gone"}])
    assert lines == ["this folder ends in 5 results: choose the ones to tell",
                     "1 of 2 files landed; the build can take up again from B.lean",
                     "1 of 1 files landed; the build can take up again from fold",
                     "the folder has changed since its fabulam was surveyed: a build starts again from the survey",
                     "the folder is not there any more; its fabulam stays as it is"]


def test_the_face_has_nothing_that_could_read_as_verified_and_writes_the_entries_through_the_build():
    face = "".join(_fn(n) for n in ("fmPaint", "fmStagesHTML", "fmViewerTopHTML", "fmPshortHTML", "fmStateLine"))
    for mark in ("✓", "✔", "thym-fits", "verified", "badge", "cosm-ok"):
        assert mark not in face, mark
    paint = _fn("fmPaint")
    assert "s.checking" in paint and "fm-checking" in paint          # the sentence, in full, under the state
    assert "data-fm-density" in paint and "fmPshortWords(p)" in paint   # one row per density
    assert 'id="fm-said"' in paint and "fm-said-by" in paint and "fm-said-at" in paint and "fm-wording" in paint
    clicks = HTML[HTML.index("case 'said': void fmGo('build'"):][:400]
    assert "said_by" in clicks and "said_at" in clicks
    assert "fmPost(resume ? '/api/fabulam/resume' : '/api/fabulam/build'" in _fn("fmGo")
    assert "'/api/fabulam/entail'" in _fn("fmEntail")
    # the tree marks a folder that holds Lean, and the menus offer the card on a .lean file, a folder, a fabulam
    menu = _fn("fabMenuItems")
    assert "FM_LEAN_RE.test(p)" in menu and "FM_FABULAM_RE.test(p)" in menu and "target.lean" in menu
    assert "lean: li.dataset.lean === '1'" in HTML


def test_a_folder_that_holds_lean_is_marked_in_the_tree(client: TestClient):
    html = client.get("/api/files").text
    assert re.search(r'<li class="dir[^"]*"[^>]*data-path="Parity"[^>]*data-lean="1"', html), html[:400]
    assert 'data-path="rness"' not in html or not re.search(r'data-path="rness"[^>]*data-lean', html)
