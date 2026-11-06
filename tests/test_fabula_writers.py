"""What writes a text's fabula and what finds it, through the app (0.6, lane C2a; MacroCOSM OES 18.4, 18.4.1,
18.4.4, 18.3.2; pins P2, P3, P6): a decompile writes `oes: fabula/1` with its `flavour` under `<text>.fabulan.cosm` or
`.fabulap.cosm`; an old-named `emf/1` twin is read and updated in place until its text is decompiled again, which
writes the new twin, carries its shorts and removes the old one only once the new one loads clean; both names at once;
every discovery site under each of the three names; the flavour plumbing; the model route per job (the lock, the
record, `derived.route`, the cloud gate).

The project, the client, the stand-in model and the job helpers are test_canon_derive_api's (a dead llm_url, every
seam in tmp_path; tests/conftest.py)."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import (canon, canon_derive as CD, canon_jobs, canon_tools as CT, cloud, fabula_names as N, home, macrocosm,
                    prompt, server)
from tests.test_canon_derive import ATEM_YAML, good
from tests.test_canon_derive_api import (FIX, client, lint_errors, model, project, sse_events, start,  # noqa: F401
                                         wait_job)
from tests.test_canon_tools import run, tool

SICK_ROSE = (FIX.parent / "fabula" / "poems" / "the-sick-rose.txt").read_text(encoding="utf-8")
OLD = (FIX / "emf" / "notes.md.cosm").read_text(encoding="utf-8")


def head(path: Path) -> dict:
    return macrocosm.yaml_load(path.read_text(encoding="utf-8"))


def new_twin(flavour: str) -> str:
    return OLD.replace("oes: emf/1\n", f"oes: fabula/1\nflavour: {flavour}\n", 1).replace(
        "id: emf/notes-md", "id: fabula/notes-md", 1)


@pytest.fixture
def lock_seen(monkeypatch: pytest.MonkeyPatch) -> list:
    """The `lock` every job was started with (None: the job does not hold the generation lock)."""
    seen: list = []
    real = canon_jobs.CanonJobs.start

    def spy(self, **kw):
        seen.append(kw.get("lock"))
        return real(self, **kw)

    monkeypatch.setattr(canon_jobs.CanonJobs, "start", spy)
    return seen


def cloud_open(monkeypatch: pytest.MonkeyPatch, *, resolved: str = "anthropic/claude-x-20261101") -> list:
    """The broker's gate open and the cloud answering as the stand-in model does; what it was asked, recorded."""
    calls: list = []
    monkeypatch.setattr(cloud, "gate_status", lambda: {"open": True, "reason": None, "denial": None,
                                                       "model_id": "cfg/model"})

    def chat_completion(messages, **kw):
        calls.append(messages)
        system = messages[0]["content"]
        if system.startswith("You write the atem"):
            text = ATEM_YAML
        elif system.startswith("You write a text back"):
            text = "# The orchard\n\nProse from the cloud.\n"
        else:
            text = good("axiom")
        return {"model": resolved, "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    def cache_completion(project_dir, **kw):
        out = Path(project_dir) / "rness" / "io" / "cloud-cache" / f"c{len(calls)}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("cached", encoding="utf-8")
        return out

    monkeypatch.setattr(cloud, "chat_completion", chat_completion)
    monkeypatch.setattr(cloud, "cache_completion", cache_completion)
    return calls


def cloud_shut(monkeypatch: pytest.MonkeyPatch, denial: str = "error: the gate's own words: turn the key on") -> str:
    monkeypatch.setattr(cloud, "gate_status", lambda: {"open": False, "reason": "no key", "denial": denial,
                                                       "model_id": None})
    return denial


# ---------------------------------------------------------------------------
# A: what a decompile writes
# ---------------------------------------------------------------------------

def test_a_fresh_decompile_writes_the_new_name_and_declaration(client: TestClient, project: Path):
    r = client.post("/api/canon/derive", json={"path": "notes.md", "what": "emf"})
    assert r.status_code == 200 and r.json()["flavour"] == "fabulan" and r.json()["suggested"] == "fabulan"
    job = r.json()["job"]
    assert job["flavour"] == "fabulan" and "route" not in job, "a rules job has no route"
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert res["twin_path"] == "notes.md.fabulan.cosm" and res["flavour"] == "fabulan" and res["replaced"] is None
    twin = project / "notes.md.fabulan.cosm"
    assert not (project / "notes.md.cosm").exists()
    assert twin.read_text(encoding="utf-8").splitlines()[:3] == ["oes: fabula/1", "macrocosm: 0.6.0",
                                                                 "flavour: fabulan"]
    doc = head(twin)
    assert list(doc)[:5] == ["oes", "macrocosm", "flavour", "id", "name"] and doc["id"] == "fabula/notes-md"
    assert "route" not in doc["derived"] and doc["derived"]["mode"] == "rules"
    assert lint_errors(twin) == []
    cat = head(project / canon.PROJECT_CATALOG)
    item = next(n for n in cat["nodes"] if n["path"] == "notes.md")
    assert item["fabula"] == {"path": "notes.md.fabulan.cosm"} and "emf" not in item
    assert not any(n["path"].startswith("notes.md.") for n in cat["nodes"])
    got = client.get("/api/canon/emf", params={"path": "notes.md"}).json()
    assert got["twin_path"] == "notes.md.fabulan.cosm" and got["flavour"] == "fabulan"
    assert got["twins"] == {"fabulan": {"path": "notes.md.fabulan.cosm", "state": "fresh"}}
    assert got["suggested"] == "fabulan" and got["cosm"]["minicosm"] == "fabula"


def test_a_poem_is_a_fabulap_by_the_suggestion_and_the_engine_derives_it_as_today(client: TestClient,
                                                                               project: Path):
    (project / "rose.txt").write_text(SICK_ROSE, encoding="utf-8")
    r = client.post("/api/canon/derive", json={"path": "rose.txt"})
    assert r.json()["flavour"] == r.json()["suggested"] == "fabulap"
    snap = wait_job(client, r.json()["job"]["id"])
    assert snap["result"]["twin_path"] == "rose.txt.fabulap.cosm"
    doc = head(project / "rose.txt.fabulap.cosm")
    assert doc["oes"] == "fabula/1" and doc["flavour"] == "fabulap" and doc["id"] == "fabula/rose-txt"
    assert lint_errors(project / "rose.txt.fabulap.cosm") == []
    # asked for, prose it is
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "rose.txt", "flavour": "fabulan"})["id"])
    assert snap["result"]["twin_path"] == "rose.txt.fabulan.cosm" and head(project / "rose.txt.fabulan.cosm")[
        "flavour"] == "fabulan"


