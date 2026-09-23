//! Fixed, per-user PostgreSQL 16 runtime for the desktop profile.
//!
//! This module never discovers executables through PATH and never runs a shell.
//! The only executable paths are under the validated native-runtime resource.

use serde::{Deserialize, Serialize};
#[cfg(unix)]
use std::fs::File;
use std::fs::{self, OpenOptions};
#[cfg(unix)]
use std::io::Read;
use std::io::Write;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const POSTGRES_MAJOR: u32 = 16;
pub const MANAGED_PORT: u16 = 55432;
const APP_ID: &str = "com.raventech.osint";
const DATABASE_USER: &str = "raventech";
const DATABASE_NAME: &str = "raventech";
const BOOTSTRAP_USER: &str = "raventech_runtime";
const HBA_POLICY: &[u8] = b"# RavenTech managed PostgreSQL: loopback only, password authentication.\nhost all all 127.0.0.1/32 scram-sha-256\n";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OwnershipMarker {
    pub application_id: String,
    pub runtime_format: u32,
    pub postgres_major: u32,
    pub created_at_unix: u64,
    pub installation_id: String,
    pub port: u16,
    pub initialized: bool,
}

#[derive(Debug)]
pub struct ManagedProcess {
    pub child: Child,
    pub pg_ctl: PathBuf,
    pub database_url: String,
    pub data_directory: PathBuf,
    pub version: String,
    pub port: u16,
}

#[derive(Debug)]
pub enum RuntimeError {
    UnsupportedPlatform,
    #[allow(dead_code)]
    RootNotAllowed,
    ArtifactsMissing,
    VersionMismatch,
    PortConflict,
    UnknownDataDirectory,
    OwnershipMismatch,
    ExistingClusterWithoutMarker,
    IncompleteInitialization,
    SecretUnavailable,
    InitFailed {
        class: InitFailureClass,
        exit_code: Option<i32>,
        resource_hint: Option<InitResourceHint>,
    },
    InitSpawnFailed(InitFailureClass),
    StartFailed,
    ReadinessTimeout,
    DatabaseBootstrapFailed,
    UnsafePath,
    Io,
}

