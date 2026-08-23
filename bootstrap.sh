#!/usr/bin/env bash
# bootstrap.sh — guided installer for `enough`. macOS and Linux.
#
# Ten steps either way; the first few differ by platform because the way
# you get a C++ inference server differs by platform, and nothing else
# really does.
#
#   macOS                             Linux
#   1. platform check                 1. platform check (+ arch, distro)
#   2. Homebrew present?              2. prerequisites: git, curl, tar, uv
#   3. brew install llama.cpp uv         (uv via its official installer if
#      tor whisper-cpp harper            missing); optional extras printed
#   4. clone/pull ~/enough            3. clone/pull ~/enough
#   5. uv sync                        4. uv sync
#                                     5. llama.cpp: pinned prebuilt release
#                                        archive → ~/enough/bin/
#   6. weights: walk the 7-model registry one at a time — live
#      machine-feasibility verdict, size (main + any MTP draft), y/n each
#   7. whisper model for voice input (~142 MB)
#   8. optional MADLAD-400-3B-MT translation model (~3 GB)
#   9. `enough` launcher at ~/.local/bin/enough
#  10. what's next
#
# Why the split at llama.cpp: brew's formula is the right answer on macOS
# and there is no equivalent on Linux worth having (no distro packages a
# current build, source builds mean a toolchain support burden). So Linux
# gets a checksum-pinned prebuilt release from ggml-org/llama.cpp,
# unpacked into ~/enough/bin/ — which the backend looks in *before* PATH
# (enough.models.find_llama_server: $ENOUGH_LLAMA_SERVER → ~/enough/bin →
# PATH). See docs/linux-plan.md §3.2.
#
# You can re-run this script safely. Each step checks state before acting.
# If anything blows up, fix the thing it complained about and re-run.

set -euo pipefail

# ---------------------------------------------------------------------------
# Cosmetics
# ---------------------------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; CYAN=$'\033[36m'; GREEN=$'\033[32m'
YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'

# Step numbers auto-increment rather than being written out, so the
# platform-specific prelude (2 brew steps on macOS, 1 prerequisites step
# plus 1 llama.cpp step on Linux) can differ without renumbering anything
# below it. Both platforms happen to land on ten.
STEP_N=0
step() { STEP_N=$((STEP_N + 1)); printf "\n${CYAN}${BOLD}[%s/%s] %s${RESET}\n" "$STEP_N" "$TOTAL" "$1"; }
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
# OS dispatch
# ---------------------------------------------------------------------------
# One script, two function groups. Everything from the repo clone onward is
# shared; only the platform check, the "how do I get llama.cpp and uv" steps,
# and a few paragraphs of closing prose branch. Written for bash 3.2 (what
# macOS ships) throughout — no associative arrays, no `${x^^}`, no mapfile —
# even though the Linux side will always be running bash 5.
UNAME_S="$(uname)"
case "$UNAME_S" in
  Darwin) PLATFORM="darwin" ;;
  Linux)  PLATFORM="linux" ;;
  *)
    err "enough installs on macOS and Linux. detected: $UNAME_S"
    exit 1
    ;;
esac

# Linux-only, filled in by platform_linux: CPU arch mapped to llama.cpp's
# release-asset naming, and the local package-manager incantation used in
# every "you'll want to install X" hint.
LLAMA_ARCH=""
PKG_INSTALL="your package manager"

detect_pkg_manager() {
  # Ubuntu 24.04 is the primary support target and Fedora the secondary
  # (docs/linux-plan.md §3.3); the other two are here because printing the
  # right command costs one line each and printing the wrong one costs the
  # user a web search.
  if command -v apt-get >/dev/null 2>&1; then
    PKG_INSTALL="sudo apt install"
  elif command -v dnf >/dev/null 2>&1; then
    PKG_INSTALL="sudo dnf install"
  elif command -v pacman >/dev/null 2>&1; then
    PKG_INSTALL="sudo pacman -S"
  elif command -v zypper >/dev/null 2>&1; then
    PKG_INSTALL="sudo zypper install"
  else
    PKG_INSTALL="your package manager"
  fi
}

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

