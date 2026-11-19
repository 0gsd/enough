"""A head states the members of each class that crosses between parts (0.8, lane W5-HD; pins 21, the finding of
W4-G3 and W3-G2: Thym's compiler rebuilt 474 of 968 because the head said `class Registry` and not that
`Registry.manifests` is a map by name; documents rebuilt 63 of 76 because no fabulac said `Volume.items` is a map of
items). `make_head` reads each crossing class's methods and fields from its source by rule (`ast`), reaches the classes
their types name, and `interfaces-agree` holds a part's copy of a member to the head's.

Fixtures: the counter head of tests/fixtures/fabula/head/ (copied, with a class added to counter-core), and a small
reader shaped like enough's (`Registry.manifests` a typed map, `Volume.items` an untyped one filled by `load`).
"""
from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

from enough import fabula
from enough import fabulac_head as H
from enough import macrocosm as mc

FIX = Path(__file__).resolve().parent / "fixtures" / "fabula" / "head"
PROV = "provenance: {mode: manual, sources: [the test], confidence: 1}"


def _errors(p: Path) -> list[str]:
    return [f"{x.check}: {x.message}" for x in fabula.lint(p).problems()
            if x.check in H.CHECKS and x.severity == "error"]


def _nodes(path: Path, yaml_items: str) -> None:
    """Append items to a fabulac's `nodes` (its last key)."""
    text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    path.write_text(text + textwrap.indent(textwrap.dedent(yaml_items).strip("\n"), "  ") + "\n", encoding="utf-8")


def _by_id(head: Path) -> dict[str, dict]:
    return {n["id"]: n for n in mc.yaml_load(head.read_text(encoding="utf-8"))["nodes"]}


# ---------------------------------------------------------------------------
# Reading a class's members by rule
# ---------------------------------------------------------------------------

READER = '''\
"""A small reader, shaped like enough's."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Manifest:
    name: str
    data: dict = field(repr=False)


@dataclass
class Item:
    key: str
    data: dict = field(default_factory=dict)


class Registry:
    """Every manifest, by name."""

    def __init__(self, dirs: list[Path] | None = None):
        self.dirs = [Path(".")] if dirs is None else [Path(d) for d in dirs]
        found = {}
        self.manifests: dict[str, Manifest] = {n: found[n] for n in found}
        self.problems: list[str] = []
        self._cache = {}

    def get(self, name: str) -> Manifest | None:
        """The manifest of that name, or None."""
        if not name:
            raise ValueError("a name")
        return self.manifests.get(name)

    def _hidden(self):
        return None


@dataclass
class Volume:
    path: Path
    items: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return ""


def load(path: Path) -> Volume:
    """A volume read from path."""
    vol = Volume(path)
    it = Item("a")
    vol.items[it.key] = it
    return vol
'''


def test_a_class_like_registry_is_read_with_its_typed_map_and_its_methods():
    reg = H.class_members(READER, "Registry")
    assert [m["name"] for m in reg["methods"]] == ["__init__", "get"]            # not _hidden
    get = reg["methods"][1]
    assert get["signature"] == "def get(self, name: str) -> Manifest | None"
    assert get["takes"] == [{"name": "name", "type": "str", "required": True}]
    assert get["gives"] == {"type": "Manifest | None"} and get["raises"] == [{"error": "ValueError"}]
    assert get["summary"] == "The manifest of that name, or None."
    fields = {f["name"]: f for f in reg["fields"]}
    assert set(fields) == {"dirs", "manifests", "problems"}                      # not _cache
    assert fields["manifests"] == {"name": "manifests", "type": "dict[str, Manifest]", "kind": "map",
                                   "means": "a map from text to Manifest"}
    assert fields["dirs"] == {"name": "dirs", "type": "list[Path]", "kind": "list", "means": "a list of Path"}
    assert fields["problems"]["kind"] == "list"
    assert not reg["record"]


def test_an_untyped_map_says_what_the_module_puts_in_it_and_a_record_its_defaults():
    vol = H.class_members(READER, "Volume")
    items = {f["name"]: f for f in vol["fields"]}["items"]
    assert items == {"name": "items", "type": "dict", "default": "dict()", "required": False, "kind": "map",
                     "means": "a map from each Item's key to that Item"}
    assert [m["signature"] for m in vol["methods"]] == ["@property def id(self) -> str"]
    man = H.class_members(READER, "Manifest")
    assert man["record"] and man["frozen"]
    assert {f["name"]: f.get("required") for f in man["fields"]} == {"name": True, "data": True}
    assert H.class_members(READER, "Nothing") is None


