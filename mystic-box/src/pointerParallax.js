// Parallax do fundo: guarda a posição do ponteiro (de -1 a 1) nas variáveis
// CSS --px e --py do <html>. As camadas do céu (theme.css/gacha.css) se
// deslocam um pouco a partir delas. Só apresentação.

export function startPointerParallax(root = document.documentElement) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const finePointer = window.matchMedia("(pointer: fine)");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!finePointer.matches || reducedMotion.matches) return () => {};

  let frame = 0;
  let x = 0;
  let y = 0;

  function apply() {
    frame = 0;
    root.style.setProperty("--px", x.toFixed(3));
    root.style.setProperty("--py", y.toFixed(3));
  }

  function onMove(event) {
    x = (event.clientX / window.innerWidth) * 2 - 1;
    y = (event.clientY / window.innerHeight) * 2 - 1;
    if (!frame) frame = requestAnimationFrame(apply);
  }

  window.addEventListener("pointermove", onMove, { passive: true });
  return () => {
    window.removeEventListener("pointermove", onMove);
    if (frame) cancelAnimationFrame(frame);
  };
}
