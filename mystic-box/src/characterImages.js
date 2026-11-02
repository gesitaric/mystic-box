const characterImages = import.meta.glob("./assets/characters/*", {
  eager: true,
  import: "default",
});

export function getCharacterImage(fileName) {
  if (!fileName) return null;
  return characterImages[`./assets/characters/${fileName}`] ?? null;
}
