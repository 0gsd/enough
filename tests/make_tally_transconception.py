"""Make tally's transconception, the conformance fixture (lane W4-X9, 0.8): `tests/fixtures/fabula/transconception/
tally/` holds, beside tally's own pinned fixture and never over it, the whole path from ground to entailing into Go
and Rust, as a Thym conformance suite (THYM 24.3's folder shape: `programs/`, `expected/`, `replay/`, `inputs/`)
that `enough.thym.conform.conform(<the folder>)` runs, and a second implementation can be held to.

What is recorded and what is simulated (the fixture's README says the same):

- **Rules** (recorded as they ran, no model): ground, the cases file, the questions a transconceiver is asked, the
  settling, the landing, the gates, the checks.
- **The sittings are simulated** (two, as the dialectic asks: the transconceiver's statements are asked only once
  there is a transconceiver): every ruling question is answered "as proposed" (`kept`, for an item never ruled), the
  lane `open` (tally is MIT), who rules "nobody: a transconceiver simulated…", and the five statements from tally's
  own files, each saying "(simulated)". Each answers volume's session says it is simulated. tally's own open
  questions of 2026-11-05 are left open.
- **The model is a recorded fake** (`engine: model:scripted`): the weighings' scores (2 on every point a model
  answers), the layouts and the cshorts' files (stubs, saying so). No model was asked anything.
- **The spikes are simulated**: there is no Go or Rust build of tally, nor any spike of it. Each spike's verdict is a
  file written here, marked `simulated`, with no finding; it lets the path reach `target-confirmed`. The gates are
  recorded before it (level 0: target-confirmed does not hold) and after it.
- **No evidence is claimed**: each cshort's entry says `evidence: []` (not judged). Nothing was built or run. The
  round trip is not claimed either (no N:target in Python), so `round-trip` fails on every stage and neither gate
  holds: tally's Python cshort of 2026-11-05 was never judged. The trial of 2026-11-05 judged a TypeScript and a
  Swift tally, never Go or Rust; its 18 recorded steps are in the cases file and judge nothing here.

Run: `python tests/make_tally_transconception.py [DEST]` (default the fixture folder). It writes the made parts
whole (`programs/ expected/ replay/ inputs/ landed/ recorded/`; the README, `tally.cases.json` and `outside/` are kept), every
run id and clock pinned, so making it again gives the same bytes but for each recorded run's plan and trace, which
carry the wall clock (`tests/test_transconception_fixture.py` holds that). Re-make it, never hand-edit it.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from enough import dialectic as dl  # noqa: E402
from enough import macrocosm as mc  # noqa: E402
from enough import thym  # noqa: E402
from enough import thym_host as H  # noqa: E402
from enough import transconception as tc  # noqa: E402
from enough.thym import Refusal  # noqa: E402
from enough.thym import plan as pl  # noqa: E402
from enough.thym import run as RUN  # noqa: E402
from enough.thym.coprocessor import candidate  # noqa: E402
from enough.thym.values import Value, digest_path  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "fabula"
TALLY = FIX / "tally"                                   # tally's pinned fixture: read, copied, never written
TALLY_FABULAC = FIX / "tally.fabulac.cosm"
CASES = FIX / "transconception" / "tally" / "tally.cases.json"   # W2-X4's, from the trial
DEST = FIX / "transconception" / "tally"

UTC = dt.timezone.utc
SIMULATED_SITTING = ("simulated for the conformance fixture: nobody sat; each ruling is answered as proposed, the "
                     "rest from tally's own files")
SIMULATED_SPIKE = ("simulated for the conformance fixture: there is no {title} build of tally and no spike of it; "
                   "this verdict was written, not judged, so that the path reaches target-confirmed")
LANGUAGES = (("go", "Go"), ("rust", "Rust"))
SUFFIX = {"Go": "go", "Rust": "rs"}
PACKAGING = {"Go": "go.mod", "Rust": "Cargo.toml"}
SPIKE_CASES = ["P:case/cli-json-and-error"]

# The stages, in order: each a file under inputs/ (what a program takes), made by the run or the host step before it.
KEPT = "tally.0-kept.fabulac.cosm"           # tally's fabulac, kept for transconception (purpose set, nothing else)
GROUNDED = "tally.1-grounded.fabulac.cosm"   # ground repo with f
ASKED = "tally.2-asked.fabulac.cosm"         # question f, gathered (rules): the rulings and who rules
SETTLED = "tally.3-settled.fabulac.cosm"     # the first sitting (simulated), settled
ASKED_AGAIN = "tally.4-asked-again.fabulac.cosm"   # question f again: the transconceiver's five statements
RULED = "tally.5-ruled.fabulac.cosm"         # the second sitting (simulated), settled: gate 1 holds
WEIGHED_GO = "tally.6-weighed-go.fabulac.cosm"
WEIGHED = "tally.7-weighed.fabulac.cosm"     # weighed in Go and in Rust (each spike at level 0)
FINAL = "tally.fabulac.cosm"                 # each spike's level read from its simulated verdict: what entailing takes
STAGES = (KEPT, GROUNDED, ASKED, SETTLED, ASKED_AGAIN, RULED, WEIGHED_GO, WEIGHED, FINAL)
RECORDED = "tally.9-recorded.fabulac.cosm"   # FINAL, the round trip's target, the recorded cases as outside items
JUDGED = "tally.10-judged.fabulac.cosm"      # RECORDED with the round trip's verdict gathered (lane T1, 0.9)

# ---------------------------------------------------------------------------
# The programs: the text's own
# ---------------------------------------------------------------------------

PROGRAMS: dict[str, str] = {   # each the text's own (Thym 20.10, 20.6, 22.4), under a `thym 1` line, byte for byte
    "ground-the-fabulac": (
        "thym 1\n\nprogram ground-the-fabulac\n  why: what the program leans on in its language is found by rule, "
        "each reliance citing where the\n       language's own text states it.\n  must: nothing in the repository is "
        "run, imported or installed.\n\n  takes repo: folder, f: fabula\n  gives g: fabula\n\n  give ground repo "
        "with f                          -- one reliance per ground entry the syntax shows\nend\n"),
    "hand-out-the-cases": (
        "thym 1\n\nprogram hand-out-the-cases\n  why: the cases that stand outside go to the recorder as data, written "
        "by rules.\n\n  takes f: fabula\n  gives cases: text\n\n  give entail f as cases\nend\n"),
    "raise-the-questions": (
        "thym 1\n\nprogram raise-the-questions\n  why: where the build was unsure it asks the person who knows, and "
        "the questions land with the\n       fabulac.\n  decided 2026-11-05: the answers come back in a second run, "
        "settle; nothing waits inside a run.\n\n  takes f: fabula\n  gives g: fabula\n  keeps fabula-checks\n\n  let "
        "asked = question f\n  give gather asked with f\nend\n"),
    "settle-the-answers": (REPO / "defaults" / "thym" / "settle.thym").read_text(encoding="utf-8"),
    "weigh-a-target": (
        "thym 1\n\nprogram weigh-a-target\n  why: a language is weighed on the twelve points before anything is "
        "entailed into it.\n\n  takes f: fabula, language: string\n  gives g: fabula\n\n  give weigh f in language"
        "                         -- one N:target, its scores, what it provides, its verdict\nend\n"),
    "entail-in-a-language": (
        "thym 1\n\nprogram entail-in-a-language\n  why: a weighed and confirmed language gets a layout first, then "
        "the code, apart from the source.\n\n  takes f: fabula, language: string\n  gives arrangement: short, code: "
        "folder\n\n  let drawn = entail f as layout in language       -- the files, their parts, the names kept "
        "interfaces take\n  give arrangement: drawn\n  give code: entail f as code in language with drawn\nend\n"),
}

def _at(h: int, m: int) -> dt.datetime:
    return dt.datetime(2026, 11, 18, h, m, tzinfo=UTC)


# The path, in order. A run: ("run", program, run id, clock, {input: (type, path)}, rules only, {give: stage file});
# a host step: ("host", what, clock). `{answers-1}` and `{answers-2}` are the sittings' answers volumes.
PATH: list[tuple] = [
    ("run", "ground-the-fabulac", "2026-11-18-1200-a901", _at(12, 0),
     {"repo": ("folder", "inputs/tally"), "f": ("fabula", f"inputs/{KEPT}")}, True, {"g": GROUNDED}),
    ("run", "hand-out-the-cases", "2026-11-18-1205-a902", _at(12, 5), {"f": ("fabula", f"inputs/{GROUNDED}")}, True,
     {}),
    ("run", "raise-the-questions", "2026-11-18-1210-a903", _at(12, 10), {"f": ("fabula", f"inputs/{GROUNDED}")}, True,
     {"g": ASKED}),
    ("host", "sitting-1", _at(12, 30)),
    ("run", "settle-the-answers", "2026-11-18-1240-a904", _at(12, 40),
     {"f": ("fabula", f"inputs/{ASKED}"), "said": ("volume", "inputs/{answers-1}")}, True, {"g": SETTLED}),
    ("run", "raise-the-questions", "2026-11-18-1245-a905", _at(12, 45), {"f": ("fabula", f"inputs/{SETTLED}")}, True,
     {"g": ASKED_AGAIN}),
    ("host", "sitting-2", _at(12, 50)),
    ("run", "settle-the-answers", "2026-11-18-1255-a906", _at(12, 55),
     {"f": ("fabula", f"inputs/{ASKED_AGAIN}"), "said": ("volume", "inputs/{answers-2}")}, True, {"g": RULED}),
    ("run", "weigh-a-target", "2026-11-18-1300-a907", _at(13, 0),
     {"f": ("fabula", f"inputs/{RULED}"), "language": ("string", "inputs/go.txt")}, False, {"g": WEIGHED_GO}),
    ("run", "weigh-a-target", "2026-11-18-1310-a908", _at(13, 10),
     {"f": ("fabula", f"inputs/{WEIGHED_GO}"), "language": ("string", "inputs/rust.txt")}, False, {"g": WEIGHED}),
    ("host", "spikes", _at(13, 30)),
    ("run", "entail-in-a-language", "2026-11-18-1400-a909", _at(14, 0),
     {"f": ("fabula", f"inputs/{FINAL}"), "language": ("string", "inputs/go.txt")}, False, {}),
    ("run", "entail-in-a-language", "2026-11-18-1410-a910", _at(14, 10),
     {"f": ("fabula", f"inputs/{FINAL}"), "language": ("string", "inputs/rust.txt")}, False, {}),
]
LANDED_STAMP = {"go": "2026-11-18-1400", "rust": "2026-11-18-1410"}

# The simulated sittings' answers. The first: every ruling as proposed (`kept`, for an item never ruled), the lane
# read from the licence tally names (MIT lets anyone make a new work and pass it on: open), and who rules. The
# second: the transconceiver's five statements, each read from tally's own files.
WHO_RULES = ("nobody: a transconceiver simulated for the conformance fixture of 0.8; no person ruled tally's "
             "transconception")
LANE = "open"
STATEMENTS = {
    "licence": "MIT, as tally/LICENSE says (simulated)",
    "lane-said": "MIT lets anyone make a new program from the source and pass it on, keeping its notice (simulated)",
    "confidential": "nothing reached the fixture in confidence: tally is a public test fixture (simulated)",
    "programs": "tally, in Go and in Rust (simulated)",
    "attribution": "tally's MIT notice and its holder's credit, as tally/LICENSE gives them (simulated)",
}


# ---------------------------------------------------------------------------
# The recorded fake model
# ---------------------------------------------------------------------------

def _t(inputs: dict, k: str) -> str:
    v = inputs.get(k)
    if isinstance(v, tuple):
        v = v[0]
    return v.text() if isinstance(v, Value) else str(v or "")


def weigh_reply(inputs: dict) -> str:
    """A weighing's answer: every point it is asked scored 2, a row `written` for every item no entry answers, a
    spike aimed at one case, no condition of its own."""
    asked = [int(ln.split(".", 1)[0]) for ln in _t(inputs, "points").splitlines() if ln.strip()]
    open_ids = [ln[2:].split(":", 2)[0] + ":" + ln[2:].split(":", 2)[1] for ln in _t(inputs, "open").splitlines()
                if ln.startswith("- ")]
    data = {"weighed": [{"point": n, "score": 2, "evidence": f"the recorded fake model's reading of point {n}"}
                        for n in asked],
            "provides": [{"for": i, "by": "written", "what": "written by hand in the new program"} for i in open_ids],
            "spike": {"use": "the option reader (C:reliance/argparse-surface), small", "cases": list(SPIKE_CASES)},
            "conditions": []}
    return mc.dump(data) + "engine: model:scripted\n"


def _ident(iid: str) -> str:
    return "N_" + re.sub(r"\W", "_", iid.split("/", 1)[-1])


def layout_reply(inputs: dict) -> str:
    """A layout: the packaging file first, then one source file holding every interface it is asked to map; a type
    for each own-types item; a fill for each gap."""
    lang = _t(inputs, "language")
    ids = [ln[2:].split(": ", 1)[0] for ln in _t(inputs, "map").splitlines() if ln.startswith("- ")]
    types = mc.yaml_load(_t(inputs, "types")) if _t(inputs, "types") != "(none)" else []
    gaps = mc.yaml_load(_t(inputs, "gaps")) if _t(inputs, "gaps") != "(none)" else []
    data = {"files": [{"path": PACKAGING[lang], "holds": f"the {lang} package", "interfaces": []},
                      {"path": f"main.{SUFFIX[lang]}", "holds": "the whole program",
                       "interfaces": [{"id": i, "name": _ident(i)} for i in ids]}],
            "types": [{"for": t["for"], "type": f"its own {lang} type"} for t in types or []],
            "gaps": [{"for": g["for"], "fill": f"written in main.{SUFFIX[lang]}"} for g in gaps or []]}
    return mc.dump(data) + "engine: model:scripted\n"


def writer_reply(inputs: dict) -> str:
    """One file: every name the layout gives it defined as an empty stub, and one guess written down."""
    lang, path = _t(inputs, "language"), _t(inputs, "path")
    brief = mc.yaml_load(_t(inputs, "brief"))
    names = [x["takes the name"] for x in brief.get("interfaces") or []]
    if path == PACKAGING[lang]:
        body = "module tally\n" if lang == "Go" else '[package]\nname = "tally"\n'
    elif lang == "Go":
        body = ("// a stub by the recorded fake model of the conformance fixture; never built\npackage main\n\n"
                + "".join(f"func {n}() {{}}\n" for n in names))
    else:
        body = ("// a stub by the recorded fake model of the conformance fixture; never built\n"
                + "".join(f"pub fn {n}() {{}}\n" for n in names))
    fence = SUFFIX[lang] if path != PACKAGING[lang] else ("" if lang == "Go" else "toml")
    return (f"```{fence}\n{body}```\n\n## Notes\n\n"
            "- the fabulac does not say the line width: 80 chosen (a recorded fake's guess, written down)\n")


class FakeModel:
    """The recorded fake: answers by the request's step, as the host's model would be asked (THYM 12.2)."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def complete(self, contract, inputs, *, budget):
        ins = {k: (v[0] if isinstance(v, tuple) else v) for k, v in inputs.items()}
        ins = {k: v if isinstance(v, Value) else Value("string", str(v)) for k, v in ins.items()}
        step = _t(ins, "fabulac") or str(contract.get("move") or "")
        self.asked.append(step)
        if contract.get("move") == "weigh":
            text = weigh_reply(ins)
        elif step == "layout":
            text = layout_reply(ins)
        else:
            text = writer_reply(ins)
        return candidate(text, engine="model:scripted", tokens=10)


