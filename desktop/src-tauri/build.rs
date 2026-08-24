//! Tauri codegen, plus the 2b source snapshot.
//!
//! tauri-plan §1: the .app runs the enough source from inside its own bundle,
//! not from `~/enough`. That source has to get into `Contents/Resources` at
//! build time and it has to TRACK THE REPO — a snapshot copied by hand would
//! be wrong the first time anyone edited a .py and forgot.
//!
//! So: `cargo build` stages the tree into `snapshot/enough-src/` (gitignored),
//! and `tauri.conf.json`'s `bundle.resources` copies that into the .app. The
//! `cargo:rerun-if-changed` lines below are what makes it track — cargo walks
//! those paths recursively and re-runs this script when any file under them
//! changes.
//!
//! The same mechanism, in miniature, gives the shell's own loading screen
//! the real loader graphic: `ui/loading.html` shows the mascot-and-wordmark
//! SVG that `enough/static/loader.html` shows, staged here into `ui/`
//! (gitignored) from its one home in the package, rather than committed
//! twice. `ui/` is `frontendDist`, so whatever is in it at compile time is
//! embedded in the binary and served at `tauri://localhost/`.

use std::fs;
use std::path::{Path, PathBuf};

/// Everything the bundled backend needs to run, relative to the repo root.
///
/// - `pyproject.toml` + `uv.lock` — what `uv run --project` resolves against.
/// - `README.md` + `LICENSE` — pyproject's `readme` and `license-files`; the
///   wheel build fails without them, so they are not optional niceties.
/// - `enough/` — the package (static/ included; it's the UI).
/// - `defaults/` — skills, roles, paradigms, policies, models.json. Read at
///   runtime via `skeleton._install_defaults_root()`, which is
///   `<the package's parent>/defaults` — i.e. this snapshot, once the app is
///   running from it.
/// - `THIRD_PARTY_LICENSES.md` — the bundled defaults/skills carry their own
///   licenses and shipping them without it would be wrong.
/// - `docs/HELP_CENTER.md` — the in-app help center reads it from
///   `<package parent>/docs/` (server.py `api_help_center`), which is this
///   snapshot once the app runs from it. The single file, NOT `docs/` — the
///   dev tree keeps gitignored local planning docs there that must never
///   ship (0.2.8; before this the .app's help center 404'd).
const SNAPSHOT: &[&str] = &[
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_LICENSES.md",
    "docs/HELP_CENTER.md",
    "enough",
    "defaults",
];

/// Junk that must not travel: compiled bytecode (stale, and it would make the
/// signed bundle differ from the source it claims to be), Finder droppings,
/// and any venv/egg-info a dev checkout accumulated.
fn skip(name: &str) -> bool {
    matches!(name, "__pycache__" | ".DS_Store" | ".venv" | ".pytest_cache")
        || name.ends_with(".pyc")
        || name.ends_with(".egg-info")
}

fn copy_tree(src: &Path, dst: &Path) -> std::io::Result<()> {
    if src.is_dir() {
        fs::create_dir_all(dst)?;
        for entry in fs::read_dir(src)? {
            let entry = entry?;
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if skip(&name) {
                continue;
            }
            copy_tree(&entry.path(), &dst.join(&*name))?;
        }
    } else {
        if let Some(parent) = dst.parent() {
            fs::create_dir_all(parent)?;
        }
        // Copy rather than hardlink: the bundler will sign what it finds, and
        // a hardlink back into the working tree would let a later edit mutate
        // an already-signed bundle.
        fs::copy(src, dst)?;
    }
    Ok(())
}

fn stage_snapshot() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    // desktop/src-tauri → desktop → repo root
    let repo = manifest.parent().unwrap().parent().unwrap().to_path_buf();
    let out = manifest.join("snapshot").join("enough-src");

    // Rebuild from scratch every time. The tree is ~8 MB and a stale file
    // left behind by a rename is exactly the bug this whole mechanism exists
    // to prevent.
    let _ = fs::remove_dir_all(&out);

    for rel in SNAPSHOT {
        let src = repo.join(rel);
        println!("cargo:rerun-if-changed={}", src.display());
        if !src.exists() {
            panic!(
                "source snapshot is missing {} — expected it at {}",
                rel,
                src.display()
            );
        }
        copy_tree(&src, &out.join(rel)).unwrap_or_else(|e| {
            panic!("could not stage {} into the snapshot: {e}", rel);
        });
    }

    // A marker the shell can read back at runtime to log which snapshot it is
    // actually running — the single most useful line in a bug report from a
    // machine you can't see.
    let stamp = format!(
        "{}\n",
        std::env::var("CARGO_PKG_VERSION").unwrap_or_default()
    );
    let _ = fs::write(out.join(".snapshot-version"), stamp);
}

/// Static assets the shell's own pages (`ui/*.html`) need, relative to the
/// repo root, staged into `ui/` under the same basename. One home each.
const UI_ASSETS: &[&str] = &["enough/static/enough-loader_1-2.svg"];

fn stage_ui_assets() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let repo = manifest.parent().unwrap().parent().unwrap().to_path_buf();
    let ui = manifest.parent().unwrap().join("ui");

    for rel in UI_ASSETS {
        let src = repo.join(rel);
        println!("cargo:rerun-if-changed={}", src.display());
        if !src.is_file() {
            panic!("ui asset is missing {} — expected it at {}", rel, src.display());
        }
        let name = src.file_name().unwrap();
        fs::copy(&src, ui.join(name)).unwrap_or_else(|e| {
            panic!("could not stage {} into ui/: {e}", rel);
        });
    }
}

fn main() {
    stage_snapshot();
    stage_ui_assets();
    tauri_build::build()
}
