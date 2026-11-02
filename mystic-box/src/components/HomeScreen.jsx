// Tela inicial do usuário logado. Só apresenta o que veio da API (saldo,
// tempo de espera) e leva para as outras telas.
function HomeScreen({
  email,
  balance,
  cooldownLabel,
  onSummon,
  onCollection,
  onShop,
  onSignOut,
}) {
  return (
    <section className="home" aria-label="Home">
      <div className="home-profile">
        {email && (
          <span className="home-email" title={email}>
            {email}
          </span>
        )}

        <div
          className="home-wallet"
          aria-label={`${balance ?? 0} Arcane Shards`}
        >
          <span className="home-wallet-label">Arcane Shards</span>
          <span className="home-wallet-amount">
            <span className="wallet-icon" aria-hidden="true">✧</span>
            {balance ?? "—"}
          </span>
        </div>
      </div>

      <nav className="home-menu" aria-label="Main menu">
        <button type="button" className="home-button home-button-primary" onClick={onSummon}>
          <span className="home-button-title">✦ Summon cards ✦</span>
          {cooldownLabel && (
            <span className="home-button-hint">
              Next summon in{" "}
              <span className="cooldown-time">{cooldownLabel}</span>
            </span>
          )}
        </button>

        <button type="button" className="home-button" onClick={onCollection}>
          <span className="home-button-title">Collection</span>
        </button>

        <button type="button" className="home-button" onClick={onShop}>
          <span className="home-button-title">Shop</span>
        </button>

        <button type="button" className="home-button home-button-quiet" onClick={onSignOut}>
          <span className="home-button-title">Sign out</span>
        </button>
      </nav>
    </section>
  );
}

export default HomeScreen;
