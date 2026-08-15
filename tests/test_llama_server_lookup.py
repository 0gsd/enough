"""The llama-server binary lookup: $ENOUGH_LLAMA_SERVER → ~/enough/bin → PATH.

One mechanism for three platforms (docs/tauri-plan.md §4 — the desktop app's
bundled sidecar; docs/linux-plan.md §3.2 — the Linux installer's prebuilt
release in ~/enough/bin; macOS/brew — PATH, as before). Every rung and every
fall-through is pinned here because three different installers now depend on
the order.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from enough import models, supervisor


def _exe(path: Path, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    """Write an executable stand-in binary at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A machine with no llama-server anywhere: scratch HOME, empty PATH,
    no override. Every test opts into exactly the rungs it wants."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.delenv(models.LLAMA_SERVER_ENV, raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# find_llama_server()
# ---------------------------------------------------------------------------

def test_nothing_installed_returns_none(iso: Path):
    assert models.find_llama_server() is None


def test_path_is_the_last_rung(iso: Path, monkeypatch: pytest.MonkeyPatch):
    bindir = iso / "brewish"
    found = _exe(bindir / "llama-server")
    monkeypatch.setenv("PATH", str(bindir))
    assert models.find_llama_server() == str(found)


def test_enough_bin_beats_path(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """~/enough/bin is where the Linux installer puts the pinned release —
    it must win over whatever the distro happens to have packaged."""
    bindir = iso / "brewish"
    _exe(bindir / "llama-server")
    monkeypatch.setenv("PATH", str(bindir))
    mine = _exe(Path(os.environ["HOME"]) / "enough" / "bin" / "llama-server")
    assert models.find_llama_server() == str(mine)


def test_env_override_beats_everything(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """The rung the desktop app's sidecar uses. It has to outrank an existing
    brew install, or enough.app would silently run the user's llama.cpp."""
    bindir = iso / "brewish"
    _exe(bindir / "llama-server")
    monkeypatch.setenv("PATH", str(bindir))
    _exe(Path(os.environ["HOME"]) / "enough" / "bin" / "llama-server")
    sidecar = _exe(iso / "enough.app" / "Contents" / "MacOS" / "llama-server")
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(sidecar))
    assert models.find_llama_server() == str(sidecar)


def test_env_override_expands_tilde(iso: Path, monkeypatch: pytest.MonkeyPatch):
    target = _exe(Path(os.environ["HOME"]) / "custom" / "llama-server")
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, "~/custom/llama-server")
    assert models.find_llama_server() == str(target)


def test_broken_override_falls_through_to_path(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """A stale ENOUGH_LLAMA_SERVER in a shell profile must not make a working
    install unreachable — it falls through (and warns; see the next test)."""
    bindir = iso / "brewish"
    found = _exe(bindir / "llama-server")
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(iso / "nope" / "llama-server"))
    assert models.find_llama_server() == str(found)


def test_broken_override_is_logged(iso: Path, monkeypatch: pytest.MonkeyPatch, caplog):
    """Falling through silently is the confusing failure: you'd be running a
    different llama.cpp than the one you named."""
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(iso / "nope" / "llama-server"))
    with caplog.at_level("WARNING", logger="enough.models"):
        models.find_llama_server()
    assert models.LLAMA_SERVER_ENV in caplog.text


