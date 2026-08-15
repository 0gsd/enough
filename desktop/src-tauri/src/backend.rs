//! Spawning, health-probing and stopping the enough backend.
//!
//! The 2a incantation (tauri-plan §1) is the existing PATH wrapper:
//!
//! ```text
//! uv run --project <code_root> enough --port <p> --no-browser
//! ```
//!
//! run with `cwd` = the chosen project directory. `code_root` is
//! `$ENOUGH_DESKTOP_CODE` when set (the dev path — point it at a checkout),
//! else `~/enough`.

use std::collections::VecDeque;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use std::os::unix::process::CommandExt;

use crate::bundled;
use crate::http;

/// The UI port we'd like. Free → we take it; occupied by anything at all →
/// we take an ephemeral port instead. tauri-plan §1: never adopt another
/// instance's UI.
pub const PREFERRED_PORT: u16 = 3456;

/// How long we'll wait for the backend to answer after spawning. `uv run`
/// may sync the environment on a cold checkout, which is the slow case.
const READY_TIMEOUT: Duration = Duration::from_secs(180);
const READY_POLL: Duration = Duration::from_millis(200);

/// Quit budget. Typical real cost is well under two seconds; these are the
/// pathological ceilings. See `shutdown()`.
const SHUTDOWN_POST_TIMEOUT: Duration = Duration::from_secs(15);
const GRACEFUL_EXIT_WAIT: Duration = Duration::from_secs(8);
const SIGTERM_WAIT: Duration = Duration::from_secs(4);
const SIGKILL_WAIT: Duration = Duration::from_secs(2);

/// Tail of the child's merged stdout+stderr, kept so a failed launch can
/// show the user what the backend actually said. `DIALOG_TAIL_LINES` is how
/// much of that a native alert gets — a whole Python traceback in an NSAlert
/// is a wall the user scrolls past; the full buffer still goes to stderr.
const LOG_TAIL_LINES: usize = 60;
const DIALOG_TAIL_LINES: usize = 16;

pub struct Backend {
    child: Child,
    pub port: u16,
    pub token: String,
    pub project: PathBuf,
    log: Arc<Mutex<VecDeque<String>>>,
}

// ---------------------------------------------------------------------------
// Ports
// ---------------------------------------------------------------------------

fn port_is_free(port: u16) -> bool {
    TcpListener::bind(("127.0.0.1", port)).is_ok()
}

fn ephemeral_port() -> Option<u16> {
    TcpListener::bind("127.0.0.1:0")
        .ok()?
        .local_addr()
        .ok()
        .map(|a| a.port())
}

/// True when whatever is on `port` answers like a live enough. Used only to
/// tell the user *why* we moved off 3456 — either way we move off it.
pub fn looks_like_enough(port: u16) -> bool {
    match http::get(port, "/api/project", Duration::from_millis(1500)) {
        Some(r) => r.status == 200 && r.body.contains("\"folder\""),
        None => false,
    }
}

/// Pick the UI port: 3456 when it's free, otherwise an ephemeral one.
pub fn choose_ui_port() -> Result<u16, String> {
    if port_is_free(PREFERRED_PORT) {
        return Ok(PREFERRED_PORT);
    }
    ephemeral_port().ok_or_else(|| "could not find a free port to serve on".to_string())
}

// ---------------------------------------------------------------------------
// Locating uv
// ---------------------------------------------------------------------------

/// Directories a GUI app launched from Finder won't have on `PATH` but which
/// hold the binaries enough needs — `uv` here, and `llama-server` / `pandoc`
/// / `tor` / `harper-cli` for the backend itself.
fn extra_bin_dirs(home: &Path) -> Vec<PathBuf> {
    vec![
        home.join(".local/bin"),
        PathBuf::from("/opt/homebrew/bin"),
        PathBuf::from("/usr/local/bin"),
        home.join(".cargo/bin"),
    ]
}

/// `$ENOUGH_DESKTOP_UV`, else the bundled sidecar, else `uv` on PATH, else the
/// usual install spots.
///
/// The sidecar outranks PATH deliberately: a machine with a two-year-old brew
/// `uv` must not decide what enough.app runs. The override still outranks the
/// sidecar, because that's the seam a QA harness and a uv developer need.
pub fn find_uv(home: &Path) -> Result<PathBuf, String> {
    if let Ok(p) = std::env::var("ENOUGH_DESKTOP_UV") {
        let p = PathBuf::from(p);
        if p.is_file() {
            return Ok(p);
        }
    }
    if let Some(p) = bundled::locate().uv {
        return Ok(p);
    }
    if let Ok(path) = std::env::var("PATH") {
        for dir in std::env::split_paths(&path) {
            let cand = dir.join("uv");
            if cand.is_file() {
                return Ok(cand);
            }
        }
    }
    for dir in extra_bin_dirs(home) {
        let cand = dir.join("uv");
        if cand.is_file() {
            return Ok(cand);
        }
    }
    Err("couldn't find `uv`. enough runs its backend through uv — install it \
         with `curl -LsSf https://astral.sh/uv/install.sh | sh`, or point \
         ENOUGH_DESKTOP_UV at the binary."
        .to_string())
}

