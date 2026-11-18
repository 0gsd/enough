"""The migration trial's 161 steps as a cases file: tally's 53 scenarios, as the trial's harness wrote them
(`harness/diff.py` inside docs/fabula-survey-migration-trial.md, 2026-11-05), in the harness's own case shape
(tools/transconception/harness.py), with the original's results where the trial's document records them.

The document is read as text, never run: the scenarios are read from the Python block by a small evaluator of
literals (`S(...)` calls, lists, strings, bytes, `T + "..."`, `"...".encode("utf-8")`), and the original's results from
the report's `--detail` section, which prints a step only where a port differed from the original (each value cut at
300 characters of its repr, a file's at 400). So a case's `expect` holds a step's result where the document has it,
`null` where it does not, and `expect-says` says which; a value the report cut is kept as the beginning it shows and
named in `cut`. Nobody has recorded tally with the promoted recorder yet (that is the owner's, in the sandbox).

    python tools/transconception/trial_cases.py TRIAL_MD TALLY_FABULAC OUT_JSON

A tool kept outside enough's import path, standard library only; it reads two files and writes one.
"""
from __future__ import annotations

import ast
import base64
import json
import re
import sys
from pathlib import Path

T = "<TMP>"
CASE = "<CASE>"
COMMANDS = {"add": "command.add", "show": "command.show", "undo": "command.undo"}
WHOLE = "command.tally"
REPR_CUT = 300      # report.py prints a step's out and err as `{!r:.300}`
FILE_CUT = 400      # and a file left behind as `{!r:.400}`
RUN = ("the migration trial of 2026-11-05, harness/diff.py and report.py --detail "
       "(docs/fabula-survey-migration-trial.md)")
# diff.py's norm_ledger: a ledger line's time as <float> or <int>, so that two runs compare
MASKS = {"written": [{"pattern": "(\"at\":\\s*)-?\\d+(?:\\.\\d+(?:[eE][+-]?\\d+)?|[eE][+-]?\\d+)", "to": "\\1<float>"},
                     {"pattern": "(\"at\":\\s*)-?\\d+", "to": "\\1<int>"}]}


# ---- the scenarios, read from the document's diff.py ----------------------------------------------------------

def _block(text: str, heading: str) -> str:
    i = text.index(heading)
    a = text.index("````python\n", i) + len("````python\n")
    return text[a:text.index("````", a)]


class _Eval:
    """Literals only: what SCENARIOS is written in."""

    def __init__(self):
        self.names = {"T": T, "None": None, "True": True, "False": False}

    def __call__(self, n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, (ast.List, ast.Tuple)):
            vals = [self(e) for e in n.elts]
            return vals if isinstance(n, ast.List) else tuple(vals)
        if isinstance(n, ast.Dict):
            return {self(k): self(v) for k, v in zip(n.keys, n.values)}
        if isinstance(n, ast.Name) and n.id in self.names:
            return self.names[n.id]
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            return self(n.left) + self(n.right)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "encode":
            return self(n.func.value).encode(*[self(a) for a in n.args])
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "S":
            args = [self(a) for a in n.args]
            kw = {k.arg: self(k.value) for k in n.keywords}
            names = ["name", "group", "steps", "seed", "env", "seed_path", "parallel", "mkdir"]
            sc = dict(zip(names, args))
            sc.update(kw)
            return {"name": sc["name"], "group": sc["group"], "steps": sc["steps"], "seed": sc.get("seed"),
                    "env": sc.get("env") or {}, "seed_path": sc.get("seed_path") or "t.jsonl",
                    "parallel": sc.get("parallel"), "mkdir": sc.get("mkdir")}
        raise ValueError(f"not a literal the scenarios use: {ast.dump(n)[:120]}")


