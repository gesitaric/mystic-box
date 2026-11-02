import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";

const SORT_FIELDS = [
  { value: "rarity", label: "Raridade" },
  { value: "name", label: "Nome" },
];

const nameCollator = new Intl.Collator("pt-BR", { sensitivity: "base" });

function compareRarity(a, b) {
  return (Number(a.rarity) || 0) - (Number(b.rarity) || 0);
}

function compareName(a, b) {
  return nameCollator.compare(a.name ?? "", b.name ?? "");
}

function sortCards(cards, field, direction) {
  const sign = direction === "asc" ? 1 : -1;
  const [primary, secondary] =
    field === "name" ? [compareName, compareRarity] : [compareRarity, compareName];

  return [...cards].sort(
    (a, b) => sign * primary(a, b) || secondary(a, b)
  );
}

function UserCardsList({ apiUrl, session, onClose, onSessionExpired }) {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [sortField, setSortField] = useState("rarity");
  const [sortDirection, setSortDirection] = useState("desc");

  const sortedCards = useMemo(
    () => sortCards(cards, sortField, sortDirection),
    [cards, sortField, sortDirection]
  );

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

        {!loading && !error && cards.length > 1 && (
          <div className="collection-sort">
            <label className="collection-sort-label" htmlFor="collection-sort-field">
              Ordenar por
            </label>
            <select
              id="collection-sort-field"
              className="collection-sort-select"
              value={sortField}
              onChange={(event) => setSortField(event.target.value)}
            >
              {SORT_FIELDS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="collection-sort-direction"
              onClick={() =>
                setSortDirection((direction) =>
                  direction === "asc" ? "desc" : "asc"
                )
              }
              aria-label={
                sortDirection === "asc"
                  ? "Ordem crescente. Alterar para decrescente"
                  : "Ordem decrescente. Alterar para crescente"
              }
            >
              {sortDirection === "asc" ? "▲ Crescente" : "▼ Decrescente"}
            </button>
          </div>
        )}

        {!loading && !error && cards.length > 0 && (
          <ul className="collection-grid">
            {sortedCards.map((card) => {
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
