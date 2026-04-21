---
name: the-internet
description: Access the open web through Tor with per-request circuit isolation, so exit nodes and destination sites can't correlate which requests came from the same source. Use whenever the user wants to read a URL, search the web, or download a public text file (Project Gutenberg books, RFCs, academic preprints, government docs, manifestos, static documents) without their research being attributable or linkable to them. Also trigger for "fetch this URL anonymously," "search the web," "download this book," "grab this article," "read this page without being tracked," "the-internet," "tor search," "tor fetch," "unlinkable browsing," "gutenberg download," or any request for anonymized web access. DO NOT use for logging into accounts, accessing paywalled/geo-gated content licensed to the user's identity, or any request where identity needs to persist across requests — Tor deliberately defeats continuity. Does NOT execute JavaScript; for SPA / JS-rendered pages the fetch will return a sparse shell.
---

# the-internet

A skill that gives your harness anonymized, unlinkable web access. It wraps a local
Tor daemon and routes HTTP through SOCKS5 with **stream isolation**: by default,
each request travels on its own three-hop Tor circuit with its own exit node, so the
destination site has no network-layer signal to link that request with any other
request you made.

Direct implementation of the capability Vitalik Buterin suggested somebody should
build: internet research without sites learning *who* the requests came from or
*which requests came from the same source as which others.*

---

## When to use

**Use it for:**

