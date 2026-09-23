//! Tauri-owned lifecycle for the fixed native RavenTech backend and worker.
//!
//! Only child handles created by this module can be stopped. An already-running
//! compatible server is observed as external and is never terminated here.

use super::managed_postgres::{self, ManagedProcess};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Manager, State};

const EXPECTED_VERSION: &str = "5.0.0-rc6";
const BACKEND_URL: &str = "127.0.0.1:8000";
const HEALTH_INTERVAL: Duration = Duration::from_secs(2);
const STARTUP_LIMIT: Duration = Duration::from_secs(45);
const BACKEND_STOP_LIMIT: Duration = Duration::from_secs(8);
const WORKER_STOP_LIMIT: Duration = Duration::from_secs(100);
const RESTART_DELAYS: [Duration; 3] = [
    Duration::from_secs(2),
    Duration::from_secs(5),
    Duration::from_secs(10),
];

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ComponentStatus {
    pub state: String,
    pub ownership: String,
    pub pid: Option<u32>,
    pub version: Option<String>,
    pub health: String,
    pub readiness: String,
    pub started_at_unix_ms: Option<u128>,
    pub restart_count: u8,
    pub last_exit_code: Option<i32>,
    pub last_error_code: Option<String>,
    pub last_error: Option<String>,
    pub heartbeat_at_unix_ms: Option<u128>,
    pub actions_available: bool,
}

