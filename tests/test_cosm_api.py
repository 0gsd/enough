"""The read routes for `.cosm` volumes (0.4.3): `GET /api/cosm`,
`GET /api/cosm/lens`, `POST /api/cosm/lint`, `GET /api/macrocosm/manifests`
and `GET /api/macrocosm-spec`, over P1's fixtures — a Comprise Holotype in a
Canon volume, an EMF twin and a standalone EMF in the project, a Canon
volume's catalog, the project catalog, a crafted bad volume and a refused
declaration.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import canon, macrocosm, skeleton
from enough.server import create_app

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "store"))
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", proj / "notes.md.cosm")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", proj / "rain.cosm")
    shutil.copyfile(FIX / "bad" / "ref-unresolved.cosm", proj / "bad.cosm")
    (proj / "future.cosm").write_text("oes: canon/9\nnodes: []\n", encoding="utf-8")
    (proj / "plain.md").write_text("not a cosm", encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    vol = canon.root() / "lib"
    canon.create_volume("lib")
    shutil.copytree(FIX / "holotypes" / "meadow", vol / "meadow")
    (vol / "guide.md").write_text("a guide", encoding="utf-8")
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(canon.root()).startswith(str(tmp_path))
    app = create_app(proj, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        c._project = proj  # type: ignore[attr-defined]
        yield c


def test_cosm_holotype_in_a_volume(client: TestClient):
    r = client.get("/api/cosm", params={"path": "canon:lib/meadow"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["minicosm"], p["major"], p["refused"]) == ("comprise", 1, None)
    assert p["problems"] == [] and p["pending"] == []
    letters = [m["letter"] for m in p["modules"]]
    manifest = macrocosm.default_registry().get("comprise")
    assert letters[: len(manifest.modules())] == manifest.modules()      # manifest order
    assert sum(m["count"] for m in p["modules"]) == 36
    assert "map" in p["lenses"]
    item = p["modules"][letters.index("P")]["kinds"][0]["items"][0]
    assert set(item) >= {"id", "key", "path", "name", "summary", "status", "visibility", "data"}
    assert item["key"].startswith("atom/")                          # Holotype keys are qualified
    assert "nodes" not in p["catalog"]
    # The same through the legacy prefix.
    assert client.get("/api/cosm", params={"path": "cacheawl:lib/meadow"}).json()["minicosm"] == "comprise"


def test_cosm_volume_folder_loads_its_canon_catalog(client: TestClient):
    p = client.get("/api/cosm", params={"path": "canon:lib"}).json()
    assert p["minicosm"] == "canon" and p["title"] == "lib" and p["problems"] == []
    kinds = {k["kind"]: k["items"] for m in p["modules"] for k in m["kinds"]}
    files = {it["data"]["path"] for it in kinds["file"]}
    assert files == {"guide.md"}
    assert kinds["folder"][0]["data"]["holotype"] is True
    assert p["uri"] == "oes:canon/lib"
    same = client.get("/api/cosm", params={"path": "canon:lib/canon.cosm"}).json()
    assert same["modules"] == p["modules"]


def test_cosm_emf_twin_and_standalone(client: TestClient):
    p = client.get("/api/cosm", params={"path": "notes.md.cosm"}).json()
    assert p["minicosm"] == "emf" and p["refused"] is None
    assert [m["letter"] for m in p["modules"]][:6] == ["L", "E", "K", "P", "T", "X"]
    assert set(p["lenses"]) >= {"claims", "map"}
    assert client.get("/api/cosm", params={"path": "rain.cosm"}).json()["minicosm"] == "emf"


def test_cosm_project_catalog_is_reconciled_on_read(client: TestClient):
    cat = client._project / canon.PROJECT_CATALOG  # type: ignore[attr-defined]
    if cat.exists():
        cat.unlink()
    p = client.get("/api/cosm", params={"path": "rness/canon.cosm"}).json()
    assert cat.is_file()
    assert p["minicosm"] == "canon" and p["catalog"]["scope"] == "project"
    names = {it["data"]["path"] for m in p["modules"] for k in m["kinds"] for it in k["items"]}
    assert "notes.md" in names and "notes.md.cosm" not in names


def test_cosm_refusals_and_bad_input(client: TestClient):
    p = client.get("/api/cosm", params={"path": "future.cosm"}).json()
    assert p["refused"] and "canon/9" in p["refused"] and p["modules"] == [] and p["lenses"] == []
    assert client.get("/api/cosm", params={"path": "plain.md"}).status_code == 400
    assert client.get("/api/cosm", params={"path": "nope.cosm"}).status_code == 404
    assert client.get("/api/cosm", params={"path": "../x.cosm"}).status_code == 400
    assert client.get("/api/cosm", params={"path": "canon:../x"}).status_code == 400
    assert client.get("/api/cosm", params={"path": ""}).status_code == 400


def test_cosm_lens(client: TestClient):
    r = client.get("/api/cosm/lens", params={"path": "canon:lib", "lens": "tree"})
    assert r.status_code == 200, r.text
    p = r.json()
    head = p["text"].split("---\n")[1]
    for line in ("merirmaid: 1", "title: lib · tree", "modality: mirror", "kind: cosm-lens",
                 "source: canon:lib#tree", "node-char-limit: 48"):
        assert line in head.splitlines(), line
    assert "flowchart" in p["text"] and "click " not in p["text"]
    paths = {v.get("fs_path") for v in p["node_map"].values()}
    assert "guide.md" in paths
    assert p["lens"] == "tree" and "map" in p["lenses"]
    r = client.get("/api/cosm/lens", params={"path": "canon:lib", "lens": "nope"})
    assert r.status_code == 400 and "tree" in r.json()["detail"]
    r = client.get("/api/cosm/lens", params={"path": "future.cosm", "lens": "map"})
    assert r.status_code == 400
    r = client.get("/api/cosm/lens", params={"path": "notes.md.cosm", "lens": "claims"})
    assert r.status_code == 200 and "source: notes.md.cosm#claims" in r.json()["text"]


def test_cosm_lint(client: TestClient):
    r = client.post("/api/cosm/lint", json={"path": "canon:lib/canon.cosm"})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["ok"] is True and rep["minicosm"] == "canon/1" and rep["errors"] == []
    rep = client.post("/api/cosm/lint", json={"path": "bad.cosm"}).json()
    assert rep["ok"] is False and any(e["check"] == "ref-unresolved" for e in rep["errors"])
    rep = client.post("/api/cosm/lint", json={"path": "future.cosm"}).json()
    assert rep["ok"] is False and rep["refused"]
    rep = client.post("/api/cosm/lint", json={"path": "canon:lib/meadow"}).json()
    assert rep["ok"] is True and any(c.startswith("rule ") for c in rep["not_run"])
    assert client.post("/api/cosm/lint", json={}).status_code == 400


def test_macrocosm_manifests(client: TestClient):
    r = client.get("/api/macrocosm/manifests")
    assert r.status_code == 200
    rows = r.json()
    assert [m["name"] for m in rows][:4] == ["comprise", "cosm", "canon", "emf"]
    by = {m["name"]: m for m in rows}
    assert by["canon"]["declaration"] == "canon/1" and by["emf"]["declaration"] == "emf/1"
    for m in rows:
        assert set(m) == {"name", "title", "version", "declaration", "summary"}
        assert m["title"] and m["summary"]


def test_macrocosm_spec(client: TestClient):
    english = (REPO / "docs" / "MACROCOSM_OES.md").read_text(encoding="utf-8")
    for lang in ("en", "fr", "xx", "../../etc"):
        r = client.get("/api/macrocosm-spec", params={"lang": lang})
        assert r.status_code == 200, lang
        assert r.headers["content-type"].startswith("text/markdown")
        assert r.text == english, lang


def test_cosm_payload_carries_the_checks_panel_and_files(client: TestClient):
    """The viewer's checks panel needs findings split by severity and the
    check ids left to the MiniCOSM's own tools; its raw-file list needs the
    files the volume was read from; each item names its part."""
    p = client.get("/api/cosm", params={"path": "canon:lib/meadow"}).json()
    rep = p["report"]
    assert set(rep) == {"ok", "errors", "warnings", "notes", "not_run"}
    assert rep["ok"] is True and rep["errors"] == []
    assert rep["not_run"], "Comprise's own rules should be listed as not run"
    assert "holotype.cosm" in p["files"]
    items = [it for m in p["modules"] for k in m["kinds"] for it in k["items"]]
    assert items and all(it["part"] == "atom/meadow" for it in items)
