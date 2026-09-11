#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use serde_json::Value;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const LOOPBACK: &str = "127.0.0.1:8000";
const FRONTEND_LOOPBACK: &str = "127.0.0.1:5173";
const MAX_RESPONSE_BYTES: usize = 65_536;
const MAX_COMMAND_OUTPUT_BYTES: usize = 16_384;

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

fn collect_snapshot() -> ServiceSnapshot {
    let (backend, backend_json) = json_probe("/health");
    let (readiness, _) = json_probe("/health/ready");
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

    ServiceSnapshot {
        backend,
        readiness,
        release,
        frontend,
        release_version,
        docker_services_status,
    }
}

fn candidate_roots() -> Vec<PathBuf> {
    let mut starts = Vec::new();
    if let Ok(path) = std::env::current_dir() {
        starts.push(path);
    }
    if let Ok(path) = std::env::current_exe() {
        if let Some(parent) = path.parent() {
            starts.push(parent.to_path_buf());
        }
    }
    starts
        .into_iter()
        .flat_map(|path| path.ancestors().map(Path::to_path_buf).collect::<Vec<_>>())
        .collect()
}

fn find_script(action: LocalAction) -> Option<(PathBuf, PathBuf)> {
    for root in candidate_roots() {
        let Ok(canonical_root) = root.canonicalize() else {
            continue;
        };
        if !canonical_root.join("docker-compose.yml").is_file()
            || !canonical_root.join("pyproject.toml").is_file()
            || !canonical_root.join("desktop").join("package.json").is_file()
        {
            continue;
        }
        let scripts = canonical_root.join("scripts").join("local");
        let candidate = scripts.join(action.script());
        let Ok(canonical_scripts) = scripts.canonicalize() else {
            continue;
        };
        if !canonical_scripts.starts_with(&canonical_root) {
            continue;
        }
        let Ok(canonical_script) = candidate.canonicalize() else {
            continue;
        };
        if canonical_script.parent() == Some(canonical_scripts.as_path())
            && canonical_script.file_name().and_then(|name| name.to_str()) == Some(action.script())
            && canonical_script.is_file()
        {
            return Some((canonical_root, canonical_script));
        }
    }
    None
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

fn run_whitelisted(action: LocalAction) -> LauncherResult {
    let Some((repository, script)) = find_script(action) else {
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

async fn run_action(action: LocalAction) -> LauncherResult {
    tauri::async_runtime::spawn_blocking(move || run_whitelisted(action))
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
async fn check_platform() -> LauncherResult {
    run_action(LocalAction::Check).await
}

#[tauri::command]
async fn start_platform() -> LauncherResult {
    run_action(LocalAction::Start).await
}

#[tauri::command]
async fn stop_platform() -> LauncherResult {
    run_action(LocalAction::Stop).await
}

#[tauri::command]
async fn restart_platform() -> LauncherResult {
    run_action(LocalAction::Restart).await
}

#[tauri::command]
async fn open_local_frontend() -> LauncherResult {
    run_action(LocalAction::OpenFrontend).await
}

#[tauri::command]
async fn probe_local_services() -> ServiceSnapshot {
    tauri::async_runtime::spawn_blocking(collect_snapshot)
        .await
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn launcher_resolves_only_the_expected_repository_script() {
        let (_, script) = find_script(LocalAction::Check).expect("repository check script");
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
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            probe_local_services,
            check_platform,
            start_platform,
            stop_platform,
            restart_platform,
            open_local_frontend
        ])
        .run(tauri::generate_context!())
        .expect("RavenTech OSINT desktop shell failed to start");
}
