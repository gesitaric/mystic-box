import { useCallback, useEffect, useState } from "react";
// Imagem pronta (WebP em 2x) desenhada a partir de `world-map.svg`: desenhar o
// SVG com tantos brilhos e desfoques no navegador deixa o mapa pesado.
import worldMapArt from "../assets/world-map.webp";
import { getCharacterImage } from "../characterImages";
import Modal from "./Modal";
import { loadWorld } from "./worldApi";
import { currentRoute, navigate } from "../router";
import { withOverlay } from "../routes";
import "../styles/lore.css";

// Mapa-múndi. Regiões, posições, textos, crônica e quem vem de cada região vêm
// de `GET /world`; quais cartas o jogador já tem vêm de `GET /users/me/cards`.
// Aqui fica só a apresentação (a ilustração e onde pôr os rótulos).

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

// Progresso da campanha (fases vencidas e epílogos) e da coleção de cada
// região, de GET /users/me/campaign.
function useCampaign(apiUrl, session) {
  const [campaign, setCampaign] = useState(null);
  const [collection, setCollection] = useState(null);

  useEffect(() => {
    if (!session) return undefined;
    let cancelled = false;
    const token = session.session.getIdToken().getJwtToken();
    fetch(`${apiUrl}/users/me/campaign`, { headers: { Authorization: token } })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setCampaign(Object.fromEntries(data.regions.map((r) => [r.region, r])));
          setCollection(Object.fromEntries((data.collection ?? []).map((r) => [r.region, r])));
        }
      })
      .catch((error) => console.error(error));
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session]);

  // Recebida a recompensa, marca a região (o servidor já gravou).
  const markClaimed = useCallback((regionId) => {
    setCollection((current) =>
      current ? { ...current, [regionId]: { ...current[regionId], claimed: true } } : current
    );
  }, []);

  return { campaign, collection, markClaimed };
}

