"""The recorder, the runner and the judge of a transconception: record what the original does on its cases, run a
cshort on the same cases, judge the two.

Promoted for 0.8 from the experiment's kit (docs/v070-x0-sandbox/x0_harness.py, drafted 2026-11-12 from the tally
trial's harness, fixed 2026-11-13 for per-target rulings). The shapes are x0's, so the experiment's own files still
read: a cases file, a recording, a run, a rulings file, a verdict. What 0.8 adds is marked "0.8" below and is optional
in every file: an older file reads as before.

This file is the OWNER'S to run, inside the owner's sandbox (the experiment's x0.sh is that wrapper: no network, no
writing outside a scratch folder the owner names). It is never imported or started by enough, and never run by an
agent: enough reads the files it writes. The standard library only; one file, so that `python -I harness.py` runs it.

    python -I harness.py record CASES IMPL OUT_FOLDER [--seeds 0,1] [--source DIR] [--commit SHA]
    python -I harness.py run    CASES IMPL OUT.json [--seed N]
    python -I harness.py stable RECORDED_A.json RECORDED_B.json OUT.json
    python -I harness.py judge  CASES RECORDED.json RUN.json RULINGS.json VERDICT.json

`record` (0.8) is the recorder: `run` on the original once per hash seed, then `stable`, into OUT_FOLDER as
`recorded-seed<N>.json`, `recorded.json` and `cases.json` (the cases file, byte for byte), the folder enough's
`gather recorded with f` reads. `--source` names the original's folder, so the recording says which source it was
recorded from (its tree digest, by MacroCOSM 18.4.1's rule, and its commit when `--commit` gives it or the folder
holds a `COMMIT` file); a recording that does not say is never taken as fresh.
`run` is the runner: it drives one implementation at its boundary only (argv, stdin, environment, the files of a
fresh folder, stdout, stderr, exit status, the files it leaves). `stable` keeps the steps two seeds agree on.
`judge` compares a cshort's run with the recording and applies the transconceiver's rulings; RULINGS may be `-`
(0.8) for the cases file's own `rulings`, which enough's `entail f as cases` derives from the fabulac. Nothing here
imports the program under test: every implementation is a child process.

The cases file is whole data. One case:
    {"id": "...", "of": "<interface id>", "from": "test|document|reliance|ruled|recorded",
     "files": {"rel/path": "text" | {"b64": "..."} | {"symlink": "target"} | {"dir": true}},
     "env": {"NAME": "value" | null}, "cwd": "rel/dir",
     "burst": {"argv": [...], "times": N},                                    (0.8: N copies at once, first)
     "steps": [["argv", "..."] | {"argv": [...], "stdin": "text" | {...json...}}],
     "reliances": ["<reliance id>", ...], "note": "...",
     "expect": {...}, "recorded": {...}, "stale": "why"}                       (0.8: read by enough, not here)
and beside the cases (0.8): "source": {commit, tree}, the source the fabulac stands on;
"masks": {"out" | "err" | "written": [{"pattern": <a regular expression>, "to": <its replacement>}]}, applied in
order after the folder's own spelling is masked (the tally trial masked its ledger's times this way);
"rulings": {"targets": {...}}, as RULINGS.json holds them.

IMPL.json: {"label", "command": [...], "env": {...}, "path", "scratch", "work", "timeout"} (x0.sh writes it).
"""
from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASE_TOKEN = "<CASE>"
SCRATCH_TOKEN = "<SCRATCH>"
STALE_FINDING = "recorded against another source"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(obj, path):
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(data: bytes, spellings) -> str:
    for s in spellings:
        if s:
            data = data.replace(s.encode(), (CASE_TOKEN if s in spellings[:2] else SCRATCH_TOKEN).encode())
    return data.decode("utf-8", "backslashreplace")


def masked(text: str, masks) -> str:
    """0.8: a cases file's masks for one stream, in order: what varies from run to run and is no behaviour (a time)."""
    for m in masks or []:
        text = re.sub(m["pattern"], m.get("to", ""), text)
    return text


