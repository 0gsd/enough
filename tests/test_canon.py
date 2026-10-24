"""Canon (0.4.3, was Cacheawl): the store root and its migration, volume
catalogs (`canon.cosm`) and the project catalog (`rness/canon.cosm`), the
listing flags (EMF twins, Holotypes, catalogs, .cosm files), the Holotype
ingest filter, the write-guards, the transfer/broker/wikisink renames and
the `enough.cacheawl` shim.

Every store goes through `ENOUGH_CANON_ROOT` (or, where the test is about
the fallback, `ENOUGH_CACHEAWL_ROOT`/`$HOME` inside tmp_path); conftest
points both seams and `$HOME` at tmp_path before anything here runs.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from enough import broker, canon, macrocosm, tools

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tests" / "fixtures" / "cosm"


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    s = tmp_path / "canon-store"
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(s))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    return s


def _wc(tool: str, path: str | None = None, content: str | None = None,
        **extra: str) -> tools.ToolCall:
    return tools.ToolCall(name=tool, path=path, content=content, command=None,
                          url=None, extra=extra, raw="", span=(0, 0))


def _lint_clean(cat: Path) -> macrocosm.Volume:
    vol = macrocosm.load_volume(cat)
    assert vol.refused is None, vol.refused
    rep = macrocosm.lint(vol)
    assert rep.problems() == [], [str(p) for p in rep.problems()]
    return vol


def _emf_pair(folder: Path, name: str = "notes.md") -> tuple[Path, Path]:
    """The fixture text and its EMF twin, copied under `name`."""
    folder.mkdir(parents=True, exist_ok=True)
    text, twin = folder / name, folder / f"{name}.cosm"
    shutil.copyfile(FIX / "emf" / "notes.md", text)
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", twin)
    return text, twin


# --------------------------------------------------------------------------
# The root: env precedence and the one-time folder rename
# --------------------------------------------------------------------------

def test_canon_root_env_wins_over_the_legacy_one(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENOUGH_CANON_ROOT", str(tmp_path / "new"))
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "old"))
    assert canon.root() == tmp_path / "new"


def test_legacy_env_still_works_when_the_new_one_is_unset(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ENOUGH_CANON_ROOT", raising=False)
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(tmp_path / "legacy-store"))
    assert canon.root() == tmp_path / "legacy-store"
    canon.create_volume("kept")
    assert (tmp_path / "legacy-store" / "kept" / canon.CATALOG_NAME).is_file()


def _no_store_env(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.delenv("ENOUGH_CANON_ROOT", raising=False)
    monkeypatch.delenv("ENOUGH_CACHEAWL_ROOT", raising=False)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    assert Path.home() == home
    return home / "enough"


def test_old_store_folder_is_renamed_once(tmp_path: Path, monkeypatch, caplog):
    base = _no_store_env(monkeypatch, tmp_path)
    (base / "cacheawl" / "notes").mkdir(parents=True)
    (base / "cacheawl" / "notes" / "a.md").write_text("kept", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="enough.canon"):
        r = canon.root()
    assert r == base / "canon"
    assert (base / "canon" / "notes" / "a.md").read_text(encoding="utf-8") == "kept"
    assert not (base / "cacheawl").exists()
    assert not (base / "canon").is_symlink()
    assert any("renamed the store" in m for m in caplog.messages)
    # A second call has nothing left to move.
    assert canon.root() == base / "canon"


def test_both_store_folders_present_uses_canon_and_keeps_both(tmp_path: Path, monkeypatch, caplog):
    base = _no_store_env(monkeypatch, tmp_path)
    (base / "cacheawl" / "old").mkdir(parents=True)
    (base / "canon" / "new").mkdir(parents=True)
    with caplog.at_level(logging.WARNING, logger="enough.canon"):
        r = canon.root()
    assert r == base / "canon"
    assert (base / "cacheawl" / "old").is_dir() and (base / "canon" / "new").is_dir()
    assert not (base / "canon" / "old").exists()           # never merged
    assert any(str(base / "cacheawl") in m and str(base / "canon") in m for m in caplog.messages)


def test_migrate_store_folder_outcomes(tmp_path: Path):
    assert canon.migrate_store_folder(tmp_path / "n", tmp_path / "o") == "none"
    (tmp_path / "o").mkdir()
    assert canon.migrate_store_folder(tmp_path / "n", tmp_path / "o") == "renamed"
    (tmp_path / "o").mkdir()
    assert canon.migrate_store_folder(tmp_path / "n", tmp_path / "o") == "both"


# --------------------------------------------------------------------------
# Sidecars: .canon.json, canon.cosm, and the pre-0.4.3 leftovers
# --------------------------------------------------------------------------

def test_create_writes_meta_and_catalog(store: Path):
    canon.create_volume("notes")
    box = store / "notes"
    assert (box / canon.META_NAME).is_file()
    assert (box / canon.CATALOG_NAME).is_file()
    assert not (box / canon.LEGACY_MIRROR_NAME).exists()
    text = (box / canon.CATALOG_NAME).read_text(encoding="utf-8")
    assert text.startswith("oes: canon/1\n")
    vol = _lint_clean(box / canon.CATALOG_NAME)
    assert vol.minicosm == "canon" and vol.id == "canon/notes"
    assert vol.catalog["counts"] == {"folders": 0, "files": 0, "articles": 0, "twins": 0, "atems": 0}


def test_first_reconcile_migrates_a_pre_canon_volume(store: Path, caplog):
    box = store / "old"
    box.mkdir(parents=True)
    (box / "a.md").write_text("a", encoding="utf-8")
    (box / canon.LEGACY_META_NAME).write_text(json.dumps({
        "name": "old", "origin": {"type": "path", "value": "/x", "depth": 1},
        "status": "complete", "created_at": "2026-01-02T03:04:05Z",
        "updated_at": "2026-01-02T03:04:05Z", "ingest": None, "fingerprint": ""}),
        encoding="utf-8")
    (box / canon.LEGACY_MIRROR_NAME).write_text(
        "---\nmerirmaid: 1\nmodality: mirror\n---\nflowchart TD\n", encoding="utf-8")
    # Readable before any reconcile: the old metadata is read as-is.
    assert canon.load_meta("old")["origin"]["value"] == "/x"
    with caplog.at_level(logging.INFO, logger="enough.canon"):
        assert canon.reconcile("old") is True
    assert not (box / canon.LEGACY_META_NAME).exists()
    assert json.loads((box / canon.META_NAME).read_text())["origin"]["value"] == "/x"
    assert not (box / canon.LEGACY_MIRROR_NAME).exists()
    assert any(canon.LEGACY_MIRROR_NAME in m for m in caplog.messages)
    vol = _lint_clean(box / canon.CATALOG_NAME)
    assert vol.catalog["origin"] == {"type": "path", "value": "/x", "depth": 1}
    assert [it.data["path"] for it in vol.items.values()] == ["a.md"]


def test_a_non_mirror_file_with_the_old_mirror_name_is_kept(store: Path):
    box = store / "keep"
    box.mkdir(parents=True)
    (box / canon.LEGACY_MIRROR_NAME).write_text("flowchart TD\n  a --> b\n", encoding="utf-8")
    canon.reconcile("keep")
    assert (box / canon.LEGACY_MIRROR_NAME).is_file()


def test_catalog_is_byte_stable_and_regenerated_on_drift(store: Path):
    canon.create_volume("stable")
    box = store / "stable"
    (box / "a.md").write_text("a", encoding="utf-8")
    assert canon.reconcile("stable") is True
    cat = box / canon.CATALOG_NAME
    before, mtime = cat.read_bytes(), cat.stat().st_mtime_ns
    assert canon.reconcile("stable") is False
    canon.regenerate_catalog("stable")
    assert cat.read_bytes() == before and cat.stat().st_mtime_ns == mtime
    # A manual drop is drift; so is somebody else's edit of the catalog.
    (box / "b.md").write_text("b", encoding="utf-8")
    assert canon.reconcile("stable") is True
    assert "b.md" in cat.read_text(encoding="utf-8")
    cat.write_text("oes: canon/1\nnodes: []\n", encoding="utf-8")
    assert canon.reconcile("stable") is True
    assert "b.md" in cat.read_text(encoding="utf-8")
    assert canon.reconcile("stable") is False


def test_catalog_items_folders_files_articles_twins_atems(store: Path):
    from enough import convert

    canon.create_volume("meadow handbook")
    box = store / "meadow handbook"
    (box / "README.md").write_text("hello", encoding="utf-8")
    _emf_pair(box / "guides", "close.md")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", box / "guides" / "standalone.cosm")
    # A convert twin, manifest and all, beside its original.
    (box / "guides" / "payroll.docx").write_bytes(b"PK fake docx")
    (box / "guides" / "payroll.docx.md").write_text("# payroll", encoding="utf-8")
    convert.write_manifest(box / "guides" / "payroll.docx", convert.new_manifest(
        box / "guides" / "payroll.docx", engine={"name": "test"}, assets=None))
    art = box / "articles" / "double-entry"
    art.mkdir(parents=True)
    (art / "article.html").write_text("<p>x</p>", encoding="utf-8")
    (art / ".meta.json").write_text(json.dumps({
        "title": "Double-entry bookkeeping",
        "source_url": "https://en.wikipedia.org/wiki/Double-entry_bookkeeping"}), encoding="utf-8")
    shutil.copytree(FIX / "holotypes" / "meadow", box / "meadow")
    canon.regenerate_catalog("meadow handbook")

    vol = _lint_clean(box / canon.CATALOG_NAME)
    assert vol.id == "canon/meadow-handbook" and vol.catalog["scope"] == "volume"
    items = {it.data["path"]: it.data for it in vol.items.values()}
    # Twins are never items.
    assert "guides/close.md.cosm" not in items and "guides/payroll.docx.md" not in items
    close = items["guides/close.md"]
    assert close["id"] == "V:file/guides--close-md" and close["parent"] == "V:folder/guides"
    assert close["emf"] == {"path": "guides/close.md.cosm", "state": "fresh"}
    assert close["atem"]["line"].startswith("The orchard's juice rose")
    assert close["kind"] == "markdown" and close["size"] == (box / "guides/close.md").stat().st_size
    assert items["guides/payroll.docx"]["twin"]["path"] == "guides/payroll.docx.md"
    assert items["guides/payroll.docx"]["twin"]["state"] in ("fresh", "edited", "stale", "conflict")
    assert items["guides/standalone.cosm"]["kind"] == "cosm"
    assert items["articles/double-entry"]["type"] == "article"
    assert items["articles/double-entry"]["title"] == "Double-entry bookkeeping"
    assert items["articles/double-entry"]["source"].startswith("https://en.wikipedia.org/")
    assert "articles/double-entry/article.html" not in items
    meadow = items["meadow"]
    assert meadow["holotype"] is True and "parts" not in meadow
    assert not any(p.startswith("meadow/") for p in items)
    assert items["guides"]["parts"] == [
        "V:file/guides--close-md", "V:file/guides--payroll-docx", "V:file/guides--standalone-cosm"]
    assert vol.catalog["counts"] == {"folders": 3, "files": 4, "articles": 1, "twins": 1, "atems": 1}
    assert "mtime" not in json.dumps(macrocosm.jsonable([it.data for it in vol.items.values()]))
    # Editing the text makes its twin stale in the next catalog.
    (box / "guides" / "close.md").write_text("rewritten", encoding="utf-8")
    canon.reconcile("meadow handbook")
    vol = _lint_clean(box / canon.CATALOG_NAME)
    assert vol.item("V:file/guides--close-md").data["emf"]["state"] == "stale"


def test_short_text_name_rule():
    n = canon.short_text_name
    assert n("notes.short-2026-10-23-1042.md", ["notes.md", "notes.txt"]) == "notes.md"
    assert n("notes.short-2026-10-23-1042-2.md", ["notes.txt"]) == "notes.txt"
    # a text with an EMF twin is the one compiled from, even when it isn't .md
    assert n("notes.short-2026-10-23-1042.md", ["notes.md", "notes.txt"], with_emf={"notes.txt"}) == "notes.txt"
    assert n("rain.short-2026-10-23-1042.md", ["rain.cosm"]) == "rain.cosm"
    assert n("rain.short-2026-10-23-1042.md", ["rain.cosm"], is_standalone=lambda name: False) is None
    assert n("report.pdf.short-2026-10-23-1042.md", ["report.pdf"]) == "report.pdf"
    assert n("notes.v2.short-2026-10-23-1042.md", ["notes.md", "notes.v2.md"]) == "notes.v2.md"
    # not a short's name, or no text beside it
    assert n("notes.short-2026-10-23.md", ["notes.md"]) is None
    assert n("notes-from-emf-2026-10-23-1042.md", ["notes.md"]) is None
    assert n("notes.short-2026-10-23-1042.md", ["other.md"]) is None
    assert n("notes.short-2026-10-23-1042.txt", ["notes.md"]) is None


def test_catalogs_mark_shorts_and_their_texts(store: Path, tmp_path: Path):
    from enough import project_meta, skeleton

    canon.create_volume("orchard")
    box = store / "orchard"
    _emf_pair(box, "notes.md")
    for name in ("notes.short-2026-10-23-1042.md", "notes.short-2026-10-23-1042-2.md",
                 "lonely.short-2026-10-23-1042.md"):
        (box / name).write_text("# a short\n", encoding="utf-8")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", box / "rain.cosm")
    (box / "rain.short-2026-10-23-1100.md").write_text("# a short\n", encoding="utf-8")
    canon.regenerate_catalog("orchard")
    vol = _lint_clean(box / canon.CATALOG_NAME)
    items = {it.data["path"]: it.data for it in vol.items.values()}
    assert items["notes.md"]["shorts"] == ["notes.short-2026-10-23-1042-2.md", "notes.short-2026-10-23-1042.md"]
    assert items["notes.short-2026-10-23-1042.md"]["short_of"] == "notes.md"
    assert items["notes.short-2026-10-23-1042.md"]["kind"] == "markdown", "a short is an ordinary file item"
    assert "short_of" not in items["lonely.short-2026-10-23-1042.md"], "no text beside it: not marked"
    assert items["rain.cosm"]["shorts"] == ["rain.short-2026-10-23-1100.md"]
    assert items["rain.short-2026-10-23-1100.md"]["short_of"] == "rain.cosm"
    assert vol.catalog["counts"]["files"] == 6
    # the project catalog marks them the same way (paths: structure only)
    proj = tmp_path / "proj"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    project_meta.save(proj, "Proj", None)
    _emf_pair(proj / "drafts", "letter.md")
    (proj / "drafts" / "letter.short-2026-10-23-1042.md").write_text("# a short\n", encoding="utf-8")
    canon.project_catalog(proj)
    pitems = {it.data["path"]: it.data for it in _lint_clean(proj / canon.PROJECT_CATALOG).items.values()}
    assert pitems["drafts/letter.md"]["shorts"] == ["drafts/letter.short-2026-10-23-1042.md"]
    assert pitems["drafts/letter.short-2026-10-23-1042.md"]["short_of"] == "drafts/letter.md"


def test_slug_rule():
    assert canon.slug("guides/close.md") == "guides--close-md"
    assert canon.slug("README.md") == "readme-md"
    assert canon.slug(".hidden_") == "hidden"
    assert canon.slug("con").startswith("con-") and len(canon.slug("con")) == 10
    assert canon.slug("con.txt") == "con-txt"          # only the bare name is reserved
    slugs = canon.item_slugs(["a.b", "a-b", "c.md"])
    assert slugs["c.md"] == "c-md"
    assert slugs["a.b"] != slugs["a-b"]
    assert slugs["a.b"].startswith("a-b-") and slugs["a-b"].startswith("a-b-")


def test_catalog_handles_collisions_and_reserved_names(store: Path):
    canon.create_volume("odd")
    box = store / "odd"
    (box / "a.b").write_text("1", encoding="utf-8")
    (box / "a-b").write_text("2", encoding="utf-8")
    (box / "con").mkdir()
    (box / "con" / "x.md").write_text("x", encoding="utf-8")
    canon.regenerate_catalog("odd")
    vol = _lint_clean(box / canon.CATALOG_NAME)
    ids = {it.data["path"]: it.id for it in vol.items.values()}
    assert len(set(ids.values())) == len(ids)
    assert ids["con"].startswith("V:folder/con-")
    for it in vol.items.values():
        assert macrocosm.item_path(vol, it), it.id          # every item has a path


# --------------------------------------------------------------------------
# Listings (_scan_tree)
# --------------------------------------------------------------------------

def _flat(nodes: list[dict]) -> dict[str, dict]:
    out = {}
    for n in nodes:
        out[n["path"]] = n
        out.update(_flat(n.get("children") or []))
    return out


def test_volume_tree_flags(store: Path):
    canon.create_volume("v")
    box = store / "v"
    text, _twin = _emf_pair(box / "docs")
    shutil.copyfile(FIX / "emf" / "standalone.cosm", box / "docs" / "rain.cosm")
    shutil.copytree(FIX / "holotypes" / "meadow", box / "meadow")
    flat = _flat(canon.volume_tree("v")["tree"])
    assert "docs/notes.md.cosm" not in flat
    assert flat["docs/notes.md"]["emf"] == {"path": "docs/notes.md.cosm", "state": "fresh"}
    assert flat["docs/rain.cosm"]["cosm"] is True
    assert flat[canon.CATALOG_NAME]["catalog"] is True and "cosm" not in flat[canon.CATALOG_NAME]
    assert flat["meadow"]["holotype"] is True and flat["meadow"]["children"] == []
    assert all(n["is_mirror"] is False for n in flat.values())
    text.write_text("changed", encoding="utf-8")
    assert _flat(canon.volume_tree("v")["tree"])["docs/notes.md"]["emf"]["state"] == "stale"


def test_a_cosm_beside_a_text_that_is_not_emf_is_not_a_twin(store: Path):
    canon.create_volume("v")
    box = store / "v"
    (box / "plan.md").write_text("plan", encoding="utf-8")
    (box / "plan.md.cosm").write_text("oes: canon/1\nnodes: []\n", encoding="utf-8")
    flat = _flat(canon.volume_tree("v")["tree"])
    assert flat["plan.md.cosm"]["cosm"] is True and "emf" not in flat["plan.md"]


def test_volume_mirror_draws_on_demand_and_hides_kept_files(store: Path):
    canon.create_volume("m")
    box = store / "m"
    _emf_pair(box)
    text, node_map = canon.build_mirror("m")
    assert "source: canon:m\n" in text and "📦 m" in text
    paths = {v["path"] for v in node_map.values()}
    assert "notes.md" in paths
    assert canon.CATALOG_NAME not in paths and "notes.md.cosm" not in paths
    assert not (box / canon.LEGACY_MIRROR_NAME).exists()


# --------------------------------------------------------------------------
# Ingest: a Holotype keeps its private parts
# --------------------------------------------------------------------------

def test_path_ingest_skips_outside_the_model_inside_a_holotype(store: Path, tmp_path: Path):
    src = tmp_path / "src"
    ht = src / "clients" / "meadow"
    shutil.copytree(FIX / "holotypes" / "meadow", ht)
    for rel in ("people.yaml", "people.proposed.yaml", "people.archive.yaml",
                "feeds/bank.txt", "scans/receipt.txt", "bindings/b.yaml",
                "reports/q3.md", "snapshots/2026-10-01/holotype.cosm"):
        (ht / rel).parent.mkdir(parents=True, exist_ok=True)
        (ht / rel).write_text("private", encoding="utf-8")
    (ht / "store.sqlite").write_bytes(b"SQLite format 3\x00")
    (src / "reports").mkdir()
    (src / "reports" / "public.md").write_text("not in a holotype", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    canon.run_ingest(project, box="clients", source_type="path", value=str(src), all_flag=True)
    box = store / "clients"
    rels = {p.relative_to(box).as_posix() for p in canon._content_files(box)}
    assert "clients/meadow/holotype.cosm" in rels
    assert any(r.startswith("clients/meadow/atoms/") for r in rels)
    assert "reports/public.md" in rels                       # only a Holotype's root is filtered
    for gone in ("people.yaml", "people.proposed.yaml", "people.archive.yaml", "feeds",
                 "scans", "bindings", "reports", "snapshots", "store.sqlite"):
        assert not (box / "clients" / "meadow" / gone).exists(), gone
    # The catalog lists the Holotype as one folder.
    vol = _lint_clean(box / canon.CATALOG_NAME)
    meadow = vol.item("V:folder/clients--meadow")
    assert meadow is not None and meadow.data["holotype"] is True


_PRIVATE = ("people.yaml", "people.proposed.yaml", "store.sqlite", "feeds/bank.txt",
            "snapshots/2026-10-01/holotype.cosm", "reports/q3.md")


def _private_holotype(at: Path) -> Path:
    """The meadow Holotype at `at`, with Comprise's private parts dropped in."""
    shutil.copytree(FIX / "holotypes" / "meadow", at)
    for rel in _PRIVATE:
        (at / rel).parent.mkdir(parents=True, exist_ok=True)
        (at / rel).write_bytes(b"private")
    return at


