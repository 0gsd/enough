"""The 0.1.7 model-registry growth: separate-file MTP drafts, per-model
llama.cpp gates, machine-feasibility verdicts, and the `install-menu` CLI
that bootstrap.sh renders as a per-model install picker.

`enough.models` points LIVE_STATE / WEIGHTS_DIR at the real ~/enough, so
every test here redirects both at tmp_path first — nothing may read or
write the user's actual install (see the `iso` fixture).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from enough import models


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fake_registry() -> dict:
    """A miniature registry covering all three entry shapes: plain,
    embedded-head MTP, and separate-draft-file MTP behind a hard gate."""
    return {
        "default": "tiny",
        "models": {
            "tiny": {
                "cute_name": "TINY",
                "label": "Tiny 1B",
                "family": "test",
                "gguf_filename": "tiny.gguf",
                "gguf_url": "https://example.invalid/tiny.gguf",
                "disk_gb_approx": 2.0,
                "ram_gb_recommended_min": 8,
                "ctx_max": 32768,
                "ctx_defaults": {
                    "gte_64gb": 32768, "gte_32gb": 16384,
                    "gte_16gb": 8192, "lt_16gb": 4096,
                },
            },
            "embed": {
                "cute_name": "EMBED",
                "label": "Embedded MTP 9B",
                "family": "test",
                "gguf_filename": "embed.gguf",
                "gguf_url": "https://example.invalid/embed.gguf",
                "disk_gb_approx": 6.0,
                "ram_gb_recommended_min": 10,
                "ctx_max": 32768,
                "ctx_defaults": {
                    "gte_64gb": 32768, "gte_32gb": 16384,
                    "gte_16gb": 8192, "lt_16gb": 4096,
                },
                "mtp": {
                    "spec_type": "draft-mtp",
                    "spec_draft_n_max": 3,
                    "llama_cpp_min_release": 9180,
                },
            },
            "drafty": {
                "cute_name": "DRAFTY",
                "label": "Draft-file MTP 27B",
                "family": "test",
                "gguf_filename": "drafty.gguf",
                "gguf_url": "https://example.invalid/drafty.gguf",
                "disk_gb_approx": 19.0,
                "ram_gb_recommended_min": 24,
                "ctx_max": 262144,
                "llama_cpp_min_release": 9200,
                "ctx_defaults": {
                    "gte_64gb": 65536, "gte_32gb": 32768,
                    "gte_16gb": 8192, "lt_16gb": 4096,
                },
                "mtp": {
                    "spec_type": "draft-mtp",
                    "spec_draft_n_max": 3,
                    "llama_cpp_min_release": 9200,
                    "draft_gguf_filename": "mtp-drafty.gguf",
                    "draft_gguf_url": "https://example.invalid/mtp-drafty.gguf",
                    "draft_disk_gb_approx": 1.7,
                },
            },
        },
    }


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module's three real-install paths at tmp_path and install
    the fake registry. Returns the scratch weights dir."""
    weights = tmp_path / "weights"
    weights.mkdir()
    reg = tmp_path / "models-template.json"
    reg.write_text(json.dumps(_fake_registry()), encoding="utf-8")
    monkeypatch.setattr(models, "WEIGHTS_DIR", weights)
    monkeypatch.setattr(models, "LIVE_STATE", tmp_path / "config" / "models.json")
    monkeypatch.setattr(models, "REGISTRY_TEMPLATE", reg)
    return weights


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch):
    """Fake this machine's RAM / free disk / llama.cpp release. Defaults
    are generous so tests only state the axis they care about."""
    def _set(*, ram_gb: int = 128, free_gb: float = 500.0, release: int = 9200):
        monkeypatch.setattr(models, "total_ram_gb", lambda: ram_gb)
        monkeypatch.setattr(models, "free_disk_gb", lambda: free_gb)
        monkeypatch.setattr(models, "llama_release", lambda binary="llama-server": release)
    _set()
    return _set


def _entry(cute: str) -> dict:
    return _fake_registry()["models"][cute]


