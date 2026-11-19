"""Transconception, phase 6 (0.8): entailing into another language. `entail f as layout in <language>` (a model's
layout checked by rules against the fabulac's kept interfaces) and `entail f as code in <language> with layout` (a
cshort written file by file, apart from the source by default, beside it only for the person's own code or an open
lane); the checks `target-confirmed`, `surface-answered`, `apart`, `files-present` and `footer` of a cshort in another
language, the layout's `footer` and `no-invention`; `evidence-stated` reading a cshort's evidence only from a verdict
(`evidence: []` until then); the landing beside the fabulac; `dialectic.target_ref` reading the weighing that stands.

The models here are scripted: a layout that puts every interface it is asked to map in one file, and a writer that
defines every name the layout gives its file and writes one guess down. Nothing is built or run: building and judging a
cshort in Go or Rust is the outside runner's (`tools/transconception/`). The experiment's four cshorts (x0 step A8) are
read as text only, by path, and skipped where they are not on the machine.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from enough import dialectic as dl
from enough import fabula as FAB
from enough import fabulac_prompts as FP
from enough import macrocosm as mc
from enough import thym
from enough import thym_host as H
from enough import transconception as tc
from enough import transconception_prompts as TP
from enough.thym import Refusal
from enough.thym import checks as C
from enough.thym import contracts as ct
from enough.thym import declarations as dc
from enough.thym import plan as pl
from enough.thym import registry as R
from enough.thym import run as RUN
from enough.thym.coprocessor import candidate
from enough.thym.folder import Folder
from enough.thym.moves import MoveError
from enough.thym.moves import transconceive as TR
from enough.thym.values import Value, digest_path

import test_ground as TG
import test_transconception_targets as TT

REPO = Path(__file__).resolve().parents[1]
PROMOTED = REPO / "tests" / "fixtures" / "fabula" / "transconception"
VULTURE = PROMOTED / "vulture.fabulac.cosm"
SLOPPY = PROMOTED / "sloppy-xml-py.fabulac.cosm"
X0 = Path("/Users/m3u/METMcloud/fabulac-test-repos/_x0")
NOW = TT.NOW
SUFFIX = {"Go": "go", "Rust": "rs"}
PACKAGING = {"Go": "go.mod", "Rust": "Cargo.toml"}


# ---------------------------------------------------------------------------
# the scripted models
# ---------------------------------------------------------------------------

def _t(inputs: dict, k: str) -> str:
    v = inputs.get(k)
    return v.text() if isinstance(v, Value) else str(v or "")


def ident(iid: str) -> str:
    return "N_" + re.sub(r"\W", "_", iid.split("/", 1)[-1])


def layout_reply(inputs: dict, *, drop: str | None = None, engine: bool = True) -> str:
    """A layout: the packaging file first, then one source file holding every interface asked (but `drop`); a type
    for each own-types item; a fill for each gap."""
    lang = _t(inputs, "language")
    ids = [ln[2:].split(": ", 1)[0] for ln in _t(inputs, "map").splitlines() if ln.startswith("- ")]
    types = mc.yaml_load(_t(inputs, "types")) if _t(inputs, "types") != "(none)" else []
    gaps = mc.yaml_load(_t(inputs, "gaps")) if _t(inputs, "gaps") != "(none)" else []
    data = {"files": [{"path": PACKAGING[lang], "holds": f"the {lang} package", "interfaces": []},
                      {"path": f"main.{SUFFIX[lang]}", "holds": "the whole program",
                       "interfaces": [{"id": i, "name": ident(i)} for i in ids if i != drop]}],
            "types": [{"for": t["for"], "type": f"its own {lang} type"} for t in types or []],
            "gaps": [{"for": g["for"], "fill": f"written in main.{SUFFIX[lang]}"} for g in gaps or []]}
    return mc.dump(data) + ("engine: model:scripted\n" if engine else "")


def writer_reply(inputs: dict, *, skip: str | None = None) -> str:
    """One file: every name the layout gives it defined (but `skip`), and one guess written down."""
    lang, path = _t(inputs, "language"), _t(inputs, "path")
    brief = mc.yaml_load(_t(inputs, "brief"))
    names = [x["takes the name"] for x in brief.get("interfaces") or [] if x["takes the name"] != skip]
    if path == PACKAGING[lang]:
        body = "module tally\n" if lang == "Go" else '[package]\nname = "tally"\n'
    elif lang == "Go":
        body = "package main\n\n" + "".join(f"func {n}() {{}}\n" for n in names)
    else:
        body = "".join(f"pub fn {n}() {{}}\n" for n in names)
    return f"```{SUFFIX.get(lang, '')}\n{body}```\n\n## Notes\n\n- the fabulac does not say the line width: 80 chosen\n"


def ctx(tmp_path: Path, *, engine=None, writer=writer_reply, sent: list | None = None) -> RUN.MoveContext:
    stage = tmp_path / "stage"
    stage.mkdir(parents=True, exist_ok=True)

    def ask(contract, inputs, budget):
        if sent is not None:
            sent.append({k: _t(inputs, k) for k in inputs})
        return candidate(writer(inputs), engine="model:scripted", tokens=10)
    return RUN.MoveContext(run="2026-11-18-1200-test", node={"id": "R:node/1", "step": {"n": 1}},
                           decls=R.read_declarations(), coprocessor=None, rules=False, now=NOW, emitted=[], slots={},
                           withheld={}, inputs_root=tmp_path, root=tmp_path, stage=stage,
                           engines={"transconception": engine or tc.thym_engine()}, ask_fn=ask)


def fab(cat: dict, items: list[dict]) -> Value:
    return Value("fabula", {**copy.deepcopy(cat), "nodes": copy.deepcopy(items)})


def layout_of(c: RUN.MoveContext, f: Value, language: str, **kw) -> Value:
    req = TR.entail_layout(c, f, **{"as": "layout", "in": Value("string", language)})
    assert isinstance(req, R.Request)
    return req.parse(layout_reply(req.inputs, **kw))


def code_of(c: RUN.MoveContext, f: Value, language: str, layout: Value) -> Value:
    return TR.entail_code_in(c, f, **{"as": "code", "in": Value("string", language), "with": layout})


def verdict(name: str, out: Value, inputs: dict, as_: str, language: str, c=None):
    r = C.verdict(name, out, inputs, {"modifiers": {"as": as_, "in": language}}, {"name": "entail"}, c)
    assert not isinstance(r, Refusal), r
    return r


LAYOUT_CONTRACT = ("target-confirmed", "surface-answered", "no-invention", "footer")
CODE_CONTRACT = ("target-confirmed", "files-present", "surface-answered", "apart", "footer")


# ---------------------------------------------------------------------------
# tally, weighed: the fixture the brief names
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def weighed(tmp_path_factory) -> dict:
    """tally grounded and kept for transconception, weighed in Go and in Rust (W3-X5's scripted weighing), each
    spike standing at level 3 as the judge's verdict on it would set it (`spike_from_verdict`: no difference)."""
    tmp = tmp_path_factory.mktemp("weighed")
    cat, items, _ = TG.ground(TG.TALLY_FABULAC, TG.TALLY)
    cat = {**cat, "purpose": "transconception"}
    for lang in ("go", "rust"):
        out = TT.weigh(tmp, cat, items, lang, spike_cases=["P:case/cli-json-and-error"])
        items = TT.nodes_of(out)
        t = TT.target_of(out, f"N:target/{lang}")
        t["spike"] = tc.spike_from_verdict(t["spike"], TT._verdict([]), where=f"results/{lang}-spike/verdict.json",
                                           digest="ab12", at="2026-11-18T18:19")
        cat = {k: v for k, v in out.payload.items() if k != "nodes"}
    return {"cat": cat, "items": items}


@pytest.mark.parametrize("language, title", [("go", "Go"), ("rust", "Rust")])
def test_tally_entails_a_layout_and_a_cshort_apart(tmp_path, weighed, language, title):
    f = fab(weighed["cat"], weighed["items"])
    sent: list = []
    c = ctx(tmp_path, sent=sent)
    lay = layout_of(c, f, language)
    text = lay.text()
    assert text.startswith(f"# tally in {title}: the layout")
    assert text.rstrip().endswith(f"*a layout of tally.fabulac.cosm, in {title}, compiled on 2026-11-18 by scripted*")
    assert "| C:interface/command.tally | main." in text and "## Gaps, and what fills each" in text
    back = TR.read_layout(text)
    assert [x["path"] for x in back["files"]] == [PACKAGING[title], f"main.{SUFFIX[title]}"]
    assert len(back["files"][1]["interfaces"]) == 14          # every interface of tally: none ruled, so all kept
    for name in LAYOUT_CONTRACT:
        assert verdict(name, lay, {"f": f}, "layout", language, c) == (True, ""), name

    cs = code_of(c, f, language, lay)
    folder = cs.payload
    assert isinstance(folder, Folder) and folder.path == f"tally.cshort-{language}/"
    assert {e.path for e in folder.entries} == {PACKAGING[title], f"main.{SUFFIX[title]}", "CSHORT.md", "NOTES.md",
                                                "NOTICE", "requests.jsonl"}
    md = folder.text("CSHORT.md")
    assert md.splitlines()[0] == f"*a cshort of tally.fabulac.cosm, in {title}, compiled on 2026-11-18 by scripted; never run*"
    assert md.rstrip().splitlines()[-1] == "Licence of the source: MIT"
    assert "| C:interface/tally.ledger.add | main." in md
    assert "the fabulac does not say the line width: 80 chosen" in folder.text("NOTES.md")
    assert "transconception of tally" in folder.text("NOTICE") and "Copyright (c) 2026 Meadow Software" in folder.text("NOTICE")
    reqs = [json.loads(x) for x in folder.text("requests.jsonl").splitlines()]
    assert [r["writes"] for r in reqs] == [PACKAGING[title], f"main.{SUFFIX[title]}"] and len(sent) == 2
    assert all(r["entailed"] == "apart" and "source" not in r["inputs"] for r in reqs)
    assert not any("tally/ledger.py" in json.dumps(r) or '"span"' in json.dumps(r) for r in reqs)
    entry = cs.origin["entry"]
    assert entry["target"] == f"N:target/{language}" and entry["entailed"] == "apart" and entry["evidence"] == []
    assert entry["order"] == "code" and entry["language"] == language
    for name in CODE_CONTRACT:
        assert verdict(name, cs, {"f": f, "with": lay}, "code", language, c) == (True, ""), name
    assert "parses" not in dc.load().view(1)["entail"].contract_when[0][2]   # no parse of another language


def test_the_entailment_waits_for_target_confirmed_and_refuses_what_is_not_its(tmp_path, weighed):
    c = ctx(tmp_path)
    items = copy.deepcopy(weighed["items"])
    next(d for d in items if d["id"] == "N:target/go")["spike"]["level"] = 0
    with pytest.raises(MoveError, match="target-confirmed: the spike in go has not reached level 2"):
        TR.entail_layout(c, fab(weighed["cat"], items), **{"as": "layout", "in": Value("string", "go")})
    f = fab(weighed["cat"], weighed["items"])
    with pytest.raises(MoveError, match="f's own language"):
        TR.entail_layout(c, f, **{"as": "layout", "in": Value("string", "python")})
    with pytest.raises(MoveError, match="no language this build knows"):
        TR.entail_layout(c, f, **{"as": "layout", "in": Value("string", "cobol")})
    with pytest.raises(MoveError, match="names the language"):
        TR.entail_layout(c, f, **{"as": "layout"})
    plain_cat = {k: v for k, v in weighed["cat"].items() if k != "purpose"}
    with pytest.raises(MoveError, match="not kept for transconception"):
        TR.entail_layout(c, fab(plain_cat, weighed["items"]), **{"as": "layout", "in": Value("string", "go")})
    # `in` and a layout belong to these two: anywhere else they are refused, never ignored
    with pytest.raises(MoveError, match="takes as layout or as code"):
        TR.refuse_stray({"as": "told", "in": Value("string", "go")})
    with pytest.raises(MoveError, match="as the layout of"):
        TR.refuse_stray({"as": "code", "with": Value("short", "x")})
    # --rules: a layout has no scaffold
    with pytest.raises(MoveError, match="no scaffold"):
        TR.entail_in_scaffold(c, f, **{"as": "layout", "in": Value("string", "go")})
    # the check, on a fabulac that is not confirmed
    lay = layout_of(c, f, "go")
    ok, why = verdict("target-confirmed", lay, {"f": fab(weighed["cat"], items)}, "layout", "go", c)
    assert not ok and "has not reached level 2" in why


def test_a_layout_is_checked_by_rules_and_read_again(tmp_path, weighed):
    c = ctx(tmp_path)
    f = fab(weighed["cat"], weighed["items"])
    req = TR.entail_layout(c, f, **{"as": "layout", "in": Value("string", "go")})
    with pytest.raises(ValueError, match="no file holds C:interface/tally.cli.main"):
        req.parse(layout_reply(req.inputs, drop="C:interface/tally.cli.main"))
    good = mc.yaml_load(layout_reply(req.inputs))
    bad = copy.deepcopy(good)
    bad["files"][1]["interfaces"].append({"id": "C:interface/tally.nowhere", "name": "Nowhere"})
    with pytest.raises(ValueError, match="which the fabulac does not hold"):
        req.parse(mc.dump(bad))
    bad = copy.deepcopy(good)
    bad["files"][0]["path"] = "CSHORT.md"
    with pytest.raises(ValueError, match="a path inside the program"):
        req.parse(mc.dump(bad))
    bad = copy.deepcopy(good)
    bad["files"][1]["path"] = "../main.go"
    with pytest.raises(ValueError, match="a path inside the program"):
        req.parse(mc.dump(bad))
    bad = copy.deepcopy(good)
    bad["files"][1]["path"] = "main.py"
    with pytest.raises(ValueError, match="no file is in the language"):
        req.parse(mc.dump(bad))
    bad = copy.deepcopy(good)
    bad["gaps"] = []
    with pytest.raises(ValueError, match="gaps: no fill for C:reliance/argparse-surface"):
        req.parse(mc.dump(bad))
    # the layout's own checks fail on a layout that drops an interface or names what the fabulac lacks
    lay = req.parse(mc.dump(good))
    text = lay.text()
    gone = Value("short", re.sub(r"^\| C:interface/tally.cli.main .*\n", "", text, flags=re.M), origin=lay.origin)
    ok, why = verdict("surface-answered", gone, {"f": f}, "layout", "go", c)
    assert not ok and "C:interface/tally.cli.main: maps it to no file and name" in why
    inv = Value("short", text.replace("## Interfaces", "Also C:behaviour/tally.made-up.\n\n## Interfaces"),
                origin=lay.origin)
    ok, why = verdict("no-invention", inv, {"f": f}, "layout", "go", c)
    assert not ok and "C:behaviour/tally.made-up" in why
    ok, why = verdict("footer", Value("short", text.rsplit("*a layout", 1)[0], origin=lay.origin), {"f": f},
                      "layout", "go", c)
    assert not ok and "not a layout's footer" in why
    with pytest.raises(MoveError, match="no layout"):
        TR.read_layout("# nothing\n")


def test_surface_answered_and_apart_fail_where_they_should(tmp_path, weighed):
    c = ctx(tmp_path)
    f = fab(weighed["cat"], weighed["items"])
    lay = layout_of(c, f, "go")
    # a writer that leaves one name out: the cshort maps it, and the name is not in the file
    c2 = ctx(tmp_path, writer=lambda i: writer_reply(i, skip=ident("C:interface/tally.render.rows")))
    cs = code_of(c2, f, "go", lay)
    ok, why = verdict("surface-answered", cs, {"f": f, "with": lay}, "code", "go", c2)
    assert not ok and "C:interface/tally.render.rows: N_tally_render_rows is not in main.go" in why
    # a request that names a path of the source, or carries a span, fails apart
    cs = code_of(c, f, "go", lay)
    texts = {e.path: cs.payload.text(e.path) for e in cs.payload.entries}
    for extra, said in ((json.dumps({"request": 9, "inputs": {"brief": "see tally/ledger.py"}}), "named a path"),
                        (json.dumps({"request": 9, "span": {"file": "x", "lines": "1-2"}}), "carried a span")):
        t2 = dict(texts, **{"requests.jsonl": texts["requests.jsonl"] + extra + "\n"})
        bad = Value("folder", TR.folder_of_texts(cs.payload.path, t2), origin=cs.origin)
        ok, why = verdict("apart", bad, {"f": f, "with": lay}, "code", "go", c)
        assert not ok and said in why
    # with no requests kept, apart cannot be held
    t3 = {k: v for k, v in texts.items() if k != "requests.jsonl"}
    ok, why = verdict("apart", Value("folder", TR.folder_of_texts(cs.payload.path, t3), origin=cs.origin),
                      {"f": f}, "code", "go", c)
    assert not ok and "requests.jsonl is missing" in why
    # files-present: a file CSHORT.md lists with another digest
    t4 = dict(texts, **{"main.go": texts["main.go"] + "// changed\n"})
    ok, why = verdict("files-present", Value("folder", TR.folder_of_texts(cs.payload.path, t4), origin=cs.origin),
                      {"f": f}, "code", "go", c)
    assert not ok and "main.go with another sha256" in why
    # a path of the source is never sent: the brief says it as a file of the original
    assert TR._scrub("reads tally/ledger.py and pyproject.toml", {"tally/ledger.py"}) == \
        "reads a file of the original and pyproject.toml"


def test_the_layout_and_the_cshort_land_beside_the_fabulac_with_the_entry(tmp_path, weighed):
    c = ctx(tmp_path)
    f = fab(weighed["cat"], weighed["items"])
    lay = layout_of(c, f, "go")
    cs = code_of(c, f, "go", lay)
    p = tmp_path / "tally.fabulac.cosm"
    p.write_text(mc.dump({**weighed["cat"], "nodes": weighed["items"]}), encoding="utf-8")
    got = tc.land_in_language(p, language="go", stamp="2026-11-18-1200", layout=lay.text(),
                              cshort={e.path: cs.payload.text(e.path) for e in cs.payload.entries},
                              entry=cs.origin["entry"])
    assert got["layout"] == "tally.layout-go-2026-11-18-1200.md" and got["cshort"] == "tally.cshort-go-2026-11-18-1200/"
    assert (tmp_path / got["layout"]).read_text(encoding="utf-8") == lay.text()
    v = mc.load_volume(p)
    e = v.catalog["shorts"][-1]
    assert e["path"] == "tally.cshort-go-2026-11-18-1200/" and e["layout"] == "tally.layout-go-2026-11-18-1200.md"
    assert e["entailed"] == "apart" and e["evidence"] == [] and e["target"] == "N:target/go"
    rep = FAB.lint(v)
    errs = {p.check: p.message for p in rep.problems() if p.severity == "error"}
    assert "evidence-stated" not in errs and "surface-answered" not in errs and "apart" not in errs
    with pytest.raises(FileExistsError):
        tc.land_in_language(p, language="go", stamp="2026-11-18-1200", layout=lay.text())
    assert tc.entailed_names("vulture.fabulac.cosm", "rust", "2026-11-19-0900") == {
        "layout": "vulture.layout-rust-2026-11-19-0900.md", "cshort": "vulture.cshort-rust-2026-11-19-0900/"}


# ---------------------------------------------------------------------------
# the promoted fixtures: vulture into Go, sloppy-xml-py into Rust, apart and beside
# ---------------------------------------------------------------------------

def _fixture(path: Path) -> tuple[dict, list[dict], Value]:
    data = mc.yaml_load(path.read_text(encoding="utf-8"))
    cat = {k: v for k, v in data.items() if k != "nodes"}
    return cat, data["nodes"], Value("fabula", data, path=path)


@pytest.mark.parametrize("path, language, title", [(VULTURE, "go", "Go"), (SLOPPY, "rust", "Rust")])
@pytest.mark.parametrize("entailed", ["apart", "beside"])
def test_the_promoted_fixtures_entail_apart_and_beside(tmp_path, path, language, title, entailed):
    cat, items, f = _fixture(path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "original.py").write_text("SECRET_LINE = 'the original, read as text'\n", encoding="utf-8")
    sent: list = []
    eng = tc.thym_engine(beside=source) if entailed == "beside" else tc.thym_engine()
    c = ctx(tmp_path, engine=eng, sent=sent)
    lay = layout_of(c, f, language)
    for name in LAYOUT_CONTRACT:
        assert verdict(name, lay, {"f": f}, "layout", language, c) == (True, ""), name
    cs = code_of(c, f, language, lay)
    assert cs.origin["entry"]["entailed"] == entailed and cs.origin["entry"]["evidence"] == []
    for name in CODE_CONTRACT:
        assert verdict(name, cs, {"f": f, "with": lay}, "code", language, c) == (True, ""), name
    stem = path.name.split(".")[0]
    assert cs.payload.path == f"{stem}.cshort-{language}/"
    req = [json.loads(x) for x in cs.payload.text("requests.jsonl").splitlines()]
    files = tc.source_paths(items)
    if entailed == "apart":
        assert all("source" not in r["inputs"] for r in req) and not any("SECRET_LINE" in s.get("source", "") for s in sent)
        assert not tc.apart_problems(cs.payload.text("requests.jsonl").splitlines(), files, None, 200)
        assert "no line of the source was read" in cs.payload.text("NOTICE")
    else:
        assert all("SECRET_LINE" in r["inputs"]["source"] for r in req)
        assert "the source read beside them" in cs.payload.text("NOTICE")
        assert "original's source is shown beside" in FP.messages({}, sent[-1])[0]["content"]


def test_beside_is_refused_for_a_closed_or_bound_lane_and_unrecorded_terms(tmp_path, weighed):
    cat, items, _ = _fixture(SLOPPY)
    source = tmp_path / "source"
    source.mkdir()
    (source / "sloppy_xml.py").write_text("x = 1\n", encoding="utf-8")
    for lane, leave, said in (("closed", None, "only with its holder's leave"), ("closed", "the holder, by letter",
                                                                                 "entailed apart only"),
                              ("bound", None, "bound lane is entailed apart only")):
        its = copy.deepcopy(items)
        lic = next(d for d in its if d["id"].startswith("R:licence/"))
        lic["lane"] = lane
        if leave:
            lic["leave"] = leave
        f = Value("fabula", {**cat, "nodes": its}, path=SLOPPY)
        c = ctx(tmp_path, engine=tc.thym_engine(beside=source))
        lay = layout_of(ctx(tmp_path), f, "rust")
        with pytest.raises(MoveError, match=f"beside the source is refused: .*{said}"):
            code_of(c, f, "rust", lay)
        assert code_of(ctx(tmp_path), f, "rust", lay).origin["entry"]["entailed"] == "apart"   # apart stands
    # the person's own code may be read beside
    own = {**cat, "source": {**cat["source"], "obtained": "own"}}
    assert tc.beside_allowed(own, items) == (True, "the person's own code")
    # tally records no lane: beside is refused
    f = fab(weighed["cat"], weighed["items"])
    lay = layout_of(ctx(tmp_path), f, "go")
    with pytest.raises(MoveError, match="no licence records its lane"):
        code_of(ctx(tmp_path, engine=tc.thym_engine(beside=source)), f, "go", lay)


# ---------------------------------------------------------------------------
# the experiment's four cshorts (x0 step A8), read as text
# ---------------------------------------------------------------------------

A8 = [("vulture", "go-apart", VULTURE, "N:target/go"), ("vulture", "go-beside", VULTURE, "N:target/go"),
      ("sloppy-xml-py", "rust-apart", SLOPPY, "N:target/rust"),
      ("sloppy-xml-py", "rust-beside", SLOPPY, "N:target/rust")]


@pytest.mark.parametrize("repo, cshort, path, target", A8)
def test_the_four_a8_cshorts_answer_every_kept_interface(repo, cshort, path, target):
    folder = X0 / repo / "told" / cshort
    if not (folder / "CSHORT.md").is_file():
        pytest.skip("the experiment's cshorts are not on this machine")
    _cat, items, _f = _fixture(path)

    def text(rel: str) -> str | None:
        p = (folder / rel).resolve()
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() and folder in p.parents else None
    md = (folder / "CSHORT.md").read_text(encoding="utf-8")
    assert tc.surface_problems(items, target, md, file_text=text) == []
    # and not by reading loosely: without the rows, every kept interface is unanswered
    kept = [d for d in items if d["id"].startswith("C:interface/") and tc.surface_kept(d, target)]
    assert len(tc.surface_problems(items, target, "# nothing\n", file_text=text)) == len(kept) > 10


def test_the_surface_reader_takes_the_experiments_rows():
    rows = tc.read_surface("| interface | ruling for Go | file | name(s) |\n|---|---|---|---|\n"
                           "| V-I1 the report | kept | `core.go` | `(*vulture).report`, `kindOrder` |\n\n"
                           "| item | file | name |\n|---|---|---|\n"
                           "| `C:interface/a.TreeBuilder` and its eight methods | `src/tree.rs` | trait `TreeBuilder` |\n")
    assert rows[0] == {"cell": "V-I1 the report", "files": ["core.go"], "names": ["(*vulture).report", "kindOrder"]}
    assert rows[1]["files"] == ["src/tree.rs"]          # each table's header says which cell is which
    assert [tc.principal_name(x) for x in ("(*vulture).report", "item.whitelistLine", "TreeBuilder::{a, b}",
                                           "stream_parse(XmlInput) -> Events", "Events: Iterator<Item = X>")] == \
        ["report", "whitelistLine", "TreeBuilder", "stream_parse", "Events"]
    items = [{"id": "C:interface/a.TreeBuilder", "ruling": [{"is": "kept"}]},
             {"id": "C:interface/a.TreeBuilder.get_root", "ruling": [{"is": "alike", "allowing": "own-types"}]},
             {"id": "C:interface/a.free", "ruling": [{"is": "free", "because": "help"}]},
             {"id": "C:interface/command.v", "ruling": [{"is": "kept", "because": "as V-I1"}]},
             {"id": "C:interface/x0.V-I1", "worksheet-id": "V-I1", "ruling": [{"is": "kept"}]}]
    md = ("| item | file | name |\n|---|---|---|\n| `C:interface/a.TreeBuilder` and its eight methods | `tree.rs` | "
          "`TreeBuilder` |\n| V-I1 the report | `core.go` | `report` |\n")
    files = {"tree.rs": "pub trait TreeBuilder {}", "core.go": "func (v *vulture) report() {}"}
    assert tc.surface_problems(items, "N:target/go", md, file_text=files.get) == []
    files["core.go"] = "func (v *vulture) other() {}"
    assert [i for i, _ in tc.surface_problems(items, "N:target/go", md, file_text=files.get)] == \
        ["C:interface/command.v", "C:interface/x0.V-I1"]


# ---------------------------------------------------------------------------
# evidence, never claimed
# ---------------------------------------------------------------------------

def test_evidence_is_read_from_a_verdict_never_claimed(tmp_path):
    doc = mc.yaml_load(VULTURE.read_text(encoding="utf-8"))
    doc["shorts"].append({"path": "vulture.cshort-go-2026-11-18-1200/", "order": "code", "language": "go",
                          "target": "N:target/go", "layout": "vulture.layout-go-2026-11-18-1200.md",
                          "entailed": "apart", "evidence": []})
    p = tmp_path / "vulture.fabulac.cosm"
    p.write_text(mc.dump(doc), encoding="utf-8")
    assert not [x for x in FAB.lint(p).problems() if x.check == "evidence-stated" and x.severity == "error"]
    doc["shorts"][-1]["evidence"] = {"level": 3, "steps": {"kept": 89, "agree": 89}}      # claimed, with no verdict
    p.write_text(mc.dump(doc), encoding="utf-8")
    errs = [x.message for x in FAB.lint(p).problems() if x.check == "evidence-stated" and x.severity == "error"]
    assert any("names the verdict file and its digest" in m for m in errs)


# ---------------------------------------------------------------------------
# the dialectic: the weighing that stands
# ---------------------------------------------------------------------------

def test_target_ref_reads_the_latest_weighing_and_rulings_stay_on_the_first(tmp_path, weighed):
    cat, items = weighed["cat"], copy.deepcopy(weighed["items"])
    out = TT.weigh(tmp_path, cat, items, "go")                    # a second weighing of go, beside the first
    nodes = TT.nodes_of(out)
    second = next(d for d in nodes if d["id"] == "N:target/go-2")
    second["at"] = "2026-11-19"
    p = tmp_path / "tally.fabulac.cosm"
    p.write_text(mc.dump({**out.payload, "nodes": nodes}), encoding="utf-8")
    led = dl.open_twin(p).ledger
    assert dl.target_ref(led, "go") == "N:target/go-2" and dl.rulings_ref(led, "go") == "N:target/go"
    assert dl.target_ref(led, "N:target/go") == "N:target/go" and dl.rulings_ref(led, "N:target/go-2") == "N:target/go"
    r = dl.raise_questions(led, target="go", at="2026-11-19T10:00:00Z")
    tb = [q["about"] for q in r.questions if q["raised"]["from"].startswith("transconception-target/")]
    assert tb and all(a.startswith("N:target/go-2#") for a in tb)    # the bank asks the points that stand
    made_for = {(q.get("proposed") or {}).get("made-for") for q in r.questions if q.get("proposed")}
    assert made_for <= {"N:target/go", None}                        # rulings are made for the first
    with pytest.raises(dl.DialecticError, match="weigh it first"):
        dl.target_ref(led, "zig")


# ---------------------------------------------------------------------------
# the declaration, the prompts, and a program that entails
# ---------------------------------------------------------------------------

def test_entail_in_a_language_is_declared_with_the_texts_contracts():
    e = dc.load().view(1)["entail"]
    assert e.modifiers["in"] == ("string",) and "short" in e.modifiers["with"] and "layout" in e.modifiers["as"]
    rules = {(r[1], r[3] if len(r) > 3 else None): r[2] for r in e.contract_when}
    assert list(rules[(("code",), ("short",))]) == ["target-confirmed", "files-present", "surface-answered", "apart",
                                                    "footer", "provenance"]
    assert list(rules[(("layout",), None)]) == ["target-confirmed", "surface-answered", "no-invention", "footer",
                                                "provenance"]
    assert "parses" in rules[(("code",), None)]                   # the round trip, in Python, keeps its own
    assert {"target-confirmed", "surface-answered", "apart"} <= set(ct.CHECKS)
    assert C.CHECKS.lookup("footer", "layout") is TR._layout_footer
    assert C.CHECKS.lookup("no-invention", "layout") is TR._layout_no_invention


def test_the_prompts_carry_what_made_the_writers_succeed():
    assert FP.step({"fabulac": "layout"}) == "layout" and FP.step({"fabulac": "code-in"}) == "code-in"
    assert len(TP.LAYOUT_SYSTEM) < 2000 and len(TP.CODE_IN_SYSTEM) + max(map(len, TP.SEEN.values())) < 2000
    m = FP.messages({}, {"fabulac": "code-in", "language": "Rust", "name": "sloppy", "path": "src/lib.rs",
                         "layout": "L", "brief": "b: 1\n", "entailed": "apart", "source": "x = 1"})
    sys_, user = m[0]["content"], m[1]["content"]
    assert "Rust" in sys_ and "The cases are the judge" in sys_ and "a guess is never silent" in sys_
    assert "never seen the original's code" in sys_ and "x = 1" not in user      # apart: no source, even if handed
    lm = FP.messages({}, {"fabulac": "layout", "language": "Go", "map": "- C:interface/a: a", "types": "(none)",
                          "gaps": "(none)", "program": "{}", "name": "t", "suffixes": ".go", "conditions": "(none)"})
    assert "own-types" in lm[0]["content"] and "Each gap the weighing found is filled" in lm[0]["content"]


ENTAIL_PROGRAM = """thym 1

program entail-in-a-language
  why: a weighed and confirmed language gets a layout first, then the code, apart from the source.

  takes f: fabula, language: string
  gives arrangement: short, code: folder

  let drawn = entail f as layout in language
  give arrangement: drawn
  give code: entail f as code in language with drawn
end
"""


class Scripted:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def complete(self, contract, inputs, *, budget):
        ins = {k: (v[0] if isinstance(v, tuple) else v) for k, v in inputs.items()}
        ins = {k: v if isinstance(v, Value) else Value("string", str(v)) for k, v in ins.items()}
        step = _t(ins, "fabulac")
        self.sent.append(step)
        if step == "layout":
            return candidate(layout_reply(ins), engine="model:scripted", tokens=10)
        return candidate(writer_reply(ins), engine="model:scripted", tokens=10)


def test_a_program_entails_tally_in_go_under_contract(tmp_path, weighed):
    (tmp_path / "tally.fabulac.cosm").write_text(mc.dump({**weighed["cat"], "nodes": weighed["items"]}),
                                                 encoding="utf-8")
    (tmp_path / "language.txt").write_text("go", encoding="utf-8")
    prog = tmp_path / "entail.thym"
    prog.write_text(ENTAIL_PROGRAM, encoding="utf-8")
    c = thym.check_file(prog)
    assert not isinstance(c, Refusal), str(c)
    rows = [{"name": "f", "type": "fabula", "path": "tally.fabulac.cosm",
             "sha256": digest_path(tmp_path / "tally.fabulac.cosm")},
            {"name": "language", "type": "string", "path": "language.txt",
             "sha256": digest_path(tmp_path / "language.txt")}]
    p = pl.plan(c, rows, program="entail-in-a-language")
    assert not isinstance(p, Refusal), str(p)
    cp = Scripted()
    t = RUN.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=prog, coprocessor=cp,
                engines=H.engines(feed=None), now=NOW)
    assert t.landed, getattr(t, "refusal", t)
    assert cp.sent == ["layout", "code-in", "code-in"]
    for rec in t.records:
        assert all(x["ok"] for x in rec.get("checks") or []), rec.get("checks")
    names = {x["name"] for rec in t.records for x in rec.get("checks") or []}
    assert {"target-confirmed", "surface-answered", "apart", "files-present", "no-invention", "footer"} <= names
    code = Path(t.outputs["code"])
    assert (code / "CSHORT.md").is_file() and (code / "requests.jsonl").is_file() and (code / "main.go").is_file()
