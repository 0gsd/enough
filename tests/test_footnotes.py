"""Footnote surgery (docs/paginate-plan.md §2.1).

This file is the reference spec for `enough/footnotes.py` **and** for the JS
mirror in index.html (`fnParse` / `fnRenumber` / `fnNextNumber` /
`fnInsertAt`), which is why the documents below are written out in full and
the expected output is spelled letter for letter rather than computed. Two
implementations of the same rules only stay in step if the rules are readable
in one screen.

Covered: what counts as a ref and what doesn't (code fences, inline spans,
named labels, definitions), the terminal definitions block, renumbering
including orphans and reordering, insertion with the renumber cascade it
triggers, and the two properties the whole feature rests on — renumbering is
idempotent, and it changes nothing but labels.

Pure functions, no fixtures, no filesystem.
"""

from __future__ import annotations

from enough import footnotes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def labels(entries: list[dict]) -> list[str]:
    return [e["label"] for e in entries]


def mask_labels(text: str) -> str:
    """`text` with every footnote label flattened to one token — the document
    as a reader sees it, minus the numbering."""
    return footnotes.REF_RE.sub("[^*]", text)


def prose_and_block(text: str) -> tuple[str, str]:
    """`(everything before the terminal definitions block, the block)`."""
    span = footnotes.definitions_span(text)
    if span is None:
        return text, ""
    return text[:span[0]], text[span[0]:span[1]]


# A document with one of everything: two managed footnotes out of order, a
# named one, an orphan definition, a fenced block and an inline code span.
KITCHEN_SINK = """# Notes

A first claim[^3] and a second[^1], plus a pinned aside[^intro-note].

```markdown
[^99] is how you write a reference.
[^99]: and this is its definition.
```

Inline, `[^98]` is the same idea.

[^3]: the third label, written first.
[^intro-note]: a named note, pinned where the writer put it.
[^1]: the first label, written second.
[^42]: an orphan — nothing refers to it.
"""


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def test_parse_reports_refs_and_defs_in_document_order():
    text = "One[^1] and two[^2].\n\n[^1]: first\n[^2]: second\n"
    doc = footnotes.parse(text)
    assert labels(doc["refs"]) == ["1", "2"]
    assert labels(doc["defs"]) == ["1", "2"]
    assert all(r["numeric"] for r in doc["refs"])
    assert [d["body"] for d in doc["defs"]] == ["first", "second"]


def test_parse_spans_slice_back_out_of_the_source():
    text = "One[^1].\n\n[^1]: first\n"
    doc = footnotes.parse(text)
    ref = doc["refs"][0]
    entry = doc["defs"][0]
    assert text[ref["start"]:ref["end"]] == "[^1]"
    assert text[entry["start"]:entry["end"]] == "[^1]: first"
    # The body is a raw tail slice, so a card knows where to write back.
    assert text[entry["end"] - len(entry["body"]):entry["end"]] == entry["body"]


def test_a_definitions_own_label_is_not_a_ref():
    text = "[^1]: an entry with no reference anywhere\n"
    doc = footnotes.parse(text)
    assert doc["refs"] == []
    assert labels(doc["defs"]) == ["1"]


def test_a_ref_inside_a_definition_body_is_not_a_ref():
    """Renumbering goes by order of appearance and definitions live at the
    end of the file — counting these would sort the tail of the document
    first, so they are read as body text."""
    text = "Claim[^1].\n\n[^1]: see also [^2]\n[^2]: the other one\n"
    doc = footnotes.parse(text)
    assert labels(doc["refs"]) == ["1"]
    assert labels(doc["defs"]) == ["1", "2"]


def test_definitions_may_be_indented_up_to_three_spaces():
    text = "A[^1].\n\n   [^1]: still a definition\n"
    doc = footnotes.parse(text)
    assert labels(doc["defs"]) == ["1"]
    assert doc["defs"][0]["body"] == "still a definition"
    # Four spaces is an indented code block, not a definition.
    assert footnotes.parse("A[^1].\n\n    [^1]: not one\n")["defs"] == []


def test_an_empty_label_is_not_a_footnote():
    """`[^]` is the sentinel the edit face types before it expands. It must
    never read as a reference on its way through."""
    doc = footnotes.parse("Half-typed[^] here.\n")
    assert doc["refs"] == [] and doc["defs"] == []


# ---------------------------------------------------------------------------
# Code is not prose
# ---------------------------------------------------------------------------

def test_refs_and_defs_inside_a_fenced_block_are_ignored():
    doc = footnotes.parse(KITCHEN_SINK)
    assert "99" not in labels(doc["refs"])
    assert "99" not in labels(doc["defs"])


