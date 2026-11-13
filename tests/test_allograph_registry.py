"""The Allograph Registry from the holder's side (enough/allograph_registry.py; Ascribe 14.7 to 14.13).

The text's worked example (the key from its seed, the tag, the proof string, the signed `list` statement) is checked
byte for byte; then the statements and their refusals, the keychain seam, Connect's device flow and every operation of
the client against a stand-in registry (`FakeRegistry`, which plays Connect: it issues nonces, verifies signatures and
keeps entries). Nothing here reaches the network (`TRANSPORT` is replaced) or the OS keychain (conftest puts a
`MemoryKeychain` in `KEYCHAIN` for every test).
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import secrets
import shutil
from pathlib import Path

import pytest

from enough import allograph_registry as R
from enough import ascribe as A
from tests.test_ascribe_module import ALLO_PROG, ALLO_TRACE, SAMPLE, SPEC_ALLOGRAPH, _for_work

SEED = hashlib.sha256(b"ascribe example key: salt-and-crumb").digest()
# The text's `list` statement (Ascribe 14.8), as its holder sends it.
SPEC_LIST = ('{"signature":"McEAI8AnkwPw9kKs4825O3R5fL/grSnmuXyL1IySYZiNXpDGIE8OFUPbTZrNBG4/zt0FH7R+BHpUkMnYgo+SAQ==",'
             '"statement":{"allograph":' + SPEC_ALLOGRAPH + ',"by":"ts7de32a5bnz","dangler":"bread, slowly",'
             '"key":"xftteVFlq9JmdslFScJdILce32OfPGOKMmVyUwNEmvE=","name":"harbour-baker",'
             '"nonce":"qk5riktfj6curptnjdndclsit4","says":"list","show":{"faceplaces":"counted","same_name":true},'
             '"statement":"ascribe-statement/0"}}')
URL = "https://connect.test"            # Connect: the device flow's sign-in and sign-out (ENOUGH_CONNECT_URL)
REGISTRY = "https://registry.test"      # the registry's own address, allograph.net in life (ENOUGH_ALLOGRAPH_URL)


# ---------------------------------------------------------------------------
# The text's example
# ---------------------------------------------------------------------------

def test_the_texts_key_tag_proof_and_signed_list_statement():
    key = R.key_from_seed(SEED)
    assert key.tag == "ts7de32a5bnz" and key.key == "xftteVFlq9JmdslFScJdILce32OfPGOKMmVyUwNEmvE="
    assert R.proof_string(key.tag, "harbourboard", "harbour-baker") == "aar-ts7de32a5bnz-k7xgvdxsixco"
    assert R.proof_string(key.tag, "harbourboard", "@Harbour-Baker") == "aar-ts7de32a5bnz-k7xgvdxsixco"
    st = R.statement("list", key.tag, "qk5riktfj6curptnjdndclsit4", key=key.key, name="harbour-baker",
                     dangler="bread, slowly", allograph=json.loads(SPEC_ALLOGRAPH),
                     show={"faceplaces": "counted", "same_name": True})
    signed = R.sign(st, key)
    assert R.canonical(signed).decode("utf-8") == SPEC_LIST
    assert R.verify(json.loads(SPEC_LIST)) and R.verify(signed, key.public)
    assert "seed" not in repr(key) and SEED.hex() not in repr(key)


def test_a_tampered_statement_does_not_verify():
    signed = json.loads(SPEC_LIST)
    signed["statement"]["name"] = "harbour-bakers"
    assert not R.verify(signed)
    other = R.new_key()
    assert not R.verify(json.loads(SPEC_LIST), other.public)


def test_canonical_json_escapes_only_what_json_requires():
    assert R.canonical({"b": "é/< ", "a": "\"\\\n"}) == '{"a":"\\"\\\\\\n","b":"é/< "}'.encode("utf-8")


# ---------------------------------------------------------------------------
# Statements, names, danglers, needs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, ok", [("harbour-baker", True), ("ab", True), ("a.b-c9", True), ("a", False),
                                      ("9lives", False), ("ends-", False), ("a..b", False), ("a.-b", False),
                                      ("Harbour", False), ("a" * 33, False), ("a_b", False)])
def test_user_names(name, ok):
    if ok:
        assert R.check_name(name) == name
    else:
        with pytest.raises(R.RegistryError) as e:
            R.check_name(name)
        assert e.value.code == "bad_name"


@pytest.mark.parametrize("dangler, ok", [("bread, slowly", True), ("Ann Quill bakes", True), ("", False),
                                         ("x" * 33, False), ("two\nlines", False), ("see https://x.test", False),
                                         ("ann@example.net", False), ("ring 020 7946 0958", False),
                                         ("17 Quillfeather Lane", False)])
def test_danglers(dangler, ok):
    if ok:
        assert R.check_dangler(dangler) == dangler            # a personal name is the holder's own choice to show
    else:
        with pytest.raises(R.RegistryError):
            R.check_dangler(dangler)


def test_a_statement_carries_only_what_its_kind_names():
    key = R.key_from_seed(SEED)
    nonce = "a" * 26
    with pytest.raises(R.RegistryError, match="carries what it does not name: extra"):
        R.statement("withdraw", key.tag, nonce, extra=1)
    with pytest.raises(R.RegistryError, match="has no address"):
        R.statement("prove", key.tag, nonce, faceplace="harbourboard", handle="harbour-baker")
    with pytest.raises(R.RegistryError, match="names no owner"):
        R.statement("list", key.tag, nonce, key=key.key, name="harbour-baker", allograph=json.loads(SPEC_ALLOGRAPH),
                    owner="company:MEADOW")
    agent = {**json.loads(SPEC_ALLOGRAPH), "kind": "agent"}
    with pytest.raises(R.RegistryError, match="names its owner"):
        R.statement("list", key.tag, nonce, key=key.key, name="crumb-bot", allograph=agent)
    assert R.statement("list", key.tag, nonce, key=key.key, name="crumb-bot", allograph=agent,
                       owner="company:MEADOW")["owner"] == "company:MEADOW"
    with pytest.raises(R.RegistryError, match="would not read"):
        R.statement("list", key.tag, nonce, key=key.key, name="harbour-baker",
                    allograph={**json.loads(SPEC_ALLOGRAPH), "handle": "salt-and-crumb"})
    with pytest.raises(R.RegistryError, match="own listing"):
        R.statement("attest", key.tag, nonce, of=key.tag, claims=[{"kind": "skill", "form": "sourdough"}],
                    epoch="2026-Q4", named=True, **{"as": "client"})
    with pytest.raises(R.RegistryError, match="as is one of"):
        R.statement("attest", key.tag, nonce, of="b" * 12, claims=[{"kind": "skill", "form": "sourdough"}],
                    epoch="2026-Q4", named=True, **{"as": "friend"})
    with pytest.raises(R.RegistryError, match="nonce"):
        R.statement("withdraw", key.tag, "short")


def test_a_key_signs_only_its_own_listings_statements():
    key, other = R.key_from_seed(SEED), R.new_key()
    st = R.statement("withdraw", other.tag, "a" * 26)
    with pytest.raises(R.RegistryError, match="signs only its own listing"):
        R.sign(st, key)
    st = R.statement("list", key.tag, "a" * 26, key=other.key, name="harbour-baker",
                     allograph=json.loads(SPEC_ALLOGRAPH))
    with pytest.raises(R.RegistryError, match="carries the key that signs it"):
        R.sign(st, key)


def test_an_attestations_digest_is_over_the_attest_statements_canonical_json():
    st = R.statement("attest", "b" * 12, "a" * 26, of="ts7de32a5bnz", claims=[{"kind": "skill", "form": "sourdough"}],
                     epoch="2026-Q4", named=True, **{"as": "client"})
    want = hashlib.sha256(R.canonical(st)).hexdigest()
    assert R.attestation_digest(st) == want == R.attestation_digest({"statement": st, "signature": "x"})


def test_needs_are_match_tokens():
    assert R.check_needs([{"about": "skill", "value": " sourdough "}]) == [{"about": "skill", "value": "sourdough"}]
    for bad in ([], [{"about": "affinity", "value": "x"}], [{"about": "form"}], [{"about": "form", "value": "x"}] * 9):
        with pytest.raises(R.RegistryError) as e:
            R.check_needs(bad)
        assert e.value.code == "bad_need"


def test_faceplace_addresses():
    fp = {"faceplace": "harbourboard", "title": "Harbourboard", "handle": "[a-z0-9-]{2,30}",
          "addresses": ["https://harbourboard.test/{handle}", "https://harbourboard.test/{handle}/posts/{any}"]}
    assert R.addresses_for(fp, "@Harbour-Baker") == ["https://harbourboard.test/harbour-baker",
                                                     "https://harbourboard.test/harbour-baker/posts/{any}"]
    assert R.address_ok(fp, "harbour-baker", "https://harbourboard.test/harbour-baker/posts/a1_b")
    assert not R.address_ok(fp, "harbour-baker", "https://harbourboard.test/someone-else")
    assert not R.address_ok(fp, "harbour-baker", "https://harbourboard.test/harbour-baker/posts/a/b")
    assert not R.address_ok(fp, "x", "https://harbourboard.test/x")       # a handle outside the faceplace's shape


# ---------------------------------------------------------------------------
# The keychain: one key per listing, made on first listing, kept there and nowhere else
# ---------------------------------------------------------------------------

def test_a_listing_key_is_made_once_and_kept_in_the_keychain():
    hid = "aej6l5qrka6c6btarfiy2f7vnj"
    assert isinstance(R.KEYCHAIN, R.MemoryKeychain)             # conftest's: never the OS keychain
    assert R.listing_key(hid) is None
    key = R.listing_key(hid, create=True)
    assert R.listing_key(hid) == key and R.listing_key(hid, create=True) == key
    (service, user), = R.KEYCHAIN.items
    assert (service, user) == ("enough/allograph", hid)
    assert json.loads(R.KEYCHAIN.items[(service, user)]) == {"seed": base64.b64encode(key.seed).decode(),
                                                            "tag": key.tag}
    assert R.listing_key("b" * 26, create=True) != key           # one key for each listing
    with pytest.raises(R.RegistryError):
        R.listing_key("not-a-hid")


def test_a_scratch_server_keeps_its_keychain_in_memory(monkeypatch):
    monkeypatch.setenv("ENOUGH_KEYCHAIN", "memory")
    kc = R.OSKeychain()
    import keyring

    def no(*a, **k):
        raise AssertionError("the OS keychain was reached")
    monkeypatch.setattr(keyring, "get_password", no)
    monkeypatch.setattr(keyring, "set_password", no)
    kc.set("enough/allograph", "x", "v")
    assert kc.get("enough/allograph", "x") == "v"
    kc.delete("enough/allograph", "x")
    assert kc.get("enough/allograph", "x") is None


# ---------------------------------------------------------------------------
# A stand-in registry, as Connect would serve it
# ---------------------------------------------------------------------------

class FakeRegistry:
    """Plays Connect's registry (14.12) closely enough for the client: nonces per account, signatures verified
    against the listing's key, a listing per tag, proofs, attestations waiting and accepted, bonds, and the device
    flow. `calls` keeps every request as (method, path, body, token). The device flow is asked of Connect's address
    (`URL`) and everything else of the registry's (`REGISTRY`); the two may be one, as at the uicheck stand-in."""

    TOKEN = "cct_test-token"

    def __init__(self) -> None:
        self.calls: list = []
        self.nonces: set = set()
        self.listings: dict = {}
        self.waiting: dict = {}
        self.proofs: dict = {}
        self.bonds: set = set()
        self.approved = False
        self.faceplaces = [{"faceplace": "harbourboard", "title": "Harbourboard", "handle": "[a-z0-9-]{2,30}",
                            "addresses": ["https://harbourboard.test/{handle}"]}]

    def __call__(self, method: str, url: str, body, token):
        if url.startswith(URL + "/api/v0/device/"):
            path = url[len(URL):]
        else:
            assert url.startswith(REGISTRY + "/api/v0/allographs"), url
            path = url[len(REGISTRY):]
        self.calls.append((method, path, copy.deepcopy(body), token))
        if path == "/api/v0/device/code":
            return 200, {"device_code": "dev-1", "user_code": "ABCD-EFGH", "verification_uri": URL + "/device",
                         "verification_uri_complete": URL + "/device?code=ABCD-EFGH", "interval": 5,
                         "expires_in": 600}
        if path == "/api/v0/device/token":
            if not self.approved:
                return 200, {"error": "authorization_pending"}
            return 200, {"access_token": self.TOKEN, "token_type": "Bearer", "expires_in": 86400, "org": None,
                         "account": {"uid": "u1"}}
        if path == "/api/v0/device/revoke":
            return 200, {"revoked": True}
        if path == "/api/v0/allographs/faceplaces":
            return 200, {"faceplaces": self.faceplaces}
        if path == "/api/v0/allographs/search":
            hits = [self.entry(t) for t, ls in sorted(self.listings.items())
                    if all(any(c["form"] == n["value"] and n["about"] in (c["kind"], "form")
                               for c in ls["statement"]["allograph"]["expertise"]) for n in body["needs"])]
            return 200, {"entries": hits}
        if path.startswith("/api/v0/allographs?name="):
            name = path.split("=", 1)[1]
            return 200, {"entries": [self.entry(t) for t, ls in sorted(self.listings.items())
                                     if ls["statement"]["name"] == name]}
        if path == "/api/v0/allographs/challenge":
            if token != self.TOKEN:
                return 401, {"error": "signed_out", "detail": "Sign in."}
            n = base64.b32encode(secrets.token_bytes(20)).decode().lower()[:26]
            self.nonces.add(n)
            return 200, {"nonce": n, "until": "later"}
        if path == "/api/v0/allographs/statements":
            return self.statement(body, token)
        if method == "DELETE":
            tag = path.rsplit("/", 1)[1]
            self.listings.pop(tag, None)
            return 200, {"withdrawn": True}
        if path.endswith("/waiting"):
            tag = path.split("/")[-2]
            return 200, {"attestations": [{"attestation": d, **s} for d, s in self.waiting.get(tag, {}).items()]}
        tag = path.rsplit("/", 1)[1]
        if tag in self.listings:
            return 200, self.entry(tag)
        return 404, {"error": "not_listed", "detail": "Nothing is listed under that tag."}

    def entry(self, tag: str) -> dict:
        ls = self.listings[tag]
        st = ls["statement"]
        return {"entry": "ascribe-entry/0", "tag": tag, "name": st["name"], "kind": st["allograph"]["kind"],
                "epoch": st["allograph"]["epoch"], "level": "stated",
                "claims": [dict(c, level="stated", attested=[]) for c in st["allograph"]["expertise"]],
                "signed": ls}

    def key_of(self, by: str):
        ls = self.listings.get(by)
        return ls["statement"]["key"] if ls else None

    def statement(self, signed, token):
        if token != self.TOKEN:
            return 401, {"error": "signed_out", "detail": "Sign in."}
        st = signed["statement"]
        if st["nonce"] not in self.nonces:
            return 400, {"error": "bad_nonce", "detail": "That nonce was not issued, or was taken."}
        self.nonces.discard(st["nonce"])
        key = st["key"] if st["says"] == "list" else self.key_of(st["by"])
        if key is None:
            return 404, {"error": "not_listed", "detail": "No listing."}
        if not R.verify(signed, key):
            return 400, {"error": "bad_signature", "detail": "No."}
        says, tag = st["says"], st["by"]
        if says == "list":
            self.listings[tag] = signed
            return 200, {"ok": True, "entry": self.entry(tag)}
        if says == "withdraw":
            self.listings.pop(tag, None)
            return 200, {"ok": True}
        if says == "prove":
            if st["address"] != f"https://harbourboard.test/{st['handle']}":
                return 400, {"error": "bad_address", "detail": "Not an address of that handle."}
            self.proofs[(tag, st["faceplace"], st["handle"])] = st["address"]
            return 200, {"ok": True, "entry": self.entry(tag)}
        if says == "unprove":
            self.proofs.pop((tag, st["faceplace"], st["handle"]), None)
            return 200, {"ok": True}
        if says == "attest":
            self.waiting.setdefault(st["of"], {})[R.attestation_digest(st)] = signed
            return 200, {"ok": True}
        if says in ("accept", "remove"):
            got = self.waiting.get(tag, {}).pop(st["attestation"], None)
            return (200, {"ok": True}) if got else (404, {"error": "not_listed", "detail": "No such attestation."})
        if says == "bond":
            if len([p for p in self.proofs if p[0] == tag]) < 2:
                return 403, {"error": "not_allowed", "detail": "An owner is an Allograph+."}
            self.bonds.add((tag, st["agent"]))
            return 200, {"ok": True}
        if says == "unbond":
            self.bonds.discard((tag, st["agent"]))
            return 200, {"ok": True}
        return 400, {"error": "bad_statement", "detail": "?"}


