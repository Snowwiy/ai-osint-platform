import { copyFile, cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { validateNativeRuntime } from "./native_runtime_package.mjs";

const VERSION = "5.0.0-rc6";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const EXECUTABLE = "RavenTech OSINT Desktop.exe";
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const portableRoot = resolve(desktop, "dist-portable");
const output = resolve(portableRoot, PRODUCT_DIRECTORY);
const sourceExecutable = resolve(desktop, "src-tauri", "target", "release", "raventech-osint-desktop.exe");

if (process.platform !== "win32") throw new Error("Portable packaging is Windows-only.");
if (!output.startsWith(`${portableRoot}\\`) || output === portableRoot) {
  throw new Error("Refusing to replace an unsafe portable output path.");
}

await readFile(sourceExecutable);
const nativeRuntime = await validateNativeRuntime({ desktop });
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

const copies = [
  [sourceExecutable, EXECUTABLE],
  [resolve(desktop, "PORTABLE_BUILD_README.md"), "README.md"],
  [resolve(repository, "LICENSE"), "LICENSE"],
];
for (const [source, name] of copies) await copyFile(source, resolve(output, name));
await mkdir(resolve(output, "native-runtime"), { recursive: true });
await cp(nativeRuntime.backend, resolve(output, "native-runtime", "backend"), { recursive: true, errorOnExist: true });
await cp(nativeRuntime.worker, resolve(output, "native-runtime", "worker"), { recursive: true, errorOnExist: true });

async function sha256(name) {
  return createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
}

const files = {};
for (const [, name] of copies) files[name] = { sha256: await sha256(name) };
const manifest = {
  format: 1,
  product: "RavenTech OSINT Desktop",
  version: VERSION,
  kind: "windows-portable-local-test",
  executable: EXECUTABLE,
  files,
  nativeRuntime: {
    packagingEngine: nativeRuntime.packagingEngine,
    requiredExternalDependencies: nativeRuntime.requiredExternalDependencies,
    backend: { binary: nativeRuntime.components.backend.binary, sha256: nativeRuntime.components.backend.sha256, sizeBytes: nativeRuntime.components.backend.sizeBytes, fileCount: nativeRuntime.components.backend.fileCount },
    worker: { binary: nativeRuntime.components.worker.binary, sha256: nativeRuntime.components.worker.sha256, sizeBytes: nativeRuntime.components.worker.sizeBytes, fileCount: nativeRuntime.components.worker.fileCount },
  },
  boundaries: {
    installer: false,
    signing: false,
    serviceAutostart: false,
    controlledLocalLauncher: true,
    safeProjectPathBinding: true,
    embeddedFrontend: true,
    arbitraryCommandExecution: false,
    embeddedBackend: true,
    embeddedDatabase: false,
    hosting: false,
    deployment: false,
    dns: false,
    supabaseMigration: false,
    routerAutomation: false,
    remoteCommandExecution: false,
    offensiveFunctionality: false,
  },
};
await writeFile(resolve(output, "portable-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Portable files collected in ${output}`);
