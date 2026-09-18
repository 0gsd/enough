"""The browser half of the pre-commit suite (see scripts/ui_check.py).

Modules, in the order they matter:

    cdp.py           launch Chrome, speak DevTools Protocol over `websockets`
    server.py        scratch project + home servers via smoke_boot.build_env()
    driver.py        the declarative step vocabulary the screens are written in
    geometry.py      rect arithmetic + every is-this-a-finding rule (pure, tested)
    probes.js        the in-page measurements (clickables, overlap, clipping…)
    screens.py       THE SCREEN REGISTRY — the extension point; add yours here
    interactions.py  scripted MODE STACK scenarios with DOM assertions
    findings.py      finding records + the committed baseline
    baseline.json    accepted pre-existing findings, keyed by selector path

Zero new dependencies is a hard constraint of this package: `websockets`
comes free with `uvicorn[standard]`, and everything else is the standard
library.
"""

from __future__ import annotations

__all__ = ["cdp", "driver", "findings", "geometry", "interactions",
           "screens", "server"]
