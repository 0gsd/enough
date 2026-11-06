"""The fabula, checked (`oes: fabula/1`, read also as its old spelling `oes: emf/1`; the manifest is
defaults/cosm/manifests/fabula.manifest.cosm, the prose MacroCOSM OES 18.4 and 18.6).

A fabula is one input decompiled: a text (a fabulan or a fabulap) or a folder of code (a fabulac). The reader,
`enough/macrocosm.py`, loads and checks it like any volume, and runs the two checks its manifest drives, `flavour` and
`flavour-kind`. This module runs the fabula's own checks beside the generic ones, the way `ascribe.lint_holograph`
runs Ascribe's, in one report (MacroCOSM OES 18.4.8):

- `code-span` (error): in a fabulac, every `span` is `{file, lines}`; its `file` is the path of a `C:file` of the
  fabulac; its `lines` are `n` or `n-m`, n no greater than m, within the file's `length.lines`.
- `licence-recorded` (error; a warning while pending): a fabulac records `source.licence`, a value or a question, and
  holds an `R:licence` item.
- `reading-whose` (warning): an author's or an expert's reading names the session it was given in; a critic's names
  the critic, or asks who.
- `interface-signature` (warning): a `function`, `method`, `class`, `command` or `format` interface carries its
  `signature`.
- `case-outcome` (error): a case says what is given and what is expected.

and the core's three checks of the dialectic (MacroCOSM OES 18.6.8), which run on every volume that holds an item of
module D, whatever its format:

- `question-about` (error): a question's `about` names an item, an item and a field path that parses, a span that fits
  the source, or a module or a kind the format declares. A question that has `settled` is skipped: its own answer may
  have removed what it was about.
- `question-shape` (error): a `choice` lists its `options`; an `answered`, `unknown` or `declined` question has an
  answer, and its last answer agrees with the state; an `open` question has no `settled`; a `stale` or `withdrawn`
  question carries `ended`.
- `session-declared` (warning): a source `D:session/<id>`, in provenance or in an answer, names a session of the
  volume. A bare `session-<n>` or `elicit-…` with no such item is accepted, with a note.

It reads only the volume it is given (never the input a span points at) and writes nothing. No server route, viewer or
tool calls it yet; `lint` is the entry point they will call.

    python -m enough.fabula lint <fabula or any volume> [--json]

Standalone like the reader: the standard library, PyYAML (through the reader) and `enough.macrocosm`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from . import macrocosm as mc

FORMAT = "fabula"
OES = "fabula/1"
OLD_OES = ("emf/1",)                         # read as a fabulan, never written
FLAVOURS = ("fabulan", "fabulap", "fabulac")

# The fabula's own checks, and the core's three of the dialectic, in the manifest's order (checks.own).
FABULA_CHECKS = ("code-span", "licence-recorded", "reading-whose", "interface-signature", "case-outcome")
DIALECTIC_CHECKS = mc.CORE_CHECKS            # question-about, question-shape, session-declared
OWN_CHECKS = ("code-span", "licence-recorded", "question-about", "question-shape", "session-declared",
              "reading-whose", "interface-signature", "case-outcome")
SEVERITY = {"code-span": "error", "licence-recorded": "error", "question-about": "error", "question-shape": "error",
            "session-declared": "warning", "reading-whose": "warning", "interface-signature": "warning",
            "case-outcome": "error"}
# An old contract name: `emf-checks` names `fabula-checks`, the fabula's checks passing with no error (18.1, 18.4.8).
CONTRACT_NAMES = ("fabula-checks", "emf-checks")

SIGNED_SURFACES = ("function", "method", "class", "command", "format")
QUESTION_STATES_ANSWERED = ("answered", "unknown", "declined")
_LINES_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")
_BARE_SESSION_RE = re.compile(r"^(?:session-[0-9]+|elicit-\S+)$")
_SESSION_PREFIX = f"{mc.DIALECTIC_MODULE}:session/"


def is_fabula(volume: mc.Volume) -> bool:
    """Whether a loaded volume is a fabula: its format is `fabula`, whether the file says `fabula/1` or `emf/1`."""
    return volume.manifest is not None and volume.minicosm == FORMAT


def flavour(volume: mc.Volume) -> str | None:
    """A fabula's flavour as the reader reads it: the catalog's `flavour`, else `fabulan` (every `emf/1` file);
    None when the volume is not a fabula."""
    if not is_fabula(volume):
        return None
    v = volume.manifest.flavour_of(volume.catalog)
    return v if isinstance(v, str) else None


def _lines(v: Any) -> tuple[int, int] | None:
    """`"12"` or `"12-40"` (or the integer 12) -> (12, 12) or (12, 40); None when it is not that shape or n > m."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return (v, v) if v >= 1 else None
    mt = _LINES_RE.match(str(v).strip()) if isinstance(v, str) else None
    if not mt:
        return None
    lo, hi = int(mt.group(1)), int(mt.group(2) or mt.group(1))
    return (lo, hi) if 1 <= lo <= hi else None


