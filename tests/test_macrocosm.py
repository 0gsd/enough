"""MacroCOSM OES v0.0.1: the reference reader (`enough/macrocosm.py`) and the four MiniCOSM manifests it ships.

Everything here reads fixtures under `tests/fixtures/cosm/`: the four public Comprise sample Holotypes and the COSM 0.2
example tree, copied from Comprise by `scripts/sync_cosm.py` (so the suite never needs comprise-dev), plus the Canon,
EMF and `bad/` volumes written for these tests. The Comprise item and open-question counts below were measured by
running Comprise's own loader and lint (`core.model.load_holotype`, `core.lint.lint_holotype`, comprise-dev fbe5b08)
read-only over the same fixtures; Comprise reports 0 load problems, 0 errors and 0 warnings on all four.
"""

from __future__ import annotations

import ast
import datetime
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from enough import macrocosm as M

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"
HOLOTYPES = FIX / "holotypes"
MANIFESTS = REPO / "defaults" / "cosm" / "manifests"

# Measured with Comprise's loader (items) and lint (open questions); see the module docstring.
COMPRISE_ITEMS = {"meadow": 36, "mozilla": 524, "wikimedia": 318, "khan-academy": 132}
COMPRISE_PENDING = {"meadow": 0, "mozilla": 82, "wikimedia": 66, "khan-academy": 56}

# Every fixture volume, by how load_volume is given it.
VOLUMES = {
    **{f"holotype:{n}": HOLOTYPES / n for n in COMPRISE_ITEMS},
    "cosm02:meadow": FIX / "cosm02" / "meadow",
    "canon:rust-book": FIX / "canon" / "rust-book",
    "canon:project": FIX / "canon" / "project" / "canon.cosm",
    "emf:notes": FIX / "emf" / "notes.md.cosm",
    "emf:standalone": FIX / "emf" / "standalone.cosm",
}


@pytest.fixture(scope="module")
def vols() -> dict[str, M.Volume]:
    return {k: M.load_volume(p) for k, p in VOLUMES.items()}


# ---------------------------------------------------------------------------
# The module stands alone
# ---------------------------------------------------------------------------

def test_module_imports_only_yaml_and_the_standard_library():
    tree = ast.parse((REPO / "enough" / "macrocosm.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "macrocosm.py must not use relative imports"
            names.add((node.module or "").split(".")[0])
    assert "enough" not in names
    assert names - {"yaml"} <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)


def test_module_never_reaches_for_the_home_folder():
    text = (REPO / "enough" / "macrocosm.py").read_text(encoding="utf-8")
    assert "Path.home" not in text and "expanduser" not in text and "~/" not in text.split('"""', 2)[2]
    assert M.DEFAULT_MANIFEST_DIR == MANIFESTS


# ---------------------------------------------------------------------------
# The file format
# ---------------------------------------------------------------------------

def test_loader_reads_yaml_1_2_booleans_only():
    d = M.yaml_load("a: true\nb: False\nc: TRUE\nd: yes\ne: no\nf: on\ng: off\non: [x]\n")
    assert d == {"a": True, "b": False, "c": True, "d": "yes", "e": "no", "f": "on", "g": "off", "on": ["x"]}


def test_loader_keeps_safeloader_scalars():
    d = M.yaml_load("since: 2019-03-01\nat: 2026-10-20T14:02:11Z\nn: 3\nx: 0.5\ncosm: 0.3\nz: null\n")
    assert d["since"] == datetime.date(2019, 3, 1)
    assert isinstance(d["at"], datetime.datetime)
    assert (d["n"], d["x"], d["cosm"], d["z"]) == (3, 0.5, 0.3, None)


def _write(tmp_path: Path, name: str, text: str, *, newline: str = "\n", bom: bool = False) -> Path:
    p = tmp_path / name
    data = text.replace("\n", newline)
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data.encode("utf-8"))
    return p


SMALL_EMF = """oes: emf/1
id: emf/small
name: small
nodes:
  - id: K:concept/x
    type: concept
    name: x
    summary: A concept, since 2019.
    since: 2019-03-01
    roles: {on: K:concept/x}
    provenance: {mode: manual, sources: [fixture], confidence: 1}
"""


def test_bom_and_crlf_read_the_same(tmp_path):
    plain = M.load_volume(_write(tmp_path, "plain.cosm", SMALL_EMF))
    odd = M.load_volume(_write(tmp_path, "odd.cosm", SMALL_EMF, newline="\r\n", bom=True))
    assert plain.problems == [] and odd.problems == []
    assert odd.catalog == plain.catalog
    item = odd.items["K:concept/x"]
    assert item.data["since"] == datetime.date(2019, 3, 1)
    assert item.data["roles"] == {"on": "K:concept/x"}        # `on:` is a key, never True
    assert M.lint(odd).ok


@pytest.mark.parametrize("snippet, words", [
    ("base: &p {mode: manual}\nother: *p\n", ["an anchor (&p)", "an alias (*p)"]),
    ("weird: !!str 5\n", ["a tag (tag:yaml.org,2002:str)"]),
    ("weird: !thing 5\n", ["a tag (!thing)"]),
    ("---\na: 1\n---\nb: 2\n", ["more than one YAML document"]),
    ("a: [1, 2\n", ["YAML error"]),
    ("since: 2019-02-30\n", ["YAML error"]),
])
def test_forbidden_constructs_are_problems_not_crashes(tmp_path, snippet, words):
    # In a module file the rest of the volume still loads; the file's own problems are load errors.
    root = tmp_path / "h"
    (root / "atoms" / "x" / "C").mkdir(parents=True)
    (root / "holotype.cosm").write_text("oes: comprise/1\nid: holotype/h\natoms: [atom/x]\n", encoding="utf-8")
    (root / "atoms" / "x" / "C" / "a.cosm").write_text(snippet, encoding="utf-8")
    v = M.load_volume(root)
    assert v.refused is None
    msgs = [str(p) for p in v.problems]
    for w in words:
        assert any(w in m for m in msgs), msgs
    assert all(p.check == "load" and p.file == "atoms/x/C/a.cosm" for p in v.problems)
    rep = M.lint(v)
    assert not rep.ok and {p.check for p in rep.errors} == {"load"}


