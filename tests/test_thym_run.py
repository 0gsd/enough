"""Thym's runtime (docs/THYM.md 12, 19, 20.2): `enough/thym/` values, registry, checks, coprocessors, run, trace,
conform and CLI, and `enough/thym_host.py`.

Every move here is a fake registered in a test registry (a `derive` that answers with the orchard twin, a `tell`, a
deterministic `count`/`band`/`mark`/`withhold`/`project` that build a projection), every model answer comes from a
`FakeCoprocessor`, and the engine-backed checks the moves lane will bring are stood in for by fakes. Every run lands
in a tmp root (conftest points ENOUGH_THYM_ROOT there); nothing touches ~/enough and no model is started.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import cli, conform
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import ReplayCoprocessor, candidate
from enough.thym.registry import Request
from enough.thym.values import NOTHING, Value, digest_path, load_input, members, read_value

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
NOTES = SUITE / "inputs" / "notes.md"
TWIN = SUITE / "inputs" / "notes.md.cosm"
NOTES_SHA = hashlib.sha256(NOTES.read_bytes()).hexdigest()
FOOTER = "*a telling of notes.md's fabula, as told*"


def load(rel: str) -> dict:
    return mc.yaml_load((SUITE / rel).read_text(encoding="utf-8"))


def lint_errors(path: Path) -> list[str]:
    vol = mc.load_volume(path)
    assert vol.refused is None, vol.refused
    return [str(p) for p in mc.lint(vol).errors]


# ---------------------------------------------------------------------------
# Fakes: moves, checks, a coprocessor
# ---------------------------------------------------------------------------

def fake_moves() -> R.Moves:
    mv = R.Moves()

    @mv.implements("count")
    def count(ctx, v):
        return Value("number", len(members(v) or []))

    @mv.implements("band")
    def band(ctx, n, **m):
        words = m["as"]
        return Value("word", words[0] if n.payload == 0 else words[-1])

    @mv.implements("mark")
    def mark(ctx, x, **m):
        if x.type == "word":
            return Value("word", x.payload, origin={"marked": m["as"]})
        return Value("item", {**x.payload, "marked": m["as"]}, origin=x.origin)

    @mv.implements("withhold")
    def withhold(ctx, v, **m):
        ctx.withhold(m["where"].select(v))

    @mv.implements("project")
    def project(ctx, h, **m):
        offers = [{"name": e.payload.get("name"), "kind": (e.origin or {}).get("kind")} for e in ctx.emitted
                  if (e.origin or {}).get("id") not in ctx.withheld]
        return Value("volume", {"isotype": "comprise-isotype/0", "sample": True,
                                "identity": {"name": h.payload.catalog.get("name")},
                                "shape": {"employees": ctx.slots["employees"].payload}, "offers": offers})

    @mv.implements("fabula")
    def fabula_of(ctx, **m):
        return read_value(m["of"].path / "fabula.cosm", "fabula")

    @mv.implements("derive")
    def derive(ctx, story):
        return Request(contract={"schema": {"format": "yaml"}, "repair": ["normalise-stance"]},
                       inputs={"story": story})

    @mv.implements("derive.scaffold")
    def derive_rules(ctx, story):
        twin = mc.yaml_load(TWIN.read_text(encoding="utf-8"))
        twin["derived"] = {**twin["derived"], "mode": "rules"}
        return Value("fabula", twin)

    for name in ("tell", "expand", "read"):
        mv.add(name, lambda ctx, *ops, _n=name, **m: Request(contract={"schema": {"format": "markdown"}},
                                                             inputs={f"in{k}": v for k, v in enumerate(ops)}))

    @mv.implements("cut")
    def cut(ctx, short, **m):
        first = C.sentences(C.body(short.text()))[0]
        return Value("short", first + "\n")

    @mv.implements("atem")
    def atem(ctx, x):
        return Request(contract={"schema": {"format": "yaml"}}, inputs={"x": x})

    return mv


ENGINE_CHECKS = ("span-resolves", "stance-closed", "terms-grounded", "coverage", "no-invention", "stance-kept",
                 "footer", "atem-shape", "span-inside", "weight-order", "verified-only-where-derived", "banded",
                 "verified-derived", "standing-gate", "epoch", "scales-met")


def fake_checks(**override) -> C.Checks:
    ck = C.CHECKS.copy()
    for name in ENGINE_CHECKS:
        ck.add(name, lambda *a: (True, ""))
    ck.add("footer", lambda out, *a: (out.text().rstrip().endswith("*"), "the short has no footer line"))
    for name, fn in override.items():
        ck.add(name.replace("_", "-"), fn)
    return ck


class FakeCoprocessor:
    """Answers from a dict, move -> output, or move -> a list of outputs, one per call in turn."""

    def __init__(self, answers: dict) -> None:
        self.answers = {k: (list(v) if isinstance(v, list) else v) for k, v in answers.items()}
        self.calls: list[tuple[str, dict]] = []

    def complete(self, contract, inputs, *, budget):
        self.calls.append((contract["move"], {k: v for k, v in contract.items()}))
        a = self.answers[contract["move"]]
        out = a.pop(0) if isinstance(a, list) else a
        return candidate(out, engine="model:fake-1", tokens=10, seconds=0)


def telling(words: int = 30, footer: bool = True) -> str:
    body = " ".join(["The orchard gave more juice this year."] * max(1, words // 7))
    return f"{body}\n\n{FOOTER}\n" if footer else f"{body}\n"


def node(n: int, name: str, move: str, *, asks: bool = False, takes=(), gives=None, after=(), line=1, **extra):
    it = {"id": f"R:node/{n}", "type": "node", "name": name, "summary": name.capitalize() + ".",
          "step": {"program": "brief", "n": n}, "move": move, "asks": asks, "takes": list(takes)}
    if gives:
        it["gives"] = gives
    it["after"] = list(after)
    it["budget"] = {"attempts": 3 if asks else 1, "output_words": 0}
    it["line"] = line
    it.update(extra)
    it["provenance"] = {"mode": "derived", "sources": ["brief.thym"], "confidence": 1}
    return it


def hand_plan(*nodes: dict, name: str = "brief", inputs=None) -> dict:
    asks = sum(1 for n in nodes if n["asks"])
    return {"oes": "thym/1", "kind": "plan", "id": f"thym/plan.{name}", "name": f"{name} on notes.md",
            "program": {"name": name, "sha256": "0" * 64},
            "inputs": inputs if inputs is not None else
            [{"name": "story", "type": "text", "path": "inputs/notes.md", "sha256": NOTES_SHA}],
            "estimate": {"steps": len(nodes), "asks": asks, "largest_prompt": 400, "output_words": 0},
            "nodes": [{"id": "R:plan/fixture", "type": "plan", "name": name, "summary": "A hand-written plan.",
                       "nodes": [n["id"] for n in nodes], "asks": asks, "largest_prompt": 400,
                       "provenance": {"mode": "derived", "sources": [f"{name}.thym"], "confidence": 1}}, *nodes]}


def brief_plan() -> dict:
    return hand_plan(node(1, "derive story", "derive", asks=True, takes=["story"], gives="f", line=5),
                     node(2, "tell f as told", "tell", asks=True, takes=["f"], gives="s", after=["R:node/1"], line=6))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "thym-root"


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def test_reader_reads_the_node_names_of_the_fixture_plans():
    moves = frozenset(R.read_declarations()) | {"offer-line"}
    st = RUN.read_statement("emit offer-line o, for each o in h where kind in [product, service, platform]", moves)
    assert st.form == "emit" and st.expr.move == "offer-line" and st.loop.var == "o"
    assert isinstance(st.loop.cond, RUN.Cmp) and st.loop.cond.op == "in"
    st = RUN.read_statement("emit employees: mark t4 as verified", moves)
    assert st.slot == "employees" and st.expr.mods == {"as": "verified"}
    st = RUN.read_statement("band t3 as [none, some]", moves)
    assert st.expr.mods["as"] == ["none", "some"]
    st = RUN.read_statement("expand t3 with f to 300 words", moves)
    assert st.expr.mods["to"] == R.Amount(300, "words") and isinstance(st.expr.mods["with"], RUN.Name)
    st = RUN.read_statement('if now.medium is "phone" and now.hurry', moves)
    assert st.form == "if" and isinstance(st.cond, RUN.BoolOp)
    st = RUN.read_statement("assert f covers story", moves)
    assert isinstance(st.cond, RUN.Covers)
    st = RUN.read_statement("package story, f, m, c, g", moves)
    assert [o.name for o in st.expr.operands] == ["story", "f", "m", "c", "g"]
    st = RUN.read_statement("measure story against null of f", moves)
    assert st.expr.mods["against"].move == "null"
    st = RUN.read_statement("withhold h where visibility is internal", moves)
    assert st.expr.move == "withhold" and st.expr.mods["where"][1] == "visibility is internal"
    with pytest.raises(RUN.ReadError):
        RUN.read_statement("band t3 as", moves)


def test_program_info_reads_lets_and_user_moves_from_items_and_from_source():
    a = RUN.ProgramInfo.from_items(load("expected/open-house/items.cosm"))
    b = RUN.ProgramInfo.from_source((SUITE / "programs" / "open-house.thym").read_text(encoding="utf-8"))
    for info in (a, b):
        assert info.name == "open-house" and info.gives == ("i", "volume")
        assert info.lets == {"staff": "h where module is employees"}
        assert list(info.moves) == ["offer-line"]
        assert info.moves["offer-line"].params == [("o", "item")]
        assert info.moves["offer-line"].body[0][2].startswith("give mark o as verified")
    ps = RUN.ProgramInfo.from_source((SUITE / "programs" / "publish-story.thym").read_text(encoding="utf-8"))
    assert ps.messages == {13: "the fabula does not cover the text"} and ps.gives == ("out", "package")


# ---------------------------------------------------------------------------
# Deterministic runs land, with made, and the trace lints clean
# ---------------------------------------------------------------------------

def test_open_house_runs_deterministically_and_lands_with_made(root):
    t = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root,
                program=load("expected/open-house/items.cosm"), moves=fake_moves(), checks=fake_checks())
    assert isinstance(t, T.Trace), t
    assert t.outcome == "landed", t.refusal
    out = t.outputs["i"]
    assert out == t.dir / "outputs" / "i.cosm" and out.is_file()
    iso = mc.yaml_load(out.read_text(encoding="utf-8"))
    assert set(iso) <= set(C.ISOTYPE_KEYS)
    assert iso["shape"] == {"employees": "none"}                      # count 0 (the sample keeps no people), banded
    assert {o["kind"] for o in iso["offers"]} == {"product", "service"}
    made = t.values["i"].made
    assert made["run"] == t.run_id and made["move"] == "project" and made["engine"] == "code" and made["step"] == 8
    assert not (t.dir / "stage").exists()
    assert (t.dir / f"{t.run_id}.plan.cosm").is_file()
    assert len(T.records_of(t.to_volume())) == 7
    assert lint_errors(t.path) == []
    assert t.atem().startswith("ran open-house on meadow in ") and t.atem().endswith("all checks green")


def test_open_house_runs_the_same_from_the_program_source(root):
    a = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root,
                program=load("expected/open-house/items.cosm"), moves=fake_moves(), checks=fake_checks())
    b = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root,
                program=SUITE / "programs" / "open-house.thym", moves=fake_moves(), checks=fake_checks())
    assert a.landed and b.landed
    assert a.outputs["i"].read_bytes() == b.outputs["i"].read_bytes()


def test_a_let_filter_without_the_program_is_refused_with_the_fix(root):
    t = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root, moves=fake_moves(),
                checks=fake_checks())
    assert isinstance(t, Refusal) and t.stage == "plan" and t.check == "unknown-move"
    assert "program beside the plan" in t.message


# ---------------------------------------------------------------------------
# Plan-time refusals: agent-free, inputs, preflight, implementations
# ---------------------------------------------------------------------------

def test_agent_free_refuses_a_plan_that_asks_before_any_call(root):
    cp = FakeCoprocessor({})
    r = RUN.run(load("expected/publish-story/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                agent_free=True, moves=fake_moves(), checks=fake_checks())
    assert isinstance(r, Refusal)
    assert (r.stage, r.check, r.line) == ("plan", "agent-free", 12)
    # THYM 9: the first step that asks is named as the person wrote it; without the program, by the plan's words
    assert r.message == "3 steps ask a model on the local route, the first derive story (line 12); agent-free is on"
    assert cp.calls == []
    assert not (root / "runs").exists()


def test_agent_free_runs_a_deterministic_plan(root):
    t = RUN.run(load("expected/open-house/plan.cosm"), inputs_root=SUITE, root=root, agent_free=True,
                program=load("expected/open-house/items.cosm"), moves=fake_moves(), checks=fake_checks())
    assert t.landed and t.environment["agent_free"] is True


def test_a_changed_or_missing_input_is_refused_at_plan_time(root, tmp_path):
    plan = brief_plan()
    plan["inputs"][0]["sha256"] = "1" * 64
    r = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({}), moves=fake_moves(),
                checks=fake_checks())
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "input") and "changed" in r.message
    plan["inputs"][0]["path"] = "inputs/nowhere.md"
    r = RUN.run(plan, inputs_root=SUITE, root=root, moves=fake_moves(), checks=fake_checks())
    assert isinstance(r, Refusal) and "is not there" in r.message


def test_preflight_refuses_a_prompt_the_model_cannot_hold(root):
    from enough import thym_host
    hook = thym_host.preflight_hook(16384)
    plan = brief_plan()
    plan["nodes"][0]["largest_prompt"] = 30000
    cp = FakeCoprocessor({})
    r = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=cp, preflight=hook, moves=fake_moves(),
                checks=fake_checks())
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "preflight")
    assert "30,000 tokens" in r.message and "16,384" in r.message and "32,768-token window" in r.message
    assert cp.calls == []
    assert thym_host.preflight_hook(65536)(plan) is None
    assert thym_host.preflight_hook(lambda: None)(plan) is None        # unknown never refuses


def test_a_move_with_no_implementation_is_refused_at_plan_time(root):
    mv = fake_moves()
    mv.remove("tell")
    r = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=FakeCoprocessor({}), moves=mv,
                checks=fake_checks())
    assert isinstance(r, Refusal) and (r.stage, r.check, r.line) == ("plan", "move", 6)


# ---------------------------------------------------------------------------
# Model-backed nodes: checks, attempts, nothing partial
# ---------------------------------------------------------------------------

def test_a_failing_check_refuses_the_whole_run_and_nothing_lands(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling(footer=False)})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=fake_checks())
    assert isinstance(t, T.Trace) and t.outcome == "refused"
    assert (t.refusal.stage, t.refusal.check, t.refusal.line) == ("run", "footer", 6)
    assert "after 3 attempts" in t.refusal.message
    assert t.stopped_at == "R:record/2"
    assert [m for m, _ in cp.calls] == ["derive", "tell", "tell", "tell"]   # attempts are bounded
    assert not (t.dir / "outputs").exists() and not (t.dir / "stage").exists()
    vol = T.read(t.run_id, root=root)
    head = T.root_item(vol)
    assert vol["outcome"] == "refused" and head["stopped_at"] == "R:record/2"
    rec = next(r for r in T.records_of(vol) if r["id"] == "R:record/2")
    assert rec["attempts"] == 3 and rec["engine"] == "model:fake-1"
    assert {"name": "footer", "ok": False, "why": "the short has no footer line"} in rec["checks"]
    # every failed attempt is kept, so a refused node explains all its tries, not only the last (THYM.md 12.3)
    assert [x["attempt"] for x in rec["tries"]] == [1, 2, 3]
    assert all(x["failed"] == [{"name": "footer", "why": "the short has no footer line"}] for x in rec["tries"])
    assert lint_errors(t.path) == []


def test_a_second_attempt_carries_the_failed_checks_and_lands(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"),
                          "tell": [telling(footer=False), telling()]})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=fake_checks())
    assert t.landed, t.refusal
    second = cp.calls[2][1]
    assert second["repair"]["failed"] == [{"name": "footer", "ok": False, "why": "the short has no footer line"}]
    assert second["checks"] == ["coverage", "no-invention", "stance-kept", "scales-met", "footer", "provenance"]
    rec = next(r for r in t.records if r["id"] == "R:record/2")
    assert rec["attempts"] == 2
    assert [x["attempt"] for x in rec["tries"]] == [1], "only the attempt that failed is a try"
    assert t.outputs["s"].read_text(encoding="utf-8") == telling()
    fabula = t.values.get("f") or None
    assert fabula is None                                        # only the program's output is landed


def test_a_check_the_registry_lacks_refuses_never_passes(root):
    ck = fake_checks()
    ck._fns.pop("no-invention")
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling()})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=ck)
    assert t.outcome == "refused"
    assert (t.refusal.stage, t.refusal.check, t.refusal.message) == ("run", "no-invention",
                                                                      "tell f as told (line 6): check not implemented")


def test_model_output_carries_made_with_its_engine(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling()})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=fake_checks())
    assert t.landed
    assert t.values["s"].made == {"move": "tell", "run": t.run_id, "step": 2, "node": "2", "engine": "model:fake-1"}
    assert sorted(p.name for p in (t.dir / "candidates").iterdir()) == ["1.1.cosm", "2.1.cosm"]


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def test_a_recorded_run_replays_to_byte_identical_outputs(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": [telling(footer=False), telling()]})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=fake_checks())
    assert t.landed
    again = RUN.replay(t.dir, root=root, moves=fake_moves(), checks=fake_checks())
    assert isinstance(again, T.Trace) and again.landed, getattr(again, "refusal", again)
    assert again.replay == {"of": t.run_id, "identical": True, "differences": []}
    assert again.run_id != t.run_id
    assert again.outputs["s"].read_bytes() == t.outputs["s"].read_bytes()
    assert again.values["s"].made["run"] == t.run_id                       # made names the recorded run
    assert T.root_item(again.to_volume())["replay_of"] == t.run_id


def test_the_replay_coprocessor_refuses_a_changed_input_or_contract(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling()})
    t = RUN.run(brief_plan(), inputs_root=SUITE, root=root, coprocessor=cp, moves=fake_moves(), checks=fake_checks())
    rc = ReplayCoprocessor(t.dir)
    story = load_input(brief_plan()["inputs"][0], SUITE)
    # a hand plan names no grammar version, so its derive is held to the thym 1 view's contract, which spells the
    # fabula's checks fabula-checks (a thym 0 program's view still says emf-checks: test_thym_versions)
    contract = {"move": "derive", "schema": {"format": "yaml"},
                "checks": ["span-resolves", "stance-closed", "terms-grounded", "coverage", "fabula-checks", "provenance"],
                "repair": {"allowed": ["normalise-stance"], "failed": []}}
    budget = {"attempts": 3, "output_words": 0, "prompt_tokens_max": 400, "seconds": 600}
    ok = rc.complete(contract, {"story": (story, story.sha256)}, budget=budget, at=("1", 1))
    assert not isinstance(ok, Refusal) and ok["engine"] == "model:fake-1"
    bad = rc.complete(contract, {"story": (story, "0" * 64)}, budget=budget, at=("1", 1))
    assert isinstance(bad, Refusal) and bad.check == "replay" and "input story" in bad.message
    other = rc.complete({**contract, "checks": ["provenance"]}, {"story": (story, story.sha256)}, budget=budget,
                        at=("1", 1))
    assert isinstance(other, Refusal) and "checks" in other.message
    assert isinstance(rc.complete(contract, {}, budget=budget, at=("9", 1)), Refusal)


# ---------------------------------------------------------------------------
# Rules mode and branches
# ---------------------------------------------------------------------------

def test_rules_runs_the_scaffold_and_marks_its_output_pending(root):
    plan = hand_plan(node(1, "derive story", "derive", asks=True, takes=["story"], gives="f", line=5))
    cp = FakeCoprocessor({})
    t = RUN.run(plan, inputs_root=SUITE, root=root, coprocessor=cp, rules=True, moves=fake_moves(),
                checks=fake_checks())
    assert t.landed, t.refusal
    assert cp.calls == []
    rec = t.records[0]
    assert rec["engine"] == "rules" and rec["state"] == "pending"
    v = t.values["f"]
    assert v.state == "pending" and v.made["engine"] == "rules"
    twin = mc.yaml_load(t.outputs["f"].read_text(encoding="utf-8"))
    assert all(n["provenance"]["state"] == "pending" for n in twin["nodes"] if "provenance" in n)
    assert lint_errors(t.path) == []


def test_rules_refuses_a_plan_whose_model_steps_have_no_scaffold(root):
    plan = hand_plan(node(1, "derive story", "derive", asks=True, takes=["story"], gives="f", line=5),
                     node(2, "expand f to 300 words", "expand", asks=True, takes=["f"], gives="s", after=["R:node/1"],
                          line=6))                                # expand declares no scaffold (THYM.md 19)
    r = RUN.run(plan, inputs_root=SUITE, root=root, rules=True, moves=fake_moves(), checks=fake_checks())
    assert isinstance(r, Refusal) and (r.stage, r.check, r.line) == ("plan", "rules", 6)
    assert r.message == "1 step asks a model and has no scaffold: expand f to 300 words (line 6); --rules runs no model"
    r = RUN.run(plan, inputs_root=SUITE, root=root, rules=True, agent_free=True, moves=fake_moves(),
                checks=fake_checks())
    assert (r.check, r.message) == ("agent-free", "1 step asks a model on the local route and has no scaffold, the "
                                                  "first expand f to 300 words (line 6); agent-free is on")


def test_an_if_takes_one_branch_and_skips_the_other(root):
    expanded = " ".join(["word"] * 250) + "\n\n*expanded from the atem*\n"
    cp = FakeCoprocessor({"atem": {"line": "One line.", "focus": "f", "push": "p", "pull": "q"}, "expand": expanded})
    t = RUN.run(load("expected/read-my-way/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                program=SUITE / "programs" / "read-my-way.thym", moves=fake_moves(), checks=fake_checks())
    assert t.landed, t.refusal
    assert [m for m, _ in cp.calls] == ["atem", "expand"]
    engines = {r["id"]: r["engine"] for r in t.records}
    assert engines["R:record/5"] == "skipped" and engines["R:record/4"] == "model:fake-1"
    assert t.outputs["r"].read_text(encoding="utf-8") == expanded
    assert lint_errors(t.path) == []


def test_the_length_check_holds_an_expansion_to_its_words(root):
    cp = FakeCoprocessor({"atem": {"line": "One line."}, "expand": "Too short.\n"})
    t = RUN.run(load("expected/read-my-way/plan.cosm"), inputs_root=SUITE, root=root, coprocessor=cp,
                program=SUITE / "programs" / "read-my-way.thym", moves=fake_moves(), checks=fake_checks())
    assert t.outcome == "refused" and t.refusal.check == "length"
    assert "fewer than 80 per hundred of 300" in t.refusal.message


STORY_IN_BRIEF = """thym 0