impl Default for ComponentStatus {
    fn default() -> Self {
        Self {
            state: "waiting".to_owned(),
            ownership: "unknown".to_owned(),
            pid: None,
            version: None,
            health: "unknown".to_owned(),
            readiness: "unknown".to_owned(),
            started_at_unix_ms: None,
            restart_count: 0,
            last_exit_code: None,
            last_error_code: None,
            last_error: None,
            heartbeat_at_unix_ms: None,
            actions_available: false,
        }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeStatus {
    pub runtime_mode: String,
    pub platform: String,
    pub architecture: String,
    pub backend: ComponentStatus,
    pub worker: ComponentStatus,
    pub postgresql: DatabaseStatus,
    pub redis: DependencyStatus,
    pub celery: DependencyStatus,
    pub embedded_frontend: String,
    pub last_messages: Vec<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DatabaseStatus {
    pub required: bool,
    pub state: String,
    pub pid: Option<u32>,
    pub mode: String,
    pub ownership: String,
    pub version: Option<String>,
    pub port: Option<u16>,
    pub local_only: bool,
    pub initialized: bool,
    pub migration_state: String,
    pub started_at_unix_ms: Option<u128>,
    pub restart_count: u8,
    pub last_exit_code: Option<i32>,
    pub last_error_code: Option<String>,
    pub last_error: Option<String>,
    pub actions_available: bool,
}

impl Default for DatabaseStatus {
    fn default() -> Self {
        Self {
            required: true,
            state: "waiting".to_owned(),
            pid: None,
            mode: "external".to_owned(),
            ownership: "unknown".to_owned(),
            version: None,
            port: None,
            local_only: true,
            initialized: false,
            migration_state: "unknown".to_owned(),
            started_at_unix_ms: None,
            restart_count: 0,
            last_exit_code: None,
            last_error_code: None,
            last_error: None,
            actions_available: false,
        }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DependencyStatus {
    pub required: bool,
    pub state: String,
}

impl Default for RuntimeStatus {
    fn default() -> Self {
        Self {
            runtime_mode: if cfg!(debug_assertions) {
                "development"
            } else {
                "desktop"
            }
            .to_owned(),
            platform: if cfg!(target_os = "windows") {
                "windows".to_owned()
            } else if cfg!(target_os = "linux") {
                "linux".to_owned()
            } else {
                "unsupported".to_owned()
            },
            architecture: std::env::consts::ARCH.to_owned(),
            backend: ComponentStatus::default(),
            worker: ComponentStatus::default(),
            postgresql: DatabaseStatus::default(),
            redis: DependencyStatus {
                required: false,
                state: "not_required".to_owned(),
            },
            celery: DependencyStatus {
                required: false,
                state: "not_required".to_owned(),
            },
            embedded_frontend: "ready".to_owned(),
            last_messages: Vec::new(),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Component {
    Backend,
    Worker,
}

#[derive(Default)]
struct Children {
    backend: Option<Child>,
    worker: Option<Child>,
    postgresql: Option<OwnedPostgres>,
}

struct OwnedPostgres {
    child: Child,
    pg_ctl: PathBuf,
    data_directory: PathBuf,
}

#[derive(Default)]
struct Control {
    stop_backend: bool,
    stop_worker: bool,
    retry_backend: bool,
    retry_worker: bool,
    stop_database: bool,
    retry_database: bool,
    shutdown: bool,
}

struct Shared {
    status: Mutex<RuntimeStatus>,
    children: Mutex<Children>,
    control: Mutex<Control>,
    desired: Mutex<Desired>,
    lease: Mutex<Option<SupervisorLease>>,
    owns_lease: AtomicBool,
    database_url: Mutex<Option<String>>,
}

struct SupervisorLease {
    _file: Option<std::fs::File>,
    #[cfg(target_os = "windows")]
    handle: usize,
}

impl Drop for SupervisorLease {
    fn drop(&mut self) {
        #[cfg(target_os = "windows")]
        unsafe {
            let _ = CloseHandle(self.handle as *mut std::ffi::c_void);
        }
    }
}

#[derive(Default)]
struct Desired {
    backend: bool,
    worker: bool,
    database: bool,
}

#[derive(Clone)]
pub struct NativeRuntimeSupervisor(Arc<Shared>);

impl Default for NativeRuntimeSupervisor {
    fn default() -> Self {
        Self(Arc::new(Shared {
            status: Mutex::new(RuntimeStatus::default()),
            children: Mutex::new(Children::default()),
            control: Mutex::new(Control::default()),
            desired: Mutex::new(Desired {
                backend: true,
                worker: true,
                database: true,
            }),
            lease: Mutex::new(None),
            owns_lease: AtomicBool::new(false),
            database_url: Mutex::new(None),
        }))
    }
}

impl NativeRuntimeSupervisor {
    pub fn start(app: AppHandle) -> Self {
        let supervisor = Self::default();
        if let Some(lease) = acquire_lease() {
            if let Ok(mut value) = supervisor.0.lease.lock() {
                *value = Some(lease);
            }
            supervisor.0.owns_lease.store(true, Ordering::Release);
        } else {
            supervisor.message("Another RavenTech Desktop session owns runtime startup. This session will only observe compatible services.");
        }
        let loop_supervisor = supervisor.clone();
        thread::Builder::new()
            .name("raventech-native-runtime".to_owned())
            .spawn(move || loop_supervisor.run(app))
            .ok();
        supervisor
    }

    pub fn status(&self) -> RuntimeStatus {
        self.0
            .status
            .lock()
            .map(|value| value.clone())
            .unwrap_or_default()
    }

    pub fn request(
        &self,
        component: Component,
        action: &str,
        confirmed: bool,
    ) -> Result<(), String> {
        if !matches!(action, "start" | "stop" | "restart") {
            return Err("Unsupported local runtime action".to_owned());
        }
        if action != "start" && !confirmed {
            return Err("Explicit confirmation is required".to_owned());
        }
        let status = self.status();
        if status.runtime_mode != "desktop" {
            return Err("Native runtime controls are disabled for this runtime profile".to_owned());
        }
        if action == "start" && !self.can_spawn() {
            return Err("Another desktop session owns native runtime startup".to_owned());
        }
        let component_status = match component {
            Component::Backend => status.backend,
            Component::Worker => status.worker,
        };
        if action != "start"
            && (component_status.ownership != "owned" || !component_status.actions_available)
        {
            return Err("Only an active component owned by this desktop session can be stopped or restarted".to_owned());
        }
        let mut control = self
            .0
            .control
            .lock()
            .map_err(|_| "Runtime control is unavailable")?;
        if let Ok(mut desired) = self.0.desired.lock() {
            match component {
                Component::Backend => desired.backend = action != "stop",
                Component::Worker => desired.worker = action != "stop",
            }
        }
        match component {
            Component::Backend => {
                control.stop_backend = action != "start";
                control.retry_backend = action != "stop";
            }
            Component::Worker => {
                control.stop_worker = action != "start";
                control.retry_worker = action != "stop";
            }
        }
        Ok(())
    }

    pub fn request_database(&self, action: &str, confirmed: bool) -> Result<(), String> {
        if !matches!(action, "start" | "stop" | "restart") {
            return Err("Unsupported database action".to_owned());
        }
        if action != "start" && !confirmed {
            return Err("Explicit confirmation is required".to_owned());
        }
        let status = self.status();
        if status.runtime_mode != "desktop" || status.postgresql.mode != "managed" {
            return Err(
                "Database lifecycle actions are available only for the local managed database"
                    .to_owned(),
            );
        }
        if action != "start"
            && (status.postgresql.ownership != "owned" || !status.postgresql.actions_available)
        {
            return Err(
                "Only PostgreSQL owned by this desktop session can be stopped or restarted"
                    .to_owned(),
            );
        }
        if action == "start" && !self.can_spawn() {
            return Err("Another desktop session owns native runtime startup".to_owned());
        }
        let mut control = self
            .0
            .control
            .lock()
            .map_err(|_| "Runtime control is unavailable")?;
        if let Ok(mut desired) = self.0.desired.lock() {
            desired.database = action != "stop";
            if action == "stop" {
                desired.backend = false;
                desired.worker = false;
            } else {
                desired.backend = true;
                desired.worker = true;
            }
        }
        control.stop_database = action != "start";
        control.retry_database = action != "stop";
        Ok(())
    }

    pub fn shutdown(&self) {
        if let Ok(mut control) = self.0.control.lock() {
            control.shutdown = true;
        }
        self.stop_owned(Component::Worker);
        self.stop_owned(Component::Backend);
        self.stop_managed_postgres();
    }

    fn run(&self, app: AppHandle) {
        let mut backend_attempts = 0_u8;
        let mut worker_attempts = 0_u8;
        let mut backend_restart_after = Instant::now();
        let mut worker_restart_after = Instant::now();
        let mut postgres_attempts = 0_u8;
        let mut postgres_restart_after = Instant::now();
        loop {
            if self.control().shutdown {
                self.stop_owned(Component::Worker);
                self.stop_owned(Component::Backend);
                self.stop_managed_postgres();
                break;
            }
            let control = self.take_control();
            if control.stop_worker || control.retry_worker {
                self.stop_owned(Component::Worker);
                worker_attempts = 0;
                if control.retry_worker {
                    self.set_restart_count(Component::Worker, 0);
                }
            }
            if control.stop_backend || control.retry_backend {
                self.stop_owned(Component::Worker);
                self.stop_owned(Component::Backend);
                backend_attempts = 0;
                worker_attempts = 0;
                self.set_restart_count(Component::Backend, 0);
                self.set_restart_count(Component::Worker, 0);
            }
            if control.stop_database || control.retry_database {
                self.stop_owned(Component::Worker);
                self.stop_owned(Component::Backend);
                self.stop_managed_postgres();
                postgres_attempts = 0;
                self.set_database_restart_count(0);
            }

            self.reap_exited(
                Component::Backend,
                &mut backend_attempts,
                &mut backend_restart_after,
            );
            self.reap_exited(
                Component::Worker,
                &mut worker_attempts,
                &mut worker_restart_after,
            );

            let profile = std::env::var("RUNTIME_PROFILE").unwrap_or_else(|_| {
                if cfg!(debug_assertions) {
                    "development".to_owned()
                } else {
                    "desktop".to_owned()
                }
            });
            if let Ok(mut status) = self.0.status.lock() {
                status.runtime_mode = profile.clone();
            }
            if profile == "docker" {
                self.message("Native supervisor inactive for the selected runtime profile.");
                thread::sleep(HEALTH_INTERVAL);
                continue;
            }
            if profile == "development" {
                if let BackendProbe::Compatible {
                    ready,
                    version,
                    database,
                    ..
                } = probe_backend()
                {
                    self.update_backend_external_or_owned(ready, version);
                    self.update_postgresql(database);
                    if self.external_worker_ready() {
                        self.update_worker_external();
                    }
                }
                thread::sleep(HEALTH_INTERVAL);
                continue;
            }

            let app_paths = artifact_paths(&app);
            if database_mode(&profile) == "managed" && self.is_database_enabled() {
                if self.child_postgres_exited() {
                    self.reap_postgres();
                    if let Some(delay) = RESTART_DELAYS
                        .get(postgres_attempts.min(2) as usize)
                        .copied()
                    {
                        postgres_attempts = postgres_attempts.saturating_add(1);
                        postgres_restart_after = Instant::now() + delay;
                        self.set_database_restart_count(postgres_attempts);
                    }
                }
                if !self.child_postgres_owned()
                    && postgres_attempts < RESTART_DELAYS.len() as u8
                    && Instant::now() >= postgres_restart_after
                {
                    match start_managed_database(&app_paths) {
                        Ok(process) => {
                            let pid = process.child.id();
                            let database_url = process.database_url.clone();
                            let _ = self
                                .0
                                .database_url
                                .lock()
                                .map(|mut value| *value = Some(database_url));
                            if let Ok(mut children) = self.0.children.lock() {
                                children.postgresql = Some(OwnedPostgres {
                                    child: process.child,
                                    pg_ctl: process.pg_ctl,
                                    data_directory: process.data_directory,
                                });
                            }
                            self.set_database_started(pid, &process.version, process.port);
                            self.audit("managed_postgresql_started", "postgresql");
                            postgres_attempts = 0;
                        }
                        Err(error) => {
                            let (code, reason) = managed_database_error(error);
                            self.set_database_failure(code, reason);
                            if code == "postgres_artifacts_missing"
                                || code == "managed_port_conflict"
                                || code == "unknown_data_directory"
                                || code == "ownership_mismatch"
                                || code == "cluster_marker_missing"
                                || code == "postgres_version_mismatch"
                            {
                                postgres_attempts = RESTART_DELAYS.len() as u8;
                            } else {
                                postgres_attempts = postgres_attempts.saturating_add(1);
                                if let Some(delay) = RESTART_DELAYS
                                    .get(postgres_attempts.saturating_sub(1).min(2) as usize)
                                    .copied()
                                {
                                    postgres_restart_after = Instant::now() + delay;
                                }
                            }
                        }
                    }
                }
                if !self.child_postgres_owned() {
                    if postgres_attempts >= RESTART_DELAYS.len() as u8 {
                        self.set_database_failure("crash_loop", "Managed PostgreSQL could not start after bounded retries. Preserve the data and use the database diagnostics before retrying.");
                    }
                    thread::sleep(HEALTH_INTERVAL);
                    continue;
                }
            } else if database_mode(&profile) != "managed" {
                self.set_database_mode("external");
            } else {
                self.set_database_state("stopped", "owned");
            }
            match probe_backend() {
                BackendProbe::Compatible {
                    ready,
                    prerequisites,
                    database,
                    version,
                } => {
                    if !self.child_owned(Component::Backend)
                        && self.status().backend.ownership != "external"
                    {
                        self.audit("external_backend_detected", "backend");
                    }
                    self.update_backend_external_or_owned(ready, version);
                    self.update_postgresql(database);
                    if prerequisites
                        && self.child_owned(Component::Backend)
                        && self.child_owned(Component::Worker)
                    {
                        self.update_worker_running();
                    } else if prerequisites && self.external_worker_ready() {
                        self.update_worker_external();
                    } else if prerequisites
                        && self.is_enabled(Component::Worker)
                        && self.can_spawn()
                        && worker_attempts < RESTART_DELAYS.len() as u8
                        && Instant::now() >= worker_restart_after
                    {
                        // Starting our fixed worker beside a compatible external backend is
                        // safe: the worker registers in PostgreSQL and is not controlled later.
                        self.launch(
                            Component::Worker,
                            &app_paths,
                            &mut worker_attempts,
                            &mut worker_restart_after,
                        );
                    } else if prerequisites && worker_attempts >= RESTART_DELAYS.len() as u8 {
                        self.set_failure(
                            Component::Worker,
                            "crash_loop",
                            "Worker restart limit reached. Retry it from Local Runtime.",
                        );
                    } else if !database {
                        self.wait_for_database();
                    }
                }
                BackendProbe::PortConflict => {
                    self.set_failure(Component::Backend, "port_conflict", "Port 8000 is occupied by a service that did not pass RavenTech identity checks.");
                    self.message("Backend port conflict. Stop or reconfigure the unrelated local service; RavenTech did not touch it.");
                }
                BackendProbe::Unavailable => {
                    if self.child_owned(Component::Backend) {
                        self.set_state(
                            Component::Backend,
                            "starting",
                            "owned",
                            "waiting",
                            "waiting",
                        );
                    } else if self.is_enabled(Component::Backend)
                        && self.can_spawn()
                        && backend_attempts < RESTART_DELAYS.len() as u8
                        && Instant::now() >= backend_restart_after
                    {
                        self.launch(
                            Component::Backend,
                            &app_paths,
                            &mut backend_attempts,
                            &mut backend_restart_after,
                        );
                    } else if backend_attempts >= RESTART_DELAYS.len() as u8 {
                        self.set_failure(
                            Component::Backend,
                            "crash_loop",
                            "Backend restart limit reached. Retry it from Local Runtime.",
                        );
                    }
                }
                BackendProbe::Incompatible(version) => {
                    self.set_failure(Component::Backend, "version_mismatch", "A RavenTech backend is running with an incompatible release. Close it using its owner.");
                    self.set_version(Component::Backend, version);
                }
                BackendProbe::OtherProfile => {
                    self.set_state(
                        Component::Backend,
                        "external",
                        "external",
                        "informational",
                        "informational",
                    );
                    self.message("A compatible backend is running under another runtime profile. This desktop will not mix runtimes.");
                }
                BackendProbe::WaitingDependency => {
                    self.update_postgresql(false);
                    self.set_state(
                        Component::Backend,
                        "waiting",
                        if self.child_owned(Component::Backend) {
                            "owned"
                        } else {
                            "external"
                        },
                        "waiting",
                        "waiting",
                    );
                    self.set_state(Component::Worker, "stopped", "none", "unknown", "unknown");
                    self.message("PostgreSQL is required. Review the selected managed or external database mode and its status.");
                }
            }
            thread::sleep(HEALTH_INTERVAL);
        }
    }

    fn take_control(&self) -> Control {
        self.0
            .control
            .lock()
            .map(|mut value| {
                let result = Control {
                    stop_backend: value.stop_backend,
                    stop_worker: value.stop_worker,
                    retry_backend: value.retry_backend,
                    retry_worker: value.retry_worker,
                    stop_database: value.stop_database,
                    retry_database: value.retry_database,
                    shutdown: value.shutdown,
                };
                value.stop_backend = false;
                value.stop_worker = false;
                value.retry_backend = false;
                value.retry_worker = false;
                value.stop_database = false;
                value.retry_database = false;
                result
            })
            .unwrap_or_default()
    }

    fn control(&self) -> Control {
        self.0
            .control
            .lock()
            .map(|value| Control {
                shutdown: value.shutdown,
                ..Control::default()
            })
            .unwrap_or_default()
    }

    fn launch(
        &self,
        component: Component,
        paths: &ArtifactPaths,
        attempts: &mut u8,
        retry_at: &mut Instant,
    ) {
        let artifact = match component {
            Component::Backend => paths.backend.as_ref(),
            Component::Worker => paths.worker.as_ref(),
        };
        let Some(artifact) = artifact else {
            self.set_failure(
                component,
                "artifact_missing",
                "The packaged native component is missing. Repair or reinstall RavenTech Desktop.",
            );
            *attempts = RESTART_DELAYS.len() as u8;
            return;
        };
        if !validate_artifact(artifact, component) {
            self.set_failure(
                component,
                "artifact_invalid",
                "The native component manifest, platform, or checksum is invalid.",
            );
            *attempts = RESTART_DELAYS.len() as u8;
            return;
        }
        match executable_version(artifact) {
            Some(version) if version == EXPECTED_VERSION => {}
            Some(_) => {
                self.set_failure(
                    component,
                    "version_mismatch",
                    "The packaged component release does not match this desktop.",
                );
                *attempts = RESTART_DELAYS.len() as u8;
                return;
            }
            None => {
                self.set_failure(component, "artifact_invalid", "The packaged component could not be validated. Repair or reinstall RavenTech Desktop.");
                *attempts = RESTART_DELAYS.len() as u8;
                return;
            }
        }
        let managed_url = self
            .0
            .database_url
            .lock()
            .ok()
            .and_then(|value| value.clone());
        if !executable_check(artifact, managed_url.as_deref()) {
            self.set_failure(component, "configuration_error", "Native runtime configuration or packaged resources are not ready. Check the external PostgreSQL configuration.");
            *attempts = RESTART_DELAYS.len() as u8;
            return;
        }
        if component == Component::Backend {
            if let Some(database_url) = managed_url.as_deref() {
                if let Ok(mut status) = self.0.status.lock() {
                    status.postgresql.migration_state = "updating".to_owned();
                }
                let migration = Command::new(artifact)
                    .arg("--upgrade-database")
                    .current_dir(artifact.parent().unwrap_or(Path::new(".")))
                    .env("RUNTIME_PROFILE", "desktop")
                    .env("BACKGROUND_JOB_BACKEND", "native")
                    .env("NATIVE_WORKER_ENABLED", "true")
                    .env("RAVENTECH_NATIVE_PACKAGE", "1")
                    .env("DATABASE_URL", database_url)
                    .env("DATABASE_RUNTIME", "managed")
                    .stdin(Stdio::null())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status();
                if !migration.is_ok_and(|status| status.success()) {
                    if let Ok(mut status) = self.0.status.lock() {
                        status.postgresql.migration_state = "failed".to_owned();
                    }
                    self.set_failure(component, "migration_failed", "Database migration did not complete. The database was preserved and dependent startup stopped.");
                    *attempts = RESTART_DELAYS.len() as u8;
                    return;
                }
                if let Ok(mut status) = self.0.status.lock() {
                    status.postgresql.migration_state = "current".to_owned();
                }
            }
        }
        self.set_state(component, "starting", "owned", "starting", "waiting");
        let mut command = Command::new(artifact);
        let stop_file = runtime_stop_file(component);
        if let Some(path) = stop_file.as_ref() {
            let _ = std::fs::remove_file(path);
        }
        command
            .arg(if component == Component::Backend {
                "--serve"
            } else {
                "--run"
            })
            .current_dir(artifact.parent().unwrap_or(Path::new(".")))
            .env("RUNTIME_PROFILE", "desktop")
            .env("BACKGROUND_JOB_BACKEND", "native")
            .env(
                "DATABASE_RUNTIME",
                if managed_url.is_some() {
                    "managed"
                } else {
                    "external"
                },
            )
            .env("NATIVE_WORKER_ENABLED", "true")
            .env("RAVENTECH_NATIVE_PACKAGE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if let Some(database_url) = managed_url.as_ref() {
            command.env("DATABASE_URL", database_url);
        }
        if let Some(path) = stop_file {
            command.env("RAVENTECH_DESKTOP_STOP_FILE", path);
        }
        configure_child_process(&mut command);
        match command.spawn() {
            Ok(child) => {
                let pid = child.id();
                if let Ok(mut children) = self.0.children.lock() {
                    match component {
                        Component::Backend => children.backend = Some(child),
                        Component::Worker => children.worker = Some(child),
                    }
                }
                self.set_pid_started(component, pid);
                let status = self.status();
                let restarts = match component {
                    Component::Backend => status.backend.restart_count,
                    Component::Worker => status.worker.restart_count,
                };
                let event = match (component, restarts > 0) {
                    (Component::Backend, true) => "backend_restarted",
                    (Component::Worker, true) => "worker_restarted",
                    (Component::Backend, false) => "backend_started",
                    (Component::Worker, false) => "worker_started",
                };
                self.audit(event, component_name(component));
                self.message(if component == Component::Backend {
                    "Native backend started by this desktop session."
                } else {
                    "Native worker started by this desktop session."
                });
                self.wait_for_component(component);
            }
            Err(_) => {
                self.set_failure(component, "spawn_failed", "The fixed native component could not be started. Check local permissions and packaging.");
                if let Some(delay) = RESTART_DELAYS.get((*attempts).min(2) as usize).copied() {
                    *attempts = attempts.saturating_add(1);
                    *retry_at = Instant::now() + delay;
                }
            }
        }
    }

    fn wait_for_component(&self, component: Component) {
        let start = Instant::now();
        while start.elapsed() < STARTUP_LIMIT {
            if component == Component::Backend {
                if let BackendProbe::Compatible {
                    ready,
                    prerequisites,
                    database,
                    version,
                } = probe_backend()
                {
                    self.update_backend_external_or_owned(ready, version);
                    self.update_postgresql(database);
                    if prerequisites && database {
                        return;
                    }
                }
            } else if self.external_worker_ready() {
                self.update_worker_running();
                return;
            }
            if self.child_exited(component) {
                return;
            }
            thread::sleep(Duration::from_millis(500));
        }
        self.set_failure(
            component,
            "startup_timeout",
            "The native component did not become healthy before the startup deadline.",
        );
    }

    fn external_worker_ready(&self) -> bool {
        matches!(
            probe_backend(),
            BackendProbe::Compatible { ready: true, .. }
        ) && worker_check().as_deref() == Some("ok")
    }

    fn child_owned(&self, component: Component) -> bool {
        self.0
            .children
            .lock()
            .map(|children| match component {
                Component::Backend => children.backend.is_some(),
                Component::Worker => children.worker.is_some(),
            })
            .unwrap_or(false)
    }

    fn is_enabled(&self, component: Component) -> bool {
        self.0
            .desired
            .lock()
            .map(|desired| match component {
                Component::Backend => desired.backend,
                Component::Worker => desired.worker,
            })
            .unwrap_or(false)
    }

    fn can_spawn(&self) -> bool {
        self.0.owns_lease.load(Ordering::Acquire)
    }

    fn child_exited(&self, component: Component) -> bool {
        self.0
            .children
            .lock()
            .map(|mut children| {
                let child = match component {
                    Component::Backend => &mut children.backend,
                    Component::Worker => &mut children.worker,
                };
                child
                    .as_mut()
                    .is_some_and(|value| value.try_wait().ok().flatten().is_some())
            })
            .unwrap_or(false)
    }

    fn reap_exited(&self, component: Component, attempts: &mut u8, retry_at: &mut Instant) {
        let exit = self.0.children.lock().ok().and_then(|mut children| {
            let child = match component {
                Component::Backend => &mut children.backend,
                Component::Worker => &mut children.worker,
            };
            let status = child.as_mut()?.try_wait().ok().flatten()?;
            *child = None;
            Some(status.code())
        });
        if let Some(code) = exit {
            self.set_exit(component, code);
            if let Some(delay) = RESTART_DELAYS.get((*attempts).min(2) as usize).copied() {
                *attempts = attempts.saturating_add(1);
                *retry_at = Instant::now() + delay;
                self.set_restart_count(component, *attempts);
                self.set_failure(
                    component,
                    "unexpected_exit",
                    "The owned component exited unexpectedly. A bounded restart will be attempted.",
                );
            }
        }
    }

    fn stop_owned(&self, component: Component) {
        let mut child = self
            .0
            .children
            .lock()
            .ok()
            .and_then(|mut children| match component {
                Component::Backend => children.backend.take(),
                Component::Worker => children.worker.take(),
            });
        if let Some(ref mut child) = child {
            self.set_state(component, "stopping", "owned", "stopping", "stopping");
            if let Some(path) = runtime_stop_file(component) {
                if let Some(parent) = path.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                let _ = std::fs::write(path, b"stop");
            }
            let start = Instant::now();
            loop {
                if child.try_wait().ok().flatten().is_some() {
                    break;
                }
                let stop_limit = if component == Component::Worker {
                    WORKER_STOP_LIMIT
                } else {
                    BACKEND_STOP_LIMIT
                };
                if start.elapsed() >= stop_limit {
                    let _ = child.kill();
                    let _ = child.wait();
                    break;
                }
                thread::sleep(Duration::from_millis(100));
            }
            self.message(if component == Component::Backend {
                "Owned backend stopped."
            } else {
                "Owned worker stopped."
            });
            self.audit(
                if component == Component::Backend {
                    "backend_stopped"
                } else {
                    "worker_stopped"
                },
                component_name(component),
            );
        }
        if !matches!(probe_backend(), BackendProbe::Compatible { .. })
            && component == Component::Backend
        {
            self.set_state(component, "stopped", "none", "unknown", "unknown");
        } else if component == Component::Worker {
            self.set_state(component, "stopped", "none", "unknown", "unknown");
        }
    }

    fn update_backend_external_or_owned(&self, ready: bool, version: String) {
        let owned = self.child_owned(Component::Backend);
        let mut state = self.0.status.lock().expect("runtime status lock");
        let was_failed = state.backend.state == "failed";
        state.backend.state = if ready { "healthy" } else { "waiting" }.to_owned();
        state.backend.ownership = if owned { "owned" } else { "external" }.to_owned();
        state.backend.pid = if owned { state.backend.pid } else { None };
        state.backend.version = Some(version);
        state.backend.health = if ready { "healthy" } else { "waiting" }.to_owned();
        state.backend.readiness = if ready { "ready" } else { "waiting" }.to_owned();
        state.backend.actions_available = owned;
        state.backend.last_error = None;
        drop(state);
        if was_failed && ready {
            self.audit("backend_recovered", "backend");
        }
    }

    fn update_worker_running(&self) {
        let owned = self.child_owned(Component::Worker);
        if let Ok(mut status) = self.0.status.lock() {
            let was_failed = status.worker.state == "failed";
            status.worker.state = "running".to_owned();
            status.worker.ownership = if owned { "owned" } else { "external" }.to_owned();
            status.worker.health = "healthy".to_owned();
            status.worker.readiness = "ready".to_owned();
            status.worker.actions_available = owned;
            status.worker.last_error = None;
            status.worker.heartbeat_at_unix_ms = Some(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis(),
            );
            drop(status);
            if was_failed {
                self.audit("worker_recovered", "worker");
            }
        }
    }

    fn update_worker_external(&self) {
        self.update_worker_running();
    }

    fn update_postgresql(&self, available: bool) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.state = if available { "healthy" } else { "unavailable" }.to_owned();
            if status.postgresql.mode == "external" {
                status.postgresql.ownership = "external".to_owned();
                status.postgresql.actions_available = false;
            } else if available {
                status.postgresql.migration_state = "current".to_owned();
            }
        }
    }

    fn wait_for_database(&self) {
        self.update_postgresql(false);
        self.set_state(Component::Backend, "waiting", "owned", "waiting", "waiting");
        self.set_state(Component::Worker, "stopped", "none", "unknown", "unknown");
        self.message(
            "PostgreSQL is required. Check the selected database mode and local database status.",
        );
    }

    fn child_postgres_owned(&self) -> bool {
        self.0
            .children
            .lock()
            .map(|children| children.postgresql.is_some())
            .unwrap_or(false)
    }
    fn is_database_enabled(&self) -> bool {
        self.0
            .desired
            .lock()
            .map(|desired| desired.database)
            .unwrap_or(false)
    }

    fn child_postgres_exited(&self) -> bool {
        self.0
            .children
            .lock()
            .map(|mut children| {
                children
                    .postgresql
                    .as_mut()
                    .is_some_and(|owned| owned.child.try_wait().ok().flatten().is_some())
            })
            .unwrap_or(false)
    }

    fn reap_postgres(&self) {
        if let Ok(mut children) = self.0.children.lock() {
            if let Some(mut owned) = children.postgresql.take() {
                let code = owned
                    .child
                    .try_wait()
                    .ok()
                    .flatten()
                    .and_then(|value| value.code());
                self.set_database_exit(code);
            }
        }
    }

    fn stop_managed_postgres(&self) {
        let mut owned = self
            .0
            .children
            .lock()
            .ok()
            .and_then(|mut children| children.postgresql.take());
        if let Some(owned_child) = owned.as_mut() {
            let stopped = managed_postgres::stop(
                &mut owned_child.child,
                &owned_child.pg_ctl,
                &owned_child.data_directory,
            );
            if stopped {
                self.set_database_state("stopped", "owned");
                self.audit("managed_postgresql_stopped", "postgresql");
            } else {
                self.set_database_failure("shutdown_timeout", "Managed PostgreSQL did not confirm a clean shutdown. Its data directory was preserved.");
                if let Ok(mut children) = self.0.children.lock() {
                    children.postgresql = owned.take();
                }
            }
        }
    }

    fn set_database_mode(&self, mode: &str) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.mode = mode.to_owned();
            if mode == "external" {
                status.postgresql.ownership = "external".to_owned();
                status.postgresql.actions_available = false;
            }
        }
    }
    fn set_database_started(&self, pid: u32, version: &str, port: u16) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.mode = "managed".to_owned();
            status.postgresql.state = "healthy".to_owned();
            status.postgresql.pid = Some(pid);
            status.postgresql.ownership = "owned".to_owned();
            status.postgresql.version = Some(version.to_owned());
            status.postgresql.port = Some(port);
            status.postgresql.local_only = true;
            status.postgresql.initialized = true;
            status.postgresql.migration_state = "pending".to_owned();
            status.postgresql.started_at_unix_ms = Some(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis(),
            );
            status.postgresql.last_error = None;
            status.postgresql.last_error_code = None;
            status.postgresql.last_exit_code = None;
            status.postgresql.actions_available = true;
        }
    }
    fn set_database_failure(&self, code: &str, reason: &str) {
        let mut changed = false;
        if let Ok(mut status) = self.0.status.lock() {
            changed = status.postgresql.state != "failed"
                || status.postgresql.last_error.as_deref() != Some(reason);
            status.postgresql.state = "failed".to_owned();
            status.postgresql.pid = None;
            status.postgresql.last_error_code = Some(code.to_owned());
            status.postgresql.last_error = Some(reason.to_owned());
            status.postgresql.actions_available = false;
            status.postgresql.migration_state = "unknown".to_owned();
        }
        self.message(reason);
        if changed {
            self.audit(&format!("managed_postgresql_{code}"), "postgresql");
        }
    }
    fn set_database_restart_count(&self, count: u8) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.restart_count = count;
        }
    }
    fn set_database_exit(&self, code: Option<i32>) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.state = "failed".to_owned();
            status.postgresql.pid = None;
            status.postgresql.last_exit_code = code;
            status.postgresql.last_error_code = Some("postgres_exited".to_owned());
            status.postgresql.actions_available = false;
            status.postgresql.last_error = Some("Managed PostgreSQL exited unexpectedly. Data was preserved; a bounded restart may be attempted.".to_owned());
        }
    }
    fn set_database_state(&self, state: &str, ownership: &str) {
        if let Ok(mut status) = self.0.status.lock() {
            status.postgresql.state = state.to_owned();
            status.postgresql.pid = None;
            status.postgresql.ownership = ownership.to_owned();
            status.postgresql.actions_available = false;
        }
    }

    fn set_pid_started(&self, component: Component, pid: u32) {
        if let Ok(mut status) = self.0.status.lock() {
            let value = match component {
                Component::Backend => &mut status.backend,
                Component::Worker => &mut status.worker,
            };
            value.pid = Some(pid);
            value.ownership = "owned".to_owned();
            value.state = "starting".to_owned();
            value.started_at_unix_ms = Some(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis(),
            );
            value.actions_available = true;
        }
    }

    fn set_version(&self, component: Component, version: String) {
        if let Ok(mut status) = self.0.status.lock() {
            match component {
                Component::Backend => status.backend.version = Some(version),
                Component::Worker => status.worker.version = Some(version),
            }
        }
    }

    fn set_exit(&self, component: Component, code: Option<i32>) {
        if let Ok(mut status) = self.0.status.lock() {
            let value = match component {
                Component::Backend => &mut status.backend,
                Component::Worker => &mut status.worker,
            };
            value.last_exit_code = code;
            value.pid = None;
            value.actions_available = false;
        }
    }

    fn set_restart_count(&self, component: Component, count: u8) {
        if let Ok(mut status) = self.0.status.lock() {
            let value = match component {
                Component::Backend => &mut status.backend,
                Component::Worker => &mut status.worker,
            };
            value.restart_count = count;
        }
    }

    fn set_state(
        &self,
        component: Component,
        state: &str,
        ownership: &str,
        health: &str,
        readiness: &str,
    ) {
        if let Ok(mut status) = self.0.status.lock() {
            let value = match component {
                Component::Backend => &mut status.backend,
                Component::Worker => &mut status.worker,
            };
            value.state = state.to_owned();
            value.ownership = ownership.to_owned();
            value.health = health.to_owned();
            value.readiness = readiness.to_owned();
            value.actions_available = ownership == "owned" && value.pid.is_some();
        }
    }

    fn set_failure(&self, component: Component, code: &str, reason: &str) {
        let mut should_audit = false;
        if let Ok(mut status) = self.0.status.lock() {
            let value = match component {
                Component::Backend => &mut status.backend,
                Component::Worker => &mut status.worker,
            };
            should_audit = value.state != "failed" || value.last_error.as_deref() != Some(reason);
            value.state = "failed".to_owned();
            value.health = "degraded".to_owned();
            value.last_error = Some(reason.to_owned());
        }
        self.message(reason);
        if should_audit {
            let event = if code == "port_conflict" {
                "port_conflict"
            } else if code == "crash_loop" {
                "crash_loop_detected"
            } else if component == Component::Backend {
                "backend_failed"
            } else {
                "worker_failed"
            };
            self.audit(event, component_name(component));
        }
    }

    fn message(&self, message: &str) {
        if let Ok(mut status) = self.0.status.lock() {
            if status
                .last_messages
                .last()
                .is_some_and(|previous| previous == message)
            {
                return;
            }
            status
                .last_messages
                .push(message.chars().take(240).collect());
            if status.last_messages.len() > 12 {
                status.last_messages.remove(0);
            }
        }
    }

    fn audit(&self, event: &str, component: &str) {
        let Some(path) = runtime_stop_file(Component::Backend).and_then(|value| {
            value
                .parent()
                .map(|parent| parent.join("runtime-audit.jsonl"))
        }) else {
            return;
        };
        let Some(parent) = path.parent() else {
            return;
        };
        if std::fs::create_dir_all(parent).is_err() {
            return;
        }
        if std::fs::metadata(&path).is_ok_and(|metadata| metadata.len() > 262_144) {
            let old = path.with_extension("jsonl.1");
            let _ = std::fs::remove_file(&old);
            let _ = std::fs::rename(&path, old);
        }
        let row = serde_json::json!({
            "event": format!("desktop_runtime.{event}"),
            "component": component,
            "timestamp_unix_ms": SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis(),
        });
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
        {
            use std::io::Write;
            let _ = writeln!(file, "{row}");
        }
    }
}

