"""`llm.complete` and `llm.reachable` (0.4.3): the one non-streaming door the derivation engine and the skill audit
share — routed local vs cloud like chat, the cloud gate asked first, the reasoning-channel fallback, the budget
bounded by llama-server's `/props`.

No network: httpx and `cloud` are replaced at the seams; the live model state is read from a file in tmp_path
(`models.LIVE_STATE` is read once at import, so it is pointed here explicitly).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from enough import cloud, llm, models, skillaudit


@pytest.fixture(autouse=True)
def live_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "live-models.json"
    state.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", state)
    return state


def use_cloud(state: Path) -> None:
    state.write_text(json.dumps({"current": "opro-api"}), encoding="utf-8")


class _Resp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)  # type: ignore[arg-type]


def fake_llama(monkeypatch: pytest.MonkeyPatch, *, content: str = "", reasoning: str = "",
               n_ctx: int | None = None, health: int = 200, model: str = "g40-04",
               finish: str = "stop") -> dict:
    sent: dict = {"posts": 0}

    def post(url, **kw):
        sent["posts"] += 1
        sent.update(kw.get("json") or {})
        sent["url"] = url
        sent["timeout"] = kw.get("timeout")
        return _Resp({"model": model, "choices": [{"finish_reason": finish, "message": {
            "role": "assistant", "content": content, "reasoning_content": reasoning}}]})

    def get(url, **kw):
        if url.endswith("/health"):
            return _Resp({}, status=health)
        if n_ctx is None:
            return _Resp({}, status=404)
        return _Resp({"default_generation_settings": {"n_ctx": n_ctx}})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    return sent


def gate(monkeypatch: pytest.MonkeyPatch, *, open_: bool, reason: str = "'local models only' is on") -> None:
    monkeypatch.setattr(cloud, "gate_status", lambda: {
        "open": open_, "reason": None if open_ else reason, "denial": None, "model_id": "cloud/model"})


def cloud_answers(monkeypatch: pytest.MonkeyPatch, content: str = "from the cloud") -> list:
    calls: list = []

    def chat_completion(messages, **kw):
        calls.append(kw)
        return {"model": "cloud/model", "choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(cloud, "chat_completion", chat_completion)
    return calls


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------

def test_local_route_posts_to_llama_server(monkeypatch):
    sent = fake_llama(monkeypatch, content="  hello  ")
    text, meta = llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:60206/")
    assert text == "hello"
    assert meta == {"model": "g40-04", "route": "local", "from_reasoning": False, "finish_reason": "stop"}
    assert sent["url"] == "http://127.0.0.1:60206/v1/chat/completions"
    assert sent["stream"] is False and sent["temperature"] == 0.2
    assert sent["max_tokens"] == llm.DEFAULT_MAX_TOKENS          # no /props: the full budget
    assert sent["timeout"] == 600.0


def test_cloud_route_with_the_gate_open(monkeypatch, live_state):
    use_cloud(live_state)
    gate(monkeypatch, open_=True)
    calls = cloud_answers(monkeypatch)
    posted = fake_llama(monkeypatch, content="local")
    text, meta = llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:9",
                              max_tokens=900, temperature=0.4)
    assert (text, meta["route"], meta["model"]) == ("from the cloud", "cloud", "cloud/model")
    assert calls == [{"temperature": 0.4, "max_tokens": 900, "timeout": 600.0}]
    assert posted["posts"] == 0, "the local server was not asked"


def test_cloud_route_with_the_gate_shut_raises_unavailable(monkeypatch, live_state):
    use_cloud(live_state)
    gate(monkeypatch, open_=False, reason="no OpenRouter key is configured")
    calls = cloud_answers(monkeypatch)
    with pytest.raises(llm.LLMUnavailable, match="no OpenRouter key"):
        llm.complete([{"role": "user", "content": "hi"}], llm_url=None)
    assert calls == [], "nothing left the machine"


def test_skill_audit_keeps_its_ungated_cloud_route(monkeypatch, live_state):
    """The audit never asked the gate before 0.4.3; the swap onto llm.complete keeps that (cloud_gate=False)."""
    use_cloud(live_state)
    gate(monkeypatch, open_=False)
    calls = cloud_answers(monkeypatch, "VERDICT: pass\nSUMMARY: fine")
    text, from_reasoning = skillaudit._complete([{"role": "user", "content": "hi"}], llm_url=None)
    assert (text, from_reasoning) == ("VERDICT: pass\nSUMMARY: fine", False)
    assert calls[0]["max_tokens"] == skillaudit.AUDIT_MAX_TOKENS
    assert calls[0]["temperature"] == skillaudit.AUDIT_TEMPERATURE


def test_audit_budget_constants_match_the_shared_ones():
    """skillaudit._complete's local budget is llm.completion_budget with llm's floor and headroom."""
    assert skillaudit.AUDIT_MIN_TOKENS == llm.MIN_TOKENS
    assert skillaudit.AUDIT_CTX_HEADROOM == llm.CTX_HEADROOM


# ---------------------------------------------------------------------------
# answers and budgets
# ---------------------------------------------------------------------------

def test_finish_reason_says_when_the_answer_was_cut(monkeypatch):
    fake_llama(monkeypatch, content="nodes:\n  - id: P:claim/x\n    salience: hig", finish="length")
    _text, meta = llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:60206")
    assert meta["finish_reason"] == "length"


def test_reasoning_fallback_when_the_answer_channel_is_empty(monkeypatch):
    fake_llama(monkeypatch, content="", reasoning="line: thinking it through")
    text, meta = llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:60206")
    assert text == "line: thinking it through" and meta["from_reasoning"] is True
    assert llm.message_text({"content": None, "reasoning": "  r  "}) == ("r", True)
    assert llm.message_text({}) == ("", False)


def test_budget_fits_the_launched_window(monkeypatch):
    sent = fake_llama(monkeypatch, content="ok", n_ctx=8192)
    big = [{"role": "user", "content": "x" * 9000}]            # ≈3 k prompt tokens
    llm.complete(big, llm_url="http://127.0.0.1:60206")
    assert llm.MIN_TOKENS <= sent["max_tokens"] <= llm.DEFAULT_MAX_TOKENS
    assert sent["max_tokens"] + 9000 // 3 + llm.CTX_HEADROOM <= 8192
    llm.complete(big, llm_url="http://127.0.0.1:60206", max_tokens=1500)
    assert sent["max_tokens"] == 1500


def test_transport_failures_raise(monkeypatch):
    def refuse(url, **kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", refuse)
    monkeypatch.setattr(httpx, "get", refuse)
    with pytest.raises(httpx.ConnectError):
        llm.complete([{"role": "user", "content": "hi"}], llm_url="http://127.0.0.1:9")


# ---------------------------------------------------------------------------
# reachable
# ---------------------------------------------------------------------------

def test_reachable_local_ok_and_loading_and_down(monkeypatch):
    fake_llama(monkeypatch, health=200)
    assert llm.reachable("http://127.0.0.1:60206") == (True, "ok")
    fake_llama(monkeypatch, health=503)
    ok, why = llm.reachable("http://127.0.0.1:60206")
    assert not ok and "loading" in why                     # 503 is not ready for a derivation


def test_reachable_reports_a_dead_server():
    ok, why = llm.reachable("http://127.0.0.1:9")          # nothing listens on the discard port
    assert not ok and why


def test_reachable_on_the_cloud_slot_is_the_gate(monkeypatch, live_state):
    use_cloud(live_state)
    gate(monkeypatch, open_=True)
    assert llm.reachable(None) == (True, "cloud (cloud/model)")
    gate(monkeypatch, open_=False, reason="the last health check failed")
    assert llm.reachable(None) == (False, "the last health check failed")
