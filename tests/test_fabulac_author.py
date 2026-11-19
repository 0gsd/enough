"""Authoring a fabulac (0.8, fabulac-first F1: pins section 4; MacroCOSM OES 18.4.1, 18.4.7, 18.6.6; Thym 6.3, 7.3,
20.11): the authored source and `program` in the manifest; the bank chosen by `source` and asked one stage at a time;
`enough/fabulac_author_job.py`, begun from a brief or from nothing and taken up from disk; the moves of
`enough/thym/moves/author.py` and `defaults/thym/author-python.thym`; the twin guard; an authored fabulac that passes
its checks.

No model is asked except where a scripted one stands in. The person's answers are recorded answers (sittings written
beside the fabulac by `answer`, as the page and the `dialectic` tool write them). Every seam points inside tmp_path
(conftest).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula
from enough import fabulac_author_job as A
from enough import fabulac_job as F
from enough import macrocosm as mc
from enough import thym_host as H
from enough.canon_derive import DeriveCancelled
from enough.thym import Refusal
from enough.thym import checks as ck
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import plan as pl
from enough.thym.contracts import AHEAD, AHEAD_MOVES
from enough.thym.coprocessor import candidate
from enough.thym.moves import author as AU
from enough.thym.values import Value
from tests.test_thym_code import engines
from tests.test_thym_shipped import compile_with

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
REPO = Path(__file__).resolve().parents[1]

BRIEF = """# tally

A small command that counts the words in a text file and prints the number.

## For whom

- People who write notes in plain text and want a quick count.

## Ways in

- tally count PATH prints the number of words in the file at PATH.

## Leaves out

- It does not count words in other languages' scripts specially.

## Cases

- Given a file notes.md holding "one two three", tally count notes.md prints 3.

## Something else

A passage under a heading the rules do not know.
"""


class Placer:
    """A scripted model for `author`'s one request: it places passage 1 as an audience, and tries to say more."""

    def __init__(self) -> None:
        self.sent: list = []

    def complete(self, contract, inputs, *, budget, **_kw):
        if contract.get("move") != "author":
            return candidate("questions: []", engine="model:scripted-1", tokens=5)   # `question`: none of its own
        self.sent.append((contract, inputs))
        return candidate("placed:\n  - {passage: 1, entry: audience}\n  - {passage: 9, entry: aim}\n"
                         "rewritten: a model's own words", engine="model:scripted-1", tokens=5)


def runtime(cp=None):
    def make(stage, plan, info, mode, scaffolds, program):
        from enough.thym.coprocessor import RefusingCoprocessor
        return {"coprocessor": cp if (mode == "model" and cp is not None) else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if mode == "model" else {},
                "root": H.host_root(), "engines": engines(), "calls": None}
    return make


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


def doc(project: Path, name: str = "tally") -> dict:
    return mc.yaml_load((project / f"{name}.fabulac.cosm").read_text(encoding="utf-8"))


def led(project: Path, name: str = "tally"):
    return dl.open_twin(project / f"{name}.fabulac.cosm").ledger


# The recorded answers: by the bank entry a question was raised from, else by the field it asks about.
BY_ENTRY = {
    "aim": "Count the words of a text file and print how many there are.",
    "audience": "People who keep their notes in plain text.",
    "use": "Count a file: run tally count with its path, read the number.",
    "occasion": "I wanted a count without opening an editor.",
    "licence": "MIT",
    "way-in": "tally count PATH",
    "signature": "tally count PATH",
    "needs": None,                     # declined: it needs nothing else
    "python": "3.11",
    "setting": "TALLY_MIN, the shortest word counted",
    "left-out": "It never counts words inside code blocks differently.",
    "must": "It must print the count and nothing else on success.",
    "case": "notes.md holding one two three gives 3",
    "open": None,
}
BY_FIELD = {"surface": "command", "set-in": "environment", "given": "tally count notes.md, notes.md holding one two three",
            "expect": "3, then a newline; exit 0"}


