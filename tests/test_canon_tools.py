"""The readvisor's MacroCOSM tools (0.4.3, P6): `cosm_read`, `cosm_lint`, `emf_derive`, `atem`.

Every tool runs through `tools.execute` with a real `ToolCall` parsed from tool-call text, the documented
examples in `prompt.CANON_TOOL_INSTRUCTIONS` included. Rules mode is the default (the tools' model seam is
unconfigured, as in any test); model mode stands in `llm.reachable` and `llm.complete`. The refusals are
shared with the derivation routes (`canon_tools.text_target`), and the last tests check the routes still
refuse identically. conftest has moved `HOME` and every `ENOUGH_*` seam into tmp_path; `broker.CONFIG_PATH`
(resolved at import) and `models.LIVE_STATE` (read once at import) are re-pointed here by hand.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import broker, canon, canon_jobs, canon_tools as CT, llm, macrocosm, models, prompt, skeleton
from enough import tools as T
from tests.test_canon_derive import ATEM_YAML, good

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"
HELLO = "# Hello\n\nA short note about the lane by the orchard. It has two sentences.\n"
LONG = "# Long\n\n" + ("The orchard keeps a record of every tree it plants. " * 600) + "\n"
MID = "# Mid\n\n" + ("The orchard keeps a record of every tree it plants. " * 180) + "\n"


@pytest.fixture(autouse=True)
def unconfigured():
    """Every test starts (and ends) with the tools' seam empty: rules mode, no job table."""
    CT.configure()
    yield
    CT.configure()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(os.environ["HOME"])
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "store"))
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", proj / "rain.cosm")
    shutil.copyfile(FIX / "bad" / "ref-unresolved.cosm", proj / "bad.cosm")
    shutil.copytree(FIX / "holotypes" / "meadow", proj / "meadow")
    shutil.copytree(FIX / "cosm02" / "meadow", proj / "tree")
    (proj / "meadow" / "NOTES.md").write_text("A text inside a Holotype.\n", encoding="utf-8")
    (proj / "hello.md").write_text(HELLO, encoding="utf-8")
    (proj / "long.md").write_text(LONG, encoding="utf-8")
    (proj / "mid.md").write_text(MID, encoding="utf-8")
    (proj / "empty.md").write_text("  \n", encoding="utf-8")
    (proj / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (proj / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (proj / "report.pdf").write_bytes(b"%PDF-1.4\n\x00\x01\x02")
    (proj / "other.md").write_text("Some text.\n", encoding="utf-8")
    (proj / "other.md.cosm").write_text("oes: canon/1\nid: canon/x\nname: x\nnodes: []\n", encoding="utf-8")
    (proj / "odd.cosm").write_text("oes: nonesuch/9\nid: x\nnodes: []\n", encoding="utf-8")
    (proj / "folder").mkdir()
    skeleton.ensure_skeleton(proj)
    canon.project_catalog(proj)                        # what a server writes at startup
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(canon.root()).startswith(str(tmp_path))
    assert str(broker.CONFIG_PATH).startswith(str(tmp_path))
    assert str(models.LIVE_STATE).startswith(str(tmp_path))
    canon.create_volume("lib")
    (canon.volume_dir("lib") / "guide.md").write_text("# The guide\n\nMeadow closes the books overnight.\n",
                                                      encoding="utf-8")
    return proj


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list:
    """A model that answers: the seam configured, `llm.reachable` true, `llm.complete` returning canned EMF (a
    claim whose bad stance the repair turn fixes) and the atem."""
    calls: list = []

    def complete(messages, **kw):
        calls.append((messages, kw))
        if messages[0]["content"].startswith("You write the atem"):
            return ATEM_YAML, {"model": "fake-model", "route": "local"}
        return good("certain" if len(messages) == 2 else "axiom"), {"model": "fake-model", "route": "local"}

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", complete)
    CT.configure(llm_url="http://127.0.0.1:9")
    return calls


def run(project: Path, text: str) -> T.ToolResult:
    calls = T.parse_tool_calls(text)
    assert len(calls) == 1, text
    return T.execute(project, calls[0])


def tool(name: str, **tags: str) -> str:
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in tags.items())
    return f'<tool name="{name}">{inner}</tool>'


def twin_data(path: Path) -> dict:
    return macrocosm.yaml_load(path.read_text(encoding="utf-8"))


def lint_errors(path: Path) -> list[str]:
    vol = macrocosm.load_volume(path)
    assert vol.refused is None, vol.refused
    return [str(p) for p in macrocosm.lint(vol).errors]


def set_toggle(key: str, value: bool) -> None:
    cfg = broker.load_config()
    cfg[key] = value
    broker.save_config(cfg)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def test_registered_traced_and_the_prefixes_match_the_server():
    from enough import server
    for name in CT.TOOL_NAMES:
        assert T._DISPATCH[name] is CT._RUNNERS[name]
        assert T._TRACE_TOGGLE[name] == "trace_log_enabled"
    assert CT.STORE_PREFIXES == server.STORE_PREFIXES
    assert CT.SIDE_EFFECT == canon_jobs.EVENT


def test_every_documented_example_runs(project: Path):
    """The block's six examples, parsed exactly as the model would write them, run in order on a project that
    holds what they name: the guide, decompile notes.md, lint the twin, write its atem, read an item of the
    Holotype, and look a word up in the spec (0.4.4; its volume is built into the tmp docs root)."""
    examples = re.findall(r'<tool name="[a-z_]+">.*?</tool>', prompt.CANON_TOOL_INSTRUCTIONS, re.DOTALL)
    assert [T.parse_tool_calls(e)[0].name for e in examples] == [
        "cosm_read", "cosm_lint", "emf_derive", "atem", "cosm_guide", "doc_lookup"]
    read, lint, derive, atem, guide, lookup = examples
    r = run(project, lookup)
    # 0.4.4 (D3's spec pass): the spec defines `stance` as a term; its answer still carries the closed list's words.
    assert r.ok and r.body.startswith("stance  [T:term/stance") and "R:list/emf.stance" in r.body, r.body
    assert all(f"- {w} — " in r.body for w in ("axiom", "observed", "deduced", "opinion", "assumed", "hearsay"))
    r = run(project, guide)
    assert r.ok and r.body.startswith("# macrocosm-oes"), r.body[:80]
    r = run(project, derive)
    assert r.ok, r.body
    assert (project / "notes.md.cosm").is_file()
    r = run(project, lint)
    assert r.ok and "0 errors" in r.body, r.body
    r = run(project, atem)
    assert r.ok and r.body.startswith("line: "), r.body
    r = run(project, read)
    assert r.ok and "R:claim/books-by-7am" in r.body and "fields:" in r.body, r.body


def test_a_tool_turn_announces_the_write_as_a_canon_event(project: Path, monkeypatch: pytest.MonkeyPatch):
    """Through the server's tool step: the chip events, then the `canon` event the UI's job handler repaints on."""
    import asyncio
    from enough import server
    seen: list = []

    async def spy(self, event, data):
        seen.append((event, json.loads(json.dumps(data))))

    monkeypatch.setattr(server.Session, "emit", spy)
    session = server.Session(project_dir=project, llm_url="http://127.0.0.1:9")
    call = T.parse_tool_calls(tool("emf_derive", path="hello.md"))[0]
    asyncio.run(server._handle_tool(session, call, []))
    assert [e for e, _d in seen] == ["tool", "tool", "canon"]
    assert seen[1][1]["status"] == "ok"
    assert seen[2][1]["state"] == "done" and seen[2][1]["result"]["twin_path"] == "hello.md.cosm"
    assert session.history[-1]["content"].startswith('<tool_result name="emf_derive"')


def test_the_server_configures_the_seam_in_project_mode_only(project: Path):
    from enough.server import create_app
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    assert CT._llm_url == "http://127.0.0.1:9"
    assert CT._jobs is app.state.canon_jobs
    CT.configure()
    create_app(project, "http://127.0.0.1:9", supervise=False, home=True)
    assert CT._llm_url is None and CT._jobs is None


def test_the_guide_is_the_skill_body_and_the_skill_ships_off(project: Path):
    """`cosm_guide` is how the guide reaches a readvisor whose `macrocosm-oes` skill is off — and it is off by
    default, like every shipped skill, so its body never rides in an ordinary turn."""
    disabled = (project / "rness" / "skills" / ".disabled").read_text(encoding="utf-8").split()
    assert CT.SKILL_NAME in disabled
    r = run(project, tool("cosm_guide"))
    assert r.ok and not r.side_effects
    body = r.body
    assert body.startswith("# macrocosm-oes") and "description:" not in body
    assert "enough-tooltip-text" not in body and not body.rstrip().endswith("---")
    for words in ("## The six stances", "## The atem", "Decompile only when asked", "People are never in files",
                  "focus", "push", "pull", "docs/MACROCOSM_OES.md", "© 2026 Graham Smith"):
        assert words in body, words
    skill = (REPO / "defaults" / "skills" / CT.SKILL_NAME / "SKILL.md").read_text(encoding="utf-8")
    assert body in skill


# ---------------------------------------------------------------------------
# cosm_read
# ---------------------------------------------------------------------------

def test_read_a_holotype(project: Path):
    r = run(project, tool("cosm_read", path="meadow"))
    assert r.ok, r.body
    assert "a comprise/1 volume" in r.body
    assert "declared: comprise/1 (`oes: comprise/1`)" in r.body
    assert "36 items · 0 open questions · 0 errors" in r.body
    assert "R:claim/books-by-7am" in r.body
    assert "more)" not in r.body                       # meadow fits whole


def test_read_a_big_holotype_is_capped(project: Path):
    shutil.copytree(FIX / "holotypes" / "mozilla", project / "mozilla")
    r = run(project, tool("cosm_read", path="mozilla"))
    assert r.ok, r.body
    assert "524 items · 82 open questions" in r.body
    tree = r.body.split("\n\n")[1]
    assert len(tree.splitlines()) <= CT.TREE_MAX_LINES
    assert len(tree) <= CT.TREE_MAX_CHARS
    assert re.search(r"… \(\d+ more\)", tree), tree
    assert "cut to fit a chat turn" in r.body
    # Every "(N more)" counts what it hides: the shown items plus the hidden ones are the whole volume.
    shown = sum(1 for ln in tree.splitlines() if re.search(r"\[[A-Z]:[^\]]+ · ", ln))
    hidden = sum(int(n) for n in re.findall(r"… \((\d+) more\)", tree))
    assert shown + hidden >= 524


def test_read_an_item_a_field_and_a_module(project: Path):
    r = run(project, tool("cosm_read", path="meadow", item="R:claim/books-by-7am"))
    assert r.ok and "path: meadow/R/claim/books-by-7am" in r.body and "summary:" in r.body, r.body
    r = run(project, tool("cosm_read", path="meadow", item="meadow/R/claim/books-by-7am#summary"))
    assert r.ok and "(a field of" in r.body, r.body
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "full.cosm")
    r = run(project, tool("cosm_read", path="full.cosm", item="P"))
    assert r.ok and re.search(r"P: \d+ items", r.body), r.body
    r = run(project, tool("cosm_read", path="meadow", item="Z:nothing/here"))
    assert not r.ok and "there is no item" in r.body