def test_a_methods_line_is_the_surveys_so_a_parts_own_reading_agrees():
    """The head's signature rule is the survey's (`repo_engine._signature`, decorators before it as the code moves
    join them): over every method of the reader's classes, the two agree byte for byte."""
    import ast

    from enough import repo_engine as RE
    src = Path(mc.__file__)
    text = src.read_text(encoding="utf-8")
    tree = ast.parse(text)
    n = 0
    for cls in (c for c in tree.body if isinstance(c, ast.ClassDef)):
        for fn in (f for f in cls.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))):
            survey = " ".join([f"@{RE._seg(text, d)}" for d in fn.decorator_list] + [RE._signature(text, fn)])
            assert H.def_line(text, fn) == survey
            n += 1
    assert n > 50


def test_a_function_no_fabulac_read_is_stated_from_its_syntax():
    it = H.function_item(READER, "load", "C:interface/outside.reader.load", where="reader.py")
    assert (it["surface"], it["signature"], it["gives"], it["summary"]) == (
        "function", "def load(path: Path) -> Volume", {"type": "Volume"}, "A volume read from path.")
    assert it["takes"] == [{"name": "path", "type": "Path", "required": True}]
    assert it["provenance"]["sources"] == ["reader.py#L48-L53"]
    assert H.function_item(READER, "nothing", "C:interface/x") is None


def test_plain_kinds_of_types_as_written():
    assert [H.plain_kind(t) for t in ("dict[str, Manifest]", "list[Path] | None", "Optional[int]", "Any", "Manifest",
                                      "str | int", "bool", "Path", "tuple[str, ...]", "")] == \
        ["map", "list", "whole number", None, "record", None, "yes-or-no", "path", "list", None]


# ---------------------------------------------------------------------------
# The counter head, with a class that crosses
# ---------------------------------------------------------------------------

TALLY = '''

class Tally:
    """Counts lines per name."""

    def __init__(self, names: list[str] | None = None):
        self.counts: dict[str, int] = {}
        self.seen = []

    def add(self, name: str, text: str) -> int:
        n = count_lines(text)
        self.counts[name] = self.counts.get(name, 0) + n
        self.seen.append(name)
        return n
'''


def _counter_with_a_class(tmp: Path) -> list[Path]:
    for name in ("counter-core", "counter-cli"):
        shutil.copytree(FIX / name, tmp / name)
        text = (FIX / f"{name}.fabulac.cosm").read_text().replace("head: oes:fabula/counter\n", "")
        (tmp / f"{name}.fabulac.cosm").write_text(text.replace(
            "    stated-in: oes:fabula/counter/C/interface/count-lines\n", ""))
    with (tmp / "counter-core" / "counter_core.py").open("a") as f:
        f.write(TALLY)
    _nodes(tmp / "counter-core.fabulac.cosm", f"""
        - id: C:file/counter-core-py
          type: file
          name: counter_core.py
          summary: The counting.
          path: counter_core.py
          stance: observed
          {PROV}
        - id: C:interface/tally
          type: interface
          name: Tally
          summary: Tally counts lines per name.
          surface: class
          signature: "class Tally"
          defined-in: C:file/counter-core-py
          stance: observed
          {PROV}
        """)
    return [tmp / "counter-core.fabulac.cosm", tmp / "counter-cli.fabulac.cosm"]


TALLY_IFACE = {"id": "C:interface/tally", "type": "interface", "name": "Tally", "summary": "Counts lines per name.",
               "surface": "class", "signature": "class Tally", "stance": "axiom",
               "provenance": {"mode": "manual", "sources": ["the test"], "confidence": 1}}


