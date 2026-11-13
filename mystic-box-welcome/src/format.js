// Formatação para exibição. Sem regras de jogo: os valores vêm da API.

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Quanto falta até `endsAt` (ISO), em dias, horas, minutos e segundos. */
export function countdownParts(endsAt, now = Date.now()) {
  const end = Date.parse(endsAt);
  if (Number.isNaN(end)) return null;
  let left = Math.max(0, end - now);
  const days = Math.floor(left / DAY);
  left -= days * DAY;
  const hours = Math.floor(left / HOUR);
  left -= hours * HOUR;
  const minutes = Math.floor(left / MINUTE);
  left -= minutes * MINUTE;
  const seconds = Math.floor(left / SECOND);
  return { days, hours, minutes, seconds, done: end <= now };
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** 3600 -> "1 hour", 5400 -> "1 hour 30 minutes", 45 -> "45 seconds". */
export function formatDuration(totalSeconds) {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return "";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const parts = [];
  if (days) parts.push(plural(days, "day"));
  if (hours) parts.push(plural(hours, "hour"));
  if (minutes) parts.push(plural(minutes, "minute"));
  if (seconds && !days && !hours) parts.push(plural(seconds, "second"));
  return parts.length ? parts.join(" ") : "0 seconds";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-11" -> "Nov 11, 2026" (sem depender do fuso de quem lê). */
export function formatDate(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate ?? "");
  if (!match) return "";
  const [, year, month, day] = match;
  return `${MONTHS[Number(month) - 1]} ${Number(day)}, ${year}`;
}

/** Quantas notas de cada tipo existem (para os filtros da lista de lançamentos). */
export function noteCounts(releases) {
  const counts = { all: 0 };
  for (const release of releases) {
    for (const note of release.notes) {
      counts.all += 1;
      counts[note.type] = (counts[note.type] ?? 0) + 1;
    }
  }
  return counts;
}

/** Só as notas do tipo pedido; lançamentos sem nenhuma somem. */
export function filterReleases(releases, type) {
  if (!type || type === "all") return releases;
  return releases
    .map((release) => ({ ...release, notes: release.notes.filter((note) => note.type === type) }))
    .filter((release) => release.notes.length > 0);
}

/** "★★★★★" para a raridade devolvida pela API. */
export function stars(rarity) {
  return "★".repeat(Math.max(0, Number(rarity) || 0));
}