def test_read_an_emf_twin_a_legacy_tree_and_a_text_through_its_twin(project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "notes.md.cosm")
    r = run(project, tool("cosm_read", path="notes.md.cosm"))
    assert r.ok and "a emf/1 volume" in r.body and "declared: emf/1 (`oes: emf/1`)" in r.body, r.body
    assert "P:claim/" in r.body
    r = run(project, tool("cosm_read", path="notes.md"))
    assert r.ok and "(reading notes.md.cosm, the EMF twin of notes.md)" in r.body, r.body
    r = run(project, tool("cosm_read", path="tree"))
    assert r.ok and "legacy `cosm: 0.2`, read as cosm/0" in r.body, r.body
    r = run(project, tool("cosm_read", path="hello.md"))
    assert not r.ok and "no EMF twin yet" in r.body


def test_read_the_canon_store_and_the_project_catalog(project: Path):
    set_toggle("canon_enabled", False)                 # reads never answer to the toggle
    r = run(project, tool("cosm_read", path="canon:lib"))
    assert r.ok and "a canon/1 volume" in r.body and "guide.md" in r.body, r.body
    (project / canon.PROJECT_CATALOG).unlink(missing_ok=True)
    r = run(project, tool("cosm_read", path="rness/canon.cosm"))
    assert r.ok and (project / canon.PROJECT_CATALOG).is_file(), r.body


