"""The checker reports every independent fault it finds, not only the first (0.7).

A parse error still stops at the first: what follows it cannot be read. A checking fault does not: each block is
checked whatever another block said, and each statement whatever another statement said, except a statement that uses
a name a refused statement would have bound (it would only repeat the first fault in other words). The first fault is
the one the compiler gave before (the conformance suite's bad/ programs still name it), and `Refusal.more` holds the
rest; the CLI prints them all and `POST /api/thym/compile` answers `refusal` (the first, where it was) and
`refusals` (every one, the first included), which the editor's strip already steps through.
"""
from __future__ import annotations

import re
from argparse import Namespace
from pathlib import Path

import pytest

from enough import thym_api
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import cli
from enough.thym import parse as ps

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
_REFUSED = re.compile(r"^-- refused: (compile|plan|run) ([a-z-]+) line (\d+)$")

# Four faults, none of which depends on another: a move no manifest declares (line 9, in the program's own move), a
# name nobody bound (line 12), another undeclared move (line 13) and a name bound twice (line 16). Line 14 uses what
# line 12 would have bound, so it is not checked: its fault would only repeat line 12's.
MANY = """thym 1

program many
  why: faults that do not depend on each other.
  takes t: text
  gives f: fabula

  move first(x: text): short
    give summarise x
  end

  let a = derive story
  let b = summarise t
  let d = derive a
  let c = derive t
  let c = derive t
  give derive t
end
"""


def compile_text(text: str) -> object:
    module = ps.parse(text)
    return module if isinstance(module, Refusal) else ck.check(module)


def faults(r: Refusal) -> list[tuple[str, int | None]]:
    return [(x.check, x.line) for x in r.all()]


def test_every_independent_fault_is_reported_in_the_order_found():
    r = compile_text(MANY)
    assert isinstance(r, Refusal)
    assert faults(r) == [("unknown-move", 9), ("unbound", 12), ("unknown-move", 13), ("rebound", 16)]
    assert (r.check, r.line) == ("unknown-move", 9)              # the first, where it always was
    assert [x.line for x in r.more] == [12, 13, 16]


def test_a_statement_that_uses_a_refused_name_is_not_checked_again():
    text = MANY.replace("  let d = derive a\n", "  let d = derive a\n  let e = summarise d\n")
    r = compile_text(text)
    assert 14 not in [x.line for x in r.all()] and 15 not in [x.line for x in r.all()]


def test_a_parse_error_still_stops_at_the_first():
    r = compile_text("thym 1\n\nprogram p\n  why: x\n  takes t: text\n  gives s: short\n  give (\n  give )\nend\n")
    assert isinstance(r, Refusal) and r.check == "parse" and r.more == ()


@pytest.mark.parametrize("name", sorted(p.name for p in SUITE.glob("bad/*.thym")))
def test_every_bad_program_still_names_its_first_fault(name: str):
    text = (SUITE / "bad" / name).read_text(encoding="utf-8")
    m = _REFUSED.match(text.split("\n", 1)[0])
    if m.group(1) != "compile":
        pytest.skip("refused after the compiler")
    r = compile_text(text)
    assert isinstance(r, Refusal), name
    assert (r.stage, r.check, r.line) == (m.group(1), m.group(2), int(m.group(3)))
    assert r.all()[0] is r


@pytest.mark.parametrize("name", sorted(p.name for p in SUITE.glob("programs/*.thym")))
def test_a_program_that_compiles_still_compiles(name: str):
    assert not isinstance(compile_text((SUITE / "programs" / name).read_text(encoding="utf-8")), Refusal)


def test_the_refusal_compares_and_prints_as_before():
    one = Refusal("compile", "type", "m", 3, "f.thym")
    two = Refusal("compile", "type", "m", 3, "f.thym", more=(Refusal("compile", "unbound", "n", 5, "f.thym"),))
    assert one == two and hash(one) == hash(two)
    assert str(two) == "f.thym:3: refused at compile (type): m"
    assert one.all() == [one] and [x.line for x in two.all()] == [3, 5]


def test_the_api_gives_the_first_where_it_was_and_every_one_in_a_list():
    r = thym_api.compile_payload(text=MANY)
    assert r["ok"] is False
    assert (r["refusal"]["check"], r["refusal"]["line"]) == ("unknown-move", 9)
    assert [(x["check"], x["line"]) for x in r["refusals"]] == [("unknown-move", 9), ("unbound", 12),
                                                               ("unknown-move", 13), ("rebound", 16)]
    assert r["refusals"][0] == r["refusal"]
    ok = thym_api.compile_payload(path=SUITE / "programs" / "tighten.thym")
    assert ok["ok"] is True and ok["refusal"] is None and ok["refusals"] == []


def test_the_cli_prints_every_fault(tmp_path: Path, capsys):
    p = tmp_path / "many.thym"
    p.write_text(MANY, encoding="utf-8")
    assert cli.cmd_check(Namespace(program=str(p))) == 2
    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 4 and all("refused at compile" in ln for ln in lines)
    assert [int(re.search(r":(\d+): ", ln).group(1)) for ln in lines] == [9, 12, 13, 16]
