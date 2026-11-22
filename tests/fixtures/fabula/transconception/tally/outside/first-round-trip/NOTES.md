# Rebuild notes: tally from tally.fabulac.cosm

Choices where the spec was silent or unclear (one per line, with the item it concerns):

1. C:interface/command.tally: the parser's description and every help string (add, show, undo, name, n, --all, --json) are not given; I wrote my own ("Count named things in an append-only ledger.", "add N to the count called NAME", ...). `tally -h` and `tally add -h` will differ from the original in those words.
2. C:structure/tally.ledger.Entry / C:behaviour/undo: `undoes` is a line number "counting blank lines", but Entry has no line field and read() drops blank lines, so undo cannot get line numbers from read() alone. I added a private `_read_numbered(path)` that undo uses; read() returns just the entries. If the original used positions in read()'s list, the two differ only when the ledger has blank lines.
3. C:behaviour/read: I check whether the file exists before reading (`path.exists()`), so a folder at the path gives an uncaught IsADirectoryError, a traceback and exit 1 (as C:reliance/uncaught-error's example says).
4. C:behaviour/read: invalid UTF-8 in the ledger is not caught. The whole file is decoded before the per-line try, so a UnicodeDecodeError ends the run with a traceback, exit 1. C:reliance/chained-errors' example ("a decode error turned into a ledger error") hints the original might wrap it instead. I did not.
5. C:interface/tally.ledger.read: I catch ValueError, KeyError, TypeError and AttributeError when building an entry, so any non-blank line that is not an object with at, name and delta (a list, a string, a null field) gives "<path>: line <n> is not a tally entry". The spec's example names only value and key errors; without TypeError a line like `[1]` would leave a traceback, against the interface's stated raise.
6. C:interface/tally.ledger.read: fields are converted with float(at), str(name), int(delta) (C:reliance/conversions, number-from-text, fraction-from-text, printed-form all point at that line), so `"delta": "3"` or `"delta": 2.9` are accepted (as 3 and 2), and `"name": 5` becomes "5". `undoes` is read with .get and converted with int() when present. The spec doesn't say how `undoes` is read.
7. C:interface/tally.ledger.add / undo: an explicit `now` is converted with float(), so `now=1` is written as 1.0. The spec only types it as float.
8. C:interface/tally.ledger.ledger_path: `env.get("TALLY_FILE") or ""` is stripped; a value made only of white space means the default. `~user` expansion is Path.expanduser's, so an unknown user raises an uncaught RuntimeError.
9. C:behaviour/add: the name printed in "NAME: TOTAL" is the stripped name the entry holds, not the word as typed.
10. C:behaviour/add: the name is checked before the number, so `tally add "two words" 0` reports the name.
11. C:behaviour/show: `show --json` with nothing to show prints `{}`, not the empty message. The spec says --json always prints one JSON object.
12. C:behaviour/show: the --json filter drops totals of 0 in the CLI (rows() does its own filtering); JSON is json.dumps defaults (ASCII escapes, ", " and ": ") with sort_keys=True.
13. C:interface/tally.render.rows: when show_all is set but no total is positive, the largest positive total defaults to 0 and no bar is drawn. A bar is `BAR * max(1, round(total * BAR_WIDTH / largest))` for a positive total. The trailing strip is str.rstrip(), so it uses Python's white-space set.
14. C:interface/tally.render.rows: the name is padded with str.ljust and the total with str.rjust (code points, C:reliance/text-length-in-code-points). Wide characters will misalign in a terminal, as the spec says they do.
15. C:interface/format.ledger-line: lines are written with path.open("a", encoding="utf-8") and one write of the JSON plus "\n". The parent folder is made with mkdir(parents=True, exist_ok=True) before every append. Text mode means Windows would write CRLF (C:reliance/newlines-translated).
16. C:interface/command.undo: the output's D is formatted with `{:+d}` of the cancelled delta (minus the new entry's delta). The total is re-read from the ledger after the append.
17. C:file/tests--test-tally-py: I wrote tests/test_tally.py with six pytest tests, one per P:case. pytest is not installed here, so I did not run them under pytest; I checked the same cases by hand through the CLI and the functions.
18. C:file/readme-md, C:file/changes-md: not reconstructed; the spec describes them without their text. LICENSE is written as the standard MIT text with "Copyright (c) 2026 Meadow Software" (R:licence/mit, the attribution statement). The exact wording of the original's copyright line is not given.

Spec vs this machine, and contradictions found:

- C:reliance/argparse-optional-positional: the spec's example says `tally add tea --x 3` reports "unrecognized arguments: --x 3". Under this machine's Python 3.13.11, argparse reports "unrecognized arguments: --x" (the 3 is taken as n). That is runtime behaviour, not the program's code. The spec's citations name 3.13.18, while its argparse-surface entry says "as 3.13.11 was recorded", so the spec mixes two patch releases.
- C:dependency/python-standard-library lists argparse, json, os, sys, time, dataclasses and pathlib. The rebuild uses exactly those.
- C:structure/tally.ledger.Entry says `undoes` counts blank lines, but read() (C:behaviour/read) skips blank lines and returns bare entries. The spec states both without saying how undo learns line numbers (see choice 2).
- N:requirement/standard-library says Python 3.10 or later. The `int | None` annotations used at runtime in the dataclass need 3.10, which fits.
