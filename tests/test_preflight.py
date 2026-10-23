"""The context-window preflight (the 16 GB context fix, 0.4.3).

docs/ctx-16gb-plan.md §8.3-§8.4: before anyone types, enough counts its own
default system prompt with llama-server's tokenizer, compares it with the live
window (2,048-token reserve), exposes the verdict on `/api/llm-status`, and
offers a one-click larger window only when enough supervises the model and the
machine can afford the window. A first-turn overflow says the same numbers
instead of the later-turn "things to try".

No test reaches a model: the llama-server here is an `httpx.MockTransport`
answering `/tokenize`, `/props` and `/health`. `models.LIVE_STATE` and
`WEIGHTS_DIR` are read once at import, so every test that touches the live
model state re-points them into tmp_path (the autouse fixture in conftest.py
handles `$HOME` and the env seams).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from enough import models
from enough import preflight as P
from enough import server
from enough import skeleton

REPO = Path(__file__).resolve().parent.parent
#: A fresh project's default prompt in gemma-4 tokens (plan §1a).
GEMMA_PROMPT = 19_974


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Live model state and weights inside tmp_path; the SHIPPED registry
    (read-only), so the verdicts below are about the real ctx_defaults."""
    monkeypatch.setattr(models, "LIVE_STATE", tmp_path / "config" / "models.json")
    monkeypatch.setattr(models, "WEIGHTS_DIR", tmp_path / "weights")
    monkeypatch.setattr(models, "REGISTRY_TEMPLATE", REPO / "defaults" / "models.json")
    models.save_state({"current": "g40-04"})
    assert str(models.LIVE_STATE).startswith(str(tmp_path))
    return tmp_path


@pytest.fixture
def ram(monkeypatch: pytest.MonkeyPatch):
    """Set this machine's RAM (and give it ample disk)."""
    def _set(gb: int) -> None:
        monkeypatch.setattr(models, "total_ram_gb", lambda: gb)
        monkeypatch.setattr(models, "free_disk_gb", lambda: 500.0)
    _set(16)
    return _set


def entry(cute: str) -> dict:
    return json.loads((REPO / "defaults" / "models.json").read_text())["models"][cute]


