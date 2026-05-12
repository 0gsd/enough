#!/usr/bin/env bash
# bootstrap.sh — guided installer for `enough`.
#
# What this does, top to bottom:
#   1. Checks you're on macOS.
#   2. Makes sure Homebrew is present (explains what it is if not).
#   3. Installs llama.cpp, uv, and tor via brew (skips ones already installed).
#   4. Clones github.com/0gsd/enough to ~/enough (or `git pull`s if already there).
#   5. Runs `uv sync` inside ~/enough so the Python env is ready
#      (this also installs the offline-translation dependencies:
#      ctranslate2, sentencepiece, huggingface_hub).
#   6. Sets up ~/enough/weights/ and either moves an existing GGUF into it
#      or downloads the recommended Gemma 4 26B MoE Q4_K_M (~16 GB).
#   7. Downloads the whisper model for voice input (~142 MB).
#   8. Optionally downloads the MADLAD-400-3B-MT translation model
#      (~3 GB) into ~/.local/share/translator/. Powers the `translator`
#      skill — offline translation across ~419 languages.
#   9. Drops a tiny `enough` launcher at ~/.local/bin/enough so you can run
#      `enough` from any directory without remembering uv incantations.
#  10. Tells you what's next.
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

TOTAL=10

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
note "  • llama.cpp, uv, tor, whisper-cpp via Homebrew"
note "  • a clone of the enough repo at ~/enough"
note "  • a GGUF model file in ~/enough/weights/"
note "  • a whisper model for voice input in ~/enough/weights/whisper/"
note "  • (optional) MADLAD-400 translation model in ~/.local/share/translator/"
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
note "llama.cpp (the LLM server), uv (fast Python env tool), tor (used by the"
note "broker to anonymize off-allowlist web fetches), and pandoc (HTML→markdown)."
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
note "five utilities go on this pass:"
note "  • llama.cpp   — the local LLM server that backs enough"
note "  • uv          — manages the Python environment that runs enough itself"
note "  • tor         — anonymization proxy used by the broker for off-allowlist web fetches"
note "  • whisper-cpp — local speech-to-text for the mic button in chat"
note "  • pandoc      — universal document converter; used by the broker to convert fetched HTML to markdown"

install_brew_pkg() {
  local pkg="$1"
  if brew list --formula | grep -qx "$pkg"; then
    ok "$pkg already installed"
  else
    note "installing $pkg via Homebrew..."
    brew install "$pkg"
    ok "$pkg installed"
  fi
}

for pkg in llama.cpp uv tor whisper-cpp pandoc; do
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
  note "cloning $REPO_URL into $ENOUGH_HOME..."
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
note "enough ships with four supported local models. You pick how many to"
note "install now; you can add the rest later by re-running this script."
note "All are Q4_K_M (~4-bit) quantizations — good quality, fast on Apple"
note "Silicon, and moderate disk footprint."
note ""
note "  [1] G40-04   Gemma 4 4B (E4B)        ~5.4 GB   fast; fits 16 GB Macs"
note "  [2] Q35-09   Qwen3.5-9B              ~5.6 GB   balanced mid-size"
note "  [3] G40-26   Gemma 4 26B MoE         ~15.6 GB  Gemma flagship (MoE)"
note "  [4] Q36-27   Qwen3.6-27B             ~16.5 GB  Qwen dense, coding"
note ""
note "Default after install is always G40-04 regardless of which tier you"
note "pick — lightest surface area, most forgiving hardware-wise."
note ""

WEIGHTS_DIR="$ENOUGH_HOME/weights"
mkdir -p "$WEIGHTS_DIR"

# Registry lookup by cute name. Using case statements instead of
# associative arrays so we stay compatible with macOS stock bash (3.2).
# Keep in sync with defaults/models.json.
MODEL_KEYS="g40-04 q35-09 g40-26 q36-27"

model_filename() {
  case "$1" in
    g40-04) echo "gemma-4-E4B-it-Q4_K_M.gguf" ;;
    q35-09) echo "Qwen3.5-9B-Q4_K_M.gguf" ;;
    g40-26) echo "gemma-4-26B-A4B-it-Q4_K_M.gguf" ;;
    q36-27) echo "Qwen_Qwen3.6-27B-Q4_K_M.gguf" ;;
  esac
}
model_url() {
  case "$1" in
    g40-04) echo "https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf" ;;
    q35-09) echo "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf" ;;
    g40-26) echo "https://huggingface.co/ggml-org/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-Q4_K_M.gguf" ;;
    q36-27) echo "https://huggingface.co/bartowski/Qwen_Qwen3.6-27B-GGUF/resolve/main/Qwen_Qwen3.6-27B-Q4_K_M.gguf" ;;
  esac
}
model_gb() {
  case "$1" in
    g40-04) echo "5.4" ;;
    q35-09) echo "5.6" ;;
    g40-26) echo "15.6" ;;
    q36-27) echo "16.5" ;;
  esac
}

