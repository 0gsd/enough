"""The fabulam's moves and its checks against the source (0.9; `enough/thym/moves/proof.py`; Thym 20.13; the design
`docs/v090-fabulam-design.md`, sections 2.B, 4.4 and 5).

By rule and with no model: `survey` of the fixture Lean file gives an outline that passes `declarations-found`,
`comments-covered`, `reach-agrees` and the volume's own checks. With recorded answers: each check of 2.B is broken
in the one way it exists to catch. The Lean is Mathlib's `Mathlib/NumberTheory/PrimesCongruentOne.lean`, shipped
whole as a fixture (`tests/fixtures/fabula/fabulam/NOTICE.md`), read as text and never built.

The recorded answers under `tests/fixtures/fabula/fabulam/recorded/` are HAND-RECORDED: a person wrote them in the
shape of a recorded candidate, and each file says so in its first line. `Recorded` answers a request from the file
of its job, as a replay answers one from a run's record. No model runs here, and nothing of Lean is run anywhere.
"""
from __future__ import annotations

import copy
import datetime as dt
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from enough import fabula as FAB
from enough import fabulam_job as J
from enough import fabulam_prompts as FP
from enough import macrocosm as mc
from enough import repo_engine as RE
from enough import thym_host as H
from enough.thym import checks as C
from enough.thym.coprocessor import RefusingCoprocessor, candidate
from enough.thym.moves import proof as P
from enough.thym.values import Value, read_value

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula" / "fabulam"
LEAN = FIX / "PrimesCongruentOne.lean"
REC = FIX / "recorded"
OWN = FIX / "own"
NOW = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.timezone.utc)
TARGET = "Nat.infinite_setOfPred_prime_modEq_one"
SPINE = "Nat.exists_prime_gt_modEq_one"
MIDDLE = "Nat.frequently_atTop_modEq_one"
DEFAULT_CHECKING = ("The file's text holds no `sorry` and declares no axiom of its own. It was read here as text. "
                    "Nothing was built or run, so whether Lean accepts it is not known here.")


def engines() -> dict:
    return {**H.engines(feed=None), **RE.engines()}


def _t(inputs: dict, name: str) -> str:
    v = (inputs or {}).get(name)
    v = v[0] if isinstance(v, tuple) else v
    return v.text() if hasattr(v, "text") else str(v or "")


def recorded(folder: Path, key: str) -> str:
    """One hand-recorded answer: the `output` of the candidate file `<key>.1.cosm`."""
    path = folder / f"{key}.1.cosm"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# HAND-RECORDED"), f"{path.name} does not say it is hand-recorded"
    data = mc.yaml_load(text)
    assert data["engine"] == "model:hand-recorded" and data["recorded"] == "by hand"
    return data["output"]


class Recorded:
    """A coprocessor that answers each request with the hand-recorded answer of its job: `<job>.<file stem>` when
    there is one for the file, else `<job>`; a pshort's is `pshort-<density>`. `answers` gives others in their
    place, by the same key: a text, or a list (one per attempt; the last is kept for later attempts)."""

    def __init__(self, folder: Path, answers: dict | None = None) -> None:
        self.folder = folder
        self.answers = {k: (list(v) if isinstance(v, list) else v) for k, v in (answers or {}).items()}
        self.sent: list[tuple[str, dict]] = []

    def complete(self, contract, inputs, *, budget):
        job = _t(inputs, "fabulam")
        if not job:                                        # the question program: nothing is proposed
            self.sent.append(("question", {}))
            return candidate("questions: []", engine="model:hand-recorded", tokens=0)
        key = f"pshort-{_t(inputs, 'density')}" if job == "pshort" else job
        stem = Path(_t(inputs, "path")).stem if _t(inputs, "path") else _t(inputs, "name").rsplit("-", 1)[-1]
        if f"{key}.{stem}" in self.answers or (self.folder / f"{key}.{stem}.1.cosm").is_file():
            key = f"{key}.{stem}"
        self.sent.append((key, {k: _t(inputs, k) for k in inputs}))
        got = self.answers.get(key)
        if isinstance(got, list):
            got = got.pop(0) if len(got) > 1 else got[0]
        out = got if got is not None else recorded(self.folder, key)
        sch = contract.get("schema") or {}
        if sch.get("format") == "yaml" and sch.get("stamp") == "engine":
            data = mc.yaml_load(out)                       # as the host's coprocessor does: the model's id stamped in
            if isinstance(data, dict):
                out = {**data, "engine": "model:hand-recorded"}
        return candidate(out, engine="model:hand-recorded", tokens=0)

    def asked(self, key: str) -> list[dict]:
        return [ins for k, ins in self.sent if k == key]