def _assert_filtered(dst: Path) -> None:
    assert (dst / "holotype.cosm").is_file() and (dst / "atoms").is_dir()
    for gone in ("people.yaml", "people.proposed.yaml", "store.sqlite", "feeds", "snapshots", "reports"):
        assert not (dst / gone).exists(), gone


def test_transfer_copy_of_a_holotype_into_the_store_leaves_private_parts_out(store: Path, tmp_path: Path):
    project = tmp_path / "proj"
    src = _private_holotype(project / "clients" / "meadow")
    canon.create_volume("v")
    out = canon.transfer(project, op="copy", src_kind="project", src_box=None,
                         src_path="clients/meadow", dst_kind="canon", dst_box="v", dst_path="meadow")
    _assert_filtered(store / "v" / "meadow")
    assert sorted(out["skipped"]) == sorted([
        "clients/meadow/feeds/", "clients/meadow/people.proposed.yaml", "clients/meadow/people.yaml",
        "clients/meadow/reports/", "clients/meadow/snapshots/", "clients/meadow/store.sqlite"])
    assert "source_kept" not in out
    assert all((src / rel).is_file() for rel in _PRIVATE)              # a copy never touches the source
    # A folder that merely contains a Holotype is filtered the same way.
    out = canon.transfer(project, op="copy", src_kind="project", src_box=None,
                         src_path="clients", dst_kind="canon", dst_box="v", dst_path="clients")
    _assert_filtered(store / "v" / "clients" / "meadow")
    assert "clients/meadow/people.yaml" in out["skipped"]


