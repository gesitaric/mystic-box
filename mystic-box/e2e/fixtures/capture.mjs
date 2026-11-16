// Gera as respostas fixas da API usadas nos testes de tela (e2e/fixtures/api).
//
// Roda contra o servidor local (mystic-box-back/local/dev_server.py), que não
// confere a assinatura do token do Cognito: os jogadores de teste são tokens
// falsos com `sub` próprio. Nada aqui acessa a AWS.
//
// Os dados são sempre do servidor: este script só faz pedidos e salva as
// respostas. Nenhuma regra de jogo é escrita aqui.
//
// Uso (a partir de mystic-box/), com um servidor local numa porta separada:
//   1. API sem tempo de espera, para sortear várias vezes:
//        $env:SUMMON_COOLDOWN_SECONDS="0"; .\.venv\Scripts\python.exe local\dev_server.py --port 3100
//      node e2e/fixtures/capture.mjs seed
//   2. Reinicie a API sem SUMMON_COOLDOWN_SECONDS (as regras gravadas saem
//      com o tempo de espera real) e rode:
//      node e2e/fixtures/capture.mjs market   (uma vez: pedidos e vendas)
//      node e2e/fixtures/capture.mjs capture
//
// API_URL muda o endereço (padrão http://localhost:3100).

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const API_URL = (process.env.API_URL ?? "http://localhost:3100").replace(/\/$/, "");
const OUT_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "api");

export const PLAYER = { sub: "e2e-player", email: "hero@mystic.test", username: "Seraphine" };
export const RIVAL = { sub: "e2e-rival", email: "rival@mystic.test", username: "Morwen" };

const PLAYER_SUMMONS = 15;
const RIVAL_SUMMONS = 8;

// JWT sem assinatura: o servidor local só lê `sub`, `exp` e `token_use`.
export function fakeIdToken({ sub, email }) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return [
    encode({ alg: "none", typ: "JWT" }),
    encode({ sub, email, token_use: "id", exp: 4102444800, iat: 1700000000 }),
    "e2e",
  ].join(".");
}

