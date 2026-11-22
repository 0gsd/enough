"""The fabulam moves: a Lean file taken apart into a fabulam, a folder of them told under a head, and a fabulam
entailed as a pshort (Thym 20.13; MacroCOSM OES 18.4.10).

No new move. Four standard moves take a new operand or a new `as` word, and hand the call on to this module by one
dispatch line each (`code.survey`, `code.derive_branch`, `verse.construe`, `code.entail_branch`):

- `survey t`, `survey t with h` (rules only): one Lean file's outline. Every declaration is an item whose id is its
  kind and its full name; `C:file`, a `C:dependency` per import root, the licence, the makers a header names, the
  means, one `audit` row per comment with no verdict, `P:claim/checking`, `P:assumption/read-as-text`, and the reach
  (`uses`, `used-by`, `leans-on`, `reached`, `depth`, `carries`). `h` is the file's head, or a fabulam of the
  catalog alone that the host wrote by rule (what it read from disk and what the person entered).
- `survey repo`, `survey repo with h` (rules only), of a folder of Lean: the head's outline. A `C:file` per file,
  a `C:component` per Lean file, `parts` in the order of the imports, and every declaration that crosses.
- `derive t as proof with f` (asks, once per chunk): the reading. What each reached declaration says, each lemma's
  role, method and why, the steps, the reliances, the terms and concepts.
- `construe t as comments | yield | stages with f` and `construe w as fit with f` (ask): the comment table and the
  claims; the fit with the public wording; the yield, the worked example, the constants and the slack; the stages,
  the teaching order, the readings and the atem.
- `derive repo with h` (asks): a head's own stages, teaching order, readings and atem, from its parts' summaries.
- `entail f as expert | student | everyone` (asks): a pshort. Rules write its three fixed lines and its footer.

The checks these calls keep are registered here: against the source, `declarations-found`, `lines-resolve`,
`nothing-invented`, `reach-agrees`, `comments-covered`, `nothing-carried`; of a pshort, `cites-resolve`,
`every-sentence-cited`, `yield-cited`, `teaching-followed`, `no-up-to`,
`example-worked`, `checking-told`, `confidence-told`, `symbols-worded`, and the pshort's readings of
`nothing-added`, `apart`, `length` and `footer`.

**Lean is read as text and never run.** The reader is reached only through `ctx.engines["syntax"]` (`outline`,
`graph`, `reach`), whose answers the runtime records, so a replay needs no reader and no file. Nothing here says a
proof is machine-checked: `P:claim/checking` is written by rule from the counts the reader took and from the
person's own entry, and no other sentence speaks of the check.

Standalone: the standard library, PyYAML and the MacroCOSM reader the package already uses.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from enough import macrocosm as mc
from enough.thym.checks import check, split_sentences
from enough.thym.folder import Folder, lines_in
from enough.thym.moves import (MoveError, answer_mapping, engine, entailment_of, fabula_doc, fold, item_kind,
                               model_of, short_value, text_blob, utc_day, words_in)
from enough.thym.moves import code as _code
from enough.thym.registry import Request
from enough.thym.values import Value, plain

# ---------------------------------------------------------------------------
# The budget (the design's 4.4): no request holds more than one file and its neighbours' statements
# ---------------------------------------------------------------------------

#: The Lean one reading request carries. A longer file is read in chunks cut at a declaration's first line.
CHUNK_LINES = 300
#: The neighbours' statements one request carries: one line each, nearest first; past it, names only.
NEIGHBOUR_CHARS = 6_000
#: One neighbour's line is cut at this many characters.
NEIGHBOUR_LINE = 240
#: One component's summary in a head's fold.
SUMMARY_CHARS = 1_200
#: The components one fold request carries. A head with more folds in rounds, then once over the rounds' answers.
HEAD_PARTS = 24
#: The crossing items one fold request carries, by `carries`.
HEAD_CROSSING = 40
#: The whole user message of any request. A request over it is refused before it is sent.
REQUEST_CHARS = 48_000
#: What the prompt adds to a request's inputs in its user message: the labels and the shape of the answer.
SHAPE_CHARS = 2_400
#: The fabulam an entailment carries. Past it the bookkeeping lemmas are left out, then the support lemmas' method.
PSHORT_CHARS = 60_000
#: The band this build reads under one head.
BAND_FILES = 60
BAND_LINES = 12_000

FLAVOUR = "fabulam"
PROOF_AXES = ("comments", "fit", "yield", "stages")
DENSITIES = ("expert", "student", "everyone")
READERS = {"expert": "experts", "student": "students", "everyone": "everyone"}
#: The words a pshort's body holds, by density (the design's 5.4).
WORDS = {"expert": (500, 900), "student": (500, 800), "everyone": (350, 600)}
DECL_KINDS = ("statement", "lemma", "definition")
LEMMA_FORMS = ("theorem", "lemma", "example")
NOTATION_FORMS = ("notation", "macro", "syntax", "infix", "infixl", "infixr", "prefix", "postfix")
DEFINITION_FORMS = ("def", "abbrev", "structure", "class", "inductive", "instance", "opaque", "axiom", "alias",
                    "notation", "other")
ROLES = ("spine", "support", "bookkeeping")
STAGE_WORDS = ("reduction", "main", "tool", "side", "close")
VERDICTS = ("agrees", "claim", "nothing")
CHECKED = {"yes": ("by",), "partial": ("by", "short-of", "mismatch", "false-as-written"),
           "contradicted": ("by", "mismatch"), "not-checkable": ()}
MISMATCHES = ("formula", "hypothesis", "name", "numbering", "inference")
FIT_HOW = ("same", "stronger", "weaker", "a-particular-reading", "different")
BOUNDS = ("at-least", "at-most", "exactly", "between", "none")
CONFIDENCE = {"high": 0.5, "medium": 0.35, "low": 0.2}
QUANTIFIERS = ("for-all", "exists", "infinitely-many", "eventually")
#: The words that may follow "up to" (2.A's `no-up-to`): there it bounds nothing.
UP_TO_ALLOWED = ("isomorphism", "order", "sign", "symmetry", "relabelling")
#: What no sentence may say of a proof but the one that `P:claim/checking` covers.
CHECK_WORDS = ("machine-checked", "machine checked", "verified", "certified", "proved correct")
HEDGES = ("may", "perhaps", "seems", "appears", "we read")
WORDED = ("call it", "written", "stands for", "is the", "the number")
NOT_READ = "a model has not read this file"
NOT_FOLDED = "a model has not read this argument as a whole"
READ_AS = {"by": "rules", "elaborated": "no", "comments": "blanked"}
#: The roots of Lean's own modules: one `C:dependency`, `lean`.
LEAN_ROOTS = ("Init", "Std", "Lean")
_SLUG_OK = re.compile(r"[A-Za-z0-9._@-]")
_ID = re.compile(r"^([A-Z]):([a-z][a-z0-9-]*)/(.+)$")
_LINES = re.compile(r"^\s*L?(\d+)\s*(?:-\s*L?(\d+))?\s*$")

READ_SAYS = ("a YAML mapping: declarations, a list of {lean, says, quantifiers, role, method, why, fields}; steps, "
             "a list of {slug, name, inside, says, lines, confidence}; reliances, a list of {slug, name, lean, "
             "known-as, field, case, gives}; terms and concepts, lists of {name, summary}")
COMMENTS_SAYS = ("a YAML mapping: audit, one entry for every comment listed, {lines, verdict, claim}; works, "
                 "people and aims, lists of {slug, name, summary, lines}")
FIT_SAYS = ("a YAML mapping: fits, one for every statement, {of, how, form-differences, differences, confidence}; "
            "claims, a list of {slug, name, says, about}")
YIELD_SAYS = ("a YAML mapping: yield {name, beyond, says, as-statement, needs, bound, chooses, trivial, no-trivial, "
              "grounds, confidence}; case {slug, name, given, expect}; constants and slack, lists")
STAGES_SAYS = ("a YAML mapping: stages, a list of {slug, name, number, stage, says, plain, plain-if, obvious, "
               "steps}; teaching, the stages' slugs in the teaching order; readings, three to six of {slug, name, "
               "summary, of, "
               "grounds, confidence}; decisions; atem {line, focus, push, pull}")
PSHORT_SAYS = ("a YAML mapping with one key, body: the pshort's body alone, as a block of markdown, each run of "
               "sentences closed by the ids it rests on")


class RequestTooLarge(MoveError):
    """A request past `REQUEST_CHARS`: refused before it is sent, under its own check's name."""
    check = "request"


# ---------------------------------------------------------------------------
# Small things
# ---------------------------------------------------------------------------

def _yaml(x: Any) -> str:
    return _code._yaml(x)


def lean_slug(name: str) -> str:
    """A Lean name as a slug the id grammar takes (the design's 1.3; `fabula_names.declaration_slug` is the same
    rule): `'` becomes `-prime`; any other character the grammar refuses becomes `-x` and its code point in hex; a
    name that would then begin with no letter or digit takes `x` first, and one that would end in a dot spells it."""
    out: list[str] = []
    for ch in name:
        if ch == "'":
            out.append("-prime")
        elif ch.isascii() and _SLUG_OK.match(ch):
            out.append(ch)
        else:
            out.append(f"-x{ord(ch):x}")
    s = "".join(out)
    if s.endswith("."):
        s = s[:-1] + "-x2e"
    if not s or not s[0].isalnum() or not s[0].isascii():
        s = "x" + s
    return s


def respell(name: str) -> str:
    """A file's or a folder's name respelled as a fabulam's (the design's 6; `fabula_names.fabulam_stem` is the same
    rule): `PrimesCongruentOne.lean` gives `primes-congruent-one`, `LSeries` gives `lseries`."""
    base = name.rstrip("/").rsplit("/", 1)[-1]
    stem = base[:-5] if base.endswith(".lean") else base
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", stem).lower()).strip("-") or "fabulam"


def lines_of(v: Any) -> tuple[int, int] | None:
    """`"12"`, `"12-18"`, `"L12-L18"` or a number as `(first, last)`; None for anything else."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return (v, v) if v > 0 else None
    m = _LINES.match(str(v if v is not None else ""))
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    return (a, b) if 0 < a <= b else None


def _lines_text(a: int, b: int | None = None) -> str:
    return f"{a}" if not b or b == a else f"{a}-{b}"


def _span_of(it: dict) -> tuple[str, int, int] | None:
    sp = it.get("span")
    if not isinstance(sp, dict):
        return None
    ab = lines_of(sp.get("lines"))
    return (str(sp.get("file") or ""), ab[0], ab[1]) if ab else None


def _file_name(t: Value) -> str:
    p = t.field("path") if isinstance(t, Value) else None
    if isinstance(p, str) and p:
        return p.replace("\\", "/").rsplit("/", 1)[-1]
    return t.path.name if isinstance(t, Value) and t.path is not None else "proof.lean"


def _fabulam(v: Any, what: str) -> tuple[dict, list[dict]]:
    """A fabulam's catalog and items as plain mappings; a MoveError in the program's words for anything else."""
    if not isinstance(v, Value) or v.type != "fabula":
        raise MoveError(what)
    cat, items = fabula_doc(v)
    cat = {k: plain(x) for k, x in cat.items() if k != "nodes"}
    if cat.get("flavour") != FLAVOUR:
        raise MoveError(f"{what}; this fabula is a {cat.get('flavour') or 'fabulan'}, not a fabulam")
    return cat, [plain(it) for it in items]


def is_head(cat: dict) -> bool:
    """A head fabulam: its source is a folder (it names its parts once they have landed)."""
    src = cat.get("source")
    return isinstance(cat.get("parts"), list) or (isinstance(src, dict) and src.get("kind") == "folder")


def part_uri(head_id: str, module: str) -> str:
    """The URI of the part a Lean file is told in: the head's id, then the file's module with its dots as hyphens
    (the design's 6; `fabula_names.fabulam_part_id` is the same rule)."""
    return f"oes:{head_id}--{lean_slug(module.replace('.', '-'))}"


def part_path(head_name: str, file_path: str) -> str:
    """Where a part's fabulam sits, relative to its head: `<name>.fabulam.parts/`, the source's folders mirrored."""
    stem = file_path[:-5] if file_path.endswith(".lean") else file_path
    return f"{head_name}.fabulam.parts/{stem}.fabulam.cosm"


def item_uri(volume_uri: str, item_id: str) -> str:
    """An item's URI in a volume: `oes:fabula/<name>/C/lemma/<slug>`."""
    module, rest = str(item_id).split(":", 1)
    return f"{volume_uri}/{module}/{rest}"


def _first_sentence(s: Any) -> str:
    parts = split_sentences(fold(s))
    return parts[0] if parts else fold(s)


def _opinion(sources: list, confidence: Any) -> dict:
    word = str(confidence or "medium").strip().lower()
    return _code.prov(sources, CONFIDENCE.get(word, CONFIDENCE["medium"]))


def _confidence(v: Any, what: str) -> str:
    word = str(v or "").strip().lower()
    if word not in CONFIDENCE:
        raise ValueError(f"{what}: confidence is high, medium or low, not {v!r}")
    return word


def _yes_no(v: Any, what: str) -> str:
    """`"yes"` or `"no"`, read from the word or from what YAML makes of the bare word."""
    if v is True:
        return "yes"
    if v is False:
        return "no"
    word = str(v or "").strip().lower()
    if word not in ("yes", "no"):
        raise ValueError(f"{what} is \"yes\" or \"no\", not {v!r}")
    return word


def _clean_slug(s: Any) -> str:
    s = str(s or "").strip()
    s = s.split("/", 1)[1] if _ID.match(s) else s
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:80].strip("-") or "item"


def _fresh(base: str, used: set[str]) -> str:
    iid, k = base, 2
    while iid in used:
        iid, k = f"{base}-{k}", k + 1
    used.add(iid)
    return iid


def _decls(items: list[dict], fname: str | None = None) -> list[dict]:
    return [it for it in items if item_kind(it) in DECL_KINDS and isinstance(it.get("lean"), str)
            and (fname is None or (it.get("span") or {}).get("file") == fname)]


def _by_lean(items: list[dict]) -> dict[str, dict]:
    return {str(it["lean"]): it for it in _decls(items)}


def _run_entry(ctx: Any, model: str | None = None) -> dict:
    run = {"program": _code._program(ctx), "run": getattr(ctx, "run", None), "at": _code.stamp_at(ctx),
           "model": model}
    return {k: v for k, v in run.items() if v}


def _with_run(cat: dict, ctx: Any, model: str | None, **derived: Any) -> dict:
    c = copy.deepcopy(cat)
    d = c.setdefault("derived", {})
    d.update({k: v for k, v in derived.items() if v is not None})
    if model:
        d["model"] = model
    entry = _run_entry(ctx, model)
    runs = d.setdefault("runs", [])
    same = next((r for r in runs if isinstance(r, dict) and entry.get("run") and r.get("run") == entry["run"]), None)
    if same is None:
        runs.append(entry)
    else:
        same.update({k: v for k, v in entry.items() if k not in same})
    return c


# ---------------------------------------------------------------------------
# Comments blanked, by rule, lines kept
# ---------------------------------------------------------------------------

_NAME_CHAR = re.compile(r"[^\W]|['!?₀-₉]")
_CHAR_LIT = re.compile(r"'(?:\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)|[^'\\\n])'")


def blank_comments(text: str) -> str:
    """Lean text with every comment's characters made spaces: `--` to the end of its line, and `/- … -/` (also
    `/-- -/` and `/-! -/`), nested as Lean nests them. A string, a character and a `«…»` name are kept whole, so
    `--` inside one starts nothing; a prime in a name (`h'`) opens no character. Every line stays at its number, a
    line that held only a comment is left empty."""
    out: list[str] = []
    i, n, depth = 0, len(text), 0
    while i < n:
        c = text[i]
        if depth:
            if text.startswith("/-", i):
                depth += 1
                out.append("  ")
                i += 2
            elif text.startswith("-/", i):
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append(c if c in "\r\n" else " ")
                i += 1
            continue
        if text.startswith("/-", i):
            depth = 1
            out.append("  ")
            i += 2
        elif text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif c == "«":
            j = text.find("»", i)
            j = n - 1 if j < 0 else j
            out.append(text[i:j + 1])
            i = j + 1
        elif c == "'" and not (i and _NAME_CHAR.match(text[i - 1])) and (m := _CHAR_LIT.match(text, i)):
            out.append(m.group(0))
            i = m.end()
        else:
            out.append(c)
            i += 1
    return "\n".join(ln.rstrip() for ln in "".join(out).split("\n"))


def numbered(text: str, a: int = 1, b: int | None = None) -> str:
    """Lines `a` to `b` of a text, each with its number in the file."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    b = len(lines) if b is None else min(b, len(lines))
    w = len(str(max(b, 1)))
    return "\n".join(f"{str(k).rjust(w)}| {lines[k - 1]}" for k in range(max(a, 1), b + 1))


def chunks_of(n_lines: int, starts: list[int], size: int = CHUNK_LINES) -> list[dict]:
    """The line ranges a file is read in: at most `size` lines each, cut at a declaration's first line (`starts`).
    A declaration longer than `size` is a range of its own, `long`, read in windows."""
    marks = sorted({s for s in starts if 1 < s <= n_lines})
    out: list[dict] = []
    a = 1
    while a <= n_lines:
        b = min(n_lines, a + size - 1)
        if b < n_lines:
            cuts = [s for s in marks if a < s <= b + 1]
            if cuts:
                b = cuts[-1] - 1
            else:
                nxt = next((s for s in marks if s > a), n_lines + 1)
                out.append({"a": a, "b": nxt - 1, "long": True})
                a = nxt
                continue
        out.append({"a": a, "b": b, "long": False})
        a = b + 1
    return out or [{"a": 1, "b": max(n_lines, 1), "long": False}]


def request_chars(inputs: dict) -> int:
    """How long a request's user message is at most: its inputs' texts and what the prompt adds."""
    total = SHAPE_CHARS
    for v in (inputs or {}).values():
        total += len(v.text() if isinstance(v, Value) else str(v))
    return total


def held(inputs: dict, what: str) -> dict:
    """The inputs, when the request they make is within `REQUEST_CHARS`; else the request is refused unsent."""
    size = request_chars(inputs)
    if size > REQUEST_CHARS:
        raise RequestTooLarge(f"{what} would send {size} characters in one request, past the {REQUEST_CHARS} this "
                              "build sends; nothing was sent")
    return inputs


def _strings(d: dict) -> dict:
    return {k: (v if isinstance(v, Value) else Value("string", str(v))) for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# The reader, through the syntax engine
# ---------------------------------------------------------------------------

def outline_of(ctx: Any, path: str, text: str) -> dict:
    """The reader's outline of one Lean file; a MoveError when it could not be read."""
    ol = engine(ctx, "syntax").outline(path, text)
    if not isinstance(ol, dict) or ol.get("ok") is False:
        where = f" (line {ol.get('line')}: {ol.get('message')})" if isinstance(ol, dict) else ""
        raise MoveError(f"{path} could not be read as Lean{where}")
    if ol.get("language") not in (None, "lean"):
        raise MoveError(f"{path} is {ol.get('language')}; a fabulam is built from a Lean file")
    return ol