def runtime(cp=None, root: Path | None = None):
    """A program's run kwargs as the app's would give them, with the recorded answers and the host's engines."""
    def make(stage, plan, info, mode, scaffolds, program):
        return {"coprocessor": cp if (mode == "model" and cp is not None) else RefusingCoprocessor(),
                "agent_free": False, "rules": scaffolds, "preflight": None,
                "environment": {"route": "local"} if mode == "model" else {},
                "root": root or H.host_root(), "engines": engines(), "calls": None}
    return make


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copy(LEAN, proj / LEAN.name)
    return proj


def fab_path(project: Path) -> Path:
    return project / "primes-congruent-one.fabulam.cosm"


def fabulam(project: Path) -> dict:
    return mc.yaml_load(fab_path(project).read_text(encoding="utf-8"))


def build(project: Path, cp: Recorded | None = None, **kw):
    kw.setdefault("mode", "model")
    kw.setdefault("runtime", runtime(cp or Recorded(REC / "primes-congruent-one")))
    return J.run_file_build(project, project / LEAN.name, now=NOW, **kw)


def outline(project: Path) -> dict:
    out = build(project, mode="rules", why="no model")
    assert [r["stage"] for r in out["ran"]] == ["survey"], out
    return fabulam(project)


def items_of(doc: dict) -> dict[str, dict]:
    return {n["id"]: n for n in doc["nodes"]}


CTX = SimpleNamespace(engines=RE.engines(), now=NOW, coprocessor=None)


def verdict(name: str, doc: dict, *, lean: Path = LEAN, mods: dict | None = None, **inputs):
    """One named check's verdict on a fabulam given as a mapping, against the Lean file."""
    ins = {"t": read_value(lean, "text"), **inputs}
    return C.verdict(name, Value("fabula", doc), ins, {"modifiers": mods or {}}, {"name": "survey"}, CTX)


def holds(name: str, doc: dict, **kw) -> None:
    ok, why = verdict(name, doc, **kw)
    assert ok, f"{name}: {why}"


def fails(name: str, doc: dict, words: str, **kw) -> None:
    ok, why = verdict(name, doc, **kw)
    assert not ok and words in why, f"{name}: {ok}, {why}"


# ---------------------------------------------------------------------------
# By rule, with no model
# ---------------------------------------------------------------------------

def test_comments_are_blanked_by_rule_and_every_line_keeps_its_number():
    text = LEAN.read_text(encoding="utf-8")
    blank = P.blank_comments(text)
    assert len(blank.split("\n")) == len(text.split("\n"))
    assert "Copyright" not in blank and "We prove that" not in blank and "arbitrarily large" not in blank
    lines, was = blank.split("\n"), text.split("\n")
    assert lines[27] == was[27] and lines[0] == "" and lines[25] == ""        # the theorem's line; the comments' gone
    # nested comments, a string that holds two hyphens, a prime in a name, a character
    odd = "/- a /- b -/ c -/ theorem x' : \"--no\" := by -- hi\n  exact 'a' -- bye\n"
    assert P.blank_comments(odd) == "                  theorem x' : \"--no\" := by\n  exact 'a'\n"
    assert P.blank_comments is FP.blank_comments           # the prompts name the same rule


def test_ids_follow_the_slug_rule_and_names_the_stem_rule():
    assert P.lean_slug("quadratic_reciprocity'") == "quadratic_reciprocity-prime"
    assert P.lean_slug("χ₈") == "x-x3c7-x2088" and P.lean_slug("Nat.foo.") == "Nat.foo-x2e"
    assert P.respell("PrimesCongruentOne.lean") == "primes-congruent-one" and P.respell("LSeries") == "lseries"
    from enough import fabula_names as N
    for name in ("quadratic_reciprocity'", "χ₈", "_root_.x", "Nat.exists_prime_gt_modEq_one"):
        assert P.lean_slug(name) == N.declaration_slug(name)
    assert P.part_uri("fabula/lseries", "Mathlib.NumberTheory.LSeries.Nonvanishing") == \
        "oes:" + N.fabulam_part_id("lseries", "Mathlib.NumberTheory.LSeries.Nonvanishing")


