// A crônica de Aethra (GET /world -> chronicle), como uma linha do tempo.
export default function Chronicle({ world }) {
  const chronicle = world?.chronicle;
  if (!chronicle?.length) return null;

  return (
    <section className="section" id="chronicle">
      <header className="section-head reveal">
        <p className="eyebrow">The chronicle</p>
        <h2 className="section-title gilded">How the world broke</h2>
      </header>
      <ol className="chronicle">
        {chronicle.map((entry, index) => (
          <li
            key={entry.title}
            className={`chronicle-entry reveal${index === chronicle.length - 1 ? " is-now" : ""}`}
          >
            <span className="chronicle-era">{entry.era}</span>
            <h3>{entry.title}</h3>
            <p>{entry.text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
