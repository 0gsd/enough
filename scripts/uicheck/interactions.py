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
from .screens import (CARDS_READY, COUNCIL_PAL_STATEMENT, DICT_PLAIN,
                      DICT_READY, DOC, GIRRAPH, JOURNAL_READY, WDL_READY)

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
         "'paginated','blobview','dict'].forEach((n) => { try { modeRemove(n); } "
         "catch (e) {} }); return true; })()")
    d.js("(() => { try { wdlClose(); dictCtxClose(); } catch (e) {} return true; })()")
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
        # 0.4.1 (U2): the overlay opens with the SAFE choice focused, so a
        # reflexive Return keeps the work instead of throwing it away.
        d.wait_idle()
        if _active(d) != "#confirm-cancel":
            fails.append(f"the discard confirm opened with focus on "
                         f"{_active(d)}, not on 'keep editing' (#confirm-cancel)")
        d.key("Enter")
        d.wait_idle()
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
    # A pal is NOT in the roster, and P9 did not change that: it is
    # invoked per ask (`/pal` in the composer), never enrolled. It takes a
    # turn number but not a slot, takes no share of the budget, and
    # `council.speakers()` still skips it — so a checkbox for it would be
    # a promise the engine does not keep. Verified against the backend:
    # `default_participants` returns chief/readvisor/user only.
    if "pal" in (kinds or []):
        fails.append("a `pal` participant was offered — a pal is invoked per "
                     "ask, not enrolled, so it has no roster row")
    if not d.js("Array.from(document.querySelectorAll("
                "'#cc-participants input[type=\"checkbox\"]')).slice(-1)[0]"
                ".disabled"):
        fails.append("the user's row could be unticked")
    # Charges: one per NON-user row, capped at the engine's 200.
    charges = d.js("Array.from(document.querySelectorAll('#cc-participants "
                   ".cc-person')).map((r) => {"
                   " const c = r.querySelector('.cc-charge');"
                   " return c ? c.maxLength : null; })") or []
    people = d.js("COMP_COUNCIL.people.map((p) => p.kind)") or []
    for kind, cap in zip(people, charges):
        if kind == "user" and cap is not None:
            fails.append("the user's row has a charge field — you are not "
                         "something the council was told to do")
        if kind != "user" and cap != 200:
            fails.append(f"a {kind} row's charge field caps at {cap!r}, not "
                         f"the engine's 200")
    # …and a charge typed into a row reaches that row's model entry, which
    # is what convene sends back.
    d.js("(() => { const c = document.querySelector('#cc-participants "
         ".cc-charge'); c.value = 'owns continuity';"
         " c.dispatchEvent(new Event('input', {bubbles: true}));"
         " return true; })()")
    if d.js("COMP_COUNCIL.people.filter((p) => p.charge === 'owns continuity')"
            ".length") != 1:
        fails.append("a typed charge did not reach the participant row")
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
    if not d.js("document.getElementById('cc-form-row').hidden"):
        fails.append("a `document` output offered a composure form select")
    # `composure` landed in P9: selectable, and it takes a FORM and no path.
    if d.js("document.querySelector('#cc-output option[value=\"composure\"]')"
            ".disabled"):
        fails.append("the `composure` output kind is still disabled — it "
                     "landed in P9")
    d.js("(() => { const s = document.getElementById('cc-output');"
         " s.value = 'composure';"
         " s.dispatchEvent(new Event('change', {bubbles: true}));"
         " return true; })()")
    d.wait_idle()
    if d.js("document.getElementById('cc-form-row').hidden"):
        fails.append("choosing `composure` did not reveal the form select")
    if not d.js("document.getElementById('cc-output-path').hidden"):
        fails.append("a `composure` output asked for a path — the file is "
                     "made beside the council")
    forms = d.js("Array.from(document.querySelectorAll('#cc-form option'))"
                 ".map((o) => o.value)")
    if forms != ["scaffold", "cards"]:
        fails.append(f"the form select offers {forms!r}, not the two forms "
                     f"the engine validates")
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


def scenario_pal_hint_row(d: Driver) -> list[str]:
    """`/` reveals the hint row; it greys itself with the gate's reason;
    Tab completes `/pal `; clearing the composer takes it away again.

    The scratch world's gate is genuinely shut — `smoke_boot.build_env()`
    gives it its own `$HOME`, so `local_models_only` is on at its default
    and there is no OpenRouter key — which makes the CLOSED row real here
    rather than mocked. The open row is a screen (`readvisor-pal-hint-open`)
    and is seeded, because opening the gate honestly would mean writing a
    key into the developer's OS keyring.
    """
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    d.wait_idle()
    if not d.js("document.getElementById('pal-hint').hidden"):
        fails.append("the hint row was showing before anything was typed")
    # Real typing, through the real input pipeline.
    d.focus("#message")
    d.type_text("/")
    d.js_await("(async () => { for (let i = 0; i < 100 && !PAL.status; i++)"
               " await new Promise((r) => setTimeout(r, 50));"
               " palSyncHint('pal-hint', document.getElementById('message')"
               ".value); return true; })()")
    d.wait_idle()
    if d.js("document.getElementById('pal-hint').hidden"):
        fails.append("`/` did not reveal the hint row")
    status = d.js("PAL.status") or {}
    if status.get("available"):
        fails.append("the scratch world's cloud gate answered OPEN — this "
                     "run is not isolated from the developer's keyring")
    else:
        if not d.js("document.getElementById('pal-hint')"
                    ".classList.contains('pal-off')"):
            fails.append("a shut gate did not grey the row")
        gloss = d.js("document.getElementById('pal-hint-gloss').textContent") or ""
        if gloss.strip() != (status.get("reason") or "").strip():
            fails.append(f"the greyed row does not carry the gate's own "
                         f"reason: {gloss!r} vs {status.get('reason')!r}")
        if (d.js("document.querySelector('#pal-hint .pal-model').textContent")
                or "").strip():
            fails.append("a shut gate named a model anyway — there is no "
                         "model to name behind a shut door")
    # Tab completes. A greyed row still completes: it is a hint, not a gate.
    d.focus("#message")
    d.key("Tab")
    d.wait_idle()
    typed = d.js("document.getElementById('message').value")
    if typed != "/pal ":
        fails.append(f"Tab did not complete the command: {typed!r}")
    # …and it is still just text in the box. No client-side handling.
    d.js("(() => { const ta = document.getElementById('message');"
         " ta.value = ''; ta.dispatchEvent(new Event('input',"
         " {bubbles: true})); return true; })()")
    d.wait_idle()
    if not d.js("document.getElementById('pal-hint').hidden"):
        fails.append("clearing the composer left the hint row behind")
    d.js("(() => { PAL.status = null; document.getElementById('message')"
         ".blur(); return true; })()")
    _reset(d)
    return fails


def scenario_pal_gate_closed(d: Driver) -> list[str]:
    """`/pal <ask>` with the gate shut: the server's own denial as a system
    bubble, and NO turn — not a pending assistant bubble, not a
    `turn_start`, nothing that costs a window."""
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    d.js("(() => { document.getElementById('conversation').innerHTML = '';"
         " window.__uicheckTurns = 0;"
         " return true; })()")
    # Count `turn_start` the way the page does — on the same EventSource.
    d.js("(() => { window.es && window.es.addEventListener"
         " && window.es.addEventListener('turn_start',"
         " () => { window.__uicheckTurns++; }); return true; })()")
    d.focus("#message")
    d.type_text("/pal which obligations slipped?")
    d.key("Enter")
    d.js_await("(async () => { for (let i = 0; i < 200 &&"
               " !document.querySelector('#conversation .msg.system'); i++)"
               " await new Promise((r) => setTimeout(r, 50)); return true; })()")
    d.wait_idle()
    said = d.js("(() => { const el = document.querySelector("
                "'#conversation .msg.system .body');"
                " return el ? el.textContent : ''; })()") or ""
    if not said.strip():
        fails.append("a `/pal` against a shut gate said nothing at all")
    elif len(said.strip()) < 40:
        fails.append(f"the denial was not the broker's sentence ({said!r})")
    # The typed line is still the user's bubble — what they wrote, not what
    # would have been sent.
    user = d.js("(() => { const el = document.querySelector("
                "'#conversation .msg.user .body');"
                " return el ? el.textContent : ''; })()") or ""
    if "/pal" not in user:
        fails.append(f"the user's bubble lost the command they typed ({user!r})")
    if d.js("!!document.getElementById('current-response')"):
        fails.append("a refused `/pal` still opened an assistant bubble — no "
                     "turn should have started")
    if d.js("document.querySelectorAll('.msg.pal, .msg.pal-sent').length"):
        fails.append("a refused `/pal` rendered pal bubbles — nothing left "
                     "the machine")
    d.js("(() => { document.getElementById('conversation').innerHTML = '';"
         " const ta = document.getElementById('message'); ta.value = '';"
         " ta.dispatchEvent(new Event('input', {bubbles: true}));"
         " PAL.status = null; return true; })()")
    _reset(d)
    return fails