# ---------------------------------------------------------------------------
# Making the folder
# ---------------------------------------------------------------------------

def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _json(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def _output(run_dir: Path, name: str) -> Path:
    found = sorted((run_dir / "outputs").glob(f"{name}.*")) or sorted((run_dir / "outputs").glob(name))
    if not found:
        raise RuntimeError(f"{run_dir.name} gave no output {name}")
    return found[0]


def plan_of(dest: Path, program: str, inputs: dict, fmt: dict) -> dict:
    """The plan of a run of `program` on `inputs` (paths under the folder), every file input held to its digest."""
    rows = []
    for name, (typ, rel) in inputs.items():
        row = {"name": name, "type": typ, "path": rel.format(**fmt)}
        if typ != "folder":
            row["sha256"] = digest_path(dest / row["path"])
        rows.append(row)
    c = thym.check_file(dest / "programs" / f"{program}.thym")
    if isinstance(c, Refusal):
        raise RuntimeError(f"{program}: {c}")
    p = pl.plan(c, rows, program=program)
    if isinstance(p, Refusal):
        raise RuntimeError(f"{program}: {p}")
    return p


def _run(dest: Path, scratch: Path, program: str, rid: str, now: dt.datetime, plan: dict, rules: bool):
    model = FakeModel()
    t = RUN.run(plan, inputs_root=dest, root=scratch, program=dest / "programs" / f"{program}.thym",
                coprocessor=None if rules else model, rules=rules, engines=H.engines(feed=None), now=now, run_id=rid)
    if isinstance(t, Refusal) or not t.landed:
        raise RuntimeError(f"{program} ({rid}): {getattr(t, 'refusal', t)}")
    for rec in t.records:
        bad = [x for x in rec.get("checks") or [] if not x.get("ok")]
        if bad:
            raise RuntimeError(f"{program} ({rid}): a check failed: {bad}")
    out = dest / "replay" / program / rid
    shutil.copytree(t.dir, out)
    return out, t


def _sitting(dest: Path, asked_name: str, at: dt.datetime) -> str:
    """A simulated sitting on the questions the transconception banks raised (THYM 22.2: an answers volume beside the
    asked fabulac); every other open question of tally's is left as it is. Returns the volume's name."""
    asked = dest / "inputs" / asked_name
    tw = dl.open_twin(asked)
    answers = []
    for q in tw.ledger.questions():
        bank = str((q.get("raised") or {}).get("from") or "")
        if q.get("state", "open") != "open" or not bank.startswith("transconception-"):
            continue
        key = bank.split("/", 1)[1]
        if q.get("proposed"):
            answers.append({"question": q["id"], "says": "as proposed"})
        elif key == "who-rules":
            answers.append({"question": q["id"], "says": WHO_RULES})
        elif key == "lane":
            answers.append({"question": q["id"], "says": LANE})
        elif key in STATEMENTS:
            answers.append({"question": q["id"], "says": STATEMENTS[key]})
        else:
            raise RuntimeError(f"the simulated sitting has no answer for {q['id']} ({bank})")
    if not answers:
        raise RuntimeError(f"nothing to answer in {asked_name}")
    av = dl.answers_delta(tw, answers, session={"with": {"to": "transconceiver", "who": SIMULATED_SITTING}}, at=at)
    path = dl.answers_path(asked, at=at)
    _write(path, dl.write_answers_volume(av))
    return path.name


def _spikes(dest: Path, at: dt.datetime) -> None:
    """The simulated spike verdicts, and the final fabulac with each spike's level read from its verdict."""
    data = mc.yaml_load((dest / "inputs" / WEIGHED).read_text(encoding="utf-8"))
    for lang, title in LANGUAGES:
        verdict = {"cshort": f"{lang}-spike", "against": "original", "target": lang,
                   "simulated": SIMULATED_SPIKE.format(title=title), "steps": {"kept": 0, "agree": 0}, "share": 0.0,
                   "passes_95": False, "unruled": 0, "passes": False, "findings": []}
        raw = _json(verdict).encode("utf-8")
        rel = f"spikes/{lang}-spike.verdict.json"
        (dest / "inputs" / "spikes").mkdir(parents=True, exist_ok=True)
        (dest / "inputs" / rel).write_bytes(raw)
        t = next(n for n in data["nodes"] if n["id"] == f"N:target/{lang}")
        t["spike"] = tc.spike_from_verdict(t["spike"], verdict, where=rel, digest=hashlib.sha256(raw).hexdigest(),
                                           at=f"{at:%Y-%m-%dT%H:%M}")
    _write(dest / "inputs" / FINAL, mc.dump(data))


def _land(dest: Path, entailed: dict) -> None:
    """The host's landing (`tc.land_in_language`) of each layout and cshort beside a copy of the final fabulac, in
    `landed/`, with the entry the move made (`evidence: []`)."""
    landed = dest / "landed"
    landed.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dest / "inputs" / FINAL, landed / FINAL)
    for lang, _title in LANGUAGES:
        t = entailed[lang]
        code = t.values["code"]
        files = {e.path: code.payload.text(e.path) for e in code.payload.entries}
        tc.land_in_language(landed / FINAL, language=lang, stamp=LANDED_STAMP[lang],
                            layout=t.values["arrangement"].text(), cshort=files, entry=code.origin["entry"])