/// Where the Python lives: `$ENOUGH_DESKTOP_CODE` (dev override, tauri-plan
/// §1) → the bundled source snapshot (2b) → `~/enough` (2a / a CLI install).
///
/// The code/state split rule in one function: the .app runs the snapshot
/// sealed inside it, a CLI clone at `~/enough` runs its own checkout, and both
/// keep their state in `~/enough`.
pub fn code_root(home: &Path) -> PathBuf {
    if let Ok(p) = std::env::var("ENOUGH_DESKTOP_CODE") {
        if !p.is_empty() {
            return PathBuf::from(p);
        }
    }
    if let Some(p) = bundled::locate().code {
        return p;
    }
    home.join("enough")
}

/// Is `root` the read-only snapshot inside our own bundle?
///
/// Two things hang off this: `uv run --frozen` (a sealed bundle must never be
/// re-locked) and the pycache redirect below. A dev checkout gets neither —
/// `--frozen` would refuse to pick up an edited `pyproject.toml`.
fn is_bundled_code(root: &Path) -> bool {
    bundled::locate().code.as_deref() == Some(root)
}

/// Where uv builds the project's virtualenv.
///
/// It cannot be the default `<project>/.venv`: the project is inside a signed
/// .app, and writing there breaks the code signature (and fails outright on a
/// volume the user can't write). `$HOME` stays the single state seam, so a
/// scratch HOME gets a scratch venv with everything else.
pub fn venv_dir(home: &Path) -> PathBuf {
    home.join("enough").join(".venv-desktop")
}

/// Where CPython may write `__pycache__`.
///
/// Same reason: importing `enough` from a sealed bundle would otherwise
/// scatter `.pyc` files through `Contents/Resources` and invalidate the
/// signature. `PYTHONPYCACHEPREFIX` keeps the caching (this is a ~7 MB
/// package; recompiling it every launch is a visible cost) and moves the
/// writes out of the bundle. Only set when we're actually running bundled
/// code — a dev checkout wants its bytecode where it always was.
pub fn pycache_dir(home: &Path) -> PathBuf {
    home.join("enough").join(".pycache-desktop")
}

/// The CPython the bundled app runs on.
///
/// `only-managed` + an explicit version, rather than uv's default of "reuse
/// whatever suitable interpreter is already around". Two reasons: a .app that
/// silently binds its venv to `/opt/homebrew/opt/python@3.11` breaks the day
/// the user runs `brew uninstall python@3.11`, and the whole point of 2b is
/// that a machine with no Homebrew works identically to one with it. uv puts
/// the interpreter under `$HOME`, so it moves with the state seam like
/// everything else.
///
/// The version is pinned rather than left to "newest managed" because
/// `uv sync --frozen` has to find wheels in a lockfile it may not rebuild:
/// today `uv.lock` carries macOS-arm64 wheels for cp311–cp314 for the
/// binary-only dependencies (ctranslate2, libzim, sentencepiece,
/// pydantic-core), and an unpinned uv that starts defaulting to a newer
/// CPython than the lock covers would fail at first run on a user's machine
/// and nowhere else. Bump it deliberately, with a re-lock.
const BUNDLED_PYTHON: &str = "3.13";

/// PATH for the child: ours, plus the dirs above, deduped, order preserved.
fn child_path(home: &Path) -> String {
    let mut dirs: Vec<PathBuf> = std::env::var("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();
    for d in extra_bin_dirs(home) {
        if !dirs.contains(&d) {
            dirs.push(d);
        }
    }
    std::env::join_paths(dirs)
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|_| "/usr/bin:/bin".to_string())
}

/// Look `name` up on the PATH the *child* will get — which is the only PATH
/// whose answer matters, since the backend is what shells out to `pandoc`,
/// `tor`, `whisper-cli` and `harper-cli`. A GUI app's own PATH would report
/// every one of them missing.
pub fn which_for_child(home: &Path, name: &str) -> Option<PathBuf> {
    use std::os::unix::fs::PermissionsExt;
    for dir in std::env::split_paths(&child_path(home)) {
        let cand = dir.join(name);
        let ok = cand
            .metadata()
            .map(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false);
        if ok {
            return Some(cand);
        }
    }
    None
}