@pytest.mark.parametrize("tags,words", [
    ({}, "needs a <path>"),
    ({"path": "nope.cosm"}, "no such file or folder"),
    ({"path": "../outside.cosm"}, "escapes project directory"),
    ({"path": "canon:"}, "name a volume"),
    ({"path": "canon:../x"}, "invalid path"),
    ({"path": "data.csv"}, "not a .cosm file or a volume folder"),
    ({"path": "odd.cosm"}, "refused by the reader"),
])
def test_read_refusals(project: Path, tags: dict, words: str):
    r = run(project, tool("cosm_read", **tags))
    assert not r.ok and words in r.body, r.body


# ---------------------------------------------------------------------------
# cosm_lint
# ---------------------------------------------------------------------------

def test_lint_a_bad_volume(project: Path):
    r = run(project, tool("cosm_lint", path="bad.cosm"))
    assert r.ok, r.body
    assert "bad.cosm — emf/1, 1 items: 1 errors · 0 warnings · 0 notes · 0 open questions" in r.body
    assert "errors:\n- ref-unresolved K:concept/x (bad.cosm): defined-by -> L:term/missing does not exist" in r.body
    assert "not run" not in r.body                     # emf lists nothing the reader lacks


def test_lint_a_holotype_names_what_comprise_keeps_in_one_line(project: Path):
    shutil.copytree(FIX / "holotypes" / "khan-academy", project / "khan")
    r = run(project, tool("cosm_lint", path="khan"))
    assert r.ok and "0 errors" in r.body and "56 open questions" in r.body, r.body
    assert "open questions (pending" in r.body and "… (31 more)" in r.body
    not_run = [ln for ln in r.body.splitlines() if ln.startswith("not run:")]
    assert len(not_run) == 1 and "58 checks the comprise MiniCOSM keeps to its own tools" in not_run[0]
    assert "(46 more)" in not_run[0]


