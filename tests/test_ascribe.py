"""Ascribe (enough/ascribe.py, defaults/cosm/manifests/ascribe.manifest.cosm): a person's holograph, checked.

The manifest in the registry, seventh; the sample holograph clean through the generic reader and through Ascribe's own
checks; each bad holograph reporting exactly the check it is for; the no-PII patterns on crafted strings, and silent
on the phrases people are meant to use; the own checks on crafted volumes; the dialectic's questions; the CLI's exit
codes. Everything reads tests/fixtures/ascribe/ or writes under tmp_path; nothing reads or writes ~/enough.
"""
from __future__ import annotations

import copy
import datetime
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from enough import ascribe as A
from enough import macrocosm as mc

REPO = Path(__file__).resolve().parents[1]
MANIFESTS = REPO / "defaults" / "cosm" / "manifests"
MANIFEST = MANIFESTS / "ascribe.manifest.cosm"
FIX = REPO / "tests" / "fixtures" / "ascribe"
SAMPLE = FIX / "sample-self"
BAD = FIX / "bad"
NODE_KINDS = {"A": "affinity", "B": "belief", "C": "concern", "E": "experience", "I": "interest", "O": "opinion",
              "Q": "quale", "S": "skill", "U": "understanding", "Y": "yearning"}
MODULE_NAMES = {"A": "Affinities", "B": "Beliefs", "C": "Concerns", "E": "Experiences", "I": "Interests",
                "O": "Opinions", "Q": "Qualia", "S": "Skills", "U": "Understandings", "Y": "Yearnings", "F": "Forms"}
PROV = {"mode": "manual", "sources": ["self"], "confidence": 1}


def _ascribe() -> mc.Manifest:
    return mc.default_registry().get("ascribe")


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------

def test_the_manifest_joins_the_registry_seventh():
    reg = mc.default_registry()
    assert list(reg.manifests) == ["comprise", "cosm", "canon", "fabula", "doc", "ascribe", "thym"]
    assert reg.get("ascribe") in reg.minicosms() and not reg.get("ascribe").core      # a MiniCOSM, never built in
    assert reg.problems == []
    m = reg.get("ascribe")
    assert (m.name, m.title, m.version, mc._decl_value(m)) == ("ascribe", "Ascribe", 1, "ascribe/1")
    # 0.5.4: `spec:` is the text's cosmoes.org home (bundled as docs/ASCRIBE.md), not a repository path.
    assert m.data["spec"] == "https://ascribe.cosmoes.org/"
    assert m.data["reference"] == ["enough/macrocosm.py", "enough/ascribe.py"]
    assert m.declaration["absent"] == "refuse" and m.volume["catalog"] == "holograph.cosm"


def test_the_manifest_carries_the_header_and_the_notice():
    text = MANIFEST.read_text(encoding="utf-8")
    head = text.split("\nmanifest:", 1)[0]
    assert head.startswith("# ") and all(line.startswith("#") or not line for line in head.splitlines())
    assert "# Copyright © 2026 Graham Smith. All rights reserved. See defaults/cosm/NOTICE.md." in head
    assert text.count("\nmanifest: minicosm/0\n") == 1
    assert "the canonical edition" in text.split("\nspec:", 1)[1].splitlines()[0]
    assert "later round" not in text and "0.5.0" not in text                   # no round language (0.5.4)


def test_ten_modules_of_one_kind_each_and_the_forms():
    m = _ascribe()
    assert m.modules() == list("ABCEIOQSUYF") + ["D"]                  # the core's dialectic, inherited
    assert {L: m.module(L)["name"] for L in m.modules() if L != "D"} == MODULE_NAMES
    assert len({name[0] for name in MODULE_NAMES.values()}) == 11            # every initial distinct
    assert list(m.kinds("D")) == ["question", "session"] and "D" not in m.data["modules"]
    for letter, kind in NODE_KINDS.items():
        assert list(m.kinds(letter)) == [kind]
        assert {"form", "of", "parts", "links"} <= set(m.refs(letter, kind))
        sub = m.module(letter)["subtitle"]
        assert isinstance(sub, str) and len(sub.split()) >= 3 and not sub.endswith(".")
    assert list(m.kinds("F")) == ["form", "polyform", "relation"]
    assert set(m.refs("F", "polyform")) == {"links", "forms", "links.from"}
    assert m.data["paths"]["segments"]["module"] == "[ABCEIOQSUYF]"      # the file, untouched
    assert m.grammar.seg["module"].pattern == "[ABCEIOQSUYFD]"            # the reader adds the core's D


