# Finding public-domain texts → markdown with provenance

Goal: return the requested text (or the best available edition of it) as clean markdown,
with provenance the user can cite and a defensible public-domain determination.

## Where to look (best-source-first)

1. **Project Gutenberg** (gutenberg.org) — 70k+ PD books, clean plain-text/HTML. Best for
   canonical English-language works. Each book has a bibliographic record with author,
   release date, and language.
2. **Standard Ebooks** (standardebooks.org) — beautifully typeset, proofread PD editions.
   Prefer for quality when available.
3. **Wikisource** (wikisource.org) — PD + freely-licensed texts, often with source-scan
   backing; excellent for documents, essays, speeches, treaties, shorter works, and
   translations. Multilingual subdomains.
4. **Internet Archive / Open Library** (archive.org, openlibrary.org) — scans + OCR text
   of vast numbers of books, including obscure and non-canonical ones. Best for "this
   isn't on Gutenberg." Full-text search inside books is available.
5. **HathiTrust** (hathitrust.org) — huge scholarly scan corpus; PD items are fully
   readable/downloadable. Good for academic and older material.
6. **Poetry-specific**: Poetry Foundation, Bartleby (older), Representative Poetry Online
   (rpo, U. Toronto) for verse with textual notes.
7. **Documents/history**: Avalon Project (Yale) for legal/diplomatic docs; Chronicling
   America (loc.gov) for historical US newspapers; Founders Online; Perseus (perseus.
   tufts.edu) for classical Greek/Latin + translations.
8. **Religious/philosophical**: Sacred-Texts (sacred-texts.com), CCEL.
9. **Non-English**: Wikisource language subdomains; Gallica (BnF, French); Deutsches
   Textarchiv (German); Biblioteca Virtual Miguel de Cervantes (Spanish).

Deep-search moves: search the title + author on the general web with
`site:gutenberg.org`, `site:archive.org`, `site:wikisource.org`; for fragments or
half-remembered lines, quote the exact remembered phrase; for "a poem about X by a
Victorian woman," search anthologies and the era's terms. See `techniques.md`.

## Verifying public domain (do this — don't assume)

Copyright status is **jurisdictional**. State the jurisdiction you're asserting for.

- **US rule of thumb (as of 2026):** anything published before **1930** is PD in the US.
  Works 1930–1977 depend on notice/renewal; many are actually PD but verify via Stanford
  Copyright Renewal Database or the fact that Gutenberg/HathiTrust already cleared it.
- **Life+70 countries (EU, UK, most of the world):** PD if the **author died before 1956**
  (roughly). So a work can be PD in the US but *not* in the EU, and vice-versa. Note this
  when it matters to the user's location or use.
- **Trust the aggregator's clearance** as strong evidence: if Project Gutenberg, Standard
  Ebooks, or HathiTrust (marked "Full view / Public Domain") hosts the full text, it's
  been vetted. Cite that as the provenance for the PD claim.
- **Translations and specific editions carry their own copyright.** A PD original (e.g.,
  Homer) may have an in-copyright modern translation. Point the user to a PD translation
  or note the distinction.

## Return format

Deliver the text as a markdown file in `rness/io/output/anything-finder/` (for anything
longer than a short excerpt), opened with a provenance header, then tell the user the path.
For short works (a single poem, a short passage) you may inline it in the reply. Copyright
caution: only reproduce full texts you have verified as public domain or openly licensed.

If the source is one enough already fetches directly — Gutenberg, Wikisource, Standard
Ebooks, archive.org are all on the default internet allowlist — `fetch_url` caches the
whole text under `rness/io/input/` for you; `read_file` that cache and write the clean
markdown out to the output folder rather than re-fetching.

```markdown
# <Title>
*<Author>* — <original publication year>

> **Source:** <e.g., Project Gutenberg, ebook #1234> · <URL>
> **Provenance:** transcribed from <edition/scan>; <translator if any>.
> **Rights:** Public domain in <jurisdiction> (<why — e.g., "published 1885; author d. 1902">).
> Retrieved <date>.

---

<the clean text, in markdown — preserve stanza/paragraph breaks, headings, section numbers>
```

If you can only find a scan (image PDF) with imperfect OCR, say so, give the archive
link, and offer to clean up the OCR text. If multiple editions exist, prefer the one with
the best provenance and note the choice.
