"""The editor and the helpers of `thym 1` (THYM 6.3, 7.3, 20.2, 20.6, 21, 22.1): `lines`, `replace`, `drop`, `insert`,
`edit` under `only-the-changed`, `reword` under `length`, `one-line` and `nothing-added`, `join`, `say`, `folders`,
`gather` under `nothing-lost` and `ids-unique`, and `count` and `words` grown; their declarations in `thym/1`'s
manifest, which a `thym 0` program never sees.

Moves are called directly where the point is the move, and through runs (scripted coprocessors stand in for a model)
where the point is what a person sees; runs land under tmp_path (the conftest's seams).
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
from enough.thym import declarations as dc
from enough.thym import folder as F
from enough.thym import parse as ps
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym import trace as T
from enough.thym.coprocessor import candidate
from enough.thym.moves import MoveError
from enough.thym.moves import edit as E
from enough.thym.registry import Amount
from enough.thym.values import Value, digest_path, make_change, sha256_bytes

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
TWIN = SUITE / "inputs" / "notes.md.cosm"
TOOL = SUITE / "inputs" / "little-tool"
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)
FORBIDDEN = re.compile(r"\bt\d+\b|\bnode \d+\b|R:node/|Error\b|Exception\b|operand\d")
NEW = ("gather", "question", "record", "settle", "lines", "replace", "drop", "insert", "edit", "reword", "join", "say",
       "folders")


def text(s: str, kind: str = "text") -> Value:
    return Value(kind, s)


def lines_of(v: Value) -> list[Value]:
    return E.lines(None, of=v).payload


def run_text(tmp_path: Path, program: str, inputs: dict[str, tuple[str, Path]], **kw):
    """Plan and run a program written into tmp_path, its inputs `{name: (type, path)}`."""
    p = tmp_path / "p.thym"
    p.write_text(program, encoding="utf-8")
    rows = [{"name": n, "type": t, "path": str(path), "sha256": digest_path(path)} for n, (t, path) in inputs.items()]
    plan = thym.plan_file(p, rows)
    assert not isinstance(plan, Refusal), plan
    t = RUN.run(plan, inputs_root=tmp_path, root=tmp_path / "root", program=p, engines=H.engines(feed=None), now=NOW,
                **kw)
    assert isinstance(t, T.Trace), t
    return t


# ---------------------------------------------------------------------------
# lines, replace, drop, insert
# ---------------------------------------------------------------------------

def test_lines_gives_every_line_numbered_with_its_place():
    v = text("# 3.2 The orchard\n\nThe apples came in.\n")
    ls = lines_of(v)
    assert [x.payload for x in ls] == ["# 3.2 The orchard", "", "The apples came in."]
    head, blank, prose = (x.origin["line"] for x in ls)
    assert (head["number"], head["level"], head["title"], head["blank"]) == (1, 1, "The orchard", False)
    assert (blank["number"], blank["blank"], prose["level"], prose["title"]) == (2, True, 0, None)
    assert all(x.origin["line"]["source"] == v.sha256 for x in ls)
    assert prose["sha256"] == sha256_bytes(b"The apples came in.")
    assert ls[0].field("level") == 1 and ls[2].field("number") == 3


def test_lines_of_a_short_and_of_crlf_and_a_last_line_without_a_break():
    assert [x.payload for x in lines_of(text("one\r\ntwo", "short"))] == ["one", "two"]
    assert lines_of(text("")) == []
    with pytest.raises(MoveError, match="lines reads a text or a short, and was given a fabula"):
        E.lines(None, of=Value("fabula", {"nodes": []}))


def test_replace_drop_and_insert_make_changes():
    v = text("a\nb\nc\n")
    a, b, _c = lines_of(v)
    ch = E.replace(None, b, **{"with": text("x\ny", "short")}).payload
    assert ch == {"at": 2, "was": sha256_bytes(b"b"), "of": v.sha256, "do": "replace", "lines": ["x", "y"]}
    assert E.drop(None, a).payload["do"] == "drop"
    assert E.insert(None, Value("string", "z"), before=b).payload == {
        "at": 2, "was": sha256_bytes(b"b"), "of": v.sha256, "do": "insert-before", "lines": ["z"]}
    assert E.insert(None, b, after=a).payload["lines"] == ["b"]            # a line fits where a string is taken


@pytest.mark.parametrize("mods", [{}, {"before": "b", "after": "b"}])
def test_insert_takes_exactly_one_of_before_and_after(mods):
    b = lines_of(text("a\nb\n"))[1]
    with pytest.raises(MoveError, match=r"^insert takes before <line> or after <line>, exactly one of the two$"):
        E.insert(None, Value("string", "z"), **{k: b for k in mods})


def test_a_change_is_made_of_a_line_read_with_lines():
    with pytest.raises(MoveError, match="replace names a line read with lines of a text or a short"):
        E.replace(None, Value("string", "loose"), **{"with": Value("string", "x")})


# ---------------------------------------------------------------------------
# edit and only-the-changed
# ---------------------------------------------------------------------------

DRAFT = "# Notes\nkeep one\nTODO two\nkeep three\nTODO four\n"


def changes(*cs: Value) -> Value:
    return Value("list", list(cs))


def test_edit_applies_every_change_at_once_and_gives_the_same_type():
    v = text(DRAFT)
    h, k1, t2, _k3, t4 = lines_of(v)
    cs = changes(E.drop(None, t2), E.replace(None, t4, **{"with": Value("string", "done four")}),
                 E.insert(None, Value("string", "after one"), after=k1),
                 E.insert(None, Value("string", "first"), before=h),
                 E.insert(None, Value("string", "second"), before=h))
    out = E.edit(None, v, **{"with": cs})
    assert out.type == "text" and out.payload == "first\nsecond\n# Notes\nkeep one\nafter one\nkeep three\ndone four\n"
    assert E.edit(None, text(DRAFT, "short"), **{"with": changes()}).type == "short"
    ok, why = E._only_the_changed(out, {"s": v, "with": cs}, {}, None, None)
    assert (ok, why) == (True, "")


def test_edit_keeps_every_line_break_and_a_last_line_without_one():
    v = text("a\r\nb\r\nc")
    *_ab, c = lines_of(v)
    out = E.edit(None, v, **{"with": changes(E.replace(None, c, **{"with": Value("string", "C")}),
                                               E.insert(None, Value("string", "d"), after=c))})
    assert out.payload == "a\r\nb\r\nC\r\nd"
    out = E.edit(None, v, **{"with": changes(E.drop(None, c))})
    assert out.payload == "a\r\nb"


@pytest.mark.parametrize("make, words", [
    (lambda ls, other: [E.drop(None, lines_of(other)[1])], "a change names line 2 of another text"),
    (lambda ls, other: [E.drop(None, ls[1]), E.drop(None, ls[1])], "line 2 is dropped twice"),
    (lambda ls, other: [E.replace(None, ls[1], **{"with": Value("string", "x")}),
                        E.replace(None, ls[1], **{"with": Value("string", "y")})], "line 2 is replaced twice"),
    (lambda ls, other: [E.replace(None, ls[1], **{"with": Value("string", "x")}), E.drop(None, ls[1])],
     "line 2 is both replaced and dropped"),
    (lambda ls, other: [make_change(9, "0" * 64, ls[0].origin["line"]["source"], "drop")],
     "a change names line 9, and the text has 5 lines"),
    (lambda ls, other: [make_change(2, "0" * 64, ls[0].origin["line"]["source"], "drop")],
     "line 2 changed since it was read"),
])
def test_edit_refuses_changes_that_cannot_hold_in_plain_words(make, words):
    v = text(DRAFT)
    cs = changes(*make(lines_of(v), text("other\nlines\n")))
    with pytest.raises(MoveError) as e:
        E.edit(None, v, **{"with": cs})
    assert str(e.value) == words and not FORBIDDEN.search(words)
    assert E._only_the_changed(text("x\n"), {"draft": v, "with": cs}, {}, None, None) == (False, words)


@pytest.mark.parametrize("cheat, words", [
    ("# Notes\nkeep ONE\nkeep three\nTODO four\n", "line 2 of draft, which no change names, differs in the output"),
    ("# Notes\nkeep one\nkeep three\nTODO four\nsomething new\n",
     "the output holds a line that neither draft nor a change gave: something new"),
    ("# Notes\nkeep one\nkeep three\n", "line 5 of draft, which no change names, is missing from the output"),
    ("# Notes\nkeep one\nDONE two\nkeep three\nTODO four\n", "line 3 is not what its change says"),
    ("# Notes\r\nkeep one\nkeep three\nTODO four\n", "the output's line breaks are not draft's"),
])
def test_only_the_changed_catches_every_kind_of_cheat(cheat, words):
    """An implementation that alters an untouched line, adds one, drops one no change names, or does not do what a
    change says is caught by the contract's fourth condition (THYM 21.3)."""
    v = text(DRAFT)
    ls = lines_of(v)
    cs = changes(E.replace(None, ls[2], **{"with": Value("string", "done two")}) if "DONE" in cheat else
                 E.drop(None, ls[2]))
    assert E._only_the_changed(text(cheat), {"draft": v, "with": cs}, {}, None, None) == (False, words)