def test_refs_inside_an_inline_code_span_are_ignored():
    doc = footnotes.parse(KITCHEN_SINK)
    assert "98" not in labels(doc["refs"])
    assert labels(doc["refs"]) == ["3", "1", "intro-note"]


def test_double_backtick_spans_and_stray_backticks():
    text = ("A real one[^1], ``a span with [^7] inside``, and a stray ` "
            "backtick before[^2].\n")
    assert labels(footnotes.parse(text)["refs"]) == ["1", "2"]


def test_a_stray_backtick_does_not_swallow_the_rest_of_the_file():
    """An unmatched run cannot cross a blank line, so a lone backtick in one
    paragraph leaves the next paragraph's footnotes alone."""
    text = "A stray ` here.\n\nA real one[^1].\n\n[^1]: one\n"
    assert labels(footnotes.parse(text)["refs"]) == ["1"]


def test_tilde_fences_and_indented_fences_count_as_code():
    text = ("Real[^1].\n\n"
            "  ~~~python\n  # [^7] in a tilde fence, indented two spaces\n  ~~~\n\n"
            "[^1]: one\n")
    assert labels(footnotes.parse(text)["refs"]) == ["1"]


def test_an_unclosed_fence_runs_to_the_end_of_the_document():
    text = "Real[^1].\n\n```\n[^7] in a block still being typed\n"
    assert labels(footnotes.parse(text)["refs"]) == ["1"]


def test_renumber_leaves_code_alone():
    out, mapping = footnotes.renumber(KITCHEN_SINK)
    assert "[^99] is how you write a reference." in out
    assert "[^99]: and this is its definition." in out
    assert "`[^98]`" in out
    assert "99" not in mapping and "98" not in mapping


# ---------------------------------------------------------------------------
# Named labels
# ---------------------------------------------------------------------------

def test_named_labels_are_recognised_but_not_numeric():
    doc = footnotes.parse("Aside[^intro-note].\n\n[^intro-note]: pinned\n")
    assert doc["refs"][0] == {"label": "intro-note", "numeric": False,
                              "start": 5, "end": 18}
    assert doc["defs"][0]["numeric"] is False


def test_named_labels_are_never_renumbered_or_moved():
    out, mapping = footnotes.renumber(KITCHEN_SINK)
    assert "pinned aside[^intro-note]" in out
    assert "intro-note" not in mapping
    # And it keeps its slot in the block: second of the four entries.
    assert labels(footnotes.parse(out)["defs"])[1] == "intro-note"


# ---------------------------------------------------------------------------
# Multi-line definition bodies
# ---------------------------------------------------------------------------

def test_four_space_continuation_lines_belong_to_the_body():
    text = ("A[^1].\n\n"
            "[^1]: first line\n"
            "    second line\n"
            "    third line\n"
            "[^2]: a separate entry\n")
    entry = footnotes.parse(text)["defs"][0]
    assert entry["body"] == "first line\n    second line\n    third line"
    assert text[entry["start"]:entry["end"]].startswith("[^1]: first line")
    assert labels(footnotes.parse(text)["defs"]) == ["1", "2"]


def test_a_tab_also_continues_a_body():
    text = "A[^1].\n\n[^1]: first line\n\tcontinued with a tab\n"
    assert footnotes.parse(text)["defs"][0]["body"] == \
        "first line\n\tcontinued with a tab"


def test_a_blank_line_ends_a_definition():
    text = "A[^1].\n\n[^1]: first line\n\n    an indented block, not the body\n"
    entry = footnotes.parse(text)["defs"][0]
    assert entry["body"] == "first line"


def test_renumber_carries_a_multi_line_body_with_its_label():
    text = ("Second[^2] first[^1].\n\n"
            "[^2]: two\n    and more of two\n"
            "[^1]: one\n")
    out, _ = footnotes.renumber(text)
    assert out == ("Second[^1] first[^2].\n\n"
                   "[^1]: two\n    and more of two\n"
                   "[^2]: one\n")


# ---------------------------------------------------------------------------
# definitions_span
# ---------------------------------------------------------------------------

def test_definitions_span_covers_the_terminal_block():
    text = "A[^1] B[^2].\n\n[^1]: one\n[^2]: two\n"
    start, end = footnotes.definitions_span(text)
    assert text[start:end] == "[^1]: one\n[^2]: two"
    assert text[end:] == "\n"


def test_definitions_span_includes_continuation_lines():
    text = "A[^1].\n\n[^1]: one\n    still one\n"
    start, end = footnotes.definitions_span(text)
    assert text[start:end] == "[^1]: one\n    still one"


def test_definitions_span_is_none_without_definitions():
    assert footnotes.definitions_span("Just prose.\n") is None


def test_definitions_span_is_none_when_prose_follows():
    """Definitions in the middle of a file are not a terminal block; a note
    filed after them would land under a heading the module cannot see."""
    text = "A[^1].\n\n[^1]: one\n\nMore prose afterwards.\n"
    assert footnotes.definitions_span(text) is None