async function api(user, method, route, body) {
  const response = await fetch(`${API_URL}${route}`, {
    method,
    headers: {
      ...(user ? { Authorization: fakeIdToken(user) } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`${method} ${route} -> ${response.status}: ${JSON.stringify(data)}`);
  }
  return data;
}

async function summonMany(user, times) {
  for (let i = 0; i < times; i += 1) {
    const { summonToken } = await api(null, "POST", "/box/open");
    await api(user, "POST", "/users/me/cards", { summonToken });
  }
}

async function ensureUsername(user) {
  const profile = await api(user, "GET", "/users/me/profile");
  if (profile.username !== user.username) {
    await api(user, "POST", "/users/me/username", { username: user.username });
  }
}

// Anuncia uma cópia de algumas cartas pelo menor preço aceito pelo servidor.
async function listSome(user, count) {
  const { cards } = await api(user, "GET", "/users/me/cards?sort=rarity&order=desc");
  for (const card of cards.slice(0, count)) {
    await api(user, "POST", "/shop/listings", {
      fileName: card.file_name ?? card.fileName,
      quantity: 1,
      price: card.listingPriceRange.min,
    });
  }
}

async function balanceOf(user) {
  return (await api(user, "GET", "/users/me/wallet")).balance ?? 0;
}

// Fragmentos só vêm de jogar: batalhas no automático contra o computador até o
// saldo chegar em `target` (subir de nível dá Fragmentos).
async function earnShards(user, target) {
  for (let battles = 0; (await balanceOf(user)) < target; battles += 1) {
    if (battles > 60) throw new Error(`${user.username} could not earn ${target} shards.`);
    const current = await api(user, "GET", "/battles/current");
    if (current.battle) {
      await api(user, "POST", "/battles/current/actions", {
        battleId: current.battle.battleId,
        type: "forfeit",
      });
    }
    const { cards } = await api(user, "GET", "/users/me/cards?sort=rarity&order=desc");
    const team = cards.slice(0, current.teamSize ?? 3).map((card) => card.file_name);
    let { battle } = await api(user, "POST", "/battles", { team, difficulty: "novice" });
    while (battle.status === "active") {
      ({ battle } = await api(user, "POST", "/battles/current/actions", {
        battleId: battle.battleId,
        type: "auto",
      }));
    }
  }
}

// Pedido pelo menor preço aceito; o servidor recusa (409) se já houver uma
// cópia à venda por esse preço, e aí a carta fica sem pedido.
async function requestCard(user, option) {
  try {
    return await api(user, "POST", "/shop/orders", {
      fileName: option.file_name,
      price: option.priceRange.min,
    });
  } catch (error) {
    console.warn(`  sem pedido de ${option.name}: ${error.message}`);
    return null;
  }
}

// Mercado com pedidos e vendas: o rival compra um anúncio do jogador e pede
// cartas (algumas o jogador tem), o jogador atende um pedido e pede uma carta.
async function seedMarket() {
  const shop = await api(RIVAL, "GET", "/shop/listings");
  const playerListing = shop.cards[0];
  await earnShards(RIVAL, (playerListing?.price ?? 0) + 200);
  if (playerListing) {
    await api(RIVAL, "POST", `/shop/listings/${playerListing.listingId}/buy`);
  }

  const { cards: playerCards } = await api(PLAYER, "GET", "/users/me/cards?sort=rarity&order=desc");
  const owned = new Set(playerCards.map((card) => card.file_name));
  const options = shop.orderOptions.filter((option) => option.rarity <= 4);
  const ownedOptions = options.filter((option) => owned.has(option.file_name));
  const missing = options.filter((option) => !owned.has(option.file_name));
  for (const option of [...ownedOptions.slice(0, 4), ...missing.slice(0, 2)]) {
    await requestCard(RIVAL, option);
  }

  const forPlayer = await api(PLAYER, "GET", "/shop/listings");
  const fillable = forPlayer.orders.find((order) => order.canFill);
  if (fillable) await api(PLAYER, "POST", `/shop/orders/${fillable.orderId}/fill`);
  const rivalOwned = new Set(
    (await api(RIVAL, "GET", "/users/me/cards")).cards.map((card) => card.file_name),
  );
  const wish = forPlayer.orderOptions.find(
    (option) => option.rarity === 3 && !owned.has(option.file_name) && !rivalOwned.has(option.file_name),
  );
  if (wish) await requestCard(PLAYER, wish);
  await listSome(PLAYER, 1);
  console.log("Mercado pronto.");
}

async function seed() {
  await ensureUsername(PLAYER);
  await ensureUsername(RIVAL);
  await summonMany(PLAYER, PLAYER_SUMMONS);
  await summonMany(RIVAL, RIVAL_SUMMONS);
  await listSome(RIVAL, 6);
  await listSome(PLAYER, 1);
  console.log("Jogadores de teste prontos.");
}

async function save(name, data) {
  await writeFile(path.join(OUT_DIR, `${name}.json`), `${JSON.stringify(data, null, 2)}\n`);
  console.log(`  ${name}.json`);
}

async function capture() {
  await mkdir(OUT_DIR, { recursive: true });
  const capturedAt = new Date().toISOString();

  await save("rules", await api(null, "GET", "/rules"));
  await save("world", await api(null, "GET", "/world"));
  // Invocar exige login. Abrir a caixa gasta o tempo de espera e deixa o
  // sorteio pendente (abrir de novo devolve o mesmo); guardar as cartas logo
  // em seguida deixa o status sem sorteio pendente, como numa sessão normal.
  const opened = await api(PLAYER, "POST", "/box/open");
  await save("box-open", opened);
  await api(PLAYER, "POST", "/users/me/cards", { summonToken: opened.summonToken });

  await save("wallet", await api(PLAYER, "GET", "/users/me/wallet"));
  await save("profile", await api(PLAYER, "GET", "/users/me/profile"));
  await save("summon-status", await api(PLAYER, "GET", "/users/me/summon-status"));
  const collection = await api(PLAYER, "GET", "/users/me/cards?sort=rarity&order=desc");
  await save("cards", collection);
  // Aba "Relic" do detalhe da primeira carta da coleção.
  const firstCard = collection.cards[0]?.file_name;
  await save(
    "relics",
    await api(PLAYER, "GET", `/users/me/relics?fileName=${encodeURIComponent(firstCard)}`),
  );
  const shop = await api(PLAYER, "GET", "/shop/listings");
  await save("shop-listings", shop);
  // Histórico de preços: a primeira carta (na ordem das opções de pedido) que
  // já teve vendas. A tela de pedidos escolhe essa carta.
  let history = null;
  for (const option of shop.orderOptions) {
    history = await api(PLAYER, "GET", `/shop/history?fileName=${encodeURIComponent(option.file_name)}`);
    if (history.summary) break;
  }
  await save("shop-history", history);
  await save("campaign", await api(PLAYER, "GET", "/users/me/campaign"));
  await save("pvp", await api(PLAYER, "GET", "/pvp"));
  await save("users-search", await api(PLAYER, "GET", `/users/search?q=${RIVAL.username.slice(0, 3)}`));

  // Batalha: sem batalha ativa e no meio de uma (depois de uma vez no automático).
  const idle = await api(PLAYER, "GET", "/battles/current");
  if (idle.battle) {
    await api(PLAYER, "POST", "/battles/current/actions", {
      battleId: idle.battle.battleId,
      type: "forfeit",
    });
  }
  await save("battles-current-idle", await api(PLAYER, "GET", "/battles/current"));

  const { cards } = await api(PLAYER, "GET", "/users/me/cards?sort=rarity&order=desc");
  const team = cards.slice(0, idle.teamSize ?? 3).map((card) => card.file_name ?? card.fileName);
  const started = await api(PLAYER, "POST", "/battles", { team, difficulty: "novice" });
  await api(PLAYER, "POST", "/battles/current/actions", {
    battleId: started.battle.battleId,
    type: "auto",
  });
  await save("battles-current-active", await api(PLAYER, "GET", "/battles/current"));
  // Desiste no fim para a próxima captura começar sem batalha.
  await api(PLAYER, "POST", "/battles/current/actions", {
    battleId: started.battle.battleId,
    type: "forfeit",
  });

  await save("meta", { capturedAt, player: PLAYER.username });
}

const command = process.argv[2];
if (command === "seed") await seed();
else if (command === "market") await seedMarket();
else if (command === "capture") await capture();
else {
  console.error("Uso: node e2e/fixtures/capture.mjs seed|market|capture");
  process.exit(1);
}