DROP_THE_TODOS = (SUITE / "programs" / "drop-the-todos.thym").read_text(encoding="utf-8")


def test_drop_the_todos_runs_and_leaves_its_source_as_it_was(tmp_path):
    src = tmp_path / "draft.md"
    src.write_text(DRAFT, encoding="utf-8")
    before = src.read_bytes()
    t = run_text(tmp_path, DROP_THE_TODOS, {"draft": ("text", src)})
    assert t.landed, t.refusal
    assert t.outputs["clean"].read_text(encoding="utf-8") == "# Notes\nkeep one\nkeep three\n"
    assert src.read_bytes() == before and t.outputs["clean"].resolve() != src.resolve()
    rec = next(r for r in t.records if r["move"] == "edit")
    assert [(c["name"], c["ok"]) for c in rec["checks"]] == [("only-the-changed", True), ("never-source", True),
                                                            ("provenance", True)]


def test_a_change_made_from_one_text_is_refused_on_another_in_the_programs_words(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text(DRAFT, encoding="utf-8")
    b.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    prog = DROP_THE_TODOS.replace("takes draft: text", "takes draft: text, other: text").replace(
        "give edit draft with changes", "give edit other with changes")
    t = run_text(tmp_path, prog, {"draft": ("text", a), "other": ("text", b)})
    assert not t.landed and not (t.dir / "outputs").exists()
    msg = t.refusal.message
    assert msg == "give edit other with changes (line 12): a change names line 3 of another text; a change names " \
                  "line 5 of another text", msg
    assert not FORBIDDEN.search(msg)


def test_two_changes_to_one_line_are_refused_at_run(tmp_path):
    src = tmp_path / "draft.md"
    src.write_text(DRAFT, encoding="utf-8")
    prog = DROP_THE_TODOS.replace("    keep drop l\n", '    keep drop l\n    keep replace l with "done"\n')
    t = run_text(tmp_path, prog, {"draft": ("text", src)})
    assert not t.landed
    assert t.refusal.message == ("give edit draft with changes (line 13): line 3 is both replaced and dropped; line 5 "
                                 "is both replaced and dropped")


@pytest.mark.parametrize("place,said", [("", "neither"), (" before l after l", "both")])
def test_an_insert_with_no_place_or_both_is_refused_at_compile_in_its_own_words(tmp_path, place, said):
    """The text gives `insert` exactly one of `before` and `after` (THYM 4.5, 21): the compiler refuses a call that
    writes neither or both (`type`), in the move's own words, before anything runs. (Called directly, the move still
    refuses the same way: `test_insert_takes_exactly_one_of_before_and_after`.)"""
    p = tmp_path / "p.thym"
    p.write_text(DROP_THE_TODOS.replace("keep drop l", f'keep insert "x"{place}'), encoding="utf-8")
    r = thym.check_file(p)
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("compile", "type")
    assert "insert takes before <line> or after <line>, exactly one of the two" in r.message
    assert r.message.endswith(f"says {said}") and not FORBIDDEN.search(r.message)
    p.write_text(DROP_THE_TODOS.replace("keep drop l", 'keep insert "x" after l'), encoding="utf-8")
    assert not isinstance(thym.check_file(p), Refusal)


# ---------------------------------------------------------------------------
# reword, one-line, nothing-added; tighten
# ---------------------------------------------------------------------------

TIGHTEN = (REPO / "defaults" / "thym" / "tighten.thym").read_text(encoding="utf-8")
LONG = SUITE / "inputs" / "long-lines.md"
APPLES_LONG = ("The apples came in early this year, and the cider press in the long barn ran for nine whole days, "
               "from the first cold morning until the last of the late fruit was gone.\n")
APPLES = ("The apples came in early this year, and the cider press in the long barn ran for nine days, until the "
          "last of the late fruit was gone.\n")
BEES = ("The bees stayed all summer in the wild strip by the south wall, where nobody mowed; the parish counted more "
        "of them there than in any other part.\n")


class Scripted:
    def __init__(self, answers: list[str]) -> None:
        self.answers, self.sent = list(answers), []

    def complete(self, contract, inputs, *, budget):
        self.sent.append({"move": contract.get("move"), "failed": [dict(f) for f in contract["repair"]["failed"]],
                          "line": inputs["line"][0].text()})
        return candidate(self.answers.pop(0), engine="model:scripted", tokens=40)


def tighten(tmp_path: Path, answers: list[str]):
    cp = Scripted(answers)
    p = tmp_path / "tighten.thym"
    p.write_text(TIGHTEN, encoding="utf-8")
    plan = thym.plan_file(p, [{"name": "s", "type": "short", "path": str(LONG), "sha256": digest_path(LONG)}])
    assert not isinstance(plan, Refusal), plan
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=p, coprocessor=cp,
                engines=H.engines(feed=None), now=NOW)
    return t, cp


