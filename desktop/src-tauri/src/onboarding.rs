//! First-run onboarding — docs/tauri-plan.md §3.
//!
//! Five steps: welcome → environment → models → extras → project. The first
//! four live in `ui/onboarding.html`; the fifth *is* the §2 launch flow, which
//! this module hands control back to.
//!
//! **Implementer's choice: the wizard is a shell-served page, and its model
//! step drives the backend's existing `/api/models*` endpoints through a
//! four-command IPC proxy** (`ob_api`'s allowlist below).
//!
//! §3 offered two shapes. Serving the wizard from the backend would have been
//! same-origin and needed no proxy — but steps 1 and 2 run *before* there is
//! a backend (step 2 is `uv sync`; it is what makes one possible), so that
//! shape splits one wizard across two origins, two stylesheets and a
//! handshake back to Rust for the steps the backend can't own. This way the
//! wizard is one page with one stepper, `enough/static/index.html` is
//! untouched, and `enough/server.py` gains no route that exists only for the
//! desktop app. What gets reused is the model *manager* — registry,
//! feasibility verdicts, the download manager with its resume and disk
//! preflight, the `download` snapshot — which is where the work is; only the
//! seven rows' markup is re-rendered, in ~120 lines that owe nothing to
//! index.html's modal.
//!
//! The IPC surface it costs is scoped to the shell's own pages:
//! `capabilities/default.json` lists no `remote` origins, so once the window
//! navigates to `http://127.0.0.1:<port>` the enough UI can call none of it —
//! the 2a property, intact.
//!
//! **Implementer's choice: the model step runs a throwaway backend in a temp
//! project.** `/api/models` needs a live server and §3 puts the project
//! picker *after* the models step, so there is no project yet to run in. A
//! scratch dir under `$TMPDIR` gets the ordinary `rness/` skeleton (a few
//! hundred symlinks into the bundled defaults — cheap, and it exercises the
//! snapshot), serves the wizard, and is removed when onboarding completes.
//! Nothing the user picks later inherits from it.

use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Manager};

use crate::backend::{self, Backend};
use crate::config::{self, Onboarding};
use crate::AppState;

/// How long the wizard's own backend gets to come up.
const BOOT_TIMEOUT_HINT: &str = "the environment step must finish first";

/// The temp project the model step's backend runs in. Stable across restarts
/// so a resumed wizard reuses the skeleton it already built.
pub fn scratch_project() -> PathBuf {
    std::env::temp_dir().join("enough-onboarding")
}

// ---------------------------------------------------------------------------
// The blocking half: called from the launch thread
// ---------------------------------------------------------------------------

/// Show the wizard and block until it's finished (or the app is quitting).
///
/// Returns `true` when onboarding completed and the caller should carry on
/// into the §2 flow, `false` when we're shutting down instead.
pub fn run(app: &AppHandle) -> bool {
    let cfg = config::load();
    let ob = cfg.onboarding.clone().unwrap_or_default();
    eprintln!(
        "[enough-desktop] onboarding: resuming at {:?}",
        ob.first_incomplete()
    );

    let state = app.state::<Arc<AppState>>();
    state.onboarding_done.store(false, Ordering::SeqCst);

    if let Some(w) = app.get_webview_window("main") {
        if let Err(e) = w.navigate(
            tauri::Url::parse("tauri://localhost/onboarding.html")
                .unwrap_or_else(|_| unreachable!()),
        ) {
            eprintln!("[enough-desktop] couldn't open the wizard: {e}");
            // Fall back to the loading screen rather than a blank window; the
            // §2 picker still works, it just won't have been introduced.
            let _ = w.eval("location.replace('onboarding.html')");
        }
    }

    // The wizard runs on the webview; we just wait for it.
    loop {
        if state.onboarding_done.load(Ordering::SeqCst) {
            break;
        }
        if state.quitting.load(Ordering::SeqCst) {
            return false;
        }
        std::thread::sleep(Duration::from_millis(120));
    }

    stop_wizard_backend(app);
    let _ = std::fs::remove_dir_all(scratch_project());
    eprintln!("[enough-desktop] onboarding complete");
    true
}

/// Stop the wizard's throwaway backend, if one is running. Idempotent — the
/// quit path calls it too.
pub fn stop_wizard_backend(app: &AppHandle) {
    let state = app.state::<Arc<AppState>>();
    let taken = state.wizard_backend.lock().unwrap().take();
    if let Some(mut be) = taken {
        let how = be.shutdown();
        eprintln!("[enough-desktop] wizard backend stopped: {how}");
    }
}

