"""Tests for the cacheawl subsystem: mirror generation (frontmatter +
stable ids), transfer ops incl. traversal rejection, infoworld-migration
idempotence, the path: ingest on a fixture tree, and the mirror-write
refusal on both write paths.

All state goes through ENOUGH_CACHEAWL_ROOT / ENOUGH_INFOWORLD_ROOT
overrides so the real ~/enough install is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enough import cacheawl as ca
from enough import tools


@pytest.fixture
def caroot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point cacheawl at a scratch store, and infoworld at a nonexistent
    scratch path so nothing ever migrates the live install by accident."""
    store = tmp_path / "cacheawl"
    monkeypatch.setenv("ENOUGH_CACHEAWL_ROOT", str(store))
    monkeypatch.setenv("ENOUGH_INFOWORLD_ROOT", str(tmp_path / "no-infoworld"))
    return store


def _wc(name: str, path: str | None = None, content: str | None = None,
        **extra: str) -> tools.ToolCall:
    return tools.ToolCall(
        name=name, path=path, content=content, command=None, url=None,
        extra=extra, raw="", span=(0, 0),
    )


# --------------------------------------------------------------------------
# Mirror generation
# --------------------------------------------------------------------------

def test_mirror_frontmatter_and_stable_ids(caroot: Path):
    ca.create_cachebox("wiki")
    box = ca.box_dir("wiki")
    (box / "a.txt").write_text("hi", encoding="utf-8")
    (box / "sub").mkdir()
    (box / "sub" / "b.md").write_text("yo", encoding="utf-8")
    ca.regenerate_mirror("wiki")

    text = (box / ca.MIRROR_NAME).read_text(encoding="utf-8")
    assert text.startswith("---")
    for key in ("merirmaid: 1", "modality: mirror", "source: cachebox:wiki",
                "title: cachebox: wiki", "generated:"):
        assert key in text, key
    assert "flowchart TD" in text
    # A metadata node with origin/items is present.
    assert "meta[" in text and "items:" in text

    # Node ids are derived from relative paths and stable across regens.
    id_a = ca._node_id("a.txt")
    id_sub = ca._node_id("sub")
    id_b = ca._node_id("sub/b.md")
    for nid in (id_a, id_sub, id_b):
        assert nid in text
    ca.regenerate_mirror("wiki")
    text2 = (box / ca.MIRROR_NAME).read_text(encoding="utf-8")
    for nid in (id_a, id_sub, id_b):
        assert nid in text2
    # The mirror file itself is recognized as a mirror.
    assert ca.is_mirror_file(box / ca.MIRROR_NAME)


def test_reconcile_catches_manual_drop(caroot: Path):
    ca.create_cachebox("box")
    box = ca.box_dir("box")
    # Manual drop the backend didn't perform.
    (box / "surprise.txt").write_text("dropped in", encoding="utf-8")
    assert ca.reconcile("box") is True
    assert ca._node_id("surprise.txt") in (box / ca.MIRROR_NAME).read_text(encoding="utf-8")
    # Second reconcile is a no-op (fingerprint now matches).
    assert ca.reconcile("box") is False


# --------------------------------------------------------------------------
# Transfer ops + traversal protection
# --------------------------------------------------------------------------

def test_transfer_copy_move_and_mirror_refresh(caroot: Path, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "doc.txt").write_text("hello", encoding="utf-8")
    ca.create_cachebox("box")

    ca.transfer(project, op="copy",
                src_kind="project", src_box=None, src_path="doc.txt",
                dst_kind="cachebox", dst_box="box", dst_path="doc.txt")
    assert (ca.box_dir("box") / "doc.txt").read_text(encoding="utf-8") == "hello"
    assert (project / "doc.txt").exists()  # copy leaves the source

    ca.transfer(project, op="move",
                src_kind="cachebox", src_box="box", src_path="doc.txt",
                dst_kind="cachebox", dst_box="box", dst_path="renamed.txt")
    assert not (ca.box_dir("box") / "doc.txt").exists()
    assert (ca.box_dir("box") / "renamed.txt").exists()
    # Mirror reflects the rename.
    mirror = (ca.box_dir("box") / ca.MIRROR_NAME).read_text(encoding="utf-8")
    assert ca._node_id("renamed.txt") in mirror


