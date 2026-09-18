"""`/pal` — the command, the turn, the tool, and the record it leaves.

No network: `cloud.chat_completion` is replaced at the seam in every test
that reaches it, and `cloud.status_snapshot` stands in for the keyring so the
gate can be opened and shut without one. Isolation is set explicitly (HOME,
the `ENOUGH_*` seams and `broker.CONFIG_PATH`) so this file behaves
identically with or without conftest's autouse fixture — and the `Path.home()`
assertion in the fixture is the one that actually stops a run from filing
cloud-cache entries in the developer's real `~/enough`.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import cloud
from enough import pal_tools as P
from enough import prompt as prompt_mod
from enough import server
from enough import skeleton
from enough import tools as T
from enough.server import Session, create_app


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_runtime():
    P.reset_runtime()
    yield
    P.reset_runtime()


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
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    return proj


def set_toggle(key: str, value: bool) -> None:
    cfg = broker.load_config()
    cfg[key] = value
    broker.save_config(cfg)


MODEL = "anthropic/claude-sonnet-4.5"


def open_gate(monkeypatch: pytest.MonkeyPatch, *, model: str = MODEL) -> None:
    """Everything the gate asks about, answered yes. `status_snapshot` is the
    seam because the real one reads the OS keyring."""
    set_toggle("local_models_only", False)
    monkeypatch.setattr(cloud, "status_snapshot", lambda: {
        "enabled": True, "model_id": model, "key_present": True,
        "last_verified_at": "2026-09-18T00:00:00Z", "last_verified_ok": True,
        "last_verified_model": model, "last_error": None,
    })


def shut_gate(monkeypatch: pytest.MonkeyPatch, why: str = "toggle") -> None:
    if why == "toggle":
        set_toggle("local_models_only", True)
        return
    set_toggle("local_models_only", False)
    snap = {"enabled": True, "model_id": MODEL, "key_present": why != "key",
            "last_verified_at": None, "last_verified_ok": why != "unhealthy",
            "last_verified_model": None,
            "last_error": "out of credits" if why == "unhealthy" else None}
    monkeypatch.setattr(cloud, "status_snapshot", lambda: snap)


def answers(text: str = "The pal's answer.", *, seen: list | None = None):
    def _completion(messages, **kw):
        if seen is not None:
            seen.append({"messages": messages, **kw})
        return {"id": "gen-1", "model": MODEL,
                "choices": [{"message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 22,
                          "total_tokens": 33}}
    return _completion


def call_of(body: str):
    calls = T.parse_tool_calls(body)
    assert calls, body
    return calls[-1]


def ask(prompt_text: str = "What changed in the spec?"):
    return call_of(f'<tool name="ask_pal">\n<prompt>{prompt_text}</prompt>\n</tool>')


# ---------------------------------------------------------------------------
# 1. The command
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message,expected", [
    ("/pal what is new in the act?", "what is new in the act?"),
    ("/PAL shout", "shout"),
    ("/Pal  spaced  out ", "spaced  out"),
    ("   /pal leading whitespace", "leading whitespace"),
    ("/pal\nthe question on its own line", "the question on its own line"),
    ("/pal", ""),
    ("/pal   ", ""),
])
def test_the_command_is_recognized(message: str, expected: str):
    assert P.strip_command(message) == expected


@pytest.mark.parametrize("message", [
    "/palette red",
    "/pals are friends",
    "/paladin",
    "tell me about /pal",
    "please /pal this",
    "//pal x",
    "pal what is new?",
    "",
])
def test_the_command_is_only_the_command(message: str):
    """`/palette` is a word somebody typed. The token has to be first, and it
    has to end where a token ends."""
    assert P.strip_command(message) is None


def test_a_multi_line_question_survives_the_strip():
    body = "/pal line one\nline two\n\nline four"
    assert P.strip_command(body) == "line one\nline two\n\nline four"


# ---------------------------------------------------------------------------
# 2. The turn window
# ---------------------------------------------------------------------------

def test_the_flag_is_set_for_the_window_and_cleared_after():
    session = Session(project_dir=Path("/nowhere"), llm_url="http://x")
    assert not P.turn_active() and not session.pal_turn
    with P.pal_turn(session) as state:
        assert P.turn_active() and session.pal_turn
        assert isinstance(state, P.PalTurn) and not state.spent
    assert not P.turn_active() and not session.pal_turn


def test_the_flag_is_cleared_when_the_body_raises():
    session = Session(project_dir=Path("/nowhere"), llm_url="http://x")
    with pytest.raises(RuntimeError):
        with P.pal_turn(session):
            raise RuntimeError("the model went silent")
    assert not P.turn_active() and not session.pal_turn


def test_an_inactive_window_touches_nothing():
    session = Session(project_dir=Path("/nowhere"), llm_url="http://x")
    with P.pal_turn(session, active=False) as state:
        assert state is None
        assert not P.turn_active() and not session.pal_turn


def test_the_flag_is_cleared_when_the_turn_raises(project: Path,
                                                  monkeypatch):
    """The whole `_run_turn`, not just the context manager: an LLM error is
    caught and framed inside it, and the window still has to close."""
    session = Session(project_dir=project, llm_url="http://127.0.0.1:1/v1")

    async def boom(*a, **kw):
        raise RuntimeError("llm exploded")
    monkeypatch.setattr(server, "_drive_message", boom)

    asyncio.run(server._run_turn(session, "a question", pal=True))
    assert not session.pal_turn and not P.turn_active()


def test_the_flag_is_cleared_when_the_turn_is_cancelled(project: Path,
                                                        monkeypatch):
    async def forever(*a, **kw):
        await asyncio.sleep(30)
    monkeypatch.setattr(server, "_drive_message", forever)
    session = Session(project_dir=project, llm_url="http://127.0.0.1:1/v1")

    async def run():
        task = asyncio.create_task(server._run_turn(session, "q", pal=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert session.pal_turn
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert not session.pal_turn and not P.turn_active()


# ---------------------------------------------------------------------------
# 3. The tool
# ---------------------------------------------------------------------------

def test_ask_pal_is_refused_outside_a_pal_turn(project: Path, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers())
    result = T.execute(project, ask())
    assert not result.ok
    assert "/pal" in result.body
    assert "has not asked for a pal this turn" in result.body
    assert not (project / "rness" / "io" / "cloud-cache").exists()


def test_ask_pal_is_refused_when_the_gate_is_shut(project: Path, monkeypatch):
    shut_gate(monkeypatch, "toggle")
    monkeypatch.setattr(cloud, "chat_completion", answers())
    with P.pal_turn():
        result = T.execute(project, ask())
    assert not result.ok
    assert result.body == broker.denial_local_models_only()


def test_ask_pal_sends_one_prompt_and_brings_back_one_answer(project: Path,
                                                              monkeypatch):
    open_gate(monkeypatch)
    seen: list = []
    monkeypatch.setattr(cloud, "chat_completion",
                        answers("Two obligations slipped.", seen=seen))
    with P.pal_turn() as state:
        result = T.execute(project, ask("Which obligations slipped?"))

    assert result.ok and result.key == MODEL
    # Exactly what was asked, and nothing else — no system message, no
    # conversation, no project.
    assert len(seen) == 1
    assert seen[0]["messages"] == [
        {"role": "user", "content": "Which obligations slipped?"}]
    assert seen[0]["model"] == MODEL
    assert seen[0]["max_tokens"] == P.MAX_TOKENS
    # The reply reaches the model wrapped as untrusted data.
    assert "UNTRUSTED CLOUD RESPONSE" in result.body
    assert "Two obligations slipped." in result.body
    assert state.exchanges == [{"model_id": MODEL,
                                "prompt": "Which obligations slipped?",
                                "reply": "Two obligations slipped."}]


def test_the_side_effect_carries_both_halves(project: Path, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers("An answer."))
    with P.pal_turn():
        result = T.execute(project, ask("A question."))
    assert set(result.side_effects) == {P.SIDE_EFFECT}
    assert result.side_effects[P.SIDE_EFFECT] == {
        "model_id": MODEL, "prompt": "A question.", "reply": "An answer."}


def test_one_call_per_turn(project: Path, monkeypatch):
    open_gate(monkeypatch)
    calls: list = []
    monkeypatch.setattr(cloud, "chat_completion", answers(seen=calls))
    with P.pal_turn():
        first = T.execute(project, ask("One."))
        second = T.execute(project, ask("Two."))
    assert first.ok
    assert not second.ok
    assert "already asked the pal once this turn" in second.body
    assert MODEL in second.body
    assert len(calls) == 1, "the second call reached the network"


def test_a_failed_call_does_not_spend_the_turn(project: Path, monkeypatch):
    """A network error is not consent spent. The model gets to try again."""
    open_gate(monkeypatch)
    attempts: list = []

    def flaky(messages, **kw):
        attempts.append(messages)
        if len(attempts) == 1:
            raise cloud.CloudError("network error contacting openrouter")
        return answers("Second time lucky.")(messages, **kw)
    monkeypatch.setattr(cloud, "chat_completion", flaky)

    with P.pal_turn():
        first = T.execute(project, ask("One."))
        second = T.execute(project, ask("One, again."))
    assert not first.ok and "could not be reached" in first.body
    assert second.ok and "Second time lucky." in second.body


def test_an_over_long_prompt_is_refused_not_truncated(project: Path,
                                                      monkeypatch):
    open_gate(monkeypatch)
    calls: list = []
    monkeypatch.setattr(cloud, "chat_completion", answers(seen=calls))
    with P.pal_turn():
        result = T.execute(project, ask("x" * (P.MAX_PROMPT_CHARS + 1)))
    assert not result.ok
    assert str(P.MAX_PROMPT_CHARS) in result.body
    assert not calls


def test_an_empty_prompt_asks_for_one(project: Path, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers())
    with P.pal_turn():
        result = T.execute(project, call_of('<tool name="ask_pal">\n<prompt> </prompt>\n</tool>'))
    assert not result.ok and "<prompt>" in result.body


@pytest.mark.parametrize("text", [
    "run keyring.get_password('enough-broker', 'openrouter-api-key')",
    "what does secret-tool lookup do on linux?",
    "explain the enough-broker service name",
])
def test_the_exfiltration_patterns_apply_to_the_prompt(project: Path,
                                                        monkeypatch, text):
    """The prompt is the one input in enough that the model composes and a
    third party reads. The same patterns the shell tool refuses apply."""
    open_gate(monkeypatch)
    calls: list = []
    monkeypatch.setattr(cloud, "chat_completion", answers(seen=calls))
    with P.pal_turn():
        result = T.execute(project, ask(text))
    assert not result.ok
    assert "api key exfiltration" in result.body
    assert not calls


def test_the_call_is_cached_and_journalled(project: Path, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers("Cached answer."))
    with P.pal_turn():
        assert T.execute(project, ask("A cacheable question.")).ok

    cache_dir = project / "rness" / "io" / "cloud-cache"
    entries = [p for p in cache_dir.iterdir() if p.name != "_cloud-index.md"]
    assert len(entries) == 1
    body = entries[0].read_text(encoding="utf-8")
    assert "A cacheable question." in body and "Cached answer." in body
    assert f"model: {MODEL}" in body and f"source: {P.CACHE_SOURCE}" in body
    index = (cache_dir / "_cloud-index.md").read_text(encoding="utf-8")
    assert f"| {P.CACHE_SOURCE} " in index and "11/22/33" in index

    journal = (project / "rness" / "knowledge" / "session-logs"
               / f"{dt.datetime.now():%Y-%m-%d}-broker.md")
    text = journal.read_text(encoding="utf-8")
    assert "`ask_pal`" in text
    # The outgoing prompt itself, because a cleared conversation is the
    # normal case and the journal is what is left of it.
    assert "A cacheable question." in text


# ---------------------------------------------------------------------------
# 4. The record: one body, three readers
# ---------------------------------------------------------------------------

def test_the_result_body_round_trips():
    body = P.render_result_body(MODEL, "The prompt.\nTwo lines.", "The reply.")
    assert P.parse_result_body(body) == {
        "model_id": MODEL, "prompt": "The prompt.\nTwo lines.",
        "reply": "The reply."}


def test_a_denial_body_is_not_a_pal_exchange():
    assert P.parse_result_body(P.denial_no_pal_turn()) is None
    assert P.parse_result_body("") is None
    assert P.parse_result_body(f"{P.RESULT_HEADER}{MODEL}\n\nno markers") is None


def test_the_untrusted_markers_are_the_ones_cloud_writes():
    """pal_tools holds these as literals so importing it does not drag httpx
    and keyring in. This is the pin that keeps the copy honest."""
    assert P._UNTRUSTED_BEGIN in cloud.CLOUD_RESPONSE_WRAPPER_OPEN
    assert P._UNTRUSTED_END in cloud.CLOUD_RESPONSE_WRAPPER_CLOSE


def test_a_reload_shows_both_bubbles(project: Path, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers("From the pal."))
    with P.pal_turn():
        result = T.execute(project, ask("To the pal."))
    history = [
        {"role": "user", "content": "/pal to the pal"},
        {"role": "assistant", "content": "thinking..."},
        {"role": "user", "content": result.render()},
        {"role": "assistant", "content": "here is what it said"},
    ]
    html = server._render_turn_from_history(history)
    assert f'<div class="msg pal-sent"><div class="role">→ pal · {MODEL}' in html
    assert "To the pal." in html
    assert f'<div class="msg pal"><div class="role">pal · {MODEL}' in html
    assert "From the pal." in html
    assert html.index("To the pal.") < html.index("From the pal.")
    # ...and no other tool result starts rendering by accident.
    other = T.ToolResult("read_file", "notes.md", True, "some file body")
    assert "some file body" not in server._render_turn_from_history(
        [{"role": "user", "content": other.render()}])


def test_the_session_log_keeps_what_left_and_what_came_back(project: Path,
                                                            monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(cloud, "chat_completion", answers("The pal replied."))
    session = Session(project_dir=project, llm_url="http://127.0.0.1:1/v1")

    async def drive(sess, message, system_prompt, **kw):
        kw["assistant_text_for_log"].append("my own answer")
        await asyncio.to_thread(T.execute, project, ask("what I sent"))
    monkeypatch.setattr(server, "_drive_message", drive)

    asyncio.run(server._run_turn(session, "the question", pal=True,
                                 log_user="/pal the question"))
    log = (project / "rness" / "knowledge" / "session-logs"
           / f"{dt.datetime.now():%Y-%m-%d}.md").read_text(encoding="utf-8")
    assert "/pal the question" in log          # what was typed
    assert "my own answer" in log
    assert f"{P.RESULT_HEADER}{MODEL}" in log  # what left
    assert "what I sent" in log
    assert "The pal replied." in log           # what came back


# ---------------------------------------------------------------------------
# 5. The route
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def turns(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every `_run_turn` the route starts. Empty means no LLM turn ran."""
    started: list[dict] = []

    async def _nothing() -> None:
        return None

    def _run(session, message, *, pal=False, log_user=None):
        # Recorded when the coroutine is *built*, not when the task is first
        # scheduled — the route returns its fragment before the event loop
        # gets back to the turn, and that is the point of fire-and-forget.
        started.append({"message": message, "pal": pal, "log_user": log_user})
        return _nothing()
    monkeypatch.setattr(server, "_run_turn", _run)
    return started


