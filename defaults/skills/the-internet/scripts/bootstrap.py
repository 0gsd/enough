#!/usr/bin/env python3
"""Self-hosting Tor bootstrapper for the-internet skill.

Downloads, verifies, extracts, and launches the Tor Expert Bundle in user
space — no sudo, no system service. Idempotent: safe to re-run.

Subcommands:
    --check            Is Tor reachable on the SOCKS port? (yes/no + exit code)
    --install          Download + verify + extract the Expert Bundle
    --start            Launch the managed tor binary as a background process
    --stop             Kill the managed tor process
    --status           Report what's installed and what's running
    --ensure-running   The one-shot: check; if not up, install if needed, start

The agent should call --ensure-running on first use of the skill.

Trust model:
    1. Download is over HTTPS from torproject.org (TLS root).
    2. The tarball is verified against its GPG signature, signed by the
       Tor Browser Developers key (fingerprint EF6E286DDA85EA2A4BA7DE684E2C6E8793298290).
    3. If gpg is unavailable on the host, the script WARNS and proceeds with
       TLS-only trust. You'll see the warning; it's not silent.

Install location: ~/.local/share/the-internet/
"""
import argparse
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import textwrap
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTALL_DIR = Path(
    os.environ.get(
        "THE_INTERNET_HOME",
        str(Path.home() / ".local" / "share" / "the-internet"),
    )
)
DOWNLOAD_PAGE = "https://www.torproject.org/download/tor/"
TOR_BROWSER_DEVS_FINGERPRINT = "EF6E286DDA85EA2A4BA7DE684E2C6E8793298290"
KEYSERVER_URL = (
    f"https://keys.openpgp.org/vks/v1/by-fingerprint/"
    f"{TOR_BROWSER_DEVS_FINGERPRINT}"
)
DEFAULT_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", "9050"))


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform():
    """Return (os_str, arch_str) matching Tor's download filename pattern."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        os_str = "linux"
    elif system == "darwin":
        os_str = "macos"
    elif system == "windows":
        os_str = "windows"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    if machine in ("x86_64", "amd64"):
        arch_str = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch_str = "aarch64"
    elif machine in ("i686", "i386", "x86"):
        arch_str = "i686"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    return os_str, arch_str


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def socks_reachable(port=DEFAULT_SOCKS_PORT, host="127.0.0.1", timeout=2):
    """True if something is listening on the SOCKS port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, OSError):
        return False


def process_alive(pid):
    """True if process with given pid is alive (POSIX)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def download_file(url, dest_path, chunk_size=65536):
    """Stream-download a URL to disk using stdlib urllib."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_path.with_suffix(dest_path.suffix + ".part")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "the-internet-bootstrap/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        total = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
    tmp.rename(dest_path)
    return total


# ---------------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------------

