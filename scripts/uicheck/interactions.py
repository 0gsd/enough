"""Mode-stack scenarios — the behaviour half of the browser stage.

The layout probes ask "does this screen look right". These ask the harder
question: "does the UI still *behave* the way the MODE STACK contract says
it does". Every scenario here is a sentence from that contract in
docs/AGENT_GUIDE.md ("Change the UI" → THE MODE STACK), turned into steps
with an assertion after each one:

* modes stack, they do not supplant — two pushes, two indicators,
  top-of-stack leftmost;
* raising a buried mode is z-order only, **never** a re-enter — so an
  unsaved edit in a buried editor is still there afterwards;
* esc targets `modeTop()` only, and is inert while a modal is open or the
  composer has focus;
* a buried entry's ribbon-redx closes *that* entry, at any depth;
* read/edit's mini ↔ full toggle keeps one live instance;
* the dirty guard fires before anything can discard unsaved work;
* the sidebar toggle is layout, not lifecycle — no open mode may notice it;
* `applyI18n()` round-trips: en → ja → en restores every English original
  byte for byte, because the engine memoizes into `data-i18n-src*`.

Each scenario returns a list of failure strings; empty means it held. They
run once per language at the reference viewport — the assertions are about
DOM state, not pixels, so repeating them per viewport would buy nothing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .driver import Driver, StepError
from .screens import CARDS_READY, DOC, GIRRAPH, JOURNAL_READY

Scenario = Callable[[Driver], list[str]]

DIRTY_MARK = "UICHECK-UNSAVED-EDIT"


def _reset(d: Driver) -> None:
    """Back to the ground floor without a reload, so a scenario failure
    cannot poison the next one."""
    # Through the indicators' own ribbons first, so each mode's `onExit`
    # runs and stops whatever it started; `modeRemove` is only the sweep-up.
    d.js("(() => { Array.from(document.querySelectorAll("
         "'#mode-stack .mode-indicator .mode-ribbon')).reverse()"
         ".forEach((b) => { try { b.click(); } catch (e) {} });"
         " ['readedit','girraph','merirmaid','wikisink','cacheawl','ref',"
         "'paginated','blobview'].forEach((n) => { try { modeRemove(n); } "
         "catch (e) {} }); return true; })()")
    d.js("(() => { document.querySelectorAll('[id$=\"-modal\"]').forEach("
         "(m) => m.classList.add('hidden'));"
         " document.getElementById('confirm-cancel')?.click();"
         " const c = document.getElementById('confirm-overlay');"
         " if (c) c.hidden = true; return true; })()")
    d.wait_idle()


def _names(d: Driver) -> list[str]:
    return [i["name"] for i in d.mode_stack()["indicators"]]


def _mine(d: Driver, resident: list[str]) -> list[str]:
    """The indicators this scenario opened, in indicator order.

    A scenario must not assert on the WHOLE stack. Some modes are resident
    — the composure round parks one on the stack for the life of the
    session — and a scenario that spells out the exact expected list goes
    red the day a later phase adds another. `resident` is whatever was
    standing after `_reset()`; everything else is the scenario's own doing,
    and that is what the MODE STACK contract is being tested against.
    """
    left = list(resident)
    out = []
    for name in _names(d):
        if name in left:
            left.remove(name)
        else:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_stack_order(d: Driver) -> list[str]:
    """Two pushes → two indicators, top-of-stack leftmost."""
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'read'}})")
    d.wait_for("#review-mode.open")
    d.wait_idle()

    state = d.mode_stack()
    names = _mine(d, resident)
    if names != ["readedit", "girraph"]:
        fails.append(f"indicator order is {names}, expected the top of the "
                     f"stack (readedit) leftmost: ['readedit', 'girraph'] "
                     f"(resident modes: {resident})")
    if state["top"] != "readedit":
        fails.append(f"modeTop() is {state['top']!r}, expected 'readedit'")
    if names[1:2] != ["girraph"] or any(
            i["buried"] is False and i["name"] == "girraph"
            for i in state["indicators"]):
        fails.append("girraph should be buried under readedit and marked so "
                     "(the top square is the inert one)")
    # Every STACK ENTRY is closable from its own square, even buried. The
    # composure round parks a permanent, ribbonless square at the right-hand
    # end for the base layer — composure is not a stack entry and cannot be
    # closed, only looked away from — so the invariant is about the entries,
    # not about every square in the bar.
    entries = {e["name"] for e in state["indicators"]
               if e["name"] in set(_names(d))} - {"composure"}
    for i in state["indicators"]:
        if i["name"] == "composure":
            if i["hasRibbon"]:
                fails.append("the composure base square has a ribbon-redx; "
                             "the base layer cannot be closed")
            continue
        if i["name"] in entries and not i["hasRibbon"]:
            fails.append(f"the {i['name']} indicator has no ribbon-redx; every "
                         f"stack entry must be closable from its own square, "
                         f"even buried")
    ribbonless = [i["name"] for i in state["indicators"] if not i["hasRibbon"]]
    if ribbonless not in ([], ["composure"]):
        fails.append(f"exactly one square may be ribbonless (the rightmost, "
                     f"composure's); found {ribbonless}")
    _reset(d)
    return fails


def scenario_raise_preserves_state(d: Driver) -> list[str]:
    """Clicking a buried indicator raises — it must never re-enter.

    The proof is an unsaved edit: `openReadEdit` reloads from disk, so if
    raising went through the enter path the marker would be gone.
    """
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'edit'}})")
    d.wait_for("#edit-mode.open .edit-textarea")
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         f" t.value = {DIRTY_MARK!r} + '\\n' + t.value;"
         " t.dispatchEvent(new Event('input', {bubbles: true})); return true; })()")
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.wait_idle()

    if _mine(d, resident)[:1] != ["girraph"]:
        fails.append(f"after pushing girraph the leftmost indicator is "
                     f"{_mine(d, resident)[:1]}, expected ['girraph']")

    raised = d.js("(() => { const sq = document.querySelector("
                  "'#mode-stack .mode-indicator[data-mode=\"readedit\"]');"
                  " if (!sq) return false; sq.click(); return true; })()")
    if not raised:
        return fails + ["no buried readedit indicator to click"]
    d.wait_idle()

    state = d.mode_stack()
    if state["top"] != "readedit":
        fails.append(f"clicking the buried readedit square left modeTop() = "
                     f"{state['top']!r}")
    if _mine(d, resident) != ["readedit", "girraph"]:
        fails.append(f"raising did not move readedit to the leftmost "
                     f"indicator: {_mine(d, resident)}")
    survived = d.js("(document.querySelector('#edit-mode .edit-textarea')||{})"
                    f".value?.indexOf({DIRTY_MARK!r}) === 0")
    if not survived:
        fails.append("the unsaved edit did not survive the raise — modeRaise() "
                     "re-entered the mode instead of just re-ordering it")

    # Leave no dirty editor behind for the next scenario's guards.
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         " if (t) { t.value = ''; t.dispatchEvent(new Event('input', {bubbles:true})); }"
         " return true; })()")
    _reset(d)
    return fails


def scenario_esc_closes_only_top(d: Driver) -> list[str]:
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js("enterRefMode()")
    d.wait_for("#ref-mode.open")
    d.wait_idle()

    d.key("Escape")
    d.wait_idle()
    names = _mine(d, resident)
    if names != ["girraph"]:
        fails.append(f"one esc left {names} of this scenario's modes open, "
                     f"expected only the top (ref) to close: ['girraph']")
    d.key("Escape")
    d.wait_idle()
    if _mine(d, resident):
        fails.append(f"a second esc left {_mine(d, resident)} standing; both "
                     f"of this scenario's modes should be gone")
    _reset(d)
    return fails


def scenario_esc_inert_under_modal_and_composer(d: Driver) -> list[str]:
    """Esc belongs to whoever owns it: a modal, or a focused text field."""
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")

    d.js("openUIModal()")
    d.wait_for("#ui-modal:not(.hidden)")
    d.wait_idle()
    d.key("Escape")
    d.wait_idle()
    if _mine(d, resident) != ["girraph"]:
        fails.append(f"esc with a modal open changed the stack to "
                     f"{_mine(d, resident)}; modals own esc for themselves "
                     f"(_escModalOpen)")
    if "ui-modal" in d.modals_open():
        fails.append("esc did not close the ui modal")

    composer = d.js("(() => { const el = document.querySelector("
                    "'#chat-form textarea, #chat-form input[type=text]');"
                    " if (!el) return null; el.focus(); return "
                    "document.activeElement === el; })()")
    if composer:
        d.key("Escape")
        d.wait_idle()
        if _mine(d, resident) != ["girraph"]:
            fails.append("esc while the composer had focus closed a mode; the "
                         "guard must keep esc out of text fields")
        # P6's decision: esc in the chat composer BLURS it rather than doing
        # nothing at all, so the rung below (rv-full → docked) is reachable
        # without the user having to click somewhere else first. The stack
        # must still be untouched — that is the assertion above.
        if d.js("document.activeElement && document.activeElement.id === "
                "'message'"):
            fails.append("esc in the chat composer did not blur it; the rungs "
                         "below it are unreachable while the caret is there")
        # …and the SECOND esc follows the normal order: the composer is no
        # longer focused, so it belongs to the top of the stack.
        d.key("Escape")
        d.wait_idle()
        if _mine(d, resident):
            fails.append(f"a second esc, after the composer blurred, left "
                         f"{_mine(d, resident)} standing; it should follow the "
                         f"normal order and close the top mode")
    _reset(d)
    return fails


def scenario_buried_ribbon_closes_that_entry(d: Driver) -> list[str]:
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js("enterRefMode()")
    d.wait_for("#ref-mode.open")
    d.wait_idle()

    clicked = d.js("(() => { const sq = document.querySelector("
                   "'#mode-stack .mode-indicator[data-mode=\"girraph\"]');"
                   " if (!sq) return false; const r = sq.querySelector('.mode-ribbon');"
                   " if (!r) return false; r.click(); return true; })()")
    if not clicked:
        return fails + ["the buried girraph indicator has no ribbon-redx"]
    d.wait_idle()
    names = _mine(d, resident)
    if names != ["ref"]:
        fails.append(f"closing the buried entry from its ribbon left {names}, "
                     f"expected ['ref'] — the ribbon must close THAT entry, "
                     f"not the top one")
    _reset(d)
    return fails


def scenario_mini_full_toggle(d: Driver) -> list[str]:
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"openReadEdit('{DOC}', {{size:'mini', face:'read'}})")
    d.wait_for("#preview.open")
    d.wait_idle()
    if _mine(d, resident).count("readedit") != 1:
        fails.append(f"opening read/edit mini gave indicators {_names(d)}; "
                     f"exactly one readedit entry is the contract")

    toggled = d.js("(() => { const b = document.querySelector("
                   "'#preview [data-icon=\"mini2full\"]')?.closest('button');"
                   " if (b) { b.click(); return 'button'; }"
                   " if (window.mini2full) { mini2full(); return 'fn'; }"
                   " return null; })()")
    d.wait_idle()
    if toggled is None:
        fails.append("found no mini→full affordance in the read/edit chrome")
    else:
        if _mine(d, resident).count("readedit") != 1:
            fails.append(f"after mini→full the indicators are {_names(d)}; the "
                         f"toggle must not push a second entry")
        if not d.exists("#review-mode.open, #review-mode:not(.hidden)"):
            fails.append("mini→full did not bring up the full frame")
    _reset(d)
    return fails


def scenario_dirty_guard(d: Driver) -> list[str]:
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'edit'}})")
    d.wait_for("#edit-mode.open .edit-textarea")
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         f" t.value = {DIRTY_MARK!r} + '\\n' + t.value;"
         " t.dispatchEvent(new Event('input', {bubbles: true})); return true; })()")
    d.wait_idle()

    # Close it the way the user would: the readedit indicator's ribbon.
    d.js("(() => { const sq = document.querySelector("
         "'#mode-stack .mode-indicator[data-mode=\"readedit\"]');"
         " sq?.querySelector('.mode-ribbon')?.click(); return true; })()")
    try:
        d.wait_for("#confirm-overlay:not([hidden])", timeout=5)
    except StepError:
        fails.append("closing a dirty editor raised no confirm overlay — the "
                     "dirty guard is the only thing between a stray click and "
                     "an hour of lost work")
    else:
        d.js("document.getElementById('confirm-cancel')?.click()")
        d.wait_idle()
        if "readedit" not in _names(d):
            fails.append("cancelling the dirty-guard confirm still closed the "
                         "editor")
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         " if (t) { t.value = ''; t.dispatchEvent(new Event('input', {bubbles:true})); }"
         " return true; })()")
    _reset(d)
    return fails


def scenario_sidebar_toggle_is_layout_only(d: Driver) -> list[str]:
    fails: list[str] = []
    _reset(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'read'}})")
    d.wait_for("#review-mode.open")
    d.wait_idle()
    before = _names(d)

    d.click("#toggle-sidebar")
    d.wait_idle()
    collapsed = d.js("!!document.querySelector('.layout.sidebar-collapsed')")
    if not collapsed:
        fails.append("#toggle-sidebar did not put .sidebar-collapsed on .layout")
    if _names(d) != before:
        fails.append(f"toggling the sidebar changed the mode stack: {before} → "
                     f"{_names(d)}; it is layout, not lifecycle")
    d.click("#toggle-sidebar")
    d.wait_idle()
    if d.js("!!document.querySelector('.layout.sidebar-collapsed')"):
        fails.append("#toggle-sidebar did not restore the sidebar")
    if _names(d) != before:
        fails.append("restoring the sidebar changed the mode stack")
    _reset(d)
    return fails


def scenario_language_roundtrip(d: Driver) -> list[str]:
    """Switching away and back must restore every `[data-i18n]` element.

    `applyI18n()` memoizes each element's original text into a
    `data-i18n-src*` attribute on first application, which is the only
    reason a live switch can be lossless. If the memo ever stops covering a
    target, this is where it shows up — and in the product it shows up as a
    label stuck in the wrong language until the page is reloaded.

    The starting language is whatever the matrix pass is running in, NOT
    English: the harness flips the whole run's language through
    `POST /api/ui-config`, so hard-coding `en` here would compare German to
    English and call it a regression.
    """
    fails: list[str] = []
    _reset(d)
    start = d.js("I18N.lang") or "en"
    other = "ja" if start != "ja" else "de"
    original = d.i18n_snapshot()
    try:
        d.js(f"setUILanguage({other!r})")
        d.wait_for(f"html[lang={other}]", timeout=10)
        d.wait_idle()
        switched = d.i18n_snapshot()
        changed = sum(1 for k, v in switched.items() if original.get(k) != v)
        if changed == 0:
            fails.append(f"switching {start} → {other} changed no [data-i18n] "
                         f"text at all — the catalog is not being applied")
    finally:
        # Whatever happened, do not leave the scratch config in the wrong
        # language for the (screen, viewport) passes that follow.
        d.js(f"setUILanguage({start!r})")
        try:
            d.wait_for(f"html[lang={start}]", timeout=10)
        except StepError:
            pass
        d.wait_idle()

    back = d.i18n_snapshot()
    lost = [k for k, v in original.items() if back.get(k) != v]
    if lost:
        sample = ", ".join(f"{k.rsplit('#', 1)[0]}: {original[k]!r} → "
                           f"{back.get(k)!r}" for k in lost[:4])
        fails.append(f"{len(lost)} [data-i18n] element(s) did not round-trip "
                     f"back to {start}: {sample}")
    return fails


# ---------------------------------------------------------------------------
# The readvisor panel (P3's four scenarios, wired in P6c)
# ---------------------------------------------------------------------------
#
# P3 landed the panel and wrote these four down for whoever owned the
# harness; nobody did, so the four claims the panel makes have never been
# checked by anything but a human. They are, in P3's words: the panel PUSHES
# rather than covers while it is docked; raising a mode from `rv-full` is a
# re-order and never a re-enter; esc has a ladder and the panel sits on a
# known rung of it; and the two mini panels live INSIDE main.

def _rv(d: Driver) -> str:
    return d.js("document.documentElement.dataset.rv") or "closed"


def scenario_rv_docked_pushes(d: Driver) -> list[str]:
    """A docked panel takes width from the stage — it does not sit on top.

    The proof is the probe the layout half already uses: with the panel
    docked and two modes stacked, NOTHING may be covered by something in its
    own layer. A panel that overlapped would show up here as a pile of
    covered toolbar buttons rather than as a screenshot somebody squints at.
    """
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    d.wait_idle()
    resident = _names(d)
    d.js(f"openReadEdit('{DOC}', {{size: 'full', face: 'read'}})")
    d.wait_for("#review-mode.open")
    d.js("enterCacheawlMode()")
    d.wait_for("#cacheawl-mode.open")
    d.wait_idle()

    mine = _mine(d, resident)
    if mine != ["cacheawl", "readedit"]:
        fails.append(f"two pushes gave indicators {mine}, expected "
                     f"['cacheawl', 'readedit']")
    if _rv(d) != "open":
        fails.append(f"opening two modes changed the panel state to {_rv(d)!r}")
    items = d.js("window.__uicheck.clickables()") or []
    covered = [i["path"] for i in items
               if i.get("inView") and not i.get("hitSelf") and i.get("coveredBy")
               and i.get("layer") == i.get("coveredByLayer")
               and not i["path"].endswith(".modal-backdrop")]
    if covered:
        fails.append(f"{len(covered)} clickable(s) are covered inside their own "
                     f"layer with the panel docked: {covered[:6]}")
    _reset(d)
    d.js("rvSetState('open')")
    return fails


def scenario_rv_full_indicator_restores(d: Driver) -> list[str]:
    """Clicking an indicator while `rv-full` drops the panel AND raises.

    The mode-stack contract says the top square is inert — this is its one
    documented exception, and it has to be a raise, never a re-enter, so an
    unsaved edit and even the scroll position survive it.
    """
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    resident = _names(d)
    d.js(f"openReadEdit('{DOC}', {{size: 'full', face: 'edit'}})")
    d.wait_for("#edit-mode.open .edit-textarea")
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         f" t.value = {DIRTY_MARK!r} + '\\n' + t.value;"
         " t.dispatchEvent(new Event('input', {bubbles: true}));"
         " t.scrollTop = 40; return true; })()")
    before = d.js("(() => { const t = document.querySelector("
                  "'#edit-mode .edit-textarea');"
                  " return {v: t.value.length, top: t.scrollTop}; })()")
    d.js("rvSetState('full')")
    d.wait_idle()
    if _rv(d) != "full":
        fails.append(f"rvSetState('full') left the panel at {_rv(d)!r}")

    clicked = d.js("(() => { const sq = document.querySelector("
                   "'#mode-stack .mode-indicator'); if (!sq) return false;"
                   " sq.click(); return true; })()")
    d.wait_idle()
    if not clicked:
        fails.append("there was no indicator to click")
    elif _rv(d) != "open":
        fails.append(f"clicking an indicator under rv-full left the panel at "
                     f"{_rv(d)!r}; it must drop to docked")
    after = d.js("(() => { const t = document.querySelector("
                 "'#edit-mode .edit-textarea'); if (!t) return null;"
                 " return {v: t.value.length, top: t.scrollTop}; })()")
    if after != before:
        fails.append(f"the editor did not survive the drop-and-raise: "
                     f"{before} → {after}; that is a re-enter, not a re-order")
    if "readedit" not in _names(d):
        fails.append("the readedit entry left the stack")
    d.js("(() => { const t = document.querySelector('#edit-mode .edit-textarea');"
         " if (t) { t.value = ''; t.dispatchEvent(new Event('input',"
         " {bubbles: true})); } return true; })()")
    _reset(d)
    d.js("rvSetState('open')")
    return fails


def scenario_rv_esc_ladder(d: Driver) -> list[str]:
    """The whole esc ladder, in order, including P6's new rung.

    1. a modal owns esc, and nothing under it moves;
    2. a focused chat composer BLURS (P6's decision — it used to be inert,
       which made rung 3 unreachable, because the panel focuses the composer
       whenever it opens);
    3. `rv-full` drops to docked;
    4. the top of the mode stack closes;
    5. a DOCKED panel is never closed by esc — it is a place you live in.
    """
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    resident = _names(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js("rvSetState('full')")
    d.wait_idle()

    # 1. a modal outranks everything.
    d.js("openUIModal()")
    d.wait_for("#ui-modal:not(.hidden)")
    d.key("Escape")
    d.wait_idle()
    if _rv(d) != "full" or _mine(d, resident) != ["girraph"]:
        fails.append(f"esc with a modal open moved the ladder: rv={_rv(d)!r}, "
                     f"modes={_mine(d, resident)}")

    # 2. the composer blurs, and NOTHING else moves.
    focused = d.js("(() => { const el = document.getElementById('message');"
                   " if (!el) return false; el.focus();"
                   " return document.activeElement === el; })()")
    if not focused:
        return fails + ["could not focus the chat composer"]
    d.key("Escape")
    d.wait_idle()
    if d.js("document.activeElement && document.activeElement.id === 'message'"):
        fails.append("esc in the composer did not blur it")
    if _rv(d) != "full":
        fails.append(f"esc in the composer also dropped the panel to "
                     f"{_rv(d)!r}; blurring is the whole of that rung")
    if _mine(d, resident) != ["girraph"]:
        fails.append("esc in the composer closed a mode")

    # 3. …and now the same key reaches rv-full.
    d.key("Escape")
    d.wait_idle()
    if _rv(d) != "open":
        fails.append(f"a second esc did not drop rv-full to docked "
                     f"({_rv(d)!r}) — the rung P3 flagged as unreachable")

    # 4. the top of the stack, and 5. never the docked panel.
    d.key("Escape")
    d.wait_idle()
    if _mine(d, resident):
        fails.append(f"esc did not close the top mode: {_mine(d, resident)}")
    if _rv(d) != "open":
        fails.append(f"esc closed the DOCKED panel ({_rv(d)!r}); a docked "
                     f"panel is a place you live in, not a thing you dismiss")
    _reset(d)
    d.js("rvSetState('open')")
    return fails


def scenario_rv_minis_inside_main(d: Driver) -> list[str]:
    """Both mini panels dock inside main, to the LEFT of the panel."""
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    d.wait_idle()
    d.js(f"openReadEdit('{DOC}', {{size: 'mini', face: 'read'}})")
    d.wait_for("#preview.open")
    d.js("enterRefMode()")
    d.wait_for("#ref-mode.open")
    d.js("refToggleSize()")
    d.wait_idle()

    rects = d.js("(() => { const r = (s) => { const e ="
                 " document.querySelector(s); if (!e) return null;"
                 " const b = e.getBoundingClientRect();"
                 " return {left: b.left, right: b.right, w: b.width}; };"
                 " return {panel: r('#readvisor-panel'), mini: r('#preview'),"
                 "  ref: r('#ref-mode')}; })()") or {}
    panel = rects.get("panel")
    if not panel or not panel["w"]:
        fails.append(f"the readvisor panel has no box to be left of: {panel}")
    else:
        for name in ("mini", "ref"):
            box = rects.get(name)
            if not box or not box["w"]:
                fails.append(f"#{name} is not on screen: {box}")
            elif box["right"] > panel["left"] + 2:
                fails.append(f"{name} ends at {box['right']:.0f}, past the "
                             f"panel's left edge at {panel['left']:.0f} — the "
                             f"minis dock INSIDE main")
    _reset(d)
    d.js("rvSetState('open')")
    return fails


# ---------------------------------------------------------------------------
# The composure canvas (composure round, P4c-1 + P4c-2)
# ---------------------------------------------------------------------------
#
# These assert on the MODEL and the DOM, not on pixels, and they drive the
# canvas through its own entry points — `compOpenNew`, `compDo`, the real
# keyboard — for the same reason the mode-stack scenarios do: a harness that
# reaches past the product's functions ends up testing itself.

def _comp_blank(d: Driver) -> None:
    """Back to a blank composure, with nothing queued."""
    d.js("compToggleComments(false); compCloseMenus(); compSearchClear(true);"
         " compSetInkSelection(null); compSetMode('view');"
         " compSetTool('pointer'); compSetSelection([]); compOpenNew('blank')")
    d.wait_idle()


def scenario_composure_input_rules(d: Driver) -> list[str]:
    """A markdown input rule converts a line at its predecessor's level.

    The regression this pins: typing `1. ` on the line after a bullet used
    to produce `<ul><li>bullet</li><ol>…</ol></ul>` — an ordered list
    nested inside an unordered one with no `<li>` around it, which is
    invalid HTML and a shape the markdown round trip cannot describe.
    """
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js("compSetMode('edit'); compSetTool('text'); compFocusFirstText()")
    d.wait_for(".comp-page[contenteditable]")
    d.js("compEl('comp-modules').querySelector('.comp-page[contenteditable]')"
         ".focus()")
    # One insertText per character: an input rule fires when the block's
    # whole text IS the marker, so the events have to arrive one at a time.
    for ch in "- bullet":
        d.type_text(ch)
    d.key("Enter")
    for ch in "1. numbered":
        d.type_text(ch)
    d.wait_idle()
    rich = (d.js("COMP.model.modules[0].pages[0].rich") or "").replace("\n", "")
    if "<ul><li>bullet</li></ul><ol><li>numbered</li></ol>" not in rich:
        fails.append(f"the ordered list is not a sibling of the bullet list: "
                     f"{rich!r}")
    if "<ul><li>bullet</li><ol" in rich:
        fails.append(f"an <ol> is nested directly inside the <ul>: {rich!r}")
    # Enter on an EMPTY item leaves the list.
    d.key("Enter")
    d.key("Enter")
    for ch in "plain":
        d.type_text(ch)
    d.wait_idle()
    rich = (d.js("COMP.model.modules[0].pages[0].rich") or "").replace("\n", "")
    if not rich.rstrip().endswith("<p>plain</p>"):
        fails.append(f"Enter on an empty item did not leave the list: {rich!r}")
    # Tab nests, shift+Tab pulls back out.
    d.key("Enter")
    for ch in "- a":
        d.type_text(ch)
    d.key("Enter")
    d.type_text("b")
    d.key("Tab")
    d.wait_idle()
    rich = (d.js("COMP.model.modules[0].pages[0].rich") or "").replace("\n", "")
    if "<ul><li>a<ul><li>b</li></ul></li></ul>" not in rich:
        fails.append(f"Tab did not nest the item under its predecessor: {rich!r}")
    _comp_blank(d)
    _reset(d)
    return fails


def scenario_composure_ink(d: Driver) -> list[str]:
    """A stroke, an erase that splits it, and an undo that puts it back."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('cards')")
    d.wait_for(CARDS_READY[1])
    d.js("compSetMode('edit'); compSetTool('pencil')")
    d.js("compDo({ops: [{op: 'add_strokes', strokes: [{id: 'suicheckink',"
         " color: 'ink', width: 2, points: [[0,0],[20,0],[40,0],[60,0],"
         "[80,0],[100,0],[120,0]]}]}], undo: [{op: 'remove_strokes',"
         " ids: ['suicheckink']}]})")
    d.wait_idle()
    n0 = d.js("(COMP.model.strokes[0] || {points: []}).points.length")
    if n0 != 7:
        fails.append(f"the seeded stroke has {n0} points, expected 7")
    # The eraser's own gesture, start to finish. P5c changed what it does:
    # it clips SEGMENTS against the circle rather than dropping points, so
    # each surviving run ends (or starts) at the circle's own boundary. On
    # this stroke — 7 points 20 apart, circle r=12 at x=60 — the point at 60
    # goes and the two segments either side are cut at x=48 and x=72, so the
    # two runs are 4 points each: 6 survivors plus 2 boundary points.
    d.js("(() => { const strokes = COMP.model.strokes;"
         " COMP.drag = {kind: 'erase', changed: false,"
         "  orig: new Map(strokes.map((s) => [s.id, compStrokeSnapshot(s)]))};"
         " COMP.drag.changed = compEraseAt({x: 60, y: 0}, 12);"
         " const d = COMP.drag; COMP.drag = null; compFinishErase(d);"
         " return true; })()")
    d.wait_idle()
    after = d.js("COMP.model.strokes.map((s) => ({id: s.id,"
                 " n: s.points.length}))") or []
    if any(s["id"] == "suicheckink" for s in after):
        fails.append("the erased stroke's id survived the split")
    if len(after) != 2:
        fails.append(f"the erase left {len(after)} polylines, expected 2: {after}")
    elif sum(s["n"] for s in after) != 8:
        fails.append(f"point counts do not add up: {after} (7 points, one "
                     f"inside the circle and two segments cut at its edge, "
                     f"so 6 + 2 = 8 should survive)")
    elif any(s["n"] < 2 for s in after):
        fails.append(f"a surviving run has fewer than 2 points: {after}")
    else:
        edges = d.js("COMP.model.strokes.map((s) => [s.points[0][0],"
                     " s.points[s.points.length - 1][0]])") or []
        want = [[0.0, 48.0], [72.0, 120.0]]
        got = sorted([float(a), float(b)] for a, b in edges)
        if any(abs(g - w) > 0.2 for pair, wp in zip(got, want)
               for g, w in zip(pair, wp)):
            fails.append(f"the cut is not at the circle's edge: {got}, "
                         f"expected {want}")
    d.js("compUndo()")
    d.wait_idle()
    back = d.js("COMP.model.strokes.map((s) => ({id: s.id,"
                " n: s.points.length}))") or []
    if back != [{"id": "suicheckink", "n": 7}]:
        fails.append(f"undo did not restore the whole stroke: {back}")
    # The arrowhead's hard corners, as the renderer reads them.
    runs = d.js("compInkRuns([[0,0],[40,0],[40,0],[30,6],[30,6],[40,0],"
                "[40,0],[30,-6]]).length")
    if runs != 4:
        fails.append(f"an arrow's doubled points split into {runs} runs, "
                     f"expected 4 (shaft, barb, retrace, barb)")
    _comp_blank(d)
    _reset(d)
    return fails


