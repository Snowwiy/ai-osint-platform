//! Fixed-schema writer for non-secret, explicitly confirmed LAN settings.

use serde::Deserialize;
use std::collections::BTreeSet;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::net::Ipv4Addr;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_CONFIG_BYTES: u64 = 1024 * 1024;
const MAX_CIDRS: usize = 16;
const MAX_PORTS: usize = 32;
const MAX_HOSTS_PER_CIDR: u64 = 256;
const PROFILE_KEYS: [&str; 19] = [
    "DESKTOP_AUTO_MONITORING_ENABLED",
    "MONITORING_AUTO_REFRESH_ENABLED",
    "MONITORING_AUTO_REFRESH_SECONDS",
    "LAN_MONITORING_ENABLED",
    "LAN_ALLOWED_CIDRS",
    "LAN_GATEWAY_HINT",
    "LAN_DISCOVERY_PING_ENABLED",
    "LAN_DISCOVERY_CONCURRENCY",
    "LAN_SERVICE_CHECK_ENABLED",
    "LAN_AUTO_DISCOVERY_ON_START",
    "LAN_AUTO_SERVICE_CHECK_ON_START",
    "LAN_AUTO_DISCOVERY_INTERVAL_SECONDS",
    "LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS",
    "LAN_SERVICE_CHECK_PORTS",
    "LAN_SERVICE_CHECK_TIMEOUT_SECONDS",
    "LAN_SERVICE_CHECK_MAX_HOSTS",
    "LAN_SERVICE_CHECK_MAX_PORTS",
    "LAN_REJECT_PUBLIC_CIDRS",
    "LAN_SSH_BANNER_DETECTION_ENABLED",
];

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LanMonitoringProfile {
    pub allowed_cidrs: Vec<String>,
    pub gateway_hint: String,
    pub service_ports: Vec<u16>,
}

#[derive(Debug, PartialEq, Eq)]
struct ValidatedProfile {
    cidrs: Vec<String>,
    gateway: Ipv4Addr,
    ports: Vec<u16>,
}

fn private_ipv4(address: Ipv4Addr) -> bool {
    let [first, second, _, _] = address.octets();
    first == 10
        || (first == 172 && (16..=31).contains(&second))
        || (first == 192 && second == 168)
}

fn parse_cidr(value: &str) -> Result<(String, u32, u32, u64), &'static str> {
    let (address, prefix) = value.trim().split_once('/').ok_or("invalid_cidr")?;
    let address = address.parse::<Ipv4Addr>().map_err(|_| "invalid_cidr")?;
    let prefix = prefix.parse::<u8>().map_err(|_| "invalid_cidr")?;
    if prefix > 32 || !private_ipv4(address) {
        return Err("private_cidr_required");
    }
    let mask = if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - u32::from(prefix))
    };
    let network = u32::from(address) & mask;
    let broadcast = network | !mask;
    let address_count = 1_u64 << (32 - u32::from(prefix));
    if address_count > MAX_HOSTS_PER_CIDR || prefix < 24 {
        return Err("cidr_exceeds_host_limit");
    }
    if prefix < 31 && (u32::from(address) == network || u32::from(address) == broadcast) {
        return Err("network_or_broadcast_address");
    }
    let normalized = format!("{}/{}", Ipv4Addr::from(network), prefix);
    Ok((normalized, network, broadcast, address_count))
}

fn validate_profile(input: &LanMonitoringProfile) -> Result<ValidatedProfile, &'static str> {
    if input.allowed_cidrs.is_empty() || input.allowed_cidrs.len() > MAX_CIDRS {
        return Err("cidr_count_out_of_range");
    }
    let mut cidrs = BTreeSet::new();
    let mut ranges = Vec::new();
    for value in &input.allowed_cidrs {
        let (normalized, network, broadcast, _count) = parse_cidr(value)?;
        if cidrs.insert(normalized) {
            ranges.push((network, broadcast));
        }
    }
    if cidrs.is_empty() {
        return Err("cidr_count_out_of_range");
    }
    let gateway = input
        .gateway_hint
        .trim()
        .parse::<Ipv4Addr>()
        .map_err(|_| "invalid_gateway")?;
    let gateway_value = u32::from(gateway);
    let gateway_range = ranges.iter().find(|(network, broadcast)| {
        gateway_value >= *network && gateway_value <= *broadcast
    });
    if !private_ipv4(gateway)
        || gateway_range.is_none()
        || gateway_range.is_some_and(|(network, broadcast)| {
            gateway_value == *network || gateway_value == *broadcast
        })
    {
        return Err("gateway_outside_authorized_networks");
    }
    if input.service_ports.is_empty() || input.service_ports.len() > MAX_PORTS {
        return Err("port_count_out_of_range");
    }
    let ports: BTreeSet<u16> = input.service_ports.iter().copied().collect();
    if ports.contains(&0) {
        return Err("invalid_port");
    }
    Ok(ValidatedProfile {
        cidrs: cidrs.into_iter().collect(),
        gateway,
        ports: ports.into_iter().collect(),
    })
}