def test_a_catalog_that_does_not_parse_is_refused(tmp_path):
    v = M.load_volume(_write(tmp_path, "canon.cosm", "oes: canon/1\nnodes: [\n"))
    assert isinstance(v.refused, M.Refusal) and not v.refused
    assert v.manifest is None and v.items == {}
    assert [p.check for p in M.lint(v).errors] == ["load"]


def test_dump_writes_the_subset(tmp_path):
    v = M.load_volume(VOLUMES["canon:rust-book"])
    shuffled = {k: v.catalog[k] for k in reversed(list(v.catalog))}
    text = M.dump(shuffled)
    assert text.startswith("oes: canon/1\n")
    assert "&" not in text and "*id" not in text
    assert M.yaml_load(text) == v.catalog
    again = M.dump({"oes": "emf/1", "a": "on", "b": "yes", "c": datetime.date(2026, 1, 2), "d": True})
    assert M.yaml_load(again) == {"oes": "emf/1", "a": "on", "b": "yes", "c": datetime.date(2026, 1, 2), "d": True}
    day = datetime.date(2026, 1, 2)
    assert "&" not in M.dump({"oes": "emf/1", "x": day, "y": day})     # equal scalars are written twice
    shared = {"mode": "manual"}
    with pytest.raises(ValueError):
        M.dump({"oes": "emf/1", "a": shared, "b": shared})
    assert M.dump({"manifest": "minicosm/0", "name": "x"}).startswith("manifest: minicosm/0\n")


def test_sniff_declaration_reads_only_the_head():
    assert M.sniff_declaration(FIX / "emf" / "notes.md.cosm") == "emf/1"
    assert M.sniff_declaration(FIX / "canon" / "project" / "canon.cosm") == "canon/1"
    assert M.sniff_declaration(FIX / "cosm02" / "meadow" / "firm.cosm") == "cosm 0.2"
    assert M.sniff_declaration(FIX / "emf" / "notes.md") is None
    assert M.sniff_declaration(FIX / "no-such-file.cosm") is None


# ---------------------------------------------------------------------------
# Manifests and the registry
# ---------------------------------------------------------------------------

def test_registry_loads_the_five_manifests_in_order():
    reg = M.default_registry()
    assert list(reg.manifests) == ["comprise", "cosm", "canon", "emf", "doc"]
    assert reg.problems == []
    assert [(m.name, m.version) for m in reg.manifests.values()] == [("comprise", 1), ("cosm", 0), ("canon", 1),
                                                                      ("emf", 1), ("doc", 1)]
    assert M.default_registry() is reg


@pytest.mark.parametrize("name", ["cosm", "canon", "emf", "doc"])
def test_our_manifests_carry_the_header_and_the_notice(name):
    text = (MANIFESTS / f"{name}.manifest.cosm").read_text(encoding="utf-8")
    head = text.split("\nmanifest:", 1)[0]
    assert head.startswith("# ") and all(line.startswith("#") or not line for line in head.splitlines())
    assert "# Copyright © 2026 Graham Smith. All rights reserved. See defaults/cosm/NOTICE.md." in head
    assert text.count("\nmanifest: minicosm/0\n") == 1


def test_the_comprise_manifest_is_the_synced_copy():
    synced = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
    rel = "defaults/cosm/manifests/comprise.manifest.cosm"
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == synced["files"][rel]


def test_manifest_helpers():
    reg = M.default_registry()
    comprise, emf, canon = reg.get("comprise"), reg.get("emf"), reg.get("canon")
    assert comprise.modules() == list("COMPRISE")
    assert "bond" in comprise.kinds("C") and comprise.refs("C", "bond")[:6] == ["owner", "at", "attributed-to",
                                                                                "counterparty", "shared-with", "links"]
    assert comprise.refs("I", "mapping")[-1] == "exclusions.sku"
    assert comprise.required_fields() == ["id", "type", "name", "summary", "provenance"]
    assert comprise.required_fields("P") == ["id", "type", "name", "summary", "owner"]
    assert comprise.closed_lists()["status"] == ["active", "dormant", "planned", "retired"]
    assert comprise.lenses() == []
    assert emf.required_fields("P", "claim")[-1] == "stance"
    assert emf.refs("P", "claim") == ["links", "roles.*"]
    assert emf.closed_lists()["stance"] == ["axiom", "observed", "deduced", "opinion", "assumed", "hearsay"]
    assert "contradicts" in emf.closed_lists()["links.rel"]
    assert [lens["id"] for lens in emf.lenses()] == ["claims", "map"]
    assert canon.single_file and canon.catalog_names == ["canon.cosm"]
    assert emf.matches_catalog("notes.md.cosm") and not canon.matches_catalog("notes.md.cosm")


