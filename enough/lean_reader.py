"""Lean 4 read as text, by rule: the reader behind a fabulam's survey (design `docs/v090-fabulam-design.md`, section
3; MacroCOSM OES 18.4.10).

Nothing of Lean is installed, imported, built or run. The text is cut into tokens, the tokens into commands, and
each declaration's names are matched to the file's own declarations by spelling. Everything Lean's elaborator would
know and a reader of the text cannot (implicit arguments, coercions, instances found by search, the lemmas `simp`
uses) is left unknown and said so (`limits`, `automation`, `how`, `reached: perhaps`).

Three functions, each answering plain data (strings, integers, booleans, lists, mappings; never a float), so that a
Thym run can record them and a replay needs no reader. A move never calls this module: it asks the syntax engine
(`ctx.engines["syntax"].outline`, `.graph`, `.reach`; `enough.repo_engine`), which hands on to the language's reader
(`enough.languages`, the field `reader`).

- `outline(path, text)`: one file's declarations, comments, imports, opens and the names each declaration uses.
- `graph(outlines)`: the declarations of a set of files and which uses which, across files by their imports.
- `reach(graph, targets)`: from the final theorems down, `reached`, `depth` and `carries` (the size of a
  declaration's subtree in the dominator tree of the reach), and the rule's candidates for the spine.

Standard library only.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

LANGUAGE = "lean"

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

# Lean's own classes of identifier characters (`isLetterLike`, `isSubScriptAlnum`): Greek but λ, Π and Σ; Coptic;
# polytonic Greek; the letterlike block; the mathematical script, double-struck and fraktur letters; subscripts.
_LL = ("α-κμ-ωΑ-ΟΡ΢Τ-Ωϊ-ϻἀ-῾℀-⅏"
       "\U0001d49c-\U0001d59f")
_SUB = "₀-₉ₐ-ₜᵢ-ᵪⱼ"
_ATOM = rf"(?:«[^»\n]*»|[A-Za-z_{_LL}][A-Za-z0-9_'!?{_LL}{_SUB}]*)"
_IDENT = rf"{_ATOM}(?:\.{_ATOM})*"

_TOKEN = re.compile(
    r"(?P<nl>\n)|(?P<ws>[^\S\n]+)|(?P<lc>--)|(?P<bc>/-)"
    r"|(?P<raw>r#*\")"
    rf"|(?P<id>{_IDENT})"
    r"|(?P<str>\")"
    r"|(?P<chr>'(?:\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|.)|[^\\'\n])')"
    r"|(?P<num>0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|[0-9][0-9_]*(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
    rf"|(?P<dot>\.{_IDENT})"
    r"|(?P<proj>\.[0-9]+)"
    r"|(?P<sym>:=|=>|<;>|@\[|\.\.|\S)")
_STR_REST = re.compile(r'(?:[^"\\]|\\.)*"', re.S)
_BLOCK = re.compile(r"/-|-/")
_NAME_LIT = re.compile(rf"``?{_IDENT}")
_SINGLE = re.compile(rf"^[A-Za-z{_LL}][0-9'{_SUB}]*$")

OPENERS = {"(": ")", "[": "]", "{": "}", "⟨": "⟩", "⦃": "⦄", "@[": "]", "‹": "›", "⟦": "⟧", "⌊": "⌋", "⌈": "⌉"}
CLOSERS = set(OPENERS.values())


class Unreadable(ValueError):
    """A text the reader cannot cut into tokens: an unclosed comment or string."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line


class Tok:
    __slots__ = ("kind", "text", "line", "col", "start", "end", "first")

    def __init__(self, kind: str, text: str, line: int, col: int, start: int, end: int, first: bool) -> None:
        self.kind, self.text, self.line, self.col, self.start, self.end, self.first = \
            kind, text, line, col, start, end, first

    def __repr__(self) -> str:                      # pragma: no cover - for a person debugging
        return f"Tok({self.kind}, {self.text!r}, L{self.line}:{self.col})"


def _words(s: str) -> int:
    return len(s.split())


def tokenize(text: str) -> tuple[list[Tok], list[dict], str]:
    """The tokens of a Lean text outside its comments and strings (strings are kept as one `str` token each), the
    comments in order, and the text with every comment blanked to spaces (line feeds kept). Raises `Unreadable`."""
    toks: list[Tok] = []
    comments: list[dict] = []
    blank = list(text) if "/-" in text or "--" in text else None
    n = len(text)
    pos, line, ls = 0, 1, 0
    line_has_tok = False

    def blank_out(a: int, b: int) -> None:
        if blank is not None:
            for k in range(a, b):
                if blank[k] != "\n":
                    blank[k] = " "

    def advance_lines(a: int, b: int) -> None:
        nonlocal line, ls
        c = text.count("\n", a, b)
        if c:
            line += c
            ls = text.rindex("\n", a, b) + 1

    while pos < n:
        m = _TOKEN.match(text, pos)
        if m is None:                                # pragma: no cover - `\S` matches any other character
            raise Unreadable(line, "a character the reader does not know")
        g = m.lastgroup
        if g == "nl":
            line += 1
            ls = pos + 1
            pos += 1
            line_has_tok = False
            continue
        if g == "ws":
            pos = m.end()
            continue
        if g == "lc":
            end = text.find("\n", pos)
            end = n if end < 0 else end
            prev = comments[-1] if comments else None
            if (prev is not None and prev["kind"] == "inline" and prev["_dash"] and prev["end"] == line - 1
                    and prev["_ntok"] == len(toks)):
                prev["end"] = line
                prev["words"] += _words(text[pos + 2:end])
                prev["_stop"] = end
            else:
                comments.append({"kind": "inline", "line": line, "end": line, "on": "",
                                 "words": _words(text[pos + 2:end]), "_dash": True, "_ntok": len(toks),
                                 "_start": pos, "_stop": end, "_trail": line_has_tok})
            blank_out(pos, end)
            pos = end
            continue
        if g == "bc":
            depth, j = 1, pos + 2
            while depth:
                bm = _BLOCK.search(text, j)
                if bm is None:
                    raise Unreadable(line, "a block comment opened here is never closed")
                depth += 1 if bm.group() == "/-" else -1
                j = bm.end()
            head = text[pos:pos + 3]
            if head == "/--" and text[pos:pos + 4] != "/--/":
                kind, inner = "note", text[pos + 3:j - 2]
            elif head == "/-!":
                kind, inner = "module-note", text[pos + 3:j - 2]
            else:
                inner = text[pos + 2:j - 2]
                kind = "header" if not toks and not comments else "inline"
            start_line = line
            advance_lines(pos, j)
            comments.append({"kind": kind, "line": start_line, "end": line, "on": "", "words": _words(inner),
                             "_dash": False, "_ntok": len(toks), "_start": pos, "_stop": j, "_inner": inner,
                             "_trail": line_has_tok})
            blank_out(pos, j)
            pos = j
            continue
        if g in ("str", "raw"):
            start_line = line
            if g == "str":
                sm = _STR_REST.match(text, pos + 1)
                if sm is None:
                    raise Unreadable(line, "a string opened here is never closed")
                j = sm.end()
            else:
                hashes = m.group()[1:-1]
                close = '"' + hashes
                k = text.find(close, m.end())
                if k < 0:
                    raise Unreadable(line, "a raw string opened here is never closed")
                j = k + len(close)
            toks.append(Tok("str", "", start_line, pos - ls, pos, j, not line_has_tok))
            line_has_tok = True
            advance_lines(pos, j)
            pos = j
            continue
        if g == "id":
            word = m.group()
            j = m.end()
            if word.endswith("!") and j < n and text[j] == '"':       # s!"…", m!"…", f!"…": an interpolated string
                start_line = line
                end = _interpolated_end(text, j)
                if end < 0:
                    raise Unreadable(line, "a string opened here is never closed")
                toks.append(Tok("str", "", start_line, pos - ls, pos, end, not line_has_tok))
                line_has_tok = True
                advance_lines(pos, end)
                pos = end
                continue
            toks.append(Tok("id", word, line, pos - ls, pos, j, not line_has_tok))
            line_has_tok = True
            pos = j
            continue
        if g == "sym" and m.group() == "`":
            nm = _NAME_LIT.match(text, pos)
            if nm is not None:                       # a name literal (`Nat.succ): a quoted name, not a use
                toks.append(Tok("str", "", line, pos - ls, pos, nm.end(), not line_has_tok))
                line_has_tok = True
                pos = nm.end()
                continue
        toks.append(Tok(g, m.group(), line, pos - ls, pos, m.end(), not line_has_tok))
        line_has_tok = True
        pos = m.end()
    return toks, comments, ("".join(blank) if blank is not None else text)