def test_non_executable_candidates_are_skipped(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """A downloaded-but-not-chmod+x binary in ~/enough/bin is a half-finished
    install, not an install."""
    dud = Path(os.environ["HOME"]) / "enough" / "bin" / "llama-server"
    dud.parent.mkdir(parents=True)
    dud.write_text("not executable")
    dud.chmod(0o644)
    bindir = iso / "brewish"
    found = _exe(bindir / "llama-server")
    monkeypatch.setenv("PATH", str(bindir))
    assert models.find_llama_server() == str(found)


def test_directory_named_llama_server_is_not_a_binary(iso: Path):
    (Path(os.environ["HOME"]) / "enough" / "bin" / "llama-server").mkdir(parents=True)
    assert models.find_llama_server() is None


def test_lookup_is_read_per_call(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """Not cached at import: the shell sets the env var in the child it
    spawns, and a QA harness moves HOME under a running suite."""
    assert models.find_llama_server() is None
    sidecar = _exe(iso / "late" / "llama-server")
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(sidecar))
    assert models.find_llama_server() == str(sidecar)


# ---------------------------------------------------------------------------
# The consumers
# ---------------------------------------------------------------------------

def test_llama_release_uses_the_lookup(iso: Path, monkeypatch: pytest.MonkeyPatch):
    """`llama_release()` with no argument must probe the binary the
    supervisor would actually launch, not whatever `llama-server` resolves to
    on PATH — otherwise the picker gates models on the wrong build."""
    sidecar = _exe(
        iso / "side" / "llama-server",
        "#!/bin/sh\necho 'version: 10362 (deadbeef)'\n",
    )
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(sidecar))
    assert models.llama_release() == 10362


def test_llama_release_is_zero_without_a_binary(iso: Path):
    assert models.llama_release() == 0


def test_llama_release_still_takes_an_explicit_binary(iso: Path):
    """The supervisor resolves once and passes the path down, so the version
    it gates on is the version it runs."""
    explicit = _exe(
        iso / "explicit" / "llama-server",
        "#!/bin/sh\necho 'version: 9200 (cafe)'\n",
    )
    assert models.llama_release(str(explicit)) == 9200


def test_supervisor_launch_reports_the_whole_lookup_order(
    iso: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The "not found" message is the only place a user learns where enough
    looked, so it names all three rungs."""
    monkeypatch.setattr(
        models, "resolve",
        lambda cute: {"installed": True, "path": str(iso / "m.gguf"), "filename": "m.gguf"},
    )
    sup = supervisor.LlamaSupervisor(llm_url="http://127.0.0.1:1")
    with pytest.raises(RuntimeError) as e:
        sup._launch("tiny", 4096)
    msg = str(e.value)
    assert "ENOUGH_LLAMA_SERVER" in msg
    assert "~/enough/bin" in msg
    assert "PATH" in msg


def test_supervisor_launch_uses_the_override(
    iso: Path, monkeypatch: pytest.MonkeyPatch,
):
    """End to end through the seam the desktop app depends on: the argv the
    supervisor builds starts with the sidecar path."""
    gguf = iso / "m.gguf"
    gguf.write_bytes(b"\0")
    sidecar = _exe(iso / "side" / "llama-server")
    monkeypatch.setenv(models.LLAMA_SERVER_ENV, str(sidecar))
    monkeypatch.setattr(
        models, "resolve",
        lambda cute: {
            "installed": True, "path": str(gguf), "filename": "m.gguf",
            "llama_cpp_min_release": 9200, "label": "Tiny",
        },
    )
    monkeypatch.setattr(models, "spec_flags", lambda info, binary=None: [])
    monkeypatch.setattr(models, "draft_flags", lambda info, binary=None: [])

    seen: dict = {}

    # Note: `subprocess.run` is itself built on Popen, so faking Popen also
    # fakes the version probe — hence llama_release is stubbed rather than
    # left to shell out. It records what it was handed, which is the other
    # half of the contract: the release we gate on is the binary we launch.
    def fake_release(binary=None):
        seen["probed"] = binary
        return 10362

    monkeypatch.setattr(models, "llama_release", fake_release)

    class FakePopen:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
            self.pid = 4321

    monkeypatch.setattr(supervisor.subprocess, "Popen", FakePopen)
    sup = supervisor.LlamaSupervisor(llm_url="http://127.0.0.1:1")
    sup._launch("tiny", 4096)
    assert seen["cmd"][0] == str(sidecar)
    assert seen["probed"] == str(sidecar)
