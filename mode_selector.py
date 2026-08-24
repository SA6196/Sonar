"""
mode_selector.py — Select the cheapest feasible mode, or degrade gracefully.

Part of the Detection, Energy & Feasibility Logic module (SIH26058).

Selection logic:
    1. From the feasibility results, collect all modes marked feasible=True.
    2. Among the feasible set, pick the one with the lowest energy_cost.
       → This is the argmin from the README:  a* = argmin_{a ∈ A_f} E(a)
    3. If NO mode is feasible, fall back to the lowest-energy mode from
       all_modes and flag degraded=True.  The system does NOT silently
       pretend sensing is reliable — it explicitly reports DEGRADED state.

Interface contract — do NOT change this signature:
    select_mode(feasibility_results: list[dict],
                all_modes: list[dict]) -> dict
"""


def select_mode(
    feasibility_results: list,
    all_modes: list,
) -> dict:
    """Pick the cheapest feasible mode, or fall back to degraded.

    Args:
        feasibility_results: List of dicts produced by
            feasibility_filter.check_feasibility() — one per mode evaluated.
            Each dict must have at least: mode_id, feasible, energy.
        all_modes: Complete list of mode dicts (from mode_library) — used
            only for the degraded fallback so we can find the cheapest
            mode regardless of feasibility.

    Returns:
        {
            "selected_mode_id": str,
            "degraded":         bool,
            "reason":           str,   # explanation shown on dashboard
        }
    """
    # --- Collect feasible modes ---
    feasible = [r for r in feasibility_results if r["feasible"]]

    if feasible:
        # Pick the cheapest feasible mode
        best = min(feasible, key=lambda r: r["energy"])
        return {
            "selected_mode_id": best["mode_id"],
            "degraded": False,
            "reason": (
                f"Mode {best['mode_id']} selected — lowest energy "
                f"({best['energy']:.2f} J) among "
                f"{len(feasible)} feasible mode(s)."
            ),
        }

    # --- No feasible mode: degraded fallback ---
    if not all_modes:
        # Defensive: should never happen in practice
        return {
            "selected_mode_id": "NONE",
            "degraded": True,
            "reason": "DEGRADED — no modes available at all.",
        }

    fallback = min(all_modes, key=lambda m: m["energy_cost"])

    # Build a summary of why each mode failed
    rejection_summary_parts = []
    for r in feasibility_results:
        if r["rejection_reasons"]:
            reasons_str = ", ".join(r["rejection_reasons"])
            rejection_summary_parts.append(f"{r['mode_id']}: {reasons_str}")

    rejection_summary = "; ".join(rejection_summary_parts) if rejection_summary_parts else "unknown"

    return {
        "selected_mode_id": fallback["id"],
        "degraded": True,
        "reason": (
            f"DEGRADED — no mode passed all feasibility gates. "
            f"Falling back to lowest-energy mode {fallback['id']} "
            f"({fallback['energy_cost']:.2f} J). "
            f"Rejections: {rejection_summary}"
        ),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("mode_selector.py -- self-test")
    print("=" * 60)

    from mode_library import get_all_modes
    from feasibility_filter import check_feasibility

    modes = get_all_modes()
    test_snrs = {"M1": 6.0, "M2": 12.0, "M3": 18.0}
    available_energy = 1.0

    # --- Scenario 1: Normal (worked example) ---
    print("\n  Scenario 1 -- Normal (range ~5 m, noise ~55 dB, battery = 1.0 J)")
    results = [check_feasibility(m, test_snrs[m["id"]], available_energy) for m in modes]
    selection = select_mode(results, modes)

    print(f"    Selected: {selection['selected_mode_id']}")
    print(f"    Degraded: {selection['degraded']}")
    print(f"    Reason:   {selection['reason']}")

    assert selection["selected_mode_id"] == "M2", \
        f"Expected M2, got {selection['selected_mode_id']}"
    assert selection["degraded"] is False, "Should not be degraded"
    print("    [OK] Correctly selected M2 (cheapest feasible).\n")

    # --- Scenario 2: Very low battery -- all modes should fail energy ---
    print("  Scenario 2 -- Very low battery (0.1 J)")
    results_low = [check_feasibility(m, test_snrs[m["id"]], 0.1) for m in modes]
    selection_low = select_mode(results_low, modes)

    print(f"    Selected: {selection_low['selected_mode_id']}")
    print(f"    Degraded: {selection_low['degraded']}")
    print(f"    Reason:   {selection_low['reason']}")

    assert selection_low["degraded"] is True, "Should be degraded with 0.1 J"
    assert selection_low["selected_mode_id"] == "M1", \
        "Fallback should be M1 (lowest energy)"
    print("    [OK] Correctly degraded; fell back to M1.\n")

    # --- Scenario 3: High battery, high SNR -- all feasible, pick cheapest ---
    print("  Scenario 3 -- High battery (10.0 J), high SNR (20 dB all modes)")
    results_good = [check_feasibility(m, 20.0, 10.0) for m in modes]
    selection_good = select_mode(results_good, modes)

    print(f"    Selected: {selection_good['selected_mode_id']}")
    print(f"    Degraded: {selection_good['degraded']}")
    print(f"    Reason:   {selection_good['reason']}")

    assert selection_good["selected_mode_id"] == "M1", \
        "With all feasible, should pick M1 (cheapest)"
    assert selection_good["degraded"] is False
    print("    [OK] Correctly selected M1 (cheapest when all are feasible).\n")

    print("All mode_selector self-tests passed.\n")
