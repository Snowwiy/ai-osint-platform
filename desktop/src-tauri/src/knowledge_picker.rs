use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::Serialize;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Component, Path, PathBuf};
use std::time::UNIX_EPOCH;
use tauri_plugin_dialog::DialogExt;

const MAX_FILES: usize = 1_000;
const MAX_FILE_BYTES: u64 = 5 * 1024 * 1024;
const MAX_TOTAL_BYTES: u64 = 50 * 1024 * 1024;
const SUPPORTED: [&str; 8] = ["md", "txt", "pdf", "docx", "html", "htm", "json", "csv"];
const IGNORED_DIRS: [&str; 8] = [
    ".obsidian",
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "tmp",
    "cache",
];

#[derive(Clone, Copy)]
pub enum SelectionMode {
    Vault,
    Documents,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KnowledgeFile {
    pub relative_name: String,
    pub content_base64: String,
    pub modified_ms: u128,
    pub size_bytes: u64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KnowledgeSelection {
    pub root_path: Option<String>,
    pub files: Vec<KnowledgeFile>,
    pub unsupported_count: usize,
    pub oversized_count: usize,
    pub total_bytes: u64,
}

pub fn pick<R: tauri::Runtime>(
    app: &tauri::AppHandle<R>,
    mode: SelectionMode,
) -> Result<Option<KnowledgeSelection>, String> {
    let picked = match mode {
        SelectionMode::Vault => {
            let Some(path) = app
                .dialog()
                .file()
                .set_title("Select an Obsidian vault")
                .blocking_pick_folder()
            else {
                return Ok(None);
            };
            let root = path
                .into_path()
                .map_err(|_| "The selected folder could not be resolved safely.")?;
            return collect_vault(&root).map(Some);
        }
        SelectionMode::Documents => {
            let Some(paths) = app
                .dialog()
                .file()
                .set_title("Select Knowledge documents")
                .add_filter("Supported Knowledge documents", &SUPPORTED)
                .blocking_pick_files()
            else {
                return Ok(None);
            };
            paths
        }
    };
    collect_documents(picked.into_iter().map(|path| {
        path.into_path()
            .map_err(|_| "A selected file could not be resolved safely.".to_owned())
    }).collect::<Result<Vec<_>, _>>()?).map(Some)
}

fn collect_vault(root: &Path) -> Result<KnowledgeSelection, String> {
    if is_link_or_reparse(root) {
        return Err("The selected vault root is a symbolic link or reparse point.".to_owned());
    }
    let canonical_root = root
        .canonicalize()
        .map_err(|_| "The selected vault folder is unavailable.")?;
    if !canonical_root.is_dir() {
        return Err("The selected vault is not a folder.".to_owned());
    }

    let mut paths = Vec::new();
    let mut stack = vec![canonical_root.clone()];
    let mut unsupported_count = 0;
    while let Some(directory) = stack.pop() {
        let entries = fs::read_dir(&directory)
            .map_err(|_| "A selected vault folder could not be read.")?;
        let mut entries = entries
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "A selected vault folder could not be read.")?;
        entries.sort_by_key(|entry| entry.file_name().to_string_lossy().to_lowercase());
        for entry in entries {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            let metadata = fs::symlink_metadata(&path)
                .map_err(|_| "A selected vault entry could not be inspected safely.")?;
            if is_link_metadata(&metadata) {
                continue;
            }
            if metadata.is_dir() {
                if !IGNORED_DIRS.iter().any(|ignored| name.eq_ignore_ascii_case(ignored)) {
                    stack.push(path);
                }
            } else if metadata.is_file() {
                if !supported(&path) {
                    unsupported_count += 1;
                    continue;
                }
                let resolved = path
                    .canonicalize()
                    .map_err(|_| "A selected vault document could not be resolved safely.")?;
                if !resolved.starts_with(&canonical_root) {
                    return Err("A selected document escapes the chosen vault.".to_owned());
                }
                paths.push(resolved);
                if paths.len() > MAX_FILES {
                    return Err("The selected vault exceeds the 1,000-document desktop selection limit.".to_owned());
                }
            }
        }
    }
    paths.sort_by_key(|path| path.to_string_lossy().to_lowercase());
    let mut selection = collect_paths(paths, Some(&canonical_root))?;
    selection.root_path = Some(
        canonical_root
            .to_str()
            .ok_or_else(|| "The selected vault path cannot be represented safely.".to_owned())?
            .to_owned(),
    );
    selection.unsupported_count = unsupported_count;
    Ok(selection)
}

fn collect_documents(paths: Vec<PathBuf>) -> Result<KnowledgeSelection, String> {
    if paths.len() > MAX_FILES {
        return Err("Select no more than 1,000 documents at a time.".to_owned());
    }
    collect_paths(paths, None)
}

fn collect_paths(paths: Vec<PathBuf>, root: Option<&Path>) -> Result<KnowledgeSelection, String> {
    let mut files = Vec::new();
    let mut unsupported_count = 0;
    let mut oversized_count = 0;
    let mut total_bytes = 0_u64;
    let mut names = std::collections::HashSet::new();
    for path in paths {
        if is_link_or_reparse(&path) {
            continue;
        }
        let canonical = path
            .canonicalize()
            .map_err(|_| "A selected document is unavailable.")?;
        if root.is_some_and(|value| !canonical.starts_with(value)) {
            return Err("A selected document escapes the chosen vault.".to_owned());
        }
        if !canonical.is_file() {
            continue;
        }
        if !supported(&canonical) {
            unsupported_count += 1;
            continue;
        }
        let metadata = fs::metadata(&canonical)
            .map_err(|_| "A selected document could not be inspected safely.")?;
        let size = metadata.len();
        if size > MAX_FILE_BYTES {
            oversized_count += 1;
            continue;
        }
        if total_bytes.saturating_add(size) > MAX_TOTAL_BYTES {
            return Err("Selected supported documents exceed the 50 MiB desktop transfer limit.".to_owned());
        }
        let relative_name = if let Some(root) = root {
            canonical
                .strip_prefix(root)
                .map_err(|_| "A selected document escapes the chosen vault.")?
                .components()
                .map(component_text)
                .collect::<Result<Vec<_>, _>>()?
                .join("/")
        } else {
            canonical
                .file_name()
                .and_then(|name| name.to_str())
                .ok_or_else(|| "A selected document has an unsupported filename.".to_owned())?
                .to_owned()
        };
        if relative_name.is_empty()
            || relative_name.len() > 1000
            || !names.insert(relative_name.to_lowercase())
        {
            return Err("Selected documents contain an invalid or duplicate relative filename.".to_owned());
        }
        let mut bytes = Vec::with_capacity(size as usize);
        File::open(&canonical)
            .and_then(|file| file.take(MAX_FILE_BYTES + 1).read_to_end(&mut bytes))
            .map_err(|_| "A selected document could not be read.")?;
        if bytes.len() as u64 > MAX_FILE_BYTES {
            oversized_count += 1;
            continue;
        }
        let modified_ms = metadata
            .modified()
            .ok()
            .and_then(|modified| modified.duration_since(UNIX_EPOCH).ok())
            .map_or(0, |duration| duration.as_millis());
        total_bytes += bytes.len() as u64;
        files.push(KnowledgeFile {
            relative_name,
            content_base64: STANDARD.encode(bytes),
            modified_ms,
            size_bytes: size,
        });
    }
    Ok(KnowledgeSelection {
        root_path: None,
        files,
        unsupported_count,
        oversized_count,
        total_bytes,
    })
}

fn component_text(component: Component<'_>) -> Result<String, String> {
    let value = component.as_os_str().to_str().ok_or_else(|| {
        "A selected vault filename cannot be represented as UTF-8.".to_owned()
    })?;
    if value.is_empty()
        || value == "."
        || value == ".."
        || value.chars().any(|character| matches!(character, '/' | '\\' | ':'))
    {
        return Err("A selected vault filename is invalid.".to_owned());
    }
    Ok(value.to_owned())
}

fn supported(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .is_some_and(|value| SUPPORTED.iter().any(|extension| value.eq_ignore_ascii_case(extension)))
}

fn is_link_or_reparse(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok_and(|metadata| is_link_metadata(&metadata))
}

fn is_link_metadata(metadata: &fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0400;
        return metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0;
    }
    #[cfg(not(windows))]
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_root(name: &str) -> PathBuf {
        let nonce = std::time::SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock after epoch")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("raventech-knowledge-picker-{name}-{}-{nonce}", std::process::id()));
        fs::create_dir_all(&root).expect("temporary directory");
        root
    }