def decl_name(d: dict) -> str:
    """A declaration's full name; one with no name is `instance-L<line>` or `example-L<line>`."""
    q = str(d.get("qual") or d.get("name") or "")
    return q or f"{d.get('kind') or 'declaration'}-L{d.get('line')}"


def decl_kind(d: dict, targets: list[str] | set[str] = ()) -> tuple[str, str]:
    """The kind and the form of a declaration's item: a target is a `statement`; every other theorem, lemma and
    example a `lemma`; everything else a `definition`."""
    k = str(d.get("kind") or "other")
    if k in LEMMA_FORMS:
        return ("statement" if decl_name(d) in targets and k != "example" else "lemma"), k
    if k in NOTATION_FORMS:
        return "definition", "notation"
    return "definition", (k if k in DEFINITION_FORMS else "other")


def targets_by_rule(outlines: dict | list) -> list[str]:
    """The final theorems by rule (the design's 1.1): every `theorem` or `lemma` that is not private, is not
    deprecated, and that no other declaration names, an `alias` of it aside. Over one outline or several."""
    ols = list(outlines.values()) if isinstance(outlines, dict) and "defs" not in outlines else [outlines]
    named: set[str] = set()
    for ol in ols:
        for d in ol.get("defs") or []:
            if d.get("kind") == "alias":
                continue
            for r in d.get("refs") or []:
                if isinstance(r, dict) and r.get("to") and r["to"] != decl_name(d):
                    named.add(str(r["to"]))
    return [decl_name(d) for ol in ols for d in ol.get("defs") or []
            if d.get("kind") in ("theorem", "lemma") and (d.get("qual") or d.get("name"))
            and "private" not in (d.get("modifiers") or []) and "deprecated" not in (d.get("attributes") or [])
            and decl_name(d) not in named]