if [[ "$PLATFORM" == "darwin" ]]; then
  note "This script sets up everything you need to run enough on a Mac:"
  note "  • Homebrew (package manager, if you don't have it)"
  note "  • llama.cpp, uv, tor, whisper-cpp, harper via Homebrew"
  note "  • a clone of the enough repo at ~/enough"
  note "  • a GGUF model file in ~/enough/weights/"
  note "  • a whisper model for voice input in ~/enough/weights/whisper/"
  note "  • (optional) MADLAD-400 translation model in ~/.local/share/translator/"
  note "  • an \`enough\` command on your PATH"
else
  note "This script sets up everything you need to run enough on Linux:"
  note "  • a check that git, curl and tar are there (they usually are)"
  note "  • uv (Python env manager) via its official installer, if missing"
  note "  • a clone of the enough repo at ~/enough"
  note "  • a pinned llama.cpp release in ~/enough/bin/ — no compiling"
  note "  • a GGUF model file in ~/enough/weights/"
  note "  • (optional) a whisper model, and the MADLAD-400 translation model"
  note "  • an \`enough\` command on your PATH (~/.local/bin)"
  note ""
  note "Nothing is installed system-wide and nothing needs sudo. Optional"
  note "extras (tor, whisper.cpp, harper) are printed with the"
  note "command to install them, never installed behind your back."
fi
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
platform_darwin() {
  note "enough v0.2.7 runs on macOS (the platform it grew up on) and Linux."
  ok "macOS detected ($(sw_vers -productVersion))"
}

platform_linux() {
  note "enough's Linux support is new in v0.2.0. The backend is checked on"
  note "every commit by CI (Ubuntu + macOS), but it has had far less time in"
  note "real hands than the macOS path — expect the odd rough edge."
  local machine pretty
  machine="$(uname -m)"
  case "$machine" in
    x86_64|amd64)   LLAMA_ARCH="x64" ;;
    aarch64|arm64)  LLAMA_ARCH="arm64" ;;
    *)
      err "unsupported CPU architecture: $machine"
      note "llama.cpp publishes Linux release binaries for x86_64 and aarch64."
      note "on anything else you'd need to build llama.cpp yourself and put"
      note "llama-server in ~/enough/bin/ — everything else here still works."
      exit 1
      ;;
  esac
  pretty="Linux"
  if [[ -r /etc/os-release ]]; then
    pretty="$( . /etc/os-release 2>/dev/null; printf '%s' "${PRETTY_NAME:-Linux}" )"
  fi
  ok "Linux detected ($pretty, $machine)"
  detect_pkg_manager
}

step "checking your platform"
if [[ "$PLATFORM" == "darwin" ]]; then
  platform_darwin
else
  platform_linux
fi

# ---------------------------------------------------------------------------
# 2 (+3 on macOS). Dependencies
# ---------------------------------------------------------------------------
deps_darwin() {
  step "checking for Homebrew"
  note "Homebrew is the standard package manager for macOS. We use it to install"
  note "llama.cpp (the LLM server), uv (fast Python env tool), tor (used by the"
  note "broker to anonymize off-allowlist web fetches), and a couple of others."
  if command -v brew >/dev/null 2>&1; then
    ok "Homebrew is installed ($(brew --version | head -1))"
  else
    warn "Homebrew is NOT installed."
    note "visit https://brew.sh for the one-line install. when it's done, re-run this script."
    exit 1
  fi

  step "installing Homebrew packages"
  note "five utilities go on this pass:"
  note "  • llama.cpp   — the local LLM server that backs enough"
  note "  • uv          — manages the Python environment that runs enough itself"
  note "  • tor         — anonymization proxy used by the broker for off-allowlist web fetches"
  note "  • whisper-cpp — local speech-to-text for the mic button in chat"
  note "  • harper      — local grammar/spell checker (Apache 2.0, by Automattic) used by the analyzer skill's proofread mode"

  for pkg in llama.cpp uv tor whisper-cpp harper; do
    install_brew_pkg "$pkg"
  done
}

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

require_cmd_linux() {
  # A hard prerequisite. We don't auto-install these: they're one apt/dnf
  # line, they're already present on any normal desktop install, and a
  # script that starts sudo-ing packages onto someone's machine is not the
  # kind of installer enough wants to be.
  local cmd="$1" pkg="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd found"
    return 0
  fi
  err "$cmd is not installed."
  note "install it, then re-run this script:"
  note ""
  note "    $PKG_INSTALL $pkg"
  note ""
  exit 1
}

