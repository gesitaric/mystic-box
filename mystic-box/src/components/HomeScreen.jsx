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
    <section className="home" aria-label="Início">
      <div className="home-profile">
        {email && (
          <span className="home-email" title={email}>
            {email}
          </span>
        )}

        <div
          className="home-wallet"
          aria-label={`${balance ?? 0} Fragmentos Arcanos`}
        >
          <span className="home-wallet-label">Fragmentos Arcanos</span>
          <span className="home-wallet-amount">
            <span className="wallet-icon" aria-hidden="true">✧</span>
            {balance ?? "—"}
          </span>
        </div>
      </div>

      <nav className="home-menu" aria-label="Menu principal">
        <button type="button" className="home-button home-button-primary" onClick={onSummon}>
          <span className="home-button-title">✦ Invocar cartas ✦</span>
          {cooldownLabel && (
            <span className="home-button-hint">
              Próxima invocação em{" "}
              <span className="cooldown-time">{cooldownLabel}</span>
            </span>
          )}
        </button>

        <button type="button" className="home-button" onClick={onCollection}>
          <span className="home-button-title">Coleção</span>
        </button>

        <button type="button" className="home-button" onClick={onShop}>
          <span className="home-button-title">Loja</span>
        </button>

        <button type="button" className="home-button home-button-quiet" onClick={onSignOut}>
          <span className="home-button-title">Sair</span>
        </button>
      </nav>
    </section>
  );
}

export default HomeScreen;
