#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;

const LOOPBACK: &str = "127.0.0.1:8000";
const FRONTEND_LOOPBACK: &str = "127.0.0.1:5173";
const MAX_RESPONSE_BYTES: usize = 65_536;
const MAX_COMMAND_OUTPUT_BYTES: usize = 16_384;
const MAX_PROJECT_PATH_CHARS: usize = 1024;
const EXPECTED_RELEASE: &str = "5.0.0-rc4";
const PROJECT_PATH_FILE: &str = "project-path.json";
const REQUIRED_SCRIPTS: [&str; 5] = [
    "start_platform.ps1",
    "stop_platform.ps1",
    "restart_platform.ps1",
    "check_platform.ps1",
    "open_platform.ps1",
];

#[derive(Default, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProbeResult {
    reachable: bool,
    healthy: bool,
    http_status: Option<u16>,
    status: Option<String>,
}

#[derive(Default, Serialize)]
#[serde(rename_all = "camelCase")]
struct ServiceSnapshot {
    backend: ProbeResult,
    readiness: ProbeResult,
    release: ProbeResult,
    frontend: ProbeResult,
    release_version: Option<String>,
    docker_services_status: Option<String>,
    docker_availability: String,
    backend_port_status: String,
    frontend_port_status: String,
    release_matches: Option<bool>,
    migration_status: Option<String>,
    setup: ProjectSetup,
}

#[derive(Default, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProjectSetup {
    configured: bool,
    configured_path: Option<String>,
    configured_path_valid: bool,
    repository_found: bool,
    repository_path: Option<String>,
    resolution_source: String,
    compose_available: bool,
    frontend_available: bool,
    backend_available: bool,
    scripts_available: bool,
    next_action: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ProjectBindingResult {
    success: bool,
    message: String,
    setup: ProjectSetup,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProjectPathPreference {
    project_path: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct LauncherResult {
    action: &'static str,
    success: bool,
    script_available: bool,
    timed_out: bool,
    exit_code: Option<i32>,
    message: String,
    output: String,
}

#[derive(Clone, Copy)]
enum LocalAction {
    Check,
    Start,
    Stop,
    Restart,
    OpenFrontend,
}

impl LocalAction {
    fn name(self) -> &'static str {
        match self {
            Self::Check => "check",
            Self::Start => "start",
            Self::Stop => "stop",
            Self::Restart => "restart",
            Self::OpenFrontend => "openFrontend",
        }
    }

    fn script(self) -> &'static str {
        match self {
            Self::Check => "check_platform.ps1",
            Self::Start => "start_platform.ps1",
            Self::Stop => "stop_platform.ps1",
            Self::Restart => "restart_platform.ps1",
            Self::OpenFrontend => "open_platform.ps1",
        }
    }

    fn timeout(self) -> Duration {
        match self {
            Self::Start | Self::Restart => Duration::from_secs(150),
            Self::Stop => Duration::from_secs(60),
            Self::Check => Duration::from_secs(90),
            Self::OpenFrontend => Duration::from_secs(20),
        }
    }
}

fn fixed_http_get(address: &str, path: &str) -> Option<(u16, String)> {
    let address: SocketAddr = address.parse().ok()?;
    let timeout = Duration::from_secs(2);
    let mut stream = TcpStream::connect_timeout(&address, timeout).ok()?;
    stream.set_read_timeout(Some(timeout)).ok()?;
    stream.set_write_timeout(Some(timeout)).ok()?;

    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).ok()?;

    let mut bytes = Vec::new();
    stream
        .take(MAX_RESPONSE_BYTES as u64)
        .read_to_end(&mut bytes)
        .ok()?;
    let response = String::from_utf8_lossy(&bytes);
    let (headers, body) = response.split_once("\r\n\r\n")?;
    let status = headers
        .lines()
        .next()?
        .split_whitespace()
        .nth(1)?
        .parse::<u16>()
        .ok()?;
    Some((status, body.to_owned()))
}

