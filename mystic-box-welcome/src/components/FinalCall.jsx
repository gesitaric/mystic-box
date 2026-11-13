import { GAME_URL } from "../api.js";

export default function FinalCall() {
  return (
    <>
      <section className="final-call reveal">
        <div className="final-sigil" aria-hidden="true" />
        <p className="eyebrow">The Box has chosen you</p>
        <h2 className="section-title gilded">Answer the call</h2>
        <p className="section-lede">
          Free to play in your browser. Create an account, open the Box and meet your first three
          champions.
        </p>
        <a className="button button-large" href={GAME_URL}>
          Play Mystic Box
        </a>
      </section>
      <footer className="footer">
        <p>
          <span className="gilded">Mystic Box</span> · A game of the Shattered Realms
        </p>
        <p>
          <a href={GAME_URL}>Play</a> · <a href="#releases">Patch notes</a> · <a href="#top">Back to top</a>
        </p>
      </footer>
    </>
  );
}
