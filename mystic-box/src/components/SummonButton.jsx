
function SummonButton({ onClick, disabled }) {
  return (
    <button
      id="summon"
      onClick={onClick}
      disabled={disabled}
    >
      ✦ SUMMON ✦
    </button>
  );
}

export default SummonButton;