# ---------------------------------------------------------------------------
# The round trip (lane T1, 0.9): recorded outside enough, rebuilt blind, judged
# ---------------------------------------------------------------------------
#
# The recording, the rebuild, its run and its verdict were made outside enough, in the sandbox, and are kept in
# `outside/` (the maker reads them, never makes them; `outside/README.md` says how they were made). From them the
# maker writes two stages beside the path, after FINAL, never over it (the entailing runs above take FINAL):
#
# - RECORDED: FINAL with the round trip's target (`N:target/python`, the source language, not weighed), the
#   round trip's `shorts` entry (no evidence yet), and the recorded cases as outside `P:case` items;
# - JUDGED: RECORDED with the verdict read into the round trip's evidence (`tc.fold_verdict`).

OUTSIDE = DEST / "outside"
ROUNDTRIP = "py-roundtrip"
ROUNDTRIP_AT = "2026-11-22T13:00"
ROUNDTRIP_BY = ("a fresh agent (model opus, lane T1 of the 0.9 build) that had not seen tally's source, from "
                f"inputs/{FINAL} alone")
JUDGE_BY = "the judge (tools/transconception/harness.py), run by an agent in the sandbox (lane T1; 0.8 pins 9, 21)"
#: What each command a step drives exercises, by rule; a step that exits other than 0 also exercises the errors.
STEP_BEHAVIOURS = {"add": ["C:behaviour/add", "C:behaviour/read"], "undo": ["C:behaviour/undo", "C:behaviour/read"],
                   "show": ["C:behaviour/show", "C:behaviour/read"]}


