import { useEffect, useRef, useState } from "react";
import { createPortalAudio } from "./portalAudio";
import { PHASE, PortalEngine } from "./portalEngine";
import "../../styles/portal.css";

const SOUND_KEY = "mystic-box:portal-sound";
const KEYBOARD_POINTER = "keyboard";

function readSoundPreference() {
  try {
    return localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

function storeSoundPreference(on) {
  try {
    localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // Sem armazenamento local: vale só nesta visita.
  }
}

const INSTRUCTIONS = {
  [PHASE.IDLE]: "HOLD TO CHANNEL ENERGY",
  [PHASE.CHARGING]: "CHANNELING...",
  [PHASE.READY]: "RELEASE TO OPEN THE PORTAL",
};

// Portal de invocação: segurar sobre o portal carrega, soltar em 100% ativa.
// `onActivated` é chamado quando o portal abre (ponto de integração com a invocação real).
function SummonPortal({ onActivated }) {
  const stageRef = useRef(null);
  const canvasRef = useRef(null);
  const hudRef = useRef(null);
  const percentRef = useRef(null);
  const engineRef = useRef(null);
  const audioRef = useRef(null);
  const pointerRef = useRef(null);
  const onActivatedRef = useRef(onActivated);

  const [phase, setPhase] = useState(PHASE.IDLE);
  const [settled, setSettled] = useState(false);
  const [hovering, setHovering] = useState(false);
  const [soundOn, setSoundOn] = useState(readSoundPreference);
  const [activations, setActivations] = useState(0);

  useEffect(() => {
    onActivatedRef.current = onActivated;
  }, [onActivated]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const audio = createPortalAudio();
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let lastPercent = -1;

    const engine = new PortalEngine(canvas, {
      audio,
      reducedMotion,
      onPhase: (next) => {
        setPhase(next);
        setSettled(false);
        if (next === PHASE.ACTIVATED) {
          setActivations((count) => count + 1);
          onActivatedRef.current?.();
        }
      },
      onSettled: () => setSettled(true),
      // Atualiza o HUD direto no DOM, sem re-renderizar a cada quadro.
      onFrame: (state) => {
        const percent = Math.floor(state.charge * 100 + 1e-6);
        if (percentRef.current && percent !== lastPercent) {
          lastPercent = percent;
          percentRef.current.textContent = String(percent);
        }
        if (hudRef.current) {
          hudRef.current.style.transform = `translate(${state.shakeX * 0.6}px, ${state.shakeY * 0.6}px)`;
          hudRef.current.style.setProperty("--charge", state.shown.toFixed(3));
          hudRef.current.style.setProperty("--portal-x", `${state.cx}px`);
          hudRef.current.style.setProperty("--portal-y", `${state.cy}px`);
          hudRef.current.style.setProperty("--portal-r", `${state.R}px`);
        }
      },
    });

    engineRef.current = engine;
    audioRef.current = audio;
    engine.start();

    const observer = new ResizeObserver(() => engine.resize());
    observer.observe(canvas);

    // Perder o foco no meio do carregamento cancela.
    const handleBlur = () => {
      pointerRef.current = null;
      engine.cancel();
    };
    window.addEventListener("blur", handleBlur);

    return () => {
      observer.disconnect();
      window.removeEventListener("blur", handleBlur);
      engine.destroy();
      audio.destroy();
      engineRef.current = null;
      audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    audioRef.current?.setEnabled(soundOn);
    storeSoundPreference(soundOn);
  }, [soundOn]);

  // Espaço / Enter também canalizam (acessibilidade por teclado).
  useEffect(() => {
    const isChannelKey = (event) => event.code === "Space" || event.code === "Enter";

    function handleKeyDown(event) {
      if (!isChannelKey(event) || event.target?.closest?.("button")) return;
      event.preventDefault();
      if (event.repeat || pointerRef.current !== null) return;
      audioRef.current?.unlock();
      if (engineRef.current?.press()) pointerRef.current = KEYBOARD_POINTER;
    }

    function handleKeyUp(event) {
      if (!isChannelKey(event) || pointerRef.current !== KEYBOARD_POINTER) return;
      pointerRef.current = null;
      engineRef.current?.release();
    }

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  function localPoint(event) {
    const rect = stageRef.current.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  }

  function handlePointerDown(event) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    // Só uma interação de carregamento por vez.
    if (pointerRef.current !== null) return;
    const engine = engineRef.current;
    if (!engine || !engine.hitTest(...localPoint(event))) return;

    event.preventDefault();
    audioRef.current?.unlock();
    if (engine.press()) {
      pointerRef.current = event.pointerId;
      event.currentTarget.setPointerCapture?.(event.pointerId);
    }
  }

  function handlePointerUp(event) {
    if (pointerRef.current !== event.pointerId) return;
    pointerRef.current = null;
    engineRef.current?.release();
  }

  function handlePointerCancel(event) {
    if (pointerRef.current !== event.pointerId) return;
    pointerRef.current = null;
    engineRef.current?.cancel();
  }

  function handlePointerMove(event) {
    const engine = engineRef.current;
    if (!engine) return;
    const inside = engine.hitTest(...localPoint(event));
    if (inside !== hovering) setHovering(inside);
  }

  const channeling = phase === PHASE.CHARGING || phase === PHASE.READY;
  const activated = phase === PHASE.ACTIVATED;
  let instruction = INSTRUCTIONS[phase] ?? "";
  if (activated) instruction = settled ? "CLICK THE PORTAL TO SEAL IT" : "";

  return (
    <div
      ref={stageRef}
      className={[
        "portal-stage",
        `portal-${phase.toLowerCase()}`,
        hovering && (phase === PHASE.IDLE || (activated && settled) || channeling) && "portal-hover",
      ]
        .filter(Boolean)
        .join(" ")}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onLostPointerCapture={handlePointerCancel}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => setHovering(false)}
      onContextMenu={(event) => event.preventDefault()}
      role="application"
      aria-label="Summoning portal. Press and hold on the portal, or hold Space, to channel energy. Release at 100% to open it."
    >
      <canvas ref={canvasRef} className="portal-canvas" aria-hidden="true" />

      <div ref={hudRef} className="portal-hud">
        <div className={channeling ? "portal-percent visible" : "portal-percent"} aria-hidden="true">
          <span ref={percentRef} className="portal-percent-value">0</span>
          <span className="portal-percent-sign">%</span>
        </div>

        {activated && (
          <div key={activations} className="portal-banner" role="status">
            <span className="portal-banner-title">PORTAL ACTIVATED!</span>
            <span className="portal-banner-sub">The summoning circle is open</span>
          </div>
        )}
      </div>

      <p key={instruction} className={`portal-instruction ${phase === PHASE.READY ? "urgent" : ""}`} aria-live="polite">
        {instruction}
      </p>

      <button
        type="button"
        className="portal-sound"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => setSoundOn((on) => !on)}
        aria-pressed={soundOn}
        aria-label={soundOn ? "Mute sound" : "Unmute sound"}
        title={soundOn ? "Mute sound" : "Unmute sound"}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
          {soundOn ? (
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
    </div>
  );
}

export default SummonPortal;
