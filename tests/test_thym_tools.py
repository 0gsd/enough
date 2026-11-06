"""The readvisor's Thym tools (0.5.0, wave 2, R1): `thym_check` and `thym_run` (docs/THYM.md 11.3, 12.1, 12.5, 19).

Every call is a real `ToolCall` parsed from tool-call text, the documented examples in
`prompt.CANON_TOOL_INSTRUCTIONS` included, run through `tools.execute` (or the runner itself, where agent-free mode
makes `execute` refuse every tool). No model: rules mode is the default (the MacroCOSM tools' model seam is
unconfigured), and where a model is pretended, `llm.reachable` answers yes and `llm.complete` is a fake that fails
the test if it is ever asked. conftest has moved `HOME` and every `ENOUGH_*` seam into tmp_path (`ENOUGH_THYM_ROOT`
among them), so every run lands in the tmp Thym root; `broker.CONFIG_PATH` and `models.LIVE_STATE` (resolved at
import) are re-pointed here by hand.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from enough import broker, canon, llm, macrocosm, models, prompt, skeleton, thym_host
from enough import canon_tools as CT
from enough import thym_tools as TT
from enough import tools as T
from enough.thym import cli
from enough.thym import trace as TR

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "tests" / "fixtures" / "thym"
MEADOW = REPO / "tests" / "fixtures" / "cosm" / "holotypes" / "meadow"


@pytest.fixture(autouse=True)
def unconfigured():
    """Every test starts (and ends) with the tools' model seam empty: no model answers."""
    CT.configure()
    yield
    CT.configure()


def set_skill(project: Path, on: bool) -> None:
    f = project / "rness" / "skills" / ".disabled"
    names = set(f.read_text(encoding="utf-8").split()) if f.is_file() else set()
    names = names - {TT.SKILL_NAME} if on else names | {TT.SKILL_NAME}
    f.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")


def set_agent_free(on: bool) -> None:
    Path(os.environ["ENOUGH_UI_CONFIG"]).write_text(json.dumps({"agent_free": on}), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(os.environ["HOME"])
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(broker, "CONFIG_PATH", home / "enough" / "config" / "broker.json")
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    shutil.copytree(MEADOW, proj / "meadow")
    (proj / "orchard").mkdir()
    shutil.copyfile(SUITE / "inputs" / "notes.md", proj / "orchard" / "notes.md")
    shutil.copyfile(SUITE / "programs" / "publish-story.thym", proj / "orchard" / "publish-story.thym")
    shutil.copyfile(SUITE / "bad" / "no-counts.thym", proj / "orchard" / "bad.thym")
    story = (SUITE / "programs" / "publish-story.thym").read_text(encoding="utf-8")
    (proj / "a.thym").write_text(story.replace("program publish-story", "program a-story"),   # the block's example
                                 encoding="utf-8")
    for name in ("orchard-notes.thym", "plain-letter.morph.cosm", "on-the-train.context.cosm"):
        src = SUITE / "inputs" / name
        (shutil.copytree if src.is_dir() else shutil.copyfile)(src, proj / "orchard" / name)
    set_skill(proj, True)
    assert str(Path.home()).startswith(str(tmp_path))
    assert str(thym_host.host_root()).startswith(str(tmp_path))
    assert str(canon.root()).startswith(str(tmp_path))
    assert str(broker.CONFIG_PATH).startswith(str(tmp_path))
    assert os.environ["ENOUGH_UI_CONFIG"].startswith(str(tmp_path))
    return proj


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list:
    """A model that answers `reachable` and must never be asked: every pretended model test here is refused, or runs
    a plan with no asking steps, before a completion would be needed."""
    asked: list = []

    def complete(messages, **kw):
        asked.append(messages)
        raise AssertionError("the model was asked")

    monkeypatch.setattr(llm, "reachable", lambda url: (True, "ok"))
    monkeypatch.setattr(llm, "complete", complete)
    CT.configure(llm_url="http://127.0.0.1:9")
    return asked


def call(text: str) -> T.ToolCall:
    calls = T.parse_tool_calls(text)
    assert len(calls) == 1, text
    return calls[0]


def run(project: Path, text: str) -> T.ToolResult:
    return T.execute(project, call(text))


def tool(name: str, **tags: str) -> str:
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in tags.items())
    return f'<tool name="{name}">{inner}</tool>'


def runs_dir() -> Path:
    return thym_host.host_root() / "runs"


