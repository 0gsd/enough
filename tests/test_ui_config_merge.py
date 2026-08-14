"""Merge-on-read backfill of the new 0.1.6 theme keys (`icons` +
`btn-bg`) into the four SHIPPED themes for pre-0.1.6 ui.json files.

Isolates config via ENOUGH_UI_CONFIG (added alongside ENOUGH_WIKISINK_CONFIG
/ ENOUGH_CACHEAWL_ROOT) so the real ~/enough/config/ui.json is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough.server import create_app


def _stale_ui_config() -> dict:
    """A ui.json as an existing (pre-0.1.6) user would have it: shipped
    themes missing `icons` and `btn-bg`, one user color customized, and a
    fully custom theme the merge must NOT touch."""
    return {
        "current": {"theme": "enough-default", "font": "mono"},
        "fonts": {"mono": {"label": "Monospace", "stack": "ui-monospace, monospace"}},
        "themes": {
            "enough-default": {
                "label": "Enough Default",
                # no "icons" key; colors lack btn-bg; --bg customized
                "colors": {"bg": "#111111"},
            },
            "pastel": {"label": "Pastel", "colors": {"bg": "#fafafa"}},
            "wireframe": {"label": "Wireframe", "colors": {}},
            "darknest": {"label": "Darknest", "colors": {}},
            "my-custom": {"label": "Mine", "colors": {"bg": "#abcabc"}},
        },
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "project"
    project.mkdir()
    ui_path = tmp_path / "ui.json"
    ui_path.write_text(json.dumps(_stale_ui_config()), encoding="utf-8")
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(ui_path))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "_store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        yield c


def test_shipped_themes_get_backfilled_keys(client: TestClient):
    cfg = client.get("/api/ui-config").json()
    themes = cfg["themes"]
    # Template defines `icons` and `btn-bg` for every shipped theme; the
    # merged view must expose them even though the stale file lacked them.
    for name in ("enough-default", "pastel", "wireframe", "darknest"):
        assert "icons" in themes[name], f"{name} missing icons after merge"
        assert "btn-bg" in themes[name]["colors"], f"{name} missing btn-bg"


def test_merge_never_overwrites_user_values(client: TestClient):
    cfg = client.get("/api/ui-config").json()
    # The user's customized --bg on enough-default must survive.
    assert cfg["themes"]["enough-default"]["colors"]["bg"] == "#111111"
    assert cfg["themes"]["pastel"]["colors"]["bg"] == "#fafafa"


def test_custom_theme_untouched(client: TestClient):
    cfg = client.get("/api/ui-config").json()
    custom = cfg["themes"]["my-custom"]
    assert "icons" not in custom
    assert "btn-bg" not in custom["colors"]
    assert custom["colors"] == {"bg": "#abcabc"}


def test_merge_is_read_only_no_rewrite(client: TestClient, tmp_path: Path):
    # GET does not rewrite the on-disk file (merge is a read-time view).
    client.get("/api/ui-config")
    on_disk = json.loads((tmp_path / "ui.json").read_text(encoding="utf-8"))
    assert "icons" not in on_disk["themes"]["enough-default"]
    assert "btn-bg" not in on_disk["themes"]["enough-default"]["colors"]
