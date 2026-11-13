import { useState } from "react";
import { filterReleases, formatDate, noteCounts } from "../format.js";
import { NOTE_TYPES, releases } from "../releases.js";

const FIRST_PAGE = 3;

export default function Releases() {
  const [type, setType] = useState("all");
  const [expanded, setExpanded] = useState(false);
  const counts = noteCounts(releases);
  const filtered = filterReleases(releases, type);
  const shown = expanded ? filtered : filtered.slice(0, FIRST_PAGE);
  const latest = releases[0];

  return (
    <section className="section" id="releases">
      <header className="section-head reveal">
        <p className="eyebrow">Patch notes</p>
        <h2 className="section-title gilded">What&apos;s new in the realm</h2>
        <p className="section-lede">
          The Box keeps changing. Here is every feature that reached the game, newest first.
        </p>
      </header>

      <a className="release-banner reveal" href={`#v${latest.version}`}>
        <span className="release-banner-badge">Latest · v{latest.version}</span>
        <span className="release-banner-name">{latest.name}</span>
        <span className="release-banner-tagline">{latest.tagline}</span>
        <span className="release-banner-date">{formatDate(latest.date)}</span>
      </a>

      <div className="chips release-filters reveal" role="group" aria-label="Filter patch notes">
        {[["all", "Everything"], ...Object.entries(NOTE_TYPES)].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`chip${type === id ? " is-active" : ""}`}
            data-note={id}
            aria-pressed={type === id}
            onClick={() => setType(id)}
          >
            {label} <span className="chip-count">{counts[id] ?? 0}</span>
          </button>
        ))}
      </div>

      <ol className="releases">
        {shown.map((release) => (
          <li className="release reveal" key={release.version} id={`v${release.version}`}>
            <div className="release-meta">
              <span className="release-version">v{release.version}</span>
              <time dateTime={release.date}>{formatDate(release.date)}</time>
            </div>
            <div className="release-body">
              <h3>
                {release.name}
                {release === latest && <span className="release-new">New</span>}
              </h3>
              <p className="release-tagline">{release.tagline}</p>
              <ul className="release-notes">
                {release.notes.map((note) => (
                  <li key={note.title} data-note={note.type}>
                    <span className="note-type">{NOTE_TYPES[note.type]}</span>
                    <div>
                      <strong>{note.title}</strong>
                      <p>{note.text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ol>

      {filtered.length > FIRST_PAGE && (
        <button type="button" className="button button-ghost center" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show fewer" : `Show ${filtered.length - FIRST_PAGE} older releases`}
        </button>
      )}
    </section>
  );
}
