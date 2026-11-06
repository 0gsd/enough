"""Ascribe's module (enough/ascribe.py, enough/thym/moves/ascribe.py; Ascribe, edition 0.6.0): what the text says an
implementation does with a holograph after it is written.

The reader's one report (section 10, `release-shape`, `form-anchored` never on D); the dialectic applied, row by row of
section 8 (an answer in each container and in F, form discovery and FEED grounding, the four follow-ups, "I don't
know", a refusal, a skip, an answer with a name refused); the private filter (section 11: each thing it withholds,
each thing it never drops, a pure function); releases and `release-shape` (section 13); `propose` with a scripted
coprocessor (section 9); the isograph, match tokens, the cryptograph and the isomorph (section 14); the manifest; the
specification's own `cosm`, `json` and `yaml` blocks (skipped, with the reason, when the cosmoes-site checkout is
absent).

Every holograph is the invented sample (tests/fixtures/ascribe/sample-self) copied under tmp_path; nothing reads or
writes ~/enough (the conftest's seams).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import shutil
from pathlib import Path

import pytest

from enough import ascribe as A
from enough import macrocosm as mc

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "ascribe"
SAMPLE = FIX / "sample-self"
JOURNAL = FIX / "journal"
SPEC = Path("/Users/m3u/METMcloud/cosmoes-site/specs/ascribe.md")
NOW = "2026-11-05T19:30:00Z"
PROG = {"name": "open-self", "sha256": "2" * 64}
TRACE = {"run": "2026-11-05-1415-ab12", "sha256": "3" * 64}
# The text's example (ASCRIBE 14.1) as the ruling of 2026-11-06 has it: the isograph names its run by id, where the
# text's example still carries `"trace":{"sha256":…}` (for the second errata pass).
SPEC_ISOGRAPH = ('{"epoch":"2026-Q4","handle":"salt-and-crumb","hid":"aej6l5qrka6c6btarfiy2f7vnj",'
                 '"isograph":"ascribe-isograph/0","program":{"name":"open-self","sha256":"' + "2" * 64 + '"},'
                 '"run":"2026-11-05-1415-ab12","sample":true,"self":[{"form":"sourdough","kind":"affinity",'
                 '"marking":"stated","strength":"moderate","valence":"against"}]}')


def ruled(text_json: str) -> str:
    """The text's isograph with the ruling applied: `trace` out, `run` (TRACE's run id) in, canonical again."""
    doc = json.loads(text_json)
    doc.pop("trace", None)
    doc["run"] = TRACE["run"]
    return A.canonical_json(doc).decode("utf-8")
LETTERS = list("ABCEIOQSUY")


def feed(words):
    """A scripted FEED lookup: knots, tides and rye are FEED words; nothing else is."""
    known = {"knots": "Ties made in rope or cord.", "tides": "The rise and fall of the sea.", "rye": "A cereal grass."}
    return {w: ({"word": w, "pos_primary": "noun", "origin": "feed", "definition": known[w]} if w in known else None)
            for w in words}


@pytest.fixture
def holo(tmp_path: Path) -> Path:
    root = tmp_path / "self"
    shutil.copytree(SAMPLE, root)
    return root


def items(root: Path) -> dict:
    return {k: it.data for k, it in mc.load_volume(root).items.items()}


def clean(root: Path) -> tuple[list, list]:
    rep = A.lint_holograph(root)
    return [str(p) for p in rep.errors], [str(p) for p in rep.warnings]


def tree_bytes(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def write_nodes(root: Path, rel: str, *nodes: dict, head: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(head + mc.dump({"nodes": [dict(n) for n in nodes]}), encoding="utf-8")


def node(nid: str, **fields) -> dict:
    kind = nid.split(":", 1)[1].split("/", 1)[0]
    d = {"id": nid, "type": kind, "name": "a test node", "summary": "Made for a test.", "form": "F:form/sourdough",
         "provenance": {"mode": "manual", "sources": ["self"], "confidence": 1}}
    d.update(fields)
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# A. The holograph in the reader: one report, Ascribe's own checks, the advice line
# ---------------------------------------------------------------------------

def test_the_one_report_carries_ascribes_checks_and_release_shape():
    rep = A.lint_holograph(SAMPLE)
    assert rep.problems() == [] and "release-shape" in rep.checks
    assert rep.checks[-len(A.ASCRIBE_CHECKS):] == list(A.ASCRIBE_CHECKS)


def test_no_pii_findings_carry_their_advice_line():
    rep = A.lint_holograph(FIX / "bad" / "pii")
    d = A.report_dict(rep)
    assert len(d["warnings"]) == 7 and all(w["advice"] == A.ADVICE for w in d["warnings"])
    assert all(w["message"].endswith(A.ADVICE) for w in d["warnings"])
    assert A.report_dict(A.lint_holograph(FIX / "bad" / "unanchored"))["errors"][0]["advice"] is None


def test_form_anchored_never_holds_an_item_of_d_and_the_dialectics_checks_run(holo):
    A.raise_bank(holo, at=NOW)
    rep = A.lint_holograph(holo)
    assert rep.errors == [] and rep.warnings == []
    assert {"question-about", "question-shape", "session-declared"} <= set(rep.checks)
    assert not any(p.check == "form-anchored" for p in rep.problems())


# ---------------------------------------------------------------------------
# B. The dialectic, applied (section 8)
# ---------------------------------------------------------------------------

def test_the_bank_raises_forty_four_questions_to_the_holder_once(holo):
    qs = A.raise_bank(holo, at=NOW, run="2026-11-05-1930-7e1a")
    bank = [q for q in qs if q["raised"]["by"] == "bank"]
    assert len(bank) == 44 and {q["to"] for q in qs} == {"holder"}
    assert bank[0]["id"] == "D:question/ascribe-a1" and bank[0]["about"] == "A"
    assert bank[0]["raised"]["from"] == "ascribe/A1" and bank[0]["why"] == "missing" and bank[0]["kind"] == "text"
    assert bank[0]["asks"] == "What do you go back to, again and again?"
    rule = [q for q in qs if q["raised"]["by"] == "move"]
    assert [q["about"] for q in rule] == ["F:form/sea-glass#feed"]             # the one open question, by rule
    assert (holo / "D" / "questions.cosm").is_file()
    assert A.raise_bank(holo, at=NOW) == []                                    # asked once of the holograph


def test_the_queue_offers_the_thinnest_container_first(holo):
    A.raise_bank(holo, at=NOW)
    vol = mc.load_volume(holo)
    counts = {L: sum(1 for it in vol.items.values() if it.module == L) for L in LETTERS}
    counts["F"] = sum(1 for it in vol.items.values() if it.module == "F" and it.kind == "form")
    q = A.queue(holo)
    first = q[0]["about"] if q[0]["about"] in counts else q[0]["about"].split(":")[0]
    assert counts[first] == min(counts.values())
    seen = [x["about"] for x in q if x["about"] in counts]
    assert [counts[a] for a in seen] == sorted(counts[a] for a in seen)


@pytest.mark.parametrize("letter", LETTERS)
def test_an_answer_in_each_container_writes_a_node_there(holo, letter):
    A.raise_bank(holo, at=NOW)
    qid = f"D:question/ascribe-{letter.lower()}1"
    got = A.answer(holo, qid, "Knots that hold and come undone again when asked.", about="knots", feed=feed, at=NOW)
    assert got.refused is None
    (q, wrote), = got.settled.settled
    assert q == qid and wrote[1] == "F:form/knots"
    data = items(holo)
    n = data[wrote[0]]
    assert wrote[0].startswith(f"{letter}:{A.KINDS[letter]}/") and n["type"] == A.KINDS[letter]
    assert n["form"] == "F:form/knots" and n["summary"] == "Knots that hold and come undone again when asked."
    assert n["name"] == "Knots that hold and come undone"
    assert n["provenance"] == {"mode": "dialectic", "sources": ["D:session/session-3"], "confidence": 1}
    assert "stance" not in n
    assert mc.load_volume(holo).items[wrote[0]].file.split("/")[0] == letter
    assert data["F:form/knots"]["feed"] == {"word": "knots", "pos": "noun", "origin": "feed"}
    assert data[qid]["state"] == "answered" and data[qid]["settled"]["wrote"] == wrote
    assert data[qid]["answers"][0]["says"] == "Knots that hold and come undone again when asked."
    assert clean(holo) == ([], [])


def test_an_answer_in_f_writes_a_form_for_each_thing_it_lists(holo):
    A.raise_bank(holo, at=NOW)
    got = A.answer(holo, "D:question/ascribe-f1", "Tides; rye, and harbour lights", feed=feed, at=NOW)
    (_q, wrote), = got.settled.settled
    assert wrote == ["F:form/tides", "F:form/rye", "F:form/harbour-lights"]
    data = items(holo)
    assert data["F:form/tides"]["feed"]["origin"] == "feed" and data["F:form/tides"]["summary"].startswith("The rise")
    assert data["F:form/harbour-lights"]["feed"] == {"pending": "not in FEED"}             # never an invented form
    assert data["F:form/harbour-lights"]["summary"] == {"pending": "What is harbour lights, in one line?"}
    assert clean(holo) == ([], [])


def test_an_answer_names_a_form_the_holograph_has_and_is_anchored_to_it(holo):
    A.raise_bank(holo, at=NOW)
    got = A.answer(holo, "D:question/ascribe-i1", "Anything about sourdough and its starters.", at=NOW)
    (_q, wrote), = got.settled.settled
    assert len(wrote) == 1 and items(holo)[wrote[0]]["form"] == "F:form/sourdough"


def test_a_word_not_in_feed_is_an_open_question_and_no_lookup_says_so(holo):
    A.raise_bank(holo, at=NOW)
    A.answer(holo, "D:question/ascribe-q1", "The smell of tar on a warm rope.", about="tar", feed=feed, at=NOW)
    A.answer(holo, "D:question/ascribe-q2", "Drizzle on the harbour wall.", about="drizzle", at=NOW)
    data = items(holo)
    assert data["F:form/tar"]["feed"] == {"pending": "not in FEED"}
    assert data["F:form/drizzle"]["feed"] == {"pending": "not looked up in FEED"}
    assert clean(holo)[0] == []


def test_an_answer_that_names_no_thing_writes_no_node_and_asks_what_it_is_about(holo):
    A.raise_bank(holo, at=NOW)
    before = len(items(holo))
    got = A.answer(holo, "D:question/ascribe-o1", "That being busy is the same as being good.", at=NOW)
    assert got.settled.settled == [] and got.settled.follow_ups == [("D:question/ascribe-o1",
                                                                     "D:question/ascribe-o1-about")]
    data = items(holo)
    fu = data["D:question/ascribe-o1-about"]
    assert fu["about"] == "D:question/ascribe-o1" and fu["asks"] == "What is this about, in a word or two?"
    assert fu["to"] == "holder" and fu["why"] == "missing" and len(data) == before + 2       # the follow-up, a session
    assert data["D:question/ascribe-o1"]["state"] == "answered" and "settled" not in data["D:question/ascribe-o1"]
    assert clean(holo)[0] == []
    got = A.answer(holo, "D:question/ascribe-o1-about", "rye", feed=feed, at="2026-11-05T19:40:00Z")
    settled = dict(got.settled.settled)
    node = settled["D:question/ascribe-o1"][0]
    assert settled["D:question/ascribe-o1-about"] == settled["D:question/ascribe-o1"]
    d = items(holo)[node]
    assert node.startswith("O:opinion/") and d["form"] == "F:form/rye"
    assert d["summary"] == "That being busy is the same as being good."
    assert clean(holo) == ([], [])


def test_the_holders_confidence_is_kept_and_one_when_none_is_given(holo):
    A.raise_bank(holo, at=NOW)
    got = A.answer(holo, "D:question/ascribe-s1", "Tying knots in the dark.", about="knots", confidence=0.7,
                   feed=feed, at=NOW)
    assert items(holo)[got.settled.settled[0][1][0]]["provenance"]["confidence"] == 0.7


def test_i_dont_know_on_a_bank_question_writes_nothing(holo):
    A.raise_bank(holo, at=NOW)
    before = {k: v for k, v in tree_bytes(holo).items() if not k.startswith("D/")}
    got = A.answer(holo, "D:question/ascribe-b1", "I don't know", at=NOW)
    assert got.settled.settled == [("D:question/ascribe-b1", [])]
    q = items(holo)["D:question/ascribe-b1"]
    assert q["state"] == "unknown" and q["answers"][0]["value"] is None and q["answers"][0]["says"] == "I don't know"
    assert {k: v for k, v in tree_bytes(holo).items() if not k.startswith("D/")} == before


def test_a_refusal_writes_nothing_and_the_bank_never_puts_it_again_unless_asked(holo):
    A.raise_bank(holo, at=NOW)
    before = {k: v for k, v in tree_bytes(holo).items() if not k.startswith("D/")}
    A.answer(holo, "D:question/ascribe-c1", "I'd rather not say", at=NOW)
    q = items(holo)["D:question/ascribe-c1"]
    assert q["state"] == "declined" and q["answers"][0]["declined"] is True
    assert {k: v for k, v in tree_bytes(holo).items() if not k.startswith("D/")} == before
    assert A.raise_bank(holo, at=NOW) == []
    assert "D:question/ascribe-c1" not in [x["id"] for x in A.queue(holo)]
    A.ask_again(holo, "D:question/ascribe-c1")                                  # the holder asks for it
    assert items(holo)["D:question/ascribe-c1"]["state"] == "open"


def test_a_skip_leaves_the_question_open_and_the_session_lists_it(holo):
    A.raise_bank(holo, at=NOW)
    got = A.answer(holo, "D:question/ascribe-e1", skip=True, at=NOW)
    data = items(holo)
    assert data["D:question/ascribe-e1"]["state"] == "open"
    assert data[got.recorded.session]["skipped"] == ["D:question/ascribe-e1"]


@pytest.mark.parametrize("says, what", [
    ("Writing letters to Margaret Hollis every week.", "a personal name"),
    ("Mail from bakers@example.net, mostly.", "an email address"),
    ("Ringing 020 7946 0958 on a Sunday.", "a phone number"),
    ("The bakery at 17 Quillfeather Lane.", "a street address"),
    ("My passport 12345678 sits in a drawer.", "an id-like run of digits"),
])
def test_an_answer_with_personal_data_is_refused_and_the_question_stays_open(holo, says, what):
    A.raise_bank(holo, at=NOW)
    before = tree_bytes(holo)
    got = A.answer(holo, "D:question/ascribe-a1", says, at=NOW)
    assert got.refused and what in got.refused and "nothing was written" in got.refused
    assert got.settled is None and tree_bytes(holo) == before
    assert items(holo)["D:question/ascribe-a1"]["state"] == "open"


def test_a_declared_pseudonym_is_not_a_name(holo):
    A.raise_bank(holo, at=NOW)
    got = A.answer(holo, "D:question/ascribe-e2", "Sailing with Wren past the knots of buoys.", about="knots",
                   feed=feed, at=NOW)
    assert got.refused is None and got.settled.settled


def test_a_write_that_would_add_a_no_pii_finding_is_refused_and_a_counter_raised(holo):
    A.raise_bank(holo, at=NOW)
    A.record_answers(holo, [{"question": "D:question/ascribe-y1", "says": "Somewhere quiet by the sea."}], at=NOW)
    st = A.settle_holograph(holo, forms={"D:question/ascribe-y1": "someone@example.net"}, at=NOW)
    assert st.settled == [] and st.counters and st.counters[0][1] == "D:question/ascribe-y1-counter"
    assert st.counters[0][2][0][0] == "no-pii"
    data = items(holo)
    assert not any(k.startswith("Y:") and "quiet" in k for k in data) and "F:form/someone-example-net" not in data


def test_the_session_names_the_holder_by_role_and_takes_a_number_no_source_cites(holo):
    A.raise_bank(holo, at=NOW)
    rec = A.record_answers(holo, [{"question": "D:question/ascribe-u1", "says": "That tides keep their own time."}],
                           session={"through": "agent", "model": "g40-04", "with": {"to": "author", "who": "Ann"}},
                           at=NOW)
    s = items(holo)[rec.session]
    assert rec.session == "D:session/session-3"           # the sample's nodes cite session-1 and session-2 already
    assert s["with"] == {"to": "holder", "who": "the holder"} and s["through"] == "agent" and s["model"] == "g40-04"
    assert (holo / "D" / "session-3.cosm").is_file()


def test_the_follow_ups_ask_about_the_optional_fields_once_each(holo):
    A.raise_bank(holo, at=NOW)
    nid = A.answer(holo, "D:question/ascribe-a3", "The bakehouse at dawn, kneading.", about="sourdough",
                   at=NOW).settled.settled[0][1][0]
    fus = A.follow_ups(holo, nid, at=NOW)
    assert [q["about"].split("#")[1] for q in fus] == ["when", "valence", "strength"]   # form it has
    by = {q["about"].split("#")[1]: q for q in fus}
    assert by["when"]["kind"] == "date" and by["valence"]["options"] == ["for", "against", "mixed"]
    assert by["strength"]["kind"] == "number" and by["strength"]["range"] == [1, 5]
    assert all(q["to"] == "holder" and q["why"] == "missing" for q in fus)
    assert A.follow_ups(holo, nid, at=NOW) == []                                         # never put twice
    A.answer(holo, by["when"]["id"], "2019", at=NOW)
    A.answer(holo, by["valence"]["id"], "for", at=NOW)
    rec = A.record_answers(holo, [{"question": by["strength"]["id"], "says": "6"}], at=NOW)
    assert rec.refused and "from 1 to 5" in rec.refused[0][1]
    d = items(holo)[nid]
    assert d["when"] == "2019" and d["valence"] == "for" and "strength" not in d
    assert set(d["provenance"]["answered"]) == {"when", "valence"}
    assert d["provenance"]["mode"] == "dialectic"
    assert clean(holo) == ([], [])


def test_i_dont_know_and_a_refusal_on_a_field(holo):
    A.raise_bank(holo, at=NOW)
    nid = A.answer(holo, "D:question/ascribe-a4", "Bread from the old oven, as a child.", about="sourdough",
                   at=NOW).settled.settled[0][1][0]
    fus = {q["about"].split("#")[1]: q for q in A.follow_ups(holo, nid, at=NOW)}
    A.answer(holo, fus["when"]["id"], "I don't know, years ago", at=NOW)
    A.answer(holo, fus["strength"]["id"], "", declined=True, at=NOW)
    d = items(holo)[nid]
    assert d["when"] == {"pending": "I don't know, years ago"}
    assert d["withheld"] == ["strength"] and d["provenance"]["state"] == "not-disclosed"
    assert clean(holo)[0] == []


# ---------------------------------------------------------------------------
# C. The private filter (section 11)
# ---------------------------------------------------------------------------

def test_the_filter_keeps_everything_byte_for_byte_when_nothing_is_withheld(holo):
    f = A.private_filter(holo, use="projection")
    assert not f.whole and f.rewritten == [] and f.files == tree_bytes(holo)
    assert A.private_filter(holo, use="projection").files == f.files                  # a pure function


def test_a_marker_withholds_its_folder_and_everything_below_it(holo):
    write_nodes(holo, "A/drafts/old.cosm", node("A:affinity/old-draft"))
    write_nodes(holo, "A/drafts/deeper/older.cosm", node("A:affinity/older-draft"))
    (holo / "A" / "drafts" / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    files = A.private_filter(holo).files
    assert not any(k.startswith("A/drafts/") for k in files) and "A/affinities.cosm" in files


def test_a_marker_beside_the_catalog_withholds_the_whole_holograph(holo):
    (holo / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    f = A.private_filter(holo, use="transfer", own_keeping=True)
    assert f.whole and f.files == {}
    with pytest.raises(A.AscribeError, match="nothing leaves"):
        A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE)


def test_restricted_items_are_withheld_wherever_written_and_their_files_written_without_them(holo):
    restricted = node("A:affinity/secret", visibility="restricted")
    kept = node("A:affinity/kept", links=[{"rel": "like", "to": "A:affinity/secret"}])
    write_nodes(holo, "A/more.cosm", restricted, kept, head="# a comment the rewrite leaves behind\n")
    cat = mc.yaml_load((holo / "holograph.cosm").read_text(encoding="utf-8"))
    cat["nodes"] = [node("Y:yearning/hidden", visibility="restricted"), node("Y:yearning/open-one")]
    (holo / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    form = {"id": "F:form/private-thing", "type": "form", "name": "private thing", "summary": "Kept to myself.",
            "visibility": "restricted", "provenance": {"mode": "manual", "sources": ["self"], "confidence": 1}}
    write_nodes(holo, "F/more.cosm", form)
    f = A.private_filter(holo)
    assert sorted(f.rewritten) == ["A/more.cosm", "F/more.cosm", "holograph.cosm"]
    more = mc.yaml_load(f.files["A/more.cosm"].decode())
    assert [n["id"] for n in more["nodes"]] == ["A:affinity/kept"]
    assert more["nodes"][0]["links"] == [{"rel": "like", "to": "A:affinity/secret"}]      # the id kept, no name
    assert "#" not in f.files["A/more.cosm"].decode() and set(more) == {"nodes"}
    newcat = mc.yaml_load(f.files["holograph.cosm"].decode())
    assert [n["id"] for n in newcat["nodes"]] == ["Y:yearning/open-one"] and newcat["handle"] == "salt-and-crumb"
    assert mc.yaml_load(f.files["F/more.cosm"].decode()) == {"nodes": []}
    for rel, raw in tree_bytes(holo).items():
        if rel not in f.rewritten:
            assert f.files[rel] == raw                                        # never rewrites a kept file
    assert "withheld" not in json.dumps(mc.jsonable({k: v.decode() for k, v in f.files.items()})).lower()


@pytest.mark.parametrize("use, own, keeps_d", [("projection", False, False), ("ingest", False, False),
                                               ("package", False, False), ("transfer", False, False),
                                               ("transfer", True, True), ("projection", True, False)])
def test_module_d_is_withheld_in_every_use_but_a_transfer_into_the_holders_keeping(holo, use, own, keeps_d):
    A.raise_bank(holo, at=NOW)
    cat = mc.yaml_load((holo / "holograph.cosm").read_text(encoding="utf-8"))
    q = items(holo)["D:question/ascribe-a1"]
    cat["nodes"] = [dict(q, id="D:question/in-the-catalog")]
    (holo / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    f = A.private_filter(holo, use=use, own_keeping=own)
    has_d = any(k.startswith("D/") for k in f.files)
    in_cat = "D:question/in-the-catalog" in f.files["holograph.cosm"].decode()
    assert has_d is keeps_d and in_cat is keeps_d


def test_what_the_filter_leaves_behind_because_it_cannot_tell(holo, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("kept elsewhere", encoding="utf-8")
    (holo / "notes-link.md").symlink_to(outside)
    (holo / "I" / "broken.cosm").write_text("nodes: [\n", encoding="utf-8")
    (holo / "readme.txt").write_text("a plain file", encoding="utf-8")
    files = A.private_filter(holo).files
    assert "notes-link.md" not in files and "I/broken.cosm" not in files and files["readme.txt"] == b"a plain file"
    with pytest.raises(ValueError):
        A.private_filter(holo, use="lens")


def test_the_marker_check_says_what_everything_that_leaves_would_leave_out(holo):
    write_nodes(holo, "A/drafts/old.cosm", node("A:affinity/old-draft"))
    (holo / "A" / "drafts" / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    note, = A.lint_holograph(holo).notes
    assert note.message == "everything that leaves would leave out A/drafts/old.cosm (1 node)"


# ---------------------------------------------------------------------------
# D. Releases (section 13)
# ---------------------------------------------------------------------------

GOOD = {"epoch": "2026-Q4", "as": "isograph", "program": dict(PROG), "trace": dict(TRACE),
        "at": dt.datetime(2026, 11, 5, 14, 15, tzinfo=dt.timezone.utc), "sha256": "4" * 64,
        "items": ["A:affinity/fast-bread", "F:form/sourdough"]}


@pytest.mark.parametrize("change, field", [
    ({"epoch": None}, "epoch"), ({"as": None}, "as"), ({"program": None}, "program"), ({"trace": None}, "trace"),
    ({"at": None}, "at"), ({"sha256": None}, "sha256"), ({"items": None}, "items"),
    ({"epoch": "2026-11-05"}, "epoch"), ({"epoch": "2026-Q5"}, "epoch"), ({"as": "paratype"}, "as"),
    ({"program": {"name": "open-self"}}, "program"), ({"trace": {"sha256": "3" * 64}}, "trace"),
    ({"at": "yesterday"}, "at"), ({"sha256": "abc"}, "sha256"), ({"items": ["F:form/b", "A:a/a"]}, "items"),
    ({"items": "all"}, "items"), ({"for": {"path": "notes.md"}}, "for"), ({"withheld": ["A:affinity/x"]}, "withheld"),
    ({"key": "AAAA-BBBB"}, "key"),
])
def test_release_shape_catches_each_malformed_release(holo, change, field):
    entry = {k: v for k, v in {**GOOD, **change}.items() if v is not None}
    assert field in [f for f, _ in A.release_problems(entry)]
    cat = mc.yaml_load((holo / "holograph.cosm").read_text(encoding="utf-8"))
    cat["releases"] = [entry]
    (holo / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    rep = A.lint_holograph(holo)
    assert [p.check for p in rep.errors] == ["release-shape"] * len(rep.errors) and rep.errors
    assert any(p.field.startswith(f"releases[0].{field}") for p in rep.errors)


def test_a_well_formed_release_and_morphs_pass(holo):
    assert A.release_problems(GOOD) == [] and A.release_problems({**GOOD, "as": "cryptograph", "items": "all"}) == []
    assert A.release_problems({**GOOD, "for": {"path": "notes.md", "sha256": "5" * 64}}) == []
    cat = mc.yaml_load((holo / "holograph.cosm").read_text(encoding="utf-8"))
    cat.update(releases=[GOOD], morphs=["salt-and-crumb.morph.cosm", "letters/x.morph.cosm", "notes.cosm"])
    (holo / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    rep = A.lint_holograph(holo)
    assert [(p.check, p.field) for p in rep.problems()] == [("release-shape", "morphs[1]"),
                                                            ("release-shape", "morphs[2]")]


def test_a_release_is_appended_never_rewritten_and_read_back(holo):
    _public(holo)
    data, rec = A.project_isograph(holo, epoch="2026-Q3", program=PROG, trace=TRACE, at=NOW)
    text1 = (holo / "holograph.cosm").read_text(encoding="utf-8")
    A.append_release(holo, dict(GOOD, epoch="2026-Q4", sha256="6" * 64))
    text2 = (holo / "holograph.cosm").read_text(encoding="utf-8")
    assert text2.startswith(text1) and len(text2) > len(text1)                 # appended; nothing before it moved
    rel = A.releases(holo)
    assert [r["epoch"] for r in rel] == ["2026-Q3", "2026-Q4"] and rel[0]["sha256"] == rec["sha256"]
    assert A.released(holo, sha256=hashlib.sha256(data).hexdigest())["as"] == "isograph"
    assert A.released(holo, sha256="7" * 64) is None
    with pytest.raises(A.AscribeError, match="not in its shape"):
        A.append_release(holo, dict(GOOD, epoch="today"))
    assert A.lint_holograph(holo).errors == []


def _public(root: Path, ids=("A:affinity/fast-bread",)) -> bool:
    """Mark the sample's nodes `visibility: public` (the sample keeps everything internal)."""
    for p in root.rglob("*.cosm"):
        data = mc.yaml_load(p.read_text(encoding="utf-8"))
        nodes = data.get("nodes") if isinstance(data, dict) else None
        if isinstance(nodes, list) and any(n.get("id") in ids for n in nodes):
            for n in nodes:
                if n.get("id") in ids:
                    n["visibility"] = "public"
            p.write_text(mc.dump(data), encoding="utf-8")
    return True


