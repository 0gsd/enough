import json

import pytest

from tally import cli, ledger, render


def test_add_and_totals(tmp_path):
    p = tmp_path / "t.jsonl"
    ledger.add(p, "tea", now=1.0)
    ledger.add(p, "tea", 2, now=2.0)
    ledger.add(p, "walks", now=3.0)
    assert ledger.totals(ledger.read(p)) == {"tea": 3, "walks": 1}


def test_undo_walks_back_and_never_undoes_an_undo(tmp_path):
    p = tmp_path / "t.jsonl"
    ledger.add(p, "tea", now=1.0)
    ledger.add(p, "walks", 2, now=2.0)
    assert ledger.undo(p, now=3.0).undoes == 2
    assert ledger.undo(p, now=4.0).undoes == 1
    assert ledger.undo(p, now=5.0) is None
    assert ledger.totals(ledger.read(p)) == {"tea": 0, "walks": 0}


def test_bad_names_and_zero_are_refused(tmp_path):
    p = tmp_path / "t.jsonl"
    with pytest.raises(ledger.LedgerError, match="one word"):
        ledger.add(p, "two words")
    with pytest.raises(ledger.LedgerError, match="changes nothing"):
        ledger.add(p, "tea", 0)
    assert not p.exists()


def test_a_broken_line_names_its_number(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"at": 1, "name": "tea", "delta": 1}\nnot json\n', encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="line 2 is not a tally entry"):
        ledger.read(p)


def test_rows_scale_bars_and_hide_zero():
    assert render.rows({"a": 10, "bb": 1, "c": 0}) == ["a   10  " + "#" * 30, "bb   1  ###"]
    assert render.rows({"a": -2}) == ["a  -2"]
    assert render.rows({"c": 0}) == []
    assert render.rows({"c": 0}, show_all=True) == ["c  0"]


def test_cli_show_json_and_error_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TALLY_FILE", str(tmp_path / "t.jsonl"))
    assert cli.main(["add", "tea", "3"]) == 0
    assert cli.main(["show", "--json"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"tea": 3}
    assert cli.main(["add", "two words"]) == 1
    assert capsys.readouterr().err == "tally: a name is one word, with no spaces\n"