def test_the_counter_head_states_a_crossing_class_with_its_methods_and_fields(tmp_path: Path):
    parts = _counter_with_a_class(tmp_path)
    head = tmp_path / "counter.fabulac.cosm"
    out = H.make_head(head, parts, name="counter", licence="MIT", at="2026-11-19", interfaces=[TALLY_IFACE])
    assert out["members"] == {"C:interface/tally": 3} and out["unread"] == []
    got = _by_id(head)
    assert got["C:interface/tally.add"]["signature"] == "def add(self, name: str, text: str) -> int"
    assert got["C:interface/tally.add"]["surface"] == "method" and got["C:interface/tally.add"]["name"] == "Tally.add"
    assert got["C:interface/tally.add"]["gives"] == {"type": "int"}
    assert got["C:interface/tally.__init__"]["takes"] == [
        {"name": "names", "type": "list[str] | None", "default": "None", "required": False}]
    fields = {f["name"]: f for f in got["C:structure/tally"]["fields"]}
    assert fields["counts"]["means"] == "a map from text to whole number"
    assert fields["seen"] == {"name": "seen", "type": "list", "kind": "list", "means": "a list of text"}
    assert "oes:fabula/counter-core: counter_core.py#L" in got["C:structure/tally"]["provenance"]["sources"][0]
    # the cli's copy of the class, stated in the head: both checks hold
    _nodes(parts[1], f"""
        - id: C:interface/tally
          type: interface
          name: Tally
          summary: The command line keeps a Tally.
          surface: class
          signature: "class Tally"
          stated-in: oes:fabula/counter/C/interface/tally
          stance: observed
          {PROV}
        - id: C:interface/tally.add
          type: interface
          name: Tally.add
          summary: It adds a text's lines under a name.
          surface: method
          signature: "def add(self, name: str, text: str) -> int"
          takes:
            - {{name: name, type: str, required: true}}
            - {{name: text, type: str, required: true}}
          stance: observed
          {PROV}
        """)
    H.stamp_parts(head)
    for p in [head] + parts:
        assert _errors(p) == [], (p.name, _errors(p))
    # a member the cli says otherwise fails, as a member of the class it is stated in
    text = parts[1].read_text()
    parts[1].write_text(text.replace('signature: "def add(self, name: str, text: str) -> int"',
                                     'signature: "def add(self, name: str) -> int"'))
    assert _errors(parts[1]) == [
        "interfaces-agree: C:interface/tally.add does not agree with oes:fabula/counter/C/interface/tally.add, "
        "a member of C:interface/tally, in its signature"]
    assert H.make_head(tmp_path / "bare.fabulac.cosm", parts, interfaces=[TALLY_IFACE], members=False,
                       at="2026-11-19")["members"] == {}


# ---------------------------------------------------------------------------
# A head over a reader shaped like enough's: Registry.manifests, and Volume reached through load
# ---------------------------------------------------------------------------

PART = """\
oes: fabula/1
flavour: fabulac
id: fabula/{db}
name: {db}
source: {{path: {db}/, kind: folder, language: python, licence: MIT}}
derived: {{at: "2026-11-19T12:00:00Z", by: person, mode: rules, completeness: outline, chunks: 0}}
atem: {{line: "{db}, a part.", focus: one part, push: the head names it, pull: it is small}}
nodes:
  - id: R:licence/licence
    type: licence
    name: licence
    summary: The terms {db} is offered on.
    stance: axiom
    {prov}
    identifier: MIT
"""


def _reader_and_user(tmp: Path) -> list[Path]:
    (tmp / "reader").mkdir()
    (tmp / "reader" / "reader.py").write_text(READER)
    (tmp / "user").mkdir()
    (tmp / "user" / "user.py").write_text("from reader import load\n\n\ndef count(p):\n    return len(load(p).items)\n")
    for db in ("reader", "user"):
        (tmp / f"{db}.fabulac.cosm").write_text(PART.format(db=db, prov=PROV))
    _nodes(tmp / "reader.fabulac.cosm", f"""
        - id: C:file/reader-py
          type: file
          name: reader.py
          summary: The reader.
          path: reader.py
          stance: observed
          {PROV}
        - id: C:interface/reader.Registry
          type: interface
          name: Registry
          summary: Every manifest, by name.
          surface: class
          signature: "class Registry"
          defined-in: C:file/reader-py
          stance: observed
          {PROV}
        - id: C:interface/reader.Volume
          type: interface
          name: Volume
          summary: A volume.
          surface: class
          signature: "class Volume"
          defined-in: C:file/reader-py
          stance: observed
          {PROV}
        - id: C:interface/reader.Item
          type: interface
          name: Item
          summary: One item.
          surface: class
          signature: "class Item"
          defined-in: C:file/reader-py
          stance: observed
          {PROV}
        - id: C:interface/reader.Manifest
          type: interface
          name: Manifest
          summary: One manifest.
          surface: class
          signature: "class Manifest"
          defined-in: C:file/reader-py
          stance: observed
          {PROV}
        - id: C:interface/reader.load
          type: interface
          name: load
          summary: A volume read from path.
          surface: function
          signature: "def load(path: Path) -> Volume"
          defined-in: C:file/reader-py
          takes:
            - {{name: path, type: Path, required: true}}
          gives: {{type: Volume}}
          stance: observed
          {PROV}
        - id: C:interface/reader.Registry.get
          type: interface
          name: Registry.get
          summary: The manifest of a name, as the reader's own reading says it.
          surface: method
          signature: "def get(self, name: str) -> Manifest | None"
          defined-in: C:file/reader-py
          takes:
            - {{name: name, type: str, required: true, means: the manifest's name}}
          gives: {{type: Manifest | None}}
          stance: observed
          {PROV}
        """)
    return [tmp / "reader.fabulac.cosm", tmp / "user.fabulac.cosm"]


