fn main() {
    let icon_path = std::path::PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("icons")
        .join("icon.ico");
    let windows = tauri_build::WindowsAttributes::new().window_icon_path(icon_path);
    let attributes = tauri_build::Attributes::new().windows_attributes(windows);
    tauri_build::try_build(attributes).expect("failed to run Tauri build script");
}
