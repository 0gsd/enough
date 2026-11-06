"""A `.thym` file enumerated into a `thym/1` program volume, and the file back byte for byte (THYM.md 10, 17.1–17.3;
stage 6 of section 11.1).

The volume's catalog names the file (`source: {path, sha256, size}`), holds `front` (everything before the first
block, verbatim) and says when and by what it was built. Its items are:

- one per top-level block, `P:program/<name>`, `P:move/<name>`, `M:morph/<name>` or `C:context/<name>`, with its
  heads as fields, its `lines`, its `order` among the blocks, and its text verbatim in `body`, from its first line to
  the next block's, blank lines and comments included;
- one per move inside a program, `P:move/<program>.<name>`, with its lines and its body verbatim, leading spaces
  included, but no order, since the program's body already holds it;
- one per statement, `P:step/<block>.<n>`, numbered from 1 in the order written within each block, with the line
  verbatim in `text`, its `form`, the move it calls and every move its line calls, what it binds and uses, whether
  it asks, its contracts, and for an `if` its `branches`, for a `for each` its `steps`;
- one per contracted call, `P:contract/<block>.<n>` for the step's own move and `<block>.<n>.<m>` for each contracted
  call nested inside it, in evaluation order, `marked` included; an `assert` step's contract names the check its
  condition uses, and a call of a user move carries the contracts the move inherits.

What `thym 1` adds here (THYM 10): a program of several outputs lists each in `gives`, and a labelled give holds its
output's name in `slot`, as a labelled emit does. A `thym 0` file enumerates exactly as before.

`compile_volume` gives `front` and then every top-level item's `body` in `order`: the file, byte for byte (law 4 of
section 7.2). `dump` writes a volume as canonical `.cosm` text, keys in insertion order, LF, UTF-8, block scalars for
multi-line strings (with an indentation indicator when the first line begins with a space), such that
`macrocosm.yaml_load(dump(m)) == m`.

Names and summaries follow the rule of section 10, and nothing is looked up by program: a step's `name` is its
statement without indentation or comment, and its `summary` the comment's text when the line has one, else the name;
a block's summary is the first sentence of its `why`, capitalised (a block with no `why` takes its first line, as a
step takes its statement); a contract's summary says what its move must leave true of what it gives, and an
`assert`'s names its condition.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import importlib
from pathlib import Path
from typing import Any

import yaml

from . import MINICOSM, Refusal
from . import check as ck
from . import contracts as ct
from . import parse as ps
from . import types as ty

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def enough_version() -> str:
    """enough's version, read lazily (`0` when the package is vendored without it)."""
    try:
        return str(importlib.import_module("enough").__version__)
    except Exception:                                   # noqa: BLE001
        return "0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def span(a: int, b: int | None = None) -> str:
    return f"L{a}" if b is None or b == a else f"L{a}-L{b}"


def provenance(fname: str, a: int | None = None, b: int | None = None) -> dict:
    src = fname if a is None else f"{fname}#{span(a, b)}"
    return {"mode": "derived", "sources": [src], "confidence": 1}


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]




def first_sentence(text: str) -> str:
    for i, ch in enumerate(text):
        if ch in ".!?" and (i + 1 == len(text) or text[i + 1] == " "):
            return text[:i + 1]
    return text




# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def step_summary(st: ps.Stmt, lines: list[str]) -> str:
    """A step's `summary`: its line's comment when it has one, else its name (THYM.md 10)."""
    return st.comment or ps.statement_name(st, lines)


def block_summary(b: ps.Block, lines: list[str]) -> str:
    """A block's `summary`: the first sentence of its `why`, capitalised; a block with no `why` takes its first line
    without indentation or comment, as a step takes its statement."""
    if b.why is not None and b.why.text:
        return cap(first_sentence(b.why.text))
    return ps.strip_comment(lines[b.line - 1])[0].strip()


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _heads(b: ps.Block, item: dict, *, always: bool) -> None:
    if b.why is not None:
        item["why"] = b.why.text
    if always or b.musts:
        item["must"] = [p.text for p in b.musts]
    if always or b.decideds:
        item["decided"] = [{"date": d.date, "what": d.what} for d in b.decideds]


def _value(e: ps.Expr) -> Any:
    if isinstance(e, ps.Lit):
        return e.value
    if isinstance(e, ps.ListLit):
        return [_value(x) for x in e.items]
    if isinstance(e, ps.Name):
        return e.name
    if isinstance(e, ps.Word):
        return e.word
    if isinstance(e, ps.Uri):
        return e.uri
    return ps.render(e)



