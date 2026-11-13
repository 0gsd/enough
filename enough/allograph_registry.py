"""The Allograph Registry, from the holder's side (Ascribe, https://ascribe.cosmoes.org/, sections 14.7 to 14.13).

An allograph is made on the holder's machine by `project h as allograph` (`enough/ascribe.py`) and is public only
when its holder lists it. This module is everything after that: the listing's key, its tag and the proof strings a
faceplace carries; the statements and their signatures; the registry's operations; Connect's sign-in, which the
registry needs to take a statement; and what enough keeps on this machine about a listing. Nothing of a holograph is
ever sent but a signed listing the holder chooses to send, and nothing here reads a holograph but `listing_status`
(the holograph's state, after the filter, to say whether it has changed since the listed allograph's run).

**The key** (14.8). One Ed25519 key per listing, made the first time its holograph is listed and kept in the holder's
keychain (service `enough/allograph`, user the holograph's hid; the value `{seed, tag}` in JSON, the seed's 32 bytes
in base64), never in the holograph, never in a file and never sent. It signs that listing's statements and nothing
else: `sign` refuses a statement whose `by` is not the key's tag, or a `list` whose `key` is not the key's own.

**The tag** is the first twelve characters of the lowercase, unpadded base32 of the SHA-256 of the key's 32 raw
bytes; **a proof string** is `aar-<tag>-<code>`, the code the first twelve of the same encoding of the SHA-256 of
`ascribe-proof/0`, the tag, the faceplace and the handle, each on its own line. **A statement** is signed over its
canonical JSON (keys sorted, no space, UTF-8, nothing escaped that JSON does not require), the 64 bytes of the
signature in standard base64 with padding. The text's own example (14.8, 14.9) is `tests/test_allograph_registry.py`.

**Connect** (14.7, 14.12). The registry is served by Comprise Connect, its listings at allograph.net, and takes a
statement only from an account signed in to Connect. enough signs in as Comprise's app does: Connect's device flow (after RFC 8628). `start_sign_in` asks Connect
for a code and gives the person the code and the address to approve it at (they sign in to Connect in their browser,
with a passkey); `poll_sign_in` asks until they have, then keeps the bearer token in the keychain (service
`enough/connect/<host>`, user `token`, the value `{token, account, expires, url, at}` in JSON), never in a file;
`sign_out` revokes it at Connect and forgets it here. The device code lives in this process's memory only. Two
addresses: Connect's, for the sign-in and the sign-out alone, is `ENOUGH_CONNECT_URL`, else https://compriseconnect.com;
the registry's, for every operation of 14.12 (statements, nonces, look-ups, faceplaces), is `ENOUGH_ALLOGRAPH_URL`,
else https://allograph.net, where the same token works. Plain http only for this machine, since a bearer token never
crosses a network in the clear. Every operation that needs an account takes a `Session` (`session()` reads the
keychain's; its `registry` is the registry's address), so a caller passes the one it has and a test passes its own.

**The network** sits behind one function, `TRANSPORT(method, url, body, token) -> (status, answer)`, which tests
replace; nothing else here opens a connection. A refusal comes back as `RegistryError`, with the registry's status,
its code (`not_listed`, `bad_nonce`, ...) and a sentence for a person.

**The keychain** sits behind `KEYCHAIN` (`get`, `set`, `delete`), the OS keychain through `keyring` by default; the
suite's conftest replaces it with `MemoryKeychain` for every test, and a scratch server sets `ENOUGH_KEYCHAIN=memory`,
so neither reads or writes the real one.

**On this machine** (`~/enough/config/allographs.json`): for each listed holograph, by its hid, the registry it was
sent to, its tag, name, dangler and kind, the listed allograph's run and sha256, and the holograph's state that run
took. It is the holder's own; nothing in the holograph names a listing (Ascribe 13: a release record never holds the
name or tag an allograph was listed under).

The standard library, `cryptography` (Ed25519), `httpx` (the default transport) and `keyring` (the default keychain).
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import re
import secrets
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import ascribe as A

DEFAULT_URL = "https://compriseconnect.com"
URL_ENV = "ENOUGH_CONNECT_URL"
REGISTRY_URL = "https://allograph.net"
REGISTRY_URL_ENV = "ENOUGH_ALLOGRAPH_URL"
KEYCHAIN_ENV = "ENOUGH_KEYCHAIN"
API = "/api/v0/allographs"
DEVICE_API = "/api/v0/device"
CLIENT = "enough"
TIMEOUT = 30.0
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

STATEMENT = "ascribe-statement/0"
ENTRY = "ascribe-entry/0"
PROOF = "ascribe-proof/0"
MAX_STATEMENT = 64 * 1024

KEY_SERVICE = "enough/allograph"
CONNECT_SERVICE = "enough/connect/"
CONNECT_USER = "token"

TAG_RE = re.compile(r"^[a-z2-7]{12}$")
NONCE_RE = re.compile(r"^[a-z2-7]{26}$")
COMPANY_RE = re.compile(r"^company:[A-Z0-9]{3,8}$")
NAME_RE = re.compile(r"^[a-z](?:[.-]?[a-z0-9])*$")
FACEPLACE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
KEY_B64_RE = re.compile(r"^[A-Za-z0-9+/]{43}=$")
EPOCH_RE = A.EPOCH_RE

#: What each statement says, and the fields it carries beyond `statement`, `says`, `by` and `nonce` (14.12):
#: (required, optional).
SAYS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "list": (("key", "name", "allograph"), ("dangler", "owner", "show")),
    "withdraw": ((), ()),
    "prove": (("faceplace", "handle", "address"), ()),
    "unprove": (("faceplace", "handle"), ()),
    "attest": (("of", "as", "claims", "epoch", "named"), ()),
    "accept": (("attestation",), ()),
    "remove": (("attestation",), ()),
    "bond": (("agent",), ()),
    "unbond": (("agent",), ()),
}
ATTEST_AS = ("client", "employer", "colleague", "certifier")
NEED_ABOUT = ("experience", "skill", "understanding", "form")
SHOW_FACEPLACES = ("named", "counted")
MAX_NEEDS = 8
MAX_CLAIMS = 20

#: The registry's refusals (14.12), as a sentence for the holder; the registry's own detail is kept beside.
PLAIN = {
    "signed_out": "Sign in to Connect first: the registry takes a statement only from a signed-in account.",
    "bad_statement": "The registry could not read the statement: a field missing, one it does not name, or a value "
                     "out of its shape.",
    "bad_signature": "The signature did not verify against the listing's key.",
    "bad_nonce": "The registry's challenge had expired or was already used; try again.",
    "bad_allograph": "The registry refused the allograph: it breaks a rule of Ascribe's section 14.6.",
    "not_feed": "A form in the allograph is not a FEED headword in the registry's edition of FEED.",
    "bad_name": "That user name is outside the rules: two to thirty-two of a-z, 0-9, . and -, beginning with a "
                "letter, ending with a letter or a digit, with no . or - beside another.",
    "bad_dangler": "That dangler is outside the rules: one line of one to thirty-two characters, with no address and "
                   "nothing that reads as personal data.",
    "name_reserved": "That user name is reserved by the registry; choose another.",
    "name_changed": "A listing's name may change at most once in ninety days.",
    "tag_taken": "Another live listing has this tag, or this tag is tied to another Connect account.",
    "not_listed": "No live listing (and no company on the Index) answers to that.",
    "not_allowed": "The registry does not let this listing say that.",
    "bad_claim": "An attested claim is one the listing's current allograph does not make.",
    "unknown_faceplace": "The registry does not check that faceplace.",
    "bad_address": "That address is not one the faceplace's entry accepts for the handle.",
    "proof_missing": "The registry read the address and did not find the proof string there.",
    "sample_refused": "This registry serves no demonstrations, and the allograph is a sample.",
    "too_large": "The statement is over 64 kilobytes.",
    "rate": "The registry's rate limit was reached; try again later.",
    "bad_need": "A search need is outside the shape, or names a word that is not a FEED headword.",
    "bad_next": "That page of answers is not one the registry gave.",
    "unreachable": "Connect could not be reached.",
    "unreachable_registry": "The Allograph Registry could not be reached.",
}


#: The status the registry answers each refusal with (14.12); a refusal made here before anything is sent carries it.
STATUS = {"signed_out": 401, "bad_statement": 400, "bad_signature": 400, "bad_nonce": 400, "bad_allograph": 400,
          "not_feed": 400, "bad_name": 400, "bad_dangler": 400, "name_reserved": 403, "name_changed": 409,
          "tag_taken": 409, "not_listed": 404, "not_allowed": 403, "bad_claim": 400, "unknown_faceplace": 400,
          "bad_address": 400, "proof_missing": 409, "sample_refused": 403, "too_large": 413, "rate": 429,
          "bad_need": 400, "bad_next": 400}


class RegistryError(Exception):
    """A refusal, in words for a person: the registry's (with its `status` and `code`), Connect's, or this module's
    own before anything is sent (the status the registry would answer for its code, else None)."""

    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status if status is not None else STATUS.get(code or "")
        self.code = code


# ---------------------------------------------------------------------------
# Encodings
# ---------------------------------------------------------------------------

def b32(data: bytes) -> str:
    """Lowercase base32, the RFC 4648 alphabet, without padding."""
    return base64.b32encode(data).decode("ascii").lower().rstrip("=")


def b64(data: bytes) -> str:
    """Standard base64, with padding."""
    return base64.b64encode(data).decode("ascii")


def canonical(statement: Any) -> bytes:
    """A statement's canonical JSON (14.7): keys sorted, no space between tokens, UTF-8 without a byte-order mark,
    and no character escaped that JSON does not require escaping (Python's encoder, unescaped, escapes only `"`, `\\`
    and the control characters)."""
    return json.dumps(statement, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Keys, tags and proof strings (14.8, 14.9)
# ---------------------------------------------------------------------------

def tag_of(public: bytes) -> str:
    """The tag a key gives: the first twelve characters of the lowercase unpadded base32 of the SHA-256 of its 32 raw
    bytes."""
    if not isinstance(public, (bytes, bytearray)) or len(public) != 32:
        raise RegistryError("a listing's key is an Ed25519 public key of 32 bytes")
    return b32(hashlib.sha256(bytes(public)).digest())[:12]


def proof_string(tag: str, faceplace: str, handle: str) -> str:
    """The proof a holder posts on a faceplace (14.9): `aar-<tag>-<code>`, good for one handle on one faceplace."""
    if not TAG_RE.match(str(tag)):
        raise RegistryError(f"{tag!r} is not a tag: twelve characters of lowercase base32")
    if not FACEPLACE_RE.match(str(faceplace)):
        raise RegistryError(f"{faceplace!r} is not a faceplace's word")
    h = normal_handle(handle)
    code = b32(hashlib.sha256(f"{PROOF}\n{tag}\n{faceplace}\n{h}".encode("utf-8")).digest())[:12]
    return f"aar-{tag}-{code}"


def normal_handle(handle: Any) -> str:
    """A handle in its normal form, the default a faceplace's entry gives (14.9): lower case, a leading `@` taken
    off."""
    h = str(handle or "").strip()
    if h.startswith("@"):
        h = h[1:]
    h = h.lower()
    if not h or any(c.isspace() for c in h):
        raise RegistryError("a handle is the account's name on the faceplace, one word")
    return h


@dataclass(frozen=True)
class ListingKey:
    """One listing's Ed25519 key. `seed` is its 32-byte private half: it lives in the keychain and nowhere else."""
    seed: bytes

    @property
    def _private(self) -> Ed25519PrivateKey:
        return Ed25519PrivateKey.from_private_bytes(self.seed)

    @property
    def public(self) -> bytes:
        return self._private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    @property
    def key(self) -> str:
        """The public key as a `list` statement carries it: 32 raw bytes in standard base64, 44 characters."""
        return b64(self.public)

    @property
    def tag(self) -> str:
        return tag_of(self.public)

    def __repr__(self) -> str:                  # never the seed, in a log or a traceback
        return f"ListingKey(tag={self.tag})"


