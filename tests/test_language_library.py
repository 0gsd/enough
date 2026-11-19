"""The language library, enough's half (0.8, lane W3-X2c): `scripts/sync_languages.py`, the vendored index builder
(`enough/library_index.py`), `enough/language_library.py`, `resolve_citation` and `ground-cited` against it, the
DocOES volume of a kept text, and the `/api/library/*` routes.

Nothing third-party is in this repository: the shelf the tests sync is cosmoes-site's made-up fixture shelf, copied
as `tests/fixtures/library-shelf/` (a text in the shape of Python's plain-text build, an HTML sheet, a memo kept
unchanged, a pin), and the Python-shaped shelves are written here from made-up words. One test reads the owner's
0.7 copy of the Python 3.13 text into tmp when this machine has it, and resolves the real ground catalogue's
citations against it.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from enough import docoes, language_library as ll, languages, library_index as li, macrocosm as mc
from enough import transconception as tc

REPO = Path(__file__).resolve().parent.parent
SHELF = REPO / "tests" / "fixtures" / "library-shelf"
COSMOES = next((p / "cosmoes-site" for p in REPO.parents
                if (p / "cosmoes-site" / "client" / "library_index.py").is_file()), None)
X0_TEXT = Path("/Users/m3u/METMcloud/fabulac-test-repos/_x0/library/python/3.13/text/python-3.13-docs-text")

_spec = importlib.util.spec_from_file_location("sync_languages", REPO / "scripts" / "sync_languages.py")
sync_languages = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_languages)

_tspec = importlib.util.spec_from_file_location("_tc_tests", REPO / "tests" / "test_transconception.py")
_tc_tests = importlib.util.module_from_spec(_tspec)
_tspec.loader.exec_module(_tc_tests)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _sync(tmp_path: Path, source: Path = SHELF, **kw) -> tuple[dict, Path]:
    root = tmp_path / "root"
    rep = sync_languages.sync(source, root, today="2026-11-18", **kw)
    return rep, root / sync_languages.DEST


def _lib(shelf: Path, tmp_path: Path, **kw) -> ll.Library:
    return ll.Library(shelf, tmp_path / "idx" / "library.sqlite", **kw)


PY_PAGES = {
    "library/stdtypes.txt": (
        "Built-in Types\n**************\n\nMade-up words in the shape of the publisher's plain-text build.\n\n\n"
        "4.7. Text Sequence Type --- str\n===============================\n\nStrings are made up here.\n\n"
        "class str(object='')\n\n   Return a made-up string.\n\nstr.splitlines(keepends=False)\n\n"
        "   Return a list of the lines.\n\n      >>> 'a\\nb'.splitlines()\n      ['a', 'b']\n"),
    "library/paths.txt": (
        "\"paths\" --- Made-up paths\n*************************\n\nA made-up module.\n\n\n"
        "Concrete paths\n==============\n\nclass paths.Path(*segments)\n\n   A made-up path.\n\n"
        "   classmethod Path.home()\n\n      Return the made-up home.\n\nformat_spec\n-----------\n\n"
        "A made-up option.\n"),
}


def _make_shelf(root: Path, *, shelf: str = "python", text: str = "docs", version: str = "3.13",
                pages: dict[str, str] = PY_PAGES, more: list[dict] | None = None) -> Path:
    """A made-up shelf written as the fetch script writes one: files/, NOTICE, FETCHED, SHA256SUMS, library.json."""
    d = root / shelf / text / version
    for rel, body in pages.items():
        p = d / "files" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (d / "NOTICE").write_text("A made-up notice for the tests.\n", encoding="utf-8")
    (d / "FETCHED").write_text("fetched: 2026-11-18T12:00:00Z\n", encoding="utf-8")
    (d / "SHA256SUMS").write_text(li.sums_text(d), encoding="utf-8")
    entry = {"shelf": shelf, "text": text, "version": version, "name": "The made-up documentation",
             "publisher": "Nobody", "what": "text", "form": "text", "lane": "open", "aboard": True,
             "licence": {"name": "Made up", "url": "https://example.invalid/licence"},
             "copyright": "Copyright (c) 2026 Nobody. Made up.", "publisher_page": "https://example.invalid/",
             "from": "https://example.invalid/docs.tar.bz2", "obtained": "2026-11-18T12:00:00Z",
             "files": len(li.walk_files(d)), "digest": li.folder_digest(d)}
    reg = {"format": li.FORMAT, "shelves": [{"slug": shelf, "title": shelf.title(), "kind": "language"}],
           "texts": [entry] + (more or [])}
    (root / "library.json").write_text(json.dumps(reg, indent=2), encoding="utf-8")
    return root


def _page_digest(shelf_root: Path, rel: str) -> str:
    return _sha((shelf_root / "python" / "docs" / "3.13" / "files" / rel).read_bytes())


# ---------------------------------------------------------------------------
# the vendored index builder and the fixture shelf
# ---------------------------------------------------------------------------

def test_the_vendored_index_builder_takes_only_the_standard_library():
    tree = ast.parse((REPO / "enough" / "library_index.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "argparse", "hashlib", "html", "json", "os", "re", "sqlite3", "sys", "tempfile",
                    "unicodedata", "dataclasses", "pathlib"}, mods


@pytest.mark.skipif(COSMOES is None, reason="no cosmoes-site checkout beside this repository")
def test_the_vendored_index_builder_is_cosmoes_sites_byte_for_byte():
    assert (REPO / "enough" / "library_index.py").read_bytes() == \
        (COSMOES / "client" / "library_index.py").read_bytes()


@pytest.mark.skipif(COSMOES is None or not (COSMOES / "tests" / "fixtures" / "library").is_dir(),
                    reason="no cosmoes-site checkout with the fixture shelf beside this repository")
def test_the_fixture_shelf_is_cosmoes_sites():
    assert _tree(SHELF) == _tree(COSMOES / "tests" / "fixtures" / "library")


# ---------------------------------------------------------------------------
# the sync
# ---------------------------------------------------------------------------

def test_the_sync_copies_every_kept_text_whole_and_nothing_else(tmp_path):
    rep, dest = _sync(tmp_path)
    assert not rep["refused"]
    assert sorted(rep["added"]) == ["example/manual/1.0", "example/sheet/2", "memos/memo/7",
                                    "reflib/languages/library.json"]
    assert (dest / "library.json").read_bytes() == (SHELF / "library.json").read_bytes()
    for key in ("example/manual/1.0", "example/sheet/2", "memos/memo/7"):
        assert _tree(dest / key) == _tree(SHELF / key)
    assert not (dest / "example" / "runner").exists()                  # a pin is never copied
    reg = json.loads((dest / "library.json").read_text(encoding="utf-8"))
    for e in reg["texts"]:
        if e["aboard"]:
            assert li.verify(li.text_dir(dest, e), e) == []
    synced = json.loads((dest / "synced.json").read_text(encoding="utf-8"))
    assert synced["kept"] == ["example/manual/1.0", "example/sheet/2", "memos/memo/7"]
    assert synced["registry"] == _sha((SHELF / "library.json").read_bytes())
    assert synced["shelf-digest"] == li.source_digest(dest)
    assert rep["index"] == {"path": None, "texts": 4, "kept": 3, "files": 6, "sections": 20}   # proved, not kept


def test_a_rerun_over_an_unchanged_shelf_writes_nothing(tmp_path):
    _, dest = _sync(tmp_path)
    before = {p: p.stat().st_mtime_ns for p in dest.rglob("*")}
    rep, _ = _sync(tmp_path)
    assert (rep["added"], rep["changed"], rep["removed"]) == ([], [], [])
    assert sorted(rep["unchanged"]) == ["example/manual/1.0", "example/sheet/2", "memos/memo/7"]
    assert {p: p.stat().st_mtime_ns for p in dest.rglob("*")} == before


def test_check_reports_and_writes_nothing(tmp_path):
    rep, dest = _sync(tmp_path, check=True)
    assert "example/manual/1.0" in rep["added"] and not dest.exists()
    assert sync_languages.main(["--from", str(SHELF), "--root", str(tmp_path / "root"), "--check"]) == 1
    assert not dest.exists()
    assert sync_languages.main(["--from", str(SHELF), "--root", str(tmp_path / "root")]) == 0
    assert sync_languages.main(["--from", str(SHELF), "--root", str(tmp_path / "root"), "--check"]) == 0


def test_the_sync_refuses_a_folder_whose_checksums_do_not_match_and_writes_nothing(tmp_path, capsys):
    bad = tmp_path / "bad"
    shutil.copytree(SHELF, bad)
    rep, dest = _sync(tmp_path, bad)
    good = _tree(dest)
    f = bad / "example" / "manual" / "1.0" / "files" / "library" / "strings.txt"
    f.write_bytes(f.read_bytes().replace(b"A string holds text.", b"A string holds words."))
    rep, _ = _sync(tmp_path, bad)
    assert list(rep["refused"]) == ["example/manual/1.0"]
    assert rep["refused"]["example/manual/1.0"] == ["files/library/strings.txt does not match its sha256"]
    assert _tree(dest) == good                                            # the copy already here is untouched
    fresh = tmp_path / "fresh"
    assert sync_languages.main(["--from", str(bad), "--root", str(fresh)]) == 1
    assert not (fresh / sync_languages.DEST).exists()                     # all or nothing
    assert "does not match its sha256" in capsys.readouterr().err


def test_the_sync_refuses_a_file_not_listed_and_a_registry_that_does_not_validate(tmp_path):
    bad = tmp_path / "bad"
    shutil.copytree(SHELF, bad)
    (bad / "example" / "sheet" / "2" / "files" / "extra.txt").write_text("not listed\n", encoding="utf-8")
    rep, dest = _sync(tmp_path, bad)
    assert "files/extra.txt is not in SHA256SUMS" in rep["refused"]["example/sheet/2"] and not dest.exists()
    reg = json.loads((SHELF / "library.json").read_text(encoding="utf-8"))
    reg["format"] = "something-else/9"
    bad2 = tmp_path / "bad2"
    shutil.copytree(SHELF, bad2)
    (bad2 / "library.json").write_text(json.dumps(reg), encoding="utf-8")
    rep, _ = _sync(tmp_path, bad2)
    assert rep["refused"]["library.json"] == ["format is not cosmoes-library/1"]


def test_a_text_no_longer_kept_is_removed(tmp_path):
    src = tmp_path / "src"
    shutil.copytree(SHELF, src)
    _, dest = _sync(tmp_path, src)
    reg = json.loads((src / "library.json").read_text(encoding="utf-8"))
    memo = next(e for e in reg["texts"] if e["text"] == "memo")
    memo["aboard"] = False
    (src / "library.json").write_text(json.dumps(reg, indent=2), encoding="utf-8")
    shutil.rmtree(src / "memos")
    rep, _ = _sync(tmp_path, src)
    assert rep["removed"] == ["memos/memo/7"] and "reflib/languages/library.json" in rep["changed"]
    assert not (dest / "memos").exists() and (dest / "example" / "manual" / "1.0").is_dir()


def test_the_sync_from_a_checkout_vendors_the_index_builder(tmp_path):
    cs = tmp_path / "cosmoes-site"
    shutil.copytree(SHELF, cs / "library")
    (cs / "client").mkdir()
    shutil.copyfile(REPO / "enough" / "library_index.py", cs / "client" / "library_index.py")
    rep, dest = _sync(tmp_path, cs)
    root = tmp_path / "root"
    assert (root / "enough" / "library_index.py").read_bytes() == (REPO / "enough" / "library_index.py").read_bytes()
    assert rep["vendored"]["sha256"] == _sha((REPO / "enough" / "library_index.py").read_bytes())
    assert "enough/library_index.py" in rep["added"]
    synced = json.loads((dest / "synced.json").read_text(encoding="utf-8"))
    assert synced["source"] == "cosmoes-site" and synced["index-builder"]["path"] == "enough/library_index.py"
    rep, _ = _sync(tmp_path, cs)
    assert rep["vendored"]["changed"] is False and not rep["changed"]


def test_no_shelf_exits_two(tmp_path):
    assert sync_languages.main(["--from", str(tmp_path), "--root", str(tmp_path / "root")]) == 2


# ---------------------------------------------------------------------------
# the index, from the files alone
# ---------------------------------------------------------------------------

def _rows(db: Path) -> list[tuple]:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT text_id, file, page, path, anchor, heading, kind, level, line_from, line_to, "
                           "sha256, parent FROM sections ORDER BY id").fetchall()
    finally:
        con.close()


def test_the_index_is_rebuilt_from_the_files_alone(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    db = lib.ensure()
    first = _rows(db)
    assert len(first) == 20 and li.is_current(dest, db)
    db.unlink()
    assert lib.rebuild()["sections"] == 20
    assert _rows(db) == first                                             # deterministic, from the files alone
    reg = dest / "library.json"
    reg.write_bytes(reg.read_bytes() + b"\n")                            # the shelf moved: the index is stale
    assert not li.is_current(dest, db)
    lib.ensure()
    assert li.is_current(dest, db) and _rows(db) == first


def test_a_shelf_that_does_not_verify_is_unavailable_not_an_error(tmp_path):
    _, dest = _sync(tmp_path)
    (dest / "example" / "manual" / "1.0" / "files" / "index.txt").write_text("spoiled\n", encoding="utf-8")
    lib = _lib(dest, tmp_path)
    with pytest.raises(ll.LibraryUnavailable):
        lib.ensure()
    c = lib.cite({"in": "example/manual", "version": "1.0", "at": "index", "digest": "0"})
    assert c["state"] == "not-aboard" and "does not verify" in c["why"]


# ---------------------------------------------------------------------------
# finding and resolving a citation
# ---------------------------------------------------------------------------

def test_a_citation_is_found_by_anchor_alias_heading_path_and_page(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    find = lambda at: lib.find({"in": "example/manual", "version": "1.0", "at": at})   # noqa: E731
    h = find("library/strings.html#text.count")
    assert (h.heading, h.by, h.kind, h.page, h.line_from, h.line_to) == \
        ("text.count", "anchor", "sig", "library/strings", 23, 26)
    assert find("library/strings#text.tally").section_id == h.section_id            # an alias on the same lines
    assert find("library/strings#Strings > Making strings").by == "heading path"
    assert find("library/strings#text > text.count").section_id == h.section_id
    p = find("index")
    assert (p.kind, p.by, p.digest) == ("file", "page", _sha((SHELF / "example/manual/1.0/files/index.txt").read_bytes()))
    assert h.section_digest == _sha(li.section_bytes(
        (dest / "example/manual/1.0/files/library/strings.txt").read_bytes(), 23, 26))
    assert find("library/strings#nope") is None and find("nowhere#x") is None
    assert lib.find({"in": "example/sheet", "version": "2", "at": "sheet.html#sec-copyright"}).heading == "Copyright"


def test_digests_decide_resolved_changed_and_the_section_digest_wins(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    h = lib.find({"in": "example/manual", "version": "1.0", "at": "library/strings#text.count"})
    base = {"in": "example/manual", "version": "1.0", "at": "library/strings#text.count"}
    assert tc.resolve_citation({**base, "digest": h.digest[:12]}, lib) == (True, "")
    ok, why = tc.resolve_citation({**base, "digest": "0123456789ab"}, lib)
    assert ok is None and "no section-digest" in why                    # the page moved: cannot be told
    assert tc.resolve_citation({**base, "digest": "0123456789ab", "section-digest": h.section_digest[:12]},
                               lib) == (True, "")                       # ... unless the section did not
    ok, why = tc.resolve_citation({**base, "digest": h.digest[:12], "section-digest": "0123456789ab"}, lib)
    assert ok is False and "section's digest" in why
    # a citation whose id moved still resolves by its section digest
    moved = {"in": "example/manual", "version": "1.0", "at": "library/strings#old-name",
             "digest": h.digest[:12], "section-digest": h.section_digest}
    assert lib.find(moved).by == "section digest"


def test_missing_unplaced_not_aboard_and_unknown(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    ok, why = tc.resolve_citation({"in": "example/manual", "version": "1.0", "at": "library/gone#x", "digest": "a"},
                                  lib)
    assert ok is False and "no page library/gone" in why
    assert lib.cite({"in": "example/manual", "version": "1.0", "at": "library/strings#nope"})["state"] == "unplaced"
    ok, why = tc.resolve_citation({"in": "example/manual", "version": "1.0", "at": "library/strings#nope",
                                   "digest": "a"}, lib)
    assert ok is None and "no such id" in why
    ok, why = tc.resolve_citation({"in": "example/runner", "version": "1", "at": "x", "digest": "a"}, lib)
    assert ok is None and "pinned, not kept" in why
    ok, why = tc.resolve_citation({"in": "python", "version": "3.13.18", "at": "library/stdtypes.html#str",
                                   "digest": "abcdef012345"}, lib)
    assert ok is None and "not in the language library's registry" in why
    shutil.rmtree(dest / "example" / "sheet")                             # aboard in the registry, not here
    assert lib.cite({"in": "example/sheet", "version": "2", "at": "sheet"})["state"] == "not-aboard"
    assert tc.resolve_citation({"in": "python", "version": "3.13.18", "at": "a", "digest": "b"}) == \
        (None, "the language library is not aboard: the citation is carried, not resolved")


def test_cited_as_names_a_text_and_a_version_is_any_patch_of_the_kept_one(tmp_path):
    shelf = _make_shelf(tmp_path / "shelf")
    lib = _lib(shelf, tmp_path)                                           # python -> python/docs/3.13: the catalogue's head
    head = languages.catalogue("python")["texts"][0]
    assert (head["cited-as"], head["shelf"], head["text"], head["version"]) == ("python", "python", "docs", "3.13")
    d = _page_digest(shelf, "library/stdtypes.txt")[:12]
    for v in ("3.13.18", "3.13.0", "3.13"):
        assert tc.resolve_citation({"in": "python", "version": v, "at": "library/stdtypes.html#str.splitlines",
                                    "digest": d}, lib) == (True, "")
    assert lib.cite({"in": "python", "version": "3.12.1", "at": "library/stdtypes.html#str"})["state"] == "unknown"
    assert lib.cite({"in": "python/docs", "version": "3.13.18", "at": "library/stdtypes#str"})["state"] == "resolved"


def test_the_publishers_html_ids_resolve_on_the_plain_text_build(tmp_path):
    """The catalogue cites the HTML build's ids; the plain-text build names the same sections otherwise: a title
    without its number, a definition without its module, `module-<name>` for the module's page."""
    shelf = _make_shelf(tmp_path / "shelf")
    lib = _lib(shelf, tmp_path)
    find = lambda at: lib.find({"in": "python", "version": "3.13.18", "at": at})   # noqa: E731
    assert find("library/stdtypes.html#text-sequence-type-str").heading == "4.7. Text Sequence Type --- str"
    assert find("library/stdtypes.html#text-sequence-type-str").by == "publisher's id"
    h = find("library/paths.html#paths.Path.home")
    assert (h.anchor, h.by) == ("Path.home", "publisher's id")
    assert find("library/paths.html#format-spec").heading == "format_spec"
    m = find("library/paths.html#module-paths")
    assert m.kind == "heading" and m.heading.startswith('"paths"')


