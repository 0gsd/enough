# tally

Count things from the command line: cups of tea, walks, pages read.

    python -m tally add tea         # tea: 1
    python -m tally add pages 12    # pages: 12
    python -m tally add pages -2    # pages: 10
    python -m tally show            # one row per name, with a bar
    python -m tally undo            # cancel the latest add

Counts are kept in an append-only ledger, `~/.tally.jsonl`, or the file `$TALLY_FILE` names. Nothing in it is
ever rewritten, so two shells adding at once never lose a count, and `undo` can always walk back.

Python 3.10 or later, standard library only.