def test_the_budget_is_the_designs_and_a_request_past_it_is_refused_before_it_is_sent():
    assert (P.CHUNK_LINES, P.NEIGHBOUR_CHARS, P.SUMMARY_CHARS, P.HEAD_PARTS, P.HEAD_CROSSING, P.REQUEST_CHARS,
            P.PSHORT_CHARS) == (300, 6000, 1200, 24, 40, 48000, 60000)
    assert (P.BAND_FILES, P.BAND_LINES) == (60, 12000)
    small = {"code": Value("string", "x" * 100)}
    assert P.held(small, "the reading") is small
    with pytest.raises(P.RequestTooLarge) as e:
        P.held({"code": Value("string", "x" * P.REQUEST_CHARS)}, "the reading of F.lean")
    assert e.value.check == "request" and "nothing was sent" in str(e.value)
    # a file is read in chunks cut at a declaration's first line; a longer declaration is a range of its own
    assert P.chunks_of(75, [28, 61, 68, 72]) == [{"a": 1, "b": 75, "long": False}]
    assert P.chunks_of(700, [10, 250, 400, 650]) == [{"a": 1, "b": 249, "long": False},
                                                     {"a": 250, "b": 399, "long": False},
                                                     {"a": 400, "b": 649, "long": False},
                                                     {"a": 650, "b": 700, "long": False}]
    assert P.chunks_of(900, [10, 20, 700]) == [{"a": 1, "b": 19, "long": False}, {"a": 20, "b": 699, "long": True},
                                               {"a": 700, "b": 900, "long": False}]


def test_every_system_prompt_is_under_two_thousand_characters_and_none_says_the_proof_is_checked():
    assert set(FP.SYSTEMS) == {"read", "comments", "fit", "yield", "stages", "head", "pshort-expert",
                               "pshort-student", "pshort-everyone"}
    for name, text in FP.SYSTEMS.items():
        assert len(text) < 2000, (name, len(text))
        low = text.lower()
        if name.startswith("pshort"):
            assert "never call your text one" in text and "never say the proof" in text
        else:
            assert not any(w in low for w in ("machine-checked", "verified", "certified", "proved correct")), name
    assert "comments blanked" in FP.READ_SYSTEM and "do not see Lean" in FP.STAGES_SYSTEM
    assert "do not see Lean" in FP.FIT_SYSTEM and "have not seen the Lean" in FP.PSHORT_COMMON


