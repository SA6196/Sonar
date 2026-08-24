# Energy-Constrained Detection-Feasible Software-Defined Sonar

**SIH26058** Â· Feasibility-first sonar mode selection for small Autonomous Underwater Vehicles (AUVs)

> A small underwater robot has several sonar modes. Before spending battery, the controller checks whether each mode is good enough for detection, has an acceptable false-alarm rate, and fits the current energy budget â€” then picks the cheapest mode that passes all three checks. If nothing passes, it says so instead of pretending sensing is reliable.

---

## The problem

Small AUVs run on limited battery. A stronger sonar mode senses better but costs more energy. Always using the strongest mode wastes battery when a cheaper mode would already work â€” and always using the cheapest mode risks missing targets when conditions are hard. The system needs to pick, in real time, the cheapest mode that still meets detection requirements.

## What already exists (and what we're not claiming)

- **Software-defined sonar** â€” configurable sonar hardware/software, already established (Zhou et al., 2025).
- **Energy-aware AUV sensing** â€” cheap sensing triggering more expensive sensing when needed (Woithe & Kremer).
- **Adaptive waveform selection** â€” changing sensing parameters under resource constraints, an existing research area.
- **Pd / Pfa detection theory** â€” the Neymanâ€“Pearson framework and CFAR are decades old.

We are not the first to do any of these individually. Our contribution is narrower and specific â€” see below.

## Our novelty

**A feasibility-first decision layer.** Every candidate sonar mode must pass three *hard, independent* admission checks before it's even allowed to compete for selection:

```
A_f = { a âˆˆ A : Pd(a) â‰¥ Pd_min, Pfa(a) â‰¤ Pfa_max, E(a) â‰¤ E_available }
a*  = argmin_{a âˆˆ A_f} E(a)
```

- A mode with excellent energy efficiency but an unacceptable false-alarm rate is still **rejected** â€” it cannot buy back a failed constraint with a good score elsewhere.
- If **no** mode is feasible, the system does not silently degrade detection quality. It explicitly reports a **DEGRADED** sensing state and switches to the safest low-energy fallback.

This is deliberately *not* a weighted score (`Score = 0.7Â·Pd âˆ’ 0.2Â·Energy`) â€” a score can hide an unacceptable constraint behind a good overall number. Ours can't.

## The math

| Step | Formula | Meaning |
|---|---|---|
| Transmission loss | `TL(r) = 20Â·log10(r) + Î±Â·r` | Signal weakening over distance |
| Sonar equation | `SNR(a) = SL(a) âˆ’ 2Â·TL(r,a) âˆ’ NL + DI(a)` | Signal clarity for mode `a` |
| Detection probability | `Pd(a) = Q((Î³ âˆ’ SNR(a)) / Ïƒ)` | Chance of a real detection |
| False-alarm probability | `Pfa(a) = Q(Î³ / Ïƒ)` | Chance of a false detection |
| Feasible set | `A_f = { a : Pdâ‰¥Pd_min, Pfaâ‰¤Pfa_max, Eâ‰¤E_available }` | Modes that pass all three gates |
| Selection | `a* = argmin_{aâˆˆA_f} E(a)` | Cheapest feasible mode |

`Q(Â·)` is the Gaussian tail-probability function. `Î³` is the detection threshold, `Ïƒ` the noise-distribution parameter â€” both per-mode, calibrated from the transducer in the physical build.

## Sonar modes

| Mode | Purpose | Energy | Notes |
|---|---|---|---|
| **M1 â€” Scout** | Cheap initial sensing | Low | Short pulse, narrow bandwidth |
| **M2 â€” Search** | Normal target search | Medium | Balanced mode |
| **M3 â€” Inspect** | Close inspection in hard conditions | High | Long pulse, wide bandwidth |

## Software pipeline

```
environment.py â†’ sonar_physics.py â†’ detection_model.py â†’ energy_model.py
â†’ feasibility_filter.py â†’ mode_selector.py â†’ hardware_controller.py
â†’ sonar_transmit_receive.py â†’ measurement_logger.py â†’ dashboard.py
```

Each candidate mode flows through this pipeline every sensing cycle: environment conditions â†’ SNR â†’ Pd/Pfa â†’ energy cost â†’ the hard feasibility gate â†’ the lowest-energy survivor is selected and configured on the hardware.

## Live demo

An interactive browser dashboard (`sonar_feasibility_dashboard.html`) simulates the full decision pipeline â€” move the range / noise / battery sliders and watch each mode get evaluated, gated, and selected (or watch the system enter DEGRADED state when nothing is feasible). No hardware required to run it; open the file in any browser.

## Hardware (planned)

- ESP32 / STM32 controller running the feasibility logic (arithmetic + Q-function only â€” no GPU needed)
- Piezoelectric transducer / hydrophone-compatible transmit-receive chain
- INA219 / INA226 for measured (not assumed) per-mode energy consumption
- LiPo battery with a protected reserve floor

## Known limitations

- Tabletop tank acoustics do not reproduce open-water conditions â€” used to validate control architecture, not production sonar performance.
- The Gaussian detector model is an approximation to be calibrated against real transducer measurements.
- Exact pulse frequencies/durations depend on the transducer eventually selected, not fixed in advance.
- Only three prototype modes; single-target, simplified environment for this stage.
- No long-horizon mission planning yet â€” the controller makes immediate feasible, minimum-energy decisions only.

## Team

| Name | Registration No. |
|---|---|
| Nikhil Sagar | 25BCE2446 |
| Tanvi Hanish | 25BCE2411 |
| Shivansh Agrawal | 25BCE2458 |
| Tanmay Shukla | 25BCE0865 |
| Divya Sharma | 25BCE2271 |
| Utkarsh Saxena | 25BEC0160 |

**Guidance:** Prof. Anish Kumar Manoharan, Associate Professor, SENSE, VIT

## Citations

Zhou et al. (2025) â€” Software-Defined Sonar for Unmanned Underwater System Â· Woithe & Kremer â€” feature-based adaptive energy management for AUV sensors Â· Neymanâ€“Pearson detection theory Â· CFAR sonar research. Full bibliographic details to be verified from original sources before final submission.