def answers_for(L, qs: list[dict], *, at: dt.datetime) -> list[dict]:
    out = []
    for q in qs:
        frm = str((q.get("raised") or {}).get("from") or "")
        entry = frm.split("/", 1)[1] if frm.startswith(f"{AU.BANK}/") else None
        about = str(q.get("about") or "")
        field = about.partition("#")[2]
        if entry == "checked-by":
            case = next(i["id"] for i in L.items if str(i.get("id", "")).startswith("P:case/"))
            out.append({"question": q["id"], "value": case, "says": case})
        elif entry is not None:
            said = BY_ENTRY[entry]
            out.append({"question": q["id"], "declined": True} if said is None else
                       {"question": q["id"], "says": said})
        elif field == "of":
            iface = next(i["id"] for i in L.items if str(i.get("id", "")).startswith("C:interface/"))
            out.append({"question": q["id"], "says": iface, "value": iface})
        elif field in BY_FIELD:
            out.append({"question": q["id"], "says": BY_FIELD[field]})
        else:
            out.append({"question": q["id"], "dont_know": True})
    return out


def interview(project: Path, *, rounds: int = 20, seen: list | None = None, **kw) -> dict:
    """Begin (or take up) and answer, a sitting at a time, until every stage has landed."""
    at = NOW
    r = A.run_author(project, "tally", runtime=runtime(kw.pop("cp", None)), now=at, **kw)
    for _ in range(rounds):
        if r["complete"]:
            return r
        L = led(project)
        qs = [q for q in L.questions() if q.get("state") == "open"]
        if seen is not None:
            seen.append(sorted({dl.stage_of_question(L, q) or "-" for q in qs}))
        at = at + dt.timedelta(minutes=1)
        A.answer(project, "tally", answers_for(L, qs, at=at), at=at)
        r = A.run_author(project, "tally", runtime=runtime(), now=at)
    raise AssertionError(f"the interview did not end: {r['message']}")


def lint_ok(project: Path) -> None:
    rep = fabula.lint(project / "tally.fabulac.cosm")
    assert rep.errors == [], [str(p) for p in rep.errors]


# ---------------------------------------------------------------------------
# The format: the authored source, program, and the bank chosen by source
# ---------------------------------------------------------------------------

def test_the_manifest_declares_the_authored_source_and_program():
    m = mc.default_registry().get("fabula")
    cat = m._block("catalog")
    assert "program" in cat["keys"] and cat["keys"].index("program") == cat["keys"].index("derived") + 1
    assert cat["source-kind"] == ["text", "folder", "authored"]
    assert cat["source-authored-fields"] == ["kind", "language", "licence", "by", "at", "brief"]
    assert cat["program-fields"] == ["kind", "start", "serve"] and cat["program-kind"] == ["tool", "library", "service"]


def _banks(catalog: dict) -> list[str]:
    L = dl.ledger_from_items(mc.default_registry().get("fabula"), [], catalog=catalog)
    return [b["name"] for b in dl.banks_for(L)]


def test_banks_are_chosen_by_source_and_no_other_bank_moves():
    fabulac = {"oes": "fabula/1", "flavour": "fabulac", "id": "fabula/x", "name": "x"}
    assert _banks({**fabulac, "source": {"kind": "authored", "language": "python"}}) == ["fabulac-authored"]
    assert _banks({**fabulac, "source": {"kind": "folder", "path": "x/"}}) == ["fabulac"]
    assert _banks(fabulac) == ["fabulac"]                                      # a standalone fabulac
    assert _banks({**fabulac, "purpose": "transconception", "source": {"kind": "folder", "path": "x/"}}) == [
        "fabulac", "transconception-standing", "transconception-target", "transconception-rulings"]
    assert _banks({"oes": "fabula/1", "flavour": "fabulan", "id": "fabula/t", "name": "t",
                   "source": {"path": "t.md"}}) == ["fabulan"]
    assert _banks({"oes": "fabula/1", "flavour": "fabulap", "id": "fabula/p", "name": "p"}) == ["fabulap"]
    assert dl.source_word({}) == "none" and dl.source_word({"source": {"path": "t.md"}}) == "text"
    assert dl.BANK_FOR["source"](dl.ledger_from_items(mc.default_registry().get("fabula"), [],
                                                      catalog={"source": {"kind": "authored"}})) == "authored"


