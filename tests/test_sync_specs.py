"""scripts/sync_specs.py: the OES specifications and their sync client, pulled from a cosmoes-site checkout.

Runs against a tiny fake cosmoes-site checkout built in tmp_path (CI has no cosmoes-site): the four documents land at
their bundled paths byte for byte, the client is vendored unchanged, docs/specs.json carries the registry's entries
with each copy's sha256, `--check` reports without writing, and a rerun is byte-stable. Two tests check the shipped
copies against docs/specs.json, and against the real checkout when one is beside this repository.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_specs", REPO / "scripts" / "sync_specs.py")
sync_specs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_specs)

REGISTRY = [
    {"slug": "oes", "file": "oes.md", "name": "The OES specifications", "edition": "0.5.4", "describes": {},
     "host": "cosmoes.org", "revised": "2026-11-03"},
    {"slug": "macrocosm-oes", "file": "macrocosm-oes.md", "name": "MacroCOSM OES", "edition": "0.5.4",
     "describes": {"macrocosm": "0.5.4"}, "host": "macro.cosmoes.org", "revised": "2026-11-03", "reference": True},
    {"slug": "thym", "file": "thym.md", "name": "Thym", "edition": "0.5.4", "describes": {"thym": "1"},
     "host": "thym.cosmoes.org", "revised": "2026-11-03"},
    {"slug": "ascribe", "file": "ascribe.md", "name": "Ascribe", "edition": "0.5.4", "describes": {"ascribe": "1"},
     "host": "ascribe.cosmoes.org", "revised": "2026-11-03"},
    {"slug": "comprise-oes", "file": "comprise-oes.md", "name": "Comprise OES", "edition": "0.5.4",
     "describes": {"comprise": "1"}, "host": "comprise.cosmoes.org", "revised": "2026-11-03"},
]


def _put(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    """A cosmoes-site checkout in miniature: the registry, the five texts (the apex is not bundled), the client, and
    things the sync must leave alone."""
    c = tmp_path / "cosmoes-site"
    _put(c, "specs/specs.json", json.dumps(REGISTRY, indent=2) + "\n")
    for e in REGISTRY:
        _put(c, f"specs/{e['file']}", f"# {e['name']}\n\n*Edition {e['edition']} · revised {e['revised']}*\n\n## 1. One\n")
    _put(c, "specs/NOTICE.md", "all rights reserved\n")
    _put(c, "client/cosmoes_client.py", "VERSION = '1'\n")
    _put(c, "client/README.md", "the client\n")
    _put(c, "site/specs/thym/short.html", "<article/>")
    return c


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_sync_copies_the_four_texts_and_the_client_and_nothing_else(fake, tmp_path):
    out = tmp_path / "repo"
    report = sync_specs.sync(fake, out, today="2026-11-03")
    expected = {"docs/MACROCOSM_OES.md", "docs/THYM.md", "docs/ASCRIBE.md", "docs/COMPRISE_OES.md",
                "enough/cosmoes_client.py", "docs/specs.json"}
    assert _files(out) == expected
    assert sorted(report["added"]) == sorted(expected) and report["changed"] == report["removed"] == []
    assert report["missing"] == [] and report["files"] == 5
    for slug, dest in sync_specs.BUNDLED.items():
        entry = next(e for e in REGISTRY if e["slug"] == slug)
        assert (out / dest).read_bytes() == (fake / "specs" / entry["file"]).read_bytes()
    assert (out / "enough/cosmoes_client.py").read_bytes() == (fake / "client/cosmoes_client.py").read_bytes()
    assert not (out / "docs" / "OES.md").exists() and "NOTICE" not in "".join(_files(out))


def test_specs_json_carries_the_registry_entries_with_hashes_commits_and_the_date(fake, tmp_path):
    out = tmp_path / "repo"
    sync_specs.sync(fake, out, today="2026-11-03")
    body = json.loads((out / "docs/specs.json").read_text(encoding="utf-8"))
    assert list(body) == ["source", "commit", "dirty", "synced", "client", "documents"]
    assert body["source"] == "cosmoes-site" and body["synced"] == "2026-11-03"
    assert body["commit"] is None and body["dirty"] is None                # the fake is not a git checkout
    assert body["client"] == {"path": "enough/cosmoes_client.py", "source": "client/cosmoes_client.py",
                              "commit": None,
                              "sha256": hashlib.sha256((fake / "client/cosmoes_client.py").read_bytes()).hexdigest()}
    assert [d["slug"] for d in body["documents"]] == ["macrocosm-oes", "thym", "ascribe", "comprise-oes"]
    for d in body["documents"]:
        entry = next(e for e in REGISTRY if e["slug"] == d["slug"])
        for k in sync_specs.REGISTRY_KEYS:
            assert d.get(k) == entry.get(k), (d["slug"], k)
        assert d["path"] == sync_specs.BUNDLED[d["slug"]] and d["source"] == f"specs/{entry['file']}"
        assert d["sha256"] == hashlib.sha256((out / d["path"]).read_bytes()).hexdigest()
    assert body["documents"][0]["reference"] is True and "reference" not in body["documents"][1]


def test_rerun_is_byte_stable_and_check_writes_nothing(fake, tmp_path, capsys):
    out = tmp_path / "repo"
    sync_specs.sync(fake, out, today="2026-11-03")
    before = {rel: ((out / rel).read_bytes(), (out / rel).stat().st_mtime_ns) for rel in _files(out)}
    again = sync_specs.sync(fake, out, today="2026-11-04")                 # another day, nothing changed: no write
    assert again["added"] == again["changed"] == again["removed"] == [] and again["synced"] == "2026-11-03"
    assert {rel: ((out / rel).read_bytes(), (out / rel).stat().st_mtime_ns) for rel in _files(out)} == before
    assert sync_specs.main(["--cosmoes", str(fake), "--root", str(out), "--check"]) == 0

    _put(fake, "specs/thym.md", "# Thym\n\n*Edition 0.5.5 · revised 2026-11-04*\n\n## 1. One\n\nchanged\n")
    _put(fake, "client/cosmoes_client.py", "VERSION = '1'\n# a fix\n")
    capsys.readouterr()
    assert sync_specs.main(["--cosmoes", str(fake), "--root", str(out), "--check"]) == 1
    said = capsys.readouterr()
    assert "changed  docs/THYM.md" in said.out and "changed  enough/cosmoes_client.py" in said.out
    assert "changed  docs/specs.json" in said.out and "differ from the checkout" in said.err
    assert {rel: (out / rel).read_bytes() for rel in _files(out)} == {rel: b for rel, (b, _) in before.items()}

    assert sync_specs.main(["--cosmoes", str(fake), "--root", str(out)]) == 0
    assert (out / "docs/THYM.md").read_text(encoding="utf-8").endswith("changed\n")
    body = json.loads((out / "docs/specs.json").read_text(encoding="utf-8"))
    thym = next(d for d in body["documents"] if d["slug"] == "thym")
    assert thym["sha256"] == hashlib.sha256((out / "docs/THYM.md").read_bytes()).hexdigest()
    assert body["client"]["sha256"] == hashlib.sha256(b"VERSION = '1'\n# a fix\n").hexdigest()
    assert sync_specs.main(["--cosmoes", str(fake), "--root", str(out), "--check"]) == 0


def test_a_text_missing_from_the_checkout_is_reported_and_the_rest_synced(fake, tmp_path, capsys):
    (fake / "specs" / "ascribe.md").unlink()
    out = tmp_path / "repo"
    report = sync_specs.sync(fake, out, today="2026-11-03")
    assert report["missing"] == ["specs/ascribe.md"] and "docs/ASCRIBE.md" not in report["added"]
    body = json.loads((out / "docs/specs.json").read_text(encoding="utf-8"))
    assert [d["slug"] for d in body["documents"]] == ["macrocosm-oes", "thym", "comprise-oes"]
    assert sync_specs.main(["--cosmoes", str(fake), "--root", str(out)]) == 0
    assert "missing  specs/ascribe.md" in capsys.readouterr().err


def test_no_cosmoes_checkout(tmp_path, capsys):
    assert sync_specs.main(["--cosmoes", str(tmp_path / "nowhere"), "--root", str(tmp_path / "repo")]) == 2
    assert "no cosmoes-site checkout" in capsys.readouterr().err
    assert not (tmp_path / "repo").exists()


def test_the_bundled_copies_are_what_specs_json_records():
    """The four texts and the client in this repository are the bytes docs/specs.json hashes: nothing was edited
    by hand (a specification changes only at cosmoes.org; rerun the sync)."""
    body = json.loads((REPO / sync_specs.SPECS_JSON).read_text(encoding="utf-8"))
    assert body["source"] == "cosmoes-site" and body["commit"] and body["client"]["commit"]
    assert [d["slug"] for d in body["documents"]] == list(sync_specs.BUNDLED)
    for d in body["documents"]:
        assert d["path"] == sync_specs.BUNDLED[d["slug"]]
        assert hashlib.sha256((REPO / d["path"]).read_bytes()).hexdigest() == d["sha256"], \
            f"{d['path']} was edited by hand: a specification changes only at cosmoes.org; rerun the sync"
        assert d["name"] and not any(ch.isdigit() for ch in d["name"]) and d["edition"] and d["revised"]
        assert d["host"] == "cosmoes.org" or d["host"].endswith(".cosmoes.org")
        first = (REPO / d["path"]).read_text(encoding="utf-8").splitlines()[0]
        assert first == f"# {d['name']}", (d["slug"], first)
    client = body["client"]
    assert client["path"] == sync_specs.CLIENT_DEST and client["source"] == sync_specs.CLIENT_SOURCE
    assert hashlib.sha256((REPO / client["path"]).read_bytes()).hexdigest() == client["sha256"], \
        "enough/cosmoes_client.py was edited here: a fix goes to cosmoes-site and is taken again"


def test_the_shipped_copies_are_the_checkout_s():
    """When a cosmoes-site checkout is beside this repository, the bundled copies are its (`--check` finds nothing
    to do). Skipped where there is none (CI)."""
    if not (sync_specs.DEFAULT_COSMOES / sync_specs.REGISTRY).is_file():
        pytest.skip("no cosmoes-site checkout beside this repo")
    report = sync_specs.sync(sync_specs.DEFAULT_COSMOES, REPO, check=True)
    assert report["added"] == report["changed"] == report["removed"] == [], report
