"""TestClient smoke pass over the /api/cacheawl/* endpoints and the
POST /api/file cachebox-mirror refusal, against a scratch cacheawl root.

Uses supervise=False so no llama-server is spawned, and points both the
cacheawl and infoworld roots at scratch dirs so the real ~/enough install
is untouched.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import cacheawl as ca
from enough.server import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "hello.txt").write_text("hi from the project", encoding="utf-8")
    # cacheawl store lives INSIDE the project here only so the POST /api/file
    # mirror-refusal test can reach a mirror through an in-tree relative path.
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(project / "_store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        c._project = project  # type: ignore[attr-defined]
        yield c


def test_create_list_and_tree(client: TestClient):
    r = client.post("/api/cacheawl/create", json={"name": "notes"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "notes"

    r = client.get("/api/cacheawl/tree")
    assert r.status_code == 200
    payload = r.json()
    assert "project" in payload and "cacheboxes" in payload
    names = [b["name"] for b in payload["cacheboxes"]]
    assert "notes" in names

    # Duplicate create → 400.
    r = client.post("/api/cacheawl/create", json={"name": "notes"})
    assert r.status_code == 400


def test_transfer_project_to_box(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "box"})
    r = client.post("/api/cacheawl/transfer", json={
        "op": "copy",
        "src": {"root": "project", "path": "hello.txt"},
        "dst": {"root": "cachebox", "box": "box", "path": "hello.txt"},
    })
    assert r.status_code == 200, r.text
    assert (ca.box_dir("box") / "hello.txt").read_text(encoding="utf-8") == "hi from the project"


def test_delete_requires_confirm(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "trash"})
    r = client.post("/api/cacheawl/delete", json={"name": "trash", "confirm": False})
    assert r.status_code == 400
    assert ca.box_dir("trash").exists()
    r = client.post("/api/cacheawl/delete", json={"name": "trash", "confirm": True})
    assert r.status_code == 200
    assert not ca.box_dir("trash").exists()


def test_ingest_path_via_endpoint(client: TestClient, tmp_path: Path):
    src = tmp_path / "srctree"
    src.mkdir()
    (src / "one.md").write_text("one", encoding="utf-8")
    (src / "two.txt").write_text("two", encoding="utf-8")
    r = client.post("/api/cacheawl/ingest", json={
        "box": "replica", "type": "path", "value": str(src), "all": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ingesting"
    # Poll ingest-status until complete (background thread). Generous
    # ceiling: on a loaded machine the thread can take well over the
    # ~2.5s a tight loop allows, which made this test flake under
    # concurrent dev servers.
    deadline = time.monotonic() + 30
    while True:
        s = client.get("/api/cacheawl/ingest-status", params={"box": "replica"}).json()
        if s["status"] == "complete" or time.monotonic() > deadline:
            break
        time.sleep(0.05)
    assert s["status"] == "complete"
    rels = {p.name for p in ca._content_files(ca.box_dir("replica"))}
    assert rels == {"one.md", "two.txt"}


def test_ingest_bad_input_fast_400(client: TestClient):
    r = client.post("/api/cacheawl/ingest", json={
        "box": "x", "type": "bogus", "value": "y",
    })
    assert r.status_code == 400


def test_post_file_refuses_cachebox_mirror(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "mbox"})
    # The store is under the project (project/_store), so the mirror is
    # reachable by an in-tree relative path.
    rel = f"_store/mbox/{ca.MIRROR_NAME}"
    r = client.post("/api/file", data={"path": rel, "content": "CLOBBER"})
    assert r.status_code == 403
    assert "modality: mirror" in r.text
    mirror = ca.box_dir("mbox") / ca.MIRROR_NAME
    assert "CLOBBER" not in mirror.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The `cacheawl:<box>/<rel>` virtual-path scheme through
# _resolve_project_path — how cacheawl mode launches store files into the
# read/edit, girraph, and merirmaid modes.
# ---------------------------------------------------------------------------

def test_cacheawl_scheme_reads_store_file(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "reads"})
    (ca.box_dir("reads") / "note.md").write_text("stored body", encoding="utf-8")
    r = client.get("/api/file/raw", params={"path": "cacheawl:reads/note.md"})
    assert r.status_code == 200, r.text
    assert r.text == "stored body"


def test_cacheawl_scheme_writes_store_file(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "writes"})
    r = client.post("/api/file", data={
        "path": "cacheawl:writes/fresh.md", "content": "written via scheme"})
    assert r.status_code == 200, r.text
    assert (ca.box_dir("writes") / "fresh.md").read_text(encoding="utf-8") \
        == "written via scheme"


def test_cacheawl_scheme_refuses_mirror_write(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "mir"})
    r = client.post("/api/file", data={
        "path": f"cacheawl:mir/{ca.MIRROR_NAME}", "content": "CLOBBER"})
    assert r.status_code == 403
    assert "modality: mirror" in r.text
    assert "CLOBBER" not in (ca.box_dir("mir") / ca.MIRROR_NAME).read_text(
        encoding="utf-8")


def test_cacheawl_scheme_refuses_meta_write(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "met"})
    before = (ca.box_dir("met") / ca.META_NAME).read_text(encoding="utf-8")
    r = client.post("/api/file", data={
        "path": f"cacheawl:met/{ca.META_NAME}", "content": "{}"})
    assert r.status_code == 403
    assert (ca.box_dir("met") / ca.META_NAME).read_text(encoding="utf-8") == before


def test_cacheawl_scheme_rejects_traversal(client: TestClient):
    for bad in ("cacheawl:../../etc/passwd", "cacheawl:box/../../escape", "cacheawl:"):
        r = client.get("/api/file/raw", params={"path": bad})
        assert r.status_code == 400, f"{bad!r} -> {r.status_code}"


def test_mirror_endpoint_root_and_subfolder(client: TestClient):
    client.post("/api/cacheawl/create", json={"name": "docs"})
    box = ca.box_dir("docs")
    (box / "readme.md").write_text("hi", encoding="utf-8")
    (box / "guide").mkdir()
    (box / "guide" / "intro.md").write_text("intro", encoding="utf-8")

    # Root mirror (path omitted).
    r = client.get("/api/cacheawl/mirror", params={"box": "docs"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["modality"] == "mirror" and p["subpath"] == ""
    assert "flowchart TD" in p["text"]
    assert p["box_path"].endswith("/docs")
    nm = p["node_map"]
    assert nm[ca._node_id("guide")]["is_dir"] is True
    assert nm[ca._node_id("readme.md")]["path"] == "readme.md"

    # Subfolder mirror — on-demand, scoped, and NOT written to disk.
    r = client.get("/api/cacheawl/mirror", params={"box": "docs", "path": "guide"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["subpath"] == "guide"
    assert "source: cachebox:docs/guide" in p["text"]
    assert ca._node_id("guide/intro.md") in p["node_map"]
    assert not (box / "guide" / ca.MIRROR_NAME).exists()

    # Missing box → 404; missing folder → 404; traversal → 400.
    assert client.get("/api/cacheawl/mirror", params={"box": "ghost"}).status_code == 404
    assert client.get("/api/cacheawl/mirror",
                      params={"box": "docs", "path": "nope"}).status_code == 404
    assert client.get("/api/cacheawl/mirror",
                      params={"box": "docs", "path": "../x"}).status_code == 400
