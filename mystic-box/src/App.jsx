import { useCallback, useEffect, useRef, useState } from "react";
import AuthModal from "./components/AuthModal";
import GachaMachine from "./components/GachaMachine";
import Particles from "./components/Particles";
import SummonButton from "./components/SummonButton";
import SummonSpread from "./components/SummonSpread";
import UserCardsList from "./components/UserCardsList";
import { getCurrentSession, signOut } from "./auth/cognito";
import "./styles/gacha.css";

const API_URL = (
  import.meta.env.VITE_API_URL ??
  "https://vzol9m72hi.execute-api.us-east-1.amazonaws.com/Prod"
).replace(/\/$/, "");

const PENDING_CARDS_KEY = "mystic-box:pending-cards";
// Chave da versão anterior, que guardava uma única carta.
const LEGACY_PENDING_CARD_KEY = "mystic-box:pending-card";

// Pausa de suspense antes de revelar a última carta.
const FINAL_CARD_SUSPENSE_MS = 1600;

function formatCountdown(ms) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function readPendingCards() {
  try {
    const raw = localStorage.getItem(PENDING_CARDS_KEY);
    if (raw) {
      const cards = JSON.parse(raw);
      if (Array.isArray(cards) && cards.length > 0) return cards;
    }

    const legacy = localStorage.getItem(LEGACY_PENDING_CARD_KEY);
    if (legacy) return [JSON.parse(legacy)];
  } catch {
    // Conteúdo inválido: descarta abaixo.
  }

  clearPendingCards();
  return null;
}

function storePendingCards(cards) {
  localStorage.setItem(PENDING_CARDS_KEY, JSON.stringify(cards));
  localStorage.removeItem(LEGACY_PENDING_CARD_KEY);
}

function clearPendingCards() {
  localStorage.removeItem(PENDING_CARDS_KEY);
  localStorage.removeItem(LEGACY_PENDING_CARD_KEY);
}

