import { access, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const required = [
  "package.json",
  "ui/index.html",
  "ui/app.css",
  "ui/app.js",
  "tests/runtime.test.mjs",
  "tests/portable-scripts.test.mjs",
  "tests/installer-scripts.test.mjs",
  "tests/smoke-script.test.mjs",
  "tests/local-release.test.mjs",
  "tests/launcher.test.mjs",
  "tests/local-scripts.test.mjs",
  "tests/first-run.test.mjs",
  "tests/handoff-docs.test.mjs",
  "scripts/build_portable.mjs",
  "scripts/package_portable.mjs",
  "scripts/validate_portable.mjs",
  "scripts/build_installer.mjs",
  "scripts/validate_installer.mjs",
  "scripts/smoke_desktop.mjs",
  "scripts/package_local_release.mjs",
  "scripts/validate_local_release.mjs",
  "PORTABLE_BUILD_README.md",
  "INSTALLER_BUILD_README.md",
  "LOCAL_RELEASE_README.md",
  "LOCAL_STARTUP_INSTRUCTIONS.md",
  "src-tauri/Cargo.toml",
  "src-tauri/tauri.conf.json",
  "src-tauri/tauri.installer.conf.json",
  "src-tauri/capabilities/default.json",
  "src-tauri/src/main.rs",
  "assets/raventech-osint-icon.svg",
  "src-tauri/icons/icon.ico",
  "src-tauri/icons/icon.png",
];
for (const path of required) await access(resolve(desktop, path));

const config = JSON.parse(await readFile(resolve(desktop, "src-tauri/tauri.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri/capabilities/default.json"), "utf8"));
const cargo = await readFile(resolve(desktop, "src-tauri/Cargo.toml"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri/src/main.rs"), "utf8");
const html = await readFile(resolve(desktop, "ui/index.html"), "utf8");
const app = await readFile(resolve(desktop, "ui/app.js"), "utf8");

if (config.version !== "5.0.0-rc6") throw new Error("Desktop version must match RC6.");
if (config.productName !== "RavenTech OSINT Desktop") throw new Error("Unexpected desktop product name.");
if (config.app.windows.some((window) => window.title !== "RavenTech OSINT Desktop — Local Workspace")) {
  throw new Error("Unexpected desktop local-workspace window title.");
}
if (config.build.frontendDist !== "../ui") throw new Error("Desktop UI must remain isolated.");
if (config.bundle.active !== false) throw new Error("Installer bundling must remain disabled.");
if (config.app.windows.some((window) => window.devtools !== false)) {
  throw new Error("Desktop runtime devtools must remain disabled.");
}
if (capability.permissions.length !== 0) throw new Error("Prototype capability must grant no plugin permissions.");
if (capability.remote !== undefined) throw new Error("Remote capability origins are not allowed.");
if (config.app.security.dangerousRemoteDomainIpcAccess !== undefined) {
  throw new Error("Dangerous remote-domain IPC access must not be configured.");
}
if (/tauri-plugin-(shell|fs)|shell:|fs:/i.test(`${cargo}\n${JSON.stringify(capability)}`)) {
  throw new Error("Shell or filesystem capability detected.");
}
if (!rust.includes("127.0.0.1")) {
  throw new Error("Health bridge must remain loopback-only.");
}
for (const marker of ["validate_repository_root", "PROJECT_PATH_FILE", "frontend/package.json", "backend/app", "REQUIRED_SCRIPTS", "trusted_script_bytes", "include_bytes!"]) {
  if (!rust.includes(marker)) throw new Error(`Missing safe project binding marker: ${marker}`);
}
if (!app.includes('invoke("bind_project_path", { projectPath: input.value })') || /showOpenDialog|readDir|readTextFile/.test(app)) {
  throw new Error("Project binding must use manual input and fixed Rust validation without broad browsing.");
}
const commandPrograms = [...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]);
if (JSON.stringify(commandPrograms) !== JSON.stringify(["&powershell"]) || !rust.includes('join("System32")') || !rust.includes('var_os("SystemRoot")')) {
  throw new Error("Only the fixed Windows PowerShell launcher is allowed.");
}
for (const script of ["start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1", "check_platform.ps1", "open_platform.ps1"]) {
  if (!rust.includes(script)) throw new Error(`Missing approved launcher script: ${script}`);
}
if (!html.includes('lang="en"') || !html.includes("Español")) {
  throw new Error("Desktop help screen must retain English/Spanish controls.");
}
if (/allow-popups|allow-top-navigation/.test(html)) {
  throw new Error("Embedded frontend navigation is too broad.");
}
if (!config.app.security.csp.includes("frame-src http://localhost:5173")) {
  throw new Error("CSP must constrain the embedded frontend to localhost:5173.");
}
if (!app.includes("http://localhost:5173") || !app.includes("http://localhost:8000")) {
  throw new Error("Desktop shell must use the documented local URL defaults.");
}
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]/i.test(`${app}\n${html}`)) {
  throw new Error("Potential secret field detected in desktop UI source.");
}

for (const doc of [
  "DESKTOP_TAURI_PROTOTYPE.md",
  "DESKTOP_APP_STRATEGY.md",
  "DESKTOP_PACKAGING_TODO.md",
  "README.md",
  "KNOWN_LIMITATIONS.md",
  "FINAL_QA_CHECKLIST.md",
  "DESKTOP_DISTRIBUTION_CHECKLIST.md",
  "DESKTOP_LOCAL_DISTRIBUTION.md",
  "OPERATOR_MANUAL.md",
  "DESKTOP_PRIVATE_HANDOFF.md",
  "DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md",
  "FRESH_SETUP_CHECKLIST.md",
]) await access(resolve(repository, doc));

console.log("Desktop prototype safety checks passed.");
