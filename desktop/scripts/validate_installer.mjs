import { createHash } from "node:crypto";
import { access, readFile, readdir, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc6";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const INSTALLER_NAME = `RavenTech-OSINT-Desktop-${VERSION}-unsigned-setup.exe`;
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const output = resolve(desktop, "dist-installer", PRODUCT_DIRECTORY);
const requireArtifact = process.argv.includes("--require-artifact");
const configOnly = process.argv.includes("--config-only");

const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const base = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
const installer = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.installer.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri", "capabilities", "default.json"), "utf8"));
const cargo = await readFile(resolve(desktop, "src-tauri", "Cargo.toml"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri", "src", "main.rs"), "utf8");

if (packageJson.version !== VERSION || base.version !== VERSION) {
  throw new Error("npm and Tauri versions must remain 5.0.0-rc6.");
}
if (packageJson.devDependencies?.["@tauri-apps/cli"] !== "2.11.4") {
  throw new Error("The installer workflow requires the exactly pinned Tauri CLI 2.11.4.");
}
if (base.productName !== "RavenTech OSINT Desktop" || base.identifier !== "com.raventech.osint") {
  throw new Error("Unexpected desktop installer metadata.");
}
if (base.bundle.active !== false) throw new Error("Portable/default Tauri bundling must remain disabled.");
const bundle = installer.bundle;
if (bundle.active !== true || JSON.stringify(bundle.targets) !== JSON.stringify(["nsis"])) {
  throw new Error("Installer override must enable only the NSIS bundle target.");
}
if (bundle.createUpdaterArtifacts !== false) throw new Error("Updater artifacts must remain disabled.");
if (bundle.publisher !== "RavenTech Local Test (Unsigned)") {
  throw new Error("Installer publisher must remain an explicit unsigned local-test placeholder.");
}
if (bundle.resources.length !== 0 || bundle.externalBin.length !== 0) {
  throw new Error("Installer must not bundle resources, services, databases, or sidecar binaries.");
}
const windows = bundle.windows;
if (windows.webviewInstallMode?.type !== "skip") {
  throw new Error("Installer must not download or embed a WebView2 installer.");
}
if (windows.allowDowngrades !== false || windows.nsis?.installMode !== "currentUser") {
  throw new Error("Installer must be current-user only and block downgrades.");
}
if (!windows.nsis.languages.includes("English") || !windows.nsis.languages.includes("Spanish")) {
  throw new Error("Installer language metadata must retain English and Spanish.");
}
for (const forbidden of ["certificateThumbprint", "timestampUrl", "signCommand", "wix", "hooks", "installerHooks", "template"]) {
  if (JSON.stringify(installer).toLowerCase().includes(forbidden.toLowerCase())) {
    throw new Error(`Forbidden installer configuration detected: ${forbidden}`);
  }
}
if (capability.permissions.length !== 0 || capability.remote !== undefined) {
  throw new Error("Tauri capabilities must remain empty and local-only.");
}
if (/tauri-plugin-(shell|fs)|shell:|fs:/i.test(`${cargo}\n${JSON.stringify(capability)}`)) {
  throw new Error("Shell or broad filesystem permissions are not allowed.");
}
const commandPrograms = [...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]);
if (JSON.stringify(commandPrograms) !== JSON.stringify(["&powershell"]) || !rust.includes('join("System32")')) {
  throw new Error("Desktop runtime must use only its fixed Windows PowerShell launcher.");
}
for (const marker of ["validate_repository_root", "PROJECT_PATH_FILE", "frontend/package.json", "backend/app", "REQUIRED_SCRIPTS", "trusted_script_bytes", "include_bytes!"]) {
  if (!rust.includes(marker)) throw new Error(`Missing safe first-run binding marker: ${marker}`);
}

for (const path of [
  "INSTALLER_BUILD_README.md",
  "PORTABLE_BUILD_README.md",
  "scripts/build_installer.mjs",
  "scripts/validate_installer.mjs",
  "scripts/build_portable.mjs",
  "scripts/validate_portable.mjs",
]) await access(resolve(desktop, path));
for (const path of [
  "DESKTOP_DISTRIBUTION_CHECKLIST.md",
  "DESKTOP_TAURI_PROTOTYPE.md",
  "DESKTOP_PACKAGING_TODO.md",
  "DESKTOP_APP_STRATEGY.md",
  "README.md",
  "KNOWN_LIMITATIONS.md",
  "FINAL_QA_CHECKLIST.md",
]) await access(resolve(repository, path));

if (configOnly) {
  console.log("Unsigned installer configuration validation passed.");
  process.exit(0);
}

let entries;
try {
  entries = (await readdir(output)).sort();
} catch (error) {
  if (error?.code === "ENOENT" && !requireArtifact) {
    console.log("Installer configuration validation passed; no local installer artifact is present.");
    process.exit(0);
  }
  throw error;
}

const allowedFiles = [INSTALLER_NAME, "LICENSE", "README.md", "installer-manifest.json"].sort();
if (JSON.stringify(entries) !== JSON.stringify(allowedFiles)) {
  throw new Error(`Installer output violates the file allowlist: ${entries.join(", ")}`);
}
for (const name of entries) {
  const info = await stat(resolve(output, name));
  if (!info.isFile()) throw new Error(`Installer output contains a non-file entry: ${name}`);
  if (/(^|\.)(env|pem|key|pfx|p12)$|backup|report|database|\.db$|\.sql$|\.dump$|\.log$/i.test(name)) {
    throw new Error(`Forbidden installer filename: ${name}`);
  }
}
const executable = await readFile(resolve(output, INSTALLER_NAME));
if (executable[0] !== 0x4d || executable[1] !== 0x5a) {
  throw new Error("Installer artifact is not a Windows PE file.");
}
const manifest = JSON.parse(await readFile(resolve(output, "installer-manifest.json"), "utf8"));
if (manifest.version !== VERSION || manifest.installer !== INSTALLER_NAME || manifest.signed !== false || manifest.publicRelease !== false) {
  throw new Error("Installer manifest does not describe the expected unsigned RC6 local build.");
}
const { controlledLocalLauncher, safeProjectPathBinding, embeddedFrontend, ...forbiddenBoundaries } = manifest.boundaries;
if (controlledLocalLauncher !== true || safeProjectPathBinding !== true || embeddedFrontend !== true || Object.values(forbiddenBoundaries).some((value) => value !== false)) {
  throw new Error("A forbidden installer capability is enabled in the manifest.");
}
for (const name of [INSTALLER_NAME, "README.md", "LICENSE"]) {
  const digest = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
  if (manifest.files[name]?.sha256 !== digest) throw new Error(`Checksum mismatch: ${name}`);
}
const readme = await readFile(resolve(output, "README.md"), "utf8");
for (const required of ["unsigned", "SmartScreen", "Docker Desktop", "http://localhost:5173", "http://localhost:8000", "never starts services automatically", "repository root"]) {
  if (!readme.includes(required)) throw new Error(`Installer README is missing: ${required}`);
}
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(readme)) {
  throw new Error("Potential secret assignment detected in installer README.");
}
console.log(`Unsigned local installer validation passed: ${output}`);
