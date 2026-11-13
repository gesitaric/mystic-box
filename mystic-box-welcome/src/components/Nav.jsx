import { useEffect, useState } from "react";
import { GAME_URL } from "../api.js";

const LINKS = [
  ["#omen", "Omen"],
  ["#play", "How to play"],
  ["#champions", "Champions"],
  ["#world", "World"],
  ["#odds", "The Box"],
  ["#releases", "Patch notes"],
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`nav${scrolled ? " is-scrolled" : ""}${open ? " is-open" : ""}`}>
      <a className="nav-brand" href="#top" onClick={() => setOpen(false)}>
        <img src="/favicon.svg" alt="" width="28" height="28" />
        <span>Mystic Box</span>
      </a>
      <button
        type="button"
        className="nav-toggle"
        aria-expanded={open}
        aria-controls="nav-links"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="sr-only">Menu</span>
        <span aria-hidden="true" />
      </button>
      <nav id="nav-links" className="nav-links" aria-label="Sections">
        {LINKS.map(([href, label]) => (
          <a key={href} href={href} onClick={() => setOpen(false)}>
            {label}
          </a>
        ))}
        <a className="button button-small" href={GAME_URL}>
          Play now
        </a>
      </nav>
    </header>
  );
}
