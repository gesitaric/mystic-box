
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterImage } from "../characterImages";

export function CardFace({ card, image, rarity }) {
  return (
    <div className={`card-content ${image ? "has-image" : ""}`}>
      {image ? (
        <img className="character-image" src={image} alt={card.name} />
      ) : (
        <div className="character">🧚</div>
      )}
      <div className="rarity">{"✦ ".repeat(rarity).trim()}</div>
      <div className="name">{(card?.name ?? "???").toUpperCase()}</div>
    </div>
  );
}

function GachaCard({ card }) {
  const [expanded, setExpanded] = useState(false);
  const image = getCharacterImage(card?.file_name);
  const rarity = card?.rarity ?? 0;

  useEffect(() => {
    if (!expanded) return;

    function handleKeyDown(event) {
      if (event.key === "Escape") setExpanded(false);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [expanded]);

  function handleCardKeyDown(event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setExpanded(true);
    }
  }

  return (
    <>
      <div
        className="card"
        role="button"
        tabIndex={0}
        data-rarity={rarity}
        aria-label={`Ampliar carta de ${card?.name ?? "???"}`}
        onClick={() => setExpanded(true)}
        onKeyDown={handleCardKeyDown}
      >
        {rarity >= 5 && (
          <div className="legendary-aura" aria-hidden="true">
            <div className="legendary-rays" />
            <div className="legendary-ring" />
            <div className="legendary-ring legendary-ring-2" />
            <div className="legendary-ring legendary-ring-3" />
          </div>
        )}
        <CardFace card={card} image={image} rarity={rarity} />
      </div>

      {expanded &&
        createPortal(
          <div
            className="card-overlay"
            role="dialog"
            aria-modal="true"
            aria-label={`Carta de ${card?.name ?? "???"}`}
            onClick={() => setExpanded(false)}
          >
            <div className="card-overlay-card" data-rarity={rarity}>
              <CardFace card={card} image={image} rarity={rarity} />
            </div>
          </div>,
          document.body
        )}
    </>
  );
}

export default GachaCard;
