import GachaCard from "./GachaCard";

function GachaMachine({ card, cardKey, cardClassName }) {
  return (
    <div className="machine">
      {card && (
        <GachaCard
          key={cardKey}
          card={card}
          className={cardClassName ? `card ${cardClassName}` : "card"}
        />
      )}

      <div className="beam" />
      <div className="box" />
      <div className="lid" />
    </div>
  );
}

export default GachaMachine;