# ---------------------------------------------------------------------------
# Wiring and the block
# ---------------------------------------------------------------------------

def test_registered_and_traced_under_the_universal_toggle():
    assert TT.TOOL_NAMES == ("thym_check", "thym_run", "thym_moves")
    for name in [n for n in TT.TOOL_NAMES if TT.documented(n)]:
        assert T._DISPATCH[name] is TT._RUNNERS[name]
        assert T._TRACE_TOGGLE[name] == "trace_log_enabled"
    assert TT.SKILL_NAME == CT.SKILL_NAME


def test_the_block_names_both_tools_says_they_need_the_skill_and_stays_under_the_cap():
    block = prompt.CANON_TOOL_INSTRUCTIONS
    assert len(block) < 1_000, len(block)
    assert '<tool name="thym_check">' in block and '<tool name="thym_run">' in block
    assert "`thym_run` runs one, `thym_moves` lists\nmoves (macrocosm-oes skill on)" in block


def test_the_documented_examples_run(project: Path):
    """The block's two Thym examples, parsed exactly as a model would write them: the check answers ok and the plan's
    line; the run of open-house on the meadow Holotype lands under the seamed Thym root and answers the trace's atem,
    the outputs' paths, the trace's path and where the outputs are."""
    examples = re.findall(r'<tool name="thym_[a-z]+">.*?</tool>', prompt.CANON_TOOL_INSTRUCTIONS, re.DOTALL)
    check, ran = examples
    r = run(project, check)
    assert r.ok and r.body.splitlines()[0] == "ok", r.body
    assert r.body.splitlines()[1].startswith("a-story: 7 nodes, 3 ask a model; largest prompt ")
    r = run(project, ran)
    assert r.ok, r.body
    lines = r.body.splitlines()
    assert lines[0].startswith("ran open-house on meadow in ") and lines[0].endswith("all checks green"), lines[0]
    out = Path(lines[1].split(": ", 1)[1])
    trace = Path(lines[2].split(": ", 1)[1])
    assert lines[1].startswith("i: ") and lines[2].startswith("trace: ") and lines[3] == TT.OUTPUTS_NOTE
    assert out.is_absolute() and out.is_file() and trace.is_file()
    assert runs_dir() in out.parents and runs_dir() in trace.parents
    assert not (project / "meadow" / "i.cosm").exists(), "the tool copies nothing beside the input"
    iso = macrocosm.yaml_load(out.read_text(encoding="utf-8"))
    assert iso["shape"]["employees"] == "none"
    vol = TR.load(trace)
    assert vol["outcome"] == "landed" and vol["environment"]["agent_free"] is False
    snap = r.side_effects[CT.SIDE_EFFECT]
    assert snap["kind"] == TT.JOB_KIND and snap["state"] == "done" and snap["path"] == "meadow"
    assert snap["id"].startswith("rv") and snap["by"]
    assert snap["result"]["run"] == trace.name[: -len(".trace.cosm")] and snap["result"]["trace"] == str(trace)
    assert snap["result"]["outputs"] == {"i": str(out)} and snap["result"]["outcome"] == "landed"
    assert not (Path.home() / "enough" / "thym").exists(), "a run lands under ENOUGH_THYM_ROOT only"


# ---------------------------------------------------------------------------
# The skill gate (the owner's decision: both behind macrocosm-oes)
# ---------------------------------------------------------------------------

def test_with_the_skill_off_both_answer_the_pointer_and_run_nothing(project: Path):
    set_skill(project, False)
    for text in (tool("thym_check", path="a.thym"), tool("thym_run", program="open-house", path="meadow")):
        r = run(project, text)
        assert not r.ok and not r.side_effects
        assert "macrocosm-oes skill, which is off in this project" in r.body and "switch it on" in r.body, r.body
        assert len(r.body.splitlines()) == 1
    assert not runs_dir().exists()


# ---------------------------------------------------------------------------
# thym_check
# ---------------------------------------------------------------------------

def test_check_answers_ok_and_the_plan_line_exactly_as_the_command_line_prints_it(
        project: Path, capsys: pytest.CaptureFixture):
    program = project / "orchard" / "publish-story.thym"
    assert cli.main(["plan", str(program), f"story={project / 'orchard' / 'notes.md'}"]) == 0
    printed = capsys.readouterr().out.strip()
    r = run(project, tool("thym_check", path="orchard/publish-story.thym", inputs="story=orchard/notes.md"))
    assert r.ok, r.body
    assert r.body.splitlines() == ["ok", *printed.splitlines(), "takes story: text; gives out: package"]
    assert printed.splitlines() == ["publish-story: 7 nodes, 3 ask a model; largest prompt 307 tokens, output budget 0 "
                                    "words", "3 model calls, at most 9, on this machine (g40-04)"]
    assert not runs_dir().exists(), "a check writes nothing"