def test_tighten_is_the_text_byte_for_byte_and_the_suites():
    shipped = (REPO / "defaults" / "thym" / "tighten.thym").read_text(encoding="utf-8")
    assert shipped in _text_blocks()
    assert (SUITE / "programs" / "tighten.thym").read_text(encoding="utf-8") == shipped


def test_tighten_re_asks_a_reword_that_fails_its_contract_and_moves_no_other_line(tmp_path):
    t, cp = tighten(tmp_path, [APPLES_LONG, APPLES, BEES])
    assert t.landed, t.refusal
    failed = [{"name": "length", "ok": False, "why": "34 words, more than 30"}]
    assert [s["failed"] for s in cp.sent] == [[], failed, []]
    assert cp.sent[0]["line"].startswith("The apples") and cp.sent[2]["line"].startswith("The bees")
    out = t.outputs["t"].read_text(encoding="utf-8")
    want = LONG.read_text(encoding="utf-8").split("\n")
    assert out.split("\n") == [want[0], want[1], APPLES.strip(), want[3], want[4], BEES.strip(), ""]
    loop = t.records[0]
    assert loop["tries"] == [{"attempt": 1, "failed": [{"name": "length", "why": "34 words, more than 30"}]}]
    assert {c["name"] for c in loop["checks"]} >= {"length", "one-line", "nothing-added", "shorter"}


