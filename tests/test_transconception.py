"""Transconception (0.8, phase 1): the schema in the fabula manifest, the thirteen checks and the two gates of
enough/transconception.py, and the experiment's two working fabulacs promoted as fixtures.

Held here: both promoted fabulacs are grounded with 0.8's ground catalogue (`promote_x0.py --ground`, 2026-11-19; the
owner's ruling in pins 25: every reliance the ground raised is `kept`) and lint with no error. `stands-alone` holds
since the grounding: what vulture named of Python, its runtime or a dependency in seven items (nine findings) and
sloppy-xml-py in one is now said by a reliance that stands behind it (tests/test_ground.py holds W1-X1's list). So
gate 1 (ready to keep) holds for both, every check measured, with the sources at hand when this machine has them
(without them `nothing-carried` is not measured and says so). Gate 2 holds for Go and for Rust: `ruled` holds for
both targets since sitting 2 (2026-11-18, the fifth allowance `own-types`) and pins 25, and `target-confirmed` holds
on A7's hand weighings, which the promoter gives a row by `weigh`'s rules for each reliance the ground raised after
them. A fabulac nobody could rule is kept unruled; each check, on a small fabulac that passes all of them, made to
fail; every other fabula untouched.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from enough import fabula
from enough import macrocosm as M
from enough import transconception as tc

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula" / "transconception"
VULTURE = FIX / "vulture.fabulac.cosm"
SLOPPY = FIX / "sloppy-xml-py.fabulac.cosm"
TALLY = REPO / "tests" / "fixtures" / "fabula" / "tally.fabulac.cosm"
# The cloned originals, read as text by nothing-carried when this machine has them (never run).
CLONES = Path("/Users/m3u/METMcloud/fabulac-test-repos")


def _errors(rep: M.Report, check: str | None = None) -> list[str]:
    return [str(p) for p in rep.errors if check is None or p.check == check]


# ---------------------------------------------------------------------------
# the promoted fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vols():
    return {p.name: M.load_volume(p) for p in (VULTURE, SLOPPY)}


# The reliances 0.8's ground raised in each promoted fabulac (pins 25). Before, stands-alone found W1-X1's nine
# findings in vulture and one in sloppy-xml-py (tests/test_ground.py's STANDS_ALONE_FIXED holds that list).
GROUND_RAISED = {"vulture.fabulac.cosm": 67, "sloppy-xml-py.fabulac.cosm": 34}
TARGET = {"vulture.fabulac.cosm": "go", "sloppy-xml-py.fabulac.cosm": "rust"}
GROUND_SAID = ("pins 25: the reliances 0.8's ground catalogue raised in the experiment's fabulacs are kept, as "
               "proposed, recorded as the owner's")


def ground_raised(v: M.Volume) -> list[str]:
    """The reliances 0.8's ground raised in a promoted fabulac: those carrying a catalogue `entry`."""
    return [i for i, it in v.items.items() if i.startswith("C:reliance/") and it.data.get("entry")]


def test_the_promoted_fabulacs_lint_with_no_error(vols):
    for name, v in vols.items():
        assert v.catalog["purpose"] == "transconception" and v.catalog["ruled-by"] == "R:maker/transconceiver"
        rep = fabula.lint(v)
        assert _errors(rep) == [], (name, _errors(rep)[:10])
        assert not [p for p in rep.problems() if p.check == "stands-alone"]
        assert not [c for c in rep.not_run if c in tc.CHECKS]


def test_the_ground_reliances_carry_the_owners_ruling_of_pins_25(vols):
    for name, v in vols.items():
        raised = ground_raised(v)
        assert len(raised) == GROUND_RAISED[name]
        for rid in raised:
            assert v.items[rid].data["ruling"] == [{"is": "kept", "by": "R:maker/transconceiver", "on": "2026-11-19",
                                                    "said": GROUND_SAID}], (name, rid)
        maker = v.items["R:maker/transconceiver"].data
        assert maker["ruled-in"][-1] == "enough-dev docs/v080-pins.md section 25 (2026-11-19, by questionnaire)"
        assert v.catalog["source"]["swhid"]["rev"] == f"swh:1:rev:{v.catalog['source']['commit']}"
        assert v.catalog["derived"]["runs"][-1]["program"] == "ground"
        # the experiment's own reliances stay as x0 wrote them
        assert not [i for i, it in v.items.items() if ("/V-R" in i or "/S-R" in i) and it.data.get("entry")]


