"""The Allograph Registry's routes (enough/allograph_api.py; Ascribe 4.2, 14.6 to 14.13), through the app.

A holograph in a scratch project, its allograph made by `POST /api/ascribe/allograph` (nothing sent), then every route
the page calls: Connect's sign-in, the subject, the listing and what this machine keeps of it, the "holograph changed"
notice, withdrawal, proofs, attestations, bonds and the look-ups. The registry is `FakeRegistry` behind
`allograph_registry.TRANSPORT`; the keychain is conftest's `MemoryKeychain`. Each route that sends refuses with 401
while this machine is not signed in to Connect.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import allograph_registry as R
from enough import ascribe as A
from enough import models, skeleton
from enough.server import create_app
from tests.test_allograph_registry import URL, FakeRegistry
from tests.test_ascribe_module import OPEN_FOR_WORK, SAMPLE, _for_work, node, write_nodes


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    live = tmp_path / "live-models.json"
    live.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", live)
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copytree(SAMPLE, proj / "self")
    _for_work(proj / "self")
    (proj / "open-for-work.thym").write_text(OPEN_FOR_WORK, encoding="utf-8")
    skeleton.ensure_skeleton(proj)
    return proj


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeRegistry:
    reg = FakeRegistry()
    monkeypatch.setattr(R, "TRANSPORT", reg)
    monkeypatch.setenv("ENOUGH_CONNECT_URL", URL)
    return reg


@pytest.fixture
def client(project: Path, fake: FakeRegistry):
    app = create_app(project, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c


def sign_in(client: TestClient, fake: FakeRegistry) -> None:
    r = client.post("/api/connect/sign-in")
    assert r.status_code == 200 and r.json()["user_code"] == "ABCD-EFGH", r.text
    assert client.post("/api/connect/poll").json()["state"] == "pending"
    fake.approved = True
    assert client.post("/api/connect/poll").json()["state"] == "signed_in"


def make(client: TestClient) -> dict:
    r = client.post("/api/ascribe/allograph", json={"path": "self", "program": "open-for-work.thym"})
    assert r.status_code == 200, r.text
    return r.json()


def test_connect_sign_in_and_out(client, fake):
    st = client.get("/api/connect/status").json()
    assert st == {"url": URL, "signed_in": False, "account": None}
    sign_in(client, fake)
    st = client.get("/api/connect/status").json()
    assert st["signed_in"] is True and st["account"] == {"uid": "u1"} and "token" not in json.dumps(st)
    assert client.post("/api/connect/sign-out").json() == {"signed_out": True}
    assert client.get("/api/connect/status").json()["signed_in"] is False


def test_every_sending_route_refuses_plainly_when_not_signed_in(client, fake, project):
    made = make(client)
    for path, body in [("/api/allograph/list", {"path": "self", "allograph": made["allograph"],
                                                "name": "harbour-baker"}),
                       ("/api/allograph/withdraw", {"path": "self"}),
                       ("/api/allograph/prove", {"path": "self", "faceplace": "harbourboard", "handle": "x",
                                                 "address": "https://harbourboard.test/x"}),
                       ("/api/allograph/unprove", {"path": "self", "faceplace": "harbourboard", "handle": "x"}),
                       ("/api/allograph/accept", {"path": "self", "attestation": "0" * 64}),
                       ("/api/allograph/remove", {"path": "self", "attestation": "0" * 64}),
                       ("/api/allograph/attest", {"path": "self", "of": "b" * 12}),
                       ("/api/allograph/bond", {"path": "self", "agent": "b" * 12}),
                       ("/api/allograph/unbond", {"path": "self", "agent": "b" * 12})]:
        r = client.post(path, json=body)
        assert r.status_code == 401 and "not signed in to Connect" in r.json()["detail"], (path, r.text)
    r = client.get("/api/allograph/waiting", params={"path": "self"})
    assert r.status_code == 401
    assert not any(c[1] == "/api/v0/allographs/statements" for c in fake.calls)       # nothing was sent
    assert R.KEYCHAIN.items == {}                                                     # and no key was made


def test_list_an_allograph_then_the_holograph_changes_then_withdraw(client, fake, project):
    made = make(client)
    assert made["document"]["kind"] == "person" and fake.calls == []             # made and shown: sent nowhere
    st = client.get("/api/allograph/listing", params={"path": "self"}).json()
    assert st["listed"] is False and st["tag"] is None and st["signed_in"] is False
    sign_in(client, fake)
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"],
                                                 "name": "harbour-baker", "dangler": "bread, slowly",
                                                 "show": {"faceplaces": "counted", "same_name": True}})
    assert r.status_code == 200, r.text
    out = r.json()
    tag = out["listing"]["tag"]
    assert out["entry"]["tag"] == tag and out["listing"]["listed"] and out["listing"]["changed"] is False
    signed = fake.listings[tag]
    assert R.verify(signed) and signed["statement"]["allograph"] == made["document"]
    # nothing of the holograph went but the allograph: no hid, no handle, no node's words
    sent = json.dumps(signed)
    assert "aej6l5qrka6c6btarfiy2f7vnj" not in sent and "salt-and-crumb" not in sent and "a test node" not in sent
    # the release record never names the listing
    assert tag not in (project / "self" / "holograph.cosm").read_text(encoding="utf-8")
    # the holograph changes: the page is told, and nothing is listed again by itself
    write_nodes(project / "self", "U/more.cosm", node("U:understanding/rising", visibility="public"))
    st = client.get("/api/allograph/listing", params={"path": "self"}).json()
    assert st["changed"] is True and st["run"] == made["run"]
    again = make(client)
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": again["allograph"],
                                                 "name": "harbour-baker"})
    assert r.status_code == 200 and r.json()["listing"]["tag"] == tag            # one key per listing: the same tag
    assert client.get("/api/allograph/listing", params={"path": "self"}).json()["changed"] is False
    # look-ups need no account
    found = client.post("/api/allograph/search", json={"needs": [{"about": "skill", "value": "sourdough"}]}).json()
    assert [e["tag"] for e in found["entries"]] == [tag]
    e = client.get("/api/allograph/entry", params={"tag": tag}).json()["entry"]
    assert e["verified"] is True and e["name"] == "harbour-baker"
    assert client.get("/api/allograph/entry", params={"tag": "b" * 12}).json() == {"entry": None}
    # withdrawn: gone there, forgotten here; the key stays, so a new listing keeps its tag
    r = client.post("/api/allograph/withdraw", json={"path": "self"})
    assert r.status_code == 200 and r.json() == {"path": "self", "withdrawn": True, "tag": tag}
    assert fake.listings == {}
    assert client.get("/api/allograph/listing", params={"path": "self"}).json()["listed"] is False


def test_list_refuses_what_is_not_this_holographs_released_allograph(client, fake, project):
    made = make(client)
    sign_in(client, fake)
    other = project / "self.allograph-forged.json"
    other.write_bytes((project / made["allograph"]).read_bytes().replace(b"strong", b"slight"))
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": other.name, "name": "harbour-baker"})
    assert r.status_code == 400 and "no allograph this holograph released" in r.json()["detail"]
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"], "name": "H!"})
    assert r.status_code == 400 and "user name" in r.json()["detail"]
    A.set_subject(project / "self", "character")
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"],
                                                 "name": "crumb-bot"})
    assert r.status_code == 400 and "make it again" in r.json()["detail"]
    assert fake.listings == {}


def test_a_characters_holograph_lists_an_agent_with_its_owner(client, fake, project):
    r = client.post("/api/ascribe/subject", json={"path": "self", "subject": "character"})
    assert r.status_code == 200 and r.json() == {"path": "self", "subject": "character", "kind": "agent"}
    assert A.subject_of(project / "self") == "character"
    made = make(client)
    assert made["document"]["kind"] == "agent"
    sign_in(client, fake)
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"], "name": "crumb-bot"})
    assert r.status_code == 403 and "names its owner" in r.json()["detail"]
    r = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"], "name": "crumb-bot",
                                                 "owner": "company:MEADOW"})
    assert r.status_code == 200, r.text
    assert r.json()["listing"]["kind"] == "agent"
    for path, body in [("/api/allograph/proof", {"faceplace": "harbourboard", "handle": "x"}),
                       ("/api/allograph/attest", {"of": "b" * 12}), ("/api/allograph/bond", {"agent": "b" * 12})]:
        r = client.post(path, json={"path": "self", **body})
        assert r.status_code == 403 and "agent's listing does not" in r.json()["detail"], path
    r = client.post("/api/ascribe/subject", json={"path": "self", "subject": "robot"})
    assert r.status_code == 400


def test_proofs_attestations_and_bonds_through_the_routes(client, fake, project):
    made = make(client)
    sign_in(client, fake)
    r = client.post("/api/allograph/proof", json={"path": "self", "faceplace": "harbourboard", "handle": "x"})
    assert r.status_code == 409 and "list its allograph first" in r.json()["detail"]
    tag = client.post("/api/allograph/list", json={"path": "self", "allograph": made["allograph"],
                                                   "name": "harbour-baker"}).json()["listing"]["tag"]
    r = client.post("/api/allograph/proof", json={"path": "self", "faceplace": "harbourboard",
                                                  "handle": "@Harbour-Baker"})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["proof"] == R.proof_string(tag, "harbourboard", "harbour-baker")
    assert got["addresses"] == ["https://harbourboard.test/harbour-baker"] and got["handle"] == "harbour-baker"
    r = client.post("/api/allograph/proof", json={"path": "self", "faceplace": "elsewhere", "handle": "x"})
    assert r.status_code == 400 and "does not check that faceplace" in r.json()["detail"]
    r = client.post("/api/allograph/prove", json={"path": "self", "faceplace": "harbourboard",
                                                  "handle": "harbour-baker",
                                                  "address": "https://harbourboard.test/harbour-baker"})
    assert r.status_code == 200 and (tag, "harbourboard", "harbour-baker") in fake.proofs
    assert client.post("/api/allograph/unprove", json={"path": "self", "faceplace": "harbourboard",
                                                       "handle": "harbour-baker"}).status_code == 200
    # another listing attests; the attestation waits for this holder's word
    client_key = R.new_key()
    sess = R.session()
    R.list_allograph(sess, client_key, name="meadow-mill", allograph=made["document"])
    R.attest(sess, client_key, of=tag, as_="client", claims=[{"kind": "skill", "form": "sourdough"}],
             epoch="2026-Q4", named=False)
    rows = client.get("/api/allograph/waiting", params={"path": "self"}).json()["attestations"]
    assert len(rows) == 1 and rows[0]["statement"]["of"] == tag
    r = client.post("/api/allograph/accept", json={"path": "self", "attestation": rows[0]["attestation"]})
    assert r.status_code == 200, r.text
    assert client.get("/api/allograph/waiting", params={"path": "self"}).json()["attestations"] == []
    # this listing attests another's work
    r = client.post("/api/allograph/attest", json={"path": "self", "of": client_key.tag, "as": "colleague",
                                                   "claims": [{"kind": "skill", "form": "sourdough"}],
                                                   "epoch": "2026-Q4", "named": True})
    assert r.status_code == 200 and fake.waiting[client_key.tag]
    # a bond: refused by the registry until this listing is an Allograph+
    agent = R.new_key()
    r = client.post("/api/allograph/bond", json={"path": "self", "agent": agent.tag})
    assert r.status_code == 403 and "Allograph+" in r.json()["detail"]
    fake.proofs.update({(tag, "a", "x"): "", (tag, "b", "x"): ""})
    assert client.post("/api/allograph/bond", json={"path": "self", "agent": agent.tag}).status_code == 200
    assert client.post("/api/allograph/unbond", json={"path": "self", "agent": agent.tag}).status_code == 200
    assert client.get("/api/allograph/faceplaces").json()["faceplaces"][0]["faceplace"] == "harbourboard"


def test_an_unreachable_connect_is_a_502_in_words(client, monkeypatch):
    def down(method, url, body, token):
        raise R.RegistryError(R.PLAIN["unreachable"], None, "unreachable")
    monkeypatch.setattr(R, "TRANSPORT", down)
    r = client.post("/api/allograph/search", json={"needs": [{"about": "form", "value": "sourdough"}]})
    assert r.status_code == 502 and "could not be reached" in r.json()["detail"]
    r = client.post("/api/allograph/search", json={"needs": []})
    assert r.status_code == 400
