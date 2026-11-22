"""enough's route guards (0.9, pins section 5): the Origin gate on every route that changes state, the promise header
on the older model-run routes, a page save through a link to a shared file making the project's own copy, and the
composure door setting a batch's source itself."""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import api_promise as P
from enough import composure as C
from enough import fabula_tools as FT
from enough import models, skeleton
from enough import origin_gate as G
from enough.routes import files as RF
from enough.server import create_app

PORT = 3456
FOREIGN = ("https://evil.example", "http://127.0.0.1:5173", "http://localhost:8080", "null",
           "http://127.0.0.1.evil.example:3456", "http://192.168.1.4:3456")
OWN = ("http://127.0.0.1:3456", "http://localhost:3456", "http://[::1]:3456", "http://testserver",
       "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost")


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, home: bool = False):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / ("home-dir" if home else "project")
    proj.mkdir()
    if not home:
        skeleton.ensure_skeleton(proj)
    return create_app(proj, "http://127.0.0.1:9", supervise=False, home=home, port=PORT), proj


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, _ = _make(tmp_path, monkeypatch)
    yield a
    FT.configure()


@pytest.fixture
def home_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, _ = _make(tmp_path, monkeypatch, home=True)
    yield a


def _state_changing(app) -> list[tuple[str, str, str]]:
    """(method, path with its parameters filled, module) for every registered route that changes state."""
    out = []
    for r in app.router.routes:
        for m in sorted(getattr(r, "methods", None) or ()):
            path = getattr(r, "path", "")
            if not G.guarded(m, path):
                continue
            ep = getattr(r, "endpoint", None)
            mod = inspect.getmodule(ep).__name__ if ep else "?"
            out.append((m, re.sub(r"\{[^}]+\}", "x", path), mod))
    return out


# ---------------------------------------------------------------- 1. the Origin gate

def test_own_origins_and_foreign_ones_by_the_rule():
    server = ("127.0.0.1", PORT)
    for o in OWN[:3] + OWN[4:]:
        assert G.own_origin(o, server), o
    assert G.own_origin("http://testserver", ("testserver", 80))
    for o in FOREIGN:
        assert not G.own_origin(o, server), o
    # The port is the socket's, or the one the app was made for: never one a page names.
    assert not G.own_origin("http://127.0.0.1:3457", server)
    assert G.own_origin("http://127.0.0.1:4000", ("testserver", 80), port=4000)


def test_what_is_guarded():
    for m in ("POST", "PUT", "PATCH", "DELETE"):
        assert G.guarded(m, "/api/anything")
    assert not G.guarded("GET", "/api/stream") and not G.guarded("GET", "/static/index.html")
    # A HEAD runs the GET's handler, so a HEAD of a GET that changes state is guarded as the GET is.
    assert G.guarded("HEAD", "/api/reset") and not G.guarded("HEAD", "/api/project")
    assert not G.guarded("OPTIONS", "/api/chat")
    for p in ("/api/reset", "/api/update-enough", "/api/reveal"):
        assert G.guarded("GET", p)


def test_every_state_changing_route_refuses_a_foreign_origin(app, home_app):
    """The sweep: every registered route that changes state, in project mode and in home mode, every route module."""
    for a in (app, home_app):
        routes = _state_changing(a)
        assert len(routes) > 100 if a is app else routes
        with TestClient(a) as c:
            for method, path, mod in routes:
                for origin in ("https://evil.example", "null"):
                    got = c.request(method, path, headers={"Origin": origin, P.HEADER: "1"})
                    assert got.status_code == 403, (method, path, mod, got.status_code)
                    assert got.json()["detail"] == G.REFUSED.format(origin=origin), (method, path)


def test_the_sweep_reaches_every_route_module(app):
    mods = {mod for _m, _p, mod in _state_changing(app)}
    for want in ("enough.allograph_api", "enough.composure_api", "enough.council_api", "enough.dialectic_api",
                 "enough.dictionary_api", "enough.fabulac_job", "enough.fabulap_job", "enough.thym_api",
                 "enough.routes.canon", "enough.routes.chat", "enough.routes.convert", "enough.routes.docs",
                 "enough.routes.fabula", "enough.routes.fabulac", "enough.routes.files", "enough.routes.girraph",
                 "enough.routes.help", "enough.routes.home", "enough.routes.models",
                 "enough.routes.paradigm_skills", "enough.routes.project", "enough.routes.settings",
                 "enough.routes.wiki"):
        assert want in mods, want


