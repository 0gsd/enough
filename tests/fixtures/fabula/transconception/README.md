# Transconception fixtures

Two working fabulacs of the 0.7 experiment (x0, written 2026-11-13 in `fabulac-test-repos/_x0/`), promoted into the
shapes pinned for 0.8 by `tools/transconception/promote_x0.py`, with each round trip's verdict folded in as evidence.
They are the experiment's own writing about two open-source programs: what each program does, its rulings, its
recorded cases, and the program's own words where a ruling keeps them (messages, help, bundled files).

Nothing here is run. The tests (`tests/test_transconception.py`) read them through enough's reader.

## Credit and licences

- `vulture.fabulac.cosm` is written about **vulture** by Jendrik Seipp and its contributors
  (https://github.com/jendrikseipp/vulture, commit edd5806f56f0bec1d0fbb45c466c0f7a258a1795). vulture is under the
  MIT License, Copyright (c) 2012-2020 Jendrik Seipp; its notice is kept beside the fixture as `vulture.LICENSE.txt`,
  copied unchanged from the repository's `LICENSE.txt`.
- `sloppy-xml-py.fabulac.cosm` is written about **sloppy-xml-py** by Armin Ronacher
  (https://github.com/mitsuhiko/sloppy-xml-py, commit 74a02907a402eed6d0016bfacca5db3d72003be5; the author as its
  `pyproject.toml` names him). sloppy-xml-py is under the Apache License, Version 2.0; the licence is kept beside the
  fixture as `sloppy-xml-py.LICENSE`, copied unchanged from the repository's `LICENSE`. The repository carries no
  NOTICE file.

## What the promotion changed

The 0.7 words are mapped (`purpose: transcoding` to `transconception`, the role `transcoder` to `transconceiver`);
`ruling` is always a list; a reliance's `of` names the dependency it is a gift of and `used-by` the items that use it;
`cited` is dropped; `source.obtained: public` and `ruled-by` are added from the transconceiver's standing statement;
a path on the recording machine inside a recorded traceback is written from the home folder (`~/`). Everything else
is as the experiment wrote it. Re-made on 2026-11-18 after the owner's second sitting (`_x0/sitting-2.md`): the
experiment's generator wrote its rulings in (V-I14 and S-I0 split, S-I2 kept at the driver's dump, S-I6 narrowed to
the byte-file steps, the allowance `own-types` on 62 Rust rulings). Since phase 5 (2026-11-18) each also carries the
hand weighing of its target from step A7 (`_x0/vulture/target-go.md`, `_x0/sloppy-xml-py/target-rust.md`) in place
of the unweighed placeholder, its points named by number, and its spike's level read from the judge's verdict on the
spike at O9 (`results/2026-11-18-1819/<repo>/<language>-spike/verdict.json`; only the spike's own cases count).
Re-make them with:

    python tools/transconception/promote_x0.py <_x0>/vulture/vulture.fabulac.cosm \
        <_x0>/results/2026-11-13-1006/vulture/py-roundtrip/verdict.json \
        tests/fixtures/fabula/transconception/vulture.fabulac.cosm \
        --target <_x0>/vulture/target-go.md <_x0>/results/2026-11-18-1819/vulture/go-spike/verdict.json
    python tools/transconception/promote_x0.py <_x0>/sloppy-xml-py/sloppy-xml-py.fabulac.cosm \
        <_x0>/results/2026-11-13-1006/sloppy-xml-py/py-roundtrip/verdict.json \
        tests/fixtures/fabula/transconception/sloppy-xml-py.fabulac.cosm \
        --target <_x0>/sloppy-xml-py/target-rust.md <_x0>/results/2026-11-18-1819/sloppy-xml-py/rust-spike/verdict.json
