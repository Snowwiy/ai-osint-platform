import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc5";
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
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

const copies = [
  [sourceExecutable, EXECUTABLE],
  [resolve(desktop, "PORTABLE_BUILD_README.md"), "README.md"],
  [resolve(repository, "LICENSE"), "LICENSE"],
];
for (const [source, name] of copies) await copyFile(source, resolve(output, name));

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
  boundaries: {
    installer: false,
    signing: false,
    serviceAutostart: false,
    controlledLocalLauncher: true,
    safeProjectPathBinding: true,
    arbitraryCommandExecution: false,
    embeddedBackend: false,
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