// Coleção da região: completar paga uma recompensa única (valor do servidor).
function RegionCollection({ apiUrl, session, mastery, onClaimed }) {
  const [claiming, setClaiming] = useState(false);
  const [message, setMessage] = useState("");
  if (!mastery) return null;

  async function claim() {
    setClaiming(true);
    setMessage("");
    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/users/me/regions/claim`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ regionId: mastery.region }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setMessage(data.message ?? "Could not claim the reward.");
        return;
      }
      onClaimed(mastery.region);
      setMessage(`You earned ✧ ${data.reward}.`);
    } catch (error) {
      console.error(error);
      setMessage("Could not claim the reward.");
    } finally {
      setClaiming(false);
    }
  }

  return (
    <div className={`world-mastery${mastery.claimed ? " is-claimed" : ""}`}>
      <p>
        <span>Collection</span>
        {mastery.claimed
          ? "Every champion of this land answered your call. The land shines for you."
          : `${mastery.owned}/${mastery.total} champions summoned · complete it for ✧ ${mastery.reward}`}
      </p>
      {mastery.complete && !mastery.claimed && (
        <button type="button" className="keep-button" disabled={claiming} onClick={claim}>
          {claiming ? "Claiming..." : `Claim ✧ ${mastery.reward}`}
        </button>
      )}
      {message && (
        <p className="world-mastery-message" role="status">
          {message}
        </p>
      )}
    </div>
  );
}

// Rótulo um pouco abaixo do centro da região, para não cobrir o desenho dela.
function pinStyle(region) {
  return {
    left: `${region.x}%`,
    top: `${Math.min(region.y + 6.5, 94)}%`,
  };
}

function MapCanvas({ regions, selectedId, owned, collection, omenRegion, onSelect }) {
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
        const mastered = Boolean(collection?.[region.id]?.claimed);
        return (
          <button
            key={region.id}
            type="button"
            className={`world-region-pin${selected ? " is-selected" : ""}${
              mastered ? " is-mastered" : ""
            }${region.id === omenRegion ? " is-omen" : ""}`}
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

function RegionCampaign({ progress, onCampaign }) {
  if (!progress) return null;
  return (
    <div className="world-campaign">
      <p>
        <span>Campaign</span>
        {progress.stages.map((stage) => (
          <em key={stage.stage} className={stage.cleared ? "is-cleared" : undefined}>
            {stage.boss ? "♛" : "✦"}
          </em>
        ))}{" "}
        {progress.complete
          ? "Champion defeated"
          : `${progress.cleared}/${progress.total} battles won`}
      </p>
      {progress.epilogue && (
        <blockquote className="campaign-epilogue">
          <span>Epilogue</span>
          {progress.epilogue}
        </blockquote>
      )}
      {onCampaign && (
        <button type="button" className="keep-button" onClick={() => onCampaign(progress.region)}>
          {progress.complete ? "Fight here again" : "Fight in this land"}
        </button>
      )}
    </div>
  );
}

// Boato da semana (região em destaque): texto e efeitos vêm de GET /world.
export function OmenNote({ omen, compact = false }) {
  if (!omen) return null;
  const ends = new Date(omen.endsAt);
  return (
    <p className={`world-omen${compact ? " is-compact" : ""}`}>
      <span>
        This week in {omen.regionName}: {omen.title}
      </span>
      {!compact && omen.text}{" "}
      <em>
        Its champions are {omen.summonMultiplier}× likelier in summons and bring +
        {omen.experienceBonusPercent}% XP in battle · until{" "}
        {ends.toLocaleDateString(undefined, { weekday: "long" })}
      </em>
    </p>
  );
}

function RegionPanel({ region, owned, campaign, onCampaign, collection, omen, children }) {
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

      {region.resonance && (
        <p className="world-resonance">
          <span>✦ Resonance · {region.resonance.name}</span>
          {region.resonance.description} (a team of 3 from this land)
        </p>
      )}

      {omen?.region === region.id && <OmenNote omen={omen} />}
      <RegionCampaign progress={campaign?.[region.id]} onCampaign={onCampaign} />
      {collection && children}

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

// A aba e a região escolhida vêm do endereço (/world, /world/chronicle, /world/:region).
export function WorldModal({
  apiUrl,
  session,
  tab = "map",
  regionId,
  onTabChange,
  onSelectRegion,
  onCampaign,
  onBalanceChange,
  onClose,
}) {
  const [state, setState] = useState({ data: null, error: "" });
  const [attempt, setAttempt] = useState(0);
  const selectedId = regionId ?? "riftheart";
  const owned = useOwnedCards(apiUrl, session);
  const { campaign, collection, markClaimed } = useCampaign(apiUrl, session);

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
    <Modal label="World map" className="world-modal" routed onClose={onClose}>
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
                onClick={() => onTabChange(id)}
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
                collection={collection}
                omenRegion={data.omen?.region}
                onSelect={onSelectRegion}
              />
              {selected && (
                <RegionPanel
                  key={selected.id}
                  region={selected}
                  owned={owned}
                  campaign={campaign}
                  onCampaign={onCampaign}
                  collection={collection}
                  omen={data.omen}
                >
                  <RegionCollection
                    apiUrl={apiUrl}
                    session={session}
                    mastery={collection?.[selected.id]}
                    onClaimed={(regionId) => {
                      markClaimed(regionId);
                      onBalanceChange?.();
                    }}
                  />
                </RegionPanel>
              )}
            </div>
          ) : (
            <Chronicle world={data.world} chronicle={data.chronicle ?? []} />
          )}
        </>
      )}
    </Modal>
  );
}

// Atalho da tela inicial que abre o mapa-múndi (/world, mostrado pelo App).
function WorldMap() {
  return (
    <>
      <button
        type="button"
        className="dock-button"
        onClick={() =>
          navigate(withOverlay(currentRoute(), { name: "world", tab: "map", region: null }))
        }
      >
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
    </>
  );
}

export default WorldMap;
