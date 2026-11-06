"""Contract blocks, `keeps`, and recursion under `depth:` (THYM 7.5, 8.3, 9, 10, 11.1, 12.2; design 2c, 2d).

A contract block is a check a program defines; a move or a program `keeps` it (or a named check) for its output. At
run a kept contract's lines run on the value given; a failed one re-asks the model within the node's attempts when the
move asks, every request of the re-run carrying the failed verdicts in `repair.failed`, and refuses with the
contract's own words after the last; a move that does not ask is refused at once; a program's kept contracts are
checked before anything lands. A move may call itself only under `depth:` (every move on its cycle), and the run
counts it. Scripted coprocessors stand in for a model; runs land under tmp_path (the conftest's seams).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from enough import thym
from enough import thym_host as H
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import checks as C
from enough.thym import enumerate as en
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import candidate
from enough.thym.registry import Request
from enough.thym.values import digest_path

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
NOTES = SUITE / "inputs" / "notes.md"
TWIN = SUITE / "inputs" / "notes.md.cosm"
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
FORBIDDEN = re.compile(r"\bt\d+\b|\bnode \d+\b|R:node/|Error\b|Exception\b")


def compile_text(text: str, path: str | None = None):
    m = ps.parse(text, path=path)
    return m if isinstance(m, Refusal) else ck.check(m)


def ok(text: str, path: str | None = None) -> ck.Checked:
    c = compile_text(text, path)
    assert not isinstance(c, Refusal), str(c)
    return c


def refused(text: str) -> Refusal:
    r = compile_text(text)
    assert isinstance(r, Refusal), "compiled, and it must be refused"
    return r


SHORTER = 'contract shorter(new: short, old: short)\n  why: says less.\n\n  assert words new < words old else "not shorter"\nend\n\n'


def prog(body: str, *, contracts: str = SHORTER, head: str = "", takes: str = "s: short", gives: str = "t: short",
         give: str = "give s", version: int = 1) -> str:
    return (f"thym {version}\n\n{contracts}program p\n  why: a test.\n  takes {takes}\n  gives {gives}\n{head}\n"
            f"{body}  {give}\nend\n")


# ---------------------------------------------------------------------------
# Contract blocks and keeps: compile
# ---------------------------------------------------------------------------

def test_a_contract_block_and_what_keeps_it_compile_and_enumerate():
    move = "  move tightened(l: short): short\n    keeps shorter against l\n    give cut l to 10 words\n  end\n"
    text = prog(move, head="  keeps shorter against s", give="give tightened s")
    c = ok(text)
    assert set(c.contracts) == {"shorter"} and c.module.features[0] == (3, "a contract block (contract shorter)")
    mv = c.local["p"]["tightened"]
    assert mv.keeps == ["shorter"] and mv.checks[-1] == "shorter"           # kept, after the inherited
    vol = en.enumerate_checked(c)
    items = {it["id"]: it for it in vol["nodes"]}
    chk = items["P:check/shorter"]
    assert (chk["type"], chk["order"], chk["lines"]) == ("check", 1, "3-7")
    assert chk["params"] == [{"name": "new", "type": "short"}, {"name": "old", "type": "short"}]
    assert chk["steps"] == ["P:step/shorter.1"] and items["P:step/shorter.1"]["form"] == "assert"
    assert items["P:program/p"]["keeps"] == ["shorter"] and items["P:move/p.tightened"]["keeps"] == ["shorter"]
    give = next(it for it in vol["nodes"] if it.get("type") == "contract" and it["move"] == "tightened")
    assert give["checks"][-1] == "shorter"
    assert en.compile_volume(vol) == text


def test_a_local_contract_block_is_p_check_of_its_program():
    local = 'program q\n  why: x.\n  takes s: short\n  gives t: short\n  keeps short-one\n\n  contract short-one(x: short)\n    assert words x < 5\n  end\n\n  give s\nend\n'
    c = ok("thym 1\n\n" + local)
    ids = [it["id"] for it in en.enumerate_checked(c)["nodes"]]
    assert "P:check/q.short-one" in ids and "P:step/q.short-one.1" in ids


@pytest.mark.parametrize("text, check, line, words", [
    (prog("", head="  keeps shorten against s"), "unknown-check", 13,
     "keeps shorten against s: no contract block and no named check is called so; did you mean shorter?"),
    (prog("", head="  keeps shorter"), "type", 13,
     "keeps shorter: shorter takes new: short, old: short, and it is given 1 value"),
    (prog("", head="  keeps shorter against s", gives="n: number", give="give words s"), "type", 13,
     "keeps shorter against s: shorter takes new: short, old: short, and p gives a number"),
    (prog("", head="  keeps shorter against q"), "unbound", 13,
     "keeps shorter against q: q is not one of the inputs of program p"),
    (prog("", head="  keeps shorter against s", gives="t: short, u: short", give="give t: s\n  give u: s"), "type",
     13, "program p gives t and u; keeps says which: keeps shorter of t"),
    (prog("", contracts='contract coverage(x: short)\n  assert words x > 0\nend\n\n'), "type", 3,
     "contract coverage has the name of a standard check; name it otherwise"),
    (prog("", contracts='contract c(x: short)\n  emit x\nend\n\n'), "type", 4,
     "a contract holds let, assert and for each lines; line 4 is an emit"),
    (prog("", contracts='contract c(x: short)\n  assert (words (atem x)) > 0\nend\n\n', head="  keeps c"), "type", 4,
     "contract c asks the model at line 4 (atem); a contract checks, and never asks"),
    ("thym 1\n\nprogram p\n  why: emits.\n  takes h: volume\n  keeps provenance\n\n  lint h\nend\n", "type", 6,
     "program p gives nothing, so it keeps nothing"),
])
def test_the_static_rules_of_keeps_and_contract_blocks(text, check, line, words):
    r = refused(text)
    assert (r.check, r.line, r.message) == (check, line, words)


def test_keeps_of_a_named_check_and_of_one_output():
    ok(prog("", head="  keeps provenance"))
    ok(prog("", head="  keeps shorter of u against s", gives="t: short, u: short", give="give t: s\n  give u: s"))


def test_a_contract_a_used_file_declares_can_be_kept(tmp_path):
    (tmp_path / "lib.thym").write_text(
        "thym 1\n\ncontract shorter(new: short, old: short)\n  assert words new < words old\nend\n", encoding="utf-8")
    text = "thym 1\nuse lib.thym\n\n" + prog("", contracts="", head="  keeps shorter against s").split("\n\n", 1)[1]
    (tmp_path / "p.thym").write_text(text, encoding="utf-8")
    ok(text, str(tmp_path / "p.thym"))


def test_contract_blocks_and_keeps_need_thym_1():
    r = refused(prog("", head="  keeps shorter against s", version=0))
    assert (r.check, r.line) == ("version", 3) and "a contract block (contract shorter)" in r.message
    r = refused(prog("", contracts="", head="  keeps provenance", version=0))
    assert r.check == "version" and r.message.startswith("this needs `thym 1`: a keeps line at line 7")


# ---------------------------------------------------------------------------
# Kept contracts at run
# ---------------------------------------------------------------------------

BRIEF = """thym 1