@pytest.mark.parametrize("flavour,words", [("fabulac", "folder of code"), ("emf", "fabulan (prose) or fabulap"),
                                           ("FABULAX", "fabulan (prose) or fabulap")])
def test_a_flavour_a_text_cannot_take_is_refused(client: TestClient, project: Path, flavour: str, words: str):
    for url, body in (("/api/canon/derive", {"path": "notes.md", "flavour": flavour}),
                      ("/api/canon/atem", {"path": "notes.md", "flavour": flavour}),
                      ("/api/canon/atem/pin", {"path": "notes.md", "flavour": flavour, "span": {"lines": "1"},
                                               "atem": {"line": "x"}})):
        r = client.post(url, json=body)
        assert r.status_code == 400 and words in r.json()["detail"], (url, r.text)
    r = run(project, tool("emf_derive", path="notes.md", flavour=flavour))
    assert not r.ok and words in r.body
    assert not any(p.name.startswith("notes.md.") for p in project.iterdir())


def test_one_twin_per_flavour_and_the_payload_names_both(client: TestClient, project: Path):
    wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md"})["id"])
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md", "flavour": "fabulap"})["id"])
    assert snap["result"]["twin_path"] == "notes.md.fabulap.cosm"
    assert (project / "notes.md.fabulan.cosm").is_file() and (project / "notes.md.fabulap.cosm").is_file()
    got = client.get("/api/canon/emf", params={"path": "notes.md"}).json()
    assert got["flavour"] == "fabulap" and got["twin_path"] == "notes.md.fabulap.cosm", "the one derived last"
    assert set(got["twins"]) == {"fabulan", "fabulap"}
    assert client.get("/api/canon/emf", params={"path": "notes.md", "flavour": "fabulan"}).json()[
        "twin_path"] == "notes.md.fabulan.cosm"
    tree = {n["path"]: n for n in server.build_file_tree(project)}
    assert "notes.md.fabulan.cosm" not in tree and "notes.md.fabulap.cosm" not in tree
    entry = tree["notes.md"]["emf"]
    assert entry["path"] == "notes.md.fabulap.cosm" and entry["flavour"] == "fabulap"
    assert [o["path"] for o in entry["others"]] == ["notes.md.fabulan.cosm"]
    # a refresh with no flavour refreshes the twin the slot shows
    r = client.post("/api/canon/derive", json={"path": "notes.md", "force": True})
    assert r.json()["flavour"] == "fabulap"
    wait_job(client, r.json()["job"]["id"])