def test_tighten_refused_when_every_attempt_fails(tmp_path):
    t, cp = tighten(tmp_path, [APPLES_LONG] * 3)
    assert not t.landed and len(cp.sent) == 3 and not (t.dir / "outputs").exists()
    msg = t.refusal.message
    assert msg == ("keep replace l with tightened l (line 22, for l = line 3): reword still fails length after 3 "
                   "attempts: 34 words, more than 30"), msg
    assert not FORBIDDEN.search(msg)


def test_the_recorded_tighten_replays_to_its_outputs(tmp_path):
    runs = sorted((SUITE / "replay" / "tighten").glob("*/"))
    assert len(runs) == 1
    again = RUN.replay(runs[0], root=tmp_path / "root", inputs_root=SUITE, engines=H.engines(feed=None))
    assert again.replay["identical"], again.replay
    cands = sorted(p.name for p in (runs[0] / "candidates").glob("*.cosm"))
    assert cands == ["1-1.1.cosm", "1.1.cosm", "1.2.cosm"]                   # one re-ask, then the second line


def test_reword_asks_for_one_line_and_repairs_an_answer_of_several():
    line = lines_of(text("a\n" + APPLES_LONG))[1]
    req = E.reword(None, line, to=Amount(30, "words"))
    assert req.contract["repair"] == ["one-line"] and req.inputs["words"].payload == 30
    v = req.parse("The apples came in early this year,\nand the press ran for nine days.\n")
    assert v.type == "line" and v.origin["line"]["number"] == 2
    assert E._one_line(v, {"l": line}, {}, None, None) == (False, "the reworded line is 2 lines, not one")
    fixed = req.repair(v, [{"name": "one-line", "ok": False, "why": "x"}])
    assert fixed.payload == "The apples came in early this year, and the press ran for nine days."
    assert E._one_line(fixed, {"l": line}, {}, None, None) == (True, "")
    assert req.repair(v, [{"name": "length", "ok": False, "why": "x"}]) is None
    assert E.reword(None, Value("string", "x y"), to=Amount(5, "words")).parse("x\n").type == "string"
    with pytest.raises(MoveError, match="reword needs a length: reword l to N words"):
        E.reword(None, line)