def test_lint_a_clean_twin_and_a_refused_file(project: Path):
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", project / "full.cosm")
    r = run(project, tool("cosm_lint", path="full.cosm"))
    assert r.ok and "clean: every check that ran passed." in r.body, r.body
    r = run(project, tool("cosm_lint", path="odd.cosm"))
    assert not r.ok and "nothing was checked" in r.body


# ---------------------------------------------------------------------------
# emf_derive
# ---------------------------------------------------------------------------

def test_derive_in_rules_mode(project: Path):
    ui = Path(os.environ["ENOUGH_UI_CONFIG"])
    ui.parent.mkdir(parents=True, exist_ok=True)
    ui.write_text(json.dumps({"chief_readvisor_name": "Mo"}), encoding="utf-8")
    r = run(project, tool("emf_derive", path="notes.md"))
    assert r.ok, r.body
    twin = project / "notes.md.cosm"
    data = twin_data(twin)
    assert data["oes"] == "emf/1" and data["derived"]["mode"] == "rules"
    assert data["derived"]["by"] == "Mo" and data["derived"]["completeness"] == "full"
    assert lint_errors(twin) == []
    assert "mode: rules — a scaffold, no model read it" in r.body and "by Mo" in r.body
    assert "items: L Lexicon" in r.body and "atem: " in r.body
    snap = r.side_effects[CT.SIDE_EFFECT]
    assert snap["kind"] == "emf" and snap["state"] == "done" and snap["by"] == "Mo"
    assert snap["result"]["twin_path"] == "notes.md.cosm" and snap["result"]["state"] == "fresh"
    assert set(snap) >= {"id", "path", "phase", "chunk", "chunks", "message", "mode", "error",
                         "started_at", "finished_at"}
    # The project catalog now lists the twin on its text.
    assert "notes.md.cosm" in (project / canon.PROJECT_CATALOG).read_text(encoding="utf-8")


