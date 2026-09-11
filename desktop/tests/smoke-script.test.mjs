import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const smoke = await readFile(resolve(desktop, "scripts", "smoke_desktop.mjs"), "utf8");
const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const config = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
const gitignore = await readFile(resolve(repository, ".gitignore"), "utf8");

test("desktop smoke command and polished branding are registered", () => {
  assert.equal(packageJson.scripts.smoke, "node scripts/smoke_desktop.mjs");
  assert.equal(config.productName, "RavenTech OSINT Desktop");
  assert.equal(config.version, "5.0.0-rc4");
  assert.equal(config.app.windows[0].title, "RavenTech OSINT Desktop — Local Workspace");
});

test("smoke checker covers artifacts, local URLs, permissions, and updater state", () => {
  for (const token of [
    "portable-manifest.json", "installer-manifest.json", "file allowlist",
    "http://localhost:5173", "http://localhost:8000", "capability.permissions",
    "createUpdaterArtifacts", "safeProjectPathBinding", "validate_repository_root", "trusted_script_bytes", "5.0.0-rc4", "--require-artifacts"
  ]) assert.ok(smoke.includes(token), `missing smoke check: ${token}`);
  assert.match(smoke, /tauri-plugin-\(shell\|fs\|updater\)/);
  assert.match(smoke, /checksum mismatch/);
  assert.match(smoke, /manifest file map violates the payload allowlist/);
});

test("generated desktop outputs remain ignored", () => {
  for (const path of ["desktop/dist-portable/", "desktop/dist-installer/"]) {
    assert.ok(gitignore.includes(path), `missing ignore rule: ${path}`);
  }
  assert.ok(gitignore.split(/\r?\n/).some((rule) => rule === "target/" || rule === "desktop/src-tauri/target/"));
});
