import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";

const TABS = [
  { value: "name", label: "Your name" },
  { value: "titles", label: "Titles" },
  { value: "search", label: "Find players" },
];

function formatDate(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatWait(seconds) {
  const days = Math.floor(seconds / 86400);
  if (days >= 1) return `${days} day${days === 1 ? "" : "s"}`;
  const hours = Math.max(1, Math.ceil(seconds / 3600));
  return `${hours} hour${hours === 1 ? "" : "s"}`;
}

// Definir/trocar o nome. Regras e tempo de espera vêm do perfil (servidor).
function UsernameForm({ apiUrl, session, profile, onSessionExpired, onProfileChange }) {
  const current = profile?.username ?? "";
  const rules = profile?.usernameRules;
  const change = profile?.usernameChange;
  const [value, setValue] = useState(current);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const locked = change ? !change.canChange : false;
  const trimmed = value.trim();
  const unchanged = trimmed === current;

  async function save() {
    setSaving(true);
    setFeedback(null);

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/users/me/username`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: token },
        body: JSON.stringify({ username: trimmed }),
      });

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 429 && data.usernameChange) {
          onProfileChange({ usernameChange: data.usernameChange });
        }
        setFeedback({ type: "error", text: data.message ?? "Could not change your username." });
        return;
      }

      onProfileChange({ username: data.username, usernameChange: data.usernameChange });
      setValue(data.username);
      setFeedback({ type: "success", text: `You are now known as ${data.username}.` });
    } catch (saveError) {
      console.error(saveError);
      setFeedback({ type: "error", text: "Could not change your username." });
    } finally {
      setSaving(false);
      setConfirming(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!trimmed || unchanged || locked) return;
    setFeedback(null);
    setConfirming(true);
  }

  if (!profile) {
    return (
      <p className="collection-status" role="status">
        Loading...
      </p>
    );
  }

  return (
    <form className="auth-form player-name-form" onSubmit={handleSubmit}>
      <p className="player-name-current">
        {current ? (
          <>
            Current name: <strong>{current}</strong>
          </>
        ) : (
          <>You have not chosen a name yet. Other players cannot find you until you do.</>
        )}
      </p>

      <label className="auth-field">
        <span>Username</span>
        <input
          type="text"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setConfirming(false);
            setFeedback(null);
          }}
          minLength={rules?.minLength}
          maxLength={rules?.maxLength}
          autoComplete="nickname"
          spellCheck={false}
          disabled={saving || locked}
          required
        />
      </label>

      {rules && (
        <p className="auth-hint">
          {rules.minLength}–{rules.maxLength} characters. {rules.allowed}
        </p>
      )}

      {locked ? (
        <p className="auth-info" role="status">
          You changed your name recently. You can change it again in{" "}
          {formatWait(change.retryAfterSeconds)}
          {change.nextChangeAt ? ` (${formatDate(change.nextChangeAt)})` : ""}.
        </p>
      ) : (
        rules && (
          <p className="auth-hint">
            After saving, you will have to wait {rules.changeCooldownDays} days to change it
            again.
          </p>
        )
      )}

      {feedback && (
        <p className={feedback.type === "error" ? "auth-error" : "auth-info"} role="status">
          {feedback.text}
        </p>
      )}

      {confirming ? (
        <div className="player-name-confirm">
          <p>
            Use <strong>{trimmed}</strong> as your name?
          </p>
          <div className="collection-sell-confirm">
            <button
              type="button"
              className="collection-sell-button is-confirm"
              disabled={saving}
              onClick={save}
            >
              {saving ? "Saving..." : "Confirm"}
            </button>
            <button
              type="button"
              className="collection-sell-button is-cancel"
              disabled={saving}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="submit"
          className="auth-submit"
          disabled={saving || locked || !trimmed || unchanged}
        >
          {current ? "Change name" : "Save name"}
        </button>
      )}
    </form>
  );
}

// Busca de jogadores pelo começo do nome. Validação e resultados são do servidor.
// "Challenge" só abre a arena com o adversário escolhido; quem pode desafiar
// quem (nome definido, limite de desafios etc.) é validado no servidor.
function PlayerSearch({ apiUrl, session, minLength, canChallenge, onSessionExpired, onChallenge }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // Nome da última busca feita: buscar de novo o mesmo nome não chama a API.
  const [lastSearched, setLastSearched] = useState(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const trimmed = query.trim();
  const ready = trimmed.length >= (minLength ?? 1);
  const sameAsLast = lastSearched !== null && trimmed.toLowerCase() === lastSearched;
  const canSearch = ready && !loading && !sameAsLast;

  // A busca só chama a API quando o jogador pede (botão ou Enter), não a cada tecla.
  const handleSearch = async (event) => {
    event.preventDefault();
    if (!canSearch) return;

    setLoading(true);
    setError("");

    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(
        `${apiUrl}/users/search?q=${encodeURIComponent(trimmed)}`,
        { headers: { Authorization: token } }
      );

      if (response.status === 401) {
        onSessionExpired();
        return;
      }

      const data = await response.json().catch(() => ({}));
      if (!mounted.current) return;

      if (!response.ok) {
        setResult(null);
        setLastSearched(null);
        setError(data.message ?? "Could not search for players.");
        return;
      }

      setResult(data);
      setLastSearched(trimmed.toLowerCase());
    } catch (searchError) {
      console.error(searchError);
      if (mounted.current) setError("Could not search for players.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  const players = result?.players ?? [];

  return (
    <div className="player-search">
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

      {!ready && minLength && (
        <p className="auth-hint">Type at least {minLength} characters.</p>
      )}

      {error && <p className="auth-error">{error}</p>}

      {!error && !loading && result && players.length === 0 && (
        <p className="collection-status" role="status">
          No players found.
        </p>
      )}

      {players.length > 0 && onChallenge && !canChallenge && (
        <p className="auth-hint">Choose a username (Your name tab) to challenge players.</p>
      )}

      {players.length > 0 && (
        <ul className={`player-results${loading ? " is-loading" : ""}`} aria-busy={loading}>
          {players.map((player) => (
            <li key={player.username} className="player-result">
              <span className="player-result-level" aria-label={`Level ${player.level}`}>
                <span className="hud-level-label">LV</span>
                {player.level}
              </span>
              <span className="player-result-name">
                {player.username}
                {player.title && <em className="player-title">{player.title}</em>}
              </span>
              {player.isYou ? (
                <span className="player-result-you">You</span>
              ) : (
                onChallenge && (
                  <button
                    type="button"
                    className="collection-sell-button is-confirm"
                    disabled={!canChallenge}
                    onClick={() => onChallenge(player)}
                  >
                    Challenge
                  </button>
                )
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Títulos: quais existem, quais foram conquistados e o escolhido vêm de
// GET /users/me/profile; o servidor confere de novo ao escolher.
function TitlePicker({ apiUrl, session, profile, onSessionExpired, onProfileChange }) {
  const [saving, setSaving] = useState(null);
  const [error, setError] = useState("");
  if (!profile) {
    return (
      <p className="collection-status" role="status">
        Loading...
      </p>
    );
  }
  const titles = profile.titles ?? [];
  const current = profile.title?.id ?? null;
  const earned = titles.filter((title) => title.earned).length;

  async function choose(titleId) {
    setSaving(titleId ?? "none");
    setError("");
    try {
      const token = session.session.getIdToken().getJwtToken();
      const response = await fetch(`${apiUrl}/users/me/title`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ titleId }),
      });
      if (response.status === 401) {
        onSessionExpired();
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.message ?? "Could not change your title.");
        return;
      }
      onProfileChange?.({ title: data.title });
    } catch (saveError) {
      console.error(saveError);
      setError("Could not change your title.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="title-picker">
      <p className="auth-hint">
        {earned}/{titles.length} titles earned. Your title appears on your profile, in player
        search and in online duels.
      </p>
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}
      <ul className="title-list">
        <li>
          <button
            type="button"
            className={`title-option${current === null ? " is-active" : ""}`}
            disabled={saving !== null}
            onClick={() => void choose(null)}
          >
            <strong>No title</strong>
          </button>
        </li>
        {titles.map((title) => (
          <li key={title.id}>
            <button
              type="button"
              className={`title-option${current === title.id ? " is-active" : ""}${
                title.earned ? "" : " is-locked"
              }`}
              disabled={!title.earned || saving !== null}
              onClick={() => void choose(title.id)}
            >
              <strong>
                {title.earned ? "✦" : "🔒"} {title.name}
              </strong>
              <span>{title.description}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlayerProfileModal({
  apiUrl,
  session,
  profile,
  tab = "name",
  onTabChange,
  onClose,
  onSessionExpired,
  onProfileChange,
  onChallenge,
}) {
  // A aba vem do endereço (/players, /players/titles, /players/search).
  return (
    <Modal label="Players" className="player-modal" routed onClose={onClose}>
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>SUMMONERS</h2>
        <p>Choose how others see you and find other players.</p>
      </header>

      <div className="shop-tabs" role="tablist" aria-label="Players">
        {TABS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            id={`player-tab-${option.value}`}
            aria-selected={tab === option.value}
            aria-controls="player-panel"
            className={`shop-tab${tab === option.value ? " is-active" : ""}`}
            onClick={() => onTabChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div id="player-panel" role="tabpanel" aria-labelledby={`player-tab-${tab}`}>
        {tab === "titles" ? (
          <TitlePicker
            apiUrl={apiUrl}
            session={session}
            profile={profile}
            onSessionExpired={onSessionExpired}
            onProfileChange={onProfileChange}
          />
        ) : tab === "name" ? (
          <UsernameForm
            key={profile ? "ready" : "loading"}
            apiUrl={apiUrl}
            session={session}
            profile={profile}
            onSessionExpired={onSessionExpired}
            onProfileChange={onProfileChange}
          />
        ) : (
          <PlayerSearch
            apiUrl={apiUrl}
            session={session}
            minLength={profile?.usernameRules?.searchMinLength}
            canChallenge={Boolean(profile?.username)}
            onSessionExpired={onSessionExpired}
            onChallenge={onChallenge}
          />
        )}
      </div>
    </Modal>
  );
}

export default PlayerProfileModal;
