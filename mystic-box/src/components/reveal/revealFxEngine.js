// Efeitos visuais da revelação das cartas (Canvas 2D por cima das cartas).
// Só apresentação: a raridade vem da API e aqui só escolhe cor e intensidade.

const TAU = Math.PI * 2;
const WHITE = "255,250,240";
const GOLD = "255,214,140";

// Mesmas cores de raridade do CSS (gacha.css, [data-rarity]).
const RARITY_RGB = {
  1: "143,211,255",
  2: "134,240,176",
  3: "185,139,255",
  4: "255,200,97",
  5: "255,138,209",
};

const rand = (min, max) => min + Math.random() * (max - min);
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v));
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

function makeGlowSprite(rgb, size = 64) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const g = canvas.getContext("2d");
  const r = size / 2;
  const grad = g.createRadialGradient(r, r, 0, r, r, r);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.14, `rgba(${rgb},0.95)`);
  grad.addColorStop(0.42, `rgba(${rgb},0.28)`);
  grad.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return canvas;
}

export function rarityColor(rarity) {
  return RARITY_RGB[Math.min(5, Math.max(1, rarity || 1))];
}

export class RevealFxEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.sprites = new Map();
    this.sparks = [];
    this.rings = [];
    this.flashes = [];
    this.pillars = [];
    this.gathering = null;
    this.running = false;
    this.frame = this.frame.bind(this);
    this.resize();
  }

  sprite(rgb) {
    if (!this.sprites.has(rgb)) this.sprites.set(rgb, makeGlowSprite(rgb));
    return this.sprites.get(rgb);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.left = rect.left;
    this.top = rect.top;
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    this.dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
  }

  // Converte um retângulo da janela para coordenadas do canvas.
  local(rect) {
    const own = this.canvas.getBoundingClientRect();
    return {
      x: rect.left - own.left + rect.width / 2,
      y: rect.top - own.top + rect.height / 2,
      w: rect.width,
      h: rect.height,
    };
  }

  wake() {
    if (this.running) return;
    this.running = true;
    this.last = performance.now();
    this.raf = requestAnimationFrame(this.frame);
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    this.running = false;
  }

  // A face da carta apareceu.
  reveal(rect, rarity) {
    const { x, y, w, h } = this.local(rect);
    const r = Math.min(5, Math.max(1, rarity || 1));
    const color = rarityColor(r);
    const palette = r >= 5 ? [color, GOLD, WHITE, color] : [color, color, WHITE];

    this.flashes.push({ x, y, t: 0, duration: 0.45 + r * 0.08, radius: w * (0.9 + r * 0.25), color });
    this.rings.push({ x, y, t: 0, duration: 0.7 + r * 0.1, color, max: w * (1 + r * 0.32), width: 3 + r });
    if (r >= 3) {
      this.rings.push({ x, y, t: -0.1, duration: 1, color: WHITE, max: w * (1.4 + r * 0.3), width: 2 });
    }
    if (r >= 5) {
      this.rings.push({ x, y, t: -0.22, duration: 1.4, color: GOLD, max: Math.hypot(this.width, this.height) * 0.6, width: 10 });
    }

    // Faíscas saindo da borda da carta.
    const count = 26 + r * r * 9;
    for (let i = 0; i < count; i += 1) {
      const angle = Math.random() * TAU;
      const edge = Math.min(w, h) * 0.45;
      const speed = rand(120, 380) * (1 + r * 0.28);
      const life = rand(0.6, 1.2 + r * 0.25);
      this.sparks.push({
        x: x + Math.cos(angle) * edge * rand(0.6, 1.1),
        y: y + Math.sin(angle) * edge * rand(0.6, 1.4),
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - rand(40, 140),
        life,
        max: life,
        size: rand(2.5, 6 + r * 1.4),
        color: pick(palette),
        drag: rand(1.6, 2.6),
        gravity: rand(90, 220),
      });
    }

    // Raridades altas: pilar de luz subindo da carta.
    if (r >= 4) {
      this.pillars.push({ x, y, t: 0, duration: r >= 5 ? 2.2 : 1.5, width: w * (r >= 5 ? 1.25 : 0.9), color });
    }
    this.wake();
  }

  // Suspense: energia convergindo para a carta. `rect` nulo encerra.
  gather(rect) {
    this.gathering = rect ? { ...this.local(rect), t: 0 } : null;
    if (rect) this.wake();
  }

  frame(now) {
    const dt = Math.min(0.05, (now - this.last) / 1000);
    this.last = now;
    this.update(dt);
    this.draw();

    const busy =
      this.sparks.length || this.rings.length || this.flashes.length || this.pillars.length || this.gathering;
    if (busy) {
      this.raf = requestAnimationFrame(this.frame);
    } else {
      this.running = false;
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  update(dt) {
    const g = this.gathering;
    if (g) {
      g.t += dt;
      // Partículas nascem em volta e são puxadas para a carta, cada vez mais.
      const rate = 60 + g.t * 160;
      const spawn = Math.floor(rate * dt + Math.random());
      for (let i = 0; i < spawn; i += 1) {
        const angle = Math.random() * TAU;
        const dist = g.w * rand(1.3, 2.6);
        this.sparks.push({
          x: g.x + Math.cos(angle) * dist,
          y: g.y + Math.sin(angle) * dist,
          vx: -Math.sin(angle) * rand(60, 140),
          vy: Math.cos(angle) * rand(60, 140),
          life: 1.4,
          max: 1.4,
          size: rand(2.5, 6),
          color: pick([GOLD, WHITE, "185,139,255", "255,138,209"]),
          drag: 1.2,
          gravity: 0,
          target: g,
        });
      }
    }

    for (const s of this.sparks) {
      if (s.target) {
        const dx = s.target.x - s.x;
        const dy = s.target.y - s.y;
        const d = Math.hypot(dx, dy) || 1;
        const pull = 1400 + (s.target.t ?? 0) * 1800;
        s.vx += (dx / d) * pull * dt;
        s.vy += (dy / d) * pull * dt;
        if (d < s.target.w * 0.25 || !this.gathering) s.life = Math.min(s.life, 0.12);
      } else {
        s.vy += s.gravity * dt;
      }
      const drag = Math.exp(-dt * s.drag);
      s.vx *= drag;
      s.vy *= drag;
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.life -= dt;
    }
    this.sparks = this.sparks.filter((s) => s.life > 0);
    if (this.sparks.length > 1400) this.sparks.splice(0, this.sparks.length - 1400);

    for (const list of [this.rings, this.flashes, this.pillars]) list.forEach((item) => (item.t += dt));
    this.rings = this.rings.filter((r) => r.t < r.duration);
    this.flashes = this.flashes.filter((f) => f.t < f.duration);
    this.pillars = this.pillars.filter((p) => p.t < p.duration);
  }

  draw() {
    const { ctx, dpr } = this;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = "lighter";

    this.drawPillars();
    this.drawGathering();
    this.drawFlashes();
    this.drawRings();
    this.drawSparks();
    ctx.globalAlpha = 1;
  }

  drawPillars() {
    const { ctx } = this;
    for (const p of this.pillars) {
      const t = p.t / p.duration;
      const grow = easeOutCubic(clamp(t / 0.25));
      const fade = t < 0.25 ? 1 : Math.pow(1 - (t - 0.25) / 0.75, 1.4);
      const half = (p.width / 2) * (0.4 + grow * 0.6);
      const top = p.y - (p.y + 40) * grow;

      const grad = ctx.createLinearGradient(p.x - half, 0, p.x + half, 0);
      grad.addColorStop(0, `rgba(${p.color},0)`);
      grad.addColorStop(0.35, `rgba(${p.color},${0.28 * fade})`);
      grad.addColorStop(0.5, `rgba(${WHITE},${0.55 * fade})`);
      grad.addColorStop(0.65, `rgba(${p.color},${0.28 * fade})`);
      grad.addColorStop(1, `rgba(${p.color},0)`);
      ctx.globalAlpha = 1;
      ctx.fillStyle = grad;
      ctx.fillRect(p.x - half, top, half * 2, p.y - top + 30);

      // Base brilhante do pilar.
      const glow = half * 2.2;
      ctx.globalAlpha = 0.8 * fade;
      ctx.drawImage(this.sprite(p.color), p.x - glow, p.y - glow, glow * 2, glow * 2);
    }
  }

  drawGathering() {
    const g = this.gathering;
    if (!g) return;
    const { ctx } = this;
    const k = clamp(g.t / 1.6);
    const pulse = 0.5 + 0.5 * Math.sin(g.t * (10 + k * 22));
    const radius = g.w * (0.8 + k * 0.9 + pulse * 0.15);
    ctx.globalAlpha = 0.25 + k * 0.5;
    ctx.drawImage(this.sprite(GOLD), g.x - radius, g.y - radius, radius * 2, radius * 2);

    // Anel contraindo em volta da carta.
    const ringT = (g.t * (1.2 + k * 2)) % 1;
    const ringR = g.w * (1.6 - ringT * 1.0);
    ctx.globalAlpha = (1 - ringT) * (0.3 + k * 0.5);
    ctx.strokeStyle = `rgba(${GOLD},1)`;
    ctx.lineWidth = 2 + k * 3;
    ctx.beginPath();
    ctx.ellipse(g.x, g.y, ringR, ringR * 1.2, 0, 0, TAU);
    ctx.stroke();
  }

  drawFlashes() {
    const { ctx } = this;
    for (const f of this.flashes) {
      const t = f.t / f.duration;
      const radius = f.radius * (0.6 + easeOutCubic(t) * 0.8);
      ctx.globalAlpha = Math.pow(1 - t, 2);
      ctx.drawImage(this.sprite(f.color), f.x - radius, f.y - radius, radius * 2, radius * 2);
      const core = radius * 0.45;
      ctx.drawImage(this.sprite(WHITE), f.x - core, f.y - core, core * 2, core * 2);
    }
  }

  drawRings() {
    const { ctx } = this;
    for (const ring of this.rings) {
      if (ring.t < 0) continue;
      const t = ring.t / ring.duration;
      const radius = ring.max * easeOutCubic(t);
      const fade = Math.pow(1 - t, 1.5);
      ctx.strokeStyle = `rgba(${ring.color},1)`;
      for (const [width, alpha] of [[ring.width * 4, 0.12], [ring.width, 0.8]]) {
        ctx.globalAlpha = alpha * fade;
        ctx.lineWidth = width * (1 - t * 0.6);
        ctx.beginPath();
        ctx.arc(ring.x, ring.y, radius, 0, TAU);
        ctx.stroke();
      }
    }
  }

  drawSparks() {
    const { ctx } = this;
    ctx.lineCap = "round";
    for (const s of this.sparks) {
      const t = clamp(s.life / s.max);
      const alpha = s.target ? Math.min(1, (s.max - s.life) * 4) : t;
      const speed = Math.hypot(s.vx, s.vy);
      if (speed > 140) {
        const k = Math.min(0.05, 16 / speed);
        ctx.globalAlpha = alpha * 0.7;
        ctx.strokeStyle = `rgba(${s.color},1)`;
        ctx.lineWidth = s.size * 0.3;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - s.vx * k, s.y - s.vy * k);
        ctx.stroke();
      }
      const size = s.size * (s.target ? 1 : 0.5 + t * 0.7);
      ctx.globalAlpha = alpha;
      ctx.drawImage(this.sprite(s.color), s.x - size, s.y - size, size * 2, size * 2);
    }
  }
}
