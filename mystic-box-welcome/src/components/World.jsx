import { useState } from "react";
import worldMap from "../../../mystic-box/src/assets/world-map.webp";
import { getCharacterImage } from "../characterImages.js";
import { stars } from "../format.js";

// O mapa do jogo (desenhado para as posições x/y de GET /world) com os
// marcadores por cima. Clicar numa região mostra o que a API conta dela.
export default function World({ world, status }) {
  const regions = world?.regions ?? [];
  const omenRegion = world?.omen?.region;
  const [selectedId, setSelectedId] = useState(null);
  const selected = regions.find((r) => r.id === (selectedId ?? omenRegion)) ?? regions[0];

  if (status === "error") return null;

  return (
    <section className="section" id="world">
      <header className="section-head reveal">
        <p className="eyebrow">{world?.world?.epithet ?? "The Shattered Realms"}</p>
        <h2 className="section-title gilded">The world of {world?.world?.name ?? "Aethra"}</h2>
        {world?.world?.story?.[0] && <p className="section-lede">{world.world.story[0]}</p>}
      </header>

      <div className="atlas reveal">
        <div className="atlas-map">
          <img src={worldMap} alt="Illustrated map of the Shattered Realms" width="1600" height="1000" loading="lazy" />
          {regions.map((region) => (
            <button
              type="button"
              key={region.id}
              className={`atlas-pin${region.id === selected?.id ? " is-selected" : ""}${
                region.id === omenRegion ? " is-omen" : ""
              }`}
              data-element={region.element ?? "rift"}
              data-edge={region.x > 78 ? "right" : region.x < 18 ? "left" : undefined}
              style={{ left: `${region.x}%`, top: `${region.y}%` }}
              onClick={() => setSelectedId(region.id)}
              aria-pressed={region.id === selected?.id}
            >
              <span className="atlas-pin-dot" aria-hidden="true" />
              <span className="atlas-pin-label">{region.name}</span>
            </button>
          ))}
        </div>

        {selected && (
          <article className="atlas-panel" data-element={selected.element ?? "rift"} key={selected.id}>
            <p className="eyebrow">{selected.epithet}</p>
            <h3>{selected.name}</h3>
            <div className="atlas-tags">
              {selected.element && <span className="tag">{selected.element}</span>}
              {selected.id === omenRegion && <span className="tag tag-omen">Omen of the week</span>}
            </div>
            <p>{selected.description}</p>
            {selected.whisper && <blockquote>“{selected.whisper}”</blockquote>}
            {selected.resonance && (
              <p className="atlas-resonance">
                <strong>{selected.resonance.name}.</strong> {selected.resonance.description}
              </p>
            )}
            {selected.characters.length > 0 ? (
              <ul className="atlas-residents">
                {selected.characters.map((c) => (
                  <li key={c.file_name} data-rarity={c.rarity}>
                    {getCharacterImage(c.file_name) && (
                      <img src={getCharacterImage(c.file_name)} alt="" loading="lazy" />
                    )}
                    <span>
                      <strong>{c.name}</strong>
                      <small>
                        {stars(c.rarity)} · {c.title}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="atlas-empty">No one lives here. Everyone who has seen it dreams about it.</p>
            )}
          </article>
        )}
      </div>
    </section>
  );
}