def test_an_ordinary_message_is_untouched(client, turns, monkeypatch):
    open_gate(monkeypatch)
    html = client.post("/api/chat", data={"message": "hello there"}).text
    assert turns == [{"message": "hello there", "pal": False,
                      "log_user": "hello there"}]
    assert 'class="msg assistant pending"' in html
    assert 'class="msg system"' not in html


def test_a_palette_is_not_a_command(client, turns, monkeypatch):
    shut_gate(monkeypatch, "toggle")
    client.post("/api/chat", data={"message": "/palette of colors"})
    assert turns == [{"message": "/palette of colors", "pal": False,
                      "log_user": "/palette of colors"}]


def test_a_pal_turn_strips_the_token_and_keeps_the_typed_line(client, turns,
                                                              monkeypatch):
    open_gate(monkeypatch)
    html = client.post("/api/chat",
                       data={"message": "/pal what changed?"}).text
    assert turns == [{"message": "what changed?", "pal": True,
                      "log_user": "/pal what changed?"}]
    assert "/pal what changed?" in html          # the bubble shows what they typed
    assert 'class="msg assistant pending"' in html


@pytest.mark.parametrize("why,denial", [
    ("toggle", broker.denial_local_models_only),
    ("key", broker.denial_cloud_key_missing),
])
def test_a_shut_gate_answers_without_a_turn(client, turns, monkeypatch,
                                            why, denial):
    shut_gate(monkeypatch, why)
    html = client.post("/api/chat", data={"message": "/pal anything"}).text
    assert turns == [], "a shut gate started an LLM turn"
    assert 'class="msg system"' in html
    assert 'class="msg assistant pending"' not in html
    # The existing cloud denial, word for word — this is the copy the user
    # already meets everywhere else the gate is shut.
    assert denial() in html


