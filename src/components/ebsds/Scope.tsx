import { useEffect, useRef } from "react";
import type { SonarFrame } from "@/lib/ebsds/types";

interface ScopeProps {
  frame: SonarFrame | null;
  /** 0 = raw only, 1 = fully processed. Drives the baseline-removal morph. */
  morph: number;
  showNoiseFloor: boolean;
  showDetection: boolean;
  showThreshold: boolean;
  running: boolean;
}

function css(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  return (
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
  );
}

export function Scope({
  frame,
  morph,
  showNoiseFloor,
  showDetection,
  showThreshold,
  running,
}: ScopeProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const state = useRef({ frame, morph, showNoiseFloor, showDetection, showThreshold, running });
  state.current = { frame, morph, showNoiseFloor, showDetection, showThreshold, running };

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const colors = {
      grid: css("--grid", "#2a3540"),
      trace: css("--trace", "#5fe3f0"),
      dim: css("--trace-dim", "#5b7285"),
      caution: css("--caution", "#e8b23a"),
      alarm: css("--alarm", "#e05a45"),
      nominal: css("--nominal", "#4fe0a8"),
      fg: css("--foreground", "#dfe8ee"),
    };

    let t = 0;
    const draw = () => {
      const s = state.current;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // grid
      ctx.strokeStyle = colors.grid;
      ctx.globalAlpha = 0.32;
      ctx.lineWidth = 1;
      for (let i = 0; i <= 10; i++) {
        const x = Math.round((i / 10) * w) + 0.5;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let i = 0; i <= 8; i++) {
        const y = Math.round((i / 8) * h) + 0.5;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      const f = s.frame;
      if (!f) {
        raf.current = requestAnimationFrame(draw);
        return;
      }

      const n = f.samples.length;
      const scale = h / 2.6;
      const mid = h / 2;

      // The backend can return real ADC counts (e.g. 0..4095) in `samples`
      // while `processed` is normalized for DSP. Normalize only for plotting so
      // both traces remain visible on the same graph.
      const rawMax = f.samples.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
      const rawScale = rawMax > 4 ? (rawMax > 1500 ? 4095 : 1023) : 1;
      const rawSamples = f.samples.map((v) => v / rawScale);
      const yRaw = (v: number) => mid - (v - f.dc_offset * s.morph) * scale;
      const yProc = (v: number) => mid - v * scale;

      // detection window shading
      if (s.showDetection && f.detection_window) {
        const x0 = f.detection_window.start * w;
        const x1 = f.detection_window.end * w;
        ctx.fillStyle = colors.nominal;
        ctx.globalAlpha = 0.09;
        ctx.fillRect(x0, 0, x1 - x0, h);
        ctx.globalAlpha = 0.55;
        ctx.strokeStyle = colors.nominal;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(x0, 0);
        ctx.lineTo(x0, h);
        ctx.moveTo(x1, 0);
        ctx.lineTo(x1, h);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.fillStyle = colors.nominal;
        ctx.font = "10px 'IBM Plex Mono', monospace";
        ctx.fillText("ECHO WINDOW", x0 + 6, 14);
      }

      // noise floor band
      if (s.showNoiseFloor) {
        const nf = f.noise_floor * scale;
        ctx.fillStyle = colors.dim;
        ctx.globalAlpha = 0.16;
        ctx.fillRect(0, mid - nf, w, nf * 2);
        ctx.globalAlpha = 1;
        ctx.fillStyle = colors.dim;
        ctx.font = "10px 'IBM Plex Mono', monospace";
        ctx.fillText("NOISE FLOOR", 6, mid - nf - 4);
      }

      // DC baseline
      if (s.morph < 0.99) {
        const yb = mid - f.dc_offset * (1 - s.morph) * scale;
        ctx.strokeStyle = colors.caution;
        ctx.globalAlpha = 0.75 * (1 - s.morph) + 0.25;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(0, yb);
        ctx.lineTo(w, yb);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = colors.caution;
        ctx.font = "10px 'IBM Plex Mono', monospace";
        ctx.fillText(`DC BASELINE  ${f.dc_offset.toFixed(3)}`, w - 150, yb - 5);
        ctx.globalAlpha = 1;
      }

      // zero axis
      ctx.strokeStyle = colors.grid;
      ctx.beginPath();
      ctx.moveTo(0, mid + 0.5);
      ctx.lineTo(w, mid + 0.5);
      ctx.stroke();

      // detection threshold
      if (s.showThreshold) {
        const th = f.detection_threshold * scale;
        ctx.strokeStyle = colors.alarm;
        ctx.globalAlpha = 0.7;
        ctx.setLineDash([2, 4]);
        [mid - th, mid + th].forEach((y) => {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        });
        ctx.setLineDash([]);
        ctx.fillStyle = colors.alarm;
        ctx.font = "10px 'IBM Plex Mono', monospace";
        ctx.fillText(`THRESHOLD ±${f.detection_threshold.toFixed(3)}`, 6, mid - th - 4);
        ctx.globalAlpha = 1;
      }

      // ghost raw trace behind processed
      if (s.morph > 0.02) {
        ctx.strokeStyle = colors.dim;
        ctx.globalAlpha = 0.3 * (1 - s.morph) + 0.12;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
          const x = (i / (n - 1)) * w;
          const y = mid - (rawSamples[i]! - f.dc_offset) * scale * 0.999;
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // main trace: interpolate raw -> processed
      ctx.lineWidth = 1.25;
      ctx.strokeStyle = colors.trace;
      ctx.shadowColor = colors.trace;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * w;
        const rawV = rawSamples[i]!;
        const procV = f.processed[i]!;
        const y = yRaw(rawV) * (1 - s.morph) + yProc(procV) * s.morph;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // sweep cursor
      if (s.running) {
        t = (t + 0.004) % 1;
        const x = t * w;
        const g = ctx.createLinearGradient(x - 40, 0, x, 0);
        g.addColorStop(0, "rgba(0,0,0,0)");
        g.addColorStop(1, colors.trace);
        ctx.globalAlpha = 0.25;
        ctx.fillStyle = g;
        ctx.fillRect(x - 40, 0, 40, h);
        ctx.globalAlpha = 1;
      }

      raf.current = requestAnimationFrame(draw);
    };

    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, []);

  return <canvas ref={ref} className="h-full w-full" />;
}
