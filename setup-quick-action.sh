#!/usr/bin/env bash
# setup-quick-action.sh
#
# Installs a Finder Quick Action / Service so you can right-click any
# folder in Finder → Quick Actions → "Launch in enough" to open a fresh
# Terminal window pointed at that folder, with `enough` already running.
#
# Idempotent: re-run any time. Removes-and-replaces the existing Quick
# Action if it's already installed.
#
# To uninstall:
#     rm -rf "$HOME/Library/Services/Launch in enough.workflow"
#     /System/Library/CoreServices/pbs -flush

set -euo pipefail

CYAN=$'\033[36m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

note() { printf "  %s\n" "$1"; }
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
warn() { printf "  ${YELLOW}!${RESET} %s\n" "$1"; }

if [[ "$(uname)" != "Darwin" ]]; then
  echo "this installer is macOS-only." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/defaults/macos/Launch in enough.workflow"
DEST="$HOME/Library/Services/Launch in enough.workflow"

if [[ ! -d "$SOURCE" ]]; then
  echo "error: workflow bundle not found at $SOURCE" >&2
  echo "       this script must be run from the enough repo root." >&2
  exit 1
fi

printf "\n${CYAN}installing Finder Quick Action: 'Launch in enough'${RESET}\n\n"
note "What this does: copies the workflow bundle into ~/Library/Services/"
note "and refreshes Finder's services cache so the new menu item shows up."
note "After this you can right-click any folder in Finder and pick"
note "'Quick Actions → Launch in enough' to open a Terminal window with"
note "\`enough\` running in that folder."
echo

if [[ -d "$DEST" ]]; then
  warn "an existing 'Launch in enough' Quick Action will be replaced."
  rm -rf "$DEST"
fi

mkdir -p "$HOME/Library/Services"
cp -R "$SOURCE" "$DEST"
ok "copied to $DEST"

# Refresh the services cache so Finder picks up the new item.
if /System/Library/CoreServices/pbs -flush 2>/dev/null; then
  ok "services cache refreshed"
else
  warn "could not flush services cache (may be a no-op on your macOS version)."
fi

echo
note "to use:"
note "  1. open Finder"
note "  2. right-click any folder"
note "  3. Quick Actions → Launch in enough"
note "  (you may need to enable it the first time: System Settings → Keyboard"
note "  → Keyboard Shortcuts → Services → Files and Folders → 'Launch in enough')"
echo
note "to uninstall later, run:"
note "  rm -rf \"\$HOME/Library/Services/Launch in enough.workflow\""
note "  /System/Library/CoreServices/pbs -flush"