/// A per-launch secret the backend requires back on `/api/shutdown`. Not a
/// security boundary against local processes (nothing on loopback is) — it
/// stops a cross-origin page from POSTing the endpoint, because a custom
/// header forces a CORS preflight the backend never answers.
/// The environment every `uv` invocation of ours shares — the backend spawn
/// and the onboarding `uv sync` alike. Applied on top of a wholesale inherit
/// (tauri-plan §2a: env passthrough is how QA injects scratch roots), so an
/// operator who already set one of these keeps their value.
///
/// * `PATH` — Finder gives a GUI app `/usr/bin:/bin:/usr/sbin:/sbin`.
/// * `ENOUGH_LLAMA_SERVER` — the sidecar. `models.find_llama_server()` reads
///   it first, ahead of `~/enough/bin` and PATH.
/// * `UV_PROJECT_ENVIRONMENT` / `PYTHONPYCACHEPREFIX` — keep every write out
///   of the signed bundle. See `venv_dir` / `pycache_dir`.
pub fn apply_child_env(cmd: &mut Command, home: &Path, root: &Path) {
    cmd.env("PATH", child_path(home));

    if std::env::var_os("ENOUGH_LLAMA_SERVER").is_none() {
        if let Some(llama) = bundled::locate().llama_server {
            cmd.env("ENOUGH_LLAMA_SERVER", llama);
        }
    }
    if std::env::var_os("UV_PROJECT_ENVIRONMENT").is_none() {
        cmd.env("UV_PROJECT_ENVIRONMENT", venv_dir(home));
    }
    if is_bundled_code(root) {
        // Without this, importing `enough` from the bundle scatters
        // `__pycache__` through `Contents/Resources` — which breaks the code
        // signature of a signed .app. Redirecting keeps the caching (a 7 MB
        // package recompiled on every launch is a visible cost) and keeps the
        // writes out of the seal.
        if std::env::var_os("PYTHONPYCACHEPREFIX").is_none() {
            cmd.env("PYTHONPYCACHEPREFIX", pycache_dir(home));
        }
        if std::env::var_os("UV_PYTHON_PREFERENCE").is_none() {
            cmd.env("UV_PYTHON_PREFERENCE", "only-managed");
        }
        if std::env::var_os("UV_PYTHON").is_none() {
            cmd.env("UV_PYTHON", BUNDLED_PYTHON);
        }
    }
}

/// `uv run` argv prefix. `--frozen` only for the sealed snapshot: uv would
/// otherwise try to refresh `uv.lock` inside the bundle.
fn uv_run_args(root: &Path) -> Vec<String> {
    let mut v = vec!["run".to_string()];
    if is_bundled_code(root) {
        v.push("--frozen".to_string());
    }
    v.push("--project".to_string());
    v.push(root.display().to_string());
    v
}

fn mint_token() -> String {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    format!("{:x}-{:x}", nanos, std::process::id())
}

// ---------------------------------------------------------------------------
// Spawn / ready / stop
// ---------------------------------------------------------------------------

impl Backend {
    pub fn spawn(project: &Path, home: &Path, port: u16) -> Result<Backend, String> {
        let uv = find_uv(home)?;
        let root = code_root(home);
        if !root.join("pyproject.toml").is_file() {
            return Err(format!(
                "no enough install at {}.\n\nExpected a pyproject.toml there. \
                 Install enough first, or set ENOUGH_DESKTOP_CODE to a checkout.",
                root.display()
            ));
        }
        let token = mint_token();
        let log: Arc<Mutex<VecDeque<String>>> = Arc::new(Mutex::new(VecDeque::new()));

        let mut cmd = Command::new(&uv);
        cmd.args(uv_run_args(&root))
            .arg("enough")
            .arg("--port")
            .arg(port.to_string())
            .arg("--no-browser");
        // `--llm-url` is normally never passed (tauri-plan 2a: 8080 and the
        // supervisor's adopt-or-launch behave exactly as they do from the
        // CLI). The override exists for QA: a scratch run must be able to
        // stay off the machine's real llama-server, which is shared state the
        // ENOUGH_* hooks can't isolate.
        if let Ok(url) = std::env::var("ENOUGH_DESKTOP_LLM_URL") {
            if !url.is_empty() {
                cmd.arg("--llm-url").arg(url);
            }
        }
        cmd.current_dir(project)
            // The parent environment is inherited wholesale — that's both the
            // ENOUGH_DESKTOP_CODE dev path and the seam a QA harness uses to
            // inject scratch ENOUGH_* roots into the server we spawn.
            .env("ENOUGH_DESKTOP", "1")
            .env("ENOUGH_DESKTOP_TOKEN", &token)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            // Own process group, so the fallback SIGTERM reaches uv *and*
            // the python it spawned. llama-server is not in this group —
            // the supervisor gives it its own session (start_new_session=True),
            // which is exactly what keeps an adopted one alive.
            .process_group(0);
        apply_child_env(&mut cmd, home, &root);

        eprintln!(
            "[enough-desktop] backend code={} (snapshot {}) uv={}",
            root.display(),
            bundled::snapshot_stamp(&root),
            uv.display()
        );

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("couldn't start the backend via {}:\n{e}", uv.display()))?;

