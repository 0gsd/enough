"""DocOES routes, the inline reader, the local graph and `doc_lookup` (0.4.4, lane D2).

`GET /api/docs` at its three densities, `/api/docs/status|build|lens|compile|inventory`, `POST /api/cosm/inline`
(+ `/lens`), `GET /api/cosm/lens?around=`, `macrocosm.load_volume_text`, `to_mermaid(around=, depth=)` and the
readvisor's `doc_lookup`, in project and home mode and while agent-free.

Most tests read a miniature install (`docoes.SOURCES` pointed at tmp: a small spec, a small Help Center in English
and German, their bubbles, and the real manifests), so they never enumerate the real 2,000-line spec; one test reads
the real documents once. Built volumes land in conftest's tmp `ENOUGH_DOCS_ROOT`; no model is started.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from enough import agent_free, canon_tools, docoes, macrocosm as mc, skeleton, tools
from enough.server import HOME_PATHS, agent_free_refusal, create_app

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "docs" / "MACROCOSM_OES.md"
FIX = REPO / "tests" / "fixtures" / "cosm"
_BLOCK = re.compile(r"^```cosm\n(.*?)^```", re.S | re.M)


def _spec_blocks() -> list[str]:
    return _BLOCK.findall(SPEC.read_text(encoding="utf-8"))


def _canon_example() -> str:
    """The real spec's smallest canon/1 example, so the fixture's example is a tested file."""
    blocks = [b for b in _spec_blocks() if b.startswith("oes: canon/1")]
    return min(blocks, key=len)


FIXTURE_SPEC = """\
# Orchard spec

## Contents

1. Trees
2. Fruit
3. Decisions in this version

## 1. Trees

<!-- atem: what grows in the orchard -->
A **tree** is one plant that bears fruit every year. Section 2 says what it bears.

### 1.1 Roots

The roots hold a tree in the ground; see section 1.

## 2. Fruit

| Word | Means |
|---|---|
| **fruit** | what a tree bears in autumn |

A fruit falls from a tree (section 1.1). A small catalog:

```cosm
{example}```

## 3. Decisions in this version

1. **Trees first.** A tree comes before its fruit (section 1).
2. **Fruit second.** Fruit follows it (section 2).
"""

FIXTURE_HELP_EN = """\
# the orchard help center

## 1. Getting started

<!-- atem: how to begin with the orchard -->
Open a project first. The cheat sheet is the one page you need (section 2).

| Word | Means |
|---|---|
| **cheat sheet** | one page of every shortcut |

## 2. Shortcuts

The cheat sheet lists every shortcut there is. See section 1.
"""

FIXTURE_HELP_DE = """\
# das Obstgarten-Hilfecenter

## 1. Erste Schritte

<!-- atem: wie man mit dem Obstgarten anfängt -->
Öffne zuerst ein Projekt. Der Spickzettel ist die eine Seite, die du brauchst (Abschnitt 2).

| Wort | Bedeutung |
|---|---|
| **Spickzettel** | eine Seite mit jedem Tastenkürzel |

## 2. Tastenkürzel

Alle Tastenkürzel stehen auf dem **Spickzettel**. Siehe Abschnitt 1.
"""

FIXTURE_BUBBLES = """\
<!-- help bubbles -->

## shortcuts
name: shortcuts
path: ~/orchard/

### what
the list of every shortcut, as section 2 tells it.

### how
press the key.

## docs
name: the docs viewer
path: docs/

