"""The one list of `ENOUGH_*` seams (enough/seams.py) is whole, and both halves of the isolation rule read it.

Whole: every `ENOUGH_*` name a module under enough/ spells out is in the list, so a new environment variable cannot
arrive without its seam (or a line in `FLAGS_WITHOUT_SEAM` saying why it needs none); and every name in the list is
still read somewhere, by the app, the desktop shell or the shell scripts.

Both halves: `scripts/smoke_boot.py`'s `build_env()` points every seam into its scratch dir, and conftest's session
floor holds under a module-scoped fixture, which is made before the per-test seams are in place.
"""

from __future__ import annotations

import importlib.util
import os
import pwd
import re
from pathlib import Path

import pytest

from enough import seams

REPO = Path(__file__).resolve().parent.parent
NAME = re.compile(r"""["'](ENOUGH_[A-Z0-9_]+)["']""")


def _names_in(paths) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for p in paths:
        for name in NAME.findall(p.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(name, []).append(p.relative_to(REPO).as_posix())
    return found


def _app_sources():
    return [p for p in sorted((REPO / "enough").rglob("*.py")) if p != REPO / "enough" / "seams.py"]


def _shell_sources():
    yield from sorted((REPO / "desktop" / "src-tauri" / "src").glob("*.rs"))
    yield from sorted(REPO.glob("*.sh"))
    yield from sorted(REPO.glob("*.command"))
    yield from sorted((REPO / "shortcuts").glob("*.command"))


def test_every_variable_the_app_reads_is_in_the_one_list():
    found = _names_in(_app_sources())
    assert found, "the scan found no ENOUGH_* names under enough/ at all; the pattern is wrong"
    missing = {name: where for name, where in found.items() if name not in seams.every_name()}
    assert not missing, (
        f"read under enough/ but not in enough/seams.py: {missing}. A variable that names a path or a service gets a "
        f"seam (PATH_SEAMS or FIXED_SEAMS); one that changes behaviour goes in BEHAVIOUR_SEAMS; a plain flag goes in "
        f"FLAGS_WITHOUT_SEAM with the reason it needs none")


def test_every_name_in_the_list_is_still_read_somewhere():
    read = set(_names_in(_app_sources())) | set(_names_in(_shell_sources()))
    # The shell scripts read their variables bare ("$ENOUGH_REPO_URL", ${ENOUGH_VULKAN_ICD_DIRS:-…}).
    for p in _shell_sources():
        read |= set(re.findall(r"\b(ENOUGH_[A-Z0-9_]+)\b", p.read_text(encoding="utf-8", errors="replace")))
    stale = seams.every_name() - read
    assert not stale, f"in enough/seams.py but read nowhere: {sorted(stale)}"


def test_the_kinds_do_not_overlap():
    groups = [set(seams.PATH_SEAMS), set(seams.FIXED_SEAMS), set(seams.BEHAVIOUR_SEAMS), set(seams.FLAGS_WITHOUT_SEAM)]
    assert sum(len(g) for g in groups) == len(seams.every_name())


def test_scratch_env_points_every_seam_under_the_scratch_root(tmp_path: Path):
    base = {"PATH": "/usr/bin", "ENOUGH_DESKTOP_CODE": "/somewhere/real", "ENOUGH_CANON_ROOT": "/real/canon"}
    env = seams.scratch_env(tmp_path, base)
    assert env["PATH"] == "/usr/bin"
    for var in seams.PATH_SEAMS:
        assert Path(env[var]).is_relative_to(tmp_path), var
    for var, value in seams.FIXED_SEAMS.items():
        assert env[var] == value
    assert not set(seams.BEHAVIOUR_SEAMS) & set(env)
    registry = Path(env["ENOUGH_MODELS_REGISTRY"])
    assert registry.read_bytes() == (REPO / "defaults" / "models.json").read_bytes()


def _smoke_boot():
    spec = importlib.util.spec_from_file_location("smoke_boot_for_seams", REPO / "scripts" / "smoke_boot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_smoke_boot_reads_the_same_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for var in seams.BEHAVIOUR_SEAMS:
        monkeypatch.setenv(var, "/exported/by/the/developer")
    env = _smoke_boot().build_env(tmp_path)
    assert Path(env["HOME"]).is_relative_to(tmp_path)
    for var in seams.PATH_SEAMS:
        if var == "ENOUGH_DICT_SOURCE":
            # The boot builds FEED from the checkout's own source, on purpose, into the scratch dict root.
            assert env[var] == str(REPO / "reflib" / "dict")
        else:
            assert Path(env[var]).is_relative_to(tmp_path), var
    for var, value in seams.FIXED_SEAMS.items():
        assert env[var] == value, var
    # The boot's own choices, made after the clearing; every other behaviour seam is gone.
    chosen = {"ENOUGH_LLAMA_SERVER", "ENOUGH_DESKTOP", "ENOUGH_DESKTOP_TOKEN"}
    assert Path(env["ENOUGH_LLAMA_SERVER"]).is_relative_to(tmp_path)
    assert env["ENOUGH_DESKTOP"] == "1"
    assert not (set(seams.BEHAVIOUR_SEAMS) - chosen) & set(env)


# Another session-scoped fixture may move a seam on purpose, and the floor and the per-test seams then leave it alone
# (conftest's `_still_pristine`): tests/test_convert_docling.py pins ENOUGH_WEIGHTS_DIR at the real weights for the
# whole session, because the docling models are the one thing those tests cannot fabricate, and points
# ENOUGH_EXTRAS_STATE at its own scratch. So in a full run a seam holds either the floor's value or such a fixture's.
# What may never happen is a seam on the real ~/enough, except the weights, read only, by that one deliberate pin.
READ_REAL_ON_PURPOSE = {"ENOUGH_WEIGHTS_DIR"}


def _floor_or_moved_on_purpose(var: str, value: str | None, mine: Path) -> None:
    real_enough = Path(pwd.getpwuid(os.getuid()).pw_dir) / "enough"
    path = Path(value or "")
    if var in READ_REAL_ON_PURPOSE:
        return
    assert not path.is_relative_to(real_enough), var
    if not path.is_relative_to(mine):
        # moved by another session fixture: it must still be scratch, never anywhere under the real home
        assert not path.is_relative_to(Path(pwd.getpwuid(os.getuid()).pw_dir)) or "pytest-of-" in str(path), var


# ---------------------------------------------------------------------------
# The session floor, seen from a fixture wider than a test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def seen_by_a_module_fixture() -> dict[str, str | None]:
    return {var: os.environ.get(var) for var in ("HOME", *seams.PATH_SEAMS, *seams.FIXED_SEAMS,
                                                  *seams.BEHAVIOUR_SEAMS)}


def test_a_module_fixture_never_sees_the_real_home(seen_by_a_module_fixture, session_floor: Path):
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    seen = seen_by_a_module_fixture
    assert Path(seen["HOME"]) != real_home
    assert Path(seen["HOME"]).is_relative_to(session_floor)
    for var in seams.PATH_SEAMS:
        _floor_or_moved_on_purpose(var, seen[var], session_floor)
    for var, value in seams.FIXED_SEAMS.items():
        assert seen[var] == value
    for var in seams.BEHAVIOUR_SEAMS:
        assert seen[var] is None, var


def test_a_test_still_gets_its_own_seams_under_the_floor(tmp_path: Path, session_floor: Path):
    assert Path(os.environ["HOME"]).is_relative_to(tmp_path)
    for var in seams.PATH_SEAMS:
        _floor_or_moved_on_purpose(var, os.environ.get(var), tmp_path)
    from enough import broker
    assert broker.CONFIG_PATH.is_relative_to(tmp_path)