def scenario_composure_search(d: Driver) -> list[str]:
    """Search is composure-wide, and jumping turns the page."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('cards')")
    d.wait_for(CARDS_READY[1])
    d.js("(() => { const ids = COMP.model.modules.slice(0, 2).map((m) => m.id);"
         " compDo({ops: [{op: 'set_page', module: ids[0], n: 1,"
         "  rich: '<p>alpha needle one</p>'},"
         " {op: 'set_page', module: ids[1], n: 1, rich: '<p>beta</p>'},"
         " {op: 'add_page', module: ids[1], n: 2,"
         "  rich: '<p>gamma needle two</p>'}], undo: []});"
         " compSetSelection([]); return true; })()")
    d.wait_idle()
    d.focus("#comp-search")
    for ch in "needle":
        d.type_text(ch)
    # The field debounces by 160ms before it searches, and `wait_idle` is
    # two settled frames — which can easily be less than that. Poll the
    # state the keystrokes are supposed to produce instead of guessing.
    for _ in range(40):
        if d.js("!!(COMP.search && COMP.search.q === 'needle')"):
            break
        d.wait_idle()
    hits = d.js("COMP.search ? COMP.search.hits.length : 0")
    if hits != 2:
        fails.append(f"search found {hits} hits across two modules and three "
                     f"pages, expected 2")
    d.key("Enter")
    d.key("Enter")
    d.wait_idle()
    turned = d.js("(() => { const h = COMP.search.hits[COMP.search.i];"
                  " return compModuleById(h.id).cur === h.n; })()")
    if not turned:
        fails.append("jumping to a hit on another page did not turn to it")
    d.key("Escape")
    d.wait_idle()
    if d.js("COMP.search !== null"):
        fails.append("esc in the search field did not clear the query")
    _comp_blank(d)
    _reset(d)
    return fails


def scenario_composure_journal(d: Driver) -> list[str]:
    """Today's page exists in memory until it is typed into."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('journal')")
    d.wait_for(JOURNAL_READY[1])
    state = d.js("({journal: COMP.journal, path: COMP.path, mode: COMP.mode,"
                 " tool: COMP.tool,"
                 " dated: !!compCurPage(compModuleById(COMP.journal.module)).date,"
                 " caret: !!compEl('comp-modules')"
                 "  .querySelector('.comp-page[contenteditable]')})")
    if not state["dated"]:
        fails.append("the journal did not land on a page stamped today")
    if state["mode"] != "edit" or state["tool"] != "text" or not state["caret"]:
        fails.append(f"the journal did not open with the caret ready: {state}")
    if state["path"]:
        fails.append(f"an untouched journal wrote a file: {state['path']}")
    if d.js("COMP.pending.length") != 0:
        fails.append("an untouched journal queued an op")
    _comp_blank(d)
    _reset(d)
    return fails


