# Finding creative assets → fonts, textures, 3D, vectors, stock footage, PD comics

The design-adjacent finds: typefaces, textures, 3D models, vector art, icons, stock
footage, and public-domain comics. All license-sensitive — return the file or URL with the
exact usage terms, because "free" ranges from true CC0 to "free for personal use only" to
"desktop use but not embedding/commercial."

## Fonts

- **Open-source / libre (embeddable, commercial-OK):** **Google Fonts** (fonts.google.com —
  OFL/Apache, safe for almost anything), **Font Library / Fontsource**, **The League of
  Moveable Type**, **Velvetyne** (velvetyne.fr — adventurous libre display faces, great
  for covers/posters), **Open Foundry**, Adobe's open-sourced families (Source Serif/Sans).
- **License check**: prefer **SIL Open Font License (OFL)** — allows commercial use,
  bundling, and embedding, with the one rule that you can't sell the font *by itself*.
  Flag "free for personal use" faces as **not** cleared for a commercial release/poster.
- For a specific *look* ("blackletter," "1970s groovy display," "condensed grotesque"),
  search the trait + "open font license," or browse Velvetyne/Google Fonts categories.

## Textures, patterns, backgrounds

- Poly Haven (polyhaven.com — **CC0** textures/HDRIs, top-tier), ambientCG (CC0),
  Texture Ninja, Lost & Taken, and museum PD scans (paper/marbling from Rijksmuseum,
  Old Book Illustrations) for analog/vintage looks. Bias to CC0 for cover/poster use.

## 3D models

- Poly Haven (CC0), Sketchfab (filter to CC/downloadable — check per-model license),
  Thingiverse / Printables / MyMiniFactory (for printable STL — check license),
  Smithsonian 3D (open access), NASA 3D. Read the per-model license; it varies widely.

## Vectors & icons

- **Icons (open):** Lucide, Feather, Tabler, Material Symbols, Bootstrap Icons, Iconoir
  (MIT/CC — safe). **The Noun Project** (CC-BY, needs credit unless paid). **SVG Repo**,
  **openclipart** (CC0). For illustration: **unDraw** (open, permissive), **Humaaans**.
- Check license per set; MIT/CC0 sets are the no-friction choice.

## Stock footage / b-roll

- Pexels Video, Pixabay Video, Coverr, Mixkit, archive.org — generally free incl.
  commercial, but confirm each site's current terms and any "no standalone redistribution"
  clause. NASA/gov footage is PD.

## Public-domain comics (a fun deep cut)

- **Digital Comic Museum** and **Comic Book Plus** — thousands of **golden-age comics that
  fell into the public domain** (lapsed copyright/no renewal), fully downloadable. Great
  for collage, reference, homage, or reprint. Verify the specific book's PD status (these
  sites curate for it, which is good evidence) and note that *characters* later revived by
  a publisher may carry trademark even if the old issue is PD.

## Download + provenance

Use `scripts/fetch_asset.py` for files, capturing license + attribution in the sidecar.
Grab the highest resolution / correct format (OTF/TTF for fonts, source SVG for vectors).

## Return format

```
### <asset>
- **File / link:** <saved path or URL>  ·  **Reference:** <source page>
- **Source:** <Google Fonts | Poly Haven | Digital Comic Museum…>
- **Rights:** <OFL/CC0/MIT → clear for commercial+embed | CC-BY → credit: "<string>" | personal-use-only ⚠>
- **Format / spec:** <OTF | 4K CC0 texture | STL | SVG…>
- **Confidence:** <…>
```

Lead the user to the truly friction-free options (CC0/OFL/MIT) and clearly flag anything
attribution-required or personal-use-only so a commercial release doesn't inherit a trap.
