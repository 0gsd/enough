"""Thym's specification and its conformance fixtures hold together.

docs/THYM.md promises that every block marked ```cosm is one complete file that loads and lints clean, that every
block marked ```thym is one complete program of the conformance suite, and that the suite's expected enumerations
compile back to their programs byte for byte (the round-trip law, section 7.2). This test holds the text and the
fixtures to those promises with the reference reader now, and with the reference compiler (`enough.thym`) once it
exists: the parts that need the compiler are skipped until it lands, and the 0.5.0 compiler lane removes the skips.

It also checks that the moves every manifest declares (section 17.6) name only checks the specification defines
(section 7.3), that move names are unique across the registry, and that every refused fixture under `bad/` says
where it must be refused.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

from enough import macrocosm as mc

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "docs" / "THYM.md"
SUITE = REPO / "tests" / "fixtures" / "thym"
MANIFESTS = REPO / "defaults" / "cosm" / "manifests"

_COSM_BLOCK = re.compile(r"^```cosm\n(.*?)^```", re.S | re.M)
_THYM_BLOCK = re.compile(r"^```thym\n(.*?)^```", re.S | re.M)
_REFUSED = re.compile(r"^-- refused: (compile|plan|run) ([a-z-]+) line (\d+)$")
_CHECK_ROW = re.compile(r"^\| `([a-z-]+)` \| ", re.M)

HAVE_COMPILER = importlib.util.find_spec("enough.thym") is not None


def _text(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


def _cosm_blocks() -> list[str]:
    return _COSM_BLOCK.findall(_text(SPEC))


def _thym_blocks() -> list[str]:
    return _THYM_BLOCK.findall(_text(SPEC))


def _file_name(data: dict) -> str:
    """The name a thym volume of this kind has on disk (THYM.md 17.1)."""
    kind = data.get("kind")
    slug = str(data.get("id", "thym/x")).split("/", 1)[-1]
    if kind == "package":
        return "package.cosm"
    return f"{slug}.{ 'thym' if kind == 'program' else kind}.cosm"


def _yaml(text: str) -> dict:
    data = mc.yaml_load(text)
    assert isinstance(data, dict) and data
    return data


# ---------------------------------------------------------------------------
# The manifest and the moves
# ---------------------------------------------------------------------------

def test_thym_manifest_is_in_the_registry():
    reg = mc.Registry()
    assert reg.problems == [], reg.problems
    m = reg.get("thym")
    assert m is not None and m.version == 1 and m.title == "Thym"
    assert "thym/1" in reg.known()
    assert list(reg.manifests)[:5] == list(mc.REGISTRY_ORDER)   # the five keep their order; thym follows


def _declared_moves() -> dict[str, tuple[str, dict]]:
    """Every move declared in a manifest's moves: block or a *.moves.cosm sidecar, by name."""
    found: dict[str, tuple[str, dict]] = {}
    for p in sorted(MANIFESTS.glob("*.cosm")):
        data = _yaml(_text(p))
        if p.name.endswith(".manifest.cosm"):
            owner, moves = str(data.get("name")), data.get("moves") or []
        elif p.name.endswith(".moves.cosm"):
            owner, moves = str(data.get("moves-of")).split("/", 1)[0], data.get("moves") or []
        else:
            continue
        for mv in moves:
            name = str(mv["name"])
            assert name not in found, f"move {name} declared twice: {found[name][0]} and {owner}"
            found[name] = (owner, mv)
    return found


def test_moves_are_declared_by_their_owners():
    moves = _declared_moves()
    owners = {n: o for n, (o, _) in moves.items()}
    assert {owners[n] for n in ("derive", "tell", "atem", "expand")} == {"fabula"}
    assert {owners[n] for n in ("enumerate", "compile")} == {"doc"}
    assert {owners[n] for n in ("project", "band", "mark", "withhold")} == {"comprise"}
    assert {owners[n] for n in ("cut", "null", "measure", "morph", "read", "package", "unpack", "lint", "trace",
                                "fabula", "context", "graph", "isomorph")} == {"thym"}
    for name, (owner, mv) in moves.items():
        assert mv.get("gives"), f"{owner}: move {name} gives nothing"
        assert isinstance(mv.get("takes"), list), f"{owner}: move {name} takes is not a list"
        assert mv.get("says"), f"{owner}: move {name} says nothing"
        assert mv.get("asks") in (None, True, False)


def test_every_contract_check_is_defined_in_the_spec():
    text = _text(SPEC)
    section = text[text.index("### 7.3 The named checks"):text.index("### 7.4")]
    defined = set(_CHECK_ROW.findall(section))
    assert len(defined) >= 30
    for name, (owner, mv) in _declared_moves().items():
        for check in mv.get("contract") or []:
            assert check in defined, f"{owner}: move {name} names a check the spec does not define: {check}"


