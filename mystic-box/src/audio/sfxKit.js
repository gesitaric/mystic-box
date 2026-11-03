// Peças de Web Audio compartilhadas pelos efeitos sonoros (só apresentação).

export function makeNoiseBuffer(ctx, seconds) {
  const length = Math.floor(ctx.sampleRate * seconds);
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i += 1) data[i] = Math.random() * 2 - 1;
  return buffer;
}

export function makeImpulse(ctx, seconds, decay) {
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

// Nota com envelope exponencial, ligada a um ou mais destinos.
export function playTone(ctx, destinations, { type, from, to, gain, attack, duration, delay = 0 }) {
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
  destinations.forEach((destination) => amp.connect(destination));
  osc.start(t);
  osc.stop(t + duration + 0.05);
}

// Ruído filtrado com varredura de frequência (estalos, ventos, estouros).
export function playNoise(
  ctx,
  buffer,
  destinations,
  { duration, filterType, from, to, gain, delay = 0, attack = 0 }
) {
  const t = ctx.currentTime + delay;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.loop = true;
  const filter = ctx.createBiquadFilter();
  filter.type = filterType;
  filter.frequency.setValueAtTime(from, t);
  filter.frequency.exponentialRampToValueAtTime(to, t + duration);
  const amp = ctx.createGain();
  if (attack > 0) {
    amp.gain.setValueAtTime(0.0001, t);
    amp.gain.exponentialRampToValueAtTime(gain, t + attack);
  } else {
    amp.gain.setValueAtTime(gain, t);
  }
  amp.gain.exponentialRampToValueAtTime(0.0001, t + duration);
  source.connect(filter);
  filter.connect(amp);
  destinations.forEach((destination) => amp.connect(destination));
  source.start(t, Math.random() * Math.max(0, buffer.duration - duration - 0.1));
  source.stop(t + duration + 0.05);
}