def test_a_release_for_a_text_is_what_the_released_check_reads(holo):
    A.append_release(holo, dict(GOOD, **{"for": {"path": "notes.md", "sha256": "8" * 64}}))
    assert A.released(holo, path="notes.md")["for"]["sha256"] == "8" * 64
    assert A.released(holo, sha256="8" * 64) is not None and A.released(holo, path="other.md") is None


# ---------------------------------------------------------------------------
# E1. propose (section 9; THYM 6.3), with a scripted coprocessor
# ---------------------------------------------------------------------------

JOURNAL_SHA = hashlib.sha256((JOURNAL / "journal.md").read_bytes()).hexdigest()
PROPOSALS = """candidates:
  - kind: skill
    name: Splicing an eye by hand
    summary: Splices a new eye into a mooring line by hand, as a retired harbour pilot once showed.
    form: knots
    span: {lines: "3"}
    confidence: 0.8
    cites: [P:claim/spliced-an-eye]
  - kind: concern
    name: A neighbour's rent
    summary: Worries that Margaret Hollis cannot pay the rent.
    form: rye
    span: {lines: "4"}
    confidence: 0.6
    cites: [P:claim/baked-instead]
  - kind: yearning
    name: Reading the weather
    summary: Wants to learn to read the weather from the clouds.
    about: the weather
    span: {lines: "5"}
    confidence: 0.7
    cites: [P:claim/learn-the-weather]
"""


