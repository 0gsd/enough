"""POST /api/shutdown — the desktop shell's graceful quit path.

Three things are pinned here:

1. The endpoint is invisible (404) unless the server's environment says
   ENOUGH_DESKTOP=1, so a plain CLI `enough` can't be taken down by a
   stray POST.
2. When the shell set a per-launch ENOUGH_DESKTOP_TOKEN, the matching
   header is required (403 without it).
3. When it does fire, the supervisor is stopped with only_if_owned=True —
   an *adopted* llama-server has to survive the app quitting, exactly
   like ctrl-c'ing the CLI. The last test asserts that on the real
   LlamaSupervisor, not just on the fake.

Everything runs with scratch ENOUGH_* roots and a fake supervisor, so no
llama-server is spawned and the real ~/enough install is untouched.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from enough import server as _server
from enough.server import create_app
from enough.supervisor import LlamaSupervisor


class FakeSupervisor:
    """Records stop() calls; never touches a real process."""

    def __init__(self, **_kw: Any) -> None:
        self.stop_calls: list[bool] = []
        self.proc = None
        self.adopted_pid = 4242  # pretend we adopted someone else's server
        self.current_ctx = None
        self.ready = True

    async def bootstrap(self) -> None:  # pragma: no cover - trivial
        pass

    async def stop(self, *, only_if_owned: bool = False) -> None:
        self.stop_calls.append(only_if_owned)
        if not only_if_owned:
            self.adopted_pid = None

    def status(self) -> dict[str, Any]:  # pragma: no cover - trivial
        return {"mode": "adopted", "ready": True, "cute": None,
                "ctx": None, "url": "http://localhost:9", "error": None}


@pytest.fixture
def desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A TestClient over create_app() with a fake supervisor + a recorded
    exit hook. Yields (client, fake_supervisor, exit_calls)."""
    project = tmp_path / "project"
    project.mkdir()
    # Every global-state seam onto tmp_path — house rule.
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(tmp_path / "wikisink.json"))
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(tmp_path / "weights"))
    monkeypatch.setenv("ENOUGH_LIVE_STATE", str(tmp_path / "models-state.json"))
    monkeypatch.delenv("ENOUGH_DESKTOP", raising=False)
    monkeypatch.delenv("ENOUGH_DESKTOP_TOKEN", raising=False)

    fake = FakeSupervisor()
    monkeypatch.setattr(_server, "LlamaSupervisor", lambda **kw: fake)

    exit_calls: list[float] = []
    monkeypatch.setattr(_server, "request_process_exit",
                        lambda delay=0.25: exit_calls.append(delay))

    app = create_app(project, "http://localhost:9", supervise=True)
    with TestClient(app) as c:
        yield c, fake, exit_calls


def test_hidden_without_the_desktop_env(desktop):
    client, fake, exit_calls = desktop
    r = client.post("/api/shutdown")
    assert r.status_code == 404
    assert fake.stop_calls == []
    assert exit_calls == []


def test_token_required_when_the_shell_set_one(desktop, monkeypatch: pytest.MonkeyPatch):
    client, fake, exit_calls = desktop
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")
    monkeypatch.setenv("ENOUGH_DESKTOP_TOKEN", "s3cret")

    assert client.post("/api/shutdown").status_code == 403
    assert client.post("/api/shutdown",
                       headers={"X-Enough-Desktop-Token": "wrong"}).status_code == 403
    assert fake.stop_calls == []
    assert exit_calls == []

    r = client.post("/api/shutdown", headers={"X-Enough-Desktop-Token": "s3cret"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "stopping": True}
    assert exit_calls == [0.25]


def test_shutdown_spares_an_adopted_llama_server(desktop, monkeypatch: pytest.MonkeyPatch):
    client, fake, exit_calls = desktop
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")

    r = client.post("/api/shutdown")
    assert r.status_code == 200, r.text
    # only_if_owned=True is the whole point: the adopted pid is still set.
    assert fake.stop_calls[0] is True
    assert fake.adopted_pid == 4242
    assert exit_calls == [0.25]


def test_supervisor_stop_only_if_owned_leaves_adopted_alone():
    """The semantics /api/shutdown leans on, checked on the real class.

    999999 is above macOS's pid ceiling, so if the only_if_owned guard ever
    regressed the SIGTERM would raise ProcessLookupError, be swallowed, and
    clear adopted_pid — which this assertion catches.
    """
    sup = LlamaSupervisor(llm_url="http://127.0.0.1:9")
    sup.adopted_pid = 999999
    asyncio.run(sup.stop(only_if_owned=True))
    assert sup.adopted_pid == 999999
    assert sup.ready is False


def test_request_process_exit_is_scheduled_not_immediate():
    """The real hook must defer the signal, not fire it inline — the
    response has to get out the door first."""
    fired: list[int] = []

    async def scenario() -> None:
        original_kill = os.kill
        try:
            os.kill = lambda pid, sig: fired.append(sig)  # type: ignore[assignment]
            _server.request_process_exit(delay=0.0)
            assert fired == []          # not yet — it's on the loop
            await asyncio.sleep(0.05)
            assert len(fired) == 1      # ...and now it is
        finally:
            os.kill = original_kill

    asyncio.run(scenario())