def test_load_manifest_refuses_what_is_not_one(tmp_path):
    assert isinstance(M.load_manifest(tmp_path / "missing.manifest.cosm"), M.Refusal)
    bad = _write(tmp_path, "x.manifest.cosm", "manifest: minicosm/9\nname: x\nversion: 1\n")
    assert "minicosm/0" in str(M.load_manifest(bad))
    bad = _write(tmp_path, "y.manifest.cosm", "manifest: minicosm/0\nname: Y Z\nversion: 1\n")
    assert isinstance(M.load_manifest(bad), M.Refusal)
    reg = M.Registry([tmp_path, MANIFESTS])
    assert len(reg.problems) == 2 and list(reg.manifests) == ["comprise", "cosm", "canon", "emf", "doc"]


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("catalog, filename, expect", [
    ({}, None, ("comprise", 1, "absent")),
    ({}, "holotype.cosm", ("comprise", 1, "absent")),
    ({"comprise": 0.1}, "holotype.cosm", ("comprise", 1, "legacy")),
    ({"oes": "comprise/1", "comprise": 0.1}, "holotype.cosm", ("comprise", 1, "oes")),
    ({"comprise": 0.1, "oes": "comprise/1"}, None, ("comprise", 1, "oes")),
    ({"cosm": 0.2}, "firm.cosm", ("cosm", 0, "legacy")),
    ({"cosm": 0.3}, "brand.cosm", ("cosm", 0, "legacy")),
    ({"opi": 0.1}, None, ("cosm", 0, "legacy")),
    ({"oes": "cosm/0", "cosm": 0.3}, None, ("cosm", 0, "oes")),
    ({"oes": "canon/1"}, "canon.cosm", ("canon", 1, "oes")),
    ({"oes": "emf/1"}, "notes.md.cosm", ("emf", 1, "oes")),
])
def test_declarations_that_read(catalog, filename, expect):
    d = M.default_registry().identify(catalog, filename=filename)
    assert isinstance(d, M.Declaration), d
    assert (d.minicosm, d.major, d.how) == expect
    assert d.manifest.name == expect[0]


@pytest.mark.parametrize("catalog, filename, said", [
    ({"oes": "comprise/2"}, "holotype.cosm", "comprise/2"),
    ({"oes": "industry/1"}, "holotype.cosm", "industry/1"),
    ({"oes": ""}, "holotype.cosm", "(empty)"),
    ({"oes": None}, None, "(empty)"),
    ({"oes": 3}, None, "3"),
    ({"oes": "comprise"}, None, "comprise"),
    ({"oes": "comprise/01"}, None, "comprise/01"),          # one spelling: Comprise refuses it too
    ({"oes": " emf/1 "}, None, "emf/1"),
    ({"oes": "industry/1", "comprise": 0.1}, "holotype.cosm", "industry/1"),
    ({"oes": "cosm/1", "cosm": 0.3}, "brand.cosm", "cosm/1"),
    ({"oes": "canon/2"}, "canon.cosm", "canon/2"),
    ({"oes": "emf/0"}, "notes.md.cosm", "emf/0"),
    ({}, "canon.cosm", None),                     # canon: absent is refused
    ({}, "notes.md.cosm", None),                  # emf: absent is refused
    ({"cosm": 0.4}, "brand.cosm", None),          # an unknown COSM version is not a legacy match
])
def test_declarations_that_are_refused(catalog, filename, said):
    r = M.default_registry().identify(catalog, filename=filename)
    assert isinstance(r, M.Refusal) and not r
    assert r.said == said
    assert "nothing was loaded" in r.message
    if said:
        assert said in r.message


def test_a_refused_holotype_loads_nothing(tmp_path):
    root = tmp_path / "h"
    (root / "atoms" / "x" / "C").mkdir(parents=True)
    (root / "holotype.cosm").write_text("oes: industry/1\nid: holotype/h\nname: H\natoms: [atom/x]\nsecret: 1\n",
                                        encoding="utf-8")
    v = M.load_volume(root)
    assert v.refused is not None and v.manifest is None and v.items == {} and v.parts == {}
    assert v.catalog == {"id": "holotype/h", "name": "H", "oes": "industry/1"}
    rep = M.lint(v)
    assert [p.check for p in rep.errors] == ["load"] and "industry/1" in rep.errors[0].message
    assert rep.to_dict()["refused"] == str(v.refused)


def test_folders_without_a_catalog_are_refused(tmp_path):
    v = M.load_volume(FIX / "emf")                  # an EMF is loaded by its file; its folder has no catalog
    assert v.refused is not None and "no catalog" in str(v.refused)
    assert M.load_volume(tmp_path / "nope").refused is not None


# ---------------------------------------------------------------------------
# Parity with Comprise: the four public Holotypes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(COMPRISE_ITEMS))
def test_public_holotypes_load_like_comprise(vols, name):
    v = vols[f"holotype:{name}"]
    assert (v.minicosm, v.major) == ("comprise", 1)
    assert v.problems == []
    assert len(v.items) == COMPRISE_ITEMS[name]
    assert v.id == f"holotype/{name}" and v.database == name
    rep = M.lint(v)
    assert rep.errors == [] and rep.warnings == [] and rep.ok
    assert len(rep.pending) == COMPRISE_PENDING[name]
    assert "id-atom" in rep.not_run and "rule 14" in rep.not_run and "P strata" in rep.not_run
    assert not set(rep.not_run) & set(rep.checks)


def test_public_holotypes_total(vols):
    assert sum(len(vols[f"holotype:{n}"].items) for n in COMPRISE_ITEMS) == 1010