def scenario_composure_comments(d: Driver) -> list[str]:
    """A quote anchor is marked once, however often it is re-rendered."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('cards')")
    d.wait_for(CARDS_READY[1])
    # The slider first: toggling it on reloads the sidecar, which would
    # wipe the fixture comment set below.
    d.js("compToggleComments(true)")
    d.wait_idle()
    d.js("(() => { const id = COMP.model.modules[0].id;"
         " compDo({ops: [{op: 'set_page', module: id, n: 1,"
         "  rich: '<p>the quick brown fox</p>'}], undo: []});"
         " COMP.comments = [{id: 'c_uicheck', body: 'why?',"
         "  created_at: '2026-09-17T10:00:00Z', resolved: false, replies: [],"
         "  anchor: {type: 'quote', module: id, page: 1, quote: 'brown fox'},"
         "  state: 'anchored'}];"
         " compRenderComments(); return true; })()")
    d.wait_for("#comp-comments-list .wiki-comment-card")
    marks = d.js("document.querySelectorAll('.comp-comment-mark').length")
    if marks != 1:
        fails.append(f"the quote is marked {marks} times, expected once")
    # Re-render twice more: marking must be idempotent, or every repaint
    # wraps the wrapper and the marks multiply.
    d.js("compRenderComments(); compRenderComments()")
    d.wait_idle()
    marks = d.js("document.querySelectorAll('.comp-comment-mark').length")
    if marks != 1:
        fails.append(f"after two more renders the quote is marked {marks} "
                     f"times; marking is not idempotent")
    cards = d.js("document.querySelectorAll("
                 "'#comp-comments-list .wiki-comment-card').length")
    if cards != 1:
        fails.append(f"the slider shows {cards} cards, expected 1")
    if not d.js("!!document.querySelector('#comp-comments-list .c-actions "
                "button[data-act=\"resolve\"]')"):
        fails.append("the shared comment card lost its actions row")
    d.js("COMP.comments = []; compToggleComments(false); compRenderComments()")
    _comp_blank(d)
    _reset(d)
    return fails


def scenario_composure_selection_shape(d: Driver) -> list[str]:
    """One shape, one renderer — for the canvas and for a document alike."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js("compSetMode('edit'); compSetTool('text'); compFocusFirstText()")
    d.wait_for(".comp-page[contenteditable]")
    d.js("compEl('comp-modules').querySelector('.comp-page[contenteditable]')"
         ".focus()")
    d.type_text("a sentence to select from")
    d.wait_idle()
    d.js("(() => { const host = compEl('comp-modules').querySelector('.comp-page');"
         " const walk = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);"
         " const n = walk.nextNode(); if (!n) return false;"
         " const r = document.createRange(); r.setStart(n, 2); r.setEnd(n, 10);"
         " const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);"
         " compCaptureSelection(); return true; })()")
    d.js("rvSetState('open')")
    d.wait_idle()
    sel = d.js("rvPendingSelection()")
    if not sel or sel.get("source") != "composure":
        fails.append(f"the canvas does not answer with the shared selection "
                     f"shape: {sel}")
    else:
        for field in ("name", "locator", "text"):
            if not sel.get(field):
                fails.append(f"the selection shape is missing {field!r}: {sel}")
        # "names the page" = carries the page number and the page count.
        # NOT the English word "page", and not an `n/N` either: the phrase
        # is translated, connector and all, so this ran red against
        # 'm1 · seite 1/1' (de) and then against 'm1 · page 1 sur 1' (fr).
        # The numbers are the only part every catalog renders the same. (P6c)
        pages = d.js("(() => { const m = compModuleById(COMP.sel[0])"
                     "  || COMP.model.modules[0];"
                     " return {n: m.cur, of: m.page_count}; })()") or {}
        want = [str(pages.get("n", "?")), str(pages.get("of", "?"))]
        if not all(n in (sel.get("locator") or "") for n in want):
            fails.append(f"the locator does not name the page ({want[0]} of "
                         f"{want[1]}): {sel['locator']!r}")
    shown = d.js("rvRenderSelection(rvPendingSelection())")
    if not shown or not shown.get("preamble", "").startswith(
            "[selection · composure · "):
        fails.append(f"the one renderer did not make the preamble: {shown}")
    chip = d.js("document.getElementById('rv-chip-where').textContent")
    if shown and chip != shown.get("label"):
        fails.append(f"the chip says {chip!r}, the renderer says "
                     f"{shown.get('label')!r}")
    # A document selection goes through the SAME renderer.
    d.js(f"openReadEdit('{DOC}', {{size: 'full', face: 'read'}})")
    d.wait_for("#review-mode.open")
    d.js("(() => { const body = document.querySelector('#review-mode .review-body');"
         " if (!body) return false;"
         " const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);"
         " let n = null;"
         " for (let x = walk.nextNode(); x; x = walk.nextNode()) {"
         "  if ((x.textContent || '').trim().length > 20) { n = x; break; } }"
         " if (!n) return false;"
         " const r = document.createRange(); r.setStart(n, 0); r.setEnd(n, 12);"
         " const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);"
         " if (typeof captureLastReviewSelection === 'function')"
         "  captureLastReviewSelection();"
         " return true; })()")
    d.wait_idle()
    dsel = d.js("rvPendingSelection()")
    if not dsel or dsel.get("source") != "doc":
        fails.append(f"the document mode does not answer with the shared "
                     f"shape: {dsel}")
    dshown = d.js("rvRenderSelection(rvPendingSelection())")
    if not dshown or not dshown.get("preamble", "").startswith(
            "[selection · doc · "):
        fails.append(f"the document's preamble is not the one renderer's: "
                     f"{dshown}")
    _reset(d)
    _comp_blank(d)
    return fails