def test_a7s_weighings_gain_a_row_by_rules_for_each_ground_reliance_and_name_their_gaps(vols):
    """A7 weighed every reliance x0 wrote; the promoter adds, for each reliance the ground raised, the row `weigh`'s
    rules give it (`answered: rules`), and changes no row A7 wrote. A7's verdict names vulture's gaps in Go in a
    numbered list; the promoter writes them on the rows (and `weigh`'s rule on the one other library row);
    sloppy-xml-py's verdict into Rust names none."""
    for name, v in vols.items():
        t = v.items[f"N:target/{TARGET[name]}"].data
        rows = {r["for"]: r for r in t["provides"]}
        raised = ground_raised(v)
        assert set(raised) <= set(rows)
        assert all(rows[r]["answered"] == "rules" for r in raised)
        assert not [r for f, r in rows.items() if f not in raised and "answered" in r]      # A7's rows as written
        assert t["provenance"]["sources"][-1].startswith("rows for the reliances 0.8's ground raised")
    gaps = {f: r["gap"] for f, r in ((r["for"], r) for r in vols["vulture.fabulac.cosm"].items["N:target/go"].data[
        "provides"]) if r.get("gap") and "answered" not in r}
    assert gaps == {
        "C:reliance/V-R02": "The parser of the input language's 3.13 grammar, type comments included (written)",
        "C:reliance/V-R03": "The command-line reader's conventions (written)",
        "C:reliance/V-R08": "The TOML 1.0 reader (library)",
        "C:reliance/V-R14": "library: sort.SliceStable with full lower-casing from golang.org/x/text/cases",
        "C:reliance/V-R19": "Identifiers normalised to NFKC (library)",
        "C:reliance/V-R27": "The parser of the input language's 3.13 grammar, type comments included (written)"}
    assert not [r for r in vols["sloppy-xml-py.fabulac.cosm"].items["N:target/rust"].data["provides"]
                if r.get("gap") and "answered" not in r]


def _catalogue_examples() -> set[str]:
    from enough import languages as L
    return {str(e["example"]) for e in L.entries("python") if e.get("example")}


def test_the_fixtures_carry_no_old_word_and_no_machine_path():
    """No path on the machine that recorded x0 (the promoter writes those from the home folder). A ground reliance
    carries its catalogue entry's `example` whole, and one example is about a home folder (`/home/ann`): that text is
    the catalogue's own, so it is left out of the search only where it is the entry's example, byte for byte."""
    examples = _catalogue_examples()
    for p in (VULTURE, SLOPPY):
        doc = M.yaml_load(p.read_text(encoding="utf-8"))
        for n in doc["nodes"]:
            if isinstance(n.get("entry"), str) and isinstance(n.get("example"), str):
                assert n["example"] in examples, (p.name, n["id"])
                n["example"] = ""
        text = M.dump(doc)
        for bad in ("transcoder", "transcoding", "/Users/", "/home/"):
            assert bad not in text, (p.name, bad)
    for lic in ("vulture.LICENSE.txt", "sloppy-xml-py.LICENSE"):
        assert (FIX / lic).is_file()
    assert "Jendrik Seipp" in (FIX / "vulture.LICENSE.txt").read_text(encoding="utf-8")
    assert "Apache License" in (FIX / "sloppy-xml-py.LICENSE").read_text(encoding="utf-8")


