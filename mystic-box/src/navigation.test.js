import assert from "node:assert/strict";
import { test } from "node:test";
import { createNavigation } from "./navigation.js";

// Navegador falso: histórico com entradas e popstate assíncrono, como o real.
function fakeWindow(start = "/", { skipGuards = false } = {}) {
  const listeners = new Set();
  const timers = [];
  const win = {
    entries: [{ url: start, state: null }],
    index: 0,
    location: { pathname: "/", search: "", hash: "" },
    addEventListener: (type, fn) => listeners.add(fn),
    removeEventListener: (type, fn) => listeners.delete(fn),
    setTimeout: (fn) => timers.push(fn),
  };

  function setLocation() {
    const url = win.entries[win.index].url;
    const [path, search = ""] = url.split("?");
    win.location.pathname = path;
    win.location.search = search ? `?${search}` : "";
  }

  function go(delta) {
    timers.push(() => {
      let target = win.index + delta;
      // Como o Chrome: o Voltar pula sentinelas criadas sem gesto do usuário.
      if (skipGuards && delta === -1) {
        while (target > 0 && win.entries[target].state?.guard) target -= 1;
      }
      target = Math.max(0, Math.min(win.entries.length - 1, target));
      if (target === win.index) return;
      win.index = target;
      setLocation();
      for (const fn of listeners) fn();
    });
  }

  win.history = {
    get state() {
      return win.entries[win.index].state;
    },
    pushState(state, _title, url) {
      win.entries = win.entries.slice(0, win.index + 1);
      win.entries.push({ url: url ?? win.entries[win.index].url, state: structuredClone(state) });
      win.index += 1;
      setLocation();
    },
    replaceState(state, _title, url) {
      win.entries[win.index] = {
        url: url ?? win.entries[win.index].url,
        state: structuredClone(state),
      };
      setLocation();
    },
    back: () => go(-1),
    go,
  };

  // Roda timers e popstates até tudo assentar.
  win.flush = () => {
    let guard = 0;
    while (timers.length > 0) {
      if ((guard += 1) > 100) throw new Error("loop");
      timers.shift()();
    }
  };
  win.back = () => {
    win.history.back();
    win.flush();
  };
  win.urls = () => win.entries.map((entry) => entry.url);

  setLocation();
  return win;
}

test("navegar empilha e o Voltar volta à tela anterior", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/arena");
  nav.navigate("/arena/duel");
  assert.equal(nav.getSnapshot().route.arena, "pvp");
  win.back();
  assert.equal(nav.getSnapshot().path, "/arena");
  win.back();
  assert.equal(nav.getSnapshot().route.screen, "home");
});

test("endereço inválido é corrigido ao abrir", () => {
  const win = fakeWindow("/nada/aqui");
  const nav = createNavigation(win);
  assert.equal(win.location.pathname, "/");
  assert.equal(nav.getSnapshot().route.screen, "home");
});

test("dados da tela viajam com a entrada", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/arena/duel/accept/c1", { data: { challenge: { challengeId: "c1" } } });
  assert.deepEqual(nav.getSnapshot().data, { challenge: { challengeId: "c1" } });
});

test("exitTo volta no histórico quando viemos de lá, senão navega", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/collection");
  nav.exitTo("/");
  win.flush();
  assert.equal(nav.getSnapshot().path, "/");
  assert.equal(win.index, 0);

  // Link direto: não há de onde voltar, então navega.
  const direct = fakeWindow("/collection");
  const nav2 = createNavigation(direct);
  nav2.exitTo("/");
  assert.equal(nav2.getSnapshot().path, "/");
  assert.deepEqual(direct.urls(), ["/collection", "/"]);
});

test("Voltar com um modal aberto fecha só o modal", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/collection");
  let open = true;
  const remove = nav.addBackHandler(() => {
    open = false;
    remove();
  });
  win.flush();
  assert.equal(win.entries.length, 3);

  win.back();
  assert.equal(open, false);
  assert.equal(nav.getSnapshot().path, "/collection");
  assert.equal(win.index, 1);

  win.back();
  assert.equal(nav.getSnapshot().path, "/");
});

test("fechar o modal pelo X tira a sentinela do histórico", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/shop");
  const remove = nav.addBackHandler(() => {});
  win.flush();
  assert.equal(win.index, 2);
  remove();
  win.flush();
  assert.equal(win.index, 1);
  assert.equal(nav.getSnapshot().path, "/shop");
});

test("modais em pilha fecham um por Voltar", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  const closed = [];
  const removers = {};
  for (const name of ["a", "b"]) {
    removers[name] = nav.addBackHandler(() => {
      closed.push(name);
      removers[name]();
    });
    win.flush();
  }
  win.back();
  assert.deepEqual(closed, ["b"]);
  win.back();
  assert.deepEqual(closed, ["b", "a"]);
  assert.equal(win.index, 0);
});

test("bloqueio segura o Voltar e avisa a tela", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/arena/battle");
  let asked = 0;
  nav.addBackHandler(() => (asked += 1), "block");
  win.flush();

  win.back();
  assert.equal(asked, 1);
  assert.equal(nav.getSnapshot().path, "/arena/battle");

  // Sair de propósito ignora o bloqueio.
  nav.exitTo("/");
  win.flush();
  assert.equal(nav.getSnapshot().path, "/");
  assert.equal(asked, 1);
});

test("modal fica acima do bloqueio", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/arena/battle");
  const events = [];
  const removeLayer = nav.addBackHandler(() => {
    events.push("layer");
    removeLayer();
  });
  nav.addBackHandler(() => events.push("block"), "block");
  win.flush();
  win.back();
  win.back();
  assert.deepEqual(events, ["layer", "block"]);
  assert.equal(nav.getSnapshot().path, "/arena/battle");
});

test("se o navegador pular a sentinela, o bloqueio devolve o histórico", () => {
  const win = fakeWindow("/", { skipGuards: true });
  const nav = createNavigation(win);
  nav.navigate("/arena/battle");
  let asked = 0;
  nav.addBackHandler(() => (asked += 1), "block");
  win.flush();
  win.back();
  assert.equal(asked, 1);
  assert.equal(nav.getSnapshot().path, "/arena/battle");
});

test("a transição recebe a tela de antes e a de depois", () => {
  const win = fakeWindow();
  const seen = [];
  const nav = createNavigation(win, {
    transition(apply, previous, next) {
      seen.push(`${previous.route.screen}->${next.route.screen}`);
      apply();
    },
  });
  let notified = 0;
  nav.subscribe(() => (notified += 1));
  nav.navigate("/arena");
  nav.navigate("/arena/grimoire");
  assert.deepEqual(seen, ["home->arena", "arena->arena"]);
  assert.equal(notified, 2);
});

test("navegar com a sentinela no topo substitui a sentinela", () => {
  const win = fakeWindow();
  const nav = createNavigation(win);
  nav.navigate("/arena/battle");
  const remove = nav.addBackHandler(() => {}, "block");
  win.flush();
  nav.navigate("/grimoire");
  remove();
  win.flush();
  assert.deepEqual(win.urls(), ["/", "/arena/battle", "/grimoire"]);
  win.back();
  assert.equal(nav.getSnapshot().path, "/arena/battle");
});
