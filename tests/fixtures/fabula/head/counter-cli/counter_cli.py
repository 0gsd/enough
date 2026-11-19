"""counter: the command line."""
import sys

from counter_core import count_lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as f:
        print(count_lines(f.read()))
    return 0