def _uses_map(graph: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for q, row in (graph.get("uses") or {}).items():
        names = []
        for x in row or []:
            name = x.get("to") if isinstance(x, dict) else x
            if isinstance(name, str) and name and name not in names:
                names.append(name)
        out[str(q)] = names
    return out


def _reach_rows(r: Any) -> tuple[dict[str, dict], list[str]]:
    """The reach's answer as `{full name: {reached, depth, carries}}` and the rule's candidates, by name."""
    rows: dict = {}
    if isinstance(r, dict):
        for key in ("decls", "reach", "rows"):
            if isinstance(r.get(key), dict):
                rows = r[key]
                break
        else:
            rows = {k: v for k, v in r.items() if isinstance(v, dict) and "reached" in v}
    cands = []
    for c in (r.get("candidates") if isinstance(r, dict) else None) or []:
        name = c.get("name") or c.get("qual") or c.get("decl") if isinstance(c, dict) else c
        if isinstance(name, str):
            cands.append(name)
    return {str(k): dict(v) for k, v in rows.items() if isinstance(v, dict)}, cands


def _depths(uses: dict[str, list[str]], entries: dict[str, int]) -> dict[str, int]:
    """The least number of steps to each declaration, each entry starting at its own depth."""
    depth = dict(entries)
    frontier = sorted(entries, key=lambda q: entries[q])
    while frontier:
        nxt: list[str] = []
        for q in frontier:
            for u in uses.get(q, []):
                if u not in depth or depth[u] > depth[q] + 1:
                    depth[u] = depth[q] + 1
                    nxt.append(u)
        frontier = nxt
    return depth


def graph_keys(outlines: dict, order: list[str]) -> dict[tuple[str, int], str]:
    """The key the reader's graph gives each declaration, by its file and first line: its full name; `<file>#L<line>`
    when it has none; `<file>#<name>` when an earlier file of the set declares the name too, and
    `<file>#<name>#L<line>` for a second declaration of one name in one file."""
    out: dict[tuple[str, int], str] = {}
    taken: set[str] = set()
    for p in order:
        mine: set[str] = set()
        for d in (outlines.get(p) or {}).get("defs") or []:
            q, line = str(d.get("qual") or ""), int(d.get("line") or 0)
            key = q if q and q not in taken else (f"{p}#{q}" if q else f"{p}#L{line}")
            if q and q in mine:
                key = f"{p}#{q}#L{line}"
            taken.add(key)
            if q:
                mine.add(q)
            out[(p, line)] = key
    return out


def reach_of(ctx: Any, outlines: dict, entries: dict[str, int]) -> dict:
    """The rule's reach over a set of outlines (the design's 4.2): `{graph, uses, rows, candidates, keys}`, the rows
    by the reader's key (`keys` gives each declaration's, by file and line). `entries` maps each declaration the
    reach starts from to its depth there: a target at 0, and, in a part, each declaration another part names at the
    depth the head gives it. `reached` and `carries` are the reader's; `depth` counts on from the entries' own. With
    nothing to start from, nothing is reached."""
    syn = engine(ctx, "syntax")
    graph = syn.graph(outlines)
    graph = graph if isinstance(graph, dict) else {}
    order = [p for p in graph.get("order") or [] if p in outlines] or sorted(outlines)
    keys = graph_keys(outlines, order + [p for p in sorted(outlines) if p not in order])
    uses = _uses_map(graph)
    if not entries:
        return {"graph": graph, "uses": uses, "keys": keys, "candidates": [],
                "rows": {k: {"reached": "no", "carries": 0} for k in keys.values()}}
    rows, cands = _reach_rows(syn.reach(graph, sorted(entries)))
    depth = _depths(uses, entries)
    for q, row in rows.items():
        if row.get("reached") == "yes" and q in depth:
            row["depth"] = depth[q]
    return {"graph": graph, "uses": uses, "rows": rows, "candidates": cands, "keys": keys}


def outside_names(d: dict) -> dict[str, int]:
    """The names a declaration writes that the reader placed in no declaration of the file, each with the first
    line it stands on: library names, and the names of other files."""
    out: dict[str, int] = {}
    for r in d.get("refs") or []:
        if isinstance(r, dict) and r.get("how") in ("outside", "ambiguous") and isinstance(r.get("name"), str):
            out.setdefault(r["name"], int(r.get("line") or d.get("line") or 1))
    return out


def written_as(lean: str, names: Any) -> str | None:
    """The name among `names` that spells `lean`: the full name, its last parts after a dot, or the name with a
    projection after it."""
    for name in names:
        bare = name[len("_root_."):] if name.startswith("_root_.") else name
        if bare == lean or lean.endswith("." + bare) or bare.endswith("." + lean) or bare.startswith(lean + "."):
            return name                                 # the last: a part of the named result (`foo.mp`, `foo.1`)
    return None


# ---------------------------------------------------------------------------
# What is said about checking, by rule
# ---------------------------------------------------------------------------

def checking_says(checking: dict) -> str:
    """The sentence of `P:claim/checking`, built from `source.checking` (the design's 1.5). No model writes it."""
    s, a, nd = (int(checking.get(k) or 0) for k in ("sorry", "axioms", "native-decide"))
    first = ("holds no `sorry`" if not s else f"holds `sorry` {s} time{'s' if s != 1 else ''}") + " and " + (
        "declares no axiom of its own" if not a else f"declares {a} axiom{'s' if a != 1 else ''} of its own")
    out = (f"The file's text {first}. It was read here as text. Nothing was built or run, so whether Lean accepts "
           "it is not known here.")
    if nd:
        out += f" It uses `native_decide` {nd} time{'s' if nd != 1 else ''}, which trusts the compiler."
    said, by = checking.get("said"), checking.get("said-by")
    if isinstance(said, str) and said.strip() and isinstance(by, str) and by.strip():
        at = checking.get("said-at")
        out += f" {by.strip()} says: {said.strip()}" + (f" ({str(at).strip()})." if at else
                                                           ("" if said.strip()[-1:] in ".!?" else "."))
    return out


def checking_item(checking: dict, source: str) -> dict:
    said = bool(checking.get("said") and checking.get("said-by"))
    sources = [source] + ([f"said by {checking['said-by']}"] if said else [])
    return {"id": "P:claim/checking", "type": "claim", "name": "What is known about the machine check",
            "summary": "What the source's text shows about checking, and what the person entered about it.",
            "stance": "hearsay" if said else "observed", "salience": "high",
            "about": "whether Lean accepts the source", "says": checking_says(checking), "checked": "not-checkable",
            "provenance": _code.prov(sources, 0.5 if said else 1)}


def read_as_text_item(source: str) -> dict:
    return {"id": "P:assumption/read-as-text", "type": "assumption", "name": "Read as text",
            "summary": "The Lean was read by rules, as text, and never run.", "stance": "observed",
            "about": "how this fabulam was read",
            "says": "The file was read as text. Names were matched by spelling. Lean was not run.",
            "checked": "no", "carries": "must",
            "if-false": "A link between two declarations may be missing or may point at the wrong one of two with "
                        "one name.",
            "provenance": _code.prov([source])}


def _checking(counts: dict, given: Any) -> dict:
    out = {"sorry": int(counts.get("sorry") or 0), "axioms": int(counts.get("axioms") or 0),
           "native-decide": int(counts.get("native-decide") or 0)}
    g = given if isinstance(given, dict) else {}
    if isinstance(g.get("said"), str) and g["said"].strip() and isinstance(g.get("said-by"), str) and \
            g["said-by"].strip():
        out["said"], out["said-by"] = g["said"].strip(), g["said-by"].strip()
        if g.get("said-at"):
            out["said-at"] = plain(g["said-at"])
    out["built-here"] = "no"
    return out


def _counts(ol: dict) -> dict:
    ax = ol.get("axioms")
    return {"sorry": int(ol.get("sorry") or 0), "axioms": len(ax) if isinstance(ax, list) else int(ax or 0),
            "native-decide": int(ol.get("native-decide") or 0)}


# ---------------------------------------------------------------------------
# The header: licence and makers, by rule
# ---------------------------------------------------------------------------

_HEADER_LICENCE = (
    (re.compile(r"(?i)\bapache(?:\s+licen[cs]e)?,?\s*(?:version\s*)?2(?:\.0)?\b"), "Apache-2.0"),
    (re.compile(r"(?i)\bMIT licen[cs]e\b"), "MIT"),
    (re.compile(r"(?i)\bBSD[- ]3"), "BSD-3-Clause"),
    (re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)"), None),
)
_AUTHORS = re.compile(r"(?im)^\s*Authors?:\s*(.+?)\s*$")


def _comment_text(text: str, c: dict) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(lines[int(c.get("line") or 1) - 1:int(c.get("end") or c.get("line") or 1)])


def _header(ol: dict, text: str) -> tuple[dict | None, str]:
    c = next((c for c in ol.get("comments") or [] if isinstance(c, dict) and c.get("kind") == "header"), None)
    return c, (_comment_text(text, c) if c else "")


def header_licence(words: str) -> str | None:
    for rx, ident in _HEADER_LICENCE:
        m = rx.search(words)
        if m:
            return ident or m.group(1)
    return None


def _licence_items(fname: str, header: dict | None, words: str, given: Any) -> tuple[Any, list[dict]]:
    """`source.licence` and the `R:licence` item: the person's or the host's entry, else the header's line, else
    the question of it."""
    found = header_licence(words)
    value: Any = given if (isinstance(given, str) and given.strip()) or mc.is_pending(given) else (
        found or {"pending": "the file's header names no licence: under which licence may it be used?"})
    where = _code.loc(fname, header.get("line"), header.get("end")) if header and found else fname
    it: dict = {"type": "licence", "stance": "observed",
                "id": f"R:licence/{_code.slug(value) if isinstance(value, str) else 'unknown'}",
                "name": value if isinstance(value, str) else "The licence"}
    it["summary"] = ("The source is under the licence " + value + "." if isinstance(value, str)
                     else "No licence was found for the source.")
    it["identifier"] = value
    it["provenance"] = _code.prov([where], 1, "known" if isinstance(value, str) else "pending")
    return value, [it]


def _maker_items(fname: str, header: dict | None, words: str) -> list[dict]:
    """The authors a header names, each an `R:maker`: what a comment says, so `hearsay`, its source the comment."""
    m = _AUTHORS.search(words)
    if not (header and m):
        return []
    where = _code.loc(fname, header.get("line"), header.get("end"))
    out, seen = [], set()
    for name in re.split(r",|\band\b", m.group(1)):
        name = fold(name).strip(" .")
        if not name or "@" in name or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append({"id": f"R:maker/{_code.slug(name)}", "type": "maker", "name": name,
                    "summary": f"The file's header names {name} as an author.", "stance": "hearsay",
                    "capacity": "author", "provenance": _code.prov([where], 0.5)})
    return out


def _dependency_root(module: str) -> str:
    root = module.split(".", 1)[0]
    return "lean" if root in LEAN_ROOTS else (root.lower() or "unknown")


def _dependency_items(fname: str, imports: list[dict], version: Any, inside: set[str] = frozenset()) -> list[dict]:
    """One `C:dependency` per import root that leads outside (`inside` names the modules of the archive)."""
    roots: dict[str, list[dict]] = {}
    for imp in imports:
        mod = str(imp.get("module") or "")
        if mod and mod not in inside:
            roots.setdefault(_dependency_root(mod), []).append(imp)
    out = []
    for root, rows in roots.items():
        title = {"mathlib": "Mathlib", "lean": "Lean"}.get(root, rows[0]["module"].split(".", 1)[0])
        k = len(rows)
        out.append({"id": f"C:dependency/{_code.slug(root)}", "type": "dependency", "name": title,
                    "summary": f"The source imports {k} module{'s' if k != 1 else ''} of {title}.",
                    "stance": "observed", "package": root,
                    "version": version if version else {"pending": f"which version of {title} is it written for?"},
                    "scope": "standard",
                    "provenance": _code.prov([_code.loc(fname, r.get("line")) for r in rows[:6]])})
    return out


def wording_item(wording: str) -> dict:
    """`E:work/wording`: the public wording of the result, as the person gave it. What it says is hearsay."""
    name = wording.replace("\\", "/").rsplit("/", 1)[-1]
    return {"id": "E:work/wording", "type": "work", "name": name,
            "summary": f"The public wording of the result, as the person gave it: {name}.",
            "stance": "hearsay", "provenance": _code.prov([wording], 0.5)}


def _means_item(toolchain: Any, source: str) -> dict:
    return {"id": "R:means/lean", "type": "means", "name": "Lean", "summary": "The proof is written in Lean 4.",
            "stance": "observed", "what": "Lean", "used-for": "the formal proof",
            "version": toolchain if toolchain else {"pending": "which Lean version does the source name?"},
            "provenance": _code.prov([source])}


# ---------------------------------------------------------------------------
# survey t: one Lean file's outline (rules only)
# ---------------------------------------------------------------------------

def _decl_item(d: dict, fname: str, targets: list[str], row: dict | None, used: set[str]) -> dict:
    lean = decl_name(d)
    kind, form = decl_kind(d, targets)
    a, b = int(d.get("line") or 1), int(d.get("end") or d.get("line") or 1)
    it: dict = {"id": _fresh(f"C:{kind}/{lean_slug(lean)}", used), "type": kind, "name": lean,
                "summary": f"The {form} {lean}, as the Lean file declares it.", "stance": "observed",
                "lean": lean, "form": form, "span": _code.span(fname, a, b)}
    if d.get("digest"):
        it["digest"] = str(d["digest"])
    reached = str((row or {}).get("reached") or "no")
    read = reached in ("yes", "perhaps")
    if kind == "statement":
        it["says"] = {"pending": f"what does {lean} state, in words? ({NOT_READ})"}
        it["quantifiers"] = {"pending": f"which quantifiers does {lean} hold, in order? ({NOT_READ})"}
    elif read:
        it["says"] = {"pending": f"what does {lean} {'state' if kind == 'lemma' else 'define'}, in words? "
                                 f"({NOT_READ})"}
    it["reached"] = reached
    if reached == "yes":
        it["depth"] = int((row or {}).get("depth") or 0)
        it["carries"] = int((row or {}).get("carries") or 0)
    if "private" in (d.get("modifiers") or []):
        it["private"] = "yes"
    if kind != "definition":
        it["proof"] = str(d.get("proof") or "none")
        it["sorry"] = int(d.get("sorry") or 0)
        if d.get("automation"):
            it["automation"] = [str(x) for x in d["automation"]]
        if d.get("scope"):
            it["scope"] = plain(d["scope"])
    it["provenance"] = _code.prov([_code.loc(fname, a, b)])
    return it


def _audit_rows(ol: dict, ids: dict[str, str]) -> list[dict]:
    """One row per comment the reader found, with no verdict: the audit job fills each."""
    rows = []
    for c in ol.get("comments") or []:
        if not isinstance(c, dict):
            continue
        on = str(c.get("on") or "")
        rows.append({"lines": _lines_text(int(c.get("line") or 1), int(c.get("end") or c.get("line") or 1)),
                     "kind": str(c.get("kind") or "inline"), "on": ids.get(on, "")})
    return rows


def _head_place(hcat: dict, hitems: list[dict], t: Value) -> dict | None:
    """Where a file sits under its head: its `C:file` there (by the file's sha256), its component, its part."""
    f = next((it for it in hitems if item_kind(it) == "file" and it.get("sha256") == t.sha256), None)
    if f is None:
        return None
    comp = next((it for it in hitems if item_kind(it) == "component" and f["id"] in (it.get("files") or [])), None)
    module = str(f.get("module") or str(f.get("path"))[:-5].replace("/", "."))
    return {"file": f, "component": comp, "uri": part_uri(str(hcat.get("id")), module),
            "path": part_path(str(hcat.get("name")), str(f.get("path")))}


def _part_source_path(hsrc: dict, part: str, fpath: str) -> str:
    """A part's Lean file, relative to the part's own fabulam: up out of the parts folder, then the head's source."""
    depth = len([p for p in part.split("/") if p]) - 1
    return "../" * max(depth, 0) + str(hsrc.get("path") or "").rstrip("/") + "/" + fpath


def crossing_in(hitems: list[dict], comp: dict | None) -> dict[str, dict]:
    """The head's items told in one part, by Lean name: the declarations of the part that another part names, and
    the targets it holds. The part's component offers them."""
    offers = set((comp or {}).get("offers") or [])
    return {str(it["lean"]): it for it in _decls(hitems) if it.get("id") in offers}


def _entries(cat: dict, hitems: list[dict] | None, comp: dict | None, names: set[str]) -> dict[str, int]:
    """Where a file's reach starts: its targets at depth 0 and, in a part, what the head says crosses into it."""
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    out = {t: 0 for t in src.get("target") or [] if t in names}
    for lean, it in crossing_in(hitems or [], comp).items():
        if lean in names:
            out.setdefault(lean, int(it.get("depth") or 0))
    return out


def survey_text(ctx: Any, t: Value, **mods: Any) -> Value:
    """`survey t` and `survey t with h`: one Lean file's outline, by rule (the design's 5.1, 5.2 stage 1)."""
    if not isinstance(t, Value) or not isinstance(t.payload, str):
        raise MoveError("survey reads a Lean file as text: survey t")
    fname = _file_name(t)
    if not fname.endswith(".lean"):
        raise MoveError(f"{fname} is no Lean file; survey of a text reads a Lean file (.lean)")
    text = t.text()
    n = lines_in(text)
    if n > BAND_LINES:
        raise MoveError("more than twelve thousand lines of Lean: past what this build reads")
    ol = outline_of(ctx, fname, text)
    h = mods.get("with")
    hcat, hitems = _fabulam(h, "survey t with h takes the file's head, or a fabulam of the catalog alone") \
        if isinstance(h, Value) else ({}, [])
    hsrc = hcat.get("source") if isinstance(hcat.get("source"), dict) else {}
    place = _head_place(hcat, hitems, t) if is_head(hcat) else None
    if is_head(hcat) and place is None:
        raise MoveError(f"{fname} is no file of the head's survey: survey the folder again")
    defs = [d for d in ol.get("defs") or [] if isinstance(d, dict)]
    names = {decl_name(d) for d in defs}
    stem = fname[:-5]
    # -- the source
    given = [str(x) for x in hsrc.get("target") or [] if isinstance(x, str)]
    if place is not None:
        fpath = str(place["file"].get("path"))
        fid = str(place["uri"]).split("oes:", 1)[-1]
        name = fid.split("/", 1)[-1]
        path = _part_source_path(hsrc, place["path"], fpath)
        module = place["file"].get("module") or stem
        targets, by = [x for x in given if x in names], str(hsrc.get("target-by") or "given")
        said_target = given
    else:
        name = str(hcat.get("name") or respell(fname))
        fid = str(hcat.get("id") or f"fabula/{name}")
        path, module = str(hsrc.get("path") or fname), hsrc.get("module") or stem
        if given:
            lost = [x for x in given if x not in {decl_name(d) for d in defs if d.get("kind") in ("theorem",
                                                                                               "lemma")}]
            if lost:
                raise MoveError(f"{lost[0]} is no theorem of {fname}; name a final theorem by its full name")
            targets, by = given, "given"
        else:
            targets, by = targets_by_rule(ol), "rule"
        said_target = targets
    toolchain = hsrc.get("toolchain") or {"pending": "which Lean version does the source name? no lean-toolchain "
                                                    "file was found at or above it"}
    header, words = _header(ol, text)
    licence, licence_items = _licence_items(fname, header, words, hsrc.get("licence"))
    checking = _checking(_counts(ol), hsrc.get("checking"))
    src: dict = {"path": path, "kind": "text", "language": "lean", "toolchain": toolchain, "module": module,
                 "lines": n, "size": len(t.bytes()), "sha256": t.sha256,
                 "imports": [str(i.get("module")) for i in ol.get("imports") or [] if isinstance(i, dict)]}
    for k in ("commit", "origin"):
        if hsrc.get(k):
            src[k] = hsrc[k]
    src["licence"] = licence
    if hsrc.get("obtained"):
        src["obtained"] = hsrc["obtained"]
    src.update({"target": list(said_target), "target-by": by})
    if hsrc.get("wording"):
        src["wording"] = hsrc["wording"]
    src.update({"read": dict(READ_AS), "checking": checking})
    cat: dict = {"oes": "fabula/1", "macrocosm": mc.MACROCOSM_VERSION, "flavour": FLAVOUR, "id": fid, "name": name}
    if place is not None:
        cat["head"] = f"oes:{hcat.get('id')}"
    cat["source"] = src
    # -- the reach
    comp = place["component"] if place is not None else None
    entries = _entries(cat, hitems if place is not None else None, comp, names)
    for x in targets:
        entries.setdefault(x, 0)
    reach = reach_of(ctx, {fname: ol}, entries)
    rows, uses, keys = reach["rows"], reach["uses"], reach["keys"]
    key_of = {decl_name(d): keys.get((fname, int(d.get("line") or 0)), decl_name(d)) for d in defs}
    name_of = {k: q for q, k in key_of.items()}
    uses = {name_of.get(k, k): [name_of.get(u, u) for u in us] for k, us in uses.items()}
    rows = {name_of.get(k, k): row for k, row in rows.items()}
    # -- the items
    used: set[str] = set()
    out: list[dict] = []
    file_id = _fresh(f"C:file/{_code.slug(fname)}", used)
    file_it: dict = {"id": file_id, "type": "file", "name": fname,
                     "summary": f"{fname}: " + (str(ol.get("doc")) if ol.get("doc") else "a Lean file") + ".",
                     "stance": "observed", "path": fname, "language": "lean",
                     "length": {"lines": n, "bytes": len(t.bytes())}, "sha256": t.sha256}
    opens = sorted({str(x) for o in ol.get("opens") or [] if isinstance(o, dict) for x in o.get("names") or []})
    if opens:
        file_it["opens"] = opens
    if ol.get("limits"):
        file_it["limits"] = [str(x) for x in ol["limits"]]
    if n:
        file_it["span"] = _code.span(fname, 1, n)
    file_it["provenance"] = _code.prov([fname])
    out.append(file_it)
    inside = {str(it.get("module")) for it in hitems if item_kind(it) == "file" and it.get("module")}
    out += _dependency_items(fname, [i for i in ol.get("imports") or [] if isinstance(i, dict)],
                             hsrc.get("commit") or (toolchain if isinstance(toolchain, str) else None), inside)
    out += licence_items + _maker_items(fname, header, words)
    out.append(_means_item(toolchain if isinstance(toolchain, str) else None, fname))
    if isinstance(src.get("wording"), str) and src["wording"].strip():
        out.append(wording_item(src["wording"]))
    used |= {it["id"] for it in out}
    ids: dict[str, str] = {}
    decl_items: dict[str, dict] = {}
    for d in defs:
        it = _decl_item(d, fname, targets, rows.get(decl_name(d)), used)
        ids[decl_name(d)] = it["id"]
        for alt in (str(d.get("name") or ""), str(d.get("qual") or "")):
            if alt:
                ids.setdefault(alt, it["id"])
        decl_items[decl_name(d)] = it
    for q, it in decl_items.items():
        mine = [ids[u] for u in uses.get(q, []) if u in decl_items and u != q]
        if mine:
            it["uses"] = mine
    for q, it in decl_items.items():
        if item_kind(it) != "statement":
            back = [ids[p] for p in decl_items if q in uses.get(p, []) and p != q]
            if back:
                it["used-by"] = back
    # -- what another part states, relied on here
    relied: list[dict] = []
    if place is not None:
        mine = set(crossing_in(hitems, comp))
        others = {str(it["lean"]): it for it in _decls(hitems) if it["lean"] not in mine}
        for d in defs:
            written = outside_names(d)
            for lean, hit in others.items():
                as_written = written_as(lean, written)
                if as_written is None:
                    continue
                rid = f"C:reliance/{lean_slug(lean)}"
                rel = next((r for r in relied if r["id"] == rid), None)
                if rel is None:
                    rel = {"id": rid, "type": "reliance", "name": lean,
                           "summary": f"This part relies on {lean}, which another part of the archive states.",
                           "stance": "deduced", "on": "part", "lean": [lean],
                           "stated-in": item_uri(f"oes:{hcat.get('id')}", str(hit["id"])),
                           "digest": hit.get("digest"),
                           "gives": copy.deepcopy(hit.get("says")) if hit.get("says") is not None else
                           {"pending": f"what does {lean} state? its part has not been read"},
                           "used-by": [], "provenance": _code.prov([_code.loc(fname, written[as_written])], 0.7)}
                    relied.append(rel)
                user = decl_items[decl_name(d)]
                if user["id"] not in rel["used-by"]:
                    rel["used-by"].append(user["id"])
                user.setdefault("leans-on", [])
                if rid not in user["leans-on"]:
                    user["leans-on"].append(rid)
    out += list(decl_items.values()) + relied
    out += [checking_item(checking, fname), read_as_text_item(fname)]
    at = _code.stamp_at(ctx)
    run = _run_entry(ctx)
    cat["derived"] = {"at": at, "by": "person", **({"program": run["program"]} if run.get("program") else {}),
                      **({"run": run["run"]} if run.get("run") else {}), "mode": "rules",
                      "completeness": "outline", "chunks": 0, "runs": [run]}
    atem: dict = {k: {"pending": f"{NOT_FOLDED}: what is its {k}?"} for k in ("line", "focus", "push", "pull")}
    first = next((it["id"] for it in decl_items.values() if item_kind(it) == "statement"), None) or next(
        (it["id"] for it in sorted(decl_items.values(), key=lambda x: x.get("depth", 10 ** 6))
         if it.get("reached") == "yes"), None)
    first = first or next((it["id"] for it in decl_items.values()), None)
    atem = {"of": first or {"pending": f"{fname} declares nothing: what does it restate?"}, **atem}
    cat.update({"atem": atem, "audit": _audit_rows(ol, ids)})
    cat["nodes"] = [_code._prov_last(it) for it in out]
    return Value("fabula", cat, origin={"proof": {"path": fname, "candidates": reach["candidates"]}})


# ---------------------------------------------------------------------------
# survey repo: a head's outline over a folder of Lean (rules only)
# ---------------------------------------------------------------------------

def is_lean_folder(v: Any) -> bool:
    """A folder whose language is Lean: it holds Lean files, and more of them than Python files."""
    if not isinstance(v, Value) or not isinstance(v.payload, Folder):
        return False
    texts = v.payload.texts()
    lean = sum(1 for e in texts if e.suffix == "lean")
    return lean > 0 and lean >= sum(1 for e in texts if e.suffix == "py")


def _modules(paths: list[str], outlines: dict, root: str | None = None) -> dict[str, str]:
    """Each Lean file's dotted module name: the import, among the set's, that spells the file's path; else the path
    itself under the prefix the others show, or under `root` (the module the folder is, when the host knows it)."""
    imports = {str(i.get("module")) for ol in outlines.values() for i in ol.get("imports") or []
               if isinstance(i, dict) and i.get("module")}
    out: dict[str, str] = {}
    prefix: str | None = root.rstrip(".") + "." if root else None
    for p in paths:
        own = p[:-5].replace("/", ".")
        hit = next((m for m in sorted(imports) if m == own or m.endswith("." + own)), None)
        if hit:
            out[p] = hit
            if prefix is None and hit != own:
                prefix = hit[: -len(own)]
    for p in paths:
        out.setdefault(p, (prefix or "") + p[:-5].replace("/", "."))
    return out


def survey_archive(ctx: Any, repo: Value, **mods: Any) -> Value:
    """`survey repo` of a folder of Lean: the head's outline (the design's 4.1, 4.2, 5.1), by rule."""
    f: Folder = repo.payload
    lean = [e for e in f.texts() if e.suffix == "lean"]
    if len(lean) > BAND_FILES:
        raise MoveError("more than sixty Lean files: past what this build reads")
    if sum(lines_in(f.text(e.path)) for e in lean) > BAND_LINES:
        raise MoveError("more than twelve thousand lines of Lean: past what this build reads")
    h = mods.get("with")
    hcat, _h = _fabulam(h, "survey repo with h takes a fabulam of the catalog alone") if isinstance(h, Value) \
        else ({}, [])
    hsrc = hcat.get("source") if isinstance(hcat.get("source"), dict) else {}
    counts = engine(ctx, "repo").tree(repo)
    if counts.get("tree") != f.tree:
        raise MoveError(f"{f.path} changed while it was surveyed: its tree is now {str(counts.get('tree'))[:12]}…")
    outlines = {e.path: outline_of(ctx, e.path, f.text(e.path)) for e in lean}
    all_names = {decl_name(d): p for p, ol in outlines.items() for d in ol.get("defs") or []}
    given = [str(x) for x in hsrc.get("target") or [] if isinstance(x, str)]
    lost = [x for x in given if x not in all_names]
    if lost:
        raise MoveError(f"{lost[0]} is no declaration of {f.name}; name a final theorem by its full name")
    targets, by = (given, "given") if given else (targets_by_rule(outlines), "rule")
    module = _modules(sorted(outlines), outlines, hsrc.get("module") if isinstance(hsrc.get("module"), str) else None)
    # the reader finds an imported file by its module's path (`A/B/C.lean` for `A.B.C`): the set goes to it so
    gpath = {p: module[p].replace(".", "/") + ".lean" for p in outlines}
    back = {g: p for p, g in gpath.items()}
    reach = reach_of(ctx, {gpath[p]: ol for p, ol in outlines.items()}, {x: 0 for x in targets})
    graph, rows, uses = reach["graph"], reach["rows"], reach["uses"]
    name_of = {reach["keys"].get((gpath[p], int(d.get("line") or 0)), decl_name(d)): decl_name(d)
               for p, ol in outlines.items() for d in ol.get("defs") or []}
    uses = {name_of.get(k, k): [name_of.get(u, u) for u in us] for k, us in uses.items()}
    rows = {name_of.get(k, k): row for k, row in rows.items()}
    order = [back[g] for g in graph.get("order") or [] if g in back]
    order += [p for p in sorted(outlines) if p not in order]
    name = str(hcat.get("name") or respell(f.name))
    hid = str(hcat.get("id") or f"fabula/{name}")
    paths = [e.path for e in f.entries]
    slugs = _code._file_slugs(paths)
    toolchain = hsrc.get("toolchain")
    if not toolchain and f.entry("lean-toolchain") is not None:
        toolchain = fold(f.text("lean-toolchain"))
    toolchain = toolchain or {"pending": "which Lean version does the source name? no lean-toolchain file was "
                                         "found at or above it"}
    out: list[dict] = []
    used: set[str] = set()
    file_ids = {p: f"C:file/{slugs[p]}" for p in paths}
    for e in f.entries:
        ol = outlines.get(e.path)
        it: dict = {"id": file_ids[e.path], "type": "file", "name": e.path,
                    "summary": f"{e.path}: " + (str(ol.get("doc")) if ol and ol.get("doc") else
                                                ("a Lean file" if ol else "a file the folder carries")) + ".",
                    "stance": "observed", "path": e.path,
                    "language": "binary" if e.binary else ("lean" if ol else _code._language(e.path))}
        if ol:
            it["module"] = module[e.path]
        it["length"] = {"bytes": e.size} if e.binary else {"lines": lines_in(f.text(e.path)), "bytes": e.size}
        if it["length"].get("lines"):
            it["span"] = _code.span(e.path, 1, it["length"]["lines"])
        it["sha256"] = e.sha256
        it["provenance"] = _code.prov([e.path])
        out.append(it)
    used |= set(file_ids.values())
    # -- the declarations that cross: named by a reached declaration of another file, and the targets
    where = {decl_name(d): (p, d) for p, ol in outlines.items() for d in ol.get("defs") or []}
    crossing: list[str] = []
    for q, row in rows.items():
        if row.get("reached") != "yes" or q not in where:
            continue
        if q in targets or any(q in uses.get(p, []) and where[p][0] != where[q][0]
                               and rows.get(p, {}).get("reached") == "yes" for p in where):
            crossing.append(q)
    crossing.sort(key=lambda q: (-int(rows[q].get("carries") or 0), q))
    parts = [{"file": p, "uri": part_uri(hid, module[p]), "path": part_path(name, p)} for p in order]
    offers: dict[str, list[str]] = {p: [] for p in order}
    head_items: list[dict] = []
    for q in crossing:
        p, d = where[q]
        kind, form = decl_kind(d, targets)
        iid = _fresh(f"C:{kind}/{lean_slug(q)}", used)
        a, b = int(d.get("line") or 1), int(d.get("end") or d.get("line") or 1)
        it = {"id": iid, "type": kind, "name": q,
              "summary": f"The {form} {q}, stated here for the parts that use it.", "stance": "observed",
              "lean": q, "form": form, "span": _code.span(p, a, b), "digest": d.get("digest"),
              "says": {"pending": f"what does {q} state? its part has not been read"},
              "reached": "yes",
              "depth": int(rows[q].get("depth") or 0), "carries": int(rows[q].get("carries") or 0),
              "provenance": _code.prov([_code.loc(p, a, b)])}
        if kind == "statement":
            it["quantifiers"] = {"pending": f"which quantifiers does {q} hold, in order? its part has not been "
                                            "read"}
        if it["digest"] is None:
            it.pop("digest")
        offers[p].append(iid)
        head_items.append(it)
    # at the head's grain, a crossing declaration uses the crossing declarations it reaches without passing through
    # another: so a chain of uses leads from the targets to every one of them
    cross = {it["lean"]: it["id"] for it in head_items}
    for it in head_items:
        seen, todo, hit = {it["lean"]}, list(uses.get(it["lean"], [])), []
        while todo:
            u = todo.pop(0)
            if u in seen:
                continue
            seen.add(u)
            if u in cross:
                hit.append(cross[u])
            elif rows.get(u, {}).get("reached") == "yes":
                todo += uses.get(u, [])
        if hit:
            it["uses"] = hit
    for p in order:
        ol = outlines[p]
        defs = [decl_name(d) for d in ol.get("defs") or []]
        n_reached = sum(1 for q in defs if rows.get(q, {}).get("reached") == "yes")
        comp: dict = {"id": _fresh(f"C:component/{_code.name_slug(module[p])}", used), "type": "component",
                      "name": module[p], "summary": f"The Lean module {module[p]}" + (f": {ol.get('doc')}" if ol.get("doc")
                                                                             else "."),
                      "stance": "observed", "files": [file_ids[p]]}
        comp["does"] = ({"pending": f"what does {module[p]} prove on the way to the targets? ({NOT_READ})"}
                        if n_reached else "No declaration of it is reached from the targets: it is outlined by "
                                          "rule and was not read.")
        comp.update({"offers": offers[p], "stages": [],
                     "counts": {"declarations": len(defs), "reached": n_reached, "spine": 0},
                     "completeness": "outline", "provenance": _code.prov([p])})
        out.append(comp)
    inside = set(module.values())
    version = hsrc.get("commit") or f.commit or (toolchain if isinstance(toolchain, str) else None)
    deps: dict[str, dict] = {}
    for p in order:
        for it in _dependency_items(p, [i for i in outlines[p].get("imports") or [] if isinstance(i, dict)],
                                    version, inside):
            if it["id"] in deps:
                deps[it["id"]]["provenance"]["sources"] += [s for s in it["provenance"]["sources"] if s not in
                                                            deps[it["id"]]["provenance"]["sources"]][:3]
            else:
                it["summary"] = f"The archive imports modules of {it['name']}."
                deps[it["id"]] = it
    out += list(deps.values())
    # -- the licence: the host's or the person's entry, the folder's licence file, else the files' headers
    lic_files = [e for e in f.texts() if _code.is_licence_file(e.path)]
    read = _code.read_licence(f.text(lic_files[0].path)) if lic_files else None
    headers = {header_licence(_header(outlines[p], f.text(p))[1]) for p in order} - {None}
    found = (read or {}).get("identifier") or (sorted(headers)[0] if len(headers) == 1 else None)
    licence, lic_items = _licence_items(f.name + "/", None, "", hsrc.get("licence") or found)
    if lic_files and isinstance(licence, str):
        lic_items[0]["file"] = lic_files[0].path
        lic_items[0]["provenance"] = _code.prov([lic_files[0].path])
    out += lic_items
    out.append(_means_item(toolchain if isinstance(toolchain, str) else None, f.name + "/"))
    if isinstance(hsrc.get("wording"), str) and hsrc["wording"].strip():
        out.append(wording_item(hsrc["wording"]))
    total = {"sorry": 0, "axioms": 0, "native-decide": 0}
    for ol in outlines.values():
        for k, v in _counts(ol).items():
            total[k] += v
    checking = _checking(total, hsrc.get("checking"))
    out += head_items
    out += [checking_item(checking, f.name + "/"), read_as_text_item(f.name + "/")]
    src: dict = {"path": str(hsrc.get("path") or f"{f.name}/"), "kind": "folder", "language": "lean",
                 "toolchain": toolchain, "files": counts["files"],
                 "lines": sum(lines_in(f.text(e.path)) for e in lean), "bytes": counts["bytes"],
                 "skipped": counts["skipped"], "tree": f.tree}
    for k, v in (("commit", hsrc.get("commit") or f.commit), ("origin", hsrc.get("origin") or f.origin)):
        if v:
            src[k] = v
    src["licence"] = licence
    if hsrc.get("obtained"):
        src["obtained"] = hsrc["obtained"]
    src.update({"target": list(targets), "target-by": by})
    if hsrc.get("wording"):
        src["wording"] = hsrc["wording"]
    src.update({"read": dict(READ_AS), "checking": checking})
    at = _code.stamp_at(ctx)
    run = _run_entry(ctx)
    atem: dict = {k: {"pending": f"{NOT_FOLDED}: what is its {k}?"} for k in ("line", "focus", "push", "pull")}
    first = next((it["id"] for it in head_items if item_kind(it) == "statement"), None)
    if first:
        atem = {"of": first, **atem}
    cat = {"oes": "fabula/1", "macrocosm": mc.MACROCOSM_VERSION, "flavour": FLAVOUR, "id": hid, "name": name,
           "source": src,
           "derived": {"at": at, "by": "person", **({"program": run["program"]} if run.get("program") else {}),
                       **({"run": run["run"]} if run.get("run") else {}), "mode": "rules",
                       "completeness": "outline", "chunks": 0, "runs": [run]},
           "atem": atem, "nodes": [_code._prov_last(it) for it in out]}
    return Value("fabula", cat, origin={"proof": {"order": order, "parts": parts,
                                                  "candidates": reach["candidates"]}})


def survey_branch(ctx: Any, x: Value, mods: dict) -> Any:
    """`survey`'s proof branch: a Lean text, or a folder of Lean; None for a folder of Python."""
    if isinstance(x, Value) and x.type != "folder" and isinstance(x.payload, str):
        return survey_text(ctx, x, **mods)
    if is_lean_folder(x):
        return survey_archive(ctx, x, **mods)
    return None


# ---------------------------------------------------------------------------
# derive t as proof with f: the reading (asks, once per chunk)
# ---------------------------------------------------------------------------

_SHOWN = ("id", "lean", "form", "reached", "depth", "carries", "private", "proof", "automation", "scope", "says",
          "role")


def _shown(it: dict) -> dict:
    out = {k: it[k] for k in _SHOWN if k in it and not mc.is_pending(it[k])}
    sp = _span_of(it)
    if sp:
        out["lines"] = _lines_text(sp[1], sp[2])
    return out


def neighbours(items: list[dict]) -> str:
    """The statements this file leans on in other parts, one line each, `name: says`, nearest first, each cut at
    `NEIGHBOUR_LINE` characters; past `NEIGHBOUR_CHARS`, names only."""
    rows = [it for it in items if item_kind(it) == "reliance" and it.get("on") == "part"]
    out, size = [], 0
    for it in rows:
        name = ", ".join(it.get("lean") or []) if isinstance(it.get("lean"), list) else str(it.get("lean"))
        says = it.get("gives")
        line = f"{name}: {fold(says)}" if isinstance(says, str) else name
        line = line if len(line) <= NEIGHBOUR_LINE else line[:NEIGHBOUR_LINE - 1] + "…"
        if size + len(line) + 1 > NEIGHBOUR_CHARS:
            line = name
        if size + len(line) + 1 > NEIGHBOUR_CHARS:
            out.append(f"(and {len(rows) - len(out)} more)")
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)


