"""The fabulam's own checks over the volume alone (MacroCOSM OES 18.4.10; the design is docs/v090-fabulam-design.md,
section 2.A).

A fabulam is a fabula of flavour `fabulam`: one Lean 4 file taken apart into what it states, defines, proves on the
way, leans on and delivers, and how the argument runs. `enough/fabula.py` calls `run_checks` when the flavour is
`fabulam`, beside the fabula's own checks, and the names join `checks.own` in the manifest. Every check is by rule.
None judges whether the mathematics or the teaching is good. None reads the Lean: the checks against the source
(2.B) and of a pshort (2.C) are Thym's (`enough/thym/moves/proof.py`).

A fabulam is built in stages, and each stage lands a fabulam that must pass `fabula-checks`. So a check that asks for
something a later stage writes (every statement's yield, the stages and the teaching, the worked example, the comment
verdicts, a reached lemma's role, the fit) holds it only once the volume says it is whole (`derived.completeness:
full`) or once that layer has begun (one yield, one stage, one verdict, one role, one fit is there). What is there is
always held to its shape.

    CHECKS, SEVERITY, run_checks(volume, add)

`add(check, item, message, field=None, *, severity=None)` is `enough/fabula.py`'s. Standalone: the standard library
and `enough.macrocosm`; `parts-resolve` reaches `enough.fabulac_head` when it runs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from . import macrocosm as mc

FLAVOUR = "fabulam"
SUFFIX = ".fabulam.cosm"
PARTS_SUFFIX = ".fabulam.parts"

CHECKS = ("declared-once", "statement-whole", "yield-stated", "fit-stated", "spine-told", "stages-whole",
          "grounds-given", "audit-whole", "stance-fits", "checking-said", "example-worked", "no-up-to",
          "statements-agree", "parts-resolve", "regime-named", "no-judgement", "plain-words", "spine-rule-differs")
WARNINGS = ("regime-named", "no-judgement", "plain-words", "spine-rule-differs")
SEVERITY = {c: ("warning" if c in WARNINGS else "error") for c in CHECKS}

# The fixed items (design 1.5, 3.3).
CHECKING_ID = "P:claim/checking"
READ_AS_TEXT_ID = "P:assumption/read-as-text"
WORDING_ID = "E:work/wording"

DECLARED = ("statement", "definition", "lemma")          # C kinds that are one Lean declaration each
STAGE_ORDER = ("reduction", "main", "tool", "side", "close")
QUANTIFIER_KINDS = ("for-all", "exists", "infinitely-many", "eventually")
RELATES_HOW = ("implies", "special-case-of", "equivalent", "independent")
CHOOSES_FIELDS = ("what", "where", "value", "gives", "best", "confidence")
TRIVIAL_FIELDS = ("case", "known", "delivered", "compares")
CONFIDENCE = ("high", "medium", "low")
CONFIDENCE_KINDS = ("C:step", "C:constant", "C:part", "P:yield", "P:fit", "P:reading", "P:case")
AUDIT_KINDS = ("header", "module-note", "note", "inline")
AUDIT_VERDICTS = ("agrees", "claim", "nothing")
CLAIM_CHECKED = {"yes": ("by",), "partial": ("by", "short-of", "mismatch", "false-as-written"),
                 "contradicted": ("by", "mismatch"), "not-checkable": ()}
MISMATCH = ("formula", "hypothesis", "name", "numbering", "inference")
CHECKING_WORDS = ("machine-checked", "verified", "certified", "proved correct")
JUDGEMENT_WORDS = ("trivial", "easy", "intended", "obvious", "famous")
UP_TO_ALLOWED = ("isomorphism", "order", "sign", "symmetry", "relabelling")
# Words by which a sentence speaks of size, rate or order of magnitude (regime-named, a warning).
SIZE_WORDS = ("size", "rate", "order of magnitude", "grows", "growth", "asymptotic", "tends to", "as large as",
              "as small as", "bounded by", "density", "o(", "≪", "≍", "∼")
# Symbols a stage's plain sentences may not hold (plain-words): mathematics' signs, never ordinary punctuation.
PLAIN_SYMBOLS = set("=<>≤≥≡≠∣·×+*/^∑∏∫√∞∈∉∀∃→←↔⇒⊂⊆∪∩∘`|!%∂∇λπσφχ_{}[]")

# What each kind's stance may be (design 1.2). `deduced` is allowed everywhere ("anything a rule adds later"), and a
# kind not named here is held only to `assumed` (which only a reliance without stated-in, a term or a concept takes).
_OBSERVED = {"observed", "deduced"}
_OPINION = {"opinion", "deduced"}
_HEARSAY = {"hearsay", "deduced"}
STANCES: dict[str, set[str]] = {
    "C:file": _OBSERVED, "C:statement": _OBSERVED, "C:definition": _OBSERVED, "C:lemma": _OBSERVED,
    "C:dependency": _OBSERVED, "P:assumption": _OBSERVED, "N:decision": {"observed", "opinion", "deduced"},
    "C:step": _OPINION, "C:constant": _OPINION, "C:part": _OPINION, "P:yield": _OPINION, "P:fit": _OPINION,
    "P:reading": _OPINION, "P:case": _OPINION,
    "P:claim": _HEARSAY, "N:aim": _HEARSAY,
    "L:term": {"assumed", "deduced"}, "K:concept": {"assumed", "deduced"},
}
ASSUMED_KINDS = ("L:term", "K:concept")                  # and a C:reliance without stated-in

_LINES_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")
_COMMENT_SOURCE_RE = re.compile(r"#L[0-9]+(?:-L?[0-9]+)?$")
_UP_TO_RE = re.compile(r"\bup to\b(?!\s+(?:" + "|".join(UP_TO_ALLOWED) + r")\b)", re.IGNORECASE)
_DIGIT_RE = re.compile(r"[0-9]")
_ONE_LETTER_RE = re.compile(r"(?<![A-Za-z'’])([B-HJ-Zb-z])(?![A-Za-z'’])")

Add = Callable[..., None]


def _lines(v: Any) -> tuple[int, int] | None:
    """`"12"`, `"12-40"` or 12 -> (lo, hi); None when it is not that shape or lo > hi."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return (v, v) if v >= 1 else None
    mt = _LINES_RE.match(v.strip()) if isinstance(v, str) else None
    if not mt:
        return None
    lo, hi = int(mt.group(1)), int(mt.group(2) or mt.group(1))
    return (lo, hi) if 1 <= lo <= hi else None