#: One route from each module that is safe to send an empty request to: (method, path, body).
SAMPLE = (
    ("POST", "/api/connect/sign-out", {}),                    # allograph_api
    ("POST", "/api/composure/new", {"form": "blank"}),         # composure_api
    ("POST", "/api/council/pause", {}),                        # council_api
    ("POST", "/api/dialectic/check", {}),                      # dialectic_api
    ("DELETE", "/api/dict/user/zzzzunknown", None),            # dictionary_api
    ("POST", "/api/fabula/cancel", {}),                        # fabulac_job
    ("POST", "/api/fabula/verse/cancel", {}),                  # fabulap_job
    ("POST", "/api/thym/compile", {}),                         # thym_api
    ("POST", "/api/cosm/lint", {}),                            # routes.canon
    ("GET", "/api/reset", None),                               # routes.chat (a GET that changes state)
    ("POST", "/api/convert/resolve", {}),                      # routes.convert
    ("POST", "/api/docs/compile", {}),                         # routes.docs
    ("POST", "/api/canon/job/nothing/cancel", {}),             # routes.fabula
    ("POST", "/api/fabulac/stop", {"path": "nothing"}),        # routes.fabulac
    ("POST", "/api/file/dismiss-undo", {}),                    # routes.files
    ("DELETE", "/api/girraph/node", None),                     # routes.girraph
    ("POST", "/api/requests/done", {}),                        # routes.help
    ("POST", "/api/shutdown", {}),                             # routes.home (404 without the desktop shell)
    ("POST", "/api/models/download/nothing/cancel", {}),       # routes.models
    ("POST", "/api/roles/toggle", {}),                         # routes.paradigm_skills
    ("POST", "/api/project/ui", {}),                           # routes.project
    ("POST", "/api/readvisor/chief", {}),                      # routes.settings
    ("POST", "/api/wiki/unsave", {}),                          # routes.wiki
)


def _send(c: TestClient, method: str, path: str, body, headers: dict):
    if body is None:
        return c.request(method, path, headers=headers)
    return c.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize("method,path,body", SAMPLE, ids=[p for _m, p, _b in SAMPLE])
def test_a_foreign_origin_is_refused_and_no_origin_and_own_origins_pass(app, method, path, body):
    refusals = {G.REFUSED.format(origin=o) for o in FOREIGN} | {G.REFUSED_SITE}
    with TestClient(app) as c:
        for origin in FOREIGN:
            got = _send(c, method, path, body, {"Origin": origin, P.HEADER: "1"})
            assert got.status_code == 403 and got.json()["detail"] == G.REFUSED.format(origin=origin), origin
        for headers in ({}, *({"Origin": o} for o in OWN), {"Sec-Fetch-Site": "same-origin"},
                        {"Sec-Fetch-Site": "none"}):
            got = _send(c, method, path, body, {**headers, P.HEADER: "1"})
            detail = got.json().get("detail") if got.headers.get("content-type", "").startswith(
                "application/json") else None
            assert str(detail) not in refusals, (headers, got.status_code, detail)


def test_a_link_from_another_site_without_origin_is_refused(app):
    with TestClient(app) as c:
        for site in ("cross-site", "same-site"):
            got = c.get("/api/reset", headers={"Sec-Fetch-Site": site})
            assert got.status_code == 403 and got.json()["detail"] == G.REFUSED_SITE
            got = c.post("/api/file/dismiss-undo", json={}, headers={"Sec-Fetch-Site": site})
            assert got.status_code == 403


def test_reads_the_stream_and_static_are_left_alone(app):
    with TestClient(app) as c:
        for path in ("/api/project", "/api/files", "/static/htmx.min.js", "/"):
            got = c.get(path, headers={"Origin": "https://evil.example"})
            assert got.status_code == 200, path
    assert G.refusal("GET", "/api/stream", "https://evil.example", "cross-site", ("127.0.0.1", PORT)) is None


