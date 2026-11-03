import { useEffect, useImperativeHandle, useRef } from "react";
import { RevealFxEngine } from "./revealFxEngine";

// Camada de efeitos por cima das cartas. `ref` expõe:
// - reveal(rect, rarity): explosão quando a face de uma carta aparece;
// - gather(rect | null): energia convergindo para a carta (suspense).
function RevealFx({ ref }) {
  const canvasRef = useRef(null);
  const engineRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const engine = new RevealFxEngine(canvas);
    engineRef.current = engine;
    const observer = new ResizeObserver(() => engine.resize());
    observer.observe(canvas);
    return () => {
      observer.disconnect();
      engine.destroy();
      engineRef.current = null;
    };
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      reveal: (rect, rarity) => engineRef.current?.reveal(rect, rarity),
      gather: (rect) => engineRef.current?.gather(rect),
    }),
    []
  );

  return <canvas ref={canvasRef} className="reveal-fx" aria-hidden="true" />;
}

export default RevealFx;