class _Own:
    """The fabula's own checks and the dialectic's over one loaded volume, adding to the generic report."""

    def __init__(self, vol: mc.Volume, rep: mc.Report):
        self.v, self.rep, self.m = vol, rep, vol.manifest
        override = self.m._block("checks").get("severity")
        override = override if isinstance(override, dict) else {}
        self.sev = dict(SEVERITY, **{str(k): str(v) for k, v in override.items() if str(k) in SEVERITY})
        self.items = list(vol.items.values())
        self.files = {it.data.get("path"): it for it in self.items
                      if it.module == "C" and it.kind == "file" and isinstance(it.data.get("path"), str)} \
            if is_fabula(vol) else {}

    def add(self, check: str, item: mc.Item | None, msg: str, fld: str | None = None, *,
            severity: str | None = None) -> None:
        self.rep.add(mc.Problem(check, severity or self.sev.get(check, "error"), item.key if item else "",
                                item.file if item else self.v.catalog_file, msg, fld))

    # ----------------------------------------------------------------- the fabula's own
    def fabula(self) -> None:
        fl = flavour(self.v)
        for it in self.items:
            if fl == "fabulac" and "span" in it.data:
                self.code_span(it, it.data["span"], "span")
            if it.module == "P" and it.kind == "reading":
                self.reading_whose(it)
            if it.module == "C" and it.kind == "interface":
                self.interface_signature(it)
            if it.module == "P" and it.kind == "case":
                self.case_outcome(it)
        if fl == "fabulac":
            self.licence_recorded()

    def _span_why(self, span: Any) -> str | None:
        """Why a code span does not fit the fabulac, or None when it does."""
        if not isinstance(span, dict) or set(span) - {"file", "lines"} or "file" not in span or "lines" not in span:
            return "a span in a fabulac is {file, lines}"
        f, lines = span["file"], _lines(span["lines"])
        if not isinstance(f, str) or f not in self.files:
            return f"{f} is not the path of a C:file of this fabulac"
        if lines is None:
            return f"lines {span['lines']!r} must be n or n-m, n no greater than m"
        length = self.files[f].data.get("length")
        n = length.get("lines") if isinstance(length, dict) else None
        if isinstance(n, int) and not isinstance(n, bool) and lines[1] > n:
            return f"lines {span['lines']} run past the end of {f} ({n} lines)"
        return None

    def code_span(self, it: mc.Item, span: Any, fld: str) -> None:
        if mc.is_pending(span):
            return
        why = self._span_why(span)
        if why:
            self.add("code-span", it, why, fld)

    def licence_recorded(self) -> None:
        src = self.v.catalog.get("source")
        lic = src.get("licence") if isinstance(src, dict) else None
        if lic is None:
            self.add("licence-recorded", None,
                     "a fabulac records its source's licence (source.licence), or asks for it", "source.licence")
        elif mc.is_pending(lic):
            self.add("licence-recorded", None, "the licence is still a question", "source.licence",
                     severity="warning")
        if not any(it.module == "R" and it.kind == "licence" for it in self.items):
            self.add("licence-recorded", None, "a fabulac holds an R:licence item: the terms the source may be used on")

    def reading_whose(self, it: mc.Item) -> None:
        w = it.data.get("whose")
        if not isinstance(w, dict) or mc.is_pending(w):
            return                                  # identity-min and closed-list have the shape
        by = w.get("by")
        if by in ("author", "expert") and not w.get("session"):
            self.add("reading-whose", it, f"the {by}'s reading names the session it was given in", "whose.session")
        elif by == "critic" and not w.get("name"):
            self.add("reading-whose", it, "a critic's reading names the critic, or asks who (name: {pending: …})",
                     "whose.name")

    def interface_signature(self, it: mc.Item) -> None:
        surface = it.data.get("surface")
        sig = it.data.get("signature")
        if surface in SIGNED_SURFACES and not (isinstance(sig, str) and sig.strip()):
            self.add("interface-signature", it, f"{mc._a(str(surface))} carries its exact signature", "signature")

    def case_outcome(self, it: mc.Item) -> None:
        missing = [k for k in ("given", "expect") if not it.data.get(k)]
        if missing:
            self.add("case-outcome", it, "a case says what is given and what is expected: no "
                                         + " and no ".join(missing), missing[0])

    # ----------------------------------------------------------------- the dialectic's (the core's)
    def dialectic(self) -> None:
        for it in self.items:
            if it.module != mc.DIALECTIC_MODULE:
                continue
            if it.kind == "question":
                self.question_about(it)
                self.question_shape(it)
        self.session_declared()

    def _about_why(self, it: mc.Item, about: Any) -> str | None:
        m, g = self.m, self.m.grammar
        if isinstance(about, dict):
            if mc.is_pending(about):
                return "about is an open question: a question names what it is about"
            if "file" in about:
                if not self.files:
                    return "a span {file, lines} is about code, and this volume holds no C:file"
                return self._span_why(about)
            if set(about) == {"lines"}:
                return None if _lines(about["lines"]) else f"lines {about['lines']!r} must be n or n-m"
            if set(about) == {"start", "end"}:
                ok = all(isinstance(about[k], str) and 0 < len(about[k].strip()) <= 60 for k in ("start", "end"))
                return None if ok else ("a span {start, end} is two short runs of the source's words (60 characters "
                                        "at most)")
            return "a span is {lines}, {start, end}, or {file, lines} in code"
        if not isinstance(about, str) or not about.strip():
            return "about names an item, an item's field, a span of the source, or a module or kind"
        if about in m.modules():
            return None                             # a bank question asked of the volume: the module
        mt = re.fullmatch(r"([A-Z][A-Za-z0-9]*):([a-z][a-z0-9-]*)", about)
        if mt:                                      # ... or of a kind, with no item yet
            return None if mt.group(1) in m.modules() and mt.group(2) in m.kinds(mt.group(1)) else \
                f"{about} is not a kind this format declares"
        base, sep, fpath = about.partition("#")
        if sep and not g.seg["field"].fullmatch(fpath):
            return f"{fpath!r} is not a field path (keys joined by \".\", list positions as [n])"
        if mc.resolve_ref(self.v, it, base) is None:
            return f"{about} names nothing in this volume"
        return None

    def question_about(self, it: mc.Item) -> None:
        if it.data.get("settled"):
            return                                  # its own answer may have removed what it was about (18.6.3)
        if "about" not in it.data:
            return                                  # identity-min has it
        why = self._about_why(it, it.data["about"])
        if why:
            self.add("question-about", it, why, "about")

    def question_shape(self, it: mc.Item) -> None:
        d = it.data
        state, answers = d.get("state"), d.get("answers")
        if d.get("kind") == "choice" and not (isinstance(d.get("options"), list) and d["options"]):
            self.add("question-shape", it, "a choice question lists its options", "options")
        if answers is not None and not (isinstance(answers, list) and all(isinstance(a, dict) for a in answers)):
            self.add("question-shape", it, "answers is a list of {at, by, says, value, confidence, session}", "answers")
            return
        answers = answers or []
        if state in QUESTION_STATES_ANSWERED:
            if not answers:
                self.add("question-shape", it, f"a question {state} has an answer to show for it", "answers")
            else:
                last, fld = answers[-1], f"answers[{len(answers) - 1}]"
                declined = last.get("declined") is True
                if state == "answered" and (declined or last.get("value") is None):
                    self.add("question-shape", it, "an answered question's last answer gives a value", fld)
                elif state == "unknown" and (declined or "value" not in last or last.get("value") is not None):
                    self.add("question-shape", it, "an unknown question's last answer is value: null, the person's "
                                                   "\"I don't know\"", fld)
                elif state == "declined" and not declined:
                    self.add("question-shape", it, "a declined question's last answer says declined: true", fld)
        if state == "open" and d.get("settled"):
            self.add("question-shape", it, "an open question has nothing settled: settled is written only when an "
                                           "answer is folded in", "settled")
        if state in ("stale", "withdrawn") and not isinstance(d.get("ended"), dict):
            self.add("question-shape", it, f"a {state} question says when, by whom and why it ended (ended: "
                                           "{at, by, because})", "ended")

    def session_declared(self) -> None:
        for it in self.items:
            prov = it.data.get("provenance")
            srcs = prov.get("sources") if isinstance(prov, dict) else None
            for i, s in enumerate(srcs if isinstance(srcs, list) else []):
                self._session(it, s, f"provenance.sources[{i}]")
            if it.module == mc.DIALECTIC_MODULE and it.kind == "question":
                answers = it.data.get("answers")
                for i, a in enumerate(answers if isinstance(answers, list) else []):
                    if isinstance(a, dict) and isinstance(a.get("session"), str):
                        self._session(it, a["session"], f"answers[{i}].session")

    def _session(self, it: mc.Item, s: Any, fld: str) -> None:
        if not isinstance(s, str):
            return
        if s.startswith(_SESSION_PREFIX):
            if mc.resolve_ref(self.v, it, s) is None:
                self.add("session-declared", it, f"{s} is not a session of this volume", fld)
        elif _BARE_SESSION_RE.match(s) and mc.resolve_ref(self.v, it, _SESSION_PREFIX + s) is None:
            self.add("session-declared", it, f"{s} names {_SESSION_PREFIX}{s}, which this volume does not hold "
                                             "(a bare session id is accepted)", fld, severity="note")


