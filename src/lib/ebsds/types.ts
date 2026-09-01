/**
 * EB-SDS — Energy-Aware Bi-Level Sonar Detection System
 * Shared contract between the frontend and the Python backend.
 *
 * The frontend NEVER implements signal-processing mathematics.
 * Everything below is produced by the backend (or, for now, the mock service).
 */

export type SensingMode = "TIER1" | "TIER2" | "DEGRADED";

/** Parameters the operator sends to the backend for a processing run. */
export interface SimulationParams {
  noise_level: number; // dB-ish operator scale 0..100
  target_amplitude: number; // 0..1 normalized ADC full scale
  target_frequency: number; // Hz
  target_position: number; // 0..1 fraction of the sample block
  target_duration: number; // ms
  sampling_rate: number; // Hz
  filter_cutoff: number; // Hz
  detection_threshold: number; // normalized amplitude
  battery_level: number; // 0..1
}

export interface SystemStatus {
  online: boolean;
  input_source: string; // "WOKWI / ESP32"
  sampling_rate: number;
  block_size: number;
  firmware: string;
  link_latency_ms: number;
}

/** Single processed acquisition block returned by the backend. */
export interface SonarFrame {
  timestamp: number;
  sampling_rate: number;
  block_size: number;

  /** Raw ADC block (with DC offset). */
  samples: number[];
  /** Post DC-removal + band-pass block. */
  processed: number[];
  /** DC baseline estimated by the backend. */
  dc_offset: number;

  /** Spectrum bins after FFT. */
  spectrum: { freq: number; magnitude: number }[];
  spectral_noise_floor: number;

  // Features
  rms: number;
  peak: number;
  peak_to_peak: number;
  variance: number;
  noise_floor: number;
  snr: number;
  dominant_frequency: number;
  bandwidth: number;
  spectral_energy: number;

  // Detection
  detected: boolean;
  confidence: number; // 0..1
  detection_threshold: number;
  detection_window: { start: number; end: number } | null;

  // Processing metadata returned by the Python backend.
  filter_metadata?: {
    hampel_outliers: number;
    notch_hz: number | null;
    highpass_hz: number;
    lowpass_hz: number;
    savgol: boolean;
    input_scaled?: boolean;
    input_scale?: number;
  };

  // Statistical model estimates
  pd: number;
  pfa: number;
  roc: { pfa: number; pd: number }[];

  // Energy
  battery: number; // 0..1
  energy_remaining: number; // J
  energy_reserve: number; // J
  tier1_cost: number; // J
  tier2_cost: number; // J

  // Decision
  current_mode: SensingMode;
  tier2_feasible: boolean;
  decision_reason: string;
}

/** Transport-agnostic backend contract. Swap the mock for the Python API. */
export interface EbsdsBackend {
  getStatus(): Promise<SystemStatus>;
  /** POST /api/process — send parameters, receive a fully processed frame. */
  process(params: SimulationParams): Promise<SonarFrame>;
  /** Optional live stream (WebSocket / SSE). Returns an unsubscribe fn. */
  subscribe?(
    params: () => SimulationParams,
    onFrame: (frame: SonarFrame) => void,
  ): () => void;
  /** POST /api/mode — force a sensing mode override. */
  setMode?(mode: SensingMode): Promise<void>;
}

export const DEFAULT_PARAMS: SimulationParams = {
  noise_level: 22,
  target_amplitude: 0.55,
  target_frequency: 4200,
  target_position: 0.52,
  target_duration: 2.4,
  sampling_rate: 50000,
  filter_cutoff: 8000,
  detection_threshold: 0.18,
  battery_level: 0.86,
};
