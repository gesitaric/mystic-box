// Base dos testes de tela: API simulada, sessão de login falsa e relógio fixo.
//
// As respostas vêm de e2e/fixtures/api (gravadas do servidor local por
// e2e/fixtures/capture.mjs). Os testes não inventam dados de jogo: se uma
// tela precisar de outra resposta, grave-a com o script de captura.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test as base, expect } from "@playwright/test";
import { E2E_API_URL } from "../playwright.config.js";

const FIXTURES_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "api");

export function fixture(name) {
  return JSON.parse(readFileSync(path.join(FIXTURES_DIR, `${name}.json`), "utf8"));
}

const META = fixture("meta");
// O relógio do navegador fica no instante da captura: contagens regressivas e
// prazos devolvidos pela API saem sempre iguais.
export const FIXED_NOW = new Date(META.capturedAt);

// "MÉTODO caminho" (sem a query) -> resposta gravada.
const DEFAULT_ROUTES = {
  "GET /rules": "rules",
  "GET /world": "world",
  "POST /box/open": "box-open",
  "GET /users/me/wallet": "wallet",
  "GET /users/me/profile": "profile",
  "GET /users/me/summon-status": "summon-status",
  "GET /users/me/cards": "cards",
  "GET /users/me/relics": "relics",
  "GET /shop/listings": "shop-listings",
  "GET /users/me/campaign": "campaign",
  "GET /pvp": "pvp",
  "POST /pvp/leave": { body: {} },
  "GET /users/search": "users-search",
  "GET /battles/current": "battles-current-idle",
};

// Sessão do Cognito como a biblioteca grava no localStorage. O navegador só
// confere a validade (exp) do token; a assinatura nunca é verificada aqui.
const CLIENT_ID = "e2eclient";
const COGNITO_USER = "e2e-player";

function fakeJwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none", typ: "JWT" })}.${encode(payload)}.e2e`;
}

function sessionStorageEntries() {
  const claims = { sub: COGNITO_USER, email: "hero@mystic.test", exp: 4102444800, iat: 1700000000 };
  const prefix = `CognitoIdentityServiceProvider.${CLIENT_ID}`;
  return {
    [`${prefix}.LastAuthUser`]: COGNITO_USER,
    [`${prefix}.${COGNITO_USER}.idToken`]: fakeJwt({ ...claims, token_use: "id" }),
    [`${prefix}.${COGNITO_USER}.accessToken`]: fakeJwt({ ...claims, token_use: "access" }),
    [`${prefix}.${COGNITO_USER}.refreshToken`]: "e2e-refresh",
    [`${prefix}.${COGNITO_USER}.clockDrift`]: "0",
  };
}

class MockApi {
  constructor() {
    this.routes = { ...DEFAULT_ROUTES };
    // Pedidos sem resposta gravada (o teste pode conferir que não houve).
    this.unhandled = [];
  }

  // Troca a resposta de uma rota: nome de fixture, objeto ou { status, body }.
  set(route, response) {
    this.routes[route] = response;
  }

  resolve(method, pathname) {
    const response = this.routes[`${method} ${pathname}`];
    if (response === undefined) return null;
    if (typeof response === "string") return { status: 200, body: fixture(response) };
    if (response && "body" in response) return { status: response.status ?? 200, body: response.body };
    return { status: 200, body: response };
  }
}

export const test = base.extend({
  api: async ({ page }, use) => {
    const api = new MockApi();
    await page.route(`${E2E_API_URL}/**`, async (route) => {
      const request = route.request();
      const headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      };
      if (request.method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers });
        return;
      }
      const { pathname } = new URL(request.url());
      const response = api.resolve(request.method(), pathname);
      if (!response) {
        api.unhandled.push(`${request.method()} ${pathname}`);
        await route.fulfill({ status: 404, headers, json: { message: "Not mocked" } });
        return;
      }
      await route.fulfill({ status: response.status, headers, json: response.body });
    });
    await page.clock.setFixedTime(FIXED_NOW);
    await use(api);
  },
});

export { expect };

// Grava a sessão de login falsa antes de o jogo carregar.
export async function signIn(page) {
  await page.addInitScript((entries) => {
    for (const [key, value] of Object.entries(entries)) localStorage.setItem(key, value);
  }, sessionStorageEntries());
}

// Abre um endereço e espera a tela assentar (fontes e imagens carregadas).
export async function open(page, url) {
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState("networkidle");
  await imagesSettled(page);
}

// Espera as imagens da página carregarem e serem decodificadas. O decode é
// assíncrono (decoding="async") e, sem placa de vídeo (CI), uma imagem grande
// como o mapa-múndi ainda aparece vazia logo depois de carregar.
export async function imagesSettled(page) {
  await page.evaluate(async () => {
    const images = [...document.images].filter((image) => image.complete || image.loading !== "lazy");
    await Promise.all(
      images.map(async (image) => {
        if (!image.complete) {
          await new Promise((resolve) => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });
          });
        }
        await image.decode().catch(() => {});
      })
    );
  });
}

// Problemas de layout comuns em telas pequenas, medidos no navegador.
export async function layoutProblems(page) {
  return page.evaluate(() => {
    const problems = [];
    const width = document.documentElement.clientWidth;
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    if (scrollWidth > width + 1) {
      problems.push(`página rola para o lado: ${scrollWidth}px de conteúdo em ${width}px`);
    }
    return problems;
  });
}

// Elementos visíveis cujo retângulo passa da largura da tela (texto cortado,
// botão fora da tela ou cortado por um "overflow: hidden"). Ignora o que está
// dentro de áreas com rolagem lateral própria (carrosséis, abas).
export async function overflowingElements(page, selector) {
  return page.evaluate((selector) => {
    const width = document.documentElement.clientWidth;
    const scrollsSideways = (element) => {
      for (let node = element.parentElement; node && node !== document.body; node = node.parentElement) {
        const style = getComputedStyle(node);
        if (/(auto|scroll)/.test(style.overflowX) && node.scrollWidth > node.clientWidth) return true;
      }
      return false;
    };
    return [...document.querySelectorAll(selector)]
      .filter((element) => {
        const style = getComputedStyle(element);
        if (style.visibility === "hidden" || style.display === "none") return false;
        const box = element.getBoundingClientRect();
        if (box.width === 0 || box.height === 0) return false;
        return (box.left < -1 || box.right > width + 1) && !scrollsSideways(element);
      })
      .map((element) => {
        const box = element.getBoundingClientRect();
        const label = (element.getAttribute("aria-label") || element.textContent || "").trim().slice(0, 40);
        return `<${element.tagName.toLowerCase()} class="${element.className}"> "${label}" x=${Math.round(box.left)}..${Math.round(box.right)}`;
      });
  }, selector);
}
