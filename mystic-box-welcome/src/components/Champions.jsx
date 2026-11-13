import { useMemo, useState } from "react";
import { getCharacterImage } from "../characterImages.js";
import { stars } from "../format.js";
import { allChampions } from "../world.js";

// Inclinação 3D da carta seguindo o ponteiro (só efeito visual).
function tilt(event) {
  const card = event.currentTarget;
  const rect = card.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  card.style.setProperty("--rx", `${(0.5 - y) * 14}deg`);
  card.style.setProperty("--ry", `${(x - 0.5) * 16}deg`);
  card.style.setProperty("--mx", `${x * 100}%`);
  card.style.setProperty("--my", `${y * 100}%`);
}

function untilt(event) {
  const card = event.currentTarget;
  card.style.setProperty("--rx", "0deg");
  card.style.setProperty("--ry", "0deg");
}

function ChampionCard({ champion }) {
  const [flipped, setFlipped] = useState(false);
  const image = getCharacterImage(champion.file_name);
  return (
    <li className="champion-slot">
      <button
        type="button"
        className={`champion${flipped ? " is-flipped" : ""}`}
        data-rarity={champion.rarity}
        data-element={champion.element ?? undefined}
        onPointerMove={tilt}
        onPointerLeave={untilt}
        onClick={() => setFlipped((value) => !value)}
        aria-pressed={flipped}
        aria-label={`${champion.name}, ${champion.rarity} stars, ${champion.title}, from ${champion.regionName}`}
      >
        <span className="champion-inner">
          <span className="champion-front">
            {image && <img src={image} alt="" loading="lazy" decoding="async" />}
            <span className="champion-shine" />
            <span className="champion-plate">
              <span className="champion-stars">{stars(champion.rarity)}</span>
              <span className="champion-name">{champion.name}</span>
            </span>
          </span>
          <span className="champion-back">
            <span className="champion-back-stars">{stars(champion.rarity)}</span>
            <span className="champion-back-name">{champion.name}</span>
            <span className="champion-back-title">{champion.title}</span>
            <span className="champion-back-region">{champion.regionName}</span>
          </span>
        </span>
      </button>
    </li>
  );
}

const PAGE = 18;

export default function Champions({ world, status }) {
  const [rarity, setRarity] = useState("all");
  const [region, setRegion] = useState("all");
  const [limit, setLimit] = useState(PAGE);

  const champions = useMemo(
    () => allChampions(world).sort((a, b) => b.rarity - a.rarity || a.name.localeCompare(b.name)),
    [world],
  );
  const rarities = [...new Set(champions.map((c) => c.rarity))].sort((a, b) => b - a);
  const regions = (world?.regions ?? []).filter((r) => r.characters.length);

  const shown = champions.filter(
    (c) => (rarity === "all" || c.rarity === rarity) && (region === "all" || c.regionId === region),
  );

  if (status === "error") return null;

  const pick = (setter) => (value) => {
    setter(value);
    setLimit(PAGE);
  };

  return (
    <section className="section" id="champions">
      <header className="section-head reveal">
        <p className="eyebrow">The roster</p>
        <h2 className="section-title gilded">Champions of the Shattered Realms</h2>
        <p className="section-lede">
          Knights, witches, dragons and things that should have stayed asleep. Tap a card to see who
          they are. Their full stories wait in your collection.
        </p>
      </header>

      <div className="filters reveal" role="group" aria-label="Filter champions">
        <div className="chips">
          <Chip active={rarity === "all"} onClick={() => pick(setRarity)("all")}>
            All
          </Chip>
          {rarities.map((r) => (
            <Chip key={r} active={rarity === r} onClick={() => pick(setRarity)(r)} rarity={r}>
              {stars(r)}
            </Chip>
          ))}
        </div>
        <label className="select">
          <span className="sr-only">Realm</span>
          <select value={region} onChange={(e) => pick(setRegion)(e.target.value)}>
            <option value="all">Every realm</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {champions.length === 0 ? (
        <ul className="champion-grid" aria-label="Loading champions">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i} className="champion-slot">
              <span className="champion champion-skeleton" />
            </li>
          ))}
        </ul>
      ) : (
        <>
          <ul className="champion-grid">
            {shown.slice(0, limit).map((champion) => (
              <ChampionCard key={champion.file_name} champion={champion} />
            ))}
          </ul>
          <p className="champion-count">
            Showing {Math.min(limit, shown.length)} of {shown.length}
            {shown.length < champions.length ? ` (${champions.length} in total)` : ""}
          </p>
          {shown.length > limit && (
            <button type="button" className="button button-ghost center" onClick={() => setLimit(shown.length)}>
              Reveal all {shown.length}
            </button>
          )}
        </>
      )}
    </section>
  );
}

function Chip({ active, onClick, rarity, children }) {
  return (
    <button
      type="button"
      className={`chip${active ? " is-active" : ""}`}
      aria-pressed={active}
      data-rarity={rarity}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
