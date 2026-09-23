import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePostgresqlRuntimeTree } from "./native_runtime_package.mjs";

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
const { controlledLocalLauncher, safeProjectPathBinding, embeddedFrontend, embeddedBackend, embeddedDatabase, managedPostgresqlRuntime, initializedDatabase, ...forbiddenBoundaries } = manifest.boundaries;
if (controlledLocalLauncher !== true || safeProjectPathBinding !== true || embeddedFrontend !== true || embeddedBackend !== true || embeddedDatabase !== false || managedPostgresqlRuntime !== true || initializedDatabase !== false || Object.values(forbiddenBoundaries).some((value) => value !== false)) {
  throw new Error("A forbidden portable capability is enabled in the manifest.");
}
for (const name of [EXECUTABLE, "LICENSE", "README.md"]) {
  const digest = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
  if (manifest.files[name]?.sha256 !== digest) throw new Error(`Checksum mismatch: ${name}`);
}

const runtimeRoot = resolve(output, "native-runtime");
if (JSON.stringify((await readdir(runtimeRoot)).sort()) !== JSON.stringify(["backend", "postgresql", "worker"])) {
  throw new Error("Portable native runtime must contain the fixed backend, worker, and PostgreSQL 16 runtime.");
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
if (manifest.nativeRuntime?.packagingEngine !== "PyInstaller" || manifest.nativeRuntime.postgresql?.major !== 16 || !manifest.nativeRuntime.postgresql.version || manifest.nativeRuntime.requiredExternalDependencies?.includes("PostgreSQL")) throw new Error("Portable native runtime metadata is invalid.");

const postgresRoot = resolve(runtimeRoot, "postgresql");
const postgresManifest = JSON.parse(await readFile(resolve(postgresRoot, "manifest.json"), "utf8"));
if (postgresManifest.major_version !== 16 || postgresManifest.os !== "windows" || postgresManifest.architecture !== "x86_64" || !postgresManifest.files) throw new Error("Bundled PostgreSQL manifest metadata is invalid.");
await validatePostgresqlRuntimeTree(postgresRoot);
for (const binary of ["postgres.exe", "initdb.exe", "psql.exe", "pg_isready.exe", "pg_ctl.exe"]) {
  const path = resolve(postgresRoot, "bin", binary);
  const bytes = await readFile(path);
  const file = postgresManifest.files[`bin/${binary}`];
  if (!file || file.size_bytes !== bytes.length || file.sha256 !== createHash("sha256").update(bytes).digest("hex")) throw new Error(`Bundled PostgreSQL checksum is invalid: ${binary}`);
}
if ((await readdir(resolve(postgresRoot, "share"))).length === 0) throw new Error("Bundled PostgreSQL share resources are missing.");
const postgresVersion = await import("node:child_process").then(({ spawnSync }) => spawnSync(resolve(postgresRoot, "bin", "postgres.exe"), ["--version"], { cwd: resolve(postgresRoot, "bin"), shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }));
if (postgresVersion.error || postgresVersion.status !== 0 || !postgresVersion.stdout.includes("PostgreSQL) 16.")) throw new Error("Bundled PostgreSQL failed its version check.");

const readme = await readFile(resolve(output, "README.md"), "utf8");
for (const required of [
  "http://localhost:5173", "http://localhost:8000", "Managed PostgreSQL 16 is included",
  "Fresh native installs start and supervise managed PostgreSQL", "no installer", "copy-only", "repository root"
]) if (!readme.includes(required)) throw new Error(`Portable README is missing: ${required}`);
if (/(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+/i.test(readme)) {
  throw new Error("Potential secret assignment detected in portable README.");
}

console.log(`Portable package validation passed: ${output}`);