def _target_python() -> dict:
    return {"id": "N:target/python", "type": "target", "name": "python",
            "summary": "A transconception of tally into python: the round trip, the source language again, to test "
                       "the fabulac alone.",
            "stance": "observed", "language": "python", "weighed": "not weighed (the source language)",
            "provenance": {"mode": "manual", "confidence": 1, "state": "known",
                           "sources": ["outside/README.md"]},
            "made": {"move": "hand", "run": "T1-2026-11-22", "engine": "rules"}}


def targeted(data: dict) -> dict:
    """FINAL with the round trip's target and its `shorts` entry (no evidence): what the recording's cases file
    was handed out from."""
    out = copy.deepcopy(data)
    out["shorts"] = list(out.get("shorts") or []) + [{
        "path": f"../outside/{ROUNDTRIP}/", "at": ROUNDTRIP_AT, "by": ROUNDTRIP_BY, "mode": "model",
        "order": "code", "language": "python", "entailed": "apart", "target": "N:target/python"}]
    out["nodes"] = list(out["nodes"]) + [_target_python()]
    return out


def handed_out(data: dict) -> str:
    """The cases file the recorder ran on: `entail f as cases`'s rule (`tc.cases_document`) over the targeted
    fabulac and the cases file beside it."""
    cat = {k: v for k, v in data.items() if k != "nodes"}
    doc, _ = tc.cases_document(cat, data["nodes"], existing=json.loads(CASES.read_text(encoding="utf-8")))
    return tc.dump_cases(doc)


