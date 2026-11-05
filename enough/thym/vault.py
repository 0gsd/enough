"""The encrypted package: a package's single-file form sealed under a key its owner hands to a chosen party
(docs/THYM.md 15.3, the owner's ruling of 2026-11-01: one cipher serves both subjects).

The cipher is Comprise's bundle scheme, `comprise-bundle/0` (comprise-dev `core/vault.py`, the owner's own code),
vendored here with its parameters unchanged, so that a reader of either can open the other's:

  data key       32 random bytes per package (the DEK); never stored or shown unwrapped.
  subkeys        HKDF-SHA256 (RFC 5869) of the DEK, salt empty, length 32: info `comprise chunk-id` gives the chunk-id
                 key, info `comprise chunk-key` the chunk key. The DEK itself encrypts nothing.
  chunks         the file cut into pieces of 4 MiB, the last one shorter. A chunk's id: lowercase hex of
                 HMAC-SHA256(chunk-id key, plaintext). Its object: nonce (12 random bytes) || AEAD(chunk key, nonce,
                 plaintext, aad = the id as 64 ASCII bytes), the ciphertext followed by the 16-byte tag.
  manifest       {bundle: "comprise-bundle/0", hid, id, taken, app_version, atoms, files: [{path, size, sha256,
                 chunks}]}, as JSON with keys sorted and no spaces, sealed like a chunk under the chunk key with aad
                 `manifest`. `hid` and `id` are repeated in the clear header, and a manifest that names others is
                 refused, so a manifest cannot be moved to another package.
  the key        Comprise's recovery code: 15 random bytes in RFC 4648 base32, 24 characters shown as six groups of
                 four (`ABCD-EFGH-IJKL-MNOP-QRST-UVWX`), read leniently (case, spaces and dashes ignored). It wraps the
                 DEK as Comprise's recovery keyring entry does: {kind: recovery, alg, salt (16 random bytes),
                 iterations: 600000, nonce, wrapped}, the wrapping key PBKDF2-HMAC-SHA256(the code's 24 characters, the
                 salt, the iterations, 32 bytes). The key is returned once, to be shown once, and stored nowhere.

**The AEAD.** Comprise seals with AES-256-GCM from the optional `cryptography` package, and so does this module when
that package imports (`aead: a256gcm`, `alg: pbkdf2-sha256-a256gcm`, the scheme exactly). enough does not depend on
`cryptography` (it is not installed on macOS, where enough ships), and the standard library has no block cipher, so
without it the same layout is sealed with an encrypt-then-MAC AEAD built from HMAC-SHA256 alone (`aead:
hmac-sha256-ctr`, `alg: pbkdf2-sha256-hmac-sha256-ctr`): the key is split by HKDF (`thym seal enc`, `thym seal mac`);
the keystream is HMAC-SHA256(enc key, nonce || an 8-byte big-endian block counter), XORed with the plaintext; the tag
is the first 16 bytes of HMAC-SHA256(mac key, the aad's length in 8 bytes || aad || nonce || ciphertext), checked
before anything is decrypted. It gives confidentiality and integrity under the usual assumption that HMAC-SHA256 is a
pseudorandom function; it is a deviation from `comprise-bundle/0`, named in every file it writes, and a package
sealed one way opens only where that way is available (AES-GCM needs `cryptography`).

**The file**, `<stem>.thym.enc`, is a `thym/1` package catalog that holds no content in the clear, YAML in the COSM
subset, binary values in base64 (RFC 4648 section 4, padded):

    oes: thym/1
    kind: package
    id: thym/<slug>
    name: a sealed package
    encrypted: {cipher: comprise-bundle/0, aead, key: shown-once, hid, bundle, keyring: {...}, manifest: <b64>,
                chunks: [{id, object: <b64>}]}
    notice: ...
    nodes: []

`seal(data, *, path, slug) -> (sealed_bytes, key_text)`; `open(sealed_bytes, key_text) -> bytes | Refusal`: the
single file's bytes, byte for byte, or a refusal with its check (`key` for a key that does not open it, `sealed` for a
file that is not a sealed package or was changed, `cipher` for a cipher this machine cannot run). Nothing here touches
the disk or the network.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import json
import re
import secrets
from typing import Any

import yaml

from enough import macrocosm as mc
from enough.thym import MINICOSM, Refusal

FORMAT = "comprise-bundle/0"
CHUNK_SIZE = 4 * 1024 * 1024
KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16
SALT_BYTES = 16
ITERATIONS = 600000
MAX_ITERATIONS = 10_000_000                   # a file asking for more is refused rather than computed
# What a stranger's file may cost before any key, as Comprise's reader holds it (comprise-dev core/vault.py, its review
# of 2026-11-03): a size read first, a YAML stream read with no anchors or aliases and a cap on its pieces and depth,
# and what opens held to a multiple of the file before any chunk is joined.
MAX_SEALED = 256 * 1024 * 1024               # 256 MiB, Comprise Connect's limit: a larger file is not read at all
MAX_OPENED_RATIO = 4                          # what opens, against the file it came in (base64 alone makes it 3/4)
MAX_SEALED_EVENTS = 10_000                    # YAML pieces in the clear part: about 35, and 6 per chunk
MAX_YAML_DEPTH = 64                           # how deep the clear part may nest; a sealed file nests 4 deep
INFO_CHUNK_ID = b"comprise chunk-id"
INFO_CHUNK_KEY = b"comprise chunk-key"
MANIFEST_AAD = b"manifest"
RECOVERY_ALG = "pbkdf2-sha256-a256gcm"        # Comprise's, with AES-256-GCM
CODE_BYTES = 15
CODE_CHARS = 24
BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
APP_VERSION = "thym 0"                        # the language that sealed it, never enough's version: a later enough reads it
NAME = "a sealed package"
NOTICE = ("A sealed Thym package: the package's single file, encrypted on its owner's machine. Open it with the key "
          "its owner gave you; nothing in it can be read without that key.")

AES_GCM = "a256gcm"
HMAC_CTR = "hmac-sha256-ctr"
_ALG = {AES_GCM: RECOVERY_ALG, HMAC_CTR: "pbkdf2-sha256-hmac-sha256-ctr"}
_INFO_ENC = b"thym seal enc"
_INFO_MAC = b"thym seal mac"
_SEPARATORS = re.compile(r"[\s\-]+")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class _Unopened(Exception):
    """A tag that does not verify: a wrong key, or bytes that were changed."""


# ---------------------------------------------------------------------------
# Primitives (Comprise's, and the standard-library AEAD)
# ---------------------------------------------------------------------------

def have_aes_gcm() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - the optional package is absent
        return False


def hkdf_sha256(ikm: bytes, info: bytes, length: int = KEY_BYTES, salt: bytes = b"") -> bytes:
    """RFC 5869 with SHA-256; the salt empty unless given (Comprise's `hkdf_sha256`)."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, block, i = b"", b"", 0
    while len(out) < length:
        i += 1
        block = hmac.new(prk, block + info + bytes([i]), hashlib.sha256).digest()
        out += block
    return out[:length]


def subkeys(dek: bytes) -> tuple[bytes, bytes]:
    """(chunk-id key, chunk key)."""
    return hkdf_sha256(dek, INFO_CHUNK_ID), hkdf_sha256(dek, INFO_CHUNK_KEY)


def chunk_id(id_key: bytes, plaintext: bytes) -> str:
    return hmac.new(id_key, plaintext, hashlib.sha256).hexdigest()


def _keystream_xor(enc_key: bytes, nonce: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    base = hmac.new(enc_key, digestmod=hashlib.sha256)
    blocks = []
    for i in range((len(data) + 31) // 32):
        h = base.copy()
        h.update(nonce + i.to_bytes(8, "big"))
        blocks.append(h.digest())
    stream = b"".join(blocks)[: len(data)]
    return (int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")).to_bytes(len(data), "big")


def _hmac_tag(mac_key: bytes, aad: bytes, nonce: bytes, ct: bytes) -> bytes:
    msg = len(aad).to_bytes(8, "big") + aad + nonce + ct
    return hmac.new(mac_key, msg, hashlib.sha256).digest()[:TAG_BYTES]


def aead_seal(aead: str, key: bytes, plaintext: bytes, aad: bytes | None, nonce: bytes | None = None) -> bytes:
    """nonce || ciphertext || tag, under AES-256-GCM (Comprise's `seal`) or the standard-library AEAD."""
    n = secrets.token_bytes(NONCE_BYTES) if nonce is None else bytes(nonce)
    if aead == AES_GCM:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return n + AESGCM(key).encrypt(n, plaintext, aad)
    enc, mac = hkdf_sha256(key, _INFO_ENC), hkdf_sha256(key, _INFO_MAC)
    ct = _keystream_xor(enc, n, plaintext)
    return n + ct + _hmac_tag(mac, aad or b"", n, ct)


def aead_open(aead: str, key: bytes, obj: bytes, aad: bytes | None) -> bytes:
    if len(obj) < NONCE_BYTES + TAG_BYTES:
        raise _Unopened("too short to be sealed")
    n = obj[:NONCE_BYTES]
    if aead == AES_GCM:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        try:
            return AESGCM(key).decrypt(n, obj[NONCE_BYTES:], aad)
        except InvalidTag:
            raise _Unopened("the tag does not verify") from None
    enc, mac = hkdf_sha256(key, _INFO_ENC), hkdf_sha256(key, _INFO_MAC)
    ct, tag = obj[NONCE_BYTES:-TAG_BYTES], obj[-TAG_BYTES:]
    if not hmac.compare_digest(tag, _hmac_tag(mac, aad or b"", n, ct)):
        raise _Unopened("the tag does not verify")
    return _keystream_xor(enc, n, ct)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: Any) -> bytes:
    return base64.b64decode(str(value), validate=True)


def canonical_json(doc: Any) -> bytes:
    """Comprise's manifest form: JSON with keys sorted, no spaces, UTF-8 unescaped."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# The key: Comprise's recovery code
# ---------------------------------------------------------------------------

def format_code(chars: str) -> str:
    return "-".join(chars[i:i + 4] for i in range(0, len(chars), 4))


def normalize_code(text: Any) -> str | None:
    """The code's 24 characters, upper case, no separators; None when it is not one."""
    s = _SEPARATORS.sub("", str(text or "")).upper()
    if len(s) != CODE_CHARS or any(c not in BASE32 for c in s):
        return None
    return s


def new_code() -> str:
    return format_code(base64.b32encode(secrets.token_bytes(CODE_BYTES)).decode("ascii"))


def wrapping_key(code: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), salt, iterations, KEY_BYTES)


def _random_base32(n: int) -> str:
    return "".join(secrets.choice(BASE32.lower()) for _ in range(n))


# ---------------------------------------------------------------------------
# seal and open
# ---------------------------------------------------------------------------

def seal(data: bytes, *, path: str = "package.cosm", slug: str = "package", now: _dt.datetime | None = None,
         iterations: int = ITERATIONS, aead: str | None = None) -> tuple[bytes, str]:
    """A package's single file sealed (THYM.md 15.3): `(the .thym.enc file's bytes, the key)`. The key is the
    caller's to show once; it is in no file and nowhere in the sealed bytes. `path` is the file's name in the
    manifest; `slug` the package's (`thym/<slug>`). `aead` is chosen by what this machine has unless given."""
    aead = aead or (AES_GCM if have_aes_gcm() else HMAC_CTR)
    if aead not in _ALG:
        raise ValueError(f"unknown AEAD {aead!r}")
    t = (now or _dt.datetime.now(_dt.timezone.utc)).astimezone(_dt.timezone.utc).replace(microsecond=0)
    dek = secrets.token_bytes(KEY_BYTES)
    id_key, chunk_key = subkeys(dek)
    chunks, ids = [], []
    for i in range(0, len(data), CHUNK_SIZE):
        piece = data[i:i + CHUNK_SIZE]
        cid = chunk_id(id_key, piece)
        ids.append(cid)
        chunks.append({"id": cid, "object": b64(aead_seal(aead, chunk_key, piece, cid.encode("ascii")))})
    hid = _random_base32(26)
    bundle = f"b-{t:%Y%m%dT%H%M%SZ}-{_random_base32(6)}"
    manifest = {"bundle": FORMAT, "hid": hid, "id": bundle, "taken": f"{t:%Y-%m-%dT%H:%M:%SZ}",
                "app_version": APP_VERSION, "atoms": 0,
                "files": [{"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                           "chunks": ids}]}
    code = new_code()
    salt = secrets.token_bytes(SALT_BYTES)
    wrapped = aead_seal(aead, wrapping_key(normalize_code(code) or "", salt, iterations), dek, None)
    keyring = {"kind": "recovery", "alg": _ALG[aead], "salt": b64(salt), "iterations": int(iterations),
               "nonce": b64(wrapped[:NONCE_BYTES]), "wrapped": b64(wrapped[NONCE_BYTES:])}
    doc = {"oes": MINICOSM, "kind": "package", "id": f"thym/{slug}", "name": NAME,
           "encrypted": {"cipher": FORMAT, "aead": aead, "key": "shown-once", "hid": hid, "bundle": bundle,
                         "keyring": keyring, "manifest": b64(aead_seal(aead, chunk_key, canonical_json(manifest),
                                                                       MANIFEST_AAD)),
                         "chunks": chunks},
           "notice": NOTICE, "nodes": []}
    return mc.dump(doc).encode("utf-8"), code


class NotPlainYaml(yaml.YAMLError):
    """A clear part this reader will not build: an anchor or an alias, or too many pieces, or too deep."""


def plain_yaml_events(text: str, max_events: int = MAX_SEALED_EVENTS) -> int:
    """Read `text` as a stream, holding nothing, and stop at the first anchor, alias, or piece or level too many: an
    answer from the parser itself, before anything is built (Comprise's `model.plain_yaml_events`). -> its pieces."""
    depth = events = 0
    for ev in yaml.parse(text, Loader=mc.Loader):
        events += 1
        if events > max_events:
            raise NotPlainYaml(f"more than {max_events} pieces")
        if isinstance(ev, yaml.AliasEvent) or getattr(ev, "anchor", None) is not None:
            raise NotPlainYaml("an anchor or an alias")
        if isinstance(ev, (yaml.SequenceStartEvent, yaml.MappingStartEvent)):
            depth += 1
            if depth > MAX_YAML_DEPTH:
                raise NotPlainYaml(f"nested more than {MAX_YAML_DEPTH} deep")
        elif isinstance(ev, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
            depth -= 1
    return events


def header(sealed: bytes) -> dict | Refusal:
    """A sealed file's clear header (its `encrypted:` block and catalog keys), or a refusal when it is not one.
    Anyone can hand a file to this with no key, so it is held to `MAX_SEALED` first, then read as a stream with no
    anchors or aliases and at most `MAX_SEALED_EVENTS` pieces (`plain_yaml_events`), and only then built."""
    if not isinstance(sealed, (bytes, bytearray)):
        return Refusal("run", "sealed", "not a sealed package")
    if len(sealed) > MAX_SEALED:
        return Refusal("run", "sealed", f"larger than any sealed package can be ({MAX_SEALED // (1024 * 1024)} MiB), "
                                        "so it was not read")
    try:
        text = bytes(sealed).decode("utf-8-sig")
        plain_yaml_events(text)
        doc = mc.yaml_load(text)
    except NotPlainYaml as e:
        return Refusal("run", "sealed", f"not a sealed package: its clear part holds {e}, which a sealed file never does")
    except Exception as e:  # noqa: BLE001 - anything a changed file can be
        return Refusal("run", "sealed", f"not a sealed package: it cannot be read ({type(e).__name__})")
    enc = doc.get("encrypted") if isinstance(doc, dict) else None
    if not isinstance(enc, dict) or doc.get("oes") != MINICOSM or doc.get("kind") != "package":
        return Refusal("run", "sealed", "not a sealed package: it has no thym/1 package catalog with encrypted:")
    if enc.get("cipher") != FORMAT:
        return Refusal("run", "cipher", f"sealed with {enc.get('cipher')!r}; this machine opens {FORMAT}")
    if enc.get("aead") not in _ALG:
        return Refusal("run", "cipher", f"sealed with the AEAD {enc.get('aead')!r}, which this reader does not know")
    return doc


def open(sealed: bytes, key_text: str) -> bytes | Refusal:  # noqa: A001 - the API's word (THYM.md 15.3)
    """The single file a sealed package holds, byte for byte, or a refusal (`key`, `sealed`, `cipher`)."""
    doc = header(sealed)
    if isinstance(doc, Refusal):
        return doc
    enc = doc["encrypted"]
    aead = enc["aead"]
    if aead == AES_GCM and not have_aes_gcm():
        return Refusal("run", "cipher", "this package was sealed with AES-256-GCM; opening it needs the optional "
                                        "`cryptography` package, which this machine does not have")
    code = normalize_code(key_text)
    if code is None:
        return Refusal("run", "key", "a key is 24 characters of A-Z and 2-7, shown as six groups of four (case, "
                                     "spaces and dashes do not matter)")
    kr = enc.get("keyring") if isinstance(enc.get("keyring"), dict) else {}
    try:
        salt, nonce, wrapped = _unb64(kr.get("salt")), _unb64(kr.get("nonce")), _unb64(kr.get("wrapped"))
        iterations = int(kr.get("iterations"))
        manifest_obj = _unb64(enc.get("manifest"))
        objects = {str(c["id"]): _unb64(c["object"]) for c in enc.get("chunks") or []}
    except Exception:  # noqa: BLE001 - a changed header
        return Refusal("run", "sealed", "the sealed package was changed: its header cannot be read")
    if kr.get("alg") != _ALG[aead] or not 1 <= iterations <= MAX_ITERATIONS or len(nonce) != NONCE_BYTES:
        return Refusal("run", "sealed", "the sealed package's key entry is not one this reader opens")
    try:
        dek = aead_open(aead, wrapping_key(code, salt, iterations), nonce + wrapped, None)
    except _Unopened:
        return Refusal("run", "key", "the key does not open this package: a wrong key, or the package was changed")
    if len(dek) != KEY_BYTES:
        return Refusal("run", "sealed", "the sealed package holds a key of the wrong length")
    id_key, chunk_key = subkeys(dek)
    try:
        manifest = json.loads(aead_open(aead, chunk_key, manifest_obj, MANIFEST_AAD).decode("utf-8"))
    except (_Unopened, ValueError):
        return Refusal("run", "sealed", "the sealed package was changed: its manifest does not open")
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if (manifest.get("bundle") != FORMAT or manifest.get("hid") != enc.get("hid")
            or manifest.get("id") != enc.get("bundle") or not isinstance(files, list) or len(files) != 1):
        return Refusal("run", "sealed", "the manifest is not this package's")
    f = files[0]
    ids = f.get("chunks") if isinstance(f, dict) else None
    if not isinstance(ids, list) or not all(isinstance(c, str) for c in ids):
        return Refusal("run", "sealed", "the sealed package was changed: its chunk list cannot be read")
    # A manifest may name one chunk over and over (a bundle shares a repeated chunk, and this reader takes one), so how
    # far a file can open is held down before anything is joined, by the objects' own sizes, not the manifest's word.
    opened = sum(max(len(objects[c]) - NONCE_BYTES - TAG_BYTES, 0) for c in ids if c in objects)
    if opened > MAX_SEALED or opened > MAX_OPENED_RATIO * len(sealed):
        return Refusal("run", "sealed", "the sealed package says it opens to far more than it holds, so it was not "
                                        "opened; ask whoever sent it to seal it again")
    parts = []
    for cid in ids:
        if not isinstance(cid, str) or not _HEX64.match(cid) or cid not in objects:
            return Refusal("run", "sealed", "the sealed package was changed: a chunk is missing")
        try:
            piece = aead_open(aead, chunk_key, objects[cid], cid.encode("ascii"))
        except _Unopened:
            return Refusal("run", "sealed", f"the sealed package was changed: chunk {cid[:12]} does not open")
        if not hmac.compare_digest(chunk_id(id_key, piece), cid):
            return Refusal("run", "sealed", f"chunk {cid[:12]} is not the chunk its id names")
        parts.append(piece)
    data = b"".join(parts)
    if len(data) != f.get("size") or hashlib.sha256(data).hexdigest() != f.get("sha256"):
        return Refusal("run", "sealed", "the opened file's size or sha256 is not the manifest's")
    return data


__all__ = ["FORMAT", "ITERATIONS", "MAX_OPENED_RATIO", "MAX_SEALED", "MAX_SEALED_EVENTS", "have_aes_gcm", "header",
           "open", "plain_yaml_events", "seal"]
