// Versões otimizadas (WebP) geradas por `npm run images` a partir dos originais
// em original-images/characters (que ficam só localmente, fora do Git).
const modules = import.meta.glob("./assets/characters/*.webp", {
  eager: true,
  import: "default",
});

// Indexa pelo nome sem extensão, para que um file_name como "astra.jfif"
// (salvo no banco) continue encontrando "astra.webp".
const characterImages = Object.fromEntries(
  Object.entries(modules).map(([filePath, url]) => [
    filePath.split("/").pop().replace(/\.[^.]+$/, ""),
    url,
  ]),
);

export function getCharacterImage(fileName) {
  if (!fileName) return null;
  return characterImages[fileName.replace(/\.[^.]+$/, "")] ?? null;
}