fn json_probe(path: &str) -> (ProbeResult, Option<Value>) {
    match fixed_http_get(LOOPBACK, path) {
        Some((code, body)) => {
            let value = serde_json::from_str::<Value>(&body).ok();
            let status = value
                .as_ref()
                .and_then(|json| json.get("status"))
                .and_then(Value::as_str)
                .map(str::to_owned);
            (
                ProbeResult {
                    reachable: true,
                    healthy: (200..300).contains(&code)
                        && status.as_deref() == Some("ok"),
                    http_status: Some(code),
                    status,
                },
                value,
            )
        }
        None => (ProbeResult::default(), None),
    }
}

fn port_status(address: &str, service_reachable: bool) -> String {
    if service_reachable {
        return "application".to_owned();
    }
    let open = address
        .parse::<SocketAddr>()
        .ok()
        .and_then(|address| TcpStream::connect_timeout(&address, Duration::from_millis(500)).ok())
        .is_some();
    if open { "occupied" } else { "available" }.to_owned()
}

fn docker_cli_detected() -> bool {
    std::env::var_os("ProgramFiles")
        .map(PathBuf::from)
        .map(|root| {
            root.join("Docker")
                .join("Docker")
                .join("resources")
                .join("bin")
                .join("docker.exe")
                .is_file()
        })
        .unwrap_or(false)
}

fn collect_snapshot(app: &tauri::AppHandle) -> ServiceSnapshot {
    let (backend, backend_json) = json_probe("/health");
    let (readiness, readiness_json) = json_probe("/health/ready");
    let (release, release_json) = json_probe("/api/v1/release");
    let release_version = release_json
        .as_ref()
        .and_then(|json| json.get("version"))
        .and_then(Value::as_str)
        .map(str::to_owned);
    let frontend = match fixed_http_get(FRONTEND_LOOPBACK, "/") {
        Some((code, _)) => ProbeResult {
            reachable: true,
            healthy: (200..400).contains(&code),
            http_status: Some(code),
            status: Some(if (200..400).contains(&code) {
                "ok".to_owned()
            } else {
                "error".to_owned()
            }),
        },
        None => ProbeResult::default(),
    };
    let docker_services_status = backend_json.as_ref().map(|json| {
        let checks = json.get("checks");
        let ready = ["database", "redis", "worker"].iter().all(|name| {
            checks
                .and_then(|value| value.get(name))
                .and_then(|value| value.get("status"))
                .and_then(Value::as_str)
                == Some("ok")
        });
        if ready { "ready" } else { "degraded" }.to_owned()
    });
    let migration_status = readiness_json
        .as_ref()
        .and_then(|json| json.get("checks"))
        .and_then(|checks| checks.get("migrations"))
        .and_then(|migration| migration.get("status"))
        .and_then(Value::as_str)
        .map(str::to_owned);
    let docker_availability = if backend.reachable {
        "running"
    } else if docker_cli_detected() {
        "installed"
    } else {
        "notDetected"
    }
    .to_owned();
    let backend_port_status = port_status(LOOPBACK, backend.reachable);
    let frontend_port_status = port_status(FRONTEND_LOOPBACK, frontend.reachable);
    let release_matches = release_version
        .as_deref()
        .map(|version| version == EXPECTED_RELEASE);
    let setup = project_setup(app);

    ServiceSnapshot {
        backend,
        readiness,
        release,
        frontend,
        release_version,
        docker_services_status,
        docker_availability,
        backend_port_status,
        frontend_port_status,
        release_matches,
        migration_status,
        setup,
    }
}

fn preference_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|directory| directory.join(PROJECT_PATH_FILE))
}