# ---------------------------------------------------------------------------
# feasibility()
# ---------------------------------------------------------------------------

def test_feasibility_good_with_ample_ram_and_disk(iso: Path, host):
    host(ram_gb=64, free_gb=200.0)
    v = models.feasibility(_entry("drafty"))
    assert v["verdict"] == "good"
    assert v["reasons"] == []          # nothing to warn about


def test_feasibility_tight_when_ram_only_just_meets_minimum(iso: Path, host):
    # 24 GB ask, 24 GB machine: runs, but under the +8 GB headroom bar.
    host(ram_gb=24, free_gb=500.0)
    v = models.feasibility(_entry("drafty"))
    assert v["verdict"] == "tight"
    assert any("24 GB RAM" in r for r in v["reasons"])


def test_feasibility_no_when_ram_below_minimum(iso: Path, host):
    host(ram_gb=16, free_gb=500.0)
    v = models.feasibility(_entry("drafty"))
    assert v["verdict"] == "no"
    assert any("wants 24 GB RAM, this machine has 16" in r for r in v["reasons"])


def test_feasibility_disk_tiers(iso: Path, host):
    # drafty downloads 19.0 + 1.7 draft = 20.7 GB.
    # good needs 20.7*1.2 + 10 = 34.8; tight needs 20.7 + 2 = 22.7.
    host(ram_gb=128, free_gb=40.0)
    assert models.feasibility(_entry("drafty"))["verdict"] == "good"
    host(ram_gb=128, free_gb=25.0)
    assert models.feasibility(_entry("drafty"))["verdict"] == "tight"
    host(ram_gb=128, free_gb=21.0)
    v = models.feasibility(_entry("drafty"))
    assert v["verdict"] == "no"
    assert any("needs ~21 GB free, you have 21" in r for r in v["reasons"])


def test_feasibility_counts_the_draft_file(iso: Path, host):
    """22 GB free clears the plain 19 GB model but not 19 + 1.7 draft."""
    plain = dict(_entry("drafty"))
    plain.pop("mtp")
    host(ram_gb=128, free_gb=21.5)
    assert models.feasibility(plain)["verdict"] == "tight"
    assert models.feasibility(_entry("drafty"))["verdict"] == "no"


def test_feasibility_worst_axis_wins(iso: Path, host):
    # Plenty of disk, nowhere near enough RAM.
    host(ram_gb=8, free_gb=1000.0)
    assert models.feasibility(_entry("drafty"))["verdict"] == "no"
    # Plenty of RAM, no disk.
    host(ram_gb=256, free_gb=1.0)
    assert models.feasibility(_entry("drafty"))["verdict"] == "no"


def test_resolve_carries_the_verdict(iso: Path, host):
    host(ram_gb=8, free_gb=1000.0)
    assert models.resolve("drafty")["feasibility"]["verdict"] == "no"


# ---------------------------------------------------------------------------
# Draft-file resolution + flags
# ---------------------------------------------------------------------------

def test_draft_path_is_none_until_the_file_exists(iso: Path, host):
    (iso / "drafty.gguf").write_bytes(b"x")
    info = models.resolve("drafty")
    assert info["installed"] is True          # main gguf alone decides this
    assert info["draft_filename"] == "mtp-drafty.gguf"
    assert info["draft_path"] is None
    assert info["draft_installed"] is False
    assert info["draft_disk_gb_approx"] == 1.7


def test_draft_path_resolves_when_downloaded(iso: Path, host):
    (iso / "drafty.gguf").write_bytes(b"x")
    (iso / "mtp-drafty.gguf").write_bytes(b"x")
    info = models.resolve("drafty")
    assert info["draft_path"] == str(iso / "mtp-drafty.gguf")
    assert info["draft_installed"] is True
    assert models.draft_flags(info) == ["--spec-draft-model", str(iso / "mtp-drafty.gguf")]


def test_missing_draft_means_a_plain_launch_not_an_error(iso: Path, host):
    """Declared-but-absent draft: no spec flags, no draft flags, no raise."""
    (iso / "drafty.gguf").write_bytes(b"x")
    info = models.resolve("drafty")
    assert models.spec_flags(info) == []
    assert models.draft_flags(info) == []


