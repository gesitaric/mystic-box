// Motor visual do portal de invocação (Canvas 2D).
// Contém a máquina de estados da interação (IDLE → CHARGING → READY → ACTIVATED)
// e todo o desenho. É só apresentação: não sorteia nem decide nada do jogo.

export const PHASE = {
  IDLE: "IDLE",
  CHARGING: "CHARGING",
  READY: "READY",
  ACTIVATED: "ACTIVATED",
};

const TAU = Math.PI * 2;
const CHARGE_SECONDS = 3;
// Depois da explosão, tempo até o portal aceitar ser fechado.
const SETTLE_SECONDS = 2.8;

const BLUE = "110,180,255";
const PURPLE = "170,110,255";
const GOLD = "255,206,120";
const WHITE = "255,250,240";
const COLORS = [BLUE, PURPLE, GOLD];

const RUNES = Array.from("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ");
const RUNE_FONT = '"Segoe UI Historic", "Noto Sans Runic", "Segoe UI Symbol", serif';

const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v));
const lerp = (a, b, t) => a + (b - a) * t;
const rand = (min, max) => min + Math.random() * (max - min);
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

function makeCanvas(width, height = width) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.ceil(width));
  canvas.height = Math.max(1, Math.ceil(height));
  return canvas;
}

function makeGlowSprite(rgb, size = 64) {
  const canvas = makeCanvas(size);
  const g = canvas.getContext("2d");
  const r = size / 2;
  const grad = g.createRadialGradient(r, r, 0, r, r, r);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.12, `rgba(${rgb},0.95)`);
  grad.addColorStop(0.4, `rgba(${rgb},0.28)`);
  grad.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return canvas;
}

function makeRuneSprite(glyph, size, rgb, blur) {
  const canvas = makeCanvas(size * 2.2);
  const g = canvas.getContext("2d");
  const c = canvas.width / 2;
  g.font = `${size}px ${RUNE_FONT}`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.shadowColor = `rgba(${rgb},1)`;
  g.shadowBlur = blur;
  g.fillStyle = `rgba(${rgb},1)`;
  g.fillText(glyph, c, c);
  g.shadowBlur = blur * 0.35;
  g.fillStyle = "rgba(255,255,255,0.9)";
  g.fillText(glyph, c, c);
  return canvas;
}

// Textura de redemoinho (braços em espiral), desenhada uma vez e girada a cada quadro.
function makeSwirl(palette, arms, twist) {
  const size = 512;
  const canvas = makeCanvas(size);
  const g = canvas.getContext("2d");
  const half = size / 2;
  g.translate(half, half);
  g.globalCompositeOperation = "lighter";
  g.lineCap = "round";

  for (let arm = 0; arm < arms; arm += 1) {
    const base = (arm / arms) * TAU;
    for (let k = 0; k < 34; k += 1) {
      const r0 = half * rand(0.35, 0.98);
      const jitter = rand(-0.35, 0.35);
      const color = pick(palette);
      g.strokeStyle = `rgba(${color},${rand(0.05, 0.22)})`;
      g.lineWidth = rand(1, 7);
      g.beginPath();
      for (let s = 0; s <= 28; s += 1) {
        const t = s / 28;
        const r = r0 * (1 - t * rand(0.5, 0.62));
        const a = base + jitter + twist * Math.log(half / r);
        const x = Math.cos(a) * r;
        const y = Math.sin(a) * r;
        if (s === 0) g.moveTo(x, y);
        else g.lineTo(x, y);
      }
      g.stroke();
    }
  }

  // Bordas suaves e um "olho" mais claro no centro.
  g.globalCompositeOperation = "destination-in";
  const mask = g.createRadialGradient(0, 0, 0, 0, 0, half);
  mask.addColorStop(0, "rgba(0,0,0,0.5)");
  mask.addColorStop(0.2, "rgba(0,0,0,1)");
  mask.addColorStop(0.75, "rgba(0,0,0,0.85)");
  mask.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = mask;
  g.fillRect(-half, -half, size, size);
  return canvas;
}

function makeBackground(width, height, cx, cy, radius) {
  const canvas = makeCanvas(width, height);
  const g = canvas.getContext("2d");

  const base = g.createRadialGradient(cx, cy, 0, cx, cy, Math.hypot(width, height) * 0.6);
  base.addColorStop(0, "#1a1236");
  base.addColorStop(0.35, "#0e0b24");
  base.addColorStop(0.7, "#070617");
  base.addColorStop(1, "#03030a");
  g.fillStyle = base;
  g.fillRect(0, 0, width, height);

  // Nebulosas.
  g.globalCompositeOperation = "lighter";
  const blobs = [
    [0.18, 0.25, 0.45, PURPLE, 0.09],
    [0.82, 0.3, 0.4, BLUE, 0.08],
    [0.5, 0.95, 0.55, PURPLE, 0.07],
    [0.15, 0.85, 0.3, BLUE, 0.06],
    [0.88, 0.82, 0.32, GOLD, 0.035],
    [0.5, 0.1, 0.35, BLUE, 0.05],
  ];
  blobs.forEach(([x, y, r, rgb, a]) => {
    const bx = x * width;
    const by = y * height;
    const br = r * Math.max(width, height);
    const grad = g.createRadialGradient(bx, by, 0, bx, by, br);
    grad.addColorStop(0, `rgba(${rgb},${a})`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, width, height);
  });

  // Estrelas fixas.
  for (let i = 0; i < 380; i += 1) {
    const x = Math.random() * width;
    const y = Math.random() * height;
    const s = Math.random() < 0.08 ? rand(1, 1.8) : rand(0.3, 0.9);
    g.fillStyle = `rgba(${pick([WHITE, BLUE, PURPLE])},${rand(0.15, 0.7)})`;
    g.fillRect(x, y, s, s);
  }

  // Chão de névoa sob o portal.
  g.globalCompositeOperation = "source-over";
  const floor = g.createRadialGradient(cx, cy + radius * 1.5, 0, cx, cy + radius * 1.5, radius * 2.4);
  floor.addColorStop(0, "rgba(90,60,180,0.16)");
  floor.addColorStop(1, "rgba(90,60,180,0)");
  g.fillStyle = floor;
  g.fillRect(0, 0, width, height);
  return canvas;
}

