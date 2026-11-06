"""The command line: tiny count FILE [--lines], tiny top FILE [-n N]."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .counting import CountError, count_words, read_text, top_words


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tiny", description="Count the words of a text file.")
    p.add_argument("--version", action="version", version=f"tiny {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("count", help="count the words, or the lines, of a file")
    c.add_argument("file")
    c.add_argument("--lines", action="store_true", help="count lines instead of words")
    t = sub.add_parser("top", help="list the commonest words")
    t.add_argument("file")
    t.add_argument("-n", type=int, default=3, help="how many words to list")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = read_text(args.file)
        if args.command == "count":
            print(len(text.splitlines()) if args.lines else count_words(text))
        else:
            print(", ".join(f"{w}: {k}" for w, k in top_words(text, args.n)))
    except CountError as e:
        print(f"tiny: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
