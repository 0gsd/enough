"""The Thym compiler (enough/thym: parse, declarations, types, check, enumerate, plan, contracts).

The conformance suite's compiler half (docs/THYM.md 20.1, 20.3): every program in tests/fixtures/thym/programs
enumerates to its expected items, compiles back byte for byte and plans to its expected plan; every bad/ program is
refused at the stage, check and line its first line names; every ```thym block of the specification compiles,
enumerates back and plans. Then the grammar's corners (section 4), the checker's refusals (section 9), `use`
(section 8.4), the declarations every manifest makes (section 17.6), and the contracts constant against section
7.3's table. The compiler is pure: nothing here touches ~/enough; scratch files go into tmp_path.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import shutil
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough import thym
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import contracts as ct
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym import types as ty

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "docs" / "THYM.md"
SUITE = REPO / "tests" / "fixtures" / "thym"
PROGRAMS = sorted(p.stem for p in SUITE.glob("programs/*.thym"))
BADS = sorted(p.name for p in SUITE.glob("bad/*.thym"))
_REFUSED = re.compile(r"^-- refused: (compile|plan|run) ([a-z-]+) line (\d+)$")
HOUSE = {"oes": "thym/1", "kind": "morph", "id": "thym/house", "name": "house",
         "nodes": [{"id": "M:morph/rosa", "type": "morph", "name": "rosa", "summary": "The house voice."}]}
V = "thym 0\n\n"


def _text(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


def _spec_blocks() -> list[str]:
    return re.findall(r"^```thym\n(.*?)^```", _text(SPEC), re.S | re.M)


def compile_text(text: str, *, path: str | None = None, volumes=None):
    """parse + check, as check_file does for a file."""
    module = ps.parse(text, path=path)
    if isinstance(module, Refusal):
        return module
    return ck.check(module, volumes=volumes)


def refused(text: str, **kw) -> Refusal:
    r = compile_text(text, **kw)
    assert isinstance(r, Refusal), "compiled, and it must be refused"
    return r


def ok(text: str, **kw) -> ck.Checked:
    r = compile_text(text, **kw)
    assert not isinstance(r, Refusal), str(r)
    return r


def _inputs_of(checked: ck.Checked) -> list[dict]:
    prog = checked.programs()[0]
    return [{"name": p.name, "type": p.type, "path": f"in/{p.name}", "sha256": "0" * 64} for p in prog.takes]


# ---------------------------------------------------------------------------
# The conformance suite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("program", PROGRAMS)
def test_program_enumerates_to_its_fixture(program):
    mine = en.enumerate_file(SUITE / "programs" / f"{program}.thym")
    assert isinstance(mine, dict), mine
    want = mc.yaml_load(_text(SUITE / "expected" / program / "items.cosm"))
    assert mine["built"]["by"].startswith("enough/")
    mine.pop("built")
    want.pop("built")
    assert mine == want


@pytest.mark.parametrize("program", PROGRAMS)
def test_program_compiles_back_byte_for_byte(program, tmp_path):
    src = SUITE / "programs" / f"{program}.thym"
    vol = en.enumerate_file(src)
    assert en.compile_volume(vol).encode("utf-8") == src.read_bytes()
    text = en.dump(vol)
    assert mc.yaml_load(text) == vol                    # the law of dump
    assert text.startswith("oes: thym/1\n") and "\r" not in text
    path = tmp_path / f"{program}.thym.cosm"            # and the reader reads it clean
    path.write_text(text, encoding="utf-8")
    volume = mc.load_volume(path)
    assert volume.refused is None, volume.refused
    report = mc.lint(volume)
    assert report.ok and not report.warnings, "; ".join(str(e) for e in report.errors + report.warnings)


def _true_digest(path: str) -> str:
    p = SUITE / path
    if p.is_dir():
        p = mc.default_registry().find_catalog(p)
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("program", PROGRAMS)
def test_program_plans_to_its_fixture(program):
    want = mc.yaml_load(_text(SUITE / "expected" / program / "plan.cosm"))
    for inp in want["inputs"]:
        assert inp["sha256"] == _true_digest(inp["path"]), f"{program}: the fixture's digest of {inp['path']}"
    got = thym.plan_file(SUITE / "programs" / f"{program}.thym", want["inputs"])
    assert isinstance(got, dict), got
    assert re.fullmatch(r"thym/\d{4}-\d{2}-\d{2}-\d{4}-[0-9a-f]{4}", got["id"])
    assert got["nodes"][0]["id"] == "R:plan/" + got["id"].split("/", 1)[1]
    assert pl.normalise(got) == pl.normalise(want)
    assert pl.normalise(want) == pl.normalise(pl.normalise(want))
    assert mc.yaml_load(en.dump(got)) == got


@pytest.mark.parametrize("bad", BADS)
def test_bad_program_is_refused_where_it_says(bad):
    path = SUITE / "bad" / bad
    stage, check, line = _REFUSED.match(_text(path).split("\n", 1)[0]).groups()
    r = thym.check_file(path)
    assert isinstance(r, Refusal), f"{bad} compiled"
    assert (r.stage, r.check, r.line) == (stage, check, int(line)), str(r)
    assert r.file == str(path) and r.message
    assert isinstance(en.enumerate_file(path), Refusal)


@pytest.mark.parametrize("index", range(len(_spec_blocks())))
def test_every_spec_block_compiles_enumerates_and_plans(index):
    text = _spec_blocks()[index]
    checked = ok(text, volumes={"oes:thym/house": HOUSE})
    vol = en.enumerate_checked(checked)
    assert en.compile_volume(vol) == text
    assert mc.yaml_load(en.dump(vol)) == vol
    plan = pl.plan(checked, _inputs_of(checked))
    assert isinstance(plan, dict), plan
    assert plan["estimate"]["steps"] == len(plan["nodes"]) - 1


def test_check_file_and_plan_file():
    checked = thym.check_file(SUITE / "programs" / "publish-story.thym")
    assert isinstance(checked, ck.Checked)
    assert [b.name for b in checked.programs()] == ["publish-story"]
    assert isinstance(thym.check_file(SUITE / "nowhere.thym"), Refusal)
    r = thym.plan_file(SUITE / "programs" / "publish-story.thym", [])
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "input")


# ---------------------------------------------------------------------------
# The grammar's corners (section 4)
# ---------------------------------------------------------------------------

def test_prose_heads_run_to_a_blank_line_a_head_or_end():
    checked = ok(V + "program p\n  why: one line\n  must: a constraint\n       continued here\n"
                 "  decided 2026-11-01: a decision\n  takes t: text\n  gives s: short\n"
                 "  give tell (derive t) as told\nend\n")
    b = checked.programs()[0]
    assert b.why.text == "one line"
    assert [m.text for m in b.musts] == ["a constraint continued here"]
    assert b.decideds[0].date == dt.date(2026, 11, 1) and b.decideds[0].what == "a decision"
    assert checked.module.warnings == []


def test_a_prose_line_that_begins_with_a_statement_keyword_warns():
    module = ps.parse(V + "program p\n  why: the reason\n  give the reader something\n  takes t: text\n"
                      "  gives s: short\n\n  give tell (derive t) as told\nend\n")
    assert isinstance(module, ps.Module)
    assert module.programs()[0].why.text == "the reason give the reader something"
    assert [w.line for w in module.warnings] == [5] and "give" in module.warnings[0].message
    assert isinstance(ck.check(module), ck.Checked)


def test_a_comment_dash_inside_a_string_is_not_a_comment():
    checked = ok(V + 'program p\n  takes t: text\n  gives f: fabula\n  let f = derive t\n'
                 '  assert f covers t else "a -- b"   -- the real comment\n  give f\nend\n')
    st = checked.programs()[0].stmts[1]
    assert st.message == "a -- b" and st.comment == "the real comment"


def test_a_list_and_parentheses_may_span_lines_nothing_else_may():
    checked = ok(V + "program p\n  takes h: volume\n  gives i: volume\n  for each o in h where kind in [product,\n"
                 "                                service]\n    emit o marked verified\n  end\n"
                 "  give project h as isotype\nend\n")
    vol = en.enumerate_checked(checked)
    step = next(i for i in vol["nodes"] if i["id"] == "P:step/p.1")
    assert step["lines"] == "6-9" and step["text"].count("\n") == 1
    r = refused(V + "program p\n  takes t: text\n  gives f: fabula\n  let f = derive t give f\nend\n")
    assert (r.check, r.line) == ("parse", 6)


def test_a_labelled_emit_a_filter_and_marked_sugar():
    checked = ok(V + "program p\n  takes h: volume\n  gives i: volume\n  let staff = h where module is employees\n"
                 "  emit employees: band (count staff) as [none, some] marked verified\n"
                 "  for each a in h where kind is aim\n    emit a marked stated\n  end\n"
                 "  give project h as isotype\nend\n")
    b = checked.programs()[0]
    let, emit1, emit2 = b.stmts[0], b.stmts[1], b.stmts[2].body[0]
    assert let.expr.type == "list of item" and isinstance(let.expr, ps.Filter)
    assert emit1.slot == "employees" and isinstance(emit1.expr, ps.Marked) and emit1.expr.type == "word"
    assert ck.step_call_names(emit1) == ["band", "count", "mark"]
    assert ck.own_call(emit2).word == "stated"          # a marked plain value: the step's move is mark
    vol = en.enumerate_checked(checked)
    step4 = next(i for i in vol["nodes"] if i["id"] == "P:step/p.4")
    assert step4["move"] == "mark" and step4["contracts"] == ["P:contract/p.4"]
    assert refused(V + "program p\n  takes h: volume\n  gives i: volume\n  emit (h where kind is aim) marked stated\n"
                   "  give project h as isotype\nend\n").check == "type"


def test_null_of_takes_its_argument_through_of_and_the_modifier_rule():
    checked = ok(V + "program p\n  takes story: text\n  gives m: morph\n  let f = derive story\n"
                 "  give measure story against null of f\nend\n")
    call = checked.programs()[0].stmts[1].expr
    against = call.mod("against").arg
    assert isinstance(against, ps.Call) and against.move == "null" and against.mod("of").arg.name == "f"
    assert ps.render(call) == "measure story against null of f"
    r = refused(V + "program p\n  takes f: fabula\n  gives s: short\n  give null f\nend\n")
    assert r.check == "type" and "of" in r.message


@pytest.mark.parametrize("body, line", [
    ("  give tell (derive t) as told with plain\n", 6),          # a typo never becomes a word
    ("  let x = aim\n  give tell (derive t) as told\n", 6),
    ("  if kind is aim then\n    give tell (derive t) as told\n  else\n    give tell (derive t) as told\n  end\n", 6),
])
def test_bare_words_are_refused_outside_their_places(body, line):
    r = refused(V + "program p\n  takes t: text\n  gives s: short\n" + body + "end\n")
    assert (r.check, r.line) == ("unbound", line)


def test_bare_words_stand_for_themselves_in_their_places():
    checked = ok(V + "program p\n  takes h: volume\n  gives i: volume\n"
                 "  for each o in h where kind is aim and stage in [draft, live]\n    emit o\n  end\n"
                 "  give project h as isotype\nend\n")
    where = checked.programs()[0].stmts[0].where
    assert where.left.left.kind == "field" and where.left.right.kind == "word"
    assert [x.kind for x in where.right.right.items] == ["word", "word"]


@pytest.mark.parametrize("src, check, line", [
    ("program p\n  give 0\nend\n", "version", 1),
    (V + "program p\n  takes t: text\n  gives f: fabula\n  give derive t\n", "parse", 3),
    (V + "program p\n  takes h: volume\n  gives i: volume\n  if count h > 3 then\n    give project h as isotype\n"
         "  else\n    give project h as paratype\n  end\nend\n", "parse", 6),
    (V + "program p\n  takes t: text\n  gives s: short\n  give tell derive t as told\nend\n", "parse", 6),
    (V + "program p\n  takes t: text\n  gives f: fabula\n  let f = derive t\n  move m(x: text): fabula\n"
         "    give derive x\n  end\n  give f\nend\n", "parse", 7),
    (V + "program p\n  takes my_t: text\n  gives f: fabula\n  give derive my_t\nend\n", "parse", 4),
    (V + "program P\nend\n", "parse", 3),
    (V + "program p\n  why: one\n  why: two\nend\n", "parse", 5),
])
def test_parse_refusals(src, check, line):
    r = refused(src)
    assert (r.stage, r.check, r.line) == ("compile", check, line), str(r)


def test_crlf_a_byte_order_mark_and_no_final_newline_round_trip():
    for src in ("﻿thym 0\r\n\r\nprogram p\r\n  takes t: text\r\n  gives f: fabula\r\n  give derive t   -- x\r\n"
                "end\r\n\r\n",
                V + 'context c\n  medium "x"\nend\nprogram p\n  gives n: number\n  give 0\nend'):
        vol = en.enumerate_text(src)
        assert isinstance(vol, dict), vol
        assert en.compile_volume(vol) == src
        assert mc.yaml_load(en.dump(vol)) == vol


def test_morph_and_context_blocks_enumerate():
    module = ps.parse(V + "morph plain\n  why: casual.\n  humour 2\nend\n")
    assert module.blocks[0].scales == [] and [w.line for w in module.warnings] == [5]
    vol = en.enumerate_text(V + "morph plain\n  why: casual, a little funny.\n\n  formality 3 toward casual\n"
                            "  humour 2\nend\n\ncontext trip\n  medium \"phone\"\n  hurry true\n  words 300\nend\n")
    morph, context = vol["nodes"]
    assert morph["id"] == "M:morph/plain" and morph["declared"] is True and morph["toward"] == "casual"
    assert list(morph["scales"]) == list(ty.SCALES) and morph["scales"]["formality"] == 3
    assert morph["scales"]["register"] == 1 and morph["summary"] == "Casual, a little funny."
    assert context["id"] == "C:context/trip" and (context["medium"], context["hurry"], context["words"]) == \
        ("phone", True, 300)


# ---------------------------------------------------------------------------
# The checker's refusals (sections 5, 7.1, 8, 9)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body, check, line", [
    ("  give tell (derive t) as verified\n", "type", 6),                          # as takes an order
    ("  give tell (derive t) with m as told\n", "type", 6),                       # modifiers in declared order
    ("  give tell (derive t) to 30 words\n", "type", 6),                          # tell takes no to
    ("  let told = derive t\n  give tell told as told\n", "type", 6),             # a reserved name
    ("  let f = derive t\n  if true then\n    let f = derive t\n  end\n  give tell f as told\n", "rebound", 8),
    ("  give atem (derive t)\n", "type", 6),                                       # gives an atem, not a short
    ("  give fabula\n", "type", 6),                                                # an accessor without of
    ("  give count [1, \"a\"]\n", "type", 6),                                      # a list of one type
    ("  if true then\n    give tell (derive t) as told\n  end\n", "no-give", 3),   # no else, no give
    ("  give tell (derive t) as told with nothing\n", "type", 6),                  # nothing is no morph here
])
def test_check_refusals(body, check, line):
    r = refused(V + "program p\n  takes t: text, m: morph\n  gives s: short\n" + body + "end\n")
    assert (r.check, r.line) == (check, line), str(r)


def test_a_loop_body_may_not_give_and_an_unmarked_word_is_not_emitted():
    r = refused(V + "program p\n  takes h: volume\n  gives i: item\n  for each o in h\n    give o\n  end\n"
                "  give project h as isotype\nend\n")
    assert (r.check, r.line) == ("type", 7)
    r = refused(V + "program p\n  takes h: volume\n  gives i: volume\n  emit band (count h) as [none, some]\n"
                "  give project h as isotype\nend\n")
    assert (r.check, r.line) == ("type", 6) and "mark" in r.message


def test_summaries_follow_the_rule_of_section_10():
    checked = ok(V + "move m(f: fabula): short\n  give tell f as told\nend\n\nprogram p\n  why: one. two.\n"
                 "  takes t: text\n  gives s: short\n  let f = derive t      -- the fabula\n  assert f covers t\n"
                 "  give m f\nend\n")
    vol = en.enumerate_checked(checked)
    by = {i["id"]: i["summary"] for i in vol["nodes"]}
    assert by["P:program/p"] == "One." and by["P:move/m"] == "move m(f: fabula): short"
    assert by["P:step/p.1"] == "the fabula" and by["P:step/p.2"] == "assert f covers t"
    assert by["P:contract/p.2"] == "The program's own check: f covers t."
    assert by["P:contract/p.3"] == "What m must leave true of what it gives."
    plan = pl.plan(checked, _inputs_of(checked))
    assert [n["summary"] for n in plan["nodes"]] == ["Three nodes, two of which ask the model.", "the fabula",
                                                     "assert f covers t", "m f"]
    assert pl.root_summary(1, 0) == "One node, none of which asks the model."
    assert pl.root_summary(21, 1) == "21 nodes, one of which asks the model."


def test_a_local_move_body_is_verbatim():
    vol = en.enumerate_file(SUITE / "programs" / "open-house.thym")
    body = next(i["body"] for i in vol["nodes"] if i["id"] == "P:move/open-house.offer-line")
    assert body.startswith("  move offer-line(o: item): item\n    give mark o as verified")
    text = en.dump(vol)
    assert "body: |2" in text and mc.yaml_load(text) == vol


def test_a_package_may_take_nothing_for_its_last_three():
    ok(V + "program p\n  takes t: text\n  gives out: package\n  let f = derive t\n"
       "  give package t, f, nothing, nothing, nothing\nend\n")
    r = refused(V + "program p\n  takes t: text\n  gives out: package\n  give package t, nothing, nothing, nothing, "
                "nothing\nend\n")
    assert r.check == "type"


def test_recursion_through_two_moves_is_refused_at_the_first():
    r = refused(V + "move a(f: fabula): short\n  give b f\nend\n\nmove b(f: fabula): short\n  give a f\nend\n")
    assert (r.check, r.line) == ("recursion", 3) and "a → b → a" in r.message


@pytest.mark.parametrize("body, check, line", [
    ("  loudness 3\n", "type", 4),
    ("  humour 6\n", "type", 4),
    ("  formality 2\n", "type", 4),
    ("  humour 2 toward casual\n", "type", 4),
    ("  humour 2\n  humour 3\n", "type", 5),
])
def test_morph_scales_are_the_ten_names_from_one_to_five(body, check, line):
    r = refused(V + "morph m\n" + body + "end\n")
    assert (r.check, r.line) == (check, line), str(r)


def test_unknown_move_names_the_nearest():
    r = refused(V + "program p\n  takes f: fabula\n  gives s: short\n  give tel f as told\nend\n")
    assert (r.check, r.line) == ("unknown-move", 6) and "`tell`" in r.message


def test_a_move_sees_its_parameters_and_never_its_caller():
    r = refused(V + "program p\n  takes t: text\n  gives s: short\n  move m(f: fabula): short\n"
                "    give tell f as told with t\n  end\n  give m (derive t)\nend\n")
    assert (r.check, r.line) == ("unbound", 7)


def test_user_moves_inherit_contracts_calls_and_asks():
    checked = ok(V + "move plainly(f: fabula): short\n  let s = tell f as told\n  assert f covers s\n  give s\nend\n\n"
                 "program p\n  takes t: text\n  gives s: short\n  give plainly (derive t)\nend\n")
    mv = checked.moves["plainly"]
    assert mv.calls == ["tell"] and mv.asks is True
    assert mv.checks == ["coverage", "no-invention", "stance-kept", "scales-met", "footer", "provenance"]
    vol = en.enumerate_checked(checked)
    contract = next(i for i in vol["nodes"] if i["id"] == "P:contract/p.1")
    assert contract["move"] == "plainly" and contract["summary"] == "What plainly must leave true of what it gives."
    move = next(i for i in vol["nodes"] if i["id"] == "P:move/plainly")
    assert move["order"] == 1 and move["params"] == [{"name": "f", "type": "fabula"}]


# ---------------------------------------------------------------------------
# use (section 8.4)
# ---------------------------------------------------------------------------

@pytest.fixture
def house(tmp_path) -> Path:
    (tmp_path / "house.thym").write_text(V + "morph rosa\n  why: the house voice.\n  person-voice 3\nend\n\n"
                                         "move plainly(f: fabula): short\n  give tell f as told with rosa\nend\n")
    (tmp_path / "voices.morph.cosm").write_text(
        "oes: thym/1\nkind: morph\nid: thym/voices\nname: voices\nnodes:\n"
        "  - {id: M:morph/rosa, type: morph, name: rosa, summary: Rosa.}\n"
        "  - {id: M:morph/plain, type: morph, name: plain, summary: Plain.}\n")
    return tmp_path


def _write(folder: Path, name: str, text: str) -> Path:
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


def test_use_of_a_sibling_file_brings_its_moves_and_morphs(house):
    p = _write(house, "main.thym", "thym 0\nuse house.thym\n\nprogram brief\n  takes t: text\n  gives s: short\n"
               "  let f = derive t\n  give plainly f\nend\n")
    checked = thym.check_file(p)
    assert isinstance(checked, ck.Checked), checked
    assert set(checked.moves) == {"plainly"} and "rosa" in checked.names
    vol = en.enumerate_file(p)
    step = next(i for i in vol["nodes"] if i["id"] == "P:step/brief.2")
    assert step["calls"] == ["plainly", "tell"] and step["asks"] is True
    assert vol["front"] == "thym 0\nuse house.thym\n\n"


def test_use_of_a_thym_volume_brings_its_morphs_and_contexts(house):
    p = _write(house, "vol.thym", "thym 0\nuse oes:thym/voices\n\nprogram brief\n  takes t: text\n  gives s: short\n"
               "  give tell (derive t) as told with plain\nend\n")
    assert isinstance(thym.check_file(p), ck.Checked)
    text = "thym 0\nuse oes:thym/house\n\nprogram p\n  takes t: text\n  gives s: short\n" \
           "  give tell (derive t) as told with rosa\nend\n"
    assert isinstance(compile_text(text, volumes={"oes:thym/house": HOUSE}), ck.Checked)
    assert isinstance(compile_text(text, volumes=lambda uri: HOUSE if uri == "oes:thym/house" else None), ck.Checked)


def test_use_clash_names_both_files(house):
    p = _write(house, "clash.thym", "thym 0\nuse house.thym\nuse oes:thym/voices\n\nprogram brief\n"
               "  gives n: number\n  give 0\nend\n")
    r = thym.check_file(p)
    assert (r.check, r.line) == ("use-clash", 3) and "house.thym" in r.message and "voices.morph.cosm" in r.message
    p = _write(house, "local.thym", "thym 0\nuse oes:thym/voices\n\nmorph plain\n  humour 2\nend\n")
    r = thym.check_file(p)
    assert (r.check, r.line) == ("use-clash", 2) and "local.thym" in r.message


@pytest.mark.parametrize("uri", ["oes:thym/nowhere", "missing.thym", "oes:emf/notes-md", "oes:thym/voices/M/morph/rosa"])
def test_unknown_uri(house, uri):
    p = _write(house, "u.thym", f"thym 0\nuse {uri}\n\nprogram p\n  gives n: number\n  give 0\nend\n")
    r = thym.check_file(p)
    assert (r.stage, r.check, r.line) == ("compile", "unknown-uri", 2), str(r)


# ---------------------------------------------------------------------------
# Plans beyond the fixtures (section 11.1)
# ---------------------------------------------------------------------------

def test_largest_prompt_and_the_run_id():
    checked = thym.check_file(SUITE / "programs" / "publish-story.thym")
    inputs = [{"name": "story", "type": "text", "path": "inputs/notes.md", "sha256": "5" * 64, "size": 1228}]
    when = dt.datetime(2026, 11, 1, 10, 42)
    plan = pl.plan(checked, inputs, now=when)
    joined = en.sha256(checked.module.text.encode()) + "5" * 64
    rid = f"2026-11-01-1042-{hashlib.sha256(joined.encode()).hexdigest()[:4]}"
    assert plan["id"] == f"thym/{rid}" and plan["nodes"][0]["id"] == f"R:plan/{rid}"
    assert plan["estimate"]["largest_prompt"] == 1228 // 4 == plan["nodes"][0]["largest_prompt"]
    assert pl.normalise(plan)["estimate"]["largest_prompt"] == 0


def test_a_loop_over_a_written_list_unrolls_and_a_call_less_give_is_a_node():
    checked = ok(V + "program p\n  takes f: fabula\n  gives f2: fabula\n  for each o in [told, weight]\n"
                 "    tell f as told\n  end\n  give f\nend\n")
    plan = pl.plan(checked, [{"name": "f", "type": "fabula", "path": "f.cosm", "sha256": "0" * 64}])
    nodes = plan["nodes"][1:]
    assert [n["move"] for n in nodes] == ["tell", "tell", "give"]
    assert not any(n.get("repeats") for n in nodes)
    assert nodes[-1]["gives"] == "f2"


def test_plan_refuses_a_file_with_no_program_and_wrong_inputs():
    checked = ok(V + "morph m\n  humour 2\nend\n")
    r = pl.plan(checked, [])
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "no-program")
    checked = thym.check_file(SUITE / "programs" / "publish-story.thym")
    r = pl.plan(checked, [{"name": "story", "type": "fabula", "path": "x", "sha256": "0" * 64}])
    assert isinstance(r, Refusal) and r.check == "input"


# ---------------------------------------------------------------------------
# Declarations, types and contracts (sections 6.3, 7.3, 17.6)
# ---------------------------------------------------------------------------

def _table_rows(section: str, until: str) -> list[str]:
    text = _text(SPEC)
    part = text[text.index(section):text.index(until)]
    return re.findall(r"^\| `([a-z-]+)` \|", part, re.M)


def test_declarations_load_from_the_real_manifests():
    decls = dc.load()
    assert decls.problems == []
    assert set(decls) == set(_table_rows("### 6.3 The standard moves", "The accessors are read-only"))
    tell = decls["tell"]
    assert tell.owner == "emf" and tell.asks is True and tell.takes == (("fabula", "item", "volume"),)
    assert list(tell.modifiers) == ["as", "by", "with"] and tell.modifiers["with"] == ("morph",)
    assert decls["band"].modifiers["as"] == ("list of word",) and decls["band"].owner == "comprise"
    assert decls["cut"].modifiers["to"] == ("words", "sentences")
    assert decls["null"].takes == () and decls["null"].modifiers["of"] == ("fabula",)
    assert decls["mark"].gives == ("item", "word")
    assert dc.load() is not dc.load()                   # each caller gets its own copy


def test_a_manifest_block_wins_over_a_sidecar_and_a_move_declared_twice_is_reported(tmp_path):
    for p in mc.DEFAULT_MANIFEST_DIR.glob("*.cosm"):
        shutil.copy(p, tmp_path / p.name)
    (tmp_path / "emf.moves.cosm").write_text("moves-of: emf/1\nmoves:\n  - {name: retell, takes: [fabula], "
                                             "gives: short, says: again}\n")
    (tmp_path / "zzz.moves.cosm").write_text("moves-of: zzz/1\nmoves:\n  - {name: tell, takes: [text], "
                                             "gives: short, says: twice}\n")
    decls = dc.load(mc.Registry([tmp_path]))
    assert "retell" not in decls and decls["tell"].owner == "emf"
    joined = " | ".join(decls.problems)
    assert "emf.moves.cosm" in joined and "tell is declared again" in joined


def test_types_accept_by_density_and_never_coerce():
    assert ty.accepts(["fabula", "item", "volume"], "fabula")
    assert not ty.accepts(["fabula"], "text") and ty.hint("text", ["fabula"]) == "derive it first"
    assert ty.accepts(["volume", "list"], "list of item")
    assert ty.accepts(["order"], "word", word="told") and not ty.accepts(["order"], "word", word="verified")
    assert ty.accepts(["isotype", "paratype"], "word", word="isotype")
    assert ty.accepts(["morph"], "nothing") and not ty.accepts(["fabula"], "nothing")
    assert ty.parse_type("list of  list of word") == "list of list of word" and ty.parse_type("lists") is None
    assert ty.alternatives("'fabula | item'".strip("'")) == ["fabula", "item"]


def test_the_contracts_constant_equals_the_table_of_section_7_3():
    assert list(ct.CHECKS) == _table_rows("### 7.3 The named checks", "### 7.4")
    every = {c for d in dc.load().values() for c in d.contract}
    assert every <= set(ct.CHECKS)
    compile_row = next(ln for ln in _text(SPEC).splitlines() if ln.startswith("| **compile** |"))
    named = re.findall(r"\(`([a-z-]+)`\)", compile_row)
    assert set(ct.COMPILE) == set(named) and set(ct.STATIC) <= set(ct.CHECKS)


def test_bad_input_never_raises():
    for text in ("", "thym", "thym 0\nprogram", "thym 0\nprogram p\n  let x = (\n", "\x00\x01", "thym 0\n" + "(" * 500,
                 'thym 0\nprogram p\n  give "unterminated\nend\n', "thym 0\nprogram p\n  give 3.5\nend\n"):
        r = compile_text(text)
        assert isinstance(r, Refusal) and r.stage == "compile" and r.check in ct.COMPILE
