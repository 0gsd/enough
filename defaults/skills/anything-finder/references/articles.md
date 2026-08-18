# Finding paywalled / buried articles & academic papers → legit open copies

Goal: get the user a readable, legal copy of an article or paper that's behind a paywall,
buried, or hard to surface. The move is almost never "defeat the paywall" — it's "find the
copy that's already free and legal," because for most articles one exists (a preprint, an
author's posted copy, a repository deposit, an archived version). Route to that.

## Academic papers

**Open by design:**
1. **arXiv** (physics/math/CS/stat/econ/q-bio), **bioRxiv/medRxiv**, **SSRN** (social sci/
   law/econ), **PsyArXiv/OSF**, **ChemRxiv** — preprints, free, legal.
2. **PubMed Central** (ncbi.nlm.nih.gov/pmc) — free full text for biomedical.
3. **DOAJ** (Directory of Open Access Journals), **PLOS**, and any gold-OA journal.
4. **Unpaywall** / **OpenAlex** / **CORE** (core.ac.uk) / **BASE** / **Semantic Scholar** —
   aggregators that locate a *legal* free copy of a paywalled paper by DOI/title. These
   are the single best tools: search the title, get the OA link if one exists.
5. **Google Scholar** — click the "All N versions" and the right-hand `[PDF]` links; these
   frequently point to an author's or a repository's free copy.
6. **Author/institution copies**: search `<paper title> filetype:pdf`, the author's
   personal/faculty page, their lab site, ResearchGate/Academia.edu (author-posted),
   or the institutional repository. Many publishers *permit* the author to post the
   accepted manuscript — that copy is legal.
7. **Ask nicely**: note that emailing the corresponding author for a copy is normal,
   legal, and usually works — good fallback when no OA copy exists.

**Get the identifier first:** find the paper's **DOI** (via Crossref/Google Scholar),
then feed it to Unpaywall/OpenAlex — that's the highest-hit-rate path to a free legal PDF.

## Journalism / magazine / news articles

1. **The Wayback Machine** (web.archive.org) — the workhorse. Many articles were free when
   published and paywalled later, or have an archived pre-paywall snapshot. Search the URL;
   also try archive.today for a snapshot.
2. **Author/outlet syndication**: the same piece often runs on the author's Substack/blog,
   a syndicating outlet, a press-release wire, or is quoted at length elsewhere. Search a
   distinctive exact sentence in quotes.
3. **Library access** — most public libraries give free digital access to news databases
   (PressReader, ProQuest, Gale, and often direct NYT/WSJ/Economist passes) with a card.
   Mention this; it's the legit, complete route.
4. **Older / distant-past articles**: newspaper archives — Chronicling America (loc.gov,
   free, pre-1964 US), Trove (Australia, free), Google News Archive, Newspapers.com and
   the British Newspaper Archive (subscription, but often library-accessible), Gale/
   ProQuest Historical (library). For magazines, the Internet Archive holds many runs.

## Deep-search moves

- Search a **distinctive exact quote** from the article in quotes — surfaces mirrors,
  quotes, and archived copies.
- For a paper: title → DOI → Unpaywall/OpenAlex → author page → repository, in that order.
- Try the **Wayback Machine on the exact article URL**, and on the outlet's homepage near
  the publication date if the direct URL isn't captured.
- If truly locked, name the **library database** that carries it and how to reach it.

## Legality line

Use archives, preprints, repositories, author copies, and library access freely — all
legal. Do **not** route to or endorse credential-sharing or paywall-cracking sites that
host in-copyright work without permission; if that's the only "copy" online, say the
legal options are the archive/repository/library/author-request routes above.

## Return format

```
### <Article / paper title> — <author(s), year, venue>
- **Read:** <direct free-legal URL or saved PDF path>
- **Source:** <arXiv | PMC | Unpaywall→repository | author page | Wayback snapshot | library DB>
- **Version:** <published | accepted manuscript | preprint | archived snapshot>
- **Rights:** <open access | author-posted (legal) | archived (was public) | library-gated>
- **Confidence:** <…>
```

If you retrieve a PDF, save it to `rness/io/output/anything-finder/` and tell the user the
path. If only a library-gated copy exists, give the exact steps to reach it with a card.