pub fn start(
    resource_root: &Path,
    data_root: &Path,
    state_root: &Path,
) -> Result<ManagedProcess, RuntimeError> {
    if !cfg!(any(target_os = "windows", target_os = "linux")) {
        return Err(RuntimeError::UnsupportedPlatform);
    }
    #[cfg(target_os = "linux")]
    if unsafe { geteuid() } == 0 {
        return Err(RuntimeError::RootNotAllowed);
    }

    // PostgreSQL's Windows executable discovery does not handle the Win32
    // extended-length `\\?\` prefix when initdb searches for its sibling
    // postgres.exe. Tauri's resource resolver can return that spelling even
    // though the same packaged files work through ordinary DOS paths.
    let resource_root = postgres_compatible_resource_root(resource_root)?;
    let runtime = resource_root.join("postgresql");
    let bin = runtime.join("bin");
    let share = runtime.join("share");
    let postgres = executable(&bin, "postgres");
    let initdb = executable(&bin, "initdb");
    let psql = executable(&bin, "psql");
    let is_ready = executable(&bin, "pg_isready");
    let pg_ctl = executable(&bin, "pg_ctl");
    let lib = runtime.join("lib");
    if ![&postgres, &initdb, &psql, &is_ready, &pg_ctl]
        .iter()
        .all(|path| path.is_file())
        || !share.is_dir()
        || !lib.is_dir()
    {
        return Err(RuntimeError::ArtifactsMissing);
    }
    if !port_available(MANAGED_PORT) {
        return Err(RuntimeError::PortConflict);
    }
    let version = output(&postgres, "--version")?;
    if !version.contains("PostgreSQL) 16.") && !version.contains("PostgreSQL 16.") {
        return Err(RuntimeError::VersionMismatch);
    }
    if !version.starts_with("postgres (PostgreSQL) 16.") {
        return Err(RuntimeError::VersionMismatch);
    }

    let pg_root = data_root.join("postgres");
    let data_directory = pg_root.join("16");
    let state_directory = state_root.join("runtime").join("postgres");
    create_private_dir(&pg_root)?;
    create_private_dir(&state_directory)?;
    reject_symlink(&pg_root)?;
    reject_symlink(&state_directory)?;
    if data_directory.exists() {
        reject_symlink(&data_directory)?;
    }
    let marker_path = pg_root.join("ownership.json");
    let secret_path = state_directory.join("database.secret");
    if marker_path.exists() {
        reject_symlink(&marker_path)?;
        let marker: OwnershipMarker =
            serde_json::from_slice(&fs::read(&marker_path).map_err(|_| RuntimeError::Io)?)
                .map_err(|_| RuntimeError::OwnershipMismatch)?;
        validate_marker(&marker)?;
        if !data_directory.join("PG_VERSION").is_file()
            && !can_retry_empty_initialization(&marker, &data_directory)?
        {
            return Err(RuntimeError::IncompleteInitialization);
        }
    } else {
        if fs::read_dir(&pg_root)
            .map_err(|_| RuntimeError::Io)?
            .any(|entry| entry.ok().is_some_and(|entry| entry.file_name() != "16"))
        {
            return Err(RuntimeError::UnknownDataDirectory);
        }
        if data_directory.exists() {
            reject_symlink(&data_directory)?;
            if fs::read_dir(&data_directory)
                .map_err(|_| RuntimeError::Io)?
                .next()
                .is_some()
            {
                return if data_directory.join("PG_VERSION").exists() {
                    Err(RuntimeError::ExistingClusterWithoutMarker)
                } else {
                    Err(RuntimeError::UnknownDataDirectory)
                };
            }
        }
        if data_directory.join("PG_VERSION").exists() {
            return Err(RuntimeError::ExistingClusterWithoutMarker);
        }
    }

    if !secret_path.exists() {
        if marker_path.exists() {
            return Err(RuntimeError::SecretUnavailable);
        }
        write_new_secret(&secret_path)?;
    }
    reject_symlink(&secret_path)?;
    let password = fs::read_to_string(&secret_path).map_err(|_| RuntimeError::SecretUnavailable)?;
    let password = password.trim().to_owned();
    if password.len() < 64 || !password.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(RuntimeError::SecretUnavailable);
    }

    if !marker_path.exists() {
        fs::create_dir_all(&data_directory).map_err(|_| RuntimeError::Io)?;
        let marker = OwnershipMarker {
            application_id: APP_ID.to_owned(),
            runtime_format: 1,
            postgres_major: POSTGRES_MAJOR,
            created_at_unix: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            installation_id: random_hex(16)?,
            port: MANAGED_PORT,
            initialized: false,
        };
        write_json_atomic(&marker_path, &marker)?;
    }
    let marker: OwnershipMarker =
        serde_json::from_slice(&fs::read(&marker_path).map_err(|_| RuntimeError::Io)?)
            .map_err(|_| RuntimeError::OwnershipMismatch)?;
    validate_marker(&marker)?;
    let bootstrap_database = !marker.initialized;

    if !data_directory.join("PG_VERSION").exists() {
        if fs::read_dir(&data_directory)
            .map_err(|_| RuntimeError::Io)?
            .any(|entry| entry.ok().is_some_and(|entry| entry.file_name() != ""))
        {
            return Err(RuntimeError::UnknownDataDirectory);
        }
        let pwfile = state_directory.join("initdb-password.tmp");
        write_private_file(&pwfile, password.as_bytes())?;
        let init = Command::new(&initdb)
            .args([
                "--encoding=UTF8",
                "--auth-host=scram-sha-256",
                "--auth-local=scram-sha-256",
                "--username=raventech_runtime",
                "--pwfile",
            ])
            .arg(&pwfile)
            .arg("--pgdata")
            .arg(&data_directory)
            .arg("-L")
            .arg(&share)
            .current_dir(&bin)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output();
        let _ = fs::remove_file(&pwfile);
        match init {
            Ok(output) if output.status.success() => {}
            Ok(output) => {
                return Err(RuntimeError::InitFailed {
                    class: classify_init_output(&output.stdout, &output.stderr),
                    exit_code: output.status.code(),
                    resource_hint: missing_resource_hint(&output.stdout, &output.stderr),
                });
            }
            Err(error) => {
                return Err(RuntimeError::InitSpawnFailed(classify_io_error(&error)));
            }
        }
    }
    if !marker.initialized && !data_directory.join("PG_VERSION").is_file() {
        return Err(RuntimeError::IncompleteInitialization);
    }
    if fs::read_to_string(data_directory.join("PG_VERSION"))
        .map_err(|_| RuntimeError::Io)?
        .trim()
        != "16"
    {
        return Err(RuntimeError::VersionMismatch);
    }
    write_hba(&data_directory.join("pg_hba.conf"))?;
    if !port_available(MANAGED_PORT) {
        return Err(RuntimeError::PortConflict);
    }

    let logs = state_directory.join("logs");
    create_private_dir(&logs)?;
    let mut command = Command::new(&postgres);
    command
        .arg("-D")
        .arg(&data_directory)
        .arg("-c")
        .arg("listen_addresses=127.0.0.1")
        .arg("-c")
        .arg(format!("port={MANAGED_PORT}"))
        .arg("-c")
        .arg(format!(
            "hba_file={}",
            data_directory.join("pg_hba.conf").display()
        ))
        .arg("-c")
        .arg("logging_collector=on")
        .arg("-c")
        .arg(format!("log_directory={}", logs.display()))
        .arg("-c")
        .arg("log_filename=postgres-%Y-%m-%d_%H%M%S.log")
        .arg("-c")
        .arg("log_rotation_size=10MB")
        .arg("-c")
        .arg("log_rotation_age=1d")
        .arg("-c")
        .arg("log_truncate_on_rotation=on")
        .arg("-c")
        .arg("log_file_mode=0600")
        .current_dir(&bin)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(target_os = "linux")]
    command.env(
        "LD_LIBRARY_PATH",
        format!("{}:{}", lib.display(), lib.join("postgresql").display()),
    );
    #[cfg(target_os = "windows")]
    use std::os::windows::process::CommandExt;
    #[cfg(target_os = "windows")]
    command.creation_flags(0x08000000 | 0x00000200);
    let mut child = command.spawn().map_err(|_| RuntimeError::StartFailed)?;
    let deadline = Instant::now() + Duration::from_secs(35);
    let ready_args = [
        "-h",
        "127.0.0.1",
        "-p",
        "55432",
        "-U",
        "raventech_runtime",
        "-d",
        "postgres",
        "-t",
        "1",
    ];
    loop {
        if child
            .try_wait()
            .map_err(|_| RuntimeError::StartFailed)?
            .is_some()
        {
            return Err(RuntimeError::StartFailed);
        }
        if Command::new(&is_ready)
            .args(ready_args)
            .current_dir(&bin)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|status| status.success())
        {
            break;
        }
        if Instant::now() >= deadline {
            let _ = stop(&mut child, &pg_ctl, &data_directory);
            return Err(RuntimeError::ReadinessTimeout);
        }
        thread::sleep(Duration::from_millis(300));
    }

    if bootstrap_database {
        let sql = format!("CREATE ROLE {DATABASE_USER} LOGIN PASSWORD '{password}';\nCREATE DATABASE {DATABASE_NAME} OWNER {DATABASE_USER};\nALTER ROLE {BOOTSTRAP_USER} NOLOGIN;\n");
        let mut psql_child = Command::new(&psql)
            .args([
                "--no-psqlrc",
                "--set=ON_ERROR_STOP=1",
                "--host=127.0.0.1",
                "--port=55432",
                "--username=raventech_runtime",
                "--dbname=postgres",
                "--no-password",
            ])
            .env("PGPASSWORD", &password)
            .current_dir(&bin)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| {
                let _ = stop(&mut child, &pg_ctl, &data_directory);
                RuntimeError::DatabaseBootstrapFailed
            })?;
        if let Some(mut stdin) = psql_child.stdin.take() {
            if stdin.write_all(sql.as_bytes()).is_err() {
                let _ = psql_child.wait();
                let _ = stop(&mut child, &pg_ctl, &data_directory);
                return Err(RuntimeError::DatabaseBootstrapFailed);
            }
        }
        if !psql_child.wait().is_ok_and(|status| status.success()) {
            let _ = stop(&mut child, &pg_ctl, &data_directory);
            return Err(RuntimeError::DatabaseBootstrapFailed);
        }
        let mut completed = marker.clone();
        completed.initialized = true;
        write_json_atomic(&marker_path, &completed)?;
    }
    let database_url = format!(
        "postgresql+asyncpg://{DATABASE_USER}:{password}@127.0.0.1:{MANAGED_PORT}/{DATABASE_NAME}"
    );
    Ok(ManagedProcess {
        child,
        pg_ctl,
        database_url,
        data_directory,
        version,
        port: MANAGED_PORT,
    })
}