def test_transfer_move_of_a_holotype_copies_and_keeps_the_source(store: Path, tmp_path: Path):
    project = tmp_path / "proj"
    src = _private_holotype(project / "meadow")
    before = sorted(p.relative_to(src).as_posix() for p in src.rglob("*"))
    canon.create_volume("v")
    out = canon.transfer(project, op="move", src_kind="project", src_box=None, src_path="meadow",
                         dst_kind="canon", dst_box="v", dst_path="meadow")
    _assert_filtered(store / "v" / "meadow")
    assert out["source_kept"] is True and "stayed at the source" in out["note"]
    assert "meadow/people.yaml" in out["skipped"] and "meadow/snapshots/" in out["skipped"]
    assert sorted(p.relative_to(src).as_posix() for p in src.rglob("*")) == before   # nothing deleted
    # store → store: a Holotype dropped into a volume by hand is filtered on the way out too.
    _private_holotype(store / "v" / "dropped")
    canon.create_volume("w")
    out = canon.transfer(project, op="move", src_kind="canon", src_box="v", src_path="dropped",
                         dst_kind="canon", dst_box="w", dst_path="dropped")
    _assert_filtered(store / "w" / "dropped")
    assert out["source_kept"] is True and (store / "v" / "dropped" / "people.yaml").is_file()


