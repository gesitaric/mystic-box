import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";

function UserCardsList({ apiUrl, session, onClose, onSessionExpired }) {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const token = session.session.getIdToken().getJwtToken();
        const response = await fetch(`${apiUrl}/users/me/cards`, {
          headers: { Authorization: token },
        });

        if (response.status === 401) {
          onSessionExpired();
          return;
        }

        if (!response.ok) {
          throw new Error(`Falha ao buscar cartas (${response.status}).`);
        }

        const data = await response.json();
        if (!cancelled) setCards(data.cards ?? []);
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Não foi possível carregar sua coleção.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, onSessionExpired, reloadKey]);

  return createPortal(
    <div
      className="auth-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Minha coleção"
      onClick={onClose}
    >
      <div
        className="auth-modal collection-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="auth-close"
          aria-label="Fechar"
          onClick={onClose}
        >
          ×
        </button>

        <header className="auth-header">
          <span className="auth-ornament">✦ ✧ ✦</span>
          <h2>MINHA COLEÇÃO</h2>
          {!loading && !error && (
            <p>
              {cards.length} {cards.length === 1 ? "carta" : "cartas"}
            </p>
          )}
        </header>

        {loading && (
          <p className="collection-status" role="status">
            Carregando...
          </p>
        )}

        {!loading && error && (
          <div className="collection-status">
            <p className="auth-error">{error}</p>
            <button
              type="button"
              className="keep-button"
              onClick={() => setReloadKey((key) => key + 1)}
            >
              Tentar novamente
            </button>
          </div>
        )}

        {!loading && !error && cards.length === 0 && (
          <p className="collection-status">
            Nenhuma carta ainda. Invoque sua primeira!
          </p>
        )}

        {!loading && !error && cards.length > 0 && (
          <ul className="collection-grid">
            {cards.map((card) => {
              const rarity = Number(card.rarity) || 0;
              return (
                <li
                  key={card.ownedCardId}
                  className="collection-card"
                  data-rarity={rarity}
                >
                  <CardFace
                    card={card}
                    image={getCharacterImage(card.file_name)}
                    rarity={rarity}
                  />
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>,
    document.body
  );
}

export default UserCardsList;