# ---------------------------------------------------------------------------
# B: an old-named twin
# ---------------------------------------------------------------------------

def test_an_old_twin_is_read_and_updated_in_place(client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    got = client.get("/api/canon/emf", params={"path": "notes.md"}).json()
    assert got["twin_path"] == "notes.md.cosm" and got["flavour"] == "fabulan"
    assert got["cosm"]["declared"]["how"] == "old"
    # a short is recorded in it, an atem written into it, a passage atem pinned to it: in place, still emf/1
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm"})["id"])
    assert snap["state"] == "done" and snap["result"]["recorded"] is True
    assert snap["result"]["written"].startswith("notes.short-")
    snap = wait_job(client, start(client, "/api/canon/atem", {"path": "notes.md"})["id"])
    assert snap["result"]["twin_path"] == "notes.md.cosm"
    r = client.post("/api/canon/atem/pin", json={"path": "notes.md", "atem": {"line": "A line."},
                                                 "span": {"lines": "3"}})
    assert r.status_code == 200 and r.json()["twin_path"] == "notes.md.cosm"
    doc = head(project / "notes.md.cosm")
    assert doc["oes"] == "emf/1" and doc["id"] == "emf/notes-md" and "flavour" not in doc
    assert len(doc["shorts"]) == 1 and any(n["id"] == r.json()["item_id"] for n in doc["nodes"])
    assert not (project / "notes.md.fabulan.cosm").exists(), "nothing but a decompile renames a twin"
    # listing, the catalog, reconciling: nothing writes the twin
    before = (project / "notes.md.cosm").read_bytes()
    server.build_file_tree(project)
    canon.project_catalog(project)
    assert (project / "notes.md.cosm").read_bytes() == before


def test_decompiling_an_old_twin_again_writes_the_new_one_carries_its_shorts_and_removes_it(
        client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.cosm"})["id"])
    r = client.post("/api/canon/atem/pin", json={"path": "notes.md", "atem": {"line": "A pinned line."},
                                                 "span": {"lines": "5"}})
    assert r.status_code == 200
    pinned = r.json()["item_id"]
    old = head(project / "notes.md.cosm")
    assert len(old["shorts"]) == 1
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "notes.md", "force": True})["id"])
    assert snap["state"] == "done", snap
    res = snap["result"]
    assert res["twin_path"] == "notes.md.fabulan.cosm" and res["replaced"] == "notes.md.cosm"
    assert not (project / "notes.md.cosm").exists()
    new = head(project / "notes.md.fabulan.cosm")
    assert new["oes"] == "fabula/1" and new["flavour"] == "fabulan" and new["id"] == "fabula/notes-md"
    assert macrocosm.jsonable(new["shorts"]) == macrocosm.jsonable(old["shorts"])
    assert [n["line"] for n in new["nodes"] if n["id"] == pinned] == ["A pinned line."]
    assert list(new).index("shorts") == list(new).index("nodes") - 1
    assert lint_errors(project / "notes.md.fabulan.cosm") == []
    # a fabulap decompile of a text whose fabulan is old-named leaves the old fabulan alone
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "other-notes.md.cosm")
    shutil.copyfile(project / "notes.md", project / "other-notes.md")
    snap = wait_job(client, start(client, "/api/canon/derive", {"path": "other-notes.md", "flavour": "fabulap"})["id"])
    assert snap["result"]["replaced"] is None and (project / "other-notes.md.cosm").is_file()


