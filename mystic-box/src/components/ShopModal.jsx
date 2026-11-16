import { useCallback, useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";
import Modal from "./Modal";
import OwnedCards from "./OwnedCards";
import PriceHistory from "./PriceHistory";

const TABS = [
  { value: "buy", label: "Buy" },
  { value: "sell", label: "Sell" },
  { value: "orders", label: "Requests" },
  { value: "mine", label: "Mine" },
];

function getToken(session) {
  return session.session.getIdToken().getJwtToken();
}

// POST na API do mercado. Devolve { status, data } ou null se a sessão expirou.
async function postShop(apiUrl, session, path, body, onSessionExpired) {
  const headers = { Authorization: getToken(session) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${apiUrl}${path}`, {
    method: "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 401) {
    onSessionExpired();
    return null;
  }
  const data = await response.json().catch(() => ({}));
  return { status: response.status, ok: response.ok, data };
}

function Feedback({ feedback }) {
  if (!feedback) return null;
  return (
    <p className={feedback.type === "error" ? "auth-error" : "auth-info"} role="status">
      {feedback.text}
    </p>
  );
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
      const result = await postShop(
        apiUrl,
        session,
        `/shop/listings/${encodeURIComponent(card.listingId)}/buy`,
        undefined,
        onSessionExpired
      );
      if (!result) return;
      const { status, ok, data } = result;

      if (status === 409 || status === 404) {
        setFeedback({ type: "error", text: data.message ?? "Could not buy this card." });
        if (typeof data.balance === "number") onBalanceChange?.(data.balance);
        onChanged();
        return;
      }

      if (!ok) {
        throw new Error(data.message ?? `Failed to buy (${status}).`);
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
      <Feedback feedback={feedback} />

      {!loading && market && cards.length === 0 && (
        <p className="collection-status">
          No cards for sale right now. New cards only come from summons — check back
          later, request a card in the Requests tab or put your own duplicates on sale.
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

function normalizeSearch(text) {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

// Busca de carta pelo nome, com a ilustração de cada uma. As opções vêm do
// servidor (orderOptions); aqui só se filtra para mostrar.
function CardPicker({ options, chosen, disabled, onChoose }) {
  const [query, setQuery] = useState("");
  const search = normalizeSearch(query);
  const matches = search
    ? options.filter((candidate) => normalizeSearch(candidate.name).includes(search))
    : options;

  if (chosen) {
    return (
      <div className="card-picker-chosen" data-rarity={chosen.rarity}>
        <img src={getCharacterImage(chosen.file_name)} alt="" className="card-picker-thumb" />
        <span className="card-picker-label">
          <span className="card-picker-name">{chosen.name}</span>
          <span className="card-picker-stars">{"★".repeat(chosen.rarity)}</span>
        </span>
        <button
          type="button"
          className="card-picker-change"
          disabled={disabled}
          onClick={() => onChoose("")}
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="card-picker">
      <label className="listing-field">
        <span className="listing-label">Card</span>
        <input
          type="search"
          className="collection-sell-input card-picker-search"
          placeholder="Search by name..."
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {matches.length === 0 ? (
        <p className="price-history-empty">No card matches “{query.trim()}”.</p>
      ) : (
        <ul className="card-picker-list" aria-label="Cards">
          {matches.map((candidate) => (
            <li key={candidate.file_name}>
              <button
                type="button"
                className="card-picker-option"
                data-rarity={candidate.rarity}
                disabled={disabled}
                onClick={() => onChoose(candidate.file_name)}
              >
                <img
                  src={getCharacterImage(candidate.file_name)}
                  alt=""
                  loading="lazy"
                  className="card-picker-thumb"
                />
                <span className="card-picker-label">
                  <span className="card-picker-name">{candidate.name}</span>
                  <span className="card-picker-stars">{"★".repeat(candidate.rarity)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Pedir uma carta: escolher a carta e o preço. As cartas, a faixa de preço de
// cada uma e o histórico vêm do servidor, que reserva os Fragmentos ao pedir.
function RequestForm({ market, apiUrl, session, onSessionExpired, onBalanceChange, onChanged }) {
  const options = market?.orderOptions ?? [];
  const [fileName, setFileName] = useState("");
  const [priceText, setPriceText] = useState("");
  const [placing, setPlacing] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const option = options.find((candidate) => candidate.file_name === fileName) ?? null;
  const range = option?.priceRange ?? null;
  const price = Number(priceText);
  const priceValid =
    range !== null && /^\d+$/.test(priceText) && price >= range.min && price <= range.max;
  const atLimit =
    Boolean(market) && (market.myOrders?.length ?? 0) >= (market.maxActiveOrders ?? Infinity);

  function choose(value) {
    setFileName(value);
    setFeedback(null);
    const chosen = options.find((candidate) => candidate.file_name === value);
    setPriceText(chosen ? String(chosen.priceRange.min) : "");
  }

  async function submit(event) {
    event.preventDefault();
    if (!priceValid || placing) return;
    setPlacing(true);
    setFeedback(null);

    try {
      const result = await postShop(
        apiUrl,
        session,
        "/shop/orders",
        { fileName, price },
        onSessionExpired
      );
      if (!result) return;
      const { status, ok, data } = result;
      if (typeof data.balance === "number") onBalanceChange?.(data.balance);

      if (status === 400 || status === 409) {
        setFeedback({ type: "error", text: data.message ?? "Could not place the request." });
        return;
      }
      if (!ok) throw new Error(data.message ?? `Failed to place the request (${status}).`);

      setFeedback({
        type: "success",
        text: `Requested ${data.order?.name ?? option.name} for ✧ ${data.order?.price ?? price}. The shards are set aside until someone sells it to you or you cancel.`,
      });
      onChanged();
    } catch (placeError) {
      console.error(placeError);
      setFeedback({ type: "error", text: placeError.message ?? "Could not place the request." });
    } finally {
      setPlacing(false);
    }
  }

  return (
    <form className="listing-form shop-request-form" onSubmit={submit}>
      <h3 className="shop-section-title">Request a card</h3>
      <p className="collection-sell-keeps shop-section-hint">
        Choose a card and what you will pay. The shards leave your balance now and go to the
        first player who sells it to you.
      </p>

      <CardPicker
        options={options}
        chosen={option}
        disabled={placing || !market}
        onChoose={choose}
      />

      {option && (
        <>
          <label className="listing-field">
            <span className="listing-label">Your offer ✧</span>
            <input
              type="number"
              inputMode="numeric"
              className="collection-sell-input listing-price-input"
              min={range.min}
              max={range.max}
              step={1}
              value={priceText}
              disabled={placing}
              aria-invalid={!priceValid}
              aria-describedby="request-price-hint"
              onChange={(event) => setPriceText(event.target.value.trim())}
              onFocus={(event) => event.target.select()}
            />
            <span
              id="request-price-hint"
              className={`collection-price-hint${priceValid ? "" : " is-invalid"}`}
            >
              From ✧ {range.min} to ✧ {range.max}
            </span>
          </label>

          <PriceHistory
            apiUrl={apiUrl}
            session={session}
            fileName={option.file_name}
            onSessionExpired={onSessionExpired}
          />
        </>
      )}

      <Feedback feedback={feedback} />

      <button
        type="submit"
        className="collection-sell-button is-confirm"
        disabled={!priceValid || placing || atLimit}
      >
        {placing ? "Requesting..." : atLimit ? "Request limit reached" : "Place request"}
      </button>
    </form>
  );
}

// Pedidos de outros jogadores: vender uma cópia da coleção para o maior
// pedido de cada carta. Quanto o jogador recebe (já sem a taxa) vem do servidor.
function WantedCards({ market, loading, apiUrl, session, onSessionExpired, onBalanceChange, onChanged }) {
  const [confirmingId, setConfirmingId] = useState(null);
  const [sellingId, setSellingId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const orders = market?.orders ?? [];

  async function sellTo(order) {
    setSellingId(order.orderId);
    setFeedback(null);

    try {
      const result = await postShop(
        apiUrl,
        session,
        `/shop/orders/${encodeURIComponent(order.orderId)}/fill`,
        undefined,
        onSessionExpired
      );
      if (!result) return;
      const { status, ok, data } = result;

      if (status === 404 || status === 409) {
        setFeedback({ type: "error", text: data.message ?? "Could not sell this card." });
        onChanged();
        return;
      }
      if (!ok) throw new Error(data.message ?? `Failed to sell (${status}).`);

      if (typeof data.balance === "number") onBalanceChange?.(data.balance);
      setFeedback({
        type: "success",
        text: `Sold ${data.name ?? order.name} for ✧ ${data.price}. You received ✧ ${data.proceeds} after the market fee.`,
      });
      onChanged();
    } catch (sellError) {
      console.error(sellError);
      setFeedback({ type: "error", text: sellError.message ?? "Could not sell the card." });
    } finally {
      setSellingId(null);
      setConfirmingId(null);
    }
  }

  return (
    <>
      <h3 className="shop-section-title">Players are looking for</h3>
      <Feedback feedback={feedback} />

      {!loading && market && orders.length === 0 && (
        <p className="collection-status">Nobody is requesting a card right now.</p>
      )}

      {orders.length > 0 && (
        <ul className={`collection-grid${loading ? " is-loading" : ""}`} aria-busy={loading}>
          {orders.map((order) => {
            const rarity = Number(order.rarity) || 0;
            const confirming = confirmingId === order.orderId;
            const selling = sellingId === order.orderId;
            return (
              <li
                key={order.file_name}
                className={`collection-card${order.canFill ? "" : " is-unaffordable"}`}
                data-rarity={rarity}
              >
                <div className="collection-card-art">
                  <CardFace card={order} image={getCharacterImage(order.file_name)} rarity={rarity} />
                  {order.wanted > 1 && (
                    <span
                      className="collection-card-quantity"
                      aria-label={`${order.wanted} copies requested`}
                    >
                      ×{order.wanted}
                    </span>
                  )}
                </div>

                <p className="collection-sell-summary">
                  Offer ✧ {order.price}
                  <span className="collection-sell-keeps">
                    {order.canFill ? `You receive ✧ ${order.proceeds}` : "You have no copy"}
                  </span>
                </p>

                {!confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(sellingId) || loading || !order.canFill}
                    onClick={() => {
                      setFeedback(null);
                      setConfirmingId(order.orderId);
                    }}
                    aria-label={
                      order.canFill
                        ? `Sell ${order.name} for ${order.price} Arcane Shards`
                        : `A player offers ${order.price} Arcane Shards for ${order.name}. You have no copy`
                    }
                  >
                    Sell
                  </button>
                )}

                {confirming && (
                  <div className="collection-sell-confirm">
                    <button
                      type="button"
                      className="collection-sell-button is-confirm"
                      disabled={selling}
                      onClick={() => sellTo(order)}
                    >
                      {selling ? "Selling..." : "Confirm"}
                    </button>
                    <button
                      type="button"
                      className="collection-sell-button is-cancel"
                      disabled={selling}
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

// Anúncios e pedidos do próprio jogador. Cancelar um anúncio devolve a carta
// para a coleção; cancelar um pedido devolve os Fragmentos reservados.
function MyMarket({ market, loading, apiUrl, session, onSessionExpired, onBalanceChange, onChanged }) {
  const [cancellingId, setCancellingId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const listings = market?.myListings ?? [];
  const orders = market?.myOrders ?? [];

  async function cancel(path, id, describeSuccess) {
    setCancellingId(id);
    setFeedback(null);

    try {
      const result = await postShop(apiUrl, session, path, undefined, onSessionExpired);
      if (!result) return;
      const { status, ok, data } = result;

      if (status === 404 || status === 409) {
        setFeedback({ type: "error", text: data.message ?? "Could not cancel." });
        onChanged();
        return;
      }
      if (!ok) throw new Error(data.message ?? `Failed to cancel (${status}).`);

      if (typeof data.balance === "number") onBalanceChange?.(data.balance);
      setFeedback({ type: "success", text: describeSuccess(data) });
      onChanged();
    } catch (cancelError) {
      console.error(cancelError);
      setFeedback({ type: "error", text: cancelError.message ?? "Could not cancel." });
    } finally {
      setCancellingId(null);
    }
  }

  function cancelListing(listing) {
    return cancel(
      `/shop/listings/${encodeURIComponent(listing.listingId)}/cancel`,
      listing.listingId,
      (data) => `${data.card?.name ?? listing.name} is back in your collection.`
    );
  }

  function cancelOrder(order) {
    return cancel(
      `/shop/orders/${encodeURIComponent(order.orderId)}/cancel`,
      order.orderId,
      (data) => `Request for ${order.name} cancelled. ✧ ${data.refunded} returned to your balance.`
    );
  }

  return (
    <>
      <Feedback feedback={feedback} />

      <h3 className="shop-section-title">On sale</h3>
      {market && (
        <p className="collection-count">
          {listings.length} of {market.maxActiveListings} listings in use · {market.marketFeePercent}%
          market fee per sale
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
                <p className="collection-sell-summary">
                  On sale for ✧ {listing.price}
                  <span className="collection-sell-keeps">You receive ✧ {listing.proceeds}</span>
                </p>
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

      <h3 className="shop-section-title">Requested</h3>
      {market && (
        <p className="collection-count">
          {orders.length} of {market.maxActiveOrders} requests in use · ✧ {market.reservedBalance} set
          aside
        </p>
      )}

      {!loading && market && orders.length === 0 && (
        <p className="collection-status">
          You have no open requests. Use the Requests tab to ask for a card.
        </p>
      )}

      {orders.length > 0 && (
        <ul className={`collection-grid${loading ? " is-loading" : ""}`} aria-busy={loading}>
          {orders.map((order) => {
            const rarity = Number(order.rarity) || 0;
            return (
              <li key={order.orderId} className="collection-card" data-rarity={rarity}>
                <div className="collection-card-art">
                  <CardFace card={order} image={getCharacterImage(order.file_name)} rarity={rarity} />
                </div>
                <p className="collection-sell-summary">Offering ✧ {order.price}</p>
                <button
                  type="button"
                  className="collection-sell-button is-cancel"
                  disabled={Boolean(cancellingId) || loading}
                  onClick={() => cancelOrder(order)}
                  aria-label={`Cancel the request for ${order.name} and get the shards back`}
                >
                  {cancellingId === order.orderId ? "Cancelling..." : "Cancel request"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

// A aba vem do endereço (/shop, /shop/sell, /shop/orders, /shop/mine).
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

  const listProps = {
    market,
    loading,
    apiUrl,
    session,
    onSessionExpired,
    onBalanceChange,
    onChanged: reload,
  };
  const mineCount = (market?.myListings?.length ?? 0) + (market?.myOrders?.length ?? 0);

  return (
    <Modal label="Shop" className="collection-modal" routed onClose={onClose}>
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
            {option.value === "mine" && mineCount > 0 && <> ({mineCount})</>}
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

        {tab === "buy" && !error && <MarketListings {...listProps} />}
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
        {tab === "orders" && !error && (
          <>
            <WantedCards {...listProps} />
            <RequestForm {...listProps} />
          </>
        )}
        {tab === "mine" && !error && <MyMarket {...listProps} />}
      </div>
    </Modal>
  );
}

export default ShopModal;
