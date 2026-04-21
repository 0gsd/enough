#!/usr/bin/env bash
# bootstrap.sh — guided installer for `enough`.
#
# What this does, top to bottom:
#   1. Checks you're on macOS.
#   2. Makes sure Homebrew is present (explains what it is if not).
#   3. Installs llama.cpp, uv, and tor via brew (skips ones already installed).
#   4. Clones github.com/0gsd/enough to ~/enough (or `git pull`s if already there).
#   5. Runs `uv sync` inside ~/enough so the Python env is ready.
#   6. Sets up ~/enough/weights/ and either moves an existing GGUF into it
#      or downloads the recommended Gemma 4 26B MoE Q4_K_M (~16 GB).
#   7. Drops a tiny `enough` launcher at ~/.local/bin/enough so you can run
#      `enough` from any directory without remembering uv incantations.
#   8. Tells you what's next.
#
# You can re-run this script safely. Each step checks state before acting.
# If anything blows up, fix the thing it complained about and re-run.

set -euo pipefail

# ---------------------------------------------------------------------------
# Cosmetics
# ---------------------------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; CYAN=$'\033[36m'; GREEN=$'\033[32m'
YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'

step() { printf "\n${CYAN}${BOLD}[%s/%s] %s${RESET}\n" "$1" "$TOTAL" "$2"; }
note() { printf "  %s\n" "$1"; }
dim()  { printf "  ${DIM}%s${RESET}\n" "$1"; }
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
warn() { printf "  ${YELLOW}!${RESET} %s\n" "$1"; }
err()  { printf "  ${RED}✗${RESET} %s\n" "$1" >&2; }

ask_yn() {
  # ask_yn "prompt" default(Y|N) -> returns 0 for yes, 1 for no
  local prompt="$1" default="${2:-Y}" answer
  local hint
  if [[ "$default" == "Y" ]]; then hint="[Y/n]"; else hint="[y/N]"; fi
  read -r -p "  $prompt $hint " answer || true
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$ ]]
}

ask_text() {
  # ask_text "prompt" default -> echoes chosen value
  local prompt="$1" default="$2" answer
  read -r -p "  $prompt [$default] " answer || true
  echo "${answer:-$default}"
}

TOTAL=8

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
cat <<'BANNER'

  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  enough — paradigmless personal LLM harness                     │
  │  bootstrap installer                                            │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

BANNER

note "This script sets up everything you need to run enough on a Mac:"
note "  • Homebrew (package manager, if you don't have it)"
note "  • llama.cpp, uv, tor via Homebrew"
note "  • a clone of the enough repo at ~/enough"
note "  • a GGUF model file in ~/enough/weights/"
note "  • an \`enough\` command on your PATH"
note ""
note "It's safe to re-run. Each step checks state first."
note ""

if ! ask_yn "ready to start?" Y; then
  note "bailing. nothing changed."
  exit 0
fi

# ---------------------------------------------------------------------------
# 1. Platform check
# ---------------------------------------------------------------------------
step 1 "checking your platform"
note "enough v0.0.3 ships for macOS only. Linux support is on the roadmap."
if [[ "$(uname)" != "Darwin" ]]; then
  err "this script only runs on macOS. detected: $(uname)"
  exit 1
fi
ok "macOS detected ($(sw_vers -productVersion))"

# ---------------------------------------------------------------------------
# 2. Homebrew
# ---------------------------------------------------------------------------
step 2 "checking for Homebrew"
note "Homebrew is the standard package manager for macOS. We use it to install"
note "llama.cpp (the LLM server), uv (fast Python env tool), and tor (optional,"
note "used by the the-internet skill to anonymize web requests)."
if command -v brew >/dev/null 2>&1; then
  ok "Homebrew is installed ($(brew --version | head -1))"
else
  warn "Homebrew is NOT installed."
  note "visit https://brew.sh for the one-line install. when it's done, re-run this script."
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Brew deps
# ---------------------------------------------------------------------------
step 3 "installing Homebrew packages"
note "three utilities go on this pass:"
note "  • llama.cpp — the local LLM server that backs enough"
note "  • uv        — manages the Python environment that runs enough itself"
note "  • tor       — (optional) anonymization proxy for the the-internet skill"

install_brew_pkg() {
  local pkg="$1"
  if brew list --formula | grep -qx "$pkg"; then
    ok "$pkg already installed"
  else
    note "installing $pkg via Homebrew…"
    brew install "$pkg"
    ok "$pkg installed"
  fi
}

for pkg in llama.cpp uv tor; do
  install_brew_pkg "$pkg"
done

# ---------------------------------------------------------------------------
# 4. Clone / pull repo
# ---------------------------------------------------------------------------
step 4 "setting up ~/enough (the install directory)"
note "This is where the enough code, defaults, weights, and infoworld live."
note "It's a clone of github.com/0gsd/enough — when you want the latest code,"
note "you cd here and \`git pull\`."

ENOUGH_HOME="$HOME/enough"
REPO_URL="${ENOUGH_REPO_URL:-git@github.com:0gsd/enough.git}"

if [[ -d "$ENOUGH_HOME/.git" ]]; then
  ok "~/enough already exists as a git repo"
  if ask_yn "git pull latest?" Y; then
    (cd "$ENOUGH_HOME" && git pull --ff-only) && ok "pulled" || warn "git pull failed; continuing"
  fi
