"""The loop fold, in both grammar versions, and refusals in the person's words (THYM 8.1, 9, 11.1; design 2g, 2h).

A call nested inside a statement of a `for each` body is part of that statement's node and runs with each member:
over a collection known only at run time (survey 2.3.1) and over a list written in the program (survey 2.3.2), whose
node binds the loop variable to its member (`, for x = <member>`). Outside a loop's body nothing changes. The two
`thym 0` loops that still run wrong (an `if` in a run-time loop, a `let` in one read in the same loop) are refused
at run with the fix, write `thym 1`. No refusal shows a temporary, a node's number or id, or an exception's name.
Runs land under tmp_path; the conftest's seams keep everything away from ~/enough.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import thym
from enough import thym_host as H
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.values import Value, digest_path

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
MEADOW = SUITE.parent / "cosm" / "holotypes" / "meadow"
NOTES = SUITE / "inputs" / "notes.md"
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
#: what a refusal may never show (THYM 9; design 2h)
FORBIDDEN = re.compile(r"\bt\d+\b|\bnode \d+\b|R:node/|Error\b|Exception\b")


def _said(r: Refusal) -> Refusal:
    """A refusal these tests met: it speaks in the person's words (the sweep, design 2h), whatever else is asked."""
    assert isinstance(r, Refusal), r
    assert not FORBIDDEN.search(r.message), r.message
    return r


def _compile(text: str, path: Path | None = None):
    m = ps.parse(text, path=str(path) if path else None)
    return m if isinstance(m, Refusal) else ck.check(m)


def _program(tmp_path: Path, version: int, takes: str, body: str, gives: str = "n: number",
             give: str = "give words t") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "p.thym"
    p.write_text(f"thym {version}\n\nprogram p\n  takes {takes}\n  gives {gives}\n\n{body}  {give}\nend\n",
                 encoding="utf-8")
    return p


