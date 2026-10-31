
import GachaCard from "./GachaCard";

function GachaMachine({ card }) {
  return (
    <div className="machine">
      {card && <GachaCard card={card} />}

      <div className="box" />
      <div className="lid" />
    </div>
  );
}

export default GachaMachine;
