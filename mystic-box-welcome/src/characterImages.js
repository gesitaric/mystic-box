// Ilustrações das cartas, lidas da pasta do jogo (sem cópia).
// Só os arquivos que aparecem na tela são baixados (as <img> usam loading="lazy").
const modules = import.meta.glob("../../mystic-box/src/assets/characters/*.webp", {
  eager: true,
  import: "default",
});

const images = Object.fromEntries(
  Object.entries(modules).map(([filePath, url]) => [
    filePath.split("/").pop().replace(/\.[^.]+$/, ""),
    url,
  ]),
);

/** `file_name` da API ("astra.jfif") -> URL da ilustração ("astra.webp"). */
export function getCharacterImage(fileName) {
  if (!fileName) return null;
  return images[fileName.replace(/\.[^.]+$/, "")] ?? null;
}