def test_propose_is_declared_by_ascribe_for_thym_1():
    from enough.thym import declarations as dc
    d = dc.load()["propose"]
    assert (d.owner, d.since, d.asks, d.gives, d.takes, d.modifiers["with"]) == (
        "ascribe", 1, True, ("list of item",), (("fabula",),), ("volume",))
    assert d.contract == ("no-invention", "provenance") and d.scaffold is None
    assert d.code == "enough.thym.moves.ascribe:propose"
    assert "propose" not in dc.load().view(0)


def _propose_run(tmp_path: Path, holo: Path, answer: str):
    from enough import thym
    from enough import thym_host as H
    from enough.thym import Refusal
    from enough.thym import run as RUN
    from enough.thym.coprocessor import candidate
    from enough.thym.values import digest_path

    class Scripted:
        def __init__(self):
            self.sent = []

        def complete(self, contract, inputs, *, budget):
            self.sent.append((contract.get("move"), sorted(inputs)))
            return candidate(answer, engine="model:scripted", tokens=40)

    shutil.copy(JOURNAL / "journal.md", tmp_path / "journal.md")
    shutil.copy(JOURNAL / "journal.md.fabulan.cosm", tmp_path / "journal.md.fabulan.cosm")
    p = tmp_path / "read-my-journal.thym"
    p.write_text("thym 1\n\nprogram read-my-journal\n  why: read my own journal for what it shows of me, and ask me "
                 "about each.\n  takes f: fabula, h: volume\n  gives found: list of item\n  give propose f with h\nend\n",
                 encoding="utf-8")
    f = tmp_path / "journal.md.fabulan.cosm"
    rows = [{"name": "f", "type": "fabula", "path": str(f), "sha256": digest_path(f)},
            {"name": "h", "type": "volume", "path": str(holo), "sha256": digest_path(holo)}]
    plan = thym.plan_file(p, rows)
    assert not isinstance(plan, Refusal), plan
    cp = Scripted()
    engines = {**H.engines(feed=None), "ascribe": A.thym_engine()}
    t = RUN.run(plan, inputs_root=tmp_path, root=tmp_path / "root", program=p, coprocessor=cp, engines=engines,
                now=dt.datetime(2026, 11, 5, 20, 0, tzinfo=dt.timezone.utc))
    return t, cp


