import assert from "node:assert/strict";
import { test } from "node:test";
import { formatRoute, needsSession, parseLocation, withOverlay } from "./routes.js";

function parse(url) {
  const [pathname, search = ""] = url.split("?");
  return parseLocation(pathname, search ? `?${search}` : "");
}

test("os endereços conhecidos voltam iguais depois de lidos", () => {
  const urls = [
    "/",
    "/summon",
    "/arena",
    "/arena/campaign",
    "/arena/campaign/riftheart",
    "/arena/campaign/riftheart/3",
    "/arena/duel",
    "/arena/duel/challenge",
    "/arena/duel/challenge?vs=Lyra+Star",
    "/arena/duel/accept/abc-123",
    "/arena/battle",
    "/collection",
    "/shop",
    "/shop/sell",
    "/shop/mine",
    "/players",
    "/players/titles",
    "/players/search",
    "/world",
    "/world/chronicle",
    "/world/riftheart",
    "/grimoire",
    "/grimoire/battle",
    "/arena/grimoire/battle",
    "/arena/battle/grimoire/battle",
    "/summon/grimoire",
  ];
  for (const url of urls) {
    const route = parse(url);
    assert.equal(route.known, true, url);
    assert.equal(formatRoute(route), url, url);
  }
});

test("lê tela, aba e painel", () => {
  assert.deepEqual(parse("/arena/campaign/riftheart/2"), {
    screen: "arena",
    arena: "campaign",
    region: "riftheart",
    stage: 2,
    overlay: null,
    known: true,
  });
  assert.deepEqual(parse("/arena/duel/challenge?vs=%20Lyra%20").vs, "Lyra");
  assert.deepEqual(parse("/shop/sell").overlay, { name: "shop", tab: "sell" });
  assert.deepEqual(parse("/world/riftheart").overlay, {
    name: "world",
    tab: "map",
    region: "riftheart",
  });
  const grimoire = parse("/arena/battle/grimoire/battle");
  assert.equal(grimoire.arena, "battle");
  assert.deepEqual(grimoire.overlay, { name: "grimoire", chapter: "battle" });
});

test("endereço desconhecido vira o início", () => {
  for (const url of [
    "/nada",
    "/arena/nada",
    "/arena/campaign/riftheart/0",
    "/arena/campaign/riftheart/02",
    "/arena/campaign/a/1/2",
    "/arena/duel/accept",
    "/arena/battle/x",
    "/summon/x",
    "/%E0%A4%A",
  ]) {
    const route = parse(url);
    assert.equal(route.known, false, url);
    assert.equal(route.screen, "home", url);
  }
});

test("painel desconhecido mantém a tela e fecha o painel", () => {
  const route = parse("/arena/duel/shop/nada");
  assert.equal(route.known, false);
  assert.equal(route.arena, "pvp");
  assert.equal(route.overlay, null);
  assert.equal(parse("/grimoire/nada").known, false);
  assert.equal(parse("/collection/x").known, false);
});

test("abre e fecha painéis sobre a tela atual", () => {
  const arena = parse("/arena/campaign/riftheart");
  assert.equal(withOverlay(arena, { name: "grimoire", chapter: "battle" }), "/arena/campaign/riftheart/grimoire/battle");
  assert.equal(withOverlay(parse("/collection"), null), "/");
});

test("diz quais endereços precisam de login", () => {
  assert.equal(needsSession(parse("/")), false);
  assert.equal(needsSession(parse("/summon")), false);
  assert.equal(needsSession(parse("/grimoire")), false);
  assert.equal(needsSession(parse("/arena")), true);
  assert.equal(needsSession(parse("/collection")), true);
  assert.equal(needsSession(parse("/world")), true);
});