def test_ready_to_keep_without_the_sources_measures_all_but_nothing_carried(vols):
    for v in vols.values():
        g = tc.ready_to_keep(v)
        assert g["do-not-hold"] == [] and g["not-measured"] == ["nothing-carried"]
        assert g["hold"] == [c for c in tc.READY_TO_KEEP if c != "nothing-carried"]
        assert not g["holds"]
        assert "source folder" in g["checks"]["nothing-carried"]["why"]


@pytest.mark.parametrize("fix, clone", [(VULTURE, "vulture"), (SLOPPY, "sloppy-xml-py")])
def test_ready_to_keep_holds_with_the_sources(fix, clone):
    """The experiment measured gate 1 as holding, with stands-alone's items "left open"; as an error they stopped it
    until 0.8's ground stood behind them (pins 25). Every check holds now, the source read as text."""
    if not (CLONES / clone).is_dir():
        pytest.skip("the cloned original is not on this machine")
    g = tc.ready_to_keep(fix, source=CLONES / clone)
    assert g["holds"] and g["says"] == "ready to keep", g["do-not-hold"]
    assert g["do-not-hold"] == [] and g["not-measured"] == []
    assert g["hold"] == list(tc.READY_TO_KEEP)


@pytest.mark.parametrize("fix, clone, language", [(VULTURE, "vulture", "go"), (SLOPPY, "sloppy-xml-py", "rust")])
def test_ready_to_entail_holds_with_the_sources(fix, clone, language):
    """Sitting 2 (2026-11-18) ruled `own-types` onto the closed list, so `ruled` holds for Rust as for Go, and pins 25
    keeps the ground's reliances. A7's hand weighings, with the ground's rows by rules, give `target-confirmed` a row
    for every reliance kept; each spike's level is read from O9's verdict on it. Gate 2 holds."""
    if not (CLONES / clone).is_dir():
        pytest.skip("the cloned original is not on this machine")
    g = tc.ready_to_entail(fix, language, source=CLONES / clone)
    assert g["holds"] and g["do-not-hold"] == [] and g["not-measured"] == [], g["do-not-hold"]
    for c in ("ruled", "target-confirmed", "stands-alone"):
        assert g["checks"][c] == {"state": "holds", "errors": [], "warnings": [], "notes": []}, c


def test_sitting_2_is_in_the_sloppy_fixture(vols):
    """The owner's rulings of sitting 2 (fabulac-test-repos/_x0/sitting-2.md), as the converter carried them."""
    nodes = {it.id: it.data for it in vols["sloppy-xml-py.fabulac.cosm"].items.values()}
    own = [r for d in nodes.values() for r in tc.rulings(d) if r.get("allowing") == "own-types"]
    assert len(own) == 62 and all(r["made-for"] == "N:target/rust" and r["is"] == "alike" for r in own)
    assert not [r for d in nodes.values() for r in tc.rulings(d)
                if r.get("is") == "alike" and r.get("allowing") not in tc.DEFAULTS["allowances"]]
    s_i0 = {r.get("about"): r["is"] for r in tc.rulings(nodes["C:interface/x0.S-I0"]) if tc.applies(r, "N:target/rust")}
    assert s_i0 == {"the driver contract": "kept", "the program's name": "changed"}
    assert [r["is"] for r in tc.rulings(nodes["C:interface/x0.S-I2"])] == ["kept", "kept"]
    byte_steps = [r for r in tc.rulings(nodes["C:interface/x0.S-I6"]) if r["is"] == "changed"]
    assert len(byte_steps) == 4 and all(r["case"] == "P:case/x0.ruled.S-C21" and r["steps"] in ([2], [4])
                                        for r in byte_steps)


def test_cases_cover_reports_the_share_the_experiment_measured(vols):
    rep = fabula.lint(vols["vulture.fabulac.cosm"])
    cc = [p for p in rep.problems() if p.check == "cases-cover"]
    assert len(cc) == 1 and cc[0].severity == "note" and "44 of 71" in cc[0].message