def scenario_pal_bubbles(d: Driver) -> list[str]:
    """One exchange renders as two bubbles, in this order, with the model
    id in both bylines — and the outgoing prompt VERBATIM.

    The event is synthetic (there is no model in the scratch world) but it
    goes through the page's own `pal_exchange` handler, and the markup it
    produces is the one `server._render_pal_bubbles` also emits when the
    same exchange is rebuilt from history on reload."""
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    prompt = ("Which obligations under the EU AI Act took effect in August "
              "2026, and which were postponed?")
    reply = "Two of the high-risk obligations moved to 2027."
    d.js("(() => { document.getElementById('conversation').innerHTML = '';"
         " palOnExchange(" + json.dumps({
             "model_id": "anthropic/claude-sonnet-4.5",
             "prompt": prompt, "reply": reply}) + "); return true; })()")
    d.wait_idle()
    order = d.js("Array.from(document.querySelectorAll('#conversation .msg'))"
                 ".map((el) => el.className)") or []
    if order != ["msg pal-sent", "msg pal"]:
        fails.append(f"the two bubbles are not the sent-then-received pair: "
                     f"{order!r}")
    sent = d.js("(() => { const el = document.querySelector('.msg.pal-sent');"
                " return el ? {role: el.querySelector('.role').textContent,"
                " body: el.querySelector('.body').textContent} : null; })()")
    got = d.js("(() => { const el = document.querySelector('.msg.pal');"
               " return el ? {role: el.querySelector('.role').textContent,"
               " body: el.querySelector('.body').textContent} : null; })()")
    if not sent or sent["body"] != prompt:
        fails.append("the outgoing prompt was not shown verbatim: "
                     f"{(sent or {}).get('body')!r}")
    if not sent or not sent["role"].startswith("→ pal · "):
        fails.append(f"the outgoing byline is wrong: {(sent or {}).get('role')!r}")
    if not sent or "anthropic/claude-sonnet-4.5" not in sent["role"]:
        fails.append("the outgoing byline does not name the model")
    if not got or got["body"] != reply:
        fails.append(f"the reply bubble is wrong: {(got or {}).get('body')!r}")
    if not got or got["role"] != "pal · anthropic/claude-sonnet-4.5":
        fails.append(f"the reply byline is wrong: {(got or {}).get('role')!r}")
    # A streaming assistant bubble is BELOW both, not above: the exchange
    # happened before the readvisor's next token.
    d.js("(() => { document.getElementById('conversation')"
         ".insertAdjacentHTML('beforeend', '<div class=\"msg assistant "
         "pending\" id=\"current-response\"><div class=\"role\">Ed</div>"
         "<div class=\"body\"></div></div>');"
         " palOnExchange({model_id: 'm', prompt: 'p', reply: 'r'});"
         " return true; })()")
    tail = d.js("Array.from(document.querySelectorAll('#conversation .msg'))"
                ".map((el) => el.className)") or []
    if tail[-1] != "msg assistant pending":
        fails.append(f"a pal exchange landed AFTER the streaming bubble: "
                     f"{tail!r}")
    d.js("(() => { document.getElementById('conversation').innerHTML = '';"
         " return true; })()")
    _reset(d)
    return fails


