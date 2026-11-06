import pytest

from tiny.counting import CountError, count_words, top_words


def test_words_are_runs_of_letters():
    assert count_words("It's a dog-day, 2 dogs.") == 6


def test_top_words_break_ties_by_letter():
    assert top_words("b a b a c", 2) == [("a", 2), ("b", 2)]


def test_top_needs_one_or_more():
    with pytest.raises(CountError, match="n must be 1 or more"):
        top_words("a", 0)
