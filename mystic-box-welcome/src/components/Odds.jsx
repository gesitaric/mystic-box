import { GAME_URL } from "../api.js";
import { formatDuration, stars } from "../format.js";

// Chances do sorteio exatamente como o servidor as calcula (GET /rules -> summon).
function Bars({ chances, label }) {
  return (
    <div className="odds-column">
      <h3>{label}</h3>
      <ul className="odds-bars">
        {chances.map((entry) => (
          <li key={entry.rarity} data-rarity={entry.rarity}>
            <span className="odds-stars">{stars(entry.rarity)}</span>
            <span className="odds-track">
              <span className="odds-fill" style={{ "--value": `${entry.chance}%` }} />
            </span>
            <span className="odds-value">{entry.chance}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Odds({ rules, status }) {
  if (status === "error") return null;
  const summon = rules?.summon;

  return (
    <section className="section" id="odds">
      <header className="section-head reveal">
        <p className="eyebrow">Inside the Box</p>
        <h2 className="section-title gilded">No hidden odds</h2>
        <p className="section-lede">
          These are the real chances, read live from the game server. The same numbers sit in the
          Grimoire, the in-game book of rules.
        </p>
      </header>

      {summon ? (
        <div className="odds reveal">
          <Bars
            chances={summon.rarityChances}
            label={summon.cardsPerSummon > 2 ? `Cards 1 to ${summon.cardsPerSummon - 1}` : "First card"}
          />
          <Bars chances={summon.lastCardRarityChances} label="The last card" />
          <ul className="odds-facts">
            <li>
              <strong>{summon.cardsPerSummon}</strong>
              <span>champions per summon</span>
            </li>
            <li>
              <strong>{formatDuration(summon.cooldownSeconds)}</strong>
              <span>between summons</span>
            </li>
            <li>
              <strong>{summon.totalCards}</strong>
              <span>champions in the Box</span>
            </li>
            <li>
              <strong>×{summon.omen.summonMultiplier}</strong>
              <span>for champions of the omen&apos;s realm</span>
            </li>
          </ul>
          <a className="button center" href={GAME_URL}>
            Try your luck
          </a>
        </div>
      ) : (
        <div className="skeleton-lines reveal" aria-label="Loading the odds">
          <span />
          <span />
          <span />
        </div>
      )}
    </section>
  );
}