def test_holotype_items_keep_their_concern(vols):
    v = vols["holotype:mozilla"]
    assert len(v.parts) == 7
    both = [it for it in v.items.values() if it.id == "C:bond/foundation-controls-org"]
    assert sorted(it.part for it in both) == ["atom/mozilla-foundation", "atom/mozilla-org"]
    brand = v.items["atom/mozilla-foundation//P:mozilla-foundation"]
    assert (brand.module, brand.kind, brand.data["type"]) == ("P", "brand", "brand")
    assert v.parts["atom/mozilla-ai"].none["E"]                              # module: none, with its reason
    assert "E" in vols["holotype:meadow"].parts["atom/meadow"].readme


@pytest.mark.parametrize("key", list(VOLUMES))
def test_every_item_path_round_trips(vols, key):
    v = vols[key]
    assert v.items
    for it in v.items.values():
        path = M.item_path(v, it)
        assert path, it.key
        a = M.parse_path(v, path)
        assert isinstance(a, M.Address), (it.key, a)
        assert a.path == path and a.level == "item"
        assert a.id == it.id.split("//", 1)[-1]
        assert M.resolve_path(v, path) is it
        uri = M.qualified_uri(v, it)
        assert uri == f"oes:{v.minicosm}/{v.database}/{path}"
        assert M.resolve_path(v, uri) is it


# Comprise OES 1 section 6.7: every example in the table resolves on the fixtures.
SPEC_EXAMPLES = [
    ("mozilla", "mozilla-foundation", "concern", "atom/mozilla-foundation", None),
    ("mozilla", "mozilla-foundation/P", "module", None, 33),
    ("mozilla", "mozilla-foundation/P/offering", "kind", None, 8),
    ("mozilla", "mozilla-foundation/P/offering/creative-futures", "item", "P:offering/creative-futures", None),
    ("mozilla", "mozilla-foundation/P/brand/mozilla-foundation", "item", "P:mozilla-foundation", None),
    ("mozilla", "mzla/P/brand/thunderbird", "item", "P:thunderbird", None),
    ("mozilla", "mozilla-foundation/R/brand/mozilla-foundation", "item", "R:brand/mozilla-foundation", None),
    ("mozilla", "mozilla-foundation/C/charter/articles", "item", "C:charter/articles", None),
    ("mozilla", "mozilla-foundation/M/geography/operations", "item", "M:geography/operations", None),
    ("mozilla", "mozilla-corporation/S/codebase/firefox", "item", "S:codebase/firefox", None),
    ("mozilla", "mozilla-foundation/C/bond/foundation-controls-org", "item", "C:bond/foundation-controls-org", None),
    ("mozilla", "mozilla-org/C/bond/foundation-controls-org", "item", "C:bond/foundation-controls-org", None),
    ("mozilla", "mozilla-corporation/C/counterparty/google", "item", "C:counterparty/google", None),
    ("mozilla", "mozilla-org/C/ip/mozilla-trademarks", "item", "C:ip/mozilla-trademarks", None),
    ("mozilla", "mozilla-foundation/O/role/Executive-Director", "item", "O:role/Executive-Director", None),
    ("mozilla", "mozilla-foundation/P/offering/mozilla-festival#economics.price", "field",
     "P:offering/mozilla-festival", None),
    ("mozilla", "mozilla-ai/E", "module", None, 0),
    ("meadow", "meadow/P/brand/meadow", "item", "P:meadow", None),
    ("meadow", "meadow/P/offering/ledger#flow.outputs[0].to", "field", "P:offering/ledger", None),
    ("meadow", "meadow/O/role/Founder", "item", "O:role/Founder", None),
    ("meadow", "meadow/C/counterparty/banks", "item", "C:counterparty/banks", None),
    ("meadow", "meadow/I/sku/ledger-monthly", "item", "I:sku/ledger-monthly", None),
    ("meadow", "meadow/E", "module", None, 0),
]


@pytest.mark.parametrize("holotype, path, level, nid, count", SPEC_EXAMPLES)
def test_comprise_spec_path_examples_resolve(vols, holotype, path, level, nid, count):
    v = vols[f"holotype:{holotype}"]
    a = M.parse_path(v, path)
    assert isinstance(a, M.Address), a
    assert a.level == level and a.id == nid
    if level == "item":
        assert M.resolve_path(v, path).id == nid
    elif level == "field":
        it, value = M.resolve_path(v, path)
        assert it.id == nid and value is not None
    elif level == "concern":
        assert nid in v.parts and M.items_under(v, path)
    else:
        assert len(M.items_under(v, path)) == count


def test_qualified_forms(vols):
    moz, meadow = vols["holotype:mozilla"], vols["holotype:meadow"]
    assert M.resolve_path(moz, "oes:comprise/mozilla/mozilla-foundation/P/offering/creative-futures").id == \
        "P:offering/creative-futures"
    assert M.resolve_path(meadow, "oes:comprise/meadow/meadow/P/brand/meadow").id == "P:meadow"
    assert M.parse_path(moz, "oes:comprise/mozilla").level == "volume"
    assert isinstance(M.parse_path(moz, "oes:comprise/meadow/meadow/P"), M.Refusal)      # another database
    assert isinstance(M.parse_path(moz, "oes:canon/mozilla/x"), M.Refusal)               # another MiniCOSM
    assert M.qualified_uri(vols["canon:project"]) == "oes:canon/~field-notes"
    assert M.qualified_uri(vols["emf:notes"]).startswith("oes:emf/notes-md")


def test_vendor_paths_parse_as_a_whole(vols):
    v = vols["holotype:meadow"]
    a = M.parse_path(v, "vendor/stripe.com/payments")
    assert a.level == "vendor" and a.id == "vendor/stripe.com/payments"
    assert isinstance(M.parse_path(v, "vendor/stripe.com/payments#x"), M.Refusal)
    assert isinstance(M.parse_path(v, "vendor/stripe.com"), M.Refusal)