#[derive(Default)]
struct ArtifactPaths {
    root: Option<PathBuf>,
    backend: Option<PathBuf>,
    worker: Option<PathBuf>,
}

fn artifact_paths(app: &AppHandle) -> ArtifactPaths {
    if std::env::consts::ARCH != "x86_64" {
        return ArtifactPaths::default();
    }
    let mut roots = Vec::new();
    if let Ok(resource_dir) = app.path().resource_dir() {
        roots.push(resource_dir.join("native-runtime"));
    }
    #[cfg(debug_assertions)]
    let desktop = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    #[cfg(all(target_os = "windows", debug_assertions))]
    roots.push(desktop.join("dist-native/windows-x86_64"));
    #[cfg(all(target_os = "linux", debug_assertions))]
    roots.push(desktop.join("dist-native/linux-x86_64"));
    #[cfg(target_os = "windows")]
    let (backend_name, worker_name) = ("RavenTechBackend.exe", "RavenTechWorker.exe");
    #[cfg(target_os = "linux")]
    let (backend_name, worker_name) = ("raventech-backend", "raventech-worker");
    #[cfg(not(any(target_os = "windows", target_os = "linux")))]
    let (backend_name, worker_name) = ("", "");
    for root in roots {
        let backend = root.join("backend").join(backend_name);
        let worker = root.join("worker").join(worker_name);
        if backend.is_file() && worker.is_file() {
            return ArtifactPaths {
                root: Some(root),
                backend: Some(backend),
                worker: Some(worker),
            };
        }
    }
    ArtifactPaths::default()
}

