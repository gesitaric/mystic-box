import { getCharacterImage } from "../characterImages";
import Grimoire from "./Grimoire";
import "../styles/home.css";

// Artes de vitrine dos cards de ação (só decoração).
const SUMMON_ART = ["lyra.png", "astra.jfif", "seraphiel.jfif"];
const BATTLE_ART = ["pyralis.jfif", "malachar.jfif"];

// Nível e experiência do jogador, como o servidor calculou.
export function LevelBadge({ progress, compact = false }) {
  if (!progress) return null;

  const { level, maxLevel, levelExperience, nextLevelExperience } = progress;
  const atMax = nextLevelExperience == null;
  const percent = atMax
    ? 100
    : Math.min(100, Math.round((levelExperience / nextLevelExperience) * 100));

  return (
    <div
      className={`level-badge${compact ? " is-compact" : ""}`}
      aria-label={
        atMax
          ? `Level ${level} (max)`
          : `Level ${level}, ${levelExperience} of ${nextLevelExperience} experience`
      }
    >
      <span className="level-badge-level">
        <span className="level-badge-label">LV</span>
        {level}
      </span>
      <span className="level-badge-progress">
        <span className="level-badge-bar" aria-hidden="true">
          <span className="level-badge-fill" style={{ width: `${percent}%` }} />
        </span>
        <span className="level-badge-xp">
          {atMax ? `Max level ${maxLevel}` : `${levelExperience} / ${nextLevelExperience} XP`}
        </span>
      </span>
    </div>
  );
}

// Perfil do HUD: anel de nível com a experiência e o nome do jogador.
// Clicar abre a escolha do nome. Sem nome definido, mostra o identificador de hoje.
function ProfileChip({ email, progress, onClick }) {
  const level = progress?.level;
  const atMax = Boolean(progress) && progress.nextLevelExperience == null;
  let percent = 0;
  if (atMax) percent = 100;
  else if (progress) {
    percent = Math.min(100, (progress.levelExperience / progress.nextLevelExperience) * 100);
  }
  const username = progress?.username;
  const name = username || (email ? email.split("@")[0] : "Summoner");

  let xpText = "…";
  if (atMax) xpText = "MAX LEVEL";
  else if (progress) xpText = `${progress.levelExperience} / ${progress.nextLevelExperience} XP`;

  return (
    <button
      type="button"
      className="hud-profile"
      onClick={onClick}
      aria-label={`${progress ? `${name}, level ${level}, ${xpText}` : name}. ${
        username ? "Change name" : "Choose a name"
      }`}
      title={username ? "Change name" : "Choose a name"}
    >
      <span className="hud-level" style={{ "--xp": `${percent * 3.6}deg` }} aria-hidden="true">
        <span className="hud-level-inner">
          <span className="hud-level-label">LV</span>
          {level ?? "—"}
        </span>
      </span>
      <span className="hud-profile-info" aria-hidden="true">
        <span className="hud-name">
          {name}
          {progress && !username && <span className="hud-name-hint">Set name</span>}
        </span>
        <span className="hud-xp-bar">
          <span className="hud-xp-fill" style={{ width: `${percent}%` }} />
        </span>
        <span className="hud-xp-text">{xpText}</span>
      </span>
    </button>
  );
}

