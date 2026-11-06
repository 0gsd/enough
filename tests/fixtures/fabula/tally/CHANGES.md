# Changes

## 0.2.0 (2026-10-14)

- The ledger is now an append-only log, `~/.tally.jsonl`, one JSON object per line. 0.1 kept one JSON file of
  totals and rewrote it on every add: two adds at the same moment could lose one, and nothing could be undone.
- New: `tally undo` cancels the latest add by appending its opposite; undoing again walks further back.
- New: `$TALLY_FILE` names another ledger.
- 0.1's `~/.tally.json` is not read. Its totals can be carried over with one `tally add NAME N` each.

## 0.1.0 (2026-09-30)

- First release: `tally add NAME [N]` and `tally show`, totals kept in `~/.tally.json`.