def test_every_other_fabula_is_untouched():
    rep = fabula.lint(TALLY)
    assert not [p for p in rep.problems() if p.check in tc.CHECKS]
    assert rep.not_run == []
    g = tc.ready_to_keep(TALLY)
    assert not g["holds"] and g["says"].startswith("not kept for transconception")


# ---------------------------------------------------------------------------
# a small fabulac that passes every check, and each check made to fail
# ---------------------------------------------------------------------------

PROV = {"mode": "manual", "sources": ["the test"], "confidence": 1}
SOURCE_TEXT = "def greet(name):\n    return 'hello ' + name\n" + "# " + "a long comment of the source. " * 20 + "\n"


def _n(id_, type_, **kw):
    d = {"id": id_, "type": type_, "name": kw.pop("name", id_.split("/")[-1]),
         "summary": kw.pop("summary", "An item of the small program."), "stance": "observed"}
    d.update(kw)
    d["provenance"] = dict(PROV)
    return d


RUL = {"by": "R:maker/transconceiver", "on": "2026-11-18", "said": "the test's sitting"}


def mini() -> dict:
    return {
        "oes": "fabula/1", "macrocosm": M.MACROCOSM_VERSION, "flavour": "fabulac", "purpose": "transconception",
        "ruled-by": "R:maker/transconceiver", "id": "fabula/hello", "name": "hello",
        "source": {"path": "hello/", "kind": "folder", "language": "python", "files": 1, "licence": "MIT",
                   "obtained": "own"},
        "shorts": [{"path": "hello.cshort-2026-11-18-1200/", "at": "2026-11-18T12:00", "by": "a writer",
                    "mode": "model", "order": "code", "language": "python", "entailed": "apart",
                    "target": "N:target/python",
                    "evidence": {"level": 3, "steps": {"kept": 2, "agree": 2}, "against": "original",
                                 "where": {"file": "verdict.json", "digest": "0" * 64}}}],
        "nodes": [
            _n("C:file/hello-py", "file", path="hello.py", language="python", length={"lines": 3}),
            _n("R:licence/mit", "licence", identifier="MIT", lane="open"),
            _n("E:person/owner", "person"),
            _n("R:maker/transconceiver", "maker", who="E:person/owner", capacity="transconceiver",
               statements={"licence": "MIT", "lane": "open", "confidential": "none", "programs": {"go": "hello"},
                           "attribution": "the notice carried"}),
            _n("N:target/python", "target", language="python"),
            _n("N:target/go", "target", language="go"),
            _n("C:dependency/python", "dependency", package="python", scope="standard", resolved="3.13.11",
               **{"needed-for": "everything"}),
            _n("C:interface/greet", "interface", surface="command", signature="hello NAME",
               ruling=[{"is": "kept", **RUL}]),
            _n("C:behaviour/greet", "behaviour", does="Says hello to the name given.", of=["C:interface/greet"],
               ruling=[{"is": "kept", **RUL}, {"is": "free", "made-for": "N:target/go", **RUL}]),
            _n("C:reliance/text-joins", "reliance", gives="Two texts joined make one.", example="hello + ada",
               ruling=[{"is": "kept", **RUL}], **{"on": "language", "of": ["C:dependency/python"],
                                                    "used-by": ["C:behaviour/greet"],
                                                    "stated": [{"in": "python", "version": "3.13.18",
                                                                "at": "library/stdtypes.html#str",
                                                                "digest": "abcdef012345"}]}),
            _n("P:case/greet-ada", "case", of=["C:interface/greet", "C:behaviour/greet"], stands="outside",
               **{"from": "recorded"}, given={"steps": [{"arguments": ["ada"]}]},
               expect={"steps": [{"exit": 0, "output": "hello ada\n", "error-output": ""}]}),
        ],
    }


def _write(tmp_path: Path, doc: dict, *, source: str | None = SOURCE_TEXT) -> Path:
    p = tmp_path / "hello.fabulac.cosm"
    p.write_text(M.dump(json.loads(json.dumps(doc))), encoding="utf-8")      # no list or mapping held twice
    if source is not None:
        (tmp_path / "hello").mkdir(exist_ok=True)
        (tmp_path / "hello" / "hello.py").write_text(source, encoding="utf-8")
    return p


