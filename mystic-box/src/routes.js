// Mapa de endereços do jogo. Só apresentação: diz qual tela e qual painel
// mostrar. Os parâmetros (região, fase, desafio, nome) são identificadores que
// o servidor valida; nada de regra de jogo vem daqui.
//
//   /                                   início (sem login: portal de invocação)
//   /summon                             portal de invocação
//   /arena                              arena, contra o computador
//   /arena/campaign[/:region[/:stage]]  campanha
//   /arena/duel                         duelos online
//   /arena/duel/challenge?vs=:username  desafiar alguém
//   /arena/duel/accept/:challengeId     aceitar um desafio
//   /arena/battle                       batalha ou duelo em andamento
//
// Painéis (modais) entram no fim do endereço da tela de baixo:
//
//   /collection
//   /shop[/sell|/mine]
//   /players[/titles|/search]
//   /world[/chronicle|/:region]
//   /grimoire[/:chapter]
//
// Ex.: /arena/grimoire/battle é o Grimório aberto em cima da arena.

export const ARENA_TABS = ["pve", "campaign", "pvp"];
export const SHOP_TABS = ["buy", "sell", "mine"];
export const PLAYERS_TABS = ["name", "titles", "search"];
export const GRIMOIRE_CHAPTERS = ["start", "summon", "shop", "ascension", "battle", "progression"];

const OVERLAYS = ["collection", "shop", "players", "world", "grimoire"];
const ARENA_SEGMENTS = { campaign: "campaign", duel: "pvp", battle: "battle" };
const ID_PATTERN = /^[A-Za-z0-9_.-]{1,80}$/;

// Painéis que só fazem sentido com login (os outros são públicos).
const PRIVATE_OVERLAYS = ["collection", "shop", "players", "world"];

const HOME = Object.freeze({ screen: "home", overlay: null });

