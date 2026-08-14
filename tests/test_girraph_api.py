"""Tests for the /api/girraph* endpoints — the same node ops the agent
tools use, reached the way the editable panel reaches them."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import girraph as gr
from enough.server import create_app


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(tmp_path, "http://127.0.0.1:1/v1", supervise=False)
    # TestClient triggers lifespan; supervise=False keeps it offline.
    with TestClient(app) as c:
        yield c


REL = "plans/api-test.girraph"


def seed(client: TestClient) -> None:
    r = client.post("/api/girraph/node",
                    data={"path": REL, "type": "issue", "label": "Root?"})
    assert r.status_code == 200, r.text
    assert r.json()["node"]["id"] == "q1"
    r = client.post("/api/girraph/node",
                    data={"path": REL, "type": "position", "label": "Yes",
                          "parent": "q1", "by": "user"})
    assert r.json()["node"]["id"] == "p1"


def test_create_read_tree(client: TestClient, tmp_path: Path):
    seed(client)
    r = client.get("/api/girraph", params={"path": REL})
    data = r.json()
    assert data["title"] == "Root?"
    assert data["roots"] == ["q1"]
    ids = [n["id"] for n in data["nodes"]]
    assert ids == ["q1", "p1"]
    assert data["nodes"][1]["by"] == "user"
    # On-disk file is canonical plain text.
    assert (tmp_path / REL).read_text().startswith("%girraph 0.1\n")


def test_patch_and_clear(client: TestClient, tmp_path: Path):
    seed(client)
    r = client.patch("/api/girraph/node",
                     data={"path": REL, "id": "p1", "label": "Yes — minimal",
                           "by": ""})
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["label"] == "Yes — minimal"
    assert node["by"] is None
    g = gr.load(tmp_path / REL)
    assert g.nodes["p1"].label == "Yes — minimal"


def test_delete_orphan_guard_and_cascade(client: TestClient):
    seed(client)
    r = client.delete("/api/girraph", params={"path": REL})  # wrong route
    assert r.status_code in (404, 405)
    r = client.delete("/api/girraph/node", params={"path": REL, "id": "q1"})
    assert r.status_code == 400 and "children" in r.json()["detail"]
    r = client.delete("/api/girraph/node",
                      params={"path": REL, "id": "q1", "cascade": "true"})
    assert r.status_code == 200
    assert set(r.json()["removed"]) == {"q1", "p1"}


def test_link_and_ref_candidates(client: TestClient, tmp_path: Path):
    seed(client)
    r = client.post("/api/girraph/link",
                    data={"path": REL, "from": "p1", "to": "q1"})
    assert r.status_code == 200
    assert "[-> q1]" in (tmp_path / REL).read_text()
    # Broken-ref repair helper finds same-basename files.
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "survey.md").write_text("x")
    r = client.get("/api/girraph/ref-candidates", params={"name": "old/survey.md"})
    assert r.json()["candidates"] == ["notes/survey.md"]


def test_raw_write_blocked(client: TestClient):
    seed(client)
    r = client.post("/api/file", data={"path": REL, "content": "clobber"})
    assert r.status_code == 403
    r = client.get("/api/girraph", params={"path": "plans/nope.girraph"})
    assert r.status_code == 404
    r = client.get("/api/girraph", params={"path": "notes.md"})
    assert r.status_code == 400
