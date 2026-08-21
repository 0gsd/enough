//! The launch flow, and the state machine that keeps a backend on screen.
//!
//! Runs on its own thread (the native folder picker must not block the main
//! one) and, since home-plan §5, never ends while the app is up: it brings a
//! backend into the window, parks until that backend goes away, works out
//! what the exit meant, and brings up the next one.
//!
//! The old rule from docs/tauri-plan.md §2 — "one window, one project;
//! cancelling the picker cancels the launch" — is superseded. The no-project
//! state is now the **home screen** (`enough --home`), and the picker survives
//! only as the fallback for a home screen that won't come up.
//!
//! Two decisions are pure functions with tests: [`initial_target`] (where a
//! launch goes) and [`after_exit`] (what a backend's exit meant).

use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;

use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

use crate::backend::{self, Backend, Mode};
use crate::config::{self, DesktopConfig};
use crate::guards;
use crate::AppState;

/// The exit code a backend uses to say "open something else — the handoff
/// file says what" (home-plan §1.7). Every other code means what it always
/// meant.
pub const HANDOFF_EXIT_CODE: i32 = 42;

/// How often the watcher looks at the child. Fast enough that a ⌘W or an
/// in-window "open project" feels immediate, slow enough to be free.
const WATCH_POLL: Duration = Duration::from_millis(200);

/// The handoff file is written (tmp+rename) *before* the backend exits, so it
/// is already on disk by the time we reap the child — Wave A guarantees the
/// ordering. These retries are for the pathological case only: a rename we
/// haven't observed yet on a network- or FUSE-backed home directory. Kept
/// short because "no file" is a perfectly ordinary answer (it is how Close
/// Project reports itself), and that case pays the whole budget.
const HANDOFF_RETRIES: u32 = 4;
const HANDOFF_RETRY_WAIT: Duration = Duration::from_millis(40);

// ---------------------------------------------------------------------------
// The two decisions, as pure functions
// ---------------------------------------------------------------------------

/// What the shell brings up next.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LaunchTarget {
    /// `enough --home` — the launch screen (home-plan §1.1).
    Home,
    /// A project folder, opened exactly the way a picker selection is.
    Project(PathBuf),
}

/// home-plan §5: where a launch goes once onboarding is done.
///
/// `reopen_last_project` on, with a `last_active_project` that still looks
/// like a project, goes straight there — unchanged from tauri-plan §2. Every
/// other case (toggle off, nothing remembered, the folder moved or lost its
/// `rness/`) is now the home screen rather than the picker.
///
/// The filesystem is injected so the rule can be tested without one.
pub fn initial_target(
    reopen: bool,
    last: Option<&str>,
    is_project: impl Fn(&Path) -> bool,
) -> LaunchTarget {
    if !reopen {
        return LaunchTarget::Home;
    }
    match last {
        Some(p) if !p.is_empty() => {
            let path = PathBuf::from(p);
            if is_project(&path) {
                LaunchTarget::Project(path)
            } else {
                LaunchTarget::Home
            }
        }
        _ => LaunchTarget::Home,
    }
}

/// What a backend's exit meant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AfterExit {
    /// 42 with a handoff file: open that project, MRU update and all.
    Open(PathBuf),
    /// 42 with no handoff file. That is how the desktop half of
    /// `POST /api/close-project` manifests — the route exits 42 and writes
    /// nothing — so it means the home screen.
    Home,
    /// Anything else: the backend fell over, or something stopped it. The
    /// user gets told, then lands somewhere safe.
    Crashed,
}

/// home-plan §1.7, the shell's half of the handshake, in one function.
///
/// `code` is `None` when a signal took the child, which is never a handoff.
pub fn after_exit(code: Option<i32>, handoff: Option<PathBuf>) -> AfterExit {
    if code != Some(HANDOFF_EXIT_CODE) {
        return AfterExit::Crashed;
    }
    match handoff {
        Some(p) if !p.as_os_str().is_empty() => AfterExit::Open(p),
        _ => AfterExit::Home,
    }
}

/// Read and delete `<enough config dir>/.home-open`.
///
/// Deleting is unconditional once the file exists — including when its
/// contents are empty or unreadable — so a stale handoff can never strand the
/// shell in a loop reopening the same project.
pub fn consume_handoff() -> Option<PathBuf> {
    consume_handoff_at(&config::enough_config_dir())
}

