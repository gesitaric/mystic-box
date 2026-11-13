import { useEffect, useState } from "react";

// Aba "Relic" do detalhe da carta. Tudo vem de GET /users/me/relics?fileName=
// (efeito na personagem, sintonia, cópias livres, se pode forjar e o custo).
// O frontend só pede para equipar, tirar ou forjar; o servidor decide.

function Changes({ changes }) {
  if (!changes?.length) return null;
  return (
    <ul className="relic-changes">
      {changes.map((change) => (
        <li key={change.stat} className={change.percent >= 0 ? "is-up" : "is-down"}>
          {change.percent >= 0 ? "+" : "−"}
          {Math.abs(change.percent)}% {change.label}
        </li>
      ))}
    </ul>
  );
}

function RelicPanel({ card, apiUrl, session, onSessionExpired, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState(null);
  const fileName = card.file_name;

  async function request(path, options = {}) {
    const token = session.session.getIdToken().getJwtToken();
    const response = await fetch(`${apiUrl}${path}`, {
      ...options,
      headers: { Authorization: token, "Content-Type": "application/json" },
    });
    if (response.status === 401) {
      onSessionExpired();
      return null;
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const failure = new Error(body.message ?? `Request failed (${response.status}).`);
      failure.status = response.status;
      throw failure;
    }
    return body;
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const token = session.session.getIdToken().getJwtToken();
        const query = new URLSearchParams({ fileName });
        const response = await fetch(`${apiUrl}/users/me/relics?${query}`, {
          headers: { Authorization: token },
        });
        if (response.status === 401) {
          onSessionExpired();
          return;
        }
        if (!response.ok) throw new Error(`Failed to load relics (${response.status}).`);
        const body = await response.json();
        if (!cancelled) setData(body);
      } catch (loadError) {
        console.error(loadError);
        if (!cancelled) setError("Could not load your relics.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, session, onSessionExpired, fileName]);

  async function act(kind, relic) {
    setBusy(`${kind}:${relic?.id ?? ""}`);
    setFeedback(null);
    try {
      const body =
        kind === "forge"
          ? await request("/users/me/relics/forge", {
              method: "POST",
              body: JSON.stringify({ relicId: relic.id, fileName }),
            })
          : await request("/users/me/relics/equip", {
              method: "POST",
              body: JSON.stringify({ fileName, relicId: kind === "equip" ? relic.id : null }),
            });
      if (!body) return;
      setData(body);
      const text = {
        forge: `${relic?.name} forged.`,
        equip: `${card.name} now carries ${relic?.name}.`,
        remove: `${card.name} took off the relic.`,
      }[kind];
      setFeedback({ type: "success", text });
      if (kind !== "forge") onChanged?.();
    } catch (actionError) {
      console.error(actionError);
      setFeedback({ type: "error", text: actionError.message ?? "Something went wrong." });
    } finally {
      setBusy("");
    }
  }

  if (error) return <p className="auth-error">{error}</p>;
  if (!data) {
    return (
      <p className="collection-status" role="status">
        Loading...
      </p>
    );
  }

  const relics = data.relics ?? [];
  const current = relics.find((relic) => relic.id === data.equipped) ?? null;
  // Ordem de exibição: a equipada, as em sintonia, as que o jogador tem e o resto.
  const rank = (relic) =>
    (relic.id === data.equipped ? 0 : 4) +
    (relic.forCard?.attuned ? 0 : 2) +
    (relic.owned > 0 ? 0 : 1);
  const ordered = [...relics].sort((a, b) => rank(a) - rank(b));

  return (
    <div className="relic-panel">
      <p className="relic-intro">
        Each champion carries one relic. In the hands of a champion from its own land, a relic is{" "}
        <b>attuned</b>: its bonuses grow and it awakens at the start of battle.
      </p>

      {current ? (
        <section className="relic-current" aria-label="Equipped relic">
          <h3>
            ◈ {current.name}
            {current.forCard?.attuned && <span className="relic-attuned">Attuned</span>}
          </h3>
          <Changes changes={current.forCard?.changes} />
          {current.forCard?.awakening && (
            <p className="relic-awakening">Awakening: {current.forCard.awakening}</p>
          )}
          <button
            type="button"
            className="collection-sell-button is-cancel"
            disabled={Boolean(busy)}
            onClick={() => act("remove", current)}
          >
            {busy === `remove:${current.id}` ? "Taking off..." : "Take off"}
          </button>
        </section>
      ) : (
        <p className="relic-empty">No relic equipped.</p>
      )}

      {feedback && (
        <p className={feedback.type === "error" ? "auth-error" : "auth-info"} role="status">
          {feedback.text}
        </p>
      )}

      <p className="relic-balance">
        ✧ {data.balance} · Forge: ✧ {data.forgeCost} (up to {data.maxCopies} copies)
      </p>

      <ul className="relic-list">
        {ordered.map((relic) => {
          const worn = relic.id === data.equipped;
          const others = relic.equippedOn.filter((wearer) => wearer.fileName !== fileName);
          return (
            <li
              key={relic.id}
              className={`relic-item${worn ? " is-worn" : ""}${relic.owned ? "" : " is-missing"}`}
            >
              <div className="relic-item-head">
                <strong>◈ {relic.name}</strong>
                <span className="relic-region">{relic.regionName}</span>
                {relic.forCard?.attuned && <span className="relic-attuned">Attuned</span>}
              </div>
              <p className="relic-lore">{relic.lore}</p>
              <Changes changes={relic.forCard?.changes} />
              <p className="relic-awakening">
                {relic.forCard?.attuned
                  ? `Awakening: ${relic.awakening}`
                  : `Awakens for a champion of ${relic.regionName}: ${relic.awakening}`}
              </p>
              <p className="relic-count">
                {relic.owned > 0
                  ? `${relic.owned} owned · ${relic.free} free`
                  : relic.unlocked
                    ? "Not forged yet"
                    : `Defeat the champion of ${relic.regionName} in the campaign to claim it.`}
                {others.length > 0 && ` · On ${others.map((wearer) => wearer.name).join(", ")}`}
              </p>
              <div className="relic-actions">
                {!worn && relic.free > 0 && (
                  <button
                    type="button"
                    className="collection-sell-button is-confirm"
                    disabled={Boolean(busy)}
                    onClick={() => act("equip", relic)}
                  >
                    {busy === `equip:${relic.id}` ? "Equipping..." : current ? "Swap" : "Equip"}
                  </button>
                )}
                {relic.unlocked && relic.owned < data.maxCopies && (
                  <button
                    type="button"
                    className="collection-sell-button is-ascend"
                    disabled={Boolean(busy) || !relic.canForge}
                    onClick={() => act("forge", relic)}
                    title={relic.canForge ? undefined : "Not enough Arcane Shards"}
                  >
                    {busy === `forge:${relic.id}` ? "Forging..." : `Forge ✧ ${data.forgeCost}`}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default RelicPanel;