def scenario_composure_council_pins_panel(d: Driver) -> list[str]:
    """P3's interplay #8, now that a council can actually be opened."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js("rvSetState('open')")
    d.wait_idle()
    d.js_await("compOpenNew('council')")
    d.wait_idle()
    if d.js("document.documentElement.dataset.rv") != "closed":
        fails.append("a council on the stage did not close the readvisor panel")
    if not d.js("document.getElementById('toggle-readvisor').disabled"):
        fails.append("…and did not disable its toggle")
    d.js("rvToggle()")
    d.wait_idle()
    if d.js("document.documentElement.dataset.rv") != "closed":
        fails.append("the toggle was not inert while a council held the stage")
    d.js_await("compOpenNew('blank')")
    d.wait_idle()
    if d.js("document.documentElement.dataset.rv") == "closed":
        fails.append("leaving the council did not restore the panel")
    if d.js("document.getElementById('toggle-readvisor').disabled"):
        fails.append("…and left its toggle disabled")
    _comp_blank(d)
    _reset(d)
    return fails


#: The suite has no model, and it does not need one: `POST /api/council/setup`
#: writes the meta and runs no turn, so every control's enabled/disabled state
#: and every 409 sentence can be driven on a real council file.
_SUITE_COUNCIL = "rness/io/composure/suite-council.comp"


def _council_open(d: Driver, **body) -> None:
    payload = {"path": _SUITE_COUNCIL, "title": "The decision",
               "input": "Should chapter four move to the front?",
               "output": {"kind": "answer"}, "max_rounds": 3}
    payload.update(body)
    d.js_await(
        "(async () => { await fetch('/api/council/setup', {method: 'POST',"
        " headers: {'Content-Type': 'application/json'},"
        f" body: JSON.stringify({json.dumps(payload)})}});"
        f" await compOpenPath({_SUITE_COUNCIL!r});"
        " for (let i = 0; i < 160 &&"
        " document.getElementById('comp-council-footer').hidden; i++)"
        " await new Promise((r) => setTimeout(r, 50));"
        " return true; })()")
    d.wait_idle()


def scenario_composure_council_setup(d: Driver) -> list[str]:
    """The setup card: the roster, the output kind, and what convene sends."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('council')")
    d.wait_idle()
    d.js_await("(async () => { for (let i = 0; i < 160 &&"
               " !document.querySelector('#cc-participants .cc-person'); i++)"
               " await new Promise((r) => setTimeout(r, 50)); return true; })()")
    if d.js("document.getElementById('comp-council-setup').hidden"):
        fails.append("a council in `setup` did not show the setup card")
    if not d.js("document.getElementById('comp-council-footer').hidden"):
        fails.append("…and showed the footer as well")
    kinds = d.js("COMP_COUNCIL.people.map((p) => p.kind)")
    if "chief" not in (kinds or []):
        fails.append(f"the roster has no chief ({kinds})")
    if "user" not in (kinds or []):
        fails.append(f"the roster has no user row ({kinds})")
    if "pal" in (kinds or []):
        fails.append("a `pal` participant was offered — it is reserved for 0.4.0")
    if not d.js("Array.from(document.querySelectorAll("
                "'#cc-participants input')).slice(-1)[0].disabled"):
        fails.append("the user's row could be unticked")
    # the output kind reveals its path field, and only for `document`
    if not d.js("document.getElementById('cc-output-path').hidden"):
        fails.append("the output path field was visible for an `answer` output")
    d.js("(() => { const s = document.getElementById('cc-output');"
         " s.value = 'document';"
         " s.dispatchEvent(new Event('change', {bubbles: true}));"
         " return true; })()")
    d.wait_idle()
    if d.js("document.getElementById('cc-output-path').hidden"):
        fails.append("choosing `document` did not reveal the path field")
    if not d.js("document.querySelector('#cc-output option[value=\"composure\"]')"
                ".disabled"):
        fails.append("the `composure` output kind was selectable — it is 0.4.0's")
    _comp_blank(d)
    d.js("rvForceClosed(false)")
    _reset(d)
    return fails


