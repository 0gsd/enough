# tally in Rust: the layout

A layout of tally.fabulac.cosm for its transconception into Rust: the files of the program to be, in the order they are written, what each holds, and the name each kept interface takes there. Written from the fabulac alone.

## Files, in the order they are written

| # | file | holds |
|---|---|---|
| 1 | Cargo.toml | the Rust package |
| 2 | main.rs | the whole program |

## Interfaces

| interface | file | name |
|---|---|---|
| C:interface/command.tally | main.rs | N_command_tally |
| C:interface/command.add | main.rs | N_command_add |
| C:interface/command.show | main.rs | N_command_show |
| C:interface/command.undo | main.rs | N_command_undo |
| C:interface/tally.cli.main | main.rs | N_tally_cli_main |
| C:interface/tally.ledger.ledger_path | main.rs | N_tally_ledger_ledger_path |
| C:interface/tally.ledger.read | main.rs | N_tally_ledger_read |
| C:interface/tally.ledger.add | main.rs | N_tally_ledger_add |
| C:interface/tally.ledger.undo | main.rs | N_tally_ledger_undo |
| C:interface/tally.ledger.totals | main.rs | N_tally_ledger_totals |
| C:interface/tally.ledger.LedgerError | main.rs | N_tally_ledger_LedgerError |
| C:interface/tally.render.rows | main.rs | N_tally_render_rows |
| C:interface/tally.render.empty_message | main.rs | N_tally_render_empty_message |
| C:interface/format.ledger-line | main.rs | N_format_ledger_line |

## Gaps, and what fills each

| gap | fill |
|---|---|
| C:reliance/whole-numbers-unbounded | written in main.rs |
| C:reliance/argparse-surface | written in main.rs |

*a layout of tally.fabulac.cosm, in Rust, compiled on 2026-11-22 by scripted*
