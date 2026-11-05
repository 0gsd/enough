"""The dynamic checks: what must hold on a move's output before it becomes a value (docs/THYM.md 7.1, 7.3, 9).

A move's contract is a list of check names (its declaration's `contract:`); the runtime runs every one of them on
every output, deterministic or model-backed, and a check this registry lacks refuses the run (`Refusal("run",
"<check>", "check not implemented")`), never a silent pass. This module implements the checks that need no engine:
`provenance`, `digests`, `length`, `whole-sentences`, `scale-range`, `labelled`, `never-source`, `byte-exact`,
`no-mark`, `no-counts`, `default-deny` and `fabula-checks` (also under its old name, `emf-checks`). The moves lane registers the engine-backed ones (`coverage`,
`span-resolves`, `no-invention`, ...) with the same decorator.

A check is `fn(output, inputs, node, decl, ctx) -> (ok, why)`: `output` is the value the move gave; `inputs` the
values it was given, by operand name, and the value modifiers (`with`, `of`, `against`, `in`) by their word; `node`
the plan node, with `modifiers` added (every modifier as written: words, `{n, unit}` for `to`); `decl` the move's
declaration; `ctx` the run's `MoveContext`, or None outside a run. A check sees `output.state == "pending"` when a
scaffold gave the output (THYM.md 19) and may hold a pending value to the weaker promise it makes.

Standalone: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from enough import macrocosm as mc
from enough.thym import Refusal
from enough.thym.values import Value, digest_path, is_fabula, item_id, plain, sha256_bytes

CheckFn = Callable[[Value, dict, dict, Any, Any], Any]

# comprise-isotype/0's keys, as comprise-dev's core/isotype.py states them (`KEYS`), with the two a release made by a
# program carries, `program` and `trace` (THYM.md 18; docs/thym-comprise-spec.md 1.4); default-deny holds a projection
# to exactly these. A paratype (docs/thym-comprise-spec.md 2.1) is an isotype at third-party standing: the same keys,
# with `paratype` in place of `isotype`, and `standing`, `submitter` and `of`.
ISOTYPE_KEYS = ("isotype", "hid", "epoch", "cadence", "sample", "identity", "shape", "offers", "seeks", "open_to",
                "program", "trace")
PARATYPE_KEYS = tuple(k for k in ISOTYPE_KEYS if k != "isotype") + ("paratype", "standing", "submitter", "of")
#: The one number a projection may hold: the founded year (THYM.md 7.3, `no-counts`).
NUMBER_ALLOWED = ("identity.founded",)
#: Words that would mark where something was withheld (THYM.md 7.2, law 5): as a key, or as a placeholder value
#: (the word alone, or in brackets: `[withheld]`, `(redacted)`).
_MARK_WORDS = re.compile(r"\b(withheld|redacted|hidden|omitted|removed|elided)\b", re.I)
_PLACEHOLDER = re.compile(r"^\s*(withheld|redacted|hidden|omitted|removed|elided)\s*$|"
                          r"[\[(<{]\s*(withheld|redacted|hidden|omitted|removed|elided)\b", re.I)


class Checks:
    """A registry of check implementations, by name. `CHECKS` is the default, holding this module's checks; a test
    copies it and adds its own."""

    def __init__(self) -> None:
        self._fns: dict[str, CheckFn] = {}

    def add(self, name: str, fn: CheckFn) -> None:
        self._fns[name] = fn

    def lookup(self, name: str) -> CheckFn | None:
        return self._fns.get(name)

    def names(self) -> list[str]:
        return sorted(self._fns)

    def copy(self) -> "Checks":
        other = Checks()
        other._fns = dict(self._fns)
        return other


CHECKS = Checks()


def check(name: str, *, registry: Checks | None = None) -> Callable[[CheckFn], CheckFn]:
    """Register a check (in the default registry unless one is named)."""
    def deco(fn: CheckFn) -> CheckFn:
        (registry or CHECKS).add(name, fn)
        return fn
    return deco


def verdict(name: str, output: Value, inputs: dict, node: dict, decl: Any, ctx: Any = None, *,
            registry: Checks | None = None) -> tuple[bool, str] | Refusal:
    """One check's verdict, `(ok, why)`; `why` is empty when it holds. A check the registry lacks is a refusal; a
    check that raises fails, with what it raised."""
    fn = (registry or CHECKS).lookup(name)
    if fn is None:
        return Refusal("run", name, "check not implemented", line=(node or {}).get("line"))
    try:
        r = fn(output, inputs or {}, node or {}, decl, ctx)
    except Exception as e:  # noqa: BLE001 - a check that breaks is a check that does not hold
        return False, f"the check raised {type(e).__name__}: {e}"
    if isinstance(r, tuple):
        return bool(r[0]), str(r[1] if len(r) > 1 and r[1] is not None else "")
    return bool(r), ""


# ---------------------------------------------------------------------------
# Text helpers: front matter, footers, sentences, words
# ---------------------------------------------------------------------------

_FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
_SPLIT = re.compile(r"(?<=[.!?])[\"”’)\]]*\s+(?=[\"“‘(\[]?[A-Z0-9])")
_WORDS = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’][A-Za-z]+)?")


def front_matter(text: str) -> tuple[dict, str]:
    """A markdown text's YAML front matter (`{}` when it has none) and the body after it."""
    text = text.replace("\r\n", "\n")
    mt = _FRONT.match(text)
    if not mt:
        return {}, text
    try:
        data = mc.yaml_load(mt.group(1))
    except Exception:  # noqa: BLE001 - front matter that does not parse is no front matter
        data = None
    return (data if isinstance(data, dict) else {}), text[mt.end():]