def _item_ref(v: Any, by_lean: dict[str, dict], ids: set[str]) -> str | None:
    """An item a model names, by its id or by its Lean name."""
    s = str(v or "").strip().strip('"')
    if s in ids:
        return s
    if s in by_lean:
        return str(by_lean[s]["id"])
    return None


def _inside_lines(lines: Any, of: dict, what: str) -> tuple[int, int]:
    ab, sp = lines_of(lines), _span_of(of)
    if ab is None:
        raise ValueError(f"{what}: lines {lines!r} are not n or n-m")
    if sp and not (sp[1] <= ab[0] and ab[1] <= sp[2]):
        raise ValueError(f"{what}: lines {_lines_text(*ab)} lie outside {of.get('id')}, which is lines "
                         f"{_lines_text(sp[1], sp[2])}")
    return ab


def _quantifiers(v: Any, what: str) -> list[dict]:
    if not isinstance(v, list):
        raise ValueError(f"{what}: quantifiers is a list of {{kind, what}}, in the order the Lean gives them")
    out = []
    for q in v:
        if not isinstance(q, dict) or q.get("kind") not in QUANTIFIERS or not q.get("what"):
            raise ValueError(f"{what}: a quantifier is {{kind: {' | '.join(QUANTIFIERS)}, what}}")
        out.append({"kind": q["kind"], "what": fold(q["what"])})
    return out


