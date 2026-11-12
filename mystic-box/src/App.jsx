import { useCallback, useEffect, useRef, useState } from "react";
import AuthModal from "./components/AuthModal";
import { GrimoireModal } from "./components/Grimoire";
import { WorldModal } from "./components/WorldMap";
import BattleScreen from "./components/battle/BattleScreen";
import HomeScreen from "./components/HomeScreen";
import PlayerProfileModal from "./components/PlayerProfileModal";
import { applyBattleProgress } from "./profileProgress";
import ShopModal from "./components/ShopModal";
import SummonPortal from "./components/portal/SummonPortal";
import SummonSpread from "./components/SummonSpread";
import RevealFx from "./components/reveal/RevealFx";
import UserCardsList from "./components/UserCardsList";
import { getCurrentSession, signOut } from "./auth/cognito";
import { currentRoute, exitTo, navigate, useBackHandler, useRoute } from "./router";
import { needsSession, routeTitle, withOverlay } from "./routes";
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

// Quanto tempo fica o aviso de que o portal ainda está abrindo.
const PORTAL_HOLD_NOTICE_MS = 2200;

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

// O sorteio é feito no servidor (só com login), que devolve as cartas e um
// token assinado.
async function fetchSummon(activeSession) {
  const token = activeSession.session.getIdToken().getJwtToken();
  const response = await fetch(`${API_URL}/box/open`, {
    method: "POST",
    headers: { Authorization: token },
  });

  if (!response.ok) {
    const error = new Error(`Failed to open the box: ${response.status}`);
    error.status = response.status;
    throw error;
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
  // Já sabemos se há login salvo (até lá, não pede login para endereços privados).
  const [sessionChecked, setSessionChecked] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  // Aviso curto quando o Voltar é apertado com o portal abrindo.
  const [portalHold, setPortalHold] = useState(false);
  const portalHoldTimer = useRef(null);
  // Tela e painel abertos vêm do endereço (ver routes.js). Sem login a tela
  // de invocação é sempre a exibida.
  const { route } = useRoute();
  const overlay = route.overlay;

  // Nome da aba do navegador acompanha a tela (ajuda a achar a aba e o histórico).
  const pageTitle = session || route.screen !== "home" ? routeTitle(route) : "Summon";
  useEffect(() => {
    document.title = pageTitle ? `${pageTitle} · Mystic Box` : "Mystic Box";
  }, [pageTitle]);
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
  // Nível e experiência do usuário logado (calculados no servidor).
  const [progress, setProgress] = useState(null);

  const autoSaveAttempted = useRef(false);
  const suspenseTimer = useRef(null);
  const portalRef = useRef(null);
  const revealFxRef = useRef(null);
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

  const fetchProfile = useCallback(async (activeSession) => {
    try {
      const token = activeSession.session.getIdToken().getJwtToken();
      const response = await fetch(`${API_URL}/users/me/profile`, {
        headers: { Authorization: token },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch the profile (${response.status}).`);
      }

      setProgress(await response.json());
    } catch (profileError) {
      console.error(profileError);
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
      setSessionChecked(true);

      if (storedSummon) {
        setCards(storedSummon.cards);
        setPendingSummon(storedSummon);
        setFlippedCount(storedSummon.cards.length);
        setRevealed(true);
      }

      if (currentSession) {
        setSession(currentSession);
        // Com um sorteio pendente, mostra a invocação para acompanhar o salvamento.
        if (storedSummon && currentRoute().screen === "home") {
          navigate("/summon", { replace: true });
        }
        void fetchWallet(currentSession);
        void fetchProfile(currentSession);

        if (storedSummon && !autoSaveAttempted.current) {
          autoSaveAttempted.current = true;
          void saveCards(storedSummon, currentSession);
        } else {
          void fetchSummonStatus(currentSession);
        }
      }
    }

    void restore();
  }, [saveCards, fetchSummonStatus, fetchWallet, fetchProfile]);

  // Sem login não há tempo de espera.
  const cooldownRemaining =
    session && cooldownUntil ? Math.max(0, cooldownUntil - now) : 0;
  const onCooldown = cooldownRemaining > 0;
  const onHome = Boolean(session) && route.screen === "home";
  const onBattle = Boolean(session) && route.screen === "arena";

  // Desafios de duelo do sininho. Não há consulta periódica: busca ao abrir a
  // tela inicial e quando o jogador abre/atualiza o sininho.
  const [duels, setDuels] = useState(null);
  const [duelsLoading, setDuelsLoading] = useState(false);

  const fetchDuels = useCallback(async (activeSession) => {
    if (!activeSession) return;
    setDuelsLoading(true);
    try {
      const token = activeSession.session.getIdToken().getJwtToken();
      const response = await fetch(`${API_URL}/pvp`, { headers: { Authorization: token } });
      if (!response.ok) throw new Error(`Failed to fetch the duels (${response.status}).`);
      // receivedAt: base da contagem regressiva dos prazos devolvidos.
      setDuels({ ...(await response.json()), receivedAt: Date.now() });
    } catch (duelsError) {
      console.error(duelsError);
    } finally {
      setDuelsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!onHome || !session) return;
    // Uma consulta ao abrir a tela inicial (o resultado vem da API).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchDuels(session);
  }, [onHome, session, fetchDuels]);

  const declineDuel = useCallback(
    async (challenge) => {
      try {
        const token = session.session.getIdToken().getJwtToken();
        await fetch(`${API_URL}/pvp/challenges/decline`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: token },
          body: JSON.stringify({ challengeId: challenge.challengeId }),
        });
      } catch (declineError) {
        console.error(declineError);
      }
      await fetchDuels(session);
    },
    [session, fetchDuels]
  );
  // Telas que não mostram o portal de invocação.
  const offSummon = onHome || onBattle;

  const totalCards = cards?.length ?? 0;
  const showingSpread = revealed && totalCards > 0;
  const revealing = showingSpread && flippedCount < totalCards;
  const showingResults = showingSpread && flippedCount >= totalCards;
  const lastFlippedCard = flippedCount > 0 ? cards?.[flippedCount - 1] : null;

  async function summon() {
    if (opening || revealing || charging || onCooldown) return;

    // Invocar exige login (o servidor recusa sem token).
    if (!session) {
      setAuthOpen(true);
      return;
    }
    const activeSession = session;

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
        fetchSummon(activeSession),
        new Promise((resolve) => setTimeout(resolve, PORTAL_REVEAL_DELAY_MS)),
      ]);

      setCards(summonResult.cards);
      setPendingSummon(summonResult);
      storePendingSummon(summonResult);
      void saveCards(summonResult, activeSession);

      setOpening(false);
      setRevealed(true);
    } catch (err) {
      console.error(err);
      setOpening(false);
      if (err.status === 401) {
        signOut();
        setSession(null);
        setError("Your session has expired. Sign in again to summon.");
      } else if (err.status === 429) {
        setError("The portal is crowded right now. Please try again in a moment.");
      } else {
        setError("The summon failed. Please channel the portal again.");
      }
      setPortalKey((key) => key + 1);
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
    // Quem entrou para guardar um sorteio continua vendo as cartas. Nos outros
    // casos fica no endereço pedido (ex.: um link para a arena).
    if ((pendingSummon || showingSpread) && route.screen === "home") {
      navigate("/summon", { replace: true });
    }
    void fetchWallet(auth);
    void fetchProfile(auth);

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
    setCooldownUntil(null);
    setBalance(null);
    setProgress(null);
    navigate("/");
  }

  // Não sai no meio da animação de abertura nem do suspense da última carta.
  const canLeaveSummon = !opening && !charging;

  // O Voltar do navegador também espera o portal: segura e avisa.
  useBackHandler(
    () => {
      clearTimeout(portalHoldTimer.current);
      setPortalHold(true);
      portalHoldTimer.current = setTimeout(() => setPortalHold(false), PORTAL_HOLD_NOTICE_MS);
    },
    { active: !offSummon && !canLeaveSummon && !overlay, kind: "block" }
  );
  useEffect(() => () => clearTimeout(portalHoldTimer.current), []);

  // Endereço que pede login (ex.: um link para a arena) sem login: abre o login
  // por cima e, depois de entrar, o jogador continua no endereço pedido.
  const authGate = sessionChecked && !session && needsSession(route);
  const closeAuth = useCallback(() => {
    setAuthOpen(false);
    if (authGate) navigate("/", { replace: true });
  }, [authGate]);

  function goHome() {
    if (!canLeaveSummon) return;
    // Resultado já resolvido (guardado ou perdido): na próxima visita, portal novo.
    // Cartas ainda não guardadas continuam na tela.
    if (showingResults && (saved || lostMessage)) {
      setError("");
      setSaveError("");
      setSaved(false);
      setLostMessage("");
      setRevealed(false);
      setCards(null);
      setFlippedCount(0);
      setPortalKey((key) => key + 1);
    }
    exitTo("/");
  }

  // Fecha o painel aberto: volta à tela de baixo (pelo histórico, se veio dela).
  const closeOverlay = useCallback(() => exitTo(withOverlay(route, null)), [route]);
  const openOverlay = useCallback(
    (next, options) => navigate(withOverlay(route, next), options),
    [route]
  );
  const challengePlayer = useCallback((opponent) => {
    const chosen = { username: opponent.username, level: opponent.level };
    navigate(
      { screen: "arena", arena: "pvp", duel: "challenge", vs: chosen.username },
      { data: { opponent: chosen } }
    );
  }, []);

  // Nome e tempo de espera devolvidos pelo servidor depois de uma troca.
  const handleProfileChange = useCallback((changes) => {
    setProgress((current) => (current ? { ...current, ...changes } : current));
  }, []);

  // Nível e experiência devolvidos pela batalha.
  const handleBattleProgress = useCallback((battleProgress) => {
    setProgress((current) => applyBattleProgress(current, battleProgress));
  }, []);

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
    navigate(withOverlay(currentRoute(), null), { replace: true });
    setAuthOpen(true);
  }, []);

  const handleBattleSessionExpired = useCallback(() => {
    signOut();
    setSession(null);
    setProgress(null);
    setBalance(null);
    navigate("/", { replace: true });
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
        onBattle && "battle-view",
        !offSummon && opening && "opening",
        !offSummon && revealed && "revealed",
        !offSummon && charging && "charging",
        !offSummon && isLegendary && "legendary",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="aurora" />
      <div className="stars" />
      <div className="motes" />
      <div className="vignette" />
      <div className="frame" />

      {!offSummon && isLegendary && (
        <div
          key={flippedCount}
          className="legendary-flash"
          style={legendaryTiming}
          aria-hidden="true"
        />
      )}

      {!offSummon && (
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

      {!offSummon && (
        <header className="title-block">
          <span className="title-ornament">✦ ✧ ✦</span>
          <h1>MYSTIC BOX</h1>
          <p className="tagline">ARCANE SUMMONING</p>
        </header>
      )}

      {onBattle ? (
        <BattleScreen
          apiUrl={API_URL}
          session={session}
          onExit={() => exitTo("/")}
          onSessionExpired={handleBattleSessionExpired}
          onProgressChange={handleBattleProgress}
          onBalanceChange={handleBalanceChange}
        />
      ) : onHome ? (
        <HomeScreen
          apiUrl={API_URL}
          email={session.email}
          balance={balance}
          progress={progress}
          cooldownLabel={onCooldown ? formatCountdown(cooldownRemaining) : ""}
          duels={duels}
          duelsLoading={duelsLoading}
          onRefreshDuels={() => void fetchDuels(session)}
          onAnswerDuel={(challenge) =>
            navigate(
              {
                screen: "arena",
                arena: "pvp",
                duel: "accept",
                challengeId: challenge.challengeId,
              },
              { data: { challenge } }
            )
          }
          onDeclineDuel={declineDuel}
          onOpenDuel={() => navigate("/arena/duel")}
          onSummon={() => navigate("/summon")}
          onBattle={() => navigate("/arena")}
          onCollection={() => openOverlay({ name: "collection" })}
          onShop={() => openOverlay({ name: "shop", tab: "buy" })}
          onProfile={() => openOverlay({ name: "players", tab: "name" })}
          onPlayers={() => openOverlay({ name: "players", tab: "search" })}
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
                fx={revealFxRef}
                suspenseSeconds={FINAL_CARD_SUSPENSE_MS / 1000}
              />
            )}
          </div>

          <RevealFx ref={revealFxRef} />

          {/* Fica montado durante a revelação: as cartas saem dele e ele vira cenário. */}
          <SummonPortal
              ref={portalRef}
              key={portalKey}
              embedded
              backdrop={showingSpread}
              silenced={showingSpread && flippedCount > 0}
              onActivated={summon}
              disabled={!session || opening || onCooldown || showingSpread}
              disabledLabel={
                !session
                  ? "SIGN IN TO SUMMON"
                  : onCooldown
                    ? `PORTAL RECHARGING · ${formatCountdown(cooldownRemaining)}`
                    : ""
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
            ) : null}

            {!session && !showingSpread && !opening && (
              <div className="keep-prompt">
                <p>Sign in to channel the portal and summon your cards.</p>
                <button
                  type="button"
                  className="keep-button"
                  onClick={() => setAuthOpen(true)}
                >
                  Sign in to summon
                </button>
              </div>
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

          {portalHold && (opening || charging) && (
            <p className="portal-hold-notice" role="status">
              ✦ The portal is still channeling. Hold on…
            </p>
          )}

          {error && (
            <div className="error" role="alert">
              <span className="error-icon">✦</span>
              <span>{error}</span>
            </div>
          )}
        </>
      )}

      {overlay?.name === "collection" && session && (
        <UserCardsList
          apiUrl={API_URL}
          session={session}
          onClose={closeOverlay}
          onSessionExpired={handleCollectionSessionExpired}
        />
      )}

      {overlay?.name === "shop" && session && (
        <ShopModal
          apiUrl={API_URL}
          session={session}
          balance={balance}
          tab={overlay.tab}
          onTabChange={(tab) => openOverlay({ name: "shop", tab }, { replace: true })}
          onClose={closeOverlay}
          onSessionExpired={handleCollectionSessionExpired}
          onBalanceChange={handleBalanceChange}
        />
      )}

      {overlay?.name === "players" && session && (
        <PlayerProfileModal
          apiUrl={API_URL}
          session={session}
          profile={progress}
          tab={overlay.tab}
          onTabChange={(tab) => openOverlay({ name: "players", tab }, { replace: true })}
          onClose={closeOverlay}
          onSessionExpired={handleCollectionSessionExpired}
          onProfileChange={handleProfileChange}
          onChallenge={challengePlayer}
        />
      )}

      {overlay?.name === "world" && session && (
        <WorldModal
          apiUrl={API_URL}
          session={session}
          tab={overlay.tab}
          regionId={overlay.region}
          onTabChange={(tab) => openOverlay({ name: "world", tab, region: null }, { replace: true })}
          onSelectRegion={(region) =>
            openOverlay({ name: "world", tab: "map", region }, { replace: true })
          }
          onCampaign={(region) =>
            navigate({ screen: "arena", arena: "campaign", region, stage: null })
          }
          onBalanceChange={handleBalanceChange}
          onClose={closeOverlay}
        />
      )}

      {overlay?.name === "grimoire" && (
        <GrimoireModal
          apiUrl={API_URL}
          chapter={overlay.chapter}
          onChapterChange={(chapter) =>
            openOverlay({ name: "grimoire", chapter }, { replace: true })
          }
          onClose={closeOverlay}
        />
      )}

      <AuthModal
        key={authOpen || authGate ? "open" : "closed"}
        open={authOpen || authGate}
        onClose={closeAuth}
        onAuthenticated={handleAuthenticated}
      />
    </main>
  );
}

export default App;