# ---------------------------------------------------------------------------
# Refused paths, from each manifest's own list
# ---------------------------------------------------------------------------

def _refused_examples(v: M.Volume, phrase: str) -> list[str]:
    """Paths the phrase refuses, built from one of the volume's own item paths."""
    base = M.item_path(v, next(iter(v.items.values())))
    segs = base.split("/")
    kind_at = v.manifest.grammar.levels.index("kind")
    p = phrase.lower()
    if p == "a leading slash":
        return ["/" + base]
    if p == "a trailing slash":
        return [base + "/", "/".join(segs[:-1]) + "/"]
    if p == "an empty segment":
        return [base.replace("/", "//", 1)]
    if p == ".":
        return ["/".join(segs[:1] + ["."] + segs[1:])]
    if p == "..":
        return ["/".join(segs[:1] + [".."] + segs[1:])]
    if p == "percent-encoding":
        return [base.replace("/", "%2F", 1)]
    if p == "a backslash":
        return [base.replace("/", "\\", 1)]
    if p == "whitespace":
        return [base + " x", base.replace("/", "/ ", 1), base + "\t"]
    if p == "a colon":
        return [base.replace("/", ":", 1)]
    if p == "non-ascii or control characters":
        return [base + "é", base + "\x07"]
    if p == "a segment ending in a dot":
        return [base + "."]
    if p == "a second '#'":
        return [base + "#a#b"]
    if p == "a kind the module does not declare":
        return ["/".join(segs[:kind_at] + ["no-such-kind"] + segs[kind_at + 1:])]
    if p.startswith("more than ") and p.endswith(" segments"):
        return [base + "/extra"]
    if p.startswith("a windows reserved name"):
        return ["/".join(segs[:-1] + [w]) for w in ("con", "CON", "con.txt", "NUL.tar.gz", "lpt1", "com0")]
    raise AssertionError(f"no example for the refused case {phrase!r}: add one here")


REFUSED_CASES = []
for _key in ("holotype:meadow", "cosm02:meadow", "canon:rust-book", "emf:notes"):
    _m = M.load_volume(VOLUMES[_key]).manifest
    REFUSED_CASES += [(_key, str(phrase)) for phrase in _m.data["paths"]["refused"]]


@pytest.mark.parametrize("key, phrase", REFUSED_CASES)
def test_refused_paths(vols, key, phrase):
    v = vols[key]
    for path in _refused_examples(v, phrase):
        r = M.parse_path(v, path)
        assert isinstance(r, M.Refusal), (phrase, path, r)
        assert r.message.startswith(f"refused {path!r}")
        assert M.resolve_path(v, path) is None


def test_refusal_counts_match_the_grammar(vols):
    assert "more than four segments" in vols["holotype:meadow"].manifest.data["paths"]["refused"]
    for key in ("cosm02:meadow", "canon:rust-book", "emf:notes"):
        assert "more than three segments" in vols[key].manifest.data["paths"]["refused"]


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def test_resolve_ref(vols):
    moz = vols["holotype:mozilla"]
    bond = moz.items["atom/mozilla-foundation//C:bond/foundation-controls-org"]
    owner_ref = bond.data.get("owner") or "O:role/Executive-Director"
    assert M.resolve_ref(moz, bond, owner_ref) is not None
    cites = [it for it in moz.items.values() if it.part != "atom/mozilla-org"]
    tm = M.resolve_ref(moz, cites[0], "atom/mozilla-org//C:ip/mozilla-trademarks")
    assert tm is not None and tm.part == "atom/mozilla-org"
    assert M.resolve_ref(moz, bond, "atom/mozilla-org") is None             # a concern is not an item
    assert M.resolve_ref(moz, bond, "none") is None
    assert M.resolve_ref(moz, bond, {"pending": "who?"}) is None
    notes = vols["emf:notes"]
    claim = notes.items["P:claim/mulch-raised-the-yield"]
    other = M.resolve_ref(notes, claim, claim.data["links"][0])
    assert other.id == "P:claim/spring-explains-the-yield"
    assert M.resolve_ref(notes, claim, "if it rains") is None


def test_walk_path_and_wildcards():
    data = {"roles": {"actor": "E:person/a", "condition": "if"}, "rows": [{"sku": "x"}, {"sku": ["y", "z"]}]}
    assert list(M.walk_path(data, "roles.*")) == ["E:person/a", "if"]
    assert list(M.walk_path(data, "rows.sku")) == ["x", "y", "z"]
    assert list(M.walk_path(data, "nothing.here")) == []


# ---------------------------------------------------------------------------
# The generic checks, one bad volume each
# ---------------------------------------------------------------------------

BAD = {
    "load": "load.cosm", "duplicate-id": "duplicate-id.cosm", "id-grammar": "id-grammar.cosm",
    "id-module": "id-module.cosm", "type": "type.cosm", "type-prefix": "type-prefix.cosm",
    "identity-min": "identity-min.cosm", "provenance": "provenance.cosm", "status": "status.cosm",
    "visibility": "visibility.cosm", "ref-grammar": "ref-grammar.cosm", "ref-unresolved": "ref-unresolved.cosm",
    "closed-list": "closed-list.cosm", "pending-shape": "pending-shape.cosm", "module-none": "module-none",
    "catalog-key": "catalog-key.cosm",
}


def test_every_implemented_check_has_a_bad_volume():
    assert set(BAD) == set(M.CHECKS)
    assert sorted(p.name for p in (FIX / "bad").iterdir() if not p.name.startswith(".")) == sorted(BAD.values())


