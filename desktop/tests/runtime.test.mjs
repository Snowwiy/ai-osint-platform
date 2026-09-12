import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const app = await readFile(resolve(desktop, "ui/app.js"), "utf8");
const html = await readFile(resolve(desktop, "ui/index.html"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri/src/main.rs"), "utf8");
const config = JSON.parse(await readFile(resolve(desktop, "src-tauri/tauri.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri/capabilities/default.json"), "utf8"));
const build = await readFile(resolve(desktop, "scripts/build.mjs"), "utf8");
const frontendApp = await readFile(resolve(desktop, "../frontend/src/App.tsx"), "utf8");
const viteConfig = await readFile(resolve(desktop, "../frontend/vite.config.ts"), "utf8");

test("uses fixed local frontend and backend defaults", () => {
  assert.match(app, /http:\/\/localhost:5173/);
  assert.match(app, /http:\/\/localhost:8000/);
  assert.match(rust, /127\.0\.0\.1:5173/);
  assert.match(rust, /127\.0\.0\.1:8000/);
  for (const path of ["/health", "/health/ready", "/api/v1/release"]) {
    assert.ok(rust.includes(path), `missing fixed probe: ${path}`);
  }
  assert.doesNotMatch(`${app}\n${rust}`, /https:\/\//);
});

test("production embeds React while development accepts successful HTML", () => {
  assert.equal(config.build.frontendDist, "../dist");
  assert.match(build, /VITE_ROUTER_BASENAME:\s*"\/app"/);
  assert.match(build, /VITE_API_BASE_URL:\s*"http:\/\/localhost:8000\/api\/v1"/);
  assert.match(build, /"--base", "\.\/"/);
  assert.match(build, /"--mode", "desktop"/);
  assert.match(build, /startsWith\("VITE_"\)/);
  assert.match(viteConfig, /mode === "desktop" \? false : undefined/);
  assert.match(frontendApp, /basename:\s*import\.meta\.env\.VITE_ROUTER_BASENAME \|\| "\/"/);
  assert.match(rust, /frontend_html_response_is_healthy/);
  assert.match(rust, /\(200\.\.300\)\.contains\(&code\)/);
  assert.match(rust, /eq_ignore_ascii_case\("text\/html"\)/);
  assert.match(rust, /for path in \["\/", "\/index\.html"\]/);
  assert.match(rust, /cfg!\(debug_assertions\) && development_frontend\.healthy/);
  assert.match(app, /EMBEDDED_FRONTEND_URL = "\.\/app\/"/);
  assert.match(app, /currentFrontendMode === "development" \? FRONTEND_URL : EMBEDDED_FRONTEND_URL/);
});

test("offers copy fallback and only fixed controlled launcher actions", () => {
  for (const command of [
    "start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1",
    "check_platform.ps1", "apply_lan_monitoring_config.ps1", "open_platform.ps1 -Target frontend",
    "cd frontend; npm run dev", "docker compose up -d postgres redis backend celery-worker"
  ]) assert.ok(app.includes(command), `missing copy command: ${command}`);
  assert.doesNotMatch(app, /__TAURI__\.(shell|process)|Command\.create|invoke\(["'](?:shell|execute)/i);
  for (const invoke of ["start_platform", "stop_platform", "restart_platform", "check_platform", "apply_lan_monitoring_config", "open_local_frontend"]) {
    assert.ok(app.includes(`invoke: "${invoke}"`), `missing fixed launcher mapping: ${invoke}`);
  }
  assert.match(rust, /Command::new\(&powershell\)/);
  assert.match(rust, /join\("System32"\)/);
  assert.match(app, /confirmedArgument: true/);
  assert.match(rust, /if !confirmed/);
});

test("keeps Tauri permissions and navigation constrained", () => {
  assert.deepEqual(capability.permissions, []);
  assert.equal(capability.remote, undefined);
  assert.equal(config.app.security.dangerousRemoteDomainIpcAccess, undefined);
  assert.match(config.app.security.csp, /frame-src 'self' http:\/\/localhost:5173/);
  assert.match(config.app.security.csp, /connect-src ipc: http:\/\/ipc\.localhost http:\/\/localhost:8000/);
  assert.doesNotMatch(config.app.security.csp, /frame-src[^;]*\*/);
  assert.doesNotMatch(html, /allow-popups|allow-top-navigation/);
  assert.equal(config.bundle.active, false);
});

test("contains bilingual status and service-specific help without secret fields", () => {
  for (const text of [
    "Backend is not reachable", "Frontend is not reachable", "Backend dependencies are not ready",
    "No se puede acceder al backend", "No se puede acceder al frontend", "Las dependencias del backend no están listas"
  ]) assert.ok(app.includes(text), `missing localized label: ${text}`);
  for (const text of ["Bundled React assets", "Recursos React incluidos", "Not required", "No requerido"]) {
    assert.ok(app.includes(text), `missing embedded frontend label: ${text}`);
  }
  assert.doesNotMatch(`${app}\n${html}`, /(api[_-]?key|access[_-]?token|password|secret)\s*[:=]/i);
});

test("native host metrics use fixed read-only Windows APIs", () => {
  for (const marker of ["GlobalMemoryStatusEx", "GetSystemTimes", "GetDiskFreeSpaceExW", "GetTickCount64", "GetComputerNameW", "GetVersionExW"]) {
    assert.ok(rust.includes(marker), `missing native metric API: ${marker}`);
  }
  assert.match(rust, /async fn get_native_host_metrics\(\)/);
  assert.match(app, /raventech-native-host-metrics/);
  assert.match(html, /host-metrics-status/);
  assert.doesNotMatch(rust, /wmic|powershell.*metric|Get-CimInstance/);
  assert.deepEqual(capability.permissions, []);
});