def _inputs(takes: str) -> list[dict]:
    if takes.startswith("h"):
        return [{"name": "h", "type": "volume", "path": str(MEADOW), "sha256": digest_path(MEADOW)}]
    return [{"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}]


def _plan(prog: Path, takes: str) -> dict:
    p = thym.plan_file(prog, _inputs(takes))
    assert not isinstance(p, Refusal), p
    return p


def _run(prog: Path, takes: str, plan: dict | None = None, **kw):
    plan = plan or _plan(prog, takes)
    kw.setdefault("program", prog)
    return RUN.run(plan, inputs_root=SUITE, root=prog.parent / "root", engines=H.engines(feed=None), now=NOW, **kw)


def _nodes(plan: dict) -> list[dict]:
    return RUN.plan_parts(plan)[1]


# ---------------------------------------------------------------------------
# The fold, over a collection known only at run time (survey 2.3.1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version", [0, 1])
def test_a_nested_call_in_a_run_time_loop_is_one_node_and_lands(tmp_path, version):
    body = "  for each o in h where kind is service\n    emit mark (mark o as stated) as verified\n  end\n"
    prog = _program(tmp_path, version, "h: volume", body, "i: volume", "give project h as isotype")
    plan = _plan(prog, "h")
    nodes = _nodes(plan)
    assert [n["name"] for n in nodes] == [
        "emit mark (mark o as stated) as verified, for each o in h where kind is service", "project h as isotype"]
    assert (nodes[0]["move"], nodes[0]["takes"], nodes[0]["repeats"]) == ("mark", ["h"], True)
    assert "gives" not in nodes[0]                     # no temporary
    t = _run(prog, "h", plan)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    offers = mc.yaml_load((t.dir / "outputs" / "i.cosm").read_text(encoding="utf-8")).get("offers")
    assert offers, "every service is emitted, each marked"


@pytest.mark.parametrize("version", [0, 1])
def test_the_surveys_band_of_words_runs_with_each_member(tmp_path, version):
    """Survey 2.3.1's probe: `assert (band (words x) as [none, some]) is some` over a list known only at run time.
    Before the fold: `band raised MoveError: band takes a number, not a list`."""
    body = ("  let ts = [t, t]\n  for each x in ts\n    assert (band (words x) as [none, some]) is some\n  end\n")
    prog = _program(tmp_path, version, "t: text", body)
    plan = _plan(prog, "t")
    names = [n["name"] for n in _nodes(plan)]
    assert names[0] == "assert (band (words x) as [none, some]) is some, for each x in ts"
    assert _nodes(plan)[0]["takes"] == ["t"]
    t = _run(prog, "t", plan)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    rec = next(r for r in t.records if r["id"] == "R:record/1")
    assert [c["ok"] for c in rec["checks"] if c["name"] == "assert"] == [True, True]     # once per member


def test_an_assert_in_a_run_time_loop_runs_for_each_member_and_names_the_pass(tmp_path):
    body = "  let ts = [t, t]\n  for each x in ts\n    assert (words x) > 100000\n  end\n"
    prog = _program(tmp_path, 0, "t: text", body)
    t = _run(prog, "t")
    assert isinstance(t, T.Trace) and not t.landed
    r = _said(t.refusal)
    words = len(NOTES.read_text(encoding="utf-8").split())
    assert (r.check, r.line) == ("assert", 9)
    assert r.message.startswith("assert (words x) > 100000 (line 9, for x = the first member): "
                                "(words x) > 100000 does not hold; (words x) is ")
    assert int(r.message.rsplit(" ", 1)[1]) in range(words - 50, words + 50)


# ---------------------------------------------------------------------------
# The fold, over a list written in the program (survey 2.3.2)
# ---------------------------------------------------------------------------

def test_a_written_list_loop_binds_its_member_in_thym_0(tmp_path):
    """Survey 2.3.2: `for each x in [t, t]` / `assert (words x) > 0`. Before: `node 1 (words x, for x = t): unexpected
    'x'`. Each member's node binds x to the member, and the nested call is part of the node."""
    body = "  for each x in [t, t]\n    assert (words x) > 0\n  end\n"
    prog = _program(tmp_path, 0, "t: text", body)
    plan = _plan(prog, "t")
    nodes = _nodes(plan)
    assert [n["name"] for n in nodes[:2]] == ["assert (words x) > 0, for x = t"] * 2
    assert all(n["takes"] == ["t"] and not n.get("repeats") for n in nodes[:2])
    t = _run(prog, "t", plan)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)


def test_a_written_list_loop_with_a_call_in_a_condition_without_parentheses_in_thym_1(tmp_path):
    body = "  for each x in [t, t]\n    assert words x > 0\n  end\n"
    prog = _program(tmp_path, 1, "t: text", body)
    plan = _plan(prog, "t")
    assert [n["name"] for n in _nodes(plan)[:2]] == ["assert words x > 0, for x = t"] * 2
    t = _run(prog, "t", plan)
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    zero = _program(tmp_path / "zero", 0, "t: text", body)
    r = _said(thym.check_file(zero))
    assert isinstance(r, Refusal) and (r.check, r.line) == ("version", 8)
    assert r.message == ("this needs `thym 1`: a call in a condition without parentheses (words x) at line 8; the "
                         "first line says thym 0")


def test_a_written_list_member_that_fails_is_named_by_its_place(tmp_path):
    body = "  for each x in [t, t]\n    assert (words x) > 100000\n  end\n"
    t = _run(_program(tmp_path, 0, "t: text", body), "t")
    r = _said(t.refusal)
    assert r.message.startswith("assert (words x) > 100000 (line 8, for x = the first member): ")


def test_outside_a_loop_nested_calls_are_still_their_own_nodes():
    """open-house's `emit employees: band (count staff) as [none, some] marked verified` is still four nodes with
    t3 and t4: the fold is for a loop's body only (and conformance holds every frozen plan)."""
    checked = thym.check_file(SUITE / "programs" / "open-house.thym")
    names = [n.name for n in pl.build(checked)]
    assert names[2:5] == ["count staff", "band t3 as [none, some]", "emit employees: mark t4 as verified"]


def test_a_plain_statement_in_a_loop_is_planned_as_it_always_was():
    checked = thym.check_file(SUITE / "programs" / "open-house.thym")
    first, second = pl.build(checked)[:2]
    assert not first.folded and not second.folded
    assert second.name == "emit mark a as stated, for each a in h where kind is aim"


# ---------------------------------------------------------------------------
# The two thym 0 loops that still run wrong, refused with the fix
# ---------------------------------------------------------------------------

def test_an_if_inside_a_run_time_loop_is_refused_pointing_at_thym_1(tmp_path):
    body = ("  for each o in h where kind is service\n    if o.name is \"x\" then\n      emit o marked stated\n"
            "    end\n  end\n")
    prog = _program(tmp_path, 0, "h: volume", body, "i: volume", "give project h as isotype")
    t = _run(prog, "h")
    assert isinstance(t, T.Trace) and not t.landed
    r = _said(t.refusal)
    assert r.line == 8 and r.message.startswith('if o.name is "x" then (line 8): o is not bound')
    assert r.message.endswith("inside a for each, write thym 1, where a loop's body runs member by member")


def test_a_let_in_a_run_time_loop_read_in_the_same_loop_is_refused_pointing_at_thym_1(tmp_path):
    body = "  for each o in h where kind is service\n    let y = mark o as stated\n    emit y\n  end\n"
    prog = _program(tmp_path, 0, "h: volume", body, "i: volume", "give project h as isotype")
    t = _run(prog, "h")
    r = _said(t.refusal)
    assert (r.check, r.line) == ("loop", 9)
    assert r.message.startswith("emit y (line 9): y is bound by let y = mark o as stated (line 8) inside this "
                                "for each")
    assert "every pass's value at once" in r.message and r.message.endswith("member by member")


# ---------------------------------------------------------------------------
# Refusals in the person's words
# ---------------------------------------------------------------------------

def _publish(tmp_path: Path) -> Path:
    p = tmp_path / "publish-story.thym"
    p.write_bytes((SUITE / "programs" / "publish-story.thym").read_bytes())
    return p


def test_a_failed_assert_outside_a_loop_names_the_expression_not_its_temporary(tmp_path):
    prog = _program(tmp_path, 0, "t: text", "  assert (words t) > 100000\n")
    plan = _plan(prog, "t")
    assert any(re.search(r"\bt\d+\b", n["name"]) for n in _nodes(plan))     # the plan keeps its temporaries
    for program in (prog, None):                                             # with the program, and without it
        t = _run(prog, "t", plan, program=program)
        r = _said(t.refusal)
        assert r.message.startswith("assert (words t) > 100000 (line 7): (words t) > 100000 does not hold; "
                                    "(words t) is "), r.message


def test_agent_free_names_the_first_step_that_asks(tmp_path):
    prog = _publish(tmp_path)
    plan = thym.plan_file(prog, [{"name": "story", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)}])
    r = _said(RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", agent_free=True, program=prog))
    assert (r.check, r.line) == ("agent-free", 12)
    assert r.message == ("3 steps ask a model on the local route, the first `let f = derive story` (line 12); "
                         "agent-free is on")


def test_a_cancelled_run_names_the_statement_it_stopped_before(tmp_path):
    prog = _program(tmp_path, 0, "t: text", "  let n = words t\n", give="give n")
    t = _run(prog, "t", should_stop=lambda: True)
    r = _said(t.refusal)
    assert r.message == "the run was cancelled before let n = words t (line 7); nothing landed"


def _moves_with(name: str, fn) -> R.Moves:
    R.load_all(R.declarations())
    mv = R.MOVES.copy()
    mv.add(name, fn)
    return mv


def test_a_move_that_cannot_go_on_says_why_and_a_runtime_fault_says_so(tmp_path):
    from enough.thym.moves import MoveError
    prog = _program(tmp_path, 0, "t: text", "  let n = words t\n", give="give n")

    def refuses(ctx, *a, **k):
        raise MoveError("words takes a text, and this one is empty")

    def breaks(ctx, *a, **k):
        return {}["no-such-key"]

    t = _run(prog, "t", moves=_moves_with("words", refuses))
    r = _said(t.refusal)
    assert r.message == "let n = words t (line 7): words takes a text, and this one is empty"
    t = _run(prog, "t", moves=_moves_with("words", breaks))
    r = _said(t.refusal)
    assert r.message == ("let n = words t (line 7): words failed inside its implementation; that is a fault of the "
                         "runtime, not of the program")
    rec = next(x for x in t.records if x["id"] == "R:record/1")
    assert "KeyError" in rec["fault"]                      # the record keeps the detail, for whoever maintains it


def test_a_statement_the_runtime_cannot_read_is_a_fault_of_the_runtime(tmp_path):
    prog = _program(tmp_path, 0, "t: text", "  let n = words t\n", give="give n")
    plan = _plan(prog, "t")
    _nodes(plan)[0]["name"] = "words t ) ("
    t = _run(prog, "t", plan)
    r = _said(t.refusal)
    assert r.message == ("let n = words t (line 7): the runtime could not read this statement; that is a fault of "
                         "the runtime, not of the program")
    assert t.records[-1].get("fault")


def test_a_move_the_plan_alone_cannot_find_says_to_run_with_the_program(tmp_path):
    r = _said(RUN.run(mc.yaml_load(mc.read_text(SUITE / "expected" / "open-house" / "plan.cosm")),
                      inputs_root=SUITE, root=tmp_path / "root"))
    assert (r.stage, r.check, r.line) == ("plan", "unknown-move", 15)
    assert r.message == ("emit offer-line o (line 15): offer-line is no declared move, so it is a move of "
                         "open-house.thym, and this run has only the plan; run it with the program beside the plan "
                         "(--program open-house.thym)")


def test_a_for_each_over_what_it_cannot_walk_is_refused_at_its_own_line(tmp_path):
    """THYM 9 (design 2h, 14): the loop's own statement and line, and what the collection is."""
    body = "  let n = words t\n  for each x in n.name\n    emit x marked stated\n  end\n"
    prog = _program(tmp_path, 0, "t: text", body, "i: volume", "give project t as isotype")
    r = _said(thym.check_file(prog))
    assert (r.check, r.line) == ("type", 8)                 # a number has no fields: the checker sees it first


def test_the_compile_refusals_of_the_suite_speak_in_the_persons_words():
    """The sweep over the suite's bad/ programs (design 2h)."""
    for p in sorted((SUITE / "bad").glob("*.thym")):
        _said(_compile(p.read_text(encoding="utf-8"), p))
