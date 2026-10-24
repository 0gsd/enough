"""scripts/sync_cosm.py: Comprise's manifest and public samples, copied into enough by an allowlist.

Runs against a tiny fake Comprise checkout built in tmp_path (CI has no comprise-dev): the allowlist is honoured,
people files, the local database and everything outside the model stay behind, `--check` reports without writing,
and a rerun is byte-stable. One test also checks the shipped copies against their own manifest.json.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_cosm", REPO / "scripts" / "sync_cosm.py")
sync_cosm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_cosm)


def _put(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    """A Comprise checkout in miniature: the manifest, one allowlisted sample with everything a real Holotype keeps
    beside its model, one sample that is not on the allowlist, and the COSM 0.2 example tree."""
    c = tmp_path / "comprise"
    _put(c, "oes/comprise-oes.manifest.cosm", "manifest: minicosm/0\nname: comprise\nversion: 1\n")
    m = "fixtures/meadow"
    _put(c, f"{m}/holotype.cosm", "oes: comprise/1\nid: holotype/meadow\natoms: [atom/meadow]\n")
    _put(c, f"{m}/atoms/meadow/C/entity.cosm", "nodes: []\n")
    _put(c, f"{m}/atoms/meadow/R/reflections/press.cosm", "nodes: []\n")
    _put(c, f"{m}/atoms/meadow/E/README", "people live only in the store\n")
    _put(c, f"{m}/atoms/meadow/.DS_Store", "junk")
    _put(c, f"{m}/atoms/meadow/P/notes.txt", "not a model file\n")
    _put(c, f"{m}/people.yaml", "people: [a person]\n")
    _put(c, f"{m}/people.proposed.yaml", "people: [another]\n")
    _put(c, f"{m}/atoms/meadow/E/people.cosm", "people: [never]\n")
    _put(c, f"{m}/store.sqlite", "sqlite")
    _put(c, f"{m}/scans/replay/home.html", "<html>")
    _put(c, f"{m}/feeds/x/runs/1.json", "{}")
    _put(c, f"{m}/snapshots/2026/manifest.yaml", "x: 1\n")
    _put(c, f"{m}/vendors/stripe.com/payments/atom.cosm", "id: vendor/stripe.com/payments\n")
    _put(c, f"{m}/logo.svg", "<svg/>")
    _put(c, "fixtures/secret-client/holotype.cosm", "oes: comprise/1\nid: holotype/secret-client\n")
    _put(c, "fixtures/secret-client/atoms/secret-client/C/entity.cosm", "nodes: []\n")
    ex = "core/vendor/comprise-oes/examples/meadow"
    for name in ("firm.cosm", "nodes.cosm", "doc.cosm", "meadow.sketch", "README.md", "extra.txt"):
        _put(c, f"{ex}/{name}", f"# {name}\n")
    _put(c, "oes/comprise-oes.md", "# Comprise OES 1\n\n## 1. The map\n")
    _put(c, "oes/README.md", "# OES: the paradigm map\n")
    _put(c, "oes/notes.md", "not a chapter\n")
    return c


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_sync_copies_the_allowlist_and_nothing_else(fake, tmp_path):
    out = tmp_path / "repo"
    report = sync_cosm.sync(fake, out)
    expected = {
        "defaults/cosm/manifests/comprise.manifest.cosm",
        "tests/fixtures/cosm/holotypes/meadow/holotype.cosm",
        "tests/fixtures/cosm/holotypes/meadow/atoms/meadow/C/entity.cosm",
        "tests/fixtures/cosm/holotypes/meadow/atoms/meadow/R/reflections/press.cosm",
        "tests/fixtures/cosm/holotypes/meadow/atoms/meadow/E/README",
        "tests/fixtures/cosm/cosm02/meadow/firm.cosm",
        "tests/fixtures/cosm/cosm02/meadow/nodes.cosm",
        "tests/fixtures/cosm/cosm02/meadow/doc.cosm",
        "tests/fixtures/cosm/cosm02/meadow/meadow.sketch",
        "tests/fixtures/cosm/cosm02/meadow/README.md",
        "tests/fixtures/cosm/manifest.json",
        "defaults/cosm/chapters/comprise-oes.md",
        "defaults/cosm/chapters/comprise-paradigm-map.md",
        "defaults/cosm/chapters/manifest.json",
    }
    assert _files(out) == expected
    assert sorted(report["added"]) == sorted(expected)
    assert report["changed"] == report["removed"] == []
    text = "".join((out / rel).read_text(encoding="utf-8") for rel in expected)
    assert "secret-client" not in text and "people: [" not in text
    assert (out / "defaults/cosm/manifests/comprise.manifest.cosm").read_bytes() == \
        (fake / "oes/comprise-oes.manifest.cosm").read_bytes()
    assert (out / "defaults/cosm/chapters/comprise-oes.md").read_bytes() == (fake / "oes/comprise-oes.md").read_bytes()
    assert (out / "defaults/cosm/chapters/comprise-paradigm-map.md").read_bytes() == \
        (fake / "oes/README.md").read_bytes()


def test_the_chapters_carry_their_source_and_hash(fake, tmp_path):
    """The chapters' manifest.json is what the doc volume's chapter provenance reads: the source path, the commit,
    and each copy's sha256; no timestamps, so a rerun is byte-stable."""
    out = tmp_path / "repo"
    sync_cosm.sync(fake, out)
    body = json.loads((out / "defaults/cosm/chapters/manifest.json").read_text(encoding="utf-8"))
    assert set(body) == {"source", "source_commit", "chapters"} and body["source"] == "comprise-dev"
    assert body["chapters"] == {
        "comprise-oes.md": {"source": "oes/comprise-oes.md",
                            "sha256": hashlib.sha256((fake / "oes/comprise-oes.md").read_bytes()).hexdigest()},
        "comprise-paradigm-map.md": {"source": "oes/README.md",
                                     "sha256": hashlib.sha256((fake / "oes/README.md").read_bytes()).hexdigest()}}
    before = (out / "defaults/cosm/chapters/manifest.json").read_bytes()
    assert sync_cosm.sync(fake, out)["changed"] == []
    assert (out / "defaults/cosm/chapters/manifest.json").read_bytes() == before


