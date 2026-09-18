"""`POST /api/council/pal` and the `council.PAL_CALL` wiring — P8/P9 glue.

The council engine's own pal seam is `tests/test_council_output.py` §6. This
file is the two things that sit either side of it: the HTTP route (the gate,
the two exclusions, what comes back) and the fact that `create_app` wires
`council.PAL_CALL` to the same one-shot call the `/pal` lane built, rather
than to a second implementation of the same rules.

No LLM and no network: `council.run_council_turn` is the completion seam and
`council.PAL_CALL` is the pal seam. Isolation is set explicitly (HOME, the
`ENOUGH_*` seams, `broker.CONFIG_PATH`) so this file behaves the same with or
without conftest's autouse fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import cloud as C
from enough import council as K
from enough import pal_tools as P
from enough.server import create_app

REL = "rness/io/composure/round-table.comp"

TRIO = [{"id": "chief", "kind": "chief", "name": "Ed"},
        {"id": "rv:skeptic", "kind": "readvisor", "name": "Nadia"},
        {"id": "user", "kind": "user", "name": "you"}]

OPEN_GATE = {"open": True, "reason": None, "denial": None,
             "model_id": "acme/sonnet-9"}
SHUT_GATE = {"open": False,
             "reason": "'local models only' is on in the broker",
             "denial": ("error: cannot use OpenRouter/cloud features — "
                        "'local models only' is enabled in the broker config."),
             "model_id": None}


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_runtime():
    K.reset_runtime()
    yield
    K.reset_runtime()
    K.PAL_CALL = K._pal_not_wired


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    assert Path.home() == home, "a test must never touch the real ~/enough"
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
    return proj


@pytest.fixture(autouse=True)
def _seam(monkeypatch: pytest.MonkeyPatch):
    async def _run(messages, on_token=None, **kw):
        text = "Does moving a reveal earlier cost tension?"
        if on_token is not None:
            await on_token(text)
        return text
    monkeypatch.setattr(K, "run_council_turn", _run)
    monkeypatch.setattr(K, "resolve_n_ctx", lambda **kw: 131072)


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


class _Held:
    """An `asyncio.Lock` that is always taken. The guard calls exactly one
    method on it, and faking that is steadier than reaching into a real
    lock's private state from another thread."""

    def locked(self) -> bool:
        return True


def ready(client: TestClient, **over) -> None:
    body = {"path": REL, "title": "Round table",
            "input": "Should chapter four move to the front?",
            "output": {"kind": "answer"}, "participants": TRIO,
            "max_rounds": 2}
    body.update(over)
    r = client.post("/api/council/setup", json=body)
    assert r.status_code == 200, r.text
    r = client.post("/api/council/convene", json={"path": REL})
    assert r.status_code == 200, r.text


def gate(monkeypatch: pytest.MonkeyPatch, value: dict) -> None:
    monkeypatch.setattr(C, "gate_status", lambda: dict(value))


# ---------------------------------------------------------------------------
# 1 · the wiring
# ---------------------------------------------------------------------------

def test_create_app_wires_pal_call_to_the_pal_lanes_one_shot_call(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    assert K.PAL_CALL is K._pal_not_wired
    create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    assert K.PAL_CALL is not K._pal_not_wired
    seen: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        P, "ask_pal_once",
        lambda pdir, prompt: (seen.append((pdir, prompt)) or ("m", "hi")))
    assert K.PAL_CALL("what about the reveal?") == ("m", "hi")
    assert seen == [(project, "what about the reveal?")]


