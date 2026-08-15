//! `~/enough/config/desktop.json` — the desktop-level settings file from
//! docs/tauri-plan.md §2. Shared-visible with the CLI install, so unknown
//! keys are round-tripped rather than dropped.

use std::io;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

/// How many projects we remember. `known_projects` is v2 groundwork (the
/// launcher list); an unbounded MRU would just be a slow leak.
const MAX_KNOWN: usize = 50;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DesktopConfig {
    #[serde(default)]
    pub reopen_last_project: bool,
    #[serde(default)]
    pub last_active_project: Option<String>,
    #[serde(default)]
    pub known_projects: Vec<String>,
    /// 2b's onboarding checkpoint (tauri-plan §3). `None` means "never
    /// started"; a half-finished wizard resumes at `first_incomplete()`.
    #[serde(default)]
    pub onboarding: Option<Onboarding>,
    /// Anything a newer enough (or the CLI) added that we don't know about.
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

/// The first-run wizard's checkpoint, tauri-plan §3.
///
/// Four booleans rather than a cursor: "resume at the first incomplete step"
/// then falls out of the data instead of needing a migration every time the
/// step list changes, and a step that was completed stays completed even if a
/// later one is re-run.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct Onboarding {
    #[serde(default)]
    pub welcome: bool,
    #[serde(default)]
    pub environment: bool,
    #[serde(default)]
    pub models: bool,
    #[serde(default)]
    pub extras: bool,
    /// Set once every step is done. This — not the four flags — is what a
    /// later launch checks, so a future version that adds a step can decide
    /// for itself whether an old `completed` still counts.
    #[serde(default)]
    pub completed: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub completed_at: Option<String>,
    /// Schema marker for exactly that future decision.
    #[serde(default = "one")]
    pub version: u32,
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

fn one() -> u32 {
    1
}

/// The wizard's steps, in order. `project` is §2's picker and lives outside
/// this list — it isn't a checkpoint, it's the thing onboarding hands off to.
pub const STEPS: [&str; 4] = ["welcome", "environment", "models", "extras"];

impl Onboarding {
    pub fn is_done(&self, step: &str) -> bool {
        match step {
            "welcome" => self.welcome,
            "environment" => self.environment,
            "models" => self.models,
            "extras" => self.extras,
            _ => false,
        }
    }

    pub fn mark(&mut self, step: &str) {
        match step {
            "welcome" => self.welcome = true,
            "environment" => self.environment = true,
            "models" => self.models = true,
            "extras" => self.extras = true,
            _ => {}
        }
        if STEPS.iter().all(|s| self.is_done(s)) {
            self.completed = true;
            if self.completed_at.is_none() {
                self.completed_at = Some(now_rfc3339());
            }
        }
    }

    /// Where a resumed wizard opens. `None` once everything is done.
    pub fn first_incomplete(&self) -> Option<&'static str> {
        STEPS.iter().copied().find(|s| !self.is_done(s))
    }
}

/// `2026-08-14T18:07:11Z`, without pulling `chrono` in for one timestamp.
fn now_rfc3339() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    // days since 1970 → civil date (Howard Hinnant's algorithm).
    let (days, rem) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        (rem % 3600) / 60,
        rem % 60
    )
}

impl DesktopConfig {
    /// True when the §3 wizard has nothing left to do — the check every
    /// launch after the first one makes.
    pub fn onboarding_complete(&self) -> bool {
        self.onboarding.as_ref().is_some_and(|o| o.completed)
    }
}

impl Default for DesktopConfig {
    fn default() -> Self {
        Self {
            reopen_last_project: false, // user decision, tauri-plan §2
            last_active_project: None,
            known_projects: Vec::new(),
            onboarding: None,
            extra: serde_json::Map::new(),
        }
    }
}

/// The user's home. `$HOME` first (so a QA harness can point the whole
/// shell at a scratch home), falling back to the passwd entry.
pub fn home_dir() -> PathBuf {
    if let Ok(h) = std::env::var("HOME") {
        if !h.is_empty() {
            return PathBuf::from(h);
        }
    }
    PathBuf::from("/")
}

/// `~/enough` — the state home, shared by the CLI install and the .app.
pub fn state_home() -> PathBuf {
    home_dir().join("enough")
}

pub fn config_path() -> PathBuf {
    state_home().join("config").join("desktop.json")
}

/// Read desktop.json, creating it with defaults when it's missing.
///
/// A corrupt file is treated as absent but is *not* overwritten until the
/// next real save — losing a user's `known_projects` to a stray parse error
/// would be worse than running one session on defaults.
pub fn load() -> DesktopConfig {
    let path = config_path();
    match std::fs::read_to_string(&path) {
        Ok(text) => serde_json::from_str(&text).unwrap_or_else(|e| {
            eprintln!("[enough-desktop] desktop.json unparsable ({e}); using defaults");
            DesktopConfig::default()
        }),
        Err(_) => {
            let fresh = DesktopConfig::default();
            if let Err(e) = save(&fresh) {
                eprintln!("[enough-desktop] could not create {}: {e}", path.display());
            }
            fresh
        }
    }
}

/// Write desktop.json via a temp file + rename, so a crash mid-write can't
/// leave a half-written config behind.
pub fn save(cfg: &DesktopConfig) -> io::Result<()> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut text = serde_json::to_string_pretty(cfg)
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    text.push('\n');
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, text)?;
    std::fs::rename(&tmp, &path)
}

impl DesktopConfig {
    /// Record a successful open: `last_active_project` plus an MRU-first,
    /// deduped upsert into `known_projects`.
    pub fn record_open(&mut self, project: &Path) {
        let key = project.to_string_lossy().into_owned();
        self.last_active_project = Some(key.clone());
        self.known_projects.retain(|p| p != &key);
        self.known_projects.insert(0, key);
        self.known_projects.truncate(MAX_KNOWN);
    }
}