def _interpolated_end(text: str, j: int) -> int:
    """Where an interpolated string that opens at `j` (its quote) ends, or -1: `{…}` may hold code and strings."""
    n, k, depth = len(text), j + 1, 0
    while k < n:
        c = text[k]
        if c == "\\":
            k += 2
            continue
        if depth == 0:
            if c == '"':
                return k + 1
            if c == "{":
                depth = 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == '"':
            sm = _STR_REST.match(text, k + 1)
            if sm is None:
                return -1
            k = sm.end()
            continue
        k += 1
    return -1


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

DECL_KINDS = {"theorem": "theorem", "lemma": "lemma", "def": "def", "abbrev": "abbrev", "instance": "instance",
              "structure": "structure", "class": "class", "inductive": "inductive", "opaque": "opaque",
              "axiom": "axiom", "example": "example", "alias": "alias"}
NOTATION_WORDS = {"notation", "notation3", "macro", "syntax", "infix", "infixl", "infixr", "prefix", "postfix",
                  "macro_rules", "elab", "elab_rules", "binder_predicate"}
OTHER_DECL_WORDS = {"irreducible_def", "simproc", "dsimproc", "simproc_decl", "dsimproc_decl"}
MODIFIERS = ("private", "protected", "noncomputable", "unsafe", "partial", "nonrec", "public", "meta")
_PREFIX_WORDS = set(MODIFIERS) | {"local", "scoped"}
_IN_PREFIX = {"open", "set_option", "variable", "include", "omit", "attribute", "unseal", "seal"}
#: Words that may stand at column 0 and still carry on the command above.
_CONTINUE = {"where", "termination_by", "decreasing_by", "deriving", "with", "then", "else", "from", "at", "using",
             "in", "fun", "by", "do", "extends", "calc", "if", "match", "show", "have", "let", "exact"}
KEYWORDS = {
    "fun", "λ", "let", "have", "show", "from", "by", "at", "with", "match", "if", "then", "else", "do", "return",
    "for", "in", "unless", "mut", "calc", "suffices", "obtain", "this", "Type", "Sort", "Prop", "where", "deriving",
    "extends", "namespace", "section", "end", "open", "import", "variable", "universe", "local", "scoped", "private",
    "protected", "noncomputable", "partial", "unsafe", "nonrec", "mutual", "termination_by", "decreasing_by",
    "attribute", "set_option", "sorry", "admit", "haveI", "letI", "nofun", "nomatch", "public", "meta", "module",
    "include", "omit", "rec", "renaming", "hiding", "export", "_", *DECL_KINDS, *NOTATION_WORDS, "macro_rules"}
#: A tactic's name is never a reference: these words inside a `by` block are tactics (or a tactic's own words).
TACTICS = set("""
exact exact? exacts apply apply? refine refine' intro intros rintro rcases obtain cases cases' induction induction'
constructor use use! exists existsi left right exfalso contradiction assumption trivial rfl ac_rfl symm trans
rw rwa rewrite erw rw? nth_rw nth_rewrite simp simp? simp! simp_all simp_all? simpa simpa? simpa! simp_rw dsimp dsimp?
simp_arith norm_num norm_num1 norm_cast push_cast exact_mod_cast apply_mod_cast assumption_mod_cast push_neg
ring ring_nf ring1 noncomm_ring abel abel_nf group field_simp linarith linarith! nlinarith nlinarith! positivity
polyrith linear_combination omega lia decide native_decide aesop aesop? grind grind? tauto itauto fun_prop
continuity measurability gcongr bound mono rel calc conv arg enter lhs rhs ext ext1 funext congr congr! congrm
convert convert_to change show specialize replace generalize subst subst_vars clear revert rename_i next case case'
all_goals any_goals first try repeat repeat' iterate focus on_goal pick_goal swap rotate_left rotate_right skip done
sorry admit classical infer_instance exact? by_cases by_contra by_contra! by_contra' contrapose contrapose! wlog
choose choose! lift set filter_upwards split split_ifs split_ands unfold unfold_let delta norm_num? refine_lift
interval_cases fin_cases decide! nontriviality inhabit borelize zify qify rify push cancel_denoms compute_degree
monicity peel apply_fun apply_rules solve_by_elim exact_rules injection injections constructorm casesm rcases?
haveI letI apply_assumption observe slim_check plausible extract_goal trans field_simp? module algebraize
reduce whnf beta_reduce simp_intro norm_fin aesop_cat tfae_have tfae_finish match_scalars mod_cases
induction_on cases_on simp_wf decreasing_tactic decreasing_trivial gcongr? positivity? fconstructor econstructor
""".split())
TACTIC_WORDS = {"at", "using", "only", "generalizing", "with", "to", "says"}
AUTOMATION = ("simp", "simpa", "aesop", "grind", "omega", "lia", "decide", "norm_num", "linarith", "nlinarith",
              "positivity", "fun_prop", "gcongr", "ring", "field_simp", "tauto", "exact?")
_AUTOMATION_OF = {"simp_all": "simp", "simp_arith": "simp", "dsimp": "simp", "norm_num1": "norm_num",
                  "ring_nf": "ring", "ring1": "ring"}
SORRY_WORDS = {"sorry", "admit", "sorryAx"}
BINDER_SYMS = {"∀", "∃", "∃!", "Π", "Σ", "Σ'", "∑", "∏", "⋃", "⋂", "⨆", "⨅", "∫", "∮", "⨁", "∐", "⋀", "⋁", "∑ᶠ",
               "∏ᶠ"}
HAVE_WORDS = {"have", "haveI", "let", "letI", "set", "obtain", "suffices", "replace"}
INTRO_WORDS = {"intro", "intros", "rintro", "ext", "ext1", "funext", "rename_i", "next", "case", "case'",
               "by_contra", "by_contra!", "by_contra'", "by_cases", "choose", "choose!", "induction'", "cases'",
               "generalize", "peel", "wlog", "inhabit", "intro!"}
#: Attributes a declaration can be used through without being named (design 4.2, rule 1).
PERHAPS_ATTRIBUTES = ("simp", "instance", "aesop", "grind", "ext", "fun_prop", "gcongr", "positivity", "norm_cast",
                      "push_cast", "norm_num")
#: Attributes that make names the text does not show.
UNSHOWN_ATTRIBUTES = {"simps", "mk_iff", "reassoc", "elementwise", "to_app"}


# ---------------------------------------------------------------------------
# The outline
# ---------------------------------------------------------------------------

def _fold(s: str) -> str:
    return " ".join(s.split())


def _matching(toks: list[Tok]) -> list[int]:
    """For each opening bracket, the index of its closer (or the end); -1 elsewhere."""
    out = [-1] * len(toks)
    stack: list[int] = []
    for i, t in enumerate(toks):
        x = t.text
        if t.kind == "sym" and x in OPENERS:
            stack.append(i)
        elif t.kind == "sym" and x in CLOSERS and stack:
            out[stack.pop()] = i
    for i in stack:
        out[i] = len(toks)
    return out


