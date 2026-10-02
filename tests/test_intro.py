"""The brief introduction to enough (0.4.1): the text, `/api/intro`, the chat's
no-model-call match, the `show_intro` tool, and the empty hint it replaces.

Scratch rule as everywhere: `HOME` and every `ENOUGH_*` seam in `tmp_path`
(conftest), `broker.CONFIG_PATH` re-pointed by hand, and an assertion that
home really is scratch before anything runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import intro as I
from enough import prompt as prompt_mod
from enough import server
from enough import skeleton
from enough import tools as T
from enough.server import Session, create_app

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    yield proj
    I.set_language_source(None)


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def turns(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    started: list[str] = []

    async def _nothing() -> None:
        return None

    def _run(session, message, *, pal=False, log_user=None):
        started.append(message)
        return _nothing()
    monkeypatch.setattr(server, "_run_turn", _run)
    return started


# ---------------------------------------------------------------------------
# The text
# ---------------------------------------------------------------------------

def test_the_english_source_ships_and_is_pure_content():
    text = (REPO / "defaults" / "intro.md").read_text(encoding="utf-8")
    assert text.startswith("**enough, briefly.**")
    assert I.text_for("en") == text.strip()


def test_a_missing_translation_falls_back_to_english(tmp_path: Path, monkeypatch):
    assert I.path_for("fr") == I.english_path() or I.path_for("fr").is_file()
    assert I.path_for("xx") == I.english_path()
    assert I.path_for("../../etc") == I.english_path()
    fake_static = tmp_path / "static"
    (fake_static / "i18n" / "fr").mkdir(parents=True)
    (fake_static / "i18n" / "fr" / "intro.md").write_text("**enough, en bref.**\n", encoding="utf-8")
    monkeypatch.setattr(I, "STATIC_DIR", fake_static)
    assert I.text_for("fr") == "**enough, en bref.**"
    assert I.text_for("de") == I.text_for("en")
    assert I.is_intro_text("**enough, en bref.**")


def test_api_intro(client: TestClient):
    r = client.get("/api/intro?lang=ja")
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == I.text_for("ja") and body["lang"] == "ja"
    assert body["text"] != I.text_for("en")     # the shipped translation
    assert client.get("/api/intro").json()["lang"] == "en"
    assert client.get("/api/intro?lang=../secrets").json()["lang"] == "en"


# ---------------------------------------------------------------------------
# The match
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    "what can you do", "What can you do?", "  WHAT CAN YOU DO?!  ", "what can enough do?",
    "What is enough?", "what is this?", "Help", "help!", "/intro", "/INTRO",
])
def test_matched_phrases(message: str):
    assert I.is_intro_request(message, conversation_empty=True)


@pytest.mark.parametrize("message", [
    "what can you do with this file?", "help me outline chapter two", "hello",
    "what is this paragraph about?", "/introduce", "can you help",
])
def test_whole_message_only(message: str):
    assert not I.is_intro_request(message, conversation_empty=True)


def test_phrases_count_only_in_an_empty_conversation_but_intro_always():
    assert not I.is_intro_request("what is this?", conversation_empty=False)
    assert not I.is_intro_request("help", conversation_empty=False)
    assert I.is_intro_request("/intro", conversation_empty=False)


def test_the_chat_answers_without_a_model_turn(client: TestClient, turns: list[str]):
    session = client.app.state.session
    html = client.post("/api/chat", data={"message": "What can you do?"}).text
    assert turns == []
    assert 'class="msg user"' in html and "What can you do?" in html
    assert 'class="msg assistant intro" data-markdown="intro"' in html
    assert f'<div class="role">{prompt_mod.chief_name()}</div>' in html
    assert "enough, briefly." in html
    assert 'id="current-response"' not in html
    # Persisted like a turn: the model sees it next time, a reload redraws it.
    assert session.history == [{"role": "user", "content": "What can you do?"},
                               {"role": "assistant", "content": I.text_for()}]
    page = server._render_turn_from_history(session.history)
    assert 'data-markdown="intro"' in page and "What can you do?" in page
    # ...and the same question again is now an ordinary message.
    client.post("/api/chat", data={"message": "what can you do?"})
    assert turns == ["what can you do?"]
    client.post("/api/chat", data={"message": "/intro"})
    assert turns == ["what can you do?"]


def test_a_running_turn_is_never_interleaved(client: TestClient, turns: list[str]):
    session = client.app.state.session

    async def hold_and_post():
        async with session.generation_lock:
            return await asyncio.to_thread(
                client.post, "/api/chat", data={"message": "help"})
    # The lock lives on the app's loop; take it from the test client's portal.
    client.portal.call(hold_and_post)
    assert turns == ["help"]
    assert session.history == []


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

def _call(text: str) -> T.ToolCall:
    calls = T.parse_tool_calls(text)
    assert len(calls) == 1
    return calls[0]


def test_show_intro_is_registered_and_emits_the_bubble(project: Path):
    assert "show_intro" in T._DISPATCH
    result = T.execute(project, _call('<tool name="show_intro">\n</tool>'))
    assert result.ok and result.body == I.RESULT_SHOWN
    payload = result.side_effects[I.SIDE_EFFECT]
    assert payload["text"] == I.text_for()
    assert payload["html"] == I.bubble(I.text_for(), prompt_mod.chief_name())
    # A reload draws the same bubble from the tool result in the history.
    html = server._render_turn_from_history([{"role": "user", "content": result.render()}])
    assert html == payload["html"]


def test_show_intro_side_effect_reaches_the_stream(project: Path):
    session = Session(project_dir=project, llm_url="http://127.0.0.1:1/v1")
    q: asyncio.Queue = asyncio.Queue()
    session.subscribers.append(q)
    sink: list = []
    asyncio.run(server._handle_tool(session, _call('<tool name="show_intro"></tool>'), sink))
    events = []
    while not q.empty():
        events.append(q.get_nowait()["event"])
    assert I.SIDE_EFFECT in events
    assert session.history[-1]["content"].startswith('<tool_result name="show_intro"')


def test_show_intro_without_a_text_says_so(project: Path, monkeypatch):
    monkeypatch.setattr(I, "INSTALL_ROOT", project / "nowhere")
    result = T.execute(project, _call('<tool name="show_intro"></tool>'))
    assert not result.ok and "intro.md is missing" in result.body
    assert not result.side_effects


# ---------------------------------------------------------------------------
# The empty hint, and the first-conversation offer
# ---------------------------------------------------------------------------

def test_the_empty_hint_is_neutral():
    assert server._default_empty_hint() == (
        '<div class="empty-hint" id="empty-hint">awaiting your first message.</div>')


def test_agent_md_offers_the_introduction():
    text = (REPO / "defaults" / "AGENT.md").read_text(encoding="utf-8")
    first = text.split("## First conversation", 1)[1]
    assert "want a brief introduction to enough?" in first
    assert "`show_intro`" in first
    for kept in ("What kind of work will they do", "personality and communication style",
                 "What tools or skills", "Which readvisors"):
        assert kept in first, kept


# ---------------------------------------------------------------------------
# Replies with no turn re-enable the composer
# ---------------------------------------------------------------------------
#
# The composer disables itself when the form posts and re-enables only on the
# `done` SSE event (index.html: `htmx:beforeRequest` / `es 'done'`). A reply
# that starts no turn must send that `done` itself.

@pytest.fixture()
def emitted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    events: list[str] = []
    session = client.app.state.session

    async def record(event, data):
        events.append(event)
    monkeypatch.setattr(session, "emit", record)
    return events


def _shut_gate(monkeypatch):
    from enough import cloud
    monkeypatch.setattr(cloud, "gate_status", lambda: {
        "open": False, "denial": "the cloud slot is off.", "reason": "toggle", "model_id": None})


def _open_gate(monkeypatch):
    from enough import cloud
    monkeypatch.setattr(cloud, "gate_status", lambda: {
        "open": True, "denial": None, "reason": None, "model_id": "m"})


@pytest.mark.parametrize("message", ["help", "/intro"])
def test_the_intro_reply_sends_done(client, turns, emitted, message):
    client.post("/api/chat", data={"message": message})
    assert emitted == ["done"] and turns == []


def test_a_pal_denial_sends_done(client, turns, emitted, monkeypatch):
    _shut_gate(monkeypatch)
    html = client.post("/api/chat", data={"message": "/pal anything"}).text
    assert "the cloud slot is off." in html
    assert emitted == ["done"] and turns == []


def test_a_bare_pal_sends_done(client, turns, emitted, monkeypatch):
    _open_gate(monkeypatch)
    html = client.post("/api/chat", data={"message": "/pal"}).text
    assert "needs a question" in html
    assert emitted == ["done"] and turns == []


def test_a_council_in_flight_reply_sends_done(client, turns, emitted, monkeypatch):
    from enough import council
    monkeypatch.setattr(council, "turn_in_flight", lambda: True)
    session = client.app.state.session

    async def post_while_council_holds_the_lock():
        async with session.generation_lock:
            return await asyncio.to_thread(
                client.post, "/api/chat", data={"message": "hello"})
    html = client.portal.call(post_while_council_holds_the_lock).text
    assert "a council is speaking right now" in html
    assert emitted == ["done"] and turns == []


def test_an_ordinary_message_sends_no_done_of_its_own(client, turns, emitted):
    client.post("/api/chat", data={"message": "hello there"})
    assert turns == ["hello there"] and emitted == []
