"""enough/specs.py and the vendored client (0.5.4): the specifications kept current from cosmoes.org.

The client is cosmoes-site's, unchanged; one sync against a loopback stand-in for cosmoes.org (W3a's test-server
pattern: the manifest and the sources built from the bundled texts, one text changed, one made invalid) fills the
specs root, the viewer's resolution (`docoes.spec_source`) switches to the synced copy, the docs volume rebuilds from
it, a second launch costs one conditional request; the launch check is off by the seam and by the preference; the
validator refuses what does not build; "its section N" never links to the citing document; every section another
text cites exists; a "Changes" section is the decisions source. Every test is offline: the stand-in is on 127.0.0.1.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from enough import __version__
from enough import cosmoes_client as cc
from enough import docoes as D
from enough import macrocosm as mc
from enough import specs as S

REPO = Path(__file__).resolve().parents[1]
SLUGS = ("macrocosm-oes", "thym", "ascribe", "comprise-oes")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundled(slug: str) -> bytes:
    return (REPO / D.DOCUMENTS[slug].sources["en"]).read_bytes()


# ------------------------------------------------------------------------------------------------ the stand-in

class Fake:
    """A cosmoes.org in miniature on 127.0.0.1: the four documents' sources (the bundled texts unless changed), a
    manifest built from them with the host set to this port (the client's loopback allowance), an ETag, a request
    log. `docs`: {slug: (bytes, edition, revised)}."""

    def __init__(self):
        self.docs = {s: (bundled(s), D.document_version(s), "2026-11-03") for s in SLUGS}
        self.requests: list[tuple[str, dict]] = []
        self.etag = '"m1"'
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.fake = self
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def manifest(self) -> bytes:
        docs = []
        for slug, (data, edition, revised) in self.docs.items():
            docs.append({"slug": slug, "name": D.DOCUMENTS[slug].name, "edition": edition, "version": edition,
                         "revised": revised, "host": f"127.0.0.1:{self.port}",
                         "source": {"path": f"specs/{slug}.md", "sha256": sha(data), "bytes": len(data)},
                         "files": {}, "raw": {"source": f"/raw/{slug}/source.md"}})
        return json.dumps({"format": cc.FORMAT, "exported": "2026-11-03T00:00:00Z", "by": "enough/test",
                           "documents": docs}).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        fake: Fake = self.server.fake
        fake.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
        if self.path == "/manifest.json":
            if self.headers.get("If-None-Match") == fake.etag:
                self.send_response(304)
                self.send_header("ETag", fake.etag)
                self.end_headers()
                return
            body = fake.manifest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", fake.etag)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        m = re.fullmatch(r"/raw/([a-z-]+)/source\.md", self.path)
        if m and m.group(1) in fake.docs:
            body = fake.docs[m.group(1)][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def fake():
    f = Fake()
    try:
        yield f
    finally:
        f.close()


@pytest.fixture(autouse=True)
def _fresh_check():
    S.reset_for_tests()
    yield
    S.reset_for_tests()


def _wait(t: threading.Thread | None) -> None:
    assert t is not None
    t.join(60)
    assert not t.is_alive()


# ------------------------------------------------------------------------------------------------ the client

def test_the_vendored_client_is_cosmoes_site_s_unchanged():
    """One file, byte for byte cosmoes-site's `client/cosmoes_client.py`, the commit it was taken from recorded in
    docs/specs.json beside its sha256 (the sync writes both). A fix goes to cosmoes-site and is taken again."""
    body = json.loads((REPO / D.SPECS_JSON).read_text(encoding="utf-8"))
    client = body["client"]
    assert client["path"] == "enough/cosmoes_client.py" and client["source"] == "client/cosmoes_client.py"
    assert re.fullmatch(r"[0-9a-f]{7,}", client["commit"])
    assert sha((REPO / client["path"]).read_bytes()) == client["sha256"]
    head = (REPO / client["path"]).read_text(encoding="utf-8")[:1200]
    assert "THE CANONICAL COPY of this file is cosmoes-site `client/cosmoes_client.py`" in head
    assert (cc.VERSION, cc.DOMAIN, cc.FORMAT, cc.KINDS) == ("1", "cosmoes.org", "docoes-export/1",
                                                            ("source", "short", "atem", "fabula"))
    assert S.USER_AGENT == f"cosmoes-client/1 (enough {__version__})" and S.SLUGS == SLUGS
    with pytest.raises(ValueError):
        cc.CosmoesClient(base="https://example.com")                        # nothing off cosmoes.org, ever


def test_one_sync_fills_the_root_and_the_viewer_reads_the_synced_copy(fake, tmp_path, monkeypatch):
    """The launch check against the stand-in: one manifest request and one per source, every text validated by the
    real DocOES build; thym changed (edition 99.0.0, newer than any bundled one: since 0.7 an older synced copy is
    set aside) and ascribe made invalid. Afterwards `spec_source` reads the
    synced copies, the volume rebuilds from thym's new text under the new edition, ascribe stays bundled (the
    previous copy is kept on a failed validation), and a second launch costs one conditional request (304)."""
    shipped = D.bundled_editions()["thym"]["edition"]
    changed = bundled("thym").replace(f"*Edition {shipped} ".encode(), b"*Edition 99.0.0 ", 1) + b"\n## 23. Added by the test\n\nA new section.\n"
    assert changed != bundled("thym")
    fake.docs["thym"] = (changed, "99.0.0", "2026-11-04")
    fake.docs["ascribe"] = (b"\xff\xfe not utf-8", "99.0.0", "2026-11-04")
    root = tmp_path / "specs"
    monkeypatch.setenv("ENOUGH_SPECS_ROOT", str(root))
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "1")
    monkeypatch.setenv("ENOUGH_COSMOES_BASE", fake.base)
    docs_root = tmp_path / "docoes"
    monkeypatch.setenv("ENOUGH_DOCS_ROOT", str(docs_root))
    before = D.digest("thym")
    assert D.spec_info("thym")["source"] == "bundled"

    _wait(S.launch_check({"specs_sync": True}))
    st = S.status({"specs_sync": True})
    assert st["ran"] and st["checked"] and st["running"] is False and st["reason"] is None
    assert sorted(tuple(p) for p in st["updated"]) == [("comprise-oes", "source"), ("macrocosm-oes", "source"),
                                                       ("thym", "source")]
    assert st["unchanged"] == [] and st["elapsed"] is not None and st["at"] and st["base"] == fake.base
    assert [tuple(e[:2]) for e in st["errors"]] == [("ascribe", "source")] and "validation" in st["errors"][0][2]
    paths = [p for p, _h in fake.requests]
    assert paths.count("/manifest.json") == 1 and sorted(p for p in paths if p != "/manifest.json") == \
        sorted(f"/raw/{s}/source.md" for s in SLUGS)
    assert all(h["user-agent"] == S.USER_AGENT for _p, h in fake.requests)
    # The folder, as the client leaves it; the resolution follows.
    assert (root / "thym" / "source.md").read_bytes() == changed and not (root / "ascribe").exists()
    state = cc.load_state(root)
    assert state["documents"]["thym"]["version"] == "99.0.0" and "ascribe" not in state["documents"]
    info = D.spec_info("thym")
    assert (info["source"], info["version"], info["revised"], info["path"]) == \
        ("cosmoes", "99.0.0", "2026-11-04", root / "thym" / "source.md")
    assert D.spec_source("thym") == root / "thym" / "source.md" and D.document_version("thym") == "99.0.0"
    assert D.spec_info("ascribe")["source"] == "bundled" and D.spec_source("ascribe") == REPO / "docs" / "ASCRIBE.md"
    assert D.spec_info("macrocosm-oes")["source"] == "cosmoes"            # fetched on the first fill, same bytes
    assert D.digest("thym") != before                                      # the digest moved: a rebuild on next open
    vol = mc.load_volume(D.build("thym", "en"))
    assert vol.name == "Thym" and vol.catalog["document"]["version"] == "99.0.0"
    assert vol.catalog["document"]["source"] == "cosmoes" and vol.catalog["document"]["revised"] == "2026-11-04"
    assert vol.catalog["document"]["path"] == str(root / "thym" / "source.md")
    assert D.compile_doc(vol) == changed.decode("utf-8") and vol.item("S:section/23") is not None
    assert st["documents"]["thym"]["edition"] == "99.0.0" and st["documents"]["ascribe"]["source"] == "bundled"
    # One check per launch: a second call in this process is a no-op.
    n = len(fake.requests)
    assert S.launch_check({"specs_sync": True}) is not None and len(fake.requests) == n
    # The next launch: one conditional request (a 304: the kept manifest stands), nothing current fetched again —
    # only the text that never validated is asked for once more, and refused once more.
    S.reset_for_tests()
    _wait(S.launch_check({"specs_sync": True}))
    st2 = S.status({})
    assert st2["checked"] and st2["updated"] == [] and len(fake.requests) == n + 2
    assert fake.requests[-2][0] == "/manifest.json" and fake.requests[-2][1]["if-none-match"] == '"m1"'
    assert fake.requests[-1][0] == "/raw/ascribe/source.md"
    assert sorted(tuple(p) for p in st2["unchanged"]) == [("comprise-oes", "source"), ("macrocosm-oes", "source"),
                                                          ("thym", "source")]
    assert [tuple(e[:2]) for e in st2["errors"]] == [("ascribe", "source")]


def test_the_launch_check_is_off_by_the_seam_and_by_the_preference(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("ENOUGH_SPECS_ROOT", str(tmp_path / "specs"))
    monkeypatch.setenv("ENOUGH_COSMOES_BASE", fake.base)
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "0")
    assert S.launch_check({"specs_sync": True}) is None
    st = S.status({"specs_sync": True})
    assert (st["ran"], st["reason"], st["allowed"], st["enabled"]) == (False, "ENOUGH_SPECS_SYNC=0", False, True)
    monkeypatch.setenv("ENOUGH_SPECS_SYNC", "1")
    assert S.launch_check({"specs_sync": False}) is None
    st = S.status({"specs_sync": False})
    assert (st["ran"], st["reason"], st["allowed"], st["enabled"]) == (False, "preference off", True, False)
    assert fake.requests == [] and not (tmp_path / "specs").exists()
    assert S.preference_on({}) and S.preference_on(None) and S.preference_on({"specs_sync": "no"})
    assert not S.preference_on({"specs_sync": False})
    assert S.cosmoes_base() == fake.base
    monkeypatch.delenv("ENOUGH_COSMOES_BASE")
    assert S.cosmoes_base() == "https://cosmoes.org"
    # A base the client refuses is a line in the status, never an exception out of the server.
    monkeypatch.setenv("ENOUGH_COSMOES_BASE", "https://evil.example")
    _wait(S.launch_check({}))
    st = S.status({})
    assert st["ran"] and not st["checked"] and st["errors"][0][:2] == ["*", "client"] and "ValueError" in st["errors"][0][2]


# ------------------------------------------------------------------------------------------------ the newer copy wins

def _lay(root: Path, slug: str, version, data: bytes | None = None) -> Path:
    """A synced copy as the client leaves one: `<root>/<slug>/source.md` and its line in state.json (sha256 of the
    file, the edition as `version`; `version=None` leaves the edition out)."""
    data = data if data is not None else bundled(slug) + b"\n## 99. Synced only\n\nA section the bundled text lacks.\n"
    (root / slug).mkdir(parents=True, exist_ok=True)
    (root / slug / "source.md").write_bytes(data)
    try:
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    except OSError:
        state = {"checked": "2026-11-12T00:00:00Z", "updated": "2026-11-12T00:00:00Z", "etag": None, "documents": {}}
    doc = {"name": D.DOCUMENTS[slug].name, "revised": "2026-11-12", "host": f"{slug}.cosmoes.org",
           "kinds": {"source": {"sha256": sha(data), "fetched": "2026-11-12T00:00:00Z"}}}
    if version is not None:
        doc["version"] = version
    state["documents"][slug] = doc
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return root / slug / "source.md"


def test_the_newer_of_the_bundled_and_the_synced_copy_wins(tmp_path, monkeypatch):
    """Tracker specs-newer-copy-wins (0.7, the same rule as Comprise's): the editions compare as tuples of integers
    and the newer is shown; equal editions keep the synced copy (it may carry a later revision); a synced copy whose
    edition does not read falls back to the bundled text. The signed 0.6.0 build showed MacroCOSM OES at 0.5.4 —
    the last major's synced copy — until its next sync got through; that is the first case here."""
    root = tmp_path / "specs"
    monkeypatch.setenv("ENOUGH_SPECS_ROOT", str(root))
    shipped = D.bundled_editions()
    # A miniature install whose docs/specs.json bundles thym at 0.6.0 exactly, whatever this checkout carries.
    mini = tmp_path / "mini"
    (mini / "docs").mkdir(parents=True)
    body = json.loads((REPO / D.SPECS_JSON).read_text(encoding="utf-8"))
    for d in body["documents"]:
        d["edition"] = "0.6.0"
        (mini / d["path"]).write_bytes((REPO / d["path"]).read_bytes())
    (mini / D.SPECS_JSON).write_text(json.dumps(body), encoding="utf-8")
    bundled_thym = mini / "docs" / "THYM.md"

    # Bundled 0.6.0 beside a synced 0.5.4: the bundled text, its provenance saying so, the older copy named.
    _lay(root, "thym", "0.5.4")
    info = D.spec_info("thym", sources=mini)
    assert (info["source"], info["version"], info["path"], info["set_aside"]) == ("bundled", "0.6.0", bundled_thym,
                                                                                  "0.5.4")
    assert info["revised"] == shipped["thym"]["revised"] and info["home"] == "https://thym.cosmoes.org/"
    assert D.spec_source("thym", sources=mini) == bundled_thym and D.document_version("thym", sources=mini) == "0.6.0"
    # Synced 0.6.1 beside bundled 0.6.0: the synced copy.
    synced = _lay(root, "thym", "0.6.1")
    info = D.spec_info("thym", sources=mini)
    assert (info["source"], info["version"], info["path"], info["set_aside"]) == ("cosmoes", "0.6.1", synced, None)
    assert info["revised"] == "2026-11-12" and info["home"] == "https://thym.cosmoes.org/"
    # Equal editions: the synced copy (a later revision of the same edition); "0.6" is the edition "0.6.0".
    for v in ("0.6.0", "0.6"):
        _lay(root, "thym", v)
        info = D.spec_info("thym", sources=mini)
        assert (info["source"], info["version"], info["path"]) == ("cosmoes", v, synced), v
    # Integers, not strings: 0.10.0 is newer than 0.6.0 (a string compare says older); 0.5.10 is older.
    _lay(root, "thym", "0.10.0")
    assert D.spec_info("thym", sources=mini)["source"] == "cosmoes"
    _lay(root, "thym", "0.5.10")
    assert D.spec_info("thym", sources=mini)["source"] == "bundled"
    # A synced copy with no readable edition falls back to the bundled text.
    for v in (None, "", "draft", "v0.7.0", 7):
        _lay(root, "thym", v)
        info = D.spec_info("thym", sources=mini)
        assert (info["source"], info["version"], info["path"]) == ("bundled", "0.6.0", bundled_thym), v
    # The digest follows the copy shown: setting a stale copy aside rebuilds from the bundled text.
    _lay(root, "thym", "0.5.4")
    aside = D.digest("thym", sources=mini)
    _lay(root, "thym", "0.6.1")
    assert D.digest("thym", sources=mini) != aside
    # An install whose docs/specs.json is missing has no bundled edition: a readable synced copy is shown.
    bare = tmp_path / "bare"
    (bare / "docs").mkdir(parents=True)
    (bare / "docs" / "THYM.md").write_bytes(bundled("thym"))
    assert D.spec_info("thym", sources=bare)["source"] == "cosmoes"
    # The edition key itself.
    assert D.edition_key("0.6.0") == D.edition_key("0.6") == (0, 6) and D.edition_key(" 1.2.3 ") == (1, 2, 3)
    assert D.edition_key("0.10.0") > D.edition_key("0.6.1") > D.edition_key("0.6.0") > D.edition_key("0.5.4")
    assert [D.edition_key(x) for x in (None, "", "x", "1..2", "1.2.", 3, "v1")] == [None] * 7


def test_the_status_says_which_copy_is_shown(tmp_path, monkeypatch):
    """`GET /api/specs-status`'s documents (what QA and the viewer read): `source` is the copy shown, `set_aside`
    the edition of an older synced copy the bundled text was preferred to; the doc volume's catalog follows."""
    root = tmp_path / "specs"
    monkeypatch.setenv("ENOUGH_SPECS_ROOT", str(root))
    monkeypatch.setenv("ENOUGH_DOCS_ROOT", str(tmp_path / "docoes"))
    shipped = D.bundled_editions()
    _lay(root, "macrocosm-oes", "0.5.4")
    _lay(root, "ascribe", shipped["ascribe"]["edition"])
    docs = S.documents()
    m = docs["macrocosm-oes"]
    assert (m["source"], m["edition"], m["set_aside"]) == ("bundled", shipped["macrocosm-oes"]["edition"], "0.5.4")
    assert m["path"] == str(REPO / "docs" / "MACROCOSM_OES.md")
    a = docs["ascribe"]
    assert (a["source"], a["edition"], a["set_aside"]) == ("cosmoes", shipped["ascribe"]["edition"], None)
    assert docs["thym"]["source"] == "bundled" and docs["thym"]["set_aside"] is None
    vol = mc.load_volume(D.build("macrocosm-oes", "en"))
    assert vol.catalog["document"]["source"] == "bundled"
    assert vol.catalog["document"]["version"] == shipped["macrocosm-oes"]["edition"]


# ------------------------------------------------------------------------------------------------ the validator

def test_the_validator_builds_the_candidate_for_real(tmp_path, monkeypatch):
    monkeypatch.setenv("ENOUGH_DOCS_ROOT", str(tmp_path / "docoes"))
    assert D.validate_spec_source("thym", "source", bundled("thym")) is None
    assert D.validate_spec_source("comprise-oes", "source", bundled("comprise-oes")) is None
    assert D.validate_spec_source("thym", "source", b"# Thym\n\nOne line.\n") is None       # small, but it builds
    assert "not UTF-8" in D.validate_spec_source("thym", "source", b"\xff\xfe")
    assert "no title" in D.validate_spec_source("thym", "source", b"no heading here\n")
    assert "no title" in D.validate_spec_source("thym", "source", b"   \n")
    assert "only a specification's source" in D.validate_spec_source("thym", "short", b"<article/>")
    assert "not a specification" in D.validate_spec_source("help-center", "source", b"# x\n")
    assert "not a specification" in D.validate_spec_source("oes", "source", b"# x\n")
    assert not list((tmp_path / "docoes").glob("*")) if (tmp_path / "docoes").exists() else True   # nothing lands there


# ------------------------------------------------------------------------------------------------ the texts

def test_its_section_never_links_to_the_citing_document():
    """"<Name> (<home>), its section N" is another document's section: the core's `_SEC_REF`, the exporter's
    `XREF_RE` and the viewer's `DOCS_XREF_RE` all skip it; a plain "section N" still links."""
    text = ("# T\n\n## 1. A\n\nSee Thym (https://thym.cosmoes.org/), its section 2, and section 2 of this text; "
            "Its section 1 is theirs too.\n\n## 2. B\n\nx\n")
    cat = D.enumerate_markdown(text, doc_id="doc/t", source_path="t.md")
    by = {n["id"]: n for n in cat["nodes"]}
    assert by["S:section/1"]["mentions"] == ["S:section/2"]
    from enough import docoes_html as X
    hits = [m.group(0) for m in X.XREF_RE.finditer("its section 2, Its section 1, section 2 and sections 3 to 4")]
    assert hits == ["section 2", "sections 3 to 4"]
    html = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const DOCS_XREF_RE"):html.index("const DOCS", html.index("const DOCS_XREF_RE") + 10)]
    assert "(?<![Ii]ts\\\\s)" in block


def _headings(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"^#{2,6}\s+((?:P\.)?\d+(?:\.\d+)*)\b", text, re.M):
        out.add(m.group(1))
    return out


def test_every_section_another_text_cites_exists(tmp_path):
    """Each "<Name> …, its section N" (or "its sections N, M and K") in the four bundled texts names a section that
    exists in that document's headings. Misses are reported, not fixed: the texts are cosmoes-site's."""
    texts = {s: bundled(s).decode("utf-8") for s in SLUGS}
    heads = {s: _headings(t) for s, t in texts.items()}
    names = {"MacroCOSM OES": "macrocosm-oes", "Thym": "thym", "Ascribe": "ascribe", "Comprise OES": "comprise-oes"}
    # The texts' shapes: "([Thym](https://thym.cosmoes.org/), its section 15.3)", "(Thym, its section 15, https://…)",
    # "the footer line of MacroCOSM OES, its section 18.4.4". Nothing between the name and "its" may be another name.
    names_re = "MacroCOSM OES|Thym|Ascribe|Comprise OES"
    cite = re.compile(rf"\b({names_re})\b(?:(?!{names_re})[^;\n]){{0,80}}?\bits sections? "
                      r"((?:P\.)?\d+(?:\.\d+)*(?:(?:,\s*|\s+and\s+|\s+or\s+)(?:P\.)?\d+(?:\.\d+)*)*)")
    found, misses = 0, []
    for slug, text in texts.items():
        flat = re.sub(r"(?<!\n)\n(?!\n)", " ", text)                     # the texts are hard-wrapped
        for m in cite.finditer(flat):
            target = names[m.group(1)]
            if target == slug:
                continue
            for num in re.findall(r"(?:P\.)?\d+(?:\.\d+)*", m.group(2)):
                found += 1
                if num not in heads[target]:
                    misses.append(f"{slug} cites {target} section {num}: no such heading")
    assert found >= 13, found                                           # Thym 4, Ascribe 8, Comprise OES 1
    assert misses == [], "\n".join(misses)


def test_a_changes_section_is_the_decisions_source():
    """The texts end with a dated "Changes" appendix, newest first: every item of every edition's list (numbered or
    bulleted, with or without a bold lead) and an edition's entry that has no list is a decision, numbered through
    the section, carrying its edition and date. A "Decisions …" heading still works as before."""
    text = """# T

## 1. A

Text with a **word** in it.

## 2. Changes

<!-- atem: what each edition changed -->
Each entry records what changed.

**Edition 0.5.4 · 2026-11-03, second revision.** One more rule, in section 1.

**Edition 0.5.4 · 2026-11-03.** The canonical edition. Section 1 was renamed.

**Edition 0.5.3 · 2026-11-02.** Two notes:

- The first bullet cites section 1. It goes on
  onto a second line.
- **A bold lead.** The rest of it.

**Version 0 · 2026-10-01.** The first version.

1. **One rule.** Said once (section 1).
2. **Two rules.**
"""
    cat = D.enumerate_markdown(text, doc_id="doc/t", source_path="t.md")
    decisions = [n for n in cat["nodes"] if n["type"] == "decision"]
    assert [d["id"] for d in decisions] == [f"S:decision/{i}" for i in range(1, 7)]
    assert [d["number"] for d in decisions] == ["1", "2", "3", "4", "5", "6"]
    assert [d["name"] for d in decisions] == ["Edition 0.5.4 · 2026-11-03, second revision",
                                             "Edition 0.5.4 · 2026-11-03", "The first bullet cites section 1",
                                             "A bold lead", "One rule", "Two rules"]
    assert [d["edition"] for d in decisions] == ["0.5.4", "0.5.4", "0.5.3", "0.5.3", "0", "0"]
    assert [d["dated"] for d in decisions] == ["2026-11-03", "2026-11-03", "2026-11-02", "2026-11-02", "2026-10-01",
                                              "2026-10-01"]
    assert decisions[0]["summary"] == "One more rule, in section 1." and decisions[0]["about"] == ["S:section/1"]
    assert decisions[1]["summary"] == "The canonical edition." and decisions[1]["about"] == ["S:section/1"]
    assert decisions[2]["about"] == ["S:section/1"] and decisions[2]["body"].count("\n") == 2
    assert decisions[3]["summary"] == "The rest of it." and decisions[4]["about"] == ["S:section/1"]
    assert all(d["in"] == "S:section/2" for d in decisions)
    assert D.compile_doc(cat) == text
    for d in decisions:
        assert D.atem_problems(d["atem"]) == [], d["atem"]
    legacy = D.enumerate_markdown(text.replace("## 2. Changes", "## 2. Decisions in this version"), doc_id="doc/t",
                                  source_path="t.md")
    old = [n for n in legacy["nodes"] if n["type"] == "decision"]
    assert [d["name"] for d in old] == ["One rule", "Two rules"] and "edition" not in old[0]
    assert Counter(n["type"] for n in cat["nodes"])["decision"] == 6
