// enough.app — milestone 2a, the thin shell.
//
// Everything the shell does lives in Rust: read ~/enough/config/desktop.json,
// pick a project (reopen or native picker), spawn `uv run --project <code>
// enough` in it, wait for the backend, point one WKWebView at it, and stop
// the backend cleanly on quit. The web UI is enough's own, unmodified.
//
// The shell's own screen (ui/loading.html) is static HTML with no IPC — it's
// updated by `eval()` from the launch thread — so there is no Node build step
// and no JS↔Rust command surface to secure.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod bundled;
mod config;
mod guards;
mod http;
mod launch;
mod onboarding;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent, Wry};

/// Menu id for the one setting the shell owns.
const REOPEN_ITEM_ID: &str = "toggle-reopen-last-project";
/// File → Close Project (⌘W), home-plan §5. Enabled only while a *project*
/// backend is running.
const CLOSE_PROJECT_ITEM_ID: &str = "close-project";
/// View → Show Hidden Projects, home-plan §1.10. Enabled only in home mode.
const SHOW_HIDDEN_ITEM_ID: &str = "toggle-show-hidden-projects";

/// Set by the SIGTERM/SIGINT handler; drained by a polling thread.
static SIGNALLED: AtomicBool = AtomicBool::new(false);

extern "C" fn note_signal(_sig: libc::c_int) {
    // The only async-signal-safe thing worth doing here: flip a flag.
    SIGNALLED.store(true, Ordering::SeqCst);
}

