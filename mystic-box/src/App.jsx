import { useCallback, useEffect, useRef, useState } from "react";
import AuthModal from "./components/AuthModal";
import GachaMachine from "./components/GachaMachine";
import Particles from "./components/Particles";
import SummonButton from "./components/SummonButton";
import UserCardsList from "./components/UserCardsList";
import { getCurrentSession, signOut } from "./auth/cognito";
import "./styles/gacha.css";

const API_URL = (
  import.meta.env.VITE_API_URL ??
  "https://d64y0i3dpf.execute-api.us-east-1.amazonaws.com/Prod"
).replace(/\/$/, "");

const PENDING_CARD_KEY = "mystic-box:pending-card";

function formatCountdown(ms) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

async function fetchCard() {
  const response = await fetch(`${API_URL}/box/open`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Falha ao abrir a caixa: ${response.status}`);
  }

  const data = await response.json();
  const drawnCard = data.cards?.[0];

  if (!drawnCard) {
    throw new Error("Nenhuma carta retornada.");
  }

  return drawnCard;
}

function App() {
  const [opening, setOpening] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [particles, setParticles] = useState([]);
  const [card, setCard] = useState(null);
  const [error, setError] = useState("");

  const [session, setSession] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [pendingCard, setPendingCard] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [cardLost, setCardLost] = useState(false);

  // Momento (ms) em que o usuário logado poderá invocar de novo.
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [now, setNow] = useState(() => Date.now());

  const autoSaveAttempted = useRef(false);

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

  const saveCard = useCallback(async (cardToSave, activeSession) => {
    if (!cardToSave || !activeSession) return;

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
        body: JSON.stringify({ card: cardToSave }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          signOut();
          setSession(null);
          throw new Error(
            "Sua sessão expirou. Entre novamente para manter a carta."
          );
        }

        if (response.status === 429) {
          // Ainda no tempo de espera: a carta puxada é perdida.
          const data = await response.json().catch(() => ({}));
          startCooldown(data.retryAfterSeconds ?? 0);
          setCardLost(true);
          setPendingCard(null);
          localStorage.removeItem(PENDING_CARD_KEY);
          return;
        }

        throw new Error(`Falha ao guardar a carta (${response.status}).`);
      }

      const data = await response.json().catch(() => ({}));
      startCooldown(data.retryAfterSeconds ?? 0);

      setSaved(true);
      setPendingCard(null);
      localStorage.removeItem(PENDING_CARD_KEY);
    } catch (saveFailure) {
      console.error(saveFailure);
      setSaveError(
        saveFailure.message ?? "Não foi possível guardar a carta."
      );
    } finally {
      setSaving(false);
    }
  }, [startCooldown]);

  useEffect(() => {
    async function restore() {
      let storedCard = null;

      try {
        const raw = localStorage.getItem(PENDING_CARD_KEY);
        if (raw) storedCard = JSON.parse(raw);
      } catch {
        localStorage.removeItem(PENDING_CARD_KEY);
      }

      const currentSession = await getCurrentSession();

      if (storedCard) {
        setCard(storedCard);
        setPendingCard(storedCard);
        setRevealed(true);
      }

      if (currentSession) {
        setSession(currentSession);

        if (storedCard && !autoSaveAttempted.current) {
          autoSaveAttempted.current = true;
          void saveCard(storedCard, currentSession);
        } else {
          void fetchSummonStatus(currentSession);
        }
      }
    }

    void restore();
  }, [saveCard, fetchSummonStatus]);

  // Sem login não há tempo de espera.
  const cooldownRemaining =
    session && cooldownUntil ? Math.max(0, cooldownUntil - now) : 0;
  const onCooldown = cooldownRemaining > 0;

  async function summon() {
    if (opening || onCooldown) return;

    setError("");
    setSaveError("");
    setSaved(false);
    setCardLost(false);
    setRevealed(false);
    setCard(null);
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
      const [drawnCard] = await Promise.all([
        fetchCard(),
        new Promise((resolve) => setTimeout(resolve, 700)),
      ]);

      setCard(drawnCard);
      setPendingCard(drawnCard);
      localStorage.setItem(PENDING_CARD_KEY, JSON.stringify(drawnCard));

      if (session) {
        void saveCard(drawnCard, session);
      }

      await new Promise((resolve) => setTimeout(resolve, 2400));

      setOpening(false);
      setRevealed(true);
    } catch (err) {
      console.error(err);
      setOpening(false);
      setError("Não foi possível abrir a caixa. Tente novamente.");
    }
  }

  function handleAuthenticated(auth) {
    setSession(auth);
    setAuthOpen(false);

    // Só a carta ainda não guardada; uma já guardada não conta de novo.
    if (pendingCard) {
      void saveCard(pendingCard, auth);
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

  const isLegendary = revealed && (card?.rarity ?? 0) >= 5;
  const hasUnsavedCard = revealed && Boolean(card) && !saved && !cardLost;

  return (
    <main
      className={`scene ${opening ? "opening" : ""} ${revealed ? "revealed" : ""} ${
        isLegendary ? "legendary" : ""
      }`}
    >
      <div className="aurora" />
      <div className="stars" />
      <div className="motes" />
      <div className="vignette" />
      <div className="frame" />

      {isLegendary && <div className="legendary-flash" aria-hidden="true" />}

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
          <div className="legendary-banner" aria-hidden="true">
            <span className="legendary-banner-title">LEGENDARY</span>
            <span className="legendary-banner-sub">A RARE CARD APPEARS</span>
          </div>
        )}

        <GachaMachine card={card} />

        <Particles particles={particles} />
      </div>

      <div className="action-bar">
        <div className="subtitle">
          A MYSTERIOUS GIFT AWAITS...
        </div>

        <SummonButton
          onClick={summon}
          disabled={opening || onCooldown}
        />

        {onCooldown && (
          <p className="cooldown-message" role="timer" aria-live="off">
            Próxima invocação em{" "}
            <span className="cooldown-time">{formatCountdown(cooldownRemaining)}</span>
          </p>
        )}

        {!saving && cardLost && (
          <p className="keep-message keep-lost" role="status">
            Você ainda estava no tempo de espera. Esta carta não pôde ser guardada.
          </p>
        )}

        {saving && (
          <p className="keep-message" role="status">
            Guardando sua carta...
          </p>
        )}

        {!saving && saved && (
          <p className="keep-message keep-success" role="status">
            ✦ Carta guardada na sua coleção
          </p>
        )}

        {!saving && hasUnsavedCard && !session && (
          <div className="keep-prompt">
            <p>
              Você não está logado. Entre para manter esta carta na sua coleção.
            </p>
            <button
              type="button"
              className="keep-button"
              onClick={() => setAuthOpen(true)}
            >
              Entrar e manter carta
            </button>
          </div>
        )}

        {!saving && hasUnsavedCard && session && saveError && (
          <div className="keep-prompt">
            <p className="keep-error">{saveError}</p>
            <button
              type="button"
              className="keep-button"
              onClick={() => saveCard(card ?? pendingCard, session)}
            >
              Tentar novamente
            </button>
          </div>
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