def test_manifest_json_records_every_copy(fake, tmp_path):
    out = tmp_path / "repo"
    sync_cosm.sync(fake, out)
    body = json.loads((out / "tests/fixtures/cosm/manifest.json").read_text(encoding="utf-8"))
    assert set(body) == {"source_commit", "files", "digest"}
    assert list(body["files"]) == sorted(body["files"])
    for rel, sha in body["files"].items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == sha
    lines = "".join(f"{rel} {sha}\n" for rel, sha in body["files"].items())
    assert body["digest"] == hashlib.sha256(lines.encode("utf-8")).hexdigest()


def test_rerun_is_byte_stable_and_check_writes_nothing(fake, tmp_path, capsys):
    out = tmp_path / "repo"
    sync_cosm.sync(fake, out)
    before = {rel: ((out / rel).read_bytes(), (out / rel).stat().st_mtime_ns) for rel in _files(out)}
    again = sync_cosm.sync(fake, out)
    assert again["added"] == again["changed"] == again["removed"] == []
    assert {rel: ((out / rel).read_bytes(), (out / rel).stat().st_mtime_ns) for rel in _files(out)} == before
    assert sync_cosm.main(["--comprise", str(fake), "--root", str(out), "--check"]) == 0

    _put(fake, "fixtures/meadow/atoms/meadow/C/entity.cosm", "nodes: [{id: C:entity/x}]\n")
    _put(fake, "fixtures/meadow/atoms/meadow/O/roles.cosm", "nodes: []\n")
    (fake / "fixtures/meadow/atoms/meadow/R/reflections/press.cosm").unlink()
    capsys.readouterr()
    assert sync_cosm.main(["--comprise", str(fake), "--root", str(out), "--check"]) == 1
    said = capsys.readouterr().out
    assert "changed  tests/fixtures/cosm/holotypes/meadow/atoms/meadow/C/entity.cosm" in said
    assert "added    tests/fixtures/cosm/holotypes/meadow/atoms/meadow/O/roles.cosm" in said
    assert "removed  tests/fixtures/cosm/holotypes/meadow/atoms/meadow/R/reflections/press.cosm" in said
    assert {rel: (out / rel).read_bytes() for rel in _files(out)} == {rel: b for rel, (b, _) in before.items()}

    assert sync_cosm.main(["--comprise", str(fake), "--root", str(out)]) == 0
    assert (out / "tests/fixtures/cosm/holotypes/meadow/atoms/meadow/C/entity.cosm").read_text() == \
        "nodes: [{id: C:entity/x}]\n"
    assert not (out / "tests/fixtures/cosm/holotypes/meadow/atoms/meadow/R").exists()     # emptied folders go too
    assert sync_cosm.main(["--comprise", str(fake), "--root", str(out), "--check"]) == 0