def key_from_seed(seed: bytes) -> ListingKey:
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != 32:
        raise RegistryError("a listing's key is made from a 32-byte seed")
    return ListingKey(bytes(seed))


def new_key() -> ListingKey:
    return ListingKey(secrets.token_bytes(32))


def sign(statement: dict, key: ListingKey) -> dict:
    """`{statement, signature}`: the statement signed with its listing's key, over its canonical JSON. Refused when the
    statement is not the key's listing's (14.8: the key signs nothing else), or is over 64 kilobytes."""
    check_statement(statement)
    if statement.get("by") != key.tag:
        raise RegistryError("a listing's key signs only its own listing's statements, and this statement is by "
                            f"{statement.get('by')!r}")
    if statement.get("says") == "list" and statement.get("key") != key.key:
        raise RegistryError("a list statement carries the key that signs it")
    data = canonical(statement)
    if len(data) > MAX_STATEMENT:
        raise RegistryError(PLAIN["too_large"], code="too_large")
    return {"statement": statement, "signature": b64(key._private.sign(data))}


def verify(signed: Any, public: bytes | str | None = None) -> bool:
    """Whether `{statement, signature}` verifies against a key (32 raw bytes, or the base64 a `list` carries); with
    none given, a `list` statement's own `key`. An entry's `signed` field is checked this way (14.11)."""
    if not isinstance(signed, dict) or not isinstance(signed.get("statement"), dict):
        return False
    st = signed["statement"]
    if public is None:
        public = st.get("key")
    try:
        raw = base64.b64decode(public, validate=True) if isinstance(public, str) else bytes(public or b"")
        sig = base64.b64decode(str(signed.get("signature") or ""), validate=True)
        Ed25519PublicKey.from_public_bytes(raw).verify(sig, canonical(st))
    except (ValueError, TypeError, InvalidSignature):
        return False
    return st.get("by") == tag_of(raw) if TAG_RE.match(str(st.get("by") or "")) else True