pub fn stop(child: &mut Child, pg_ctl: &Path, data_directory: &Path) -> bool {
    if child.try_wait().ok().flatten().is_some() {
        return true;
    }
    let _ = Command::new(pg_ctl)
        .arg("-D")
        .arg(data_directory)
        .args(["-m", "fast", "-w", "-t", "20", "stop"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    let until = Instant::now() + Duration::from_secs(20);
    while Instant::now() < until {
        if child.try_wait().ok().flatten().is_some() {
            return true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    false
}

fn validate_marker(marker: &OwnershipMarker) -> Result<(), RuntimeError> {
    if marker.application_id != APP_ID
        || marker.runtime_format != 1
        || marker.postgres_major != POSTGRES_MAJOR
        || marker.port != MANAGED_PORT
        || marker.installation_id.len() != 32
        || !marker
            .installation_id
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit())
    {
        return Err(RuntimeError::OwnershipMismatch);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum InitFailureClass {
    PermissionDenied,
    MissingResource,
    ServerExecutableMissing,
    ServerExecutableVersionMismatch,
    LocaleConfiguration,
    InvalidPath,
    StorageUnavailable,
    ProcessLaunch,
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum InitResourceHint {
    BootstrapCatalog,
    ConfigurationSample,
    HbaSample,
    IdentSample,
    PostgresExecutable,
    RuntimeLibrary,
    TimezoneData,
    LocaleData,
    PasswordFile,
}

impl InitResourceHint {
    pub fn label(self) -> &'static str {
        match self {
            Self::BootstrapCatalog => "PostgreSQL bootstrap catalog (postgres.bki)",
            Self::ConfigurationSample => "PostgreSQL configuration template",
            Self::HbaSample => "PostgreSQL authentication template",
            Self::IdentSample => "PostgreSQL identity template",
            Self::PostgresExecutable => "PostgreSQL server executable",
            Self::RuntimeLibrary => "PostgreSQL runtime library",
            Self::TimezoneData => "PostgreSQL timezone data",
            Self::LocaleData => "PostgreSQL locale data",
            Self::PasswordFile => "temporary initialization credential file",
        }
    }
}

fn missing_resource_hint(stdout: &[u8], stderr: &[u8]) -> Option<InitResourceHint> {
    let mut diagnostic = String::from_utf8_lossy(stdout).to_ascii_lowercase();
    diagnostic.push_str(&String::from_utf8_lossy(stderr).to_ascii_lowercase());
    [
        ("postgres.bki", InitResourceHint::BootstrapCatalog),
        (
            "postgresql.conf.sample",
            InitResourceHint::ConfigurationSample,
        ),
        ("pg_hba.conf.sample", InitResourceHint::HbaSample),
        ("pg_ident.conf.sample", InitResourceHint::IdentSample),
        ("postgres.exe", InitResourceHint::PostgresExecutable),
        ("initdb-password.tmp", InitResourceHint::PasswordFile),
        ("timezone", InitResourceHint::TimezoneData),
        ("locale", InitResourceHint::LocaleData),
        (".dll", InitResourceHint::RuntimeLibrary),
    ]
    .iter()
    .find_map(|(marker, hint)| diagnostic.contains(marker).then_some(*hint))
}

fn classify_init_output(stdout: &[u8], stderr: &[u8]) -> InitFailureClass {
    let mut diagnostic = String::from_utf8_lossy(stdout).to_ascii_lowercase();
    diagnostic.push_str(&String::from_utf8_lossy(stderr).to_ascii_lowercase());
    if ["permission denied", "access is denied", "not permitted"]
        .iter()
        .any(|marker| diagnostic.contains(marker))
    {
        InitFailureClass::PermissionDenied
    } else if diagnostic.contains("was not found in the same directory") {
        InitFailureClass::ServerExecutableMissing
    } else if diagnostic.contains("was not the same version") {
        InitFailureClass::ServerExecutableVersionMismatch
    } else if ["locale", "encoding", "collation"]
        .iter()
        .any(|marker| diagnostic.contains(marker))
    {
        InitFailureClass::LocaleConfiguration
    } else if ["no space left", "disk full", "input/output error"]
        .iter()
        .any(|marker| diagnostic.contains(marker))
    {
        InitFailureClass::StorageUnavailable
    } else if ["path too long", "file name too long", "invalid path"]
        .iter()
        .any(|marker| diagnostic.contains(marker))
    {
        InitFailureClass::InvalidPath
    } else if [
        "could not find",
        "could not load",
        "cannot find",
        "not found",
        "failed to load",
    ]
    .iter()
    .any(|marker| diagnostic.contains(marker))
    {
        InitFailureClass::MissingResource
    } else {
        InitFailureClass::Unknown
    }
}

fn classify_io_error(error: &std::io::Error) -> InitFailureClass {
    match error.kind() {
        std::io::ErrorKind::PermissionDenied => InitFailureClass::PermissionDenied,
        std::io::ErrorKind::NotFound => InitFailureClass::MissingResource,
        std::io::ErrorKind::InvalidInput => InitFailureClass::InvalidPath,
        _ => InitFailureClass::ProcessLaunch,
    }
}

fn is_empty_directory(path: &Path) -> Result<bool, RuntimeError> {
    let mut entries = fs::read_dir(path).map_err(|_| RuntimeError::IncompleteInitialization)?;
    match entries.next() {
        None => Ok(true),
        Some(Ok(_)) => Ok(false),
        Some(Err(_)) => Err(RuntimeError::Io),
    }
}

fn can_retry_empty_initialization(
    marker: &OwnershipMarker,
    data_directory: &Path,
) -> Result<bool, RuntimeError> {
    if marker.initialized {
        return Ok(false);
    }
    is_empty_directory(data_directory)
}

fn executable(bin: &Path, name: &str) -> PathBuf {
    #[cfg(target_os = "windows")]
    let name = format!("{name}.exe");
    #[cfg(not(target_os = "windows"))]
    let name = name.to_owned();
    bin.join(name)
}

#[cfg(windows)]
fn postgres_compatible_resource_root(path: &Path) -> Result<PathBuf, RuntimeError> {
    use std::ffi::OsString;
    use std::os::windows::ffi::{OsStrExt, OsStringExt};

    let wide: Vec<u16> = path.as_os_str().encode_wide().collect();
    const VERBATIM_PREFIX: [u16; 4] = [b'\\' as u16, b'\\' as u16, b'?' as u16, b'\\' as u16];
    if !wide.starts_with(&VERBATIM_PREFIX) {
        return Ok(path.to_path_buf());
    }

    let remainder = &wide[VERBATIM_PREFIX.len()..];
    let unc_prefix = [b'U', b'N', b'C', b'\\'];
    let is_unc = remainder.len() >= unc_prefix.len()
        && remainder[..unc_prefix.len()]
            .iter()
            .zip(unc_prefix)
            .all(|(actual, expected)| {
                let upper = if (b'a' as u16..=b'z' as u16).contains(actual) {
                    actual - 32
                } else {
                    *actual
                };
                upper == expected as u16
            });
    let legacy = if is_unc {
        let mut unc = vec![b'\\' as u16, b'\\' as u16];
        unc.extend_from_slice(&remainder[4..]);
        unc
    } else if remainder.len() >= 3
        && matches!(remainder[0], 65..=90 | 97..=122)
        && remainder[1] == b':' as u16
        && remainder[2] == b'\\' as u16
    {
        remainder.to_vec()
    } else {
        return Err(RuntimeError::UnsafePath);
    };

    let normalized = PathBuf::from(OsString::from_wide(&legacy));
    if !normalized.is_absolute() {
        return Err(RuntimeError::UnsafePath);
    }
    Ok(normalized)
}

#[cfg(not(windows))]
fn postgres_compatible_resource_root(path: &Path) -> Result<PathBuf, RuntimeError> {
    Ok(path.to_path_buf())
}

fn output(path: &Path, argument: &str) -> Result<String, RuntimeError> {
    let output = Command::new(path)
        .arg(argument)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .map_err(|_| RuntimeError::ArtifactsMissing)?;
    if !output.status.success() {
        return Err(RuntimeError::ArtifactsMissing);
    }
    String::from_utf8(output.stdout)
        .map(|value| value.trim().to_owned())
        .map_err(|_| RuntimeError::ArtifactsMissing)
}

fn port_available(port: u16) -> bool {
    TcpListener::bind(("127.0.0.1", port)).is_ok()
}

fn create_private_dir(path: &Path) -> Result<(), RuntimeError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            return Err(RuntimeError::UnsafePath)
        }
        Ok(_) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            fs::create_dir_all(path).map_err(|_| RuntimeError::Io)?;
        }
        Err(_) => return Err(RuntimeError::Io),
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))
            .map_err(|_| RuntimeError::Io)?;
    }
    Ok(())
}