function makeVignette(width, height) {
  const canvas = makeCanvas(width, height);
  const g = canvas.getContext("2d");
  const grad = g.createRadialGradient(
    width / 2, height / 2, Math.min(width, height) * 0.35,
    width / 2, height / 2, Math.hypot(width, height) * 0.58
  );
  grad.addColorStop(0, "rgba(0,0,0,0)");
  grad.addColorStop(1, "rgba(0,0,0,0.82)");
  g.fillStyle = grad;
  g.fillRect(0, 0, width, height);
  return canvas;
}

// Raio por deslocamento de ponto médio.
function boltPath(x1, y1, x2, y2, roughness) {
  let points = [[x1, y1], [x2, y2]];
  let offset = Math.hypot(x2 - x1, y2 - y1) * roughness;
  for (let level = 0; level < 6; level += 1) {
    const next = [points[0]];
    for (let i = 0; i < points.length - 1; i += 1) {
      const [ax, ay] = points[i];
      const [bx, by] = points[i + 1];
      const dx = bx - ax;
      const dy = by - ay;
      const len = Math.hypot(dx, dy) || 1;
      const shift = (Math.random() - 0.5) * offset;
      next.push([(ax + bx) / 2 + (-dy / len) * shift, (ay + by) / 2 + (dx / len) * shift]);
      next.push(points[i + 1]);
    }
    points = next;
    offset *= 0.52;
  }
  return points;
}

export class PortalEngine {
  constructor(canvas, { audio, onPhase, onFrame, onSettled, reducedMotion = false }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.audio = audio;
    this.onPhase = onPhase;
    this.onFrame = onFrame;
    this.onSettled = onSettled;
    this.motionScale = reducedMotion ? 0.25 : 1;

    this.phase = PHASE.IDLE;
    this.charge = 0; // carga lógica (0..1)
    this.shown = 0; // carga suavizada usada no desenho
    this.activation = 0; // 0 = adormecido, 1 = portal aberto
    this.time = 0;
    this.phaseTime = 0;
    this.explodeTime = -1;
    this.settled = false;

    this.rotation = 0;
    this.spin = 0.1;
    this.vortexRotation = 0;
    this.waveTimer = 0;
    this.boltTimer = 0;
    this.emitTimer = 0;
    this.intakeTimer = 0;
    this.shakeX = 0;
    this.shakeY = 0;

    this.motes = [];
    this.sparks = [];
    this.bolts = [];
    this.waves = [];
    this.rings = [];
    this.rays = Array.from({ length: 18 }, (_, i) => ({
      angle: (i / 18) * TAU + rand(-0.12, 0.12),
      width: rand(0.025, 0.09),
      length: rand(2.6, 4.2),
      speed: rand(0.6, 1.8),
      seed: rand(0, TAU),
      color: pick(COLORS),
    }));

    this.glow = {
      [BLUE]: makeGlowSprite(BLUE),
      [PURPLE]: makeGlowSprite(PURPLE),
      [GOLD]: makeGlowSprite(GOLD),
      [WHITE]: makeGlowSprite(WHITE),
    };
    this.swirlA = makeSwirl([PURPLE, BLUE, PURPLE], 5, 2.1);
    this.swirlB = makeSwirl([BLUE, GOLD, BLUE], 3, 2.8);

    this.frame = this.frame.bind(this);
    this.resize();
  }

  start() {
    this.last = performance.now();
    this.raf = requestAnimationFrame(this.frame);
  }

  destroy() {
    cancelAnimationFrame(this.raf);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    this.dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);

    this.cx = this.width / 2;
    this.cy = this.height * 0.47;
    this.R = Math.max(90, Math.min(this.width * 0.21, this.height * 0.29));

    this.background = makeBackground(this.width, this.height, this.cx, this.cy, this.R);
    this.vignette = makeVignette(this.width, this.height);

    const runeSize = this.R * 0.11;
    this.runeDim = RUNES.map((g) => makeRuneSprite(g, runeSize, BLUE, runeSize * 0.5));
    this.runeLit = RUNES.map((g) => makeRuneSprite(g, runeSize, GOLD, runeSize * 0.8));