# ---------------------------------------------------------------- 2. the promise header on the model-run routes

def test_every_model_run_route_is_the_apps(app):
    have = {(m, r.path) for r in app.router.routes for m in (getattr(r, "methods", None) or ())}
    for path in P.MODEL_RUNS:
        assert ("POST", path) in have, path
    council = {p for m, p in have if m == "POST" and p.startswith("/api/council/")}
    assert council - P.MODEL_RUN_OPEN and "/api/council/pause" in council


def _model_run_routes(app) -> list[str]:
    return sorted({r.path for r in app.router.routes
                   if "POST" in (getattr(r, "methods", None) or ()) and P.model_run("POST", r.path)})


def test_a_model_run_route_refuses_without_the_header(app):
    routes = _model_run_routes(app)
    assert set(P.MODEL_RUNS) <= set(routes) and "/api/council/convene" in routes
    with TestClient(app) as c:
        for path in routes:
            got = c.post(path, json={})
            assert got.status_code == 403 and got.json()["detail"] == P.MODEL_RUN_MISSING, path
            got = c.post(path, json={}, headers={P.HEADER: "2"})
            assert got.status_code == 403 and "keeps API promise 1" in got.json()["detail"], path
        # Stopping a council is always allowed, and loading a model is the Origin gate's alone (the shell posts it).
        assert c.post("/api/council/pause", json={}).json().get("detail") != P.MODEL_RUN_MISSING
        assert not P.model_run("POST", "/api/model") and not P.model_run("GET", "/api/chat")


def test_with_the_header_a_model_run_route_is_not_refused_by_the_gate(app):
    with TestClient(app) as c:
        for path in ("/api/thym/run", "/api/fabula/build", "/api/dialectic/settle", "/api/council/convene"):
            got = c.post(path, json={}, headers={P.HEADER: "1"})
            assert got.json().get("detail") not in (P.MODEL_RUN_MISSING, P.MISSING), (path, got.json())


def test_the_page_sends_the_header_on_every_api_call():
    page = (Path(__file__).resolve().parents[1] / "enough" / "static" / "index.html").read_text(encoding="utf-8")
    head = page[:page.index("</head>")]
    assert "window.fetch = function enoughFetch" in head and "ENOUGH_API_HEADER = 'X-Enough-Api'" in head
    assert "htmx:configRequest" in page and "e.detail.headers[ENOUGH_API_HEADER] = '1'" in page


# ---------------------------------------------------------------- 3. a save through a link to a shared file

def _save(c: TestClient, path: str, text: str):
    return c.post("/api/file", data={"path": path, "content": text})


def test_a_save_to_a_linked_paradigm_makes_a_project_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, proj = _make(tmp_path, monkeypatch)
    shared = tmp_path / "global" / "paradigms" / "house.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("the shared text\n", encoding="utf-8")
    link = proj / "rness" / "paradigms" / "house.md"
    link.symlink_to(shared)
    with TestClient(a) as c:
        got = _save(c, "rness/paradigms/house.md", "this project's text\n")
        assert got.status_code == 200, got.text
        assert got.headers.get(RF.UNLINKED_HEADER) == "1"
        assert 'class="file-unlinked"' in got.text
        assert shared.read_text(encoding="utf-8") == "the shared text\n"
        assert not link.is_symlink() and link.read_text(encoding="utf-8") == "this project's text\n"
        # A second save is an ordinary one, and undo goes back to the shared text, still in the project's own file.
        again = _save(c, "rness/paradigms/house.md", "and again\n")
        assert again.status_code == 200 and RF.UNLINKED_HEADER not in again.headers
        undo = c.post("/api/file/undo", data={"path": "rness/paradigms/house.md"})
        assert undo.status_code == 200
    assert shared.read_text(encoding="utf-8") == "the shared text\n"
    FT.configure()


