"""The transconception card (0.8, lane W4-X7; survey `v080-survey-transcoding.md` section 3, phase 7): what
`GET /api/fabula/transconception` gives the page of a fabulac kept for transconception, read only, and what the page
does with it.

- `transconception.card`: the two gates with each check held or not and why; the rulings queue (questions about a
  ruling, batched, as the dialectic raised them); the ground (every reliance, each citation with what came of it in
  the language library: resolved, fetching, not aboard, ...); the targets with their twelve points, verdict,
  conditions and gaps; each cshort with its target, apart or beside, its layout and its evidence.
- The route takes the fabulac or its folder, answers `{transconception: false}` for any other fabulac, and writes
  nothing.
- The page: the card offers no build and no run of a cshort, a cshort in another language is a cshort to the tree's
  menu (read, never "build its fabulac…"), and a citation opens the library's section in the docs viewer.

`seed_card(dest)` is the fixture the uicheck screens use too (scripts/uicheck/server.py): the promoted vulture fabulac
(MIT, its licence beside it) with five rulings taken back to open, batched questions, and a cshort in Go with its
layout, entailed apart and not judged yet. Its Go files are a few lines written for this page check, not a real
entailment: they are read, never built.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enough import dialectic as dl
from enough import macrocosm as mc
from enough import transconception as tc
from enough.server import create_app

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "fabula" / "transconception"
VULTURE = FIX / "vulture.fabulac.cosm"
TALLY = REPO / "tests" / "fixtures" / "fabula" / "tally.fabulac.cosm"
HTML = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")
RAISED = "2026-11-19T09:00:00Z"
STAMP = "2026-11-18-1900"
GO_CSHORT = f"vulture.cshort-go-{STAMP}/"
GO_LAYOUT = f"vulture.layout-go-{STAMP}.md"
#: the items whose rulings the seed takes back to open (each proposed as it was ruled)
REOPEN = ("C:reliance/V-R01", "C:reliance/V-R02", "C:reliance/V-R03", "C:reliance/V-R04", "C:reliance/V-R05")

LAYOUT_MD = f"""# vulture in Go: the layout

The files a cshort of vulture in Go is written to, and the name each kept interface takes there.

## Files, in the order they are written

| # | file | holds |
|---|---|---|
| 1 | go.mod | the module |
| 2 | main.go | the command |

## Interfaces

| interface | file | name |
|---|---|---|
| C:interface/command.vulture | main.go | main |

*a layout of vulture.fabulac.cosm, in Go, compiled on 2026-11-18 by a fixture of the page check*
"""
CSHORT_MD = f"""*a cshort of vulture.fabulac.cosm, in Go, compiled on 2026-11-18 by a fixture of the page check; never run*

Entailed apart from the source, by the layout {GO_LAYOUT}; never built here.

| file | holds | sha256 |
|---|---|---|
| go.mod | the module | - |
| main.go | the command | - |

## Every kept interface, mapped

| interface | file | name |
|---|---|---|
| C:interface/command.vulture | main.go | main |

Licence of the source: MIT
"""
MAIN_GO = """// A few lines written for the page check: read, never built or run.
package main

import "os"