def attestation_digest(statement: dict) -> str:
    """The digest an `accept` or a `remove` names (14.9): the SHA-256 of the `attest` statement's canonical JSON, in
    lowercase hex."""
    inner = statement.get("statement") if isinstance(statement.get("statement"), dict) else statement
    return hashlib.sha256(canonical(inner)).hexdigest()


# ---------------------------------------------------------------------------
# Statements (14.7, 14.12): built and checked before anything is signed or sent
# ---------------------------------------------------------------------------

def check_name(name: Any) -> str:
    """A user name (14.8), or a refusal in the registry's words."""
    s = str(name or "")
    if not (2 <= len(s) <= 32 and NAME_RE.match(s)):
        raise RegistryError(PLAIN["bad_name"], code="bad_name")
    return s


def check_dangler(dangler: Any) -> str:
    """A dangler (14.8): one to thirty-two printable characters on one line, with no `://` and nothing `no-pii` reads
    as an email address, a phone number, an id-like run of digits, a street address or a birth date. A personal name
    is the holder's own choice to show."""
    s = str(dangler if dangler is not None else "")
    if not (1 <= len(s) <= 32) or not s.isprintable() or "://" in s or A.pii_findings(s):
        raise RegistryError(PLAIN["bad_dangler"], code="bad_dangler")
    return s


def _signer_ok(v: Any) -> bool:
    return isinstance(v, str) and bool(TAG_RE.match(v) or COMPANY_RE.match(v))