def scenario_composure_council_pal(d: Driver) -> list[str]:
    """`/pal` in the council composer: a different endpoint, and its refusal
    is a sentence in the footer's notice.

    The scratch world's gate is shut, so `POST /api/council/pal` answers
    409 with the broker's copy before it spends a single model call — which
    is the shape this asserts, and it needs no model to assert it."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    _council_open(d)
    before = d.js("COMP_COUNCIL.state.council.turn")
    # The hint row appears in the footer too, on the same rules.
    d.js("(() => { const ta = document.getElementById('cc-say');"
         " ta.value = '/pal'; ta.dispatchEvent(new Event('input',"
         " {bubbles: true})); return true; })()")
    d.js_await("(async () => { for (let i = 0; i < 100 && !PAL.status; i++)"
               " await new Promise((r) => setTimeout(r, 50));"
               " palSyncHint('cc-pal-hint',"
               " document.getElementById('cc-say').value); return true; })()")
    d.wait_idle()
    if d.js("document.getElementById('cc-pal-hint').hidden"):
        fails.append("`/pal` in the council composer showed no hint row")
    if not d.js("document.getElementById('cc-pal-hint')"
                ".classList.contains('pal-off')"):
        fails.append("the council's hint row did not grey itself on a shut gate")
    # A bare `/pal` never reaches the server: it is a usage note, not a turn.
    d.js("(() => { document.getElementById('cc-say').value = '/pal';"
         " return true; })()")
    d.js_await("(async () => { await compCouncilSayIt(); return true; })()")
    note = d.js("document.getElementById('cc-notice').textContent") or ""
    if "/pal" not in note:
        fails.append(f"a bare `/pal` did not explain itself ({note!r})")
    # …and with an ask, the server's own refusal reaches the same notice.
    d.js("(() => { document.getElementById('cc-say').value ="
         " '/pal what about the reveal?'; return true; })()")
    d.js_await("(async () => { await compCouncilSayIt(); return true; })()",
               timeout=30.0)
    d.wait_idle()
    note = d.js("document.getElementById('cc-notice').textContent") or ""
    if len(note.strip()) < 40:
        fails.append(f"the council's `/pal` refusal was not the server's "
                     f"sentence ({note!r})")
    after = d.js("COMP_COUNCIL.state.council.turn")
    if after != before:
        fails.append(f"a refused `/pal` still took a turn ({before} → {after})")
    d.js("(() => { const ta = document.getElementById('cc-say');"
         " ta.value = ''; ta.dispatchEvent(new Event('input',"
         " {bubbles: true})); PAL.status = null; return true; })()")

    # --- and what a pal's ANSWER looks like once it is committed ---------
    #
    # The statement is built in the MODEL only, the way
    # `composure-journal-filed` fakes a filed page: a real one wants two
    # model calls and a cloud key. What is asserted is what
    # `compPaintModule` makes of it.
    d.run_steps((COUNCIL_PAL_STATEMENT,), what="a pal statement")
    d.wait_for(".comp-module[data-speaker-kind='pal']")
    d.wait_idle()
    cls = d.js("document.querySelector('.comp-module[data-speaker-kind=\"pal\"]')"
               ".className") or ""
    if "comp-bg-gray" not in cls:
        fails.append(f"a pal statement is not gray-tinted ({cls!r})")
    if "comp-locked" not in cls:
        fails.append("a pal statement is not locked — statements belong to "
                     "the engine")
    quote = d.js("(() => { const q = document.querySelector("
                 "'.comp-module[data-speaker-kind=\"pal\"] blockquote');"
                 " return q ? {hidden: q.hidden, cls: q.className,"
                 "  text: (q.textContent || '').slice(0, 8)} : null; })()")
    if not quote:
        fails.append("a pal statement lost its outgoing prompt entirely — "
                     "that block IS the record of what left the machine")
    else:
        if not quote["hidden"]:
            fails.append("the outgoing prompt was not collapsed by default")
        if "comp-pal-prompt" not in quote["cls"]:
            fails.append(f"the leading quote was not recognised ({quote!r})")
    if not d.exists(".comp-module[data-speaker-kind='pal'] "
                    ".comp-council-pal-lead"):
        fails.append("there is no disclosure to open the outgoing prompt with")
    # A real click opens it, and a second one closes it again.
    d.click(".comp-module[data-speaker-kind='pal'] .comp-council-pal-lead")
    d.wait_idle()
    if d.js("document.querySelector('.comp-module[data-speaker-kind=\"pal\"] "
            "blockquote').hidden"):
        fails.append("the disclosure did not open the outgoing prompt")
    if d.js("document.querySelector('.comp-module[data-speaker-kind=\"pal\"] "
            ".comp-council-pal-lead').getAttribute('aria-expanded')") != "true":
        fails.append("the disclosure did not say it was open")
    d.click(".comp-module[data-speaker-kind='pal'] .comp-council-pal-lead")
    d.wait_idle()
    if not d.js("document.querySelector('.comp-module[data-speaker-kind=\"pal\"] "
                "blockquote').hidden"):
        fails.append("the disclosure would not close again")
    # The disclosure is CHROME: a repaint must not write it into the file.
    if not d.js("!!document.querySelector('.comp-module[data-speaker-kind="
                "\"pal\"] .comp-council-pal-lead[data-comp-chrome]')"):
        fails.append("the disclosure is not marked as chrome — it would be "
                     "serialized into the statement as prose")
    _comp_blank(d)
    d.js("rvForceClosed(false)")
    _reset(d)
    return fails


def scenario_composure_council_reconvene(d: Driver) -> list[str]:
    """A concluded council's footer carries the reconvene control, and a
    council that has already been reconvened shows where it went instead."""
    fails: list[str] = []
    _reset(d)
    _comp_blank(d)
    _council_open(d)
    if d.js("!!document.getElementById('cc-reconvene')"):
        fails.append("a running council offered reconvene")
    # Concluded in the MODEL only — a real conclude wants a model, and this
    # is about the collapsed footer. (`composure-council-concluded` does
    # the same.)
    d.js("(() => { const m = COMP_COUNCIL.state.council;"
         " m.status = 'concluded'; m.round = m.max_rounds;"
         " m.transcript = 'rness/knowledge/councils/x.md';"
         " compCouncilRender(); return true; })()")
    d.wait_idle()
    if not d.js("!!document.getElementById('cc-reconvene')"):
        fails.append("a concluded council has no reconvene control")
    if not d.js("document.getElementById('cc-composer').hidden"):
        fails.append("a concluded council still shows its composer")
    # Once reconvened, the button is replaced by where it went.
    d.js("(() => { const m = COMP_COUNCIL.state.council;"
         " m.reconvened_to = 'rness/io/composure/again.comp';"
         " compCouncilRender(); return true; })()")
    d.wait_idle()
    if d.js("!!document.getElementById('cc-reconvene')"):
        fails.append("a council already reconvened offered to be again — a "
                     "council is reconvened once")
    done = d.js("document.getElementById('cc-done').textContent") or ""
    if "again.comp" not in done:
        fails.append(f"the footer does not say where it went ({done!r})")
    # …and the other end of the chain says where it came from.
    d.js("(() => { const m = COMP_COUNCIL.state.council;"
         " m.reconvened_from = 'rness/io/composure/before.comp';"
         " compCouncilRender(); return true; })()")
    d.wait_idle()
    frm = d.js("(() => { const el = document.getElementById('cc-from');"
               " return el.hidden ? '' : el.textContent; })()") or ""
    if "before.comp" not in frm:
        fails.append(f"a reconvened council does not say what it carries on "
                     f"from ({frm!r})")
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


# --- 0.4.1 polish (U1) -----------------------------------------------------

def _sleep(d: Driver, ms: int) -> None:
    d.js_await(f"new Promise((r) => setTimeout(() => r(true), {int(ms)}))")


def scenario_chat_sides(d: Driver) -> list[str]:
    """The user's turns hug the left of the chat column, the readvisor's the
    right; enough's own notes keep the full width; the transcript scrolls
    and is padded (its selector went missing once — see
    tests/test_css_integrity.py); the composer never scrolls sideways,
    at any ui scale."""
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    long = "a turn long enough to wrap inside the docked panel " * 3
    d.js("(() => { const c = document.getElementById('conversation');"
         " c.innerHTML = "
         + json.dumps(
             f'<div class="msg user"><div class="role">user</div><div class="body">{long}</div></div>'
             '<div class="msg assistant"><div class="role">Ed</div><div class="body">ok</div></div>'
             '<div class="msg system"><div class="role">enough</div><div class="body">a note</div></div>')
         + "; return true; })()")
    d.wait_idle()
    for state in ("open", "full"):
        d.js(f"rvSetState('{state}')")
        _sleep(d, 300)
        g = d.js("(() => { const c = document.getElementById('conversation');"
                 " const cs = getComputedStyle(c); const r = c.getBoundingClientRect();"
                 " const z = UIZ(); const pl = parseFloat(cs.paddingLeft) * z,"
                 " pr = parseFloat(cs.paddingRight) * z;"
                 " const box = (s) => c.querySelector(s).getBoundingClientRect();"
                 " const u = box('.msg.user'), a = box('.msg.assistant'), s = box('.msg.system');"
                 " return {overflowY: cs.overflowY, pad: pl, inL: r.left + pl, inR: r.right - pr,"
                 " uL: u.left, uR: u.right, aL: a.left, aR: a.right, sL: s.left, sR: s.right}; })()")
        if g["overflowY"] != "auto" or g["pad"] < 8:
            fails.append(f"[{state}] .conversation is not the padded scroller "
                         f"(overflow-y {g['overflowY']}, padding {g['pad']:.0f}px)")
        if abs(g["uL"] - g["inL"]) > 1.5 or g["uR"] > g["inR"] - 20:
            fails.append(f"[{state}] the user's turn does not hug the left: {g}")
        if abs(g["aR"] - g["inR"]) > 1.5 or g["aL"] < g["inL"] + 20:
            fails.append(f"[{state}] the readvisor's turn does not hug the right: {g}")
        if abs(g["sL"] - g["inL"]) > 1.5 or abs(g["sR"] - g["inR"]) > 1.5:
            fails.append(f"[{state}] a system note is not full width: {g}")
    d.js("rvSetState('open')")
    d.js("document.getElementById('message').value = "
         + json.dumps("x" * 400 + " https://example.invalid/" + "a/b/" * 60))
    for z in (1, 1.1, 1.2):
        d.js(f"(() => {{ UI_SCALES.ui_scale = {z}; applyUIScales(); return true; }})()")
        _sleep(d, 150)
        sw = d.js("(() => { const t = document.getElementById('message');"
                  " return [t.scrollWidth, t.clientWidth]; })()")
        if sw[0] > sw[1]:
            fails.append(f"the composer scrolls sideways at ui {z}: "
                         f"scrollWidth {sw[0]} > clientWidth {sw[1]}")
    d.js("(() => { UI_SCALES.ui_scale = 1; applyUIScales();"
         " document.getElementById('message').value = '';"
         " document.getElementById('conversation').innerHTML = ''; return true; })()")
    _reset(d)
    return fails


def scenario_chat_tool_chip(d: Driver) -> list[str]:
    """A tool call gets its chip. The server ends the model's turn
    (`turn_end`, which releases #current-response) BEFORE it runs the call,
    so the chip has to land on the bubble that just finished; an assistant
    bubble with no tool calls keeps no empty chip row under it."""
    fails: list[str] = []
    _reset(d)
    d.js("rvSetState('open')")
    r = d.js_await("(async () => { const c = document.getElementById('conversation'); c.innerHTML ="
                   " '<div class=\"msg assistant\"><div class=\"role\">Ed</div><div class=\"body\">plain</div>'"
                   " + '<div class=\"tool-indicators\"></div></div>'"
                   " + '<div class=\"msg assistant\"><div class=\"role\">Ed</div><div class=\"body\">let me look.</div>'"
                   " + '<div class=\"tool-indicators\"></div></div>';"
                   " const ev = (status) => es.dispatchEvent(new MessageEvent('tool', {data: JSON.stringify("
                   "{name: 'dict_lookup', key: '', status})}));"
                   " ev('running'); ev('ok'); await new Promise((r) => setTimeout(r, 50));"
                   " const ti = c.querySelectorAll('.tool-indicators');"
                   " const chip = ti[1].querySelector('.tool-indicator');"
                   " return {chip: chip && chip.className, text: chip && chip.textContent,"
                   " emptyShown: getComputedStyle(ti[0]).display !== 'none'}; })()", timeout=10) or {}
    if r.get("chip") != "tool-indicator ok" or r.get("text") != "dict_lookup":
        fails.append(f"the tool chip did not land on the finished bubble: {r}")
    if r.get("emptyShown"):
        fails.append("an assistant bubble with no tool calls keeps an empty chip row")
    d.js("(() => { document.getElementById('conversation').innerHTML = ''; return true; })()")
    _reset(d)
    return fails


def scenario_topbar_no_collisions(d: Driver) -> list[str]:
    """The project title is an in-flow item: with a long name, five stacked
    modes and the doc counters showing, at ui 1.0-1.2, nothing in the top
    bar paints over anything else and the bar never overflows."""
    fails: list[str] = []
    _reset(d)
    d.js(f"enterGirraphMode('{GIRRAPH}')")
    d.wait_for("#girraph-mode.open")
    d.js("enterCacheawlMode()")
    d.wait_for("#cacheawl-mode.open")
    d.js("enterRefMode()")
    d.wait_for("#ref-mode.open")
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'read'}})")
    d.wait_for("#review-mode.open")
    d.wait_idle()
    name0 = d.js("document.getElementById('project-name').textContent")
    d.js("applyProjectName('a deliberately long project name that has to give way to the rest of the bar')")
    for z in (1, 1.1, 1.2):
        d.js(f"(() => {{ UI_SCALES.ui_scale = {z}; applyUIScales(); return true; }})()")
        _sleep(d, 200)
        g = d.js("""(() => {
          const R = (el) => el.getBoundingClientRect();
          const bar = document.querySelector('.topbar');
          const items = [['title', document.getElementById('project-title')],
            ['counters', document.getElementById('doc-counters')],
            ['badge', document.getElementById('model-badge')],
            ['rv', document.getElementById('toggle-readvisor')]];
          document.querySelectorAll('#mode-stack .mode-indicator').forEach(
            (s, i) => items.push(['square' + i, s]));
          const vis = items.filter(([, el]) => el && R(el).width > 0);
          const hits = [];
          for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
            const a = R(vis[i][1]), b = R(vis[j][1]);
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            if (w > 0.5) hits.push(vis[i][0] + '/' + vis[j][0] + ' ' + w.toFixed(1));
          }
          return {hits, over: bar.scrollWidth - bar.clientWidth};
        })()""")
        if g["hits"]:
            fails.append(f"top bar items overlap at ui {z}: {g['hits']}")
        if g["over"] > 1:
            fails.append(f"the top bar overflows by {g['over']}px at ui {z}")
    d.js("(() => { UI_SCALES.ui_scale = 1; applyUIScales(); return true; })()")
    d.js(f"applyProjectName({json.dumps(name0 or '')})")
    _reset(d)
    return fails


def scenario_composure_autofit(d: Driver) -> list[str]:
    """A board ends up fitted and centred after any viewport size change —
    but not while a drag owns the view, and not while it is covered."""
    fails: list[str] = []
    _reset(d)
    d.js_await("compOpenNew('cards')")
    d.wait_for(CARDS_READY[1])
    d.wait_idle()
    off = ("(() => { const vp = compViewport(), b = compBounds();"
           " const c = compWorldToStage(b.x + b.w / 2, b.y + b.h / 2);"
           " return [Math.round(c.x - vp.clientWidth / 2),"
           " Math.round(c.y - vp.clientHeight / 2)]; })()")
    pan = ("(() => { COMP.origin = {x: COMP.origin.x + 260, y: COMP.origin.y + 90};"
           " COMP.zoomed = true; compApplyView(false); return true; })()")
    centred = lambda o: o and abs(o[0]) <= 2 and abs(o[1]) <= 2  # noqa: E731
    d.js(pan)
    d.click("#toggle-sidebar")
    _sleep(d, 700)
    if not centred(d.js(off)):
        fails.append(f"hiding the sidebar did not refit the board: {d.js(off)}")
    d.js(pan)
    d.js("COMP.drag = {kind: 'pan'}")
    d.click("#toggle-sidebar")
    _sleep(d, 600)
    if centred(d.js(off)):
        fails.append("the board was refitted in the middle of a drag")
    d.js("COMP.drag = null")
    _sleep(d, 600)
    if not centred(d.js(off)):
        fails.append(f"the deferred fit never landed after the drag: {d.js(off)}")
    d.js(pan)
    d.js("rvSetState(RV_STATE === 'closed' ? 'open' : 'closed')")
    _sleep(d, 700)
    if not centred(d.js(off)):
        fails.append(f"toggling the readvisor panel did not refit: {d.js(off)}")
    d.js("rvSetState('open')")
    _reset(d)
    _comp_blank(d)
    return fails


# --- 0.4.1 modal a11y (U2) -------------------------------------------------
#
# One helper (index.html, "Modal a11y") watches every dialog's own open and
# close. These hold it to its contract: the dialog is what assistive tech
# and the keyboard can reach, nothing behind it is, focus goes in on open
# and back to the opener on close, and a confirm raised over a modal stacks.

_AX_INTERACTIVE = frozenset({
    "button", "link", "textbox", "searchbox", "combobox", "checkbox",
    "switch", "radio", "slider", "spinbutton", "menuitem", "tab",
    "PopUpButton", "ListBox", "listbox"})


def _active(d: Driver) -> str:
    return d.js("(() => { const a = document.activeElement;"
                " if (!a || a === document.body) return 'BODY';"
                " if (a.id) return '#' + a.id;"
                " return a.tagName.toLowerCase() + (a.className"
                " ? '.' + String(a.className).split(' ')[0] : ''); })()")


def _focus_inside(d: Driver, sel: str) -> bool:
    return bool(d.js(f"!!document.querySelector({json.dumps(sel)})"
                     f"?.contains(document.activeElement)"))


def _shift_tab(d: Driver) -> None:
    spec = {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9,
            "nativeVirtualKeyCode": 9, "modifiers": 8}
    d.page.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", **spec})
    d.page.send("Input.dispatchKeyEvent", {"type": "keyUp", **spec})


def _ax_dialog(d: Driver, sel: str) -> list[str]:
    """The accessibility tree, as a screen reader gets it: one named dialog,
    its controls, and NO control from behind it."""
    fails: list[str] = []
    tree = d.page.send("Accessibility.getFullAXTree", {})
    nodes = [n for n in tree.get("nodes", []) if not n.get("ignored")]
    role = lambda n: (n.get("role") or {}).get("value")          # noqa: E731
    name = lambda n: (n.get("name") or {}).get("value") or ""    # noqa: E731
    dialogs = [n for n in nodes if role(n) == "dialog"]
    if not dialogs:
        fails.append(f"{sel}: no dialog in the accessibility tree")
    elif not any(name(n).strip() for n in dialogs):
        fails.append(f"{sel}: the dialog has no accessible name")
    inside = 0
    leaks: list[str] = []
    for n in nodes:
        if role(n) not in _AX_INTERACTIVE or not n.get("backendDOMNodeId"):
            continue
        obj = d.page.send("DOM.resolveNode",
                          {"backendNodeId": n["backendDOMNodeId"]})
        oid = (obj.get("object") or {}).get("objectId")
        if not oid:
            continue
        r = d.page.send("Runtime.callFunctionOn", {
            "objectId": oid, "returnByValue": True,
            "functionDeclaration": "function (s) { const e = this.nodeType === 1"
                                   " ? this : this.parentElement;"
                                   " return !!(e && e.closest(s)); }",
            "arguments": [{"value": sel}]})
        if (r.get("result") or {}).get("value"):
            inside += 1
        else:
            leaks.append(f"{role(n)} '{name(n)[:30]}'")
    if not inside:
        fails.append(f"{sel}: none of the dialog's controls are in the tree")
    if leaks:
        fails.append(f"{sel}: the background is exposed behind the dialog: "
                     f"{leaks[:8]}")
    return fails


def _modal_contract(d: Driver, opener: str, sel: str) -> list[str]:
    fails: list[str] = []
    _reset(d)
    d.focus(opener)
    d.click(opener)
    d.wait_for(f"{sel}:not(.hidden)")
    d.wait_idle()
    if d.js(f"document.querySelector({json.dumps(sel)}).getAttribute('aria-hidden')") != "false":
        fails.append(f"{sel}: aria-hidden is not 'false' while it is open")
    if not _focus_inside(d, sel):
        fails.append(f"{sel}: focus stayed on {_active(d)} when it opened")
    fails += _ax_dialog(d, sel)
    left = []
    for i in range(40):
        d.key("Tab")
        if not _focus_inside(d, sel):
            left.append(f"Tab {i + 1} → {_active(d)}")
    for i in range(10):
        _shift_tab(d)
        if not _focus_inside(d, sel):
            left.append(f"shift-Tab {i + 1} → {_active(d)}")
    if left:
        fails.append(f"{sel}: focus left the dialog: {left[:5]}")
    d.key("Escape")
    d.wait_gone(f"{sel}:not(.hidden)")
    d.wait_idle()
    if _active(d) != opener:
        fails.append(f"{sel}: closing it left focus on {_active(d)}, "
                     f"not on the opener {opener}")
    if d.js("document.querySelectorAll('[data-modal-inert]').length"):
        fails.append(f"{sel}: the background is still inert after it closed")
    _reset(d)
    return fails


def scenario_modal_prefs_a11y(d: Driver) -> list[str]:
    """Preferences: named dialog, background out of the a11y tree and the
    tab order, focus in on open and back on the ⚙ button on close."""
    return _modal_contract(d, "#ui-btn", "#ui-modal")


def scenario_modal_broker_a11y(d: Driver) -> list[str]:
    """The broker: the same contract, through an htmx re-fetch of its body
    that lands after the dialog opened."""
    return _modal_contract(d, "#broker-btn", "#broker-modal")


def scenario_modal_return_after_open(d: Driver) -> list[str]:
    """The QA repro: open Preferences, Tab, Return. That used to open
    wikisink BEHIND the dialog, because focus never left the top bar."""
    fails: list[str] = []
    _reset(d)
    resident = _names(d)
    d.focus("#ui-btn")
    d.click("#ui-btn")
    d.wait_for("#ui-modal:not(.hidden)")
    d.wait_idle()
    d.key("Tab")
    d.key("Enter")
    d.wait_idle()
    if _mine(d, resident):
        fails.append(f"Tab, Return in a fresh Preferences opened "
                     f"{_mine(d, resident)} behind it")
    if d.js("document.getElementById('wiki-mode').classList.contains('open')"):
        fails.append("Tab, Return in a fresh Preferences opened wikisink")
    _reset(d)
    return fails


def scenario_modal_confirm_stack(d: Driver) -> list[str]:
    """A confirm raised over Preferences: the confirm is the dialog, the
    prefs go inert UNDER it, esc peels one layer at a time, and focus walks
    back down the stack to where it came from."""
    fails: list[str] = []
    _reset(d)
    d.focus("#ui-btn")
    d.click("#ui-btn")
    d.wait_for("#ui-modal:not(.hidden)")
    d.wait_idle()
    under = _active(d)
    d.js("(() => { window.__u2Confirm = confirmOverlay({title: 'stacked?',"
         " message: 'a confirm over a modal'}); return true; })()")
    d.wait_for("#confirm-overlay:not([hidden])")
    d.wait_idle()
    if _active(d) != "#confirm-cancel":
        fails.append(f"the confirm opened with focus on {_active(d)}; the "
                     f"default is cancel")
    if not d.js("document.getElementById('ui-modal').inert"):
        fails.append("Preferences stayed live under the confirm")
    if d.js("document.getElementById('confirm-overlay').inert"):
        fails.append("the confirm itself is inert")
    fails += _ax_dialog(d, "#confirm-overlay")
    for i in range(12):
        d.key("Tab")
        if not _focus_inside(d, "#confirm-overlay"):
            fails.append(f"Tab {i + 1} left the confirm for {_active(d)}")
            break
    d.key("Escape")
    d.wait_gone("#confirm-overlay:not([hidden])")
    d.wait_idle()
    if d.js("document.getElementById('ui-modal').classList.contains('hidden')"):
        fails.append("esc on the confirm also closed Preferences under it")
    if d.js("document.getElementById('ui-modal').inert"):
        fails.append("Preferences stayed inert after the confirm closed")
    if _active(d) != under:
        fails.append(f"after the confirm, focus is on {_active(d)}, not back "
                     f"on {under} inside Preferences")
    d.js("(() => { window.__u2Confirm = confirmOverlay({title: 'ok?',"
         " defaultButton: 'confirm'}); return true; })()")
    d.wait_for("#confirm-overlay:not([hidden])")
    d.wait_idle()
    if _active(d) != "#confirm-ok":
        fails.append(f"defaultButton:'confirm' put focus on {_active(d)}")
    d.key("Escape")
    d.wait_gone("#confirm-overlay:not([hidden])")
    d.key("Escape")
    d.wait_gone("#ui-modal:not(.hidden)")
    d.wait_idle()
    if _active(d) != "#ui-btn":
        fails.append(f"closing the whole stack left focus on {_active(d)}")
    if d.js("document.querySelectorAll('[data-modal-inert]').length"):
        fails.append("something is still inert after the stack emptied")
    _reset(d)
    return fails


# --- 0.4.1 help find + contents, the intro (U2) ----------------------------

def _cmd_f(d: Driver) -> None:
    spec = {"key": "f", "code": "KeyF", "windowsVirtualKeyCode": 70,
            "nativeVirtualKeyCode": 70, "modifiers": 4}   # meta
    d.page.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", **spec})
    d.page.send("Input.dispatchKeyEvent", {"type": "keyUp", **spec})


def _scales(d: Driver, ui: float, txt: float) -> None:
    d.js(f"(() => {{ UI_SCALES.ui_scale = {ui}; UI_SCALES.text_scale = {txt};"
         " applyUIScales(); return true; })()")
    _sleep(d, 200)


_FIND_OPEN = "!document.getElementById('ref-find').hidden"
_CUR_IN_VIEW = ("(() => { const h = window.CSS && CSS.highlights"
                " && CSS.highlights.get('enough-find-current');"
                " const m = document.querySelector('#ref-body mark.find-hit.current');"
                " const r = h ? [...h][0].getBoundingClientRect()"
                " : (m ? m.getBoundingClientRect() : null);"
                " if (!r) return null;"
                " const b = document.getElementById('ref-body').getBoundingClientRect();"
                " return r.top >= b.top && r.bottom <= b.bottom; })()")


def scenario_ref_find_contents(d: Driver) -> list[str]:
    """Help: stable section ids, a contents list that jumps and tracks,
    cross-references that link, ⌘F find that steps through matches and
    keeps the current one on screen at any ui/text scale, esc closing the
    bar before the mode, a way back after a jump — and ⌘F left alone while
    the chat composer has the caret."""
    fails: list[str] = []
    _reset(d)
    d.js("enterRefMode()")
    d.wait_for("#ref-body h2[id]")
    d.wait_idle()
    g = d.js("(() => { const hs = Array.from(document.querySelectorAll("
             "'#ref-body h1, #ref-body h2, #ref-body h3'));"
             " const ids = hs.map((h) => h.id);"
             " return {n: hs.length, uniq: new Set(ids).size, first: ids[1],"
             " toc: document.querySelectorAll('#ref-toc a').length,"
             " xref: document.querySelectorAll('#ref-body a.ref-xref').length,"
             " bad: Array.from(document.querySelectorAll('#ref-body a.ref-xref'))"
             ".filter((a) => !document.getElementById(a.dataset.target)).length}; })()")
    if g["uniq"] != g["n"] or g["first"] != "ref-sec-1":
        fails.append(f"heading ids are not unique/stable: {g}")
    if g["toc"] < 10:
        fails.append(f"the contents list has {g['toc']} entries")
    if not g["xref"] or g["bad"]:
        fails.append(f"section references: {g['xref']} linked, {g['bad']} dangling")

    # The contents list: a jump lands the heading at the top of the frame,
    # the list marks it, and the reader can go back.
    for ui, txt in ((1, 1), (1.2, 1.3)):
        _scales(d, ui, txt)
        d.js("refTocToggle(true)")
        j = d.js("(() => { const body = document.getElementById('ref-body');"
                 " body.scrollTop = 0; const a = document.querySelectorAll('#ref-toc a')[25];"
                 " a.click(); const h = document.getElementById(a.dataset.target);"
                 " const off = h.getBoundingClientRect().top - body.getBoundingClientRect().top;"
                 " refTocToggle(true);"
                 " return {off, back: !document.getElementById('ref-back').hidden,"
                 " cur: document.querySelector('#ref-toc a.current')?.dataset.target,"
                 " want: a.dataset.target}; })()")
        if not (0 <= j["off"] <= 40):
            fails.append(f"[ui {ui}/text {txt}] a contents jump put the heading "
                         f"{j['off']:.0f}px from the top of the frame")
        if j["cur"] != j["want"]:
            fails.append(f"[ui {ui}/text {txt}] the contents list marks "
                         f"{j['cur']}, not {j['want']}")
        if not j["back"]:
            fails.append(f"[ui {ui}/text {txt}] no way back after a jump")
        d.js("refBackGo()")
        if d.js("document.getElementById('ref-body').scrollTop") > 2:
            fails.append(f"[ui {ui}/text {txt}] 'back' did not return to the top")

    # ⌘F, typing, Return/shift-Return stepping, the current match in view.
    d.js("document.activeElement && document.activeElement.blur()")
    _cmd_f(d)
    if not d.js(_FIND_OPEN):
        fails.append("⌘F in help did not open the find bar")
    elif not d.js("document.activeElement.classList.contains('find-q')"):
        fails.append(f"⌘F opened the bar but focus is on {_active(d)}")
    d.type_text("composure")
    _sleep(d, 350)
    st = d.js("REF_FIND.state()")
    if not st or st["n"] < 3:
        fails.append(f"find 'composure' in the manual: {st}")
    else:
        for ui, txt in ((1, 1), (1.2, 1.3)):
            _scales(d, ui, txt)
            seen = []
            for _ in range(4):
                d.key("Enter")
                seen.append(d.js(_CUR_IN_VIEW))
            if not all(seen):
                fails.append(f"[ui {ui}/text {txt}] a current match was off "
                             f"screen after Return: {seen}")
        i0 = d.js("REF_FIND.state().i")
        _shift_enter = {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                        "nativeVirtualKeyCode": 13, "text": "\r", "modifiers": 8}
        d.page.send("Input.dispatchKeyEvent", {"type": "keyDown", **_shift_enter})
        d.page.send("Input.dispatchKeyEvent", {"type": "keyUp", **_shift_enter})
        if d.js("REF_FIND.state().i") != i0 - 1:
            fails.append("shift-Return did not step back one match")
        cnt = d.js("document.querySelector('#ref-find .find-count').textContent")
        if cnt != f"{i0} of {st['n']}" and d.js("I18N.lang") == "en":
            fails.append(f"the count reads {cnt!r}, expected '{i0} of {st['n']}'")
    d.key("Escape")
    d.wait_idle()
    if d.js(_FIND_OPEN):
        fails.append("esc in the find field did not close the bar")
    if not d.js("document.getElementById('ref-mode').classList.contains('open')"):
        fails.append("esc in the find field closed help as well as the bar")
    if d.js("window.CSS && CSS.highlights && CSS.highlights.size") or \
            d.js("document.querySelectorAll('#ref-body mark.find-hit').length"):
        fails.append("closing find left matches painted")
    # Bar open but focus elsewhere: esc still takes the bar first.
    _cmd_f(d)
    d.js("document.activeElement.blur()")
    d.key("Escape")
    d.wait_idle()
    if d.js(_FIND_OPEN) or not d.js(
            "document.getElementById('ref-mode').classList.contains('open')"):
        fails.append("with the bar open and unfocused, esc did not close the "
                     "bar first (and only the bar)")
    # The chat composer keeps ⌘F.
    d.js("rvSetState('open')")
    d.focus("#message")
    _cmd_f(d)
    if d.js(_FIND_OPEN):
        fails.append("⌘F with the caret in the chat composer opened help's find")
    # Mini: the contents list drops over the text and esc folds it first.
    d.js("document.activeElement.blur(); refToggleSize(); refTocToggle(true)")
    _sleep(d, 200)
    sheet = d.js("getComputedStyle(document.getElementById('ref-toc')).position")
    if sheet != "absolute":
        fails.append(f"in mini the contents list is not a sheet ({sheet})")
    d.key("Escape")
    d.wait_idle()
    if not d.js("document.getElementById('ref-toc').hidden"):
        fails.append("esc did not fold the contents sheet")
    if not d.js("document.getElementById('ref-mode').classList.contains('open')"):
        fails.append("esc folded the contents sheet AND closed help")
    _scales(d, 1, 1)
    _reset(d)
    return fails


def scenario_chat_intro(d: Driver) -> list[str]:
    """The empty conversation offers the intro; asking sends `/intro`
    through the chat, the chief's bubble arrives RENDERED, the composer
    comes back, the bubble is full-width on the right in docked and full
    chat, and a reload renders it again from history."""
    fails: list[str] = []
    _reset(d)
    d.js_await("fetch('/api/reset').then(() => true)")
    d.reload()
    d.wait_idle()
    d.js("rvSetState('open')")
    _sleep(d, 200)
    if not d.exists("#empty-hint .intro-link"):
        fails.append("the empty conversation has no 'a brief introduction' link")
        return fails
    d.click("#empty-hint .intro-link")
    try:
        d.wait_for(".msg.intro .body[data-md-rendered] p")
    except StepError:
        fails.append("asking for the intro produced no rendered intro bubble")
        d.js_await("fetch('/api/reset').then(() => true)")
        return fails
    _sleep(d, 400)
    g = d.js("(() => { const m = document.querySelector('.msg.intro');"
             " const b = m.querySelector('.body');"
             " return {user: !!document.querySelector('.msg.user'),"
             " strong: b.querySelectorAll('strong').length,"
             " ws: getComputedStyle(b).whiteSpace,"
             " raw: b.textContent.includes('**'),"
             " off: document.getElementById('message').disabled"
             " || document.getElementById('send-btn').disabled}; })()")
    if not g["user"]:
        fails.append("the /intro request has no user bubble")
    if g["raw"] or not g["strong"]:
        fails.append(f"the intro body is not rendered markdown: {g}")
    if g["ws"] == "pre-wrap":
        fails.append("the intro body keeps pre-wrap (blank lines between paragraphs)")
    if g["off"]:
        fails.append("the composer stayed disabled after the intro")
    for state in ("open", "full"):
        d.js(f"rvSetState('{state}')")
        _sleep(d, 300)
        w = d.js("(() => { const c = document.getElementById('conversation');"
                 " const cs = getComputedStyle(c), r = c.getBoundingClientRect(), z = UIZ();"
                 " const inL = r.left + parseFloat(cs.paddingLeft) * z,"
                 " inR = r.right - parseFloat(cs.paddingRight) * z;"
                 " const m = document.querySelector('.msg.intro').getBoundingClientRect();"
                 " return {inL, inR, mL: m.left, mR: m.right}; })()")
        if abs(w["mR"] - w["inR"]) > 1.5 or abs(w["mL"] - w["inL"]) > 1.5:
            fails.append(f"[{state}] the intro is not full-width on the right: {w}")
    d.js("rvSetState('open')")
    d.reload()
    d.wait_idle()
    _sleep(d, 300)
    if not d.js("!!document.querySelector('.msg.intro .body[data-md-rendered] strong')"):
        fails.append("after a reload the intro is not rendered from history")
    d.js_await("fetch('/api/reset').then(() => true)")
    d.reload()
    d.wait_idle()
    return fails


# --- FEED: the dictionary, the WDL, the context menu (0.4.1, U3) -----------

def _dict_open(d: Driver, word: str | None = None) -> None:
    d.js(DICT_PLAIN[1])
    d.js(f"enterDictMode({json.dumps({'word': word} if word else {})})")
    d.wait_for("#dict-mode.open")
    d.js_await(DICT_READY[1], timeout=25)
    d.wait_idle()


def _dict_page(d: Driver) -> dict:
    return d.js("(() => { const els = Array.from(document.querySelectorAll('#dict-flow .dict-e'));"
                " return {start: DICT.start, fit: DICT.fit, n: els.length,"
                " first: els[0] && els[0].dataset.w, last: els.length ? els[els.length - 1].dataset.w : null,"
                " gl: document.getElementById('dict-gw-l').textContent,"
                " gr: document.getElementById('dict-gw-r').textContent,"
                " next: (document.querySelector('#dict-next .cw') || {}).textContent,"
                " overflowX: document.getElementById('dict-mode').scrollWidth"
                " > document.getElementById('dict-mode').clientWidth + 1}; })()") or {}


def _right_click(d: Driver, root_sel: str, word: str, *, shift: bool = False) -> dict | None:
    """A real right-click (CDP mouse events) on `word` inside `root_sel`."""
    pos = d.js("(() => { const root = document.querySelector(" + json.dumps(root_sel) + ");"
               " if (!root) return null; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);"
               " const re = new RegExp('\\\\b' + " + json.dumps(word) + " + '\\\\b');"
               " for (let n = w.nextNode(); n; n = w.nextNode()) { const m = re.exec(n.data); if (!m) continue;"
               " const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);"
               " const b = r.getBoundingClientRect(); if (!b.width || b.top < 0 || b.bottom > innerHeight) continue;"
               " return {x: b.left + b.width / 2, y: b.top + b.height / 2}; } return null; })()")
    if not pos:
        return None
    mods = 8 if shift else 0
    for typ, buttons in (("mousePressed", 2), ("mouseReleased", 0)):
        d.page.send("Input.dispatchMouseEvent", {"type": typ, "x": pos["x"], "y": pos["y"],
                                                 "button": "right", "buttons": buttons,
                                                 "clickCount": 1, "modifiers": mods})
    _sleep(d, 120)
    return d.js("(() => { const m = document.getElementById('dict-ctx-menu');"
                " return {open: !m.hidden, text: m.innerText}; })()")


def scenario_dict_open_flip(d: Driver) -> list[str]:
    """The launcher in Preferences opens dictionary mode on the stack; the
    page holds whole entries with guide words that match them; → turns to
    the page the foot named and ← comes back to the same page; a resize
    re-paginates without moving the first entry; esc closes the mode."""
    fails: list[str] = []
    _reset(d)
    d.js(DICT_PLAIN[1])
    d.click("#ui-btn")
    d.wait_for("#ui-modal:not(.hidden)")
    d.click("#ui-dict-btn")
    d.wait_for("#dict-mode.open")
    d.js_await(DICT_READY[1], timeout=25)
    d.wait_idle()
    if d.js("modeTop() && modeTop().name") != "dict":
        fails.append(f"the launcher did not push `dict`: {_names(d)}")
    if not d.js("document.getElementById('ui-modal').classList.contains('hidden')"):
        fails.append("Preferences stayed open over the dictionary")
    if d.js("document.querySelector('#mode-stack .mode-indicator[data-mode=\"dict\"] > img.svg-icon:last-child')"
            "?.dataset.icon") != "feed":
        fails.append("the stack indicator is not the feed icon")
    p0 = _dict_page(d)
    if not p0.get("n"):
        fails.append(f"no entries on the first page: {p0}")
        _reset(d)
        return fails
    if p0["gl"] != p0["first"] or (p0["n"] > 1 and p0["gr"] != p0["last"]):
        fails.append(f"guide words {p0['gl']!r}–{p0['gr']!r} are not the page's first/last "
                     f"{p0['first']!r}–{p0['last']!r}")
    if p0["overflowX"]:
        fails.append("dictionary mode overflows horizontally")
    d.focus("#dict-frame")
    d.key("ArrowRight")
    _sleep(d, 250)
    p1 = _dict_page(d)
    if p1.get("start") != p0["start"] + p0["fit"] or p1.get("first") != p0.get("next"):
        fails.append(f"→ went to {p1.get('start')} ({p1.get('first')!r}), not "
                     f"{p0['start'] + p0['fit']} ({p0.get('next')!r})")
    d.key("ArrowLeft")
    _sleep(d, 250)
    if _dict_page(d).get("start") != p0["start"]:
        fails.append(f"← did not come back to the first page: {_dict_page(d)}")
    first = _dict_page(d).get("first")
    d.js("rvSetState('open')")
    _sleep(d, 500)
    after = _dict_page(d)
    if after.get("first") != first:
        fails.append(f"docking the panel moved the page: first {first!r} → {after.get('first')!r}")
    d.js("rvSetState('closed')")
    _sleep(d, 300)
    d.key("Escape")
    d.wait_idle()
    if "dict" in _names(d):
        fails.append("esc did not close dictionary mode")
    _reset(d)
    return fails


def scenario_dict_sorts_rail(d: Driver) -> list[str]:
    """Every sort key (and a sub-sort) draws its group headings and a thumb
    index whose tabs are the server's groups; a tab click turns to that
    group's first entry."""
    fails: list[str] = []
    _reset(d)
    _dict_open(d)
    for sort in ("alpha", "length", "domain", "era", "pos", "frequency", "syllables", "added", "origin"):
        r = d.js_await("(async () => { const s = document.getElementById('dict-s1'); s.value = " + json.dumps(sort) + ";"
                       " s.dispatchEvent(new Event('change')); await new Promise((r) => setTimeout(r, 900));"
                       " const st = dictStore(); return {sort: DICT.view.sort, total: st.total,"
                       " groups: (st.groups || []).length, tabs: document.querySelectorAll('#dict-edge .dict-tab[data-off]').length,"
                       " here: document.querySelectorAll('#dict-edge .dict-tab.here').length,"
                       " n: document.querySelectorAll('#dict-flow .dict-e').length}; })()", timeout=25) or {}
        if r.get("sort") != sort or not r.get("n"):
            fails.append(f"sort {sort}: no page ({r})")
            continue
        if r.get("tabs") != r.get("groups"):
            fails.append(f"sort {sort}: {r.get('tabs')} live tabs for {r.get('groups')} groups")
        if not r.get("here"):
            fails.append(f"sort {sort}: no tab marks the current page")
    r = d.js_await("(async () => { const tabs = document.querySelectorAll('#dict-edge .dict-tab[data-off]');"
                   " const t = tabs[Math.floor(tabs.length / 2)]; t.click(); await new Promise((r) => setTimeout(r, 700));"
                   " return {want: +t.dataset.off, got: DICT.start, here: t.classList.contains('here'),"
                   " gh: !!document.querySelector('#dict-flow .dict-gh')}; })()", timeout=20) or {}
    if r.get("want") != r.get("got") or not r.get("here") or not r.get("gh"):
        fails.append(f"a thumb tab did not open its group with a heading: {r}")
    r = d.js_await("(async () => { Object.assign(DICT.view, {sort: 'domain', dir: 'asc', then: 'era', thenDir: 'asc'});"
                   " dictViewChanged(); await new Promise((r) => setTimeout(r, 900));"
                   " return {keys: document.querySelectorAll('#dict-flow .dict-key, #dict-flow .dict-key-n').length,"
                   " d2: document.getElementById('dict-d2').disabled}; })()", timeout=20) or {}
    if not r.get("keys") or r.get("d2"):
        fails.append(f"domain, then era: no margin keys or the sub-sort direction is off: {r}")
    # Both keys of a two-key order show on every entry (0.4.1, U4), so the
    # order is legible: "length, then era" reads "7 · middle eng.".
    r = d.js_await("(async () => { Object.assign(DICT.view, {sort: 'length', dir: 'asc', then: 'era', thenDir: 'asc'});"
                   " dictViewChanged(); await new Promise((r) => setTimeout(r, 900));"
                   " const es = Array.from(document.querySelectorAll('#dict-flow .dict-e'));"
                   " const two = es.filter((e) => e.querySelector('.dict-key .dict-key-sep, .dict-key-n .dict-key-sep'));"
                   " const k = two[0] && (two[0].querySelector('.dict-key, .dict-key-n') || {}).textContent;"
                   " return {n: es.length, two: two.length, k, len: two[0] && two[0].dataset.w.length}; })()",
                   timeout=20) or {}
    if not r.get("n") or r.get("two", 0) < r.get("n", 1) * 0.8 or not str(r.get("k") or "").startswith(str(r.get("len"))):
        fails.append(f"length, then era: the entries do not show both keys: {r}")
    _reset(d)
    return fails