def _text(v: Any) -> str:
    """Every string under a value, joined: what a word search reads."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return " ".join(_text(x) for k, x in v.items() if k != "pending")
    if isinstance(v, list):
        return " ".join(_text(x) for x in v)
    return ""


def _strings(v: Any, path: str = "") -> list[tuple[str, str]]:
    """(field path, string) for every string under a value."""
    if isinstance(v, str):
        return [(path, v)]
    if isinstance(v, dict):
        if mc.is_pending(v):
            return []
        return [x for k, sub in v.items() for x in _strings(sub, f"{path}.{k}" if path else str(k))]
    if isinstance(v, list):
        return [x for i, sub in enumerate(v) for x in _strings(sub, f"{path}[{i}]")]
    return []


def _given(v: Any) -> bool:
    """A field holds something: a non-empty value, or an open question (which says what is owed)."""
    if mc.is_pending(v):
        return True
    if isinstance(v, str):
        return bool(v.strip())
    return v is not None and v != [] and v != {}


def _ids(v: Any) -> list[str]:
    """The ids a reference field holds: a string, a list of them, or typed links."""
    out: list[str] = []
    for x in v if isinstance(v, list) else [v]:
        if isinstance(x, dict):
            x = x.get("to") or x.get("id") or x.get("of")
        if isinstance(x, str):
            out.append(x)
    return out


def _has(text: str, word: str) -> bool:
    return re.search(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", text, re.IGNORECASE) is not None


class _Fabulam:
    def __init__(self, vol: mc.Volume, add: Add):
        self.v, self._add = vol, add
        self.cat = vol.catalog if isinstance(vol.catalog, dict) else {}
        self.src = self.cat.get("source") if isinstance(self.cat.get("source"), dict) else {}
        self.items = list(vol.items.values())
        self.by_id = {it.id: it for it in self.items}
        self.head = "parts" in self.cat
        der = self.cat.get("derived") if isinstance(self.cat.get("derived"), dict) else {}
        self.full = der.get("completeness") == "full"

    def add(self, check: str, item: mc.Item | None, msg: str, fld: str | None = None, *,
            severity: str | None = None) -> None:
        self._add(check, item, msg, fld, severity=severity)

    def of(self, module: str, kind: str) -> list[mc.Item]:
        return [it for it in self.items if it.module == module and it.kind == kind]

    def name(self, it: mc.Item) -> str:
        return it.id

    @property
    def statements(self) -> list[mc.Item]:
        return self.of("C", "statement")

    @property
    def lemmas(self) -> list[mc.Item]:
        return self.of("C", "lemma")

    @property
    def stages(self) -> list[mc.Item]:
        return self.of("C", "part")

    def span_lines(self, it: mc.Item) -> tuple[str | None, tuple[int, int] | None]:
        sp = it.data.get("span")
        if not isinstance(sp, dict):
            return None, None
        return (sp.get("file") if isinstance(sp.get("file"), str) else None), _lines(sp.get("lines"))

    def run(self) -> None:
        for check in CHECKS:
            getattr(self, check.replace("-", "_"))()

    # -------------------------------------------------------------- the checks, in the table's order
    def declared_once(self) -> None:
        seen: dict[str, mc.Item] = {}
        for it in self.items:
            if it.module != "C":
                continue
            d = it.data
            if it.kind in DECLARED:
                lean = d.get("lean")
                if not (isinstance(lean, str) and lean.strip()):
                    self.add("declared-once", it, f"{it.id} is a Lean declaration and carries its full name in lean",
                             "lean")
                    continue
                told = d.get("told-in") is not None            # a head's crossing item: its span is the part's
                if not told and (not isinstance(d.get("span"), dict) or self.span_lines(it)[1] is None):
                    self.add("declared-once", it, f"{it.id} carries a span {{file, lines}}: the lines of {lean}",
                             "span")
                if lean in seen:
                    self.add("declared-once", it, f"{it.id} and {seen[lean].id} both carry lean {lean!r}: a "
                                                  "declaration is named exactly once", "lean")
                else:
                    seen[lean] = it
            elif it.kind == "constant" and "lean" in d:
                self.add("declared-once", it, f"{it.id} is a constant the proof fixes, not a declaration: it carries "
                                              "no lean", "lean")
            elif it.kind == "reliance" and not _given(d.get("lean")):
                self.add("declared-once", it, f"{it.id} names the Lean it leans on, as the file writes it, in lean",
                         "lean")

    def statement_whole(self) -> None:
        # Read with the parts (the conductor's ruling on design 2.A against 4.1): a fabulam that stands alone (no
        # head, no parts) holds at least one statement and one for every target; a part holds one for each target
        # declared in its own file and needs none for the others; a head, one for every target.
        sts = self.statements
        part = "head" in self.cat and not self.head
        alone = "head" not in self.cat and not self.head
        if not sts and alone:
            self.add("statement-whole", None, "a fabulam that stands alone holds at least one C:statement: a final "
                                              "theorem of source.target", "nodes")
        targets = self.src.get("target")
        tlist = [t for t in targets if isinstance(t, str)] if isinstance(targets, list) else None
        if tlist is None and not mc.is_pending(targets):
            self.add("statement-whole", None, "source.target lists the full names of the final theorems the "
                                              "fabulam tells", "source.target")
        leans = {}
        for it in sts:
            d = it.data
            lean = d.get("lean")
            leans[lean] = it
            if tlist is not None and isinstance(lean, str) and lean not in tlist:
                self.add("statement-whole", it, f"{it.id} states {lean}, which is not one of source.target", "lean")
            if not _given(d.get("says")):
                self.add("statement-whole", it, f"{it.id} says the statement in full, in words", "says")
            q = d.get("quantifiers")
            if mc.is_pending(q):
                pass
            elif not isinstance(q, list) or not q:
                self.add("statement-whole", it, f"{it.id} lists its quantifiers in order, each {{kind, what}}",
                         "quantifiers")
            else:
                for i, e in enumerate(q):
                    if not (isinstance(e, dict) and e.get("kind") in QUANTIFIER_KINDS and _given(e.get("what"))):
                        self.add("statement-whole", it, f"quantifiers[{i}] is {{kind, what}}, kind one of "
                                                        f"{', '.join(QUANTIFIER_KINDS)}", f"quantifiers[{i}]")
            rel = d.get("relates")
            if rel is not None:
                if len(sts) != 2:
                    self.add("statement-whole", it, "relates is written only when the fabulam has two statements",
                             "relates")
                elif not (isinstance(rel, dict) and rel.get("how") in RELATES_HOW
                          and self.by_id.get(rel.get("to")) in sts and rel.get("to") != it.id):
                    self.add("statement-whole", it, f"relates is {{to: the other statement, how: "
                                                    f"{' | '.join(RELATES_HOW)}, says}}", "relates")
        own = {it.data.get("lean"): it for it in self.items if it.module == "C" and it.kind in DECLARED
               and it.data.get("told-in") is None}
        for t in tlist or []:
            if t in leans:
                continue
            if part and t not in own:
                continue                                  # a target declared in another part's file
            if part:
                self.add("statement-whole", own[t], f"the target {t} is declared in this part's file, so it is a "
                                                    "C:statement here", "type")
            else:
                self.add("statement-whole", None, f"the target {t} has no C:statement", "source.target")
        atem = self.cat.get("atem")
        if isinstance(atem, dict) and not mc.is_pending(atem.get("of")):
            hit = self.by_id.get(atem.get("of"))
            if part and not sts:
                if hit is None or (hit.module, hit.kind) not in (("C", k) for k in DECLARED) \
                        or hit.data.get("told-in") is not None:
                    self.add("statement-whole", None, f"atem.of names one of this part's own declarations, not "
                                                      f"{atem.get('of')!r}", "atem.of")
            elif hit is None or (hit.module, hit.kind) != ("C", "statement"):
                self.add("statement-whole", None, f"atem.of names a C:statement, not {atem.get('of')!r}", "atem.of")

    def _of_each(self, module: str, kind: str) -> dict[str, list[mc.Item]]:
        """The items of a kind, by the statement (or other item) their `of` names."""
        out: dict[str, list[mc.Item]] = {}
        for it in self.of(module, kind):
            for ref in _ids(it.data.get("of")):
                out.setdefault(ref, []).append(it)
        return out

    def yield_stated(self) -> None:
        ys = self.of("P", "yield")
        by = self._of_each("P", "yield")
        need = self.full or bool(ys)
        for st in self.statements:
            n = len(by.get(st.id, []))
            if n > 1 or (n == 0 and need):
                self.add("yield-stated", st, f"{st.id} has exactly one P:yield, not {n}", "of")
        for y in ys:
            d = y.data
            of = self.by_id.get(d.get("of")) if isinstance(d.get("of"), str) else None
            if of is None or (of.module, of.kind) != ("C", "statement"):
                self.add("yield-stated", y, f"{y.id}'s of names a C:statement", "of")
            beyond = d.get("beyond")
            if mc.is_pending(beyond):
                pass
            elif beyond not in ("yes", "no"):
                self.add("yield-stated", y, f"{y.id}'s beyond is the quoted word \"yes\" or \"no\", not {beyond!r}",
                         "beyond")
            elif (beyond == "yes") != ("as-statement" in d):
                self.add("yield-stated", y, f"{y.id} carries as-statement exactly when beyond is \"yes\"",
                         "as-statement")
            for f in ("needs", "chooses"):
                if not mc.is_pending(d.get(f)) and not isinstance(d.get(f), list):
                    self.add("yield-stated", y, f"{y.id}'s {f} is a list ([] when there is none)", f)
            for i, c in enumerate(d.get("chooses") if isinstance(d.get("chooses"), list) else []):
                missing = [k for k in CHOOSES_FIELDS if not (isinstance(c, dict) and _given(c.get(k)))]
                if missing:
                    self.add("yield-stated", y, f"chooses[{i}] is whole: no {', no '.join(missing)}", f"chooses[{i}]")
            triv, none = d.get("trivial"), d.get("no-trivial")
            if mc.is_pending(triv):
                continue
            if isinstance(triv, list) and triv:
                for i, t in enumerate(triv):
                    missing = [k for k in TRIVIAL_FIELDS if not (isinstance(t, dict) and _given(t.get(k)))]
                    if missing:
                        self.add("yield-stated", y, f"trivial[{i}] is whole: no {', no '.join(missing)}",
                                 f"trivial[{i}]")
            elif not (isinstance(none, str) and none.strip()):
                self.add("yield-stated", y, f"{y.id} gives a trivial case, or no-trivial with a sentence saying why "
                                            "none exists", "trivial")

    def fit_stated(self) -> None:
        fits = self.of("P", "fit")
        wording = self.src.get("wording")
        if not wording:
            for f in fits:
                self.add("fit-stated", f, f"{f.id}: a fit is made only when source.wording names a public wording",
                         "of")
            return
        if WORDING_ID not in self.by_id:
            self.add("fit-stated", None, f"source.wording is set, so the fabulam holds {WORDING_ID}",
                     "source.wording")
        by = self._of_each("P", "fit")
        need = self.full or bool(fits)
        for st in self.statements:
            n = len(by.get(st.id, []))
            if n > 1 or (n == 0 and need):
                self.add("fit-stated", st, f"{st.id} has exactly one P:fit against the wording, not {n}", "of")
        for f in fits:
            if f.data.get("against") != WORDING_ID:
                self.add("fit-stated", f, f"{f.id} is against {WORDING_ID}", "against")

    def spine_told(self) -> None:
        lemmas = self.lemmas
        need = self.full or any("role" in it.data for it in lemmas)
        in_steps = {s for st in self.stages for s in _ids(st.data.get("steps"))}
        have_stages = bool(self.stages)
        spine = []
        for it in lemmas:
            d = it.data
            reached = d.get("reached")
            if reached == "yes":
                if "role" not in d and need:
                    self.add("spine-told", it, f"{it.id} is reached by a target, so it has a role: spine, support or "
                                               "bookkeeping", "role")
            elif "role" in d:
                self.add("spine-told", it, f"{it.id} is not reached (reached: {reached!r}), so it has no role",
                         "role")
            if d.get("role") == "spine":
                spine.append(it)
                if not _given(d.get("why")):
                    self.add("spine-told", it, f"{it.id} is spine and says why: what the argument would lack "
                                               "without it", "why")
                if have_stages and it.id not in in_steps:
                    self.add("spine-told", it, f"{it.id} is spine and is in the steps of a stage", "role")
        if spine and self.statements:                   # a part with no target is reached from other parts
            seen: set[str] = set()
            todo = [st.id for st in self.statements]
            while todo:
                cur = todo.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                hit = self.by_id.get(cur)
                if hit is not None:
                    todo.extend(_ids(hit.data.get("uses")))
            for it in spine:
                if it.id not in seen:
                    self.add("spine-told", it, f"{it.id} is spine, yet no chain of uses leads to it from a statement",
                             "uses")

    def stages_whole(self) -> None:
        stages = self.stages
        teaching = self.cat.get("teaching")
        if not stages and not self.full and teaching is None:
            return
        if not stages and self.full and not self.head:
            self.add("stages-whole", None, "a whole fabulam tells its argument in stages (C:part, division: stage)",
                     "nodes")
            return
        nums = []
        for st in stages:
            d = st.data
            if d.get("division") != "stage":
                self.add("stages-whole", st, f"{st.id}: a part of a fabulam is a stage (division: stage)",
                         "division")
            if d.get("stage") not in STAGE_ORDER:
                self.add("stages-whole", st, f"{st.id}'s stage is one of {', '.join(STAGE_ORDER)}", "stage")
            n = d.get("number")
            if isinstance(n, int) and not isinstance(n, bool):
                nums.append(n)
            else:
                self.add("stages-whole", st, f"{st.id}'s number is its place in the logic, a whole number", "number")
            for f in ("plain", "plain-if"):
                if not _given(d.get(f)):
                    self.add("stages-whole", st, f"{st.id} has {f}", f)
        if sorted(nums) != list(range(1, len(nums) + 1)):
            self.add("stages-whole", None, f"the stages' numbers run 1, 2, 3 with no gap and no repeat, not "
                                           f"{sorted(nums)}", "nodes")
        red = [st for st in stages if st.data.get("stage") == "reduction"]
        if len(red) != 1:
            self.add("stages-whole", None, f"exactly one stage is the reduction, not {len(red)}", "nodes")
        for st in red:
            if not _given(st.data.get("obvious")):
                self.add("stages-whole", st, f"{st.id} is the reduction and says the obvious way, and why it fails "
                                             "(or none: the file's way is the obvious one)", "obvious")
        if mc.is_pending(teaching):
            return
        if not isinstance(teaching, list):
            self.add("stages-whole", None, "teaching lists every stage's id once, the reduction first", "teaching")
            return
        ids = [st.id for st in stages]
        if sorted(map(str, teaching)) != sorted(ids) or len(set(map(str, teaching))) != len(teaching):
            self.add("stages-whole", None, "teaching lists every stage once, and nothing else", "teaching")
            return
        ranks = [STAGE_ORDER.index(self.by_id[t].data.get("stage")) if self.by_id[t].data.get("stage")
                 in STAGE_ORDER else 9 for t in teaching]
        if ranks and ranks[0] != 0:
            self.add("stages-whole", None, f"teaching starts with the reduction, not {teaching[0]}", "teaching")
        elif ranks != sorted(ranks):
            self.add("stages-whole", None, "teaching goes reduction, then main, tool, side and close stages, in that "
                                           "order", "teaching")

    def _grounds(self, it: mc.Item, g: Any, fld: str) -> None:
        if mc.is_pending(g):
            return
        if not isinstance(g, list) or not g:
            self.add("grounds-given", it, f"{it.id} has grounds: at least one {{of, lines}}", fld)
            return
        for i, e in enumerate(g):
            if not (isinstance(e, dict) and isinstance(e.get("of"), str) and _lines(e.get("lines")) is not None):
                self.add("grounds-given", it, f"{fld}[{i}] is {{of, lines}}, lines n or n-m", f"{fld}[{i}]")
            elif e["of"] not in self.by_id:
                self.add("grounds-given", it, f"{fld}[{i}].of -> {e['of']} does not exist", f"{fld}[{i}].of")

    def grounds_given(self) -> None:
        for it in self.of("P", "yield") + self.of("P", "reading"):
            self._grounds(it, it.data.get("grounds"), "grounds")
        for it in self.statements + self.lemmas:
            sl = it.data.get("slack")
            if sl is None or mc.is_pending(sl):
                continue
            if not isinstance(sl, list):
                self.add("grounds-given", it, "slack is a list of {hypothesis, would-suffice, lines, confidence}",
                         "slack")
                continue
            for i, e in enumerate(sl):
                if not (isinstance(e, dict) and _lines(e.get("lines")) is not None):
                    self.add("grounds-given", it, f"slack[{i}] gives the lines that show a weaker hypothesis would do",
                             f"slack[{i}].lines")
        for it in self.of("C", "step"):
            inside = self.by_id.get(it.data.get("inside")) if isinstance(it.data.get("inside"), str) else None
            if inside is None or (inside.module, inside.kind) not in (("C", "lemma"), ("C", "statement")):
                self.add("grounds-given", it, f"{it.id}'s inside names the lemma or statement whose proof holds it",
                         "inside")
                continue
            f1, l1 = self.span_lines(it)
            f2, l2 = self.span_lines(inside)
            if l1 is None:
                self.add("grounds-given", it, f"{it.id} has a span {{file, lines}}", "span")
            elif l2 is not None and (f1 != f2 or l1[0] < l2[0] or l1[1] > l2[1]):
                self.add("grounds-given", it, f"{it.id}'s span lies inside the lines of {inside.id}", "span")

    def audit_whole(self) -> None:
        rows = self.cat.get("audit")
        claims = {it.id: it for it in self.of("P", "claim")}
        named: set[str] = set()
        if rows is not None and not mc.is_pending(rows):
            if not isinstance(rows, list):
                self.add("audit-whole", None, "audit is a list of rows {lines, kind, on, verdict, claim}", "audit")
                rows = []
            need = self.full or any(isinstance(r, dict) and "verdict" in r for r in rows)
            for i, r in enumerate(rows):
                fld = f"audit[{i}]"
                if not isinstance(r, dict):
                    self.add("audit-whole", None, f"{fld} is {{lines, kind, on, verdict}}", fld)
                    continue
                if _lines(r.get("lines")) is None:
                    self.add("audit-whole", None, f"{fld}.lines is n or n-m", f"{fld}.lines")
                if r.get("kind") not in AUDIT_KINDS:
                    self.add("audit-whole", None, f"{fld}.kind is one of {', '.join(AUDIT_KINDS)}", f"{fld}.kind")
                verdict = r.get("verdict")
                if verdict is None:
                    if need:
                        self.add("audit-whole", None, f"{fld} has a verdict: {', '.join(AUDIT_VERDICTS)}",
                                 f"{fld}.verdict")
                elif verdict not in AUDIT_VERDICTS:
                    self.add("audit-whole", None, f"{fld}.verdict is one of {', '.join(AUDIT_VERDICTS)}, not "
                                                  f"{verdict!r}", f"{fld}.verdict")
                c = r.get("claim")
                if (verdict == "claim") != (c is not None):
                    self.add("audit-whole", None, f"{fld} says claim exactly when it names a P:claim in claim",
                             f"{fld}.claim")
                elif c is not None:
                    if c not in claims:
                        self.add("audit-whole", None, f"{fld}.claim -> {c} is not a P:claim of this fabulam",
                                 f"{fld}.claim")
                    named.add(str(c))
        elif self.full and not self.head:
            self.add("audit-whole", None, "a whole fabulam has its comment table, audit (one row per comment)",
                     "audit")
        for cid, it in claims.items():
            d = it.data
            prov = d.get("provenance") if isinstance(d.get("provenance"), dict) else {}
            srcs = prov.get("sources") if isinstance(prov.get("sources"), list) else []
            if any(isinstance(s, str) and _COMMENT_SOURCE_RE.search(s) for s in srcs) and cid not in named:
                self.add("audit-whole", it, f"{cid} comes from a comment, and a row of audit names it", "provenance")
            if cid == CHECKING_ID:
                continue
            checked = d.get("checked")
            if mc.is_pending(checked):
                continue
            if checked not in CLAIM_CHECKED:
                self.add("audit-whole", it, f"{cid}'s checked is one of {', '.join(repr(w) for w in CLAIM_CHECKED)}",
                         "checked")
                continue
            for f in CLAIM_CHECKED[checked]:
                if not _given(d.get(f)):
                    self.add("audit-whole", it, f"{cid} is checked {checked!r}, so it carries {f}", f)
            if "mismatch" in CLAIM_CHECKED[checked] and _given(d.get("mismatch")) \
                    and d.get("mismatch") not in MISMATCH and not mc.is_pending(d.get("mismatch")):
                self.add("audit-whole", it, f"{cid}'s mismatch is one of {', '.join(MISMATCH)}", "mismatch")
            if checked == "partial" and d.get("false-as-written") not in ("yes", "no", None) \
                    and not mc.is_pending(d.get("false-as-written")):
                self.add("audit-whole", it, f"{cid}'s false-as-written is \"yes\" or \"no\"", "false-as-written")
            if checked == "yes" and _given(d.get("by")) and not mc.is_pending(d.get("by")) \
                    and not all(r in self.by_id for r in _ids(d.get("by"))):
                self.add("audit-whole", it, f"{cid}'s by names items of this fabulam", "by")

    def stance_fits(self) -> None:
        for it in self.items:
            if it.module == mc.DIALECTIC_MODULE:
                continue
            d = it.data
            stance = d.get("stance")
            if stance is None or mc.is_pending(stance):
                continue
            key = f"{it.module}:{it.kind}"
            if key == "C:reliance":
                allowed = {"deduced"} if d.get("stated-in") is not None else {"assumed", "deduced"}
            elif it.id == CHECKING_ID:
                allowed = {"observed", "hearsay"}
            elif it.module == "R":
                allowed = {"observed", "hearsay", "deduced"}
            elif it.module == "E":
                allowed = _HEARSAY
            else:
                allowed = STANCES.get(key)
            if allowed is not None and stance not in allowed:
                self.add("stance-fits", it, f"{it.id} is {stance}; in a fabulam {_a(key)} is "
                                            f"{' or '.join(sorted(allowed))}", "stance")
            elif allowed is None and stance == "assumed":
                self.add("stance-fits", it, f"{it.id} is assumed; nothing about what this proof does may be "
                                            "assumed (only a reliance without stated-in, a term or a concept)",
                         "stance")
            if stance == "hearsay":
                prov = d.get("provenance") if isinstance(d.get("provenance"), dict) else {}
                if not (isinstance(prov.get("sources"), list) and prov["sources"]):
                    self.add("stance-fits", it, f"{it.id} is hearsay and names its source in provenance.sources",
                             "provenance.sources")
            if key in CONFIDENCE_KINDS and stance == "opinion" and d.get("confidence") not in CONFIDENCE \
                    and not mc.is_pending(d.get("confidence")):
                self.add("stance-fits", it, f"{it.id} is a model's opinion and says its confidence: "
                                            f"{', '.join(CONFIDENCE)}", "confidence")

    def checking_said(self) -> None:
        chk = self.src.get("checking")
        chk = chk if isinstance(chk, dict) else {}
        if chk.get("built-here") != "no":
            self.add("checking-said", None, "source.checking.built-here is the quoted word \"no\": nothing is built "
                                            "here", "source.checking.built-here")
        said, said_by = chk.get("said"), chk.get("said-by")
        if said and not said_by:
            self.add("checking-said", None, "source.checking.said is written only with said-by: who says it",
                     "source.checking.said-by")
        it = self.by_id.get(CHECKING_ID)
        if it is None:
            self.add("checking-said", None, f"the fabulam holds {CHECKING_ID}: what is known about the check, "
                                            "written by rule", "nodes")
            return
        says = it.data.get("says")
        text = says if isinstance(says, str) else ""
        if said and said_by:
            if str(said).strip() not in text:
                self.add("checking-said", it, f"{CHECKING_ID} says what {said_by} says about the check", "says")
            if it.data.get("stance") != "hearsay":
                self.add("checking-said", it, f"{CHECKING_ID} carries a person's entry, so its stance is hearsay",
                         "stance")
        else:
            bad = [w for w in CHECKING_WORDS if _has(text, w)]
            if bad:
                self.add("checking-said", it, f"{CHECKING_ID} holds {', '.join(repr(w) for w in bad)} with nobody "
                                              "saying so: with no entry it says only what the text shows", "says")
            if it.data.get("stance") not in ("observed", None):
                self.add("checking-said", it, f"{CHECKING_ID} with no entry is observed", "stance")

    def example_worked(self) -> None:
        if not (self.full or self.of("P", "yield")):
            return
        yields = self._of_each("P", "yield")
        cases = [c for c in self.of("P", "case") if c.data.get("from") == "worked"]
        for st in self.statements:
            mine = {st.id} | {y.id for y in yields.get(st.id, [])}
            ok = [c for c in cases if set(_ids(c.data.get("of"))) & mine
                  and _DIGIT_RE.search(_text(c.data.get("given"))) and _DIGIT_RE.search(_text(c.data.get("expect")))]
            if not ok:
                self.add("example-worked", st, f"{st.id} has a worked P:case (from: worked) whose given and expect "
                                               "each hold a number", "of")

    def no_up_to(self) -> None:
        for it in self.of("P", "yield"):
            for fld, s in _strings({k: v for k, v in it.data.items() if k not in ("provenance", "span")}):
                if _UP_TO_RE.search(s):
                    self.add("no-up-to", it, f"{it.id}'s {fld} says \"up to\": a delivered bound is at least, at "
                                             "most, exactly or between", fld)
        for it in self.stages:
            for fld, s in _strings(it.data.get("plain"), "plain"):
                if _UP_TO_RE.search(s):
                    self.add("no-up-to", it, f"{it.id}'s plain says \"up to\"", fld)

    def statements_agree(self) -> None:
        crossing = [it for it in self.items if it.module == "C" and it.kind in DECLARED
                    and isinstance(it.data.get("told-in"), str)]
        relying = [it for it in self.of("C", "reliance") if isinstance(it.data.get("stated-in"), str)]
        if not crossing and not relying:
            return
        known = known_fabulams(self.v)
        for it in relying:
            _v, theirs, why = known.item(it.data["stated-in"])
            if theirs is None:
                self.add("statements-agree", it, f"stated-in: {why}", "stated-in")
                continue
            self._agree(it, theirs, it.data["stated-in"], says_field="gives")
        for it in crossing:
            _v, theirs, why = known.item(it.data["told-in"])
            if theirs is None:
                self.add("statements-agree", it, f"told-in: {why}", "told-in")
                continue
            self._agree(it, theirs, it.data["told-in"], says_field="says")

    def _agree(self, it: mc.Item, theirs: dict, uri: str, *, says_field: str) -> None:
        mine = it.data.get("lean")                      # a reliance's lean lists the names the file writes
        same_lean = theirs.get("lean") in mine if isinstance(mine, list) else theirs.get("lean") == mine
        diff = ([] if same_lean else ["lean"]) + (["digest"] if theirs.get("digest") != it.data.get("digest") else [])
        if " ".join(_text(it.data.get(says_field)).split()) != " ".join(_text(theirs.get("says")).split()):
            diff.append(says_field)
        if diff:
            self.add("statements-agree", it, f"{it.id} does not agree with {uri} in its {', '.join(diff)}", diff[0])

    def parts_resolve(self) -> None:
        if "parts" not in self.cat and "head" not in self.cat and not any(
                it.data.get("told-in") is not None for it in self.of("C", "component")):
            return
        from enough import fabulac_head as _head
        for check, item, msg, fld, sev in _head.problems(self.v, known_fabulams(self.v)):
            self.add(check, item, msg, fld, severity=sev if sev == "note" else None)

    def regime_named(self) -> None:
        for it in self.of("P", "yield") + self.of("P", "reading") + self.stages:
            d = it.data
            if "regime" in d:
                continue
            text = _text({k: v for k, v in d.items() if k not in ("provenance", "span", "grounds", "steps")}).lower()
            hit = next((w for w in SIZE_WORDS if (w in text if not w[0].isalpha() else _has(text, w))), None)
            if hit:
                self.add("regime-named", it, f"{it.id} speaks of size ({hit!r}) and names its regime: {{as, "
                                             "uniform-in, fixed, worst-over}", "regime")

    def no_judgement(self) -> None:
        for it in self.of("P", "fit"):
            for fld, s in _strings(it.data.get("differences"), "differences"):
                bad = [w for w in JUDGEMENT_WORDS if _has(s, w)]
                if bad:
                    self.add("no-judgement", it, f"{it.id}'s {fld} holds a word of judgement: {', '.join(bad)}", fld)

    def plain_words(self) -> None:
        for it in self.stages:
            for fld, s in _strings(it.data.get("plain"), "plain"):
                sym = sorted({ch for ch in s if ch in PLAIN_SYMBOLS})
                one = _ONE_LETTER_RE.findall(s)
                if sym or one:
                    what = ([f"the symbols {' '.join(sym)}"] if sym else []) + \
                           ([f"the one-letter names {', '.join(dict.fromkeys(one))}"] if one else [])
                    self.add("plain-words", it, f"{it.id}'s plain holds {' and '.join(what)}", fld)

    def spine_rule_differs(self) -> None:
        reached = [it for it in self.items if it.module == "C" and it.kind in DECLARED
                   and it.data.get("reached") == "yes"]
        n = len(reached)
        for it in self.lemmas:
            d = it.data
            if d.get("reached") != "yes" or d.get("form") not in ("theorem", "lemma", None):
                continue
            depth, carries, role = d.get("depth"), d.get("carries"), d.get("role")
            depth = depth if isinstance(depth, int) and not isinstance(depth, bool) else None
            carries = carries if isinstance(carries, int) and not isinstance(carries, bool) else None
            candidate = depth == 1 or (carries is not None and carries >= 3 and carries * 100 >= 2 * n)
            if candidate and role == "bookkeeping":
                self.add("spine-rule-differs", it, f"{it.id} is one of the rule's candidates (depth {depth}, carries "
                                                   f"{carries}) and was judged bookkeeping: a person should look",
                         "role")
            elif role == "spine" and carries == 0 and depth is not None and depth >= 3:
                self.add("spine-rule-differs", it, f"{it.id} carries nothing at depth {depth} and was judged spine: "
                                                   "a person should look", "role")


def _a(word: str) -> str:
    return ("an " if word.split(":")[-1][:1].lower() in "aeiou" else "a ") + word


def known_fabulams(vol: mc.Volume):
    """The resolver `parts-resolve` and `statements-agree` use for a fabulam: the fabulac's (its folder and three
    above), with every `*.fabulam.cosm` of those folders, and, for a part inside `<name>.fabulam.parts/`, the head
    beside that folder."""
    from enough import fabulac_head as _head
    where = (Path(vol.root) / vol.catalog_file if vol.root is not None else Path(vol.catalog_file)) \
        if vol.catalog_file else None
    if where is None:
        return _head.Fabulacs()
    where = where.absolute()
    known = _head.Fabulacs.near(where)
    folders = [where.parent] + list(where.parent.parents)[:_head.LEVELS_UP]
    for folder in where.parents:
        if folder.name.endswith(PARTS_SUFFIX):
            folders.append(folder.parent)
            known.add_file(folder.parent / (folder.name[: -len(PARTS_SUFFIX)] + SUFFIX))
            break
    parts = vol.catalog.get("parts") if isinstance(vol.catalog, dict) else None
    for p in parts if isinstance(parts, list) else []:
        if isinstance(p, dict) and isinstance(p.get("path"), str):
            known.add_file(where.parent / p["path"])
    for folder in folders:
        try:
            for p in sorted(folder.glob(f"*{SUFFIX}")):
                if p.is_file():
                    known.add_file(p)
        except OSError:
            continue
    return known


def run_checks(volume: mc.Volume, add: Add) -> dict[str, str]:
    """Every check of the table (design 2.A) over one fabulam, each problem through `add`. Returns the checks it
    could not measure, {check: why} (none in this build), as `transconception.run_checks` does."""
    _Fabulam(volume, add).run()
    return {}


__all__ = ["CHECKS", "SEVERITY", "WARNINGS", "CHECKING_ID", "READ_AS_TEXT_ID", "WORDING_ID", "FLAVOUR", "SUFFIX",
           "PARTS_SUFFIX", "known_fabulams", "run_checks"]
