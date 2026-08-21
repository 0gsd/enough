#!/usr/bin/env bash
# tests/bootstrap_linux_harness.sh — exercise bootstrap.sh's LINUX function
# group end to end, on any machine, without installing or downloading a
# single real thing.
#
#     bash tests/bootstrap_linux_harness.sh          # all scenarios
#     bash tests/bootstrap_linux_harness.sh -v       # ...and show the output
#
# How: run the REAL bootstrap.sh (never a copy, never an extract — the
# thing that ships) against
#
#   • a fake $HOME, so ~/enough, ~/.local/bin and ~/.cache are scratch;
#   • a PATH-prefixed shim dir where `uname` says Linux, `curl` copies a
#     fixture instead of reaching GitHub, `git clone` materialises a
#     minimal checkout out of this repo, `uv` execs the repo's own venv
#     python, `sha256sum` says what the scenario tells it to, `ldconfig`
#     reports the Vulkan loader the scenario wants, and `apt-get` merely
#     exists so the package-manager hints are deterministic;
#   • ENOUGH_VULKAN_ICD_DIRS pointed at a scratch dir, because the real ICD
#     manifest paths live under /usr and a test may not write there;
#   • a scripted answer stream on stdin.
#
# What it does NOT do: verify a real llama.cpp archive. The pinned sha256
# table is checked for *shape* (all four builds present, and the URL the
# script chooses matches the arch/variant it announced), and the mismatch
# path is checked for real, but the happy path's digest comes from the
# scenario rather than from 16-32 MB of GitHub. Downloading the actual
# archive is the VM pass's job, not CI's.
#
# Every scenario asserts on the fake home afterwards, so "it ran without
# erroring" is never mistaken for "it did the right thing".
#
# Scenarios: A CPU/x64 · B Vulkan/arm64 · C user overrides the detection ·
# D checksum mismatch aborts · E missing prerequisite · F idempotent re-run ·
# G the macOS path, unchanged (same ten steps, same labels, same six brew
# formulae) — because `uname` is a shim, that regression check runs here
# too, on either host, and this whole file is bash-3.2 clean so the macOS
# runner can execute it.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
BOOTSTRAP="$REPO_ROOT/bootstrap.sh"
# Absolute, because scenario E hands the run a PATH with almost nothing on
# it and `env -i … bash` would then fail to find bash itself.
BASH_ABS="$(command -v bash)"
# The uv shim execs the repo's own venv python; run from the repo root so
# `python -m enough.models` imports even without an editable install.
cd "$REPO_ROOT"
VERBOSE=""
[[ "${1:-}" == "-v" ]] && VERBOSE=1

WORK="$(mktemp -d "${TMPDIR:-/tmp}/enough-bootstrap-harness.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0
SCENARIO=""

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
good() { PASS=$((PASS + 1)); printf '   \033[32mok\033[0m   %s\n' "$*"; }
bad()  { FAIL=$((FAIL + 1)); printf '   \033[31mFAIL\033[0m %s — %s\n' "$SCENARIO" "$*"; }

check()      { if [[ -n "$1" ]];   then good "$2"; else bad "$2"; fi; }
check_file() { if [[ -f "$1" ]];   then good "$2"; else bad "$2 (missing $1)"; fi; }
check_grep() {  # pattern file message
  if grep -q -- "$1" "$2" 2>/dev/null; then good "$3"
  else bad "$3 (no /$1/ in $(basename "$2"))"; fi
}
check_no_grep() {
  if grep -q -- "$1" "$2" 2>/dev/null; then bad "$3 (unexpected /$1/)"
  else good "$3"; fi
}

# ---------------------------------------------------------------------------
# The pinned checksum table, read back out of bootstrap.sh
# ---------------------------------------------------------------------------
# Doubles as an assertion: all four Linux builds must carry a pin, or a
# user on that arch/variant hits "no pinned checksum for …" and stops.
pin_for() {
  sed -n "s/^ *$1) *echo \"\([0-9a-f]\{64\}\)\".*/\1/p" "$BOOTSTRAP" | head -n 1
}