# ---------------------------------------------------------------------------
# ground-cited
# ---------------------------------------------------------------------------

def _fabulac(tmp_path: Path, stated: list[dict]) -> Path:
    doc = _tc_tests.mini()
    _tc_tests._node(doc, "C:reliance/text-joins")["stated"] = stated
    return _tc_tests._write(tmp_path, doc)


def _ground_cited(tmp_path: Path, stated: list[dict], lib) -> dict:
    return tc.ready_to_keep(_fabulac(tmp_path, stated), library=lib)["checks"]["ground-cited"]


def test_ground_cited_resolves_against_the_synced_shelf(tmp_path):
    shelf = _make_shelf(tmp_path / "shelf")
    lib = _lib(shelf, tmp_path)
    d = _page_digest(shelf, "library/stdtypes.txt")[:12]
    good = [{"in": "python", "version": "3.13.18", "at": "library/stdtypes.html#str", "digest": d}]
    g = _ground_cited(tmp_path, good, lib)
    assert (g["state"], g["errors"], g["warnings"]) == ("holds", [], [])
    g = _ground_cited(tmp_path, [{**good[0], "at": "library/nothing.html#str"}], lib)
    assert g["state"] == "fails" and "no page library/nothing" in g["errors"][0]
    g = _ground_cited(tmp_path, [{**good[0], "at": "library/stdtypes.html#no-such-id"}], lib)
    assert g["state"] == "holds" and "1 citation(s) carried, not resolved here" in g["warnings"][0]


