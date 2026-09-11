#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use serde_json::Value;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

const LOOPBACK: &str = "127.0.0.1:8000";
const FRONTEND_LOOPBACK: &str = "127.0.0.1:5173";
const MAX_RESPONSE_BYTES: usize = 65_536;

#[derive(Default, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProbeResult {
    available: bool,
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
                    available: (200..300).contains(&code),
                    status,
                },
                value,
            )
        }
        None => (ProbeResult::default(), None),
    }
}

fn collect_snapshot() -> ServiceSnapshot {
    let (backend, _) = json_probe("/health");
    let (readiness, _) = json_probe("/health/ready");
    let (release, release_json) = json_probe("/api/v1/release");
    let release_version = release_json
        .as_ref()
        .and_then(|json| json.get("version"))
        .and_then(Value::as_str)
        .map(str::to_owned);
    let frontend = match fixed_http_get(FRONTEND_LOOPBACK, "/") {
        Some((code, _)) => ProbeResult {
            available: (200..400).contains(&code),
            status: Some("ok".to_owned()),
        },
        None => ProbeResult::default(),
    };

    ServiceSnapshot {
        backend,
        readiness,
        release,
        frontend,
        release_version,
    }
}

#[tauri::command]
async fn probe_local_services() -> ServiceSnapshot {
    tauri::async_runtime::spawn_blocking(collect_snapshot)
        .await
        .unwrap_or_default()
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![probe_local_services])
        .run(tauri::generate_context!())
        .expect("RavenTech OSINT desktop shell failed to start");
}
