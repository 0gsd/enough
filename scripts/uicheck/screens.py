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

from dataclasses import dataclass

# The fixture file names seeded by server.seed_project().
DOC = "notes.md"
GIRRAPH = "map.girraph"
MERIRMAID = "diagram.merirmaid"
LONG_NAME = ("a-file-with-a-deliberately-very-long-name-that-the-sidebar-"
             "has-to-decide-how-to-truncate.md")

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
# and cacheawl all run one. Tearing a mode down the manager's way instead of
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
#: conclude wants a model, and this screen is about the collapsed footer.
COUNCIL_CONCLUDE: Step = ("eval", """(() => {
  const meta = (COMP_COUNCIL.state && COMP_COUNCIL.state.council)
    || (COMP.model && COMP.model.council);
  if (!meta) return false;
  meta.status = 'concluded';
  meta.round = meta.max_rounds;
  meta.transcript = 'rness/knowledge/councils/2026-09-17-the-decision.md';
  compCouncilRender();
  return true; })()""")


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


# ---------------------------------------------------------------------------
# Project-mode screens
# ---------------------------------------------------------------------------

PROJECT_SCREENS: list[Screen] = [
    Screen("project-base", "project",
           note="the ground floor: chat home, sidebar, top bar"),

    Screen("sidebar-hidden", "project",
           setup=(("click", "#toggle-sidebar"), ("wait_idle", "")),
           teardown=(("click", "#toggle-sidebar"), ("wait_idle", "")),
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

    Screen("cacheawl", "project",
           setup=(("eval", "enterCacheawlMode()"),
                  ("wait_for", "#cacheawl-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("ref-mode", "project",
           setup=(("eval", "enterRefMode()"),
                  ("wait_for", "#ref-mode.open"), ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

    Screen("ref-mini", "project",
           setup=(("eval", "enterRefMode()"), ("wait_for", "#ref-mode.open"),
                  ("eval", "refToggleSize()"),
                  ("wait_idle", "")),
           teardown=EXIT_ALL_MODES),

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
           note="the footer collapsed to the transcript line"),

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

    Screen("readvisor-and-minis", "project",
           setup=(("eval", "rvSetState('open')"),
                  ("eval", f"openReadEdit('{DOC}', {{size:'mini', face:'read'}})"),
                  ("wait_for", "#preview.open"),
                  ("eval", "enterRefMode()"), ("wait_for", "#ref-mode.open"),
                  ("eval", "refToggleSize()"), ("wait_idle", "")),
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

    Screen("home-no-readvisor", "home",
           setup=(("wait_idle", ""),),
           note="P3: home has no readvisor at all — the toggle is display:none "
                "and the panel is visibility:hidden. Measured under its own "
                "name so a finding says which page lost it"),
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