def test_the_bank_carries_the_interview_order():
    assert AU.stages() == ["for", "ways-in", "needs", "left-out", "cases", "open"]
    e = {x["id"]: x for x in AU.bank_entries()}
    assert all(isinstance(x.get("writes"), str) for x in e.values() if "#" not in x["about"] and ":" not in x["about"])
    assert e["must"]["sets"] == {"force": "must"} and e["case"]["writes"] == "case"


# ---------------------------------------------------------------------------
# A brief, read by rules
# ---------------------------------------------------------------------------

def test_a_brief_is_read_by_its_headings_and_the_rest_is_named():
    placed, unplaced = AU.read_brief(BRIEF)
    got = [(e["id"], p["text"]) for e, p in placed]
    assert got[0] == ("aim", "A small command that counts the words in a text file and prints the number.")
    assert ("audience", "People who write notes in plain text and want a quick count.") in got
    assert ("way-in", "tally count PATH prints the number of words in the file at PATH.") in got
    assert [e for e, _t in got] == ["aim", "audience", "way-in", "left-out", "case"]
    assert [(p["heading"], p["first"]) for p in unplaced] == [("Something else", 23)]
    assert AU.title_of(BRIEF) == "tally"
    items = AU.brief_items(placed, [], "tally.brief.md")
    assert all(i["stance"] == "axiom" and i["provenance"]["mode"] == "structured-intake" for i in items)
    assert items[2]["id"].startswith("C:interface/") and items[2]["surface"]["pending"]
    assert items[0]["provenance"]["sources"] == ["tally.brief.md#L3"]


# ---------------------------------------------------------------------------
# The job: from a brief and from nothing, stage by stage, to a fabulac that passes its checks
# ---------------------------------------------------------------------------

def test_from_a_brief_by_rules_to_a_fabulac_that_passes_its_checks(project):
    (project / "tally.brief.md").write_text(BRIEF, encoding="utf-8")
    seen: list = []
    first = A.run_author(project, "tally", brief="tally.brief.md", licence=None, by="Ada", mode="rules",
                         runtime=runtime(), now=NOW)
    assert A.AGENT_FREE_WORDS in first["message"]
    assert first["ran"][0]["brief"]["placed"] == 5 and len(first["ran"][0]["brief"]["unplaced"]) == 1
    d = doc(project)
    assert d["source"]["kind"] == "authored" and d["source"]["brief"] == "tally.brief.md"
    assert d["source"]["by"] == ["R:maker/ada"] and d["program"] == {"kind": "tool", "start": ["-m", "tally"]}
    # what the brief answered is not asked again: no aim, audience, way-in, left-out or case question
    L = led(project)
    asked = {str((q.get("raised") or {}).get("from")) for q in L.questions()}
    assert not asked & {f"{AU.BANK}/{e}" for e in ("aim", "audience", "way-in", "left-out", "case")}
    r = interview(project, seen=seen)
    assert r["complete"] and r["state"]["next"] == "done"
    d = doc(project)
    assert d["source"]["licence"] == "MIT"                        # the interview's licence, carried into the catalog
    for n in d["nodes"]:
        if str(n["id"]).startswith("D:"):
            continue
        assert n["stance"] == "axiom", n["id"]
        assert n["provenance"]["mode"] in ("structured-intake", "manual", "dialectic"), n["id"]
    brief_text = " ".join(BRIEF.split())
    for n in d["nodes"]:
        if (n.get("provenance") or {}).get("mode") == "structured-intake":
            assert " ".join(n["summary"].split()) in brief_text
    assert any(n["id"].startswith("N:use/") and n["provenance"]["mode"] == "dialectic" for n in d["nodes"])
    lint_ok(project)
    chk = A.check(project, "tally")
    assert chk["ok"] and chk["source"] == [] and chk["uncovered"] == []
    runs = [x["program"] for x in d["derived"]["runs"]]
    assert runs[0] == "begin-the-catalog" and "settle-the-answers" in runs and "raise-the-questions" in runs


