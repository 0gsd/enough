# Releasing enough.app — sign, notarize, staple, verify

This is a **user-executed** checklist. It needs a Developer ID certificate and
an App Store Connect key, and agents never handle either.

> **Credentials come from your shell environment and nowhere else.** Every
> value below is exported in your own interactive shell for the length of one
> release. Do not put any of them in a file in this repository, in a `.env`, in
> `tauri.conf.json`, in a CI variable, or in a shell rc file that syncs to
> another machine. `tauri.conf.json` deliberately carries
> `"signingIdentity": null` — that is the wiring: the bundler reads
> `APPLE_SIGNING_IDENTITY` from the environment when the field is null, so the
> repo never names your identity. The `.p8` key stays wherever you keep it,
> outside the repo, referenced by path.

Everything here is arm64-only (tauri-plan §4). One machine, one architecture.

**Version bumps touch five files in lockstep** — `pyproject.toml`,
`enough/__init__.py`, `desktop/src-tauri/tauri.conf.json`,
`desktop/src-tauri/Cargo.toml`, and the version string in `bootstrap.sh` —
so the UI badge, the bundle's Info.plist, and the DMG filename all agree.
`desktop/src-tauri/Cargo.lock` is the silent sixth: it records the crate's
own version and only updates when cargo next runs — so bump, **build**,
*then* commit, or the lockfile trails the release by one commit. The repo's
`uv.lock` is the silent seventh, for the same reason (it records `enough`'s
own version): run `uv lock` after the bump and expect exactly two changed
lines — the version, and the rolling `exclude-newer` timestamp.
Any bump (or any bundle change at all) means re-running §4 and §6: a new
Info.plist is a new bundle is a new signature is a new notarization.

---

## 0. Once per machine

- Xcode Command Line Tools: `xcode-select --install`
- **Developer ID Application** certificate in the login keychain. Check:
  ```sh
  security find-identity -v -p codesigning | grep "Developer ID Application"
  ```
  You need the full string in the quotes, e.g.
  `Developer ID Application: Jane Smith (AB12CD34EF)`.
- An **App Store Connect API key** for notarization: App Store Connect →
  Users and Access → Integrations → App Store Connect API → generate a key
  with the *Developer* role. You get a `.p8` (downloadable once), a Key ID,
  and an Issuer ID. Store the `.p8` outside this repo — `~/.appstoreconnect/`
  is a reasonable home; `chmod 600` it.

  (An Apple ID + app-specific password works too — `APPLE_ID`,
  `APPLE_PASSWORD`, `APPLE_TEAM_ID` — but the API key is revocable
  independently of your Apple ID, so prefer it.)

## 1. The release shell

Open a terminal and export these. Nothing persists them; close the window when
you're done.

```sh
export APPLE_SIGNING_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)"
export APPLE_API_KEY="YOUR_KEY_ID"            # the 10-char Key ID
export APPLE_API_ISSUER="00000000-0000-..."   # the Issuer UUID
export APPLE_API_KEY_PATH="$HOME/.appstoreconnect/AuthKey_YOUR_KEY_ID.p8"
export TEAMID="TEAMID"                        # convenience for the checks below

export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"
```

Sanity check that you did not fat-finger the identity — this must print one
line:

```sh
security find-identity -v -p codesigning | grep -F "$APPLE_SIGNING_IDENTITY"
```

**Do not set `CI=true` for a release build.** It makes the bundler pass
`--skip-jenkins` to `bundle_dmg.sh`, which skips the AppleScript that lays the
DMG window out (icon positions, the Applications drop target). That flag is for
headless/agent builds only.

## 2. Fetch the sidecars

```sh
cd desktop
./fetch-sidecars.sh
```

Checksum-pinned; it refuses on a mismatch. Current pins live at the top of that
script and are mirrored in `docs/tauri-plan.md` §4 — **uv 0.12.3**,
**llama.cpp b10362**.

## 3. Sign the llama.cpp payload — BEFORE building

**This step is not optional and the bundler will not do it for you.** Tauri
signs frameworks, `externalBin` sidecars (`Contents/MacOS/uv`) and the .app
itself. It does *not* walk `Contents/Resources/`, which is where
`llama-server` and its ten dylibs live (they must sit beside the binary: its
only `LC_RPATH` is `@loader_path`). Notarization rejects a bundle containing
an unsigned Mach-O, so signing them at the source — before `cargo tauri build`
copies them in — is the whole fix. Signatures survive the copy.