async function fetchCards() {
  const response = await fetch(`${API_URL}/box/open`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Falha ao abrir a caixa: ${response.status}`);
  }

  const data = await response.json();

  if (!Array.isArray(data.cards) || data.cards.length === 0) {
    throw new Error("Nenhuma carta retornada.");
  }

  return data.cards;
}

function App() {
  const [opening, setOpening] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [particles, setParticles] = useState([]);
  const [cards, setCards] = useState(null);
  // Quantas cartas já foram viradas (as viradas ficam à esquerda).
  const [flippedCount, setFlippedCount] = useState(0);
  const [charging, setCharging] = useState(false);
  const [error, setError] = useState("");

  const [session, setSession] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [pendingCards, setPendingCards] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [cardsLost, setCardsLost] = useState(false);

  // Momento (ms) em que o usuário logado poderá invocar de novo.
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [now, setNow] = useState(() => Date.now());

  const autoSaveAttempted = useRef(false);
  const suspenseTimer = useRef(null);

  useEffect(() => () => clearTimeout(suspenseTimer.current), []);

  const startCooldown = useCallback((seconds) => {
    const current = Date.now();
    setNow(current);
    setCooldownUntil(seconds > 0 ? current + seconds * 1000 : null);
  }, []);

  useEffect(() => {
    if (!cooldownUntil) return;

    const timer = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= cooldownUntil) setCooldownUntil(null);
    }, 1000);

    return () => clearInterval(timer);
  }, [cooldownUntil]);

  const fetchSummonStatus = useCallback(
    async (activeSession) => {
      try {
        const token = activeSession.session.getIdToken().getJwtToken();
        const response = await fetch(`${API_URL}/users/me/summon-status`, {
          headers: { Authorization: token },
        });

        if (!response.ok) {
          throw new Error(`Falha ao consultar o tempo de espera (${response.status}).`);
        }

        const data = await response.json();
        startCooldown(data.retryAfterSeconds ?? 0);
      } catch (statusError) {
        console.error(statusError);
      }
    },
    [startCooldown]
  );

  const saveCards = useCallback(
    async (cardsToSave, activeSession) => {
      if (!cardsToSave?.length || !activeSession) return;

      setSaving(true);
      setSaveError("");

      try {
        const token = activeSession.session.getIdToken().getJwtToken();
        const response = await fetch(`${API_URL}/users/me/cards`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: token,
          },
          body: JSON.stringify({ cards: cardsToSave }),
        });

        if (!response.ok) {
          if (response.status === 401) {
            signOut();
            setSession(null);
            throw new Error(
              "Sua sessão expirou. Entre novamente para manter as cartas."
            );
          }

          if (response.status === 429) {
            // Ainda no tempo de espera: as cartas puxadas são perdidas.
            const data = await response.json().catch(() => ({}));
            startCooldown(data.retryAfterSeconds ?? 0);
            setCardsLost(true);
            setPendingCards(null);
            clearPendingCards();
            return;
          }

          throw new Error(`Falha ao guardar as cartas (${response.status}).`);
        }

        const data = await response.json().catch(() => ({}));
        startCooldown(data.retryAfterSeconds ?? 0);

        setSaved(true);
        setPendingCards(null);
        clearPendingCards();
      } catch (saveFailure) {
        console.error(saveFailure);
        setSaveError(
          saveFailure.message ?? "Não foi possível guardar as cartas."
        );
      } finally {
        setSaving(false);
      }
    },
    [startCooldown]
  );

  useEffect(() => {
    async function restore() {
      const storedCards = readPendingCards();
      const currentSession = await getCurrentSession();

      if (storedCards) {
        setCards(storedCards);
        setPendingCards(storedCards);
        setFlippedCount(storedCards.length);
        setRevealed(true);
      }

      if (currentSession) {
        setSession(currentSession);

        if (storedCards && !autoSaveAttempted.current) {
          autoSaveAttempted.current = true;
          void saveCards(storedCards, currentSession);
        } else {
          void fetchSummonStatus(currentSession);
        }
      }
    }

    void restore();
  }, [saveCards, fetchSummonStatus]);

  // Sem login não há tempo de espera.
  const cooldownRemaining =
    session && cooldownUntil ? Math.max(0, cooldownUntil - now) : 0;
  const onCooldown = cooldownRemaining > 0;

  const totalCards = cards?.length ?? 0;
  const showingSpread = revealed && totalCards > 0;
  const revealing = showingSpread && flippedCount < totalCards;
  const showingResults = showingSpread && flippedCount >= totalCards;
  const lastFlippedCard = flippedCount > 0 ? cards?.[flippedCount - 1] : null;

  async function summon() {
    if (opening || revealing || charging || onCooldown) return;

    clearTimeout(suspenseTimer.current);
    setError("");
    setSaveError("");
    setSaved(false);
    setCardsLost(false);
    setRevealed(false);
    setCharging(false);
    setCards(null);
    setFlippedCount(0);
    setOpening(true);

    setParticles(
      Array.from({ length: 40 }, (_, i) => ({
        id: i,
        x: Math.random() * 500 - 250,
        y: Math.random() * -500 - 50,
        delay: Math.random() * 0.5,
      }))
    );

    try {
      const [drawnCards] = await Promise.all([
        fetchCards(),
        new Promise((resolve) => setTimeout(resolve, 700)),
      ]);

      setCards(drawnCards);
      setPendingCards(drawnCards);
      storePendingCards(drawnCards);

      if (session) {
        void saveCards(drawnCards, session);
      }

      await new Promise((resolve) => setTimeout(resolve, 1900));

      setOpening(false);
      setRevealed(true);
    } catch (err) {
      console.error(err);
      setOpening(false);
      setError("Não foi possível abrir a caixa. Tente novamente.");
    }
  }

  function flipNext() {
    if (!revealing || charging) return;

    if (totalCards > 1 && flippedCount === totalCards - 1) {
      // Suspense antes de virar a última carta.
      setCharging(true);
      suspenseTimer.current = setTimeout(() => {
        setCharging(false);
        setFlippedCount((count) => count + 1);
      }, FINAL_CARD_SUSPENSE_MS);
      return;
    }

    setFlippedCount((count) => count + 1);
  }

  function handleAuthenticated(auth) {
    setSession(auth);
    setAuthOpen(false);

    // Só cartas ainda não guardadas; as já guardadas não contam de novo.
    if (pendingCards) {
      void saveCards(pendingCards, auth);
    } else {
      void fetchSummonStatus(auth);
    }
  }

  function handleSignOut() {
    signOut();
    setSession(null);
    setCollectionOpen(false);
    setCooldownUntil(null);
  }

  const closeCollection = useCallback(() => setCollectionOpen(false), []);

  const handleCollectionSessionExpired = useCallback(() => {
    signOut();
    setSession(null);
    setCollectionOpen(false);
    setAuthOpen(true);
  }, []);

  // Efeito lendário enquanto a última carta virada for lendária.
  const isLegendary = showingSpread && !charging && (lastFlippedCard?.rarity ?? 0) >= 5;
  // O clarão espera a carta terminar de girar.
  const legendaryTiming = {
    animationDelay: flippedCount === totalCards ? "0.6s" : "0.35s",
    animationFillMode: "both",
  };
  const hasUnsavedCards = showingResults && !saved && !cardsLost;

  const nextLabel =
    flippedCount === totalCards - 1 ? "Revelar última carta" : "Virar carta";

  let revealStatus = `${flippedCount} DE ${totalCards} REVELADAS`;
  if (flippedCount === 0) revealStatus = `${totalCards} CARTAS FORAM INVOCADAS`;
  if (charging) revealStatus = "A ÚLTIMA CARTA ESTÁ CHEGANDO...";

  return (
    <main
      className={[
        "scene",
        opening && "opening",
        revealed && "revealed",
        charging && "charging",
        isLegendary && "legendary",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="aurora" />
      <div className="stars" />
      <div className="motes" />
      <div className="vignette" />
      <div className="frame" />

      {isLegendary && (
        <div
          key={flippedCount}
          className="legendary-flash"
          style={legendaryTiming}
          aria-hidden="true"
        />
      )}

      <div className="session-bar">
        {session ? (
          <>
            <span className="session-email" title={session.email}>
              {session.email}
            </span>
            <button
              type="button"
              className="session-button"
              onClick={() => setCollectionOpen(true)}
            >
              Coleção
            </button>
            <button
              type="button"
              className="session-button"
              onClick={handleSignOut}
            >
              Sair
            </button>
          </>
        ) : (
          <button
            type="button"
            className="session-button"
            onClick={() => setAuthOpen(true)}
          >
            Entrar
          </button>
        )}
      </div>

      <header className="title-block">
        <span className="title-ornament">✦ ✧ ✦</span>
        <h1>MYSTIC BOX</h1>
        <p className="tagline">ARCANE SUMMONING</p>
      </header>

      <div className="stage">
        <div className="glow" />

        {isLegendary && (
          <div
            key={flippedCount}
            className="legendary-banner"
            style={legendaryTiming}
            aria-hidden="true"
          >
            <span className="legendary-banner-title">LEGENDARY</span>
            <span className="legendary-banner-sub">A RARE CARD APPEARS</span>
          </div>
        )}

        {showingSpread ? (
          <SummonSpread
            cards={cards}
            flippedCount={flippedCount}
            charging={charging}
            onFlip={flipNext}
          />
        ) : (
          <GachaMachine />
        )}

        <Particles particles={particles} />
      </div>

      <div className="action-bar">
        {revealing || charging ? (
          <>
            <div className="subtitle reveal-progress" aria-live="polite">
              {revealStatus}
            </div>

            <button
              type="button"
              className="keep-button reveal-next"
              onClick={flipNext}
              disabled={charging}
            >
              {nextLabel}
            </button>
          </>
        ) : (
          <>
            <div className="subtitle">
              A MYSTERIOUS GIFT AWAITS...
            </div>

            <SummonButton
              onClick={summon}
              disabled={opening || onCooldown}
            />
          </>
        )}

        {onCooldown && !revealing && !charging && (
          <p className="cooldown-message" role="timer" aria-live="off">
            Próxima invocação em{" "}
            <span className="cooldown-time">{formatCountdown(cooldownRemaining)}</span>
          </p>
        )}

        {showingResults && (
          <>
            {!saving && cardsLost && (
              <p className="keep-message keep-lost" role="status">
                Você ainda estava no tempo de espera. Estas cartas não puderam ser guardadas.
              </p>
            )}

            {saving && (
              <p className="keep-message" role="status">
                Guardando suas cartas...
              </p>
            )}

            {!saving && saved && (
              <p className="keep-message keep-success" role="status">
                ✦ Cartas guardadas na sua coleção
              </p>
            )}

            {!saving && hasUnsavedCards && !session && (
              <div className="keep-prompt">
                <p>
                  Você não está logado. Entre para manter estas cartas na sua coleção.
                </p>
                <button
                  type="button"
                  className="keep-button"
                  onClick={() => setAuthOpen(true)}
                >
                  Entrar e manter cartas
                </button>
              </div>
            )}

            {!saving && hasUnsavedCards && session && saveError && (
              <div className="keep-prompt">
                <p className="keep-error">{saveError}</p>
                <button
                  type="button"
                  className="keep-button"
                  onClick={() => saveCards(pendingCards ?? cards, session)}
                >
                  Tentar novamente
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {error && (
        <div className="error" role="alert">
          <span className="error-icon">✦</span>
          <span>{error}</span>
        </div>
      )}

      {collectionOpen && session && (
        <UserCardsList
          apiUrl={API_URL}
          session={session}
          onClose={closeCollection}
          onSessionExpired={handleCollectionSessionExpired}
        />
      )}

      <AuthModal
        key={authOpen ? "open" : "closed"}
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onAuthenticated={handleAuthenticated}
      />
    </main>
  );
}

export default App;
