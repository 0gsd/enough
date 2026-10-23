"""The derivation routes (0.4.3, P3): `/api/canon/derive`, `/api/canon/atem`, `/api/canon/atem/pin`,
`/api/canon/emf`, `/api/canon/compile`, `/api/canon/job/{id}` (+ cancel) — refusals, jobs to completion, the
`canon` SSE event, catalogs regenerated after writes, and the generation-lock rule.

TestClient over `create_app(..., supervise=False)` with a dead llm_url (port 9), so `llm.reachable` reports no
model and every job runs in rules mode unless a test stands in for the model (`llm.reachable` and `llm.complete`
monkeypatched). The store and every other seam point inside tmp_path (conftest); `ensure_skeleton` runs before
`create_app`; `models.LIVE_STATE` (read once at import) is pointed at tmp_path too.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import canon, canon_derive as CD, dictionary, llm, macrocosm, models, skeleton
from enough.server import create_app
from tests.test_canon_derive import ATEM_YAML, good, kind_of

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"
LONG_PARA = " ".join(["The orchard keeps a record of every tree it plants."] * 12)
LONG = "# The long notes\n\n" + "\n\n".join([LONG_PARA] * 8) + "\n"
HELLO = "# Hello\n\nA short note about the lane by the orchard. It has two sentences.\n"


def _wait_for(path: Path, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.02)
    return path.is_file()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", proj / "rain.cosm")
    shutil.copytree(FIX / "holotypes" / "meadow", proj / "meadow")
    (proj / "meadow" / "NOTES.md").write_text("A text inside a Holotype.\n", encoding="utf-8")
    (proj / "hello.md").write_text(HELLO, encoding="utf-8")
    (proj / "long.md").write_text(LONG, encoding="utf-8")
    (proj / "empty.md").write_text("  \n", encoding="utf-8")
    (proj / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (proj / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (proj / "report.pdf").write_bytes(b"%PDF-1.4\n\x00\x01\x02")
    (proj / "memo.pdf").write_bytes(b"%PDF-1.4\n\x00\x01\x02")
    (proj / "memo.pdf.md").write_text("# Memo\n\nThe memo says the budget is due in March.\n", encoding="utf-8")
    (proj / "other.md").write_text("Some text.\n", encoding="utf-8")
    (proj / "other.md.cosm").write_text("oes: canon/1\nid: canon/x\nname: x\nnodes: []\n", encoding="utf-8")
    (proj / "folder").mkdir()
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(canon.root()).startswith(str(tmp_path))
    assert str(dictionary.state_root()).startswith(str(tmp_path))
    assert str(models.LIVE_STATE).startswith(str(tmp_path))
    canon.create_volume("lib")
    (canon.volume_dir("lib") / "guide.md").write_text("# The guide\n\nMeadow closes the books overnight.\n",
                                                      encoding="utf-8")
    return proj


@pytest.fixture
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        assert _wait_for(project / canon.PROJECT_CATALOG)
        yield c


@pytest.fixture
def sse_events(monkeypatch: pytest.MonkeyPatch) -> list:
    """Everything the session fans out over SSE."""
    from enough import server as _server

    seen: list[tuple[str, dict]] = []
    original = _server.Session.emit

    async def spy(self, event, data):
        seen.append((event, data))
        await original(self, event, data)

    monkeypatch.setattr(_server.Session, "emit", spy)
    return seen


class _Calls(list):
    """The messages of every completion asked for, and the `max_tokens` each was given."""

    def __init__(self):
        super().__init__()
        self.budgets: list = []


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list:
    """A model that answers: reachable, and `llm.complete` returning canned EMF (one claim with a bad stance the
    repair turn fixes) and the atem."""
    calls = _Calls()

    def complete(messages, **kw):
        calls.append(messages)
        calls.budgets.append(kw.get("max_tokens"))
        system = messages[0]["content"]
        if system.startswith("You write the atem"):
            return ATEM_YAML, {"model": "fake-model", "route": "local"}
        if system.startswith("You write a text back"):
            return "# The orchard\n\nProse from the model.\n", {"model": "fake-model"}
        repair = "did not pass the checks" in messages[-1]["content"]
        return good("axiom" if repair else "certain"), {"model": "fake-model", "route": "local",
                                                         "finish_reason": "stop"}

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", complete)
    return calls


def wait_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished: {snap}")


def start(client: TestClient, url: str, body: dict) -> dict:
    r = client.post(url, json=body)
    assert r.status_code == 200, r.text
    return r.json()["job"]


def lint_errors(path: Path) -> list[str]:
    vol = macrocosm.load_volume(path)
    assert vol.refused is None, vol.refused
    return [str(p) for p in macrocosm.lint(vol).errors]


def find(nodes: list, path: str) -> dict | None:
    for n in nodes:
        if n.get("path") == path:
            return n
        hit = find(n.get("children") or [], path)
        if hit:
            return hit
    return None


SNAPSHOT_KEYS = {"id", "kind", "path", "state", "phase", "chunk", "chunks", "message", "mode", "result", "error",
                 "started_at", "finished_at"}


# ---------------------------------------------------------------------------
# derive: rules mode end to end
# ---------------------------------------------------------------------------

def test_derive_emf_in_rules_mode_writes_a_clean_twin(client: TestClient, project: Path, sse_events):
    before = (project / canon.PROJECT_CATALOG).read_text(encoding="utf-8")
    assert "notes.md.cosm" not in before
    job = start(client, "/api/canon/derive", {"path": "notes.md", "what": "emf"})
    assert set(job) == SNAPSHOT_KEYS
    assert job["kind"] == "emf" and job["mode"] == "rules" and job["path"] == "notes.md"
    assert job["state"] in ("queued", "running") and "no model is answering" in job["message"]
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert res["twin_path"] == "notes.md.cosm" and res["text_path"] == "notes.md"
    assert res["mode"] == "rules" and res["state"] == "fresh" and res["chunks"] == 1
    assert "scaffold" in snap["message"] and snap["started_at"] and snap["finished_at"]
    twin = project / "notes.md.cosm"
    assert lint_errors(twin) == []
    doc = macrocosm.yaml_load(twin.read_text(encoding="utf-8"))
    assert doc["derived"]["mode"] == "rules" and doc["id"] == "emf/notes-md"
    # the project catalog now lists the twin behind its text
    cat = macrocosm.yaml_load((project / canon.PROJECT_CATALOG).read_text(encoding="utf-8"))
    item = next(n for n in cat["nodes"] if n.get("path") == "notes.md")
    assert item["emf"] == {"path": "notes.md.cosm"} and item["atem"]["line"].startswith("Mara Okafor")
    # the reader's route and the cosm viewer's route both read it
    emf = client.get("/api/canon/emf", params={"path": "notes.md"}).json()
    assert emf["twin_path"] == "notes.md.cosm" and emf["state"] == "fresh"
    assert emf["cosm"]["minicosm"] == "emf" and emf["cosm"]["report"]["errors"] == []
    assert client.get("/api/canon/emf", params={"path": "notes.md.cosm"}).json()["twin_path"] == "notes.md.cosm"
    viewer = client.get("/api/cosm", params={"path": "notes.md.cosm"})
    assert viewer.status_code == 200 and viewer.json()["minicosm"] == "emf"
    # the SSE `canon` event carries the snapshot, ending done
    deadline = time.time() + 5
    while time.time() < deadline and not any(e == "canon" and d["state"] == "done" for e, d in sse_events):
        client.get(f"/api/canon/job/{job['id']}")
        time.sleep(0.02)
    payloads = [d for e, d in sse_events if e == "canon" and d["id"] == job["id"]]
    assert payloads and all(set(p) == SNAPSHOT_KEYS for p in payloads)
    assert payloads[-1]["state"] == "done" and payloads[-1]["result"]["twin_path"] == "notes.md.cosm"
    assert {p["phase"] for p in payloads} >= {"lexicon", "writing", "done"}


def test_fresh_twin_refuses_without_force(client: TestClient):
    wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md"})["id"])
    r = client.post("/api/canon/derive", json={"path": "notes.md", "what": "emf"})
    assert r.status_code == 409 and "already fresh" in r.json()["detail"]
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md", "force": True})["id"])
    assert snap["state"] == "done"


def test_twin_state_agrees_with_the_listing(client: TestClient, project: Path):
    wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md"})["id"])
    wait_job(client, start(client, "/api/canon/derive", {"path": "canon:lib/guide.md"})["id"])

    def listed() -> tuple[str, str]:
        tree = client.get("/api/canon/tree").json()
        proj = find(tree["project"], "notes.md")
        lib = next(v for v in tree["cacheboxes"] if v["name"] == "lib")
        guide = find(lib["tree"], "guide.md")
        return proj["emf"]["state"], guide["emf"]["state"]

    assert listed() == ("fresh", "fresh")
    assert CD.twin_state(project / "notes.md") == "fresh"
    with (project / "notes.md").open("a", encoding="utf-8") as fh:
        fh.write("\nAn afterthought.\n")
    assert listed()[0] == "stale" == CD.twin_state(project / "notes.md")
    assert client.get("/api/canon/emf", params={"path": "notes.md"}).json()["state"] == "stale"
    # a stale twin is no longer "already fresh"
    assert client.post("/api/canon/derive", json={"path": "notes.md"}).status_code == 200


def test_derive_in_a_canon_volume_regenerates_its_catalog(client: TestClient):
    vol = canon.volume_dir("lib")
    canon.regenerate_catalog("lib")
    assert "guide.md.cosm" not in (vol / "canon.cosm").read_text(encoding="utf-8")
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "canon:lib/guide.md"})["id"])
    assert snap["state"] == "done", snap
    assert snap["result"]["twin_path"] == "canon:lib/guide.md.cosm"
    twin = vol / "guide.md.cosm"
    assert lint_errors(twin) == []
    assert macrocosm.yaml_load(twin.read_text(encoding="utf-8"))["id"] == "emf/guide-md"
    cat = macrocosm.yaml_load((vol / "canon.cosm").read_text(encoding="utf-8"))
    item = next(n for n in cat["nodes"] if n.get("path") == "guide.md")
    assert item["emf"]["path"] == "guide.md.cosm" and item["emf"]["state"] == "fresh"
    emf = client.get("/api/canon/emf", params={"path": "cacheawl:lib/guide.md"}).json()
    assert emf["twin_path"] == "cacheawl:lib/guide.md.cosm"


def test_derive_reads_a_converted_original_through_its_markdown(client: TestClient, project: Path):
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "memo.pdf"})["id"])
    assert snap["state"] == "done", snap
    assert snap["result"]["text_path"] == "memo.pdf.md" and snap["result"]["twin_path"] == "memo.pdf.md.cosm"
    assert (project / "memo.pdf.md.cosm").is_file() and not (project / "memo.pdf.cosm").exists()
    assert client.get("/api/canon/emf", params={"path": "memo.pdf"}).json()["twin_path"] == "memo.pdf.md.cosm"


@pytest.mark.parametrize("path,status,words", [
    ("nope.md", 404, "no such file"),
    ("folder", 400, "is a folder"),
    ("meadow", 400, "Holotype is browsed"),
    ("meadow/NOTES.md", 400, "Holotype is browsed"),
    ("meadow/holotype.cosm", 400, "Holotype is browsed"),
    ("rness/canon.cosm", 400, "kept by enough"),
    ("canon:lib/canon.cosm", 400, "kept by enough"),
    ("canon:lib/.canon.json", 400, "kept by enough"),
    ("rain.cosm", 400, "already enumerated"),
    ("pic.png", 400, "binary"),
    ("report.pdf", 400, "convert it first"),
    ("data.csv", 400, "markdown and plain text"),
    ("empty.md", 400, "empty"),
    ("other.md", 409, "not an EMF twin"),
    ("../outside.md", 400, "invalid path"),
    ("", 400, "missing path"),
])
def test_derive_refusals(client: TestClient, project: Path, path: str, status: int, words: str):
    r = client.post("/api/canon/derive", json={"path": path, "what": "emf"})
    assert r.status_code == status, (path, r.text)
    assert words in r.json()["detail"], (path, r.json())
    assert not (project / "other.md.cosm").read_text(encoding="utf-8").startswith("oes: emf/1")


def test_derive_refuses_an_unknown_what(client: TestClient):
    r = client.post("/api/canon/derive", json={"path": "notes.md", "what": "summary"})
    assert r.status_code == 400 and "emf or atem" in r.json()["detail"]


# ---------------------------------------------------------------------------
# atems and pins
# ---------------------------------------------------------------------------

def test_file_atem_makes_a_minimal_twin(client: TestClient, project: Path):
    snap = wait_job(client, start(client, "/api/canon/atem", {"path": "hello.md"})["id"])
    assert snap["state"] == "done" and snap["kind"] == "atem", snap
    res = snap["result"]
    assert res["written"] is True and res["twin_path"] == "hello.md.cosm" and res["mode"] == "rules"
    assert res["atem"]["line"] == "A short note about the lane by the orchard."
    assert res["atem"]["push"] == {"pending": "a model has not read this passage"}
    doc = macrocosm.yaml_load((project / "hello.md.cosm").read_text(encoding="utf-8"))
    assert doc["derived"]["completeness"] == "atem" and doc["nodes"] == [] and doc["name"] == "Hello"
    assert lint_errors(project / "hello.md.cosm") == []
    cat = macrocosm.yaml_load((project / canon.PROJECT_CATALOG).read_text(encoding="utf-8"))
    item = next(n for n in cat["nodes"] if n.get("path") == "hello.md")
    assert item["atem"]["line"] == "A short note about the lane by the orchard."
    # derive what=atem on a fresh atem is "already fresh"; the atem route itself always remakes it
    assert client.post("/api/canon/derive", json={"path": "hello.md", "what": "atem"}).status_code == 409
    assert wait_job(client, start(client, "/api/canon/atem", {"path": "hello.md"})["id"])["state"] == "done"
    # a full derive upgrades the minimal twin even though it is fresh
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "hello.md"})["id"])
    assert snap["state"] == "done"
    full = macrocosm.yaml_load((project / "hello.md.cosm").read_text(encoding="utf-8"))
    assert full["derived"]["completeness"] == "full" and full["nodes"]


def test_passage_atem_is_pinnable_and_writes_nothing(client: TestClient, project: Path):
    sel = {"text": "The parish council's grounds team wants to mow the meadow strip in July.\n"
                   "Mowing then would cut the wildflowers before they seed, and the strip exists\n"
                   "to feed the pollinators the orchard depends on. If the strip is mown in July,\n"
                   "the orchard loses the very insects that set its fruit."}
    snap = wait_job(client, start(client, "/api/canon/atem", {"path": "notes.md", "selection": sel})["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert res["pinnable"] is True and res["written"] is False and res["path"] == "notes.md"
    assert res["span"]["lines"] == "17-20"
    assert res["span"]["start"] == "The parish council's grounds team wants to mow the meadow st"
    assert res["line"].startswith("The parish council's grounds team wants to mow")
    assert res["mode"] == "rules" and res["stance_profile"] == {}
    assert not (project / "notes.md.cosm").exists()


def test_text_atem_and_input_refusals(client: TestClient):
    snap = wait_job(client, start(client, "/api/canon/atem", {"text": "Rain runs off dry soil. It pools."})["id"])
    assert snap["result"]["pinnable"] is False and snap["result"]["path"] is None
    assert snap["result"]["line"] == "Rain runs off dry soil."
    for body, words in (({}, "nothing to make an atem of"),
                        ({"selection": "text"}, "selection must be"),
                        ({"text": "x" * 200_001}, "too long"),
                        ({"path": "meadow", "selection": {"text": "x"}}, "Holotype")):
        r = client.post("/api/canon/atem", json=body)
        assert r.status_code == 400 and words in r.json()["detail"], (body, r.text)


def test_pin_creates_then_appends(client: TestClient, project: Path, sse_events):
    atem = {"line": "Mowing the strip in July would starve the orchard's pollinators before the fruit sets.",
            "focus": "The mowing date.", "push": "Wait until September.", "pull": "The orchard needs the strip."}
    r = client.post("/api/canon/atem/pin", json={"path": "notes.md", "atem": atem, "span": {"lines": "17-20"},
                                                 "of": ["P:claim/missing"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["twin_path"] == "notes.md.cosm" and body["item_id"] == "X:atem/1"
    assert body["job"]["kind"] == "pin" and body["job"]["state"] == "done" and body["job"]["mode"] == "model"
    twin = project / "notes.md.cosm"
    doc = macrocosm.yaml_load(twin.read_text(encoding="utf-8"))
    assert doc["derived"]["completeness"] == "atem" and [n["id"] for n in doc["nodes"]] == ["X:atem/1"]
    assert doc["nodes"][0]["of"] == [{"pending": "P:claim/missing is not an item of this twin"}]
    assert lint_errors(twin) == []
    scaffold = {"line": "Mowing in July.", "focus": "Mowing.", "push": {"pending": "a model has not read this passage"},
                "pull": {"pending": "a model has not read this passage"}}
    r = client.post("/api/canon/atem/pin", json={"path": "notes.md", "atem": scaffold,
                                                 "span": {"start": "Mowing then", "end": "set its fruit."}})
    assert r.json()["item_id"] == "X:atem/2" and r.json()["job"]["mode"] == "rules"
    assert [n["id"] for n in macrocosm.yaml_load(twin.read_text(encoding="utf-8"))["nodes"]] == [
        "X:atem/1", "X:atem/2"]
    assert any(e == "canon" and d["kind"] == "pin" for e, d in sse_events)
    for bad, words in (({"atem": {"focus": "no line"}, "span": {"lines": "1"}}, "with a line"),
                       ({"atem": atem}, "span must say"),
                       ({"atem": atem, "span": {"lines": "nowhere"}}, "span must say"),
                       ({"atem": {**atem, "push": 3}, "span": {"lines": "1"}}, "atem.push"),
                       ({"atem": atem, "span": {"lines": "1"}, "of": "P:claim/x"}, "list of item ids")):
        r = client.post("/api/canon/atem/pin", json={"path": "notes.md", **bad})
        assert r.status_code == 400 and words in r.json()["detail"], (bad, r.text)
    r = client.post("/api/canon/atem/pin", json={"path": "rain.cosm", "atem": atem, "span": {"lines": "1"}})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------

def test_compile_writes_a_short_and_records_it_in_the_twin(client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    src, emf = project / "notes.md", project / "notes.md.cosm"
    text_before = (src.read_bytes(), src.stat().st_mtime_ns)
    twin_before = emf.read_text(encoding="utf-8")
    job = start(client, "/api/canon/compile", {"path": "notes.md.cosm"})
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and snap["kind"] == "compile", snap
    res = snap["result"]
    written = res["written"]
    assert re.fullmatch(r"notes\.short-\d{4}-\d{2}-\d{2}-\d{4}\.md", written), written
    assert res["order"] == "told", "a twin whose text is there tells in the author's order by default"
    assert res["mode"] == "rules" and res["recorded"] is True and res["emf_path"] == "notes.md.cosm"
    out = project / written
    md = out.read_text(encoding="utf-8")
    assert md.startswith("# The Hollins Lane orchard, autumn notes") and "It is assumed that" in md
    assert "## What it claims" not in md
    assert md.splitlines()[-1].startswith("*a short of notes.md, told as the author told it, compiled from its EMF "
                                          "twin on ") and md.splitlines()[-1].endswith(" by rules, without a model*")
    assert (src.read_bytes(), src.stat().st_mtime_ns) == text_before, "the text is never touched"
    # the twin gained exactly its shorts: list, and is still fresh and clean
    twin_after = emf.read_text(encoding="utf-8")
    doc = macrocosm.yaml_load(twin_after)
    assert [(x["path"], x["by"], x["mode"], x["order"]) for x in doc["shorts"]] == [(written, "rules", "rules", "told")]
    block = twin_after[twin_after.index("shorts:\n"):twin_after.index("\nnodes:") + 1]
    assert block.count("\n") == 2 and twin_after.replace(block, "", 1) == twin_before, "byte-stable but for the list"
    assert CD.twin_state(src) == "fresh" and lint_errors(emf) == []
    # twice in the same minute, by weight: a second file, never an overwrite, and a second record
    again = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm", "order": "weight"})["id"])
    assert again["result"]["written"] != written and out.read_text(encoding="utf-8") == md
    assert again["result"]["order"] == "weight"
    md2 = (project / again["result"]["written"]).read_text(encoding="utf-8")
    assert "## What it claims" in md2 and md2.splitlines()[-1].startswith("*a short of notes.md, told by weight,")
    assert [x["order"] for x in macrocosm.yaml_load(emf.read_text(encoding="utf-8"))["shorts"]] == ["told", "weight"]
    # a standalone EMF compiles beside itself, by weight, and records its short too
    rain = wait_job(client, start(client, "/api/canon/compile", {"path": "rain.cosm"})["id"])
    assert re.fullmatch(r"rain\.short-\d{4}-\d{2}-\d{2}-\d{4}\.md", rain["result"]["written"])
    assert rain["result"]["order"] == "weight"
    assert macrocosm.yaml_load((project / "rain.cosm").read_text(encoding="utf-8"))["shorts"][0]["order"] == "weight"
    # the project catalog lists the shorts as ordinary files, marked, and the text with its shorts
    cat = macrocosm.yaml_load((project / canon.PROJECT_CATALOG).read_text(encoding="utf-8"))
    items = {n["path"]: n for n in cat["nodes"]}
    assert items[written]["short_of"] == "notes.md" and items[written]["type"] == "file"
    assert items["notes.md"]["shorts"] == sorted([written, again["result"]["written"]])
    assert items[rain["result"]["written"]]["short_of"] == "rain.cosm"
    assert items["rain.cosm"]["shorts"] == [rain["result"]["written"]]
    # the short is visible in the file tree, not hidden like a twin
    tree = client.get("/api/files").text
    assert f'data-path="{written}"' in tree


def test_compile_with_the_text_gone_defaults_to_weight(client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "orphan.cosm")     # names notes.md… beside it
    (project / "elsewhere").mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "elsewhere" / "notes.md.cosm")
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "elsewhere/notes.md.cosm"})["id"])
    assert snap["state"] == "done" and snap["result"]["order"] == "weight", snap
    assert snap["result"]["written"].startswith("elsewhere/notes.short-")
    told = wait_job(client, start(client, "/api/canon/compile",
                                  {"path": "elsewhere/notes.md.cosm", "order": "told"})["id"])
    assert told["result"]["order"] == "told", "told can still be asked for: the spans place the items"


def test_compile_order_validation(client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    for bad in ("as it happened", "TOLDX", 3, ["told"]):
        r = client.post("/api/canon/compile", json={"path": "notes.md.cosm", "order": bad})
        assert r.status_code == 400 and "told or weight" in r.json()["detail"], (bad, r.text)
    assert not list(project.glob("notes.short-*.md")), "a refused compile writes nothing"
    ok = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm", "order": " Weight "})["id"])
    assert ok["result"]["order"] == "weight"


def test_compile_shares_the_texts_claim(client: TestClient, project: Path):
    """A compile writes the twin (its shorts: list), so it holds the claim a decompile of the text holds."""
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    jobs = client.app.state.canon_jobs
    with jobs.holding(str(project.resolve() / "notes.md"), "notes.md"):
        r = client.post("/api/canon/compile", json={"path": "notes.md.cosm"})
        assert r.status_code == 409, r.text
    assert wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm"})["id"])["state"] == "done"


@pytest.mark.parametrize("path,status,words", [
    ("nope.cosm", 404, "no such file"),
    ("notes.md", 400, "not an EMF"),
    ("rness/canon.cosm", 400, "declares canon/1"),
    ("meadow/holotype.cosm", 400, "not an EMF"),
    ("", 400, "missing path"),
])
def test_compile_refusals(client: TestClient, path: str, status: int, words: str):
    r = client.post("/api/canon/compile", json={"path": path})
    assert r.status_code == status and words in r.json()["detail"], (path, r.text)


# ---------------------------------------------------------------------------
# jobs: model mode, the generation lock, cancel, claims
# ---------------------------------------------------------------------------

def test_job_routes_404_and_409(client: TestClient):
    assert client.get("/api/canon/job/cn999").status_code == 404
    assert client.post("/api/canon/job/cn999/cancel").status_code == 404
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "hello.md"})["id"])
    r = client.post(f"/api/canon/job/{snap['id']}/cancel")
    assert r.status_code == 409 and "not running" in r.json()["detail"]


def test_model_mode_job(client: TestClient, project: Path, model: list):
    job = start(client, "/api/canon/derive", {"path": "notes.md"})
    assert job["mode"] == "model"
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    assert snap["result"]["mode"] == "model" and snap["result"]["model"] == "fake-model"
    assert snap["result"]["dropped"] == 0 and snap["result"]["counts"]["P"] == 2
    assert [kind_of(m) for m in model] == ["passage", "repair", "atem"]
    assert model.budgets == [CD.EMF_MAX_TOKENS, CD.EMF_MAX_TOKENS, None], "EMF calls carry the output budget"
    assert snap["result"]["continued"] == 0 and snap["result"]["normalized"] >= 0
    twin = project / "notes.md.cosm"
    assert lint_errors(twin) == []
    doc = macrocosm.yaml_load(twin.read_text(encoding="utf-8"))
    assert doc["derived"]["model"] == "fake-model" and doc["derived"]["mode"] == "model"
    assert doc["atem"]["push"] == "Ask the parish council to wait until September before mowing."
    # compile, model mode: one completion, its prose written, the footer naming the model and the order
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm"})["id"])
    written = (project / snap["result"]["written"]).read_text(encoding="utf-8")
    assert written.startswith("# The orchard\n\nProse from the model.\n\n---\n\n*a short of notes.md, told as the "
                              "author told it, compiled from its EMF twin on ")
    assert written.endswith(" by fake-model*\n") and snap["result"]["model"] == "fake-model"
    assert macrocosm.yaml_load((project / "notes.md.cosm").read_text(encoding="utf-8"))["shorts"][0]["by"] == \
        "fake-model"
    # an atem of a passage, model mode
    snap = wait_job(client, start(client, "/api/canon/atem", {"text": "A passage."})["id"])
    assert snap["result"]["mode"] == "model" and snap["result"]["stance_profile"] == {"axiom": 1, "hearsay": 1}


def test_a_model_that_dies_mid_job_fails_it_in_words(client: TestClient, project: Path, monkeypatch):
    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))

    def dead(messages, **kw):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(llm, "complete", dead)
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md"})["id"])
    assert snap["state"] == "failed" and "the model stopped answering" in snap["error"]
    assert not (project / "notes.md.cosm").exists(), "no silent fallback to rules"


def _lock_free(client: TestClient, timeout: float = 10.0) -> bool:
    """The generation lock as the app's own loop sees it, waited for: a job publishes `done` from inside its
    `async with lock`, so the lock is let go a moment after the last snapshot, never before."""
    lock = client.app.state.session.generation_lock
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not client.portal.call(lock.locked):
            return True
        time.sleep(0.01)
    return False


def test_a_model_job_waits_for_the_generation_lock(client: TestClient, project: Path, model: list,
                                                   monkeypatch: pytest.MonkeyPatch):
    session = client.app.state.session
    client.portal.call(session.generation_lock.acquire)
    try:
        job = start(client, "/api/canon/derive", {"path": "notes.md"})
        assert job["state"] == "queued" and job["message"] == "waiting for the model"
        time.sleep(0.3)
        snap = client.get(f"/api/canon/job/{job['id']}").json()
        assert snap["state"] == "queued" and model == [], "nothing reaches the model while chat holds it"
        # A rules-mode job does not take the lock: with no model answering it runs to the end while chat still
        # holds the lock (the mode is decided at the route, so the model can be "down" for this one request).
        monkeypatch.setattr(llm, "reachable", lambda url: (False, "connection refused"))
        rules = start(client, "/api/canon/compile", {"path": "rain.cosm"})
        monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
        assert rules["mode"] == "rules"
        done = wait_job(client, rules["id"])
        assert done["state"] == "done" and done["result"]["mode"] == "rules"
        assert client.portal.call(session.generation_lock.locked), "chat still holds the lock"
        assert client.get(f"/api/canon/job/{job['id']}").json()["state"] == "queued"
    finally:
        client.portal.call(session.generation_lock.release)
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done" and snap["result"]["mode"] == "model"
    assert _lock_free(client), "the job lets the lock go when it ends"


def test_cancel_a_queued_job(client: TestClient, project: Path, model: list):
    session = client.app.state.session
    client.portal.call(session.generation_lock.acquire)
    try:
        job = start(client, "/api/canon/derive", {"path": "notes.md"})
        r = client.post(f"/api/canon/job/{job['id']}/cancel")
        assert r.status_code == 200 and r.json()["state"] == "cancelled"
        assert r.json()["message"] == "cancelled before it started"
    finally:
        client.portal.call(session.generation_lock.release)
    assert _lock_free(client)
    assert model == [] and not (project / "notes.md.cosm").exists()


def test_cancel_between_passages(client: TestClient, project: Path, monkeypatch, sse_events):
    started, release = threading.Event(), threading.Event()
    calls: list = []

    def slow(messages, **kw):
        calls.append(messages)
        if messages[0]["content"].startswith("You decompile"):
            started.set()
            release.wait(10)
            return "nodes: []", {"model": "slow"}
        return ATEM_YAML, {"model": "slow"}

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", slow)
    n_chunks = len(CD.chunk(LONG))
    assert n_chunks >= 2
    try:
        job = start(client, "/api/canon/derive", {"path": "long.md"})
        assert started.wait(10)
        # the same file is claimed while the job runs: no second derive, no pin
        assert client.post("/api/canon/derive", json={"path": "long.md", "force": True}).status_code == 409
        pin = client.post("/api/canon/atem/pin", json={"path": "long.md", "span": {"lines": "3"},
                                                       "atem": {"line": "A line."}})
        assert pin.status_code == 409
        r = client.post(f"/api/canon/job/{job['id']}/cancel")
        assert r.status_code == 200
        snap = r.json()
        assert snap["state"] == "running" and snap["phase"] == "cancelling"
        assert "finishes the passage it is reading" in snap["message"]
    finally:
        release.set()
    snap = wait_job(client, job["id"])
    assert snap["state"] == "cancelled", snap
    assert snap["message"] == f"cancelled after passage 1 of {n_chunks}; nothing was written"
    assert len(calls) == 1, "the passage being read finished; no other began"
    assert not (project / "long.md.cosm").exists()
    deadline = time.time() + 5
    while time.time() < deadline and not any(e == "canon" and d["state"] == "cancelled" for e, d in sse_events):
        time.sleep(0.02)
    assert any(e == "canon" and d["id"] == job["id"] and d["state"] == "cancelled" for e, d in sse_events)
    # released: the file can be derived again
    assert client.post("/api/canon/derive", json={"path": "long.md"}).status_code == 200


def test_home_mode_has_no_derivation_routes(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False, home=True)
    with TestClient(app) as c:
        for method, path in (("post", "/api/canon/derive"), ("post", "/api/canon/atem"),
                             ("post", "/api/canon/atem/pin"), ("get", "/api/canon/emf?path=notes.md"),
                             ("get", "/api/canon/eml?path=notes.md"),
                             ("post", "/api/canon/compile"), ("get", "/api/canon/job/cn1")):
            r = getattr(c, method)(path, **({"json": {"path": "notes.md"}} if method == "post" else {}))
            assert r.status_code == 404, path


def test_emf_route_404s_without_a_twin(client: TestClient):
    r = client.get("/api/canon/emf", params={"path": "hello.md"})
    assert r.status_code == 404 and "no EMF twin" in r.json()["detail"]
    assert client.get("/api/canon/emf", params={"path": "nope.md"}).status_code == 404
    assert client.get("/api/canon/emf", params={"path": "other.md"}).status_code == 404


def test_the_names_before_emf_still_answer_for_one_release(client: TestClient, project: Path):
    """Plan §16: `what: "eml"` is read as `emf`, and `GET /api/canon/eml` is `/api/canon/emf`, for one release."""
    job = start(client, "/api/canon/derive", {"path": "notes.md", "what": "eml"})
    assert job["kind"] == "emf"
    assert wait_job(client, job["id"])["state"] == "done"
    new = client.get("/api/canon/emf", params={"path": "notes.md"})
    old = client.get("/api/canon/eml", params={"path": "notes.md"})
    assert new.status_code == old.status_code == 200 and new.json() == old.json()
    assert client.get("/api/canon/eml", params={"path": "hello.md"}).status_code == 404
    assert macrocosm.sniff_declaration(project / "notes.md.cosm") == "emf/1"


def test_pins_survive_a_full_derive(client: TestClient, project: Path):
    atem = {"line": "Mowing the strip in July would starve the orchard's pollinators before the fruit sets.",
            "focus": "The mowing date.", "push": "Wait until September.", "pull": "The orchard needs the strip."}
    r = client.post("/api/canon/atem/pin", json={"path": "notes.md", "atem": atem, "span": {"lines": "17-20"}})
    assert r.status_code == 200 and r.json()["item_id"] == "X:atem/1"
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md"})["id"])
    assert snap["state"] == "done" and snap["result"]["counts"]["X"] == 1
    doc = macrocosm.yaml_load((project / "notes.md.cosm").read_text(encoding="utf-8"))
    assert doc["derived"]["completeness"] == "full"
    assert [n for n in doc["nodes"] if n["id"] == "X:atem/1"][0]["line"] == atem["line"]