contract brief(s: short)
  why: a telling of a dozen words or fewer.

  assert words s < 13 else "the telling runs past twelve words"
end

program told-briefly
  why: a fabula told briefly, asked again until it is brief.

  takes f: fabula
  gives s: short

  move briefly(x: fabula): short
    keeps brief
    give tell x as told
  end

  give briefly f
end
"""
LONG = "The orchard gave more juice this year than in any year that the people of the valley remember.\n"
SHORT = "The orchard gave more juice.\n"


class Scripted:
    def __init__(self, answers: list[str]) -> None:
        self.answers, self.sent = list(answers), []

    def complete(self, contract, inputs, *, budget):
        self.sent.append(contract)
        return candidate(self.answers.pop(0), engine="model:scripted-1", tokens=5)


def tell_moves() -> R.Moves:
    mv = R.MOVES.copy()
    R.load_all(R.declarations(), moves=mv)
    mv.add("tell", lambda ctx, *ops, **m: Request(contract={"schema": {"format": "markdown"}},
                                                  inputs={f"in{k}": v for k, v in enumerate(ops)}))
    return mv


def easy_checks(**override) -> C.Checks:
    out = C.CHECKS.copy()
    for name in ("coverage", "no-invention", "stance-kept", "scales-met", "footer"):
        out.add(name, lambda *a: (True, ""))
    for name, fn in override.items():
        out.add(name, fn)
    return out


def brief_run(tmp_path: Path, answers: list[str], **kw):
    p = tmp_path / "told-briefly.thym"
    p.write_text(BRIEF, encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}])
    assert not isinstance(plan, Refusal), plan
    node = RUN.plan_parts(plan)[1][0]
    assert (node["keeps"], node["budget"]["attempts"]) == (["brief"], 3)
    cp = Scripted(answers)
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, coprocessor=cp, moves=tell_moves(),
                checks=easy_checks(), engines=H.engines(feed=None), now=NOW, **kw)
    return t, cp


def test_a_failed_kept_contract_re_asks_and_what_failed_reaches_the_model(tmp_path):
    t, cp = brief_run(tmp_path, [LONG, SHORT])
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    assert t.outputs["s"].read_text(encoding="utf-8").startswith("The orchard gave more juice.")
    assert cp.sent[0]["repair"]["failed"] == []
    assert cp.sent[1]["repair"]["failed"] == [{"name": "brief", "ok": False,
                                               "why": "the telling runs past twelve words"}]
    rec = t.records[0]
    assert rec["tries"] == [{"attempt": 1, "failed": [{"name": "brief", "why": "the telling runs past twelve words"}]}]
    assert {"name": "brief", "ok": True, "why": ""} in rec["checks"]
    keys = sorted(x.name for x in (t.dir / "candidates").glob("*.cosm"))
    assert keys == ["1-1.1.cosm", "1.1.cosm"]                                # the re-run's call keeps counting
    again = RUN.replay(t.dir, root=tmp_path / "root", moves=tell_moves(), checks=easy_checks(),
                       engines=H.engines(feed=None))
    assert again.replay["identical"], again.replay


def test_every_attempt_failing_refuses_in_the_contracts_own_words(tmp_path):
    t, cp = brief_run(tmp_path, [LONG, LONG, LONG])
    assert isinstance(t, T.Trace) and not t.landed and len(cp.sent) == 3
    r = t.refusal
    assert (r.check, r.line) == ("brief", 20) and not FORBIDDEN.search(r.message)
    assert r.message == ("give briefly f (line 20): briefly still fails brief after 3 attempts: the telling runs past "
                         "twelve words")
    assert [x["attempt"] for x in t.records[0]["tries"]] == [1, 2, 3]
    assert not (t.dir / "outputs").exists()


def test_a_deterministic_move_that_fails_its_contract_is_refused_at_once(tmp_path):
    text = prog("  move same(x: short): short\n    keeps shorter against x\n    give x\n  end\n", give="give same s")
    p = tmp_path / "p.thym"
    p.write_text(text, encoding="utf-8")
    note = tmp_path / "s.md"
    note.write_text("Some words here.\n", encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "s", "type": "short", "path": str(note), "sha256": digest_path(note)}])
    t = RUN.run(plan, inputs_root=tmp_path, root=tmp_path / "root", program=p, engines=H.engines(feed=None), now=NOW)
    assert not t.landed and (t.refusal.check, t.refusal.message) == ("shorter", "give same s (line 18): same fails "
                                                                                 "shorter: not shorter")
    assert len(t.records[0]["tries"]) == 1


def test_a_program_that_keeps_is_checked_before_anything_lands(tmp_path):
    text = prog("", contracts="", head="  keeps labelled", takes="t: text", gives="n: number", give="give words t")
    p = tmp_path / "p.thym"
    p.write_text(text, encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}])
    assert RUN.plan_parts(plan)[1][0]["keeps"] == ["labelled"]
    fails = easy_checks(labelled=lambda *a: (False, "it carries no label"))
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, checks=fails,
                engines=H.engines(feed=None), now=NOW)
    assert not t.landed and not (t.dir / "outputs").exists()
    assert (t.refusal.check, t.refusal.message) == ("labelled", "program p gives n, and it fails labelled: it carries "
                                                                "no label; nothing landed")
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, checks=easy_checks(
        labelled=lambda *a: (True, "")), engines=H.engines(feed=None), now=NOW)
    assert t.landed and {"name": "labelled", "ok": True, "why": ""} in t.records[-1]["checks"]


# ---------------------------------------------------------------------------
# Recursion under depth:
# ---------------------------------------------------------------------------

AGAIN = """thym 1

