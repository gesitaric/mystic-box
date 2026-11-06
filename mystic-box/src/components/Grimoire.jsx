import { useCallback, useEffect, useMemo, useState } from "react";
import Modal from "./Modal";
import { ELEMENT_STYLE, STATUS_ICON, TARGET_LABELS } from "./battle/battlePresentation";
import "../styles/grimoire.css";

// Grimório: ajuda com todas as regras do jogo. Só apresentação: os números
// (chances, preços, custos, multiplicadores...) vêm de GET /rules, calculados
// pelas mesmas regras que o servidor aplica.

let rulesRequest = null;

function loadRules(apiUrl) {
  if (!rulesRequest) {
    rulesRequest = fetch(`${apiUrl}/rules`)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load the rules (${response.status}).`);
        return response.json();
      })
      .catch((error) => {
        rulesRequest = null;
        throw error;
      });
  }
  return rulesRequest;
}

function useRules(apiUrl) {
  const [state, setState] = useState({ rules: null, error: "" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    loadRules(apiUrl).then(
      (rules) => active && setState({ rules, error: "" }),
      (error) => {
        console.error(error);
        if (active) setState({ rules: null, error: "The grimoire could not be opened." });
      }
    );
    return () => {
      active = false;
    };
  }, [apiUrl, attempt]);

  const retry = useCallback(() => {
    setState({ rules: null, error: "" });
    setAttempt((value) => value + 1);
  }, []);

  return { ...state, retry };
}

function formatDuration(seconds) {
  if (seconds % 3600 === 0) {
    const hours = seconds / 3600;
    return `${hours} hour${hours === 1 ? "" : "s"}`;
  }
  if (seconds % 60 === 0) return `${seconds / 60} minutes`;
  return `${seconds} seconds`;
}

function formatPrice({ min, max }) {
  return min === max ? `${min}` : `${min}–${max}`;
}

function Stars({ count }) {
  return (
    <span className={`gr-stars is-r${count}`} aria-label={`${count} stars`}>
      {"★".repeat(count)}
    </span>
  );
}

function Shards({ children }) {
  return (
    <span className="gr-shards">
      <span aria-hidden="true">✧</span> {children}
    </span>
  );
}

function ChanceBars({ chances }) {
  return (
    <ul className="gr-chances">
      {chances.map((entry) => (
        <li key={entry.rarity}>
          <Stars count={entry.rarity} />
          <span className="gr-chance-track" aria-hidden="true">
            <span
              className={`gr-chance-fill is-r${entry.rarity}`}
              style={{ width: `${entry.chance}%` }}
            />
          </span>
          <span className="gr-chance-value">{entry.chance}%</span>
        </li>
      ))}
    </ul>
  );
}

function AetherPips({ filled, max, label }) {
  return (
    <span className="gr-pips" role="img" aria-label={label}>
      {Array.from({ length: max }, (_, index) => (
        <span key={index} className={`gr-pip${index < filled ? " is-filled" : ""}`} />
      ))}
    </span>
  );
}

function Tip({ children }) {
  return (
    <p className="gr-tip">
      <span className="gr-tip-icon" aria-hidden="true">
        ✦
      </span>
      <span>{children}</span>
    </p>
  );
}

// ------------------------------------------------------------- capítulos ---

function StartChapter({ rules, go }) {
  const { summon, battle } = rules;
  const loop = [
    { icon: "🌀", title: "Summon", text: `${summon.cardsPerSummon} free cards every ${formatDuration(summon.cooldownSeconds)}.`, to: "summon" },
    { icon: "🗂️", title: "Collect", text: "Keep your pulls, or trade them with other players in the shop.", to: "shop" },
    { icon: "⚔️", title: "Battle", text: `Pick ${battle.teamSize} cards and fight the computer.`, to: "battle" },
    { icon: "⬆️", title: "Level up", text: "Experience raises your level, stats and rewards.", to: "progression" },
    { icon: "✧", title: "Earn Shards", text: "Level up and sell cards to other players to earn Arcane Shards.", to: "shop" },
  ];

  return (
    <>
      <p className="gr-lead">
        Mystic Box is a cycle: every step feeds the next. Tap a step to read its page.
      </p>
      <ol className="gr-loop">
        {loop.map((step, index) => (
          <li key={step.title}>
            <button type="button" className="gr-loop-step" onClick={() => go(step.to)}>
              <span className="gr-loop-index">{index + 1}</span>
              <span className="gr-loop-icon" aria-hidden="true">
                {step.icon}
              </span>
              <span className="gr-loop-title">{step.title}</span>
              <span className="gr-loop-text">{step.text}</span>
            </button>
          </li>
        ))}
      </ol>

      <h3 className="gr-heading">Battle in 30 seconds</h3>
      <ol className="gr-quick">
        <li>Cards act once per round, fastest (<b>Celerity</b>) first.</li>
        <li>
          Your team shares <b>Aether</b> (max {battle.aether.max}). <b>Strike</b> and{" "}
          <b>Guard</b> are free and refill it; skills spend it.
        </li>
        <li>
          Hit the element your card is strong against for{" "}
          <b>×{battle.elements.advantageMultiplier}</b> damage.
        </li>
        <li>A foe with <b>Taunt</b> must be hit first by single-target attacks.</li>
        <li>
          Knock out all {battle.teamSize} foes before round {battle.maxRounds} to win.
        </li>
      </ol>
      <button type="button" className="gr-cta" onClick={() => go("battle")}>
        Read the full battle guide →
      </button>
    </>
  );
}

function SummonChapter({ rules }) {
  const { summon } = rules;
  return (
    <>
      <p className="gr-lead">
        Activate the portal to summon <b>{summon.cardsPerSummon} different cards</b> out of{" "}
        {summon.totalCards}. The draw happens on the server, so nobody can rig it.
      </p>

      <div className="gr-columns">
        <section className="gr-panel">
          <h3 className="gr-heading">First cards</h3>
          <ChanceBars chances={summon.rarityChances} />
        </section>
        <section className="gr-panel is-highlight">
          <h3 className="gr-heading">Last card ✦ luckier</h3>
          <ChanceBars chances={summon.lastCardRarityChances} />
        </section>
      </div>

      <h3 className="gr-heading">Recharge</h3>
      <ul className="gr-list">
        <li>
          After you keep a summon, the portal recharges for{" "}
          <b>{formatDuration(summon.cooldownSeconds)}</b>.
        </li>
        <li>
          Anyone can summon without an account. You then have{" "}
          <b>{formatDuration(summon.tokenTtlSeconds)}</b> to sign in and keep the cards, or
          they are lost.
        </li>
        <li>Each summon can be kept only once.</li>
      </ul>
    </>
  );
}

function ShopChapter({ rules }) {
  const { shop } = rules;
  return (
    <>
      <p className="gr-lead">
        <b>Arcane Shards</b> <Shards /> are the currency. You earn them by leveling up and by
        selling cards to other players, and spend them buying cards other players put on sale.
      </p>

      <p className="gr-lead">
        New cards only come from <b>summons</b>. The shop is a market between players: a card
        is only for sale if someone listed it, and it goes to the first player who buys it.
      </p>

      <table className="gr-table">
        <thead>
          <tr>
            <th scope="col">Rarity</th>
            <th scope="col">Listing price (each)</th>
          </tr>
        </thead>
        <tbody>
          {shop.listingPrices.map((row) => (
            <tr key={row.rarity}>
              <td>
                <Stars count={row.rarity} />
              </td>
              <td>
                <Shards>{formatPrice(row)}</Shards>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="gr-heading">Good to know</h3>
      <ul className="gr-list">
        <li>You choose the price of each card you sell, within the range for its rarity.</li>
        <li>
          Up to <b>{shop.maxListingQuantity}</b> copies can be listed at once, and you can have
          up to <b>{shop.maxActiveListings}</b> cards on sale at the same time.
        </li>
        <li>
          A card on sale leaves your collection until it is sold or you cancel the sale; you
          cannot battle with it meanwhile.
        </li>
        <li>When a card is sold, its full price goes to your balance.</li>
        <li>The shop always offers the cheapest copy of each card first.</li>
        <li>You can only buy a card if your balance covers its price.</li>
      </ul>
    </>
  );
}

function ProgressionChapter({ rules }) {
  const { progression, battle } = rules;
  return (
    <>
      <p className="gr-lead">
        Battles give experience. Your level goes up to <b>{progression.maxLevel}</b> and every
        level makes your cards <b>{progression.levelStatBonusPercent}% stronger</b> in battle.
      </p>

      <div className="gr-formula" aria-label="Experience needed for the next level">
        <span>XP to next level</span>
        <span className="gr-formula-eq">=</span>
        <span>
          {progression.baseLevelExperience} + {progression.levelExperienceStep} × (level − 1)
        </span>
      </div>
      <div className="gr-formula" aria-label="Shards earned when reaching a level">
        <span>Shards on reaching a level</span>
        <span className="gr-formula-eq">=</span>
        <span>new level × {progression.levelUpShardsPerLevel}</span>
      </div>

      <table className="gr-table">
        <thead>
          <tr>
            <th scope="col">Level</th>
            <th scope="col">XP to next</th>
            <th scope="col">Reward on next</th>
          </tr>
        </thead>
        <tbody>
          {progression.examples.map((row) => (
            <tr key={row.level}>
              <td>{row.level}</td>
              <td>{row.experienceToNext}</td>
              <td>
                <Shards>{row.shardsOnReach}</Shards>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="gr-heading">Unlocked by level</h3>
      <ul className="gr-list">
        {battle.difficulties.map((difficulty) => (
          <li key={difficulty.id}>
            <b>{difficulty.label}</b> difficulty: level {difficulty.minLevel}
          </li>
        ))}
      </ul>
    </>
  );
}

// --------------------------------------------------------------- batalha ---

const BATTLE_PAGES = [
  { id: "flow", label: "Turns" },
  { id: "aether", label: "Aether" },
  { id: "damage", label: "Damage" },
  { id: "elements", label: "Elements" },
  { id: "archetypes", label: "Classes" },
  { id: "effects", label: "Effects" },
  { id: "difficulty", label: "Rewards" },
];

function FlowPage({ battle }) {
  const steps = [
    {
      title: "Assemble",
      text: `Choose ${battle.teamSize} different cards and a difficulty. The foe team is drawn by the server.`,
    },
    {
      title: "Round starts",
      text: "Every living card lines up by Celerity (fastest first, ties at random). Each acts once.",
    },
    {
      title: "Turn starts",
      text: `Your team gains ${battle.aether.perTurn} Aether. Guard fades, Burn hurts, Regen heals, a Stunned card loses its turn.`,
    },
    {
      title: "Act",
      text: "Pick a skill and a target, or press Auto and let the arcane AI choose for you.",
    },
    {
      title: "Next",
      text: "Effects tick down at the end of the acting card's turn. When everyone has acted, a new round begins.",
    },
  ];

  return (
    <>
      <ol className="gr-timeline">
        {steps.map((step, index) => (
          <li key={step.title}>
            <span className="gr-timeline-dot">{index + 1}</span>
            <div>
              <h4>{step.title}</h4>
              <p>{step.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="gr-columns">
        <section className="gr-panel is-win">
          <h3 className="gr-heading">Victory</h3>
          <p>Every foe is knocked out.</p>
        </section>
        <section className="gr-panel is-lose">
          <h3 className="gr-heading">Defeat</h3>
          <p>
            Your whole team falls, round {battle.maxRounds} ends without a winner, or you
            forfeit.
          </p>
        </section>
      </div>
      <Tip>
        Leaving the arena does not end the battle: it waits for you on the Battle screen.
      </Tip>
    </>
  );
}

function AetherPage({ battle }) {
  const { aether, archetypes } = battle;
  const costs = [...new Set(archetypes.flatMap((a) => a.skills.map((s) => s.cost)))].sort(
    (a, b) => a - b
  );

  return (
    <>
      <p className="gr-lead">
        Aether is the team&apos;s shared mana. Spending it now or saving it for a big skill is
        the heart of every battle.
      </p>

      <div className="gr-aether-demo">
        <div>
          <span className="gr-aether-label">Battle start</span>
          <AetherPips
            filled={aether.starting}
            max={aether.max}
            label={`${aether.starting} of ${aether.max} Aether`}
          />
        </div>
        <div>
          <span className="gr-aether-label">Maximum</span>
          <AetherPips filled={aether.max} max={aether.max} label={`${aether.max} Aether`} />
        </div>
      </div>

      <ul className="gr-list">
        <li>
          <b>+{aether.perTurn}</b> at the start of each of your cards&apos; turns.
        </li>
        <li>
          <b>+{aether.basicSkillBonus}</b> extra when a card uses <b>Strike</b> or{" "}
          <b>Guard</b> (both free).
        </li>
        <li>Anything above {aether.max} is wasted, so don&apos;t sit on a full bar.</li>
      </ul>

      <h3 className="gr-heading">Skill costs</h3>
      <div className="gr-cost-row">
        {costs.map((cost) => (
          <span key={cost} className="gr-cost-chip">
            <AetherPips filled={cost} max={cost} label={`${cost} Aether`} />
            {cost}
          </span>
        ))}
      </div>
      <Tip>
        A common plan: Strike with the first card to build Aether, then fire a 5 or 7 cost
        skill with your strongest card.
      </Tip>
    </>
  );
}

function DamagePage({ battle }) {
  const { damage, elements, stats, rarityScaling } = battle;
  return (
    <>
      <div className="gr-formula is-big" aria-label="Damage formula">
        <span>Power × Skill</span>
        <span className="gr-formula-eq">×</span>
        <span>
          {damage.defenseConstant} ÷ ({damage.defenseConstant} + Defense)
        </span>
        <span className="gr-formula-eq">×</span>
        <span>Element × Effects</span>
      </div>

      <ul className="gr-list">
        <li>
          <b>Physical</b> skills use Might against Bulwark. <b>Magical</b> skills use Arcana
          against Resolve. <b>Hybrid</b> skills average both.
        </li>
        <li>The “Skill” value is the ×number in each skill&apos;s description.</li>
        <li>
          Element: ×{elements.advantageMultiplier} with advantage, ×
          {elements.disadvantageMultiplier} with disadvantage.
        </li>
        <li>Every hit varies by ±{damage.variancePercent}%.</li>
        <li>
          <b>Fate</b> is the % chance of a critical hit (max {damage.maxFate}%), which deals ×
          {damage.criticalMultiplier}.
        </li>
        <li>Shields absorb damage before Vitality.</li>
      </ul>

      <h3 className="gr-heading">Stats</h3>
      <dl className="gr-stats">
        {stats.map((stat) => (
          <div key={stat.id}>
            <dt>{stat.label}</dt>
            <dd>{stat.description}</dd>
          </div>
        ))}
      </dl>

      <h3 className="gr-heading">Rarity matters</h3>
      <table className="gr-table">
        <thead>
          <tr>
            <th scope="col">Rarity</th>
            <th scope="col">Main stats</th>
            <th scope="col">Celerity</th>
            <th scope="col">Fate</th>
            <th scope="col">Class skills</th>
          </tr>
        </thead>
        <tbody>
          {rarityScaling.map((row) => (
            <tr key={row.rarity}>
              <td>
                <Stars count={row.rarity} />
              </td>
              <td>×{row.statMultiplier}</td>
              <td>+{row.celerityBonus}</td>
              <td>+{row.fateBonus}</td>
              <td>{row.archetypeSkills}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function ElementsPage({ battle }) {
  const { elements } = battle;
  const [selected, setSelected] = useState(elements.list[0]?.id);
  const current = elements.list.find((element) => element.id === selected) ?? elements.list[0];
  const label = (id) => elements.list.find((element) => element.id === id)?.label ?? id;

  return (
    <>
      <p className="gr-lead">Tap an element to see its matchups.</p>
      <div className="gr-element-layout">
        <div className="gr-element-wheel" role="tablist" aria-label="Elements">
          {elements.list.map((element, index) => {
            const style = ELEMENT_STYLE[element.id] ?? {};
            let relation = "";
            if (current.strongAgainst.includes(element.id)) relation = " is-prey";
            else if (current.weakAgainst.includes(element.id)) relation = " is-threat";
            return (
              <button
                key={element.id}
                type="button"
                role="tab"
                aria-selected={element.id === current.id}
                className={`gr-element${element.id === current.id ? " is-selected" : ""}${relation}`}
                style={{ "--element": style.color, "--i": index, "--n": elements.list.length }}
                onClick={() => setSelected(element.id)}
              >
                <span aria-hidden="true">{style.icon}</span>
                {element.label}
              </button>
            );
          })}
        </div>

        <div
          className="gr-element-detail"
          style={{ "--element": ELEMENT_STYLE[current.id]?.color }}
        >
          <h3>
            {ELEMENT_STYLE[current.id]?.icon} {current.label}
          </h3>
          <p className="is-prey">
            <b>×{elements.advantageMultiplier}</b> against{" "}
            {current.strongAgainst.map(label).join(", ")}
          </p>
          {current.weakAgainst.length > 0 ? (
            <p className="is-threat">
              <b>×{elements.disadvantageMultiplier}</b> against{" "}
              {current.weakAgainst.map(label).join(", ")}
            </p>
          ) : (
            <p className="is-threat">
              Takes ×{elements.advantageMultiplier} from{" "}
              {current.strongAgainst.map(label).join(", ")} too: a mutual rivalry.
            </p>
          )}
          <p>
            <b>Arcanist spells:</b> {current.rider}
          </p>
        </div>
      </div>
    </>
  );
}

function SkillRow({ skill }) {
  return (
    <li className={`gr-skill${skill.supreme ? " is-supreme" : ""}`}>
      <div className="gr-skill-head">
        <span className="gr-skill-name">{skill.name}</span>
        {skill.unlockRarity && <Stars count={skill.unlockRarity} />}
        <span className="gr-skill-cost" title="Aether cost">
          {skill.cost === 0 ? "Free" : `${skill.cost} Aether`}
        </span>
      </div>
      <p>{skill.description}</p>
      <span className="gr-skill-target">{TARGET_LABELS[skill.target] ?? skill.target}</span>
    </li>
  );
}

function ArchetypesPage({ battle }) {
  const { archetypes, basicSkills } = battle;
  const [selected, setSelected] = useState(archetypes[0]?.id);
  const current = archetypes.find((a) => a.id === selected) ?? archetypes[0];
  const maxima = useMemo(() => {
    const result = {};
    for (const archetype of archetypes) {
      for (const [stat, value] of Object.entries(archetype.baseStats)) {
        result[stat] = Math.max(result[stat] ?? 0, value);
      }
    }
    return result;
  }, [archetypes]);
  const statLabel = (id) => battle.stats.find((stat) => stat.id === id)?.label ?? id;

  return (
    <>
      <p className="gr-lead">
        Every card belongs to a class. It sets the stats and the skills; rarity decides how
        many class skills the card knows (the last one is its <b>Supreme</b>).
      </p>
      <div className="gr-pills" role="tablist" aria-label="Classes">
        {archetypes.map((archetype) => (
          <button
            key={archetype.id}
            type="button"
            role="tab"
            aria-selected={archetype.id === current.id}
            className={`gr-pill${archetype.id === current.id ? " is-active" : ""}`}
            onClick={() => setSelected(archetype.id)}
          >
            {archetype.label}
          </button>
        ))}
      </div>

      <div className="gr-archetype">
        <p className="gr-archetype-desc">{current.description}</p>
        <ul className="gr-bars" aria-label={`${current.label} base stats`}>
          {Object.entries(current.baseStats).map(([stat, value]) => (
            <li key={stat}>
              <span>{statLabel(stat)}</span>
              <span className="gr-bar-track" aria-hidden="true">
                <span
                  className="gr-bar-fill"
                  style={{ width: `${(value / maxima[stat]) * 100}%` }}
                />
              </span>
            </li>
          ))}
        </ul>
        <ul className="gr-skills">
          {current.skills.map((skill) => (
            <SkillRow key={skill.id} skill={skill} />
          ))}
        </ul>
      </div>

      <h3 className="gr-heading">Every card also knows</h3>
      <ul className="gr-skills">
        {basicSkills.map((skill) => (
          <SkillRow key={skill.id} skill={skill} />
        ))}
      </ul>
    </>
  );
}

function EffectsPage({ battle }) {
  const groups = [
    { kind: "buff", title: "Blessings" },
    { kind: "debuff", title: "Curses" },
  ];
  return (
    <>
      <p className="gr-lead">
        Effects last a number of the affected card&apos;s own turns, shown on its badge.
        Some skills cleanse curses; check their descriptions in Classes.
      </p>
      {groups.map((group) => (
        <section key={group.kind}>
          <h3 className="gr-heading">{group.title}</h3>
          <ul className={`gr-effects is-${group.kind}`}>
            {battle.statuses
              .filter((status) => status.kind === group.kind)
              .map((status) => (
                <li key={status.id}>
                  <span className="gr-effect-icon" aria-hidden="true">
                    {STATUS_ICON[status.id] ?? "✦"}
                  </span>
                  <span>
                    <b>{status.label}</b>
                    <span>{status.description}</span>
                  </span>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function DifficultyPage({ battle }) {
  const { difficulties, rewards } = battle;
  return (
    <>
      <div className="gr-difficulties">
        {difficulties.map((difficulty) => (
          <section key={difficulty.id} className={`gr-difficulty is-${difficulty.id}`}>
            <h3>{difficulty.label}</h3>
            <p className="gr-difficulty-desc">{difficulty.description}</p>
            <dl>
              <div>
                <dt>Unlocks</dt>
                <dd>Level {difficulty.minLevel}</dd>
              </div>
              <div>
                <dt>Foe level</dt>
                <dd>
                  {difficulty.levelOffset === 0
                    ? "Yours"
                    : `Yours ${difficulty.levelOffset > 0 ? "+" : "−"}${Math.abs(difficulty.levelOffset)}`}
                </dd>
              </div>
              <div>
                <dt>Foe power</dt>
                <dd>{difficulty.enemyPowerPercent}%</dd>
              </div>
              <div>
                <dt>Win</dt>
                <dd>{difficulty.winExperience} XP</dd>
              </div>
            </dl>
            <ChanceBars chances={difficulty.rarityChances} />
          </section>
        ))}
      </div>

      <h3 className="gr-heading">Experience</h3>
      <ul className="gr-list">
        <li>Victory: the full experience of the difficulty.</li>
        <li>
          Defeat: {rewards.lossExperiencePercent}% of it, plus{" "}
          {rewards.lossExperiencePerDefeat} XP per foe you knocked out.
        </li>
        <li>Forfeit: {rewards.forfeitExperience} XP.</li>
        <li>Leveling up pays Arcane Shards (see Progression).</li>
      </ul>
    </>
  );
}

const BATTLE_PAGE_COMPONENTS = {
  flow: FlowPage,
  aether: AetherPage,
  damage: DamagePage,
  elements: ElementsPage,
  archetypes: ArchetypesPage,
  effects: EffectsPage,
  difficulty: DifficultyPage,
};

function BattleChapter({ rules, page, setPage }) {
  const Page = BATTLE_PAGE_COMPONENTS[page] ?? FlowPage;
  return (
    <>
      <div className="gr-pills is-sticky" role="tablist" aria-label="Battle topics">
        {BATTLE_PAGES.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={entry.id === page}
            className={`gr-pill${entry.id === page ? " is-active" : ""}`}
            onClick={() => setPage(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      <Page battle={rules.battle} />
    </>
  );
}

// ---------------------------------------------------------------- busca ---

function buildIndex(rules) {
  const { battle } = rules;
  return [
    ...battle.basicSkills.map((s) => ({ name: s.name, kind: "Skill", text: s.description, page: "archetypes" })),
    ...battle.archetypes.flatMap((a) => [
      { name: a.label, kind: "Class", text: a.description, page: "archetypes" },
      ...a.skills.map((s) => ({
        name: s.name,
        kind: `${a.label} skill · ${s.cost} Aether`,
        text: s.description,
        page: "archetypes",
      })),
    ]),
    ...battle.statuses.map((s) => ({ name: s.label, kind: "Effect", text: s.description, page: "effects" })),
    ...battle.stats.map((s) => ({ name: s.label, kind: "Stat", text: s.description, page: "damage" })),
    ...battle.elements.list.map((e) => ({ name: e.label, kind: "Element", text: e.rider, page: "elements" })),
    ...battle.difficulties.map((d) => ({ name: d.label, kind: "Difficulty", text: d.description, page: "difficulty" })),
    { name: "Aether", kind: "Resource", text: "Shared team mana spent on skills.", page: "aether" },
  ];
}

function SearchResults({ rules, query, onPick }) {
  const index = useMemo(() => buildIndex(rules), [rules]);
  const needle = query.trim().toLowerCase();
  const results = index.filter(
    (entry) =>
      entry.name.toLowerCase().includes(needle) || entry.text.toLowerCase().includes(needle)
  );

  if (results.length === 0) {
    return <p className="gr-empty">Nothing in the grimoire matches “{query}”.</p>;
  }

  return (
    <ul className="gr-results">
      {results.slice(0, 30).map((entry) => (
        <li key={`${entry.kind}:${entry.name}`}>
          <button type="button" onClick={() => onPick(entry.page)}>
            <span className="gr-result-name">{entry.name}</span>
            <span className="gr-result-kind">{entry.kind}</span>
            <span className="gr-result-text">{entry.text}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------- modal ---

const CHAPTERS = [
  { id: "start", label: "Start here", icon: "✦", component: StartChapter },
  { id: "summon", label: "Summon", icon: "🌀", component: SummonChapter },
  { id: "shop", label: "Shards & Shop", icon: "✧", component: ShopChapter },
  { id: "battle", label: "Battle", icon: "⚔️", component: BattleChapter },
  { id: "progression", label: "Progression", icon: "⬆️", component: ProgressionChapter },
];

function GrimoireModal({ apiUrl, initialChapter, onClose }) {
  const { rules, error, retry } = useRules(apiUrl);
  const [chapter, setChapter] = useState(initialChapter);
  const [battlePage, setBattlePage] = useState("flow");
  const [query, setQuery] = useState("");
  const current = CHAPTERS.find((entry) => entry.id === chapter) ?? CHAPTERS[0];
  const Chapter = current.component;

  function openBattlePage(page) {
    setQuery("");
    setChapter("battle");
    setBattlePage(page);
  }

  let body;
  if (error) {
    body = (
      <div className="gr-state">
        <p className="auth-error">{error}</p>
        <button type="button" className="keep-button" onClick={retry}>
          Try again
        </button>
      </div>
    );
  } else if (!rules) {
    body = (
      <p className="gr-state" role="status">
        Turning the pages...
      </p>
    );
  } else if (query.trim()) {
    body = <SearchResults rules={rules} query={query} onPick={openBattlePage} />;
  } else {
    body = (
      <>
        <h2 className="gr-chapter-title">
          <span aria-hidden="true">{current.icon}</span> {current.label}
        </h2>
        <Chapter rules={rules} go={setChapter} page={battlePage} setPage={setBattlePage} />
      </>
    );
  }

  return (
    <Modal label="Grimoire: game rules" className="grimoire-modal" onClose={onClose}>
      <header className="gr-header">
        <span className="gr-sigil" aria-hidden="true">
          ✦
        </span>
        <div>
          <h1 className="gr-title">Summoner&apos;s Grimoire</h1>
          <p className="gr-subtitle">Everything the arcane laws allow</p>
        </div>
        <input
          type="search"
          className="gr-search"
          placeholder="Search skills, effects..."
          aria-label="Search the rules"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={!rules}
        />
      </header>

      <div className="gr-body">
        <nav className="gr-chapters" role="tablist" aria-label="Chapters">
          {CHAPTERS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={!query && entry.id === current.id}
              className={`gr-chapter${!query && entry.id === current.id ? " is-active" : ""}`}
              onClick={() => {
                setQuery("");
                setChapter(entry.id);
              }}
            >
              <span className="gr-chapter-icon" aria-hidden="true">
                {entry.icon}
              </span>
              {entry.label}
            </button>
          ))}
        </nav>

        <div className="gr-page" key={query.trim() ? "search" : `${chapter}:${battlePage}`}>
          {body}
        </div>
      </div>
    </Modal>
  );
}

// Botão que abre o Grimório. `chapter` escolhe a página inicial (ex.: "battle"
// na arena). `variant`: "dock" (atalho da tela inicial) ou "icon" (barra do topo).
function Grimoire({ apiUrl, chapter = "start", variant = "icon" }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <>
      {variant === "dock" ? (
        <button type="button" className="dock-button" onClick={() => setOpen(true)}>
          <BookIcon size={22} />
          <span>Grimoire</span>
        </button>
      ) : (
        <button
          type="button"
          className="grimoire-icon-button"
          onClick={() => setOpen(true)}
          aria-label="Open the Grimoire (game rules)"
          title="Grimoire · how to play"
        >
          <BookIcon size={18} />
          <span className="grimoire-icon-label">Rules</span>
        </button>
      )}
      {open && <GrimoireModal apiUrl={apiUrl} initialChapter={chapter} onClose={close} />}
    </>
  );
}

function BookIcon({ size }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path
        d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <path
        d="M12 6.5l.9 1.9 2.1.3-1.5 1.4.4 2.1-1.9-1-1.9 1 .4-2.1-1.5-1.4 2.1-.3z"
        fill="currentColor"
      />
    </svg>
  );
}

export default Grimoire;
