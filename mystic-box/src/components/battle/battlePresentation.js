// Só apresentação: ícones, cores e textos do registro da batalha.
// Nenhuma regra do jogo fica aqui; tudo vem calculado da API.

export const ELEMENT_STYLE = {
  ember: { icon: "🔥", color: "#ff8a4c" },
  tide: { icon: "🌊", color: "#5cc0ff" },
  gale: { icon: "🌪️", color: "#7fe6c8" },
  terra: { icon: "⛰️", color: "#d6ad6e" },
  volt: { icon: "⚡", color: "#8fa2ff" },
  lumen: { icon: "☀️", color: "#ffe27a" },
  umbra: { icon: "🌑", color: "#b48cff" },
};

export const STATUS_ICON = {
  burn: "🔥",
  stun: "💫",
  weaken: "🥀",
  expose: "🎯",
  slow: "🐌",
  shield: "🛡️",
  taunt: "📣",
  regen: "✚",
  empower: "⚔️",
  guard: "◈",
  companion: "🐾",
};

export const STAT_LABELS = [
  ["vitality", "VIT"],
  ["might", "MIG"],
  ["arcana", "ARC"],
  ["bulwark", "BUL"],
  ["resolve", "RES"],
  ["celerity", "CEL"],
  ["fate", "FATE"],
];

export const STAT_NAMES = {
  vitality: "Vitality (health)",
  might: "Might (physical power)",
  arcana: "Arcana (magical power and healing)",
  bulwark: "Bulwark (physical defense)",
  resolve: "Resolve (magical defense)",
  celerity: "Celerity (turn order)",
  fate: "Fate (critical hit chance %)",
};

export const TARGET_LABELS = {
  enemy: "One foe",
  all_enemies: "All foes",
  ally: "One ally",
  all_allies: "All allies",
  self: "Self",
  fallen_ally: "Fallen ally",
};

export const END_REASON_TEXT = {
  victory: "Every foe has fallen.",
  defeat: "Your whole team has fallen.",
  forfeit: "You fled the battle.",
  timeout: "The battle dragged on for too long.",
  opponent_forfeit: "Your rival fled the duel.",
  abandon: "You missed too many turns and abandoned the duel.",
  opponent_abandon: "Your rival stopped playing and abandoned the duel.",
};

// Fim do duelo para quem assiste: o servidor diz quem venceu, quem perdeu e
// por quê ("victory"/"defeat" são vistos do lado de quem desafiou).
export function spectatorEndText({ winner, loser, reason }) {
  switch (reason) {
    case "victory":
    case "defeat":
      return `${loser}'s whole team has fallen.`;
    case "forfeit":
      return `${loser} fled the duel.`;
    case "abandon":
      return `${loser} stopped playing and abandoned the duel.`;
    case "timeout":
      return "The duel dragged on for too long.";
    default:
      return winner ? `${winner} won the duel.` : "";
  }
}

const STATUS_NAMES = {
  burn: "Burn",
  stun: "Stun",
  weaken: "Weaken",
  expose: "Expose",
  slow: "Slow",
  shield: "Shield",
  taunt: "Taunt",
  regen: "Regen",
  empower: "Empower",
  guard: "Guard",
  companion: "Companion",
};