def scenario_dict_paging(d: Driver) -> list[str]:
    """The folio counts entries, so paging forward never makes it go down;
    ← after a jump (no forward history) draws a FULL page measured backwards
    from the anchor, even when the running entries-per-page estimate is far
    too small; ← near the top turns to the first page, full, from entry 1."""
    fails: list[str] = []
    _reset(d)
    _dict_open(d, "lantern")
    seen = []
    d.focus("#dict-frame")
    for _ in range(6):
        seen.append(d.js("(() => { const n = document.querySelector('#dict-folio .num');"
                         " return n ? +n.textContent.replace(/[^0-9]/g, '') : null; })()"))
        d.key("ArrowRight")
        _sleep(d, 250)
    if None in seen or any(b <= a for a, b in zip(seen, seen[1:])):
        fails.append(f"the folio did not count up while paging forward: {seen}")
    for word in ("gloaming", "zymurgy"):
        r = d.js_await("(async () => { DICT.avg = 4; await dictJumpTo(" + json.dumps(word) + ");"
                       " await new Promise((r) => setTimeout(r, 400)); await dictPrev();"
                       " await new Promise((r) => setTimeout(r, 600));"
                       " const st = dictStore(), s = DICT.start, f = DICT.fit;"
                       " const roomy = s > 0 && dictFitsAll(st, s - 1, s + f);"
                       " await dictShow(s, {keepBack: true, limit: f});"
                       " return {s, f, roomy}; })()", timeout=25) or {}
        if r.get("roomy"):
            fails.append(f"← after a jump to {word!r} left room for another entry: {r}")
    r = d.js_await("(async () => { await dictShow(3); await new Promise((r) => setTimeout(r, 400));"
                   " await dictPrev(); await new Promise((r) => setTimeout(r, 600));"
                   " return {s: DICT.start, f: DICT.fit}; })()", timeout=20) or {}
    if r.get("s") != 0 or (r.get("f") or 0) <= 3:
        fails.append(f"← near the top did not turn to a full first page: {r}")
    _reset(d)
    return fails