fn write_private_file(path: &Path, bytes: &[u8]) -> Result<(), RuntimeError> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path).map_err(|_| RuntimeError::Io)?;
    file.write_all(bytes).map_err(|_| RuntimeError::Io)?;
    file.sync_all().map_err(|_| RuntimeError::Io)
}

fn write_new_secret(path: &Path) -> Result<(), RuntimeError> {
    let value = random_hex(32)?;
    write_private_file(path, value.as_bytes())
}

fn write_json_atomic(path: &Path, value: &impl Serialize) -> Result<(), RuntimeError> {
    let tmp = path.with_extension("json.tmp");
    let bytes = serde_json::to_vec(value).map_err(|_| RuntimeError::Io)?;
    let _ = fs::remove_file(&tmp);
    write_private_file(&tmp, &bytes)?;
    replace_file(&tmp, path)
}

#[cfg(not(target_os = "windows"))]
fn replace_file(source: &Path, destination: &Path) -> Result<(), RuntimeError> {
    fs::rename(source, destination).map_err(|_| RuntimeError::Io)
}
#[cfg(target_os = "windows")]
fn replace_file(source: &Path, destination: &Path) -> Result<(), RuntimeError> {
    use std::os::windows::ffi::OsStrExt;
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn MoveFileExW(existing: *const u16, new: *const u16, flags: u32) -> i32;
    }
    let src: Vec<u16> = source
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let dst: Vec<u16> = destination
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    if unsafe { MoveFileExW(src.as_ptr(), dst.as_ptr(), 0x1 | 0x8) } != 0 {
        Ok(())
    } else {
        Err(RuntimeError::Io)
    }
}

