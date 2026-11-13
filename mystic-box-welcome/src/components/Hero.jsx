import { useEffect, useMemo, useState } from "react";
import { GAME_URL } from "../api.js";
import { getCharacterImage } from "../characterImages.js";
import { stars } from "../format.js";
import { allChampions, hash } from "../world.js";

// A cada ciclo, três personagens saem da caixa. A ordem "embaralhada" é estável
// (hash do nome) e só serve para variar a vitrine.
const CYCLE_MS = 5200;

export default function Hero({ world, rules }) {
  const champions = useMemo(
    () =>
      allChampions(world)
        .filter((c) => getCharacterImage(c.file_name))
        .sort((a, b) => hash(a.name) - hash(b.name)),
    [world],
  );
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
    const id = setInterval(() => setTick((value) => value + 1), CYCLE_MS);
    return () => clearInterval(id);
  }, []);

  const trio = champions.length >= 3
    ? [0, 1, 2].map((i) => champions[(tick * 3 + i) % champions.length])
    : [];

  const stats = [
    world && [world.regions.reduce((sum, r) => sum + r.characters.length, 0), "champions"],
    world && [world.regions.filter((r) => r.characters.length).length, "realms"],
    rules && [rules.battle.elements.list.length, "elements"],
    rules && [rules.battle.archetypes.length, "archetypes"],
  ].filter(Boolean);

  return (
    <section className="hero" id="top">
      <div className="hero-copy">
        <p className="eyebrow">A card-summoning game of the Shattered Realms</p>
        <h1 className="hero-title">
          <span className="gilded">Mystic Box</span>
        </h1>
        <p className="hero-lede">
          {world?.world?.story?.[2] ??
            "The Box drifts in the crater where the world broke, calling champions from every realm and binding them into cards for the summoners it chooses."}
        </p>
        <div className="hero-actions">
          <a className="button" href={GAME_URL}>
            Open the Box
          </a>
          <a className="button button-ghost" href="#releases">
            What&apos;s new
          </a>
        </div>
        {stats.length > 0 && (
          <dl className="hero-stats">
            {stats.map(([value, label]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      <div className="hero-stage" aria-hidden="true">
        <div className="hero-sigil" />
        <div className="hero-beam" />
        <div className="box-scene">
          <div className="box">
            <div className="box-face box-front" />
            <div className="box-face box-back" />
            <div className="box-face box-left" />
            <div className="box-face box-right" />
            <div className="box-face box-bottom" />
            <div className="box-lid">
              <div className="box-face box-top" />
            </div>
          </div>
        </div>
        <div className="hero-cards" key={tick}>
          {trio.map((champion, index) => (
            <figure className={`hero-card hero-card-${index}`} data-rarity={champion.rarity} key={champion.file_name}>
              <img src={getCharacterImage(champion.file_name)} alt="" />
              <figcaption>
                <span className="hero-card-stars">{stars(champion.rarity)}</span>
                <span className="hero-card-name">{champion.name}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>

      <a className="scroll-hint" href="#omen" aria-label="Scroll to the omen of the week">
        <span />
      </a>
    </section>
  );
}