@pytest.fixture
def fake(monkeypatch) -> FakeRegistry:
    reg = FakeRegistry()
    monkeypatch.setattr(R, "TRANSPORT", reg)
    monkeypatch.setenv("ENOUGH_CONNECT_URL", URL)
    monkeypatch.setenv("ENOUGH_ALLOGRAPH_URL", REGISTRY)
    return reg


def test_the_conftest_seams_point_nowhere():
    import os
    assert os.environ["ENOUGH_CONNECT_URL"] == "http://127.0.0.1:1" and R.connect_url() == "http://127.0.0.1:1"
    assert os.environ["ENOUGH_ALLOGRAPH_URL"] == "http://127.0.0.1:1" and R.registry_url() == "http://127.0.0.1:1"
    assert os.environ["ENOUGH_KEYCHAIN"] == "memory"


def test_two_addresses_connect_s_for_the_sign_in_and_the_registry_s_for_the_rest(fake, monkeypatch):
    sess = _signed_in(fake)
    assert sess.url == URL and sess.registry == REGISTRY and fake.TOKEN not in repr(sess)
    R.list_allograph(sess, R.key_from_seed(SEED), name="harbour-baker", allograph=json.loads(SPEC_ALLOGRAPH))
    R.search(R.registry_url(), [{"about": "skill", "value": "sourdough"}])
    R.sign_out()
    paths = [c[1] for c in fake.calls]
    assert paths[:2] == ["/api/v0/device/code", "/api/v0/device/token"] and paths[-1] == "/api/v0/device/revoke"
    assert "/api/v0/allographs/challenge" in paths and "/api/v0/allographs/statements" in paths
    # the defaults, with neither variable set: Connect for the sign-in, allograph.net for the registry
    monkeypatch.delenv("ENOUGH_CONNECT_URL")
    monkeypatch.delenv("ENOUGH_ALLOGRAPH_URL")
    assert R.connect_url() == "https://compriseconnect.com" and R.registry_url() == "https://allograph.net"
    assert R.Session("https://compriseconnect.com", "t").registry == "https://allograph.net"
    monkeypatch.setenv("ENOUGH_ALLOGRAPH_URL", "http://allograph.example")
    with pytest.raises(R.RegistryError, match="the Allograph Registry is reached over https"):
        R.registry_url()