def _is_footer(line: str) -> bool:
    s = line.strip()
    return len(s) > 2 and s.startswith("*") and s.endswith("*") and not s.startswith("**")


def body(text: str, *, footer: bool = False) -> str:
    """The text a telling says: without its front matter and, unless `footer`, without its closing footer (a last
    paragraph in italics, `*...*`, on one line or several, as MacroCOSM 18.4.4's and THYM.md 14's footers are)."""
    _, rest = front_matter(text)
    rest = rest.rstrip()
    if not footer:
        paras = re.split(r"\n\s*\n", rest)
        if paras and _is_footer(" ".join(paras[-1].split())):
            paras.pop()
        rest = "\n\n".join(paras)
    return rest


def sentences(text: str) -> list[str]:
    """The sentences of a text, by a simple rule: paragraphs split on blank lines, a heading or a list line is a
    sentence of its own, and inside a paragraph a sentence ends at `.`, `!` or `?` followed by space and a capital or a
    digit. Whitespace inside a sentence is folded to one space."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", body(text, footer=True)):
        buf: list[str] = []
        for line in para.split("\n"):
            s = line.strip()
            if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s)", s) and not _is_footer(s):
                if buf:
                    out += _split(" ".join(buf))
                    buf = []
                out.append(" ".join(s.split()))
            elif s:
                buf.append(s)
        if buf:
            out += _split(" ".join(buf))
    return out


def _split(para: str) -> list[str]:
    return [" ".join(p.split()) for p in _SPLIT.split(para) if p.strip()]


def words(text: str) -> int:
    return len(_WORDS.findall(text))


def _first(inputs: dict, *types: str) -> Value | None:
    for v in inputs.values():
        if isinstance(v, Value) and v.type in types:
            return v
    return None


def _mods(node: dict) -> dict:
    m = (node or {}).get("modifiers")
    return m if isinstance(m, dict) else {}


def _walk(v: Any, path: str = ""):
    if isinstance(v, dict):
        for k, x in v.items():
            yield from _walk(x, f"{path}.{k}" if path else str(k))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _walk(x, f"{path}[{i}]")
    else:
        yield path, v


# ---------------------------------------------------------------------------
# The checks that need no engine
# ---------------------------------------------------------------------------

@check("provenance")
def _provenance(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The law of provenance (7.2): the output carries `made`, naming its move and its run."""
    m = output.made
    if output.is_nothing:
        return False, "the move gave nothing, so nothing carries made"
    if not isinstance(m, dict) or not m.get("move"):
        return False, "the output carries no made"
    if m.get("move") != "none" and not m.get("run"):
        return False, f"made names the move {m.get('move')} but no run"
    return True, ""


def _package_problems(v: Value) -> list[str]:
    cat = v.mapping() or {}
    rows = cat.get("contents")
    if not isinstance(rows, list):
        return ["the package's catalog lists no contents"]
    out = []
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("path"), str):
            out.append("a contents entry has no path")
            continue
        want = r.get("sha256")
        if isinstance(r.get("text"), str):
            got = sha256_bytes(r["text"].encode("utf-8"))
        elif v.path is not None and v.path.is_dir() and (v.path / r["path"]).is_file():
            got = digest_path(v.path / r["path"])
        else:
            out.append(f"{r['path']} is not in the package")
            continue
        if got != want:
            out.append(f"{r['path']} has sha256 {str(got)[:12]}, the catalog says {str(want)[:12]}")
    return out


