import { useEffect, useRef, useState } from "react";
import { LevelBadge } from "../HomeScreen";

// Linha do tempo da celebração (ms desde que abriu).
const BURST_AT = 0;
const TITLE_AT = 700;
const LEVEL_AT = 1300;
const LEVEL_STEP_MS = 320;
const REWARD_DELAY_MS = 500;
const SHARDS_COUNT_MS = 900;

const SPARKS = 36;
const MOTES = 18;

// Faíscas em ângulo áureo: espalhadas por igual, sem sorteio no render.
const sparkStyles = Array.from({ length: SPARKS }, (_, i) => ({
  "--angle": `${(i * 137.5) % 360}deg`,
  "--dist": `${32 + (i % 5) * 9}vmin`,
  "--delay": `${(i % 7) * 0.035}s`,
  "--size": `${4 + (i % 3) * 3}px`,
}));

const moteStyles = Array.from({ length: MOTES }, (_, i) => ({
  "--x": `${(i * 61) % 100}%`,
  "--delay": `${(i % 9) * 0.4}s`,
  "--duration": `${3.2 + (i % 4) * 0.7}s`,
}));

// Comemoração de subida de nível. Nível, experiência, recompensa e
// dificuldades liberadas vêm da API; aqui só se anima.
function LevelUpCelebration({ result, unlocked = [], onSound, onDone }) {
  const previous = result.previousLevel;
  const target = result.level;
  const [stage, setStage] = useState(0); // 0 explosão, 1 título, 2 nível, 3 recompensas
  const [shownLevel, setShownLevel] = useState(previous);
  const [shownShards, setShownShards] = useState(0);
  const [rewardsShown, setRewardsShown] = useState(false);
  const sound = useRef(onSound);
  const continueButton = useRef(null);

  useEffect(() => {
    sound.current = onSound;
  });

  useEffect(() => {
    const timers = [];
    const at = (ms, fn) => timers.push(setTimeout(fn, ms));
    let frame = 0;

    at(BURST_AT, () => sound.current?.("levelUpBurst"));
    at(TITLE_AT, () => setStage(1));

    const levels = target - previous;
    at(LEVEL_AT, () => setStage(2));
    for (let step = 1; step <= levels; step += 1) {
      at(LEVEL_AT + step * LEVEL_STEP_MS, () => {
        setShownLevel(previous + step);
        sound.current?.("levelTick", step);
      });
    }

    const rewardsAt = LEVEL_AT + levels * LEVEL_STEP_MS + REWARD_DELAY_MS;
    at(rewardsAt, () => {
      setStage(3);
      setRewardsShown(true);
      if (result.shardsReward > 0) {
        sound.current?.("shards");
        const startedAt = performance.now();
        const tick = (now) => {
          const progress = Math.min(1, (now - startedAt) / SHARDS_COUNT_MS);
          setShownShards(Math.round(result.shardsReward * (1 - Math.pow(1 - progress, 3))));
          if (progress < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
      }
    });
    if (unlocked.length > 0) {
      at(rewardsAt + SHARDS_COUNT_MS, () => sound.current?.("unlock"));
    }

    return () => {
      timers.forEach(clearTimeout);
      cancelAnimationFrame(frame);
    };
  }, [previous, target, result.shardsReward, unlocked.length]);

  useEffect(() => {
    if (rewardsShown) continueButton.current?.focus();
  }, [rewardsShown]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape" || (rewardsShown && event.key === "Enter")) onDone();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [rewardsShown, onDone]);

  return (
    <div
      className={`levelup stage-${stage}`}
      role="dialog"
      aria-modal="true"
      aria-label={`Level up! You reached level ${target}`}
    >
      <div className="levelup-flash" aria-hidden="true" />
      <div className="levelup-rays" aria-hidden="true" />
      <div className="levelup-ring" aria-hidden="true" />
      <div className="levelup-ring levelup-ring-2" aria-hidden="true" />
      <div className="levelup-ring levelup-ring-3" aria-hidden="true" />
      <div className="levelup-sparks" aria-hidden="true">
        {sparkStyles.map((style, i) => (
          <span key={i} className="levelup-spark" style={style} />
        ))}
      </div>
      <div className="levelup-motes" aria-hidden="true">
        {moteStyles.map((style, i) => (
          <span key={i} className="levelup-mote" style={style}>
            ✦
          </span>
        ))}
      </div>

      <div className="levelup-content">
        <p className="levelup-kicker">Your power grows</p>
        <h2 className="levelup-title">
          <span>LEVEL</span> <span>UP</span>
        </h2>

        <div className="levelup-level" aria-live="polite">
          <span className="levelup-level-label">Level</span>
          <span key={shownLevel} className="levelup-level-number">
            {shownLevel}
          </span>
        </div>

        {rewardsShown && (
          <div className="levelup-rewards">
            <LevelBadge progress={result.progress} />

            {result.shardsReward > 0 && (
              <p className="levelup-reward">
                <span className="wallet-icon" aria-hidden="true">
                  ✧
                </span>{" "}
                +{shownShards} Arcane Shards
              </p>
            )}

            {unlocked.map((difficulty) => (
              <p key={difficulty.id} className="levelup-unlock">
                <span className="levelup-unlock-tag">Unlocked</span> {difficulty.label}{" "}
                challenge
              </p>
            ))}

            <button
              ref={continueButton}
              type="button"
              className="keep-button levelup-continue"
              onClick={onDone}
            >
              Continue
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default LevelUpCelebration;