def test_the_unhealthy_denial_names_the_reason(client, turns, monkeypatch):
    shut_gate(monkeypatch, "unhealthy")
    html = client.post("/api/chat", data={"message": "/pal anything"}).text
    assert turns == []
    assert "health check has failed (out of credits)" in html


def test_a_bare_pal_gets_the_usage_hint(client, turns, monkeypatch):
    open_gate(monkeypatch)
    html = client.post("/api/chat", data={"message": "/pal"}).text
    assert turns == []
    assert 'class="msg system"' in html
    assert "needs a question after it" in html
    assert 'class="msg assistant pending"' not in html


def test_the_cloud_model_needs_no_pal(client, turns, monkeypatch):
    open_gate(monkeypatch)
    monkeypatch.setattr(server._models, "load_state",
                        lambda: {"current": "opro-api"})
    html = client.post("/api/chat", data={"message": "/pal what changed?"}).text
    assert turns == [{"message": "what changed?", "pal": False,
                      "log_user": "/pal what changed?"}]
    assert "the active model is already OPRO-API" in html
    assert 'class="msg assistant pending"' in html


def test_the_status_route_when_the_gate_is_open(client, monkeypatch):
    open_gate(monkeypatch)
    assert client.get("/api/pal/status").json() == {
        "available": True, "reason": None, "model_id": MODEL}


