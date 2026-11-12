// Comparação de imagem: cada tela em cada tamanho contra a referência
// aprovada em e2e/__screenshots__. Depois de uma mudança visual proposital,
// confira as diferenças (npm run test:ui:report) e atualize as referências
// com npm run test:ui:update.

import { SCREENS } from "./screens.js";
import { expect, open, signIn, test } from "./support.js";

for (const screen of SCREENS) {
  test(`${screen.name} igual à referência`, async ({ page, api }) => {
    if (screen.signedIn !== false) await signIn(page);
    await screen.setup?.(api, page);
    await open(page, screen.path);
    await expect(screen.ready(page)).toBeVisible();
    await expect(page).toHaveScreenshot(`${screen.name}.png`, {
      // Partes desenhadas em canvas a cada quadro (portal e brilhos) mudam
      // entre execuções mesmo com o movimento reduzido.
      mask: [page.locator("canvas")],
    });
  });
}