def test_propose_runs_and_gives_candidates_each_with_its_question(tmp_path, holo):
    before = tree_bytes(holo)
    t, cp = _propose_run(tmp_path, holo, PROPOSALS)
    assert t.landed, t.refusal
    assert cp.sent == [("propose", ["fabula", "forms"])]
    rec = t.records[0]
    assert {c["name"]: c["ok"] for c in rec["checks"]} == {"no-invention": True, "provenance": True}
    out = mc.yaml_load(t.outputs["found"].read_text(encoding="utf-8"))
    got = [m for m in out["members"]]
    ids = [d["id"] for d in got]
    assert ids == ["F:form/knots", "S:skill/splicing-an-eye-by-hand", "D:question/splicing-an-eye-by-hand-candidate",
                   "Y:yearning/reading-the-weather", "D:question/reading-the-weather-candidate"]
    assert tree_bytes(holo) == before                                   # a run writes nothing into the holograph
    skill = got[1]
    assert skill["provenance"] == {"mode": "derived", "sources": [f"journal.md#sha256:{JOURNAL_SHA}"],
                                   "confidence": 0.8, "state": "pending"}
    assert skill["span"] == {"lines": "3"} and skill["form"] == "F:form/knots"
    assert skill["made"]["move"] == "propose" and skill["made"]["run"] == t.run_id
    assert got[3]["form"] == {"pending": "the weather"}
    q = got[2]
    assert (q["about"], q["why"], q["to"], q["kind"], q["options"]) == (skill["id"], "unsure", "holder", "choice",
                                                                        ["yes", "no", "partly"])
    assert not any("Hollis" in json.dumps(mc.jsonable(d)) for d in got)          # the candidate with a name refused