def test_a_text_not_aboard_is_a_warning_never_an_error(tmp_path):
    _, dest = _sync(tmp_path)                                             # the fixture shelf: no Python on it
    lib = _lib(dest, tmp_path)
    st = [{"in": "python", "version": "3.13.18", "at": "library/stdtypes.html#str", "digest": "abcdef012345"}]
    g = _ground_cited(tmp_path, st, lib)
    assert g["state"] == "holds" and g["errors"] == []
    assert g["warnings"] and "not in the language library's registry" in g["warnings"][0]
    g = _ground_cited(tmp_path, st, None)                                 # no library on this machine: as before
    assert (g["state"], g["warnings"]) == ("holds", [])


def test_the_checks_use_the_library_synced_on_this_machine(tmp_path, monkeypatch):
    shelf = _make_shelf(tmp_path / "shelf")
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(shelf))
    monkeypatch.setenv("ENOUGH_LANGUAGES_ROOT", str(tmp_path / "state"))
    monkeypatch.setattr(ll, "_LOCAL", {})
    assert tc.local_library() is not None
    st = [{"in": "python", "version": "3.13.18", "at": "library/nothing.html#str", "digest": "abcdef012345"}]
    from enough import fabula
    rep = fabula.lint(_fabulac(tmp_path, st))
    assert [p for p in rep.errors if p.check == "ground-cited" and "no page library/nothing" in p.message]
    assert (tmp_path / "state" / "library.sqlite").is_file()             # the index, built in the state root
    monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(tmp_path / "none"))
    assert tc.local_library() is None


