import { useEffect, useRef, useSyncExternalStore } from "react";
import { flushSync } from "react-dom";
import { createNavigation } from "./navigation.js";

// Troca de tela (início, invocação, arena) com a transição de "portal"
// (View Transitions API, onde o navegador tiver; ver index.css). Painéis e
// abas trocam sem ela.
function screenTransition(apply, previous, next) {
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const screenChanged = previous.route.screen !== next.route.screen;
  if (!screenChanged || reduceMotion || !document.startViewTransition) {
    apply();
    return;
  }
  document.startViewTransition(() => flushSync(apply));
}

// Roteador do jogo (um só por página). Ver `routes.js` para os endereços e
// `navigation.js` para como o Voltar do navegador é tratado.
const navigation = createNavigation(window, { transition: screenTransition });

export const navigate = navigation.navigate;
export const exitTo = navigation.exitTo;

// Rota atual fora da renderização (ex.: dentro de um efeito que roda uma vez).
export function currentRoute() {
  return navigation.getSnapshot().route;
}

// Rota atual: { route, path, data, from }.
export function useRoute() {
  return useSyncExternalStore(navigation.subscribe, navigation.getSnapshot);
}

// Enquanto `active`, o Voltar do navegador chama `onBack` em vez de sair da tela.
// kind "layer": modal sem endereço próprio (o Voltar o fecha, como o Esc).
// kind "block": tela que não pode ser deixada pelo Voltar agora.
export function useBackHandler(onBack, { active = true, kind = "layer" } = {}) {
  const ref = useRef(onBack);

  useEffect(() => {
    ref.current = onBack;
  });

  useEffect(() => {
    if (!active) return undefined;
    return navigation.addBackHandler(() => ref.current?.(), kind);
  }, [active, kind]);
}
