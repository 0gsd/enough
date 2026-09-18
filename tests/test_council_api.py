"""The `/api/council*` routes, reached the way the canvas reaches them.

No LLM and no network: every turn goes through the `council.run_council_turn`
seam. Isolation is set explicitly (HOME, the `ENOUGH_*` seams and
`broker.CONFIG_PATH`) so this file behaves identically with or without
conftest's autouse fixture.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import composure as C
from enough import council as K
from enough.server import create_app

REL = "rness/io/composure/round-table.comp"


@pytest.fixture(autouse=True)
def _clean_runtime():
    K.reset_runtime()
    yield
    K.reset_runtime()


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"),
                     ("ENOUGH_CACHEAWL_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_READVISORS_ROOT", "readvisors-global"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    (proj / "rness" / "readvisors").mkdir(parents=True)
    (proj / "notes").mkdir(parents=True)
    return proj


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


TRIO = [{"id": "chief", "kind": "chief", "name": "Ed"},
        {"id": "rv:skeptic", "kind": "readvisor", "name": "Nadia"},
        {"id": "user", "kind": "user", "name": "you"}]


def replies(text: str = "A statement about the thing.", *, seen=None):
    async def _run(messages, on_token=None, **kw):
        if seen is not None:
            seen.append(messages)
        if on_token is not None:
            await on_token(text)
        return text
    return _run


@pytest.fixture(autouse=True)
def _seam(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", replies())
    # A roomy window so the API tests exercise the routes, not the fold.
    monkeypatch.setattr(K, "resolve_n_ctx", lambda **kw: 131072)


def setup(client: TestClient, **over) -> dict:
    body = {"path": REL, "title": "Round table",
            "input": "Should chapter four move to the front?",
            "parameters": "Two rounds.", "constraints": "No rewriting.",
            "output": {"kind": "answer"}, "participants": TRIO,
            "max_rounds": 2}
    body.update(over)
    r = client.post("/api/council/setup", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def convene(client: TestClient) -> dict:
    r = client.post("/api/council/convene", json={"path": REL})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

def test_setup_creates_the_council_and_moves_setup_to_ready(
        client: TestClient, project: Path):
    state = setup(client)
    assert (project / REL).is_file()
    meta = state["council"]
    assert meta["status"] == "ready"
    assert meta["input"].startswith("Should chapter four")
    assert [p["id"] for p in meta["participants"]] == \
        ["chief", "rv:skeptic", "user"]
    assert meta["participants"][1]["tint"] in K.READVISOR_TINTS
    assert state["next"] == "chief"
    assert state["budget"]["speakers"] == 2
    assert state["budget"]["share"] == 131072 // 2
    # The brief module the council form ships with is still on top.
    comp = C.load(project / REL)
    assert comp.council["status"] == "ready"
    assert comp.modules[0].title == "Brief"


def test_setup_defaults_the_participants_to_chief_plus_enabled_readvisors(
        client: TestClient, project: Path):
    d = project / "rness" / "readvisors" / "open-skeptic"
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENT.md").write_text("# Nadia the Skeptic\n\nbody\n", encoding="utf-8")
    (d / "MOTIVATION.md").write_text("motive\n", encoding="utf-8")
    rows = client.get("/api/council/participants").json()["participants"]
    kinds = [p["kind"] for p in rows]
    assert kinds[0] == "chief" and kinds[-1] == "user"
    rv = [p for p in rows if p["kind"] == "readvisor"]
    assert rv and rv[0]["name"] == "Nadia the Skeptic"
    assert rv[0]["folder"] == "open-skeptic"
    r = client.post("/api/council/setup", json={"path": REL, "input": "x"})
    assert r.status_code == 200, r.text
    assert len(r.json()["council"]["participants"]) == len(rows)


def test_setup_refuses_an_existing_document_without_overwrite(
        client: TestClient, project: Path):
    (project / "notes" / "out.md").write_text("mine\n", encoding="utf-8")
    r = client.post("/api/council/setup", json={
        "path": REL, "input": "x", "participants": TRIO,
        "output": {"kind": "document", "path": "notes/out.md"}})
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    assert not (project / REL).exists()      # refused before anything was written
    ok = client.post("/api/council/setup", json={
        "path": REL, "input": "x", "participants": TRIO, "overwrite": True,
        "output": {"kind": "document", "path": "notes/out.md"}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["council"]["output"]["overwrite"] is True


def test_setup_refuses_a_traversing_output_path(client: TestClient):
    r = client.post("/api/council/setup", json={
        "path": REL, "input": "x", "participants": TRIO,
        "output": {"kind": "document", "path": "../escape.md"}})
    assert r.status_code == 400
    assert "output path" in r.json()["detail"]


def test_state_404s_for_a_path_that_is_not_a_council(client: TestClient):
    r = client.get("/api/council/state", params={"path": REL})
    assert r.status_code == 404
    bad = client.get("/api/council/state", params={"path": "notes/out.md"})
    assert bad.status_code == 400 and "must end in" in bad.json()["detail"]


# ---------------------------------------------------------------------------
# driving
# ---------------------------------------------------------------------------

def test_next_runs_one_turn_and_round_runs_the_rotation(
        client: TestClient, project: Path):
    setup(client)
    convene(client)
    one = client.post("/api/council/next", json={"path": REL})
    assert one.status_code == 200, one.text
    assert one.json()["spoke"] == "Ed" and one.json()["turn"] == 1
    assert one.json()["next_name"] == "Nadia"
    rnd = client.post("/api/council/round", json={"path": REL})
    assert rnd.status_code == 200, rnd.text
    # The rotation had one slot left when `/round` started, so a round here
    # means "finish this round" — the documented semantics.
    assert rnd.json()["spoke"] == ["Nadia"]
    assert rnd.json()["council"]["round"] == 1
    said = [m for m in C.load(project / REL).modules if m.speaker]
    assert [m.speaker for m in said] == ["Ed", "Nadia"]
    assert all(m.locked for m in said)


def test_a_ready_council_can_be_driven_without_an_explicit_convene(
        client: TestClient):
    """`ready` is runnable — pressing `next turn` on a freshly set-up council
    should speak, not lecture. Only `setup` and `concluded` refuse."""
    setup(client)
    r = client.post("/api/council/next", json={"path": REL})
    assert r.status_code == 200, r.text
    assert r.json()["spoke"] == "Ed"


def test_a_council_in_setup_cannot_be_driven(client: TestClient, project: Path):
    setup(client)
    comp, meta = K.Council(project / REL, project_dir=project,
                           rel_path=REL).load()
    meta["status"] = "setup"
    C.apply_ops(project / REL, None,
                [{"op": "set_council", "council": meta}], source="council",
                rel_path=REL)
    r = client.post("/api/council/next", json={"path": REL})
    assert r.status_code == 409 and "not been set up" in r.json()["detail"]


def test_run_goes_to_max_rounds_in_the_background(client: TestClient,
                                                  project: Path):
    setup(client, max_rounds=2)
    convene(client)
    r = client.post("/api/council/run", json={"path": REL})
    assert r.status_code == 200 and r.json()["running"] is True
    _settle(client)
    state = client.get("/api/council/state", params={"path": REL}).json()
    assert state["council"]["round"] == 2
    assert state["council"]["turn"] == 4            # 2 speakers x 2 rounds
    assert state["council"]["status"] == "ready"    # it stopped itself
    assert state["running"] is False


def test_pause_stops_a_run_and_leaves_it_resumable(client: TestClient,
                                                   project: Path,
                                                   monkeypatch):
    gate = asyncio.Event()

    async def slow(messages, on_token=None, **kw):
        await gate.wait()
        return "eventually"
    monkeypatch.setattr(K, "run_council_turn", slow)
    setup(client, max_rounds=5)
    convene(client)
    client.post("/api/council/run", json={"path": REL})
    gate.set()
    paused = client.post("/api/council/pause", json={"path": REL})
    assert paused.status_code == 200
    assert paused.json()["council"]["status"] == "paused"
    assert paused.json()["running"] is False
    monkeypatch.setattr(K, "run_council_turn", replies("back at it"))
    again = client.post("/api/council/convene", json={"path": REL})
    assert again.json()["council"]["status"] == "running"
    nxt = client.post("/api/council/next", json={"path": REL})
    assert nxt.status_code == 200
    # Everything said before the pause is still on the canvas.
    said = [m for m in C.load(project / REL).modules if m.speaker]
    assert len(said) == int(nxt.json()["council"]["turn"])


def test_say_commits_at_once_when_nothing_is_streaming(client: TestClient,
                                                       project: Path):
    setup(client)
    convene(client)
    client.post("/api/council/next", json={"path": REL})
    r = client.post("/api/council/say", json={"path": REL,
                                              "text": "One thing first."})
    assert r.status_code == 200, r.text
    assert r.json()["queued"] is False
    m = C.load(project / REL).module(r.json()["module"])
    assert m.speaker == "you" and m.speaker_kind == "user"
    assert m.bg == K.USER_TINT
    # The interjection did not consume the rotation.
    assert r.json()["next_name"] == "Nadia"
    assert r.json()["council"]["queue"] == []
    blank = client.post("/api/council/say", json={"path": REL, "text": "  "})
    assert blank.status_code == 400


def test_say_queues_while_a_turn_is_streaming(client: TestClient,
                                              project: Path, monkeypatch):
    """The race the footer composer actually has: a statement typed while a
    turn is mid-stream is queued and takes the next slot, never lost."""
    setup(client)
    convene(client)
    K._IN_FLIGHT.add(str((project / REL).resolve()))
    r = client.post("/api/council/say", json={"path": REL, "text": "hold on"})
    assert r.status_code == 200 and r.json()["queued"] is True
    state = client.get("/api/council/state", params={"path": REL}).json()
    assert state["council"]["queue"] == [{"text": "hold on"}]
    assert state["next"] == "user"           # the queue takes the next slot
    K._IN_FLIGHT.clear()
    nxt = client.post("/api/council/next", json={"path": REL})
    assert nxt.json()["spoke"] == "you"
    assert nxt.json()["council"]["queue"] == []
    assert nxt.json()["next_name"] == "Ed"   # the rotation was not consumed


# ---------------------------------------------------------------------------
# Lock exclusion, both directions
# ---------------------------------------------------------------------------

def test_a_council_control_is_409_while_the_chat_is_mid_turn(
        client: TestClient, project: Path):
    setup(client)
    convene(client)
    app_session = _session(client)
    asyncio.get_event_loop_policy()
    _hold(app_session)
    try:
        for route in ("next", "round", "run", "conclude"):
            r = client.post(f"/api/council/{route}", json={"path": REL})
            assert r.status_code == 409, (route, r.text)
            assert "answering in the chat" in r.json()["detail"]
        # ...but the user can still queue a statement and read the state.
        assert client.post("/api/council/say",
                           json={"path": REL, "text": "meanwhile"}
                           ).status_code == 200
        assert client.get("/api/council/state",
                          params={"path": REL}).status_code == 200
    finally:
        _release(app_session)


def test_chat_is_refused_politely_while_a_council_turn_streams(
        client: TestClient, project: Path):
    setup(client)
    K._IN_FLIGHT.add(str((project / REL).resolve()))
    try:
        r = client.post("/api/chat", data={"message": "hello?"})
        assert r.status_code == 200
        assert "a council is speaking right now" in r.text
        assert 'id="current-response"' not in r.text   # no turn was started
        assert "hello?" in r.text                      # their words are kept
    finally:
        K._IN_FLIGHT.clear()


def test_a_second_council_control_is_409_while_a_turn_streams(
        client: TestClient, project: Path):
    setup(client)
    convene(client)
    K._IN_FLIGHT.add(str((project / REL).resolve()))
    try:
        r = client.post("/api/council/next", json={"path": REL})
        assert r.status_code == 409 and "already streaming" in r.json()["detail"]
    finally:
        K._IN_FLIGHT.clear()


# ---------------------------------------------------------------------------
# conclude
# ---------------------------------------------------------------------------

def test_conclude_answer_writes_a_final_ink_module_and_exports(
        client: TestClient, project: Path):
    setup(client)
    convene(client)
    client.post("/api/council/next", json={"path": REL})
    r = client.post("/api/council/conclude", json={"path": REL})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["output"] == "answer" and body["document"] is None
    comp = C.load(project / REL)
    final = comp.module(body["module"])
    assert final.bg == K.CONCLUSION_TINT
    assert final.title.endswith("conclusion") and final.speaker == "Ed"
    assert comp.council["status"] == "concluded"
    assert comp.council["transcript"] == body["transcript"]
    text = (project / body["transcript"]).read_text(encoding="utf-8")
    assert "## The brief" in text and "## Participants" in text
    # A concluded council refuses everything but reading.
    assert client.post("/api/council/next",
                       json={"path": REL}).status_code == 409
    assert client.post("/api/council/conclude",
                       json={"path": REL}).status_code == 409
    assert client.post("/api/council/setup",
                       json={"path": REL, "input": "again"}).status_code == 409


def test_conclude_document_writes_through_the_write_file_door(
        client: TestClient, project: Path, monkeypatch):
    monkeypatch.setattr(K, "run_council_turn",
                        replies("# The decision\n\nMove it.\n"))
    setup(client, output={"kind": "document", "path": "notes/out.md"})
    convene(client)
    r = client.post("/api/council/conclude", json={"path": REL})
    assert r.status_code == 200, r.text
    assert r.json()["document"] == "notes/out.md"
    assert (project / "notes" / "out.md").read_text() == \
        "# The decision\n\nMove it.\n"
    # The document is linked from the council that produced it.
    comp = C.load(project / REL)
    link = [m for m in comp.modules if m.type == "doc"]
    assert link and link[0].href == "notes/out.md"
    assert "`notes/out.md`" in (project / r.json()["transcript"]).read_text()


def test_conclude_document_refuses_to_clobber_without_a_confirm(
        client: TestClient, project: Path):
    setup(client, output={"kind": "document", "path": "notes/out.md"})
    convene(client)
    (project / "notes" / "out.md").write_text("written since setup\n",
                                              encoding="utf-8")
    r = client.post("/api/council/conclude", json={"path": REL})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert (project / "notes" / "out.md").read_text() == "written since setup\n"
    ok = client.post("/api/council/conclude", json={"path": REL,
                                                    "overwrite": True})
    assert ok.status_code == 200, ok.text
    assert (project / "notes" / "out.md").read_text() != "written since setup\n"


def test_conclude_refuses_the_composure_output_until_0_4_0(
        client: TestClient, project: Path):
    setup(client, output={"kind": "composure", "form": "scaffold"})
    convene(client)
    r = client.post("/api/council/conclude", json={"path": REL})
    assert r.status_code == 501
    assert "lands in 0.4.0" in r.json()["detail"]
    # Nothing was spent: the council is still runnable.
    state = client.get("/api/council/state", params={"path": REL}).json()
    assert state["council"]["status"] == "running"
    assert state["council"]["turn"] == 0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _Held:
    """A stand-in for `asyncio.Lock` that is always taken. The guard calls
    exactly one method on it, and faking that is steadier than reaching into
    a real lock's private state from another thread."""

    def locked(self) -> bool:
        return True


def _session(client: TestClient):
    return client.app.state.session


def _hold(session) -> None:
    session._real_lock = session.generation_lock
    session.generation_lock = _Held()


def _release(session) -> None:
    session.generation_lock = session._real_lock


def _settle(client: TestClient, tries: int = 200) -> None:
    """Let the background `/run` task finish. The TestClient's portal runs the
    loop, so a state read is what actually gives it a slice."""
    for _ in range(tries):
        state = client.get("/api/council/state", params={"path": REL}).json()
        if not state["running"]:
            return
    raise AssertionError("the background run never finished")