    const target = Math.round((this.width * this.height) / 9000);
    const count = clamp(target, 90, 220);
    this.motes = Array.from({ length: count }, () => this.spawnMote(true));
  }

  // Área clicável: o portal e o anel externo.
  hitTest(x, y) {
    return Math.hypot(x - this.cx, y - this.cy) <= this.R * 1.36;
  }

  setPhase(phase) {
    if (this.phase === phase) return;
    this.phase = phase;
    this.phaseTime = 0;
    this.onPhase?.(phase);
  }

  // Botão pressionado sobre o portal.
  press() {
    if (this.phase === PHASE.IDLE) {
      // Retoma de onde a carga estava se ainda estiver esvaziando.
      this.setPhase(PHASE.CHARGING);
      return true;
    }
    if (this.phase === PHASE.ACTIVATED && this.settled) {
      this.seal();
    }
    return false;
  }

  // Botão solto.
  release() {
    if (this.phase === PHASE.CHARGING) this.setPhase(PHASE.IDLE);
    else if (this.phase === PHASE.READY) this.explode();
  }

  // Interação interrompida (janela perdeu o foco, ponteiro cancelado).
  cancel() {
    if (this.phase === PHASE.CHARGING || this.phase === PHASE.READY) this.setPhase(PHASE.IDLE);
  }

  seal() {
    this.charge = 0;
    this.settled = false;
    this.audio?.seal();
    this.setPhase(PHASE.IDLE);
  }

  explode() {
    this.charge = 0;
    this.activation = 1;
    this.explodeTime = 0;
    this.settled = false;
    this.bolts.length = 0;
    this.audio?.explode();

    const { cx, cy, R } = this;
    const reach = Math.hypot(this.width, this.height);

    // Centenas de faíscas.
    for (let i = 0; i < 520; i += 1) {
      const angle = Math.random() * TAU;
      const speed = rand(0.25, 1) ** 1.6 * reach * rand(0.9, 1.9);
      const start = rand(0, R * 0.35);
      const life = rand(0.9, 2.8);
      this.sparks.push({
        x: cx + Math.cos(angle) * start,
        y: cy + Math.sin(angle) * start,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life,
        max: life,
        size: rand(4, 16),
        color: Math.random() < 0.18 ? WHITE : pick(COLORS),
        drag: rand(1.4, 2.6),
      });
    }

    // Anéis de energia em sequência.
    [
      [0, WHITE, 1.25, 26],
      [0.06, GOLD, 1.5, 16],
      [0.16, PURPLE, 1.8, 12],
      [0.28, BLUE, 2.1, 9],
      [0.45, GOLD, 2.4, 5],
    ].forEach(([delay, color, duration, width]) =>
      this.rings.push({ t: -delay, duration, color, width })
    );

    // Empurra as partículas do ambiente para fora.
    this.motes.forEach((m) => {
      const dx = m.x - cx;
      const dy = m.y - cy;
      const d = Math.hypot(dx, dy) || 1;
      const push = 1500 * (1 - clamp(d / reach));
      m.vx = (dx / d) * push;
      m.vy = (dy / d) * push;
    });

    this.setPhase(PHASE.ACTIVATED);
  }

  spawnMote(anywhere) {
    const { width, height } = this;
    let x;
    let y;
    if (anywhere) {
      x = Math.random() * width;
      y = Math.random() * height;
    } else {
      // Renasce na borda, longe do portal.
      const side = Math.floor(Math.random() * 4);
      x = side === 0 ? -10 : side === 1 ? width + 10 : Math.random() * width;
      y = side === 2 ? -10 : side === 3 ? height + 10 : Math.random() * height;
    }
    return {
      x,
      y,
      vx: rand(-6, 6),
      vy: rand(-14, -3),
      size: rand(2, 7) * (Math.random() < 0.1 ? 2 : 1),
      color: pick([BLUE, BLUE, PURPLE, PURPLE, GOLD]),
      seed: rand(0, TAU),
      fade: anywhere ? 1 : 0,
      twinkle: rand(0.6, 2.2),
    };
  }

  frame(now) {
    const dt = Math.min(0.05, (now - this.last) / 1000);
    this.last = now;
    this.update(dt);
    this.draw();
    this.onFrame?.(this);
    this.raf = requestAnimationFrame(this.frame);
  }

  update(dt) {
    this.time += dt;
    this.phaseTime += dt;
    const { phase } = this;

    if (phase === PHASE.CHARGING) {
      this.charge = Math.min(1, this.charge + dt / CHARGE_SECONDS);
      // Resto do portal fechado some rápido para a carga aparecer.
      this.activation = Math.max(0, this.activation - dt * 1.6);
      if (this.charge >= 1) {
        this.setPhase(PHASE.READY);
        this.audio?.charged();
      }
    } else if (phase === PHASE.IDLE) {
      // Cancelado: esvazia aos poucos.
      this.charge = Math.max(0, this.charge - dt * (0.3 + this.charge * 0.45));
      this.activation = Math.max(0, this.activation - dt * 0.65);
    } else if (phase === PHASE.ACTIVATED) {
      this.explodeTime += dt;
      if (!this.settled && this.explodeTime >= SETTLE_SECONDS) {
        this.settled = true;
        this.onSettled?.();
      }
    }

    this.shown += (this.charge - this.shown) * Math.min(1, dt * 14);
    const c = this.shown;
    const a = this.activation;
    const ready = phase === PHASE.READY;

    // Rotação progressiva.
    let targetSpin = 0.08 + 2.6 * c * c;
    if (ready) targetSpin = 3.2;
    if (phase === PHASE.ACTIVATED) targetSpin = lerp(4, 0.55, easeOutCubic(clamp(this.explodeTime / 2.5)));
    targetSpin = Math.max(targetSpin, 0.55 * a);
    this.spin += (targetSpin - this.spin) * Math.min(1, dt * 4);
    this.rotation += this.spin * dt;
    this.vortexRotation += (0.25 + this.spin * 1.4) * dt;

    // Tremor de câmera.
    let shake = 0;
    if (phase === PHASE.CHARGING || phase === PHASE.IDLE) shake = Math.max(0, (c - 0.72) / 0.28) ** 2 * 5;
    if (ready) shake = 5 + Math.sin(this.time * 9) * 2;
    if (this.explodeTime >= 0 && phase === PHASE.ACTIVATED) {
      shake = Math.max(shake, 30 * Math.exp(-this.explodeTime * 3.2));
    }
    shake *= this.motionScale;
    this.shakeX = (Math.random() - 0.5) * 2 * shake;
    this.shakeY = (Math.random() - 0.5) * 2 * shake;

    this.updateMotes(dt, c, a);
    this.updateIntake(dt, c);
    this.updateSparks(dt);
    this.updateBolts(dt, c, a);
    this.updateWaves(dt, c);
    this.rings.forEach((r) => (r.t += dt));
    this.rings = this.rings.filter((r) => r.t < r.duration);

    this.audio?.update(c, phase, a);
  }

  updateMotes(dt, c, a) {
    const { cx, cy, R, phase } = this;
    const pulling = phase === PHASE.CHARGING || phase === PHASE.READY;
    const pull = pulling ? Math.max(0.15, c) : c * 0.4;
    const damping = Math.exp(-dt * (pulling ? 1.2 : 1.8));

    for (let i = 0; i < this.motes.length; i += 1) {
      const m = this.motes[i];
      const dx = cx - m.x;
      const dy = cy - m.y;
      const d = Math.hypot(dx, dy) || 1;

      // Deriva suave para cima.
      m.vx += Math.sin(this.time * 0.7 + m.seed) * 10 * dt;
      m.vy += (-10 - m.vy) * dt * 0.5;

      if (pull > 0.01) {
        const strength = pull * pull * 2600 + pull * 300;
        m.vx += (dx / d) * strength * dt + (-dy / d) * strength * 0.55 * dt;
        m.vy += (dy / d) * strength * dt + (dx / d) * strength * 0.55 * dt;
      }

      // No portal ativado, partículas saem devagar do centro.
      if (phase === PHASE.ACTIVATED && d < R * 2) {
        m.vx -= (dx / d) * 40 * a * dt;
        m.vy -= (dy / d) * 40 * a * dt;
      }

      m.vx *= damping;
      m.vy *= damping;
      m.x += m.vx * dt;
      m.y += m.vy * dt;
      m.fade = Math.min(1, m.fade + dt * 0.8);

      const outside =
        m.x < -60 || m.x > this.width + 60 || m.y < -60 || m.y > this.height + 60;
      if ((pull > 0.05 && d < R * 0.12) || outside) {
        this.motes[i] = this.spawnMote(false);
      }
    }
  }

  // Partículas extras sugadas para o centro durante o carregamento.
  updateIntake(dt, c) {
    const { cx, cy, R, phase } = this;
    const pulling = phase === PHASE.CHARGING || phase === PHASE.READY;
    if (pulling) {
      const rate = phase === PHASE.READY ? 220 : 30 + c * 190;
      this.intakeTimer += dt * rate;
      while (this.intakeTimer >= 1) {
        this.intakeTimer -= 1;
        const angle = Math.random() * TAU;
        const r = R * rand(1.25, 2.3);
        const swirl = rand(120, 260);
        this.sparks.push({
          x: cx + Math.cos(angle) * r,
          y: cy + Math.sin(angle) * r,
          vx: -Math.sin(angle) * swirl,
          vy: Math.cos(angle) * swirl,
          life: 2.2,
          max: 2.2,
          size: rand(3, 9),
          color: pick([BLUE, PURPLE, GOLD, PURPLE]),
          drag: 1.1,
          intake: true,
        });
      }
    }

    // Portal ativado: brasas douradas saindo da borda.
    if (phase === PHASE.ACTIVATED) {
      this.emitTimer += dt * 28;
      while (this.emitTimer >= 1) {
        this.emitTimer -= 1;
        const angle = Math.random() * TAU;
        const r = R * rand(0.75, 1.0);
        const speed = rand(30, 90);
        this.sparks.push({
          x: cx + Math.cos(angle) * r,
          y: cy + Math.sin(angle) * r,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 20,
          life: rand(1.6, 3.4),
          max: 3.4,
          size: rand(3, 8),
          color: pick([GOLD, GOLD, PURPLE, BLUE]),
          drag: 0.3,
        });
      }
    }
  }

  updateSparks(dt) {
    const { cx, cy, R, phase } = this;
    const pulling = phase === PHASE.CHARGING || phase === PHASE.READY;
    const intakePull = pulling ? 900 + this.shown * 2600 : 0;

    for (const s of this.sparks) {
      if (s.intake) {
        const dx = cx - s.x;
        const dy = cy - s.y;
        const d = Math.hypot(dx, dy) || 1;
        if (pulling) {
          s.vx += (dx / d) * intakePull * dt + (-dy / d) * intakePull * 0.25 * dt;
          s.vy += (dy / d) * intakePull * dt + (dx / d) * intakePull * 0.25 * dt;
        }
        if (d < R * 0.1) s.life = 0;
      }
      const drag = Math.exp(-dt * s.drag);
      s.vx *= drag;
      s.vy *= drag;
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.life -= dt;
    }
    this.sparks = this.sparks.filter((s) => s.life > 0);
    if (this.sparks.length > 1600) this.sparks.splice(0, this.sparks.length - 1600);
  }

  updateBolts(dt, c, a) {
    const { phase } = this;
    let rate = 0;
    if (phase === PHASE.CHARGING || phase === PHASE.IDLE) rate = Math.max(0, (c - 0.28) / 0.72) ** 1.4 * 16;
    if (phase === PHASE.READY) rate = 24;
    if (phase === PHASE.ACTIVATED) rate = this.explodeTime < 0.6 ? 40 : 2.5 * a;

    this.boltTimer += dt * rate;
    while (this.boltTimer >= 1) {
      this.boltTimer -= 1;
      this.spawnBolt(phase === PHASE.READY ? 1 : Math.max(c, a * 0.6));
    }

    for (const b of this.bolts) b.life -= dt;
    this.bolts = this.bolts.filter((b) => b.life > 0);
  }

  spawnBolt(intensity) {
    const { cx, cy, R } = this;
    const kind = Math.random();
    let points;
    let color = pick([BLUE, PURPLE, BLUE, WHITE]);

    if (kind < 0.45) {
      // Arco correndo pelo anel externo.
      const a0 = Math.random() * TAU;
      const span = rand(0.25, 0.9);
      const radius = R * rand(1.08, 1.22);
      points = [];
      const steps = 20;
      for (let i = 0; i <= steps; i += 1) {
        const ang = a0 + (span * i) / steps;
        const r = radius + (i === 0 || i === steps ? 0 : (Math.random() - 0.5) * R * 0.09);
        points.push([cx + Math.cos(ang) * r, cy + Math.sin(ang) * r]);
      }
    } else if (kind < 0.85) {
      // Para fora, saindo do portal.
      const ang = Math.random() * TAU;
      const r0 = R * rand(0.95, 1.2);
      const r1 = R * rand(1.45, 1.7 + intensity * 0.9);
      const bend = rand(-0.25, 0.25);
      points = boltPath(
        cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0,
        cx + Math.cos(ang + bend) * r1, cy + Math.sin(ang + bend) * r1,
        0.3
      );
    } else {
      // Para dentro, até o núcleo.
      const ang = Math.random() * TAU;
      const r0 = R * rand(0.85, 1.05);
      points = boltPath(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0, cx, cy, 0.22);
      color = Math.random() < 0.5 ? GOLD : WHITE;
    }

    const life = rand(0.07, 0.18);
    const bolt = { points, life, max: life, width: rand(1, 2.2) * (0.7 + intensity * 0.6), color };
    this.bolts.push(bolt);

    // Galho.
    if (points.length > 8 && Math.random() < 0.5) {
      const [bx, by] = points[Math.floor(points.length * rand(0.2, 0.6))];
      const ang = Math.atan2(by - cy, bx - cx) + rand(-0.9, 0.9);
      const len = R * rand(0.15, 0.4);
      this.bolts.push({
        points: boltPath(bx, by, bx + Math.cos(ang) * len, by + Math.sin(ang) * len, 0.35),
        life,
        max: life,
        width: bolt.width * 0.6,
        color,
      });
    }
    this.audio?.crackle(intensity);
  }

  updateWaves(dt, c) {
    const { phase } = this;
    const ready = phase === PHASE.READY;
    if (ready || (phase === PHASE.CHARGING && c > 0.55)) {
      const interval = ready ? 0.32 : lerp(0.95, 0.38, (c - 0.55) / 0.45);
      this.waveTimer += dt;
      if (this.waveTimer >= interval) {
        this.waveTimer = 0;
        this.waves.push({ t: 0, duration: ready ? 1.1 : 1.4, strength: ready ? 1 : c });
      }
    } else if (phase === PHASE.ACTIVATED && this.explodeTime > 1.2) {
      // Pulso calmo do portal aberto.
      this.waveTimer += dt;
      if (this.waveTimer >= 1.8) {
        this.waveTimer = 0;
        this.waves.push({ t: 0, duration: 2.6, strength: 0.45 });
      }
    }
    this.waves.forEach((w) => (w.t += dt));
    this.waves = this.waves.filter((w) => w.t < w.duration);
  }

  // ----------------------------------------------------------------- desenho

  draw() {
    const { ctx, dpr, width, height } = this;
    const c = this.shown;
    const a = this.activation;
    const energy = Math.max(c, a);
    const ready = this.phase === PHASE.READY;
    const pulse = ready ? 0.5 + 0.5 * Math.sin(this.time * 14) : 0;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.drawImage(this.background, 0, 0, width, height);

    ctx.save();
    ctx.translate(this.shakeX, this.shakeY);

    this.drawAmbientLight(energy, pulse);
    this.drawRays(c, a, pulse);
    this.drawMotes(c);
    this.drawWaves();
    this.drawPortalBody(c, a, energy, pulse);
    this.drawOuterCircle(c, a, energy);
    this.drawRunes(c, a, energy);
    this.drawProgress(c, pulse);
    this.drawSparks();
    this.drawBolts();
    this.drawCore(c, a, pulse);
    this.drawRings();
    this.drawDistortion(c, pulse);

    ctx.restore();

    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.drawImage(this.vignette, 0, 0, width, height);
    this.drawFlash();
  }

  drawAmbientLight(energy, pulse) {
    const { ctx, cx, cy, R } = this;
    ctx.globalCompositeOperation = "lighter";
    const radius = R * (2.2 + energy * 1.2 + pulse * 0.15);
    const grad = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, radius);
    grad.addColorStop(0, `rgba(${PURPLE},${0.1 + energy * 0.22})`);
    grad.addColorStop(0.45, `rgba(${BLUE},${0.04 + energy * 0.1})`);
    grad.addColorStop(1, `rgba(${BLUE},0)`);
    ctx.globalAlpha = 1;
    ctx.fillStyle = grad;
    ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
  }

  drawRays(c, a, pulse) {
    const { ctx, cx, cy, R } = this;
    let strength = Math.max(0, (c - 0.6) / 0.4) * 0.35 + pulse * 0.12;
    if (this.phase === PHASE.ACTIVATED) {
      const t = this.explodeTime;
      strength = Math.max(strength, lerp(1, 0.32, easeOutCubic(clamp(t / 2.2))));
    } else {
      strength = Math.max(strength, a * 0.32);
    }
    if (strength < 0.01) return;

    ctx.globalCompositeOperation = "lighter";
    const turn = this.time * 0.05;
    for (const ray of this.rays) {
      const flicker = 0.6 + 0.4 * Math.sin(this.time * ray.speed + ray.seed);
      const alpha = strength * flicker * 0.28;
      const len = R * ray.length;
      const ang = ray.angle + turn;
      const grad = ctx.createLinearGradient(cx, cy, cx + Math.cos(ang) * len, cy + Math.sin(ang) * len);
      grad.addColorStop(0, `rgba(${ray.color},${alpha})`);
      grad.addColorStop(0.35, `rgba(${ray.color},${alpha * 0.45})`);
      grad.addColorStop(1, `rgba(${ray.color},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(ang - ray.width) * len, cy + Math.sin(ang - ray.width) * len);
      ctx.lineTo(cx + Math.cos(ang + ray.width) * len, cy + Math.sin(ang + ray.width) * len);
      ctx.closePath();
      ctx.fill();
    }
  }

  drawMotes(c) {
    const { ctx } = this;
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    for (const m of this.motes) {
      const twinkle = 0.55 + 0.45 * Math.sin(this.time * m.twinkle + m.seed);
      const alpha = m.fade * twinkle * (0.45 + c * 0.5);
      const speed = Math.hypot(m.vx, m.vy);
      const size = m.size * (1 + c * 0.6);
      if (speed > 160) {
        const k = Math.min(0.09, 18 / speed);
        ctx.globalAlpha = alpha * 0.6;
        ctx.strokeStyle = `rgba(${m.color},1)`;
        ctx.lineWidth = size * 0.22;
        ctx.beginPath();
        ctx.moveTo(m.x, m.y);
        ctx.lineTo(m.x - m.vx * k, m.y - m.vy * k);
        ctx.stroke();
      }
      ctx.globalAlpha = alpha;
      ctx.drawImage(this.glow[m.color], m.x - size, m.y - size, size * 2, size * 2);
    }
    ctx.globalAlpha = 1;
  }

  drawWaves() {
    const { ctx, cx, cy, R } = this;
    ctx.globalCompositeOperation = "lighter";
    for (const w of this.waves) {
      const t = w.t / w.duration;
      const r = R * (0.95 + easeOutCubic(t) * 1.25);
      const alpha = (1 - t) * 0.55 * w.strength;
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = `rgba(${PURPLE},1)`;
      ctx.lineWidth = 10 * (1 - t) + 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, TAU);
      ctx.stroke();
      ctx.strokeStyle = `rgba(${WHITE},1)`;
      ctx.lineWidth = 1.5 * (1 - t) + 0.5;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  drawPortalBody(c, a, energy, pulse) {
    const { ctx, cx, cy, R } = this;

    // Fundo escuro do portal (profundidade).
    ctx.globalCompositeOperation = "source-over";
    const depth = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.95);
    depth.addColorStop(0, "rgba(10,6,24,0.92)");
    depth.addColorStop(0.75, "rgba(16,10,40,0.85)");
    depth.addColorStop(1, "rgba(16,10,40,0)");
    ctx.fillStyle = depth;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.95, 0, TAU);
    ctx.fill();

    // Redemoinhos.
    ctx.globalCompositeOperation = "lighter";
    const size = R * 1.8;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.globalAlpha = 0.35 + energy * 0.65;
    ctx.rotate(this.vortexRotation);
    ctx.drawImage(this.swirlA, -size / 2, -size / 2, size, size);
    ctx.rotate(-this.vortexRotation * 1.65 + 1.3);
    const inner = size * (0.72 + pulse * 0.04);
    ctx.globalAlpha = 0.2 + energy * 0.7;
    ctx.drawImage(this.swirlB, -inner / 2, -inner / 2, inner, inner);
    ctx.restore();

    // Geometria interna.
    const lineAlpha = 0.22 + energy * 0.6;
    const gold = c > 0.5 || a > 0.5;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.lineCap = "round";

    // Anel tracejado em sentido contrário.
    ctx.rotate(-this.rotation * 0.55);
    ctx.strokeStyle = `rgba(${BLUE},${lineAlpha})`;
    ctx.lineWidth = 2;
    ctx.setLineDash([R * 0.06, R * 0.035]);
    ctx.beginPath();
    ctx.arc(0, 0, R * 0.95, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);

    // Hexagrama.
    ctx.rotate(this.rotation * 0.85);
    ctx.strokeStyle = `rgba(${gold ? GOLD : PURPLE},${lineAlpha * 0.85})`;
    ctx.lineWidth = 1.4;
    for (let tri = 0; tri < 2; tri += 1) {
      ctx.beginPath();
      for (let i = 0; i <= 3; i += 1) {
        const ang = (i / 3) * TAU + (tri * Math.PI) / 3 - Math.PI / 2;
        const x = Math.cos(ang) * R * 0.88;
        const y = Math.sin(ang) * R * 0.88;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Círculo interno com nós.
    ctx.rotate(-this.rotation * 1.6);
    ctx.strokeStyle = `rgba(${PURPLE},${lineAlpha})`;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(0, 0, R * 0.58, 0, TAU);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, R * 0.44, 0, TAU);
    ctx.stroke();
    for (let i = 0; i < 6; i += 1) {
      const ang = (i / 6) * TAU;
      ctx.beginPath();
      ctx.arc(Math.cos(ang) * R * 0.58, Math.sin(ang) * R * 0.58, R * 0.05, 0, TAU);
      ctx.stroke();
    }
    ctx.restore();

    // Borda luminosa do portal.
    ctx.globalAlpha = 1;
    const rim = ctx.createRadialGradient(cx, cy, R * 0.82, cx, cy, R * 1.04);
    rim.addColorStop(0, `rgba(${PURPLE},0)`);
    rim.addColorStop(0.6, `rgba(${PURPLE},${0.12 + energy * 0.35})`);
    rim.addColorStop(0.85, `rgba(${BLUE},${0.1 + energy * 0.3 + pulse * 0.1})`);
    rim.addColorStop(1, `rgba(${BLUE},0)`);
    ctx.fillStyle = rim;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.04, 0, TAU);
    ctx.fill();
  }

  drawOuterCircle(c, a, energy) {
    const { ctx, cx, cy, R } = this;
    const lit = clamp(energy);
    const color = lit > 0.5 ? GOLD : BLUE;
    const alpha = 0.2 + lit * 0.75;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.globalCompositeOperation = "lighter";
    ctx.rotate(this.rotation * 0.3);

    // Brilho largo + traço fino.
    for (const [lw, al] of [[10, 0.08], [2.2, 1]]) {
      ctx.strokeStyle = `rgba(${color},${alpha * al})`;
      ctx.lineWidth = lw;
      ctx.beginPath();
      ctx.arc(0, 0, R * 1.18, 0, TAU);
      ctx.stroke();
    }
    ctx.strokeStyle = `rgba(${color},${alpha * 0.6})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(0, 0, R * 1.245, 0, TAU);
    ctx.stroke();

    // Marcações, que acendem em sequência conforme a carga.
    const ticks = 96;
    for (let i = 0; i < ticks; i += 1) {
      const ang = (i / ticks) * TAU;
      const on = i / ticks < Math.max(c, a);
      const major = i % 8 === 0;
      const r0 = R * 1.18;
      const r1 = R * (major ? 1.245 : 1.21);
      ctx.strokeStyle = on ? `rgba(${GOLD},0.95)` : `rgba(${BLUE},${0.18 + lit * 0.2})`;
      ctx.lineWidth = major ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(Math.cos(ang) * r0, Math.sin(ang) * r0);
      ctx.lineTo(Math.cos(ang) * r1, Math.sin(ang) * r1);
      ctx.stroke();
    }

    // Losangos nos pontos cardeais.
    ctx.fillStyle = `rgba(${lit > 0.5 ? WHITE : BLUE},${0.4 + lit * 0.6})`;
    for (let i = 0; i < 8; i += 1) {
      const ang = (i / 8) * TAU;
      const r = R * 1.212;
      ctx.save();
      ctx.translate(Math.cos(ang) * r, Math.sin(ang) * r);
      ctx.rotate(ang);
      const s = R * 0.022;
      ctx.beginPath();
      ctx.moveTo(s * 1.6, 0);
      ctx.lineTo(0, s);
      ctx.lineTo(-s * 1.6, 0);
      ctx.lineTo(0, -s);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }

  drawRunes(c, a, energy) {
    const { ctx, cx, cy, R } = this;
    const count = RUNES.length;
    const radius = R * 1.065;
    const sprite = this.runeDim[0];
    const size = sprite.width;

    ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < count; i += 1) {
      const ang = (i / count) * TAU - this.rotation * 0.45 - Math.PI / 2;
      const x = cx + Math.cos(ang) * radius;
      const y = cy + Math.sin(ang) * radius;
      const flicker = 0.75 + 0.25 * Math.sin(this.time * 3 + i * 1.7);

      // Cada runa acende quando a carga passa por ela.
      const threshold = i / count;
      const litness = Math.max(clamp((c - threshold) * count * 0.6), a);

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(ang + Math.PI / 2);
      const scale = 1 + litness * 0.18 + (litness > 0 ? Math.sin(this.time * 8 + i) * 0.04 * energy : 0);
      ctx.scale(scale, scale);
      ctx.globalAlpha = (0.35 + energy * 0.3) * flicker * (1 - litness * 0.7);
      ctx.drawImage(this.runeDim[i], -size / 2, -size / 2);
      if (litness > 0) {
        ctx.globalAlpha = litness * flicker;
        ctx.drawImage(this.runeLit[i], -size / 2, -size / 2);
      }
      ctx.restore();
    }
    ctx.globalAlpha = 1;
  }

  drawProgress(c, pulse) {
    const { ctx, cx, cy, R } = this;
    const channeling = this.phase === PHASE.CHARGING || this.phase === PHASE.READY;
    const visible = channeling ? 1 : clamp(c * 3);
    if (visible < 0.01) return;

    const r = R * 1.33;
    const start = -Math.PI / 2;
    const end = start + TAU * c;

    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    ctx.globalAlpha = visible;

    ctx.strokeStyle = `rgba(${BLUE},0.14)`;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, TAU);
    ctx.stroke();

    if (c > 0.002) {
      for (const [lw, color, al] of [
        [16, PURPLE, 0.12 + pulse * 0.1],
        [7, GOLD, 0.35],
        [2.5, WHITE, 0.95],
      ]) {
        ctx.strokeStyle = `rgba(${color},${al})`;
        ctx.lineWidth = lw;
        ctx.beginPath();
        ctx.arc(cx, cy, r, start, end);
        ctx.stroke();
      }
      // Ponta brilhante.
      const hx = cx + Math.cos(end) * r;
      const hy = cy + Math.sin(end) * r;
      const hs = 26 + pulse * 18;
      ctx.drawImage(this.glow[GOLD], hx - hs, hy - hs, hs * 2, hs * 2);
      ctx.drawImage(this.glow[WHITE], hx - hs * 0.4, hy - hs * 0.4, hs * 0.8, hs * 0.8);
    }
    ctx.globalAlpha = 1;
  }

  drawSparks() {
    const { ctx } = this;
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    for (const s of this.sparks) {
      const t = clamp(s.life / s.max);
      const alpha = s.intake ? Math.min(1, (s.max - s.life) * 3) : t;
      const speed = Math.hypot(s.vx, s.vy);
      if (speed > 120) {
        const k = Math.min(0.06, 22 / speed);
        ctx.globalAlpha = alpha * 0.7;
        ctx.strokeStyle = `rgba(${s.color},1)`;
        ctx.lineWidth = s.size * 0.25;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - s.vx * k, s.y - s.vy * k);
        ctx.stroke();
      }
      const size = s.size * (s.intake ? 1 : 0.6 + t * 0.6);
      ctx.globalAlpha = alpha;
      ctx.drawImage(this.glow[s.color], s.x - size, s.y - size, size * 2, size * 2);
    }
    ctx.globalAlpha = 1;
  }

  drawBolts() {
    const { ctx } = this;
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const b of this.bolts) {
      const alpha = (b.life / b.max) * rand(0.6, 1);
      ctx.beginPath();
      b.points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      for (const [lw, color, al] of [
        [b.width * 9, b.color, 0.08],
        [b.width * 3.2, b.color, 0.35],
        [b.width, WHITE, 1],
      ]) {
        ctx.globalAlpha = alpha * al;
        ctx.strokeStyle = `rgba(${color},1)`;
        ctx.lineWidth = lw;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  drawCore(c, a, pulse) {
    const { ctx, cx, cy, R } = this;
    let strength = 0.15 + c * c * 0.85 + pulse * 0.25;
    let breathe = Math.sin(this.time * (2 + c * 10)) * 0.05 * (0.3 + c);
    if (this.phase === PHASE.ACTIVATED) {
      const t = this.explodeTime;
      strength = lerp(1.8, 1, easeOutCubic(clamp(t / 1.5)));
      breathe = Math.sin(this.time * 2.2) * 0.06;
    } else {
      strength = Math.max(strength, a);
    }

    const radius = R * (0.16 + c * c * 0.34 + a * 0.32 + pulse * 0.06 + breathe);
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 1;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 2.2);
    grad.addColorStop(0, `rgba(${WHITE},${clamp(strength)})`);
    grad.addColorStop(0.12, `rgba(${GOLD},${clamp(strength * 0.85)})`);
    grad.addColorStop(0.35, `rgba(${PURPLE},${clamp(strength * 0.45)})`);
    grad.addColorStop(0.7, `rgba(${BLUE},${clamp(strength * 0.12)})`);
    grad.addColorStop(1, `rgba(${BLUE},0)`);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 2.2, 0, TAU);
    ctx.fill();

    // Ponto quente central.
    const hot = radius * 0.5;
    ctx.globalAlpha = clamp(0.3 + strength * 0.7);
    ctx.drawImage(this.glow[WHITE], cx - hot, cy - hot, hot * 2, hot * 2);
    ctx.globalAlpha = 1;
  }

  drawRings() {
    const { ctx, cx, cy, R, width, height } = this;
    if (!this.rings.length) return;
    const reach = Math.hypot(width, height) * 0.75;
    ctx.globalCompositeOperation = "lighter";
    for (const ring of this.rings) {
      if (ring.t < 0) continue;
      const t = clamp(ring.t / ring.duration);
      const r = R * 0.4 + easeOutExpo(t) * reach;
      const fade = Math.pow(1 - t, 1.6);

      // Onda de choque: faixa larga com gradiente.
      const thickness = ring.width * (1 + t * 3);
      const grad = ctx.createRadialGradient(cx, cy, Math.max(0, r - thickness * 2.5), cx, cy, r + thickness);
      grad.addColorStop(0, `rgba(${ring.color},0)`);
      grad.addColorStop(0.75, `rgba(${ring.color},${0.35 * fade})`);
      grad.addColorStop(0.92, `rgba(${WHITE},${0.85 * fade})`);
      grad.addColorStop(1, `rgba(${ring.color},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, r + thickness, 0, TAU);
      ctx.fill();
    }
  }

  // Distorção: o portal é redesenhado sobre si mesmo levemente ampliado e girado.
  drawDistortion(c, pulse) {
    const { ctx, canvas, dpr, cx, cy, R } = this;
    let k = Math.max(0, (c - 0.7) / 0.3);
    if (this.phase === PHASE.ACTIVATED) k = Math.max(k, 1 - clamp(this.explodeTime / 0.9));
    if (k < 0.02) return;

    const half = R * 1.55;
    const wobble = 0.5 + 0.5 * Math.sin(this.time * 21);
    const scale = 1 + (0.025 + pulse * 0.02) * k * (0.6 + wobble * 0.4);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.16 * k;
    ctx.translate(cx, cy);
    ctx.rotate(Math.sin(this.time * 7) * 0.02 * k);
    ctx.scale(scale, scale);
    const sx = (cx - half + this.shakeX) * dpr;
    const sy = (cy - half + this.shakeY) * dpr;
    ctx.drawImage(canvas, sx, sy, half * 2 * dpr, half * 2 * dpr, -half, -half, half * 2, half * 2);
    ctx.restore();
  }

  drawFlash() {
    if (this.phase !== PHASE.ACTIVATED) return;
    const t = this.explodeTime;
    if (t > 1.2) return;
    const { ctx, width, height, cx, cy } = this;
    ctx.globalCompositeOperation = "lighter";
    const white = Math.pow(clamp(1 - t / 0.55), 2);
    if (white > 0) {
      ctx.globalAlpha = white;
      ctx.fillStyle = "rgb(255,250,235)";
      ctx.fillRect(0, 0, width, height);
    }
    const tint = clamp(1 - t / 1.2) * 0.5;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.hypot(width, height) * 0.6);
    grad.addColorStop(0, `rgba(${GOLD},${tint})`);
    grad.addColorStop(0.5, `rgba(${PURPLE},${tint * 0.5})`);
    grad.addColorStop(1, `rgba(${BLUE},0)`);
    ctx.globalAlpha = 1;
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);
  }
}
