import GachaCard from "./GachaCard";

function SummonSpread({ cards, flippedCount, charging, onFlip }) {
  const center = (cards.length - 1) / 2;

  return (
    <div className="summon-spread" aria-label="Cartas invocadas">
      {cards.map((card, index) => {
        const flipped = index < flippedCount;
        const isNext = index === flippedCount;
        const isFinal = index === cards.length - 1;

        const className = [
          "spread-card",
          flipped && "flipped",
          isNext && !charging && "next",
          isNext && charging && "charging",
          isFinal && "final",
        ]
          .filter(Boolean)
          .join(" ");

        return (
          <div
            key={`${card.file_name}-${index}`}
            className={className}
            data-rarity={flipped ? card.rarity ?? 0 : undefined}
            style={{
              // As cartas saem do centro (da caixa) para suas posições.
              "--from-x": `${(center - index) * 110}%`,
              animationDelay: `${index * 0.15}s`,
            }}
          >
            <div className="spread-card-inner">
              <button
                type="button"
                className="spread-face spread-back"
                onClick={onFlip}
                disabled={!isNext || charging}
                tabIndex={flipped ? -1 : 0}
                aria-label={`Virar carta ${index + 1}`}
              >
                <span className="spread-sigil" aria-hidden="true">
                  ✦
                </span>
              </button>

              <GachaCard
                card={card}
                className="spread-face spread-front"
                showAura={false}
                interactive={flipped}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default SummonSpread;
