"""`enough.model_route` (fabula P6): a model route chosen per job, local or cloud.

No network, no llama-server, no keyring: httpx and the `cloud` module are replaced at the seams
`tests/test_llm_complete.py` uses; `$HOME`, the broker's config and ui.json are tmp_path's (tests/conftest.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from enough import agent_free, broker, cloud, llm, model_route, models

MSGS = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "the secret prompt text"}]


@pytest.fixture(autouse=True)
def live_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "live-models.json"
    state.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", state)
    return state


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    return p


class _Resp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)  # type: ignore[arg-type]


def net(monkeypatch: pytest.MonkeyPatch, *, model: str = "g40-04", usage: dict | None = None) -> list:
    """Every httpx.post/get recorded; llama-server answers posts to /v1/chat/completions."""
    calls: list = []

    def post(url, **kw):
        calls.append(("post", url))
        body = {"model": model, "choices": [{"finish_reason": "stop", "message": {"content": " local answer "}}]}
        if usage is not None:
            body["usage"] = usage
        return _Resp(body)

    def get(url, **kw):
        calls.append(("get", url))
        return _Resp({}, status=404)

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    return calls


def gate(monkeypatch: pytest.MonkeyPatch, *, open_: bool, denial: str = "error: the gate's own denial",
         model_id: str = "cfg/model") -> None:
    monkeypatch.setattr(cloud, "gate_status", lambda: {
        "open": open_, "reason": None if open_ else "shut", "denial": None if open_ else denial,
        "model_id": model_id if open_ else None})


def cloud_answers(monkeypatch: pytest.MonkeyPatch, *, model: str = "anthropic/claude-x-20261101",
                  usage: dict | None = None) -> list:
    calls: list = []

    def chat_completion(messages, **kw):
        calls.append(kw)
        body = {"model": model, "choices": [{"finish_reason": "stop", "message": {"content": "from the cloud"}}]}
        if usage is not None:
            body["usage"] = usage
        return body

    monkeypatch.setattr(cloud, "chat_completion", chat_completion)
    return calls


def journal_text(project: Path) -> str:
    logs = list((project / "rness" / "knowledge" / "session-logs").glob("*-broker.md"))
    return "".join(p.read_text(encoding="utf-8") for p in logs)


# ---------------------------------------------------------------------------
# the factory
# ---------------------------------------------------------------------------

def test_the_factory_refuses_bad_arguments_at_once(project):
    with pytest.raises(ValueError, match="unknown model route"):
        model_route.make_complete("remote", llm_url="http://x")
    with pytest.raises(ValueError, match="llm_url"):
        model_route.make_complete("local")
    with pytest.raises(ValueError, match="project_dir"):
        model_route.make_complete("cloud")


def test_the_generation_lock_is_for_the_local_route_only():
    assert model_route.holds_generation_lock("local") is True
    assert model_route.holds_generation_lock("cloud") is False
    with pytest.raises(ValueError):
        model_route.holds_generation_lock("elsewhere")


# ---------------------------------------------------------------------------
# local
# ---------------------------------------------------------------------------

def test_local_asks_llama_server_and_meta_says_so(monkeypatch):
    calls = net(monkeypatch, usage={"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15})
    complete = model_route.make_complete("local", llm_url="http://127.0.0.1:60206/")
    text, meta = complete(MSGS, max_tokens=700)
    assert text == "local answer"
    assert meta == {"model": "g40-04", "route": "local", "from_reasoning": False, "finish_reason": "stop",
                    "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15}}
    assert "provider" not in meta
    assert ("post", "http://127.0.0.1:60206/v1/chat/completions") in calls


def test_local_without_usage_leaves_it_out(monkeypatch):
    net(monkeypatch)
    _, meta = model_route.make_complete("local", llm_url="http://127.0.0.1:1")(MSGS)
    assert "usage" not in meta and meta["route"] == "local"


def test_local_never_reaches_the_cloud_even_on_the_cloud_slot(monkeypatch, live_state):
    live_state.write_text(json.dumps({"current": "opro-api"}), encoding="utf-8")
    gate(monkeypatch, open_=True)
    asked = cloud_answers(monkeypatch)
    calls = net(monkeypatch)
    text, meta = model_route.make_complete("local", llm_url="http://127.0.0.1:1")(MSGS)
    assert (text, meta["route"]) == ("local answer", "local")
    assert asked == [] and any(c[0] == "post" for c in calls)


def test_local_passes_max_tokens_and_temperature(monkeypatch):
    sent: dict = {}

    def post(url, **kw):
        sent.update(kw["json"])
        return _Resp({"model": "g40-04", "choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _Resp({}, status=404))
    model_route.make_complete("local", llm_url="http://127.0.0.1:1")(MSGS, max_tokens=900, temperature=0.5,
                                                                      ignored="x")
    assert sent["max_tokens"] == 900 and sent["temperature"] == 0.5 and "model" not in sent


# ---------------------------------------------------------------------------
# cloud
# ---------------------------------------------------------------------------

def test_cloud_with_a_shut_gate_refuses_with_the_denial_and_sends_nothing(monkeypatch, project):
    gate(monkeypatch, open_=False, denial="error: the gate's own denial")
    calls = net(monkeypatch)
    with pytest.raises(model_route.RouteRefused) as e:
        model_route.make_complete("cloud", project_dir=project)(MSGS)
    assert str(e.value) == "error: the gate's own denial" and e.value.route == "cloud"
    assert isinstance(e.value, llm.LLMUnavailable)
    assert calls == [], "no HTTP call, local or cloud"
    assert not (project / "rness").exists(), "nothing cached, nothing journalled"


def test_local_models_only_refuses_the_cloud(monkeypatch, project):
    """The real gate, with the broker's default (`local_models_only` on): no keyring read, no request."""
    assert broker.is_enabled("local_models_only")
    calls = net(monkeypatch)
    with pytest.raises(model_route.RouteRefused) as e:
        model_route.make_complete("cloud", project_dir=project)(MSGS)
    assert str(e.value) == broker.denial_local_models_only()
    assert calls == []