def _node(doc: dict, id_: str) -> dict:
    return next(n for n in doc["nodes"] if n["id"] == id_)


def test_the_small_fabulac_passes_every_check_and_gate_1(tmp_path):
    p = _write(tmp_path, mini())
    rep = fabula.lint(p)
    assert rep.errors == [] and rep.warnings == [], [str(x) for x in rep.problems()]
    g = tc.ready_to_keep(p)
    assert g["holds"] and g["says"] == "ready to keep"
    assert not tc.ready_to_entail(p, "go")["holds"]


def _set(path: str, value):
    def f(doc):
        node, _, fld = path.partition("#")
        tgt = doc if node == "" else _node(doc, node)
        keys = fld.split(".")
        for k in keys[:-1]:
            tgt = tgt[int(k)] if isinstance(tgt, list) else tgt[k]
        if value is _DEL:
            tgt.pop(keys[-1]) if isinstance(tgt, dict) else tgt.pop(int(keys[-1]))
        else:
            tgt[int(keys[-1]) if isinstance(tgt, list) else keys[-1]] = value
    return f


_DEL = object()


def _case_names_a_source_file(doc):
    _node(doc, "P:case/greet-ada")["given"]["steps"][0]["arguments"] = ["hello.py"]


def _carry_the_source(doc):
    _node(doc, "C:interface/greet")["summary"] = SOURCE_TEXT[50:300]
    _node(doc, "C:interface/greet")["ruling"] = [{"is": "free", **RUL}]


def _uncover(doc):
    _node(doc, "P:case/greet-ada")["of"] = ["C:interface/greet"]


FAILS = [
    ("standing", _set("R:licence/mit#lane", _DEL), "lane"),
    ("standing", _set("R:maker/transconceiver#statements.attribution", {"pending": "who?"}), "attribution"),
    ("standing", _set("R:licence/mit#lane", "closed"), "leave"),
    ("ground-given", _set("C:reliance/text-joins#example", _DEL), "example"),
    ("ground-given", _set("C:dependency/python#needed-for", ""), "needed for"),
    ("ground-cited", _set("C:reliance/text-joins#stated", _DEL), "stated"),
    ("ground-cited", _set("C:reliance/text-joins#stated.0.version", "3.12.1"), "3.13"),
    ("ground-cited", _set("C:reliance/text-joins#stated.0.digest", _DEL), "{in, version, at, digest}"),
    ("stands-alone", _set("C:interface/greet#summary", "Runs as a Python script."), "Python"),
    ("nothing-carried", _carry_the_source, "code points"),
    ("case-outside", _case_names_a_source_file, "a file of the source"),
    ("case-outside", _set("P:case/greet-ada#expect", {"steps": []}), "one per given step"),
    ("cases-cover", _uncover, "0 of 1"),
    ("ruled", _set("C:behaviour/greet#ruling", _DEL), "no ruling"),
    ("ruled", _set("C:interface/greet#ruling", {"is": "kept"}), "a list"),
    ("ruled", _set("C:behaviour/greet#ruling.1.said", _DEL), "because or said"),
    ("ruled", _set("C:interface/greet#ruling", [{"pending": "kept?", "proposed": "kept"}]), "not ruled yet"),
    ("round-trip", _set("#shorts.0.evidence.level", 1), "level 2"),
    ("round-trip", _set("#shorts", _DEL), "level 2"),
    ("target-confirmed", _set("N:target/go#verdict", "feasible"), "spike"),
    ("evidence-stated", _set("#shorts.0.evidence.where", {"file": "verdict.json"}), "digest"),
    ("evidence-stated", _set("#shorts.0.evidence.steps", {"kept": 1, "agree": 2}), "agree"),
]