def test_reword_one_line_through_a_run_joins_the_lines(tmp_path):
    two = APPLES.replace(" and the cider", "\nand the cider")
    t, _cp = tighten(tmp_path, [two, BEES])
    assert t.landed, t.refusal
    assert APPLES.strip() in t.outputs["t"].read_text(encoding="utf-8")


@pytest.mark.parametrize("out, feed, verdict", [
    ("The press ran nine days.", None, (True, "")),
    ("The press ran 12 days.", None, (False, "the number 12 is not in what was reworded")),
    ("The press at Hollins ran nine days.", None, (False, "the name Hollins is not in what was reworded")),
    ("The press ran nine splendid days.", None,
     (True, "FEED is not here; only names and numbers were held to what was reworded")),
    ("The press ran nine splendid days.", {"splendid": {"word": "splendid"}}, (True, "")),
    ("The press ran nine glorbish days.", {}, (False, "the word glorbish is in neither FEED nor what was reworded")),
])
def test_nothing_added_holds_names_numbers_and_words_outside_feed_to_the_input(out, feed, verdict):
    class Ctx:
        engines = {} if feed is None else {"feed": lambda words: {w.lower(): feed.get(w.lower()) for w in words}}

    src = Value("line", "The cider press ran for nine days in the barn.")
    got = E._nothing_added(Value("line", out), {"l": src, "with": Value("morph", {})}, {}, None, Ctx())
    assert got == verdict


def test_the_reword_prompt_builder_is_registered_and_names_the_length():
    assert E.PROMPTS["reword"] is E.reword_messages and R.MOVES.prompt("reword") is not None
    line = Value("line", APPLES_LONG.strip())
    req = E.reword(None, line, to=Amount(30, "words"))
    msgs = E.reword_messages({"move": "reword"}, {k: (v, v.sha256) for k, v in req.inputs.items()})
    assert msgs[0]["role"] == "system" and "at most 30 words, and no fewer than 24" in msgs[0]["content"]
    assert "on one line" in msgs[0]["content"] and msgs[1]["content"] == f"The line:\n{APPLES_LONG.strip()}"


# ---------------------------------------------------------------------------
# join, say, folders, count, words
# ---------------------------------------------------------------------------

def test_join_say_and_the_grown_count_and_words():
    xs = Value("list", [Value("string", "a.py"), Value("line", "b"), Value("short", "c\nd\n")])
    assert E.join(None, xs).payload == "a.py\nb\nc\nd\n"
    assert E.join(None, Value("list", [Value("string", "## "), Value("string", "1")]),
                  **{"with": Value("string", "")}).payload == "## 1\n"
    assert E.join(None, Value("list", [])).payload == ""
    assert [E.say(None, v).payload for v in (Value("number", 12), Value("bool", False), Value("word", "told"),
                                             Value("date", dt.date(2026, 11, 5)))] == ["12", "false", "told",
                                                                                      "2026-11-05"]
    assert E.words(None, Value("line", "The apples came in.")).payload == 4
    assert E.words(None, Value("string", "two words")).payload == 2
    folder = Value("folder", F.read(TOOL, path="little-tool/"))
    assert E.count(None, folder).payload == len(folder.payload.texts()) == folder.payload.files - 1   # one binary
    subs = E.folders(None, of=folder).payload
    assert [s.payload.path for s in subs] == [f.path for f in folder.payload.folders()] and subs
    assert all(s.type == "folder" for s in subs)