def test_from_nothing_one_stage_at_a_time(project):
    seen: list = []
    r = interview(project, seen=seen, mode="rules")
    assert r["complete"]
    d = doc(project)
    assert d["name"] == "tally" and "brief" not in d["source"] and d["source"]["licence"] == "MIT"
    # the person met one stage at a time, in the bank's order (pending fields are asked with no stage: "-")
    stages_met = [s for row in seen for s in row if s != "-"]
    order = AU.stages()
    assert stages_met == sorted(stages_met, key=order.index)
    assert all(len({s for s in row if s != "-"}) <= 1 for row in seen), seen
    assert set(stages_met) == {"for", "ways-in", "needs", "left-out", "cases", "open"}
    assert doc(project)["derived"]["runs"][0]["program"] == "begin-by-interview"
    kinds = {n["id"].split("/")[0] for n in d["nodes"]}
    assert {"N:aim", "N:audience", "N:use", "C:interface", "C:setting", "N:requirement", "P:case"} <= kinds
    req = next(n for n in d["nodes"] if n["id"].startswith("N:requirement/"))
    assert req["force"] == "must" and str(req["checked-by"]).startswith("P:case/")
    lint_ok(project)


def test_each_step_lands_whole_and_the_job_takes_up_again_after_a_stop(project):
    fab = project / "tally.fabulac.cosm"
    first = A.run_author(project, "tally", mode="rules", runtime=runtime(), now=NOW)
    assert first["state"]["next"] == "answer" and first["state"]["stage"] == "for"
    assert [r["step"] for r in first["ran"]] == ["begin"]
    assert 1 <= len(first["waiting"]) <= A.SHOWN                    # one or two at a time
    L = led(project)
    at = NOW + dt.timedelta(minutes=1)
    A.answer(project, "tally", answers_for(L, [q for q in L.questions() if q.get("state") == "open"], at=at), at=at)
    assert A.author_state(project, fab)["next"] == "settle"         # the sitting waits beside it
    before = fab.read_bytes()
    with pytest.raises(DeriveCancelled):                            # stopped before anything ran: nothing written
        A.run_author(project, "tally", runtime=runtime(), now=at, should_stop=lambda: True)
    assert fab.read_bytes() == before
    def after_one_step() -> bool:
        return fab.read_bytes() != before                           # once the settle has landed
    with pytest.raises(DeriveCancelled):                            # the settle lands whole, then the stop
        A.run_author(project, "tally", runtime=runtime(), now=at, should_stop=after_one_step)
    st = A.author_state(project, fab)
    assert st["next"] == "raise" and st["stages"][0]["landed"] and not st["stages"][1]["landed"]
    assert all(q.get("settled") for q in led(project).questions())
    r = A.run_author(project, "tally", runtime=runtime(), now=at)  # taken up from disk: the next stage is raised
    assert [x["step"] for x in r["ran"]] == ["raise"]
    assert r["state"]["next"] == "answer" and r["state"]["stage"] == "ways-in"


def test_a_run_refused_midway_writes_nothing(project, monkeypatch):
    A.run_author(project, "tally", mode="rules", runtime=runtime(), now=NOW)
    L = led(project)
    at = NOW + dt.timedelta(minutes=1)
    A.answer(project, "tally", answers_for(L, [q for q in L.questions() if q.get("state") == "open"], at=at), at=at)
    before = (project / "tally.fabulac.cosm").read_bytes()
    from enough import dialectic_api
    monkeypatch.setattr(dialectic_api, "settle_fabula",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("settle was refused (test)")))
    with pytest.raises(RuntimeError):
        A.run_author(project, "tally", runtime=runtime(), now=at)
    assert (project / "tally.fabulac.cosm").read_bytes() == before
    monkeypatch.undo()
    r = A.run_author(project, "tally", runtime=runtime(), now=at)
    assert r["state"]["stage"] == "ways-in"


LINECOUNT_BRIEF = """# linecount

linecount says how many lines a text file holds.

## For whom

People who keep notes in plain text files.

## Ways in

- the command `linecount PATH`

## Leaves out

- It does not count words.

## Must

- It never writes a file.
"""


