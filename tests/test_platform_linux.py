"""The Linux port's platform seams (docs/linux-plan.md §3.1).

Everything macOS-shaped that had to grow a second branch, pinned here so a
future edit can't quietly re-macOS-ify it:

- `supervisor._find_pid_on_port` — pidfile → lsof → `ss -ltnp`.
- `/api/reveal` — `open -R` on macOS, `xdg-open` on Linux, 501 elsewhere.
- `models.install_hint` — the per-platform clause in absence messages.
- `models.total_ram_gb` — the `/proc/meminfo` branch actually firing on a
  Linux runner (the §3.4 marker test), and `sysctl` on a Mac.

The `ss`/`lsof` tests run on every platform: both probes are driven through
`subprocess.check_output`, so a scripted stand-in exercises the parsing on
whatever host CI happens to be, which is the point — the macOS job proves
the Linux fallback parses too.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import models, supervisor
from enough.server import create_app


# ---------------------------------------------------------------------------
# supervisor._find_pid_on_port — the ss fallback
# ---------------------------------------------------------------------------

# Real `ss -ltnp` output (iproute2 6.1, Ubuntu 24.04), trimmed. Note the
# mixed v4/v6 rows and the unnamed process (a listener the caller doesn't
# own — ss shows no users:(…) for those).
SS_OUTPUT = """\
State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
LISTEN 0      4096        127.0.0.53%lo:53         0.0.0.0:*     users:(("systemd-resolve",pid=712,fd=14))
LISTEN 0      511             127.0.0.1:8080       0.0.0.0:*     users:(("llama-server",pid=90210,fd=17))
LISTEN 0      4096              0.0.0.0:22         0.0.0.0:*
LISTEN 0      511                  [::]:3456          [::]:*     users:(("python3",pid=4242,fd=9))
"""


@pytest.fixture
def no_pidfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A scratch HOME, so the pidfile fast path can't find the real
    install's `~/enough/.llama-server/server.pid` and short-circuit."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _script(monkeypatch: pytest.MonkeyPatch, table: dict[str, object]) -> None:
    """Replace subprocess.check_output with a table keyed by argv[0]. A
    value that is an Exception instance is raised; anything else is
    returned as the command's stdout."""
    def fake(cmd, *a, **k):  # noqa: ANN001
        got = table.get(cmd[0], FileNotFoundError(cmd[0]))
        if isinstance(got, BaseException):
            raise got
        return got
    monkeypatch.setattr(supervisor.subprocess, "check_output", fake)


def test_ss_parses_the_listening_pid(monkeypatch: pytest.MonkeyPatch):
    _script(monkeypatch, {"ss": SS_OUTPUT})
    assert supervisor._pid_via_ss(8080) == 90210
    assert supervisor._pid_via_ss(3456) == 4242      # the [::] row


def test_ss_ignores_ports_that_merely_look_similar(monkeypatch: pytest.MonkeyPatch):
    _script(monkeypatch, {"ss": SS_OUTPUT})
    assert supervisor._pid_via_ss(80) is None        # not a suffix match
    assert supervisor._pid_via_ss(22) is None        # listening, but unnamed
    assert supervisor._pid_via_ss(9999) is None


def test_ss_absent_is_not_an_error(monkeypatch: pytest.MonkeyPatch):
    """macOS has no `ss` at all — that has to read as "don't know", not as
    a crash inside the adopt path."""
    _script(monkeypatch, {})
    assert supervisor._pid_via_ss(8080) is None


def test_find_pid_falls_back_from_lsof_to_ss(no_pidfile, monkeypatch: pytest.MonkeyPatch):
    """The Ubuntu 24.04 shape: no lsof installed, ss present."""
    _script(monkeypatch, {"ss": SS_OUTPUT})
    assert supervisor._find_pid_on_port(8080) == 90210


def test_find_pid_prefers_lsof_when_present(no_pidfile, monkeypatch: pytest.MonkeyPatch):
    _script(monkeypatch, {"lsof": "31337\n", "ss": SS_OUTPUT})
    assert supervisor._find_pid_on_port(8080) == 31337


def test_find_pid_with_neither_tool(no_pidfile, monkeypatch: pytest.MonkeyPatch):
    _script(monkeypatch, {})
    assert supervisor._find_pid_on_port(8080) is None


