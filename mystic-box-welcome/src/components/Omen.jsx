import { useEffect, useState } from "react";
import { GAME_URL } from "../api.js";
import { getCharacterImage } from "../characterImages.js";
import { countdownParts, stars } from "../format.js";

function useNow(intervalMs) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function Countdown({ endsAt }) {
  const now = useNow(1000);
  const parts = countdownParts(endsAt, now);
  if (!parts) return null;
  if (parts.done) return <p className="omen-countdown-done">A new rumor is spreading. Refresh to hear it.</p>;
  const units = [
    [parts.days, "days"],
    [parts.hours, "hours"],
    [parts.minutes, "min"],
    [parts.seconds, "sec"],
  ];
  return (
    <div className="omen-countdown" role="timer" aria-label="Time until the next omen">
      {units.map(([value, label]) => (
        <div key={label}>
          <span className="omen-countdown-value">{String(value).padStart(2, "0")}</span>
          <span className="omen-countdown-label">{label}</span>
        </div>
      ))}
    </div>
  );
}

export default function Omen({ omen, regions, status }) {
  if (status === "error") return null;
  const region = regions?.find((r) => r.id === omen?.region);

  return (
    <section className="section omen" id="omen" data-element={region?.element ?? undefined}>
      <div className="omen-card reveal">
        <div className="omen-rays" aria-hidden="true" />
        <p className="eyebrow">Omen of the week</p>
        {omen ? (
          <>
            <h2 className="omen-title gilded">{omen.title}</h2>
            <p className="omen-region">
              Rumors from <strong>{omen.regionName}</strong>
            </p>
            <p className="omen-text">{omen.text}</p>
            <ul className="omen-effects">
              <li>
                <strong>×{omen.summonMultiplier}</strong> chance to summon its champions
              </li>
              <li>
                <strong>+{omen.experienceBonusPercent}%</strong> experience for teams that bring one
              </li>
            </ul>
            {region?.characters?.length > 0 && (
              <ul className="omen-champions" aria-label={`Champions of ${omen.regionName}`}>
                {region.characters.map((c) => (
                  <li key={c.file_name} data-rarity={c.rarity} title={`${c.name}, ${c.title}`}>
                    {getCharacterImage(c.file_name) && (
                      <img src={getCharacterImage(c.file_name)} alt="" loading="lazy" />
                    )}
                    <span>{c.name}</span>
                    <small>{stars(c.rarity)}</small>
                  </li>
                ))}
              </ul>
            )}
            <p className="omen-ends">The rumor fades in</p>
            <Countdown endsAt={omen.endsAt} />
            <a className="button" href={GAME_URL}>
              Summon while it lasts
            </a>
          </>
        ) : (
          <div className="skeleton-lines" aria-label="Loading the omen">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>
    </section>
  );
}