say "pinned llama.cpp checksums"
SCENARIO="pins"
for kind in ubuntu-x64 ubuntu-vulkan-x64 ubuntu-arm64 ubuntu-vulkan-arm64; do
  p="$(pin_for "$kind")"
  check "$([[ ${#p} -eq 64 ]] && echo 1)" "$kind carries a 64-hex sha256 pin"
done
RELEASE="$(sed -n 's/^LLAMA_RELEASE="\(b[0-9]*\)".*/\1/p' "$BOOTSTRAP" | head -n 1)"
check "$([[ -n "$RELEASE" ]] && echo 1)" "llama.cpp release pin found ($RELEASE)"
MINREQ="$(sed -n 's/^LLAMA_MIN_REQUIRED="\([0-9]*\)".*/\1/p' "$BOOTSTRAP" | head -n 1)"
check "$([[ -n "$MINREQ" && "${RELEASE#b}" -ge "$MINREQ" ]] && echo 1)" \
      "the pinned release ($RELEASE) satisfies the registry floor (b$MINREQ)"

# ---------------------------------------------------------------------------
# Fixture archive: what `curl` "downloads"
# ---------------------------------------------------------------------------
# Same shape as a real llama.cpp Linux release: a single llama-$RELEASE/
# directory holding llama-server, a soname symlink chain, and LICENSE.
# llama-server is a shell script that answers --version, which is exactly
# how bootstrap.sh verifies the install.
build_fixture() {
  local stage="$WORK/fixture/llama-$RELEASE"
  mkdir -p "$stage"
  cat > "$stage/llama-server" <<EOF
#!/bin/sh
echo "version: ${RELEASE#b} (harness-fixture)"
EOF
  chmod +x "$stage/llama-server"
  printf 'ELF-ish\n' > "$stage/libggml-base.so.0.19.0"
  ln -sf libggml-base.so.0.19.0 "$stage/libggml-base.so.0"
  ln -sf libggml-base.so.0      "$stage/libggml-base.so"
  printf 'ELF-ish\n' > "$stage/libllama.so.0.0.10362"
  ln -sf libllama.so.0.0.10362 "$stage/libllama.so.0"
  printf 'ELF-ish\n' > "$stage/libggml-cpu-haswell.so"
  printf 'MIT-ish\n' > "$stage/LICENSE"
  # A tool we deliberately do NOT install — the archive ships ~20 of them.
  printf 'not ours\n' > "$stage/llama-bench"
  ( cd "$WORK/fixture" && tar czf "$WORK/fixture.tar.gz" "llama-$RELEASE" )
}
build_fixture

# ---------------------------------------------------------------------------
# Shims
# ---------------------------------------------------------------------------
SHIM="$WORK/shim"
mkdir -p "$SHIM"

w() {  # w <name> <<'BODY'
  local name="$1"
  cat > "$SHIM/$name"
  chmod +x "$SHIM/$name"
}

w uname <<'SH'
#!/bin/sh
case "${1:-}" in
  -m) echo "${HARNESS_ARCH:-x86_64}" ;;
  *)  echo "${HARNESS_UNAME:-Linux}" ;;
esac
SH

w git <<'SH'
#!/bin/sh
echo "git $*" >> "$HARNESS_LOG"
case "$1" in
  clone)
    # A minimal but real-enough checkout: the two directories enough.models
    # reads plus the project files, and a .git so a re-run takes the pull
    # branch. Symlinked, so this costs nothing and can't drift.
    dest="$3"
    mkdir -p "$dest/.git"
    ln -sfn "$HARNESS_REPO/enough"   "$dest/enough"
    ln -sfn "$HARNESS_REPO/defaults" "$dest/defaults"
    cp "$HARNESS_REPO/pyproject.toml" "$HARNESS_REPO/uv.lock" "$dest/" 2>/dev/null || true
    echo "Cloning into '$dest'..."
    ;;
  *) : ;;
esac
exit 0
SH

