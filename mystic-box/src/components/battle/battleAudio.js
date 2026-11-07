// Sons da batalha (Web Audio, sem arquivos). Só apresentação: os eventos e
// valores vêm da API; aqui só se escolhe o som de cada um.

import { makeImpulse, makeNoiseBuffer, playNoise, playTone } from "../../audio/sfxKit";
import { readSoundPreference } from "../../audio/soundPreference";

// Notas (Hz) usadas nos acordes e arpejos.
const NOTE = {
  C4: 261.63, E4: 329.63, G4: 392, A4: 440, B4: 493.88,
  C5: 523.25, D5: 587.33, E5: 659.25, G5: 783.99, A5: 880,
  C6: 1046.5, E6: 1318.51, G6: 1567.98,
};

export function createBattleAudio() {
  let ctx = null;
  let master = null;
  let reverb = null;
  let noise = null;
  let enabled = readSoundPreference();

  function ensure() {
    if (!enabled) return false;
    if (!ctx) {
      const AudioCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtor) return false;
      ctx = new AudioCtor();
      master = ctx.createGain();
      master.gain.value = 0.5;
      const compressor = ctx.createDynamicsCompressor();
      compressor.threshold.value = -14;
      compressor.ratio.value = 6;
      master.connect(compressor);
      compressor.connect(ctx.destination);
      reverb = ctx.createConvolver();
      reverb.buffer = makeImpulse(ctx, 1.8, 2.8);
      const wet = ctx.createGain();
      wet.gain.value = 0.35;
      reverb.connect(wet);
      wet.connect(master);
      noise = makeNoiseBuffer(ctx, 3);
    }
    if (ctx.state === "suspended") void ctx.resume();
    return true;
  }

  const dry = () => [master];
  const both = () => [master, reverb];
  const tone = (options, wet = true) => playTone(ctx, wet ? both() : dry(), options);
  const hiss = (options, wet = true) => playNoise(ctx, noise, wet ? both() : dry(), options);

  function setEnabled(on) {
    enabled = on;
    if (!on && ctx) void ctx.suspend();
  }

  // Clique em habilidade ou alvo.
  function select() {
    if (!ensure()) return;
    tone({ type: "triangle", from: 1320, to: 1760, gain: 0.05, attack: 0.005, duration: 0.09 }, false);
  }

  // Abertura da arena: tambor e trompa.
  function start() {
    if (!ensure()) return;
    [0, 0.22, 0.44].forEach((delay, i) => {
      tone({ type: "sine", from: 110, to: 45, gain: 0.5, attack: 0.005, duration: 0.35, delay }, false);
      hiss({ duration: 0.12, filterType: "lowpass", from: 900, to: 200, gain: 0.25, delay }, false);
      if (i === 2) {
        [NOTE.C4, NOTE.G4, NOTE.C5].forEach((freq) =>
          tone({ type: "sawtooth", from: freq, gain: 0.035, attack: 0.08, duration: 1.1, delay: delay + 0.1 })
        );
      }
    });
  }

  // Nova rodada: gongo suave.
  function round() {
    if (!ensure()) return;
    tone({ type: "sine", from: 196, to: 190, gain: 0.12, attack: 0.01, duration: 1.4 });
    tone({ type: "sine", from: 523, to: 515, gain: 0.04, attack: 0.01, duration: 1.0 });
  }

  // É a vez de uma carta do jogador.
  function yourTurn() {
    if (!ensure()) return;
    tone({ type: "sine", from: NOTE.E5, gain: 0.06, attack: 0.01, duration: 0.35 });
    tone({ type: "sine", from: NOTE.A5, gain: 0.06, attack: 0.01, duration: 0.5, delay: 0.1 });
  }

  // Lançamento de habilidade: o timbre segue o elemento de quem usa.
  function cast(element, basic) {
    if (!ensure()) return;
    const gain = basic ? 0.6 : 1;
    switch (element) {
      case "ember":
        hiss({ duration: 0.45, filterType: "bandpass", from: 400, to: 2400, gain: 0.2 * gain, attack: 0.05 });
        tone({ type: "sawtooth", from: 140, to: 320, gain: 0.04 * gain, attack: 0.03, duration: 0.4 });
        break;
      case "tide":
        tone({ type: "sine", from: 900, to: 300, gain: 0.08 * gain, attack: 0.02, duration: 0.45 });
        tone({ type: "sine", from: 600, to: 1100, gain: 0.05 * gain, attack: 0.02, duration: 0.25, delay: 0.12 });
        break;
      case "gale":
        hiss({ duration: 0.5, filterType: "highpass", from: 1200, to: 5000, gain: 0.16 * gain, attack: 0.15 });
        break;
      case "terra":
        tone({ type: "sine", from: 90, to: 50, gain: 0.35 * gain, attack: 0.01, duration: 0.4 }, false);
        hiss({ duration: 0.3, filterType: "lowpass", from: 600, to: 150, gain: 0.2 * gain });
        break;
      case "volt":
        [0, 0.07, 0.14].forEach((delay) =>
          tone({ type: "square", from: 1800, to: 300, gain: 0.035 * gain, attack: 0.002, duration: 0.09, delay })
        );
        hiss({ duration: 0.25, filterType: "highpass", from: 3000, to: 6000, gain: 0.12 * gain });
        break;
      case "lumen":
        [NOTE.C6, NOTE.E6, NOTE.G6].forEach((freq, i) =>
          tone({ type: "sine", from: freq, gain: 0.04 * gain, attack: 0.01, duration: 0.6, delay: i * 0.05 })
        );
        break;
      case "umbra":
        [1, 1.03].forEach((ratio) =>
          tone({ type: "sawtooth", from: 220 * ratio, to: 70 * ratio, gain: 0.04 * gain, attack: 0.05, duration: 0.55 })
        );
        break;
      default:
        hiss({ duration: 0.3, filterType: "bandpass", from: 600, to: 2000, gain: 0.12 * gain });
    }
  }

  // Golpe acertando. `kind`: physical | magical | hybrid; burn = dano da queimadura.
  function hit({ kind, critical, effectiveness, burn }) {
    if (!ensure()) return;
    if (burn) {
      hiss({ duration: 0.3, filterType: "bandpass", from: 3000, to: 900, gain: 0.14 });
      return;
    }
    const weak = effectiveness === "weak";
    if (kind === "magical") {
      tone({ type: "square", from: 1400, to: 200, gain: weak ? 0.03 : 0.06, attack: 0.003, duration: 0.22 });
      hiss({ duration: 0.18, filterType: "highpass", from: 4000, to: 1500, gain: 0.1 });
    } else {
      tone({ type: "sine", from: 160, to: 60, gain: weak ? 0.25 : 0.45, attack: 0.003, duration: 0.2 }, false);
      hiss({ duration: 0.12, filterType: "bandpass", from: 2500, to: 600, gain: 0.3 }, false);
      if (kind === "hybrid") {
        tone({ type: "triangle", from: 900, to: 300, gain: 0.04, attack: 0.003, duration: 0.18 });
      }
    }
    if (effectiveness === "strong") {
      tone({ type: "triangle", from: NOTE.E5, to: NOTE.A5, gain: 0.05, attack: 0.005, duration: 0.2, delay: 0.04 });
    }
    if (critical) {
      hiss({ duration: 0.08, filterType: "highpass", from: 6000, to: 3000, gain: 0.35 }, false);
      tone({ type: "sawtooth", from: 2200, to: 800, gain: 0.05, attack: 0.002, duration: 0.25, delay: 0.02 });
    }
  }

  // O escudo absorveu todo o golpe.
  function block() {
    if (!ensure()) return;
    tone({ type: "triangle", from: 1900, to: 1850, gain: 0.07, attack: 0.002, duration: 0.5 });
    tone({ type: "sine", from: 2850, gain: 0.03, attack: 0.002, duration: 0.35 });
  }

  function heal() {
    if (!ensure()) return;
    [NOTE.C5, NOTE.E5, NOTE.G5, NOTE.C6].forEach((freq, i) =>
      tone({ type: "sine", from: freq, gain: 0.04, attack: 0.02, duration: 0.45, delay: i * 0.06 })
    );
  }

  // Efeito aplicado: subida para aliados (buff), descida para inimigos (debuff).
  function status(buff) {
    if (!ensure()) return;
    if (buff) {
      tone({ type: "triangle", from: NOTE.G5, to: NOTE.C6, gain: 0.035, attack: 0.01, duration: 0.2 });
    } else {
      tone({ type: "triangle", from: NOTE.B4, to: NOTE.E4, gain: 0.04, attack: 0.01, duration: 0.25 });
    }
  }

  function stunned() {
    if (!ensure()) return;
    [0, 0.09, 0.18].forEach((delay, i) =>
      tone({ type: "sine", from: 1500 - i * 200, to: 1300 - i * 200, gain: 0.04, attack: 0.005, duration: 0.12, delay })
    );
  }

  function defeated() {
    if (!ensure()) return;
    tone({ type: "sawtooth", from: 330, to: 55, gain: 0.06, attack: 0.01, duration: 0.8 });
    tone({ type: "sine", from: 80, to: 35, gain: 0.4, attack: 0.01, duration: 0.6, delay: 0.1 }, false);
  }

  function revive() {
    if (!ensure()) return;
    hiss({ duration: 0.8, filterType: "bandpass", from: 400, to: 5000, gain: 0.1, attack: 0.6 });
    [NOTE.C5, NOTE.G5, NOTE.C6, NOTE.E6].forEach((freq, i) =>
      tone({ type: "sine", from: freq, gain: 0.045, attack: 0.02, duration: 0.7, delay: 0.3 + i * 0.08 })
    );
  }

  // Aether roubado.
  function siphon() {
    if (!ensure()) return;
    tone({ type: "sine", from: 300, to: 1500, gain: 0.06, attack: 0.05, duration: 0.4 });
    hiss({ duration: 0.4, filterType: "bandpass", from: 800, to: 3500, gain: 0.08, attack: 0.3 });
  }

  function victory() {
    if (!ensure()) return;
    const melody = [NOTE.C5, NOTE.E5, NOTE.G5, NOTE.C6];
    melody.forEach((freq, i) =>
      tone({ type: "triangle", from: freq, gain: 0.07, attack: 0.01, duration: 0.3, delay: i * 0.13 })
    );
    [NOTE.C5, NOTE.E5, NOTE.G5, NOTE.C6].forEach((freq) =>
      tone({ type: "sawtooth", from: freq, gain: 0.025, attack: 0.05, duration: 1.6, delay: 0.55 })
    );
    tone({ type: "sine", from: 110, to: 50, gain: 0.4, attack: 0.005, duration: 0.5, delay: 0.55 }, false);
  }

  function defeat() {
    if (!ensure()) return;
    [NOTE.A4, NOTE.G4, NOTE.E4, NOTE.C4].forEach((freq, i) =>
      tone({ type: "triangle", from: freq, gain: 0.06, attack: 0.02, duration: 0.55, delay: i * 0.28 })
    );
    tone({ type: "sine", from: 65, to: 40, gain: 0.3, attack: 0.02, duration: 1.4, delay: 1.0 }, false);
  }

  // Subida de nível: subida de energia que explode num acorde grande.
  function levelUpBurst() {
    if (!ensure()) return;
    const rise = 0.7;
    hiss({ duration: rise, filterType: "bandpass", from: 200, to: 7000, gain: 0.16, attack: rise * 0.95 });
    tone({ type: "sawtooth", from: 80, to: 640, gain: 0.05, attack: rise * 0.9, duration: rise });
    tone({ type: "sine", from: 70, to: 30, gain: 0.6, attack: 0.005, duration: 0.9, delay: rise }, false);
    hiss({ duration: 0.5, filterType: "lowpass", from: 3000, to: 200, gain: 0.35, delay: rise }, false);
    [NOTE.C4, NOTE.G4, NOTE.C5, NOTE.E5, NOTE.G5, NOTE.C6].forEach((freq) =>
      tone({ type: "sawtooth", from: freq, gain: 0.03, attack: 0.02, duration: 2.4, delay: rise })
    );
    [NOTE.C6, NOTE.E6, NOTE.G6, NOTE.C6 * 2].forEach((freq, i) =>
      tone({ type: "sine", from: freq, gain: 0.04, attack: 0.005, duration: 0.6, delay: rise + 0.15 + i * 0.07 })
    );
  }

  // Cada nível que o número passa.
  function levelTick(step) {
    if (!ensure()) return;
    const freq = NOTE.G5 * Math.pow(2, (step * 2) / 12);
    tone({ type: "triangle", from: freq, gain: 0.07, attack: 0.005, duration: 0.3 });
    tone({ type: "sine", from: freq * 2, gain: 0.03, attack: 0.005, duration: 0.25 });
  }

  // Fragmentos Arcanos caindo na carteira.
  function shards() {
    if (!ensure()) return;
    for (let i = 0; i < 6; i += 1) {
      const freq = 1800 + (i % 3) * 420;
      tone({ type: "triangle", from: freq, to: freq * 1.02, gain: 0.04, attack: 0.002, duration: 0.18, delay: i * 0.09 });
    }
  }

  // Dificuldade nova liberada.
  function unlock() {
    if (!ensure()) return;
    tone({ type: "square", from: NOTE.C5, gain: 0.03, attack: 0.005, duration: 0.15 });
    tone({ type: "square", from: NOTE.G5, gain: 0.03, attack: 0.005, duration: 0.15, delay: 0.1 });
    tone({ type: "triangle", from: NOTE.C6, gain: 0.06, attack: 0.005, duration: 0.6, delay: 0.2 });
  }

  function destroy() {
    if (ctx) void ctx.close();
    ctx = null;
  }

  return {
    setEnabled, select, start, round, yourTurn, cast, hit, block, heal, status,
    stunned, defeated, revive, siphon, victory, defeat,
    levelUpBurst, levelTick, shards, unlock, destroy,
  };
}