def test_a_save_to_a_linked_policy_in_the_install_defaults_makes_a_project_copy(tmp_path: Path,
                                                                                monkeypatch: pytest.MonkeyPatch):
    a, proj = _make(tmp_path, monkeypatch)
    fake_defaults = tmp_path / "install" / "defaults"
    shared = fake_defaults / "policies" / "house-rules.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("shared rules\n", encoding="utf-8")
    monkeypatch.setattr(skeleton, "_install_defaults_root", lambda: fake_defaults)
    link = proj / "rness" / "policies" / "house-rules.md"
    link.symlink_to(shared)
    with TestClient(a) as c:
        got = _save(c, "rness/policies/house-rules.md", "our rules\n")
        assert got.status_code == 200 and got.headers.get(RF.UNLINKED_HEADER) == "1"
    assert shared.read_text(encoding="utf-8") == "shared rules\n"
    assert link.is_file() and not link.is_symlink() and link.read_text(encoding="utf-8") == "our rules\n"
    FT.configure()


def test_a_save_to_a_link_of_the_persons_own_writes_through_as_before(tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch):
    a, proj = _make(tmp_path, monkeypatch)
    mine = tmp_path / "elsewhere" / "notes.md"
    mine.parent.mkdir()
    mine.write_text("old\n", encoding="utf-8")
    link = proj / "notes.md"
    link.symlink_to(mine)
    with TestClient(a) as c:
        got = _save(c, "notes.md", "new\n")
        assert got.status_code == 200 and RF.UNLINKED_HEADER not in got.headers
    assert link.is_symlink() and mine.read_text(encoding="utf-8") == "new\n"
    FT.configure()


def test_a_linked_skill_is_still_refused(app):
    with TestClient(app) as c:
        got = _save(c, "rness/skills/anything/SKILL.md", "x")
        assert got.status_code == 403 and "skill files" in got.json()["detail"]


def test_the_page_says_so_in_one_line_in_six_languages():
    root = Path(__file__).resolve().parents[1] / "enough" / "static"
    page = (root / "index.html").read_text(encoding="utf-8")
    assert "t('file.unlinked'," in page and "'enough:unlinked'" in page
    for lang in ("en", "fr", "es", "de", "zh", "ja"):
        strings = json.loads((root / "i18n" / lang / "ui.json").read_text(encoding="utf-8"))["strings"]
        assert strings.get("file.unlinked"), lang


# ---------------------------------------------------------------- 4. the composure door sets the source

REL = "rness/io/composure/plane.comp"


def _seed(c: TestClient, form: str = "blank", rel: str = REL) -> dict:
    r = c.post("/api/composure/ops", json={"path": rel, "base_rev": 0, "create": True, "form": form,
                                           "title": "Plane", "ops": [{"op": "set_meta", "title": "Plane"}]})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_client_may_not_claim_a_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, proj = _make(tmp_path, monkeypatch)
    with TestClient(a) as c:
        _seed(c)
        before = len(C.load(proj / REL).modules)
        for claimed in ("readvisor", "council", "enough", "hacker", "UI"):
            got = c.post("/api/composure/ops", json={"path": REL, "source": claimed,
                                                     "ops": [{"op": "add_module", "type": "text"}]})
            assert got.status_code == 403, claimed
            assert "the server sets a batch's source" in got.json()["detail"], claimed
        for fine in ({}, {"source": "ui"}, {"source": None}):
            got = c.post("/api/composure/ops", json={"path": REL, **fine,
                                                     "ops": [{"op": "add_module", "type": "text"}]})
            assert got.status_code == 200, (fine, got.text)
    assert len(C.load(proj / REL).modules) == before + 3      # the refused five added nothing
    FT.configure()


def test_a_journal_module_with_a_filed_page_cannot_be_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, proj = _make(tmp_path, monkeypatch)
    rel = "rness/io/composure/journal.comp"
    with TestClient(a) as c:
        _seed(c, form="journal", rel=rel)
        mid = C.load(proj / rel).modules[0].id
        filed = c.post("/api/composure/ops", json={"path": rel, "ops": [{"op": "file_page", "module": mid, "n": 1}]})
        assert filed.status_code == 200, filed.text
        gone = c.post("/api/composure/ops", json={"path": rel, "ops": [{"op": "remove_module", "id": mid}]})
        assert gone.status_code == 400 and "filed page" in gone.json()["detail"]
    assert [m.id for m in C.load(proj / rel).modules] == [mid]
    FT.configure()
