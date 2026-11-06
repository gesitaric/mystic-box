import { useEffect, useState } from "react";
import { getCharacterImage } from "../../characterImages";
import {
  ELEMENT_STYLE,
  STAT_LABELS,
  STAT_NAMES,
  TARGET_LABELS,
} from "./battlePresentation";

function StatGrid({ stats }) {
  return (
    <dl className="battle-stats">
      {STAT_LABELS.map(([key, label]) => (
        <div key={key} className="battle-stat" title={STAT_NAMES[key]}>
          <dt>{label}</dt>
          <dd>{stats?.[key] ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SkillList({ skills }) {
  return (
    <ul className="battle-skill-list">
      {skills.map((skill) => (
        <li key={skill.id}>
          <span className="battle-skill-list-head">
            <strong>{skill.name}</strong>
            <span className="battle-skill-cost">
              {skill.cost > 0 ? `${skill.cost} ✦` : "Free"}
            </span>
            <span className="battle-skill-target">{TARGET_LABELS[skill.target]}</span>
          </span>
          <span className="battle-skill-desc">{skill.description}</span>
        </li>
      ))}
    </ul>
  );
}

export { StatGrid };

// Escolha do time e da dificuldade. Cartas, atributos, habilidades e
// dificuldades liberadas vêm da API; aqui só se escolhe.
// Sem `setup.difficulties` (duelo online) só o time é escolhido.
function TeamSetup({
  apiUrl,
  session,
  setup,
  initialTeam,
  starting,
  startError,
  onStart,
  onSessionExpired,
  startLabel = "Begin battle",
  startingLabel = "Opening the arena...",
  canStart = true,
  children,
}) {
  const teamSize = setup?.teamSize ?? 3;
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [team, setTeam] = useState(initialTeam ?? []);
  const [inspected, setInspected] = useState(initialTeam?.[0] ?? null);
  const unlockedDifficulties = (setup?.difficulties ?? []).filter((d) => d.unlocked);
  const [difficulty, setDifficulty] = useState(
    unlockedDifficulties[unlockedDifficulties.length - 1]?.id ?? "novice"
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const token = session.session.getIdToken().getJwtToken();
        const response = await fetch(`${apiUrl}/users/me/cards?sort=rarity&order=desc`, {
          headers: { Authorization: token },
        });
        if (response.status === 401) {
          onSessionExpired();
          return;
        }
        if (!response.ok) throw new Error(`Failed to load cards (${response.status}).`);
        const data = await response.json();
        if (cancelled) return;
        const usable = (data.cards ?? []).filter((card) => card.battle && card.file_name);
        setCards(usable);
        // Cartas que o jogador não tem mais saem do time sugerido.
        setTeam((current) =>
          current.filter((name) => usable.some((card) => card.file_name === name))
        );
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Could not load your cards.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, onSessionExpired]);

  function toggle(fileName) {
    setInspected(fileName);
    setTeam((current) => {
      if (current.includes(fileName)) return current.filter((name) => name !== fileName);
      if (current.length >= teamSize) return current;
      return [...current, fileName];
    });
  }

  const inspectedCard = cards.find((card) => card.file_name === inspected);
  const ready = team.length === teamSize && !starting && canStart;
  const showDifficulty = Boolean(setup?.difficulties);

  return (
    <div className="battle-setup">
      {children}
      {showDifficulty && (
        <section className="battle-panel" aria-label="Difficulty">
          <h2 className="battle-panel-title">Choose your challenge</h2>
          <div className="battle-difficulties" role="radiogroup" aria-label="Difficulty">
            {(setup?.difficulties ?? []).map((option) => (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={difficulty === option.id}
                disabled={!option.unlocked}
                className={`battle-difficulty${difficulty === option.id ? " is-active" : ""}`}
                onClick={() => setDifficulty(option.id)}
              >
                <span className="battle-difficulty-name">{option.label}</span>
                <span className="battle-difficulty-desc">
                  {option.unlocked
                    ? option.description
                    : `Unlocks at level ${option.minLevel}`}
                </span>
                {option.unlocked && (
                  <span className="battle-difficulty-meta">
                    Foes Lv {option.enemyLevel} · Win +{option.experience} XP
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="battle-panel" aria-label="Team">
        <h2 className="battle-panel-title">
          Choose {teamSize} cards{" "}
          <span className="battle-panel-count">
            {team.length}/{teamSize}
          </span>
        </h2>

        {loading && <p className="collection-status">Loading your cards...</p>}
        {!loading && error && <p className="auth-error">{error}</p>}
        {!loading && !error && cards.length < teamSize && (
          <p className="collection-status">
            You need at least {teamSize} different cards to battle. Summon or buy more
            cards first.
          </p>
        )}

        {cards.length > 0 && (
          <ul className="battle-roster">
            {cards.map((card) => {
              const position = team.indexOf(card.file_name);
              const selected = position >= 0;
              const element = ELEMENT_STYLE[card.battle.element];
              return (
                <li key={card.file_name}>
                  <button
                    type="button"
                    className={`battle-roster-card${selected ? " is-selected" : ""}`}
                    data-rarity={card.rarity}
                    style={{ "--element": element?.color }}
                    aria-pressed={selected}
                    disabled={!selected && team.length >= teamSize}
                    onClick={() => toggle(card.file_name)}
                    onMouseEnter={() => setInspected(card.file_name)}
                    onFocus={() => setInspected(card.file_name)}
                  >
                    <img src={getCharacterImage(card.file_name)} alt="" />
                    {selected && <span className="battle-roster-order">{position + 1}</span>}
                    <span className="battle-roster-name">{card.name}</span>
                    <span className="battle-roster-meta">
                      {element?.icon} {card.battle.archetypeLabel}
                    </span>
                    <span className="battle-roster-stars">{"✦".repeat(card.rarity)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {inspectedCard && (
        <section className="battle-panel battle-inspect" aria-label={`${inspectedCard.name} details`}>
          <h2 className="battle-panel-title">
            {inspectedCard.name}{" "}
            <span className="battle-inspect-sub">
              {ELEMENT_STYLE[inspectedCard.battle.element]?.icon}{" "}
              {inspectedCard.battle.elementLabel} · {inspectedCard.battle.archetypeLabel}
            </span>
          </h2>
          <p className="battle-inspect-desc">{inspectedCard.battle.archetypeDescription}</p>
          <StatGrid stats={inspectedCard.battle.stats} />
          {inspectedCard.battle.skills && <SkillList skills={inspectedCard.battle.skills} />}
        </section>
      )}

      <div className="battle-setup-actions">
        {startError && (
          <p className="auth-error" role="alert">
            {startError}
          </p>
        )}
        <button
          type="button"
          className="keep-button"
          disabled={!ready}
          onClick={() => onStart(team, difficulty)}
        >
          {starting ? startingLabel : startLabel}
        </button>
      </div>
    </div>
  );
}

export default TeamSetup;
