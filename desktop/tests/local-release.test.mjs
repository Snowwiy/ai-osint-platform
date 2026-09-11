import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";
import { resolve } from "node:path";

const desktop = resolve(import.meta.dirname, "..");
const repository = resolve(desktop, "..");
const packageJson = JSON.parse(await readFile(resolve(desktop, "package.json"), "utf8"));
const tauri = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.conf.json"), "utf8"));
const installer = JSON.parse(await readFile(resolve(desktop, "src-tauri", "tauri.installer.conf.json"), "utf8"));
const build = await readFile(resolve(desktop, "scripts", "package_local_release.mjs"), "utf8");
const validate = await readFile(resolve(desktop, "scripts", "validate_local_release.mjs"), "utf8");
const gitignore = await readFile(resolve(repository, ".gitignore"), "utf8");

test("branding and RC6 metadata are consistent", async () => {
  assert.equal(packageJson.version, "5.0.0-rc6");
  assert.equal(tauri.productName, "RavenTech OSINT Desktop");
  assert.equal(tauri.version, "5.0.0-rc6");
  assert.equal(tauri.app.windows[0].title, "RavenTech OSINT Desktop — Local Workspace");
  assert.deepEqual(tauri.bundle.icon, ["icons/icon.ico", "icons/icon.png"]);
  assert.equal(installer.bundle.windows.nsis.installerIcon, "icons/icon.ico");
  for (const icon of ["assets/raventech-osint-icon.svg", "src-tauri/icons/icon.ico", "src-tauri/icons/icon.png"]) {
    await access(resolve(desktop, icon));
  }
  const iconSource = await readFile(resolve(desktop, "assets", "raventech-osint-icon.svg"), "utf8");
  assert.doesNotMatch(iconSource, /<image|<text|font-family|(?:xlink:)?href=/i);
  assert.match(iconSource, /viewBox="0 0 512 512"/);
});

test("local release workflow has a strict private artifact contract", () => {
  assert.match(build, /RavenTech-OSINT-Desktop-\$\{VERSION\}/);
  assert.match(build, /validate_portable\.mjs/);
  assert.match(build, /validate_installer\.mjs/);
  assert.match(build, /gitCommit\(\)/);
  assert.match(build, /SHA256SUMS\.txt/);
  assert.match(validate, /expectedFiles/);
  assert.match(validate, /forbiddenName/);
  assert.match(validate, /embeddedFrontend !== true/);
  assert.ok(gitignore.split(/\r?\n/).includes("desktop/dist-local-release/"));
});

test("local release scripts cannot publish, sign, or download", () => {
  const source = `${build}\n${validate}`;
  assert.doesNotMatch(source, /git\s+push|gh\s+release|npm\s+publish|signtool|timestampUrl|https:\/\//i);
  assert.doesNotMatch(source, /shell:\s*true/);
  assert.match(build, /signed:\s*false/);
  assert.match(build, /localOnly:\s*true/);
  assert.match(build, /dockerRequired:\s*true/);
});