PYTHON_FILES = """thym 1

program python-files
  why: the Python files of a folder, one line each with its length in lines.

  takes repo: folder
  gives listing: short

  let rows = for each t in repo where suffix is py
    keep join [t.path, (say t.lines)] with " · "
  end
  give join rows
end
"""


def test_python_files_of_the_text_runs_over_a_folder(tmp_path):
    t = run_text(tmp_path, PYTHON_FILES, {"repo": ("folder", TOOL)})
    assert t.landed, t.refusal
    got = t.outputs["listing"].read_text(encoding="utf-8").splitlines()
    f = F.read(TOOL)
    want = [f"{e.path} · {f.member_fields(e)['lines']}" for e in f.texts() if e.suffix == "py"]
    assert got == want and want


# ---------------------------------------------------------------------------
# gather: the fabulac build's join, and the dialectic's landing
# ---------------------------------------------------------------------------

def fabula(*items: dict, name: str = "f") -> Value:
    return Value("fabula", {"oes": "fabula/1", "id": f"fabula/{name}", "name": name, "nodes": list(items)})


A = {"id": "C:file/a.py", "type": "file", "name": "a.py", "summary": "the file a.py"}
B = {"id": "C:behaviour/a-adds", "type": "behaviour", "name": "adds", "summary": "a adds two numbers"}
C2 = {"id": "C:behaviour/b-adds", "type": "behaviour", "name": "adds", "summary": "b adds two numbers"}
Q = {"id": "D:question/aim", "type": "question", "name": "aim", "summary": "what is it for", "state": "open"}


def test_gather_lands_every_reading_in_the_fabula_so_far():
    base = fabula(A)
    readings = Value("list", [fabula(A, B, name="r1"), fabula(A, C2, name="r2")])
    out = E.gather(None, readings, **{"with": base})
    assert out.type == "fabula" and [n["id"] for n in out.payload["nodes"]] == [A["id"], B["id"], C2["id"]]
    assert out.payload["id"] == "fabula/f"                           # the with volume's catalog
    inputs = {"readings": readings, "with": base}
    assert E._nothing_lost(out, inputs, {}, None, None) == (True, "")
    assert E._ids_unique(out, inputs, {}, None, None) == (True, "")


I = {"id": "C:interface/a.add", "type": "interface", "name": "add", "summary": "adds", "surface": "function",
     "signature": "def add(x: int, y: int = 1) -> int", "takes": [{"name": "x", "type": "int"}, {"name": "y",
                                                                                                "default": "1"}],
     "raises": [{"error": "ValueError", "message": "x must be positive"}], "provenance": {"mode": "derived",
                                                                                         "sources": ["a.py#L3-L9"]}}


def test_gather_merges_what_a_reading_adds_to_the_outlines_own_item():
    enrich = {"id": I["id"], "takes": [{"name": "x", "means": "the first number"}, {"name": "y", "means": "the step"}],
              "gives": {"type": "int", "means": "x plus y"},
              "raises": [{"error": "ValueError", "message": "x must be positive", "when": "x is 0 or less"},
                         {"error": "TypeError", "when": "x is not a number"}],
              "provenance": {"sources": ["a.py#L5"]}, "made": {"move": "derive", "run": "r"}}
    base = fabula(I)
    parts = Value("list", [fabula(enrich, name="r")])
    out = E.gather(None, parts, **{"with": base})
    (got,) = out.payload["nodes"]
    assert got["takes"] == [{"name": "x", "type": "int", "means": "the first number"},
                            {"name": "y", "default": "1", "means": "the step"}]
    assert got["raises"][0]["when"] == "x is 0 or less" and got["raises"][1]["error"] == "TypeError"
    assert got["provenance"]["sources"] == ["a.py#L3-L9", "a.py#L5"] and got["gives"]["means"] == "x plus y"
    assert E._nothing_lost(out, {"parts": parts, "with": base}, {}, None, None) == (True, "")
    assert E._ids_unique(out, {}, {}, None, None) == (True, "")
    for bad, field in ((dict(enrich, signature="def add(x)"), "its signature is read by rules"),
                       ({"id": I["id"], "takes": [{"name": "y"}, {"name": "x"}]}, "takes[0].name differs"),
                       ({"id": I["id"], "raises": []}, "raises holds 1 entries")):
        with pytest.raises(E.MoveError, match=field.replace("[", r"\[").replace("]", r"\]")):
            E.gather(None, Value("list", [fabula(bad, name="r")]), **{"with": base})
    answered = fabula(dict(I, gives={"pending": "what does add give?"}))
    out = E.gather(None, Value("list", [fabula({"id": I["id"], "gives": {"type": "int"}}, name="r")]),
                   **{"with": answered})
    assert out.payload["nodes"][0]["gives"] == {"type": "int"}           # an open question answered


