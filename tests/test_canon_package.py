"""Packages in Canon (0.5.0, docs/THYM.md 15): the cipher of the encrypted form (`enough.thym.vault`, Comprise's
`comprise-bundle/0` vendored) and how Canon's listings, mirror and catalogs show a package beside its text.

No app here (the routes are `tests/test_thym_api.py`); the store points inside tmp_path (conftest).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from enough import canon, macrocosm as mc
from enough.thym import Refusal, vault

REPO = Path(__file__).resolve().parent.parent
INPUTS = REPO / "tests" / "fixtures" / "thym" / "inputs"
PACKAGE = REPO / "tests" / "fixtures" / "thym" / "replay" / "publish-story" / "2026-11-01-2148-35b5" / "outputs"
FAST = 1000                              # iterations for the tests' keys; the default is Comprise's 600000


# ---------------------------------------------------------------------------
# The cipher
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def single() -> bytes:
    return (PACKAGE / "out.package.cosm").read_bytes()


def test_seal_and_open_round_trip(single: bytes):
    sealed, key = vault.seal(single, path="notes.package.cosm", slug="notes", iterations=FAST)
    assert vault.open(sealed, key) == single
    assert vault.open(sealed, key.lower().replace("-", " ")) == single, "a key reads leniently"
    head = mc.yaml_load(sealed.decode("utf-8"))
    assert (head["oes"], head["kind"], head["id"], head["name"]) == ("thym/1", "package", "thym/notes",
                                                                     "a sealed package")
    enc = head["encrypted"]
    assert enc["cipher"] == "comprise-bundle/0" and enc["key"] == "shown-once"
    assert enc["aead"] == ("a256gcm" if vault.have_aes_gcm() else "hmac-sha256-ctr")
    assert enc["keyring"]["kind"] == "recovery" and enc["keyring"]["iterations"] == FAST
    assert len(enc["chunks"]) == 1 and len(enc["chunks"][0]["id"]) == 64


def test_the_default_key_is_comprises_recovery_code(single: bytes):
    sealed, key = vault.seal(single)
    parts = key.split("-")
    assert len(parts) == 6 and all(len(p) == 4 for p in parts) and set("".join(parts)) <= set(vault.BASE32)
    assert mc.yaml_load(sealed.decode())["encrypted"]["keyring"]["iterations"] == 600000
    assert vault.open(sealed, key) == single


def test_a_wrong_key_is_refused(single: bytes):
    sealed, key = vault.seal(single, iterations=FAST)
    other = vault.new_code()
    r = vault.open(sealed, other)
    assert isinstance(r, Refusal) and r.check == "key" and "does not open" in r.message
    r = vault.open(sealed, "not a key")
    assert isinstance(r, Refusal) and r.check == "key"


def test_one_flipped_byte_is_refused(single: bytes):
    sealed, key = vault.seal(single, iterations=FAST)
    text = sealed.decode("utf-8")
    at = text.index("object: ") + 200                       # inside the chunk's base64
    flipped = text[:at] + ("B" if text[at] != "B" else "C") + text[at + 1:]
    r = vault.open(flipped.encode("utf-8"), key)
    assert isinstance(r, Refusal) and r.check == "sealed"
    raw = bytearray(sealed)
    raw[len(raw) // 2] ^= 0x01                               # any byte at all: a refusal, never other bytes
    r = vault.open(bytes(raw), key)
    assert isinstance(r, Refusal) and r.check in ("sealed", "key")


# What a stranger's file may cost before any key (Comprise's review, ported: comprise-dev core/vault.py)

def test_a_file_larger_than_any_sealed_package_is_not_read(single: bytes, monkeypatch):
    sealed, key = vault.seal(single, iterations=FAST)
    monkeypatch.setattr(vault, "MAX_SEALED", len(sealed) - 1)
    for r in (vault.header(sealed), vault.open(sealed, key)):
        assert isinstance(r, Refusal) and r.check == "sealed" and "was not read" in r.message, r
    monkeypatch.setattr(vault.mc, "yaml_load", lambda text: pytest.fail("parsed a file over the cap"))
    assert isinstance(vault.header(sealed), Refusal)


def test_a_clear_part_with_an_anchor_or_an_alias_is_refused_before_it_is_built(single: bytes, monkeypatch):
    sealed, key = vault.seal(single, iterations=FAST)
    text = sealed.decode("utf-8")
    laughs = "lol: &a [x, x, x, x, x, x, x, x, x]\nlol2: &b [*a, *a, *a, *a, *a, *a, *a, *a, *a]\n" \
             "lol3: [*b, *b, *b, *b, *b, *b, *b, *b, *b]\n"
    for changed in (text.replace("notice:", laughs + "notice:", 1), text.replace("nodes: []", "nodes: &n []", 1)):
        monkeypatch.setattr(vault.mc, "yaml_load", lambda t: pytest.fail("built a clear part with an alias"))
        r = vault.header(changed.encode("utf-8"))
        assert isinstance(r, Refusal) and r.check == "sealed" and "an anchor or an alias" in r.message, r
        monkeypatch.undo()
        assert isinstance(vault.open(changed.encode("utf-8"), key), Refusal)


def test_a_clear_part_of_too_many_pieces_or_too_deep_is_refused(single: bytes):
    sealed, _key = vault.seal(single, iterations=FAST)
    text = sealed.decode("utf-8")
    many = "pad: [" + ", ".join("x" for _ in range(vault.MAX_SEALED_EVENTS)) + "]\n"
    r = vault.header(text.replace("notice:", many + "notice:", 1).encode("utf-8"))
    assert isinstance(r, Refusal) and r.check == "sealed" and "pieces" in r.message, r
    deep = "pad: " + "[" * (vault.MAX_YAML_DEPTH + 1) + "]" * (vault.MAX_YAML_DEPTH + 1) + "\n"
    r = vault.header(text.replace("notice:", deep + "notice:", 1).encode("utf-8"))
    assert isinstance(r, Refusal) and r.check == "sealed" and "deep" in r.message, r
    assert vault.plain_yaml_events(text) < 100, "a real sealed file is a few dozen pieces"


def _reseal_manifest(sealed: bytes, key: str, repeat: int) -> bytes:
    """The sealed file with its manifest sealed again, naming its one chunk `repeat` times (the key is known)."""
    doc = mc.yaml_load(sealed.decode("utf-8"))
    enc, kr = doc["encrypted"], doc["encrypted"]["keyring"]
    aead = enc["aead"]
    wk = vault.wrapping_key(vault.normalize_code(key), vault._unb64(kr["salt"]), int(kr["iterations"]))
    dek = vault.aead_open(aead, wk, vault._unb64(kr["nonce"]) + vault._unb64(kr["wrapped"]), None)
    _id_key, chunk_key = vault.subkeys(dek)
    manifest = json.loads(vault.aead_open(aead, chunk_key, vault._unb64(enc["manifest"]), vault.MANIFEST_AAD))
    f = manifest["files"][0]
    f["chunks"] = f["chunks"] * repeat
    f["size"] *= repeat
    f["sha256"] = hashlib.sha256(vault.open(sealed, key) * repeat).hexdigest()
    enc["manifest"] = vault.b64(vault.aead_seal(aead, chunk_key, vault.canonical_json(manifest), vault.MANIFEST_AAD))
    return mc.dump(doc).encode("utf-8")


def test_a_manifest_that_repeats_a_chunk_cannot_swell_what_opens(single: bytes):
    sealed, key = vault.seal(single, iterations=FAST)
    twice = _reseal_manifest(sealed, key, 2)                # a repeated chunk is the format's own, and opens
    assert vault.open(twice, key) == single * 2
    swollen = _reseal_manifest(sealed, key, 50)              # 50 copies of a chunk of a file of one chunk
    assert len(swollen) < 2 * len(sealed)
    r = vault.open(swollen, key)
    assert isinstance(r, Refusal) and r.check == "sealed" and "far more than it holds" in r.message, r


def test_the_key_is_not_in_the_sealed_bytes(single: bytes):
    sealed, key = vault.seal(single, iterations=FAST)
    for form in (key, key.replace("-", ""), key.lower()):
        assert form.encode("ascii") not in sealed
    assert b"Hollins" not in sealed, "nothing of the text is in the clear"


def test_a_file_that_is_not_sealed_is_refused():
    r = vault.open(b"oes: thym/1\nkind: package\n", "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF")
    assert isinstance(r, Refusal) and r.check == "sealed"
    r = vault.open(b"\x00\x01 not yaml", "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF")
    assert isinstance(r, Refusal) and r.check == "sealed"


@pytest.mark.skipif(not vault.have_aes_gcm(), reason="AES-256-GCM needs the optional cryptography package")
def test_aes_gcm_is_comprises_scheme(single: bytes):
    sealed, key = vault.seal(single, aead="a256gcm", iterations=FAST)
    assert mc.yaml_load(sealed.decode())["encrypted"]["keyring"]["alg"] == "pbkdf2-sha256-a256gcm"
    assert vault.open(sealed, key) == single


def test_the_standard_library_aead_is_named_and_authenticates(single: bytes):
    sealed, key = vault.seal(single, aead="hmac-sha256-ctr", iterations=FAST)
    enc = mc.yaml_load(sealed.decode())["encrypted"]
    assert enc["aead"] == "hmac-sha256-ctr" and enc["keyring"]["alg"] == "pbkdf2-sha256-hmac-sha256-ctr"
    k = hashlib.sha256(b"k").digest()
    obj = vault.aead_seal("hmac-sha256-ctr", k, b"the orchard", b"aad")
    assert b"the orchard" not in obj and vault.aead_open("hmac-sha256-ctr", k, obj, b"aad") == b"the orchard"
    with pytest.raises(Exception):
        vault.aead_open("hmac-sha256-ctr", k, obj, b"other aad")


# ---------------------------------------------------------------------------
# Canon: a package is one thing, shown beside its text
# ---------------------------------------------------------------------------

@pytest.fixture
def volume() -> Path:
    canon.create_volume("orchard")
    box = canon.volume_dir("orchard")
    shutil.copyfile(INPUTS / "notes.md", box / "notes.md")
    shutil.copyfile(INPUTS / "notes.md.cosm", box / "notes.md.cosm")
    shutil.copyfile(PACKAGE / "out.package.cosm", box / "notes.package.cosm")
    shutil.copytree(PACKAGE / "notes.thym", box / "notes.thym")
    sealed, _key = vault.seal((box / "notes.package.cosm").read_bytes(), iterations=FAST)
    (box / "notes.thym.enc").write_bytes(sealed)
    (box / "other.md").write_text("# Other\n\nA neighbour.\n", encoding="utf-8")
    return box


def test_file_kind_names_the_package_forms():
    assert canon.file_kind("notes.package.cosm") == "package"
    assert canon.file_kind("notes.thym.enc") == "sealed"
    assert canon.file_kind("notes.cosm") == "cosm" and canon.file_kind("notes.md") == "markdown"
    assert canon.package_stem("notes.thym") == canon.package_stem("notes.package.cosm") == "notes"
    assert canon.package_stem("notes.md") is None


def test_the_scan_shows_a_package_beside_its_text_and_never_opens_it(volume: Path):
    tree = canon._scan_tree(volume)
    by = {n["name"]: n for n in tree}
    assert by["notes.thym"]["kind"] == "package" and by["notes.thym"]["children"] == []
    assert by["notes.package.cosm"]["kind"] == "package" and by["notes.package.cosm"].get("cosm") is True
    assert by["notes.thym.enc"]["kind"] == "sealed"
    assert by["notes.md"]["package"] == {"path": "notes.package.cosm", "folder": "notes.thym",
                                         "sealed": "notes.thym.enc"}
    assert "package" not in by["other.md"]


def test_the_catalog_lists_a_package_as_one_item(volume: Path):
    cat = mc.yaml_load(canon.build_catalog("orchard"))
    by = {n["path"]: n for n in cat["nodes"]}
    assert by["notes.thym"]["type"] == "folder" and by["notes.thym"]["kind"] == "package"
    assert "parts" not in by["notes.thym"] and not any(p.startswith("notes.thym/") for p in by)
    assert (by["notes.package.cosm"]["kind"], by["notes.thym.enc"]["kind"]) == ("package", "sealed")
    assert by["notes.md"]["package"] == {"path": "notes.package.cosm", "folder": "notes.thym",
                                         "sealed": "notes.thym.enc"}
    assert by["notes.md"]["fabula"]["path"] == "notes.md.cosm"
    report = mc.lint(mc.load_volume_text(canon.build_catalog("orchard"), filename="canon.cosm"))
    assert report.ok, report.to_dict()


def test_the_mirror_draws_a_package_folder_as_one_node(volume: Path):
    body, node_map = canon.build_mirror("orchard")
    assert "🧳 notes.thym" in body
    assert not any(v["path"].startswith("notes.thym/") for v in node_map.values())


def test_a_folder_named_like_a_package_without_its_catalog_is_a_folder(volume: Path):
    (volume / "draft.thym").mkdir()
    (volume / "draft.thym" / "text.md").write_text("Just a folder.\n", encoding="utf-8")
    assert not canon.is_package_folder(volume / "draft.thym")
    cat = mc.yaml_load(canon.build_catalog("orchard"))
    assert any(n["path"] == "draft.thym/text.md" for n in cat["nodes"])


def test_the_catalog_excerpt_is_what_surrounds_a_text(volume: Path, tmp_path: Path):
    ex = canon.catalog_excerpt(volume / "notes.md")
    assert ex["volume"] == {"id": "canon/orchard", "name": "orchard", "scope": "volume"}
    assert ex["text"]["path"] == "notes.md" and ex["text"]["package"]["path"] == "notes.package.cosm"
    assert "other.md" in {n["path"] for n in ex["neighbours"]}
    assert "notes.md" not in {n["path"] for n in ex["neighbours"]}
    assert canon.catalog_excerpt(tmp_path / "nowhere.md") is None
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.md").write_text("A.\n", encoding="utf-8")
    (proj / "b.md").write_text("B.\n", encoding="utf-8")
    ex = canon.catalog_excerpt(proj / "a.md", proj)
    assert ex["volume"]["scope"] == "project" and [n["path"] for n in ex["neighbours"]] == ["b.md"]