def test_derive_in_model_mode(project: Path, model: list):
    r = run(project, tool("emf_derive", path="notes.md"))
    assert r.ok, r.body
    data = twin_data(project / "notes.md.cosm")
    assert data["derived"]["mode"] == "model" and data["derived"]["model"] == "fake-model"
    assert data["derived"]["by"] == prompt.chief_name() == "Ed"
    assert any(n["id"].startswith("P:claim/") for n in data["nodes"])
    assert lint_errors(project / "notes.md.cosm") == []
    assert "mode: model (fake-model)" in r.body
    assert all(kw.get("llm_url") == "http://127.0.0.1:9" for _m, kw in model)
    assert r.side_effects[CT.SIDE_EFFECT]["mode"] == "model"


def test_already_fresh_force_and_the_upgrade_to_a_model(project: Path, monkeypatch: pytest.MonkeyPatch):
    assert run(project, tool("emf_derive", path="hello.md")).ok
    r = run(project, tool("emf_derive", path="hello.md"))
    assert r.ok and r.body.startswith("already fresh") and not r.side_effects, r.body
    r = run(project, tool("emf_derive", path="hello.md", force="yes"))
    assert r.ok and r.body.startswith("ok — wrote"), r.body
    # A scaffold is not fresh enough once a model answers: the tool reads it properly.
    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", lambda m, **kw: (ATEM_YAML if m[0]["content"].startswith(
        "You write the atem") else good(), {"model": "fake-model"}))
    CT.configure(llm_url="http://127.0.0.1:9")
    r = run(project, tool("emf_derive", path="hello.md"))
    assert r.ok and "mode: model" in r.body, r.body


def test_a_model_that_dies_writes_nothing(project: Path, monkeypatch: pytest.MonkeyPatch):
    def boom(messages, **kw):
        raise llm.LLMUnavailable("the gate closed")

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", boom)
    CT.configure(llm_url="http://127.0.0.1:9")
    r = run(project, tool("emf_derive", path="notes.md"))
    assert not r.ok and "the model became unavailable (the gate closed); nothing was written" in r.body, r.body
    assert not (project / "notes.md.cosm").exists()
    r = run(project, tool("atem", path="notes.md"))
    assert not r.ok and "nothing was written" in r.body
    assert not (project / "notes.md.cosm").exists()


def test_a_model_reads_only_short_texts_in_a_chat_turn(project: Path, model: list):
    """Over EMF_MODEL_MAX the twin is the rules scaffold even with a model answering, and the result says the full
    pass belongs in the reader; at or under it the model reads. `atem` keeps the model up to TEXT_MAX."""
    assert CT.EMF_MODEL_MAX < len(MID) <= CT.TEXT_MAX
    r = run(project, tool("emf_derive", path="mid.md"))
    assert r.ok, r.body
    assert model == [], "no model call for a long text inside a chat turn"
    data = twin_data(project / "mid.md.cosm")
    assert data["derived"]["mode"] == "rules" and "model" not in data["derived"]
    assert f"{len(MID):,} characters: {CT.LONG_FOR_A_TURN}" in r.body
    assert "a full model pass on a text this long belongs in the reader's decompile, which runs in the " \
           "background" in r.body
    assert r.side_effects[CT.SIDE_EFFECT]["mode"] == "rules"
    # A rules twin of a long text is as fresh as it can get here.
    r = run(project, tool("emf_derive", path="mid.md"))
    assert r.ok and r.body.startswith("already fresh") and model == []
    # The atem of the same text is the model's.
    r = run(project, tool("atem", path="mid.md"))
    assert r.ok and "mode: model (fake-model)" in r.body and len(model) == 1, r.body
    # ...and a short text is the model's for both.
    assert len((project / "notes.md").read_text(encoding="utf-8")) <= CT.EMF_MODEL_MAX
    r = run(project, tool("emf_derive", path="notes.md"))
    assert r.ok and "mode: model (fake-model)" in r.body


def test_the_length_refusal(project: Path):
    assert len(LONG) > CT.TEXT_MAX
    r = run(project, tool("emf_derive", path="long.md"))
    assert not r.ok and "that's long for a chat turn — use decompile in the reader instead" in r.body
    r = run(project, tool("atem", path="long.md"))
    assert not r.ok and "that's long for a chat turn — use atem in the reader instead" in r.body
    r = run(project, tool("atem", text=LONG))
    assert not r.ok and "long for a chat turn" in r.body
    assert not (project / "long.md.cosm").exists()


