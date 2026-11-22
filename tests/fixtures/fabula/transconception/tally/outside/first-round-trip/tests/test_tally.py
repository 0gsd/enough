import json

import pytest

from tally import cli
from tally.ledger import LedgerError, add, read, totals, undo
from tally.render import rows


def test_add_and_totals(tmp_path):
    p = tmp_path / "t.jsonl"
    add(p, "tea", now=1.0)
    add(p, "tea", 2, now=2.0)
    add(p, "walks", now=3.0)
    assert totals(read(p)) == {"tea": 3, "walks": 1}


def test_undo_walks_back(tmp_path):
    p = tmp_path / "t.jsonl"
    add(p, "tea", now=1.0)
    add(p, "walks", 2, now=2.0)
    assert undo(p).undoes == 2
    assert undo(p).undoes == 1
    assert undo(p) is None
    assert totals(read(p)) == {"tea": 0, "walks": 0}


def test_bad_names_and_zero(tmp_path):
    p = tmp_path / "t.jsonl"
    with pytest.raises(LedgerError, match="one word"):
        add(p, "two words")
    with pytest.raises(LedgerError, match="changes nothing"):
        add(p, "tea", 0)
    assert not p.exists()


def test_broken_line(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"at": 1, "name": "tea", "delta": 1}) + "\nnot json\n")
    with pytest.raises(LedgerError, match="line 2 is not a tally entry"):
        read(p)


def test_rows():
    assert rows({"a": 10, "bb": 1, "c": 0}) == ["a   10  " + "#" * 30, "bb   1  ###"]
    assert rows({"a": -2}) == ["a  -2"]
    assert rows({"c": 0}) == []
    assert rows({"c": 0}, show_all=True) == ["c  0"]


def test_cli_json_and_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TALLY_FILE", str(tmp_path / "t.jsonl"))
    assert cli.main(["add", "tea", "3"]) == 0
    capsys.readouterr()
    assert cli.main(["show", "--json"]) == 0
    assert capsys.readouterr().out.strip() == '{"tea": 3}'
    assert cli.main(["add", "two words"]) == 1
    assert "tally: a name is one word, with no spaces" in capsys.readouterr().err