@pytest.mark.parametrize("url, ok", [("https://compriseconnect.com", True), ("http://localhost:8095", True),
                                     ("http://connect.test", False), ("ftp://x.test", False), ("", False)])
def test_connects_address(url, ok):
    if ok:
        assert R.normalize_url(url + "/") == url
    else:
        with pytest.raises(R.RegistryError):
            R.normalize_url(url)


def test_signing_in_by_the_device_flow_keeps_the_token_in_the_keychain(fake):
    assert R.session() is None
    got = R.start_sign_in(device="a test machine")
    assert got["user_code"] == "ABCD-EFGH" and "device_code" not in got
    assert fake.calls[0][2] == {"client": "enough", "device": "a test machine"}
    assert R.poll_sign_in() == {"state": "pending", "interval": 5}
    fake.approved = True
    assert R.poll_sign_in()["state"] == "signed_in"
    sess = R.session()
    assert sess is not None and sess.token == fake.TOKEN and fake.TOKEN not in repr(sess)
    (service, user), = R.KEYCHAIN.items
    assert (service, user) == ("enough/connect/connect.test", "token")

    def no_read(*a):
        raise AssertionError("the keychain was read again in the same process")
    R.KEYCHAIN.get = no_read                       # the session is read once a process, and kept in memory
    assert R.session().token == fake.TOKEN
    del R.KEYCHAIN.get
    R._SESSIONS.clear()
    assert R.session().token == fake.TOKEN         # a new process reads it from the keychain
    with pytest.raises(R.RegistryError, match="no sign-in is waiting"):
        R.poll_sign_in()
    assert R.sign_out() is True and R.session() is None
    assert fake.calls[-1][1] == "/api/v0/device/revoke" and fake.calls[-1][3] == fake.TOKEN


