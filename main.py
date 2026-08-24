"""
main.py — Person 3 (Integration, Logging & Dashboard).

Orchestrates the pipeline for SIH26058:

    scenario/state
        -> sonar_physics.get_snr()            (Person 1 — placeholder)
        -> feasibility_filter.check_feasibility()  (Person 2, per mode)
        -> mode_selector.select_mode()             (Person 2)
        -> build_measurement_record()              (Person 3, this file)
        -> logger.log_measurement()                (Person 3)
        -> print_status()                          (Person 3)

This file does NOT re-implement any physics or selection logic — it only
calls Person 1 / Person 2's functions and wires the results together.

Run:
    python main.py --scenario easy
    python main.py --scenario difficult
    python main.py --scenario energy_limited
    python main.py --scenario easy --export-json
"""

from __future__ import annotations

import argparse
import sys

from mode_library import get_all_modes
from feasibility_filter import check_feasibility
from mode_selector import select_mode
from sonar_physics import get_snr, SonarMode  # Person 1's real module
from environment import Environment

from measurement_logger import MeasurementLogger, MeasurementRecord, make_timestamp


# ---------------------------------------------------------------------------
# SonarMode mapping (bridges Person 2's mode dicts with Person 1's SonarMode)
# ---------------------------------------------------------------------------
# Person 1's get_snr expects a SonarMode with source_level_db and
# directivity_index_db.  Person 2's mode dicts have gamma/sigma/energy_cost.
# This mapping lives HERE in the integration layer so neither Person 1 nor
# Person 2 has to know about the other's internal types.

SONAR_MODES = {
    "M1": SonarMode("M1-Scout",   source_level_db=140, directivity_index_db=10),
    "M2": SonarMode("M2-Search",  source_level_db=160, directivity_index_db=15),
    "M3": SonarMode("M3-Inspect", source_level_db=180, directivity_index_db=20),
}


# ---------------------------------------------------------------------------
# Assumptions owned by the integration layer (documented, not hidden)
# ---------------------------------------------------------------------------

# The AUV's usable sonar energy budget for this demo. Person 2's modules
# work in Joules (mode "energy_cost" fields); Person 3 tracks battery as a
# percentage for the dashboard/story. This constant is the only place that
# converts between the two. It is an illustrative assumption, not a
# measured spec, and is documented here for that reason.
BATTERY_CAPACITY_J = 20.0

PD_MIN = 0.85
PFA_MAX = 0.05


def battery_pct_to_available_energy_j(battery_pct: float) -> float:
    """Convert battery percentage to available energy budget in Joules."""
    return max(0.0, battery_pct) / 100.0 * BATTERY_CAPACITY_J


def energy_j_to_battery_pct(energy_j: float) -> float:
    """Convert a Joule quantity back to an equivalent battery percentage."""
    return energy_j / BATTERY_CAPACITY_J * 100.0


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------
#
# These are demonstration presets, NOT claims about real-world measured
# sonar performance. Each scenario is a list of per-step (range_m, noise_db)
# environmental states. Battery is simulated statefully by the loop below
# (it depletes according to whichever mode actually gets selected), so it
# is defined here only as a starting percentage + optional per-step idle
# drain.

def scenario_easy() -> dict:
    """SCENARIO 1 — Easy / Normal.

    Good acoustic conditions (short range, moderate noise) and ample
    battery. All modes should pass detection; the selector should be free
    to pick the cheapest feasible mode.
    """
    steps = [
        {"range_m": 5.0, "noise_db": 58.0},
        {"range_m": 6.0, "noise_db": 60.0},
        {"range_m": 6.0, "noise_db": 59.0},
        {"range_m": 7.0, "noise_db": 61.0},
        {"range_m": 6.0, "noise_db": 60.0},
        {"range_m": 5.5, "noise_db": 58.5},
        {"range_m": 6.5, "noise_db": 60.5},
        {"range_m": 6.0, "noise_db": 59.5},
    ]
    return {
        "name": "EASY / NORMAL",
        "key": "easy",
        "start_battery_pct": 90.0,
        "idle_drain_pct_per_step": 0.1,
        "steps": steps,
    }