def test_propose_refuses_in_plain_words_without_its_engine(tmp_path, holo):
    from enough.thym.moves import MoveError
    from enough.thym.moves import ascribe as M
    from enough.thym.values import read_value

    class Ctx:
        engines: dict = {}
    f = read_value(JOURNAL / "journal.md.fabulan.cosm", "fabula")
    h = read_value(holo, "volume")
    with pytest.raises(MoveError, match="needs the ascribe engine"):
        M.propose(Ctx(), f, **{"with": h})
    with pytest.raises(MoveError, match="reads a holograph"):
        M.propose(Ctx(), f, **{"with": read_value(REPO / "tests/fixtures/cosm/holotypes/meadow", "volume")})


def _land_journal(holo: Path) -> list[dict]:
    props = mc.yaml_load(PROPOSALS)["candidates"]
    got, refused = A.candidates(holo, props, text="journal.md", sha256=JOURNAL_SHA, feed=feed, at=NOW,
                                made={"move": "propose", "run": "r1"})
    assert [i for i, _ in refused] == [1] and "personal data" in refused[0][1]
    A.land_candidates(holo, got)
    return got


def test_candidates_land_as_candidates_and_are_not_the_holders(holo):
    got = _land_journal(holo)
    data = items(holo)
    skill = data["S:skill/splicing-an-eye-by-hand"]
    assert skill["provenance"]["state"] == "pending" and skill["made"] == {"move": "propose", "run": "r1"}
    assert clean(holo) == ([], [])
    assert A.raise_bank(holo, at=NOW) and not any(q["about"] == skill["id"] for q in A.raise_bank(holo, at=NOW))
    with pytest.raises(A.AscribeError, match="already holds"):
        A.land_candidates(holo, got)
    with pytest.raises(A.AscribeError, match="not a candidate"):
        A.land_candidates(holo, [node("A:affinity/sneaked-in")])


def test_yes_makes_a_candidate_the_holders(holo):
    _land_journal(holo)
    got = A.answer(holo, "D:question/splicing-an-eye-by-hand-candidate", "yes", confidence=0.9, at=NOW)
    assert got.settled.settled == [("D:question/splicing-an-eye-by-hand-candidate", ["S:skill/splicing-an-eye-by-hand"])]
    prov = items(holo)["S:skill/splicing-an-eye-by-hand"]["provenance"]
    assert "state" not in prov and prov["confidence"] == 0.9
    assert prov["sources"] == [f"journal.md#sha256:{JOURNAL_SHA}", "D:session/session-3"]
    assert clean(holo) == ([], [])


def test_no_removes_the_candidate_and_closes_its_question(holo):
    _land_journal(holo)
    got = A.answer(holo, "D:question/splicing-an-eye-by-hand-candidate", "no", at=NOW)
    assert got.settled.removed == ["S:skill/splicing-an-eye-by-hand"]
    data = items(holo)
    assert "S:skill/splicing-an-eye-by-hand" not in data and "F:form/knots" not in data     # its form went with it
    q = data["D:question/splicing-an-eye-by-hand-candidate"]
    assert q["state"] == "answered" and q["settled"]["wrote"] == [] and q["answers"][0]["value"] == "no"
    assert clean(holo) == ([], [])
    assert not any(x["about"] == "S:skill/splicing-an-eye-by-hand" for x in A.raise_bank(holo, at=NOW))


def test_partly_keeps_it_and_asks_the_holder_to_say_it_their_way(holo):
    _land_journal(holo)
    got = A.answer(holo, "D:question/reading-the-weather-candidate", "partly", at=NOW)
    (_q, fu), = got.settled.follow_ups
    assert items(holo)[fu]["about"] == "Y:yearning/reading-the-weather#summary"
    A.answer(holo, fu, "Wants to know when the squalls are coming.", at=NOW)
    assert items(holo)["Y:yearning/reading-the-weather"]["summary"] == "Wants to know when the squalls are coming."


def test_i_dont_know_leaves_a_candidate_a_candidate(holo):
    _land_journal(holo)
    A.answer(holo, "D:question/reading-the-weather-candidate", "I don't know", at=NOW)
    assert items(holo)["Y:yearning/reading-the-weather"]["provenance"]["state"] == "pending"


# ---------------------------------------------------------------------------
# E2. project … as isograph (section 14.1)
# ---------------------------------------------------------------------------

def test_the_isograph_of_the_sample_is_the_texts_example(holo):
    _public(holo)
    data, rec = A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, at="2026-11-05T14:15:00Z")
    assert data.decode("utf-8") == SPEC_ISOGRAPH
    assert rec == {"epoch": "2026-Q4", "as": "isograph", "program": PROG, "trace": TRACE,
                   "at": dt.datetime(2026, 11, 5, 14, 15, tzinfo=dt.timezone.utc),
                   "sha256": hashlib.sha256(data).hexdigest(), "items": ["A:affinity/fast-bread", "F:form/sourdough"]}
    assert A.releases(holo) == [rec] and A.lint_holograph(holo).problems() == []


def test_default_deny_only_the_fields_the_schema_names(holo):
    write_nodes(holo, "A/more.cosm", node("A:affinity/loud", visibility="public", valence="for", strength=5,
                                          when="2014-06-03", secret="a field nobody named", status="active",
                                          links=[{"rel": "like", "to": "A:affinity/fast-bread"}], of=None))
    doc, _ = A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    assert set(doc) == {"isograph", "hid", "handle", "epoch", "sample", "program", "run", "self"}
    assert doc["self"] == [{"kind": "affinity", "form": "sourdough", "valence": "for", "strength": "strong",
                            "when": "2010s", "marking": "stated"}]
    assert A.isograph_problems(doc) == []


