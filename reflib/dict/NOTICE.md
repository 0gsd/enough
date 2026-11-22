# free enough enumerated dictionary (FEED)

Copyright © 2026 Graham Smith.

The files in this folder (`reflib/dict/`) are the public edition of the Enough Dictionary, published as FEED, the
free enough enumerated dictionary. enough builds its local dictionary database from them. They are **not** covered
by this repository's Apache License 2.0.

## The terms

**The data.** The dictionary data in this folder is licensed under the Creative Commons Attribution-ShareAlike 4.0
International licence (CC BY-SA 4.0): https://creativecommons.org/licenses/by-sa/4.0/. You may copy it, share it and
change it, for any purpose, on that licence's terms. Something you make from it and share is shared under the same
licence.

**Attribution.** A copy, or anything made from one, carries the attribution the licence asks for:

- the author, Graham Smith;
- the dictionary's name and edition: FEED, the free enough enumerated dictionary, edition 1.9;
- a link to its home: https://github.com/0gsd/enough (the edition is in `reflib/dict/`);
- the licence's name and link, and a note if you changed the data.

The edition is `dictionary_version` in `meta.jsonl`; `scripts/sync_dictionary.py` sets it in this notice.

**The code.** enough's code, including the code that builds and reads this dictionary, is licensed under the Apache
License, Version 2.0 (`../../LICENSE`). That licence does not cover the data, and CC BY-SA 4.0 does not cover the
code.

**The names.** The licence does not license the names: FEED, enough, and the other names enough and its
specifications introduce. The author holds the names for now.

## What comes from other works

The definitions, examples, usage notes, origins and translations were written for the dictionary, with published
dictionaries read as evidence and not copied. Some columns draw on other works, which keep their own terms:

- **Synonyms** (the `synonyms` column and table, and the synonyms in `forms`) come from WordNet 3.1, by Princeton
  University, under the WordNet licence, which asks that its notice below appear on all copies.
- **Pronunciations**: many of the first edition's were drafted from suggestions converted from the Carnegie Mellon
  University Pronouncing Dictionary (CMUdict), © Carnegie Mellon University, under its own BSD-style licence, and
  from Wiktionary's pronunciations (through the Kaikki.org extract), under CC BY-SA, then checked and corrected.
- **Frequency bands** (`frequency_rank`) are computed with wordfreq 3.1, by Robyn Speer, whose word data is
  licensed under CC BY-SA 4.0 and draws on SUBTLEX (Marc Brysbaert et al.), Wikipedia, OpenSubtitles, Google Books
  Ngrams and other corpora.

The WordNet notice:

```
This software and database is being provided to you, the LICENSEE, by
Princeton University under the following license.  By obtaining, using
and/or copying this software and database, you agree that you have
read, understood, and will comply with these terms and conditions.:

Permission to use, copy, modify and distribute this software and
database and its documentation for any purpose and without fee or
royalty is hereby granted, provided that you agree to comply with
the following copyright notice and statements, including the disclaimer,
and that the same appear on ALL copies of the software, database and
documentation, including modifications that you make for internal
use or for distribution.

WordNet 3.1 Copyright 2011 by Princeton University.  All rights reserved.

THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON
UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PRINCETON
UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES OF MERCHANT-
ABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE OR THAT THE USE
OF THE LICENSED SOFTWARE, DATABASE OR DOCUMENTATION WILL NOT
INFRINGE ANY THIRD PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR
OTHER RIGHTS.

The name of Princeton University or Princeton may not be used in
advertising or publicity pertaining to distribution of the software
and/or database.  Title to copyright in this software, database and
any associated documentation shall at all times remain with
Princeton University and LICENSEE agrees to preserve same.
```

This is a report of the terms the author has published, not legal advice.
