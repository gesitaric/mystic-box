import { useEffect, useState } from "react";
// Imagem pronta (WebP em 2x) desenhada a partir de `world-map.svg`: desenhar o
// SVG com tantos brilhos e desfoques no navegador deixa o mapa pesado.
import worldMapArt from "../assets/world-map.webp";
import { getCharacterImage } from "../characterImages";
import Modal from "./Modal";
import "../styles/lore.css";

// Mapa-múndi. Regiões, posições, textos, crônica e quem vem de cada região vêm
// de `GET /world`; quais cartas o jogador já tem vêm de `GET /users/me/cards`.
// Aqui fica só a apresentação (a ilustração e onde pôr os rótulos).

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

// Cartas que o jogador já tem (só para marcar quem foi descoberto).
function useOwnedCards(apiUrl, session) {
  const [owned, setOwned] = useState(null);

  useEffect(() => {
    if (!session) return undefined;
    let cancelled = false;
    const token = session.session.getIdToken().getJwtToken();
    fetch(`${apiUrl}/users/me/cards`, { headers: { Authorization: token } })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data) setOwned(new Set(data.cards.map((card) => card.file_name)));
      })
      .catch((error) => console.error(error));
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session]);

  return owned;
}

// Rótulo um pouco abaixo do centro da região, para não cobrir o desenho dela.
function pinStyle(region) {
  return {
    left: `${region.x}%`,
    top: `${Math.min(region.y + 6.5, 94)}%`,
  };
}

function MapCanvas({ regions, selectedId, owned, onSelect }) {
  return (
    <div className="world-map">
      <img
        className="world-map-art"
        src={worldMapArt}
        alt="Illustrated map of the Shattered Realms of Aethra"
        width="1600"
        height="1000"
        decoding="async"
        draggable="false"
      />
      {regions.map((region) => {
        const found = owned
          ? region.characters.filter((c) => owned.has(c.file_name)).length
          : null;
        const selected = region.id === selectedId;
        return (
          <button
            key={region.id}
            type="button"
            className={`world-region-pin${selected ? " is-selected" : ""}`}
            data-element={region.element ?? "rift"}
            style={pinStyle(region)}
            onClick={() => onSelect(region.id)}
            aria-pressed={selected}
          >
            <span className="world-region-pin-name">{region.name}</span>
            {region.characters.length > 0 && (
              <span className="world-region-pin-count">
                {found != null ? `${found}/${region.characters.length}` : region.characters.length}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function RegionPanel({ region, owned }) {
  const found = owned ? region.characters.filter((c) => owned.has(c.file_name)).length : null;

  return (
    <section className="world-region" aria-live="polite">
      <header>
        <p className="world-region-epithet">
          {region.epithet}
          {region.element && <span className="story-element">{region.element}</span>}
        </p>
        <h3>{region.name}</h3>
      </header>
      <p className="world-region-description">{region.description}</p>
      {region.whisper && (
        <blockquote className="world-whisper">
          <span>Whispers</span>
          {region.whisper}
        </blockquote>
      )}

      {region.characters.length > 0 ? (
        <>
          <h4>
            Champions of this land
            {found != null && (
              <span className="world-found">
                {found}/{region.characters.length} summoned
              </span>
            )}
          </h4>
          <ul className="world-residents">
            {region.characters.map((character) => {
              const missing = owned && !owned.has(character.file_name);
              return (
                <li
                  key={character.file_name}
                  data-rarity={character.rarity}
                  className={missing ? "is-missing" : undefined}
                >
                  <img src={getCharacterImage(character.file_name)} alt="" loading="lazy" />
                  <div>
                    <strong>
                      {character.name} <span>{"✦".repeat(character.rarity)}</span>
                    </strong>
                    <em>{character.title}</em>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="world-region-hint">
            Summon a champion to read their full story, bonds and secret chapter in your
            collection.
          </p>
        </>
      ) : (
        <p className="world-region-hint">No one lives here. Only the Box.</p>
      )}
    </section>
  );
}

function Chronicle({ world, chronicle }) {
  return (
    <div className="world-chronicle">
      <div className="story-text world-legend">
        {world.story.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
      <ol className="world-timeline">
        {chronicle.map((entry) => (
          <li key={entry.title}>
            <span className="world-timeline-era">{entry.era}</span>
            <strong>{entry.title}</strong>
            <p>{entry.text}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function WorldModal({ apiUrl, session, onClose }) {
  const [state, setState] = useState({ data: null, error: "" });
  const [attempt, setAttempt] = useState(0);
  const [selectedId, setSelectedId] = useState("riftheart");
  const [tab, setTab] = useState("map");
  const owned = useOwnedCards(apiUrl, session);

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
          <div className="world-tabs" role="tablist">
            {[
              ["map", "Map"],
              ["chronicle", "Chronicle"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                className={tab === id ? "is-active" : undefined}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "map" ? (
            <div className="world-layout">
              <MapCanvas
                regions={regions}
                selectedId={selected?.id}
                owned={owned}
                onSelect={setSelectedId}
              />
              {selected && <RegionPanel region={selected} owned={owned} />}
            </div>
          ) : (
            <Chronicle world={data.world} chronicle={data.chronicle ?? []} />
          )}
        </>
      )}
    </Modal>
  );
}

// Atalho da tela inicial que abre o mapa-múndi.
function WorldMap({ apiUrl, session }) {
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
      {open && <WorldModal apiUrl={apiUrl} session={session} onClose={() => setOpen(false)} />}
    </>
  );
}

export default WorldMap;