def scenario_dict_search_jump(d: Driver) -> list[str]:
    """`/` and ⌘F focus the search; a query replaces the page with matches;
    Return on an exact word turns to that word's page in the current order
    and selects it; esc clears the search and goes back."""
    fails: list[str] = []
    _reset(d)
    _dict_open(d, "lantern")
    before = _dict_page(d).get("start")
    _cmd_f(d)
    _sleep(d, 100)
    if _active(d) != "#dict-q":
        fails.append(f"⌘F in dictionary mode focused {_active(d)}, not the search")
    d.type_text("twilight")
    _sleep(d, 900)
    r = d.js("(() => ({q: DICT.view.q, total: dictStore().total,"
             " hits: document.querySelectorAll('#dict-flow mark, #dict-flow .dict-hw.hit').length}))()") or {}
    if r.get("q") != "twilight" or not r.get("total") or not r.get("hits"):
        fails.append(f"searching did not show marked matches: {r}")
    d.key("Escape")
    _sleep(d, 500)
    r = d.js("(() => ({q: DICT.view.q, start: DICT.start, value: document.getElementById('dict-q').value}))()") or {}
    if r.get("q") or r.get("value") or r.get("start") != before:
        fails.append(f"esc in the search did not clear it and go back: {r} (was at {before})")
    d.focus("#dict-q")
    d.type_text("gloaming")
    d.key("Enter")
    _sleep(d, 1200)
    r = d.js("(() => ({q: DICT.view.q, sel: DICT.sel,"
             " on: !!document.querySelector('#dict-flow .dict-e[data-w=\"gloaming\"]')}))()") or {}
    if r.get("q") or r.get("sel") != "gloaming" or not r.get("on"):
        fails.append(f"Return on an exact word did not turn to its page: {r}")
    _reset(d)
    return fails


