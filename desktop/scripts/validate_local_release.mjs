import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePostgresqlRuntimeTree } from "./native_runtime_package.mjs";

const VERSION = "5.0.0-rc6";
const PRODUCT = "RavenTech OSINT Desktop";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const PORTABLE_EXE = `${PRODUCT}.exe`;
const INSTALLER_EXE = `RavenTech-OSINT-Desktop-${VERSION}-unsigned-setup.exe`;
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const output = resolve(desktop, "dist-local-release", PRODUCT_DIRECTORY);
const requireArtifact = process.argv.includes("--require-artifact");
const expectedFiles = [
  PORTABLE_EXE,
  INSTALLER_EXE,
  "native-runtime",
  "README.md",
  "LOCAL_STARTUP_INSTRUCTIONS.md",
  "KNOWN_LIMITATIONS.md",
  "SHA256SUMS.txt",
  "local-release-manifest.json",
].sort();
const payloadFiles = expectedFiles.filter((name) => !["SHA256SUMS.txt", "local-release-manifest.json"].includes(name));

const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const tauri = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
const installer = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.installer.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri", "capabilities", "default.json"), "utf8"));
const cargo = await readFile(resolve(desktop, "src-tauri", "Cargo.toml"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri", "src", "main.rs"), "utf8");
const supervisor = await readFile(resolve(desktop, "src-tauri", "src", "runtime_supervisor.rs"), "utf8");
const gitignore = await readFile(resolve(repository, ".gitignore"), "utf8");

if (packageJson.version !== VERSION || tauri.version !== VERSION) throw new Error("Local release must remain RC6.");
if (tauri.productName !== PRODUCT || tauri.app.windows.some((window) => window.title !== `${PRODUCT} — Local Workspace`)) {
  throw new Error("Desktop branding is inconsistent.");
}
if (!tauri.bundle.icon.includes("icons/icon.ico") || installer.bundle.windows.nsis.installerIcon !== "icons/icon.ico") {
  throw new Error("Branded Windows icon metadata is missing.");
}
if (capability.permissions.length !== 0 || capability.remote !== undefined) throw new Error("Desktop permissions are not restricted.");
if (/tauri-plugin-(shell|fs|updater)|shell:|fs:|updater:/i.test(`${cargo}\n${JSON.stringify(capability)}`)) {
  throw new Error("Forbidden shell, filesystem, or updater permission detected.");
}
const approved = ["start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1", "check_platform.ps1", "open_platform.ps1", "apply_lan_monitoring_config.ps1"];
for (const script of approved) if (!rust.includes(script)) throw new Error(`Missing approved launcher: ${script}`);
if ([...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]).join() !== "&powershell") {
  throw new Error("Launcher command boundary changed.");
}
if (!supervisor.includes('"--serve"') || !supervisor.includes('"--run"') || !supervisor.includes("fn validate_artifact") || /taskkill|systemctl|bash\s+-c|sh\s+-c|eval\s*\(|exec\s*\(/i.test(supervisor)) throw new Error("Native supervisor process controls are unsafe.");
if (!gitignore.split(/\r?\n/).includes("desktop/dist-local-release/")) {
  throw new Error("Generated local release package is not Git-ignored.");
}

let entries;
try {
  entries = (await readdir(output)).sort();
} catch (error) {
  if (error?.code === "ENOENT" && !requireArtifact) {
    console.log("Local release source validation passed; no package is present.");
    process.exit(0);
  }
  throw error;
}
if (JSON.stringify(entries) !== JSON.stringify(expectedFiles)) {
  throw new Error(`Local release violates the file allowlist: ${entries.join(", ")}`);
}
const forbiddenName = /(^|\.)(env|pem|key|pfx|p12)$|secret|credential|token|supabase|backup|report|database|\.db$|\.sql$|\.dump$|\.log$/i;
for (const name of entries) {
  if (forbiddenName.test(name)) throw new Error(`Forbidden local release filename: ${name}`);
  if (name !== "native-runtime" && !(await stat(resolve(output, name))).isFile()) throw new Error(`Local release contains an unexpected directory: ${name}`);
}
for (const binary of [PORTABLE_EXE, INSTALLER_EXE]) {
  const bytes = await readFile(resolve(output, binary));
  if (bytes[0] !== 0x4d || bytes[1] !== 0x5a) throw new Error(`${binary} is not a Windows PE file.`);
}

const manifest = JSON.parse(await readFile(resolve(output, "local-release-manifest.json"), "utf8"));
if (manifest.appName !== PRODUCT || manifest.version !== VERSION || manifest.portableArtifact !== PORTABLE_EXE || manifest.installerArtifact !== INSTALLER_EXE) {
  throw new Error("Local release manifest branding or artifact metadata is invalid.");
}
if (!/^\d{4}-\d{2}-\d{2}T/.test(manifest.buildTime) || !/^[0-9a-f]{40}$/.test(manifest.commit)) {
  throw new Error("Local release build time or commit metadata is invalid.");
}
const { embeddedFrontend, bundledBackend, managedPostgresqlRuntime, initializedDatabase, ...disabledBoundaries } = manifest.boundaries;
if (manifest.signed !== false || manifest.localOnly !== true || manifest.dockerRequired !== false || manifest.postgresqlRequired !== true || manifest.externalPostgresqlRequired !== false || manifest.managedPostgresqlRuntimeIncluded !== true || manifest.managedPostgresql?.major !== 16 || embeddedFrontend !== true || bundledBackend !== true || managedPostgresqlRuntime !== true || initializedDatabase !== false || Object.values(disabledBoundaries).some((value) => value !== false)) {
  throw new Error("Local-only release security boundaries are invalid.");
}
if (JSON.stringify(Object.keys(manifest.files).sort()) !== JSON.stringify(payloadFiles)) {
  throw new Error("Local release manifest payload allowlist is invalid.");
}
const expectedChecksums = [];
await validatePostgresqlRuntimeTree(resolve(output, "native-runtime", "postgresql"));
for (const name of payloadFiles) {
  const digest = createHash("sha256");
  if (name === "native-runtime") {
    const walk = async (directory, prefix = "") => {
      for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
        const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
        const path = resolve(directory, entry.name);
        if (/(^|\/)(\.env(?:\..*)?|backups?|uploads?|logs?)(\/|$)|\.(key|pfx|p12|db|sqlite|dump|log)$/i.test(relative)) throw new Error(`Forbidden native runtime resource: ${relative}`);
        if (entry.isDirectory()) await walk(path, relative);
        else if (entry.isFile()) digest.update(`${relative}\0`).update(await readFile(path));
        else throw new Error(`Unsupported native runtime resource: ${relative}`);
      }
    };
    await walk(resolve(output, name));
  } else digest.update(await readFile(resolve(output, name)));
  const value = digest.digest("hex");
  if (manifest.files[name]?.sha256 !== value) throw new Error(`Manifest checksum mismatch: ${name}`);
  expectedChecksums.push(`${value}  ${name}`);
}
const actualChecksums = (await readFile(resolve(output, "SHA256SUMS.txt"), "utf8")).trim().split(/\r?\n/).sort();
if (JSON.stringify(actualChecksums) !== JSON.stringify(expectedChecksums.sort())) throw new Error("SHA256SUMS.txt is invalid.");

const docs = `${await readFile(resolve(output, "README.md"), "utf8")}\n${await readFile(resolve(output, "LOCAL_STARTUP_INSTRUCTIONS.md"), "utf8")}`;
for (const marker of [PRODUCT, VERSION, "managed PostgreSQL 16 runtime", "Docker remains an optional", "no repository binding", "no terminal", "http://localhost:5173", "http://localhost:8000", "SmartScreen", "unsigned", "no code signing"]) {
  if (!docs.includes(marker)) throw new Error(`Local release guidance is missing: ${marker}`);
}
if (/Docker Desktop.*installed|bind the repository root|run manually in PowerShell/i.test(docs)) {
  throw new Error("Local release guidance contains stale native-desktop setup instructions.");
}
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(docs)) throw new Error("Potential secret assignment found in release guidance.");
console.log(`Local release package validation passed: ${output}`);