def check_statement(st: Any) -> None:
    """Refuse, in words, a statement section 14.12 would answer `bad_statement` (or `bad_name`, `bad_dangler`,
    `bad_allograph`): a field missing or not named, a value out of its shape."""
    if not isinstance(st, dict):
        raise RegistryError("a statement is one JSON object", code="bad_statement")
    says = st.get("says")
    if st.get("statement") != STATEMENT or says not in SAYS:
        raise RegistryError(f"a statement is {STATEMENT} and says one of {', '.join(SAYS)}", code="bad_statement")
    need, may = SAYS[says]
    named = {"statement", "says", "by", "nonce", *need, *may}
    extra = sorted(k for k in st if k not in named)
    missing = sorted(k for k in ("by", "nonce", *need) if k not in st)
    if extra or missing:
        raise RegistryError(f"a {says} statement " + "; ".join(
            ([f"has no {', '.join(missing)}"] if missing else []) +
            ([f"carries what it does not name: {', '.join(extra)}"] if extra else [])), code="bad_statement")
    if not _signer_ok(st["by"]):
        raise RegistryError("by is a listing's tag or company:<handle>", code="bad_statement")
    if not NONCE_RE.match(str(st["nonce"])):
        raise RegistryError("nonce is the registry's challenge: 26 characters of lowercase base32",
                            code="bad_statement")
    if says == "list":
        if not KEY_B64_RE.match(str(st["key"])):
            raise RegistryError("key is the listing's public key, 44 characters of base64", code="bad_statement")
        check_name(st["name"])
        if "dangler" in st:
            check_dangler(st["dangler"])
        probs = A.allograph_problems(st["allograph"])
        if probs:
            raise RegistryError("the allograph would not read: " + "; ".join(probs), code="bad_allograph")
        kind = st["allograph"].get("kind")
        if kind == "agent" and "owner" not in st:
            raise RegistryError("an agent's listing names its owner, who answers for it (14.10)", code="not_allowed")
        if kind == "person" and "owner" in st:
            raise RegistryError("a person's listing names no owner (14.8)", code="bad_statement")
        if "owner" in st and not _signer_ok(st["owner"]):
            raise RegistryError("owner is a listing's tag or company:<handle>", code="bad_statement")
        show = st.get("show")
        if "show" in st and not (isinstance(show, dict) and set(show) == {"faceplaces", "same_name"}
                                 and show["faceplaces"] in SHOW_FACEPLACES and isinstance(show["same_name"], bool)):
            raise RegistryError("show is {faceplaces: named | counted, same_name: true | false}", code="bad_statement")
    elif says in ("prove", "unprove"):
        if not FACEPLACE_RE.match(str(st["faceplace"])) or not isinstance(st["handle"], str) or not st["handle"]:
            raise RegistryError("a proof names a faceplace by its word and the handle on it", code="bad_statement")
        if says == "prove" and not str(st["address"]).startswith("https://"):
            raise RegistryError("a proof's address is an https address on the faceplace", code="bad_address")
    elif says == "attest":
        if not TAG_RE.match(str(st["of"])):
            raise RegistryError("of is the tag of the listing attested", code="bad_statement")
        if st["as"] not in ATTEST_AS:
            raise RegistryError(f"as is one of {', '.join(ATTEST_AS)}", code="bad_statement")
        claims = st["claims"]
        if not (isinstance(claims, list) and 1 <= len(claims) <= MAX_CLAIMS and all(
                isinstance(c, dict) and set(c) == {"kind", "form"} and c["kind"] in ("experience", "skill",
                                                                                     "understanding")
                for c in claims)):
            raise RegistryError("claims are one to twenty {kind, form}, each a claim of the listing's allograph",
                                code="bad_statement")
        if not EPOCH_RE.match(str(st["epoch"])):
            raise RegistryError("epoch is a quarter, a month or a week", code="bad_statement")
        if not isinstance(st["named"], bool):
            raise RegistryError("named is true or false", code="bad_statement")
        if st["of"] == st["by"]:
            raise RegistryError("no one attests their own listing (14.9)", code="not_allowed")
    elif says in ("accept", "remove"):
        if not DIGEST_RE.match(str(st["attestation"])):
            raise RegistryError("attestation is the attest statement's digest, 64 lowercase hex", code="bad_statement")
    elif says in ("bond", "unbond"):
        if not TAG_RE.match(str(st["agent"])):
            raise RegistryError("agent is the agent's tag", code="bad_statement")


def statement(says: str, by: str, nonce: str, /, **fields: Any) -> dict:
    """A statement (`ascribe-statement/0`) that says `says`, checked; fields whose value is None are left out."""
    st = {"statement": STATEMENT, "says": says, "by": by, "nonce": nonce,
          **{k: v for k, v in fields.items() if v is not None}}
    check_statement(st)
    return st


def check_needs(needs: Any) -> list[dict]:
    """A search's needs (14.11): one to eight match tokens `{about, value}` (14.3)."""
    if not (isinstance(needs, list) and 1 <= len(needs) <= MAX_NEEDS):
        raise RegistryError("a search needs one to eight things, each {about, value}", code="bad_need")
    out = []
    for n in needs:
        if not (isinstance(n, dict) and set(n) == {"about", "value"} and n["about"] in NEED_ABOUT
                and isinstance(n["value"], str) and n["value"].strip()):
            raise RegistryError("each need is {about: experience | skill | understanding | form, value: a FEED word}",
                                code="bad_need")
        out.append({"about": n["about"], "value": n["value"].strip()})
    return out


# ---------------------------------------------------------------------------
# Faceplaces (14.9): what the registry checks, and the addresses it accepts for a handle
# ---------------------------------------------------------------------------

_SEG = "[A-Za-z0-9_-]+"


def addresses_for(faceplace: dict, handle: str) -> list[str]:
    """The addresses a faceplace's entry accepts for a handle, `{any}` left for the holder to fill (a gist's id, a
    post's)."""
    h = normal_handle(handle)
    return [str(t).replace("{handle}", h) for t in faceplace.get("addresses") or []]


def address_ok(faceplace: dict, handle: str, address: str) -> bool:
    """Whether `address` is one the faceplace's entry accepts for the handle: an https template, `{handle}` the
    handle, `{any}` one path segment."""
    h = normal_handle(handle)
    rx = faceplace.get("handle")
    if isinstance(rx, str) and rx and not re.fullmatch(rx, h):
        return False
    for t in faceplace.get("addresses") or []:
        t = str(t)
        if not t.startswith("https://"):
            continue
        pat = re.escape(t).replace(re.escape("{handle}"), re.escape(h)).replace(re.escape("{any}"), _SEG)
        if re.fullmatch(pat, str(address)):
            return True
    return False


