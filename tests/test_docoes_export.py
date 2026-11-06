"""The DocOES export (enough/docoes_html.py, `python -m enough.docoes export`): a doc volume as static HTML at the
three densities, docs.css and a merged manifest.json (docs/thym-landed-X1.md section 2).

Every fast test exports a miniature install written here — a crafted spec, a mini Thym and Comprise OES, the real
manifests, two ad hoc documents — never the real 2,600-line spec; the last test exports the real three documents
once and checks them against the survey's counts. Volumes are built into tmp dirs (the export's own temporary
directory, or `--docs-root` under tmp_path); conftest points ENOUGH_DOCS_ROOT into tmp_path as well.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest

from enough import docoes as D
from enough import docoes_html as X
from enough import macrocosm as mc

REPO = Path(__file__).resolve().parents[1]

MINI_SPEC = """# MacroCOSM OES

<!-- atem: the grammar every miniature is written in -->
MacroCOSM OES is the grammar. Read section 1 first, and sections 2 to 3 after.

## How to read this

| Here | In the files | Example |
|---|---|---|
| volume | `catalog.cosm` | `canon.cosm` |

## 1. Volumes

<!-- atem: what a volume is, and what names it -->
A **catalog** is the file that names a volume. See section 2.1, §2 of Comprise, README §1 and P.1. Thym
(https://thym.cosmoes.org/), its section 2, is Thym's own.

- **atem** — the one line every item has
- a list item that wraps
  onto a second line, with a catalog in it

A volume is never a <slug> placeholder in HTML; `<code>` stays code, and so does `section 2`.

| Field | What it holds, written long enough that the row wraps in the source |
|---|---|
| `id` | the item's id, never a catalog |

## 2. Atems

<!-- atem: the one line an item has -->
An atem is short. A catalog is mentioned here again, and section 1 too. Sections 1, 2 and 9 are listed.

### 2.1 An example

```cosm
oes: canon/1
id: canon/orchard
name: orchard
nodes: []
```

## 3. Decisions in this version

1. **Atems are short.** Because a line is enough (section 2).
2. **A catalog names a volume.** One file, one name.
"""

MINI_COMPRISE = """# Comprise OES

The specification of Comprise, in miniature.

A **concern** is one part of a company, and it has a catalog. See §2 of the plan (never linked here), section 2
and P.1.

## 1. Concerns

A concern holds a catalog of its own.

## 2. Modules

Eight modules per concern.

### P.1 Brands

A brand is a concern's face; see section 1.
"""

MINI_THYM = """# Thym 0: a language in miniature

<!-- atem: a language for moving meaning, in miniature -->
A **move** is one step of a program. Read section 1.

## 1. Moves

<!-- atem: what a move does -->
Every move has a contract; see section 2. A move is never a <name>.

## 2. Contracts

<!-- atem: what a move promises -->
A **contract** is what a move promises. {{convert-formats}}
"""

# An ad hoc document named like a manifest (`emf`), so its version is that manifest's. (Until 0.5.0's lane X2 the
# mini Thym was the ad hoc example; `thym` is a registered document now, and THYM.md exports as it.)
MINI_EMF = MINI_THYM.replace("# Thym 0: a language in miniature", "# EMF: a language in miniature")

MINI_NOTES = """# Field notes

<!-- atem: notes with no manifest of their own -->
A **note** is a line in the margin.

## 1. Notes

Notes, and more notes.
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


@pytest.fixture
def mini(tmp_path) -> Path:
    """A miniature install: the crafted spec (registered `macrocosm-oes`), a mini Thym (registered `thym`), a mini
    Comprise OES (registered `comprise-oes`), two ad hoc documents, the real manifests and docs/specs.json."""
    root = tmp_path / "install"
    _write(root, "docs/MACROCOSM_OES.md", MINI_SPEC)
    _write(root, "docs/THYM.md", MINI_THYM)
    _write(root, "docs/EMF.md", MINI_EMF)
    _write(root, "docs/FIELD_NOTES.md", MINI_NOTES)
    # 0.5.4: Comprise OES is a document of its own; the miniature carries the real docs/specs.json, so the
    # registered specifications resolve their editions (names carry no number; the edition is a field).
    _write(root, "docs/COMPRISE_OES.md", MINI_COMPRISE)
    shutil.copyfile(REPO / D.SPECS_JSON, root / D.SPECS_JSON)
    shutil.copytree(REPO / D.MANIFESTS_DIR, root / D.MANIFESTS_DIR)
    return root


def _export(src: Path, out: Path, doc: str = "macrocosm-oes", *extra: str) -> int:
    return D.main(["export", doc, str(out), "--sources", str(src), *extra])


class _Scan(HTMLParser):
    """What the checks need from a fragment: tags, ids, in-page hrefs, and per section its key, scope and terms."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.tags: Counter = Counter()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.sections: list[dict] = []
        self.links: list[dict] = []
        self._sec: dict | None = None
        self._a: dict | None = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags[tag] += 1
        if a.get("id"):
            self.ids.append(a["id"])
        href = a.get("href")
        if tag == "a" and href is not None:
            if href.startswith("#"):
                self.hrefs.append(href[1:])
            self._a = {"class": a.get("class", ""), "href": href, "term": a.get("data-term"), "text": "",
                       "section": self._sec}
            self.links.append(self._a)
        if tag == "section":
            self._sec = {"class": a.get("class", ""), "key": a.get("data-key"), "scope": a.get("data-scope"),
                         "terms": []}
            self.sections.append(self._sec)
        if tag == "a" and "docs-term" in a.get("class", "") and self._sec is not None:
            self._sec["terms"].append(a.get("data-term"))

    def handle_endtag(self, tag):
        if tag == "section":
            self._sec = None
        if tag == "a":
            self._a = None

    def handle_data(self, data):
        if self._a is not None:
            self._a["text"] += data


def _fragment_ok(text: str, *, crafted: bool = True) -> _Scan:
    for bad in ("<script", "<style", ' style="', "<html", "<head", "<body"):
        assert bad not in text, bad
    sc = _Scan(text)
    assert sc.tags["h1"] == 1
    assert sc.tags["article"] >= 1 and text.startswith('<article class="docoes docoes-')
    dup = [k for k, n in Counter(sc.ids).items() if n > 1]
    assert not dup, dup
    assert not set(sc.hrefs) - set(sc.ids), sorted(set(sc.hrefs) - set(sc.ids))
    if crafted:                                     # the crafted sources hold no dates, so neither may a fragment
        assert not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d", text)
    return sc


# ---------------------------------------------------------------------------
# The registered document, with chapters and the reference
# ---------------------------------------------------------------------------

def test_the_export_writes_three_fragments_css_and_a_manifest(mini, tmp_path, capsys):
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    assert "0 dangling" in capsys.readouterr().out
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "docs.css", "macrocosm-oes/atem.html", "macrocosm-oes/fabula.html", "macrocosm-oes/short.html",
        "manifest.json"]
    css = (out / "docs.css").read_text(encoding="utf-8")
    assert ".docoes a.docs-term" in css and "var(--ink, #1a1f2b)" in css and "overflow-x: auto" in css
    assert not [ln for ln in css.splitlines() if ln and not ln.startswith((" ", "}", "/*", ".docoes", "@media",
                                                                           "body.docoes-page", "   "))]
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["format"] == "docoes-export/1" and man["css"] == "docs.css" and man["standalone"] is False
    assert man["by"] == f"enough/{D.ENOUGH_VERSION}" and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",
                                                                      man["exported"])
    assert man["source"] == {"commit": None, "dirty": None}                  # the miniature is not a checkout
    assert man["pages"] == {"short": "short.html", "atem": "atem.html", "fabula": "fabula.html"}
    (entry,) = man["documents"]
    assert entry["slug"] == "macrocosm-oes" and entry["name"] == "MacroCOSM OES"
    assert entry["version"] == D.document_version("macrocosm-oes", sources=mini) != ""    # its edition (specs.json)
    assert entry["id"] == "doc/macrocosm-oes" and entry["oes"] == "doc/1"
    assert entry["lead"] == "the grammar every miniature is written in"
    assert entry["source"] == {"path": "docs/MACROCOSM_OES.md",
                               "sha256": hashlib.sha256(MINI_SPEC.encode("utf-8")).hexdigest()}
    assert entry["chapters"] == []                                            # no chapters since 0.5.4
    c = entry["counts"]
    assert c["sections"] >= 6 and c["terms"] >= 3 and c["examples"] == 1 and c["decisions"] == 2
    assert c["reference"] > 50                                               # the R: items of the real manifests
    for dens, f in entry["files"].items():
        data = (out / f["path"]).read_bytes()
        assert f["path"] == f"macrocosm-oes/{dens}.html"
        assert f["sha256"] == hashlib.sha256(data).hexdigest() and f["bytes"] == len(data)


def test_every_fragment_is_clean_unique_and_self_contained(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    for dens in X.DENSITIES:
        text = (out / "macrocosm-oes" / f"{dens}.html").read_text(encoding="utf-8")
        _fragment_ok(text)
        assert f'data-density="{dens}"' in text and 'data-doc="macrocosm-oes"' in text and 'data-lang="en"' in text
        assert '<nav class="docoes-contents" aria-label="Contents"><ol>' in text
        assert '<div class="docoes-body">' in text


def test_the_short_density(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    text = (out / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    sc = _fragment_ok(text)
    vol_secs = [s for s in sc.sections if "docs-glossary" not in s["class"]]
    assert vol_secs and all(s["key"] and s["scope"] is not None for s in vol_secs)
    assert [s["key"] for s in vol_secs][:3] == ["S:section/root", "S:section/how-to-read-this", "S:section/1"]
    assert {s["scope"] for s in vol_secs} == {""}                                 # one document, no chapters
    # Heading ids as the app's, the levels as written; data-toc on h2/h3.
    assert '<h1 id="docs-macrocosm-oes">MacroCOSM OES</h1>' in text
    assert '<h2 id="docs-sec-1" data-toc="2">1. Volumes</h2>' in text
    assert '<h3 id="docs-sec-2-1" data-toc="3">2.1 An example</h3>' in text
    assert "docs-comprise-" not in text and "docs-chapter-note" not in text
    # Markers dropped outside fences, placeholders shown as text, code left alone, tables wrapped.
    assert "atem:" not in re.sub(r"<pre>.*?</pre>", "", text, flags=re.S)
    assert "&lt;slug&gt;" in text and "<code>&lt;code&gt;</code>" in text and "<code>section 2</code>" in text
    assert '<div class="docs-table">\n<table>' in text
    assert '<pre><code class="language-cosm">oes: canon/1' in text
    assert "a list item that wraps\nonto a second line" in text                 # lazy continuation, one item
    # Cross-references by the spec's rules (0.5.4): §, README § and P.N name other documents' sections and are
    # never linked; "section N" is its own.
    xr = {(a["text"], a["href"]) for a in sc.links if "ref-xref" in a["class"]}
    assert ("section 2.1", "#docs-sec-2-1") in xr
    assert not [a for a in sc.links if a["text"] in ("§2", "README §1", "P.1")]
    assert ("sections 2", "#docs-sec-2") in xr and ("3", "#docs-sec-3") in xr     # a range: each number
    assert ("Sections 1", "#docs-sec-1") in xr and ("2", "#docs-sec-2") in xr
    assert not [a for a in sc.links if a["text"] == "9"]                         # names no heading: not linked
    assert '<a class="ref-xref ref-xref-num" href="#docs-sec-3">3</a>' in text
    # "its section N" (0.5.4) is another document's section: never linked, whatever number follows.
    assert "its section 2" in text and 'its <a class="ref-xref"' not in text
    # Margin marks.
    assert re.search(r'<h2 id="docs-sec-2" data-toc="2">2\. Atems</h2>\n<p class="docs-marks"><span class="docs-mark" '
                     r'title="mentioned in \d+ places?">◂ \d+</span></p>', text)
    assert '<span class="docs-mark" title="1 example">❏ 1</span>' in text


def test_term_links_and_the_glossary(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    text = (out / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    sc = _fragment_ok(text)
    vol = _volume(mini)
    terms = {k: it for k, it in vol.items.items() if it.kind == "term"}
    assert {"T:term/catalog", "T:term/atem", "T:term/volume"} <= set(terms)
    for s in sc.sections:
        assert len(s["terms"]) == len(set(s["terms"])), s["key"]               # the first use per section
        for k in s["terms"]:
            assert terms[k].data["defined_in"] != s["key"], (k, s["key"])       # never where it is defined
    by_sec = {s["key"]: s["terms"] for s in sc.sections}
    assert "T:term/catalog" not in by_sec["S:section/1"] and "T:term/catalog" in by_sec["S:section/2"]
    a = next(x for x in sc.links if x["term"] == "T:term/catalog")
    assert a["href"] == "#docs-item-t-term-catalog" and a["class"] == "docs-term"
    assert re.search(r'<a class="docs-term" href="#docs-item-t-term-catalog" data-term="T:term/catalog" '
                     r'title="[^"]+">catalog</a>', text)
    # The glossary: last, the document's terms alphabetically.
    gl = text.split('<section class="docs-sec docs-glossary" id="docs-glossary">')[1]
    assert gl.startswith('<h2 id="docs-glossary-h" data-toc="2">Terms</h2>')
    names = re.findall(r'<dt id="docs-item-t-term-[a-z0-9-]+">([^<]+)</dt>', gl.split("<h3")[0])
    assert names == sorted(names, key=str.casefold) and "catalog" in names
    assert "<h3" not in gl                                                      # no chapter's terms under their own h3
    assert ('<dt id="docs-item-t-term-catalog">catalog</dt><dd>the file that names a volume — <a class="ref-xref" '
            'href="#docs-sec-1">defined in §1 Volumes</a></dd>') in gl
    toc = text.split("</nav>")[0]
    assert toc.rstrip().endswith('<li class="lvl2"><a href="#docs-glossary-h">Terms</a></li></ol>')
    assert 'class="lvl2 chapter"' not in toc


def _volume(src: Path) -> mc.Volume:
    root = src.parent / "vol"
    return mc.load_volume(D.build("macrocosm-oes", "en", docs_root=root, sources=src), D._registry(src))


def test_the_atem_and_fabula_densities_and_page_hrefs(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out, "macrocosm-oes", "--page", "short=short", "--page", "atem=atem",
                   "--page", "fabula=fabula") == 0
    atem = (out / "macrocosm-oes" / "atem.html").read_text(encoding="utf-8")
    fab = (out / "macrocosm-oes" / "fabula.html").read_text(encoding="utf-8")
    short = (out / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    _fragment_ok(atem)
    _fragment_ok(fab)
    assert '<h1>MacroCOSM OES</h1><p class="docs-atem-lead">' not in atem          # one element a line
    assert "<h1>MacroCOSM OES</h1>\n<p class=\"docs-atem-lead\">the grammar every miniature is written in</p>" in atem
    assert ('<li class="docs-ol-top" data-depth="0"><a class="docs-ol-row" href="short#docs-sec-1"><span '
            'class="docs-ol-num">1</span> <span class="docs-ol-name">Volumes</span> <span class="docs-ol-atem">— what '
            'a volume is, and what names it</span></a></li>') in atem
    assert '<li data-depth="1"><a class="docs-ol-row" href="short#docs-sec-2-1">' in atem
    assert "docs-ol-chapter" not in atem
    for hid in ("docs-atem-outline", "docs-atem-glossary", "docs-atem-reference", "docs-atem-checks"):
        assert f'id="{hid}" data-toc=' in atem
    assert '<h3 id="docs-item-r-minicosm-comprise" data-toc="3">Comprise OES · comprise/1</h3>' in atem
    assert 'href="short#docs-sec-1">defined in §1 Volumes</a>' in atem
    assert 'href="fabula#docs-item-r-module-comprise-c">Corporation</a>' in atem
    # Fabula: a card per item, ids shared with the glossary, fields, the way back to short.
    vol = _volume(mini)
    cards = re.findall(r'<article class="docs-card" id="([^"]+)" data-kind="([^"]+)">', fab)
    assert len(cards) == len(vol.items)
    assert {c for c, _k in cards} == {X.item_id(k) for k in vol.items}
    for dt in re.findall(r'<dt id="(docs-item-[^"]+)">', short):
        assert f'id="{dt}"' in fab
    assert '<h2 id="docs-fab-s" data-toc="2">S · Structure</h2>' in fab
    assert re.search(r'<h3 id="docs-fab-s-section" data-toc="3">sections \(\d+\)</h3>', fab)
    assert '<h3 id="docs-fab-r-lens" data-toc="3">lenses (' in fab
    assert ('<p class="docs-card-read"><a class="ref-xref" href="short#docs-sec-1">read it at short</a></p>') in fab
    assert '<h4><code class="docs-card-id">S:section/1</code> Volumes</h4>' in fab
    assert '<dt>defined_in</dt><dd><a href="#docs-item-s-section-1">S:section/1</a></dd>' in fab
    assert '<pre><code class="language-cosm">oes: canon/1\nid: canon/orchard' in fab
    assert "<dt>provenance</dt><dd><code>{&quot;mode&quot;:&quot;derived&quot;" in fab
    assert "<dt>body</dt>" not in fab and "<dt>order</dt>" not in fab and "<dt>lines</dt>" not in fab
    assert '<div class="docs-card-body"><ol>\n<li><strong>Atems are short.</strong>' in fab


def test_a_second_document_merges_and_a_rerun_replaces_in_place(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    assert _export(mini, out, "docs/THYM.md") == 0
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [d["slug"] for d in man["documents"]] == ["macrocosm-oes", "thym"]
    first = (out / "macrocosm-oes" / "short.html").read_bytes()
    assert _export(mini, out, "macrocosm-oes", "--densities", "short,atem") == 0
    man2 = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [d["slug"] for d in man2["documents"]] == ["macrocosm-oes", "thym"]
    assert sorted(man2["documents"][0]["files"]) == ["atem", "short"]
    assert man2["documents"][1] == man["documents"][1]
    assert (out / "macrocosm-oes" / "short.html").read_bytes() == first          # unchanged sources: same bytes
    assert (out / "thym" / "short.html").is_file()


def test_a_markdown_path_exports_ad_hoc(mini, tmp_path):
    out = tmp_path / "site"
    assert _export(mini, out, "docs/EMF.md") == 0
    assert _export(mini, out, str(mini / "docs" / "FIELD_NOTES.md")) == 0       # absolute, inside the root
    assert _export(mini, out, "docs/FIELD_NOTES.md", "--slug", "notes", "--name", "Notes", "--version", "7") == 0
    assert _export(mini, out, "docs/MACROCOSM_OES.md", "--densities", "short") == 0   # a registered one's path
    assert _export(mini, out, "docs/THYM.md", "--densities", "short") == 0       # registered since 0.5.0 (X2)
    docs = {d["slug"]: d for d in json.loads((out / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    assert list(docs) == ["emf", "field-notes", "notes", "macrocosm-oes", "thym"]
    emf = docs["emf"]
    assert emf["name"] == "EMF: a language in miniature" and emf["id"] == "doc/emf"
    assert emf["version"] == str(mc.default_registry().by_name("emf").version)  # its manifest's (the fabula's) version
    assert emf["chapters"] == [] and emf["counts"]["reference"] == 0
    assert docs["field-notes"]["name"] == "Field notes" and docs["field-notes"]["version"] == ""
    assert docs["notes"]["name"] == "Notes" and docs["notes"]["version"] == "7"
    assert docs["macrocosm-oes"]["chapters"] == []                               # the registered document, whole
    thym = docs["thym"]                                                          # the registered one: its name
    assert (thym["name"], thym["version"], thym["id"]) == ("Thym", D.document_version("thym", sources=mini), "doc/thym")
    text = (out / "emf" / "short.html").read_text(encoding="utf-8")
    sc = _fragment_ok(text)
    assert '<p class="docs-note">' not in text                                   # inline: the note's words
    assert "(the formats table is drawn in the app)" in text and "{{convert-formats}}" not in text
    assert "&lt;name&gt;" in text
    assert ('<a class="ref-xref" href="#docs-sec-2">section 2</a>') in text      # an ad hoc document: own scope
    assert {s["scope"] for s in sc.sections if s["key"]} == {""}
    assert (out / "notes" / "fabula.html").is_file() and (out / "field-notes" / "atem.html").is_file()


def test_no_marks_leaves_the_margin_marks_out(mini, tmp_path):
    """`--no-marks`: the short density without `◂ N` / `❏ N` (cosmoes-site's build asks for it; the marks are the
    in-app viewer's buttons, inert in a static page). Nothing else changes: strip the marks from the marked export and
    the fragments are the same bytes; atem and fabula never carried them."""
    marked, bare = tmp_path / "marked", tmp_path / "bare"
    assert _export(mini, marked) == 0
    assert _export(mini, bare, "macrocosm-oes", "--no-marks") == 0
    with_marks = (marked / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    text = (bare / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    assert '<p class="docs-marks">' in with_marks and "◂" in with_marks and "❏" in with_marks
    assert "docs-mark" not in text and "◂" not in text and "❏" not in text
    assert re.sub(r'<p class="docs-marks">.*?</p>\n', "", with_marks) == text
    _fragment_ok(text)
    for dens in ("atem", "fabula"):
        assert (marked / "macrocosm-oes" / f"{dens}.html").read_bytes() == (bare / "macrocosm-oes" / f"{dens}.html").read_bytes()
    counts = [json.loads((d / "manifest.json").read_text(encoding="utf-8"))["documents"][0]["counts"] for d in (marked, bare)]
    assert counts[0] == counts[1]


def test_reference_joins_the_manifests_reference_to_an_ad_hoc_document(mini, tmp_path):
    """`--reference`: an ad hoc document carries the R: items generated from the manifests, as the registered
    MacroCOSM OES does (the same registry, the same count); without it, none."""
    out = tmp_path / "site"
    assert _export(mini, out) == 0
    assert _export(mini, out, "docs/EMF.md") == 0
    assert _export(mini, out, "docs/EMF.md", "--slug", "emf-ref", "--reference") == 0
    docs = {d["slug"]: d for d in json.loads((out / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    assert docs["emf"]["counts"]["reference"] == 0
    assert docs["emf-ref"]["counts"]["reference"] == docs["macrocosm-oes"]["counts"]["reference"] > 0
    assert docs["emf-ref"]["counts"]["sections"] == docs["emf"]["counts"]["sections"]
    assert 'id="docs-atem-reference"' not in (out / "emf" / "atem.html").read_text(encoding="utf-8")
    for dens in X.DENSITIES:
        text = (out / "emf-ref" / f"{dens}.html").read_text(encoding="utf-8")
        _fragment_ok(text)
        plain = (out / "emf" / f"{dens}.html").read_text(encoding="utf-8")
        if dens == "atem":
            assert 'id="docs-atem-reference"' in text and 'class="docs-r-name"' in text
        if dens == "fabula":
            assert text.count('<article class="docs-card"') > plain.count('<article class="docs-card"')
        if dens == "short":
            assert text.count("<section") == plain.count("<section")              # the prose is the same


def test_an_explicit_registered_slug_exports_the_path_ad_hoc(mini, tmp_path):
    """cosmoes-site keeps the texts outside enough and builds each from its path under the registered slug: the
    text alone (no chapters, the reference only with --reference), the name and version given, the spec's own
    cross-reference rules still keyed by its slug (§ and P.N name Comprise's sections, which this volume lacks, so
    they stay plain text; its own "section N" links as before)."""
    out = tmp_path / "site"
    assert _export(mini, out, "docs/MACROCOSM_OES.md", "--slug", "macrocosm-oes", "--name", "MacroCOSM OES",
                   "--version", "0.5.4", "--no-marks") == 0
    assert _export(mini, out, "docs/THYM.md", "--slug", "thym", "--name", "Thym", "--version", "0.5.4") == 0
    docs = {d["slug"]: d for d in json.loads((out / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    spec = docs["macrocosm-oes"]
    assert (spec["name"], spec["version"], spec["id"]) == ("MacroCOSM OES", "0.5.4", "doc/macrocosm-oes")
    assert spec["chapters"] == [] and spec["counts"]["reference"] == 0
    assert spec["source"]["path"] == "docs/MACROCOSM_OES.md"
    text = (out / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    sc = _fragment_ok(text)
    assert {s["scope"] for s in sc.sections if s["key"]} == {""}
    assert "docs-chapter-note" not in text and "docs-comprise" not in text and "docs-marks" not in text
    xr = {(a["text"], a["href"]) for a in sc.links if "ref-xref" in a["class"]}
    assert ("section 2.1", "#docs-sec-2-1") in xr and ("sections 2", "#docs-sec-2") in xr
    assert not [a for a in sc.links if a["text"] in ("§2", "P.1", "README §1")]
    assert "§2 of Comprise, README §1 and P.1" in text
    thym = docs["thym"]
    assert (thym["name"], thym["version"], thym["id"], thym["chapters"]) == ("Thym", "0.5.4", "doc/thym", [])
    # With --reference the same text carries the manifests' reference, as the registered document does.
    ref = tmp_path / "ref"
    assert _export(mini, ref, "docs/MACROCOSM_OES.md", "--slug", "macrocosm-oes", "--reference") == 0
    r = json.loads((ref / "manifest.json").read_text(encoding="utf-8"))["documents"][0]
    assert r["chapters"] == [] and r["counts"]["reference"] > 0 and r["counts"]["terms"] == spec["counts"]["terms"]
    # Without --slug, a registered document's path still exports the registered document, whole.
    whole = tmp_path / "whole"
    assert _export(mini, whole, "docs/MACROCOSM_OES.md") == 0
    assert json.loads((whole / "manifest.json").read_text(encoding="utf-8"))["documents"][0]["counts"]["reference"] > 50


def test_distinctive_mentions_as_the_help_center_counts_them(mini, tmp_path):
    _write(mini, "docs/ORCHARD.md", "# Orchard\n\n## 1. Rows\n\n- **row** — a line of trees\n- **graft union** — "
                                    "where two trees meet\n\n## 2. Work\n\nEvery row is walked; each graft union "
                                    "is checked.\n\n**row** by row, and **Row** as a label.\n")
    doc = D.Document("orchard", "Orchard", {"en": "docs/ORCHARD.md"}, plain_mentions="distinctive")
    r = X.export(doc, tmp_path / "site", densities=("short",), sources=mini)
    assert r["stats"]["short"]["dangling"] == []
    work = (tmp_path / "site" / "orchard" / "short.html").read_text(encoding="utf-8").split(
        'data-key="S:section/2"')[1].split("</section>")[0]
    assert 'data-term="T:term/graft-union"' in work                              # distinctive: linked
    assert "Every row is walked" in work                                         # an everyday word: not linked
    assert '<strong><a class="docs-term" href="#docs-item-t-term-row" data-term="T:term/row"' in work


def test_standalone_pages(mini, tmp_path):
    out = tmp_path / "standalone"
    assert _export(mini, out, "macrocosm-oes", "--standalone") == 0
    page = (out / "macrocosm-oes" / "atem.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>\n<html lang=\"en\">")
    assert '<meta name="robots" content="noindex">' in page and '<link rel="stylesheet" href="../docs.css">' in page
    assert "<title>MacroCOSM OES · atem</title>" in page and '<body class="docoes-page">' in page
    assert ('<nav class="docoes-densities" aria-label="Density"><a href="atem.html" aria-current="page">atem</a>'
            '<a href="short.html">short</a><a href="fabula.html">fabula</a></nav>') in page
    assert f"exported by enough/{D.ENOUGH_VERSION}</footer>" in page and "<script" not in page
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["standalone"] is True
    f = man["documents"][0]["files"]["atem"]
    assert f["sha256"] == hashlib.sha256((out / f["path"]).read_bytes()).hexdigest()


def test_the_real_docs_root_is_never_written(mini, tmp_path, monkeypatch):
    guard = tmp_path / "guarded-docoes"
    monkeypatch.setenv("ENOUGH_DOCS_ROOT", str(guard))
    assert D.docs_root() == guard
    assert _export(mini, tmp_path / "site") == 0
    assert not guard.exists()
    kept = tmp_path / "kept"
    assert _export(mini, tmp_path / "site", "macrocosm-oes", "--docs-root", str(kept)) == 0
    assert (kept / "macrocosm-oes.en.doc.cosm").is_file() and not guard.exists()


def test_exit_codes(mini, tmp_path, capsys, monkeypatch):
    out = tmp_path / "site"
    assert _export(mini, out, "nothing-here") == 2
    assert _export(mini, out, "macrocosm-oes", "--lang", "fr") == 2
    assert _export(mini, out, "macrocosm-oes", "--lang", "xx") == 2
    assert _export(mini, out, "macrocosm-oes", "--densities", "short,syuzhet") == 2
    assert _export(mini, out, "macrocosm-oes", "--page", "middle=x") == 2
    assert _export(mini, out, str(REPO / "README.md")) == 2                       # outside the sources root
    assert _export(mini, tmp_path / "ok", "docs/THYM.md", "--slug", "help-center") == 0   # an explicit registered slug: ad hoc
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "manifest.json").write_text('{"format": "something/9"}', encoding="utf-8")
    assert _export(mini, foreign) == 2
    assert sorted(p.name for p in foreign.iterdir()) == ["manifest.json"]       # refused before writing anything
    assert not out.exists()
    capsys.readouterr()

    def refused(path, registry=None):
        return mc.Volume(Path(path), refused=mc.Refusal("not a volume this reader reads"))
    monkeypatch.setattr(X.mc, "load_volume", refused)
    assert _export(mini, out) == 1
    assert "refused" in capsys.readouterr().err


def test_the_cli_lists_export(capsys):
    with pytest.raises(SystemExit):
        D.main(["--help"])
    assert "export" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        D.main(["export", "--help"])
    assert "--standalone" in capsys.readouterr().out


def test_item_ids():
    assert X.item_id("T:term/part") == "docs-item-t-term-part"
    assert X.item_id("R:kind/comprise.C.bond") == "docs-item-r-kind-comprise-c-bond"
    assert X.default_slug("docs/THYM.md") == "thym" and X.default_slug("MACROCOSM_OES.md") == "macrocosm-oes"
    assert X.default_slug("Field notes (v2).md") == "fieldnotesv2"


# ---------------------------------------------------------------------------
# The real documents, once
# ---------------------------------------------------------------------------

SURVEY = {"macrocosm-oes": {"sections": 110, "terms": 41, "examples": 8, "decisions": 38, "reference": 256},
          "thym": {"sections": 83, "terms": 12, "examples": 1, "decisions": 25},
          "ascribe": {"sections": 27, "terms": 2, "examples": 1, "decisions": 12},
          "comprise-oes": {"sections": 99, "terms": 15, "examples": 0, "decisions": 21}}


def test_the_real_four_documents(tmp_path):
    """The four bundled editions export whole (0.5.4: Comprise OES a document of its own, no chapters anywhere, the
    counts of the Changes sections' decisions, and no "its section N" linked in any of them)."""
    out = tmp_path / "site"
    for doc in ("macrocosm-oes", "docs/THYM.md", "docs/ASCRIBE.md", "docs/COMPRISE_OES.md"):
        assert D.main(["export", doc, str(out), "--page", "short=short", "--page", "atem=atem",
                       "--page", "fabula=fabula"]) == 0
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [d["slug"] for d in man["documents"]] == ["macrocosm-oes", "thym", "ascribe", "comprise-oes"]
    assert [d["name"] for d in man["documents"]] == ["MacroCOSM OES", "Thym", "Ascribe", "Comprise OES"]
    assert {d["version"] for d in man["documents"]} == {D.document_version("macrocosm-oes")}
    assert all(d["chapters"] == [] for d in man["documents"])
    for d in man["documents"]:
        for k, n in SURVEY[d["slug"]].items():
            assert d["counts"][k] >= n, (d["slug"], k)
        for dens, f in d["files"].items():
            text = (out / f["path"]).read_text(encoding="utf-8")
            assert hashlib.sha256(text.encode("utf-8")).hexdigest() == f["sha256"]
            _fragment_ok(text, crafted=False)
    spec = (out / "macrocosm-oes" / "short.html").read_text(encoding="utf-8")
    assert spec.count('class="ref-xref') > 100 and spec.count('class="docs-term"') > 700
    assert "docs-comprise-" not in spec
    for d in man["documents"]:
        for f in d["files"].values():
            text = (out / f["path"]).read_text(encoding="utf-8")
            assert not re.search(r"[Ii]ts <a class=\"ref-xref", text), (d["slug"], f["path"])
    comprise = (out / "comprise-oes" / "short.html").read_text(encoding="utf-8")
    assert 'id="docs-p-1' in comprise and '<a class="ref-xref" href="#docs-p-' in comprise   # P.N: its own chapter P
