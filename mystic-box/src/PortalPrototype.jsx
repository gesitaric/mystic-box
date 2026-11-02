import SummonPortal from "./components/portal/SummonPortal";

// Protótipo isolado da mecânica do portal (abrir em /#portal).
// Ainda não sorteia nem revela cartas.
function PortalPrototype() {
  return (
    <div className="portal-page">
      <p className="portal-brand">MYSTIC BOX</p>
      <SummonPortal />
    </div>
  );
}

export default PortalPrototype;
