import assert from "node:assert/strict";
import { test } from "node:test";

import { applyBattleProgress } from "./profileProgress.js";

// Perfil como devolvido por GET /users/me/profile.
const profile = {
  userId: "user-123",
  username: "Merlin",
  usernameChange: { canChange: true, retryAfterSeconds: 0, nextChangeAt: null },
  usernameRules: { minLength: 3, maxLength: 20 },
  level: 2,
  experience: 10,
  wins: 1,
  losses: 0,
};

// `progress` como devolvido pelas rotas de batalha (só nível e experiência).
const battleProgress = {
  level: 3,
  experience: 0,
  experienceToNext: 160,
  maxLevel: 50,
  wins: 2,
  losses: 0,
};

test("battle progress keeps the username when the player returns home", () => {
  const updated = applyBattleProgress(profile, battleProgress);

  assert.equal(updated.username, "Merlin");
  assert.equal(updated.userId, "user-123");
  assert.deepEqual(updated.usernameChange, profile.usernameChange);
  assert.deepEqual(updated.usernameRules, profile.usernameRules);
});

test("battle progress updates level and experience", () => {
  const updated = applyBattleProgress(profile, battleProgress);

  assert.equal(updated.level, 3);
  assert.equal(updated.experience, 0);
  assert.equal(updated.wins, 2);
});

test("battle progress before the profile loads is kept as is", () => {
  assert.deepEqual(applyBattleProgress(null, battleProgress), battleProgress);
});
