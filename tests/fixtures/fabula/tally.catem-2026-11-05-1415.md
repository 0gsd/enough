# What you can do with tally

tally counts named things from the command line, cups of tea, walks, pages, in a ledger that is only ever added to.
It needs Python 3.10 or later and nothing else. Run it as `python -m tally`.

## Count something

`tally add NAME [N]` adds N (1 when left out) to the count called NAME and prints `NAME: TOTAL`. N may be negative
(`tally add pages -2`) but never 0. A name is one word with no spaces.

## See every total

`tally show` prints one row per name, in alphabetical order, with a bar of `#` scaled so the largest total fills 30
characters. Totals of 0 are hidden; `--all` shows them. `--json` prints the same totals as one JSON object instead.
With nothing to show it says `nothing tallied yet`.

## Take an add back

`tally undo` cancels the latest add that has not already been undone, and says what it did: `undid +1 on tea; tea: 2`.
Run it again to walk further back. When nothing is left it says `nothing to undo`. Nothing is ever deleted: an undo is
one more line in the ledger.

## Where the counts live

In `~/.tally.jsonl`, one JSON object per line, or in the file the environment variable `TALLY_FILE` names. Two shells
adding at once are both counted. A ledger from tally 0.1 (`~/.tally.json`) is not read.

## When something goes wrong

A refused add, or a ledger line that is not an entry, prints `tally: ` and the reason on standard error and exits with
status 1 (`tally: <ledger>: line 2 is not a tally entry` names the line). A command typed wrongly prints the usage and exits
with status 2. `tally --version` prints the version.

*a catem of tally.fabulac.cosm, at depth overview, compiled on 2026-11-05 14:15 by anthropic/claude-opus-5.5 (cloud, openrouter)*