deps_linux() {
  step "checking prerequisites"
  note "enough needs three ordinary command-line tools plus uv:"
  note "  • git   — to fetch and update the enough source"
  note "  • curl  — to download llama.cpp and the model weights"
  note "  • tar   — to unpack the llama.cpp release archive"
  note "  • uv    — manages the Python environment that runs enough itself"
  note ""
  require_cmd_linux git git
  require_cmd_linux curl curl
  require_cmd_linux tar tar

  if command -v uv >/dev/null 2>&1; then
    ok "uv is installed ($(uv --version 2>/dev/null | head -1))"
  else
    warn "uv is NOT installed."
    note "uv is Astral's Python package/environment manager. enough uses it so"
    note "its dependencies live in ~/enough/.venv and never touch your system"
    note "Python. The official installer drops a single static binary into"
    note "~/.local/bin — no root, no system packages, and \`uv self uninstall\`"
    note "removes it cleanly."
    note ""
    note "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    note ""
    if ! ask_yn "run that installer now?" Y; then
      err "uv is required. install it however you prefer, then re-run this script."
      exit 1
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer writes to ~/.local/bin (or $XDG_BIN_HOME) and tells the
    # user to restart their shell. We're mid-script, so put it on PATH here
    # too — otherwise every `uv` call below would fail on a fresh machine.
    export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
      err "uv still isn't on PATH after the install."
      note "open a new terminal (so your shell picks up ~/.local/bin) and re-run."
      exit 1
    fi
    ok "uv installed ($(uv --version 2>/dev/null | head -1))"
  fi

  note ""
  note "optional extras — enough degrades gracefully without every one of"
  note "these, and says so in the UI when it hits one. install what you want:"
  note ""
  note "  • tor         — anonymizes off-allowlist web fetches (without it,"
  note "                  off-allowlist fetches are simply denied)"
  note "                    $PKG_INSTALL tor"
  note "  • whisper.cpp — the mic button in chat needs a \`whisper-cli\` binary."
  note "                  no distro packages it yet; build it from"
  note "                  https://github.com/ggml-org/whisper.cpp"
  note "  • harper      — grammar/spell pass for the analyzer skill's proofread"
  note "                  mode. https://github.com/automattic/harper (releases,"
  note "                  or \`cargo install harper-cli\`)"
  note ""
  dim "none of these are installed by this script."
}

if [[ "$PLATFORM" == "darwin" ]]; then
  deps_darwin
else
  deps_linux
fi

# ---------------------------------------------------------------------------
# Clone / pull repo
# ---------------------------------------------------------------------------
step "setting up ~/enough (the install directory)"
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
# Python env
# ---------------------------------------------------------------------------
step "preparing the Python environment"
note "\`uv sync\` reads ~/enough/pyproject.toml, creates ~/enough/.venv, and"
note "installs every Python dependency enough needs. No global pip pollution."
note "this also includes:"
note "  • ctranslate2, sentencepiece, huggingface_hub — for the offline"
note "    \`translator\` skill (used by step 8 below)"
note "  • pypandoc-binary + typst — the document converters. both ship as"
note "    python wheels, so every install can open word/opendocument/rtf/"
note "    epub files as markdown and export any markdown to PDF, with no"
note "    separate package to chase. (reading PDFs, powerpoint decks and"
note "    excel workbooks is a bigger optional extra, installed later from"
note "    inside enough — see step 10.)"
if [[ "$PLATFORM" == "darwin" ]]; then
  note "  • keyring — the cross-platform binding to the OS credential store"
  note "    (macOS Keychain on this machine). Used by the optional OpenRouter"
  note "    cloud-model slot to store an api key without ever writing it to"
  note "    disk in plaintext. The slot itself is off by default; see step 10."
else
  note "  • keyring — the cross-platform binding to the OS credential store"
  note "    (the Secret Service — gnome-keyring or kwallet — on this machine)."
  note "    Used by the optional OpenRouter cloud-model slot to store an api"
  note "    key without ever writing it to disk in plaintext. The slot itself"
  note "    is off by default; see step 10. On a headless box with no Secret"
  note "    Service daemon running, the cloud slot simply can't be enabled;"
  note "    nothing else is affected."
fi
( cd "$ENOUGH_HOME" && uv sync )
ok "~/enough/.venv is ready"