// ---------------------------------------------------------------------------
// Wizard <-> shell plumbing
// ---------------------------------------------------------------------------

/// Push a line into a log pane on the wizard page. No IPC event surface, same
/// as 2a's loading screen: the page defines `__obLog` and we call it.
fn log_line(app: &AppHandle, pane: &str, text: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let js = format!(
            "window.__obLog&&window.__obLog({},{})",
            serde_json::to_string(pane).unwrap_or_else(|_| "\"\"".into()),
            serde_json::to_string(text).unwrap_or_else(|_| "\"\"".into()),
        );
        let _ = w.eval(&js);
    }
}

#[derive(Serialize)]
pub struct StateView {
    step: Option<&'static str>,
    steps: Vec<StepView>,
    /// Where the code we're about to run lives — shown on the welcome step so
    /// a bug report can say which snapshot it came from.
    code: String,
    snapshot: String,
    uv: String,
    llama_server: String,
    bundled: bool,
    /// True once the wizard's backend is serving.
    backend_ready: bool,
}

#[derive(Serialize)]
pub struct StepView {
    id: &'static str,
    done: bool,
}

fn view(app: &AppHandle) -> StateView {
    let home = config::home_dir();
    let ob = config::load().onboarding.unwrap_or_default();
    let b = crate::bundled::locate();
    let code = backend::code_root(&home);
    let backend_ready = {
        let state = app.state::<Arc<AppState>>();
        let ready = state.wizard_backend.lock().unwrap().is_some();
        ready
    };
    let bundled_complete = b.is_complete();
    StateView {
        step: ob.first_incomplete(),
        steps: config::STEPS
            .iter()
            .map(|id| StepView {
                id,
                done: ob.is_done(id),
            })
            .collect(),
        snapshot: crate::bundled::snapshot_stamp(&code),
        code: code.display().to_string(),
        uv: backend::find_uv(&home).map(|p| p.display().to_string()).unwrap_or_default(),
        llama_server: b
            .llama_server
            .map(|p| p.display().to_string())
            .unwrap_or_else(|| "(not bundled — PATH or ~/enough/bin)".into()),
        bundled: bundled_complete,
        backend_ready,
    }
}

fn save_step(step: &str) -> Result<Onboarding, String> {
    let mut cfg = config::load();
    let mut ob = cfg.onboarding.clone().unwrap_or_default();
    ob.mark(step);
    cfg.onboarding = Some(ob.clone());
    config::save(&cfg).map_err(|e| format!("couldn't write desktop.json: {e}"))?;
    Ok(ob)
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn ob_state(app: AppHandle) -> StateView {
    let v = view(&app);
    // The wizard calls this the moment its script runs, so the line doubles as
    // "the page loaded and its JS is talking to us" — the one thing a log from
    // a machine you can't see otherwise can't tell you.
    eprintln!(
        "[enough-desktop] wizard: step={:?} bundled={} backend={}",
        v.step, v.bundled, v.backend_ready
    );
    v
}

/// Step 2 — run `uv sync` against the code root with the bundled uv, streaming
/// uv's own output into the page. First network use: uv fetches a managed
/// CPython and the dependency set.
#[tauri::command]
pub async fn ob_env_sync(app: AppHandle) -> Result<String, String> {
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || env_sync_blocking(&handle))
        .await
        .map_err(|e| format!("environment step panicked: {e}"))?
}