def parse_reading(data: dict, *, fname: str, items: list[dict], defs: list[dict], cover: list[str], taken: set[str],
                  feed: Any = None, needs: str = "all") -> list[dict]:
    """A model's reading of one chunk as items (strict: a ValueError says what is wrong, and it is asked again).
    `cover` names the declarations the chunk must tell; `needs` is `all`, or `notes` for a window of a long
    declaration, which tells none."""
    by_lean = _by_lean(items)
    ids = {str(it.get("id")) for it in items}
    out: dict[str, dict] = {}
    rows = data.get("declarations") or []
    if not isinstance(rows, list):
        raise ValueError("declarations must be a list")
    told: set[str] = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"declarations entry {i} is not a mapping")
        base = by_lean.get(str(row.get("lean") or "").strip()) or next(
            (it for it in by_lean.values() if it["id"] == row.get("id")), None)
        if base is None:
            raise ValueError(f"declarations entry {i} names {row.get('lean')!r}, which the outline does not list; "
                             "name a declaration by its lean, exactly as the outline writes it")
        if (base.get("span") or {}).get("file") != fname:
            raise ValueError(f"{base['lean']} belongs to another file")
        kind, lean = item_kind(base), base["lean"]
        if base.get("reached") not in ("yes", "perhaps"):
            continue                                   # not reached: a model does not tell it
        add: dict = {"id": base["id"]}
        if isinstance(row.get("says"), str) and row["says"].strip():
            add["says"] = fold(row["says"])
        if kind == "statement" and row.get("quantifiers") is not None:
            add["quantifiers"] = _quantifiers(row["quantifiers"], lean)
        if kind == "lemma" and base.get("reached") == "yes":
            if row.get("role") is not None:
                if row["role"] not in ROLES:
                    raise ValueError(f"{lean}: role is {', '.join(ROLES)}, not {row['role']!r}")
                add["role"] = row["role"]
            if isinstance(row.get("method"), str) and row["method"].strip():
                add["method"] = fold(row["method"])
            if add.get("role") == "spine":
                if not (isinstance(row.get("why"), str) and row["why"].strip()):
                    raise ValueError(f"{lean} is spine and has no why: what the argument would lack without it")
                add["why"] = fold(row["why"])
        if kind == "statement" and isinstance(row.get("method"), str) and row["method"].strip():
            add["method"] = fold(row["method"])
        if kind == "definition" and isinstance(row.get("fields"), list):
            add["fields"] = [{"name": str(x.get("name")), "says": fold(x.get("says"))} for x in row["fields"]
                             if isinstance(x, dict) and x.get("name") and x.get("says")]
        out[base["id"]] = add
        told.add(lean)
    if needs == "all":
        for lean in cover:
            base, add = by_lean[lean], out.get(by_lean[lean]["id"], {})
            kind = item_kind(base)
            lacks = [k for k in (("says", "quantifiers") if kind == "statement" else ("says",)) if k not in add]
            if kind == "lemma" and base.get("reached") == "yes":
                lacks += [k for k in ("role", "method") if k not in add]
            if lacks:
                raise ValueError(f"{lean} is reached and the answer gives no {', '.join(lacks)} for it")
    new: list[dict] = []
    used = set(taken)
    # -- steps
    for i, row in enumerate(data.get("steps") or [], 1):
        if not isinstance(row, dict) or not row.get("says") or not row.get("name"):
            raise ValueError(f"steps entry {i} needs name, inside, says and lines")
        inside = _item_ref(row.get("inside"), by_lean, ids)
        of = next((it for it in items if it.get("id") == inside), None)
        if of is None or item_kind(of) not in ("lemma", "statement"):
            raise ValueError(f"steps entry {i}: inside names {row.get('inside')!r}, which is no lemma or statement "
                             "of the outline")
        a, b = _inside_lines(row.get("lines"), of, f"steps entry {i}")
        iid = _fresh(f"C:step/{_clean_slug(row.get('slug') or row['name'])}", used)
        new.append({"id": iid, "type": "step", "name": fold(row["name"])[:120],
                    "summary": _first_sentence(row.get("summary") or row["says"]), "stance": "opinion",
                    "inside": inside, "says": fold(row["says"]), "span": _code.span(fname, a, b),
                    "confidence": _confidence(row.get("confidence") or "medium", f"steps entry {i}"),
                    "provenance": _opinion([_code.loc(fname, a, b)], row.get("confidence"))})
    # -- reliances: library results, by the names the file writes
    by_def = {decl_name(d): outside_names(d) for d in defs}
    written = {n: ln for names in by_def.values() for n, ln in names.items()}
    deps = [it for it in items if item_kind(it) == "dependency"]
    for i, row in enumerate(data.get("reliances") or [], 1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("gives"):
            raise ValueError(f"reliances entry {i} needs name, lean and gives")
        names = row.get("lean")
        names = [names] if isinstance(names, str) else [str(x) for x in names or []]
        if not names:
            raise ValueError(f"reliances entry {i} ({row['name']}) names no lean: the names the file writes")
        lost = [x for x in names if written_as(x, written) is None]
        if lost:
            raise ValueError(f"reliances entry {i}: the file does not write {lost[0]} outside its own declarations; "
                             "name a library result by a name the file writes, or leave the reliance out")
        names = [written_as(x, written) or x for x in names]
        root = _dependency_root(names[0]) if "." in names[0] else None
        dep = next((d for d in deps if d.get("package") == root), None) or next(
            (d for d in deps if d.get("package") == "mathlib"), None) or (deps[0] if deps else None)
        iid = _fresh(f"C:reliance/{_clean_slug(row.get('slug') or row['name'])}", used)
        it: dict = {"id": iid, "type": "reliance", "name": fold(row["name"])[:120],
                    "summary": _first_sentence(row.get("summary") or row["gives"]), "stance": "assumed",
                    "on": "dependency"}
        if dep is not None:
            it["of"] = dep["id"]
        it["lean"] = names
        for k in ("known-as", "field", "case"):
            if isinstance(row.get(k), str) and row[k].strip():
                it[k] = fold(row[k])
        it["gives"] = fold(row["gives"])
        users = [by_lean[q]["id"] for q, ns in by_def.items() if q in by_lean and set(names) & set(ns)]
        if users:
            it["used-by"] = users
        it["provenance"] = _code.prov([_code.loc(fname, min(written[x] for x in names))], 0.3)
        new.append(it)
        for uid in users:
            base = next(x for x in items if x.get("id") == uid)
            add = out.setdefault(uid, {"id": uid})
            add.setdefault("leans-on", list(base.get("leans-on") or []))
            if iid not in add["leans-on"]:
                add["leans-on"].append(iid)
    # -- terms and concepts
    for section, letter, kind in (("terms", "L", "term"), ("concepts", "K", "concept")):
        for i, row in enumerate(data.get(section) or [], 1):
            if not isinstance(row, dict) or not row.get("name") or not row.get("summary"):
                raise ValueError(f"{section} entry {i} needs name and summary")
            base_id = f"{letter}:{kind}/{_clean_slug(row.get('slug') or row['name'])}"
            if base_id in taken:
                continue                               # the fabulam has the word already
            it = {"id": _fresh(base_id, used), "type": kind, "name": fold(row["name"])[:120],
                  "summary": fold(row["summary"])}
            if kind == "term":
                it["feed"] = _code._ground(feed, str(row.get("word") or row["name"]), row.get("pos"))
                if row.get("sense"):
                    it["sense"] = fold(row["sense"])
            it["stance"] = "assumed"
            it["provenance"] = _code.prov([fname], 0.3)
            new.append(it)
    return list(out.values()) + new


def _notes(data: dict) -> list[str]:
    return [fold(x) for x in data.get("notes") or [] if isinstance(x, str) and x.strip()]


def read_proof(ctx: Any, t: Value, **mods: Any) -> Request | Value:
    """`derive t as proof with f`: one Lean file read against its outline (the design's 5.2 stage 2), comments
    blanked. One request for a file of `CHUNK_LINES` lines or fewer; else one per chunk, a declaration longer than
    that in windows with one last request, without Lean, for its method."""
    w = mods.get("with")
    cat, items = _fabulam(w, "derive … as proof reads a Lean file against its outline: derive t as proof with f")
    fname, text = _file_name(t), t.text()
    file_it = next((it for it in items if item_kind(it) == "file" and it.get("path") == fname), None)
    if file_it is None or file_it.get("sha256") != t.sha256:
        raise MoveError(f"{fname} is not the file this fabulam was surveyed from: survey it first")
    ol = outline_of(ctx, fname, text)
    defs = [d for d in ol.get("defs") or [] if isinstance(d, dict)]
    n = lines_in(text)
    blank = blank_comments(text)
    mine = _decls(items, fname)
    shown = [it for it in mine if it.get("reached") in ("yes", "perhaps")]
    taken = {str(it.get("id")) for it in items}
    feed = (getattr(ctx, "engines", None) or {}).get("feed")
    parts = chunks_of(n, [int(d.get("line") or 1) for d in defs])
    near = neighbours(items)
    outline = _yaml([_shown(it) for it in shown])
    schema = {"format": "yaml", "stamp": "engine", "says": READ_SAYS}
    name = str(cat.get("name") or fname)

    def cover(a: int, b: int) -> list[str]:
        return [it["lean"] for it in shown if (sp := _span_of(it)) and a <= sp[1] <= b]

    def inputs(a: int, b: int, **more: Any) -> dict:
        ins = {"fabulam": "read", "name": name, "path": fname, "lines": f"{a}-{b} of {n}",
               "code": numbered(blank, a, b), "outline": outline, "neighbours": near or None,
               "cover": _yaml(cover(a, b)), **more}
        if len(parts) > 1:
            ins["part"] = f"{[p['a'] for p in parts].index(a) + 1} of {len(parts)}" if "window" not in more else None
        return held(_strings(ins), f"the reading of {fname}, lines {a} to {b},")

    def value(new: list[dict]) -> Value:
        return Value("fabula", _code.reading_value(cat, items, fname, new), origin={"reading": {"path": fname}})

    if len(parts) == 1 and not parts[0]["long"]:
        def parse(out: Any) -> Value:
            return value(parse_reading(answer_mapping(out), fname=fname, items=items, defs=defs, cover=cover(1, n),
                                       taken=taken, feed=feed))
        return Request(contract={"schema": schema, "repair": []}, inputs=inputs(1, n), parse=parse)
    failed = "; ".join(f"{x.get('name')}: {x.get('why')}" for x in getattr(ctx, "failed", None) or []) or None
    new: list[dict] = []

    def ask(ins: dict, read: Any) -> Any:
        err = failed
        for _try in range(2):
            if err:
                ins = {**ins, "failed": Value("string", err)}
            cand = ctx.ask({"schema": schema, "repair": []}, ins)
            try:
                return read(answer_mapping(cand.get("output")))
            except ValueError as e:
                err = str(e)
        raise MoveError(f"{fname}: the reading could not be read: {err}")

    def gain(rows: list[dict]) -> None:
        have = {x["id"]: x for x in new}
        for it in rows:
            if it["id"] in have and set(it) <= set(have[it["id"]]) | {"leans-on"}:
                have[it["id"]].update(it)
            elif it["id"] in have:
                have[it["id"]].update({k: v for k, v in it.items() if k != "id"})
            else:
                new.append(it)

    for p in parts:
        a, b = p["a"], p["b"]
        used = taken | {x["id"] for x in new}
        if not p["long"]:
            gain(ask(inputs(a, b), lambda d, a=a, b=b, used=used: parse_reading(
                d, fname=fname, items=items, defs=defs, cover=cover(a, b), taken=used, feed=feed)))
            continue
        # a declaration longer than a chunk: windows, each given its statement again, then its method from the notes
        d0 = next((d for d in defs if int(d.get("line") or 0) == a), None)
        statement = str((d0 or {}).get("signature") or "")
        windows = [(k, min(b, k + CHUNK_LINES - 1)) for k in range(a, b + 1, CHUNK_LINES)]
        notes: list[str] = []
        for k, (wa, wb) in enumerate(windows, 1):
            def read_window(d: dict, used: set = used) -> list[dict]:
                rows = parse_reading(d, fname=fname, items=items, defs=defs, cover=[], taken=used, feed=feed,
                                     needs="notes")
                notes.extend(_notes(d))
                return [r for r in rows if item_kind(r) in ("step", "reliance", "term", "concept") or "leans-on" in r]
            gain(ask(inputs(wa, wb, window=f"{k} of {len(windows)}", statement=statement), read_window))
            used = taken | {x["id"] for x in new}
        last = held(_strings({"fabulam": "read", "name": name, "path": fname, "lines": f"{a}-{b} of {n}",
                              "outline": outline, "statement": statement, "notes": _yaml(notes),
                              "cover": _yaml(cover(a, b)), "neighbours": near or None}),
                    f"the method of the declaration at line {a} of {fname}")
        gain(ask(last, lambda d, a=a, b=b, used=used: parse_reading(
            d, fname=fname, items=items, defs=defs, cover=cover(a, b), taken=used, feed=feed)))
    return value(new)


# ---------------------------------------------------------------------------
# construe t as comments with f: the comment table (asks)
# ---------------------------------------------------------------------------

def _brief(items: list[dict], kinds: tuple[str, ...], fields: tuple[str, ...]) -> list[dict]:
    rows = []
    for it in items:
        if item_kind(it) not in kinds:
            continue
        row = {"id": it.get("id")}
        for k in fields:
            if k in it and not mc.is_pending(it[k]):
                row[k] = it[k]
        sp = _span_of(it)
        if sp:
            row["lines"] = _lines_text(sp[1], sp[2])
        rows.append(row)
    return rows


def parse_comments(data: dict, *, fname: str, cat: dict, items: list[dict], rows: list[dict], taken: set[str]
                   ) -> tuple[list[dict], list[dict]]:
    """The audit's answer as `(the rows with their verdicts, the new items)`. Every row asked has one entry."""
    by_lean = _by_lean(items)
    ids = {str(it.get("id")) for it in items}
    got = data.get("audit")
    if not isinstance(got, list):
        raise ValueError("the answer holds no audit: list")
    by_lines: dict[str, dict] = {}
    for i, r in enumerate(got, 1):
        ab = lines_of(r.get("lines")) if isinstance(r, dict) else None
        if ab is None:
            raise ValueError(f"audit entry {i} has no lines")
        key = _lines_text(*ab)
        if key in by_lines:
            raise ValueError(f"two audit entries for the comment at lines {key}")
        by_lines[key] = r
    asked = {r["lines"] for r in rows}
    extra = [k for k in by_lines if k not in asked]
    if extra:
        raise ValueError(f"the audit names lines {extra[0]}, which hold no comment listed; use the lines as listed")
    missing = [r["lines"] for r in rows if r["lines"] not in by_lines]
    if missing:
        raise ValueError(f"no audit entry for the comment at lines {', '.join(missing[:8])}: one for every comment")
    used = set(taken)
    new: list[dict] = []
    out_rows: list[dict] = []
    for row in rows:
        r = by_lines[row["lines"]]
        verdict = str(r.get("verdict") or "").strip()
        if verdict not in VERDICTS:
            raise ValueError(f"lines {row['lines']}: verdict is {', '.join(VERDICTS)}, not {r.get('verdict')!r}")
        claim = r.get("claim")
        if (verdict == "claim") != isinstance(claim, dict):
            raise ValueError(f"lines {row['lines']}: a row says claim exactly when it gives a claim")
        done = {**row, "verdict": verdict}
        if isinstance(claim, dict):
            a, b = lines_of(row["lines"])                      # type: ignore[misc]
            if not claim.get("name") or not claim.get("says"):
                raise ValueError(f"lines {row['lines']}: a claim needs name and says")
            word = str(claim.get("checked") or "").strip().strip('"')
            if claim.get("checked") is True:
                word = "yes"
            if word not in CHECKED:
                raise ValueError(f"lines {row['lines']}: checked is one of {', '.join(CHECKED)}, in quotes")
            iid = _fresh(f"P:claim/{_clean_slug(claim.get('slug') or claim['name'])}", used)
            about = _item_ref(claim.get("about"), by_lean, ids) or fold(claim.get("about") or row.get("on") or
                                                                         "the file")
            it: dict = {"id": iid, "type": "claim", "name": fold(claim["name"])[:120],
                        "summary": _first_sentence(claim["says"]), "stance": "hearsay", "salience": "normal",
                        "about": about, "says": fold(claim["says"]), "checked": word}
            for k in CHECKED[word]:
                v = claim.get(k)
                if k == "by":
                    ref = _item_ref(v, by_lean, ids)
                    if ref is None:
                        raise ValueError(f"lines {row['lines']}: checked {word!r} names by, the declaration that "
                                         f"bears on it; {v!r} is none of the outline")
                    it["by"] = [ref]
                elif k == "mismatch":
                    if v not in MISMATCHES:
                        raise ValueError(f"lines {row['lines']}: mismatch is one of {', '.join(MISMATCHES)}")
                    it["mismatch"] = v
                elif k == "false-as-written":
                    it[k] = _yes_no(v, f"lines {row['lines']}: false-as-written")
                elif not (isinstance(v, str) and v.strip()):
                    raise ValueError(f"lines {row['lines']}: checked {word!r} needs {k}")
                else:
                    it[k] = fold(v)
            it["span"] = _code.span(fname, a, b)
            it["provenance"] = _code.prov([_code.loc(fname, a, b)], 0.5)
            new.append(it)
            done["claim"] = iid
        out_rows.append(done)
    for section, letter, kind in (("works", "E", "work"), ("people", "E", "person"), ("aims", "N", "aim")):
        for i, row in enumerate(data.get(section) or [], 1):
            if not isinstance(row, dict) or not row.get("name") or not row.get("summary"):
                raise ValueError(f"{section} entry {i} needs name, summary and lines")
            ab = lines_of(row.get("lines"))
            if ab is None or _lines_text(*ab) not in asked:
                raise ValueError(f"{section} entry {i}: lines must be those of the comment that names it")
            base_id = f"{letter}:{kind}/{_clean_slug(row.get('slug') or row['name'])}"
            if base_id in taken:
                continue
            new.append({"id": _fresh(base_id, used), "type": kind, "name": fold(row["name"])[:120],
                        "summary": fold(row["summary"]), "stance": "hearsay",
                        "provenance": _code.prov([_code.loc(fname, ab[0], ab[1])], 0.5)})
    return out_rows, new


def audit_comments(ctx: Any, t: Value, **mods: Any) -> Request | Value:
    """`construe t as comments with f`: every comment set against the Lean it stands over (5.2 stage 3). This is
    the one job that sees the comments."""
    w = mods.get("with")
    cat, items = _fabulam(w, "construe … as comments takes the fabulam so far: construe t as comments with f")
    fname, text = _file_name(t), t.text()
    rows = [dict(r) for r in cat.get("audit") or [] if isinstance(r, dict)]
    if not rows:
        return Value("fabula", {**_with_run(cat, ctx, None), "nodes": items})
    n = lines_in(text)
    taken = {str(it.get("id")) for it in items}
    outline = _yaml(_brief(items, DECL_KINDS, ("lean", "says")))
    schema = {"format": "yaml", "stamp": "engine", "says": COMMENTS_SAYS}
    starts = sorted({lines_of(r["lines"])[0] for r in rows} | {sp[1] for it in _decls(items, fname)       # type: ignore[index]
                                                              if (sp := _span_of(it))})
    parts = chunks_of(n, starts)

    def asked(a: int, b: int) -> list[dict]:
        return [r for r in rows if a <= lines_of(r["lines"])[0] <= b]            # type: ignore[index]

    def inputs(a: int, b: int) -> dict:
        shown = [{k: r[k] for k in ("lines", "kind", "on") if r.get(k) not in (None, "")} for r in asked(a, b)]
        return held(_strings({"fabulam": "comments", "name": str(cat.get("name") or fname), "path": fname,
                              "lines": f"{a}-{b} of {n}", "code": numbered(text, a, b), "outline": outline,
                              "comments": _yaml(shown)}), f"the audit of {fname}, lines {a} to {b},")

    def value(done: list[dict], new: list[dict], model: str | None) -> Value:
        c = _with_run(cat, ctx, model)
        c["audit"] = done
        return Value("fabula", {**c, "nodes": items + new})

    if len(parts) == 1:
        def parse(out: Any) -> Value:
            data = answer_mapping(out)
            done, new = parse_comments(data, fname=fname, cat=cat, items=items, rows=rows, taken=taken)
            return value(done, new, model_of(data))
        return Request(contract={"schema": schema, "repair": []}, inputs=inputs(1, n), parse=parse)
    done_all: list[dict] = []
    new_all: list[dict] = []
    model = None
    for p in parts:
        mine = asked(p["a"], p["b"])
        if not mine:
            continue
        err = None
        for _try in range(2):
            ins = inputs(p["a"], p["b"])
            if err:
                ins["failed"] = Value("string", err)
            cand = ctx.ask({"schema": schema, "repair": []}, ins)
            try:
                data = answer_mapping(cand.get("output"))
                done, new = parse_comments(data, fname=fname, cat=cat, items=items + new_all, rows=mine,
                                           taken=taken | {x["id"] for x in new_all})
                model = model or model_of(data)
                done_all += done
                new_all += new
                break
            except ValueError as e:
                err = str(e)
        else:
            raise MoveError(f"{fname}, lines {p['a']} to {p['b']}: the audit could not be read: {err}")
    return value(done_all, new_all, model)


# ---------------------------------------------------------------------------
# construe w as fit with f: the statement against the public wording (asks; no Lean)
# ---------------------------------------------------------------------------

def _statements(items: list[dict]) -> list[dict]:
    return [it for it in items if item_kind(it) == "statement"]


def fit_wording(ctx: Any, wording: Value, **mods: Any) -> Request | Value:
    """`construe w as fit with f`: each statement set against the public wording (5.2 stage 4). No Lean is sent."""
    w = mods.get("with")
    cat, items = _fabulam(w, "construe … as fit takes the fabulam so far: construe w as fit with f")
    statements = _statements(items)
    if not statements:
        return Value("fabula", {**_with_run(cat, ctx, None), "nodes": items})
    wname = _file_name(wording)
    by_lean, ids = _by_lean(items), {str(it.get("id")) for it in items}
    taken = set(ids)
    inputs = held(_strings({"fabulam": "fit", "name": str(cat.get("name") or ""), "source": wname,
                            "wording": numbered(wording.text()),
                            "statements": _yaml(_brief(items, ("statement",), ("lean", "says", "quantifiers")))}),
                  f"the fit of {wname}")

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        fits = data.get("fits")
        if not isinstance(fits, list):
            raise ValueError("the answer holds no fits: list")
        used = set(taken)
        new: list[dict] = [] if "E:work/wording" in taken else [wording_item(wname)]
        used.add("E:work/wording")
        seen: set[str] = set()
        for i, row in enumerate(fits, 1):
            of = _item_ref(row.get("of"), by_lean, ids) if isinstance(row, dict) else None
            st = next((s for s in statements if s["id"] == of), None)
            if st is None:
                raise ValueError(f"fits entry {i}: of names no statement of the fabulam")
            if of in seen:
                raise ValueError(f"two fits for {of}: one for every statement")
            seen.add(of)
            if row.get("how") not in FIT_HOW:
                raise ValueError(f"fits entry {i}: how is one of {', '.join(FIT_HOW)}")
            diffs = row.get("differences")
            if not isinstance(diffs, list):
                raise ValueError(f"fits entry {i}: differences is a list (empty when there is none)")
            conf = _confidence(row.get("confidence"), f"fits entry {i}")
            sp = _span_of(st)
            it = {"id": _fresh(f"P:fit/{str(of).split('/', 1)[1]}", used), "type": "fit",
                  "name": f"How {st['lean']} fits the public wording",
                  "summary": f"The statement is {str(row['how']).replace('-', ' ')} set against the wording.",
                  "stance": "opinion", "of": of, "against": "E:work/wording", "how": row["how"]}
            if isinstance(row.get("form-differences"), list):
                it["form-differences"] = [fold(x) for x in row["form-differences"] if fold(x)]
            it["differences"] = [fold(x) for x in diffs if fold(x)]
            it["confidence"] = conf
            it["provenance"] = _opinion([wname] + ([_code.loc(sp[0], sp[1], sp[2])] if sp else []), conf)
            new.append(it)
        missing = [s["lean"] for s in statements if s["id"] not in seen]
        if missing:
            raise ValueError(f"no fit for {', '.join(missing)}: one for every statement")
        for i, row in enumerate(data.get("claims") or [], 1):
            if not isinstance(row, dict) or not row.get("name") or not row.get("says"):
                raise ValueError(f"claims entry {i} needs name and says")
            new.append({"id": _fresh(f"P:claim/{_clean_slug(row.get('slug') or row['name'])}", used),
                        "type": "claim", "name": fold(row["name"])[:120], "summary": _first_sentence(row["says"]),
                        "stance": "hearsay", "salience": "normal",
                        "about": _item_ref(row.get("about"), by_lean, ids) or fold(row.get("about") or "the result"),
                        "says": fold(row["says"]), "checked": "not-checkable",
                        "provenance": _code.prov(["E:work/wording", wname], 0.5)})
        return Value("fabula", {**_with_run(cat, ctx, model_of(data)), "nodes": items + new})

    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": FIT_SAYS}, "repair": []},
                   inputs=inputs, parse=parse)


# ---------------------------------------------------------------------------
# construe t as yield with f: stated against shown (asks, once per statement)
# ---------------------------------------------------------------------------

_UP_TO = re.compile(r"\bup to\b(?:\s+(?:an?\s+|the\s+)?([a-z]+))?", re.I)


def holds_up_to(s: Any) -> bool:
    """Whether a text says "up to" of a bound: the phrase, not followed by one of `UP_TO_ALLOWED`."""
    return any((m.group(1) or "").lower() not in UP_TO_ALLOWED for m in _UP_TO.finditer(str(s or "")))


def _walk_strings(x: Any):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _walk_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk_strings(v)


def proof_ranges(items: list[dict], st: dict, fname: str) -> list[tuple[int, int]]:
    """The lines the yield job reads for one statement: its own, then the reached lemmas it rests on, the spine
    first and then by depth and by what they carry, within `CHUNK_LINES` lines in all."""
    out, total = [], 0
    rest = sorted((it for it in _decls(items, fname) if item_kind(it) == "lemma" and it.get("reached") == "yes"),
                  key=lambda it: (it.get("role") != "spine", int(it.get("depth") or 0),
                                  -int(it.get("carries") or 0)))
    for it in [st] + rest:
        sp = _span_of(it)
        if not sp:
            continue
        k = sp[2] - sp[1] + 1
        if out and total + k > CHUNK_LINES:
            continue
        out.append((sp[1], sp[2]))
        total += k
    return sorted(out)