def test_the_old_twin_stays_when_the_new_one_does_not_load_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shutil.copyfile(FIX / "emf" / "notes.md", tmp_path / "notes.md")
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", tmp_path / "notes.md.cosm")
    text, stat = CD.read_source(tmp_path / "notes.md")
    cosm, _ = CD.derive_emf(text, source_name="notes.md", source_stat=stat, lookup=lambda ws: {},
                            previous=OLD)

    class Bad:
        errors = ["a check failed"]

    monkeypatch.setattr(CD.macrocosm, "lint", lambda vol: Bad())
    out = CD.replace_twin(tmp_path / "notes.md", "fabulan", cosm)
    assert out == {"path": tmp_path / "notes.md.fabulan.cosm", "removed": None}
    assert (tmp_path / "notes.md.cosm").is_file() and N.superseded_by(tmp_path / "notes.md.cosm")
    assert N.find_twin(tmp_path / "notes.md") == tmp_path / "notes.md.fabulan.cosm"


def test_both_names_at_once(client: TestClient, project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    (project / "notes.md.fabulan.cosm").write_text(new_twin("fabulan"), encoding="utf-8")
    tree = {n["path"]: n for n in server.build_file_tree(project)}
    assert "notes.md.fabulan.cosm" not in tree and tree["notes.md"]["emf"]["path"] == "notes.md.fabulan.cosm"
    assert tree["notes.md.cosm"]["cosm"] is True
    assert tree["notes.md.cosm"]["old_twin"] == {"of": "notes.md", "twin": "notes.md.fabulan.cosm"}
    canon.project_catalog(project)
    items = {n["path"]: n for n in head(project / canon.PROJECT_CATALOG)["nodes"]}
    assert items["notes.md"]["fabula"] == {"path": "notes.md.fabulan.cosm"}
    assert items["notes.md.cosm"]["kind"] == "cosm" and "old-named twin" in items["notes.md.cosm"]["note"]
    assert client.get("/api/canon/emf", params={"path": "notes.md"}).json()["twin_path"] == "notes.md.fabulan.cosm"
    assert client.get("/api/canon/emf", params={"path": "notes.md.cosm"}).status_code == 404
    skip = home._mirror_skip(project)
    assert skip(project / "notes.md.fabulan.cosm") and not skip(project / "notes.md.cosm")


# ---------------------------------------------------------------------------
# C: every discovery site, under each name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,body", [("notes.md.fabulan.cosm", lambda: new_twin("fabulan")),
                                       ("notes.md.fabulap.cosm", lambda: new_twin("fabulap")),
                                       ("notes.md.cosm", lambda: OLD)])
