#!/usr/bin/env python3
"""Fetch a URL through Tor and return clean extracted text.

Usage:
    python fetch.py <url>                       # extracted article text
    python fetch.py <url> --raw                 # full raw HTML
    python fetch.py <url> --isolation-id ID     # reuse a specific circuit
"""
import argparse
import sys

from tor_client import check_tor_running, tor_session


def fetch(url, raw=False, isolation_id=None):
    check_tor_running()
    s = tor_session(isolation_id=isolation_id)
    r = s.get(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    if raw:
        return r.text
    # Primary: trafilatura for clean article extraction
    try:
        import trafilatura

        extracted = trafilatura.extract(
            r.text,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            url=url,
        )
        if extracted and len(extracted) > 100:
            return extracted
    except ImportError:
        pass
    # Fallback: crude tag strip with BeautifulSoup
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    # Collapse long runs of blank lines
    lines = [ln for ln in text.split("\n") if ln.strip()]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--raw", action="store_true", help="Return raw HTML")
    ap.add_argument(
        "--isolation-id",
        default=None,
        help="Reuse a specific circuit across calls with the same ID",
    )
    args = ap.parse_args()
    try:
        output = fetch(args.url, raw=args.raw, isolation_id=args.isolation_id)
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(output)


if __name__ == "__main__":
    main()
