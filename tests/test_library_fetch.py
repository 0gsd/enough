"""The language library fetched on demand from cosmoes.org and cached (0.8, lane W4-LS; ruled 2026-11-19).

Never the real site: a stand-in on a loopback port serves a copy of the made-up fixture shelf
(`tests/fixtures/library-shelf/`, cosmoes-site's) in the site's own layout — `/library/library.json`,
`/library/<shelf>/<text>/<version>/SHA256SUMS|NOTICE|FETCHED` and `…/raw/<path>` — and logs what it was asked. One
test asks cosmoes-site's own app instead, when a checkout with the `/library/library.json` route is on this machine.
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import sys
import threading
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from enough import language_library as ll, library_fetch as lf, library_index as li
from enough import transconception as tc

REPO = Path(__file__).resolve().parent.parent
SHELF = REPO / "tests" / "fixtures" / "library-shelf"
MANUAL = {"in": "example/manual", "version": "1.0", "at": "library/strings.html#text.count"}
SHEET = {"in": "example/sheet", "version": "2", "at": "sheet.html#sec-copyright"}


# ---------------------------------------------------------------------------
# the stand-in
# ---------------------------------------------------------------------------

class StandIn:
    """cosmoes.org's library routes over a folder, on 127.0.0.1. `asked` lists every path asked for."""

    def __init__(self, root: Path):
        self.root = root
        self.asked: list[str] = []
        stand = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):            # quiet
                pass

            def do_GET(self):                     # noqa: N802
                path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
                stand.asked.append(path)
                body = stand.body(path)
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/library"

    def body(self, path: str) -> bytes | None:
        if not path.startswith("/library/") or ".." in path.split("/"):
            return None
        rest = path[len("/library/"):]
        if rest == "library.json":
            p = self.root / "library.json"
        else:
            parts = rest.split("/")
            if len(parts) == 4 and parts[3] in li.META_FILES:
                p = self.root.joinpath(*parts)
            elif len(parts) >= 5 and parts[3] == "raw":
                p = self.root.joinpath(*parts[:3], "files", *parts[4:])
            else:
                return None
        return p.read_bytes() if p.is_file() else None

    def raw_asked(self) -> list[str]:
        return [a for a in self.asked if "/raw/" in a]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def env(tmp_path, monkeypatch):
    """No synced shelf, a fresh state root, the fetch allowed, and a stand-in serving a copy of the fixture shelf."""
    site = tmp_path / "site"
    shutil.copytree(SHELF, site)
    stand = StandIn(site)
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "1")
    monkeypatch.setenv("ENOUGH_LIBRARY_URL", stand.url)
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(tmp_path / "no-shelf"))
    monkeypatch.setenv("ENOUGH_LANGUAGES_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setattr(ll, "_LOCAL", {})
    lf.reset_for_tests()
    yield stand
    lib = ll._LOCAL and next(iter(ll._LOCAL.values()))
    if lib and lib.fetcher:
        lib.fetcher.wait(10)
    lf.reset_for_tests()
    stand.close()


def _fresh_launch(monkeypatch) -> None:
    monkeypatch.setattr(ll, "_LOCAL", {})
    lf.reset_for_tests()


def _cache() -> Path:
    return ll.cache_dir()


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# where and whether
# ---------------------------------------------------------------------------

def test_only_cosmoes_org_or_a_loopback_stand_in_is_asked():
    assert lf.check_url("https://cosmoes.org/library/") == "https://cosmoes.org/library"
    assert lf.check_url("http://127.0.0.1:8791/library") == "http://127.0.0.1:8791/library"
    for bad in ("http://cosmoes.org/library", "https://cosmoes.org:8443/library", "https://example.org/library",
                "https://cosmoes.org.example.org/library", "http://10.0.0.1/library", "file:///tmp/library",
                "https://cosmoes.org/library?x=1"):
        with pytest.raises(ValueError):
            lf.check_url(bad)
    assert lf.DEFAULT_URL == "https://cosmoes.org/library"


def test_the_fetch_follows_the_spec_syncs_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(tmp_path / "no-shelf"))
    monkeypatch.setenv("ENOUGH_LANGUAGES_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    monkeypatch.setattr(ll, "_LOCAL", {})
    lf.reset_for_tests()
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "0")                      # every test and scratch rig
    assert lf.allowed() == (False, "ENOUGH_SPECS_SYNC=0")
    assert ll.local() is None                                         # nothing synced, nothing cached, no fetch
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "1")
    monkeypatch.setenv("ENOUGH_LIBRARY_URL", "http://127.0.0.1:1/library")
    (tmp_path / "ui.json").write_text(json.dumps({"specs_sync": False}))
    ok, why = lf.allowed()
    assert not ok and "preference" in why
    (tmp_path / "ui.json").write_text(json.dumps({"specs_sync": True, "agent_free": True}))
    assert lf.allowed() == (True, "")                                 # agent-free does not stop it, as with specs
    monkeypatch.setenv("ENOUGH_LIBRARY_URL", "https://example.org/library")
    assert lf.allowed()[0] is False


