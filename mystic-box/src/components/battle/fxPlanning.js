// Efeitos visuais da batalha. Só apresentação: tudo sai dos eventos que a API
// devolveu (quem agiu, em quem, dano físico ou mágico, crítico...). Nenhuma
// regra do jogo fica aqui.

const FX_KEY = "mystic-box:battle-fx";

// "full": partículas, projéteis e tremor. "lite": só o essencial (mais leve
// para o aparelho). Quem pede menos movimento no sistema começa no "lite".
export function readFxPreference() {
  try {
    const stored = localStorage.getItem(FX_KEY);
    if (stored === "full" || stored === "lite") return stored;
  } catch {
    // Sem armazenamento local: usa o padrão.
  }
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return "lite";
  } catch {
    // Sem matchMedia: segue no padrão.
  }
  return "full";
}

export function storeFxPreference(mode) {
  try {
    localStorage.setItem(FX_KEY, mode);
  } catch {
    // Sem armazenamento local: vale só nesta visita.
  }
}

// Quanto tempo (ms) cada efeito fica na tela. As animações no CSS usam o mesmo
// tempo (variável --fx-ms), então o elemento sai quando a animação acaba.
export const FX_MS = {
  cast: 760,
  banner: 1150,
  projectile: 420,
  beam: 460,
  slash: 460,
  burst: 620,
  heal: 820,
  shield: 640,
  buff: 720,
  debuff: 720,
  stun: 900,
  shatter: 900,
  revive: 1000,
  round: 1100,
  surge: 1200,
  turn: 1300,
  flash: 260,
  link: 900,
};

// Máximo de efeitos ao mesmo tempo (os mais antigos saem antes).
export const MAX_FX = 28;

// Olha os eventos que a habilidade causou (até a próxima vez ou habilidade)
// para decidir o que lançar em cada alvo: golpe físico, magia ou apoio.
export function planSkill(events, index) {
  const skill = events[index];
  const hits = {};
  for (let i = index + 1; i < events.length; i += 1) {
    const event = events[i];
    if (["skill", "turn", "round", "duo", "end", "companion"].includes(event.type)) break;
    if (event.type === "damage" && event.source === skill.actor && !event.status) {
      hits[event.target] = hits[event.target] ?? event.kind ?? "physical";
    } else if (["heal", "revive", "status", "cleanse"].includes(event.type)) {
      hits[event.target] = hits[event.target] ?? "support";
    }
  }
  return (skill.targets ?? [])
    .filter((target) => target !== skill.actor)
    .map((target) => ({ target, kind: hits[target] ?? "support" }));
}

// Centro da arte de uma carta na tela (ou null se ela não estiver lá).
export function unitPoint(unitId) {
  if (typeof document === "undefined") return null;
  const node = document.querySelector(`[data-unit-id="${CSS.escape(unitId)}"] .battle-unit-art`);
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return null;
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

// Linha do meio do campo, entre os dois times (faixas de habilidade, rodada,
// maré e vez do jogador). Sem as fileiras na tela, o centro do campo.
export function fieldPoint() {
  if (typeof document === "undefined") return null;
  const foes = document.querySelector(".battle-row.is-enemy")?.getBoundingClientRect();
  const allies = document.querySelector(".battle-row.is-player")?.getBoundingClientRect();
  if (foes && allies && foes.width > 0) {
    return {
      x: (foes.left + foes.right) / 2,
      y: (foes.bottom + allies.top) / 2,
      width: foes.width,
    };
  }
  const node = document.querySelector(".battle-field");
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width };
}
