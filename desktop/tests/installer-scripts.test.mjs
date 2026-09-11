import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const build = await readFile(resolve(desktop, "scripts", "build_installer.mjs"), "utf8");
const validate = await readFile(resolve(desktop, "scripts", "validate_installer.mjs"), "utf8");
const config = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.installer.conf.json"), "utf8"));

test("installer scripts and RC6 NSIS metadata are present", () => {
  assert.ok(build.length > 0 && validate.length > 0);
  assert.equal(config.bundle.active, true);
  assert.deepEqual(config.bundle.targets, ["nsis"]);
  assert.equal(config.bundle.publisher, "RavenTech Local Test (Unsigned)");
  assert.match(validate, /5\.0\.0-rc6/);
});

test("installer configuration is unsigned, local, and carries no payload sidecars", () => {
  assert.equal(config.bundle.createUpdaterArtifacts, false);
  assert.deepEqual(config.bundle.resources, []);
  assert.deepEqual(config.bundle.externalBin, []);
  assert.deepEqual(config.bundle.windows.webviewInstallMode, { type: "skip" });
  assert.equal(config.bundle.windows.allowDowngrades, false);
  assert.equal(config.bundle.windows.nsis.installMode, "currentUser");
  assert.deepEqual(config.bundle.windows.nsis.languages, ["English", "Spanish"]);
  const windows = config.bundle.windows;
  for (const key of ["certificateThumbprint", "timestampUrl", "signCommand", "wix"]) {
    assert.equal(windows[key], undefined, `forbidden Windows bundle key: ${key}`);
  }
  for (const key of ["hooks", "installerHooks", "template"]) {
    assert.equal(windows.nsis[key], undefined, `forbidden NSIS key: ${key}`);
  }
});

test("installer build uses the pinned CLI without network or signing commands", () => {
  for (const token of ["tauri.js", "makensis.exe", "CARGO_NET_OFFLINE", "--bundles", "nsis", "--no-sign", "--locked", "--offline", "shell: false"]) {
    assert.ok(build.includes(token), `missing safe build token: ${token}`);
  }
  assert.doesNotMatch(build, /npm\s+(install|ci)|npx|curl|Invoke-WebRequest|signtool|powershell/i);
  assert.match(validate, /file allowlist/i);
  assert.match(validate, /Forbidden installer filename/);
  assert.match(build, /--config-only/);
  assert.match(validate, /--require-artifact/);
  assert.match(build, /controlledLocalLauncher:\s*true/);
  assert.match(build, /safeProjectPathBinding:\s*true/);
  assert.match(build, /arbitraryCommandExecution:\s*false/);
  assert.match(build, /expectedBundle.*RavenTech OSINT Desktop_\$\{VERSION\}_x64-setup\.exe/);
  assert.doesNotMatch(build, /Expected exactly one NSIS installer/);
});
