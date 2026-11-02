// Sons do portal sintetizados com Web Audio (sem arquivos de áudio).
// Só apresentação: nada aqui decide regra de jogo.

function makeNoiseBuffer(ctx, seconds) {
  const length = Math.floor(ctx.sampleRate * seconds);
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i += 1) data[i] = Math.random() * 2 - 1;
  return buffer;
}

function makeImpulse(ctx, seconds, decay) {
  const length = Math.floor(ctx.sampleRate * seconds);
  const buffer = ctx.createBuffer(2, length, ctx.sampleRate);
  for (let channel = 0; channel < 2; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i += 1) {
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
    }
  }
  return buffer;
}

export function createPortalAudio() {
  let ctx = null;
  let enabled = true;
  let nodes = null;
  let lastCrackle = 0;

  function build() {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return false;

    ctx = new AudioCtor();
    const master = ctx.createGain();
    master.gain.value = enabled ? 0.6 : 0;
    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.value = -14;
    compressor.ratio.value = 6;
    master.connect(compressor);
    compressor.connect(ctx.destination);

    const reverb = ctx.createConvolver();
    reverb.buffer = makeImpulse(ctx, 3.4, 2.6);
    const reverbGain = ctx.createGain();
    reverbGain.gain.value = 0.45;
    reverb.connect(reverbGain);
    reverbGain.connect(master);

    const noiseBuffer = makeNoiseBuffer(ctx, 2);

    // Zumbido do carregamento: dois serrotes desafinados + sub, num passa-baixa.
    const droneFilter = ctx.createBiquadFilter();
    droneFilter.type = "lowpass";
    droneFilter.frequency.value = 200;
    droneFilter.Q.value = 6;
    const droneGain = ctx.createGain();
    droneGain.gain.value = 0;
    droneFilter.connect(droneGain);
    droneGain.connect(master);
    droneGain.connect(reverb);

    const oscA = ctx.createOscillator();
    oscA.type = "sawtooth";
    const oscB = ctx.createOscillator();
    oscB.type = "sawtooth";
    const sub = ctx.createOscillator();
    sub.type = "sine";
    const subGain = ctx.createGain();
    subGain.gain.value = 1.6;
    [oscA, oscB].forEach((osc) => osc.connect(droneFilter));
    sub.connect(subGain);
    subGain.connect(droneFilter);

    // Tremolo que aparece na intensificação.
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 5;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0;
    lfo.connect(lfoGain);
    lfoGain.connect(droneGain.gain);

    // Vento de energia: ruído num passa-banda que sobe com a carga.
    const wind = ctx.createBufferSource();
    wind.buffer = noiseBuffer;
    wind.loop = true;
    const windFilter = ctx.createBiquadFilter();
    windFilter.type = "bandpass";
    windFilter.Q.value = 1.4;
    windFilter.frequency.value = 400;
    const windGain = ctx.createGain();
    windGain.gain.value = 0;
    wind.connect(windFilter);
    windFilter.connect(windGain);
    windGain.connect(master);
    windGain.connect(reverb);

    // Brilho cristalino do portal pronto / ativado.
    const shimmerGain = ctx.createGain();
    shimmerGain.gain.value = 0;
    shimmerGain.connect(reverb);
    shimmerGain.connect(master);
    const shimmerLfo = ctx.createOscillator();
    shimmerLfo.frequency.value = 7;
    const shimmerLfoGain = ctx.createGain();
    shimmerLfoGain.gain.value = 0.4;
    const shimmerAmp = ctx.createGain();
    shimmerAmp.gain.value = 0.6;
    shimmerLfo.connect(shimmerLfoGain);
    shimmerLfoGain.connect(shimmerAmp.gain);
    shimmerAmp.connect(shimmerGain);
    const shimmerOscs = [1046.5, 1318.5, 1568, 2093].map((freq, i) => {
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = freq;
      osc.detune.value = (i - 1.5) * 6;
      osc.connect(shimmerAmp);
      return osc;
    });

    const sources = [oscA, oscB, sub, lfo, wind, shimmerLfo, ...shimmerOscs];
    sources.forEach((source) => source.start());

    nodes = {
      master,
      reverb,
      noiseBuffer,
      droneFilter,
      droneGain,
      oscA,
      oscB,
      sub,
      lfo,
      lfoGain,
      windFilter,
      windGain,
      shimmerGain,
      sources,
    };
    return true;
  }

  function ready() {
    return Boolean(ctx && nodes && ctx.state === "running");
  }

  // Precisa vir de um gesto do usuário (pointerdown/keydown).
  function unlock() {
    if (!ctx && !build()) return;
    if (ctx.state === "suspended") void ctx.resume();
  }

  function setEnabled(value) {
    enabled = value;
    if (!ctx || !nodes) return;
    nodes.master.gain.setTargetAtTime(value ? 0.6 : 0, ctx.currentTime, 0.05);
  }

  // Chamado a cada quadro com a carga (0..1) e a fase do portal.
  function update(charge, phase, activation) {
    if (!ready()) return;
    const t = ctx.currentTime;
    const c = charge;
    const channeling = phase === "CHARGING" || phase === "READY";

    const base = 52 + c * c * 120;
    nodes.oscA.frequency.setTargetAtTime(base, t, 0.06);
    nodes.oscB.frequency.setTargetAtTime(base * 1.012, t, 0.06);
    nodes.sub.frequency.setTargetAtTime(base / 2, t, 0.06);
    nodes.droneFilter.frequency.setTargetAtTime(180 + c * c * 3400, t, 0.08);

    const hum = 0.035 * activation;
    const droneLevel = Math.min(1, c * 5) * (0.06 + 0.2 * c);
    nodes.droneGain.gain.setTargetAtTime(Math.max(droneLevel, hum), t, channeling ? 0.06 : 0.25);

    const intense = Math.max(0, (c - 0.6) / 0.4);
    nodes.lfo.frequency.setTargetAtTime(4 + intense * 12, t, 0.1);
    nodes.lfoGain.gain.setTargetAtTime(intense * 0.07, t, 0.1);

    nodes.windFilter.frequency.setTargetAtTime(300 + c * c * 2600, t, 0.1);
    nodes.windGain.gain.setTargetAtTime(0.16 * c * c + 0.02 * activation, t, 0.12);

    let shimmer = 0.02 * activation;
    if (phase === "READY") shimmer = 0.05;
    else if (channeling) shimmer = Math.max(shimmer, intense * intense * 0.03);
    nodes.shimmerGain.gain.setTargetAtTime(shimmer, t, 0.2);
  }

  function noiseHit({ duration, filterType, from, to, gain, delay = 0, wet = true }) {
    const t = ctx.currentTime + delay;
    const source = ctx.createBufferSource();
    source.buffer = nodes.noiseBuffer;
    const filter = ctx.createBiquadFilter();
    filter.type = filterType;
    filter.frequency.setValueAtTime(from, t);
    filter.frequency.exponentialRampToValueAtTime(to, t + duration);
    const amp = ctx.createGain();
    amp.gain.setValueAtTime(gain, t);
    amp.gain.exponentialRampToValueAtTime(0.0001, t + duration);
    source.connect(filter);
    filter.connect(amp);
    amp.connect(nodes.master);
    if (wet) amp.connect(nodes.reverb);
    source.start(t, Math.random() * 1.5);
    source.stop(t + duration + 0.05);
  }

  function tone({ type, from, to, gain, attack, duration, delay = 0, dry = true }) {
    const t = ctx.currentTime + delay;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(from, t);
    if (to && to !== from) osc.frequency.exponentialRampToValueAtTime(to, t + duration);
    const amp = ctx.createGain();
    amp.gain.setValueAtTime(0.0001, t);
    amp.gain.exponentialRampToValueAtTime(gain, t + attack);
    amp.gain.exponentialRampToValueAtTime(0.0001, t + duration);
    osc.connect(amp);
    if (dry) amp.connect(nodes.master);
    amp.connect(nodes.reverb);
    osc.start(t);
    osc.stop(t + duration + 0.05);
  }

  // Estalo curto de raio.
  function crackle(intensity) {
    if (!ready()) return;
    const now = ctx.currentTime;
    if (now - lastCrackle < 0.045) return;
    lastCrackle = now;
    noiseHit({
      duration: 0.05 + Math.random() * 0.08,
      filterType: "highpass",
      from: 2400 + Math.random() * 3000,
      to: 900,
      gain: 0.06 + intensity * 0.14,
    });
  }

  // Carga chegou a 100%.
  function charged() {
    if (!ready()) return;
    tone({ type: "sine", from: 420, to: 1260, gain: 0.12, attack: 0.05, duration: 0.6 });
    [784, 1174.7, 1568].forEach((freq, i) =>
      tone({ type: "triangle", from: freq, gain: 0.05, attack: 0.02, duration: 1.6, delay: 0.08 + i * 0.05 })
    );
  }

  function explode() {
    if (!ready()) return;
    // Impacto grave.
    tone({ type: "sine", from: 110, to: 26, gain: 0.95, attack: 0.008, duration: 2.2 });
    tone({ type: "triangle", from: 220, to: 40, gain: 0.3, attack: 0.005, duration: 0.9 });
    // Estouro de ruído que vai escurecendo.
    noiseHit({ duration: 2.4, filterType: "lowpass", from: 9000, to: 120, gain: 0.8 });
    noiseHit({ duration: 0.35, filterType: "highpass", from: 6000, to: 2000, gain: 0.35, wet: false });
    // Acorde mágico.
    [523.25, 659.25, 783.99, 1046.5, 1318.5, 1568, 2093].forEach((freq, i) =>
      tone({
        type: i % 2 ? "sine" : "triangle",
        from: freq,
        gain: 0.07,
        attack: 0.02,
        duration: 3.8,
        delay: 0.05 + i * 0.045,
      })
    );
    // Brilho subindo depois do impacto.
    tone({ type: "sine", from: 600, to: 2400, gain: 0.04, attack: 0.4, duration: 2.5, delay: 0.25, dry: false });
  }

  // Uma carta saindo do portal.
  function emerge() {
    if (!ready()) return;
    tone({ type: "sine", from: 260, to: 980, gain: 0.12, attack: 0.02, duration: 0.5 });
    tone({ type: "triangle", from: 1318.5, gain: 0.06, attack: 0.01, duration: 1.4, delay: 0.12 });
    noiseHit({ duration: 0.45, filterType: "bandpass", from: 900, to: 4200, gain: 0.14 });
  }

  // Fechar o portal ativado.
  function seal() {
    if (!ready()) return;
    tone({ type: "sine", from: 880, to: 180, gain: 0.08, attack: 0.05, duration: 1.4 });
    noiseHit({ duration: 1.2, filterType: "bandpass", from: 2400, to: 200, gain: 0.12 });
  }

  function destroy() {
    if (!ctx) return;
    void ctx.close();
    ctx = null;
    nodes = null;
  }

  return { unlock, setEnabled, update, crackle, charged, explode, emerge, seal, destroy };
}