### what
the orchard spec; section 1 says what a tree is.
"""


@pytest.fixture
def docs_src(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A miniature install for DocOES to read, with the real manifests."""
    root = tmp_path / "install"
    files = {
        "docs/MACROCOSM_OES.md": FIXTURE_SPEC.format(example=_canon_example()),
        "docs/HELP_CENTER.md": FIXTURE_HELP_EN,
        "enough/static/i18n/de/help-center.md": FIXTURE_HELP_DE,
        "enough/static/help-docs.md": FIXTURE_BUBBLES,
        "enough/static/i18n/de/help-docs.md": FIXTURE_BUBBLES,
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    shutil.copytree(REPO / "defaults" / "cosm" / "manifests", root / "defaults" / "cosm" / "manifests")
    monkeypatch.setattr(docoes, "SOURCES", root)
    assert docoes.docs_root().is_relative_to(tmp_path)
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    shutil.copyfile(FIX / "emf" / "notes.md", proj / "notes.md")
    shutil.copyfile(FIX / "emf" / "notes.md.cosm", proj / "notes.md.cosm")
    skeleton.ensure_skeleton(proj)
    assert str(Path.home()).startswith(str(tmp_path))
    return proj


def _client(project: Path, mode: str) -> TestClient:
    return TestClient(create_app(project, "http://127.0.0.1:9", supervise=False, home=(mode == "home")))


def _docs(c: TestClient, doc: str = "macrocosm-oes", lang: str = "en", **params: str):
    return c.get("/api/docs", params={"doc": doc, "lang": lang, **params})


def set_ui(**values: Any) -> None:
    path = agent_free.ui_config_path()
    cfg: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    cfg.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg), encoding="utf-8")


def lookup(project: Path, term: str):
    call = tools.parse_tool_calls(f'<tool name="doc_lookup">\n<term>{term}</term>\n</tool>')[0]
    return tools.execute(project, call)


# ---------------------------------------------------------------------------
# The docs root and the cached loader
# ---------------------------------------------------------------------------

def test_the_docs_root_defaults_to_a_state_folder_of_its_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """~/enough/docs/ is an install's own documentation folder; built volumes go to ~/enough/docoes/."""
    monkeypatch.delenv("ENOUGH_DOCS_ROOT", raising=False)
    assert docoes.docs_root() == Path.home() / "enough" / "docoes"
    assert str(Path.home()).startswith(str(tmp_path))


def test_load_built_caches_by_file_version(docs_src: Path):
    first = docoes.load_built("help-center", "en")
    assert docoes.load_built("help-center", "en") is first
    with open(docs_src / "docs/HELP_CENTER.md", "a", encoding="utf-8") as fh:
        fh.write("\nOne more line.\n")
    assert docoes.is_fresh("help-center", "en") is False
    again = docoes.load_built("help-center", "en")
    assert again is not first and docoes.compile_doc(again).endswith("One more line.\n")
    with pytest.raises(docoes.DocsUnavailable):
        docoes.load_built("help-center", "fr")                            # no French source in this install


# ---------------------------------------------------------------------------
# The reader: a volume from text, the local graph
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("index", range(len(_spec_blocks())))
def test_load_volume_text_reads_each_spec_example_as_its_file_would(index: int, tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch):
    import tempfile
    from test_macrocosm_spec import _file_name
    text = _spec_blocks()[index]
    name = _file_name(mc.yaml_load(text))
    (tmp_path / name).write_text(text, encoding="utf-8")
    on_disk = mc.load_volume(tmp_path / name)

    def no_disk(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("load_volume_text wrote to disk")

    for fn in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, fn, no_disk)
    inline = mc.load_volume_text(text, filename=name)
    assert inline.refused is None and inline.minicosm == on_disk.minicosm
    assert list(inline.items) == list(on_disk.items)
    assert mc.lint(inline).to_dict()["errors"] == mc.lint(on_disk).to_dict()["errors"] == []
    assert inline.root is None and not inline.path.is_absolute()


def test_load_volume_text_refuses_and_reports_without_raising():
    assert mc.load_volume_text("oes: nope/9\n", filename="x.cosm").refused is not None
    bad = mc.load_volume_text("oes: canon/1\nnodes: [\n", filename="canon.cosm")
    assert bad.refused is not None and any(p.check == "load" for p in bad.problems)
    holo = (FIX / "holotypes" / "meadow" / "holotype.cosm").read_text(encoding="utf-8")
    vol = mc.load_volume_text(holo, filename="holotype.cosm")             # a folder MiniCOSM with parts
    assert vol.minicosm == "comprise" and vol.refused is None
    assert any("missing" in p.message for p in vol.problems)


