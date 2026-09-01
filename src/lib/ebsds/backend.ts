/**
 * Backend selection layer.
 *
 * `getBackend()` returns the active EB-SDS backend. Today that is the mock
 * service; pointing it at the Python API is a one-line change here and
 * requires no modification anywhere in the UI.
 */
import type {
  EbsdsBackend,
  SensingMode,
  SimulationParams,
  SonarFrame,
  SystemStatus,
} from "./types";
import { mockFrame } from "./mock-engine";

export const mockBackend: EbsdsBackend = {
  async getStatus(): Promise<SystemStatus> {
    return {
      online: true,
      input_source: "WOKWI / ESP32",
      sampling_rate: 50000,
      block_size: 500,
      firmware: "EB-SDS v1.4.0 · MOCK",
      link_latency_ms: 12,
    };
  },
  async process(params: SimulationParams): Promise<SonarFrame> {
    return mockFrame(params);
  },
  subscribe(getParams, onFrame) {
    const id = setInterval(() => onFrame(mockFrame(getParams())), 120);
    return () => clearInterval(id);
  },
  async setMode() {
    /* no-op in mock */
  },
};

/** REST client for the real Python service. Not active yet. */
export function createHttpBackend(baseUrl: string): EbsdsBackend {
  const json = async (path: string, init?: RequestInit) => {
    const res = await fetch(`${baseUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  };
  return {
    getStatus: () => json("/api/status"),
    process: (params) =>
      json("/api/process", { method: "POST", body: JSON.stringify(params) }),
    subscribe(getParams, onFrame) {
      const ws = new WebSocket(baseUrl.replace(/^http/, "ws") + "/ws/stream");
      ws.onopen = () => ws.send(JSON.stringify(getParams()));
      ws.onmessage = (e) => onFrame(JSON.parse(e.data) as SonarFrame);
      return () => ws.close();
    },
    setMode: (mode: SensingMode) =>
      json("/api/mode", { method: "POST", body: JSON.stringify({ mode }) }),
  };
}

export function getBackend(): EbsdsBackend {
  return createHttpBackend("http://127.0.0.1:8000");
}
