import { useLayoutEffect, useRef } from "react";
import GachaCard from "./GachaCard";

// Intervalo entre as cartas saindo do portal.
const EMERGE_STAGGER_S = 0.32;

// `getOrigin()` devolve o ponto (na janela) de onde as cartas saem, ex.: o centro
// do portal; `onEmerge(index)` avisa quando cada carta começa a sair.
function SummonSpread({ cards, flippedCount, charging, onFlip, getOrigin, onEmerge }) {
  const center = (cards.length - 1) / 2;
  const cardRefs = useRef([]);
  const fromPortal = Boolean(getOrigin);

  // Distância de cada carta até o portal, medida antes da primeira pintura.
  useLayoutEffect(() => {
    const origin = getOrigin?.();
    if (!origin) return;
    cardRefs.current.forEach((el) => {
      if (!el) return;
      const rect = el.getBoundingClientRect();
      el.style.setProperty("--emerge-x", `${origin.x - (rect.left + rect.width / 2)}px`);
      el.style.setProperty("--emerge-y", `${origin.y - (rect.top + rect.height / 2)}px`);
    });
  }, [getOrigin, cards]);

  return (
    <div
      className={fromPortal ? "summon-spread from-portal" : "summon-spread"}
      aria-label="Summoned cards"
    >
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
            ref={(el) => {
              cardRefs.current[index] = el;
            }}
            className={className}
            onAnimationStart={(event) => {
              if (event.target === event.currentTarget && event.animationName === "portalEmerge") {
                onEmerge?.(index);
              }
            }}
            data-rarity={flipped ? card.rarity ?? 0 : undefined}
            style={{
              // As cartas saem do centro (da caixa) para suas posições.
              "--from-x": `${(center - index) * 110}%`,
              animationDelay: `${index * (fromPortal ? EMERGE_STAGGER_S : 0.15)}s`,
            }}
          >
            <div className="spread-card-inner">
              <button
                type="button"
                className="spread-face spread-back"
                onClick={onFlip}
                disabled={!isNext || charging}
                tabIndex={flipped ? -1 : 0}
                aria-label={`Flip card ${index + 1}`}
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
