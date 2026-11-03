// Preferência de som do jogador (só conveniência local, vale para todos os efeitos).
const SOUND_KEY = "mystic-box:portal-sound";

export function readSoundPreference() {
  try {
    return localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

export function storeSoundPreference(on) {
  try {
    localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // Sem armazenamento local: vale só nesta visita.
  }
}