def test_scratch_runs_point_the_library_at_nothing():
    from enough import seams
    assert seams.FIXED_SEAMS["ENOUGH_LIBRARY_URL"].startswith("http://127.0.0.1:1/")
    assert seams.FIXED_SEAMS["ENOUGH_SPECS_SYNC"] == "0"


# ---------------------------------------------------------------------------
# on demand: fetching, then resolved
# ---------------------------------------------------------------------------

def test_a_citation_reads_fetching_then_resolves_and_the_copy_is_the_sites(env):
    lib = ll.local()
    assert lib is not None and lib.root == _cache() and lib.fetcher is not None
    first = lib.cite(MANUAL)
    assert first["state"] == "fetching" and "ask again" in first["why"]
    assert tc.resolve_citation(MANUAL, lib)[0] is None                # a warning while it is fetched, never an error
    assert lib.fetcher.wait(10)
    got = lib.cite(MANUAL)
    assert got["state"] == "resolved" and got["hit"].heading == "text.count"
    assert tc.resolve_citation(MANUAL, lib) == (True, "")
    # the copy is the site's, byte for byte, and only what was asked for is kept
    assert _tree(_cache() / "example/manual/1.0") == _tree(SHELF / "example/manual/1.0")
    assert not (_cache() / "example/sheet").exists() and not (_cache() / "memos").exists()
    assert not list(_cache().glob(".fetch-*")) and not list(_cache().glob(".part-*"))
    assert (_cache() / lf.REMOTE_REGISTRY).read_bytes() == (SHELF / "library.json").read_bytes()
    ours = json.loads((_cache() / "library.json").read_text())
    assert {(e["text"], e["aboard"]) for e in ours["texts"]} == {("manual", True), ("runner", False),
                                                                 ("sheet", False), ("memo", False)}
    rec = json.loads((_cache() / lf.FETCHED_RECORD).read_text())
    assert list(rec) == ["example/manual/1.0"] and rec["example/manual/1.0"]["files"] == 4
    assert sorted(env.raw_asked()) == sorted(f"/library/example/manual/1.0/raw/{r[len('files/'):]}"
                                             for r in li.walk_files(SHELF / "example/manual/1.0"))


def test_with_wait_a_citation_resolves_in_one_ask(env):
    lib = ll.local()
    got = lib.cite(SHEET, wait=10)
    assert got["state"] == "resolved" and got["hit"].heading == "Copyright"


def test_a_name_the_registry_here_does_not_know_waits_for_the_registry(env):
    lib = ll.local()
    lib.fetcher.wait(10)                                               # nothing yet: no registry here at all
    assert lib.cite({"in": "nowhere/nothing", "version": "1", "at": "x"}, wait=10)["state"] == "unknown"
    pin = lib.cite({"in": "example/runner", "version": "1", "at": "x"}, wait=10)
    assert pin["state"] == "not-aboard" and "pinned" in pin["why"]
    assert not env.raw_asked()


# ---------------------------------------------------------------------------
# refused: nothing kept
# ---------------------------------------------------------------------------

def test_a_tampered_file_is_refused_and_nothing_of_the_text_is_kept(env):
    (env.root / "example/manual/1.0/files/library/strings.txt").write_text("tampered\n")
    lib = ll.local()
    got = lib.cite(MANUAL, wait=10)
    assert got["state"] == "not-aboard"
    assert "does not match its sha256" in got["why"] and "refused" in got["why"]
    assert tc.resolve_citation(MANUAL, lib)[0] is None                 # a warning, never an error
    assert not (_cache() / "example/manual").exists()
    assert not list(_cache().glob(".fetch-*"))
    assert json.loads((_cache() / lf.FETCHED_RECORD).read_text()) == {}
    st = lf.status(_cache())
    assert st["jobs"]["example/manual/1.0"]["state"] == "failed" and st["cached"] == []
    # asked again at once: not fetched again (the viewer polls), still not aboard
    n = len(env.asked)
    assert lib.cite(MANUAL)["state"] == "not-aboard" and len(env.asked) == n