def test_links_closed_lists_checks_and_renderers():
    m = _ascribe()
    assert m.link_rels is None                     # left out, so an author's own relation is not a closed-list error
    assert m._block("links")["starter"] == list(A.STARTER_RELS)
    assert m.closed_lists()["valence"] == ["for", "against", "mixed"]
    checks = m._block("checks")
    assert checks["severity"] == {"no-pii": "warning"}
    assert all(c in mc.CHECKS for c in m.checks())                         # the generic list only
    assert all(c in checks["own"] for c in A.ASCRIBE_CHECKS)
    assert [r["id"] for r in m.data["renderers"]] == ["self", "timeline", "graph", "text-tree"]
    assert {s["id"]: (s["kind"], s.get("diagram")) for s in m.lenses()} == {
        "self": ("mermaid", "mindmap"), "timeline": ("table", None), "graph": ("mermaid", "flowchart")}
    assert m.data["filter"]["marker"] == A.PRIVATE_MARKER and m.data["filter"]["status"].startswith("declared")
    assert "moves" not in m.data
    for key in ("public-projection", "extension"):
        text = " ".join(str(v) for v in m.data[key].values())
        assert "Thym projection of the holograph" in text and "no outsider's graph of a person exists" in text


def test_the_schema_has_no_place_for_personal_data():
    m = _ascribe()
    cat = m._block("catalog")
    assert "name" not in cat["keys"] and "handle" in cat["keys"] and cat["id"] == "ascribe/<hid>"
    fields = set(m.envelope["fields"]) | set(cat["keys"])
    for L in m.modules():
        for spec in m.kinds(L).values():
            fields |= set(spec.get("refs", [])) | set(spec.get("checked", []))
    words = ("email", "phone", "address", "birth", "born", "passport", "ssn", "employer", "surname", "first-name",
             "last-name", "person")
    assert [f for f in fields if any(w in f for w in words)] == []


def test_the_dialectic_asks_three_to_five_plain_questions_per_module():
    m = _ascribe()
    qs = m.data["dialectic"]["questions"]
    assert list(qs) == [L for L in m.modules() if L != "D"]
    for letter, questions in qs.items():
        assert 3 <= len(questions) <= 5, letter
        assert len(set(questions)) == len(questions)
        assert all(isinstance(q, str) and q[0].isupper() and q.endswith("?") for q in questions), letter
    for letter, kind in NODE_KINDS.items():                # no definitions: a module's questions never name its kind
        assert not any(kind in q.lower() for q in qs[letter]), letter
    assert "What do you wish you had time for?" in qs["Y"]
    assert "What did you once believe and no longer do?" in qs["B"]
    assert "Which sensation do you remember most exactly?" in qs["Q"]


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------

def test_the_sample_lints_clean_both_ways():
    vol = mc.load_volume(SAMPLE)
    assert vol.refused is None and vol.oes == "ascribe/1" and vol.catalog_file == "holograph.cosm"
    generic = mc.lint(vol)
    assert generic.problems() == [] and generic.not_run == []
    rep = A.lint_holograph(SAMPLE)
    assert rep.problems() == [], [str(p) for p in rep.problems()]
    assert rep.checks[-len(A.ASCRIBE_CHECKS):] == list(A.ASCRIBE_CHECKS)
    assert rep.pending == [("F:form/sea-glass", "feed", "not in FEED")]
    assert A.lint_holograph(SAMPLE / "holograph.cosm").problems() == []


