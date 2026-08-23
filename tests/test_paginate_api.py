"""TestClient pass over /api/paginate{,/status}, the tree's hiding rule for
the viewer folder, and the `.pdf` gate that lets one of our own PDFs back in
without the document reader.

supervise=False so no llama-server is spawned; every `ENOUGH_*` seam the app
touches points into tmp_path, so the developer's real ~/enough is never read
or written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import convert, paginate
from enough.server import create_app

BOOK_MD = """# One

A first chapter with a note.[^1]

# Two

A second chapter with another.[^2]

[^1]: the first note.
[^2]: the second note.
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "project"
    project.mkdir()
    scratch = tmp_path / "state"
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(scratch / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(scratch / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(scratch / "wikisink.json"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(scratch / "ui.json"))
    monkeypatch.setenv("ENOUGH_EXTRAS_STATE", str(scratch / "extras.json"))
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(scratch / "weights"))
    convert.reset_engines()
    (project / "book.md").write_text(BOOK_MD, encoding="utf-8")
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        c._project = project  # type: ignore[attr-defined]
        yield c
    convert.reset_engines()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_carries_the_table_the_modal_draws(client: TestClient):
    body = client.get("/api/paginate/status", params={"path": "book.md"}).json()
    assert body["fonts"] == list(paginate.FONTS)
    assert set(body["sizes"]) == set(paginate.SIZES)
    assert body["sizes"]["a4"]["w_mm"] == 210.0
    assert body["pandoc"] is True and body["typst"] is True
    assert body["name"] == "book"
    assert body["defaults"]["footnotes"] == "page"
    assert isinstance(body["fonts_bundled"], bool)


def test_status_refuses_traversal_cacheawl_and_non_markdown(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "notes.txt").write_text("x", encoding="utf-8")
    assert client.get("/api/paginate/status",
                      params={"path": "../escape.md"}).status_code == 400
    assert client.get("/api/paginate/status",
                      params={"path": "cacheawl:box/a.md"}).status_code == 400
    assert client.get("/api/paginate/status",
                      params={"path": "notes.txt"}).status_code == 400
    assert client.get("/api/paginate/status",
                      params={"path": "missing.md"}).status_code == 404


# ---------------------------------------------------------------------------
# POST /api/paginate
# ---------------------------------------------------------------------------

def test_paginate_happy_path(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    r = client.post("/api/paginate", json={"path": "book.md", "name": "book",
                                           "size": "a5", "margin_mm": 15})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["viewer"] is None
    assert body["pdf"].startswith("book-") and body["pdf"].endswith(".pdf")
    assert body["pages"] == 2 and body["sheets"] == 2
    pdf = project / body["pdf"]
    assert pdf.read_bytes().startswith(b"%PDF")
    assert paginate.embedded_source(pdf)[0] == BOOK_MD


def test_paginate_in_a_subfolder_answers_a_relative_path(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    sub = project / "letters"
    sub.mkdir()
    (sub / "essay.md").write_text("# Essay\n\nBody.\n", encoding="utf-8")
    body = client.post("/api/paginate",
                       json={"path": "letters/essay.md", "size": "a5"}).json()
    assert body["pdf"].startswith("letters/essay-")
    assert (project / body["pdf"]).is_file()


def test_paginate_brings_the_viewer_in(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    body = client.post("/api/paginate", json={"path": "book.md", "name": "book",
                                              "size": "a5", "bring_in": True}).json()
    assert body["viewer"] == f".{Path(body['pdf']).name}.paginate.json"
    # The manifest and the pages are reachable through the blob route — the
    # only way the viewer gets at them.
    r = client.get("/api/file/blob", params={"path": body["viewer"]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["pages"] == body["pages"]
    page = f"{body['pdf']}.pages/{paginate.page_svg_name(1)}"
    r = client.get("/api/file/blob", params={"path": page})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert (project / page).is_file()


def test_paginate_rejects_bad_options(client: TestClient):
    assert client.post("/api/paginate", json={}).status_code == 400
    assert client.post("/api/paginate",
                       json={"path": "book.md", "size": "tabloid"}).status_code == 400
    assert client.post("/api/paginate",
                       json={"path": "book.md", "name": "../x"}).status_code == 400
    assert client.post("/api/paginate",
                       json={"path": "../escape.md"}).status_code == 400
    assert client.post("/api/paginate",
                       json={"path": "cacheawl:box/a.md"}).status_code == 400
    assert client.post("/api/paginate",
                       json={"path": "missing.md"}).status_code == 404


def test_paginate_emits_the_convert_event(client: TestClient,
                                          monkeypatch: pytest.MonkeyPatch):
    from enough import server as _server

    seen: list[tuple[str, dict]] = []
    original = _server.Session.emit

    async def spy(self, event, data):
        seen.append((event, data))
        await original(self, event, data)

    monkeypatch.setattr(_server.Session, "emit", spy)
    client.post("/api/paginate", json={"path": "book.md", "size": "a5"})
    events = [d for e, d in seen if e == convert.EVENT and d.get("op") == "paginate"]
    assert events, seen
    final = events[-1]
    assert final["state"] == "done" and final["path"] == "book.md"
    assert set(final) >= {"job", "path", "state", "progress", "message", "result"}
    assert final["result"]["ok"] is True


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------

def test_tree_shows_the_pdf_and_hides_its_viewer_folder(client: TestClient):
    body = client.post("/api/paginate", json={"path": "book.md", "name": "book",
                                              "size": "a5", "bring_in": True}).json()
    name = Path(body["pdf"]).name
    html = client.get("/api/files").text
    # The PDF is the artifact: it shows.
    assert f'data-path="{name}"' in html
    assert 'data-path="book.md"' in html
    # Its pages folder and its manifest are backend-owned and do not — no
    # row of their own (`data-paginated` below is an attribute of the PDF's).
    assert f'data-path="{name}.pages"' not in html
    assert f'data-path="{body["viewer"]}"' not in html
    assert paginate.page_svg_name(1) not in html
    # And the row carries what the viewer needs to open instead of the blob.
    assert f'data-paginated="{body["viewer"]}"' in html
    assert 'data-pages="2"' in html


def test_tree_shows_a_pages_folder_that_is_not_ours(client: TestClient):
    # `notes.pdf.pages/` with no manifest is somebody's folder, not a viewer.
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "notes.pdf.pages").mkdir()
    html = client.get("/api/files").text
    assert 'data-path="notes.pdf.pages"' in html


# ---------------------------------------------------------------------------
# The `.pdf` gate (plan §2.6)
# ---------------------------------------------------------------------------

def test_our_pdf_is_convertible_without_docling(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    body = client.post("/api/paginate", json={"path": "book.md", "name": "book",
                                              "size": "a5"}).json()
    name = body["pdf"]
    assert convert.docling_available() is False

    status = client.get("/api/convert/status", params={"path": name}).json()
    assert status["state"] == "unconverted"
    assert status["spec"]["reader"] == "unpack"
    assert status["spec"]["available"] is True

    r = client.post("/api/convert", json={"path": name})
    assert r.status_code == 200, r.text
    from tests.test_convert_api import wait_for_job
    snap = wait_for_job(client, r.json()["job"])
    assert snap["state"] == "done", snap
    assert snap["result"]["engine"]["name"] == "unpack"
    assert (project / f"{name}.md").read_text(encoding="utf-8") == BOOK_MD
    # One row for the pair, exactly like any other converted document.
    html = client.get("/api/files").text
    assert f'data-path="{name}.md"' not in html
    assert 'data-convert-state="fresh"' in html


def test_a_foreign_pdf_gate_is_unchanged(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "paper.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    status = client.get("/api/convert/status", params={"path": "paper.pdf"}).json()
    assert status["state"] == "engine-missing"
    assert status["spec"]["reader"] == "docling"
    assert status["spec"]["available"] is False
    r = client.post("/api/convert", json={"path": "paper.pdf"})
    assert r.status_code == 503
    assert "PDF extra" in r.json()["detail"] or "models aren't" in r.json()["detail"]
    assert 'data-convert-state="engine-missing"' in client.get("/api/files").text


def test_save_normalizes_crlf_to_lf(client):
    """Browsers CRLF-normalize multipart form values, so before 0.2.7 every
    UI save silently rewrote a file's line endings — which broke the
    paginate round-trip's byte-exact claim (the embedded source is read in
    text mode and comes back LF). The save endpoint now normalizes."""
    project = client._project
    (project / "notes.md").write_text("a\nb\n", encoding="utf-8")
    r = client.post("/api/file",
                    data={"path": "notes.md", "content": "a\r\nb\r\n[^1] c\r\n"})
    assert r.status_code == 200
    raw = (project / "notes.md").read_bytes()
    assert b"\r" not in raw
    assert raw == b"a\nb\n[^1] c\n"