def test_sums_that_are_not_the_registrys_are_refused(env):
    sums = env.root / "example/sheet/2/SHA256SUMS"
    sums.write_text(sums.read_text() + "0" * 64 + "  files/extra.txt\n")
    got = ll.local().cite(SHEET, wait=10)
    assert got["state"] == "not-aboard" and "SHA256SUMS is not the one the registry names" in got["why"]
    assert not (_cache() / "example/sheet").exists() and not env.raw_asked()


def test_a_path_out_of_the_folder_is_refused(tmp_path):
    for rel in ("files/../x", "x/y", "files/", "files//a", "/files/a", "files/a\\b"):
        assert not lf._safe_rel(rel), rel
    assert lf._safe_rel("files/library/strings.txt")


# ---------------------------------------------------------------------------
# offline
# ---------------------------------------------------------------------------

def test_offline_a_citation_reads_not_aboard_a_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "1")
    monkeypatch.setenv("ENOUGH_LIBRARY_URL", f"http://127.0.0.1:{_free_port()}/library")
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(tmp_path / "no-shelf"))
    monkeypatch.setenv("ENOUGH_LANGUAGES_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(tmp_path / "ui.json"))
    _fresh_launch(monkeypatch)
    lib = ll.local()
    got = lib.cite(MANUAL, wait=10)
    assert got["state"] == "not-aboard" and "could not be fetched" in got["why"]
    ok, why = tc.resolve_citation(MANUAL, lib)
    assert ok is None and "could not be fetched" in why
    assert not (_cache() / "library.json").exists()
    lf.reset_for_tests()


def test_offline_the_texts_already_cached_still_resolve(env, monkeypatch):
    assert ll.local().cite(MANUAL, wait=10)["state"] == "resolved"
    _fresh_launch(monkeypatch)
    monkeypatch.setenv("ENOUGH_LIBRARY_URL", f"http://127.0.0.1:{_free_port()}/library")
    lib = ll.local()
    lib.fetcher.wait(10)                                                # the launch's registry check fails, quietly
    assert lib.cite(MANUAL)["state"] == "resolved"
    assert lib.cite(SHEET, wait=10)["state"] == "not-aboard"
    _fresh_launch(monkeypatch)
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "0")                        # the fetch off: the cache still reads
    lib = ll.local()
    assert lib is not None and lib.fetcher is None
    assert lib.cite(MANUAL)["state"] == "resolved"
    assert lib.cite(SHEET)["state"] == "not-aboard"


# ---------------------------------------------------------------------------
# the cache reused, and kept current
# ---------------------------------------------------------------------------

def test_the_cache_is_reused_the_next_launch(env, monkeypatch):
    assert ll.local().cite(MANUAL, wait=10)["state"] == "resolved"
    raw = len(env.raw_asked())
    _fresh_launch(monkeypatch)
    env.asked.clear()
    lib = ll.local()
    assert lib.cite(MANUAL)["state"] == "resolved"                      # at once: no fetch of the text
    lib.fetcher.wait(10)
    assert env.asked == ["/library/library.json"] and raw == 4         # the launch's one registry check
    _fresh_launch(monkeypatch)
    env.asked.clear()
    lib = ll.local()
    lib.fetcher.wait(10)
    assert lib.cite(MANUAL)["state"] == "resolved" and not env.raw_asked()


def test_a_text_the_site_no_longer_keeps_as_it_was_is_dropped_and_fetched_again(env, monkeypatch):
    assert ll.local().cite(MANUAL, wait=10)["state"] == "resolved"
    reg = json.loads((env.root / "library.json").read_text())
    for e in reg["texts"]:
        if e["text"] == "manual":
            e["digest"] = "sha256:" + "0" * 64                         # republished: another SHA256SUMS
    (env.root / "library.json").write_text(json.dumps(reg, indent=2))
    _fresh_launch(monkeypatch)
    lib = ll.local()
    lib.fetcher.wait(10)
    assert not (_cache() / "example/manual").exists()
    assert json.loads((_cache() / lf.FETCHED_RECORD).read_text()) == {}
    got = lib.cite(MANUAL, wait=10)                                     # fetched again: its sums no longer agree
    assert got["state"] == "not-aboard" and "SHA256SUMS is not the one the registry names" in got["why"]


def test_a_synced_shelf_is_read_and_nothing_is_fetched_into_it(env, monkeypatch, tmp_path):
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(SHELF))
    lib = ll.local()
    assert lib.root == SHELF and lib.fetcher is None
    assert lib.cite(MANUAL)["state"] == "resolved" and env.asked == []


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------

@pytest.fixture
def client(env, tmp_path):
    from fastapi.testclient import TestClient

    from enough import skeleton
    from enough.server import create_app
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    return TestClient(create_app(proj, "http://127.0.0.1:9", supervise=False, home=True))


