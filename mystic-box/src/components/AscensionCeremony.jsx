import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterImage } from "../characterImages";
import { CardFace } from "./GachaCard";
import RevealFx from "./reveal/RevealFx";
import { createRevealAudio } from "./reveal/revealAudio";
import "../styles/ascension.css";

// Cerimônia depois de uma ascensão. Só apresentação: nível, bônus, atributos
// e habilidades vêm da resposta de POST /users/me/cards/ascend (`result`) e da
// carta como estava antes (`card`).
//
// Fases: 0 = cópias voando para a carta e energia se juntando, 1 = explosão,
// 2 = marcas de ascensão surgindo, 3 = resumo do que a carta ganhou.

const CHARGE_MS = 1900;
const MARKS_START_MS = 650;
const MARK_GAP_MS = 480;
const MAX_GHOSTS = 6;

const STAT_ROWS = [
  ["vitality", "Vitality"],
  ["might", "Might"],
  ["arcana", "Arcana"],
  ["bulwark", "Bulwark"],
  ["resolve", "Resolve"],
];

const ROMAN = ["", "I", "II", "III", "IV", "V"];

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function AscensionCeremony({ card, result, onClose }) {
  const level = result.ascension.level;
  const rarity = Number(card.rarity) || 0;
  const image = getCharacterImage(card.file_name);
  const [reduced] = useState(prefersReducedMotion);
  const [phase, setPhase] = useState(reduced ? 3 : 0);
  const [marks, setMarks] = useState(reduced ? level : 0);
  const cardRef = useRef(null);
  const fxRef = useRef(null);
  const audioRef = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const beforeSkills = new Set((card.battle?.skills ?? []).map((skill) => skill.id));
  const newSkills = (result.battle?.skills ?? []).filter((skill) => !beforeSkills.has(skill.id));
  const beforeStats = card.battle?.stats ?? {};
  const afterStats = result.battle?.stats ?? {};
  const previousBonus = card.ascension?.statBonusPercent ?? 0;
  const ghosts = Math.min(MAX_GHOSTS, result.consumed ?? 1);

  // Linha do tempo da cerimônia.
  useEffect(() => {
    if (reduced) return undefined;
    const audio = createRevealAudio();
    audioRef.current = audio;
    const timers = [];
    const at = (ms, fn) => timers.push(setTimeout(fn, ms));
    const rect = () => cardRef.current?.getBoundingClientRect();

    at(150, () => {
      const r = rect();
      if (r) fxRef.current?.gather(r);
      audio.suspense(CHARGE_MS / 1000 - 0.1);
    });
    at(CHARGE_MS, () => {
      fxRef.current?.gather(null);
      const r = rect();
      if (r) fxRef.current?.reveal(r, 5);
      audio.reveal(5);
      setPhase(1);
    });
    for (let i = 1; i <= level; i += 1) {
      at(CHARGE_MS + MARKS_START_MS + (i - 1) * MARK_GAP_MS, () => {
        setPhase(2);
        setMarks(i);
        audio.flip(false);
        audio.hover();
        if (i === level) {
          const r = rect();
          if (r) fxRef.current?.reveal(r, 4);
        }
      });
    }
    at(CHARGE_MS + MARKS_START_MS + level * MARK_GAP_MS + 250, () => setPhase(3));

    return () => {
      // As partículas somem junto com o RevealFx, que é desmontado com a cerimônia.
      timers.forEach(clearTimeout);
      audio.destroy();
      audioRef.current = null;
    };
  }, [reduced, level]);

  // Esc fecha no fim; antes, pula para o resumo.
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, []);

  function skipOrClose() {
    if (phase < 3) {
      setPhase(3);
      setMarks(level);
      return;
    }
    onClose();
  }

  return createPortal(
    <div
      className={`ascension-ceremony is-phase-${phase}`}
      data-rarity={rarity}
      role="dialog"
      aria-modal="true"
      aria-label={`${card.name} ascended`}
      onClick={skipOrClose}
    >
      <div className="ascension-rays" aria-hidden="true" />
      <div className="ascension-flash" aria-hidden="true" />

      <div className="ascension-stage">
        <div className="ascension-card-wrap">
          {!reduced &&
            Array.from({ length: ghosts }, (_, i) => {
              const angle = (360 / ghosts) * i - 90;
              return (
                <div
                  key={i}
                  className="ascension-ghost"
                  style={{ "--angle": `${angle}deg`, "--delay": `${i * 0.12}s` }}
                  aria-hidden="true"
                >
                  <img src={image} alt="" />
                </div>
              );
            })}
          <div className="ascension-aura" aria-hidden="true" />
          <div ref={cardRef} className="ascension-card">
            <CardFace card={card} image={image} rarity={rarity} />
          </div>
        </div>

        <div className="ascension-marks" aria-label={`Ascension ${level}`}>
          {Array.from({ length: result.ascension.max }, (_, i) => (
            <span
              key={i}
              className={`ascension-mark${i < marks ? " is-lit" : ""}${i === marks - 1 ? " is-new" : ""}`}
              aria-hidden="true"
            >
              ✴
            </span>
          ))}
        </div>

        <div className="ascension-summary" aria-live="polite">
          <p className="ascension-kicker">{card.name}</p>
          <h2 className="ascension-title">Ascension {ROMAN[level] ?? level}</h2>
          <p className="ascension-bonus">
            Stats +{previousBonus}% → <b>+{result.ascension.statBonusPercent}%</b>
          </p>

          <dl className="ascension-stats">
            {STAT_ROWS.filter(([key]) => afterStats[key] > (beforeStats[key] ?? 0)).map(
              ([key, label], index) => (
                <div key={key} style={{ "--i": index }}>
                  <dt>{label}</dt>
                  <dd>
                    {beforeStats[key] ?? "—"} <span aria-hidden="true">→</span>{" "}
                    <b>{afterStats[key]}</b>
                  </dd>
                </div>
              )
            )}
          </dl>

          {newSkills.map((skill) => (
            <div key={skill.id} className="ascension-skill">
              <span className="ascension-skill-tag">New skill</span>
              <b>{skill.name}</b>
              <span>{skill.description}</span>
            </div>
          ))}

          <button
            type="button"
            className="ascension-continue"
            onClick={(event) => {
              event.stopPropagation();
              onClose();
            }}
          >
            Continue
          </button>
        </div>
      </div>

      <RevealFx ref={fxRef} />
      {phase < 3 && <p className="ascension-skip">Tap to skip</p>}
    </div>,
    document.body
  );
}

export default AscensionCeremony;
