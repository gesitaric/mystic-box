// Telas conferidas em cada tamanho. `ready` é algo que só aparece quando a
// tela terminou de carregar os dados da API; `setup` troca respostas da API.

import { fixture } from "./support.js";

const FIRST_CARD = fixture("cards").cards[0].name;

export const SCREENS = [
  {
    name: "summon-signed-out",
    path: "/",
    signedIn: false,
    ready: (page) => page.getByRole("button", { name: "Sign in" }),
  },
  {
    name: "home",
    path: "/",
    ready: (page) => page.getByText("Seraphine").first(),
  },
  {
    name: "summon",
    path: "/summon",
    ready: (page) => page.getByRole("button", { name: "← Home" }),
  },
  {
    name: "summon-reveal",
    path: "/summon",
    // Sorteio ainda não guardado: o jogo mostra as cartas já viradas.
    setup: async (api, page) => {
      const summon = fixture("box-open");
      await page.addInitScript((value) => {
        localStorage.setItem("mystic-box:pending-summon", JSON.stringify(value));
      }, summon);
      api.set("POST /users/me/cards", { status: 200, body: { retryAfterSeconds: 3600 } });
    },
    ready: (page) => page.getByText("Cards added to your collection"),
  },
  {
    name: "collection",
    path: "/collection",
    ready: (page) => page.locator(".auth-modal").getByRole("img", { name: FIRST_CARD }).first(),
  },
  {
    name: "shop-buy",
    path: "/shop",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "shop-sell",
    path: "/shop/sell",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "shop-mine",
    path: "/shop/mine",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "players-profile",
    path: "/players",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "players-titles",
    path: "/players/titles",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "world-map",
    path: "/world",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "world-region",
    path: "/world/riftheart",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "world-chronicle",
    path: "/world/chronicle",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "grimoire",
    path: "/grimoire",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "grimoire-battle",
    path: "/grimoire/battle",
    ready: (page) => page.locator(".auth-modal"),
  },
  {
    name: "arena-setup",
    path: "/arena",
    ready: (page) => page.locator("[aria-label='Battle setup']"),
  },
  {
    name: "arena-campaign",
    path: "/arena/campaign",
    ready: (page) => page.locator("[aria-label='Battle setup']"),
  },
  {
    name: "arena-duel",
    path: "/arena/duel",
    ready: (page) => page.locator("[aria-label='Battle setup']"),
  },
  {
    name: "battle",
    path: "/arena/battle",
    setup: async (api) => api.set("GET /battles/current", "battles-current-active"),
    ready: (page) => page.locator(".battle-screen.is-arena .battle-field"),
  },
];