fn profile_lines(profile: &ValidatedProfile) -> Vec<String> {
    vec![
        "DESKTOP_AUTO_MONITORING_ENABLED=true".to_owned(),
        "MONITORING_AUTO_REFRESH_ENABLED=true".to_owned(),
        "MONITORING_AUTO_REFRESH_SECONDS=30".to_owned(),
        "LAN_MONITORING_ENABLED=true".to_owned(),
        format!("LAN_ALLOWED_CIDRS={}", profile.cidrs.join(",")),
        format!("LAN_GATEWAY_HINT={}", profile.gateway),
        "LAN_DISCOVERY_PING_ENABLED=true".to_owned(),
        "LAN_DISCOVERY_CONCURRENCY=16".to_owned(),
        "LAN_SERVICE_CHECK_ENABLED=true".to_owned(),
        "LAN_AUTO_DISCOVERY_ON_START=true".to_owned(),
        "LAN_AUTO_SERVICE_CHECK_ON_START=true".to_owned(),
        "LAN_AUTO_DISCOVERY_INTERVAL_SECONDS=300".to_owned(),
        "LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS=600".to_owned(),
        format!(
            "LAN_SERVICE_CHECK_PORTS={}",
            profile
                .ports
                .iter()
                .map(u16::to_string)
                .collect::<Vec<_>>()
                .join(",")
        ),
        "LAN_SERVICE_CHECK_TIMEOUT_SECONDS=2".to_owned(),
        "LAN_SERVICE_CHECK_MAX_HOSTS=256".to_owned(),
        "LAN_SERVICE_CHECK_MAX_PORTS=32".to_owned(),
        "LAN_REJECT_PUBLIC_CIDRS=true".to_owned(),
        "LAN_SSH_BANNER_DETECTION_ENABLED=true".to_owned(),
    ]
}

fn link_or_reparse(metadata: &fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        return metadata.file_attributes() & 0x400 != 0;
    }
    #[cfg(not(windows))]
    false
}

fn next_sibling(path: &Path, suffix: &str) -> Result<PathBuf, &'static str> {
    let parent = path.parent().ok_or("invalid_config_path")?;
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or("invalid_config_path")?;
    for attempt in 0..32_u32 {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "clock_unavailable")?;
        let candidate = parent.join(format!(
            "{}.{}-{}-{}{}",
            name,
            suffix,
            nonce.as_secs(),
            nonce.subsec_nanos(),
            if attempt == 0 {
                String::new()
            } else {
                format!("-{attempt}")
            }
        ));
        if !candidate.exists() {
            return Ok(candidate);
        }
    }
    Err("temporary_path_unavailable")
}

fn create_private_file(path: &Path) -> Result<File, &'static str> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    options.open(path).map_err(|_| "config_write_failed")
}

fn write_backup(path: &Path, contents: &[u8]) -> Result<String, &'static str> {
    let backup = next_sibling(path, "backup")?;
    let mut file = create_private_file(&backup)?;
    file.write_all(contents)
        .and_then(|_| file.sync_all())
        .map_err(|_| "config_backup_failed")?;
    Ok(backup
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(".env.backup")
        .to_owned())
}

fn atomic_write(path: &Path, contents: &[u8]) -> Result<(), &'static str> {
    let temporary = next_sibling(path, "tmp")?;
    let mut file = create_private_file(&temporary)?;
    if file.write_all(contents).and_then(|_| file.sync_all()).is_err() {
        let _ = fs::remove_file(&temporary);
        return Err("config_write_failed");
    }
    drop(file);
    if fs::rename(&temporary, path).is_err() {
        let _ = fs::remove_file(&temporary);
        return Err("config_replace_failed");
    }
    #[cfg(unix)]
    if let Some(parent) = path.parent() {
        if let Ok(directory) = File::open(parent) {
            let _ = directory.sync_all();
        }
    }
    Ok(())
}

pub fn apply_lan_monitoring_profile(
    path: &Path,
    input: &LanMonitoringProfile,
    confirmed: bool,
) -> Result<Option<String>, &'static str> {
    if !confirmed {
        return Err("confirmation_required");
    }
    let profile = validate_profile(input)?;
    let parent = path.parent().ok_or("invalid_config_path")?;
    fs::create_dir_all(parent).map_err(|_| "config_directory_unavailable")?;
    let parent_metadata = fs::symlink_metadata(parent).map_err(|_| "config_directory_unavailable")?;
    if !parent_metadata.is_dir() || link_or_reparse(&parent_metadata) {
        return Err("config_directory_unsafe");
    }

    let existing = match fs::symlink_metadata(path) {
        Ok(metadata) if !metadata.is_file() || link_or_reparse(&metadata) => {
            return Err("config_file_unsafe");
        }
        Ok(metadata) if metadata.len() > MAX_CONFIG_BYTES => return Err("config_file_too_large"),
        Ok(_) => Some(fs::read(path).map_err(|_| "config_read_failed")?),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
        Err(_) => return Err("config_read_failed"),
    };
    let original = existing.as_deref().unwrap_or_default();
    let text = std::str::from_utf8(original).map_err(|_| "config_encoding_invalid")?;
    if text.contains('\0') {
        return Err("config_encoding_invalid");
    }
    let mut kept = Vec::new();
    for line in text.lines() {
        let key = line
            .split_once('=')
            .map(|(key, _)| key.trim())
            .unwrap_or_default();
        if !PROFILE_KEYS.contains(&key) {
            kept.push(line.to_owned());
        }
    }
    kept.extend(profile_lines(&profile));
    let mut output = kept.join("\n");
    output.push('\n');

    let backup = if let Some(existing) = existing {
        Some(write_backup(path, &existing)?)
    } else {
        None
    };
    atomic_write(path, output.as_bytes())?;
    Ok(backup)
}

