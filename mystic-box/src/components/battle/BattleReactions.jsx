import { useEffect, useRef, useState } from "react";

// Reações do duelo online. A lista de emojis, o limite de envio e quem pode
// reagir vêm do servidor; aqui só se escolhe um emoji e se anima o que chegou.

// Posição horizontal estável para cada reação (só apresentação).
function laneFor(id) {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return 12 + (hash % 76);
}

function senderLabel(reaction) {
  if (reaction.isYou) return "You";
  if (reaction.username) return reaction.username;
  return reaction.side === "spectator" ? "A spectator" : "";
}

// Emojis subindo pela tela. Não recebe cliques.
export function ReactionLayer({ reactions }) {
  return (
    <div className="battle-reactions" aria-hidden="true">
      {reactions.map((reaction) => (
        <span
          key={reaction.id}
          className={`battle-reaction is-${reaction.side}${reaction.isYou ? " is-you" : ""}`}
          style={{ left: `${laneFor(reaction.id)}%` }}
        >
          <span className="battle-reaction-emoji">{reaction.emoji}</span>
          <span className="battle-reaction-name">{senderLabel(reaction)}</span>
        </span>
      ))}
    </div>
  );
}

// Botão que abre a paleta de emojis.
export function ReactionPicker({ options, coolingDown, onSend }) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function handlePointer(event) {
      if (!wrapper.current?.contains(event.target)) setOpen(false);
    }
    function handleKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointer);
    window.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("pointerdown", handlePointer);
      window.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div className="battle-react" ref={wrapper}>
      <button
        type="button"
        className="battle-menu-button battle-react-button"
        aria-label="Send a reaction"
        aria-expanded={open}
        title="React"
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">😊</span>
      </button>
      {open && (
        <div className="battle-react-palette" role="group" aria-label="Reactions">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className="battle-react-option"
              disabled={coolingDown}
              aria-label={`React with ${option.emoji}`}
              onClick={() => {
                onSend(option.id);
                setOpen(false);
              }}
            >
              {option.emoji}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
