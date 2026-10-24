"""Agent-free mode (0.4.4, docs/docoes-044-plan.md §13): the machine-global
`agent_free` switch in ui.json, the supervisor that never starts a model while
it is on, the 409 gate on every model route, the derivations' rules path with
`reason: agent-free`, Canon's ingest called directly, and the runtime toggle
stopping and starting the model.

Every state seam points inside tmp_path (conftest's autouse fixture; the
switch lives in the ui.json `ENOUGH_UI_CONFIG` names), `models.LIVE_STATE`
(read once at import) is pointed there too, and no test starts a model: the
supervisor is a fake, or the real class with `_launch` recorded.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon, cloud, llm, models, skeleton, skillaudit, tools
from enough import server as _server
from enough import supervisor as _supervisor
from enough.server import create_app

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"


def set_agent_free(on: bool) -> None:
    """Write the switch the way a user's file would hold it."""
    path = agent_free.ui_config_path()
    cfg: dict[str, Any] = {}
    if path.is_file():
        cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg[agent_free.KEY] = on
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    skeleton.ensure_skeleton(proj)
    for where in (Path.home(), agent_free.ui_config_path(), canon.root(), models.LIVE_STATE):
        assert str(where).startswith(str(tmp_path)), where
    return proj


@pytest.fixture
def free(project: Path) -> Path:
    """Agent-free mode on, before any app is built."""
    set_agent_free(True)
    assert agent_free.enabled()
    return project


