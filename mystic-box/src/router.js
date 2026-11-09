import { useEffect, useRef, useSyncExternalStore } from "react";
import { createNavigation } from "./navigation.js";

// Roteador do jogo (um só por página). Ver `routes.js` para os endereços e
// `navigation.js` para como o Voltar do navegador é tratado.
const navigation = createNavigation(window);

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
