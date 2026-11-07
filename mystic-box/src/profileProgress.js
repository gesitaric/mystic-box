// Atualiza o perfil exibido com o progresso devolvido pela batalha.
// A batalha só devolve nível e experiência; o resto do perfil (nome de
// usuário, tempo de espera da troca de nome) continua o que veio de
// GET /users/me/profile.
export function applyBattleProgress(current, progress) {
  return current ? { ...current, ...progress } : progress;
}
