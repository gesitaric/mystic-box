import { useEffect, useMemo, useState } from "react";
import { getCharacterImage } from "../characterImages";
import Modal from "./Modal";
import "../styles/lore.css";

// Mapa-múndi. Regiões, posições, textos e quem vem de cada região vêm de
// `GET /world`; aqui fica só o desenho (cores por terreno, forma das ilhas).

let worldRequest = null;

function loadWorld(apiUrl) {
  if (!worldRequest) {
    worldRequest = fetch(`${apiUrl}/world`)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load the map (${response.status}).`);
        return response.json();
      })
      .catch((error) => {
        worldRequest = null;
        throw error;
      });
  }
  return worldRequest;
}

// Visual de cada terreno (apresentação).
const TERRAIN_COLORS = {
  rift: { land: "#3a1f5c", edge: "#c08cff" },
  frost: { land: "#5d7f99", edge: "#dff4ff" },
  isles: { land: "#5f86a8", edge: "#bfe3ff" },
  shadow: { land: "#2e2240", edge: "#a77bd6" },
  sky: { land: "#8f8a6a", edge: "#fff1b8" },
  meadow: { land: "#5e8a4a", edge: "#c7ec9b" },
  forest: { land: "#2f5e3a", edge: "#8fd99a" },
  holy: { land: "#9a7a35", edge: "#ffe08a" },
  blossom: { land: "#8a5470", edge: "#ffc2df" },
  city: { land: "#4b4a5e", edge: "#c9c5e8" },
  mountain: { land: "#6b5a49", edge: "#d9c3a5" },
  sea: { land: "#2f6c74", edge: "#9ef0f0" },
  volcano: { land: "#6e2a1c", edge: "#ff9b5e" },
  steam: { land: "#6b5230", edge: "#f0c27a" },
};

const MAP_WIDTH = 160;
const MAP_HEIGHT = 100;

// Número pseudoaleatório estável a partir de um texto (forma fixa por região).
function seededRandom(text) {
  let seed = 0;
  for (const char of text) seed = (seed * 31 + char.charCodeAt(0)) >>> 0;
  return () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

function blobPath(cx, cy, radius, random, points = 11) {
  const coords = [];
  for (let i = 0; i < points; i += 1) {
    const angle = (i / points) * Math.PI * 2;
    const r = radius * (0.72 + random() * 0.5);
    coords.push([cx + Math.cos(angle) * r * 1.25, cy + Math.sin(angle) * r]);
  }
  // Curvas suaves passando pelos pontos médios.
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const start = mid(coords[coords.length - 1], coords[0]);
  let path = `M${start[0].toFixed(2)},${start[1].toFixed(2)}`;
  coords.forEach((point, index) => {
    const next = mid(point, coords[(index + 1) % coords.length]);
    path += ` Q${point[0].toFixed(2)},${point[1].toFixed(2)} ${next[0].toFixed(2)},${next[1].toFixed(2)}`;
  });
  return `${path} Z`;
}

function regionShapes(region) {
  const random = seededRandom(region.id);
  const cx = (region.x / 100) * MAP_WIDTH;
  const cy = (region.y / 100) * MAP_HEIGHT;
  const size = 6 + Math.min(region.characters.length, 9) * 0.45;
  const shapes = [blobPath(cx, cy, size, random)];
  const islets = region.terrain === "isles" || region.terrain === "blossom" ? 3 : 1;
  for (let i = 0; i < islets; i += 1) {
    const angle = random() * Math.PI * 2;
    const distance = size * (1.3 + random() * 0.5);
    shapes.push(
      blobPath(
        cx + Math.cos(angle) * distance * 1.25,
        cy + Math.sin(angle) * distance,
        size * (0.25 + random() * 0.15),
        random,
        7
      )
    );
  }
  return { cx, cy, shapes };
}

function MapCanvas({ regions, selectedId, onSelect }) {
  const drawn = useMemo(
    () => regions.map((region) => ({ region, ...regionShapes(region) })),
    [regions]
  );
  const center = drawn.find(({ region }) => region.terrain === "rift");

  return (
    <div className="world-map">
      <svg
        className="world-map-svg"
        viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <radialGradient id="world-sea" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#1d1840" />
            <stop offset="100%" stopColor="#070514" />
          </radialGradient>
          <radialGradient id="world-rift-glow">
            <stop offset="0%" stopColor="#e2c6ff" stopOpacity="0.9" />
            <stop offset="60%" stopColor="#8a4dff" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#8a4dff" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={MAP_WIDTH} height={MAP_HEIGHT} fill="url(#world-sea)" />

        {center &&
          drawn
            .filter(({ region }) => region !== center.region)
            .map(({ region, cx, cy }) => (
              <line
                key={`line-${region.id}`}
                className="world-ley-line"
                x1={center.cx}
                y1={center.cy}
                x2={cx}
                y2={cy}
              />
            ))}

        {drawn.map(({ region, shapes }) => {
          const colors = TERRAIN_COLORS[region.terrain] ?? TERRAIN_COLORS.meadow;
          const selected = region.id === selectedId;
          return (
            <g key={region.id} className={`world-land${selected ? " is-selected" : ""}`}>
              {shapes.map((d, index) => (
                <path
                  key={index}
                  d={d}
                  fill={colors.land}
                  stroke={colors.edge}
                  strokeWidth={selected ? 0.7 : 0.35}
                />
              ))}
            </g>
          );
        })}

        {center && (
          <circle
            className="world-rift-glow"
            cx={center.cx}
            cy={center.cy}
            r="9"
            fill="url(#world-rift-glow)"
          />
        )}
      </svg>

      {regions.map((region) => (
        <button
          key={region.id}
          type="button"
          className={`world-region-pin${region.id === selectedId ? " is-selected" : ""}`}
          data-terrain={region.terrain}
          style={{ left: `${region.x}%`, top: `${region.y}%` }}
          onClick={() => onSelect(region.id)}
          aria-pressed={region.id === selectedId}
        >
          <span className="world-region-pin-name">{region.name}</span>
          {region.characters.length > 0 && (
            <span className="world-region-pin-count">{region.characters.length}</span>
          )}
        </button>
      ))}
    </div>
  );
}

function RegionPanel({ region }) {
  return (
    <section className="world-region" aria-live="polite">
      <header>
        <p className="world-region-epithet">{region.epithet}</p>
        <h3>{region.name}</h3>
      </header>
      <p className="world-region-description">{region.description}</p>

      {region.characters.length > 0 ? (
        <>
          <h4>Champions of this land</h4>
          <ul className="world-residents">
            {region.characters.map((character) => (
              <li key={character.file_name} data-rarity={character.rarity}>
                <img src={getCharacterImage(character.file_name)} alt="" loading="lazy" />
                <div>
                  <strong>
                    {character.name} <span>{"✦".repeat(character.rarity)}</span>
                  </strong>
                  <em>{character.title}</em>
                </div>
              </li>
            ))}
          </ul>
          <p className="world-region-hint">
            Summon a champion to read their full story in your collection.
          </p>
        </>
      ) : (
        <p className="world-region-hint">No one lives here. Only the Box.</p>
      )}
    </section>
  );
}

function WorldModal({ apiUrl, onClose }) {
  const [state, setState] = useState({ data: null, error: "" });
  const [attempt, setAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [showLegend, setShowLegend] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadWorld(apiUrl)
      .then((data) => {
        if (!cancelled) setState({ data, error: "" });
      })
      .catch((error) => {
        console.error(error);
        if (!cancelled) setState({ data: null, error: "Could not load the map." });
      });
    return () => {
      cancelled = true;
    };
  }, [apiUrl, attempt]);

  const data = state.data;
  const regions = data?.regions ?? [];
  const selected = regions.find((region) => region.id === selectedId) ?? regions[0];

  return (
    <Modal label="World map" className="world-modal" onClose={onClose}>
      <header className="auth-header world-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>{data ? data.world.name.toUpperCase() : "THE WORLD"}</h2>
        {data && <p>{data.world.epithet}</p>}
      </header>

      {!data && !state.error && (
        <p className="collection-status" role="status">
          Loading...
        </p>
      )}

      {state.error && (
        <div className="collection-status">
          <p className="auth-error">{state.error}</p>
          <button type="button" className="keep-button" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
        </div>
      )}

      {data && (
        <>
          <button
            type="button"
            className="world-legend-toggle"
            aria-expanded={showLegend}
            onClick={() => setShowLegend((open) => !open)}
          >
            {showLegend ? "▾" : "▸"} The legend of {data.world.name}
          </button>
          {showLegend && (
            <div className="story-text world-legend">
              {data.world.story.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          )}

          <div className="world-layout">
            <MapCanvas
              regions={regions}
              selectedId={selected?.id}
              onSelect={setSelectedId}
            />
            {selected && <RegionPanel region={selected} />}
          </div>
        </>
      )}
    </Modal>
  );
}

// Atalho da tela inicial que abre o mapa-múndi.
function WorldMap({ apiUrl }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" className="dock-button" onClick={() => setOpen(true)}>
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            d="M3 6.5l5.5-2 7 2.5 5.5-2v13l-5.5 2-7-2.5-5.5 2z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
          <path d="M8.5 4.5v13M15.5 7v13" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <circle cx="12" cy="11" r="1.6" fill="currentColor" />
        </svg>
        <span>World</span>
      </button>
      {open && <WorldModal apiUrl={apiUrl} onClose={() => setOpen(false)} />}
    </>
  );
}

export default WorldMap;
