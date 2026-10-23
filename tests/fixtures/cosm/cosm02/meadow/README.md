# Meadow Software — the running example, complete

Fictional, so every field can be filled: 9 nodes, 4 roles, 3 externals, 1 contract, 0 pending, and
the model reaches equilibrium (snapshot allowed). Use it to see what "done" looks like, and to try the
renderers in a few seconds:

    python3 ../../scripts/cosm.py lint .                         # 0 errors, 0 warnings, SNAPSHOT: allowed
    python3 ../../scripts/cosm.py deck . --html --svg            # meadow-internal.pdf, meadow-external.pdf, HTML, SVG pages
    python3 ../../scripts/cosm.py pack . --out CONTEXT.md

`meadow.sketch` is the same firm in the one-line shorthand; `cosm.py expand meadow.sketch` turns it into
a draft with every unfilled aspect, including mattering, marked pending.
