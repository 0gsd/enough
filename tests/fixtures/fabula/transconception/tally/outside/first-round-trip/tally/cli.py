"""The command line: parse, run one command against the ledger, print.

It holds no counting logic. A LedgerError becomes "tally: MESSAGE" on
standard error and exit status 1; a usage error is argparse's, status 2.
"""

import argparse
import json
import sys

from tally import __version__
from tally.ledger import LedgerError, add, ledger_path, read, totals, undo
from tally.render import empty_message, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tally",
        description="Count named things in an append-only ledger.",
    )
    parser.add_argument("--version", action="version", version=f"tally {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p_add = sub.add_parser("add", help="add N to the count called NAME")
    p_add.add_argument("name", help="one word, no spaces")
    p_add.add_argument("n", type=int, nargs="?", default=1, help="what to add (default 1; may be negative)")
    p_show = sub.add_parser("show", help="print every total")
    p_show.add_argument("--all", action="store_true", help="include totals of 0")
    p_show.add_argument("--json", action="store_true", help="print one JSON object instead of rows")
    sub.add_parser("undo", help="cancel the latest add")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = ledger_path()
    try:
        if args.command == "add":
            entry = add(path, args.name, args.n)
            total = totals(read(path))[entry.name]
            print(f"{entry.name}: {total}")
        elif args.command == "show":
            current = totals(read(path))
            if args.json:
                if not args.all:
                    current = {name: total for name, total in current.items() if total}
                print(json.dumps(current, sort_keys=True))
            else:
                lines = rows(current, args.all)
                if lines:
                    for line in lines:
                        print(line)
                else:
                    print(empty_message(args.all))
        elif args.command == "undo":
            entry = undo(path)
            if entry is None:
                print("nothing to undo")
            else:
                total = totals(read(path))[entry.name]
                print(f"undid {-entry.delta:+d} on {entry.name}; {entry.name}: {total}")
    except LedgerError as exc:
        print(f"tally: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
