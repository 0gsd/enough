"""Thym 1, part b: the folder type and folder.py, line and change, several outputs, `in` with a text, the loop's `where`
after a call, and the declaration keys that choose by the call (docs/fabula-pins-thym1.md 2a, 2e types, 2f, 3.1;
THYM 4.5, 5.1, 8.2, 12.1, 12.4, 17.6, 20.1 to 20.4; MacroCOSM OES 18.4.1)."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym import check as ck
from enough.thym import declarations as dc
from enough.thym import enumerate as en
from enough.thym import folder as F
from enough.thym import parse as ps
from enough.thym import plan as pl
from enough.thym import run as RUN
from enough.thym import types as ty
from enough.thym import values as V

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "tests" / "fixtures" / "thym"
LITTLE = SUITE / "inputs" / "little-tool"
#: The tree digest of the suite's little-tool folder, as the reference code (docs/fabula-pins-schema.md appendix G)
#: gives it: 6 files read, 616 bytes, 1 skipped (docs/logo.png).
LITTLE_TREE = "dfef659dbe23efd61025ed62c67ec01c82ee0d7d5c68effa940584dbc96b48ea"


def compile_text(text: str, *, path: str | None = None, decls=None):
    m = ps.parse(text, path=path)
    return m if isinstance(m, Refusal) else ck.check(m, decls=decls)


def ok(text: str, **kw):
    r = compile_text(text, **kw)
    assert not isinstance(r, Refusal), str(r)
    return r


def refused(text: str, **kw) -> Refusal:
    r = compile_text(text, **kw)
    assert isinstance(r, Refusal), "compiled, and it must be refused"
    return r


# ---------------------------------------------------------------------------
# The reference code, verbatim in what it computes (appendix G), to hold folder.py to it
# ---------------------------------------------------------------------------

_REF_SKIP_DIRS = {".git", ".hg", ".svn", ".bzr", "_darcs", "CVS", ".venv", "venv", "__pypackages__", ".tox", ".nox",
                  "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis",
                  ".ipynb_checkpoints", ".cache", "htmlcov", "build", "dist", ".eggs"}
_REF_SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", ".coverage"}
_REF_SKIP_SUFFIXES = (".pyc", ".pyo", ".so", ".pyd", ".dylib", ".dll", ".o", ".a", ".class")


def reference_tree(root: Path) -> dict:
    out, skipped = [], 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink() and not (
            d in _REF_SKIP_DIRS or d.endswith(".egg-info") or ".cshort-" in d or (here / d / "pyvenv.cfg").is_file())]
        for f in filenames:
            p = here / f
            if (p.is_symlink() or f in _REF_SKIP_FILES or f.endswith(_REF_SKIP_SUFFIXES)
                    or f.endswith(".fabulac.cosm") or ".catem-" in f):
                skipped += 1
                continue
            data = p.read_bytes()
            if len(data) > 1_000_000 or b"\0" in data[:8192]:
                skipped += 1
                continue
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                skipped += 1
                continue
            out.append((p.relative_to(root).as_posix(), hashlib.sha256(data).hexdigest(), len(data)))
    out.sort(key=lambda r: r[0].encode("utf-8"))
    h = hashlib.sha256()
    for rel, digest, _ in out:
        h.update(rel.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n")
    return {"files": len(out), "bytes": sum(s for _, _, s in out), "skipped": skipped, "tree": h.hexdigest()}


@pytest.fixture
def tricky(tmp_path):
    """A folder that the two rules read differently, with links of every kind."""
    t = tmp_path / "tricky"
    files = {"a.py": b"x = 1\n", ".github/ci.yml": b"on: push\n", ".env": b"SECRET=1\n", "build/out.py": b"y\n",
             "venv/lib.py": b"z\n", "pkg/__pycache__/m.pyc": b"\x00\x01", "pkg/m.py": b"m\n",
             "late-nul.txt": b"a" * 9000 + b"\0", "big.txt": b"b" * 1_000_001, "x.fabulac.cosm": b"oes: fabula/1\n",
             "bom.md": b"\xef\xbb\xbfhi\n", "node_modules/q.js": b"q\n", "env2/pyvenv.cfg": b"home=x\n",
             "env2/s.py": b"s\n", "Thumbs.db": b"thumb", "crlf.txt": b"a\r\nb\r\n", "latin.txt": b"caf\xe9\n",
             "deep/er/still.md": b"# still\n", "x.egg-info/PKG": b"p\n"}
    for p, b in files.items():
        (t / p).parent.mkdir(parents=True, exist_ok=True)
        (t / p).write_bytes(b)
    os.symlink(t / "a.py", t / "link.py")
    os.symlink(t / "pkg", t / "linkdir")
    os.symlink(t / "gone", t / "dangling")
    os.symlink(tmp_path / "outside.md", t / "out.md")
    (tmp_path / "outside.md").write_text("secret outside\n")
    return t


# ---------------------------------------------------------------------------
# folder.py: the rule, the digest, the fields
# ---------------------------------------------------------------------------

def test_the_suite_folder_digest_is_the_reference_digest():
    assert reference_tree(LITTLE)["tree"] == LITTLE_TREE
    d = F.tree_digest(LITTLE)
    assert {k: d[k] for k in ("files", "bytes", "skipped", "tree")} == {"files": 6, "bytes": 616, "skipped": 1,
                                                                        "tree": LITTLE_TREE}
    f = F.read(LITTLE, path="inputs/little-tool")
    assert f.tree == LITTLE_TREE and f.files == 7 and f.bytes == 640 and f.lines == 26 and f.skipped == 1
    assert [e.path for e in f.entries] == ["LICENSE", "README.md", "docs/guide.md", "docs/logo.png",
                                           "little/__init__.py", "little/cli.py", "little/count.py"]
    assert [e.path for e in f.entries if e.binary] == ["docs/logo.png"]
    assert f.name == "little-tool" and f.commit is None and f.origin is None


def test_the_digest_matches_the_reference_where_the_two_rules_differ(tricky):
    ref = reference_tree(tricky)
    mine = F.tree_digest(tricky)
    assert {k: mine[k] for k in ref} == ref
    assert F.read(tricky).tree == ref["tree"] and F.read(tricky).skipped == ref["skipped"]


def test_the_folder_rule_skips_dot_parts_pycache_node_modules_and_links(tricky):
    f = F.read(tricky)
    paths = [e.path for e in f.entries]
    assert paths == sorted(paths, key=lambda p: p.encode("utf-8"))
    for gone in (".github/ci.yml", ".env", "pkg/__pycache__/m.pyc", "node_modules/q.js", "link.py", "linkdir/m.py",
                 "dangling", "out.md"):
        assert gone not in paths, gone
    for kept in ("a.py", "build/out.py", "venv/lib.py", "env2/s.py", "x.fabulac.cosm", "deep/er/still.md",
                 "x.egg-info/PKG", "Thumbs.db"):
        assert kept in paths, kept                    # Thym's rule keeps what MacroCOSM's digest leaves out
    assert f.links == 4                               # every link is left out, and counted
    by = {e.path: e for e in f.entries}
    assert by["late-nul.txt"].binary and by["late-nul.txt"].tree       # a zero byte past 8 KiB: binary, in the digest
    assert by["big.txt"].binary and not by["big.txt"].tree
    assert by["latin.txt"].binary and not by["latin.txt"].tree
    assert not by["bom.md"].binary and by["bom.md"].tree               # a byte-order mark is tolerated
    assert not by["x.fabulac.cosm"].binary and not by["x.fabulac.cosm"].tree
    assert not by["build/out.py"].tree and not by["Thumbs.db"].tree
    assert f.text("crlf.txt") == "a\r\nb\r\n" and F.lines_in(f.text("crlf.txt")) == 2


def test_no_link_is_followed_not_even_the_root(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "a.md").write_text("a\n")
    os.symlink(tmp_path / "real", tmp_path / "via")
    with pytest.raises(F.FolderError, match="symbolic link"):
        F.read(tmp_path / "via")
    with pytest.raises(F.FolderError, match="not a folder"):
        F.read(tmp_path / "real" / "a.md")


def test_member_fields_filter_and_folders_below():
    f = F.read(LITTLE, path="inputs/little-tool")
    by = {e.path: f.member_fields(e) for e in f.entries}
    assert by["little/cli.py"] == {"path": "little/cli.py", "name": "cli.py", "suffix": "py", "depth": 1,
                                   "size": 205, "sha256": by["little/cli.py"]["sha256"], "binary": False, "lines": 10}
    assert by["LICENSE"]["suffix"] == "" and by["docs/logo.png"]["lines"] is None
    py = f.where(lambda e: e.suffix == "py")
    assert [e.path for e in py.entries] == ["little/__init__.py", "little/cli.py", "little/count.py"]
    assert py.tree == F.digest_of((e.path, e.sha256) for e in py.entries) and py.tree != f.tree
    assert py.lines == 17 and py.files == 3 and py.path == f.path
    assert [e.path for e in f.where(lambda e: e.binary).entries] == ["docs/logo.png"]
    subs = f.folders()
    assert [s.path for s in subs] == ["inputs/little-tool/docs", "inputs/little-tool/little"]
    assert [e.path for e in subs[1].entries] == ["__init__.py", "cli.py", "count.py"]
    assert subs[1].tree == F.tree_digest(LITTLE / "little")["tree"]       # a folder below: its own digest


def test_commit_and_origin_are_read_from_the_clone_files(tmp_path):
    root = tmp_path / "clone"
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / "a.py").write_text("a\n")
    sha = "4b1f0c2" + "0" * 33
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / ".git" / "config").write_text('[core]\n\tbare = false\n[remote "origin"]\n\turl = https://example.org/t\n')
    (root / ".git" / "packed-refs").write_text(f"# pack-refs\n{sha} refs/heads/main\n")
    f = F.read(root)
    assert (f.commit, f.origin) == (sha, "https://example.org/t")
    assert [e.path for e in f.entries] == ["a.py"]
    (root / ".git" / "refs" / "heads" / "main").write_text("a" * 40 + "\n")
    assert F.read(root).commit == "a" * 40


# ---------------------------------------------------------------------------
# The snapshot: its format, its fidelity, its cost
# ---------------------------------------------------------------------------

TEXTS = ["a\n", "a", "a\n\n\n", "\n\nlead\n", "  indented first\nnext\n", "\ttab\n", "# hash\n---\n...\n", "x: y\n- z",
         "trail  \n  \n", "﻿bom\n", "cr\r\nlf\n", "nel\x85x\n", "ls x\n", "ctl\x01\n", "\n", "\n\n", " ", "",
         'quote " and \\ back\n', "emoji \U0001F600\n", "|\n>\n", "    \n\n  x", "%YAML\n", " nbsp\n", "del\x7f\n"]


def test_a_snapshot_holds_every_text_exactly_and_reads_back():
    entries, texts = [], {}
    for i, t in enumerate(TEXTS):
        b = t.encode("utf-8")
        entries.append(F.Entry(f"f{i:02}.txt", hashlib.sha256(b).hexdigest(), len(b)))
        texts[f"f{i:02}.txt"] = t
    entries.append(F.Entry("logo.png", "ab" * 32, 3, binary=True, tree=False))
    entries.append(F.Entry("a.fabulac.cosm", hashlib.sha256(b"x\n").hexdigest(), 2, tree=False))
    texts["a.fabulac.cosm"] = "x\n"
    entries.sort(key=lambda e: F.path_key(e.path))
    f = F.Folder("odd/", tuple(entries), F.digest_of((e.path, e.sha256) for e in entries if e.tree), _texts=texts)
    text = F.snapshot_text(f, id="thym/2026-11-05-1530-a1b2.repo")
    assert text.startswith("oes: thym/1\nkind: folder\nid: ")
    assert "binary: true}" in text and "digested: false}" in text
    g = F.from_snapshot(mc.yaml_load(text))
    assert g.tree == f.tree and g.entries == f.entries and g.root is None
    assert all(g.text(e.path) == f.text(e.path) for e in f.texts())


def test_a_snapshot_that_does_not_match_its_digests_is_refused():
    f = F.read(LITTLE, path="inputs/little-tool")
    data = mc.yaml_load(F.snapshot_text(f, id="thym/x.repo"))
    data["texts"][0]["text"] += "tampered\n"
    with pytest.raises(F.FolderError, match="does not match its digest"):
        F.from_snapshot(data)
    data = mc.yaml_load(F.snapshot_text(f, id="thym/x.repo"))
    del data["texts"][1]
    with pytest.raises(F.FolderError, match="holds no text for"):
        F.from_snapshot(data)


def test_the_snapshot_costs_the_text_once_and_a_row_per_file():
    f = F.read(LITTLE, path="inputs/little-tool")
    size = len(F.snapshot_text(f, id="thym/2026-11-01-1200-abcd.repo").encode("utf-8"))
    text = sum(e.size for e in f.texts())
    assert text == 616 and size < text + 7 * 130 + 26 * 6 + 400          # rows, indentation, catalog
    assert size == 1963


# ---------------------------------------------------------------------------
# Types: folder, line, change; what fits where; their values
# ---------------------------------------------------------------------------

def test_line_fits_string_and_folder_walks_as_text():
    assert ty.accepts(["string"], "line") and not ty.accepts(["line"], "string")
    assert ty.accepts(["list of string"], "list of line")
    assert ty.member("folder") == "text" and ty.member("short") == "string" and ty.member("number") is None
    assert ty.show(["folder"]) == "a folder" and ty.parse_type("list of change") == "list of change"


def test_line_and_change_values():
    l = V.make_line("## 3.2 The rule", 7, "ab" * 32)
    assert (l.type, l.plain(), l.field("number"), l.field("level"), l.field("title"), l.field("blank")) == \
        ("line", "## 3.2 The rule", 7, 2, "The rule", False)
    assert l.sha256 == hashlib.sha256(b"## 3.2 The rule").hexdigest() and l.field("source") == "ab" * 32
    assert V.make_line("plain", 1, "x").field("title") is None and V.make_line("", 2, "x").field("blank") is True
    c = V.make_change(3, "aa", "bb", "drop")
    assert c.type == "change" and c.field("do") == "drop" and c.field("lines") == []
    with pytest.raises(ValueError):
        V.make_change(3, "aa", "bb", "rename")


def test_folder_values_members_and_provenance():
    v = V.load_input({"name": "repo", "type": "folder", "path": "inputs/little-tool", "sha256": LITTLE_TREE}, SUITE)
    assert v.type == "folder" and v.sha256 == LITTLE_TREE and v.field("lines") == 26 and v.field("files") == 7
    rows = V.members(v)
    assert [r.field("path") for r in rows] == ["LICENSE", "README.md", "docs/guide.md", "little/__init__.py",
                                               "little/cli.py", "little/count.py"]           # no binary file walked
    cli = rows[4]
    assert cli.type == "text" and cli.field("suffix") == "py" and cli.field("lines") == 10
    assert cli.made == {"move": "none", "source": {"folder": LITTLE_TREE, "path": "little/cli.py"}}
    assert cli.sha256 == cli.field("sha256")
    assert V.guess_type(LITTLE) == "folder" and V.digest_path(LITTLE, "folder") == LITTLE_TREE
    assert V.digest_path(LITTLE) is None                       # a folder with no catalog is no volume


def test_a_changed_folder_is_refused_at_plan_time(tmp_path):
    repo = tmp_path / "tool"
    shutil.copytree(LITTLE, repo)
    spec = {"name": "repo", "type": "folder", "path": "tool/", "sha256": LITTLE_TREE}
    assert V.load_input(spec, tmp_path).sha256 == LITTLE_TREE
    (repo / "little" / "cli.py").write_text("changed\n")
    r = V.load_input(spec, tmp_path)
    assert isinstance(r, Refusal) and (r.stage, r.check) == ("plan", "input")
    assert r.message.startswith("repo changed since it was planned: tool/ has tree ")
    assert r.message.endswith(f"the plan recorded {LITTLE_TREE[:4]}…; plan it again")
    shutil.rmtree(repo)
    assert "is not there" in V.load_input(spec, tmp_path).message


# ---------------------------------------------------------------------------
# The checker: folders, several outputs, in with a text, the loop's where; their thym 0 refusals
# ---------------------------------------------------------------------------

def folder_prog(version: int, body: str, gives: str = "n: number", takes: str = "repo: folder") -> str:
    return f"thym {version}\n\nprogram p\n  takes {takes}\n  gives {gives}\n\n{body}end\n"


def test_folders_type_check():
    ok(folder_prog(1, "  let code = repo where suffix is py\n  assert code.lines < 6001\n"
                      "  for each t in code where depth is 0\n    assert words t > 0\n  end\n  give code.files\n"))
    r = refused(folder_prog(1, "  give repo.colour\n"))
    assert (r.check, r.line) == ("type", 7) and "a folder has no field colour" in r.message
    r = refused(folder_prog(1, "  for each t in repo.name\n    assert words t > 0\n  end\n  give 0\n"))
    assert r.check == "type" and r.message == ("for each goes through a volume, a fabula, a folder, a short or a "
                                               "list; repo.name is a string")
    r = refused(folder_prog(1, "  give repo where suffix is py\n"))
    assert r.check == "type" and "is a folder" in r.message


def test_several_outputs_each_once_on_every_path():
    two = "code: folder, size: number"
    ok(folder_prog(1, "  give code: repo\n  give size: repo.files\n", gives=two))
    ok(folder_prog(1, "  give size: repo.lines\n  if repo.files > 3 then\n    give code: repo\n  else\n"
                      "    give code: repo where binary\n  end\n", gives=two))
    r = refused(folder_prog(1, "  give code: repo\n", gives=two))
    assert (r.check, r.line, r.message) == ("no-give", 3, "program p gives code and size; the path through line 7 "
                                                          "never gives size")
    r = refused(folder_prog(1, "  give code: repo\n  give size: repo.files\n  give manuel: 0\n", gives=two))
    assert (r.check, r.line) == ("type", 9)
    assert r.message == "give manuel: … names no output of p; it gives code and size"
    r = refused(folder_prog(1, "  give repo\n", gives=two))
    assert r.check == "type" and r.message == "program p gives code and size; a give says which: give code: …"
    r = refused(folder_prog(1, "  give code: repo\n  give size: 1\n  give size: 2\n", gives=two))
    assert (r.check, r.line) == ("type", 9) and "gives size a second time" in r.message
    r = refused(folder_prog(1, "  give size: 1\n", gives="size: number, size: folder"))
    assert r.check == "rebound"
    r = refused(folder_prog(1, "  give code: repo\n  give size: repo\n", gives=two))
    assert r.check == "type" and "program p gives size: number, and repo is a folder" in r.message
    ok(folder_prog(1, "  give n: 3\n"))                       # one output may be labelled or not


def test_in_finds_a_string_in_a_text():
    ok(folder_prog(1, '  for each t in repo where "def" in t\n    assert words t > 0\n  end\n'
                      '  give 0\n'))
    r = refused(folder_prog(1, "  for each t in repo where 3 in t\n    assert words t > 0\n  end\n  give 0\n"))
    assert r.check == "type" and "finds a string in it; 3 is a number" in r.message
    r = refused('thym 0\n\nprogram p\n  takes t: text\n  gives n: number\n\n  assert "TODO" in t\n  give 0\nend\n')
    assert (r.check, r.line) == ("version", 7) and "in with a text on its right at line 7" in r.message


def test_the_thym_1_constructs_of_part_b_under_thym_0_need_thym_1():
    cases = {
        "the type folder": ("  takes r: folder\n  gives n: number\n\n  give 0\n", 4),
        "the type line": ("  takes r: line\n  gives n: number\n\n  give 0\n", 4),
        "the type change": ("  takes r: list of change\n  gives n: number\n\n  give 0\n", 4),
        "a program that gives several outputs": ("  takes t: text\n  gives a: number, b: number\n\n  give a: 0\n"
                                                 "  give b: 1\n", 5),
        "a labelled give (give a: …)": ("  takes t: text\n  gives a: number\n\n  give a: 0\n", 7),
    }
    for phrase, (body, line) in cases.items():
        r = refused(f"thym 0\n\nprogram p\n{body}end\n")
        assert (r.check, r.line) == ("version", line), (phrase, r)
        assert r.message == f"this needs `thym 1`: {phrase} at line {line}; the first line says thym 0"


def test_a_where_after_a_call_in_a_loop_header_belongs_to_the_loop():
    one = ("  for each o in fabula of p where kind is claim\n    emit o marked stated\n  end\n"
           "  give project h as isotype\n")
    head = "  takes p: package, h: volume\n  gives i: volume\n\n"
    m = ps.parse(f"thym 1\n\nprogram q\n{head}{one}end\n")
    loop = m.blocks[0].stmts[0]
    assert isinstance(loop.coll, ps.Call) and loop.coll.mod("where") is None and loop.where is not None
    assert any("a for each whose collection is a call followed by where" in f for _, f in m.features)
    checked = ck.check(m)
    assert not isinstance(checked, Refusal), checked
    r = refused(f"thym 0\n\nprogram q\n{head}{one}end\n")
    assert (r.check, r.line) == ("version", 7)
    assert "a for each whose collection is a call followed by where at line 7" in r.message
    nodes = pl.build(checked)
    assert nodes[1].name == "emit mark o as stated, for each o in t1 where kind is claim"
    st = RUN.read_statement(nodes[1].name, {"fabula", "mark", "project"})
    assert st.loop.coll == RUN.Name("t1") and st.loop.cond is not None
    wrapped = ps.parse(f"thym 1\n\nprogram q\n{head}"
                       "  for each o in (fabula of p where kind is claim)\n    emit o marked stated\n  end\n"
                       "  give project h as isotype\nend\n")
    assert wrapped.blocks[0].stmts[0].where is None                       # inside parentheses the where is the call's


# ---------------------------------------------------------------------------
# Declaration keys that choose by the call (3.1; THYM 17.6)
# ---------------------------------------------------------------------------

SIDECAR = """moves-of: testing/1
moves:
  - {name: tell-two, takes: [fabula], gives: short, modifiers: {as: order}, asks: true, contract: [coverage],
     scaffold: outline,
     thym-1: {modifiers: {as: 'order | code'}, gives-when: [{as: code, gives: folder}],
              contract-when: [{as: code, contract: [parses, provenance]}], scaffold-when: [{as: code, scaffold: none}]}}
  - {name: gather-two, takes: ['list of item'], gives: same-as-with, modifiers: {with: 'fabula | volume'}, since: 1}
  - {name: count-two, takes: ['volume | list'], gives: number, thym-1: {takes: ['volume | list | folder']},
     gives-when: [{takes: folder, gives: 'list of word'}]}
  - {name: shout, takes: [string], gives: string, since: 1}
