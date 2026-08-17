//! The launch flow from docs/tauri-plan.md §2, start to finish.
//!
//! Runs on its own thread (the native folder picker must not block the main
//! one) and ends in exactly one of three states: the window navigated to a
//! live backend, the user cancelled the picker and the app exited, or a
//! dialog explained what went wrong and we looped back to the picker.

use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

use crate::backend::{self, Backend};
use crate::config::{self, DesktopConfig};
use crate::guards;
use crate::AppState;

/// Push a line into the loading screen's status slot.
fn status(app: &AppHandle, text: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let js = format!(
            "(function(){{var e=document.getElementById('status');if(e)e.textContent={};}})()",
            serde_json::to_string(text).unwrap_or_else(|_| "\"\"".into())
        );
        let _ = w.eval(&js);
    }
}

fn error_dialog(app: &AppHandle, title: &str, body: &str) {
    app.dialog()
        .message(body)
        .title(title)
        .kind(MessageDialogKind::Error)
        .blocking_show();
}

/// Ask a yes/no question. `true` = the affirmative (left) button.
fn confirm(app: &AppHandle, title: &str, body: &str, yes: &str, no: &str) -> bool {
    app.dialog()
        .message(body)
        .title(title)
        .kind(MessageDialogKind::Warning)
        .buttons(MessageDialogButtons::OkCancelCustom(
            yes.to_string(),
            no.to_string(),
        ))
        .blocking_show()
}

fn pick_folder(app: &AppHandle) -> Option<PathBuf> {
    app.dialog()
        .file()
        .set_title("Choose your project folder — enough works inside it (not an install location)")
        .blocking_pick_folder()
        .and_then(|p| p.into_path().ok())
}

/// Entry point for the launch thread.
pub fn run(app: AppHandle) {
    let home = config::home_dir();
    let install_root = config::state_home();

    // §3: a fresh (or half-finished) install runs the wizard first. A
    // completed one never sees it again — straight into §2 below.
    if !config::load().onboarding_complete() {
        if !crate::onboarding::run(&app) {
            return; // quitting mid-wizard
        }
        // The wizard's last step is what put us here; the loading screen is
        // the right backdrop for the picker that follows.
        if let Some(w) = app.get_webview_window("main") {
            let _ = w.eval("location.replace('loading.html')");
        }
    }

    let mut cfg = config::load();

    // §2 step 1: the reopen fast path. Anything short of "exists AND has an
    // rness/" falls through to the picker rather than erroring — a project
    // the user moved or deleted shouldn't be a modal on launch.
    let mut candidate: Option<PathBuf> = if cfg.reopen_last_project {
        cfg.last_active_project
            .as_ref()
            .map(PathBuf::from)
            .filter(|p| config::is_enough_project(p))
    } else {
        None
    };
    match &candidate {
        Some(p) => eprintln!("[enough-desktop] reopening last project {}", p.display()),
        None => eprintln!(
            "[enough-desktop] no reopen candidate (reopen_last_project={}) — folder picker",
            cfg.reopen_last_project
        ),
    }

    loop {
        let project = match candidate.take() {
            Some(p) => p,
            None => {
                status(&app, "choose a folder…");
                eprintln!("[enough-desktop] opening the folder picker");
                match pick_folder(&app) {
                    Some(p) => {
                        eprintln!("[enough-desktop] picked {}", p.display());
                        p
                    }
                    // §2 has no "no project" state in v1 — one window, one
                    // project. Cancelling the picker is cancelling the launch.
                    None => {
                        eprintln!("[enough-desktop] picker cancelled — exiting");
                        app.exit(0);
                        return;
                    }
                }
            }
        };

        // Pre-flight guard: ~/enough. The backend refuses this outright, so
        // there's nothing to ask about.
        if guards::inside_install_dir(&project, &install_root) {
            error_dialog(
                &app,
                "That folder is the enough install",
                &format!(
                    "{}\n\nenough can't run a project inside its own install \
                     directory — the project skeleton would collide with the \
                     global defaults. Pick any other folder.",
                    project.display()
                ),
            );
            continue;
        }

        // Pre-flight guard: cloud sync. The backend only *warns* about these
        // (it shows a notice in the chat pane), so the shell asks rather than
        // refuses — but it asks before spending 30 seconds on a boot.
        if let Some(provider) = guards::cloud_sync_provider(&project) {
            let ok = confirm(
                &app,
                &format!("This folder is inside {provider}"),
                &format!(
                    "{}\n\nCloud sync can't preserve the symlinks enough uses \
                     for its rness/ skeleton, or the executable bit on \
                     enough-on.command, between machines. enough re-heals \
                     broken links on each launch, but sharing this project \
                     across Macs will be fragile.\n\nFor multi-Mac setups, \
                     keep projects on local disk.",
                    project.display()
                ),
                "Open anyway",
                "Choose another folder",
            );
            if !ok {
                continue;
            }
        }

        match boot(&app, &project, &home) {
            Ok(()) => {
                cfg.record_open(&project);
                if let Err(e) = config::save(&cfg) {
                    eprintln!("[enough-desktop] couldn't write desktop.json: {e}");
                }
                sync_menu_check(&app, &cfg);
                eprintln!("[enough-desktop] open: {}", project.display());
                return;
            }
            Err(msg) => {
                eprintln!("[enough-desktop] launch failed: {msg}");
                error_dialog(&app, "enough couldn't start", &msg);
                status(&app, "choose a folder…");
                // Loop back to the picker rather than leaving a dead window.
            }
        }
    }
}

