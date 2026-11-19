# The language library, as enough keeps it

This folder holds a copy of the cosmoes.org language library's shelf: the texts a fabulac's reliances cite (the
Python documentation, and later the other languages and standards). Everything here but this README is written by
`scripts/sync_languages.py` and is gitignored.

    uv run python scripts/sync_languages.py            # from ../../cosmoes-site (its library/ folder)
    uv run python scripts/sync_languages.py --check    # what differs; writes nothing
    uv run python scripts/sync_languages.py --from DIR # another checkout, or a shelf folder holding library.json

After a sync:

    library.json                                  the registry, byte for byte as cosmoes-site has it
    synced.json                                   what was copied, from which commit, when
    <shelf>/<text>/<version>/files/...            the publisher's files as they came, never edited
    <shelf>/<text>/<version>/NOTICE               the licence and the copyright notice
    <shelf>/<text>/<version>/FETCHED              when and from where the owner fetched them
    <shelf>/<text>/<version>/SHA256SUMS           every file under files/ with its sha256

The sync refuses, writing nothing, when any kept text's folder does not match its SHA256SUMS or the registry.

## Why it is not committed

These are other publishers' texts under their own licences. cosmoes.org keeps and publishes them with their notices;
enough's repository carries none of them, so a licence is honoured in one place. They are also large (the Python
3.13 plain-text build alone is about 14 MB, its index about 31 MB) and change with every release a transconception
names. `reflib/dict` is committed because the dictionary is enough's own, with no other home.

## The index

`enough/language_library.py` builds one SQLite index from these files alone, with `enough/library_index.py`
(cosmoes-site's `client/library_index.py`, vendored byte for byte), under `~/enough/languages/library.sqlite`
(`ENOUGH_LANGUAGES_ROOT`), and rebuilds it whenever the shelf changes. enough reads the texts as text: it runs,
imports and installs nothing it finds here. A machine with no copy here still works: citations are carried, not
resolved, and `ground-cited` says so in a warning.
