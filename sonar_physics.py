"""
sonar_physics.py

Turns the environment (range, noise) plus a sonar mode's hardware
parameters (source level, directivity index) into a single number: SNR.

This is the physics core of the whole project -- Pd, Pfa, and every
feasibility decision downstream depends on this being correct.
"""

import math
from dataclasses import dataclass

# Acoustic absorption coefficient, in dB/m. This is a placeholder value
# for a tabletop ultrasonic prototype. It MUST be recalibrated once the
# real transducer and water tank are available.
ALPHA_DB_PER_M = 0.05


@dataclass
class SonarMode:
    """
    The hardware-defined parameters of one sonar mode (M1 / M2 / M3).
    Ownership of these numbers ultimately belongs to mode_library.py
    (a teammate's module) -- this class just defines the shape that
    sonar_physics.py expects to receive.
    """
    name: str
    source_level_db: float        # SL: how loud the transmitted ping is
    directivity_index_db: float   # DI: gain from focusing the beam


def transmission_loss(range_m: float, alpha: float = ALPHA_DB_PER_M) -> float:
    """
    TL(r) = 20*log10(r) + alpha*r

    - The 20*log10(r) term is spherical spreading loss: sound spreads
      out over a growing sphere as it travels, so it gets weaker the
      same way a shout fades the farther away you stand.
    - The alpha*r term is absorption loss: water itself eats a bit of
      the sound energy per meter travelled.
    """
    if range_m <= 0:
        raise ValueError("range_m must be positive")
    return 20 * math.log10(range_m) + alpha * range_m


def sonar_equation(SL: float, TL: float, NL: float, DI: float) -> float:
    """
    SNR = SL - 2*TL - NL + DI

    TL is counted TWICE: once for the ping travelling out to the target,
    once for the echo travelling back to the receiver.
    """
    return SL - 2 * TL - NL + DI


def get_snr(mode: SonarMode, environment) -> float:
    """
    The one function the rest of the team calls.

    mode: a SonarMode (or anything with .source_level_db / .directivity_index_db)
    environment: an Environment (or anything with .target_range_m / .noise_level_db)

    Returns SNR in dB.
    """
    tl = transmission_loss(environment.target_range_m)
    return sonar_equation(
        SL=mode.source_level_db,
        TL=tl,
        NL=environment.noise_level_db,
        DI=mode.directivity_index_db,
    )


if __name__ == "__main__":
    from environment import generate_environment

    # PLACEHOLDER mode parameters -- tune these once the real transducer
    # is chosen (PDF Section 6: M1 Scout / M2 Search / M3 Inspect).
    modes = [
        SonarMode("M1-Scout",   source_level_db=140, directivity_index_db=10),
        SonarMode("M2-Search",  source_level_db=160, directivity_index_db=15),
        SonarMode("M3-Inspect", source_level_db=180, directivity_index_db=20),
    ]

    for scenario in ["easy", "difficult_range", "difficult_noise", "energy_limited"]:
        env = generate_environment(scenario)
        print(f"\nScenario: {scenario}  (range={env.target_range_m:.1f} m, noise={env.noise_level_db:.1f} dB)")
        for mode in modes:
            snr = get_snr(mode, env)
            print(f"  {mode.name:10s} SNR = {snr:6.2f} dB")