/// Spawn the backend for `project`, wait for it, point the window at it.
fn boot(app: &AppHandle, project: &PathBuf, home: &std::path::Path) -> Result<(), String> {
    status(app, "picking a port…");
    let port = backend::choose_ui_port()?;
    if port != backend::PREFERRED_PORT {
        if backend::looks_like_enough(backend::PREFERRED_PORT) {
            eprintln!(
                "[enough-desktop] {} is already serving an enough; using {port} instead",
                backend::PREFERRED_PORT
            );
        } else {
            eprintln!("[enough-desktop] port {} is busy; using {port}", backend::PREFERRED_PORT);
        }
    }

    status(app, "starting the backend…");
    let mut be = Backend::spawn(project, home, port)?;

    let app_for_progress = app.clone();
    let ready = be.wait_ready(|m| status(&app_for_progress, m));
    if let Err(msg) = ready {
        // The child may still be alive (timeout case) — don't leak it.
        be.shutdown();
        return Err(msg);
    }

    let url = be.url();
    let state = app.state::<Arc<AppState>>();
    *state.backend.lock().unwrap() = Some(be);

    status(app, "opening…");
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "the shell's window disappeared".to_string())?;
    let parsed = tauri::Url::parse(&url).map_err(|e| format!("bad backend url {url}: {e}"))?;
    window
        .navigate(parsed)
        .map_err(|e| format!("couldn't open {url}: {e}"))?;
    let label = project
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| project.display().to_string());
    let _ = window.set_title(&format!("enough — {label}"));
    Ok(())
}

/// Keep the menu's check mark honest after a config write.
fn sync_menu_check(app: &AppHandle, cfg: &DesktopConfig) {
    let state = app.state::<Arc<AppState>>();
    let item = state.reopen_item.lock().unwrap();
    if let Some(i) = item.as_ref() {
        let _ = i.set_checked(cfg.reopen_last_project);
    }
}

/// Quit path: stop the backend, then let the process go.
///
/// Idempotent — `AppState::quitting` gates it, because both the window's
/// close button and Cmd-Q land here.
pub fn shutdown_backend(app: &AppHandle) {
    // A quit mid-onboarding must not leave the wizard's temporary backend
    // (and any llama-server it owns) running.
    crate::onboarding::stop_wizard_backend(app);
    let state = app.state::<Arc<AppState>>();
    let taken = state.backend.lock().unwrap().take();
    if let Some(mut be) = taken {
        let how = be.shutdown();
        eprintln!("[enough-desktop] backend on {} stopped: {how}", be.port);
    }
    // Give the loopback socket a beat to clear before the process exits.
    std::thread::sleep(Duration::from_millis(50));
}
