// GET /world (público): pedido único compartilhado pela tela inicial e pelo mapa.

let worldRequest = null;

export function loadWorld(apiUrl) {
  if (!worldRequest) {
    worldRequest = fetch(`${apiUrl}/world`)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load the map (${response.status}).`);
        return response.json();
      })
      .catch((error) => {
        worldRequest = null;
        throw error;
      });
  }
  return worldRequest;
}