@check("digests")
def _digests(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every file in a package's catalog has the sha256 the catalog says (15.4); every package among the output and
    the inputs is checked."""
    packages = [v for v in [output, *inputs.values()] if isinstance(v, Value) and v.type == "package"]
    if not packages:
        return False, "no package to check"
    for p in packages:
        bad = _package_problems(p)
        if bad:
            return False, "; ".join(bad)
    return True, ""


@check("length")
def _length(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`to N words`: at most N words and at least 80 per hundred of N; `to N sentences`: N sentences or fewer. The
    footer line and the front matter are not counted."""
    to = _mods(node).get("to")
    if not to:
        return True, "no length was asked"
    if isinstance(to, dict):
        n, unit = to.get("n"), to.get("unit")
    else:
        n, unit = getattr(to, "n", None), getattr(to, "unit", None)
    text = output.text()
    if unit == "sentences":
        k = len(sentences(body(text)))
        return (k <= int(n), "" if k <= int(n) else f"{k} sentences, more than {n}")
    k = words(body(text))
    if k > int(n):
        return False, f"{k} words, more than {n}"
    if k * 100 < 80 * int(n):
        return False, f"{k} words, fewer than 80 per hundred of {n}"
    return True, ""


@check("whole-sentences")
def _whole_sentences(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """`cut` removed whole sentences only: every sentence of the output is a sentence of the input, in order."""
    src = _first(inputs, "short", "text")
    if src is None:
        return False, "no short among the inputs"
    pool = sentences(body(src.text()))
    i = 0
    for s in sentences(body(output.text())):
        while i < len(pool) and pool[i] != s:
            i += 1
        if i == len(pool):
            return False, f"not a whole sentence of the input, or out of order: {s[:80]}"
        i += 1
    return True, ""


def _morph_items(v: Value) -> list[dict]:
    m = v.mapping() or {}
    if isinstance(m.get("nodes"), list):
        return [n for n in m["nodes"] if isinstance(n, dict) and isinstance(n.get("scales"), dict)]
    return [m] if isinstance(m.get("scales"), dict) else []


@check("scale-range")
def _scale_range(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """Every scale is an integer from 1 to 5; a scaffold's open question (`{pending: ...}`) stands for a judgement
    scale the rules cannot give."""
    rows = _morph_items(output)
    if not rows:
        return False, "no morph with scales"
    for it in rows:
        for k, v in it["scales"].items():
            if mc.is_pending(v):
                continue
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                return False, f"{it.get('id', 'the morph')}: {k} is {v!r}, not an integer from 1 to 5"
    return True, ""


@check("labelled")
def _labelled(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A reading carries `read_through: <morph name>` in its front matter and the reading footer (14)."""
    fm, rest = front_matter(output.text())
    name = fm.get("read_through")
    if not isinstance(name, str) or not name.strip():
        return False, "no read_through in the front matter"
    tail = [ln.strip() for ln in rest.rstrip().split("\n") if ln.strip()][-3:]
    n = name.strip().lower()
    if not any(ln.lower().startswith("*a reading of ") and f" through {n}" in ln.lower() for ln in tail):
        return False, f"no reading footer (*a reading of <text> through {name.strip()}, ...*) at the end"
    return True, ""


@check("never-source")
def _never_source(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A reading's path is not the path of any input, and no input file changed (14)."""
    for k, v in inputs.items():
        if not isinstance(v, Value) or v.path is None:
            continue
        if output.path is not None and output.path.resolve() == v.path.resolve():
            return False, f"the output would replace the input {k}"
        if v.raw is not None and v.path.exists():
            now = digest_path(v.path)
            if now != sha256_bytes(v.raw):
                return False, f"the input {k} changed on disk during the run"
    return True, ""


def _compile_program(cat: dict) -> str | None:
    """A program volume compiled back (THYM.md 10): the catalog's front, then each top-level item's body in order."""
    rows = [n for n in cat.get("nodes") or [] if isinstance(n, dict) and isinstance(n.get("order"), int)]
    if not isinstance(cat.get("front"), str) or not rows:
        return None
    return cat["front"] + "".join(str(n.get("body") or "") for n in sorted(rows, key=lambda n: n["order"]))


@check("byte-exact")
def _byte_exact(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The compiled bytes equal the source bytes. For a text given from a volume (`compile`), the text's sha256 is the
    volume's `source.sha256`; for a volume given from a text (`enumerate`), its `source.sha256` is the text's and, for
    a program volume, front plus bodies in order give the text back byte for byte."""
    if output.type in ("text", "short"):
        vol = _first(inputs, "volume", "item", "fabula")
        m = (vol.mapping() or {}) if vol else {}
        src = m.get("source") or m.get("document")            # a doc/1 volume names its text under document
        want = src.get("sha256") if isinstance(src, dict) else None
        if not want:
            return False, "the volume names no source sha256 to compare with"
        return (output.sha256 == want, "" if output.sha256 == want else
                f"the compiled text has sha256 {output.sha256[:12]}, the source {str(want)[:12]}")
    cat = output.mapping() or {}
    src = _first(inputs, "text")
    if src is None:
        return False, "no source text among the inputs"
    src_block = cat.get("source") if isinstance(cat.get("source"), dict) else cat.get("document")
    sha = src_block.get("sha256") if isinstance(src_block, dict) else None
    if sha != src.sha256:
        return False, f"the volume's source sha256 is {str(sha)[:12]}, the text's {src.sha256[:12]}"
    back = _compile_program(cat)
    if back is not None and back.encode("utf-8") != src.bytes():
        return False, "the program volume does not compile back to its text byte for byte"
    return True, ""


@check("no-mark")
def _no_mark(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """A withheld item leaves no placeholder, count or gap (7.2, law 5): no withheld id appears in the output, and no
    key or text marks that something was withheld."""
    if output.is_nothing:
        return True, ""
    withheld = getattr(ctx, "withheld", None) or {}
    data = output.mapping()
    readable = data is not None or isinstance(output.payload, str)
    text = output.bytes().decode("utf-8", errors="replace") if readable else ""
    for wid, item in withheld.items():
        # held by its key (`MoveContext.withhold`); the output may name it by its bare id too, and either gives it away
        names = {wid} | ({item_id(item)} if isinstance(item, Value) and not item.is_nothing else set())
        for name in sorted(n for n in names if n):
            if name in text:
                return False, f"the withheld item {name} is named in the output"
    if data is not None:
        for path, v in _walk(plain(data)):
            leaf = path.rsplit(".", 1)[-1]
            if _MARK_WORDS.search(leaf.replace("_", " ")) or (isinstance(v, str) and _PLACEHOLDER.search(v)):
                return False, f"{path} marks something withheld"
    elif _PLACEHOLDER.search(text):
        return False, "the output marks something withheld"
    return True, ""


@check("no-counts")
def _no_counts(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """No number of anything internal reaches the projection; the founded year is the only number allowed."""
    data = output.mapping()
    if data is None:
        return False, "the projection is not a mapping"
    for path, v in _walk(plain(data)):
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) and path not in NUMBER_ALLOWED:
            return False, f"{path} holds the number {v}"
    return True, ""


@check("default-deny")
def _default_deny(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The projection holds only the fields its target schema names: comprise-isotype/0's keys (comprise-dev
    core/isotype.py KEYS), or comprise-paratype/0's for a paratype."""
    data = output.mapping()
    if data is None or isinstance(data.get("nodes"), list):
        return False, "the projection is not a comprise-isotype/0 document"
    kind = _mods(node).get("as")
    keys = PARATYPE_KEYS if (kind == "paratype" or "paratype" in data) else ISOTYPE_KEYS
    extra = [str(k) for k in data if k not in keys]
    if extra:
        return False, f"fields the target schema does not name: {', '.join(extra)}"
    return True, ""


@check("emf-checks")
@check("fabula-checks")
def _fabula_checks(output: Value, inputs: dict, node: dict, decl: Any, ctx: Any) -> tuple[bool, str]:
    """The volume passes its own manifest's checks (`macrocosm.lint`, no errors): a fabula, `fabula/1` or `emf/1`
    (THYM 7.3). One check under two names: `fabula-checks`, and `emf-checks`, its old name, read wherever it is
    written; a verdict keeps the name it was asked by."""
    text = output.raw.decode("utf-8-sig") if output.raw is not None else (
        mc.dump(plain(output.payload)) if isinstance(output.payload, dict) else None)
    if text is None:
        return False, "the output is not a fabula"
    vol = mc.load_volume_text(text, filename="fabula.md.cosm")
    if vol.refused is not None:
        return False, str(vol.refused)
    if not is_fabula(vol.oes):
        return False, f"the volume is {vol.oes}, not a fabula (fabula/1)"
    errs = mc.lint(vol).errors
    if errs:
        return False, "; ".join(str(p) for p in errs[:3]) + (f" (and {len(errs) - 3} more)" if len(errs) > 3 else "")
    return True, ""
