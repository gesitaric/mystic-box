import { useCallback, useEffect, useRef, useState } from "react";
import TeamSetup from "./TeamSetup";
import { SessionExpired } from "./arenaApi";
import Countdown from "../Countdown";
import { exitTo, navigate } from "../../router";

const DUEL_LIST = { screen: "arena", arena: "pvp", duel: "list" };

function LevelTag({ level }) {
  // Rival vindo de um link (/arena/duel/challenge?vs=nome): o nível não é conhecido.
  if (level == null) return null;
  return (
    <span className="player-result-level" aria-label={`Level ${level}`}>
      <span className="hud-level-label">LV</span>
      {level}
    </span>
  );
}

// Busca o adversário pelo começo do nome. Resultados vêm do servidor.
function OpponentSearch({ request, selected, onSelect }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // Nome da última busca feita: buscar de novo o mesmo nome não chama a API.
  const [lastSearched, setLastSearched] = useState(null);
  const mounted = useRef(true);
  const trimmed = query.trim();
  const sameAsLast = lastSearched !== null && trimmed.toLowerCase() === lastSearched;
  const canSearch = Boolean(trimmed) && !loading && !sameAsLast;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // A busca só chama a API quando o jogador pede (botão ou Enter), não a cada tecla.
  const handleSearch = async (event) => {
    event.preventDefault();
    if (!canSearch) return;
    setLoading(true);
    setError("");
    try {
      const { ok, data } = await request(`/users/search?q=${encodeURIComponent(trimmed)}`);
      if (!mounted.current) return;
      if (!ok) {
        setResult(null);
        setLastSearched(null);
        setError(data.message ?? "Could not search for players.");
        return;
      }
      setResult(data);
      setLastSearched(trimmed.toLowerCase());
    } catch (searchError) {
      if (searchError instanceof SessionExpired || !mounted.current) return;
      console.error(searchError);
      setError("Could not search for players.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  const players = (result?.players ?? []).filter((player) => !player.isYou);

  return (
    <section className="battle-panel" aria-label="Opponent">
      <h2 className="battle-panel-title">Choose your rival</h2>
      {selected ? (
        <div className="pvp-selected">
          <LevelTag level={selected.level} />
          <span className="player-result-name">{selected.username}</span>
          <button type="button" className="collection-sell-button is-cancel" onClick={() => onSelect(null)}>
            Change
          </button>
        </div>
      ) : (
        <>
          <form className="player-search-form" onSubmit={handleSearch}>
            <label className="auth-field">
              <span>Player name</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Type a name..."
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            <button type="submit" className="auth-submit" disabled={!canSearch}>
              {loading ? "Searching..." : "Search"}
            </button>
          </form>
          {error && <p className="auth-error">{error}</p>}
          {!error && !loading && result && players.length === 0 && (
            <p className="collection-status">No players found.</p>
          )}
          {players.length > 0 && (
            <ul className={`player-results${loading ? " is-loading" : ""}`}>
              {players.map((player) => (
                <li key={player.username} className="player-result">
                  <LevelTag level={player.level} />
                  <span className="player-result-name">{player.username}</span>
                  <button
                    type="button"
                    className="collection-sell-button is-confirm"
                    onClick={() => onSelect(player)}
                  >
                    Select
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

// Quem está online agora (devolvido pelo servidor em GET /pvp), com desafio
// em um clique. O próprio jogador aparece marcado como "You".
function OnlinePlayers({ online, outgoing, canChallenge, onChallenge }) {
  const challenged = new Set(outgoing.map((entry) => entry.username.toLowerCase()));
  const others = online.filter((player) => !player.isYou);
  return (
    <section className="battle-panel" aria-label="Online now">
      <h2 className="battle-panel-title">
        Online now <span className="battle-panel-count">{others.length}</span>
      </h2>
      {others.length === 0 && (
        <p className="collection-status">
          No other summoners here right now. Stay a while or challenge someone by name.
        </p>
      )}
      {online.length > 0 && (
        <ul className="player-results pvp-online">
          {online.map((player) => {
            let status = null;
            if (player.isYou) status = <span className="player-result-you">You</span>;
            else if (player.inDuel) status = <span className="pvp-online-status">In a duel</span>;
            else if (challenged.has(player.username.toLowerCase())) {
              status = <span className="pvp-online-status">Challenged</span>;
            }
            return (
              <li key={player.username} className="player-result">
                <LevelTag level={player.level} />
                <span className="pvp-online-name">
                  <span className="player-result-name">{player.username}</span>
                  {player.title && <span className="pvp-online-title">{player.title}</span>}
                </span>
                {status ?? (
                  <button
                    type="button"
                    className="collection-sell-button is-confirm"
                    disabled={!canChallenge}
                    onClick={() => onChallenge(player)}
                  >
                    Challenge
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

// Duelos de outros jogadores em andamento (devolvidos pelo servidor), para
// assistir. O próprio duelo aparece marcado, sem o botão.
function LiveDuels({ duels, onWatch }) {
  return (
    <section className="battle-panel" aria-label="Duels in progress">
      <h2 className="battle-panel-title">
        Duels in progress <span className="battle-panel-count">{duels.length}</span>
      </h2>
      {duels.length === 0 ? (
        <p className="collection-status">No duels right now.</p>
      ) : (
        <ul className="player-results pvp-live">
          {duels.map((duel) => (
            <li key={duel.battleId} className="player-result">
              <span className="pvp-live-names">
                <span className="player-result-name">{duel.players.player.username}</span>
                <span className="pvp-live-vs">vs</span>
                <span className="player-result-name">{duel.players.enemy.username}</span>
              </span>
              <span className="pvp-expires">
                Round {duel.round}/{duel.maxRounds}
              </span>
              {duel.isYours ? (
                <span className="player-result-you">Yours</span>
              ) : (
                <button
                  type="button"
                  className="collection-sell-button is-confirm"
                  onClick={() => onWatch(duel)}
                >
                  Watch
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// Lobby do duelo online: quem está online, duelos para assistir, desafios recebidos e enviados,
// desafiar alguém e aceitar um desafio. Regras, prazos e validações são do
// servidor. Enquanto a tela está aberta (e a aba visível), o lobby é
// consultado de tempos em tempos (o intervalo vem das regras): isso mantém o
// jogador na lista de quem está online e leva ao duelo quando aceitam o desafio.
function PvpLobby({
  apiUrl,
  session,
  request,
  route,
  routeData,
  initialTeam,
  cachedCards,
  onCardsLoaded,
  onTeamChosen,
  onEnterDuel,
  onSessionExpired,
}) {
  const [lobby, setLobby] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // Tela do lobby, lida do endereço: list | challenge | accept.
  let view = { name: "list" };
  if (route.duel === "challenge") {
    const opponent =
      routeData?.opponent?.username === route.vs && route.vs
        ? routeData.opponent
        : route.vs
          ? { username: route.vs, level: null }
          : null;
    view = { name: "challenge", opponent };
  } else if (route.duel === "accept") {
    // O desafio vem do sininho junto com o endereço; num link direto, da lista.
    const challenge =
      (routeData?.challenge?.challengeId === route.challengeId ? routeData.challenge : null) ??
      lobby?.incoming?.find((entry) => entry.challengeId === route.challengeId);
    if (challenge) view = { name: "accept", challenge };
  }
  const missingChallenge = route.duel === "accept" && Boolean(lobby) && view.name !== "accept";

  // Desafio que não existe mais (expirou, foi cancelado): volta à lista.
  useEffect(() => {
    if (missingChallenge) navigate(DUEL_LIST, { replace: true });
  }, [missingChallenge]);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [pageVisible, setPageVisible] = useState(() => document.visibilityState !== "hidden");

  const refresh = useCallback(async () => {
    try {
      const { ok, data } = await request("/pvp");
      if (!ok) {
        setError(data.message ?? "Could not load the duels.");
        return;
      }
      setError("");
      // receivedAt: base da contagem regressiva dos prazos devolvidos.
      setLobby({ ...data, receivedAt: Date.now() });
      if (data.battle) onEnterDuel();
    } catch (loadError) {
      if (loadError instanceof SessionExpired) return;
      console.error(loadError);
      setError("Could not reach the arena.");
    }
  }, [request, onEnterDuel]);

  // Uma consulta ao abrir e outra ao voltar para a aba.
  useEffect(() => {
    if (!pageVisible) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh, pageVisible]);

  useEffect(() => {
    function handleVisibility() {
      setPageVisible(document.visibilityState !== "hidden");
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  // Depois, de tempos em tempos (com a aba escondida, não consulta).
  const refreshSeconds = lobby?.rules?.lobbyRefreshSeconds;
  useEffect(() => {
    if (!refreshSeconds || !pageVisible) return undefined;
    const timer = setInterval(() => void refresh(), refreshSeconds * 1000);
    return () => clearInterval(timer);
  }, [refreshSeconds, pageVisible, refresh]);

  // Ao sair da tela de duelo, sai da lista de quem está online.
  const requestRef = useRef(request);
  useEffect(() => {
    requestRef.current = request;
  });
  useEffect(
    () => () => {
      requestRef.current("/pvp/leave", { method: "POST" }).catch(() => {});
    },
    []
  );

  async function manualRefresh() {
    setRefreshing(true);
    setNotice("");
    await refresh();
    setRefreshing(false);
  }

  const teamSize = lobby?.rules?.teamSize ?? 3;

  async function sendChallenge(team) {
    setSubmitting(true);
    setSubmitError("");
    onTeamChosen(team);
    try {
      const { ok, data } = await request("/pvp/challenges", {
        method: "POST",
        body: JSON.stringify({ username: view.opponent.username, team }),
      });
      if (!ok) {
        setSubmitError(data.message ?? "Could not send the challenge.");
        return;
      }
      setNotice(
        `Challenge sent to ${data.challenge.username}. Stay here: the duel starts as soon as they accept.`
      );
      exitTo("/arena/duel");
      void refresh();
    } catch (sendError) {
      if (sendError instanceof SessionExpired) return;
      console.error(sendError);
      setSubmitError("Could not send the challenge.");
    } finally {
      setSubmitting(false);
    }
  }

  async function acceptChallenge(team) {
    setSubmitting(true);
    setSubmitError("");
    onTeamChosen(team);
    try {
      const { ok, data } = await request("/pvp/challenges/accept", {
        method: "POST",
        body: JSON.stringify({ challengeId: view.challenge.challengeId, team }),
      });
      if (!ok) {
        setSubmitError(data.message ?? "Could not accept the challenge.");
        void refresh();
        return;
      }
      onEnterDuel();
    } catch (acceptError) {
      if (acceptError instanceof SessionExpired) return;
      console.error(acceptError);
      setSubmitError("Could not accept the challenge.");
    } finally {
      setSubmitting(false);
    }
  }

  async function dismiss(path, challengeId) {
    setBusyId(challengeId);
    setNotice("");
    try {
      const { ok, data } = await request(path, {
        method: "POST",
        body: JSON.stringify({ challengeId }),
      });
      if (!ok) setNotice(data.message ?? "That challenge is no longer available.");
      await refresh();
    } catch (dismissError) {
      if (dismissError instanceof SessionExpired) return;
      console.error(dismissError);
      setNotice("Could not reach the arena.");
    } finally {
      setBusyId(null);
    }
  }

  function openView(next) {
    setSubmitError("");
    setNotice("");
    if (next.name === "list") {
      exitTo("/arena/duel");
    } else if (next.name === "accept") {
      navigate(
        { ...DUEL_LIST, duel: "accept", challengeId: next.challenge.challengeId },
        { data: { challenge: next.challenge } }
      );
    } else {
      navigate({ ...DUEL_LIST, duel: "challenge", vs: null });
    }
  }

  // Desafio a partir da lista de quem está online.
  function challengePlayer(player) {
    setSubmitError("");
    setNotice("");
    navigate(
      { ...DUEL_LIST, duel: "challenge", vs: player.username },
      { data: { opponent: { username: player.username, level: player.level } } }
    );
  }

  function watchDuel(duel) {
    setNotice("");
    navigate({ ...DUEL_LIST, duel: "watch", battleId: duel.battleId });
  }

  // Rival escolhido (ou trocado) fica no endereço da mesma tela.
  function selectOpponent(opponent) {
    navigate(
      { ...DUEL_LIST, duel: "challenge", vs: opponent?.username ?? null },
      { replace: true, data: opponent ? { opponent } : null }
    );
  }

  if (!lobby) {
    return (
      <p className="collection-status" role="status">
        {error || "Looking for rivals..."}
      </p>
    );
  }

  if (view.name === "challenge" || view.name === "accept") {
    const accepting = view.name === "accept";
    return (
      <TeamSetup
        apiUrl={apiUrl}
        session={session}
        setup={{ teamSize }}
        initialTeam={initialTeam}
        starting={submitting}
        startError={submitError}
        onStart={accepting ? acceptChallenge : sendChallenge}
        onSessionExpired={onSessionExpired}
        startLabel={accepting ? "Accept duel" : "Send challenge"}
        startingLabel={accepting ? "Entering the duel..." : "Sending..."}
        canStart={accepting || Boolean(view.opponent)}
        cachedCards={cachedCards}
        onCardsLoaded={onCardsLoaded}
      >
        <div className="pvp-back">
          <button type="button" className="session-button" onClick={() => openView({ name: "list" })}>
            ← Duels
          </button>
        </div>
        {accepting ? (
          <section className="battle-panel" aria-label="Challenge">
            <h2 className="battle-panel-title">
              Duel against {view.challenge.username}
            </h2>
            <p className="battle-inspect-desc">
              Choose the {teamSize} cards that will answer the challenge.
            </p>
          </section>
        ) : (
          <OpponentSearch
            request={request}
            selected={view.opponent}
            onSelect={selectOpponent}
          />
        )}
      </TeamSetup>
    );
  }

  const { incoming, outgoing, rules } = lobby;
  const canChallenge = lobby.hasUsername && outgoing.length < rules.maxOutgoingChallenges;

  return (
    <div className="battle-setup pvp-lobby">
      <div className="pvp-refresh">
        <button
          type="button"
          className="session-button"
          disabled={refreshing}
          onClick={() => void manualRefresh()}
        >
          {refreshing ? "Checking..." : "↻ Refresh"}
        </button>
      </div>
      {!lobby.hasUsername && (
        <section className="battle-panel">
          <p className="auth-info">
            Choose a username (Players, on the home screen) to challenge other summoners.
            Without one, nobody can find you.
          </p>
        </section>
      )}

      {error && <p className="auth-error">{error}</p>}
      {notice && (
        <p className="auth-info" role="status">
          {notice}
        </p>
      )}

      <OnlinePlayers
        online={lobby.online ?? []}
        outgoing={outgoing}
        canChallenge={canChallenge}
        onChallenge={challengePlayer}
      />

      <LiveDuels duels={lobby.liveDuels ?? []} onWatch={watchDuel} />

      <section className="battle-panel" aria-label="Challenges received">
        <h2 className="battle-panel-title">
          Challenges for you <span className="battle-panel-count">{incoming.length}</span>
        </h2>
        {incoming.length === 0 ? (
          <p className="collection-status">No one has challenged you yet.</p>
        ) : (
          <ul className="player-results pvp-challenges">
            {incoming.map((entry) => (
              <li key={entry.challengeId} className="player-result">
                <LevelTag level={entry.level} />
                <span className="player-result-name">{entry.username}</span>
                <span className="pvp-expires">
                  <Countdown
                    seconds={entry.expiresInSeconds}
                    since={lobby.receivedAt}
                    onExpire={refresh}
                  />
                </span>
                <span className="pvp-challenge-actions">
                  <button
                    type="button"
                    className="collection-sell-button is-confirm"
                    disabled={busyId === entry.challengeId}
                    onClick={() => openView({ name: "accept", challenge: entry })}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="collection-sell-button is-cancel"
                    disabled={busyId === entry.challengeId}
                    onClick={() => void dismiss("/pvp/challenges/decline", entry.challengeId)}
                  >
                    Decline
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="battle-panel" aria-label="Challenges sent">
        <h2 className="battle-panel-title">
          Your challenges{" "}
          <span className="battle-panel-count">
            {outgoing.length}/{rules.maxOutgoingChallenges}
          </span>
        </h2>
        {outgoing.length > 0 && (
          <ul className="player-results pvp-challenges">
            {outgoing.map((entry) => (
              <li key={entry.challengeId} className="player-result">
                <LevelTag level={entry.level} />
                <span className="player-result-name">{entry.username}</span>
                <span className="pvp-expires">
                  <Countdown
                    seconds={entry.expiresInSeconds}
                    since={lobby.receivedAt}
                    onExpire={refresh}
                    prefix="Waiting · "
                  />
                </span>
                <span className="pvp-challenge-actions">
                  <button
                    type="button"
                    className="collection-sell-button is-cancel"
                    disabled={busyId === entry.challengeId}
                    onClick={() => void dismiss("/pvp/challenges/cancel", entry.challengeId)}
                  >
                    Cancel
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="battle-setup-actions">
          <button
            type="button"
            className="keep-button"
            disabled={!canChallenge}
            onClick={() => openView({ name: "challenge", opponent: null })}
          >
            Challenge by name
          </button>
        </div>
      </section>
    </div>
  );
}

export default PvpLobby;
