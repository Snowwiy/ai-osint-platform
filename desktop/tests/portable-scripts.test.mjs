import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const names = ["build_portable.mjs", "package_portable.mjs", "validate_portable.mjs"];
const scripts = Object.fromEntries(await Promise.all(names.map(async (name) => [
  name,
  await readFile(resolve(desktop, "scripts", name), "utf8"),
])));

test("portable scripts exist and keep the RC6 output contract", () => {
  for (const name of names) assert.ok(scripts[name].length > 0, `${name} is empty`);
  assert.match(scripts["package_portable.mjs"], /RavenTech-OSINT-Desktop-\$\{VERSION\}/);
  assert.match(scripts["package_portable.mjs"], /RavenTech OSINT Desktop\.exe/);
  assert.match(scripts["validate_portable.mjs"], /5\.0\.0-rc6/);
});

test("portable build is locked, offline, and does not invoke an installer", () => {
  const build = scripts["build_portable.mjs"];
  for (const flag of ["--release", "--locked", "--offline"]) assert.ok(build.includes(flag));
  assert.doesNotMatch(build, /tauri\s+build|bundle|msi|nsis|signtool/i);
  assert.match(build, /shell:\s*false/);
});

test("portable collection uses a strict allowlist without sensitive data", () => {
  const packaging = scripts["package_portable.mjs"];
  const validation = scripts["validate_portable.mjs"];
  for (const allowed of ["README.md", "LICENSE", "portable-manifest.json"]) {
    assert.ok(validation.includes(allowed), `missing allowlisted file: ${allowed}`);
  }
  assert.doesNotMatch(packaging, /\.env|backups|reports_output|\.sql|\.dump/i);
  assert.match(validation, /Forbidden portable filename/);
  assert.match(validation, /Checksum mismatch/);
  assert.match(packaging, /controlledLocalLauncher:\s*true/);
  assert.match(packaging, /safeProjectPathBinding:\s*true/);
  assert.match(packaging, /arbitraryCommandExecution:\s*false/);
});