- Reading any web page the user links or describes ("read this article," "what does
  this page say," "summarize this")
- Searching the web ("find recent writing on X," "search for Y")
- Downloading plain-text files — Gutenberg books, RFCs, papers, government filings,
  static docs, CSVs, any file the user wants on disk
- Research that shouldn't be attributable: price checking, legal research, journalism,
  medical questions, adversarial review of your own work, reading dissident media,
  reading about a former employer

**Don't use it for:**

- Anything requiring login or session persistence — Tor rotates exits, most sites
  demand re-verification on each circuit, and the moment you log in you've defeated
  the point
- Sites that require JavaScript to render content (Twitter, Reddit's new UI, most
  modern news sites with lazy-loading). This skill fetches raw HTML only. If the
  user needs a JS-rendered page, say so and suggest a headless-browser route instead
- Illegal content, stalking, doxing, harassment. See `reference/ethical-use.md`

---

## Prerequisites

A local Tor daemon with SOCKS5 on **127.0.0.1:9050**. You have two paths:

**Agent-managed (no sudo, fully self-hosting).** The skill ships a bootstrap
script that downloads the official Tor Expert Bundle from torproject.org,
verifies its GPG signature against the Tor Browser Developers key, extracts it
to `~/.local/share/the-internet/`, and launches it as a user process. No
system install, no sudo, no persistent service. This is the path that keeps
the skill in line with rness's sovereignty principle.

**System-managed.** A one-time `sudo apt install tor && sudo systemctl enable --now tor`
(or equivalent) gives you a persistent background service that every skill
and agent on the machine can share. Less portable but zero per-invocation
overhead.

`bootstrap.py --ensure-running` detects which situation you're in and acts
accordingly: if a Tor is already reachable (because you installed it system-wide
or another skill started one), it does nothing; otherwise it installs and
launches the agent-managed bundle. Idempotent — safe to call every time.

See `reference/tor-setup.md` for more on each path.

Python deps (once):

    pip install -r requirements.txt

---

## Workflow

Before invoking anything else, always:

1. **Ensure Tor is running.**

       python scripts/bootstrap.py --ensure-running

   This is the one-shot: it checks if Tor is already reachable, and only if
   it isn't, installs the Expert Bundle (first run only) and launches it.
   Idempotent, safe to call every time. Takes ~2 seconds if Tor is already
   up, 30–60s for the first bootstrap, 10–15s for subsequent cold starts.

   If it fails — the download is blocked, the signature doesn't verify, no
   gpg available and the user wants strict verification — tell the user
   what happened; don't fall back to unrouted HTTP fetches silently.

2. **Pick the right tool:**

   | Task                              | Tool                        |
   | --------------------------------- | --------------------------- |
   | Read one page as clean text       | `scripts/fetch.py <url>`    |
   | Search the web                    | `scripts/search.py "query"` |
   | Download Gutenberg book by ID     | `scripts/gutenberg.py <id>` |
   | Search Gutenberg catalog by title | `scripts/gutenberg.py --title "..."` |
   | Download any other static file    | `scripts/download.py <url> --output path` |

3. **Use isolation deliberately.**

   - **Default (no `--isolation-id`):** each invocation gets a fresh random identity
     → different circuit → different exit node. Use this when the requests are
     unrelated and you want sites unable to link them.
   - **Shared (`--isolation-id <string>`):** same string = same circuit for the batch.
     Use this when you're following pagination, loading linked documents on the
     *same* site, or doing anything where flooding a site with requests from many
     different IPs would itself look suspicious or trigger a rate-limit / CAPTCHA
     wall. Within one site, behaving like one user is less anomalous than behaving
     like fifty.
   - Rule of thumb: **different sites → different isolation** (default random).
     **Same site, related requests → shared isolation.**

4. **Extract vs. preserve.** `fetch.py` runs `trafilatura` and returns just the
   article text by default — clean, no ads/nav/footer. `gutenberg.py` and
   `download.py` save the raw file byte-for-byte. Pick accordingly.

5. **Be polite.** Tor exit nodes are volunteer-run. Don't parallelize. Sleep
   ~1 second between requests on the same circuit. None of the scripts parallelize
   by default — keep it that way unless the user has a specific reason.

6. **If a site CAPTCHAs you, don't solve it.** Cloudflare and similar Tor-wall
   aggressively. Try a different source (archive.org, a mirror, a cached version)
   or tell the user the site is Tor-hostile.

---

## Tool reference

### `scripts/fetch.py`

    python scripts/fetch.py <url> [--raw] [--isolation-id ID]

Fetches one URL. By default, extracts the main article text using `trafilatura` —
returns clean prose with no nav/ads/footer. Pass `--raw` to get the full HTML
instead. Prints to stdout.

### `scripts/search.py`

    python scripts/search.py "query" [--max-results 10]

Hits DuckDuckGo's HTML endpoint (no JS required) over Tor. Returns a JSON array:

    [{"title": "...", "url": "...", "snippet": "..."}, ...]

URLs are already unwrapped from DDG's redirector. Follow up with `fetch.py` to read
any result. Each search uses its own fresh isolated circuit.

### `scripts/gutenberg.py`

    python scripts/gutenberg.py <book_id> [--output path]
    python scripts/gutenberg.py --title "Moby Dick"

Project Gutenberg IDs are in the URL: `gutenberg.org/ebooks/2701` → `2701`. The
script tries the canonical plain-text URLs in order and saves the first one that
works. With `--title`, searches the catalog and prints matches — pick an ID and
re-run.

### `scripts/download.py`

    python scripts/download.py <url> --output path [--isolation-id ID]

Generic streaming download. Works for any static file — txt, md, pdf, csv, tar.gz.
Saves raw bytes; does not extract text.

### `scripts/tor_client.py`

    python scripts/tor_client.py --check

Verifies Tor is reachable and reports the current exit IP via
`check.torproject.org`. Also serves as the shared module the other scripts
import for SOCKS session setup.

### `scripts/bootstrap.py`

    python scripts/bootstrap.py --ensure-running   # idempotent: install+start if needed
    python scripts/bootstrap.py --check            # is Tor reachable?
    python scripts/bootstrap.py --install          # download+verify+extract Expert Bundle
    python scripts/bootstrap.py --start            # launch managed tor
    python scripts/bootstrap.py --stop             # kill managed tor
    python scripts/bootstrap.py --status           # what's installed and running

Self-hosts a Tor instance in `~/.local/share/the-internet/` by downloading
the Tor Expert Bundle from torproject.org, verifying its GPG signature against
the Tor Browser Developers key, and launching it as a user process. No sudo
needed. Override install location with `THE_INTERNET_HOME` env var.

---

## Anonymity model — the short version

See `reference/anonymity-model.md` for the full writeup.

**Protected:**
- Your real IP never reaches the destination
- Different requests (default) look like they came from different, uncorrelated IPs
- Your ISP sees Tor traffic, not URLs or content

**Not protected:**
- Semantic correlation. If you fetch 50 pages on the same obscure topic in one
  hour, that's a fingerprint no transport-layer tool can hide. Tor fixes the pipe,
  not the contents
- Anything you do while logged in to an account that identifies you
- Timing analysis by a global passive adversary (Tor's known weakness — if that's
  your threat model, use Tor Browser, not this skill)

---

## Ethical use

See `reference/ethical-use.md`. The skill defaults to helping with legitimate
research — journalism, legal, medical, privacy-preserving browsing, open text
retrieval. It refuses CSAM, operational violence planning, unauthorized account
access, stalking, and doxing. Normal adult internet use — including things that
are *unflattering to the user*, like researching their own legal exposure or
reading about topics they'd rather not have profiled — is fully supported.
