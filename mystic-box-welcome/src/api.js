import { useEffect, useState } from "react";

// A landing só lê as rotas públicas do jogo (GET /world e GET /rules).
// Todos os números e catálogos exibidos vêm daqui; nada é recalculado na página.
const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export const GAME_URL = import.meta.env.VITE_GAME_URL || "https://mystic-box.geskee.com.br";

async function getJson(path, signal) {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`${path} respondeu ${response.status}`);
  return response.json();
}

/** { status: "loading" | "ready" | "error", data } de uma rota pública. */
export function usePublicApi(path) {
  const [state, setState] = useState({ status: "loading", data: null });

  useEffect(() => {
    const controller = new AbortController();
    getJson(path, controller.signal)
      .then((data) => setState({ status: "ready", data }))
      .catch((error) => {
        if (error.name !== "AbortError") setState({ status: "error", data: null });
      });
    return () => controller.abort();
  }, [path]);

  return state;
}