def test_find_pid_pidfile_beats_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The fast path stays first: our own pidfile wins without shelling
    out at all."""
    home = tmp_path / "home"
    (home / "enough" / ".llama-server").mkdir(parents=True)
    (home / "enough" / ".llama-server" / "server.pid").write_text(str(os.getpid()))
    monkeypatch.setenv("HOME", str(home))
    _script(monkeypatch, {"lsof": "31337\n", "ss": SS_OUTPUT})
    assert supervisor._find_pid_on_port(8080) == os.getpid()


# ---------------------------------------------------------------------------
# models.install_hint
# ---------------------------------------------------------------------------

def test_install_hint_picks_by_platform(monkeypatch: pytest.MonkeyPatch):
    for plat, want in (("darwin", "mac"), ("linux", "pen"), ("linux2", "pen"),
                       ("win32", "other")):
        monkeypatch.setattr(models.sys, "platform", plat)
        assert models.install_hint(mac="mac", linux="pen", other="other") == want


def test_install_hint_unknown_platform_falls_back_to_mac_wording(
    monkeypatch: pytest.MonkeyPatch,
):
    """Better to name the package with the wrong package manager than to
    say nothing at all."""
    monkeypatch.setattr(models.sys, "platform", "freebsd14")
    assert models.install_hint(mac="brew install x", linux="apt install x") == "brew install x"


def test_release_gate_hint_is_platform_specific(monkeypatch: pytest.MonkeyPatch):
    info = {"label": "Big Model", "llama_cpp_min_release": 9999}
    monkeypatch.setattr(models, "llama_release", lambda binary=None: 9000)

    monkeypatch.setattr(models.sys, "platform", "darwin")
    assert "brew upgrade llama.cpp" in (models.release_gate(info) or "")

    monkeypatch.setattr(models.sys, "platform", "linux")
    msg = models.release_gate(info) or ""
    assert "brew" not in msg
    assert "bootstrap.sh" in msg and "~/enough/bin" in msg


# ---------------------------------------------------------------------------
# /api/reveal
# ---------------------------------------------------------------------------

@pytest.fixture
def reveal_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A server over a scratch project, with every global-state hook and
    HOME pointed at tmp_path (house rule: never touch the real install)."""
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(tmp_path / "wikisink.json"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    project = tmp_path / "project"
    project.mkdir()
    (project / "note.md").write_text("hi", encoding="utf-8")
    (project / "folder").mkdir()
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c, project


def _spawned(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Capture subprocess.Popen argv instead of actually opening anything."""
    from enough import server as _server
    calls: list[list[str]] = []

    def fake_popen(cmd, *a, **k):  # noqa: ANN001
        calls.append(list(cmd))
        return None
    monkeypatch.setattr(_server.subprocess, "Popen", fake_popen)
    return calls


def test_reveal_uses_open_dash_r_on_macos(reveal_client, monkeypatch: pytest.MonkeyPatch):
    client, _project = reveal_client
    monkeypatch.setattr(sys, "platform", "darwin")
    calls = _spawned(monkeypatch)
    r = client.get("/api/reveal", params={"path": "note.md"})
    assert r.status_code == 200, r.text
    assert calls[0][:2] == ["/usr/bin/open", "-R"]
    assert "Finder" in r.text


def test_reveal_uses_xdg_open_on_linux(reveal_client, monkeypatch: pytest.MonkeyPatch):
    client, project = reveal_client
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/xdg-open")
    calls = _spawned(monkeypatch)
    r = client.get("/api/reveal", params={"path": "folder"})
    assert r.status_code == 200, r.text
    assert calls[0] == ["/usr/bin/xdg-open", str((project / "folder").resolve())]
    assert "Finder" not in r.text


def test_reveal_of_a_file_on_linux_opens_its_parent(
    reveal_client, monkeypatch: pytest.MonkeyPatch,
):
    """xdg-open has no `-R`; opening the file itself would *launch* it in
    its default app, which is not what reveal means."""
    client, project = reveal_client
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/xdg-open")
    calls = _spawned(monkeypatch)
    r = client.get("/api/reveal", params={"path": "note.md"})
    assert r.status_code == 200, r.text
    assert calls[0] == ["/usr/bin/xdg-open", str(project.resolve())]


def test_reveal_without_xdg_open_says_how_to_install_it(
    reveal_client, monkeypatch: pytest.MonkeyPatch,
):
    client, _project = reveal_client
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: None)
    r = client.get("/api/reveal", params={"path": "note.md"})
    assert r.status_code == 501
    assert "xdg-utils" in r.text


def test_reveal_on_an_unsupported_platform_no_longer_says_macos_only(
    reveal_client, monkeypatch: pytest.MonkeyPatch,
):
    client, _project = reveal_client
    monkeypatch.setattr(sys, "platform", "win32")
    r = client.get("/api/reveal", params={"path": "note.md"})
    assert r.status_code == 501
    assert "macOS-only" not in r.text
    assert "xdg-open" in r.text and "win32" in r.text


# ---------------------------------------------------------------------------
# total_ram_gb — the §3.4 marker test: the right branch on the real runner
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="linux only")
def test_total_ram_gb_reads_real_meminfo_on_linux():
    """On a Linux runner the `/proc/meminfo` branch must be the one that
    answers — and answer with the real number, not the 16 GB fallback."""
    assert models.MEMINFO.is_file()
    want = 0
    for line in models.MEMINFO.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            want = int(line.split()[1]) // (1024 ** 2)
            break
    assert want > 0
    assert models.total_ram_gb() == want


@pytest.mark.skipif(sys.platform != "darwin", reason="macos only")
def test_total_ram_gb_reads_real_sysctl_on_macos():
    out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
    assert models.total_ram_gb() == int(out.strip()) // (1024 ** 3)
