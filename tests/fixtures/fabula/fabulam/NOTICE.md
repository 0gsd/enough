# Notice for this folder

`PrimesCongruentOne.lean` is not enough's own work. It is a copy, whole and unchanged, byte for byte, of
`Mathlib/NumberTheory/PrimesCongruentOne.lean` from Mathlib (<https://github.com/leanprover-community/mathlib4>),
taken at commit `6ebcce37335bcb6bca64596e5d57bb3035648030`.

Its own header says:

```
Copyright (c) 2020 Riccardo Brasca. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Riccardo Brasca
```

It is distributed under the Apache License, Version 2.0. The licence's text is the file `LICENSE` at the root of
this repository, which is the same licence.

enough reads the file as text. It is the fixture a fabulam is built from in the tests. Nothing of it is built or
run here, and nothing here says that Lean accepts it.

## The fabulam made from it, and its three pshorts

`primes-congruent-one.fabulam.cosm` is a map of that file's proof, and the three files
`primes-congruent-one.pshort-<density>-2026-11-22-1200.md` are short guides written from the map alone. They are
enough's own, made by its pipeline on 2026-11-22. Model agents stood in as the model: one fresh agent for each
request, the reader of the proof seeing the Lean with its comments blanked, the writer of the pshorts seeing the
map and never the Lean. Their answers are kept as they were given, the refused tries too, under
`recorded/primes-congruent-one-run/`, and `tests/test_fabulam_fixture.py` rebuilds the four files from those
answers, byte for byte, with no model.

What to know before reading them:

- No mathematician has read them. A pshort is a guide to a formal proof. It is not a proof.
- Nothing of Lean was built or run. The map says so in its item `P:claim/checking`, and says no more than that.
- The file was read alone, outside a clone, so the map names no Lean version (`toolchain` is an open question) and
  its `module` is the file's own name.
- A second model read all four against the Lean and found no false statement about the Lean. It found two weak
  remarks in the map's yield, both the model's opinion: that `k` times the least common multiple would be the
  "best" point to evaluate at (not shown, and not the best), and that the least prime factor gives "the smallest
  witness" (the smallest factor of that one value only). The expert pshort repeats the second. They are left as
  the pipeline wrote them.
- The map ends in some forty questions for an expert, most of them of the form "is this right?". They come from a
  general bank of questions, and are more than a reader needs.

Every other file in this folder is enough's own, under the repository's licence. The small Lean files under
`own/` were written for these tests, were never built, and say so in their first line.