def test_transfer_rejects_traversal(caroot: Path, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    ca.create_cachebox("box")
    with pytest.raises(ca.CacheawlError):
        ca.transfer(project, op="copy",
                    src_kind="cachebox", src_box="box",
                    src_path="../../../../etc/passwd",
                    dst_kind="project", dst_box=None, dst_path="x")


def test_transfer_refuses_sidecar(caroot: Path, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    ca.create_cachebox("box")
    with pytest.raises(ca.CacheawlError):
        ca.transfer(project, op="move",
                    src_kind="cachebox", src_box="box",
                    src_path=ca.MIRROR_NAME,
                    dst_kind="project", dst_box=None, dst_path="x.merirmaid")


def test_transfer_no_clobber_without_overwrite(caroot: Path, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "doc.txt").write_text("A", encoding="utf-8")
    ca.create_cachebox("box")
    (ca.box_dir("box") / "doc.txt").write_text("B", encoding="utf-8")
    with pytest.raises(ca.CacheawlError):
        ca.transfer(project, op="copy",
                    src_kind="project", src_box=None, src_path="doc.txt",
                    dst_kind="cachebox", dst_box="box", dst_path="doc.txt")


# --------------------------------------------------------------------------
# infoworld → cacheawl migration idempotence
# --------------------------------------------------------------------------

def test_migration_moves_and_is_idempotent(caroot: Path, tmp_path: Path):
    iw = tmp_path / "infoworld"
    for sub in ("personal", "public", "wiki"):
        (iw / sub).mkdir(parents=True)
        (iw / sub / "note.md").write_text(f"{sub} note", encoding="utf-8")

    r1 = ca.migrate_infoworld(iw)
    assert sorted(r1["migrated"]) == ["personal", "public", "wiki"]
    assert (caroot / "wiki" / "note.md").read_text(encoding="utf-8") == "wiki note"
    assert not (iw / "wiki").exists()          # move-only: source gone
    meta = ca.load_meta("wiki")
    assert meta["origin"]["type"] == "infoworld-migration"
    assert (caroot / "wiki" / ca.MIRROR_NAME).is_file()

    # Idempotent: infoworld is gone now, second run is a clean no-op.
    r2 = ca.migrate_infoworld(iw)
    assert r2["migrated"] == []
    assert (caroot / "personal" / "note.md").exists()


def test_migration_skips_existing_box_without_clobber(caroot: Path, tmp_path: Path):
    iw = tmp_path / "infoworld"
    (iw / "wiki").mkdir(parents=True)
    (iw / "wiki" / "orig.md").write_text("original", encoding="utf-8")
    ca.migrate_infoworld(iw)

    # A later infoworld/wiki with new content must NOT overwrite the box.
    (iw / "wiki").mkdir(parents=True)
    (iw / "wiki" / "new.md").write_text("new", encoding="utf-8")
    r = ca.migrate_infoworld(iw)
    assert "wiki" in r["skipped"]
    assert (caroot / "wiki" / "orig.md").exists()
    assert not (caroot / "wiki" / "new.md").exists()


# --------------------------------------------------------------------------
# path: ingest on a fixture tree
# --------------------------------------------------------------------------

@pytest.fixture
def source_tree(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    (src / "a" / "b").mkdir(parents=True)
    (src / "top.txt").write_text("top", encoding="utf-8")
    (src / "a" / "mid.md").write_text("mid", encoding="utf-8")
    (src / "a" / "b" / "deep.py").write_text("print('deep')", encoding="utf-8")
    (src / "pic.png").write_bytes(b"\x89PNG\r\n\x00\x00binary")   # binary ext
    (src / "blob.dat").write_bytes(b"text-ish\x00with null")       # null sniff
    return src


def _rels(box: Path) -> set[str]:
    return {p.relative_to(box).as_posix() for p in ca._content_files(box)}


def test_ingest_path_depth_1(caroot: Path, tmp_path: Path, source_tree: Path):
    project = tmp_path / "proj"
    project.mkdir()
    ca.run_ingest(project, box="d1", source_type="path",
                  value=str(source_tree), depth=1)
    assert _rels(ca.box_dir("d1")) == {"top.txt"}


def test_ingest_path_depth_2(caroot: Path, tmp_path: Path, source_tree: Path):
    project = tmp_path / "proj"
    project.mkdir()
    ca.run_ingest(project, box="d2", source_type="path",
                  value=str(source_tree), depth=2)
    assert _rels(ca.box_dir("d2")) == {"top.txt", "a/mid.md"}


def test_ingest_path_all_skips_binaries(caroot: Path, tmp_path: Path,
                                        source_tree: Path):
    project = tmp_path / "proj"
    project.mkdir()
    summary = ca.run_ingest(project, box="dall", source_type="path",
                            value=str(source_tree), all_flag=True)
    rels = _rels(ca.box_dir("dall"))
    assert rels == {"top.txt", "a/mid.md", "a/b/deep.py"}
    assert "pic.png" not in rels and "blob.dat" not in rels
    meta = ca.load_meta("dall")
    assert meta["status"] == "complete"
    assert meta["origin"] == {"type": "path", "value": str(source_tree), "depth": "all"}
    assert summary["files_written"] == 3


def test_ingest_wikisink_rejects_all(caroot: Path, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(ca.CacheawlError):
        ca.run_ingest(project, box="w", source_type="wikisink",
                      value="Odin", all_flag=True)


# --------------------------------------------------------------------------
# Mirror-write refusal — agent write_file path
# --------------------------------------------------------------------------

def test_write_file_refuses_mirror(caroot: Path, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    ca.create_cachebox("box")
    mirror = ca.box_dir("box") / ca.MIRROR_NAME
    res = tools.run_write_file(project, _wc("write_file", str(mirror), "CLOBBER"))
    assert not res.ok
    assert "modality: mirror" in res.body
    # File is untouched — still a valid mirror.
    assert ca.is_mirror_file(mirror)
    assert "CLOBBER" not in mirror.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# On-demand mirrors: build_mirror node_map + subpath scoping (v0.1.7)
# --------------------------------------------------------------------------

def test_build_mirror_node_map_and_subpath(caroot: Path):
    ca.create_cachebox("box")
    box = ca.box_dir("box")
    (box / "top.txt").write_text("x", encoding="utf-8")
    (box / "sub").mkdir()
    (box / "sub" / "b.md").write_text("y", encoding="utf-8")
    (box / "sub" / "deep").mkdir()
    (box / "sub" / "deep" / "c.md").write_text("z", encoding="utf-8")

    # Box-root mirror: node_map covers every content node with path + type,
    # and every mapped id appears in the rendered source.
    text, nmap = ca.build_mirror("box")
    assert text.startswith("---") and "flowchart TD" in text
    assert nmap["root"] == {"path": "", "is_dir": True}
    assert nmap[ca._node_id("top.txt")] == {"path": "top.txt", "is_dir": False}
    assert nmap[ca._node_id("sub")] == {"path": "sub", "is_dir": True}
    assert nmap[ca._node_id("sub/b.md")] == {"path": "sub/b.md", "is_dir": False}
    for nid in nmap:
        assert nid in text, nid

    # Subfolder mirror: scoped to the subtree; node_map paths stay
    # box-relative; the root node points at the subfolder itself.
    text2, nmap2 = ca.build_mirror("box", "sub")
    assert "source: cachebox:box/sub" in text2
    assert "title: folder: sub" in text2
    assert nmap2["root"] == {"path": "sub", "is_dir": True}
    assert nmap2[ca._node_id("sub/b.md")]["path"] == "sub/b.md"
    # A file outside the subtree is absent from both map and source.
    assert ca._node_id("top.txt") not in nmap2
    assert "top.txt" not in text2

    # On-demand sub-mirrors are NEVER written to disk.
    assert not (box / "sub" / ca.MIRROR_NAME).exists()
    assert list((box / "sub").glob("*.merirmaid")) == []


def test_build_mirror_subpath_validation(caroot: Path):
    ca.create_cachebox("box")
    box = ca.box_dir("box")
    (box / "sub").mkdir()
    (box / "f.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ca.CacheawlError):
        ca.build_mirror("box", "../escape")     # traversal
    with pytest.raises(ca.CacheawlError):
        ca.build_mirror("box", "nope")          # missing folder
    with pytest.raises(ca.CacheawlError):
        ca.build_mirror("box", "f.txt")         # a file, not a folder
    with pytest.raises(ca.CacheawlError):
        ca.build_mirror("nobox")                # missing box
    # Empty / root subpath is valid and equals the box root.
    _text, nmap = ca.build_mirror("box", "")
    assert nmap["root"]["path"] == ""
