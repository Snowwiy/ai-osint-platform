import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc5";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const PORTABLE_EXE = "RavenTech OSINT Desktop.exe";
const INSTALLER_EXE = `RavenTech-OSINT-Desktop-${VERSION}-unsigned-setup.exe`;
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const requireArtifacts = process.argv.includes("--require-artifacts");

const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const config = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
const installerConfig = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.installer.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri", "capabilities", "default.json"), "utf8"));
const cargo = await readFile(resolve(desktop, "src-tauri", "Cargo.toml"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri", "src", "main.rs"), "utf8");
const app = await readFile(resolve(desktop, "ui", "app.js"), "utf8");
const gitignore = await readFile(resolve(repository, ".gitignore"), "utf8");

if (packageJson.version !== VERSION || config.version !== VERSION) throw new Error("Desktop version must remain 5.0.0-rc5.");
if (config.productName !== "RavenTech OSINT Desktop" || config.identifier !== "com.raventech.osint") {
  throw new Error("Desktop product metadata changed unexpectedly.");
}
if (config.app.windows.some((window) => window.title !== "RavenTech OSINT Desktop — Local Workspace")) {
  throw new Error("Desktop window branding does not match the local distribution contract.");
}
if (config.bundle.active !== false) throw new Error("Default/portable installer bundling must remain disabled.");
if (installerConfig.bundle.createUpdaterArtifacts !== false) throw new Error("Updater artifacts must remain disabled.");
if (installerConfig.bundle.resources.length !== 0 || installerConfig.bundle.externalBin.length !== 0) {
  throw new Error("Installer resources and sidecar binaries must remain empty.");
}
if (installerConfig.bundle.windows?.nsis?.installMode !== "currentUser") throw new Error("Installer must remain current-user only.");
if (!installerConfig.bundle.windows.nsis.languages.includes("English") || !installerConfig.bundle.windows.nsis.languages.includes("Spanish")) {
  throw new Error("English and Spanish installer language labels are required.");
}
if (capability.permissions.length !== 0 || capability.remote !== undefined) throw new Error("Desktop permissions must remain empty and local-only.");
if (/tauri-plugin-(shell|fs|updater)|shell:|fs:|updater:/i.test(`${cargo}\n${JSON.stringify(capability)}`)) {
  throw new Error("Shell, filesystem, or updater permission detected.");
}
const commandPrograms = [...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]);
if (JSON.stringify(commandPrograms) !== JSON.stringify(["&powershell"]) || !rust.includes('join("System32")')) {
  throw new Error("Desktop launcher is not constrained to fixed Windows PowerShell execution.");
}
for (const marker of ["validate_repository_root", "PROJECT_PATH_FILE", "REQUIRED_SCRIPTS", "trusted_script_bytes", "include_bytes!"]) {
  if (!rust.includes(marker)) throw new Error(`Missing safe project-path validation marker: ${marker}`);
}
if (!app.includes('invoke("bind_project_path", { projectPath: input.value })') || /showOpenDialog|readDir|readTextFile/.test(app)) {
  throw new Error("First-run project binding must remain manual and narrowly validated.");
}
for (const url of app.match(/https?:\/\/[^"'`\s]+/g) ?? []) {
  if (!url.startsWith("http://localhost:5173") && !url.startsWith("http://localhost:8000")) {
    throw new Error(`Non-local desktop URL detected: ${url}`);
  }
}
for (const required of ["http://localhost:5173", "http://localhost:8000"]) {
  if (!app.includes(required)) throw new Error(`Missing local URL: ${required}`);
}
for (const [artifact, acceptedRules] of [
  ["desktop/dist-portable/", ["desktop/dist-portable/"]],
  ["desktop/dist-installer/", ["desktop/dist-installer/"]],
  ["desktop/src-tauri/target/", ["desktop/src-tauri/target/", "target/"]],
]) {
  if (!acceptedRules.some((rule) => gitignore.split(/\r?\n/).includes(rule))) {
    throw new Error(`Generated desktop artifact is not ignored: ${artifact}`);
  }
}

const forbiddenName = /(^|\.)(env|pem|key|pfx|p12)$|secret|credential|token|supabase|backup|report|database|\.db$|\.sql$|\.dump$|\.log$/i;
async function verifyArtifact({ directory, allowed, manifestName, binaryName, kind }) {
  let entries;
  try {
    entries = (await readdir(directory)).sort();
  } catch (error) {
    if (error?.code === "ENOENT" && !requireArtifacts) {
      console.log(`${kind} artifact not present; source contract remains valid.`);
      return;
    }
    throw error;
  }
  if (JSON.stringify(entries) !== JSON.stringify([...allowed].sort())) {
    throw new Error(`${kind} artifact violates the file allowlist: ${entries.join(", ")}`);
  }
  for (const name of entries) {
    if (forbiddenName.test(name)) throw new Error(`Forbidden ${kind} artifact filename: ${name}`);
    if (!(await stat(resolve(directory, name))).isFile()) throw new Error(`${kind} artifact contains a directory: ${name}`);
  }
  const binary = await readFile(resolve(directory, binaryName));
  if (binary[0] !== 0x4d || binary[1] !== 0x5a) throw new Error(`${kind} binary is not a Windows PE file.`);
  const manifest = JSON.parse(await readFile(resolve(directory, manifestName), "utf8"));
  const { controlledLocalLauncher, safeProjectPathBinding, ...forbiddenBoundaries } = manifest.boundaries;
  if (manifest.version !== VERSION || controlledLocalLauncher !== true || safeProjectPathBinding !== true || Object.values(forbiddenBoundaries).some((value) => value !== false)) {
    throw new Error(`${kind} manifest version or security boundaries are invalid.`);
  }
  if (kind === "installer" && (manifest.signed !== false || manifest.publicRelease !== false)) {
    throw new Error("Installer manifest must remain unsigned and private.");
  }
  const expectedPayload = allowed.filter((name) => name !== manifestName).sort();
  if (JSON.stringify(Object.keys(manifest.files).sort()) !== JSON.stringify(expectedPayload)) {
    throw new Error(`${kind} manifest file map violates the payload allowlist.`);
  }
  for (const [name, metadata] of Object.entries(manifest.files)) {
    const digest = createHash("sha256").update(await readFile(resolve(directory, name))).digest("hex");
    if (metadata.sha256 !== digest) throw new Error(`${kind} checksum mismatch: ${name}`);
  }
}

await verifyArtifact({
  directory: resolve(desktop, "dist-portable", PRODUCT_DIRECTORY),
  allowed: [PORTABLE_EXE, "LICENSE", "README.md", "portable-manifest.json"],
  manifestName: "portable-manifest.json",
  binaryName: PORTABLE_EXE,
  kind: "portable",
});
await verifyArtifact({
  directory: resolve(desktop, "dist-installer", PRODUCT_DIRECTORY),
  allowed: [INSTALLER_EXE, "LICENSE", "README.md", "installer-manifest.json"],
  manifestName: "installer-manifest.json",
  binaryName: INSTALLER_EXE,
  kind: "installer",
});

console.log("Desktop local-distribution smoke checks passed.");