@pytest.mark.parametrize("check", list(BAD))
def test_each_check_fires_on_its_bad_volume(check):
    v = M.load_volume(FIX / "bad" / BAD[check])
    assert v.refused is None, v.refused
    rep = M.lint(v)
    found = rep.errors + rep.warnings
    assert {p.check for p in found} == {check}, [str(p) for p in found]
    assert check in rep.checks
    severity = M.SEVERITY[check]
    assert all(p.severity == severity for p in found)
    assert rep.ok == (severity != "error")
    for p in found:
        assert str(p).startswith(f"{check} ")


def test_bad_input_never_raises(tmp_path):
    """Deterministic junk through every entry point: catalogs and items of the wrong shapes, values of every type
    where ids belong. Everything comes back as problems; paths that exist still round-trip."""
    import copy
    import random
    rnd = random.Random(7)
    values = [None, 1, -2.5, True, "", "x", "K:concept/x", "E:person/a", "atom/x", "P:x", {"pending": None},
              {"pending": "q"}, {"to": "K:concept/x"}, {"to": 5}, [], [None], {"a": {"b": [1, {"pending": 3}]}},
              ["K:concept/x", {"rel": "contradicts", "to": "nope"}], "2026-01-01", "none", "con", "a/b/c", ":"]
    keys = ["id", "type", "name", "summary", "provenance", "links", "parts", "parent", "stance", "roles", "status",
            "visibility", "pending", "defined-by", "agent", "of", "path", "emf", "twin", "on"]
    for i in range(60):
        nodes = []
        for _ in range(rnd.randint(0, 5)):
            d = {k: copy.deepcopy(rnd.choice(values)) for k in rnd.sample(keys, rnd.randint(0, 9))}
            d["id"] = rnd.choice(["K:concept/x", "P:claim/y", "V:file/z", "L:term/con", "bad id", "E:person/é", 3])
            d["type"] = rnd.choice(["concept", "claim", "file", "folder", "term", "nope", None])
            nodes.append(d)
        cat = {"oes": rnd.choice(["emf/1", "canon/1", "x/1", ""]), "id": copy.deepcopy(rnd.choice(values)),
               "nodes": nodes if i % 7 else copy.deepcopy(rnd.choice(values))}
        p = tmp_path / f"{i}.{rnd.choice(['notes.md', 'canon'])}.cosm"
        p.write_text(M.dump(cat), encoding="utf-8")
        v = M.load_volume(p)
        M.lint(v).to_dict()
        for it in v.items.values():
            path = M.item_path(v, it)
            assert not path or M.resolve_path(v, path) is it
            M.resolve_ref(v, it, it.data.get("parent"))
        for target in ("", "/a", "K/concept/x#a#b", None, 5, "oes:emf/x/K/concept/x"):
            assert M.resolve_path(v, target) is None or isinstance(M.resolve_path(v, target), (M.Item, tuple))
            M.items_under(v, target)
        for lens in M.lenses(v):
            M.to_mermaid(v, lens, max_nodes=2, clicks=True)
        M.to_text_tree(v)


def test_a_duplicate_is_a_load_problem_where_the_manifest_says_so(tmp_path):
    root = tmp_path / "h"
    (root / "atoms" / "x" / "C").mkdir(parents=True)
    (root / "holotype.cosm").write_text("oes: comprise/1\nid: holotype/h\natoms: [atom/x]\n", encoding="utf-8")
    node = ("  - {id: C:policy/p, type: policy, name: p, summary: s, "
            "provenance: {mode: manual, sources: [a], confidence: 1}}\n")
    (root / "atoms" / "x" / "C" / "a.cosm").write_text("nodes:\n" + node + node, encoding="utf-8")
    v = M.load_volume(root)
    assert len(v.items) == 1 and [p.check for p in v.problems] == ["duplicate-id"]
    rep = M.lint(v)
    assert [p.check for p in rep.errors] == ["load"] and "duplicate id C:policy/p" in rep.errors[0].message


def test_unknown_catalog_keys_are_notes(tmp_path):
    rep = M.lint(M.load_volume(_write(tmp_path, "x.cosm", SMALL_EMF + "colour: blue\n")))
    assert rep.ok and [(p.check, p.severity, p.field) for p in rep.notes] == [("catalog-key", "note", "colour")]


def test_duplicate_ids_keep_the_first():
    v = M.load_volume(FIX / "bad" / "duplicate-id.cosm")
    assert len(v.items) == 1 and v.items["K:concept/x"].data["summary"] == "The first x."


def test_problem_string_shape():
    p = M.Problem("ref-unresolved", "error", "K:concept/x", "x.cosm", "defined-by -> L:term/y does not exist")
    assert str(p) == "ref-unresolved K:concept/x (x.cosm): defined-by -> L:term/y does not exist"
    assert str(M.Problem("load", "error", "", "a.cosm", "YAML error")) == "load a.cosm: YAML error"


def test_soft_references_are_ids_or_text(tmp_path):
    text = SMALL_EMF.replace("roles: {on: K:concept/x}", "roles: {actor: E:person/nobody, condition: when it rains}")
    rep = M.lint(M.load_volume(_write(tmp_path, "soft.cosm", text.replace("K:concept/x\n    type: concept",
                                                                             "P:claim/x\n    type: claim\n    stance: assumed"))))
    assert [(p.check, p.field) for p in rep.errors] == [("ref-unresolved", "roles.*")]