@pytest.mark.skipif(not X0_TEXT.is_dir(), reason="the owner's 0.7 copy of the Python 3.13 text is not on this machine")
def test_the_catalogues_citations_resolve_against_the_python_text(tmp_path):
    """The real ground catalogue against the owner's Python 3.13.18 plain-text build, copied into tmp as a kept text
    (never into the repository): every citation finds its page with the cited digest; all but the ids the plain-text
    build does not carry (rst labels, attribute entries) find their section, and those are warnings, not errors."""
    shelf = tmp_path / "shelf"
    d = shelf / "python" / "docs" / "3.13"
    shutil.copytree(X0_TEXT, d / "files")
    (d / "NOTICE").write_text("scratch\n", encoding="utf-8")
    (d / "FETCHED").write_text("scratch\n", encoding="utf-8")
    (d / "SHA256SUMS").write_text(li.sums_text(d), encoding="utf-8")
    head = languages.catalogue("python")["texts"][0]
    e = {k: head[k] for k in ("shelf", "text", "version", "name", "publisher", "what", "form", "lane", "licence")}
    e.update(aboard=True, copyright="scratch", publisher_page="https://docs.python.org/3.13/",
             obtained="2026-11-13T00:51:00Z", files=len(li.walk_files(d)), digest=li.folder_digest(d),
             **{"from": "https://docs.python.org/3.13/archives/python-3.13-docs-text.tar.bz2"})
    (shelf / "library.json").write_text(json.dumps({"format": li.FORMAT, "texts": [e], "shelves": [
        {"slug": "python", "title": "Python", "kind": "language"}]}), encoding="utf-8")
    lib = _lib(shelf, tmp_path)
    states: dict[str, list] = {}
    for ent in languages.entries("python"):
        for st in ent.get("stated") or []:
            if "nowhere" not in st:
                c = lib.cite(st)
                states.setdefault(c["state"], []).append((ent["id"], st["at"]))
                if c["hit"] is not None:
                    assert c["hit"].digest.startswith(st["digest"]), st
    assert set(states) <= {"resolved", "unplaced"}, {k: v for k, v in states.items() if k not in ("resolved",)}
    assert len(states["resolved"]) >= 150 and len(states.get("unplaced", [])) <= 10


