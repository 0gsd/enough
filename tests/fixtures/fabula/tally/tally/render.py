"""Drawing totals for a terminal: one row per name, a bar scaled to the largest total."""
from __future__ import annotations

BAR_WIDTH = 30
BAR = "#"


def rows(totals: dict[str, int], show_all: bool = False) -> list[str]:
    """One line per name: the name padded to the longest, the total right-aligned, then a bar.

    A total of 0 is left out unless show_all. A negative total gets no bar. The longest bar is BAR_WIDTH
    characters; every other bar is scaled to it and rounded, and a positive total always gets at least one."""
    shown = {k: v for k, v in totals.items() if v != 0 or show_all}
    if not shown:
        return []
    name_w = max(len(k) for k in shown)
    num_w = max(len(str(v)) for v in shown.values())
    top = max([v for v in shown.values() if v > 0], default=0)
    out = []
    for name, value in shown.items():
        bar = ""
        if value > 0 and top:
            bar = BAR * max(1, round(value * BAR_WIDTH / top))
        out.append(f"{name.ljust(name_w)}  {str(value).rjust(num_w)}  {bar}".rstrip())
    return out


def empty_message(show_all: bool) -> str:
    return "nothing tallied yet" if show_all else "nothing tallied yet (or every total is 0; try --all)"