@pytest.mark.parametrize("check, change, says", FAILS, ids=[f"{c}-{i}" for i, (c, _, _) in enumerate(FAILS)])
def test_each_check_fails(tmp_path, check, change, says):
    doc = mini()
    change(doc)
    rep = fabula.lint(_write(tmp_path, doc))
    found = [p for p in rep.problems() if p.check == check and p.severity in ("error", "warning")]
    assert found, [str(p) for p in rep.problems()]
    assert any(says in p.message for p in found), [p.message for p in found]
    if check in tc.READY_TO_KEEP and found[0].severity == "error":
        assert check in tc.ready_to_keep(_write(tmp_path, doc))["do-not-hold"]


def test_cases_cover_alone_is_a_warning_and_stands_alone_an_error(tmp_path):
    """The owner, checkpoint A (2026-11-18): every check of transconception is an error but cases-cover."""
    assert {c for c, s in tc.SEVERITY.items() if s != "error"} == {"cases-cover"}
    doc = mini()
    _uncover(doc)
    rep = fabula.lint(_write(tmp_path, doc))
    assert {p.check for p in rep.warnings} == {"cases-cover"} and rep.errors == []
    assert tc.ready_to_keep(_write(tmp_path, doc))["holds"]       # a warning is shown, it does not stop keeping
    _node(doc, "C:interface/greet")["summary"] = "Runs as a Python script."
    rep = fabula.lint(_write(tmp_path, doc))
    assert [p.check for p in rep.errors] == ["stands-alone"]
    assert tc.ready_to_keep(_write(tmp_path, doc))["do-not-hold"] == ["stands-alone"]


def test_target_confirmed_holds_once_weighed_and_gate_2_follows(tmp_path):
    doc = mini()
    _node(doc, "N:target/go").update({"verdict": "feasible", "spike": {"level": 2},
                                      "provides": [{"for": "C:reliance/text-joins", "by": "built-in"}]})
    p = _write(tmp_path, doc)
    assert tc.ready_to_entail(p, "go")["holds"]
    _node(doc, "N:target/go")["provides"] = []
    g = tc.ready_to_entail(_write(tmp_path, doc), "go")
    assert g["do-not-hold"] == ["target-confirmed"]
    assert "provides nothing for C:reliance/text-joins" in g["checks"]["target-confirmed"]["errors"][0]


def test_an_allowance_the_judge_does_not_know_blocks_only_gate_2(tmp_path):
    doc = mini()
    _node(doc, "C:behaviour/greet")["ruling"][1] = {"is": "alike", "allowing": "the order of keys",
                                                     "made-for": "N:target/go", **RUL}
    _node(doc, "N:target/go").update({"verdict": "feasible", "spike": {"level": 2},
                                      "provides": [{"for": "C:reliance/text-joins", "by": "built-in"}]})
    p = _write(tmp_path, doc)
    assert tc.ready_to_keep(p)["holds"]
    g = tc.ready_to_entail(p, "go")
    assert g["do-not-hold"] == ["ruled"]
    doc2 = copy.deepcopy(doc)
    _node(doc2, "C:behaviour/greet")["ruling"][1]["allowing"] = "exit-only"
    assert tc.ready_to_entail(_write(tmp_path, doc2), "go")["holds"]
    _node(doc2, "C:behaviour/greet")["ruling"][1]["allowing"] = "own-types"     # the fifth, ruled at sitting 2
    assert tc.ready_to_entail(_write(tmp_path, doc2), "go")["holds"]


def test_a_fabulac_nobody_could_rule_is_kept_unruled(tmp_path):
    doc = mini()
    doc["ruled-by"] = "none"
    doc["nodes"] = [n for n in doc["nodes"] if n["id"] != "R:maker/transconceiver"]
    for n in doc["nodes"]:
        n.pop("ruling", None)
    p = _write(tmp_path, doc)
    g = tc.ready_to_keep(p)
    assert g["kept-unruled"] and g["says"] == "kept unruled" and not g["holds"]
    assert g["checks"]["standing"]["state"] == "holds" and g["do-not-hold"] == ["ruled"]
    assert tc.ready_to_entail(p, "go")["says"].startswith("kept unruled")