def test_a_worded_answer_to_an_unsure_question_does_not_loop_at_settle(project):
    """W5-F7's find: begun from a brief agent-free, "Yes, that is right." to `D:question/ada-unsure` left the job
    settling for ever ("stopped after 40 steps"): a whole-item answer in words waits for a model to read the item
    again, and the job kept choosing settle. A plain yes now confirms the item by rules; a correction waits for a
    model without holding the rest of the interview."""
    (project / "brief.md").write_text(LINECOUNT_BRIEF, encoding="utf-8")
    r = A.run_author(project, "linecount", brief="brief.md", licence="MIT", by="Ada", mode="rules",
                     runtime=runtime(), now=NOW)
    L = led(project, "linecount")
    opened = {q["id"] for q in L.questions() if q.get("state") == "open"}
    assert {"D:question/ada-unsure", "D:question/licence-unsure"} <= opened, opened
    at = NOW + dt.timedelta(minutes=1)
    A.answer(project, "linecount", [{"question": "D:question/ada-unsure", "says": "Yes, that is right."},
                                    {"question": "D:question/licence-unsure",
                                     "says": "No: the terms are Apache-2.0, not MIT."}], at=at)
    r = A.run_author(project, "linecount", runtime=runtime(), now=at)
    assert "stopped after" not in r["message"], r["message"]
    assert len(r["ran"]) < 5
    L = led(project, "linecount")
    ada = L.question("D:question/ada-unsure")
    assert ada.get("settled") and ada["settled"]["wrote"] == ["R:maker/ada"]
    maker = next(i for i in L.items if i.get("id") == "R:maker/ada")
    assert maker["provenance"].get("state") != "pending" and maker["provenance"]["confidence"] == 1
    assert not L.question("D:question/licence-unsure").get("settled")          # a correction waits for a model
    assert r["state"]["reading"] == ["D:question/licence-unsure"] and r["state"]["next"] == "answer"
    assert "wait" in r["message"] and "for a model" in r["message"]
    assert not any(q.get("about") == "R:maker/ada" and q.get("state") == "open" for q in L.questions())


def test_only_a_plain_yes_confirms():
    assert dl._confirms("Yes, that is right.") and dl._confirms("yes") and dl._confirms("Correct.")
    assert dl._confirms("Yep, that's right")
    assert not dl._confirms("Yes, but it was Bob") and not dl._confirms("No") and not dl._confirms("")
    assert not dl._confirms("It was Bob, yes")


def test_with_a_model_the_text_s_program_runs_and_the_model_only_places(project):
    (project / "tally.brief.md").write_text(BRIEF, encoding="utf-8")
    cp = Placer()
    r = A.run_author(project, "tally", brief="tally.brief.md", licence="MIT", mode="model", runtime=runtime(cp),
                     now=NOW)
    assert len(cp.sent) == 1                                        # one request: the passage the rules left
    d = doc(project)
    assert d["derived"]["runs"][0]["program"] == "begin-from-a-brief" and d["source"]["licence"] == "MIT"
    placed = [n for n in d["nodes"] if (n.get("provenance") or {}).get("confidence") == AU.PLACED_CONFIDENCE]
    assert [(n["id"], n["summary"]) for n in placed] == [
        ("N:audience/a-passage-under-a-heading-the", "A passage under a heading the rules do not know.")]
    assert "a model's own words" not in (project / "tally.fabulac.cosm").read_text(encoding="utf-8")
    assert r["state"]["next"] == "answer"


def test_begin_refuses_a_fabulac_or_a_folder_already_there(project):
    (project / "tally").mkdir()
    (project / "tally" / "a.py").write_text("x = 1\n")
    with pytest.raises(A.AuthorError, match="tally/ is there already"):
        A.run_author(project, "tally", mode="rules", runtime=runtime(), now=NOW)
    assert not (project / "tally.fabulac.cosm").exists()


# ---------------------------------------------------------------------------
# The twin guard
# ---------------------------------------------------------------------------