def test_the_routes_say_fetching_then_resolve_and_status_reports_the_cache(client, env):
    q = {**MANUAL, "wait": 0}
    r = client.get("/api/library/section", params=q).json()
    assert r["state"] == "fetching" and r["section"] is None
    ll.local().fetcher.wait(10)
    r = client.get("/api/library/section", params=q).json()
    assert r["state"] == "resolved" and r["section"]["id"] == "S:section/text.count"
    assert r["text"]["here"] is True and r["text"]["copy"] == ll.COPY_LINE
    v = client.get("/api/library/volume", params={"shelf": "example", "text": "sheet", "version": "2", "wait": 0})
    assert v.status_code == 202 and v.json()["state"] == "fetching"
    v = client.get("/api/library/volume", params={"shelf": "example", "text": "sheet", "version": "2", "wait": 10})
    assert v.status_code == 200 and v.json()["nodes"][0]["id"] == "S:section/notice"
    st = client.get("/api/library/status").json()
    assert st["present"] is True and st["source"] == str(_cache())
    assert {(t["text"], t["here"]) for t in st["texts"]} == {("manual", True), ("runner", False), ("sheet", True),
                                                             ("memo", False)}
    f = st["fetch"]
    assert f["allowed"] is True and f["url"] == env.url and f["registry"] is True
    assert [c["key"] for c in f["cached"]] == ["example/manual/1.0", "example/sheet/2"]
    assert f["jobs"]["example/sheet/2"]["state"] == "done"
    assert client.get("/api/library/volume", params={"shelf": "example", "text": "runner", "version": "1",
                                                     "wait": 5}).status_code == 404


def test_offline_the_routes_say_not_aboard(client, env, monkeypatch):
    env.close()
    r = client.get("/api/library/section", params={**MANUAL, "wait": 10}).json()
    assert r["state"] == "not-aboard" and "could not be fetched" in r["why"]
    v = client.get("/api/library/volume", params={"shelf": "example", "text": "manual", "version": "1.0", "wait": 5})
    assert v.status_code == 404 and v.json()["state"] == "not-aboard"
    st = client.get("/api/library/status").json()
    assert st["present"] is False and st["fetch"]["jobs"]["library.json"]["state"] == "failed"


# ---------------------------------------------------------------------------
# against cosmoes-site's own app, when a checkout with the registry route is here
# ---------------------------------------------------------------------------

def _site_app():
    for root in [os.environ.get("COSMOES_SITE")] + [str(p / "cosmoes-site") for p in REPO.parents]:
        if root and (Path(root) / "cosmoes" / "app.py").is_file() and \
                "/library/library.json" in (Path(root) / "cosmoes" / "app.py").read_text():
            return Path(root)
    return None


def test_against_cosmoes_sites_own_routes(tmp_path, monkeypatch):
    root = _site_app()
    if root is None:
        pytest.skip("no cosmoes-site checkout with /library/library.json here (COSMOES_SITE names one)")
    pytest.importorskip("jinja2")
    monkeypatch.syspath_prepend(str(root))
    for m in [m for m in sys.modules if m == "cosmoes" or m.startswith("cosmoes.")]:
        monkeypatch.delitem(sys.modules, m)
    from fastapi.testclient import TestClient
    from cosmoes.app import create_app as site_app                    # noqa: E402
    lib_copy = shutil.copytree(SHELF, tmp_path / "site-library")
    site = TestClient(site_app(library_folder=lib_copy), base_url="https://cosmoes.org")

    class Opener:
        def open(self, req, timeout=None):
            path = urllib.parse.urlsplit(req.full_url).path
            r = site.get(path, headers={"host": "cosmoes.org"})
            if r.status_code != 200:
                raise urllib.error.HTTPError(req.full_url, r.status_code, "", {}, None)

            class Resp:
                headers = {"Content-Length": str(len(r.content))}

                def read(self, n=-1):
                    return r.content

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            return Resp()

    f = lf.Fetcher(tmp_path / "cache", "https://cosmoes.org/library", opener=Opener())
    f.fetch_registry()
    for e in [e for e in json.loads((SHELF / "library.json").read_text())["texts"] if e["aboard"]]:
        f.fetch_text(e)
        assert _tree(li.text_dir(tmp_path / "cache", e)) == _tree(li.text_dir(SHELF, e))
    lib = ll.Library(tmp_path / "cache", tmp_path / "idx.sqlite")
    assert lib.cite(MANUAL)["state"] == "resolved" and lib.cite(SHEET)["state"] == "resolved"
