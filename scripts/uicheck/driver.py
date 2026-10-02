"""The step executor: what turns a `Screen`'s declarative recipe into CDP.

`screens.py` says *what* a screen is; this says *how*. Keeping them apart is
what lets the registry stay readable enough that the next phase of the round
will actually add to it.

Two rules govern everything here:

* **Never sleep for time.** Every wait is a condition poll — a selector that
  appears, a selector that goes away, or the page's own `__uicheck.idle()`
  (two consecutive animation frames with an unchanged layout signature). A
  fixed sleep is either too short on a cold machine or wasted on a warm one,
  and the full matrix runs a few hundred of them.
* **Drive the product's own entry points.** `click` dispatches the element's
  real click, `key` goes through `Input.dispatchKeyEvent` so the document's
  key handlers see a genuine event, and an `eval` step calls
  `openUIModal()` / `enterGirraphMode(path)` rather than toggling classes.
  A harness that reaches past the UI's own functions ends up testing itself.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from pathlib import Path

from .cdp import CDPError, Page

PROBES_JS = (Path(__file__).resolve().parent / "probes.js").read_text(encoding="utf-8")

# --- the hard ceilings -----------------------------------------------------
#
# Every call below already has a deadline of its own, and that was not
# enough: "bounded" and "cannot hang" are different claims, and the suite
# ran into the difference twice (P4c-1's known gap 10, P5c's note). A
# `recv` inside a C call, a `send` into a socket buffer that never drains,
# a browser process stopped dead by a dialog in a tab nobody is reading —
# none of those are reached by a `deadline` parameter.
#
# So there is a watchdog, and it is deliberately blunt: when the budget
# expires it closes the page's WebSocket from another thread, which makes
# whatever the main thread is blocked on raise. A wedge then costs one
# named FAIL and a screenshot instead of a run that never ends. The
# pre-commit hook runs `--quick`; a hook that can hang is a hook that gets
# uninstalled.
#
# The numbers are ceilings, not budgets to spend: a healthy step is under a
# second and a healthy scenario under ten. They are generous enough that a
# cold machine under load never trips them.
STEP_BUDGET_S = 45.0
SCENARIO_BUDGET_S = 150.0


class Wedged(RuntimeError):
    """The watchdog fired: this page never came back and was cut loose."""


@contextlib.contextmanager
def watchdog(page: Page, seconds: float, what: str):
    """Give the block `seconds` of wall clock, then break the page's socket.

    `threading.Timer` rather than `signal.alarm`: the harness has to work
    when it is driven from pytest or from a thread that is not the main one,
    and SIGALRM is main-thread-only. Closing the socket is the only lever
    that reaches a thread blocked inside the websocket library.
    """
    fired: list[bool] = []

    def trip() -> None:
        fired.append(True)
        page.abort()

    timer = threading.Timer(seconds, trip)
    timer.daemon = True
    timer.start()
    try:
        yield
    except BaseException as e:                                   # noqa: BLE001
        if fired:
            raise Wedged(f"{what}: no answer within {seconds:.0f}s — the page "
                         f"was cut loose ({type(e).__name__}: {e})") from e
        raise
    finally:
        timer.cancel()
    if fired:
        raise Wedged(f"{what}: exceeded its {seconds:.0f}s budget")

# Keys the scenarios press, with the fields Chrome insists on. `text` is
# omitted on purpose for non-printing keys — supplying it makes Chrome treat
# them as character input.
#
# `rawKeyDown` for a key with no `text`, `keyDown` for one that has it —
# puppeteer's own rule, and it is not cosmetic in either direction.
# `keyDown` asks Chrome to produce a char event, which a non-printing key has
# no business doing; `rawKeyDown` produces none, which is why Enter (whose
# `text` is "\r") MUST stay `keyDown` — sent raw, it moves the caret without
# inserting the newline, and `composure-input-rules` typed
# "bullet1. numbered" onto one line and failed. (Neither type is what fixed
# the Escape wedge — see `_SYNTHETIC_KEYS` — and the two were confused once
# already.)
def _key_down_type(spec: dict) -> str:
    return "keyDown" if spec.get("text") else "rawKeyDown"

#: Keys that must NOT go through `Input.dispatchKeyEvent`.
#:
#: **Escape deadlocks headless Chrome.** On a tab the browser has ACTIVATED
#: — which is every tab `/json/new` opens, and every tab `recover()` opens
#: after it — an `Input.dispatchKeyEvent` carrying Escape stops the browser
#: process dead: that tab stops answering, so does every other tab, and so
#: does the DevTools HTTP endpoint, so the harness cannot even throw the tab
#: away and open a fresh one. Measured on Chrome 152 headless (macOS) on a
#: bare `data:text/html` page with no application on it at all — three
#: Escapes and the browser is gone. Tab, in the same loop, is fine forty
#: times out of forty.
#:
#: That is the `--quick` wedge P4c-1 and P5c both reported: it always landed
#: on an esc scenario or on a modal screen whose teardown is esc, it
#: reproduced with `#composure` removed, and it is nothing enough does.
#: Focus emulation instead of `Page.bringToFront` (see `Driver.front`) makes
#: it much rarer but does not remove it, because `/json/new` activates the
#: tab it opens.
#:
#: So Escape is dispatched from inside the page. See `_key_in_page` for what
#: that does and does not still prove. Every other key keeps the real input
#: pipeline.
_SYNTHETIC_KEYS = frozenset({"Escape"})

_KEYS = {
    "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27,
               "nativeVirtualKeyCode": 27},
    "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
              "nativeVirtualKeyCode": 13, "text": "\r"},
    "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9,
            "nativeVirtualKeyCode": 9},
    # FEED (0.4.1): the dictionary turns pages and the WDL walks entries.
    "ArrowRight": {"key": "ArrowRight", "code": "ArrowRight",
                   "windowsVirtualKeyCode": 39, "nativeVirtualKeyCode": 39},
    "ArrowLeft": {"key": "ArrowLeft", "code": "ArrowLeft",
                  "windowsVirtualKeyCode": 37, "nativeVirtualKeyCode": 37},
    "ArrowDown": {"key": "ArrowDown", "code": "ArrowDown",
                  "windowsVirtualKeyCode": 40, "nativeVirtualKeyCode": 40},
    "Backspace": {"key": "Backspace", "code": "Backspace",
                  "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8},
}


class StepError(RuntimeError):
    """A screen's recipe did not work — names the step that broke."""