def test_every_discovery_site_finds_the_twin_under_each_name(client: TestClient, project: Path, name: str, body):
    (project / name).write_text(body(), encoding="utf-8")
    flavour = N.flavour_of_twin(name)
    # the sidebar tree and the project catalog hide it behind its text
    tree = {n["path"]: n for n in server.build_file_tree(project)}
    assert name not in tree and tree["notes.md"]["emf"]["path"] == name
    assert tree["notes.md"]["emf"]["flavour"] == flavour
    html = server._tree_to_html(server.build_file_tree(project))
    assert f'data-emf="{name}"' in html
    canon.project_catalog(project)
    items = {n["path"]: n for n in head(project / canon.PROJECT_CATALOG)["nodes"]}
    assert name not in items and items["notes.md"]["fabula"] == {"path": name}
    assert head(project / canon.PROJECT_CATALOG)["counts"]["twins"] == 1
    # the project mirror skips it
    assert home._mirror_skip(project)(project / name)
    # a Canon volume's listing and catalog
    vol = canon.volume_dir("lib")
    (vol / "notes.md").write_text((project / "notes.md").read_text(encoding="utf-8"), encoding="utf-8")
    (vol / name).write_text(body(), encoding="utf-8")
    flat = {n["path"]: n for n in canon.volume_tree("lib")["tree"]}
    assert name not in flat and flat["notes.md"]["emf"]["path"] == name
    assert canon._volume_skip(vol)(vol / name)
    canon.regenerate_catalog("lib")
    cat = head(vol / canon.CATALOG_NAME)
    vitems = {n["path"]: n for n in cat["nodes"]}
    assert name not in vitems and vitems["notes.md"]["fabula"]["path"] == name
    # the reader's route, the tools' read, Thym's twin check
    got = client.get("/api/canon/emf", params={"path": "notes.md"}).json()
    assert got["twin_path"] == name and got["flavour"] == flavour
    assert client.get("/api/canon/emf", params={"path": name}).json()["twin_path"] == name
    vol_, note = CT.load(project, "notes.md")
    assert Path(vol_.path).name == name and name in note
    t = CT.text_target(project, "notes.md")
    assert t["twin"] == project / name and t["twin_rel"] == name and t["flavour"] == flavour
    # a compile of it is claimed by its text, and its short takes the text's stem
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": name})["id"])
    assert snap["state"] == "done" and snap["result"]["written"].startswith("notes.short-")
    assert snap["result"]["recorded"] is True and len(head(project / name)["shorts"]) == 1


def test_a_standalone_fabula_under_a_new_name_is_an_ordinary_cosm_file_and_compiles(client: TestClient,
                                                                                   project: Path):
    (project / "rain.fabulan.cosm").write_text(
        (FIX / "emf" / "standalone.cosm").read_text(encoding="utf-8").replace("oes: emf/1", "oes: fabula/1", 1),
        encoding="utf-8")
    tree = {n["path"]: n for n in server.build_file_tree(project)}
    assert tree["rain.fabulan.cosm"]["cosm"] is True and "emf" not in tree["rain.fabulan.cosm"]
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "rain.fabulan.cosm"})["id"])
    assert snap["state"] == "done" and snap["result"]["order"] == "weight"
    assert snap["result"]["written"].startswith("rain.short-")
    canon.project_catalog(project)
    items = {n["path"]: n for n in head(project / canon.PROJECT_CATALOG)["nodes"]}
    assert items[snap["result"]["written"]]["short_of"] == "rain.fabulan.cosm"


# ---------------------------------------------------------------------------
# E: Canon's field
# ---------------------------------------------------------------------------

def test_a_catalog_written_before_reads_its_emf_field_as_fabula():
    vol = macrocosm.load_volume(FIX / "canon" / "project" / "canon.cosm")
    assert vol.refused is None and macrocosm.lint(vol).errors == []
    item = next(it.data for it in vol.items.values() if it.data.get("path") == "drafts/orchard.md")
    assert "fabula" not in item and canon.item_fabula(item) == item["emf"]
    assert canon.item_fabula({"fabula": {"path": "a"}, "emf": {"path": "b"}}) == {"path": "a"}
    assert canon.item_fabula({"path": "x"}) is None


# ---------------------------------------------------------------------------
# F: the model route
# ---------------------------------------------------------------------------

def test_a_job_with_no_route_runs_local_holds_the_lock_and_records_it(client: TestClient, project: Path, model: list,
                                                                     lock_seen: list):
    job = start(client, "/api/canon/derive", {"path": "notes.md"})
    assert job["mode"] == "model" and job["route"] == "local" and lock_seen[-1] is not None
    snap = wait_job(client, job["id"])
    assert snap["result"]["route"] == "local"
    d = head(project / "notes.md.fabulan.cosm")["derived"]
    assert (d["model"], d["route"], "provider" in d) == ("fake-model", "local", False)
    assert list(d)[:4] == ["at", "by", "model", "route"]
    # a short told by a model records its route
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.fabulan.cosm"})["id"])
    entry = head(project / "notes.md.fabulan.cosm")["shorts"][0]
    assert entry["route"] == "local" and entry["mode"] == "model" and snap["result"]["route"] == "local"
    # route: local, said, is the same
    job = start(client, "/api/canon/derive", {"path": "hello.md", "route": "local"})
    assert job["route"] == "local" and lock_seen[-1] is not None
    wait_job(client, job["id"])


