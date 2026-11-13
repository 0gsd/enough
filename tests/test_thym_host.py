"""enough's side of Thym that wave 2 shares: the programs a run may pick (`thym_host.list_programs`,
`find_program`) and the three shipped programs, byte for byte the conformance suite's."""
from __future__ import annotations

from pathlib import Path

import pytest

from enough import thym_host as H

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "thym" / "programs"
NAMES = ("open-house", "publish-story", "read-my-way")


@pytest.mark.parametrize("name", NAMES)
def test_shipped_programs_are_the_suites(name: str) -> None:
    shipped = H.SHIPPED_PROGRAMS / f"{name}.thym"
    assert shipped.is_file(), f"defaults/thym/{name}.thym ships"
    assert shipped.read_bytes() == (FIXTURES / f"{name}.thym").read_bytes(), (
        f"defaults/thym/{name}.thym must stay byte for byte tests/fixtures/thym/programs/{name}.thym "
        "(the conformance suite's); change both, or neither")


def test_program_name_reads_the_declared_name(tmp_path: Path) -> None:
    assert H.program_name(FIXTURES / "publish-story.thym") == ("publish-story", None)
    bad = tmp_path / "bad.thym"
    bad.write_text("thym 0\n\nprogram oops\n  takes t: text\n", encoding="utf-8")
    name, problem = H.program_name(bad)
    assert name is None and problem
    assert H.program_name(tmp_path / "missing.thym")[1].startswith("cannot be read")