def test_comprise_manifest_is_still_a_byte_copy():
    """The sidecar exists because comprise.manifest.cosm is never edited in enough (MacroCOSM 13.4)."""
    assert "\nmoves:" not in _text(MANIFESTS / "comprise.manifest.cosm")
    sidecar = _yaml(_text(MANIFESTS / "comprise.moves.cosm"))
    assert sidecar["moves-of"] == "comprise/1"


# ---------------------------------------------------------------------------
# The blocks of the specification
# ---------------------------------------------------------------------------

def test_spec_exists_and_has_examples():
    assert SPEC.is_file()
    assert len(_cosm_blocks()) >= 1
    assert len(_thym_blocks()) >= 6


@pytest.mark.parametrize("index", range(len(_cosm_blocks()) if SPEC.is_file() else 0))
def test_spec_cosm_block_loads_and_lints_clean(index, tmp_path):
    text = _cosm_blocks()[index]
    data = _yaml(text)
    assert next(iter(data)) == "oes", f"cosm block {index + 1} does not start with its declaration"
    assert data["oes"] == "thym/1"
    path = tmp_path / _file_name(data)
    path.write_text(text, encoding="utf-8")
    volume = mc.load_volume(path)
    assert volume.refused is None, f"cosm block {index + 1} refused: {volume.refused}"
    report = mc.lint(volume)
    assert report.ok, f"cosm block {index + 1}: " + "; ".join(str(e) for e in report.errors)
    assert not report.warnings, f"cosm block {index + 1}: " + "; ".join(str(w) for w in report.warnings)


@pytest.mark.parametrize("index", range(len(_thym_blocks()) if SPEC.is_file() else 0))
def test_spec_thym_block_is_a_complete_program(index):
    text = _thym_blocks()[index]
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("--")]
    assert lines[0] == "thym 0", f"thym block {index + 1} does not start with its version line"
    assert lines[-1] == "end", f"thym block {index + 1} does not close its last block"
    assert re.search(r"^(program|move|morph|context) [a-z][a-z0-9-]*", text, re.M)
    if not HAVE_COMPILER:
        pytest.skip("enough.thym is not built yet: the 0.5.0 compiler lane compiles every thym block")
    from enough.thym import Refusal, check, parse
    # `use oes:thym/house` (section 8.4) names the install's volume; a stand-in holding `rosa` answers for it.
    house = {"oes": "thym/1", "kind": "morph", "id": "thym/house", "name": "house",
             "nodes": [{"id": "M:morph/rosa", "type": "morph", "name": "rosa", "summary": "The house voice."}]}
    module = parse.parse(text)
    result = module if isinstance(module, Refusal) else check.check(module, volumes={"oes:thym/house": house})
    assert not isinstance(result, Refusal), f"thym block {index + 1} refused: {result}"


def test_the_three_programs_of_the_spec_are_the_suite_s():
    """The suite's first three programs are the specification's blocks, byte for byte."""
    blocks = {re.search(r"^program ([a-z-]+)", b, re.M).group(1): b for b in _thym_blocks()}
    for name in ("publish-story", "read-my-way", "open-house"):
        assert blocks[name] == _text(SUITE / "programs" / f"{name}.thym"), f"{name}: the spec and the suite differ"


# ---------------------------------------------------------------------------
# The conformance suite
# ---------------------------------------------------------------------------

def _programs() -> list[Path]:
    return sorted(SUITE.glob("programs/*.thym"))


def test_suite_layout():
    assert (SUITE / "README.md").is_file()
    names = [p.stem for p in _programs()]
    assert names[:0] == [] and {"publish-story", "read-my-way", "open-house"} <= set(names)
    for name in names:
        assert (SUITE / "expected" / name / "items.cosm").is_file(), f"{name}: no expected enumeration"
        assert (SUITE / "expected" / name / "plan.cosm").is_file(), f"{name}: no expected plan"
    assert len(list(SUITE.glob("bad/*.thym"))) >= 10


