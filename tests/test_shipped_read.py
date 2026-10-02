"""read_file and the skeleton's symlinks.

A shipped skill is a symlink out of the project, so plain containment used
to refuse its SKILL.md and `references/` — the very files the skills tell
the model to read. `read_file` now follows a path written under `rness/`
into the install's `defaults/` (or the user's readvisors dir), and nowhere
else. Writes never get the exception.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from enough import broker, skeleton
from enough import tools as T

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(skeleton.user_readvisors_root()).startswith(str(tmp_path))
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    assert (proj / "rness" / "skills" / "analyzer").is_symlink()
    return proj


def _call(name: str, path: str, content: str | None = None) -> T.ToolCall:
    return T.ToolCall(name=name, path=path, content=content, command=None,
                      url=None, extra={}, raw="", span=(0, 0))


def read(project: Path, path: str) -> T.ToolResult:
    return T.run_read_file(project, _call("read_file", path))


def write(project: Path, path: str, content: str) -> T.ToolResult:
    return T.run_write_file(project, _call("write_file", path, "overwritten" if content is None else content))


def test_shipped_skill_files_are_readable(project: Path):
    r = read(project, "rness/skills/analyzer/SKILL.md")
    assert r.ok, r.body
    assert "analyzer" in r.body
    ref = next((REPO / "defaults/skills/anything-finder/references").glob("*.md"))
    r = read(project, f"rness/skills/anything-finder/references/{ref.name}")
    assert r.ok, r.body


def test_a_disabled_skill_is_readable_too(project: Path):
    disabled = (project / "rness/skills/.disabled").read_text()
    assert "lexicographer" in disabled
    assert read(project, "rness/skills/lexicographer/SKILL.md").ok


def test_absolute_spelling_of_the_same_path(project: Path):
    r = read(project, str(project / "rness/skills/analyzer/SKILL.md"))
    assert r.ok, r.body


def test_shipped_paradigm_and_policy(project: Path):
    assert read(project, "rness/paradigms/text-planning.md").ok
    assert read(project, "rness/policies/allowlists.md").ok


def test_user_readvisor_through_its_symlink(project: Path):
    root = skeleton.user_readvisors_root()
    (root / "mine").mkdir(parents=True)
    (root / "mine" / "AGENT.md").write_text("# mine\n")
    (project / "rness/readvisors").mkdir(exist_ok=True)
    link = project / "rness/readvisors/mine"
    if not link.exists():
        link.symlink_to(root / "mine")
    assert read(project, "rness/readvisors/mine/AGENT.md").ok


def test_a_planted_symlink_elsewhere_is_still_refused(project: Path, tmp_path: Path):
    secret = tmp_path / "outside"
    secret.mkdir()
    (secret / "key.txt").write_text("hunter2")
    (project / "rness/skills/evil").symlink_to(secret)
    r = read(project, "rness/skills/evil/key.txt")
    assert not r.ok and "hunter2" not in r.body
    (project / "rness/hosts").symlink_to("/etc/hosts")
    assert not read(project, "rness/hosts").ok


def test_dotdot_out_of_a_shipped_dir_is_refused(project: Path):
    # defaults/../pyproject.toml is real, and outside the shipped root
    assert (REPO / "pyproject.toml").exists()
    for path in ("rness/skills/analyzer/../../../pyproject.toml",
                 "rness/skills/analyzer/../../../../pyproject.toml"):
        assert not read(project, path).ok, path


def test_the_exception_starts_only_under_rness(project: Path):
    (project / "side-door").symlink_to(REPO / "defaults" / "skills")
    assert not read(project, "side-door/analyzer/SKILL.md").ok
    # the install path itself, spelled directly, still needs the allowlist
    assert not read(project, str(REPO / "defaults/skills/analyzer/SKILL.md")).ok


def test_writes_through_the_symlink_are_refused(project: Path):
    shipped = REPO / "defaults/skills/analyzer/SKILL.md"
    before = shipped.read_bytes()
    for path in ("rness/skills/analyzer/SKILL.md",
                 str(project / "rness/skills/analyzer/SKILL.md"),
                 "rness/skills/analyzer/new-file.md"):
        r = write(project, path, "overwritten")
        assert not r.ok, path
    assert shipped.read_bytes() == before
    assert not (REPO / "defaults/skills/analyzer/new-file.md").exists()
