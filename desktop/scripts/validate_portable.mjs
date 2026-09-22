import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc6";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const EXECUTABLE = "RavenTech OSINT Desktop.exe";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(desktop, "dist-portable", PRODUCT_DIRECTORY);
const allowedFiles = [EXECUTABLE, "LICENSE", "README.md", "portable-manifest.json", "native-runtime"].sort();

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
  if (name !== "native-runtime" && !info.isFile()) throw new Error(`Portable output contains an unexpected directory: ${name}`);
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
const { controlledLocalLauncher, safeProjectPathBinding, embeddedFrontend, embeddedBackend, ...forbiddenBoundaries } = manifest.boundaries;
if (controlledLocalLauncher !== true || safeProjectPathBinding !== true || embeddedFrontend !== true || embeddedBackend !== true || Object.values(forbiddenBoundaries).some((value) => value !== false)) {
  throw new Error("A forbidden portable capability is enabled in the manifest.");
}
for (const name of [EXECUTABLE, "LICENSE", "README.md"]) {
  const digest = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
  if (manifest.files[name]?.sha256 !== digest) throw new Error(`Checksum mismatch: ${name}`);
}

const runtimeRoot = resolve(output, "native-runtime");
if (JSON.stringify((await readdir(runtimeRoot)).sort()) !== JSON.stringify(["backend", "worker"])) {
  throw new Error("Portable native runtime must contain only the fixed backend and worker directories.");
}
for (const [component, binaryName] of [["backend", "RavenTechBackend.exe"], ["worker", "RavenTechWorker.exe"]]) {
  const componentRoot = resolve(runtimeRoot, component);
  const tree = async (directory, prefix = "") => {
    const paths = [];
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (/(^|\/)(\.env(?:\..*)?|backups?|uploads?|logs?)(\/|$)|\.(key|pfx|p12|db|sqlite|dump|log)$/i.test(relative)) throw new Error(`Forbidden native runtime file: ${relative}`);
      const full = resolve(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Native runtime may not include symlinks: ${relative}`);
      if (entry.isDirectory()) paths.push(...await tree(full, relative));
      else if (entry.isFile()) {
        if (/\.pem$/i.test(relative) && /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test((await readFile(full)).subarray(0, 4096).toString("utf8"))) throw new Error(`Private key material is prohibited: ${relative}`);
        paths.push(relative);
      }
      else throw new Error(`Unsupported native runtime entry: ${relative}`);
    }
    return paths;
  };
  const names = await tree(componentRoot);
  const native = manifest.nativeRuntime?.[component];
  if (!native || !names.includes(binaryName) || !names.includes("manifest.json") || names.length !== native.fileCount) throw new Error(`Packaged ${component} resources are incomplete.`);
  const artifactManifest = JSON.parse(await readFile(resolve(componentRoot, "manifest.json"), "utf8"));
  if (artifactManifest.version !== VERSION || artifactManifest.component !== component || artifactManifest.os !== "windows" || artifactManifest.architecture !== "x86_64") throw new Error(`Packaged ${component} manifest has incompatible platform metadata.`);
  const binary = await readFile(resolve(componentRoot, binaryName));
  const sha256 = createHash("sha256").update(binary).digest("hex");
  if (sha256 !== native.sha256 || sha256 !== artifactManifest.binary_sha256 || binary.length !== artifactManifest.binary_size_bytes) throw new Error(`Packaged ${component} binary checksum is invalid.`);
  const versionResult = await import("node:child_process").then(({ spawnSync }) => spawnSync(resolve(componentRoot, binaryName), ["--version"], { cwd: componentRoot, shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }));
  if (versionResult.error || versionResult.status !== 0 || versionResult.stdout.trim() !== VERSION) throw new Error(`Packaged ${component} executable reports an incompatible version.`);
}
if (manifest.nativeRuntime?.packagingEngine !== "PyInstaller" || JSON.stringify(manifest.nativeRuntime.requiredExternalDependencies) !== JSON.stringify(["PostgreSQL", "external configuration"])) throw new Error("Portable native runtime metadata is invalid.");

const readme = await readFile(resolve(output, "README.md"), "utf8");
for (const required of [
  "http://localhost:5173", "http://localhost:8000", "PostgreSQL remains external",
  "desktop starts and supervises only its fixed native backend and worker", "no installer", "copy-only", "repository root"
]) if (!readme.includes(required)) throw new Error(`Portable README is missing: ${required}`);
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(readme)) {
  throw new Error("Potential secret assignment detected in portable README.");
}

console.log(`Portable package validation passed: ${output}`);
