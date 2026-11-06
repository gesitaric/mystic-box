import { useCallback, useEffect, useRef, useState } from "react";
import { getCharacterImage } from "../../characterImages";
import { LevelBadge } from "../HomeScreen";
import Grimoire from "../Grimoire";
import LevelUpCelebration from "./LevelUpCelebration";
import PvpLobby from "./PvpLobby";
import TeamSetup, { SkillList, StatGrid } from "./TeamSetup";
import { SessionExpired, arenaRequest } from "./arenaApi";
import "../../styles/battle.css";
import {
  ELEMENT_STYLE,
  END_REASON_TEXT,
  STATUS_ICON,
  TARGET_LABELS,
  describeEvent,
  eventDelay,
} from "./battlePresentation";
import { createBattleAudio } from "./battleAudio";
import { readSoundPreference, storeSoundPreference } from "../../audio/soundPreference";

const SINGLE_TARGETS = ["enemy", "ally", "fallen_ally"];
const LOG_LIMIT = 60;
const FLOAT_MS = 1100;
// A celebração de nível entra depois da fanfarra de vitória/derrota.
const LEVEL_UP_DELAY_MS = 1100;
// Duelo online: de quanto em quanto tempo busca a jogada do adversário. Começa
// em DUEL_POLL_MS e cresce (x DUEL_POLL_GROWTH) enquanto nada muda, até
// DUEL_POLL_MAX_MS; volta ao começo quando chega jogada nova.
const DUEL_POLL_MS = 1500;
const DUEL_POLL_GROWTH = 1.5;
const DUEL_POLL_MAX_MS = 5000;
// Folga depois do fim do turno antes de conferir o que o servidor fez.
const TURN_END_MARGIN_MS = 1000;

const ARENA_TABS = [
  { value: "pve", label: "vs Computer" },
  { value: "pvp", label: "Online duel" },
];

// Guarda quando a resposta chegou, para contar o tempo de turno na tela.
function received(battle) {
  return battle ? { ...battle, receivedAt: Date.now() } : battle;
}

function SoundButton({ on, onToggle }) {
  return (
    <button
      type="button"
      className="battle-sound"
      onClick={onToggle}
      aria-pressed={on}
      aria-label={on ? "Mute sound" : "Unmute sound"}
      title={on ? "Mute sound" : "Unmute sound"}
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
        {on ? (
          <path
            d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        ) : (
          <path d="M16 9l5 6M21 9l-5 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        )}
      </svg>
    </button>
  );
}

// Antes da primeira animação, todos aparecem como no começo da batalha.
function freshView(view) {
  return {
    ...view,
    turn: null,
    actions: [],
    units: view.units.map((unit) => ({ ...unit, hp: unit.maxHp, alive: true, statuses: [] })),
  };
}

function AetherMeter({ label, value, max, side }) {
  return (
    <div className={`battle-aether is-${side}`} aria-label={`${label}: ${value} of ${max} Aether`}>
      <span className="battle-aether-label">{label}</span>
      <span className="battle-aether-pips" aria-hidden="true">
        {Array.from({ length: max }, (_, index) => (
          <span key={index} className={`battle-aether-pip${index < value ? " is-full" : ""}`} />
        ))}
      </span>
      <span className="battle-aether-value">{value}</span>
    </div>
  );
}

function BattleUnit({ unit, hp, alive, active, acting, targetable, inspected, floats, onClick }) {
  const element = ELEMENT_STYLE[unit.element];
  const percent = Math.max(0, Math.min(100, (hp / unit.maxHp) * 100));
  const hit = floats.some((float) => float.kind === "damage");
  const clickable = Boolean(onClick);

  return (
    <div
      className={[
        "battle-unit",
        `is-${unit.side}`,
        !alive && "is-fallen",
        active && "is-active",
        acting && "is-acting",
        targetable && "is-targetable",
        inspected && "is-inspected",
        hit && "is-hit",
      ]
        .filter(Boolean)
        .join(" ")}
      data-rarity={unit.rarity}
      style={{ "--element": element?.color }}
      {...(clickable
        ? {
            role: "button",
            tabIndex: 0,
            onClick,
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick();
              }
            },
          }
        : {})}
      aria-label={`${unit.name}, ${alive ? `${hp} of ${unit.maxHp} vitality` : "fallen"}${
        targetable ? ", select as target" : ""
      }`}
    >
      <div className="battle-unit-art">
        <img src={getCharacterImage(unit.fileName)} alt="" />
        <span className="battle-unit-element" title={unit.elementLabel}>
          {element?.icon}
        </span>
        <span className="battle-unit-level">Lv {unit.level}</span>
      </div>
      <div className="battle-unit-body">
        <span className="battle-unit-name">{unit.name}</span>
        <span className="battle-unit-class">{unit.archetypeLabel}</span>
        <span className="battle-hp" aria-hidden="true">
          <span
            className={`battle-hp-fill${percent < 30 ? " is-low" : ""}`}
            style={{ width: `${percent}%` }}
          />
        </span>
        <span className="battle-hp-text">
          {hp} / {unit.maxHp}
        </span>
        <span className="battle-unit-statuses">
          {unit.statuses.map((status) => (
            <span
              key={status.id}
              className={`battle-status is-${status.kind}`}
              title={`${status.label} (${status.turns}): ${status.description}`}
            >
              {STATUS_ICON[status.id] ?? "•"}
              <span className="battle-status-turns">{status.turns}</span>
            </span>
          ))}
        </span>
      </div>
      {floats.map((float) => (
        <span key={float.id} className={`battle-float is-${float.kind}`} aria-hidden="true">
          {float.text}
        </span>
      ))}
    </div>
  );
}

