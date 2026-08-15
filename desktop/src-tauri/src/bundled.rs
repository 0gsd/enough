//! What the .app carries inside itself (tauri-plan §4): the `uv` sidecar, the
//! `llama-server` sidecar, and the enough source snapshot.
//!
//! ```text
//! enough.app/Contents/
//!   MacOS/enough                  ← us
//!   MacOS/uv                      ← externalBin sidecar
//!   Resources/llama/llama-server  ← + its 10 dylibs, same directory
//!   Resources/enough-src/         ← pyproject + uv.lock + enough/ + defaults/
//! ```
//!
//! Everything is derived from `current_exe()` rather than Tauri's
//! `PathResolver`, so the same code answers correctly in a `cargo run` build
//! (where none of it exists and every field is `None`) without an AppHandle
//! to thread through `backend.rs`.
//!
//! `llama-server`'s only `LC_RPATH` is `@loader_path`, which is why it is a
//! Resources *directory* rather than a second `externalBin`: sidecars land in
//! `Contents/MacOS` and resources in `Contents/Resources`, and separating the
//! binary from its dylibs would break the rpath. `DYLD_LIBRARY_PATH` is not a
//! way out — the hardened runtime strips `DYLD_*` from a signed process.

use std::path::{Path, PathBuf};

#[derive(Debug, Default, Clone)]
pub struct Bundled {
    /// `Contents/MacOS/uv`
    pub uv: Option<PathBuf>,
    /// `Contents/Resources/llama/llama-server`
    pub llama_server: Option<PathBuf>,
    /// `Contents/Resources/enough-src` — the source snapshot.
    pub code: Option<PathBuf>,
}

impl Bundled {
    /// True when we're running from a real .app with its payload intact.
    pub fn is_complete(&self) -> bool {
        self.uv.is_some() && self.llama_server.is_some() && self.code.is_some()
    }
}

fn file_if_exists(p: PathBuf) -> Option<PathBuf> {
    p.is_file().then_some(p)
}

/// Find the bundle payload. Cheap (three `stat`s); call it wherever.
pub fn locate() -> Bundled {
    let exe = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return Bundled::default(),
    };
    // Resolve symlinks: `/Applications/enough.app` reached through one would
    // otherwise put Resources somewhere that doesn't exist.
    let exe = std::fs::canonicalize(&exe).unwrap_or(exe);
    let macos_dir = match exe.parent() {
        Some(d) => d,
        None => return Bundled::default(),
    };
    let resources = macos_dir.join("../Resources");

    Bundled {
        uv: file_if_exists(macos_dir.join("uv")),
        llama_server: file_if_exists(resources.join("llama/llama-server")),
        code: {
            let root = resources.join("enough-src");
            root.join("pyproject.toml").is_file().then_some(root)
        },
    }
}

/// The version stamp `build.rs` wrote next to the snapshot, for the log.
pub fn snapshot_stamp(code: &Path) -> String {
    std::fs::read_to_string(code.join(".snapshot-version"))
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "unknown".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_dev_build_has_no_payload() {
        // `cargo test` runs from target/debug/deps — nothing bundled there,
        // and the fallbacks in backend.rs are what must kick in.
        let b = locate();
        assert!(!b.is_complete());
    }

    #[test]
    fn missing_pieces_are_none_not_bogus_paths() {
        let b = Bundled::default();
        assert!(b.uv.is_none() && b.llama_server.is_none() && b.code.is_none());
        assert!(!b.is_complete());
    }
}