def test_an_absolute_path_inside_the_project_is_taken(project: Path):
    r = run(project, tool("emf_derive", path=str(project / "hello.md")))
    assert r.ok and (project / "hello.md.cosm").is_file(), r.body
    # Anything else stays inside the project, as the routes read it: the leading slash is dropped.
    r = run(project, tool("emf_derive", path="/etc/hosts"))
    assert not r.ok and "no such file: etc/hosts" in r.body


def test_a_job_holding_the_file_wins(project: Path):
    jobs = canon_jobs.CanonJobs()
    CT.configure(jobs=jobs)
    key = str(CT.text_target(project, "notes.md")["key"])
    with jobs.holding(key, "notes.md"):
        r = run(project, tool("emf_derive", path="notes.md"))
        assert not r.ok and "is being derived right now" in r.body, r.body
        r = run(project, tool("atem", path="notes.md"))
        assert not r.ok and "is being derived right now" in r.body
    assert not (project / "notes.md.cosm").exists()
    assert run(project, tool("emf_derive", path="notes.md")).ok


# ---------------------------------------------------------------------------
# atem
# ---------------------------------------------------------------------------

def test_a_file_atem_makes_a_minimal_twin(project: Path):
    r = run(project, tool("atem", path="hello.md"))
    assert r.ok, r.body
    lines = r.body.splitlines()
    assert [ln.split(":")[0] for ln in lines[:4]] == ["line", "focus", "push", "pull"]
    assert "(open: a model has not read this passage)" in lines[2]
    assert "a new minimal twin (completeness: atem" in r.body and "by Ed" in r.body
    data = twin_data(project / "hello.md.cosm")
    assert data["derived"]["completeness"] == "atem" and data["derived"]["by"] == "Ed" and data["nodes"] == []
    snap = r.side_effects[CT.SIDE_EFFECT]
    assert snap["kind"] == "atem" and snap["result"]["written"] is True
    # A second atem keeps a full twin's items and changes only its atem: block.
    assert run(project, tool("emf_derive", path="notes.md")).ok
    before = twin_data(project / "notes.md.cosm")
    r = run(project, tool("atem", path="notes.md"))
    assert r.ok and "the twin's items are kept" in r.body
    after = twin_data(project / "notes.md.cosm")
    assert after["nodes"] == before["nodes"] and after["derived"] == before["derived"]


def test_an_inline_atem_writes_nothing(project: Path):
    before = sorted(p.name for p in project.iterdir())
    r = run(project, tool("atem", text="The parish should wait until September. The bees need the clover."))
    assert r.ok and r.body.startswith("line: The parish should wait until September."), r.body
    assert "written: nowhere" in r.body and not r.side_effects
    assert sorted(p.name for p in project.iterdir()) == before
    # With a path too, the file is the passage's context and the refusals still apply.
    r = run(project, tool("atem", path="hello.md", text="A short note."))
    assert r.ok and not (project / "hello.md.cosm").exists()
    r = run(project, tool("atem", path="meadow/NOTES.md", text="A short note."))
    assert not r.ok and "Holotype is browsed" in r.body


def test_a_model_atem(project: Path, model: list):
    r = run(project, tool("atem", path="hello.md"))
    assert r.ok and "line: The orchard pressed more juice this year" in r.body, r.body
    assert "stances: axiom 1 · hearsay 1" in r.body and "mode: model (fake-model)" in r.body
    data = twin_data(project / "hello.md.cosm")
    assert data["derived"]["mode"] == "model" and data["atem"]["push"].startswith("Ask the parish")
    r = run(project, tool("atem", text="Some passage to reduce."))
    assert r.ok and "written: nowhere" in r.body


def test_no_text_no_path(project: Path):
    r = run(project, tool("atem"))
    assert not r.ok and "<path>" in r.body and "<text>" in r.body
    r = run(project, tool("emf_derive"))
    assert not r.ok and "needs the text in a <path>" in r.body


# ---------------------------------------------------------------------------
# The Canon store: the broker toggle, and the volume's catalog
# ---------------------------------------------------------------------------

