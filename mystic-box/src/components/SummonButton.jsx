
function SummonButton({ onClick, disabled }) {
  return (
    <div className="summon-wrap">
      <button
        id="summon"
        onClick={onClick}
        disabled={disabled}
      >
        <span className="summon-text">✦ SUMMON ✦</span>
      </button>
    </div>
  );
}

export default SummonButton;