def test_survey_by_rule_gives_an_outline_that_passes_its_checks(project: Path):
    doc = outline(project)
    assert (doc["oes"], doc["flavour"], doc["id"], doc["name"]) == ("fabula/1", "fabulam",
                                                                    "fabula/primes-congruent-one",
                                                                    "primes-congruent-one")
    src = doc["source"]
    assert (src["path"], src["kind"], src["language"], src["lines"], src["size"]) == (
        "PrimesCongruentOne.lean", "text", "lean", 75, 3151)
    assert src["sha256"] == "5130258351145d9fef49db0c6ef1f6146fbbb3fbb59e75380c281bdc6da47678"
    assert src["imports"] == ["Mathlib.RingTheory.Polynomial.Cyclotomic.Eval"] and src["licence"] == "Apache-2.0"
    assert src["target"] == [TARGET] and src["target-by"] == "rule"
    assert src["read"] == {"by": "rules", "elaborated": "no", "comments": "blanked"}
    assert src["checking"] == {"sorry": 0, "axioms": 0, "native-decide": 0, "built-here": "no"}
    assert mc.is_pending(src["toolchain"])                  # a loose file: no lean-toolchain at or above it
    assert doc["derived"]["completeness"] == "outline" and doc["derived"]["mode"] == "rules"
    assert "teaching" not in doc and doc["atem"]["of"] == f"C:statement/{TARGET}"
    it = items_of(doc)
    # every declaration is an item, its id its kind and its full name
    assert {i for i in it if i.split("/")[0] in ("C:statement", "C:lemma", "C:definition")} == {
        f"C:statement/{TARGET}", f"C:lemma/{SPINE}", f"C:lemma/{MIDDLE}",
        "C:definition/Nat.infinite_setOf_prime_modEq_one"}
    st, spine, mid, alias = (it[f"C:statement/{TARGET}"], it[f"C:lemma/{SPINE}"], it[f"C:lemma/{MIDDLE}"],
                             it["C:definition/Nat.infinite_setOf_prime_modEq_one"])
    assert (st["lean"], st["span"], st["form"]) == (TARGET, {"file": "PrimesCongruentOne.lean", "lines": "68-70"},
                                                    "theorem")
    assert mc.is_pending(st["says"]) and mc.is_pending(st["quantifiers"])
    # the reach, by rule: reached, depth, carries; uses and used-by
    assert [(x["reached"], x.get("depth"), x.get("carries")) for x in (st, mid, spine, alias)] == [
        ("yes", 0, 2), ("yes", 1, 1), ("yes", 2, 0), ("no", None, None)]
    assert st["uses"] == [f"C:lemma/{MIDDLE}"] and mid["uses"] == [f"C:lemma/{SPINE}"]
    assert spine["used-by"] == [f"C:lemma/{MIDDLE}"] and mid["used-by"] == [f"C:statement/{TARGET}"]
    assert (spine["proof"], spine["automation"], spine["sorry"]) == ("tactic", ["simp"], 0)
    assert alias["form"] == "alias" and "says" not in alias
    # the file, what it imports from, the licence, the maker the header names, the means
    f = it["C:file/primescongruentone-lean"]
    assert (f["path"], f["language"], f["length"], f["opens"]) == ("PrimesCongruentOne.lean", "lean",
                                                                   {"lines": 75, "bytes": 3151},
                                                                   ["Filter", "Nat", "Polynomial"])
    dep = it["C:dependency/mathlib"]
    assert (dep["package"], dep["scope"]) == ("mathlib", "standard")
    assert it["R:licence/apache-2-0"]["identifier"] == "Apache-2.0" and it["R:means/lean"]["what"] == "Lean"
    maker = next(x for x in doc["nodes"] if x["type"] == "maker")
    assert maker["stance"] == "hearsay" and maker["provenance"]["sources"] == ["PrimesCongruentOne.lean#L1-L5"]
    # one audit row per comment, with no verdict yet
    assert doc["audit"] == [{"lines": "1-5", "kind": "header", "on": ""},
                            {"lines": "10-15", "kind": "module-note", "on": ""},
                            {"lines": "26-27", "kind": "note", "on": f"C:lemma/{SPINE}"},
                            {"lines": "67", "kind": "note", "on": f"C:statement/{TARGET}"}]
    # the two fixed items
    chk = it["P:claim/checking"]
    assert chk["says"] == DEFAULT_CHECKING and chk["stance"] == "observed"
    txt = it["P:assumption/read-as-text"]
    assert txt["says"] == "The file was read as text. Names were matched by spelling. Lean was not run."
    assert (txt["checked"], txt["carries"]) == ("no", "must")
    # the checks against the source, and the volume's own
    for name in ("declarations-found", "comments-covered", "reach-agrees", "code-span", "licence-recorded",
                 "lines-resolve", "nothing-invented", "nothing-carried"):
        holds(name, doc)
    rep = FAB.lint(fab_path(project))
    assert rep.errors == [], [str(e) for e in rep.errors]
    assert P.its_own_file(doc["nodes"], "PrimesCongruentOne.lean") is None


def test_what_is_said_about_checking_is_built_by_rule_from_the_counts_and_the_persons_entry():
    assert P.checking_says({"sorry": 0, "axioms": 0, "native-decide": 0}) == DEFAULT_CHECKING
    said = P.checking_says({"sorry": 2, "axioms": 1, "native-decide": 3})
    assert said.startswith("The file's text holds `sorry` 2 times and declares 1 axiom of its own.")
    assert said.endswith("It uses `native_decide` 3 times, which trusts the compiler.")
    with_entry = P.checking_says({"sorry": 0, "axioms": 0, "native-decide": 0, "said": "It builds at this commit.",
                                  "said-by": "The library's maintainers", "said-at": "2026-11-01"})
    assert with_entry == DEFAULT_CHECKING + " The library's maintainers says: It builds at this commit. (2026-11-01)."
    # said with nobody saying it is not written: the sentence is the default
    assert P.checking_says({"sorry": 0, "axioms": 0, "native-decide": 0, "said": "It builds."}) == DEFAULT_CHECKING
    for text in (DEFAULT_CHECKING, said):
        assert not any(w in text.lower() for w in P.CHECK_WORDS)