class FakeLlama:
    """A llama-server that answers the three endpoints the preflight and
    llm-status use, and records what it was asked."""

    def __init__(self, *, tokens: int = GEMMA_PROMPT, n_ctx: int = 16384,
                 fail: str | None = None) -> None:
        self.tokens = tokens
        self.n_ctx = n_ctx
        self.fail = fail            # "tokenize" | "props" | "connect" | None
        self.requests: list[tuple[str, str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        if self.fail == "connect":
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/tokenize":
            if self.fail == "tokenize":
                return httpx.Response(404, text="Not Found")
            return httpx.Response(200, json={"tokens": list(range(self.tokens))})
        if request.url.path == "/props":
            if self.fail == "props":
                return httpx.Response(200, json={"default_generation_settings": {}})
            return httpx.Response(200, json={
                "default_generation_settings": {"n_ctx": self.n_ctx},
                "model_path": "/w/gemma-4-E4B-it-Q4_K_M.gguf"})
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


class FakeSupervisor:
    def __init__(self, cute: str | None = "g40-04", ctx: int | None = 16384,
                 ready: bool = True) -> None:
        self.current_cute = cute
        self.current_ctx = ctx
        self.ready = ready


def make(fake: FakeLlama, *, supervisor: Any = None,
         prompt: str = "the default system prompt") -> P.Preflight:
    return P.Preflight(llm_url="http://llama.test", build_prompt=lambda: prompt,
                       supervisor=supervisor, transport=fake.transport())


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------

def test_it_fits_with_the_reserve_to_spare():
    v = P.evaluate(GEMMA_PROMPT, 32768, entry=entry("g40-04"), supervised=True)
    assert v == {"prompt_tokens": GEMMA_PROMPT, "n_ctx": 32768, "reserve": 2048,
                 "fits": True, "suggest_ctx": None, "fix": "none",
                 "fix_reason": None}


def test_the_reserve_is_part_of_fitting():
    """20k of instructions in a 21k window answer nothing: the first message
    and a thinking reply need ~2k beside them."""
    assert P.evaluate(GEMMA_PROMPT, GEMMA_PROMPT + 2048)["fits"] is True
    assert P.evaluate(GEMMA_PROMPT, GEMMA_PROMPT + 2047)["fits"] is False
    assert P.evaluate(GEMMA_PROMPT, 16384)["fits"] is False


@pytest.mark.parametrize("tokens, ctx_max, want", [
    (GEMMA_PROMPT, 131072, 32768),         # the common case
    (30_720, 131072, 32768),                # 30,720 + 2,048 = 32,768 exactly
    (30_721, 131072, 65536),
    (70_000, 131072, 131072),
    (129_025, 131072, None),                # 131,073 needed
    (40_000, 32768, None),                  # the model's own ceiling
    (40_000, None, 65536),                  # unknown model: no ceiling
    (200_000, None, None),                  # past the largest window offered
])
def test_suggest_ctx_is_the_smallest_window_that_holds_it(tokens, ctx_max, want):
    assert P.suggest_ctx(tokens, ctx_max) == want


def test_the_fix_is_a_switch_when_supervised_and_affordable(live, ram):
    """G40-04 on a 16 GB machine with an old 16k override: 32k is what the
    registry now ships at that tier, so enough offers it."""
    ram(16)
    v = P.evaluate(GEMMA_PROMPT, 16384, entry=entry("g40-04"), supervised=True)
    assert (v["fits"], v["suggest_ctx"], v["fix"], v["fix_reason"]) == \
        (False, 32768, "switch", None)


def test_g40_12_on_16_gb_is_offered_32k_too(live, ram):
    ram(16)
    v = P.evaluate(GEMMA_PROMPT, 8192, entry=entry("g40-12"), supervised=True)
    assert (v["fix"], v["suggest_ctx"]) == ("switch", 32768)


@pytest.mark.parametrize("cute, ram_gb", [
    ("g40-26", 24),     # stays 8,192 at 16-31 GB (plan §8.1)
    ("q36-27", 24),
    ("q38-04", 24),
    ("g40-04", 8),      # under 16 GB no window holds the full prompt
])
def test_no_button_when_the_machine_cannot_afford_the_window(live, ram, cute, ram_gb):
    ram(ram_gb)
    v = P.evaluate(GEMMA_PROMPT, 8192, entry=entry(cute), supervised=True)
    assert (v["fix"], v["fix_reason"], v["suggest_ctx"]) == ("none", "memory", 32768)


def test_no_button_when_enough_does_not_supervise_the_model(live, ram):
    ram(64)
    v = P.evaluate(GEMMA_PROMPT, 16384, entry=entry("g40-04"), supervised=False)
    assert (v["fix"], v["fix_reason"], v["suggest_ctx"]) == ("none", "unsupervised", 32768)
    # …and a llama-server enough cannot name is never switchable either.
    v = P.evaluate(GEMMA_PROMPT, 16384, entry=None, supervised=True)
    assert (v["fix"], v["fix_reason"]) == ("none", "unsupervised")


def test_no_button_when_no_window_is_large_enough(live, ram):
    ram(128)
    small = dict(entry("g40-04"), ctx_max=16384)
    v = P.evaluate(GEMMA_PROMPT, 8192, entry=small, supervised=True)
    assert (v["fix"], v["fix_reason"], v["suggest_ctx"]) == ("none", "no_window", None)


def test_the_fix_reads_feasibility_at_the_suggested_window(live, monkeypatch):
    """The decision is `models.feasibility(entry, ctx=suggest_ctx)`'s RAM
    axis, nothing else — disk is moot for a model already on disk."""
    seen: list[Any] = []

    def fake(e, ctx=None):
        seen.append(ctx)
        return {"verdict": "no", "reasons": ["disk"], "ram": "good", "disk": "no"}

    monkeypatch.setattr(models, "feasibility", fake)
    v = P.evaluate(GEMMA_PROMPT, 16384, entry=entry("g40-04"), supervised=True)
    assert seen == [32768] and v["fix"] == "switch"
    monkeypatch.setattr(models, "feasibility",
                        lambda e, ctx=None: {"verdict": "no", "reasons": [], "ram": "no", "disk": "good"})
    assert P.evaluate(GEMMA_PROMPT, 16384, entry=entry("g40-04"),
                      supervised=True)["fix_reason"] == "memory"


def test_feasibility_without_ctx_is_unchanged(live, ram):
    ram(16)
    v = models.feasibility(entry("g40-12"))
    assert v["verdict"] == "tight" and v["ram"] == "tight"
    assert models.feasibility(entry("g40-12"), ctx=32768)["ram"] == "tight"
    no = models.feasibility(entry("g40-12"), ctx=65536)
    assert no["ram"] == "no" and any("65,536-token window" in r for r in no["reasons"])


def test_the_registry_ships_32k_for_the_two_small_gemmas_at_16_gb():
    """§8.1, and nothing else moved: G40-26 stays at 8,192."""
    reg = json.loads((REPO / "defaults" / "models.json").read_text())["models"]
    assert reg["g40-04"]["ctx_defaults"]["gte_16gb"] == 32768
    assert reg["g40-12"]["ctx_defaults"]["gte_16gb"] == 32768
    assert reg["g40-26"]["ctx_defaults"]["gte_16gb"] == 8192
    assert models.recommend_ctx(reg["g40-04"], 16) == 32768
    assert models.recommend_ctx(reg["g40-12"], 24) == 32768


# ---------------------------------------------------------------------------
# The runner, against a fake llama-server
# ---------------------------------------------------------------------------

def test_a_run_counts_the_prompt_exactly_and_reads_the_window(live, ram):
    fake = FakeLlama(tokens=GEMMA_PROMPT, n_ctx=32768)
    pf = make(fake, supervisor=FakeSupervisor(ctx=32768), prompt="PROMPT")
    result = asyncio.run(pf.run("test"))
    assert result is not None and result["fits"] is True
    assert pf.state == "done"
    assert ("POST", "/tokenize", {"content": "PROMPT", "with_pieces": False}) in fake.requests
    assert ("GET", "/props", None) in fake.requests
    f = pf.fields()
    assert (f["prompt_tokens"], f["n_ctx"], f["fits"], f["fix"], f["preflight"]) == \
        (GEMMA_PROMPT, 32768, True, "none", "done")


def test_a_run_that_does_not_fit_offers_the_switch(live, ram):
    ram(16)
    pf = make(FakeLlama(n_ctx=16384), supervisor=FakeSupervisor(ctx=16384))
    asyncio.run(pf.run())
    f = pf.fields()
    assert (f["fits"], f["suggest_ctx"], f["fix"], f["fix_reason"]) == \
        (False, 32768, "switch", None)


@pytest.mark.parametrize("fail", ["tokenize", "props", "connect"])
def test_a_failure_leaves_the_verdict_unknown(live, fail):
    pf = make(FakeLlama(fail=fail), supervisor=FakeSupervisor())
    assert asyncio.run(pf.run()) is None
    f = pf.fields()
    assert f["preflight"] == "failed"
    assert f["fits"] is None and f["prompt_tokens"] is None and f["fix"] is None


def test_a_prompt_that_cannot_be_built_is_unknown_too(live):
    def boom() -> str:
        raise OSError("rness/ unreadable")
    pf = P.Preflight(llm_url="http://llama.test", build_prompt=boom,
                     transport=FakeLlama().transport())
    assert asyncio.run(pf.run()) is None and pf.state == "failed"


def test_cloud_mode_is_skipped_without_asking_anything(live):
    models.save_state({"current": "opro-api"})
    fake = FakeLlama()
    pf = make(fake, supervisor=FakeSupervisor())
    assert asyncio.run(pf.run()) is None
    assert pf.fields()["preflight"] == "skipped" and pf.fields()["fits"] is None
    assert fake.requests == []

    async def scheduled() -> None:
        pf.schedule("test")
        await asyncio.sleep(0)
    asyncio.run(scheduled())
    assert pf.state == "skipped" and fake.requests == []


def test_a_verdict_for_another_window_reads_as_unknown(live, ram):
    """After a switch the old numbers are wrong; until the new model's run
    lands, the page sees `fits: None` and shows no notice."""
    sup = FakeSupervisor(ctx=16384)
    pf = make(FakeLlama(n_ctx=16384), supervisor=sup)
    asyncio.run(pf.run())
    assert pf.fields()["fits"] is False
    sup.current_ctx = 32768
    assert pf.fields()["fits"] is None and pf.fields()["preflight"] == "idle"


def test_schedule_waits_for_a_supervised_model_to_be_ready(live):
    fake = FakeLlama()
    sup = FakeSupervisor(ready=False)
    pf = make(fake, supervisor=sup)

    async def go() -> None:
        pf.schedule("too early")
        await asyncio.sleep(0.05)
        assert fake.requests == [] and pf.state == "idle"
        sup.ready = True
        pf.schedule("ready")
        await asyncio.wait_for(pf._task, 5)
    asyncio.run(go())
    assert pf.state == "done"


def test_a_schedule_during_a_run_reruns_once(live):
    fake = FakeLlama(n_ctx=32768)
    pf = make(fake, supervisor=FakeSupervisor(ctx=32768))

    async def go() -> None:
        pf.schedule("one")
        pf.schedule("two")      # lands while "one" is running
        pf.schedule("three")    # …and folds into the same rerun
        await asyncio.wait_for(pf._task, 5)
    asyncio.run(go())
    assert [p for _m, p, _b in fake.requests].count("/tokenize") == 2


def test_the_supervisor_ready_hook_fires_and_never_breaks_readiness():
    from enough.supervisor import LlamaSupervisor
    sup = LlamaSupervisor(llm_url="http://127.0.0.1:1")
    calls: list[int] = []
    sup.on_ready = lambda: calls.append(1)
    sup._notify_ready()
    assert calls == [1]
    sup.on_ready = lambda: 1 / 0
    sup._notify_ready()          # logged, swallowed


# ---------------------------------------------------------------------------
# /api/llm-status
# ---------------------------------------------------------------------------

FIELDS = ("prompt_tokens", "n_ctx", "reserve", "fits", "suggest_ctx", "fix",
          "fix_reason", "preflight")


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    return proj


def _wait_for(client: TestClient, pred, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    body: dict = {}
    while time.time() < deadline:
        body = client.get("/api/llm-status").json()
        if pred(body):
            return body
        time.sleep(0.02)
    raise AssertionError(f"llm-status never got there: {body}")


def test_llm_status_carries_the_preflight_when_external(live, tmp_path):
    """--no-supervise: measured at project open, never switchable."""
    app = server.create_app(_project(tmp_path), "http://127.0.0.1:9", supervise=False)
    app.state.session.preflight._transport = FakeLlama(n_ctx=16384).transport()
    with TestClient(app) as client:
        body = _wait_for(client, lambda b: b.get("preflight") == "done")
    for k in FIELDS:
        assert k in body, k
    assert body["mode"] == "external"
    assert (body["n_ctx"], body["fits"], body["reserve"]) == (16384, False, 2048)
    assert body["prompt_tokens"] == GEMMA_PROMPT
    assert (body["fix"], body["fix_reason"], body["suggest_ctx"]) == \
        ("none", "unsupervised", 32768)


def test_llm_status_measures_the_prompt_a_chat_turn_would_send(live, tmp_path):
    """Exactly the default system prompt: the `chat` profile, no pal block."""
    proj = _project(tmp_path)
    fake = FakeLlama(n_ctx=65536)
    app = server.create_app(proj, "http://127.0.0.1:9", supervise=False)
    app.state.session.preflight._transport = fake.transport()
    with TestClient(app) as client:
        _wait_for(client, lambda b: b.get("preflight") == "done")
    sent = [b for _m, p, b in fake.requests if p == "/tokenize"][0]["content"]
    assert sent == server.assemble_system_prompt(proj)


def test_llm_status_fields_ride_on_the_supervised_shape(live, tmp_path):
    """No model installed in the scratch world, so the supervisor stays off —
    the fields are there anyway, unknown."""
    app = server.create_app(_project(tmp_path), "http://127.0.0.1:9", supervise=True)
    with TestClient(app) as client:
        body = client.get("/api/llm-status").json()
    assert body["mode"] == "off"
    for k in FIELDS:
        assert k in body, k
    assert body["fits"] is None and body["preflight"] == "idle"


def test_llm_status_in_cloud_mode_skips_the_preflight(live, tmp_path):
    models.save_state({"current": "opro-api"})
    app = server.create_app(_project(tmp_path), "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as client:
        body = client.get("/api/llm-status").json()
    assert body["mode"] == "cloud"
    assert body["preflight"] == "skipped" and body["fits"] is None


def test_home_mode_has_no_preflight(live, tmp_path):
    app = server.create_app(tmp_path, "http://127.0.0.1:9", supervise=False, home=True)
    assert app.state.session.preflight is None


# ---------------------------------------------------------------------------
# The overflow message
# ---------------------------------------------------------------------------

OVERFLOW_400 = json.dumps({"error": {
    "code": 400, "type": "exceed_context_size_error", "n_prompt_tokens": 20098,
    "n_ctx": 16384,
    "message": "request (20098 tokens) exceeds the available context size "
               "(16384 tokens), try increasing it"}})


def test_n_ctx_is_read_from_the_400():
    assert P.n_ctx_from_error(OVERFLOW_400) == 16384
    cut = OVERFLOW_400.replace('"n_ctx": 16384,', "")[:200]
    assert P.n_ctx_from_error(cut) == 16384           # regex, from the message
    assert P.n_ctx_from_error("nothing useful") is None


def _session(tmp_path: Path, fake: FakeLlama, history: list[dict]) -> server.Session:
    s = server.Session(project_dir=_project(tmp_path), llm_url="http://llama.test")
    s.history = list(history)
    s.client = httpx.AsyncClient(transport=fake.transport())
    return s


def _advice(session: server.Session, prompt: str = "PROMPT") -> str | None:
    async def go():
        try:
            return await server._first_turn_overflow(session, prompt, OVERFLOW_400)
        finally:
            await session.client.aclose()
    return asyncio.run(go())


def test_a_first_turn_overflow_gives_the_numbers_and_the_fix(live, tmp_path):
    s = _session(tmp_path, FakeLlama(), [{"role": "user", "content": "hi"}])
    msg = _advice(s)
    assert msg is not None
    assert "enough's instructions alone are 19,974 tokens" in msg
    assert "holds 16,384" in msg
    assert "open the model window" in msg and "larger context" in msg
    assert "/reset" not in msg and "skills" not in msg


def test_a_retried_first_turn_is_still_a_first_turn(live, tmp_path):
    """A failed first turn leaves its user message behind; a second try has
    two user messages and still no reply."""
    s = _session(tmp_path, FakeLlama(), [{"role": "user", "content": "hi"},
                                         {"role": "user", "content": "hello?"}])
    assert "alone are 19,974" in (_advice(s) or "")


def test_a_later_turn_keeps_todays_advice(live, tmp_path):
    s = _session(tmp_path, FakeLlama(tokens=6_000),
                 [{"role": "user", "content": "hi"},
                  {"role": "assistant", "content": "hello"},
                  {"role": "user", "content": "x" * 50_000}])
    assert _advice(s) is None


def test_instructions_that_alone_leave_no_room_win_on_any_turn(live, tmp_path):
    s = _session(tmp_path, FakeLlama(tokens=15_000),
                 [{"role": "user", "content": "hi"},
                  {"role": "assistant", "content": "hello"},
                  {"role": "user", "content": "more"}])
    assert "alone are 15,000 tokens" in (_advice(s) or "")


def test_a_huge_first_message_is_named_as_the_problem(live, tmp_path):
    s = _session(tmp_path, FakeLlama(tokens=6_000), [{"role": "user", "content": "x"}])
    msg = _advice(s) or ""
    assert "instructions are 6,000 tokens" in msg
    assert "this message is longer than the room left" in msg
    assert "/reset" not in msg


def test_without_tokenize_the_count_is_an_estimate(live, tmp_path):
    s = _session(tmp_path, FakeLlama(fail="tokenize"), [{"role": "user", "content": "hi"}])
    msg = _advice(s, prompt="y" * 74_000) or ""
    assert "about 20,000 tokens" in msg


def test_the_turn_path_emits_the_first_turn_branch(live, tmp_path, monkeypatch):
    """End to end through `_run_turn`: llama-server's 400 on the first
    message becomes the new advice, tagged `kind: ctx_overflow` so the page
    can put the notice under it."""
    from enough.llm import LLMError

    async def overflowing(*_a, **_k):
        raise LLMError(400, OVERFLOW_400)
        yield ""                                   # pragma: no cover

    monkeypatch.setattr(server, "stream_chat", overflowing)
    s = _session(tmp_path, FakeLlama(), [])

    async def go() -> list[dict]:
        q: asyncio.Queue = asyncio.Queue()
        s.subscribers.append(q)
        try:
            await server._run_turn(s, "hi")
        finally:
            await s.client.aclose()
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out

    events = asyncio.run(go())
    errors = [json.loads(e["data"]) for e in events if e["event"] == "error"]
    assert len(errors) == 1
    err = errors[0]
    assert err.get("kind") == "ctx_overflow"
    assert "alone are 19,974 tokens" in err["message"] and "16,384" in err["message"]
    assert "/reset" not in err["message"]


def test_the_turn_path_keeps_the_later_turn_advice(live, tmp_path, monkeypatch):
    from enough.llm import LLMError

    async def overflowing(*_a, **_k):
        raise LLMError(400, OVERFLOW_400)
        yield ""                                   # pragma: no cover

    monkeypatch.setattr(server, "stream_chat", overflowing)
    s = _session(tmp_path, FakeLlama(tokens=6_000),
                 [{"role": "user", "content": "hi"},
                  {"role": "assistant", "content": "hello"}])

    async def go() -> list[dict]:
        q: asyncio.Queue = asyncio.Queue()
        s.subscribers.append(q)
        try:
            await server._run_turn(s, "and another thing")
        finally:
            await s.client.aclose()
        return [q.get_nowait() for _ in range(q.qsize())]

    err = [json.loads(e["data"]) for e in asyncio.run(go()) if e["event"] == "error"][0]
    assert "kind" not in err
    assert "things to try" in err["message"] and "/reset" in err["message"]
