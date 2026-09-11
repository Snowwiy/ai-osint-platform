import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const names = [
  "start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1",
  "check_platform.ps1", "open_platform.ps1",
];
const scripts = Object.fromEntries(await Promise.all(names.map(async (name) => [
  name,
  await readFile(resolve(repository, "scripts", "local", name), "utf8"),
])));

test("approved scripts use fixed repository-relative paths and strict errors", () => {
  for (const [name, source] of Object.entries(scripts)) {
    assert.match(source, /Set-StrictMode -Version Latest/);
    assert.match(source, /\$ErrorActionPreference = "Stop"/);
    assert.doesNotMatch(source, /Read-Host|Invoke-Expression|iex\b|ScriptBlock::Create/i, `${name} accepts dynamic execution`);
  }
  for (const name of ["start_platform.ps1", "stop_platform.ps1", "check_platform.ps1"]) {
    assert.match(scripts[name], /\$PSScriptRoot/);
  }
  assert.match(scripts["open_platform.ps1"], /\[ValidateSet\("frontend", "backend", "docs"\)\]/);
});

test("service scripts remain non-destructive and do not expose configuration", () => {
  const combined = Object.values(scripts).join("\n");
  assert.doesNotMatch(combined, /docker\s+compose\s+down|--volumes|-v\b|Remove-Item|reset_demo|restore_db|\.env|Get-Content\s+env:/i);
  assert.match(scripts["stop_platform.ps1"], /docker compose stop backend celery-worker postgres redis/);
  assert.match(scripts["start_platform.ps1"], /alembic upgrade head/);
});

test("health helpers safely handle release payloads without a status field", () => {
  for (const name of ["start_platform.ps1", "check_platform.ps1"]) {
    assert.match(scripts[name], /PSObject\.Properties\["status"\]/);
    assert.doesNotMatch(scripts[name], /if \(\$response\.status/);
  }
});