def test_store_writes_answer_to_canon_enabled(project: Path):
    set_toggle("canon_enabled", False)
    for text in (tool("emf_derive", path="canon:lib/guide.md"), tool("atem", path="canon:lib/guide.md"),
                 tool("emf_derive", path="cacheawl:lib/guide.md")):
        r = run(project, text)
        assert not r.ok and r.body == broker.denial_canon_disabled(), r.body
    assert not (canon.volume_dir("lib") / "guide.md.cosm").exists()
    # Reads, project writes and inline atems never ask.
    assert run(project, tool("cosm_read", path="canon:lib")).ok
    assert run(project, tool("atem", text="A passage.")).ok
    assert run(project, tool("emf_derive", path="hello.md")).ok


def test_a_store_write_regenerates_the_volume_catalog(project: Path):
    set_toggle("canon_enabled", True)
    r = run(project, tool("emf_derive", path="canon:lib/guide.md"))
    assert r.ok, r.body
    assert "wrote canon:lib/guide.md.cosm" in r.body
    twin = canon.volume_dir("lib") / "guide.md.cosm"
    data = twin_data(twin)
    assert data["id"] == "emf/guide-md" and data["derived"]["by"] == "Ed"
    vol = macrocosm.load_volume(canon.volume_dir("lib") / canon.CATALOG_NAME)
    guide = next(it for it in vol.items.values() if it.data.get("path") == "guide.md")
    assert guide.data["emf"]["path"] == "guide.md.cosm" and guide.data["emf"]["state"] == "fresh"
    assert r.side_effects[CT.SIDE_EFFECT]["path"] == "canon:lib/guide.md"


# ---------------------------------------------------------------------------
# The refusals the routes share
# ---------------------------------------------------------------------------

REFUSED = [
    ("nope.md", 404, "no such file"),
    ("folder", 400, "is a folder"),
    ("meadow", 400, "Holotype is browsed"),
    ("meadow/NOTES.md", 400, "Holotype is browsed"),
    ("meadow/holotype.cosm", 400, "Holotype is browsed"),
    ("rness/canon.cosm", 400, "kept by enough"),
    ("canon:lib/canon.cosm", 400, "kept by enough"),
    ("canon:lib/.canon.json", 400, "kept by enough"),
    ("rain.cosm", 400, "already enumerated"),
    ("pic.png", 400, "binary"),
    ("report.pdf", 400, "convert it first"),
    ("data.csv", 400, "markdown and plain text"),
    ("empty.md", 400, "empty"),
    ("other.md", 409, "not an EMF twin"),
    ("../outside.md", 400, "invalid path"),
]


@pytest.mark.parametrize("path,status,words", REFUSED)
def test_tools_refuse_what_the_routes_refuse(project: Path, path: str, status: int, words: str):
    set_toggle("canon_enabled", True)
    with pytest.raises(CT.TextTargetError) as e:
        CT.text_target(project, path)
    assert e.value.status == status and words in str(e.value)
    for name in ("emf_derive", "atem"):
        r = run(project, tool(name, path=path))
        assert not r.ok and words in r.body, (name, r.body)
    assert (project / "other.md.cosm").read_text(encoding="utf-8").startswith("oes: canon/1")


def test_the_routes_still_refuse_identically(project: Path):
    """After the refactor the derive route answers every refusal with the shared function's status and words."""
    from enough.server import create_app
    with TestClient(create_app(project, "http://127.0.0.1:9", supervise=False)) as c:
        for path, status, words in REFUSED + [("", 400, "missing path")]:
            try:
                CT.text_target(project, path)
                expected = None
            except CT.TextTargetError as e:
                expected = (e.status, str(e))
            r = c.post("/api/canon/derive", json={"path": path, "what": "emf"})
            assert (r.status_code, r.json()["detail"]) == expected, (path, r.text)
            assert r.status_code == status and words in r.json()["detail"]
            if path:                                   # the atem route says "nothing to make an atem of"
                r = c.post("/api/canon/atem", json={"path": path})
                assert (r.status_code, r.json()["detail"]) == expected, (path, r.text)
        # ...and a text it accepts still derives.
        r = c.post("/api/canon/derive", json={"path": "hello.md", "what": "emf"})
        assert r.status_code == 200, r.text