def _case_item(case: dict) -> dict:
    """One recorded case as an outside `P:case` item: of the interface it drives and, by rule, the behaviours its
    steps exercise (STEP_BEHAVIOURS), its steps and the original's recorded results."""
    steps = case["steps"]
    exp = case["expect"]["steps"]
    of = [f"C:interface/{case['of']}"]
    for s, e in zip(steps, exp):
        argv = s if isinstance(s, list) else s.get("argv", [])
        for b in STEP_BEHAVIOURS.get(argv[0] if argv else "", []) + (
                ["C:behaviour/errors"] if e.get("exit") != 0 else []):
            if b not in of:
                of.append(b)
    given: dict = {k: case[k] for k in ("files", "env", "cwd") if case.get(k) not in (None, {}, "")}
    given["steps"] = [tc.given_step(s) for s in steps]
    expect: dict = {"steps": [tc.case_expect(e) for e in exp]}
    if case["expect"].get("written"):
        expect["files"] = case["expect"]["written"]
    rec = dict(case["recorded"])
    src = rec.pop("source", {}) or {}
    item = {"id": f"P:case/trial-{case['id'].lower()}", "type": "case", "name": case.get("note") or case["id"],
            "summary": f"The migration trial's scenario {case['id']}, recorded from the original "
                       f"({case.get('group', '')}).",
            "stance": "observed", "worksheet-id": case["id"], "of": of, "stands": "outside", "from": "recorded",
            "drafted-from": case.get("from") or "document", "given": given, "expect": expect,
            "recorded": {**({"source-tree": src["tree"]} if src.get("tree") else {}),
                         **({"source-commit": src["commit"]} if src.get("commit") else {}), **rec}}
    if case.get("note"):
        item["note"] = case["note"]
    item["provenance"] = {"mode": "derived", "confidence": 1, "state": "known",
                          "sources": [f"outside/recording/recorded.json#{case['id']}"]}
    item["made"] = {"move": "hand", "run": "T1-2026-11-22", "engine": "rules"}
    return item


