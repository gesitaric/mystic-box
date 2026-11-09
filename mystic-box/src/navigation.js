import { formatRoute, parseLocation } from "./routes.js";

// Histórico do navegador do jogo, sem React (testável com um `window` falso).
//
// Cada entrada do histórico guarda em `history.state`:
//   idx   posição no histórico desta visita (0 = primeira página aberta)
//   key   identifica a entrada (muda a cada navegação)
//   from  endereço da entrada anterior (para "voltar" em vez de empilhar)
//   data  dados da tela que não cabem no endereço (ex.: o desafio aberto no sininho)
//   guard entrada-sentinela (ver abaixo)
//
// Camadas e bloqueios: enquanto um modal sem endereço próprio está aberto
// ("layer") ou a tela não pode ser deixada pelo Voltar ("block"), existe uma
// entrada-sentinela com o mesmo endereço no topo do histórico. O Voltar a
// consome: uma camada fecha; um bloqueio devolve o jogador à sentinela e avisa
// a tela (ex.: perguntar se quer sair da batalha). Se o navegador pular a
// sentinela, o histórico é devolvido com `history.go`.

let keySeed = 0;

function newKey() {
  keySeed += 1;
  return `${Date.now().toString(36)}-${keySeed}`;
}

function splitPath(path) {
  const at = path.indexOf("?");
  return at === -1 ? [path, ""] : [path.slice(0, at), path.slice(at)];
}

export function createNavigation(win, { schedule } = {}) {
  const history = win.history;
  const later = schedule ?? ((fn) => win.setTimeout(fn, 0));
  const listeners = new Set();
  const handlers = [];
  // Mudanças de histórico causadas por nós mesmos (popstate a aceitar sem interceptar).
  let ownPops = 0;
  let syncQueued = false;

  function read() {
    const state = history.state ?? {};
    return {
      path: `${win.location.pathname}${win.location.search}`,
      idx: typeof state.idx === "number" ? state.idx : 0,
      key: state.key ?? null,
      from: state.from ?? null,
      data: state.data ?? null,
      guard: state.guard === true,
    };
  }

  function snapshotOf(current) {
    const [pathname, search] = splitPath(current.path);
    return {
      path: current.path,
      route: parseLocation(pathname, search),
      data: current.data,
      from: current.from,
    };
  }

  // Endereço inválido é trocado pelo endereço da rota que ele virou.
  function normalize() {
    const current = read();
    const [pathname, search] = splitPath(current.path);
    const route = parseLocation(pathname, search);
    const state = history.state ?? {};
    const needsKey = typeof state.idx !== "number" || !state.key;
    if (!route.known || needsKey) {
      history.replaceState(
        { ...state, idx: current.idx, key: state.key ?? newKey() },
        "",
        route.known ? undefined : `${formatRoute(route)}${win.location.hash}`
      );
    }
    return read();
  }

  let entry = normalize();
  let snapshot = snapshotOf(entry);

  function emit() {
    for (const listener of [...listeners]) listener();
  }

  function update(next) {
    const changed = next.key !== entry.key || next.path !== entry.path;
    entry = next;
    if (changed) {
      snapshot = snapshotOf(entry);
      emit();
    }
  }

  function queueSync() {
    if (syncQueued) return;
    syncQueued = true;
    later(sync);
  }

  // Põe ou tira a sentinela conforme haja camadas/bloqueios ativos.
  function sync() {
    syncQueued = false;
    // Ainda esperando um popstate nosso: tenta de novo quando ele chegar.
    if (ownPops > 0) return;
    const wanted = handlers.length > 0;
    if (wanted && !entry.guard) {
      history.pushState(
        { idx: entry.idx + 1, key: entry.key, from: entry.from, data: entry.data, guard: true },
        "",
        entry.path
      );
      entry = read();
    } else if (!wanted && entry.guard) {
      ownPops += 1;
      history.back();
    }
  }

  // Camadas (modais) ficam acima de bloqueios: o Voltar fecha o modal primeiro.
  function topHandler() {
    for (let i = handlers.length - 1; i >= 0; i -= 1) {
      if (handlers[i].kind === "layer") return handlers[i];
    }
    return handlers[handlers.length - 1] ?? null;
  }

  function handlePop() {
    const next = read();
    if (ownPops > 0) {
      ownPops -= 1;
      update(next);
      queueSync();
      return;
    }

    const top = topHandler();
    if (top && next.idx < entry.idx) {
      if (top.kind === "layer" && entry.guard && next.idx === entry.idx - 1) {
        // Voltar normal saindo da sentinela: só fecha a camada.
        update(next);
        top.run();
        queueSync();
        return;
      }
      // Bloqueio (ou o navegador pulou a sentinela): devolve o histórico.
      ownPops += 1;
      history.go(entry.idx - next.idx);
      top.run();
      return;
    }

    update(next);
    queueSync();
  }

  win.addEventListener("popstate", handlePop);

  // Vai para um endereço (ou rota). `replace` troca a entrada atual.
  function navigate(to, { replace = false, data = null } = {}) {
    const path = typeof to === "string" ? to : formatRoute(to);
    const key = newKey();
    if (entry.guard) {
      // A sentinela é uma cópia da página atual: a nova página fica no lugar dela.
      history.replaceState({ idx: entry.idx, key, from: entry.path, data }, "", path);
    } else if (replace || (path === entry.path && !data)) {
      history.replaceState({ idx: entry.idx, key, from: entry.from, data }, "", path);
    } else {
      history.pushState({ idx: entry.idx + 1, key, from: entry.path, data }, "", path);
    }
    update(read());
    queueSync();
  }

  // Sai da página atual para `path`. Se viemos de lá, volta no histórico
  // (sem passar pelos bloqueios); senão, navega para lá.
  function exitTo(path) {
    const steps = entry.guard ? 2 : 1;
    if (entry.from === path && entry.idx - steps >= 0) {
      ownPops += 1;
      history.go(-steps);
      return;
    }
    navigate(path);
  }

  function addBackHandler(run, kind = "layer") {
    const handler = { run, kind };
    handlers.push(handler);
    queueSync();
    return () => {
      const index = handlers.indexOf(handler);
      if (index !== -1) handlers.splice(index, 1);
      queueSync();
    };
  }

  return {
    navigate,
    exitTo,
    addBackHandler,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot: () => snapshot,
    destroy() {
      win.removeEventListener("popstate", handlePop);
    },
  };
}