program again-and-again
  why: a move that calls itself, as deep as its argument says.

  takes t: text
  gives n: number

  move again(x: text, more: bool): number
    depth: {d}
    if more then
      give again x, false
    else
      give words x
    end
  end

  give again t, true
end
"""


@pytest.mark.parametrize("d, landed", [(2, True), (1, False)])
def test_the_run_counts_a_move_against_its_depth(tmp_path, d, landed):
    p = tmp_path / "p.thym"
    p.write_text(AGAIN.format(d=d), encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}])
    node = RUN.plan_parts(plan)[1][0]
    assert node["budget"] == {"attempts": 1, "output_words": 0, "depth": d}
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, engines=H.engines(feed=None), now=NOW)
    assert t.landed is landed
    if not landed:
        assert (t.refusal.check, t.refusal.line) == ("recursion", 18)
        assert t.refusal.message == "give again t, true (line 18): again went 2 deep; its depth is 1"


@pytest.mark.parametrize("moves, check, line, words", [
    ("  move a(x: text): number\n    depth: 3\n    give b x\n  end\n  move b(x: text): number\n    give a x\n  end\n",
     "recursion", 10, "move b calls itself through a → b → a; a move that calls itself says how deep it may go: add "
                      "`depth: 8` under its why"),
    ("  move a(x: text): number\n    depth: 0\n    give a x\n  end\n", "type", 7, "depth is a number from 1 to 64"),
    ("  move a(x: text): number\n    depth: 65\n    give a x\n  end\n", "type", 7, "depth is a number from 1 to 64"),
    ("  depth: 3\n", "type", 6, "program p is never called, so it says no depth: a depth: line stands in a move that "
                                "calls itself"),
])
def test_the_static_rules_of_depth(moves, check, line, words):
    text = f"thym 1\n\nprogram p\n  takes t: text\n  gives n: number\n{moves}\n  give 0\nend\n"
    r = refused(text)
    assert (r.check, r.line, r.message) == (check, line, words)


def test_a_cycle_of_moves_shares_its_calls_and_checks_and_plans_finitely():
    text = ("thym 1\n\nprogram p\n  takes t: text\n  gives n: number\n"
            "  move a(x: short): number\n    depth: 3\n    if words x > 5 then\n      give b x\n    else\n"
            "      give count [x]\n    end\n  end\n"
            "  move b(x: short): number\n    depth: 2\n    assert (words (atem x)) > 0\n"
            "    give a (cut x to 5 words)\n  end\n"
            "  give a (tell (derive t) as told)\nend\n")
    c = ok(text)
    a, b = c.local["p"]["a"], c.local["p"]["b"]
    assert a.calls == b.calls and a.checks == b.checks and a.asks and b.asks
    assert ("a move that calls itself (move a)") in [f[1] for f in c.module.features]
    plan = pl.plan(c, [{"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}])
    n = RUN.plan_parts(plan)[1]
    assert [x["move"] for x in n] == ["derive", "tell", "a"]
    assert n[-1]["budget"] == {"attempts": 3, "output_words": 0, "depth": 3}


def test_recursion_without_depth_keeps_thym_0s_refusal():
    r = refused((SUITE / "bad" / "recursion.thym").read_text(encoding="utf-8"))
    assert (r.check, r.line) == ("recursion", 8) and "thym 0 has no recursion" in r.message


# ---------------------------------------------------------------------------
# Hooks the move lanes build on: a ceiling on model calls, a move that asks several times, the count of calls
# ---------------------------------------------------------------------------

def test_a_run_past_its_ceiling_of_model_calls_is_refused(tmp_path):
    t, cp = brief_run(tmp_path, [LONG, SHORT], calls=1)
    assert isinstance(t, T.Trace) and not t.landed and len(cp.sent) == 1
    assert (t.refusal.check, t.refusal.message) == ("calls", "give briefly f (line 20): this run reached its ceiling "
                                                             "of 1 model call; nothing landed")


def test_a_move_that_asks_several_times_is_called_again_with_what_failed(tmp_path):
    """`ctx.ask` (the hook for `tell f as code`, one request per file): every request is keyed on the node's counter
    and recorded; a value that fails the contract calls the move again with `ctx.failed`, `ctx.previous` and
    `ctx.attempt`, within the node's attempts, and the replay meets every request in order."""
    seen: list[tuple[int, list, bool]] = []

    def tell(ctx, f, **m):
        seen.append((ctx.attempt, [x["name"] for x in ctx.failed], ctx.previous is not None))
        if ctx.previous is None:
            parts = [ctx.ask({"schema": {"format": "markdown"}}, {"f": f})["output"] for _ in range(2)]
            return thym.values.Value("short", "".join(parts))
        last = ctx.ask({"schema": {"format": "markdown"}}, {"f": f})["output"]
        return thym.values.Value("short", ctx.previous.text() + last)

    def moves() -> R.Moves:
        mv = tell_moves()
        mv.add("tell", tell)
        return mv

    footer = lambda out, *a: (out.text().rstrip().endswith("*"), "the telling has no footer line")  # noqa: E731
    p = tmp_path / "p.thym"
    p.write_text("thym 1\n\nprogram p\n  takes f: fabula\n  gives s: short\n\n  give tell f as told\nend\n",
                 encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}])
    cp = Scripted(["One part.\n", "Two parts.\n", "*a footer*\n"])
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, coprocessor=cp, moves=moves(),
                checks=easy_checks(footer=footer), engines=H.engines(feed=None), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    assert seen == [(1, [], False), (2, ["footer"], True)]
    assert [c["repair"]["failed"] for c in cp.sent] == [[], [], [{"name": "footer", "ok": False,
                                                                  "why": "the telling has no footer line"}]]
    assert sorted(x.name for x in (t.dir / "candidates").glob("*.cosm")) == ["1-1.1.cosm", "1-2.1.cosm", "1.1.cosm"]
    rec = t.records[0]
    assert (rec["engine"], rec["attempts"]) == ("model:scripted-1", 2) and [x["attempt"] for x in rec["tries"]] == [1]
    again = RUN.replay(t.dir, root=tmp_path / "root", moves=moves(), checks=easy_checks(footer=footer),
                       engines=H.engines(feed=None))
    assert again.replay["identical"], again.replay


