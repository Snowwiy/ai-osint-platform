import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc6";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(desktop, "dist-linux", `RavenTech-OSINT-Desktop-${VERSION}-linux-x86_64`);
if (process.platform !== "linux" || process.arch !== "x64") throw new Error("Linux package validation must run on Linux x86_64.");
const entries = (await readdir(output)).sort();
const allowed = ["LICENSE", "README.md", "linux-runtime-manifest.json", "native-runtime", "raventech-osint-desktop"].sort();
if (JSON.stringify(entries) !== JSON.stringify(allowed)) throw new Error(`Linux package violates its allowlist: ${entries.join(", ")}`);
for (const name of ["raventech-osint-desktop", "native-runtime/backend/raventech-backend", "native-runtime/worker/raventech-worker"]) {
  const path = resolve(output, name);
  const info = await stat(path);
  if (!info.isFile() || (info.mode & 0o111) === 0) throw new Error(`Linux runtime executable is missing executable permission: ${name}`);
}
const desktopBytes = await readFile(resolve(output, "raventech-osint-desktop"));
if (desktopBytes.subarray(0, 4).toString("hex") !== "7f454c46") throw new Error("Tauri desktop artifact is not a Linux ELF executable.");
const manifest = JSON.parse(await readFile(resolve(output, "linux-runtime-manifest.json"), "utf8"));
if (manifest.version !== VERSION || manifest.os !== "linux" || manifest.architecture !== "x86_64" || manifest.runtimeProfile !== "desktop" || manifest.requiredExternalDependencies?.[0] !== "PostgreSQL") throw new Error("Linux runtime metadata is invalid.");
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
