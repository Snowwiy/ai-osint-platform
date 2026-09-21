import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("health badges have text, icon, accessible reason, and dark-theme contrast", () => {
  const ui = read("src/components/LocalHostPanel.tsx");
  const panel = read("src/components/LanMonitoringPanel.tsx");
  const health = read("src/lib/serviceHealth.ts");
  for (const word of ["healthy", "warning", "critical", "neutral"]) assert.match(health, new RegExp(word));
  assert.match(ui, /aria-label=.*reason/);
  assert.match(panel, /aria-label=.*advisory_reason/);
  assert.match(health, /text-emerald-200/);
  assert.match(health, /text-amber-100/);
  assert.match(health, /text-rose-100/);
});

test("service severity and filters have English and Spanish labels", () => {
  const dictionary = read("src/lib/i18n.tsx");
  for (const line of ['"healthy": "Saludable"', '"warning": "Advertencia"', '"critical": "Crítico"', '"neutral": "Neutral"', '"Expected": "Esperados"', '"Unexpected": "Inesperados"']) assert.ok(dictionary.includes(line), line);
  const panel = read("src/components/LanMonitoringPanel.tsx");
  for (const filter of ["open", "expected", "unexpected", "warning", "critical", "changed"]) assert.ok(panel.includes(filter));
});

test("service UI does not expose raw banners or command lines", () => {
  const panel = read("src/components/LanMonitoringPanel.tsx");
  assert.doesNotMatch(panel, /item\.banner_hint/);
  const local = read("src/components/LocalHostPanel.tsx");
  assert.doesNotMatch(local, /\.commandLine|\.environment|\.arguments/);
});

test("native desktop labels Redis and Celery as optional", () => {
  const panel = read("src/components/LocalHostPanel.tsx");
  const health = read("src/lib/serviceHealth.ts");
  const dictionary = read("src/lib/i18n.tsx");
  assert.match(panel, /name: "Celery", status: "optional"/);
  assert.match(panel, /name: "Redis".*"optional"/);
  assert.match(health, /!required && status === "optional"/);
  for (const label of ["Worker health", "Queue depth", "Oldest queued", "Priority"])
    assert.ok(dictionary.includes(`"${label}":`), label);
});
