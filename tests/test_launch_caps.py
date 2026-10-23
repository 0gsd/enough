"""llama-server memory caps on machines under 32 GB (the 16 GB context fix).

docs/ctx-16gb-plan.md §3c/§8.2: below 32 GB of RAM a launch passes
`--ctx-checkpoints 2 --cache-ram 2048` — each flag only when the binary's
`--help` lists it, probed once per binary path + mtime, so an older llama.cpp
still starts. Two launchers apply the rule: `supervisor._launch` (through
`models.launch_caps`) and `llama_server.sh` (in shell). Both are exercised
here against a stand-in llama-server; nothing real is started.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

from enough import models

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "llama_server.sh"

HELP_BOTH = """\
-c,    --ctx-size N                     size of the prompt context
-ctxcp, --ctx-checkpoints, --swa-checkpoints N
                                        max number of context checkpoints to create per slot
-cram, --cache-ram N                    set the maximum cache size in MiB (default: 8192)
"""
HELP_OLD = """\
-c,    --ctx-size N                     size of the prompt context
--swa-checkpoints N                     max number of SWA checkpoints per slot
--cache-ram-ish N                       not the flag we want
"""
HELP_RAM_ONLY = """\
-c,    --ctx-size N                     size of the prompt context
-cram, --cache-ram N                    set the maximum cache size in MiB
"""


def fake_llama(path: Path, help_text: str, *, log: Path | None = None) -> Path:
    """A llama-server stand-in: `--help` prints `help_text` (and counts the
    call in `log`), `--version` a release, anything else records its argv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    log = log or path.parent / "calls.log"
    path.write_text(
        "#!/bin/sh\n"
        f"if [ \"$1\" = \"--help\" ]; then echo help >> '{log}'; cat <<'EOF'\n"
        f"{help_text}EOF\n"
        "exit 0; fi\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'version: 9200 (fake)'; exit 0; fi\n"
        f"echo \"$@\" > '{path.parent / 'argv.txt'}'\n",
        encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture(autouse=True)
def clean_cache():
    models._HELP_FLAGS_CACHE.clear()
    yield
    models._HELP_FLAGS_CACHE.clear()


def help_calls(binary: Path) -> int:
    log = binary.parent / "calls.log"
    return len(log.read_text().splitlines()) if log.is_file() else 0


# ---------------------------------------------------------------------------
# models.llama_server_flags / launch_caps
# ---------------------------------------------------------------------------

def test_the_help_probe_reads_long_flags(tmp_path: Path):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_BOTH)
    flags = models.llama_server_flags(str(b))
    assert {"--ctx-checkpoints", "--swa-checkpoints", "--cache-ram", "--ctx-size"} <= flags
    assert "-ctxcp" not in flags          # short forms are not what we pass


def test_the_probe_is_cached_per_path_and_mtime(tmp_path: Path):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_BOTH)
    models.llama_server_flags(str(b))
    models.llama_server_flags(str(b))
    assert help_calls(b) == 1
    # A `brew upgrade` replaces the file: new mtime, new probe.
    fake_llama(b, HELP_RAM_ONLY)
    st = b.stat()
    os.utime(b, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert "--ctx-checkpoints" not in models.llama_server_flags(str(b))
    assert help_calls(b) == 2


def test_a_missing_or_broken_binary_lists_nothing(tmp_path: Path):
    assert models.llama_server_flags(None) == frozenset()
    assert models.llama_server_flags(str(tmp_path / "nope")) == frozenset()
    dud = tmp_path / "dud"
    dud.write_text("not a program")
    dud.chmod(0o755)
    assert models.llama_server_flags(str(dud)) == frozenset()


def test_under_32_gb_both_caps_when_the_help_lists_them(tmp_path: Path):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_BOTH)
    argv, note = models.launch_caps(str(b), ram_gb=16)
    assert argv == ["--ctx-checkpoints", "2", "--cache-ram", "2048"]
    assert "applied --ctx-checkpoints 2 --cache-ram 2048" in note
    assert "16 GB" in note


def test_an_older_build_gets_only_what_it_knows(tmp_path: Path):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_RAM_ONLY)
    argv, note = models.launch_caps(str(b), ram_gb=24)
    assert argv == ["--cache-ram", "2048"]
    assert "skipped --ctx-checkpoints" in note and "does not list it" in note


