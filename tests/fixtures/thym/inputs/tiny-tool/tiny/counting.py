"""Words, counted: what a word is, how many a text holds, and which come most often."""
from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

WORD = re.compile(r"[A-Za-z]+")
DEFAULT_TOP = 3


class CountError(Exception):
    """A file that cannot be counted; its message is shown to the user as it is."""


@dataclass(frozen=True)
class Summary:
    """What a text holds, counted."""
    words: int
    lines: int
    encoding: str = "utf-8"


def read_text(path: Path, env: dict | None = None) -> str:
    """The text of a file, read in the encoding TINY_ENCODING names (UTF-8 when unset)."""
    env = os.environ if env is None else env
    encoding = env.get("TINY_ENCODING", "utf-8") or "utf-8"
    try:
        return Path(path).read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError, LookupError) as e:
        raise CountError(f"cannot read {path}: {e.__class__.__name__}") from None


def words(text: str) -> list[str]:
    """The words of a text, lowercased, in order."""
    return [w.lower() for w in WORD.findall(text)]


def count_words(text: str) -> int:
    """How many words a text holds."""
    return len(words(text))


def top_words(text: str, n: int = DEFAULT_TOP) -> list[tuple[str, int]]:
    """The n commonest words with their counts, commonest first; ties in alphabetical order."""
    if n < 1:
        raise CountError("n must be 1 or more")
    counts = Counter(words(text))
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def summarise(text: str, encoding: str = "utf-8") -> Summary:
    """The words and lines of a text, with the encoding it was read in."""
    return Summary(count_words(text), len(text.splitlines()), encoding)
