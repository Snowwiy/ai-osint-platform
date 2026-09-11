import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rust = await readFile(resolve(desktop, "src-tauri", "src", "main.rs"), "utf8");
const app = await readFile(resolve(desktop, "ui", "app.js"), "utf8");
const html = await readFile(resolve(desktop, "ui", "index.html"), "utf8");
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri", "capabilities", "default.json"), "utf8"));

const scripts = [
  "start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1",
  "check_platform.ps1", "open_platform.ps1",
];
const commands = [
  "check_platform", "start_platform", "stop_platform", "restart_platform", "open_local_frontend",
];

test("Rust launcher allowlist contains exactly the five approved scripts", () => {
  for (const script of scripts) assert.ok(rust.includes(`"${script}"`), `missing ${script}`);
  for (const rejected of ["reset_demo.ps1", "restore_db.ps1", "backup_db.ps1", "local_monitor_agent.ps1"]) {
    assert.ok(!rust.includes(rejected), `unsafe script entered allowlist: ${rejected}`);
  }
  assert.deepEqual([...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]), ["&powershell"]);
  assert.match(rust, /script\.parent\(\) == Some\(scripts\.as_path\(\)\)/);
  assert.match(rust, /scripts\.starts_with\(&root\)/);
  for (const marker of ["docker-compose.yml", "pyproject.toml", 'join("System32")', 'var_os("SystemRoot")']) {
    assert.ok(rust.includes(marker), `missing trusted launcher root marker: ${marker}`);
  }
});

test("Tauri exposes fixed launcher commands with only an internal app handle", () => {
  for (const command of commands) {
    assert.match(rust, new RegExp(`async fn ${command}\\(app: tauri::AppHandle\\) -> LauncherResult`));
    assert.ok(app.includes(`invoke: "${command}"`), `UI mapping missing ${command}`);
  }
  assert.doesNotMatch(rust, /command:\s*String|script:\s*String|args:\s*Vec/);
  assert.doesNotMatch(rust, /fn (?:check|start|stop|restart|open)_\w+\([^)]*(?:String|PathBuf|Vec)/);
  assert.doesNotMatch(app, /prompt\(|contenteditable|name=["']command/i);
  assert.deepEqual(capability.permissions, []);
});

test("project binding validates fixed repository markers without adding filesystem permissions", () => {
  for (const marker of [
    "docker-compose.yml", "pyproject.toml", "desktop/package.json",
    "frontend/package.json", "backend/app", "REQUIRED_SCRIPTS",
    "validate_repository_root", "PROJECT_PATH_FILE", "trusted_script_bytes", "include_bytes!"
  ]) assert.ok(rust.includes(marker), `missing binding marker: ${marker}`);
  assert.match(rust, /async fn bind_project_path\([\s\S]*project_path: String/);
  assert.match(app, /invoke\("bind_project_path", \{ projectPath: input\.value \}\)/);
  assert.deepEqual(capability.permissions, []);
});

test("launcher resolution order is configured, current directory, then development-relative", () => {
  const configured = rust.indexOf('return Some((root, "configured"))');
  const current = rust.indexOf('return Some((root, "currentDirectory"))');
  const development = rust.indexOf('return Some((root, "developmentRelative"))');
  assert.ok(configured > 0 && configured < current && current < development);
  assert.ok(rust.includes('unwrap_or("copyOnly")'));
});

test("launcher output is bounded, sanitized, and timed out safely", () => {
  for (const marker of ["MAX_COMMAND_OUTPUT_BYTES", "sensitive output removed", "database_url", "supabase", "child.kill()", "timed_out", "wait_failed"]) {
    assert.ok(rust.includes(marker), `missing launcher safety marker: ${marker}`);
  }
  assert.match(rust, /Duration::from_secs\(150\)/);
  assert.match(rust, /Stdio::null\(\)/);
  assert.match(rust, /-NoProfile/);
});

test("start stop and restart require confirmation while copy fallback remains", () => {
  for (const label of ["start", "stop", "restart"]) {
    assert.match(app, new RegExp(`label: "${label}"[^\n]+confirm: true`));
  }
  assert.match(html, /id="confirm-dialog"/);
  assert.match(app, /navigator\.clipboard\.writeText\(command\.text\)/);
  assert.match(app, /commandUnavailable/);
});