@pytest.mark.parametrize("extra, where", [
    ({"visibility": "restricted"}, "A/more.cosm"),
    ({}, "A/hidden/more.cosm"),
    ({"provenance": {"mode": "derived", "sources": ["x.md#sha256:" + "a" * 64], "confidence": 0.9,
                     "state": "pending"}}, "A/more.cosm"),
    ({"provenance": {"mode": "manual", "sources": ["self"], "confidence": 0.4}}, "A/more.cosm"),
    ({"status": "retired"}, "A/more.cosm"),
    ({"form": "F:form/celestial-navigation"}, "A/more.cosm"),
    ({"form": "F:form/sea-glass"}, "A/more.cosm"),
])
def test_what_never_appears_in_an_isograph(holo, extra, where):
    n = node("A:affinity/hidden-one", visibility="public", valence="mixed")
    n.update(extra)
    write_nodes(holo, where, n)
    if "hidden" in where:
        (holo / "A" / "hidden" / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    doc, ids = A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    assert doc["self"] == [] and ids == []


def test_no_d_item_ever_appears_and_every_entry_is_stated(holo):
    A.raise_bank(holo, at=NOW)
    A.answer(holo, "D:question/ascribe-i1", "Anything about sourdough and its starters.", at=NOW)
    _public(holo, ids=[k for k in items(holo) if k[0] in "ABCEIOQSUY"])
    doc, ids = A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    text = A.canonical_json(doc).decode()
    assert not any(i.startswith("D:") for i in ids) and "question" not in text and "starters" not in text
    assert {x["marking"] for x in doc["self"]} == {"stated"} and doc["self"]
    rows = [(A.CONTAINERS.index(next(L for L, k in A.KINDS.items() if k == x["kind"])), x["form"]) for x in doc["self"]]
    assert rows == sorted(rows)
    assert not re.search(r"[0-9]", re.sub(r"[0-9]{3}0s", "", json.dumps(doc["self"])))    # no number but a decade


def test_a_polyform_leaves_as_its_sorted_words_only_when_every_form_is_feeds(holo):
    forms = [{"id": f"F:form/{w}", "type": "form", "name": w, "summary": f"{w}.", "feed": {"word": w, "origin": "feed"},
              "provenance": {"mode": "manual", "sources": ["self"], "confidence": 1}} for w in ("tides", "knots")]
    poly = {"id": "F:polyform/sea-work", "type": "polyform", "name": "sea work", "summary": "Tides and knots.",
            "forms": ["F:form/tides", "F:form/knots"],
            "provenance": {"mode": "manual", "sources": ["self"], "confidence": 1}}
    write_nodes(holo, "F/more.cosm", *forms, poly)
    write_nodes(holo, "S/more.cosm", node("S:skill/sea-work", form="F:polyform/sea-work", visibility="public"),
                node("S:skill/crafts", form="F:polyform/slow-crafts", visibility="public"))
    doc, ids = A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    assert doc["self"] == [{"kind": "skill", "form": ["knots", "tides"], "marking": "stated"}]
    assert ids == ["F:form/knots", "F:form/tides", "F:polyform/sea-work", "S:skill/sea-work"]


def test_no_pii_refuses_a_projection_and_a_marker_lets_it_go(holo):
    _public(holo)
    (holo / "O" / "opinions.cosm").write_text("# write back to someone@example.net\n"
                                              + (holo / "O" / "opinions.cosm").read_text(encoding="utf-8"),
                                              encoding="utf-8")
    assert A.lint_holograph(holo).errors == []                      # a warning in the holograph, never an error
    with pytest.raises(A.AscribeError, match="no-pii"):
        A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    assert A.releases(holo) == []                                    # refused: nothing recorded
    (holo / "O" / "private").mkdir()
    (holo / "O" / "opinions.cosm").rename(holo / "O" / "private" / "opinions.cosm")
    (holo / "O" / "private" / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE)


def test_one_isograph_per_epoch_and_a_program_keeps_back_never_adds(holo):
    _public(holo, ids=("A:affinity/fast-bread", "A:affinity/sourdough-baking"))
    doc, ids = A.isograph_doc(holo, epoch="2026-Q4", program=PROG, trace=TRACE, keep=["A:affinity/fast-bread",
                                                                                     "E:experience/not-there"])
    assert len(doc["self"]) == 1 and "A:affinity/sourdough-baking" not in ids
    A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    with pytest.raises(A.AscribeError, match="one isograph per epoch"):
        A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    A.project_isograph(holo, epoch="2026-11", program=PROG, trace=TRACE)


@pytest.mark.parametrize("change, said", [
    ({"self": [{"kind": "affinity", "form": "sourdough", "marking": "verified"}]}, "verified"),
    ({"name": "Somebody"}, "does not name: name"),
    ({"self": [{"kind": "affinity", "form": "sourdough", "marking": "stated", "summary": "free text"}]},
     "does not name: summary"),
    ({"self": [{"kind": "affinity", "form": "sourdough", "marking": "stated", "strength": 4}]}, "band"),
    ({"self": [{"kind": "affinity", "form": "sourdough", "marking": "stated", "when": "2014"}]}, "decade"),
    ({"handle": "Ann Quill"}, "handle"),
])
def test_a_reader_refuses_an_isograph_with_an_unnamed_field_or_verified(change, said):
    doc = {**json.loads(SPEC_ISOGRAPH), **change}
    assert any(said in p for p in A.isograph_problems(doc))
    assert A.isograph_problems(json.loads(SPEC_ISOGRAPH)) == []


def test_the_isograph_arm_reaches_only_its_engine(holo):
    from enough.thym.moves import MoveError
    from enough.thym.moves import ascribe as M
    from enough.thym.values import Value, read_value
    _public(holo)

    class Ctx:
        now = dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone.utc)
        emitted = [Value("item", {"id": "A:affinity/fast-bread"}, origin={"id": "A:affinity/fast-bread"})]
        withheld: dict = {}
        stage = None
        run = "2026-11-05-1415-ab12"
        engines = {"ascribe": A.thym_engine()}

        def trace(self):
            return Value("trace", {"program": {"name": "open-self", "sha256": "2" * 64}})
    v = M.isograph(Ctx(), read_value(holo, "volume"))
    assert v.type == "volume" and v.payload["self"][0]["form"] == "sourdough" and A.releases(holo) == []
    Ctx.engines = {}
    with pytest.raises(MoveError, match="needs the ascribe engine"):
        M.isograph(Ctx(), read_value(holo, "volume"))


# ---------------------------------------------------------------------------
# E3. Match tokens, the cryptograph, the isomorph (sections 14.2, 14.3, 14.5)
# ---------------------------------------------------------------------------

def test_match_tokens_for_the_forms_the_holder_chooses(holo):
    _public(holo, ids=("A:affinity/fast-bread", "A:affinity/sourdough-baking"))
    key = b"k" * 32
    data, got_key, rec = A.make_tokens(holo, [{"about": "affinity", "form": "sourdough"},
                                              {"about": "form", "form": "F:form/sourdough"}],
                                       of="b" * 26, epoch="2026-Q4", program=PROG, trace=TRACE, key=key, at=NOW)
    doc = json.loads(data)
    assert got_key == key and set(doc) == {"tokens", "of", "epoch", "entries"} and doc["tokens"] == "ascribe-tokens/0"
    want = {hmac.new(key, f"affinity\n{v}".encode(), hashlib.sha256).hexdigest()
            for v in ("sourdough for", "sourdough against")}
    want.add(hmac.new(key, b"form\nsourdough", hashlib.sha256).hexdigest())
    assert {e["token"] for e in doc["entries"]} == want
    assert [e["token"] for e in doc["entries"]] == sorted(e["token"] for e in doc["entries"])
    assert rec["as"] == "tokens" and rec["sha256"] == hashlib.sha256(data).hexdigest()
    assert key.hex() not in (holo / "holograph.cosm").read_text() and "kkkk" not in (holo / "holograph.cosm").read_text()
    with pytest.raises(A.AscribeError, match="grounded in FEED"):
        A.make_tokens(holo, [{"about": "form", "form": "celestial-navigation"}], of="b" * 26, epoch="2026-Q4",
                      program=PROG, trace=TRACE)
    with pytest.raises(A.AscribeError, match="chose no form"):
        A.make_tokens(holo, [], of="b" * 26, epoch="2026-Q4", program=PROG, trace=TRACE)


