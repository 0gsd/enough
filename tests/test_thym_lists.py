"""A list as an input (THYM.md 11.1, 12.1, 12.4, 17.1, 20.3; docs/fabula-landed-T3.md): `takes xs: list of T` is
given member by member. The plan records the members (posix paths, each digest, the list's own digest over theirs in
order), sizes the list by their sum and counts them for a loop's `at_most`; the run reads each member as a single
input of type T is read, refusing in the same words with the member named `xs[n]`, holds each to its digest, and
gives the program a list in the order given; a list of folders is snapshotted folder by folder, so a recorded run
replays with no folder on disk. A `thym 0` program may declare a list input (it always could) and runs on one too.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from enough import macrocosm as mc
from enough.thym import Refusal, cli, parse, check
from enough.thym import plan as pl
from enough.thym import run as R
from enough.thym.values import digest_path, list_digest

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "tests" / "fixtures" / "thym"
INPUTS = SUITE / "inputs"
LITTLE = INPUTS / "little-tool"

JOIN = """thym 1

program join-them
  why: several shorts as one, and how many there were.

  takes xs: list of short
  gives all: short, n: number

  give all: join xs with " "
  give n: count xs
end
"""

COUNT_ZERO = """thym 0

program count-them
  why: how many words each note has, read one by one.

  takes xs: list of text
  gives n: number

  for each x in xs
    assert (words x) > 0
  end
  give count xs
end
"""

FOLDERS = """thym 1

program size-them
  why: the Python of several folders, its lines counted folder by folder.

  takes repos: list of folder
  gives sizes: short

  let counts = for each r in repos
    keep say (r where suffix is py).lines
  end
  give join counts with ", "
