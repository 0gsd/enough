"""i18n round: structural parity across the shipped UI languages (the
scripts/i18n_check.py assertions, run as a test so a release can't ship
drift), plus the server's two language behaviors — the ui_language
whitelist in /api/ui-config and the translated-manual fallback in
/api/help-center. The process doc is docs/I18N.md."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import server as server_mod
from enough.server import create_app

REPO = Path(__file__).resolve().parent.parent


def _check_module():
    spec = importlib.util.spec_from_file_location(
        "i18n_check", REPO / "scripts" / "i18n_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_translations_in_lockstep():
    """The whole contract in one assertion: en catalog == index.html
    usage, and every shipped language mirrors the English structure.
    When this fails, its output is the to-do list (see docs/I18N.md)."""
    problems = _check_module().check()
    assert problems == [], "\n".join(problems)


# ---------------------------------------------------------------------------
# server behaviors
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "_store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        yield c


def test_ui_language_roundtrip_and_whitelist(client: TestClient):
    # Fresh config: no language key means English.
    assert client.get("/api/ui-config").json().get("ui_language") in (None, "en")
    # A shipped language sticks.
    cfg = client.post("/api/ui-config", json={"ui_language": "fr"}).json()
    assert cfg["ui_language"] == "fr"
    # An unknown code is dropped, not stored.
    cfg = client.post("/api/ui-config", json={"ui_language": "tlh"}).json()
    assert cfg["ui_language"] == "fr"
    # And the theme merge doesn't eat it (top-level key survives current
    # rebuilds, like home_view et al).
    cfg = client.post("/api/ui-config", json={"theme": "pastel"}).json()
    assert cfg["ui_language"] == "fr"


def test_boot_state_carries_language(client: TestClient):
    client.post("/api/ui-config", json={"ui_language": "de"})
    html = client.get("/").text
    assert "/*UI_STATE_JSON*/null" not in html
    assert '"lang": "de"' in html or '"lang":"de"' in html


def test_help_center_language_fallback(client: TestClient, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch):
    # A pretend static dir with one translated manual. The endpoint reads
    # server_mod.STATIC_DIR at request time; the app's /static mount was
    # bound at create_app time and is irrelevant here.
    fake_static = tmp_path / "static"
    (fake_static / "i18n" / "fr").mkdir(parents=True)
    (fake_static / "i18n" / "fr" / "help-center.md").write_text(
        "# BONJOUR MANUEL\n", encoding="utf-8")
    monkeypatch.setattr(server_mod, "STATIC_DIR", fake_static)

    # Translated when present…
    assert "BONJOUR MANUEL" in client.get("/api/help-center?lang=fr").text
    # …English when the language ships no manual…
    assert "BONJOUR MANUEL" not in client.get("/api/help-center?lang=de").text
    # …English for anything not on the whitelist (also the path guard).
    evil = client.get("/api/help-center", params={"lang": "../../etc"})
    assert evil.status_code == 200
    assert "BONJOUR MANUEL" not in evil.text


def test_en_catalog_is_valid_json_when_present():
    cat = REPO / "enough" / "static" / "i18n" / "en" / "ui.json"
    if not cat.is_file():
        pytest.skip("en catalog not created yet (sweep pending)")
    data = json.loads(cat.read_text(encoding="utf-8"))
    assert isinstance(data.get("strings"), dict) and data["strings"]