def _roundtrip(dest: Path) -> None:
    """The two stages of the round trip (RECORDED, JUDGED), from what `outside/` holds."""
    outside = dest / "outside"
    data = mc.yaml_load((dest / "inputs" / FINAL).read_text(encoding="utf-8"))
    t = targeted(data)
    raw = (outside / "recording" / "cases.json").read_text(encoding="utf-8")
    if raw != handed_out(t):
        raise RuntimeError("outside/recording/cases.json is not the cases file entail f as cases gives the targeted "
                           "fabulac: record it again")
    cat = {k: v for k, v in t.items() if k != "nodes"}
    doc = json.loads(raw)
    doc, report = tc.gather_recorded(doc, tc.read_recording_folder(outside / "recording"), now=tc.source_of(cat))
    if report["stale"] or report["unknown"] or len(report["recorded"]) != len(doc["cases"]):
        raise RuntimeError(f"the recording does not stand whole: {report}")
    t["nodes"] = t["nodes"] + [_case_item(c) for c in doc["cases"]]
    _write(dest / "inputs" / RECORDED, mc.dump(t))
    vraw = (outside / ROUNDTRIP / "verdict.json").read_bytes()
    verdict = tc.read_verdict(vraw)
    cat = {k: v for k, v in t.items() if k != "nodes"}
    new_cat, _rep = tc.fold_verdict(cat, verdict, verdict_bytes=vraw, where=f"../outside/{ROUNDTRIP}/verdict.json",
                                    at=ROUNDTRIP_AT, by=JUDGE_BY)
    _write(dest / "inputs" / JUDGED, mc.dump({**new_cat, "nodes": t["nodes"]}))


