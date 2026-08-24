"""
demo_integration.py -- End-to-end pipeline demo (no dashboard needed).

Wires together:
    Person 1:  environment.py  (Environment dataclass + scenarios)
    Person 2:  detection_model, energy_model, feasibility_filter, mode_selector
    SNR stub:  simple sonar equation until Person 1 fills in sonar_physics.py

Run:  python demo_integration.py
"""

import math
from environment import generate_environment, simulate_environment, SCENARIOS
from mode_library import get_all_modes
from detection_model import calculate_pd, calculate_pfa
from feasibility_filter import check_feasibility
from mode_selector import select_mode


# ── SNR stub (stands in for Person 1's sonar_physics.get_snr) ───────────
# Uses the sonar equation from the README:
#   SNR = SL - 2*TL - NL + DI
#   TL  = 20*log10(r) + alpha*r
# We assign illustrative SL and DI per mode so the worked example holds.

MODE_PHYSICS = {
    "M1": {"source_level": 150.0, "directivity_index": 5.0},
    "M2": {"source_level": 160.0, "directivity_index": 10.0},
    "M3": {"source_level": 170.0, "directivity_index": 15.0},
}
ABSORPTION_COEFF = 0.1  # dB/m (illustrative for shallow freshwater)


def stub_get_snr(mode: dict, env) -> float:
    """Placeholder SNR calc until Person 1 ships sonar_physics.get_snr()."""
    p = MODE_PHYSICS[mode["id"]]
    r = max(env.target_range_m, 0.1)  # avoid log(0)
    tl = 20.0 * math.log10(r) + ABSORPTION_COEFF * r
    snr = p["source_level"] - 2.0 * tl - env.noise_level_db + p["directivity_index"]
    return snr


# ── Pretty printer ──────────────────────────────────────────────────────

def run_scenario(name: str, env):
    modes = get_all_modes()
    print(f"\n{'=' * 70}")
    print(f"  SCENARIO: {name}")
    print(f"  Range = {env.target_range_m:.1f} m  |  Noise = {env.noise_level_db:.1f} dB  "
          f"|  Battery = {env.battery_j:.2f} J  |  Usable = {env.available_energy_j:.2f} J")
    print(f"{'=' * 70}")

    results = []
    for mode in modes:
        snr = stub_get_snr(mode, env)
        pd  = calculate_pd(snr, mode["gamma"], mode["sigma"])
        pfa = calculate_pfa(mode["gamma"], mode["sigma"])
        res = check_feasibility(mode, snr, env.available_energy_j)
        results.append(res)

        status = "PASS" if res["feasible"] else "FAIL"
        print(f"\n  [{status}] {mode['id']} ({mode['name']})")
        print(f"        SNR  = {snr:+.2f} dB")
        print(f"        Pd   = {pd:.4f}  {'OK' if res['pd_ok'] else 'XX  <-- below 0.85'}")
        print(f"        Pfa  = {pfa:.6f}  {'OK' if res['pfa_ok'] else 'XX  <-- above 0.05'}")
        print(f"        E    = {res['energy']:.2f} J   {'OK' if res['energy_ok'] else 'XX  <-- exceeds budget'}")
        if res["rejection_reasons"]:
            print(f"        Rejected: {', '.join(res['rejection_reasons'])}")

    selection = select_mode(results, modes)
    print(f"\n  >> DECISION: {selection['selected_mode_id']}"
          f"  {'[DEGRADED]' if selection['degraded'] else '[NOMINAL]'}")
    print(f"     {selection['reason']}")
    print()


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("#  SIH26058 -- Feasibility-First Sonar Mode Controller")
    print("#  Integration Demo (Person 1 env + Person 2 logic)")
    print("#" * 70)

    # Run all of Person 1's named scenarios
    for scenario_name in SCENARIOS:
        env = generate_environment(scenario_name)
        run_scenario(scenario_name, env)

    # Bonus: a couple of random environments
    print("\n" + "#" * 70)
    print("#  RANDOMIZED ENVIRONMENTS")
    print("#" * 70)
    for seed in range(3):
        env = simulate_environment(seed=seed)
        run_scenario(f"random (seed={seed})", env)
