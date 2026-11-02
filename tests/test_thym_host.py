"""enough's side of Thym that wave 2 shares: the programs a run may pick (`thym_host.list_programs`,
`find_program`) and the three shipped programs, byte for byte the conformance suite's."""
from __future__ import annotations

from pathlib import Path

import pytest

from enough import thym_host as H

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "thym" / "programs"
NAMES = ("open-house", "publish-story", "read-my-way")


@pytest.mark.parametrize("name", NAMES)
def test_shipped_programs_are_the_suites(name: str) -> None:
    shipped = H.SHIPPED_PROGRAMS / f"{name}.thym"
    assert shipped.is_file(), f"defaults/thym/{name}.thym ships"
    assert shipped.read_bytes() == (FIXTURES / f"{name}.thym").read_bytes(), (
        f"defaults/thym/{name}.thym must stay byte for byte tests/fixtures/thym/programs/{name}.thym "
        "(the conformance suite's); change both, or neither")


def test_program_name_reads_the_declared_name(tmp_path: Path) -> None:
    assert H.program_name(FIXTURES / "publish-story.thym") == ("publish-story", None)
    bad = tmp_path / "bad.thym"
    bad.write_text("thym 0\n\nprogram oops\n  takes t: text\n", encoding="utf-8")
    name, problem = H.program_name(bad)
    assert name is None and problem
    assert H.program_name(tmp_path / "missing.thym")[1].startswith("cannot be read")


def test_list_programs_orders_project_canon_shipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    (project / "notes").mkdir(parents=True)
    (project / "rness").mkdir()
    (project / "notes" / "mine.thym").write_bytes((FIXTURES / "read-my-way.thym").read_bytes())
    (project / "rness" / "hidden.thym").write_bytes((FIXTURES / "read-my-way.thym").read_bytes())
    (project / "broken.thym").write_text("thym 0\n\nprogram oops\n", encoding="utf-8")
    store = tmp_path / "canon"
    (store / "field-notes").mkdir(parents=True)
    (store / "field-notes" / "open-house.thym").write_bytes((FIXTURES / "open-house.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(store))
    rows = H.list_programs(project)
    wheres = [r["where"] for r in rows]
    assert wheres == ["project", "project", "canon", "shipped", "shipped", "shipped"], rows
    assert rows[0]["rel"] == "broken.thym" and rows[0]["name"] is None and rows[0]["problem"]
    assert rows[1] == {"name": "read-my-way", "where": "project", "path": str(project / "notes" / "mine.thym"),
                       "rel": "notes/mine.thym", "problem": None}
    assert rows[2]["rel"] == "canon:field-notes/open-house.thym" and rows[2]["name"] == "open-house"
    assert [r["rel"] for r in rows[3:]] == ["open-house.thym", "publish-story.thym", "read-my-way.thym"]
    assert "rness/hidden.thym" not in [r["rel"] for r in rows], "rness/ is the harness's, never a program's"


def test_find_program_by_name_prefers_the_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    mine = project / "publish-story.thym"
    mine.write_bytes((FIXTURES / "publish-story.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "canon"))
    assert H.find_program("publish-story", project) == mine
    assert H.find_program("open-house", project) == H.SHIPPED_PROGRAMS / "open-house.thym"
    assert H.find_program("nothing-of-the-kind", project) is None
    assert H.find_program("", project) is None


def test_find_program_by_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    (project / "a").mkdir(parents=True)
    mine = project / "a" / "p.thym"
    mine.write_bytes((FIXTURES / "publish-story.thym").read_bytes())
    store = tmp_path / "canon"
    (store / "vol").mkdir(parents=True)
    theirs = store / "vol" / "q.thym"
    theirs.write_bytes((FIXTURES / "open-house.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(store))
    assert H.find_program("a/p.thym", project) == mine
    assert H.find_program("canon:vol/q.thym", project) == theirs
    assert H.find_program("canon:../../a/p.thym", project) is None, "a store path never leaves the store"
    assert H.find_program("a/none.thym", project) is None
    assert H.find_program("read-my-way.thym") == H.SHIPPED_PROGRAMS / "read-my-way.thym", "a bare file name of a shipped program"
