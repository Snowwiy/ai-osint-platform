import assert from "node:assert/strict";
import { access, readFile, readdir, stat } from "node:fs/promises";
import { test } from "node:test";
import { resolve } from "node:path";

const desktop = resolve(import.meta.dirname, "..");
const repository = resolve(desktop, "..");
const version = "5.0.0-rc6";
const artifactRoot = `RavenTech-OSINT-Desktop-${version}`;
const docs = [
  "OPERATOR_MANUAL.md",
  "DESKTOP_PRIVATE_HANDOFF.md",
  "DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md",
  "FRESH_SETUP_CHECKLIST.md",
  "EXTERNAL_MACHINE_TEST_CHECKLIST.md",
];

test("private handoff documents exist and remain RC6-local", async () => {
  for (const name of docs) await access(resolve(repository, name));
  const source = await Promise.all(docs.map((name) => readFile(resolve(repository, name), "utf8")));
  for (const text of source) {
    assert.match(text, /5\.0\.0-rc6/);
    assert.match(text, /private/i);
    assert.match(text, /unsigned/i);
    assert.match(text, /Docker/);
  }
  assert.doesNotMatch(source.join("\n"), /5\.0\.0-rc[0-5]/);
});

test("operator manual covers the fixed local workflow", async () => {
  const manual = await readFile(resolve(repository, "OPERATOR_MANUAL.md"), "utf8");
  for (const heading of [
    "Local architecture", "Prerequisites", "First-run setup", "Health checks",
    "Login and registration", "Language switch", "Monitoring overview",
    "LAN monitoring and service checks", "Endpoint agents",
    "Posture recommendations", "Reports and export", "Backup and restore",
    "Troubleshooting", "Limitations and safety boundary",
  ]) assert.match(manual, new RegExp(`##[#]? ${heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
  for (const script of ["start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1", "check_platform.ps1", "open_platform.ps1"]) {
    assert.match(manual, new RegExp(script.replace(".", "\\.")));
  }
  for (const url of ["http://localhost:5173", "http://localhost:8000", "/health/ready", "/api/v1/release"]) {
    assert.ok(manual.includes(url));
  }
});

test("private handoff declares exact ignored artifact paths and exclusions", async () => {
  const handoff = await readFile(resolve(repository, "DESKTOP_PRIVATE_HANDOFF.md"), "utf8");
  const gitignore = await readFile(resolve(repository, ".gitignore"), "utf8");
  for (const directory of ["dist-portable", "dist-installer", "dist-local-release"]) {
    assert.ok(handoff.includes(`desktop/${directory}/${artifactRoot}/`));
    assert.ok(gitignore.split(/\r?\n/).includes(`desktop/${directory}/`));
  }
  for (const marker of [".env", "credentials", "tokens", "database dumps", "backups", "generated reports", "logs"]) {
    assert.ok(handoff.includes(marker));
  }
});

test("fresh setup checklist covers reproducible RC6 operator setup", async () => {
  const setup = await readFile(resolve(repository, "FRESH_SETUP_CHECKLIST.md"), "utf8");
  for (const marker of [
    "git clone", "Copy-Item -LiteralPath .env.example", "docker compose build",
    "alembic upgrade head", "npm ci", "npm run dev", "/health/ready",
    "/api/v1/release", "scripts/create_admin.py", "scripts.seed_demo_data",
    "reset_demo.ps1 -Confirmation RESET-DEMO", "npm run tauri:dev",
    "npm run portable:build", "npm run installer:build",
    "npm run local-release:package", "DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md",
  ]) assert.ok(setup.includes(marker), `Missing fresh-setup marker: ${marker}`);
  for (const exclusion of [".env", "secret", "token", "credential", "database dump", "backup", "generated report", "log", "local user data"]) {
    assert.ok(setup.includes(exclusion), `Missing fresh-setup exclusion: ${exclusion}`);
  }
});

test("external-machine checklist covers transfer prerequisites and recovery", async () => {
  const external = await readFile(resolve(repository, "EXTERNAL_MACHINE_TEST_CHECKLIST.md"), "utf8");
  for (const prerequisite of ["Windows 10 or 11 x64", "WebView2 Runtime", "Docker Desktop", "Git", "Node.js and npm", "Rust/Cargo", "Tauri CLI", "NSIS"]) {
    assert.ok(external.includes(prerequisite), `Missing external prerequisite: ${prerequisite}`);
  }
  for (const workflow of ["git clone", "Copy-Item -LiteralPath .env.example", "alembic upgrade head", "npm run dev", "scripts/create_admin.py", "scripts.seed_demo_data", "Validate and save", "/health/ready", "/api/v1/release", "Settings > Apps > Installed apps"]) {
    assert.ok(external.includes(workflow), `Missing external workflow: ${workflow}`);
  }
  for (const recovery of ["Docker is not installed", "Docker is installed but not running", "Port 8000 or 5173 is busy", "Backend is unreachable", "Frontend is unreachable", "Project path is wrong", "Approved scripts are missing or altered", "Release mismatch", "Migrations are pending", "SmartScreen warns about the installer"]) {
    assert.ok(external.includes(recovery), `Missing recovery guidance: ${recovery}`);
  }
  assert.doesNotMatch(external, /Stop-Process|taskkill|Set-NetFirewall|Remove-Item|docker compose down --volumes/);
});

test("present desktop artifacts keep strict allowlists", async () => {
  const expected = {
    "dist-portable": ["LICENSE", "portable-manifest.json", "RavenTech OSINT Desktop.exe", "README.md"],
    "dist-installer": ["installer-manifest.json", "LICENSE", `RavenTech-OSINT-Desktop-${version}-unsigned-setup.exe`, "README.md"],
    "dist-local-release": ["KNOWN_LIMITATIONS.md", "LOCAL_STARTUP_INSTRUCTIONS.md", "local-release-manifest.json", "RavenTech OSINT Desktop.exe", `RavenTech-OSINT-Desktop-${version}-unsigned-setup.exe`, "README.md", "SHA256SUMS.txt"],
  };
  for (const [directory, allowlist] of Object.entries(expected)) {
    const root = resolve(desktop, directory, artifactRoot);
    let entries;
    try {
      entries = (await readdir(root)).sort();
    } catch (error) {
      if (error?.code === "ENOENT") continue;
      throw error;
    }
    assert.deepEqual(entries, allowlist.sort());
    for (const entry of entries) assert.equal((await stat(resolve(root, entry))).isFile(), true);
  }
});

test("desktop security boundary remains unchanged", async () => {
  const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri", "capabilities", "default.json"), "utf8"));
  const cargo = await readFile(resolve(desktop, "src-tauri", "Cargo.toml"), "utf8");
  const rust = await readFile(resolve(desktop, "src-tauri", "src", "main.rs"), "utf8");
  assert.deepEqual(capability.permissions, []);
  assert.equal(capability.remote, undefined);
  assert.doesNotMatch(cargo, /tauri-plugin-(shell|fs|updater)/i);
  const programs = [...rust.matchAll(/Command::new\(([^)]+)\)/g)].map((match) => match[1]);
  assert.deepEqual(programs, ["&powershell"]);
  for (const script of ["start_platform.ps1", "stop_platform.ps1", "restart_platform.ps1", "check_platform.ps1", "open_platform.ps1"]) {
    assert.ok(rust.includes(script));
  }
});
