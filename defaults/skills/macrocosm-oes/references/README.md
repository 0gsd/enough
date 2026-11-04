# macrocosm-oes: where the sources are

This skill keeps no copies. Everything it teaches comes from these files,
named by their place in an enough install:

- `docs/MACROCOSM_OES.md` — MacroCOSM OES, the canonical edition published at
  https://macro.cosmoes.org/ (edition 0.5.4; grammar version 0.5.4, with 0.0.2 and
  0.0.1 read unchanged). In the app it opens in the docs viewer (the MacroCOSM
  button, a menu of the four specifications), at three densities. `docs/specs.json`
  names each bundled edition; enough keeps the four current from cosmoes.org.
- `defaults/cosm/manifests/comprise.manifest.cosm` — Comprise OES, the
  Holotype MiniCOSM (a byte copy of Comprise's own manifest).
- `defaults/cosm/manifests/cosm.manifest.cosm` — standalone COSM 0.2 and 0.3
  product trees.
- `defaults/cosm/manifests/canon.manifest.cosm` — Canon volume catalogs and
  project catalogs (`canon.cosm`).
- `defaults/cosm/manifests/emf.manifest.cosm` — EMF twins of texts.
- `defaults/cosm/manifests/doc.manifest.cosm` — DocOES: a document (this
  specification, the Help Center) enumerated into a doc volume.
- `defaults/cosm/manifests/thym.manifest.cosm` — Thym 1: programs, morphs,
  contexts, plans, traces and packages, with the moves Thym owns.
- `defaults/cosm/manifests/ascribe.manifest.cosm` — Ascribe 1: a holograph, a
  self described with no name.
- `defaults/cosm/manifests/comprise.moves.cosm` — the moves Comprise's
  MiniCOSM offers to Thym, beside its byte-copied manifest.
- `docs/THYM.md` — Thym (https://thym.cosmoes.org/), the MacroCOSM language: its
  programs, compiler and
  runtime. `defaults/thym/` holds the three programs enough ships
  (`publish-story`, `read-my-way`, `open-house`); `enough/thym/` is the
  reference compiler and runtime.
- `docs/ASCRIBE.md` — Ascribe (https://ascribe.cosmoes.org/): a holograph, a self
  described with no name. `docs/COMPRISE_OES.md` — Comprise OES
  (https://comprise.cosmoes.org/): a company as Comprise describes one, the
  Holotype and its isotype; the format `comprise.manifest.cosm` declares.
- `enough/macrocosm.py` — the reference reader. Where a specification and the
  reader disagree, one of them is in error and is corrected; the text's Changes
  section records which.

Sections of the specification worth knowing first: §2 the model on one page,
§3 the scales, §10 open questions, §11 ids, paths and URIs, §12 the checks,
§18 the five MiniCOSMs (§18.3.5 atems, §18.4 EMF, §18.5 DocOES).

MacroCOSM OES © 2026 Graham Smith; see defaults/cosm/NOTICE.md
