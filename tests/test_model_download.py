"""Wave 2a: the in-app model manager's download machinery — the
`ModelDownloadManager` and the `/api/models/{download,delete}` endpoints —
against a local threaded HTTP stub serving tiny fake GGUFs.

Nothing here reaches the network or the real ~/enough: `models.WEIGHTS_DIR`,
`LIVE_STATE` and `REGISTRY_TEMPLATE` are redirected at tmp_path, and the
registry's (deliberately unreachable) `example.invalid` URLs are rebased onto
the stub via `ENOUGH_MODELS_URL_BASE` — the same seam QA uses, so every
download test also proves the seam (docs/seven-models-plan.md §5).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import broker as _broker
from enough import model_download as mdl
from enough import models
from enough.server import create_app

MAIN = b"tiny-gguf-payload-" * 512        # ~9 KB
DRAFT = b"draft-payload-" * 256           # ~3.5 KB
BIG = bytes(range(256)) * 256             # 64 KB — big enough to cancel mid-flight


# ---------------------------------------------------------------------------
# The stub server
# ---------------------------------------------------------------------------

@dataclass
class Stub:
    """A running file server. `requests` records (filename, Range header) in
    order, which is how the resume tests prove a ranged GET happened."""
    base: str = ""
    requests: list[tuple[str, str | None]] = field(default_factory=list)


@pytest.fixture
def serve():
    """Start a throwaway HTTP server over an in-memory {filename: bytes}.

    `ignore_range` answers 200-with-the-whole-file to a Range request (the
    misbehaving-mirror case). `gate` makes the handler send `gate_after`
    bytes and then block until the event is set, which is what lets a test
    cancel a download deterministically instead of racing it."""
    servers: list[ThreadingHTTPServer] = []

    def _start(files: dict[str, bytes], *, ignore_range: bool = False,
               gate: threading.Event | None = None, gate_after: int = 0) -> Stub:
        stub = Stub()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # keep pytest output clean
                pass

            def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's spelling
                name = self.path.lstrip("/")
                rng = self.headers.get("Range")
                stub.requests.append((name, rng))
                body = files.get(name)
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                start = 0
                if rng and not ignore_range:
                    start = int(rng.split("=", 1)[1].split("-", 1)[0])
                    if start >= len(body):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(body)}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header("Content-Range",
                                     f"bytes {start}-{len(body) - 1}/{len(body)}")
                else:
                    self.send_response(200)
                chunk = body[start:]
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                try:
                    if gate is None:
                        self.wfile.write(chunk)
                    else:
                        self.wfile.write(chunk[:gate_after])
                        self.wfile.flush()
                        gate.wait(10)
                        self.wfile.write(chunk[gate_after:])
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass  # the client cancelled — expected

        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        stub.base = f"http://127.0.0.1:{srv.server_address[1]}"
        return stub

    yield _start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def _registry() -> dict:
    """Three shapes: plain, separate-draft-file MTP, and one too big for any
    disk (the preflight's subject). URLs are unreachable on purpose — only
    the ENOUGH_MODELS_URL_BASE rebase makes them fetchable."""
    common = {
        "family": "test", "ctx_max": 32768,
        "ctx_defaults": {"gte_64gb": 32768, "gte_32gb": 16384,
                         "gte_16gb": 8192, "lt_16gb": 4096},
    }
    return {
        "default": "tiny",
        "models": {
            "tiny": {
                "cute_name": "TINY", "label": "Tiny 1B",
                "gguf_filename": "tiny.gguf",
                "gguf_url": "https://example.invalid/repo/tiny.gguf",
                "disk_gb_approx": 0.001, "ram_gb_recommended_min": 8, **common,
            },
            "drafty": {
                "cute_name": "DRAFTY", "label": "Draft-file MTP 27B",
                "gguf_filename": "drafty.gguf",
                "gguf_url": "https://example.invalid/repo/drafty.gguf",
                "disk_gb_approx": 0.002, "ram_gb_recommended_min": 24, **common,
                "mtp": {
                    "spec_type": "draft-mtp", "spec_draft_n_max": 3,
                    "draft_gguf_filename": "mtp-drafty.gguf",
                    "draft_gguf_url": "https://example.invalid/repo/mtp-drafty.gguf",
                    "draft_disk_gb_approx": 0.001,
                },
            },
            "huge": {
                "cute_name": "HUGE", "label": "Huge 400B",
                "gguf_filename": "huge.gguf",
                "gguf_url": "https://example.invalid/repo/huge.gguf",
                "disk_gb_approx": 500.0, "ram_gb_recommended_min": 512, **common,
            },
        },
    }


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point models.py's three real-install paths at tmp_path, install the
    fake registry, and fake a roomy machine. Returns the weights dir."""
    weights = tmp_path / "weights"
    weights.mkdir()
    reg = tmp_path / "models-template.json"
    reg.write_text(json.dumps(_registry()), encoding="utf-8")
    monkeypatch.setattr(models, "WEIGHTS_DIR", weights)
    monkeypatch.setattr(models, "LIVE_STATE", tmp_path / "config" / "models.json")
    monkeypatch.setattr(models, "REGISTRY_TEMPLATE", reg)
    monkeypatch.setattr(models, "total_ram_gb", lambda: 128)
    monkeypatch.setattr(models, "free_disk_gb", lambda: 500.0)
    return weights


def _seed_part(filename: str, data: bytes) -> Path:
    part = mdl.part_path(filename)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(data)
    return part


def _run(cute: str) -> tuple[mdl.ModelDownloadManager, list[tuple[str, dict]]]:
    """Download `cute` to completion on a throwaway loop; return the manager
    and every event it emitted."""
    events: list[tuple[str, dict]] = []

    async def _emit(name: str, data: dict) -> None:
        events.append((name, dict(data)))

    async def go() -> mdl.ModelDownloadManager:
        mgr = mdl.ModelDownloadManager(emit=_emit)
        mgr.start(cute)
        await mgr.wait()
        return mgr

    return asyncio.run(go()), events


# ---------------------------------------------------------------------------
# The QA seam
# ---------------------------------------------------------------------------

def test_url_base_env_rebases_registry_urls_by_filename(
        iso: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(models.URL_BASE_ENV, raising=False)
    assert models.resolve("drafty")["url"].startswith("https://example.invalid/")

    monkeypatch.setenv(models.URL_BASE_ENV, "http://127.0.0.1:9/stubs/")
    info = models.resolve("drafty")
    assert info["url"] == "http://127.0.0.1:9/stubs/drafty.gguf"
    assert info["draft_url"] == "http://127.0.0.1:9/stubs/mtp-drafty.gguf"


def test_weights_dir_env_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENOUGH_WEIGHTS_DIR", raising=False)
    assert models._weights_dir_default() == Path.home() / "enough" / "weights"
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(tmp_path / "scratch"))
    assert models._weights_dir_default() == tmp_path / "scratch"


def test_live_state_env_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENOUGH_LIVE_STATE", raising=False)
    assert models._live_state_default() == Path.home() / "enough" / "config" / "models.json"
    monkeypatch.setenv("ENOUGH_LIVE_STATE", str(tmp_path / "state.json"))
    assert models._live_state_default() == tmp_path / "state.json"


def test_registry_template_env_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENOUGH_MODELS_REGISTRY", raising=False)
    assert models._registry_template_default() == models.INSTALL_ROOT / "defaults" / "models.json"
    monkeypatch.setenv("ENOUGH_MODELS_REGISTRY", str(tmp_path / "registry.json"))
    assert models._registry_template_default() == tmp_path / "registry.json"


def test_rebase_url_uses_local_filename(monkeypatch: pytest.MonkeyPatch):
    # The stub dir is keyed by gguf_filename, which differs from the URL
    # basename for the -MTP-marked local names (q35-09 / q36-27).
    monkeypatch.setenv(models.URL_BASE_ENV, "http://127.0.0.1:9/stubs")
    assert (
        models.rebase_url("https://hf.example/repo/Qwen3.5-9B-Q4_K_M.gguf",
                          "Qwen3.5-9B-MTP-Q4_K_M.gguf")
        == "http://127.0.0.1:9/stubs/Qwen3.5-9B-MTP-Q4_K_M.gguf"
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_downloads_the_main_gguf_then_the_draft(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    stub = serve({"drafty.gguf": MAIN, "mtp-drafty.gguf": DRAFT})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)

    mgr, events = _run("drafty")

    assert (iso / "drafty.gguf").read_bytes() == MAIN
    assert (iso / "mtp-drafty.gguf").read_bytes() == DRAFT
    # Main first, draft second, each fetched exactly once and unranged.
    assert stub.requests == [("drafty.gguf", None), ("mtp-drafty.gguf", None)]
    # No .part debris left behind.
    assert not mdl.part_path("drafty.gguf").exists()
    assert not mdl.part_path("mtp-drafty.gguf").exists()
    assert not mgr.active


def test_the_event_stream_carries_the_ui_contract(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    stub = serve({"drafty.gguf": MAIN, "mtp-drafty.gguf": DRAFT})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)

    _mgr, events = _run("drafty")

    assert {name for name, _ in events} == {"model-dl"}
    payloads = [data for _, data in events]
    for data in payloads:
        assert data["cute"] == "drafty"
        assert data["label"] == "Draft-file MTP 27B"
        assert data["phase"] in ("main", "draft")
        assert set(data) >= {
            "status", "filename", "bytes_done", "bytes_total", "pct",
            "human_done", "human_total", "rate_bps", "eta_s", "error",
        }
    assert payloads[0]["phase"] == "main"
    assert payloads[0]["status"] == "downloading"
    assert payloads[0]["bytes_done"] == 0
    assert any(p["phase"] == "draft" for p in payloads)

    done = payloads[-1]
    assert done["status"] == "done"
    assert done["installed"] is True and done["draft_installed"] is True
    assert done["pct"] == 100.0
    assert done["human_total"] == mdl.bytes_to_human(len(DRAFT))
    assert done["error"] is None


def test_downloads_only_the_draft_when_the_main_gguf_is_already_there(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    """A registry that grows a draft companion for a model the user already
    has must fetch the draft alone, not refuse as "already installed"."""
    (iso / "drafty.gguf").write_bytes(MAIN)
    stub = serve({"mtp-drafty.gguf": DRAFT})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)

    _mgr, events = _run("drafty")

    assert [name for name, _ in stub.requests] == ["mtp-drafty.gguf"]
    assert events[0][1]["phase"] == "draft"
    assert (iso / "mtp-drafty.gguf").read_bytes() == DRAFT


def test_a_plain_model_needs_no_draft_phase(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    stub = serve({"tiny.gguf": MAIN})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)

    _mgr, events = _run("tiny")

    assert {data["phase"] for _, data in events} == {"main"}
    assert (iso / "tiny.gguf").read_bytes() == MAIN


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

def test_resume_continues_from_the_partial(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    """The `.part` file IS the resume state — no config record involved, so
    this is also the across-restarts case."""
    stub = serve({"tiny.gguf": MAIN})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    _seed_part("tiny.gguf", MAIN[:1000])

    _mgr, events = _run("tiny")

    assert stub.requests == [("tiny.gguf", "bytes=1000-")]
    assert (iso / "tiny.gguf").read_bytes() == MAIN
    # The opening event anchors at the resume point, not at zero.
    assert events[0][1]["bytes_done"] == 1000


def test_a_complete_partial_is_finished_not_refetched(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    """A cancel that landed on the last chunk leaves a whole-file `.part`;
    the server answers 416 and we move it into place rather than erroring."""
    stub = serve({"tiny.gguf": MAIN})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    _seed_part("tiny.gguf", MAIN)

    mgr, _events = _run("tiny")

    assert stub.requests == [("tiny.gguf", f"bytes={len(MAIN)}-")]
    assert (iso / "tiny.gguf").read_bytes() == MAIN
    assert mgr.state()["status"] == "done"


def test_a_server_that_ignores_range_restarts_cleanly(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    """200 instead of 206 means the mirror ignored our Range — the partial
    must be overwritten, never appended to."""
    stub = serve({"tiny.gguf": MAIN}, ignore_range=True)
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    _seed_part("tiny.gguf", b"stale-bytes" * 50)

    _mgr, _events = _run("tiny")

    assert (iso / "tiny.gguf").read_bytes() == MAIN


def test_partials_reports_resumable_downloads(iso: Path):
    _seed_part("drafty.gguf", b"x" * 300)
    _seed_part("mtp-drafty.gguf", b"y" * 200)
    assert mdl.partials() == {"drafty": 500}


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

def test_cancel_keeps_the_partial_and_the_next_start_resumes(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    gate = threading.Event()
    stub = serve({"tiny.gguf": BIG}, gate=gate, gate_after=16384)
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    monkeypatch.setattr(mdl, "CHUNK_SIZE", 1024)
    monkeypatch.setattr(mdl, "EMIT_INTERVAL", 0.0)   # progress per chunk

    async def go() -> mdl.ModelDownloadManager:
        mgr = mdl.ModelDownloadManager()
        mgr.start("tiny")
        for _ in range(500):
            if mgr.state()["bytes_done"] >= 1024:
                break
            await asyncio.sleep(0.01)
        mgr.cancel("tiny")
        gate.set()                                   # let the handler finish
        await mgr.wait()
        return mgr

    mgr = asyncio.run(go())
    kept = mdl.part_path("tiny.gguf").stat().st_size
    assert 0 < kept < len(BIG)
    assert not (iso / "tiny.gguf").exists()          # nothing moved into place
    assert mgr.state()["status"] == "cancelled"
    assert mdl.partials() == {"tiny": kept}

    # Second attempt picks up exactly where the first stopped.
    stub2 = serve({"tiny.gguf": BIG})
    monkeypatch.setenv(models.URL_BASE_ENV, stub2.base)
    _mgr2, _events = _run("tiny")

    assert stub2.requests == [("tiny.gguf", f"bytes={kept}-")]
    assert (iso / "tiny.gguf").read_bytes() == BIG
    assert mdl.partials() == {}


def test_cancel_refuses_when_nothing_is_running(iso: Path):
    with pytest.raises(mdl.ModelDownloadError) as e:
        mdl.ModelDownloadManager().cancel("tiny")
    assert e.value.status == 409


def test_cancel_refuses_a_different_model_than_the_one_running(
        iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    gate = threading.Event()
    stub = serve({"tiny.gguf": BIG}, gate=gate, gate_after=16384)
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    monkeypatch.setattr(mdl, "CHUNK_SIZE", 1024)
    monkeypatch.setattr(mdl, "EMIT_INTERVAL", 0.0)

    async def go() -> int:
        mgr = mdl.ModelDownloadManager()
        mgr.start("tiny")
        for _ in range(500):
            if mgr.state()["bytes_done"] >= 1024:
                break
            await asyncio.sleep(0.01)
        with pytest.raises(mdl.ModelDownloadError) as e:
            mgr.cancel("drafty")
        status = e.value.status
        # …and a second download is refused while this one runs.
        with pytest.raises(mdl.ModelDownloadError) as e2:
            mgr.start("drafty")
        assert e2.value.status == 409
        mgr.cancel()
        gate.set()
        await mgr.wait()
        return status

    assert asyncio.run(go()) == 409


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def test_refuses_a_model_that_is_already_installed(iso: Path):
    (iso / "tiny.gguf").write_bytes(MAIN)
    with pytest.raises(mdl.ModelDownloadError) as e:
        mdl.ModelDownloadManager().start("tiny")
    assert e.value.status == 409
    assert "already installed" in str(e.value)


def test_refuses_when_the_disk_cant_hold_whats_left(
        iso: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(models, "free_disk_gb", lambda: 1.0)
    with pytest.raises(mdl.ModelDownloadError) as e:
        mdl.ModelDownloadManager().start("huge")
    assert e.value.status == 400
    assert "not enough free space" in str(e.value)


def test_the_disk_guard_counts_only_the_remaining_bytes(
        iso: Path, monkeypatch: pytest.MonkeyPatch):
    """Most of the file already in its `.part` means most of the download is
    already paid for — the guard judges the remainder, not the full size,
    or no resume would ever restart on a nearly-full volume."""
    monkeypatch.setattr(models, "free_disk_gb", lambda: 100_000 / mdl._G)
    mgr = mdl.ModelDownloadManager()
    phase = {"phase": "main", "filename": "tiny.gguf",
             "url": "http://127.0.0.1:9/tiny.gguf", "expected_bytes": 200_000}
    with pytest.raises(mdl.ModelDownloadError) as e:
        mgr.preflight([phase])
    assert e.value.status == 400

    _seed_part("tiny.gguf", b"x" * 150_000)
    mgr.preflight([phase])                     # 50 KB left, 100 KB free: fine


def test_unknown_model_raises_key_error(iso: Path):
    with pytest.raises(KeyError):
        mdl.ModelDownloadManager().start("nope")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_removes_main_draft_and_partial(iso: Path):
    models.save_state({"current": "tiny"})
    (iso / "drafty.gguf").write_bytes(MAIN)
    (iso / "mtp-drafty.gguf").write_bytes(DRAFT)
    _seed_part("drafty.gguf", b"x" * 10)

    out = mdl.ModelDownloadManager().delete("drafty")

    assert sorted(out["removed"]) == ["drafty.gguf", "drafty.gguf.part",
                                      "mtp-drafty.gguf"]
    assert out["freed_bytes"] == len(MAIN) + len(DRAFT) + 10
    assert out["freed_human"]
    assert not (iso / "drafty.gguf").exists()
    assert not (iso / "mtp-drafty.gguf").exists()
    assert not mdl.part_path("drafty.gguf").exists()


def test_delete_refuses_the_current_model(iso: Path):
    models.save_state({"current": "drafty"})
    (iso / "drafty.gguf").write_bytes(MAIN)
    with pytest.raises(mdl.ModelDownloadError) as e:
        mdl.ModelDownloadManager().delete("drafty")
    assert e.value.status == 409
    assert (iso / "drafty.gguf").exists()      # nothing removed


def test_delete_of_an_absent_model_is_a_404(iso: Path):
    models.save_state({"current": "tiny"})
    with pytest.raises(mdl.ModelDownloadError) as e:
        mdl.ModelDownloadManager().delete("drafty")
    assert e.value.status == 404


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def client(iso: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient over create_app with every ENOUGH_* hook pointed at scratch
    dirs (house rule) and supervise=False so no llama-server is spawned."""
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(tmp_path / "wikisink.json"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    # Toggle defaults without reading (or writing) the user's broker.json —
    # and with local_models_only ON, /api/models skips the cloud slot, so no
    # keyring access from a test.
    monkeypatch.setattr(_broker, "is_enabled", lambda key: True)
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        yield c


def _await_download(client: TestClient, status: str = "done", timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    snap: dict = {}
    while time.monotonic() < deadline:
        snap = client.get("/api/models").json()["download"]
        if snap["status"] == status:
            return snap
        time.sleep(0.02)
    raise AssertionError(f"download never reached {status!r}: {snap}")


def test_api_download_draft_follows_main_then_delete(
        client: TestClient, iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    stub = serve({"drafty.gguf": MAIN, "mtp-drafty.gguf": DRAFT})
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)

    r = client.post("/api/models/download/drafty")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["started"] is True
    assert body["cute"] == "drafty" and body["phase"] == "main"
    assert body["status"] == "downloading"

    snap = _await_download(client)
    assert snap["installed"] is True and snap["draft_installed"] is True
    assert (iso / "drafty.gguf").exists() and (iso / "mtp-drafty.gguf").exists()

    payload = client.get("/api/models").json()
    row = next(m for m in payload["models"] if m["cute"] == "drafty")
    assert row["installed"] is True and row["draft_installed"] is True

    r = client.post("/api/models/delete/drafty")
    assert r.status_code == 200, r.text
    assert sorted(r.json()["removed"]) == ["drafty.gguf", "mtp-drafty.gguf"]
    assert not (iso / "drafty.gguf").exists()


def test_api_refuses_an_installed_model_with_409(client: TestClient, iso: Path):
    (iso / "tiny.gguf").write_bytes(MAIN)
    r = client.post("/api/models/download/tiny")
    assert r.status_code == 409
    assert "already installed" in r.json()["detail"]


def test_api_unknown_model_is_404(client: TestClient):
    assert client.post("/api/models/download/nope").status_code == 404
    assert client.post("/api/models/delete/nope").status_code == 404


def test_api_delete_of_the_current_model_is_409(client: TestClient, iso: Path):
    models.save_state({"current": "drafty"})
    (iso / "drafty.gguf").write_bytes(MAIN)
    r = client.post("/api/models/delete/drafty")
    assert r.status_code == 409
    assert "switch to another one first" in r.json()["detail"]


def test_api_cancel_with_nothing_running_is_409(client: TestClient):
    r = client.post("/api/models/download/tiny/cancel")
    assert r.status_code == 409


def test_api_cancel_keeps_the_partial(
        client: TestClient, iso: Path, serve, monkeypatch: pytest.MonkeyPatch):
    gate = threading.Event()
    stub = serve({"tiny.gguf": BIG}, gate=gate, gate_after=16384)
    monkeypatch.setenv(models.URL_BASE_ENV, stub.base)
    monkeypatch.setattr(mdl, "CHUNK_SIZE", 1024)
    monkeypatch.setattr(mdl, "EMIT_INTERVAL", 0.0)

    assert client.post("/api/models/download/tiny").status_code == 200
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if client.get("/api/models").json()["download"]["bytes_done"] >= 1024:
            break
        time.sleep(0.02)

    r = client.post("/api/models/download/tiny/cancel")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "cute": "tiny", "cancelling": True}
    gate.set()

    snap = _await_download(client, "cancelled")
    assert not (iso / "tiny.gguf").exists()
    assert snap["partials"]["tiny"] == mdl.part_path("tiny.gguf").stat().st_size


def test_api_models_carries_an_idle_download_snapshot(client: TestClient):
    snap = client.get("/api/models").json()["download"]
    assert snap["active"] is False
    assert snap["status"] == "idle"
    assert snap["cute"] is None
    assert snap["partials"] == {}