def _iface(item_id: str, name: str, surface: str, signature: str) -> dict:
    return {"id": item_id, "type": "interface", "name": name, "summary": f"{name}, between the parts.",
            "surface": surface, "signature": signature, "stance": "axiom",
            "provenance": {"mode": "manual", "sources": ["the test"], "confidence": 1}}


def test_a_head_states_registry_manifests_and_reaches_volume_and_its_items(tmp_path: Path):
    parts = _reader_and_user(tmp_path)
    head = tmp_path / "tool.fabulac.cosm"
    given = [_iface("C:interface/outside.reader.Registry", "Registry", "class", "class Registry"),
             _iface("C:interface/outside.reader.load", "load", "function", "def load(path: Path) -> Volume")]
    out = H.make_head(head, parts, name="tool", licence="MIT", at="2026-11-19", interfaces=given)
    assert out["unread"] == []
    assert set(out["members"]) == {"C:interface/outside.reader.Registry", "C:interface/outside.reader.Volume",
                                   "C:interface/outside.reader.Manifest", "C:interface/outside.reader.Item"}
    got = _by_id(head)
    manifests = {f["name"]: f for f in got["C:structure/outside.reader.Registry"]["fields"]}["manifests"]
    assert (manifests["type"], manifests["kind"], manifests["means"]) == ("dict[str, Manifest]", "map",
                                                                          "a map from text to Manifest")
    items = {f["name"]: f for f in got["C:structure/outside.reader.Volume"]["fields"]}["items"]
    assert (items["kind"], items["means"]) == ("map", "a map from each Item's key to that Item")
    assert "reached from C:interface/outside.reader.load" in \
        got["C:interface/outside.reader.Volume"]["provenance"]["sources"][1]
    # the reader's own reading of get lends its words: its signature is the source's
    assert got["C:interface/outside.reader.Registry.get"]["summary"] == \
        "The manifest of a name, as the reader's own reading says it."
    assert got["C:interface/outside.reader.Registry.get"]["takes"][0]["means"] == "the manifest's name"
    # the user's copy of Registry, stated in the head, holds; then one that reads manifests as a list fails
    _nodes(parts[1], f"""
        - id: C:interface/outside.reader.Registry
          type: interface
          name: Registry
          summary: The user keeps a Registry.
          surface: class
          signature: "class Registry"
          stated-in: oes:fabula/tool/C/interface/outside.reader.Registry
          stance: observed
          {PROV}
        - id: C:structure/outside.reader.Registry
          type: structure
          name: Registry
          summary: What the user takes a Registry to hold.
          fields:
            - {{name: manifests, type: "dict[str, Manifest]", kind: map}}
          stance: observed
          {PROV}
        """)
    H.stamp_parts(head)
    for p in [head] + parts:
        assert _errors(p) == [], (p.name, _errors(p))
    text = parts[1].read_text()
    parts[1].write_text(text.replace('{name: manifests, type: "dict[str, Manifest]", kind: map}',
                                     '{name: manifests, type: "list[Manifest]", kind: list}'))
    assert _errors(parts[1]) == [
        "interfaces-agree: C:structure/outside.reader.Registry does not agree with "
        "oes:fabula/tool/C/structure/outside.reader.Registry, the fields of C:interface/outside.reader.Registry: "
        "manifests's type and kind is 'list[Manifest]', 'list', the head's 'dict[str, Manifest]', 'map'"]


def test_a_class_whose_source_cannot_be_read_is_listed_unread(tmp_path: Path):
    parts = _reader_and_user(tmp_path)
    (tmp_path / "reader" / "reader.py").unlink()
    out = H.make_head(tmp_path / "tool.fabulac.cosm", parts, at="2026-11-19",
                      interfaces=[_iface("C:interface/outside.reader.Registry", "Registry", "class", "class Registry")])
    assert out["unread"] == ["C:interface/outside.reader.Registry"] and out["members"] == {}
    # a source named outright is read
    (tmp_path / "elsewhere.py").write_text(READER)
    out = H.make_head(tmp_path / "again.fabulac.cosm", [tmp_path / "user.fabulac.cosm"], at="2026-11-19",
                      interfaces=[_iface("C:interface/x.Registry", "Registry", "class", "class Registry")],
                      sources={"C:interface/x.Registry": tmp_path / "elsewhere.py"})
    assert out["members"] == {"C:interface/x.Registry": 3} and out["unread"] == []
