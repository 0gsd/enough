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


def _mk_paradigm(rness: Path, name: str = "text-planning") -> None:
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
        prompt._render_multipurpose("poetry", False))
    assert name2 == "poetry" and enabled2 is False

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
    _mk_paradigm(rness, "poetry")
    _mk_paradigm(rness, "text-planning")
    f = rness / "active-paradigm"

    f.write_text("poetry\n", encoding="utf-8")                      # legacy bare
    assert prompt.get_active_paradigm(rness) == "poetry"

    f.write_text("text-planning\n", encoding="utf-8")               # bare, other name
    assert prompt.get_active_paradigm(rness) == "text-planning"

    f.write_text(prompt._render_multipurpose("text-planning", True),
                 encoding="utf-8")                                  # markdown form
    assert prompt.get_active_paradigm(rness) == "text-planning"

    f.write_text(prompt._render_multipurpose("nope", True), encoding="utf-8")
    assert prompt.get_active_paradigm(rness) == "text-planning"     # unknown → home


def test_get_help_bubbles_missing_file_is_on(tmp_path: Path):
    rness = tmp_path / "rness"
    assert prompt.get_help_bubbles(rness) is True                   # no file → on


def test_set_active_paradigm_preserves_bubbles(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness, "poetry")
    _mk_paradigm(rness, "text-planning")
    prompt.seed_multipurpose_file(rness)
    assert prompt.get_help_bubbles(rness) is True

    prompt.set_help_bubbles(rness, False)
    prompt.set_active_paradigm(rness, "poetry")
    assert prompt.get_active_paradigm(rness) == "poetry"
    assert prompt.get_help_bubbles(rness) is False                 # preserved!


def test_get_set_help_bubbles_roundtrip(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    prompt.seed_multipurpose_file(rness)
    assert prompt.get_help_bubbles(rness) is True                  # seeded on

    prompt.set_help_bubbles(rness, False)
    assert prompt.get_help_bubbles(rness) is False
    assert prompt.get_active_paradigm(rness) == "text-planning"    # paradigm preserved

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
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "cacheawl"))
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
    assert prompt.get_active_paradigm(proj / "rness") == "text-planning"  # retired name migrated


