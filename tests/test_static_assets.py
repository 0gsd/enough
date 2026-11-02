"""The static mount revalidates (0.5.1).

`/static/*` answers with `Cache-Control: no-cache` and an ETag, so a browser
keeps the file but asks before reusing it (a 304 on loopback is free), and
the page's boot state carries the server's version, which `staticUrl()` in
index.html stamps onto icon and catalog URLs. Both because the 0.5.0
desktop app drew 0.4.4's icons: the snapshot had the new files, the server
sent them, and the webview never asked — an icon's path had not changed and
nothing said how long it was good for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import __version__, models, skeleton
from enough.server import create_app

ICON = "/static/icons/build/comp-pointer.svg"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c


def test_static_answers_no_cache_with_an_etag(client: TestClient) -> None:
    r = client.get(ICON)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers.get("etag")
    again = client.get(ICON, headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304
    # The stamp the page appends is a query string the mount ignores.
    assert client.get(ICON + "?v=" + __version__).content == r.content


def test_boot_state_carries_the_version(client: TestClient) -> None:
    html = client.get("/").text
    m = re.search(r"const BOOT_UI_STATE = (\{.*?\});\n", html)
    assert m, "the boot state is templated into index.html"
    assert json.loads(m.group(1))["version"] == __version__
    assert "staticUrl('/static/icons/build/'" in html


def test_the_page_loads_pele_not_mermaid() -> None:
    """The renderer swap (0.5.1): the page lazy-loads Pele's global build;
    Mermaid's bundle is gone from the tree and from the page."""
    static = Path(__file__).resolve().parents[1] / "enough" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    assert "staticUrl('/static/pele.global.js')" in html
    assert "mermaid.min.js" not in html
    assert (static / "pele.global.js").is_file()
    assert not (static / "mermaid.min.js").exists()
    head = (static / "pele.global.js").read_text(encoding="utf-8", errors="replace")[:120]
    assert "Pele 1.13.0" in head and "MIT License" in head