def test_a_gate_that_cannot_be_read_refuses(monkeypatch, project):
    def boom():
        raise RuntimeError("keyring locked")

    monkeypatch.setattr(cloud, "gate_status", boom)
    asked = cloud_answers(monkeypatch)
    with pytest.raises(model_route.RouteRefused, match="keyring locked"):
        model_route.make_complete("cloud", project_dir=project)(MSGS)
    assert asked == []


def test_cloud_answers_caches_under_the_source_and_journals_once(monkeypatch, project):
    gate(monkeypatch, open_=True, model_id="cfg/model")
    asked = cloud_answers(monkeypatch, usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25})
    calls = net(monkeypatch)
    complete = model_route.make_complete("cloud", model="anthropic/claude-x", project_dir=project, source="fabula")
    text, meta = complete(MSGS, max_tokens=800)
    assert text == "from the cloud"
    assert meta["route"] == "cloud" and meta["provider"] == "openrouter"
    assert meta["model"] == "anthropic/claude-x-20261101", "the provider's resolved id"
    assert meta["usage"] == {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}
    assert asked == [{"model": "anthropic/claude-x", "temperature": 0.2, "max_tokens": 800, "timeout": 600.0}]
    assert calls == [], "the local server was not asked"

    cache_dir = project / cloud.CLOUD_CACHE_DIRNAME
    entries = [p for p in cache_dir.glob("*.md") if p.name != cloud.CLOUD_CACHE_INDEX_FILENAME]
    assert len(entries) == 1 and meta["cache"] == str(entries[0])
    assert "source: fabula" in entries[0].read_text(encoding="utf-8")
    assert "| fabula |" in (cache_dir / cloud.CLOUD_CACHE_INDEX_FILENAME).read_text(encoding="utf-8")

    j = journal_text(project)
    assert j.count(f"`{model_route.JOURNAL_TOOL}`") == 1
    assert "a fabula job used the cloud" in j and "anthropic/claude-x-20261101" in j and "20/5/25" in j
    assert "openrouter" in j
    assert "secret prompt text" not in j and "from the cloud" not in j


def test_cloud_without_a_chosen_model_uses_the_configured_one(monkeypatch, project):
    gate(monkeypatch, open_=True, model_id="cfg/model")
    asked = cloud_answers(monkeypatch, model="cfg/model")
    _, meta = model_route.make_complete("cloud", project_dir=project, source="thym")(MSGS)
    assert asked[0]["model"] == "cfg/model" and meta["model"] == "cfg/model"
    assert "usage" not in meta
    assert "?/?/?" in journal_text(project)


def test_a_failed_cloud_call_is_journalled_and_raises(monkeypatch, project):
    gate(monkeypatch, open_=True)

    def fail(messages, **kw):
        raise cloud.CloudHTTPError(429, "rate limited")

    monkeypatch.setattr(cloud, "chat_completion", fail)
    with pytest.raises(cloud.CloudError):
        model_route.make_complete("cloud", project_dir=project, source="thym")(MSGS)
    j = journal_text(project)
    assert "a thym job used the cloud" in j and "**outcome:** fail" in j
    assert not (project / cloud.CLOUD_CACHE_DIRNAME).exists()


# ---------------------------------------------------------------------------
# agent-free
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("route", ["local", "cloud"])
def test_agent_free_refuses_both_routes(monkeypatch, project, route):
    monkeypatch.setattr(agent_free, "enabled", lambda: True)
    gate(monkeypatch, open_=True)
    asked = cloud_answers(monkeypatch)
    calls = net(monkeypatch)
    complete = model_route.make_complete(route, llm_url="http://127.0.0.1:1", project_dir=project)
    with pytest.raises(model_route.RouteRefused) as e:
        complete(MSGS)
    assert str(e.value) == agent_free.REASON
    assert asked == [] and calls == []


# ---------------------------------------------------------------------------
# the callers' convention
# ---------------------------------------------------------------------------

def test_canon_derive_hands_max_tokens_through(monkeypatch):
    """canon_derive's `_call` passes keywords only to a callable that takes them; ours takes `**kw`."""
    from enough import canon_derive
    sent: dict = {}

    def post(url, **kw):
        sent.update(kw["json"])
        return _Resp({"model": "g40-04", "choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _Resp({}, status=404))
    text, meta = canon_derive._call(model_route.make_complete("local", llm_url="http://127.0.0.1:1"), MSGS,
                                    max_tokens=4096)
    assert (text, meta["route"], sent["max_tokens"]) == ("ok", "local", 4096)