def test_the_local_graph(docs_src: Path):
    vol = docoes.load_built("macrocosm-oes", "en")
    body, nm = mc.to_mermaid(vol, "graph", around="T:term/tree")
    assert body.startswith("flowchart LR\n") and "subgraph" not in body
    focus = [k for k, v in nm.items() if v.get("focus")]
    assert len(focus) == 1 and nm[focus[0]]["id"] == "T:term/tree"
    assert f"  class {focus[0]} focus;" in body and "classDef focus" in body
    drawn = {v["id"] for v in nm.values()}
    assert {"S:section/1", "S:section/1.1", "S:section/2"} <= drawn            # defined in, mentioned by
    assert "R:minicosm/canon" not in drawn                                    # three steps away
    assert {v["id"] for v in mc.to_mermaid(vol, "graph", around="T:term/tree", depth=0)[1].values()} == \
        {"T:term/tree"}
    assert "R:minicosm/canon" in {v["id"] for v in                            # tree < §2 > example 1 > canon
                                  mc.to_mermaid(vol, "graph", around="T:term/tree", depth=3)[1].values()}
    _body, small = mc.to_mermaid(vol, "graph", around="T:term/tree", max_nodes=2)
    assert any(v.get("more") for v in small.values()) and len([v for v in small.values() if v["id"]]) == 2
    mind, _ = mc.to_mermaid(vol, "map", around="S:section/2")                  # a mindmap lens: a flowchart
    assert mind.startswith("flowchart") and "class " in mind
    with pytest.raises(ValueError, match="no item"):
        mc.to_mermaid(vol, "graph", around="T:term/nothing")


# ---------------------------------------------------------------------------
# Every route, in project mode and in home mode
# ---------------------------------------------------------------------------

DOCS_ROUTES = ("/api/docs", "/api/docs/status", "/api/docs/build", "/api/docs/lens", "/api/docs/compile",
               "/api/docs/inventory", "/api/cosm/inline", "/api/cosm/inline/lens")


def test_the_routes_are_home_paths():
    assert set(DOCS_ROUTES) <= HOME_PATHS


@pytest.mark.parametrize("mode", ["project", "home"])
def test_every_docs_route_answers(docs_src: Path, project: Path, mode: str):
    example = _canon_example()
    with _client(project, mode) as c:
        for density in ("atem", "short", "fabula"):
            r = _docs(c, density=density)
            assert r.status_code == 200, (density, r.text)
            assert r.json()["density"] == density
        assert _docs(c, "help-center", "de").status_code == 200
        st = c.get("/api/docs/status")
        assert st.status_code == 200 and {(d["doc"], d["lang"]) for d in st.json()["documents"]} >= \
            {("macrocosm-oes", "en"), ("help-center", "de")}
        r = c.get("/api/docs/lens", params={"doc": "macrocosm-oes", "lang": "en", "around": "T:term/tree"})
        assert r.status_code == 200 and r.json()["around"] == "T:term/tree", r.text
        r = c.post("/api/docs/compile", json={"doc": "help-center", "lang": "de"})
        assert r.status_code == 200 and r.json()["markdown"] == FIXTURE_HELP_DE
        r = c.get("/api/docs/inventory", params={"doc": "macrocosm-oes", "lang": "en"})
        assert r.status_code == 200 and r.json()["rows"]
        r = c.post("/api/cosm/inline", json={"text": example, "filename": "canon.cosm"})
        assert r.status_code == 200 and r.json()["minicosm"] == "canon", r.text
        r = c.post("/api/cosm/inline/lens", json={"text": example, "filename": "canon.cosm", "lens": "map"})
        assert r.status_code == 200 and r.json()["text"].startswith("---\nmerirmaid: 1\n"), r.text
        r = c.post("/api/docs/build", json={"doc": "help-center", "lang": "en"})
        assert r.status_code == 202 and r.json()["building"] is True
        # The project's volumes stay project routes: home mode still 404s them.
        r = c.get("/api/cosm/lens", params={"path": "notes.md.cosm", "around": "E:person/x"})
        assert r.status_code == (404 if mode == "home" else 404)        # home: the gate; project: no such item
        if mode == "home":
            assert c.get("/api/cosm", params={"path": "notes.md.cosm"}).status_code == 404


def test_cosm_lens_draws_around_an_item_of_a_project_volume(project: Path):
    vol = mc.load_volume(project / "notes.md.cosm")
    some = next(it for it in vol.items.values() if any(True for _ in mc._edges(vol, {}, it)))
    with _client(project, "project") as c:
        r = c.get("/api/cosm/lens", params={"path": "notes.md.cosm", "around": some.id, "depth": 1})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["around"] == some.key and p["lens"] == "map"
        assert "around" in p["text"].split("---")[1] and "subgraph" not in p["text"]
        assert [v["id"] for v in p["node_map"].values() if v.get("focus")] == [some.key]
        plain = c.get("/api/cosm/lens", params={"path": "notes.md.cosm"}).json()
        assert plain["around"] is None and not any(v.get("focus") for v in plain["node_map"].values())


