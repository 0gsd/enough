"""DocOES (enough/docoes.py): a document enumerated into a doc volume, and compiled back.

The enumeration of a crafted document (sections, terms by each convention, mentions, examples, decisions, atems),
the real documents (the four OES specifications bundled from cosmoes.org — MacroCOSM OES, Thym, Ascribe, Comprise
OES — and the Help Center in six tellings), the reference generated from the manifests, the round trip byte for byte,
build-on-digest, the inventory and cross-volume references, DocOES's own checks, and the CLI. Every build goes
into a scratch docs root: the real `~/enough/docoes/` is never touched (conftest points ENOUGH_DOCS_ROOT into
tmp_path).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from enough import docoes as D
from enough import macrocosm as mc

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "docs" / "MACROCOSM_OES.md"


def _read(rel: str) -> str:
    return (REPO / rel).read_bytes().decode("utf-8")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> dict:
    """Every telling of every document, built once into a scratch docs root and loaded through the reader."""
    root = tmp_path_factory.mktemp("docs")
    vols = {}
    for doc in D.DOCUMENTS:
        for lang in D.tellings(doc):
            path = D.build(doc, lang, docs_root=root)
            assert path.parent == root and path.name == f"{doc}.{lang}.doc.cosm"
            vols[(doc, lang)] = mc.load_volume(path)
    return {"root": root, "vols": vols}


def _ids(vol: mc.Volume, kind: str | None = None) -> list[str]:
    return [k for k, it in vol.items.items() if kind is None or it.data.get("type") == kind]


# ---------------------------------------------------------------------------
# A crafted document
# ---------------------------------------------------------------------------

CRAFTED = """Before the title, a note.

# The Orchard handbook

<!-- atem: how the orchard is kept, season by season -->
The orchard has rows.

## Contents

A list of what follows, for the reader in a hurry.

## How to read this

| Here | In the files | Example |
|---|---|---|
| row | `R:row/<slug>` | `R:row/north` |
| graft | `graft:` | `graft: m9` |

## 1. Trees

A **tree** is one planted stock with its graft. See section 2.1, and sections 2 to 3 for the rest.

| Kind | What it is |
|---|---|
| **rootstock** | the lower part, chosen for vigour |

- **scion** — the upper part, chosen for fruit
- **Not a term.** A label, not a definition.

<!-- term: pruning -->
Cutting back in winter so the tree fruits in summer.

```text
## 9. Not a heading
A **tree** in code is not a use.
```

### 1.1 Planting

Every tree is planted in a row. `tree` in code is not a use, and **grafting** is not defined anywhere.

**Graft unions** heal in a season.

## 2. Seasons

A tree is pruned in winter (section 1.1).

### 2.1 Winter

Pruning only.

```cosm
oes: canon/1
id: canon/orchard
name: orchard
nodes: []
```

```yaml
oes: emf/1
```

## 3. Decisions in this version

1. **Rows run north to south.** The sun reaches both sides (section 1).
2. **A tree is defined once.** A second definition would split the word.

## 4. Empty

### 4.1 Nothing here

## Colophon