def test_a_cryptograph_of_the_whole_holograph_opens_with_its_key_and_carries_only_what_the_filter_keeps(holo):
    from enough.thym import vault
    A.raise_bank(holo, at=NOW)
    _land_journal(holo)
    write_nodes(holo, "A/more.cosm", node("A:affinity/secret", visibility="restricted"), node("A:affinity/open"))
    sealed, key, rec = A.cryptograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, at=NOW)
    opened = vault.open(sealed, key)
    assert isinstance(opened, bytes)
    cat = mc.yaml_load(opened.decode("utf-8"))
    paths = [r["path"] for r in cat["contents"]]
    assert not any(p.startswith("D/") for p in paths) and {r["role"] for r in cat["contents"]} == {"holograph"}
    body = opened.decode("utf-8")
    assert "A:affinity/open" in body and "A:affinity/secret" not in body
    assert "splicing-an-eye" not in body                                        # a candidate never leaves
    header = mc.yaml_load(sealed.decode("utf-8"))
    assert header["encrypted"]["hid"] != "aej6l5qrka6c6btarfiy2f7vnj" and A.HID_RE.match(header["encrypted"]["hid"])
    assert rec["as"] == "cryptograph" and rec["items"] == "all" and rec["sha256"] == hashlib.sha256(sealed).hexdigest()
    assert key not in (holo / "holograph.cosm").read_text()


def test_a_cryptograph_of_a_projection(holo):
    from enough.thym import vault
    _public(holo)
    data, irec = A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE)
    sealed, key, rec = A.cryptograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, projection=data,
                                     program_text="thym 1\n", trace_text="oes: thym/1\n", items=irec["items"])
    cat = mc.yaml_load(vault.open(sealed, key).decode("utf-8"))
    assert [(r["path"], r["role"]) for r in cat["contents"]] == [("projection.json", "projection"),
                                                                ("program.thym", "program"), ("trace.cosm", "trace")]
    assert rec["items"] == irec["items"]
    with pytest.raises(A.AscribeError, match="would not read"):
        A.cryptograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, projection=b'{"isograph": 1}',
                      program_text="", trace_text="", items=["x"])


def test_an_isomorph_leaves_without_its_evidence(holo, tmp_path):
    morph = {"oes": "thym/1", "kind": "morph", "id": "thym/salt-and-crumb-morph", "nodes": [
        {"id": "M:morph/letters", "type": "morph", "name": "letters", "summary": "How the holder writes letters.",
         "scales": {"formality": 2}, "evidence": [{"quote": "a line of a letter"}],
         "derived": {"from": ["letter.md#sha256:" + "c" * 64], "at": "2026-11-01"}}]}
    (holo.parent / "salt-and-crumb.morph.cosm").write_text(mc.dump(morph), encoding="utf-8")
    cat = mc.yaml_load((holo / "holograph.cosm").read_text(encoding="utf-8"))
    cat["morphs"] = ["salt-and-crumb.morph.cosm"]
    (holo / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    raw, rec = A.isomorph(holo, "salt-and-crumb.morph.cosm", "M:morph/letters", epoch="2026-Q4", program=PROG,
                          trace=TRACE)
    out = mc.yaml_load(raw.decode("utf-8"))["nodes"][0]
    assert out["shared"] is True and "evidence" not in out and "from" not in out.get("derived", {})
    assert rec["items"] == ["M:morph/letters"] and A.lint_holograph(holo).errors == []


# ---------------------------------------------------------------------------
# F. The manifest, and every holograph that was valid stays valid
# ---------------------------------------------------------------------------

def test_the_manifest_as_the_text_now_has_it():
    reg = mc.default_registry()
    assert reg.problems == []
    m = reg.get("ascribe")
    cat = m._block("catalog")
    assert {"releases", "morphs"} <= set(cat["keys"]) and cat["release-as"] == list(A.RELEASE_AS)
    dia = m._block("dialectic")
    assert dia["to"] == "holder" and dia["writes"]["F"] == "F:form"
    assert {k: v.split(":")[1] for k, v in dia["writes"].items() if k != "F"} == A.KINDS
    assert [e["about"] for e in dia["follow-ups"]] == ["#form", "#when", "#valence", "#strength"]
    bank, = m.banks()
    assert bank["name"] == "ascribe" and len(bank["questions"]) == 44 and bank["to"] == "holder"
    assert m.data["filter"]["applies-to"] == list(A.FILTER_USES)
    pp = m.data["public-projection"]
    assert pp["schema"] == A.ISOGRAPH and pp["fields"] == list(A.ISOGRAPH_KEYS)
    assert pp["self-fields"] == list(A.ISOGRAPH_SELF_KEYS) and pp["derivable"] == []
    text = (REPO / "defaults/cosm/manifests/ascribe.manifest.cosm").read_text(encoding="utf-8")
    assert "not built" not in text and "the process that asks them is reserved" not in text
    assert "filter that applies it is reserved" not in text and "release-shape" in m._block("checks")["own"]


@pytest.mark.parametrize("name, errors, warnings", [("sample-self", 0, 0), ("bad/pii", 0, 7),
                                                   ("bad/unanchored", 1, 0), ("bad/undeclared-relation", 1, 0)])
def test_every_fixture_loads_as_before(name, errors, warnings):
    rep = A.lint_holograph(FIX / name)
    assert (len(rep.errors), len(rep.warnings), len(rep.notes)) == (errors, warnings, 0)


def test_the_command_line_is_lint_alone():
    with pytest.raises(SystemExit):
        A.main(["ask", str(SAMPLE)])


# ---------------------------------------------------------------------------
# The specification's own blocks (cosmoes-site/specs/ascribe.md)
# ---------------------------------------------------------------------------

def _blocks(kind: str) -> list[str]:
    if not SPEC.is_file():
        pytest.skip(f"the specification's checkout is absent ({SPEC}); its blocks cannot be read here")
    return re.findall(rf"^```{kind}\n(.*?)^```", SPEC.read_text(encoding="utf-8"), re.S | re.M)


def _spec_holograph(tmp_path: Path) -> Path:
    cosm, = _blocks("cosm")
    root = tmp_path / "spec-self"
    root.mkdir()
    (root / "holograph.cosm").write_text(cosm, encoding="utf-8")
    return root


def test_the_texts_cosm_example_lints_clean(tmp_path):
    root = _spec_holograph(tmp_path)
    rep = A.lint_holograph(root)
    assert rep.problems() == [] and len(rep.volume.items) == 5


def test_the_texts_json_isograph_is_what_the_projection_gives(tmp_path):
    js, = _blocks("json")
    doc = json.loads(js)
    # the text's example still names a trace digest (errata); with the ruling applied it reads clean
    assert A.isograph_problems(doc) == ["fields ascribe-isograph/0 does not name: trace", "no run"]
    assert A.canonical_json(doc).decode() == js.strip() and A.isograph_problems(json.loads(ruled(js))) == []
    root = _spec_holograph(tmp_path)
    frag = next(b for b in _blocks("yaml") if b.startswith("# A/affinities.cosm"))
    nodes = mc.yaml_load(frag)["nodes"]
    nodes[0]["visibility"] = "public"
    write_nodes(root, "A/affinities.cosm", *nodes)
    data, rec = A.project_isograph(root, epoch="2026-Q4", program=PROG, trace=TRACE)
    assert data.decode("utf-8") == ruled(js) == SPEC_ISOGRAPH


def test_the_texts_yaml_fragments_read(tmp_path):
    frags = _blocks("yaml")
    session = next(b for b in frags if b.startswith("# D/session-3.cosm"))
    release = next(b for b in frags if b.startswith("releases:"))
    for entry in mc.yaml_load(release)["releases"]:
        assert A.release_problems(entry) == []
    root = _spec_holograph(tmp_path)
    (root / "D").mkdir()
    (root / "D" / "session-3.cosm").write_text(session, encoding="utf-8")
    cat = mc.yaml_load((root / "holograph.cosm").read_text(encoding="utf-8"))
    cat.update(mc.yaml_load(release))
    (root / "holograph.cosm").write_text(mc.dump(cat), encoding="utf-8")
    rep = A.lint_holograph(root)
    assert [p for p in rep.errors if p.check != "question-about"] == []
    assert not any(p.check in ("release-shape", "no-pii", "form-anchored") for p in rep.problems())


# ---------------------------------------------------------------------------
# The rulings of 2026-11-06 on what leaves a holograph
# ---------------------------------------------------------------------------

CANDIDATE_PROV = {"mode": "derived", "sources": ["notes.md#sha256:" + "a" * 64], "confidence": 0.6,
                  "state": "pending"}


@pytest.mark.parametrize("use,own", [("ingest", False), ("package", False), ("transfer", False),
                                     ("transfer", True), ("projection", False)])
def test_a_candidate_and_its_questions_never_leave(holo, use, own):
    """Ruling 1: a candidate is not part of the self until the holder says yes; the filter withholds it, and every
    question about it, from every use (a transfer into the holder's own keeping too)."""
    write_nodes(holo, "A/proposed.cosm", node("A:affinity/rye", visibility="public", provenance=CANDIDATE_PROV),
                node("A:affinity/kept", visibility="public"))
    q = {"id": "D:question/is-rye-yours", "type": "question", "about": "A:affinity/rye", "asks": "Is this yours?",
         "kind": "choice", "options": ["yes", "no"], "state": "open", "to": "holder",
         "raised": {"by": "rules", "from": "propose"}}
    write_nodes(holo, "D/candidates.cosm", q)
    f = A.private_filter(holo, use=use, own_keeping=own)
    everything = b"".join(f.files.values()).decode("utf-8")
    assert "A:affinity/rye" not in everything and "D:question/is-rye-yours" not in everything
    assert "A:affinity/kept" in everything and "A/proposed.cosm" in f.rewritten


def test_the_release_record_never_leaves(holo):
    """Ruling 2: the catalog's `releases:` is the holder's own account of what left: the filter withholds it from
    every use, a cryptograph of the whole holograph included, and leaves the rest of the catalog as it was."""
    _public(holo)
    A.project_isograph(holo, epoch="2026-Q3", program=PROG, trace=TRACE, at=NOW)
    assert A.releases(holo)
    for use in A.FILTER_USES:
        cat = mc.yaml_load(A.private_filter(holo, use=use).files["holograph.cosm"].decode("utf-8"))
        assert "releases" not in cat and cat["handle"] == "salt-and-crumb"
    sealed, key, _rec = A.cryptograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, at=NOW)
    assert TRACE["sha256"].encode() not in sealed