def test_gather_lands_questions_in_a_fabula_and_in_a_volume():
    asked = Value("list", [Value("item", Q), Value("item", dict(Q))])
    out = E.gather(None, asked, **{"with": fabula(A)})
    assert [n["id"] for n in out.payload["nodes"]] == [A["id"], Q["id"]]
    vol = Value("volume", {"oes": "comprise/1", "id": "x", "nodes": [A]})
    out = E.gather(None, asked, **{"with": vol})
    assert out.type == "volume" and len(out.payload["nodes"]) == 2
    assert E._nothing_lost(out, {"asked": asked, "with": vol}, {}, None, None) == (True, "")


def test_ids_unique_and_nothing_lost_catch_what_gather_must_never_do():
    clash = dict(B, summary="a subtracts")
    with pytest.raises(E.MoveError, match="C:behaviour/a-adds: its summary is read by rules"):
        E.gather(None, Value("list", [fabula(clash, name="r")]), **{"with": fabula(A, B)})
    twice = fabula(A, B, dict(B, summary="a subtracts"))
    assert E._ids_unique(twice, {}, {}, None, None) == (False, "two different items share the id C:behaviour/a-adds")
    lost = fabula(A)
    assert E._nothing_lost(lost, {"readings": Value("list", [fabula(B, name="r")]), "with": fabula(A)}, {}, None,
                           None) == (False, "C:behaviour/a-adds, of readings, is not in the output")
    changed = fabula(dict(A, summary="another"))
    assert E._nothing_lost(changed, {"readings": Value("list", []), "with": fabula(A)}, {}, None, None) == (
        False, "C:file/a.py, of the volume gathered into, is in the output changed")
    stamped = fabula(dict(A, made={"move": "gather", "run": "r"}))           # made written by the runtime is no change
    assert E._nothing_lost(stamped, {"with": fabula(A)}, {}, None, None) == (True, "")
    again = E.gather(None, Value("list", [fabula(A, name="r")]), **{"with": stamped})
    assert len(again.payload["nodes"]) == 1                                   # one item, made aside


GATHER = """thym 1

program gather-back
  why: the claims of a fabula gathered back into it, and the fabula twice: nothing changes.

  takes f: fabula
  gives g: fabula

  let claims = for each i in f where kind is claim
    keep i
  end
  let twice = for each x in [f, f]
    keep x
  end
  let once = gather twice with f
  give gather claims with once
end
"""


def test_gather_runs_under_its_contract_and_loses_nothing(tmp_path):
    t = run_text(tmp_path, GATHER, {"f": ("fabula", TWIN)})
    assert t.landed, t.refusal
    recs = [r for r in t.records if r["move"] == "gather"]
    assert len(recs) == 2 and all(c["ok"] for r in recs for c in r["checks"]), recs
    assert {c["name"] for c in recs[0]["checks"]} == {"nothing-lost", "ids-unique", "fabula-checks", "provenance"}


# ---------------------------------------------------------------------------
# The declarations: thym/1's manifest
# ---------------------------------------------------------------------------

def test_every_new_move_is_declared_by_thym_1_since_1_and_thym_0_sees_none():
    d = dc.load()
    assert not d.problems, d.problems
    for name in NEW:
        assert d[name].owner == "thym" and d[name].since == 1, name
        assert name not in d.view(0) and name in d.view(1)
        want = "dialectic" if name in ("question", "record", "settle") else "edit"
        assert d[name].code == f"enough.thym.moves.{want}:{name}"
    assert d["count"].view(0).takes == (("volume", "fabula", "short", "list"),)
    assert d["count"].view(1).takes == (("volume", "fabula", "short", "list", "folder"),)
    assert d["words"].view(0).takes == (("text", "short", "atem"),)
    assert d["words"].view(1).takes == (("text", "short", "atem", "line", "string"),)