# ---------------------------------------------------------------------------
# llama.cpp (Linux only — macOS got it from brew in step 3)
# ---------------------------------------------------------------------------
# Pinned to the same release the desktop app bundles
# (desktop/fetch-sidecars.sh), so all three installers agree on one build.
# Bumping this means bumping the four checksums below it — they come from
# the GitHub release's own published asset digests, and a mismatch aborts
# rather than installing an unverified binary.
LLAMA_RELEASE="b10362"          # ggml-org/llama.cpp, 2026-08-11
LLAMA_MIN_REQUIRED="9200"       # highest llama_cpp_min_release in defaults/models.json

llama_sha256_for() {
  case "$1" in
    ubuntu-x64)          echo "d55a64e814e0a379082f79b9a974499fe14bcc6f4b491ffae23e4a2993d1b85f" ;;
    ubuntu-vulkan-x64)   echo "cd9dc4885a32bae4c7640454e15aeba1324fff8bb6ea003555b5b112aa16d3bc" ;;
    ubuntu-arm64)        echo "69bddd2aa441982bb7cf79ff65faa41a82b0629ad79741b32521ce00cba5165f" ;;
    ubuntu-vulkan-arm64) echo "aaa5cd203ad591ffc637535239ebd5e341fa4d272f70a976825d8823d9325b0e" ;;
    *)                   echo "" ;;
  esac
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    echo ""
  fi
}

installed_llama_release() {
  # b-number of the llama-server at $1, or empty.
  [[ -x "$1" ]] || return 0
  "$1" --version 2>&1 | sed -n 's/^version: \([0-9][0-9]*\).*/\1/p' | head -n 1
}