    #[test]
    fn selected_vault_uses_relative_names_and_ignores_unsupported_and_obsidian_settings() {
        let root = temp_root("relative");
        fs::create_dir_all(root.join("Notas Unicode")).expect("nested directory");
        fs::create_dir_all(root.join(".obsidian")).expect("settings directory");
        fs::write(root.join("Notas Unicode").join("\u{00f1}.md"), "# Local").expect("markdown");
        fs::write(root.join("ignored.exe"), b"no execution").expect("unsupported");
        fs::write(root.join(".obsidian").join("config.json"), "{}").expect("settings");
        let selection = collect_vault(&root).expect("safe selection");
        assert_eq!(selection.files.len(), 1);
        assert_eq!(selection.files[0].relative_name, "Notas Unicode/\u{00f1}.md");
        assert_eq!(selection.unsupported_count, 1);
        assert_eq!(STANDARD.decode(&selection.files[0].content_base64).unwrap(), b"# Local");
        fs::remove_dir_all(root).expect("test cleanup");
    }

    #[test]
    fn selected_files_respect_per_file_and_total_limits() {
        let root = temp_root("limits");
        let oversized = root.join("large.md");
        fs::write(&oversized, vec![b'x'; (MAX_FILE_BYTES + 1) as usize]).expect("large file");
        let selection = collect_documents(vec![oversized]).expect("oversized file is skipped");
        assert_eq!(selection.files.len(), 0);
        assert_eq!(selection.oversized_count, 1);
        fs::remove_dir_all(root).expect("test cleanup");
    }
}
