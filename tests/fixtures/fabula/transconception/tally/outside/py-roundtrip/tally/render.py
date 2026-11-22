"""Draw totals as rows for a terminal; this module never touches the ledger."""


BAR_WIDTH = 30
BAR = "#"


def rows(totals: dict[str, int], show_all: bool = False) -> list[str]:
    """One line per name shown, in the order given; [] when none is shown.

    A total of 0 is left out unless show_all. The largest positive total
    gets BAR_WIDTH marks, the rest are scaled (at least one for any positive
    total), and a negative total has no bar.
    """
    shown = {name: total for name, total in totals.items() if total or show_all}
    if not shown:
        return []
    name_width = max(len(name) for name in shown)
    total_width = max(len(str(total)) for total in shown.values())
    largest = max((total for total in shown.values() if total > 0), default=0)
    lines = []
    for name, total in shown.items():
        length = max(1, round(total * BAR_WIDTH / largest)) if total > 0 else 0
        bar = BAR * length
        lines.append(f"{name.ljust(name_width)}  {str(total).rjust(total_width)}  {bar}".rstrip())
    return lines


def empty_message(show_all: bool) -> str:
    """What show prints when it has no rows."""
    return "nothing tallied yet" if show_all else "nothing tallied yet (or every total is 0; try --all)"