/// Route catchable terminations through the same quit path as Cmd-Q.
///
/// macOS's own quit flows (Cmd-Q, the Dock, logout, Force Quit's first
/// attempt) arrive as Apple Events and land in `RunEvent::ExitRequested`, so
/// this is mainly for `kill`, a terminal ctrl-c during development, and any
/// tooling that stops the app the Unix way. SIGKILL is by definition
/// unhandleable — that is the one path that can orphan the backend.
fn watch_for_signals(app: tauri::AppHandle) {
    unsafe {
        libc::signal(libc::SIGTERM, note_signal as *const () as libc::sighandler_t);
        libc::signal(libc::SIGINT, note_signal as *const () as libc::sighandler_t);
        // Writing to a socket whose peer vanished must not take us down.
        libc::signal(libc::SIGPIPE, libc::SIG_IGN);
    }
    std::thread::spawn(move || loop {
        if SIGNALLED.load(Ordering::SeqCst) {
            eprintln!("[enough-desktop] termination signal — shutting down");
            begin_quit(&app);
            return;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    });
}

#[derive(Default)]
pub struct AppState {
    /// The backend the window is pointing at. Its `mode` is how the shell
    /// knows whether it is showing a project or the home screen — it spawned
    /// the child, so it knows the argv (home-plan §5).
    pub backend: Mutex<Option<backend::Backend>>,
    /// The throwaway backend the onboarding wizard's model step runs against
    /// (onboarding.rs). Separate from `backend` because it is stopped at a
    /// different moment and never becomes the window's destination.
    pub wizard_backend: Mutex<Option<backend::Backend>>,
    /// A project backend that ⌘W is in the middle of stopping. Its own slot
    /// so the launch thread's watcher doesn't read the exit as a crash, and
    /// so a quit arriving mid-close still finds something to wait for rather
    /// than orphaning a uvicorn.
    pub closing_backend: Mutex<Option<backend::Backend>>,
    /// What the launch thread should bring up next, when a menu action rather
    /// than an exit code decided it.
    pub next_target: Mutex<Option<launch::LaunchTarget>>,
    /// Flipped by `ob_advance` when the last step lands; the launch thread is
    /// parked on it.
    pub onboarding_done: AtomicBool,
    pub reopen_item: Mutex<Option<CheckMenuItem<Wry>>>,
    pub close_project_item: Mutex<Option<MenuItem<Wry>>>,
    pub show_hidden_item: Mutex<Option<CheckMenuItem<Wry>>>,
    pub quitting: AtomicBool,
}

fn main() {
    let state = Arc::new(AppState::default());

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Arc::clone(&state))
        // The wizard's commands. App-defined commands are reachable only from
        // origins a capability grants IPC to, and `capabilities/default.json`
        // lists no `remote` entry — so these exist for `ui/onboarding.html`
        // and are invisible to the enough UI on 127.0.0.1.
        .invoke_handler(tauri::generate_handler![
            onboarding::ob_state,
            onboarding::ob_env_sync,
            onboarding::ob_models_boot,
            onboarding::ob_api,
            onboarding::ob_extras,
            onboarding::ob_advance,
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("loading.html".into()))
                .title("enough")
                .inner_size(1180.0, 820.0)
                .min_inner_size(720.0, 520.0)
                .center()
                .build()?;

            app.set_menu(build_menu(&handle)?)?;
            watch_for_signals(handle.clone());

            // The launch flow blocks on a native folder picker, which must
            // never run on the main thread.
            std::thread::spawn(move || launch::run(handle));
            Ok(())
        })
        .on_menu_event(|app, event| {
            let id = event.id();
            if id == REOPEN_ITEM_ID {
                let mut cfg = config::load();
                cfg.reopen_last_project = !cfg.reopen_last_project;
                if let Err(e) = config::save(&cfg) {
                    eprintln!("[enough-desktop] couldn't write desktop.json: {e}");
                }
                let state = app.state::<Arc<AppState>>();
                let item = state.reopen_item.lock().unwrap().clone();
                if let Some(item) = item {
                    let _ = item.set_checked(cfg.reopen_last_project);
                }
            } else if id == CLOSE_PROJECT_ITEM_ID {
                // Returns immediately; the graceful shutdown and the home
                // spawn happen off the menu thread.
                launch::request_close_project(app);
            } else if id == SHOW_HIDDEN_ITEM_ID {
                launch::toggle_show_hidden(app);
            }
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let app = window.app_handle();
                if !app.state::<Arc<AppState>>().quitting.load(Ordering::SeqCst) {
                    api.prevent_close();
                    begin_quit(app);
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build the enough shell")
        .run(move |app, event| match event {
            RunEvent::ExitRequested { api, .. } => {
                // Cmd-Q and the app menu's Quit land here. Hold the exit
                // open exactly once, long enough to stop the backend.
                if !app.state::<Arc<AppState>>().quitting.load(Ordering::SeqCst) {
                    api.prevent_exit();
                    begin_quit(app);
                }
            }
            RunEvent::Exit => {
                // Belt and braces: if anything got us here without passing
                // through begin_quit, don't leave a uvicorn behind.
                launch::shutdown_backend(app);
            }
            _ => {}
        });
}

/// Start the quit sequence. Hides the window immediately so quitting feels
/// instant, stops the backend on a worker thread (it can block for seconds
/// in the pathological case), then lets the app exit for real.
fn begin_quit(app: &tauri::AppHandle) {
    let state = app.state::<Arc<AppState>>();
    if state.quitting.swap(true, Ordering::SeqCst) {
        return;
    }
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
    }
    let handle = app.clone();
    std::thread::spawn(move || {
        launch::shutdown_backend(&handle);
        handle.exit(0);
    });
}

/// The whole native surface: an app menu carrying the one desktop setting, a
/// File menu with Close Project, a View menu with the home screen's one
/// toggle, and an Edit menu — without which copy/paste is dead in the
/// WKWebView.
///
/// The two new items start **disabled**: nothing is running when the menu is
/// built, and `launch::sync_mode_menus` turns exactly one of them on each
/// time a backend comes up.
fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<Wry>> {
    let cfg = config::load();

    let reopen = CheckMenuItem::with_id(
        app,
        REOPEN_ITEM_ID,
        "Reopen Last Project on Launch",
        true,
        cfg.reopen_last_project,
        None::<&str>,
    )?;
    let close_project = MenuItem::with_id(
        app,
        CLOSE_PROJECT_ITEM_ID,
        "Close Project",
        false,
        Some("CmdOrCtrl+W"),
    )?;
    let show_hidden = CheckMenuItem::with_id(
        app,
        SHOW_HIDDEN_ITEM_ID,
        "Show Hidden Projects",
        false,
        config::ui_flag(config::SHOW_HIDDEN_KEY),
        None::<&str>,
    )?;
    {
        let state = app.state::<Arc<AppState>>();
        state.reopen_item.lock().unwrap().replace(reopen.clone());
        state
            .close_project_item
            .lock()
            .unwrap()
            .replace(close_project.clone());
        state
            .show_hidden_item
            .lock()
            .unwrap()
            .replace(show_hidden.clone());
    }

    let app_menu = Submenu::with_items(
        app,
        "enough",
        true,
        &[
            &PredefinedMenuItem::about(app, None, None)?,
            &PredefinedMenuItem::separator(app)?,
            // "Settings" in the tauri-plan §2 sense: one toggle, native
            // chrome, no window of its own to maintain.
            &MenuItem::with_id(app, "settings-header", "Settings", false, None::<&str>)?,
            &reopen,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::hide(app, None)?,
            &PredefinedMenuItem::hide_others(app, None)?,
            &PredefinedMenuItem::show_all(app, None)?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::quit(app, None)?,
        ],
    )?;

    // home-plan §5. One item, because closing a project is the only file-ish
    // thing the shell does — everything else about a project lives in the web
    // UI, which has its own affordances.
    let file_menu = Submenu::with_items(app, "File", true, &[&close_project])?;

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &PredefinedMenuItem::undo(app, None)?,
            &PredefinedMenuItem::redo(app, None)?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, None)?,
            &PredefinedMenuItem::copy(app, None)?,
            &PredefinedMenuItem::paste(app, None)?,
            &PredefinedMenuItem::select_all(app, None)?,
        ],
    )?;

    let view_menu = Submenu::with_items(app, "View", true, &[&show_hidden])?;

    // No `close_window` item: on macOS the predefined one carries ⌘W, which
    // now belongs to Close Project. The app is one window and closing it
    // quits, so ⌘Q and the red button already cover it.
    let window_menu = Submenu::with_items(
        app,
        "Window",
        true,
        &[
            &PredefinedMenuItem::minimize(app, None)?,
            &PredefinedMenuItem::fullscreen(app, None)?,
        ],
    )?;

    // On macOS the first submenu is the app menu, whatever it is called.
    Menu::with_items(
        app,
        &[&app_menu, &file_menu, &edit_menu, &view_menu, &window_menu],
    )
}