def find_stable_bundle_url(os_str, arch_str):
    """Scrape torproject.org/download/tor/ for the current stable URL.

    Matches only strictly-numeric versions (e.g., 15.0.9) — skips alphas
    like 16.0a5.
    """
    req = urllib.request.Request(
        DOWNLOAD_PAGE,
        headers={"User-Agent": "the-internet-bootstrap/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    # Backreference forces version in path to match version in filename,
    # and \d+\.\d+\.\d+ rejects alpha versions (16.0a5).
    pattern = re.compile(
        r"https://[^\"']+/torbrowser/(\d+\.\d+\.\d+)/"
        rf"tor-expert-bundle-{re.escape(os_str)}-{re.escape(arch_str)}-\1\.tar\.gz"
    )
    m = pattern.search(html)
    if not m:
        raise RuntimeError(
            f"Could not locate stable Expert Bundle URL for "
            f"{os_str}-{arch_str} on the Tor download page. "
            f"They may have changed the page layout."
        )
    return m.group(0)


# ---------------------------------------------------------------------------
# GPG verification
# ---------------------------------------------------------------------------

def verify_signature(tarball_path, sig_path):
    """Verify the tarball's GPG signature. Returns True on success, False if
    skipped, raises on failure."""
    if not shutil.which("gpg"):
        print(
            "WARNING: gpg not found on this system. Skipping signature "
            "verification. You are trusting TLS to torproject.org alone. "
            "Install gpg (apt install gnupg / brew install gnupg) and re-run "
            "`bootstrap.py --install` for full cryptographic verification.",
            file=sys.stderr,
        )
        return False

    # Ensure the key is in the keyring
    key_check = subprocess.run(
        ["gpg", "--list-keys", TOR_BROWSER_DEVS_FINGERPRINT],
        capture_output=True,
        text=True,
    )
    if key_check.returncode != 0:
        print("Importing Tor Browser Developers signing key...", file=sys.stderr)
        # First try WKD (authoritative)
        wkd = subprocess.run(
            [
                "gpg",
                "--auto-key-locate",
                "nodefault,wkd",
                "--locate-keys",
                "torbrowser@torproject.org",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if wkd.returncode != 0:
            print(
                "  WKD lookup failed; falling back to keys.openpgp.org",
                file=sys.stderr,
            )
            # Fallback: fetch key from keys.openpgp.org over HTTPS
            try:
                req = urllib.request.Request(
                    KEYSERVER_URL,
                    headers={"User-Agent": "the-internet-bootstrap/1.0"},
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    key_data = r.read()
                imp = subprocess.run(
                    ["gpg", "--import"],
                    input=key_data,
                    capture_output=True,
                )
                if imp.returncode != 0:
                    raise RuntimeError(
                        f"Failed to import signing key: {imp.stderr.decode()}"
                    )
            except Exception as e:
                raise RuntimeError(
                    f"Could not import signing key (WKD and keys.openpgp.org "
                    f"both failed): {e}"
                )

    # Verify
    print("Verifying GPG signature...", file=sys.stderr)
    verify = subprocess.run(
        ["gpg", "--verify", str(sig_path), str(tarball_path)],
        capture_output=True,
        text=True,
    )
    combined = verify.stdout + verify.stderr
    if verify.returncode != 0:
        raise RuntimeError(
            f"SIGNATURE VERIFICATION FAILED. Do not use this binary.\n"
            f"{combined}"
        )

    # Confirm the primary fingerprint appears in output (defends against
    # signatures from a different key with the same UID).
    stripped = combined.replace(" ", "").replace(":", "")
    if TOR_BROWSER_DEVS_FINGERPRINT not in stripped:
        raise RuntimeError(
            f"Signature verified but expected primary fingerprint "
            f"{TOR_BROWSER_DEVS_FINGERPRINT} did not appear in gpg output. "
            f"Possible key substitution attack. Aborting.\n{combined}"
        )

    print("  GPG signature: Good", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install():
    """Download + verify + extract the Expert Bundle to INSTALL_DIR/bundle."""
    os_str, arch_str = detect_platform()
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = INSTALL_DIR / "cache"
    cache_dir.mkdir(exist_ok=True)
    bundle_dir = INSTALL_DIR / "bundle"

    print(f"Finding current stable URL for {os_str}-{arch_str}...", file=sys.stderr)
    url = find_stable_bundle_url(os_str, arch_str)
    print(f"  {url}", file=sys.stderr)

    filename = url.rsplit("/", 1)[1]
    tarball = cache_dir / filename
    sig = cache_dir / (filename + ".asc")

    if not tarball.exists():
        print(f"Downloading tarball ({filename})...", file=sys.stderr)
        size = download_file(url, tarball)
        print(f"  {size:,} bytes", file=sys.stderr)
    else:
        print(f"Tarball already in cache: {tarball}", file=sys.stderr)

    if not sig.exists():
        print("Downloading signature...", file=sys.stderr)
        download_file(url + ".asc", sig)

    verify_signature(tarball, sig)

    # Extract (clean any previous extraction first)
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    print(f"Extracting to {bundle_dir}...", file=sys.stderr)
    with tarfile.open(tarball, "r:gz") as tf:
        # Prefer data filter on 3.12+, fallback otherwise
        try:
            tf.extractall(bundle_dir, filter="data")
        except TypeError:
            tf.extractall(bundle_dir)

    tor_bin = _tor_binary_path(bundle_dir)
    if not tor_bin.exists():
        raise RuntimeError(
            f"Extraction succeeded but tor binary not found at expected "
            f"path {tor_bin}. Bundle layout may have changed."
        )
    tor_bin.chmod(0o755)
    print(f"Installed: {tor_bin}", file=sys.stderr)
    return tor_bin


def _tor_binary_path(bundle_dir):
    if os.name == "nt":
        return bundle_dir / "tor" / "tor.exe"
    return bundle_dir / "tor" / "tor"


# ---------------------------------------------------------------------------
# Start / stop / status
# ---------------------------------------------------------------------------

def _torrc_path():
    return INSTALL_DIR / "torrc"


def _pid_path():
    return INSTALL_DIR / "tor.pid"


def _log_path():
    return INSTALL_DIR / "tor.log"


def _data_path():
    return INSTALL_DIR / "data"


def _write_torrc(port):
    data_dir = _data_path()
    data_dir.mkdir(parents=True, exist_ok=True)
    # Tor requires DataDirectory to be mode 700
    os.chmod(data_dir, 0o700)
    content = textwrap.dedent(
        f"""\
        # Generated by the-internet bootstrap. Edit at your own risk.
        SOCKSPort 127.0.0.1:{port}
        SocksPolicy accept 127.0.0.1
        SocksPolicy reject *
        DataDirectory {data_dir}
        Log notice file {_log_path()}
        # No ControlPort -- stream isolation uses SOCKS auth, not control protocol.
        AvoidDiskWrites 1
        """
    )
    _torrc_path().write_text(content)


def start(port=DEFAULT_SOCKS_PORT):
    """Launch tor in the background. Returns PID."""
    bundle_dir = INSTALL_DIR / "bundle"
    tor_bin = _tor_binary_path(bundle_dir)
    if not tor_bin.exists():
        raise RuntimeError(
            f"tor binary not found at {tor_bin}. Run `bootstrap.py --install` first."
        )

    # Already running?
    pid_file = _pid_path()
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            if process_alive(old_pid) and socks_reachable(port):
                print(f"Tor already running (pid {old_pid}).")
                return old_pid
        except (ValueError, OSError):
            pass
        pid_file.unlink(missing_ok=True)

    _write_torrc(port)

    # Bundle ships its own libs; make sure they're findable on Linux.
    env = os.environ.copy()
    if sys.platform.startswith("linux"):
        lib_dir = str(tor_bin.parent)
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = (
            lib_dir + (os.pathsep + existing if existing else "")
        )

    print(f"Starting tor (bundle: {tor_bin})...", file=sys.stderr)
    proc = subprocess.Popen(
        [str(tor_bin), "-f", str(_torrc_path())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    pid_file.write_text(str(proc.pid))

    # Wait for bootstrap to progress to a usable circuit.
    print("Waiting for Tor to bootstrap (first run takes 30-60s)...", file=sys.stderr)
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"tor exited with code {proc.returncode} during bootstrap. "
                f"Check log: {_log_path()}"
            )
        if socks_reachable(port):
            # Check bootstrap % via log
            if _bootstrap_complete():
                print(f"Tor is up (pid {proc.pid}).", file=sys.stderr)
                return proc.pid
        time.sleep(1)

    raise RuntimeError(
        f"Tor failed to bootstrap within 120s. Check log: {_log_path()}"
    )


def _bootstrap_complete():
    """Check tor.log for 'Bootstrapped 100%' line."""
    log = _log_path()
    if not log.exists():
        return False
    try:
        tail = log.read_text(errors="replace")[-4096:]
    except OSError:
        return False
    return "Bootstrapped 100%" in tail


def stop():
    """Kill the managed tor process."""
    pid_file = _pid_path()
    if not pid_file.exists():
        print("No managed tor process.")
        return
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        print("Stale pid file removed.")
        return

    if not process_alive(pid):
        pid_file.unlink(missing_ok=True)
        print(f"Process {pid} was not running; cleaned up stale pid file.")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        print(f"Process {pid} already gone.")
        return

    for _ in range(20):
        if not process_alive(pid):
            break
        time.sleep(0.5)
    else:
        print(f"SIGTERM timed out, sending SIGKILL to {pid}...")
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    pid_file.unlink(missing_ok=True)
    print(f"Stopped tor (was pid {pid}).")


def status():
    """Print current state."""
    port = DEFAULT_SOCKS_PORT
    reachable = socks_reachable(port)
    bundle_dir = INSTALL_DIR / "bundle"
    bundle_installed = _tor_binary_path(bundle_dir).exists()

    pid_file = _pid_path()
    managed_pid = None
    if pid_file.exists():
        try:
            p = int(pid_file.read_text().strip())
            if process_alive(p):
                managed_pid = p
        except ValueError:
            pass

    print(f"Install dir:        {INSTALL_DIR}")
    print(f"Bundle installed:   {bundle_installed}")
    print(f"SOCKS port {port}:     {'reachable' if reachable else 'NOT reachable'}")
    print(
        f"Managed tor pid:    "
        f"{managed_pid if managed_pid else '(none running)'}"
    )
    if bundle_installed:
        print(f"Log file:           {_log_path()}")


def ensure_running():
    """Idempotent: ensure Tor is reachable on the SOCKS port. Install and
    start the bundled tor only if no existing tor (system service or
    otherwise) is already serving the port."""
    port = DEFAULT_SOCKS_PORT
    if socks_reachable(port):
        print(
            f"Tor already reachable on port {port} "
            f"(system service or other process)."
        )
        return 0

    bundle_dir = INSTALL_DIR / "bundle"
    if not _tor_binary_path(bundle_dir).exists():
        print("No Tor detected and no local bundle. Installing...", file=sys.stderr)
        install()

    start(port=port)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true",
                   help="Exit 0 if Tor is reachable on SOCKS port, else 1")
    g.add_argument("--install", action="store_true",
                   help="Download + verify + extract Expert Bundle")
    g.add_argument("--start", action="store_true",
                   help="Start managed tor process")
    g.add_argument("--stop", action="store_true",
                   help="Stop managed tor process")
    g.add_argument("--status", action="store_true",
                   help="Report current state")
    g.add_argument("--ensure-running", action="store_true",
                   help="The one-shot: check, install-if-needed, start")
    args = ap.parse_args()

    try:
        if args.check:
            ok = socks_reachable()
            print("reachable" if ok else "not reachable")
            sys.exit(0 if ok else 1)
        elif args.install:
            install()
        elif args.start:
            start()
        elif args.stop:
            stop()
        elif args.status:
            status()
        elif args.ensure_running:
            sys.exit(ensure_running())
    except Exception as e:
        print(f"bootstrap failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