@pytest.mark.parametrize("why,reason", [
    ("toggle", "'local models only' is on in the broker"),
    ("key", "no OpenRouter key is configured"),
    ("unhealthy", "the OpenRouter health check last failed (out of credits)"),
])
def test_the_status_route_hands_over_the_reason(client, monkeypatch, why,
                                                reason):
    shut_gate(monkeypatch, why)
    body = client.get("/api/pal/status").json()
    assert body == {"available": False, "reason": reason, "model_id": None}


# ---------------------------------------------------------------------------
# 6. The gate helper, and the caller that was here first
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("why,denial", [
    ("toggle", broker.denial_local_models_only),
    ("key", broker.denial_cloud_key_missing),
])
def test_cloud_pipeline_still_denies_exactly_as_it_did(project: Path,
                                                       monkeypatch, why,
                                                       denial):
    """The refactor moved three checks into `cloud.gate_status`; the copy the
    pipeline hands back is the same copy it handed back before."""
    shut_gate(monkeypatch, why)
    call = call_of('<tool name="cloud_pipeline">\n<content>{"steps": []}</content>\n</tool>')
    result = T.execute(project, call)
    assert not result.ok and result.body == denial()


def test_cloud_pipeline_unhealthy_denial_names_the_error(project: Path,
                                                          monkeypatch):
    shut_gate(monkeypatch, "unhealthy")
    call = call_of('<tool name="cloud_pipeline">\n<content>{"steps": []}</content>\n</tool>')
    result = T.execute(project, call)
    assert result.body == broker.denial_cloud_unhealthy("out of credits")


