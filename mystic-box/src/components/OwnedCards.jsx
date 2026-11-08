import { useEffect, useState } from "react";
import { getCharacterImage } from "../characterImages";
import AscensionCeremony from "./AscensionCeremony";
import { ELEMENT_STYLE } from "./battle/battlePresentation";
import { SkillList, StatGrid } from "./battle/TeamSetup";
import { CardFace } from "./GachaCard";
import Modal from "./Modal";
import "../styles/battle.css";
import "../styles/lore.css";

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

// Modal de anúncio no mercado: quantas cópias e o preço pedido por cópia. O
// limite de cópias (`maxListingQuantity`) e a faixa de preço
// (`listingPriceRange`) vêm do servidor, que valida tudo de novo ao anunciar.
function ListingModal({ card, listing, error, onConfirm, onClose }) {
  const max = card.maxListingQuantity;
  const range = card.listingPriceRange;
  const rarity = Number(card.rarity) || 0;
  const owned = Number(card.quantity) || 1;
  const [quantity, setQuantity] = useState(1);
  const [priceText, setPriceText] = useState(String(range.min));

  const clamp = (value) => Math.min(max, Math.max(1, value));
  const price = Number(priceText);
  const priceValid =
    /^\d+$/.test(priceText) && price >= range.min && price <= range.max;
  const keepsCount = owned - quantity;

  function submit(event) {
    event.preventDefault();
    if (priceValid && !listing) onConfirm(quantity, price);
  }

  return (
    <Modal
      label={`Sell ${card.name}`}
      className="listing-modal"
      onClose={listing ? () => {} : onClose}
    >
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>PUT ON SALE</h2>
        <p>Other players can buy it in the shop while it is on sale.</p>
      </header>

      <div className="listing-card" data-rarity={rarity}>
        <div className="listing-card-art">
          <CardFace card={card} image={getCharacterImage(card.file_name)} rarity={rarity} />
        </div>
        <p className="listing-owned">You own {copiesLabel(owned)}</p>
      </div>

      <form className="listing-form" onSubmit={submit}>
        {max > 1 && (
          <div className="listing-field">
            <span className="listing-label" id="listing-quantity-label">
              Copies to sell
            </span>
            <div className="collection-sell-stepper">
              <button
                type="button"
                className="collection-sell-step"
                disabled={listing || quantity <= 1}
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
                disabled={listing}
                onChange={(event) => {
                  const value = Number.parseInt(event.target.value, 10);
                  setQuantity(Number.isNaN(value) ? 1 : clamp(value));
                }}
                onFocus={(event) => event.target.select()}
                aria-labelledby="listing-quantity-label"
              />
              <button
                type="button"
                className="collection-sell-step"
                disabled={listing || quantity >= max}
                onClick={() => setQuantity((value) => clamp(value + 1))}
                aria-label="Sell one more copy"
              >
                +
              </button>
            </div>
          </div>
        )}

        <label className="listing-field">
          <span className="listing-label">Price per copy ✧</span>
          <input
            type="number"
            inputMode="numeric"
            className="collection-sell-input listing-price-input"
            min={range.min}
            max={range.max}
            step={1}
            value={priceText}
            disabled={listing}
            aria-invalid={!priceValid}
            aria-describedby="listing-price-hint"
            autoFocus
            onChange={(event) => setPriceText(event.target.value.trim())}
            onFocus={(event) => event.target.select()}
          />
          <span
            id="listing-price-hint"
            className={`collection-price-hint${priceValid ? "" : " is-invalid"}`}
          >
            From ✧ {range.min} to ✧ {range.max}
          </span>
        </label>

        <p className="collection-sell-summary" aria-live="polite">
          {quantity}× ✧ {priceValid ? price : "—"}
          <span className="collection-sell-keeps">
            {keepsCount > 0
              ? `You keep ${copiesLabel(keepsCount)} in your collection`
              : "Leaves your collection while on sale"}
          </span>
        </p>

        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}

        <div className="listing-actions">
          <button
            type="button"
            className="collection-sell-button is-cancel"
            disabled={listing}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="collection-sell-button is-confirm"
            disabled={listing || !priceValid}
          >
            {listing ? "Listing..." : "Put on sale"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ascensionMarks(level) {
  return "✴".repeat(level);
}

// Modal de ascensão: mostra o custo e o ganho calculados pelo servidor
// (`card.ascension`). O servidor confere tudo de novo ao ascender.
function AscendModal({ card, ascending, error, onConfirm, onClose }) {
  const rarity = Number(card.rarity) || 0;
  const owned = Number(card.quantity) || 1;
  const info = card.ascension;
  const next = info.level + 1;
  const needed = info.nextCost + 1;
  const newSkill = info.unlocksSkill && next === info.skillUnlockLevel;

  return (
    <Modal
      label={`Ascend ${card.name}`}
      className="listing-modal"
      onClose={ascending ? () => {} : onClose}
    >
      <header className="auth-header">
        <span className="auth-ornament">✴ ✦ ✴</span>
        <h2>ASCEND</h2>
        <p>Spend duplicate copies to make this card stronger for good.</p>
      </header>

      <div className="listing-card" data-rarity={rarity}>
        <div className="listing-card-art">
          <CardFace card={card} image={getCharacterImage(card.file_name)} rarity={rarity} />
        </div>
        <p className="listing-owned">You own {copiesLabel(owned)}</p>
      </div>

      <dl className="ascend-steps">
        <div>
          <dt>Ascension</dt>
          <dd>
            {info.level > 0 ? ascensionMarks(info.level) : "—"} → {ascensionMarks(next)}
          </dd>
        </div>
        <div>
          <dt>Stat bonus</dt>
          <dd>
            +{info.statBonusPercent}% → +{info.nextStatBonusPercent}%
          </dd>
        </div>
        {newSkill && (
          <div>
            <dt>New skill</dt>
            <dd>Learns one more class skill</dd>
          </div>
        )}
        <div>
          <dt>Cost</dt>
          <dd>{copiesLabel(info.nextCost)}</dd>
        </div>
      </dl>

      <p className="collection-sell-summary" aria-live="polite">
        {info.canAscend
          ? `You keep ${copiesLabel(owned - info.nextCost)} in your collection`
          : `You need ${copiesLabel(needed)} (one always stays in your collection)`}
      </p>

      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}

      <div className="listing-actions">
        <button
          type="button"
          className="collection-sell-button is-cancel"
          disabled={ascending}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="collection-sell-button is-confirm"
          disabled={ascending || !info.canAscend}
          onClick={onConfirm}
        >
          {ascending ? "Ascending..." : "Ascend"}
        </button>
      </div>
    </Modal>
  );
}

// História da personagem (`card.lore`, vinda do servidor junto com a coleção):
// de onde ela vem, a história e os laços com outras personagens.
// Aba de batalha: elemento, classe, ascensão, atributos e habilidades, tudo
// como veio de `card.battle` e `card.ascension` (calculados no servidor).
function BattleTab({ card }) {
  const profile = card.battle;
  const ascension = card.ascension;
  const element = ELEMENT_STYLE[profile.element];

  return (
    <div className="story-battle" style={{ "--element": element?.color }}>
      <div className="story-battle-tags">
        <span className="story-battle-tag">
          {element?.icon} {profile.elementLabel}
        </span>
        <span className="story-battle-tag">{profile.archetypeLabel}</span>
        {profile.strongAgainst?.length > 0 && (
          <span className="story-battle-tag is-muted">
            Strong vs {profile.strongAgainst.map((id) => ELEMENT_STYLE[id]?.icon ?? id).join(" ")}
          </span>
        )}
      </div>
      <p className="story-battle-desc">{profile.archetypeDescription}</p>

      {ascension && (
        <p className="story-battle-ascension">
          <span>Ascension</span>
          {ascension.level > 0 ? ascensionMarks(ascension.level) : "—"}
          <em>
            {ascension.level}/{ascension.max} · +{ascension.statBonusPercent}% stats
          </em>
        </p>
      )}

      <h3>Stats</h3>
      <StatGrid stats={profile.stats} />
      <p className="story-battle-note">At level 1. Stats grow with your level in battle.</p>

      {profile.skills?.length > 0 && (
        <>
          <h3>Skills</h3>
          <SkillList skills={profile.skills} />
        </>
      )}
    </div>
  );
}

function StoryModal({ card, onClose }) {
  const rarity = Number(card.rarity) || 0;
  const lore = Array.isArray(card.lore?.story) ? card.lore : null;
  const [tab, setTab] = useState(lore ? "story" : "battle");
  const tabs = [lore && ["story", "Story"], card.battle && ["battle", "Battle"]].filter(Boolean);

  return (
    <Modal label={card.name} className="story-modal" onClose={onClose}>
      <div className="story-hero" data-rarity={rarity}>
        <div className="story-hero-art">
          <CardFace card={card} image={getCharacterImage(card.file_name)} rarity={rarity} />
        </div>
        <header className="story-heading">
          {lore?.region && (
            <p className="story-region" data-element={lore.region.element ?? undefined}>
              ✦ {lore.region.name}
              {lore.region.element && <span className="story-element">{lore.region.element}</span>}
            </p>
          )}
          <h2>{card.name}</h2>
          {lore?.title && <p className="story-title">{lore.title}</p>}
        </header>
      </div>

      {tabs.length > 1 && (
        <div className="world-tabs story-tabs" role="tablist">
          {tabs.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? "is-active" : undefined}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {tab === "story" ? <StoryTab card={card} /> : <BattleTab card={card} />}
    </Modal>
  );
}

function StoryTab({ card }) {
  const lore = card.lore;
  const bonds = lore.bonds ?? [];
  const secret = lore.secret;

  return (
    <>
      <div className="story-text">
        {lore.story.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>

      {secret && (
        <section
          className={`story-secret${secret.unlocked ? " is-unlocked" : ""}`}
          aria-label="Secret chapter"
        >
          <h3>
            <span aria-hidden="true">{secret.unlocked ? "✴" : "🔒"}</span> Secret chapter:{" "}
            {secret.title}
          </h3>
          {secret.unlocked ? (
            <p>{secret.text}</p>
          ) : (
            <p className="story-secret-locked">
              Reach ascension {"✴".repeat(secret.unlockAscension)} with this card to reveal
              what {card.name} has never told anyone.
            </p>
          )}
        </section>
      )}

      {bonds.length > 0 && (
        <section className="story-bonds" aria-label="Bonds">
          <h3>Bonds</h3>
          <ul>
            {bonds.map((bond) => (
              <li
                key={bond.file_name}
                data-rarity={bond.rarity}
                className={bond.owned === false ? "is-missing" : undefined}
              >
                <img src={getCharacterImage(bond.file_name)} alt="" loading="lazy" />
                <div>
                  <strong>
                    {bond.name}
                    {bond.owned === false && <em className="story-bond-missing">Not summoned yet</em>}
                  </strong>
                  <span>{bond.relation}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

// Cartas do usuário, agrupadas por personagem, com ordenação e anúncio no
// mercado. Usado na coleção (com ascensão) e na aba "Sell" da loja.
function OwnedCards({ apiUrl, session, onSessionExpired, onListed, allowAscend = false }) {
  const [cards, setCards] = useState([]);
  const [totalCards, setTotalCards] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [sortField, setSortField] = useState("rarity");
  const [sortDirection, setSortDirection] = useState("desc");
  // Anúncio: carta com o modal aberto, se está enviando, erro no modal e
  // resultado mostrado na lista depois que o modal fecha.
  const [sellingCard, setSellingCard] = useState(null);
  const [listing, setListing] = useState(false);
  const [listError, setListError] = useState("");
  const [listFeedback, setListFeedback] = useState(null);
  // Ascensão: carta com o modal aberto, se está enviando e erro no modal.
  const [ascendingCard, setAscendingCard] = useState(null);
  const [ascending, setAscending] = useState(false);
  const [ascendError, setAscendError] = useState("");
  // Cerimônia mostrada depois que a ascensão deu certo: carta antes + resposta.
  const [ceremony, setCeremony] = useState(null);
  const [storyCard, setStoryCard] = useState(null);

  function openAscend(card) {
    setListFeedback(null);
    setAscendError("");
    setAscendingCard(card);
  }

  // Pedimos só a ascensão da carta; custo e efeito são decididos pelo servidor.
  async function ascendCard(card) {
    setAscending(true);
    setAscendError("");

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/users/me/cards/ascend`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ fileName: card.file_name }),
      });

      if (response.status === 401) {
        setAscendingCard(null);
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 409) {
        setAscendingCard(null);
        setListFeedback({
          type: "error",
          text: data.message ?? "Your collection has changed. Check it and try again.",
        });
        setReloadKey((key) => key + 1);
        return;
      }

      if (!response.ok) {
        throw new Error(data.message ?? `Failed to ascend (${response.status}).`);
      }

      setAscendingCard(null);
      setCeremony({ card, result: data });
      setListFeedback({
        type: "success",
        text: `${data.name ?? card.name} reached ascension ${ascensionMarks(data.ascension.level)} (+${data.ascension.statBonusPercent}% stats).`,
      });
      setReloadKey((key) => key + 1);
    } catch (requestError) {
      console.error(requestError);
      setAscendError(requestError.message ?? "Could not ascend the card.");
    } finally {
      setAscending(false);
    }
  }

  function openListing(card) {
    setListFeedback(null);
    setListError("");
    setSellingCard(card);
  }

  // Pedimos o anúncio (qual carta, quantas cópias e o preço). Quais cópias
  // saem e se o preço é aceito são decididos pelo servidor.
  async function listCards(card, quantity, price) {
    setListing(true);
    setListError("");

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/shop/listings`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ fileName: card.file_name, quantity, price }),
      });

      if (response.status === 401) {
        setSellingCard(null);
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      // Preço recusado: o modal continua aberto para o jogador corrigir.
      if (response.status === 400) {
        setListError(data.message ?? "Check the price and try again.");
        return;
      }

      if (response.status === 404 || response.status === 409) {
        setSellingCard(null);
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

      setSellingCard(null);
      setListFeedback({
        type: "success",
        text: `${copiesLabel(data.listedQuantity)} of ${data.name ?? card.name} put on sale for ✧ ${data.price} each.`,
      });
      setReloadKey((key) => key + 1);
      onListed?.();
    } catch (requestError) {
      console.error(requestError);
      setListError(requestError.message ?? "Could not list the card.");
    } finally {
      setListing(false);
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
            const ascension = card.ascension;
            const canOpenAscend = allowAscend && ascension?.nextCost != null;
            const hasDetails = Array.isArray(card.lore?.story) || Boolean(card.battle);
            const face = (
              <CardFace
                card={card}
                image={getCharacterImage(card.file_name)}
                rarity={rarity}
              />
            );
            return (
              <li key={key} className="collection-card" data-rarity={rarity}>
                <div className="collection-card-art">
                  {hasDetails ? (
                    <button
                      type="button"
                      className="collection-card-story"
                      onClick={() => setStoryCard(card)}
                      aria-label={`Open the story and battle details of ${card.name}`}
                    >
                      {face}
                    </button>
                  ) : (
                    face
                  )}
                  {quantity > 1 && (
                    <span
                      className="collection-card-quantity"
                      aria-label={`You have ${copiesLabel(quantity)}`}
                    >
                      ×{quantity}
                    </span>
                  )}
                  {ascension?.level > 0 && (
                    <span
                      className="collection-card-ascension"
                      aria-label={`Ascension ${ascension.level} of ${ascension.max}`}
                      title={`Ascension ${ascension.level}/${ascension.max} · +${ascension.statBonusPercent}% stats`}
                    >
                      {ascensionMarks(ascension.level)}
                    </span>
                  )}
                </div>

                {(canList || canOpenAscend) && (
                  <div className="collection-card-actions">
                    {canList && (
                      <button
                        type="button"
                        className="collection-sell-button"
                        disabled={loading}
                        onClick={() => openListing({ ...card, quantity })}
                        aria-label={`Put ${card.name} on sale in the shop`}
                      >
                        Sell
                      </button>
                    )}
                    {canOpenAscend && (
                      <button
                        type="button"
                        className={`collection-sell-button is-ascend${ascension.canAscend ? " is-ready" : ""}`}
                        disabled={loading}
                        onClick={() => openAscend({ ...card, quantity })}
                        aria-label={`Ascend ${card.name}`}
                      >
                        Ascend
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {sellingCard && (
        <ListingModal
          card={sellingCard}
          listing={listing}
          error={listError}
          onConfirm={(quantity, price) => listCards(sellingCard, quantity, price)}
          onClose={() => setSellingCard(null)}
        />
      )}

      {ascendingCard && (
        <AscendModal
          card={ascendingCard}
          ascending={ascending}
          error={ascendError}
          onConfirm={() => ascendCard(ascendingCard)}
          onClose={() => setAscendingCard(null)}
        />
      )}

      {storyCard && <StoryModal card={storyCard} onClose={() => setStoryCard(null)} />}

      {ceremony && (
        <AscensionCeremony
          card={ceremony.card}
          result={ceremony.result}
          onClose={() => setCeremony(null)}
        />
      )}
    </>
  );
}

export default OwnedCards;
