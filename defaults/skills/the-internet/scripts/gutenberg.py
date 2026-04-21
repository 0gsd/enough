#!/usr/bin/env python3
"""Download a Project Gutenberg book as plain text via Tor, or search the catalog.

Usage:
    python gutenberg.py 2701                        # download Moby Dick (id 2701)
    python gutenberg.py 2701 --output moby.txt      # custom output path
    python gutenberg.py --title "Moby Dick"         # search catalog, print JSON

Book IDs come from the URL: gutenberg.org/ebooks/2701  ->  2701
"""
import argparse
import json
import sys

from tor_client import check_tor_running, tor_session


def _candidate_urls(book_id):
    """Gutenberg's canonical plain-text URLs, in preference order."""
    return [
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt",
        f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8",
    ]


def download_by_id(book_id, output_path=None):
    check_tor_running()
    # Reuse one circuit across the candidate attempts — they're all the same site.
    s = tor_session(isolation_id=f"gutenberg-{book_id}")
    last_err = None
    for url in _candidate_urls(book_id):
        try:
            r = s.get(url, timeout=60, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 1000:
                text = r.text
                if output_path is None:
                    output_path = f"gutenberg-{book_id}.txt"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text)
                return output_path, len(text), url
            last_err = f"{url} -> HTTP {r.status_code} ({len(r.text)} bytes)"
        except Exception as e:
            last_err = f"{url} -> {e}"
    raise RuntimeError(
        f"Could not download Gutenberg book {book_id}. Last attempt: {last_err}"
    )


def search_by_title(title):
    """Search Gutenberg catalog. Returns list of {id, title, author}."""
    check_tor_running()
    s = tor_session()
    r = s.get(
        "https://www.gutenberg.org/ebooks/search/",
        params={"query": title},
        timeout=30,
    )
    r.raise_for_status()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.text, "lxml")
    results = []
    for li in soup.select("li.booklink"):
        a = li.select_one("a.link")
        if not a:
            continue
        href = a.get("href", "")
        if "/ebooks/" not in href:
            continue
        try:
            book_id = int(href.rstrip("/").split("/")[-1])
        except ValueError:
            continue
        t = li.select_one(".title")
        auth = li.select_one(".subtitle")
        results.append(
            {
                "id": book_id,
                "title": t.get_text(strip=True) if t else "",
                "author": auth.get_text(strip=True) if auth else "",
            }
        )
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "book_id",
        nargs="?",
        type=int,
        help="Project Gutenberg book ID (e.g. 2701 for Moby Dick)",
    )
    ap.add_argument("--title", help="Search catalog by title instead of downloading")
    ap.add_argument("--output", default=None, help="Output file path (for download)")
    args = ap.parse_args()

    if args.title and args.book_id:
        ap.error("Use either book_id or --title, not both")
    if not args.title and not args.book_id:
        ap.error("Provide a book_id (e.g. 2701) or --title 'search terms'")

    try:
        if args.title:
            results = search_by_title(args.title)
            print(json.dumps(results, indent=2, ensure_ascii=False))
            if results:
                print(
                    f"\n{len(results)} result(s). Re-run with a book_id to download.",
                    file=sys.stderr,
                )
            else:
                print("No matches.", file=sys.stderr)
        else:
            path, size, url = download_by_id(args.book_id, output_path=args.output)
            print(f"Saved {size:,} chars from {url}\n  -> {path}")
    except Exception as e:
        print(f"gutenberg failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