fn runtime_data_and_state_paths() -> Option<(PathBuf, PathBuf)> {
    #[cfg(debug_assertions)]
    if let Some(test_root) = std::env::var_os("RAVENTECH_TEST_DATABASE_ROOT") {
        let root = PathBuf::from(test_root);
        if !root.is_absolute()
            || std::fs::symlink_metadata(&root)
                .ok()?
                .file_type()
                .is_symlink()
        {
            return None;
        }
        let marker = std::fs::read_to_string(root.join("PHASE5BM-ISOLATED-TEST")).ok()?;
        if marker != "RAVENTECH-PHASE5BM-ISOLATED-TEST\n"
            && marker != "RAVENTECH-PHASE5BM-ISOLATED-TEST"
        {
            return None;
        }
        let canonical = root.canonicalize().ok()?;
        if !canonical.starts_with(std::env::temp_dir().canonicalize().ok()?) {
            return None;
        }
        return Some((canonical.join("data"), canonical.join("state")));
    }
    #[cfg(target_os = "windows")]
    {
        let root = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)?
            .join("RavenTech OSINT");
        return Some((root.clone(), root));
    }
    #[cfg(target_os = "linux")]
    {
        let home = PathBuf::from(std::env::var_os("HOME")?);
        let data = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local/share"))
            .join("raventech-osint");
        let state = std::env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local/state"))
            .join("raventech-osint");
        return Some((data, state));
    }
    #[allow(unreachable_code)]
    None
}

