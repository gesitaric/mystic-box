import "./styles/relics.css";

// Ilustrações das relíquias, geradas por `npm run images` a partir de
// original-images/relics (fora do Git). O nome do arquivo é o id da relíquia
// que a API devolve; sem imagem, mostra o símbolo ◈.
const modules = import.meta.glob("./assets/relics/*.webp", {
  eager: true,
  import: "default",
});

const relicImages = Object.fromEntries(
  Object.entries(modules).map(([filePath, url]) => [
    filePath.split("/").pop().replace(/\.[^.]+$/, ""),
    url,
  ]),
);

function getRelicImage(relicId) {
  return relicId ? (relicImages[relicId] ?? null) : null;
}

// `size` em px. Decorativa (o nome da relíquia sempre aparece ao lado ou no title).
export function RelicIcon({ relicId, size = 32, className = "" }) {
  const src = getRelicImage(relicId);
  if (!src) {
    return (
      <span className={`relic-icon is-fallback ${className}`} aria-hidden="true">
        ◈
      </span>
    );
  }
  return (
    <img
      className={`relic-icon ${className}`}
      src={src}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      decoding="async"
    />
  );
}