def scenario_difficult() -> dict:
    """SCENARIO 2 — Difficult acoustic environment.

    Range held roughly constant (~18 m); noise oscillates through a band
    that straddles the feasibility boundary for these mode parameters, so
    the run should show a genuine mix of:
        - NORMAL steps where only the highest-gain mode (M3) is feasible,
        - DEGRADED steps where no mode clears the Pd gate at all.
    Battery starts high so energy is deliberately NOT the limiting factor
    here — this scenario is about the acoustic environment, not power.
    """
    noise_pattern = [58, 60, 62, 63, 64, 62, 60, 58, 61, 63, 65, 62]
    steps = [{"range_m": 18.0, "noise_db": float(n)} for n in noise_pattern]
    return {
        "name": "DIFFICULT ACOUSTIC ENVIRONMENT",
        "key": "difficult",
        "start_battery_pct": 88.0,
        "idle_drain_pct_per_step": 0.1,
        "steps": steps,
    }


def scenario_energy_limited() -> dict:
    """SCENARIO 3 — Energy-limited (the central novelty demo).

    Acoustic conditions are kept GOOD throughout (short range, moderate
    noise — like scenario 1) so detection is never the bottleneck. Battery
    starts low and is spent down by whichever mode gets selected each
    step, so the story is purely about the energy gate:
        HIGH_RES rejected on energy -> cheaper feasible mode selected
        -> mission continues instead of draining the battery.
    Given enough steps the battery should eventually drop low enough that
    even the lowest-energy mode is rejected, demonstrating the full
    DEGRADED / "no feasible mode" fallback.
    """
    steps = [{"range_m": 6.0, "noise_db": 60.0} for _ in range(16)]
    return {
        "name": "ENERGY-LIMITED",
        "key": "energy_limited",
        "start_battery_pct": 6.0,
        "idle_drain_pct_per_step": 0.15,
        "steps": steps,
    }


SCENARIOS = {
    "easy": scenario_easy,
    "difficult": scenario_difficult,
    "energy_limited": scenario_energy_limited,
}


# ---------------------------------------------------------------------------
# Integration layer
# ---------------------------------------------------------------------------

def run_step(step_idx: int, scenario_name: str, state: dict, battery_pct: float,
             all_modes: list) -> MeasurementRecord:
    """Run one full timestep of the pipeline and return the measurement record.

    Calls Person 1 (get_snr, once per mode) and Person 2 (check_feasibility
    per mode, then select_mode) without altering their logic.
    """
    range_m = state["range_m"]
    noise_db = state["noise_db"]
    available_energy_j = battery_pct_to_available_energy_j(battery_pct)

    # Build an Environment object for Person 1's get_snr
    env_obj = Environment(
        target_range_m=range_m,
        noise_level_db=noise_db,
        battery_j=battery_pct / 100.0 * BATTERY_CAPACITY_J,
    )

    feasibility_results = []
    mode_details = {}

    for mode in all_modes:
        # Person 1: SNR for this mode under this environment.
        sonar_mode = SONAR_MODES[mode["id"]]
        snr_db = get_snr(sonar_mode, env_obj)

        # Person 2: three-gate feasibility check. Interface untouched.
        result = check_feasibility(
            mode, snr_db, available_energy_j, pd_min=PD_MIN, pfa_max=PFA_MAX
        )
        feasibility_results.append(result)

        mode_details[mode["id"]] = {
            "snr": round(snr_db, 3),
            "pd": round(result["pd"], 4),
            "pfa": round(result["pfa"], 4),
            "energy": round(result["energy"], 3),
            "feasible": result["feasible"],
            "rejection_reasons": result["rejection_reasons"],
        }

    # Person 2: pick cheapest feasible mode, or degrade gracefully.
    selection = select_mode(feasibility_results, all_modes)

    selected_id = selection["selected_mode_id"]
    degraded = selection["degraded"]
    system_status = "DEGRADED" if degraded else "NORMAL"

    selected_detail = mode_details.get(selected_id)
    if selected_detail is not None:
        selected_snr = selected_detail["snr"]
        selected_pd = selected_detail["pd"]
        selected_pfa = selected_detail["pfa"]
        selected_energy = selected_detail["energy"]
    else:
        # Defensive only — mode_selector always returns an id present in
        # all_modes/feasibility_results in current Person 2 code.
        selected_snr = selected_pd = selected_pfa = selected_energy = "N/A"

    record = MeasurementRecord(
        step=step_idx,
        timestamp=make_timestamp(),
        scenario=scenario_name,
        battery_pct=round(battery_pct, 2),
        available_energy_j=round(available_energy_j, 3),
        range_m=range_m,
        noise_db=noise_db,
        mode_details=mode_details,
        selected_mode=selected_id,
        degraded=degraded,
        selection_reason=selection["reason"],
        system_status=system_status,
        selected_snr_db=selected_snr,
        selected_pd=selected_pd,
        selected_pfa=selected_pfa,
        selected_energy_j=selected_energy,
    )
    return record


