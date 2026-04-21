#!/usr/bin/env python3
"""Search the web via DuckDuckGo's HTML endpoint, routed through Tor.

DuckDuckGo's HTML interface works without JS and doesn't rate-limit Tor as
aggressively as Google. Results are returned as JSON to stdout.

Usage:
    python search.py "your query"
    python search.py "your query" --max-results 20
"""
import argparse
import json
import sys
from urllib.parse import parse_qs, unquote, urlparse

from tor_client import check_tor_running, tor_session

DDG_HTML = "https://html.duckduckgo.com/html/"


def _unwrap_ddg(href):
    """DDG wraps outbound URLs in a redirector; extract the real target."""
    if href.startswith("//duckduckgo.com/l/?") or href.startswith(
        "//html.duckduckgo.com/l/?"
    ):
        href = "https:" + href
    if "uddg=" in href:
        q = parse_qs(urlparse(href).query)
        if "uddg" in q:
            return unquote(q["uddg"][0])
    return href


def search(query, max_results=10):
    check_tor_running()
    s = tor_session()  # Fresh isolated circuit per search
    r = s.post(DDG_HTML, data={"q": query, "kl": "wt-wt"}, timeout=30)
    r.raise_for_status()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.text, "lxml")
    results = []

    # DDG's markup drifts; try several known patterns.
    item_selectors = [
        "div.result",
        "div.web-result",
        "article[data-testid='result']",
    ]
    items = []
    for sel in item_selectors:
        items = soup.select(sel)
        if items:
            break

    for item in items[:max_results]:
        title_a = (
            item.select_one("a.result__a")
            or item.select_one("h2 a")
            or item.select_one("a[data-testid='result-title-a']")
        )
        snippet_el = item.select_one(".result__snippet") or item.select_one(
            "[data-testid='result-snippet']"
        )
        if not title_a:
            continue
        raw_href = title_a.get("href", "")
        real_url = _unwrap_ddg(raw_href)
        results.append(
            {
                "title": title_a.get_text(strip=True),
                "url": real_url,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            }
        )
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("query")
    ap.add_argument("--max-results", type=int, default=10)
    args = ap.parse_args()

    try:
        results = search(args.query, max_results=args.max_results)
    except Exception as e:
        print(f"search failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print(
            "No results (DDG may have returned a CAPTCHA or changed its markup). "
            "Try again; each retry uses a new circuit.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