def test_skeleton_legacy_bare_existing_upgraded_to_on(scratch_env: Path):
    proj = scratch_env / "projBARE"
    (proj / "rness").mkdir(parents=True)
    (proj / "rness" / "active-paradigm").write_text("default\n", encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    text = (proj / "rness" / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm" in text                            # upgraded to markdown
    assert prompt.get_help_bubbles(proj / "rness") is True        # legacy → on
    assert "\ntext-planning\n" in text                            # retired name migrated


# --------------------------------------------------------------------------
# 0.4.1: `default` folded into `text-planning`
# --------------------------------------------------------------------------

def test_new_project_starts_in_text_planning(scratch_env: Path):
    proj = scratch_env / "projHOME"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    rness = proj / "rness"
    assert not (rness / "paradigms" / "default.md").exists()
    assert prompt.get_active_paradigm(rness) == "text-planning"
    assert "# Paradigm: text-planning" in prompt.assemble_system_prompt(proj)


def test_migration_after_the_default_symlink_is_pruned(scratch_env: Path):
    """The ordinary existing project: `default.md` was a symlink into the
    install, the install no longer ships it, launch prunes the dangling link
    and the stored `default` becomes the home paradigm, bubble state kept."""
    proj = scratch_env / "projPRUNED"
    rness = proj / "rness"
    (rness / "paradigms").mkdir(parents=True)
    gone = scratch_env / "old-install" / "default.md"   # never created: dangling
    (rness / "paradigms" / "default.md").symlink_to(gone)
    (rness / "active-paradigm").write_text(
        prompt._render_multipurpose("default", False), encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    assert not (rness / "paradigms" / "default.md").is_symlink()   # pruned
    text = (rness / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm\ntext-planning\n" in text
    assert prompt.get_help_bubbles(rness) is False
    assert "# Paradigm: text-planning" in prompt.assemble_system_prompt(proj)


def test_migration_still_applies_to_a_live_default_symlink(tmp_path: Path):
    """A link that still resolves (an older sibling install) is not the
    user's own copy: migrate."""
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    elsewhere = tmp_path / "sibling" / "default.md"
    elsewhere.parent.mkdir()
    elsewhere.write_text("---\nname: default\ndescription: d\n---\nold\n", encoding="utf-8")
    (rness / "paradigms" / "default.md").symlink_to(elsewhere)
    (rness / "active-paradigm").write_text("default\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert prompt.get_active_paradigm(rness) == "text-planning"


def test_a_customised_default_is_kept(scratch_env: Path):
    """A real `rness/paradigms/default.md` is the user's: `default` stays
    active and its body still reaches the system prompt."""
    proj = scratch_env / "projCUSTOM"
    rness = proj / "rness"
    (rness / "paradigms").mkdir(parents=True)
    (rness / "paradigms" / "default.md").write_text(
        "---\nname: default\ndescription: mine\n---\nMY-OWN-DEFAULT-RULES\n",
        encoding="utf-8")
    (rness / "active-paradigm").write_text(
        prompt._render_multipurpose("default", True), encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    assert (rness / "paradigms" / "default.md").is_file()
    assert prompt.get_active_paradigm(rness) == "default"
    system = prompt.assemble_system_prompt(proj)
    assert "# Paradigm: default" in system and "MY-OWN-DEFAULT-RULES" in system
    # ...and the bare legacy form is kept just the same.
    (rness / "active-paradigm").write_text("default\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert "# Active paradigm\ndefault\n" in (rness / "active-paradigm").read_text(encoding="utf-8")


def test_legacy_one_line_default_migrates(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    f = rness / "active-paradigm"
    f.write_text("default\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert f.read_text(encoding="utf-8") == prompt._render_multipurpose("text-planning", True)
    before = f.read_text(encoding="utf-8")                         # idempotent
    prompt.ensure_multipurpose_file(rness)
    assert f.read_text(encoding="utf-8") == before


def test_a_missing_paradigm_falls_back_rather_than_vanishing(tmp_path: Path):
    """Whatever the file names, the prompt gets a Paradigm section: the home
    paradigm when the named one is gone, and any present one when even the
    home paradigm is."""
    rness = tmp_path / "rness"
    _mk_paradigm(rness)
    _mk_paradigm(rness, "workflow-design")
    f = rness / "active-paradigm"
    f.write_text(prompt._render_multipurpose("poetry", True), encoding="utf-8")
    assert prompt.get_active_paradigm(rness) == "text-planning"
    (rness / "paradigms" / "text-planning.md").unlink()
    assert prompt.get_active_paradigm(rness) == "workflow-design"
    assert prompt._load_active_paradigm_body(rness, prompt.get_active_paradigm(rness))


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "_store"))
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


# --------------------------------------------------------------------------
# 0.8: `translation` renamed `transcognition` (the migration keys on the
# stored name, as `default`'s does)
# --------------------------------------------------------------------------

def test_a_project_on_translation_opens_on_transcognition(scratch_env: Path):
    """The ordinary existing project: `translation.md` was a link into the
    install, the install now ships `transcognition.md`, launch prunes the
    dangling link before the migration runs, and the stored name moves."""
    proj = scratch_env / "projTRANS"
    rness = proj / "rness"
    (rness / "paradigms").mkdir(parents=True)
    (rness / "paradigms" / "translation.md").symlink_to(scratch_env / "old" / "translation.md")
    (rness / "active-paradigm").write_text(
        prompt._render_multipurpose("translation", False), encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    assert not (rness / "paradigms" / "translation.md").is_symlink()   # pruned
    assert (rness / "paradigms" / "transcognition.md").is_symlink()    # linked
    text = (rness / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm\ntranscognition\n" in text
    assert prompt.get_help_bubbles(rness) is False                      # kept
    assert prompt.get_active_paradigm(rness) == "transcognition"
    assert "# Paradigm: transcognition" in prompt.assemble_system_prompt(proj)


def test_legacy_one_line_translation_migrates(tmp_path: Path):
    rness = tmp_path / "rness"
    _mk_paradigm(rness, "transcognition")
    f = rness / "active-paradigm"
    f.write_text("translation\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert f.read_text(encoding="utf-8") == prompt._render_multipurpose("transcognition", True)
    before = f.read_text(encoding="utf-8")                         # idempotent
    prompt.ensure_multipurpose_file(rness)
    assert f.read_text(encoding="utf-8") == before


def test_a_customised_translation_is_kept_and_stays_active(scratch_env: Path):
    proj = scratch_env / "projMYTRANS"
    rness = proj / "rness"
    (rness / "paradigms").mkdir(parents=True)
    (rness / "paradigms" / "translation.md").write_text(
        "---\nname: translation\ndescription: mine\n---\nMY-OWN-TRANSLATION\n"
        "nllb_optin: true\n", encoding="utf-8")
    (rness / "active-paradigm").write_text(
        prompt._render_multipurpose("translation", True), encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    assert (rness / "paradigms" / "translation.md").is_file()
    assert prompt.get_active_paradigm(rness) == "translation"
    system = prompt.assemble_system_prompt(proj)
    assert "# Paradigm: translation" in system and "MY-OWN-TRANSLATION" in system
    # nothing is converted silently: transcognition stays the install's link,
    # and the catalog says, once, that the name moved
    assert (rness / "paradigms" / "transcognition.md").is_symlink()
    assert "since renamed **transcognition**" in system


# --------------------------------------------------------------------------
# 0.8: up to three paradigms on at once
# --------------------------------------------------------------------------

def _three(rness: Path) -> None:
    for n in ("text-planning", "transcognition", "workflow-design", "poetry"):
        _mk_paradigm(rness, n)


def test_one_name_reads_and_renders_as_before(tmp_path: Path):
    assert prompt._render_multipurpose(["text-planning"], True) == \
        prompt._render_multipurpose("text-planning", True) == \
        "# Active paradigm\ntext-planning\n\n# Help bubbles\non\n"
    rness = tmp_path / "rness"
    _three(rness)
    prompt.seed_multipurpose_file(rness)
    assert prompt.get_active_paradigms(rness) == ["text-planning"]


def test_a_set_round_trips(tmp_path: Path):
    rness = tmp_path / "rness"
    _three(rness)
    prompt.seed_multipurpose_file(rness)
    written = prompt.set_active_paradigms(rness, ["workflow-design", "text-planning"])
    assert written == ["text-planning", "workflow-design"]
    text = (rness / "active-paradigm").read_text(encoding="utf-8")
    assert "# Active paradigm\ntext-planning\nworkflow-design\n" in text
    assert prompt.get_active_paradigms(rness) == ["text-planning", "workflow-design"]
    assert prompt.get_active_paradigm(rness) == "text-planning"   # the sorted first
    assert prompt._parse_multipurpose_set(text) == (["text-planning", "workflow-design"], True)
    # a name gone from disk drops out of the set; the rest stays
    (rness / "paradigms" / "workflow-design.md").unlink()
    assert prompt.get_active_paradigms(rness) == ["text-planning"]


def test_a_fourth_is_refused_with_a_sentence(tmp_path: Path):
    rness = tmp_path / "rness"
    _three(rness)
    prompt.set_active_paradigms(rness, ["text-planning", "transcognition", "workflow-design"])
    before = (rness / "active-paradigm").read_text(encoding="utf-8")
    with pytest.raises(prompt.ParadigmSetRefused) as e:
        prompt.toggle_paradigm(rness, "poetry", True)
    assert e.value.reason == "cap" and "3 paradigms" in str(e.value)
    assert (rness / "active-paradigm").read_text(encoding="utf-8") == before
    with pytest.raises(prompt.ParadigmSetRefused) as e:
        prompt.set_active_paradigms(rness, [])
    assert e.value.reason == "empty"
    prompt.set_active_paradigm(rness, "poetry")                   # this one alone
    with pytest.raises(prompt.ParadigmSetRefused):
        prompt.toggle_paradigm(rness, "poetry", False)            # the last stays on
    assert prompt.toggle_paradigm(rness, "text-planning", True) == ["poetry", "text-planning"]
    assert prompt.toggle_paradigm(rness, "poetry", False) == ["text-planning"]


def test_a_bare_file_s_lines_read_as_a_set(tmp_path: Path):
    rness = tmp_path / "rness"
    _three(rness)
    f = rness / "active-paradigm"
    f.write_text("transcognition\ntext-planning\n", encoding="utf-8")   # a readvisor's write
    assert prompt.get_active_paradigms(rness) == ["text-planning", "transcognition"]
    f.write_text("transcognition\n", encoding="utf-8")                  # one line: that alone
    assert prompt.get_active_paradigms(rness) == ["transcognition"]
    f.write_text("a\nb\nc\nd\n", encoding="utf-8")                       # never more than three
    assert prompt._parse_multipurpose_set(f.read_text(encoding="utf-8"))[0] == ["a", "b", "c"]
    f.write_text("workflow-design\ntext-planning\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)                               # upgraded, set kept
    assert prompt.get_active_paradigms(rness) == ["text-planning", "workflow-design"]
    assert prompt.get_help_bubbles(rness) is True


def test_help_bubbles_keep_every_name(tmp_path: Path):
    rness = tmp_path / "rness"
    _three(rness)
    prompt.set_active_paradigms(rness, ["text-planning", "transcognition", "workflow-design"])
    prompt.set_help_bubbles(rness, False)
    assert prompt.get_active_paradigms(rness) == ["text-planning", "transcognition", "workflow-design"]
    assert prompt.get_help_bubbles(rness) is False
    prompt.set_active_paradigms(rness, ["text-planning", "poetry"])
    assert prompt.get_help_bubbles(rness) is False                     # preserved
    prompt.ensure_multipurpose_file(rness)                              # not collapsed
    assert prompt.get_active_paradigms(rness) == ["poetry", "text-planning"]


def test_retired_names_migrate_inside_a_set(tmp_path: Path):
    rness = tmp_path / "rness"
    _three(rness)
    f = rness / "active-paradigm"
    f.write_text(prompt._render_multipurpose(["default", "translation", "workflow-design"], False),
                 encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert prompt._parse_multipurpose_set(f.read_text(encoding="utf-8")) == \
        (["text-planning", "transcognition", "workflow-design"], False)
    # `default` and `text-planning` together become one name, not two
    f.write_text("default\ntext-planning\n", encoding="utf-8")
    prompt.ensure_multipurpose_file(rness)
    assert prompt._parse_multipurpose_set(f.read_text(encoding="utf-8"))[0] == ["text-planning"]


def test_a_set_has_one_heading_and_the_catalog_says_how_to_toggle(tmp_path: Path):
    proj = tmp_path / "p"
    rness = proj / "rness"
    _three(rness)
    prompt.set_active_paradigms(rness, ["transcognition", "text-planning"])
    system = prompt.assemble_system_prompt(proj)
    assert "# Paradigms: text-planning + transcognition" in system
    assert "# Paradigm: " not in system
    assert "Currently active: **text-planning**, **transcognition**" in system
    assert "under `# Active paradigm`" in system and "Up to three" in system


# --------------------------------------------------------------------------
# The route: toggles, a refused fourth, the composed note
# --------------------------------------------------------------------------

def test_paradigm_rows_are_toggles(client: TestClient, tmp_path: Path):
    html = client.get("/api/paradigm").text
    assert 'hx-post="/api/paradigm/toggle"' in html
    assert 'data-active-count="1"' in html and 'data-paradigm-text="paradigm"' in html
    r = client.post("/api/paradigm/toggle", data={"name": "transcognition", "on": "1"})
    assert r.status_code == 200
    assert 'data-active-count="2"' in r.text
    assert 'data-paradigm-text="metaparadigm"' in r.text        # the shipped pair's own text
    assert 'data-paradigm-note="composed"' not in r.text
    r = client.post("/api/paradigm/toggle", data={"name": "workflow-design", "on": "1"})
    assert 'data-active-count="3"' in r.text
    # a paradigm of the project's own has no combination written: composed
    rness = tmp_path / "project" / "rness"
    (rness / "paradigms" / "extra.md").write_text("---\nname: extra\n---\nx\n", encoding="utf-8")
    client.post("/api/paradigm/set", data={"name": "text-planning"})
    r = client.post("/api/paradigm/toggle", data={"name": "extra", "on": "1"})
    assert 'data-paradigm-note="composed"' in r.text           # no text written for the pair
    assert 'data-paradigms="extra text-planning"' in r.text


def test_paradigm_toggle_refuses_a_fourth_and_the_last(client: TestClient, tmp_path: Path):
    rness = tmp_path / "project" / "rness"
    (rness / "paradigms" / "extra.md").write_text("---\nname: extra\n---\nx\n", encoding="utf-8")
    for n in ("transcognition", "workflow-design"):
        client.post("/api/paradigm/toggle", data={"name": n, "on": "1"})
    r = client.post("/api/paradigm/toggle", data={"name": "extra", "on": "1"})
    assert r.status_code == 200
    assert 'data-paradigm-note="cap"' in r.text and 'data-limit="3"' in r.text
    assert prompt.get_active_paradigms(rness) == ["text-planning", "transcognition", "workflow-design"]
    client.post("/api/paradigm/set", data={"name": "extra"})       # this one alone
    assert prompt.get_active_paradigms(rness) == ["extra"]
    r = client.post("/api/paradigm/toggle", data={"name": "extra", "on": "0"})
    assert 'data-paradigm-note="empty"' in r.text
    assert client.post("/api/paradigm/toggle", data={"name": "nope", "on": "1"}).status_code == 400
