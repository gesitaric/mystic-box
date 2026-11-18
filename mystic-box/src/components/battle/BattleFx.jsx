import { getCharacterImage } from "../../characterImages";

// Partículas de cada efeito: o ângulo sai do índice no CSS (--i), sem sorteio.
const PARTICLES = { full: 8, lite: 0 };

function Particles({ count, className = "fx-p" }) {
  return Array.from({ length: count }, (_, index) => (
    <i key={index} className={className} style={{ "--i": index, "--n": count }} />
  ));
}

// Uma peça de efeito. Tudo anima só com transform e opacity (leve para a GPU).
function Effect({ fx, lite }) {
  const style = {
    left: `${fx.x}px`,
    top: `${fx.y}px`,
    "--fx-ms": `${fx.ms}ms`,
    "--fx-delay": `${fx.delay ?? 0}ms`,
    ...(fx.color ? { "--fx-color": fx.color } : {}),
    ...(fx.style ?? {}),
  };
  const className = ["fx", `fx-${fx.type}`, fx.element && `fx-el-${fx.element}`, fx.variant && `is-${fx.variant}`]
    .filter(Boolean)
    .join(" ");
  const particles = lite ? 0 : PARTICLES.full;

  switch (fx.type) {
    case "cast":
      return (
        <div className={className} style={style}>
          <i className="fx-cast-glow" />
          <i className="fx-cast-ring" />
          {!lite && <i className="fx-cast-ring is-inner" />}
          {!lite && <Particles count={6} className="fx-cast-rune" />}
        </div>
      );
    case "banner":
      return (
        <div className={className} style={style}>
          <span className="fx-banner-icon">{fx.icon}</span>
          <span className="fx-banner-text">
            <strong>{fx.text}</strong>
            {fx.sub && <small>{fx.sub}</small>}
          </span>
        </div>
      );
    case "projectile":
      return (
        <div className={className} style={style}>
          <i className="fx-projectile-trail" />
          <i className="fx-projectile-core" />
        </div>
      );
    case "link":
      return (
        <div className={className} style={style}>
          <i className="fx-link-beam" />
        </div>
      );
    case "slash":
      return (
        <div className={className} style={style}>
          <i className="fx-slash-line" />
          <i className="fx-slash-line is-cross" />
          {!lite && <Particles count={5} className="fx-spark" />}
        </div>
      );
    case "burst":
      return (
        <div className={className} style={style}>
          <i className="fx-burst-core" />
          <i className="fx-burst-ring" />
          <Particles count={particles} />
        </div>
      );
    case "heal":
    case "revive":
      return (
        <div className={className} style={style}>
          <i className="fx-pillar" />
          <Particles count={lite ? 0 : 6} className="fx-mote" />
        </div>
      );
    case "shield":
      return (
        <div className={className} style={style}>
          <i className="fx-shield-dome" />
        </div>
      );
    case "buff":
    case "debuff":
      return (
        <div className={className} style={style}>
          <i className="fx-aura-ring" />
          <Particles count={lite ? 0 : 4} className="fx-arrow" />
        </div>
      );
    case "stun":
      return (
        <div className={className} style={style}>
          <span className="fx-stun-orbit">
            <i>★</i>
            <i>★</i>
            <i>★</i>
          </span>
        </div>
      );
    case "shatter":
      return (
        <div className={className} style={style}>
          <i className="fx-burst-core" />
          <Particles count={lite ? 0 : 10} className="fx-shard" />
        </div>
      );
    case "tag":
      return (
        <div className={className} style={style}>
          {fx.text}
        </div>
      );
    case "round":
      return (
        <div className={className} style={style}>
          <span>{fx.text}</span>
        </div>
      );
    case "surge":
      return (
        <div className={className} style={style}>
          <i className="fx-surge-wave" />
          <span>{fx.text}</span>
        </div>
      );
    case "turn":
      return (
        <div className={className} style={style}>
          <img src={getCharacterImage(fx.fileName)} alt="" />
          <span className="fx-turn-text">
            <small>{fx.sub}</small>
            <strong>{fx.text}</strong>
          </span>
        </div>
      );
    case "flash":
      return <div className={className} style={style} />;
    default:
      return null;
  }
}

export function BattleFxLayer({ effects, mode }) {
  if (effects.length === 0) return null;
  const lite = mode === "lite";
  return (
    <div className={`fx-layer${lite ? " is-lite" : ""}`} aria-hidden="true">
      {effects.map((fx) => (
        <Effect key={fx.id} fx={fx} lite={lite} />
      ))}
    </div>
  );
}
