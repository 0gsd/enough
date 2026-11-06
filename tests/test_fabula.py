"""The fabula round's reader (0.6): the core and its registry, the fabula's manifest and its old spelling, the core's
module D, the tree digest, and the fabula's own checks (enough/fabula.py).

What is held here: the thirteen things the reader learned (docs/fabula-pins-schema.md part 8; MacroCOSM OES 5, 6.2,
9.3, 11.3, 12, 13, 18.1, 18.4, 18.6, 20), each with a passing and a failing case; the shipped manifests; each of the
fabula's own checks on a clean and a broken volume; the three worked examples of the schema file (a fabulan, a
fabulap, a fabulac and its program, byte for byte as the schema's appendices B to F give them) through the real
reader; every `oes: emf/1` file the repository keeps, read as a fabula by its old spelling; and every `cosm` block of
the 0.6 draft of MacroCOSM OES (a copy kept as tests/fixtures/fabula/macrocosm-oes-0.6-draft.md until the synced
copies are updated).
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pytest

from enough import fabula
from enough import macrocosm as M

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures"
FAB = FIX / "fabula"
MANIFESTS = REPO / "defaults" / "cosm" / "manifests"
DRAFT = FAB / "macrocosm-oes-0.6-draft.md"
CLOSE = FAB / "guides" / "close.md.fabulan.cosm"
ROSE = FAB / "poems" / "the-sick-rose.txt.fabulap.cosm"
TALLY = FAB / "tally.fabulac.cosm"
TALLY_TREE = "0f26fb8759b9780f4131d6f6fbc541089d441051baaf1d88fa52023b30cadaea"


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _vol(text: str, name: str = "x.fabulan.cosm", registry: M.Registry | None = None) -> M.Volume:
    return M.load_volume_text(text, filename=name, registry=registry)


def _checks(rep: M.Report, check: str) -> list[M.Problem]:
    return [p for p in rep.problems() if p.check == check]


# ---------------------------------------------------------------------------
# 1. core: true, and the registry's two lists (spec 13.3, 13.6)
# ---------------------------------------------------------------------------

def test_the_registry_knows_five_built_ins_and_two_minicosms():
    reg = M.default_registry()
    assert [m.name for m in reg.built_ins()] == ["cosm", "canon", "fabula", "doc", "thym"]
    assert [m.name for m in reg.minicosms()] == ["comprise", "ascribe"]
    assert all(m.core for m in reg.built_ins()) and not any(m.core for m in reg.minicosms())
    assert "core" not in reg.get("comprise").data and "core" not in reg.get("ascribe").data


def test_core_is_true_only_when_it_says_true(tmp_path):
    for i, said in enumerate(("core: 'true'\n", "core: yes\n", "core: false\n", "")):
        d = tmp_path / str(i)
        d.mkdir()
        (d / "z.manifest.cosm").write_text(f"manifest: minicosm/0\nname: z\nversion: 1\n{said}", encoding="utf-8")
        reg = M.Registry([d])
        assert reg.minicosms() == [reg.get("z")] and reg.built_ins() == []


# ---------------------------------------------------------------------------
# 2. declaration.old: `oes: emf/1` is a fabula, identified `old` (spec 5.2, 5.3, 5.4)
# ---------------------------------------------------------------------------

def test_an_old_spelling_is_read_as_its_format():
    reg = M.default_registry()
    d = reg.identify({"oes": "emf/1"}, filename="close.md.cosm")
    assert isinstance(d, M.Declaration)
    assert (d.minicosm, d.major, d.how, d.key, d.said, d.value) == ("fabula", 1, "old", "oes", "emf/1", "fabula/1")
    d = reg.identify({"oes": "fabula/1"}, filename="close.md.fabulan.cosm")
    assert (d.minicosm, d.how, d.said) == ("fabula", "oes", "fabula/1")
    assert reg.get("fabula").old == ["emf/1"] and reg.get("fabula").old_names == ["emf"]


def test_known_lists_each_format_with_its_old_spellings():
    assert M.default_registry().known() == ("comprise/1, cosm/0, canon/1, fabula/1 (also emf/1), doc/1, ascribe/1, "
                                            "thym/1")


@pytest.mark.parametrize("said", [" emf/1 ", "emf/2", "emf/01", "fabula/2", "fabulan/1", "emf"])
def test_an_old_spelling_is_spelled_exactly_or_refused(said):
    r = M.default_registry().identify({"oes": said}, filename="close.md.cosm")
    assert isinstance(r, M.Refusal) and "nothing was loaded" in r.message
    assert "fabula/1" in r.message


def test_an_old_twin_keeps_its_declaration_and_is_never_rewritten():
    text = _text(FIX / "cosm" / "emf" / "notes.md.cosm")
    v = _vol(text, "notes.md.cosm")
    assert v.oes == "fabula/1" and v.catalog["oes"] == "emf/1" and v.declaration.how == "old"
    assert M.dump(v.catalog).startswith("oes: emf/1\n")          # what a semantic rewrite would write back


def test_a_manifest_without_old_refuses_what_it_does_not_list(tmp_path):
    for p in MANIFESTS.glob("*.cosm"):
        if p.name != "fabula.manifest.cosm":
            (tmp_path / p.name).write_bytes(p.read_bytes())
    text = _text(MANIFESTS / "fabula.manifest.cosm").replace("  old: [emf/1]", "  old: []", 1)
    (tmp_path / "fabula.manifest.cosm").write_text(text, encoding="utf-8")
    r = M.Registry([tmp_path]).identify({"oes": "emf/1"})
    assert isinstance(r, M.Refusal) and "does not know the MiniCOSM 'emf'" in r.message


# ---------------------------------------------------------------------------
# 3. the registry order (spec 5.2, 13.6)
# ---------------------------------------------------------------------------

def test_registry_order_has_fabula_where_emf_was():
    assert M.REGISTRY_ORDER == ("comprise", "cosm", "canon", "fabula", "doc")
    assert list(M.default_registry().manifests) == ["comprise", "cosm", "canon", "fabula", "doc", "ascribe", "thym"]
    assert not (MANIFESTS / "emf.manifest.cosm").exists()


# ---------------------------------------------------------------------------
# 4. catalog.id-old, and the database name (spec 6.2)
# ---------------------------------------------------------------------------

def test_an_old_id_passes_catalog_key_and_gives_the_same_database_name():
    old = _vol(_text(FIX / "cosm" / "emf" / "notes.md.cosm"), "notes.md.cosm")
    assert old.id == "emf/notes-md" and old.database == "notes-md"
    assert not _checks(M.lint(old), "catalog-key")
    new = _vol(_text(CLOSE), "close.md.fabulan.cosm")
    assert new.id == "fabula/guides--close-md" and new.database == "guides--close-md"
    bad = _vol(_text(CLOSE).replace("id: fabula/guides--close-md", "id: fabulan/guides--close-md", 1))
    assert [p.message for p in _checks(M.lint(bad), "catalog-key")] == \
        ["id 'fabulan/guides--close-md' is not fabula/<slug>"]
    assert M.default_registry().get("fabula").catalog_id_forms() == ["fabula/<slug>", "emf/<slug>"]


# ---------------------------------------------------------------------------
# 5. URIs: `oes:emf/…` names what `oes:fabula/…` names; written as the latter (spec 11.3)
# ---------------------------------------------------------------------------

def test_uris_under_the_old_name_resolve_and_are_written_under_the_new():
    v = _vol(_text(FIX / "cosm" / "emf" / "notes.md.cosm"), "notes.md.cosm")
    it = next(i for i in v.items.values() if i.kind == "claim")
    uri = M.qualified_uri(v, it)
    assert uri.startswith("oes:fabula/notes-md/P/claim/")
    old = "oes:emf/" + uri[len("oes:fabula/"):]
    assert M.resolve_path(v, uri) is it and M.resolve_path(v, old) is it
    assert M.parse_path(v, "oes:emf/notes-md").level == "volume"
    assert isinstance(M.parse_path(v, "oes:canon/notes-md/P/claim/x"), M.Refusal)
    assert isinstance(M.parse_path(v, "oes:emf/other/" + uri.split("/", 2)[2]), M.Refusal)


# ---------------------------------------------------------------------------
# 6. the two checks the manifest drives: flavour and flavour-kind (spec 12.2, 18.4.8)
# ---------------------------------------------------------------------------

def test_flavour_absent_reads_fabulan_and_a_bad_one_is_named_once():
    no = _vol(_text(CLOSE).replace("flavour: fabulan\n", "", 1))
    assert M.lint(no).ok and fabula.flavour(no) == "fabulan"
    bad = _vol(_text(CLOSE).replace("flavour: fabulan\n", "flavour: fabulax\n", 1))
    rep = M.lint(bad)
    assert [str(p) for p in rep.errors] == \
        ["flavour x.fabulan.cosm: flavour 'fabulax' is not fabulan, fabulap or fabulac"]


def test_a_fabulap_relabelled_fabulan_fails_flavour_kind_on_every_verse_kind():
    v = _vol(_text(ROSE).replace("flavour: fabulap", "flavour: fabulan", 1))
    errs = _checks(M.lint(v), "flavour-kind")
    assert errs and all(p.severity == "error" for p in errs)
    assert "C:line/1: a line belongs to fabulap, not to a fabulan" in [f"{p.item}: {p.message}" for p in errs]
    assert {v.items[p.item].kind for p in errs} == {"line", "metre", "rhyme"}


def test_a_code_kind_in_a_fabulan_and_a_reading_in_a_fabulac_are_refused():
    v = _vol(_text(TALLY).replace("flavour: fabulac", "flavour: fabulan", 1))
    kinds = {v.items[p.item].kind for p in _checks(M.lint(v), "flavour-kind")}
    assert {"file", "component", "interface", "use", "requirement", "case"} <= kinds
    assert "claim" not in kinds and "maker" not in kinds
    v = _vol(_text(ROSE).replace("flavour: fabulap", "flavour: fabulac", 1))
    msgs = {p.message for p in _checks(M.lint(v), "flavour-kind")}
    assert "a reading belongs to fabulan or fabulap, not to a fabulac" in msgs


# ---------------------------------------------------------------------------
# 7. checks.own as a list: listed as not run by the generic reader (spec 12.3)
# ---------------------------------------------------------------------------

def test_own_checks_are_listed_not_run_and_prose_stays_prose():
    rep = M.lint(M.load_volume(CLOSE))
    assert rep.not_run == list(fabula.OWN_CHECKS)
    assert not set(fabula.OWN_CHECKS) & set(rep.checks)
    assert M.default_registry().get("ascribe").own_checks() == []          # Ascribe's own: a string, prose
    assert M.default_registry().get("fabula").own_checks() == list(fabula.OWN_CHECKS)
    full = fabula.lint(CLOSE)
    assert full.not_run == [] and set(fabula.OWN_CHECKS) <= set(full.checks)


def test_a_volume_with_dialectic_items_lists_the_cores_checks_not_run():
    assert set(M.CORE_CHECKS) <= set(M.lint(_vol(_text(CLOSE))).not_run)
    canon = _text(FIX / "cosm" / "canon" / "rust-book" / "canon.cosm")
    assert set(M.CORE_CHECKS).isdisjoint(M.lint(_vol(canon, "canon.cosm")).not_run)        # no D items: nothing owed
    q = "  - {id: D:session/s1, type: session, at: 2026-11-05T10:00:00Z, with: {to: owner, who: x}, through: person}\n"
    with_d = _vol(canon.replace("\nnodes:\n", "\nnodes:\n" + q, 1), "canon.cosm")
    rep = M.lint(with_d)
    assert rep.ok and rep.not_run == list(M.CORE_CHECKS)


# ---------------------------------------------------------------------------
# 8. a kind's own closed lists (spec 7.3, 18.6.2)
# ---------------------------------------------------------------------------

def test_a_kinds_closed_lists_apply_to_its_items_only():
    m = M.default_registry().get("fabula")
    assert m.kind_closed("D", "question") == {
        "why": ["missing", "unsure", "ambiguous", "intent", "conflict", "counter"],
        "kind": ["text", "choice", "yes-no", "number", "date", "ref", "span"],
        "state": ["open", "answered", "unknown", "declined", "stale", "withdrawn"]}
    assert m.kind_closed("D", "session") == {"through": ["person", "agent"]}
    assert not {"why", "kind", "state", "through"} & set(m.closed_lists())     # never global
    text = _text(CLOSE)
    ok = _vol(text.replace("    stance: assumed\n", "    stance: assumed\n    state: whatever\n    kind: anything\n",
                           1))
    assert M.lint(ok).ok
    bad = _vol(text.replace("    why: missing\n", "    why: curious\n", 1))
    assert [(p.check, p.field) for p in M.lint(bad).errors] == [("closed-list", "why")]


def test_a_kinds_closed_list_overrides_the_global_one(tmp_path):
    (tmp_path / "z.manifest.cosm").write_text(
        "manifest: minicosm/0\nname: z\nversion: 1\nvolume: {catalog: z.cosm, single-file: true}\n"
        "closed-lists: {colour: [red, blue]}\n"
        "modules:\n  A:\n    kinds:\n      a: {refs: []}\n      b: {refs: [], closed: {colour: [green]}}\n"
        "checks: {load: [load], envelope: [closed-list]}\n", encoding="utf-8")
    reg = M.Registry([tmp_path])
    v = _vol("oes: z/1\nnodes:\n  - {id: A:a/1, type: a, colour: red}\n  - {id: A:b/1, type: b, colour: green}\n"
             "  - {id: A:b/2, type: b, colour: red}\n", "z.cosm", reg)
    assert [p.item for p in M.lint(v).errors] == ["A:b/2"]


# ---------------------------------------------------------------------------
# 9. addresses `<id>#<field>` (spec 9.1, 9.3)
# ---------------------------------------------------------------------------

def test_an_address_resolves_to_its_item_when_the_field_path_parses():
    v = M.load_volume(CLOSE)
    q = v.items["D:question/occasion"]
    target = M.resolve_ref(v, q, "I:occasion/why-written#roles.event")
    assert target is v.items["I:occasion/why-written"]
    assert M.resolve_ref(v, q, "N:audience/owners#who") is v.items["N:audience/owners"]         # field absent is fine
    assert M.resolve_ref(v, q, "N:audience/owners#no such") is None
    assert M.resolve_ref(v, q, "N:audience/nobody#who") is None
    text = _text(CLOSE).replace("    asked: [", "    asked: [N:audience/owners#who, ", 1)
    assert "N:audience/owners#who" in text and M.lint(_vol(text)).ok
    bad = _text(CLOSE).replace("    asked: [", "    asked: [N:audience/nobody#who, ", 1)
    assert [p.check for p in M.lint(_vol(bad)).errors] == ["ref-unresolved"]


# ---------------------------------------------------------------------------
# 10. module D, inherited from the core by every format (spec 13.4, 18.6.2)
# ---------------------------------------------------------------------------

def test_every_format_inherits_module_d_from_the_core():
    reg = M.default_registry()
    assert reg.core_modules_path == MANIFESTS / M.CORE_MODULES_FILE and reg.problems == []
    for m in reg.manifests.values():
        assert m.modules()[-1] == "D" and list(m.kinds("D")) == ["question", "session"], m.name
        assert "D" in m.inherited and "D" not in m._block("modules") and m.inherited_from == reg.core_modules_path
        assert m.grammar.seg["module"].fullmatch("D"), m.name
        assert m.required_fields("D", "question") == ["id", "type", "about", "asks", "why", "kind", "to", "raised",
                                                       "state"]


def test_a_manifest_that_declares_d_keeps_its_own(tmp_path):
    (tmp_path / M.CORE_MODULES_FILE).write_bytes((MANIFESTS / M.CORE_MODULES_FILE).read_bytes())
    (tmp_path / "z.manifest.cosm").write_text(
        "manifest: minicosm/0\nname: z\nversion: 1\nmodules:\n  A: {kinds: {a: {refs: []}}}\n"
        "  D: {name: Drafts, kinds: {draft: {refs: []}}}\n", encoding="utf-8")
    m = M.Registry([tmp_path]).get("z")
    assert m.modules() == ["A", "D"] and list(m.kinds("D")) == ["draft"] and m.inherited == {}


def test_the_core_letters_join_every_id_form():
    reg = M.default_registry()
    assert M.parse_id(reg.get("comprise"), "atom/meadow//D:question/x") == \
        {"module": "D", "kind": "question", "slug": "x", "part": "meadow", "bare": "D:question/x"}
    assert M.parse_id(reg.get("comprise"), "D:session/elicit-2026-11-02-a3f9")["kind"] == "session"
    assert M.parse_id(reg.get("cosm"), "D:question/x")["module"] == "D"                 # a COSM tree's <kind>/<slug>
    assert M.parse_id(reg.get("cosm"), "role/Founder")["module"] == "P"                  # its own ids unchanged
    assert reg.get("cosm").grammar.default_module == "P"
    assert reg.get("comprise").grammar.seg["module"].pattern == "[COMPRISED]"
    assert reg.get("canon").grammar.seg["module"].pattern == "[VD]"


def test_comprises_manifest_is_untouched_and_inherits_d():
    import json
    synced = json.loads((FIX / "cosm" / "manifest.json").read_text(encoding="utf-8"))
    rel = "defaults/cosm/manifests/comprise.manifest.cosm"
    assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == synced["files"][rel]
    assert "D" in M.default_registry().get("comprise").modules()


def test_a_holograph_may_hold_dialectic_items_without_a_form(tmp_path):
    from enough import ascribe
    src = FIX / "ascribe"
    holo = next(p.parent for p in src.rglob("holograph.cosm"))
    text = _text(holo / "holograph.cosm")
    data = M.yaml_load(text)
    assert "nodes" not in data or isinstance(data["nodes"], list)
    extra = ("  - {id: D:session/session-9, type: session, at: 2026-11-05T10:00:00Z, with: {to: holder, who: the "
             "holder}, through: person}\n")
    text = text.rstrip("\n") + "\n" + ("" if "nodes:" in text else "nodes:\n") + extra
    import shutil
    dst = tmp_path / holo.name
    shutil.copytree(holo, dst)
    (dst / "holograph.cosm").write_text(text, encoding="utf-8")
    rep = ascribe.lint_holograph(dst)
    assert not [p for p in rep.problems() if p.item == "D:session/session-9"], [str(p) for p in rep.problems()]


def test_the_core_modules_file_is_not_a_manifest_nor_a_moves_sidecar():
    from enough.thym import declarations as dc
    assert not M.CORE_MODULES_FILE.endswith((".manifest.cosm", ".moves.cosm"))
    decls = dc.load()
    assert decls.problems == []
    assert {decls[n].owner for n in ("derive", "tell", "atem", "expand")} == {"fabula"}


def test_a_broken_core_modules_file_is_a_problem_never_a_crash(tmp_path):
    (tmp_path / M.CORE_MODULES_FILE).write_text("modules-of: elsewhere\nmodules: {}\n", encoding="utf-8")
    (tmp_path / "z.manifest.cosm").write_text("manifest: minicosm/0\nname: z\nversion: 1\n", encoding="utf-8")
    reg = M.Registry([tmp_path])
    assert reg.get("z").modules() == [] and len(reg.problems) == 1 and M.CORE_MODULES_FILE in reg.problems[0]


# ---------------------------------------------------------------------------
# 11. the tree digest (spec 18.4.1; schema appendix G)
# ---------------------------------------------------------------------------

def test_the_tree_digest_of_tally_is_the_reference_value():
    r = M.tree_digest(FAB / "tally")
    assert (r["files"], r["bytes"], r["skipped"], r["tree"]) == (9, 11325, 0, TALLY_TREE)
    assert [rel for rel, _, _ in r["read"]] == ["CHANGES.md", "LICENSE", "README.md", "tally/__init__.py",
                                                "tally/__main__.py", "tally/cli.py", "tally/ledger.py",
                                                "tally/render.py", "tests/test_tally.py"]
    src = M.load_volume(TALLY).catalog["source"]
    assert (src["tree"], src["files"], src["bytes"], src["skipped"]) == (r["tree"], r["files"], r["bytes"],
                                                                         r["skipped"])


def test_the_tree_digest_reads_exactly_the_files_the_spec_names(tmp_path):
    root = tmp_path / "tool"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_bytes(b"x = 1\r\n")                  # raw bytes: CRLF kept
    (root / "B.md").write_bytes("caf\u00e9\n".encode("utf-8"))
    for d in (".git", "__pycache__", "node_modules", "dist", "x.egg-info", "tool.cshort-2026-11-05-1412", "env"):
        (root / d).mkdir()
        (root / d / "f.py").write_text("skipped whole\n", encoding="utf-8")
    (root / "env" / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    skipped = {".DS_Store": b"x", "m.pyc": b"x", "lib.so": b"x", "tool.fabulac.cosm": b"oes: fabula/1\n",
               "tool.catem-2026-11-05-1415.md": b"# x\n", "big.txt": b"a" * 1_000_001, "nul.txt": b"a\0b",
               "latin.txt": "caf\u00e9".encode("latin-1")}
    for name, data in skipped.items():
        (root / name).write_bytes(data)
    os.symlink(root / "B.md", root / "link.md")
    os.symlink(root / "pkg", root / "linkdir")
    r = M.tree_digest(root)
    assert [rel for rel, _, _ in r["read"]] == ["B.md", "pkg/a.py"]
    assert r["skipped"] == len(skipped) + 1             # the file symlink counts; a folder skipped whole does not
    h = hashlib.sha256()
    for rel, data in (("B.md", "caf\u00e9\n".encode("utf-8")), ("pkg/a.py", b"x = 1\r\n")):
        h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
    assert r["tree"] == h.hexdigest() and r["bytes"] == len("caf\u00e9\n".encode("utf-8")) + 7
    assert M.tree_digest(tmp_path / "empty-or-missing")["tree"] == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# 12. banks, both shapes (spec 18.6.6)
# ---------------------------------------------------------------------------

def test_the_fabula_carries_a_bank_per_flavour():
    banks = M.default_registry().get("fabula").banks()
    assert [(b["name"], b["for"], b["to"], len(b["questions"])) for b in banks] == [
        ("fabulan", {"flavour": "fabulan"}, "author", 17), ("fabulap", {"flavour": "fabulap"}, "author", 25),
        ("fabulac", {"flavour": "fabulac"}, "maker", 17)]
    first = banks[1]["questions"][7]
    assert (first["id"], first["about"], first["kind"], first["to"]) == ("speaker", "C:voice#roles.speaker", "text",
                                                                       "author")


def test_ascribes_older_shape_reads_as_one_bank():
    m = M.default_registry().get("ascribe")
    (bank,) = m.banks()
    assert (bank["name"], bank["to"]) == ("ascribe", "holder")
    qs = bank["questions"]
    assert len(qs) == sum(len(v) for v in m.data["dialectic"]["questions"].values())
    assert qs[0] == {"id": "A1", "about": "A", "asks": "What do you go back to, again and again?", "kind": "text",
                     "why": "missing", "to": "holder"}
    assert M.default_registry().get("canon").banks() == []


# ---------------------------------------------------------------------------
# 13. nothing to learn: the dialectic's fields are kept as written
# ---------------------------------------------------------------------------

def test_the_dialectics_fields_are_kept():
    v = M.load_volume(CLOSE)
    aud = v.items["N:audience/owners"].data
    assert set(aud["provenance"]["answered"]) == {"who", "summary"}
    q = v.items["D:question/audience"].data
    assert q["settled"]["wrote"] == ["N:audience/owners#summary", "N:audience/owners#who"]


# ---------------------------------------------------------------------------
# The shipped manifests
# ---------------------------------------------------------------------------

def test_every_shipped_manifest_loads_and_carries_its_place():
    reg = M.default_registry()
    assert reg.problems == [] and reg.notes == []
    names = sorted(p.name for p in MANIFESTS.glob("*.cosm"))
    assert names == ["ascribe.manifest.cosm", "canon.manifest.cosm", "comprise.manifest.cosm", "comprise.moves.cosm",
                     "core.modules.cosm", "cosm.manifest.cosm", "doc.manifest.cosm", "fabula.manifest.cosm",
                     "thym.manifest.cosm"]


def test_the_fabula_manifest():
    m = M.default_registry().get("fabula")
    assert (m.name, m.title, m.version, m.core) == ("fabula", "fabula", 1, True)
    assert m.declaration["value"] == "fabula/1" and m.declaration["absent"] == "refuse"
    assert list(m._block("modules")) == list("ILEKNCRPTX")                     # ten; D is the core's
    assert m.flavours == ["fabulan", "fabulap", "fabulac"] and m.flavour_absent == "fabulan"
    assert {"flavour", "flavour-kind"} <= set(m.checks())
    assert m.data["catalog"]["derived-runs-fields"] == ["program", "run", "at", "model", "route", "provider"]
    for L in "LEKX":
        for k, spec in m.kinds(L).items():
            assert spec["flavours"] == list(fabula.FLAVOURS), (L, k)
    assert [mv["name"] for mv in m.data["moves"]] == ["derive", "tell", "atem", "expand"]
    assert all(mv["code"].startswith("enough.thym.moves.emf:") for mv in m.data["moves"])
    assert "emf-checks" in m.data["moves"][0]["contract"]
    assert all(m.matches_catalog(n) for n in ("close.md.fabulan.cosm", "rose.txt.fabulap.cosm",
                                               "tool.fabulac.cosm", "close.md.cosm"))


def test_the_four_other_built_ins_changed_only_by_core():
    for name in ("cosm", "canon", "doc", "thym"):
        text = _text(MANIFESTS / f"{name}.manifest.cosm")
        assert re.search(r"^core: true\b", text, re.M), name


# ---------------------------------------------------------------------------
# The fabula's own checks (enough/fabula.py), each clean and broken
# ---------------------------------------------------------------------------

def _own(text: str, name: str = "x.fabulac.cosm") -> M.Report:
    return fabula.lint(_vol(text, name))


def test_the_three_examples_pass_every_check():
    for path, n, pending, fl in ((CLOSE, 28, 3, "fabulan"), (ROSE, 43, 5, "fabulap"), (TALLY, 79, 4, "fabulac")):
        rep = fabula.lint(path)
        v = rep.volume
        assert v.declaration.how == "oes" and fabula.flavour(v) == fl
        assert len(v.items) == n and len(rep.pending) == pending
        assert rep.ok and rep.problems() == [] and rep.not_run == [], [str(p) for p in rep.problems()]
        assert set(fabula.OWN_CHECKS) | {"flavour", "flavour-kind"} <= set(rep.checks)


def test_code_span():
    t = _text(TALLY)
    assert "span: {file: tally/ledger.py, lines: " in t
    for bad, msg in (("span: {file: tally/nowhere.py, lines: ", "tally/nowhere.py is not the path of a C:file"),
                     ("span: {file: tally/ledger.py, lines: \"9000-9001\"}\n    x: ", "run past the end"),):
        broken = re.sub(r"span: \{file: tally/ledger.py, lines: \"[0-9-]+\"\}", bad.rstrip(), t, count=1) \
            if "9000" in bad else t.replace("span: {file: tally/ledger.py, lines: ", bad, 1)
        errs = _checks(_own(broken), "code-span")
        assert errs and msg in errs[0].message and errs[0].severity == "error", [str(p) for p in errs]
    errs = _checks(_own(re.sub(r"span: \{file: (tally/ledger.py), lines: \"([0-9]+)-([0-9]+)\"\}",
                              r'span: {file: \1, lines: "\3-\2"}', t, count=1)), "code-span")
    assert errs and "n or n-m" in errs[0].message
    errs = _checks(_own(t.replace("span: {file: tally/ledger.py, lines: ", "span: {lines: ", 1)), "code-span")
    assert errs and errs[0].message == "a span in a fabulac is {file, lines}"
    assert not _checks(_own(_text(CLOSE), "x.fabulan.cosm"), "code-span")       # a text's spans are not code


def test_licence_recorded():
    t = _text(TALLY)
    assert "licence: MIT" in t
    errs = _checks(_own(t.replace(", licence: MIT}", "}", 1)), "licence-recorded")
    assert [p.severity for p in errs] == ["error"] and "source.licence" in errs[0].message
    warn = _checks(_own(t.replace("licence: MIT}", 'licence: {pending: "which licence?"}}', 1)), "licence-recorded")
    assert [p.severity for p in warn] == ["warning"]
    no_item = re.sub(r"  - id: R:licence/[^\n]*\n(?:    [^\n]*\n)+", "", t, count=1)
    assert "R:licence/" not in no_item
    errs = _checks(_own(no_item), "licence-recorded")
    assert [p.message for p in errs] == ["a fabulac holds an R:licence item: the terms the source may be used on"]


def test_reading_whose():
    t = _text(ROSE)
    readings = re.findall(r"whose: \{[^}]*\}", t)
    assert readings
    broken = t.replace(readings[0], "whose: {by: author}", 1)
    warn = _checks(_own(broken, "x.fabulap.cosm"), "reading-whose")
    assert [p.severity for p in warn] == ["warning"] and "session" in warn[0].message
    broken = t.replace(readings[0], "whose: {by: critic}", 1)
    warn = _checks(_own(broken, "x.fabulap.cosm"), "reading-whose")
    assert warn and "names the critic" in warn[0].message
    ok = t.replace(readings[0], 'whose: {by: critic, name: {pending: "which critic?"}}', 1)
    assert not _checks(_own(ok, "x.fabulap.cosm"), "reading-whose")


def test_interface_signature():
    t = _text(TALLY)
    sig = re.search(r"\n    signature: [^\n]*", t).group(0)
    warn = _checks(_own(t.replace(sig, "", 1)), "interface-signature")
    assert [p.severity for p in warn] == ["warning"] and "carries its exact signature" in warn[0].message


def test_case_outcome():
    t = _text(TALLY)
    m = re.search(r"\n    expect: [^\n]*(?:\n      [^\n]*)*", t)
    errs = _checks(_own(t.replace(m.group(0), "", 1)), "case-outcome")
    assert errs and errs[0].severity == "error" and "no expect" in errs[0].message


def test_question_about():
    t = _text(CLOSE)
    assert "    about: I:occasion/why-written#roles.event\n" in t
    for about, fine in (("I", True), ("N:audience", True), ("N:audience/owners#who", True), ('{lines: "3-4"}', True),
                        ('{start: "Meadow closes", end: "arrive."}', True), ("N:nothing", False),
                        ("Q", False), ("N:audience/nobody", False), ("N:audience/owners#bad path", False),
                        ('{lines: "4-3"}', False), ("{file: x.py, lines: \"1\"}", False),
                        ("C:voice#roles.speaker", False)):
        rep = _own(t.replace("    about: I:occasion/why-written#roles.event\n", f"    about: {about}\n", 1),
                   "x.fabulan.cosm")
        errs = _checks(rep, "question-about")
        assert (not errs) == fine, (about, [str(p) for p in errs])
    gone = t.replace("about: N:audience/owners\n", "about: N:audience/gone\n", 1)
    assert "about: N:audience/gone" in gone
    assert not _checks(_own(gone, "x.fabulan.cosm"), "question-about")               # settled: skipped (18.6.3)
    spans = _text(TALLY)
    assert not _checks(_own(spans.replace("about: ", "about: {file: tally/cli.py, lines: \"1-2\"}\n    was: ", 1)),
                       "question-about")


def test_question_shape():
    t = _text(CLOSE)
    occ = "    state: open\n"
    assert occ in t
    cases = [
        (t.replace("    kind: text\n    to: author\n    raised: {by: bank, from: fabulan/occasion",
                   "    kind: choice\n    to: author\n    raised: {by: bank, from: fabulan/occasion", 1), "options"),
        (t.replace(occ, "    state: answered\n", 1), "an answer to show"),
        (t.replace(occ, "    state: open\n    settled: {at: 2026-11-05T10:31:02Z, run: x, wrote: []}\n", 1),
         "nothing settled"),
        (t.replace(occ, "    state: withdrawn\n", 1), "ended"),
        (t.replace("    state: answered\n", "    state: unknown\n", 1), "value: null"),
        (t.replace("    state: answered\n", "    state: declined\n", 1), "declined: true"),
    ]
    for text, words in cases:
        errs = _checks(_own(text, "x.fabulan.cosm"), "question-shape")
        assert errs and words in errs[0].message and errs[0].severity == "error", (words, [str(p) for p in errs])
    ok = t.replace(occ, "    state: withdrawn\n    ended: {at: 2026-11-05T11:00:00Z, by: person, because: asked "
                        "twice}\n", 1)
    assert not _checks(_own(ok, "x.fabulan.cosm"), "question-shape")


def test_session_declared():
    t = _text(CLOSE)
    assert "D:session/session-1]" in t
    gone = re.sub(r"  - id: D:session/session-1\n(?:    [^\n]*\n)+", "", t, count=1)
    rep = _own(gone, "x.fabulan.cosm")
    warn = _checks(rep, "session-declared")
    assert warn and all(p.severity == "warning" for p in warn)
    assert "D:session/session-1 is not a session of this volume" in [p.message for p in warn]
    bare = t.replace("sources: ['close.md#L5', D:session/session-1]", "sources: ['close.md#L5', session-2]", 1)
    assert "session-2]" in bare
    notes = _checks(_own(bare, "x.fabulan.cosm"), "session-declared")
    assert [p.severity for p in notes] == ["note"]


def test_the_dialectic_checks_run_on_any_format():
    canon = _text(FIX / "cosm" / "canon" / "rust-book" / "canon.cosm")
    q = ("  - {id: D:question/x, type: question, about: V:file/nothing, asks: 'Is it?', why: missing, kind: choice, "
         "to: owner, raised: {by: person}, state: open}\n")
    assert "\nnodes:\n" in canon
    v = _vol(canon.replace("\nnodes:\n", "\nnodes:\n" + q, 1), "canon.cosm")
    rep = fabula.lint(v)
    assert {p.check for p in rep.errors} == {"question-about", "question-shape"}
    assert set(fabula.DIALECTIC_CHECKS) <= set(rep.checks) and not set(fabula.FABULA_CHECKS) & set(rep.checks)
    assert rep.not_run == []


def test_the_cli(capsys):
    assert fabula.main(["lint", str(TALLY)]) == 0
    out = capsys.readouterr().out
    assert out.strip() == "fabula/1, fabulac: 79 items, 0 errors, 0 warnings, 0 notes, 4 open questions"
    assert fabula.main(["lint", str(FIX / "cosm" / "emf" / "notes.md.cosm")]) == 0
    assert "(old: emf/1)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Every `oes: emf/1` file the repository keeps reads as a fabula, by its old spelling
# ---------------------------------------------------------------------------

EMF_FILES = sorted(p for p in FIX.rglob("*.cosm") if M.sniff_declaration(p) == "emf/1")


def test_the_repository_keeps_emf_files():
    assert len(EMF_FILES) >= 20


@pytest.mark.parametrize("path", EMF_FILES, ids=lambda p: str(p.relative_to(FIX)))
def test_every_emf_file_reads_as_a_fabula_by_its_old_spelling(path):
    v = M.load_volume(path)
    if path.parent.name == "bad" and path.name == "load.cosm":
        return                                      # a file that does not parse, on purpose
    assert v.refused is None and v.oes == "fabula/1" and v.declaration.how == "old" and v.catalog["oes"] == "emf/1"
    assert fabula.flavour(v) == "fabulan"
    if path.parent.name != "bad":                   # the bad volumes fail one generic check each, on purpose
        rep = fabula.lint(v)
        assert rep.ok and not rep.warnings, [str(p) for p in rep.problems()]


# ---------------------------------------------------------------------------
# The 0.6 draft of MacroCOSM OES: every cosm block loads and passes its checks
# ---------------------------------------------------------------------------

_BLOCK = re.compile(r"^```cosm\n(.*?)^```", re.S | re.M)


def _draft_blocks() -> list[str]:
    return _BLOCK.findall(_text(DRAFT))


def _name(data: dict) -> str:
    oes = data.get("oes")
    if oes == "canon/1":
        return "canon.cosm"
    if oes in ("fabula/1", "emf/1"):
        src = str((data.get("source") or {}).get("path") or "text.md").rstrip("/")
        return Path(src).name + (f".{data['flavour']}.cosm" if data.get("flavour") else ".cosm")
    if oes == "doc/1":
        return f"{str(data['id']).split('/', 1)[-1]}.{(data.get('telling') or {}).get('lang', 'en')}.doc.cosm"
    if oes == "ascribe/1":
        return "holograph.cosm"
    if oes == "thym/1":
        kind, slug = data.get("kind") or "morph", str(data.get("id", "thym/x")).split("/", 1)[-1]
        return "package.cosm" if kind == "package" else f"{slug}.{kind}.cosm"
    return "brand.cosm"


def test_the_draft_holds_the_fabulas_examples():
    datas = [M.yaml_load(b) for b in _draft_blocks()]
    assert len(datas) == 11
    flavours = [d.get("flavour") for d in datas if d.get("oes") == "fabula/1"]
    assert {"fabulan", "fabulap", "fabulac"} <= set(flavours)
    assert sum(1 for d in datas if d.get("oes") == "emf/1") == 1


@pytest.mark.parametrize("index", range(len(_draft_blocks())))
def test_every_draft_block_loads_and_passes(index, tmp_path):
    from enough import ascribe
    text = _draft_blocks()[index]
    data = M.yaml_load(text)
    path = tmp_path / _name(data)
    path.write_text(text, encoding="utf-8")
    v = M.load_volume(path)
    assert v.refused is None, v.refused
    if data.get("oes") == "emf/1":
        assert v.oes == "fabula/1" and v.declaration.how == "old"
    rep = ascribe.lint_holograph(v) if data.get("oes") == "ascribe/1" else fabula.lint(v)
    assert rep.ok and not rep.warnings and not rep.notes, [str(p) for p in rep.problems()]
    assert not (set(rep.not_run) & (set(fabula.OWN_CHECKS) | set(M.CORE_CHECKS)))


# ---------------------------------------------------------------------------
# DocOES: the overlay reads the 0.6 text's shapes, and the reference says what each format is
# ---------------------------------------------------------------------------

def test_the_overlay_reads_the_draft_shapes():
    from enough import docoes as D
    t = D.spec_tables(_text(DRAFT))
    # 18.1's `Format … Enumerates` and 19's `MiniCOSM … Enumerates`: all seven formats
    assert sorted(t.minicosms) == ["ascribe", "canon", "comprise", "cosm", "doc", "fabula", "thym"]
    assert t.minicosms["fabula"].startswith("one input decompiled")
    # 14.5's `Format | Lens | Draws`
    assert ("fabula", "claims") in t.lenses and ("ascribe", "graph") in t.lenses
    # kinds under `### 18.4 fabula:` (What it holds, several kinds per row) and `### 19.2 ascribe:` (What it is)
    assert t.kinds[("fabula", "interface")].startswith("something another program")
    assert {("fabula", k) for k in ("person", "org", "place", "work", "thing")} <= set(t.kinds)
    assert t.kinds[("ascribe", "affinity")] == "something the person is drawn to, or turns from"
    assert {"flavour", "flavour-kind"} <= set(t.checks)
    # the text before 0.6 still reads: emf's rows, MiniCOSM headers
    old = D.spec_tables(_text(REPO / "docs" / "MACROCOSM_OES.md"))
    assert "emf" in old.minicosms and ("emf", "claims") in old.lenses


def test_the_reference_built_from_the_draft_says_built_in_or_minicosm(tmp_path):
    import shutil
    from enough import docoes as D
    shutil.copytree(REPO / "defaults" / "cosm", tmp_path / "defaults" / "cosm")
    (tmp_path / "docs").mkdir()
    shutil.copyfile(DRAFT, tmp_path / "docs" / "MACROCOSM_OES.md")
    nodes = D.catalog_for("macrocosm-oes", "en", sources=tmp_path, synced=False)["nodes"]
    by = {n["id"]: n for n in nodes}
    formats = [n for n in nodes if n.get("type") == "minicosm"]
    assert [(n["id"].split("/")[1], n["core"]) for n in formats] == [
        ("comprise", False), ("cosm", True), ("canon", True), ("fabula", True), ("doc", True), ("ascribe", False),
        ("thym", True)]
    assert by["R:minicosm/fabula"]["atem"] == "one input decompiled, a text, a poem or a folder of code"
    assert by["R:minicosm/fabula"]["old"] == ["emf/1"]
    assert by["R:kind/ascribe.A.affinity"]["atem"] == "something the person is drawn to, or turns from"
    examples = [n for n in nodes if n.get("type") == "example"]
    old = [n for n in examples if n["body"].startswith("oes: emf/1\n")]
    assert old and old[0]["declaration"] == "fabula/1"                      # the format the reader identified
    assert len(examples) == 11 and len(old) == 1
    assert old[0]["declares"] == "R:minicosm/fabula"                         # the old spelling declares the fabula
    assert all(n["declares"] in by for n in examples)
