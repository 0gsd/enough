# Tor setup for the-internet

The skill expects a local Tor daemon listening for SOCKS5 on
**127.0.0.1:9050**. There are two supported paths to get one. The control
port is not required in either case — stream isolation works via SOCKS5 auth
alone.

---

## Path A: Agent-managed (recommended, no sudo)

The skill ships a bootstrap script that self-hosts Tor in user space. First
run downloads the official Tor Expert Bundle from torproject.org, verifies
its GPG signature against the Tor Browser Developers key, and extracts it to
`~/.local/share/the-internet/`. Subsequent starts are instant.

    python scripts/bootstrap.py --ensure-running

That's it. The command is idempotent: if Tor is already reachable (because
you installed it system-wide, or because another skill already started a
managed instance), it does nothing. If not, it installs the bundle (first
time only) and launches it.

**Trust model for auto-install:**

1. TLS to torproject.org for the download
2. GPG signature verified against key fingerprint
   `EF6E286DDA85EA2A4BA7DE684E2C6E8793298290` (the Tor Browser Developers
   signing key)
3. If gpg isn't installed, the script prints a clear warning and proceeds
   with TLS-only trust. Install gpg (`apt install gnupg` / `brew install gnupg`)
   and re-run `--install` to upgrade to full verification.

**Manual subcommands:**

    python scripts/bootstrap.py --status    # what's installed and running
    python scripts/bootstrap.py --install   # force re-download + re-extract
    python scripts/bootstrap.py --start     # launch (if installed but not running)
    python scripts/bootstrap.py --stop      # kill the managed process
    python scripts/bootstrap.py --check     # is port 9050 reachable?

**Where things live:**

    ~/.local/share/the-internet/
    ├── bundle/          # extracted Expert Bundle
    │   └── tor/tor      # the daemon binary
    ├── cache/           # downloaded tarballs + .asc signatures (kept)
    ├── data/            # Tor's DataDirectory (mode 700)
    ├── torrc            # generated config
    ├── tor.log          # Tor's own log
    └── tor.pid          # pid of the managed process

Override the install location with the `THE_INTERNET_HOME` environment
variable. Override the port with `TOR_SOCKS_PORT`.

---

## Path B: System service (one-time sudo, persistent)

If you'd rather have Tor as a background service every tool on the machine
can share, install it the normal way. The bootstrap script will detect the
already-running system service and use it instead of installing its own.

### Debian / Ubuntu

    sudo apt install tor
    sudo systemctl enable --now tor

### Fedora / RHEL

    sudo dnf install tor
    sudo systemctl enable --now tor

### Arch

    sudo pacman -S tor
    sudo systemctl enable --now tor

### macOS (Homebrew)

    brew install tor
    brew services start tor

### Docker (portable, no system install)

    docker run -d --name tor-proxy -p 127.0.0.1:9050:9050 dperson/torproxy

Stop it with `docker stop tor-proxy && docker rm tor-proxy`.

Verify any of the above with:

    python scripts/tor_client.py --check

---

## Using Tor Browser's bundled tor

Tor Browser ships its own `tor` on port **9150**, not 9050. You can point
the skill at it instead:

    export TOR_SOCKS_PORT=9150
    python scripts/fetch.py https://example.com

Tor Browser must be running for port 9150 to be open.

---

## Troubleshooting

### `bootstrap.py --install` fails with a signature verification error

**Do not ignore this.** It means either:

- The download was tampered with in transit (unlikely if TLS succeeded, but
  possible with a compromised root CA), or
- The Tor Browser Developers signing key has been rotated and the
  fingerprint hardcoded in bootstrap.py is stale.

To check #2, visit `https://support.torproject.org/tbb/how-to-verify-signature/`
and compare the current primary key fingerprint to the one in `bootstrap.py`.
If it has changed, update the `TOR_BROWSER_DEVS_FINGERPRINT` constant and
re-run.

### `bootstrap.py` says "gpg not found; skipping signature verification"

The script proceeded with TLS-only trust. This is okay for most threat
models but not ideal. Install gpg:

    sudo apt install gnupg       # Debian/Ubuntu
    brew install gnupg            # macOS

Then re-run `python scripts/bootstrap.py --install` to upgrade to full
verification.

### "Cannot reach Tor SOCKS5 at 127.0.0.1:9050"

The daemon isn't running. Either:

- You're on Path A and haven't bootstrapped yet:
  `python scripts/bootstrap.py --ensure-running`
- You're on Path B and the service stopped:
  `sudo systemctl start tor` (Linux) / `brew services start tor` (mac)
- Port 9050 is bound by something else. Check `ss -ltn | grep 9050` (Linux)
  or `lsof -i :9050` (mac). If it's another Tor (e.g., Tor Browser at 9150),
  set `TOR_SOCKS_PORT=9150`.

### Bootstrap download is slow

First download pulls ~15 MB from torproject.org over regular internet (no
Tor yet — chicken and egg). Subsequent starts are instant because the bundle
is cached in `~/.local/share/the-internet/cache/`.

### Requests hang for 30+ seconds on the first call after start

Tor is bootstrapping its circuits. Normal on a cold start — give it a
minute. `bootstrap.py --start` waits for `Bootstrapped 100%` in the log
before returning, so if you're calling `--ensure-running` you shouldn't hit
this; if you're calling the skill scripts directly without bootstrapping
first, you might.

### Site returns a CAPTCHA instantly

Cloudflare and similar WAFs frequently challenge Tor exit traffic. Options:

- Try a different source (archive.org, a mirror, a cached version via Wayback)
- Retry — each retry uses a new circuit with a new exit. Some exits are
  less flagged than others
- Accept that this particular site is Tor-hostile and tell the user

**Do not** fall back to non-Tor fetching silently. If the user needs the
page badly enough to burn anonymity, that's their call to make explicitly.

### Site returns sparse / empty HTML

The page is JavaScript-rendered. This skill does not run JS. Modern SPAs
(Twitter, Reddit, many news sites) return a shell with no content. Tell the
user; suggest a headless browser route (Playwright, Puppeteer) if they need
JS-rendered pages. That's outside this skill's scope — and headless browsers
leak more fingerprinting signal anyway, so anonymity is harder there.

### Download is extremely slow

Tor's median bandwidth is a fraction of a direct connection, and exit nodes
vary wildly. For large files (books are fine; videos are not), expect
minutes, not seconds. If throughput is unusable, request a new circuit by
re-running — new invocation = new exit node.

### Everything works but `check.torproject.org` says `IsTor: false`

Your TOR_SOCKS_PORT is probably wrong — you're proxying through something
else (a regular HTTP proxy, for instance). Double-check the port.

### Upgrading the bundled Tor

    python scripts/bootstrap.py --stop
    python scripts/bootstrap.py --install
    python scripts/bootstrap.py --start

`--install` re-scrapes torproject.org for the current stable version, so
it'll pick up new releases automatically.