fn configured_project_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let path = preference_path(app)?;
    let bytes = fs::read(path).ok()?;
    if bytes.len() > 4096 {
        return None;
    }
    let preference = serde_json::from_slice::<ProjectPathPreference>(&bytes).ok()?;
    let value = preference.project_path.trim();
    (!value.is_empty() && value.chars().count() <= MAX_PROJECT_PATH_CHARS)
        .then(|| PathBuf::from(value))
}

fn canonical_child(root: &Path, relative: &Path, file: bool) -> bool {
    let Ok(path) = root.join(relative).canonicalize() else {
        return false;
    };
    path.starts_with(root) && if file { path.is_file() } else { path.is_dir() }
}

fn trusted_script_bytes(name: &str) -> Option<&'static [u8]> {
    match name {
        "start_platform.ps1" => Some(include_bytes!("../../../scripts/local/start_platform.ps1")),
        "stop_platform.ps1" => Some(include_bytes!("../../../scripts/local/stop_platform.ps1")),
        "restart_platform.ps1" => Some(include_bytes!("../../../scripts/local/restart_platform.ps1")),
        "check_platform.ps1" => Some(include_bytes!("../../../scripts/local/check_platform.ps1")),
        "open_platform.ps1" => Some(include_bytes!("../../../scripts/local/open_platform.ps1")),
        _ => None,
    }
}

fn trusted_script(root: &Path, name: &str) -> bool {
    let relative = Path::new("scripts/local").join(name);
    if !canonical_child(root, &relative, true) {
        return false;
    }
    let Some(expected) = trusted_script_bytes(name) else {
        return false;
    };
    fs::read(root.join(relative))
        .map(|bytes| bytes == expected)
        .unwrap_or(false)
}

fn validate_repository_root(path: &Path) -> Option<PathBuf> {
    let root = path.canonicalize().ok()?;
    if !root.is_dir()
        || !canonical_child(&root, Path::new("docker-compose.yml"), true)
        || !canonical_child(&root, Path::new("pyproject.toml"), true)
        || !canonical_child(&root, Path::new("desktop/package.json"), true)
        || !canonical_child(&root, Path::new("frontend/package.json"), true)
        || !canonical_child(&root, Path::new("backend/app"), false)
    {
        return None;
    }
    let scripts = root.join("scripts").join("local");
    let canonical_scripts = scripts.canonicalize().ok()?;
    if !canonical_scripts.starts_with(&root)
        || REQUIRED_SCRIPTS
            .iter()
            .any(|name| !trusted_script(&root, name))
    {
        return None;
    }
    Some(root)
}

fn ancestor_roots(start: PathBuf) -> Vec<PathBuf> {
    start.ancestors().map(Path::to_path_buf).collect()
}

fn resolve_repository(app: &tauri::AppHandle) -> Option<(PathBuf, &'static str)> {
    if let Some(configured) = configured_project_path(app) {
        if let Some(root) = validate_repository_root(&configured) {
            return Some((root, "configured"));
        }
    }
    if let Ok(current) = std::env::current_dir() {
        for candidate in ancestor_roots(current) {
            if let Some(root) = validate_repository_root(&candidate) {
                return Some((root, "currentDirectory"));
            }
        }
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            for candidate in ancestor_roots(parent.to_path_buf()) {
                if let Some(root) = validate_repository_root(&candidate) {
                    return Some((root, "developmentRelative"));
                }
            }
        }
    }
    None
}