def test_nothing_carried_spares_a_kept_message_and_a_case(tmp_path):
    doc = mini()
    _node(doc, "C:interface/greet")["summary"] = SOURCE_TEXT[50:300]     # ruled kept: carried exactly
    _node(doc, "P:case/greet-ada")["expect"]["steps"][0]["output"] = SOURCE_TEXT
    assert not [p for p in fabula.lint(_write(tmp_path, doc)).problems() if p.check == "nothing-carried"]
    alone = tmp_path / "alone"
    alone.mkdir()
    rep = fabula.lint(_write(alone, doc, source=None))
    assert [p for p in rep.notes if p.check == "nothing-carried" and "not measured" in p.message]


def test_evidence_stated_checks_the_verdict_file_when_at_hand(tmp_path):
    doc = mini()
    (tmp_path / "verdict.json").write_text('{"passes": true}\n', encoding="utf-8")
    rep = fabula.lint(_write(tmp_path, doc))
    assert [p for p in rep.errors if p.check == "evidence-stated" and "has digest" in p.message]
    doc["shorts"][0]["evidence"]["where"]["digest"] = hashlib.sha256(b'{"passes": true}\n').hexdigest()
    assert not _errors(fabula.lint(_write(tmp_path, doc)), "evidence-stated")


def test_ground_cited_leaves_one_place_for_the_library():
    entry = {"in": "python", "version": "3.13.18", "at": "library/x.html#y", "digest": "abc"}
    assert tc.resolve_citation(entry) == (None, "the language library is not aboard: the citation is carried, "
                                                "not resolved")

    class Lib:
        def find(self, e):
            return None
    ok, why = tc.resolve_citation(entry, Lib())
    assert ok is False and "no section" in why


def _cshort_doc(tmp_path: Path, *, csmd: str | None, requests: str | None) -> Path:
    doc = mini()
    doc["shorts"].append({"path": "hello.cshort-go/", "at": "2026-11-18T13:00", "by": "a writer", "mode": "model",
                          "order": "code", "language": "go", "entailed": "apart", "target": "N:target/go"})
    d = tmp_path / "hello.cshort-go"
    d.mkdir(exist_ok=True)
    (d / "main.go").write_text("package main\nfunc Greet(name string) string { return \"hello \" + name }\n")
    if csmd is not None:
        (d / "CSHORT.md").write_text(csmd, encoding="utf-8")
    if requests is not None:
        (d / "requests.jsonl").write_text(requests, encoding="utf-8")
    return _write(tmp_path, doc)


def test_surface_answered_and_apart_on_a_cshort_in_another_language(tmp_path):
    good = "| item | file | name |\n|---|---|---|\n| C:interface/greet | main.go | Greet |\n"
    p = _cshort_doc(tmp_path, csmd=good, requests='{"brief": "say hello to the name"}\n')
    rep = fabula.lint(p)
    assert not _errors(rep, "surface-answered") and not _errors(rep, "apart")
    p = _cshort_doc(tmp_path, csmd=good.replace("Greet |", "Hello |"),
                    requests=json.dumps({"brief": "see", "span": {"file": "hello.py", "lines": "1-2"}}) + "\n")
    rep = fabula.lint(p)
    assert any("Hello is not in main.go" in e for e in _errors(rep, "surface-answered"))
    assert any("carried a span" in e for e in _errors(rep, "apart"))
    p = _cshort_doc(tmp_path, csmd="nothing here\n", requests=json.dumps({"brief": "read hello.py"}) + "\n")
    rep = fabula.lint(p)
    assert any("maps it to no file" in e for e in _errors(rep, "surface-answered"))
    assert any("named a path of the source" in e for e in _errors(rep, "apart"))