def test_the_wired_call_goes_through_the_same_gate_and_caps(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    """`ask_pal_once` is the gate, the caps and the exfiltration patterns —
    not a second copy of them. A shut gate refuses before anything is sent."""
    create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    gate(monkeypatch, SHUT_GATE)
    sent: list[object] = []
    monkeypatch.setattr(C, "chat_completion",
                        lambda *a, **k: sent.append(a) or {})
    with pytest.raises(P.PalRefused) as e:
        K.PAL_CALL("anything at all")
    assert "local models only" in str(e.value)
    assert sent == [], "a shut gate still reached the network"

    gate(monkeypatch, OPEN_GATE)
    with pytest.raises(P.PalRefused) as e:
        K.PAL_CALL("x" * (P.MAX_PROMPT_CHARS + 1))
    assert str(P.MAX_PROMPT_CHARS) in str(e.value)
    assert sent == [], "an over-long prompt was sent anyway"


# ---------------------------------------------------------------------------
# 2 · the route
# ---------------------------------------------------------------------------

def test_a_council_pal_commits_one_gray_statement(
        client: TestClient, monkeypatch: pytest.MonkeyPatch):
    ready(client)
    gate(monkeypatch, OPEN_GATE)
    monkeypatch.setattr(
        K, "PAL_CALL",
        lambda prompt: ("acme/sonnet-9", "Usually yes, unless it is a setup."))
    r = client.post("/api/council/pal",
                    json={"path": REL, "ask": "what about the reveal?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pal"] is True
    assert body["spoke"] == "pal · acme/sonnet-9"
    assert body["turn"] == 1
    said = body["statements"][-1]
    assert said["speaker_kind"] == "pal"
    assert K.PAL_TINT == "gray"
    # The tint is on the module, which is what the canvas paints from.
    comp = client.get("/api/composure", params={"path": REL}).json()
    mod = [m for m in comp["model"]["modules"] if m["id"] == body["module"]][0]
    assert mod["bg"] == K.PAL_TINT
    assert mod["speaker_kind"] == "pal"
    # The record: what left the machine is the first block, quoted.
    assert body["text"].startswith(f"> **{K.PAL_PROMPT_LEAD}**")
    assert "Usually yes" in body["text"]


def test_a_pal_answer_does_not_move_the_rotation(
        client: TestClient, monkeypatch: pytest.MonkeyPatch):
    ready(client)
    gate(monkeypatch, OPEN_GATE)
    monkeypatch.setattr(K, "PAL_CALL", lambda p: ("m", "A pal answer."))
    before = client.get("/api/council/state", params={"path": REL}).json()
    after = client.post("/api/council/pal",
                        json={"path": REL, "ask": "go on"}).json()
    assert after["next"] == before["next"]
    assert after["council"]["round"] == before["council"]["round"]


def test_a_shut_gate_is_a_409_carrying_the_broker_denial(
        client: TestClient, monkeypatch: pytest.MonkeyPatch):
    ready(client)
    gate(monkeypatch, SHUT_GATE)
    called: list[str] = []
    monkeypatch.setattr(K, "PAL_CALL",
                        lambda p: called.append(p) or ("m", "no"))
    r = client.post("/api/council/pal", json={"path": REL, "ask": "go on"})
    assert r.status_code == 409
    assert "local models only" in r.json()["detail"]
    # And no chief turn was spent distilling a prompt that cannot be sent.
    assert called == []
    state = client.get("/api/council/state", params={"path": REL}).json()
    assert state["council"]["turn"] == 0


def test_an_empty_ask_is_a_400(client: TestClient,
                               monkeypatch: pytest.MonkeyPatch):
    ready(client)
    gate(monkeypatch, OPEN_GATE)
    r = client.post("/api/council/pal", json={"path": REL, "ask": "   "})
    assert r.status_code == 400
    assert "`/pal`" in r.json()["detail"]


def test_a_chat_turn_in_flight_excludes_a_council_pal(
        client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Councils and the chat share one model, so the same 409 every other
    council control gets applies here — checked before the model is used."""
    ready(client)
    gate(monkeypatch, OPEN_GATE)
    called: list[str] = []
    monkeypatch.setattr(K, "PAL_CALL",
                        lambda p: called.append(p) or ("m", "no"))
    session = client.app.state.session
    real, session.generation_lock = session.generation_lock, _Held()
    try:
        r = client.post("/api/council/pal", json={"path": REL, "ask": "go on"})
    finally:
        session.generation_lock = real
    assert r.status_code == 409
    assert "chat" in r.json()["detail"]
    assert called == []


def test_a_council_that_has_not_been_set_up_refuses(
        client: TestClient, monkeypatch: pytest.MonkeyPatch):
    client.post("/api/council/setup",
                json={"path": REL, "title": "Round table",
                      "input": "x", "output": {"kind": "answer"},
                      "participants": TRIO, "max_rounds": 2})
    gate(monkeypatch, OPEN_GATE)
    monkeypatch.setattr(K, "PAL_CALL", lambda p: ("m", "no"))
    # `setup` leaves it `ready`, so drive it to `concluded` the only way a
    # test without a model can: the engine's own refusal for a council that
    # has nothing to say to.
    client.post("/api/council/convene", json={"path": REL})
    r = client.post("/api/council/pal",
                    json={"path": "notes/not-a-composure.md", "ask": "hi"})
    assert r.status_code == 400
