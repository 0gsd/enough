# Deep-search techniques → the cross-cutting playbook

Read this whenever a mission stalls, or up front for anything genuinely buried. Finding is
a craft of *reformulation*, *knowing the specialist source*, and *following trails*. These
techniques apply across every category.

## 1. Query reformulation (the single biggest lever)

Don't repeat a failing query — rotate the frame:
- **Exact phrase** in quotes for a distinctive string (title, a line, an error message).
- **Synonyms & register**: everyday word ⇄ technical term ⇄ the term the *maker* uses.
- **Era-appropriate language**: old things were described in old words. A "wireless" not a
  "radio"; a "phonograph"; a "calculating machine." Historical fiction/objects especially.
- **Alternate names**: foreign release titles, working titles, retitles, model revisions,
  the pseudonym, the maiden name, the pre-merger company name. Find these on Wikipedia/
  IMDb/Discogs "a.k.a." fields, then re-search with them.
- **Narrow with operators**: `site:` against the specialist database (see each category
  ref), `filetype:pdf`, `intitle:`, date-range. **Broaden** by dropping the most
  constraining term when results are empty.
- **Language pivot**: search in the source language for foreign works, then translate back.

## 2. Go to the specialist source, not the general web

The general web is page 1 of a few big sites. The *find* usually lives in a domain-specific
archive or registry. Each category reference lists them — reach for those first (IMSLP for
scores, Reverb for gear, Unpaywall for papers, archive.org for old media, Codeberg/PyPI for
off-GitHub code, Digital Comic Museum for PD comics, and so on).

## 3. Follow the trail

- **Citation trails**: a paper's references and "cited by" lead to the open version or the
  better source. A Wikipedia article's footnotes and External Links are a curated
  bibliography — mine them.
- **People trails**: find the author/maker/uploader, then their own site/repo/channel,
  which often hosts the thing directly and legally.
- **Community trails**: the relevant subreddit, forum, Discord, or wiki almost always has
  a thread where enthusiasts already solved "where do I get X" — search the item + "reddit"
  / "forum" and read it.

## 4. Archives & caches (for buried, moved, or vanished things)

- **Wayback Machine** (web.archive.org): recover a dead URL, a pre-paywall snapshot, an
  old product page, a deleted post. Try the exact URL and the site's homepage near the
  relevant date.
- **archive.today** as a second snapshot source.
- **Internet Archive** broadly (books, film, audio, software, periodicals) for anything old.
- **Software Heritage** to recover source code that vanished from a forge.
- **Google cache / other search engines**: try a different engine (Bing, DuckDuckGo,
  Marginalia for indie/old-web, Yandex for non-English) — indexes differ.

## 5. Identifying a half-remembered thing

When the user can't name what they want ("that film where…", "a synth that does…", "a book
about…"):
1. Extract every concrete detail: era, medium, distinctive images/plot beats, a fragment of
   text/dialogue/lyric, form factor, a specific feature.
2. Search combinations of the most *distinctive* details (unusual specifics beat common
   ones), including on community Q&A ("Tip of My Tongue" subreddit, StackExchange, forums).
3. Produce a small ranked candidate list, confirm the top pick against the user's details,
   then locate it via the right category ref.

## 6. Access mechanics — legitimate, and used freely

- **Custom `User-Agent` / headers / cookies** are ordinary, legal parts of HTTP; the
  bundled `fetch_asset.py` sets a normal browser UA so sites that reject blank/botty agents
  serve the public file they'd serve any visitor. This is for reaching *public* content,
  not defeating access controls on content the user has no right to.
- **`fetch_url` is the default and the only content transport.** It handles the
  allowlist/Tor routing decision for you and caches what it retrieves under
  `rness/io/input/`, so a long mission doesn't fill your context window — `read_file` the
  cache path when you need the whole page. Never `curl` a page for its content. The
  bundled scripts are verification helpers (link liveness, registry license lookup, one
  file download with provenance), not a way around the broker.
- **If the broker denies a fetch**, tell the user the exact domain to add to
  `rness/policies/allowlists.md` (under `## Internet domains`), or which toggle to flip —
  then carry on with the sources you can reach, and name the unchecked ones in the
  deliverable. Never silently fail, never pretend you retrieved it, never try a different
  transport to get around the refusal.
- **Tor exit nodes get blocked** by Google, Cloudflare-fronted sites, and some news
  outlets. That's routing, not a dead end: pivot to an on-allowlist source for the same
  fact — `en.wikipedia.org`, `en.wikisource.org`, `www.gutenberg.org`, `archive.org`,
  `commons.wikimedia.org` — rather than retrying the same URL.
- **A local Wikipedia archive, if installed**, answers identification questions
  (`wiki_search` / `read_wiki_article`) instantly, offline, and without touching the
  network at all. Reach for it before reaching outward.
- **The line, restated:** find the *legitimate* copy (archive, repository, library,
  official host, PD edition, author copy). If the only source is piracy of an in-copyright
  work, report that and give the legal alternatives — that's a better answer anyway,
  because legit sources don't rot or malware you.

## 7. Verify before you deliver

- **Links resolve**: run `scripts/link_check.py` on your candidate URLs; replace or
  Wayback-fallback the dead ones. Never hand over a 404.
- **It's the real thing**: confirm the page actually contains the work/item, not a
  same-titled decoy, a stub, or a spam mirror.
- **Rights are as claimed**: verify PD against the jurisdiction rule, licenses by reading
  the actual license (`verify_license.py` for code), and image/asset terms on the source
  page — not a thumbnail badge.

## 8. Persistence budget & honest stop

Scale effort to difficulty: a couple of searches for easy finds; 10–20+ query variations
across 4–6 specialist sources for a hard one. Stop when you've either found it, or covered
the plausible specialist sources and the main reformulations — then deliver the honest
"here's the status and the closest thing" per the SKILL.md "when the thing isn't found"
section. Thoroughness *shown* (what you searched) is part of a trustworthy negative result.