def test_flags_the_help_does_not_list_are_never_passed(tmp_path: Path):
    """`--swa-checkpoints` and `--cache-ram-ish` are not the flags we want;
    a whole-word match keeps them from passing for them."""
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_OLD)
    argv, note = models.launch_caps(str(b), ram_gb=16)
    assert argv == []
    assert "none applied" in note


def test_at_32_gb_and_up_no_caps_and_no_probe(tmp_path: Path):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_BOTH)
    for gb in (32, 64, 96):
        argv, note = models.launch_caps(str(b), ram_gb=gb)
        assert argv == [] and "none" in note
    assert help_calls(b) == 0


def test_the_ram_comes_from_total_ram_gb_by_default(tmp_path: Path, monkeypatch):
    b = fake_llama(tmp_path / "bin" / "llama-server", HELP_BOTH)
    monkeypatch.setattr(models, "total_ram_gb", lambda: 18)
    assert models.launch_caps(str(b))[0] == ["--ctx-checkpoints", "2", "--cache-ram", "2048"]
    monkeypatch.setattr(models, "total_ram_gb", lambda: 36)
    assert models.launch_caps(str(b))[0] == []


# ---------------------------------------------------------------------------
# supervisor._launch
# ---------------------------------------------------------------------------

@pytest.fixture
def launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`_launch` with a stand-in binary and a recorded Popen. Returns
    (run(ram_gb, help_text) -> argv)."""
    from enough import supervisor as sup

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    gguf = tmp_path / "m.gguf"
    gguf.write_bytes(b"\0")
    monkeypatch.setattr(models, "resolve", lambda cute=None: {
        "cute": "tiny", "label": "Tiny", "filename": "m.gguf", "path": str(gguf),
        "installed": True, "spec_args": "", "llama_cpp_min_release": 0,
        "draft_filename": None, "draft_path": None})
    seen: list[list[str]] = []

    class _Proc:
        pid = 4242

    def run(ram_gb: int, help_text: str) -> list[str]:
        b = fake_llama(tmp_path / "bin" / "llama-server", help_text)
        monkeypatch.setattr(models, "find_llama_server", lambda: str(b))
        monkeypatch.setattr(models, "total_ram_gb", lambda: ram_gb)
        # Probe the stand-in for real first: the probe is cached per path +
        # mtime, so `_launch` reads the cache — and the Popen faked below
        # (which subprocess.run is built on) only ever sees the launch.
        assert models.llama_server_flags(str(b))
        monkeypatch.setattr(sup.subprocess, "Popen",
                            lambda cmd, **kw: (seen.append(list(cmd)), _Proc())[1])
        sup.LlamaSupervisor(llm_url="http://127.0.0.1:1")._launch("tiny", 32768)
        assert len(seen) == 1
        return seen[0]

    return run


def test_launch_under_32_gb_carries_the_caps(launch, caplog, tmp_path: Path):
    with caplog.at_level("INFO", logger="enough.supervisor"):
        cmd = launch(16, HELP_BOTH)
    # …and the same line heads this launch in server.log, where it is seen.
    server_log = tmp_path / "home" / "enough" / ".llama-server" / "server.log"
    assert "[enough] memory caps (16 GB RAM" in server_log.read_text()
    i = cmd.index("--ctx-checkpoints")
    assert cmd[i + 1] == "2"
    j = cmd.index("--cache-ram")
    assert cmd[j + 1] == "2048"
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "32768"
    lines = [r.getMessage() for r in caplog.records if "memory caps" in r.getMessage()]
    assert len(lines) == 1 and "applied" in lines[0]


def test_launch_skips_what_the_build_does_not_list(launch, caplog):
    with caplog.at_level("INFO", logger="enough.supervisor"):
        cmd = launch(16, HELP_RAM_ONLY)
    assert "--ctx-checkpoints" not in cmd
    assert cmd[cmd.index("--cache-ram") + 1] == "2048"
    assert any("skipped --ctx-checkpoints" in r.getMessage() for r in caplog.records)


def test_launch_at_32_gb_is_unchanged(launch, caplog):
    with caplog.at_level("INFO", logger="enough.supervisor"):
        cmd = launch(32, HELP_BOTH)
    assert "--ctx-checkpoints" not in cmd and "--cache-ram" not in cmd
    assert any("memory caps: none (32 GB RAM" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# llama_server.sh — the same rule in shell
# ---------------------------------------------------------------------------

def test_the_script_still_parses():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_the_script_carries_the_rule():
    """The shell half of §8.2, by inspection: a RAM probe, the 32 GB line,
    the --help check, both caps, and the caps reaching the argv."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "sysctl -n hw.memsize" in text and "/proc/meminfo" in text
    assert '-ge 32' in text
    assert '--help' in text and "help_lists_flag" in text
    assert "CAP_ARGS+=(--ctx-checkpoints 2)" in text
    assert "CAP_ARGS+=(--cache-ram 2048)" in text
    assert '${CAP_ARGS[@]+"${CAP_ARGS[@]}"}' in text
    assert "resolve_cap_flags" in text