def test_a_re_ask_carries_why_the_move_could_not_take_the_last_answer(tmp_path):
    """`ctx.ask` takes a move's own failures (lane T2, item 5; G1's note 2.4): `repair` may be the list of repairs
    allowed (as before, byte for byte: code.py's `repair: []` asks exactly what it asked), or the mapping
    `{allowed, failed}`, whose failures (a `{name, why}` or the reason as a string) follow the runtime's own, so a
    re-ask is never the same request again."""
    def tell(ctx, f, **m):
        first = ctx.ask({"schema": {"format": "markdown"}, "repair": ["drop-unresolved-refs"]}, {"f": f})["output"]
        assert first == "not it\n"
        again = ctx.ask({"schema": {"format": "markdown"},
                         "repair": {"allowed": [], "failed": [{"name": "answer", "why": "it holds no footer"}]}},
                        {"f": f})["output"]
        last = ctx.ask({"schema": {"format": "markdown"}, "repair": {"failed": ["it still holds no footer"]}},
                       {"f": f})["output"]
        return thym.values.Value("short", again + last)

    def moves() -> R.Moves:
        mv = tell_moves()
        mv.add("tell", tell)
        return mv

    p = tmp_path / "p.thym"
    p.write_text("thym 1\n\nprogram p\n  takes f: fabula\n  gives s: short\n\n  give tell f as told\nend\n",
                 encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}])
    cp = Scripted(["not it\n", "Told.\n", "*a footer*\n"])
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, coprocessor=cp, moves=moves(),
                checks=easy_checks(), engines=H.engines(feed=None), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    assert [c["repair"] for c in cp.sent] == [
        {"allowed": ["drop-unresolved-refs"], "failed": []},
        {"allowed": [], "failed": [{"name": "answer", "ok": False, "why": "it holds no footer"}]},
        {"allowed": [], "failed": [{"name": "answer", "ok": False, "why": "it still holds no footer"}]}]
    # the host's prompt says why: the second request is not the first
    msgs = [H.ModelCoprocessor(complete=lambda *a, **k: ("", {}), moves=R.Moves()).messages(c, {}) for c in cp.sent]
    assert msgs[0] != msgs[1] and "it holds no footer" in msgs[1][-1]["content"]
    assert RUN._move_repair([]) == ([], []) and RUN._move_repair(None) == ([], [])


