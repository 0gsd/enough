# Finding copyright-cleared images → files + reference URLs + attribution

Goal: find images that are genuinely safe to use in an album cover, poster, zine, or
release — public domain, CC0, or clearly licensed — then **download the file(s)** to
`rness/io/output/anything-finder/`, record the license and attribution, and hand the user
the paths. The deliverable is files-you-can-actually-drop-into-a-layout, not just a search
page.

## Where to look (by rights type)

**Public domain / CC0 (no attribution required, safest for commercial cover art):**
1. **Wikimedia Commons** (commons.wikimedia.org) — millions of files; filter by license;
   PD and CC0 items are ideal. Each file page states the exact license + author.
2. **Internet Archive** image collections; **Openverse** (openverse.org) — aggregates CC
   + PD images across sources with license filters.
3. **Museum open-access**: The Met (metmuseum.org/art/collection — CC0 on open-access
   works), Art Institute of Chicago, Rijksmuseum (rijksstudio — hi-res PD), NGA (US),
   Smithsonian Open Access (CC0), NYPL Digital Collections, Cleveland Museum, Getty
   Open Content, Biodiversity Heritage Library (PD natural-history plates — great for
   covers). These are gold for striking, unusual, license-clean art.
4. **Stock (CC0-ish, commercial-OK, usually no attribution):** Unsplash, Pexels, Pixabay
   — check each one's current license terms; generally free for commercial use but with
   restrictions on redistribution/"as-is" resale. Good for photographic backgrounds.
5. **PD photo archives**: Flickr Commons (institutional PD sets), USF/NASA image
   libraries, LOC Prints & Photographs, Old Book Illustrations, PublicDomainReview.

**Attribution-required (CC-BY / CC-BY-SA — usable but you MUST credit; SA is copyleft):**
6. Flickr with a CC filter, Wikimedia CC-BY files. Capture the exact attribution string.

## The license-verification rule (critical for cover art)

Cover art is a *commercial, public* use — get this right.
- **Read the file's own rights statement**, not a thumbnail label. Open the source page
  and record the precise license (PD / CC0 / CC-BY-4.0 / CC-BY-SA / etc.) and the author.
- **Prefer PD or CC0** for album/poster use — no attribution obligation, no share-alike
  trap. Flag **CC-BY-SA** and other copyleft image licenses since they can force
  licensing terms onto a derivative.
- **Watch for embedded third-party rights**: a CC0 *photo of* a modern sculpture, logo,
  building, or living person can still carry the artwork's copyright, trademark, or
  personality/publicity rights. Note these when the image contains such subjects.
- **"Free for personal use" ≠ commercial-cleared.** Many "free image" sites mean personal
  only. Don't return those for a release without flagging it.

## Download + provenance

Use `scripts/fetch_asset.py` to pull the actual file and write a provenance sidecar:

```
python3 rness/skills/anything-finder/scripts/fetch_asset.py --url "<direct image URL>" --name cover_bg \
  --license "CC0" --attribution "Rijksmuseum, public domain" --source "<page URL>"
```

It saves the image to `rness/io/output/anything-finder/` and writes `cover_bg.provenance.txt`
with source, license, and attribution. Grab the **highest-resolution** version available
(museum sites and Commons usually have a "download original / full resolution" link) —
cover art needs 300 DPI at print size.

## Return format

Tell the user where the file(s) landed — they can open them from the file tree — and give
a find card per image:

```
### <short description of the image>
- **File:** rness/io/output/anything-finder/<name>.<ext>  ·  **Reference:** <source page URL>
- **Source:** <Wikimedia Commons | The Met Open Access | Openverse → origin | …>
- **Rights:** <PD / CC0 → no attribution needed | CC-BY-4.0 → credit: "<string>">
- **Resolution:** <WxH> (<print-size note if relevant>)
- **Confidence:** <…>
```

Offer 3–6 options ranked by fit when the brief is loose ("something moody and botanical"),
and say which are truly attribution-free vs. which need a credit line. If the user wants
something no cleared image matches, note that generating original art is an alternative,
but this skill's job is *finding* cleared existing images.