"""


@pytest.fixture
def scratch_decls(tmp_path):
    reg = mc.default_registry()
    (tmp_path / "testing.moves.cosm").write_text(SIDECAR, encoding="utf-8")
    decls = dc.load(mc.Registry([*reg.dirs, tmp_path]))
    assert [p for p in decls.problems if "which the registry does not know" not in p] == [], decls.problems
    return decls


def test_the_when_keys_are_read_into_the_views(scratch_decls):
    t = scratch_decls["tell-two"]
    assert t.gives_when == () and t.view(1).gives_when == (("as", ("code",), ("folder",)),)
    assert dc.chosen(t.view(1), as_word="code") == {"gives": ("folder",), "contract": ("parses", "provenance"),
                                                    "scaffold": "none"}
    assert dc.chosen(t.view(1), as_word="told") == {"gives": ("short",), "contract": ("coverage",),
                                                    "scaffold": "outline"}
    assert dc.chosen(t.view(0), as_word="code")["gives"] == ("short",)
    assert dc.chosen(scratch_decls["gather-two"], with_type="volume")["gives"] == ("volume",)
    bad = []
    assert dc._decl("t", {"name": "x", "takes": [], "gives": "short", "gives-when": [{"as": "code"}]}, "t.cosm",
                    bad) is None and "gives-when must be a list" in bad[0]


def test_a_call_is_typed_and_contracted_from_its_declaration(scratch_decls):
    text = ("thym 1\n\nprogram p\n  takes f: fabula\n  gives code: folder, manual: short\n\n"
            "  give code: tell-two f as code\n  give manual: tell-two f as told\nend\n")
    checked = ok(text, decls=scratch_decls)
    items = en.enumerate_checked(checked)
    contracts = {it["of"]: it["checks"] for it in items["nodes"] if it.get("type") == "contract"}
    assert contracts == {"P:step/p.1": ["parses", "provenance"], "P:step/p.2": ["coverage"]}
    r = refused(text.replace("gives code: folder", "gives code: short"), decls=scratch_decls)
    assert r.check == "type" and "tell-two f as code is a folder" in r.message
    r = refused("thym 0\n\nprogram p\n  takes f: fabula\n  gives n: number\n\n  let c = tell-two f as code\n"
                "  give 0\nend\n", decls=scratch_decls)
    assert r.check == "version" and "the word code after as of tell-two, which thym 1 adds" in r.message
    ok("thym 1\n\nprogram p\n  takes xs: list of item, v: volume\n  gives out: volume\n\n"
       "  give gather-two xs with v\nend\n", decls=scratch_decls)
    ok("thym 1\n\nprogram p\n  takes repo: folder\n  gives n: list of word\n\n  give count-two repo\nend\n",
       decls=scratch_decls)


def test_a_line_fits_where_a_string_is_taken(scratch_decls):
    ok("thym 1\n\nprogram p\n  takes l: line\n  gives s: string\n\n  give shout l\nend\n", decls=scratch_decls)
    r = refused("thym 1\n\nprogram p\n  takes l: change\n  gives s: string\n\n  give shout l\nend\n",
                decls=scratch_decls)
    assert r.check == "type"


# ---------------------------------------------------------------------------
# Enumeration and plans
# ---------------------------------------------------------------------------

def test_several_outputs_enumerate_and_plan(tmp_path):
    items = en.enumerate_file(SUITE / "programs" / "split-a-folder.thym")
    prog = next(it for it in items["nodes"] if it["type"] == "program")
    assert prog["gives"] == [{"name": "code", "type": "folder"}, {"name": "prose", "type": "folder"},
                             {"name": "size", "type": "number"}]
    assert [it.get("slot") for it in items["nodes"] if it.get("form") == "give"] == ["code", "prose", "size"]
    plan = mc.yaml_load(mc.read_text(SUITE / "expected" / "split-a-folder" / "plan.cosm"))
    assert plan["inputs"] == [{"name": "repo", "type": "folder", "path": "inputs/little-tool", "sha256": LITTLE_TREE,
                               "files": 7, "bytes": 640}]
    assert [n.get("gives") for n in plan["nodes"] if n.get("move") == "give"] == ["code", "prose", "size"]


def test_a_folder_input_row_is_filled_from_the_folder(tmp_path):
    checked = ok((SUITE / "programs" / "keep-the-python.thym").read_text(),
                 path=str(SUITE / "programs" / "keep-the-python.thym"))
    p = pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(LITTLE), "sha256": ""}])
    assert p["inputs"][0]["sha256"] == LITTLE_TREE and (p["inputs"][0]["files"], p["inputs"][0]["bytes"]) == (7, 640)


# ---------------------------------------------------------------------------
# The runtime: walking, snapshots and replay, landing several outputs and folders
# ---------------------------------------------------------------------------

def plan_and_run(tmp_path, name: str, *, folder: Path | None = None, **kw):
    src = SUITE / "programs" / f"{name}.thym"
    repo = tmp_path / "work" / "tool"
    shutil.copytree(folder or LITTLE, repo)
    checked = ok(src.read_text(), path=str(src))
    plan = pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(repo)}])
    assert not isinstance(plan, Refusal), plan
    t = RUN.run(plan, inputs_root=tmp_path / "work", root=tmp_path / "root", program=src, **kw)
    return t, repo, plan


def test_a_folder_output_lands_as_a_directory_with_its_digest_in_the_trace(tmp_path):
    t, repo, _ = plan_and_run(tmp_path, "keep-the-python")
    assert not isinstance(t, Refusal) and t.landed, getattr(t, "refusal", t)
    out = t.dir / "outputs" / "code"
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == \
        ["little/__init__.py", "little/cli.py", "little/count.py"]
    tv = mc.yaml_load(mc.read_text(t.path))
    rows = [r for rec in tv["nodes"] if rec.get("type") == "record" for r in rec.get("outputs") or []
            if r.get("name") == "code"]
    py = F.read(repo).where(lambda e: e.suffix == "py")
    assert rows == [{"name": "code", "sha256": py.tree, "path": "outputs/code/"}]
    snap = t.dir / "inputs" / "repo.folder.cosm"
    assert snap.is_file() and mc.yaml_load(snap.read_text())["tree"] == LITTLE_TREE


def test_several_outputs_land_together(tmp_path):
    t, _, _ = plan_and_run(tmp_path, "split-a-folder")
    assert t.landed, t.refusal
    got = sorted(p.relative_to(t.dir / "outputs").as_posix() for p in (t.dir / "outputs").rglob("*") if p.is_file())
    assert got == ["code/little/__init__.py", "code/little/cli.py", "code/little/count.py", "prose/README.md",
                   "prose/docs/guide.md", "size.txt"]
    assert (t.dir / "outputs" / "size.txt").read_text() == "17"


def test_several_outputs_land_all_or_none(tmp_path, monkeypatch):
    src = SUITE / "programs" / "split-a-folder.thym"
    checked = ok(src.read_text(), path=str(src))
    plan = pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(LITTLE)}])
    plan["nodes"] = [n for n in plan["nodes"] if n.get("gives") != "size"]        # no node gives size now
    plan["nodes"][0]["nodes"] = [n["id"] for n in plan["nodes"][1:]]
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=src)
    assert not t.landed and (t.refusal.check, t.refusal.message) == (
        "no-give", "program split-a-folder gives size, and no give reached it; nothing landed")
    assert not (t.dir / "outputs").exists() and not (t.dir / "stage").exists()

    def broken(folder, dest):
        raise F.FolderError("the disk is full")
    monkeypatch.setattr(F, "write_tree", broken)
    t = RUN.run(pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(LITTLE)}]), inputs_root=SUITE,
                root=tmp_path / "root2", program=src)
    assert not t.landed and t.refusal.check == "output" and "nothing landed" in t.refusal.message
    assert not (t.dir / "outputs").exists() and not (t.dir / "stage").exists()


def test_a_replay_reads_the_folder_from_its_snapshot_with_the_folder_deleted(tmp_path):
    t, repo, _ = plan_and_run(tmp_path, "split-a-folder")
    assert t.landed, t.refusal
    shutil.rmtree(repo)
    again = RUN.replay(t.dir, root=tmp_path / "root")
    assert not isinstance(again, Refusal), again
    assert again.landed and again.replay == {"of": t.run_id, "identical": True, "differences": []}
    assert (again.dir / "inputs" / "repo.folder.cosm").read_bytes() != b""          # a replay snapshots it too
    (t.dir / "inputs" / "repo.folder.cosm").unlink()
    r = RUN.replay(t.dir, root=tmp_path / "root")
    assert isinstance(r, Refusal) and r.check == "input" and "kept no snapshot" in r.message


def test_a_replay_refuses_a_tampered_snapshot(tmp_path):
    t, repo, _ = plan_and_run(tmp_path, "keep-the-python")
    snap = t.dir / "inputs" / "repo.folder.cosm"
    snap.write_text(snap.read_text().replace("Counting words.", "Counting words!"))
    r = RUN.replay(t.dir, root=tmp_path / "root")
    assert isinstance(r, Refusal) and r.check == "input" and "does not match its digest" in r.message


def test_a_pass_over_a_folder_is_named_by_the_file_path(tmp_path):
    src = tmp_path / "p.thym"
    src.write_text("thym 1\n\nprogram p\n  takes repo: folder\n  gives n: number\n\n"
                   "  for each t in repo where suffix is py\n    assert words t > 50\n  end\n  give repo.files\nend\n")
    checked = ok(src.read_text(), path=str(src))
    plan = pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(LITTLE)}])
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=src)
    assert not t.landed
    assert t.refusal.message.startswith("assert words t > 50 (line 8, for t = little/__init__.py): ")


def test_count_of_a_folder_counts_its_text_files_where_the_declaration_allows_it(tmp_path):
    decls = dc.load()
    base = decls["count"]
    import dataclasses
    decls["count"] = dataclasses.replace(base, thym1={"takes": ((*base.takes[0], "folder"),)})
    src = tmp_path / "p.thym"
    src.write_text("thym 1\n\nprogram p\n  takes repo: folder\n  gives n: number\n\n  give count repo\nend\n")
    checked = ok(src.read_text(), path=str(src), decls=decls)
    plan = pl.plan(checked, [{"name": "repo", "type": "folder", "path": str(LITTLE)}])
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=src, decls=decls)
    assert t.landed, t.refusal
    assert (t.dir / "outputs" / "n.txt").read_text() == "6"
    m = ps.parse(src.read_text())
    assert ("count repo (a folder), which thym 1 allows" in [f for _, f in ck.check(m, decls=decls).module.features])
    # the shipped count's thym 1 view now takes a folder (6.3: "count adds folder"); a thym 0 program has no folder
    shipped = ok(src.read_text(), path=str(src))
    assert ("count repo (a folder), which thym 1 allows" in [f for _, f in shipped.module.features])
    r = refused(src.read_text().replace("thym 1", "thym 0", 1))
    assert r.check == "version" and "this needs `thym 1`" in r.message


def test_a_loop_over_a_call_with_its_own_where_runs(tmp_path):
    src = tmp_path / "q.thym"
    src.write_text("thym 1\n\nprogram q\n  takes p: package\n  gives n: number\n\n"
                   "  for each o in fabula of p where kind is claim\n    assert o has id\n  end\n  give 0\nend\n")
    checked = ok(src.read_text(), path=str(src))
    pkg = SUITE / "inputs" / "orchard-notes.thym"
    plan = pl.plan(checked, [{"name": "p", "type": "package", "path": str(pkg), "sha256": V.digest_path(pkg)}])
    assert [n["name"] for n in plan["nodes"][1:3]] == ["fabula of p", "assert o has id, for each o in t1 where kind "
                                                                       "is claim"]
    t = RUN.run(plan, inputs_root=SUITE, root=tmp_path / "root", program=src)
    assert t.landed, t.refusal
    rec = next(r for r in t.records if r["name"].startswith("assert"))
    assert rec["checks"] and all(c["ok"] for c in rec["checks"])
