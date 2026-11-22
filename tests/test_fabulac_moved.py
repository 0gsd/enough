"""The moved-parts rule (`enough/fabulac_moved.py`, `python -m enough.fabulac moved-parts`; 0.9 pins section 6).

A small program in a git repository of its own, told as two parts under a head; the tree is read on disk and at refs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from enough import fabulac_cli as cli
from enough import fabulac_moved as M
from enough import macrocosm as mc

A = '''"""Part a."""


def count(text):
    return len(text.split())


class Counter:
    def add(self, n):
        return n + 1


LIMIT = 10
'''
B = '''"""Part b."""
from pkg.a import count


def report(text):
    return f"{count(text)} words"
'''
INIT = '"""The package."""\n'


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _file(path: str, root: Path) -> dict:
    return {"id": "C:file/" + path.replace("/", "--").replace(".", "-"), "type": "file", "path": path,
            "sha256": _sha(root / path)}


def _ruled(item: dict) -> dict:
    return {**item, "ruling": [{"is": "kept", "by": "R:maker/transconceiver", "on": "2026-11-22", "said": "x"}]}


def _part(name: str, files: list[str], root: Path, items: list[dict], head: str | None = "oes:fabula/demo") -> dict:
    nodes = [_file(f, root) for f in files] + items
    read = [(f, _sha(root / f)) for f in files]
    doc = {"oes": "fabula/1", "flavour": "fabulac", "id": f"fabula/{name}", "name": name,
           "source": {"path": f"{name}/", "kind": "folder", "language": "python", "tree": M.tree_of(read)},
           "nodes": nodes}
    if head:
        doc["head"] = head
    return doc


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text(INIT)
    (root / "pkg" / "a.py").write_text(A)
    (root / "pkg" / "b.py").write_text(B)
    (root / "README.md").write_text("demo\n")
    _git(root, "init", "-q")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one")
    _git(root, "tag", "v1")
    return root


def _set(repo: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    a_items = [
        _ruled({"id": "C:interface/pkg.a.count", "type": "interface", "name": "count", "surface": "function",
                "span": {"file": "pkg/a.py", "lines": "4-5"}}),
        _ruled({"id": "C:interface/pkg.a.Counter.add", "type": "interface", "name": "Counter.add",
                "surface": "method", "span": {"file": "pkg/a.py", "lines": "9-10"}}),
        _ruled({"id": "C:behaviour/pkg.a.count.doc", "type": "behaviour", "of": ["C:interface/pkg.a.count"],
                "span": {"file": "pkg/a.py", "lines": "4-5"}}),
        _ruled({"id": "C:setting/pkg.a.LIMIT", "type": "setting", "span": {"file": "pkg/a.py", "lines": "13"}}),
        _ruled({"id": "C:setting/env.DEMO", "type": "setting", "span": {"file": "pkg/a.py", "lines": "2-3"}}),
        _ruled({"id": "C:reliance/split", "type": "reliance", "of": "R:means/python",
                "used-by": ["C:interface/pkg.a.count"], "span": {"file": "pkg/a.py", "lines": "5"}}),
        {"id": "D:question/count", "type": "question", "about": "C:interface/pkg.a.count", "state": "open"},
        {"id": "D:question/whole", "type": "question", "about": "I", "state": "open"},
        {"id": "N:aim/small", "type": "aim"},
    ]
    b_items = [
        _ruled({"id": "C:interface/pkg.b.report", "type": "interface", "name": "report", "surface": "function",
                "span": {"file": "pkg/b.py", "lines": "5-6"}}),
        {"id": "D:question/report", "type": "question", "about": "C:interface/pkg.b.report#signature",
         "state": "answered"},
    ]
    pa = _part("demo-a", ["pkg/__init__.py", "pkg/a.py"], repo, a_items)
    pb = _part("demo-b", ["pkg/b.py"], repo, b_items)
    for name, doc in (("demo-a", pa), ("demo-b", pb)):
        (out / f"{name}.fabulac.cosm").write_text(mc.dump(doc), encoding="utf-8")
    head = {"oes": "fabula/1", "flavour": "fabulac", "id": "fabula/demo", "name": "demo",
            "parts": [{"uri": f"oes:fabula/{n}", "path": f"{n}.fabulac.cosm",
                       "sha256": _sha(out / f"{n}.fabulac.cosm")} for n in ("demo-a", "demo-b")],
            "nodes": [_ruled({"id": "C:interface/pkg.a.count", "type": "interface", "name": "count"}),
                      _ruled({"id": "C:structure/pkg.a.Counter", "type": "structure"}),
                      {"id": "D:question/count", "type": "question", "about": "C:interface/pkg.a.count",
                       "state": "answered"}]}
    (out / "demo.fabulac.cosm").write_text(mc.dump(head), encoding="utf-8")
    return out


def _row(rep: dict, name: str) -> dict:
    return next(r for r in rep["parts"] + rep["heads"] if r["uri"] == f"oes:fabula/{name}")


def test_unmoved_on_disk_and_at_the_ref(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    for ref in (None, "v1"):
        rep = M.moved_parts([fabs], repo, ref=ref)
        assert rep["moved"] == []
        assert {r["state"] for r in rep["parts"] + rep["heads"]} == {"unmoved"}
        a = _row(rep, "demo-a")
        assert a["tree"]["consistent"] and a["tree"]["now"] == a["tree"]["recorded"]
        assert a["rulings"] == {"total": 6, "resolve": 6, "gone": []}
        assert a["questions"]["total"] == 2
        assert _row(rep, "demo")["parts"][0]["fabulac"] == "in-step"
    assert "Nothing moved." in M.table(rep)


def test_one_file_touched_moves_that_part_and_its_head_only(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "b.py").write_text(B + "\n# touched\n")
    rep = M.moved_parts([fabs], repo)
    assert rep["moved"] == ["oes:fabula/demo", "oes:fabula/demo-b"]
    b = _row(rep, "demo-b")
    assert b["files"]["changed"] == ["pkg/b.py"] and b["files"]["vanished"] == []
    assert b["rulings"]["resolve"] == 1 and b["questions"]["resolve"] == 1
    assert _row(rep, "demo-a")["state"] == "unmoved"
    assert b["tree"]["now"] != b["tree"]["recorded"]


def test_a_definition_gone_does_not_resolve(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "a.py").write_text(A.replace("def count(text):\n    return len(text.split())\n", "")
                                       .replace("    def add(self, n):", "    def plus(self, n):"))
    rep = M.moved_parts([fabs], repo)
    a = _row(rep, "demo-a")
    assert a["state"] == "moved" and a["files"]["changed"] == ["pkg/a.py"]
    gone = set(a["rulings"]["gone"])
    # count is gone, so its behaviour and the reliance it alone used go too; Counter.add is gone; LIMIT is there;
    # env.DEMO names no definition and its lines are still within the file.
    assert gone == {"C:interface/pkg.a.count", "C:interface/pkg.a.Counter.add", "C:behaviour/pkg.a.count.doc",
                    "C:reliance/split"}
    assert a["rulings"]["resolve"] == 2
    assert a["questions"]["gone"] == ["D:question/count"]
    h = _row(rep, "demo")
    assert h["state"] == "moved"
    assert h["rulings"]["gone"] == ["C:interface/pkg.a.count"]          # the structure Counter is still a class
    assert h["questions"]["gone"] == ["D:question/count"]
    assert "no longer resolve" in M.table(rep)


def test_vanished_and_added_files(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "b.py").unlink()
    (repo / "pkg" / "c.py").write_text("X = 1\n")
    (repo / "pkg" / "__pycache__").mkdir()
    (repo / "pkg" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\0")
    rep = M.moved_parts([fabs], repo)
    b = _row(rep, "demo-b")
    assert b["files"]["vanished"] == ["pkg/b.py"] and b["rulings"]["resolve"] == 0
    assert b["questions"]["gone"] == ["D:question/report"]
    # pkg/ is held (the set tells its __init__.py) and shared by both parts: c.py is listed once, for the set.
    assert rep["unclaimed"] == [{"folder": "pkg", "parts": ["oes:fabula/demo-a", "oes:fabula/demo-b"],
                                 "files": [{"path": "pkg/c.py", "state": "unclaimed"}]}]


def test_base_tells_added_from_untold(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "old.py").write_text("Y = 2\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "old")
    _git(repo, "tag", "v1b")
    (repo / "pkg" / "new.py").write_text("Z = 3\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "new")
    _git(repo, "tag", "v2")
    rep = M.moved_parts([fabs], repo, ref="v2", base="v1b")
    files = {r["path"]: r["state"] for u in rep["unclaimed"] for r in u["files"]}
    assert files == {"pkg/new.py": "added", "pkg/old.py": "untold"}
    # an added file in a folder the parts share moves the head, not a part
    assert rep["moved"] == ["oes:fabula/demo"]
    assert _row(rep, "demo")["added"] == ["pkg/new.py"]


def test_a_part_alone_in_its_folder_owns_what_is_added(repo, tmp_path):
    fabs = tmp_path / "solo"
    fabs.mkdir()
    doc = _part("solo", ["pkg/__init__.py", "pkg/a.py", "pkg/b.py"], repo, [], head=None)
    (fabs / "solo.fabulac.cosm").write_text(mc.dump(doc), encoding="utf-8")
    _git(repo, "tag", "base")
    (repo / "pkg" / "c.py").write_text("X = 1\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    rep = M.moved_parts([fabs], repo, ref="HEAD", base="base")
    s = _row(rep, "solo")
    assert s["state"] == "moved" and s["added"] == ["pkg/c.py"] and s["files"]["changed"] == []
    rep = M.moved_parts([fabs], repo, ref="base")
    assert rep["moved"] == []


def test_the_ref_is_read_without_a_checkout(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "a.py").write_text("broken(\n")                   # on disk only; the ref still has it whole
    assert _row(M.moved_parts([fabs], repo, ref="v1"), "demo-a")["state"] == "unmoved"
    assert _row(M.moved_parts([fabs], repo), "demo-a")["state"] == "moved"
    assert _git(repo, "status", "--porcelain").strip() == "M pkg/a.py"


def test_a_part_fabulac_edited_since_the_head_recorded_it(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    p = fabs / "demo-b.fabulac.cosm"
    p.write_text(p.read_text() + "# edited\n")
    h = _row(M.moved_parts([fabs], repo), "demo")
    assert h["state"] == "unmoved"
    assert {r["uri"]: r["fabulac"] for r in h["parts"]}["oes:fabula/demo-b"] == "moved"


def test_a_head_without_its_parts_is_not_judged(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    rep = M.moved_parts([fabs / "demo.fabulac.cosm"], repo)
    assert _row(rep, "demo")["state"] == "not judged"
    assert "was not given" in M.table(rep)


def test_a_later_fabulac_of_the_same_id_replaces_an_earlier(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    other = tmp_path / "other"
    other.mkdir()
    (other / "demo-b.fabulac.cosm").write_text((fabs / "demo-b.fabulac.cosm").read_text())
    rep = M.moved_parts([fabs, other], repo)
    assert len(rep["parts"]) == 2 and len(rep["notes"]) == 1


def test_refusals(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    with pytest.raises(M.MovedError):
        M.moved_parts([fabs], repo, ref="no-such-ref")
    with pytest.raises(M.MovedError):
        M.moved_parts([tmp_path / "nothing"], repo)
    bad = tmp_path / "bad.fabulac.cosm"
    bad.write_text("nodes: [\n")
    with pytest.raises(M.MovedError):
        M.moved_parts([bad], repo)
    with pytest.raises(M.MovedError):
        M.moved_parts([tmp_path / "empty-dir-not-there"], repo)


def test_the_command_line(repo, tmp_path, capsys):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "b.py").write_text(B + "# touched\n")
    assert cli.main(["--json", "moved-parts", str(fabs), "--tree", str(repo)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["moved"] == ["oes:fabula/demo", "oes:fabula/demo-b"]
    assert cli.main(["moved-parts", str(fabs), "--tree", str(repo), "--ref", "v1"]) == 0
    text = capsys.readouterr().out
    assert "moved: none" in text and "demo-a" in text
    assert cli.main(["moved-parts", str(fabs), "--tree", str(repo), "--ref", "nope"]) == 2


def test_a_span_past_the_end_of_a_changed_file_does_not_resolve(repo, tmp_path):
    fabs = _set(repo, tmp_path / "fabs")
    (repo / "pkg" / "a.py").write_text(A.splitlines()[0] + "\n")
    gone = set(_row(M.moved_parts([fabs], repo), "demo-a")["rulings"]["gone"])
    assert "C:setting/env.DEMO" in gone and "C:setting/pkg.a.LIMIT" in gone


def test_the_rule_imports_nothing_it_reads():
    text = Path(M.__file__).read_text(encoding="utf-8")
    assert "importlib" not in text and "exec(" not in text and "eval(" not in text
    assert "checkout" not in [w.strip("`,.") for w in text.split() if w.startswith("git")]
