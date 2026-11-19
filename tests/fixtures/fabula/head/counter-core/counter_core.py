"""counter_core: count the lines of a text."""


def count_lines(text: str) -> int:
    return len(text.splitlines())
