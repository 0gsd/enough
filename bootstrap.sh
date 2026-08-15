#!/usr/bin/env bash
# bootstrap.sh — guided installer for `enough`.
#
# What this does, top to bottom:
#   1. Checks you're on macOS.
#   2. Makes sure Homebrew is present (explains what it is if not).
#   3. Installs llama.cpp, uv, tor, whisper-cpp, pandoc, and harper via brew
#      (skips ones already installed).
#   4. Clones github.com/0gsd/enough to ~/enough (or `git pull`s if already there).
#   5. Runs `uv sync` inside ~/enough so the Python env is ready
#      (this also installs the offline-translation dependencies —
#      ctranslate2, sentencepiece, huggingface_hub — and the keyring
#      binding used for the optional OpenRouter cloud-model slot).
#   6. Sets up ~/enough/weights/ and walks the full 7-model registry one
#      model at a time — live machine-feasibility verdict, size (main +
#      any MTP draft), y/n per model, sane defaults pre-picked.
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
note "  • llama.cpp, uv, tor, whisper-cpp, pandoc, harper via Homebrew"
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
note "enough v0.2.0 ships for macOS only. Linux support is on the roadmap."
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
note "six utilities go on this pass:"
note "  • llama.cpp   — the local LLM server that backs enough"
note "  • uv          — manages the Python environment that runs enough itself"
note "  • tor         — anonymization proxy used by the broker for off-allowlist web fetches"
note "  • whisper-cpp — local speech-to-text for the mic button in chat"
note "  • pandoc      — universal document converter; used by the broker to convert fetched HTML to markdown"
note "  • harper      — local grammar/spell checker (Apache 2.0, by Automattic) used by the analyzer skill's proofread mode"

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

for pkg in llama.cpp uv tor whisper-cpp pandoc harper; do
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
REPO_URL="${ENOUGH_REPO_URL:-https://github.com/0gsd/enough.git}"

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
note "this also includes:"
note "  • ctranslate2, sentencepiece, huggingface_hub — for the offline"
note "    \`translator\` skill (used by step 8 below)"
note "  • keyring — the cross-platform binding to the OS credential store"
note "    (macOS Keychain on this machine). Used by the optional OpenRouter"
note "    cloud-model slot to store an api key without ever writing it to"
note "    disk in plaintext. The slot itself is off by default; see step 10."
( cd "$ENOUGH_HOME" && uv sync )
ok "~/enough/.venv is ready"

# ---------------------------------------------------------------------------
# 6. Model weights
# ---------------------------------------------------------------------------
step 6 "placing the LLM weights"
note "enough ships with 7 local models across two families — Gemma and Qwen —"
note "from a 4B model that's happy on a 16 GB Mac up to a 54 GB flagship that"
note "wants a Mac Studio. Instead of a fixed list, this step reads the real"
note "model registry live (the same registry the running app uses) and checks"
note "this machine's RAM and free disk against every entry."
note ""

WEIGHTS_DIR="$ENOUGH_HOME/weights"
mkdir -p "$WEIGHTS_DIR"

# Captured now, before anything below touches the registry: enough.models'
# resolve() (called per-model further down, purely to read a label/URL for
# display) has the side effect of auto-seeding config/models.json to the
# registry default the first time it runs on a fresh install. Checking
# file-existence AFTER that loop would always see it as "already there" and
# silently skip the smallest-installed-model fallback below — so the seed
# decision has to be based on whether it existed at THIS point, not later.
HAD_LIVE_STATE=""
[[ -f "$ENOUGH_HOME/config/models.json" ]] && HAD_LIVE_STATE="1"

note "here's what enough knows about this machine, model by model:"
note "  ✓ good to go     ~ tight but workable     ✗ out of reach here"
echo
uv run --project "$ENOUGH_HOME" python -m enough.models install-menu | while IFS= read -r line; do
  dim "$line"
done
echo
note "you'll get a y/n for each one you don't already have. say no to any you"
note "don't want yet — re-run this script later to add them, already-installed"
note "ones are skipped automatically. a handful of small, comfortable-fit"
note "models default to yes; everything else defaults to no, so a green light"
note "never turns into an accidental double-digit-GB download."
note ""

