import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rust = await readFile(resolve(desktop, "src-tauri/src/main.rs"), "utf8");
const app = await readFile(resolve(desktop, "ui/app.js"), "utf8");
const html = await readFile(resolve(desktop, "ui/index.html"), "utf8");
const css = await readFile(resolve(desktop, "ui/app.css"), "utf8");

test("first-run setup is manual, bilingual, and rejects invalid repositories", () => {
  for (const text of [
    "FIRST-RUN SETUP", "CONFIGURACIÓN INICIAL", "Validate and save", "Validar y guardar",
    "That path is not a complete RavenTech repository", "La ruta no es un repositorio completo"
  ]) assert.ok(`${app}\n${html}`.includes(text), `missing setup copy: ${text}`);
  assert.match(html, /id="project-path"[^>]+type="text"[^>]+maxlength="1024"/);
  assert.doesNotMatch(html, /type="file"|webkitdirectory/);
  assert.doesNotMatch(app, /showOpenDialog|openDialog|readDir|readTextFile/);
  assert.match(rust, /let Some\(root\) = validate_repository_root\(Path::new\(value\)\) else/);
});

test("runtime checklist explains Docker, ports, release, migrations, and missing scripts", () => {
  for (const id of [
    "check-repository", "check-docker", "check-backend-port", "check-frontend-port",
    "check-release", "check-migrations", "scripts-status", "next-action"
  ]) assert.ok(html.includes(`id="${id}"`), `missing runtime item: ${id}`);
  for (const marker of ["notDetected", "backendPortConflict", "frontendPortConflict", "releaseMismatchAction", "fixMigrations", "restoreScripts"]) {
    assert.ok(app.includes(marker), `missing runtime guidance: ${marker}`);
  }
});

test("RC6 setup wizard exposes three bilingual prerequisite stages", () => {
  for (const id of ["step-project", "step-prerequisites", "step-services"]) {
    assert.ok(html.includes(`id="${id}"`), `missing wizard stage: ${id}`);
  }
  for (const text of [
    "RC6 local setup assistant", "Asistente de configuración local RC6",
    "Prerequisites", "Requisitos", "Local services", "Servicios locales",
    "Windows firewall guidance", "Guía del firewall de Windows",
    "Portable and installed builds", "Las versiones portable e instalada"
  ]) assert.ok(`${app}\n${html}`.includes(text), `missing RC6 setup guidance: ${text}`);
  assert.match(app, /renderWizard\(snapshot\)/);
  assert.match(app, /dockerAvailability !== "notDetected"/);
});

test("invalid paths and unavailable Docker retain manual guidance", () => {
  for (const marker of ["enterProjectPath", "pathRejected", "installDocker", "copyFailed"]) {
    assert.ok(app.includes(marker), `missing safe recovery state: ${marker}`);
  }
  assert.match(app, /input\.setAttribute\("aria-invalid", "true"\)/);
  assert.match(app, /nothing is installed automatically/i);
  assert.doesNotMatch(app, /docker\s+(install|start)|winget|choco|Start-Process/i);
});

test("setup UI remains bounded and command output stays sanitized", () => {
  assert.match(css, /overflow-x:\s*hidden/);
  assert.match(css, /overflow-wrap:\s*anywhere/);
  assert.match(rust, /sanitize_output/);
  assert.match(rust, /sensitive output removed/);
  assert.doesNotMatch(`${app}\n${html}`, /(api[_-]?key|access[_-]?token|password|secret)\s*[:=]/i);
});
