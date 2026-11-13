import { usePublicApi } from "./api.js";
import Starfield from "./components/Starfield.jsx";
import Nav from "./components/Nav.jsx";
import Hero from "./components/Hero.jsx";
import Omen from "./components/Omen.jsx";
import Pillars from "./components/Pillars.jsx";
import Champions from "./components/Champions.jsx";
import World from "./components/World.jsx";
import Chronicle from "./components/Chronicle.jsx";
import Odds from "./components/Odds.jsx";
import Elements from "./components/Elements.jsx";
import Releases from "./components/Releases.jsx";
import FinalCall from "./components/FinalCall.jsx";
import { useReveal } from "./components/useReveal.js";

export default function App() {
  const world = usePublicApi("/world");
  const rules = usePublicApi("/rules");
  useReveal();

  const worldData = world.data;
  const rulesData = rules.data;

  return (
    <>
      <Starfield />
      <Nav />
      <main>
        <Hero world={worldData} rules={rulesData} />
        <Omen omen={worldData?.omen} regions={worldData?.regions} status={world.status} />
        <Pillars rules={rulesData} world={worldData} />
        <Champions world={worldData} status={world.status} />
        <World world={worldData} status={world.status} />
        <Chronicle world={worldData} />
        <Odds rules={rulesData} status={rules.status} />
        <Elements rules={rulesData} />
        <Releases />
        <FinalCall />
      </main>
    </>
  );
}
