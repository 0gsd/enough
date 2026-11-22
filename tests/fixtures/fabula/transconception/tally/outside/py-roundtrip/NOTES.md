# Choices made where the fabulac was silent or unclear

- C:interface/command.tally: the parser's description ("Count named things in an append-only ledger.") is my own words; the spec gives no help or description text.
- C:interface/command.add / command.show / command.undo: every sub-command and argument help string is my own wording, taken from each item's `means`/`summary`; the spec quotes none.
- C:interface/command.tally: `prog="tally"` is set explicitly, so the usage line reads "tally ..." under `python -m tally` (3.13 would otherwise print "python3 -m tally"), as the argparse-surface example requires.
- C:interface/command.add: `n` is an optional positional (`nargs="?"`, `type=int`, default 1), the subparsers `dest="command"`, `required=True`, per the signatures and the argparse-surface example.
- C:interface/tally.ledger.read: the conversions are `float(at)`, `str(name)`, `int(delta)` (from C:reliance/conversions, printed-form, number-from-text cited at ledger.py#L46); `undoes` is read with `.get` and converted with `int()` when not null, else None. The spec does not say how `undoes` is read.
- C:interface/tally.ledger.read: the handler catches ValueError, KeyError, TypeError and AttributeError, so any non-blank line that is not a JSON object holding at, name and delta (a list, a number, a string, a bad field) becomes "line N is not a tally entry". C:reliance/error-kinds' example names only value and key errors; I widened it to match the `raises` clause.
- C:interface/tally.ledger.read: the file is read with `read_text(encoding="utf-8")` outside the per-line handler, so invalid UTF-8 is an uncaught decoding error (traceback, exit 1) rather than a LedgerError; the spec says only that such a ledger "fails to read".
- C:interface/tally.ledger.read: a missing file is checked with `path.exists()`, so a broken link reads as empty and a folder gives an uncaught error (per C:reliance/path-kinds and uncaught-error).
- C:behaviour/read: "blank" is a line that is empty after `strip()` (C:reliance/truth-of-values example); line numbers in the error count blank lines, entry places for undo do not (the `fixed` provenance).
- C:interface/tally.ledger.add: the name check comes before the zero check; `now` is stored as given (not forced to float).
- C:interface/format.ledger-line: the line is written with `json.dumps(record, sort_keys=True)` (default separators and ensure_ascii) plus "\n", through a text-mode append opened with encoding utf-8; the folder is made with `mkdir(parents=True, exist_ok=True)` just before the append.
- C:interface/tally.ledger.undo: the cancelled delta's opposite is written as `-delta`; the new entry carries the cancelled entry's name; ties are impossible since the walk goes from the last place to the first.
- C:behaviour/show: the name and total column widths are measured over the rows shown only (zeros hidden without --all are not counted); the example cannot tell the two readings apart.
- C:behaviour/show: the largest positive total is taken over the rows shown, `max(..., default=0)`; a bar is `max(1, round(total * 30 / largest))` for a positive total, none otherwise; the row is right-stripped as a whole with `str.rstrip()`.
- C:interface/command.show: rows are printed with one `print` of the lines joined by "\n"; --json prints `json.dumps(shown, sort_keys=True)` of the totals with zeros removed unless --all (so an empty ledger prints `{}`).
- C:interface/command.add: the printed name is the stripped name (the entry's), and its total is read back from the whole ledger after the append.
- C:interface/tally.cli.main: `ledger_path()` is called outside the LedgerError handler, so an unknown ~user in TALLY_FILE is an uncaught error.
- C:file/tally--main-py: `from tally.cli import main` (absolute import) and `sys.exit(main())`.
- C:file/tally--init-py: the docstring text is my own.

# Contradictions or doubts found

- C:reliance/argparse-optional-positional: its example says `tally add tea --x 3` reports "unrecognized arguments: --x 3", but Python 3.13.11 on this machine reports "unrecognized arguments: --x" (argparse now defers an empty match of an optional positional, so 3 is taken as n). I kept stock argparse; the difference is the runtime's, not the program's.
- C:dependency/python-standard-library lists `os, sys, time, dataclasses and pathlib` and the README says Python 3.10 or later; the `int | None` annotations need 3.10, which agrees. No contradiction, but the rebuild was only run on 3.13.
- P:case/undo-walks-back summary still says "the first undo names line 2, the second line 1"; with no blank lines, line and place agree, so it does not contradict the fixed wording.
- D:question/undo-by-opposite-unsure and D:question/undo-unsure still quote the old "names that entry's line" wording; I followed the `fixed`/`now` wording (place among entries, blank lines not counted).
