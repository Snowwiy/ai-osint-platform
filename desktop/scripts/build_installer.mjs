import { createHash } from "node:crypto";
import { access, copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const VERSION = "5.0.0-rc6";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const INSTALLER_NAME = `RavenTech-OSINT-Desktop-${VERSION}-unsigned-setup.exe`;
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const frontend = resolve(repository, "frontend");
const installerRoot = resolve(desktop, "dist-installer");
const output = resolve(installerRoot, PRODUCT_DIRECTORY);
const tauriCli = resolve(desktop, "node_modules", "@tauri-apps", "cli", "tauri.js");
const bundleDirectory = resolve(desktop, "src-tauri", "target", "release", "bundle", "nsis");
const expectedBundle = resolve(bundleDirectory, `RavenTech OSINT Desktop_${VERSION}_x64-setup.exe`);
const nsisCompiler = resolve(process.env.LOCALAPPDATA ?? "", "tauri", "NSIS", "makensis.exe");

if (process.platform !== "win32") throw new Error("Installer builds are Windows-only.");
if (!output.startsWith(`${installerRoot}\\`) || output === installerRoot) {
  throw new Error("Refusing to replace an unsafe installer output path.");
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    env: { ...process.env, CI: "true", CARGO_NET_OFFLINE: "true" },
    shell: false,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
  }
}

try {
  await access(tauriCli);
  await access(nsisCompiler);
} catch {
  throw new Error(
    "Pinned Tauri CLI dependencies and cached NSIS tools are required. " +
    "Install them only in a separately approved dependency setup; this build will not download them."
  );
}

console.log("Validating desktop, portable, and installer source contracts...");
run(process.execPath, [resolve(desktop, "scripts", "validate.mjs")], desktop);
run(process.execPath, ["--test", ...[
  "installer-scripts.test.mjs", "launcher.test.mjs", "local-scripts.test.mjs", "first-run.test.mjs",
  "portable-scripts.test.mjs", "runtime.test.mjs", "smoke-script.test.mjs",
].map((name) => resolve(desktop, "tests", name))], desktop);
run(process.execPath, [resolve(desktop, "scripts", "validate_installer.mjs"), "--config-only"], desktop);
try {
  await access(resolve(desktop, "dist-portable", PRODUCT_DIRECTORY, "portable-manifest.json"));
  run(process.execPath, [resolve(desktop, "scripts", "validate_portable.mjs")], desktop);
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
  console.log("No portable artifact is present; portable source checks still passed.");
}
run(process.execPath, [resolve(desktop, "scripts", "build.mjs")], desktop);

console.log("Confirming the browser frontend still builds...");
run(process.execPath, [resolve(frontend, "node_modules", "typescript", "bin", "tsc"), "--noEmit"], frontend);
run(process.execPath, [resolve(frontend, "node_modules", "vite", "bin", "vite.js"), "build"], frontend);

console.log("Building an unsigned, current-user NSIS installer...");
run(process.execPath, [
  tauriCli,
  "build",
  "--ci",
  "--no-sign",
  "--bundles", "nsis",
  "--config", resolve(desktop, "src-tauri", "tauri.installer.conf.json"),
  "--", "--locked", "--offline",
], desktop);

await access(expectedBundle);

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await copyFile(expectedBundle, resolve(output, INSTALLER_NAME));
await copyFile(resolve(desktop, "INSTALLER_BUILD_README.md"), resolve(output, "README.md"));
await copyFile(resolve(repository, "LICENSE"), resolve(output, "LICENSE"));

async function sha256(name) {
  return createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
}

const files = {};
for (const name of [INSTALLER_NAME, "README.md", "LICENSE"]) {
  files[name] = { sha256: await sha256(name) };
}
const manifest = {
  format: 1,
  product: "RavenTech OSINT Desktop",
  version: VERSION,
  kind: "windows-nsis-unsigned-local-test",
  installer: INSTALLER_NAME,
  signed: false,
  publicRelease: false,
  files,
  boundaries: {
    autoUpdate: false,
    serviceAutostart: false,
    controlledLocalLauncher: true,
    safeProjectPathBinding: true,
    embeddedFrontend: true,
    arbitraryCommandExecution: false,
    embeddedBackend: false,
    embeddedDatabase: false,
    bundledCredentials: false,
    hosting: false,
    deployment: false,
    dns: false,
    supabaseMigration: false,
    routerAutomation: false,
    remoteCommandExecution: false,
    offensiveFunctionality: false
  }
};
await writeFile(resolve(output, "installer-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
run(process.execPath, [resolve(desktop, "scripts", "validate_installer.mjs"), "--require-artifact"], desktop);
console.log(`Unsigned local installer collected in ${output}`);
