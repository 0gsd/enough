"""Shared Tor SOCKS5 session helpers.

Stream isolation via SOCKS5 auth: Tor routes different (username, password)
tuples onto separate circuits, so the default behavior of giving each session
a random identity produces per-request unlinkability without needing the
control port or NEWNYM cooldowns.

Environment variables:
    TOR_SOCKS_HOST  (default 127.0.0.1)
    TOR_SOCKS_PORT  (default 9050; Tor Browser's bundled tor uses 9150)
"""
import os
import random
import socket
import string

import requests

TOR_SOCKS_HOST = os.environ.get("TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", "9050"))

# Small pool of common, non-distinguishing User-Agents. Randomizing here is
# better than sending a unique UA (which fingerprints you) and worse than
# masquerading as Tor Browser exactly (use Tor Browser if that matters).
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def check_tor_running():
    """Verify Tor SOCKS5 port is reachable. Raise RuntimeError if not."""
    try:
        with socket.create_connection(
            (TOR_SOCKS_HOST, TOR_SOCKS_PORT), timeout=3
        ):
            pass
    except (socket.error, OSError) as e:
        raise RuntimeError(
            f"Cannot reach Tor SOCKS5 at {TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}. "
            f"Is Tor running? See reference/tor-setup.md. "
            f"(underlying error: {e})"
        )


def _random_isolation_id(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def tor_session(isolation_id=None, timeout=30):
    """Return a requests.Session routed through Tor with stream isolation.

    If isolation_id is None, a random one is generated — each call gets an
    independent Tor circuit with a fresh exit node. Pass a stable string to
    reuse the same circuit across related requests (e.g., paginating one site).
    """
    if isolation_id is None:
        isolation_id = _random_isolation_id()
    # SOCKS username/password triggers IsolateSOCKSAuth -> separate circuit.
    # "socks5h" ensures DNS is resolved through Tor, not locally.
    proxy_url = (
        f"socks5h://{isolation_id}:isolated@{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}"
    )
    s = requests.Session()
    s.proxies = {"http": proxy_url, "https": proxy_url}
    s.headers.update(
        {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    # Stash timeout on the session for callers that want a default.
    s.request_timeout = timeout
    return s


def verify_exit():
    """Return the current exit node's apparent IP and Tor status."""
    s = tor_session()
    r = s.get("https://check.torproject.org/api/ip", timeout=15)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Tor client sanity check")
    ap.add_argument("--check", action="store_true", help="Verify Tor reachability")
    args = ap.parse_args()

    if args.check or True:  # --check is the only action; run it either way
        try:
            check_tor_running()
            info = verify_exit()
            print(
                f"OK: Tor reachable at {TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}. "
                f"Exit IP: {info.get('IP')}, IsTor: {info.get('IsTor')}"
            )
        except Exception as e:
            print(f"FAIL: {e}", file=sys.stderr)
            sys.exit(1)