def print_status(record: MeasurementRecord, scenario_label: str) -> None:
    """Concise, judge-readable terminal status block for one step."""
    print("-" * 60)
    print(f"STEP {record.step} | {scenario_label}")
    print(f"Battery: {record.battery_pct:.1f}%   (available energy: {record.available_energy_j:.2f} J)")
    print(f"Range: {record.range_m:.1f} m")
    print(f"Noise: {record.noise_db:.1f} dB")
    print()

    for mode_id, d in record.mode_details.items():
        status = "FEASIBLE" if d["feasible"] else "REJECTED"
        print(f"{mode_id}:")
        print(f"  SNR: {d['snr']:.1f} dB   Pd: {d['pd']:.2f}   Pfa: {d['pfa']:.4f}")
        print(f"  Energy: {d['energy']:.2f} J   Status: {status}")
        if d["rejection_reasons"]:
            print(f"  Reason: {', '.join(d['rejection_reasons'])}")
        print()

    print(f"SELECTED: {record.selected_mode}")
    print(f"  -> {record.selection_reason}")
    print(f"SYSTEM: {record.system_status}")
    print("-" * 60)


def run_scenario(scenario_key: str, verbose: bool = True,
                  export_json: bool = False) -> tuple[MeasurementLogger, dict]:
    """Run one full scenario end-to-end and return (logger, summary_stats)."""
    if scenario_key not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_key}'. Choose from: {list(SCENARIOS)}")

    scenario = SCENARIOS[scenario_key]()
    all_modes = get_all_modes()
    logger = MeasurementLogger()

    battery_pct = scenario["start_battery_pct"]
    idle_drain = scenario.get("idle_drain_pct_per_step", 0.0)

    for i, state in enumerate(scenario["steps"], start=1):
        record = run_step(i, scenario["name"], state, battery_pct, all_modes)
        logger.log_measurement(record)

        if verbose:
            print_status(record, scenario["name"])

        # Deplete battery for the NEXT step based on the energy actually
        # spent this step (selected mode's cost) plus a small idle drain
        # for housekeeping/sensors. This makes battery state genuinely
        # stateful across the run rather than a fixed per-scenario value.
        consumed_j = record.selected_energy_j if isinstance(record.selected_energy_j, (int, float)) else 0.0
        battery_pct -= energy_j_to_battery_pct(consumed_j) + idle_drain
        battery_pct = max(0.0, battery_pct)

    stats = logger.summary_stats()

    print("\n" + "=" * 60)
    print(f"MISSION SUMMARY — {scenario['name']}")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    csv_path = f"/mnt/user-data/outputs/{scenario_key}_run.csv"
    try:
        logger.export_csv(csv_path)
        if verbose:
            print(f"\nCSV exported -> {csv_path}")
    except FileNotFoundError:
        # Fallback for local/dev runs outside the sandboxed outputs dir.
        csv_path = f"{scenario_key}_run.csv"
        logger.export_csv(csv_path)
        if verbose:
            print(f"\nCSV exported -> {csv_path}")

    if export_json:
        json_path = csv_path.replace(".csv", ".json")
        logger.export_json(json_path)
        if verbose:
            print(f"JSON exported -> {json_path}")

    return logger, stats


def main():
    parser = argparse.ArgumentParser(description="SIH26058 sonar payload — demo runner")
    parser.add_argument(
        "--scenario", choices=list(SCENARIOS.keys()), default="easy",
        help="Which demo scenario to run.",
    )
    parser.add_argument(
        "--export-json", action="store_true",
        help="Also export the run as JSON (in addition to CSV).",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-step terminal output (summary still printed).",
    )
    args = parser.parse_args()

    run_scenario(args.scenario, verbose=not args.quiet, export_json=args.export_json)


if __name__ == "__main__":
    sys.exit(main() or 0)
