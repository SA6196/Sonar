import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { SonarFrame } from "@/lib/ebsds/types";

export function Panel({
  title,
  right,
  children,
  className,
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel flex min-h-0 flex-col", className)}>
      <header className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <h2 className="label-xs text-foreground/80">{title}</h2>
        {right}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

export function Readout({
  label,
  value,
  unit,
  tone = "default",
}: {
  label: string;
  value: string;
  unit?: string | undefined;
  tone?: "default" | "accent" | "caution" | "alarm";
}) {
  return (
    <div className="flex items-baseline justify-between border-b border-border/60 px-3 py-1.5 last:border-b-0">
      <span className="label-xs">{label}</span>
      <span
        className={cn(
          "tabular-nums text-[13px]",
          tone === "accent" && "text-primary",
          tone === "caution" && "text-caution",
          tone === "alarm" && "text-alarm",
        )}
      >
        {value}
        {unit && <span className="ml-1 text-[10px] text-muted-foreground">{unit}</span>}
      </span>
    </div>
  );
}

export function Bar({ value, tone = "accent" }: { value: number; tone?: string }) {
  return (
    <div className="h-1 w-full bg-secondary">
      <div
        className={cn(
          "h-full transition-[width] duration-500",
          tone === "accent" && "bg-primary",
          tone === "caution" && "bg-caution",
          tone === "alarm" && "bg-alarm",
          tone === "nominal" && "bg-nominal",
        )}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  );
}

export function RocCurve({ frame }: { frame: SonarFrame | null }) {
  if (!frame) return <div className="h-24" />;
  const pts = frame.roc
    .map((p, i) => {
      const x = (i / (frame.roc.length - 1)) * 100;
      return `${x},${(1 - p.pd) * 100}`;
    })
    .join(" ");
  const opX =
    ((Math.log10(Math.max(1e-4, frame.pfa)) + 4) / 4) * 100;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-24 w-full">
      <defs>
        <pattern id="rocgrid" width="12.5" height="25" patternUnits="userSpaceOnUse">
          <path d="M12.5 0V25M0 25H12.5" stroke="var(--grid)" strokeWidth="0.3" fill="none" />
        </pattern>
      </defs>
      <rect width="100" height="100" fill="url(#rocgrid)" opacity="0.5" />
      <polyline points={pts} fill="none" stroke="var(--trace)" strokeWidth="0.9" />
      <line
        x1={opX}
        y1="0"
        x2={opX}
        y2="100"
        stroke="var(--caution)"
        strokeWidth="0.5"
        strokeDasharray="2 2"
      />
      <circle
        cx={opX}
        cy={(1 - frame.pd) * 100}
        r="1.8"
        fill="var(--caution)"
        stroke="var(--background)"
        strokeWidth="0.6"
      />
    </svg>
  );
}
