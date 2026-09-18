"""The `/api/composure*` routes, reached the way the canvas reaches them.

Environment isolation is set explicitly rather than relied on: `HOME`, the
`ENOUGH_*` seams and `broker.CONFIG_PATH` are all pointed inside `tmp_path`
here, so these tests behave identically with or without the autouse fixture
in conftest.py. `broker.CONFIG_PATH` needs the `setattr` because it is
resolved at import time from `Path.home()` — an env var set afterwards
cannot move it.

Nothing in this file reaches the network: the webframe tests stub
`tools.fetch_and_cache`, which is the seam the endpoint actually calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import composure as C
from enough.server import create_app

REL = "rness/io/composure/board.comp"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"),
                     ("ENOUGH_CACHEAWL_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config"
                        / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    return proj


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


def seed(client: TestClient, form: str = "blank", rel: str = REL) -> dict:
    """Materialize a composure through the lazy-create door, the way the
    canvas does: `/new` describes it, the first op batch writes it."""
    r = client.post("/api/composure/ops", json={
        "path": rel, "base_rev": 0, "create": True, "form": form,
        "title": "Board",
        "ops": [{"op": "set_meta", "title": "Board"}],
    })
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# new / ops / get
# ---------------------------------------------------------------------------

def test_new_describes_without_writing(client: TestClient, project: Path):
    r = client.post("/api/composure/new", json={"form": "cards",
                                                "title": "Chapter map"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] is None                     # nothing on disk yet
    assert body["pending_path"].startswith("rness/io/composure/chapter-map-")
    assert body["form"] == "cards" and body["rev"] == 0
    assert len(body["model"]["modules"]) == 16
    assert not list((project / "rness" / "io" / "composure").glob("*.comp"))


def test_new_refuses_an_unknown_form(client: TestClient):
    r = client.post("/api/composure/new", json={"form": "nope"})
    assert r.status_code == 400 and "no composure form" in r.json()["detail"]


def test_ops_creates_then_reads_back(client: TestClient, project: Path):
    created = seed(client)
    assert created["created"] is True and created["rev"] == 1
    assert (project / REL).is_file()

    r = client.post("/api/composure/ops", json={
        "path": REL, "base_rev": created["rev"], "want_model": True,
        "ops": [{"op": "add_module", "type": "text", "bg": "yellow",
                 "markdown": "# Act one\n\nthe hero wants something"}],
    })
    body = r.json()
    assert body["rev"] == 2 and len(body["changed"]) == 1
    assert body["stale"] is False and "model" in body

    r = client.get("/api/composure", params={"path": REL})
    doc = r.json()
    assert doc["path"] == REL and doc["rev"] == 2
    mod = next(m for m in doc["model"]["modules"] if m["bg"] == "yellow")
    assert mod["pages"][0]["rich"].startswith("<h1>Act one</h1>")
    assert mod["pages"][0]["first_line"] == "Act one"


def test_ops_without_create_404s_rather_than_writing(client: TestClient):
    r = client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "set_meta", "title": "x"}]})
    assert r.status_code == 400 and "create:true" in r.json()["detail"]


def test_a_bad_op_is_a_400_with_the_cores_own_message(client: TestClient):
    seed(client)
    r = client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "add_module", "type": "applet"}]})
    assert r.status_code == 400
    assert "unknown module type" in r.json()["detail"]


def test_a_stale_base_rev_merges_and_names_what_moved(client: TestClient):
    seed(client)
    first = client.post("/api/composure/ops", json={
        "path": REL, "base_rev": 1,
        "ops": [{"op": "add_module", "type": "text"}]}).json()
    stale = client.post("/api/composure/ops", json={
        "path": REL, "base_rev": 1,
        "ops": [{"op": "add_module", "type": "text"}]}).json()
    assert stale["stale"] is True
    assert stale["stale_changed"] == first["changed"]
    assert "model" in stale                 # a stale reply always resyncs
    assert stale["rev"] == 3


def test_path_rules(client: TestClient):
    seed(client)
    for path, code, fragment in (
        ("notes/plan.md", 400, "must end in .comp"),
        ("", 400, "missing path"),
        ("../../escape.comp", 400, "invalid path"),
        ("/etc/passwd.comp", 400, "invalid path"),
    ):
        r = client.get("/api/composure", params={"path": path})
        assert r.status_code == code, (path, r.text)
        assert fragment in r.json()["detail"], (path, r.text)


def test_unknown_source_is_refused(client: TestClient):
    seed(client)
    r = client.post("/api/composure/ops", json={
        "path": REL, "source": "hacker",
        "ops": [{"op": "set_meta", "title": "x"}]})
    assert r.status_code == 400 and "unknown source" in r.json()["detail"]


def test_get_composure_sanitizes_a_hostile_file(client: TestClient,
                                                project: Path):
    """The file is edited outside the harness — which is allowed; files are
    the source of truth — and the model still comes back clean."""
    seed(client)
    target = project / REL
    raw = target.read_text(encoding="utf-8")
    target.write_text(raw.replace(
        'data-n="1">',
        'data-n="1"><script>alert(1)</script>'
        '<p onclick="x">hi</p><a href="javascript:void">l</a>', 1),
        encoding="utf-8")
    doc = client.get("/api/composure", params={"path": REL}).json()
    rich = doc["model"]["modules"][0]["pages"][0]["rich"]
    assert rich == "<p>hi</p>l"


# ---------------------------------------------------------------------------
# list / forms / rename / save-as-form
# ---------------------------------------------------------------------------

def test_list_and_forms(client: TestClient):
    seed(client)
    rows = client.get("/api/composure/list").json()["composures"]
    assert [r["path"] for r in rows] == [REL]
    forms = client.get("/api/composure/forms").json()["forms"]
    assert {f["name"] for f in forms} >= set(C.SHIPPED_FORMS)
    assert all(f["origin"] == "shipped" for f in forms)


def test_rename_moves_the_file_and_carries_the_sidecar(client: TestClient,
                                                       project: Path):
    seed(client)
    client.post("/api/composure/comments", json={
        "path": REL, "body": "keep me", "anchor": {"module": "m1"}})
    r = client.post("/api/composure/rename", json={"path": REL,
                                                   "title": "Chapter map"})
    assert r.status_code == 200, r.text
    new_rel = r.json()["path"]
    assert new_rel != REL and "chapter-map-" in new_rel
    assert (project / new_rel).is_file() and not (project / REL).exists()
    kept = client.get("/api/composure/comments", params={"path": new_rel})
    assert kept.json()["comments"][0]["body"] == "keep me"
    assert C.load(project / new_rel).title == "Chapter map"


def test_rename_refuses_to_overwrite(client: TestClient, project: Path):
    seed(client)
    other = client.post("/api/composure/rename",
                        json={"path": REL, "title": "Chapter map"}).json()["path"]
    seed(client, rel=REL)
    r = client.post("/api/composure/rename", json={"path": REL,
                                                   "title": "Chapter map"})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert (project / other).is_file()


def test_rename_can_keep_the_filename(client: TestClient, project: Path):
    seed(client)
    r = client.post("/api/composure/rename",
                    json={"path": REL, "title": "Same file",
                          "keep_filename": True})
    assert r.json()["path"] == REL
    assert C.load(project / REL).title == "Same file"


def test_save_as_form_then_use_it(client: TestClient, project: Path):
    seed(client, form="cards")
    r = client.post("/api/composure/save-as-form",
                    json={"path": REL, "name": "My Board"})
    assert r.status_code == 200, r.text
    assert r.json()["form"] == "my-board"
    names = {f["name"]: f for f in r.json()["forms"]}
    assert names["my-board"]["origin"] == "project"
    assert (project / "rness" / "composure-forms" / "my-board.comp").is_file()
    made = client.post("/api/composure/new",
                       json={"form": "my-board", "title": "From my form"})
    assert made.json()["form"] == "my-board"


# ---------------------------------------------------------------------------
# link preview
# ---------------------------------------------------------------------------

def test_link_preview_for_a_project_document(client: TestClient, project: Path):
    (project / "notes").mkdir()
    (project / "notes" / "plan.md").write_text(
        "# Plan\n\nfirst line\n\nsecond line\n", encoding="utf-8")
    seed(client)
    mid = client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "add_module", "type": "doc",
                              "href": "notes/plan.md"}]}).json()["changed"][0]
    body = client.get("/api/composure/link-preview",
                      params={"path": REL, "module": mid}).json()
    assert body["ok"] is True and body["title"] == "plan.md"
    assert "first line" in body["body"]


def test_link_preview_of_another_composure_is_its_outline(client: TestClient):
    seed(client)
    other = "rness/io/composure/other.comp"
    seed(client, form="cards", rel=other)
    mid = client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "add_module", "type": "doc",
                              "href": other}]}).json()["changed"][0]
    body = client.get("/api/composure/link-preview",
                      params={"path": REL, "module": mid}).json()
    assert body["ok"] and "composure: Board" in body["body"]


def test_link_preview_reports_a_missing_target_calmly(client: TestClient):
    seed(client)
    mid = client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "add_module", "type": "doc",
                              "href": "gone.md"}]}).json()["changed"][0]
    body = client.get("/api/composure/link-preview",
                      params={"path": REL, "module": mid}).json()
    assert body["ok"] is False and "not in this project" in body["detail"]


def test_link_preview_404s_an_unknown_module(client: TestClient):
    seed(client)
    r = client.get("/api/composure/link-preview",
                   params={"path": REL, "module": "mnope"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# webframe refresh (network stubbed at the shared pipeline seam)
# ---------------------------------------------------------------------------

def add_webframe(client: TestClient, url: str = "https://ok.example/feed") -> str:
    return client.post("/api/composure/ops", json={
        "path": REL, "ops": [{"op": "add_module", "type": "webframe",
                              "url": url}]}).json()["changed"][0]


def test_webframe_refresh_uses_the_shared_pipeline(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    from enough import tools

    def fake(project_dir, url, **kw):
        (project_dir / "rness" / "io" / "input").mkdir(parents=True,
                                                       exist_ok=True)
        (project_dir / "rness" / "io" / "input" / "page.md").write_text(
            "# Remote\n\nbody text\n", encoding="utf-8")
        return tools.CachedFetch(
            url=url, status=200, content_type="text/html", used_tor=False,
            host="ok.example", title="Remote", converted=True,
            cache_rel="rness/io/input/page.md", cache_ext="md",
            short_hash="abc12345", timestamp="2026-09-17 10:00:00",
            raw_bytes=42, content="# Remote\n\nbody text\n")

    monkeypatch.setattr(tools, "fetch_and_cache", fake)
    seed(client)
    mid = add_webframe(client)
    r = client.post("/api/composure/webframe/refresh",
                    json={"path": REL, "module": mid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["denied"] is False
    assert body["cache"] == "rness/io/input/page.md"
    assert "<h1>Remote</h1>" in body["rich"]
    m = C.load(project / REL).module(mid)
    assert m.cache == "rness/io/input/page.md"
    assert "body text" in m.pages[0].rich


@pytest.mark.parametrize("toggle", ["fetch_url_enabled",
                                    "fetch_url_tor_for_offlist"])
def test_webframe_refresh_returns_the_brokers_denial_verbatim(
        client: TestClient, toggle: str):
    """With fetch_url off, or with an off-allowlist host and Tor routing
    off, the endpoint must say exactly what the readvisor would be told —
    the user is entitled to the same sentence."""
    cfg = {t.key: t.default for t in broker.TOGGLES}
    cfg[toggle] = False
    broker.save_config(cfg)
    seed(client)
    mid = add_webframe(client)
    r = client.post("/api/composure/webframe/refresh",
                    json={"path": REL, "module": mid})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["denied"] is True
    expected = (broker.denial_tool_disabled("fetch_url")
                if toggle == "fetch_url_enabled"
                else broker.denial_off_internet_allowlist_no_tor("ok.example"))
    assert body["detail"] == expected


def test_webframe_refresh_refuses_a_non_webframe_module(client: TestClient,
                                                        project: Path):
    seed(client)
    mid = C.load(project / REL).modules[0].id
    r = client.post("/api/composure/webframe/refresh",
                    json={"path": REL, "module": mid})
    assert r.status_code == 400 and "not a webframe" in r.json()["detail"]


# ---------------------------------------------------------------------------
# comments
# ---------------------------------------------------------------------------

def test_comment_crud_over_http(client: TestClient, project: Path):
    seed(client)
    empty = client.get("/api/composure/comments", params={"path": REL}).json()
    assert empty["comments"] == []

    made = client.post("/api/composure/comments", json={
        "path": REL, "body": "why this order?",
        "anchor": {"type": "quote", "module": "m1", "page": 1,
                   "quote": "the hero"}}).json()
    assert made["state"] == "anchored"

    reply = client.post("/api/composure/comments", json={
        "path": REL, "comment": made["id"], "body": "because of act three"})
    assert reply.status_code == 200

    patched = client.patch("/api/composure/comments", json={
        "path": REL, "id": made["id"], "resolved": True}).json()
    assert patched["resolved"] is True

    doc = client.get("/api/composure/comments", params={"path": REL}).json()
    assert len(doc["comments"]) == 1 and len(doc["comments"][0]["replies"]) == 1
    assert doc["doc_path"] == REL

    gone = client.delete("/api/composure/comments",
                         params={"path": REL, "id": made["id"]})
    assert gone.status_code == 200
    assert not C.comments_path(project / REL).exists()


def test_comment_errors(client: TestClient):
    seed(client)
    assert client.post("/api/composure/comments",
                       json={"path": REL, "body": "  "}).status_code == 400
    assert client.post("/api/composure/comments", json={
        "path": REL, "comment": "c_nope", "body": "x"}).status_code == 404
    assert client.patch("/api/composure/comments", json={
        "path": REL, "id": "c_nope", "body": "x"}).status_code == 404
    assert client.patch("/api/composure/comments", json={
        "path": REL, "id": "c_x", "state": "wat"}).status_code == 400
    assert client.delete("/api/composure/comments",
                         params={"path": REL, "id": "c_nope"}).status_code == 404


def test_a_comment_survives_on_a_filed_journal_page(client: TestClient,
                                                    project: Path):
    rel = "rness/io/composure/journal.comp"
    seed(client, form="journal", rel=rel)
    mid = C.load(project / rel).modules[0].id
    client.post("/api/composure/ops", json={
        "path": rel, "ops": [{"op": "file_page", "module": mid, "n": 1}]})
    blocked = client.post("/api/composure/ops", json={
        "path": rel, "ops": [{"op": "set_page", "module": mid, "n": 1,
                              "markdown": "rewrite"}]})
    assert blocked.status_code == 400
    assert "permanently read-only" in blocked.json()["detail"]
    ok = client.post("/api/composure/comments", json={
        "path": rel, "body": "a thought about a filed day",
        "anchor": {"module": mid}})
    assert ok.status_code == 200


# ---------------------------------------------------------------------------
# write doors, tree, launch
# ---------------------------------------------------------------------------

def test_post_api_file_refuses_comp_and_its_sidecar(client: TestClient):
    seed(client)
    r = client.post("/api/file", data={"path": REL, "content": "<html>x"})
    assert r.status_code == 403 and "module-by-module" in r.json()["detail"]
    r = client.post("/api/file", data={
        "path": "rness/io/composure/.board.comp.comments.json",
        "content": "[]"})
    assert r.status_code == 403 and "backend-owned" in r.json()["detail"]


def test_the_tree_marks_comp_files_and_hides_the_sidecar(client: TestClient):
    seed(client)
    client.post("/api/composure/comments",
                json={"path": REL, "body": "x", "anchor": {"module": "m1"}})
    html = client.get("/api/files").text
    assert "board.comp" in html
    assert ".board.comp.comments.json" not in html


def test_launch_setting_round_trip(client: TestClient):
    assert client.get("/api/composure/launch").json() == {
        "launch": "blank", "path": None, "form": "blank", "notice": ""}

    seed(client)
    # Opening a composure stamps `last`, whatever the launch mode is.
    client.get("/api/composure", params={"path": REL})
    saved = client.post("/api/project/composure", json={"launch": "last"})
    assert saved.status_code == 200
    assert saved.json()["composure"] == {"launch": "last", "path": "",
                                         "form": "", "last": REL}
    assert client.get("/api/composure/launch").json()["path"] == REL

    client.post("/api/project/composure", json={"launch": "file", "path": REL})
    assert client.get("/api/composure/launch").json() == {
        "launch": "file", "path": REL, "form": None, "notice": ""}

    client.post("/api/project/composure", json={"launch": "form",
                                                "form": "scaffold"})
    assert client.get("/api/composure/launch").json()["form"] == "scaffold"

    r = client.post("/api/project/composure", json={"launch": "sideways"})
    assert r.status_code == 400 and "launch must be one of" in r.json()["detail"]


def test_launch_falls_back_to_blank_with_a_notice(client: TestClient,
                                                  project: Path):
    seed(client)
    client.post("/api/project/composure", json={"launch": "file", "path": REL})
    (project / REL).unlink()
    body = client.get("/api/composure/launch").json()
    assert body["launch"] == "blank" and "no longer there" in body["notice"]

    client.post("/api/project/composure", json={"launch": "form",
                                                "form": "gone-form"})
    body = client.get("/api/composure/launch").json()
    assert body["launch"] == "blank" and "no longer installed" in body["notice"]


def test_composure_routes_404_on_a_home_server(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False,
                     home=True)
    with TestClient(app) as c:
        assert c.get("/api/composure/list").status_code == 404
        assert c.post("/api/composure/new", json={}).status_code == 404


def test_the_sse_event_fires_on_every_batch(project: Path):
    """The canvas stays live off this event; without it a readvisor edit
    would be invisible until reload. Built here with three lambdas, which
    is also the assertion that `build_router` needs nothing else."""
    from fastapi import FastAPI

    from enough import composure_api

    seen: list[tuple[str, dict]] = []

    async def emit(event: str, data: dict) -> None:
        seen.append((event, data))

    def resolve(rel: str) -> Path:
        candidate = Path(rel)
        assert not candidate.is_absolute() and ".." not in candidate.parts
        return project.resolve() / candidate

    app = FastAPI()
    app.include_router(composure_api.build_router(
        project_dir=project, resolve_path=resolve, emit=emit))
    with TestClient(app) as c:
        created = c.post("/api/composure/ops", json={
            "path": REL, "create": True, "form": "blank", "title": "Board",
            "ops": [{"op": "set_meta", "title": "Board"}]}).json()
        second = c.post("/api/composure/ops", json={
            "path": REL, "base_rev": created["rev"], "source": "readvisor",
            "ops": [{"op": "add_module", "type": "text"}]}).json()

    assert [e for e, _ in seen] == [composure_api.EVENT] * 2
    assert seen[0][1] == {"path": REL, "rev": 1, "changed": [],
                          "source": "ui", "created": True}
    assert seen[1][1] == {"path": REL, "rev": 2, "changed": second["changed"],
                          "source": "readvisor", "created": False}


def test_model_is_json_serializable_end_to_end(client: TestClient):
    seed(client, form="scaffold")
    doc = client.get("/api/composure", params={"path": REL}).json()
    json.dumps(doc)
    assert len(doc["model"]["modules"]) == 29
    assert doc["model"]["caps"]["page_chars"] == C.MAX_PAGE_CHARS
