import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc6";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const EXECUTABLE = "RavenTech OSINT Desktop.exe";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(desktop, "dist-portable", PRODUCT_DIRECTORY);
const allowedFiles = [EXECUTABLE, "LICENSE", "README.md", "portable-manifest.json"].sort();

const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const tauriConfig = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
if (packageJson.version !== VERSION || tauriConfig.version !== VERSION) {
  throw new Error("Portable, npm, and Tauri versions must remain 5.0.0-rc6.");
}
if (tauriConfig.productName !== "RavenTech OSINT Desktop") {
  throw new Error("Unexpected desktop product metadata.");
}
if (tauriConfig.bundle.active !== false) throw new Error("Installer bundling must remain disabled.");

const entries = (await readdir(output)).sort();
if (JSON.stringify(entries) !== JSON.stringify(allowedFiles)) {
  throw new Error(`Portable output violates the file allowlist: ${entries.join(", ")}`);
}
for (const name of entries) {
  const info = await stat(resolve(output, name));
  if (!info.isFile()) throw new Error(`Portable output contains a non-file entry: ${name}`);
  if (/(^|\.)(env|pem|key|pfx|p12)$|backup|report|database|\.db$|\.sql$|\.dump$/i.test(name)) {
    throw new Error(`Forbidden portable filename: ${name}`);
  }
}

const executable = await readFile(resolve(output, EXECUTABLE));
if (executable.length < 2 || executable[0] !== 0x4d || executable[1] !== 0x5a) {
  throw new Error("Portable executable is not a Windows PE file.");
}

const manifest = JSON.parse(await readFile(resolve(output, "portable-manifest.json"), "utf8"));
if (manifest.version !== VERSION || manifest.executable !== EXECUTABLE) {
  throw new Error("Portable manifest metadata does not match the RC6 build.");
}
const { controlledLocalLauncher, safeProjectPathBinding, embeddedFrontend, ...forbiddenBoundaries } = manifest.boundaries;
if (controlledLocalLauncher !== true || safeProjectPathBinding !== true || embeddedFrontend !== true || Object.values(forbiddenBoundaries).some((value) => value !== false)) {
  throw new Error("A forbidden portable capability is enabled in the manifest.");
}
for (const name of [EXECUTABLE, "LICENSE", "README.md"]) {
  const digest = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
  if (manifest.files[name]?.sha256 !== digest) throw new Error(`Checksum mismatch: ${name}`);
}

const readme = await readFile(resolve(output, "README.md"), "utf8");
for (const required of [
  "http://localhost:5173", "http://localhost:8000", "Docker Desktop",
  "no installer", "never starts services automatically", "copy-only", "repository root"
]) if (!readme.includes(required)) throw new Error(`Portable README is missing: ${required}`);
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(readme)) {
  throw new Error("Potential secret assignment detected in portable README.");
}

console.log(`Portable package validation passed: ${output}`);