def test_the_sample_holds_what_a_holograph_can():
    vol = mc.load_volume(SAMPLE)
    cat = vol.catalog
    assert cat["sample"] is True and "name" not in cat and cat["pseudonyms"] == ["Wren"]
    assert A.HANDLE_RE.match(cat["handle"]) and A.HID_RE.match(cat["id"].split("/", 1)[1])
    by = vol.by_module()
    counts = {L: sum(len(v) for v in kinds.values()) for L, kinds in by.items()}
    assert sum(1 for L in NODE_KINDS if 2 <= counts.get(L, 0) <= 3) >= 6
    for it in vol.items.values():
        assert it.file.split("/", 1)[0] == it.module
        prov = it.data["provenance"]
        assert prov["mode"] in ("dialectic", "manual") and 0 <= prov["confidence"] <= 1 and prov["sources"]
    forms = by["F"]["form"]
    assert [f.id for f in forms if (f.data.get("feed") or {}).get("origin") == "feed"] == ["F:form/sourdough"]
    assert [f.id for f in forms if "wiki" in f.data] == ["F:form/celestial-navigation"]
    assert [f.id for f in forms if mc.is_pending(f.data.get("feed"))] == ["F:form/sea-glass"]
    assert len(by["F"]["polyform"]) == 1 and len(by["F"]["relation"]) == 1
    rels = [ln["rel"] for it in vol.items.values() for ln in it.data.get("links", []) if isinstance(ln, dict)]
    assert "learned-in" in rels and set(rels) - {"learned-in"} <= set(A.STARTER_RELS)
    parent = vol.items["E:experience/harbour-years"]
    assert len(parent.data["parts"]) == 2 and all(vol.items[c].data["of"] == parent.id for c in parent.data["parts"])
    whens = [it.data["when"] for it in vol.items.values() if "when" in it.data]
    assert {type(w) for w in whens} == {datetime.date, int, str}            # a date, a year, an era word
    assert {it.data.get("valence") for it in vol.items.values()} >= {"for", "against", "mixed"}
    assert sum(1 for it in vol.items.values() if "strength" in it.data) >= 3


def test_the_lenses_draw_the_sample():
    vol = mc.load_volume(SAMPLE)
    assert mc.lenses(vol) == ["self", "graph", "map", "tree"]
    body, nodes = mc.to_mermaid(vol, "self")
    assert body.startswith("mindmap") and "A · Affinities" in body and "F · Forms" not in body
    body, _ = mc.to_mermaid(vol, "graph")
    assert body.startswith("flowchart") and "learned-in" in body
    with pytest.raises(ValueError, match="table"):
        mc.to_mermaid(vol, "timeline")
    assert "U · Understandings" in mc.to_text_tree(vol)


def test_a_volume_of_another_minicosm_gets_the_generic_report_alone():
    meadow = REPO / "tests" / "fixtures" / "cosm" / "holotypes" / "meadow"
    rep = A.lint_holograph(meadow)
    assert not set(A.ASCRIBE_CHECKS) & set(rep.checks)


# ---------------------------------------------------------------------------
# The bad holographs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, check, severity, count", [
    ("pii", "no-pii", "warning", 7),
    ("unanchored", "form-anchored", "error", 1),
    ("undeclared-relation", "relation-declared", "error", 1),
])
def test_each_bad_holograph_reports_exactly_its_check(name, check, severity, count):
    assert mc.lint(mc.load_volume(BAD / name)).problems() == []          # the generic reader sees nothing wrong
    rep = A.lint_holograph(BAD / name)
    assert [(p.check, p.severity) for p in rep.problems()] == [(check, severity)] * count
    assert rep.ok is (severity != "error")


def test_the_pii_holograph_trips_every_pattern_once():
    rep = A.lint_holograph(BAD / "pii")
    kinds = Counter(k for p in rep.warnings for k, what in A.PII_WHAT.items() if f"reads as {what}" in p.message)
    assert kinds == Counter(dict.fromkeys(A.PII_WHAT, 1))
    assert all(p.message.endswith(A.ADVICE) for p in rep.warnings)


