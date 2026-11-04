# The OES specifications and the MiniCOSM manifests

Copyright © 2026 Graham Smith. All rights reserved.

The four OES specifications bundled with enough — MacroCOSM OES (`docs/MACROCOSM_OES.md`), Thym (`docs/THYM.md`),
Ascribe (`docs/ASCRIBE.md`) and Comprise OES (`docs/COMPRISE_OES.md`) — are the canonical editions published at
cosmoes.org (https://cosmoes.org/: macro., thym., ascribe. and comprise.cosmoes.org), copied byte for byte from the
cosmoes-site repository by `scripts/sync_specs.py`, which records each copy's edition, revision date and sha256 in
`docs/specs.json`. They, the MiniCOSM manifests in this folder (`defaults/cosm/manifests/`), and the names MacroCOSM,
MiniCOSM, MicroCOSM, Canon, EMF and atem are **not** covered by this repository's Apache License 2.0, nor by any other
licence in this repository.

They are bundled for use within enough only: enough reads the manifests to open, check and draw `.cosm` files, and
shows the specifications in its docs viewer, refreshing them from cosmoes.org by the sync at release time and at run
time (once per launch, `enough/specs.py`, into `~/enough/specs/`). No other use, copying, redistribution or derivative
work is licensed. A licence for the specifications is still to be decided; until one is published at cosmoes.org, all
rights are reserved. A specification changes only at cosmoes.org, never here.

The reader, `enough/macrocosm.py`, and the vendored sync client, `enough/cosmoes_client.py` (cosmoes-site's
`client/cosmoes_client.py`, Apache License 2.0), are part of enough and released under the Apache License 2.0 with the
rest of the code (see `LICENSE` at the repository root).