def test_the_declarations_are_the_texts_table():
    """THYM 6.3's second table, row by row (and design 3.2's, which `test_thym_shipped` copies as scratch)."""
    d = dc.load().view(1)
    row = {n: (d[n].takes, d[n].gives, dict(d[n].modifiers), d[n].asks, d[n].contract, d[n].scaffold) for n in NEW}
    assert row["gather"] == ((("list of fabula", "list of item"),), ("same-as-with",), {"with": ("fabula", "volume")},
                             False, ("nothing-lost", "ids-unique", "fabula-checks", "provenance"), None)
    assert row["question"] == ((("fabula", "volume"),), ("list of item",), {}, True,
                               ("addressed", "no-duplicate", "provenance"), "bank")
    assert row["record"] == ((("volume",),), ("same-as-in",), {"in": ("fabula", "volume")}, False,
                             ("addressed", "only-the-asked", "provenance"), None)
    assert row["settle"][3:] == (True, ("addressed", "only-the-asked", "fabula-checks", "provenance"), "direct")
    assert row["lines"] == ((), ("list of line",), {"of": ("text", "short")}, False, (), None)
    assert row["replace"] == ((("line",),), ("change",), {"with": ("string", "line", "short")}, False, (), None)
    assert row["insert"][2] == {"before": ("line",), "after": ("line",)}
    assert row["edit"][4] == ("only-the-changed", "never-source", "provenance")
    assert row["reword"][2:5] == ({"to": ("words",), "with": ("morph",)}, True,
                                  ("length", "one-line", "nothing-added", "provenance"))
    assert row["join"][1:] == (("short",), {"with": ("string",)}, False, ("provenance",), None)
    assert row["folders"] == ((), ("list of folder",), {"of": ("folder",)}, False, (), None)
    for name, first, gives in [("edit", "text", "text"), ("edit", "short", "short"), ("reword", "line", "line"),
                               ("reword", "string", "string"), ("settle", "volume", "volume")]:
        assert dc.chosen(d[name], first_type=first)["gives"] == (gives,), (name, first)


def test_a_declared_move_whose_module_is_not_there_never_breaks_loading():
    """The dialectic's `code:` names a module its lane writes; until it lands, `load_all` reports it and raises
    nothing, and every other move still loads."""
    mv = R.MOVES.copy()
    decl = dict(dc.load())
    decl["settle"] = dc.dataclasses.replace(decl["settle"], code="enough.thym.moves.not_here:settle")
    problems = R.load_all(decl, moves=mv)
    assert "settle: enough.thym.moves.not_here: ModuleNotFoundError: No module named 'enough.thym.moves.not_here'" \
        in problems
    assert all(p.startswith(("question: enough.thym.moves.dialectic", "record: enough.thym.moves.dialectic"))
               for p in problems if "not_here" not in p), problems
    assert all(mv.lookup(n) is not None for n in NEW if n not in ("question", "record", "settle"))


@pytest.mark.parametrize("body, words", [
    ("  let ls = lines of t\n  give count ls\n", "the move lines, which thym 1 declares at line 8"),
    ('  give words "a b"\n', 'words "a b" (a string), which thym 1 allows at line 8'),
])
def test_a_thym_0_program_cannot_see_the_new_moves(body, words):
    src = f"thym 0\n\nprogram p\n  why: x.\n  takes t: text\n  gives n: number\n\n{body}end\n"
    m = ps.parse(src)
    r = m if isinstance(m, Refusal) else ck.check(m)
    assert isinstance(r, Refusal) and r.check == "version"
    assert r.message == f"this needs `thym 1`: {words}; the first line says thym 0"


def _text_blocks() -> list[str]:
    """Every ```thym block of the synced text, docs/THYM.md, as a program file holds it."""
    import re as _re
    text = (Path(__file__).resolve().parents[1] / "docs" / "THYM.md").read_text(encoding="utf-8")
    return [b for b in _re.findall(r"^```thym\n(.*?)^```", text, _re.S | _re.M)]