def test_the_builder_refuses_to_decompile_an_authored_fabulac_s_folder(project):
    A.run_author(project, "tally", mode="rules", runtime=runtime(), now=NOW)
    (project / "tally").mkdir()                                     # as an entailment would land it
    (project / "tally" / "__init__.py").write_text("")
    before = (project / "tally.fabulac.cosm").read_bytes()
    with pytest.raises(F.BuildError) as e:
        F.run_build(project, project / "tally", mode="rules", now=NOW)
    assert str(e.value) == ("tally.fabulac.cosm is authored; tally/ is its entailment. Entail again, or take a hand "
                            "edit back") and e.value.status == 409
    assert (project / "tally.fabulac.cosm").read_bytes() == before
    folder, fab = F.target_of(project, "tally")                     # the status and a cancel still name it
    assert fab.name == "tally.fabulac.cosm" and F.authored_twin(folder) == fab


# ---------------------------------------------------------------------------
# The moves and the program
# ---------------------------------------------------------------------------

#: Thym 6.3's rows for the authoring moves (v080-texts), until the sync brings them into docs/THYM.md.
TEXT_ROWS = {"author": (True, ["authored-source", "fabula-checks", "provenance"]),
             "add": (False, ["authored-source", "nothing-lost", "ids-unique", "fabula-checks", "provenance"]),
             "compare": (False, []), "uncovered": (False, [])}


def test_the_moves_are_declared_as_the_text_s_rows():
    d = dc.load()
    assert set(TEXT_ROWS) <= set(AHEAD_MOVES) and "authored-source" in AHEAD
    for name, (asks, contract) in TEXT_ROWS.items():
        v = d[name].view(1)
        assert d[name].since == 1 and d[name].view(0) is None
        assert v.asks is asks and list(v.contract) == contract, name
    assert dc.chosen(d["author"].view(1), first_type="text")["scaffold"] is None
    assert dc.chosen(d["author"].view(1))["scaffold"] == AU.SCAFFOLD
    assert d["compare"].view(1).gives == ("report",) and d["uncovered"].view(1).gives == ("list of item",)


def test_the_program_compiles_plans_and_enumerates_with_two_ways_in():
    path = REPO / "defaults" / "thym" / "author-python.thym"
    text = path.read_text(encoding="utf-8")
    c = compile_with(text, dc.load(), str(path))
    assert not isinstance(c, Refusal), str(c)
    assert [p.name for p in c.programs()] == ["begin-from-a-brief", "begin-by-interview", "state-a-requirement",
                                              "ready-to-entail"]
    for prog in c.programs():
        plan = pl.plan(c, [{"name": p.name, "type": p.type, "path": f"{p.name}.in", "sha256": "0" * 64}
                           for p in prog.takes], program=prog.name)
        assert not isinstance(plan, Refusal), (prog.name, str(plan))
    assert en.compile_volume(en.enumerate_checked(c)) == text
    # the cosmoes-site text, when it is here, holds the same block byte for byte
    site = Path("/Users/m3u/METMcloud/cosmoes-site/specs/thym.md")
    if site.is_file() and "### 20.11 Authoring a fabulac" in site.read_text(encoding="utf-8"):
        assert text in site.read_text(encoding="utf-8")


def _run(project: Path, program: str, rows: list[dict], *, prog: Path | str | None = None, rules: bool = True):
    from enough.thym import run as R
    path = prog or REPO / "defaults" / "thym" / "author-python.thym"
    checked = compile_with(path.read_text(encoding="utf-8") if isinstance(path, Path) else path, dc.load())
    plan = pl.plan(checked, rows, program=program, inputs_root=project)
    assert not isinstance(plan, Refusal), str(plan)
    eng = {**engines(), AU.ENGINE: lambda: {"name": "tally", "licence": "MIT"}}
    return R.run(plan, inputs_root=project, program=path, rules=rules, engines=eng, now=NOW, root=H.host_root())