def _signed_in(fake: FakeRegistry) -> R.Session:
    R.start_sign_in()
    fake.approved = True
    R.poll_sign_in()
    return R.session()


def test_every_operation_against_the_stand_in_registry(fake):
    sess = _signed_in(fake)
    me = R.key_from_seed(SEED)
    allo = json.loads(SPEC_ALLOGRAPH)
    got = R.list_allograph(sess, me, name="harbour-baker", allograph=allo, dangler="bread, slowly",
                           show={"faceplaces": "counted", "same_name": True})
    assert got["ok"] and got["entry"]["tag"] == me.tag
    sent = next(c[2] for c in fake.calls if c[1] == "/api/v0/allographs/statements")
    assert R.verify(sent) and sent["statement"]["allograph"] == allo
    assert R.entry(REGISTRY, me.tag)["name"] == "harbour-baker" and R.entry(REGISTRY, "b" * 12) is None
    assert [e["tag"] for e in R.by_name(REGISTRY, "harbour-baker")] == [me.tag]
    assert [e["tag"] for e in R.search(REGISTRY, [{"about": "skill", "value": "sourdough"}])["entries"]] == [me.tag]
    assert R.search(REGISTRY, [{"about": "experience", "value": "sourdough"}])["entries"] == []
    # proofs
    with pytest.raises(R.RegistryError) as e:
        R.prove(sess, me, "harbourboard", "harbour-baker", "https://harbourboard.test/someone")
    assert e.value.code == "bad_address" and e.value.status == 400
    R.prove(sess, me, "harbourboard", "@Harbour-Baker", "https://harbourboard.test/harbour-baker")
    assert ("ts7de32a5bnz", "harbourboard", "harbour-baker") in fake.proofs
    R.unprove(sess, me, "harbourboard", "harbour-baker")
    assert fake.proofs == {}
    # an attestation from another listing waits, and is accepted by its digest
    client = R.new_key()
    R.list_allograph(sess, client, name="meadow-mill", allograph=allo)
    R.attest(sess, client, of=me.tag, as_="client", claims=[{"kind": "skill", "form": "sourdough"}],
             epoch="2026-Q4", named=True)
    row, = R.waiting(sess, me.tag)
    digest = R.attestation_digest(row["statement"])
    assert row["attestation"] == digest
    R.accept(sess, me, digest)
    assert R.waiting(sess, me.tag) == []
    with pytest.raises(R.RegistryError) as e:
        R.remove(sess, me, digest)
    assert e.value.status == 404
    # a bond needs an Allograph+: two live proofs
    agent = R.new_key()
    with pytest.raises(R.RegistryError) as e:
        R.bond(sess, me, agent.tag)
    assert e.value.code == "not_allowed" and "Allograph+" in str(e.value)
    fake.proofs.update({(me.tag, "a", "x"): "", (me.tag, "b", "x"): ""})
    R.bond(sess, me, agent.tag)
    R.unbond(sess, me, agent.tag)
    assert fake.bonds == set()
    # withdrawn, by the key and by the account
    R.withdraw(sess, me)
    assert R.entry(REGISTRY, me.tag) is None
    R.withdraw_by_account(sess, client.tag)
    assert fake.listings == {}
    # every statement went with the account's token and a fresh nonce, used once
    sent = [c for c in fake.calls if c[1] == "/api/v0/allographs/statements"]
    assert all(c[3] == fake.TOKEN for c in sent)
    assert len({c[2]["statement"]["nonce"] for c in sent}) == len(sent)