class Driver:
    """One page, plus the vocabulary the screens and scenarios speak."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    # -- page lifecycle -------------------------------------------------
    #: "enough's inline script has finished executing". A `const` is the only
    #: honest probe: function declarations are hoisted for the whole script
    #: before its first statement runs, so `typeof enterCacheawlMode` is
    #: already 'function' while the boot code is still halfway down the file.
    #: `UI_SCALES` is a top-level `const`, so reading it throws until
    #: execution actually reaches the declaration.
    READY = ("(() => { try { return typeof UI_SCALES === 'object'; } "
             "catch (e) { return false; } })()")

    #: …and "the page has finished BOOTING", which is a later moment.
    #:
    #: A project page's base layer is a composure, and `compBoot()` opens it
    #: asynchronously — a `fetch('/api/composure/launch')` and then an
    #: `await compOpenNew(form)`. `READY` goes true well before that lands.
    #: A screen recipe that opened its own form in between would resolve,
    #: then be CLOBBERED by boot's own adopt a beat later (`COMP_OPEN_SEQ`
    #: hands the document to whoever asked last), and the recipe's in-page
    #: poll would then spin for its whole six-second ceiling waiting for a
    #: module that was never coming.
    #:
    #: That is where `--quick`'s wall clock went — a dozen composure screens
    #: a run at 6.6s each — and, worse, each of those screens then MEASURED
    #: a blank composure under the name of a form. Waiting here costs about
    #: 40ms and is the difference between the suite checking the UI and the
    #: suite checking a blank page. The home page has no composure and says
    #: so through `IS_HOME`.
    BOOTED = ("(() => { try { if (window.IS_HOME) return true;"
              " return !!(window.COMP && window.COMP.ready); }"
              " catch (e) { return true; } })()")

    def front(self) -> None:
        """Give THIS tab focus, so its animation frames keep running.

        Chrome throttles an unfocused tab down to no animation frames at
        all, so the "wait until the layout settles" probe there burns its
        whole budget on every call — 2.5s a wait against 0.06s. The harness
        drives two tabs (project and home), so without this exactly one of
        them is always the slow one.

        **NOT `Page.bringToFront`, and this is the whole `--quick` wedge.**
        `bringToFront` ACTIVATES the tab in the browser UI, and on an
        activated tab an `Input.dispatchKeyEvent` carrying **Escape**
        deadlocks Chrome's browser process: the tab stops answering, so
        does every other tab, and so does the DevTools HTTP endpoint, so
        the harness cannot even throw the tab away and open a new one.
        Measured on Chrome 152 headless, macOS, on a bare
        `data:text/html` page with no application on it at all:

            bringToFront + Escape  →  dead at the 3rd Escape, permanently
            no focus call + Escape →  30/30 fine, but every wait_idle 2.50s
            focus emulation + Esc  →  30/30 fine, wait_idle 0.10s

        That is why P4c-1 could reproduce it with `#composure` removed and
        why it always landed on the esc scenarios: the wedge is Escape plus
        an activated tab, not anything enough does. Focus emulation gives
        the renderer the same "you are focused" signal without going near
        the browser UI. Exactly one page may have it — telling two tabs at
        once that they have focus is what the P0 note warned about — so
        `unfocus()` is called on the others.
        """
        self._focus_emulation(True)

    def unfocus(self) -> None:
        """Hand focus back, so exactly one tab claims it at a time."""
        self._focus_emulation(False)

    def _focus_emulation(self, on: bool) -> None:
        try:
            self.page.send("Emulation.setFocusEmulationEnabled",
                           {"enabled": bool(on)})
        except CDPError:
            # An old Chromium without the command: the tab is merely
            # throttled, which is slow and safe. Never fall back to
            # `bringToFront` — that is the thing that wedges.
            pass

    def load(self) -> None:
        self.page.navigate(self.base_url + "/", ready=self.READY)
        self.after_load()

    def reload(self) -> None:
        self.page.reload(ready=self.READY)
        self.after_load()

    def after_load(self) -> None:
        """Re-inject the probes and wait for the app's boot fetches.

        `__uicheck` lives on `window`, so it evaporates on every navigation;
        re-installing it here rather than at each call site is the only
        reason the rest of this module can assume it exists.
        """
        self.page.evaluate(PROBES_JS, await_promise=False)
        self.wait_booted()
        self.wait_idle()

    def wait_booted(self, *, timeout: float = 20.0) -> None:
        """Poll `BOOTED`. Never raises: a page that cannot answer this has a
        louder problem, and the step that follows will report it."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.page.evaluate(self.BOOTED, await_promise=False,
                                      timeout=8):
                    return
            except CDPError:
                return
            time.sleep(0.02)

    # -- primitives -----------------------------------------------------
    def js(self, expression: str, *, timeout: float | None = None):
        """Evaluate and return, WITHOUT awaiting a returned promise.

        This matters more than it looks. `confirmOverlay()` returns a promise
        that settles when the *user* answers, so awaiting it hangs the
        harness forever; several `enter*Mode()` functions are `async` and
        settle only after a fetch. An `eval` step is a trigger, and the
        `wait_for` step after it is the wait — that split is the whole reason
        the recipes are two verbs instead of one.
        """
        wrapped = (f"(function () {{ var __v = ({expression});"
                   f" return (__v && typeof __v.then === 'function')"
                   f" ? '[promise]' : __v; }})()")
        try:
            return self.page.evaluate(wrapped, await_promise=False,
                                      timeout=timeout)
        except CDPError as e:
            if "SyntaxError" not in str(e):
                raise
            # An `eval` step that is a statement rather than an expression
            # (`if (x) y;`). Re-run it as a function body so a screen author
            # does not have to remember which one they wrote — but the value
            # is lost, which is why expressions stay the documented form.
            return self.page.evaluate(
                f"(function () {{ {expression}; return true; }})()",
                await_promise=False, timeout=timeout)

    def js_await(self, expression: str, *, timeout: float = 20.0):
        """Evaluate and await. Only for expressions known to settle."""
        return self.page.evaluate(f"(async () => ({expression}))()",
                                  await_promise=True, timeout=timeout)

    def exists(self, selector: str) -> bool:
        return bool(self.page.evaluate(
            f"!!document.querySelector({json.dumps(selector)})",
            await_promise=False))

    def wait_for(self, selector: str, *, timeout: float = 8.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.exists(selector):
                return
            time.sleep(0.02)
        raise StepError(f"selector never appeared: {selector}")

    def wait_gone(self, selector: str, *, timeout: float = 8.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.exists(selector):
                return
            time.sleep(0.02)
        raise StepError(f"selector never went away: {selector}")

    def wait_idle(self, *, timeout: float = 20.0) -> None:
        try:
            self.page.evaluate(
                "window.__uicheck ? window.__uicheck.idle() : Promise.resolve(true)",
                timeout=timeout)
        except CDPError:
            # An idle probe that times out is not itself a finding; the
            # measurement that follows is what matters.
            pass

    def click(self, selector: str) -> None:
        hit = self.page.evaluate(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            f" if (!el) return false; el.click(); return true; }})()",
            await_promise=False)
        if not hit:
            raise StepError(f"nothing to click: {selector}")

    def key(self, name: str) -> None:
        spec = _KEYS.get(name)
        if spec is None:
            raise StepError(f"unknown key: {name}")
        if name in _SYNTHETIC_KEYS:
            self._key_in_page(spec)
            return
        self.page.send("Input.dispatchKeyEvent",
                       {"type": _key_down_type(spec), **spec})
        self.page.send("Input.dispatchKeyEvent", {"type": "keyUp", **spec})

    def _key_in_page(self, spec: dict) -> None:
        """Dispatch a key from INSIDE the page instead of through the browser.

        Reserved for Escape, and only because Chrome leaves no other option —
        see `_SYNTHETIC_KEYS`. The event is built on `document.activeElement`
        with `bubbles`, `cancelable` and `composed`, so it capture-phases and
        bubbles through exactly the listeners a real one would: every esc
        handler enough has is a `document.addEventListener('keydown', …)`,
        several of them capture-phase, and `preventDefault()` /
        `stopPropagation()` behave identically on a cancelable synthetic
        event. What is NOT exercised is Chrome's own default action for the
        key and `isTrusted` — neither of which enough's esc order consults.
        """
        init = {"key": spec["key"], "code": spec["code"],
                "keyCode": spec["windowsVirtualKeyCode"],
                "which": spec["windowsVirtualKeyCode"],
                "bubbles": True, "cancelable": True, "composed": True}
        payload = json.dumps(init)
        ok = self.page.evaluate(
            f"(() => {{ const init = {payload};"
            f" const el = document.activeElement || document.body;"
            f" el.dispatchEvent(new KeyboardEvent('keydown', init));"
            f" el.dispatchEvent(new KeyboardEvent('keyup', init));"
            f" return true; }})()", await_promise=False)
        if not ok:
            raise StepError(f"could not dispatch {spec['key']} in the page")

    def focus(self, selector: str) -> None:
        ok = self.page.evaluate(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            f" if (!el) return false; el.focus(); return document.activeElement === el; }})()",
            await_promise=False)
        if not ok:
            raise StepError(f"could not focus: {selector}")

    def type_text(self, text: str) -> None:
        self.page.send("Input.insertText", {"text": text})

    def set_viewport(self, vp) -> None:
        self.page.set_viewport(vp.w, vp.h, vp.dpr)

    # The belt-and-braces reset run after every screen, whatever its own
    # teardown did. Screens are measured back to back on one page for speed,
    # so a teardown that half-worked would silently contaminate every screen
    # after it — which is exactly what happened before this existed: one
    # modal that does not answer esc, and twenty later screens measuring a
    # UI with a dialog still open on top of it.
    #
    # It closes through the product's own `modeRemove()` where there is one,
    # and falls back to the `.hidden` class the modal convention is built on.
    # Teardown is the one place reaching past the UI's functions is fair:
    # nothing is being asserted here, only cleaned.
    _RESET_JS = """(function () {
      // Exit each stacked mode the way the user does — through its own
      // indicator ribbon, which runs that mode's `onExit`. `modeRemove()`
      // only does the stack's bookkeeping, so a mode torn down that way
      // leaves its render loop running behind a hidden element; a dozen
      // screens of that and the renderer stops answering. The direct
      // `modeRemove` below is the fallback for anything the ribbons missed.
      Array.from(document.querySelectorAll(
        '#mode-stack .mode-indicator .mode-ribbon')).reverse()
        .forEach(function (b) { try { b.click(); } catch (e) {} });
      try { if (window.wdlClose) wdlClose(); } catch (e) {}
      ['readedit','girraph','merirmaid','wikisink','cacheawl','ref',
       'paginated','blobview','dict'].forEach(function (n) {
        try { modeRemove(n); } catch (e) {}
      });
      document.querySelectorAll('[id$="-modal"]').forEach(function (m) {
        m.classList.add('hidden');
      });
      // The confirm overlay is the one dialog that does NOT use the
      // `.hidden` class convention — it toggles the `hidden` ATTRIBUTE, and
      // it parks a promise resolver until someone answers. Clicking cancel
      // settles that promise the way the product does; the attribute is
      // belt and braces.
      try { document.getElementById('confirm-cancel')?.click(); } catch (e) {}
      var c = document.getElementById('confirm-overlay');
      if (c) c.hidden = true;
      try { if (window.closeHelp) closeHelp(); } catch (e) {}
      try { if (window.paginateClose) paginateClose(); } catch (e) {}
      var p = document.getElementById('preview');
      if (p) p.classList.remove('open');
      ['review-mode','edit-mode','girraph-mode','merirmaid-mode','wiki-mode',
       'cacheawl-mode','ref-mode','paginated-mode','dict-mode'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.classList.remove('open');
      });
      return true;
    })()"""

    def reset_page(self, *, settle: bool = True) -> None:
        """Force the UI back to the ground floor.

        `settle=False` skips the "wait for the layout to stop moving" pass,
        and is for the one caller that is about to navigate away: waiting
        for a document to settle and then throwing it away is ~50ms a
        screen, which is two and a half minutes across the full matrix.
        """
        try:
            self.page.evaluate(self._RESET_JS, await_promise=False, timeout=10)
            if settle:
                self.wait_idle()
        except CDPError:
            pass

    def native_dialogs(self, *, clear: bool = True) -> list[dict]:
        """Every native dialog the page tried to raise since the last read.

        `probes.js` traps `alert`/`confirm`/`prompt` so one can never stop
        the browser process; this is how the run still gets to SAY that a
        screen hit an error path. Never raises: a page that cannot answer
        this has bigger problems, and they are reported elsewhere.
        """
        try:
            return self.page.evaluate(
                f"(window.__uicheck ? __uicheck.nativeDialogs({str(clear).lower()})"
                f" : [])", await_promise=False, timeout=5) or []
        except CDPError:
            return []

    # -- recipes --------------------------------------------------------
    def run_steps(self, steps, *, what: str,
                  budget: float = STEP_BUDGET_S) -> None:
        for i, (verb, arg) in enumerate(steps):
            try:
                with watchdog(self.page, budget, f"{what}: step {i} ({verb})"):
                    self._one_step(verb, arg)
            except (StepError, CDPError, Wedged) as e:
                raise StepError(f"{what}: step {i} ({verb} {arg!r}) failed: {e}") from e

    def _one_step(self, verb: str, arg: str) -> None:
        if verb == "click":
            self.click(arg)
        elif verb == "key":
            self.key(arg)
        elif verb == "eval":
            self.js(arg)
        elif verb == "eval_await":
            # For an entry point that RETURNS a promise and settles on its
            # own — `compOpenNew(form)` resolves once the document has been
            # adopted. Plain `eval` fires and forgets, which is right for
            # `confirmOverlay()` (its promise waits for a human) and wrong
            # here: two opens in flight at once meant the recipe after the
            # step ran against the document that was about to be replaced.
            self.js_await(arg)
        elif verb == "wait_for":
            self.wait_for(arg)
        elif verb == "wait_gone":
            self.wait_gone(arg)
        elif verb == "wait_idle":
            self.wait_idle()
        else:
            raise StepError(f"unknown step verb {verb!r}")

    # -- measurement ----------------------------------------------------
    def measure(self) -> dict:
        return self.page.evaluate("window.__uicheck.measure()", await_promise=False)

    def mode_stack(self) -> dict:
        return self.page.evaluate("window.__uicheck.modeStack()", await_promise=False)

    def modals_open(self) -> list[str]:
        return self.page.evaluate("window.__uicheck.modalOpen()", await_promise=False)

    def i18n_snapshot(self) -> dict[str, str]:
        return self.page.evaluate("window.__uicheck.i18nSnapshot()", await_promise=False)

    def screenshot(self, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.page.screenshot_png())