def test_files_with_no_source_are_removed_but_own_files_stay(fake, tmp_path):
    out = tmp_path / "repo"
    sync_cosm.sync(fake, out)
    _put(out, "tests/fixtures/cosm/holotypes/stray/holotype.cosm", "oes: comprise/1\n")
    _put(out, "tests/fixtures/cosm/NOTICE.md", "hand-written\n")
    _put(out, "tests/fixtures/cosm/emf/notes.md", "ours\n")
    report = sync_cosm.sync(fake, out)
    assert report["removed"] == ["tests/fixtures/cosm/holotypes/stray/holotype.cosm"]
    assert not (out / "tests/fixtures/cosm/holotypes/stray").exists()
    assert (out / "tests/fixtures/cosm/NOTICE.md").read_text() == "hand-written\n"
    assert (out / "tests/fixtures/cosm/emf/notes.md").read_text() == "ours\n"


def test_no_comprise_checkout(tmp_path, capsys):
    assert sync_cosm.main(["--comprise", str(tmp_path / "nowhere"), "--root", str(tmp_path / "repo")]) == 2
    assert "no Comprise checkout" in capsys.readouterr().err
    assert not (tmp_path / "repo").exists()


def test_the_allowlist_is_the_four_public_samples():
    assert sync_cosm.HOLOTYPES == ("meadow", "mozilla", "wikimedia", "khan-academy")


def test_the_shipped_copies_match_their_manifest():
    body = json.loads((REPO / sync_cosm.MANIFEST_JSON).read_text(encoding="utf-8"))
    for rel, sha in body["files"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == sha, f"{rel} was edited by hand: rerun the sync"
    chapters = json.loads((REPO / sync_cosm.CHAPTERS_JSON).read_text(encoding="utf-8"))
    assert chapters["source_commit"] == body["source_commit"]
    assert set(chapters["chapters"]) == set(sync_cosm.CHAPTERS.values())
    for dest, entry in chapters["chapters"].items():
        rel = f"{sync_cosm.CHAPTERS_DEST}/{dest}"
        assert body["files"][rel] == entry["sha256"] == hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
    assert set(sync_cosm._existing(REPO)) == {rel for rel in body["files"] if not rel.startswith("defaults/")}
    holotypes = {rel.split("/")[4] for rel in body["files"] if rel.startswith(sync_cosm.HOLOTYPES_DEST)}
    assert holotypes == set(sync_cosm.HOLOTYPES)


def test_nothing_shipped_names_a_sample_off_the_allowlist():
    """When a Comprise checkout is beside this one, every fixture folder it has that is not on the allowlist is a
    name that must appear in nothing this round wrote. Skipped where there is no checkout (CI)."""
    fixtures = sync_cosm.DEFAULT_COMPRISE / "fixtures"
    if not fixtures.is_dir():
        pytest.skip("no comprise-dev checkout beside this repo")
    others = {d.name.lower() for d in fixtures.iterdir() if d.is_dir() and not d.name.startswith(".")} \
        - set(sync_cosm.HOLOTYPES)
    assert others, "expected Comprise to hold fixtures beyond the public four"
    roots = [REPO / "tests" / "fixtures" / "cosm", REPO / "defaults" / "cosm", REPO / "scripts" / "sync_cosm.py",
             REPO / "enough" / "macrocosm.py", REPO / "tests" / "test_macrocosm.py", Path(__file__)]
    for root in roots:
        for p in ([root] if root.is_file() else [q for q in root.rglob("*") if q.is_file()]):
            text = p.read_bytes().decode("utf-8", "replace").lower()
            hits = [name for name in others if name in text or name in p.as_posix().lower()]
            assert not hits, f"{p.relative_to(REPO)} names a Comprise fixture that is not public"