class _Enumerator:
    def __init__(self, checked: ck.Checked, fname: str):
        self.c, self.m, self.fname = checked, checked.module, fname
        self.lines = self.m.lines

    def steps_and_contracts(self, b: ps.Block, of_id: str) -> tuple[list[dict], list[dict]]:
        slug = b.qualified
        order = list(ck.walk(b.stmts))
        num = {id(s): k + 1 for k, s in enumerate(order)}
        sid = lambda s: f"P:step/{slug}.{num[id(s)]}"           # noqa: E731
        steps: list[dict] = []
        contracts: list[dict] = []
        for st in order:
            n = num[id(st)]
            own = ck.own_call(st)
            entries: list[tuple[str, str, list[str], str]] = []
            if own is not None:
                chk = ck.call_checks(own)
                if chk:
                    entries.append((f"{slug}.{n}", ck.move_name(own), chk, ct.summary(ck.move_name(own))))
            elif isinstance(st, ps.Assert):
                chk = ct.condition_checks(st.cond)
                if chk:
                    entries.append((f"{slug}.{n}", "assert", chk,
                                    ct.summary("assert", condition=ps.render_cond(st.cond), block_kind=b.kind)))
            k = 0
            for c in ck.step_calls(st):
                if c is own:
                    continue
                chk = ck.call_checks(c)
                if chk:
                    k += 1
                    entries.append((f"{slug}.{n}.{k}", ck.move_name(c), chk, ct.summary(ck.move_name(c))))
            multi = isinstance(st, (ps.If, ps.For)) or st.header_end > st.line
            last = st.end if isinstance(st, (ps.If, ps.For)) else st.header_end
            item: dict[str, Any] = {
                "id": sid(st), "type": "step", "name": ps.statement_name(st, self.lines),
                "summary": step_summary(st, self.lines), "of": of_id, "n": n, "text": st.text,
            }
            if isinstance(st, ps.Emit) and st.slot:
                item["slot"] = st.slot
            elif isinstance(st, ps.Give) and st.label:
                item["slot"] = st.label
            item["line"] = st.line
            if multi:
                item["lines"] = f"{st.line}-{last}"
            item["form"] = st.form
            if own is not None:
                item["move"] = ck.move_name(own)
            elif isinstance(st, ps.Assert):
                item["move"] = "assert"
            item["calls"] = ck.step_call_names(st)
            if isinstance(st, ps.Let):
                item["binds"] = st.name
            elif isinstance(st, ps.For):
                item["binds"] = st.var
            item["uses"] = ck.names_used(st)
            item["asks"] = ck.step_asks(st)
            if isinstance(st, ps.If):
                item["branches"] = {"then": [sid(s) for s in st.then], "else": [sid(s) for s in (st.else_ or [])]}
            elif isinstance(st, ps.For):
                item["steps"] = [sid(s) for s in st.body]
            item["contracts"] = [f"P:contract/{e[0]}" for e in entries]
            item["provenance"] = provenance(self.fname, st.line, last if multi else None)
            steps.append(item)
            for cid, move, chk, summ in entries:
                contracts.append({"id": f"P:contract/{cid}", "type": "contract", "name": move, "summary": summ,
                                  "of": sid(st), "move": move, "checks": list(chk),
                                  "provenance": provenance(self.fname, st.line)})
        return steps, contracts

    def top_steps(self, b: ps.Block) -> list[str]:
        order = list(ck.walk(b.stmts))
        num = {id(s): k + 1 for k, s in enumerate(order)}
        return [f"P:step/{b.qualified}.{num[id(s)]}" for s in b.stmts]

    def items(self) -> tuple[str, list[dict]]:
        m = self.m
        raw = m.raw_lines
        starts = [b.line - 1 for b in m.blocks]
        if not starts:
            return m.text, []
        front = "\n".join(raw[:starts[0]]) + "\n" if starts[0] > 0 else ""
        nodes: list[dict] = []
        for k, b in enumerate(m.blocks):
            a = starts[k]
            body = "\n".join(raw[a:starts[k + 1]]) + "\n" if k + 1 < len(starts) else "\n".join(raw[a:])
            nodes.extend(self.block_items(b, order=k + 1, body=body))
        return front, nodes

    def block_items(self, b: ps.Block, *, order: int | None, body: str) -> list[dict]:
        out: list[dict] = []
        lines = f"{b.line}-{b.end}"
        prov = provenance(self.fname, b.line, b.end)
        if b.kind == "morph":
            item = {"id": f"M:morph/{b.name}", "type": "morph", "name": b.name, "summary": block_summary(b, self.lines)}
            _heads(b, item, always=False)
            values = {s.scale: s.value.value for s in b.scales}
            toward = next((s.toward for s in b.scales if s.toward), None)
            item.update({"declared": True, "shared": False, "scales": {s: values.get(s, 1) for s in ty.SCALES}})
            if toward:
                item["toward"] = toward
            item.update({"pinned": [], "lines": lines, "order": order, "body": body, "provenance": prov})
            return [item]
        if b.kind == "context":
            item = {"id": f"C:context/{b.name}", "type": "context", "name": b.name, "summary": block_summary(b, self.lines)}
            _heads(b, item, always=False)
            for f in b.fields:
                item[f.field] = _value(f.value)
            item.update({"lines": lines, "order": order, "body": body, "provenance": prov})
            return [item]
        if b.kind == "move":
            return self.move_items(b, order=order, body=body)
        item = {"id": f"P:program/{b.name}", "type": "program", "name": b.name, "summary": block_summary(b, self.lines)}
        _heads(b, item, always=True)
        item["takes"] = [{"name": p.name, "type": p.type} for p in b.takes]
        item["gives"] = [{"name": o.name, "type": o.type} for o in (b.outputs or [b.gives])] if b.gives else []
        item.update({"lines": lines, "order": order, "body": body})
        if b.moves:
            item["moves"] = [f"P:move/{b.name}.{lm.name}" for lm in b.moves]
        item["steps"] = self.top_steps(b)
        item["provenance"] = prov
        out.append(item)
        move_contracts: list[dict] = []
        for lm in b.moves:
            lbody = "\n".join(self.m.raw_lines[lm.line - 1:lm.end]) + "\n"
            items = self.move_items(lm, order=None, body=lbody, split=True)
            out.extend(items[0])
            move_contracts.extend(items[1])
        steps, contracts = self.steps_and_contracts(b, item["id"])
        out.extend(steps)
        out.extend(move_contracts)
        out.extend(contracts)
        return out

    def move_items(self, b: ps.Block, *, order: int | None, body: str, split: bool = False):
        item: dict[str, Any] = {"id": f"P:move/{b.qualified}", "type": "move", "name": b.name,
                                "summary": block_summary(b, self.lines)}
        _heads(b, item, always=False)
        item["params"] = [{"name": p.name, "type": p.type} for p in b.params]
        item["gives"] = [{"name": b.gives.name, "type": b.gives.type}] if b.gives else []
        item["lines"] = f"{b.line}-{b.end}"
        if order is not None:
            item["order"] = order
        item["body"] = body
        item["steps"] = self.top_steps(b)
        item["provenance"] = provenance(self.fname, b.line, b.end)
        steps, contracts = self.steps_and_contracts(b, item["id"])
        if split:
            return [item] + steps, contracts
        return [item] + steps + contracts