fn database_mode(profile: &str) -> &'static str {
    if profile != "desktop" {
        return "external";
    }
    if let Ok(mode) = std::env::var("DATABASE_RUNTIME") {
        if mode.eq_ignore_ascii_case("external") {
            return "external";
        }
        if mode.eq_ignore_ascii_case("managed") {
            return "managed";
        }
    }
    let config = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|root| root.join("RavenTech OSINT/config/.env"))
        .or_else(|| {
            std::env::var_os("XDG_CONFIG_HOME")
                .map(PathBuf::from)
                .map(|root| root.join("raventech-osint/.env"))
        })
        .or_else(|| {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|root| root.join(".config/raventech-osint/.env"))
        });
    if config
        .and_then(|path| std::fs::read_to_string(path).ok())
        .is_some_and(|contents| {
            contents
                .lines()
                .any(|line| line.trim_start().starts_with("DATABASE_URL="))
        })
    {
        "external"
    } else {
        "managed"
    }
}

fn start_managed_database(
    paths: &ArtifactPaths,
) -> Result<ManagedProcess, managed_postgres::RuntimeError> {
    let root = paths
        .root
        .as_ref()
        .ok_or(managed_postgres::RuntimeError::ArtifactsMissing)?;
    let (data, state) =
        runtime_data_and_state_paths().ok_or(managed_postgres::RuntimeError::UnsafePath)?;
    managed_postgres::start(root, &data, &state)
}