def test_signed_out_is_refused_before_anything_is_sent(fake):
    with pytest.raises(R.RegistryError) as e:
        R.withdraw(None, R.key_from_seed(SEED))
    assert e.value.status == 401 and e.value.code == "signed_out" and fake.calls == []
    stale = R.Session(URL, "cct_revoked")
    with pytest.raises(R.RegistryError) as e:
        R.withdraw(stale, R.key_from_seed(SEED))
    assert e.value.code == "signed_out" and "Sign in to Connect" in str(e.value)


def test_a_refusal_is_said_in_plain_words(fake):
    sess = _signed_in(fake)
    fake.nonces = set()

    def stale_challenge(s):
        return "a" * 26
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(R, "challenge", stale_challenge)
        with pytest.raises(R.RegistryError) as e:
            R.list_allograph(sess, R.key_from_seed(SEED), name="harbour-baker", allograph=json.loads(SPEC_ALLOGRAPH))
    assert e.value.code == "bad_nonce" and "challenge had expired" in str(e.value)


# ---------------------------------------------------------------------------
# What this machine keeps, and the "holograph changed" notice (14.6)
# ---------------------------------------------------------------------------

@pytest.fixture
def holo(tmp_path: Path) -> Path:
    root = tmp_path / "self"
    shutil.copytree(SAMPLE, root)
    _for_work(root)
    return root


