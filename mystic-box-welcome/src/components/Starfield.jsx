import { useEffect, useRef } from "react";

// Céu estrelado do fundo: estrelas que piscam, poeira de Aether subindo e,
// de vez em quando, uma estrela cadente. Some o movimento com prefers-reduced-motion.
export default function Starfield() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let stars = [];
    let motes = [];
    let comet = null;
    let frame = 0;
    let scroll = window.scrollY;

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = Math.round((width * height) / 4200);
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.3 + 0.2,
        depth: Math.random() * 0.6 + 0.1,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.02 + 0.004,
        warm: Math.random() < 0.18,
      }));
      motes = Array.from({ length: Math.round(count / 9) }, () => newMote(true));
    };

    const newMote = (anywhere) => ({
      x: Math.random() * width,
      y: anywhere ? Math.random() * height : height + 10,
      r: Math.random() * 1.8 + 0.6,
      vy: Math.random() * 0.25 + 0.08,
      drift: Math.random() * Math.PI * 2,
      hue: Math.random() < 0.5 ? "255, 217, 138" : "200, 160, 255",
    });

    const draw = (time) => {
      ctx.clearRect(0, 0, width, height);
      for (const star of stars) {
        const twinkle = still ? 0.7 : 0.55 + Math.sin(star.phase + time * star.speed * 0.06) * 0.45;
        const y = (((star.y - scroll * star.depth * 0.3) % height) + height) % height;
        ctx.globalAlpha = Math.max(0.08, twinkle);
        ctx.fillStyle = star.warm ? "#ffe2a8" : "#e8ddff";
        ctx.beginPath();
        ctx.arc(star.x, y, star.r, 0, Math.PI * 2);
        ctx.fill();
      }

      for (let i = 0; i < motes.length; i += 1) {
        const mote = motes[i];
        if (!still) {
          mote.y -= mote.vy;
          mote.x += Math.sin(time * 0.0006 + mote.drift) * 0.15;
          if (mote.y < -10) motes[i] = newMote(false);
        }
        const gradient = ctx.createRadialGradient(mote.x, mote.y, 0, mote.x, mote.y, mote.r * 4);
        gradient.addColorStop(0, `rgba(${mote.hue}, 0.55)`);
        gradient.addColorStop(1, `rgba(${mote.hue}, 0)`);
        ctx.globalAlpha = 1;
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(mote.x, mote.y, mote.r * 4, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!still) {
        if (!comet && Math.random() < 0.0025) {
          comet = { x: Math.random() * width * 0.7 + width * 0.3, y: Math.random() * height * 0.35, life: 0 };
        }
        if (comet) {
          comet.life += 1;
          const progress = comet.life / 70;
          const x = comet.x - progress * 420;
          const y = comet.y + progress * 200;
          const tail = ctx.createLinearGradient(x, y, x + 120, y - 57);
          tail.addColorStop(0, `rgba(255, 243, 207, ${0.9 * (1 - progress)})`);
          tail.addColorStop(1, "rgba(255, 243, 207, 0)");
          ctx.globalAlpha = 1;
          ctx.strokeStyle = tail;
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + 120, y - 57);
          ctx.stroke();
          if (progress >= 1) comet = null;
        }
      }
      ctx.globalAlpha = 1;
    };

    const loop = (time) => {
      draw(time);
      frame = requestAnimationFrame(loop);
    };
    const onScroll = () => {
      scroll = window.scrollY;
      if (still) draw(0);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("scroll", onScroll, { passive: true });
    if (still) draw(0);
    else frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  return (
    <div className="sky" aria-hidden="true">
      <div className="sky-nebula" />
      <canvas ref={canvasRef} className="sky-canvas" />
    </div>
  );
}