The end."""


@pytest.fixture(scope="module")
def crafted() -> dict:
    cat = D.enumerate_markdown(CRAFTED, doc_id="doc/orchard", source_path="orchard.md", version="1")
    return {"cat": cat, "by": {n["id"]: n for n in cat["nodes"]}}


def test_sections_numbers_slugs_root_and_front(crafted):
    by = crafted["by"]
    secs = [n["id"] for n in crafted["cat"]["nodes"] if n["type"] == "section"]
    assert secs == ["S:section/front", "S:section/root", "S:section/contents", "S:section/how-to-read-this",
                    "S:section/1", "S:section/1.1", "S:section/2", "S:section/2.1", "S:section/3", "S:section/4",
                    "S:section/4.1", "S:section/colophon"]
    assert "S:section/9" not in by                                   # a heading inside a fence is not one
    assert by["S:section/front"]["body"] == "Before the title, a note.\n\n" and "heading" not in by["S:section/front"]
    assert by["S:section/root"]["heading"] == "# The Orchard handbook" and by["S:section/root"]["level"] == 1
    assert by["S:section/1"]["number"] == "1" and by["S:section/1"]["name"] == "Trees"
    assert by["S:section/1"]["parent"] == "S:section/root" and by["S:section/1.1"]["parent"] == "S:section/1"
    assert by["S:section/1"]["parts"] == ["S:section/1.1"]
    assert by["S:section/1.1"]["lines"] == "38-43" and by["S:section/1.1"]["anchor"] == "sec-1-1"
    assert by["S:section/1"]["lines"] == "19-37"                     # the fenced "## 9." stays in its body
    assert by["S:section/how-to-read-this"]["anchor"] == "how-to-read-this"
    orders = [by[s]["order"] for s in secs]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)
    assert by["S:section/1.1"]["provenance"] == {"mode": "derived", "sources": ["orchard.md#L38-L43"],
                                                 "confidence": 1, "state": "known"}


def test_terms_by_each_convention(crafted):
    by = crafted["by"]
    terms = {n["id"]: n for n in crafted["cat"]["nodes"] if n["type"] == "term"}
    assert {t: n["convention"] for t, n in terms.items()} == {
        "T:term/row": "glossary", "T:term/graft": "glossary", "T:term/tree": "sentence",
        "T:term/rootstock": "table", "T:term/scion": "bullet", "T:term/pruning": "marker"}
    assert terms["T:term/tree"]["defined_in"] == "S:section/1"
    assert terms["T:term/tree"]["atem"] == "one planted stock with its graft"
    assert terms["T:term/tree"]["summary"] == "A tree is one planted stock with its graft."
    assert terms["T:term/rootstock"]["atem"] == "the lower part, chosen for vigour"
    assert terms["T:term/scion"]["atem"] == "the upper part, chosen for fruit"
    assert terms["T:term/pruning"]["atem"] == "Cutting back in winter so the tree fruits in summer"
    assert terms["T:term/row"]["in_the_files"] == "R:row/<slug>" and terms["T:term/row"]["example"] == "R:row/north"
    assert "T:term/not-a-term" not in by
    assert terms["T:term/scion"]["lines"] == "27"


def test_mentions_sections_ranges_and_terms_outside_code(crafted):
    by = crafted["by"]
    # "sections 2 to 3" is a range; "graft" is a plain use of the glossary's term; "tree" is defined here
    assert by["S:section/1"]["mentions"] == ["S:section/2.1", "S:section/2", "S:section/3", "T:term/graft"]
    assert by["S:section/1.1"]["mentions"] == ["T:term/tree", "T:term/row", "T:term/graft"]   # not the code span
    assert by["S:section/2"]["mentions"] == ["S:section/1.1", "T:term/tree"]
    assert by["S:section/2.1"]["mentions"] == ["T:term/pruning"]
    assert by["S:section/root"]["mentions"] == ["T:term/row"]                                # a plural counts


def test_examples_and_decisions(crafted):
    by = crafted["by"]
    ex = by["S:example/1"]
    assert ex["in"] == "S:section/2.1" and ex["declaration"] == "canon/1"
    assert ex["body"] == "oes: canon/1\nid: canon/orchard\nname: orchard\nnodes: []\n"
    assert ex["name"] == "example 1: orchard"
    assert "S:example/2" not in by                                       # a yaml block is not an example
    assert [n["id"] for n in crafted["cat"]["nodes"] if n["type"] == "decision"] == ["S:decision/1", "S:decision/2"]
    d = by["S:decision/1"]
    assert d["name"] == "Rows run north to south" and d["atem"] == "Rows run north to south"
    assert d["about"] == ["S:section/1", "T:term/row"] and d["in"] == "S:section/3"
    assert d["body"] == "1. **Rows run north to south.** The sun reaches both sides (section 1).\n"
    assert by["S:decision/2"]["about"] == ["T:term/tree"]


def test_atem_marker_first_sentence_and_fallbacks(crafted):
    by = crafted["by"]
    assert by["S:section/root"]["atem"] == "how the orchard is kept, season by season"      # the marker wins
    assert by["S:section/root"]["summary"] == "The orchard has rows."
    assert by["S:section/contents"]["atem"] == "A list of what follows, for the reader in a hurry"
    assert by["S:section/4"]["atem"] == "Empty: Nothing here"                              # no prose: its parts
    assert by["S:section/4.1"]["atem"] == "Nothing here, in Empty"                         # nor parts: its place
    for n in crafted["cat"]["nodes"]:
        assert D.atem_problems(n["atem"]) == [], (n["id"], n["atem"])


def test_the_atem_lint():
    assert D.atem_problems("one planted stock with its graft") == []
    assert D.atem_problems("A full stop.") == ["no final period: an atem is a phrase"]
    assert D.atem_problems("Orchard")[0].startswith("1 words")
    assert any("words: an atem has 2 to 15" in p for p in D.atem_problems(" ".join(["word"] * 16)))
    assert "no markup in an atem" in D.atem_problems("a **bold** claim")
    assert "no ids in an atem" in D.atem_problems("the row R:row/north and its trees")
    assert "one phrase, not sentences" in D.atem_problems("Rows run north. Trees stand in rows")
    assert D.atem_problems(None) == ["no atem: every item has one line"]
    assert D.atem_problems("インストール、ショートカット", "ja") == []
    assert any("characters" in p for p in D.atem_problems("あ" * 46, "ja"))
    # derived atems are cut by rule: at a clause break, else at fifteen words with an ellipsis
    assert D._atem_cut("The reader keeps a registry of the manifests it knows (section 13.6), in order: a, b.") == \
        "The reader keeps a registry of the manifests it knows"
    long = "An atem is the tightest fair, full, plain-English reduction of a text or of a passage of one."
    assert D._atem_cut(long) == "An atem is the tightest fair, full, plain-English reduction of a text…"


def test_the_crafted_document_round_trips_and_lints(crafted, tmp_path):
    assert D.compile_doc(crafted["cat"]) == CRAFTED
    cat = dict(crafted["cat"], tellings=["en"])
    path = tmp_path / "orchard.en.doc.cosm"
    path.write_text(D.dump(cat), encoding="utf-8")
    vol = mc.load_volume(path)
    assert vol.refused is None and vol.oes == "doc/1"
    assert D.compile_doc(vol) == CRAFTED
    rep = D.lint_doc(vol)
    assert rep.ok, [str(p) for p in rep.errors]
    found = Counter(p.check for p in rep.problems())
    assert found == {"empty-section": 1, "unlinked-mentions": 1}
    assert [p.item for p in rep.notes if p.check == "empty-section"] == ["S:section/4.1"]
    assert "**Graft unions**" in next(p.message for p in rep.notes if p.check == "unlinked-mentions")
    assert set(D.DOC_CHECKS) <= set(rep.checks) and not set(D.DOC_CHECKS) & set(rep.not_run)


def test_round_trip_keeps_odd_bytes():
    """CRLF line ends, a heading at the very end with no newline, trailing spaces, tabs and a BOM come back."""
    text = "﻿# T\r\n\r\nbody  \r\n\t- x\r\n## 1. A\nend\n### 1.1 B"
    cat = D.enumerate_markdown(text, doc_id="doc/odd", source_path="odd.md")
    assert D.compile_doc(cat) == text
    again = mc.yaml_load(D.dump(dict(cat, tellings=["en"])))
    assert D.compile_doc(again) == text


def test_doc_checks_catch_what_they_promise(crafted, tmp_path):
    nodes = [dict(n) for n in crafted["cat"]["nodes"]]
    by = {n["id"]: n for n in nodes}
    by["S:section/2"]["number"] = "1"                                    # numbered twice
    by["S:section/3"]["number"] = "5"                                    # skips 4
    by["T:term/tree"]["also_defined_in"] = ["S:section/2"]               # defined twice
    by["S:section/colophon"]["atem"] = "The end."                        # a final period
    by["S:section/contents"]["xrefs"] = ["orchard@1:section:9", "elsewhere@1:section:1", "not a reference"]
    cat = dict(crafted["cat"], nodes=nodes, tellings=["en"])
    path = tmp_path / "orchard.en.doc.cosm"
    path.write_text(D.dump(cat), encoding="utf-8")
    rep = D.lint_doc(mc.load_volume(path))
    errs = Counter(p.check for p in rep.errors)
    assert errs == {"numbering": 5, "atem-shape": 1, "xref-unresolved": 2}   # a twice, three out of order, 2.1 under 1
    assert any(p.check == "term-defined-once" for p in rep.warnings)
    assert any(p.check == "xref-unresolved" and "elsewhere" in p.message for p in rep.notes)


# ---------------------------------------------------------------------------
# The MacroCOSM spec, with Comprise's chapters
# ---------------------------------------------------------------------------

def test_the_spec_every_heading_is_a_section(built):
    vol = built["vols"][("macrocosm-oes", "en")]
    text = SPEC.read_text(encoding="utf-8")
    lines, fences = D._scan(text)
    heads = [ln for ln in lines if not ln.code and re.match(r"^#{1,6} ", ln.text)]
    main = [it for it in vol.items.values() if it.data.get("type") == "section" and "chapter" not in it.data]
    assert [it.data["heading"] for it in main] == [ln.text for ln in heads]
    assert sum(1 for ln in heads if re.match(r"^#{2,4} ", ln.text)) == \
        sum(1 for it in main if 2 <= it.data["level"] <= 4)
    assert vol.item("S:section/18.5").data["atem"] == \
        "one document taken apart into items and compiled back, byte for byte"
    assert vol.item("S:section/root").data["name"] == "MacroCOSM OES"
    assert {"S:section/contents", "S:section/how-to-read-this", "S:section/colophon"} <= set(vol.items)


def test_the_spec_examples_are_items_that_load(built, tmp_path):
    vol = built["vols"][("macrocosm-oes", "en")]
    blocks = re.findall(r"^```cosm\n(.*?)^```", SPEC.read_text(encoding="utf-8"), re.S | re.M)
    examples = [it for it in vol.items.values() if it.data.get("type") == "example"]
    assert len(examples) == len(blocks) == 8                    # §18.6 ascribe and §18.7 thym added theirs (0.5.0)
    assert [it.data["body"] for it in examples] == blocks
    # an `emf/1` example declares the fabula, the format its old spelling names (0.6)
    assert [it.data["declares"] for it in examples] == ["R:minicosm/cosm", "R:minicosm/canon", "R:minicosm/canon",
                                                        "R:minicosm/fabula", "R:minicosm/fabula", "R:minicosm/doc",
                                                        "R:minicosm/ascribe", "R:minicosm/thym"]
    assert vol.item("S:example/6").data["in"] == "S:section/18.5.5"
    for it in examples:
        decl = it.data["declaration"]
        name = {"canon/1": "canon.cosm", "emf/1": "x.md.cosm", "doc/1": "x.en.doc.cosm"}.get(decl, "brand.cosm")
        p = tmp_path / it.id.split("/")[-1] / name
        p.parent.mkdir()
        p.write_text(it.data["body"], encoding="utf-8")
        ex = mc.load_volume(p)
        assert ex.refused is None and mc.lint(ex).ok, it.id
    # the doc example is a doc volume that compiles to the handbook it shows
    doc_ex = mc.yaml_load(vol.item("S:example/6").data["body"])
    handbook = re.search(r"^```markdown\n(# The Meadow handbook\n.*?)^```", SPEC.read_text(encoding="utf-8"),
                         re.S | re.M).group(1)
    assert D.compile_doc(doc_ex) == handbook
    assert doc_ex["document"]["sha256"] == hashlib.sha256(handbook.encode("utf-8")).hexdigest()


def test_the_spec_references_all_resolve_and_it_lints(built):
    """Every "section N.M" names a section that exists (this is also the spec's numbering check), every § and
    P.N reference resolves into Comprise's chapters, and DocOES's own checks find no error."""
    vol = built["vols"][("macrocosm-oes", "en")]
    rep = D.lint_doc(vol)
    assert rep.ok, [str(p) for p in rep.errors]
    assert not [p for p in rep.problems() if p.check in ("ref-unresolved", "ref-grammar", "numbering")]
    mentions = [m for it in vol.items.values() for m in it.data.get("mentions") or []]
    assert sum(1 for m in mentions if m.startswith("S:section/")) > 150
    # 0.5.4: the appendix cites Comprise OES by bare number under a header that names it — no in-page link, no
    # xref: the chapters are gone, and §, README § and P.N in this text name other documents' sections, never its own.
    appendix = vol.item("S:section/appendix-the-mapping-to-comprise-oes").data
    assert "xrefs" not in appendix
    assert not [k for k in vol.items if k.startswith("S:chapter/") or k.startswith("S:section/comprise")]
    assert {p.check for p in rep.warnings} <= {"term-defined-once"}


def test_the_spec_terms_and_decisions(built):
    vol = built["vols"][("macrocosm-oes", "en")]
    t = vol.item("T:term/kind").data
    assert t["defined_in"] == "S:section/7.3" and t["atem"] == "a table" and t["in_the_files"].startswith("type")
    assert vol.item("T:term/part").data["convention"] == "glossary"
    assert vol.item("T:term/stance") is None or vol.item("T:term/stance").data["defined_in"].startswith("S:section/")
    assert "T:term/kind" in vol.item("S:section/7.4").data["mentions"]
    # 0.5.4: the decisions come from the "Changes" section — every item of every edition's list, numbered through
    # the section, each carrying its edition and date: 8 for 0.5.4, 3 for 0.0.2, the 27 old decisions under 0.0.1.
    decisions = [it for it in vol.items.values() if it.data.get("type") == "decision"]
    assert len(decisions) == 38 and decisions[-1].data["name"] == "A document is enumerated in its own grammar"
    assert Counter(d.data.get("edition") for d in decisions) == {"0.5.4": 8, "0.0.2": 3, "0.0.1": 27}
    first = decisions[0].data
    assert (first["id"], first["name"], first["edition"], first["dated"]) == \
        ("S:decision/1", "Names carry no number", "0.5.4", "2026-11-03")
    assert [d.data["number"] for d in decisions] == [str(i) for i in range(1, 39)]
    assert decisions[-1].data["in"] == decisions[0].data["in"] == "S:section/20"


def test_no_document_carries_chapters(built):
    """0.5.4: Comprise OES is a document of its own (it was two chapters of MacroCOSM OES before, synced from
    comprise-dev); no registered document has chapters, no volume a chapter item, no catalog a `chapters` list."""
    assert all(d.chapters == () for d in D.DOCUMENTS.values())
    for (slug, lang), vol in built["vols"].items():
        assert not [k for k in vol.items if k.startswith("S:chapter/")], (slug, lang)
        assert vol.catalog.get("chapters") in (None, []), (slug, lang)
    c = built["vols"][("comprise-oes", "en")]
    assert c.item("S:section/P.1") is not None and c.item("S:section/P.3").data["number"] == "P.3"
    # Comprise's P.N names its own chapter P (`own_p`); its § names other documents and is never linked.
    assert "S:section/P.3" in c.item("S:section/root").data.get("mentions", []) or any(
        "S:section/P.3" in (it.data.get("mentions") or []) for it in c.items.values())
    assert not [it for it in c.items.values() if it.data.get("xrefs")]


# ---------------------------------------------------------------------------
# The reference, generated from the manifests
# ---------------------------------------------------------------------------

def test_manifests_become_reference_items():
    items = D.enumerate_manifests(mc.default_registry(), tables=D.spec_tables(SPEC.read_text(encoding="utf-8")))
    by = {it["id"]: it for it in items}
    count = Counter((it["type"], it["id"].split("/", 1)[1].split(".", 1)[0]) for it in items
                    if it["type"] in ("module", "kind", "list"))
    assert [(count[("module", m)], count[("kind", m)])
            for m in ("comprise", "cosm", "canon", "fabula", "doc", "ascribe", "thym")] == \
        [(9, 73), (2, 11), (2, 5), (11, 42), (5, 14), (12, 15), (6, 15)]      # each with the core's D (0.6); thym's P gained check
    assert [count[("list", m)] for m in ("comprise", "cosm", "canon", "fabula")] == [4, 1, 4, 24]
    assert [it["id"] for it in items if it["type"] == "minicosm"] == \
        ["R:minicosm/comprise", "R:minicosm/cosm", "R:minicosm/canon", "R:minicosm/fabula", "R:minicosm/doc",
         "R:minicosm/ascribe", "R:minicosm/thym"]
    assert [it["id"] for it in items if it["type"] == "minicosm" and it["core"]] == \
        ["R:minicosm/cosm", "R:minicosm/canon", "R:minicosm/fabula", "R:minicosm/doc", "R:minicosm/thym"]
    assert by["R:minicosm/fabula"]["old"] == ["emf/1"] and "old" not in by["R:minicosm/canon"]
    assert by["R:module/cosm.D"]["provenance"]["sources"] == ["defaults/cosm/manifests/core.modules.cosm#modules.D"]
    checks = [it["id"].split("/", 1)[1] for it in items if it["type"] == "check"]
    assert checks == list(mc.CHECKS) + list(D.DOC_CHECKS)
    claim = by["R:kind/fabula.P.claim"]
    assert claim["refs"] == ["links", "roles.*"] and claim["required"][-1] == "stance"
    assert "R:list/fabula.stance" in claim["lists"] and claim["of"] == "R:module/fabula.P"
    assert claim["provenance"]["mode"] == "catalogue"
    assert claim["provenance"]["sources"] == ["defaults/cosm/manifests/fabula.manifest.cosm#modules.P.kinds.claim"]
    assert re.fullmatch(r"[0-9a-f]{16}", claim["provenance"]["hash"])
    assert by["R:module/fabula.P"]["atem"] == "What the work claims, how it can be read, and what it must do"
    assert by["R:check/ref-unresolved"]["atem"] == "a reference that names nothing in the volume"
    assert by["R:check/ref-unresolved"]["selected_by"] == [f"R:minicosm/{m}" for m in ("comprise", "cosm", "canon",
                                                                                         "fabula", "doc", "ascribe",
                                                                                         "thym")]
    assert by["R:check/module-none"]["selected_by"] == ["R:minicosm/comprise"]
    assert by["R:check/atem-shape"]["severity"] == "error" and by["R:check/atem-shape"]["atem"] == "an item with no atem"
    # the bundled text still says emf where the reader says fabula: its overlay still reaches the fabula's items
    assert by["R:list/fabula.stance"]["meanings"]["assumed"].startswith("taken for granted")
    assert by["R:lens/fabula.claims"]["atem"].startswith("entities, concepts and claims")
    assert by["R:lens/comprise.map"]["lens"]["generic"] is True
    assert by["R:kind/canon.V.folder"]["atem"] == "a folder of the volume"
    assert by["R:kind/comprise.E.broadcast"]["declared"]["status"] == "not built"


def test_lenses_the_reader_draws_and_the_ones_it_keeps(built):
    vol = built["vols"][("macrocosm-oes", "en")]
    assert [s["id"] for s in vol.manifest.lenses()] == ["manual", "map", "graph", "inventory"]
    assert mc.lenses(vol) == ["map", "graph", "tree"]
    with pytest.raises(ValueError, match="short, not a Mermaid drawing"):
        mc.to_mermaid(vol, "manual")
    body, node_map = mc.to_mermaid(vol, "graph", max_nodes=40)
    assert body.startswith("flowchart") and node_map


# ---------------------------------------------------------------------------
# The Help Center: six tellings, bubbles, Rosa
# ---------------------------------------------------------------------------

def test_the_help_center_tellings_share_one_set_of_ids(built):
    vols = {lang: built["vols"][("help-center", lang)] for lang in D.LANGS}
    en = set(vols["en"].items)
    for lang, vol in vols.items():
        assert set(vol.items) == en, lang
        assert vol.catalog["telling"] == {"lang": lang, "voice": "rosa"}
        assert vol.catalog["id"] == "doc/help-center" and vol.catalog["tellings"] == list(D.LANGS)
        assert vol.catalog["document"]["path"] == D.DOCUMENTS["help-center"].sources[lang]
    counts = Counter(it.data["type"] for it in vols["en"].items.values())
    lines, _ = D._scan(_read("docs/HELP_CENTER.md"))
    headings = sum(1 for ln in lines if not ln.code and re.match(r"^#{1,6} ", ln.text))
    assert counts["section"] == headings + 1                                    # and the front, before the title
    assert counts["bubble"] == len(re.findall(r"^## \S+\s*$", _read("enough/static/help-docs.md"), re.M))
    assert counts["term"] > 50
    fr = vols["fr"].item("S:section/12.3").data
    assert fr["name"] != vols["en"].item("S:section/12.3").data["name"] and fr["heading"].startswith("### 12.3 ")
    assert vols["fr"].item("S:section/front").data["atem"].startswith("Bonjour")


def test_the_help_center_lints_clean_in_every_telling(built):
    spec_rows = D.inventory(built["vols"][("macrocosm-oes", "en")])
    for lang in D.LANGS:
        vol = built["vols"][("help-center", lang)]
        rep = D.lint_doc(vol, inventories=spec_rows)
        assert rep.ok, (lang, [str(p) for p in rep.errors][:5])
        assert not [p for p in rep.notes if p.check == "xref-unresolved"], lang     # the spec's inventory was given
        twice = sorted(p.item for p in rep.warnings if p.check == "term-defined-once")
        assert twice == ["T:term/agent-md", "T:term/council", "T:term/input", "T:term/motivation-md"], lang
    fallback = [it.id for it in built["vols"][("help-center", "ja")].items.values() if it.data.get("fallback")]
    for tid in fallback:
        assert built["vols"][("help-center", "ja")].item(tid).data["atem"] == \
            built["vols"][("help-center", "en")].item(tid).data["atem"]


def test_bubbles():
    text = """<!-- the help content.
## not-a-bubble
-->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
your local, offline copy of english wikipedia. it is big.

### how
see section 11 for <strong>setup</strong>, and section 11.2.

### ideas
- save the articles a project leans on.

## docs
name: docs viewer

### what
the specification, read in section 18.4.
"""
    items = D.enumerate_bubbles(text, "en", source_path="help-docs.md")
    assert [it["id"] for it in items] == ["B:bubble/wikisink", "B:bubble/docs"]
    w = items[0]
    assert w["name"] == "wikisink" and w["path"] == "~/enough/wikisink/" and w["about"] == "wikisink"
    assert w["atem"] == "your local, offline copy of english wikipedia"
    assert w["how"] == "see section 11 for <strong>setup</strong>, and section 11.2."
    assert w["ideas"] == "- save the articles a project leans on."
    assert w["see"] == ["S:section/11", "S:section/11.2"]
    assert items[1]["xrefs"] == [f"macrocosm-oes@{D.document_version('macrocosm-oes')}:section:18.4"]
    assert "see" not in items[1]
    assert w["provenance"]["sources"] == ["help-docs.md#L5-L17"]


def test_the_real_bubbles(built):
    vol = built["vols"][("help-center", "en")]
    heads = re.findall(r"^## (\S+)\s*$", _read("enough/static/help-docs.md"), re.M)
    assert [k.split("/", 1)[1] for k in _ids(vol, "bubble")] == heads
    # 0.4.4: `cosmspec` merged into `docs`, the docs viewer's bubble, whose section numbers name the spec's.
    assert "B:bubble/cosmspec" not in vol.items
    spec_rows = D.inventory(built["vols"][("macrocosm-oes", "en")])
    for (doc, lang), v in built["vols"].items():
        if doc != "help-center":
            continue
        b = v.item("B:bubble/docs").data
        assert b["xrefs"] and all(x.startswith("macrocosm-oes@") for x in b["xrefs"]), lang
        assert "see" not in b, lang
        assert all(D.resolve_xref(x, spec_rows) for x in b["xrefs"]), lang
    assert set(D.BUBBLE_DOCUMENT) <= set(heads)


# ---------------------------------------------------------------------------
# Thym and Ascribe (0.5.0, lane X2): the two specifications written in MacroCOSM OES
# ---------------------------------------------------------------------------

def test_the_five_documents():
    """0.5.4: four specifications — the canonical editions published at cosmoes.org, bundled by
    scripts/sync_specs.py with their editions in docs/specs.json — and the help center. Names carry no number; a
    specification's version is its edition, read from specs.json (or a synced state.json), never the grammar's."""
    assert list(D.DOCUMENTS) == ["macrocosm-oes", "thym", "ascribe", "comprise-oes", "help-center"]
    editions = D.bundled_editions()
    assert set(editions) == {"macrocosm-oes", "thym", "ascribe", "comprise-oes"}
    for slug, name, path in (("macrocosm-oes", "MacroCOSM OES", "docs/MACROCOSM_OES.md"),
                             ("thym", "Thym", "docs/THYM.md"), ("ascribe", "Ascribe", "docs/ASCRIBE.md"),
                             ("comprise-oes", "Comprise OES", "docs/COMPRISE_OES.md")):
        d = D.DOCUMENTS[slug]
        assert (d.slug, d.name, d.sources, d.spec) == (slug, name, {"en": path}, True)
        assert (d.chapters, d.bubbles, d.voice, d.plain_mentions, d.version) == ((), {}, None, "all", "")
        assert D.tellings(slug) == ["en"]
        e = editions[slug]
        assert e["name"] == name and e["path"] == path and e["revised"] and e["host"].endswith("cosmoes.org")
        assert re.fullmatch(r"\d+\.\d+\.\d+", e["edition"])
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == e["sha256"]   # the bundled text, as synced
        assert D.document_version(slug) == e["edition"]
        info = D.spec_info(slug)
        assert (info["source"], info["path"], info["home"]) == ("bundled", REPO / path, f"https://{e['host']}/")
        assert D.spec_source(slug) == REPO / path
        assert not any(ch.isdigit() for ch in d.name)
    assert D.DOCUMENTS["macrocosm-oes"].reference and not D.DOCUMENTS["thym"].reference
    assert D.DOCUMENTS["macrocosm-oes"].xref == {"§": "", "README §": "", "P.": ""}
    assert D.DOCUMENTS["comprise-oes"].own_p and D.DOCUMENTS["comprise-oes"].xref == {"§": ""}
    # The grammar version is the reader's; a MiniCOSM's declaration version is not an edition either.
    assert D.document_version("macrocosm-oes") != "" and mc.MACROCOSM_VERSION == "0.5.4"
    assert str(mc.default_registry().get("thym").version) == "1"


def test_the_three_minicosm_specifications_enumerate(built):
    """The counts of the 0.5.4 editions (the decisions are the Changes sections' items: 7 + 18, 1 + 11, 2 + 19),
    the document's name and edition in the catalog with where it came from, no chapters and no reference, and
    every term defined in a section of its own document."""
    for slug, counts in (("thym", {"section": 83, "term": 12, "example": 1, "decision": 25}),
                         ("ascribe", {"section": 27, "term": 2, "example": 1, "decision": 12}),
                         ("comprise-oes", {"section": 99, "term": 15, "example": 0, "decision": 21})):
        vol = built["vols"][(slug, "en")]
        assert vol.refused is None and vol.id == f"doc/{slug}"
        got = Counter(it.data.get("type") for it in vol.items.values())
        assert {k: got[k] for k in counts} == counts, slug
        assert not [k for k in vol.items if k.startswith(("R:", "B:", "S:chapter/"))], slug
        assert vol.name == D.DOCUMENTS[slug].name
        doc = vol.catalog["document"]
        edition = D.document_version(slug)
        assert doc["version"] == edition and doc["path"] == D.DOCUMENTS[slug].sources["en"]
        assert doc["source"] == "bundled" and doc["revised"] and doc["home"].endswith(".cosmoes.org/")
        assert vol.catalog.get("chapters") in (None, [])
        for it in vol.items.values():
            if it.data.get("type") == "term":
                assert it.data["defined_in"] in vol.items, (slug, it.key)
        rows = D.inventory(vol)
        assert rows and all(r["inventory"] == slug and r["version"] == edition for r in rows)
        decisions = [it for it in vol.items.values() if it.data.get("type") == "decision"]
        assert decisions and all(d.data.get("edition") for d in decisions), slug
        assert decisions[0].data["edition"] == "0.5.4" and decisions[0].data["dated"] == "2026-11-03", slug


# ---------------------------------------------------------------------------
# The round trip, for every document and telling
# ---------------------------------------------------------------------------

def test_the_round_trip_is_byte_for_byte(built):
    for (doc, lang), vol in built["vols"].items():
        source = _read(D.DOCUMENTS[doc].sources[lang])
        assert D.compile_doc(vol) == source, (doc, lang)
        assert vol.catalog["document"]["sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError):
        D.compile_doc(built["vols"][("help-center", "en")], order="weight")


# ---------------------------------------------------------------------------
# Build on digest
# ---------------------------------------------------------------------------

def _sources(tmp: Path) -> Path:
    """A miniature install: the Help Center's English sources and the manifests."""
    root = tmp / "install"
    for rel in ("docs/HELP_CENTER.md", "enough/static/help-docs.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, root / rel)
    shutil.copytree(REPO / "defaults" / "cosm" / "manifests", root / "defaults" / "cosm" / "manifests")
    return root


def test_build_on_digest(tmp_path, monkeypatch):
    src, out = _sources(tmp_path), tmp_path / "out"
    first = D.ensure_built("help-center", "en", docs_root=out, sources=src)
    assert first["built"] == ["help-center.en"] and first["errors"] == []
    path = D.volume_path("help-center", "en", out)
    stamp = path.stat().st_mtime_ns
    assert D.recorded_digest(path) == D.digest("help-center", "en", sources=src)
    assert D.ensure_built("help-center", "en", docs_root=out, sources=src)["fresh"] == ["help-center.en"]
    assert path.stat().st_mtime_ns == stamp
    assert not list(out.glob(".*.tmp"))
    with open(src / "docs/HELP_CENTER.md", "a", encoding="utf-8") as fh:              # the document changes
        fh.write("\nOne more line.\n")
    assert D.ensure_built("help-center", "en", docs_root=out, sources=src)["built"] == ["help-center.en"]
    assert D.compile_doc(mc.load_volume(path, mc.Registry([src / "defaults/cosm/manifests"]))) == \
        (src / "docs/HELP_CENTER.md").read_text(encoding="utf-8")
    with open(src / "defaults/cosm/manifests/fabula.manifest.cosm", "a", encoding="utf-8") as fh:   # a manifest does
        fh.write("# a comment\n")
    assert D.ensure_built("help-center", "en", docs_root=out, sources=src)["built"] == ["help-center.en"]
    monkeypatch.setattr(D, "ENOUGH_VERSION", "9.9.9")                                    # enough's version does
    assert D.ensure_built("help-center", "en", docs_root=out, sources=src)["built"] == ["help-center.en"]
    assert mc.load_volume(path).catalog["built"]["by"] == "enough/9.9.9"
    assert D.ensure_built("help-center", "en", docs_root=out, sources=src)["fresh"] == ["help-center.en"]


def test_a_missing_source_is_reported_not_raised(tmp_path):
    src = _sources(tmp_path)
    r = D.ensure_built("help-center", "de", docs_root=tmp_path / "out", sources=src)
    assert r["built"] == [] and r["errors"] and "help-center.de" in r["errors"][0]


def test_the_docs_root_seam_is_scratch(tmp_path):
    """conftest points ENOUGH_DOCS_ROOT into tmp_path, so nothing in the suite can reach ~/enough/docoes/."""
    assert D.docs_root().is_relative_to(tmp_path)
    assert D.volume_path("help-center", "fr") == D.docs_root() / "help-center.fr.doc.cosm"


def test_status(tmp_path):
    src, out = _sources(tmp_path), tmp_path / "out"
    D.ensure_built("help-center", "en", docs_root=out, sources=src)
    rows = {(r["doc"], r["lang"]): r for r in D.status(docs_root=out, sources=src)["documents"]}
    assert rows[("help-center", "en")]["fresh"] is True
    assert rows[("help-center", "fr")]["exists"] is False and rows[("macrocosm-oes", "en")]["fresh"] is False
    for slug in ("thym", "ascribe", "comprise-oes"):
        assert rows[(slug, "en")]["exists"] is False                                   # no sources here
    assert [r for r in rows if r[0] in ("thym", "ascribe", "comprise-oes")] == \
        [("thym", "en"), ("ascribe", "en"), ("comprise-oes", "en")]


# ---------------------------------------------------------------------------
# Stale provenance
# ---------------------------------------------------------------------------

def test_stale_provenance_hash(built, tmp_path):
    vol = built["vols"][("macrocosm-oes", "en")]
    root = tmp_path / "install"
    shutil.copytree(REPO / "defaults" / "cosm", root / "defaults" / "cosm")
    (root / "docs").mkdir()
    shutil.copyfile(SPEC, root / "docs" / "MACROCOSM_OES.md")
    assert not [p for p in D.lint_doc(vol, sources=root).problems() if p.check == "stale-provenance-hash"]
    m = root / "defaults/cosm/manifests/fabula.manifest.cosm"
    m.write_text(m.read_text(encoding="utf-8").replace("subtitle: What the work claims, how it can be read, and what "
                                                       "it must do", "subtitle: What the work claims"),
                 encoding="utf-8")
    rep = D.lint_doc(vol, sources=root, registry=mc.Registry([root / "defaults/cosm/manifests"]))
    stale = {p.item for p in rep.warnings if p.check == "stale-provenance-hash"}
    assert "R:module/fabula.P" in stale
    assert "R:module/fabula.L" not in stale


# ---------------------------------------------------------------------------
# The inventory and cross-volume references
# ---------------------------------------------------------------------------

def test_inventory_and_cross_volume_references(built):
    vol = built["vols"][("macrocosm-oes", "en")]
    ver = D.document_version("macrocosm-oes")
    rows = D.inventory(vol)
    by_xref = {r["xref"]: r for r in rows}
    own = by_xref[f"macrocosm-oes@{ver}:section:18.5"]
    assert own == {"inventory": "macrocosm-oes", "xref": f"macrocosm-oes@{ver}:section:18.5",
                   "id": "S:section/18.5", "kind": "section", "version": ver, "anchor": "sec-18-5",
                   "atem": vol.item("S:section/18.5").data["atem"]}
    assert by_xref[f"macrocosm-oes@{ver}:kind:comprise.C.bond"]["id"] == "R:kind/comprise.C.bond"  # Comprise's manifest
    assert not [x for x in by_xref if x.startswith("comprise@")]      # Comprise's sections are its own document's now
    # Comprise OES's inventory is its own (0.5.4), under its edition; P.N sections are addressable like any other.
    cvol = built["vols"][("comprise-oes", "en")]
    cver = D.document_version("comprise-oes")
    crows = D.inventory(cvol)
    cby = {r["xref"]: r for r in crows}
    assert cby[f"comprise-oes@{cver}:section:2.5"]["id"] == "S:section/2.5"
    assert cby[f"comprise-oes@{cver}:section:P.3"]["id"] == "S:section/P.3"
    assert D.resolve_xref(f"comprise-oes@{cver}:section:P.3", crows)["id"] == "S:section/P.3"
    assert D.resolve_xref(f"comprise-oes@{cver}:section:99", crows) is None
    assert D.resolve_xref("comprise-oes@2:section:2.5", crows) is None            # the version is part of it
    assert D.resolve_xref("not a reference", crows) is None
    assert all(r["atem"] for r in rows) and all(r["atem"] for r in crows)


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------

def test_cli(tmp_path, capsys):
    out = str(tmp_path / "cli")
    assert D.main(["build", "help-center", "--lang", "fr", "--docs-root", out]) == 0
    assert "built" in capsys.readouterr().out
    assert D.main(["build", "help-center", "--lang", "fr", "--docs-root", out]) == 0
    assert capsys.readouterr().out.startswith("fresh ")
    assert D.main(["compile", "help-center", "--lang", "fr", "--docs-root", out]) == 0
    assert capsys.readouterr().out == _read("enough/static/i18n/fr/help-center.md")
    assert D.main(["inventory", "macrocosm-oes", "--docs-root", out]) == 0
    assert f"macrocosm-oes@{D.document_version('macrocosm-oes')}:section:18.5\tS:section/18.5\t" in \
        capsys.readouterr().out
    assert D.main(["inventory", "comprise-oes", "--docs-root", out]) == 0
    assert f"comprise-oes@{D.document_version('comprise-oes')}:section:2.5\tS:section/2.5\t" in \
        capsys.readouterr().out
    assert D.main(["compile", "comprise-oes", "--docs-root", out]) == 0
    assert capsys.readouterr().out == _read("docs/COMPRISE_OES.md")
    assert D.main(["lint", "macrocosm-oes", "--docs-root", out, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert D.main(["status", "--docs-root", out]) == 0
    assert "fresh   help-center.fr" in capsys.readouterr().out
    assert D.main(["build", "nothing", "--docs-root", out]) == 2
    assert D.main(["build", "macrocosm-oes", "--lang", "fr", "--docs-root", out]) == 2
    assert not (Path.home() / "enough" / "docs").exists() or Path.home().is_relative_to(tmp_path)