def test_unknown_check_ids_are_not_run(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    text = (MANIFESTS / "emf.manifest.cosm").read_text(encoding="utf-8")
    (d / "emf.manifest.cosm").write_text(text.replace("closed-list, pending-shape, catalog-key]",
                                                      "closed-list, pending-shape, catalog-key, emf-pronouns]"),
                                         encoding="utf-8")
    v = M.load_volume(FIX / "emf" / "notes.md.cosm", M.Registry([d]))
    rep = M.lint(v)
    assert rep.ok and rep.not_run == ["emf-pronouns"] and "emf-pronouns" not in rep.checks


# ---------------------------------------------------------------------------
# Our own MiniCOSMs: the Canon, EMF and COSM examples load and lint clean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key, oes, n", [
    ("cosm02:meadow", "cosm/0", 17), ("canon:rust-book", "canon/1", 9), ("canon:project", "canon/1", 8),
    ("emf:notes", "emf/1", 21), ("emf:standalone", "emf/1", 3),
])
def test_our_examples_lint_clean(vols, key, oes, n):
    v = vols[key]
    assert v.oes == oes and len(v.items) == n and v.problems == []
    rep = M.lint(v)
    assert rep.problems() == [], [str(p) for p in rep.problems()]
    assert rep.not_run == []


def test_cosm02_reads_the_legacy_tree(vols):
    v = vols["cosm02:meadow"]
    assert v.declaration.how == "legacy" and v.declaration.key == "cosm" and v.declaration.said == "0.2"
    assert v.name == "Meadow Software" and v.id == "cosm/meadow"
    kinds = {it.id: it.kind for it in v.items.values()}
    assert kinds["meadow"] == "brand" and kinds["role/Founder"] == "role" and kinds["ext/banks"] == "external"
    assert M.item_path(v, v.items["ext/banks"]) == "P/external/banks"
    assert M.resolve_path(v, "P/brand/meadow").id == "meadow"


def test_emf_twin_shape(vols):
    v = vols["emf:notes"]
    assert v.catalog["source"]["path"] == "notes.md"
    src = (FIX / "emf" / "notes.md").read_bytes()
    assert v.catalog["source"]["sha256"] == hashlib.sha256(src).hexdigest()
    assert v.catalog["source"]["size"] == len(src)
    assert set(v.catalog["atem"]) == {"line", "focus", "push", "pull"}
    stances = {it.data["stance"] for it in v.items.values() if it.kind == "claim"}
    assert len(stances) >= 3
    assert any(link.get("rel") == "contradicts" for it in v.items.values() for link in it.data.get("links") or [])
    assert v.items["X:atem/1"].data["of"] in v.items
    rep = M.lint(v)
    assert ("L:term/leaf-mould", "feed", "not in FEED") in rep.pending
    assert ("E:org/parish-council", "node", v.items["E:org/parish-council"].data["pending"]) in rep.pending
    lines = (FIX / "emf" / "notes.md").read_text(encoding="utf-8").splitlines()
    for it in v.items.values():
        span = it.data.get("span", {}).get("lines")
        if span:
            first, _, last = str(span).partition("-")
            assert 1 <= int(first) <= int(last or first) <= len(lines) and lines[int(first) - 1].strip(), it.id


def test_project_catalog_carries_no_sizes_or_times(vols):
    v = vols["canon:project"]
    assert v.catalog["scope"] == "project" and v.database == "~field-notes"
    assert not {"created", "updated"} & set(v.catalog)
    for it in v.items.values():
        assert not {"size", "mtime"} & set(it.data), it.id
    assert v.items["V:folder/research--meadow-holotype"].data["holotype"] is True


# ---------------------------------------------------------------------------
# Lenses
# ---------------------------------------------------------------------------

_NODE_DEF = re.compile(r'^\s*([A-Za-z0-9_]+)(?:\(\(\(|\(\(|\[\[|\[/|\[\\|\(\[|\[\(|\{\{|\[|\(|\{|>)"([^"]*)"')


def _check_body(v: M.Volume, body: str, node_map: dict) -> None:
    lines = body.splitlines()
    assert lines[0].split()[0] in ("flowchart", "mindmap")
    assert not body.startswith("---")                                         # no frontmatter: the caller wraps it
    assert sum(1 for ln in lines if ln.strip().startswith("subgraph ")) == sum(1 for ln in lines if ln.strip() == "end")
    defs = [(mt.group(1), mt.group(2)) for ln in lines if (mt := _NODE_DEF.match(ln))]
    ids = [d[0] for d in defs]
    assert len(ids) == len(set(ids)), "node ids must be unique"
    for _, label in defs:
        assert label != "end" and len(label.replace("#quot;", '"').replace("#35;", "#")) <= M.LABEL_LIMIT + 8
        assert not M._EMOJI_RE.search(label)
    for nid, entry in node_map.items():
        assert nid in ids, nid
        assert entry["id"] is None or entry["id"] in v.items
        if entry["id"] is not None:
            assert entry["path"] == M.item_path(v, v.items[entry["id"]])
            assert entry["file"] == v.items[entry["id"]].file


LENS_CASES = [(k, lens) for k in VOLUMES for lens in M.lenses(M.load_volume(VOLUMES[k]))]


@pytest.mark.parametrize("key, lens", LENS_CASES)
def test_every_lens_draws(vols, key, lens):
    v = vols[key]
    body, node_map = M.to_mermaid(v, lens)
    _check_body(v, body, node_map)
    again, _ = M.to_mermaid(v, lens)
    assert again == body                                                      # stable across runs


