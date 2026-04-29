#!/bin/bash
# install-enough.command
#
# Double-click installer launcher. Lives at the root of a cloned enough
# repo. Double-clicking from Finder opens Terminal, runs bootstrap.sh,
# and keeps the window open at the end so the install output is
# readable.
#
# First-time-on-a-machine note: macOS Gatekeeper may show a warning the
# first time you double-click. Right-click → Open once and macOS
# remembers the trust forever.

# Find the repo root. Look in the script's own directory first (the
# expected case — install-enough.command sits at the repo root next to
# bootstrap.sh), then fall back to one level up so the launcher still
# works if it gets moved into a subdirectory.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/bootstrap.sh" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../bootstrap.sh" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  cat <<HINT

─── install-enough.command — wrong location? ────────────────────────

  this launcher needs to live inside a cloned enough repo, next to
  bootstrap.sh. i don't see bootstrap.sh at:

    $SCRIPT_DIR/bootstrap.sh
    $SCRIPT_DIR/../bootstrap.sh

  fix: clone the repo, then double-click the launcher inside the
  clone. eg:

    git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
    open ~/Downloads/enough-seed

──────────────────────────────────────────────────────────────────────

press any key to close this window...
HINT
  read -n 1 -s
  exit 1
fi
cd "$REPO_ROOT" || {
  echo "error: could not access $REPO_ROOT"
  echo "press any key to close this window..."
  read -n 1 -s
  exit 1
}

# Finder-spawned Terminals get a thinner PATH than an interactive
# shell. Make sure Homebrew (Apple Silicon at /opt/homebrew/bin, Intel
# at /usr/local/bin) and any user-local bins are reachable so
# bootstrap.sh's brew/uv/git checks don't falsely report "not
# installed" when the binaries are present but off the path.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

clear
cat <<EOF
─── enough — installer launcher ──────────────────────────────────────

  about to run bootstrap.sh from:
    $REPO_ROOT

  the installer is interactive — it asks before each step and
  explains what it's about to do. Ctrl-C is safe; bootstrap.sh is
  idempotent, so you can re-run it any time and it picks up where
  you left off.

──────────────────────────────────────────────────────────────────────

EOF

bash bootstrap.sh
status=$?

echo
if [[ $status -eq 0 ]]; then
  echo "✓ installer finished. you can close this window."
else
  echo "✗ bootstrap.sh exited with status $status."
  echo "  scroll up to see what happened, address the issue, then re-run."
fi
echo
echo "press any key to close this window..."
read -n 1 -s
