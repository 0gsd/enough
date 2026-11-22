# tally in Go: the layout

A layout of tally.fabulac.cosm for its transconception into Go: the files of the program to be, in the order they are written, what each holds, and the name each kept interface takes there. Written from the fabulac alone.

## Files, in the order they are written

| # | file | holds |
|---|---|---|
| 1 | go.mod | the Go package |
| 2 | main.go | the whole program |

## Interfaces

| interface | file | name |
|---|---|---|
| C:interface/command.tally | main.go | N_command_tally |
| C:interface/command.add | main.go | N_command_add |
| C:interface/command.show | main.go | N_command_show |
| C:interface/command.undo | main.go | N_command_undo |
| C:interface/tally.cli.main | main.go | N_tally_cli_main |
| C:interface/tally.ledger.ledger_path | main.go | N_tally_ledger_ledger_path |
| C:interface/tally.ledger.read | main.go | N_tally_ledger_read |
| C:interface/tally.ledger.add | main.go | N_tally_ledger_add |
| C:interface/tally.ledger.undo | main.go | N_tally_ledger_undo |
| C:interface/tally.ledger.totals | main.go | N_tally_ledger_totals |
| C:interface/tally.ledger.LedgerError | main.go | N_tally_ledger_LedgerError |
| C:interface/tally.render.rows | main.go | N_tally_render_rows |
| C:interface/tally.render.empty_message | main.go | N_tally_render_empty_message |
| C:interface/format.ledger-line | main.go | N_format_ledger_line |

## Gaps, and what fills each

| gap | fill |
|---|---|
| C:reliance/argparse-surface | written in main.go |

*a layout of tally.fabulac.cosm, in Go, compiled on 2026-11-22 by scripted*
