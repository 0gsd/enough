"""The Canon HTTP surface (0.4.3): `/api/canon/*` with its `/api/cacheawl/*`
aliases answering identically, the new catalog routes, the `canon:` and
`cacheawl:` path prefixes, the write-guards on `POST /api/file`, the listing
flags in the sidebar tree, and the project catalog's triggers (written at
open, never by `/api/files`).

TestClient over `create_app(..., supervise=False)`; the store and every
other seam point inside tmp_path (conftest), and `ensure_skeleton` runs
before `create_app`, as in a real launch.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import canon, skeleton
from enough.server import create_app

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"
LEAD = "this catalog is kept by enough; change the files it lists instead"


def _wait_for(path: Path, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.02)
    return path.is_file()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "store"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "hello.md").write_text("hi from the project", encoding="utf-8")
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", proj / "notes.md.cosm")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", proj / "rain.cosm")
    shutil.copytree(FIX / "holotypes" / "meadow", proj / "meadow")
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(canon.root()).startswith(str(tmp_path))
    return proj


@pytest.fixture
def client(project: Path):
    app = create_app(project, "http://localhost:9", supervise=False)
    with TestClient(app) as c:
        # The startup catalog runs in a worker thread; let it land so no
        # test races it.
        assert _wait_for(project / canon.PROJECT_CATALOG)
        yield c


def _store_volume(client: TestClient, name: str) -> Path:
    r = client.post("/api/canon/create", json={"name": name})
    assert r.status_code == 200, r.text
    return canon.volume_dir(name)


# --------------------------------------------------------------------------
# Aliases
# --------------------------------------------------------------------------

def test_every_old_route_answers_under_both_prefixes(client: TestClient):
    box = _store_volume(client, "docs")
    (box / "a.md").write_text("a", encoding="utf-8")
    for sub, params in (("tree", {}), ("mirror", {"box": "docs"}),
                        ("ingest-status", {"box": "docs"})):
        new = client.get(f"/api/canon/{sub}", params=params)
        old = client.get(f"/api/cacheawl/{sub}", params=params)
        assert new.status_code == old.status_code == 200, (sub, new.text)
        a, b = new.json(), old.json()
        if sub == "mirror":            # the frontmatter carries a generated: stamp
            a["text"], b["text"] = (t.split("generated:", 1)[0] for t in (a["text"], b["text"]))
        assert a == b, sub
    for sub in ("create", "rename", "delete", "transfer", "ingest"):
        assert client.post(f"/api/cacheawl/{sub}", json={}).status_code == 400, sub
        assert client.post(f"/api/canon/{sub}", json={}).status_code == 400, sub


def test_tree_payload_keeps_its_wire_keys_and_flags(client: TestClient, project: Path):
    box = _store_volume(client, "v")
    shutil.copyfile(FIX / "emf" / "notes.md", box / "notes.md")
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", box / "notes.md.cosm")
    payload = client.get("/api/canon/tree").json()
    assert set(payload) == {"root", "project", "cacheboxes"}
    vol = next(v for v in payload["cacheboxes"] if v["name"] == "v")
    assert vol["catalog"] == canon.CATALOG_NAME and vol["holotype"] is False
    names = {n["name"]: n for n in vol["tree"]}
    assert "notes.md.cosm" not in names
    assert names["notes.md"]["emf"]["state"] == "fresh"
    assert names[canon.CATALOG_NAME]["catalog"] is True
    proj = {n["name"]: n for n in payload["project"]}
    assert "notes.md.cosm" not in proj and proj["notes.md"]["emf"]["path"] == "notes.md.cosm"
    assert proj["meadow"]["holotype"] is True and proj["meadow"]["children"]   # contents still shown


def test_mirror_payload_has_volume_path_and_canon_source(client: TestClient):
    box = _store_volume(client, "m")
    (box / "guide").mkdir()
    (box / "guide" / "intro.md").write_text("x", encoding="utf-8")
    p = client.get("/api/canon/mirror", params={"box": "m"}).json()
    assert p["volume_path"] == p["box_path"] == str(box)
    assert "source: canon:m\n" in p["text"] and "📦 m" in p["text"]
    assert all(v["path"] != canon.CATALOG_NAME for v in p["node_map"].values())
    assert not (box / canon.LEGACY_MIRROR_NAME).exists()
    p = client.get("/api/canon/mirror", params={"box": "m", "path": "guide"}).json()
    assert "source: canon:m/guide\n" in p["text"]
    assert client.get("/api/canon/mirror", params={"box": "ghost"}).status_code == 404


def test_transfer_with_canon_root_and_legacy_cachebox_root(client: TestClient, project: Path):
    box = _store_volume(client, "box")
    r = client.post("/api/canon/transfer", json={
        "op": "copy", "src": {"root": "project", "path": "hello.md"},
        "dst": {"root": "canon", "box": "box", "path": "hello.md"}})
    assert r.status_code == 200, r.text
    r = client.post("/api/cacheawl/transfer", json={
        "op": "copy", "src": {"root": "cachebox", "box": "box", "path": "hello.md"},
        "dst": {"root": "project", "path": "copy.md"}})
    assert r.status_code == 200, r.text
    assert (project / "copy.md").read_text(encoding="utf-8") == "hi from the project"
    assert "hello.md" in (box / canon.CATALOG_NAME).read_text(encoding="utf-8")


def test_delete_missing_volume_is_404(client: TestClient):
    r = client.post("/api/canon/delete", json={"name": "ghost", "confirm": True})
    assert r.status_code == 404


# --------------------------------------------------------------------------
# New read routes: catalogs
# --------------------------------------------------------------------------

def test_volume_catalog_route(client: TestClient):
    box = _store_volume(client, "lib")
    (box / "a.md").write_text("a", encoding="utf-8")
    r = client.get("/api/canon/catalog", params={"volume": "lib"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["path"] == "canon:lib/canon.cosm" and p["text"].startswith("oes: canon/1\n")
    assert p["problems"] == []
    assert p["parsed"]["catalog"]["id"] == "canon/lib" and "nodes" not in p["parsed"]["catalog"]
    assert [it["path"] for it in p["parsed"]["items"]] == ["a.md"]      # reconciled first
    assert client.get("/api/canon/catalog", params={"volume": "ghost"}).status_code == 404
    assert client.get("/api/canon/catalog", params={"volume": "../x"}).status_code == 400
    assert client.get("/api/cacheawl/catalog", params={"volume": "lib"}).status_code == 404


def test_project_catalog_route_reconciles_first(client: TestClient, project: Path):
    cat = project / canon.PROJECT_CATALOG
    cat.unlink()
    (project / "later.md").write_text("later", encoding="utf-8")
    p = client.get("/api/canon/project-catalog").json()
    assert p["path"] == "rness/canon.cosm" and cat.is_file()
    assert p["problems"] == []
    paths = {it["path"]: it for it in p["parsed"]["items"]}
    assert "later.md" in paths and "notes.md.cosm" not in paths
    assert paths["notes.md"]["emf"] == {"path": "notes.md.cosm"}
    assert paths["meadow"]["holotype"] is True
    assert not any(k.startswith("rness") for k in paths)


def test_project_catalog_is_written_at_open_and_never_by_the_tree_poll(client: TestClient,
                                                                      project: Path):
    cat = project / canon.PROJECT_CATALOG
    assert cat.is_file()                                  # the startup thread wrote it
    cat.unlink()
    for _ in range(3):
        assert client.get("/api/files").status_code == 200
    assert not cat.exists()
    client.get("/api/canon/tree")                         # the Canon pane does reconcile it
    assert cat.is_file()


# --------------------------------------------------------------------------
# Paths: canon: and cacheawl:
# --------------------------------------------------------------------------

def test_both_prefixes_read_and_write_the_store(client: TestClient):
    box = _store_volume(client, "reads")
    (box / "note.md").write_text("stored body", encoding="utf-8")
    for prefix in ("canon:", "cacheawl:"):
        r = client.get("/api/file/raw", params={"path": f"{prefix}reads/note.md"})
        assert r.status_code == 200 and r.text == "stored body", prefix
    r = client.post("/api/file", data={"path": "canon:reads/fresh.md", "content": "via canon"})
    assert r.status_code == 200, r.text
    assert (box / "fresh.md").read_text(encoding="utf-8") == "via canon"


def test_prefixes_keep_the_traversal_rules(client: TestClient):
    for bad in ("canon:../../etc/passwd", "canon:box/../../escape", "canon:",
                "cacheawl:../x", "cacheawl:"):
        r = client.get("/api/file/raw", params={"path": bad})
        assert r.status_code == 400, f"{bad!r} -> {r.status_code}"


def test_project_only_features_refuse_both_prefixes(client: TestClient):
    for prefix in ("canon:", "cacheawl:"):
        assert client.get("/api/convert/status",
                          params={"path": f"{prefix}box/a.docx"}).status_code == 400
        assert client.get("/api/paginate/status",
                          params={"path": f"{prefix}box/a.md"}).status_code == 400


def test_highlights_on_a_canon_path_live_beside_the_stored_file(client: TestClient, project: Path):
    box = _store_volume(client, "hl")
    (box / "doc.md").write_text("some highlighted words here", encoding="utf-8")
    for prefix in ("canon:", "cacheawl:"):
        r = client.post("/api/highlights", data={
            "path": f"{prefix}hl/doc.md", "color": "yellow", "snippet": "highlighted"})
        assert r.status_code == 200, r.text
    assert (box / ".doc.md.highlights.json").is_file()
    assert not any(p.name.startswith(("canon:", "cacheawl:")) for p in project.iterdir())
    got = client.get("/api/highlights", params={"path": "canon:hl/doc.md"}).json()
    assert len(got["highlights"]) == 2


# --------------------------------------------------------------------------
# Write guards on POST /api/file
# --------------------------------------------------------------------------

def test_post_file_refuses_every_kept_file(client: TestClient, project: Path):
    box = _store_volume(client, "kept")
    before = (box / canon.CATALOG_NAME).read_text(encoding="utf-8")
    for path in ("canon:kept/canon.cosm", "cacheawl:kept/canon.cosm", "canon:kept/.canon.json",
                 "canon:kept/.cachebox.json", "canon:kept/_cachebox.merirmaid", "rness/canon.cosm"):
        r = client.post("/api/file", data={"path": path, "content": "CLOBBER"})
        assert r.status_code == 403, (path, r.text)
        assert LEAD in r.text, path
    assert (box / canon.CATALOG_NAME).read_text(encoding="utf-8") == before
    assert "CLOBBER" not in (project / canon.PROJECT_CATALOG).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The sidebar tree's HTML carries the flags
# --------------------------------------------------------------------------

def test_files_html_flags(client: TestClient):
    html = client.get("/api/files").text
    assert 'data-path="notes.md.cosm"' not in html
    assert 'data-emf="notes.md.cosm" data-emf-state="fresh"' in html
    assert 'data-path="rain.cosm"' in html and 'data-cosm="1"' in html
    assert 'data-holotype="1"' in html
    assert 'data-path="rness/canon.cosm"' in html and 'data-catalog="1"' in html


# --------------------------------------------------------------------------
# Home mode
# --------------------------------------------------------------------------

def test_home_mode_hides_canon_routes_alike(project: Path):
    app = create_app(project, "http://localhost:9", supervise=False, home=True)
    with TestClient(app) as c:
        for path in ("/api/canon/tree", "/api/cacheawl/tree", "/api/canon/project-catalog",
                     "/api/cosm?path=rain.cosm"):
            assert c.get(path).status_code == 404, path
        r = c.get("/api/macrocosm-spec")
        assert r.status_code == 200 and r.text.startswith("# MacroCOSM OES")