def _qualify(name: str, ns: str) -> str:
    if name.startswith("_root_."):
        return name[len("_root_."):]
    return f"{ns}.{name}" if ns and name else name


def _prefixes(path: str) -> list[str]:
    """`A.B.C` → `[A.B.C, A.B, A]`."""
    parts = path.split(".") if path else []
    return [".".join(parts[:k]) for k in range(len(parts), 0, -1)]


class _Reader:
    """One pass over one file's tokens; `outline()` gives the record."""

    def __init__(self, path: str, text: str) -> None:
        self.path, self.text = path, text
        self.toks, self.comments, self.blank = tokenize(text)
        self.match = _matching(self.toks)
        self.n = len(self.toks)
        self.defs: list[dict] = []
        self.opens: list[dict] = []
        self.namespaces: list[dict] = []
        self.imports: list[dict] = []
        self.limits: list[str] = []
        self.indented: list[int] = []
        self.notation_lines: list[int] = []
        self.unshown: list[str] = []
        self.module_system = False
        self.universes: set[str] = set()
        # the scope stack: each {type, name, path, opens: [records], vars: [{line, end}], bound: set}
        self.stack: list[dict] = [{"type": "file", "name": "", "path": "", "opens": [], "vars": [], "bound": set()}]
        self.pending_in: dict | None = None

    # -- commands ---------------------------------------------------------

    def commands(self) -> list[tuple[int, int]]:
        toks, spans, start, in_mutual = self.toks, [], None, False
        for i, t in enumerate(toks):
            if not t.first:
                continue
            begins = False
            if t.col == 0:
                if t.kind == "id" and (t.text not in _CONTINUE or (t.text == "deriving" and i + 1 < self.n
                                                                   and toks[i + 1].text == "instance")):
                    begins = True
                elif t.kind == "sym" and t.text in ("@[", "#"):
                    begins = True
            elif in_mutual and t.kind in ("id", "sym") and (t.text in DECL_KINDS or t.text in _PREFIX_WORDS
                                                             or t.text in ("@[", "end")):
                begins = True
            elif t.kind == "id" and t.text in DECL_KINDS and t.text not in ("instance",) and not in_mutual:
                self.indented.append(t.line)
            if begins:
                if start is not None:
                    spans.append((start, i))
                start = i
                if t.text == "mutual":
                    in_mutual = True
                elif t.text == "end" and in_mutual:
                    in_mutual = False
        if start is not None:
            spans.append((start, self.n))
        return self._merge_prefixes(spans)

    def _skip_prefix(self, i: int, e: int) -> tuple[int, list[int], list[str]]:
        """Past the attributes and modifiers that open a command: (index, attribute-block starts, modifiers)."""
        toks, attrs, mods = self.toks, [], []
        while i < e:
            x = toks[i].text
            if x == "@[":
                attrs.append(i)
                i = min(self.match[i], e - 1) + 1
            elif toks[i].kind == "id" and x in _PREFIX_WORDS:
                mods.append(x)
                i += 1
                if x == "scoped" and i < e and toks[i].text == "[":
                    i = min(self.match[i], e - 1) + 1
            else:
                break
        return i, attrs, mods

    def _merge_prefixes(self, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        carry: int | None = None
        for s, e in spans:
            i, _a, _m = self._skip_prefix(s, e)
            if i >= e:                               # attributes or modifiers alone: they open the next command
                carry = s if carry is None else carry
                continue
            out.append((carry if carry is not None else s, e))
            carry = None
        if carry is not None:
            out.append((carry, spans[-1][1]))
        return out

    # -- the pass ----------------------------------------------------------

    def run(self) -> None:
        for s, e in self.commands():
            self.command(s, e)
        last = self.toks[-1].line if self.toks else 1
        for entry in self.stack:
            for o in entry["opens"]:
                if o["until"] is None:
                    o["until"] = last
            if entry.get("rec") is not None and entry["rec"]["until"] is None:
                entry["rec"]["until"] = last
        if self.pending_in:
            for o in self.pending_in["opens"]:
                o["until"] = o["line"]
        self.place_all()
        self.mark_comments()
        if self.indented:
            self.limits.append(f"{len(self.indented)} declaration word(s) stand at an indent and were not read as "
                               f"declarations (lines {_lines(self.indented)}).")
        if self.notation_lines:
            self.limits.append(f"The file defines notation, syntax or macros (lines {_lines(self.notation_lines)}); "
                               "they were not expanded.")
        if self.unshown:
            self.limits.append("Some declarations make names the text does not show (" + ", ".join(
                sorted(set(self.unshown))) + ").")

    def ns_path(self) -> str:
        return ".".join(x["name"] for x in self.stack if x["type"] == "namespace")

    def command(self, s: int, e: int) -> None:
        toks = self.toks
        i, attrs, mods = self._skip_prefix(s, e)
        if i >= e:
            return
        kw = toks[i].text
        if kw in _IN_PREFIX:
            k = self._in_at(i + 1, e)
            if k is not None:
                self.prefix_command(i, k, kw)
                if k + 1 < e:
                    self.command(k + 1, e)
                return
        pend, self.pending_in = self.pending_in, None
        if kw == "module" and not self.defs and not self.imports:
            self.module_system = True
            return
        if kw == "import":
            j = i + 1
            all_ = j < e and toks[j].text == "all"
            j += 1 if all_ else 0
            for t in toks[j:e]:
                if t.kind == "id":
                    self.imports.append({"module": t.text, "line": t.line, "public": "public" in mods,
                                         "meta": "meta" in mods, "all": all_})
            return
        if kw == "namespace":
            name = toks[i + 1].text if i + 1 < e and toks[i + 1].kind == "id" else ""
            path = ".".join(p for p in (self.ns_path(), name) if p)
            rec = {"name": path, "line": toks[i].line, "until": None}
            self.namespaces.append(rec)
            self.stack.append({"type": "namespace", "name": name, "opens": [], "vars": [], "bound": set(),
                               "rec": rec})
            return
        if kw == "section":
            self.stack.append({"type": "section", "name": "", "opens": [], "vars": [], "bound": set(), "rec": None})
            return
        if kw == "mutual":
            self.stack.append({"type": "mutual", "name": "", "opens": [], "vars": [], "bound": set(), "rec": None})
            return
        if kw == "end":
            if len(self.stack) > 1:
                top = self.stack.pop()
                line = toks[i].line
                for o in top["opens"]:
                    o["until"] = line
                if top.get("rec") is not None:
                    top["rec"]["until"] = line
            return
        if kw in ("open", "variable", "include", "omit", "universe"):
            self.scope_command(i, e, kw, self.stack[-1])
            return
        kind = DECL_KINDS.get(kw)
        if kw in NOTATION_WORDS:
            kind = "notation"
        elif kw in OTHER_DECL_WORDS:
            kind = "other"
        elif kw == "class" and i + 1 < e and toks[i + 1].text == "inductive":
            kind, i = "inductive", i + 1
        if kind is None:
            if pend:                                   # `open … in` before a command that is no declaration
                for o in pend["opens"]:
                    o["until"] = toks[e - 1].line
            return
        if pend:
            for o in pend["opens"]:
                o["until"] = toks[e - 1].line
        self.declaration(s, i, e, kind, attrs, mods, pend)

    def _in_at(self, i: int, e: int) -> int | None:
        """The index of the `in` that ends an `open … in` (at bracket depth 0), or None."""
        k = i
        while k < e:
            t = self.toks[k]
            if t.kind == "sym" and t.text in OPENERS:
                k = self.match[k] + 1
                continue
            if t.kind == "id" and t.text == "in":
                return k
            k += 1
        return None

    def prefix_command(self, i: int, k: int, kw: str) -> None:
        """`open … in`, `variable … in`, `include … in`, `omit … in`, `set_option … in`: they hold for the next
        command only."""
        if self.pending_in is None:
            self.pending_in = {"type": "in", "opens": [], "vars": [], "bound": set()}
        if kw in ("open", "variable", "include", "omit"):
            self.scope_command(i, k, kw, self.pending_in)

    def scope_command(self, i: int, e: int, kw: str, entry: dict) -> None:
        toks = self.toks
        if kw == "universe":
            self.universes |= {t.text for t in toks[i + 1:e] if t.kind == "id"}
            return
        if kw == "open":
            j, scoped = i + 1, False
            if j < e and toks[j].text == "scoped":
                scoped, j = True, j + 1
            names, hiding, only, renaming = [], [], [], {}
            mode = "names"
            while j < e:
                t = toks[j]
                if t.text == "hiding":
                    mode = "hiding"
                elif t.text == "renaming":
                    mode = "renaming"
                elif t.text == "(" and mode == "names":
                    close = self.match[j]
                    only += [x.text for x in toks[j + 1:close] if x.kind == "id"]
                    j = close
                elif t.kind == "id":
                    if mode == "names":
                        names.append(t.text)
                    elif mode == "hiding":
                        hiding.append(t.text)
                    elif mode == "renaming" and j + 2 < e and toks[j + 1].text in ("→", "->"):
                        renaming[toks[j + 2].text] = t.text
                        j += 2
                j += 1
            rec = {"names": names, "line": toks[i].line, "until": None, "scoped": scoped, "hiding": hiding}
            if only:
                rec["only"] = only
            if renaming:
                rec["renaming"] = renaming
            rec["_ns"] = self.ns_path()
            self.opens.append(rec)
            entry["opens"].append(rec)
            return
        entry["vars"].append({"line": toks[i].line, "end": toks[e - 1].line})
        if kw == "variable":
            entry["bound"].update(self.group_binders(i + 1, e))

    # -- binders -----------------------------------------------------------

    def group_binders(self, a: int, e: int) -> list[str]:
        """The names a run of binder groups binds: `(x y : T)`, `{x}`, `⦃x⦄`, `[inst : C]` (not `[C]`)."""
        toks, out, k = self.toks, [], a
        while k < e:
            t = toks[k]
            if t.kind == "sym" and t.text in OPENERS:
                close = min(self.match[k], e)
                inner = toks[k + 1:close]
                has_colon = any(x.text == ":" for x in inner)
                if t.text in ("[", "@[") and not has_colon:
                    k = close + 1
                    continue
                for x in inner:
                    if x.text in (":", ":="):
                        break
                    if x.kind == "id" and "." not in x.text and x.text not in KEYWORDS:
                        out.append(x.text)
                k = close + 1
                continue
            if t.text in (":", ":=", "where", "|"):
                break
            k += 1
        return out

    def collect(self, k: int, e: int, stops: set[str], *, pattern: bool, eol: bool, cap: int = 80) -> list[str]:
        """The names bound from token `k` on: at depth 0 the names before any other symbol, inside brackets the
        names before a `:` (a `[C]` group binds nothing)."""
        toks, out = self.toks, []
        if k >= e:
            return out
        line0 = toks[k - 1].line if k > 0 else toks[k].line
        depth, colon, live0, steps = 0, [False], True, 0
        while k < e and steps < cap:
            t = toks[k]
            x = t.text
            steps += 1
            if eol and depth == 0 and t.line != line0:
                break
            if depth == 0 and x in stops:
                break
            if t.kind == "sym" and x in OPENERS:
                if x == "[" and not pattern and not any(y.text == ":" for y in toks[k + 1:self.match[k]]):
                    k = self.match[k] + 1
                    if depth == 0:
                        live0 = False
                    continue
                depth += 1
                colon.append(False)
            elif t.kind == "sym" and x in CLOSERS:
                if depth == 0:
                    break
                depth -= 1
                colon.pop()
            elif x in (":", ":="):
                colon[-1] = True
            elif x in (",", "|") and depth > 0:
                colon[-1] = False
            elif t.kind == "id":
                if x in KEYWORDS:
                    if depth == 0:
                        live0 = False
                elif not colon[-1] and (depth > 0 or live0) and "." not in x:
                    out.append(x)
            elif depth == 0 and not (pattern and x in ("|", "-", "@", "⟨")):
                live0 = False
            k += 1
        return out

    # -- a declaration -----------------------------------------------------

    def declaration(self, s: int, i: int, e: int, kind: str, attrs: list[int], mods: list[str],
                    pend: dict | None) -> None:
        toks = self.toks
        kw_tok = toks[i]
        j = i + 1
        name = ""
        generates: list[str] = []
        unknown = False
        ns = self.ns_path()
        if kind == "instance" and j < e and toks[j].text == "(":
            j = self.match[j] + 1
        if kind in ("notation", "example"):
            if kind == "notation":
                self.notation_lines.append(kw_tok.line)
        elif kind == "alias" and j < e and toks[j].text == "⟨":
            close = self.match[j]
            generates += [_qualify(t.text, ns) for t in toks[j + 1:close] if t.kind == "id"]
            j = close + 1
        elif j < e and toks[j].kind == "id" and toks[j].text not in KEYWORDS:
            name = toks[j].text
            j += 1
        name_end = toks[j - 1].end if name else kw_tok.end
        qual = _qualify(name, ns) if name else ""
        # where the statement ends
        stop, k = None, j
        while k < e:
            t = toks[k]
            x = t.text
            if t.kind == "sym" and x in OPENERS:
                k = self.match[k] + 1
                continue
            if x == ":=" or (t.kind == "id" and x in ("where", "deriving")) \
                    or (x == "|" and (t.first or kind == "inductive")) or (kind == "notation" and x == "=>"):
                stop = k
                break
            k += 1
        sig_end = toks[stop].start if stop is not None else toks[e - 1].end
        signature = _fold(self.blank[name_end if name else kw_tok.end:sig_end])
        if name:
            signature = _fold(name + " " + signature)
        body = None
        body_a = e
        if stop is not None and toks[stop].text != "deriving":
            body_a = stop + 1 if toks[stop].text in (":=", "=>") else stop
            if body_a < e:
                body = {"line": toks[body_a].line, "end": toks[e - 1].line}
        proof = "none" if body is None else ("tactic" if toks[body_a].text == "by" else "term")
        # attributes
        attributes: list[str] = []
        for a in attrs:
            names, gen, unk = self.attribute_block(a, ns)
            attributes += names
            generates += gen
            unknown = unknown or unk
        if any(t.text == "deriving" for t in toks[j:e]):
            unknown = True
        if set(attributes) & UNSHOWN_ATTRIBUTES or ("ext" in attributes and kind in ("structure", "class")):
            unknown = True
        # the scope that holds here
        scope: list[dict] = []
        bound: set[str] = set(self.universes)
        opens_here: list[dict] = []
        for entry in self.stack + ([pend] if pend else []):
            scope += entry["vars"]
            bound |= entry["bound"]
            opens_here += entry["opens"]
        # binders of the statement, and of the body
        sig_colon = k_colon = j
        while k_colon < (stop if stop is not None else e):
            t = toks[k_colon]
            if t.kind == "sym" and t.text in OPENERS:
                k_colon = self.match[k_colon] + 1
                continue
            if t.text == ":":
                break
            k_colon += 1
        sig_colon = k_colon
        bound.update(self.group_binders(j, sig_colon))
        skip: set[int] = set()
        if kind == "alias":
            pass
        elif kind in ("structure", "class") and stop is not None and toks[stop].text == "where":
            fields, ctor = self.structure_fields(stop, e, skip)
            bound.update(fields)
            generates += [f"{qual}.{f}" for f in fields] + [f"{qual}.{ctor or 'mk'}"]
            for p in self.parents(j, stop):
                generates.append(f"{qual}.to{p}")
        elif kind in ("structure", "class"):
            generates.append(f"{qual}.mk")
        elif kind == "inductive" and stop is not None:
            for kk in range(stop, e):
                t = toks[kk]
                if t.text == "|" and kk + 1 < e and toks[kk + 1].kind == "id":
                    generates.append(f"{qual}.{toks[kk + 1].text}")
                    skip.add(kk + 1)
                    bound.update(self.collect(kk + 2, e, {":", "|", ":="}, pattern=False, eol=False))
        elif stop is not None and toks[stop].text == "where" and kind in ("def", "instance", "abbrev", "other",
                                                                          "theorem", "lemma"):
            self.where_fields(stop, e, skip, bound)
        if kind not in ("structure", "class", "inductive"):
            aux = self.where_aux(body_a, e, skip, bound)
            generates += [f"{qual}.{a}" for a in aux] if qual else []
        if kind == "notation" and stop is not None:
            bound.update(t.text for t in toks[j:stop] if t.kind == "id")
        self.body_binders(j, e, bound, kind)
        raw, auto = self.refs(j, e, bound, skip, body_a)
        nsorry = sum(1 for t in toks[body_a:e] if t.kind == "id" and t.text in SORRY_WORDS)
        rec: dict[str, Any] = {
            "kind": kind, "name": name, "qual": qual, "line": toks[s].line, "end": toks[e - 1].line,
            "signature": signature, "digest": hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16],
            "body": body, "proof": proof}
        note = self.note_of(s)
        if note is not None:
            rec["note"] = {"line": note["line"], "end": note["end"]}
            note["on"] = qual
            note["_over"] = True
        rec.update({"attributes": attributes, "modifiers": [m for m in mods if m in MODIFIERS], "scope": scope,
                    "sorry": nsorry, "automation": auto, "generates": generates})
        if unknown:
            rec["generates-unknown"] = True
            self.unshown.append(qual or kind)
        rec["refs"] = raw
        rec["_ns"] = ns
        rec["_opens"] = opens_here
        rec["_start"] = toks[s].start
        self.defs.append(rec)

    def attribute_block(self, a: int, ns: str) -> tuple[list[str], list[str], bool]:
        """The attribute names of one `@[…]`, the names a named `to_additive` makes, and whether one makes names the
        text does not show."""
        toks, close = self.toks, self.match[a]
        names, gen, unknown = [], [], False
        entry: list[Tok] = []
        k = a + 1
        entries: list[list[Tok]] = []
        while k < close:
            t = toks[k]
            if t.kind == "sym" and t.text in OPENERS:
                entry.append(t)
                inner_close = self.match[k]
                entry.append(toks[inner_close] if inner_close < len(toks) else t)
                k = inner_close + 1
                continue
            if t.text == ",":
                entries.append(entry)
                entry = []
            else:
                entry.append(t)
            k += 1
        entries.append(entry)
        for ent in entries:
            ids = [t for t in ent if t.kind == "id" and t.text not in ("local", "scoped")]
            if not ids:
                continue
            head = ids[0].text
            names.append(head)
            if head in ("to_additive", "to_dual", "to_additive?"):
                rest = [t for t in ids[1:]]
                if rest and rest[0].text == "existing":
                    continue
                if rest:
                    gen.append(_qualify(rest[0].text, ns))
                else:
                    unknown = True
        return names, gen, unknown

    def note_of(self, s: int) -> dict | None:
        got = None
        for c in self.comments:
            if c["_ntok"] == s and c["kind"] == "note":
                got = c
            elif c["_ntok"] > s:
                break
        return got

    def structure_fields(self, where: int, e: int, skip: set[int]) -> tuple[list[str], str | None]:
        toks, fields, ctor = self.toks, [], None
        k = where + 1
        while k < e:
            t = toks[k]
            if t.first and t.kind == "id" and t.text not in KEYWORDS | {"protected", "private"} or (
                    t.first and t.text in ("protected", "private") and k + 1 < e):
                kk = k
                while kk < e and toks[kk].text in ("protected", "private"):
                    kk += 1
                if kk + 2 < e and toks[kk + 1].text == ":" and toks[kk + 2].text == ":" and toks[kk + 1].end == \
                        toks[kk + 2].start:
                    ctor = toks[kk].text
                    skip.add(kk)
                    k = kk + 3
                    continue
                while kk < e and toks[kk].kind == "id" and toks[kk].line == t.line and toks[kk].text not in KEYWORDS:
                    fields.append(toks[kk].text)
                    skip.add(kk)
                    kk += 1
                k = kk
                continue
            if t.first and t.text == "(":
                close = self.match[k]
                for x in toks[k + 1:close]:
                    if x.text == ":":
                        break
                    if x.kind == "id":
                        fields.append(x.text)
                        skip.add(toks.index(x, k, close))
                k = close + 1
                continue
            k += 1
        return fields, ctor

    def parents(self, j: int, stop: int) -> list[str]:
        toks = self.toks
        out = []
        for k in range(j, stop):
            if toks[k].text == "extends":
                depth = 0
                head = True
                for t in toks[k + 1:stop]:
                    if t.kind == "sym" and t.text in OPENERS:
                        depth += 1
                    elif t.kind == "sym" and t.text in CLOSERS:
                        depth -= 1
                    elif depth == 0 and t.text == ",":
                        head = True
                    elif depth == 0 and head and t.kind == "id":
                        out.append(t.text.rsplit(".", 1)[-1])
                        head = False
                break
        return out

    def where_fields(self, where: int, e: int, skip: set[int], bound: set[str]) -> None:
        """`def … where` / `instance … where`: each line's first name is a field set, not a use."""
        toks = self.toks
        for k in range(where + 1, e):
            t = toks[k]
            if t.first and t.kind == "id" and t.text not in KEYWORDS:
                skip.add(k)
                bound.update(self.collect(k + 1, e, {":=", "|"}, pattern=True, eol=True))

    def where_aux(self, a: int, e: int, skip: set[int], bound: set[str]) -> list[str]:
        """A body's `where` after `:=`: the auxiliary declarations it makes (`foo.go`)."""
        toks, out = self.toks, []
        k = a
        depth = 0
        where = None
        while k < e:
            t = toks[k]
            if t.kind == "sym" and t.text in OPENERS:
                k = self.match[k] + 1
                continue
            if t.kind == "id" and t.text == "where":
                where = k
                break
            k += 1
        if where is None:
            return out
        col = None
        for k in range(where + 1, e):
            t = toks[k]
            if not t.first:
                continue
            if col is None and t.kind == "id":
                col = t.col
            if t.col == col and t.kind == "id" and t.text not in KEYWORDS:
                out.append(t.text)
                skip.add(k)
                bound.update(self.group_binders(k + 1, e))
        del depth
        return out

    def body_binders(self, a: int, e: int, bound: set[str], kind: str) -> None:
        toks = self.toks
        for k in range(a, e):
            t = toks[k]
            x = t.text
            if t.kind == "id":
                if x in ("fun",):
                    if k + 1 < e and toks[k + 1].text != "|":
                        bound.update(self.collect(k + 1, e, {"=>", "↦"}, pattern=True, eol=False))
                elif x in HAVE_WORDS:
                    bound.update(self.collect(k + 1, e, {":=", ":", "from", "by", ",", "=>", "with", "|"} - (
                        {"|"} if x == "obtain" else set()), pattern=True, eol=True))
                elif x == "with":
                    bound.update(self.collect(k + 1, e, {"=>", ":=", ";", "<;>"}, pattern=True, eol=True))
                elif x in INTRO_WORDS:
                    bound.update(self.collect(k + 1, e, {":", ":=", "using", "at", "with", ";", "<;>", "=>", "to"},
                                              pattern=True, eol=True))
                elif x in ("rcases", "obtain", "rintro", "cases", "induction", "match"):
                    pass
            elif t.kind == "sym":
                if x == "λ":
                    if k + 1 < e and toks[k + 1].text != "|":
                        bound.update(self.collect(k + 1, e, {"=>", "↦", ","}, pattern=True, eol=False))
                elif x in BINDER_SYMS or (x in ("∀", "∃") and False):
                    kk = k + 1
                    while kk < e and toks[kk].kind == "sym" and toks[kk].text in ("ᶠ", "!", "'", "ˢ") and \
                            toks[kk].start == toks[kk - 1].end:
                        kk += 1
                    bound.update(self.collect(kk, e, {","}, pattern=False, eol=False))
                elif x == "|" and kind not in ("inductive",):
                    if t.first or (k > 0 and toks[k - 1].text in ("with", "fun", "λ")):
                        kk = k + 1
                        while kk < e and toks[kk].line == t.line and toks[kk].text != "=>":
                            kk += 1
                        if kk < e and toks[kk].text == "=>":
                            bound.update(self.collect(k + 1, e, {"=>"}, pattern=True, eol=True))
                elif x == "{" and kind not in ("structure", "class"):
                    close = self.match[k]
                    bar = None
                    kk, depth = k + 1, 0
                    while kk < close:
                        y = toks[kk]
                        if y.kind == "sym" and y.text in OPENERS:
                            kk = self.match[kk] + 1
                            continue
                        if y.text == "|" or (y.text == "/" and kk + 1 < close and toks[kk + 1].text == "/"):
                            bar = kk
                            break
                        kk += 1
                    if bar is not None:
                        bound.update(self.collect(k + 1, bar, {"|"}, pattern=False, eol=False))

    def refs(self, a: int, e: int, bound: set[str], skip: set[int], body_a: int) -> tuple[list[dict], list[str]]:
        """The names a declaration uses, by spelling (first use of each), and the automation its body calls."""
        toks = self.toks
        seen: dict[tuple[str, bool], dict] = {}
        auto: list[str] = []
        depth = 0
        by_stack: list[int] = []
        for k in range(a, e):
            t = toks[k]
            x = t.text
            if t.kind == "sym":
                if x in OPENERS:
                    depth += 1
                elif x in CLOSERS:
                    depth -= 1
                    while by_stack and by_stack[-1] > depth:
                        by_stack.pop()
                elif x == "," and by_stack and by_stack[-1] == depth and depth > 0:
                    by_stack.pop()
                continue
            if t.kind == "dot":
                nm = x[1:].split(".", 1)[0]
                if (nm, True) not in seen:
                    seen[(nm, True)] = {"name": nm, "line": t.line, "dot": True}
                continue
            if t.kind != "id":
                continue
            if x == "by":
                by_stack.append(depth)
                continue
            if k >= body_a:
                if x in SORRY_WORDS:
                    continue
                base = x if x == "exact?" else x.rstrip("!?")
                base = _AUTOMATION_OF.get(base, base)
                if base in AUTOMATION and base not in auto:
                    auto.append(base)
            if x in KEYWORDS or x == "_" or k in skip:
                continue
            if by_stack and (x in TACTICS or x in TACTIC_WORDS):
                continue
            if k + 1 < e and toks[k + 1].text == ":=":
                continue
            if k > 0 and toks[k - 1].text == "?" and toks[k - 1].end == t.start:
                continue
            parts = x.split(".")
            if parts[0] in bound:
                if len(parts) > 1:
                    nm = parts[1]
                    if (nm, True) not in seen:
                        seen[(nm, True)] = {"name": nm, "line": t.line, "dot": True}
                continue
            if len(parts) == 1 and _SINGLE.match(x):
                continue
            if (x, False) not in seen:
                seen[(x, False)] = {"name": x, "line": t.line, "dot": False}
        auto.sort(key=AUTOMATION.index)
        return list(seen.values()), auto

    # -- placing names -----------------------------------------------------

    def place_all(self) -> None:
        table, last = _tables(self.defs)
        for d in self.defs:
            out = []
            for r in d["refs"]:
                how, to, cands = place(r["name"], r["dot"], r["line"], d["qual"], d["_ns"],
                                       [o for o in self.opens if _holds(o, r["line"])], table, last)
                row: dict[str, Any] = {"name": r["name"], "line": r["line"], "to": to, "how": how}
                if cands:
                    row["candidates"] = cands
                if r["dot"]:
                    row["dot"] = True
                out.append(row)
            d["refs"] = out

    def mark_comments(self) -> None:
        for c in self.comments:
            if c["kind"] in ("header", "module-note") or c.get("_over"):
                continue
            for d in self.defs:
                if d["_start"] < c["_start"] and d["line"] <= c["line"] <= d["end"]:
                    c["on"] = d["qual"]
                    break

    def outline(self) -> dict:
        self.run()
        doc = ""
        for c in self.comments:
            if c["kind"] == "module-note":
                for ln in c["_inner"].splitlines():
                    s = ln.strip().lstrip("#").strip()
                    if s:
                        doc = s
                        break
                break
        defs = []
        for d in self.defs:
            defs.append({k: v for k, v in d.items() if not k.startswith("_")})
        lines = 0 if not self.text else self.text.count("\n") + (0 if self.text.endswith("\n") else 1)
        sorry = sum(1 for t in self.toks if t.kind == "id" and t.text in SORRY_WORDS)
        native = sum(1 for k, t in enumerate(self.toks) if t.kind == "id" and (
            t.text == "native_decide" or (t.text == "decide" and k + 2 < self.n and self.toks[k + 1].text == "+"
                                          and self.toks[k + 2].text == "native")))
        opens = [{k: v for k, v in o.items() if not k.startswith("_")} for o in self.opens]
        for o, src in zip(opens, self.opens):
            o["ns"] = src["_ns"]
        out: dict[str, Any] = {
            "ok": True, "language": LANGUAGE, "lines": lines, "module-system": self.module_system, "doc": doc,
            "imports": self.imports, "opens": opens, "namespaces": self.namespaces, "defs": defs,
            "comments": [{k: v for k, v in c.items() if not k.startswith("_")} for c in self.comments],
            "sorry": sorry, "axioms": [d["qual"] for d in self.defs if d["kind"] == "axiom"],
            "native-decide": native, "limits": self.limits}
        return out


