/* The in-page measurement functions for scripts/ui_check.py.
 *
 * Injected once per page load and parked on `window.__uicheck`. Everything
 * here returns plain JSON, because the Python side only ever asks through
 * `Runtime.evaluate {returnByValue: true}` — no object handles, no
 * round-trips per element. One call, one snapshot of the whole layout.
 *
 * The hard part of this file is not measuring; it is deciding what NOT to
 * report. A UI that stacks modes like windows *intends* to have elements
 * covering each other, and `position: sticky` chrome *intends* to sit over
 * scrolled content. So every predicate here leans on `elementFromPoint` —
 * what the user's click would actually hit — rather than on rect geometry
 * alone. A button that is covered by something the user can see is a
 * finding; a button that is covered because its whole mode is buried under
 * another mode is not, and the hit test is what tells them apart.
 *
 * Coordinates: everything is `getBoundingClientRect()`, i.e. top-level CSS
 * pixels, the same frame `elementFromPoint` takes. enough sets `zoom` on
 * `body` (see "Display scales" in AGENT_GUIDE), which is exactly why nothing
 * here touches offsetWidth/clientHeight for geometry — those are in
 * zoomed-local px and mixing the two is the classic bug.
 */
(function () {
  'use strict';

  /* ------------------------------------------------------------------
   * Native dialogs: trapped, recorded, never shown.
   *
   * This is the harness's single worst failure mode and it is worth the
   * paragraph. `alert()`, `confirm()` and `prompt()` run a nested message
   * loop in Chrome's BROWSER process — not in the tab that called them. For
   * as long as one is up, no tab answers `Runtime.evaluate`, `Page.reload`
   * never replies, and the DevTools HTTP endpoint (`/json/list`,
   * `/json/new`) stops accepting connections, so the harness cannot even
   * throw the tab away and open a fresh one. The run simply stops, with no
   * error and nothing in the log.
   *
   * enough reaches for `alert()` on about thirty error paths (a failed
   * fetch, a refused save, a mode that could not open). Every one of them
   * is reachable in the scratch world, where there is no model and several
   * endpoints are mode-gated — so this is not a hypothetical.
   *
   * So: record and answer, in the page, before anything can call one.
   * `confirm` answers **false** and `prompt` answers **null**, because
   * "cancel" is the answer that never destroys anything. `driver.py` reads
   * the list back after every screen and scenario and the run reports each
   * one as a harness error — a dialog is a real finding, it just must not
   * be a fatal one. (`cdp.py`'s `Page.javascriptDialogOpening` handler stays
   * as the belt-and-braces for anything this cannot reach: a `beforeunload`,
   * or a dialog raised before the probes are injected.)
   * ------------------------------------------------------------------ */
  var NATIVE_DIALOGS = (window.__uicheck && window.__uicheck._dialogs) || [];

  function trapDialog(name, answer) {
    var original = window[name];
    if (original && original.__uicheckTrap) return;
    function trap(message) {
      NATIVE_DIALOGS.push({
        kind: name,
        message: String(message === undefined ? '' : message).slice(0, 240),
        at: new Date().toISOString()
      });
      return answer;
    }
    trap.__uicheckTrap = true;
    try { window[name] = trap; } catch (e) { /* frozen: cdp.py covers it */ }
  }
  trapDialog('alert', undefined);
  trapDialog('confirm', false);
  trapDialog('prompt', null);

  var CLICKABLE = [
    'button', 'a[href]', 'input', 'select', 'textarea',
    '[role=button]', '[onclick]', '.icon-btn', '[data-help]',
    '.help-trigger', '.ribbon-redx', '.mode-indicator', '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  /* A stable, human-readable address for an element. NOT a pixel value and
   * NOT an index into a NodeList — the baseline is keyed on this, so it has
   * to survive a re-layout, a language switch and a viewport change. id
   * first, then a short tag.class chain, then the nth-of-type tiebreak. */
  function pathOf(el) {
    if (!el || el.nodeType !== 1) return '(none)';
    if (el.id) return '#' + el.id;
    var parts = [];
    var node = el;
    for (var depth = 0; node && node.nodeType === 1 && depth < 4; depth++) {
      var part = node.tagName.toLowerCase();
      if (node.id) { parts.unshift('#' + node.id); break; }
      var cls = (node.getAttribute('class') || '').trim().split(/\s+/)
        .filter(function (c) { return c && !/^(is-|js-)/.test(c); })
        .slice(0, 2);
      if (cls.length) part += '.' + cls.join('.');
      if (!cls.length && node.parentElement) {
        var same = Array.prototype.filter.call(
          node.parentElement.children,
          function (c) { return c.tagName === node.tagName; });
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join('>');
  }

  /* Which "layer" an element belongs to.
   *
   * enough paints in deliberate tiers: the page, then the full-frame modes
   * (z = 30 + stack index), then the confirm overlay (950+), then modals
   * (1000+). A modal covering the whole page is the design working, not a
   * bug — so a covered/overlap finding only counts when both elements are
   * in the SAME layer. Reporting cross-layer coverage would have meant ~75
   * findings per open modal and a harness nobody reads.
   *
   * The list is explicit rather than derived from z-index because a
   * computed z-index tells you nothing about intent: `.mode-indicator` and
   * a buried mode both sit above the page, but only one of them is supposed
   * to swallow clicks. */
  var LAYER_SEL = '#confirm-overlay, #help-viewer, #preview, [id$="-modal"],' +
    ' #readvisor-panel,' +
    ' #review-mode, #edit-mode, #girraph-mode, #merirmaid-mode, #wiki-mode,' +
    ' #cacheawl-mode, #ref-mode, #paginated-mode';
  /* `#readvisor-panel` joined the list in P6c, when the panel's own screens
   * were finally wired. Docked, it PUSHES — nothing is covered and the list
   * changes nothing. In `full` (and in the narrow-viewport overlay) it is
   * meant to sit over the stage, and without this every composure toolbar
   * button under it reported as covered: thirty findings a run saying "the
   * panel is open", which is the same noise an open modal would make. */

  function layerOf(el) {
    var node = el;
    while (node && node.nodeType === 1 && node !== document.body) {
      if (node.matches && node.matches(LAYER_SEL)) return node.id || 'layer';
      node = node.parentElement;
    }
    return 'page';
  }

  function ownText(el) {
    var out = '';
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) out += n.nodeValue;
    }
    return out.trim();
  }

  function label(el) {
    var t = (el.innerText || ownText(el) || el.getAttribute('aria-label')
      || el.getAttribute('title') || el.getAttribute('placeholder')
      || el.getAttribute('data-icon') || '').trim();
    return t.length > 60 ? t.slice(0, 57) + '…' : t;
  }

  function rectOf(el) {
    var r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height,
             right: r.right, bottom: r.bottom };
  }

  /* Visible = paints, has area, and is reachable by a click at its centre.
   * The hit test is the interesting half: it is what finds a button that is
   * perfectly laid out and completely covered. */
  function visibility(el) {
    var cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    if (parseFloat(cs.opacity) === 0) return null;
    var r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return null;
    var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    var inView = cx >= 0 && cy >= 0 && cx <= innerWidth && cy <= innerHeight;
    var hit = inView ? document.elementFromPoint(cx, cy) : null;
    var self = false, covered = null;
    if (hit) {
      self = hit === el || el.contains(hit) || hit.contains(el);
      if (!self) covered = hit;
    }
    return { rect: rectOf(el), inView: inView, hitSelf: self,
             coveredBy: covered ? pathOf(covered) : null,
             coveredByLayer: covered ? layerOf(covered) : null,
             hasHit: !!hit };
  }

  function scrollParent(el) {
    var node = el.parentElement;
    while (node && node !== document.body) {
      var cs = getComputedStyle(node);
      var o = cs.overflow + cs.overflowX + cs.overflowY;
      if (/(auto|scroll)/.test(o) &&
          (node.scrollHeight > node.clientHeight + 1 ||
           node.scrollWidth > node.clientWidth + 1)) return node;
      node = node.parentElement;
    }
    return null;
  }

  /* "this element is simply scrolled past inside its own scroller".
   *
   * `find_offscreen` has always understood that inside a scroll container
   * "outside the viewport" just means "below the fold", which is what
   * scrolling is for — but `find_covered` and `find_overlaps` did not, and
   * they blame whatever `elementFromPoint` returns. So the paginate modal's
   * form controls (its panel is height-capped and its body scrolls) reported
   * as "covered by the modal foot", and after P6c capped the model modal,
   * `#apply-model-btn` joined them. Eighteen findings that all meant "you
   * have not scrolled down yet". The scroller's own box is the only thing
   * that can tell those apart from a real cover, and only the page knows it.
   */
  function scrolledPast(el, sp, r) {
    if (!sp) return false;
    var s = sp.getBoundingClientRect();
    var cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    return cx < s.left || cx > s.right || cy < s.top || cy > s.bottom;
  }

  function clickables() {
    var out = [];
    var els = document.querySelectorAll(CLICKABLE);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.disabled) continue;
      var v = visibility(el);
      if (!v) continue;
      var sp = scrollParent(el);
      out.push({
        path: pathOf(el), tag: el.tagName.toLowerCase(), text: label(el),
        rect: v.rect, inView: v.inView, hitSelf: v.hitSelf,
        coveredBy: v.coveredBy, coveredByLayer: v.coveredByLayer,
        layer: layerOf(el), inScroller: sp ? pathOf(sp) : null,
        outOfScroller: scrolledPast(el, sp, v.rect),
        z: getComputedStyle(el).zIndex
      });
      el.__uicheckIndex = out.length - 1;
    }
    return out;
  }

  /* Text that does not fit its own box, with the two deliberate exceptions
   * the spec carves out: anything that opted into truncation (an ellipsis or
   * an explicit data-clip-ok) is fine unless it is egregious — under 40% of
   * the text showing, or fewer than three characters' worth of width. */
  function clipped() {
    var out = [];
    var els = document.querySelectorAll('body *');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var text = ownText(el);
      if (!text) continue;
      var cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      var overflowHidden = /(hidden|clip)/.test(cs.overflowX + cs.overflowY);
      if (!overflowHidden) continue;
      var overW = el.scrollWidth - el.clientWidth;
      var overH = el.scrollHeight - el.clientHeight;
      if (overW <= 1 && overH <= 1) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      var opted = cs.textOverflow === 'ellipsis' || el.hasAttribute('data-clip-ok');
      if (opted) {
        var shown = el.scrollWidth ? el.clientWidth / el.scrollWidth : 1;
        var chars = el.clientWidth / Math.max(1, parseFloat(cs.fontSize) * 0.55);
        if (shown >= 0.4 && chars >= 3) continue;
        out.push({ path: pathOf(el), text: label(el), kind: 'ellipsis-egregious',
                   shown: Math.round(shown * 100), chars: Math.round(chars) });
        continue;
      }
      out.push({ path: pathOf(el), text: label(el), kind: 'clipped',
                 overW: Math.round(overW), overH: Math.round(overH) });
    }
    return out;
  }

  /* The snapshot. Note what is NOT here: overlap, off-screen and
   * too-small are *judgements*, and they live in
   * scripts/uicheck/geometry.py where they can be unit-tested against
   * hand-built rectangles on a machine with no browser. This function
   * measures and stops. Clipping is the one exception that has to stay in
   * the page, because only the browser knows `scrollWidth`, the computed
   * `overflow`, and whether the element opted into an ellipsis. */
  function measure() {
    var items = clickables();
    return {
      viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
      mode: document.body.getAttribute('data-mode') || '',
      lang: document.documentElement.lang || '',
      items: items,
      clipped: clipped()
    };
  }

  /* Small helpers the declarative screen steps compile down to. */
  window.__uicheck = {
    measure: measure,
    clickables: clickables,
    /* Every native dialog this page tried to raise, in order. Read (and
     * cleared) by `Driver.native_dialogs()` after each screen and scenario;
     * the run reports them as harness errors. */
    _dialogs: NATIVE_DIALOGS,
    nativeDialogs: function (clear) {
      var out = NATIVE_DIALOGS.slice();
      if (clear) NATIVE_DIALOGS.length = 0;
      return out;
    },
    /* Text of every [data-i18n] element, keyed by its i18n key — the
     * language round-trip scenario compares two of these. */
    i18nSnapshot: function () {
      var out = {};
      var els = document.querySelectorAll('[data-i18n]');
      for (var i = 0; i < els.length; i++) {
        out[els[i].getAttribute('data-i18n') + '#' + i] = els[i].textContent;
      }
      return out;
    },
    /* `MODE_STACK` is a `const` in the inline script, so it is NOT a window
     * property — the indicators are the observable truth, and they are the
     * thing the contract is actually about. `_modeRender()` walks the stack
     * backwards, so indicator[0] is the top of the stack (leftmost). */
    modeStack: function () {
      var bar = document.getElementById('mode-stack');
      var ind = bar ? Array.prototype.map.call(
        bar.querySelectorAll('.mode-indicator'),
        function (el) {
          return { name: el.getAttribute('data-mode'),
                   buried: el.classList.contains('buried'),
                   hasRibbon: !!el.querySelector('.mode-ribbon') };
        }) : [];
      return { indicators: ind, hidden: bar ? !!bar.hidden : null,
               top: ((window.modeTop && window.modeTop()) || {}).name || null };
    },
    modalOpen: function () {
      var open = [];
      var els = document.querySelectorAll('[id$="-modal"]');
      for (var i = 0; i < els.length; i++) {
        if (!els[i].classList.contains('hidden')) open.push(els[i].id);
      }
      return open;
    },
    /* "The page has stopped moving": three consecutive animation frames
     * with an unchanged layout signature. Cheaper and far more reliable
     * than a fixed sleep, which is what the spec forbids.
     *
     * Bounded on purpose, twice over. enough polls `/api/llm-status` and
     * friends forever, so a page that never settles is normal, not a bug —
     * after `budget` frames this resolves `false` and the caller measures
     * what is there. The `setTimeout` is the second belt: if rAF is not
     * running at all (a throttled background tab), the promise still
     * settles instead of hanging the whole matrix on one screen. */
    idle: function (budget) {
      var maxFrames = budget || 60;
      return new Promise(function (resolve) {
        var last = null, stable = 0, frames = 0, done = false;
        function finish(v) { if (!done) { done = true; resolve(v); } }
        function sig() {
          var b = document.body;
          return [b.scrollHeight, b.scrollWidth, b.clientWidth, b.clientHeight,
                  document.querySelectorAll('*').length].join('|');
        }
        function tick() {
          if (done) return;
          var s = sig();
          stable = (s === last) ? stable + 1 : 0;
          last = s;
          if (stable >= 3) return finish(true);
          if (++frames >= maxFrames) return finish(false);
          requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        setTimeout(function () { finish(false); }, 2500);
      });
    }
  };
  return true;
})();