fn env_sync_blocking(app: &AppHandle) -> Result<String, String> {
    use std::io::{BufRead, BufReader};
    use std::process::{Command, Stdio};

    let home = config::home_dir();
    let root = backend::code_root(&home);
    let uv = backend::find_uv(&home)?;
    if !root.join("pyproject.toml").is_file() {
        return Err(format!(
            "no enough source at {} — this app's bundle is incomplete.",
            root.display()
        ));
    }

    log_line(app, "env", &format!("uv: {}", uv.display()));
    log_line(app, "env", &format!("source: {}", root.display()));
    log_line(app, "env", &format!("venv: {}", backend::venv_dir(&home).display()));
    log_line(app, "env", "");

    let mut cmd = Command::new(&uv);
    cmd.arg("sync");
    if crate::bundled::locate().code.as_deref() == Some(root.as_path()) {
        cmd.arg("--frozen");
    }
    // `uv sync` is exact and would uninstall anything the lockfile's default
    // set doesn't name — including an optional extra the user installed from
    // the UI. Every sync path re-asks for the recorded ones; this is the
    // desktop's copy of that rule (convert-plan §6, gotcha 1).
    let extras = recorded_extras();
    if !extras.is_empty() {
        log_line(app, "env", &format!("keeping extras: {}", extras.join(", ")));
        for name in &extras {
            cmd.arg("--extra").arg(name);
        }
    }
    cmd.arg("--project")
        .arg(&root)
        .current_dir(std::env::temp_dir())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    backend::apply_child_env(&mut cmd, &home, &root);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("couldn't run {}: {e}", uv.display()))?;

    let mut threads = Vec::new();
    for pipe in [
        child.stdout.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        child.stderr.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let app = app.clone();
        threads.push(std::thread::spawn(move || {
            for line in BufReader::new(pipe).lines().map_while(Result::ok) {
                eprintln!("[uv] {line}");
                log_line(&app, "env", &line);
            }
        }));
    }

    let status = child.wait().map_err(|e| format!("uv sync: {e}"))?;
    for t in threads {
        let _ = t.join();
    }
    if !status.success() {
        return Err(format!(
            "uv sync failed ({status}). The log above has uv's own message — a \
             dropped network connection is the usual cause, and re-running \
             this step resumes from what it already fetched."
        ));
    }
    save_step("environment")?;
    Ok("ready".into())
}

/// `~/enough/config/extras.json`, or `$ENOUGH_EXTRAS_STATE` when it's set.
///
/// The env seam is honoured here as well as in the backend and
/// `update-enough.command` because "every `ENOUGH_*` points into the scratch
/// dir" is a QA rule with no exceptions — an install path that read the real
/// file anyway would sync the real venv from a scratch harness.
fn extras_state_path() -> PathBuf {
    if let Ok(p) = std::env::var("ENOUGH_EXTRAS_STATE") {
        if !p.is_empty() {
            return PathBuf::from(p);
        }
    }
    config::state_home().join("config").join("extras.json")
}

/// The optional dependency groups this install has, as `uv sync --extra`
/// names, sorted.
///
/// Names are validated rather than trusted. The file is plain JSON beside a
/// user-editable config and its keys end up in an argv, so anything that
/// doesn't look like an extra is dropped — the same `[a-z0-9][a-z0-9._-]*`
/// rule `update-enough.command` applies, which is what stops a key beginning
/// with `-` from arriving at uv as a flag.
fn recorded_extras() -> Vec<String> {
    let Ok(text) = std::fs::read_to_string(extras_state_path()) else {
        return Vec::new();
    };
    let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&text) else {
        return Vec::new();
    };
    let Some(map) = parsed.as_object() else {
        return Vec::new();
    };
    let mut names: Vec<String> = map.keys().filter(|n| is_extra_name(n)).cloned().collect();
    names.sort();
    names
}

fn is_extra_name(name: &str) -> bool {
    if name.is_empty() || name.len() > 64 {
        return false;
    }
    let mut chars = name.chars();
    matches!(chars.next(), Some(c) if c.is_ascii_lowercase() || c.is_ascii_digit())
        && chars.all(|c| {
            c.is_ascii_lowercase() || c.is_ascii_digit() || matches!(c, '.' | '_' | '-')
        })
}

/// Step 3a — bring up the throwaway backend the model picker talks to.
#[tauri::command]
pub async fn ob_models_boot(app: AppHandle) -> Result<(), String> {
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || boot_wizard_backend(&handle))
        .await
        .map_err(|e| format!("model step panicked: {e}"))?
}

fn boot_wizard_backend(app: &AppHandle) -> Result<(), String> {
    {
        let state = app.state::<Arc<AppState>>();
        if state.wizard_backend.lock().unwrap().is_some() {
            return Ok(());
        }
    }
    let home = config::home_dir();
    let project = scratch_project();
    std::fs::create_dir_all(&project)
        .map_err(|e| format!("couldn't create {}: {e}", project.display()))?;

    log_line(app, "models", "starting a temporary enough to fetch models…");
    let port = backend::choose_ui_port()?;
    let mut be = Backend::spawn(&project, &home, port)?;
    let app_for_progress = app.clone();
    if let Err(msg) = be.wait_ready(|m| log_line(&app_for_progress, "models", m)) {
        be.shutdown();
        return Err(format!("{msg}\n\n({BOOT_TIMEOUT_HINT}.)"));
    }
    log_line(app, "models", "ready");
    app.state::<Arc<AppState>>()
        .wizard_backend
        .lock()
        .unwrap()
        .replace(be);
    Ok(())
}

