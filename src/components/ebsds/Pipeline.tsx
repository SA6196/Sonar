import { cn } from "@/lib/utils";

export const STAGES = [
  { id: "input", label: "INPUT", sub: "RAW ADC" },
  { id: "preprocess", label: "DC REMOVAL", sub: "CENTER SIGNAL" },
  { id: "filter", label: "FILTER", sub: "CONDITION" },
  { id: "features", label: "FEATURES", sub: "MEASURE" },
  { id: "fft", label: "FFT", sub: "SPECTRUM" },
  { id: "characterize", label: "CHARACTERIZE", sub: "SIGNAL" },
] as const;

export function Pipeline({ active }: { active: number }) {
  return (
    <div className="flex items-stretch gap-0 overflow-hidden">
      {STAGES.map((s, i) => {
        const done = i < active;
        const live = i === active;
        return (
          <div key={s.id} className="flex min-w-0 flex-1 items-stretch">
            <div
              className={cn(
                "relative min-w-0 flex-1 overflow-hidden border-y border-l px-3 py-2 transition-colors duration-300",
                i === STAGES.length - 1 && "border-r",
                done && "border-primary/40 bg-primary/8",
                live && "border-primary bg-primary/15",
                !done && !live && "border-border bg-panel",
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full transition-colors",
                    live
                      ? "live-dot bg-primary"
                      : done
                        ? "bg-primary"
                        : "bg-muted-foreground/40",
                  )}
                />
                <span
                  className={cn(
                    "truncate text-[11px] tracking-[0.14em]",
                    done || live ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {s.label}
                </span>
              </div>
              <div className="label-xs mt-1 truncate">{s.sub}</div>
              {live && (
                <span className="pointer-events-none absolute inset-y-0 left-0 w-1/3 stage-sweep bg-linear-to-r from-transparent via-primary/25 to-transparent" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
