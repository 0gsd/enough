#!/usr/bin/env bash
# update-weights.command
#
# Double-click in Finder to refresh any AI assets ALREADY installed on
# this machine — the GGUFs under ~/enough/weights/, the whisper model
# under ~/enough/weights/whisper/, and the MADLAD translator under
# ~/.local/share/translator/. Internet required.
#
# This is the installed-side equivalent of the EAT (USB drive) launcher
# of the same name. The EAT version verifies/repairs from a bundled
# PAR2 redundancy set before touching the network; installed users
# don't have PAR2 (it's a USB-drive thing), so the installed version
# goes straight to "re-fetch from Hugging Face" with curl -C - resume
# support, which means a partial-file refresh is cheap.
#
# Idempotent. Only refreshes assets that are ALREADY installed — never
# expands your footprint. To add a new tier of weights, re-run
# bootstrap.sh instead.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "  %s\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
err()  { printf "  \033[31m✗\033[0m %s\n" "$*" >&2; }
ask_yn() {
  local prompt="$1" default="${2:-Y}" answer hint
  if [[ "$default" == "Y" ]]; then hint="[Y/n]"; else hint="[y/N]"; fi
  read -r -p "  $prompt $hint " answer || true
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$ ]]
}
pause() {
  echo
  echo "(press any key to close this window)"
  read -n 1 -s
}

# Mirror install-enough.command PATH widening so Homebrew binaries are
# reachable when Finder-spawned.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# Where things live on an installed machine.
WEIGHTS_DIR="$HERE/weights"
WHISPER_DIR="$WEIGHTS_DIR/whisper"
TRANSLATOR_HOME_DIR="${TRANSLATOR_HOME:-$HOME/.local/share/translator}"
TRANSLATOR_DIR_3B="$TRANSLATOR_HOME_DIR/madlad400-3b-ct2"

clear
bold "enough — refresh weights"
echo
info "this script re-downloads AI assets that are ALREADY installed."
info "it never adds new ones — to install a new model tier, re-run"
info "bootstrap.sh instead. curl uses -C - to resume partial files, so"
info "refreshing a single damaged file is cheap."
echo

# ---------------------------------------------------------------------------
# Tooling
# ---------------------------------------------------------------------------
if ! command -v curl >/dev/null 2>&1; then
  err "curl is not on PATH (shouldn't happen on macOS)"
  pause
  exit 1
fi

# ---------------------------------------------------------------------------
# Inventory: what's actually installed?
# ---------------------------------------------------------------------------
# Map of cute-name → filename, URL. Mirrors bootstrap.sh:209-225 — keep
# in sync if the canonical model registry changes there. (Both files
# being out of date is a deeper problem than either being out of date
# alone; the canonical registry move-to-config has been deferred.)
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
ALL_MODEL_KEYS="g40-04 q35-09 g40-26 q36-27"

WHISPER_NAME="ggml-base.en.bin"
WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_NAME"

# Detect what's installed.
INSTALLED_MODELS=()
for k in $ALL_MODEL_KEYS; do
  fn=$(model_filename "$k")
  [[ -f "$WEIGHTS_DIR/$fn" ]] && INSTALLED_MODELS+=("$k")
done
WHISPER_INSTALLED=0
[[ -f "$WHISPER_DIR/$WHISPER_NAME" ]] && WHISPER_INSTALLED=1
TRANSLATOR_INSTALLED=0
[[ -f "$TRANSLATOR_DIR_3B/model.bin" && -f "$TRANSLATOR_DIR_3B/sentencepiece.model" ]] && TRANSLATOR_INSTALLED=1

# Tally up what we found.
COUNT=$(( ${#INSTALLED_MODELS[@]} + WHISPER_INSTALLED + TRANSLATOR_INSTALLED ))
if (( COUNT == 0 )); then
  warn "no AI assets found under $WEIGHTS_DIR or $TRANSLATOR_HOME_DIR"
  info "looks like this machine hasn't run bootstrap.sh yet, or you"
  info "installed into a non-default location. nothing to refresh."
  pause
  exit 0
fi

bold "found $COUNT installed asset(s):"
for k in "${INSTALLED_MODELS[@]}"; do
  fn=$(model_filename "$k")
  sz=$(du -h "$WEIGHTS_DIR/$fn" 2>/dev/null | awk '{print $1}')
  info "    $k    $fn    ($sz)"
done
if (( WHISPER_INSTALLED )); then
  sz=$(du -h "$WHISPER_DIR/$WHISPER_NAME" 2>/dev/null | awk '{print $1}')
  info "    whisper    $WHISPER_NAME    ($sz)"
fi
if (( TRANSLATOR_INSTALLED )); then
  sz=$(du -sh "$TRANSLATOR_DIR_3B" 2>/dev/null | awk '{print $1}')
  info "    translator (MADLAD-400-3B)    ($sz)"
fi
echo
if ! ask_yn "refresh all installed assets from Hugging Face?" Y; then
  info "no changes made. exiting."
  pause
  exit 0
fi

# ---------------------------------------------------------------------------
# Network check
# ---------------------------------------------------------------------------
echo
info "checking Hugging Face reachability..."
if ! curl -fsS --max-time 8 -o /dev/null https://huggingface.co 2>/dev/null; then
  err "huggingface.co is unreachable."
  info "try again on a connected network."
  pause
  exit 1
fi
ok "huggingface.co reachable"

# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------
mkdir -p "$WEIGHTS_DIR" "$WHISPER_DIR"

redownload() {
  # redownload <url> <destpath>
  local url="$1" dest="$2"
  echo
  info "refreshing $(basename "$dest")"
  # -L: follow redirects, -C -: resume partial files, --fail: HTTP errors abort
  if curl -L -C - --fail --progress-bar -o "$dest" "$url"; then
    ok "got $(basename "$dest")"
  else
    warn "download failed for $(basename "$dest") — keeping existing copy"
  fi
}

bold "[1/3] refreshing GGUF weights"
for k in "${INSTALLED_MODELS[@]}"; do
  redownload "$(model_url "$k")" "$WEIGHTS_DIR/$(model_filename "$k")"
done

if (( WHISPER_INSTALLED )); then
  echo
  bold "[2/3] refreshing whisper model"
  redownload "$WHISPER_URL" "$WHISPER_DIR/$WHISPER_NAME"
else
  echo
  info "[2/3] whisper not installed — skipping"
fi

if (( TRANSLATOR_INSTALLED )); then
  echo
  bold "[3/3] refreshing MADLAD translator (via huggingface_hub)"
  if ! command -v uv >/dev/null 2>&1; then
    warn "uv is not on PATH — skipping translator refresh."
    info "install uv (brew install uv) and re-run if you want this."
  else
    uv run --no-project --quiet --with 'huggingface_hub>=0.24' python - <<PYEOF
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="santhosh/madlad400-3b-ct2",
    local_dir="$TRANSLATOR_DIR_3B",
    local_dir_use_symlinks=False,
)
PYEOF
    if [[ -f "$TRANSLATOR_DIR_3B/model.bin" ]]; then
      ok "translator refreshed"
    else
      warn "translator snapshot didn't produce model.bin — try a better connection"
    fi
  fi
else
  echo
  info "[3/3] translator not installed — skipping"
fi

echo
ok "refresh complete"
info "if enough is currently running, restart the llama-server so it"
info "re-mmaps the refreshed weight file:"
info "    ~/enough/llama_server.sh restart"
pause
