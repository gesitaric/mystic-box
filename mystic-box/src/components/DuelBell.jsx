import { useEffect, useRef, useState } from "react";

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

// Sininho de desafios de duelo. Não consulta sozinho: a lista vem de quando a
// tela inicial abriu e é atualizada ao abrir o sininho (onRefresh).
function DuelBell({ duels, loading, onRefresh, onAnswer, onDecline, onOpenDuel }) {
  const [open, setOpen] = useState(false);
  const [decliningId, setDecliningId] = useState(null);
  const root = useRef(null);
  const incoming = duels?.incoming ?? [];
  const count = incoming.length + (duels?.battle ? 1 : 0);

  useEffect(() => {
    if (!open) return undefined;
    function handlePointer(event) {
      if (!root.current?.contains(event.target)) setOpen(false);
    }
    function handleKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("pointerdown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  function toggle() {
    if (!open) onRefresh();
    setOpen((current) => !current);
  }

  async function decline(challenge) {
    setDecliningId(challenge.challengeId);
    try {
      await onDecline(challenge);
    } finally {
      setDecliningId(null);
    }
  }

  return (
    <div className="duel-bell" ref={root}>
      <button
        type="button"
        className={`hud-icon-button${count > 0 ? " has-alert" : ""}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={count > 0 ? `${count} duel notification${count === 1 ? "" : "s"}` : "Duel notifications"}
        title="Duel challenges"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path
            d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
        {count > 0 && <span className="duel-bell-badge">{count}</span>}
      </button>

      {open && (
        <div className="duel-bell-panel" role="dialog" aria-label="Duel challenges">
          <div className="duel-bell-head">
            <span>Duels</span>
            <button
              type="button"
              className="duel-bell-refresh"
              onClick={onRefresh}
              disabled={loading}
            >
              {loading ? "Checking..." : "Refresh"}
            </button>
          </div>

          {duels?.battle && (
            <div className="duel-bell-item is-battle">
              <span className="duel-bell-text">
                Duel in progress vs <strong>{duels.battle.opponent}</strong>
              </span>
              <button
                type="button"
                className="collection-sell-button is-confirm"
                onClick={() => {
                  setOpen(false);
                  onOpenDuel();
                }}
              >
                Enter
              </button>
            </div>
          )}

          {incoming.map((challenge) => (
            <div key={challenge.challengeId} className="duel-bell-item">
              <span className="duel-bell-text">
                <strong>{challenge.username}</strong> (LV {challenge.level}) challenges you
                <span className="duel-bell-expires">{formatClock(challenge.expiresInSeconds)}</span>
              </span>
              <span className="duel-bell-actions">
                <button
                  type="button"
                  className="collection-sell-button is-confirm"
                  disabled={decliningId === challenge.challengeId}
                  onClick={() => {
                    setOpen(false);
                    onAnswer(challenge);
                  }}
                >
                  Accept
                </button>
                <button
                  type="button"
                  className="collection-sell-button is-cancel"
                  disabled={decliningId === challenge.challengeId}
                  onClick={() => void decline(challenge)}
                >
                  Decline
                </button>
              </span>
            </div>
          ))}

          {count === 0 && (
            <p className="duel-bell-empty">
              {duels ? "No challenges for you." : loading ? "Checking..." : "Could not load the duels."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default DuelBell;