fn managed_database_error(error: managed_postgres::RuntimeError) -> (&'static str, &'static str) {
    match error {
        managed_postgres::RuntimeError::RootNotAllowed => ("root_not_allowed", "Managed PostgreSQL cannot run as root. Launch RavenTech Desktop as a regular user."),
        managed_postgres::RuntimeError::ArtifactsMissing => ("postgres_artifacts_missing", "The bundled PostgreSQL 16 runtime is unavailable or incomplete. Repair the desktop installation."),
        managed_postgres::RuntimeError::VersionMismatch => ("postgres_version_mismatch", "The managed PostgreSQL runtime or existing data major version is incompatible. Data was preserved."),
        managed_postgres::RuntimeError::PortConflict => ("managed_port_conflict", "The managed local PostgreSQL port 55432 is occupied. RavenTech did not contact or stop that process."),
        managed_postgres::RuntimeError::UnknownDataDirectory => ("unknown_data_directory", "The managed database directory contains unknown data and was left untouched."),
        managed_postgres::RuntimeError::OwnershipMismatch => ("ownership_mismatch", "The database ownership marker is invalid. Data was preserved and no process was started."),
        managed_postgres::RuntimeError::ExistingClusterWithoutMarker => ("cluster_marker_missing", "An existing PostgreSQL cluster has no RavenTech ownership marker. It was not adopted or modified."),
        managed_postgres::RuntimeError::SecretUnavailable => ("database_secret_unavailable", "The managed database credential is unavailable or invalid. Data was preserved."),
        managed_postgres::RuntimeError::IncompleteInitialization => ("incomplete_initialization", "Managed PostgreSQL initialization was interrupted. RavenTech will not repeat initdb automatically."),
        managed_postgres::RuntimeError::InitFailed => ("cluster_initialization_failed", "PostgreSQL initialization failed. The data directory was preserved; manual retry is required."),
        managed_postgres::RuntimeError::StartFailed => ("postgres_start_failed", "Managed PostgreSQL exited during startup. Review the sanitized database status and logs."),
        managed_postgres::RuntimeError::ReadinessTimeout => ("postgres_readiness_timeout", "Managed PostgreSQL did not become ready before the startup deadline. Data was preserved."),
        managed_postgres::RuntimeError::DatabaseBootstrapFailed => ("database_bootstrap_failed", "The RavenTech database could not be created. The cluster was preserved for diagnosis."),
        managed_postgres::RuntimeError::UnsafePath => ("unsafe_runtime_path", "A managed database path is not a regular user-owned path. No data was changed."),
        managed_postgres::RuntimeError::UnsupportedPlatform => ("unsupported_platform", "Managed PostgreSQL is supported only on Windows and Linux x86_64."),
        managed_postgres::RuntimeError::Io => ("runtime_io_error", "A managed PostgreSQL runtime file could not be safely read or written."),
    }
}

