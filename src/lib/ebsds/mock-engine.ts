/**
 * MOCK DATA SERVICE — placeholder only.
 *
 * This file exists solely so the UI has something to render before the real
 * Python EB-SDS backend is attached. It is intentionally isolated: deleting it
 * and pointing `EbsdsBackend` at the HTTP client requires no UI changes.
 * None of this is the production signal-processing chain.
 */
import type { SimulationParams, SonarFrame, SensingMode } from "./types";

const BLOCK = 500;
const DC = 0.42;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export function mockFrame(p: SimulationParams, seed = Date.now()): SonarFrame {
  const rand = rng(seed);
  const noise = p.noise_level / 100;
  const n = BLOCK;
  const dur = Math.max(0.2, p.target_duration);
  const durSamples = (dur / 1000) * p.sampling_rate;
  const centre = p.target_position * n;
  const half = Math.max(6, Math.min(n / 3, durSamples / 2));

  const raw: number[] = new Array(n);
  const processed: number[] = new Array(n);
  const cutoffAtten = Math.min(1, p.filter_cutoff / Math.max(1, p.target_frequency));

  for (let i = 0; i < n; i++) {
    const t = i / p.sampling_rate;
    const env = Math.exp(-Math.pow((i - centre) / half, 2));
    const echo = p.target_amplitude * env * Math.sin(2 * Math.PI * p.target_frequency * t);
    const wn = (rand() * 2 - 1) * noise * 0.55;
    const drift = 0.012 * Math.sin((i / n) * Math.PI * 1.7);
    raw[i] = DC + drift + echo + wn;
    processed[i] = echo * cutoffAtten + wn * 0.45 * cutoffAtten;
  }

  // features
  let sum = 0,
    sq = 0,
    peak = 0,
    min = Infinity,
    max = -Infinity;
  for (const v of processed) {
    sum += v;
    sq += v * v;
    peak = Math.max(peak, Math.abs(v));
    min = Math.min(min, v);
    max = Math.max(max, v);
  }
  const mean = sum / n;
  const rms = Math.sqrt(sq / n);
  const variance = sq / n - mean * mean;
  const noiseFloor = noise * 0.28 + 0.008;
  const snr = 20 * Math.log10(Math.max(1e-4, peak) / Math.max(1e-4, noiseFloor));

  // spectrum (cosmetic envelope, not a real FFT)
  const bins = 128;
  const nyq = p.sampling_rate / 2;
  const spectrum = Array.from({ length: bins }, (_, k) => {
    const freq = (k / bins) * nyq;
    const lobe =
      p.target_amplitude *
      cutoffAtten *
      Math.exp(-Math.pow((freq - p.target_frequency) / (420 + dur * 60), 2));
    const harm =
      0.18 *
      p.target_amplitude *
      Math.exp(-Math.pow((freq - p.target_frequency * 2) / 700, 2));
    const roll = freq > p.filter_cutoff ? Math.exp(-(freq - p.filter_cutoff) / 2200) : 1;
    const floor = (noise * 0.09 + 0.006) * (0.6 + rand() * 0.8);
    return { freq, magnitude: Math.max(0.001, (lobe + harm) * roll + floor) };
  });
  const specNoiseFloor = noise * 0.09 + 0.008;
  const dominant = spectrum.reduce((a, b) => (b.magnitude > a.magnitude ? b : a));
  const halfPow = dominant.magnitude / Math.SQRT2;
  const above = spectrum.filter((s) => s.magnitude >= halfPow);
  const first = above[0];
  const last = above[above.length - 1];
  const bandwidth = first && last ? Math.max(120, last.freq - first.freq) : 0;
  const spectralEnergy = spectrum.reduce((a, b) => a + b.magnitude * b.magnitude, 0);

  // detection
  const detected = peak > p.detection_threshold && snr > 2;
  const confidence = Math.max(
    0.02,
    Math.min(0.995, 1 / (1 + Math.exp(-(snr - 6) / 2.6)) * (detected ? 1 : 0.55)),
  );
  const pd = Math.max(0.01, Math.min(0.999, 1 / (1 + Math.exp(-(snr - 4.5) / 1.9))));
  const pfa = Math.max(
    1e-5,
    Math.min(0.4, 0.05 * Math.exp(-snr / 5) + noise * 0.012),
  );
  const roc = Array.from({ length: 40 }, (_, i) => {
    const x = Math.pow(10, -4 + (i / 39) * 4);
    return { pfa: x, pd: Math.min(0.999, Math.pow(x, 1 / (1 + Math.max(0.2, snr) / 3))) };
  });

  // energy
  const capacity = 5.0;
  const energyRemaining = p.battery_level * capacity;
  const reserve = 1.2;
  const tier1Cost = 0.31;
  const tier2Cost = 1.48;
  const tier1Sufficient = detected && pd >= 0.85 && pfa <= 0.05;
  const tier2Feasible = energyRemaining - tier2Cost >= reserve;

  let mode: SensingMode;
  let reason: string;
  if (tier1Sufficient) {
    mode = "TIER1";
    reason = `TIER 1 sufficient: Pd ${pd.toFixed(3)} ≥ 0.850 and Pfa ${pfa.toFixed(4)} ≤ 0.0500 at ${tier1Cost.toFixed(2)} J. Escalation not required.`;
  } else if (tier2Feasible) {
    mode = "TIER2";
    reason = `TIER 2 activated: TIER 1 detection confidence insufficient (Pd ${pd.toFixed(3)} < 0.850). Post-transaction energy ${(energyRemaining - tier2Cost).toFixed(2)} J ≥ reserve ${reserve.toFixed(2)} J — escalation feasible.`;
  } else {
    mode = "DEGRADED";
    reason = `TIER 2 rejected: escalation would leave ${(energyRemaining - tier2Cost).toFixed(2)} J against a ${reserve.toFixed(2)} J reserve. Energy constraint dominates — DEGRADED sensing selected.`;
  }

  return {
    timestamp: Date.now(),
    sampling_rate: p.sampling_rate,
    block_size: n,
    samples: raw,
    processed,
    dc_offset: DC,
    spectrum,
    spectral_noise_floor: specNoiseFloor,
    rms,
    peak,
    peak_to_peak: max - min,
    variance,
    noise_floor: noiseFloor,
    snr,
    dominant_frequency: dominant.freq,
    bandwidth,
    spectral_energy: spectralEnergy,
    detected,
    confidence,
    detection_threshold: p.detection_threshold,
    detection_window: detected
      ? { start: Math.max(0, (centre - half * 1.6) / n), end: Math.min(1, (centre + half * 1.6) / n) }
      : null,
    pd,
    pfa,
    roc,
    battery: p.battery_level,
    energy_remaining: energyRemaining,
    energy_reserve: reserve,
    tier1_cost: tier1Cost,
    tier2_cost: tier2Cost,
    current_mode: mode,
    tier2_feasible: tier2Feasible,
    decision_reason: reason,
  };
}