function decode(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function isId(value) {
  return typeof value === "string" && ID_PATTERN.test(value);
}

function parseOverlay(segments) {
  const [name, arg] = segments;
  if (segments.length > 2) return null;

  switch (name) {
    case "collection":
      return arg === undefined ? { name } : null;
    case "shop":
      if (arg === undefined) return { name, tab: "buy" };
      return SHOP_TABS.includes(arg) && arg !== "buy" ? { name, tab: arg } : null;
    case "players":
      if (arg === undefined) return { name, tab: "name" };
      return PLAYERS_TABS.includes(arg) && arg !== "name" ? { name, tab: arg } : null;
    case "world":
      if (arg === undefined) return { name, tab: "map", region: null };
      if (arg === "chronicle") return { name, tab: "chronicle", region: null };
      return isId(arg) ? { name, tab: "map", region: arg } : null;
    case "grimoire":
      if (arg === undefined) return { name, chapter: "start" };
      return GRIMOIRE_CHAPTERS.includes(arg) ? { name, chapter: arg } : null;
    default:
      return null;
  }
}

function parseArena(segments, params) {
  const [kind, ...rest] = segments;
  if (kind === undefined) return { screen: "arena", arena: "pve" };

  const arena = ARENA_SEGMENTS[kind];
  if (!arena) return null;

  if (arena === "battle") return rest.length === 0 ? { screen: "arena", arena } : null;

  if (arena === "campaign") {
    const [region, stage, ...extra] = rest;
    if (extra.length > 0) return null;
    if (region !== undefined && !isId(region)) return null;
    let stageNumber = null;
    if (stage !== undefined) {
      stageNumber = Number(stage);
      if (!Number.isInteger(stageNumber) || stageNumber < 1 || String(stageNumber) !== stage) {
        return null;
      }
    }
    return { screen: "arena", arena, region: region ?? null, stage: stageNumber };
  }

  // Duelo online.
  const [view, id, ...extra] = rest;
  if (extra.length > 0) return null;
  if (view === undefined) return { screen: "arena", arena, duel: "list" };
  if (view === "challenge" && id === undefined) {
    const vs = params.get("vs");
    return { screen: "arena", arena, duel: "challenge", vs: vs && vs.trim() ? vs.trim() : null };
  }
  if (view === "accept" && isId(id)) {
    return { screen: "arena", arena, duel: "accept", challengeId: id };
  }
  return null;
}

// Endereço -> rota. Endereço desconhecido vira o início; `known` diz se o
// endereço era válido (para corrigir a barra de endereço).
export function parseLocation(pathname = "/", search = "") {
  const segments = [];
  for (const raw of pathname.split("/")) {
    if (!raw) continue;
    const segment = decode(raw);
    if (segment === null) return { ...HOME, known: false };
    segments.push(segment);
  }
  const params = new URLSearchParams(search);

  const overlayAt = segments.findIndex((segment) => OVERLAYS.includes(segment));
  const screenSegments = overlayAt === -1 ? segments : segments.slice(0, overlayAt);
  const overlaySegments = overlayAt === -1 ? [] : segments.slice(overlayAt);

  let route = null;
  const [first, ...rest] = screenSegments;
  if (first === undefined) route = { screen: "home" };
  else if (first === "summon" && rest.length === 0) route = { screen: "summon" };
  else if (first === "arena") route = parseArena(rest, params);

  if (!route) return { ...HOME, known: false };

  let overlay = null;
  if (overlaySegments.length > 0) {
    overlay = parseOverlay(overlaySegments);
    if (!overlay) return { ...route, overlay: null, known: false };
  }

  return { ...route, overlay, known: true };
}

function arenaPath(route) {
  switch (route.arena) {
    case "battle":
      return "/arena/battle";
    case "campaign": {
      let path = "/arena/campaign";
      if (route.region) {
        path += `/${encodeURIComponent(route.region)}`;
        if (route.stage) path += `/${route.stage}`;
      }
      return path;
    }
    case "pvp":
      if (route.duel === "challenge") return "/arena/duel/challenge";
      if (route.duel === "accept" && route.challengeId) {
        return `/arena/duel/accept/${encodeURIComponent(route.challengeId)}`;
      }
      return "/arena/duel";
    default:
      return "/arena";
  }
}

function overlayPath(overlay) {
  if (!overlay) return "";
  switch (overlay.name) {
    case "shop":
      return overlay.tab && overlay.tab !== "buy" ? `/shop/${overlay.tab}` : "/shop";
    case "players":
      return overlay.tab && overlay.tab !== "name" ? `/players/${overlay.tab}` : "/players";
    case "world":
      if (overlay.tab === "chronicle") return "/world/chronicle";
      return overlay.region ? `/world/${encodeURIComponent(overlay.region)}` : "/world";
    case "grimoire":
      return overlay.chapter && overlay.chapter !== "start"
        ? `/grimoire/${overlay.chapter}`
        : "/grimoire";
    default:
      return `/${overlay.name}`;
  }
}

// Rota -> endereço (caminho + busca).
export function formatRoute(route) {
  let screen = "";
  if (route.screen === "summon") screen = "/summon";
  else if (route.screen === "arena") screen = arenaPath(route);

  const path = `${screen}${overlayPath(route.overlay)}` || "/";
  const query =
    route.screen === "arena" && route.arena === "pvp" && route.duel === "challenge" && route.vs
      ? `?${new URLSearchParams({ vs: route.vs })}`
      : "";
  return `${path}${query}`;
}

// Mesma tela, outro painel (null fecha o painel).
export function withOverlay(route, overlay) {
  return formatRoute({ ...route, overlay });
}

export function needsSession(route) {
  return route.screen === "arena" || PRIVATE_OVERLAYS.includes(route.overlay?.name);
}

// Nome da aba do navegador.
export function routeTitle(route) {
  const overlayTitles = {
    collection: "Collection",
    shop: "Shop",
    players: "Players",
    world: "World map",
    grimoire: "Grimoire",
  };
  if (route.overlay) return overlayTitles[route.overlay.name];
  if (route.screen === "summon") return "Summon";
  if (route.screen === "arena") {
    if (route.arena === "battle") return "Battle";
    if (route.arena === "campaign") return "Campaign";
    if (route.arena === "pvp") return "Online duel";
    return "Arena";
  }
  return null;
}