```sh
cd desktop/src-tauri
for f in vendor/llama/llama-server vendor/llama/*.dylib; do
  codesign --force --timestamp --options runtime \
           --sign "$APPLE_SIGNING_IDENTITY" "$f"
done
```

Verify before moving on — every line must show *your* Team ID:

```sh
for f in vendor/llama/llama-server vendor/llama/*.dylib; do
  printf '%-34s %s\n' "$(basename "$f")" \
    "$(codesign -dv "$f" 2>&1 | sed -n 's/^TeamIdentifier=//p')"
done
```

> **Why this matters, concretely.** `--options runtime` turns on library
> validation: a hardened process may only load libraries whose Team ID matches
> its own. Signing these with mismatched identities — or with an ad-hoc `-`
> identity, which has *no* Team ID — produces a `llama-server` that dies at
> launch with
> `code signature ... not valid for use in process: mapping process and mapped
> file (non-platform) have different Team IDs`.
> This was reproduced during 2b QA. Sign all eleven files with the **same**
> `$APPLE_SIGNING_IDENTITY`, in one pass, as above.

## 4. Build

```sh
cd desktop/src-tauri
cargo tauri build
```

The bundler signs `Contents/MacOS/uv` and then the .app (inside out, as Apple
requires), reads `entitlements.plist`, applies the hardened runtime, and —
because `APPLE_API_*` are exported — submits the result to `notarytool` and
staples it. Expect several minutes for notarization.

Outputs:

```
target/release/bundle/macos/enough.app
target/release/bundle/dmg/enough_<version>_aarch64.dmg
```

If notarization is not wanted in the same run, unset the `APPLE_API_*` trio;
the build then signs only, and §6 has the manual commands.

## 5. Verify the signature

```sh
cd target/release/bundle
APP=macos/enough.app

# 1. The bundle verifies, nested code included.
codesign --verify --deep --strict --verbose=2 "$APP"
#   expected: "$APP: valid on disk" / "satisfies its Designated Requirement"

# 2. Hardened runtime is on and the entitlements are the two we intend.
codesign -d --entitlements :- "$APP" 2>/dev/null
#   expected: com.apple.security.network.client and .network.server, true.
#   Anything else in that list is a mistake — see entitlements.plist.
codesign -dv "$APP" 2>&1 | grep flags
#   expected: flags=0x10000(runtime)   (0x2 'adhoc' must NOT appear)

# 3. Every Mach-O inside carries your Team ID — this is what notarization
#    checks, and the one that catches a forgotten §3.
find "$APP" -type f -perm +111 -o -name '*.dylib' | while read -r f; do
  file "$f" | grep -q Mach-O || continue
  printf '%-52s %s\n' "${f#$APP/}" \
    "$(codesign -dv "$f" 2>&1 | sed -n 's/^TeamIdentifier=//p')"
done
#   expected: $TEAMID on all of: Contents/MacOS/enough-desktop,
#   Contents/MacOS/uv, Contents/Resources/llama/llama-server, and the ten
#   Contents/Resources/llama/*.dylib. "not set" anywhere = go back to §3.
```

## 6. Notarize and staple manually (only if §4 didn't)

```sh
xcrun notarytool submit dmg/enough_*_aarch64.dmg \
  --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY" \
  --issuer "$APPLE_API_ISSUER" --wait
#   expected: status: Accepted

xcrun stapler staple dmg/enough_*_aarch64.dmg
xcrun stapler staple macos/enough.app
#   expected: "The staple and validate action worked!"
```

On `status: Invalid`, get the reasons — the log names every offending file:

```sh
xcrun notarytool log <submission-id> \
  --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY" --issuer "$APPLE_API_ISSUER"
```

## 7. Gatekeeper verification

```sh
spctl -a -vvv -t install macos/enough.app
#   expected:
#     macos/enough.app: accepted
#     source=Notarized Developer ID
#     origin=Developer ID Application: YOUR NAME (TEAMID)

spctl -a -vvv -t open --context context:primary-signature dmg/enough_*_aarch64.dmg
#   expected: accepted / source=Notarized Developer ID

xcrun stapler validate macos/enough.app
xcrun stapler validate dmg/enough_*_aarch64.dmg
```

`source=Unnotarized Developer ID` means the staple didn't take — redo §6.

## 8. The quarantine test — the one that reflects a real user

