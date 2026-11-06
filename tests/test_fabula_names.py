"""`enough.fabula_names` (0.6, lane C2a; MacroCOSM OES 18.4 its volume, 18.4.4; pins P3): the names a text's twin
takes, how a twin is found beside its text under each of the three names, the stem of a short, and the flavour enough
suggests for a text. Pure: files in tmp_path only."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from enough import canon, canon_derive as CD, fabula_names as N

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"
OLD = (FIX / "emf" / "notes.md.cosm").read_text(encoding="utf-8")      # an `emf/1` twin, as 0.4.3 wrote one


def new_twin(flavour: str, at: str = "2026-11-05T10:00:00Z") -> str:
    """The fixture twin respelled as a writer of 0.6 writes it."""
    body = OLD.replace("oes: emf/1\n", f"oes: fabula/1\nflavour: {flavour}\n", 1)
    body = body.replace("id: emf/notes-md", "id: fabula/notes-md", 1)
    return body.replace("derived: {at: 2026-10-22T10:30:00Z", f"derived: {{at: {at}", 1)


def put(folder: Path, name: str, text: str) -> Path:
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def here(tmp_path: Path) -> Path:
    shutil.copyfile(FIX / "emf" / "notes.md", tmp_path / "notes.md")
    return tmp_path


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def test_the_three_names_and_the_old_one():
    assert N.twin_name("close.md", "fabulan") == "close.md.fabulan.cosm"
    assert N.twin_name("rose.txt", "fabulap") == "rose.txt.fabulap.cosm"
    assert N.twin_name("tool", "fabulac") == "tool.fabulac.cosm"
    assert N.old_twin_path(Path("a/close.md")) == Path("a/close.md.cosm")
    assert N.parse("close.md.fabulan.cosm") == ("close.md", "fabulan")
    assert N.parse("rose.txt.fabulap.cosm") == ("rose.txt", "fabulap")
    assert N.parse("tool.fabulac.cosm") == ("tool", "fabulac")
    assert N.parse("close.md.cosm") == ("close.md", None)
    assert N.parse("close.md") is None and N.parse(".cosm") is None
    with pytest.raises(N.FlavourError):
        N.suffix("fabulax")


@pytest.mark.parametrize("given,want", [(None, None), ("", None), ("fabulan", "fabulan"), (" FabulaP ", "fabulap")])
def test_a_text_flavour_is_checked(given, want):
    assert N.check_text_flavour(given) == want


def test_fabulac_is_refused_for_a_text_in_plain_words():
    with pytest.raises(N.FlavourError) as e:
        N.check_text_flavour("fabulac")
    assert "folder of code" in str(e.value) and "fabulan (prose) or fabulap (verse)" in str(e.value)
    with pytest.raises(N.FlavourError) as e:
        N.check_text_flavour("emf")
    assert "fabulan (prose) or fabulap (verse)" in str(e.value)


# ---------------------------------------------------------------------------
# One text's twin, under each name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,text,flavour", [
    ("notes.md.fabulan.cosm", lambda: new_twin("fabulan"), "fabulan"),
    ("notes.md.fabulap.cosm", lambda: new_twin("fabulap"), "fabulap"),
    ("notes.md.cosm", lambda: OLD, "fabulan"),
])
def test_a_twin_is_found_under_each_name(here: Path, name: str, text, flavour: str):
    twin = put(here, name, text())
    assert N.text_twins(here / "notes.md") == {flavour: twin}
    assert N.find_twin(here / "notes.md") == twin and N.find_twin(here / "notes.md", flavour) == twin
    assert N.is_twin(twin) and N.text_of_twin(twin) == here / "notes.md"
    assert canon.is_emf_twin(twin) and canon.emf_twin_path(here / "notes.md") == twin
    assert CD.twin_path(here / "notes.md") == twin and CD.twin_state(here / "notes.md", flavour) in ("fresh", "stale")
    ft = N.folder_twins(sorted(here.iterdir()))
    assert ft.primary == {"notes.md": twin} and ft.hidden == {name} and ft.superseded == {}
    assert ft.flavour("notes.md") == flavour and N.flavour_of_twin(twin) == flavour
    # the listings hide it behind its text
    assert canon.emf_twins(sorted(here.iterdir())) == {"notes.md": twin}
    other = "fabulap" if flavour == "fabulan" else "fabulan"
    assert N.find_twin(here / "notes.md", other) is None and CD.twin_state(here / "notes.md", other) == "absent"


def test_with_no_twin_a_new_one_is_named_by_its_flavour(here: Path):
    assert N.text_twins(here / "notes.md") == {}
    assert CD.twin_path(here / "notes.md") == here / "notes.md.fabulan.cosm"
    assert CD.twin_path(here / "notes.md", "fabulap") == here / "notes.md.fabulap.cosm"
    assert CD.twin_state(here / "notes.md") == "absent"


def test_a_file_of_a_twin_name_that_is_not_a_fabula_is_not_a_twin(here: Path):
    p = put(here, "notes.md.fabulan.cosm", "oes: canon/1\nid: canon/x\nname: x\nnodes: []\n")
    assert not N.is_twin(p) and N.text_twins(here / "notes.md") == {}
    assert N.folder_twins(sorted(here.iterdir())).hidden == set()


@pytest.mark.parametrize("name,text", [("rain.fabulan.cosm", lambda: new_twin("fabulan")), ("rain.cosm", lambda: OLD),
                                       ("rain.fabulap.cosm", lambda: new_twin("fabulap"))])
def test_a_standalone_fabula_is_no_twin(tmp_path: Path, name: str, text):
    p = put(tmp_path, name, text())
    assert not N.is_twin(p) and N.text_of_twin(p) is None
    ft = N.folder_twins([p])
    assert ft.hidden == set() and ft.primary == {}
    assert N.declares_fabula(p)


def test_a_fabulac_beside_a_folder_is_named_but_not_paired_as_a_text_twin(tmp_path: Path):
    (tmp_path / "tool").mkdir()
    p = put(tmp_path, "tool.fabulac.cosm", new_twin("fabulac"))
    assert N.parse(p.name) == ("tool", "fabulac") and not N.is_twin(p)
    assert N.folder_twins(sorted(tmp_path.iterdir())).hidden == set()


def test_both_names_the_flavour_named_one_is_the_twin_and_the_old_one_an_ordinary_file(here: Path):
    old = put(here, "notes.md.cosm", OLD)
    new = put(here, "notes.md.fabulan.cosm", new_twin("fabulan"))
    assert N.text_twins(here / "notes.md") == {"fabulan": new}
    assert N.is_twin(new) and not N.is_twin(old) and N.superseded_by(old) == new
    ft = N.folder_twins(sorted(here.iterdir()))
    assert ft.hidden == {"notes.md.fabulan.cosm"}
    assert ft.superseded == {"notes.md.cosm": ("notes.md", "notes.md.fabulan.cosm")}
    entry = canon.superseded_entry("notes.md.cosm", "docs", ft)
    assert entry == {"of": "docs/notes.md", "twin": "docs/notes.md.fabulan.cosm"}


def test_one_twin_per_flavour_and_the_slot_shows_the_one_derived_last(here: Path):
    nan = put(here, "notes.md.fabulan.cosm", new_twin("fabulan", "2026-11-05T09:00:00Z"))
    pap = put(here, "notes.md.fabulap.cosm", new_twin("fabulap", "2026-11-05T11:00:00Z"))
    os.utime(nan, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))   # mtime later; derived.at decides
    assert N.text_twins(here / "notes.md") == {"fabulan": nan, "fabulap": pap}
    assert N.primary(N.text_twins(here / "notes.md")) == ("fabulap", pap)
    assert N.find_twin(here / "notes.md") == pap and N.find_twin(here / "notes.md", "fabulan") == nan
    ft = N.folder_twins(sorted(here.iterdir()))
    assert ft.primary == {"notes.md": pap} and ft.hidden == {nan.name, pap.name}
    entry = canon.listing_entry(here / "notes.md", "", ft)
    assert entry["path"] == "notes.md.fabulap.cosm" and entry["flavour"] == "fabulap"
    assert entry["others"] == [{"path": "notes.md.fabulan.cosm", "state": entry["others"][0]["state"],
                                "flavour": "fabulan"}]
    # an old-named fabulan beside a fabulap is the text's fabulan, not superseded
    nan.unlink()
    old = put(here, "notes.md.cosm", OLD)
    assert N.text_twins(here / "notes.md") == {"fabulan": old, "fabulap": pap}


def test_derived_at_reads_the_flow_and_the_block_form(tmp_path: Path):
    a = put(tmp_path, "a.cosm", "oes: fabula/1\nderived: {at: 2026-11-05T10:00:00Z, by: person}\nnodes: []\n")
    b = put(tmp_path, "b.cosm", "oes: fabula/1\nderived:\n  by: person\n  at: '2026-11-05T12:00:00Z'\nnodes: []\n")
    c = put(tmp_path, "c.cosm", "oes: fabula/1\nnodes: []\n")
    assert N.derived_at(a) == "2026-11-05T10:00:00Z" and N.derived_at(b) == "2026-11-05T12:00:00Z"
    assert N.derived_at(c) == "" and N.derived_at(tmp_path / "gone.cosm") == ""


# ---------------------------------------------------------------------------
# Shorts: the stem
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,stem", [
    ("close.md.fabulan.cosm", "close"), ("close.md.cosm", "close"), ("rose.txt.fabulap.cosm", "rose"),
    ("rain.fabulan.cosm", "rain"), ("rain.cosm", "rain"), ("tool.fabulac.cosm", "tool"),
    ("report.pdf.md.fabulan.cosm", "report.pdf"),
])
def test_the_stem_of_a_short(tmp_path: Path, name: str, stem: str):
    import datetime as dt
    assert N.short_stem(name) == stem
    out = CD.short_path(tmp_path / name, dt.datetime(2026, 11, 5, 10, 42))
    assert out.name == f"{stem}.short-2026-11-05-1042.md"


def test_a_short_finds_its_standalone_fabula_under_each_name():
    n = canon.short_text_name
    for name in ("rain.fabulan.cosm", "rain.fabulap.cosm", "rain.fabulac.cosm", "rain.cosm"):
        assert n("rain.short-2026-11-05-1042.md", [name, "other.md"], is_standalone=lambda x: True) == name
    # a text wins over a standalone fabula; the flavour-named standalone over the old name
    assert n("rain.short-2026-11-05-1042.md", ["rain.md", "rain.fabulan.cosm"]) == "rain.md"
    assert n("rain.short-2026-11-05-1042.md", ["rain.cosm", "rain.fabulan.cosm"]) == "rain.fabulan.cosm"


def test_thyms_output_stem_reads_the_new_names():
    from enough import thym_api
    assert thym_api.stem_of(Path("notes.md.fabulan.cosm")) == "notes"
    assert thym_api.stem_of(Path("notes.md.cosm")) == "notes"
    assert thym_api.stem_of(Path("mine.morph.cosm")) == "mine"


# ---------------------------------------------------------------------------
# The flavour enough suggests
# ---------------------------------------------------------------------------

SICK_ROSE = (FIX.parent / "fabula" / "poems" / "the-sick-rose.txt").read_text(encoding="utf-8")
CLOSE = (FIX.parent / "fabula" / "guides" / "close.md").read_text(encoding="utf-8")
STANZAS = "Whose woods these are I think I know.\nHis house is in the village though;\n\n" \
          "He will not see me stopping here\nTo watch his woods fill up with snow.\n"
LIMERICK = ("There once was a man from the coast\nWho wanted to talk to a ghost.\n\n"
            "The ghost wasn't there,\nSo he talked to a chair,\nWhich is what he enjoyed talking to most.\n")
PROSE = ("The orchard keeps a record of every tree it plants, and every year the record grows by a page "
         "or two.\n\nWe meet on Thursdays to go through the ledger, line by line, before the books close.\n")
WRAPPED = "\n".join(["The orchard keeps a record of every tree it plants, and the record"] * 3 + [""]
                    + ["grows by a page or two each year, which nobody minds very much at all."] * 3) + "\n"


@pytest.mark.parametrize("text,want", [
    (SICK_ROSE, "fabulap"),
    (STANZAS, "fabulap"),
    (LIMERICK, "fabulap"),
    ("Roses are red,\nviolets are blue.\n\nSugar is sweet,\nand so are you.\n", "fabulap"),
    (CLOSE, "fabulan"),
    (PROSE, "fabulan"),
    (WRAPPED, "fabulan"),                                         # hard-wrapped prose: long lines
    ("# A poem\n\nRoses are red,\nviolets are blue.\n\nSugar is sweet,\nand so are you.\n", "fabulan"),  # a heading
    ("Roses are red,\nviolets are blue,\nsugar is sweet,\nand so are you.\n", "fabulan"),   # one stanza
    ("Buy milk.\n\nCall Sam.\n\nPost the letter.\n\nWater the beans.\n", "fabulan"),  # one line a stanza: notes
    ("- milk\n- eggs\n\n| a | b |\n|---|---|\n", "fabulan"),        # a table
    ("```\nline one\nline two\n```\n\nline three\nline four\n", "fabulan"),   # a code fence
    ("", "fabulan"),
    ("A single short line.\n", "fabulan"),
])
def test_the_flavour_suggested_for_a_text(text: str, want: str):
    assert N.suggest_flavour(text) == want