fn project_setup(app: &tauri::AppHandle) -> ProjectSetup {
    let configured_path = configured_project_path(app);
    let configured_path_valid = configured_path
        .as_deref()
        .and_then(validate_repository_root)
        .is_some();
    let resolved = resolve_repository(app);
    let repository = resolved.as_ref().map(|(root, _)| root);
    let resolution_source = resolved
        .as_ref()
        .map(|(_, source)| *source)
        .unwrap_or("copyOnly");
    let scripts_available = repository.is_some_and(|root| {
        REQUIRED_SCRIPTS.iter().all(|name| trusted_script(root, name))
    });
    let next_action = if configured_path.is_some() && !configured_path_valid {
        "correctProjectPath"
    } else if repository.is_none() {
        "bindProjectPath"
    } else if !scripts_available {
        "restoreScripts"
    } else {
        "checkRuntime"
    };
    ProjectSetup {
        configured: configured_path.is_some(),
        configured_path: configured_path.map(|path| path.to_string_lossy().to_string()),
        configured_path_valid,
        repository_found: repository.is_some(),
        repository_path: repository.map(|path| path.to_string_lossy().to_string()),
        resolution_source: resolution_source.to_owned(),
        compose_available: repository.is_some_and(|root| canonical_child(root, Path::new("docker-compose.yml"), true)),
        frontend_available: repository.is_some_and(|root| canonical_child(root, Path::new("frontend/package.json"), true)),
        backend_available: repository.is_some_and(|root| canonical_child(root, Path::new("backend/app"), false)),
        scripts_available,
        next_action: next_action.to_owned(),
    }
}

fn find_script(app: &tauri::AppHandle, action: LocalAction) -> Option<(PathBuf, PathBuf)> {
    let (root, _) = resolve_repository(app)?;
    let scripts = root.join("scripts").join("local").canonicalize().ok()?;
    let script = scripts.join(action.script()).canonicalize().ok()?;
    (scripts.starts_with(&root)
        && script.parent() == Some(scripts.as_path())
        && script.file_name().and_then(|name| name.to_str()) == Some(action.script())
        && trusted_script(&root, action.script()))
    .then_some((root, script))
}

fn powershell_path() -> Option<PathBuf> {
    let system_root = PathBuf::from(std::env::var_os("SystemRoot")?);
    let executable = system_root
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe")
        .canonicalize()
        .ok()?;
    (executable.is_file()
        && executable.file_name().and_then(|name| name.to_str()) == Some("powershell.exe"))
    .then_some(executable)
}

fn read_capped(mut reader: impl Read) -> Vec<u8> {
    let mut captured = Vec::new();
    let mut chunk = [0_u8; 2048];
    while let Ok(read) = reader.read(&mut chunk) {
        if read == 0 {
            break;
        }
        let remaining = MAX_COMMAND_OUTPUT_BYTES.saturating_sub(captured.len());
        if remaining > 0 {
            captured.extend_from_slice(&chunk[..read.min(remaining)]);
        }
    }
    captured
}

fn sanitize_output(bytes: &[u8], repository: &Path) -> String {
    let raw = String::from_utf8_lossy(bytes)
        .replace(&repository.to_string_lossy().to_string(), "[repository]")
        .replace('\0', "");
    let sensitive = [
        "api_key", "api-key", "access_token", "access-token", "password", "secret",
        "credential", "database_url", "redis_url", "supabase",
    ];
    let mut lines = Vec::new();
    for line in raw.lines().take(40) {
        let cleaned: String = line
            .chars()
            .filter(|character| !character.is_control() || *character == '\t')
            .take(300)
            .collect();
        if sensitive.iter().any(|marker| cleaned.to_lowercase().contains(marker)) {
            lines.push("[sensitive output removed]".to_owned());
        } else if !cleaned.trim().is_empty() {
            lines.push(cleaned);
        }
    }
    lines.join("\n")
}

fn unavailable(action: LocalAction) -> LauncherResult {
    LauncherResult {
        action: action.name(),
        success: false,
        script_available: false,
        timed_out: false,
        exit_code: None,
        message: "The RavenTech repository scripts were not found. Use the copy-only command from the repository root.".to_owned(),
        output: String::new(),
    }
}

