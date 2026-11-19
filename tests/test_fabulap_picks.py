"""The owner's four fabulap picks (docs/v080-pins.md section 13; MacroCOSM OES 18.4.2 `C:form`, 18.4.6; Thym 20.5, 20.9,
7.3 `form-grounded`), as enough's verse moves follow them:

1. A form's `scheme` is read across the whole poem, a sound that comes back in a later stanza keeping its first letter,
   and a rule that runs across stanzas is read from it; each `C:line`'s `rhyme` and each `C:rhyme` stay stanza-local.
   Fixtures written for these tests (lane W3-VP, 2026): `the-ferry-road.txt` (terza rima) and `porch-light.txt` (a
   villanelle); their FEED rows are reflib/dict's, in `feed-forms.json`.
2. A form's rule may be `held: {pending: "…"}`, and counts only once it is held or broken.
3. An answer to the fabulap bank's `breaks` (about `C:line`) or `stanza` (about `C:part`) writes the answerer's
   `P:reading` of those lines or stanzas through the entry's `writes`, never a new `C:line` or `C:part`.
4. 20.5's program is `decompile-verse-quick`.
"""
from __future__ import annotations

import copy
from pathlib import Path

from enough import dialectic as dl
from enough import fabulap_job as P
from enough import macrocosm as mc
from enough import verse_forms as VF
from enough import thym
from enough.thym import Refusal
from enough.thym.values import Value, read_value
from tests.test_verse_moves import FIX, MV, ctx_for, heard, items, verdict

REPO = Path(__file__).resolve().parents[1]
ROSE = REPO / "tests" / "fixtures" / "fabula" / "poems" / "the-sick-rose.txt.fabulap.cosm"
SHIPPED = REPO / "defaults" / "thym"
AT = "2026-11-18T12:00:00Z"


def _form(got: dict) -> dict:
    return next(it for it in items(got["form"]).values() if it["type"] == "form")


def _with_form(v: Value, **fields) -> Value:
    doc = copy.deepcopy(v.payload)
    for it in doc["nodes"]:
        if it.get("type") == "form":
            it.update(fields)
    return Value("fabula", doc)


# ---------------------------------------------------------------------------
# 1. The form's scheme, across the whole poem
# ---------------------------------------------------------------------------

def test_terza_rima_is_named_from_a_scheme_read_across_the_poem(tmp_path):
    _ctx, _poem, got = heard(tmp_path, "the-ferry-road.txt")
    form = _form(got)
    assert form["form"] == "terza rima" and form["scheme"] == "aba bcb cdc ded e"
    assert form["rules"] == [{"rule": "tercets", "held": True},
                             {"rule": "each one's middle line rhyming with the outer lines of the next (aba bcb cdc)",
                              "held": True},
                             {"rule": "iambic pentameter", "held": True},
                             {"rule": "a closing line or couplet", "held": True}]
    it = items(got["form"])
    # the lines and the rhymes keep a stanza's own letters, run on from stanza to stanza
    assert "".join(it[f"C:line/{n}"]["rhyme"] for n in range(1, 14)) == "abacdcefeghgi"
    rhymes = {v["id"]: (v["scheme"], v["lines"]) for v in it.values() if v["type"] == "rhyme"}
    assert rhymes["C:rhyme/still-will"] == ("c", ["C:line/4", "C:line/6"])      # `hill` (line 2) is another stanza's


def test_a_villanelle_of_the_fixtures_is_named_and_its_scheme_keeps_its_letters(tmp_path):
    _ctx, _poem, got = heard(tmp_path, "porch-light.txt")
    form = _form(got)
    assert form["form"] == "villanelle" and form["scheme"] == "aba aba aba aba aba abaa"
    assert [r["held"] for r in form["rules"]] == [True, True, True, True]
    it = items(got["form"])
    assert "".join(it[f"C:line/{n}"]["rhyme"] for n in range(1, 20)) == "abacdcefeghgijiklkk"