def test_the_new_kinds_and_lists_are_read_by_the_generic_reader(tmp_path):
    doc = mini()
    _node(doc, "R:licence/mit")["lane"] = "shut"
    _node(doc, "C:reliance/text-joins")["on"] = "moon"
    _node(doc, "C:interface/greet")["ruling"] = [{"is": "maybe", **RUL}]
    _node(doc, "R:maker/transconceiver")["capacity"] = "transcoder"
    doc["purpose"] = "transcoding"
    rep = fabula.lint(_write(tmp_path, doc))
    bad = {(p.check, p.field) for p in rep.errors}
    assert {("closed-list", "lane"), ("closed-list", "on"), ("closed-list", "ruling.is"),
            ("closed-list", "capacity"), ("catalog-key", "purpose")} <= bad
    assert not [p for p in rep.problems() if p.check in tc.CHECKS]   # not purpose: transconception: none run


# ---------------------------------------------------------------------------
# the converter (tools/transconception/promote_x0.py, kept out of enough's import path)
# ---------------------------------------------------------------------------

def _promote_module():
    spec = importlib.util.spec_from_file_location("promote_x0", REPO / "tools" / "transconception" / "promote_x0.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_loading_the_converter_leaves_enoughs_dumper_as_it_was():
    """The converter quotes a string holding a YAML line break with a dumper of its own; enough's dump of the same
    string is the same before and after the converter is loaded (a recorded run's engine-call digests are dumps)."""
    data = {"oes": "fabula/1", "said": "one two"}
    before = M.dump(data)
    mod = _promote_module()
    assert M.dump(data) == before
    assert mod.dump(data) != before and '"one\\Ltwo"' in mod.dump(data)


def test_the_converter_maps_the_words_and_the_shapes():
    mod = _promote_module()
    x0 = {"oes": "fabula/1", "macrocosm": "0.5.4", "flavour": "fabulac", "purpose": "transcoding", "id": "fabula/a",
          "source": {"path": "a/", "language": "python"},
          "nodes": [
              {"id": "R:maker/transcoder", "type": "maker", "name": "the owner, as transcoder",
               "summary": "rules as transcoder", "capacity": "transcoder"},
              {"id": "C:dependency/python", "type": "dependency", "package": "python"},
              {"id": "N:target/python", "type": "target", "language": "python"},
              {"id": "C:reliance/R1", "type": "reliance", "on": "runtime", "of": ["C:behaviour/b"],
               "used-by": ["C:component/c"], "cited": "stated in full", "gives": "g",
               "ruling": {"is": "kept", "by": "R:maker/transcoder", "said": "File \"/Users/someone/x.py\""}},
          ]}
    verdict = {"steps": {"kept": 3, "agree": 3}, "against": "original", "recorded_digest": "f" * 64}
    out = mod.promote(x0, verdict, "d" * 64, "../v.json", level=3, at="2026-11-13T10:06", cshort_path="told/x/")
    assert out["purpose"] == "transconception" and out["ruled-by"] == "R:maker/transconceiver"
    assert out["source"]["obtained"] == "public" and out["macrocosm"] == M.MACROCOSM_VERSION
    nodes = {n["id"]: n for n in out["nodes"]}
    m = nodes["R:maker/transconceiver"]
    assert m["capacity"] == "transconceiver" and "transconceiver" in m["name"] + m["summary"]
    r = nodes["C:reliance/R1"]
    assert r["of"] == ["C:dependency/python"] and r["used-by"] == ["C:behaviour/b", "C:component/c"]
    assert "cited" not in r and isinstance(r["ruling"], list) and r["ruling"][0]["by"] == "R:maker/transconceiver"
    assert "/Users/" not in r["ruling"][0]["said"] and "~/x.py" in r["ruling"][0]["said"]
    sh = out["shorts"][-1]
    assert sh["target"] == "N:target/python" and sh["entailed"] == "apart" and sh["evidence"]["level"] == 3
    assert sh["evidence"]["where"] == {"file": "../v.json", "digest": "d" * 64}
