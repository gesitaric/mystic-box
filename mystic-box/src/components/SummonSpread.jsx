import { useEffect, useLayoutEffect, useRef } from "react";
import GachaCard from "./GachaCard";
import { createRevealAudio } from "./reveal/revealAudio";

// Intervalo entre as cartas saindo do portal.
const EMERGE_STAGGER_S = 0.32;
// Momento do giro em que a face aparece (acompanha a transição do CSS).
const FACE_VISIBLE_MS = 300;
const FINAL_FACE_VISIBLE_MS = 620;

function ensureAudio(audioRef) {
  if (!audioRef.current) audioRef.current = createRevealAudio();
  return audioRef.current;
}

// `getOrigin()` devolve o ponto (na janela) de onde as cartas saem, ex.: o centro
// do portal; `onEmerge(index)` avisa quando cada carta começa a sair.
// `fx` é a ref da camada de efeitos (RevealFx); `suspenseSeconds` é a duração
// do suspense da última carta.
function SummonSpread({
  cards,
  flippedCount,
  charging,
  onFlip,
  getOrigin,
  onEmerge,
  fx,
  suspenseSeconds = 1.6,
}) {
  const center = (cards.length - 1) / 2;
  const cardRefs = useRef([]);
  const fromPortal = Boolean(getOrigin);
  const audioRef = useRef(null);
  const timersRef = useRef([]);
  // Cartas já viradas ao montar (sorteio restaurado) não disparam efeitos.
  const shownFlips = useRef(flippedCount);

  useEffect(
    () => () => {
      timersRef.current.forEach(clearTimeout);
      audioRef.current?.destroy();
    },
    []
  );

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

  // Carta virada: som do giro e, quando a face aparece, explosão pela raridade.
  useEffect(() => {
    if (flippedCount <= shownFlips.current) {
      shownFlips.current = flippedCount;
      return;
    }
    shownFlips.current = flippedCount;

    const index = flippedCount - 1;
    const card = cards[index];
    const isFinal = cards.length > 1 && index === cards.length - 1;
    const rarity = card?.rarity ?? 1;
    ensureAudio(audioRef).flip(isFinal);

    const timer = setTimeout(
      () => {
        const el = cardRefs.current[index];
        if (el) fx?.current?.reveal(el.getBoundingClientRect(), rarity);
        ensureAudio(audioRef).reveal(rarity);
      },
      isFinal ? FINAL_FACE_VISIBLE_MS : FACE_VISIBLE_MS
    );
    timersRef.current.push(timer);
  }, [flippedCount, cards, fx]);

  // Suspense da última carta: energia convergindo e som subindo.
  useEffect(() => {
    if (!charging) return undefined;
    const layer = fx?.current;
    const el = cardRefs.current[flippedCount];
    if (el) layer?.gather(el.getBoundingClientRect());
    ensureAudio(audioRef).suspense(suspenseSeconds);
    return () => layer?.gather(null);
  }, [charging, flippedCount, fx, suspenseSeconds]);

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
                onPointerEnter={isNext && !charging ? () => ensureAudio(audioRef).hover() : undefined}
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

            {/* Clarão na cor da raridade quando a face aparece. */}
            <span className="spread-flash" aria-hidden="true" />
          </div>
        );
      })}
    </div>
  );
}

export default SummonSpread;
