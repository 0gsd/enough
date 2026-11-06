"""Counting words."""


def words(text: str) -> int:
    """How many words a text holds: runs of characters between spaces."""
    return len(text.split())