def own_checks(volume: mc.Volume) -> list[mc.Problem]:
    """The fabula's own checks and the dialectic's, alone, as problems (nothing for a refused volume)."""
    rep = mc.Report(volume)
    if volume.manifest is not None:
        own = _Own(volume, rep)
        if is_fabula(volume):
            own.fabula()
        own.dialectic()
    return rep.problems()


def lint(path, *, registry: mc.Registry | None = None) -> mc.Report:
    """The generic checks (`macrocosm.lint`) and the ones this module runs, in one report, for a volume (a path or a
    volume already loaded). A fabula gets its own eight; any other volume that holds an item of module D gets the
    dialectic's three; every other volume gets the generic report alone. The checks run are added to `checks` and
    taken off `not_run`."""
    vol = path if isinstance(path, mc.Volume) else mc.load_volume(path, registry)
    rep = mc.lint(vol)
    if vol.manifest is None:
        return rep
    ran: list[str] = []
    own = _Own(vol, rep)
    if is_fabula(vol):
        own.fabula()
        ran += list(OWN_CHECKS)
    if is_fabula(vol) or any(it.module == mc.DIALECTIC_MODULE for it in vol.items.values()):
        own.dialectic()
        ran += [c for c in DIALECTIC_CHECKS if c not in ran]
    rep.checks = rep.checks + [c for c in ran if c not in rep.checks]
    rep.not_run = [c for c in rep.not_run if c not in ran]
    return rep


lint_fabula = lint                           # the manifest's name for it (checks.own)


# ---------------------------------------------------------------------------
# CLI: python -m enough.fabula lint <path>
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m enough.fabula",
                                 description="The fabula: check a fabula (oes: fabula/1, or emf/1), or the dialectic "
                                             "of any volume.")
    ap.add_argument("command", choices=["lint"])
    ap.add_argument("path", help="a fabula, or any volume's catalog or folder")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args(argv)
    rep = lint(Path(args.path))
    vol = rep.volume
    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        for p in rep.problems():
            print(f"{p.severity:7} {p}")
        how = f" ({vol.declaration.how}: {vol.declaration.said})" if vol.declaration and vol.declaration.how == "old" \
            else ""
        fl = f", {flavour(vol)}" if is_fabula(vol) else ""
        print(f"{vol.oes or 'refused'}{fl}{how}: {len(vol.items)} items, {len(rep.errors)} errors, "
              f"{len(rep.warnings)} warnings, {len(rep.notes)} notes, {len(rep.pending)} open questions"
              + (f"; not run: {', '.join(rep.not_run)}" if rep.not_run else ""))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