w uv <<'SH'
#!/bin/sh
echo "uv $*" >> "$HARNESS_LOG"
if [ "${1:-}" = "--version" ]; then echo "uv 9.9.9 (harness)"; exit 0; fi
if [ "${1:-}" = "sync" ]; then exit 0; fi
if [ "${1:-}" = "run" ]; then
  shift
  # Drop uv's own flags up to the interpreter, then exec the repo's venv
  # python directly — no uv, no cache, no network, same registry code.
  while [ $# -gt 0 ] && [ "$1" != "python" ]; do
    case "$1" in
      --project) shift 2 ;;
      *) shift ;;
    esac
  done
  [ "${1:-}" = "python" ] && shift
  exec "$HARNESS_REPO/.venv/bin/python" "$@"
fi
exit 0
SH

w curl <<'SH'
#!/bin/sh
echo "curl $*" >> "$HARNESS_LOG"
out=""
url=""
prev=""
for a in "$@"; do
  case "$prev" in -o) out="$a" ;; esac
  case "$a" in http*) url="$a" ;; esac
  prev="$a"
done
echo "$url" >> "$HARNESS_URLS"
if [ -n "$out" ]; then
  case "$url" in
    *llama.cpp/releases/*) cp "$HARNESS_FIXTURE" "$out" ;;
    *) printf 'harness-stub\n' > "$out" ;;
  esac
fi
exit 0
SH

w sha256sum <<'SH'
#!/bin/sh
# Scenario-controlled: the fixture archive is not the pinned binary, so a
# real digest here would only ever exercise the mismatch path.
echo "${HARNESS_DIGEST:-deadbeef}  $1"
SH

w shasum <<'SH'
#!/bin/sh
echo "${HARNESS_DIGEST:-deadbeef}  ${2:-$1}"
SH

w ldconfig <<'SH'
#!/bin/sh
if [ -n "${HARNESS_VULKAN_LOADER:-}" ]; then
  echo "	libvulkan.so.1 (libc6,x86-64) => /lib/x86_64-linux-gnu/libvulkan.so.1"
fi
exit 0
SH

# Present only so PKG_INSTALL resolves to apt on every host, macOS included.
w apt-get <<'SH'
#!/bin/sh
echo "apt-get $*" >> "$HARNESS_LOG"
exit 0
SH

# For the macOS no-regression scenario (G) only.
w brew <<'SH'
#!/bin/sh
echo "brew $*" >> "$HARNESS_LOG"
case "${1:-}" in
  --version) echo "Homebrew 9.9.9 (harness)" ;;
  list)      : ;;                 # nothing installed → every pkg gets installed
  install)   echo "==> installing $2" ;;
esac
exit 0
SH

w sw_vers <<'SH'
#!/bin/sh
echo "15.9"
SH

# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------
# run_bootstrap <name> — reads: HARNESS_ARCH, HARNESS_VULKAN_LOADER,
# HARNESS_ICD, HARNESS_DIGEST, ANSWERS (newline string). Writes: $HOME_DIR,
# $OUT, $LOG, $URLS, $RC.
run_bootstrap() {
  local name="$1"
  SCENARIO="$name"
  local base="$WORK/$name"
  rm -rf "$base"
  HOME_DIR="$base/home"
  OUT="$base/out.txt"
  LOG="$base/cmds.txt"
  URLS="$base/urls.txt"
  local icd="$base/icd.d"
  mkdir -p "$HOME_DIR" "$icd"
  : > "$LOG"
  : > "$URLS"
  [[ -n "${HARNESS_ICD:-}" ]] && printf '{}\n' > "$icd/scenario.json"
  [[ -n "${PRESEED:-}" ]] && eval "$PRESEED"

  printf '%s\n' "$ANSWERS" | \
  env -i \
    PATH="${PATH_OVERRIDE:-$SHIM:/usr/bin:/bin:/usr/sbin:/sbin}" \
    HOME="$HOME_DIR" \
    TERM=dumb \
    LANG=C.UTF-8 \
    HARNESS_REPO="$REPO_ROOT" \
    HARNESS_LOG="$LOG" \
    HARNESS_URLS="$URLS" \
    HARNESS_FIXTURE="$WORK/fixture.tar.gz" \
    HARNESS_ARCH="${HARNESS_ARCH:-x86_64}" \
    HARNESS_UNAME="${HARNESS_UNAME:-Linux}" \
    HARNESS_VULKAN_LOADER="${HARNESS_VULKAN_LOADER:-}" \
    HARNESS_DIGEST="${HARNESS_DIGEST:-deadbeef}" \
    ENOUGH_VULKAN_ICD_DIRS="$icd" \
    ENOUGH_REPO_URL="https://example.invalid/enough.git" \
    "$BASH_ABS" "$BOOTSTRAP" > "$OUT" 2>&1
  RC=$?
  if [[ -n "$VERBOSE" ]]; then
    echo "--- $name (rc=$RC) ---"
    cat "$OUT"
  fi
}

answers() { ANSWERS="$(printf '%s\n' "$@")"; }

# The prompt order on a fresh Linux install with uv already present:
#   ready to start? → use the <x> build? → install <cute>? ×7 →
#   download whisper? → download MADLAD?
FRESH_ANSWERS=(y y n n n n n n n n n)

# ---------------------------------------------------------------------------
say "scenario A — x86_64, no Vulkan driver → CPU build"
# ---------------------------------------------------------------------------
HARNESS_ARCH=x86_64 HARNESS_VULKAN_LOADER= HARNESS_ICD= \
HARNESS_DIGEST="$(pin_for ubuntu-x64)" \
PRESEED= answers "${FRESH_ANSWERS[@]}"
HARNESS_ARCH=x86_64 HARNESS_VULKAN_LOADER="" HARNESS_ICD="" \
  HARNESS_DIGEST="$(pin_for ubuntu-x64)" run_bootstrap A-cpu-x64

check "$([[ $RC -eq 0 ]] && echo 1)" "exits 0 (got $RC)"
check_grep "Linux detected" "$OUT" "announces the platform"
check_grep "picking the CPU build" "$OUT" "explains the CPU choice"
check_grep "no usable Vulkan setup found" "$OUT" "…and says what it looked for"
check_grep "llama-b10362-bin-ubuntu-x64.tar.gz" "$URLS" "downloads the CPU x64 archive"
check_no_grep "vulkan" "$URLS" "…and nothing Vulkan"
check_grep "checksum verified" "$OUT" "verifies the checksum"
check_file "$HOME_DIR/enough/bin/llama-server" "llama-server lands in ~/enough/bin"
check "$([[ -x "$HOME_DIR/enough/bin/llama-server" ]] && echo 1)" "…and is executable"
check_file "$HOME_DIR/enough/bin/libggml-base.so.0.19.0" "the shared objects land beside it"
check "$([[ -L "$HOME_DIR/enough/bin/libggml-base.so" ]] && echo 1)" \
      "…with their soname symlink chain intact (\$ORIGIN rpath needs it)"
check_file "$HOME_DIR/enough/bin/LICENSE-llama.cpp" "the llama.cpp LICENSE travels with it"
check "$([[ ! -e "$HOME_DIR/enough/bin/llama-bench" ]] && echo 1)" \
      "the archive's other tools are NOT installed"
check "$([[ ! -d "$HOME_DIR/enough/bin/.download" ]] && echo 1)" "the download scratch dir is cleaned up"
check_grep "b10362" "$OUT" "reports the installed release"
check_file "$HOME_DIR/.local/bin/enough" "the PATH wrapper is written"
check "$([[ -x "$HOME_DIR/.local/bin/enough" ]] && echo 1)" "…and is executable"
check_file "$HOME_DIR/enough/config/models.json" "live model state is seeded"
check "$([[ -d "$HOME_DIR/enough/weights" ]] && echo 1)" "the weights dir exists"
check "$([[ -z "$(ls -A "$HOME_DIR/enough/weights" 2>/dev/null | grep -c gguf | sed 's/^0$//')" ]] && echo 1)" \
      "…and no model was downloaded (every prompt answered no)"
# No pandoc one-liner any more: pypandoc-binary ships pandoc as a base wheel,
# so `uv sync` installs it and offering a distro package would be advice to
# install a second copy (convert-plan §8).
check_no_grep "install pandoc" "$OUT" "no longer offers pandoc as an install"
check_grep "sudo apt install tor" "$OUT" "prints the tor install one-liner"
check_grep "whisper.cpp" "$OUT" "names whisper.cpp as a build-it-yourself extra"
check_grep "harper" "$OUT" "names harper as an optional extra"
check_no_grep "brew" "$OUT" "never mentions Homebrew on Linux"
check_grep "Secret Service" "$OUT" "keyring copy is the Linux one"
check_grep "\[10/10\]" "$OUT" "runs ten steps, same as macOS"

# ---------------------------------------------------------------------------
say "scenario B — aarch64 with a Vulkan loader + driver → Vulkan build"
# ---------------------------------------------------------------------------
answers "${FRESH_ANSWERS[@]}"
HARNESS_ARCH=aarch64 HARNESS_VULKAN_LOADER=1 HARNESS_ICD=1 \
  HARNESS_DIGEST="$(pin_for ubuntu-vulkan-arm64)" run_bootstrap B-vulkan-arm64

check "$([[ $RC -eq 0 ]] && echo 1)" "exits 0 (got $RC)"
check_grep "picking the Vulkan build" "$OUT" "explains the Vulkan choice"
check_grep "found a Vulkan loader" "$OUT" "…naming both signals it found"
check_grep "llama-b10362-bin-ubuntu-vulkan-arm64.tar.gz" "$URLS" "downloads the Vulkan arm64 archive"
check_file "$HOME_DIR/enough/bin/llama-server" "llama-server installed"

# ---------------------------------------------------------------------------
say "scenario C — detection says CPU, user overrides to Vulkan"
# ---------------------------------------------------------------------------
# Same as A but answering NO to "use the cpu build?" — the choice is
# offered explicitly, so declining must actually flip it.
answers y n n n n n n n n n n
HARNESS_ARCH=x86_64 HARNESS_VULKAN_LOADER="" HARNESS_ICD="" \
  HARNESS_DIGEST="$(pin_for ubuntu-vulkan-x64)" run_bootstrap C-override

check "$([[ $RC -eq 0 ]] && echo 1)" "exits 0 (got $RC)"
check_grep "switched to the vulkan build" "$OUT" "honours the override"
check_grep "llama-b10362-bin-ubuntu-vulkan-x64.tar.gz" "$URLS" "downloads the Vulkan x64 archive"

# ---------------------------------------------------------------------------
say "scenario D — checksum mismatch aborts without installing"
# ---------------------------------------------------------------------------
answers "${FRESH_ANSWERS[@]}"
HARNESS_ARCH=x86_64 HARNESS_VULKAN_LOADER="" HARNESS_ICD="" \
  HARNESS_DIGEST="0000000000000000000000000000000000000000000000000000000000000000" \
  run_bootstrap D-badsum

check "$([[ $RC -ne 0 ]] && echo 1)" "exits non-zero (got $RC)"
check_grep "sha256 mismatch" "$OUT" "says why"
check "$([[ ! -e "$HOME_DIR/enough/bin/llama-server" ]] && echo 1)" \
      "no llama-server was installed"
check "$([[ ! -d "$HOME_DIR/enough/bin/.download" ]] && echo 1)" \
      "the unverified download is deleted"

# ---------------------------------------------------------------------------
say "scenario E — a missing prerequisite stops with the install command"
# ---------------------------------------------------------------------------
answers y
# A PATH with no `git` anywhere on it — not merely no shim. /usr/bin has a
# real git on both CI runners, so hiding the shim alone would prove nothing
# (and would then run a real `git clone` against example.invalid).
MINBIN="$WORK/minbin"
MINSHIM="$WORK/minshim"
mkdir -p "$MINBIN" "$MINSHIM"
for t in cat head sed grep tr ls; do
  src="$(command -v "$t" 2>/dev/null || true)"
  [[ -n "$src" ]] && ln -sf "$src" "$MINBIN/$t"
done
# Every shim except git.
for s in "$SHIM"/*; do
  [[ "$(basename "$s")" == "git" ]] && continue
  ln -sf "$s" "$MINSHIM/$(basename "$s")"
done
PATH_OVERRIDE="$MINSHIM:$MINBIN" HARNESS_ARCH=x86_64 run_bootstrap E-no-git
PATH_OVERRIDE=

check "$([[ $RC -ne 0 ]] && echo 1)" "exits non-zero (got $RC)"
check_grep "git is not installed" "$OUT" "names the missing tool"
check_grep "sudo apt install git" "$OUT" "…and the exact command to fix it"
check "$([[ ! -d "$HOME_DIR/enough" ]] && echo 1)" "nothing was created"

# ---------------------------------------------------------------------------
say "scenario F — re-run is idempotent (no re-download, no re-clone)"
# ---------------------------------------------------------------------------
# Stage a home that already has everything: a checkout, a current
# llama-server, and seeded model state.
answers y y n n n n n n n n n
PRESEED='
  mkdir -p "$HOME_DIR/enough/.git" "$HOME_DIR/enough/bin" "$HOME_DIR/enough/config"
  ln -sfn "'"$REPO_ROOT"'/enough"   "$HOME_DIR/enough/enough"
  ln -sfn "'"$REPO_ROOT"'/defaults" "$HOME_DIR/enough/defaults"
  printf "#!/bin/sh\necho \"version: 10362 (preseeded)\"\n" > "$HOME_DIR/enough/bin/llama-server"
  chmod +x "$HOME_DIR/enough/bin/llama-server"
  printf "{\"current\": \"g40-04\"}\n" > "$HOME_DIR/enough/config/models.json"
'
HARNESS_ARCH=x86_64 HARNESS_VULKAN_LOADER="" HARNESS_ICD="" \
  HARNESS_DIGEST="$(pin_for ubuntu-x64)" run_bootstrap F-rerun
PRESEED=

check "$([[ $RC -eq 0 ]] && echo 1)" "exits 0 (got $RC)"
check_grep "already in ~/enough/bin" "$OUT" "skips the llama.cpp install"
check_no_grep "llama.cpp/releases" "$URLS" "downloads no archive at all"
check_grep "already exists as a git repo" "$OUT" "takes the pull branch, not clone"
check_no_grep "Cloning into" "$OUT" "…so nothing is re-cloned"

# ---------------------------------------------------------------------------
say "scenario G — the macOS path still does exactly what it always did"
# ---------------------------------------------------------------------------
# The Linux port was allowed to change the macOS path's *wording*, not its
# behaviour. Pin the shape: same ten steps, same labels, same order, brew
# still asked for the same six formulae, and none of the Linux prose
# leaking across. Runs on any host — `uname` is a shim.
answers y n n n n n n n n n
HARNESS_UNAME=Darwin HARNESS_ARCH=arm64 run_bootstrap G-macos
HARNESS_UNAME=

check "$([[ $RC -eq 0 ]] && echo 1)" "exits 0 (got $RC)"
check_grep "macOS detected" "$OUT" "takes the darwin branch"
STEPS="$(grep -o '\[[0-9]*/10\] .*' "$OUT" | sed 's/\x1b\[[0-9;]*m//g')"
printf '%s\n' "$STEPS" > "$WORK/G-macos/steps.txt"
EXPECTED_STEPS="[1/10] checking your platform
[2/10] checking for Homebrew
[3/10] installing Homebrew packages
[4/10] setting up ~/enough (the install directory)
[5/10] preparing the Python environment
[6/10] placing the LLM weights
[7/10] placing the voice-input model
[8/10] placing the offline-translation model
[9/10] installing the \`enough\` command on your PATH
[10/10] done"
if [[ "$STEPS" == "$EXPECTED_STEPS" ]]; then
  good "ten steps, unchanged labels, unchanged order"
else
  bad "step sequence drifted:"
  diff <(printf '%s\n' "$EXPECTED_STEPS") <(printf '%s\n' "$STEPS") || true
fi
for f in llama.cpp uv tor whisper-cpp harper; do
  check_grep "brew install $f" "$WORK/G-macos/cmds.txt" "still brew-installs $f"
done
check_no_grep "brew install pandoc" "$WORK/G-macos/cmds.txt" \
      "no longer brew-installs pandoc (it ships in the venv)"
check_no_grep "sudo apt" "$OUT" "no Linux package-manager hints leak into the Mac run"
check_no_grep "~/enough/bin" "$OUT" "no Linux llama.cpp prose leaks into the Mac run"
check_grep "macOS Keychain" "$OUT" "keyring copy is still the macOS one"

# ---------------------------------------------------------------------------
printf '\n\033[1m%s\033[0m\n' "harness: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
exit 0