fn executable_version(path: &Path) -> Option<String> {
    let output = Command::new(path)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let version = String::from_utf8(output.stdout).ok()?.trim().to_owned();
    (!version.is_empty()).then_some(version)
}

fn executable_check(path: &Path, database_url: Option<&str>) -> bool {
    let mut command = Command::new(path);
    command
        .arg("--check")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .env("RUNTIME_PROFILE", "desktop")
        .env("BACKGROUND_JOB_BACKEND", "native")
        .env("NATIVE_WORKER_ENABLED", "true")
        .env("RAVENTECH_NATIVE_PACKAGE", "1");
    if let Some(database_url) = database_url {
        command
            .env("DATABASE_URL", database_url)
            .env("DATABASE_RUNTIME", "managed");
    }
    command.status().is_ok_and(|status| status.success())
}

fn validate_artifact(path: &Path, component: Component) -> bool {
    let Some(root) = path.parent() else {
        return false;
    };
    let Ok(bytes) = std::fs::read(root.join("manifest.json")) else {
        return false;
    };
    let Ok(manifest) = serde_json::from_slice::<serde_json::Value>(&bytes) else {
        return false;
    };
    let expected_component = component_name(component);
    let expected_os = if cfg!(target_os = "windows") {
        "windows"
    } else {
        "linux"
    };
    if manifest
        .get("component")
        .and_then(serde_json::Value::as_str)
        != Some(expected_component)
        || manifest.get("os").and_then(serde_json::Value::as_str) != Some(expected_os)
        || manifest
            .get("architecture")
            .and_then(serde_json::Value::as_str)
            != Some("x86_64")
        || manifest.get("version").and_then(serde_json::Value::as_str) != Some(EXPECTED_VERSION)
        || !manifest
            .get("packaging_engine")
            .and_then(serde_json::Value::as_str)
            .is_some_and(|value| value.starts_with("PyInstaller "))
    {
        return false;
    }
    let Ok(mut file) = std::fs::File::open(path) else {
        return false;
    };
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        match file.read(&mut buffer) {
            Ok(0) => break,
            Ok(size) => hasher.update(&buffer[..size]),
            Err(_) => return false,
        }
    }
    let digest = hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    let size = std::fs::metadata(path)
        .map(|metadata| metadata.len())
        .unwrap_or_default();
    manifest
        .get("binary_sha256")
        .and_then(serde_json::Value::as_str)
        == Some(digest.as_str())
        && manifest
            .get("binary_size_bytes")
            .and_then(serde_json::Value::as_u64)
            == Some(size)
}

#[cfg(target_os = "windows")]
fn configure_child_process(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    command.creation_flags(0x08000000 | 0x00000200); // CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
}

#[cfg(not(target_os = "windows"))]
fn configure_child_process(_command: &mut Command) {}

enum BackendProbe {
    Unavailable,
    PortConflict,
    Incompatible(String),
    OtherProfile,
    WaitingDependency,
    Compatible {
        ready: bool,
        prerequisites: bool,
        database: bool,
        version: String,
    },
}