# model_row <cute> — prints shell-sourceable ROW_*/MODEL_*/DRAFT_* vars for
# one registry entry, read live off enough.models instead of a shadow copy
# of the registry in this script (that shadow copy — model_filename/
# model_url/model_gb case tables — is exactly what this replaces).
# ROW_* mirrors what `install-menu --json` reports (label, size, verdict,
# reasons, default_yes, the llama.cpp release gate). MODEL_*/DRAFT_* come
# from resolve(), which — unlike the `params` CLI subcommand llama_server.sh
# uses — works for a model that isn't installed yet, which is exactly the
# case here.
model_row() {
  uv run --project "$ENOUGH_HOME" python - "$1" <<'PYEOF'
import shlex
import sys
from enough import models as m

cute = sys.argv[1]
rows = {r["cute"]: r for r in m.install_menu_rows()}
row = rows[cute]
info = m.resolve(cute)


def q(v):
    return shlex.quote("" if v is None else str(v))


fields = {
    "ROW_LABEL": row["label"],
    "ROW_MAIN_GB": row["disk_gb_approx"],
    "ROW_SIZE_GB": row["size_gb"],
    "ROW_DRAFT_GB": row["draft_disk_gb_approx"] or "",
    "ROW_INSTALLED": "1" if row["installed"] else "",
    "ROW_VERDICT": row["verdict"],
    "ROW_REASONS": "; ".join(row["reasons"]),
    "ROW_DEFAULT_YES": "1" if row["default_yes"] else "",
    "ROW_MIN_RELEASE": row["llama_cpp_min_release"],
    "MODEL_FILENAME": info["filename"],
    "MODEL_URL": info["url"],
    "DRAFT_FILENAME": info["draft_filename"] or "",
    "DRAFT_URL": info["draft_url"] or "",
}
for key, value in fields.items():
    print(f"{key}={q(value)}")
PYEOF
}

# download_model_file <url> <dest> — fetches into a .part file under
# weights/downloads/ via `curl -C -` (resumable), then moves it into place
# on success. This is the same partial-file convention the in-app
# ModelDownloadManager uses (see docs/seven-models-plan.md's Wave 2a
# notes) — sharing it means a download interrupted here resumes correctly
# whether it's re-run from this script or finished later from the model
# picker, and, more importantly, means a partial download can never look
# "installed": resolve()'s installed check only ever looks at the final
# filename in weights/, never at weights/downloads/.
download_model_file() {
  local url="$1" dest="$2"
  local part_dir="$WEIGHTS_DIR/downloads"
  local part="$part_dir/$(basename "$dest").part"
  mkdir -p "$part_dir"
  curl -L -C - --progress-bar -o "$part" "$url"
  mv "$part" "$dest"
}

