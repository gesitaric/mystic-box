import { useState } from "react";

// Roda dos elementos montada com GET /rules -> battle.elements:
// cada seta vai do elemento forte para o fraco. Pares que são fortes um contra
// o outro (ex.: luz e sombra) ficam no centro, ligados por uma seta dupla.
const SIZE = 360;
const CENTER = SIZE / 2;
const RADIUS = 128;

function isMutual(el, byId) {
  return (
    el.strongAgainst.length > 0 &&
    el.strongAgainst.every((target) => byId[target]?.strongAgainst.includes(el.id))
  );
}

function layout(list) {
  const byId = Object.fromEntries(list.map((el) => [el.id, el]));
  const ring = list.filter((el) => !isMutual(el, byId));
  const center = list.filter((el) => isMutual(el, byId));
  const points = {};
  ring.forEach((el, i) => {
    points[el.id] = position(i, ring.length);
  });
  center.forEach((el, i) => {
    const offset = center.length > 1 ? (i / (center.length - 1) - 0.5) * RADIUS * 0.9 : 0;
    points[el.id] = { x: CENTER + offset, y: CENTER };
  });
  return { points, byId };
}

function position(index, total) {
  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  return { x: CENTER + Math.cos(angle) * RADIUS, y: CENTER + Math.sin(angle) * RADIUS };
}

// Encurta a seta para não entrar nos círculos dos elementos.
function shorten(from, to, gap) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  return {
    x1: from.x + (dx / length) * gap,
    y1: from.y + (dy / length) * gap,
    x2: to.x - (dx / length) * gap,
    y2: to.y - (dy / length) * gap,
  };
}

export default function Elements({ rules }) {
  const elements = rules?.battle?.elements;
  const [activeId, setActiveId] = useState(null);
  if (!elements?.list?.length) return null;

  const list = elements.list;
  const { points, byId } = layout(list);
  const active = list.find((el) => el.id === activeId) ?? list[0];
  const arrows = [];
  for (const el of list) {
    for (const target of el.strongAgainst) {
      if (!points[target]) continue;
      const both = byId[target].strongAgainst.includes(el.id);
      // Seta dupla: desenha uma vez só.
      if (both && arrows.some((a) => a.from === target && a.to === el.id)) continue;
      arrows.push({ from: el.id, to: target, both });
    }
  }
  const mutualWith = active.strongAgainst.filter((id) => byId[id]?.strongAgainst.includes(active.id));
  const advantage = Math.round((elements.advantageMultiplier - 1) * 100);
  const disadvantage = Math.round((1 - elements.disadvantageMultiplier) * 100);

  return (
    <section className="section" id="elements">
      <header className="section-head reveal">
        <p className="eyebrow">The wheel of Aether</p>
        <h2 className="section-title gilded">Seven elements, one advantage</h2>
        <p className="section-lede">
          Strike a weakness for {advantage}% more damage. Strike a resistance and lose {disadvantage}%.
          Every element also leaves its mark on the target.
        </p>
      </header>

      <div className="elements reveal">
        <svg className="element-wheel" viewBox={`0 0 ${SIZE} ${SIZE}`} role="group" aria-label="Element wheel">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 10 5 0 10z" fill="currentColor" />
            </marker>
          </defs>
          <circle cx={CENTER} cy={CENTER} r={RADIUS} className="element-ring" />
          {arrows.map(({ from, to, both }) => {
            const line = shorten(points[from], points[to], 30);
            const lit = from === active.id || to === active.id;
            return (
              <line
                key={`${from}-${to}`}
                {...line}
                className={`element-arrow${lit ? " is-lit" : ""}${from === active.id ? " is-out" : ""}`}
                markerEnd="url(#arrow)"
                markerStart={both ? "url(#arrow)" : undefined}
              />
            );
          })}
          {list.map((el) => {
            const point = points[el.id];
            return (
              <g
                key={el.id}
                className={`element-node${el.id === active.id ? " is-active" : ""}`}
                data-element={el.id}
                transform={`translate(${point.x} ${point.y})`}
                tabIndex={0}
                role="button"
                aria-pressed={el.id === active.id}
                aria-label={el.label}
                onMouseEnter={() => setActiveId(el.id)}
                onFocus={() => setActiveId(el.id)}
                onClick={() => setActiveId(el.id)}
              >
                <circle r="26" />
                <text dy="4">{el.label}</text>
              </g>
            );
          })}
        </svg>

        <div className="element-card" data-element={active.id}>
          <h3>{active.label}</h3>
          <p>{active.rider}</p>
          {mutualWith.length > 0 && (
            <p className="element-mutual">
              {active.label} and {mutualWith.map(labelOf(list)).join(", ")} are strong against each other.
            </p>
          )}
          <dl>
            <div>
              <dt>Strong against</dt>
              <dd>{active.strongAgainst.map(labelOf(list)).join(", ") || "Nothing"}</dd>
            </div>
            <div>
              <dt>Weak against</dt>
              <dd>{active.weakAgainst.map(labelOf(list)).join(", ") || "Nothing"}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function labelOf(list) {
  return (id) => list.find((el) => el.id === id)?.label ?? id;
}