fn probe_backend() -> BackendProbe {
    let health = super::fixed_http_get(BACKEND_URL, "/health");
    let Some((_health_code, health_body, _)) = health else {
        return if super::port_status(BACKEND_URL, false) == "occupied" {
            BackendProbe::PortConflict
        } else {
            BackendProbe::Unavailable
        };
    };
    let Ok(health_json) = serde_json::from_str::<serde_json::Value>(&health_body) else {
        return BackendProbe::PortConflict;
    };
    let Some(checks) = health_json
        .get("checks")
        .and_then(serde_json::Value::as_object)
    else {
        return BackendProbe::PortConflict;
    };
    if !["database", "migrations", "storage", "worker"]
        .iter()
        .all(|key| checks.contains_key(*key))
    {
        return BackendProbe::PortConflict;
    }
    if health_json
        .get("runtime_profile")
        .and_then(serde_json::Value::as_str)
        != Some("desktop")
        || health_json
            .get("background_job_backend")
            .and_then(serde_json::Value::as_str)
            != Some("native")
    {
        return BackendProbe::OtherProfile;
    }
    let database = checks
        .get("database")
        .and_then(|value| value.get("status"))
        .and_then(serde_json::Value::as_str)
        == Some("ok");
    let release = super::fixed_http_get(BACKEND_URL, "/api/v1/release");
    let Some((code, body, _)) = release else {
        return if !database {
            BackendProbe::WaitingDependency
        } else {
            BackendProbe::PortConflict
        };
    };
    let Ok(release_json) = serde_json::from_str::<serde_json::Value>(&body) else {
        return if !database {
            BackendProbe::WaitingDependency
        } else {
            BackendProbe::PortConflict
        };
    };
    if !(200..300).contains(&code) {
        return if !database {
            BackendProbe::WaitingDependency
        } else {
            BackendProbe::PortConflict
        };
    }
    if release_json
        .get("app_name")
        .and_then(serde_json::Value::as_str)
        != Some("RavenTech OSINT")
        || release_json
            .get("version")
            .and_then(serde_json::Value::as_str)
            .is_none()
    {
        return BackendProbe::PortConflict;
    }
    let version = release_json["version"]
        .as_str()
        .unwrap_or_default()
        .to_owned();
    if version != EXPECTED_VERSION {
        return BackendProbe::Incompatible(version);
    }
    let ready_doc = super::fixed_http_get(BACKEND_URL, "/health/ready");
    let ready = ready_doc.as_ref().is_some_and(|(status, text, _)| {
        (200..300).contains(status)
            && serde_json::from_str::<serde_json::Value>(text)
                .ok()
                .and_then(|value| {
                    value
                        .get("status")
                        .and_then(serde_json::Value::as_str)
                        .map(str::to_owned)
                })
                .as_deref()
                == Some("ok")
    });
    let checks = health_json.get("checks");
    let prerequisites = checks.is_some_and(|value| {
        ["database", "migrations", "storage"].iter().all(|key| {
            value
                .get(*key)
                .and_then(|item| item.get("status"))
                .and_then(serde_json::Value::as_str)
                == Some("ok")
        })
    });
    BackendProbe::Compatible {
        ready,
        prerequisites,
        database,
        version,
    }
}

fn worker_check() -> Option<String> {
    let (_, body, _) = super::fixed_http_get(BACKEND_URL, "/health")
        .filter(|(code, _, _)| (200..300).contains(code))?;
    let value: serde_json::Value = serde_json::from_str(&body).ok()?;
    value
        .get("checks")?
        .get("worker")?
        .get("status")?
        .as_str()
        .map(str::to_owned)
}

fn runtime_stop_file(component: Component) -> Option<PathBuf> {
    let base = if cfg!(target_os = "windows") {
        std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)?
            .join("RavenTech OSINT")
    } else {
        let state = std::env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/state"))
            })?;
        state.join("raventech-osint")
    };
    Some(base.join("runtime").join(match component {
        Component::Backend => "backend.stop",
        Component::Worker => "worker.stop",
    }))
}

fn component_name(component: Component) -> &'static str {
    match component {
        Component::Backend => "backend",
        Component::Worker => "worker",
    }
}

#[cfg(target_os = "windows")]
#[link(name = "kernel32")]
extern "system" {
    fn CreateMutexW(
        attributes: *mut std::ffi::c_void,
        owner: i32,
        name: *const u16,
    ) -> *mut std::ffi::c_void;
    fn GetLastError() -> u32;
    fn CloseHandle(handle: *mut std::ffi::c_void) -> i32;
}

#[cfg(target_os = "windows")]
fn acquire_lease() -> Option<SupervisorLease> {
    let name: Vec<u16> = "Local\\RavenTechOSINT-NativeRuntime-5-0-0-rc6"
        .encode_utf16()
        .chain(std::iter::once(0))
        .collect();
    let handle = unsafe { CreateMutexW(std::ptr::null_mut(), 0, name.as_ptr()) };
    if handle.is_null() {
        return None;
    }
    if unsafe { GetLastError() } == 183 {
        unsafe {
            let _ = CloseHandle(handle);
        }
        return None;
    }
    Some(SupervisorLease {
        _file: None,
        handle: handle as usize,
    })
}

#[cfg(target_os = "linux")]
fn acquire_lease() -> Option<SupervisorLease> {
    use std::os::fd::AsRawFd;
    extern "C" {
        fn flock(fd: i32, operation: i32) -> i32;
    }
    let path = runtime_stop_file(Component::Backend)?
        .parent()?
        .join("supervisor.lock");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok()?;
    }
    let file = std::fs::OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(path)
        .ok()?;
    (unsafe { flock(file.as_raw_fd(), 2 | 4) } == 0)
        .then_some(SupervisorLease { _file: Some(file) })
}

#[cfg(not(any(target_os = "windows", target_os = "linux")))]
fn acquire_lease() -> Option<SupervisorLease> {
    None
}

#[tauri::command]
pub fn get_native_runtime_status(supervisor: State<'_, NativeRuntimeSupervisor>) -> RuntimeStatus {
    supervisor.status()
}

#[tauri::command]
pub fn control_native_runtime_component(
    supervisor: State<'_, NativeRuntimeSupervisor>,
    component: String,
    action: String,
    confirmed: bool,
) -> Result<(), String> {
    if component == "postgresql" {
        return supervisor.request_database(&action, confirmed);
    }
    let component = match component.as_str() {
        "backend" => Component::Backend,
        "worker" => Component::Worker,
        _ => return Err("Unsupported local runtime component".to_owned()),
    };
    supervisor.request(component, &action, confirmed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_is_normalized_and_marks_optional_services() {
        let status = RuntimeStatus::default();
        assert_eq!(
            status.runtime_mode,
            if cfg!(debug_assertions) {
                "development"
            } else {
                "desktop"
            }
        );
        assert!(status.postgresql.required);
        assert!(!status.redis.required);
        assert!(!status.celery.required);
        assert_eq!(status.backend.ownership, "unknown");
    }

    #[test]
    fn runtime_actions_are_fixed_confirmed_and_owned_only() {
        let supervisor = NativeRuntimeSupervisor::default();
        assert!(supervisor
            .request(Component::Backend, "shell", true)
            .is_err());
        assert!(supervisor
            .request(Component::Backend, "stop", false)
            .is_err());
        assert!(supervisor
            .request(Component::Backend, "stop", true)
            .is_err());
    }

    #[test]
    fn child_environment_cannot_select_compatibility_runtime() {
        let artifact = Path::new("fixed-native-artifact");
        assert!(!artifact.to_string_lossy().contains("DATABASE_URL"));
        assert_eq!(EXPECTED_VERSION, "5.0.0-rc6");
    }
}