// Tela inicial do usuário logado, no formato de lobby de jogo: HUD em cima,
// ações principais no centro e atalhos embaixo. Só apresenta o que veio da
// API (saldo, nível, vitórias, tempo de espera).
function HomeScreen({
  apiUrl,
  email,
  balance,
  progress,
  cooldownLabel,
  onSummon,
  onBattle,
  onCollection,
  onShop,
  onProfile,
  onPlayers,
  onSignOut,
}) {
  const wins = progress?.wins ?? 0;
  const losses = progress?.losses ?? 0;

  return (
    <section className="lobby" aria-label="Home">
      <header className="lobby-hud">
        <ProfileChip email={email} progress={progress} onClick={onProfile} />

        <div className="hud-right">
          <button
            type="button"
            className="hud-currency"
            onClick={onShop}
            aria-label={`${balance ?? 0} Arcane Shards. Open shop`}
            title="Arcane Shards · open shop"
          >
            <span className="wallet-icon" aria-hidden="true">
              ✧
            </span>
            <span className="hud-currency-amount">{balance ?? "—"}</span>
            <span className="hud-currency-plus" aria-hidden="true">
              +
            </span>
          </button>

          <button
            type="button"
            className="hud-icon-button"
            onClick={onSignOut}
            aria-label="Sign out"
            title="Sign out"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </header>

      <div className="lobby-logo">
        <span className="title-ornament">✦ ✧ ✦</span>
        <h1>MYSTIC BOX</h1>
        <p className="tagline">ARCANE SUMMONING</p>
      </div>

      <nav className="lobby-main" aria-label="Main actions">
        <button type="button" className="lobby-card is-summon" onClick={onSummon}>
          <span className="lobby-card-art" aria-hidden="true">
            {SUMMON_ART.map((fileName, index) => (
              <img
                key={fileName}
                src={getCharacterImage(fileName)}
                alt=""
                className={`lobby-fan lobby-fan-${index}`}
              />
            ))}
            <span className="lobby-portal-glow" />
          </span>
          <span className="lobby-card-body">
            <span className="lobby-card-kicker">Arcane portal</span>
            <span className="lobby-card-title">Summon</span>
            {cooldownLabel ? (
              <span className="lobby-card-status is-waiting">
                Recharging · <span className="cooldown-time">{cooldownLabel}</span>
              </span>
            ) : (
              <span className="lobby-card-status is-ready">Portal ready</span>
            )}
          </span>
        </button>

        <button type="button" className="lobby-card is-battle" onClick={onBattle}>
          <span className="lobby-card-art" aria-hidden="true">
            <img
              src={getCharacterImage(BATTLE_ART[0])}
              alt=""
              className="lobby-duel lobby-duel-left"
            />
            <img
              src={getCharacterImage(BATTLE_ART[1])}
              alt=""
              className="lobby-duel lobby-duel-right"
            />
            <span className="lobby-vs">VS</span>
          </span>
          <span className="lobby-card-body">
            <span className="lobby-card-kicker">Arena</span>
            <span className="lobby-card-title">Battle</span>
            <span className="lobby-card-status">
              {wins}W · {losses}L
            </span>
          </span>
        </button>
      </nav>

      <nav className="lobby-dock" aria-label="Shortcuts">
        <button type="button" className="dock-button" onClick={onCollection}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <rect x="3" y="5" width="11" height="15" rx="2" fill="none" stroke="currentColor" strokeWidth="1.7" />
            <path d="M17 7l3 1-3 12-3-1" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
            <path d="M8.5 10l1.2 2.4 2.3.3-1.7 1.6.4 2.4-2.2-1.2-2.2 1.2.4-2.4L5 12.7l2.3-.3z" fill="currentColor" />
          </svg>
          <span>Collection</span>
        </button>
        <button type="button" className="dock-button" onClick={onShop}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d="M4 9h16l-1.5 11h-13z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
            <path d="M8 9V7a4 4 0 0 1 8 0v2" fill="none" stroke="currentColor" strokeWidth="1.7" />
            <path d="M12 12.5l1 2 2.2.3-1.6 1.5.4 2.2-2-1.1-2 1.1.4-2.2-1.6-1.5 2.2-.3z" fill="currentColor" />
          </svg>
          <span>Shop</span>
        </button>
        <button type="button" className="dock-button" onClick={onPlayers}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <circle cx="10" cy="10" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
            <path d="M14.2 14.2L20 20" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
            <path d="M7.4 12.4a3 3 0 0 1 5.2 0" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx="10" cy="8.6" r="1.5" fill="currentColor" />
          </svg>
          <span>Players</span>
        </button>
        <Grimoire apiUrl={apiUrl} variant="dock" />
      </nav>
    </section>
  );
}

export default HomeScreen;
