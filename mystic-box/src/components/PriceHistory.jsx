import { useEffect, useState } from "react";

const SHOWN_SALES = 5;

function formatDay(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

// Últimas vendas de uma carta no mercado. Preços, resumo e janela de dias vêm
// de GET /shop/history; aqui só se mostra.
function PriceHistory({ apiUrl, session, fileName, onSessionExpired }) {
  // Resultado guardado com a carta pedida: ao trocar de carta, o anterior
  // deixa de valer sem precisar limpar o estado.
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!fileName) return undefined;
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(
          `${apiUrl}/shop/history?fileName=${encodeURIComponent(fileName)}`,
          { headers: { Authorization: session.session.getIdToken().getJwtToken() } }
        );
        if (response.status === 401) {
          onSessionExpired?.();
          return;
        }
        if (!response.ok) throw new Error(`Failed to load the history (${response.status}).`);
        const data = await response.json();
        if (!cancelled) setResult({ fileName, history: data });
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setResult({ fileName, failed: true });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, fileName, onSessionExpired]);

  const current = result?.fileName === fileName ? result : null;
  if (current?.failed) return null;
  const history = current?.history ?? null;

  return (
    <section className="price-history" aria-label="Recent sales" aria-busy={!history}>
      <h3 className="price-history-title">Recent sales</h3>
      {!history && <p className="price-history-empty">Loading...</p>}
      {history && !history.summary && (
        <p className="price-history-empty">No sales in the last {history.days} days.</p>
      )}
      {history?.summary && (
        <>
          <dl className="price-history-summary">
            <div>
              <dt>Last</dt>
              <dd>✧ {history.summary.last}</dd>
            </div>
            <div>
              <dt>Average</dt>
              <dd>✧ {history.summary.average}</dd>
            </div>
            <div>
              <dt>Range</dt>
              <dd>
                ✧ {history.summary.min}–{history.summary.max}
              </dd>
            </div>
          </dl>
          <ul className="price-history-sales">
            {history.sales.slice(0, SHOWN_SALES).map((sale, index) => (
              <li key={`${sale.soldAt}-${index}`}>
                <span>{formatDay(sale.soldAt)}</span>
                <span>✧ {sale.price}</span>
              </li>
            ))}
          </ul>
          <p className="price-history-note">
            {history.summary.count} sale{history.summary.count === 1 ? "" : "s"} in the last{" "}
            {history.days} days
          </p>
        </>
      )}
    </section>
  );
}

export default PriceHistory;