fn write_hba(path: &Path) -> Result<(), RuntimeError> {
    reject_symlink(path)?;
    let mut options = OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path).map_err(|_| RuntimeError::Io)?;
    file.write_all(HBA_POLICY).map_err(|_| RuntimeError::Io)?;
    file.sync_all().map_err(|_| RuntimeError::Io)
}

fn reject_symlink(path: &Path) -> Result<(), RuntimeError> {
    let metadata = fs::symlink_metadata(path).map_err(|_| RuntimeError::Io)?;
    if metadata.file_type().is_symlink() {
        return Err(RuntimeError::UnsafePath);
    }
    Ok(())
}

fn random_hex(bytes: usize) -> Result<String, RuntimeError> {
    let mut data = vec![0_u8; bytes];
    #[cfg(unix)]
    {
        File::open("/dev/urandom")
            .and_then(|mut file| file.read_exact(&mut data))
            .map_err(|_| RuntimeError::Io)?;
    }
    #[cfg(windows)]
    {
        if unsafe { SystemFunction036(data.as_mut_ptr(), bytes as u32) } == 0 {
            return Err(RuntimeError::Io);
        }
    }
    #[cfg(not(any(unix, windows)))]
    {
        return Err(RuntimeError::UnsupportedPlatform);
    }
    Ok(data.iter().map(|byte| format!("{byte:02x}")).collect())
}