# ---------------------------------------------------------------------------
# DocOES
# ---------------------------------------------------------------------------

def test_a_page_is_a_docoes_volume_with_its_notice_first(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    cat = lib.volume("example", "manual", "1.0", "library/strings")
    assert cat["oes"] == "doc/1" and cat["id"] == "doc/library-example-manual-1.0-library.strings"
    notice = cat["nodes"][0]
    assert notice["id"] == "S:section/notice" and notice["summary"] == ll.COPY_LINE
    assert "not the publisher's own page" in notice["body"]
    assert "The Example Licence (made up)" in notice["body"] and "All rights reserved." in notice["body"]
    assert (dest / "example/manual/1.0/NOTICE").read_text(encoding="utf-8") in notice["body"]
    assert cat["document"]["licence"] == {"name": "The Example Licence (made up)", "url": "https://example.invalid/licence"}
    assert cat["document"]["copy"] == ll.COPY_LINE and cat["document"]["changed"] == li.FORMS["text"]["changed"]
    page = (dest / "example/manual/1.0/files/library/strings.txt").read_text(encoding="utf-8")
    assert "".join(n["body"] for n in cat["nodes"][1:]) == page          # bodies verbatim, in the publisher's order
    vol = mc.load_volume_text(docoes.dump(cat), filename="strings.doc.cosm")
    assert not [p for p in vol.problems if p.severity == "error"]
    assert "S:section/text.count" in vol.items and vol.items["S:section/text.count"].data["parent"] == "S:section/text"
    for n in cat["nodes"][1:]:                                            # every section is citable, and cites back
        hit = lib.cite(n["cite"])
        assert hit["state"] == "resolved", n["id"]
        assert hit["hit"].section_digest == n["sha256"]


def test_a_texts_contents_volume_lists_its_pages(tmp_path):
    _, dest = _sync(tmp_path)
    lib = _lib(dest, tmp_path)
    cat = lib.volume("example", "manual", "1.0")
    assert [(n["id"], n["name"]) for n in cat["nodes"]] == [
        ("S:section/notice", "Notice"), ("S:section/p-copyright", "Copyright"),
        ("S:section/p-index", "The Example Manual"), ("S:section/p-library.strings", "Strings"),
        ("S:section/p-license", "The Example Licence")]
    assert not mc.load_volume_text(docoes.dump(cat), filename="manual.doc.cosm").problems
    with pytest.raises(KeyError):
        lib.volume("example", "runner", "1")                              # a pin has no volume
    with pytest.raises(KeyError):
        lib.volume("example", "manual", "1.0", "library/gone")


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from enough import skeleton
    from enough.server import create_app

    def make(shelf: Path | None, mode: str = "home") -> TestClient:
        monkeypatch.setenv("ENOUGH_LANGUAGES_SOURCE", str(shelf if shelf is not None else tmp_path / "no-shelf"))
        monkeypatch.setenv("ENOUGH_LANGUAGES_ROOT", str(tmp_path / "state"))
        monkeypatch.setattr(ll, "_LOCAL", {})
        proj = tmp_path / "project"
        proj.mkdir(exist_ok=True)
        skeleton.ensure_skeleton(proj)
        return TestClient(create_app(proj, "http://127.0.0.1:9", supervise=False, home=(mode == "home")))
    return make


@pytest.mark.parametrize("mode", ["home", "project"])
def test_the_section_route_opens_a_citation_with_its_notice(tmp_path, client, mode):
    _, dest = _sync(tmp_path)
    c = client(dest, mode)
    r = c.get("/api/library/section", params={"in": "example/manual", "version": "1.0",
                                              "at": "library/strings.html#text.count"})
    assert r.status_code == 200
    body = r.json()
    assert (body["state"], body["why"]) == ("resolved", "")
    assert body["cited"] == {"in": "example/manual", "version": "1.0", "at": "library/strings.html#text.count"}
    t = body["text"]
    assert t["copy"] == ll.COPY_LINE and t["licence"]["name"] == "The Example Licence (made up)"
    assert t["copyright"].startswith("Copyright © 2026") and "not the publisher's own page" in t["notice"]
    assert t["changed"] == li.FORMS["text"]["changed"] and t["here"] is True
    s = body["section"]
    assert s["id"] == "S:section/text.count" and s["volume"] == "doc/library-example-manual-1.0-library.strings"
    assert s["body"] == "   text.count(sub)\n   text.tally(sub)\n\n      Count how often *sub* occurs.\n"
    assert s["parent"]["id"] == "S:section/text" and s["lines"] == [23, 26] and s["found_by"] == "anchor"
    r = c.get("/api/library/section", params={"in": "example/manual", "version": "1.0", "at": "index",
                                              "digest": "0123456789ab"})
    assert r.json()["state"] == "changed"
    assert c.get("/api/library/section", params={"in": "x", "version": "1", "at": " "}).status_code == 400


def test_the_routes_without_a_library_say_not_aboard(tmp_path, client):
    c = client(None)
    r = c.get("/api/library/section", params={"in": "python", "version": "3.13.18", "at": "library/stdtypes#str"})
    assert r.status_code == 200 and r.json()["state"] == "not-aboard" and r.json()["section"] is None
    assert c.get("/api/library/status").json()["present"] is False
    assert c.get("/api/library/volume", params={"shelf": "python", "text": "docs", "version": "3.13"}).status_code \
        == 404


def test_the_volume_and_status_routes(tmp_path, client):
    _, dest = _sync(tmp_path)
    c = client(dest)
    st = c.get("/api/library/status").json()
    assert st["present"] is True and st["problems"] == []
    assert {(t["text"], t["here"]) for t in st["texts"]} == {("manual", True), ("runner", False), ("sheet", True),
                                                             ("memo", True)}
    v = c.get("/api/library/volume", params={"shelf": "example", "text": "manual", "version": "1.0",
                                             "page": "library/strings"}).json()
    assert v["nodes"][0]["id"] == "S:section/notice" and v["document"]["copy"] == ll.COPY_LINE
    assert c.get("/api/library/volume", params={"shelf": "example", "text": "runner",
                                                "version": "1"}).status_code == 404