def test_embedded_mtp_entries_are_unaffected(iso: Path, host):
    """q35/q36-style models keep working with no draft file anywhere."""
    (iso / "embed.gguf").write_bytes(b"x")
    info = models.resolve("embed")
    assert info["draft_filename"] is None
    assert info["draft_path"] is None
    assert models.spec_flags(info) == ["--spec-type", "draft-mtp", "--spec-draft-n-max", "3"]
    assert models.draft_flags(info) == []


def test_draft_flags_stay_empty_when_the_release_is_too_old(iso: Path, host):
    (iso / "drafty.gguf").write_bytes(b"x")
    (iso / "mtp-drafty.gguf").write_bytes(b"x")
    host(release=9100)
    info = models.resolve("drafty")
    assert models.spec_flags(info) == []
    assert models.draft_flags(info) == []   # never -md without --spec-type


# ---------------------------------------------------------------------------
# release_gate()
# ---------------------------------------------------------------------------

def test_release_gate_passes_ungated_models(iso: Path, host):
    host(release=1)
    assert models.release_gate(models.resolve("tiny")) is None
    assert models.release_gate(models.resolve("embed")) is None


def test_release_gate_passes_when_the_build_is_new_enough(iso: Path, host):
    host(release=9200)
    assert models.release_gate(models.resolve("drafty")) is None


def test_release_gate_names_the_release_and_the_fix(iso: Path, host):
    host(release=9100)
    msg = models.release_gate(models.resolve("drafty"))
    assert msg is not None
    assert "b9200" in msg and "b9100" in msg
    assert "brew upgrade llama.cpp" in msg
    assert "Draft-file MTP 27B" in msg


def test_release_gate_when_llama_cpp_is_absent(iso: Path, host):
    host(release=0)
    msg = models.release_gate(models.resolve("drafty"))
    assert msg is not None and "no llama.cpp on PATH" in msg


# ---------------------------------------------------------------------------
# install-menu
# ---------------------------------------------------------------------------

def test_install_menu_rows_size_includes_draft(iso: Path, host):
    rows = {r["cute"]: r for r in models.install_menu_rows()}
    assert rows["drafty"]["size_gb"] == 20.7
    assert rows["drafty"]["draft_disk_gb_approx"] == 1.7
    assert rows["tiny"]["draft_disk_gb_approx"] is None


def test_install_menu_default_yes_only_for_good_and_small(iso: Path, host):
    host(ram_gb=128, free_gb=1000.0)     # everything is "good"
    rows = {r["cute"]: r for r in models.install_menu_rows()}
    assert rows["tiny"]["default_yes"] is True        # 2.0 GB
    assert rows["embed"]["default_yes"] is True       # 6.0 GB
    assert rows["drafty"]["default_yes"] is False     # 20.7 GB, good but big


def test_install_menu_default_no_when_already_installed(iso: Path, host):
    (iso / "tiny.gguf").write_bytes(b"x")
    rows = {r["cute"]: r for r in models.install_menu_rows()}
    assert rows["tiny"]["installed"] is True
    assert rows["tiny"]["default_yes"] is False


