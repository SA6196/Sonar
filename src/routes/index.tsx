  import { createFileRoute } from "@tanstack/react-router";
  import { useCallback, useEffect, useMemo, useRef, useState } from "react";
  import { Scope } from "@/components/ebsds/Scope";
  import { Spectrum } from "@/components/ebsds/Spectrum";
  import { Pipeline, STAGES } from "@/components/ebsds/Pipeline";
  import { Panel, Readout } from "@/components/ebsds/Panels";
  import { Slider, CmdButton, PRESETS } from "@/components/ebsds/Controls";
  import { getBackend } from "@/lib/ebsds/backend";
  import { DEFAULT_PARAMS, type SimulationParams, type SonarFrame } from "@/lib/ebsds/types";
  import { cn } from "@/lib/utils";

  export const Route = createFileRoute("/")({
    head: () => ({
      meta: [
        { title: "EB-SDS — Energy-Aware Bi-Level Sonar Detection Console" },
        {
          name: "description",
          content:
            "Live console for EB-SDS: underwater sonar signal-processing chain, waveform conditioning, feature extraction and FFT spectral analysis.",
        },
        { property: "og:title", content: "EB-SDS — Energy-Aware Bi-Level Sonar Detection" },
        {
          property: "og:description",
          content:
            "Underwater acoustic signal-processing console: raw ADC waveform, preprocessing, feature extraction and spectral analysis.",
        },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    }),
    component: Console,
  });

  const STAGE_MS = 620;

  function Console() {
    const backend = useMemo(() => getBackend(), []);
    const [params, setParams] = useState<SimulationParams>(DEFAULT_PARAMS);
    const [frame, setFrame] = useState<SonarFrame | null>(null);
    const [stage, setStage] = useState(-1);
    const [running, setRunning] = useState(false);
    const [log, setLog] = useState<string[]>([]);
    const [preset, setPreset] = useState<string | null>(null);
    const paramsRef = useRef(params);
    paramsRef.current = params;
    const startRef = useRef(Date.now());

    const push = useCallback((msg: string) => {
      const t = ((Date.now() - startRef.current) / 1000).toFixed(2).padStart(6, "0");
      setLog((l) => [`[${t}] ${msg}`, ...l].slice(0, 60));
    }, []);

    // Single-shot process on parameter change
    useEffect(() => {
      let cancelled = false;
      backend.process(params).then((f) => !cancelled && setFrame(f));
      return () => {
        cancelled = true;
      };
    }, [backend, params]);

    // Live stream while running
    useEffect(() => {
      if (!running || !backend.subscribe) return;
      return backend.subscribe(() => paramsRef.current, setFrame);
    }, [running, backend]);

    const run = useCallback(() => {
      setStage(0);
      setRunning(false);
      startRef.current = Date.now();
      setLog([]);
      push("ACQ start · block 500 samples @ 50 kHz");
      STAGES.forEach((s, i) => {
        if (i === 0) return;
        setTimeout(() => setStage(i), i * STAGE_MS);
      });
      setTimeout(() => setRunning(true), STAGES.length * STAGE_MS);
    }, [push]);

    // stage narration
    useEffect(() => {
      if (stage < 0 || !frame) return;
      const f = frame;
      const lines: Record<number, string> = {
        0: `INPUT · ${f.block_size} ADC samples @ ${(f.sampling_rate / 1000).toFixed(0)} kHz`,
        1: `DC REMOVAL · estimated baseline ${f.dc_offset.toFixed(3)} · waveform centered`,
        2: `FILTER · configurable cutoff ${(params.filter_cutoff / 1000).toFixed(1)} kHz · unwanted components reduced`,
        3: `FEATURES · RMS ${f.rms.toFixed(4)} · peak ${f.peak.toFixed(4)} · SNR ${f.snr.toFixed(2)} dB`,
        4: `FFT · dominant frequency ${(f.dominant_frequency / 1000).toFixed(2)} kHz · bandwidth ${f.bandwidth.toFixed(0)} Hz`,
        5: `CHARACTERIZE · acoustic waveform characterized from time and frequency-domain features`,
      };
      const line = lines[stage];
      if (line) push(line);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stage]);

    const reached = (i: number) => stage >= i;
    const morph = reached(1) ? 1 : 0;
    const revealFFT = reached(4) ? 1 : 0;

    const applyPreset = (id: string, patch: Partial<SimulationParams>) => {
      setPreset(id);
      setParams((p) => ({ ...p, ...patch }));
      setTimeout(run, 30);
    };

    const reset = () => {
      setRunning(false);
      setStage(-1);
      setPreset(null);
      setParams(DEFAULT_PARAMS);
      setLog([]);
    };

    const modeTone = (m: string) =>
      m === "TIER1" ? "nominal" : m === "TIER2" ? "caution" : "alarm";

    return (
      <main className="flex h-screen min-h-0 flex-col overflow-hidden bg-background">
        {/* HEADER */}
        <header className="flex shrink-0 items-center justify-between border-b border-border bg-panel px-4 py-2">
          <div className="flex items-baseline gap-4">
            <h1 className="text-[15px] tracking-[0.28em] text-foreground">EB-SDS</h1>
            <span className="text-[11px] tracking-[0.1em] text-muted-foreground">
              Energy-Aware Bi-Level Sonar Detection System
            </span>
          </div>
          <div className="flex items-center gap-5 text-[10px] tracking-[0.14em] text-muted-foreground">
            <span className="flex items-center gap-1.5 text-nominal">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-nominal" />
              SYSTEM ONLINE
            </span>
            <span>INPUT: WOKWI / ESP32</span>
            <span>SAMPLING: 50 kHz</span>
            <span>BLOCK: 500 SAMPLES</span>
            <span className="border border-border px-1.5 py-0.5 text-foreground/70">
              {running ? "STREAMING" : stage >= 0 ? "SEQUENCING" : "IDLE"}
            </span>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-[248px_minmax(0,1fr)_282px] gap-px bg-border">
          {/* LEFT — CONTROLS */}
          <div className="flex min-h-0 flex-col gap-px overflow-y-auto bg-border">
            <Panel title="Simulation Controls">
              <div className="py-1">
                <Slider
                  label="Noise Level"
                  value={params.noise_level}
                  min={0}
                  max={100}
                  step={1}
                  format={(v) => `${v.toFixed(0)} dB`}
                  onChange={(v) => setParams((p) => ({ ...p, noise_level: v }))}
                />
                <Slider
                  label="Target Amplitude"
                  value={params.target_amplitude}
                  min={0}
                  max={1}
                  step={0.01}
                  format={(v) => v.toFixed(2)}
                  onChange={(v) => setParams((p) => ({ ...p, target_amplitude: v }))}
                />
                <Slider
                  label="Target Frequency"
                  value={params.target_frequency}
                  min={500}
                  max={20000}
                  step={100}
                  format={(v) => `${(v / 1000).toFixed(1)} kHz`}
                  onChange={(v) => setParams((p) => ({ ...p, target_frequency: v }))}
                />
                <Slider
                  label="Target Position"
                  value={params.target_position}
                  min={0.05}
                  max={0.95}
                  step={0.01}
                  format={(v) => `${(v * 100).toFixed(0)} %`}
                  onChange={(v) => setParams((p) => ({ ...p, target_position: v }))}
                />
                <Slider
                  label="Target Duration"
                  value={params.target_duration}
                  min={0.2}
                  max={8}
                  step={0.1}
                  format={(v) => `${v.toFixed(1)} ms`}
                  onChange={(v) => setParams((p) => ({ ...p, target_duration: v }))}
                />
                <Slider
                  label="Sampling Rate"
                  value={params.sampling_rate}
                  min={10000}
                  max={100000}
                  step={1000}
                  format={(v) => `${(v / 1000).toFixed(0)} kHz`}
                  onChange={(v) => setParams((p) => ({ ...p, sampling_rate: v }))}
                />
                <Slider
                  label="Filter Cutoff"
                  value={params.filter_cutoff}
                  min={1000}
                  max={24000}
                  step={250}
                  format={(v) => `${(v / 1000).toFixed(1)} kHz`}
                  onChange={(v) => setParams((p) => ({ ...p, filter_cutoff: v }))}
                />
                <Slider
                  label="Detection Threshold"
                  value={params.detection_threshold}
                  min={0.02}
                  max={0.8}
                  step={0.01}
                  format={(v) => v.toFixed(2)}
                  onChange={(v) => setParams((p) => ({ ...p, detection_threshold: v }))}
                />
                <Slider
                  label="Battery Level"
                  value={params.battery_level}
                  min={0.05}
                  max={1}
                  step={0.01}
                  format={(v) => `${(v * 100).toFixed(0)} %`}
                  onChange={(v) => setParams((p) => ({ ...p, battery_level: v }))}
                />
              </div>
              <div className="flex gap-px border-t border-border p-2">
                <CmdButton tone="accent" onClick={run}>
                  ▶ RUN
                </CmdButton>
                <CmdButton onClick={() => setRunning(false)} active={!running && stage >= 0}>
                  ❙❙ PAUSE
                </CmdButton>
                <CmdButton tone="alarm" onClick={reset}>
                  ⟲ RESET
                </CmdButton>
              </div>
            </Panel>

            <Panel title="Preset Scenarios" className="flex-1">
              <div className="p-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => applyPreset(p.id, p.patch)}
                    className={cn(
                      "mb-1 block w-full border px-2 py-1.5 text-left transition-colors",
                      preset === p.id
                        ? "border-primary/60 bg-primary/12"
                        : "border-border hover:border-primary/40 hover:bg-panel-raised",
                    )}
                  >
                    <div
                      className={cn(
                        "text-[11px] tracking-[0.1em]",
                        preset === p.id ? "text-primary" : "text-foreground/85",
                      )}
                    >
                      {p.label}
                    </div>
                    <div className="mt-0.5 text-[10px] leading-tight text-muted-foreground">
                      {p.note}
                    </div>
                  </button>
                ))}
              </div>
            </Panel>
          </div>

          {/* CENTER — WORKSPACE */}
          <div className="flex min-h-0 min-w-0 flex-col gap-px bg-border">
            <Panel
              title="Live Signal Workspace — Time Domain"
              className="min-h-[250px] flex-[3]"
              right={
                <div className="flex gap-4 text-[10px] tracking-[0.12em] text-muted-foreground">
                  <span className="text-trace">
                    {stage >= 1 ? "PROCESSED TRACE" : "RAW TRACE"}
                  </span>
                  <span>Δt {(1000 / params.sampling_rate).toFixed(3)} ms/sample</span>
                  <span>{frame?.block_size ?? 500} pts</span>
                </div>
              }
            >
              <div className="scanlines h-full w-full">
                <Scope
                  frame={frame}
                  morph={morph}
                  showNoiseFloor={reached(3)}
                  showDetection={false}
                  showThreshold={false}
                  running={running}
                />
              </div>
            </Panel>

            <div className="bg-panel px-px py-px">
              <Pipeline active={stage} />
            </div>

            <Panel
              title="Spectral Analysis — FFT"
              className="min-h-[220px] flex-[2]"
              right={
                <span className="text-[10px] tracking-[0.12em] text-muted-foreground">
                  MAGNITUDE vs FREQUENCY · 0 – {(params.sampling_rate / 2000).toFixed(0)} kHz
                </span>
              }
            >
              <div className="scanlines h-full w-full">
                <Spectrum frame={frame} reveal={revealFFT} />
              </div>
            </Panel>

            {/* SIGNAL PROCESSING EXPLANATION */}
            <Panel
              title="Signal Processing — What Happens to the Echo?"
              className="shrink-0"
            >
              <div className="grid grid-cols-6 gap-px bg-border">
                {[
                  ["CAPTURE", "ESP32 / Wokwi provides raw ADC samples."],
                  ["CENTER", "Estimate and remove the DC baseline."],
                  ["CLEAN", "Apply configurable filtering."],
                  ["MEASURE", "Extract amplitude and statistical features."],
                  ["TRANSFORM", "FFT reveals frequency content."],
                  ["CHARACTERIZE", "Combine time and spectral evidence."],
                ].map(([title, desc], i) => (
                  <div
                    key={title}
                    className={cn(
                      "relative min-h-[92px] overflow-hidden bg-panel px-2.5 py-2 transition-all duration-500",
                      reached(i) ? "bg-primary/8" : "opacity-55",
                    )}
                  >
                    <div className="mb-1 flex items-center gap-1.5">
                      <span className={cn(
                        "h-1.5 w-1.5 rounded-full transition-all duration-500",
                        reached(i) ? "live-dot bg-primary" : "bg-muted-foreground/40"
                      )} />
                      <span className="text-[10px] tracking-[0.16em] text-foreground/85">{title}</span>
                    </div>
                    <p className="text-[10px] leading-relaxed text-muted-foreground">{desc}</p>
                    {reached(i) && (
                      <span className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 animate-[stage-sweep_1.8s_linear_infinite] bg-linear-to-r from-transparent via-primary/10 to-transparent" />
                    )}
                  </div>
                ))}
              </div>
            </Panel>
            </div>

          {/* RIGHT — INSTRUMENTATION */}
          <div className="flex h-full min-h-0 flex-col gap-px overflow-y-auto bg-border">
            <Panel title="Feature Extraction" className="shrink-0">
              <div className={cn("transition-opacity", reached(2) ? "opacity-100" : "opacity-30")}>
                <Readout label="RMS" value={(frame?.rms ?? 0).toFixed(4)} />
                <Readout label="Peak" value={(frame?.peak ?? 0).toFixed(4)} />
                <Readout label="Peak-to-Peak" value={(frame?.peak_to_peak ?? 0).toFixed(4)} />
                <Readout label="Variance" value={(frame?.variance ?? 0).toExponential(2)} />
                <Readout
                  label="SNR"
                  value={(frame?.snr ?? 0).toFixed(2)}
                  unit="dB"
                  tone={(frame?.snr ?? 0) > 6 ? "accent" : "caution"}
                />
                <Readout
                  label="Dominant Freq"
                  value={((frame?.dominant_frequency ?? 0) / 1000).toFixed(2)}
                  unit="kHz"
                />
                <Readout label="Bandwidth" value={(frame?.bandwidth ?? 0).toFixed(0)} unit="Hz" />
                <Readout
                  label="Spectral Energy"
                  value={(frame?.spectral_energy ?? 0).toFixed(3)}
                />
              </div>
            </Panel>
              
            

            <Panel title="Processing Status" className="shrink-0">
              <div className="px-3 py-2 text-[10px] leading-[1.7]">
                {[
                  ["RAW ADC", "500 samples captured"],
                  ["DC REMOVAL", "baseline estimated per block"],
                  ["FILTERING", "configurable frequency conditioning"],
                  ["FEATURES", "time-domain measurements"],
                  ["FFT", "frequency-domain transformation"],
                  ["CHARACTERIZATION", "signal properties summarized"],
                ].map(([name, desc], i) => (
                  <div key={name} className="flex items-center gap-2 border-b border-border/50 py-1.5 last:border-0">
                    <span className={cn("h-1.5 w-1.5 rounded-full", reached(i) ? "bg-primary" : "bg-muted-foreground/35")} />
                    <span className={cn("w-[105px] tracking-[0.08em]", reached(i) ? "text-primary" : "text-muted-foreground")}>{name}</span>
                    <span className="text-muted-foreground">{desc}</span>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Processing Event Log" className="min-h-[140px] flex-1">
              <div className="h-full overflow-y-auto px-3 py-1.5 text-[10.5px] leading-[1.6]">
                {log.length === 0 && (
                  <div className="text-muted-foreground">— no events · press RUN —</div>
                )}
                {log.map((l, i) => (
                  <div
                    key={i}
                    className={cn(i === 0 ? "text-primary" : "text-muted-foreground")}
                  >
                    {l}
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      
      </main>
    );
  }