
import { useState } from "react";
import GachaMachine from "./components/GachaMachine";
import Particles from "./components/Particles";
import SummonButton from "./components/SummonButton";
import "./styles/gacha.css";

function App() {
  const [opening, setOpening] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [particles, setParticles] = useState([]);
  const [card, setCard] = useState(null);
  const [error, setError] = useState("");

  async function fetchCard() {
    const response = await fetch("http://127.0.0.1:3000/box/open", {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Falha ao abrir a caixa: ${response.status}`);
    }

    const data = await response.json();
    const drawnCard = data.cards?.[0];

    if (!drawnCard) {
      throw new Error("Nenhuma carta retornada.");
    }

    return drawnCard;
  }

  async function summon() {
    if (opening || revealed) return;

    setError("");
    setOpening(true);

    setParticles(
      Array.from({ length: 40 }, (_, i) => ({
        id: i,
        x: Math.random() * 500 - 250,
        y: Math.random() * -500 - 50,
        delay: Math.random() * 0.5,
      }))
    );

    try {
      const [drawnCard] = await Promise.all([
        fetchCard(),
        new Promise((resolve) => setTimeout(resolve, 700)),
      ]);

      setCard(drawnCard);

      await new Promise((resolve) => setTimeout(resolve, 2400));

      setOpening(false);
      setRevealed(true);
    } catch (err) {
      console.error(err);
      setOpening(false);
      setError("Não foi possível abrir a caixa. Tente novamente.");
    }
  }

  return (
    <main className={`scene ${opening ? "opening" : ""} ${revealed ? "revealed" : ""}`}>
      <div className="aurora" />
      <div className="stars" />
      <div className="motes" />
      <div className="vignette" />
      <div className="frame" />
      <div className="glow" />

      <header className="title-block">
        <span className="title-ornament">✦ ✧ ✦</span>
        <h1>MYSTIC BOX</h1>
        <p className="tagline">ARCANE SUMMONING</p>
      </header>

      <GachaMachine card={card} />

      <Particles particles={particles} />

      <div className="subtitle">
        A MYSTERIOUS GIFT AWAITS...
      </div>

      {error && (
        <div className="error" role="alert">
          <span className="error-icon">✦</span>
          <span>{error}</span>
        </div>
      )}

      <SummonButton
        onClick={summon}
        disabled={opening || revealed}
      />
    </main>
  );
}

export default App;
