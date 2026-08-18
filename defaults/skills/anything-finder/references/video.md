# Finding rare / lost / out-of-print video → watchable URLs

Goal: return a URL where the user can **legally** watch the requested film, episode, or
video, or — if no legal stream exists — the honest status and the routes that do exist
(library, disc, archive, purchase). Never hand over a piracy link as the answer; if that's
all that exists, say so and pivot to legal options.

## Where to look (by type)

**Public-domain & archival film/video** (fully free, fully legal):
1. **Internet Archive** (archive.org) — enormous free film/TV/video collection: PD
   features, ephemeral/industrial film (Prelinger), news, home movies, uploaded TV.
   First stop for anything old or "lost."
2. **Library of Congress** National Screening Room; **NARA** (archives.gov) for gov film.
3. **YouTube** — official channels, restored PD films, archival uploads. Note: distinguish
   an official/rights-holder upload from a random reupload; prefer the former.
4. **National/regional film archives**: BFI Player (UK), EUscreen (European TV heritage),
   NFB (Canada, nfb.ca — free), Australia's NFSA, DEFA/European archives.

**Commercially available but obscure** (find *where* it streams/sells):
5. **JustWatch** (justwatch.com) and **Reelgood** — locate which service streams/rents a
   title in the user's country. Best tool for "where can I watch X."
6. **Library streaming** — **Kanopy** and **Hoopla** stream huge catalogs *free* with a
   library card, including art-house, documentary, and Criterion-adjacent titles. Always
   mention these for hard-to-find "real" films.
7. **Boutique labels / rental**: Criterion Channel, MUBI, Fandor-likes, OVID, Le Cinéma
   Club, Nightflight, Night Flix, distributor sites; Vimeo On Demand for indie/self-
   released work; the filmmaker's own site.
8. **Physical media**: if it's only on DVD/Blu-ray/VHS, point to it — Discogs (yes, video
   too), eBay, distributor, or a **library hold** via WorldCat (worldcat.org).

**Lost / bootleg-only / never-released**:
9. Fan/archival wikis (Lost Media Wiki), collector communities, and the **Media History
   Digital Library** for pre-1964 trade context. If a work is genuinely "lost" or only
   circulates unofficially, report that status, name where scholars discuss it, and note
   any restoration efforts — don't route to a warez host.

## Deep-search moves

- Search the exact title + year + director; add "watch online," "streaming," "archive.org."
- For TV: search `<show> <episode title or S0xE0y> archive` and check whether a network/
  official channel posted it.
- Alternate/original titles matter enormously (foreign release titles, working titles,
  re-release retitles). Find them via IMDb/Wikipedia "also known as," then re-search.
- For "I saw this thing once and can't name it," use the identifying-a-half-remembered-
  work technique in `techniques.md` (plot beats, era, distinctive images → candidate
  titles → confirm).

## Return format

For each result, a find card with the **watch link**, the **host/service**, whether it's
free / library / rental / purchase, the **country** the availability applies to (streaming
rights are regional — note it), and legality. Lead with the best legal option.

```
### <Title> (<year>, dir. <name>)
- **Watch:** <URL>
- **Source:** <Internet Archive | Kanopy (library) | JustWatch → Service | disc via WorldCat…>
- **Provenance:** <official upload / restored PD print / archive scan>
- **Rights:** <public domain | licensed stream, region: US | rent $X | library card needed>
- **Confidence:** <…>
```

If nothing legal is online: say so, give the disc/library/archive route, and note any
known restoration or rights-holder so the user can follow up.
