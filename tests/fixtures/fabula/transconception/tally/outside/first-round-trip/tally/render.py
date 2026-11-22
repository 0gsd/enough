"""Drawing totals as rows for a terminal. Never touches the ledger."""

BAR_WIDTH = 30
BAR = "#"


def rows(totals: dict[str, int], show_all: bool = False) -> list[str]:
    """One line per name shown, in the order given; [] when none is shown.

    A row is the name padded to the longest name, two spaces, the total
    right-aligned to the widest total, two spaces, then a bar scaled so the
    largest positive total gets BAR_WIDTH marks; trailing space removed.
    """
    shown = {name: total for name, total in totals.items() if show_all or total != 0}
    if not shown:
        return []
    name_width = max(len(name) for name in shown)
    numbers = [str(total) for total in shown.values()]
    number_width = max(len(text) for text in numbers)
    largest = max((total for total in shown.values() if total > 0), default=0)
    lines = []
    for (name, total), text in zip(shown.items(), numbers):
        bar = BAR * max(1, round(total * BAR_WIDTH / largest)) if total > 0 else ""
        lines.append(f"{name.ljust(name_width)}  {text.rjust(number_width)}  {bar}".rstrip())
    return lines


def empty_message(show_all: bool) -> str:
    """What show prints when it has no rows."""
    if show_all:
        return "nothing tallied yet"
    return "nothing tallied yet (or every total is 0; try --all)"
