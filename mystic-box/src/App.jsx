import { useCallback, useEffect, useRef, useState } from "react";
import AuthModal from "./components/AuthModal";
import HomeScreen from "./components/HomeScreen";
import ShopModal from "./components/ShopModal";
import SummonPortal from "./components/portal/SummonPortal";
import SummonSpread from "./components/SummonSpread";
import UserCardsList from "./components/UserCardsList";
import { getCurrentSession, signOut } from "./auth/cognito";
import "./styles/gacha.css";

const API_URL = (
  import.meta.env.VITE_API_URL ??
  "https://vzol9m72hi.execute-api.us-east-1.amazonaws.com/Prod"
).replace(/\/$/, "");

// Guarda o sorteio ainda não salvo: as cartas (só para exibir) e o token
// assinado pelo servidor, que é a única coisa enviada para guardá-las.
const PENDING_SUMMON_KEY = "mystic-box:pending-summon";
// Chaves de versões anteriores, que guardavam só as cartas (sem token).
const LEGACY_PENDING_KEYS = ["mystic-box:pending-cards", "mystic-box:pending-card"];

// Depois de o portal abrir, tempo mínimo da explosão antes de as cartas saírem dele.
const PORTAL_REVEAL_DELAY_MS = 1700;

// Pausa de suspense antes de revelar a última carta.
const FINAL_CARD_SUSPENSE_MS = 1600;

function formatCountdown(ms) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function isValidSummon(summon) {
  return (
    Array.isArray(summon?.cards) &&
    summon.cards.length > 0 &&
    typeof summon.summonToken === "string" &&
    summon.summonToken.length > 0
  );
}

function readPendingSummon() {
  try {
    const raw = localStorage.getItem(PENDING_SUMMON_KEY);
    if (raw) {
      const summon = JSON.parse(raw);
      if (isValidSummon(summon)) return summon;
    }
  } catch {
    // Conteúdo inválido: descarta abaixo.
  }

  // Sorteios antigos não têm token e não podem mais ser guardados.
  clearPendingSummon();
  return null;
}

function storePendingSummon(summon) {
  try {
    localStorage.setItem(PENDING_SUMMON_KEY, JSON.stringify(summon));
  } catch {
    // Sem armazenamento local: o sorteio só vale nesta aba.
  }
}

function clearPendingSummon() {
  try {
    localStorage.removeItem(PENDING_SUMMON_KEY);
    LEGACY_PENDING_KEYS.forEach((key) => localStorage.removeItem(key));
  } catch {
    // Nada a limpar.
  }
}