def problems(rep: mc.Report) -> dict:
    return {"ok": rep.ok, "errors": [str(p) for p in rep.errors], "warnings": [str(p) for p in rep.warnings]}


def gates_of(path: Path, source: Path) -> dict:
    """Gate 1 and gate 2 in each language, as the card reads them (`tc.ready_to_keep`, `tc.ready_to_entail`)."""
    out = {"ready-to-keep": tc.ready_to_keep(path, source=source)}
    for lang, _ in LANGUAGES:
        out[f"ready-to-entail {lang}"] = tc.ready_to_entail(path, lang, source=source)
    return out


def recorded_files(dest: Path) -> list[Path]:
    """The stage fabulacs whose checks and gates the fixture records: every stage, then the landed one."""
    return ([dest / "inputs" / s for s in STAGES] + [dest / "landed" / FINAL]
            + [dest / "inputs" / s for s in (RECORDED, JUDGED)])


def reports(dest: Path) -> tuple[dict, dict]:
    """What every check of the fabula's lint says of each stage (`checks.json`), and what the gates report
    (`gates.json`), keyed by the file's path under the folder. The source is the copy in `inputs/tally/`."""
    source = dest / "inputs" / "tally"
    from enough import fabula as FAB
    checks, gates = {}, {}
    for p in recorded_files(dest):
        key = p.relative_to(dest).as_posix()
        checks[key] = problems(FAB.lint(p))
        gates[key] = gates_of(p, source)
    return checks, gates