program story-in-brief
  why: a story, told plainly and then cut to a paragraph, for a listing.

  takes story: text
  gives brief: short

  move plain-paragraph(f: fabula): short
    let plain = tell f as told
    assert f covers plain else "the telling lost part of the fabula"
    give cut plain to 120 words
  end

  let f = derive story
  give plain-paragraph f
end
"""


def brief_move_plan() -> dict:
    return hand_plan(node(1, "derive story", "derive", asks=True, takes=["story"], gives="f", line=15),
                     node(2, "plain-paragraph f", "plain-paragraph", asks=True, takes=["f"], gives="brief",
                          after=["R:node/1"], line=16), name="story-in-brief")


def test_a_user_move_runs_its_body_with_its_asks_and_asserts(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling()})
    t = RUN.run(brief_move_plan(), inputs_root=SUITE, root=root, coprocessor=cp, program=STORY_IN_BRIEF,
                moves=fake_moves(), checks=fake_checks())
    assert t.landed, t.refusal
    assert t.outputs["brief"].read_text(encoding="utf-8") == "The orchard gave more juice this year.\n"
    rec = next(r for r in t.records if r["id"] == "R:record/2")
    assert rec["engine"] == "model:fake-1" and {c["name"] for c in rec["checks"]} >= {"coverage", "whole-sentences"}
    assert (t.dir / "story-in-brief.thym").read_text(encoding="utf-8") == STORY_IN_BRIEF
    again = RUN.replay(t.dir, root=root, moves=fake_moves(), checks=fake_checks())
    assert again.replay["identical"], again.replay


def test_a_failed_assert_inside_a_user_move_refuses_with_its_message(root):
    cp = FakeCoprocessor({"derive": TWIN.read_text(encoding="utf-8"), "tell": telling()})
    # coverage holds as every move's contract check (a declaration is given) and fails as the assert's `covers`
    ck = fake_checks(coverage=lambda out, inputs, node, decl, ctx: (decl is not None, "sentence 2 traces to no item"))
    t = RUN.run(brief_move_plan(), inputs_root=SUITE, root=root, coprocessor=cp, program=STORY_IN_BRIEF,
                moves=fake_moves(), checks=ck)
    assert t.outcome == "refused" and t.stopped_at == "R:record/2"
    assert (t.refusal.stage, t.refusal.check, t.refusal.line) == ("run", "coverage", 16)
    assert t.refusal.message == ("give plain-paragraph f (line 16): the telling lost part of the fabula (sentence 2 "
                                 "traces to no item)")
    assert not (t.dir / "outputs").exists()


def test_rules_looks_inside_a_user_move_for_scaffolds(root):
    mv = fake_moves()
    r = RUN.run(brief_move_plan(), inputs_root=SUITE, root=root, rules=True, program=STORY_IN_BRIEF, moves=mv,
                checks=fake_checks())
    assert isinstance(r, Refusal) and (r.stage, r.check, r.line) == ("plan", "move", 16)
    assert "scaffold of tell (outline)" in r.message
    mv.add("outline", lambda ctx, f, **m: Value("short", telling()))          # registered under the scaffold's name
    t = RUN.run(brief_move_plan(), inputs_root=SUITE, root=root, rules=True, program=STORY_IN_BRIEF, moves=mv,
                checks=fake_checks())
    assert t.landed, t.refusal
    assert [r["engine"] for r in t.records] == ["rules", "rules"]
    assert t.values["brief"].made["move"] == "cut"       # cut is deterministic; the telling under it was the scaffold's
    assert t.values["brief"].state == "pending"          # and what is made from a pending value is pending too


# ---------------------------------------------------------------------------
# Values, digests and the engine-free checks
# ---------------------------------------------------------------------------

def test_digests_follow_section_12_6(tmp_path):
    assert Value("text", "é\n").sha256 == hashlib.sha256("é\n".encode("utf-8")).hexdigest()
    m = {"oes": "thym/1", "kind": "context", "id": "thym/x", "nodes": []}
    assert Value("context", m).sha256 == hashlib.sha256(mc.dump(m).encode("utf-8")).hexdigest()
    pkg = SUITE / "inputs" / "orchard-notes.thym"
    assert digest_path(pkg) == hashlib.sha256((pkg / "package.cosm").read_bytes()).hexdigest()
    meadow = SUITE.parent / "cosm" / "holotypes" / "meadow"
    assert digest_path(meadow) == load("expected/open-house/plan.cosm")["inputs"][0]["sha256"]
    v = load_input({"name": "p", "type": "package", "path": "inputs/orchard-notes.thym"}, SUITE)
    assert v.type == "package" and v.sha256 == digest_path(pkg) and v.made == {"move": "none"}
    assert NOTHING.sha256 == hashlib.sha256(b"").hexdigest()


def test_the_engine_free_checks():
    def ok(name, out, inputs=None, node=None, ctx=None):
        return C.verdict(name, out, inputs or {}, node or {}, None, ctx)
    iso = Value("volume", {"isotype": "comprise-isotype/0", "identity": {"name": "M", "founded": 2019},
                           "shape": {"employees": "some"}})
    assert ok("default-deny", iso) == (True, "") and ok("no-counts", iso) == (True, "")
    assert ok("default-deny", Value("volume", {"isotype": "x", "staff": 3}))[0] is False
    assert ok("no-counts", Value("volume", {"shape": {"employees": 3}})) == (False,
                                                                            "shape.employees holds the number 3")
    short = Value("short", "One. Two is here. Three!\n\n*footer*\n")
    assert ok("whole-sentences", Value("short", "One. Three!\n"), {"s": short}) == (True, "")
    assert ok("whole-sentences", Value("short", "One. Four.\n"), {"s": short})[0] is False
    morph = Value("morph", {"nodes": [{"id": "M:morph/x", "scales": {"register": 1, "humour": {"pending": "q"}}}]})
    assert ok("scale-range", morph)[0] is True
    assert ok("scale-range", Value("morph", {"scales": {"register": 6}}))[0] is False
    reading = Value("short", "---\nread_through: plain-letter\n---\nText.\n\n*a reading of notes.md through plain-letter, made here on 2026-11-01 by g40-04; the text stands unchanged*\n")
    assert ok("labelled", reading) == (True, "") and ok("labelled", Value("short", "Text.\n"))[0] is False
    assert ok("provenance", Value("short", "x", made={"move": "tell", "run": "r", "step": 1}))[0] is True
    assert ok("provenance", Value("short", "x"))[0] is False
    pkg = read_value(SUITE / "inputs" / "orchard-notes.thym", "package")
    assert ok("digests", pkg) == (True, "")
    twin = read_value(TWIN, "fabula")
    assert ok("emf-checks", twin) == (True, "")

    class Ctx:
        withheld = {"C:entity/meadow-software-inc": NOTHING}
    assert ok("no-mark", Value("volume", {"offers": [{"name": "x"}]}), ctx=Ctx())[0] is True
    assert ok("no-mark", Value("volume", {"offers": [{"name": "[withheld]"}]}), ctx=Ctx())[0] is False
    assert ok("no-mark", Value("volume", {"note": "C:entity/meadow-software-inc"}), ctx=Ctx())[0] is False
    assert isinstance(C.verdict("nonesuch", short, {}, {}, None), Refusal)


# ---------------------------------------------------------------------------
# The host: the model coprocessor, the root
# ---------------------------------------------------------------------------

def test_model_coprocessor_over_a_fake_complete():
    from enough import thym_host
    seen = []

    def fake(messages, max_tokens=None):
        seen.append(messages)
        return "```yaml\nnodes:\n  - {id: K:claim/a, stance: Observation, span: {lines: '1'}}\n" \
               "  - {id: K:claim/b, stance: opinion, span: {lines: '90-91'}}\n```", {"model": "m1"}

    mc_ = thym_host.ModelCoprocessor(fake)
    story = Value("text", "one line\n")
    contract = {"move": "derive", "schema": {"format": "yaml"}, "checks": ["coverage"],
                "repair": {"allowed": ["normalise-stance", "drop-unresolved-spans"],
                           "failed": [{"name": "coverage", "ok": False, "why": "line 1 is not covered"}]}}
    cand = mc_.complete(contract, {"story": (story, story.sha256)}, budget={"attempts": 3, "output_words": 0,
                                                                           "prompt_tokens_max": 0, "seconds": 60})
    assert cand["engine"] == "model:m1" and cand["attempts"] == 1 and cand["tokens"] > 0
    assert cand["output"]["nodes"] == [{"id": "K:claim/a", "stance": "observed", "span": {"lines": "1"}}]
    assert "coverage: line 1 is not covered" in seen[0][-1]["content"]
    md = thym_host.ModelCoprocessor(lambda m: ("```markdown\nA telling.\n```", {}))
    out = md.complete({"move": "tell", "schema": {"format": "markdown"}, "checks": [], "repair": {}}, {},
                      budget={"attempts": 1, "output_words": 0, "prompt_tokens_max": 0, "seconds": 1})
    assert out["output"] == "A telling.\n" and out["engine"] == "model:unknown"

    def broken(messages):
        raise RuntimeError("no model")
    r = thym_host.ModelCoprocessor(broken).complete(contract, {}, budget={})
    assert isinstance(r, Refusal) and r.check == "coprocessor"


def test_host_root_and_coprocessor_choice(monkeypatch, tmp_path):
    from enough import thym_host
    from enough.thym.coprocessor import RefusingCoprocessor
    monkeypatch.setenv("ENOUGH_THYM_ROOT", str(tmp_path / "t"))
    root = thym_host.host_root()
    assert root == tmp_path / "t" and (root / "runs").is_dir() is False   # nothing is made until a run writes
    assert isinstance(thym_host.host_coprocessor(True, rules=False), RefusingCoprocessor)
    assert isinstance(thym_host.host_coprocessor(False, rules=True), RefusingCoprocessor)
    assert isinstance(thym_host.host_coprocessor(False, rules=False, complete=lambda m: ""),
                      thym_host.ModelCoprocessor)
    kw = thym_host.runtime_kwargs()
    assert kw["agent_free"] is False and kw["root"] == root and kw["environment"]["enough"]


def test_the_runtime_imports_only_what_it_may():
    import ast
    for p in sorted((REPO / "enough" / "thym").glob("*.py")):
        if p.name not in ("values.py", "registry.py", "checks.py", "coprocessor.py", "run.py", "trace.py",
                          "conform.py", "cli.py", "__main__.py", "engines.py", "vault.py"):
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("enough"):
                assert n.module == "enough" and all(a.name == "macrocosm" for a in n.names) \
                    or n.module.startswith("enough.thym"), (p.name, n.module)
            if isinstance(n, ast.Import):
                allowed = ("enough.thym", "enough.macrocosm")
                assert not any(a.name.startswith("enough") and not a.name.startswith(allowed) for a in n.names), p.name


# ---------------------------------------------------------------------------
# The command line and the suite
# ---------------------------------------------------------------------------

def test_cli_runs_a_plan_in_the_thym_root(monkeypatch, capsys, tmp_path):
    import os
    root = Path(os.environ["ENOUGH_THYM_ROOT"])
    assert str(root).startswith(str(tmp_path.parent)) or "thym" in root.name     # conftest moved it into tmp
    monkeypatch.setattr(R, "MOVES", fake_moves())
    monkeypatch.setattr(C, "CHECKS", fake_checks())
    from enough import thym_host

    def no_model(url):
        raise AssertionError("a run that asks no model never asks a model's size (THYM.md 12.3)")
    monkeypatch.setattr(thym_host, "_read_n_ctx", no_model)
    code = cli.main(["run", str(SUITE / "expected" / "open-house" / "plan.cosm"),
                     "--program", str(SUITE / "expected" / "open-house" / "items.cosm"), "--inputs-root", str(SUITE)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "all checks green" in out
    runs = sorted((root / "runs").iterdir())
    assert len(runs) == 1 and (runs[0] / "outputs" / "i.cosm").is_file()
    assert cli.main(["trace", runs[0].name]) == 0
    assert "R:record/7" in capsys.readouterr().out
    assert cli.main(["trace", "no-such-run"]) == 2
    assert "refused at run (trace)" in capsys.readouterr().out


def test_cli_check_and_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
    assert "conform" in capsys.readouterr().out


def test_conform_reports_the_suite(tmp_path):
    rep = conform.conform(SUITE, root=tmp_path / "conform-root")
    assert rep.lines and rep.summary().startswith("conform: ")
    compiler_mods, _ = conform.compiler()
    if len(compiler_mods) < 4:
        assert any("the compiler is not here yet" in s for s in rep.skipped)
    assert rep.ok, "\n".join(rep.failed)
