
import { useState } from "react";
import GachaMachine from "./components/GachaMachine";
import Particles from "./components/Particles";
import SummonButton from "./components/SummonButton";
import "./styles/gacha.css";

function App() {
  const [opening, setOpening] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [particles, setParticles] = useState([]);

  function summon() {
    if (opening || revealed) return;

    setOpening(true);

    setParticles(
      Array.from({ length: 40 }, (_, i) => ({
        id: i,
        x: Math.random() * 500 - 250,
        y: Math.random() * -500 - 50,
        delay: Math.random() * 0.5,
      }))
    );

    setTimeout(() => {
      setOpening(false);
      setRevealed(true);
    }, 2500);
  }

  return (
    <main className={`scene ${opening ? "opening" : ""} ${revealed ? "revealed" : ""}`}>
      <div className="stars" />
      <div className="glow" />

      <h1>MYSTIC BOX</h1>

      <GachaMachine />

      <Particles particles={particles} />

      <div className="subtitle">
        A MYSTERIOUS GIFT AWAITS...
      </div>

      <SummonButton
        onClick={summon}
        disabled={opening || revealed}
      />
    </main>
  );
}

export default App;