/// Step 3b — the proxy. Everything the model step does goes through here.
///
/// The allowlist is the point: this is a hole from a webview into an HTTP
/// client, and it should reach exactly the five shapes the model manager
/// needs and nothing else — not `/api/file`, not `/api/shutdown`.
#[tauri::command]
pub async fn ob_api(
    app: AppHandle,
    method: String,
    path: String,
    body: Option<String>,
) -> Result<serde_json::Value, String> {
    if !path_allowed(&method, &path) {
        return Err(format!("{method} {path} is not an onboarding endpoint"));
    }
    let (port, token) = {
        let state = app.state::<Arc<AppState>>();
        let guard = state.wizard_backend.lock().unwrap();
        match guard.as_ref() {
            Some(be) => (be.port, be.token.clone()),
            None => return Err("the model step's backend isn't running".into()),
        }
    };
    tauri::async_runtime::spawn_blocking(move || {
        let r = crate::http::request_body(
            port,
            &method,
            &path,
            &[("X-Enough-Desktop-Token", token.as_str())],
            body.as_deref(),
            Duration::from_secs(30),
        )
        .ok_or_else(|| format!("no answer from the backend for {method} {path}"))?;
        let json: serde_json::Value = serde_json::from_str(&r.body).unwrap_or_else(|_| {
            serde_json::json!({ "detail": r.body })
        });
        if r.status >= 400 {
            let detail = json
                .get("detail")
                .and_then(|d| d.as_str())
                .unwrap_or("request failed");
            return Err(detail.to_string());
        }
        Ok(json)
    })
    .await
    .map_err(|e| format!("proxy panicked: {e}"))?
}

fn path_allowed(method: &str, path: &str) -> bool {
    match method {
        "GET" => path == "/api/models",
        "POST" => {
            path == "/api/model"
                || (path.starts_with("/api/models/download/") && !path.contains(".."))
        }
        _ => false,
    }
}

/// Step 4 — what else this machine could have, and what it costs not to.
/// Pure lookup; §3 is explicit that v1 does not auto-install any of it.
#[tauri::command]
pub fn ob_extras() -> Vec<Extra> {
    let home = config::home_dir();
    vec![
        Extra::binary(
            "whisper", "whisper-cli", "Voice input",
            "The mic button in the chat box records but can't transcribe.",
            "brew install whisper-cpp",
            &home,
        ),
        // No pandoc row: `pypandoc-binary` is a base dependency now, so every
        // install has pandoc in its venv and a Homebrew one is an
        // optimisation rather than an extra (convert-plan §8).
        Extra::python_extra(
            "pdf", "PDF reading",
            "PDFs, PowerPoint decks and Excel workbooks stay unreadable — \
             everything else converts to an editable markdown twin.",
            "install from the UI window → extras after setup, or ask the agent",
            &home,
        ),
        Extra::binary(
            "tor", "tor", "Off-allowlist fetches",
            "The broker can still fetch allowlisted sites; anonymized \
             off-allowlist fetches are unavailable.",
            "brew install tor",
            &home,
        ),
        Extra::binary(
            "harper", "harper-cli", "Proofreading",
            "The analyzer's proofread mode falls back to LLM-only scanning.",
            "brew install harper",
            &home,
        ),
        Extra::directory(
            "translator",
            home.join(".local/share/translator/madlad400-3b-ct2"),
            "Offline translation",
            "The translator skill has no local model to run.",
            "the translator skill downloads it on first use",
        ),
    ]
}

#[derive(Serialize)]
pub struct Extra {
    id: &'static str,
    label: &'static str,
    /// One line of "what you lose without it", per §3.4.
    lose: &'static str,
    how: &'static str,
    found: bool,
    where_: String,
}

impl Extra {
    fn binary(
        id: &'static str,
        bin: &str,
        label: &'static str,
        lose: &'static str,
        how: &'static str,
        home: &Path,
    ) -> Extra {
        let found = backend::which_for_child(home, bin);
        Extra {
            id,
            label,
            lose,
            how,
            found: found.is_some(),
            where_: found.map(|p| p.display().to_string()).unwrap_or_default(),
        }
    }

