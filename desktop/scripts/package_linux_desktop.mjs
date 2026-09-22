import { createHash } from "node:crypto";
import { chmod, copyFile, cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validateNativeRuntime } from "./native_runtime_package.mjs";

const VERSION = "5.0.0-rc6";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const outputRoot = resolve(desktop, "dist-linux");
const output = resolve(outputRoot, `RavenTech-OSINT-Desktop-${VERSION}-linux-x86_64`);
const sourceDesktop = resolve(desktop, "src-tauri", "target", "release", "raventech-osint-desktop");

if (process.platform !== "linux" || process.arch !== "x64") throw new Error("Linux desktop packaging must run on Linux x86_64.");
const runtime = await validateNativeRuntime({ desktop });
const tauri = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
if (tauri.version !== VERSION || tauri.bundle.active !== false) throw new Error("Linux desktop packaging requires the unchanged RC6 portable Tauri contract.");
await readFile(sourceDesktop);
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await copyFile(sourceDesktop, resolve(output, "raventech-osint-desktop"));
await chmod(resolve(output, "raventech-osint-desktop"), 0o755);
await mkdir(resolve(output, "native-runtime"), { recursive: true });
await cp(runtime.backend, resolve(output, "native-runtime", "backend"), { recursive: true });
await cp(runtime.worker, resolve(output, "native-runtime", "worker"), { recursive: true });
for (const component of ["backend", "worker"]) await chmod(resolve(output, "native-runtime", component, runtime[`${component}Binary`]), 0o755);
await copyFile(resolve(desktop, "LINUX_NATIVE_PACKAGE_README.md"), resolve(output, "README.md"));
await copyFile(resolve(repository, "LICENSE"), resolve(output, "LICENSE"));

const files = {};
for (const name of ["raventech-osint-desktop", "README.md", "LICENSE"]) files[name] = { sha256: createHash("sha256").update(await readFile(resolve(output, name))).digest("hex") };
const manifest = {
  format: 1,
  product: "RavenTech OSINT Desktop",
  version: VERSION,
  os: "linux",
  architecture: "x86_64",
  packagingEngine: "Tauri portable + PyInstaller native runtime",
  runtimeProfile: "desktop",
  requiredExternalDependencies: runtime.requiredExternalDependencies,
  backendSha256: runtime.components.backend.sha256,
  workerSha256: runtime.components.worker.sha256,
  files,
  boundaries: { signed: false, publicRelease: false, postgresBundled: false, autoStartPersistence: false, arbitraryCommandExecution: false },
};
await writeFile(resolve(output, "linux-runtime-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Private Linux desktop package created at ${output}`);
