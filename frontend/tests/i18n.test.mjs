import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("language switcher persists en/es with English fallback", () => {
  const i18n = read("src/lib/i18n.tsx");
  const switcher = read("src/components/LanguageSwitcher.tsx");
  const shell = read("src/components/AppShell.tsx");
  const login = read("src/pages/LoginPage.tsx");

  assert.match(i18n, /LANGUAGE_STORAGE_KEY = "raventech\.language"/);
  assert.match(i18n, /spanish\[english\] \?\? english/);
  assert.match(i18n, /=== "es" \? "es" : "en"/);
  assert.match(switcher, /<option value="en">English<\/option>/);
  assert.match(switcher, /<option value="es">Español<\/option>/);
  assert.match(shell, /<LanguageSwitcher/);
  assert.match(login, /<LanguageSwitcher/);
});

test("major navigation, monitoring and recon labels have Spanish copy", () => {
  const i18n = read("src/lib/i18n.tsx");
  for (const copy of [
    '"Investigations": "Investigaciones"',
    '"Monitoring Center": "Centro de monitoreo"',
    '"Endpoint Agents": "Agentes de endpoint"',
    '"Security Posture": "Postura de seguridad"',
    '"Stored results are valid": "Los resultados almacenados son válidos"',
    '"Retry is safe": "Es seguro reintentar"',
    '"Provider timeout": "Tiempo de espera agotado del proveedor"',
    '"SSH on non-standard port": "SSH en puerto no estándar"',
  ]) assert.ok(i18n.includes(copy), `missing localized copy: ${copy}`);
  assert.doesNotMatch(i18n, />[a-z]+\.[a-z.]+</);
});

test("report forms send only supported language values and no secrets", () => {
  const types = read("src/types.ts");
  const reports = read("src/pages/ReportsPage.tsx");
  const center = read("src/pages/ReportingCenterPage.tsx");

  assert.match(types, /language\?: "en" \| "es"/);
  assert.match(reports, /language: reportLanguage/);
  assert.match(center, /language: reportLanguage/);
  assert.doesNotMatch(reports, /password|credential|secret|token/i);
  assert.doesNotMatch(center, /password|credential|secret|token/i);
});