# ---------------------------------------------------------------------------
# The keychain seam
# ---------------------------------------------------------------------------

class OSKeychain:
    """The OS keychain, through `keyring`. Reading may ask the person for permission (macOS); a failure is said.
    With `ENOUGH_KEYCHAIN=memory` (a scratch server's, `scripts/smoke_boot.py`) it is a keychain held in the
    process's memory instead, and the OS keychain is never reached."""

    def _scratch(self) -> "MemoryKeychain | None":
        return _SCRATCH if os.environ.get(KEYCHAIN_ENV) == "memory" else None

    def get(self, service: str, user: str) -> str | None:
        if self._scratch():
            return _SCRATCH.get(service, user)
        import keyring
        try:
            return keyring.get_password(service, user)
        except Exception as e:  # noqa: BLE001 - no backend, a locked keychain
            raise RegistryError(f"the keychain could not be read ({e}); unlock it and try again") from None

    def set(self, service: str, user: str, value: str) -> None:
        if self._scratch():
            return _SCRATCH.set(service, user, value)
        import keyring
        try:
            keyring.set_password(service, user, value)
        except Exception as e:  # noqa: BLE001
            raise RegistryError(f"the keychain refused to keep it ({e}); unlock it and try again") from None

    def delete(self, service: str, user: str) -> None:
        if self._scratch():
            return _SCRATCH.delete(service, user)
        import keyring
        try:
            keyring.delete_password(service, user)
        except Exception:  # noqa: BLE001 - already gone, or no backend: nothing to forget
            pass


class MemoryKeychain:
    """A keychain held in memory: the suite's (tests/conftest.py puts one in `KEYCHAIN` for every test)."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}

    def get(self, service: str, user: str) -> str | None:
        return self.items.get((service, user))

    def set(self, service: str, user: str, value: str) -> None:
        self.items[(service, user)] = value

    def delete(self, service: str, user: str) -> None:
        self.items.pop((service, user), None)


_SCRATCH = MemoryKeychain()
KEYCHAIN: Any = OSKeychain()


def listing_key(hid: str, *, create: bool = False) -> ListingKey | None:
    """The listing key of the holograph whose hid this is, from the keychain; made and kept there when `create` and
    there is none (the first listing). None when there is none and none is made."""
    if not A.HID_RE.match(str(hid)):
        raise RegistryError("a listing key belongs to a holograph, named by its 26-character hid")
    raw = KEYCHAIN.get(KEY_SERVICE, hid)
    if raw:
        try:
            doc = json.loads(raw)
            key = key_from_seed(base64.b64decode(doc["seed"], validate=True))
        except (ValueError, KeyError, TypeError):
            raise RegistryError("the keychain's listing key for this holograph cannot be read") from None
        return key
    if not create:
        return None
    key = new_key()
    KEYCHAIN.set(KEY_SERVICE, hid, json.dumps({"seed": b64(key.seed), "tag": key.tag}))
    return key


# ---------------------------------------------------------------------------
# Connect: the address, the session, the device flow
# ---------------------------------------------------------------------------

def normalize_url(url: Any, what: str = "Connect", like: str = DEFAULT_URL) -> str:
    """`https://host[:port][/path]` without a trailing slash; plain http only for this machine."""
    s = str(url or "").strip().rstrip("/")
    u = urllib.parse.urlsplit(s)
    if u.scheme not in ("https", "http") or not u.hostname or u.query or u.fragment:
        raise RegistryError(f"{s or '(empty)'} is not an address of {what}: give https://<host>, like {like}")
    if u.scheme == "http" and u.hostname not in LOCAL_HOSTS:
        raise RegistryError(f"{what} is reached over https; plain http only for this machine, since a bearer token "
                            "never crosses a network in the clear")
    return s


def connect_url() -> str:
    """The Connect enough signs in to and out of: `ENOUGH_CONNECT_URL`, else https://compriseconnect.com."""
    return normalize_url(os.environ.get(URL_ENV) or DEFAULT_URL)


def registry_url() -> str:
    """The Allograph Registry's address, for every operation of 14.12: `ENOUGH_ALLOGRAPH_URL`, else
    https://allograph.net. Connect serves it there; the sign-in stays at `connect_url()`."""
    return normalize_url(os.environ.get(REGISTRY_URL_ENV) or REGISTRY_URL, "the Allograph Registry", REGISTRY_URL)