/// [`consume_handoff`] with the directory injected, for the tests.
fn consume_handoff_at(dir: &Path) -> Option<PathBuf> {
    let path = dir.join(".home-open");
    let mut raw: Option<String> = None;
    for attempt in 0..HANDOFF_RETRIES {
        if attempt > 0 {
            std::thread::sleep(HANDOFF_RETRY_WAIT);
        }
        if let Ok(text) = std::fs::read_to_string(&path) {
            raw = Some(text);
            break;
        }
    }
    let text = raw?;
    if let Err(e) = std::fs::remove_file(&path) {
        eprintln!("[enough-desktop] couldn't clear the handoff file: {e}");
    }
    let trimmed = text.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(PathBuf::from(trimmed))
    }
}

// ---------------------------------------------------------------------------
// Window chrome
// ---------------------------------------------------------------------------

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

/// Put the shell's own loading page back in the window.
///
/// A full `navigate`, not `location.replace`: between backends the window may
/// be showing a page on 127.0.0.1, where a relative URL would resolve against
/// the backend rather than against the bundle.
fn show_loading(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        if let Ok(url) = tauri::Url::parse("tauri://localhost/loading.html") {
            let _ = w.navigate(url);
        }
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

// ---------------------------------------------------------------------------
// The launch thread
// ---------------------------------------------------------------------------

/// Entry point for the launch thread.
pub fn run(app: AppHandle) {
    let home = config::home_dir();
    let install_root = config::state_home();

    // tauri-plan §3: a fresh (or half-finished) install runs the wizard
    // first. A completed one never sees it again — straight into the routing
    // below, which since 0.2.5 means the home screen rather than the picker.
    let onboarded = config::load().onboarding_complete();
    if !onboarded && !crate::onboarding::run(&app) {
        return; // quitting mid-wizard
    }

    let cfg = config::load();
    let mut target = initial_target(
        cfg.reopen_last_project,
        cfg.last_active_project.as_deref(),
        config::is_enough_project,
    );
    match &target {
        LaunchTarget::Project(p) => {
            eprintln!("[enough-desktop] reopening last project {}", p.display())
        }
        LaunchTarget::Home => eprintln!(
            "[enough-desktop] no reopen candidate (reopen_last_project={}) — home screen",
            cfg.reopen_last_project
        ),
    }

    // Set once the home screen has failed to come up. From then on the 2a
    // folder picker is this session's no-project state — the documented
    // fallback, so a broken `--home` leaves a usable app rather than a
    // dialog loop.
    let mut home_broken = false;

    loop {
        // A quit that landed while the previous backend was being stopped
        // must not start a new one behind it.
        if app.state::<Arc<AppState>>().quitting.load(Ordering::SeqCst) {
            return;
        }
        show_loading(&app);

        // --- bring a backend up ---------------------------------------
        let running = match target.clone() {
            LaunchTarget::Home if home_broken => {
                status(&app, "choose a folder…");
                eprintln!("[enough-desktop] opening the folder picker (home unavailable)");
                match pick_folder(&app) {
                    Some(p) => {
                        eprintln!("[enough-desktop] picked {}", p.display());
                        target = LaunchTarget::Project(p);
                    }
                    // With no home screen to fall back to there is nowhere
                    // else to be, so the 2a rule stands on this path only:
                    // cancelling the picker cancels the launch.
                    None => {
                        eprintln!("[enough-desktop] picker cancelled — exiting");
                        app.exit(0);
                        return;
                    }
                }
                continue;
            }
            LaunchTarget::Home => match boot(&app, &LaunchTarget::Home, &home) {
                Ok(()) => {
                    eprintln!("[enough-desktop] open: home");
                    Mode::Home
                }
                Err(msg) => {
                    eprintln!("[enough-desktop] home screen failed: {msg}");
                    error_dialog(
                        &app,
                        "enough couldn't open the home screen",
                        &format!("{msg}\n\nFalling back to the folder picker."),
                    );
                    home_broken = true;
                    continue;
                }
            },
            LaunchTarget::Project(project) => {
                if !preflight(&app, &project, &install_root) {
                    target = LaunchTarget::Home;
                    continue;
                }
                match boot(&app, &LaunchTarget::Project(project.clone()), &home) {
                    Ok(()) => {
                        // The MRU update is the picker's, unchanged — an
                        // exit-42 handoff records an open exactly as a pick
                        // does (home-plan §5).
                        let mut cfg = config::load();
                        cfg.record_open(&project);
                        if let Err(e) = config::save(&cfg) {
                            eprintln!("[enough-desktop] couldn't write desktop.json: {e}");
                        }
                        sync_menu_check(&app, &cfg);
                        eprintln!("[enough-desktop] open: {}", project.display());
                        Mode::Project
                    }
                    Err(msg) => {
                        eprintln!("[enough-desktop] launch failed: {msg}");
                        error_dialog(&app, "enough couldn't start", &msg);
                        target = LaunchTarget::Home;
                        continue;
                    }
                }
            }
        };
        sync_mode_menus(&app, Some(running));

        // --- park until that backend goes away ------------------------
        match watch(&app) {
            Woke::Quitting => return,
            Woke::Requested(next) => {
                sync_mode_menus(&app, None);
                target = next;
            }
            Woke::Exited(be, code) => {
                sync_mode_menus(&app, None);
                eprintln!(
                    "[enough-desktop] backend mode={running:?} on {} exited with {code:?}",
                    be.port
                );
                target = match after_exit(code, consume_handoff()) {
                    AfterExit::Open(p) => LaunchTarget::Project(p),
                    AfterExit::Home => LaunchTarget::Home,
                    AfterExit::Crashed => {
                        let tail = be.log_tail(backend::DIALOG_TAIL_LINES);
                        let detail = if tail.trim().is_empty() {
                            String::new()
                        } else {
                            format!("\n\n{tail}")
                        };
                        error_dialog(
                            &app,
                            "The enough backend stopped",
                            &format!(
                                "It exited with {}.{detail}",
                                code.map(|c| c.to_string())
                                    .unwrap_or_else(|| "a signal".into())
                            ),
                        );
                        // A home screen that dies on its own is a home screen
                        // we shouldn't keep respawning.
                        if running == Mode::Home {
                            home_broken = true;
                        }
                        LaunchTarget::Home
                    }
                };
            }
        }
    }
}

/// The pre-flight guards, unchanged from 2a bar the first. `false` = don't
/// open this.
fn preflight(app: &AppHandle, project: &Path, install_root: &Path) -> bool {
    // New in 0.2.5, for the new way a path can arrive: a handoff names a
    // folder that went away between the click and the spawn. Without this the
    // failure is `Command::spawn` complaining about a cwd, which reads like a
    // bug in enough rather than a missing folder. (A picked or remembered
    // folder has already been checked, so this costs one `stat` and never
    // fires on those paths.)
    if !project.is_dir() {
        error_dialog(
            app,
            "That folder isn't there any more",
            &format!(
                "{}\n\nenough can't open it. If it's on a drive that isn't \
                 mounted, mount it and try again — the home screen still \
                 lists the project either way.",
                project.display()
            ),
        );
        return false;
    }

    // ~/enough. The backend refuses this outright, so there's nothing to ask
    // about.
    if guards::inside_install_dir(project, install_root) {
        error_dialog(
            app,
            "That folder is the enough install",
            &format!(
                "{}\n\nenough can't run a project inside its own install \
                 directory — the project skeleton would collide with the \
                 global defaults. Pick any other folder.",
                project.display()
            ),
        );
        return false;
    }

    // Cloud sync. The backend only *warns* about these (it shows a notice in
    // the chat pane), so the shell asks rather than refuses — but it asks
    // before spending 30 seconds on a boot.
    if let Some(provider) = guards::cloud_sync_provider(project) {
        let ok = confirm(
            app,
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
            return false;
        }
    }
    true
}

/// Spawn the backend for `target`, wait for it, point the window at it.
fn boot(app: &AppHandle, target: &LaunchTarget, home: &Path) -> Result<(), String> {
    status(app, "picking a port…");
    let port = backend::choose_ui_port()?;
    if port != backend::PREFERRED_PORT {
        if backend::looks_like_enough(backend::PREFERRED_PORT) {
            eprintln!(
                "[enough-desktop] {} is already serving an enough; using {port} instead",
                backend::PREFERRED_PORT
            );
        } else {
            eprintln!(
                "[enough-desktop] port {} is busy; using {port}",
                backend::PREFERRED_PORT
            );
        }
    }

    let mut be = match target {
        LaunchTarget::Home => {
            status(app, "opening the home screen…");
            Backend::spawn_home(home, port)?
        }
        LaunchTarget::Project(project) => {
            status(app, "starting the backend…");
            Backend::spawn(project, home, port)?
        }
    };

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
    let title = match target {
        LaunchTarget::Home => "enough".to_string(),
        LaunchTarget::Project(project) => {
            let label = project
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_else(|| project.display().to_string());
            format!("enough — {label}")
        }
    };
    let _ = window.set_title(&title);
    Ok(())
}

// ---------------------------------------------------------------------------
// The watcher (home-plan §5, exit-42)
// ---------------------------------------------------------------------------

/// Why the launch thread stopped waiting.
enum Woke {
    /// The child exited on its own. Carries the (already reaped) backend, so
    /// a crash dialog can quote what it printed, and the exit code.
    Exited(Backend, Option<i32>),
    /// A menu action stopped the backend and named what comes next — today
    /// that is ⌘W, whose answer is always the home screen.
    Requested(LaunchTarget),
    /// The app is going away.
    Quitting,
}

fn watch(app: &AppHandle) -> Woke {
    let state = app.state::<Arc<AppState>>();
    loop {
        if state.quitting.load(Ordering::SeqCst) {
            return Woke::Quitting;
        }
        if let Some(next) = state.next_target.lock().unwrap().take() {
            return Woke::Requested(next);
        }
        // Held for one `waitpid` and no longer: the quit path takes the whole
        // Backend out from under us and must never wait on this poll.
        let exited = {
            let mut guard = state.backend.lock().unwrap();
            let gone = match guard.as_mut() {
                Some(be) => be.exited(),
                // ⌘W moved it to `closing_backend`; its worker will set
                // `next_target` when the shutdown lands.
                None => None,
            };
            match gone {
                Some(code) => guard.take().map(|be| (be, code)),
                None => None,
            }
        };
        if let Some((be, code)) = exited {
            return Woke::Exited(be, code);
        }
        std::thread::sleep(WATCH_POLL);
    }
}

// ---------------------------------------------------------------------------
// Menu actions
// ---------------------------------------------------------------------------

/// File → Close Project (⌘W), home-plan §5.
///
/// Stops the project backend through the graceful door the quit path uses,
/// then hands the launch thread a home target. A no-op unless a *project*
/// backend is actually running, which also makes it re-entrant: the second
/// ⌘W finds the slot empty and returns.
pub fn request_close_project(app: &AppHandle) {
    let state = app.state::<Arc<AppState>>();
    if state.quitting.load(Ordering::SeqCst) {
        return;
    }
    let taken = {
        let mut running = state.backend.lock().unwrap();
        match running.as_ref() {
            Some(be) if be.mode == Mode::Project => running.take(),
            // Home, or a close already in flight (which empties this slot) —
            // which is what makes a second ⌘W a no-op rather than a race.
            _ => None,
        }
    };
    let Some(be) = taken else { return };
    // Park it where a concurrent quit can still find it (see
    // `shutdown_backend`), and where the watcher can't see a live-then-dead
    // child it would read as a crash. The slot is necessarily empty: it is
    // only ever filled from here, only when `backend` was `Some`, and the
    // worker below clears it before the launch thread is allowed to refill
    // `backend`. The two locks are never held at once, in either direction.
    *state.closing_backend.lock().unwrap() = Some(be);
    sync_mode_menus(app, None);

    let handle = app.clone();
    std::thread::spawn(move || {
        {
            let state = handle.state::<Arc<AppState>>();
            let mut closing = state.closing_backend.lock().unwrap();
            if let Some(be) = closing.as_mut() {
                let how = be.shutdown();
                eprintln!("[enough-desktop] project closed: backend on {} {how}", be.port);
            }
            *closing = None;
        }
        // ⌘W's answer is the home screen whatever else happened, so clear any
        // handoff file the backend managed to write on its way out (the user
        // clicking "open project" in the same instant). Leaving it would open
        // a stale project at the *next* exit 42.
        if let Some(p) = consume_handoff() {
            eprintln!(
                "[enough-desktop] discarding a handoff for {} — ⌘W closed the project",
                p.display()
            );
        }
        let state = handle.state::<Arc<AppState>>();
        *state.next_target.lock().unwrap() = Some(LaunchTarget::Home);
    });
}

/// View → Show Hidden Projects, home-plan §1.10 / §5.
///
/// The webview owns the toggle: Wave B's `homeSetShowHidden(on)` re-renders
/// the grid and persists the answer to ui.json through `/api/ui-config`. The
/// shell therefore reads the *persisted* value to decide what "toggle" means,
/// which keeps the menu honest even when the user last flipped it with the
/// home screen's own chip.
pub fn toggle_show_hidden(app: &AppHandle) {
    let is_home = {
        let state = app.state::<Arc<AppState>>();
        let guard = state.backend.lock().unwrap();
        matches!(guard.as_ref(), Some(be) if be.mode == Mode::Home)
    };
    if !is_home {
        return;
    }
    let next = !config::ui_flag(config::SHOW_HIDDEN_KEY);
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.eval(format!(
            "window.homeSetShowHidden&&window.homeSetShowHidden({next})"
        ));
    }
    let state = app.state::<Arc<AppState>>();
    let item = state.show_hidden_item.lock().unwrap().clone();
    if let Some(i) = item {
        let _ = i.set_checked(next);
    }
}

