import { useEffect, useState } from "react";
import { getCharacterImage } from "../../characterImages";
import { SessionExpired } from "./arenaApi";

// Campanha pelo mapa: regiões, fases, inimigos e recompensas vêm de
// `GET /users/me/campaign`. Aqui só se escolhe a fase.
function CampaignPanel({ request, initialRegion, onChooseStage }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [regionId, setRegionId] = useState(initialRegion ?? null);

  useEffect(() => {
    let cancelled = false;
    request("/users/me/campaign")
      .then(({ ok, data: body }) => {
        if (cancelled) return;
        if (!ok) throw new Error(body.message ?? "Could not load the campaign.");
        setData(body);
      })
      .catch((loadError) => {
        if (loadError instanceof SessionExpired || cancelled) return;
        console.error(loadError);
        setError("Could not load the campaign.");
      });
    return () => {
      cancelled = true;
    };
  }, [request]);

  if (error) {
    return (
      <p className="auth-error" role="alert">
        {error}
      </p>
    );
  }
  if (!data) {
    return (
      <p className="collection-status" role="status">
        Loading the campaign...
      </p>
    );
  }

  const region = data.regions.find((r) => r.region === regionId) ?? null;

  if (!region) {
    return (
      <div className="campaign">
        <p className="campaign-lead">
          Travel the Shattered Realms. Each land has three battles and a champion waiting at the
          end. The first victory in each battle pays a reward.
        </p>
        <ul className="campaign-regions">
          {data.regions.map((r) => (
            <li key={r.region}>
              <button
                type="button"
                className={`campaign-region${r.complete ? " is-complete" : ""}`}
                onClick={() => setRegionId(r.region)}
              >
                <strong>{r.regionName}</strong>
                <span className="campaign-region-progress">
                  {Array.from({ length: r.total }, (_, i) => (
                    <span key={i} className={i < r.cleared ? "is-cleared" : undefined}>
                      {i === r.total - 1 ? "♛" : "✦"}
                    </span>
                  ))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="campaign">
      <button type="button" className="session-button" onClick={() => setRegionId(null)}>
        ← All lands
      </button>
      <h2 className="campaign-title">
        {region.regionName}{" "}
        <span>
          {region.cleared}/{region.total}
        </span>
      </h2>
      <ol className="campaign-stages">
        {region.stages.map((stage) => (
          <li
            key={stage.stage}
            className={[
              "campaign-stage",
              stage.cleared && "is-cleared",
              !stage.unlocked && "is-locked",
              stage.boss && "is-boss",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <header>
              <span className="campaign-stage-number">
                {stage.boss ? "♛ Champion" : `Battle ${stage.stage}`}
              </span>
              <strong>{stage.name}</strong>
              {stage.cleared && <span className="campaign-stage-check">✓</span>}
            </header>
            <p>{stage.intro}</p>
            <div className="campaign-stage-foes">
              {stage.enemies.map((enemy) => (
                <img
                  key={enemy.file_name}
                  src={getCharacterImage(enemy.file_name)}
                  alt={enemy.name}
                  title={`${enemy.name} ${"✦".repeat(enemy.rarity)}`}
                  loading="lazy"
                />
              ))}
              <span className="campaign-stage-meta">
                Foes Lv {stage.enemyLevel} · +{stage.experience} XP
                {!stage.cleared && <> · first win ✧ {stage.reward}</>}
              </span>
            </div>
            <button
              type="button"
              className="keep-button"
              disabled={!stage.unlocked}
              onClick={() => onChooseStage(region, stage)}
            >
              {!stage.unlocked ? "Locked" : stage.cleared ? "Fight again" : "Fight"}
            </button>
          </li>
        ))}
      </ol>
      {region.epilogue && (
        <blockquote className="campaign-epilogue">
          <span>Epilogue</span>
          {region.epilogue}
        </blockquote>
      )}
    </div>
  );
}

export default CampaignPanel;
