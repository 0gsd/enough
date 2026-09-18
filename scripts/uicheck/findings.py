"""Findings and the baseline — the part that decides what counts as news.

A layout harness that reports everything reports nothing: today's tree has
pre-existing overlap and clipping, and a pre-commit check that is red on
arrival gets `--no-verify`'d into irrelevance within a day. So findings are
compared against a committed **baseline** and only the new ones fail.

The baseline key is the whole design:

    (screen, class-of-finding, selector-path[, second selector-path])

and deliberately **no pixel values, no viewport, no language**. Keying on
geometry would mean a baseline that churns on every font change and an
"accepted" entry that silently stops matching the thing it accepted. Keying
on the element's address means the entry survives a re-layout and dies the
moment the element does — which is exactly when a human should look again.

Dropping the viewport and language from the key is the other half: a button
that overlaps its neighbour in German at 1024px is one finding, not six. The
*record* still carries every (viewport, language) it was seen at, so the
report can say "worst first" honestly; only the key is coarse.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import geometry

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

# Worst first. The order is a judgement about user harm: a control the user
# cannot click at all, then one they cannot see, then text they cannot read,
# then a target that is merely hard to hit.
SEVERITY = ("covered", "overlap", "offscreen", "clipped", "ellipsis-egregious",
            "tiny", "scenario")


@dataclass
class Finding:
    """One problem, at one or more (screen, viewport, language) points."""
    screen: str
    kind: str
    path: str
    detail: str
    other: str = ""
    seen: set[tuple[str, str]] = field(default_factory=set)

    @property
    def key(self) -> str:
        parts = [self.screen, self.kind, self.path]
        if self.other:
            parts.append(self.other)
        return " | ".join(parts)

    @property
    def rank(self) -> int:
        return SEVERITY.index(self.kind) if self.kind in SEVERITY else len(SEVERITY)

    def where(self) -> str:
        return ", ".join(f"{lang}@{vp}" for vp, lang in sorted(self.seen)[:4]) + (
            f" (+{len(self.seen) - 4} more)" if len(self.seen) > 4 else "")


class FindingSet:
    """Accumulates findings across the matrix, deduplicated by key."""

    def __init__(self) -> None:
        self._by_key: dict[str, Finding] = {}

    def add(self, finding: Finding, *, viewport: str, lang: str) -> None:
        existing = self._by_key.get(finding.key)
        if existing is None:
            self._by_key[finding.key] = finding
            existing = finding
        existing.seen.add((viewport, lang))

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self):
        return iter(sorted(self._by_key.values(),
                           key=lambda f: (f.rank, f.screen, f.path)))

    def keys(self) -> set[str]:
        return set(self._by_key)

    def by_screen(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = defaultdict(list)
        for f in self:
            out[f.screen].append(f)
        return dict(out)


def from_measurement(screen: str, data: dict) -> list[Finding]:
    """Turn one `__uicheck.measure()` payload into findings.

    The page hands over raw measurements; every judgement below it comes
    from `geometry.py`, which is pure Python precisely so the rules are
    testable without a browser.
    """
    items = data.get("items") or []
    vp = data.get("viewport") or {"w": 0, "h": 0}
    data = dict(data)
    data["covered"] = geometry.find_covered(items)
    data["overlaps"] = geometry.find_overlaps(items)
    data["offscreen"] = geometry.find_offscreen(items, vp["w"], vp["h"])
    data["tiny"] = geometry.find_tiny(items)

    out: list[Finding] = []
    for c in data.get("covered") or []:
        out.append(Finding(screen, "covered", c["path"],
                           f"{c['text'] or '(no text)'} is covered by "
                           f"{c['coveredBy']}", other=c["coveredBy"] or ""))
    for o in data.get("overlaps") or []:
        a, b = sorted((o["a"], o["b"]))
        out.append(Finding(screen, "overlap", a,
                           f"overlaps {b} by {o['overlapW']}x{o['overlapH']}px "
                           f"({o['hidden']} loses the hit test)", other=b))
    for c in data.get("clipped") or []:
        out.append(Finding(screen, c["kind"], c["path"],
                           (f"{c['text'] or '(no text)'}: "
                            + (f"only {c['shown']}% of the text fits "
                               f"(~{c['chars']} chars)" if c["kind"].startswith("ellipsis")
                               else f"overflows by {c['overW']}x{c['overH']}px "
                                    f"under overflow:hidden"))))
    for o in data.get("offscreen") or []:
        r = o["rect"]
        out.append(Finding(screen, "offscreen", o["path"],
                           f"{o['text'] or '(no text)'} sits at "
                           f"({round(r['x'])},{round(r['y'])}) "
                           f"{round(r['w'])}x{round(r['h'])} outside the "
                           f"{o['viewport']['w']}x{o['viewport']['h']} viewport "
                           f"with no scroller to reach it"))
    for t in data.get("tiny") or []:
        out.append(Finding(screen, "tiny", t["path"],
                           f"{t['text'] or '(no text)'} is only {t['w']}x{t['h']}px"))
    return out


# ---------------------------------------------------------------------------
# The committed baseline
# ---------------------------------------------------------------------------

def load_baseline(path: Path = BASELINE_PATH) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return dict(data.get("accepted") or {})


def write_baseline(findings: FindingSet, path: Path = BASELINE_PATH) -> int:
    payload = {
        "_doc": (
            "Accepted pre-existing UI findings, keyed by "
            "(screen | class | selector-path[ | second path]) — never by pixel "
            "values, so an entry survives a re-layout and dies with the element "
            "it names. Regenerate with `uv run python scripts/ui_check.py "
            "--update-baseline` and read the diff: a key that disappears means "
            "something got fixed (delete it), a key that appears means something "
            "new needs a human. The list is a to-do, not an amnesty."
        ),
        "_notes": (
            "EVERY entry below is justified, by family, in "
            "scripts/uicheck/baseline-notes.md — what it is, why it is "
            "accepted, and which lane should fix it. If you add one, add a "
            "paragraph there; if you fix one, delete both in the same change."
        ),
        "accepted": {f.key: f"[{f.kind}] {f.detail}" for f in findings},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return len(payload["accepted"])
