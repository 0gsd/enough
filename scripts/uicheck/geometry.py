"""Rect arithmetic for the layout probes — pure Python, on purpose.

The page measures (it has to: only the browser knows where things are), but
it does not *judge*. Every "is this a finding" decision lives here instead,
for one reason: this file can be unit-tested without a browser, and
`probes.js` cannot. `tests/test_ui_check.py` runs these predicates against
hand-built rectangles on every `pytest -q`, so the rules stay honest even on
a machine with no Chrome — which is most CI machines.

The vocabulary is small and all of it is in top-level CSS pixels, the frame
`getBoundingClientRect()` and `elementFromPoint()` share. enough zooms
`body`, so element-relative lengths (`offsetWidth`, `clientHeight`) are in a
*different* unit; nothing here ever sees one. See the coordinate contract
under "Display scales" in docs/AGENT_GUIDE.md.
"""

from __future__ import annotations

from typing import Any, NamedTuple

#: Below this, two rects are touching rather than overlapping — a shared
#: 1px border or a rounding artefact, not a bug.
OVERLAP_SLOP_PX = 2.0

#: The smallest comfortable hit target. Anything under this is a warning,
#: never a failure: enough's icon chips are deliberately small and the point
#: is to notice when a *new* one is smaller still.
MIN_TARGET_PX = 16.0


class Rect(NamedTuple):
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Rect:
        return cls(float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))


def intersection(a: Rect, b: Rect) -> tuple[float, float]:
    """(overlap width, overlap height). Zero or negative means no overlap."""
    return (min(a.right, b.right) - max(a.x, b.x),
            min(a.bottom, b.bottom) - max(a.y, b.y))


def overlaps(a: Rect, b: Rect, *, slop: float = OVERLAP_SLOP_PX) -> bool:
    """True when the two rects share more than `slop` px on BOTH axes."""
    ox, oy = intersection(a, b)
    return ox > slop and oy > slop


def contains(outer: Rect, inner: Rect, *, slop: float = 1.0) -> bool:
    """True when `inner` sits (near enough) entirely inside `outer`.

    A control inside its own container overlaps it completely and is not a
    finding; this is the predicate that says so.
    """
    return (inner.x >= outer.x - slop and inner.right <= outer.right + slop
            and inner.y >= outer.y - slop and inner.bottom <= outer.bottom + slop)


def inside_viewport(r: Rect, width: float, height: float, *,
                    slop: float = 1.0) -> bool:
    return (r.x >= -slop and r.y >= -slop
            and r.right <= width + slop and r.bottom <= height + slop)


def is_tiny(r: Rect, *, minimum: float = MIN_TARGET_PX) -> bool:
    return r.w < minimum or r.h < minimum


# ---------------------------------------------------------------------------
# The judgements, over the JSON `clickables()` hands back
# ---------------------------------------------------------------------------

def _covers(covered_path: str | None, other_path: str) -> bool:
    """Did `other_path` (or something inside it) win the hit test?"""
    if not covered_path:
        return False
    return covered_path == other_path or covered_path.startswith(other_path + ">")


def scrolled_past(item: dict[str, Any]) -> bool:
    """Is this only unreachable because nobody has scrolled to it?

    `find_offscreen` has always skipped anything inside a scroll container,
    on the grounds that "below the fold" is what scrolling is for. The
    coverage rules did not, and they believed whatever `elementFromPoint`
    answered — so a height-capped modal whose body scrolls reported its own
    form controls as "covered by the modal foot". `probes.js` computes the
    flag, because only the page knows where the scroller's box is.
    """
    return bool(item.get("outOfScroller"))


def find_overlaps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pairs that overlap AND where the overlap actually costs a click.

    Geometry alone cannot tell a bug from the design: enough stacks modes
    like windows, so a buried mode's buttons legitimately sit under the one
    above. The filter is the hit test — a pair is a finding only when one of
    the two fails `elementFromPoint` *because of the other one*. That is the
    difference between "covered by the mode on top of it" (correct) and
    "covered by its own neighbour in the top bar" (not).
    """
    out: list[dict[str, Any]] = []
    rects = [Rect.from_json(i["rect"]) for i in items]
    for i, a in enumerate(items):
        if not a.get("inView"):
            continue
        for j in range(i + 1, len(items)):
            b = items[j]
            if not b.get("inView"):
                continue
            ra, rb = rects[i], rects[j]
            if not overlaps(ra, rb):
                continue
            if contains(rb, ra) or contains(ra, rb):
                continue
            if is_backdrop(a["path"]) or is_backdrop(b["path"]):
                continue
            blamed = None
            if (not a.get("hitSelf") and same_layer(a) and not scrolled_past(a)
                    and _covers(a.get("coveredBy"), b["path"])):
                blamed = a
            elif (not b.get("hitSelf") and same_layer(b) and not scrolled_past(b)
                    and _covers(b.get("coveredBy"), a["path"])):
                blamed = b
            if blamed is None:
                continue
            ox, oy = intersection(ra, rb)
            out.append({"a": a["path"], "b": b["path"],
                        "aText": a.get("text", ""), "bText": b.get("text", ""),
                        "overlapW": round(ox), "overlapH": round(oy),
                        "hidden": blamed["path"]})
    return out


#: A modal's click-outside target. It is *supposed* to sit behind the panel
#: and lose the hit test wherever the panel is drawn — reporting it once per
#: modal per screen is 25 entries of pure noise in the baseline.
BACKDROP = ".modal-backdrop"


def is_backdrop(path: str) -> bool:
    return path.endswith(BACKDROP)


def same_layer(item: dict[str, Any]) -> bool:
    """Is the thing covering `item` in the same paint tier as `item`?

    enough stacks modes like windows and floats modals over everything, so
    cross-tier coverage is the design, not a defect — an open modal covers
    ~70 controls and every one of them is fine. Only a same-tier cover is a
    finding: a top-bar button under its own neighbour, a chip under its own
    panel's header.
    """
    return item.get("layer") == item.get("coveredByLayer")


def find_covered(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Visible clickables that something in their own layer would swallow."""
    return [{"path": i["path"], "text": i.get("text", ""),
             "coveredBy": i.get("coveredBy")}
            for i in items
            if i.get("inView") and not i.get("hitSelf") and i.get("coveredBy")
            and same_layer(i) and not is_backdrop(i["path"])
            and not scrolled_past(i)]


def find_offscreen(items: list[dict[str, Any]], width: float,
                   height: float) -> list[dict[str, Any]]:
    """Clickables outside the viewport with no scroller to reach them by.

    Inside a scroll container, "outside the viewport" is just "below the
    fold", which is what scrolling is for.
    """
    out: list[dict[str, Any]] = []
    for i in items:
        if i.get("inScroller"):
            continue
        r = Rect.from_json(i["rect"])
        if inside_viewport(r, width, height):
            continue
        out.append({"path": i["path"], "text": i.get("text", ""),
                    "rect": i["rect"],
                    "viewport": {"w": width, "h": height}})
    return out


def find_tiny(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in items:
        if not i.get("inView") or not i.get("hitSelf"):
            # A too-small target that is currently behind a modal is not
            # this screen's problem; it will be reported on the screen where
            # the user can actually reach it.
            continue
        r = Rect.from_json(i["rect"])
        if not is_tiny(r):
            continue
        out.append({"path": i["path"], "text": i.get("text", ""),
                    "w": round(r.w), "h": round(r.h)})
    return out