    /// An optional Python dependency group, installed by uv rather than by a
    /// package manager. There is no binary on PATH to look for — the packages
    /// live inside `~/enough/.venv-desktop` — so `found` reads the same
    /// `extras.json` every `uv sync` path re-asks for, which is also the only
    /// record that survives an update.
    fn python_extra(
        id: &'static str,
        label: &'static str,
        lose: &'static str,
        how: &'static str,
        home: &Path,
    ) -> Extra {
        let found = recorded_extras().iter().any(|n| n == id);
        Extra {
            id,
            label,
            lose,
            how,
            found,
            where_: if found {
                backend::venv_dir(home).display().to_string()
            } else {
                String::new()
            },
        }
    }

    fn directory(
        id: &'static str,
        dir: PathBuf,
        label: &'static str,
        lose: &'static str,
        how: &'static str,
    ) -> Extra {
        Extra {
            id,
            label,
            lose,
            how,
            found: dir.is_dir(),
            where_: dir.display().to_string(),
        }
    }
}

/// Mark a step finished. `"extras"` is the last one, which completes
/// onboarding and releases the launch thread into the §2 picker.
#[tauri::command]
pub fn ob_advance(app: AppHandle, step: String) -> Result<StateView, String> {
    let ob = save_step(&step)?;
    eprintln!("[enough-desktop] onboarding: {step} done");
    if ob.completed {
        app.state::<Arc<AppState>>()
            .onboarding_done
            .store(true, Ordering::SeqCst);
    }
    Ok(view(&app))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_proxy_allowlist_is_the_model_manager_and_nothing_else() {
        assert!(path_allowed("GET", "/api/models"));
        assert!(path_allowed("POST", "/api/model"));
        assert!(path_allowed("POST", "/api/models/download/g40-12"));
        assert!(path_allowed("POST", "/api/models/download/g40-12/cancel"));

        // The endpoints a wizard has no business reaching.
        assert!(!path_allowed("POST", "/api/shutdown"));
        assert!(!path_allowed("POST", "/api/file"));
        assert!(!path_allowed("GET", "/api/project"));
        assert!(!path_allowed("DELETE", "/api/models/download/x"));
        // Deletion is not an onboarding action; the in-app picker owns it.
        assert!(!path_allowed("POST", "/api/models/delete/g40-12"));
        // No traversal out of the download namespace.
        assert!(!path_allowed("POST", "/api/models/download/../../shutdown"));
        // GET is exact, not a prefix.
        assert!(!path_allowed("GET", "/api/models/download/x"));
    }

    #[test]
    fn only_things_shaped_like_an_extra_can_reach_uvs_argv() {
        assert!(is_extra_name("pdf"));
        assert!(is_extra_name("ocr-fast"));
        assert!(is_extra_name("x2.1_b"));

        // A key that would arrive at uv as a flag, or as a second argument.
        assert!(!is_extra_name("-extra"));
        assert!(!is_extra_name("--frozen"));
        assert!(!is_extra_name("pdf extra"));
        assert!(!is_extra_name("pdf;rm -rf /"));
        assert!(!is_extra_name("PDF"));
        assert!(!is_extra_name(""));
        assert!(!is_extra_name(&"p".repeat(65)));
    }

    #[test]
    fn a_missing_or_broken_extras_file_reads_as_no_extras() {
        // The reader is best-effort by design: an unreadable extras.json must
        // degrade to "sync the base set", never to a failed launch.
        let dir = std::env::temp_dir().join(format!("enough-extras-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("extras.json");
        std::env::set_var("ENOUGH_EXTRAS_STATE", &path);

        assert!(recorded_extras().is_empty(), "absent file");

        std::fs::write(&path, "{ not json").unwrap();
        assert!(recorded_extras().is_empty(), "malformed file");

        std::fs::write(&path, "[\"pdf\"]").unwrap();
        assert!(recorded_extras().is_empty(), "top level is not an object");

        std::fs::write(&path, r#"{"pdf": {"installed_at": "x"}, "--bad": {}}"#).unwrap();
        assert_eq!(recorded_extras(), vec!["pdf".to_string()]);

        std::env::remove_var("ENOUGH_EXTRAS_STATE");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn the_scratch_project_is_not_in_the_state_home() {
        let p = scratch_project();
        assert!(p.is_absolute());
        assert!(!p.starts_with(config::state_home()));
    }
}