def test_install_menu_text_output(iso: Path, host, capsys: pytest.CaptureFixture[str]):
    host(ram_gb=16, free_gb=1000.0)   # tiny good, embed tight, drafty no
    assert models.main(["install-menu"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("✓ tiny")
    assert lines[1].startswith("~ embed")
    assert lines[2].startswith("✗ drafty")
    assert "20.7 GB (incl. 1.7 draft)" in lines[2]
    assert "wants 24 GB RAM, this machine has 16" in lines[2]


def test_install_menu_marks_installed_models(iso: Path, host, capsys: pytest.CaptureFixture[str]):
    (iso / "tiny.gguf").write_bytes(b"x")
    models.main(["install-menu"])
    out = capsys.readouterr().out
    assert "already installed" in out.splitlines()[0]


def test_install_menu_json(iso: Path, host, capsys: pytest.CaptureFixture[str]):
    host(ram_gb=16, free_gb=1000.0)
    assert models.main(["install-menu", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r["cute"] for r in rows] == ["tiny", "embed", "drafty"]
    drafty = rows[-1]
    assert drafty["verdict"] == "no"
    assert drafty["size_gb"] == 20.7
    assert drafty["llama_cpp_min_release"] == 9200
    assert drafty["reasons"]


# ---------------------------------------------------------------------------
# params CLI (what llama_server.sh eval's)
# ---------------------------------------------------------------------------

def test_params_emits_draft_path_and_min_release(iso: Path, host, capsys):
    (iso / "drafty.gguf").write_bytes(b"x")
    (iso / "mtp-drafty.gguf").write_bytes(b"x")
    assert models.main(["params", "--cute", "drafty"]) == 0
    out = dict(
        line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines()
    )
    assert out["MIN_RELEASE"] == "9200"
    assert out["DRAFT_PATH"].strip("'") == str(iso / "mtp-drafty.gguf")


def test_params_draft_path_is_empty_when_absent(iso: Path, host, capsys):
    (iso / "tiny.gguf").write_bytes(b"x")
    models.main(["params", "--cute", "tiny"])
    out = dict(
        line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines()
    )
    assert out["DRAFT_PATH"] == "''"
    assert out["MIN_RELEASE"] == "0"


# ---------------------------------------------------------------------------
# total_ram_gb() — the Linux branch
# ---------------------------------------------------------------------------

def test_total_ram_gb_parses_proc_meminfo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """With no usable sysctl (the Linux shape), MemTotal decides. kB in,
    GB out — 33_554_432 kB is exactly 32 GB."""
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       33554432 kB\nMemFree:         1000000 kB\n", encoding="utf-8"
    )
    monkeypatch.setattr(models, "MEMINFO", meminfo)
    monkeypatch.setattr(
        models.subprocess, "check_output",
        lambda *a, **k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "sysctl")),
    )
    assert models.total_ram_gb() == 32


