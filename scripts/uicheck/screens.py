"""The screen registry — **the extension point of the whole harness.**

Every named state the UI can be in gets one entry here: how to get into it
(`setup`) and how to get back out (`teardown`). The layout probes then run
against each entry at every viewport in every language, which is the only
reason a clipping bug in Japanese at 1024px ever gets found before a user
finds it.

**If you change the UI, you change this file in the same commit.** A new
modal, a new mode, a new panel — it needs a `Screen` here, or the suite is
quietly checking a UI that no longer exists. That rule is written down in
docs/AGENT_GUIDE.md ("Pre-commit suite") because it is the one thing that
makes the harness stay useful instead of decaying into a green light nobody
trusts.

Steps are deliberately tiny and declarative — `click`, `key`, `eval`,
`wait_for`, `wait_gone`, `wait_idle`, `sleep_frames` — so a screen reads as
a recipe rather than as code, and so a screen that breaks names the step it
broke on. Anything a step cannot express goes in an `eval`, which calls the
page's own entry points (`openUIModal()`, `enterGirraphMode(path)`) rather
than poking at the DOM: driving the real functions is what makes this a test
of the product and not of the harness's idea of the product.

Two things are deliberately NOT covered, and both are environmental rather
than optional:

* anything that needs model output — there is no llama-server in the scratch
  environment, by design (see `smoke_boot.build_env()`), so the harness
  tests chrome, never replies;
* wikisink's reader — the scratch environment has no Wikipedia archive, so
  only the setup/empty state is reachable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# The fixture file names seeded by server.seed_project().
DOC = "notes.md"
GIRRAPH = "map.girraph"
MERIRMAID = "diagram.merirmaid"
LONG_NAME = ("a-file-with-a-deliberately-very-long-name-that-the-sidebar-"
             "has-to-decide-how-to-truncate.md")
# The Canon round's fixtures (0.4.3), seeded by server.seed_project() and
# server.seed_canon(): a text's EMF twin, a Comprise Holotype in the project,
# and a volume in the scratch Canon store.
EMF_TWIN = "orchard/notes.md.cosm"
HOLOTYPE = "meadow"
CANON_VOLUME = "field-notes"
# Checkpoint B: the text that twin belongs to, a sentence of it, and a text
# with no twin of its own (the pin scenario writes its minimal twin).
EMF_TEXT = "orchard/notes.md"
EMF_PASSAGE = "Every apple tree needs a second variety nearby to set fruit."
LEDGER = "orchard/ledger.md"
# SHORT: a second text with a twin, which the compile-short scenario writes beside.
PRESS = "orchard/press.md"
# Thym (0.5.0), seeded by server._seed_thym() beside the orchard notes: a
# program with its enumeration, a plan, checkpoint A's real trace, the package
# it landed (both forms), a hand-made reading, and a program that asks no
# model, with a text of its own for it to run on.
THYM_PROGRAM = "orchard/publish-story.thym"
THYM_PLAN = "orchard/publish-story.plan.cosm"
THYM_TRACE = "orchard/2026-11-01-2148-35b5.trace.cosm"
THYM_PACKAGE = "orchard/notes.thym"
THYM_READING = "orchard/notes.read-null-2026-11-01-1200.md"
THYM_READING_FOOTER = ("*a reading of notes.md through null, made here on 2026-11-01 by a model; "
                       "the text stands unchanged*")
THYM_RULES_PROGRAM = "orchard/count-words.thym"
HARVEST = "orchard/harvest.md"
# The package and unpack cards (U2): the morph beside the notes, and a sealed
# copy of the package alone in a folder of its own (server._seed_sealed; its
# key is server.THYM_SEALED_KEY, in the harness's memory only).
THYM_MORPH = "orchard/notes.morph.cosm"
THYM_SEALED = "orchard/received/notes.thym.enc"
#: What the key screen paints in place of a real key: it seals nothing.
THYM_PLACEHOLDER_KEY = "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF"
# Writing and running Thym (0.6, U1c): seeded by server._seed_thym().
THYM_BROKEN = "orchard/broken.thym"              # refused at line 9: an unknown move
THYM_BROKEN_LINE = 9
THYM_TWO = "orchard/two-outs.thym"               # thym 1: a folder and a short in, two outputs, no model
THYM_REPO = "orchard/little-repo/"
THYM_LONG = "orchard/long-lines.md"              # a short with a line `tighten` (shipped, asks a model) would reword
THYM_TRIES = "orchard/2026-11-05-1956-ae6e.trace.cosm"
# The fabula round (0.6, U1a), seeded by server._seed_fabula() in works/: a
# Python tool with its finished fabulac, the cshort and the catem it compiled
# into, a folder of Python with no fabulac yet, a poem with no twin and a
# letter whose old-named twin sits beside its new one.
FAB_TOOL = "works/tally"
FAB_FABULAC = "works/tally.fabulac.cosm"
FAB_CSHORT = "works/tally.cshort-2026-11-05-1412/"
FAB_CATEM = "works/tally.catem-2026-11-05-1415.md"
FAB_TINY = "works/tiny-tool"
FAB_POEM = "works/rain.md"
FAB_LETTER = "works/letter.md"
# The dialectic (0.6, U1b), seeded by server._seed_dialectic() in talks/: the
# morning-close guide's fabulan with one open question of every kind, the same
# with a sitting written and not settled, the same with no questions at all,
# the sample holograph with its bank raised and two candidates landed (and the
# holder's program beside it), the holograph whose checks warn with advice, and
# one copy per language of the fabulan and of the holograph for the scenarios.
DLG_KINDS = "talks/kinds/close.md.fabulan.cosm"
DLG_SITTING = "talks/sitting/close.md.fabulan.cosm"
DLG_BARE = "talks/bare/close.md.fabulan.cosm"
DLG_SELF = "talks/self"
DLG_SELF_PII = "talks/self-pii"
DLG_ANSWER = "talks/answer-{lang}/close.md.fabulan.cosm"
DLG_SELF_ASK = "talks/self-ask-{lang}"

Step = tuple[str, str]


@dataclass(frozen=True)
class Screen:
    name: str
    mode: str                       # "project" | "home"
    setup: tuple[Step, ...] = ()
    teardown: tuple[Step, ...] = ()
    #: Screens that only make sense once, e.g. the ui-scale variants.
    base_only: bool = False
    note: str = ""


def _esc() -> Step:
    return ("key", "Escape")


# Teardown does not assert. A screen's teardown gets the UI back to the
# ground floor and nothing more; `Driver.reset_page()` then forces whatever
# is left. Anything that *should* happen on the way out — esc closing the
# modal it is pressed in, the dirty guard appearing — is a claim about
# behaviour, and claims belong in interactions.py, where a failure is
# reported as a finding instead of costing every screen an eight-second
# `wait_gone` timeout.
#
# Close every stacked mode through its own indicator ribbon.
#
# NOT `modeRemove(name)`. `modeRemove` is the stack manager's bookkeeping —
# it splices the entry and re-renders the indicators, and that is all. The
# mode's own `onExit` is what stops its render loop, and girraph, merirmaid
# and canon all run one. Tearing a mode down the manager's way instead of
# the user's way leaves an animation frame loop spinning behind a hidden
# element, and after a dozen screens the renderer is saturated and stops
# answering. (That is not a hypothesis: it is what the first version of this
# file did, and the symptom was a tab that went silent halfway through the
# matrix.) The ribbon click is exactly what a user clicking the red x does.
EXIT_ALL_MODES: tuple[Step, ...] = (
    ("eval", "Array.from(document.querySelectorAll("
             "'#mode-stack .mode-indicator .mode-ribbon'))"
             ".reverse().map((b) => b.click())"),
    ("wait_idle", ""),
)

# Opening a composure is ONE step, and it does its own waiting.
#
# Three things conspired against the obvious recipe (`eval compOpenNew(f)`
# then `wait_for` a selector). `compOpenNew` is async, so the wait ran
# against the document that was about to be replaced. A blank composure
# already HAS a module, so `.comp-module` proved nothing — each form is
# identified by a swatch only it uses (`cards` has yellow cards, `scaffold`
# the lilac premise card, a journal page a date header). And the page the
# matrix drives is never reloaded between screens, so it can get busy
# enough that a `wait_for`'s 8-second ceiling expires on a document that
# was in fact already there. Doing both halves inside one awaited
# expression removes all three.
CARDS_READY: Step = ("wait_for", "#comp-modules .comp-module.comp-bg-yellow")
SCAFFOLD_READY: Step = ("wait_for", "#comp-modules .comp-module.comp-bg-lilac")
JOURNAL_READY: Step = ("wait_for", ".comp-journal-head")
#: A council in `setup` has drawn its checklist; that is the last thing the
#: card waits on (GET /api/council/participants). The wait is done INSIDE the
#: page for the reason `_open` gives: a `wait_for`'s 8-second ceiling expires
#: on a busy tab even when the thing it wants is already there.
COUNCIL_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200
       && !document.querySelector('#cc-participants .cc-person'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")

#: The sidebar's collapse/expand transition (180ms) has finished.
SIDEBAR_SETTLED: Step = ("eval_await", "new Promise((r) => setTimeout(() => r(true), 260))")

#: The dictionary has drawn a page. FEED builds its database in the
#: background at boot (a few seconds on the real data), so the wait is long
#: and done inside the page, for the reason COUNCIL_READY gives.
DICT_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 360
       && !document.querySelector('#dict-flow .dict-e'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The WDL has a plate (not the "looking it up" line).
WDL_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200
       && !document.querySelector('#wdl-scroll .wdl-mast'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The cosm viewer has drawn its volume (cards, a refusal or an error) —
#: GET /api/cosm then the render, waited for inside the page.
COSM_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector(
       '#cosm-body .cosm-card, #cosm-body .cosm-refusal, #cosm-body .cosm-error'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The docs viewer (0.4.4) has drawn its document — the short density's
#: sections, the atem density's outline or the fabula's prism cards (or an
#: error, which the `_OK` variants below refuse to call ready). GET /api/docs
#: builds the doc volume on its first call (about a second, cold), so the
#: wait is long and in-page.
DOCS_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 300 && !document.querySelector(
       '#docs-body .docs-sec h2[id], #docs-body .docs-outline, #docs-body .cosm-card.docs-prism,'
       + ' #docs-body .ref-error'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: …and it is the short density's sections, not an error: a step that fails
#: (a harness error) when the document could not be loaded — how the home
#: screens prove the route is home-accessible.
DOCS_SHORT_OK: Step = ("wait_for", "#docs-body .docs-sec h2[id]")
DOCS_ATEM_OK: Step = ("wait_for", "#docs-body .docs-outline .docs-ol-row")
#: The fabula density (U2) has drawn its prism cards and the rail beside them.
DOCS_FAB_OK: Step = ("wait_for", "#docs-body .cosm-card.docs-prism")
#: …and a live example's block has loaded and linted (POST /api/cosm/inline),
#: its verdict line painted — waited for inside the page.
DOCS_LIVE_OK: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector('#docs-body .docs-live[data-ready]'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return !!document.querySelector('#docs-body .docs-live[data-ready="ok"]'); })()""")
#: merirmaid has drawn a diagram's nodes (a lens: GET /api/docs/lens, then Pele).
MM_NODES_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 300 && !document.querySelector('#merirmaid-body g.pele-node'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")


#: A program in the docs viewer (0.5.0) has drawn its density — cards, the
#: source, the outline — or said what is missing.
THYM_DOC_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector('#docs-body .cosm-card, #docs-body .thym-src,'
       + ' #docs-body .docs-outline, #docs-body .ref-error, #docs-body .docs-busy'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The run card has its programs (or the "not available yet" line), and a
#: program chosen shows its plan, a refusal, or the same line.
THYM_PICK_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector('#thym-plan .thym-atem-line, #thym-plan .thym-unavail,'
       + ' #thym-plan .thym-refusal, #thym-list .thym-unavail'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: A reading's band is up in the full reader with its footer line read.
THYM_BAND_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(document.querySelector('#read-band-review:not([hidden])')
       && document.querySelector('#read-band-review .read-band-line').textContent); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")


#: The package card has looked for a morph beside its text (the parts drawn).
THYM_PACK_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(THYM_PACK.open && THYM_PACK.morph !== undefined); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The unpack card knows what the package carries (a sealed one: that it cannot).
THYM_UNPACK_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(THYM_PACK.open && THYM_PACK.parts !== null); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: Closes the package card even with a key showing (only "I have it" does, by hand).
THYM_PACK_CLOSE: Step = ("eval", "(() => { try { thymPackClose(true); } catch (e) {} return true; })()")


def thym_moves_stub_js() -> str:
    """JS that hands the page `GET /api/thym/moves`' answer when the server has no such route yet (U1c asked for
    it): the same shape, built by the harness from the declarations a compile reads (server.thym_moves_payload).
    When the route answers, nothing is stubbed and the page reads the server."""
    from . import server as _server
    payload = json.dumps({str(v): _server.thym_moves_payload(v) for v in (0, 1)})
    return ("(async () => { try { const r = await fetch('/api/thym/moves?version=1'); if (r.ok) return true; } catch (e) {}"
            " if (window.__thymMovesStub) return true; const data = " + payload + ";"
            " const real = window.fetch; window.__thymMovesStub = true;"
            " window.fetch = (u, o) => { const m = /^\\/api\\/thym\\/moves\\?version=(\\d)/.exec(String(u));"
            " if (m && data[m[1]]) return Promise.resolve(new Response(JSON.stringify(data[m[1]]),"
            " {status: 200, headers: {'Content-Type': 'application/json'}})); return real(u, o); };"
            " return true; })()")


def _thym_edit(path: str, size: str = "full") -> Step:
    """A program open in the editor, its check strip drawn (clean or refused)."""
    root = "#thym-ed" if size == "full" else "#thym-ed-mini"
    return ("eval_await", "(async () => { await openReadEdit(%s, {size: %s, face: 'edit'});"
                          " for (let i = 0; i < 200 && !document.querySelector(%s); i++)"
                          " await new Promise((r) => setTimeout(r, 50)); return true; })()"
            % (json.dumps(path), json.dumps(size), json.dumps(root + ".refused, " + root + ".clean")))


#: The editor's text back as it is on disk, so a teardown never meets the dirty guard.
THYM_EDIT_CLEAN: Step = ("eval", "(() => { try { const ta = reEditTextarea(); if (ta) { ta.value = RE_PRISTINE;"
                                 " RE_EDIT_BUFFER = RE_PRISTINE; } } catch (e) {} return true; })()")
#: The run card's plan has drawn (its steps, or a refusal at its statement).
THYM_PLAN_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector('#thym-plan ol.thym-plan-read, #thym-plan .thym-refusal,'
       + ' #thym-plan .thym-unavail'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")


def _thym_run_on(program: str, inputs: dict[str, str] | None = None, text: str | None = None) -> Step:
    """"run with…" opened from a program, its inputs given (as the dialectic card gives them), planned."""
    return ("eval_await", "(async () => { await thymRunOpen({program: %s, inputs: %s, input: %s});"
                          " return true; })()" % (json.dumps(program), json.dumps(inputs), json.dumps(text)))


THYM_REF_CLOSE: Step = ("eval", "(() => { try { thymRefClose(); } catch (e) {} return true; })()")
THYM_PICK_CLOSE: Step = ("eval", "(() => { try { thymPickClose(); } catch (e) {} return true; })()")


def _thym_pick(text: str, program: str) -> Step:
    """Open "run with…" on `text` and choose `program` as a person would (a
    click on its radio, which plans it); the route-less build shows its line."""
    return ("eval_await", "(async () => { await thymRunOpen({input: %s});"
                          " for (let i = 0; i < 200 && !document.querySelector('#thym-list input, #thym-list .thym-unavail'); i++)"
                          " await new Promise((r) => setTimeout(r, 50));"
                          " const r = document.querySelector('#thym-list input[value=' + JSON.stringify(%s) + ']');"
                          " if (r) r.click(); return true; })()" % (json.dumps(text), json.dumps(program)))


def _docs(doc: str, density: str = "short", lang: str | None = None,
          anchor: str | None = None) -> Step:
    """Open the docs viewer on `doc` at `density` — always named: the
    viewer remembers a density per document in localStorage, which outlives
    the reloads between screens. `anchor`: an item key or a section number."""
    opts = {"doc": doc, "density": density}
    if lang:
        opts["lang"] = lang
    if anchor:
        opts["anchor"] = anchor
    return ("eval", f"enterDocsMode({json.dumps(opts)})")
#: The fabula card (0.6) has read what it shows: a text's twins, or a folder's build and what it made.
FAB_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(FAB.open && (FAB.face === 'text' ? !!FAB.flavour
       : (FAB.build !== null && (FAB.build.error || !FAB.build.exists || FAB.compiled !== null)))); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
FAB_CLOSE: Step = ("eval", "(() => { try { fabCardClose(); } catch (e) {} return true; })()")
#: The cshort / catem viewer has its file (a cshort: its first file's text too).
FABV_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(FABV.open && (FABV.error || (FABV.data && (FABV.kind === 'catem'
       || FABV.text !== null || FABV.ferror)))); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
FABV_CLOSE: Step = ("eval", "(() => { try { fabViewClose(); } catch (e) {} return true; })()")
#: The dialectic card (0.6, U1b) has read its volume (the questions and the viewer's
#: read of it), or, on its isograph face, the holder's programs.
DLG_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(DLG.open && (DLG.face === 'iso' ? (DLG.iso.programs !== null || DLG.iso.error)
       : ((DLG.data && DLG.cosm !== null) || DLG.error))); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  await new Promise((r) => setTimeout(r, 120));
  return true; })()""")
DLG_CLOSE: Step = ("eval", "(() => { try { dlgClose(); DLG.drafts.clear(); DLG.putNext = []; } catch (e) {} return true; })()")


def _dlg_put(*keys: str) -> Step:
    """Put these questions in hand (as a settle or a refusal would), and repaint."""
    return ("eval", f"(() => {{ DLG.putNext = {json.dumps(list(keys))}; DLG.mainKey = null; dlgPaint(); return true; }})()")
#: The Canon chip knows the text's twin state (GET /api/fabula/twin answered).
CANON_CHIP_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !(CANON.doc && CANON.doc.state); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The EMF face has drawn the twin's cards.
EMF_FACE_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector(
       '#review-emf:not([hidden]) .cosm-card, #preview-emf:not([hidden]) .cosm-card'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
#: The atem card has its answer (rules mode: a scaffold) or an error.
ATEM_READY: Step = ("eval_await", """(async () => {
  for (let i = 0; i < 200 && !document.querySelector(
       '#atem-modal:not(.hidden) .cosm-atem-line, #atem-modal:not(.hidden) .atem-error'); i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return true; })()""")
ATEM_CLOSE: Step = ("eval", "(() => { try { atemCardClose(); } catch (e) {} return true; })()")


def _atem_of_passage(size: str) -> Step:
    """Open the EMF text at `size` and ask for the atem of one of its
    sentences, as the right-click menu does (path included, so the card can
    pin). The harness has no model: the card shows the labelled scaffold.
    The mini panel slides open over 180ms, and the card's modal makes the
    page stop moving in a way `wait_idle` reads as settled: wait out the
    slide first, or the header is measured half-open."""
    return ("eval_await", "(async () => { await openReadEdit(%s, {size: %s, face: 'read'});"
                          " await new Promise((r) => setTimeout(r, 260));"
                          " await canonAtemSelection({text: %s}, {path: %s, where: 'notes.md'});"
                          " return true; })()" % (json.dumps(EMF_TEXT), json.dumps(size),
                                                  json.dumps(EMF_PASSAGE), json.dumps(EMF_TEXT)))


#: Back to a known order, so a screen never inherits a sort or a search the
#: previous one (or a persisted visit) left behind.
DICT_PLAIN = ("eval", "(() => { try { localStorage.removeItem('enough.dict.v1'); } catch (e) {}"
                      " Object.assign(DICT.view, {sort: 'alpha', dir: 'asc', then: '',"
                      " thenDir: 'asc', q: ''}); DICT.view.filters = {domain: '', pos: '',"
                      " band: '', origin: ''}; DICT.sel = null; DICT.start = null;"
                      " document.getElementById('dict-q').value = ''; return true; })()")

#: A CONVENED council, without a model. `POST /api/council/setup` only writes
#: the meta — it runs no turn — so the footer's whole state machine can be
#: driven here exactly as it is in the app, on a real file at a fixed path
#: (so the matrix leaves one `.comp` behind however often it runs). `convene`
#: is deliberately not called: `ready` is runnable, and the controls' enabled
#: matrix is the same.
COUNCIL_PATH = "rness/io/composure/suite-council.comp"
COUNCIL_SETUP: Step = ("eval_await", f"""(async () => {{
  await fetch('/api/council/setup', {{method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{path: {COUNCIL_PATH!r},
      title: 'The decision',
      input: 'Should chapter four move to the front?',
      parameters: 'Two rounds, then decide.',
      constraints: 'Do not rewrite the prose.',
      output: {{kind: 'answer'}}, max_rounds: 3}})}});
  await compOpenPath({COUNCIL_PATH!r});
  // Wait for the LIVE STATE, not just the footer: compAdoptDoc renders the
  // footer from the model's own meta a beat before /api/council/state
  // answers, and a screen that measured in between would catch the controls
  // mid-decision.
  for (let i = 0; i < 200 && !(COMP_COUNCIL.state
       && COMP_COUNCIL.state.council); i++) {{
    await new Promise((r) => setTimeout(r, 50));
  }}
  return true; }})()""")

#: …and the same council shown as concluded. The status is flipped in the
#: MODEL only, the way `composure-journal-filed` fakes a filed page: a real
#: conclude wants a model, and this screen is about the collapsed footer —
#: which since P9 carries the reconvene control as well as the two paths.
COUNCIL_CONCLUDE: Step = ("eval", """(() => {
  const meta = (COMP_COUNCIL.state && COMP_COUNCIL.state.council)
    || (COMP.model && COMP.model.council);
  if (!meta) return false;
  meta.status = 'concluded';
  meta.round = meta.max_rounds;
  meta.transcript = 'rness/knowledge/councils/2026-09-17-the-decision.md';
  compCouncilRender();
  return true; })()""")

#: A council set up for a `composure` output: the form select is revealed
#: and the path field is not, and every non-user row carries its charge.
COUNCIL_COMPOSURE: Step = ("eval_await", f"""(async () => {{
  await fetch('/api/council/setup', {{method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{path: {COUNCIL_PATH!r},
      title: 'The decision',
      input: 'Should chapter four move to the front?',
      output: {{kind: 'composure', form: 'scaffold'}}, max_rounds: 3}})}});
  await compOpenPath({COUNCIL_PATH!r});
  for (let i = 0; i < 200 && !(COMP_COUNCIL.state
       && COMP_COUNCIL.state.council); i++) {{
    await new Promise((r) => setTimeout(r, 50));
  }}
  COMP_COUNCIL.showSetup = true;
  await compCouncilSeedSetup();
  for (const p of (COMP_COUNCIL.people || [])) {{
    if (p.kind !== 'user') p.charge = 'argues the reader\\u2019s side';
  }}
  compCouncilRenderPeople();
  compCouncilRender();
  return true; }})()""")

#: A pal's statement, built in the MODEL only — the same treatment
#: `composure-journal-filed` gives a filed page, and for the same reason:
#: a real one wants two model calls and a cloud key. What is measured is
#: what `compPaintModule` makes of a `speaker_kind="pal"` module: the gray
#: tint, and the outgoing prompt collapsed behind its disclosure.
#:
#: It re-dresses the BRIEF module rather than adding a second one below it.
#: A second module down the column is below the fold at 1024x640 — which is
#: what a council canvas is for, you pan to it — but a screen that has to
#: pan first is a screen whose measurements depend on where a 240ms ease
#: happened to land. `composure-council-footer` already measures this exact
#: box cleanly at every viewport in every language; this changes what is
#: painted inside it and nothing about where it is.
COUNCIL_PAL_STATEMENT: Step = ("eval", """(() => {
  const m = ((COMP.model && COMP.model.modules) || [])[0];
  if (!m) return false;
  m.bg = 'gray';
  m.known_bg = true;
  m.locked = true;
  m.title = 'pal \\u00b7 anthropic/claude-sonnet-4.5 \\u00b7 turn 4';
  m.speaker = 'pal \\u00b7 anthropic/claude-sonnet-4.5';
  m.speaker_kind = 'pal';
  m.turn = '4';
  m.pages[0].locked = true;
  m.pages[0].rich =
    '<blockquote><p><strong>\\u2192 pal</strong> \\u2014 the prompt this '
    + 'council sent:</p><p>Does moving a reveal earlier cost tension in a '
    + 'book whose second half depends on it?</p></blockquote>'
    + '<p>Usually yes, unless the reveal is a setup rather than a payoff '
    + '\\u2014 in which case moving it forward buys the second half its '
    + 'room.</p>';
  compRefreshModule(m.id);
  // …and leave 120 world units of headroom above it. The composure
  // toolbar FLOATS over the top of the stage, so anything in the first
  // line of the topmost card is under it — true of a pager and a module
  // pin too, and the reason the brief (which has no controls) never
  // reported it. In a real council a pal statement is never the topmost
  // card; the view is where that difference lives, so the fixture puts it
  // where the product's own follow would. `compApplyView(false)` is
  // deliberate: eased is a 240ms CSS transition, and a screen must not
  // measure mid-ease. `kind: page` derives x from the sheet, so only y is
  // ours to set.
  COMP.origin.y = m.y - 120;
  compApplyView(false);
  return true; })()""")


#: ---------------------------------------------------------------------
#: `/pal` (P8)
#:
#: The hint row is revealed by `/` as the first character of the composer
#: and painted from `GET /api/pal/status`. In the scratch world that route
#: answers honestly — `local_models_only` is on and there is no OpenRouter
#: key — so the GATE-CLOSED row is the real thing, reason and all.
#:
#: The gate-OPEN row cannot be reached honestly: opening it needs a key in
#: the OS keyring, which is the developer's, not the harness's. So that
#: one screen seeds `PAL.status` — the page's own cache of the route's
#: answer — and calls the page's own `palSyncHint`. What is measured is
#: the row the product paints from a status body; what is faked is only
#: where the body came from.
PAL_HINT: Step = ("eval_await", """(async () => {
  const ta = document.getElementById('message');
  ta.focus();
  ta.value = '/';
  ta.dispatchEvent(new Event('input', {bubbles: true}));
  for (let i = 0; i < 100 && !PAL.status; i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  palSyncHint('pal-hint', ta.value);
  return true; })()""")

PAL_HINT_OPEN: Step = ("eval_await", """(async () => {
  const ta = document.getElementById('message');
  PAL.status = {available: true, reason: null,
                model_id: 'anthropic/claude-sonnet-4.5'};
  ta.focus();
  ta.value = '/';
  ta.dispatchEvent(new Event('input', {bubbles: true}));
  palSyncHint('pal-hint', ta.value);
  return true; })()""")

PAL_HINT_BACK: tuple[Step, ...] = (
    ("eval", """(() => {
  PAL.status = null;
  const ta = document.getElementById('message');
  if (ta) { ta.value = ''; ta.blur(); }
  palSyncHint('pal-hint', '');
  return true; })()"""),
    ("wait_idle", ""))

#: The two bubbles, through the page's own `pal_exchange` handler. There
#: is no model in the scratch world and there never will be, so the event
#: is synthetic — but the renderer, the order and the markup are the
#: product's, and the markup is the one the SERVER also emits when the
#: same exchange is rebuilt from history on reload.
PAL_BUBBLES: Step = ("eval", """(() => {
  palOnExchange({
    model_id: 'anthropic/claude-sonnet-4.5',
    prompt: 'Which obligations under the EU AI Act took effect in August '
      + '2026, and which were postponed?',
    reply: 'Two of the high-risk obligations moved to 2027; the '
      + 'transparency duties took effect on schedule.'});
  return true; })()""")

#: The context notice (the 16 GB context fix, 0.4.3). There is no model in
#: the scratch world, so no preflight can ever say "does not fit" — the
#: `/api/llm-status` body is stubbed IN THE PAGE (the harness wraps
#: `window.fetch` for that one path) and the product's own poll function,
#: `refreshLlmStatus()`, paints the notice. Everything drawn is the
#: product's: `ctxNoticePaint()` into whatever `#empty-hint` is showing.
#: A screen run on its own after one that removed the empty state gets it
#: back the way a user would, through `/reset`.
def _ctx_notice(status: dict) -> Step:
    body = json.dumps(status)
    return ("eval_await", f"""(async () => {{
  if (!window.__uicheckFetch) window.__uicheckFetch = window.fetch;
  const real = window.__uicheckFetch;
  const body = {body!r};
  window.fetch = (u, o) => String(u).startsWith('/api/llm-status')
    ? Promise.resolve(new Response(body, {{status: 200,
        headers: {{'Content-Type': 'application/json'}}}}))
    : real(u, o);
  if (!document.getElementById('empty-hint')) await handleSlashCommand('/reset');
  await refreshLlmStatus();
  for (let i = 0; i < 100 && !document.querySelector('#empty-hint .ctx-notice'); i++)
    await new Promise((r) => setTimeout(r, 50));
  return !!document.querySelector('#empty-hint .ctx-notice'); }})()""")


_CTX_BASE = {"mode": "owned", "ready": True, "cute": "g40-04", "ctx": 16384,
             "url": "http://127.0.0.1:8080", "error": None,
             "prompt_tokens": 19974, "n_ctx": 16384, "reserve": 2048,
             "fits": False, "preflight": "done"}
CTX_NOTICE_SWITCH: Step = _ctx_notice(dict(
    _CTX_BASE, suggest_ctx=32768, fix="switch", fix_reason=None))
CTX_NOTICE_NONE: Step = _ctx_notice(dict(
    _CTX_BASE, cute="g40-26", ctx=8192, n_ctx=8192, suggest_ctx=32768,
    fix="none", fix_reason="memory"))
CTX_NOTICE_BACK: tuple[Step, ...] = (
    ("eval_await", "(async () => { if (window.__uicheckFetch) {"
                   " window.fetch = window.__uicheckFetch;"
                   " delete window.__uicheckFetch; }"
                   " await refreshLlmStatus(); return true; })()"),
    ("wait_idle", ""))

PAL_BUBBLES_BACK: tuple[Step, ...] = (
    ("eval", "(() => { document.querySelectorAll('.msg.pal, .msg.pal-sent')"
             ".forEach((el) => el.remove()); return true; })()"),
    ("wait_idle", ""))


def _open(form: str, ready: Step | None = None) -> Step:
    """One step: open `form` and wait, in the page, for it to be drawn."""
    sel = ready[1] if ready else ""
    poll = (f" for (let i = 0; i < 120 && !document.querySelector({sel!r});"
            " i++) await new Promise((r) => setTimeout(r, 50));" if sel else "")
    return ("eval_await",
            f"(async () => {{ await compOpenNew('{form}');{poll}"
            " return true; })()")


# Put the composure stage back to the ground floor (composure round, P4c).
#
# There is no "exit": the canvas is the BASE layer, so a composure screen's
# teardown is "open a blank one" rather than "close this one". That is also
# free on disk — a composure nobody typed into is never written — so the
# matrix can run these screens a few hundred times without leaving a single
# `.comp` behind. The tool, the selection, the slider, the menus and the
# search all belong to the document that is going away.
COMP_RESET: tuple[Step, ...] = (
    ("eval", "compToggleComments(false); compCloseMenus();"
             " compSearchClear(true); compSetInkSelection(null);"
             " compSetMode('view'); compSetTool('pointer');"
             " compSetSelection([])"),
    # `_open` awaits the open, so the NEXT screen can never be handed a
    # document that this teardown's open is about to clobber — which is a
    # failure that lands one screen away from its cause.
    _open("blank"),
    ("wait_idle", ""),
)


# `compOpenNew()` is ASYNC, and a blank composure already has one module —
# so `wait_for '.comp-module'` after opening a form matches the document
# that is about to be REPLACED, and the step after it runs against a model
# the adopt is about to throw away. Wait for something only the new form can
# produce instead. (This cost an afternoon: a screen that seeded five
# link-in cards found them gone by the time the probe looked.)


#: Back to the panel's default. Every readvisor screen ends here, because a
#: panel left `closed` or `full` would silently re-lay-out every screen the
#: matrix measures after it.
RV_BACK: tuple[Step, ...] = (("eval", "rvSetState('open')"), ("wait_idle", ""))

#: Agent-free mode (0.4.4, plan §13), switched the way the slider switches
#: it: `agentFreeSet()` POSTs /api/ui-config {agent_free} and awaits the
#: answer. The preference lives in the ui.json `build_env()` points
#: ENOUGH_UI_CONFIG at — the SCRATCH one, shared by the run's project and
#: home servers, never the developer's. The 260 ms waits out the panel's
#: 180 ms column slide, which `wait_idle` cannot see (SIDEBAR_SETTLED's
#: reason).
AF_ON: Step = ("eval_await", "(async () => { await agentFreeSet(true);"
                             " await new Promise((r) => setTimeout(r, 260));"
                             " return agentFreeOn(); })()")
#: Every agent-free screen's teardown. The page is reloaded after a screen,
#: but the FILE is not: a switch left on would carry into every screen (and
#: both servers) after it. If the page's own setter cannot, the scratch
#: config is written directly.
AF_OFF: Step = ("eval_await", "(async () => { try { await agentFreeSet(false); } catch (e) {}"
                              " if (window.agentFreeOn && agentFreeOn()) {"
                              " await fetch('/api/ui-config', {method: 'POST',"
                              " headers: {'Content-Type': 'application/json'},"
                              " body: JSON.stringify({agent_free: false})}); }"
                              " return true; })()")
#: Canon's ingest bar, filled with a url (the confirmation with the most
#: lines: source, volume, depth, the page cap and the fetch gate) and
#: submitted. Agent-free, that raises the plain confirmation — nothing is
#: fetched unless it is confirmed, and the screens never confirm.
CANON_INGEST_URL: Step = ("eval", "(() => { document.getElementById('cn-ingest-type').value = 'url';"
                                  " cnIngestTypeChanged();"
                                  " document.getElementById('cn-ingest-value').value ="
                                  " 'https://example.invalid/orchard/pressing-notes';"
                                  " document.getElementById('cn-ingest-depth').value = '2';"
                                  " submitCanonIngest(); return true; })()")


# ---------------------------------------------------------------------------
# Project-mode screens
# ---------------------------------------------------------------------------

PROJECT_SCREENS: list[Screen] = [
    Screen("project-base", "project",
           note="the ground floor: chat home, sidebar, top bar"),

    # The column slides shut over 180ms and goes `visibility: hidden` at
    # the end of it (0.4.1). `wait_idle` watches the body's size and node
    # count, neither of which a grid-column transition changes, so on its
    # own it measured the sidebar half-way through the slide.
    Screen("sidebar-hidden", "project",
           setup=(("click", "#toggle-sidebar"), SIDEBAR_SETTLED, ("wait_idle", "")),
           teardown=(("click", "#toggle-sidebar"), SIDEBAR_SETTLED, ("wait_idle", "")),
           note="the layout the sidebar toggle leaves behind"),

    # --- modals -----------------------------------------------------------
    Screen("modal-model", "project",
           setup=(("eval", "openModelModal()"),
                  ("wait_for", "#model-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), ("wait_idle", ""))),

    Screen("modal-broker", "project",
           setup=(("eval", "openBrokerModal()"),
                  ("wait_for", "#broker-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), ("wait_idle", ""))),

    Screen("modal-ui", "project",
           setup=(("eval", "openUIModal()"),
                  ("wait_for", "#ui-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), ("wait_idle", ""))),

    Screen("modal-ui-specs", "project",
           setup=(("eval", "openUIModal()"),
                  ("wait_for", "#ui-modal:not(.hidden)"), ("click", "#ui-specs-btn"),
                  ("wait_for", "#ui-specs-menu:not([hidden])"), ("wait_idle", "")),
           teardown=(_esc(), _esc(), ("wait_idle", "")),
           note="the MacroCOSM button's menu open (0.5.0, X2): MacroCOSM, Thym, "
                "Ascribe under the header row"),

    Screen("modal-project", "project",
           setup=(("eval", "openProjectModal()"),
                  ("wait_for", "#project-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), ("wait_idle", ""))),

    Screen("modal-wikisink-setup", "project",
           setup=(("click", "#wikisink-btn"),
                  ("wait_for", "#wiki-setup-modal:not(.hidden), #wiki-mode.open"),
                  ("wait_idle", "")),
           teardown=(_esc(),) + EXIT_ALL_MODES,
           note="no archive in the scratch env: the setup/empty state only"),

    Screen("modal-paginate", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"),
                  ("eval", "document.querySelector('[data-icon=paginate]')"
                           "?.closest('button,[role=button]')?.click()"),
                  ("wait_for", "#paginate-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(("eval", "window.paginateClose && paginateClose()"),
                     ("wait_gone", "#paginate-modal:not(.hidden)"))
                    + EXIT_ALL_MODES),

    Screen("confirm-overlay", "project",
           setup=(("eval", "confirmOverlay({title: 'uicheck', message: "
                           "'a fixture confirmation, long enough that a narrow "
                           "viewport has to wrap it somewhere'})"),
                  ("wait_for", "#confirm-overlay:not([hidden])"),
                  ("wait_idle", "")),
           teardown=(("click", "#confirm-cancel"),
                     ("wait_gone", "#confirm-overlay:not([hidden])")),
           note="the overlay hides with the `hidden` ATTRIBUTE, not the "
                "modal convention's .hidden class"),

    # --- full-frame modes --------------------------------------------------
    Screen("read-full", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("read-mini", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'mini', face:'read'}})"),
                  ("wait_for", "#preview.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("edit-full", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'edit'}})"),
                  ("wait_for", "#edit-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("edit-mini", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'mini', face:'edit'}})"),
                  ("wait_for", "#preview.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("girraph", "project",
           setup=(("eval", f"enterGirraphMode('{GIRRAPH}')"),
                  ("wait_for", "#girraph-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("merirmaid", "project",
           setup=(("eval", f"enterMerirmaidMode('{MERIRMAID}')"),
                  ("wait_for", "#merirmaid-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("canon", "project",
           setup=(("eval", "enterCanonMode()"),
                  ("wait_for", "#canon-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    # --- the docs viewer (0.4.4, DocOES): the help center and the spec ----
    # (the 0.4.1 ref-mode / ref-mini screens, re-pointed: plan §5's gate)
    Screen("docs-help", "project",
           setup=(_docs("help-center"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the help center at the short density, in the UI language's "
                "telling: contents beside the text, margin marks, term links"),

    Screen("docs-help-mini", "project",
           setup=(_docs("help-center"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("eval", "docsToggleSize()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="docked right: the density control down to its glyphs, the "
                "contents folded into a sheet"),

    Screen("docs-help-fr", "project",
           setup=(_docs("help-center", lang="fr"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a telling other than the UI language's (French), in every "
                "language's chrome"),

    Screen("docs-atem", "project",
           setup=(_docs("macrocosm-oes", "atem"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_ATEM_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the spec at the atem density: the outline, the glossary strip "
                "and the reference one-liners grouped by MiniCOSM"),

    Screen("docs-short", "project",
           setup=(("eval_await", "(async () => { await enterDocsMode({doc: 'macrocosm-oes',"
                                 " density: 'short', anchor: '18.4.5'}); return true; })()"),
                  DOCS_SHORT_OK, ("eval", "document.querySelector('#docs-body button.docs-mark')?.focus()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the spec at short on §18.4.5: the margin marks (buttons that flip "
                "to the section's card, one focused), the quiet term links"),

    # --- the fabula density (0.4.4, U2): prism cards, facets, live examples --
    Screen("docs-fabula", "project",
           setup=(_docs("macrocosm-oes", "fabula", anchor="18.4"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_FAB_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the spec at the fabula density on §18.4: the rail (catalog, facets, "
                "modules, section pages, checks) beside the section page's pager and "
                "prism cards"),

    Screen("docs-fabula-mini", "project",
           setup=(_docs("help-center", "fabula", anchor="B:bubble/wikisink"),
                  ("wait_for", "#docs-mode.open"), DOCS_READY, DOCS_FAB_OK,
                  ("eval", "docsToggleSize()"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the help center's fabula docked right on a help bubble's card: the "
                "outline folded into a sheet, the card's lists stacked"),

    Screen("docs-card-term", "project",
           setup=(_docs("macrocosm-oes", "fabula", anchor="T:term/atem"),
                  ("wait_for", "#docs-mode.open"), DOCS_READY, DOCS_FAB_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a term's prism card: its atem, the breadcrumb into the short, "
                "identity, schema (defined in), renderings, mentioned in"),

    Screen("docs-card-example-live", "project",
           setup=(_docs("macrocosm-oes", "fabula", anchor="S:example/4"),
                  ("wait_for", "#docs-mode.open"), DOCS_READY, DOCS_FAB_OK, DOCS_LIVE_OK,
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="an example's card, live: its block loaded as a volume, the lint "
                "verdict, a lens picker and \"open in the cosm viewer\""),

    Screen("docs-graph", "project",
           setup=(_docs("macrocosm-oes", "fabula", anchor="S:section/18.4"),
                  ("wait_for", "#docs-mode.open"), DOCS_READY, DOCS_FAB_OK,
                  ("click", '#docs-body .cosm-card[data-key="S:section/18.4"] [data-dact="graph"]'),
                  ("wait_for", "#merirmaid-mode.open"), MM_NODES_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="\"graph around this\" on §18.4's card: the local graph (one step, "
                "in and out) in merirmaid, read only, the item in bold"),

    # --- the Canon round (0.4.3): volumes, the cosm viewer, the spec -------
    Screen("canon-volume", "project",
           setup=(("eval_await", "(async () => { await enterCanonMode();"
                                 f" CN_STORE_VOLUME = '{CANON_VOLUME}'; CN_STORE_SUB = [];"
                                 " cnRenderStore(); return true; })()"),
                  ("wait_for", "#cn-store-grid .cn-tag"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="inside a volume: the catalog tile, a Holotype folder, a text "
                "with its EMF-twin chip; the project pane's catalog button"),

    Screen("cosm-viewer", "project",
           setup=(("eval", f"enterCosmMode('{EMF_TWIN}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="an EMF twin: the atem card, stances, spans, FEED grounding, "
                "open questions"),

    Screen("cosm-viewer-holotype", "project",
           setup=(("eval", f"enterCosmMode('{HOLOTYPE}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a Comprise Holotype: eight modules, nested fields, the "
                "checks left to Comprise"),

    Screen("cosm-viewer-mini", "project",
           setup=(("eval", f"enterCosmMode('{EMF_TWIN}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("eval", "cosmToggleSize()"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="docked right: two-row toolbar, the outline folded into a sheet"),

    Screen("docs-spec", "project",
           setup=(_docs("macrocosm-oes"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the MacroCOSM spec at short (the 0.4.3 cosmspec screen): its "
                "name and version in the badge, the English-only note in a "
                "translated UI"),

    # --- checkpoint B: the Canon chip, the EMF face, the atem card ---------
    Screen("canon-chip", "project",
           setup=(("eval", f"openReadEdit('{EMF_TEXT}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), CANON_CHIP_READY,
                  ("wait_for", "#canon-chip-review:not([hidden])"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a text with a fresh EMF twin in the read face: the tinted twin "
                "badge, atem, refresh twin and the (?) in the crowded toolbar"),

    Screen("emf-face", "project",
           setup=(("eval", f"openReadEdit('{EMF_TEXT}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), CANON_CHIP_READY,
                  ("eval_await", f"emfFaceShow('{EMF_TEXT}').then(() => true)"),
                  EMF_FACE_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the twin in place of the text, full size: its head (lens, outline, "
                "open raw, compile a short, back to the text), the rail and the cards"),

    Screen("emf-face-mini", "project",
           setup=(("eval", f"openReadEdit('{EMF_TEXT}', {{size:'mini', face:'read'}})"),
                  ("wait_for", "#preview.open"), CANON_CHIP_READY,
                  ("eval_await", f"emfFaceShow('{EMF_TEXT}').then(() => true)"),
                  EMF_FACE_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the same face in the mini panel: the head on two rows, the "
                "outline folded into a sheet"),

    Screen("emf-short-menu", "project",
           setup=(("eval", f"openReadEdit('{EMF_TEXT}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), CANON_CHIP_READY,
                  ("eval_await", f"emfFaceShow('{EMF_TEXT}').then(() => true)"),
                  EMF_FACE_READY, ("eval", "emfShortMenu(true)"),
                  ("wait_for", "#review-emf .emf-short-menu:not([hidden])"), ("wait_idle", "")),
           teardown=(("eval", "(() => { try { emfShortMenu(false); } catch (e) {} return true; })()"),)
                    + EXIT_ALL_MODES,
           note="SHORT: the face's \"compile a short\" split button with its tiny menu open "
                "(as the author told it / by weight, the default marked) over the cards"),

    # --- 0.6, the fabula round (U1a): decompile, the fabulac, cshorts and catems ---
    Screen("fabula-decompile", "project",
           setup=(("eval_await", f"(async () => {{ await fabDecompileOpen('{FAB_POEM}', 'absent'); return true; }})()"),
                  ("wait_for", "#fabula-modal:not(.hidden)"), FAB_READY, ("wait_idle", "")),
           teardown=(FAB_CLOSE,) + EXIT_ALL_MODES,
           note="the card before a decompile, on a poem with no twin: prose or verse with verse "
                "marked as the suggestion, where each twin would be written, the model line "
                "(here; the cloud is shut in the scratch environment), decompile"),

    Screen("fabula-decompile-old", "project",
           setup=(("eval_await", f"(async () => {{ await fabDecompileOpen('{EMF_TEXT}', 'fresh'); return true; }})()"),
                  ("wait_for", "#fabula-modal:not(.hidden)"), FAB_READY, ("wait_idle", "")),
           teardown=(FAB_CLOSE,) + EXIT_ALL_MODES,
           note="the same card on the orchard notes, whose twin has the old name: its state, the "
                "line that says decompiling again writes the new name and removes the old file, "
                "the up-to-date note, decompile again"),

    Screen("fabula-build", "project",
           setup=(("eval_await", f"(async () => {{ await fabFolderOpen('{FAB_TOOL}'); return true; }})()"),
                  ("wait_for", "#fabula-modal:not(.hidden)"), FAB_READY, ("wait_idle", "")),
           teardown=(FAB_CLOSE,) + EXIT_ALL_MODES,
           note="a folder's fabulac card, the build complete: the five stages with who ran them, "
                "the model line, compile (as code or a catem at three depths), what it has made "
                "(a cshort, a catem) with open, build again and open the fabulac"),

    Screen("fabula-cosm", "project",
           setup=(("eval", f"enterCosmMode('{FAB_FABULAC}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a fabulac in the cosm viewer: build and compile… in the toolbar, the rail with "
                "who made it (model, route, its runs) and the source's licence, the modules I to "
                "D with the fabulac's kinds"),

    Screen("fabula-cshort", "project",
           setup=(("eval_await", f"(async () => {{ await fabViewOpen('{FAB_CSHORT}'); return true; }})()"),
                  ("wait_for", "#cshort-modal:not(.hidden)"), FABV_READY, ("wait_idle", "")),
           teardown=(FABV_CLOSE,) + EXIT_ALL_MODES,
           note="a cshort read: the line that says enough never runs it, the footer and the "
                "licence, the file list and the first source file as monospaced text"),

    Screen("fabula-catem", "project",
           setup=(("eval_await", f"(async () => {{ await fabViewOpen('{FAB_CATEM}'); return true; }})()"),
                  ("wait_for", "#cshort-modal:not(.hidden)"), FABV_READY, ("wait_idle", "")),
           teardown=(FABV_CLOSE,) + EXIT_ALL_MODES,
           note="a catem at depth overview: its depth line, the markdown, its footer"),

    # --- 0.6, the fabula round (U1b): the dialectic card, a holograph, its isograph ---
    Screen("dialectic-card", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_KINDS}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY, ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="the dialectic card on a fabulan with one open question of every kind: the "
                "progress line, who is asked, the first two (a text, a choice with other:), "
                "each with what it is about, its hint, I don't know / I'd rather not say / "
                "skip for now, keep these and the next, send the sitting"),

    Screen("dialectic-kinds-yes-number", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_KINDS}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY,
                  _dlg_put("D:question/meant-to-reassure", "D:question/retry-hour"), ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a yes-no question and a number with its range"),

    Screen("dialectic-kinds-date-ref", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_KINDS}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY,
                  _dlg_put("D:question/published", "D:question/feed-source"), ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a date (a year or year-month too) and a reference to an item, with its prefix"),

    Screen("dialectic-kinds-span-pending", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_KINDS}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY,
                  _dlg_put("D:question/retry-lines", "L:term/morning-summary#feed"),
                  ("eval", "(() => { const b = document.getElementById('dlg-alt-dont_know-1'); if (b) b.click(); return true; })()"),
                  ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a span of lines, and an open field asked by its address, answered I don't know"),

    Screen("dialectic-sitting", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_KINDS}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY,
                  ("eval", "(() => { const a = document.getElementById('dlg-in-0'); a.value = 'An owner rang support twice in a week.';"
                           " a.dispatchEvent(new Event('input', {bubbles: true}));"
                           " const r = document.querySelector('input[name=\"dlg-r-1\"][value=\"warm\"]'); r.checked = true;"
                           " r.dispatchEvent(new Event('input', {bubbles: true})); document.getElementById('dlg-next').click();"
                           " const n = document.getElementById('dlg-in-1'); n.value = '30';"
                           " n.dispatchEvent(new Event('input', {bubbles: true})); return true; })()"),
                  ("eval_await", "(async () => { for (let i = 0; i < 100 && !(document.getElementById('dlg-chk-1') || {}).textContent; i++)"
                                 " await new Promise((r) => setTimeout(r, 50)); return true; })()"),
                  ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="two answers kept in the sitting (with change), the next two in hand, a number "
                "out of its range refused in the server's words beside its field"),

    Screen("dialectic-waiting", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_SITTING}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY, ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a sitting written and not settled: the open fields still to answer, settle with "
                "its sitting file and the model line (here), the question waiting in that sitting, "
                "answered before (one settled question) with ask again"),

    Screen("dialectic-raise", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_BARE}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY, ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a volume with no questions yet: what raising them asks, raise the questions, "
                "and its open fields answerable meanwhile"),

    Screen("dialectic-holograph", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_SELF}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY, ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="a holograph's card: for the holder alone, personal data refused, nothing to a "
                "cloud model (and no model line), the thinnest part of the self asked first"),

    Screen("dialectic-candidate", "project",
           setup=(("eval_await", f"(async () => {{ await dlgOpen('{DLG_SELF}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY,
                  _dlg_put("D:question/splicing-an-eye-by-hand-candidate", "D:question/reading-the-weather-candidate"),
                  ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="two candidates a reading of the holder's own text proposed, each with what it "
                "says and yes / partly / no, what each does said under it"),

    Screen("dialectic-isograph", "project",
           setup=(("eval_await", f"(async () => {{ await dlgIsoOpen('{DLG_SELF}'); return true; }})()"),
                  ("wait_for", "#dialectic-modal:not(.hidden)"), DLG_READY, ("wait_idle", "")),
           teardown=(DLG_CLOSE,) + EXIT_ALL_MODES,
           note="the isograph face: what an isograph is and that it leaves no name, the holder's "
                "program, make the isograph"),

    Screen("dialectic-holograph-cosm", "project",
           setup=(("eval", f"enterCosmMode('{DLG_SELF_PII}')"), ("wait_for", "#cosm-mode.open"), COSM_READY,
                  ("eval_await", "(async () => { for (let i = 0; i < 100 && document.getElementById('cosm-dlg-btn').hidden; i++)"
                                 " await new Promise((r) => setTimeout(r, 50));"
                                 " const d = document.querySelector('#cosm-rail details.cosm-problems'); if (d) d.open = true;"
                                 " return true; })()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a holograph in the cosm viewer: questions (with its count) and the isograph… in the "
                "toolbar, the checks' personal-data warnings each with its advice on a line"),

    Screen("dialectic-cosm-count", "project",
           setup=(("eval", f"enterCosmMode('{DLG_KINDS}')"), ("wait_for", "#cosm-mode.open"), COSM_READY,
                  ("eval_await", "(async () => { for (let i = 0; i < 100 && document.getElementById('cosm-dlg-btn').hidden; i++)"
                                 " await new Promise((r) => setTimeout(r, 50)); return true; })()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a fabulan in the cosm viewer: questions with the count of the open ones in the toolbar"),

    # --- 0.5.0, Thym (U1): programs, plans, traces, the run card, readings ---
    Screen("thym-program", "project",
           setup=(("eval_await", f"(async () => {{ await enterProgramDoc('{THYM_PROGRAM}', {{density: 'fabula'}});"
                                 " return true; })()"),
                  ("wait_for", "#docs-mode.open"), THYM_DOC_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a program as a document at the fabula density: the program's card with "
                "\"run with…\" and its (?), its steps in order with their contracts under "
                "them, the rail with the steps"),

    Screen("thym-plan", "project",
           setup=(("eval", f"enterCosmMode('{THYM_PLAN}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_for", "#cosm-body figure.thym-graph"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a plan in the cosm viewer: its atem and cost line, the graph (nodes, "
                "`after` as edges, a diamond where a node asks the model), the plan lens "
                "button, the nodes in order"),

    Screen("thym-trace", "project",
           setup=(("eval", f"enterCosmMode('{THYM_TRACE}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="checkpoint A's trace: the atem as the title line with the outcome, one "
                "card per record (step, move, engine, attempts, seconds, tokens, every "
                "check with its verdict), the plan it followed folded"),

    Screen("thym-run", "project",
           setup=(_thym_pick(EMF_TEXT, THYM_PROGRAM), ("wait_for", "#thym-modal:not(.hidden)"),
                  THYM_PICK_READY, ("wait_idle", "")),
           teardown=(("eval", "(() => { try { thymPickClose(); } catch (e) {} return true; })()"),)
                    + EXIT_ALL_MODES,
           note="\"run with…\" on the orchard notes, publish-story chosen: the programs "
                "(project first, shipped last), the plan's cost line and, with no model "
                "here, the refusal that says why it cannot run; route-less, the "
                "\"not available yet\" line"),

    Screen("thym-read", "project",
           setup=(("eval", f"openReadEdit('{THYM_READING}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), THYM_BAND_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a reading open in the full reader: the band under the toolbar, "
                "\"read through null\" and the footer line, with the (?)"),

    # --- 0.6, Thym (U1c): writing a program, the moves at hand, a plan to read, run with every input ---
    Screen("thym-editor", "project",
           setup=(_thym_edit(THYM_BROKEN), ("wait_for", "#thym-ed.refused"), ("wait_idle", "")),
           teardown=(THYM_EDIT_CLEAN,) + EXIT_ALL_MODES,
           note="a program refused at line 9 in the full editor: the strip under the toolbar with the line as a "
                "button, the check and the compiler's own words, the version line it reads, F8's line, the "
                "moves… and plan and run… buttons and the (?)"),

    Screen("thym-editor-mini", "project",
           setup=(_thym_edit(THYM_TWO, "mini"), ("wait_for", "#thym-ed-mini.clean"), ("wait_idle", "")),
           teardown=(THYM_EDIT_CLEAN,) + EXIT_ALL_MODES,
           note="a thym 1 program that compiles, in the mini editor: the strip above the text says so, the "
                "version line, what it takes and gives, its steps"),

    Screen("thym-moves", "project",
           setup=(("eval_await", thym_moves_stub_js()), _thym_edit(THYM_TWO), ("wait_for", "#thym-ed.clean"),
                  ("eval", "(() => { thymRefOpen('moves'); return true; })()"),
                  ("wait_for", "#thym-ref-modal:not(.hidden) article.tref-move"), ("wait_idle", "")),
           teardown=(THYM_REF_CLOSE, THYM_EDIT_CLEAN) + EXIT_ALL_MODES,
           note="Thym at hand over the editor, its moves tab: the search, thym 1 / thym 0, where \"put it in\" "
                "writes, the count, the moves grouped by the format that declares them, each with its "
                "signature, whether it asks, its contract, its scaffold, an example and \"put it in\""),

    Screen("thym-programs", "project",
           setup=(("eval", "(() => { thymRefOpen('programs'); return true; })()"),
                  ("wait_for", "#thym-ref-modal:not(.hidden) article.tref-prog"), ("wait_idle", "")),
           teardown=(THYM_REF_CLOSE,) + EXIT_ALL_MODES,
           note="the programs to start from: every shipped program with its version, file, why: line, what "
                "it takes and gives, read it and copy into this project to change it"),

    Screen("thym-run-inputs", "project",
           setup=(_thym_run_on(THYM_TWO, {"repo": THYM_REPO, "s": THYM_LONG}),
                  ("wait_for", "#thym-modal:not(.hidden)"), THYM_PLAN_READY, ("wait_idle", "")),
           teardown=(THYM_PICK_CLOSE,) + EXIT_ALL_MODES,
           note="run with… a thym 1 program that takes a folder and a short: an input row for each with what "
                "it takes and what a folder's run reads, the plan's steps at their lines with the loop said "
                "with its passes, what it reads (the folder's files and bytes) and what it will write, two "
                "outputs, beside the folder"),

    Screen("thym-run-asks", "project",
           setup=(_thym_run_on("tighten.thym", None, THYM_LONG),
                  ("wait_for", "#thym-modal:not(.hidden)"), THYM_PLAN_READY, ("wait_idle", "")),
           teardown=(THYM_PICK_CLOSE,) + EXIT_ALL_MODES,
           note="the shipped tighten on a short: its plan asks a model and none is here, so it is refused at "
                "its statement (quoted, at its line), and the loop over the short's lines is said to be known "
                "only at run time, keeping its contract"),

    Screen("thym-run-landed", "project",
           setup=(_thym_run_on(THYM_TWO, {"repo": THYM_REPO, "s": THYM_LONG}),
                  ("wait_for", "#thym-modal:not(.hidden)"), THYM_PLAN_READY,
                  ("eval", "(() => { Object.assign(THYM_PICK, {result: {run: 'seed', outcome: 'landed',"
                           " atem: 'ran two-outs on little-repo, long-lines.md in 0 s: 3 steps, all checks green',"
                           " outputs: [{name: 'n', type: 'number', rel: 'orchard/little-repo.n.txt'},"
                           " {name: 'listing', type: 'short', rel: 'orchard/little-repo.listing.md'}]}});"
                           " thymPickPaint(); return true; })()"),
                  ("wait_for", "#thym-status [data-topen]"), ("wait_idle", "")),
           teardown=(THYM_PICK_CLOSE,) + EXIT_ALL_MODES,
           note="a landed run of two outputs: what it made, each by its name and type with open and its path, "
                "show the trace in the foot (the result is placed by the screen: it runs nothing)"),

    Screen("thym-run-refused", "project",
           setup=(_thym_run_on("tighten.thym", None, THYM_LONG),
                  ("wait_for", "#thym-modal:not(.hidden)"), THYM_PLAN_READY,
                  ("eval", "(() => { Object.assign(THYM_PICK, {result: {run: 'seed', outcome: 'refused',"
                           " atem: 'ran tighten on long-lines.md in 31 s: refused at step 1',"
                           " refusal: {stage: 'run', check: 'shorter', line: 18, message: '`give reword l to 30 words`"
                           " (line 18, for l = line 3): the reworded line is not shorter than the line it replaces'},"
                           " outputs: []}, told: [{name: 'let changes = for each l in lines of s where words l > 30',"
                           " attempts: 3, failed: [{name: 'shorter', why: 'the reworded line is not shorter than the"
                           " line it replaces'}], tries: [{attempt: 1, failed: [{name: 'length', why: '34 words, more"
                           " than 30'}]}, {attempt: 2, failed: [{name: 'shorter', why: 'the reworded line is not"
                           " shorter than the line it replaces'}]}, {attempt: 3, failed: [{name: 'shorter', why:"
                           " 'the reworded line is not shorter than the line it replaces'}]}]}]});"
                           " thymPickPaint(); return true; })()"),
                  ("wait_for", "#thym-status .thym-told"), ("wait_idle", "")),
           teardown=(THYM_PICK_CLOSE,) + EXIT_ALL_MODES,
           note="a run its contract refused: the refusal in the runtime's words, the condition that failed in "
                "the contract's own words, and what the model was told each time it was asked again (placed by "
                "the screen from a recorded trace's shape: it runs nothing)"),

    Screen("thym-trace-tries", "project",
           setup=(("eval", f"enterCosmMode('{THYM_TRIES}')"), ("wait_for", "#cosm-mode.open"),
                  COSM_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="a recorded tighten run whose first reword failed length and was asked again: the record's "
                "attempts that failed, folded, each with what the next ask was told"),

    # --- 0.5.0, Thym (U2): a package made, its key shown once, a package unpacked ---
    Screen("thym-package", "project",
           setup=(("eval_await", f"(async () => {{ await thymPackOpen('{EMF_TEXT}'); return true; }})()"),
                  ("wait_for", "#thym-pack-modal:not(.hidden)"), THYM_PACK_READY, ("wait_idle", "")),
           teardown=(THYM_PACK_CLOSE,) + EXIT_ALL_MODES,
           note="\"package…\" on the orchard notes: what goes in (the text, its twin, the morph "
                "beside it, its context), where both forms land, the seal box with its note, the "
                "package button and the (?)"),

    Screen("thym-package-key", "project",
           setup=(("eval_await", f"(async () => {{ await thymPackOpen('{EMF_TEXT}'); return true; }})()"),
                  ("wait_for", "#thym-pack-modal:not(.hidden)"), THYM_PACK_READY,
                  ("eval", "(() => { Object.assign(THYM_PACK, {seal: true, result: {package: 'orchard/notes.package.cosm',"
                           " folder: 'orchard/notes.thym', sealed: 'orchard/notes.thym.enc'},"
                           f" key: '{THYM_PLACEHOLDER_KEY}', nudge: true}}); thymPackPaint(); return true; }})()"),
                  ("wait_for", "#thym-pack-key:not([hidden])"), ("wait_idle", "")),
           teardown=(THYM_PACK_CLOSE,) + EXIT_ALL_MODES,
           note="the same card once a sealed package has landed: the three forms listed, the key "
                "large and monospaced with its copy button, the shown-once line and the nudge esc "
                "gives; only \"I have it\" closes it (a placeholder key: the screen seals nothing)"),

    Screen("thym-unpack", "project",
           setup=(("eval_await", f"(async () => {{ await thymUnpackOpen('{THYM_SEALED}'); return true; }})()"),
                  ("wait_for", "#thym-pack-modal:not(.hidden)"), THYM_UNPACK_READY, ("wait_idle", "")),
           teardown=(THYM_PACK_CLOSE,) + EXIT_ALL_MODES,
           note="\"unpack…\" on a sealed package that came in a folder of its own: what will be "
                "written beside it, the key field, the unpack button"),

    Screen("atem-card", "project",
           setup=(_atem_of_passage("full"), ATEM_READY, ("wait_idle", "")),
           teardown=(ATEM_CLOSE,) + EXIT_ALL_MODES,
           note="a passage's atem over the read face, rules mode: the line, focus, "
                "push and pull as open questions, the scaffold note, pin to twin"),

    Screen("atem-card-mini", "project",
           setup=(_atem_of_passage("mini"), ATEM_READY, ("wait_idle", "")),
           teardown=(ATEM_CLOSE,) + EXIT_ALL_MODES,
           note="the card raised over the mini reader"),

    Screen("docs-spec-mini", "project",
           setup=(_docs("macrocosm-oes"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("eval", "docsToggleSize()"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    # --- 0.5.0 (lane X2): Thym and Ascribe, the two specs written in MacroCOSM OES
    Screen("docs-thym", "project",
           setup=(_docs("thym"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the Thym specification at short: \"Thym · edition 0.5.4\" in the "
                "badge, the English-only note in a translated UI, its term links"),

    Screen("docs-ascribe", "project",
           setup=(_docs("ascribe"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the Ascribe specification at short: \"Ascribe · edition 0.5.4\" "
                "in the badge (its title says where the text came from), the "
                "English-only note in a translated UI"),

    # --- 0.5.4: Comprise OES, the fourth specification, a document of its own
    Screen("docs-comprise", "project",
           setup=(_docs("comprise-oes"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the Comprise OES specification at short: \"Comprise OES · edition "
                "0.5.4\" in the badge, its P.N section numbers linked, its § left "
                "as words"),

    # --- FEED: the dictionary, the word data lightbox (0.4.1) -------------
    Screen("dict-mode", "project",
           setup=(DICT_PLAIN, ("eval", "enterDictMode({word: 'lantern'})"),
                  ("wait_for", "#dict-mode.open"), DICT_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("dict-sorted-filters", "project",
           setup=(DICT_PLAIN, ("eval", "enterDictMode()"), ("wait_for", "#dict-mode.open"),
                  DICT_READY,
                  ("eval", "(() => { Object.assign(DICT.view, {sort: 'domain', then: 'era'});"
                           " dictViewChanged(); dictOptsToggle(true); return true; })()"),
                  DICT_READY, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="domain, then era: margin keys, lettered group headings, the "
                "presets + filters strip open under the toolbar"),

    Screen("dict-search", "project",
           setup=(DICT_PLAIN, ("eval", "enterDictMode()"), ("wait_for", "#dict-mode.open"),
                  DICT_READY, ("eval", "dictSetQuery('twilight')"),
                  ("wait_for", "#dict-flow mark"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("wdl-plate", "project",
           setup=(DICT_PLAIN, ("eval", "enterDictMode()"), ("wait_for", "#dict-mode.open"),
                  DICT_READY, ("eval", "wdlOpen('gloaming', {fromDict: true})"),
                  ("wait_for", "#wdl-modal:not(.hidden)"), WDL_READY, ("wait_idle", "")),
           teardown=(("eval", "wdlClose()"),) + EXIT_ALL_MODES),

    Screen("wdl-over-read", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"),
                  ("eval", "(() => { wdlOpen('serendipity'); WDL.tab = 'languages'; return true; })()"),
                  ("wait_for", "#wdl-modal:not(.hidden)"), WDL_READY, ("wait_idle", "")),
           teardown=(("eval", "wdlClose()"),) + EXIT_ALL_MODES,
           note="the lightbox over another mode, its languages tab"),

    Screen("wdl-not-found", "project",
           setup=(("eval", "wdlOpen('glomrify')"),
                  ("wait_for", "#wdl-modal:not(.hidden)"), WDL_READY, ("wait_idle", "")),
           teardown=(("eval", "wdlClose()"), ("wait_idle", ""))),

    # --- help --------------------------------------------------------------
    Screen("help-bubble", "project",
           setup=(("eval", "openHelp('skills')"),
                  ("wait_for", "#help-viewer.open"), ("wait_idle", "")),
           teardown=(("eval", "closeHelp()"), ("wait_idle", ""))),

    # --- the composure canvas (P4c-1 + P4c-2) ------------------------------
    # Composure is the BASE layer, so there is no "enter" — a fresh project
    # already opens on one, and every screen below is a different document
    # or a different tool on the same stage. Teardown puts a blank back:
    # a composure nobody types into writes no file, so this costs nothing
    # on disk however many times the matrix runs it.
    Screen("composure-blank", "project",
           note="a fresh project opens on a blank composure, caret ready"),

    Screen("composure-cards", "project",
           setup=(_open("cards", CARDS_READY), ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-scaffold", "project",
           setup=(_open("scaffold", SCAFFOLD_READY), ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-journal", "project",
           setup=(_open("journal", JOURNAL_READY), ("wait_idle", "")),
           teardown=COMP_RESET,
           note="opens on today's page with the file-entry button live"),

    Screen("composure-journal-filed", "project",
           setup=(_open("journal", JOURNAL_READY),
                  # A filed page, faked in the MODEL only: the date header
                  # and the read-only body are what this screen is for, and
                  # filing for real would write a file per matrix cell.
                  ("eval", "(() => { const m = COMP.model.modules[0];"
                           " m.pages[0].date = '2026-09-17';"
                           " m.pages[0].filed = true; m.pages[0].locked = true;"
                           " m.pages[0].rich = '<p>a filed entry, long enough "
                           "that a narrow page has to wrap it.</p>';"
                           " COMP.journal = null; compEndEditing();"
                           " compRefreshModule(m.id); compUpdateJournalBtn();"
                           " return true; })()"),
                  ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-council", "project",
           setup=(_open("council"), COUNCIL_READY, ("wait_idle", "")),
           teardown=COMP_RESET + (("eval", "rvForceClosed(false)"),
                                  ("wait_idle", "")),
           note="a council in `setup`: the setup card, and the readvisor "
                "panel pinned shut while it is the stage"),

    Screen("composure-council-footer", "project",
           setup=(COUNCIL_SETUP, ("wait_idle", "")),
           teardown=COMP_RESET + (("eval", "rvForceClosed(false)"),
                                  ("wait_idle", "")),
           note="a convened council: the footer replaces the chat"),

    Screen("composure-council-concluded", "project",
           setup=(COUNCIL_SETUP, COUNCIL_CONCLUDE, ("wait_idle", "")),
           teardown=COMP_RESET + (("eval", "rvForceClosed(false)"),
                                  ("wait_idle", "")),
           note="the footer collapsed to the transcript line and the "
                "reconvene control"),

    Screen("composure-council-composure-output", "project",
           setup=(COUNCIL_COMPOSURE, ("wait_idle", "")),
           teardown=COMP_RESET + (("eval", "rvForceClosed(false)"),
                                  ("wait_idle", "")),
           note="the setup card with a `composure` output: the form select "
                "revealed, no path field, and a charge under every "
                "non-user row"),

    Screen("composure-council-pal", "project",
           setup=(COUNCIL_SETUP, COUNCIL_PAL_STATEMENT,
                  ("wait_for", ".comp-module[data-speaker-kind='pal']"),
                  ("wait_idle", "")),
           teardown=COMP_RESET + (("eval", "rvForceClosed(false)"),
                                  ("wait_idle", "")),
           note="a pal's statement: gray, and the outgoing prompt collapsed "
                "behind its disclosure"),

    Screen("composure-edit", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compSetMode('edit')"), ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-inspector", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compSetMode('edit'); compSetTool('pointer');"
                           " compSetSelection([COMP.model.modules[0].id])"),
                  ("wait_for", "#comp-inspector:not([hidden])"),
                  ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-ink", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compSetMode('edit'); compSetTool('pencil')"),
                  # One freehand stroke and one shift-drag arrow (the
                  # doubled points are the arrowhead's hard corners).
                  ("eval", "compDo({ops: [{op: 'add_strokes', strokes: ["
                           "{id: 'suicheck1', color: 'ink', width: 2,"
                           " points: [[40,40],[120,92],[200,44],[292,128]]},"
                           "{id: 'suicheck2', color: 'red', width: 2,"
                           " points: [[40,220],[260,220],[260,220],[232,206],"
                           "[232,206],[260,220],[260,220],[232,234]]}]}],"
                           " undo: []}); compFitAll(false)"),
                  ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-ink-selected", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compSetMode('edit'); compSetTool('pointer');"
                           " compDo({ops: [{op: 'add_strokes', strokes: ["
                           "{id: 'suicheck3', color: 'blue', width: 2,"
                           " points: [[40,40],[120,92],[200,44]]}]}], undo: []});"
                           " compSetInkSelection('suicheck3')"),
                  ("wait_for", "#comp-insp-slot .comp-swatch[data-ink]"),
                  ("wait_idle", "")),
           teardown=COMP_RESET,
           note="the inspector's ink palette — the five named ink colours"),

    Screen("composure-links", "project",
           setup=(_open("cards", CARDS_READY),
                  # The five link-in cards, side by side, in the MODEL only.
                  ("eval", "(() => { const mk = (id, type, fields, title) => ({"
                           " id, type, known_type: true, x: 0, y: 0, w: 320,"
                           " h: 150, z: 1, bg: 'paper', known_bg: true,"
                           " scale: 1, title, cur: 1, fields, speaker: null,"
                           " speaker_kind: null, turn: null, locked: false,"
                           " page_count: 1, pages: [{n: 1, rich: '',"
                           " first_line: '', chars: 0, date: null,"
                           " filed: false, locked: false, data: {}}], data: {}});"
                           " const rows = [mk('mudoc','doc',{href:'notes.md'},''),"
                           " mk('muwiki','wiki',{article:'A/Ada_Lovelace'},''),"
                           " mk('mulink','weblink',{url:'https://example.invalid/a'},''),"
                           " mk('muframe','webframe',{url:'https://example.invalid/b',"
                           " refresh:'manual'},''),"
                           " mk('muimg','image',{href:'cover.png'},'')];"
                           " rows.forEach((m, i) => { m.x = (i % 2) * 360;"
                           " m.y = Math.floor(i / 2) * 180; });"
                           " COMP.model.modules = rows; compRenderModules();"
                           " COMP.zoomed = true;"
                           " COMP.userZoom = 1 / compPanelFactor();"
                           " COMP.origin = {x: -24, y: -24};"
                           " compApplyView(false); return true; })()"),
                  ("wait_for", ".comp-link"), ("wait_idle", "")),
           teardown=COMP_RESET,
           note="all five link-in renderers; no archive and no network in "
                "the scratch env, so each shows its degraded card"),

    Screen("composure-comments", "project",
           setup=(_open("cards", CARDS_READY),
                  # Open the slider FIRST: toggling it on reloads the
                  # sidecar, which would wipe the fixture comments below.
                  ("eval", "compToggleComments(true)"), ("wait_idle", ""),
                  ("eval", "COMP.comments = [{id: 'c_uicheck1',"
                           " body: 'a fixture comment, long enough that a "
                           "narrow panel has to decide where to wrap it',"
                           " created_at: '2026-09-17T10:00:00Z',"
                           " resolved: false, replies: [{id: 'r_uicheck1',"
                           " body: 'and a reply'}], anchor: {type: 'quote',"
                           " module: COMP.model.modules[0].id, page: 1,"
                           " quote: 'One idea per card'}, state: 'anchored'},"
                           "{id: 'c_uicheck2', body: 'on the whole module',"
                           " created_at: '2026-09-17T10:05:00Z',"
                           " resolved: false, replies: [], anchor: {type:"
                           " 'module', module: COMP.model.modules[0].id},"
                           " state: 'module'}];"
                           " compRenderComments()"),
                  ("wait_for", "#comp-comments-list .wiki-comment-card"),
                  ("wait_idle", "")),
           teardown=COMP_RESET,
           note="the slider docks inside main, left of the readvisor panel"),

    Screen("composure-search", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "document.getElementById('comp-search').value = 'card';"
                           " compSearchRun('card'); compSearchGo(1)"),
                  ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-type-menu", "project",
           setup=(("eval", "compSetMode('edit'); compOpenTypeMenu()"),
                  ("wait_for", "#comp-type-menu button[data-type]"),
                  ("wait_idle", "")),
           teardown=(("eval", "compCloseMenus()"),) + COMP_RESET),

    Screen("composure-ctx-menu", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compOpenCtxMenu(COMP.model.modules[0].id,"
                           " {clientX: 260, clientY: 240})"),
                  ("wait_for", "#comp-ctx-menu button[data-act]"),
                  ("wait_idle", "")),
           teardown=(("eval", "compCloseMenus()"),) + COMP_RESET),

    Screen("composure-composures-menu", "project",
           setup=(("eval", "compOpenComposuresMenu()"),
                  ("wait_for", "#comp-menu button[data-form]"),
                  ("wait_idle", "")),
           teardown=(("eval", "compCloseMenus()"),) + COMP_RESET),

    # 0.4.2: a composure's own settings, every <details> open so the
    # longest labels and the facts grid are all measured at once.
    Screen("composure-settings", "project",
           setup=(("eval_await", "compOpenSettings()"),
                  ("wait_for", "#comp-settings-modal:not(.hidden)"),
                  ("eval", "document.querySelectorAll('#comp-settings-modal details')"
                           ".forEach((d) => { d.open = true; })"),
                  ("wait_idle", "")),
           teardown=(("eval", "compCloseSettings()"),) + COMP_RESET,
           note="a composure's settings modal, all sections open"),

    Screen("composure-faces", "project",
           setup=(_open("scaffold", SCAFFOLD_READY),
                  ("eval", "COMP.zoomed = true;"
                           " COMP.userZoom = 0.2 / compPanelFactor();"
                           " compApplyView(false)"),
                  ("wait_for", ".comp-module.comp-faced"), ("wait_idle", "")),
           teardown=COMP_RESET,
           note="semantic zoom: every card is its own title, whole words only"),

    Screen("composure-pages", "project",
           setup=(_open("cards", CARDS_READY),
                  ("eval", "compSetMode('edit'); compSetTool('pointer');"
                           " compSetSelection([COMP.model.modules[0].id]);"
                           " compAddPage(); compFitAll(false)"),
                  ("wait_for", ".comp-pages"), ("wait_idle", "")),
           teardown=COMP_RESET),

    Screen("composure-notice", "project",
           setup=(("eval", "compNotice('a test notice, long enough that a "
                           "narrow stage has to wrap it somewhere')"),
                  ("wait_for", "#comp-notice:not([hidden])"), ("wait_idle", "")),
           teardown=(("eval", "document.getElementById('comp-notice')"
                              ".hidden = true"), ("wait_idle", ""))),

    Screen("composure-peek", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"),
                  ("eval", "compPeekSet(true)"),
                  ("wait_idle", "")),
           teardown=(("eval", "compPeekSet(false)"),) + EXIT_ALL_MODES,
           note="every stacked root hidden, state intact, indicators dimmed"),

    # --- the readvisor panel (P3's registry additions, wired in P6c) -------
    #
    # P3 landed the panel and listed these; nothing had added them, so the
    # suite has been checking a UI with a four-state column in it and never
    # once looking at three of the four states. Each is a different layout of
    # the same grid, which is exactly what the layout probes are for.
    Screen("readvisor-docked", "project",
           setup=(("eval", "rvSetState('open')"), ("wait_idle", "")),
           teardown=RV_BACK,
           note="the default: the panel docked beside the stage"),

    Screen("readvisor-closed", "project",
           setup=(("eval", "rvSetState('closed')"), ("wait_idle", "")),
           teardown=RV_BACK,
           note="the stage with the whole width to itself"),

    Screen("readvisor-full", "project",
           setup=(("eval", "rvSetState('full')"), ("wait_idle", "")),
           teardown=RV_BACK,
           note="the panel over the stage at its reading width"),

    Screen("readvisor-overlay", "project",
           # The overlay is not a state the UI can be PUT into — it is what
           # the docked state becomes when the stage left over would be
           # under RV_MIN_STAGE, and `rvApplyOverlay()` sets
           # `data-rvOverlay` for it. So the recipe is the docked state, and
           # the matrix's narrow viewports (1024x640, 1080x1920) are what
           # actually exercises it. Measuring it under its own name is what
           # makes a finding say WHICH layout broke.
           setup=(("eval", "rvSetState('open'); rvApplyOverlay()"),
                  ("wait_idle", "")),
           teardown=RV_BACK,
           note="docked, but floating over the stage — narrow viewports only"),

    Screen("readvisor-chip", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open .review-body"),
                  ("eval", "rvSetState('open')"),
                  # A real selection in the document, captured through the
                  # product's own capture function, so the chip carries the
                  # shape P4c-2's one renderer produces.
                  ("eval", "(() => { const body = document.querySelector("
                           "'#review-mode .review-body'); if (!body) return false;"
                           " const walk = document.createTreeWalker(body,"
                           "  NodeFilter.SHOW_TEXT); let n = null;"
                           " for (let x = walk.nextNode(); x; x = walk.nextNode())"
                           "  { if ((x.textContent || '').trim().length > 20)"
                           "    { n = x; break; } }"
                           " if (!n) return false; const r = document.createRange();"
                           " r.setStart(n, 0); r.setEnd(n, 24);"
                           " const s = window.getSelection(); s.removeAllRanges();"
                           " s.addRange(r); captureLastReviewSelection();"
                           " rvUpdateChip(); return true; })()"),
                  ("wait_for", "#rv-chip:not([hidden])"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES + RV_BACK,
           note="the selection chip above the composer"),

    Screen("readvisor-forced-closed", "project",
           setup=(("eval", "rvForceClosed(true, 'a council is using the whole "
                           "conversation')"), ("wait_idle", "")),
           teardown=(("eval", "rvForceClosed(false)"),) + RV_BACK,
           note="pinned shut with a reason, and the toggle disabled"),

    Screen("readvisor-unread", "project",
           # There is no model in the scratch world, so no turn can ever
           # finish and the dot can never appear on its own. `_rvMarkUnread()`
           # is the product's own one-line function for it (a top-level
           # declaration, so it is a global like every other), and calling it
           # is still driving the product rather than painting a class on.
           setup=(("eval", "rvSetState('closed'); _rvMarkUnread()"),
                  ("wait_for", "#toggle-readvisor.rv-unread"), ("wait_idle", "")),
           teardown=RV_BACK,
           note="the unread dot on the topbar toggle"),

    # --- the context notice (the 16 GB context fix, 0.4.3) ----------------
    #
    # The empty conversation when enough's instructions do not fit the
    # model's window: with the one-click larger window, and without it (the
    # reason and a way into the model window). See CTX_NOTICE_SWITCH.
    Screen("readvisor-ctx-notice", "project",
           setup=(("eval", "rvSetState('open')"), CTX_NOTICE_SWITCH,
                  ("wait_for", "#empty-hint .ctx-notice .ctx-notice-switch"),
                  ("wait_idle", "")),
           teardown=CTX_NOTICE_BACK + RV_BACK,
           note="the instructions do not fit: numbers + 'use a 32,768-token "
                "window' (the /api/llm-status body is stubbed in the page)"),

    Screen("readvisor-ctx-notice-none", "project",
           setup=(("eval", "rvSetState('open')"), CTX_NOTICE_NONE,
                  ("wait_for", "#empty-hint .ctx-notice .ctx-notice-open"),
                  ("wait_idle", "")),
           teardown=CTX_NOTICE_BACK + RV_BACK,
           note="no affordable window: the reason, and the model window "
                "button instead of the switch"),

    # --- `/pal` in the composer (P8) --------------------------------------

    Screen("readvisor-pal-hint", "project",
           setup=(("eval", "rvSetState('open')"), PAL_HINT, ("wait_idle", "")),
           teardown=PAL_HINT_BACK + RV_BACK,
           note="the `/pal` hint row, gate CLOSED — the scratch world has "
                "`local models only` on and no key, so this is the real "
                "greyed row carrying the real reason"),

    Screen("readvisor-pal-hint-open", "project",
           setup=(("eval", "rvSetState('open')"), PAL_HINT_OPEN,
                  ("wait_idle", "")),
           teardown=PAL_HINT_BACK + RV_BACK,
           note="the same row with the gate open and a model named — the "
                "status body is seeded (see PAL_HINT_OPEN); the row is the "
                "product's"),

    Screen("readvisor-pal-bubbles", "project",
           setup=(("eval", "rvSetState('open')"), PAL_BUBBLES,
                  ("wait_for", ".msg.pal"), ("wait_idle", "")),
           teardown=PAL_BUBBLES_BACK + RV_BACK,
           note="one pal exchange: what left this machine, then what came "
                "back"),

    Screen("readvisor-and-minis", "project",
           setup=(("eval", "rvSetState('open')"),
                  ("eval", f"openReadEdit('{DOC}', {{size:'mini', face:'read'}})"),
                  ("wait_for", "#preview.open"),
                  _docs("help-center"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, ("eval", "docsToggleSize()"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES + RV_BACK,
           note="both mini panels dock INSIDE main, left of the panel"),

    # --- convert's twin chrome (P3) ---------------------------------------
    #
    # There is no PDF and no twin in the scratch world, so the chips are
    # revealed rather than produced: `convertPaintChips()` needs a
    # CONVERT_DOC, and a fixture PDF per matrix cell is not worth it. What
    # the layout probes are looking at is the chip's own row — it joins an
    # already-crowded toolbar, and that is where it clips.
    Screen("convert-chip-review", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"),
                  ("eval", "(() => { const c = document.getElementById("
                           "'convert-chip-review'); if (!c) return false;"
                           " c.hidden = false;"
                           " c.querySelectorAll('.cc-btn').forEach((b) =>"
                           "  { b.hidden = false; });"
                           " c.querySelector('[data-cc=\"name\"]').textContent ="
                           "  'a-scanned-report.pdf';"
                           " c.querySelector('[data-cc=\"twin\"]').textContent ="
                           "  '· a-scanned-report.md'; return true; })()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("convert-chip-edit", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'edit'}})"),
                  ("wait_for", "#edit-mode.open"),
                  ("eval", "(() => { const c = document.getElementById("
                           "'convert-chip-edit'); if (!c) return false;"
                           " c.hidden = false;"
                           " c.querySelectorAll('.cc-btn').forEach((b) =>"
                           "  { b.hidden = false; });"
                           " c.querySelector('[data-cc=\"name\"]').textContent ="
                           "  'a-scanned-report.pdf';"
                           " c.querySelector('[data-cc=\"twin\"]').textContent ="
                           "  '· a-scanned-report.md'; return true; })()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("convert-chip-mini", "project",
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'mini', face:'read'}})"),
                  ("wait_for", "#preview.open"),
                  ("eval", "(() => { const c = document.getElementById("
                           "'convert-chip-mini'); if (!c) return false;"
                           " c.hidden = false;"
                           " c.querySelectorAll('.cc-btn').forEach((b) =>"
                           "  { b.hidden = false; });"
                           " c.querySelector('[data-cc=\"name\"]').textContent ="
                           "  'report.pdf'; return true; })()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    # --- the bare stage, and the narrow stage (P3 + P4c-1) ----------------
    Screen("composure-stage", "project",
           # "the stage after the last mode closes": a mode is pushed and
           # then exited through its own ribbon, which is the way a user
           # gets back here and the way that runs the mode's `onExit`.
           setup=(("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"))
                 + EXIT_ALL_MODES
                 + (("wait_gone", "#mode-stack .mode-indicator[data-mode=\"readedit\"]"),
                    ("wait_idle", "")),
           note="the empty stack: the canvas, and only the base indicator"),

    Screen("composure-narrow", "project",
           # `.comp-narrow` is what the stage becomes when both side panels
           # are open and there is not much left — the matrix's 1024x640 and
           # 1080x1920 are where it actually appears.
           setup=(("eval", "rvSetState('open'); compPanelChanged()"),
                  ("wait_idle", "")),
           teardown=RV_BACK,
           note="both panels open on a small screen; the toolbar folds"),

    # --- a two-deep stack, which is where indicator layout gets interesting -
    Screen("stacked-two-modes", "project",
           setup=(("eval", f"enterGirraphMode('{GIRRAPH}')"),
                  ("wait_for", "#girraph-mode.open"),
                  ("eval", f"openReadEdit('{DOC}', {{size:'full', face:'read'}})"),
                  ("wait_for", "#review-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    # --- agent-free mode (0.4.4, plan §13) ---------------------------------
    Screen("ui-modal-agentfree", "project",
           setup=(AF_ON, ("wait_for", "html[data-agent-free]"),
                  ("eval", "openUIModal()"),
                  ("wait_for", "#ui-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), AF_OFF, ("wait_idle", "")),
           note="the slider on (\"agent free\"), the readvisor keyboard rows gone"),

    Screen("project-agentfree", "project",
           setup=(AF_ON, ("wait_for", "html[data-agent-free]"),
                  SIDEBAR_SETTLED, ("wait_idle", "")),
           teardown=(AF_OFF, ("wait_idle", "")),
           note="the panel collapsed and its toggle gone, the sidebar down to "
                "the project tree, the badge saying the state word"),

    Screen("model-modal-agentfree", "project",
           setup=(AF_ON, ("wait_for", "html[data-agent-free]"),
                  ("eval", "openModelModal()"),
                  ("wait_for", "#model-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), AF_OFF, ("wait_idle", "")),
           note="the mirrored slider and its reason; switch, ctx, auto-reset "
                "greyed; download and delete live"),

    Screen("canon-ingest-agentfree", "project",
           setup=(AF_ON, ("wait_for", "html[data-agent-free]"),
                  ("eval", "enterCanonMode()"), ("wait_for", "#canon-mode.open"),
                  CANON_INGEST_URL,
                  ("wait_for", "#confirm-overlay:not([hidden])"), ("wait_idle", "")),
           teardown=(("click", "#confirm-cancel"),
                     ("wait_gone", "#confirm-overlay:not([hidden])"), AF_OFF)
                    + EXIT_ALL_MODES,
           note="the plain confirmation: source, volume, depth, the url cap "
                "and the fetch gate (the longest one there is)"),
]


# ---------------------------------------------------------------------------
# Home-mode screens
# ---------------------------------------------------------------------------

HOME_SCREENS: list[Screen] = [
    Screen("home-list", "home",
           setup=(("eval", "homeSetView('list')"),
                  ("wait_idle", "")),
           note="the registry table — two projects, so it is a real list"),

    Screen("home-icons", "home",
           setup=(("eval", "homeSetView('icons')"),
                  ("wait_idle", "")),
           teardown=(("eval", "homeSetView('list')"),
                     ("wait_idle", ""))),

    Screen("home-ui-modal", "home",
           setup=(("eval", "openUIModal()"),
                  ("wait_for", "#ui-modal:not(.hidden)"), ("wait_idle", "")),
           teardown=(_esc(), ("wait_idle", ""))),

    Screen("home-docs-spec", "home",
           setup=(_docs("macrocosm-oes"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the MacroCOSM spec from the home screen (/api/docs is "
                "home-accessible): the 0.4.3 home-cosmspec screen"),

    Screen("home-docs-fabula", "home",
           setup=(_docs("macrocosm-oes", "fabula", anchor="S:example/1"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_FAB_OK, DOCS_LIVE_OK,
                  ("wait_for", '#docs-body .docs-live[data-ready="ok"]'), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the fabula from the home screen on a live example: /api/docs and "
                "/api/cosm/inline are home-accessible (the wait fails when not)"),

    Screen("home-docs-thym", "home",
           setup=(("eval", "(() => { try { localStorage.removeItem('enough.docs.density.thym'); }"
                           " catch (e) {} return true; })()"),
                  ("eval", "openUIModal()"), ("wait_for", "#ui-modal:not(.hidden)"),
                  ("click", "#ui-thym-btn"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the Thym specification opened from the home screen's ui window, "
                "through its own button (0.5.0, X2; the wait fails when not)"),

    Screen("home-docs-help", "home",
           setup=(("eval", "openUIModal()"), ("wait_for", "#ui-modal:not(.hidden)"),
                  ("click", "#ui-help-center-btn"), ("wait_for", "#docs-mode.open"),
                  DOCS_READY, DOCS_SHORT_OK, ("wait_idle", "")),
           teardown=EXIT_ALL_MODES,
           note="the help center opened from the home screen's ui window, "
                "through its own button"),

    Screen("home-no-readvisor", "home",
           setup=(("wait_idle", ""),),
           note="P3: home has no readvisor at all — the toggle is display:none "
                "and the panel is visibility:hidden. Measured under its own "
                "name so a finding says which page lost it"),

    Screen("home-agentfree", "home",
           setup=(AF_ON, ("wait_for", "html[data-agent-free]"), ("wait_idle", "")),
           teardown=(AF_OFF, ("wait_idle", "")),
           note="0.4.4: the head's agent-free word (home has no model badge; "
                "the switch decides how a project opens)"),
]


ALL_SCREENS: list[Screen] = PROJECT_SCREENS + HOME_SCREENS


def screens_for(mode: str) -> list[Screen]:
    return [s for s in ALL_SCREENS if s.mode == mode]


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Viewport:
    w: int
    h: int
    dpr: float

    @property
    def name(self) -> str:
        return f"{self.w}x{self.h}@{self.dpr:g}"


# CSS px @ DPR. The spread is deliberate: the smallest laptop enough claims
# to run on, the two MacBook sizes, a 1080p and a 1440p external, a 21:9
# ultrawide (the one that finds "stretched to the full width" bugs), and a
# portrait orientation (the one that finds "assumed landscape" bugs).
VIEWPORTS: list[Viewport] = [
    Viewport(1024, 640, 1),
    Viewport(1280, 800, 2),
    Viewport(1512, 982, 2),
    Viewport(1728, 1117, 2),
    Viewport(1920, 1080, 1),
    Viewport(2560, 1440, 1),
    Viewport(3440, 1440, 1),
    Viewport(1080, 1920, 1),
]

# --quick: the two extremes plus the developer's own laptop. Enough to catch
# a layout regression in the 90 seconds a pre-commit hook is allowed.
QUICK_VIEWPORTS = (VIEWPORTS[0], VIEWPORTS[2], VIEWPORTS[6])

LANGUAGES = ("en", "fr", "es", "de", "zh", "ja")
QUICK_LANGUAGES = ("en", "de", "ja")

# Interaction scenarios run once per language at the reference viewport —
# they assert on DOM state, not on pixels, so repeating them per viewport
# would buy nothing but minutes.
INTERACTION_VIEWPORT = Viewport(1512, 982, 2)


def tauri_min_viewport(conf: dict) -> Viewport | None:
    """The Tauri window's configured minimum size, if it declares one.

    That size is a real constraint — it is the smallest the desktop app can
    ever be — so it belongs in the matrix. Today's tauri.conf.json declares
    no minimum and this returns None; the check stays because the day
    someone adds `minWidth` the harness should start covering it without
    anyone remembering to.
    """
    windows = ((conf.get("app") or {}).get("windows")
               or conf.get("windows") or [])
    for win in windows:
        mw, mh = win.get("minWidth"), win.get("minHeight")
        if mw and mh:
            return Viewport(int(mw), int(mh), 1)
    return None