def test_definitions_span_takes_only_the_consecutive_run():
    text = "A[^1] B[^2].\n\n[^1]: one\n\n[^2]: two\n"
    start, end = footnotes.definitions_span(text)
    assert text[start:end] == "[^2]: two"


# ---------------------------------------------------------------------------
# next_number
# ---------------------------------------------------------------------------

def test_next_number_counts_the_managed_refs_before_the_offset():
    text = "One[^1] two[^2] three[^3].\n\n[^1]: a\n[^2]: b\n[^3]: c\n"
    assert footnotes.next_number(text, 0) == 1
    assert footnotes.next_number(text, text.index("two")) == 2
    assert footnotes.next_number(text, text.index("three")) == 3
    assert footnotes.next_number(text, len(text)) == 4


def test_next_number_ignores_named_refs_and_code():
    text = ("Named[^aside] then `[^7]` then real[^1].\n\n"
            "[^aside]: named\n[^1]: one\n")
    assert footnotes.next_number(text, text.index("real")) == 1
    assert footnotes.next_number(text, text.index(".\n")) == 2


def test_next_number_at_a_refs_own_start_does_not_count_it():
    text = "Claim[^1].\n\n[^1]: one\n"
    assert footnotes.next_number(text, text.index("[^1]")) == 1
    assert footnotes.next_number(text, text.index("[^1]") + 4) == 2


# ---------------------------------------------------------------------------
# renumber
# ---------------------------------------------------------------------------

def test_renumber_puts_an_out_of_order_document_in_order():
    text = ("Third[^3] first[^1] second[^2].\n\n"
            "[^1]: one\n[^2]: two\n[^3]: three\n")
    out, mapping = footnotes.renumber(text)
    assert out == ("Third[^1] first[^2] second[^3].\n\n"
                   "[^1]: three\n[^2]: one\n[^3]: two\n")
    assert mapping == {"3": "1", "1": "2", "2": "3"}


def test_renumber_reorders_the_definitions_block_into_ref_order():
    """The bodies do not move between labels — the entries move as a unit,
    so the block reads in the order the reader meets the refs."""
    text = "Beta[^2] alpha[^1].\n\n[^1]: alpha body\n[^2]: beta body\n"
    out, _ = footnotes.renumber(text)
    assert out == "Beta[^1] alpha[^2].\n\n[^1]: beta body\n[^2]: alpha body\n"


def test_renumber_is_a_no_op_on_an_already_ordered_document():
    text = "One[^1] two[^2].\n\n[^1]: one\n[^2]: two\n"
    out, mapping = footnotes.renumber(text)
    assert out == text
    # The map is the managed set, not a diff: labels that stayed put appear.
    assert mapping == {"1": "1", "2": "2"}


def test_renumber_without_any_managed_footnotes_returns_the_text_unchanged():
    text = "Only[^aside] a named one.\n\n[^aside]: named\n"
    assert footnotes.renumber(text) == (text, {})
    assert footnotes.renumber("No footnotes at all.\n") == \
        ("No footnotes at all.\n", {})


def test_renumber_leaves_orphan_definitions_byte_untouched():
    text = ("Fifth[^5] and third[^3].\n\n"
            "[^3]: three\n[^5]: five\n[^9]: an orphan nobody refers to\n")
    out, mapping = footnotes.renumber(text)
    assert out == ("Fifth[^1] and third[^2].\n\n"
                   "[^1]: five\n[^2]: three\n"
                   "[^9]: an orphan nobody refers to\n")
    assert mapping == {"5": "1", "3": "2"}
    assert "9" not in mapping


def test_renumber_gives_a_repeated_label_one_number():
    """A label used twice is one footnote, not two — and `{old: new}` could
    not say anything else."""
    text = "A[^1] again[^1] then[^2].\n\n[^1]: one\n[^2]: two\n"
    out, mapping = footnotes.renumber(text)
    assert out == text
    assert mapping == {"1": "1", "2": "2"}


def test_renumber_relabels_a_definition_that_sits_outside_the_block():
    """Only the terminal block is reordered; a stray definition earlier in
    the file still follows its label."""
    text = "A[^2].\n\n[^2]: two, filed early\n\nMore prose.\n"
    out, mapping = footnotes.renumber(text)
    assert out == "A[^1].\n\n[^1]: two, filed early\n\nMore prose.\n"
    assert mapping == {"2": "1"}


def test_renumber_is_idempotent():
    once, first = footnotes.renumber(KITCHEN_SINK)
    twice, second = footnotes.renumber(once)
    assert twice == once
    assert second == {"1": "1", "2": "2"}


