import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePostgresqlRuntimeTree } from "./native_runtime_package.mjs";

const VERSION = "5.0.0-rc6";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(desktop, "dist-linux", `RavenTech-OSINT-Desktop-${VERSION}-linux-x86_64`);
if (process.platform !== "linux" || process.arch !== "x64") throw new Error("Linux package validation must run on Linux x86_64.");
const entries = (await readdir(output)).sort();
const allowed = ["LICENSE", "README.md", "linux-runtime-manifest.json", "native-runtime", "raventech-osint-desktop"].sort();
if (JSON.stringify(entries) !== JSON.stringify(allowed)) throw new Error(`Linux package violates its allowlist: ${entries.join(", ")}`);
for (const name of ["raventech-osint-desktop", "native-runtime/backend/raventech-backend", "native-runtime/worker/raventech-worker", "native-runtime/postgresql/bin/postgres", "native-runtime/postgresql/bin/initdb", "native-runtime/postgresql/bin/psql", "native-runtime/postgresql/bin/pg_isready", "native-runtime/postgresql/bin/pg_ctl"]) {
  const path = resolve(output, name);
  const info = await stat(path);
  if (!info.isFile() || (info.mode & 0o111) === 0) throw new Error(`Linux runtime executable is missing executable permission: ${name}`);
}
const desktopBytes = await readFile(resolve(output, "raventech-osint-desktop"));
if (desktopBytes.subarray(0, 4).toString("hex") !== "7f454c46") throw new Error("Tauri desktop artifact is not a Linux ELF executable.");
const manifest = JSON.parse(await readFile(resolve(output, "linux-runtime-manifest.json"), "utf8"));
if (manifest.version !== VERSION || manifest.os !== "linux" || manifest.architecture !== "x86_64" || manifest.runtimeProfile !== "desktop" || manifest.postgresqlBundled !== true || manifest.requiredExternalDependencies?.includes("PostgreSQL") || manifest.boundaries?.managedPostgresqlRuntime !== true || manifest.boundaries?.initializedDatabase !== false) throw new Error("Linux runtime metadata is invalid.");
const pgRoot = resolve(output, "native-runtime", "postgresql");
await validatePostgresqlRuntimeTree(pgRoot);
const pgManifest = JSON.parse(await readFile(resolve(pgRoot, "manifest.json"), "utf8"));
if (pgManifest.major_version !== 16 || pgManifest.os !== "linux" || pgManifest.architecture !== "x86_64" || !pgManifest.required_libraries) throw new Error("Linux PostgreSQL metadata is invalid.");
for (const name of ["postgres", "initdb", "psql", "pg_isready", "pg_ctl"]) {
  const path = resolve(pgRoot, "bin", name);
  const bytes = await readFile(path);
  if (bytes.subarray(0, 4).toString("hex") !== "7f454c46" || (((await stat(path)).mode & 0o111) === 0)) throw new Error(`Linux PostgreSQL binary is invalid: ${name}`);
  const metadata = pgManifest.files[`bin/${name}`];
  if (!metadata || metadata.size_bytes !== bytes.length || metadata.sha256 !== createHash("sha256").update(bytes).digest("hex")) throw new Error(`Linux PostgreSQL checksum is invalid: ${name}`);
}
const snowballPath = resolve(pgRoot, "lib", "dict_snowball.so");
const snowballBytes = await readFile(snowballPath);
const snowballRecord = pgManifest.files["lib/dict_snowball.so"];
if (!snowballRecord || snowballRecord.size_bytes !== snowballBytes.length || snowballRecord.sha256 !== createHash("sha256").update(snowballBytes).digest("hex")) throw new Error("Linux PostgreSQL shared-module resource is invalid.");
for (const name of ["postgres", "initdb", "psql", "pg_isready", "pg_ctl", "lib/dict_snowball.so"]) {
  const dependencyPath = resolve(pgRoot, name.startsWith("lib/") ? name : `bin/${name}`);
  const dependencies = await import("node:child_process").then(({ spawnSync }) => spawnSync("ldd", [dependencyPath], { shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }));
  if (dependencies.error || dependencies.status !== 0 || /not found/.test(`${dependencies.stdout}\n${dependencies.stderr}`)) throw new Error(`Linux PostgreSQL shared-library validation failed for ${name}.`);
}
if ((await readdir(resolve(pgRoot, "share"))).length === 0) throw new Error("Linux PostgreSQL share resources are missing.");
for (const [component, binary] of [["backend", "raventech-backend"], ["worker", "raventech-worker"]]) {
  const root = resolve(output, "native-runtime", component);
  const artifact = JSON.parse(await readFile(resolve(root, "manifest.json"), "utf8"));
  const bytes = await readFile(resolve(root, binary));
  const digest = createHash("sha256").update(bytes).digest("hex");
  if (artifact.version !== VERSION || artifact.component !== component || artifact.os !== "linux" || artifact.architecture !== "x86_64" || digest !== artifact.binary_sha256 || bytes.length !== artifact.binary_size_bytes || digest !== manifest[`${component}Sha256`]) throw new Error(`Linux ${component} artifact is invalid.`);
  const result = await import("node:child_process").then(({ spawnSync }) => spawnSync(resolve(root, binary), ["--version"], { cwd: root, shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }));
  if (result.error || result.status !== 0 || result.stdout.trim() !== VERSION) throw new Error(`Linux ${component} reports an incompatible version.`);
}
for (const name of ["raventech-osint-desktop", "README.md", "LICENSE"]) {
  const digest = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
  if (manifest.files[name]?.sha256 !== digest) throw new Error(`Linux artifact checksum mismatch: ${name}`);
}
console.log(`Linux native desktop package validation passed: ${output}`);
