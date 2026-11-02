import { useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";

const SORT_FIELDS = [
  { value: "rarity", label: "Rarity" },
  { value: "name", label: "Name" },
  { value: "quantity", label: "Duplicates" },
];

function cardKey(card) {
  return card.file_name ?? card.name;
}

function copiesLabel(count) {
  return `${count} ${count === 1 ? "copy" : "copies"}`;
}

// Escolha de quantas cópias vender. O limite (`maxSellQuantity`) e o preço
// por cópia (`sellPrice`) vêm do servidor; o total final é o que a venda
// devolver.
function SellQuantityPicker({ card, selling, onConfirm, onCancel }) {
  const max = card.maxSellQuantity;
  // Com repetidas, o padrão é vender as extras e ficar com uma.
  const [quantity, setQuantity] = useState(
    card.quantity > 1 ? Math.min(card.quantity - 1, max) : 1
  );

  const clamp = (value) => Math.min(max, Math.max(1, value));
  const keepsCount = card.quantity - quantity;
  const shortcuts = [];
  if (card.quantity > 1 && card.quantity - 1 <= max) {
    shortcuts.push({ label: "Duplicates", value: card.quantity - 1 });
  }
  if (max > 1) {
    shortcuts.push({ label: max === card.quantity ? "All" : "Max", value: max });
  }

  return (
    <div
      className="collection-sell-panel"
      role="group"
      aria-label={`Sell ${card.name}`}
    >
      {max > 1 && (
        <>
          <div className="collection-sell-stepper">
            <button
              type="button"
              className="collection-sell-step"
              disabled={selling || quantity <= 1}
              onClick={() => setQuantity((value) => clamp(value - 1))}
              aria-label="Sell one fewer copy"
            >
              −
            </button>
            <input
              type="number"
              className="collection-sell-input"
              min={1}
              max={max}
              value={quantity}
              disabled={selling}
              onChange={(event) => {
                const value = Number.parseInt(event.target.value, 10);
                setQuantity(Number.isNaN(value) ? 1 : clamp(value));
              }}
              onFocus={(event) => event.target.select()}
              aria-label={`Quantity to sell, from 1 to ${max}`}
            />
            <button
              type="button"
              className="collection-sell-step"
              disabled={selling || quantity >= max}
              onClick={() => setQuantity((value) => clamp(value + 1))}
              aria-label="Sell one more copy"
            >
              +
            </button>
          </div>

          {shortcuts.length > 0 && (
            <div className="collection-sell-shortcuts">
              {shortcuts.map((shortcut) => (
                <button
                  key={shortcut.label}
                  type="button"
                  className={`collection-sell-chip${
                    quantity === shortcut.value ? " is-active" : ""
                  }`}
                  disabled={selling}
                  aria-pressed={quantity === shortcut.value}
                  onClick={() => setQuantity(shortcut.value)}
                >
                  {shortcut.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      <p className="collection-sell-summary" aria-live="polite">
        {quantity}× ✧ {card.sellPrice}
        <span className="collection-sell-keeps">
          {keepsCount > 0 ? `You keep ${keepsCount}` : "Leaves your collection"}
        </span>
      </p>

      <div className="collection-sell-confirm">
        <button
          type="button"
          className="collection-sell-button is-confirm"
          disabled={selling}
          onClick={() => onConfirm(quantity)}
        >
          {selling ? "Selling..." : "Confirm"}
        </button>
        <button
          type="button"
          className="collection-sell-button is-cancel"
          disabled={selling}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// Cartas do usuário, agrupadas por personagem, com ordenação e venda. Usado
// na coleção e na aba "Vender" da loja.
function OwnedCards({ apiUrl, session, onSessionExpired, onBalanceChange }) {
  const [cards, setCards] = useState([]);
  const [totalCards, setTotalCards] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [sortField, setSortField] = useState("rarity");
  const [sortDirection, setSortDirection] = useState("desc");
  // Venda: carta aguardando confirmação, carta sendo vendida e resultado.
  const [confirmingKey, setConfirmingKey] = useState(null);
  const [sellingKey, setSellingKey] = useState(null);
  const [sellFeedback, setSellFeedback] = useState(null);

  // Só pedimos a venda (qual carta e quantas cópias); quais cópias saem,
  // o preço e o crédito são decididos pelo servidor.
  async function sellCards(card, quantity) {
    setSellingKey(cardKey(card));
    setSellFeedback(null);

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/users/me/cards/sell`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ fileName: card.file_name, quantity }),
      });

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 409) {
        setSellFeedback({
          type: "error",
          text: data.message ?? "Your collection has changed. Check it and try again.",
        });
        // Atualiza a coleção com o que o servidor sabe agora.
        setReloadKey((key) => key + 1);
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Failed to sell (${response.status}).`);
      }

      onBalanceChange?.(data.balance);
      setSellFeedback({
        type: "success",
        text: `Sold ${copiesLabel(data.soldQuantity)} of ${data.name ?? card.name} for ✧ ${data.price}.`,
      });
      setReloadKey((key) => key + 1);
    } catch (sellError) {
      console.error(sellError);
      setSellFeedback({
        type: "error",
        text: sellError.message ?? "Could not sell the card.",
      });
    } finally {
      setSellingKey(null);
      setConfirmingKey(null);
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
          throw new Error(`Failed to load cards (${response.status}).`);
        }

        const data = await response.json();
        if (cancelled) return;
        setCards(data.cards ?? []);
        setTotalCards(data.totalCards ?? 0);
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Could not load your collection.");
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
          {totalCards} {totalCards === 1 ? "card" : "cards"}
          {cards.length > 0 && cards.length !== totalCards && (
            <>
              {" "}
              · {cards.length} {"unique"}
            </>
          )}
        </p>
      )}

      {loading && cards.length === 0 && (
        <p className="collection-status" role="status">
          Loading...
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
            Try again
          </button>
        </div>
      )}

      {!loading && !error && cards.length === 0 && (
        <p className="collection-status">
          No cards yet. Summon your first one!
        </p>
      )}

      {!error && cards.length > 1 && (
        <div className="collection-sort">
          <label className="collection-sort-label" htmlFor="collection-sort-field">
            Sort by
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
                ? "Ascending order. Switch to descending"
                : "Descending order. Switch to ascending"
            }
          >
            {sortDirection === "asc" ? "▲ Ascending" : "▼ Descending"}
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
            const key = cardKey(card);
            const rarity = Number(card.rarity) || 0;
            const quantity = Number(card.quantity) || 1;
            const canSell =
              typeof card.sellPrice === "number" && card.maxSellQuantity > 0;
            const confirming = confirmingKey === key;
            const selling = sellingKey === key;
            return (
              <li key={key} className="collection-card" data-rarity={rarity}>
                <div className="collection-card-art">
                  <CardFace
                    card={card}
                    image={getCharacterImage(card.file_name)}
                    rarity={rarity}
                  />
                  {quantity > 1 && (
                    <span
                      className="collection-card-quantity"
                      aria-label={`You have ${copiesLabel(quantity)}`}
                    >
                      ×{quantity}
                    </span>
                  )}
                </div>

                {canSell && !confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(sellingKey) || loading}
                    onClick={() => {
                      setSellFeedback(null);
                      setConfirmingKey(key);
                    }}
                    aria-label={`Sell ${card.name}, ${card.sellPrice} Arcane Shards per copy`}
                  >
                    Sell ✧ {card.sellPrice}
                    {quantity > 1 && <span className="collection-sell-each"> each</span>}
                  </button>
                )}

                {canSell && confirming && (
                  <SellQuantityPicker
                    card={{ ...card, quantity }}
                    selling={selling}
                    onConfirm={(amount) => sellCards(card, amount)}
                    onCancel={() => setConfirmingKey(null)}
                  />
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
