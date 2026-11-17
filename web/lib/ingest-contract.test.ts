import assert from "node:assert/strict";
import test from "node:test";
import { parseIngestBody, rateDecision } from "./ingest-contract.ts";

test("a single reading is accepted and measured by default", () => {
  const parsed = parseIngestBody({
    timestamp: "2026-11-17T10:00:00+05:30",
    pv_kw: 1.2,
    consumption_kw: 0.4,
  });
  assert.equal(parsed.ok, true);
  if (!parsed.ok) return;
  assert.equal(parsed.readings.length, 1);
  assert.equal(parsed.readings[0].data_label, "MEASURED");
  assert.equal(parsed.readings[0].is_simulated, false);
  assert.equal(parsed.readings[0].pv_kw, 1.2);
});

test("simulated rows must say so", () => {
  const bad = parseIngestBody({
    timestamp: "2026-11-17T10:00:00Z",
    pv_kw: 1,
    is_simulated: true,
    data_label: "MEASURED",
  });
  assert.equal(bad.ok, false);
});

test("negative power and an empty batch are rejected", () => {
  assert.equal(parseIngestBody({ timestamp: "2026-11-17T10:00:00Z", pv_kw: -1 }).ok, false);
  assert.equal(parseIngestBody({ readings: [] }).ok, false);
  assert.equal(parseIngestBody({ timestamp: "not-a-time", pv_kw: 1 }).ok, false);
});

test("the same timestamp can be sent again", () => {
  const body = { readings: [{ timestamp: "2026-11-17T10:00:00Z", export_kw: 0.2 }] };
  const first = parseIngestBody(body);
  const second = parseIngestBody(body);
  assert.equal(first.ok && second.ok, true);
  if (!first.ok || !second.ok) return;
  assert.equal(first.readings[0].timestamp, second.readings[0].timestamp);
});

test("rate limit allows 29 and stops at 30", () => {
  assert.equal(rateDecision(29), "ok");
  assert.equal(rateDecision(30), "limited");
});