def test_the_persons_entry_on_checking_reaches_the_fixed_item_as_hearsay(project: Path):
    out = build(project, mode="rules", why="no model", said="The file builds at the commit it was taken from.",
                said_by="A maintainer of the library", said_at="2026-11-20")
    assert out["state"]["said_by"] == "A maintainer of the library"
    doc = fabulam(project)
    chk = items_of(doc)["P:claim/checking"]
    assert chk["stance"] == "hearsay" and chk["says"].endswith(
        "A maintainer of the library says: The file builds at the commit it was taken from. (2026-11-20).")
    assert doc["source"]["checking"]["said-by"] == "A maintainer of the library"
    assert FAB.lint(fab_path(project)).errors == []
    # the entry is kept by a later build that leaves it out
    again = build(project, mode="rules", why="no model", restart=True)
    assert again["state"]["said"] == "The file builds at the commit it was taken from."


def test_a_target_the_person_gives_is_held_to_the_files_theorems(project: Path):
    with pytest.raises(RuntimeError) as e:
        build(project, mode="rules", why="no model", target=["Nat.no_such_theorem"])
    assert "Nat.no_such_theorem is no theorem of PrimesCongruentOne.lean" in str(e.value)
    out = build(project, mode="rules", why="no model", target=[SPINE])
    doc = fabulam(project)
    assert doc["source"]["target"] == [SPINE] and doc["source"]["target-by"] == "given"
    it = items_of(doc)
    assert it[f"C:statement/{SPINE}"]["depth"] == 0 and it[f"C:lemma/{TARGET}"]["reached"] == "no"
    assert out["state"]["targets"] == [SPINE]


# ---------------------------------------------------------------------------
# With the recorded answers: the reading, and what each job is shown
# ---------------------------------------------------------------------------

@pytest.fixture
def whole(project: Path):
    cp = Recorded(REC / "primes-congruent-one")
    out = build(project, cp)
    assert out["complete"], out
    return SimpleNamespace(project=project, cp=cp, out=out, doc=fabulam(project), path=fab_path(project))


def test_the_reader_of_the_proof_sees_no_comment_and_only_the_audit_does(whole):
    read = whole.cp.asked("read")
    assert len(read) == 1
    assert "Copyright" not in read[0]["code"] and "We prove that" not in read[0]["code"]
    assert "theorem exists_prime_gt_modEq_one" in read[0]["code"] and "28| " in read[0]["code"]
    audit = whole.cp.asked("comments")[0]
    assert "Copyright (c) 2020" in audit["code"] and "lines: 10-15" in audit["comments"].replace("'", "")
    y = whole.cp.asked("yield")[0]
    assert "arbitrarily large prime" not in y["code"] and "minFac" in y["code"]
    # the stages are folded from the items alone: no Lean at all
    st = whole.cp.asked("stages")[0]
    assert "code" not in st and "minFac" not in st["items"] and ":= by" not in st["items"]
    for key, ins in whole.cp.sent:
        if ins:
            assert FP.user_chars({k: Value("string", v) for k, v in ins.items()}) <= P.request_chars(
                {k: Value("string", v) for k, v in ins.items()}), key


def test_every_check_against_the_source_holds_of_the_whole_fabulam(whole):
    for name in ("declarations-found", "comments-covered", "reach-agrees", "lines-resolve", "nothing-invented",
                 "nothing-carried", "code-span", "licence-recorded"):
        holds(name, whole.doc)
    assert P.its_own_file(whole.doc["nodes"], "PrimesCongruentOne.lean") is None


def _broken(doc: dict, change) -> dict:
    d = copy.deepcopy(doc)
    change(d, items_of(d))
    return d


def test_declarations_found_catches_a_declaration_with_no_item_and_an_item_with_no_declaration(whole):
    def drop(d, it):
        d["nodes"] = [n for n in d["nodes"] if n["id"] != f"C:lemma/{MIDDLE}"]
    fails("declarations-found", _broken(whole.doc, drop), f"{MIDDLE} is the lean of no item")

    def invent(d, it):
        d["nodes"].append({**it[f"C:lemma/{MIDDLE}"], "id": "C:lemma/Nat.made_up", "lean": "Nat.made_up"})
    fails("declarations-found", _broken(whole.doc, invent), "names a declaration the file lacks")

    def move(d, it):
        it[f"C:lemma/{SPINE}"]["span"]["lines"] = "28-58"
    fails("declarations-found", _broken(whole.doc, move), "its span says otherwise")


