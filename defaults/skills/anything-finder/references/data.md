# Finding datasets, APIs, and public records → URLs + access notes

The information-retrieval finds: machine-readable **datasets**, **public APIs**,
**government / legal documents**, and **historical newspaper archives**. Return the source
URL plus honest access notes (free? key required? rate limits? license for reuse?).

## Datasets

- **Aggregators**: Hugging Face Datasets (huggingface.co/datasets — ML-ready, license per
  dataset), Kaggle Datasets, Google Dataset Search (datasetsearch.research.google.com —
  indexes datasets across the web), Papers with Code datasets, Awesome-public-datasets.
- **Government / official**: data.gov (US), data.europa.eu (EU), the ONS/Eurostat/World
  Bank/UN data portals, census bureaus, city open-data portals, OpenStreetMap for geo.
- **Academic**: Zenodo, Figshare, Dryad, ICPSR (social science), the dataset behind a
  specific paper (check the paper's "data availability" statement).
- **License matters for reuse**: capture whether it's CC0/CC-BY/ODbL/custom, and any
  "non-commercial / research-only" restriction. Note it in the card.

## Public APIs

- **Directories**: the "public-apis" lists (github.com/public-apis), APIs.guru,
  RapidAPI, ProgrammableWeb-successors, Postman public API network.
- Search by function ("free weather API no key", "public transit GTFS API <city>").
- Report the essentials: **auth** (none / free key / paid), **rate limits**, **cost**,
  **CORS/usage terms**, and whether it's actively maintained. A free-tier API with a
  brutal rate limit is a different answer than a truly open one — say which.

## Government & legal documents

- **US**: govinfo.gov, congress.gov, regulations.gov, the Federal Register, PACER/CourtListener
  (courtlistener.com — free court opinions + RECAP for filings), SEC EDGAR (company filings),
  USPTO/Google Patents (for a real prior-art search see `references/patents.md`),
  state/local portals.
- **International/legal**: EUR-Lex (EU law), national gazettes, WorldLII/BAILII (case law),
  UN Treaty Collection, national archives.
- **FOIA angle**: if a record isn't published, note that a FOIA/records request is the
  legitimate route and where to file it.

## Historical newspaper & periodical archives

- **Free**: Chronicling America (loc.gov — pre-1964 US, huge), Trove (Australia), Google
  News Archive, Europeana, DPLA (dp.la — aggregates US library/museum/archive digital
  collections), Internet Archive periodicals.
- **Subscription but library-accessible**: Newspapers.com, British Newspaper Archive,
  ProQuest/Gale Historical — reachable free through many library cards; say so.

## Deep-search moves

- For a dataset: describe the variables + domain + "dataset csv/parquet"; try HF + Google
  Dataset Search + the relevant gov portal.
- For "is there an API for X": search function + "API", check the public-apis list, and
  confirm it's live (some listed APIs are dead — verify).
- For a record: identify the *authoritative* holder (agency, court, registry) and go
  straight there rather than a secondhand blog.

## Return format

```
### <dataset / API / document>
- **Link:** <URL or saved file>
- **Source:** <Hugging Face | data.gov | CourtListener | Chronicling America…>
- **Access:** <free | free key required | library card | paid tier> — <rate limit / size / format>
- **Rights / reuse:** <CC0 | CC-BY | public record | research-only ⚠ | check terms>
- **Confidence:** <live & maintained? completeness?>
```

Prefer the authoritative, machine-readable, openly-licensed source; flag research-only or
gated ones so the user doesn't build on something they can't actually use.