vulkan_looks_usable() {
  # The heuristic, deliberately two greps and no more: a Vulkan build needs
  # the LOADER (libvulkan.so.1, known to the dynamic linker) and at least
  # one DRIVER (an ICD manifest in a standard search path). Both present →
  # the Vulkan build has something to talk to; either missing → it would
  # start and silently fall back to CPU anyway, at 2x the download.
  #
  # Deliberately NOT `vulkaninfo`: that lives in a separate package
  # (vulkan-tools) which plenty of machines with perfectly good drivers
  # don't have installed, and its absence would push Vulkan-capable users
  # onto the CPU build. Deliberately not a GPU-vendor lspci scrape either
  # — a GPU with no driver installed is exactly the case this must say no
  # to. Whatever it decides, it says so out loud and offers the other one.
  local have_loader="" have_icd="" d
  if command -v ldconfig >/dev/null 2>&1; then
    if ldconfig -p 2>/dev/null | grep -q 'libvulkan\.so\.1'; then have_loader=1; fi
  fi
  for d in $VULKAN_ICD_DIRS; do
    if [[ -d "$d" ]] && ls "$d"/*.json >/dev/null 2>&1; then have_icd=1; fi
  done
  [[ -n "$have_loader" && -n "$have_icd" ]]
}

# Where to look for Vulkan driver manifests. Overridable for the same
# reason ENOUGH_REPO_URL is: tests/bootstrap_linux_harness.sh has to be
# able to stage a machine with (and without) drivers, and it cannot write
# to /usr/share. Unset in every real install.
VULKAN_ICD_DIRS="${ENOUGH_VULKAN_ICD_DIRS:-/usr/share/vulkan/icd.d /usr/local/share/vulkan/icd.d /etc/vulkan/icd.d}"

install_llama_cpp_linux() {
  step "installing llama.cpp"
  note "llama.cpp is the inference server that actually runs your models."
  note "No distro ships a current build and compiling one is a toolchain"
  note "adventure, so enough installs an official prebuilt release straight"
  note "from ggml-org/llama.cpp — pinned to $LLAMA_RELEASE, checksum-verified,"
  note "unpacked into ~/enough/bin/. Nothing goes into /usr; nothing needs"
  note "sudo; enough looks in ~/enough/bin before your PATH, so this build"
  note "wins over anything a package manager may have left lying around."
  note ""

  local bin_dir="$ENOUGH_HOME/bin"
  mkdir -p "$bin_dir"

  local have
  have="$(installed_llama_release "$bin_dir/llama-server")"
  if [[ -n "$have" && "$have" -ge "${LLAMA_RELEASE#b}" ]]; then
    ok "llama.cpp b$have already in ~/enough/bin — nothing to do"
    return 0
  fi

  note "two builds are published for Linux:"
  note "  • Vulkan — offloads layers onto any GPU with a Vulkan driver."
  note "             Much faster when there's a GPU; useless without one."
  note "  • CPU    — works on every machine, needs no drivers at all."
  note ""
  local variant
  if vulkan_looks_usable; then
    variant="vulkan"
    ok "found a Vulkan loader (libvulkan.so.1) and at least one installed driver"
    note "→ picking the Vulkan build"
  else
    variant="cpu"
    note "no usable Vulkan setup found — looked for libvulkan.so.1 via ldconfig"
    note "and for driver manifests in /usr/share/vulkan/icd.d"
    note "→ picking the CPU build"
  fi
  note ""
  if ! ask_yn "use the $variant build?" Y; then
    if [[ "$variant" == "vulkan" ]]; then variant="cpu"; else variant="vulkan"; fi
    warn "switched to the $variant build at your request"
  fi

  local kind archive url want got dl src
  if [[ "$variant" == "vulkan" ]]; then
    kind="ubuntu-vulkan-$LLAMA_ARCH"
  else
    kind="ubuntu-$LLAMA_ARCH"
  fi
  archive="llama-$LLAMA_RELEASE-bin-$kind.tar.gz"
  url="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/$archive"
  want="$(llama_sha256_for "$kind")"
  if [[ -z "$want" ]]; then
    err "no pinned checksum for $kind — this script doesn't know that build."
    exit 1
  fi

  dl="$bin_dir/.download"
  rm -rf "$dl"
  mkdir -p "$dl"
  note "downloading $archive"
  curl -L --progress-bar --retry 3 -o "$dl/$archive" "$url"

  got="$(sha256_of "$dl/$archive")"
  if [[ -z "$got" ]]; then
    warn "no sha256sum/shasum on this machine — skipping checksum verification"
  elif [[ "$got" != "$want" ]]; then
    err "sha256 mismatch for $archive"
    note "  expected $want"
    note "  got      $got"
    note "refusing to install an unverified binary. delete $dl and retry;"
    note "if it happens again, something upstream (or in between) is wrong."
    rm -rf "$dl"
    exit 1
  else
    ok "checksum verified"
  fi

  tar xzf "$dl/$archive" -C "$dl"
  src="$dl/llama-$LLAMA_RELEASE"
  if [[ ! -f "$src/llama-server" ]]; then
    err "unexpected archive layout: no llama-server in $src"
    rm -rf "$dl"
    exit 1
  fi
  # llama-server's only RPATH is $ORIGIN, and the ggml CPU-backend variants
  # are dlopen'd from the same directory — so every .so has to sit BESIDE
  # the binary, not in a lib/ subdir. `cp -a` keeps the soname symlink
  # chains (libggml.so → libggml.so.0 → libggml.so.0.19.0) intact. We take
  # llama-server and the shared objects only; the other twenty CLI tools in
  # the archive aren't ours to install.
  cp -a "$src"/llama-server "$src"/*.so* "$bin_dir"/
  chmod +x "$bin_dir/llama-server"
  [[ -f "$src/LICENSE" ]] && cp -f "$src/LICENSE" "$bin_dir/LICENSE-llama.cpp"
  rm -rf "$dl"

  have="$(installed_llama_release "$bin_dir/llama-server")"
  if [[ -z "$have" ]]; then
    err "the installed llama-server didn't report a version — install looks broken."
    exit 1
  fi
  if [[ "$have" -lt "$LLAMA_MIN_REQUIRED" ]]; then
    err "installed llama.cpp is b$have, but the model registry needs >= b$LLAMA_MIN_REQUIRED"
    exit 1
  fi
  ok "llama.cpp b$have ($variant build) installed at ~/enough/bin/llama-server"
}

if [[ "$PLATFORM" == "linux" ]]; then
  install_llama_cpp_linux
fi

# ---------------------------------------------------------------------------
# 6. Model weights
# ---------------------------------------------------------------------------
step "placing the LLM weights"
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
    if [[ "$PLATFORM" == "darwin" ]]; then
      dim "needs llama.cpp b${ROW_MIN_RELEASE}+ to load — this script installs llama.cpp"
      dim "via brew; if yours is older, \`brew upgrade llama.cpp\` after it finishes."
    else
      dim "needs llama.cpp b${ROW_MIN_RELEASE}+ to load — the pinned release this"
      dim "script puts in ~/enough/bin/ is newer than that, so you're covered."
    fi
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
step "placing the voice-input model"
note "The mic button in the chat input sends audio to a local whisper.cpp"
if [[ "$PLATFORM" == "darwin" ]]; then
  note "binary (installed via Homebrew in step 3) for transcription. It needs a"
else
  note "binary (\`whisper-cli\`) for transcription. It needs a"
fi
note "model file. Recommended: ggml-base.en.bin (~142 MB, English-only,"
note "well-balanced accuracy vs speed). Everything stays on your machine —"
note "no audio leaves this computer."
note ""

WHISPER_DIR="$ENOUGH_HOME/weights/whisper"
WHISPER_MODEL_NAME="ggml-base.en.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL_NAME"
WHISPER_DEFAULT="Y"
mkdir -p "$WHISPER_DIR"

if [[ "$PLATFORM" == "linux" ]] && ! command -v whisper-cli >/dev/null 2>&1; then
  # No distro packages whisper.cpp, so on Linux the binary is very likely
  # absent and the model file would be 142 MB of nothing. Still offered —
  # people do build it — just not pre-answered yes.
  note "note: there's no \`whisper-cli\` on this machine, and no Linux distro"
  note "packages whisper.cpp yet. Build it from"
  note "https://github.com/ggml-org/whisper.cpp if you want the mic button;"
  note "this model file is only useful once you have."
  note ""
  WHISPER_DEFAULT="N"
fi

if [[ -f "$WHISPER_DIR/$WHISPER_MODEL_NAME" ]]; then
  ok "whisper model already present:"
  dim "$WHISPER_DIR/$WHISPER_MODEL_NAME  ($(du -h "$WHISPER_DIR/$WHISPER_MODEL_NAME" | awk '{print $1}'))"
else
  if ask_yn "download $WHISPER_MODEL_NAME (~142 MB)?" "$WHISPER_DEFAULT"; then
    curl -L --progress-bar -o "$WHISPER_DIR/$WHISPER_MODEL_NAME" "$WHISPER_MODEL_URL"
    ok "whisper model downloaded"
  else
    warn "skipping. voice input won't work until a whisper .bin is in $WHISPER_DIR/"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Offline translation model (MADLAD-400-3B-MT)
# ---------------------------------------------------------------------------
step "placing the offline-translation model"
note "enough ships with a \`translator\` skill that does offline translation"
note "across ~419 languages — no API call, no account, no network hop after"
note "the model is downloaded. It's powered by Google's MADLAD-400-3B-MT"
note "(Apache 2.0), served through CTranslate2 + SentencePiece for fast"
note "local inference (Metal on Apple silicon, CPU elsewhere)."
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
step "installing the \`enough\` command on your PATH"
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
step "done"
ok "enough is installed at ~/enough"
ok "weights at ~/enough/weights/"
ok "\`enough\` CLI at ~/.local/bin/enough"
if [[ "$PLATFORM" == "linux" ]]; then
  ok "llama.cpp at ~/enough/bin/llama-server (found before anything on PATH)"
fi
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
note "  (from then on, \`enough --home\` opens the home screen from anywhere:"
note "   every folder you've made into a project, in one list, with a button"
note "   for adding another. \`enough\` in a project folder still opens that"
note "   project directly, exactly as above.)"
note ""
note "optional, and installed from inside enough rather than from here:"
note ""
note "  • PDF reading (the \`pdf\` extra) — opens PDFs, powerpoint decks and"
note "    excel workbooks as editable markdown. ⚙ UI window → extras."
note "    about 250 MB to download, about 1 GB on disk, plus about 0.7 GB"
note "    of document models in ~/enough/weights/docling/. writing PDFs out"
note "    of markdown already works without it."
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
if [[ "$PLATFORM" == "darwin" ]]; then
  note "       check). the key is stored in macOS Keychain, never on disk in"
  note "       plaintext"
else
  note "       check). the key is stored in your desktop's Secret Service"
  note "       (gnome-keyring / kwallet), never on disk in plaintext — so"
  note "       this slot needs a running keyring daemon"
fi
note ""
note "  privacy is what local-first guarantees; cloud cost is sometimes lower"
note "  than the marginal electricity of local inference. the choice is yours."
note ""
if [[ "$PLATFORM" == "linux" ]]; then
  note "optional extras you may still want (nothing here installed them):"
  note "    $PKG_INSTALL tor"
  note "  plus whisper.cpp and harper, built from their own repos. enough"
  note "  degrades gracefully without each of them and says which is missing."
  note ""
fi
note "troubleshooting: re-run this script any time — it's idempotent."
