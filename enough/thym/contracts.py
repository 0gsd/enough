"""The static side of contracts (THYM.md 7.1, 7.3, 7.4, 9): which checks each call carries, the check an `assert`
condition names, the static refusals the compiler makes, and the sentence a contract item carries.

The checks a move carries are its declaration's `contract:` list (section 6.4); a user move inherits the checks of
every move it uses, and its `assert` lines add theirs (section 8.3). The runtime holds the dynamic side, on every
output; the compiler refuses only what can be known before a run: `no-counts`, when a number is put into a
projection whose contract forbids counts.

`CHECKS` is every check section 7.3 names, in its order, and `COMPILE` every check name a compile-time refusal uses
(section 9); a test holds the first to the specification's table. `summary` is a contract's sentence, by the rule of
section 10.
"""
from __future__ import annotations

from typing import Any


# Section 7.3's table, in its order. It is the specification's list, held to the text by a test; it is not the
# list of what may be named: a `keeps` or a contract may name any check a declaration's contract names or a move
# module registers (`check.known_checks` reads all three), so a move lane that registers a new check needs no line
# here, only a row in the text's table.
CHECKS = (
    "span-resolves", "stance-closed", "terms-grounded", "coverage", "no-invention", "stance-kept", "footer",
    "byte-exact", "atem-shape", "length", "span-inside", "whole-sentences", "weight-order", "scale-range",
    "scale-evidence", "null-pinned", "scales-met", "labelled", "never-source", "default-deny", "no-counts",
    "banded", "no-mark", "verified-derived", "verified-only-where-derived", "standing-gate", "epoch", "digests",
    "released", "provenance", "fabula-checks", "flavour", "files-found", "code-span", "licence-recorded",
    "outline-cited", "fold-grounded", "history-grounded", "parses", "interfaces-present", "files-present",
    "uses-told", "quotes-held", "nothing-lost", "ids-unique", "addressed", "no-duplicate", "only-the-asked",
    "only-the-changed", "one-line", "nothing-added", "lines-found", "scansion-grounded", "sound-grounded",
    "form-grounded", "ground-cited", "target-weighed", "target-confirmed", "case-outside", "cases-whole",
    "source-named", "ruled", "surface-answered", "apart", "evidence-stated", "cases-entailed", "authored-source",
    "only-authored", "in-sandbox",
)

# The checks a shipped declaration names ahead of the text: an owner's ruling that section 7.3's table does not hold
# yet, for the next revision of the specification at cosmoes.org. A test holds each to being no row of the table, so
# that it leaves this list the day the text takes it. Empty since the 0.8 texts were synced (every check 0.8 built
# is a row of the bundled 7.3). Since the 0.9 build: the fabulam's checks against its source and of a pshort (Thym
# 20.13, `enough/thym/moves/proof.py`), which the 0.9 text's 7.3 takes.
AHEAD: tuple[str, ...] = (
    "declarations-found", "comments-covered", "reach-agrees", "lines-resolve", "nothing-invented", "nothing-carried",
    "cites-resolve", "every-sentence-cited", "yield-cited", "teaching-followed", "no-up-to", "example-worked",
    "checking-told", "confidence-told", "symbols-worded",
)

# The moves a shipped declaration names ahead of the bundled text's 6.3 table. A test holds each to being no row of
# that table, so it leaves this list the day the text is synced. Empty since the 0.8 sync.
AHEAD_MOVES: tuple[str, ...] = ()

# The other way round: rows of the bundled text's 6.3 table that no declaration here builds yet. A test holds each to
# being undeclared, so it leaves this list the day its move is declared, and the text's blocks that call it are held
# to being refused as an unknown move until then. Empty since `run` (Thym 20.12) was built in 0.8
# (enough/thym/moves/run_entailment.py).
BEHIND_MOVES: tuple[str, ...] = ()

# A check's old name, read wherever it is written (section 7.3; a `thym 0` view keeps `emf-checks`, ruling 7).
OLD_NAMES = {"emf-checks": "fabula-checks"}

# Section 9's compile-time check names.
COMPILE = ("parse", "version", "unknown-move", "unknown-uri", "use-clash", "unbound", "rebound", "type", "recursion",
           "unknown-check", "no-give", "emit-without-project", "flavour")

# The static contract checks the compiler refuses by their own name (section 7.1).
STATIC = ("no-counts",)

# The check a condition operator names in an `assert` (section 7.4).
CONDITION_CHECKS = {"covers": "coverage"}

# The moves that consume what a program emits and withholds (section 8.2).
EMIT_CONSUMERS = ("project",)

def checks_of(target: Any) -> list[str]:
    """The checks a call's target carries: a declaration's `contract`, or a user move's inherited checks."""
    if target is None:
        return []
    if hasattr(target, "contract") and not hasattr(target, "block"):
        return list(target.contract)
    return list(getattr(target, "checks", []) or [])


def condition_checks(cond: Any) -> list[str]:
    """The checks an `assert` condition names, in the order they appear (`f covers t` names `coverage`)."""
    from . import parse as ps
    out: list[str] = []

    def walk(c: Any) -> None:
        if isinstance(c, ps.Logic):
            walk(c.left)
            walk(c.right)
        elif isinstance(c, ps.Not):
            walk(c.inner)
        elif isinstance(c, ps.Covers):
            name = CONDITION_CHECKS["covers"]
            if name not in out:
                out.append(name)

    walk(cond)
    return out


def summary(move: str, *, condition: str | None = None, block_kind: str = "program") -> str:
    """The one sentence a `P:contract` item carries, by the rule of THYM.md 10: what the move must leave true of
    what it gives, the same words for every move; for an `assert`, the condition as written."""
    if move == "assert":
        return f"The {block_kind}'s own check: {condition or 'its condition'}."
    return f"What {move} must leave true of what it gives."


def consumer_checks(targets: list[Any]) -> set[str]:
    """Every check the emit consumers among these call targets carry (a `project`'s `no-counts`, …)."""
    out: set[str] = set()
    for t in targets:
        if getattr(t, "name", None) in EMIT_CONSUMERS:
            out.update(checks_of(t))
    return out
