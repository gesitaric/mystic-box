import { RelicIcon } from "../relicImages";

// Relíquia que o chefe de uma região dá na primeira vitória. Os dados (`relic`
// e `relicClaimed`) vêm de GET /users/me/campaign; aqui é só apresentação.
// `compact`: só imagem, nome e efeito (sem a explicação).
function CampaignRelic({ relic, claimed, regionName, compact = false }) {
  if (!relic) return null;
  const effects = [
    ...relic.bonuses.map((entry) => `+${Math.abs(entry.percent)}% ${entry.label}`),
    ...relic.penalties.map((entry) => `−${Math.abs(entry.percent)}% ${entry.label}`),
  ].join(", ");
  return (
    <div className={`campaign-relic${claimed ? " is-claimed" : ""}${compact ? " is-compact" : ""}`}>
      <RelicIcon relicId={relic.id} size={compact ? 40 : 56} className="is-large" />
      <div className="campaign-relic-text">
        <span className="campaign-relic-label">
          {claimed ? "✓ Relic claimed" : "♛ Champion's reward"}
        </span>
        <strong>{relic.name}</strong>
        <small>{effects}</small>
        {!compact && (
          <p>
            {claimed
              ? "Equip it from the Relic tab of a card in your collection, and forge more copies with Arcane Shards."
              : `Defeat the champion of ${regionName} for the first time to claim this relic.`}
          </p>
        )}
      </div>
    </div>
  );
}

export default CampaignRelic;
