import { useEffect, useRef } from "react";
import type { SonarFrame } from "@/lib/ebsds/types";

function css(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  return (
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
  );
}

export function Spectrum({ frame, reveal }: { frame: SonarFrame | null; reveal: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const state = useRef({ frame, reveal });
  state.current = { frame, reveal };

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
    };

    const smooth: number[] = [];
    const draw = () => {
      const { frame: f, reveal: rv } = state.current;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      ctx.strokeStyle = colors.grid;
      ctx.globalAlpha = 0.3;
      for (let i = 0; i <= 8; i++) {
        const x = Math.round((i / 8) * w) + 0.5;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let i = 0; i <= 4; i++) {
        const y = Math.round((i / 4) * h) + 0.5;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (!f) {
        raf.current = requestAnimationFrame(draw);
        return;
      }

      const bins = f.spectrum;
      const maxMag = Math.max(...bins.map((b) => b.magnitude), 0.05);
      for (let i = 0; i < bins.length; i++) {
        const target = (bins[i]!.magnitude / maxMag) * rv;
        smooth[i] = (smooth[i] ?? 0) + (target - (smooth[i] ?? 0)) * 0.18;
      }

      // noise floor line
      const nfY = h - (f.spectral_noise_floor / maxMag) * h * rv;
      ctx.strokeStyle = colors.dim;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, nfY);
      ctx.lineTo(w, nfY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = colors.dim;
      ctx.font = "10px 'IBM Plex Mono', monospace";
      ctx.fillText("SPECTRAL NOISE FLOOR", 6, Math.max(10, nfY - 4));

      // filled spectrum
      ctx.beginPath();
      ctx.moveTo(0, h);
      smooth.forEach((v, i) => {
        ctx.lineTo((i / (smooth.length - 1)) * w, h - v * h * 0.92);
      });
      ctx.lineTo(w, h);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, colors.trace);
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.globalAlpha = 0.22;
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = colors.trace;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      smooth.forEach((v, i) => {
        const x = (i / (smooth.length - 1)) * w;
        const y = h - v * h * 0.92;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();

      // dominant frequency marker + bandwidth
      const nyq = f.sampling_rate / 2;
      const dx = (f.dominant_frequency / nyq) * w;
      const bw = (f.bandwidth / nyq) * w;
      ctx.globalAlpha = 0.12 * rv;
      ctx.fillStyle = colors.caution;
      ctx.fillRect(dx - bw / 2, 0, bw, h);
      ctx.globalAlpha = 0.85 * rv;
      ctx.strokeStyle = colors.caution;
      ctx.beginPath();
      ctx.moveTo(dx, 0);
      ctx.lineTo(dx, h);
      ctx.stroke();
      ctx.fillStyle = colors.caution;
      ctx.fillText(`f0 ${(f.dominant_frequency / 1000).toFixed(2)} kHz`, dx + 5, 13);
      ctx.fillText(`BW ${Math.round(f.bandwidth)} Hz`, dx + 5, 26);
      ctx.globalAlpha = 1;

      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, []);

  return <canvas ref={ref} className="h-full w-full" />;
}