def _expected(dest: Path, program: str, plan: dict) -> None:
    """expected/<program>/: its enumeration and its plan (the latest run's), as the suite compares them."""
    from enough.thym import enumerate as en
    exp = dest / "expected" / program
    items = en.enumerate_file(dest / "programs" / f"{program}.thym")
    if isinstance(items, Refusal):
        raise RuntimeError(f"{program}: {items}")
    if isinstance(items.get("built"), dict):         # the suite compares without `built`; pinned so a remake is equal
        items["built"]["at"] = "2026-11-18T12:00:00Z"
    _write(exp / "items.cosm", mc.dump(items))
    _write(exp / "plan.cosm", mc.dump(pl.normalise(plan)))


def make(dest: Path = DEST, scratch: Path | None = None) -> Path:
    """Write the fixture's made parts into `dest` (its README and tally.cases.json are kept as they are)."""
    import tempfile
    dest = Path(dest)
    for sub in ("programs", "expected", "replay", "inputs", "landed", "recorded"):
        if (dest / sub).exists():
            shutil.rmtree(dest / sub)
    with tempfile.TemporaryDirectory(prefix="tally-fixture-") as tmp:
        scratch = Path(scratch or tmp)
        for name, text in PROGRAMS.items():
            _write(dest / "programs" / f"{name}.thym", text)
        inputs = dest / "inputs"
        shutil.copytree(TALLY, inputs / "tally", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        shutil.copyfile(CASES, inputs / "tally.cases.json")
        kept = TALLY_FABULAC.read_text(encoding="utf-8").replace("flavour: fabulac\n",
                                                                  "flavour: fabulac\npurpose: transconception\n", 1)
        _write(inputs / KEPT, kept)
        for lang, _ in LANGUAGES:
            _write(inputs / f"{lang}.txt", lang)
        fmt: dict = {}
        plans: dict = {}
        entailed: dict = {}
        for step in PATH:
            if step[0] == "host":
                _, what, at = step
                if what == "sitting-1":
                    fmt["answers-1"] = _sitting(dest, ASKED, at)
                elif what == "sitting-2":
                    fmt["answers-2"] = _sitting(dest, ASKED_AGAIN, at)
                elif what == "spikes":
                    _spikes(dest, at)
                continue
            _, program, rid, now, ins, rules, gives = step
            plan = plan_of(dest, program, ins, fmt)
            out, t = _run(dest, scratch, program, rid, now, plan, rules)
            plans[program] = plan                      # the latest run's plan is the one expected/ holds
            for give, stage in gives.items():
                shutil.copyfile(_output(out, give), inputs / stage)
            if program == "entail-in-a-language":
                entailed[(dest / ins["language"][1]).read_text(encoding="utf-8")] = t
        for program, plan in plans.items():
            _expected(dest, program, plan)
        _land(dest, entailed)
        if not (dest / "outside").is_dir():
            shutil.copytree(OUTSIDE, dest / "outside")
        _roundtrip(dest)
        checks, gates = reports(dest)
        _write(dest / "recorded" / "checks.json", _json(checks))
        _write(dest / "recorded" / "gates.json", _json(gates))
    return dest


def _scratch_seams() -> None:
    """Hold every ENOUGH_* seam at its scratch value before anything is made, as the test suite does: run by hand,
    the maker must never reach the network (the language library's fetch, cosmoes.org) or a person's ~/enough, and
    the fixture must not record what one machine's environment happened to allow (0.8 build: a run outside the
    seams once recorded a live 404 from cosmoes.org/library)."""
    import os
    import tempfile
    from enough import seams
    scratch = Path(tempfile.mkdtemp(prefix="tally-fixture-seams-"))
    for name in seams.BEHAVIOUR_SEAMS:
        os.environ.pop(name, None)
    for name, value in seams.scratch_env(scratch, {}).items():
        if name.startswith("ENOUGH_"):
            os.environ[name] = value


if __name__ == "__main__":
    _scratch_seams()
    print(make(Path(sys.argv[1]) if len(sys.argv) > 1 else DEST))


