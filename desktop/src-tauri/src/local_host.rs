//! Native, local-only host inventory and narrowly scoped administrative actions.

use serde::Serialize;
use sysinfo::System;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessItem {
    pub pid: u32,
    pub name: String,
    pub cpu_percent: f32,
    pub memory_bytes: u64,
    pub started_at_unix: u64,
    pub creation_ticks: Option<String>,
    pub runtime_seconds: u64,
    pub action_available: bool,
    pub action_reason: String,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceItem {
    pub name: String,
    pub display_name: String,
    pub state: String,
    pub start_type: Option<String>,
    pub pid: Option<u32>,
    pub description: Option<String>,
    pub sub_state: Option<String>,
    pub enabled: Option<bool>,
    pub started_at_unix: Option<u64>,
    pub action_available: bool,
    pub action_reason: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostInventory {
    pub available: bool,
    pub processes: Vec<ProcessItem>,
    pub services: Vec<ServiceItem>,
    pub detail: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActionResult {
    pub success: bool,
    pub previous_state: String,
    pub resulting_state: String,
    pub message: String,
}

const CORE_PROCESSES: &[&str] = &[
    "system",
    "registry",
    "smss",
    "csrss",
    "wininit",
    "services",
    "lsass",
    "winlogon",
    "secure system",
    "dwm",
    "fontdrvhost",
    "memory compression",
    "svchost",
    "sihost",
    "explorer",
    "taskhostw",
    "spoolsv",
    "raventech-osint-desktop",
];
const CORE_SERVICES: &[&str] = &[
    "rpcss",
    "dcomlaunch",
    "rpceptmapper",
    "eventlog",
    "plugplay",
    "samss",
    "windefend",
    "mpssvc",
    "trustedinstaller",
    "winmgmt",
    "schedule",
    "lanmanworkstation",
    "lanmanserver",
    "profsvc",
    "cryptsvc",
    "gpsvc",
];

pub fn process_protection_reason(name: &str, pid: u32) -> Option<&'static str> {
    let normalized = name.trim().to_ascii_lowercase();
    let stem = normalized.strip_suffix(".exe").unwrap_or(&normalized);
    if pid <= 4 || pid == std::process::id() || CORE_PROCESSES.contains(&stem) {
        Some("Protected system or RavenTech desktop process")
    } else {
        None
    }
}

pub fn service_protection_reason(name: &str) -> Option<&'static str> {
    if CORE_SERVICES.contains(&name.to_ascii_lowercase().as_str()) {
        Some("Protected Windows service")
    } else {
        None
    }
}

fn process_items() -> Vec<ProcessItem> {
    let mut system = System::new_all();
    std::thread::sleep(std::time::Duration::from_millis(150));
    system.refresh_all();
    let mut items: Vec<_> = system
        .processes()
        .iter()
        .map(|(pid, process)| {
            let pid = pid.as_u32();
            let name = process.name().to_string();
            #[cfg(target_os = "windows")]
            let creation_ticks =
                windows::process_creation_ticks(pid).map(|value| value.to_string());
            #[cfg(target_os = "linux")]
            let creation_ticks = linux::process_creation_ticks(pid);
            #[cfg(not(any(target_os = "windows", target_os = "linux")))]
            let creation_ticks = None;
            let reason = process_protection_reason(&name, pid).or_else(|| {
                #[cfg(target_os = "windows")]
                {
                    if creation_ticks.is_none() {
                        Some("Windows did not permit process identity verification")
                    } else {
                        windows::critical_process_reason(pid)
                    }
                }
                #[cfg(target_os = "linux")]
                {
                    linux::process_protection_reason(pid, creation_ticks.as_deref())
                }
                #[cfg(not(any(target_os = "windows", target_os = "linux")))]
                {
                    Some("Local process control is unavailable on this platform")
                }
            });
            ProcessItem {
                pid,
                name,
                cpu_percent: process.cpu_usage().clamp(0.0, 100.0),
                memory_bytes: process.memory(),
                started_at_unix: process.start_time(),
                creation_ticks,
                runtime_seconds: process.run_time(),
                action_available: reason.is_none(),
                action_reason: reason
                    .unwrap_or("OS permission and critical-state check required")
                    .to_owned(),
            }
        })
        .collect();
    items.sort_by_key(|item| item.pid);
    items
}

pub fn inventory() -> HostInventory {
    #[cfg(target_os = "windows")]
    {
        match windows::services() {
            Ok(services) => HostInventory {
                available: true,
                processes: process_items(),
                services,
                detail: "Local native Windows process and Service Control Manager inventory."
                    .to_owned(),
            },
            Err(message) => HostInventory {
                available: true,
                processes: process_items(),
                services: vec![],
                detail: message,
            },
        }
    }
    #[cfg(target_os = "linux")]
    {
        match linux::services() {
            Ok(services) => HostInventory {
                available: true,
                processes: process_items(),
                services,
                detail: "Local Linux process and systemd D-Bus service inventory.".to_owned(),
            },
            Err(_) => HostInventory {
                available: true,
                processes: process_items(),
                services: vec![],
                detail: "Local processes are available; systemd D-Bus inventory is unavailable."
                    .to_owned(),
            },
        }
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux")))]
    {
        HostInventory {
            available: false,
            processes: vec![],
            services: vec![],
            detail: "Local inventory is unavailable on this platform.".to_owned(),
        }
    }
}

pub fn terminate(pid: u32, name: &str, creation_ticks: &str) -> Result<ActionResult, String> {
    if let Some(reason) = process_protection_reason(name, pid) {
        return Err(reason.to_owned());
    }
    let found = process_items()
        .into_iter()
        .find(|item| item.pid == pid)
        .ok_or("Process has already exited")?;
    validate_process_identity(&found, name, creation_ticks)?;
    #[cfg(target_os = "windows")]
    {
        windows::terminate(
            pid,
            creation_ticks
                .parse::<u64>()
                .map_err(|_| "Invalid process identity".to_owned())?,
        )
    }
    #[cfg(target_os = "linux")]
    {
        linux::terminate(pid, creation_ticks)
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux")))]
    {
        Err("Local process termination is unavailable on this platform".to_owned())
    }
}

fn validate_process_identity(
    found: &ProcessItem,
    name: &str,
    creation_ticks: &str,
) -> Result<(), String> {
    if !found.action_available {
        return Err(found.action_reason.clone());
    }
    if found.name != name || found.creation_ticks.as_deref() != Some(creation_ticks) {
        Err("Process identity changed; refresh before retrying".to_owned())
    } else {
        Ok(())
    }
}

pub fn service_action(name: &str, action: &str) -> Result<ActionResult, String> {
    if !matches!(action, "start" | "stop" | "restart") {
        return Err("Unsupported service action".to_owned());
    }
    if let Some(reason) = service_protection_reason(name) {
        return Err(reason.to_owned());
    }
    #[cfg(target_os = "windows")]
    {
        windows::service_action(name, action)
    }
    #[cfg(target_os = "linux")]
    {
        linux::service_action(name, action)
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux")))]
    {
        let _ = name;
        Err("Local service control is unavailable here".to_owned())
    }
}

#[cfg(target_os = "linux")]
mod linux {
    use super::{ActionResult, ServiceItem};
    use std::fs;
    use zbus::blocking::{Connection, Proxy};
    use zbus::zvariant::OwnedObjectPath;

    type Unit = (
        String,
        String,
        String,
        String,
        String,
        String,
        OwnedObjectPath,
        u32,
        String,
        OwnedObjectPath,
    );

    fn manager<'a>(connection: &'a Connection) -> Result<Proxy<'a>, String> {
        Proxy::new(
            connection,
            "org.freedesktop.systemd1",
            "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager",
        )
        .map_err(|_| "systemd D-Bus is unavailable".to_owned())
    }

    pub fn process_creation_ticks(pid: u32) -> Option<String> {
        let stat = fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
        let after_name = stat.rsplit_once(')')?.1;
        after_name.split_whitespace().nth(19).map(str::to_owned)
    }

    pub fn process_protection_reason(pid: u32, identity: Option<&str>) -> Option<&'static str> {
        if identity.is_none() {
            return Some("Process identity is unavailable");
        }
        let status = match fs::read_to_string(format!("/proc/{pid}/status")) {
            Ok(value) => value,
            Err(_) => return Some("Process owner is unavailable"),
        };
        let uid = status
            .lines()
            .find_map(|line| line.strip_prefix("Uid:"))
            .and_then(|value| value.split_whitespace().next())
            .and_then(|value| value.parse::<u32>().ok());
        let Some(uid) = uid else {
            return Some("Process owner is unavailable");
        };
        if uid == 0 {
            Some("Root-owned process is protected")
        } else {
            None
        }
    }

    pub fn services() -> Result<Vec<ServiceItem>, String> {
        let connection =
            Connection::system().map_err(|_| "systemd D-Bus is unavailable".to_owned())?;
        let proxy = manager(&connection)?;
        let units: Vec<Unit> = proxy
            .call("ListUnits", &())
            .map_err(|_| "systemd service inventory is unavailable".to_owned())?;
        let unit_files: Vec<(String, String)> =
            proxy.call("ListUnitFiles", &()).unwrap_or_default();
        let enabled: std::collections::HashMap<String, String> = unit_files
            .into_iter()
            .filter_map(|(path, state)| {
                std::path::Path::new(&path)
                    .file_name()
                    .map(|name| (name.to_string_lossy().into_owned(), state))
            })
            .collect();
        Ok(units
            .into_iter()
            .filter(|unit| unit.0.ends_with(".service"))
            .take(2048)
            .map(|unit| {
                let protected = ["systemd-", "dbus", "polkit", "network", "NetworkManager"]
                    .iter()
                    .any(|prefix| unit.0.starts_with(prefix))
                    || matches!(
                        unit.0.as_str(),
                        "ssh.service"
                            | "sshd.service"
                            | "systemd-resolved.service"
                            | "getty@tty1.service"
                    );
                let main_pid = Proxy::new(
                    &connection,
                    "org.freedesktop.systemd1",
                    unit.6.clone(),
                    "org.freedesktop.systemd1.Service",
                )
                .ok()
                .and_then(|service| service.get_property::<u32>("MainPID").ok());
                let started_at_unix = Proxy::new(
                    &connection,
                    "org.freedesktop.systemd1",
                    unit.6.clone(),
                    "org.freedesktop.systemd1.Unit",
                )
                .ok()
                .and_then(|service| service.get_property::<u64>("ActiveEnterTimestamp").ok())
                .filter(|value| *value > 0)
                .map(|value| value / 1_000_000);
                let unit_state = enabled.get(&unit.0).cloned();
                ServiceItem {
                    name: unit.0,
                    display_name: unit.1,
                    state: match unit.3.as_str() {
                        "active" => "running",
                        "inactive" => "stopped",
                        "activating" => "starting",
                        "deactivating" => "stopping",
                        "failed" => "stopped",
                        _ => "unknown",
                    }
                    .to_owned(),
                    start_type: unit_state.clone(),
                    pid: main_pid.filter(|pid| *pid > 0),
                    description: Some(format!("systemd sub-state: {}", unit.4)),
                    sub_state: Some(unit.4),
                    enabled: unit_state.as_deref().map(|state| state == "enabled"),
                    started_at_unix,
                    action_available: !protected,
                    action_reason: if protected {
                        "Protected systemd service"
                    } else {
                        "OS permission required"
                    }
                    .to_owned(),
                }
            })
            .collect())
    }

    pub fn terminate(pid: u32, creation_ticks: &str) -> Result<ActionResult, String> {
        if process_creation_ticks(pid).as_deref() != Some(creation_ticks) {
            return Err("Process identity changed; refresh before retrying".to_owned());
        }
        if process_protection_reason(pid, Some(creation_ticks)).is_some() {
            return Err("Protected or unverifiable process".to_owned());
        }
        unsafe extern "C" {
            fn kill(pid: i32, signal: i32) -> i32;
        }
        let pid = i32::try_from(pid).map_err(|_| "Invalid process ID".to_owned())?;
        if unsafe { kill(pid, 15) } != 0 {
            return Err("OS denied local process termination".to_owned());
        }
        Ok(ActionResult {
            success: true,
            previous_state: "running".to_owned(),
            resulting_state: "stopping".to_owned(),
            message: "Local SIGTERM requested".to_owned(),
        })
    }

    pub fn service_action(name: &str, action: &str) -> Result<ActionResult, String> {
        let previous = services()?
            .into_iter()
            .find(|item| item.name == name)
            .ok_or("Service is not in the local inventory")?;
        if !previous.action_available {
            return Err(previous.action_reason);
        }
        let connection =
            Connection::system().map_err(|_| "systemd D-Bus is unavailable".to_owned())?;
        let proxy = manager(&connection)?;
        let method = match action {
            "start" => "StartUnit",
            "stop" => "StopUnit",
            "restart" => "RestartUnit",
            _ => return Err("Unsupported service action".to_owned()),
        };
        let _: OwnedObjectPath = proxy
            .call(method, &(name, "replace"))
            .map_err(|_| "OS denied local systemd action".to_owned())?;
        let resulting = services()?
            .into_iter()
            .find(|item| item.name == name)
            .map(|item| item.state)
            .unwrap_or_else(|| "unknown".to_owned());
        Ok(ActionResult {
            success: true,
            previous_state: previous.state,
            resulting_state: resulting,
            message: "Local systemd action requested".to_owned(),
        })
    }
}

#[cfg(target_os = "windows")]
mod windows {
    use super::{service_protection_reason, ActionResult, ServiceItem};
    use std::{
        ffi::c_void,
        ptr::{null, null_mut},
        thread,
        time::{Duration, Instant},
    };
    type Handle = *mut c_void;
    #[repr(C)]
    struct ServiceStatusProcess {
        service_type: u32,
        state: u32,
        controls_accepted: u32,
        win32_exit_code: u32,
        service_specific_exit_code: u32,
        check_point: u32,
        wait_hint: u32,
        process_id: u32,
        service_flags: u32,
    }
    #[repr(C)]
    struct EnumServiceStatusProcess {
        name: *const u16,
        display_name: *const u16,
        status: ServiceStatusProcess,
    }
    #[repr(C)]
    struct QueryServiceConfig {
        service_type: u32,
        start_type: u32,
        error_control: u32,
        binary_path: *const u16,
        load_group: *const u16,
        tag_id: u32,
        dependencies: *const u16,
        service_account: *const u16,
        display_name: *const u16,
    }
    #[repr(C)]
    struct ServiceDescription {
        description: *const u16,
    }
    #[repr(C)]
    struct ServiceStatus {
        service_type: u32,
        state: u32,
        controls_accepted: u32,
        win32_exit_code: u32,
        service_specific_exit_code: u32,
        check_point: u32,
        wait_hint: u32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct FileTime {
        low: u32,
        high: u32,
    }
    #[link(name = "advapi32")]
    extern "system" {
        fn OpenSCManagerW(machine: *const u16, database: *const u16, access: u32) -> Handle;
        fn CloseServiceHandle(handle: Handle) -> i32;
        fn EnumServicesStatusExW(
            manager: Handle,
            level: u32,
            service_type: u32,
            state: u32,
            buffer: *mut u8,
            size: u32,
            needed: *mut u32,
            returned: *mut u32,
            resume: *mut u32,
            group: *const u16,
        ) -> i32;
        fn OpenServiceW(manager: Handle, name: *const u16, access: u32) -> Handle;
        fn QueryServiceConfigW(
            service: Handle,
            config: *mut QueryServiceConfig,
            size: u32,
            needed: *mut u32,
        ) -> i32;
        fn QueryServiceConfig2W(
            service: Handle,
            level: u32,
            config: *mut u8,
            size: u32,
            needed: *mut u32,
        ) -> i32;
        fn QueryServiceStatusEx(
            service: Handle,
            level: u32,
            status: *mut u8,
            size: u32,
            needed: *mut u32,
        ) -> i32;
        fn StartServiceW(service: Handle, args: u32, arguments: *const *const u16) -> i32;
        fn ControlService(service: Handle, control: u32, status: *mut ServiceStatus) -> i32;
    }
    #[link(name = "kernel32")]
    extern "system" {
        fn OpenProcess(access: u32, inherit: i32, pid: u32) -> Handle;
        fn CloseHandle(handle: Handle) -> i32;
        fn IsProcessCritical(handle: Handle, critical: *mut i32) -> i32;
        fn GetProcessTimes(
            handle: Handle,
            created: *mut FileTime,
            exited: *mut FileTime,
            kernel: *mut FileTime,
            user: *mut FileTime,
        ) -> i32;
        fn TerminateProcess(handle: Handle, code: u32) -> i32;
    }
    struct ScopedHandle(Handle, bool);
    impl Drop for ScopedHandle {
        fn drop(&mut self) {
            unsafe {
                if self.1 {
                    CloseServiceHandle(self.0);
                } else {
                    CloseHandle(self.0);
                }
            }
        }
    }
    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(Some(0)).collect()
    }
    unsafe fn string(ptr: *const u16) -> String {
        if ptr.is_null() {
            return String::new();
        }
        let mut len = 0;
        while len < 512 && *ptr.add(len) != 0 {
            len += 1;
        }
        String::from_utf16_lossy(std::slice::from_raw_parts(ptr, len))
    }
    pub(super) fn state(value: u32) -> String {
        match value {
            1 => "stopped",
            2 | 5 => "starting",
            3 | 6 => "stopping",
            4 => "running",
            7 => "paused",
            _ => "unknown",
        }
        .to_owned()
    }
    fn manager() -> Result<ScopedHandle, String> {
        let handle = unsafe { OpenSCManagerW(null(), null(), 0x0001 | 0x0004) };
        if handle.is_null() {
            Err(
                "Windows Service Control Manager is unavailable or permission was denied"
                    .to_owned(),
            )
        } else {
            Ok(ScopedHandle(handle, true))
        }
    }
    pub fn critical_process_reason(pid: u32) -> Option<&'static str> {
        let handle = unsafe { OpenProcess(0x1000, 0, pid) };
        if handle.is_null() {
            return Some("Windows did not permit critical-state verification");
        }
        let handle = ScopedHandle(handle, false);
        let mut critical = 0;
        if unsafe { IsProcessCritical(handle.0, &mut critical) } == 0 {
            Some("Windows did not permit critical-state verification")
        } else if critical != 0 {
            Some("Windows marks this process as system-critical")
        } else {
            None
        }
    }
    pub fn process_creation_ticks(pid: u32) -> Option<u64> {
        let handle = unsafe { OpenProcess(0x1000, 0, pid) };
        if handle.is_null() {
            return None;
        }
        let handle = ScopedHandle(handle, false);
        let (mut created, mut exited, mut kernel, mut user) = (
            FileTime::default(),
            FileTime::default(),
            FileTime::default(),
            FileTime::default(),
        );
        if unsafe { GetProcessTimes(handle.0, &mut created, &mut exited, &mut kernel, &mut user) }
            == 0
        {
            return None;
        }
        Some((u64::from(created.high) << 32) | u64::from(created.low))
    }
    fn open_service(
        manager: &ScopedHandle,
        name: &str,
        access: u32,
    ) -> Result<ScopedHandle, String> {
        let handle = unsafe { OpenServiceW(manager.0, wide(name).as_ptr(), access) };
        if handle.is_null() {
            Err("Windows denied access to this service".to_owned())
        } else {
            Ok(ScopedHandle(handle, true))
        }
    }
    fn status(handle: &ScopedHandle) -> Result<ServiceStatusProcess, String> {
        let mut value = ServiceStatusProcess {
            service_type: 0,
            state: 0,
            controls_accepted: 0,
            win32_exit_code: 0,
            service_specific_exit_code: 0,
            check_point: 0,
            wait_hint: 0,
            process_id: 0,
            service_flags: 0,
        };
        let mut needed = 0;
        let ok = unsafe {
            QueryServiceStatusEx(
                handle.0,
                0,
                (&mut value as *mut ServiceStatusProcess).cast(),
                std::mem::size_of::<ServiceStatusProcess>() as u32,
                &mut needed,
            )
        };
        if ok == 0 {
            Err("Service status is unavailable".to_owned())
        } else {
            Ok(value)
        }
    }
    pub fn services() -> Result<Vec<ServiceItem>, String> {
        let manager = manager()?;
        let mut needed = 0;
        let mut returned = 0;
        let mut resume = 0;
        unsafe {
            EnumServicesStatusExW(
                manager.0,
                0,
                0x30,
                3,
                null_mut(),
                0,
                &mut needed,
                &mut returned,
                &mut resume,
                null(),
            );
        }
        if needed == 0 || needed > 2_000_000 {
            return Err("Service inventory exceeded the safe size limit".to_owned());
        }
        let buffer_size = needed as usize + 4096;
        let mut buffer = vec![0_u64; buffer_size.div_ceil(8)];
        resume = 0;
        let ok = unsafe {
            EnumServicesStatusExW(
                manager.0,
                0,
                0x30,
                3,
                buffer.as_mut_ptr().cast(),
                buffer_size as u32,
                &mut needed,
                &mut returned,
                &mut resume,
                null(),
            )
        };
        if ok == 0 {
            return Err("Service inventory is unavailable or permission was denied".to_owned());
        }
        if returned as usize * std::mem::size_of::<EnumServiceStatusProcess>() > buffer_size {
            return Err("Service inventory returned an invalid size".to_owned());
        }
        let mut items = Vec::with_capacity(returned as usize);
        for index in 0..returned as usize {
            let entry = unsafe {
                std::ptr::read_unaligned(
                    buffer
                        .as_ptr()
                        .cast::<u8>()
                        .add(index * std::mem::size_of::<EnumServiceStatusProcess>())
                        .cast::<EnumServiceStatusProcess>(),
                )
            };
            let name = unsafe { string(entry.name) };
            let display_name = unsafe { string(entry.display_name) };
            let mut start_type = None;
            let mut description = None;
            if let Ok(service) = open_service(&manager, &name, 0x0001) {
                let mut size = 0;
                unsafe {
                    QueryServiceConfigW(service.0, null_mut(), 0, &mut size);
                }
                if size > 0 && size < 65_536 {
                    let mut config = vec![0_u64; (size as usize).div_ceil(8)];
                    if unsafe {
                        QueryServiceConfigW(service.0, config.as_mut_ptr().cast(), size, &mut size)
                    } != 0
                    {
                        let raw = unsafe {
                            std::ptr::read_unaligned(config.as_ptr().cast::<QueryServiceConfig>())
                        };
                        start_type = Some(
                            match raw.start_type {
                                0 => "boot",
                                1 => "system",
                                2 => "automatic",
                                3 => "manual",
                                4 => "disabled",
                                _ => "unknown",
                            }
                            .to_owned(),
                        );
                    }
                }
                let mut size = 0;
                unsafe {
                    QueryServiceConfig2W(service.0, 1, null_mut(), 0, &mut size);
                }
                if size > 0 && size < 65_536 {
                    let mut config = vec![0_u64; (size as usize).div_ceil(8)];
                    if unsafe {
                        QueryServiceConfig2W(
                            service.0,
                            1,
                            config.as_mut_ptr().cast(),
                            size,
                            &mut size,
                        )
                    } != 0
                    {
                        let raw = unsafe {
                            std::ptr::read_unaligned(config.as_ptr().cast::<ServiceDescription>())
                        };
                        let value = unsafe { string(raw.description) };
                        let lower = value.to_ascii_lowercase();
                        if !value.is_empty()
                            && !["password", "secret", "token", "credential", "api_key"]
                                .iter()
                                .any(|marker| lower.contains(marker))
                        {
                            description = Some(
                                value
                                    .chars()
                                    .filter(|character| !character.is_control())
                                    .take(300)
                                    .collect(),
                            );
                        }
                    }
                }
            }
            let reason = service_protection_reason(&name).or_else(|| {
                if entry.status.service_flags & 1 != 0 {
                    Some("Service runs in a Windows system process")
                } else if start_type.as_deref() == Some("disabled") {
                    Some("Service start type is disabled")
                } else {
                    None
                }
            });
            items.push(ServiceItem {
                name,
                display_name,
                state: state(entry.status.state),
                start_type,
                pid: (entry.status.process_id > 0).then_some(entry.status.process_id),
                description,
                sub_state: None,
                enabled: None,
                started_at_unix: None,
                action_available: reason.is_none(),
                action_reason: reason
                    .unwrap_or("OS permissions and dependencies apply")
                    .to_owned(),
            });
        }
        items.sort_by(|a, b| {
            a.display_name
                .to_lowercase()
                .cmp(&b.display_name.to_lowercase())
        });
        Ok(items)
    }
    pub fn terminate(pid: u32, creation_ticks: u64) -> Result<ActionResult, String> {
        let handle = unsafe { OpenProcess(0x1000 | 0x0001, 0, pid) };
        if handle.is_null() {
            return Err("Process exited or Windows denied access".to_owned());
        }
        let handle = ScopedHandle(handle, false);
        let mut critical = 0;
        if unsafe { IsProcessCritical(handle.0, &mut critical) } == 0 {
            return Err("Windows could not verify whether this process is protected".to_owned());
        }
        if critical != 0 {
            return Err("Windows marks this process as system-critical".to_owned());
        }
        let (mut created, mut exited, mut kernel, mut user) = (
            FileTime::default(),
            FileTime::default(),
            FileTime::default(),
            FileTime::default(),
        );
        if unsafe { GetProcessTimes(handle.0, &mut created, &mut exited, &mut kernel, &mut user) }
            == 0
        {
            return Err("Process identity could not be verified".to_owned());
        }
        let actual = (u64::from(created.high) << 32) | u64::from(created.low);
        if actual != creation_ticks {
            return Err("PID was reused; refresh before retrying".to_owned());
        }
        if unsafe { TerminateProcess(handle.0, 1) } == 0 {
            return Err("Windows denied process termination".to_owned());
        }
        Ok(ActionResult {
            success: true,
            previous_state: "running".to_owned(),
            resulting_state: "terminated".to_owned(),
            message: "Local process terminated".to_owned(),
        })
    }
    pub fn service_action(name: &str, action: &str) -> Result<ActionResult, String> {
        if !services()?
            .iter()
            .any(|item| item.name == name && item.action_available)
        {
            return Err("Service is not in the actionable local inventory".to_owned());
        }
        let manager = manager()?;
        let service = open_service(&manager, name, 0x0004 | 0x0010 | 0x0020)?;
        let previous = state(status(&service)?.state);
        if action == "stop" || action == "restart" {
            if previous == "running" {
                let mut result = ServiceStatus {
                    service_type: 0,
                    state: 0,
                    controls_accepted: 0,
                    win32_exit_code: 0,
                    service_specific_exit_code: 0,
                    check_point: 0,
                    wait_hint: 0,
                };
                if unsafe { ControlService(service.0, 1, &mut result) } == 0 {
                    return Err(
                        "Windows refused service stop; check dependencies and privileges"
                            .to_owned(),
                    );
                }
                wait_state(&service, "stopped")?;
            } else if action == "stop" {
                return Err("Service is not running".to_owned());
            }
        }
        if action == "start" || action == "restart" {
            if action == "start" && previous != "stopped" {
                return Err("Service is not stopped".to_owned());
            }
            if unsafe { StartServiceW(service.0, 0, null()) } == 0 {
                return Err(
                    "Windows refused service start; check dependencies and privileges".to_owned(),
                );
            }
            wait_state(&service, "running")?;
        }
        Ok(ActionResult {
            success: true,
            previous_state: previous,
            resulting_state: state(status(&service)?.state),
            message: format!("Local service {action} completed"),
        })
    }
    fn wait_state(service: &ScopedHandle, target: &str) -> Result<(), String> {
        let started = Instant::now();
        while started.elapsed() < Duration::from_secs(20) {
            if state(status(service)?.state) == target {
                return Ok(());
            }
            thread::sleep(Duration::from_millis(300));
        }
        Err("Service did not reach the requested state within 20 seconds".to_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn protected_processes_rejected() {
        for name in [
            "System",
            "Registry",
            "smss.exe",
            "csrss.exe",
            "lsass.exe",
            "svchost.exe",
            "RavenTech-OSINT-Desktop.exe",
        ] {
            assert!(process_protection_reason(name, 500).is_some());
        }
        assert!(process_protection_reason("notepad.exe", 500).is_none());
    }
    #[test]
    fn core_services_rejected() {
        assert!(service_protection_reason("RpcSs").is_some());
        assert!(service_protection_reason("example-service").is_none());
    }
    #[test]
    fn invalid_actions_rejected() {
        assert!(service_action("anything", "delete").is_err());
    }
    #[test]
    fn process_identity_and_pid_reuse_are_deterministic() {
        let item = ProcessItem {
            pid: 555,
            name: "example.exe".to_owned(),
            cpu_percent: 2.0,
            memory_bytes: 1024,
            started_at_unix: 100,
            creation_ticks: Some("123456789012345678".to_owned()),
            runtime_seconds: 20,
            action_available: true,
            action_reason: "".to_owned(),
        };
        assert!(validate_process_identity(&item, "example.exe", "123456789012345678").is_ok());
        assert!(validate_process_identity(&item, "example.exe", "123456789012345679").is_err());
        assert!(validate_process_identity(&item, "other.exe", "123456789012345678").is_err());
        assert!(!serde_json::to_string(&item)
            .unwrap()
            .contains("command_line"));
    }
    #[cfg(target_os = "windows")]
    #[test]
    fn service_states_are_normalized() {
        assert_eq!(windows::state(4), "running");
        assert_eq!(windows::state(7), "paused");
        assert_eq!(windows::state(99), "unknown");
    }
    #[cfg(target_os = "windows")]
    #[test]
    fn native_inventory_is_local_and_secret_free() {
        let sample = inventory();
        assert!(sample.available);
        assert!(!sample.processes.is_empty());
        assert!(sample
            .processes
            .iter()
            .any(|item| item.pid == std::process::id()));
        assert!(
            !sample.services.is_empty(),
            "SCM service enumeration must succeed"
        );
        let value = serde_json::to_value(&sample.processes[0]).unwrap();
        let keys = value.as_object().unwrap();
        for forbidden in ["commandLine", "environment", "openedFiles", "credential"] {
            assert!(!keys.contains_key(forbidden));
        }
    }
    #[cfg(target_os = "linux")]
    #[test]
    fn linux_process_identity_and_local_inventory() {
        let pid = std::process::id();
        assert!(linux::process_creation_ticks(pid).is_some());
        let sample = inventory();
        assert!(sample.available);
        assert!(sample.processes.iter().any(|item| item.pid == pid));
        let json = serde_json::to_string(&sample).unwrap();
        assert!(!json.contains("commandLine"));
        assert!(!json.contains("environment"));
        if std::env::var_os("RAVENTECH_EXPECT_SYSTEMD_TEST").is_some() {
            let services = linux::services().expect("systemd D-Bus inventory must be available");
            assert!(!services.is_empty());
            assert!(services.iter().all(|item| item.name.ends_with(".service")));
            assert!(services.iter().any(|item| item.sub_state.is_some()));
        }
    }
}