def scenario_dict_wdl_a11y(d: Driver) -> list[str]:
    """The word data lightbox is a proper dialog: named, the background out
    of the tree and the tab order, focus in on open, Tab wraps, esc closes
    it (and only it), focus goes back to the page it came from."""
    fails: list[str] = []
    _reset(d)
    _dict_open(d, "lantern")
    d.focus("#dict-frame")
    d.js("(() => { const e = document.querySelector('#dict-flow .dict-e[data-w=\"lantern\"]')"
         " || document.querySelector('#dict-flow .dict-e');"
         " e.dispatchEvent(new MouseEvent('dblclick', {bubbles: true})); return true; })()")
    d.wait_for("#wdl-modal:not(.hidden)")
    d.js_await(WDL_READY[1])
    d.wait_idle()
    if d.js("document.getElementById('wdl-modal').getAttribute('aria-hidden')") != "false":
        fails.append("#wdl-modal: aria-hidden is not 'false' while it is open")
    if not _focus_inside(d, "#wdl-modal"):
        fails.append(f"#wdl-modal: focus stayed on {_active(d)} when it opened")
    fails += _ax_dialog(d, "#wdl-modal")
    left = []
    for i in range(30):
        d.key("Tab")
        if not _focus_inside(d, "#wdl-modal"):
            left.append(f"Tab {i + 1} → {_active(d)}")
    for i in range(8):
        _shift_tab(d)
        if not _focus_inside(d, "#wdl-modal"):
            left.append(f"shift-Tab {i + 1} → {_active(d)}")
    if left:
        fails.append(f"#wdl-modal: focus left the dialog: {left[:5]}")
    d.key("Escape")
    d.wait_gone("#wdl-modal:not(.hidden)")
    d.wait_idle()
    if "dict" not in _names(d):
        fails.append("esc on the lightbox also closed dictionary mode under it")
    if _active(d) != "#dict-frame":
        fails.append(f"closing the lightbox left focus on {_active(d)}, not the page")
    if d.js("document.querySelectorAll('[data-modal-inert]').length"):
        fails.append("the background is still inert after the lightbox closed")
    _reset(d)
    return fails