def scenario_composure_council_controls(d: Driver) -> list[str]:
    """The footer's controls, disabled per the state machine, and a 409
    shown verbatim rather than swallowed."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    _council_open(d)
    state = d.js("COMP_COUNCIL.state.council.status")
    if state != "ready":
        fails.append(f"a set-up council is not `ready` ({state})")
    if d.js("document.getElementById('comp-council-setup').hidden") is False:
        fails.append("a convened council still showed the setup card")
    live = d.js("['cc-next','cc-round','cc-run','cc-conclude','cc-send']"
                ".map((i) => document.getElementById(i).disabled)")
    if any(live or [True]):
        fails.append(f"a `ready` council had a dead control ({live})")
    if not d.js("document.getElementById('cc-pause').disabled"):
        fails.append("`pause` was live on a council that is not running")
    # The status line names the round. NOT by looking for the word "round":
    # the scenarios run in every language, and this went red in de and ja
    # against a line that says exactly the right thing ("bereit · Runde 1 von
    # 3 · als Nächstes: Ed"). Assert on the numbers, which every catalog
    # renders the same way. (P6c)
    line = d.js("document.getElementById('cc-status-text').textContent") or ""
    # The model counts rounds COMPLETED; the line names the one about to
    # run (`compCouncilStatusLine`: `min(max, done + 1)`), which is what a
    # reader wants to know.
    meta = d.js("(() => { const m = COMP_COUNCIL.state.council;"
                " const max = m.max_rounds || 1; const done = m.round || 0;"
                " return {n: (m.status === 'concluded') ? done"
                "   : Math.min(max, done + 1), max: max}; })()") or {}
    want = [str(meta.get("n", "?")), str(meta.get("max", "?"))]
    if not all(n in line for n in want):
        fails.append(f"the status line does not say which round: {line!r} "
                     f"names neither {want[0]} nor {want[1]} of "
                     f"{want[0]}/{want[1]}")

    # A REFUSAL IS A SENTENCE TO SHOW, not an error to swallow. The suite's
    # scratch server has no model (`--llm-url` points at a dead port), so
    # `conclude` — which needs one chief turn — is refused deterministically
    # and without one, which is exactly the shape a 409 has: the server's own
    # words have to reach the footer's notice rather than the console.
    d.click("#cc-conclude")
    d.js_await("(async () => { for (let i = 0; i < 300 &&"
               " document.getElementById('cc-notice').hidden; i++)"
               " await new Promise((r) => setTimeout(r, 50)); return true; })()")
    if d.js("document.getElementById('cc-notice').hidden"):
        fails.append("a refused control showed nothing at all")
    else:
        note = d.js("document.getElementById('cc-notice').textContent") or ""
        if len(note.strip()) < 12:
            fails.append(f"the refusal was not the server's sentence ({note!r})")
    _comp_blank(d)
    d.js("rvForceClosed(false)")
    _reset(d)
    return fails


def scenario_composure_inspector_is_clickable(d: Driver) -> list[str]:
    """The inspector answers a real click.

    Every control in it lives INSIDE the viewport, so a pointerdown that
    the canvas does not stand back from lands on "the pointer tool, on
    empty desk" — and the pointer-up clears the selection, which hides the
    panel that was clicked. That is invisible to a harness driving the
    functions directly, so this one clicks.
    """
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    d.js_await("compOpenNew('cards')")
    d.wait_for(CARDS_READY[1])
    d.js("compSetMode('edit'); compSetTool('pointer');"
         " compSetSelection([COMP.model.modules[0].id])")
    d.wait_for("#comp-inspector:not([hidden])")
    before = d.js("compModuleById(COMP.sel[0]).bg")
    d.click("#comp-insp-swatches .comp-swatch[data-bg='blue']")
    d.wait_idle()
    if d.js("COMP.sel.length") != 1:
        fails.append("clicking a swatch cleared the selection")
    if d.js("document.getElementById('comp-inspector').hidden"):
        fails.append("clicking a swatch hid the inspector")
    after = d.js("COMP.sel.length ? compModuleById(COMP.sel[0]).bg : null")
    if after != "blue":
        fails.append(f"the swatch did not repaint the module: {before!r} → "
                     f"{after!r}")
    d.js("compUndo()")
    d.wait_idle()
    _comp_blank(d)
    _reset(d)
    return fails


SCENARIOS: dict[str, Scenario] = {
    "stack-order": scenario_stack_order,
    "raise-preserves-state": scenario_raise_preserves_state,
    "esc-closes-only-top": scenario_esc_closes_only_top,
    "esc-inert-under-modal-and-composer": scenario_esc_inert_under_modal_and_composer,
    "buried-ribbon-closes-that-entry": scenario_buried_ribbon_closes_that_entry,
    "mini-full-toggle": scenario_mini_full_toggle,
    "dirty-guard": scenario_dirty_guard,
    "sidebar-toggle-is-layout-only": scenario_sidebar_toggle_is_layout_only,
    "language-roundtrip": scenario_language_roundtrip,
    # --- the readvisor panel (P3) ---
    "rv-docked-pushes": scenario_rv_docked_pushes,
    "rv-full-indicator-restores": scenario_rv_full_indicator_restores,
    "rv-esc-ladder": scenario_rv_esc_ladder,
    "rv-minis-inside-main": scenario_rv_minis_inside_main,
    # --- the composure canvas ---
    "composure-input-rules": scenario_composure_input_rules,
    "composure-ink": scenario_composure_ink,
    "composure-search": scenario_composure_search,
    "composure-journal": scenario_composure_journal,
    "composure-comments": scenario_composure_comments,
    "composure-selection-shape": scenario_composure_selection_shape,
    "composure-council-pins-panel": scenario_composure_council_pins_panel,
    "composure-council-setup": scenario_composure_council_setup,
    "composure-council-controls": scenario_composure_council_controls,
    "composure-inspector-is-clickable":
        scenario_composure_inspector_is_clickable,
}
