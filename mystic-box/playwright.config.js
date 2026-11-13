import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// Testes de tela: o jogo aberto no Edge já instalado (sem baixar navegadores)
// em vários tamanhos de tela. A API é simulada (e2e/support.js), então não
// precisa do banco nem do servidor local.

// O Edge cria um perfil temporário por aba e o Playwright grava os traces na
// pasta temporária do sistema. Ela fica no disco do projeto (o C está sem
// espaço); os workers herdam a variável. Só no Windows: no Linux (CI) o Edge
// cria um socket nessa pasta e o caminho ficaria longo demais para ele.
if (process.platform === "win32") {
  const TEMP_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "node_modules", ".cache", "playwright-tmp");
  mkdirSync(TEMP_DIR, { recursive: true });
  process.env.TEMP = TEMP_DIR;
  process.env.TMP = TEMP_DIR;
  process.env.TMPDIR = TEMP_DIR;
}

const PORT = 4173;
// Endereço falso da API: todo pedido para ele é respondido pelos testes.
export const E2E_API_URL = "http://api.mystic.test";

const edge = { channel: "msedge", browserName: "chromium" };

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  // O mapa e a coleção carregam imagens grandes. Poucas abas ao mesmo tempo
  // e resolução 1x: com mais, falta memória e o Windows aumenta o arquivo de
  // paginação (no disco C). No CI (runner com 4 núcleos) são 4.
  timeout: 60_000,
  workers: process.env.CI ? 4 : 2,
  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  expect: {
    toHaveScreenshot: {
      // Sem placa de vídeo (CI) as telas com imagens grandes demoram a ficar
      // iguais em duas capturas seguidas.
      timeout: 15_000,
      animations: "disabled",
      caret: "hide",
      // Pequenas diferenças de suavização do texto entre execuções.
      maxDiffPixelRatio: 0.01,
    },
  },
  // Referências separadas por tamanho de tela (o sistema operacional entra no
  // nome: a fonte sai diferente no Windows e no Linux).
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{-platform}{ext}",
  use: {
    baseURL: `http://localhost:${PORT}`,
    reducedMotion: "reduce",
    // Para investigar uma falha: npm run test:ui -- --trace on
    trace: "off",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "phone-small",
      use: { ...edge, viewport: { width: 360, height: 640 }, isMobile: true, hasTouch: true },
    },
    {
      name: "phone",
      use: { ...edge, viewport: { width: 393, height: 852 }, isMobile: true, hasTouch: true },
    },
    {
      name: "tablet",
      use: { ...edge, viewport: { width: 820, height: 1180 }, isMobile: true, hasTouch: true },
    },
    {
      name: "desktop",
      use: { ...edge, viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: `npx vite --mode e2e --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      VITE_API_URL: E2E_API_URL,
      // Pool falso: o login vem de uma sessão gravada no localStorage.
      VITE_COGNITO_USER_POOL_ID: "us-east-1_e2etest",
      VITE_COGNITO_CLIENT_ID: "e2eclient",
    },
  },
});