const RESULT_TITLE = { won: "VICTORY", lost: "DEFEAT", draw: "DRAW" };

function BattleResult({ result, onAgain, onExit }) {
  const won = result.outcome === "won";
  return (
    <div className="battle-result" role="dialog" aria-modal="true" aria-label="Battle result">
      <div className={`battle-result-card${won ? " is-won" : " is-lost"}`}>
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>{RESULT_TITLE[result.outcome] ?? "DEFEAT"}</h2>
        <p className="battle-result-reason">{END_REASON_TEXT[result.reason] ?? ""}</p>
        <p className="battle-result-xp">+{result.experienceGained} XP</p>
        {result.leveledUp && (
          <p className="battle-result-levelup">
            Level up! You reached level {result.level}
            {result.shardsReward > 0 && <> and earned ✧ {result.shardsReward}</>}.
          </p>
        )}
        <LevelBadge progress={result.progress} />
        <div className="battle-result-actions">
          <button type="button" className="keep-button" onClick={onAgain}>
            Battle again
          </button>
          <button type="button" className="session-button" onClick={onExit}>
            Home
          </button>
        </div>
      </div>
    </div>
  );
}

// Tela de batalha contra o computador. Tudo (dano, turnos, IA, recompensas)
// é decidido pelo servidor; aqui só se pedem ações e se anima o resultado.
function BattleScreen({
  apiUrl,
  session,
  duelIntent,
  onExit,
  onSessionExpired,
  onProgressChange,
  onBalanceChange,
}) {
  const [phase, setPhase] = useState("loading"); // loading | setup | battle | error
  const [setup, setSetup] = useState(null);
  const [view, setView] = useState(null);
  const [playback, setPlayback] = useState(null);
  const [hpOverride, setHpOverride] = useState({});
  const [aetherOverride, setAetherOverride] = useState(null);
  const [actingId, setActingId] = useState(null);
  const [floats, setFloats] = useState([]);
  const [log, setLog] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [startError, setStartError] = useState("");
  const [starting, setStarting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [inspectedId, setInspectedId] = useState(null);
  const [autoMode, setAutoMode] = useState(false);
  const [confirmForfeit, setConfirmForfeit] = useState(false);
  const [lastTeam, setLastTeam] = useState([]);
  const [showLevelUp, setShowLevelUp] = useState(false);
  // Aba da preparação: contra o computador ou duelo online.
  const [arena, setArena] = useState(duelIntent ? "pvp" : "pve");
  const [clock, setClock] = useState(() => Date.now());
  // Último lote de eventos do duelo já recebido.
  const seqRef = useRef(0);
  const enteringDuel = useRef(false);
  // Consultas seguidas sem novidade (para o intervalo crescente).
  const idlePolls = useRef(0);
  // Duelo na tela: as consultas vão direto a ele (uma leitura no servidor).
  const battleIdRef = useRef(null);
  // Aba visível: com a aba escondida o duelo não é consultado.
  const [pageVisible, setPageVisible] = useState(() => document.visibilityState !== "hidden");
  const busyRef = useRef(false);
  const floatId = useRef(0);
  const logEnd = useRef(null);
  const [soundOn, setSoundOn] = useState(readSoundPreference);
  const audio = useRef(null);
  // Callbacks do App sem reiniciar a animação quando a identidade muda.
  const callbacks = useRef({ onProgressChange, onBalanceChange });
  const autoRef = useRef(autoMode);

  useEffect(() => {
    callbacks.current = { onProgressChange, onBalanceChange };
    autoRef.current = autoMode;
    battleIdRef.current = view?.battleId ?? null;
  });

  useEffect(() => {
    audio.current = createBattleAudio();
    return () => {
      audio.current?.destroy();
      audio.current = null;
    };
  }, []);

  useEffect(() => {
    audio.current?.setEnabled(soundOn);
    storeSoundPreference(soundOn);
  }, [soundOn]);

  const request = useCallback(
    (path, init) => arenaRequest({ apiUrl, session, onSessionExpired }, path, init),
    [apiUrl, session, onSessionExpired]
  );

  const loadCurrent = useCallback(async () => {
    setPhase("loading");
    setError("");
    try {
      const [current, duel] = await Promise.all([
        request("/battles/current"),
        request("/pvp/battle"),
      ]);
      const { ok, status, data } = current;
      if (!ok) throw new Error(data.message ?? `Failed to load (${status}).`);
      setSetup({ teamSize: data.teamSize, difficulties: data.difficulties });
      if (data.progress) callbacks.current.onProgressChange?.(data.progress);
      // Um duelo em andamento tem prioridade: o tempo de turno está correndo.
      const activeDuel = duel.ok && duel.data.battle?.status === "active" ? duel.data.battle : null;
      if (activeDuel) {
        seqRef.current = activeDuel.seq;
        setArena("pvp");
        setView(received(activeDuel));
        setLog([{ id: "resume", text: "Duel resumed.", kind: "round" }]);
        setPhase("battle");
      } else if (data.battle) {
        setView(data.battle);
        setLog([{ id: "resume", text: "Battle resumed.", kind: "round" }]);
        setPhase("battle");
      } else {
        setView(null);
        setPhase("setup");
      }
    } catch (loadError) {
      if (loadError instanceof SessionExpired) return;
      console.error(loadError);
      setError("Could not reach the arena.");
      setPhase("error");
    }
  }, [request]);

  useEffect(() => {
    // Carrega da API ao abrir a tela (o estado vem da resposta).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadCurrent();
  }, [loadCurrent]);

  // Reproduz os eventos devolvidos pelo servidor, um por vez.
  useEffect(() => {
    if (!playback) return undefined;

    let cancelled = false;
    let timer = null;
    let index = 0;
    const { events, next, outcome } = playback;
    const names = Object.fromEntries(next.units.map((unit) => [unit.id, unit.name]));
    const unitsById = Object.fromEntries(next.units.map((unit) => [unit.id, unit]));
    // Lado de quem está agindo: efeito no próprio time soa como buff.
    let actorSide = null;

    function playSound(event) {
      const sfx = audio.current;
      if (!sfx) return;
      switch (event.type) {
        case "round":
          if (event.round > 1) sfx.round();
          break;
        case "skill":
          actorSide = unitsById[event.actor]?.side ?? null;
          sfx.cast(unitsById[event.actor]?.element, ["strike", "guard"].includes(event.skill));
          break;
        case "damage":
          if (event.amount > 0) {
            sfx.hit({
              kind: event.kind,
              critical: event.critical,
              effectiveness: event.effectiveness,
              burn: event.status === "burn",
            });
          } else {
            sfx.block();
          }
          break;
        case "heal":
          if (event.amount > 0) sfx.heal();
          break;
        case "status":
          sfx.status(unitsById[event.target]?.side === actorSide);
          break;
        case "stunned":
          sfx.stunned();
          break;
        case "defeated":
          sfx.defeated();
          break;
        case "revive":
          sfx.revive();
          break;
        case "aether":
          sfx.siphon();
          break;
        case "turn":
          actorSide = null;
          break;
        default:
          break;
      }
    }

    function addFloat(unitId, text, kind) {
      const id = ++floatId.current;
      setFloats((current) => [...current, { id, unitId, text, kind }]);
      setTimeout(() => {
        setFloats((current) => current.filter((float) => float.id !== id));
      }, FLOAT_MS);
    }

    function apply(event) {
      const entry = describeEvent(event, names);
      if (entry) {
        const id = ++floatId.current;
        setLog((current) => [...current, { id, ...entry }].slice(-LOG_LIMIT));
      }

      if (event.aether) setAetherOverride(event.aether);
      playSound(event);

      switch (event.type) {
        case "turn":
          setActingId(event.actor);
          break;
        case "skill":
          setActingId(event.actor);
          addFloat(event.actor, event.skillName, "skill");
          break;
        case "damage":
          setHpOverride((current) => ({
            ...current,
            [event.target]: { hp: event.hp, alive: event.hp > 0 },
          }));
          addFloat(
            event.target,
            event.amount > 0
              ? `-${event.amount}${event.critical ? "!" : ""}`
              : `🛡 ${event.absorbed}`,
            event.amount > 0 ? "damage" : "shield"
          );
          break;
        case "heal":
          if (event.amount > 0) {
            setHpOverride((current) => ({
              ...current,
              [event.target]: { hp: event.hp, alive: true },
            }));
            addFloat(event.target, `+${event.amount}`, "heal");
          }
          break;
        case "revive":
          setHpOverride((current) => ({
            ...current,
            [event.target]: { hp: event.hp, alive: true },
          }));
          addFloat(event.target, "Revived", "heal");
          break;
        case "defeated":
          setHpOverride((current) => ({ ...current, [event.target]: { hp: 0, alive: false } }));
          break;
        case "stunned":
          addFloat(event.target, "Stunned", "status");
          break;
        case "status":
          addFloat(event.target, STATUS_ICON[event.status] ?? "•", "status");
          break;
        default:
          break;
      }
    }

    function step() {
      if (cancelled) return;
      if (index >= events.length) {
        setView(next);
        setHpOverride({});
        setAetherOverride(null);
        setActingId(null);
        setPlayback(null);
        if (outcome) {
          if (outcome.outcome === "won") audio.current?.victory();
          else audio.current?.defeat();
          setAutoMode(false);
          setResult(outcome);
          if (outcome.progress) callbacks.current.onProgressChange?.(outcome.progress);
          if (outcome.shardsReward > 0) callbacks.current.onBalanceChange?.();
        } else if (
          next.status === "active" &&
          next.turn &&
          (next.yourTurn ?? true) &&
          !autoRef.current
        ) {
          audio.current?.yourTurn();
        }
        return;
      }
      const event = events[index];
      index += 1;
      apply(event);
      timer = setTimeout(step, eventDelay(event));
    }

    // Começa no próximo ciclo: no StrictMode o efeito roda duas vezes.
    timer = setTimeout(step, 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [playback]);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ block: "nearest" });
  }, [log]);

  useEffect(() => {
    if (!result?.leveledUp) return undefined;
    const timer = setTimeout(() => setShowLevelUp(true), LEVEL_UP_DELAY_MS);
    return () => clearTimeout(timer);
  }, [result]);

  const closeLevelUp = useCallback(() => setShowLevelUp(false), []);
  const playLevelUpSound = useCallback((name, ...args) => audio.current?.[name]?.(...args), []);

  async function startBattle(team, difficulty) {
    setStarting(true);
    setStartError("");
    setLastTeam(team);
    try {
      const { ok, data } = await request("/battles", {
        method: "POST",
        body: JSON.stringify({ team, difficulty }),
      });
      if (!ok) {
        setStartError(data.message ?? "Could not start the battle.");
        return;
      }
      setResult(null);
      setSelectedSkill(null);
      setInspectedId(null);
      setLog([]);
      audio.current?.start();
      setView(freshView(data.battle));
      setPlayback({ events: data.events ?? [], next: data.battle, outcome: data.result });
      setPhase("battle");
    } catch (startFailure) {
      if (startFailure instanceof SessionExpired) return;
      console.error(startFailure);
      setStartError("Could not start the battle.");
    } finally {
      setStarting(false);
    }
  }

  // Entra no duelo que acabou de começar (aceito por um dos dois jogadores).
  const enterDuel = useCallback(async () => {
    if (enteringDuel.current) return;
    enteringDuel.current = true;
    try {
      const { ok, data } = await request("/pvp/battle?since=0");
      if (!ok || !data.battle) return;
      seqRef.current = data.battle.seq;
      setResult(null);
      setSelectedSkill(null);
      setInspectedId(null);
      setAutoMode(false);
      setLog([]);
      audio.current?.start();
      setView(freshView(data.battle));
      setPlayback({ events: data.events ?? [], next: received(data.battle), outcome: data.result });
      setPhase("battle");
    } catch (enterError) {
      if (enterError instanceof SessionExpired) return;
      console.error(enterError);
      setStartError("Could not enter the duel.");
    } finally {
      enteringDuel.current = false;
    }
  }, [request]);

  // Busca o que mudou no duelo desde o último lote recebido.
  const syncDuel = useCallback(async () => {
    const battleId = battleIdRef.current;
    const { ok, data } = await request(
      `/pvp/battle?since=${seqRef.current}${battleId ? `&battleId=${encodeURIComponent(battleId)}` : ""}`
    );
    if (!ok || !data.battle) return;
    if (data.unchanged) {
      // Nada novo: só atualiza o tempo de turno.
      idlePolls.current += 1;
      setView((current) =>
        current
          ? { ...current, turnSecondsLeft: data.battle.turnSecondsLeft, receivedAt: Date.now() }
          : current
      );
      return;
    }
    const changed = data.battle.seq !== seqRef.current;
    seqRef.current = data.battle.seq;
    idlePolls.current = changed ? 0 : idlePolls.current + 1;
    if (changed) {
      setPlayback({ events: data.events ?? [], next: received(data.battle), outcome: data.result });
    } else {
      setView(received(data.battle));
    }
  }, [request]);

  const sendAction = useCallback(
    async (action) => {
      if (!view || busyRef.current) return;
      const duel = view.mode === "pvp";
      busyRef.current = true;
      setBusy(true);
      setError("");
      setSelectedSkill(null);
      setConfirmForfeit(false);
      try {
        const { ok, status, data } = await request(
          duel ? "/pvp/battle/actions" : "/battles/current/actions",
          {
            method: "POST",
            body: JSON.stringify({
              battleId: view.battleId,
              ...action,
              ...(duel ? { since: seqRef.current } : {}),
            }),
          }
        );
        if (!ok) {
          setAutoMode(false);
          if (status === 409 || status === 404) {
            if (duel) {
              if (data.message) setError(data.message);
              await syncDuel();
            } else {
              await loadCurrent();
            }
            return;
          }
          setError(data.message ?? "That action failed.");
          return;
        }
        if (duel) {
          seqRef.current = data.battle.seq;
          idlePolls.current = 0;
        }
        setPlayback({
          events: data.events ?? [],
          next: duel ? received(data.battle) : data.battle,
          outcome: data.result,
        });
      } catch (actionError) {
        if (actionError instanceof SessionExpired) return;
        console.error(actionError);
        setAutoMode(false);
        setError("Could not reach the arena. Try again.");
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [view, request, loadCurrent, syncDuel]
  );

  const inDuel = phase === "battle" && view?.mode === "pvp";
  const waitingForPlayer =
    phase === "battle" &&
    view?.status === "active" &&
    Boolean(view?.turn) &&
    (view?.yourTurn ?? true) &&
    !playback;

  useEffect(() => {
    function handleVisibility() {
      const visible = document.visibilityState !== "hidden";
      // Ao voltar para a aba, confere o duelo logo.
      if (visible) idlePolls.current = -1;
      setPageVisible(visible);
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  // Duelo: na vez do adversário, busca a jogada dele com intervalo crescente
  // (DUEL_POLL_MS até DUEL_POLL_MAX_MS). Na própria vez não consulta: só uma
  // vez quando o tempo do turno acaba (o servidor joga no automático). Se o
  // adversário desistir nesse meio tempo, a próxima ação devolve 409 e a tela
  // se atualiza. Com a aba escondida, não consulta.
  useEffect(() => {
    if (!inDuel || !pageVisible || view.status !== "active" || playback || busy) {
      return undefined;
    }
    let delay =
      idlePolls.current < 0
        ? 0
        : Math.min(DUEL_POLL_MAX_MS, DUEL_POLL_MS * DUEL_POLL_GROWTH ** idlePolls.current);
    if (view.yourTurn && delay > 0) {
      if (view.turnSecondsLeft == null) return undefined;
      const elapsed = Date.now() - (view.receivedAt ?? Date.now());
      delay = Math.max(DUEL_POLL_MS, view.turnSecondsLeft * 1000 - elapsed + TURN_END_MARGIN_MS);
    }
    const timer = setTimeout(() => {
      syncDuel().catch((pollError) => {
        if (pollError instanceof SessionExpired) return;
        console.error(pollError);
        // Tenta de novo no próximo ciclo (sem repetir na hora).
        idlePolls.current = Math.max(0, idlePolls.current) + 1;
        setView((current) => (current ? { ...current } : current));
      });
    }, delay);
    return () => clearTimeout(timer);
  }, [inDuel, pageVisible, view, playback, busy, syncDuel]);

  // Relógio da tela para o tempo de turno do duelo.
  useEffect(() => {
    if (!inDuel) return undefined;
    const timer = setInterval(() => setClock(Date.now()), 500);
    return () => clearInterval(timer);
  }, [inDuel]);

  // Modo automático: o servidor escolhe a ação a cada turno do jogador.
  useEffect(() => {
    if (!autoMode || !waitingForPlayer || busy) return undefined;
    const timer = setTimeout(() => void sendAction({ type: "auto" }), 250);
    return () => clearTimeout(timer);
  }, [autoMode, waitingForPlayer, busy, sendAction]);

  useEffect(() => {
    if (!selectedSkill) return undefined;
    function handleKeyDown(event) {
      if (event.key === "Escape") setSelectedSkill(null);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedSkill]);

  function chooseSkill(action) {
    if (!action.usable || !waitingForPlayer || busy) return;
    if (selectedSkill?.id === action.id) {
      setSelectedSkill(null);
      return;
    }
    audio.current?.select();
    if (SINGLE_TARGETS.includes(action.target) && action.targets.length > 1) {
      setSelectedSkill(action);
      return;
    }
    void sendAction({ type: "skill", skill: action.id, target: action.targets[0] ?? null });
  }

  function backToSetup() {
    setShowLevelUp(false);
    setResult(null);
    setView(null);
    setLog([]);
    void loadCurrent();
  }

  if (phase === "loading") {
    return (
      <section className="battle-screen" aria-label="Battle">
        <p className="collection-status" role="status">
          Entering the arena...
        </p>
      </section>
    );
  }

  if (phase === "error") {
    return (
      <section className="battle-screen" aria-label="Battle">
        <div className="battle-topbar">
          <button type="button" className="session-button" onClick={onExit}>
            ← Home
          </button>
        </div>
        <div className="collection-status">
          <p className="auth-error">{error}</p>
          <button type="button" className="keep-button" onClick={() => void loadCurrent()}>
            Try again
          </button>
        </div>
      </section>
    );
  }

  if (phase === "setup") {
    return (
      <section className="battle-screen" aria-label="Battle setup">
        <div className="battle-topbar">
          <button type="button" className="session-button" onClick={onExit}>
            ← Home
          </button>
          <h1 className="battle-heading">Arena</h1>
          <SoundButton on={soundOn} onToggle={() => setSoundOn((on) => !on)} />
          <Grimoire apiUrl={apiUrl} chapter="battle" />
        </div>
        <div className="shop-tabs battle-mode-tabs" role="tablist" aria-label="Battle mode">
          {ARENA_TABS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={arena === option.value}
              className={`shop-tab${arena === option.value ? " is-active" : ""}`}
              onClick={() => setArena(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        {arena === "pvp" ? (
          <>
            {startError && (
              <p className="auth-error" role="alert">
                {startError}
              </p>
            )}
            <PvpLobby
              apiUrl={apiUrl}
              session={session}
              request={request}
              initialTeam={lastTeam}
              initialChallenge={duelIntent?.challenge}
              onTeamChosen={setLastTeam}
              onEnterDuel={enterDuel}
              onSessionExpired={onSessionExpired}
            />
          </>
        ) : (
          <TeamSetup
            apiUrl={apiUrl}
            session={session}
            setup={setup}
            initialTeam={lastTeam}
            starting={starting}
            startError={startError}
            onStart={startBattle}
            onSessionExpired={onSessionExpired}
          />
        )}
      </section>
    );
  }

  const aether = aetherOverride ?? view.aether;
  const units = view.units;
  const enemies = units.filter((unit) => unit.side === "enemy");
  const allies = units.filter((unit) => unit.side === "player");
  const duel = view.mode === "pvp";
  const yourTurn = view.yourTurn ?? true;
  const currentUnit =
    !playback && view.turn && yourTurn ? units.find((u) => u.id === view.turn) : null;
  const rivalName = view.opponent?.username ?? "Your rival";
  const turnLeft =
    duel && view.turnSecondsLeft != null && !playback
      ? Math.max(
          0,
          Math.ceil(view.turnSecondsLeft - (clock - (view.receivedAt ?? clock)) / 1000)
        )
      : null;
  let waitingText = view.status === "active" ? "The foes are acting..." : "The battle is over.";
  if (duel && view.status === "active") {
    waitingText = playback ? "..." : `${rivalName} is choosing`;
  }
  const inspectedUnit = units.find((unit) => unit.id === inspectedId) ?? null;
  const targetIds = selectedSkill?.targets ?? [];
  const upcoming = (view.upcoming ?? [])
    .map((id) => units.find((unit) => unit.id === id))
    .filter(Boolean);

  function renderUnit(unit) {
    const override = hpOverride[unit.id];
    const targetable = targetIds.includes(unit.id);
    return (
      <BattleUnit
        key={unit.id}
        unit={unit}
        hp={override?.hp ?? unit.hp}
        alive={override?.alive ?? unit.alive}
        active={currentUnit?.id === unit.id}
        acting={actingId === unit.id}
        targetable={targetable}
        inspected={inspectedId === unit.id}
        floats={floats.filter((float) => float.unitId === unit.id)}
        onClick={() => {
          if (targetable) {
            audio.current?.select();
            void sendAction({ type: "skill", skill: selectedSkill.id, target: unit.id });
          } else {
            setInspectedId((current) => (current === unit.id ? null : unit.id));
          }
        }}
      />
    );
  }

  return (
    <section className="battle-screen is-arena" aria-label="Battle">
      <div className="battle-topbar">
        <button
          type="button"
          className="session-button"
          onClick={onExit}
          title={
            duel
              ? "The duel goes on: when your time runs out, your cards act on their own."
              : "The battle stays open; you can come back to it."
          }
        >
          ← Home
        </button>
        <span className="battle-round">
          {duel ? `Duel vs ${rivalName}` : view.difficultyLabel} · Round {view.round}/
          {view.maxRounds}
        </span>
        <SoundButton on={soundOn} onToggle={() => setSoundOn((on) => !on)} />
        <Grimoire apiUrl={apiUrl} chapter="battle" />
      </div>

      <AetherMeter
        label={duel ? rivalName : "Foes"}
        value={aether.enemy}
        max={view.maxAether}
        side="enemy"
      />
      <div className="battle-row is-enemy">{enemies.map(renderUnit)}</div>

      <div className="battle-center">
        <ol className="battle-log" aria-live="polite" aria-label="Battle log">
          {log.map((entry) => (
            <li key={entry.id} className={`battle-log-entry is-${entry.kind}`}>
              {entry.text}
            </li>
          ))}
          <li ref={logEnd} className="battle-log-end" aria-hidden="true" />
        </ol>
        {upcoming.length > 0 && !playback && (
          <div className="battle-upcoming" aria-label="Next in this round">
            <span>Next:</span>
            {upcoming.slice(0, 5).map((unit) => (
              <img
                key={unit.id}
                src={getCharacterImage(unit.fileName)}
                alt={unit.name}
                title={unit.name}
                className={`battle-upcoming-face is-${unit.side}`}
              />
            ))}
          </div>
        )}
      </div>

      <div className="battle-row is-player">{allies.map(renderUnit)}</div>
      <AetherMeter label="Your Aether" value={aether.player} max={view.maxAether} side="player" />

      <div className="battle-actions">
        {currentUnit ? (
          <>
            <p className="battle-actions-title">
              {selectedSkill
                ? `${selectedSkill.name}: choose a target (${TARGET_LABELS[selectedSkill.target]}) · Esc to cancel`
                : `${currentUnit.name}'s turn`}
              {turnLeft != null && (
                <span className={`battle-turn-timer${turnLeft <= 10 ? " is-low" : ""}`}>
                  {" "}
                  · {turnLeft}s
                </span>
              )}
            </p>
            {duel && view.missedTurns > 0 && (
              <p className="battle-turn-warning" role="status">
                You missed {view.missedTurns} of {view.maxMissedTurns} turns in a row. Miss them
                all and you abandon the duel.
              </p>
            )}
            <div className="battle-skills">
              {view.actions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  className={`battle-skill${selectedSkill?.id === action.id ? " is-selected" : ""}`}
                  disabled={!action.usable || busy || autoMode}
                  title={action.usable ? action.description : `${action.description} (${action.reason})`}
                  onClick={() => chooseSkill(action)}
                >
                  <span className="battle-skill-name">{action.name}</span>
                  <span className="battle-skill-meta">
                    {action.cost > 0 ? `${action.cost} ✦` : "Free"} ·{" "}
                    {TARGET_LABELS[action.target]}
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="battle-actions-title">
            {waitingText}
            {turnLeft != null && (
              <span className={`battle-turn-timer${turnLeft <= 10 ? " is-low" : ""}`}>
                {" "}
                · {turnLeft}s
              </span>
            )}
          </p>
        )}

        <div className="battle-controls">
          <label className="battle-auto">
            <input
              type="checkbox"
              checked={autoMode}
              disabled={view.status !== "active"}
              onChange={(event) => setAutoMode(event.target.checked)}
            />
            Auto battle
          </label>
          {view.status === "active" &&
            (confirmForfeit ? (
              <span className="battle-forfeit-confirm">
                <button
                  type="button"
                  className="collection-sell-button is-confirm"
                  disabled={busy || Boolean(playback)}
                  onClick={() => void sendAction({ type: "forfeit" })}
                >
                  Flee (no XP)
                </button>
                <button
                  type="button"
                  className="collection-sell-button is-cancel"
                  onClick={() => setConfirmForfeit(false)}
                >
                  Stay
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="collection-sell-button is-cancel"
                disabled={busy || Boolean(playback) || (!duel && !view.turn)}
                onClick={() => setConfirmForfeit(true)}
              >
                Flee
              </button>
            ))}
        </div>

        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
      </div>

      {inspectedUnit && (
        <aside className="battle-panel battle-inspect battle-inspect-float" aria-label={`${inspectedUnit.name} details`}>
          <button
            type="button"
            className="auth-close"
            aria-label="Close details"
            onClick={() => setInspectedId(null)}
          >
            ×
          </button>
          <h2 className="battle-panel-title">
            {inspectedUnit.name}{" "}
            <span className="battle-inspect-sub">
              {ELEMENT_STYLE[inspectedUnit.element]?.icon} {inspectedUnit.elementLabel} ·{" "}
              {inspectedUnit.archetypeLabel} · Lv {inspectedUnit.level}
            </span>
          </h2>
          {view.elementRiders?.[inspectedUnit.element] && (
            <p className="battle-inspect-desc">
              Element spell effect: {view.elementRiders[inspectedUnit.element]}
            </p>
          )}
          <StatGrid stats={inspectedUnit.stats} />
          {inspectedUnit.statuses.length > 0 && (
            <ul className="battle-inspect-statuses">
              {inspectedUnit.statuses.map((status) => (
                <li key={status.id}>
                  {STATUS_ICON[status.id]} <strong>{status.label}</strong> ({status.turns}):{" "}
                  {status.description}
                </li>
              ))}
            </ul>
          )}
          <SkillList skills={inspectedUnit.skills} />
        </aside>
      )}

      {result && <BattleResult result={result} onAgain={backToSetup} onExit={onExit} />}

      {result && showLevelUp && (
        <LevelUpCelebration
          result={result}
          unlocked={(setup?.difficulties ?? []).filter(
            (difficulty) =>
              difficulty.minLevel > result.previousLevel && difficulty.minLevel <= result.level
          )}
          onSound={playLevelUpSound}
          onDone={closeLevelUp}
        />
      )}
    </section>
  );
}

export default BattleScreen;
