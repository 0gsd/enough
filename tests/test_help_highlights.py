"""Tests for the multipurpose ``rness/active-paradigm`` file and the
per-project help-bubble on/off toggle (item 5 of the mode-stack plan) —
including the legacy → on/off migration reads.

All UI-config and store state is routed through ENOUGH_* overrides so the real
~/enough install is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import prompt, skeleton
from enough.server import create_app


def _mk_paradigm(rness: Path, name: str = "default") -> None:
    (rness / "paradigms").mkdir(parents=True, exist_ok=True)
    (rness / "paradigms" / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: d\n---\nbody\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Pure helpers: parse / render / get / set
# --------------------------------------------------------------------------

def test_parse_render_roundtrip():
    # The paradigm value stays byte-compatible; the bubble section is on/off.
    text = prompt._render_multipurpose("text-planning", True)
    assert "# Active paradigm\ntext-planning\n" in text
    assert text.rstrip().endswith("# Help bubbles\non")
    name, enabled = prompt._parse_multipurpose(text)
    assert name == "text-planning" and enabled is True

    name2, enabled2 = prompt._parse_multipurpose(
        prompt._render_multipurpose("default", False))
    assert name2 == "default" and enabled2 is False

    # Legacy bare form: first line is the name, bubbles default on.
    assert prompt._parse_multipurpose("text-planning\n") == ("text-planning", True)


def test_legacy_values_read_as_on():
    # Every pre-0.1.7 value for the section reads as bubbles-on.
    def _parse(section_body: str) -> bool:
        text = (f"# {prompt._MP_PARADIGM_HEAD}\ndefault\n\n"
                f"# {prompt._MP_HIGHLIGHTS_HEAD}\n{section_body}\n")
        return prompt._parse_multipurpose(text)[1]

    assert _parse("all") is True                  # old first-launch sentinel
    assert _parse("- skills\n- roles") is True    # old pending id list
    assert _parse("") is True                     # empty section
    assert _parse("on") is True                   # new explicit on
    assert _parse("off") is False                 # new explicit off

    # A section under the OLD heading name is simply not found → default on.
    legacy = ("# Active paradigm\ndefault\n\n"
              "# Help bubble highlights\nall\n")
    assert prompt._parse_multipurpose(legacy)[1] is True


def test_get_active_paradigm_backcompat(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    _mk_paradigm(rness, "text-planning")
    f = rness / "active-paradigm"

    f.write_text("default\n", encoding="utf-8")                     # legacy bare
    assert prompt.get_active_paradigm(rness) == "default"

    f.write_text("text-planning\n", encoding="utf-8")               # bare, other name
    assert prompt.get_active_paradigm(rness) == "text-planning"

    f.write_text(prompt._render_multipurpose("text-planning", True),
                 encoding="utf-8")                                  # markdown form
    assert prompt.get_active_paradigm(rness) == "text-planning"

    f.write_text(prompt._render_multipurpose("nope", True), encoding="utf-8")
    assert prompt.get_active_paradigm(rness) == "default"           # unknown → fallback


def test_get_help_bubbles_missing_file_is_on(tmp_path: Path):
    rness = tmp_path / "rness"
    assert prompt.get_help_bubbles(rness) is True                   # no file → on


def test_set_active_paradigm_preserves_bubbles(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    _mk_paradigm(rness, "text-planning")
    prompt.seed_multipurpose_file(rness)
    assert prompt.get_help_bubbles(rness) is True

    prompt.set_help_bubbles(rness, False)
    prompt.set_active_paradigm(rness, "text-planning")
    assert prompt.get_active_paradigm(rness) == "text-planning"
    assert prompt.get_help_bubbles(rness) is False                 # preserved!


def test_get_set_help_bubbles_roundtrip(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    prompt.seed_multipurpose_file(rness)
    assert prompt.get_help_bubbles(rness) is True                  # seeded on

    prompt.set_help_bubbles(rness, False)
    assert prompt.get_help_bubbles(rness) is False
    assert prompt.get_active_paradigm(rness) == "default"          # paradigm preserved

    prompt.set_help_bubbles(rness, True)
    assert prompt.get_help_bubbles(rness) is True


def test_ensure_multipurpose_upgrades_legacy(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness, "text-planning")
    f = rness / "active-paradigm"
    f.write_text("text-planning\n", encoding="utf-8")              # legacy bare

    prompt.ensure_multipurpose_file(rness)
    assert "# Active paradigm" in f.read_text(encoding="utf-8")
    assert prompt.get_active_paradigm(rness) == "text-planning"
    assert prompt.get_help_bubbles(rness) is True                  # default on

    before = f.read_text(encoding="utf-8")                         # idempotent
    prompt.ensure_multipurpose_file(rness)
    assert f.read_text(encoding="utf-8") == before


def test_ensure_multipurpose_leaves_off_state_untouched(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    prompt.seed_multipurpose_file(rness)
    prompt.set_help_bubbles(rness, False)                          # already markdown, off
    prompt.ensure_multipurpose_file(rness)                         # must not re-enable
    assert prompt.get_help_bubbles(rness) is False


# --------------------------------------------------------------------------
# Skeleton seeding — new projects seed bubbles ON, established ones aren't
# reseeded (but do get the markdown upgrade).
# --------------------------------------------------------------------------

@pytest.fixture
def scratch_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    return tmp_path


def test_skeleton_seeds_bubbles_on(scratch_env: Path):
    proj = scratch_env / "projNEW"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    assert prompt.get_help_bubbles(proj / "rness") is True
    text = (proj / "rness" / "active-paradigm").read_text(encoding="utf-8")
    assert text.rstrip().endswith("# Help bubbles\non")


def test_skeleton_existing_project_upgraded_not_reseeded(scratch_env: Path):
    proj = scratch_env / "projEXIST"
    (proj / "rness").mkdir(parents=True)
    # A pre-0.1.7 file with the OFF state must survive the launch upgrade...
    (proj / "rness" / "active-paradigm").write_text(
        prompt._render_multipurpose("default", False), encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    text = (proj / "rness" / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm" in text
    assert prompt.get_help_bubbles(proj / "rness") is False        # not reseeded to on


def test_skeleton_legacy_bare_existing_upgraded_to_on(scratch_env: Path):
    proj = scratch_env / "projBARE"
    (proj / "rness").mkdir(parents=True)
    (proj / "rness" / "active-paradigm").write_text("default\n", encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    text = (proj / "rness" / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm" in text                            # upgraded to markdown
    assert prompt.get_help_bubbles(proj / "rness") is True        # legacy → on


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "_store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    skeleton.ensure_skeleton(project)   # the real launcher does this before create_app
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        yield c


def test_bubbles_endpoints(client: TestClient):
    body = client.get("/api/help/bubbles").json()
    assert body == {"enabled": True}                   # seeded on for a new project

    r = client.post("/api/help/bubbles", json={"enabled": False})
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False}
    assert client.get("/api/help/bubbles").json() == {"enabled": False}

    r = client.post("/api/help/bubbles", json={"enabled": True})
    assert r.status_code == 200
    assert client.get("/api/help/bubbles").json() == {"enabled": True}


def test_bubbles_endpoint_rejects_non_bool(client: TestClient):
    assert client.post("/api/help/bubbles", json={"enabled": "yes"}).status_code == 400
    assert client.post("/api/help/bubbles", json={"enabled": 1}).status_code == 400
    assert client.post("/api/help/bubbles", json={}).status_code == 400


def test_old_highlights_endpoints_gone(client: TestClient):
    assert client.get("/api/help/highlights").status_code == 404
    # /api/help/defaults is untouched.
    assert client.get("/api/help/defaults").status_code == 200