def test_a_move_may_say_which_verdicts_its_re_ask_carries(tmp_path):
    """`replaces: true` in a move's own `repair` mapping (lane S3, item 7): its `failed` stands instead of the
    runtime's verdicts on its last output, so a part asked again hears its own fault alone; without it (a list, or a
    mapping that does not say it) the runtime's verdicts ride as before."""
    def tell(ctx, f, **m):
        if ctx.previous is None:
            return thym.values.Value("short", ctx.ask({"schema": {"format": "markdown"}}, {"f": f})["output"])
        mine = ctx.ask({"schema": {"format": "markdown"},
                        "repair": {"allowed": [], "failed": ["part 2 only"], "replaces": True}}, {"f": f})["output"]
        both = ctx.ask({"schema": {"format": "markdown"}, "repair": {"failed": ["part 2 only"]}}, {"f": f})["output"]
        return thym.values.Value("short", ctx.previous.text() + mine + both)

    def moves() -> R.Moves:
        mv = tell_moves()
        mv.add("tell", tell)
        return mv

    footer = lambda out, *a: (out.text().rstrip().endswith("*"), "the telling has no footer line")  # noqa: E731
    p = tmp_path / "p.thym"
    p.write_text("thym 1\n\nprogram p\n  takes f: fabula\n  gives s: short\n\n  give tell f as told\nend\n",
                 encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}])
    cp = Scripted(["One part.\n", "Two.\n", "*a footer*\n"])
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, coprocessor=cp, moves=moves(),
                checks=easy_checks(footer=footer), engines=H.engines(feed=None), now=NOW)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    footer_failed = {"name": "footer", "ok": False, "why": "the telling has no footer line"}
    own = {"name": "answer", "ok": False, "why": "part 2 only"}
    assert [c["repair"] for c in cp.sent] == [
        {"allowed": [], "failed": []},
        {"allowed": [], "failed": [own]},                     # replaces: the move's own alone
        {"allowed": [], "failed": [footer_failed, own]}]      # as before: the runtime's, then the move's
    assert all("replaces" not in c["repair"] for c in cp.sent)
    assert RUN._move_replaces({"replaces": True}) and not RUN._move_replaces({"replaces": "yes"})
    assert not RUN._move_replaces([]) and not RUN._move_replaces(None)


