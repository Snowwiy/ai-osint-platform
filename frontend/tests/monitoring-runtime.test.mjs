import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const shell = await readFile(resolve(root, "src/components/AppShell.tsx"), "utf8");
const center = await readFile(resolve(root, "src/pages/MonitoringCenterPage.tsx"), "utf8");
const activation = await readFile(resolve(root, "src/components/MonitoringActivationPanel.tsx"), "utf8");
const bootstrap = await readFile(resolve(root, "src/components/LanBootstrapPanel.tsx"), "utf8");
const api = await readFile(resolve(root, "src/lib/api.ts"), "utf8");
const i18n = await readFile(resolve(root, "src/lib/i18n.tsx"), "utf8");

test("authenticated application startup loads and safely polls monitoring summary", () => {
  assert.match(api, /request<MonitoringStartupStatus>\("\/monitoring\/startup"\)/);
  assert.match(shell, /queryKey: \["monitoring-startup"\]/);
  assert.match(shell, /Math\.max\(15, runtime\.auto_refresh_seconds\) \* 1000/);
  assert.doesNotMatch(`${shell}\n${center}`, /discoverLan\(|runLanServiceCheck\(/);
});

test("authorized LAN bootstrap remains private, guided, and non-scanning", () => {
  assert.match(bootstrap, /192\.168\.50\.1\/24/);
  assert.match(bootstrap, /192\.168\.50\.0\/24/);
  assert.match(bootstrap, /Verify LAN setup/);
  assert.match(bootstrap, /Manual router observation/);
  assert.match(bootstrap, /<ENROLLMENT_TOKEN>/);
  assert.match(api, /\/monitoring\/lan\/bootstrap\/verify/);
  assert.doesNotMatch(bootstrap, /runLanServiceCheck|discoverLan\(/);
  assert.doesNotMatch(bootstrap, /rae_[A-Za-z0-9_-]+/);
});

test("monitoring disabled states are informational and embedded mode remains independent", () => {
  assert.match(activation, /Monitoring ready, LAN discovery disabled by configuration/);
  assert.match(activation, /border-cyan-300/);
  assert.match(center, /Monitoring loaded/);
  assert.match(center, /Auto refresh active/);
  assert.doesNotMatch(`${shell}\n${center}\n${activation}`, /localhost:5173/);
});

test("new runtime states retain Spanish translations", () => {
  for (const phrase of [
    "Monitoreo cargado",
    "Actualización automática activa",
    "Descubrimiento LAN",
    "Deshabilitado por configuración",
    "La telemetría de agentes de endpoint es opcional",
    "Inicio guiado de LAN autorizada",
    "Verificar configuración LAN",
    "Observación manual del router",
  ]) assert.ok(i18n.includes(phrase), `missing Spanish monitoring copy: ${phrase}`);
});
