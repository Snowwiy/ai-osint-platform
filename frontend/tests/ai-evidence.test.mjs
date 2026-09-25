import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveAiEvidenceDestination } from "../src/lib/aiEvidence.js";

const testDirectory = dirname(fileURLToPath(import.meta.url));
const panelSource = readFileSync(
  resolve(testDirectory, "../src/components/EvidenceAnalysisPanel.tsx"),
  "utf8",
);
const apiSource = readFileSync(resolve(testDirectory, "../src/lib/api.ts"), "utf8");
const spanishSource = readFileSync(resolve(testDirectory, "../src/lib/i18n.tsx"), "utf8");
const panelLocaleKeys = new Set([
  ...[...panelSource.matchAll(/\bt\("([^"]+)"\)/g)].map((match) => match[1]),
  ...[...panelSource.matchAll(/label: "([^"]+)"/g)].map((match) => match[1]),
  ...[...panelSource.matchAll(/title="([^"]+)"/g)].map((match) => match[1]),
]);

const investigationId = "11111111-1111-4111-8111-111111111111";

test("evidence links resolve to fixed RavenTech source pages", () => {
  assert.equal(
    resolveAiEvidenceDestination(`INVESTIGATION:${investigationId}`),
    `/investigations/${investigationId}`,
  );
  assert.equal(
    resolveAiEvidenceDestination("FINDING:fixture", { investigation_id: investigationId }),
    `/investigations/${investigationId}/findings`,
  );
  assert.equal(
    resolveAiEvidenceDestination("TIMELINE:fixture", { investigation_id: investigationId }),
    `/investigations/${investigationId}/timeline`,
  );
  assert.equal(resolveAiEvidenceDestination("ALERT:fixture"), "/notifications");
  assert.equal(resolveAiEvidenceDestination("KNOWLEDGE:fixture"), "/knowledge");
  assert.equal(resolveAiEvidenceDestination("HOST-METRIC:fixture"), "/monitoring");
});

test("evidence links reject unknown types and untrusted path identifiers", () => {
  assert.equal(resolveAiEvidenceDestination("shell:run"), null);
  assert.equal(resolveAiEvidenceDestination("INVESTIGATION:../../admin"), null);
  assert.equal(
    resolveAiEvidenceDestination("FINDING:fixture", { investigation_id: "../../admin" }),
    "/investigations",
  );
  assert.equal(resolveAiEvidenceDestination("not-an-evidence-reference"), null);
});

test("analysis panel exposes bounded read-only workflows and saved comparisons", () => {
  for (const workflow of [
    '"host_current"', '"host_changes"', '"host_resource"', '"host_services"',
    '"host_ports"', '"lan_current"', '"lan_changes"', '"asset_current"',
    '"alert_context"', '"posture_context"', '"investigation_context"',
  ]) {
    assert.ok(panelSource.includes(workflow), `missing workflow ${workflow}`);
  }
  assert.ok(panelSource.includes("listEvidenceAnalyses"));
  assert.ok(panelSource.includes("rerunEvidenceAnalysis"));
  assert.ok(panelSource.includes("compareEvidenceAnalyses"));
  assert.ok(panelSource.includes("safeInventory"));
  assert.ok(panelSource.includes("No model required"));
  assert.ok(panelSource.includes("Data gaps and uncertainty"));
  assert.ok(!panelSource.includes("command_line"));
  assert.ok(!panelSource.includes("environment_variables"));
});

test("analysis API and key evidence labels have Spanish localization", () => {
  assert.ok(apiSource.includes("/ai/analysis/run"));
  assert.ok(apiSource.includes("/ai/analysis/compare"));
  for (const entry of [
    '"Evidence analysis": "Análisis de evidencia"',
    '"Analyze Server": "Analizar servidor"',
    '"What Changed": "Qué cambió"',
    '"Data gaps and uncertainty": "Vacíos de datos e incertidumbre"',
    '"Hypotheses": "Hipótesis"',
    '"insufficient": "insuficiente"',
    '"rising": "ascendente"',
    '"falling": "descendente"',
    '"stable": "estable"',
  ]) {
    assert.ok(spanishSource.includes(entry), `missing Spanish entry ${entry}`);
  }
  for (const label of panelLocaleKeys) {
    assert.ok(spanishSource.includes(`"${label}":`), `missing Spanish key ${label}`);
  }
});
