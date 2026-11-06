"""The loop that collects and the `thym 1` loop node (THYM 8.1, 11.1, 12.3, 12.4; design 2b, 2g; rulings 5 and 10).

`let xs = for each x in c … keep <expr> … end` binds `list of T` after its end; every `keep` belongs to the nearest
enclosing loop that collects. Under `thym 1` a loop over a collection known only at run time (of more than one plain
statement), a loop that collects and a loop nested in an unrolled one are one node each, whose body runs member by
member as a unit: a `let`, an `if` and a nested `for each` take the pass's values. Under `thym 0` nothing changes but
the third loop that runs wrong (a `for each` nested in a run-time loop), now refused with the fix. Runs land under
tmp_path; the conftest's seams keep everything away from ~/enough.
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
MEADOW = SUITE.parent / "cosm" / "holotypes" / "meadow"
NOTES = SUITE / "inputs" / "notes.md"
TWIN = SUITE / "inputs" / "notes.md.cosm"
TOOL = SUITE / "inputs" / "little-tool"
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
FORBIDDEN = re.compile(r"\bt\d+\b|\bnode \d+\b|R:node/|Error\b|Exception\b")


def compile_text(text: str):
    m = ps.parse(text)
    return m if isinstance(m, Refusal) else ck.check(m)


def refused(text: str) -> Refusal:
    r = compile_text(text)
    assert isinstance(r, Refusal), "compiled, and it must be refused"
    return r


def prog(version: int, body: str, takes: str = "t: text", gives: str = "n: number", give: str = "give words t",
         head: str = "") -> str:
    return f"thym {version}\n\nprogram p\n  takes {takes}\n  gives {gives}\n{head}\n{body}  {give}\nend\n"


INPUTS = {
    "t": lambda: {"name": "t", "type": "text", "path": str(NOTES), "sha256": digest_path(NOTES)},
    "h": lambda: {"name": "h", "type": "volume", "path": str(MEADOW), "sha256": digest_path(MEADOW)},
    "f": lambda: {"name": "f", "type": "fabula", "path": str(TWIN), "sha256": digest_path(TWIN)},
    "repo": lambda: {"name": "repo", "type": "folder", "path": str(TOOL)},
}


def plan_of(tmp_path: Path, text: str, *names: str) -> tuple[Path, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "p.thym"
    p.write_text(text, encoding="utf-8")
    plan = thym.plan_file(p, [INPUTS[n]() for n in names])
    assert not isinstance(plan, Refusal), plan
    return p, plan


def nodes(plan: dict) -> list[dict]:
    return RUN.plan_parts(plan)[1]


def run(p: Path, plan: dict, **kw):
    kw.setdefault("program", p)
    kw.setdefault("engines", H.engines(feed=None))
    return RUN.run(plan, inputs_root=SUITE, root=p.parent / "root", now=NOW, **kw)


def landed(t) -> T.Trace:
    assert isinstance(t, T.Trace) and t.landed, getattr(t, "refusal", t)
    return t


def said(r: Refusal) -> Refusal:
    assert isinstance(r, Refusal) and not FORBIDDEN.search(r.message), r
    return r


# ---------------------------------------------------------------------------
# The loop that collects: compile
# ---------------------------------------------------------------------------

def test_a_loop_that_collects_binds_a_list_of_what_it_keeps_after_its_end():
    c = compile_text(prog(1, "  let ns = for each x in [t, t]\n    keep words x\n  end\n", give="give count ns"))
    assert not isinstance(c, Refusal), c
    loop = c.programs()[0].stmts[0]
    assert isinstance(loop, ps.For) and loop.collect == "ns" and loop.collect_binding.type == "list of number"
    assert (7, "a loop that collects (let ns = for each …)") in c.module.features


@pytest.mark.parametrize("body, line, words", [
    ("  for each x in [t]\n    keep x\n  end\n", 8, "keep stands inside a loop that collects (let <name> = for each …)"
                                                    "; the loop at line 7 binds nothing"),
    ("  keep t\n", 7, "keep stands inside a loop that collects (let <name> = for each …); line 7 stands in no loop"),
    ("  let ns = for each x in [t]\n    let w = words x\n  end\n", 7, "the loop that binds ns keeps nothing: add a keep line"),
    ("  let ns = for each x in [t]\n    keep x\n    keep words x\n  end\n", 9,
     "the loop that binds ns keeps a text at line 8 and a number at line 9; a list holds one type"),
    ("  let ns = for each x in [t]\n    keep (count ns)\n  end\n", 8,
     "ns is bound by the loop it is read in; read it after the loop's end (line 9)"),
    ("  let ns = for each x in [t]\n    give words x\n  end\n", 8, "a loop body may not give: a block gives once, "
                                                                     "after its loops"),
])
def test_where_a_keep_may_stand_and_each_refusal(body, line, words):
    r = refused(prog(1, body, give="give 0"))
    assert (r.check, r.line, r.message) == ("type", line, words)


def test_a_keep_belongs_to_the_nearest_loop_that_collects():
    """Inside an `if` and inside a plain inner loop (which then keeps several per pass); never in a user move's body
    unless that body holds the loop."""
    body = ("  let ns = for each x in [t, t]\n    if words x > 0 then\n      for each y in [x, x]\n        keep words y\n"
            "      end\n    end\n  end\n")
    assert not isinstance(compile_text(prog(1, body, give="give count ns")), Refusal)
    move = "  move m(x: text): number\n    keep words x\n    give words x\n  end\n"
    r = refused(prog(1, "  let ns = for each x in [t]\n    keep m x\n  end\n", give="give count ns", head=move))
    assert (r.check, r.line) == ("type", 7) and r.message.startswith("keep stands inside a loop that collects")
    inner = "  move m(x: text): number\n    let ks = for each y in [x]\n      keep words y\n    end\n    give count ks\n  end\n"
    assert not isinstance(compile_text(prog(1, "", head=inner, give="give m t")), Refusal)


def test_a_loop_that_collects_needs_thym_1():
    r = refused(prog(0, "  let ns = for each x in [t]\n    keep words x\n  end\n", give="give count ns"))
    assert (r.check, r.line) == ("version", 7)
    assert r.message == ("this needs `thym 1`: a loop that collects (let ns = for each …) at line 7; the first line "
                         "says thym 0")


def test_a_loop_that_collects_enumerates_as_a_for_step_that_binds_its_name_with_keep_steps():
    vol = en.enumerate_text(prog(1, "  let ns = for each x in [t, t]\n    keep words x\n  end\n", give="give count ns"))
    steps = {it["id"]: it for it in vol["nodes"] if it["type"] == "step"}
    loop, keep = steps["P:step/p.1"], steps["P:step/p.2"]
    assert (loop["form"], loop["binds"], loop["steps"], loop["lines"]) == ("for", "ns", ["P:step/p.2"], "7-9")
    assert (keep["form"], keep["move"], keep["calls"]) == ("keep", "words", ["words"])
    assert en.compile_volume(vol) == prog(1, "  let ns = for each x in [t, t]\n    keep words x\n  end\n",
                                          give="give count ns")


# ---------------------------------------------------------------------------
# The loop that collects: plan and run
# ---------------------------------------------------------------------------

def test_a_loop_that_collects_over_a_written_list_is_one_node_and_runs(tmp_path):
    text = prog(1, "  let ns = for each x in [t, t]\n    keep words x\n  end\n", give="give count ns")
    p, plan = plan_of(tmp_path, text, "t")
    n = nodes(plan)
    assert [x["name"] for x in n] == ["let ns = for each x in [t, t]", "count ns"]
    assert (n[0]["move"], n[0]["gives"], n[0]["repeats"], n[0]["takes"]) == ("for", "ns", True, ["t"])
    assert n[0]["calls"] == ["words"] and n[0]["members"] == {"at_most": 2} and n[1]["after"] == ["R:node/1"]
    t = landed(run(p, plan))
    rec = t.records[0]
    assert rec["passes"] == 2 and [o["name"] for o in rec["outputs"]] == ["ns", "ns.1", "ns.2"]
    assert t.outputs["n"].read_text(encoding="utf-8") == "2"


def test_a_loop_that_collects_over_a_folder_and_a_run_time_collection(tmp_path):
    text = ("thym 1\n\nprogram p\n  takes repo: folder\n  gives n: number\n\n"
            "  let ws = for each f in repo where suffix is py\n    keep words f\n  end\n"
            "  let big = for each w in ws where w > 0\n    keep w\n  end\n  give count big\nend\n")
    p, plan = plan_of(tmp_path, text, "repo")
    n = nodes(plan)
    assert n[0]["members"] == {"at_most": 7}                 # the folder's files, before the where
    assert "members" not in n[1]                             # a list made at run time: unknown at plan time
    t = landed(run(p, plan))
    assert [r.get("passes") for r in t.records[:2]] == [3, 3]
    assert t.outputs["n"].read_text(encoding="utf-8") == "3"


def test_a_refusal_in_a_pass_names_the_statement_of_the_body_and_the_pass_and_nothing_lands(tmp_path):
    body = "  let ns = for each x in [t, t]\n    let w = words x\n    assert w > 100000\n    keep w\n  end\n"
    p, plan = plan_of(tmp_path, prog(1, body, give="give count ns"), "t")
    t = run(p, plan)
    assert isinstance(t, T.Trace) and not t.landed and not (t.dir / "outputs").exists()
    r = said(t.refusal)
    assert (r.check, r.line) == ("assert", 9)
    assert r.message.startswith("assert w > 100000 (line 9, for x = the first member): w > 100000 does not hold; "
                                "w is ")


# ---------------------------------------------------------------------------
# The thym 1 loop node (ruling 5; design 2g)
# ---------------------------------------------------------------------------

def test_a_run_time_loop_of_several_statements_is_one_node_in_thym_1_and_runs_as_a_unit(tmp_path):
    body = ("  for each o in h where kind is service\n    let s = mark o as stated\n    if s has name then\n"
            "      emit mark s as verified\n    end\n  end\n")
    text = prog(1, body, takes="h: volume", gives="i: volume", give="give project h as isotype")
    p, plan = plan_of(tmp_path, text, "h")
    n = nodes(plan)
    assert [x["name"] for x in n] == ["for each o in h where kind is service", "project h as isotype"]
    assert (n[0]["move"], n[0]["repeats"], n[0]["calls"], n[0]["takes"]) == ("for", True, ["mark"], ["h"])
    assert "gives" not in n[0] and n[1]["after"] == ["R:node/1"]
    t = landed(run(p, plan))
    assert t.records[0]["passes"] == 3 and [o["name"] for o in t.records[0]["outputs"]] == ["emit.1", "emit.2",
                                                                                          "emit.3"]
    offers = mc.yaml_load((t.dir / "outputs" / "i.cosm").read_text(encoding="utf-8")).get("offers")
    assert len(offers) == 3


def test_the_same_loop_in_thym_0_is_refused_with_the_fix(tmp_path):
    body = "  for each o in h where kind is service\n    let s = mark o as stated\n    emit mark s as verified\n  end\n"
    text = prog(0, body, takes="h: volume", gives="i: volume", give="give project h as isotype")
    p, plan = plan_of(tmp_path, text, "h")
    assert [x["move"] for x in nodes(plan)] == ["mark", "mark", "project"]       # thym 0's plan, unchanged
    r = said(run(p, plan).refusal)
    assert r.check == "loop" and r.message.endswith("inside a for each, write thym 1, where a loop's body runs "
                                                    "member by member")
    relabelled = text.replace("thym 0", "thym 1", 1)
    p, plan = plan_of(tmp_path / "one", relabelled, "h")
    assert [x["move"] for x in nodes(plan)] == ["for", "project"]
    landed(run(p, plan))


def test_a_for_each_nested_in_a_run_time_loop_is_refused_in_thym_0_and_runs_in_thym_1(tmp_path):
    """Ruling 10's third case: in `thym 0` the plan lost the outer loop, so the inner loop does not run once per pass;
    it is refused at run with the same fix. In `thym 1` the outer loop is one node and the inner runs per pass."""
    body = ("  for each o in h where kind is service\n    for each x in [o, o]\n      emit mark x as verified\n"
            "    end\n  end\n")
    text = prog(0, body, takes="h: volume", gives="i: volume", give="give project h as isotype")
    p, plan = plan_of(tmp_path, text, "h")
    r = said(run(p, plan).refusal)
    assert (r.check, r.line) == ("loop", 9)
    assert r.message == ("emit mark x as verified (line 9): this statement stands in the for each at line 8, inside "
                         "the for each at line 7, and in thym 0 each statement of a for each over a collection known "
                         "only at run time runs over every member before the next statement starts, so the inner "
                         "loop does not run once for each pass of the outer one; inside a for each, write thym 1, "
                         "where a loop's body runs member by member")
    p, plan = plan_of(tmp_path / "one", text.replace("thym 0", "thym 1", 1), "h")
    assert [x["move"] for x in nodes(plan)] == ["for", "project"]
    t = landed(run(p, plan))
    assert t.records[0]["passes"] == 3 and len(t.records[0]["outputs"]) == 6       # two per service


def test_a_loop_nested_in_a_written_list_loop_is_one_node_per_member_and_sees_it(tmp_path):
    body = "  for each x in [t, t]\n    let ws = for each y in [x]\n      keep words y\n    end\n    assert count ws > 0\n  end\n"
    p, plan = plan_of(tmp_path, prog(1, body), "t")
    names = [x["name"] for x in nodes(plan)]
    assert names[:2] == ["let ws = for each y in [x], for x = t", "assert count ws > 0, for x = t"]
    landed(run(p, plan))


def test_a_loop_of_one_plain_statement_plans_as_thym_0_does():
    text = ("for each o in h where kind is service\n    emit mark o as stated\n  end\n")
    zero = compile_text(prog(0, "  " + text, takes="h: volume", gives="i: volume", give="give project h as isotype"))
    one = compile_text(prog(1, "  " + text, takes="h: volume", gives="i: volume", give="give project h as isotype"))
    rows = [INPUTS["h"]()]
    assert pl.plan(zero, rows)["nodes"][1:] == pl.plan(one, rows)["nodes"][1:]


def test_a_loop_node_without_the_program_is_refused_with_the_fix(tmp_path):
    body = "  for each o in h where kind is service\n    let s = mark o as stated\n    emit s\n  end\n"
    p, plan = plan_of(tmp_path, prog(1, body, takes="h: volume", gives="i: volume", give="give project h as isotype"),
                      "h")
    r = said(run(p, plan, program=None).refusal)
    assert r.check == "program" and r.message == (
        "for each o in h where kind is service (line 7): this loop's body is read from the program, and this run has "
        "only the plan: run it with the program beside the plan (--program)")


# ---------------------------------------------------------------------------
# Model calls inside a loop node: keyed per member, replayed in order (THYM 12.4)
# ---------------------------------------------------------------------------

class Scripted:
    """Answers each model request in turn from a list; keeps every contract it was sent."""

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


def easy_checks() -> C.Checks:
    out = C.CHECKS.copy()
    for name in ("coverage", "no-invention", "stance-kept", "scales-met", "footer"):
        out.add(name, lambda *a: (True, ""))
    return out


def test_model_calls_in_a_loop_node_are_keyed_per_member_and_replay(tmp_path):
    body = "  let tellings = for each x in [f, f]\n    keep tell x as told\n  end\n"
    text = prog(1, body, takes="f: fabula", gives="n: number", give="give count tellings")
    p, plan = plan_of(tmp_path, text, "f")
    n = nodes(plan)
    assert (n[0]["asks"], n[0]["budget"]["attempts"], n[0]["calls"]) == (True, 3, ["tell"])
    cp = Scripted(["The first telling.\n", "The second telling.\n"])
    t = landed(run(p, plan, coprocessor=cp, moves=tell_moves(), checks=easy_checks()))
    keys = sorted(x.name for x in (t.dir / "candidates").glob("*.cosm"))
    assert keys == ["1-1.1.cosm", "1.1.cosm"]
    again = RUN.replay(t.dir, root=tmp_path / "root", moves=tell_moves(), checks=easy_checks(),
                       engines=H.engines(feed=None))
    assert again.replay["identical"], again.replay


def test_a_pass_over_lines_is_named_by_the_lines_number():
    """THYM 9: `for l = line 7`, whatever list the lines came in (`lines of s` gives a list of line values)."""
    from enough.thym.values import Value, make_line
    assert RUN._Run._pass(None, "l", make_line("A long line.", 7, "0" * 64), 1, Value("list", [])) == "for l = line 7"
