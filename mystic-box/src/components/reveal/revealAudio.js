// Sons da revelação das cartas (Web Audio, sem arquivos). Só apresentação:
// a raridade vem da API e aqui só escolhe o som.

import { makeImpulse, makeNoiseBuffer, playNoise, playTone } from "../../audio/sfxKit";
import { readSoundPreference } from "../../audio/soundPreference";

// Pentatônica maior em Dó, subindo.
const SCALE = [523.25, 587.33, 659.25, 783.99, 880, 1046.5, 1174.66, 1318.51, 1567.98, 1760, 2093];

export function createRevealAudio() {
  let ctx = null;
  let master = null;
  let reverb = null;
  let noise = null;
  let lastHover = 0;

  function ensure() {
    if (!readSoundPreference()) return false;
    if (!ctx) {
      const AudioCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtor) return false;
      ctx = new AudioCtor();
      master = ctx.createGain();
      master.gain.value = 0.55;
      const compressor = ctx.createDynamicsCompressor();
      compressor.threshold.value = -12;
      compressor.ratio.value = 5;
      master.connect(compressor);
      compressor.connect(ctx.destination);
      reverb = ctx.createConvolver();
      reverb.buffer = makeImpulse(ctx, 2.8, 2.4);
      const wet = ctx.createGain();
      wet.gain.value = 0.5;
      reverb.connect(wet);
      wet.connect(master);
      noise = makeNoiseBuffer(ctx, 3);
    }
    if (ctx.state === "suspended") void ctx.resume();
    return true;
  }

  const both = () => [master, reverb];

  // Passar o mouse na próxima carta.
  function hover() {
    if (!ensure()) return;
    const now = ctx.currentTime;
    if (now - lastHover < 0.25) return;
    lastHover = now;
    playTone(ctx, both(), { type: "sine", from: 1760, to: 2350, gain: 0.025, attack: 0.01, duration: 0.25 });
  }

  // Clique: a carta começa a girar.
  function flip(isFinal) {
    if (!ensure()) return;
    playNoise(ctx, noise, both(), {
      duration: isFinal ? 0.9 : 0.35,
      filterType: "bandpass",
      from: 500,
      to: isFinal ? 5200 : 3200,
      gain: 0.22,
      attack: 0.04,
    });
    playNoise(ctx, noise, [master], { duration: 0.04, filterType: "highpass", from: 3000, to: 2000, gain: 0.12 });
  }

  // A face da carta aparece: quanto maior a raridade, mais rico o som.
  function reveal(rarity) {
    if (!ensure()) return;
    const r = Math.min(5, Math.max(1, rarity || 1));
    const start = r - 1;
    const notes = SCALE.slice(start, start + r + 1);

    notes.forEach((freq, i) =>
      playTone(ctx, both(), {
        type: i % 2 ? "sine" : "triangle",
        from: freq,
        gain: 0.075,
        attack: 0.01,
        duration: 0.9 + r * 0.35,
        delay: i * (0.075 - r * 0.006),
      })
    );

    if (r >= 3) {
      // Brilho agudo.
      playTone(ctx, [reverb], { type: "sine", from: 2093, to: 3136, gain: 0.03, attack: 0.15, duration: 1.6, delay: 0.1 });
      playNoise(ctx, noise, [reverb], { duration: 1.2, filterType: "highpass", from: 6000, to: 9000, gain: 0.05 });
    }

    if (r >= 4) {
      // Impacto grave.
      playTone(ctx, [master], { type: "sine", from: 95, to: 34, gain: 0.7, attack: 0.006, duration: 1.4 });
      playNoise(ctx, noise, both(), { duration: 1.4, filterType: "lowpass", from: 5000, to: 150, gain: 0.35 });
    }

    if (r >= 5) {
      // Acorde lendário e cascata de brilhos.
      [261.63, 392, 523.25, 659.25, 783.99, 1046.5].forEach((freq, i) =>
        playTone(ctx, both(), { type: "triangle", from: freq, gain: 0.06, attack: 0.04, duration: 3.6, delay: 0.12 + i * 0.03 })
      );
      for (let i = 0; i < 14; i += 1) {
        playTone(ctx, [reverb, master], {
          type: "sine",
          from: SCALE[5 + Math.floor(Math.random() * 6)] * 2,
          gain: 0.025,
          attack: 0.005,
          duration: 0.6,
          delay: 0.35 + i * 0.07 + Math.random() * 0.04,
        });
      }
    }
  }

  // Suspense da última carta: zumbido subindo + batidas que aceleram.
  function suspense(seconds) {
    if (!ensure()) return;
    const t = ctx.currentTime;
    const end = t + seconds;

    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.Q.value = 8;
    filter.frequency.setValueAtTime(180, t);
    filter.frequency.exponentialRampToValueAtTime(3200, end);
    const amp = ctx.createGain();
    amp.gain.setValueAtTime(0.0001, t);
    amp.gain.exponentialRampToValueAtTime(0.16, end - 0.05);
    amp.gain.exponentialRampToValueAtTime(0.0001, end + 0.25);
    filter.connect(amp);
    amp.connect(master);
    amp.connect(reverb);

    [1, 1.01, 0.5].forEach((ratio) => {
      const osc = ctx.createOscillator();
      osc.type = ratio === 0.5 ? "sine" : "sawtooth";
      osc.frequency.setValueAtTime(70 * ratio, t);
      osc.frequency.exponentialRampToValueAtTime(260 * ratio, end);
      osc.connect(filter);
      osc.start(t);
      osc.stop(end + 0.3);
    });

    playNoise(ctx, noise, both(), {
      duration: seconds,
      filterType: "bandpass",
      from: 300,
      to: 6000,
      gain: 0.12,
      attack: seconds * 0.9,
    });

    // Batidas de coração cada vez mais rápidas.
    let at = 0;
    let gap = 0.5;
    while (at < seconds - 0.1) {
      playTone(ctx, [master], { type: "sine", from: 70, to: 40, gain: 0.5, attack: 0.005, duration: 0.18, delay: at });
      at += gap;
      gap = Math.max(0.14, gap * 0.78);
    }
  }

  function destroy() {
    if (ctx) void ctx.close();
    ctx = null;
  }

  return { hover, flip, reveal, suspense, destroy };
}
