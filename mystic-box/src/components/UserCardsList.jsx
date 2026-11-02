import Modal from "./Modal";
import OwnedCards from "./OwnedCards";

function UserCardsList({
  apiUrl,
  session,
  onClose,
  onSessionExpired,
  onBalanceChange,
}) {
  return (
    <Modal label="Minha coleção" className="collection-modal" onClose={onClose}>
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>MINHA COLEÇÃO</h2>
      </header>

      <OwnedCards
        apiUrl={apiUrl}
        session={session}
        onSessionExpired={onSessionExpired}
        onBalanceChange={onBalanceChange}
      />
    </Modal>
  );
}

export default UserCardsList;