def enumerate_checked(checked: ck.Checked, *, built_at: _dt.datetime | None = None) -> dict:
    """The program volume of a checked module, as a mapping in the fixtures' shape."""
    m = checked.module
    fname = m.file_name
    stem = fname[:-len(".thym")] if fname.endswith(".thym") else Path(fname).stem
    data = m.text.encode("utf-8")
    front, nodes = _Enumerator(checked, fname).items()
    at = built_at or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    return {
        "oes": MINICOSM, "kind": "program", "id": f"thym/{stem}", "name": stem,
        "source": {"path": fname, "sha256": sha256(data), "size": len(data)},
        "front": front,
        "built": {"at": at, "by": f"enough/{enough_version()}"},
        "nodes": nodes,
    }


def enumerate_text(text: str, *, path: str | None = None, decls: dict | None = None,
                   volumes: ck.Volumes = None) -> dict | Refusal:
    """The program volume of a program's text (parse, check, enumerate)."""
    module = ps.parse(text, path=path)
    if isinstance(module, Refusal):
        return module
    checked = ck.check(module, decls=decls, volumes=volumes)
    if isinstance(checked, Refusal):
        return checked
    return enumerate_checked(checked)


def enumerate_file(path, *, decls: dict | None = None, volumes: ck.Volumes = None) -> dict | Refusal:
    """The program volume of a `.thym` file, exactly the conformance fixtures' shape, or the refusal."""
    p = Path(path)
    try:
        text = p.read_bytes().decode("utf-8")
    except OSError as e:
        return Refusal("compile", "unknown-uri", f"{p.name} cannot be read: {e.strerror or e}", None, str(p))
    except UnicodeDecodeError:
        return Refusal("compile", "parse", f"{p.name} is not UTF-8", None, str(p))
    return enumerate_text(text, path=str(p), decls=decls, volumes=volumes)


def compile_volume(mapping: dict) -> str:
    """A program volume's file again: `front`, then every top-level item's `body` in `order`, byte for byte."""
    tops = [it for it in mapping.get("nodes") or []
            if isinstance(it, dict) and isinstance(it.get("order"), int) and isinstance(it.get("body"), str)]
    tops.sort(key=lambda it: it["order"])
    return str(mapping.get("front") or "") + "".join(it["body"] for it in tops)


# ---------------------------------------------------------------------------
# Canonical text
# ---------------------------------------------------------------------------

class _Dumper(yaml.SafeDumper):
    """safe_dump's dumper with no anchors, and multi-line strings as literal blocks where YAML can hold them so."""

    def ignore_aliases(self, data):
        return True


def _str_rep(dumper: yaml.SafeDumper, s: str):
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None)


_Dumper.add_representer(str, _str_rep)


def dump(mapping: dict) -> str:
    """Canonical `.cosm` text for a thym volume: the declaration first, keys in insertion order, LF, UTF-8, block
    scalars for bodies and front; `macrocosm.yaml_load(dump(m)) == m`."""
    if not isinstance(mapping, dict):
        raise TypeError("dump takes a mapping: a .cosm file's top level is a mapping")
    if "oes" in mapping and next(iter(mapping)) != "oes":
        mapping = {"oes": mapping["oes"], **{k: v for k, v in mapping.items() if k != "oes"}}
    return yaml.dump(mapping, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110,
                     default_flow_style=False)
