import { useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";

const SORT_FIELDS = [
  { value: "rarity", label: "Raridade" },
  { value: "name", label: "Nome" },
];

// Cartas do usuário com ordenação e venda. Usado na coleção e na aba
// "Vender" da loja.
function OwnedCards({ apiUrl, session, onSessionExpired, onBalanceChange }) {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [sortField, setSortField] = useState("rarity");
  const [sortDirection, setSortDirection] = useState("desc");
  // Venda: carta aguardando confirmação, carta sendo vendida e resultado.
  const [confirmingId, setConfirmingId] = useState(null);
  const [sellingId, setSellingId] = useState(null);
  const [sellFeedback, setSellFeedback] = useState(null);

  // O preço e o crédito são decididos pelo servidor; aqui só pedimos a venda.
  async function sellCard(card) {
    setSellingId(card.ownedCardId);
    setSellFeedback(null);

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(
        `${apiUrl}/users/me/cards/${encodeURIComponent(card.ownedCardId)}/sell`,
        { method: "POST", headers: { Authorization: token } }
      );

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));
      const removeCard = () =>
        setCards((current) =>
          current.filter((item) => item.ownedCardId !== card.ownedCardId)
        );

      if (response.status === 404) {
        removeCard();
        setSellFeedback({
          type: "error",
          text: "Esta carta já não estava na sua coleção.",
        });
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Falha ao vender (${response.status}).`);
      }

      removeCard();
      onBalanceChange?.(data.balance);
      setSellFeedback({
        type: "success",
        text: `${card.name} vendida por ✧ ${data.price}.`,
      });
    } catch (sellError) {
      console.error(sellError);
      setSellFeedback({
        type: "error",
        text: sellError.message ?? "Não foi possível vender a carta.",
      });
    } finally {
      setSellingId(null);
      setConfirmingId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const token = session.session.getIdToken().getJwtToken();
        const query = new URLSearchParams({
          sort: sortField,
          order: sortDirection,
        });
        const response = await fetch(`${apiUrl}/users/me/cards?${query}`, {
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
  }, [apiUrl, session, onSessionExpired, reloadKey, sortField, sortDirection]);

  return (
    <>
      {!loading && !error && (
        <p className="collection-count">
          {cards.length} {cards.length === 1 ? "carta" : "cartas"}
        </p>
      )}

      {loading && cards.length === 0 && (
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

      {!error && cards.length > 1 && (
        <div className="collection-sort">
          <label className="collection-sort-label" htmlFor="collection-sort-field">
            Ordenar por
          </label>
          <select
            id="collection-sort-field"
            className="collection-sort-select"
            value={sortField}
            disabled={loading}
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
            disabled={loading}
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

      {sellFeedback && (
        <p
          className={sellFeedback.type === "error" ? "auth-error" : "auth-info"}
          role="status"
        >
          {sellFeedback.text}
        </p>
      )}

      {!error && cards.length > 0 && (
        <ul
          className={`collection-grid${loading ? " is-loading" : ""}`}
          aria-busy={loading}
        >
          {cards.map((card) => {
            const rarity = Number(card.rarity) || 0;
            const canSell = typeof card.sellPrice === "number";
            const confirming = confirmingId === card.ownedCardId;
            const selling = sellingId === card.ownedCardId;
            return (
              <li
                key={card.ownedCardId}
                className="collection-card"
                data-rarity={rarity}
              >
                <div className="collection-card-art">
                  <CardFace
                    card={card}
                    image={getCharacterImage(card.file_name)}
                    rarity={rarity}
                  />
                </div>

                {canSell && !confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(sellingId)}
                    onClick={() => {
                      setSellFeedback(null);
                      setConfirmingId(card.ownedCardId);
                    }}
                    aria-label={`Vender ${card.name} por ${card.sellPrice} Fragmentos Arcanos`}
                  >
                    Vender ✧ {card.sellPrice}
                  </button>
                )}

                {canSell && confirming && (
                  <div className="collection-sell-confirm">
                    <button
                      type="button"
                      className="collection-sell-button is-confirm"
                      disabled={selling}
                      onClick={() => sellCard(card)}
                    >
                      {selling ? "Vendendo..." : "Confirmar"}
                    </button>
                    <button
                      type="button"
                      className="collection-sell-button is-cancel"
                      disabled={selling}
                      onClick={() => setConfirmingId(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export default OwnedCards;
