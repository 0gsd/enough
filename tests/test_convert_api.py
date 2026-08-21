"""TestClient pass over the /api/convert/* endpoints, /api/file/blob, the
file tree's hiding + badge attributes, and the POST /api/file sync rule.

supervise=False so no llama-server is spawned; every `ENOUGH_*` seam the app
touches points into tmp_path, so the developer's real ~/enough is never read
or written.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import convert
from enough.server import create_app
from tests.conftest import FIXTURE_HEADER


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
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        c._project = project  # type: ignore[attr-defined]
        yield c
    convert.reset_engines()


def wait_for_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/convert/job/{job_id}").json()
        if snap["state"] != "running":
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished")


# ---------------------------------------------------------------------------
# formats / status
# ---------------------------------------------------------------------------

def test_formats_endpoint(client: TestClient):
    payload = client.get("/api/convert/formats").json()
    assert [r["ext"] for r in payload["formats"]] == list(convert.FORMATS)
    assert payload["export_targets"] == convert.EXPORT_TARGETS
    assert payload["engines"]["pandoc"]["available"] is True
    assert payload["engines"]["docling"]["available"] is False


def test_status_unconverted_then_converted(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    body = client.get("/api/convert/status", params={"path": "memo.docx"}).json()
    assert body["state"] == "unconverted" and body["twin"] is None
    assert body["spec"]["label"] == "Word document"
    assert body["spec"]["sync_ok"] is True

    r = client.post("/api/convert", json={"path": "memo.docx"})
    assert r.status_code == 200, r.text
    snap = wait_for_job(client, r.json()["job"])
    assert snap["state"] == "done", snap
    assert snap["result"]["twin"] == "memo.docx.md"

    body = client.get("/api/convert/status", params={"path": "memo.docx"}).json()
    assert body["state"] == "fresh" and body["twin"] == "memo.docx.md"
    # Either end of the pair resolves to the same answer.
    twin_body = client.get("/api/convert/status",
                           params={"path": "memo.docx.md"}).json()
    assert twin_body["path"] == "memo.docx" and twin_body["state"] == "fresh"


def test_status_on_a_plain_markdown_file(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "notes.md").write_text("# hi\n", encoding="utf-8")
    body = client.get("/api/convert/status", params={"path": "notes.md"}).json()
    assert body["state"] is None and body["export_targets"] == convert.EXPORT_TARGETS


def test_convert_refuses_a_second_job_for_the_same_path(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    first = client.post("/api/convert", json={"path": "memo.docx"})
    assert first.status_code == 200
    second = client.post("/api/convert", json={"path": "memo.docx"})
    assert second.status_code in (409,), second.text
    wait_for_job(client, first.json()["job"])
    # And a second run over an existing twin needs force.
    assert client.post("/api/convert", json={"path": "memo.docx"}).status_code == 409
    r = client.post("/api/convert", json={"path": "memo.docx", "force": True})
    assert r.status_code == 200
    assert wait_for_job(client, r.json()["job"])["state"] == "done"


def test_convert_rejects_cacheawl_and_traversal(client: TestClient):
    assert client.get("/api/convert/status",
                      params={"path": "cacheawl:box/a.docx"}).status_code == 400
    assert client.get("/api/convert/status",
                      params={"path": "../escape.docx"}).status_code == 400


def test_job_cancel_404s_for_an_unknown_id(client: TestClient):
    assert client.get("/api/convert/job/nope").status_code == 404
    assert client.post("/api/convert/job/nope/cancel").status_code == 404


# ---------------------------------------------------------------------------
# The tree: hiding + badge attributes
# ---------------------------------------------------------------------------

def test_tree_hides_the_twin_and_flags_the_original(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    (project / "notes.md").write_text("# ordinary\n", encoding="utf-8")

    html = client.get("/api/files").text
    assert "memo.docx" in html and "notes.md" in html
    assert 'data-convertible="1"' in html
    assert 'data-convert-state="unconverted"' in html

    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    html = client.get("/api/files").text
    # One row for the pair: the original, badged; the twin and assets hidden.
    assert 'data-path="memo.docx"' in html
    assert 'data-path="memo.docx.md"' not in html
    assert "memo.docx.assets" not in html
    assert 'data-converted="1"' in html
    assert 'data-twin="memo.docx.md"' in html
    assert 'data-convert-state="fresh"' in html
    assert 'data-help="converted-file"' in html
    # The ordinary markdown file is untouched by any of this.
    assert 'data-path="notes.md"' in html


def test_tree_shows_a_stray_twin_shaped_file(client: TestClient):
    # `notes.pdf.md` with no manifest is somebody's markdown file, not a twin.
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "notes.pdf").write_bytes(b"%PDF-1.7\n")
    (project / "notes.pdf.md").write_text("mine\n", encoding="utf-8")
    html = client.get("/api/files").text
    assert 'data-path="notes.pdf.md"' in html
    assert 'data-convert-state="engine-missing"' in html   # docling not wired


def test_tree_flags_images(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assert 'data-image="1"' in client.get("/api/files").text


# ---------------------------------------------------------------------------
# /api/file/blob
# ---------------------------------------------------------------------------

def test_blob_serves_allowlisted_types_only(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (project / "page.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    (project / "notes.txt").write_text("hello", encoding="utf-8")

    r = client.get("/api/file/blob", params={"path": "shot.png"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.headers["x-content-type-options"] == "nosniff"

    # Never text/html — a same-origin HTML document would run script.
    assert client.get("/api/file/blob", params={"path": "page.html"}).status_code == 415
    assert client.get("/api/file/blob", params={"path": "notes.txt"}).status_code == 415
    assert client.get("/api/file/blob", params={"path": "missing.png"}).status_code == 404


def test_blob_svg_carries_the_csp(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>',
                                      encoding="utf-8")
    r = client.get("/api/file/blob", params={"path": "logo.svg"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["content-security-policy"] == convert.SVG_CSP
    assert r.headers["x-content-type-options"] == "nosniff"


def test_blob_path_guard_matches_api_file(client: TestClient):
    for bad in ("../../etc/passwd", "/etc/passwd"):
        assert client.get("/api/file/blob", params={"path": bad}).status_code == 400


def test_blob_meta_is_minimal(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    (project / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    body = client.get("/api/file/blob",
                      params={"path": "shot.png", "meta": 1}).json()
    assert body["media_type"] == "image/png" and body["size"] == 28
    # Dimensions are the viewer's job (naturalWidth), not a header parser's.
    assert body["width"] is None and body["height"] is None


# ---------------------------------------------------------------------------
# export / sync / resolve
# ---------------------------------------------------------------------------

def test_export_copy_and_overwrite(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    twin = project / "memo.docx.md"
    twin.write_text(twin.read_text() + "\n\nEdited in the UI.\n", encoding="utf-8")

    r = client.post("/api/convert/export",
                    json={"path": "memo.docx", "target": ".docx", "mode": "copy"})
    assert r.status_code == 200, r.text
    assert r.json()["written"].startswith("memo-")

    r = client.post("/api/convert/export",
                    json={"path": "memo.docx", "target": ".docx", "mode": "overwrite"})
    assert r.status_code == 200, r.text
    assert r.json() == {**r.json(), "written": "memo.docx", "undo": True}
    assert (project / ".memo.docx.undo").is_file()


def test_export_409_when_the_original_moved_underneath(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    memo = project / "memo.docx"
    make_docx(memo)
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    memo.write_bytes(memo.read_bytes() + b"\x00")     # "edited in Word"
    r = client.post("/api/convert/export",
                    json={"path": "memo.docx", "target": ".docx", "mode": "overwrite"})
    assert r.status_code == 409
    assert "changed outside enough" in r.json()["detail"]
    # "export mine over it" is the one call that bypasses it.
    r = client.post("/api/convert/resolve",
                    json={"path": "memo.docx", "choice": "export"})
    assert r.status_code == 200, r.text


def test_export_400s_on_a_bad_target(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    r = client.post("/api/convert/export",
                    json={"path": "memo.docx", "target": ".xyz", "mode": "copy"})
    assert r.status_code == 400
    r = client.post("/api/convert/export",
                    json={"path": "memo.docx", "target": ".odt", "mode": "overwrite"})
    assert r.status_code == 400


def test_resolve_keep_and_reconvert(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    memo = project / "memo.docx"
    make_docx(memo)
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    twin = project / "memo.docx.md"
    twin.write_text("# mine\n", encoding="utf-8")
    memo.write_bytes(memo.read_bytes() + b"\x00")
    assert client.get("/api/convert/status",
                      params={"path": "memo.docx"}).json()["state"] == "conflict"

    r = client.post("/api/convert/resolve", json={"path": "memo.docx", "choice": "keep"})
    assert r.status_code == 200 and r.json()["state"] == "edited"
    assert twin.read_text(encoding="utf-8") == "# mine\n"

    r = client.post("/api/convert/resolve",
                    json={"path": "memo.docx", "choice": "reconvert"})
    assert r.status_code == 200, r.text
    assert wait_for_job(client, r.json()["job"])["state"] == "done"
    assert "# Fixture" in twin.read_text(encoding="utf-8")
    assert (project / ".memo.docx.md.undo").read_text(encoding="utf-8") == "# mine\n"

    assert client.post("/api/convert/resolve",
                       json={"path": "memo.docx", "choice": "nope"}).status_code == 400


def test_sync_endpoint_refuses_writerless_formats(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    deck = project / "slides.pptx"
    deck.write_bytes(b"PK\x03\x04")
    (project / "slides.pptx.md").write_text("# deck\n", encoding="utf-8")
    convert.write_manifest(deck, convert.new_manifest(
        deck, engine={"name": "docling", "version": None, "ocr": None}, assets=None))
    r = client.post("/api/convert/sync", json={"path": "slides.pptx", "enabled": True})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/file — the sync-on-save rule
# ---------------------------------------------------------------------------

def test_save_syncs_the_original(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    memo = project / "memo.docx"
    make_docx(memo)
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    assert client.post("/api/convert/sync",
                       json={"path": "memo.docx", "enabled": True}).status_code == 200

    twin_text = (project / "memo.docx.md").read_text(encoding="utf-8")
    r = client.post("/api/file", data={
        "path": "memo.docx.md",
        "content": twin_text + "\n\nSaved from the UI.\n"})
    assert r.status_code == 200, r.text
    assert 'data-sync-state="synced"' in r.text
    # The original really was rewritten, and it kept its header.
    import zipfile
    assert FIXTURE_HEADER in zipfile.ZipFile(memo).read("word/header1.xml").decode()
    assert convert.state(memo) == "fresh"


def test_save_still_saves_when_the_sync_conflicts(client: TestClient, make_docx):
    project: Path = client._project  # type: ignore[attr-defined]
    memo = project / "memo.docx"
    make_docx(memo)
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    client.post("/api/convert/sync", json={"path": "memo.docx", "enabled": True})
    memo.write_bytes(memo.read_bytes() + b"\x00")     # changed in Word

    r = client.post("/api/file", data={"path": "memo.docx.md",
                                       "content": "# my text\n"})
    assert r.status_code == 200
    assert 'data-sync-state="conflict"' in r.text
    # Saving never loses the user's text, conflict or not.
    assert (project / "memo.docx.md").read_text(encoding="utf-8") == "# my text\n"


def test_save_of_an_ordinary_file_is_unchanged(client: TestClient):
    project: Path = client._project  # type: ignore[attr-defined]
    r = client.post("/api/file", data={"path": "notes.md", "content": "# hi\n"})
    assert r.status_code == 200
    assert "convert-sync" not in r.text
    assert (project / "notes.md").read_text(encoding="utf-8") == "# hi\n"


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def test_install_status(client: TestClient):
    body = client.get("/api/convert/install/status").json()
    assert body["installed"] is convert.docling_installed()
    assert body["recorded"] == []
    assert body["job"] is None
    assert "pandoc" in body["engines"]


def test_install_rejects_an_unknown_extra(client: TestClient):
    assert client.post("/api/convert/install",
                       json={"extra": "wat"}).status_code == 400


# ---------------------------------------------------------------------------
# The `convert` SSE event (payload shape the frontend wave codes against)
# ---------------------------------------------------------------------------

@pytest.fixture
def sse_events(monkeypatch: pytest.MonkeyPatch):
    """Record everything the session fans out over SSE."""
    from enough import server as _server

    seen: list[tuple[str, dict]] = []
    original = _server.Session.emit

    async def spy(self, event, data):
        seen.append((event, data))
        await original(self, event, data)

    monkeypatch.setattr(_server.Session, "emit", spy)
    return seen


def test_convert_job_emits_progress_and_completion(client: TestClient, make_docx,
                                                   sse_events):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    job = client.post("/api/convert", json={"path": "memo.docx"}).json()["job"]
    wait_for_job(client, job)
    # Give the loop a moment to drain the last threadsafe emit.
    deadline = time.time() + 5
    while time.time() < deadline:
        if any(e == "convert" and d.get("state") == "done" for e, d in sse_events):
            break
        client.get("/api/convert/install/status")
        time.sleep(0.05)
    payloads = [d for e, d in sse_events if e == "convert"]
    assert payloads, sse_events
    for p in payloads:
        assert set(p) >= {"job", "path", "state", "progress", "message"}
        assert p["path"] == "memo.docx"
    final = payloads[-1]
    assert final["state"] == "done" and final["result"]["twin"] == "memo.docx.md"


def test_sync_on_save_emits_a_convert_event(client: TestClient, make_docx, sse_events):
    project: Path = client._project  # type: ignore[attr-defined]
    make_docx(project / "memo.docx")
    wait_for_job(client, client.post("/api/convert",
                                     json={"path": "memo.docx"}).json()["job"])
    client.post("/api/convert/sync", json={"path": "memo.docx", "enabled": True})
    client.post("/api/file", data={"path": "memo.docx.md", "content": "# saved\n"})
    synced = [d for e, d in sse_events
              if e == "convert" and d.get("op") == "sync"]
    assert synced and synced[-1]["state"] == "synced"
    assert synced[-1]["original"] == "memo.docx"


def test_cancel_kills_a_running_job(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import threading

    project: Path = client._project  # type: ignore[attr-defined]
    (project / "big.docx").write_bytes(b"PK\x03\x04")
    started, release = threading.Event(), threading.Event()

    def slow(original, **kw):
        started.set()
        release.wait(10)
        return {"twin": "big.docx.md", "assets": None, "engine": {}, "images": 0}

    monkeypatch.setattr(convert, "run_convert", slow)
    try:
        job = client.post("/api/convert", json={"path": "big.docx"}).json()["job"]
        assert started.wait(5)
        assert client.get(f"/api/convert/job/{job}").json()["state"] == "running"
        r = client.post(f"/api/convert/job/{job}/cancel")
        assert r.status_code == 200 and r.json()["state"] == "cancelled"
        # Cancelling twice is a 409, not a second kill.
        assert client.post(f"/api/convert/job/{job}/cancel").status_code == 409
    finally:
        release.set()


# ---------------------------------------------------------------------------
# /api/ui-config — the convert intro's "once per file type" flag
# ---------------------------------------------------------------------------

def test_ui_config_round_trips_seen_convert_intro(client: TestClient):
    """Plan decision 10: the intro flag persists in the ui-config JSON so a
    desktop webview and a browser tab agree. Keys are normalized (dot and
    case stripped), non-strings dropped, and merges are unions — a second
    profile posting its own list must never un-see the first's."""
    r = client.post("/api/ui-config",
                    json={"seen_convert_intro": [".DocX", "pdf", "docx", "", 42]})
    assert r.status_code == 200
    assert r.json()["seen_convert_intro"] == ["docx", "pdf"]
    # Union-merge, not replace.
    r = client.post("/api/ui-config", json={"seen_convert_intro": ["epub"]})
    assert r.json()["seen_convert_intro"] == ["docx", "pdf", "epub"]
    # A theme/font-only post leaves the list alone.
    r = client.post("/api/ui-config", json={"font": "nope"})
    assert r.json()["seen_convert_intro"] == ["docx", "pdf", "epub"]
    # And it survives a fresh read.
    assert client.get("/api/ui-config").json()["seen_convert_intro"] == \
        ["docx", "pdf", "epub"]


def test_save_sync_marker_carries_relative_original(client: TestClient, make_docx):
    """The .convert-sync marker's data-original (and the sync SSE) must be a
    project-relative path, not a basename — a twin in a subfolder would
    otherwise point the UI at the project root."""
    project: Path = client._project  # type: ignore[attr-defined]
    sub = project / "letters"
    sub.mkdir()
    make_docx(sub / "memo.docx")
    job = client.post("/api/convert", json={"path": "letters/memo.docx"}).json()["job"]
    assert wait_for_job(client, job)["state"] == "done"
    assert client.post("/api/convert/sync",
                       json={"path": "letters/memo.docx", "enabled": True}).status_code == 200
    twin_text = (sub / "memo.docx.md").read_text(encoding="utf-8") + "\nmore\n"
    r = client.post("/api/file",
                    data={"path": "letters/memo.docx.md", "content": twin_text})
    assert r.status_code == 200
    assert 'data-sync-state="synced"' in r.text
    assert 'data-original="letters/memo.docx"' in r.text