/// Keep the menu's check mark honest after a config write.
fn sync_menu_check(app: &AppHandle, cfg: &DesktopConfig) {
    let state = app.state::<Arc<AppState>>();
    let item = state.reopen_item.lock().unwrap();
    if let Some(i) = item.as_ref() {
        let _ = i.set_checked(cfg.reopen_last_project);
    }
}

/// Enable the mode-specific menu items for the backend that is running (or
/// disable both when none is).
///
/// This is the whole of "the shell knows which mode it's in": the launch
/// thread spawned the child, so it knows the argv, and every menu decision
/// reads from that one fact rather than probing the backend.
pub fn sync_mode_menus(app: &AppHandle, mode: Option<Mode>) {
    let state = app.state::<Arc<AppState>>();
    let close = state.close_project_item.lock().unwrap().clone();
    let hidden = state.show_hidden_item.lock().unwrap().clone();
    if let Some(i) = close {
        let _ = i.set_enabled(mode == Some(Mode::Project));
    }
    if let Some(i) = hidden {
        let _ = i.set_enabled(mode == Some(Mode::Home));
        if mode == Some(Mode::Home) {
            let _ = i.set_checked(config::ui_flag(config::SHOW_HIDDEN_KEY));
        }
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
    // A ⌘W close already in flight holds this lock for the length of its own
    // graceful shutdown, so taking it here waits for that to finish rather
    // than racing it into an orphaned uvicorn.
    let closing = state.closing_backend.lock().unwrap().take();
    if let Some(mut be) = closing {
        let how = be.shutdown();
        eprintln!("[enough-desktop] closing backend on {} stopped: {how}", be.port);
    }
    let taken = state.backend.lock().unwrap().take();
    if let Some(mut be) = taken {
        let how = be.shutdown();
        eprintln!("[enough-desktop] backend on {} stopped: {how}", be.port);
    }
    // Give the loopback socket a beat to clear before the process exits.
    std::thread::sleep(Duration::from_millis(50));
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A stand-in for `config::is_enough_project` that answers from a list —
    /// the routing rule is about the decision, not about `rness/`.
    fn only(paths: &'static [&'static str]) -> impl Fn(&Path) -> bool {
        move |p: &Path| paths.iter().any(|q| Path::new(q) == p)
    }

    // -----------------------------------------------------------------------
    // Launch routing (home-plan §5, first bullet)
    // -----------------------------------------------------------------------

    #[test]
    fn reopen_off_lands_on_home() {
        // Even with a perfectly good last project — the toggle is the point.
        assert_eq!(
            initial_target(false, Some("/w/novel"), only(&["/w/novel"])),
            LaunchTarget::Home
        );
    }

    #[test]
    fn reopen_on_with_a_live_project_goes_straight_there() {
        assert_eq!(
            initial_target(true, Some("/w/novel"), only(&["/w/novel"])),
            LaunchTarget::Project(PathBuf::from("/w/novel"))
        );
    }

    #[test]
    fn a_first_launch_lands_on_home_not_the_picker() {
        // Nothing remembered yet: this is the case that used to open the
        // native folder picker straight out of the wizard.
        assert_eq!(initial_target(true, None, only(&[])), LaunchTarget::Home);
        assert_eq!(initial_target(false, None, only(&[])), LaunchTarget::Home);
    }

    #[test]
    fn a_moved_or_un_enoughed_last_project_falls_through_to_home() {
        // The folder is gone, or somebody deleted its rness/. Not a modal on
        // launch — just the home screen, where it renders as `missing`.
        assert_eq!(
            initial_target(true, Some("/w/gone"), only(&["/w/novel"])),
            LaunchTarget::Home
        );
        // An empty string in desktop.json is "nothing remembered", not "/".
        assert_eq!(initial_target(true, Some(""), only(&[""])), LaunchTarget::Home);
    }

    // -----------------------------------------------------------------------
    // The exit-42 handshake (home-plan §1.7 / §5, second bullet)
    // -----------------------------------------------------------------------

    #[test]
    fn exit_42_with_a_handoff_file_opens_that_project() {
        assert_eq!(
            after_exit(Some(42), Some(PathBuf::from("/w/novel"))),
            AfterExit::Open(PathBuf::from("/w/novel"))
        );
    }

    #[test]
    fn exit_42_without_a_handoff_file_means_home() {
        // This is how the desktop half of POST /api/close-project manifests.
        assert_eq!(after_exit(Some(42), None), AfterExit::Home);
        // …and a file that was there but held nothing is the same thing.
        assert_eq!(after_exit(Some(42), Some(PathBuf::new())), AfterExit::Home);
    }

    #[test]
    fn every_other_exit_keeps_todays_behavior() {
        for code in [0, 1, 2, 41, 43, 130] {
            assert_eq!(
                after_exit(Some(code), Some(PathBuf::from("/w/novel"))),
                AfterExit::Crashed,
                "exit {code}"
            );
        }
        // Killed by a signal: no code at all, and never a handoff.
        assert_eq!(after_exit(None, None), AfterExit::Crashed);
        assert_eq!(after_exit(None, Some(PathBuf::from("/w/novel"))), AfterExit::Crashed);
    }

    // -----------------------------------------------------------------------
    // The handoff file itself
    // -----------------------------------------------------------------------

    #[test]
    fn the_handoff_file_is_read_once_and_deleted() {
        let dir = config::scratch_dir("handoff");
        let file = dir.join(".home-open");
        // Exactly what `home.write_handoff` writes: one absolute path, one
        // trailing newline.
        std::fs::write(&file, "/w/novel\n").unwrap();

        assert_eq!(consume_handoff_at(&dir), Some(PathBuf::from("/w/novel")));
        assert!(!file.exists(), "the shell consumes the file");
        // A second read must not reopen the same project.
        assert_eq!(consume_handoff_at(&dir), None);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn an_absent_handoff_file_is_the_close_project_case() {
        let dir = config::scratch_dir("handoff-absent");
        assert_eq!(consume_handoff_at(&dir), None);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn an_empty_handoff_file_is_consumed_rather_than_left_to_rot() {
        let dir = config::scratch_dir("handoff-empty");
        let file = dir.join(".home-open");
        std::fs::write(&file, "  \n").unwrap();
        assert_eq!(consume_handoff_at(&dir), None);
        assert!(!file.exists(), "a stale file must not strand the shell");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_path_with_spaces_survives_intact() {
        let dir = config::scratch_dir("handoff-spaces");
        std::fs::write(dir.join(".home-open"), "/Users/g/My Writing/the novel\n").unwrap();
        assert_eq!(
            consume_handoff_at(&dir),
            Some(PathBuf::from("/Users/g/My Writing/the novel"))
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    // -----------------------------------------------------------------------
    // The two halves together — the flows a human then checks by hand
    // -----------------------------------------------------------------------

    #[test]
    fn the_open_handshake_end_to_end() {
        let dir = config::scratch_dir("handshake-open");
        std::fs::write(dir.join(".home-open"), "/w/novel\n").unwrap();
        // Home exits 42 having written the file: the shell opens that project.
        assert_eq!(
            after_exit(Some(HANDOFF_EXIT_CODE), consume_handoff_at(&dir)),
            AfterExit::Open(PathBuf::from("/w/novel"))
        );
        // The project server later exits 42 having written nothing: home.
        assert_eq!(
            after_exit(HANDOFF_EXIT_CODE.into(), consume_handoff_at(&dir)),
            AfterExit::Home
        );
        let _ = std::fs::remove_dir_all(&dir);
    }
}
