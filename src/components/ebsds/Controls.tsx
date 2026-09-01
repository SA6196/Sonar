import { cn } from "@/lib/utils";
import type { SimulationParams } from "@/lib/ebsds/types";

export function Slider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="px-3 py-1.5">
      <div className="flex items-baseline justify-between">
        <span className="label-xs">{label}</span>
        <span className="tabular-nums text-[12px] text-primary">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1.5 h-1 w-full cursor-pointer appearance-none bg-secondary accent-primary
          [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-1.5 [&::-webkit-slider-thumb]:appearance-none
          [&::-webkit-slider-thumb]:bg-primary [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:w-1.5
          [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-primary"
      />
    </div>
  );
}

export function CmdButton({
  children,
  onClick,
  tone = "default",
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  tone?: "default" | "accent" | "alarm";
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex-1 border px-2 py-1.5 text-[11px] tracking-[0.12em] transition-colors",
        tone === "accent"
          ? "border-primary/60 bg-primary/15 text-primary hover:bg-primary/25"
          : tone === "alarm"
            ? "border-alarm/50 text-alarm hover:bg-alarm/15"
            : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground",
        active && "bg-primary/20 text-primary",
      )}
    >
      {children}
    </button>
  );
}

export const PRESETS: { id: string; label: string; note: string; patch: Partial<SimulationParams> }[] =
  [
    {
      id: "clear",
      label: "CLEAR ECHO",
      note: "Strong localized acoustic return",
      patch: { target_amplitude: 0.72, noise_level: 12 },
    },
    {
      id: "weak",
      label: "WEAK ECHO",
      note: "Low-amplitude return for processing",
      patch: { target_amplitude: 0.16, noise_level: 34 },
    },
    {
      id: "noise",
      label: "HIGH NOISE",
      note: "Ambient noise dominates the waveform",
      patch: { target_amplitude: 0.34, noise_level: 68 },
    },
    {
      id: "transient",
      label: "SHORT TRANSIENT",
      note: "Localized echo for time-domain analysis",
      patch: { target_amplitude: 0.55, noise_level: 20, target_duration: 0.4 },
    },
    {
      id: "tone",
      label: "FREQUENCY SWEEP",
      note: "Change frequency and observe the FFT",
      patch: { target_amplitude: 0.48, noise_level: 18, target_frequency: 8000 },
    },
  ];