def test_check_without_inputs_plans_on_the_programs_takes_and_says_the_prompt_is_unmeasured(project: Path):
    r = run(project, tool("thym_check", path="read-my-way"))                  # a name reaches a shipped program
    assert r.ok, r.body
    lines = r.body.splitlines()
    assert lines[:4] == ["ok", "read-my-way: 5 nodes, 3 ask a model; largest prompt 0 tokens, output budget 300 words",
                         "3 model calls, at most 9, on this machine (g40-04)",
                         "takes p: package, mine: morph, now: context; gives r: short"]
    assert "not measured" in lines[4] and "<inputs>" in lines[4]


def test_check_refusal_names_the_file_the_line_and_the_check(project: Path):
    r = run(project, tool("thym_check", path="orchard/bad.thym"))
    assert r.ok, "a check's verdict is its answer, as cosm_lint's report is"
    assert r.body.startswith("orchard/bad.thym:9: refused at compile (no-counts): "), r.body
    assert "band it first" in r.body and str(project) not in r.body


def test_check_works_while_agent_free(project: Path):
    """THYM.md 19: a check asks no model. `tools.execute` refuses every tool while agent-free is on (no readvisor
    turn runs then, 0.4.4), so the runner answers when it is called directly."""
    set_agent_free(True)
    c = call(tool("thym_check", path="orchard/publish-story.thym"))
    assert not T.execute(project, c).ok
    r = TT.run_thym_check(project, c)
    assert r.ok and r.body.startswith("ok\npublish-story: 7 nodes"), r.body


def test_check_of_an_unknown_program_lists_the_names(project: Path):
    r = run(project, tool("thym_check", path="nope.thym"))
    assert not r.ok and "no program 'nope.thym'" in r.body
    assert "the programs here: a-story, leaky, publish-story, " in r.body, r.body          # the project's first
    assert "open-house" in r.body and "read-my-way" in r.body, "then the shipped ones (their number grows)"


# ---------------------------------------------------------------------------
# thym_run: refusals at plan time
# ---------------------------------------------------------------------------

def test_run_refuses_a_plan_that_asks_when_no_model_runs(project: Path):
    r = run(project, tool("thym_run", program="publish-story", path="orchard/notes.md"))
    assert not r.ok and not r.side_effects
    assert ("orchard/publish-story.thym:12: refused at plan (rules): 3 steps ask a model on the local route, the "
            "first `let f = derive story` (line 12); no model is running. "
            "Start the model") in r.body, r.body
    assert not runs_dir().exists()


def test_run_refuses_a_plan_that_asks_while_agent_free_and_runs_one_that_does_not(project: Path):
    set_agent_free(True)
    r = TT.run_thym_run(project, call(tool("thym_run", program="publish-story", path="orchard/notes.md")))
    assert not r.ok
    assert ("orchard/publish-story.thym:12: refused at plan (agent-free): 3 steps ask a model on the local route, "
            "the first `let f = derive story` (line 12); agent-free is on. "
            "Turn agent-free off") in r.body, r.body
    assert not runs_dir().exists()
    r = TT.run_thym_run(project, call(tool("thym_run", program="open-house", path="meadow")))
    assert r.ok, r.body
    trace = Path(r.body.splitlines()[2].split(": ", 1)[1])
    assert TR.load(trace)["environment"]["agent_free"] is True


def test_run_of_an_unknown_program_lists_the_names_and_runs_nothing(project: Path):
    r = run(project, tool("thym_run", program="nope", path="orchard/notes.md"))
    assert not r.ok
    assert r.body.startswith("error: no program 'nope': give a program's name or the path of a .thym file; the "
                             "programs here: a-story, leaky, publish-story, "), r.body
    assert "open-house" in r.body and "read-my-way" in r.body
    assert not runs_dir().exists()