def test_renumber_changes_nothing_but_the_labels():
    """The round-trip property the read face depends on: with labels masked
    out, the prose is identical and the definitions block holds exactly the
    same lines (in some order — reordering is the point)."""
    src_prose, src_block = prose_and_block(KITCHEN_SINK)
    out, _ = footnotes.renumber(KITCHEN_SINK)
    out_prose, out_block = prose_and_block(out)
    assert mask_labels(out_prose) == mask_labels(src_prose)
    assert sorted(mask_labels(ln) for ln in out_block.split("\n")) == \
        sorted(mask_labels(ln) for ln in src_block.split("\n"))


# ---------------------------------------------------------------------------
# insert_at
# ---------------------------------------------------------------------------

SIMPLE = "One[^1] two[^2].\n\n[^1]: first\n[^2]: second\n"


def test_insert_between_two_refs_renumbers_the_rest_including_defs():
    """Acceptance §4.1: inserting between 1 and 2 renumbers 2→3 everywhere."""
    out, k = footnotes.insert_at(SIMPLE, SIMPLE.index(" two"), "wedged in")
    assert k == 2
    assert out == ("One[^1][^2] two[^3].\n\n"
                   "[^1]: first\n[^2]: wedged in\n[^3]: second\n")


def test_insert_at_the_start_of_the_document():
    out, k = footnotes.insert_at(SIMPLE, 0)
    assert k == 1
    assert out == ("[^1]One[^2] two[^3].\n\n"
                   "[^1]:\n[^2]: first\n[^3]: second\n")


def test_insert_after_every_ref_appends_without_touching_the_others():
    out, k = footnotes.insert_at(SIMPLE, SIMPLE.index("."), "the last word")
    assert k == 3
    assert out == ("One[^1] two[^2][^3].\n\n"
                   "[^1]: first\n[^2]: second\n[^3]: the last word\n")


def test_insert_creates_the_block_one_blank_line_below_the_prose():
    text = "A document with no notes yet."
    out, k = footnotes.insert_at(text, len(text), "the first note")
    assert k == 1
    assert out == ("A document with no notes yet.[^1]\n\n"
                   "[^1]: the first note\n")


def test_insert_creating_a_block_does_not_stack_blank_lines():
    text = "Prose that ends with room to spare.\n\n\n"
    out, _ = footnotes.insert_at(text, len("Prose"))
    assert out == "Prose[^1] that ends with room to spare.\n\n[^1]:\n"


def test_insert_with_an_empty_body_leaves_the_entry_ready_to_edit():
    """An orphan ref renders a card with an empty body; there is no trailing
    space for the editor to inherit."""
    out, _ = footnotes.insert_at("Prose.", 6)
    assert out == "Prose.[^1]\n\n[^1]:\n"


def test_insert_indents_a_multi_line_body_to_the_continuation_depth():
    out, _ = footnotes.insert_at("Prose.", 6, "first line\nsecond line")
    assert out == "Prose.[^1]\n\n[^1]: first line\n    second line\n"
    assert footnotes.parse(out)["defs"][0]["body"] == "first line\n    second line"


def test_insert_files_the_new_entry_in_ref_order_around_a_named_one():
    text = ("One[^1] pinned[^aside] two[^2].\n\n"
            "[^1]: first\n[^aside]: named\n[^2]: second\n")
    out, k = footnotes.insert_at(text, text.index(" two"), "wedged in")
    assert k == 2
    assert out == ("One[^1] pinned[^aside][^2] two[^3].\n\n"
                   "[^1]: first\n[^aside]: named\n[^2]: wedged in\n"
                   "[^3]: second\n")


def test_insert_leaves_named_refs_and_code_alone():
    text = ("Named[^aside] and `[^9]` and one[^1].\n\n"
            "[^aside]: named\n[^1]: first\n")
    out, k = footnotes.insert_at(text, text.index(" and one"))
    assert k == 1
    assert out == ("Named[^aside] and `[^9]`[^1] and one[^2].\n\n"
                   "[^aside]: named\n[^1]:\n[^2]: first\n")


def test_insert_then_renumber_is_a_no_op():
    out, _ = footnotes.insert_at(SIMPLE, SIMPLE.index(" two"), "wedged in")
    assert footnotes.renumber(out)[0] == out


def test_insert_into_a_document_whose_notes_are_not_terminal_starts_a_block():
    """Degenerate but well-defined: with prose after the definitions there is
    no terminal block, so the new entry starts one at the end rather than
    guess where the old notes belong."""
    text = "A[^1].\n\n[^1]: one\n\nMore prose.\n"
    out, k = footnotes.insert_at(text, text.index("More prose") + 10, "later")
    assert k == 2
    assert out == "A[^1].\n\n[^1]: one\n\nMore prose[^2].\n\n[^2]: later\n"