def test_transfer_refuses_a_private_part_on_its_own(store: Path, tmp_path: Path):
    project = tmp_path / "proj"
    _private_holotype(project / "meadow")
    canon.create_volume("v")
    for rel in ("meadow/people.yaml", "meadow/store.sqlite", "meadow/feeds", "meadow/feeds/bank.txt",
                "meadow/snapshots/2026-10-01"):
        for op in ("copy", "move"):
            with pytest.raises(canon.CanonError, match="never leave"):
                canon.transfer(project, op=op, src_kind="project", src_box=None, src_path=rel,
                               dst_kind="canon", dst_box="v", dst_path="x")
        assert (project / rel).exists()
    # The rest of a Holotype moves freely.
    out = canon.transfer(project, op="copy", src_kind="project", src_box=None, src_path="meadow/atoms",
                         dst_kind="canon", dst_box="v", dst_path="atoms")
    assert out["skipped"] == [] and (store / "v" / "atoms").is_dir()
    # …and the path ingest refuses a private folder as its source as well.
    with pytest.raises(canon.CanonError, match="never leave"):
        canon.run_ingest(project, box="feeds", source_type="path",
                         value=str(project / "meadow" / "feeds"), all_flag=True)


def test_transfer_of_a_plain_folder_is_unaffected(store: Path, tmp_path: Path):
    project = tmp_path / "proj"
    plain = project / "notes"
    for rel in ("people.yaml", "reports/q3.md", "store.sqlite", "a.md"):
        (plain / rel).parent.mkdir(parents=True, exist_ok=True)
        (plain / rel).write_text("mine", encoding="utf-8")
    canon.create_volume("v")
    out = canon.transfer(project, op="move", src_kind="project", src_box=None, src_path="notes",
                         dst_kind="canon", dst_box="v", dst_path="notes")
    assert out["skipped"] == [] and "source_kept" not in out
    assert not plain.exists()                                         # a real move
    for rel in ("people.yaml", "reports/q3.md", "store.sqlite", "a.md"):
        assert (store / "v" / "notes" / rel).is_file(), rel
    # A Holotype with nothing private in it moves normally too.
    shutil.copytree(FIX / "holotypes" / "meadow", project / "clean")
    out = canon.transfer(project, op="move", src_kind="project", src_box=None, src_path="clean",
                         dst_kind="canon", dst_box="v", dst_path="clean")
    assert out["skipped"] == [] and not (project / "clean").exists()


