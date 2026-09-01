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
      label: "CLEAR TARGET",
      note: "Strong echo · high battery → TIER 1 sufficient",
      patch: { target_amplitude: 0.72, noise_level: 12, battery_level: 0.9 },
    },
    {
      id: "weak",
      label: "WEAK TARGET",
      note: "Low SNR · high battery → TIER 2 escalation",
      patch: { target_amplitude: 0.16, noise_level: 34, battery_level: 0.92 },
    },
    {
      id: "noise",
      label: "HIGH NOISE",
      note: "Ambient dominated · Pfa rises",
      patch: { target_amplitude: 0.34, noise_level: 68, battery_level: 0.8 },
    },
    {
      id: "lowbat",
      label: "LOW BATTERY",
      note: "Reserve pressure on escalation budget",
      patch: { target_amplitude: 0.6, noise_level: 20, battery_level: 0.32 },
    },
    {
      id: "weak-lowbat",
      label: "TARGET + LOW BATTERY",
      note: "TIER 2 would help but violates reserve → DEGRADED",
      patch: { target_amplitude: 0.16, noise_level: 34, battery_level: 0.3 },
    },
  ];