        for pipe in [
            child.stdout.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
            child.stderr.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        ]
        .into_iter()
        .flatten()
        {
            let sink = Arc::clone(&log);
            std::thread::spawn(move || {
                for line in BufReader::new(pipe).lines().map_while(Result::ok) {
                    eprintln!("[enough] {line}");
                    if let Ok(mut q) = sink.lock() {
                        q.push_back(line);
                        while q.len() > LOG_TAIL_LINES {
                            q.pop_front();
                        }
                    }
                }
            });
        }

        Ok(Backend {
            child,
            port,
            token,
            project: project.to_path_buf(),
            log,
        })
    }

    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    /// The last `n` lines the backend printed.
    pub fn log_tail(&self, n: usize) -> String {
        self.log
            .lock()
            .map(|q| {
                let skip = q.len().saturating_sub(n);
                q.iter().skip(skip).cloned().collect::<Vec<_>>().join("\n")
            })
            .unwrap_or_default()
    }

    /// Poll `/api/project` until the backend answers. Returns early with the
    /// child's own output if it dies first — that's how the ~/enough refusal
    /// and any other startup error reach the user as a readable message.
    pub fn wait_ready(&mut self, mut on_progress: impl FnMut(&str)) -> Result<(), String> {
        let started = Instant::now();
        let mut announced_slow = false;
        loop {
            if let Ok(Some(status)) = self.child.try_wait() {
                let tail = self.log_tail(DIALOG_TAIL_LINES);
                let detail = if tail.trim().is_empty() {
                    String::new()
                } else {
                    format!("\n\n{tail}")
                };
                return Err(format!(
                    "The enough backend stopped while starting up ({status}).{detail}"
                ));
            }
            if let Some(r) = http::get(self.port, "/api/project", Duration::from_millis(1200)) {
                if r.status == 200 && r.body.contains("\"folder\"") {
                    return Ok(());
                }
            }
            if !announced_slow && started.elapsed() > Duration::from_secs(8) {
                announced_slow = true;
                on_progress("still starting — uv may be syncing the environment…");
            }
            if started.elapsed() >= READY_TIMEOUT {
                break;
            }
            std::thread::sleep(READY_POLL);
        }
        Err(format!(
            "The enough backend didn't answer on port {} within {} seconds.\n\n{}",
            self.port,
            READY_TIMEOUT.as_secs(),
            self.log_tail(DIALOG_TAIL_LINES)
        ))
    }

    fn pid(&self) -> i32 {
        self.child.id() as i32
    }

    fn wait_for_exit(&mut self, budget: Duration) -> bool {
        let deadline = Instant::now() + budget;
        loop {
            match self.child.try_wait() {
                Ok(Some(_)) => return true,
                Ok(None) => {}
                Err(_) => return true, // already reaped by someone
            }
            if Instant::now() >= deadline {
                return false;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }

    fn signal_group(&self, sig: i32) {
        // Negative pid = "the whole process group", which is uv + the python
        // it spawned. Any llama-server is in its own session and unaffected.
        unsafe {
            libc::kill(-self.pid(), sig);
        }
    }

    /// Stop the backend, preferring the graceful door.
    ///
    /// 1. `POST /api/shutdown` — the backend stops an *owned* llama-server
    ///    (`only_if_owned=True`, so an adopted one lives on) and then asks
    ///    uvicorn to exit.
    /// 2. Wait for the process to actually go.
    /// 3. SIGTERM the process group. Still graceful for uvicorn — its own
    ///    signal handler runs the same lifespan teardown — just without the
    ///    endpoint's cooperation.
    /// 4. SIGKILL, last resort.
    ///
    /// Returns the rung it got off at, for the log.
    pub fn shutdown(&mut self) -> &'static str {
        let posted = http::request(
            self.port,
            "POST",
            "/api/shutdown",
            &[("X-Enough-Desktop-Token", self.token.as_str())],
            SHUTDOWN_POST_TIMEOUT,
        )
        .map(|r| r.status == 200)
        .unwrap_or(false);

        if posted && self.wait_for_exit(GRACEFUL_EXIT_WAIT) {
            return "graceful (/api/shutdown)";
        }
        // Either the POST didn't land or the process is lingering.
        if !posted && self.wait_for_exit(Duration::from_millis(300)) {
            return "already gone";
        }

        self.signal_group(libc::SIGTERM);
        if self.wait_for_exit(SIGTERM_WAIT) {
            return "SIGTERM";
        }

        self.signal_group(libc::SIGKILL);
        self.wait_for_exit(SIGKILL_WAIT);
        "SIGKILL"
    }
}
