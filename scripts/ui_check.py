#!/usr/bin/env python3
"""The browser stage of the pre-commit suite: layout and mode-stack drift.

    uv run python scripts/ui_check.py              # the full matrix
    uv run python scripts/ui_check.py --quick      # 3 viewports x 3 languages
    uv run python scripts/ui_check.py --update-baseline
    uv run python scripts/ui_check.py --screens read-full,girraph -v

What it does: boots two scratch enough servers (a project one and a home
one) through the real `python -m enough` entry, drives a headless Chrome
over the DevTools Protocol, and for every
(screen x viewport x language) asks the page to measure itself — which
clickables are covered, which overlap, which text is clipped, which controls
fell outside the viewport, which targets are under 16px. Then it runs the
MODE STACK scenarios once per language.

**Zero new dependencies.** CDP is JSON over one WebSocket and `websockets`
is already locked in as a transitive of `uvicorn[standard]`; that is the
whole reason this is a few hundred lines instead of a playwright install.

**Nothing real is touched.** Both servers run under
`smoke_boot.build_env()`: every `ENOUGH_*` seam and `$HOME` point into a
temp dir, and `--llm-url` gets a port nothing is listening on, so a run can
never adopt or kill the developer's llama-server. The UI language is flipped
through `POST /api/ui-config`, which writes into that scratch `$HOME` and
not into the developer's `~/enough/config/ui.json`.

**It degrades.** No Chrome anywhere → one clear SKIPPED line and exit 0. CI
has no guarantee of a browser, and a check that cannot run is not a check
that failed.

Output: a human summary on stdout, the full report at
`.pytest_cache/ui-check/report.json`, and a PNG per failing
(screen, viewport, language) under `.pytest_cache/ui-check/shots/`.

Findings that already exist in today's tree live in
`scripts/uicheck/baseline.json`, keyed by selector path rather than by
pixels, so only NEW ones fail. Read that file's `_doc` before regenerating
it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from uicheck import screens as screens_mod                       # noqa: E402
from uicheck.cdp import Browser, CDPError, find_chrome, stray_debug_processes  # noqa: E402
from uicheck.driver import (SCENARIO_BUDGET_S, Driver,           # noqa: E402
                            StepError, Wedged, watchdog)
from uicheck.findings import (Finding, FindingSet, from_measurement,  # noqa: E402
                              load_baseline, write_baseline)
from uicheck.interactions import SCENARIOS                       # noqa: E402
from uicheck.screens import (INTERACTION_VIEWPORT, LANGUAGES, QUICK_LANGUAGES,
                             QUICK_VIEWPORTS, VIEWPORTS, Screen, Viewport,
                             screens_for, tauri_min_viewport)    # noqa: E402
from uicheck.server import ScratchWorld                          # noqa: E402

OUT_DIR = REPO / ".pytest_cache" / "ui-check"
SHOTS_DIR = OUT_DIR / "shots"


# ---------------------------------------------------------------------------
# Matrix assembly
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    viewports: list[Viewport]
    languages: tuple[str, ...]
    screens: list[Screen]
    scenarios: tuple[str, ...]


def build_plan(args: argparse.Namespace) -> Plan:
    viewports = list(QUICK_VIEWPORTS if args.quick else VIEWPORTS)
    if not args.quick:
        conf = REPO / "desktop" / "src-tauri" / "tauri.conf.json"
        if conf.is_file():
            extra = tauri_min_viewport(json.loads(conf.read_text(encoding="utf-8")))
            if extra and extra.name not in {v.name for v in viewports}:
                viewports.append(extra)
    langs = QUICK_LANGUAGES if args.quick else LANGUAGES
    if args.langs:
        want = tuple(x.strip() for x in args.langs.split(",") if x.strip())
        unknown = set(want) - set(LANGUAGES)
        if unknown:
            raise SystemExit(f"unknown language(s): {', '.join(sorted(unknown))}")
        langs = want
    if args.viewports:
        want_vp = {x.strip() for x in args.viewports.split(",") if x.strip()}
        viewports = [v for v in VIEWPORTS if v.name in want_vp]
        if not viewports:
            raise SystemExit(f"no known viewport matched {args.viewports!r}; "
                             f"names are "
                             f"{', '.join(v.name for v in VIEWPORTS)}")

    chosen = screens_mod.ALL_SCREENS
    if args.screens:
        want = {s.strip() for s in args.screens.split(",") if s.strip()}
        chosen = [s for s in chosen if s.name in want]
        missing = want - {s.name for s in chosen}
        if missing:
            raise SystemExit(f"unknown screen(s): {', '.join(sorted(missing))}")
    scenarios = tuple(SCENARIOS) if not args.no_scenarios else ()
    return Plan(viewports, tuple(langs), list(chosen), scenarios)


# ---------------------------------------------------------------------------
# One pass over one mode
# ---------------------------------------------------------------------------

def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)


def _is_wedged(err: Exception) -> bool:
    """Does this failure mean the tab stopped answering, rather than that a
    selector was wrong? A silent renderer is unrecoverable in place."""
    text = str(err)
    return ("no reply within" in text or "timed out after" in text
            or "was cut loose" in text or "exceeded its" in text)


class Run:
    def __init__(self, plan: Plan, *, verbose: bool, shots: bool) -> None:
        self.plan = plan
        self.verbose = verbose
        self.shots = shots
        self.findings = FindingSet()
        self.errors: list[str] = []
        self.screens_run = 0
        self.shots_taken: list[str] = []
        self.browser: Browser | None = None
        self.drivers: dict[str, Driver] = {}
        #: Screens measured on the current tab, per mode. See TAB_LIFETIME.
        self.on_tab: dict[str, int] = {}

    #: Replace each tab after this many screens, before anything goes wrong.
    #: Every screen already starts from a reloaded page, but a reload does
    #: not reclaim everything a renderer accumulates, and a long enough run
    #: eventually finds a tab that stops answering CDP under load. A fresh
    #: tab costs about a third of a second; a wedged one costs a twelve
    #: second timeout and a gap in the matrix. This is the cheap side of
    #: that trade, and it is why a run should show no recoveries at all.
    TAB_LIFETIME = 10

    def recover(self, mode: str) -> Driver:
        """Replace a page whose renderer stopped answering.

        A screen that wedges its tab — a spinning script, a modal dialog we
        did not get to first — otherwise poisons every screen after it, and
        the symptom (thirty seconds of silence, repeated) tells you nothing
        about where it started. Throwing the tab away and opening a fresh
        one turns that into one named harness error and a run that finishes.
        """
        old = self.drivers[mode]
        assert self.browser is not None
        self.browser.close_page(old.page)
        fresh = Driver(self.browser.new_page(), old.base_url)
        self.drivers[mode] = fresh
        self.on_tab[mode] = 0
        self.focus(mode)
        fresh.load()
        return fresh

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"    {msg}", flush=True)

    # -- layout ---------------------------------------------------------
    def sweep(self, mode: str, lang: str) -> None:
        todo = [s for s in self.plan.screens if s.mode == mode]
        if not todo:
            return
        for vp in self.plan.viewports:
            driver = self.focus(mode)
            try:
                driver.set_viewport(vp)
                driver.wait_idle()
            except CDPError:
                driver = self.recover(mode)
                driver.set_viewport(vp)
            for screen in todo:
                if self.on_tab.get(mode, 0) >= self.TAB_LIFETIME:
                    driver = self.recover(mode)
                    driver.set_viewport(vp)
                self.on_tab[mode] = self.on_tab.get(mode, 0) + 1
                self.pump_idle_tabs(mode)
                if not self.one_screen(driver, screen, vp, lang):
                    driver = self.recover(mode)
                    driver.set_viewport(vp)
            if mode == "project" and any(s.name == "project-base" for s in todo):
                self.one_scaled_base(driver, vp, lang)

    def one_scaled_base(self, driver: Driver, vp: Viewport, lang: str) -> None:
        """The base view again at the largest ui scale this viewport allows.

        Display scales are `zoom` on `body`, so they change every rect in the
        page — which makes "the biggest step the user can reach here" the one
        extra variable most likely to push a top-bar control off the edge.
        `uiScaleLimits()` is resolution-aware and recomputed per step, so the
        harness asks the page for the limit rather than hard-coding one.
        """
        try:
            scale = driver.js(
                "(() => { const lim = uiScaleLimits();"
                " UI_SCALES.ui_scale = lim.uiMax; applyUIScales();"
                " return lim.uiMax; })()")
            driver.wait_idle()
            data = driver.measure()
        except (CDPError, StepError) as e:
            self.errors.append(f"ui-scale sweep {vp.name} {lang}: {e}")
            return
        finally:
            try:
                driver.js("(() => { UI_SCALES.ui_scale = 1.0; applyUIScales();"
                          " return true; })()")
                driver.wait_idle()
            except (CDPError, StepError):
                pass
        self.screens_run += 1
        for f in from_measurement("project-base@ui-scale-max", data):
            self.findings.add(f, viewport=vp.name, lang=lang)
        self.log(f"project-base@ui-scale-max {vp.name} {lang}: scale {scale}")

    def one_screen(self, driver: Driver, screen: Screen, vp: Viewport,
                   lang: str) -> bool:
        """Measure one screen. False means the page needs replacing.

        Every screen starts from a freshly reloaded page. That costs about
        a third of a second and buys the only isolation that actually
        holds: enough's full-frame modes own render loops, and a loop that
        outlives its mode by even one screen compounds until the renderer
        stops answering CDP altogether. Teardown plus `reset_page()` is
        still run first — a screen whose exit path is broken should fail
        here rather than be papered over by the reload.
        """
        started = time.monotonic()
        tag = f"{screen.name} {vp.name} {lang}"
        try:
            driver.run_steps(screen.setup, what=f"{screen.name} setup")
        except StepError as e:
            if _is_wedged(e):
                self.errors.append(str(e))
                self.log(f"SETUP FAILED {tag}: {e}")
                self.log("  …the tab stopped answering; replacing it")
                return False
            # One retry from a clean page. A screen recipe that has genuinely
            # rotted fails twice and is reported; a recipe that lost a race
            # with a fetch this once does not deserve to turn the whole
            # pre-commit suite red.
            self.log(f"SETUP FAILED {tag}: {e} — retrying once")
            driver.reset_page()
            try:
                driver.reload()
                driver.run_steps(screen.setup, what=f"{screen.name} setup")
            except (StepError, CDPError) as again:
                self.errors.append(f"{str(again)} (failed twice)")
                self.log(f"SETUP FAILED AGAIN {tag}: {again}")
                if _is_wedged(again):
                    return False
                try:
                    driver.run_steps(screen.teardown,
                                     what=f"{screen.name} teardown")
                except StepError:
                    pass
                driver.reset_page()
                return True
        try:
            data = driver.measure()
            # Read the dialog log BEFORE the teardown reloads the page —
            # `window.__uicheck` (and the log on it) does not survive a
            # navigation.
            self.note_dialogs(driver, f"{screen.name} [{lang}]")
        except CDPError as e:
            self.errors.append(f"{tag}: measure failed: {e}")
            return False
        finally:
            try:
                driver.run_steps(screen.teardown, what=f"{screen.name} teardown")
            except StepError as e:
                self.errors.append(str(e))
            # `settle=False`: the reload on the next line throws this
            # document away, so waiting for it to stop moving first buys
            # nothing and costs 50ms a screen.
            driver.reset_page(settle=False)
            try:
                driver.reload()
            except CDPError as e:
                self.errors.append(f"{tag}: reload after the screen failed: {e}")

        self.screens_run += 1
        found = from_measurement(screen.name, data)
        for f in found:
            self.findings.add(f, viewport=vp.name, lang=lang)
        self.log(f"{tag}: {len(data.get('items') or [])} clickables, "
                 f"{len(found)} finding(s), {time.monotonic() - started:.1f}s")
        return True

    # -- behaviour ------------------------------------------------------
    def focus(self, mode: str) -> Driver:
        """Point the run at one tab: it gets focus, the others give it up.

        Focus emulation is the replacement for `Page.bringToFront` (see
        `Driver.front`), and it is only safe while EXACTLY ONE page claims
        focus — two tabs both told they are focused is the state the P0 note
        warned about. Doing it here, where every driver is in scope, is the
        only place that can promise it.
        """
        driver = self.drivers[mode]
        for other_mode, other in self.drivers.items():
            if other_mode != mode:
                other.unfocus()
        driver.front()
        return driver

    def pump_idle_tabs(self, busy: str) -> None:
        """Read whatever arrived on every tab the run is NOT driving.

        The two-tab matrix's one sharp edge. A native dialog stops Chrome's
        whole browser process (see `cdp.Page._note_event`), and the CDP
        auto-accept that unstops it only runs on a socket somebody reads —
        so a dialog in the idle tab used to take the busy tab's next
        `Page.reload` down with it, and then `/json/new` too, which is why
        even `recover()` could not recover. One non-blocking read per idle
        tab, before every screen and every scenario, closes that.
        """
        for mode, other in self.drivers.items():
            if mode == busy:
                continue
            try:
                other.page.pump_pending()
            except Exception:                                    # noqa: BLE001
                pass

    def note_dialogs(self, driver: Driver, where: str) -> None:
        """A native dialog is a finding, not a fatality (probes.js traps it)."""
        for d in driver.native_dialogs():
            msg = (f"{where}: the page raised a native "
                   f"{d.get('kind', 'dialog')}(): "
                   f"{(d.get('message') or '').strip()!r} — trapped by the "
                   f"harness (one would stop Chrome's browser process)")
            if msg not in self.errors:
                self.errors.append(msg)

    def run_scenarios(self, driver: Driver, lang: str) -> None:
        driver = self.focus("project")
        driver.set_viewport(INTERACTION_VIEWPORT)
        for name in self.plan.scenarios:
            fn = SCENARIOS[name]
            self.pump_idle_tabs("project")
            started = time.monotonic()
            wedged = False
            try:
                # The hard ceiling. Inside it every step has its own; this is
                # what catches a scenario that is looping in Python, or a
                # page that stopped answering in a way no single call's
                # deadline reaches. Blowing it is a FAIL with a screenshot,
                # never a run that does not end.
                with watchdog(driver.page, SCENARIO_BUDGET_S,
                              f"scenario {name} [{lang}]"):
                    fails = fn(driver)
            except Wedged as e:
                wedged = True
                fails = [f"scenario WEDGED: {e}"]
            except (StepError, CDPError) as e:
                fails = [f"scenario raised: {e}"]
                wedged = _is_wedged(e)
            except Exception as e:                               # noqa: BLE001
                fails = [f"scenario raised {type(e).__name__}: {e}"]
            for msg in fails:
                self.findings.add(Finding(f"scenario:{name}", "scenario",
                                          name, msg),
                                  viewport=INTERACTION_VIEWPORT.name, lang=lang)
            self.log(f"scenario {name} [{lang}]: "
                     f"{'ok' if not fails else f'{len(fails)} failure(s)'} "
                     f"({time.monotonic() - started:.1f}s)")
            if wedged:
                driver = self.recover("project")
                driver.set_viewport(INTERACTION_VIEWPORT)
                self.shoot(driver, f"scenario-{name}", INTERACTION_VIEWPORT.name,
                           lang)
                continue
            self.note_dialogs(driver, f"scenario {name} [{lang}]")
            if fails and self.shots:
                self.shoot(driver, f"scenario-{name}",
                           INTERACTION_VIEWPORT.name, lang)
            # A scenario that blew up mid-way can leave modes standing.
            try:
                driver.reload()
            except CDPError:
                driver = self.recover("project")

    def shoot(self, driver: Driver, tag: str, vp_name: str, lang: str) -> None:
        """Best-effort PNG. A wedge that produces no picture is still a FAIL,
        so this never raises — but a picture is most of the debugging."""
        name = f"{_safe(tag)}_{_safe(vp_name)}_{lang}.png"
        try:
            driver.screenshot(SHOTS_DIR / name)
        except (CDPError, OSError, RuntimeError):
            return
        if name not in self.shots_taken:
            self.shots_taken.append(name)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def summarize(run: Run, baseline: dict[str, str], *, per_class: int = 6,
              full: bool = True) -> int:
    new = [f for f in run.findings if f.key not in baseline]
    accepted = [f for f in run.findings if f.key in baseline]
    fixed = sorted(set(baseline) - run.findings.keys())

    print(f"\nui-check: {run.screens_run} screen measurements, "
          f"{len(run.findings)} distinct finding(s) — "
          f"{len(accepted)} baselined, {len(new)} new")

    if new:
        print("\nNEW findings (worst first):")
        shown: dict[str, int] = {}
        for f in sorted(new, key=lambda x: (x.rank, x.screen, x.path)):
            n = shown.get(f.kind, 0)
            if n >= per_class:
                continue
            shown[f.kind] = n + 1
            print(f"  [{f.kind}] {f.screen} · {f.path}")
            print(f"      {f.detail}")
            print(f"      seen at: {f.where()}")
        hidden = len(new) - sum(min(v, per_class) for v in shown.values())
        if hidden > 0:
            print(f"  … and {hidden} more (full list in the JSON report)")

    # Only meaningful after a full run: the quick matrix is a subset, so
    # most of what it "no longer reproduces" is simply a viewport or a
    # language it did not visit.
    if fixed and full:
        print(f"\n{len(fixed)} baselined finding(s) no longer reproduce — rerun "
              f"with --update-baseline to drop them:")
        for key in fixed[:10]:
            print(f"  - {key}")

    if run.errors:
        print(f"\n{len(run.errors)} harness error(s) (a screen recipe that no "
              f"longer works is itself drift):")
        for e in run.errors[:10]:
            print(f"  ! {e}")

    return len(new) + len(run.errors)


def write_report(run: Run, baseline: dict[str, str], plan: Plan,
                 elapsed: float) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "elapsed_s": round(elapsed, 1),
        "screens_measured": run.screens_run,
        "viewports": [v.name for v in plan.viewports],
        "languages": list(plan.languages),
        "scenarios": list(plan.scenarios),
        "errors": run.errors,
        "findings": [
            {"key": f.key, "screen": f.screen, "kind": f.kind, "path": f.path,
             "other": f.other, "detail": f.detail,
             "baselined": f.key in baseline,
             "seen": sorted(f"{lang}@{vp}" for vp, lang in f.seen)}
            for f in run.findings
        ],
        "shots": run.shots_taken,
    }
    dest = OUT_DIR / "report.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return dest


def capture_failure_shots(world: ScratchWorld, browser: Browser, run: Run,
                          baseline: dict[str, str], plan: Plan) -> None:
    """One PNG per failing (screen, viewport, language).

    Taken in a second pass rather than during the sweep: screenshots are the
    single most expensive CDP call, and on a green run there should be
    exactly zero of them.
    """
    new = [f for f in run.findings if f.key not in baseline]
    if not new:
        return
    wanted: dict[tuple[str, str, str], Screen] = {}
    by_name = {s.name: s for s in screens_mod.ALL_SCREENS}
    for f in new:
        screen = by_name.get(f.screen)
        if screen is None:
            continue            # scenario findings have no screen to shoot
        for vp_name, lang in sorted(f.seen)[:1]:
            wanted.setdefault((f.screen, vp_name, lang), screen)
    if not wanted:
        return
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    by_vp = {v.name: v for v in plan.viewports}

    for mode, server in (("project", world.project_server),
                         ("home", world.home_server)):
        items = [(k, s) for k, s in wanted.items() if s.mode == mode]
        if not items:
            continue
        page = browser.new_page()
        driver = Driver(page, server.base)
        # Exactly one focused page at a time (see `Run.focus`): the matrix's
        # own tabs are done with, so this one takes it for the shot pass.
        for other in run.drivers.values():
            other.unfocus()
        driver.front()
        try:
            for (screen_name, vp_name, lang), screen in items:
                server.post_json("/api/ui-config", {"ui_language": lang})
                driver.load()
                vp = by_vp.get(vp_name)
                if vp:
                    driver.set_viewport(vp)
                try:
                    driver.run_steps(screen.setup, what=f"{screen_name} setup")
                    name = f"{_safe(screen_name)}_{_safe(vp_name)}_{lang}.png"
                    driver.screenshot(SHOTS_DIR / name)
                    run.shots_taken.append(name)
                except (StepError, CDPError):
                    continue
        finally:
            page.close()
    print(f"\n{len(run.shots_taken)} screenshot(s) in "
          f"{SHOTS_DIR.relative_to(REPO)}/")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_matrix(plan: Plan, *, verbose: bool, shots: bool,
               update_baseline: bool, quick: bool = False) -> int:
    chrome = find_chrome()
    if not chrome:
        print("ui-check: SKIPPED — no Chrome/Chromium found "
              "($ENOUGH_CHROME, /Applications/…, PATH). The browser stage is "
              "optional by design; every other stage still ran.")
        return 0
    print(f"ui-check: {chrome}")
    print(f"ui-check: {len(plan.screens)} screens x {len(plan.viewports)} "
          f"viewports x {len(plan.languages)} languages, "
          f"{len(plan.scenarios)} scenarios")

    started = time.monotonic()
    baseline = load_baseline()
    scratch = Path(tempfile.mkdtemp(prefix="enough-uicheck-"))
    run = Run(plan, verbose=verbose, shots=shots)
    browser: Browser | None = None
    try:
        with ScratchWorld(scratch) as world:
            browser = Browser(chrome)
            browser.start()
            run.browser = browser
            # One tab per mode, reused for the whole matrix. Opening a page
            # per screen would be most of the wall clock; `reset_page()`
            # between screens is what makes reuse safe.
            run.drivers = {
                "project": Driver(browser.new_page(), world.project_server.base),
                "home": Driver(browser.new_page(), world.home_server.base),
            }
            servers = {"project": world.project_server,
                       "home": world.home_server}
            for lang in plan.languages:
                print(f"  language {lang} "
                      f"({time.monotonic() - started:.0f}s elapsed)", flush=True)
                for mode in ("project", "home"):
                    if not any(s.mode == mode for s in plan.screens):
                        continue
                    servers[mode].post_json("/api/ui-config", {"ui_language": lang})
                    try:
                        run.drivers[mode].load()
                    except CDPError:
                        run.recover(mode)
                    run.sweep(mode, lang)
                if plan.scenarios:
                    servers["project"].post_json("/api/ui-config",
                                                 {"ui_language": lang})
                    try:
                        run.drivers["project"].load()
                    except CDPError:
                        run.recover("project")
                    run.run_scenarios(run.drivers["project"], lang)
            # Back to English so the scratch config never outlives the run in
            # a surprising state (it is thrown away, but cheap insurance).
            for mode, server in servers.items():
                server.post_json("/api/ui-config", {"ui_language": "en"})

            if update_baseline:
                n = write_baseline(run.findings)
                print(f"\nui-check: wrote {n} accepted finding(s) to "
                      f"scripts/uicheck/baseline.json")
                baseline = load_baseline()
            elif shots:
                capture_failure_shots(world, browser, run, baseline, plan)
    finally:
        if browser is not None:
            browser.stop()
        from uicheck.server import cleanup
        cleanup(scratch)

    elapsed = time.monotonic() - started
    bad = summarize(run, baseline, full=not quick)
    report = write_report(run, baseline, plan, elapsed)
    print(f"\nui-check: {elapsed:.1f}s · report {report.relative_to(REPO)}")
    stray = stray_debug_processes()
    if stray:
        print("ui-check: WARNING — debug-port browsers still running:")
        for line in stray:
            print(f"  {line}")
    return 0 if (update_baseline or bad == 0) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true",
                    help="3 viewports x {en,de,ja} — the pre-commit default")
    ap.add_argument("--screens", default="",
                    help="comma-separated screen names (default: all)")
    ap.add_argument("--langs", default="",
                    help="comma-separated language codes (default: the matrix)")
    ap.add_argument("--viewports", default="",
                    help="comma-separated viewport names, e.g. 1512x982@2")
    ap.add_argument("--no-scenarios", action="store_true",
                    help="skip the mode-stack interaction scenarios")
    ap.add_argument("--update-baseline", action="store_true",
                    help="rewrite scripts/uicheck/baseline.json from this run")
    ap.add_argument("--no-shots", action="store_true",
                    help="don't capture screenshots for new findings")
    ap.add_argument("--list", action="store_true",
                    help="print the screen registry and the matrix, run nothing")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        plan = build_plan(args)
        print("screens:")
        for s in screens_mod.ALL_SCREENS:
            mark = " " if s in plan.screens else "-"
            print(f" {mark} {s.name:<28} {s.mode:<8} {s.note}")
        print("\nscenarios:")
        for name in SCENARIOS:
            print(f"   {name}")
        print("\nviewports: " + ", ".join(v.name for v in plan.viewports))
        print("languages: " + ", ".join(plan.languages))
        return 0

    try:
        plan = build_plan(args)
        return run_matrix(plan, verbose=args.verbose, shots=not args.no_shots,
                          update_baseline=args.update_baseline,
                          quick=args.quick)
    except KeyboardInterrupt:
        print("\nui-check: interrupted", file=sys.stderr)
        return 130
    except Exception as e:                                       # noqa: BLE001
        print(f"\nui-check ERRORED: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