def scenarios(text: str) -> list[dict]:
    tree = ast.parse(_block(text, "### harness/diff.py"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCENARIOS" for t in node.targets):
            return _Eval()(node.value)
    raise ValueError("no SCENARIOS in the document's diff.py")


# ---- the original's results, read from the report's --detail section --------------------------------------------

def _literal(s: str, cut_at: int) -> tuple[str, bool, int]:
    """A repr at the start of `s`: (value, cut, length of the repr as printed). A repr longer than `cut_at` was cut
    by the report: its beginning is decoded as far as it goes."""
    q = s[0]
    i = 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == q:
            break
        i += 1
    if i < len(s) and i + 1 <= cut_at:
        return ast.literal_eval(s[:i + 1]), False, i + 1
    head = s[:cut_at]
    for k in range(0, 10):
        try:
            return ast.literal_eval(head[:len(head) - k] + q), True, cut_at
        except (SyntaxError, ValueError):
            continue
    raise ValueError(f"cannot read the beginning of {head[:60]!r}")


def _step_line(rest: str) -> dict:
    m = re.match(r"exit (\S+) out ", rest)
    ex = m.group(1)
    out, out_cut, n = _literal(rest[m.end():], REPR_CUT)
    tail = rest[m.end() + n:]
    assert tail.startswith(" err "), tail[:40]
    err, err_cut, _ = _literal(tail[len(" err "):], REPR_CUT)
    step = {"exit": int(ex) if re.fullmatch(r"-?\d+", ex) else ex, "out": out, "err": err}
    cut = [k for k, c in (("out", out_cut), ("err", err_cut)) if c]
    if err.startswith("<TRACEBACK> "):       # report.py printed a crash's last line only
        step["err"] = err[len("<TRACEBACK> "):]
        step["traceback"] = True
        if "err" not in cut:
            cut.append("err")
    if cut:
        step["cut"] = cut
    return step


def differences(text: str) -> dict:
    """{(scenario, argv as JSON or '<files>'): the original's result}, from every port's section: a step's
    `{exit, out, err, cut?, traceback?}`, or the files' `{path: (content, cut)}`."""
    i = text.index("### Every difference (report.py --detail)")
    sect = text[i:text.index("## The writers' notes", i)]
    out: dict = {}
    lines = sect.splitlines()
    k = 0
    while k < len(lines):
        m = re.match(r"^-- (.+?) :: (.*)$", lines[k])
        if not m:
            k += 1
            continue
        name, what = m.group(1), m.group(2)
        if what == "<the files left behind>":
            files = {}
            k += 1
            while k + 1 < len(lines) and re.match(r"^   \S", lines[k]):
                path = lines[k].strip()
                om = re.match(r"^     original: (.*)$", lines[k + 1])
                val, cut, _ = _literal(om.group(1), FILE_CUT)
                files[path] = (val, cut)
                k += 3
            key = (name, "<files>")
            out[key] = _better(out.get(key), files)
            continue
        om = re.match(r"^   original: (.*)$", lines[k + 1])
        argv = ast.literal_eval(what)
        key = (name, json.dumps(argv, ensure_ascii=False))
        out.setdefault(key, []).append(_step_line(om.group(1)))
        k += 2
    return out


def _better(a, b):
    if a is None:
        return b
    for p, (v, cut) in b.items():
        if p not in a or (a[p][1] and not cut):
            a[p] = (v, cut)
    return a


def _merge_steps(seen: list[dict]) -> dict:
    """One step's result from what each port's section printed of the original: a whole value over a cut one."""
    best = dict(seen[0])
    for s in seen[1:]:
        for f in ("out", "err"):
            if f in best.get("cut", []) and f not in s.get("cut", []):
                best[f] = s[f]
                best["cut"] = [c for c in best["cut"] if c != f]
        if not best.get("cut"):
            best.pop("cut", None)
    return best


# ---- the cases ---------------------------------------------------------------------------------------------------

def _case_text(s):
    return s.replace(T, CASE) if isinstance(s, str) else s


def _of(steps: list) -> str:
    firsts = {s[0] if s and s[0] in COMMANDS else None for s in steps}
    return COMMANDS[firsts.pop()] if len(firsts) == 1 and None not in firsts else WHOLE


def _file(seed: bytes):
    try:
        return seed.decode("utf-8")
    except UnicodeDecodeError:
        return {"b64": base64.b64encode(seed).decode("ascii")}


def _ranges(idx: list[int]) -> str:
    return ", ".join(str(i) for i in idx)


def build(text: str, fabulac_text: str) -> dict:
    sc = scenarios(text)
    diffs = differences(text)
    tree = re.search(r"tree: ([0-9a-f]{64})", fabulac_text).group(1)
    fid = re.search(r"^id: (\S+)$", fabulac_text, re.M).group(1)
    cases = []
    for s in sc:
        cid = s["name"].split(" ", 1)[0]
        steps = [list(a) for a in s["steps"]]
        env = {"TALLY_FILE": CASE + "/t.jsonl"}
        for k, v in s["env"].items():
            env[k] = _case_text(v)
        files = {}
        if s["mkdir"]:
            files[s["mkdir"]] = {"dir": True}
        if s["seed"] is not None:
            files[s["seed_path"]] = _file(s["seed"])
        case = {"id": cid, "of": _of(steps), "from": "document", "group": s["group"]}
        if files:
            case["files"] = files
        case["env"] = env
        if s["parallel"]:
            argv, n = s["parallel"]
            case["burst"] = {"argv": list(argv), "times": n}
        case["steps"] = steps
        case["note"] = s["name"]
        expect, known, ambiguous = [None] * len(steps), [], []
        for argv_key in {json.dumps(a, ensure_ascii=False) for a in steps}:
            seen = diffs.get((s["name"], argv_key))
            if not seen:
                continue
            at = [i for i, a in enumerate(steps) if json.dumps(a, ensure_ascii=False) == argv_key]
            if len(at) == 1:
                st = _merge_steps(seen)
                for f in ("out", "err"):
                    st[f] = _case_text(st[f])
                expect[at[0]] = st
                known.append(at[0])
            else:
                ambiguous += at
        says = []
        if known:
            says.append(f"steps {_ranges(sorted(known))}: the original's result as the trial's report printed it, "
                        "where a port differed")
        rest = [i for i in range(len(steps)) if i not in known and i not in ambiguous]
        if rest:
            says.append(f"steps {_ranges(rest)}: not in the trial's document (both ports agreed with the original, "
                        "and the report prints only differences)")
        if ambiguous:
            says.append(f"steps {_ranges(sorted(ambiguous))}: a port differed on one of these same commands; the "
                        "report does not say which")
        exp: dict = {"steps": expect}
        fd = diffs.get((s["name"], "<files>"))
        if fd:
            exp["written"] = {p: _case_text(v) for p, (v, _c) in sorted(fd.items())}
            cut = sorted(p for p, (_v, c) in fd.items() if c)
            if cut:
                exp["written-cut"] = cut
            says.append(f"the files it leaves ({', '.join(sorted(fd))}): as the report printed the original's")
        else:
            says.append("the files it leaves: not in the trial's document")
        if any(e and e.get("cut") for e in expect) or exp.get("written-cut"):
            says.append("a value named in `cut` is only the beginning the report printed")
        case["expect"] = exp
        case["expect-says"] = "; ".join(says) + "."
        case["recorded"] = {"source": {"tree": tree}, "run": RUN, "python": "3.13.11"}
        cases.append(case)
    return {
        "repo": "tally",
        "fabulac": fid,
        "source": {"tree": tree},
        "drafted": "2026-11-05, the migration trial's 53 scenarios (harness/diff.py); written as cases 2026-11-18 by "
                   "tools/transconception/trial_cases.py",
        "boundary": "argv, the environment (TALLY_FILE, HOME), the files of the case folder (the ledger), stdout, "
                    "stderr, exit status; working folder = the case folder. The trial's harness set HOME and "
                    "TALLY_FILE as these cases do; the promoted runner also sets COLUMNS=80, NO_COLOR and "
                    "PYTHONHASHSEED, which the trial did not.",
        "groups": {g: sum(len(c["steps"]) for c in cases if c["group"] == g)
                   for g in dict.fromkeys(c["group"] for c in cases)},
        "masks": MASKS,
        "cases": cases,
    }


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) != 3:
        raise SystemExit(__doc__)
    doc = build(Path(a[0]).read_text(encoding="utf-8"), Path(a[1]).read_text(encoding="utf-8"))
    Path(a[2]).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(c["steps"]) for c in doc["cases"])
    k = sum(1 for c in doc["cases"] for e in c["expect"]["steps"] if e is not None)
    print(f"{len(doc['cases'])} cases, {n} steps, {k} with the original's result -> {a[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