def test_lines_resolve_catches_lines_outside_the_item_they_name(whole):
    def step_out(d, it):
        it["C:step/p-exceeds-n"]["span"]["lines"] = "60-62"
    fails("lines-resolve", _broken(whole.doc, step_out), "do not lie inside")

    def ground_out(d, it):
        it["P:yield/what-the-proof-delivers"]["grounds"][0]["lines"] = "33-64"
    fails("lines-resolve", _broken(whole.doc, ground_out), "do not lie inside")

    def past_the_file(d, it):
        it[f"C:statement/{TARGET}"]["span"]["lines"] = "68-99"
    fails("lines-resolve", _broken(whole.doc, past_the_file), "lie outside PrimesCongruentOne.lean")

    def reaches_nothing(d, it):
        it["C:part/from-one-to-many"]["steps"] = []
    fails("lines-resolve", _broken(whole.doc, reaches_nothing), "reaches no declaration with lines")


def test_nothing_invented_catches_a_reliance_the_file_does_not_write_and_a_link_the_reader_did_not_find(whole):
    def invent(d, it):
        d["nodes"].insert(0, {**it["C:reliance/infinitely-many-primes"], "id": "C:reliance/a-theorem-it-remembers",
                              "lean": ["Nat.a_theorem_the_file_never_writes"], "used-by": []})
    fails("nothing-invented", _broken(whole.doc, invent), "which the file does not write")

    def link(d, it):
        it[f"C:lemma/{SPINE}"]["uses"] = [f"C:lemma/{MIDDLE}"]
    fails("nothing-invented", _broken(whole.doc, link), "a link the reader did not find")

    def known(d, it):
        it["C:step/p-exceeds-n"]["known-as"] = "Euclid's theorem"
    fails("nothing-invented", _broken(whole.doc, known), "named only through a reliance")


def test_reach_agrees_catches_a_depth_the_rule_does_not_give(whole):
    def deeper(d, it):
        it[f"C:lemma/{SPINE}"]["depth"] = 1
    fails("reach-agrees", _broken(whole.doc, deeper), "the rule gives 2")

    def unreached(d, it):
        it[f"C:lemma/{MIDDLE}"]["reached"] = "no"
    fails("reach-agrees", _broken(whole.doc, unreached), "the rule gives 'yes'")


def test_comments_covered_catches_a_comment_with_no_row_and_a_row_with_no_comment(whole):
    def drop(d, it):
        d["audit"] = d["audit"][1:]
    fails("comments-covered", _broken(whole.doc, drop), "the comment at lines 1-5 has 0 audit rows")

    def extra(d, it):
        d["audit"].append({"lines": "40-41", "kind": "inline", "on": "", "verdict": "nothing"})
    fails("comments-covered", _broken(whole.doc, extra), "which hold no comment")


def test_nothing_carried_catches_a_run_of_the_files_own_text(whole):
    text = LEAN.read_text(encoding="utf-8").split("\n")
    carried = " ".join(text[42:45])                       # three lines of the proof, as written
    assert len(carried) > 80

    def carry(d, it):
        it["C:step/b-is-a-root-modulo-p"]["says"] = carried
    fails("nothing-carried", _broken(whole.doc, carry), "carries the file's own text")
    # the lean field alone may hold the file's own names
    assert P.carried_run("a prime p with n < p", "\n".join(text)) is None


def test_its_own_file_catches_an_item_that_points_into_another_file(whole):
    def stray(d, it):
        it["C:step/p-exceeds-n"]["span"]["file"] = "Other.lean"
    bad = _broken(whole.doc, stray)
    assert P.its_own_file(bad["nodes"], "PrimesCongruentOne.lean") == "C:step/p-exceeds-n points into another file"
    assert P.its_own_file([], "PrimesCongruentOne.lean") == "the reading found nothing in the file"


def test_an_answer_that_names_a_spine_lemma_without_a_why_is_asked_again(project: Path):
    good = recorded(REC / "primes-congruent-one", "read")
    bad = "\n".join(ln for ln in good.split("\n") if not ln.strip().startswith("why:"))
    assert bad != good
    cp = Recorded(REC / "primes-congruent-one", {"read": [bad, good]})
    out = build(project, cp)
    assert out["complete"] and len(cp.asked("read")) == 2


def test_a_request_past_the_budget_is_refused_and_nothing_is_sent(project: Path, monkeypatch):
    build(project, mode="rules", why="no model")
    monkeypatch.setattr(P, "REQUEST_CHARS", 3000)
    cp = Recorded(REC / "primes-congruent-one")
    with pytest.raises(RuntimeError) as e:
        build(project, cp)
    assert "read was refused (request" in str(e.value) and "past the 3000 this build sends" in str(e.value)
    assert cp.sent == []
