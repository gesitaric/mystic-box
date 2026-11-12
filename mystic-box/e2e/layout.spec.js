// Regras de layout em cada tamanho de tela (projetos do playwright.config.js).
// Um teste por tela; as verificações são "soft" para o relatório mostrar
// todos os problemas da tela de uma vez.

import { SCREENS } from "./screens.js";
import { expect, layoutProblems, open, overflowingElements, signIn, test } from "./support.js";

const INTERACTIVE = "button, a[href], input, select, textarea, [role='button'], [role='tab']";

for (const screen of SCREENS) {
  test(`${screen.name} cabe na tela`, async ({ page, api }) => {
    if (screen.signedIn !== false) await signIn(page);
    await screen.setup?.(api, page);
    await open(page, screen.path);
    await expect(screen.ready(page)).toBeVisible();

    expect.soft(await layoutProblems(page), "a página não rola para o lado").toEqual([]);

    expect
      .soft(await overflowingElements(page, INTERACTIVE), "botões e campos ficam dentro da tela")
      .toEqual([]);

    const modal = page.locator(".auth-modal");
    if ((await modal.count()) > 0) {
      const box = await modal.first().boundingBox();
      const viewport = page.viewportSize();
      const outside =
        box.x < -1 ||
        box.y < -1 ||
        box.x + box.width > viewport.width + 1 ||
        box.y + box.height > viewport.height + 1;
      expect.soft(outside, `o painel aberto cabe na tela (${JSON.stringify(box)})`).toBe(false);
    }

    expect.soft(api.unhandled, "todos os pedidos à API têm resposta gravada").toEqual([]);
  });
}