def test_the_plan_counts_its_model_calls_for_the_route_it_is_given():
    c = ok(BRIEF)
    rows = [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}]
    plan = pl.plan(c, rows, models={"route": "local", "model": "g40-04", "window": 16384})
    assert plan["models"] == {"route": "local", "model": "g40-04", "calls": 1, "at_most": 3, "calls_open": [],
                              "window": 16384}
    assert "models" not in pl.normalise(plan) and "models" not in pl.plan(c, rows)
    text = BRIEF.replace("  give briefly f\n", "  let ts = for each x in [f, f, f]\n    keep briefly x\n  end\n"
                         "  give cut (tell f as told) to 10 words\n")
    plan = pl.plan(ok(text), rows, models={"route": "cloud"})
    assert plan["models"] == {"route": "cloud", "calls": 4, "at_most": 12, "calls_open": []}
    plan = pl.plan(ok(AGAIN.format(d=2).replace("give words x", "give words (tell (derive x) as told)")),
                   [{"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}],
                   models={"route": "cloud"})
    assert plan["models"]["calls_open"] == ["R:node/1"]                 # a move that calls itself and asks


def test_agent_free_refuses_a_loop_node_that_asks_at_plan_time(tmp_path):
    p = tmp_path / "p.thym"
    p.write_text(prog("  let ts = for each x in [f, f]\n    keep tell x as told\n  end\n", contracts="",
                      takes="f: fabula", gives="n: number", give="give count ts"), encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)}])
    r = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, agent_free=True,
                engines=H.engines(feed=None), now=NOW)
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "agent-free")
    assert r.message == ("1 step asks a model on the local route, the first `let ts = for each x in [f, f]` "
                         "(line 8); agent-free is on")
