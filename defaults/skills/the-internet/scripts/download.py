#!/usr/bin/env python3
"""Download any text or binary file through Tor.

Streams the response — handles files larger than memory. Saves raw bytes;
does not extract text. For extraction, use fetch.py.

Usage:
    python download.py <url> --output path
    python download.py <url> --output path --isolation-id ID
"""
import argparse
import sys

from tor_client import check_tor_running, tor_session


def download(url, output_path, isolation_id=None, chunk_size=65536):
    check_tor_running()
    s = tor_session(isolation_id=isolation_id)
    total = 0
    with s.get(url, timeout=60, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--output", required=True, help="Output file path")
    ap.add_argument(
        "--isolation-id",
        default=None,
        help="Reuse a specific circuit (e.g. for related files from one site)",
    )
    args = ap.parse_args()

    try:
        size = download(args.url, args.output, isolation_id=args.isolation_id)
    except Exception as e:
        print(f"download failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Saved {size:,} bytes -> {args.output}")


if __name__ == "__main__":
    main()
