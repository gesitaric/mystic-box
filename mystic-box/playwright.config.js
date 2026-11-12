import { defineConfig } from "@playwright/test";

// Testes de tela: o jogo aberto no Edge já instalado (sem baixar navegadores)
// em vários tamanhos de tela. A API é simulada (e2e/support.js), então não
// precisa do banco nem do servidor local.

const PORT = 4173;
// Endereço falso da API: todo pedido para ele é respondido pelos testes.
export const E2E_API_URL = "http://api.mystic.test";

const edge = { channel: "msedge", browserName: "chromium" };

export default defineConfig({
  testDir: "e2e",
  // Uma tela por vez no mesmo tamanho; os tamanhos rodam em paralelo.
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  expect: {
    toHaveScreenshot: {
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
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "phone-small",
      use: { ...edge, viewport: { width: 360, height: 640 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
    {
      name: "phone",
      use: { ...edge, viewport: { width: 393, height: 852 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
    {
      name: "tablet",
      use: { ...edge, viewport: { width: 820, height: 1180 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
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
