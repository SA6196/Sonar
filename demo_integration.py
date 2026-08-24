"""
demo_integration.py -- End-to-end pipeline demo (no dashboard needed).

Wires together:
    Person 1:  environment.py + sonar_physics.py (real implementation)
    Person 2:  detection_model, energy_model, feasibility_filter, mode_selector

Run:  python demo_integration.py
"""

from environment import generate_environment, simulate_environment, SCENARIOS
from mode_library import get_all_modes
from detection_model import calculate_pd, calculate_pfa
from feasibility_filter import check_feasibility
from mode_selector import select_mode
from sonar_physics import get_snr, SonarMode


# Bridge between Person 2's mode dicts and Person 1's SonarMode dataclass.
# These SL/DI values match Person 1's self-test in sonar_physics.py.
SONAR_MODES = {
    "M1": SonarMode("M1-Scout",   source_level_db=140, directivity_index_db=10),
    "M2": SonarMode("M2-Search",  source_level_db=160, directivity_index_db=15),
    "M3": SonarMode("M3-Inspect", source_level_db=180, directivity_index_db=20),
}


# ── Pretty printer ──────────────────────────────────────────────────────

def run_scenario(name: str, env):
    modes = get_all_modes()
    avail_energy = env.available_energy_j

    print(f"\n{'=' * 70}")
    print(f"  SCENARIO: {name}")
    print(f"  Range = {env.target_range_m:.1f} m  |  Noise = {env.noise_level_db:.1f} dB  "
          f"|  Battery = {env.battery_j:.2f} J  |  Usable = {avail_energy:.2f} J")
    print(f"{'=' * 70}")

    results = []
    for mode in modes:
        sonar_mode = SONAR_MODES[mode["id"]]
        snr = get_snr(sonar_mode, env)
        pd  = calculate_pd(snr, mode["gamma"], mode["sigma"])
        pfa = calculate_pfa(mode["gamma"], mode["sigma"])
        res = check_feasibility(mode, snr, avail_energy)
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
    print("#  Integration Demo (Person 1 physics + Person 2 logic)")
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
