import GachaCard from "./GachaCard";

function SummonResults({ cards }) {
  return (
    <div className="summon-results" aria-label="Cartas invocadas">
      {cards.map((card, index) => (
        <GachaCard
          key={`${card.file_name}-${index}`}
          card={card}
          className="result-card"
          showAura={false}
          style={{ animationDelay: `${index * 0.12}s` }}
        />
      ))}
    </div>
  );
}

export default SummonResults;
