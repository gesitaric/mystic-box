// Chamadas à API da arena (batalha e duelo online). Sem regras de jogo:
// só envia o pedido com o token e devolve a resposta.

export class SessionExpired extends Error {}

export async function arenaRequest({ apiUrl, session, onSessionExpired }, path, init = {}) {
  const token = session.session.getIdToken().getJwtToken();
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: token,
    },
  });
  if (response.status === 401) {
    onSessionExpired();
    throw new SessionExpired();
  }
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, data };
}
