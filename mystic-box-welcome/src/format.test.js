import assert from "node:assert/strict";
import { test } from "node:test";
import {
  countdownParts,
  filterReleases,
  formatDate,
  formatDuration,
  noteCounts,
  stars,
} from "./format.js";

test("countdownParts divide o tempo restante", () => {
  const now = Date.parse("2026-11-12T10:00:00Z");
  assert.deepEqual(countdownParts("2026-11-16T00:00:00+00:00", now), {
    days: 3,
    hours: 14,
    minutes: 0,
    seconds: 0,
    done: false,
  });
  assert.equal(countdownParts("2026-11-01T00:00:00Z", now).done, true);
  assert.equal(countdownParts("2026-11-01T00:00:00Z", now).days, 0);
  assert.equal(countdownParts("nope", now), null);
});

test("formatDuration escreve por extenso", () => {
  assert.equal(formatDuration(3600), "1 hour");
  assert.equal(formatDuration(5400), "1 hour 30 minutes");
  assert.equal(formatDuration(45), "45 seconds");
  assert.equal(formatDuration(90061), "1 day 1 hour 1 minute");
  assert.equal(formatDuration(0), "0 seconds");
  assert.equal(formatDuration(-1), "");
});

test("formatDate não depende do fuso", () => {
  assert.equal(formatDate("2026-11-02"), "Nov 2, 2026");
  assert.equal(formatDate("bad"), "");
});

const sample = [
  { version: "2", notes: [{ type: "new" }, { type: "fixed" }] },
  { version: "1", notes: [{ type: "new" }] },
];

test("noteCounts conta por tipo", () => {
  assert.deepEqual(noteCounts(sample), { all: 3, new: 2, fixed: 1 });
});

test("filterReleases mantém só o tipo pedido", () => {
  assert.equal(filterReleases(sample, "all"), sample);
  const fixed = filterReleases(sample, "fixed");
  assert.equal(fixed.length, 1);
  assert.equal(fixed[0].version, "2");
  assert.deepEqual(fixed[0].notes, [{ type: "fixed" }]);
});

test("stars repete a estrela", () => {
  assert.equal(stars(3), "★★★");
  assert.equal(stars(undefined), "");
});