def test_a_cloud_job_with_the_gate_open_holds_no_lock_and_records_the_provider(client: TestClient, project: Path,
                                                                              lock_seen: list,
                                                                              monkeypatch: pytest.MonkeyPatch):
    calls = cloud_open(monkeypatch)
    job = start(client, "/api/canon/derive", {"path": "notes.md", "route": "cloud"})
    assert job["mode"] == "model" and job["route"] == "cloud" and lock_seen[-1] is None
    snap = wait_job(client, job["id"])
    assert snap["state"] == "done", snap
    assert snap["result"]["route"] == "cloud" and snap["result"]["provider"] == "openrouter"
    d = head(project / "notes.md.fabulan.cosm")["derived"]
    assert (d["model"], d["route"], d["provider"]) == ("anthropic/claude-x-20261101", "cloud", "openrouter")
    assert list(d)[:5] == ["at", "by", "model", "route", "provider"] and calls
    # the atem and the compile on the cloud too
    snap = wait_job(client, start(client, "/api/canon/atem", {"text": "A passage.", "route": "cloud"})["id"])
    assert snap["result"]["route"] == "cloud" and lock_seen[-1] is None
    snap = wait_job(client, start(client, "/api/canon/compile", {"path": "notes.md.fabulan.cosm",
                                                                 "route": "cloud"})["id"])
    assert head(project / "notes.md.fabulan.cosm")["shorts"][0]["route"] == "cloud"


def test_a_cloud_job_with_the_gate_shut_is_refused_in_the_gates_words(client: TestClient, project: Path,
                                                                     monkeypatch: pytest.MonkeyPatch):
    denial = cloud_shut(monkeypatch)
    for url, body in (("/api/canon/derive", {"path": "notes.md", "route": "cloud"}),
                      ("/api/canon/atem", {"text": "A passage.", "route": "cloud"}),
                      ("/api/canon/compile", {"path": "rain.cosm", "route": "cloud"})):
        r = client.post(url, json=body)
        assert r.status_code == 403 and r.json()["detail"] == denial, (url, r.text)
    assert not (project / "notes.md.fabulan.cosm").exists()
    r = client.post("/api/canon/derive", json={"path": "notes.md", "route": "moon"})
    assert r.status_code == 400 and "local or cloud" in r.json()["detail"]
    r = run(project, tool("emf_derive", path="notes.md", route="cloud"))
    assert not r.ok and denial in r.body


def test_the_tools_take_flavour_and_route(project: Path, monkeypatch: pytest.MonkeyPatch):
    r = run(project, tool("emf_derive", path="notes.md", flavour="fabulap"))
    assert r.ok and "notes.md.fabulap.cosm" in r.body, r.body
    assert head(project / "notes.md.fabulap.cosm")["flavour"] == "fabulap"
    r = run(project, tool("atem", path="notes.md"))
    assert r.ok and head(project / "notes.md.fabulap.cosm")["atem"]


def test_the_tools_description_block_stays_inside_its_cap():
    assert len(prompt.CANON_TOOL_INSTRUCTIONS) <= 1_000
    assert "<path>notes.md</path>" in prompt.CANON_TOOL_INSTRUCTIONS


def test_short_entries_and_derived_say_no_route_by_rules():
    t = CD.record_short("oes: fabula/1\nid: fabula/x\nname: x\nnodes: []\n", path="x.short-2026-11-05-1000.md",
                        at=dt.datetime(2026, 11, 5, 10, tzinfo=dt.timezone.utc), by="rules", mode="rules",
                        order="weight", route="local")
    assert "route" not in macrocosm.yaml_load(t)["shorts"][0]
    t = CD.record_short("oes: emf/1\nid: emf/x\nname: x\nnodes: []\n", path="x.short-2026-11-05-1000.md",
                        at=dt.datetime(2026, 11, 5, 10, tzinfo=dt.timezone.utc), by="g40-04", mode="model",
                        order="weight", route="local")
    doc = macrocosm.yaml_load(t)
    assert doc["oes"] == "emf/1" and doc["shorts"][0]["route"] == "local"
