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
const native = await readFile(resolve(root, "src/lib/nativeHostMetrics.ts"), "utf8");
const agents = await readFile(resolve(root, "src/components/AgentManagementPanel.tsx"), "utf8");
const lan = await readFile(resolve(root, "src/components/LanMonitoringPanel.tsx"), "utf8");

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
    "Métricas nativas del host",
    "Agente de endpoint del servidor",
    "Alternativa del contenedor Docker",
  ]) assert.ok(i18n.includes(phrase), `missing Spanish monitoring copy: ${phrase}`);
});

test("desktop host metrics take precedence and agent cadence stays manual", () => {
  assert.match(center, /const metricSource = nativePrimary\s*\? t\("Host native metrics"\)/);
  assert.match(center, /server_endpoint_agent/);
  assert.match(center, /Docker container fallback/);
  assert.match(native, /get_native_host_metrics/);
  assert.match(native, /raventech-native-host-metrics/);
  assert.match(agents, /-Mode ServerHost -BackendUrl http:\/\/localhost:8000/);
  assert.match(agents, /-Mode LanEndpoint/);
  assert.match(agents, /<ENROLLMENT_TOKEN>/);
  assert.doesNotMatch(`${native}\n${agents}`, /Command\.create|shell:|schtasks|New-Service|Startup\\/i);
});

test("real LAN acceptance status is readable without weakening safety gates", () => {
  for (const field of [
    "last_discovery_at",
    "last_service_check_at",
    "assets_total",
    "static_router_observations",
    "gateway_hint",
  ]) assert.ok(center.includes(field), `missing LAN runtime field: ${field}`);
  assert.match(center, /Disabled optional monitoring is informational, not degraded/);
  assert.match(lan, /Service-check eligible\. TCP connect only/);
  assert.match(lan, /SSH indicator/);
  assert.match(lan, /Advisory risk indicator only/);
  assert.match(lan, /Docker could not read host LAN neighbors/);
});

test("automatic LAN registration states remain local, readable, and bilingual", () => {
  for (const field of [
    "agent_self_registered",
    "host_neighbor_observations",
    "assets_needing_review",
    "last_host_neighbor_sample",
    "server_host_agent_connected",
  ]) assert.ok(`${center}\n${lan}`.includes(field), `missing automatic registration field: ${field}`);
  assert.match(activation, /auto_registration_enabled/);
  assert.match(activation, /host_neighbor_collection_enabled/);
  assert.match(agents, /self-register authorized LAN assets/);
  assert.match(lan, /Agent self-registration does not require manual asset creation/);
  for (const phrase of [
    "Registro automático de activos",
    "Observaciones de vecinos del host",
    "Activos que requieren revisión",
    "Docker no pudo leer los vecinos LAN del host",
  ]) assert.ok(i18n.includes(phrase), `missing Spanish auto-registration copy: ${phrase}`);
});

test("agent enrollment acceptance remains manual and token-secret safe", () => {
  assert.match(agents, /Endpoint enrollment acceptance/);
  assert.match(agents, /Verify the first heartbeat and connected status/);
  assert.match(agents, /Verify telemetry freshness and the 30-second reporting cadence/);
  assert.match(agents, /-Mode ServerHost -BackendUrl http:\/\/localhost:8000 -IntervalSeconds/);
  assert.match(agents, /-Mode LanEndpoint -BackendUrl \$\{commandBackendUrl\} -IntervalSeconds/);
  assert.match(agents, /<ENROLLMENT_TOKEN>/);
  assert.doesNotMatch(agents, /localStorage.*token|sessionStorage.*token|console\.log\(.*token/);
  for (const phrase of [
    "Aceptación de inscripción de endpoints",
    "Último descubrimiento",
    "Fuente de métricas del host",
  ]) assert.ok(i18n.includes(phrase), `missing Spanish acceptance copy: ${phrase}`);
});

test("controlled LAN activation is confirmed, fixed, and copy-only outside desktop", () => {
  assert.match(activation, /apply_lan_monitoring_config/);
  assert.match(activation, /\{ confirmed: true \}/);
  assert.match(activation, /window\.confirm/);
  assert.match(activation, /restart_platform/);
  assert.match(activation, /Existing secrets and unknown settings are preserved and never displayed/);
  assert.match(activation, /navigator\.clipboard\.writeText/);
  assert.match(activation, /Backup: \(\\\.env\\\.backup/);
  assert.doesNotMatch(activation, /readTextFile|writeTextFile|Command\.create|shell:/);
  for (const phrase of [
    "Activación LAN controlada",
    "Aplicar perfil LAN fijo",
    "Reiniciar y verificar",
    "Ruta del respaldo",
  ]) assert.ok(i18n.includes(phrase), `missing Spanish activation copy: ${phrase}`);
});
