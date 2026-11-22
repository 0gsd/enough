"""The command line: tally add, tally show and tally undo.

It parses the arguments, runs one command against the ledger, prints, and
turns a LedgerError into exit status 1. It holds no counting logic.
"""

import argparse
import json
import sys

from tally import __version__, ledger, render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tally", description="Count named things in an append-only ledger."
    )
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add N to the count called NAME")
    add.add_argument("name", help="one word, no spaces")
    add.add_argument("n", type=int, nargs="?", default=1, help="what to add (default 1; may be negative)")
    show = sub.add_parser("show", help="print every total")
    show.add_argument("--all", action="store_true", help="include totals of 0")
    show.add_argument("--json", action="store_true", help="print one JSON object instead of rows")
    sub.add_parser("undo", help="cancel the latest add that has not been undone")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = ledger.ledger_path()
    try:
        if args.command == "add":
            entry = ledger.add(path, args.name, args.n)
            total = ledger.totals(ledger.read(path))[entry.name]
            print(f"{entry.name}: {total}")
        elif args.command == "show":
            totals = ledger.totals(ledger.read(path))
            if args.json:
                shown = {name: t for name, t in totals.items() if t or args.all}
                print(json.dumps(shown, sort_keys=True))
            else:
                lines = render.rows(totals, args.all)
                print("\n".join(lines) if lines else render.empty_message(args.all))
        elif args.command == "undo":
            entry = ledger.undo(path)
            if entry is None:
                print("nothing to undo")
            else:
                total = ledger.totals(ledger.read(path))[entry.name]
                print(f"undid {-entry.delta:+d} on {entry.name}; {entry.name}: {total}")
    except ledger.LedgerError as error:
        print(f"tally: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
