// Leitura da resposta de GET /world para a apresentação (sem regras de jogo).

/** Todos os personagens de todas as regiões, com a região de cada um. */
export function allChampions(world) {
  if (!world?.regions) return [];
  return world.regions.flatMap((region) =>
    region.characters.map((character) => ({
      ...character,
      regionId: region.id,
      regionName: region.name,
      element: region.element,
    })),
  );
}

/** Hash simples e estável de um texto (para variar a ordem de exibição). */
export function hash(text) {
  let value = 0;
  for (const char of text) value = (value * 31 + char.charCodeAt(0)) >>> 0;
  return value;
}