fn run_whitelisted(app: &tauri::AppHandle, action: LocalAction) -> LauncherResult {
    let Some((repository, script)) = find_script(app, action) else {
        return unavailable(action);
    };
    let Some(powershell) = powershell_path() else {
        return LauncherResult {
            action: action.name(),
            success: false,
            script_available: true,
            timed_out: false,
            exit_code: None,
            message: "Windows PowerShell is unavailable. Use the copy-only fallback.".to_owned(),
            output: String::new(),
        };
    };
    let mut child = match Command::new(&powershell)
        .args(["-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(&script)
        .current_dir(&repository)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(_) => {
            return LauncherResult {
                action: action.name(),
                success: false,
                script_available: true,
                timed_out: false,
                exit_code: None,
                message: "Windows PowerShell could not be started. Use the copy-only fallback.".to_owned(),
                output: String::new(),
            };
        }
    };

    let stdout = child.stdout.take().map(|pipe| thread::spawn(move || read_capped(pipe)));
    let stderr = child.stderr.take().map(|pipe| thread::spawn(move || read_capped(pipe)));
    let started = Instant::now();
    let mut timed_out = false;
    let mut wait_failed = false;
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) if started.elapsed() < action.timeout() => thread::sleep(Duration::from_millis(100)),
            Ok(None) => {
                timed_out = true;
                let _ = child.kill();
                break child.wait().ok();
            }
            Err(_) => {
                wait_failed = true;
                let _ = child.kill();
                let _ = child.wait();
                break None;
            }
        }
    };
    let (mut combined, stderr) = if timed_out || wait_failed {
        // Dropping the join handles detaches the drain threads. This guarantees
        // that a descendant retaining PowerShell's pipe cannot block the UI.
        (Vec::new(), Vec::new())
    } else {
        (
            stdout.and_then(|handle| handle.join().ok()).unwrap_or_default(),
            stderr.and_then(|handle| handle.join().ok()).unwrap_or_default(),
        )
    };
    if !combined.is_empty() && !stderr.is_empty() {
        combined.push(b'\n');
    }
    combined.extend(stderr);
    let success = !timed_out && status.as_ref().is_some_and(std::process::ExitStatus::success);
    let message = if timed_out {
        "The approved script exceeded its time limit. Check platform status before retrying."
    } else if success {
        "The approved local script completed."
    } else {
        "The approved local script did not complete successfully. Review the sanitized result or use the copy-only fallback."
    };
    LauncherResult {
        action: action.name(),
        success,
        script_available: true,
        timed_out,
        exit_code: status.and_then(|value| value.code()),
        message: message.to_owned(),
        output: sanitize_output(&combined, &repository),
    }
}

async fn run_action(app: tauri::AppHandle, action: LocalAction) -> LauncherResult {
    tauri::async_runtime::spawn_blocking(move || run_whitelisted(&app, action))
        .await
        .unwrap_or_else(|_| LauncherResult {
            action: action.name(),
            success: false,
            script_available: true,
            timed_out: false,
            exit_code: None,
            message: "The controlled launcher was interrupted. Use the copy-only fallback.".to_owned(),
            output: String::new(),
        })
}

#[tauri::command]
async fn check_platform(app: tauri::AppHandle) -> LauncherResult {
    run_action(app, LocalAction::Check).await
}

#[tauri::command]
async fn start_platform(app: tauri::AppHandle) -> LauncherResult {
    run_action(app, LocalAction::Start).await
}

#[tauri::command]
async fn stop_platform(app: tauri::AppHandle) -> LauncherResult {
    run_action(app, LocalAction::Stop).await
}

#[tauri::command]
async fn restart_platform(app: tauri::AppHandle) -> LauncherResult {
    run_action(app, LocalAction::Restart).await
}

#[tauri::command]
async fn open_local_frontend(app: tauri::AppHandle) -> LauncherResult {
    run_action(app, LocalAction::OpenFrontend).await
}

#[tauri::command]
async fn probe_local_services(app: tauri::AppHandle) -> ServiceSnapshot {
    tauri::async_runtime::spawn_blocking(move || collect_snapshot(&app))
        .await
        .unwrap_or_default()
}

