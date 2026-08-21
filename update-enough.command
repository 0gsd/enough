#!/usr/bin/env bash
# update-enough.command
#
# Double-click in Finder to pull the latest 'enough' source code from
# GitHub and resync the Python environment. Internet required. If the
# network is unreachable the script tells you and exits without
# breaking anything — your installed copy still works fine.
#
# This is the installed-side equivalent of the EAT (USB drive) launcher
# of the same name. Same UX, same idempotent behavior, different anchor:
# instead of updating the ./enough/ folder on a flash drive, it updates
# the cloned repo at ~/enough/ (or wherever this script lives — the
# script anchors to its own directory).

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "  %s\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
err()  { printf "  \033[31m✗\033[0m %s\n" "$*" >&2; }
pause() {
  echo
  echo "(press any key to close this window)"
  read -n 1 -s
}

# Finder-spawned Terminals get a thinner PATH than an interactive
# shell. Mirror install-enough.command so git/uv/brew binaries are
# reachable without the user having to source their shell rc.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

clear
bold "enough — update source code"
echo
info "this script runs:"
info "    git pull --ff-only    in $HERE"
info "    uv sync               to pick up any new Python deps"
info "                          (keeping any optional extras you installed)"
echo

# ---------------------------------------------------------------------------
# Sanity: is this a git repo?
# ---------------------------------------------------------------------------
if [[ ! -d "$HERE/.git" ]]; then
  err "this folder is not a git repo:"
  info "    $HERE"
  info "update-enough only works inside a clone of the enough repo."
  info "if you installed via the EAT USB drive, run that drive's"
  info "update-enough.command instead."
  pause
  exit 1
fi

# ---------------------------------------------------------------------------
# Tool check
# ---------------------------------------------------------------------------
for t in git curl uv; do
  if ! command -v "$t" >/dev/null 2>&1; then
    err "$t is not on PATH"
    info "this should have been installed by bootstrap.sh. re-run bootstrap"
    info "or install '$t' manually, then come back."
    pause
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Network check (cheap — short timeout, just a connectivity ping)
# ---------------------------------------------------------------------------
info "checking GitHub reachability..."
if ! curl -fsS --max-time 8 -o /dev/null https://github.com 2>/dev/null; then
  warn "GitHub is unreachable from this network."
  info "your installed copy of enough still works fine."
  info "try again later, or work offline for now."
  pause
  exit 0
fi
ok "GitHub reachable"

# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------
echo
info "running 'git pull --ff-only'..."
PULL_OUTPUT="$(git pull --ff-only 2>&1)"
PULL_STATUS=$?
echo "$PULL_OUTPUT"
echo
if [[ $PULL_STATUS -ne 0 ]]; then
  err "git pull failed."
  info "this can happen if local changes diverged from upstream, or if the"
  info "remote was force-pushed. your installation is unchanged."
  info "to reset to upstream main (DESTRUCTIVE — discards local edits):"
  info "    cd \"$HERE\" && git fetch origin && git reset --hard origin/main"
  pause
  exit 1
fi
ok "git pull complete"

# Detect "Already up to date" so we can skip uv sync in the common no-op case.
if [[ "$PULL_OUTPUT" == *"Already up to date"* ]]; then
  echo
  ok "already at the latest version. nothing to sync."
  pause
  exit 0
fi

# ---------------------------------------------------------------------------
# Optional extras
#
# `uv sync` is EXACT by default: left to itself it would UNINSTALL any
# optional dependency group the user added from the app (the PDF reader,
# say), because the group isn't in the default set. ~/enough/config/extras.json
# records what's installed, and every sync path — this script, the desktop
# shell, and the in-app installer — re-asks for each one. python3 does the
# JSON reading; names are validated so nothing from that file can become a
# stray flag.
# ---------------------------------------------------------------------------
EXTRAS_STATE="${ENOUGH_EXTRAS_STATE:-$HOME/enough/config/extras.json}"
EXTRA_FLAGS=""
if [[ -f "$EXTRAS_STATE" ]] && command -v python3 >/dev/null 2>&1; then
  EXTRA_FLAGS="$(python3 - "$EXTRAS_STATE" <<'PYEXTRAS'
import json, re, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    raise SystemExit(0)
if isinstance(data, dict):
    for name in sorted(data):
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", str(name)):
            print("--extra")
            print(name)
PYEXTRAS
)"
fi
if [[ -n "$EXTRA_FLAGS" ]]; then
  info "keeping installed extras:$(printf ' %s' $EXTRA_FLAGS | sed 's/ --extra//g')"
fi

# ---------------------------------------------------------------------------
# uv sync
# ---------------------------------------------------------------------------
echo
info "running 'uv sync' to pick up any new Python deps..."
if uv sync $EXTRA_FLAGS; then
  echo
  ok "Python environment synced"
else
  err "uv sync failed."
  info "the git pull succeeded, but Python deps may be out of date."
  info "try running 'uv sync' manually from this directory:"
  info "    cd \"$HERE\" && uv sync $EXTRA_FLAGS"
  pause
  exit 1
fi

echo
ok "enough is up to date"
info "tip: if enough is currently running, restart it so the new code loads."
pause
