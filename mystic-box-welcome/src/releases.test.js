import assert from "node:assert/strict";
import { test } from "node:test";
import { NOTE_TYPES, releases } from "./releases.js";

test("lançamentos do mais novo para o mais antigo, sem versão repetida", () => {
  const versions = new Set();
  for (let i = 0; i < releases.length; i += 1) {
    const release = releases[i];
    assert.match(release.date, /^\d{4}-\d{2}-\d{2}$/, release.version);
    assert.ok(!versions.has(release.version), `versão repetida: ${release.version}`);
    versions.add(release.version);
    if (i > 0) {
      assert.ok(release.date <= releases[i - 1].date, `${release.version} fora de ordem`);
    }
  }
});

test("toda nota tem tipo conhecido, título, texto e PR", () => {
  for (const release of releases) {
    assert.ok(release.name && release.tagline, release.version);
    assert.ok(release.notes.length > 0, release.version);
    for (const note of release.notes) {
      assert.ok(note.type in NOTE_TYPES, `${release.version}: tipo ${note.type}`);
      assert.ok(note.title && note.text, `${release.version}: ${note.title}`);
      assert.ok(note.prs.length > 0 && note.prs.every(Number.isInteger), note.title);
    }
  }
});