func main() {
\tos.Exit(0)
}
"""


def seed_card(dest: Path) -> Path:
    """The card's fixture in `dest` (see the module's docstring); returns the fabulac."""
    dest.mkdir(parents=True, exist_ok=True)
    fab = dest / "vulture.fabulac.cosm"
    shutil.copyfile(VULTURE, fab)
    shutil.copyfile(FIX / "vulture.LICENSE.txt", dest / "vulture.LICENSE.txt")
    t = dl.open_twin(fab)
    for d in t.ledger.items:
        if isinstance(d, dict) and d.get("id") in REOPEN:
            d["ruling"] = [{"pending": "not ruled yet", **{k: x[k] for k in ("made-for", "about", "steps") if k in x},
                            "proposed": {k: x[k] for k in ("is", "allowing", "because", "to") if k in x}}
                           for x in d["ruling"]]
    r = dl.raise_questions(t.ledger, at=RAISED)
    dl.land(t.ledger, [q for q in r.questions if dl.is_ruling_question(q)])
    t.doc["shorts"] = list(t.doc.get("shorts") or []) + [{
        "path": GO_CSHORT, "at": "2026-11-18T19:00", "by": "a fixture of the page check", "mode": "model",
        "order": "code", "language": "go", "entailed": "apart", "target": "N:target/go", "layout": GO_LAYOUT,
        "evidence": []}]
    t.save()
    (dest / GO_LAYOUT).write_text(LAYOUT_MD, encoding="utf-8")
    cs = dest / GO_CSHORT
    cs.mkdir(exist_ok=True)
    (cs / "CSHORT.md").write_text(CSHORT_MD, encoding="utf-8")
    (cs / "go.mod").write_text("module vulture\n\ngo 1.27\n", encoding="utf-8")
    (cs / "main.go").write_text(MAIN_GO, encoding="utf-8")
    (cs / "requests.jsonl").write_text("", encoding="utf-8")
    return fab


class FakeLibrary:
    """A library that answers each citation by its page: one is being fetched, one resolves, the rest are not
    aboard."""

    def cite(self, stated: dict, wait: float = 0.0) -> dict:
        at = str(stated.get("at"))
        if at.startswith("library/pathlib.html"):
            return {"state": "fetching", "why": "fetching python/docs/3.13 from the stand-in", "hit": None}
        if at.startswith("library/argparse.html"):
            return {"state": "resolved", "why": "", "hit": None}
        return {"state": "not-aboard", "why": "python/docs/3.13 is not kept here", "hit": None}


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return seed_card(tmp_path_factory.mktemp("card").resolve() / "transconceive")


def test_the_seed_carries_open_batched_rulings_and_a_cshort_in_go(seeded: Path):
    doc = mc.yaml_load(seeded.read_text(encoding="utf-8"))
    qs = [n for n in doc["nodes"] if n.get("type") == "question" and str(n.get("about")).endswith("#ruling")]
    assert qs and all(q["state"] == "open" for q in qs)
    named = {q["about"].partition("#")[0] for q in qs} | {a.partition("#")[0] for q in qs for a in q.get("batch") or []}
    assert named == set(REOPEN)
    assert any(q.get("batch") for q in qs), "the rulings bank batches items of one proposal"
    assert (seeded.parent / GO_CSHORT / "main.go").is_file() and (seeded.parent / GO_LAYOUT).is_file()
    assert mc.load_volume(seeded).catalog["shorts"][-1]["target"] == "N:target/go"


def test_the_card_says_each_gate_and_each_check(seeded: Path):
    c = tc.card(seeded, library=FakeLibrary())
    assert c["transconception"] and c["name"] == "vulture" and c["language"] == "python"
    keep = c["gates"]["keep"]
    assert keep["gate"] == "ready-to-keep" and keep["holds"] is False and keep["says"] == "not ready to keep"
    assert list(keep["checks"]) == list(tc.READY_TO_KEEP)
    # the open questions keep `ruled` from holding, each named with why (a skipped question blocks the gate)
    assert keep["checks"]["ruled"]["state"] == "fails"
    assert any("asks for its ruling and stands open" in e for e in keep["checks"]["ruled"]["errors"])
    assert keep["checks"]["stands-alone"]["state"] == "fails"
    # no source beside it: what needs it is not measured, and says why
    assert keep["checks"]["nothing-carried"]["state"] == "not measured" and keep["checks"]["nothing-carried"]["why"]
    assert c["source-here"] is False
    assert [g["language"] for g in c["gates"]["entail"]] == ["go"]
    go = c["gates"]["entail"][0]
    assert go["gate"] == "ready-to-entail" and "target-confirmed" in go["checks"] and go["holds"] is False


def test_the_card_lists_the_rulings_queue(seeded: Path):
    r = tc.card(seeded, library=FakeLibrary())["rulings"]
    assert r["counts"] == {"open": len(r["questions"])} and r["questions"]
    # one question per scope (a reliance ruled for go and for python is asked twice), batched across items
    assert {q["about"] for q in r["questions"]} <= set(REOPEN) and any(q["batch"] for q in r["questions"])
    pending = sum(1 for n in mc.yaml_load(seeded.read_text(encoding="utf-8"))["nodes"] if n.get("id") in REOPEN
                  for x in n["ruling"] if "pending" in x)
    assert sum(1 + q["batch"] for q in r["questions"]) == pending
    assert all(q["state"] == "open" and q["proposed"].get("is") for q in r["questions"])
    assert r["unruled"] == len(REOPEN) and r["items"] > 200
    assert r["words"]["kept"] > 100 and set(r["words"]) <= {"kept", "alike", "free", "kept-wrong", "changed"}


def test_the_ground_says_what_came_of_each_citation(seeded: Path):
    g = tc.card(seeded, library=FakeLibrary())["ground"]
    assert g["library"] is True and len(g["items"]) == 37
    states = g["states"]
    assert states["fetching"] >= 1 and states["resolved"] >= 1 and states["not-aboard"] >= 1 and states["nowhere"] >= 1
    r01 = next(x for x in g["items"] if x["id"] == "C:reliance/V-R01")
    assert [c["state"] for c in r01["stated"]] == ["fetching", "fetching"]
    assert r01["stated"][0] == {"in": "python", "version": "3.13.18", "at": "library/pathlib.html#pathlib.PurePath",
                                "digest": "ea319d48765a", "state": "fetching",
                                "why": "fetching python/docs/3.13 from the stand-in"}
    assert r01["rulings"] and all(x["pending"] for x in r01["rulings"])


def test_with_no_library_every_citation_is_not_aboard(seeded: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tc, "local_library", lambda: None)
    g = tc.card(seeded)["ground"]
    assert g["library"] is False
    assert set(g["states"]) == {"not-aboard", "nowhere"}
    assert all(c["why"].startswith("the language library is not aboard here") for it in g["items"]
               for c in it["stated"] if c["state"] == "not-aboard")


def test_the_targets_carry_twelve_points_and_the_cshorts_their_evidence(seeded: Path):
    c = tc.card(seeded, library=FakeLibrary())
    py, go = c["targets"]
    assert py["source"] and py["language"] == "python" and py["points"] == [] and py["verdict"] is None
    assert go["language"] == "go" and go["verdict"] == "feasible-with" and go["standing"] and go["version"] == "1.27.4"
    assert [p["point"] for p in go["points"]] == list(range(1, 13))
    assert [p["point"] for p in go["points"] if p["gate"]] == list(tc.GATE_POINTS)
    assert all(isinstance(p["score"], int) and p["evidence"] for p in go["points"])
    assert go["conditions"] and go["provides"]["written"] >= 1 and go["spike"]["level"] >= 2
    rt, cs = c["cshorts"]
    assert rt["language"] == "python" and not rt["other-language"] and rt["judged"]
    assert rt["evidence"]["level"] == 3 and rt["evidence"]["kept"] == rt["evidence"]["agree"] == 92
    assert cs == {"path": GO_CSHORT, "language": "go", "target": "N:target/go", "other-language": True,
                  "entailed": "apart", "layout": GO_LAYOUT, "layout-there": True, "there": True,
                  "at": "2026-11-18T19:00", "by": "a fixture of the page check", "evidence": None, "judged": False}


def test_a_fabulac_kept_for_no_transconception_says_so():
    assert tc.card(TALLY) == {"transconception": False, "purpose": None}


@pytest.fixture
def client(tmp_path: Path):
    proj = (tmp_path / "project").resolve()
    proj.mkdir()
    seed_card(proj / "transconceive")
    shutil.copyfile(TALLY, proj / "tally.fabulac.cosm")
    app = create_app(proj, "http://127.0.0.1:9", supervise=False)
    with TestClient(app) as c:
        yield c, proj


def _tree(root: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_the_route_reads_the_card_and_writes_nothing(client):
    c, proj = client
    before = _tree(proj / "transconceive")
    for path in ("transconceive/vulture.fabulac.cosm",):     # (its folder is not beside it: the source is not here)
        r = c.get("/api/fabula/transconception", params={"path": path})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["path"] == "transconceive/vulture.fabulac.cosm" and d["transconception"] is True
        assert d["gates"]["keep"]["says"] == "not ready to keep" and len(d["targets"]) == 2
        assert d["cshorts"][-1]["other-language"] is True
        json.dumps(d)
    assert _tree(proj / "transconceive") == before
    r = c.get("/api/fabula/transconception", params={"path": "tally.fabulac.cosm"})
    assert r.status_code == 200 and r.json() == {"path": "tally.fabulac.cosm", "transconception": False, "purpose": None}
    assert c.get("/api/fabula/transconception", params={"path": "nothing-here.fabulac.cosm"}).status_code == 404
    assert c.get("/api/fabula/transconception", params={"path": "../outside.fabulac.cosm"}).status_code in (400, 403, 404)


def test_the_layout_is_read_through_the_catem_route(client):
    c, _proj = client
    r = c.get("/api/fabula/catem", params={"path": "transconceive/" + GO_LAYOUT})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "layout" and r.json()["depth"] is None and "the layout" in r.json()["text"]
    r = c.get("/api/fabula/cshort", params={"path": "transconceive/" + GO_CSHORT})
    assert r.status_code == 200 and {f["path"] for f in r.json()["files"]} >= {"main.go", "CSHORT.md"}


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

def _fn(name: str) -> str:
    m = re.search(r"\n    (?:async )?function " + re.escape(name) + r"\(", HTML)
    assert m, name
    end = HTML.index("\n    }\n", m.end())
    return HTML[m.start():end]


TC_FUNCTIONS = ("fabTcLoad", "fabTcGateHTML", "fabTcRulingsHTML", "fabTcGroundHTML", "fabTcTargetsHTML",
                "fabTcCshortsHTML", "fabTcHTML", "fabTcCite", "libLoad", "libRender", "libDocClick")


def test_the_card_offers_no_build_and_no_run():
    """Nothing the card draws posts anything: it reads its route and the library's, opens the cshort viewer, the docs
    viewer and the dialectic; a cshort in any language is read."""
    for name in TC_FUNCTIONS:
        body = _fn(name)
        assert "canonPost" not in body and "fapPost" not in body and "method: 'POST'" not in body, name
        assert not re.search(r"/api/(?:fabulac|sandbox|thym)/", body), name
        assert not re.search(r"data-fab=\"(?:compile|verse-build)\"|data-fap=", body), name
    acts = set(re.findall(r"data-fab=\"([a-z-]+)\"", "".join(_fn(n) for n in TC_FUNCTIONS)))
    assert acts == {"tc-cite", "tc-rulings", "view"}, acts
    assert "canonJSON('/api/fabula/transconception?path='" in _fn("fabTcLoad")
    assert "canonJSON('/api/library/section?'" in _fn("libLoad")
    assert "enterDocsMode({ doc: 'library', cite })" in _fn("fabTcCite")


def test_a_cshort_in_another_language_is_a_cshort_to_the_tree():
    m = re.search(r"const FAB_CSHORT_RE = (/.*/);", HTML)
    lay = re.search(r"const FAB_LAYOUT_RE = (/.*/i);", HTML)
    assert m and lay
    pat = re.compile(m.group(1)[1:-1].replace("\\/", "/"))
    for name in ("works/tally.cshort-2026-11-05-1412/", "vulture.cshort-go-2026-11-18-1900/",
                 "x.cshort-rust-2026-11-18-1900-2", GO_CSHORT):
        assert pat.search(name), name
    assert not pat.search("vulture.catem-2026-11-18-1900.md")
    lpat = re.compile(lay.group(1)[1:-2].replace("\\/", "/"), re.I)
    assert lpat.search(GO_LAYOUT) and not lpat.search("vulture.catem-2026-11-18-1900.md")
    # the tree's menu on a cshort folder reads it, and offers nothing else
    menu = _fn("fabMenuItems")
    assert "if (FAB_CSHORT_RE.test(p)) return item('fab-view'" in menu