# --------------------------------------------------------------------------
# Write guards
# --------------------------------------------------------------------------

def test_catalog_write_denial_covers_every_kept_file(store: Path, tmp_path: Path):
    canon.create_volume("g")
    box = store / "g"
    project = tmp_path / "proj"
    (project / "rness").mkdir(parents=True)
    lead = "error: this catalog is kept by enough; change the files it lists instead"
    for target in (box / canon.CATALOG_NAME, box / canon.META_NAME, box / canon.LEGACY_META_NAME,
                   box / canon.LEGACY_MIRROR_NAME, project / "rness" / "canon.cosm"):
        why = canon.catalog_write_denial(target, project)
        assert why and why.startswith(lead), target
        assert canon.is_catalog_file(target, project)
    assert canon.catalog_write_denial(box / "notes.md", project) is None
    assert canon.catalog_write_denial(box / "sub" / canon.CATALOG_NAME, project) is None
    assert canon.catalog_write_denial(project / "canon.cosm", project) is None
    assert "modality: mirror" in canon.catalog_write_denial(box / canon.LEGACY_MIRROR_NAME)


def test_agent_write_file_refuses_both_catalogs(store: Path, tmp_path: Path):
    canon.create_volume("w")
    project = tmp_path / "proj"
    (project / "rness").mkdir(parents=True)
    res = tools.run_write_file(project, _wc("write_file", "rness/canon.cosm", "CLOBBER"))
    assert not res.ok and "kept by enough" in res.body
    assert not (project / "rness" / "canon.cosm").exists()
    cat = store / "w" / canon.CATALOG_NAME
    before = cat.read_text(encoding="utf-8")
    res = tools.run_write_file(project, _wc("write_file", str(cat), "CLOBBER"))
    assert not res.ok and "kept by enough" in res.body
    assert cat.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# Transfer, broker, wikisink, the shim
