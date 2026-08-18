"""The reader's throttled newer-snapshot check (docs/skills-round-plan.md §5).

Never touches download.kiwix.org: `newer_snapshot_available` is monkeypatched
in every test, and the two "must not go to the network" cases assert that by
counting calls. Scratch wikisink config via ENOUGH_WIKISINK_CONFIG.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough.server import create_app
from enough.wikisink import config as wconfig
from enough.wikisink import download as wdl

NEWER = {"flavor": "top1m_nopic", "date": "2026-08", "size_bytes": 17_000_000_000,
         "size_human": "15.8 GB", "filename": "wikipedia_en_top1m_nopic_2026-08.zim",
         "url": "https://download.kiwix.org/zim/wikipedia/x.zim"}


@pytest.fixture(autouse=True)
def _scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(tmp_path / "wikisink.json"))
    monkeypatch.setattr(wconfig, "CONFIG_PATH", tmp_path / "wikisink.json",
                        raising=False)
    yield


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []

    def fake(cfg=None, *, cached_only=False):
        calls.append({"cached_only": cached_only})
        return None if cached_only else dict(NEWER)

    monkeypatch.setattr(wdl, "newer_snapshot_available", fake)
    return calls


def _installed(monkeypatch: pytest.MonkeyPatch, yes: bool = True) -> None:
    monkeypatch.setattr(wconfig, "installed", lambda cfg=None: yes)


def test_no_archive_means_no_check(monkeypatch, spy):
    _installed(monkeypatch, False)
    out = wdl.newer_snapshot_throttled()
    assert out == {"newer": None, "checked_at": None, "checked": False}
    assert spy == []          # never even asked


def test_first_open_checks_and_stamps(monkeypatch, spy):
    _installed(monkeypatch)
    out = wdl.newer_snapshot_throttled()
    assert out["checked"] is True
    assert out["newer"]["date"] == "2026-08"
    assert spy == [{"cached_only": False}]
    stamped = wconfig.load_config()["listing_checked_at"]
    assert stamped and stamped == out["checked_at"]


def test_second_open_inside_the_window_stays_offline(monkeypatch, spy):
    _installed(monkeypatch)
    cfg = wconfig.load_config()
    cfg["listing_checked_at"] = (datetime.now(timezone.utc)
                                 - timedelta(hours=3)).isoformat()
    wconfig.save_config(cfg)
    out = wdl.newer_snapshot_throttled()
    assert out["checked"] is False
    assert spy == [{"cached_only": True}]   # cache only — no kiwix


def test_a_day_later_it_checks_again(monkeypatch, spy):
    _installed(monkeypatch)
    cfg = wconfig.load_config()
    cfg["listing_checked_at"] = (datetime.now(timezone.utc)
                                 - timedelta(hours=25)).isoformat()
    wconfig.save_config(cfg)
    out = wdl.newer_snapshot_throttled()
    assert out["checked"] is True
    assert spy == [{"cached_only": False}]


def test_a_failed_check_is_silent_and_still_stamps(monkeypatch):
    _installed(monkeypatch)

    def boom(cfg=None, *, cached_only=False):
        raise OSError("network is unreachable")

    monkeypatch.setattr(wdl, "newer_snapshot_available", boom)
    out = wdl.newer_snapshot_throttled()
    assert out["newer"] is None
    assert out["checked"] is True
    # Stamped anyway: an offline machine retries tomorrow, not every open.
    assert wconfig.load_config()["listing_checked_at"] == out["checked_at"]


def test_endpoint(tmp_path: Path, monkeypatch, spy):
    _installed(monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        js = c.get("/api/wiki/newer-snapshot").json()
        assert js["newer"]["size_human"] == "15.8 GB"
        assert js["checked"] is True
        # Second call inside the window doesn't re-fetch.
        js2 = c.get("/api/wiki/newer-snapshot").json()
        assert js2["checked"] is False