def _tool_dir(tmp_path: Path, ram_bytes: int, help_text: str) -> tuple[Path, Path]:
    """A PATH holding only what the script needs: real coreutils by symlink,
    plus a fake sysctl (the machine's RAM), a fake curl (health is always
    200) and the stand-in llama-server. No `uv`, so the script falls back to
    `command -v llama-server`."""
    bindir = tmp_path / "path"
    bindir.mkdir()
    for tool in ("dirname", "mkdir", "cat", "seq", "sleep", "nohup", "grep",
                 "awk", "sed", "head", "uname", "rm", "env"):
        real = shutil.which(tool)
        if real:
            (bindir / tool).symlink_to(real)
    for name, body in (("sysctl", f"#!/bin/sh\necho {ram_bytes}\n"),
                       ("curl", "#!/bin/sh\nprintf 200\n")):
        p = bindir / name
        p.write_text(body)
        p.chmod(0o755)
    llama = fake_llama(bindir / "llama-server", help_text, log=tmp_path / "help.log")
    return bindir, llama


def _run_script(tmp_path: Path, ram_gb: int, help_text: str) -> tuple[str, list[str]]:
    if not Path("/bin/bash").exists():
        pytest.skip("no /bin/bash")
    work = tmp_path / "install"
    work.mkdir()
    script = work / "llama_server.sh"
    shutil.copyfile(SCRIPT, script)        # its state dir lands beside it
    bindir, llama = _tool_dir(tmp_path, ram_gb * 1024 ** 3, help_text)
    gguf = tmp_path / "m.gguf"
    gguf.write_bytes(b"\0")
    env = {"PATH": str(bindir), "HOME": str(tmp_path / "home"),
           "MODEL": str(gguf), "CTX": "32768", "PORT": "8099", "SPEC": "off"}
    out = subprocess.run(["/bin/bash", str(script), "start"], env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    argv_file = llama.parent / "argv.txt"
    for _ in range(100):                   # nohup'd into the background
        if argv_file.is_file() and argv_file.read_text().strip():
            break
        time.sleep(0.05)
    return out.stdout, argv_file.read_text().split()


def test_the_script_caps_a_small_machine(tmp_path: Path):
    stdout, argv = _run_script(tmp_path, 16, HELP_BOTH)
    i = argv.index("--ctx-checkpoints")
    assert argv[i + 1] == "2"
    assert argv[argv.index("--cache-ram") + 1] == "2048"
    assert "caps:" in stdout and "applied --ctx-checkpoints 2 --cache-ram 2048" in stdout


def test_the_script_passes_only_listed_flags(tmp_path: Path):
    stdout, argv = _run_script(tmp_path, 16, HELP_OLD)
    assert "--ctx-checkpoints" not in argv and "--cache-ram" not in argv
    assert "skipped --ctx-checkpoints --cache-ram" in stdout


def test_the_script_leaves_a_big_machine_alone(tmp_path: Path):
    stdout, argv = _run_script(tmp_path, 64, HELP_BOTH)
    assert "--ctx-checkpoints" not in argv and "--cache-ram" not in argv
    assert "caps:  none (64 GB RAM" in stdout
    assert not (tmp_path / "help.log").exists()      # never even asked