def test_a_broken_chain_is_read_from_the_scheme_and_names_no_terza_rima(tmp_path):
    work = tmp_path / "in"
    work.mkdir()
    text = (FIX / "the-ferry-road.txt").read_text(encoding="utf-8").replace("growing back", "growing still")
    (work / "broken.txt").write_text(text, encoding="utf-8")
    ctx = ctx_for(tmp_path, inputs_root=work)
    poem = read_value(work / "broken.txt", "text")
    prev = MV.scan(ctx, poem)
    for word in ("rhyme", "sound", "recurrence", "form"):
        prev = MV.scan(ctx, poem, **{"as": word, "with": prev})
    form = next(it for it in items(prev).values() if it["type"] == "form")
    # line 5 now ends on `still`, the second sound's: its letter is b across the poem, and the chain of line 5 to
    # lines 7 and 9 is broken
    assert form["scheme"] == "aba bbb cdc ded e" and form["form"] != "terza rima"
    f = VF.Facts(n=6, parts=[("C:part/1", [1, 2, 3]), ("C:part/2", [4, 5, 6])], syllables={}, beats={},
                 norm={}, end={n: f"w{n}" for n in range(1, 7)}, metre=None, turns=None,
                 rhymes=lambda a, b: {a, b} in ({1, 3}, {2, 4}, {2, 6}, {4, 6}) or a == b)
    assert f.scheme() == "aba bcb" and VF._terza_chain(f)[0] is True


def test_form_grounded_reads_the_scheme_across_the_poem(tmp_path):
    ctx, poem, got = heard(tmp_path, "the-ferry-road.txt")
    ins = {"poem": poem, "with": got["recurrence"]}
    assert verdict("form-grounded", got["form"], ins, ctx, "form") == (True, "")
    local = _with_form(got["form"], scheme="aba cdc efe ghg i")       # the stanza-local letters, not the form's
    ok, why = verdict("form-grounded", local, ins, ctx, "form")
    assert not ok and "read across the whole poem it is 'aba bcb cdc ded e'" in why


# ---------------------------------------------------------------------------
# 2. A pending rule counts once held or broken
# ---------------------------------------------------------------------------

def test_a_pending_rule_counts_only_once_held_or_broken(tmp_path):
    ctx, poem, got = heard(tmp_path, "sonnet-116.txt")
    form = _form(got)
    assert mc.is_pending(form["rules"][-1]["held"]) and form["provenance"]["confidence"] == 0.67
    assert VF.counted(form["rules"]) == [True, True, False]
    answered = copy.deepcopy(form["rules"])
    answered[-1]["held"] = True                                      # a person's answer: the turn is at line 13
    assert VF.counted(answered) == [True, True, False, True] and VF.confidence_of(answered) == 0.75
    ins = {"poem": poem, "with": got["recurrence"]}
    assert verdict("form-grounded", got["form"], ins, ctx, "form")[0] is True
    assert verdict("form-grounded", _with_form(got["form"], rules=answered), ins, ctx, "form") == (True, "")
    odd = copy.deepcopy(form["rules"])
    odd[-1]["held"] = "perhaps"
    ok, why = verdict("form-grounded", _with_form(got["form"], rules=odd), ins, ctx, "form")
    assert not ok and "held true, false or {pending: …}" in why
    flipped = copy.deepcopy(form["rules"])
    flipped[2]["held"] = True                                        # iambic pentameter, which the rule reads broken
    ok, why = verdict("form-grounded", _with_form(got["form"], rules=flipped), ins, ctx, "form")
    assert not ok and "'iambic pentameter' is broken" in why
    card = P.card_of({"nodes": [_with_form(got["form"], rules=answered).payload["nodes"][-1]] + [
        it for it in got["form"].payload["nodes"] if it.get("type") != "form"]})
    assert card["form"]["counted"] == 4 and card["form"]["confidence"] == 0.75
    assert [r["held"] for r in card["form"]["rules"]] == ["held", "held", "not held", "held"]
    card = P.card_of(got["form"].payload)
    assert card["form"]["counted"] == 3 and card["form"]["rules"][-1]["held"] == "open"


def test_no_rule_counted_yet_is_the_cap():
    assert VF.confidence_of([{"rule": "a turn", "held": {"pending": "where?"}}]) == VF.FORM_CAP
    assert VF.counted([{"rule": "x", "held": {"pending": "?"}}, {"rule": "y", "held": False}]) == [False]


# ---------------------------------------------------------------------------
# 3. `breaks` and `stanza` write the answerer's reading
# ---------------------------------------------------------------------------

