fn main() {
    // tauri-build requires a Windows resource icon even when bundling is disabled.
    // Generate a tiny build-only placeholder; final branded assets are explicitly
    // deferred to the packaging phase.
    let icon_path = std::path::PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("target")
        .join("prototype.ico");
    let icon: [u8; 70] = [
        0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 32, 0, 48, 0, 0, 0, 22, 0, 0, 0, 40, 0, 0,
        0, 1, 0, 0, 0, 2, 0, 0, 0, 1, 0, 32, 0, 0, 0, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 196, 230, 101, 255, 0, 0, 0, 0,
    ];
    std::fs::create_dir_all(icon_path.parent().unwrap())
        .expect("failed to create build output directory");
    std::fs::write(&icon_path, icon).expect("failed to create build-only icon");
    let windows = tauri_build::WindowsAttributes::new().window_icon_path(icon_path);
    let attributes = tauri_build::Attributes::new().windows_attributes(windows);
    tauri_build::try_build(attributes).expect("failed to run Tauri build script");
}