#[cfg(test)]
mod tests {
    use super::{apply_lan_monitoring_profile, LanMonitoringProfile};
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn test_dir() -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("raventech-lan-config-{nonce}"));
        fs::create_dir_all(&path).expect("test directory");
        path
    }

    fn valid_profile() -> LanMonitoringProfile {
        LanMonitoringProfile {
            allowed_cidrs: vec!["192.168.50.37/24".to_owned()],
            gateway_hint: "192.168.50.1".to_owned(),
            service_ports: vec![443, 22, 443],
        }
    }

    #[test]
    fn config_apply_preserves_unknown_values_and_creates_safe_backup() {
        let directory = test_dir();
        let path = directory.join(".env");
        fs::write(
            &path,
            "DATABASE_URL=placeholder-connection\nLAN_MONITORING_ENABLED=false\nCUSTOM_SETTING=kept\n",
        )
        .expect("seed config");
        let backup = apply_lan_monitoring_profile(&path, &valid_profile(), true)
            .expect("apply profile")
            .expect("backup name");
        let output = fs::read_to_string(&path).expect("read updated config");
        let saved = fs::read_to_string(directory.join(backup)).expect("read backup");
        assert!(output.contains("DATABASE_URL=placeholder-connection"));
        assert!(output.contains("CUSTOM_SETTING=kept"));
        assert!(output.contains("LAN_ALLOWED_CIDRS=192.168.50.0/24"));
        assert!(output.contains("LAN_AUTO_DISCOVERY_ON_START=true"));
        assert_eq!(saved, "DATABASE_URL=placeholder-connection\nLAN_MONITORING_ENABLED=false\nCUSTOM_SETTING=kept\n");
        assert!(!output.contains("LAN_MONITORING_ENABLED=false"));
        fs::remove_dir_all(directory).expect("remove isolated test directory");
    }

    #[test]
    fn config_apply_rejects_public_or_oversized_networks_and_unconfirmed_writes() {
        let directory = test_dir();
        let path = directory.join(".env");
        let mut profile = valid_profile();
        profile.allowed_cidrs = vec!["8.8.8.0/24".to_owned()];
        assert_eq!(
            apply_lan_monitoring_profile(&path, &profile, true),
            Err("private_cidr_required")
        );
        profile.allowed_cidrs = vec!["10.0.0.0/16".to_owned()];
        assert_eq!(
            apply_lan_monitoring_profile(&path, &profile, true),
            Err("cidr_exceeds_host_limit")
        );
        assert_eq!(
            apply_lan_monitoring_profile(&path, &valid_profile(), false),
            Err("confirmation_required")
        );
        assert!(!path.exists());
        fs::remove_dir_all(directory).expect("remove isolated test directory");
    }

    #[test]
    fn config_apply_rejects_gateway_and_port_outside_the_fixed_schema() {
        let directory = test_dir();
        let path = directory.join(".env");
        let mut profile = valid_profile();
        profile.gateway_hint = "192.168.51.1".to_owned();
        assert_eq!(
            apply_lan_monitoring_profile(&path, &profile, true),
            Err("gateway_outside_authorized_networks")
        );
        profile = valid_profile();
        profile.service_ports = vec![0];
        assert_eq!(
            apply_lan_monitoring_profile(&path, &profile, true),
            Err("invalid_port")
        );
        assert!(!path.exists());
        fs::remove_dir_all(directory).expect("remove isolated test directory");
    }

    #[test]
    fn gateway_is_checked_against_its_containing_range_only() {
        let profile = LanMonitoringProfile {
            allowed_cidrs: vec!["192.168.50.37/24".to_owned(), "192.168.51.37/24".to_owned()],
            gateway_hint: "192.168.50.1".to_owned(),
            service_ports: vec![443],
        };
        let directory = test_dir();
        let path = directory.join(".env");
        let result = apply_lan_monitoring_profile(&path, &profile, true);
        assert!(result.is_ok(), "unexpected profile validation failure: {result:?}");
        fs::remove_dir_all(directory).expect("remove isolated test directory");
    }
}
