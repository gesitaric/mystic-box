import { useCallback, useEffect, useRef, useState } from "react";
import { ELEMENT_STYLE } from "./battlePresentation";
import { FX_MS, MAX_FX, fieldPoint, planSkill, unitPoint } from "./fxPlanning";

function angleBetween(from, to) {
  return (Math.atan2(to.y - from.y, to.x - from.x) * 180) / Math.PI;
}

// Efeitos da batalha: `play(event, context)` transforma um evento da API em
// peças de efeito na tela; `banner` mostra uma faixa no centro do campo.
export function useBattleFx(mode) {
  const [effects, setEffects] = useState([]);
  const [shaking, setShaking] = useState(false);
  const [lunge, setLunge] = useState(null);
  const nextId = useRef(0);
  const timers = useRef(new Set());
  const modeRef = useRef(mode);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending) clearTimeout(timer);
      pending.clear();
    };
  }, []);

  const later = useCallback((fn, ms) => {
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      fn();
    }, ms);
    timers.current.add(timer);
  }, []);

  const spawn = useCallback(
    (list) => {
      const fresh = list
        .filter(Boolean)
        .map((fx) => ({ ...fx, id: ++nextId.current, ms: fx.ms ?? FX_MS[fx.type] ?? 600 }));
      if (fresh.length === 0) return;
      // Faixas do centro do campo não se empilham: a nova toma o lugar.
      const slots = new Set(fresh.map((fx) => fx.slot).filter(Boolean));
      setEffects((current) =>
        [...current.filter((fx) => !slots.has(fx.slot)), ...fresh].slice(-MAX_FX)
      );
      const ids = new Set(fresh.map((fx) => fx.id));
      const life = Math.max(...fresh.map((fx) => fx.ms + (fx.delay ?? 0)));
      later(() => setEffects((current) => current.filter((fx) => !ids.has(fx.id))), life + 60);
    },
    [later]
  );

  const shake = useCallback(
    (strong) => {
      if (modeRef.current === "lite") return;
      setShaking(strong ? "strong" : "soft");
      later(() => setShaking(false), strong ? 420 : 300);
    },
    [later]
  );

  const clear = useCallback(() => {
    setEffects([]);
    setShaking(false);
    setLunge(null);
  }, []);

  // Faixa no centro do campo (rodada, vez do jogador, maré).
  const banner = useCallback(
    (fx) => {
      const center = fieldPoint();
      if (!center) return;
      spawn([{ ...fx, x: center.x, y: center.y, slot: "center" }]);
    },
    [spawn]
  );

  const play = useCallback(
    (event, { events, index, unitsById }) => {
      const lite = modeRef.current === "lite";
      const elementOf = (id) => unitsById[id]?.element;
      const colorOf = (id) => ELEMENT_STYLE[elementOf(id)]?.color;
      const at = (id) => unitPoint(id);

      switch (event.type) {
        case "skill": {
          const from = at(event.actor);
          if (!from) return;
          const element = elementOf(event.actor);
          const actor = unitsById[event.actor];
          const list = [
            { type: "cast", x: from.x, y: from.y, element, color: colorOf(event.actor) },
          ];
          const center = fieldPoint();
          if (center) {
            list.push({
              type: "banner",
              slot: "center",
              x: center.x,
              y: center.y,
              variant: actor?.side === "enemy" ? "enemy" : "player",
              icon: ELEMENT_STYLE[element]?.icon ?? "✦",
              text: event.skillName,
              sub: actor?.name,
              color: colorOf(event.actor),
            });
          }
          let lungeTo = null;
          for (const { target, kind } of planSkill(events, index)) {
            const to = at(target);
            if (!to) continue;
            const foe = unitsById[target]?.side !== actor?.side;
            if (kind === "physical") {
              lungeTo = lungeTo ?? to;
              continue;
            }
            if (lite && !foe) continue;
            const dx = to.x - from.x;
            const dy = to.y - from.y;
            list.push({
              type: "projectile",
              x: from.x,
              y: from.y,
              element,
              color: colorOf(event.actor),
              variant: foe ? (kind === "magical" ? "spell" : "hex") : "blessing",
              delay: 180,
              style: {
                "--dx": `${dx}px`,
                "--dy": `${dy}px`,
                "--angle": `${angleBetween(from, to)}deg`,
              },
            });
          }
          if (lungeTo) {
            const dx = lungeTo.x - from.x;
            const dy = lungeTo.y - from.y;
            const length = Math.hypot(dx, dy) || 1;
            const reach = Math.min(28, length * 0.25);
            setLunge({ unitId: event.actor, x: (dx / length) * reach, y: (dy / length) * reach });
            later(() => setLunge(null), 480);
          }
          spawn(list);
          return;
        }
        case "damage": {
          const to = at(event.target);
          if (!to) return;
          if (event.amount <= 0) {
            spawn([{ type: "shield", x: to.x, y: to.y }]);
            return;
          }
          const sourceElement = elementOf(event.source);
          const list = [];
          if (event.status === "burn") {
            list.push({ type: "burst", x: to.x, y: to.y, element: "ember", variant: "small" });
          } else if (event.kind === "magical" || event.chain) {
            list.push({
              type: "burst",
              x: to.x,
              y: to.y,
              element: event.chain ? "volt" : sourceElement,
              color: event.chain ? ELEMENT_STYLE.volt.color : colorOf(event.source),
              variant: event.effectiveness === "weak" ? "small" : event.critical ? "big" : null,
            });
          } else {
            list.push({
              type: "slash",
              x: to.x,
              y: to.y,
              color: colorOf(event.source),
              variant: event.critical ? "big" : event.effectiveness === "weak" ? "small" : null,
            });
          }
          if (event.critical) {
            list.push({ type: "tag", x: to.x, y: to.y, text: "Critical!", variant: "critical" });
            if (!lite) list.push({ type: "flash", x: 0, y: 0 });
            shake(true);
          } else if (event.effectiveness === "strong") {
            list.push({ type: "tag", x: to.x, y: to.y, text: "Super effective!", variant: "strong" });
            shake(false);
          } else if (event.effectiveness === "weak") {
            list.push({ type: "tag", x: to.x, y: to.y, text: "Resisted", variant: "weak" });
          }
          spawn(list);
          return;
        }
        case "heal": {
          if (event.amount <= 0) return;
          const to = at(event.target);
          if (to) spawn([{ type: "heal", x: to.x, y: to.y }]);
          return;
        }
        case "revive": {
          const to = at(event.target);
          if (to) spawn([{ type: "revive", x: to.x, y: to.y }]);
          return;
        }
        case "cleanse": {
          const to = at(event.target);
          if (to) spawn([{ type: "buff", x: to.x, y: to.y, variant: "cleanse" }]);
          return;
        }
        case "status": {
          const to = at(event.target);
          if (!to) return;
          // O servidor diz se é bônus ou penalidade (`kind`).
          if (event.status === "shield" || event.status === "guard") {
            spawn([{ type: "shield", x: to.x, y: to.y, variant: "raise" }]);
          } else {
            spawn([{ type: event.kind === "debuff" ? "debuff" : "buff", x: to.x, y: to.y }]);
          }
          return;
        }
        case "stunned": {
          const to = at(event.target);
          if (to) spawn([{ type: "stun", x: to.x, y: to.y }]);
          return;
        }
        case "defeated": {
          const to = at(event.target);
          if (to) spawn([{ type: "shatter", x: to.x, y: to.y, color: colorOf(event.target) }]);
          shake(false);
          return;
        }
        case "duo":
        case "bond":
        case "bondTorn":
        case "rivalry": {
          const from = at(event.actor);
          const to = at(event.target);
          if (!from || !to) return;
          const variant = { duo: "duo", bond: "bond", bondTorn: "torn", rivalry: "rival" }[event.type];
          spawn([
            {
              type: "link",
              x: from.x,
              y: from.y,
              variant,
              style: {
                "--length": `${Math.hypot(to.x - from.x, to.y - from.y)}px`,
                "--angle": `${angleBetween(from, to)}deg`,
              },
            },
            event.type === "duo" && {
              type: "burst",
              x: to.x,
              y: to.y,
              element: elementOf(event.actor),
              color: colorOf(event.actor),
              variant: "big",
              delay: 260,
            },
          ]);
          return;
        }
        case "round":
          if (event.round > 1) banner({ type: "round", text: `Round ${event.round}` });
          return;
        case "surge":
          banner({ type: "surge", text: "Aether Surge" });
          shake(false);
          return;
        default:
          return;
      }
    },
    [spawn, shake, banner, later]
  );

  return { effects, shaking, lunge, play, banner, clear };
}
