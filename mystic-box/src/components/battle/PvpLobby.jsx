import { useCallback, useEffect, useState } from "react";
import TeamSetup from "./TeamSetup";
import { SessionExpired } from "./arenaApi";

const SEARCH_DEBOUNCE_MS = 350;

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function LevelTag({ level }) {
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
  const trimmed = query.trim();

  useEffect(() => {
    if (!trimmed) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const { ok, data } = await request(`/users/search?q=${encodeURIComponent(trimmed)}`);
        if (cancelled) return;
        if (!ok) {
          setResult(null);
          setError(data.message ?? "Could not search for players.");
          return;
        }
        setResult(data);
      } catch (searchError) {
        if (searchError instanceof SessionExpired || cancelled) return;
        console.error(searchError);
        setError("Could not search for players.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [request, trimmed]);

  const players = trimmed ? (result?.players ?? []).filter((player) => !player.isYou) : [];

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
          <label className="auth-field">
            <span>Player name</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Start typing a name..."
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          {trimmed && error && <p className="auth-error">{error}</p>}
          {trimmed && !error && !loading && result && players.length === 0 && (
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

// Lobby do duelo online: desafios recebidos e enviados, desafiar alguém e
// aceitar um desafio. Regras, prazos e validações são do servidor.
function PvpLobby({
  apiUrl,
  session,
  request,
  initialTeam,
  initialChallenge,
  onTeamChosen,
  onEnterDuel,
  onSessionExpired,
}) {
  const [lobby, setLobby] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // list | challenge | accept
  const [view, setView] = useState(
    initialChallenge ? { name: "accept", challenge: initialChallenge } : { name: "list" }
  );
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const { ok, data } = await request("/pvp");
      if (!ok) {
        setError(data.message ?? "Could not load the duels.");
        return;
      }
      setError("");
      setLobby(data);
      if (data.battle) onEnterDuel();
    } catch (loadError) {
      if (loadError instanceof SessionExpired) return;
      console.error(loadError);
      setError("Could not reach the arena.");
    }
  }, [request, onEnterDuel]);

  // Uma consulta ao abrir; depois só quando o jogador pede (botão Refresh).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

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
        `Challenge sent to ${data.challenge.username}. Press Refresh to see if they accepted.`
      );
      setView({ name: "list" });
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
    setView(next);
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
            onSelect={(opponent) => setView({ name: "challenge", opponent })}
          />
        )}
      </TeamSetup>
    );
  }

  const { incoming, outgoing, rules } = lobby;

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
                <span className="pvp-expires">{formatClock(entry.expiresInSeconds)}</span>
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
                  Waiting · {formatClock(entry.expiresInSeconds)}
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
            disabled={!lobby.hasUsername || outgoing.length >= rules.maxOutgoingChallenges}
            onClick={() => openView({ name: "challenge", opponent: null })}
          >
            Challenge a player
          </button>
        </div>
      </section>
    </div>
  );
}

export default PvpLobby;