#[tauri::command]
async fn get_project_setup(app: tauri::AppHandle) -> ProjectSetup {
    project_setup(&app)
}

#[tauri::command]
async fn bind_project_path(
    app: tauri::AppHandle,
    project_path: String,
) -> ProjectBindingResult {
    let value = project_path.trim();
    if value.is_empty() || value.chars().count() > MAX_PROJECT_PATH_CHARS || value.contains('\0') {
        return ProjectBindingResult {
            success: false,
            message: "Enter a valid local RavenTech repository path.".to_owned(),
            setup: project_setup(&app),
        };
    }
    let Some(root) = validate_repository_root(Path::new(value)) else {
        return ProjectBindingResult {
            success: false,
            message: "That path does not contain the required RavenTech repository structure and five approved scripts.".to_owned(),
            setup: project_setup(&app),
        };
    };
    let Some(preference) = preference_path(&app) else {
        return ProjectBindingResult {
            success: false,
            message: "The desktop preference location is unavailable. Automatic discovery and copy-only fallback remain available.".to_owned(),
            setup: project_setup(&app),
        };
    };
    let payload = ProjectPathPreference {
        project_path: root.to_string_lossy().to_string(),
    };
    let stored = preference
        .parent()
        .is_some_and(|directory| fs::create_dir_all(directory).is_ok())
        && serde_json::to_vec(&payload)
            .ok()
            .is_some_and(|bytes| fs::write(&preference, bytes).is_ok());
    ProjectBindingResult {
        success: stored,
        message: if stored {
            "Project path validated and saved for this desktop user."
        } else {
            "The validated path could not be saved. Automatic discovery and copy-only fallback remain available."
        }
        .to_owned(),
        setup: project_setup(&app),
    }
}

#[tauri::command]
async fn clear_project_path(app: tauri::AppHandle) -> ProjectBindingResult {
    let success = preference_path(&app)
        .map_or(true, |path| !path.exists() || fs::remove_file(path).is_ok());
    ProjectBindingResult {
        success,
        message: if success {
            "Saved project path cleared. Automatic discovery and copy-only fallback remain available."
        } else {
            "The saved project path could not be cleared."
        }
        .to_owned(),
        setup: project_setup(&app),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn launcher_resolves_only_the_expected_repository_script() {
        let root = validate_repository_root(Path::new(env!("CARGO_MANIFEST_DIR")).join("../..").as_path())
            .expect("repository root");
        let scripts = root.join("scripts").join("local").canonicalize().expect("scripts");
        let script = scripts.join(LocalAction::Check.script()).canonicalize().expect("check script");
        assert_eq!(
            script.file_name().and_then(|name| name.to_str()),
            Some("check_platform.ps1")
        );
        assert_eq!(
            script
                .parent()
                .and_then(Path::file_name)
                .and_then(|name| name.to_str()),
            Some("local")
        );
    }

    #[test]
    fn launcher_output_is_redacted_and_path_sanitized() {
        let repository = Path::new(r"C:\safe\repository");
        let output = sanitize_output(
            b"Health: ok\npassword=do-not-print\nC:\\safe\\repository\\scripts\\local\n",
            repository,
        );
        assert!(output.contains("Health: ok"));
        assert!(output.contains("[sensitive output removed]"));
        assert!(output.contains("[repository]"));
        assert!(!output.contains("do-not-print"));
    }

    #[test]
    fn invalid_repository_path_is_rejected() {
        assert!(validate_repository_root(Path::new(env!("CARGO_MANIFEST_DIR"))).is_none());
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            probe_local_services,
            check_platform,
            start_platform,
            stop_platform,
            restart_platform,
            open_local_frontend,
            get_project_setup,
            bind_project_path,
            clear_project_path
        ])
        .run(tauri::generate_context!())
        .expect("RavenTech OSINT desktop shell failed to start");
}
