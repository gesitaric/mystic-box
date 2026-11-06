import Modal from "./Modal";
import OwnedCards from "./OwnedCards";

function UserCardsList({
  apiUrl,
  session,
  onClose,
  onSessionExpired,
}) {
  return (
    <Modal label="My collection" className="collection-modal" onClose={onClose}>
      <header className="auth-header">
        <span className="auth-ornament">✦ ✧ ✦</span>
        <h2>MY COLLECTION</h2>
      </header>

      <OwnedCards
        apiUrl={apiUrl}
        session={session}
        onSessionExpired={onSessionExpired}
      />
    </Modal>
  );
}

export default UserCardsList;