def test_preflight_refuses_a_prompt_the_window_cannot_hold_with_the_number(
        project: Path, model: list, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(thym_host, "_read_n_ctx", lambda url: 2048)
    r = run(project, tool("thym_run", program="orchard/publish-story.thym", path="orchard/notes.md"))
    assert not r.ok
    assert ("refused at plan (preflight): the plan's largest prompt is 307 tokens and the model's window is 2,048 "
            "with 2,048 kept free") in r.body, r.body
    assert model == [] and not runs_dir().exists()


def test_a_long_text_is_the_readers_work_not_a_turns(project: Path, model: list):
    (project / "long.md").write_text("# Long\n\n" + "The orchard keeps a record of every tree. " * 700,
                                     encoding="utf-8")
    r = run(project, tool("thym_run", program="publish-story", path="long.md"))
    assert not r.ok and "long.md is " in r.body and "the reader's run-with" in r.body, r.body
    assert model == [] and not runs_dir().exists()


def test_a_model_run_shares_the_turns_model_and_takes_no_rules(
        project: Path, model: list, monkeypatch: pytest.MonkeyPatch):
    seen: list = []
    original = thym_host.runtime_kwargs

    def spy(**kw):
        seen.append(kw)
        return original(**kw)

    monkeypatch.setattr(thym_host, "runtime_kwargs", spy)
    r = run(project, tool("thym_run", program="open-house", path="meadow"))
    assert r.ok, r.body
    (kw,) = seen
    assert kw["rules"] is False and callable(kw["complete"]) and kw["llm_url"] == "http://127.0.0.1:9"
    assert callable(kw["catalog"]), "the surrounding catalog `context of` reads, as the routes pass it"
    assert model == [], "open-house asks no model"
    assert r.side_effects[CT.SIDE_EFFECT]["mode"] == "rules"           # code only: no model step ran


# ---------------------------------------------------------------------------
# thym_run: inputs
# ---------------------------------------------------------------------------

def test_a_missing_input_says_where_further_inputs_go(project: Path):
    r = run(project, tool("thym_run", program="read-my-way", path="orchard/orchard-notes.thym"))
    assert not r.ok
    assert "refused at plan (input): program read-my-way takes mine: morph" in r.body
    assert "further ones in <inputs> lines (name=path)" in r.body, r.body


def test_further_inputs_come_as_inputs_lines(project: Path):
    """With all three inputs given, the plan is made, and its asking steps are what refuses (no model here)."""
    lines = "mine=orchard/plain-letter.morph.cosm\nnow=orchard/on-the-train.context.cosm"
    r = run(project, tool("thym_run", program="read-my-way", path="orchard/orchard-notes.thym", inputs=lines))
    assert not r.ok and ("refused at plan (rules): 3 steps ask a model on the local route, the first `give expand "
                         "(atem f) with f to 300 words` (line 20); no model is running") in r.body, r.body
    r = run(project, tool("thym_run", program="read-my-way", path="orchard/orchard-notes.thym", inputs="mine"))
    assert not r.ok and "an <inputs> line is name=path" in r.body


@pytest.mark.parametrize("path, words", [
    ("../outside.md", "invalid path '../outside.md' for story: give a project-relative path"),
    ("orchard/none.md", "no such file: orchard/none.md (the input story)"),
])
def test_a_bad_input_path_is_refused_in_words(project: Path, path: str, words: str):
    r = run(project, tool("thym_run", program="publish-story", path=path))
    assert not r.ok and words in r.body, r.body
    assert not runs_dir().exists()


def test_a_program_by_path_and_an_input_by_its_full_path(project: Path):
    """A model often echoes a file's full path; one inside the project is read as project-relative."""
    r = run(project, tool("thym_run", program=str(project / "a.thym"), path=str(project / "orchard" / "notes.md")))
    assert not r.ok and r.body.startswith("error: a.thym:12: refused at plan (rules): 3 steps ask a model"), r.body


# ---------------------------------------------------------------------------
# 0.6: the route, the ceiling, folders and several outputs, thym_moves
# ---------------------------------------------------------------------------

def gate(monkeypatch: pytest.MonkeyPatch, open_: bool) -> list:
    from enough import cloud
    asked: list = []

    def status() -> dict:
        asked.append(1)
        return {"open": open_, "reason": None if open_ else "'local models only' is on in the broker",
                "denial": None, "model_id": "vendor/large-model" if open_ else None}
    monkeypatch.setattr(cloud, "gate_status", status)
    monkeypatch.setattr(cloud, "chat_completion", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("asked")))
    return asked