# ---------------------------------------------------------------------------
# The no-PII patterns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind, text, found", [
    ("email", "write to wren.fenwhistle@example.org", "wren.fenwhistle@example.org"),
    ("phone", "ring +1 415 555 0142 after six", "+1 415 555 0142"),
    ("phone", "or (415) 555-0142", "(415) 555-0142"),
    ("phone", "or 415-555-0142", "415-555-0142"),
    ("phone", "or 020 7946 0958", "020 7946 0958"),
    ("phone", "or 07700 900123", "07700 900123"),
    ("id-number", "licence 000-12-3456", "000-12-3456"),
    ("id-number", "card 4000 0000 0000 0002", "4000 0000 0000 0002"),
    ("id-number", "account 12345678", "12345678"),
    ("street-address", "at 17 Quillfeather Lane", "17 Quillfeather Lane"),
    ("street-address", "au 12 rue des Lilas", "12 rue des Lilas"),
    ("street-address", "in der Lindenstraße 5", "Lindenstraße 5"),
    ("street-address", "PO Box 42", "PO Box 42"),
    ("birth-date", "born on 3 March 1990", "born on 3 March 1990"),
    ("birth-date", "dob 1990-03-03", "dob 1990-03-03"),
    ("birth-date", "my birthday is 3/3/1990", "birthday is 3/3/1990"),
    ("birth-date", "March 3, 1990, the day I was born", "March 3, 1990, the day I was born"),
])
def test_each_pattern_fires_on_a_crafted_string(kind, text, found):
    assert A.pii_findings(text) == [(kind, found)]


ROLE_PHRASES = [
    "a colleague from the first lab", "my oldest friend", "a retired harbour pilot", "the neighbour two doors down",
    "my sister's partner", "Grandmother's kitchen on a Sunday", "a teacher who let me read in class",
    "In 2014 a winter course", "between 2010 and 2014", "about 3 miles down the road", "took the 7:15 ferry",
    "version 0.4.3", "born in 1990", "On 2015-08-21 we crossed the bay", "pages 120-135 of the pilot book",
    "The Lake District in May, then New York City", "a 24-hour race at 10:30", "1,200 nautical miles",
]


@pytest.mark.parametrize("text", ROLE_PHRASES)
def test_role_phrases_read_as_nothing(text):
    assert A.pii_findings(text) == [] and A.name_bigrams(text) == []


def test_capitalised_pairs_read_as_names_unless_declared():
    assert A.name_bigrams("Walked the coast path with Odile Fenwhistle every spring.") == ["Odile Fenwhistle"]
    assert A.name_bigrams("Professor Quillon taught the class") == ["Professor Quillon"]
    assert A.name_bigrams("the friend I call Captain Wren") == ["Captain Wren"]
    assert A.name_bigrams("the friend I call Captain Wren", ["Wren"]) == []
    assert A.name_bigrams("the friend I call Captain Wren", ["Captain Wren"]) == []
    assert A.name_bigrams("NASA Ames") == []                                 # an acronym is not a name


# ---------------------------------------------------------------------------
# The own checks, on crafted volumes
# ---------------------------------------------------------------------------

