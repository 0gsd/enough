#!/usr/bin/env bash
# Fetch the two binaries enough.app bundles, from their official releases.
#
#   desktop/src-tauri/binaries/uv-aarch64-apple-darwin   (Tauri externalBin)
#   desktop/src-tauri/vendor/llama/{llama-server,*.dylib,LICENSE}
#
# Neither directory is tracked by git — they're ~63 MB of third-party
# binaries, and a checksum-pinned fetch is a better contract than a blob in
# history. Run this once before `cargo build` / `cargo tauri build`; it is
# idempotent and skips work when the pinned versions are already in place.
#
# Pins live here and are mirrored in docs/tauri-plan.md §4. Bumping either
# means bumping the sha256 next to it — the script refuses a mismatch rather
# than shipping an unverified binary.
set -euo pipefail

# --- pins ------------------------------------------------------------------

UV_VERSION="0.12.3"                       # astral-sh/uv, 2026-08-07
UV_SHA256="546f7f8a6c70ff13a3a9d2bc958db3427298cebf3e0cb756f9177133b7068843"

LLAMA_RELEASE="b10362"                    # ggml-org/llama.cpp, 2026-08-11
LLAMA_SHA256="e353a453cadb25960bea9b24692b72bd0a6b7b50b3bab5860bd5df8a434e7c5b"
# Every registry entry's llama_cpp_min_release must be <= this. Today the
# highest in defaults/models.json is b9200.
LLAMA_MIN_REQUIRED="9200"

TARGET_TRIPLE="aarch64-apple-darwin"      # arm64-only v1 (tauri-plan §4)

# --- layout ----------------------------------------------------------------

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tauri="$here/src-tauri"
cache="$here/vendor-dl"
binaries="$tauri/binaries"
llamadir="$tauri/vendor/llama"

mkdir -p "$cache" "$binaries" "$llamadir"

say() { printf '  %s\n' "$*"; }

fetch() {  # url sha256 dest
    local url="$1" want="$2" dest="$3"
    if [ -f "$dest" ] && [ "$(shasum -a 256 "$dest" | cut -d' ' -f1)" = "$want" ]; then
        say "cached  $(basename "$dest")"
        return
    fi
    say "fetch   $url"
    curl -fsSL --retry 3 -o "$dest.tmp" "$url"
    local got
    got="$(shasum -a 256 "$dest.tmp" | cut -d' ' -f1)"
    if [ "$got" != "$want" ]; then
        rm -f "$dest.tmp"
        echo "error: sha256 mismatch for $url" >&2
        echo "  expected $want" >&2
        echo "  got      $got" >&2
        exit 1
    fi
    mv "$dest.tmp" "$dest"
}

# --- uv --------------------------------------------------------------------

echo "uv $UV_VERSION"
uv_tar="$cache/uv-$UV_VERSION-$TARGET_TRIPLE.tar.gz"
fetch "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$TARGET_TRIPLE.tar.gz" \
      "$UV_SHA256" "$uv_tar"

rm -rf "$cache/uv-x" && mkdir -p "$cache/uv-x"
tar xzf "$uv_tar" -C "$cache/uv-x"
# Tauri's sidecar convention: the file on disk carries the target triple and
# the bundler drops it into Contents/MacOS/ under the bare name.
install -m 0755 "$cache/uv-x/uv-$TARGET_TRIPLE/uv" "$binaries/uv-$TARGET_TRIPLE"
# `uvx` is uv's tool-runner alias — enough never invokes it, so it stays out.
say "installed binaries/uv-$TARGET_TRIPLE ($("$binaries/uv-$TARGET_TRIPLE" --version))"

# uv's release tarball carries no license text; take it from the tag.
for lic in LICENSE-APACHE LICENSE-MIT; do
    curl -fsSL --retry 3 \
        -o "$binaries/uv-$lic" \
        "https://raw.githubusercontent.com/astral-sh/uv/$UV_VERSION/$lic"
done
say "installed binaries/uv-LICENSE-{APACHE,MIT}"

# --- llama.cpp -------------------------------------------------------------

echo "llama.cpp $LLAMA_RELEASE"
llama_tar="$cache/llama-$LLAMA_RELEASE-bin-macos-arm64.tar.gz"
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_RELEASE/llama-$LLAMA_RELEASE-bin-macos-arm64.tar.gz" \
      "$LLAMA_SHA256" "$llama_tar"

rm -rf "$cache/llama-x" && mkdir -p "$cache/llama-x"
tar xzf "$llama_tar" -C "$cache/llama-x"
src="$cache/llama-x/llama-$LLAMA_RELEASE"

# The release archive is ~26 MB of every llama.cpp tool. We want llama-server
# and nothing else, so walk its @rpath closure and copy only that. The names
# in the archive are symlinks into versioned files; `install` dereferences,
# which keeps the bundle free of symlinks that codesign and the DMG would
# otherwise have to carry.
#
# llama-server's only LC_RPATH is `@loader_path`, so the dylibs MUST sit in
# the same directory as the binary. That is why llama-server is a Resources
# directory rather than a Tauri externalBin: sidecars land in Contents/MacOS
# and resources land in Contents/Resources, and splitting the two would break
# the rpath. DYLD_* env vars are not an option — the hardened runtime strips
# them from a signed process.
rm -f "$llamadir"/*.dylib "$llamadir/llama-server"
python3 - "$src" "$llamadir" <<'PY'
import os, subprocess, sys, shutil

src, dst = sys.argv[1], sys.argv[2]
need, queue = [], ["llama-server"]
while queue:
    name = queue.pop(0)
    if name in need:
        continue
    need.append(name)
    out = subprocess.check_output(["otool", "-L", os.path.join(src, name)], text=True)
    for line in out.splitlines()[1:]:
        dep = line.strip().split(" ")[0]
        if dep.startswith("@rpath/"):
            queue.append(dep.rsplit("/", 1)[-1])

total = 0
for name in need:
    s = os.path.realpath(os.path.join(src, name))
    d = os.path.join(dst, name)
    shutil.copyfile(s, d)
    os.chmod(d, 0o755)
    total += os.path.getsize(d)
print(f"  copied  {len(need)} mach-o files, {total/1e6:.1f} MB")
PY

cp "$src/LICENSE" "$llamadir/LICENSE-llama.cpp"

have="$("$llamadir/llama-server" --version 2>&1 | sed -n 's/^version: \([0-9]*\).*/\1/p' | head -1)"
if [ -z "$have" ]; then
    echo "error: bundled llama-server did not report a version" >&2
    exit 1
fi
if [ "$have" -lt "$LLAMA_MIN_REQUIRED" ]; then
    echo "error: bundled llama.cpp is b$have, registry needs >= b$LLAMA_MIN_REQUIRED" >&2
    exit 1
fi
say "installed vendor/llama/llama-server (b$have >= b$LLAMA_MIN_REQUIRED)"

echo
echo "sidecars ready. next: cargo tauri build  (from desktop/src-tauri)"
