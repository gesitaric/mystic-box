import { useCallback, useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";
import Modal from "./Modal";
import OwnedCards from "./OwnedCards";

const TABS = [
  { value: "buy", label: "Buy" },
  { value: "sell", label: "Sell" },
  { value: "mine", label: "My listings" },
];

function getToken(session) {
  return session.session.getIdToken().getJwtToken();
}

// Mercado: cartas que outros jogadores puseram à venda. Preço, quantidade
// disponível e se o jogador pode pagar vêm do servidor.
function MarketListings({ market, loading, apiUrl, session, onSessionExpired, onBalanceChange, onChanged }) {
  const [confirmingId, setConfirmingId] = useState(null);
  const [buyingId, setBuyingId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const cards = market?.cards ?? [];

  // Só pedimos a compra pelo id do anúncio; preço, débito e crédito ao
  // vendedor são do servidor.
  async function buyListing(card) {
    setBuyingId(card.listingId);
    setFeedback(null);

    try {
      const response = await fetch(
        `${apiUrl}/shop/listings/${encodeURIComponent(card.listingId)}/buy`,
        { method: "POST", headers: { Authorization: getToken(session) } }
      );

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (response.status === 409 || response.status === 404) {
        setFeedback({ type: "error", text: data.message ?? "Could not buy this card." });
        if (typeof data.balance === "number") onBalanceChange?.(data.balance);
        onChanged();
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Failed to buy (${response.status}).`);
      }

      if (typeof data.balance === "number") onBalanceChange?.(data.balance);
      setFeedback({
        type: "success",
        text: `Bought ${data.card?.name ?? card.name} for ✧ ${data.price}. It is now in your collection.`,
      });
      onChanged();
    } catch (buyError) {
      console.error(buyError);
      setFeedback({ type: "error", text: buyError.message ?? "Could not buy the card." });
    } finally {
      setBuyingId(null);
      setConfirmingId(null);
    }
  }

  return (
    <>
      {feedback && (
        <p className={feedback.type === "error" ? "auth-error" : "auth-info"} role="status">
          {feedback.text}
        </p>
      )}

      {!loading && market && cards.length === 0 && (
        <p className="collection-status">
          No cards for sale right now. New cards only come from summons — check back
          later or put your own duplicates on sale.
        </p>
      )}

      {cards.length > 0 && (
        <ul className={`collection-grid${loading ? " is-loading" : ""}`} aria-busy={loading}>
          {cards.map((card) => {
            const rarity = Number(card.rarity) || 0;
            const confirming = confirmingId === card.listingId;
            const buying = buyingId === card.listingId;
            return (
              <li
                key={card.file_name}
                className={`collection-card${card.canAfford ? "" : " is-unaffordable"}`}
                data-rarity={rarity}
              >
                <div className="collection-card-art">
                  <CardFace card={card} image={getCharacterImage(card.file_name)} rarity={rarity} />
                  {card.available > 1 && (
                    <span
                      className="collection-card-quantity"
                      aria-label={`${card.available} copies for sale`}
                    >
                      ×{card.available}
                    </span>
                  )}
                </div>

                {!confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(buyingId) || loading || !card.canAfford}
                    onClick={() => {
                      setFeedback(null);
                      setConfirmingId(card.listingId);
                    }}
                    aria-label={
                      card.canAfford
                        ? `Buy ${card.name} for ${card.price} Arcane Shards`
                        : `${card.name} costs ${card.price} Arcane Shards. Not enough balance`
                    }
                  >
                    Buy ✧ {card.price}
                  </button>
                )}

                {confirming && (
                  <div className="collection-sell-confirm">
                    <button
                      type="button"
                      className="collection-sell-button is-confirm"
                      disabled={buying}
                      onClick={() => buyListing(card)}
                    >
                      {buying ? "Buying..." : "Confirm"}
                    </button>
                    <button
                      type="button"
                      className="collection-sell-button is-cancel"
                      disabled={buying}
                      onClick={() => setConfirmingId(null)}
                    >
                      Cancel
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

// Anúncios do próprio jogador. Cancelar devolve a carta para a coleção.
function MyListings({ market, loading, apiUrl, session, onSessionExpired, onChanged }) {
  const [cancellingId, setCancellingId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const listings = market?.myListings ?? [];

  async function cancelListing(listing) {
    setCancellingId(listing.listingId);
    setFeedback(null);

    try {
      const response = await fetch(
        `${apiUrl}/shop/listings/${encodeURIComponent(listing.listingId)}/cancel`,
        { method: "POST", headers: { Authorization: getToken(session) } }
      );

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 409) {
        setFeedback({ type: "error", text: data.message ?? "Could not cancel this listing." });
        onChanged();
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Failed to cancel (${response.status}).`);
      }

      setFeedback({
        type: "success",
        text: `${data.card?.name ?? listing.name} is back in your collection.`,
      });
      onChanged();
    } catch (cancelError) {
      console.error(cancelError);
      setFeedback({ type: "error", text: cancelError.message ?? "Could not cancel the listing." });
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <>
      {market && (
        <p className="collection-count">
          {listings.length} of {market.maxActiveListings} listings in use
        </p>
      )}

      {feedback && (
        <p className={feedback.type === "error" ? "auth-error" : "auth-info"} role="status">
          {feedback.text}
        </p>
      )}

      {!loading && market && listings.length === 0 && (
        <p className="collection-status">
          You have nothing on sale. Use the Sell tab to list cards from your collection.
        </p>
      )}

      {listings.length > 0 && (
        <ul className={`collection-grid${loading ? " is-loading" : ""}`} aria-busy={loading}>
          {listings.map((listing) => {
            const rarity = Number(listing.rarity) || 0;
            return (
              <li key={listing.listingId} className="collection-card" data-rarity={rarity}>
                <div className="collection-card-art">
                  <CardFace
                    card={listing}
                    image={getCharacterImage(listing.file_name)}
                    rarity={rarity}
                  />
                </div>
                <p className="collection-sell-summary">On sale for ✧ {listing.price}</p>
                <button
                  type="button"
                  className="collection-sell-button is-cancel"
                  disabled={Boolean(cancellingId) || loading}
                  onClick={() => cancelListing(listing)}
                  aria-label={`Cancel the sale of ${listing.name} and return it to your collection`}
                >
                  {cancellingId === listing.listingId ? "Cancelling..." : "Cancel sale"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

// A aba vem do endereço (/shop, /shop/sell, /shop/mine).
function ShopModal({
  apiUrl,
  session,
  balance,
  tab = "buy",
  onTabChange,
  onClose,
  onSessionExpired,
  onBalanceChange,
}) {
  const [market, setMarket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const response = await fetch(`${apiUrl}/shop/listings`, {
          headers: { Authorization: getToken(session) },
        });

        if (response.status === 401) {
          onSessionExpired();
          return;
        }

        if (!response.ok) {
          throw new Error(`Failed to open the shop (${response.status}).`);
        }

        const data = await response.json();
        if (cancelled) return;
        setMarket(data);
        if (typeof data.balance === "number") onBalanceChange?.(data.balance);
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Could not open the shop.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, onSessionExpired, onBalanceChange, reloadKey]);

  function selectTab(value) {
    onTabChange(value);
    // Outros jogadores podem ter comprado ou anunciado nesse meio-tempo.
    if (value !== "sell") reload();
  }

  const listProps = { market, loading, apiUrl, session, onSessionExpired, onChanged: reload };

  return (
    <Modal label="Shop" className="collection-modal" onClose={onClose}>
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>ARCANE SHOP</h2>
        <p>
          Your balance: <span className="shop-balance">✧ {balance ?? 0}</span>
        </p>
      </header>

      <div className="shop-tabs" role="tablist" aria-label="Shop">
        {TABS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            id={`shop-tab-${option.value}`}
            aria-selected={tab === option.value}
            aria-controls="shop-panel"
            className={`shop-tab${tab === option.value ? " is-active" : ""}`}
            onClick={() => selectTab(option.value)}
          >
            {option.label}
            {option.value === "mine" && market?.myListings?.length > 0 && (
              <> ({market.myListings.length})</>
            )}
          </button>
        ))}
      </div>

      <div id="shop-panel" role="tabpanel" aria-labelledby={`shop-tab-${tab}`}>
        {tab !== "sell" && loading && !market && (
          <p className="collection-status" role="status">
            Loading...
          </p>
        )}

        {tab !== "sell" && !loading && error && (
          <div className="collection-status">
            <p className="auth-error">{error}</p>
            <button type="button" className="keep-button" onClick={reload}>
              Try again
            </button>
          </div>
        )}

        {tab === "buy" && !error && (
          <MarketListings {...listProps} onBalanceChange={onBalanceChange} />
        )}
        {tab === "sell" && (
          <>
            <p className="collection-count">
              Choose a card and your price. Other players can buy it while it is on sale.
            </p>
            <OwnedCards
              apiUrl={apiUrl}
              session={session}
              onSessionExpired={onSessionExpired}
              onListed={reload}
            />
          </>
        )}
        {tab === "mine" && !error && <MyListings {...listProps} />}
      </div>
    </Modal>
  );
}

export default ShopModal;