def _lines(xs: list[int]) -> str:
    xs = sorted(set(xs))
    shown = ", ".join(str(x) for x in xs[:8])
    return shown + (f" and {len(xs) - 8} more" if len(xs) > 8 else "")


def _holds(o: dict, line: int) -> bool:
    until = o.get("until")
    return o["line"] <= line <= (until if until is not None else line)


def _tables(defs: list[dict]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """`{full name: the declaration's qual}` (a generated name maps to its maker) and `{last name: [quals]}`."""
    table: dict[str, str] = {}
    last: dict[str, list[str]] = {}
    for d in defs:
        q = d["qual"]
        if not q:
            continue
        for full in [q, *(d.get("generates") or [])]:
            table.setdefault(full, q)
            tail = full.rsplit(".", 1)[-1]
            lst = last.setdefault(tail, [])
            if q not in lst:
                lst.append(q)
    return table, last


def _namespaces_of(qual: str, ns: str) -> list[str]:
    out: list[str] = []
    for p in ([qual] if qual else []) + _prefixes(qual.rsplit(".", 1)[0] if "." in qual else "") + _prefixes(ns):
        if p and p not in out:
            out.append(p)
    return out


def _place_full(n: str, qual: str, ns: str, opens: list[dict], table: dict[str, str]) -> tuple | None:
    if n.startswith("_root_."):
        m = n[len("_root_."):]
        return ("exact", table[m], None) if m in table else None
    if n in table:
        return "exact", table[n], None
    for p in _namespaces_of(qual, ns):
        q = f"{p}.{n}"
        if q in table:
            return "namespace", table[q], None
    hits: list[str] = []
    head = n.split(".", 1)[0]
    for o in opens:
        if o.get("scoped"):
            continue
        if head in (o.get("hiding") or []):
            continue
        only = o.get("only")
        nn = n
        ren = o.get("renaming") or {}
        if ren:
            if head not in ren:
                continue
            nn = ren[head] + n[len(head):]
        elif only is not None and head not in only:
            continue
        for name in o.get("names") or []:
            for base in [name] + [f"{p}.{name}" for p in _prefixes(o.get("ns") or o.get("_ns") or "")]:
                q = f"{base}.{nn}"
                if q in table and table[q] not in hits:
                    hits.append(table[q])
    if len(hits) == 1:
        return "open", hits[0], None
    if len(hits) > 1:
        return "ambiguous", None, sorted(hits)
    return None


def place(name: str, dot: bool, line: int, qual: str, ns: str, opens: list[dict], table: dict[str, str],
          last: dict[str, list[str]]) -> tuple[str, str | None, list[str] | None]:
    """Where a name used at `line` inside the declaration `qual` (in namespace `ns`, under `opens`) points:
    `(how, to, candidates)` by the steps of design 3.1: `exact`, `namespace`, `open`, `last-name`, else `outside`,
    or `ambiguous` with its candidates."""
    del line
    if dot:
        c = sorted(set(last.get(name) or []))
        if len(c) == 1:
            return "last-name", c[0], None
        if len(c) > 1:
            return "ambiguous", None, c
        return "outside", None, None
    got = _place_full(name, qual, ns, opens, table)
    if got is None and "." in name:
        parts = name.split(".")
        for k in range(len(parts) - 1, 0, -1):         # `foo.symm`: the name is `foo`, the rest a field of it
            got = _place_full(".".join(parts[:k]), qual, ns, opens, table)
            if got is not None:
                break
    if got is None:
        return "outside", None, None
    return got


def outline(path: str, text: str) -> dict:
    """A Lean 4 file's outline, read as text (never built): `{ok: true, language: "lean", lines, module-system, doc,
    imports, opens, namespaces, defs, comments, sorry, axioms, native-decide, limits}` (design 3.1). A text the
    reader cannot cut into tokens (an unclosed comment or string) gives `{ok: false, line, message}`."""
    try:
        r = _Reader(str(path), text)
    except Unreadable as e:
        return {"ok": False, "language": LANGUAGE, "line": int(e.line), "message": str(e)}
    return r.outline()


# ---------------------------------------------------------------------------
# Targets by rule (design 1.1)
# ---------------------------------------------------------------------------

def default_targets(ol: dict) -> list[str]:
    """The targets by rule of one outline: every `theorem` or `lemma` that is not `private`, not deprecated, and
    that no other declaration of the file names (an `alias` of it aside)."""
    if not isinstance(ol, dict) or not ol.get("ok"):
        return []
    named: set[str] = set()
    for d in ol.get("defs") or []:
        if d.get("kind") == "alias":
            continue
        for r in d.get("refs") or []:
            for q in [r.get("to")] + list(r.get("candidates") or []):
                if q and q != d.get("qual"):
                    named.add(q)
    out = []
    for d in ol.get("defs") or []:
        if d.get("kind") not in ("theorem", "lemma") or not d.get("qual"):
            continue
        if "private" in (d.get("modifiers") or []) or "deprecated" in (d.get("attributes") or []):
            continue
        if d["qual"] in named:
            continue
        out.append(d["qual"])
    return out


# ---------------------------------------------------------------------------
# The graph of a set of files
# ---------------------------------------------------------------------------

def _module_of(path: str) -> str:
    p = str(path)
    return p[:-5].replace("/", ".") if p.endswith(".lean") else p.replace("/", ".")


def _file_of(module: str, paths: list[str]) -> str | None:
    want = module.replace(".", "/") + ".lean"
    for p in paths:
        if p == want or p.endswith("/" + want):
            return p
    return None


def graph(outlines: dict) -> dict:
    """The declarations of a set of Lean files and which uses which (design 3.2): `{ok, language, decls, uses,
    used-by, outside, order, files}`. `decls` maps each full name to `{file, line, kind, attributes, modifiers}` (a
    declaration with no name is keyed `<file>#L<line>`, a second declaration of one name `<file>#<name>`); `uses`
    holds, for each, the declarations it names, in its own file and in the files of the set it imports (directly
    or not), placed by the steps of `place`; `outside` the names it uses that none of them declares; `order` the
    files, each after the files it imports."""
    paths = sorted(str(p) for p, o in (outlines or {}).items() if isinstance(o, dict) and o.get("ok"))
    imports: dict[str, list[str]] = {}
    for p in paths:
        got = []
        for im in outlines[p].get("imports") or []:
            f = _file_of(str(im.get("module") or ""), paths)
            if f and f != p and f not in got:
                got.append(f)
        imports[p] = got
    # the order: every file after what it imports
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(p: str) -> None:
        stack = [(p, iter(imports[p]))]
        state[p] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                state[node] = 2
                order.append(node)
            elif state.get(nxt, 0) == 0:
                state[nxt] = 1
                stack.append((nxt, iter(imports[nxt])))

    for p in paths:
        if state.get(p, 0) == 0:
            visit(p)
    closure: dict[str, list[str]] = {}
    for p in order:
        seen: list[str] = []
        for q in imports[p]:
            for x in [q, *closure.get(q, [])]:
                if x not in seen:
                    seen.append(x)
        closure[p] = seen
    decls: dict[str, dict] = {}
    keys: dict[str, dict[str, str]] = {}           # path → {qual: key}
    tables: dict[str, tuple[dict, dict]] = {}
    for p in order:
        keys[p] = {}
        for d in outlines[p].get("defs") or []:
            q = d.get("qual") or ""
            key = q if q and q not in decls else (f"{p}#{q}" if q else f"{p}#L{d.get('line')}")
            if q and q in keys[p]:
                key = f"{p}#{q}#L{d.get('line')}"
            decls[key] = {"file": p, "line": int(d.get("line") or 0), "kind": d.get("kind"),
                          "attributes": list(d.get("attributes") or []), "modifiers": list(d.get("modifiers") or [])}
            if q:
                keys[p].setdefault(q, key)
        tables[p] = _tables(outlines[p].get("defs") or [])
    uses: dict[str, list[str]] = {}
    outside: dict[str, list[str]] = {}
    for p in order:
        ol = outlines[p]
        # the names of the files this one imports, in the set
        ctab: dict[str, str] = {}
        clast: dict[str, list[str]] = {}
        owner: dict[str, str] = {}                 # a qual of another file → that file
        for f in closure[p]:
            t, l_ = tables[f]
            for k, v in t.items():
                if k not in ctab:
                    ctab[k] = v
                    owner.setdefault(v, f)
            for k, vs in l_.items():
                lst = clast.setdefault(k, [])
                for v in vs:
                    if v not in lst:
                        lst.append(v)
                    owner.setdefault(v, f)
        ns_recs = ol.get("namespaces") or []
        opens = ol.get("opens") or []
        for d in ol.get("defs") or []:
            q = d.get("qual") or ""
            key = keys[p].get(q) if q else f"{p}#L{d.get('line')}"
            if key is None:
                continue
            got: list[str] = []
            out: list[str] = []
            for r in d.get("refs") or []:
                tos = [r["to"]] if r.get("to") else list(r.get("candidates") or [])
                if tos:
                    for t in tos:
                        k2 = keys[p].get(t)
                        if k2 and k2 != key and k2 not in got:
                            got.append(k2)
                    continue
                if closure[p]:
                    ns = _ns_at(ns_recs, int(r.get("line") or 0))
                    how, to, cands = place(str(r["name"]), bool(r.get("dot")), int(r.get("line") or 0), q, ns,
                                           [o for o in opens if _holds(o, int(r.get("line") or 0))], ctab, clast)
                    placed = [to] if to else list(cands or [])
                    if placed:
                        for t in placed:
                            f = owner.get(t)
                            k2 = keys.get(f, {}).get(t) if f else None
                            if k2 and k2 not in got:
                                got.append(k2)
                        continue
                if r["name"] not in out:
                    out.append(str(r["name"]))
            uses[key] = got
            if out:
                outside[key] = sorted(out)
    used_by: dict[str, list[str]] = {k: [] for k in decls}
    for k, vs in uses.items():
        for v in vs:
            used_by.setdefault(v, []).append(k)
    for k in decls:
        uses.setdefault(k, [])
    files = {p: {"module": _module_of(p), "imports": imports[p], "declarations": sum(
        1 for d in decls.values() if d["file"] == p)} for p in order}
    return {"ok": True, "language": LANGUAGE, "decls": decls, "uses": uses, "used-by": used_by, "outside": outside,
            "order": order, "files": files,
            "targets-by-rule": {p: default_targets(outlines[p]) for p in order}}


def _ns_at(recs: list[dict], line: int) -> str:
    best = ""
    for r in recs:
        until = r.get("until")
        if int(r.get("line") or 0) <= line <= (until if until is not None else line) and len(r["name"]) >= len(best):
            best = r["name"]
    return best


# ---------------------------------------------------------------------------
# The reach (design 4.2)
# ---------------------------------------------------------------------------

def _dominators(nodes: list[str], succ: dict[str, list[str]], root: str) -> dict[str, str]:
    """Immediate dominators over the nodes reachable from `root` (Cooper, Harvey and Kennedy's iteration)."""
    order: list[str] = []
    seen = {root}
    stack = [(root, iter(succ.get(root, [])))]
    while stack:
        node, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            stack.pop()
            order.append(node)
        elif nxt not in seen:
            seen.add(nxt)
            stack.append((nxt, iter(succ.get(nxt, []))))
    rpo = list(reversed(order))
    index = {v: i for i, v in enumerate(rpo)}
    preds: dict[str, list[str]] = {v: [] for v in rpo}
    for u in rpo:
        for v in succ.get(u, []):
            if v in index:
                preds[v].append(u)
    idom: dict[str, str] = {root: root}

    def intersect(a: str, b: str) -> str:
        while a != b:
            while index[a] > index[b]:
                a = idom[a]
            while index[b] > index[a]:
                b = idom[b]
        return a

    changed = True
    while changed:
        changed = False
        for v in rpo[1:]:
            ps = [p for p in preds[v] if p in idom]
            if not ps:
                continue
            new = ps[0]
            for p in ps[1:]:
                new = intersect(p, new)
            if idom.get(v) != new:
                idom[v] = new
                changed = True
    del nodes
    return idom


ROOT = "\u0000root"


def reach(g: dict, targets: Any = None) -> dict:
    """From the targets down (design 4.2): for each declaration `reached` (`yes`, `perhaps`, `no`), `depth` (the
    least number of steps from a target) and `carries` (how many reached declarations every chain from a target
    meets only through it: its subtree in the dominator tree, itself aside); and the rule's candidates, by
    `carries`. With no targets given, the targets by rule (design 1.1) of the files no other file of the set
    imports. Gives `{ok, targets, target-by, unknown, reached, decls, candidates, files}`."""
    if not isinstance(g, dict) or not g.get("ok"):
        return {"ok": None, "why": "no graph to reach over"}
    decls: dict[str, dict] = g.get("decls") or {}
    uses: dict[str, list[str]] = g.get("uses") or {}
    files: dict[str, dict] = g.get("files") or {}
    given = [str(t) for t in (targets or []) if str(t)]
    if given:
        by = "given"
        tg = [t for t in given if t in decls]
        unknown = [t for t in given if t not in decls]
    else:
        by = "rule"
        imported = {f for v in files.values() for f in v.get("imports") or []}
        tops = [p for p in g.get("order") or [] if p not in imported]
        rule = g.get("targets-by-rule") or {}
        tg = [t for p in tops for t in rule.get(p) or [] if t in decls]
        unknown = []
    depth: dict[str, int] = {t: 0 for t in tg}
    queue = list(tg)
    qi = 0
    while qi < len(queue):
        u = queue[qi]
        qi += 1
        for v in uses.get(u) or []:
            if v in decls and v not in depth:
                depth[v] = depth[u] + 1
                queue.append(v)
    reached = list(depth)
    # dominators, a root above every target
    succ = {ROOT: list(tg)}
    for u in reached:
        succ[u] = [v for v in uses.get(u) or [] if v in depth]
    idom = _dominators(reached, succ, ROOT)
    size: dict[str, int] = {u: 1 for u in reached}
    for u in sorted(reached, key=lambda x: -depth[x]):
        pass
    # subtree sizes: children before parents, by a post-order of the dominator tree
    kids: dict[str, list[str]] = {}
    for v, p in idom.items():
        if v != ROOT:
            kids.setdefault(p, []).append(v)
    post: list[str] = []
    stack = [(ROOT, iter(kids.get(ROOT, [])))]
    while stack:
        node, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            stack.pop()
            post.append(node)
        else:
            stack.append((nxt, iter(kids.get(nxt, []))))
    for v in post:
        if v != ROOT and idom.get(v) not in (None, ROOT):
            size[idom[v]] += size[v]
    # perhaps: used without a name, within the files the targets' files can see
    see: set[str] = set()
    tfiles = {decls[t]["file"] for t in tg}
    order = g.get("order") or []
    imports_of = {p: (files.get(p) or {}).get("imports") or [] for p in order}
    todo = list(tfiles)
    while todo:
        p = todo.pop()
        if p in see:
            continue
        see.add(p)
        todo += imports_of.get(p, [])
    out: dict[str, dict] = {}
    for k, d in decls.items():
        if k in depth:
            out[k] = {"reached": "yes", "depth": depth[k], "carries": size.get(k, 1) - 1}
        elif d.get("file") in see and (d.get("kind") == "instance"
                                       or set(d.get("attributes") or []) & set(PERHAPS_ATTRIBUTES)):
            out[k] = {"reached": "perhaps", "depth": None, "carries": 0}
        else:
            out[k] = {"reached": "no", "depth": None, "carries": 0}
    n = len(reached)
    cands = []
    for k in reached:
        d = decls[k]
        why = []
        if k in tg:
            why.append("target")
        if d.get("kind") in ("theorem", "lemma"):
            if depth[k] == 1:
                why.append("depth-1")
            c = out[k]["carries"]
            if c >= 3 and c * 100 >= 2 * n:
                why.append("carries")
        if why:
            cands.append({"name": k, "file": d.get("file"), "line": d.get("line"), "kind": d.get("kind"),
                          "depth": depth[k], "carries": out[k]["carries"], "why": why})
    cands.sort(key=lambda c: (-c["carries"], c["depth"], c["name"]))
    per_file = {}
    for p in order:
        rows = [out[k] for k, d in decls.items() if d.get("file") == p]
        per_file[p] = {"declarations": len(rows), "reached": sum(1 for r in rows if r["reached"] == "yes"),
                       "perhaps": sum(1 for r in rows if r["reached"] == "perhaps")}
    return {"ok": True, "targets": tg, "target-by": by, "unknown": unknown, "reached": n, "decls": out,
            "candidates": cands, "files": per_file}


__all__ = ["AUTOMATION", "LANGUAGE", "PERHAPS_ATTRIBUTES", "Unreadable", "default_targets", "graph", "outline",
           "place", "reach", "tokenize"]
