// Regras de layout em cada tamanho de tela (projetos do playwright.config.js).

import { SCREENS } from "./screens.js";
import { expect, layoutProblems, open, overflowingElements, signIn, test } from "./support.js";

const INTERACTIVE = "button, a[href], input, select, textarea, [role='button'], [role='tab']";

for (const screen of SCREENS) {
  test.describe(screen.name, () => {
    test.beforeEach(async ({ page, api }) => {
      if (screen.signedIn !== false) await signIn(page);
      await screen.setup?.(api, page);
      await open(page, screen.path);
      await expect(screen.ready(page)).toBeVisible();
    });

    test("a página não rola para o lado", async ({ page }) => {
      expect(await layoutProblems(page)).toEqual([]);
    });

    test("botões e campos ficam dentro da tela", async ({ page }) => {
      expect(await overflowingElements(page, INTERACTIVE)).toEqual([]);
    });

    test("o painel aberto cabe na tela", async ({ page }) => {
      const modal = page.locator(".auth-modal");
      test.skip((await modal.count()) === 0, "tela sem painel");
      const box = await modal.first().boundingBox();
      const viewport = page.viewportSize();
      expect(box.x).toBeGreaterThanOrEqual(-1);
      expect(box.y).toBeGreaterThanOrEqual(-1);
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1);
    });

    test("todos os pedidos à API têm resposta gravada", async ({ api }) => {
      expect(api.unhandled).toEqual([]);
    });
  });
}
