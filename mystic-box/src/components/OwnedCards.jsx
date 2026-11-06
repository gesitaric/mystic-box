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

// Anúncio no mercado: quantas cópias e o preço pedido por cópia. O limite de
// cópias (`maxListingQuantity`) e a faixa de preço (`listingPriceRange`) vêm
// do servidor, que valida tudo de novo ao criar o anúncio.
function ListingPicker({ card, listing, onConfirm, onCancel }) {
  const max = card.maxListingQuantity;
  const range = card.listingPriceRange;
  const [quantity, setQuantity] = useState(1);
  const [priceText, setPriceText] = useState(String(range.min));

  const clamp = (value) => Math.min(max, Math.max(1, value));
  const price = Number(priceText);
  const priceValid =
    /^\d+$/.test(priceText) && price >= range.min && price <= range.max;
  const keepsCount = card.quantity - quantity;

  return (
    <div
      className="collection-sell-panel"
      role="group"
      aria-label={`Sell ${card.name}`}
    >
      {max > 1 && (
        <div className="collection-sell-stepper">
          <button
            type="button"
            className="collection-sell-step"
            disabled={listing || quantity <= 1}
            onClick={() => setQuantity((value) => clamp(value - 1))}
            aria-label="List one fewer copy"
          >
            −
          </button>
          <input
            type="number"
            className="collection-sell-input"
            min={1}
            max={max}
            value={quantity}
            disabled={listing}
            onChange={(event) => {
              const value = Number.parseInt(event.target.value, 10);
              setQuantity(Number.isNaN(value) ? 1 : clamp(value));
            }}
            onFocus={(event) => event.target.select()}
            aria-label={`Copies to list, from 1 to ${max}`}
          />
          <button
            type="button"
            className="collection-sell-step"
            disabled={listing || quantity >= max}
            onClick={() => setQuantity((value) => clamp(value + 1))}
            aria-label="List one more copy"
          >
            +
          </button>
        </div>
      )}

      <label className="collection-price-field">
        <span>Price each ✧</span>
        <input
          type="number"
          inputMode="numeric"
          className="collection-sell-input collection-price-input"
          min={range.min}
          max={range.max}
          step={1}
          value={priceText}
          disabled={listing}
          aria-invalid={!priceValid}
          onChange={(event) => setPriceText(event.target.value.trim())}
          onFocus={(event) => event.target.select()}
        />
      </label>
      <p className={`collection-price-hint${priceValid ? "" : " is-invalid"}`}>
        From ✧ {range.min} to ✧ {range.max}
      </p>

      <p className="collection-sell-summary" aria-live="polite">
        {quantity}× ✧ {priceValid ? price : "—"}
        <span className="collection-sell-keeps">
          {keepsCount > 0 ? `You keep ${keepsCount}` : "Leaves your collection"}
        </span>
      </p>

      <div className="collection-sell-confirm">
        <button
          type="button"
          className="collection-sell-button is-confirm"
          disabled={listing || !priceValid}
          onClick={() => onConfirm(quantity, price)}
        >
          {listing ? "Listing..." : "Put on sale"}
        </button>
        <button
          type="button"
          className="collection-sell-button is-cancel"
          disabled={listing}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// Cartas do usuário, agrupadas por personagem, com ordenação e anúncio no
// mercado. Usado na coleção e na aba "Sell" da loja.
function OwnedCards({ apiUrl, session, onSessionExpired, onListed }) {
  const [cards, setCards] = useState([]);
  const [totalCards, setTotalCards] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [sortField, setSortField] = useState("rarity");
  const [sortDirection, setSortDirection] = useState("desc");
  // Anúncio: carta com o formulário aberto, carta sendo anunciada e resultado.
  const [confirmingKey, setConfirmingKey] = useState(null);
  const [listingKey, setListingKey] = useState(null);
  const [listFeedback, setListFeedback] = useState(null);

  // Pedimos o anúncio (qual carta, quantas cópias e o preço). Quais cópias
  // saem e se o preço é aceito são decididos pelo servidor.
  async function listCards(card, quantity, price) {
    setListingKey(cardKey(card));
    setListFeedback(null);

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/shop/listings`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ fileName: card.file_name, quantity, price }),
      });

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if ([400, 404, 409].includes(response.status)) {
        setListFeedback({
          type: "error",
          text: data.message ?? "Your collection has changed. Check it and try again.",
        });
        // Atualiza a coleção com o que o servidor sabe agora.
        setReloadKey((key) => key + 1);
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Failed to list (${response.status}).`);
      }

      setListFeedback({
        type: "success",
        text: `${copiesLabel(data.listedQuantity)} of ${data.name ?? card.name} put on sale for ✧ ${data.price} each.`,
      });
      setReloadKey((key) => key + 1);
      onListed?.();
    } catch (listError) {
      console.error(listError);
      setListFeedback({
        type: "error",
        text: listError.message ?? "Could not list the card.",
      });
    } finally {
      setListingKey(null);
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

      {listFeedback && (
        <p
          className={listFeedback.type === "error" ? "auth-error" : "auth-info"}
          role="status"
        >
          {listFeedback.text}
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
            const canList =
              card.listingPriceRange != null && card.maxListingQuantity > 0;
            const confirming = confirmingKey === key;
            const listing = listingKey === key;
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

                {canList && !confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(listingKey) || loading}
                    onClick={() => {
                      setListFeedback(null);
                      setConfirmingKey(key);
                    }}
                    aria-label={`Put ${card.name} on sale in the shop`}
                  >
                    Sell
                  </button>
                )}

                {canList && confirming && (
                  <ListingPicker
                    card={{ ...card, quantity }}
                    listing={listing}
                    onConfirm={(amount, price) => listCards(card, amount, price)}
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