// Texto do registro para um evento devolvido pela API (ou null para não mostrar).
export function describeEvent(event, names) {
  const name = (id) => names[id] ?? "???";

  switch (event.type) {
    case "round":
      return { text: `— Round ${event.round} —`, kind: "round" };
    case "surge":
      return {
        text:
          event.healPenaltyPercent >= 100
            ? `🌊 The Aether surges: damage +${event.damageBonusPercent}%, healing is gone.`
            : `🌊 The Aether surges: damage +${event.damageBonusPercent}%, healing −${event.healPenaltyPercent}%.`,
        kind: "surge",
      };
    case "skill":
      return { text: `${name(event.actor)} uses ${event.skillName}.`, kind: "skill", side: event.actor?.[0] };
    case "damage": {
      if (event.status === "burn") {
        return { text: `${name(event.target)} burns for ${event.amount}.`, kind: "damage" };
      }
      const notes = [
        event.critical && "critical",
        event.effectiveness === "strong" && "super effective",
        event.effectiveness === "weak" && "resisted",
        event.absorbed > 0 && `${event.absorbed} absorbed`,
        event.rival && "rivalry",
      ].filter(Boolean);
      const verb = event.chain ? "is struck by arcing lightning for" : "takes";
      return {
        text: `${name(event.target)} ${verb} ${event.amount} damage${notes.length ? ` (${notes.join(", ")})` : ""}.`,
        kind: "damage",
      };
    }
    case "heal":
      if (event.amount <= 0) return null;
      return { text: `${name(event.target)} recovers ${event.amount}.`, kind: "heal" };
    case "status":
      return { text: `${name(event.target)}: ${STATUS_NAMES[event.status] ?? event.status}.`, kind: "status" };
    case "cleanse":
      return { text: `${name(event.target)} is cleansed.`, kind: "heal" };
    case "revive":
      return { text: `${name(event.target)} returns to the fight!`, kind: "heal" };
    case "defeated":
      return { text: `${name(event.target)} has fallen.`, kind: "defeat" };
    case "bond":
      return {
        text: `♥ ${name(event.actor)} & ${name(event.target)}: “${event.line}” — “${event.reply}”`,
        kind: "bond",
      };
    case "omen":
      return {
        text: `☾ ${event.title}: ${event.targets.map(name).join(", ")} carry the omen (+${event.bonusPercent}% XP).`,
        kind: "resonance",
      };
    case "resonance":
      return {
        text: `✦ ${event.regionName} resonance — ${event.name}: ${event.description}`,
        kind: "resonance",
      };
    case "relic":
      return {
        text: `◈ ${name(event.target)}'s ${event.name} awakens: ${event.description}`,
        kind: "resonance",
      };
    case "duo":
      return {
        text: `✦✦ ${name(event.actor)} and ${name(event.target)} unleash ${event.skillName}!`,
        kind: "duo",
        side: event.actor?.[0],
      };
    case "lastWords":
      return { text: `${name(event.target)}: “${event.line}”`, kind: "lastWords" };
    case "bondTorn":
      return {
        text: `💔 ${name(event.actor)} faces ${name(event.target)}: “${event.line}” — “${event.reply}”`,
        kind: "bond",
      };
    case "rivalry":
      return {
        text: `⚔ ${name(event.actor)} vs ${name(event.target)}: “${event.line}” — “${event.reply}”`,
        kind: "rivalry",
      };
    case "bondGrief":
      return { text: `♥ ${name(event.target)} fights on for ${name(event.source)}!`, kind: "bond" };
    case "stunned":
      return { text: `${name(event.target)} is stunned and loses the turn.`, kind: "status" };
    case "aether":
      return { text: `${name(event.source)} steals ${event.amount} Aether.`, kind: "status" };
    case "companion":
      return { text: `${name(event.actor)}'s companion lunges at ${name(event.target)}.`, kind: "skill", side: event.actor?.[0] };
    case "timeout":
      return { text: `${name(event.target)} ran out of time and acts on its own.`, kind: "status" };
    case "end":
      if (event.result === "draw") return { text: "Draw.", kind: "round" };
      return {
        text: event.result === "won" ? "Victory!" : "Defeat.",
        kind: event.result === "won" ? "heal" : "defeat",
      };
    default:
      return null;
  }
}

// Quanto tempo (ms) cada evento fica na tela antes do próximo.
export function eventDelay(event) {
  switch (event.type) {
    case "skill":
      return 650;
    case "damage":
      return 420;
    case "heal":
      return event.amount > 0 ? 380 : 0;
    case "resonance":
    case "omen":
      return 1800;
    case "relic":
      return 1200;
    case "duo":
      return 900;
    case "surge":
      return 700;
    case "lastWords":
      return 2000;
    case "bond":
    case "bondTorn":
    case "rivalry":
      return 2200;
    case "bondGrief":
      return 700;
    case "defeated":
    case "revive":
    case "stunned":
      return 520;
    case "round":
      return 380;
    case "aether":
      return 320;
    case "companion":
      return 450;
    case "timeout":
      return 450;
    case "status":
    case "cleanse":
      return 170;
    case "turn":
      return 140;
    default:
      return 0;
  }
}