def scenario_dict_wdl_walk(d: Driver) -> list[str]:
    """Every word in the plate walks it; the walk is kept (trail + back);
    ←/→ step through the current order; a form resolves to its headword;
    a word FEED lacks gets the not-found plate with where it would fall;
    "show on its page" turns the dictionary to the word."""
    fails: list[str] = []
    _reset(d)
    _dict_open(d)
    d.js("wdlOpen('gloaming', {fromDict: true})")
    d.wait_for("#wdl-modal:not(.hidden)")
    d.js_await(WDL_READY[1])
    _sleep(d, 400)
    d.click("#wdl-scroll .wdl-w[data-go=\"twilight\"]")
    d.js_await(WDL_READY[1])
    _sleep(d, 300)
    r = d.js("(() => ({hw: document.getElementById('wdl-hw').textContent, stack: WDL.stack.slice(),"
             " crumbs: document.querySelectorAll('#wdl-trail [data-trail]').length,"
             " back: !document.getElementById('wdl-back').disabled}))()") or {}
    if r.get("hw") != "twilight" or r.get("stack") != ["gloaming", "twilight"] or not r.get("crumbs") or not r.get("back"):
        fails.append(f"clicking a synonym did not walk the plate: {r}")
    d.click("#wdl-back")
    d.js_await(WDL_READY[1])
    _sleep(d, 400)
    if d.js("document.getElementById('wdl-hw').textContent") != "gloaming":
        fails.append("back did not return to gloaming")
    nxt = d.js("WDL.nb && WDL.nb.next")
    d.focus("#wdl-scroll")
    d.key("ArrowRight")
    d.js_await(WDL_READY[1])
    _sleep(d, 400)
    if not nxt or d.js("document.getElementById('wdl-hw').textContent") != nxt:
        fails.append(f"→ did not step to the next entry {nxt!r}")
    d.js("wdlNav('gloamings')")
    d.js_await(WDL_READY[1])
    _sleep(d, 300)
    r = d.js("(() => ({hw: document.getElementById('wdl-hw').textContent,"
             " note: (document.querySelector('.wdl-matched') || {}).textContent || ''}))()") or {}
    if r.get("hw") != "gloaming" or "gloamings" not in r.get("note", ""):
        fails.append(f"a form did not resolve to its headword with a note: {r}")
    d.js("wdlNav('glomrify')")
    d.js_await(WDL_READY[1])
    _sleep(d, 600)
    r = d.js("(() => ({missing: !!document.querySelector('.wdl-hw.missing'),"
             " where: (document.getElementById('wdl-where') || {}).textContent || ''}))()") or {}
    # the sentence is translated; the neighbouring words (glom…) are not
    if not r.get("missing") or "glom" not in r.get("where", ""):
        fails.append(f"the not-found plate did not say where it would fall: {r}")
    d.js("wdlNav('lantern')")
    d.js_await(WDL_READY[1])
    _sleep(d, 300)
    d.click("#wdl-show")
    _sleep(d, 900)
    r = d.js("(() => ({wdl: wdlIsOpen(), top: modeTop() && modeTop().name, sel: DICT.sel,"
             " on: !!document.querySelector('#dict-flow .dict-e[data-w=\"lantern\"]')}))()") or {}
    if r.get("wdl") or r.get("top") != "dict" or r.get("sel") != "lantern" or not r.get("on"):
        fails.append(f"show on its page did not turn the dictionary to the word: {r}")
    _reset(d)
    return fails