def parse_yield(data: dict, *, fname: str, st: dict, items: list[dict], taken: set[str], many: bool
                ) -> tuple[list[dict], dict[str, list[dict]]]:
    """The yield job's answer for one statement as `(new items, slack by item id)`."""
    by_lean, ids = _by_lean(items), {str(it.get("id")) for it in items}
    by_id = {str(it.get("id")): it for it in items}
    y = data.get("yield")
    if not isinstance(y, dict):
        raise ValueError("the answer holds no yield: mapping")
    if not (isinstance(y.get("says"), str) and y["says"].strip()):
        raise ValueError("the yield has no says: what the proof's construction delivers")
    beyond = _yes_no(y.get("beyond"), "yield.beyond")
    stated = isinstance(y.get("as-statement"), str) and y["as-statement"].strip()
    if (beyond == "yes") != bool(stated):
        raise ValueError("yield.as-statement is given exactly when beyond is \"yes\"")
    bound = str(y.get("bound") or "").strip()
    if bound not in BOUNDS:
        raise ValueError(f"yield.bound is one of {', '.join(BOUNDS)}")
    conf = _confidence(y.get("confidence"), "yield")
    grounds = []
    for g in y.get("grounds") or []:
        of = _item_ref(g.get("of"), by_lean, ids) if isinstance(g, dict) else None
        if of is None or item_kind(by_id[of]) not in ("lemma", "statement", "step"):
            raise ValueError("a ground of the yield names a lemma, a statement or a step, with lines")
        a, b = _inside_lines(g.get("lines"), by_id[of], f"yield.grounds ({of})")
        grounds.append({"of": of, "lines": _lines_text(a, b)})
    if not grounds:
        raise ValueError("the yield has no grounds: [{of, lines}], at least one")
    chooses = []
    for i, c in enumerate(y.get("chooses") if isinstance(y.get("chooses"), list) else [None], 1):
        if c is None:
            raise ValueError("yield.chooses is a list ([] when the proof picks nothing)")
        if not isinstance(c, dict) or any(not c.get(k) for k in ("what", "where", "value", "gives", "best")):
            raise ValueError(f"yield.chooses entry {i} needs what, where, value, gives, best and confidence")
        where = _item_ref(c["where"], by_lean, ids)
        if where is None:
            raise ValueError(f"yield.chooses entry {i}: where names no item of the fabulam")
        chooses.append({"what": fold(c["what"]), "where": where, "value": fold(c["value"]), "gives": fold(c["gives"]),
                        "best": plain(c["best"]) if mc.is_pending(c["best"]) else fold(c["best"]),
                        "confidence": _confidence(c.get("confidence"), f"yield.chooses entry {i}")})
    trivial = []
    for i, c in enumerate(y.get("trivial") or [], 1):
        if not isinstance(c, dict) or any(not c.get(k) for k in ("case", "known", "delivered")) or \
                c.get("compares") not in ("above", "equal", "below"):
            raise ValueError(f"yield.trivial entry {i} needs case, known, delivered and compares (above, equal or "
                             "below)")
        trivial.append({k: (c[k] if k == "compares" else fold(c[k])) for k in ("case", "known", "delivered",
                                                                              "compares")})
    none = y.get("no-trivial")
    if not trivial and not (isinstance(none, str) and none.strip()):
        raise ValueError("the yield gives a trivial case, or no-trivial with one sentence saying why none exists")
    used = set(taken)
    tail = str(st["id"]).split("/", 1)[1]
    yid = _fresh(f"P:yield/{_clean_slug(y.get('slug') or 'what-the-proof-delivers')}" + (f"-{_clean_slug(tail)}"
                                                                                        if many else ""), used)
    it: dict = {"id": yid, "type": "yield", "name": fold(y.get("name") or "What the proof delivers")[:120],
                "summary": _first_sentence(y["says"]), "stance": "opinion", "of": st["id"], "beyond": beyond,
                "says": fold(y["says"])}
    if stated:
        it["as-statement"] = fold(y["as-statement"])
    it["needs"] = [fold(x) for x in y.get("needs") or [] if fold(x)]
    it["bound"] = bound
    it["chooses"] = chooses
    if trivial:
        it["trivial"] = trivial
    else:
        it["no-trivial"] = fold(none)
    it["grounds"] = grounds
    it["confidence"] = conf
    if isinstance(y.get("regime"), dict):
        it["regime"] = plain(y["regime"])
    it["provenance"] = _opinion([_code.loc(fname, *lines_of(g["lines"])) for g in grounds], conf)     # type: ignore[misc]
    if any(holds_up_to(s) for s in _walk_strings({k: v for k, v in it.items() if k != "provenance"})):
        raise ValueError('the yield says "up to": say at least, at most, exactly or between')
    new = [it]
    c = data.get("case")
    if not isinstance(c, dict) or any(not c.get(k) for k in ("name", "given", "expect")):
        raise ValueError("the answer holds no case: the worked example, {name, given, expect}, in small numbers")
    if not (re.search(r"\d", str(c["given"])) and re.search(r"\d", str(c["expect"]))):
        raise ValueError("the worked example's given and expect each hold a number")
    new.append({"id": _fresh(f"P:case/{_clean_slug(c.get('slug') or c['name'])}", used), "type": "case",
                "name": fold(c["name"])[:120], "summary": _first_sentence(c.get("summary") or c["expect"]),
                "stance": "opinion", "of": yid, "from": "worked", "stands": "inside", "given": fold(c["given"]),
                "expect": fold(c["expect"]), "confidence": conf, "provenance": _opinion([yid], conf)})
    for i, row in enumerate(data.get("constants") or [], 1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("says"):
            raise ValueError(f"constants entry {i} needs name, says and where")
        where = row.get("where")
        where = [_item_ref(x, by_lean, ids) for x in (where if isinstance(where, list) else [where])]
        if not where or None in where:
            raise ValueError(f"constants entry {i}: where names the items that hold it")
        k_it = {"id": _fresh(f"C:constant/{_clean_slug(row.get('slug') or row['name'])}", used), "type": "constant",
                "name": fold(row["name"])[:120], "summary": _first_sentence(row["says"]), "stance": "opinion",
                "says": fold(row["says"]), "where": where}
        for k in ("value", "why"):
            if row.get(k) not in (None, ""):
                k_it[k] = fold(row[k])
        k_it["confidence"] = _confidence(row.get("confidence") or conf, f"constants entry {i}")
        k_it["provenance"] = _opinion([loc for x in where if (sp := _span_of(by_id[x])) for loc in
                                       [_code.loc(sp[0], sp[1], sp[2])]] or [fname], row.get("confidence") or conf)
        new.append(k_it)
    slack: dict[str, list[dict]] = {}
    for i, row in enumerate(data.get("slack") or [], 1):
        on = _item_ref(row.get("on"), by_lean, ids) if isinstance(row, dict) else None
        if on is None or any(not row.get(k) for k in ("hypothesis", "would-suffice")):
            raise ValueError(f"slack entry {i} needs on, hypothesis, would-suffice, lines and confidence")
        a, b = _inside_lines(row.get("lines"), by_id[on], f"slack entry {i}")
        slack.setdefault(on, []).append({"hypothesis": fold(row["hypothesis"]),
                                         "would-suffice": fold(row["would-suffice"]), "lines": _lines_text(a, b),
                                         "confidence": _confidence(row.get("confidence"), f"slack entry {i}")})
    return new, slack


def tell_yield(ctx: Any, t: Value, **mods: Any) -> Request | Value:
    """`construe t as yield with f`: what each statement's proof delivers, set against what it says (5.2 stage 5,
    first half), comments blanked. Once per statement."""
    w = mods.get("with")
    cat, items = _fabulam(w, "construe … as yield takes the fabulam so far: construe t as yield with f")
    fname, text = _file_name(t), t.text()
    statements = [s for s in _statements(items) if (s.get("span") or {}).get("file") == fname]
    if not statements:
        return Value("fabula", {**_with_run(cat, ctx, None), "nodes": items})
    blank = blank_comments(text)
    n = lines_in(text)
    schema = {"format": "yaml", "stamp": "engine", "says": YIELD_SAYS}
    outline = _yaml(_brief(items, ("lemma", "step", "reliance", "definition"),
                           ("lean", "says", "role", "method", "why", "depth", "carries", "gives", "inside")))

    def inputs(st: dict) -> dict:
        ranges = proof_ranges(items, st, fname)
        code = "\n\n".join(f"lines {a}-{b}:\n{numbered(blank, a, b)}" for a, b in ranges)
        return held(_strings({"fabulam": "yield", "name": str(cat.get("name") or fname), "path": fname,
                              "lines": f"{', '.join(_lines_text(a, b) for a, b in ranges)} of {n}",
                              "statement": _yaml(_brief([st], ("statement",), ("lean", "says", "quantifiers"))),
                              "code": code, "outline": outline}), f"the yield of {st['lean']}")

    def value(new: list[dict], slack: dict, model: str | None) -> Value:
        nodes = []
        for it in items:
            if it.get("id") in slack:
                it = {**it, "slack": list(it.get("slack") or []) + slack[it["id"]]}
                it = _code._prov_last(it)
            nodes.append(it)
        return Value("fabula", {**_with_run(cat, ctx, model), "nodes": nodes + new})

    taken = {str(it.get("id")) for it in items}
    if len(statements) == 1:
        def parse(out: Any) -> Value:
            data = answer_mapping(out)
            new, slack = parse_yield(data, fname=fname, st=statements[0], items=items, taken=taken, many=False)
            return value(new, slack, model_of(data))
        return Request(contract={"schema": schema, "repair": []}, inputs=inputs(statements[0]), parse=parse)
    new_all: list[dict] = []
    slack_all: dict[str, list[dict]] = {}
    model = None
    for st in statements:
        err = None
        for _try in range(2):
            ins = inputs(st)
            if err:
                ins["failed"] = Value("string", err)
            cand = ctx.ask({"schema": schema, "repair": []}, ins)
            try:
                data = answer_mapping(cand.get("output"))
                new, slack = parse_yield(data, fname=fname, st=st, items=items,
                                         taken=taken | {x["id"] for x in new_all}, many=True)
                model = model or model_of(data)
                new_all += new
                for k, v in slack.items():
                    slack_all.setdefault(k, []).extend(v)
                break
            except ValueError as e:
                err = str(e)
        else:
            raise MoveError(f"{st['lean']}: the yield could not be read: {err}")
    return value(new_all, slack_all, model)


# ---------------------------------------------------------------------------
# construe t as stages with f, and derive repo with h: the argument folded (ask; no Lean)
# ---------------------------------------------------------------------------

def parse_stages(data: dict, *, items: list[dict], taken: set[str], sources: list[str], step_kinds: tuple[str, ...],
                 atem_of: str | None) -> tuple[list[dict], list[str], dict]:
    """The fold's answer as `(new items, teaching, atem)`: the stages, three to six readings, the decisions."""
    by_lean, ids = _by_lean(items), {str(it.get("id")) for it in items}
    by_id = {str(it.get("id")): it for it in items}
    rows = data.get("stages")
    if not isinstance(rows, list) or not rows:
        raise ValueError("the answer holds no stages: list")
    used = set(taken)
    new: list[dict] = []
    slugs: dict[str, str] = {}
    numbers: list[int] = []
    in_steps: set[str] = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or any(not row.get(k) for k in ("name", "says", "plain", "plain-if")):
            raise ValueError(f"stages entry {i} needs name, number, stage, says, plain, plain-if and steps")
        if row.get("stage") not in STAGE_WORDS:
            raise ValueError(f"stages entry {i}: stage is one of {', '.join(STAGE_WORDS)}")
        if isinstance(row.get("number"), bool) or not isinstance(row.get("number"), int):
            raise ValueError(f"stages entry {i}: number is its place in the logic, 1, 2, 3")
        steps = [_item_ref(x, by_lean, ids) for x in row.get("steps") or []]
        if not steps or None in steps or any(item_kind(by_id[s]) not in step_kinds for s in steps):
            raise ValueError(f"stages entry {i}: steps names the {', '.join(step_kinds)} items that make it up, by "
                             "id")
        if row["stage"] == "reduction" and not (isinstance(row.get("obvious"), str) and row["obvious"].strip()):
            raise ValueError("the reduction has no obvious: the obvious way and why it fails, or \"none: the "
                             "file's way is the obvious one\"")
        if holds_up_to(row["plain"]):
            raise ValueError(f'stages entry {i}: plain says "up to": say at least, at most, exactly or between')
        conf = _confidence(row.get("confidence") or "medium", f"stages entry {i}")
        iid = _fresh(f"C:part/{_clean_slug(row.get('slug') or row['name'])}", used)
        slugs[_clean_slug(row.get("slug") or row["name"])] = iid
        it: dict = {"id": iid, "type": "part", "name": fold(row["name"])[:120],
                    "summary": _first_sentence(row["says"]), "stance": "opinion", "division": "stage",
                    "number": row["number"], "stage": row["stage"], "says": fold(row["says"]),
                    "plain": fold(row["plain"]), "plain-if": fold(row["plain-if"])}
        if row["stage"] == "reduction":
            it["obvious"] = fold(row["obvious"])
        it["steps"] = steps
        if isinstance(row.get("regime"), dict):
            it["regime"] = plain(row["regime"])
        it["confidence"] = conf
        locs = [_code.loc(sp[0], sp[1], sp[2]) for s in steps if (sp := _span_of(by_id[s]))]
        it["provenance"] = _opinion(locs or sources, conf)
        new.append(it)
        numbers.append(row["number"])
        in_steps |= set(steps)
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise ValueError(f"the stages' numbers are {sorted(numbers)}; they run 1, 2, 3 with no gap")
    stages = [it for it in new]
    if sum(1 for it in stages if it["stage"] == "reduction") != 1:
        raise ValueError("exactly one stage is the reduction: what has to be shown or made large, and why")
    spine = [it["id"] for it in items if item_kind(it) == "lemma" and it.get("role") == "spine"]
    left = [s for s in spine if s not in in_steps]
    if left:
        raise ValueError(f"every spine lemma is in the steps of a stage; {', '.join(left[:6])} is in none")
    # -- the teaching order: the model's order within a stage word, the words in the order of the design's 1.4
    said = [slugs.get(_clean_slug(x)) or (x if x in {s["id"] for s in stages} else None)
            for x in data.get("teaching") or []]
    if None in said or len(set(said)) != len(said):
        raise ValueError("teaching lists the stages' slugs, each once, in the order a teacher would tell them")
    said += [s["id"] for s in sorted(stages, key=lambda s: s["number"]) if s["id"] not in said]
    word = {s["id"]: STAGE_WORDS.index(s["stage"]) for s in stages}
    teaching = sorted(said, key=lambda x: word[x])
    # -- readings
    readings = data.get("readings")
    if not isinstance(readings, list) or not 1 <= len(readings) <= 6:
        raise ValueError("readings holds three to six key ideas, each with grounds (a short file may hold fewer, "
                         "never none)")
    stage_ids = {s["id"] for s in stages}
    for i, row in enumerate(readings, 1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("summary"):
            raise ValueError(f"readings entry {i} needs name, summary, of, grounds and confidence")
        of = row.get("of")
        of = [slugs.get(_clean_slug(x)) if slugs.get(_clean_slug(x)) in stage_ids else _item_ref(x, by_lean, ids)
              for x in (of if isinstance(of, list) else [of])]
        if not of or None in of:
            raise ValueError(f"readings entry {i}: of names the statement or the stage it reads")
        grounds = []
        for g in row.get("grounds") or []:
            gof = _item_ref(g.get("of"), by_lean, ids) if isinstance(g, dict) else None
            if gof is None or _span_of(by_id[gof]) is None:
                raise ValueError(f"readings entry {i}: a ground names an item with lines, {{of, lines}}")
            a, b = _inside_lines(g.get("lines"), by_id[gof], f"readings entry {i}")
            grounds.append({"of": gof, "lines": _lines_text(a, b)})
        if not grounds:
            raise ValueError(f"readings entry {i} has no grounds: [{{of, lines}}], at least one")
        conf = _confidence(row.get("confidence"), f"readings entry {i}")
        it = {"id": _fresh(f"P:reading/{_clean_slug(row.get('slug') or row['name'])}", used), "type": "reading",
              "name": fold(row["name"])[:120], "summary": fold(row["summary"]), "stance": "opinion", "of": of,
              "whose": {"by": "model"}, "grounds": grounds, "confidence": conf}
        if isinstance(row.get("regime"), dict):
            it["regime"] = plain(row["regime"])
        it["provenance"] = _opinion([_code.loc(_span_of(by_id[g["of"]])[0], *lines_of(g["lines"]))       # type: ignore[index,misc]
                                     for g in grounds], conf)
        new.append(it)
    for i, row in enumerate(data.get("decisions") or [], 1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("summary"):
            raise ValueError(f"decisions entry {i} needs name and summary")
        it = {"id": _fresh(f"N:decision/{_clean_slug(row.get('slug') or row['name'])}", used), "type": "decision",
              "name": fold(row["name"])[:120], "summary": fold(row["summary"]), "stance": "opinion"}
        for k in ("chose", "over", "because"):
            if row.get(k) not in (None, "", []):
                it[k] = plain(row[k]) if isinstance(row[k], list) else fold(row[k])
        it["provenance"] = _opinion(sources, row.get("confidence") or "medium")
        new.append(it)
    a = data.get("atem")
    if not isinstance(a, dict) or any(not (isinstance(a.get(k), str) and a[k].strip()) for k in
                                      ("line", "focus", "push", "pull")):
        raise ValueError("the answer holds no atem: {line, focus, push, pull}")
    atem = {**({"of": atem_of} if atem_of else {}), **{k: fold(a[k]) for k in ("line", "focus", "push", "pull")}}
    return new, teaching, atem


def _atem_of(cat: dict, items: list[dict]) -> str | None:
    of = (cat.get("atem") or {}).get("of") if isinstance(cat.get("atem"), dict) else None
    ids = {it.get("id") for it in items}
    return of if of in ids else next((it["id"] for it in _statements(items)), None)


def fold_argument(ctx: Any, t: Value, **mods: Any) -> Request:
    """`construe t as stages with f`: the stages, the teaching order, the readings and the atem (5.2 stage 5, second
    half), from the items alone. No Lean is sent."""
    w = mods.get("with")
    cat, items = _fabulam(w, "construe … as stages takes the fabulam so far: construe t as stages with f")
    fname = _file_name(t)
    told = _yaml(_brief(items, ("statement", "lemma", "step", "definition", "reliance", "yield", "case", "constant",
                                "claim", "fit"),
                        ("lean", "name", "says", "quantifiers", "role", "method", "why", "depth", "carries",
                         "reached", "inside", "gives", "known-as", "case", "beyond", "as-statement", "bound",
                         "chooses", "trivial", "given", "expect", "value", "checked", "how", "differences")))
    inputs = held(_strings({"fabulam": "stages", "name": str(cat.get("name") or fname), "items": told}),
                  f"the fold of {fname}")
    taken = {str(it.get("id")) for it in items}
    shown = [it for it in items if not (item_kind(it) == "lemma" and it.get("reached") == "no")]

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        new, teaching, atem = parse_stages(data, items=shown, taken=taken, sources=[fname],
                                          step_kinds=("lemma", "statement", "step", "definition"),
                                          atem_of=_atem_of(cat, items))
        model = model_of(data)
        # `completeness: full` is the last program's to write (the job writes it when the questions have landed)
        c = _with_run(cat, ctx, model, at=_code.stamp_at(ctx), mode="model")
        c.update({"atem": atem, "teaching": teaching})
        return Value("fabula", {**c, "nodes": items + new}, origin={"fold": {"before": sorted(taken)}})

    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": STAGES_SAYS}, "repair": []},
                   inputs=inputs, parse=parse)


def _component_summary(it: dict) -> dict:
    row = {"id": it.get("id"), "name": it.get("name")}
    for k in ("does", "stages", "counts", "completeness", "offers"):
        if k in it and not mc.is_pending(it[k]):
            row[k] = it[k]
    text = _yaml(row)
    if len(text) > SUMMARY_CHARS and isinstance(row.get("does"), str):
        over = len(text) - SUMMARY_CHARS
        row["does"] = row["does"][: max(40, len(row["does"]) - over - 1)] + "…"
    return row


def head_roles(data: dict, items: list[dict]) -> list[dict]:
    """The head's items with each crossing lemma's role in the archive's argument: the fold's own judgement where
    it gives one (`roles: [{of, role, why}]`), else the lemma's role in its own part. A spine lemma says why."""
    by_lean, ids = _by_lean(items), {str(it.get("id")) for it in items}
    said: dict[str, dict] = {}
    for i, row in enumerate(data.get("roles") or [], 1):
        of = _item_ref(row.get("of") or row.get("lean"), by_lean, ids) if isinstance(row, dict) else None
        if of is None or row.get("role") not in ROLES:
            raise ValueError(f"roles entry {i} is {{of: a crossing lemma, role: {' | '.join(ROLES)}, why}}")
        said[of] = row
    out = []
    for it in items:
        if item_kind(it) == "lemma" and it.get("reached") == "yes":
            row = said.get(it["id"]) or {}
            role = row.get("role") or (it.get("role-there") if it.get("role-there") in ROLES else "support")
            why = row.get("why") if isinstance(row.get("why"), str) and row["why"].strip() else it.get("why-there")
            it = {**it, "role": role}
            if role == "spine":
                if not (isinstance(why, str) and why.strip()):
                    raise ValueError(f"{it['lean']} is spine here and has no why: give it under roles")
                it["why"] = fold(why)
            it = _code._prov_last(it)
        out.append(it)
    return out


def fold_head(ctx: Any, repo: Value, **mods: Any) -> Request | Value:
    """`derive repo with h`: a head's own stages, teaching order, readings and atem (the design's 4.3), from its parts'
    summaries and its crossing items. It never sees Lean. A head of more than `HEAD_PARTS` parts folds in rounds,
    then once over the rounds' notes."""
    h = mods.get("with")
    cat, items = _fabulam(h, "derive of a folder of Lean folds its head: derive repo with h")
    if not is_head(cat):
        raise MoveError("derive repo with h folds a head fabulam; this fabulam names no parts")
    comps = [it for it in items if item_kind(it) == "component"
             and int((it.get("counts") or {}).get("reached") or 0) > 0]
    unread = [c["name"] for c in comps if mc.is_pending(c.get("does"))]
    if unread:
        raise MoveError(f"{unread[0]} has not been read: a head is folded when every reached part has landed")
    crossing = sorted(_decls(items), key=lambda it: -int(it.get("carries") or 0))[:HEAD_CROSSING]
    shown = _yaml(_brief(crossing, DECL_KINDS, ("lean", "says", "role-there", "why-there", "depth", "carries")))
    yields = _yaml(_brief(items, ("yield", "case"), ("of", "says", "as-statement", "beyond", "given", "expect")))
    name = str(cat.get("name") or "")
    schema = {"format": "yaml", "stamp": "engine", "says": STAGES_SAYS}
    taken = {str(it.get("id")) for it in items}
    rounds = [comps[i:i + HEAD_PARTS] for i in range(0, len(comps), HEAD_PARTS)] or [[]]
    notes: list[str] = []
    if len(rounds) > 1:
        for k, group in enumerate(rounds, 1):
            ins = held(_strings({"fabulam": "head", "name": name, "round": f"{k} of {len(rounds)}",
                                 "components": _yaml([_component_summary(c) for c in group]), "crossing": shown}),
                       f"round {k} of the fold of {name}")
            err = None
            for _try in range(2):
                if err:
                    ins = {**ins, "failed": Value("string", err)}
                cand = ctx.ask({"schema": {"format": "yaml", "stamp": "engine", "says": "a YAML mapping: notes, a "
                                           "list of sentences on what these parts do for the argument"},
                                "repair": []}, ins)
                try:
                    got = _notes(answer_mapping(cand.get("output")))
                    if not got:
                        raise ValueError("the answer holds no notes: list of sentences")
                    notes += got
                    break
                except ValueError as e:
                    err = str(e)
            else:
                raise MoveError(f"round {k} of the fold could not be read: {err}")
    inputs = held(_strings({"fabulam": "head", "name": name,
                            "components": None if notes else _yaml([_component_summary(c) for c in rounds[0]]),
                            "notes": _yaml(notes) if notes else None, "crossing": shown,
                            "yields": yields if yields.strip() not in ("", "[]") else None}),
                  f"the fold of {name}")

    def read(out: Any) -> Value:
        data = answer_mapping(out)
        judged = head_roles(data, items)
        new, teaching, atem = parse_stages(data, items=judged, taken=taken, sources=[f"{name}.fabulam.cosm"],
                                          step_kinds=DECL_KINDS, atem_of=_atem_of(cat, items))
        model = model_of(data)
        c = _with_run(cat, ctx, model, at=_code.stamp_at(ctx), mode="model", completeness="full")
        c.update({"atem": atem, "teaching": teaching})
        return Value("fabula", {**c, "nodes": judged + new}, origin={"fold": {"before": sorted(taken)}})

    if len(rounds) == 1:
        return Request(contract={"schema": schema, "repair": []}, inputs=inputs, parse=read)
    err = None
    for _try in range(2):
        if err:
            inputs = {**inputs, "failed": Value("string", err)}
        cand = ctx.ask({"schema": schema, "repair": []}, inputs)
        try:
            return read(cand.get("output"))
        except ValueError as e:
            err = str(e)
    raise MoveError(f"the fold of {name} could not be read: {err}")


def derive_branch(ctx: Any, x: Value, mods: dict) -> Any:
    """`derive`'s proof branches: `as proof`, and a folder folded with a head fabulam; None for any other call."""
    if mods.get("as") == "proof":
        return read_proof(ctx, x, **mods)
    w = mods.get("with")
    if isinstance(x, Value) and x.type == "folder" and isinstance(w, Value) and w.type == "fabula" \
            and fabula_doc(w)[0].get("flavour") == FLAVOUR:
        return fold_head(ctx, x, **mods)
    return None


def construe(ctx: Any, t: Value, **mods: Any) -> Any:
    """`construe`'s four proof axes."""
    axis = mods.get("as")
    return {"comments": audit_comments, "fit": fit_wording, "yield": tell_yield, "stages": fold_argument}[axis](
        ctx, t, **mods)


# ---------------------------------------------------------------------------
# entail f as expert | student | everyone: the pshort (asks; the Lean is never read here)
# ---------------------------------------------------------------------------

_STRIP = frozenset(("span", "lines", "provenance", "made", "digest", "sha256", "path", "scope", "stated-in",
                    "told-in"))
_CITES = re.compile(r"\[\s*((?:[A-Z]:[a-z][a-z0-9-]*/[^\]\s,;]+)(?:\s*[,;]\s*(?:[A-Z]:[a-z][a-z0-9-]*/[^\]\s,;]+))*)"
                    r"\s*\]")
_FOOT = re.compile(r"^\*a pshort of (?P<f>\S+), at (?P<density>expert|student|everyone), entailed apart on "
                   r"(?P<day>\d{4}-\d{2}-\d{2}) by (?P<who>[^;*]+?)(?:; left out for length: (?P<left>[^*]+))?\*$")


def _stripped(x: Any) -> Any:
    """An item as the entailer sees it: no span, no lines, no path, nothing that points into the source."""
    if isinstance(x, dict):
        return {k: _stripped(v) for k, v in x.items() if k not in _STRIP}
    if isinstance(x, list):
        return [_stripped(v) for v in x]
    return x


def pshort_view(cat: dict, items: list[dict]) -> tuple[str, list[str]]:
    """The fabulam as an entailment carries it, as YAML, and what was left out for length (`PSHORT_CHARS`): the
    bookkeeping lemmas first, then the support lemmas' method."""
    keep = [it for it in items if item_kind(it) not in ("file", "question", "session")
            and not (item_kind(it) in DECL_KINDS and it.get("reached") == "no")]
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    head = {"name": cat.get("name"), "atem": _stripped(cat.get("atem")), "teaching": cat.get("teaching"),
            "source": {k: src[k] for k in ("language", "toolchain", "module", "target", "read", "checking")
                       if k in src},
            "audit": [_stripped(r) for r in cat.get("audit") or [] if isinstance(r, dict)
                      and r.get("verdict") == "claim"]}
    left: list[str] = []

    def dump(rows: list[dict]) -> str:
        return _yaml({**head, "items": [_stripped(it) for it in rows]})
    text = dump(keep)
    if len(text) > PSHORT_CHARS:
        keep = [it for it in keep if it.get("role") != "bookkeeping"]
        left.append("the bookkeeping lemmas")
        text = dump(keep)
    if len(text) > PSHORT_CHARS:
        keep = [{k: v for k, v in it.items() if not (k == "method" and it.get("role") == "support")} for it in keep]
        left.append("the support lemmas' method")
        text = dump(keep)
    return text, left


def fabulam_file(cat: dict, fab: Value | None) -> str:
    if fab is not None and fab.path is not None and fab.path.name.endswith(".fabulam.cosm"):
        return fab.path.name
    return f"{cat.get('name') or 'fabulam'}.fabulam.cosm"


def must_cite(cat: dict, items: list[dict], density: str) -> list[str]:
    """The ids a pshort at one density must cite (2.C): every yield, every fit, `P:claim/checking`; at `everyone`
    every stage and a worked example."""
    out = [it["id"] for it in items if item_kind(it) in ("yield", "fit")] + ["P:claim/checking"]
    if density == "everyone":
        out += [x for x in cat.get("teaching") or [] if isinstance(x, str)]
    return out


def pshort_fixed(cat: dict, items: list[dict], fab: Value | None, density: str) -> list[str]:
    """The three lines rules write at the top of a pshort (the design's 5.4)."""
    checking = next((it for it in items if it.get("id") == "P:claim/checking"), None)
    if checking is None or not isinstance(checking.get("says"), str):
        raise MoveError("the fabulam holds no P:claim/checking: survey its source again")
    return [f"# {cat.get('name')}, for {READERS[density]}",
            f"*A pshort of {fabulam_file(cat, fab)} at {density}. It is a guide to a formal proof. It is not a "
            "proof.*",
            f"*{checking['says']}* [P:claim/checking]"]


def pshort_footer(cat: dict, fab: Value | None, density: str, day: str, who: str, left: list[str] | None = None
                  ) -> str:
    tail = f"; left out for length: {' and '.join(left)}" if left else ""
    return f"*a pshort of {fabulam_file(cat, fab)}, at {density}, entailed apart on {day} by {who}{tail}*"


def pshort_text(fixed: list[str], body: str, footer: str) -> str:
    return "\n\n".join(fixed + [body.strip(), footer]) + "\n"


def entail_pshort(ctx: Any, fab: Value, density: str, **mods: Any) -> Request:
    """`entail f as expert | student | everyone`: the pshort (the design's 5.4), from the fabulam's items alone."""
    cat, items = _fabulam(fab, "a pshort is entailed from a fabulam: entail f as expert, student or everyone")
    if not cat.get("teaching") or mc.is_pending((cat.get("atem") or {}).get("line")):
        raise MoveError(f"{cat.get('name')} is an outline: a pshort is entailed once the stages have landed")
    fixed = pshort_fixed(cat, items, fab, density)
    view, left = pshort_view(cat, items)
    lo, hi = WORDS[density]
    inputs = held(_strings({"fabulam": "pshort", "density": density, "name": str(cat.get("name") or ""),
                            "items": view, "must": _yaml(must_cite(cat, items, density)),
                            "words": f"{lo} to {hi}"}), f"the pshort of {cat.get('name')} at {density}")
    sent = [{k: v.text() for k, v in inputs.items()}]

    def parse(out: Any) -> Value:
        data = answer_mapping(out)
        body = data.get("body")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("the answer holds no body: a YAML mapping with one key, body, the markdown as a block")
        body = body.replace("\r\n", "\n").strip()
        first = body.split("\n", 1)[0].strip()
        if first.startswith("# ") or "A pshort of" in body or _FOOT.match(body.rsplit("\n", 1)[-1].strip()):
            raise ValueError("write the body alone: the title, the two lines under it and the footer are written "
                             "by rule")
        who = model_of(data) or "model"
        text = pshort_text(fixed, body, pshort_footer(cat, fab, density, utc_day(ctx), who, left))
        return short_value(text, fabula=fab, order="told", density=density, requests=sent, left=left)

    # the answer is YAML so that the host stamps the model's name into it: the footer names the model, and a
    # replay names it again from the record
    return Request(contract={"schema": {"format": "yaml", "stamp": "engine", "says": PSHORT_SAYS}, "repair": []},
                   inputs=inputs, parse=parse)


def entail_branch(ctx: Any, x: Value, mods: dict) -> Any:
    a = mods.get("as")
    return entail_pshort(ctx, x, a, **mods) if a in DENSITIES else None


# -- reading a pshort back ------------------------------------------------------------------------------------------

def pshort_parts(text: str) -> dict:
    """A pshort's text taken apart: `{title, second, third, body: [paragraph], footer}`. A paragraph is its text."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()) if p.strip()]
    get = lambda i: paras[i] if len(paras) > i else ""                     # noqa: E731
    return {"title": get(0), "second": " ".join(get(1).split()), "third": " ".join(get(2).split()),
            "body": paras[3:-1] if len(paras) > 4 else [], "footer": " ".join(paras[-1].split()) if paras else ""}


def covered(paragraph: str) -> tuple[list[tuple[str, list[str]]], str]:
    """A paragraph's sentences with the citations that cover each, and the words no citation covers. A group of
    citations covers the sentence it closes and the sentences before it, back to the group before."""
    text = " ".join(paragraph.split())
    rows: list[tuple[str, list[str]]] = []
    at = 0
    for m in _CITES.finditer(text):
        ids = [c.strip() for c in re.split(r"[,;]", m.group(1)) if c.strip()]
        run = text[at:m.start()].strip()
        run = re.sub(r"^[.!?)\"'”’]+\s*", "", run)          # the stop of the sentence the last group closed
        for s in split_sentences(run):
            if s.strip():
                rows.append((s.strip(), ids))
        at = m.end()
    rest = re.sub(r"^[.!?)\"'”’\s]+", "", text[at:]).strip()
    return rows, rest


def pshort_rows(text: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Every covered sentence of a pshort's body with its citations, and every stretch of body no citation covers.
    A heading is no sentence."""
    rows: list[tuple[str, list[str]]] = []
    bare: list[str] = []
    for para in pshort_parts(text)["body"]:
        lines = [ln for ln in para.split("\n") if not re.match(r"^\s{0,3}#{1,6}\s", ln)]
        if not lines:
            continue
        got, rest = covered(" ".join(lines))
        rows += got
        if rest:
            bare.append(rest)
    return rows, bare


def _pshort_of(output: Value, inputs: dict) -> tuple[dict, list[dict], str, Value | None]:
    """`(catalog, items, density, the fabulam)` of a pshort being checked."""
    t = entailment_of(output) or {}
    fab = t.get("fabula") if isinstance(t.get("fabula"), Value) else next(
        (v for v in inputs.values() if isinstance(v, Value) and v.type == "fabula"), None)
    cat, items = fabula_doc(fab) if fab is not None else ({}, [])
    density = t.get("density")
    if density not in DENSITIES:
        m = _FOOT.match(pshort_parts(output.text())["footer"])
        density = m.group("density") if m else ""
    return {k: plain(v) for k, v in cat.items() if k != "nodes"}, [plain(it) for it in items], str(density), fab


def _all_cites(text: str) -> list[str]:
    parts = pshort_parts(text)
    out: list[str] = []
    for chunk in [parts["third"]] + parts["body"]:
        for m in _CITES.finditer(chunk):
            out += [c.strip() for c in re.split(r"[,;]", m.group(1)) if c.strip()]
    return out


@check("cites-resolve")
def _cites_resolve(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every id in square brackets names an item of the fabulam (2.C)."""
    _cat, items, _d, fab = _pshort_of(output, inputs)
    if fab is None:
        return False, "no fabulam to look the pshort's citations up in"
    ids = {str(it.get("id")) for it in items}
    bad = sorted({c for c in _all_cites(output.text()) if c not in ids})
    return (False, f"the pshort cites {', '.join(bad[:4])}, which the fabulam does not hold") if bad else (True, "")


@check("every-sentence-cited")
def _every_sentence_cited(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every sentence of the body is covered by a group of citations, so every paragraph ends in one (2.C)."""
    rows, bare = pshort_rows(output.text())
    if bare:
        return False, f"no citation covers: {bare[0][:120]}"
    if not rows:
        return False, "the pshort's body holds no sentence"
    return True, f"{len(rows)} sentences, each covered"


@check("yield-cited")
def _yield_cited(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every `P:yield`, every `P:fit` and `P:claim/checking` is cited (2.C)."""
    _cat, items, _d, _fab = _pshort_of(output, inputs)
    cited = set(_all_cites(output.text()))
    want = [it["id"] for it in items if item_kind(it) in ("yield", "fit")] + ["P:claim/checking"]
    missing = [i for i in want if i not in cited]
    return (False, f"the pshort does not cite {', '.join(missing[:4])}") if missing else (True, "")


@check("teaching-followed")
def _teaching_followed(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every stage is cited, and the stages are first cited in the order of `teaching`: held at `everyone`, a note
    at the other densities (2.C)."""
    cat, _items, density, _fab = _pshort_of(output, inputs)
    teaching = [x for x in cat.get("teaching") or [] if isinstance(x, str)]
    first: list[str] = []
    for c in _all_cites(output.text()):
        if c in teaching and c not in first:
            first.append(c)
    why = ""
    missing = [x for x in teaching if x not in first]
    if missing:
        why = f"the stage {missing[0]} is not cited"
    elif first != teaching:
        k = next(i for i, (a, b) in enumerate(zip(first, teaching)) if a != b)
        why = f"the stages are not told in the teaching order: {first[k]} comes where {teaching[k]} is due"
    if why and density == "everyone":
        return False, why
    return True, (f"a note: {why}" if why else "")


@check("no-up-to")
def _no_up_to(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No sentence covered by a citation of a `P:yield` holds "up to" (2.C)."""
    for s, ids in pshort_rows(output.text())[0]:
        if any(i.startswith("P:yield/") for i in ids) and holds_up_to(s):
            return False, f'a sentence that tells the yield says "up to": {s[:120]}'
    return True, ""


@check("example-worked")
def _example_worked(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """At `everyone`, a worked `P:case` is cited (2.C)."""
    _cat, items, density, _fab = _pshort_of(output, inputs)
    worked = {it["id"] for it in items if item_kind(it) == "case" and it.get("from") == "worked"}
    if set(_all_cites(output.text())) & worked:
        return True, ""
    if density == "everyone":
        return False, "the pshort for everyone cites no worked example"
    return True, "a note: no worked example is cited"


def _said_of_check(s: str) -> str | None:
    low = s.lower()
    return next((w for w in CHECK_WORDS if w in low), None)


@check("checking-told")
def _checking_told(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """"machine-checked", "verified", "certified" and "proved correct" appear only in a sentence covered by
    `P:claim/checking`; the second line is the fixed line, and the third the checking sentence (2.C)."""
    cat, items, density, fab = _pshort_of(output, inputs)
    parts = pshort_parts(output.text())
    try:
        fixed = pshort_fixed(cat, items, fab, density) if density in DENSITIES else None
    except MoveError as e:
        return False, str(e)
    if fixed is None:
        return False, "the pshort names no density"
    if parts["title"] != fixed[0] or parts["second"] != fixed[1]:
        return False, "the pshort's first two lines are not the fixed lines"
    if parts["third"] != " ".join(fixed[2].split()):
        return False, "the pshort's third line is not the sentence of P:claim/checking"
    if not _FOOT.match(parts["footer"]):
        return False, "the pshort's last line is not its footer"
    rows, bare = pshort_rows(output.text())
    for s in bare:
        if (w := _said_of_check(s)):
            return False, f'"{w}" is said outside the checking sentence: {s[:120]}'
    for s, ids in rows:
        if (w := _said_of_check(s)) and "P:claim/checking" not in ids:
            return False, f'"{w}" is said in a sentence P:claim/checking does not cover: {s[:120]}'
    return True, ""


@check("confidence-told")
def _confidence_told(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A sentence covered only by items of `confidence: low` holds a hedge: a warning, never a refusal (2.C)."""
    _cat, items, _d, _fab = _pshort_of(output, inputs)
    low = {str(it.get("id")) for it in items if it.get("confidence") == "low"}
    for s, ids in pshort_rows(output.text())[0]:
        if ids and set(ids) <= low and not any(re.search(rf"\b{re.escape(h)}\b", s, re.I) for h in HEDGES):
            return True, f"a warning: a sentence that rests only on low confidence holds no hedge: {s[:100]}"
    return True, ""


_ONE_LETTER = re.compile(r"(?<![\w'’])([A-Za-z])(?![\w'’])")


@check("symbols-worded")
def _symbols_worded(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """At `everyone`, each one-letter name's first sentence also holds the words that say what it is: a warning,
    never a refusal (2.C)."""
    _cat, _items, density, _fab = _pshort_of(output, inputs)
    if density != "everyone":
        return True, ""
    seen: set[str] = set()
    for s, _ids in pshort_rows(output.text())[0]:
        for m in _ONE_LETTER.finditer(s):
            x = m.group(1)
            if x in ("a", "A", "I") or x in seen:
                continue
            seen.add(x)
            if not any(w in s.lower() for w in WORDED):
                return True, f"a warning: {x} is used before it is said what it is: {s[:100]}"
    return True, ""


def _body_words(text: str) -> str:
    return _CITES.sub(" ", "\n\n".join(pshort_parts(text)["body"]))


def _pshort_nothing_added(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every name, number and word outside the dictionary in the pshort's body is in the fabulam (2.C): the pshort's
    "nothing invented". Without FEED only names and numbers are held to the fabulam."""
    cat, items, _d, fab = _pshort_of(output, inputs)
    if fab is None:
        return False, "no fabulam to hold the pshort's words to"
    have = {w.lower() for w in words_in(text_blob(cat, items))}
    have |= {w.lower() for w in words_in(_yaml(cat.get("source") or {}))}
    lookup = (getattr(ctx, "engines", None) or {}).get("feed")
    unknown: list[str] = []
    for sentence in split_sentences(" ".join(_body_words(output.text()).split())):
        ws = words_in(re.sub(r"^\s{0,3}#{1,6}\s+", "", sentence))
        for k, w in enumerate(ws):
            lw = w.lower().replace("’", "'")
            base = lw[:-2] if lw.endswith("'s") else lw
            if lw in have or base in have:
                continue
            if any(ch.isdigit() for ch in w):
                return False, f"the number {w} is not in the fabulam"
            if w[:1].isupper() and k > 0 and not w.isupper():
                return False, f"the name {w} is not in the fabulam"
            if len(w) > 1:
                unknown.append(lw)
    if not unknown or lookup is None:
        return True, "" if lookup is not None else "FEED is not here; only names and numbers were held to the fabulam"
    words = list(dict.fromkeys(unknown))
    try:
        found = lookup(words) or {}
    except Exception:  # noqa: BLE001 - a FEED that cannot be read grounds nothing, and says so
        return False, "FEED could not be read"
    for w in words:
        if not isinstance(found.get(w), dict):
            try:
                one = lookup([w]) or {}
            except Exception:  # noqa: BLE001
                return False, "FEED could not be read"
            if not any(isinstance(x, dict) for x in one.values()):
                return False, f"the word {w} is in neither the dictionary nor the fabulam"
    return True, ""


def _pshort_apart(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No request of the entailment carried a span, lines, the source's path or the source's text (2.C). The
    requests ride with the pshort while the run holds it."""
    t = entailment_of(output) or {}
    sent = t.get("requests")
    if not isinstance(sent, list) or not sent:
        return False, "the pshort carries no record of what was sent: it was not entailed apart here"
    cat, items, _d, _fab = _pshort_of(output, inputs)
    src = cat.get("source") if isinstance(cat.get("source"), dict) else {}
    paths = {str(src.get("path") or "")} | {str(it.get("path")) for it in items if item_kind(it) == "file"}
    paths = {p for p in paths if p and p != "None"} | {p.rsplit("/", 1)[-1] for p in paths if p and p != "None"}
    for req in sent:
        for name, text in (req or {}).items():
            text = str(text)
            if re.search(r"(?m)^\s*(?:-\s+)?(?:span|lines):", text) or re.search(r"[{,]\s*(?:span|lines):", text):
                return False, f"the request's {name} carries a span or lines"
            for p in paths:
                if p in text:
                    return False, f"the request's {name} carries the source's path {p}"
            if name in ("code", "source", "lean"):
                return False, f"the request carries {name}: an entailment apart never reads the Lean"
    return True, ""


def _pshort_length(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The body's words are within the density's range (the design's 5.4)."""
    _cat, _items, density, _fab = _pshort_of(output, inputs)
    if density not in WORDS:
        return False, "the pshort names no density"
    lo, hi = WORDS[density]
    k = len(words_in(_body_words(output.text())))
    if k < lo or k > hi:
        return False, f"the body is {k} words; a pshort at {density} is {lo} to {hi}"
    return True, f"{k} words"


def _pshort_footer(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The last line is the pshort's footer: its fabulam's file, its density, the run's day in UTC, the model."""
    cat, _items, density, fab = _pshort_of(output, inputs)
    foot = pshort_parts(output.text())["footer"]
    m = _FOOT.match(foot)
    if not m:
        return False, f"the last line is not a pshort's footer: {foot[:80]}"
    if m.group("f") != fabulam_file(cat, fab):
        return False, f"the footer names {m.group('f')}, not {fabulam_file(cat, fab)}"
    if density and m.group("density") != density:
        return False, f"the footer says {m.group('density')}, and the pshort is entailed at {density}"
    if ctx is not None and m.group("day") != utc_day(ctx):
        return False, f"the footer's day is {m.group('day')}, the run's {utc_day(ctx)}"
    return True, ""


for _d in DENSITIES:
    check("nothing-added", kind=_d)(_pshort_nothing_added)
    check("apart", kind=_d)(_pshort_apart)
    check("length", kind=_d)(_pshort_length)
    check("footer", kind=_d)(_pshort_footer)


# ---------------------------------------------------------------------------
# The checks against the source (2.B): each reads the Lean only through the syntax engine's answer
# ---------------------------------------------------------------------------

def _doc(output: Value, inputs: dict) -> tuple[dict, list[dict]]:
    """The fabulam a check reads: a reading laid into the fabulam it was read with, else the output."""
    whole = _code.joined(output, inputs) or output
    cat, items = fabula_doc(whole)
    return {k: plain(v) for k, v in cat.items() if k != "nodes"}, [plain(it) for it in items]


def _text_in(inputs: dict) -> Value | None:
    return next((v for v in inputs.values() if isinstance(v, Value) and v.type != "fabula"
                 and isinstance(v.payload, str) and _file_name(v).endswith(".lean")), None)


def _source(output: Value, inputs: dict, ctx: Any) -> tuple[dict, list[dict], str, str, dict] | str:
    """`(catalog, items, file name, text, outline)`, or the words that say what is missing."""
    cat, items = _doc(output, inputs)
    t = _text_in(inputs)
    if t is None:
        return "no Lean file among the inputs to hold the fabulam to"
    fname = _file_name(t)
    try:
        ol = outline_of(ctx, fname, t.text())
    except MoveError as e:
        return str(e)
    return cat, items, fname, t.text(), ol


@check("declarations-found")
def _declarations_found(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every declaration the reader lists is the `lean` of exactly one item, with the reader's lines, and no item
    names a declaration the file lacks (2.B)."""
    got = _source(output, inputs, ctx)
    if isinstance(got, str):
        return False, got
    _cat, items, fname, _text, ol = got
    mine: dict[str, list[dict]] = {}
    for it in _decls(items, fname):
        mine.setdefault(it["lean"], []).append(it)
    for d in ol.get("defs") or []:
        lean = decl_name(d)
        rows = mine.pop(lean, [])
        if len(rows) != 1:
            return False, (f"{lean} is the lean of no item" if not rows else f"{lean} is the lean of {len(rows)} "
                                                                             "items")
        want = (int(d.get("line") or 1), int(d.get("end") or d.get("line") or 1))
        sp = _span_of(rows[0])
        if sp is None or (sp[1], sp[2]) != want:
            return False, f"{rows[0]['id']} is at lines {_lines_text(*want)} in the file, and its span says otherwise"
    if mine:
        return False, f"{next(iter(mine.values()))[0]['id']} names a declaration the file lacks"
    return True, ""


@check("comments-covered")
def _comments_covered(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every comment the reader lists has exactly one `audit` row with its lines, and no row names lines that hold
    no comment (2.B)."""
    got = _source(output, inputs, ctx)
    if isinstance(got, str):
        return False, got
    cat, _items, _fname, _text, ol = got
    rows = [str(r.get("lines")) for r in cat.get("audit") or [] if isinstance(r, dict)]
    want = [_lines_text(int(c.get("line") or 1), int(c.get("end") or c.get("line") or 1))
            for c in ol.get("comments") or [] if isinstance(c, dict)]
    for w in want:
        k = rows.count(w)
        if k != 1:
            return False, f"the comment at lines {w} has {k} audit rows, not one"
    extra = [r for r in rows if r not in want]
    if extra:
        return False, f"an audit row names lines {extra[0]}, which hold no comment"
    return True, ""


@check("reach-agrees")
def _reach_agrees(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every item's `reached`, `depth` and `carries` are the ones the rule gives from the reader's graph and
    `source.target` (2.B). In a part, the reach starts from what its head says crosses into it too."""
    got = _source(output, inputs, ctx)
    if isinstance(got, str):
        return False, got
    cat, items, fname, _text, ol = got
    names = {decl_name(d) for d in ol.get("defs") or []}
    h = inputs.get("with")
    hcat, hitems = fabula_doc(h) if isinstance(h, Value) and h.type == "fabula" else ({}, [])
    hcat = {k: plain(v) for k, v in hcat.items() if k != "nodes"}
    t = _text_in(inputs)
    place = _head_place(hcat, [plain(x) for x in hitems], t) if is_head(hcat) and t is not None else None
    entries = _entries(cat, [plain(x) for x in hitems] if place else None, (place or {}).get("component"), names)
    reach = reach_of(ctx, {fname: ol}, entries)
    key_of = {decl_name(d): reach["keys"].get((fname, int(d.get("line") or 0)), decl_name(d))
              for d in ol.get("defs") or []}
    rows = reach["rows"]
    for it in _decls(items, fname):
        row = rows.get(key_of.get(it["lean"], it["lean"])) or {}
        want = str(row.get("reached") or "no")
        if it.get("reached") != want:
            return False, f"{it['id']} says reached {it.get('reached')!r}; the rule gives {want!r}"
        if want == "yes":
            for k in ("depth", "carries"):
                if it.get(k) != int(row.get(k) or 0):
                    return False, f"{it['id']} says {k} {it.get(k)!r}; the rule gives {int(row.get(k) or 0)}"
        elif "depth" in it or "carries" in it:
            return False, f"{it['id']} is not reached and carries a depth"
    return True, ""


#: The items that say something about the proof, and the fields through which each reaches a declaration.
_REACHES = {"yield": ("grounds", "of"), "reading": ("grounds",), "part": ("steps",), "step": ("inside",),
            "constant": ("where",)}


@check("lines-resolve")
def _lines_resolve(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every span and every ground's lines lie inside the file and inside the item they name; every item that says
    something about the proof reaches a declaration item with lines (2.B)."""
    cat, items = _doc(output, inputs)
    by_id = {str(it.get("id")): it for it in items}
    lengths = {str(it.get("path")): int((it.get("length") or {}).get("lines") or 0) for it in items
               if item_kind(it) == "file"}

    def decl_reached(ref: Any, seen: frozenset = frozenset()) -> bool:
        it = by_id.get(str(ref))
        if it is None or ref in seen:
            return False
        if item_kind(it) in DECL_KINDS:
            return _span_of(it) is not None
        nxt = it.get("inside") if item_kind(it) == "step" else None
        return decl_reached(nxt, seen | {ref}) if nxt else False

    for it in items:
        iid, kind = it.get("id"), item_kind(it)
        sp = _span_of(it)
        if it.get("span") is not None:
            if sp is None:
                return False, f"{iid}: its span's lines are not n or n-m"
            if sp[0] not in lengths:
                return False, f"{iid}: its span names {sp[0]}, which is no file of the fabulam"
            if lengths[sp[0]] and sp[2] > lengths[sp[0]]:
                return False, f"{iid}: lines {_lines_text(sp[1], sp[2])} lie outside {sp[0]}"
        if kind == "step":
            of = by_id.get(str(it.get("inside")))
            osp = _span_of(of) if of else None
            if of is None or osp is None or sp is None or not (osp[1] <= sp[1] and sp[2] <= osp[2]):
                return False, f"{iid}: its lines do not lie inside {it.get('inside')}"
        rows = list(it.get("grounds") or []) if isinstance(it.get("grounds"), list) else []
        rows += [{"of": iid, **s} for s in it.get("slack") or [] if isinstance(s, dict)]
        for g in rows:
            of = by_id.get(str(g.get("of"))) if isinstance(g, dict) else None
            ab = lines_of(g.get("lines")) if isinstance(g, dict) else None
            osp = _span_of(of) if of else None
            if of is None or ab is None:
                return False, f"{iid}: a ground or a slack entry names no item with lines"
            if osp is None or not (osp[1] <= ab[0] and ab[1] <= osp[2]):
                return False, f"{iid}: lines {_lines_text(*ab)} do not lie inside {g.get('of')}"
        fields = _REACHES.get(kind) if not (kind == "part" and it.get("division") != "stage") else None
        if kind == "claim" and it.get("by"):
            fields = ("by",)
        if fields:
            refs: list = []
            for k in fields:
                v = it.get(k)
                for x in (v if isinstance(v, list) else [v]):
                    refs.append(x.get("of") if isinstance(x, dict) else x)
            if not any(decl_reached(r) for r in refs if r):
                return False, f"{iid} reaches no declaration with lines through {', '.join(fields)}"
    del cat
    return True, ""


@check("nothing-invented")
def _nothing_invented(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every `lean` name of a `C:reliance` is a name the reader found in the file's text outside its own
    declarations; every `uses`, `used-by` and `leans-on` link is one the reader found; a known theorem's name
    (`known-as`) stands only on a reliance (2.B)."""
    got = _source(output, inputs, ctx)
    if isinstance(got, str):
        return False, got
    _cat, items, fname, _text, ol = got
    defs = [d for d in ol.get("defs") or [] if isinstance(d, dict)]
    by_def = {decl_name(d): outside_names(d) for d in defs}
    written = {n for names in by_def.values() for n in names}
    key_of = {k: decl_name(d) for d in defs
              for k in [graph_keys({fname: ol}, [fname]).get((fname, int(d.get("line") or 0)))]}
    uses = {key_of.get(k, k): [key_of.get(u, u) for u in us]
            for k, us in _uses_map(engine(ctx, "syntax").graph({fname: ol}) or {}).items()}
    by_id = {str(it.get("id")): it for it in items}
    mine = {it["id"]: it["lean"] for it in _decls(items, fname)}
    for it in items:
        kind = item_kind(it)
        if "known-as" in it and kind != "reliance":
            return False, f"{it.get('id')} carries known-as; a known theorem is named only through a reliance"
        if kind == "reliance":
            names = it.get("lean")
            names = [names] if isinstance(names, str) else [str(x) for x in names or []]
            if not names:
                return False, f"{it.get('id')} names no lean"
            for x in names:
                if written_as(x, written) is None:
                    return False, f"{it.get('id')} names {x}, which the file does not write outside its own " \
                                  "declarations"
            for uid in it.get("used-by") or []:
                q = mine.get(uid)
                if q is None or not any(written_as(x, by_def.get(q, {})) for x in names):
                    return False, f"{it.get('id')} says {uid} uses it, and the reader found no such use"
        if it.get("id") in mine:
            q = mine[it["id"]]
            for ref in it.get("uses") or []:
                if mine.get(ref) not in uses.get(q, []):
                    return False, f"{it['id']} says it uses {ref}, a link the reader did not find"
            for ref in it.get("used-by") or []:
                if q not in uses.get(mine.get(ref, ""), []):
                    return False, f"{it['id']} says {ref} uses it, a link the reader did not find"
            for ref in it.get("leans-on") or []:
                rel = by_id.get(ref)
                names = (rel or {}).get("lean")
                names = [names] if isinstance(names, str) else [str(x) for x in names or []]
                if rel is None or not any(written_as(x, by_def.get(q, {})) for x in names):
                    return False, f"{it['id']} says it leans on {ref}, a link the reader did not find"
    return True, ""


#: The longest run of the file's own text a field but `lean` may hold (the fabulac's check, with a lower number).
CARRIED = 80
_KEPT_FIELDS = frozenset(("lean", "id", "provenance", "made", "span", "digest", "sha256"))


def carried_run(s: str, source: str, most: int = CARRIED) -> str | None:
    """A run of more than `most` code points of `source` that `s` holds, white space folded; None when it holds
    none."""
    s, src = " ".join(s.split()), " ".join(source.split())
    k = most + 1
    if len(s) < k:
        return None
    for i in range(0, len(s) - k + 1):
        if s[i:i + k] in src:
            return s[i:i + k]
    return None


@check("nothing-carried")
def _nothing_carried(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No field but `lean` holds a run of more than 80 code points of the file's own text (2.B)."""
    t = _text_in(inputs)
    if t is None:
        return False, "no Lean file among the inputs to hold the fabulam to"
    source = t.text()
    _cat, items = fabula_doc(output)
    for it in items:
        for k, v in plain(it).items():
            if k in _KEPT_FIELDS:
                continue
            for s in _walk_strings(v):
                run = carried_run(s, source)
                if run:
                    return False, f"{it.get('id')}: its {k} carries the file's own text: {run[:60]}…"
    return True, ""


def its_own_file(items: list[dict], fname: str) -> str | None:
    """What the contract block `its-own-file` of `decompile-lean.thym` holds, for a test or a tool: a file's reading
    points into that file only. None when it holds, else the words."""
    if not items:
        return "the reading found nothing in the file"
    bad = next((it for it in items if isinstance(it.get("span"), dict) and it["span"].get("file") != fname), None)
    return f"{bad.get('id')} points into another file" if bad else None


def fold_grounded(output: Value, inputs: dict) -> tuple[bool, str]:
    """`fold-grounded` as a head's fold holds it: every stage's steps and every reading's grounds name items the
    head held before the fold, and the atem restates one of them."""
    w = inputs.get("with")
    before = {str(it.get("id")) for it in fabula_doc(w)[1]} if isinstance(w, Value) else set()
    cat, items = fabula_doc(output)
    new = [plain(it) for it in items if str(it.get("id")) not in before]
    if not any(item_kind(it) == "part" for it in new):
        return False, "the fold gave no stage"
    for it in new:
        refs = list(it.get("steps") or []) + [g.get("of") for g in it.get("grounds") or [] if isinstance(g, dict)]
        if item_kind(it) in ("part", "reading") and (not refs or any(r not in before for r in refs)):
            return False, f"{it.get('id')} rests on something the head did not hold"
    of = (cat.get("atem") or {}).get("of") if isinstance(cat.get("atem"), dict) else None
    if of is not None and of not in before:
        return False, "the atem restates an item the head does not hold"
    return True, ""


__all__ = ["BAND_FILES", "BAND_LINES", "CHUNK_LINES", "DENSITIES", "HEAD_CROSSING", "HEAD_PARTS", "NEIGHBOUR_CHARS",
           "PROOF_AXES", "PSHORT_CHARS", "REQUEST_CHARS", "SUMMARY_CHARS", "RequestTooLarge", "blank_comments",
           "carried_run", "checking_says", "chunks_of", "construe", "covered", "crossing_in", "decl_kind",
           "decl_name", "derive_branch", "entail_branch", "entail_pshort", "fold_grounded", "fold_head",
           "head_roles", "held", "is_head", "is_lean_folder", "item_uri", "its_own_file", "lean_slug", "must_cite", "numbered", "part_path", "part_uri", "pshort_fixed",
           "pshort_footer", "pshort_parts", "pshort_rows", "pshort_text", "pshort_view", "reach_of", "read_proof",
           "respell", "survey_archive", "survey_branch", "survey_text", "targets_by_rule"]