@pytest.fixture
def client(free: Path):
    app = create_app(free, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c


class FakeSupervisor:
    """Records what the server asks of it; never touches a process."""

    def __init__(self) -> None:
        self.bootstraps = 0
        self.stop_calls: list[bool] = []
        self.ready = False
        self.current_cute: str | None = None
        self.current_ctx: int | None = None
        self.on_ready = None

    async def bootstrap(self) -> None:
        self.bootstraps += 1

    async def stop(self, *, only_if_owned: bool = False) -> None:
        self.stop_calls.append(only_if_owned)

    def status(self) -> dict[str, Any]:
        on = agent_free.enabled()
        return {"mode": "agent-free" if on else "off", "ready": False, "cute": None,
                "ctx": None, "url": "http://127.0.0.1:9", "error": None, "agent_free": on}


@pytest.fixture
def fake_sup(monkeypatch: pytest.MonkeyPatch) -> FakeSupervisor:
    fake = FakeSupervisor()
    monkeypatch.setattr(_server, "LlamaSupervisor", lambda **kw: fake)
    return fake


def wait_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    snap: dict = {}
    while time.time() < deadline:
        snap = client.get(f"/api/canon/job/{job_id}").json()
        if snap["state"] not in ("queued", "running"):
            return snap
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished: {snap}")


def refused(r) -> bool:
    return r.status_code == 409 and r.json()["detail"].startswith("agent-free mode:")


# ---------------------------------------------------------------------------
# The preference
# ---------------------------------------------------------------------------

def test_the_template_ships_it_off():
    cfg = json.loads((REPO / "defaults" / "ui-config.json").read_text(encoding="utf-8"))
    assert cfg[agent_free.KEY] is False


def test_only_a_literal_true_turns_it_on(tmp_path: Path):
    path = agent_free.ui_config_path()
    assert not path.exists() and agent_free.enabled() is False      # no file: off
    path.parent.mkdir(parents=True, exist_ok=True)
    for raw, want in (("{}", False), ('{"agent_free": "yes"}', False),
                      ('{"agent_free": 1}', False), ("{not json", False),
                      ("[true]", False), ('{"agent_free": true}', True),
                      ('{"agent_free": false}', False)):
        path.write_text(raw, encoding="utf-8")
        assert agent_free.enabled() is want, raw


def test_the_preference_round_trips(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        # A file from before 0.4.4 has no key: the read view says false.
        c.get("/api/ui-config")                 # seeds the live file
        live = agent_free.ui_config_path()
        cfg = json.loads(live.read_text(encoding="utf-8"))
        cfg.pop(agent_free.KEY, None)
        live.write_text(json.dumps(cfg), encoding="utf-8")
        assert c.get("/api/ui-config").json()[agent_free.KEY] is False

        r = c.post("/api/ui-config", json={"agent_free": True})
        assert r.status_code == 200 and r.json()[agent_free.KEY] is True
        assert c.get("/api/ui-config").json()[agent_free.KEY] is True
        assert json.loads(live.read_text(encoding="utf-8"))[agent_free.KEY] is True
        assert agent_free.enabled()

        # Not a bool: dropped, the switch keeps what it had.
        assert c.post("/api/ui-config", json={"agent_free": "no"}).json()[agent_free.KEY] is True
        # A theme change leaves it alone.
        assert c.post("/api/ui-config", json={"theme": "pastel"}).json()[agent_free.KEY] is True

        assert c.post("/api/ui-config", json={"agent_free": False}).json()[agent_free.KEY] is False
        assert not agent_free.enabled()


def test_the_page_boots_knowing_it(free: Path):
    app = create_app(free, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        assert '"agent_free": true' in c.get("/").text


def test_home_mode_saves_it_and_boots_knowing_it(tmp_path: Path, project: Path):
    app = create_app(tmp_path, "http://127.0.0.1:9", supervise=False, home=True)
    with TestClient(app) as c:
        assert '"agent_free": false' in c.get("/").text
        assert c.post("/api/ui-config", json={"agent_free": True}).json()[agent_free.KEY] is True
        assert '"agent_free": true' in c.get("/").text
        # The model routes are the project server's; home 404s them as ever.
        assert c.get("/api/llm-status").status_code == 404
    assert agent_free.enabled()


# ---------------------------------------------------------------------------
# Boot: no model
# ---------------------------------------------------------------------------

def test_an_agent_free_boot_starts_no_model(free: Path, fake_sup: FakeSupervisor):
    app = create_app(free, "http://127.0.0.1:9", supervise=True)
    with TestClient(app) as c:
        assert fake_sup.bootstraps == 0
        body = c.get("/api/llm-status").json()
        assert body["mode"] == "agent-free" and body["ready"] is False
        assert body["agent_free"] is True
        assert body["fits"] is None and body["preflight"] == "skipped"
        models_view = c.get("/api/models").json()
        assert models_view["agent_free"] is True
        assert models_view["supervisor"]["mode"] == "agent-free"
    assert app.state.session.preflight.state in ("idle", "skipped")


def test_llm_status_agent_free_without_supervision(client: TestClient):
    body = client.get("/api/llm-status").json()
    assert (body["mode"], body["ready"], body["fits"], body["preflight"]) == \
        ("agent-free", False, None, "skipped")
    assert client.get("/api/models").json()["supervisor"] == {"mode": "agent-free", "agent_free": True}


def test_the_real_supervisor_never_adopts_launches_or_switches(free: Path, monkeypatch):
    sup = _supervisor.LlamaSupervisor(llm_url="http://127.0.0.1:9")

    async def no_probe(self):
        raise AssertionError("agent-free bootstrap must not probe for a server")

    stops: list[bool] = []

    async def stop(self, *, only_if_owned: bool = False):
        stops.append(only_if_owned)

    monkeypatch.setattr(_supervisor.LlamaSupervisor, "_probe_existing", no_probe)
    monkeypatch.setattr(_supervisor.LlamaSupervisor, "stop", stop)
    import asyncio
    asyncio.run(sup.bootstrap())
    assert sup.proc is None and sup.adopted_pid is None and sup.last_error is None
    with pytest.raises(RuntimeError, match="agent-free mode"):
        sup._launch("g40-04", 4096)
    with pytest.raises(RuntimeError, match="agent-free mode"):
        asyncio.run(sup.switch("g40-04", 4096))
    assert stops == []                      # refused before anything stopped
    st = sup.status()
    assert st["mode"] == "agent-free" and st["ready"] is False and st["agent_free"] is True


def test_the_cli_skips_the_llama_check_when_agent_free(free: Path, monkeypatch):
    from enough import __main__ as cli

    def no_check(url):
        raise AssertionError("agent-free: no llama-server to insist on")

    ran: list[dict] = []
    monkeypatch.setattr(llm, "check_llm_reachable", no_check)
    monkeypatch.setattr(_server, "run", lambda **kw: ran.append(kw) or 0)
    assert cli.main(["--dir", str(free), "--no-browser", "--no-supervise"]) == 0
    assert ran and ran[0]["project_dir"] == free.resolve()


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

COUNCIL_REFUSED = ("setup", "convene", "next", "round", "run", "say", "pal",
                   "conclude", "reconvene")


def test_every_model_route_answers_409(client: TestClient):
    assert refused(client.post("/api/chat", data={"message": "hello"}))
    assert refused(client.post("/api/chat", data={"message": "/intro"}))
    assert refused(client.post("/api/model", json={"cute": "g40-04"}))
    assert refused(client.post("/api/cloud/health-check"))
    assert refused(client.post("/api/transcribe", files={"audio": ("a.wav", b"RIFF", "audio/wav")}))
    for sub in COUNCIL_REFUSED:
        assert refused(client.post(f"/api/council/{sub}", json={"path": "c.composure.md"})), sub


def test_what_needs_no_model_stays_open(client: TestClient):
    # Stopping a council is always allowed (here: a 400 for the bad path,
    # which proves the route answered, not the gate).
    r = client.post("/api/council/pause", json={})
    assert r.status_code != 409
    assert client.get("/api/council/participants").status_code == 200
    assert client.get("/api/reset").status_code == 200
    assert client.get("/api/intro").status_code == 200
    # Installing stays allowed: an unknown model is the handler's 404.
    assert client.post("/api/models/download/no-such-model").status_code == 404
    assert client.post("/api/models/delete/no-such-model").status_code == 404
    pal = client.get("/api/pal/status").json()
    assert pal["available"] is False and pal["reason"] == "agent-free mode is on"


def test_the_gate_opens_when_the_switch_is_off(project: Path):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        # An empty message is the handler's no-op 200: the gate let it by.
        assert c.post("/api/chat", data={"message": ""}).status_code == 200
        set_agent_free(True)
        assert refused(c.post("/api/chat", data={"message": ""}))
        set_agent_free(False)
        assert c.post("/api/chat", data={"message": ""}).status_code == 200


def test_the_refusal_table_is_post_only():
    assert _server.agent_free_refusal("GET", "/api/council/state") is None
    assert _server.agent_free_refusal("POST", "/api/council/pause") is None
    assert _server.agent_free_refusal("POST", "/api/models/download/x") is None
    assert _server.agent_free_refusal("POST", "/api/canon/derive") is None
    assert _server.agent_free_refusal("POST", "/api/council/run").startswith("agent-free mode:")
    assert _server.agent_free_refusal("POST", "/api/chat").startswith("agent-free mode:")
    assert _server.agent_free_refusal("POST", "/api/transcribe").startswith("agent-free mode:")


def test_a_skill_that_needs_its_audit_is_refused(client: TestClient, free: Path, monkeypatch):
    d = free / "rness" / "skills" / "widget"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: widget\ndescription: hi\n---\n\nhi\n", encoding="utf-8")

    def no_audit(*a, **kw):
        raise AssertionError("no audit while agent-free")

    monkeypatch.setattr(skillaudit, "try_claim", no_audit)
    r = client.post("/api/skills/toggle", data={"name": "widget", "enabled": "1"})
    assert refused(r)
    assert "first-use audit" in r.json()["detail"]
    # Toggling off needs no model.
    assert client.post("/api/skills/toggle", data={"name": "widget", "enabled": "0"}).status_code == 200


def test_the_model_doors_refuse_behind_the_gate(free: Path, monkeypatch):
    def no_probe(url, timeout=3.0):
        raise AssertionError("agent-free: nothing is probed")

    monkeypatch.setattr(llm, "check_llm_reachable", no_probe)
    assert llm.reachable("http://127.0.0.1:9") == (False, "agent-free")
    with pytest.raises(llm.LLMUnavailable, match="agent-free"):
        llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:9")
    with pytest.raises(llm.LLMUnavailable, match="agent-free"):
        llm.complete([{"role": "user", "content": "hi"}], llm_url=None, cloud_gate=False)
    gate = cloud.gate_status()
    assert gate["open"] is False and gate["denial"].startswith("agent-free mode:")
    res = tools.execute(free, tools.ToolCall(
        name="read_file", path="notes.md", content=None, command=None, url=None,
        extra={}, raw="", span=(0, 0)))
    assert res.ok is False and "agent-free mode" in res.body


# ---------------------------------------------------------------------------
# Derivations: the rules path, labelled agent-free
# ---------------------------------------------------------------------------

def test_derive_atem_and_compile_run_by_rules(client: TestClient, free: Path, monkeypatch):
    def no_complete(*a, **kw):
        raise AssertionError("no completion while agent-free")

    monkeypatch.setattr(llm, "complete", no_complete)

    r = client.post("/api/canon/derive", json={"path": "notes.md", "what": "emf"})
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert job["mode"] == "rules" and job["reason"] == "agent-free"
    assert job["message"].startswith("agent-free:")
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    assert done["result"]["mode"] == "rules" and done["result"]["reason"] == "agent-free"
    assert "agent-free" in done["message"]
    assert (free / "notes.md.cosm").is_file()

    r = client.post("/api/canon/atem", json={"text": "The orchard keeps a record of every tree."})
    job = r.json()["job"]
    assert (job["mode"], job["reason"]) == ("rules", "agent-free")
    done = wait_job(client, job["id"])
    assert done["state"] == "done" and done["result"]["reason"] == "agent-free"

    r = client.post("/api/canon/atem", json={"path": "notes.md"})
    done = wait_job(client, r.json()["job"]["id"])
    assert done["state"] == "done" and (done["result"]["mode"], done["result"]["reason"]) == \
        ("rules", "agent-free")

    r = client.post("/api/canon/compile", json={"path": "notes.md.cosm"})
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert (job["mode"], job["reason"]) == ("rules", "agent-free")
    done = wait_job(client, job["id"])
    assert done["state"] == "done", done
    assert done["result"]["mode"] == "rules" and done["result"]["reason"] == "agent-free"
    assert (free / done["result"]["written"]).is_file()


def test_rules_jobs_without_agent_free_keep_their_shape(project: Path):
    """No model answering, switch off: rules as in 0.4.3, and no `reason`."""
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        job = c.post("/api/canon/atem", json={"text": "A short passage of text."}).json()["job"]
        assert job["mode"] == "rules" and "reason" not in job
        assert not job["message"].startswith("agent-free")
        done = wait_job(c, job["id"])
        assert "reason" not in done and "reason" not in done["result"]


# ---------------------------------------------------------------------------
# Canon's ingest, called directly
# ---------------------------------------------------------------------------

def test_ingest_runs_directly_and_says_its_caps(client: TestClient, tmp_path: Path, monkeypatch):
    from enough.wikisink import config as wconfig
    # Read once at import, so pointed here for this test's no-archive world.
    monkeypatch.setattr(wconfig, "CONFIG_PATH", tmp_path / "wikisink.json")
    caps = client.get("/api/canon/ingest-caps").json()
    assert caps["caps"] == {"url_pages": canon.INGEST_URL_PAGE_CAP,
                            "wiki_articles": canon.INGEST_WIKI_ARTICLE_CAP,
                            "path_files": canon.INGEST_PATH_FILE_CAP}
    assert caps["depth"] == {"min": 1, "max": 3, "all": ["path", "url"]}
    assert set(caps["fetch"]) == {"enabled", "tor_for_offlist", "allowlist", "robots"}
    assert caps["fetch"]["robots"] is True and isinstance(caps["fetch"]["allowlist"], list)
    assert caps["wikisink"]["installed"] is False and caps["wikisink"]["reason"]
    assert caps["agent_free"] is True

    src = tmp_path / "source"
    (src / "sub").mkdir(parents=True)
    (src / "a.md").write_text("# A\n\nalpha\n", encoding="utf-8")
    (src / "sub" / "b.txt").write_text("beta\n", encoding="utf-8")
    r = client.post("/api/canon/ingest", json={"box": "shelf", "type": "path",
                                               "value": str(src), "depth": 2})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ingesting"
    deadline = time.time() + 20
    status: dict = {}
    while time.time() < deadline:
        status = client.get("/api/canon/ingest-status", params={"box": "shelf"}).json()
        if status.get("status") in ("complete", "failed"):
            break
        time.sleep(0.05)
    assert status.get("status") == "complete", status
    vol = canon.volume_dir("shelf")
    assert (vol / "a.md").is_file() and (vol / "sub" / "b.txt").is_file()


# ---------------------------------------------------------------------------
# The runtime toggle
# ---------------------------------------------------------------------------

def test_turning_it_on_stops_the_model_and_off_starts_it(project: Path, fake_sup: FakeSupervisor):
    app = create_app(project, "http://127.0.0.1:9", supervise=True)
    with TestClient(app) as c:
        assert fake_sup.bootstraps == 1                     # an ordinary launch
        c.post("/api/ui-config", json={"agent_free": True})
        assert fake_sup.stop_calls == [False]               # owned or adopted
        assert c.get("/api/llm-status").json()["mode"] == "agent-free"
        assert refused(c.post("/api/chat", data={"message": "hello"}))
        # Saying it again changes nothing.
        c.post("/api/ui-config", json={"agent_free": True})
        assert fake_sup.stop_calls == [False] and fake_sup.bootstraps == 1
        c.post("/api/ui-config", json={"agent_free": False})
        assert fake_sup.bootstraps == 2 and fake_sup.stop_calls == [False]
        assert c.get("/api/llm-status").json()["mode"] == "off"


def test_turning_it_off_starts_through_the_startup_choice(free: Path, monkeypatch):
    """The real supervisor: off → `bootstrap()` → `_resolve_startup_choice` →
    `_launch`, recorded instead of spawning anything."""
    launched: list[tuple[str, int]] = []

    async def nothing_listening(self):
        return None

    monkeypatch.setattr(_supervisor.LlamaSupervisor, "_probe_existing", nothing_listening)
    monkeypatch.setattr(_supervisor, "_resolve_startup_choice", lambda: ("g40-04", 4096))
    monkeypatch.setattr(_supervisor.LlamaSupervisor, "_launch",
                        lambda self, cute, ctx: launched.append((cute, ctx)))
    monkeypatch.setattr(_supervisor.LlamaSupervisor, "_start_healthwatch", lambda self: None)
    app = create_app(free, "http://127.0.0.1:9", supervise=True)
    with TestClient(app) as c:
        assert launched == []
        assert c.post("/api/ui-config", json={"agent_free": False}).status_code == 200
        assert launched == [("g40-04", 4096)]