def test_check_on_the_cloud_shows_the_route_and_a_shut_gate(project: Path, monkeypatch):
    gate(monkeypatch, True)
    r = run(project, tool("thym_check", path="orchard/publish-story.thym", inputs="story=orchard/notes.md",
                          model="cloud"))
    assert r.ok and r.body.splitlines()[2] == "3 model calls, at most 9, on the cloud (openrouter: vendor/large-model)"
    gate(monkeypatch, False)
    r = run(project, tool("thym_check", path="orchard/publish-story.thym", model="cloud"))
    assert r.ok and ("orchard/publish-story.thym:12: refused at plan (cloud): the cloud is not open for this run: "
                     "'local models only' is on in the broker") in r.body, r.body
    r = run(project, tool("thym_check", path="orchard/publish-story.thym", model="sky"))
    assert not r.ok and "<model> is local, cloud or cloud:<model id>" in r.body


def test_run_on_the_cloud_refuses_a_shut_gate_and_never_falls_back(project: Path, model: list, monkeypatch):
    asked = gate(monkeypatch, False)
    r = run(project, tool("thym_run", program="publish-story", path="orchard/notes.md", model="cloud"))
    assert not r.ok and "refused at plan (cloud): the cloud is not open for this run" in r.body, r.body
    assert asked and model == [] and not runs_dir().exists(), "never the local model instead"
    r = run(project, tool("thym_run", program="publish-story", path="orchard/notes.md", calls="none"))
    assert not r.ok and "<calls> is a ceiling of at least 1 model call" in r.body


def test_run_takes_a_folder_and_lists_every_output(project: Path):
    shutil.copytree(SUITE / "inputs" / "little-tool", project / "tool")
    shutil.copyfile(SUITE / "programs" / "split-a-folder.thym", project / "split.thym")
    r = run(project, tool("thym_run", program="split.thym", path="tool"))
    assert r.ok, r.body
    out = r.body.splitlines()
    assert out[1].startswith("code: ") and out[1].endswith("/ (a folder of 3 files)")
    assert out[2].startswith("prose: ") and out[3].startswith("size: ")
    r = run(project, tool("thym_run", program="split.thym", path="orchard/notes.md"))
    assert not r.ok and "notes.md is a file; repo takes a folder" in r.body
    r = run(project, tool("thym_check", path="split.thym"))
    assert "gives code: folder, prose: folder, size: number" in r.body


def moves_call(project: Path, text: str) -> T.ToolResult:
    """`thym_moves` through its runner: it is dispatched once the block names it (`TT.documented`)."""
    return TT.run_thym_moves(project, call(text))


def test_thym_moves_lists_what_a_program_of_a_version_may_use(project: Path):
    run = moves_call                                                    # noqa: F811 - the runner, as above
    r = run(project, tool("thym_moves"))
    assert r.ok and r.key == "thym 1"
    lines = r.body.splitlines()
    assert lines[0].startswith("the moves a thym 1 program may use (")
    tell = next(ln for ln in lines if ln.startswith("- tell "))
    assert tell.startswith("- tell <fabula | item | volume") and "[with <morph>] gives short" in tell, tell
    assert "; asks a model, scaffold outline; contract coverage, no-invention" in tell, tell
    assert "- context of <text | package> gives context; asks nothing." in r.body
    zero = run(project, tool("thym_moves", version="0"))
    assert zero.ok and len(zero.body.splitlines()) < len(lines), "a thym 0 program sees fewer moves"
    one = run(project, tool("thym_moves", move="derive"))
    assert one.ok and one.body.startswith("- derive <")
    assert not run(project, tool("thym_moves", move="dance")).ok
    assert not run(project, tool("thym_moves", version="2")).ok
    set_skill(project, False)
    off = run(project, tool("thym_moves"))
    assert not off.ok and "macrocosm-oes" in off.body


def test_thym_moves_is_registered_and_the_block_stays_under_its_cap():
    """The MacroCOSM block shown to the model is capped at 1,000 characters (tests/test_prompt_weight.py
    `CANON_BLOCK_MAX`); it names `thym_moves` now, so the tool is dispatched (the prompt-weight guard: a tool is
    callable only while a prompt names it, `TT.documented`)."""
    assert len(prompt.CANON_TOOL_INSTRUCTIONS) <= 1_000
    assert TT._RUNNERS["thym_moves"] is TT.run_thym_moves
    assert TT.documented("thym_moves")
    assert T._DISPATCH["thym_moves"] is TT.run_thym_moves
