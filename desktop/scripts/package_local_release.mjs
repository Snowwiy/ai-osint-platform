import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "5.0.0-rc6";
const PRODUCT = "RavenTech OSINT Desktop";
const PRODUCT_DIRECTORY = `RavenTech-OSINT-Desktop-${VERSION}`;
const PORTABLE_EXE = `${PRODUCT}.exe`;
const INSTALLER_EXE = `RavenTech-OSINT-Desktop-${VERSION}-unsigned-setup.exe`;
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const releaseRoot = resolve(desktop, "dist-local-release");
const output = resolve(releaseRoot, PRODUCT_DIRECTORY);

if (process.platform !== "win32") throw new Error("Local release packaging is Windows-only.");
if (!output.startsWith(`${releaseRoot}\\`) || output === releaseRoot) {
  throw new Error("Refusing to replace an unsafe local release output path.");
}

function runNode(script, args = []) {
  const result = spawnSync(process.execPath, [resolve(desktop, "scripts", script), ...args], {
    cwd: desktop,
    env: process.env,
    shell: false,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${script} failed with exit code ${result.status}.`);
}

function gitCommit() {
  const result = spawnSync("git", ["rev-parse", "HEAD"], {
    cwd: repository,
    encoding: "utf8",
    shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error("Unable to resolve the local Git commit.");
  const commit = result.stdout.trim();
  if (!/^[0-9a-f]{40}$/.test(commit)) throw new Error("Unexpected Git commit metadata.");
  return commit;
}

runNode("validate_portable.mjs");
runNode("validate_installer.mjs", ["--require-artifact"]);

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

const copies = [
  [resolve(desktop, "dist-portable", PRODUCT_DIRECTORY, PORTABLE_EXE), PORTABLE_EXE],
  [resolve(desktop, "dist-installer", PRODUCT_DIRECTORY, INSTALLER_EXE), INSTALLER_EXE],
  [resolve(desktop, "LOCAL_RELEASE_README.md"), "README.md"],
  [resolve(desktop, "LOCAL_STARTUP_INSTRUCTIONS.md"), "LOCAL_STARTUP_INSTRUCTIONS.md"],
  [resolve(repository, "KNOWN_LIMITATIONS.md"), "KNOWN_LIMITATIONS.md"],
];
for (const [source, name] of copies) await copyFile(source, resolve(output, name));

async function sha256(name) {
  return createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
}

const files = {};
for (const [, name] of copies) files[name] = { sha256: await sha256(name) };
const checksumText = Object.entries(files)
  .map(([name, metadata]) => `${metadata.sha256}  ${name}`)
  .join("\n");
await writeFile(resolve(output, "SHA256SUMS.txt"), `${checksumText}\n`, "utf8");

const manifest = {
  format: 1,
  appName: PRODUCT,
  version: VERSION,
  buildTime: new Date().toISOString(),
  commit: gitCommit(),
  portableArtifact: PORTABLE_EXE,
  installerArtifact: INSTALLER_EXE,
  signed: false,
  localOnly: true,
  dockerRequired: true,
  files,
  boundaries: {
    publicRelease: false,
    autoUpdate: false,
    serviceAutostart: false,
    embeddedFrontend: true,
    bundledBackend: false,
    bundledDatabase: false,
    bundledRedis: false,
    bundledCredentials: false,
    broadFilesystemAccess: false,
    arbitraryCommandExecution: false,
    routerAutomation: false,
    remoteAdministration: false,
    remoteCommandExecution: false,
    offensiveFunctionality: false,
  },
};
await writeFile(resolve(output, "local-release-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
runNode("validate_local_release.mjs", ["--require-artifact"]);
console.log(`Local-only release package collected in ${output}`);