#[cfg(target_os = "linux")]
unsafe extern "C" {
    fn geteuid() -> u32;
}
#[cfg(target_os = "windows")]
#[link(name = "advapi32")]
unsafe extern "system" {
    fn SystemFunction036(buffer: *mut u8, length: u32) -> u8;
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_wrong_owner_or_major_without_touching_cluster() {
        let marker = OwnershipMarker {
            application_id: "other".into(),
            runtime_format: 1,
            postgres_major: 16,
            created_at_unix: 1,
            installation_id: "a".repeat(32),
            port: MANAGED_PORT,
            initialized: true,
        };
        assert!(matches!(
            validate_marker(&marker),
            Err(RuntimeError::OwnershipMismatch)
        ));
        let marker = OwnershipMarker {
            application_id: APP_ID.into(),
            postgres_major: 17,
            ..marker
        };
        assert!(matches!(
            validate_marker(&marker),
            Err(RuntimeError::OwnershipMismatch)
        ));
    }

    #[test]
    fn generated_values_are_hex_and_not_fixed() {
        let first = random_hex(32).expect("system RNG");
        let second = random_hex(32).expect("system RNG");
        assert_eq!(first.len(), 64);
        assert!(first.bytes().all(|byte| byte.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[cfg(windows)]
    #[test]
    fn postgres_resource_root_normalizes_windows_verbatim_paths() {
        assert_eq!(
            postgres_compatible_resource_root(Path::new(
                r"\\?\C:\Users\A Long User\RavenTech OSINT\resources\native-runtime"
            ))
            .expect("local verbatim path"),
            PathBuf::from(r"C:\Users\A Long User\RavenTech OSINT\resources\native-runtime")
        );
        assert_eq!(
            postgres_compatible_resource_root(Path::new(
                r"\\?\UNC\host\share\RavenTech OSINT\native-runtime"
            ))
            .expect("UNC verbatim path"),
            PathBuf::from(r"\\host\share\RavenTech OSINT\native-runtime")
        );
    }

    #[test]
    fn managed_hba_has_only_loopback_scram_rule() {
        assert_eq!(MANAGED_PORT, 55432);
        let rules = String::from_utf8_lossy(HBA_POLICY);
        assert!(rules.contains("host all all 127.0.0.1/32 scram-sha-256"));
        assert!(!rules.contains("trust"));
        assert!(!rules.contains("0.0.0.0"));
        assert!(!rules.contains("192.168.50.0/24"));
    }

    #[test]
    fn marker_rejects_unknown_or_incompatible_clusters() {
        let marker = OwnershipMarker {
            application_id: APP_ID.into(),
            runtime_format: 1,
            postgres_major: 16,
            created_at_unix: 1,
            installation_id: "a".repeat(32),
            port: MANAGED_PORT,
            initialized: true,
        };
        assert!(validate_marker(&marker).is_ok());
        let invalid = OwnershipMarker {
            port: 5432,
            ..marker
        };
        assert!(matches!(
            validate_marker(&invalid),
            Err(RuntimeError::OwnershipMismatch)
        ));
    }

    #[test]
    fn only_empty_uninitialized_owned_cluster_can_retry_initdb() {
        let root = std::env::temp_dir().join(format!(
            "raventech-phase5bn-init-retry-{}-{}",
            std::process::id(),
            random_hex(8).expect("random test suffix")
        ));
        fs::create_dir_all(&root).expect("isolated test directory");
        let marker = OwnershipMarker {
            application_id: APP_ID.into(),
            runtime_format: 1,
            postgres_major: POSTGRES_MAJOR,
            created_at_unix: 1,
            installation_id: "a".repeat(32),
            port: MANAGED_PORT,
            initialized: false,
        };
        assert!(can_retry_empty_initialization(&marker, &root).expect("empty directory"));

        fs::write(root.join("unknown.file"), b"preserve").expect("unknown test file");
        assert!(!can_retry_empty_initialization(&marker, &root).expect("nonempty directory"));
        let initialized = OwnershipMarker {
            initialized: true,
            ..marker
        };
        assert!(!can_retry_empty_initialization(&initialized, &root).expect("healthy marker"));
        let canonical_root = root.canonicalize().expect("canonical isolated test path");
        let canonical_temp = std::env::temp_dir()
            .canonicalize()
            .expect("canonical temp root");
        assert!(canonical_root.starts_with(canonical_temp));
        assert!(!fs::symlink_metadata(&root)
            .expect("isolated path metadata")
            .file_type()
            .is_symlink());
        fs::remove_dir_all(canonical_root).expect("remove only isolated test data");
    }

    #[test]
    fn initdb_diagnostics_reduce_to_sanitized_failure_classes() {
        assert_eq!(
            classify_init_output(b"", b"initdb: error: Access is denied"),
            InitFailureClass::PermissionDenied
        );
        assert_eq!(
            classify_init_output(b"", b"could not load required file"),
            InitFailureClass::MissingResource
        );
        assert_eq!(
            classify_init_output(
                b"",
                br#"program "postgres" is needed by "C:\private\initdb.exe" but was not found in the same directory as "C:\private\initdb.exe""#
            ),
            InitFailureClass::ServerExecutableMissing
        );
        assert_eq!(
            classify_init_output(
                b"",
                br#"program "postgres" was found by "C:\private\initdb.exe" but was not the same version as initdb"#
            ),
            InitFailureClass::ServerExecutableVersionMismatch
        );
        assert_eq!(
            classify_init_output(b"", b"invalid locale configuration"),
            InitFailureClass::LocaleConfiguration
        );
        assert_eq!(
            missing_resource_hint(
                b"",
                br#"initdb: could not open file "C:\private\path\postgres.bki": The system cannot find the file specified"#
            ),
            Some(InitResourceHint::BootstrapCatalog)
        );
        assert_eq!(
            missing_resource_hint(b"could not find an unrelated resource", b""),
            None
        );
    }

    #[test]
    #[ignore = "starts a real isolated PostgreSQL process; run explicitly during platform acceptance"]
    fn live_managed_postgres_bootstrap_restart_and_persistence() {
        let resource_root = std::env::var_os("RAVENTECH_TEST_POSTGRES_RESOURCE_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("..")
                    .join("dist-native")
                    .join(format!("{}-x86_64", std::env::consts::OS))
            });
        let temp_root = std::env::temp_dir()
            .join(format!("raventech-phase5bn-pgtest-{}", std::process::id()))
            .join("RavenTech OSINT");
        assert!(
            !temp_root.exists(),
            "refusing to overwrite an existing test path"
        );
        let data_root = temp_root.clone();
        let state_root = temp_root.clone();
        let first =
            start(&resource_root, &data_root, &state_root).expect("first managed cluster startup");
        let first_marker: OwnershipMarker = serde_json::from_slice(
            &fs::read(data_root.join("postgres/ownership.json")).expect("marker"),
        )
        .expect("valid marker");
        assert!(first_marker.initialized);
        assert!(first.version.contains("PostgreSQL) 16."));
        let password = fs::read_to_string(state_root.join("runtime/postgres/database.secret"))
            .expect("app-owned password file");
        let psql = executable(&resource_root.join("postgresql/bin"), "psql");
        let roles = Command::new(&psql)
            .args([
                "--no-psqlrc",
                "--tuples-only",
                "--no-align",
                "--host=127.0.0.1",
                "--port=55432",
                "--username=raventech",
                "--dbname=raventech",
                "--no-password",
                "--command=SELECT (SELECT rolsuper FROM pg_roles WHERE rolname='raventech')::text || '|' || (SELECT rolcanlogin FROM pg_roles WHERE rolname='raventech_runtime')::text",
            ])
            .env("PGPASSWORD", password.trim())
            .output()
            .expect("verify restricted application database role");
        assert!(roles.status.success());
        assert_eq!(String::from_utf8_lossy(&roles.stdout).trim(), "false|false");
        let mut create_probe = Command::new(&psql)
            .args([
                "--no-psqlrc",
                "--set=ON_ERROR_STOP=1",
                "--host=127.0.0.1",
                "--port=55432",
                "--username=raventech",
                "--dbname=raventech",
                "--no-password",
            ])
            .env("PGPASSWORD", password.trim())
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("create persistence test record");
        create_probe.stdin.take().expect("psql input").write_all(b"CREATE TABLE public.phase5bm_persistence_probe (value integer primary key); INSERT INTO public.phase5bm_persistence_probe VALUES (1);\n").expect("write fixed persistence SQL");
        assert!(create_probe
            .wait()
            .expect("finish persistence SQL")
            .success());
        let mut child = first.child;
        assert!(stop(&mut child, &first.pg_ctl, &first.data_directory));

        let second =
            start(&resource_root, &data_root, &state_root).expect("reusing managed cluster");
        let second_marker: OwnershipMarker = serde_json::from_slice(
            &fs::read(data_root.join("postgres/ownership.json")).expect("marker after restart"),
        )
        .expect("valid marker after restart");
        assert_eq!(first_marker.installation_id, second_marker.installation_id);
        assert!(second_marker.initialized);
        let password = fs::read_to_string(state_root.join("runtime/postgres/database.secret"))
            .expect("same app-owned credential");
        let query = Command::new(&psql)
            .args([
                "--no-psqlrc",
                "--tuples-only",
                "--no-align",
                "--host=127.0.0.1",
                "--port=55432",
                "--username=raventech",
                "--dbname=raventech",
                "--no-password",
                "--command=SELECT count(*) FROM public.phase5bm_persistence_probe WHERE value = 1",
            ])
            .env("PGPASSWORD", password.trim())
            .output()
            .expect("query persisted test record");
        assert!(query.status.success());
        assert_eq!(String::from_utf8_lossy(&query.stdout).trim(), "1");
        let mut child = second.child;
        assert!(stop(&mut child, &second.pg_ctl, &second.data_directory));
        assert_eq!(
            fs::read_to_string(data_root.join("postgres/16/PG_VERSION"))
                .expect("persistent cluster version")
                .trim(),
            "16"
        );
        let marker_path = data_root.join("postgres/ownership.json");
        let final_marker: OwnershipMarker =
            serde_json::from_slice(&fs::read(&marker_path).expect("persistent owner marker"))
                .expect("valid final marker");
        assert!(validate_marker(&final_marker).is_ok());
        let canonical_temp = temp_root.canonicalize().expect("canonical test directory");
        assert!(canonical_temp.starts_with(
            std::env::temp_dir()
                .canonicalize()
                .expect("canonical temp root")
        ));
        assert!(!fs::symlink_metadata(&temp_root)
            .expect("test path metadata")
            .file_type()
            .is_symlink());
        fs::remove_dir_all(canonical_temp).expect("remove only validated, stopped test database");
    }
}