def _answered(entry: str, says: str, to: str = "author") -> tuple[dl.Twin, dl.Settled, dict]:
    t = dl.open_twin(ROSE)
    r = dl.raise_questions(t, at=AT, banks=["fabulap"], pending=False, unsure=False)
    q = next(q for q in r.questions if (q.get("raised") or {}).get("from") == f"fabulap/{entry}")
    q = {**q, "to": to}
    dl.land(t, [q])
    t = dl.twin_from_text(t.render(), filename=ROSE.name)
    dl.record(t, [{"question": q["id"].split("/", 1)[1], "says": says}],
              session={"with": {"to": to, "who": "the poet" if to == "author" else "a reader of Blake"}}, at=AT)
    res = dl.settle(t, at="2026-11-18T13:00:00Z")
    return dl.twin_from_text(t.render(), filename=ROSE.name), res, q


def test_an_answer_to_breaks_writes_the_answerers_reading_of_the_lines():
    before = dl.open_twin(ROSE).ledger
    lines = [d["id"] for d in before.items if str(d.get("id", "")).startswith("C:line/")]
    out, res, q = _answered("breaks", "Each line breaks on the word the rose must hear.")
    wrote = res.settled[0][1]
    assert len(wrote) == 1 and wrote[0].startswith("P:reading/")
    d = out.ledger.item(wrote[0])
    assert d["of"] == lines and d["stance"] == "hearsay"
    session = d["provenance"]["sources"][0]
    assert session.startswith("D:session/") and d["whose"] == {"by": "author", "session": session}
    assert [x["id"] for x in out.ledger.items if str(x.get("id", "")).startswith("C:line/")] == lines
    assert [p for p in out.lint().errors] == []


def test_an_answer_to_stanza_writes_a_reading_of_the_stanzas_and_says_whose():
    before = dl.open_twin(ROSE).ledger
    parts = [d["id"] for d in before.items if str(d.get("id", "")).startswith("C:part/")]
    out, res, _q = _answered("stanza", "Two quatrains: a warning and its cause.", to="expert")
    d = out.ledger.item(res.settled[0][1][0])
    assert d["type"] == "reading" and d["of"] == parts and d["whose"]["by"] == "expert"
    assert [x["id"] for x in out.ledger.items if str(x.get("id", "")).startswith("C:part/")] == parts
    assert [p for p in out.lint().errors] == []


def test_the_bank_says_breaks_and_stanza_write_a_reading():
    m = dl.open_twin(ROSE).ledger.manifest
    bank = next(b for b in m.banks() if b["name"] == "fabulap")
    got = {e["id"]: (e["about"], e.get("writes")) for e in bank["questions"] if e["id"] in ("breaks", "stanza")}
    assert got == {"breaks": ("C:line", "P:reading"), "stanza": ("C:part", "P:reading")}


# ---------------------------------------------------------------------------
# 4. 20.5's program is decompile-verse-quick
# ---------------------------------------------------------------------------

def test_the_one_call_program_is_named_decompile_verse_quick():
    c = thym.check_file(SHIPPED / "decompile-verse-quick.thym")
    assert not isinstance(c, Refusal), c
    assert [p.name for p in c.programs()] == ["decompile-verse-quick"]
    full = thym.check_file(SHIPPED / "decompile-verse.thym")
    assert not isinstance(full, Refusal), full
    assert "decompile-verse" not in [p.name for p in full.programs()]
    assert P.PROGRAM_FILE == "decompile-verse.thym"


def test_a_one_call_fabulap_under_either_name_is_rebuilt_in_steps_only_when_asked(tmp_path):
    poem = tmp_path / "nobody.txt"
    poem.write_text((FIX / "nobody.txt").read_text(encoding="utf-8"), encoding="utf-8")
    for name in ("decompile-verse", "decompile-verse-quick"):
        doc = {"oes": "fabula/1", "flavour": "fabulap", "nodes": [],
               "derived": {"runs": [{"program": name, "run": "2026-11-18-0000-abcd"}]}}
        (tmp_path / "nobody.txt.fabulap.cosm").write_text(mc.dump(doc), encoding="utf-8")
        state = P.build_state(tmp_path, poem)
        assert state["exists"] and not state["built"], name