def test_list_programs_orders_project_canon_shipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    (project / "notes").mkdir(parents=True)
    (project / "rness").mkdir()
    (project / "notes" / "mine.thym").write_bytes((FIXTURES / "read-my-way.thym").read_bytes())
    (project / "rness" / "hidden.thym").write_bytes((FIXTURES / "read-my-way.thym").read_bytes())
    (project / "broken.thym").write_text("thym 0\n\nprogram oops\n", encoding="utf-8")
    store = tmp_path / "canon"
    (store / "field-notes").mkdir(parents=True)
    (store / "field-notes" / "open-house.thym").write_bytes((FIXTURES / "open-house.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(store))
    rows = H.list_programs(project)
    wheres = [r["where"] for r in rows]
    assert wheres[:3] == ["project", "project", "canon"] and set(wheres[3:]) == {"shipped"}, rows
    assert rows[0]["rel"] == "broken.thym" and rows[0]["name"] is None and rows[0]["problem"]
    assert rows[1] == {"name": "read-my-way", "where": "project", "path": str(project / "notes" / "mine.thym"),
                       "rel": "notes/mine.thym", "problem": None}
    assert rows[2]["rel"] == "canon:field-notes/open-house.thym" and rows[2]["name"] == "open-house"
    shipped = [r["rel"] for r in rows[3:]]
    assert shipped == sorted(shipped) and {"open-house.thym", "publish-story.thym", "read-my-way.thym"} <= set(shipped)
    assert "rness/hidden.thym" not in [r["rel"] for r in rows], "rness/ is the harness's, never a program's"


def test_find_program_by_name_prefers_the_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    mine = project / "publish-story.thym"
    mine.write_bytes((FIXTURES / "publish-story.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "canon"))
    assert H.find_program("publish-story", project) == mine
    assert H.find_program("open-house", project) == H.SHIPPED_PROGRAMS / "open-house.thym"
    assert H.find_program("nothing-of-the-kind", project) is None
    assert H.find_program("", project) is None


def test_find_program_by_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    (project / "a").mkdir(parents=True)
    mine = project / "a" / "p.thym"
    mine.write_bytes((FIXTURES / "publish-story.thym").read_bytes())
    store = tmp_path / "canon"
    (store / "vol").mkdir(parents=True)
    theirs = store / "vol" / "q.thym"
    theirs.write_bytes((FIXTURES / "open-house.thym").read_bytes())
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(store))
    assert H.find_program("a/p.thym", project) == mine
    assert H.find_program("canon:vol/q.thym", project) == theirs
    assert H.find_program("canon:../../a/p.thym", project) is None, "a store path never leaves the store"
    assert H.find_program("a/none.thym", project) is None
    assert H.find_program("read-my-way.thym") == H.SHIPPED_PROGRAMS / "read-my-way.thym", "a bare file name of a shipped program"


# ---------------------------------------------------------------------------
# Models in a run (THYM.md 23; docs/fabula-pins-thym1.md 4): the route, the plan's models block, made, the trace
# ---------------------------------------------------------------------------

import json  # noqa: E402
import sys  # noqa: E402
import types  # noqa: E402

from enough import agent_free, cloud, llm, models  # noqa: E402
from enough import model_route  # noqa: E402
from enough.thym import Refusal, check, parse  # noqa: E402
from enough.thym import plan as P  # noqa: E402
from enough.thym import run as RUN  # noqa: E402
from enough.thym.cli import models_line  # noqa: E402
from enough.thym.values import digest_path  # noqa: E402

SUITE = REPO / "tests" / "fixtures" / "thym"
NOTES = SUITE / "inputs" / "notes.md"
PUBLISH = FIXTURES / "publish-story.thym"
TREE = """thym 1

program tree
  why: a move that calls itself, and asks, under the depth it says.

  takes t: text
  gives n: number

  move again(x: text, more: bool): number
    depth: 2
    if more then
      give again x, false
    else
      give words (tell (derive x) as told)
    end
  end

  give again t, true
end
"""


@pytest.fixture
def live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The chat's slot (`g40-04`, a local one), no llama-server (its id and window read as unknown), no cloud call
    that a test did not stand in for."""
    state = tmp_path / "live-models.json"
    state.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", state)
    monkeypatch.setattr(H, "local_model_id", lambda url=None: None)
    monkeypatch.setattr(H, "_read_n_ctx", lambda url=None: None)

    def no_cloud(*a, **kw):
        raise AssertionError("the cloud was asked")
    monkeypatch.setattr(cloud, "chat_completion", no_cloud)
    return state


def gate(monkeypatch: pytest.MonkeyPatch, *, open_: bool, model_id: str = "vendor/large-model") -> list:
    asked: list = []

    def status() -> dict:
        asked.append(1)
        return {"open": open_, "reason": None if open_ else "'local models only' is on in the broker",
                "denial": None if open_ else "error: local models only is on (the broker's copy)",
                "model_id": model_id if open_ else None}
    monkeypatch.setattr(cloud, "gate_status", status)
    return asked


def set_agent_free(on: bool) -> None:
    path = agent_free.ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({agent_free.KEY: on}), encoding="utf-8")


def checked_of(text: str):
    c = check.check(parse.parse(text))
    assert not isinstance(c, Refusal), c
    return c


def publish_rows(path: Path = NOTES) -> list[dict]:
    return [{"name": "story", "type": "text", "path": str(path), "sha256": digest_path(path)}]


def test_the_routes_and_the_lock():
    assert H.ROUTES == ("local", "cloud") and H.check_route(None) == "local"
    assert H.holds_lock("local") is True and H.holds_lock("cloud") is False
    with pytest.raises(ValueError, match="local or cloud"):
        H.check_route("sky")


def test_local_route_info_names_the_machines_model_and_window(live, monkeypatch):
    monkeypatch.setattr(H, "local_model_id", lambda url=None: "g40-04-alias")
    monkeypatch.setattr(H, "_read_n_ctx", lambda url=None: 16384)
    assert H.route_info("local") == {"route": "local", "model": "g40-04-alias", "window": 16384}
    monkeypatch.setattr(H, "local_model_id", lambda url=None: None)
    assert H.route_info("local", n_ctx=8192) == {"route": "local", "model": "g40-04", "window": 8192}, \
        "without llama-server's id, the slot's name, which is its alias"


def test_cloud_route_info_reads_the_gate_and_the_window_constant(live, monkeypatch):
    gate(monkeypatch, open_=True)
    info = H.route_info("cloud")
    assert info == {"route": "cloud", "provider": "openrouter", "model": "vendor/large-model",
                    "gate": {"open": True, "reason": None, "denial": None}, "window": H.CLOUD_WINDOW}
    assert H.route_info("cloud", "vendor/other")["model"] == "vendor/other"
    assert H.route_info("cloud", n_ctx=200_000)["window"] == 200_000
    assert H.plan_models(info) == {"route": "cloud", "provider": "openrouter", "model": "vendor/large-model",
                                   "window": H.CLOUD_WINDOW}


def test_a_plan_shows_its_models_on_either_route(live, monkeypatch):
    c = checked_of(PUBLISH.read_text(encoding="utf-8"))
    monkeypatch.setattr(H, "local_model_id", lambda url=None: "g40-04")
    monkeypatch.setattr(H, "_read_n_ctx", lambda url=None: 16384)
    plan, info = H.plan_for(c, publish_rows())
    assert plan["models"] == {"route": "local", "model": "g40-04", "calls": 3, "at_most": 9, "calls_open": [],
                              "window": 16384}
    assert models_line(plan) == "3 model calls, at most 9, on this machine (g40-04)"
    assert H.route_refusal(plan, info) is None
    gate(monkeypatch, open_=True)
    plan, info = H.plan_for(c, publish_rows(), route="cloud")
    assert plan["models"]["route"] == "cloud" and plan["models"]["window"] == H.CLOUD_WINDOW
    assert models_line(plan) == "3 model calls, at most 9, on the cloud (openrouter: vendor/large-model)"
    assert P.normalise(plan) == P.normalise(H.plan_for(c, publish_rows())[0]), "the route is the run's, not the plan's"


def test_a_plan_that_asks_nothing_reads_no_model(live, monkeypatch):
    def no(*a, **kw):
        raise AssertionError("a plan that asks nothing reads nothing of any model")
    monkeypatch.setattr(H, "route_info", no)
    count = "thym 0\n\nprogram n\n  takes t: text\n  gives n: number\n\n  give words t\nend\n"
    plan, info = H.plan_for(checked_of(count), [{"name": "t", **publish_rows()[0]} | {"name": "t"}], route="cloud")
    assert info is None and "models" not in plan


def test_a_shut_gate_refuses_the_cloud_in_its_own_words_before_any_request(live, monkeypatch, tmp_path):
    asked = gate(monkeypatch, open_=False)
    c = checked_of(PUBLISH.read_text(encoding="utf-8"))
    plan, info = H.plan_for(c, publish_rows(), route="cloud")
    r = H.route_refusal(plan, info, program=PUBLISH)
    assert (r.stage, r.check, r.line) == ("plan", "cloud", 12)
    assert r.message == "the cloud is not open for this run: 'local models only' is on in the broker"
    # the run: refused at plan, nothing asked (chat_completion raises if it is), never a fall back to local
    monkeypatch.setattr(llm, "complete_local", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("local")))
    kw = H.runtime_kwargs(route="cloud", project_dir=tmp_path)
    t = RUN.run(plan, inputs_root=SUITE, program=PUBLISH, **kw)
    refusal = t if isinstance(t, Refusal) else t.refusal
    assert refusal.check == "cloud" and "the cloud is not open for this run" in refusal.message
    assert asked, "the gate was asked"


def test_agent_free_refuses_both_routes_and_asks_no_broker(live, monkeypatch):
    set_agent_free(True)

    def no_gate():
        raise AssertionError("agent-free asks no broker")
    monkeypatch.setattr(cloud, "gate_status", no_gate)
    c = checked_of(PUBLISH.read_text(encoding="utf-8"))
    for route in ("local", "cloud"):
        plan, info = H.plan_for(c, publish_rows(), route=route)
        assert info == {"route": route, "agent_free": True}
        r = H.route_refusal(plan, info, program=PUBLISH)
        assert (r.check, r.line) == ("agent-free", 12)
        assert r.message == (f"3 steps ask a model on the {route} route, the first `let f = derive story` (line 12); "
                             "agent-free is on")
        kw = H.runtime_kwargs(route=route)
        assert kw["agent_free"] is True and kw["preflight"] is None and kw["environment"]["model"] == "none"
        t = RUN.run(plan, inputs_root=SUITE, program=PUBLISH, **kw)
        assert (t if isinstance(t, Refusal) else t.refusal).check == "agent-free"


def test_an_open_count_on_the_cloud_needs_a_ceiling(live, monkeypatch):
    gate(monkeypatch, open_=True)
    plan, info = H.plan_for(checked_of(TREE), [{"name": "t", "type": "text", "path": str(NOTES),
                                                "sha256": digest_path(NOTES)}], route="cloud")
    assert plan["models"]["calls_open"] == ["R:node/1"]
    r = H.route_refusal(plan, info)
    assert r.check == "calls" and r.message == (
        "this plan may ask the cloud model a number of times nobody can know before it runs (again calls itself "
        "and asks); give a ceiling with --calls")
    assert "give a ceiling with calls" in H.route_refusal(plan, info, ceiling="calls").message
    assert H.route_refusal(plan, info, calls=40) is None
    assert "nobody can know" not in (models_line(plan) or "") and "cannot be counted" in models_line(plan)
    local, linfo = H.plan_for(checked_of(TREE), [{"name": "t", "type": "text", "path": str(NOTES),
                                                  "sha256": digest_path(NOTES)}])
    assert H.route_refusal(local, linfo) is None, "a local run needs no ceiling: it costs time, not money"


def test_the_cloud_window_constant_refuses_a_step_that_cannot_fit(live, monkeypatch, tmp_path):
    gate(monkeypatch, open_=True)
    big = tmp_path / "big.md"
    big.write_text("# Big\n\n" + "The orchard keeps a record of every tree it has ever had. " * 2400, encoding="utf-8")
    plan, info = H.plan_for(checked_of(PUBLISH.read_text(encoding="utf-8")), publish_rows(big), route="cloud")
    assert info["window"] == H.CLOUD_WINDOW == 32_768
    r = H.route_refusal(plan, info)
    assert r.check == "preflight" and f"the model's window is {H.CLOUD_WINDOW:,}" in r.message
    assert H.route_refusal(plan, {**info, "window": 400_000}) is None, "a window the caller knows is read instead"


def test_local_runs_on_llama_server_whatever_the_chats_slot(live, monkeypatch):
    live.write_text(json.dumps({"current": "opro-api"}), encoding="utf-8")          # the chat is on the cloud slot
    seen: list = []

    def complete_local(messages, *, llm_url, **kw):
        seen.append(llm_url)
        return "A telling.", {"model": "g40-04", "route": "local", "usage": {"total_tokens": 9}}
    monkeypatch.setattr(llm, "complete_local", complete_local)
    cop = H.runtime_kwargs(route="local", llm_url="http://127.0.0.1:9")["coprocessor"]
    cand = cop.complete({"move": "tell", "schema": {"format": "markdown"}, "checks": [], "repair": {}}, {},
                        budget={"attempts": 1, "output_words": 0, "prompt_tokens_max": 0, "seconds": 1})
    assert seen == ["http://127.0.0.1:9"]
    assert (cand["engine"], cand["route"], cand["tokens"]) == ("model:g40-04", "local", 9) and "provider" not in cand


def test_a_cloud_candidate_says_its_route_provider_and_the_models_own_id(live, monkeypatch, tmp_path):
    gate(monkeypatch, open_=True)
    monkeypatch.setattr(cloud, "chat_completion", lambda messages, **kw: {
        "model": "vendor/large-model-2026", "usage": {"total_tokens": 21},
        "choices": [{"finish_reason": "stop", "message": {"content": "A telling."}}]})
    cop = H.runtime_kwargs(route="cloud", model="vendor/large-model", project_dir=tmp_path)["coprocessor"]
    cand = cop.complete({"move": "tell", "schema": {"format": "markdown"}, "checks": [], "repair": {}}, {},
                        budget={"attempts": 1, "output_words": 0, "prompt_tokens_max": 0, "seconds": 1})
    assert (cand["engine"], cand["route"], cand["provider"]) == ("model:vendor/large-model-2026", "cloud",
                                                                  "openrouter")
    assert cop.model_seen() == "vendor/large-model-2026"
    assert list((tmp_path / "rness" / "io" / "cloud-cache").glob("*.md")), "cached in the project under source thym"


def test_a_coprocessor_with_no_route_says_none_as_before():
    cop = H.ModelCoprocessor(lambda m: ("A telling.", {"model": "m1"}))
    cand = cop.complete({"move": "tell", "schema": {"format": "markdown"}, "checks": [], "repair": {}}, {},
                        budget={})
    assert "route" not in cand and "provider" not in cand and cand["engine"] == "model:m1"


def test_the_trace_names_the_model_that_ran_its_route_and_provider_not_the_slot(live, tmp_path, monkeypatch):
    import test_thym_run as TR
    answers = [TR.TWIN.read_text(encoding="utf-8"), TR.telling()]

    def complete(messages, **kw):
        return answers.pop(0), {"model": "vendor/large-model", "route": "cloud", "provider": "openrouter"}
    gate(monkeypatch, open_=True)
    kw = H.runtime_kwargs(route="cloud", complete=complete, project_dir=tmp_path)
    kw.pop("root")
    t = RUN.run(TR.brief_plan(), inputs_root=TR.SUITE, root=tmp_path / "thym", moves=TR.fake_moves(),
                checks=TR.fake_checks(), **kw)
    assert t.landed, t.refusal
    env = t.environment
    assert (env["model"], env["route"], env["provider"], env["context"]) == (
        "vendor/large-model", "cloud", "openrouter", H.CLOUD_WINDOW)
    assert env["model"] != "g40-04", "the chat's slot does not name a run's model"
    assert t.values["s"].made["engine"] == "model:vendor/large-model"


def test_made_and_the_recorded_candidate_carry_the_route(live, tmp_path, monkeypatch):
    import test_thym_run as TR
    answers = [TR.TWIN.read_text(encoding="utf-8"), TR.telling()]

    def complete(messages, **kw):
        return answers.pop(0), {"model": "vendor/large-model", "route": "cloud", "provider": "openrouter"}
    gate(monkeypatch, open_=True)
    kw = H.runtime_kwargs(route="cloud", complete=complete, project_dir=tmp_path)
    kw.pop("root")
    t = RUN.run(TR.brief_plan(), inputs_root=TR.SUITE, root=tmp_path / "thym", moves=TR.fake_moves(),
                checks=TR.fake_checks(), **kw)
    assert t.landed, t.refusal
    made = t.values["s"].made
    rec = (t.dir / "candidates" / "2.1.cosm").read_text(encoding="utf-8")
    again = RUN.replay(t.dir, inputs_root=TR.SUITE, root=tmp_path / "thym", moves=TR.fake_moves(), checks=TR.fake_checks())
    assert (made["route"], made["provider"]) == ("cloud", "openrouter") and "route: cloud" in rec
    assert again.values["s"].made.get("route") == "cloud"


def test_a_run_recorded_before_routes_replays_without_one(tmp_path):
    import test_thym_run as TR
    cp = TR.FakeCoprocessor({"derive": TR.TWIN.read_text(encoding="utf-8"), "tell": TR.telling()})
    t = RUN.run(TR.brief_plan(), inputs_root=TR.SUITE, root=tmp_path / "thym", coprocessor=cp,
                moves=TR.fake_moves(), checks=TR.fake_checks())
    assert "route" not in (t.dir / "candidates" / "2.1.cosm").read_text(encoding="utf-8")
    again = RUN.replay(t.dir, inputs_root=TR.SUITE, root=tmp_path / "thym", moves=TR.fake_moves(), checks=TR.fake_checks(),
                       environment=H.environment(agent_free=False, route="local"))
    assert again.landed and again.replay["identical"] is True
    assert "route" not in again.values["s"].made and again.outputs["s"].read_bytes() == t.outputs["s"].read_bytes()


# ---------------------------------------------------------------------------
# The sibling lanes' engines and prompt builders, found when present
# ---------------------------------------------------------------------------

def test_sibling_engines_join_when_their_modules_are_there(monkeypatch):
    repo = types.ModuleType("enough.repo_engine")
    repo.repo_engine = lambda: "the repo engine"
    repo.syntax_engine = lambda: "the syntax engine"
    dia = types.ModuleType("enough.dialectic")
    dia.thym_engine = lambda: "the dialectic engine"
    monkeypatch.setitem(sys.modules, "enough.repo_engine", repo)
    monkeypatch.setitem(sys.modules, "enough.dialectic", dia)
    got = H.engines(feed=None)
    assert (got["repo"], got["syntax"], got["dialectic"]) == ("the repo engine", "the syntax engine",
                                                              "the dialectic engine")


def test_sibling_engines_are_skipped_quietly_when_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "enough.repo_engine", None)     # import raises ModuleNotFoundError
    monkeypatch.setitem(sys.modules, "enough.dialectic", None)
    got = H.engines(feed=None)
    assert not {"repo", "syntax", "dialectic"} & set(got) and {"canon", "docoes"} <= set(got)
    broken = types.ModuleType("enough.repo_engine")

    def boom():
        raise RuntimeError("mid-build")
    broken.repo_engine = boom
    monkeypatch.setitem(sys.modules, "enough.repo_engine", broken)
    assert "repo" not in H.engines(feed=None), "an engine that cannot be made is skipped, and the run goes on"


def test_sibling_prompt_builders_go_first_and_pass_what_is_not_theirs(monkeypatch):
    from enough.thym import registry
    mod = types.ModuleType("enough.fabulac_prompts")

    def derive_code(contract, inputs):
        return [{"role": "user", "content": "code"}] if contract.get("as") == "code" else None
    mod.PROMPTS = {"derive": derive_code, "survey-note": lambda c, i: [{"role": "user", "content": "new"}]}
    monkeypatch.setitem(sys.modules, "enough.fabulac_prompts", mod)
    for absent in ("enough.thym.moves.code", "enough.thym.moves.dialectic"):
        monkeypatch.setitem(sys.modules, absent, None)
    moves = registry.Moves()
    assert {"derive", "survey-note"} <= set(H.register_prompts(moves))
    build = moves.prompt("derive")
    assert build({"move": "derive", "as": "code"}, {}) == [{"role": "user", "content": "code"}]
    host = build({"move": "derive"}, {})
    assert host[0]["role"] == "system", "a request that is not the sibling's reaches the host's own builder"
    assert moves.prompt("survey-note")({"move": "survey-note"}, {}) == [{"role": "user", "content": "new"}]
    H.register_prompts(moves)
    assert len(moves.prompt("derive").chain) == 2, "registering again builds the chain again, never nests it"
    monkeypatch.setitem(sys.modules, "enough.fabulac_prompts", None)
    fresh = registry.Moves()
    assert "derive" not in H.register_prompts(fresh) and fresh.prompt("derive") is None


def test_a_thym_1_text_is_a_program_where_programs_are_recognised():
    from enough.thym.moves import doc
    assert doc.is_program("thym 1\n\nprogram p\n") and doc.is_program("-- a note\n\nthym 0 -- old\n")
    assert doc.is_program((FIXTURES / "split-a-folder.thym").read_text(encoding="utf-8"))
    assert not doc.is_program("# thym 1\n\nA note about Thym.\n")


def test_check_input_holds_each_input_to_what_it_takes(tmp_path):
    inputs = SUITE / "inputs"
    ok = {"text": inputs / "notes.md", "fabula": inputs / "notes.md.cosm", "folder": inputs / "little-tool",
          "morph": inputs / "plain-letter.morph.cosm", "context": inputs / "on-the-train.context.cosm",
          "package": inputs / "orchard-notes.thym", "volume": inputs / "notes.md.cosm", "short": inputs / "notes.md"}
    for typ, p in ok.items():
        assert H.check_input(p, typ) is None, (typ, p)
    assert H.check_input(inputs / "notes.md", "folder", name="repo") == "notes.md is a file; repo takes a folder"
    assert H.check_input(inputs / "little-tool", "text", name="story") == \
        "little-tool is a folder; story takes a text (a markdown or plain file)"
    assert "is not a fabula" in H.check_input(inputs / "notes.md", "fabula")
    assert "is not a morph" in H.check_input(inputs / "on-the-train.context.cosm", "morph")
    assert "is not a context" in H.check_input(inputs / "plain-letter.morph.cosm", "context")
    assert "is not a package" in H.check_input(inputs / "notes.md", "package")
    assert "is a volume" in H.check_input(inputs / "notes.md.cosm", "text")
    assert H.check_input(tmp_path / "none.md", "text", name="story") == "no such file: none.md (story)"
    assert H.accepts("folder") == "a folder" and H.accepts("number") == "a number"


def test_the_dialectic_module_is_the_dialectic_engine_as_a_namespace_of_its_functions(monkeypatch):
    # the dialectic now makes its engine (`thym_engine`, docs/fabula-landed-T1-dialectic.md 9.1): the host's engine is
    # exactly that namespace of the module's own functions
    from enough import dialectic
    eng = H.engines(feed=None)["dialectic"]
    made = vars(dialectic.thym_engine())
    assert made and vars(eng).keys() == made.keys()
    assert all(getattr(eng, n) is getattr(dialectic, n) for n in made)
    # a dialectic module without the maker is still the engine itself, its public names as a namespace
    bare = types.ModuleType("enough.dialectic")
    bare.question = lambda *a: "q"
    bare.STATES = ("open",)
    bare.__all__ = ["question", "STATES"]
    monkeypatch.setitem(sys.modules, "enough.dialectic", bare)
    ns = H.sibling_engine("dialectic")
    assert ns.question is bare.question and ns.STATES == ("open",)


def test_the_ascribe_engine_is_found_by_name_and_is_ascribes_own(monkeypatch):
    """`ascribe` joins the engines lazily, by name, as the other siblings do: `enough.ascribe.thym_engine()`'s
    namespace when the module is there, nothing (quietly) when it is not."""
    from enough import ascribe
    assert H.SIBLING_ENGINES["ascribe"] == ("enough.ascribe", "thym_engine")
    eng = H.engines(feed=None)["ascribe"]
    assert set(vars(eng)) == set(ascribe.THYM_FUNCTIONS)
    assert all(getattr(eng, n) is getattr(ascribe, n) for n in ascribe.THYM_FUNCTIONS)
    monkeypatch.setitem(sys.modules, "enough.ascribe", None)        # the module not there: skipped, no error
    assert "ascribe" not in H.engines(feed=None)


def test_find_program_where_looks_in_one_place_only(tmp_path: Path):
    """Lane S4: a shipped program and a project file of the same bare name are told apart by `where`."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "tighten.thym").write_text("thym 0\n\nprogram mine\n  takes s: text\n  gives n: number\n\n"
                                       "  give words s\nend\n", encoding="utf-8")
    assert H.find_program("tighten.thym", proj) == proj / "tighten.thym"            # as before: the project's
    assert H.find_program("tighten.thym", proj, where="shipped") == H.SHIPPED_PROGRAMS / "tighten.thym"
    assert H.find_program("tighten", proj, where="shipped") == H.SHIPPED_PROGRAMS / "tighten.thym"
    assert H.find_program("tighten.thym", proj, where="project") == proj / "tighten.thym"
    assert H.find_program("mine", proj, where="project") == proj / "tighten.thym"
    assert H.find_program("mine", proj, where="shipped") is None
    assert H.find_program("publish-story.thym", proj, where="project") is None
    assert H.find_program("x/tighten.thym", proj, where="shipped") is None
    assert H.find_program("../tighten.thym", proj, where="project") is None
    assert H.find_program("canon:v/a.thym", proj, where="project") is None
    with pytest.raises(ValueError):
        H.find_program("tighten.thym", proj, where="elsewhere")


def test_accepts_says_a_list_by_its_members():
    assert H.accepts("list of text") == "a list of texts (each a markdown or plain file)"
    assert H.accepts("list of folder") == "a list of folders"
    assert H.accepts("list of item") == "a list of items"
    assert H.accepts("text") == "a text (a markdown or plain file)"
