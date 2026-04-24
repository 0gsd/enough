#!/bin/bash
# enough-on.command
#
# Drop a copy of this file into any project folder you want to use with
# enough. Double-click it: macOS opens Terminal, cd's into that folder,
# and launches `enough` there.
#
# First-time-on-a-machine note: macOS may show a Gatekeeper warning the
# first time you double-click this. Right-click → Open once and macOS
# remembers the trust forever.

set -e

# Resolve the directory THIS script lives in (which is also the project
# you want enough to launch in, since you copied the file there).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Finder-spawned Terminals get a thinner PATH than your interactive shell.
# Make sure the place bootstrap.sh installs the wrapper is reachable.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v enough >/dev/null 2>&1; then
  echo "error: 'enough' is not on PATH."
  echo "       expected wrapper at: ~/.local/bin/enough"
  echo
  echo "       did you run bootstrap.sh? if so, the wrapper may have been"
  echo "       installed but ~/.local/bin isn't on your PATH yet — open"
  echo "       a fresh Terminal and try \`enough\` first."
  echo
  echo "press any key to close this window..."
  read -n 1 -s
  exit 1
fi

clear
cat <<EOF
─── enough ─────────────────────────────────────────────────────────
  project: $SCRIPT_DIR
  to stop: ⌃C in this window, or ⌘W to close it
─────────────────────────────────────────────────────────────────────

EOF

exec enough