@pytest.mark.parametrize("program", [p.stem for p in _programs()] if SUITE.is_dir() else [])
def test_expected_items_compile_back_byte_for_byte(program, tmp_path):
    src = SUITE / "programs" / f"{program}.thym"
    items_path = SUITE / "expected" / program / "items.cosm"
    data = _yaml(_text(items_path))
    assert data["oes"] == "thym/1" and data["kind"] == "program"
    assert data["source"]["path"] == src.name
    assert data["source"]["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
    assert data["source"]["size"] == len(src.read_bytes())
    # The round-trip law: front, then every top-level item's body in order, is the file.
    tops = sorted((i for i in data["nodes"] if "order" in i), key=lambda i: i["order"])
    assert tops, f"{program}: no top-level items carry order"
    compiled = data.get("front", "") + "".join(i["body"] for i in tops)
    assert compiled == _text(src), f"{program}: the items do not compile back to the program"
    # Every step's text is the line it says it is.
    lines = _text(src).split("\n")
    steps = [i for i in data["nodes"] if i["type"] == "step"]
    assert steps
    for s in steps:
        assert lines[s["line"] - 1] == s["text"], f"{program}: step {s['id']} is not line {s['line']}"
    # And the volume loads and lints clean under the reader.
    path = tmp_path / f"{program}.thym.cosm"
    path.write_text(_text(items_path), encoding="utf-8")
    volume = mc.load_volume(path)
    assert volume.refused is None, volume.refused
    report = mc.lint(volume)
    assert report.ok and not report.warnings, "; ".join(str(e) for e in report.errors + report.warnings)


@pytest.mark.parametrize("program", [p.stem for p in _programs()] if SUITE.is_dir() else [])
def test_expected_plan_is_acyclic_and_lints_clean(program, tmp_path):
    plan_path = SUITE / "expected" / program / "plan.cosm"
    data = _yaml(_text(plan_path))
    assert data["oes"] == "thym/1" and data["kind"] == "plan"
    assert data["program"]["name"] == program
    nodes = {i["id"]: i for i in data["nodes"] if i["type"] == "node"}
    assert nodes
    state: dict[str, int] = {}

    def visit(nid: str) -> None:
        assert state.get(nid) != 1, f"{program}: the plan has a cycle at {nid}"
        if state.get(nid) == 2:
            return
        state[nid] = 1
        for prev in nodes[nid].get("after") or []:
            assert prev in nodes, f"{program}: {nid} runs after an unknown node {prev}"
            visit(prev)
        state[nid] = 2

    for nid in nodes:
        visit(nid)
    asks = sum(1 for n in nodes.values() if n.get("asks") is True)
    root = next(i for i in data["nodes"] if i["type"] == "plan")
    assert root["asks"] == asks == data["estimate"]["asks"]
    assert data["estimate"]["steps"] == len(nodes)
    path = tmp_path / "fixture.plan.cosm"
    path.write_text(_text(plan_path), encoding="utf-8")
    volume = mc.load_volume(path)
    assert volume.refused is None, volume.refused
    report = mc.lint(volume)
    assert report.ok and not report.warnings, "; ".join(str(e) for e in report.errors + report.warnings)


@pytest.mark.parametrize("bad", sorted(p.name for p in SUITE.glob("bad/*.thym")) if SUITE.is_dir() else [])
def test_refused_fixture_says_where(bad):
    text = _text(SUITE / "bad" / bad)
    first = text.split("\n", 1)[0]
    m = _REFUSED.match(first)
    assert m, f"{bad}: the first line must read '-- refused: <stage> <check> line <n>'"
    stage, check, line = m.group(1), m.group(2), int(m.group(3))
    assert 1 <= line <= text.count("\n"), f"{bad}: line {line} is not in the file"
    assert stage == "compile", f"{bad}: bad/ holds compile-time refusals only"
    if not HAVE_COMPILER:
        pytest.skip("enough.thym is not built yet: the 0.5.0 compiler lane refuses every bad fixture at its line")
    from enough.thym import Refusal
    from enough.thym import check as thym_check
    from enough.thym import parse as thym_parse
    module = thym_parse.parse(text, path=str(SUITE / "bad" / bad))
    result = module if isinstance(module, Refusal) else thym_check.check(module)
    assert isinstance(result, Refusal), f"{bad}: compiled, and it must be refused ({check} at line {line})"
    assert (result.stage, result.check, result.line) == (stage, check, line), f"{bad}: {result}"


def test_suite_inputs_are_consistent():
    pkg = SUITE / "inputs" / "orchard-notes.thym"
    assert (pkg / "text.md").read_bytes() == (SUITE / "inputs" / "notes.md").read_bytes()
    fab = _yaml(_text(pkg / "fabula.cosm"))
    assert fab["oes"] == "emf/1" and fab["source"]["path"] == "text.md"
    for p in (SUITE / "inputs" / "plain-letter.morph.cosm", SUITE / "inputs" / "on-the-train.context.cosm",
              pkg / "package.cosm"):
        volume = mc.load_volume(p)
        assert volume.refused is None, f"{p.name}: {volume.refused}"
        report = mc.lint(volume)
        assert report.ok and not report.warnings, f"{p.name}: " + "; ".join(str(e) for e in report.errors + report.warnings)