MODEL_KEYS=$(uv run --project "$ENOUGH_HOME" python -c "
from enough import models as m
print(' '.join(r['cute'] for r in m.install_menu_rows()))
")

for cute in $MODEL_KEYS; do
  eval "$(model_row "$cute")"

  if [[ -n "$ROW_INSTALLED" ]]; then
    ok "$cute already at $MODEL_FILENAME  ($(du -h "$WEIGHTS_DIR/$MODEL_FILENAME" | awk '{print $1}'))"
    if [[ -n "$DRAFT_FILENAME" ]]; then
      draft_dest="$WEIGHTS_DIR/$DRAFT_FILENAME"
      if [[ -f "$draft_dest" ]]; then
        ok "$cute's MTP draft already at $DRAFT_FILENAME  ($(du -h "$draft_dest" | awk '{print $1}'))"
      elif ask_yn "also grab $cute's MTP draft (~${ROW_DRAFT_GB} GB, faster generation)?" Y; then
        note "downloading $cute's MTP draft (~${ROW_DRAFT_GB} GB) → $(basename "$draft_dest")"
        download_model_file "$DRAFT_URL" "$draft_dest"
        ok "$cute draft installed"
      fi
    fi
    continue
  fi

  glyph="~"
  [[ "$ROW_VERDICT" == "good" ]] && glyph="✓"
  [[ "$ROW_VERDICT" == "no" ]] && glyph="✗"
  size_note="${ROW_SIZE_GB} GB"
  [[ -n "$ROW_DRAFT_GB" ]] && size_note="$size_note (incl. ${ROW_DRAFT_GB} GB MTP draft)"

  echo
  note "$glyph $cute — $ROW_LABEL — $size_note"
  if [[ -n "$ROW_REASONS" ]]; then
    dim "$ROW_REASONS"
  fi
  if [[ "$ROW_MIN_RELEASE" != "0" ]]; then
    dim "needs llama.cpp b${ROW_MIN_RELEASE}+ to load — step 3 installs llama.cpp via"
    dim "brew; if yours is older, \`brew upgrade llama.cpp\` after this script finishes."
  fi

  default="N"
  [[ -n "$ROW_DEFAULT_YES" ]] && default="Y"
  if ask_yn "install $cute?" "$default"; then
    dest="$WEIGHTS_DIR/$MODEL_FILENAME"
    note "downloading $cute (~${ROW_MAIN_GB} GB) → $(basename "$dest")"
    download_model_file "$MODEL_URL" "$dest"
    ok "$cute installed"
    if [[ -n "$DRAFT_FILENAME" ]]; then
      draft_dest="$WEIGHTS_DIR/$DRAFT_FILENAME"
      note "downloading $cute's MTP draft (~${ROW_DRAFT_GB} GB) → $(basename "$draft_dest")"
      download_model_file "$DRAFT_URL" "$draft_dest"
      ok "$cute draft installed"
    fi
  fi
done

INSTALLED_COUNT=$(uv run --project "$ENOUGH_HOME" python -c "
from enough import models as m
print(sum(1 for r in m.install_menu_rows() if r['installed']))
")

echo
if [[ "$INSTALLED_COUNT" == "0" ]]; then
  warn "no local models installed. that's fine if you're planning to run"
  warn "cloud-only through the OPRO-API slot (see step 10) — otherwise,"
  warn "re-run this script anytime to add one."
fi

# Seed the live current selection if not yet set. g40-04 is the default
# when it's installed (lightest surface area, most forgiving hardware-wise);
# if it isn't, fall back to whichever installed model has the smallest
# total download, so `current` never points at a model that isn't actually
# on disk. If nothing at all is installed (the cloud-only path above), seed
# g40-04 anyway — a harmless default that just means nothing loads until
# the user installs or switches.
mkdir -p "$ENOUGH_HOME/config"
if [[ -z "$HAD_LIVE_STATE" ]]; then
  SEED_CUTE=$(uv run --project "$ENOUGH_HOME" python -c "
from enough import models as m
rows = m.install_menu_rows()
by_cute = {r['cute']: r for r in rows}
if by_cute.get('g40-04', {}).get('installed'):
    print('g40-04')
else:
    installed = [r for r in rows if r['installed']]
    if installed:
        installed.sort(key=lambda r: r['size_gb'])
        print(installed[0]['cute'])
    else:
        print('g40-04')
")
  printf '{"current": "%s"}\n' "$SEED_CUTE" > "$ENOUGH_HOME/config/models.json"
  if [[ "$SEED_CUTE" == "g40-04" ]]; then
    ok "live model state seeded to default (G40-04)"
  else
    ok "live model state seeded to $SEED_CUTE (G40-04 wasn't installed; smallest model that is)"
  fi
fi

echo
note "all your local models:"
uv run --project "$ENOUGH_HOME" python -m enough.models install-menu | while IFS= read -r line; do
  dim "$line"
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
note "optional: enable the OpenRouter cloud-model slot (OPRO-API)"
note ""
note "  enough is local-first by default — whichever local models you just"
note "  installed run entirely on this machine. if you'd also like to route"
note "  through a cloud model via openrouter.ai (gpt, claude, mistral, etc.), enough"
note "  has a fifth opt-in model slot that's intentionally hard to enable"
note "  accidentally:"
note ""
note "    a. open the broker pane (top-nav 'broker' icon) and turn OFF"
note "       'local models only'"
note "    b. open the model picker — OPRO-API now appears as a fifth slot"
note "    c. click it to run a 3-screen onboarding wizard (account / billing"
note "       acknowledgement, paste an openrouter api key, automatic health"
note "       check). the key is stored in macOS Keychain, never on disk in"
note "       plaintext"
note ""
note "  privacy is what local-first guarantees; cloud cost is sometimes lower"
note "  than the marginal electricity of local inference. the choice is yours."
note ""
note "troubleshooting: re-run this script any time — it's idempotent."