def test_total_ram_gb_falls_back_to_16(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(models, "MEMINFO", tmp_path / "nope")
    monkeypatch.setattr(
        models.subprocess, "check_output",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no sysctl")),
    )
    assert models.total_ram_gb() == 16


def test_free_disk_gb_creates_the_weights_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    weights = tmp_path / "not-yet" / "weights"
    monkeypatch.setattr(models, "WEIGHTS_DIR", weights)
    assert models.free_disk_gb() > 0
    assert weights.is_dir()


# ---------------------------------------------------------------------------
# supervisor._launch — where the flags and the gate actually land
# ---------------------------------------------------------------------------

@pytest.fixture
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A LlamaSupervisor whose Popen is a recorder and whose HOME is
    tmp_path (the real ~/enough/.llama-server must not be touched).
    Returns (supervisor, argv_holder, set_model)."""
    from enough import supervisor as sup

    monkeypatch.setenv("HOME", str(tmp_path))
    argv: list[list[str]] = []

    class _FakeProc:
        pid = 4242

    monkeypatch.setattr(
        sup.subprocess, "Popen",
        lambda cmd, **kw: (argv.append(list(cmd)), _FakeProc())[1],
    )
    # The supervisor no longer reaches for `shutil.which` itself — it asks
    # models.find_llama_server(), which is the one place the
    # $ENOUGH_LLAMA_SERVER → ~/enough/bin → PATH order lives.
    monkeypatch.setattr(models, "find_llama_server", lambda: "/fake/bin/llama-server")

    def _set_model(**over):
        info = {
            "cute": "drafty", "label": "Draft-file MTP 27B",
            "filename": "drafty.gguf", "path": str(tmp_path / "drafty.gguf"),
            "installed": True,
            "spec_args": "--spec-type draft-mtp --spec-draft-n-max 3",
            "spec_min_release": 9200, "llama_cpp_min_release": 9200,
            "draft_filename": "mtp-drafty.gguf",
            "draft_path": str(tmp_path / "mtp-drafty.gguf"),
        }
        info.update(over)
        monkeypatch.setattr(models, "resolve", lambda cute=None: info)
        return info

    monkeypatch.setattr(models, "llama_release", lambda binary="llama-server": 9200)
    return sup.LlamaSupervisor(), argv, _set_model


def test_launch_passes_the_draft_file(launcher):
    supervisor, argv, set_model = launcher
    info = set_model()
    supervisor._launch("drafty", 32768)
    cmd = argv[0]
    assert "--spec-type" in cmd and "draft-mtp" in cmd
    i = cmd.index("--spec-draft-model")
    assert cmd[i + 1] == info["draft_path"]


def test_launch_without_the_draft_file_is_plain_not_an_error(launcher):
    supervisor, argv, set_model = launcher
    set_model(draft_path=None)
    supervisor._launch("drafty", 32768)      # must not raise
    cmd = argv[0]
    assert "--spec-draft-model" not in cmd
    assert "--spec-type" not in cmd
    assert "-m" in cmd                        # …but it did launch


def test_launch_refuses_a_too_old_llama_cpp(launcher, monkeypatch: pytest.MonkeyPatch):
    supervisor, argv, set_model = launcher
    set_model()
    monkeypatch.setattr(models, "llama_release", lambda binary="llama-server": 9100)
    with pytest.raises(RuntimeError, match=r"b9200 or newer"):
        supervisor._launch("drafty", 32768)
    assert argv == []                         # nothing was spawned


def test_launch_allows_ungated_models_on_an_old_build(launcher, monkeypatch: pytest.MonkeyPatch):
    supervisor, argv, set_model = launcher
    set_model(llama_cpp_min_release=0, spec_args="", draft_filename=None, draft_path=None)
    monkeypatch.setattr(models, "llama_release", lambda binary="llama-server": 9000)
    supervisor._launch("drafty", 32768)
    assert len(argv) == 1


# ---------------------------------------------------------------------------
# The shipped registry itself
# ---------------------------------------------------------------------------

def test_shipped_registry_has_the_seven_models():
    reg = models.load_registry()
    assert list(reg["models"]) == [
        "g40-04", "q35-09", "g40-12", "g40-26", "q36-27", "q38-04", "q38-16",
    ]
    assert "install_tiers" not in reg      # deleted in 0.1.7


@pytest.mark.parametrize("cute", ["q38-04", "q38-16"])
def test_shipped_qwen38_entries_declare_a_draft_file_and_a_hard_gate(cute: str):
    entry = models.load_registry()["models"][cute]
    assert entry["llama_cpp_min_release"] == 9200
    mtp = entry["mtp"]
    assert mtp["spec_type"] == "draft-mtp"
    assert mtp["draft_gguf_filename"].startswith("mtp-Qwen3.8-27B-")
    assert mtp["draft_gguf_url"].endswith(mtp["draft_gguf_filename"])
    assert mtp["draft_disk_gb_approx"] > 0


@pytest.mark.parametrize("cute", ["g40-04", "q35-09", "g40-12", "g40-26", "q36-27"])
def test_shipped_pre_existing_entries_stay_ungated(cute: str):
    """The hard gate is opt-in — adding it must not strand anyone whose
    llama.cpp already runs the models they have."""
    entry = models.load_registry()["models"][cute]
    assert not entry.get("llama_cpp_min_release")
    assert not (entry.get("mtp") or {}).get("draft_gguf_filename")


# ---------------------------------------------------------------------------
# Supervisor port derivation (Wave 4 blocker: port must follow llm_url)
# ---------------------------------------------------------------------------

def test_supervisor_port_follows_llm_url():
    from enough.supervisor import LlamaSupervisor

    assert LlamaSupervisor(llm_url="http://127.0.0.1:18081").port == 18081
    # No port in the URL → the historical default.
    assert LlamaSupervisor(llm_url="http://127.0.0.1").port == 8080
    assert LlamaSupervisor().port == 8080
    # An explicit override still wins.
    assert LlamaSupervisor(llm_url="http://127.0.0.1:18081", port=9999).port == 9999
