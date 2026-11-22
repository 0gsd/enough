"""enough's API promise (0.8, fabulac-first F6: pins section 4): one table (`enough/api_promise.py`), the app's
routes and the client (`enough/enough_client.py`) held to each other; the header gate (`X-Enough-Api: 1`) on every
promised route that starts a run or writes, with the header and without; the reference table lists them all."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import api_promise as P
from enough import enough_client as EC
from enough import fabula_tools as FT
from enough import models, skeleton
from enough.server import create_app

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    a = create_app(proj, "http://127.0.0.1:9", supervise=False)
    yield a
    FT.configure()


def _app_routes(app) -> set[tuple[str, str]]:
    out = set()
    for r in app.router.routes:
        for m in getattr(r, "methods", None) or ():
            if m in ("GET", "POST"):
                out.add((m, getattr(r, "path", "")))
    return out


def test_the_table_is_one_version_and_each_post_is_gated():
    assert P.VERSION == 1 and P.HEADER == "X-Enough-Api"
    keys = [(r.method, r.path) for r in P.ROUTES]
    assert len(keys) == len(set(keys))
    for r in P.ROUTES:
        assert r.gated == (r.method == "POST"), r
        assert r.does and r.gives and r.since == 1
    pay = P.payload()
    assert pay["version"] == 1 and len(pay["routes"]) == len(P.ROUTES)


def test_every_promised_route_is_the_apps_and_every_fabulac_route_is_promised(app):
    have = _app_routes(app)
    promised = {(r.method, r.path) for r in P.ROUTES}
    assert promised <= have, promised - have
    ours = {(m, p) for m, p in have if p.startswith("/api/fabulac/")}
    assert ours == {(m, p) for m, p in promised if p.startswith("/api/fabulac/")}


def test_the_client_calls_exactly_the_promised_routes():
    promised = {(r.method, r.path) for r in P.ROUTES}
    assert set(EC.CALLS) == promised
    assert EC.PROMISE == P.VERSION and EC.HEADER == P.HEADER
    src = (REPO / "enough" / "enough_client.py").read_text(encoding="utf-8")
    used = set(re.findall(r'"(/api/[a-z/{}_-]+)"', src))
    assert used <= {p for _m, p in promised} | {"/api/canon/job/"}, used - {p for _m, p in promised}
    for m, p in promised:
        if "{" not in p:
            assert f'"{p}"' in src.split("CALLS: tuple")[0], p


def test_the_client_is_one_file_of_the_standard_library():
    tree = ast.parse((REPO / "enough" / "enough_client.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "the client imports nothing of enough"
            names.add((node.module or "").split(".")[0])
    assert names - {"__future__"} <= set(sys.stdlib_module_names), names


def test_a_gated_route_without_the_header_is_403_with_a_sentence(app):
    with TestClient(app) as c:
        for r in P.ROUTES:
            if not r.gated:
                continue
            got = c.post(r.path, json={"path": "nothing"})
            assert got.status_code == 403, (r.path, got.status_code)
            assert got.json()["detail"] == P.MISSING
            got = c.post(r.path, json={"path": "nothing"}, headers={P.HEADER: "2"})
            assert got.status_code == 403 and "keeps API promise 1" in got.json()["detail"], r.path
            got = c.post(r.path, json={"path": "nothing"}, headers={P.HEADER: "1"})
            assert got.status_code != 403, (r.path, got.json())


def test_a_read_route_needs_no_header(app):
    with TestClient(app) as c:
        for r in P.ROUTES:
            if r.gated or "{" in r.path:
                continue
            got = c.get(r.path, params={"path": "nothing"})
            assert got.status_code != 403, (r.path, got.json())
        assert c.get("/api/fabulac/promise").json()["version"] == 1


def test_the_gate_leaves_every_other_route_alone():
    # 0.9: the older model-run routes take the header too (tests/test_route_guards.py); other routes need none.
    assert P.refusal("POST", "/api/fabula/build", None) == P.MODEL_RUN_MISSING
    assert P.refusal("POST", "/api/file", None) is None
    assert P.refusal("POST", "/api/council/pause", None) is None
    assert P.refusal("GET", "/api/fabulac/status", None) is None
    assert P.refusal("POST", "/api/fabulac/test", None) == P.MISSING
    assert P.refusal("POST", "/api/fabulac/test", " 1 ") is None


def test_the_reference_table_lists_every_route_word_and_check():
    ref = (REPO / "docs" / "DEVELOPERS.md").read_text(encoding="utf-8")   # its section 6, the reference
    for r in P.ROUTES:
        assert f"`{r.method} {r.path}`" in ref, r.path
    for word in FT.FIRST_DO + ("build", "status", "compile", "cancel"):
        assert f"`<do>{word}</do>`" in ref, word
    from enough.fabulac_cli import build_parser
    sub = next(a for a in build_parser()._actions if a.dest == "cmd")
    for cmd in sub.choices:
        assert f"`python -m enough.fabulac {cmd}" in ref, cmd
    for move in ("author", "add", "compare", "uncovered"):
        assert f"`{move}" in ref, move
    for check in ("authored-source", "cases-entailed", "requirement-cased", "parts-resolve", "interfaces-agree",
                  "files-present", "interfaces-present", "footer"):
        assert f"`{check}`" in ref, check
    for name in ("starters", "begin", "add", "check", "entail", "test", "run", "stop", "status", "moved", "keep",
                 "let_go", "take_back", "head", "parts_moved", "answer"):
        assert f"`e.{name}(" in ref, name


def test_the_reference_lists_the_fabulams_routes_the_pick_answer_and_the_two_gates(app):
    """0.9 (lane M7): the fabulam's five routes (not promised, so not in `ROUTES`), the answer a build gives when a
    file ends in several results, and the two gates every route passes, the Origin gate and the header on the older
    model-run routes, are all in the reference, held to the app and to `api_promise`."""
    ref = (REPO / "docs" / "DEVELOPERS.md").read_text(encoding="utf-8")
    fabulam = {(m, p) for m, p in _app_routes(app) if p.startswith("/api/fabulam/")}
    assert len(fabulam) == 5, fabulam
    for method, path in fabulam:
        assert f"`{method} {path}`" in ref, path
    assert '{"job": null, "targets": [' in ref and '"check": "pick"' in ref
    for word in ("build", "resume", "status", "cancel", "entail"):
        assert f"`<do>{word}</do>`" in ref, word
    assert "`enough/origin_gate.py`" in ref and "`X-Enough-Api: 1`" in ref
    for path in P.MODEL_RUNS | set(P.MODEL_RUN_OPEN):
        assert f"`{path}`" in ref, path
    for prefix in P.MODEL_RUN_PREFIXES:
        assert f"every POST under `{prefix}`" in ref, prefix
