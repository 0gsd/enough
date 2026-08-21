"""enough home (docs/home-plan.md §7): the registry, the counters, the
fingerprint short-circuit, the add guards, the handoff, the project mirror,
and the mode gate.

Everything runs against scratch seams — `ENOUGH_PROJECTS_STATE` (autouse in
conftest) plus every other `ENOUGH_*` the app touches — so no test can put a
tmp dir on the developer's real home screen or read their real desktop.json.
No server is ever really asked to exit: the two process-level hooks
(`request_process_exit`, `request_process_exec`) are swapped for recorders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import home
from enough import server as _server
from enough.server import create_app

# The counting fixture. Deliberately awkward: three blank lines in a row, a
# whitespace-only "blank" line, a fenced code block with a blank line *inside*
# it, and trailing whitespace on the last line. The three numbers below are
# what index.html's `updateDocCounters()` produces for this exact string —
# computed by hand from its three lines of JS, not by re-porting them:
#
#   paragraphs 5 — "# Title" / the sentence / "```python\nx = 1" /
#                  "y = 2\n```" / "Last line." (the fence is not understood
#                  by the rules, and that is the point)
#   words     17 — "#", "Title", 5 in the sentence, "```python", "x", "=",
#                  "1", "y", "=", "2", "```", "Last", "line."
#   chars     89 — every character including the newlines and the trailing
#                  three spaces
COUNTER_FIXTURE = (
    "# Title\n"
    "\n"
    "\n"
    "First paragraph, two words more.\n"
    "   \n"
    "```python\n"
    "x = 1\n"
    "\n"
    "y = 2\n"
    "```\n"
    "\n"
    "Last line.   \n"
)
COUNTER_FIXTURE_P = 5
COUNTER_FIXTURE_W = 17
COUNTER_FIXTURE_C = 89


def make_project(root: Path) -> Path:
    """A folder that reads as an enough project without running the real
    skeleton builder (which syncs global skills and is not what's under test
    here)."""
    (root / "rness").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def scratch_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every seam onto tmp_path, including a scratch HOME — `check_addable`
    asks where ~/enough is, and the answer must not be the real one."""
    state = tmp_path / "state"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ENOUGH_PROJECTS_STATE", str(state / "config" / "projects.json"))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(state / "cacheawl"))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(state / "no-infoworld"))
    monkeypatch.setenv("ENOUGH_WIKISINK_CONFIG", str(state / "wikisink.json"))
    monkeypatch.setenv("ENOUGH_UI_CONFIG", str(state / "ui.json"))
    monkeypatch.setenv("ENOUGH_EXTRAS_STATE", str(state / "extras.json"))
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(state / "weights"))
    monkeypatch.delenv("ENOUGH_DESKTOP", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# The counters (§1.4)
# ---------------------------------------------------------------------------

def test_count_text_agrees_with_the_top_bar_rules():
    counts = home.count_text(COUNTER_FIXTURE)
    assert counts == {"p": COUNTER_FIXTURE_P, "w": COUNTER_FIXTURE_W,
                      "c": COUNTER_FIXTURE_C}


def test_count_text_on_nothing():
    assert home.count_text("") == {"p": 0, "w": 0, "c": 0}
    assert home.count_text("\n\n   \n") == {"p": 0, "w": 0, "c": 6}


def test_project_counts_sum_the_visible_markdown(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    (project / "chapter.md").write_text(COUNTER_FIXTURE, encoding="utf-8")
    (project / "notes.markdown").write_text("One two three.\n", encoding="utf-8")
    # Counted: a twin is the user's text even though the tree hides it.
    (project / "memo.docx.md").write_text("Twin words here.\n", encoding="utf-8")
    # Not counted: scaffolding, ignored dirs, dotfiles, non-markdown.
    (project / "rness" / "AGENT.md").write_text("# agent\n\nlots of words\n",
                                                encoding="utf-8")
    (project / "node_modules").mkdir()
    (project / "node_modules" / "readme.md").write_text("noise noise\n", encoding="utf-8")
    (project / ".hidden.md").write_text("secret\n", encoding="utf-8")
    (project / "photo.png").write_bytes(b"\x89PNG")

    counted = {p.name for p, _st in home._counted_files(project)}
    assert counted == {"chapter.md", "notes.markdown", "memo.docx.md"}

    counts = home.counts_of(home._counted_files(project))
    assert counts == {
        "p": COUNTER_FIXTURE_P + 1 + 1,
        "w": COUNTER_FIXTURE_W + 3 + 3,
        "c": COUNTER_FIXTURE_C + 15 + 17,
    }


def test_counting_descends_but_skips_nested_rness(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    (project / "parts").mkdir()
    (project / "parts" / "one.md").write_text("a b\n", encoding="utf-8")
    (project / "parts" / "inner").mkdir()
    make_project(project / "parts" / "inner")
    (project / "parts" / "inner" / "rness" / "AGENT.md").write_text("x\n", encoding="utf-8")
    names = {p.name for p, _st in home._counted_files(project)}
    assert names == {"one.md"}


# ---------------------------------------------------------------------------
# The registry file
# ---------------------------------------------------------------------------

def test_registry_round_trip_and_register_is_idempotent(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    first = home.register(project)
    assert first["path"] == str(project.resolve())
    assert first["last_opened"] is None and first["counts"] is None
    again = home.register(project)
    assert again["created_at"] == first["created_at"]
    assert len(home.read_registry()["projects"]) == 1

    opened = home.touch_opened(project)
    assert opened["last_opened"]
    assert home.entry_for(project)["last_opened"] == opened["last_opened"]


def test_touch_opened_registers_a_project_that_predates_the_registry(scratch_env: Path):
    project = make_project(scratch_env / "old-project")
    assert home.entry_for(project) is None
    home.touch_opened(project)
    entry = home.entry_for(project)
    assert entry is not None and entry["last_opened"]


def test_a_corrupt_registry_reads_as_empty_and_is_not_overwritten(scratch_env: Path):
    path = home.projects_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all", encoding="utf-8")
    assert home.read_registry() == {"schema": 1, "projects": []}
    # Reading never writes: the bytes are still there for a human to look at.
    assert path.read_text(encoding="utf-8") == "{not json at all"
    # A real save is what replaces it.
    home.register(make_project(scratch_env / "p"))
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == 1


def test_unknown_registry_keys_survive_a_save(scratch_env: Path):
    reg = home.read_registry()
    reg["something_new"] = "keep me"
    home.save_registry(reg)
    home.register(make_project(scratch_env / "p"))
    assert home.read_registry()["something_new"] == "keep me"


def test_hide_is_registry_only(scratch_env: Path):
    """Hiding flags the entry — it never removes it, and it never touches
    disk. ("Forget" sounded like deleting rness/; §1.10 chose a hide flag.)"""
    project = make_project(scratch_env / "novel")
    (project / "chapter.md").write_text("words\n", encoding="utf-8")
    home.register(project)
    assert home.set_hidden(project, True) is True
    entry = home.entry_for(project)
    assert entry is not None and entry["hidden"] is True
    # Unhide round-trips.
    assert home.set_hidden(project, False) is True
    assert home.entry_for(project)["hidden"] is False
    # An unregistered path is a no-op False.
    assert home.set_hidden(project.parent / "never-registered", True) is False
    # Nothing on disk moved.
    assert (project / "rness").is_dir() and (project / "chapter.md").is_file()


# ---------------------------------------------------------------------------
# The fingerprint short-circuit (§1.5)
# ---------------------------------------------------------------------------

def test_refresh_recounts_only_when_the_fingerprint_moved(
        scratch_env: Path, monkeypatch: pytest.MonkeyPatch):
    project = make_project(scratch_env / "novel")
    doc = project / "chapter.md"
    doc.write_text("one two\n", encoding="utf-8")
    entry = home.register(project)

    reads: list[int] = []
    real_counts = home.counts_of
    monkeypatch.setattr(home, "counts_of",
                        lambda scanned: (reads.append(len(scanned)), real_counts(scanned))[1])

    assert home.refresh_entry(entry) is True          # never scanned before
    assert entry["counts"] == {"p": 1, "w": 2, "c": 8}
    assert entry["last_edited"]
    assert len(reads) == 1

    assert home.refresh_entry(entry) is False         # nothing moved
    assert len(reads) == 1

    doc.write_text("one two three four\n", encoding="utf-8")
    assert home.refresh_entry(entry) is True          # bytes moved → recount
    assert entry["counts"]["w"] == 4
    assert len(reads) == 2


def test_a_missing_project_keeps_its_last_known_counts(scratch_env: Path):
    project = make_project(scratch_env / "on-a-usb-stick")
    (project / "chapter.md").write_text("one two\n", encoding="utf-8")
    home.register(project)
    rows = home.list_projects()
    assert rows[0]["counts"] == {"p": 1, "w": 2, "c": 8} and rows[0]["missing"] is False

    # The drive goes away (here: the rness/ does).
    for leftover in (project / "rness").iterdir():
        leftover.unlink()
    (project / "rness").rmdir()

    row = home.list_projects()[0]
    assert row["missing"] is True
    assert row["counts"] == {"p": 1, "w": 2, "c": 8}   # last known, not zeroes
    assert row["name"] == "on-a-usb-stick"


def test_list_projects_reads_the_display_name_live(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    home.register(project)
    assert home.list_projects()[0]["name"] == "novel"
    (project / "rness" / "project.json").write_text(
        json.dumps({"name": "The Book", "description": "a memoir"}), encoding="utf-8")
    row = home.list_projects()[0]
    assert row["name"] == "The Book" and row["description"] == "a memoir"


# ---------------------------------------------------------------------------
# Seeding from the shell's MRU (§1.3)
# ---------------------------------------------------------------------------

def test_seeding_takes_real_projects_only_and_runs_once(scratch_env: Path):
    good = make_project(scratch_env / "kept")
    not_a_project = scratch_env / "plain-folder"
    not_a_project.mkdir()
    gone = scratch_env / "deleted"

    desktop = home.desktop_config_path()
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(json.dumps({
        "reopen_last_project": True,
        "known_projects": [str(good), str(not_a_project), str(gone), ""],
    }), encoding="utf-8")

    assert home.seed_from_desktop() == 1
    paths = [e["path"] for e in home.read_registry()["projects"]]
    assert paths == [str(good.resolve())]
    # created_at comes off the rness/ dir, not "now" — and it is a stamp.
    entry = home.entry_for(good)
    assert entry["created_at"].endswith("Z") and len(entry["created_at"]) == 20

    # Once means once: hiding a project the shell still lists must not be
    # undone by re-seeding on the next boot.
    home.set_hidden(good, True)
    assert home.seed_from_desktop() == 0
    assert home.entry_for(good)["hidden"] is True


def test_seeding_survives_a_missing_or_corrupt_desktop_json(scratch_env: Path):
    assert home.seed_from_desktop() == 0
    home.save_registry({"schema": 1, "projects": []})     # clear the seeded flag
    desktop = home.desktop_config_path()
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text("{{{", encoding="utf-8")
    assert home.seed_from_desktop() == 0


# ---------------------------------------------------------------------------
# The add guards (§1.8)
# ---------------------------------------------------------------------------

def test_add_refuses_the_install_dir(scratch_env: Path):
    install = Path.home() / "enough"
    (install / "defaults").mkdir(parents=True)
    with pytest.raises(home.HomeError, match="install directory"):
        home.check_addable(install)
    with pytest.raises(home.HomeError, match="install directory"):
        home.check_addable(install / "defaults")


def test_add_refuses_a_cloud_synced_folder(scratch_env: Path):
    synced = scratch_env / "Dropbox" / "novel"
    synced.mkdir(parents=True)
    with pytest.raises(home.HomeError, match="Dropbox"):
        home.check_addable(synced)


def test_add_refuses_a_folder_that_isnt_there(scratch_env: Path):
    with pytest.raises(home.HomeError, match="no folder at"):
        home.check_addable(scratch_env / "typo")
    a_file = scratch_env / "notes.txt"
    a_file.write_text("hi", encoding="utf-8")
    with pytest.raises(home.HomeError, match="not a folder"):
        home.check_addable(a_file)


def test_add_builds_the_skeleton_and_registers(scratch_env: Path):
    folder = scratch_env / "fresh"
    folder.mkdir()
    row = home.add_project(folder)
    assert row["path"] == str(folder.resolve())
    assert (folder / "rness" / "AGENT.md").is_file()
    assert home.entry_for(folder) is not None
    assert row["counts"] == {"p": 0, "w": 0, "c": 0}


# ---------------------------------------------------------------------------
# The handoff (§1.7)
# ---------------------------------------------------------------------------

def test_handoff_file_write_then_consume(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    assert home.read_handoff() is None
    written = home.write_handoff(project)
    assert written == home.handoff_path()
    assert written.parent == home.projects_state_path().parent
    assert home.read_handoff(consume=False) == project.resolve()
    assert home.read_handoff() == project.resolve()     # …and consumed
    assert not written.exists()
    assert home.read_handoff() is None


def test_exec_argv_shape(scratch_env: Path):
    project = scratch_env / "novel"
    argv = home.exec_argv(project_dir=project, port=3999,
                          llm_url="http://localhost:8080", max_tool_iters=50,
                          supervise=True)
    assert argv[1:3] == ["-m", "enough"]
    assert "--dir" in argv and str(project) in argv
    assert argv[argv.index("--port") + 1] == "3999"
    assert "--no-browser" in argv and "--home" not in argv
    assert "--no-supervise" not in argv

    back_home = home.exec_argv(project_dir=None, port=3999,
                               llm_url="http://127.0.0.1:9999",
                               max_tool_iters=50, supervise=False)
    assert "--home" in back_home and "--dir" not in back_home
    # A QA run's scratch llama-server survives the round trip; so does
    # --no-supervise, which is the user's choice and not home's.
    assert back_home[back_home.index("--llm-url") + 1] == "http://127.0.0.1:9999"
    assert "--no-supervise" in back_home


# ---------------------------------------------------------------------------
# The project mirror (§1.6)
# ---------------------------------------------------------------------------

def test_project_mirror_for_a_planted_tree(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    (project / "chapter.md").write_text("words\n", encoding="utf-8")
    (project / "parts").mkdir()
    (project / "parts" / "one.md").write_text("words\n", encoding="utf-8")
    (project / ".secret").write_text("x", encoding="utf-8")
    (project / "node_modules").mkdir()
    (project / "rness" / "skills").mkdir()
    home.register(project)
    home.list_projects()                    # fills counts, which the meta node shows

    text = home.build_project_mirror(project)
    assert text.startswith("---\n")
    assert "modality: mirror" in text
    assert f"source: project:{project.resolve()}" in text
    assert "flowchart TD" in text
    assert '📁 novel' in text                       # the root node
    assert "📄 chapter.md" in text and "📁 parts" in text and "📄 one.md" in text
    assert "📁 rness" in text                        # the sidebar shows it, so does this
    assert "skills" not in text                      # …but not its hidden children
    assert ".secret" not in text and "node_modules" not in text
    assert "markdown: 2 files" in text


def test_project_mirror_hides_a_converted_twin(scratch_env: Path):
    from enough import convert

    project = make_project(scratch_env / "novel")
    original = project / "memo.docx"
    original.write_bytes(b"PK\x03\x04not-a-real-docx")
    twin = project / "memo.docx.md"
    twin.write_text("# memo\n", encoding="utf-8")
    convert.write_manifest(original, convert.new_manifest(
        original, engine={"name": "pandoc", "version": "3.9"}, assets=None))
    text = home.build_project_mirror(project)
    assert "📄 memo.docx" in text
    assert "memo.docx.md" not in text


# ---------------------------------------------------------------------------
# The API + the mode gate (§3)
# ---------------------------------------------------------------------------

@pytest.fixture
def home_client(scratch_env: Path):
    app = create_app(scratch_env, "http://localhost:9", supervise=False, home=True,
                     port=3999)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def project_client(scratch_env: Path):
    project = make_project(scratch_env / "novel")
    app = create_app(project, "http://localhost:9", supervise=False, port=3999)
    with TestClient(app) as client:
        client._project = project  # type: ignore[attr-defined]
        yield client


@pytest.fixture
def exits(monkeypatch: pytest.MonkeyPatch):
    """Recorders for the two process-level hooks, so a handoff can be
    asserted instead of performed."""
    calls: dict[str, list] = {"exit": [], "exec": []}
    monkeypatch.setattr(_server, "request_process_exit",
                        lambda delay=0.25, code=None: calls["exit"].append(code))
    monkeypatch.setattr(_server, "request_process_exec",
                        lambda argv, delay=0.25: calls["exec"].append(argv))
    return calls


def test_home_mode_serves_the_page_with_its_marker(home_client: TestClient):
    body = home_client.get("/").text
    assert '<body data-mode="home">' in body
    assert "<!-- HISTORY -->" not in body and "<!-- PROJECT_NAME -->" not in body


def test_project_mode_marks_the_page_too(project_client: TestClient):
    assert '<body data-mode="project">' in project_client.get("/").text


def test_the_mode_gate_hides_the_project_routes_from_home(home_client: TestClient):
    for path in ("/api/project", "/api/files", "/api/models", "/api/broker",
                 "/api/cacheawl/tree", "/api/wiki/status"):
        assert home_client.get(path).status_code == 404, path
    assert home_client.post("/api/close-project").status_code == 404
    # …and keeps the handful of things home does serve.
    assert home_client.get("/api/ui-config").status_code == 200
    assert home_client.get("/api/convert/formats").status_code == 200
    assert home_client.get("/api/home/projects").status_code == 200
    # The shell has to be able to quit a home backend gracefully; the route's
    # own ENOUGH_DESKTOP gate is what keeps a browser from using it (404 here
    # because this server isn't a desktop child, not because of the mode).
    assert home_client.post("/api/shutdown").status_code == 404


def test_home_mode_still_lets_the_desktop_shell_quit_it(
        scratch_env: Path, exits: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")
    app = create_app(scratch_env, "http://localhost:9", supervise=False, home=True)
    with TestClient(app) as client:
        assert client.post("/api/shutdown").json() == {"ok": True, "stopping": True}
    assert exits["exit"] == [None]      # a plain stop, not a 42 handoff


def test_the_mode_gate_hides_the_home_routes_from_a_project(project_client: TestClient):
    assert project_client.get("/api/home/projects").status_code == 404
    assert project_client.post("/api/home/open", json={"path": "/x"}).status_code == 404
    # The one exception, and the reason it exists.
    assert project_client.get("/api/project").status_code == 200


def test_projects_endpoint_lists_and_refreshes(home_client: TestClient, scratch_env: Path):
    project = make_project(scratch_env / "novel")
    (project / "chapter.md").write_text(COUNTER_FIXTURE, encoding="utf-8")
    home.register(project)
    payload = home_client.get("/api/home/projects").json()
    assert [p["path"] for p in payload["projects"]] == [str(project.resolve())]
    row = payload["projects"][0]
    assert row["counts"] == {"p": COUNTER_FIXTURE_P, "w": COUNTER_FIXTURE_W,
                             "c": COUNTER_FIXTURE_C}
    assert set(row) == {"path", "name", "description", "created_at", "last_opened",
                        "last_edited", "counts", "missing", "hidden"}


def test_mirror_endpoint_requires_a_registered_project(
        home_client: TestClient, scratch_env: Path):
    project = make_project(scratch_env / "novel")
    (project / "chapter.md").write_text("words\n", encoding="utf-8")
    assert home_client.get("/api/home/mirror",
                           params={"path": str(project)}).status_code == 404
    home.register(project)
    payload = home_client.get("/api/home/mirror", params={"path": str(project)}).json()
    assert payload["name"] == "novel" and "modality: mirror" in payload["text"]


def test_add_endpoint_raises_the_dialog_when_no_path_is_sent(
        home_client: TestClient, scratch_env: Path, monkeypatch: pytest.MonkeyPatch):
    chosen = scratch_env / "picked"
    chosen.mkdir()
    monkeypatch.setattr(home, "choose_folder", lambda *a, **k: str(chosen))
    payload = home_client.post("/api/home/add", json={}).json()
    assert payload["created"] is True
    assert payload["project"]["path"] == str(chosen.resolve())
    assert (chosen / "rness").is_dir()

    # Second time round it's already there — 409, with the entry to open.
    r = home_client.post("/api/home/add", json={"path": str(chosen)})
    assert r.status_code == 409
    assert r.json()["project"]["path"] == str(chosen.resolve())


def test_add_endpoint_reports_a_cancelled_or_unavailable_dialog(
        home_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(home, "choose_folder", lambda *a, **k: None)
    assert home_client.post("/api/home/add", json={}).json() == {"cancelled": True}

    def _no_dialog(*_a, **_k):
        raise home.DialogUnavailable("no osascript here")

    monkeypatch.setattr(home, "choose_folder", _no_dialog)
    payload = home_client.post("/api/home/add", json={}).json()
    assert payload["dialog_unavailable"] is True
    assert payload["detail"] == "no osascript here"


def test_add_endpoint_surfaces_a_guard_refusal(home_client: TestClient, scratch_env: Path):
    synced = scratch_env / "Dropbox" / "novel"
    synced.mkdir(parents=True)
    r = home_client.post("/api/home/add", json={"path": str(synced)})
    assert r.status_code == 400 and "Dropbox" in r.json()["detail"]


def test_open_hands_off_by_exec_on_the_cli(
        home_client: TestClient, scratch_env: Path, exits: dict):
    project = make_project(scratch_env / "novel")
    home.register(project)
    payload = home_client.post("/api/home/open", json={"path": str(project)}).json()
    assert payload == {"handoff": "exec"}
    assert exits["exec"] and "--dir" in exits["exec"][0]
    assert home.entry_for(project)["last_opened"]
    assert home.read_handoff() is None      # no file: nobody is watching for one


def test_open_hands_off_by_exit_42_on_the_desktop(
        home_client: TestClient, scratch_env: Path, exits: dict,
        monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")
    project = make_project(scratch_env / "novel")
    home.register(project)
    payload = home_client.post("/api/home/open", json={"path": str(project)}).json()
    assert payload == {"handoff": "desktop"}
    assert exits["exit"] == [42] and exits["exec"] == []
    assert home.read_handoff() == project.resolve()


def test_open_refuses_an_unregistered_or_vanished_project(
        home_client: TestClient, scratch_env: Path, exits: dict):
    stranger = make_project(scratch_env / "stranger")
    assert home_client.post("/api/home/open",
                            json={"path": str(stranger)}).status_code == 404
    ghost = scratch_env / "ghost"
    ghost.mkdir()
    home.register(ghost)
    r = home_client.post("/api/home/open", json={"path": str(ghost)})
    assert r.status_code == 409 and "isn't there any more" in r.json()["detail"]
    assert home_client.post("/api/home/open", json={}).status_code == 400
    assert exits["exec"] == [] and exits["exit"] == []


def test_hide_endpoint(home_client: TestClient, scratch_env: Path):
    project = make_project(scratch_env / "novel")
    home.register(project)
    payload = home_client.post(
        "/api/home/hide", json={"path": str(project), "hidden": True}).json()
    assert payload == {"path": str(project.resolve()), "hidden": True}
    assert home.entry_for(project)["hidden"] is True
    assert (project / "rness").is_dir()
    # The projects listing still carries the entry, flagged.
    listed = home_client.get("/api/home/projects").json()["projects"]
    assert [p["hidden"] for p in listed if p["path"] == str(project.resolve())] == [True]
    # Unhide; bad bodies refuse.
    assert home_client.post(
        "/api/home/hide", json={"path": str(project), "hidden": False}
    ).json()["hidden"] is False
    assert home_client.post(
        "/api/home/hide", json={"path": str(project)}).status_code == 400
    assert home_client.post(
        "/api/home/hide",
        json={"path": str(scratch_env / "nope"), "hidden": True}).status_code == 404


def test_close_project_goes_back_to_home(project_client: TestClient, exits: dict):
    payload = project_client.post("/api/close-project").json()
    assert payload == {"handoff": "exec"}
    assert "--home" in exits["exec"][0] and "--dir" not in exits["exec"][0]


def test_close_project_on_the_desktop_exits_42_with_no_handoff_file(
        project_client: TestClient, exits: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")
    assert project_client.post("/api/close-project").json() == {"handoff": "desktop"}
    assert exits["exit"] == [42]
    # No file named — "exit 42 and nothing to read" is how the shell is told
    # to come back to home rather than open something.
    assert home.read_handoff() is None


def test_ui_config_round_trips_the_home_view(project_client: TestClient):
    assert "home_view" not in project_client.get("/api/ui-config").json()
    cfg = project_client.post("/api/ui-config", json={"home_view": "list"}).json()
    assert cfg["home_view"] == "list"
    assert project_client.get("/api/ui-config").json()["home_view"] == "list"
    # Two legal values; anything else is dropped, not stored.
    cfg = project_client.post("/api/ui-config", json={"home_view": "carousel"}).json()
    assert cfg["home_view"] == "list"
    # …and it doesn't disturb the theme selection or the convert flag.
    cfg = project_client.post("/api/ui-config",
                              json={"seen_convert_intro": ["pdf"]}).json()
    assert cfg["home_view"] == "list" and cfg["seen_convert_intro"] == ["pdf"]


def test_project_boot_registers_and_stamps(project_client: TestClient):
    project: Path = project_client._project  # type: ignore[attr-defined]
    entry = home.entry_for(project)
    assert entry is not None and entry["last_opened"]


# ---------------------------------------------------------------------------
# The CLI flag
# ---------------------------------------------------------------------------

def test_home_and_dir_are_mutually_exclusive(capsys: pytest.CaptureFixture):
    from enough.__main__ import main, parse_args

    # `--dir` defaults to None precisely so "the user passed it" is knowable.
    assert parse_args([]).dir is None and parse_args([]).home is False
    assert parse_args(["--home"]).home is True
    assert main(["--home", "--dir", "/tmp"]) == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_ensure_skeleton_registers_the_project(scratch_env: Path):
    from enough.skeleton import ensure_skeleton

    folder = scratch_env / "fresh"
    folder.mkdir()
    assert ensure_skeleton(folder) is True
    assert home.entry_for(folder) is not None


def test_mode_marker_lands_on_the_real_body_tag(home_client: TestClient):
    """The / route stamps data-mode via html.replace("<body>", …, 1) — a
    literal "<body>" appearing ANYWHERE earlier in the file (a CSS comment,
    a code sample) would steal the replacement. Wave B hit exactly that.
    Guard the invariant: the served page carries the attribute on an actual
    body element, exactly once."""
    html = home_client.get("/").text
    assert html.count('<body data-mode="home">') == 1
    assert html.count("<body") == 1