def test_unknown_documents_languages_and_densities(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        assert _docs(c, "nope").status_code == 404
        assert _docs(c, "help-center", "xx").status_code == 404
        assert _docs(c, density="whole").status_code == 400
        r = _docs(c, "macrocosm-oes", "de", density="atem")                  # the spec is told in English only
        assert r.status_code == 200 and (r.json()["lang"], r.json()["requested_lang"]) == ("en", "de")
        r = _docs(c, "help-center", "fr")                                     # a telling with no source here
        assert r.status_code == 503 and "help-center" in r.json()["detail"]
        assert c.get("/api/docs/lens", params={"doc": "macrocosm-oes", "around": "T:term/none"}).status_code == 404
        assert c.get("/api/docs/lens", params={"doc": "macrocosm-oes", "lens": "nope"}).status_code == 400
        r = c.post("/api/docs/compile", json={"doc": "macrocosm-oes", "chapter": "nope"})
        assert r.status_code == 404
        assert _docs(c, density="fabula", section="9").status_code == 404
        assert c.post("/api/docs/build", json={"lang": "de"}).status_code == 400


# ---------------------------------------------------------------------------
# The densities
# ---------------------------------------------------------------------------

HEAD = {"doc", "lang", "requested_lang", "density", "id", "title", "uri", "telling", "tellings", "document",
        "chapters", "built"}


def test_the_densities_shapes(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        atem, short, fab = (_docs(c, density=d).json() for d in ("atem", "short", "fabula"))
    vol = docoes.load_built("macrocosm-oes", "en")
    # atem: the head and every item, light.
    assert HEAD <= set(atem) and set(atem) - HEAD == {"items"}
    assert (atem["doc"], atem["lang"], atem["id"], atem["uri"]) == \
        ("macrocosm-oes", "en", "doc/macrocosm-oes", "oes:doc/macrocosm-oes")
    assert atem["built"]["digest"] == docoes.digest("macrocosm-oes", "en")
    assert [i["key"] for i in atem["items"]] == list(vol.items)
    row = next(i for i in atem["items"] if i["id"] == "S:section/1")
    assert {"key", "id", "kind", "module", "name", "atem", "order", "level", "parent"} <= set(row)
    assert (row["atem"], row["level"], row["parent"], row["number"]) == \
        ("what grows in the orchard", 2, "S:section/root", "1")
    assert "body" not in row and not any("body" in i for i in atem["items"])
    # short: the atem payload, sections in telling order with their bodies verbatim, the terms.
    assert set(short) - HEAD == {"items", "sections", "terms"} and short["items"] == atem["items"]
    orders = [s["order"] for s in short["sections"]]
    assert orders == sorted(orders) and len(orders) == sum(1 for it in vol.items.values() if it.kind == "section")
    assert "".join(s["heading"] + "\n" + s["body"] for s in short["sections"]) == \
        (docs_src / "docs/MACROCOSM_OES.md").read_text(encoding="utf-8")
    fruit = next(s for s in short["sections"] if s["id"] == "S:section/2")
    assert fruit["examples"] == ["S:example/1"] and fruit["anchor"] == "sec-2"
    terms = {t["id"]: t for t in short["terms"]}
    assert terms["T:term/tree"]["defined_in"] == "S:section/1"
    assert terms["T:term/fruit"]["atem"] == "what a tree bears in autumn"
    # fabula: the /api/cosm shape + backrefs, inventory, the declared lenses, no page.
    assert {"path", "minicosm", "major", "modules", "problems", "pending", "report", "files", "lenses",
            "refused", "backrefs", "inventory", "declared_lenses", "page"} <= set(fab)
    assert (fab["minicosm"], fab["path"], fab["page"]) == ("doc", "docs:macrocosm-oes.en", None)
    assert [m["letter"] for m in fab["modules"]] == ["S", "T", "R", "B"]
    assert sum(m["count"] for m in fab["modules"]) == len(vol.items)
    assert fab["report"]["errors"] == [] and fab["lenses"] == mc.lenses(vol)
    assert {d["id"]: d["kind"] for d in fab["declared_lenses"]}["inventory"] == "table"
    assert fab["inventory"] == json.loads(json.dumps(docoes.inventory(vol)))


def test_declared_lenses_carry_the_modules_they_draw(docs_src: Path, project: Path):
    """D3 (0.4.4): each lens says which modules it draws — the manifest's `include`, every module when it has
    none, and the reader's generic drawings marked `generic` — the same as the spec's R:lens/doc.* items, so the
    prism card's "renderings" needs no constant for a telling without Reference items (the Help Center)."""
    with _client(project, "home") as c:
        spec, help_de = (_docs(c, doc, lang, density="fabula").json()
                         for doc, lang in (("macrocosm-oes", "en"), ("help-center", "de")))
    for p in (spec, help_de):
        got = {d["id"]: (d["include"], d["generic"]) for d in p["declared_lenses"]}
        assert got == {"manual": (["S", "T", "R", "B"], False), "map": (["S", "T"], False),
                       "graph": (["S", "T", "R"], False), "inventory": (["S", "T", "R", "B"], False),
                       "tree": (["S", "T", "R", "B"], True)}
        assert {d["id"] for d in p["declared_lenses"] if d["kind"] == "mermaid"} == set(p["lenses"])
    # The spec's own R:lens/doc.* items say the same thing.
    items = {i["id"]: i["data"] for m in spec["modules"] for k in m["kinds"] for i in k["items"]}
    for d in spec["declared_lenses"]:
        draws = items[f"R:lens/doc.{d['id']}"]["draws"]
        assert [x.rsplit(".", 1)[1] for x in draws] == d["include"], d["id"]


def test_backrefs_and_mentioned_in(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        short, fab = (_docs(c, density=d).json() for d in ("short", "fabula"))
    data = {i["id"]: i["data"] for m in fab["modules"] for k in m["kinds"] for i in k["items"]}
    back = fab["backrefs"]
    assert {"S:section/1.1", "S:decision/1", "S:section/3"} <= set(back["S:section/1"])
    assert "S:section/root" not in back["S:section/1"]                       # the tree is not a backref
    assert {"S:section/1.1", "S:section/2"} <= set(back["T:term/tree"]) and "S:section/1" not in back["T:term/tree"]
    assert "S:example/1" in back["R:minicosm/canon"]                        # its declaration

    def names(value: Any, target: str) -> bool:
        if isinstance(value, str):
            return value == target
        if isinstance(value, dict):
            return any(names(v, target) for v in value.values())
        if isinstance(value, list):
            return any(names(v, target) for v in value)
        return False

    for target, sources in back.items():                                     # every backref is a real reference
        for src in sources:
            assert names({k: v for k, v in data[src].items() if k not in ("parts", "parent", "chapter")}, target)
    for src, d in data.items():                                              # every mention is a backref
        for t in d.get("mentions") or []:
            assert src in back[t], (src, t)
    for s in short["sections"]:                                              # mentioned_in: the prose references
        want = {src for src, d in data.items()
                if any(names(d.get(f), s["id"]) for f in ("mentions", "about", "see", "same_as", "also_defined_in"))}
        assert s["mentioned_in"] == len(want), s["id"]
    assert next(s for s in short["sections"] if s["id"] == "S:section/1")["mentioned_in"] == 3


def test_a_fabula_page_is_a_section_with_what_it_holds(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        p = _docs(c, density="fabula", section="2").json()
        keys = {i["key"] for m in p["modules"] for k in m["kinds"] for i in k["items"]}
        assert keys == {"S:section/2", "S:example/1", "T:term/fruit"}
        assert p["page"] == {"section": "2", "module": None, "count": 3, "total": p["page"]["total"]}
        p = _docs(c, density="fabula", section="S:section/1").json()
        assert {i["key"] for m in p["modules"] for k in m["kinds"] for i in k["items"]} == \
            {"S:section/1", "S:section/1.1", "T:term/tree"}
        p = _docs(c, density="fabula", module="R").json()
        assert [m["count"] for m in p["modules"] if m["letter"] != "R"] == [0, 0, 0]
        assert next(m for m in p["modules"] if m["letter"] == "R")["count"] == p["page"]["count"] > 100
        assert p["backrefs"]                                                 # the whole volume's, on every page


def test_the_help_center_fabula_resolves_the_bubble_into_the_spec(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        p = _docs(c, "help-center", "de", density="fabula").json()
    assert p["telling"]["lang"] == "de" and p["telling"]["voice"] == "rosa"
    assert "B:bubble/shortcuts" in p["backrefs"]["S:section/2"]             # the bubble's `see`
    assert not [e for e in p["report"]["errors"] if "xref" in str(e)]
    assert not [n for n in p["report"]["notes"] if "xref" in str(n)]
    bubble = next(i for m in p["modules"] for k in m["kinds"] for i in k["items"] if i["id"] == "B:bubble/docs")
    assert bubble["data"]["xrefs"] == [f"macrocosm-oes@{mc.MACROCOSM_VERSION}:section:1"]


# ---------------------------------------------------------------------------
# Building: on first use, 202 while a build runs, the background build
# ---------------------------------------------------------------------------

def test_a_build_in_progress_answers_202(docs_src: Path, project: Path, monkeypatch: pytest.MonkeyPatch):
    gate, started = threading.Event(), threading.Event()
    real = docoes.build

    def slow(*args: Any, **kwargs: Any) -> Path:
        started.set()
        assert gate.wait(20)
        return real(*args, **kwargs)

    monkeypatch.setattr(docoes, "build", slow)
    with _client(project, "home") as c:
        first: dict[str, Any] = {}
        t = threading.Thread(target=lambda: first.setdefault("r", _docs(c, density="atem")))
        t.start()
        try:
            assert started.wait(20)
            r = _docs(c, density="short")
            assert r.status_code == 202, r.text
            p = r.json()
            assert p["building"] is True and (p["doc"], p["lang"]) == ("macrocosm-oes", "en")
            assert set(p["progress"]) == {"done", "total", "current", "elapsed_s"}
            assert p["progress"]["current"] == "macrocosm-oes.en" and p["progress"]["total"] == 1
            assert c.get("/api/docs/lens", params={"doc": "macrocosm-oes"}).status_code == 202
            row = next(d for d in c.get("/api/docs/status").json()["documents"]
                       if (d["doc"], d["lang"]) == ("macrocosm-oes", "en"))
            assert row["building"] is True and row["built"] is False and row["progress"]
        finally:
            gate.set()
            t.join(20)
        assert first["r"].status_code == 200 and first["r"].json()["density"] == "atem"
        st = c.get("/api/docs/status").json()
        row = next(d for d in st["documents"] if (d["doc"], d["lang"]) == ("macrocosm-oes", "en"))
        assert (row["built"], row["fresh"], row["building"], st["building"]) == (True, True, False, False)
        assert row["digest"] == docoes.digest("macrocosm-oes", "en")
        assert _docs(c, density="short").status_code == 200


def test_the_background_build(docs_src: Path, project: Path):
    import time
    with _client(project, "home") as c:
        r = c.post("/api/docs/build", json={})
        assert r.status_code == 202 and r.json()["progress"]["total"] == 7
        for _ in range(200):
            st = c.get("/api/docs/status").json()
            if not st["building"]:
                break
            time.sleep(0.05)
        rows = {(d["doc"], d["lang"]): d for d in st["documents"]}
        assert rows[("macrocosm-oes", "en")]["fresh"] and rows[("help-center", "de")]["fresh"]
        assert not rows[("help-center", "fr")]["built"]                      # no source in this install
        assert st["ready"] is False


# ---------------------------------------------------------------------------
# Inline volumes, compile, inventory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("index", range(len(_spec_blocks())))
def test_the_spec_examples_through_the_inline_route(index: int, project: Path, tmp_path: Path):
    from test_macrocosm_spec import _file_name
    text = _spec_blocks()[index]
    name = _file_name(mc.yaml_load(text))
    (tmp_path / name).write_text(text, encoding="utf-8")
    on_disk = mc.load_volume(tmp_path / name)
    with _client(project, "home") as c:
        for filename in (name, None):
            r = c.post("/api/cosm/inline", json={"text": text, **({"filename": filename} if filename else {})})
            assert r.status_code == 200, r.text
            p = r.json()
            assert p["refused"] is None and p["report"]["ok"] and p["lenses"], p["problems"]
            assert p["minicosm"] == on_disk.minicosm
            assert sum(m["count"] for m in p["modules"]) == len(on_disk.items)
            assert p["path"] == f"inline:{filename or 'inline.cosm'}"
        lens = p["lenses"][0]
        r = c.post("/api/cosm/inline/lens", json={"text": text, "filename": name, "lens": lens})
        assert r.status_code == 200 and r.json()["lens"] == lens


def test_the_inline_route_refuses(project: Path):
    with _client(project, "project") as c:
        assert c.post("/api/cosm/inline", json={}).status_code == 400
        assert c.post("/api/cosm/inline", json={"text": "  "}).status_code == 400
        big = "oes: canon/1\nnodes: []\n# " + "x" * (256 * 1024) + "\n"
        assert c.post("/api/cosm/inline", json={"text": big}).status_code == 413
        r = c.post("/api/cosm/inline", json={"text": "oes: canon/9\nnodes: []\n"})
        assert r.status_code == 200 and r.json()["refused"]                  # a refusal is shown, not an error


def test_compile_round_trips_through_the_route(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        for doc, lang, rel in (("macrocosm-oes", "en", "docs/MACROCOSM_OES.md"),
                               ("help-center", "en", "docs/HELP_CENTER.md"),
                               ("help-center", "de", "enough/static/i18n/de/help-center.md")):
            r = c.post("/api/docs/compile", json={"doc": doc, "lang": lang})
            assert r.status_code == 200
            p = r.json()
            assert (p["doc"], p["lang"], p["chapter"]) == (doc, lang, None)
            assert p["markdown"].encode("utf-8") == (docs_src / rel).read_bytes()


def test_the_inventory_route(docs_src: Path, project: Path):
    with _client(project, "home") as c:
        p = c.get("/api/docs/inventory", params={"doc": "macrocosm-oes", "lang": "en"}).json()
    rows = p["rows"]
    assert (p["doc"], p["lang"]) == ("macrocosm-oes", "en")
    row = next(r for r in rows if r["id"] == "S:section/1.1")
    assert row == {"inventory": "macrocosm-oes", "xref": f"macrocosm-oes@{mc.MACROCOSM_VERSION}:section:1.1",
                   "id": "S:section/1.1", "kind": "section", "version": mc.MACROCOSM_VERSION,
                   "anchor": "sec-1-1", "atem": row["atem"]}
    assert docoes.resolve_xref(row["xref"], rows)["id"] == "S:section/1.1"


# ---------------------------------------------------------------------------
# Agent-free: every docs route is a read and stays open
# ---------------------------------------------------------------------------

def test_the_docs_routes_answer_while_agent_free(docs_src: Path, project: Path):
    for path in ("/api/docs/build", "/api/docs/compile", "/api/cosm/inline", "/api/cosm/inline/lens"):
        assert agent_free_refusal("POST", path) is None, path
    set_ui(agent_free=True)
    assert agent_free.enabled()
    example = _canon_example()
    with _client(project, "project") as c:
        for density in ("atem", "short", "fabula"):
            assert _docs(c, density=density).status_code == 200
        assert c.get("/api/docs/status").status_code == 200
        assert c.get("/api/docs/lens", params={"doc": "macrocosm-oes", "around": "T:term/tree"}).status_code == 200
        assert c.post("/api/docs/compile", json={"doc": "macrocosm-oes"}).status_code == 200
        assert c.get("/api/docs/inventory", params={"doc": "macrocosm-oes"}).status_code == 200
        assert c.post("/api/docs/build", json={"doc": "help-center", "lang": "de"}).status_code == 202
        assert c.post("/api/cosm/inline", json={"text": example}).status_code == 200
        assert c.post("/api/cosm/inline/lens", json={"text": example, "lens": "map"}).status_code == 200
        assert c.get("/api/cosm/lens", params={"path": "notes.md.cosm"}).status_code == 200
        assert c.post("/api/chat", json={"message": "hi"}).status_code == 409   # the gate is on


# ---------------------------------------------------------------------------
# doc_lookup
# ---------------------------------------------------------------------------

def test_doc_lookup_a_spec_term(docs_src: Path, project: Path):
    r = lookup(project, "trees")
    assert r.ok and r.name == "doc_lookup", r.body
    lines = r.body.splitlines()
    assert lines[0] == "tree  [T:term/tree · term]  — the MacroCOSM OES spec (en)"
    assert "atem: one plant that bears fruit every year" in lines
    assert "definition: A tree is one plant that bears fruit every year." in lines
    assert "defined in: §1 Trees" in lines
    assert any(ln.startswith("mentioned in: §1.1 Roots; §2 Fruit; §3 Decisions in this version") for ln in lines)
    r = lookup(project, "R:minicosm/canon")
    assert r.ok and "a MiniCOSM, declared oes: canon/1" in r.body


def test_doc_lookup_a_help_term_in_the_ui_language(docs_src: Path, project: Path):
    set_ui(ui_language="de")
    assert canon_tools.ui_language() == "de"
    r = lookup(project, "Spickzettel")
    assert r.ok, r.body
    assert r.body.splitlines()[0] == "Spickzettel  [T:term/cheat-sheet · term]  — the enough manual (de)"
    assert "atem: eine Seite mit jedem Tastenkürzel" in r.body           # the definition is the atem: said once
    assert "defined in: §1 Erste Schritte" in r.body and "mentioned in: §2 Tastenkürzel" in r.body
    set_ui(ui_language="en")
    assert lookup(project, "cheat sheets").body.startswith("cheat sheet  [T:term/cheat-sheet")


def test_doc_lookup_a_section_number(docs_src: Path, project: Path):
    r = lookup(project, "§2")
    assert r.ok and r.body.startswith("Fruit  [S:section/2 · section]  — the MacroCOSM OES spec"), r.body
    assert "(also §2 in the enough manual: Shortcuts" in r.body and 'ask for "help 2"' in r.body
    r = lookup(project, "help 2")
    assert r.body.startswith("Shortcuts  [S:section/2 · section]  — the enough manual (en)")
    assert "where: a section of the enough manual" in r.body
    r = lookup(project, "section 1.1")
    assert r.body.startswith("Roots  [S:section/1.1") and "where: a section of the MacroCOSM OES spec, in §1 Trees" \
        in r.body
    r = lookup(project, "decisions in this version")                          # a section title, the fallback
    assert r.body.startswith("Decisions in this version  [S:section/3")


def test_doc_lookup_no_entry(docs_src: Path, project: Path):
    r = lookup(project, "zebra crossing")
    assert r.ok and r.body == "no entry for 'zebra crossing' in the MacroCOSM spec or the enough manual."
    r = lookup(project, "autumn")                                            # in an atem only: offered, not answered
    assert r.body.startswith("no entry for 'autumn'") and "T:term/fruit" in r.body
    call = tools.parse_tool_calls('<tool name="doc_lookup"></tool>')[0]
    r = tools.execute(project, call)
    assert not r.ok and "<term>" in r.body


# ---------------------------------------------------------------------------
# The real documents, once
# ---------------------------------------------------------------------------

def test_the_real_spec_once(project: Path):
    """The shipped spec, enumerated for real: it round-trips through the route, MicroCOSM is defined once (§3; §17
    mentions it), the short density holds every section, and the local graph draws around a real term."""
    assert docoes.SOURCES is None
    with _client(project, "home") as c:
        short = _docs(c, density="short").json()
        assert len(short["sections"]) == sum(1 for i in short["items"] if i["kind"] == "section") > 200
        r = c.post("/api/docs/compile", json={"doc": "macrocosm-oes", "lang": "en"})
        assert r.json()["markdown"].encode("utf-8") == SPEC.read_bytes()
        r = c.get("/api/docs/lens", params={"doc": "macrocosm-oes", "around": "T:term/atem"})
        assert r.status_code == 200 and r.json()["around"] == "T:term/atem"
    micro = next(t for t in short["terms"] if t["id"] == "T:term/microcosm")
    assert micro["defined_in"] == "S:section/3" and micro["also_defined_in"] == []
    rep = docoes.lint_doc(docoes.load_built("macrocosm-oes", "en"))
    assert not [w for w in rep.warnings if w.check == "term-defined-once"]
    r = lookup(project, "MicroCOSM")
    assert "defined in: §3 Scales: MacroCOSM, MiniCOSM, MicroCOSM" in r.body and "also defined" not in r.body
