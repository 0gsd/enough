"""`project_meta`'s composure block — the P4d launch setting.

A separate file from `test_project_meta.py` on purpose: the display-scale
half of `rness/project.json` is owned by another lane this round, and the
whole point of three separate writers is that they cannot clobber each
other. Those non-clobbering assertions live here, where they read as what
they are.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from enough import project_meta

REL = "rness/io/composure/board.comp"


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    p = tmp_path / "project"
    (p / "rness").mkdir(parents=True)
    return p


def raw(project: Path) -> dict:
    return json.loads((project / project_meta.META_REL).read_text(
        encoding="utf-8"))


# ---------------------------------------------------------------------------
# Defaults and reads
# ---------------------------------------------------------------------------

def test_a_project_with_no_metadata_reads_as_blank(project: Path):
    assert project_meta.load(project)["composure"] == {
        "launch": "blank", "path": "", "form": "", "last": ""}


def test_load_is_always_populated_even_from_corrupt_json(project: Path):
    (project / project_meta.META_REL).write_text("{not json", encoding="utf-8")
    assert project_meta.load(project)["composure"]["launch"] == "blank"


def test_unknown_keys_in_the_block_are_ignored_not_fatal(project: Path):
    (project / project_meta.META_REL).write_text(json.dumps({
        "composure": {"launch": "file", "path": REL, "from_the_future": 1}}),
        encoding="utf-8")
    loaded = project_meta.load(project)["composure"]
    assert loaded["launch"] == "file" and loaded["path"] == REL
    assert "from_the_future" not in loaded


# ---------------------------------------------------------------------------
# save_composure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", project_meta.COMPOSURE_LAUNCH_MODES)
def test_every_launch_mode_round_trips(project: Path, mode: str):
    saved = project_meta.save_composure(project, mode, REL, "scaffold")
    assert saved["composure"]["launch"] == mode
    assert project_meta.load(project)["composure"]["launch"] == mode


def test_an_unknown_launch_mode_resolves_to_blank(project: Path):
    """A project must always open; a garbage setting is not a crash."""
    for bad in ("sideways", "", None, 7, True):
        assert project_meta.save_composure(
            project, bad)["composure"]["launch"] == "blank"


def test_omitted_fields_keep_what_is_on_disk(project: Path):
    project_meta.save_composure(project, "file", REL, "scaffold")
    kept = project_meta.save_composure(project, "form")["composure"]
    assert kept["path"] == REL and kept["form"] == "scaffold"


def test_paths_are_validated_before_they_are_stored(project: Path):
    for bad in ("/etc/passwd.comp", "../../escape.comp", "notes/plan.md",
                "rness/../../x.comp", "", None, 42):
        stored = project_meta.save_composure(project, "file", bad)["composure"]
        assert stored["path"] == "", bad
    ok = project_meta.save_composure(project, "file",
                                     "a/b/c.comp")["composure"]
    assert ok["path"] == "a/b/c.comp"
    # Windows-style separators normalize rather than smuggling a traversal.
    assert project_meta.save_composure(
        project, "file", "a\\..\\..\\x.comp")["composure"]["path"] == ""


def test_form_names_are_slugs_never_paths(project: Path):
    for bad in ("../../etc", "Scaffold", "a/b", "-leading", "", None):
        assert project_meta.save_composure(
            project, "form", None, bad)["composure"]["form"] == "", bad
    assert project_meta.save_composure(
        project, "form", None, "my-board")["composure"]["form"] == "my-board"


def test_save_composure_never_writes_last(project: Path):
    """`last` is bookkeeping owned by `touch_composure`. Choosing "a
    specific composure" must not erase the trail "the last one used"
    needs."""
    project_meta.touch_composure(project, REL)
    other = "rness/io/composure/other.comp"
    saved = project_meta.save_composure(project, "file", other)["composure"]
    assert saved["last"] == REL and saved["path"] == other


# ---------------------------------------------------------------------------
# touch_composure
# ---------------------------------------------------------------------------

def test_touch_composure_stamps_last(project: Path):
    assert project_meta.touch_composure(project, REL)["composure"]["last"] == REL
    assert raw(project)["composure"]["last"] == REL


def test_touch_composure_is_a_no_op_when_nothing_changed(project: Path):
    """It runs on every canvas open; a project.json rewritten on every read
    would be noise in the user's version control."""
    project_meta.touch_composure(project, REL)
    before = (project / project_meta.META_REL).stat().st_mtime_ns
    project_meta.touch_composure(project, REL)
    assert (project / project_meta.META_REL).stat().st_mtime_ns == before


def test_touch_composure_ignores_junk(project: Path):
    project_meta.touch_composure(project, REL)
    for bad in ("", "notes/plan.md", "../escape.comp", "/abs.comp"):
        assert project_meta.touch_composure(
            project, bad)["composure"]["last"] == REL


def test_touch_composure_does_not_disturb_the_launch_choice(project: Path):
    project_meta.save_composure(project, "form", None, "cards")
    after = project_meta.touch_composure(project, REL)["composure"]
    assert after == {"launch": "form", "path": "", "form": "cards",
                     "last": REL}


# ---------------------------------------------------------------------------
# Three writers, three halves of one file
# ---------------------------------------------------------------------------

def test_the_three_writers_do_not_clobber_each_other(project: Path):
    project_meta.save(project, "My Book", "a memoir")
    project_meta.save_ui(project, 1.2, 0.9)
    project_meta.save_composure(project, "file", REL)
    project_meta.touch_composure(project, "rness/io/composure/x.comp")

    loaded = project_meta.load(project)
    assert loaded["name"] == "My Book" and loaded["description"] == "a memoir"
    assert loaded["ui"]["ui_scale"] == 1.2 and loaded["ui"]["text_scale"] == 0.9
    assert loaded["composure"]["launch"] == "file"
    assert loaded["composure"]["path"] == REL
    assert loaded["composure"]["last"] == "rness/io/composure/x.comp"

    # ...in either order.
    project_meta.save(project, "Renamed", "still here")
    assert project_meta.load(project)["composure"]["path"] == REL
    assert project_meta.load(project)["ui"]["ui_scale"] == 1.2


def test_keys_this_module_does_not_own_survive_a_write(project: Path):
    (project / project_meta.META_REL).write_text(
        json.dumps({"name": "X", "someone_elses_key": {"a": 1}}),
        encoding="utf-8")
    project_meta.save_composure(project, "last")
    assert raw(project)["someone_elses_key"] == {"a": 1}


def test_the_file_is_created_when_rness_does_not_exist_yet(tmp_path: Path):
    fresh = tmp_path / "brand-new"
    saved = project_meta.save_composure(fresh, "blank")
    assert (fresh / project_meta.META_REL).is_file()
    assert saved["composure"]["launch"] == "blank"
