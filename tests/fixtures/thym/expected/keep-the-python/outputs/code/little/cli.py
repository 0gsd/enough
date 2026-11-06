"""The command line: little-tool <file>."""
import sys

from little.count import words


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(words(fh.read()))
    return 0
