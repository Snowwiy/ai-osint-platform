import assert from "node:assert/strict";
import test from "node:test";
import { resolveAiEvidenceDestination } from "../src/lib/aiEvidence.js";

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
