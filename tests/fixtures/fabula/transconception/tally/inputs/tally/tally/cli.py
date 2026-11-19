"""tally: count things from the command line.

    tally add NAME [N]      add N (default 1; may be negative) to NAME
    tally show [--all] [--json]
    tally undo              cancel the latest add that has not been undone

The ledger is $TALLY_FILE, or ~/.tally.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, ledger, render


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tally", description="Count things from the command line.")
    p.add_argument("--version", action="version", version=f"tally {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add to a count")
    a.add_argument("name")
    a.add_argument("n", nargs="?", type=int, default=1)
    s = sub.add_parser("show", help="show every total")
    s.add_argument("--all", action="store_true", help="include totals of 0")
    s.add_argument("--json", action="store_true", help="print the totals as one JSON object")
    sub.add_parser("undo", help="cancel the latest add")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = ledger.ledger_path()
    try:
        if args.command == "add":
            e = ledger.add(path, args.name, args.n)
            total = ledger.totals(ledger.read(path))[e.name]
            print(f"{e.name}: {total}")
        elif args.command == "show":
            totals = ledger.totals(ledger.read(path))
            if args.json:
                shown = {k: v for k, v in totals.items() if v != 0 or args.all}
                print(json.dumps(shown, sort_keys=True))
            else:
                lines = render.rows(totals, show_all=args.all)
                print("\n".join(lines) if lines else render.empty_message(args.all))
        elif args.command == "undo":
            e = ledger.undo(path)
            if e is None:
                print("nothing to undo")
            else:
                total = ledger.totals(ledger.read(path))[e.name]
                print(f"undid {-e.delta:+d} on {e.name}; {e.name}: {total}")
    except ledger.LedgerError as err:
        print(f"tally: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