def scenario_dict_context_menu(d: Driver) -> list[str]:
    """Right-click on a word: the dictionary-entry menu (read face → WDL over
    it; dictionary → turns to the word; WDL → walks there). Right-click with
    shift, or off any word, leaves the system menu alone."""
    fails: list[str] = []
    _reset(d)
    d.js(f"openReadEdit('{DOC}', {{size:'full', face:'read'}})")
    d.wait_for("#review-mode.open")
    d.wait_idle()
    m = _right_click(d, "#review-body", "paragraph")
    if not m or not m.get("open") or "paragraph" not in m.get("text", ""):
        fails.append(f"no dictionary menu on a word in the read face: {m}")
    else:
        d.click("#dict-ctx-menu .ctx-item[data-act=\"entry\"]")
        d.wait_for("#wdl-modal:not(.hidden)")
        d.js_await(WDL_READY[1])
        if d.js("document.getElementById('wdl-hw').textContent") != "paragraph":
            fails.append("the menu did not open the lightbox on the word")
        if d.js("modeTop() && modeTop().name") != "readedit":
            fails.append("the lightbox changed the mode stack under it")
        m = _right_click(d, "#wdl-scroll .wdl-def", "text")
        if m and m.get("open"):
            d.click("#dict-ctx-menu .ctx-item[data-act=\"entry\"]")
            d.js_await(WDL_READY[1])
            _sleep(d, 300)
            if d.js("WDL.stack.slice(-1)[0]") != "text":
                fails.append("the menu inside the lightbox did not walk it")
        else:
            fails.append(f"no dictionary menu on a word inside the lightbox: {m}")
        d.js("wdlClose()")
    m = _right_click(d, "#review-body", "paragraph", shift=True)
    if m and m.get("open"):
        fails.append("shift-right-click opened the dictionary menu instead of the system one")
    off = d.js("(() => { const b = document.getElementById('review-body').getBoundingClientRect();"
               " return {x: b.right - 6, y: b.bottom - 6}; })()")
    for typ, buttons in (("mousePressed", 2), ("mouseReleased", 0)):
        d.page.send("Input.dispatchMouseEvent", {"type": typ, "x": off["x"], "y": off["y"],
                                                 "button": "right", "buttons": buttons, "clickCount": 1})
    _sleep(d, 120)
    if d.js("!document.getElementById('dict-ctx-menu').hidden"):
        fails.append("a right-click off any word opened the dictionary menu")
    d.js("dictCtxClose()")
    _reset(d)
    _dict_open(d, "lambent")
    m = _right_click(d, "#dict-flow .dict-e[data-w=\"lambent\"]", "candlelight")
    if not m or not m.get("open"):
        fails.append(f"no dictionary menu on a word in the dictionary: {m} "
                     f"(page {_dict_page(d)}, rv {_rv(d)})")
    else:
        d.click("#dict-ctx-menu .ctx-item[data-act=\"entry\"]")
        _sleep(d, 900)
        r = d.js("(() => ({sel: DICT.sel, on: !!document.querySelector('#dict-flow .dict-e[data-w=\"candlelight\"]'),"
                 " wdl: wdlIsOpen()}))()") or {}
        if r.get("sel") != "candlelight" or not r.get("on") or r.get("wdl"):
            fails.append(f"the menu in the dictionary did not turn to the word: {r}")
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
    "composure-council-pal": scenario_composure_council_pal,
    "composure-council-reconvene": scenario_composure_council_reconvene,
    # --- `/pal` (P8) ---
    "pal-hint-row": scenario_pal_hint_row,
    "pal-gate-closed": scenario_pal_gate_closed,
    "pal-bubbles": scenario_pal_bubbles,
    "composure-inspector-is-clickable":
        scenario_composure_inspector_is_clickable,
    # --- 0.4.1 polish (U1) ---
    "chat-sides": scenario_chat_sides,
    "chat-tool-chip": scenario_chat_tool_chip,
    "topbar-no-collisions": scenario_topbar_no_collisions,
    "composure-autofit": scenario_composure_autofit,
    # --- 0.4.1 modal a11y + help find/contents + intro (U2) ---
    "modal-prefs-a11y": scenario_modal_prefs_a11y,
    "modal-broker-a11y": scenario_modal_broker_a11y,
    "modal-return-after-open": scenario_modal_return_after_open,
    "modal-confirm-stack": scenario_modal_confirm_stack,
    "ref-find-contents": scenario_ref_find_contents,
    "chat-intro": scenario_chat_intro,
    # --- 0.4.1 FEED: dictionary mode, the WDL, the context menu (U3) ---
    "dict-open-flip": scenario_dict_open_flip,
    "dict-sorts-rail": scenario_dict_sorts_rail,
    "dict-paging": scenario_dict_paging,
    "dict-search-jump": scenario_dict_search_jump,
    "dict-wdl-a11y": scenario_dict_wdl_a11y,
    "dict-wdl-walk": scenario_dict_wdl_walk,
    "dict-context-menu": scenario_dict_context_menu,
}