def test_add_compare_and_uncovered_by_the_text_s_programs(project):
    A.run_author(project, "tally", mode="rules", runtime=runtime(), now=NOW)
    fab = project / "tally.fabulac.cosm"
    from enough.thym.values import digest_path
    said = project / "said.txt"
    said.write_text("It must print the count and nothing else.", encoding="utf-8")
    t = _run(project, "state-a-requirement",
             [{"name": "f", "type": "fabula", "path": str(fab), "sha256": digest_path(fab)},
              {"name": "said", "type": "string", "path": str(said), "sha256": digest_path(said)}])
    assert not isinstance(t, Refusal) and t.landed, getattr(t, "refusal", t)
    g = mc.yaml_load(Path(t.outputs["g"]).read_text(encoding="utf-8"))
    new = [n for n in g["nodes"] if n["id"].startswith("N:requirement/")]
    assert len(new) == 1 and new[0]["provenance"]["mode"] == "manual" and new[0]["stance"] == "axiom"
    assert new[0]["summary"] == "It must print the count and nothing else." and new[0]["force"]["pending"]
    # ready-to-entail: a requirement of force must with no case is refused by its assert
    out = Path(t.outputs["g"])
    musty = mc.yaml_load(out.read_text(encoding="utf-8"))
    for n in musty["nodes"]:
        if n["id"] == new[0]["id"]:
            n["force"] = "must"
    out2 = project / "musty.fabulac.cosm"
    out2.write_text(mc.dump(musty), encoding="utf-8")
    r = _run(project, "ready-to-entail", [{"name": "f", "type": "fabula", "path": str(out2),
                                           "sha256": digest_path(out2)}])
    refusal = r if isinstance(r, Refusal) else r.refusal
    assert refusal is not None and "has no case" in str(refusal.message)
    assert [d["id"] for d in AU.uncovered_items(musty["nodes"])] == [new[0]["id"]]
    rep = AU.compare_docs(doc(project), g, {n["id"]: n for n in doc(project)["nodes"]},
                          {n["id"]: n for n in g["nodes"]})
    assert rep["only-in-second"] == [new[0]["id"]] and rep["only-in-first"] == []


def test_add_takes_only_an_authored_fabulac():
    f = Value("fabula", {"oes": "fabula/1", "flavour": "fabulac", "id": "fabula/x", "name": "x",
                         "source": {"kind": "folder", "path": "x/"}, "nodes": []})
    with pytest.raises(Exception, match="add takes only an authored fabulac"):
        AU.add(None, Value("string", "It must count."), **{"as": "requirement", "with": f})


def test_authored_source_refuses_what_its_author_did_not_say():
    cat = AU.begin("tally", at="2026-11-20T12:00:00Z")
    ok = ck.verdict("authored-source", Value("fabula", cat), {}, {}, None)
    assert ok == (True, "")
    brief = Value("text", "# tally\n\nCounts words.\n")
    bad = dict(cat, nodes=[*cat["nodes"], {"id": "N:aim/x", "type": "aim", "name": "x", "summary": "Sings songs.",
                                           "stance": "axiom",
                                           "provenance": {"mode": "structured-intake", "sources": [], "confidence": 1}}])
    got = ck.verdict("authored-source", Value("fabula", bad), {"brief": brief}, {}, None)
    assert got[0] is False and "says what the brief does not" in got[1]
    hearsay = dict(cat, nodes=[*cat["nodes"][:2], dict(cat["nodes"][2], stance="hearsay")])
    assert ck.verdict("authored-source", Value("fabula", hearsay), {}, {}, None)[0] is False
    no_kind = dict(cat, program={})
    assert "program names a kind" in ck.verdict("authored-source", Value("fabula", no_kind), {}, {}, None)[1]


def test_the_paradigm_names_the_calls_of_the_flow():
    text = (REPO / "defaults" / "paradigms" / "transcognition.md").read_text(encoding="utf-8")
    part = text[text.index("# Toward a codebase"):text.index("# Other fabulas")]
    for word in ("begin", "status", "add", "check", "entail", "test", "run", "stop", "moved"):
        assert re.search(rf"<do>{word}</do>", part), word
    assert "<brief>" in part and "`dialectic`" in part
    trans = text[text.index("# Transconception"):text.index("## What it asks")]
    for call in ("ground repo with f", "weigh f in go", "entail f as cases", "gather recorded with f",
                 "entail f as layout in go", "gather verdict with f"):
        assert call in trans, call