def test_lens_lists(vols):
    assert M.lenses(vols["holotype:meadow"]) == ["map", "tree"]
    assert M.lenses(vols["cosm02:meadow"]) == ["tree", "map"]
    assert M.lenses(vols["canon:rust-book"]) == ["tree", "map"]
    assert M.lenses(vols["emf:notes"]) == ["claims", "map"]
    with pytest.raises(ValueError):
        M.to_mermaid(vols["emf:notes"], "no-such-lens")


def test_claims_lens_classes_by_stance(vols):
    body, node_map = M.to_mermaid(vols["emf:notes"], "claims")
    for stance in ("axiom", "observed", "deduced", "opinion", "assumed", "hearsay"):
        assert f"classDef c_stance_{stance} " in body
    assert '-.->|"contradicts"|' in body
    assert {e["id"].split(":")[0] for e in node_map.values()} <= {"E", "K", "P"}


def test_canon_tree_lens_maps_files(vols):
    v = vols["canon:rust-book"]
    body, node_map = M.to_mermaid(v, "tree")
    fs = {e["fs_path"] for e in node_map.values()}
    assert "ch02-guessing-game/src/main.rs" in fs and "foreword.pdf" in fs
    assert body.count(" --> ") == 5


def test_max_nodes_collapses_the_rest(vols):
    v = vols["holotype:mozilla"]
    body, node_map = M.to_mermaid(v, "map", max_nodes=50)
    _check_body(v, body, node_map)
    shown = [e for e in node_map.values() if e["id"] is not None]
    more = [e for e in node_map.values() if e["id"] is None]
    assert len(shown) == 50 and more
    assert len(shown) + sum(e["more"] for e in more) == len(v.items)
    assert all(re.search(rf'\["… {e["more"]} more"\]', body) for e in more)
    full, full_map = M.to_mermaid(v, "map", max_nodes=10_000)
    assert len(full_map) == len(v.items) and not re.search(r'more_\w+\["… \d+ more"\]', full)


def test_labels_follow_merirmaid_rules():
    assert M._mm_text("end") == "End"
    assert M._mm_text('say "hi" #1 <b>') == "say #quot;hi#quot; #35;1 #lt;b#gt;"
    assert M._mm_text("rocket 🚀 launch") == "rocket launch"
    long = M._mm_text("x" * 100)
    assert len(long) == M.LABEL_LIMIT and long.endswith("…")


def test_text_tree_shows_every_item(vols):
    for key in ("holotype:mozilla", "canon:rust-book", "emf:notes", "cosm02:meadow"):
        v = vols[key]
        tree = M.to_text_tree(v)
        assert tree.splitlines()[0].startswith(v.name)
        for it in v.items.values():
            assert f"[{it.id} · " in tree, it.key
    assert "(none: " in M.to_text_tree(vols["holotype:mozilla"])


# ---------------------------------------------------------------------------
# Speed and the command line
# ---------------------------------------------------------------------------

def test_mozilla_loads_fast():
    t = time.perf_counter()
    v = M.load_volume(HOLOTYPES / "mozilla")
    elapsed = time.perf_counter() - t
    assert len(v.items) == COMPRISE_ITEMS["mozilla"]
    assert elapsed < 1.5, f"mozilla took {elapsed:.2f}s"


def _cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "enough.macrocosm", *map(str, args)], cwd=REPO,
                          capture_output=True, text=True, timeout=60)


def test_cli_lint():
    r = _cli("lint", HOLOTYPES / "meadow")
    assert r.returncode == 0, r.stderr
    assert "comprise/1: 36 items, 0 errors, 0 warnings" in r.stdout
    r = _cli("lint", FIX / "bad" / "ref-unresolved.cosm")
    assert r.returncode == 1 and "ref-unresolved K:concept/x" in r.stdout
    r = _cli("lint", FIX / "emf" / "notes.md.cosm", "--json")
    body = json.loads(r.stdout)
    assert r.returncode == 0 and body["ok"] and body["minicosm"] == "emf/1" and body["pending"]


def test_cli_paths_tree_mermaid_identify():
    r = _cli("paths", HOLOTYPES / "meadow")
    assert r.returncode == 0 and "meadow/P/brand/meadow\tatom/meadow//P:meadow" in r.stdout
    r = _cli("paths", HOLOTYPES / "meadow", "meadow/P/offering/ledger#flow.outputs[0].to")
    assert r.returncode == 0 and r.stdout.startswith("meadow/P/offering/ledger\tP:offering/ledger")
    assert _cli("paths", HOLOTYPES / "meadow", "meadow/P/no-such").returncode == 1
    r = _cli("tree", FIX / "canon" / "rust-book")
    assert r.returncode == 0 and "└── " in r.stdout and "main.rs" in r.stdout
    r = _cli("mermaid", FIX / "emf" / "notes.md.cosm", "--lens", "claims")
    assert r.returncode == 0 and r.stdout.startswith("flowchart TB\n")
    assert _cli("mermaid", FIX / "emf" / "notes.md.cosm", "--lens", "nope").returncode == 2
    r = _cli("identify", FIX / "cosm02" / "meadow")
    assert r.returncode == 0 and r.stdout.startswith("cosm/0")
    r = _cli("identify", FIX / "bad" / "module-none" / "holotype.cosm", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["minicosm"] == "comprise"


def test_cli_refuses_plainly(tmp_path):
    p = _write(tmp_path, "x.cosm", "oes: industry/1\n")
    r = _cli("identify", p)
    assert r.returncode == 1 and "industry/1" in r.stdout
    r = _cli("lint", p)
    assert r.returncode == 1 and "industry/1" in r.stdout
    r = _cli("tree", p)
    assert r.returncode == 1 and "refused" in r.stderr