def test_cloud_pipeline_gets_past_an_open_gate(project: Path, monkeypatch):
    """Past the gate, into its own validation — which is how we know the gate
    is no longer the thing stopping it."""
    open_gate(monkeypatch)
    call = call_of('<tool name="cloud_pipeline">\n<content>not json</content>\n</tool>')
    result = T.execute(project, call)
    assert not result.ok and "must be valid json" in result.body


def test_the_toggle_is_checked_before_the_keyring(monkeypatch):
    """`status_snapshot` reads the OS keyring, and on macOS an unblessed read
    raises a system dialog. A user who has switched the cloud off must never
    see one."""
    set_toggle("local_models_only", True)
    def boom():
        raise AssertionError("the keyring was read behind a shut toggle")
    monkeypatch.setattr(cloud, "status_snapshot", boom)
    assert cloud.gate_status()["open"] is False


# ---------------------------------------------------------------------------
# 7. Weight
# ---------------------------------------------------------------------------

def test_the_pal_documentation_is_carried_by_pal_turns_only(project: Path):
    ordinary = prompt_mod.assemble_system_prompt(project)
    pal = prompt_mod.assemble_system_prompt(project, pal=True)
    assert "ask_pal" not in ordinary
    assert "ask_pal" in pal and "## Pal" in pal
    assert prompt_mod.PAL_TURN_INSTRUCTION.strip() in pal