`spctl` passing is not the same as a double-click working. A DMG you built
locally has no quarantine bit; a downloaded one does, and that is the path
Gatekeeper actually gates.

```sh
xattr -w com.apple.quarantine \
  "0083;00000000;Safari;|org.enough.test" dmg/enough_*_aarch64.dmg
xattr -p com.apple.quarantine dmg/enough_*_aarch64.dmg   # confirm it's set
```

Then, **as a clean macOS user account** (System Settings → Users & Groups →
Add User; log in as them — a fresh account has no Homebrew on PATH, no
`~/enough`, and no developer tools, which is the whole point):

1. Copy the quarantined DMG to that user's Downloads.
2. Double-click it. Drag `enough.app` to Applications.
3. Launch from Applications. **Expected: it opens with no Gatekeeper prompt at
   all** — not "downloaded from the internet, are you sure", not "cannot be
   opened because the developer cannot be verified". A notarized, stapled app
   launches silently.
4. Walk the first-run wizard end to end: welcome → environment (uv builds the
   Python environment; a few minutes on first run) → models (pick the
   smallest ✓ model and let it download) → extras (a clean account should show
   every extra as missing, which is correct and must read as informative, not
   alarming) → **the home screen** (not the folder picker — 0.2.5 made home
   the front door) → add a folder from it → the enough UI, and a chat
   round-trip. Then ⌘W: **expected: back to the home screen**, with the
   project you just used listed on it.
5. Quit with ⌘Q. In *your* account: `pgrep -fl "llama-server|uvicorn"` should
   show nothing that the test account started.
6. Relaunch. **Expected: straight to the home screen, no wizard.**
7. App menu → "Reopen Last Project on Launch", quit, relaunch. **Expected:
   the project opens directly.**

Delete the test user when you're done.

## 9. Ship

The DMG in `target/release/bundle/dmg/` is the artifact. v1 updates are
"download the new DMG, replace the old .app" — there is no updater feed
(tauri-plan §4).

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| `The specified item could not be found in the keychain` | `APPLE_SIGNING_IDENTITY` doesn't match `security find-identity` output byte for byte. |
| notarytool `Invalid` → log says "not signed with a valid Developer ID" | §3 was skipped; the named files are in `Contents/Resources/llama/`. |
| App launches, model never loads, log shows *different Team IDs* | The llama payload was signed with a different identity than the app (or ad-hoc). Redo §3 with one identity and rebuild. |
| `"enough" is damaged and should be moved to the Trash` | A stapled bundle was modified after signing. Rebuild; do not edit anything inside the .app. |
| Wizard's environment step fails on a clean account | Network. uv downloads a managed CPython 3.13 and the dependency set on first run — by design (the app pins `UV_PYTHON_PREFERENCE=only-managed` so it never binds to a Homebrew interpreter). |
| DMG window has no layout | You set `CI=true`. See §1. |
| `cargo: command not found` | Fresh terminal without §1's `PATH` line — rustup is keg-only. Re-run the whole §1 export block; the identity/API exports are almost certainly missing too. |
| Build finishes with **no** "Signing with identity…" lines; §5 deep-verify says `code has no resources but signature indicates they must be present`; `TeamIdentifier=not set`, `flags=…adhoc,linker-signed` | `APPLE_SIGNING_IDENTITY` was empty in the build shell, so the bundler skipped signing *and* notarization and shipped the raw linker-signed binary. Re-run §1 in that terminal (`echo "[$APPLE_SIGNING_IDENTITY]"` must not be empty), then §4 again. |
| `bundle_dmg.sh` hangs for many minutes after "Notarizing… Accepted" | The layout AppleScript drives a Finder window it opens on the mounted DMG — **do not close that window**; it closes itself in ~10 s. Also hangs if a previous run's `rw.*.dmg` is still attached. Recovery: Ctrl-C, `hdiutil detach` every `rw.*.enough_*.dmg` volume (`hdiutil info` lists them), `rm target/release/bundle/macos/rw.*.dmg`, rerun §4. Guaranteed no-layout escape hatch: `CI=true cargo tauri build`. |
| First-run wizard / every launch prompts for the login keychain password ("python3.13 wants to access key enough-broker") | Pre-0.2.1 `cloud.has_api_key()` read the OpenRouter secret to answer a presence question, and the app's venv python is a different binary from the one that stored it. Fixed in 0.2.1 (metadata-only check). On an old build: enter the password and click **Always Allow** once. |