def test_an_isograph_names_its_run_and_the_release_carries_the_trace_digest(holo):
    """Ruling 3: an isograph cannot carry its own run's trace digest (the trace is not finished when it is written):
    it names the program and the run's id, and the release record carries the trace's digest."""
    _public(holo)
    data, rec = A.project_isograph(holo, epoch="2026-Q4", program=PROG, trace=TRACE, at=NOW)
    doc = json.loads(data)
    assert doc["run"] == TRACE["run"] and "trace" not in doc and "3" * 64 not in data.decode()
    assert rec["trace"] == TRACE and A.isograph_problems(doc) == []
    assert A.isograph_problems({**doc, "run": "yesterday"}) == ["run is the id of the run that made it"]


# ---------------------------------------------------------------------------
# `project h as isograph` through Thym (THYM 6.2, 6.3, 18; Ascribe 14.1): the kind Ascribe adds to Comprise's move
# ---------------------------------------------------------------------------

OPEN_SELF = """thym {v}

program open-self
  why: what a person says they like, as they say it, and nothing more.
  takes h: volume
  gives i: volume

  for each a in h where kind is affinity
    emit a
  end
  give project h as isograph
end
"""


def _open_self(tmp_path: Path, v: str):
    from enough import thym
    from enough.thym.values import digest_path
    root = _spec_holograph(tmp_path)
    frag = next(b for b in _blocks("yaml") if b.startswith("# A/affinities.cosm"))
    nodes = mc.yaml_load(frag)["nodes"]
    nodes[0]["visibility"] = "public"
    write_nodes(root, "A/affinities.cosm", *nodes)
    prog = tmp_path / "open-self.thym"
    prog.write_text(OPEN_SELF.format(v=v), encoding="utf-8")
    return root, prog, thym.plan_file(prog, [{"name": "h", "type": "volume", "path": str(root),
                                              "sha256": digest_path(root)}])


def test_ascribe_adds_isograph_to_project_for_thym_1_only():
    from enough.thym import declarations as dc
    decls = dc.load()
    assert decls.problems == []
    p = decls["project"]
    assert p.owner == "comprise" and p.view(0).modifiers["as"] == ("isotype", "paratype")
    assert p.view(0).contract_when == () and p.view(0).code_when == ()
    one = p.view(1)
    assert one.modifiers["as"] == ("isotype", "paratype", "isograph")
    assert dc.chosen(one, as_word="isotype")["contract"] == p.contract          # Comprise's kinds: Comprise's contract
    assert dc.chosen(one, as_word="isograph")["contract"] == ("default-deny", "no-counts", "no-mark", "epoch",
                                                              "provenance")
    assert one.code_when == ((("isograph",), "enough.thym.moves.ascribe:isograph", "ascribe"),)


def test_project_as_isograph_runs_on_the_sample_to_the_texts_example(tmp_path):
    from enough import thym_host as H
    from enough.thym import Refusal
    from enough.thym import run as RUN
    root, prog, pl = _open_self(tmp_path, "1")
    assert not isinstance(pl, Refusal), pl
    t = RUN.run(pl, inputs_root=tmp_path, root=tmp_path / "runs", program=prog, engines=H.engines(feed=None),
                now=dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone.utc))
    assert t.landed, t.refusal
    got = (t.dir / "outputs" / "isograph.json").read_text(encoding="utf-8")
    # the text's example, byte for byte, but for what only this run can know: its program's digest and its run's id
    js, = _blocks("json")
    want = json.loads(ruled(js))
    want["program"]["sha256"] = hashlib.sha256(prog.read_bytes()).hexdigest()
    want["run"] = t.dir.name
    assert got == A.canonical_json(want).decode("utf-8")
    checks = {c["name"] for r in t.records for c in r.get("checks") or []} if hasattr(t, "records") else set()
    assert not checks or {"default-deny", "no-counts", "epoch"} <= checks
    assert A.releases(root) == []                 # nothing written into the holograph by the run itself


def test_project_as_isograph_in_a_thym_0_program_needs_thym_1(tmp_path):
    from enough.thym import Refusal
    _root, _prog, pl = _open_self(tmp_path, "0")
    assert isinstance(pl, Refusal) and (pl.stage, pl.check) == ("compile", "version")
    assert "this needs `thym 1`: the word isograph after as of project" in pl.message


def test_an_isograph_is_held_to_its_own_schema_and_an_isotype_to_comprises(holo):
    """One check name, two implementations: `default-deny` of an `as isograph` call reads ascribe-isograph/0; of an
    `as isotype` call, Comprise's keys, as before."""
    from enough.thym import checks as C
    from enough.thym.moves import ascribe as _M  # noqa: F401 - registers the isograph kind's checks
    from enough.thym.values import Value

    class Ctx:
        engines = {"ascribe": A.thym_engine()}
    doc = json.loads(SPEC_ISOGRAPH)
    iso = {"modifiers": {"as": "isograph"}}
    assert C.verdict("default-deny", Value("volume", doc), {}, iso, None, Ctx()) == (True, "")
    ok, why = C.verdict("default-deny", Value("volume", {**doc, "name": "Ann"}), {}, iso, None, Ctx())
    assert not ok and "does not name: name" in why
    ok, why = C.verdict("no-counts", Value("volume", {**doc, "self": [dict(doc["self"][0], strength=3)]}), {}, iso,
                        None, Ctx())
    assert not ok and "holds a number" in why
    ok, why = C.verdict("default-deny", Value("volume", doc), {}, {"modifiers": {"as": "isotype"}}, None, Ctx())
    assert not ok and "fields the target schema does not name" in why          # Comprise's implementation