# --------------------------------------------------------------------------

def test_transfer_accepts_canon_and_legacy_cachebox_sides(store: Path, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "doc.md").write_text("doc", encoding="utf-8")
    canon.create_volume("t")
    out = canon.transfer(project, op="copy", src_kind="project", src_box=None, src_path="doc.md",
                         dst_kind="canon", dst_box="t", dst_path="doc.md")
    assert out["volumes_updated"] == ["t"] == out["boxes_updated"]
    canon.transfer(project, op="copy", src_kind="cachebox", src_box="t", src_path="doc.md",
                   dst_kind="project", dst_box=None, dst_path="back.md")
    assert (project / "back.md").read_text(encoding="utf-8") == "doc"
    assert "doc.md" in (store / "t" / canon.CATALOG_NAME).read_text(encoding="utf-8")
    with pytest.raises(canon.CanonError):
        canon.transfer(project, op="move", src_kind="canon", src_box="t",
                       src_path=canon.CATALOG_NAME, dst_kind="project", dst_box=None, dst_path="x")


def test_broker_moves_a_stored_cacheawl_toggle_once(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "broker.json"
    monkeypatch.setattr(broker, "CONFIG_PATH", cfg)
    cfg.write_text(json.dumps({"cacheawl_enabled": False}), encoding="utf-8")
    assert broker.load_config()["canon_enabled"] is False
    on_disk = json.loads(cfg.read_text(encoding="utf-8"))
    assert on_disk["canon_enabled"] is False and "cacheawl_enabled" not in on_disk
    assert broker.is_enabled("canon_enabled") is False
    assert "canon tools" in broker.denial_canon_disabled()
    toggle = next(t for t in broker.TOGGLES if t.key == "canon_enabled")
    assert (toggle.label, toggle.group) == ("canon tools", "canon")


def test_canon_tools_are_gated_and_named(store: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(broker, "CONFIG_PATH", tmp_path / "broker.json")
    project = tmp_path / "proj"
    project.mkdir()
    assert {"canon_list", "canon_create", "canon_ingest"} <= set(tools._DISPATCH)
    assert not any(n.startswith("cachebox_") for n in tools._DISPATCH)
    res = tools.run_canon_create(project, _wc("canon_create", name="notes"))
    assert res.ok and (store / "notes" / canon.CATALOG_NAME).is_file()
    res = tools.run_canon_list(project, _wc("canon_list", volume="notes"))
    assert res.ok and "volume 'notes'" in res.body
    res = tools.run_canon_list(project, _wc("canon_list", box="notes"))   # the old tag
    assert res.ok
    broker.save_config({**broker.load_config(), "canon_enabled": False})
    res = tools.run_canon_list(project, _wc("canon_list"))
    assert not res.ok and "canon tools are disabled" in res.body


def test_wikisink_saved_dir_resolves_both_prefixes(store: Path, tmp_path: Path):
    from enough.wikisink import save as wsave

    art = store / "wiki" / "odin"
    art.mkdir(parents=True)
    (art / "article.html").write_text("<p>Odin</p>", encoding="utf-8")
    (art / ".meta.json").write_text("{}", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    for ref in ("canon:wiki/odin/article.html", "cacheawl:wiki/odin/article.html"):
        assert wsave._resolve_saved_dir(project, ref) == art.resolve()
    with pytest.raises(ValueError):
        wsave._resolve_saved_dir(project, "canon:../etc")


def test_the_cacheawl_shim_re_exports_every_old_name():
    from enough import cacheawl

    assert cacheawl.CacheawlError is canon.CanonError
    pairs = {
        "box_dir": canon.volume_dir, "regenerate_mirror": canon.regenerate_catalog,
        "is_mirror_file": canon.is_catalog_file, "mirror_write_denial": canon.catalog_write_denial,
        "cachebox_summary": canon.volume_summary, "list_cacheboxes": canon.list_volumes,
        "cachebox_tree": canon.volume_tree, "create_cachebox": canon.create_volume,
        "rename_cachebox": canon.rename_volume, "delete_cachebox": canon.delete_volume,
    }
    for old, new in pairs.items():
        assert getattr(cacheawl, old) is new, old
    for same in ("root", "load_meta", "save_meta", "folder_flowchart", "build_mirror", "transfer",
                 "reconcile", "reconcile_all", "ingest_status", "register_ingest", "run_ingest",
                 "posix_dirname", "migrate_infoworld"):
        assert getattr(cacheawl, same) is getattr(canon, same), same
    assert cacheawl.META_NAME == ".canon.json" and cacheawl.MIRROR_NAME == "_cachebox.merirmaid"
    assert set(cacheawl.__all__) <= set(dir(cacheawl))


# --------------------------------------------------------------------------
# The project catalog (rness/canon.cosm)
# --------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path: Path, store: Path) -> Path:
    from enough import project_meta, skeleton

    proj = tmp_path / "field notes"
    proj.mkdir()
    skeleton.ensure_skeleton(proj)
    project_meta.save(proj, "Field Notes", None)
    assert str(Path.home()).startswith(str(tmp_path))
    return proj


def _project_items(proj: Path) -> dict[str, dict]:
    vol = _lint_clean(proj / canon.PROJECT_CATALOG)
    assert vol.catalog["scope"] == "project" and vol.id.startswith("canon/~")
    return {it.data["path"]: it.data for it in vol.items.values()}


def test_project_catalog_enumerates_what_the_sidebar_shows(project: Path):
    from enough import convert

    (project / "README.md").write_text("hi", encoding="utf-8")
    _emf_pair(project / "drafts", "orchard.md")
    (project / "drafts" / "letter.docx").write_bytes(b"PK fake")
    (project / "drafts" / "letter.docx.md").write_text("# letter", encoding="utf-8")
    convert.write_manifest(project / "drafts" / "letter.docx", convert.new_manifest(
        project / "drafts" / "letter.docx", engine={"name": "test"}, assets=None))
    shutil.copytree(FIX / "holotypes" / "meadow", project / "research" / "meadow")
    (project / ".hidden.md").write_text("no", encoding="utf-8")
    text = canon.project_catalog(project)
    assert (project / canon.PROJECT_CATALOG).read_text(encoding="utf-8") == text
    assert "\nid: canon/~field-notes\nname: Field Notes\nscope: project\n" in text
    items = _project_items(project)
    assert not any(p == "rness" or p.startswith("rness/") for p in items)
    assert "drafts/orchard.md.cosm" not in items and "drafts/letter.docx.md" not in items
    assert ".hidden.md" not in items
    assert items["drafts/orchard.md"]["emf"] == {"path": "drafts/orchard.md.cosm"}   # no state
    assert items["drafts/orchard.md"]["atem"]["line"]
    assert items["drafts/letter.docx"]["twin"] == {"path": "drafts/letter.docx.md"}
    assert items["research/meadow"]["holotype"] is True
    assert not any(p.startswith("research/meadow/") for p in items)
    for it in items.values():
        assert "size" not in it and "mtime" not in it
    for key in ("created", "updated", "origin", "status"):
        assert f"\n{key}:" not in text


def test_project_catalog_is_byte_stable_and_moves_only_with_the_file_list(project: Path):
    (project / "plan.md").write_text("one", encoding="utf-8")
    _emf_pair(project, "notes.md")
    canon.project_catalog(project)
    cat = project / canon.PROJECT_CATALOG
    before, mtime = cat.read_bytes(), cat.stat().st_mtime_ns
    canon.project_catalog(project)
    assert cat.stat().st_mtime_ns == mtime                    # nothing rewritten
    (project / "plan.md").write_text("two, longer", encoding="utf-8")
    (project / "notes.md").write_text("an edit to a twinned text", encoding="utf-8")
    canon.project_catalog(project)
    assert cat.read_bytes() == before and cat.stat().st_mtime_ns == mtime
    (project / "new.md").write_text("new", encoding="utf-8")
    canon.project_catalog(project)
    assert cat.read_bytes() != before and "new.md" in cat.read_text(encoding="utf-8")


def test_project_catalog_without_write_writes_nothing(project: Path):
    text = canon.project_catalog(project, write=False)
    assert text.startswith("oes: canon/1\n")
    assert not (project / canon.PROJECT_CATALOG).exists()


def test_project_catalog_cap_lists_big_folders_without_contents(project: Path):
    (project / "README.md").write_text("hi", encoding="utf-8")
    (project / "small").mkdir()
    (project / "small" / "a.md").write_text("a", encoding="utf-8")
    big = project / "archive"
    (big / "deep").mkdir(parents=True)
    for i in range(canon.CATALOG_ITEM_CAP + 5):
        (big / f"f{i:05d}.txt").write_bytes(b"")
    (big / "deep" / "x.txt").write_bytes(b"")
    canon.project_catalog(project)
    items = _project_items(project)
    archive = items["archive"]
    assert archive["pending"] == canon.CATALOG_PENDING
    assert archive["counts"] == {"folders": 1, "files": canon.CATALOG_ITEM_CAP + 6}
    assert "parts" not in archive
    assert not any(p.startswith("archive/") for p in items)
    assert "README.md" in items and "small/a.md" in items


def test_project_catalog_cap_is_the_module_constant(project: Path, monkeypatch):
    monkeypatch.setattr(canon, "CATALOG_ITEM_CAP", 3)
    for d in ("a", "b"):
        (project / d).mkdir()
        for i in range(3):
            (project / d / f"{i}.md").write_text("x", encoding="utf-8")
    canon.project_catalog(project)
    items = _project_items(project)
    assert items["a"]["pending"] and items["b"]["pending"]
    assert items["a"]["counts"] == {"folders": 0, "files": 3}


def test_the_home_mirror_hides_emf_twins_too(project: Path):
    from enough import home

    _emf_pair(project)
    text = home.build_project_mirror(project)
    assert "📄 notes.md\"" in text and "notes.md.cosm" not in text


def test_a_failed_path_ingest_records_its_reason(store: Path, tmp_path: Path):
    # 0.4.4: a CanonError's sentence lands in ingest-status, so the UI's toast can say why.
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(canon.CanonError, match="does not exist"):
        canon.run_ingest(project, box="gone", source_type="path",
                         value=str(tmp_path / "nowhere"), all_flag=True)
    st = canon.ingest_status("gone")
    assert st["status"] == "failed"
    assert "does not exist" in (st["ingest"] or {}).get("error", "")


def test_a_relative_ingest_path_is_relative_to_the_project(store: Path, tmp_path: Path, monkeypatch):
    # 0.4.4: never the server's cwd — the project folder is the one the person can see.
    project = tmp_path / "proj"
    (project / "readings").mkdir(parents=True)
    (project / "readings" / "a.md").write_text("from the project", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "readings").mkdir(parents=True)
    (elsewhere / "readings" / "b.md").write_text("from the cwd", encoding="utf-8")
    monkeypatch.chdir(elsewhere)
    canon.run_ingest(project, box="rel", source_type="path", value="readings", all_flag=True)
    rels = {p.relative_to(store / "rel").as_posix() for p in canon._content_files(store / "rel")}
    assert any(r.endswith("a.md") for r in rels) and not any(r.endswith("b.md") for r in rels)