def _host(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    return (u.hostname or "").lower() + (f":{u.port}" if u.port else "")


@dataclass(frozen=True)
class Session:
    """A signed-in Connect account, as the registry's operations take it: Connect's address (where the token was
    given, and is revoked), the bearer token, and the registry's address (where it is used)."""
    url: str
    token: str
    account: Any = None
    registry: str = field(default_factory=registry_url)

    def __repr__(self) -> str:                  # never the token
        return f"Session(url={self.url!r}, registry={self.registry!r})"


_SESSIONS: dict[str, dict | None] = {}        # url -> the keychain's document, read once per process


def session(url: str | None = None) -> Session | None:
    """The session kept in the keychain for this Connect, or None (signed out, or the token expired). The keychain is
    read once in a process and the answer kept in memory (on macOS a read can ask the person for their password);
    signing in or out replaces it."""
    url = normalize_url(url or connect_url())
    if url not in _SESSIONS:
        raw = KEYCHAIN.get(CONNECT_SERVICE + _host(url), CONNECT_USER)
        try:
            doc = json.loads(raw) if raw else None
        except ValueError:
            doc = None
        _SESSIONS[url] = doc if isinstance(doc, dict) else None
    doc = _SESSIONS[url]
    if doc is None:
        return None
    exp = doc.get("expires")
    if isinstance(exp, str):
        try:
            if _dt.datetime.fromisoformat(exp.replace("Z", "+00:00")) <= _dt.datetime.now(_dt.timezone.utc):
                return None
        except ValueError:
            pass
    tok = doc.get("token")
    return Session(url, tok, doc.get("account")) if isinstance(tok, str) and tok else None


def need_session(sess: Session | None) -> Session:
    if sess is None:
        raise RegistryError(PLAIN["signed_out"], 401, "signed_out")
    return sess


_PENDING: dict[str, dict] = {}                 # url -> the device flow waiting for the person's approval
_PENDING_LOCK = threading.Lock()


def start_sign_in(url: str | None = None, *, device: str | None = None) -> dict:
    """Begin Connect's device flow: `{user_code, verification_uri, verification_uri_complete, interval,
    expires_in}` for the person to approve in their browser. The device code stays in this process."""
    url = normalize_url(url or connect_url())
    got = request("POST", url, f"{DEVICE_API}/code", {"client": CLIENT, **({"device": device} if device else {})})
    if not isinstance(got, dict) or not got.get("device_code") or not got.get("user_code"):
        raise RegistryError("Connect did not give a sign-in code")
    with _PENDING_LOCK:
        _PENDING[url] = {"device_code": got["device_code"], "interval": int(got.get("interval") or 5)}
    return {k: got.get(k) for k in ("user_code", "verification_uri", "verification_uri_complete", "interval",
                                     "expires_in")}


def poll_sign_in(url: str | None = None) -> dict:
    """Ask Connect whether the person has approved: `{state: pending}` until then, `{state: signed_in, account}` once,
    the token kept in the keychain. Denied or expired: a refusal, and the flow is forgotten."""
    url = normalize_url(url or connect_url())
    with _PENDING_LOCK:
        flow = _PENDING.get(url)
    if flow is None:
        raise RegistryError("no sign-in is waiting: start one first")
    status, got = TRANSPORT("POST", url + f"{DEVICE_API}/token", {"device_code": flow["device_code"]}, None)
    got = got if isinstance(got, dict) else {}
    if status == 200 and got.get("error") in ("authorization_pending", "slow_down"):
        return {"state": "pending", "interval": flow["interval"] + (5 if got["error"] == "slow_down" else 0)}
    if status != 200 or not got.get("access_token"):
        with _PENDING_LOCK:
            _PENDING.pop(url, None)
        raise RegistryError(str(got.get("error_description") or got.get("detail") or "the sign-in did not finish"),
                            status, str(got.get("error") or "") or None)
    with _PENDING_LOCK:
        _PENDING.pop(url, None)
    expires = None
    if isinstance(got.get("expires_in"), int):
        expires = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=got["expires_in"])).isoformat()
    account = got.get("account")
    doc = {"token": got["access_token"], "account": account, "expires": expires, "url": url,
           "at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    KEYCHAIN.set(CONNECT_SERVICE + _host(url), CONNECT_USER, json.dumps(doc))
    _SESSIONS[url] = doc
    return {"state": "signed_in", "account": account}


def sign_out(url: str | None = None) -> bool:
    """Revoke the token at Connect (`POST /api/v0/device/revoke`) and forget it here. True when one was kept."""
    url = normalize_url(url or connect_url())
    sess = session(url)
    with _PENDING_LOCK:
        _PENDING.pop(url, None)
    if sess is None:
        KEYCHAIN.delete(CONNECT_SERVICE + _host(url), CONNECT_USER)
        _SESSIONS[url] = None
        return False
    try:
        TRANSPORT("POST", url + f"{DEVICE_API}/revoke", None, sess.token)
    except RegistryError:
        pass                                    # forgotten here all the same; the token lives out its days there
    KEYCHAIN.delete(CONNECT_SERVICE + _host(url), CONNECT_USER)
    _SESSIONS[url] = None
    return True


# ---------------------------------------------------------------------------
# The network seam, and the registry's operations (14.12)
# ---------------------------------------------------------------------------

def _http(method: str, url: str, body: Any, token: str | None) -> tuple[int, Any]:
    """The default transport: one JSON request over HTTPS (httpx), no redirect followed. (status, parsed answer)."""
    import httpx
    headers = {"Accept": "application/json", "User-Agent": f"{CLIENT} (allograph registry client)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = canonical(body)
        headers["Content-Type"] = "application/json"
    try:
        r = httpx.request(method, url, content=data, headers=headers, timeout=TIMEOUT, follow_redirects=False)
    except httpx.HTTPError as e:
        said = PLAIN["unreachable"] if url.startswith(connect_url() + "/") else PLAIN["unreachable_registry"]
        raise RegistryError(f"{said} ({type(e).__name__})", None, "unreachable") from None
    try:
        answer = r.json() if r.content else None
    except ValueError:
        answer = None
    return r.status_code, answer


#: `TRANSPORT(method, url, body, token) -> (status, answer)`: the one function that reaches the network. Tests replace
#: it; `body` is a JSON value or None, `token` Connect's bearer token or None.
TRANSPORT: Callable[[str, str, Any, str | None], tuple[int, Any]] = _http


def request(method: str, base: str, path: str, body: Any = None, sess: Session | None = None) -> Any:
    """One operation at `base` (the registry's address, or Connect's for the device flow): the answer on a 2xx, a
    `RegistryError` in plain words otherwise."""
    status, got = TRANSPORT(method, normalize_url(base) + path, body, sess.token if sess else None)
    if 200 <= status < 300:
        return got
    code = str(got.get("error") or "") if isinstance(got, dict) else ""
    detail = str(got.get("detail") or "") if isinstance(got, dict) else ""
    said = PLAIN.get(code) or detail or f"the registry answered {status}"
    if detail and detail != said and detail != code:
        said = f"{said} ({detail})"
    raise RegistryError(said, status, code or None)


def challenge(sess: Session) -> str:
    """A nonce good for one statement from this account, for ten minutes (`POST /api/v0/allographs/challenge`)."""
    got = request("POST", need_session(sess).registry, f"{API}/challenge", {}, sess)
    nonce = got.get("nonce") if isinstance(got, dict) else None
    if not NONCE_RE.match(str(nonce or "")):
        raise RegistryError("the registry gave no challenge")
    return nonce


def send(sess: Session, signed: dict) -> dict:
    """`POST /api/v0/allographs/statements`: `{ok: true}`, with `entry` when the statement is about the signer's own
    listing."""
    return request("POST", need_session(sess).registry, f"{API}/statements", signed, sess)


def say(sess: Session, signer: ListingKey, says: str, /, **fields: Any) -> dict:
    """Fetch a challenge, build the statement, sign it with the listing's key and send it."""
    sess = need_session(sess)
    nonce = challenge(sess)
    return send(sess, sign(statement(says, signer.tag, nonce, **fields), signer))


def list_allograph(sess: Session, key: ListingKey, *, name: str, allograph: dict, dangler: str | None = None,
                   owner: str | None = None, show: dict | None = None) -> dict:
    """Publish the listing, or replace the one its key has (`list`, 14.8)."""
    return say(sess, key, "list", key=key.key, name=check_name(name), allograph=allograph,
               dangler=check_dangler(dangler) if dangler is not None else None, owner=owner, show=show)


def withdraw(sess: Session, key: ListingKey) -> dict:
    """Withdraw the listing by its key (`withdraw`, 14.13)."""
    return say(sess, key, "withdraw")


def withdraw_by_account(sess: Session, tag: str) -> dict:
    """Withdraw a listing without its key, from the account its tag is tied to (`DELETE`, 14.13)."""
    if not TAG_RE.match(str(tag)):
        raise RegistryError(f"{tag!r} is not a tag")
    return request("DELETE", need_session(sess).registry, f"{API}/{tag}", None, sess)


def prove(sess: Session, key: ListingKey, faceplace: str, handle: str, address: str) -> dict:
    return say(sess, key, "prove", faceplace=faceplace, handle=normal_handle(handle), address=address)


def unprove(sess: Session, key: ListingKey, faceplace: str, handle: str) -> dict:
    return say(sess, key, "unprove", faceplace=faceplace, handle=normal_handle(handle))


def attest(sess: Session, key: ListingKey, *, of: str, as_: str, claims: list, epoch: str, named: bool) -> dict:
    """Offer an attestation (14.9), which waits for the holder of `of` to accept it."""
    return say(sess, key, "attest", of=of, claims=claims, epoch=epoch, named=named, **{"as": as_})


def accept(sess: Session, key: ListingKey, attestation: str) -> dict:
    return say(sess, key, "accept", attestation=attestation)


def remove(sess: Session, key: ListingKey, attestation: str) -> dict:
    return say(sess, key, "remove", attestation=attestation)


def bond(sess: Session, key: ListingKey, agent: str) -> dict:
    """The owner answers for the agent (14.10): sent by an Allograph+ person's listing; the registry refuses it from
    one that is not."""
    return say(sess, key, "bond", agent=agent)


def unbond(sess: Session, key: ListingKey, agent: str) -> dict:
    return say(sess, key, "unbond", agent=agent)


def waiting(sess: Session, tag: str) -> list:
    """The attestations waiting for the holder's word: each `{attestation, statement, signature}`."""
    if not TAG_RE.match(str(tag)):
        raise RegistryError(f"{tag!r} is not a tag")
    got = request("GET", need_session(sess).registry, f"{API}/{tag}/waiting", None, sess)
    return list((got or {}).get("attestations") or []) if isinstance(got, dict) else []


# Look-ups need no account (14.11).

def entry(base: str, tag: str) -> dict | None:
    """The one entry of a tag, or None when nothing is listed under it."""
    if not TAG_RE.match(str(tag)):
        raise RegistryError(f"{tag!r} is not a tag")
    try:
        return request("GET", base, f"{API}/{tag}")
    except RegistryError as e:
        if e.status == 404:
            return None
        raise


def by_name(base: str, name: str) -> list:
    got = request("GET", base, f"{API}?name={urllib.parse.quote(check_name(name))}")
    return list((got or {}).get("entries") or []) if isinstance(got, dict) else []


def search(base: str, needs: list, *, kind: str | None = None, plus: bool | None = None,
           attested: bool | None = None, next: str | None = None) -> dict:
    """`{entries, next}` by what a person needs (14.11)."""
    if kind is not None and kind not in ("person", "agent"):
        raise RegistryError("kind is person or agent, or left out", code="bad_need")
    body = {"needs": check_needs(needs), "kind": kind, "plus": plus, "attested": attested, "next": next}
    got = request("POST", base, f"{API}/search", {k: v for k, v in body.items() if v is not None})
    return got if isinstance(got, dict) else {"entries": []}


def faceplaces(base: str) -> list:
    got = request("GET", base, f"{API}/faceplaces")
    return list((got or {}).get("faceplaces") or []) if isinstance(got, dict) else []


# ---------------------------------------------------------------------------
# What enough keeps on this machine about a listing, and the "holograph changed" notice (14.6)
# ---------------------------------------------------------------------------

def _state_file() -> Path:
    return Path.home() / "enough" / "config" / "allographs.json"


def _read_state() -> dict:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"listings": {}}
    return data if isinstance(data, dict) and isinstance(data.get("listings"), dict) else {"listings": {}}


def _write_state(data: dict) -> None:
    p = _state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def listing_record(hid: str) -> dict | None:
    rec = _read_state()["listings"].get(hid)
    return dict(rec) if isinstance(rec, dict) else None


def record_listing(hid: str, rec: dict) -> dict:
    data = _read_state()
    data["listings"][hid] = rec
    _write_state(data)
    return rec


def forget_listing(hid: str) -> None:
    data = _read_state()
    if data["listings"].pop(hid, None) is not None:
        _write_state(data)


def hid_of(folder: Any) -> str:
    """The holograph's hid, from its catalog."""
    from . import macrocosm as mc
    vol = mc.load_volume(A._root_of(folder))
    hid = str(vol.catalog.get("id") or "")[len("ascribe/"):]
    if not A.HID_RE.match(hid):
        raise RegistryError("the holograph's catalog has no ascribe/<hid> id, so no listing can be kept for it")
    return hid


def listing_status(folder: Any) -> dict:
    """What the page shows of a holograph's listing, from this machine alone (nothing is asked of the registry):
    `{hid, kind, tag, listed, registry, name, dangler, allograph, run, changed}`. `tag` is the listed one (None while
    nothing is listed from this machine; the keychain is not read); `changed` is true when the holograph has changed
    since the run the listed allograph names (Ascribe 14.6: an implementation should say so; nothing lists again by
    itself), None when that run's record is not on this machine."""
    hid = hid_of(folder)
    rec = listing_record(hid)
    # the tag as this machine recorded it: the keychain is not read to show a page (on macOS a read of the secret
    # can ask the person for their password, as enough/cloud.py's has_api_key explains)
    out: dict = {"hid": hid, "kind": A.SUBJECT_KIND.get(A.subject_of(folder)), "tag": rec.get("tag") if rec else None,
                 "listed": rec is not None, "registry": None, "name": None, "dangler": None, "allograph": None,
                 "run": None, "changed": False}
    if rec is not None:
        out.update({k: rec.get(k) for k in ("registry", "name", "dangler", "allograph", "run")})
        try:
            # None when the listed allograph's run is not on this machine: its state cannot be told
            out["changed"] = (A.holograph_state(folder) != rec["holograph"]) if rec.get("holograph") else None
        except A.AscribeError:
            out["changed"] = True               # a marker beside the catalog now withholds everything
    return out


def load_allograph(path: Path) -> tuple[dict, bytes]:
    """An allograph file as `project h as allograph` wrote it: (the document, its bytes), refused when a reader would
    refuse it."""
    try:
        data = Path(path).read_bytes()
        doc = json.loads(data)
    except (OSError, ValueError):
        raise RegistryError(f"{Path(path).name} is not an allograph's JSON") from None
    probs = A.allograph_problems(doc)
    if probs:
        raise RegistryError("the allograph would not read: " + "; ".join(probs), code="bad_allograph")
    return doc, data


def released_allograph(folder: Any, data: bytes) -> dict:
    """The release recorded for these allograph bytes in the holograph (Ascribe 13: nothing leaves unrecorded)."""
    rec = A.released(folder, sha256=hashlib.sha256(data).hexdigest())
    if rec is None or rec.get("as") != "allograph":
        raise RegistryError("these bytes are no allograph this holograph released: make it again with the holder's "
                            "program")
    return rec


def run_state(run_id: str, root: Path | None = None) -> str | None:
    """The holograph's state an allograph's run took, as the run recorded it with the engine's answer: read from the
    run's folder under the Thym root. None when the run is not on this machine."""
    from . import macrocosm as mc
    from .thym_host import host_root
    if not A.RUN_ID_RE.match(str(run_id)):
        return None
    run_dir = Path(root or host_root()) / "runs" / str(run_id)
    for p in sorted((run_dir / "candidates").glob("*-e*.cosm")) if run_dir.is_dir() else []:
        try:
            rec = mc.yaml_load(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a record that does not read answers nothing
            continue
        out = rec.get("output") if isinstance(rec, dict) and rec.get("engine") == "ascribe.thym_allograph" else None
        state = out.get("holograph") if isinstance(out, dict) else None
        if isinstance(state, str) and DIGEST_RE.match(state):
            return state
    return None


__all__ = ["ATTEST_AS", "DEFAULT_URL", "KEYCHAIN", "ListingKey", "MemoryKeychain", "PLAIN", "RegistryError",
           "Session", "TRANSPORT", "accept", "address_ok", "addresses_for", "attest", "attestation_digest", "b32",
           "bond", "by_name", "canonical", "challenge", "check_dangler", "check_name", "check_needs",
           "check_statement", "connect_url", "entry", "faceplaces", "forget_listing", "hid_of", "key_from_seed",
           "list_allograph", "listing_key", "listing_record", "listing_status", "load_allograph", "new_key",
           "normal_handle", "poll_sign_in", "proof_string", "prove", "record_listing", "released_allograph",
           "remove", "request", "run_state", "say", "search", "send", "session", "sign", "sign_out", "start_sign_in",
           "statement", "tag_of", "unbond", "unprove", "verify", "waiting", "withdraw", "withdraw_by_account"]