def test_the_listing_status_says_when_the_holograph_has_changed_since_the_listed_run(holo, tmp_path):
    st = R.listing_status(holo)
    assert st["listed"] is False and st["tag"] is None and st["kind"] == "person" and st["changed"] is False
    hid = R.hid_of(holo)
    key = R.listing_key(hid, create=True)
    R.record_listing(hid, {"registry": REGISTRY, "tag": key.tag, "name": "harbour-baker", "dangler": None,
                           "kind": "person", "allograph": "self.allograph-x.json", "run": ALLO_TRACE["run"],
                           "sha256": "0" * 64, "holograph": A.holograph_state(holo)})
    st = R.listing_status(holo)
    assert st["listed"] and st["tag"] == key.tag and st["changed"] is False

    def no_read(*a):
        raise AssertionError("the keychain was read to show a page")
    R.KEYCHAIN.get = no_read
    assert R.listing_status(holo)["tag"] == key.tag
    del R.KEYCHAIN.get
    assert (Path.home() / "enough" / "config" / "allographs.json").is_file()
    assert "harbour-baker" not in (holo / "holograph.cosm").read_text(encoding="utf-8")   # never in the holograph
    A.project_allograph(holo, epoch="2026-Q4", program=ALLO_PROG, trace=ALLO_TRACE)
    assert R.listing_status(holo)["changed"] is False            # a release is not a change of the self
    from tests.test_ascribe_module import node, write_nodes
    write_nodes(holo, "U/more.cosm", node("U:understanding/rising", visibility="public"))
    assert R.listing_status(holo)["changed"] is True
    R.forget_listing(hid)
    assert R.listing_status(holo)["listed"] is False


def test_the_state_a_run_took_is_read_from_its_record(holo, tmp_path):
    import datetime as dt
    from enough import thym
    from enough import thym_host as H
    from enough.thym import run as RUN
    from enough.thym.values import digest_path
    from tests.test_ascribe_module import OPEN_FOR_WORK
    prog = tmp_path / "open-for-work.thym"
    prog.write_text(OPEN_FOR_WORK, encoding="utf-8")
    pl = thym.plan_file(prog, [{"name": "h", "type": "volume", "path": str(holo), "sha256": digest_path(holo)}])
    t = RUN.run(pl, inputs_root=tmp_path, root=tmp_path / "thym", program=prog, engines=H.engines(feed=None),
                now=dt.datetime(2026, 11, 12, 9, 30, tzinfo=dt.timezone.utc))
    assert t.landed, t.refusal
    assert R.run_state(t.run_id, root=tmp_path / "thym") == A.holograph_state(holo)
    assert R.run_state("2026-11-12-0000-ffff", root=tmp_path / "thym") is None
    assert R.run_state("../etc", root=tmp_path / "thym") is None
