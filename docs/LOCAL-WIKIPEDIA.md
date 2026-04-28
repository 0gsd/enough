# Local Wikipedia for `infoworld/`

`enough`'s `infoworld/` directory (at `~/enough/infoworld/`, symlinked
into every project) is meant to hold offline reference material the
agent can grep through before falling back to its training data. The
`wiki/` subfolder is the natural home for Wikipedia content. This
document covers three ways to populate it, from lightest to heaviest.

The agent doesn't need fancy indexing — it uses `grep` and `read_file`,
both of which work great on plain text and markdown. Anything you can
get into `infoworld/wiki/` as `.txt` or `.md` is fair game.

---

## Option 1 — On-demand (lightest)

Best for: dipping in, picking up a few articles relevant to a current
project, no commitment.

The agent's default paradigm already knows how to fetch from
Wikipedia (via the internet allowlist in `.rness/policies/allowlists.md`)
and cache the result. Just ask:

> "Cache the Wikipedia article on the French Revolution into `infoworld/wiki/`."

The agent will:

1. Pull the plain-text source via `curl` against `en.wikipedia.org`
2. Save it under `~/enough/infoworld/wiki/wikipedia-french-revolution/article.txt`
3. Drop a sibling `_manifest.md` capturing the source URL, the
   CC-BY-SA license, and the retrieval date

This works well for the dozen or two articles you actually care about.
It's not a strategy for "cache all of Wikipedia."

If you want it project-local instead of global, ask for it under
`.rness/io/input/` instead.

---

## Option 2 — Kiwix ZIM bundles (recommended for bulk)

Best for: actually wanting a meaningful slice of Wikipedia offline.
Easiest non-technical bulk path.

[Kiwix](https://kiwix.org/) packages up the entire English Wikipedia
(and dozens of other corpora) into single `.zim` files. They ship
several sizes, from a curated few-thousand-article subset all the way
up to "every English article with images."

### Step 1 — Pick a ZIM size

Visit [kiwix.org/wiki/Content_in_all_languages](https://wiki.kiwix.org/wiki/Content_in_all_languages)
and search for "wikipedia_en". You'll see options like:

| ZIM | What's in it | Size on disk |
|---|---|---|
| `wikipedia_en_simple_all_nopic` | Simple English Wikipedia, text only | ~250 MB |
| `wikipedia_en_for_schools_nopic` | Wikipedia for Schools subset | ~1.5 GB |
| `wikipedia_en_all_nopic` | Full English Wikipedia, text only | ~50 GB |
| `wikipedia_en_all_maxi` | Full English with images | ~100+ GB |

For most users, `simple_all_nopic` or `for_schools_nopic` is the sweet
spot — meaningful coverage, manageable size. Download the latest dated
file from the index. (Kiwix mirrors are slow sometimes; the larger
files may take hours.)

### Step 2 — Install `zimdump`

`zimdump` is the command-line tool that extracts ZIM contents to plain
text/HTML. Install via Homebrew:

```bash
brew install zim-tools
```

(The Homebrew formula is named `zim-tools`; the binary it installs is
`zimdump`.)

### Step 3 — Extract to `infoworld/wiki/`

```bash
mkdir -p ~/enough/infoworld/wiki/wikipedia_en_simple
zimdump dump --dir=~/enough/infoworld/wiki/wikipedia_en_simple ~/Downloads/wikipedia_en_simple_all_nopic_2024-XX.zim
```

This drops every article as an HTML file under that directory. The
agent can `grep -r` through it and `read_file` individual articles.

### Step 4 (optional) — Convert HTML to plain text

If you want cleaner greps and smaller disk footprint, you can convert
HTML to text with `pandoc`:

```bash
brew install pandoc
cd ~/enough/infoworld/wiki/wikipedia_en_simple
find . -name '*.html' -exec sh -c '
  pandoc -f html -t plain "$1" -o "${1%.html}.txt"
  rm "$1"
' _ {} \;
```

This may take a while for larger corpora. You can skip it; the agent
handles HTML fine via `grep`.

### Step 5 — Tell the agent it's there

Once populated, just mention to the agent that `infoworld/wiki/` is
populated and it'll start consulting it before reaching for training
data. You can also edit `.rness/MOTIVATION.md` to note which corpora
are available locally.

---

## Option 3 — Wikipedia XML dumps + WikiExtractor (heaviest)

Best for: technical users who want fine control over what gets
extracted, or who want articles in a structured plain-text format
suitable for further processing.

### Step 1 — Download the dump

```bash
mkdir -p ~/Downloads/wikipedia
cd ~/Downloads/wikipedia
curl -O https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2
```

This file is ~22 GB compressed (~80 GB uncompressed). The download is
slow. Plan for an hour or two. Don't bother decompressing — WikiExtractor
reads the bz2 directly.

### Step 2 — Install WikiExtractor

```bash
pip install --user wikiextractor
```

(Or use a venv: `python3 -m venv ~/.venvs/wikiext && source ~/.venvs/wikiext/bin/activate && pip install wikiextractor`.)

### Step 3 — Run the extraction

```bash
wikiextractor --json -o ~/enough/infoworld/wiki/wikipedia_en_full \
  ~/Downloads/wikipedia/enwiki-latest-pages-articles.xml.bz2
```

This takes hours on Apple Silicon. Output is sharded into directories
of compressed JSON files (one article per JSON object), which is great
for scripted processing but a little awkward for grep.

If you want plain text instead of JSON, drop the `--json` flag:

```bash
wikiextractor -o ~/enough/infoworld/wiki/wikipedia_en_full \
  ~/Downloads/wikipedia/enwiki-latest-pages-articles.xml.bz2
```

That produces files where each article is bracketed by `<doc id="..." title="...">` / `</doc>` tags around the body text. `grep` works fine on those.

### Step 4 — Free the disk

Once extracted and verified, delete the `.bz2` to reclaim ~22 GB:

```bash
rm ~/Downloads/wikipedia/enwiki-latest-pages-articles.xml.bz2
```

---

## Maintenance

- **Updates:** Wikipedia changes constantly. Re-running Option 2 or 3
  every 6–12 months gives you a refresh. Old extractions can be deleted
  cleanly by removing the relevant subdirectory under
  `~/enough/infoworld/wiki/`.
- **Multiple languages:** Kiwix has ZIMs for every Wikipedia language.
  Drop them in parallel subfolders (`wikipedia_en_simple/`,
  `wikipedia_es_simple/`, etc.) — the agent will see them all.
- **Other Kiwix corpora:** Stack Exchange, Project Gutenberg, WikiHow,
  TED talks, and many other sources have ZIM files. They all extract
  the same way; they're all just plain text once `zimdump` is done.

---

## License notes

Wikipedia content is licensed under **CC BY-SA 4.0** (with some legacy
content under CC BY-SA 3.0 + GFDL). You're free to use it for personal
reference. If you incorporate Wikipedia text into derivative works
you'll publish, you need to attribute and share-alike. Check
[en.wikipedia.org/wiki/Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights)
for the canonical rules.

The `_manifest.md` files the agent drops next to cached articles are
specifically designed to make attribution easy later — they capture the
URL, the license, and the retrieval date in one place.
