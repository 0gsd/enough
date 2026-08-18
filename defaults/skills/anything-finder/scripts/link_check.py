#!/usr/bin/env python3
"""
link_check.py — Check that candidate URLs actually resolve before you hand them to the
user, so a find card never contains a dead link. For URLs that fail, it prints a Wayback
Machine URL to try instead.

Pass URLs as arguments or via --file (one per line). Uses a HEAD-then-GET probe with a
normal browser User-Agent (some hosts reject HEAD or blank agents).

Examples:
  python3 rness/skills/anything-finder/scripts/link_check.py https://example.com/a https://example.com/b
  python3 rness/skills/anything-finder/scripts/link_check.py --file urls.txt
"""
import argparse
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/122.0 Safari/537.36 anything-finder/1.0")


def wayback(url):
    return "https://web.archive.org/web/2/" + url


def probe(url, method):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status


def check(url):
    for method in ("HEAD", "GET"):
        try:
            status = probe(url, method)
            if 200 <= status < 400:
                return True, status, ""
            # 4xx/5xx: try GET if we were doing HEAD, else report
            if method == "GET":
                return False, status, ""
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 429) and method == "HEAD":
                continue  # some hosts refuse HEAD or throttle; try GET
            if method == "GET" or e.code not in (403, 405, 429):
                return False, e.code, str(e.reason)
        except urllib.error.URLError as e:
            return False, None, str(getattr(e, "reason", e))
    return False, None, "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="URLs to check")
    ap.add_argument("--file", help="file with one URL per line")
    a = ap.parse_args()

    urls = list(a.urls)
    if a.file:
        with open(a.file) as f:
            urls += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if not urls:
        ap.error("give at least one URL, or --file")

    ok = dead = 0
    for u in urls:
        good, status, note = check(u)
        if good:
            ok += 1
            print(f"[OK  {status}] {u}")
        else:
            dead += 1
            tag = status if status is not None else "ERR"
            extra = f" ({note})" if note else ""
            print(f"[DEAD {tag}]{extra} {u}")
            print(f"    ↳ try Wayback: {wayback(u)}")
    print(f"\n{ok} ok, {dead} dead of {len(urls)}.")
    sys.exit(1 if dead else 0)


if __name__ == "__main__":
    main()