end
"""


def compiled(tmp_path: Path, name: str, text: str):
    src = tmp_path / name
    src.write_text(text, encoding="utf-8")
    c = check.check(parse.parse(text, path=str(src)))
    assert not isinstance(c, Refusal), c
    return src, c


def row(name: str, typ: str, *paths: Path) -> dict:
    t = "folder" if typ.endswith("folder") else None
    return {"name": name, "type": typ, "members": [{"path": str(p), "sha256": digest_path(p, t)} for p in paths]}


def landed(t) -> dict:
    assert not isinstance(t, Refusal), t
    assert t.landed, t.refusal
    return {k: Path(v).read_text(encoding="utf-8") for k, v in t.outputs.items()}


def test_the_plan_records_each_member_and_the_list_digest(tmp_path: Path):
    src, c = compiled(tmp_path, "join.thym", JOIN)
    p = pl.plan(c, [row("xs", "list of short", INPUTS / "notes.md", INPUTS / "draft.md")])
    (r,) = p["inputs"]
    shas = [digest_path(INPUTS / "notes.md"), digest_path(INPUTS / "draft.md")]
    assert r == {"name": "xs", "type": "list of short", "path": (INPUTS / "notes.md").as_posix(),
                 "sha256": list_digest(shas),
                 "members": [{"path": (INPUTS / f).as_posix(), "sha256": s} for f, s in zip(("notes.md", "draft.md"),
                                                                                          shas)]}
    assert p["name"] == "join-them on notes.md and 1 more"
    sizes = pl._size(r) == (INPUTS / "notes.md").stat().st_size + (INPUTS / "draft.md").stat().st_size
    assert sizes


def test_a_loop_over_a_list_input_counts_its_members(tmp_path: Path):
    src, c = compiled(tmp_path, "sizes.thym", FOLDERS)
    other = tmp_path / "other"
    shutil.copytree(LITTLE, other)
    p = pl.plan(c, [row("repos", "list of folder", LITTLE, other, LITTLE)])
    loop = next(n for n in p["nodes"] if n.get("move") == "for")
    assert loop["members"] == {"at_most": 3}
    m = p["inputs"][0]["members"][0]
    assert set(m) == {"path", "sha256", "files", "bytes"} and m["files"] == 7 and m["bytes"] == 640


def test_one_path_for_a_list_a_list_for_one_path_and_an_empty_list_are_refused(tmp_path: Path):
    src, c = compiled(tmp_path, "join.thym", JOIN)
    one = pl.plan(c, [{"name": "xs", "type": "list of short", "path": "notes.md", "sha256": ""}])
    assert isinstance(one, Refusal) and (one.check, one.line) == ("input", 6)
    assert one.message == ("xs is a list of short: it takes a list given member by member, and one path was given "
                           "(notes.md)")
    empty = pl.plan(c, [{"name": "xs", "type": "list of short", "members": []}])
    assert isinstance(empty, Refusal) and "and no input was given for it" in empty.message
    _, count = compiled(tmp_path, "count.thym", "thym 0\n\nprogram c\n  takes t: text\n  gives n: number\n\n"
                                                "  give words t\nend\n")
    many = pl.plan(count, [row("t", "text", INPUTS / "notes.md", INPUTS / "draft.md")])
    assert isinstance(many, Refusal) and many.message == "t is a text: it takes one path, and a list of 2 was given"


def test_the_run_reads_each_member_in_order_records_each_and_replays(tmp_path: Path):
    src, c = compiled(tmp_path, "join.thym", JOIN)
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("one\n", encoding="utf-8")
    b.write_text("two\n", encoding="utf-8")
    p = pl.plan(c, [row("xs", "list of short", b, a)])
    t = R.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=src)
    assert landed(t) == {"all": "two one\n", "n": "2"}                      # in the order given, not by name
    assert t.atem().startswith("ran join-them on b.md, a.md")
    trace = mc.yaml_load(mc.read_text(t.path))
    rec = next(n for n in trace["nodes"] if n.get("type") == "record" and n.get("move") == "join")
    assert [i["name"] for i in rec["inputs"]] == ["xs", "xs[1]", "xs[2]"]
    assert [i.get("path") for i in rec["inputs"][1:]] == [b.as_posix(), a.as_posix()]
    assert rec["inputs"][1]["sha256"] == digest_path(b)
    again = R.replay(t.dir, root=tmp_path / "root")
    assert not isinstance(again, Refusal) and again.replay["identical"], again


def test_a_changed_or_missing_member_is_refused_by_its_place(tmp_path: Path):
    src, c = compiled(tmp_path, "join.thym", JOIN)
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("one\n", encoding="utf-8")
    b.write_text("two\n", encoding="utf-8")
    p = pl.plan(c, [row("xs", "list of short", a, b)])
    b.write_text("two, changed\n", encoding="utf-8")
    r = R.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=src)
    assert isinstance(r, Refusal) and r.check == "input"
    assert r.message.startswith("input xs[2] changed since it was planned: ")
    a.unlink()
    r = R.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=src)
    assert isinstance(r, Refusal) and r.message.startswith("input xs[1]: ") and "is not there" in r.message


def test_a_thym_0_program_declares_and_runs_a_list_input(tmp_path: Path):
    src, c = compiled(tmp_path, "count.thym", COUNT_ZERO)
    p = pl.plan(c, [row("xs", "list of text", INPUTS / "notes.md", INPUTS / "draft.md", INPUTS / "long-lines.md")])
    node = next(n for n in p["nodes"] if n.get("repeats"))
    assert "members" not in node                     # `members` is a thym 1 plan's key (THYM 17.3); thym 0's as before
    assert pl._members(next(iter(pl.build(c))).loop.coll, {"xs": p["inputs"][0]}, {}) == 3   # its count of calls
    assert landed(R.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=src)) == {"n": "3"}


def test_a_list_of_folders_is_snapshotted_member_by_member_and_replays_without_them(tmp_path: Path):
    src, c = compiled(tmp_path, "sizes.thym", FOLDERS)
    one, two = tmp_path / "one", tmp_path / "two"
    shutil.copytree(LITTLE, one)
    shutil.copytree(LITTLE, two)
    (two / "little" / "extra.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    p = pl.plan(c, [row("repos", "list of folder", one, two)])
    t = R.run(p, inputs_root=tmp_path, root=tmp_path / "root", program=src)
    out = landed(t)["sizes"]
    first, second = (int(x) for x in out.strip().split(", "))
    assert second == first + 2
    snaps = sorted(f.name for f in (t.dir / "inputs").iterdir())
    assert snaps == ["repos.1.folder.cosm", "repos.2.folder.cosm"]
    shutil.rmtree(one)
    shutil.rmtree(two)
    again = R.replay(t.dir, root=tmp_path / "root")
    assert not isinstance(again, Refusal) and again.replay["identical"], again
    (t.dir / "inputs" / "repos.2.folder.cosm").unlink()
    gone = R.replay(t.dir, root=tmp_path / "root")
    assert isinstance(gone, Refusal) and gone.message.startswith("input repos[2]: the recorded run kept no snapshot")


def test_the_command_line_gives_a_list_by_its_name_once_per_member(tmp_path: Path, capsys):
    src, _ = compiled(tmp_path, "join.thym", JOIN)
    assert cli._pairs(["xs=a.md", "xs=b.md"], src) == {"xs": ["a.md", "b.md"]}
    assert cli._pairs(["a.md", "b.md"], src) == {"xs": ["a.md", "b.md"]}    # the one input's members, bare
    assert cli._pairs(["xs=a.md"], None, names=["xs"], lists={"xs"}) == {"xs": ["a.md"]}
    notes, draft = INPUTS / "notes.md", INPUTS / "draft.md"
    assert cli.main(["run", str(src), f"xs={draft}", f"xs={notes}"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("ran join-them on draft.md, notes.md")
    n = Path(next(ln for ln in out if ln.startswith("n: ")).split(": ", 1)[1]).read_text(encoding="utf-8")
    assert n == "2"
    plan_file = tmp_path / "join.plan.cosm"
    assert cli.main(["plan", str(src), str(notes), str(draft), "--out", str(plan_file)]) == 0
    capsys.readouterr()
    assert cli.main(["run", str(plan_file), f"xs={notes}", "--program", str(src)]) == 2
    assert capsys.readouterr().out.strip().endswith("xs has 2 members in the plan, and 1 was given; give each, in "
                                                    "order, or plan it again")
    assert cli.main(["run", str(plan_file), f"xs={notes}", f"xs={draft}", "--program", str(src)]) == 0
