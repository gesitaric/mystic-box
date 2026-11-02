import { useEffect, useState } from "react";
import App from "./App.jsx";
import PortalPrototype from "./PortalPrototype.jsx";

const isPortalRoute = () => window.location.hash === "#portal";

// /#portal abre o protótipo do portal de invocação; o resto é o jogo.
function Root() {
  const [portal, setPortal] = useState(isPortalRoute);

  useEffect(() => {
    const handleHashChange = () => setPortal(isPortalRoute());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return portal ? <PortalPrototype /> : <App />;
}

export default Root;
