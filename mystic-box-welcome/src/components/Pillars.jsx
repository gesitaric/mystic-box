import { formatDuration } from "../format.js";

// "How to play": o texto é apresentação; os números vêm de GET /rules e GET /world.
function pillars(rules, world) {
  const summon = rules?.summon;
  const battle = rules?.battle;
  const ascension = rules?.ascension;
  const pvp = rules?.pvp;
  const realms = world?.regions?.filter((r) => r.characters.length).length;

  return [
    {
      id: "summon",
      glyph: "✦",
      title: "Summon",
      text: "Open the Mystic Box and it answers with champions torn from every corner of Aethra.",
      fact: summon && `${summon.cardsPerSummon} champions every ${formatDuration(summon.cooldownSeconds)}`,
    },
    {
      id: "collect",
      glyph: "❖",
      title: "Collect & ascend",
      text: "Every champion has a story. Duplicates feed ascension, which makes them stronger and reveals a secret chapter of their past.",
      fact: ascension && `Up to ${ascension.maxLevel} ascensions per champion`,
    },
    {
      id: "battle",
      glyph: "⚔",
      title: "Battle",
      text: "Build a team, spend Aether on skills and play elements against each other. Bonded champions fight harder side by side.",
      fact: battle && `Teams of ${battle.teamSize} · ${battle.difficulties.length} difficulties`,
    },
    {
      id: "campaign",
      glyph: "⌘",
      title: "Campaign",
      text: "Cross the map of the Shattered Realms, defeat each realm's boss and read how its story ends.",
      fact: realms && `${realms} realms to conquer`,
    },
    {
      id: "duel",
      glyph: "☍",
      title: "Duel online",
      text: "Challenge summoners by name, see who is online, watch live duels and throw a reaction from the stands.",
      fact: pvp && `${formatDuration(pvp.turnSeconds)} per turn`,
    },
    {
      id: "market",
      glyph: "⚖",
      title: "Trade",
      text: "Every card in the market was summoned by a real player and listed at the price they chose. No card appears out of thin air.",
      fact: rules?.shop && `Up to ${rules.shop.maxActiveListings} active listings`,
    },
  ];
}

export default function Pillars({ rules, world }) {
  return (
    <section className="section" id="play">
      <header className="section-head reveal">
        <p className="eyebrow">How to play</p>
        <h2 className="section-title gilded">Six ways to answer the call</h2>
        <p className="section-lede">
          Mystic Box runs in your browser, on any screen. Every rule lives on the server, so every
          summon and every battle is fair.
        </p>
      </header>
      <ol className="pillars">
        {pillars(rules, world).map((pillar, index) => (
          <li
            className="pillar reveal"
            key={pillar.id}
            style={{ "--delay": `${index * 70}ms` }}
          >
            <span className="pillar-step">{String(index + 1).padStart(2, "0")}</span>
            <span className="pillar-glyph" aria-hidden="true">
              {pillar.glyph}
            </span>
            <h3>{pillar.title}</h3>
            <p>{pillar.text}</p>
            {pillar.fact && <p className="pillar-fact">{pillar.fact}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