else
  if [[ -e "$ENOUGH_HOME" ]]; then
    err "~/enough exists but isn't a git repo. move it aside and re-run."
    exit 1
  fi
  note "cloning $REPO_URL into $ENOUGH_HOME…"
  git clone "$REPO_URL" "$ENOUGH_HOME"
  ok "cloned"
fi

# ---------------------------------------------------------------------------
# 5. Python env
# ---------------------------------------------------------------------------
step 5 "preparing the Python environment"
note "\`uv sync\` reads ~/enough/pyproject.toml, creates ~/enough/.venv, and"
note "installs every Python dependency enough needs. No global pip pollution."
( cd "$ENOUGH_HOME" && uv sync )
ok "~/enough/.venv is ready"

# ---------------------------------------------------------------------------
# 6. Model weights
# ---------------------------------------------------------------------------
step 6 "placing the LLM weights"
note "enough talks to a local llama-server that loads a GGUF model file."
note "Recommended: Gemma 4 26B A4B-it Q4_K_M (~16 GB on disk, ~4B active"
note "parameters at inference — fast on Apple Silicon)."
note ""

WEIGHTS_DIR="$ENOUGH_HOME/weights"
mkdir -p "$WEIGHTS_DIR"
RECOMMENDED="gemma-4-26B-A4B-it-Q4_K_M.gguf"
RECOMMENDED_URL="https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF/resolve/main/$RECOMMENDED"

if compgen -G "$WEIGHTS_DIR/*.gguf" > /dev/null; then
  ok "found at least one .gguf in ~/enough/weights/ — nothing to do here:"
  for f in "$WEIGHTS_DIR"/*.gguf; do
    dim "$(basename "$f")  ($(du -h "$f" | awk '{print $1}'))"
  done
else
  note "no .gguf found in ~/enough/weights/ yet."
  note "you can either (a) point to an existing GGUF you already have, or"
  note "(b) download the recommended one from Hugging Face."
  echo
  if ask_yn "do you already have a Gemma 4 26B MoE GGUF on this machine?" N; then
    EXISTING=$(ask_text "absolute path to the .gguf" "")
    EXISTING="${EXISTING/#\~/$HOME}"
    if [[ -f "$EXISTING" ]]; then
      if ask_yn "move (not copy) it into ~/enough/weights/? saves 16GB of duplication" Y; then
        mv "$EXISTING" "$WEIGHTS_DIR/"
        ok "moved $(basename "$EXISTING") → $WEIGHTS_DIR/"
      else
        ln -s "$EXISTING" "$WEIGHTS_DIR/$(basename "$EXISTING")"
        ok "symlinked $(basename "$EXISTING") → $WEIGHTS_DIR/"
      fi
    else
      err "no file at $EXISTING — skipping weights step. re-run the script when it's in place."
    fi
  else
    warn "downloading ~16 GB. this will take a while on normal home internet."
    if ask_yn "proceed with download of $RECOMMENDED?" Y; then
      curl -L --progress-bar -o "$WEIGHTS_DIR/$RECOMMENDED" "$RECOMMENDED_URL"
      ok "downloaded $RECOMMENDED"
    else
      warn "skipping. put a .gguf into ~/enough/weights/ before running enough."
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 7. PATH wrapper
# ---------------------------------------------------------------------------
step 7 "installing the \`enough\` command on your PATH"
note "This is a 3-line shell script at ~/.local/bin/enough that runs"
note "\`uv run --project ~/enough enough \"\$@\"\`. Once it's on PATH, you can"
note "\`cd\` into any project dir and type \`enough\` to launch the harness there."

LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
WRAPPER="$LOCAL_BIN/enough"
cat > "$WRAPPER" <<'WRAP'
#!/usr/bin/env bash
# Thin wrapper so `enough` works from any directory.
# Runs the enough CLI using the venv at ~/enough/.venv via uv.
exec uv run --project "$HOME/enough" enough "$@"
WRAP
chmod +x "$WRAPPER"
ok "wrote $WRAPPER"

# PATH check
if echo ":$PATH:" | grep -q ":$LOCAL_BIN:"; then
  ok "$LOCAL_BIN is on PATH"
else
  warn "$LOCAL_BIN is NOT on your PATH."
  note "add this to ~/.zshrc (or ~/.bashrc if you use bash):"
  note ""
  note "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  note ""
  note "then open a new terminal or \`source ~/.zshrc\` to pick it up."
fi

# ---------------------------------------------------------------------------
# 8. Done
# ---------------------------------------------------------------------------
step 8 "done"
ok "enough is installed at ~/enough"
ok "weights at ~/enough/weights/"
ok "\`enough\` CLI at ~/.local/bin/enough"
echo
note "next steps:"
note ""
note "  1. start the LLM server (one-time per boot):"
note "     MODEL=~/enough/weights/*.gguf ~/enough/llama_server.sh start"
note ""
note "  2. \`cd\` into any project directory you want to work in"
note "     (or make a new one: \`mkdir ~/my-first-enough-project && cd \$_\`)"
note ""
note "  3. run:"
note "     enough"
note ""
note "  4. open http://127.0.0.1:3456 and say hi to your fresh agent."
note ""
note "troubleshooting: re-run this script any time — it's idempotent."
