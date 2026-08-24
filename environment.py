"""
Person 1 -- Physics & Environment
environment.py

Generates the "world" the sonar operates in: target range, background
noise level, and battery / available energy state.

In the finished system this data comes from real sensors (a range
estimate, a noise measurement, an INA219/INA226 battery reading). Right
now, at Review 1, we simulate it so the rest of the pipeline
(SNR -> Pd/Pfa -> feasibility filter -> mode selection) can be built and
tested end-to-end before any hardware exists.
"""

from dataclasses import dataclass
import random


@dataclass
class Environment:
    target_range_m: float           # distance to target, in meters
    noise_level_db: float           # background acoustic noise, in dB
    battery_j: float                # energy currently in the battery, Joules
    battery_reserve_j: float = 0.5  # hard floor -- never let a mode spend this

    @property
    def available_energy_j(self) -> float:
        """Energy the mode-selector is actually allowed to spend."""
        return max(0.0, self.battery_j - self.battery_reserve_j)


# Named scenarios taken directly from the SIH doc's "Example situations"
# table (Section 1): Easy, Difficult (range or noise), Energy-limited.
SCENARIOS = {
    "easy":            dict(target_range_m=3.0,  noise_level_db=45.0, battery_j=5.0),
    "difficult_range": dict(target_range_m=15.0, noise_level_db=50.0, battery_j=5.0),
    "difficult_noise": dict(target_range_m=5.0,  noise_level_db=70.0, battery_j=5.0),
    "energy_limited":  dict(target_range_m=5.0,  noise_level_db=55.0, battery_j=0.7),
}


def generate_environment(scenario: str = "easy") -> Environment:
    """Return a fixed, named scenario -- useful for repeatable demos and
    for the judge-facing dashboard (same input -> same output every time)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from {list(SCENARIOS)}")
    return Environment(**SCENARIOS[scenario])


def simulate_environment(seed: int = None) -> Environment:
    """Return a randomized environment -- useful for stress-testing the
    feasibility controller across many missions in the simulation loop
    described in PDF Section 12."""
    rng = random.Random(seed)
    return Environment(
        target_range_m=rng.uniform(1.0, 20.0),
        noise_level_db=rng.uniform(40.0, 75.0),
        battery_j=rng.uniform(0.3, 5.0),
    )


if __name__ == "__main__":
    print("Named scenarios:")
    for name in SCENARIOS:
        env = generate_environment(name)
        print(f"  {name:16s} -> {env} | usable energy = {env.available_energy_j:.2f} J")

    print("\nRandomized environments (seeded, so this is repeatable):")
    for i in range(3):
        env = simulate_environment(seed=i)
        print(f"  seed={i} -> {env}")