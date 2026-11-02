import { useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";
import Modal from "./Modal";
import OwnedCards from "./OwnedCards";

const TABS = [
  { value: "buy", label: "Comprar" },
  { value: "sell", label: "Vender" },
];

// Catálogo da loja. Preços e se o jogador pode pagar vêm do servidor.
function ShopCatalog({ apiUrl, session, onSessionExpired, onBalanceChange }) {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [confirmingId, setConfirmingId] = useState(null);
  const [buyingId, setBuyingId] = useState(null);
  const [buyFeedback, setBuyFeedback] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const token = session.session.getIdToken().getJwtToken();
        const response = await fetch(`${apiUrl}/shop/cards`, {
          headers: { Authorization: token },
        });

        if (response.status === 401) {
          onSessionExpired();
          return;
        }

        if (!response.ok) {
          throw new Error(`Falha ao abrir a loja (${response.status}).`);
        }

        const data = await response.json();
        if (cancelled) return;
        setCards(data.cards ?? []);
        if (typeof data.balance === "number") onBalanceChange?.(data.balance);
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Não foi possível abrir a loja.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, onSessionExpired, onBalanceChange, reloadKey]);

  // Só pedimos a compra pelo identificador; preço e débito são do servidor.
  async function buyCard(card) {
    setBuyingId(card.file_name);
    setBuyFeedback(null);

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(
        `${apiUrl}/shop/cards/${encodeURIComponent(card.file_name)}/buy`,
        { method: "POST", headers: { Authorization: token } }
      );

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (response.status === 409 || response.status === 404) {
        setBuyFeedback({
          type: "error",
          text: data.message ?? "Não foi possível comprar esta carta.",
        });
        // Atualiza saldo e disponibilidade com o que o servidor sabe agora.
        setReloadKey((key) => key + 1);
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Falha ao comprar (${response.status}).`);
      }

      onBalanceChange?.(data.balance);
      setBuyFeedback({
        type: "success",
        text: `${data.card?.name ?? card.name} comprada por ✧ ${data.price}. Ela já está na sua coleção.`,
      });
      setReloadKey((key) => key + 1);
    } catch (buyError) {
      console.error(buyError);
      setBuyFeedback({
        type: "error",
        text: buyError.message ?? "Não foi possível comprar a carta.",
      });
    } finally {
      setBuyingId(null);
      setConfirmingId(null);
    }
  }

  return (
    <>
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

      {buyFeedback && (
        <p
          className={buyFeedback.type === "error" ? "auth-error" : "auth-info"}
          role="status"
        >
          {buyFeedback.text}
        </p>
      )}

      {!error && cards.length > 0 && (
        <ul
          className={`collection-grid${loading ? " is-loading" : ""}`}
          aria-busy={loading}
        >
          {cards.map((card) => {
            const rarity = Number(card.rarity) || 0;
            const confirming = confirmingId === card.file_name;
            const buying = buyingId === card.file_name;
            return (
              <li
                key={card.file_name}
                className={`collection-card${card.canAfford ? "" : " is-unaffordable"}`}
                data-rarity={rarity}
              >
                <div className="collection-card-art">
                  <CardFace
                    card={card}
                    image={getCharacterImage(card.file_name)}
                    rarity={rarity}
                  />
                </div>

                {!confirming && (
                  <button
                    type="button"
                    className="collection-sell-button"
                    disabled={Boolean(buyingId) || loading || !card.canAfford}
                    onClick={() => {
                      setBuyFeedback(null);
                      setConfirmingId(card.file_name);
                    }}
                    aria-label={
                      card.canAfford
                        ? `Comprar ${card.name} por ${card.buyPrice} Fragmentos Arcanos`
                        : `${card.name} custa ${card.buyPrice} Fragmentos Arcanos. Saldo insuficiente`
                    }
                  >
                    Comprar ✧ {card.buyPrice}
                  </button>
                )}

                {confirming && (
                  <div className="collection-sell-confirm">
                    <button
                      type="button"
                      className="collection-sell-button is-confirm"
                      disabled={buying}
                      onClick={() => buyCard(card)}
                    >
                      {buying ? "Comprando..." : "Confirmar"}
                    </button>
                    <button
                      type="button"
                      className="collection-sell-button is-cancel"
                      disabled={buying}
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

function ShopModal({ apiUrl, session, balance, onClose, onSessionExpired, onBalanceChange }) {
  const [tab, setTab] = useState("buy");

  return (
    <Modal label="Loja" className="collection-modal" onClose={onClose}>
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>LOJA ARCANA</h2>
        <p>
          Seu saldo: <span className="shop-balance">✧ {balance ?? 0}</span>
        </p>
      </header>

      <div className="shop-tabs" role="tablist" aria-label="Loja">
        {TABS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            id={`shop-tab-${option.value}`}
            aria-selected={tab === option.value}
            aria-controls="shop-panel"
            className={`shop-tab${tab === option.value ? " is-active" : ""}`}
            onClick={() => setTab(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div id="shop-panel" role="tabpanel" aria-labelledby={`shop-tab-${tab}`}>
        {tab === "buy" ? (
          <ShopCatalog
            apiUrl={apiUrl}
            session={session}
            onSessionExpired={onSessionExpired}
            onBalanceChange={onBalanceChange}
          />
        ) : (
          <OwnedCards
            apiUrl={apiUrl}
            session={session}
            onSessionExpired={onSessionExpired}
            onBalanceChange={onBalanceChange}
          />
        )}
      </div>
    </Modal>
  );
}

export default ShopModal;