// O sorteio é feito no servidor, que devolve as cartas e um token assinado.
async function fetchSummon() {
  const response = await fetch(`${API_URL}/box/open`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Failed to open the box: ${response.status}`);
  }

  const data = await response.json();

  if (!isValidSummon(data)) {
    throw new Error("No cards returned.");
  }

  return { cards: data.cards, summonToken: data.summonToken };
}

function App() {
  const [opening, setOpening] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [cards, setCards] = useState(null);
  // Quantas cartas já foram viradas (as viradas ficam à esquerda).
  const [flippedCount, setFlippedCount] = useState(0);
  const [charging, setCharging] = useState(false);
  const [error, setError] = useState("");
  // Muda para recriar o portal (volta ao estado adormecido) depois de um erro.
  const [portalKey, setPortalKey] = useState(0);

  const [session, setSession] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [shopOpen, setShopOpen] = useState(false);
  // Tela do usuário logado: "home" (início) ou "summon" (invocação).
  // Sem login a tela de invocação é sempre a exibida.
  const [screen, setScreen] = useState("home");
  // Sorteio ainda não guardado: { cards, summonToken }.
  const [pendingSummon, setPendingSummon] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  // Motivo pelo qual as cartas sorteadas não puderam ser guardadas.
  const [lostMessage, setLostMessage] = useState("");

  // Momento (ms) em que o usuário logado poderá invocar de novo.
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [now, setNow] = useState(() => Date.now());

  // Saldo de Fragmentos Arcanos do usuário logado.
  const [balance, setBalance] = useState(null);

  const autoSaveAttempted = useRef(false);
  const suspenseTimer = useRef(null);
  const portalRef = useRef(null);
  const getPortalCenter = useCallback(() => portalRef.current?.getCenter() ?? null, []);
  const handleCardEmerge = useCallback(() => portalRef.current?.burst(), []);

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
          throw new Error(`Failed to fetch the cooldown (${response.status}).`);
        }

        const data = await response.json();
        startCooldown(data.retryAfterSeconds ?? 0);
      } catch (statusError) {
        console.error(statusError);
      }
    },
    [startCooldown]
  );

  const fetchWallet = useCallback(async (activeSession) => {
    try {
      const token = activeSession.session.getIdToken().getJwtToken();
      const response = await fetch(`${API_URL}/users/me/wallet`, {
        headers: { Authorization: token },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch the balance (${response.status}).`);
      }

      const data = await response.json();
      setBalance(data.balance ?? 0);
    } catch (walletError) {
      console.error(walletError);
    }
  }, []);

  const saveCards = useCallback(
    async (summon, activeSession) => {
      if (!summon?.summonToken || !activeSession) return;

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
          // Só o token: o servidor lê dele quais cartas foram sorteadas.
          body: JSON.stringify({ summonToken: summon.summonToken }),
        });

        if (!response.ok) {
          if (response.status === 401) {
            signOut();
            setSession(null);
            throw new Error(
              "Your session has expired. Sign in again to keep your cards."
            );
          }

          if (response.status === 429) {
            // Ainda no tempo de espera: as cartas puxadas são perdidas.
            const data = await response.json().catch(() => ({}));
            startCooldown(data.retryAfterSeconds ?? 0);
            setLostMessage(
              "You were still on cooldown. These cards could not be kept."
            );
            setPendingSummon(null);
            clearPendingSummon();
            return;
          }

          if ([400, 409, 410].includes(response.status)) {
            // Sorteio expirado, inválido ou já usado: não adianta tentar de novo.
            const data = await response.json().catch(() => ({}));
            setLostMessage(
              `${data.message ?? "This summon is no longer valid."} These cards could not be kept.`
            );
            setPendingSummon(null);
            clearPendingSummon();
            return;
          }

          throw new Error(`Failed to keep the cards (${response.status}).`);
        }

        const data = await response.json().catch(() => ({}));
        startCooldown(data.retryAfterSeconds ?? 0);

        setSaved(true);
        setPendingSummon(null);
        clearPendingSummon();
      } catch (saveFailure) {
        console.error(saveFailure);
        setSaveError(
          saveFailure.message ?? "Could not keep the cards."
        );
      } finally {
        setSaving(false);
      }
    },
    [startCooldown]
  );

  useEffect(() => {
    async function restore() {
      const storedSummon = readPendingSummon();
      const currentSession = await getCurrentSession();

      if (storedSummon) {
        setCards(storedSummon.cards);
        setPendingSummon(storedSummon);
        setFlippedCount(storedSummon.cards.length);
        setRevealed(true);
      }

      if (currentSession) {
        setSession(currentSession);
        // Com um sorteio pendente, mostra a invocação para acompanhar o salvamento.
        setScreen(storedSummon ? "summon" : "home");
        void fetchWallet(currentSession);

        if (storedSummon && !autoSaveAttempted.current) {
          autoSaveAttempted.current = true;
          void saveCards(storedSummon, currentSession);
        } else {
          void fetchSummonStatus(currentSession);
        }
      }
    }

    void restore();
  }, [saveCards, fetchSummonStatus, fetchWallet]);

  // Sem login não há tempo de espera.
  const cooldownRemaining =
    session && cooldownUntil ? Math.max(0, cooldownUntil - now) : 0;
  const onCooldown = cooldownRemaining > 0;
  const onHome = Boolean(session) && screen === "home";

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
    setLostMessage("");
    setRevealed(false);
    setCharging(false);
    setCards(null);
    setFlippedCount(0);
    setOpening(true);

    try {
      // O sorteio corre no servidor enquanto a explosão do portal acontece.
      const [summonResult] = await Promise.all([
        fetchSummon(),
        new Promise((resolve) => setTimeout(resolve, PORTAL_REVEAL_DELAY_MS)),
      ]);

      setCards(summonResult.cards);
      setPendingSummon(summonResult);
      storePendingSummon(summonResult);

      if (session) {
        void saveCards(summonResult, session);
      }

      setOpening(false);
      setRevealed(true);
    } catch (err) {
      console.error(err);
      setOpening(false);
      setError("The summon failed. Please channel the portal again.");
      setPortalKey((key) => key + 1);
    }
  }

  // Sai do resultado e volta ao portal adormecido (não sorteia nada).
  function returnToPortal() {
    if (revealing || charging) return;
    clearTimeout(suspenseTimer.current);
    setError("");
    setSaveError("");
    setSaved(false);
    setLostMessage("");
    setRevealed(false);
    setCards(null);
    setFlippedCount(0);
    // Portal novo, adormecido.
    setPortalKey((key) => key + 1);
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
    // Quem entrou para guardar um sorteio continua vendo as cartas.
    setScreen(pendingSummon || showingSpread ? "summon" : "home");
    void fetchWallet(auth);

    // Só cartas ainda não guardadas; as já guardadas não contam de novo.
    if (pendingSummon) {
      void saveCards(pendingSummon, auth);
    } else {
      void fetchSummonStatus(auth);
    }
  }

  function handleSignOut() {
    signOut();
    setSession(null);
    setCollectionOpen(false);
    setShopOpen(false);
    setCooldownUntil(null);
    setBalance(null);
    setScreen("home");
  }

  // Não sai no meio da animação de abertura nem do suspense da última carta.
  const canLeaveSummon = !opening && !charging;

  function goHome() {
    if (!canLeaveSummon) return;
    setScreen("home");
  }

  const closeCollection = useCallback(() => setCollectionOpen(false), []);
  const closeShop = useCallback(() => setShopOpen(false), []);

  // Saldo devolvido pelo servidor após uma venda; sem ele, consulta de novo.
  const handleBalanceChange = useCallback(
    (newBalance) => {
      if (typeof newBalance === "number") {
        setBalance(newBalance);
      } else if (session) {
        void fetchWallet(session);
      }
    },
    [session, fetchWallet]
  );

  const handleCollectionSessionExpired = useCallback(() => {
    signOut();
    setSession(null);
    setCollectionOpen(false);
    setShopOpen(false);
    setAuthOpen(true);
  }, []);

  // Efeito lendário enquanto a última carta virada for lendária.
  const isLegendary = showingSpread && !charging && (lastFlippedCard?.rarity ?? 0) >= 5;
  // O clarão espera a carta terminar de girar.
  const legendaryTiming = {
    animationDelay: flippedCount === totalCards ? "0.6s" : "0.35s",
    animationFillMode: "both",
  };
  const hasUnsavedCards = showingResults && !saved && !lostMessage;

  const nextLabel =
    flippedCount === totalCards - 1 ? "Reveal last card" : "Flip card";

  let revealStatus = `${flippedCount} OF ${totalCards} REVEALED`;
  if (flippedCount === 0) revealStatus = `${totalCards} CARDS SUMMONED`;
  if (charging) revealStatus = "THE LAST CARD IS COMING...";

  return (
    <main
      className={[
        "scene",
        onHome && "home-view",
        !onHome && opening && "opening",
        !onHome && revealed && "revealed",
        !onHome && charging && "charging",
        !onHome && isLegendary && "legendary",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="aurora" />
      <div className="stars" />
      <div className="motes" />
      <div className="vignette" />
      <div className="frame" />

      {!onHome && isLegendary && (
        <div
          key={flippedCount}
          className="legendary-flash"
          style={legendaryTiming}
          aria-hidden="true"
        />
      )}

      {!onHome && (
        <div className={session ? "session-bar session-bar-start" : "session-bar"}>
          {session ? (
            <button
              type="button"
              className="session-button"
              onClick={goHome}
              disabled={!canLeaveSummon}
            >
              ← Home
            </button>
          ) : (
            <button
              type="button"
              className="session-button"
              onClick={() => setAuthOpen(true)}
            >
              Sign in
            </button>
          )}
        </div>
      )}

      <header className="title-block">
        <span className="title-ornament">✦ ✧ ✦</span>
        <h1>MYSTIC BOX</h1>
        <p className="tagline">ARCANE SUMMONING</p>
      </header>

      {onHome ? (
        <HomeScreen
          email={session.email}
          balance={balance}
          cooldownLabel={onCooldown ? formatCountdown(cooldownRemaining) : ""}
          onSummon={() => setScreen("summon")}
          onCollection={() => setCollectionOpen(true)}
          onShop={() => setShopOpen(true)}
          onSignOut={handleSignOut}
        />
      ) : (
        <>
          <div className="stage">

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

            {showingSpread && (
              <SummonSpread
                cards={cards}
                flippedCount={flippedCount}
                charging={charging}
                onFlip={flipNext}
                getOrigin={getPortalCenter}
                onEmerge={handleCardEmerge}
              />
            )}
          </div>

          {/* Fica montado durante a revelação: as cartas saem dele e ele vira cenário. */}
          <SummonPortal
              ref={portalRef}
              key={portalKey}
              embedded
              backdrop={showingSpread}
              onActivated={summon}
              disabled={opening || onCooldown || showingSpread}
              disabledLabel={
                onCooldown ? `PORTAL RECHARGING · ${formatCountdown(cooldownRemaining)}` : ""
              }
              activatedLabel={opening ? "THE CARDS ARE ARRIVING..." : undefined}
          />

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
              showingResults && (
                <button type="button" className="keep-button" onClick={returnToPortal}>
                  ✦ Return to the portal ✦
                </button>
              )
            )}

            {onCooldown && showingResults && (
              <p className="cooldown-message" role="timer" aria-live="off">
                Next summon in{" "}
                <span className="cooldown-time">{formatCountdown(cooldownRemaining)}</span>
              </p>
            )}

            {showingResults && (
              <>
                {!saving && lostMessage && (
                  <p className="keep-message keep-lost" role="status">
                    {lostMessage}
                  </p>
                )}

                {saving && (
                  <p className="keep-message" role="status">
                    Keeping your cards...
                  </p>
                )}

                {!saving && saved && (
                  <p className="keep-message keep-success" role="status">
                    ✦ Cards added to your collection
                  </p>
                )}

                {!saving && hasUnsavedCards && !session && (
                  <div className="keep-prompt">
                    <p>
                      You are not signed in. Sign in to keep these cards in your collection.
                    </p>
                    <button
                      type="button"
                      className="keep-button"
                      onClick={() => setAuthOpen(true)}
                    >
                      Sign in and keep cards
                    </button>
                  </div>
                )}

                {!saving && hasUnsavedCards && session && saveError && pendingSummon && (
                  <div className="keep-prompt">
                    <p className="keep-error">{saveError}</p>
                    <button
                      type="button"
                      className="keep-button"
                      onClick={() => saveCards(pendingSummon, session)}
                    >
                      Try again
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
        </>
      )}

      {collectionOpen && session && (
        <UserCardsList
          apiUrl={API_URL}
          session={session}
          onClose={closeCollection}
          onSessionExpired={handleCollectionSessionExpired}
          onBalanceChange={handleBalanceChange}
        />
      )}

      {shopOpen && session && (
        <ShopModal
          apiUrl={API_URL}
          session={session}
          balance={balance}
          onClose={closeShop}
          onSessionExpired={handleCollectionSessionExpired}
          onBalanceChange={handleBalanceChange}
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
