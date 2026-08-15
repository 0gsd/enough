//! Pre-flight checks the shell runs on a chosen folder, so a folder the
//! backend can't (or shouldn't) serve produces a friendly native dialog
//! instead of a window that never loads.
//!
//! Both checks mirror Python that already exists. They are duplicated here
//! rather than shelled out to because `uv run` costs hundreds of ms and the
//! picker should feel instant; the rule in each case is a handful of literal
//! path prefixes that have not changed in the life of the project. If you
//! touch either upstream, touch these:
//!
//!   * [`cloud_sync_provider`]  ← `enough/skeleton.py::cloud_sync_provider`
//!   * [`inside_install_dir`]   ← `enough/__main__.py::main` (the ~/enough refusal)
//!
//! The backend's own guards still run — this is a nicer front door, never a
//! replacement. Anything these miss is caught by [`crate::backend`] noticing
//! the child exited and surfacing its stderr.

use std::path::Path;

/// Human label for the cloud-sync service hosting `path`, or `None`.
///
/// Note the asymmetry with the Python: `skeleton.cloud_sync_provider` feeds a
/// non-blocking in-UI *warning*, not a refusal, so the shell asks rather than
/// refuses too (see `launch.rs`).
pub fn cloud_sync_provider(path: &Path) -> Option<&'static str> {
    let s = path.to_string_lossy().to_lowercase();
    // macOS File-Provider mounts (Drive for Desktop, Dropbox, OneDrive, …).
    if s.contains("/library/cloudstorage/googledrive") {
        return Some("Google Drive");
    }
    if s.contains("/library/cloudstorage/dropbox") {
        return Some("Dropbox");
    }
    if s.contains("/library/cloudstorage/onedrive") {
        return Some("OneDrive");
    }
    if s.contains("/library/cloudstorage/icloud") {
        return Some("iCloud Drive");
    }
    if s.contains("/library/cloudstorage/") {
        return Some("a cloud-synced folder");
    }
    // iCloud Drive's on-disk location, plus legacy non-File-Provider roots.
    if s.contains("/library/mobile documents/com~apple~clouddocs") {
        return Some("iCloud Drive");
    }
    if s.contains("/google drive/") || s.contains("/googledrive-") {
        return Some("Google Drive");
    }
    if s.contains("/dropbox/") {
        return Some("Dropbox");
    }
    None
}

/// True when `path` is `~/enough` or anywhere beneath it. The backend hard-
/// refuses these (an `rness/` there would collide with the global defaults).
pub fn inside_install_dir(path: &Path, install_root: &Path) -> bool {
    let p = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    let root = install_root
        .canonicalize()
        .unwrap_or_else(|_| install_root.to_path_buf());
    p.starts_with(&root)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn spots_the_file_provider_mounts() {
        let cases = [
            ("/Users/x/Library/CloudStorage/GoogleDrive-a@b.com/My Drive/p", "Google Drive"),
            ("/Users/x/Library/CloudStorage/Dropbox/p", "Dropbox"),
            ("/Users/x/Library/CloudStorage/OneDrive-Personal/p", "OneDrive"),
            ("/Users/x/Library/CloudStorage/iCloud Drive/p", "iCloud Drive"),
            ("/Users/x/Library/CloudStorage/Box-Box/p", "a cloud-synced folder"),
            ("/Users/x/Library/Mobile Documents/com~apple~CloudDocs/p", "iCloud Drive"),
            ("/Users/x/Dropbox/p", "Dropbox"),
        ];
        for (path, want) in cases {
            assert_eq!(cloud_sync_provider(&PathBuf::from(path)), Some(want), "{path}");
        }
    }

    #[test]
    fn leaves_ordinary_paths_alone() {
        assert_eq!(cloud_sync_provider(&PathBuf::from("/Users/x/projects/book")), None);
        assert_eq!(cloud_sync_provider(&PathBuf::from("/tmp/scratch")), None);
    }

    #[test]
    fn install_dir_check_covers_the_root_and_below() {
        let root = PathBuf::from("/Users/x/enough");
        assert!(inside_install_dir(&PathBuf::from("/Users/x/enough"), &root));
        assert!(inside_install_dir(&PathBuf::from("/Users/x/enough/defaults"), &root));
        assert!(!inside_install_dir(&PathBuf::from("/Users/x/enough-dev"), &root));
        assert!(!inside_install_dir(&PathBuf::from("/Users/x/projects"), &root));
    }
}
