# The OES specifications and the MiniCOSM manifests

Copyright © 2026 Graham Smith.

The four OES specifications bundled with enough — MacroCOSM OES (`docs/MACROCOSM_OES.md`), Thym (`docs/THYM.md`),
Ascribe (`docs/ASCRIBE.md`) and Comprise OES (`docs/COMPRISE_OES.md`) — are the canonical editions published at
cosmoes.org (https://cosmoes.org/: macro., thym., ascribe. and comprise.cosmoes.org), copied byte for byte from the
cosmoes-site repository by `scripts/sync_specs.py`, which records each copy's edition, revision date and sha256 in
`docs/specs.json`. They, the MiniCOSM manifests in this folder (`defaults/cosm/manifests/`), and the names MacroCOSM,
MiniCOSM, MicroCOSM, Canon, fabula (EMF, its earlier name) and atem are **not** covered by this repository's Apache
License 2.0.

**The specifications** are published under the Creative Commons Attribution 4.0 International licence (CC BY 4.0,
https://creativecommons.org/licenses/by/4.0/), with a patent promise under the Open Web Foundation Final
Specification Agreement 1.0 (OWFa 1.0) made by their author, Graham Smith.

**The manifests** are published under the same terms: CC BY 4.0, with the same OWFa 1.0 patent promise by the same
author.

**The names** are not licensed by either. They are held by the author for now, with the intent to move them later to
a body that is not a company.

enough reads the manifests to open, check and draw `.cosm` files, and shows the specifications in its docs viewer,
refreshing them from cosmoes.org by the sync at release time and at run time (once per launch, `enough/specs.py`,
into `~/enough/specs/`). A specification changes only at cosmoes.org, never here.

The reader, `enough/macrocosm.py`, and the vendored sync client, `enough/cosmoes_client.py` (cosmoes-site's
`client/cosmoes_client.py`, Apache License 2.0), are part of enough and released under the Apache License 2.0 with the
rest of the code (see `LICENSE` at the repository root).