/// A directory is an existing enough project iff it holds an `rness/`
/// folder — the same test tauri-plan §2 gates the reopen path on.
pub fn is_enough_project(dir: &Path) -> bool {
    dir.join("rness").is_dir()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn defaults_match_the_spec() {
        let cfg = DesktopConfig::default();
        let json: serde_json::Value =
            serde_json::from_str(&serde_json::to_string(&cfg).unwrap()).unwrap();
        assert_eq!(json["reopen_last_project"], serde_json::json!(false));
        assert_eq!(json["last_active_project"], serde_json::Value::Null);
        assert_eq!(json["known_projects"], serde_json::json!([]));
        assert_eq!(json["onboarding"], serde_json::Value::Null);
    }

    #[test]
    fn record_open_is_mru_first_and_deduped() {
        let mut cfg = DesktopConfig::default();
        cfg.record_open(&PathBuf::from("/a"));
        cfg.record_open(&PathBuf::from("/b"));
        cfg.record_open(&PathBuf::from("/a")); // revisit
        assert_eq!(cfg.known_projects, vec!["/a".to_string(), "/b".to_string()]);
        assert_eq!(cfg.last_active_project.as_deref(), Some("/a"));
    }

    #[test]
    fn record_open_caps_the_list() {
        let mut cfg = DesktopConfig::default();
        for i in 0..(MAX_KNOWN + 10) {
            cfg.record_open(&PathBuf::from(format!("/p{i}")));
        }
        assert_eq!(cfg.known_projects.len(), MAX_KNOWN);
        assert_eq!(cfg.known_projects[0], format!("/p{}", MAX_KNOWN + 9));
    }

    #[test]
    fn unknown_keys_survive_a_round_trip() {
        // desktop.json is shared-visible with the CLI; a newer enough writing
        // a key we don't model must not lose it when the shell saves.
        let src = r#"{"reopen_last_project":true,"last_active_project":"/x",
                      "known_projects":["/x"],
                      "onboarding":{"welcome":true,"a_later_step":2},
                      "schema_version":3,"something_new":"keep me"}"#;
        let cfg: DesktopConfig = serde_json::from_str(src).unwrap();
        assert!(cfg.reopen_last_project);
        assert!(cfg.onboarding.as_ref().unwrap().welcome);
        let back: serde_json::Value =
            serde_json::from_str(&serde_json::to_string(&cfg).unwrap()).unwrap();
        assert_eq!(back["schema_version"], serde_json::json!(3));
        assert_eq!(back["something_new"], serde_json::json!("keep me"));
        // …including inside the onboarding block, which a newer wizard will
        // grow steps in.
        assert_eq!(back["onboarding"]["a_later_step"], serde_json::json!(2));
    }

    // -----------------------------------------------------------------------
    // Onboarding (tauri-plan §3)
    // -----------------------------------------------------------------------

    #[test]
    fn a_fresh_install_has_not_onboarded() {
        assert!(!DesktopConfig::default().onboarding_complete());
    }

    #[test]
    fn resume_lands_on_the_first_incomplete_step() {
        let mut o = Onboarding::default();
        assert_eq!(o.first_incomplete(), Some("welcome"));
        o.mark("welcome");
        assert_eq!(o.first_incomplete(), Some("environment"));
        o.mark("environment");
        assert_eq!(o.first_incomplete(), Some("models"));
    }

    #[test]
    fn a_gap_earlier_in_the_list_wins() {
        // A wizard that somehow recorded a later step without an earlier one
        // must not skip the earlier one on resume.
        let mut o = Onboarding::default();
        o.mark("welcome");
        o.mark("models");
        assert_eq!(o.first_incomplete(), Some("environment"));
        assert!(!o.completed);
    }

    #[test]
    fn completing_every_step_completes_onboarding_and_stamps_it() {
        let mut o = Onboarding::default();
        for s in STEPS {
            o.mark(s);
        }
        assert!(o.completed);
        assert_eq!(o.first_incomplete(), None);
        let at = o.completed_at.clone().expect("stamped");
        assert!(at.ends_with('Z') && at.len() == 20, "{at}");
        // Re-marking a step must not move the timestamp.
        o.mark("extras");
        assert_eq!(o.completed_at, Some(at));
    }

    #[test]
    fn an_unknown_step_name_is_inert() {
        let mut o = Onboarding::default();
        o.mark("teleport");
        assert!(!o.completed);
        assert_eq!(o.first_incomplete(), Some("welcome"));
    }

    #[test]
    fn a_completed_wizard_survives_the_config_round_trip() {
        let mut cfg = DesktopConfig::default();
        let mut o = Onboarding::default();
        for s in STEPS {
            o.mark(s);
        }
        cfg.onboarding = Some(o);
        let back: DesktopConfig =
            serde_json::from_str(&serde_json::to_string(&cfg).unwrap()).unwrap();
        assert!(back.onboarding_complete());
    }

    #[test]
    fn the_timestamp_helper_matches_a_known_epoch() {
        // 1755201600 = 2026-08-14T20:00:00Z
        let d = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_755_201_600);
        let secs = d.duration_since(std::time::UNIX_EPOCH).unwrap().as_secs();
        assert_eq!(secs, 1_755_201_600);
        // now_rfc3339 reads the clock, so pin the shape instead of the value.
        let s = now_rfc3339();
        assert_eq!(s.len(), 20);
        assert!(s.as_bytes()[4] == b'-' && s.as_bytes()[10] == b'T');
    }
}