# Cumulative install tiers.
echo
note "cumulative install tiers:"
note "  1  →  G40-04 only                       (~5.4 GB)"
note "  2  →  G40-04 + Q35-09                   (~11 GB)"
note "  3  →  G40-04 + Q35-09 + G40-26          (~27 GB)"
note "  4  →  all four models                   (~43 GB)"
echo
TIER=$(ask_text "install how many? [1-4]" "1")
case "$TIER" in
  1) SELECTED="g40-04" ;;
  2) SELECTED="g40-04 q35-09" ;;
  3) SELECTED="g40-04 q35-09 g40-26" ;;
  4) SELECTED="g40-04 q35-09 g40-26 q36-27" ;;
  *)
    warn "unrecognized tier $TIER — defaulting to 1 (G40-04 only)"
    SELECTED="g40-04" ;;
esac

for cute in $SELECTED; do
  filename=$(model_filename "$cute")
  dest="$WEIGHTS_DIR/$filename"
  if [[ -f "$dest" ]]; then
    ok "$cute already at $(basename "$dest")  ($(du -h "$dest" | awk '{print $1}'))"
  else
    note "downloading $cute (~$(model_gb "$cute") GB) → $(basename "$dest")"
    curl -L --progress-bar -o "$dest" "$(model_url "$cute")"
    ok "$cute installed"
  fi
done

# Seed the live current selection if not yet set.
mkdir -p "$ENOUGH_HOME/config"
if [[ ! -f "$ENOUGH_HOME/config/models.json" ]]; then
  echo '{"current": "g40-04"}' > "$ENOUGH_HOME/config/models.json"
  ok "live model state seeded to default (G40-04)"
fi

echo
note "all your installed models:"
for cute in $MODEL_KEYS; do
  fn=$(model_filename "$cute")
  if [[ -f "$WEIGHTS_DIR/$fn" ]]; then
    dim "  ✓ $cute   $fn   ($(du -h "$WEIGHTS_DIR/$fn" | awk '{print $1}'))"
  else
    dim "  · $cute   (not installed; re-run this script to add)"
  fi
done

# ---------------------------------------------------------------------------
# 7. Whisper model for voice input
# ---------------------------------------------------------------------------
step 7 "placing the voice-input model"
note "The mic button in the chat input sends audio to a local whisper.cpp"
note "binary (installed via Homebrew in step 3) for transcription. It needs a"
note "model file. Recommended: ggml-base.en.bin (~142 MB, English-only,"
note "well-balanced accuracy vs speed). Everything stays on your machine —"
note "no audio leaves this computer."
note ""

WHISPER_DIR="$ENOUGH_HOME/weights/whisper"
WHISPER_MODEL_NAME="ggml-base.en.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL_NAME"
mkdir -p "$WHISPER_DIR"

if [[ -f "$WHISPER_DIR/$WHISPER_MODEL_NAME" ]]; then
  ok "whisper model already present:"
  dim "$WHISPER_DIR/$WHISPER_MODEL_NAME  ($(du -h "$WHISPER_DIR/$WHISPER_MODEL_NAME" | awk '{print $1}'))"
else
  if ask_yn "download $WHISPER_MODEL_NAME (~142 MB)?" Y; then
    curl -L --progress-bar -o "$WHISPER_DIR/$WHISPER_MODEL_NAME" "$WHISPER_MODEL_URL"
    ok "whisper model downloaded"
  else
    warn "skipping. voice input won't work until a whisper .bin is in $WHISPER_DIR/"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Offline translation model (MADLAD-400-3B-MT)
# ---------------------------------------------------------------------------
step 8 "placing the offline-translation model"
note "enough ships with a \`translator\` skill that does offline translation"
note "across ~419 languages — no API call, no account, no network hop after"
note "the model is downloaded. It's powered by Google's MADLAD-400-3B-MT"
note "(Apache 2.0), served through CTranslate2 + SentencePiece for fast"
note "CPU/Metal inference."
note ""
note "The Python deps (ctranslate2, sentencepiece, huggingface_hub) were"
note "already installed in step 5 via \`uv sync\`. What's left is the model"
note "weights themselves: ~3 GB, downloaded once, never phones home again."
note ""
note "You can skip this and the model will be downloaded on first use of"
note "the translator skill instead. It'll go to ~/.local/share/translator/"
note "either way."
note ""

TRANSLATOR_HOME_DIR="${TRANSLATOR_HOME:-$HOME/.local/share/translator}"
TRANSLATOR_MODEL_DIR="$TRANSLATOR_HOME_DIR/madlad400-3b-ct2"

if [[ -f "$TRANSLATOR_MODEL_DIR/model.bin" && -f "$TRANSLATOR_MODEL_DIR/sentencepiece.model" ]]; then
  ok "MADLAD-400-3B-MT already at $TRANSLATOR_MODEL_DIR"
else
  if ask_yn "download MADLAD-400-3B-MT now (~3 GB)?" Y; then
    note "downloading via huggingface_hub.snapshot_download..."
    ( cd "$ENOUGH_HOME" && uv run python defaults/skills/translator/scripts/bootstrap.py --install )
    ok "translator model installed"
  else
    warn "skipping. translator skill will download the model on first use."
    note "to download manually later, run:"
    note "  cd ~/enough && uv run python defaults/skills/translator/scripts/bootstrap.py --install"
  fi
fi

# ---------------------------------------------------------------------------
# 9. PATH wrapper
# ---------------------------------------------------------------------------
step 9 "installing the \`enough\` command on your PATH"
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
# 10. Done
# ---------------------------------------------------------------------------
step 10 "done"
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