def seed(folder: Path, files: dict):
    for rel, content in sorted(files.items()):
        target = folder / rel
        if not str(target.resolve()).startswith(str(folder.resolve())):
            raise SystemExit(f"case file escapes its folder: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            target.write_bytes(content.encode("utf-8"))
        elif "b64" in content:
            target.write_bytes(base64.b64decode(content["b64"]))
        elif "symlink" in content:
            os.symlink(content["symlink"], target)
        elif content.get("dir"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            raise SystemExit(f"unknown file form for {rel}")


def snapshot(folder: Path, spellings, masks=None):
    out = {}
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for nm in sorted(names):
            full = Path(root, nm)
            rel = str(full.relative_to(folder))
            if full.is_symlink():
                out[rel] = "-> " + os.readlink(full)
            else:
                out[rel] = masked(norm(full.read_bytes(), spellings), masks)
    return out


def as_step(step):
    if isinstance(step, list):
        return {"argv": step, "stdin": None}
    stdin = step.get("stdin")
    if stdin is not None and not isinstance(stdin, str):
        stdin = json.dumps(stdin, ensure_ascii=True)
    return {"argv": step.get("argv", []), "stdin": stdin}


def run_case(impl: dict, case: dict, work_root: Path, seed_value: str, scratch: str, masks=None):
    masks = masks or {}
    folder = Path(tempfile.mkdtemp(prefix="case-", dir=work_root))
    try:
        seed(folder, case.get("files", {}))
        spellings = [str(folder), os.path.realpath(folder), scratch, os.path.realpath(scratch)]
        before = snapshot(folder, spellings, masks.get("written"))
        env = {
            "PATH": impl.get("path", "/usr/bin:/bin"),
            "HOME": str(folder),
            "TMPDIR": str(work_root),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "COLUMNS": "80",
            "LINES": "24",
            "NO_COLOR": "1",
            "PYTHON_COLORS": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": seed_value,
        }
        env.update(impl.get("env", {}))
        for k, v in case.get("env", {}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v.replace(CASE_TOKEN, str(folder))
        cwd = folder / case.get("cwd", ".")
        cwd.mkdir(parents=True, exist_ok=True)

        def call(st):
            argv = [a.replace(CASE_TOKEN, str(folder)) for a in st["argv"]]
            try:
                kw = ({"stdin": subprocess.DEVNULL} if st["stdin"] is None
                      else {"input": st["stdin"].encode("utf-8", "surrogatepass")})
                p = subprocess.run(impl["command"] + argv, env=env, cwd=cwd, timeout=impl.get("timeout", 30),
                                   capture_output=True, **kw)
                return {"exit": p.returncode, "out": masked(norm(p.stdout, spellings), masks.get("out")),
                        "err": masked(norm(p.stderr, spellings), masks.get("err"))}
            except subprocess.TimeoutExpired:
                return {"exit": "timeout", "out": "", "err": ""}
            except OSError as e:
                return {"exit": "cannot-run", "out": "", "err": str(e)}

        result = {}
        burst = case.get("burst")
        if burst:                       # 0.8: N copies of one step at the same moment, before the steps
            st = as_step(burst["argv"] if isinstance(burst.get("argv"), list) else burst)
            n = int(burst.get("times", 1))
            with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
                got = list(ex.map(lambda _: call(st), range(n)))
            result["burst"] = {"exits": sorted({str(g["exit"]) for g in got})}
        steps = [call(as_step(raw)) for raw in case["steps"]]
        after = snapshot(folder, spellings, masks.get("written"))
        written = {k: v for k, v in after.items() if before.get(k) != v}
        written.update({k: "<removed>" for k in before if k not in after})
        return {"steps": steps, "written": written, **result}
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def cmd_run(cases_path, impl_path, out_path, seed_value="0"):
    cases = load(cases_path)
    impl = load(impl_path)
    scratch = impl["scratch"]
    work_root = Path(impl["work"])
    work_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases["cases"]:
        rows.append({"id": case["id"], "of": case["of"], "argv": [as_step(s) for s in case["steps"]],
                     "run": run_case(impl, case, work_root, seed_value, scratch, cases.get("masks"))})
    dump({"impl": impl["label"], "seed": seed_value, "cases_digest": digest(cases_path),
          "python": sys.version, "rows": rows}, out_path)
    print(f"{impl['label']}: {len(rows)} cases, {sum(len(r['argv']) for r in rows)} steps -> {out_path}")


def cmd_stable(a_path, b_path, out_path):
    a, b = load(a_path), load(b_path)
    unstable = []
    for ra, rb in zip(a["rows"], b["rows"]):
        for i, (sa, sb) in enumerate(zip(ra["run"]["steps"], rb["run"]["steps"])):
            if sa != sb:
                unstable.append({"case": ra["id"], "step": i, "seed_a": sa, "seed_b": sb})
        if ra["run"]["written"] != rb["run"]["written"]:
            unstable.append({"case": ra["id"], "step": "written"})
    a["unstable"] = unstable
    a["seeds"] = [a["seed"], b["seed"]]
    dump(a, out_path)
    print(f"recorded: {len(a['rows'])} cases; {len(unstable)} steps differ between hash seeds "
          f"{a['seed']} and {b['seed']} (listed under 'unstable'; each needs a ruling)")


# ---- 0.8: the recorder, and the source a recording is of -------------------------------------------------------

# MacroCOSM 18.4.1's tree digest (the reference code of its appendix), so that a recording names the source the same
# way a fabulac does: what is skipped, and the line hashed per file.
TREE_SKIP_DIRS = frozenset({".git", ".hg", ".svn", ".bzr", "_darcs", "CVS",
                            ".venv", "venv", "__pypackages__", ".tox", ".nox", "node_modules",
                            "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis",
                            ".ipynb_checkpoints", ".cache", "htmlcov", "build", "dist", ".eggs"})
TREE_SKIP_DIR_SUFFIXES = (".egg-info",)
TREE_SKIP_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", ".coverage"})
TREE_SKIP_FILE_SUFFIXES = (".pyc", ".pyo", ".so", ".pyd", ".dylib", ".dll", ".o", ".a", ".class")
TREE_MAX_BYTES = 1_000_000
TREE_SNIFF = 8192


def _tree_skip_dir(d: Path) -> bool:
    n = d.name
    return n in TREE_SKIP_DIRS or n.endswith(TREE_SKIP_DIR_SUFFIXES) or ".cshort-" in n or (d / "pyvenv.cfg").is_file()


def tree_digest(folder) -> str:
    root = Path(folder)
    read = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not ((here / d).is_symlink() or _tree_skip_dir(here / d))]
        for f in filenames:
            p = here / f
            if (p.is_symlink() or f in TREE_SKIP_FILES or f.endswith(TREE_SKIP_FILE_SUFFIXES)
                    or f.endswith(".fabulac.cosm") or ".catem-" in f):
                continue
            data = p.read_bytes()
            if len(data) > TREE_MAX_BYTES or b"\0" in data[:TREE_SNIFF]:
                continue
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            read.append((p.relative_to(root).as_posix(), hashlib.sha256(data).hexdigest()))
    read.sort(key=lambda r: r[0].encode("utf-8"))
    h = hashlib.sha256()
    for rel, d in read:
        h.update(rel.encode("utf-8") + b"\0" + d.encode("ascii") + b"\n")
    return h.hexdigest()


def source_marks(source_dir=None, commit=None) -> dict:
    out = {}
    if source_dir:
        out["tree"] = tree_digest(source_dir)
        c = Path(source_dir, "COMMIT")
        if not commit and c.is_file():
            commit = c.read_text(encoding="utf-8").strip()
    if commit:
        out["commit"] = commit
    return out


def cmd_record(cases_path, impl_path, out_folder, seeds=("0", "1"), source_dir=None, commit=None):
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cases_path, out / "cases.json")
    paths = []
    for s in seeds:
        p = out / f"recorded-seed{s}.json"
        cmd_run(out / "cases.json", impl_path, p, seed_value=str(s))
        paths.append(p)
    if len(paths) == 1:
        rec = load(paths[0])
        rec["unstable"], rec["seeds"] = [], [rec["seed"]]
        dump(rec, out / "recorded.json")
    else:
        cmd_stable(paths[0], paths[1], out / "recorded.json")
    rec = load(out / "recorded.json")
    rec["source"] = source_marks(source_dir, commit)
    dump(rec, out / "recorded.json")
    print(f"recorded from {rec['source'] or 'a source it does not name'} -> {out}")


def _stale(cases: dict, rec: dict):
    """0.8: why a recording does not stand against the source the cases file names, or None."""
    now, then = cases.get("source") or {}, rec.get("source") or {}
    for key in ("tree", "commit"):
        if now.get(key) and then.get(key):
            return None if now[key] == then[key] else (f"recorded from {key} {then[key][:12]}; the cases stand on "
                                                       f"{key} {now[key][:12]}")
    return None


# ---- the judge -------------------------------------------------------------------------------------------------

def crashed(step):
    return "Traceback (most recent call last)" in step["err"]


NORMALISERS = {
    # The closed list of allowances the judge understands for `alike`. Add one only by the owner's ruling.
    "exit-only": lambda s: (s["exit"],),
    "exit-and-stdout": lambda s: (s["exit"], s["out"]),
    "stderr-said-or-not": lambda s: (s["exit"], s["out"], bool(s["err"].strip())),
    "lines-in-any-order": lambda s: (s["exit"], sorted(s["out"].splitlines()), sorted(s["err"].splitlines())),
    # Sitting 2 (2026-11-18): a value may take the target's own type where the kept interface cannot see the
    # difference. The judge sees only the interface: it compares exit status, stdout and stderr exactly, as for
    # `kept`. A type of the target's own that changed what the interface prints is a difference, not an allowance.
    "own-types": lambda s: (s["exit"], s["out"], s["err"]),
}


def same(orig, other, ruling):
    if crashed(orig):  # uncaught-error: kept as the status only
        return orig["exit"] == other["exit"]
    if ruling and ruling.get("is") == "alike":
        f = NORMALISERS.get(ruling.get("allowing", ""))
        if f is None:
            return None  # an allowance the judge cannot apply: reported as unjudged
        return f(orig) == f(other)
    return orig == other


def pick_target(rulings, label):
    """The rulings for this cshort: the target whose `labels` begin its label (go-apart -> go), or the file's top
    level when it names no targets (the form written before 2026-11-13)."""
    targets = rulings.get("targets")
    if not targets:
        return rulings.get("made-for"), rulings
    for name, t in targets.items():
        if any(label == p or label.startswith(p + "-") for p in t.get("labels", [name])):
            return name, t
    raise SystemExit(f"no rulings for the label {label!r}: name it under a target's labels in the rulings file")


def step_rulings(r_case):
    """{step: ruling} from a case's ruling (one mapping or a list; `also` read as one more). Each covers only the
    `steps` it names; one that names none covers every step."""
    rs = list(r_case) if isinstance(r_case, list) else ([r_case] if r_case else [])
    rs += [r["also"] for r in rs if r.get("also")]
    out = {}
    for r in rs:
        for s in r.get("steps", ["*"]):
            out[s] = r
    return out


def cmd_judge(cases_path, recorded_path, run_path, rulings_path, out_path):
    cases_doc = load(cases_path)
    cases = {c["id"]: c for c in cases_doc["cases"]}
    rec, run = load(recorded_path), load(run_path)
    own = rulings_path in ("-", None)
    rulings = (cases_doc.get("rulings") or {}) if own else load(rulings_path)
    target, chosen = pick_target(rulings, run["impl"])
    iface = chosen.get("interfaces", {})
    by_case = chosen.get("cases", {})
    unstable = {(u["case"], u["step"]) for u in rec.get("unstable", [])}
    stale = _stale(cases_doc, rec)
    counted = agree = 0
    findings = []
    for ro, rc in zip(rec["rows"], run["rows"]):
        cid = ro["id"]
        if cases[cid].get("stale"):     # 0.8: a case enough marked stale is reported, never judged silently
            findings.append({"case": cid, "kind": STALE_FINDING, "why": cases[cid]["stale"]})
            continue
        r_if = iface.get(cases[cid]["of"])
        by_step = step_rulings(by_case.get(cid))
        if r_if is None:
            findings.append({"case": cid, "kind": "interface not ruled", "of": cases[cid]["of"]})
            continue
        if r_if["is"] in ("free", "changed"):
            continue
        pairs = list(enumerate(zip(ro["run"]["steps"], rc["run"]["steps"])))
        if ro["run"]["written"] or rc["run"]["written"]:  # files left behind count as a step only when there are any
            pairs.append(("written", (ro["run"]["written"], rc["run"]["written"])))
        for i, (o, c) in pairs:
            r_step = by_step.get(i, by_step.get("*"))
            if r_step and r_step["is"] in ("free", "changed"):  # shown, not counted (assumption A3)
                if o != c:
                    findings.append({"case": cid, "step": i, "kind": "ruled difference", "ruling": r_step,
                                     "argv": ro["argv"][i] if i != "written" else "written",
                                     "original": o, "cshort": c})
                elif r_step["is"] == "changed":
                    findings.append({"case": cid, "step": i, "kind": "ruled change not seen", "ruling": r_step})
                continue
            r_cmp = r_step if r_step and r_step["is"] == "alike" else r_if
            if (cid, i) in unstable and r_cmp is r_if:  # only a ruling of this case's step settles it
                findings.append({"case": cid, "step": i, "kind": "original unstable, not ruled"})
                continue
            counted += 1
            ok = (o == c) if i == "written" else same(o, c, r_cmp)
            if ok is None:
                findings.append({"case": cid, "step": i, "kind": "allowance unknown to the judge",
                                 "allowing": r_cmp.get("allowing")})
                continue
            if ok:
                agree += 1
                continue
            findings.append({"case": cid, "step": i, "kind": "UNRULED difference",
                             "ruling": r_step, "argv": ro["argv"][i] if i != "written" else "written",
                             "original": o, "cshort": c})
    share = agree / counted if counted else 0.0
    shown = ("ruled difference", "ruled change not seen")  # neither needs a ruling; the second is for reading
    unruled = [f for f in findings if f["kind"] not in shown]
    verdict = {
        "cshort": run["impl"], "against": rec["impl"], "target": target, "recorded_digest": digest(recorded_path),
        "run_digest": digest(run_path), "rulings_digest": digest(cases_path if own else rulings_path),
        "steps": {"kept": counted, "agree": agree}, "share": round(share, 4),
        "passes_95": share >= 0.95, "unruled": len(unruled),
        "passes": share >= 0.95 and not unruled and not stale, "findings": findings,
    }
    if rec.get("source"):           # 0.8: the source the recording, and so this verdict, stands on
        verdict["source"] = rec["source"]
    if stale:
        verdict["stale"] = stale
    dump(verdict, out_path)
    print(f"{run['impl']} against {rec['impl']} (rulings for {target}): {agree}/{counted} steps agree at kept "
          f"interfaces ({share:.1%}); {sum(f['kind'] == 'ruled difference' for f in findings)} ruled differences; "
          f"{len(unruled)} findings need a ruling; passes: {verdict['passes']}")
    if stale:
        print(f"  !! the recording is stale: {stale}; record the original again")
    for f in findings:
        if f["kind"] != "ruled difference":
            print(f"  {'..' if f['kind'] in shown else '--'} {f['case']} step {f.get('step', '')}: {f['kind']}")


def _opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "run":
        s = _opt(args, "--seed", "0")
        cmd_run(*args, seed_value=s)
    elif cmd == "record":
        seeds = tuple(_opt(args, "--seeds", "0,1").split(","))
        src = _opt(args, "--source")
        sha = _opt(args, "--commit")
        cmd_record(*args, seeds=seeds, source_dir=src, commit=sha)
    elif cmd == "stable":
        cmd_stable(*args)
    elif cmd == "judge":
        cmd_judge(*args)
    else:
        raise SystemExit(__doc__)