def _holograph(tmp_path: Path, files: dict[str, str] | None = None, *, catalog: dict | None = None) -> Path:
    """The sample, copied, with files added or replaced (and the catalog rewritten when given)."""
    root = tmp_path / "h"
    shutil.copytree(SAMPLE, root)
    for rel, text in (files or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if catalog is not None:
        (root / "holograph.cosm").write_text(mc.dump(catalog), encoding="utf-8")
    return root


def _nodes(*nodes: dict) -> str:
    return mc.dump({"nodes": [copy.deepcopy(n) for n in nodes]})      # one copy each: no shared mapping


def _node(nid: str, **fields) -> dict:
    kind = nid.split(":", 1)[1].split("/", 1)[0]
    base = {"id": nid, "type": kind, "name": "a test node", "summary": "Made for a test.", "form": "F:form/sourdough",
            "provenance": PROV}
    base.update(fields)
    return {k: v for k, v in base.items() if v is not None}


def _found(root: Path, **kw) -> list[tuple]:
    return [(p.check, p.severity, p.item, p.field) for p in A.lint_holograph(root, **kw).problems()]


def _catalog(**changes) -> dict:
    cat = mc.yaml_load((SAMPLE / "holograph.cosm").read_text(encoding="utf-8"))
    cat.update(changes)
    return {k: v for k, v in cat.items() if v is not None}


@pytest.mark.parametrize("when, ok", [
    (datetime.date(2014, 6, 3), True), ("2014-06-03", True), (2014, True), ("2014", True), ("childhood", True),
    ("2010s", True), ("secondary-school", True), ({"pending": "which summer?"}, True),
    ("2014-06", False), ("June 2014", False), ("2014-02-30", False), ("Childhood", False), ("the 1990s", False),
    (14, False), (True, False), (datetime.datetime(2014, 6, 3, 10, 0), False),
])
def test_when_shape(tmp_path, when, ok):
    root = _holograph(tmp_path, {"A/extra.cosm": _nodes(_node("A:affinity/x", when=when))})
    assert _found(root) == ([] if ok else [("when-shape", "error", "A:affinity/x", "when")])


@pytest.mark.parametrize("strength, ok", [(1, True), (5, True), (0, False), (6, False), ("4", False), (2.5, False),
                                          (True, False)])
def test_strength_range(tmp_path, strength, ok):
    root = _holograph(tmp_path, {"A/extra.cosm": _nodes(_node("A:affinity/x", strength=strength))})
    assert _found(root) == ([] if ok else [("strength-range", "error", "A:affinity/x", "strength")])


def test_valence_is_the_generic_closed_list(tmp_path):
    root = _holograph(tmp_path, {"A/extra.cosm": _nodes(_node("A:affinity/x", valence="sideways"))})
    assert _found(root) == [("closed-list", "error", "A:affinity/x", "valence")]


@pytest.mark.parametrize("form, expect", [
    (None, [("form-anchored", "error")]),
    ("F:form/missing", [("ref-unresolved", "error"), ("form-anchored", "error")]),
    ("S:skill/noon-sight", [("form-anchored", "error")]),
    ("F:relation/learned-in", [("form-anchored", "error")]),
    (["F:form/sourdough"], [("form-anchored", "error")]),
    ({"pending": "which form is this about?"}, [("form-anchored", "note")]),
    ("F:polyform/slow-crafts", []),
])
def test_form_anchored(tmp_path, form, expect):
    root = _holograph(tmp_path, {"Q/extra.cosm": _nodes(_node("Q:quale/x", form=form))})
    assert [(c, s) for c, s, *_ in _found(root)] == expect


@pytest.mark.parametrize("links, expect", [
    ([{"rel": "learned-in", "to": "E:experience/harbour-years"}], []),
    ([{"rel": "F:relation/learned-in", "to": "E:experience/harbour-years"}], []),
    ([{"rel": "toward", "to": "Y:yearning/ocean-by-sextant"}, "E:experience/harbour-years"], []),
    ([{"rel": "learnt-in", "to": "E:experience/harbour-years"}], [("relation-declared", "links[0].rel")]),
    ([{"to": "E:experience/harbour-years", "rel": 3}], [("relation-declared", "links[0].rel")]),
])
def test_relation_declared(tmp_path, links, expect):
    root = _holograph(tmp_path, {"S/extra.cosm": _nodes(_node("S:skill/x", links=links))})
    assert [(c, f) for c, _, _, f in _found(root)] == expect


def test_a_declared_relation_may_not_repeat_a_starter_word(tmp_path):
    rel = {"id": "F:relation/about", "type": "relation", "name": "about", "summary": "Says what it is about.",
           "provenance": PROV}
    root = _holograph(tmp_path, {"F/more.cosm": _nodes(rel)})
    assert _found(root) == [("relation-declared", "error", "F:relation/about", "id")]


def test_a_node_lives_in_its_module_folder_or_the_catalog(tmp_path):
    root = _holograph(tmp_path, {"B/misplaced.cosm": _nodes(_node("A:affinity/x")),
                                 "loose.cosm": _nodes(_node("A:affinity/y"))},
                      catalog=_catalog(nodes=[_node("Y:yearning/z")]))
    assert _found(root) == [("id-module", "error", "A:affinity/x", None), ("id-module", "error", "A:affinity/y", None)]


@pytest.mark.parametrize("changes, field", [
    ({"id": "ascribe/not-a-hid"}, "id"),
    ({"id": "ascribe/AEJ6L5QRKA6C6BTARFIY2F7VNJ"}, "id"),
    ({"handle": "Salt And Crumb"}, "handle"),
    ({"handle": None}, "handle"),
    ({"pseudonyms": "Wren"}, "pseudonyms"),
])
def test_the_catalog_holds_a_hid_and_a_handle(tmp_path, changes, field):
    root = _holograph(tmp_path, catalog=_catalog(**changes))
    found = _found(root)
    assert ("catalog-key", "error", "", field) in found and {c for c, *_ in found} <= {"catalog-key", "no-pii"}


def test_no_pii_reads_the_catalog_comments_and_dated_births(tmp_path):
    root = _holograph(tmp_path, {
        "E/born.cosm": "# kept for later: reach me at someone@example.net\n"
                       + _nodes(_node("E:experience/born", name="The day I was born", when=datetime.date(1990, 3, 3))),
    }, catalog=_catalog(name="Somebody Invented"))
    found = A.lint_holograph(root).problems()
    assert sorted((p.check, p.severity, p.item, p.field or "", p.file) for p in found) == sorted([
        ("catalog-key", "note", "", "name", "holograph.cosm"),
        ("no-pii", "warning", "", "name", "holograph.cosm"),
        ("no-pii", "warning", "", "", "E/born.cosm"),
        ("no-pii", "warning", "E:experience/born", "when", "E/born.cosm"),
    ])
    assert any("line 1, a comment" in p.message for p in found)


def test_a_pseudonym_is_declared_in_the_catalog(tmp_path):
    root = _holograph(tmp_path, catalog=_catalog(pseudonyms=None))
    assert _found(root) == [("no-pii", "warning", "E:experience/first-night-crossing", "summary")]


def test_a_form_with_a_wiki_is_a_public_subject(tmp_path):
    named = "The sculptor Ada Quillon, whose work fills a gallery by the harbour."
    public = {"id": "F:form/ada-quillon", "type": "form", "name": "Ada Quillon", "summary": named,
              "wiki": "Ada Quillon", "provenance": PROV}
    private = {"id": "F:form/her-studio", "type": "form", "name": "her studio", "summary": named, "provenance": PROV}
    root = _holograph(tmp_path, {"F/more.cosm": _nodes(public, private)})
    assert _found(root) == [("no-pii", "warning", "F:form/her-studio", "summary")]


def test_no_pii_is_never_an_error(tmp_path):
    folder = tmp_path / "manifests"
    shutil.copytree(MANIFESTS, folder)
    p = folder / "ascribe.manifest.cosm"
    p.write_text(p.read_text(encoding="utf-8").replace("severity: {no-pii: warning}", "severity: {no-pii: error}"),
                 encoding="utf-8")
    rep = A.lint_holograph(BAD / "pii", registry=mc.Registry([folder]))
    assert rep.ok and len(rep.warnings) == 7 and rep.errors == []


def test_the_private_marker_is_reported_never_applied(tmp_path):
    root = _holograph(tmp_path, {"A/drafts/old.cosm": _nodes(_node("A:affinity/old-draft")),
                                 f"A/drafts/{A.PRIVATE_MARKER}": ""})
    rep = A.lint_holograph(root)
    assert rep.ok and [(p.check, p.severity, p.file) for p in rep.problems()] == [
        ("private-marker", "note", f"A/drafts/{A.PRIVATE_MARKER}")]
    assert "A/drafts/old.cosm (1 node)" in rep.notes[0].message
    assert (root / "A/drafts/old.cosm").is_file() and "A:affinity/old-draft" in rep.volume.items
    (root / A.PRIVATE_MARKER).write_text("", encoding="utf-8")
    msgs = [p.message for p in A.lint_holograph(root).notes]
    assert any("the whole holograph, holograph.cosm included" in m for m in msgs)
    assert A.private_drops(root)[0] == (A.PRIVATE_MARKER, sorted(
        [p.name + "/" if p.is_dir() else p.name for p in root.iterdir() if p.name != A.PRIVATE_MARKER]))


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path, code", [(SAMPLE, 0), (BAD / "pii", 0), (BAD / "unanchored", 1),
                                        (BAD / "undeclared-relation", 1)])
def test_the_cli_exits_one_on_errors_only(path, code, capsys):
    assert A.main(["lint", str(path)]) == code
    out = capsys.readouterr().out.splitlines()
    assert out[-1].startswith("ascribe/1: ")
    assert ("errors" in out[-1]) and (len(out) > 1) is (path != SAMPLE)


def test_the_cli_runs_as_a_module_and_speaks_json(tmp_path):
    r = subprocess.run([sys.executable, "-m", "enough.ascribe", "lint", str(BAD / "pii"), "--json"], cwd=REPO,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True and body["errors"] == [] and len(body["warnings"]) == 7
    assert body["minicosm"] == "ascribe/1" and "no-pii" in body["checks"]
    assert A.main(["lint", str(tmp_path)]) == 1                         # no catalog: refused, an error
