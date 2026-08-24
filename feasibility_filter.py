"""
feasibility_filter.py — Three-gate hard feasibility check for sonar modes.

Part of the Detection, Energy & Feasibility Logic module (SIH26058).

The feasibility check enforces THREE INDEPENDENT boolean gates:
    1. Pd  ≥  pd_min           (detection probability gate)
    2. Pfa ≤  pfa_max          (false-alarm probability gate)
    3. energy_cost ≤ available_energy   (energy budget gate)

A mode is feasible ONLY if ALL THREE pass.  A good score on one gate
CANNOT compensate for a failure on another — this is the core design
principle of the project (no weighted scores, no averaging).

Interface contract — do NOT change this signature:
    check_feasibility(mode, snr, available_energy,
                      pd_min=0.85, pfa_max=0.05) -> dict
"""

from detection_model import calculate_pd, calculate_pfa
from energy_model import get_energy_cost


def check_feasibility(
    mode: dict,
    snr: float,
    available_energy: float,
    pd_min: float = 0.85,
    pfa_max: float = 0.05,
) -> dict:
    """Run all three hard feasibility gates on a single mode.

    Each gate is evaluated INDEPENDENTLY.  The mode is feasible only if
    every gate passes.  If any gate fails, the corresponding rejection
    reason is recorded.

    Args:
        mode:             Mode dict (must have id, gamma, sigma, energy_cost).
        snr:              Signal-to-Noise Ratio in dB (from Person 1's
                          sonar_physics.get_snr).
        available_energy: Current energy budget in Joules (from Person 3).
        pd_min:           Minimum acceptable detection probability (default 0.85).
        pfa_max:          Maximum acceptable false-alarm probability (default 0.05).

    Returns:
        A result dict:
        {
            "mode_id":            str,
            "pd":                 float,
            "pfa":                float,
            "energy":             float,
            "pd_ok":              bool,
            "pfa_ok":             bool,
            "energy_ok":          bool,
            "feasible":           bool,        # True only if ALL three pass
            "rejection_reasons":  list[str],   # empty when feasible
        }
    """
    gamma = mode["gamma"]
    sigma = mode["sigma"]
    energy = get_energy_cost(mode)

    # --- Gate 1: Detection probability ---
    pd = calculate_pd(snr, gamma, sigma)
    pd_ok = pd >= pd_min

    # --- Gate 2: False-alarm probability ---
    # NOTE: Pfa depends ONLY on gamma and sigma, NOT on SNR.
    pfa = calculate_pfa(gamma, sigma)
    pfa_ok = pfa <= pfa_max

    # --- Gate 3: Energy budget ---
    energy_ok = energy <= available_energy

    # --- Collect rejection reasons ---
    rejection_reasons = []
    if not pd_ok:
        rejection_reasons.append("Pd below minimum")
    if not pfa_ok:
        rejection_reasons.append("Pfa exceeds maximum")
    if not energy_ok:
        rejection_reasons.append("energy exceeds available budget")

    return {
        "mode_id": mode["id"],
        "pd": pd,
        "pfa": pfa,
        "energy": energy,
        "pd_ok": pd_ok,
        "pfa_ok": pfa_ok,
        "energy_ok": energy_ok,
        "feasible": pd_ok and pfa_ok and energy_ok,
        "rejection_reasons": rejection_reasons,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("feasibility_filter.py -- self-test")
    print("=" * 60)

    from mode_library import get_all_modes

    modes = get_all_modes()
    test_snrs = {"M1": 6.0, "M2": 12.0, "M3": 18.0}
    available_energy = 1.0

    print(f"\n  Test conditions: available_energy = {available_energy} J")
    print(f"  Illustrative SNRs: {test_snrs}")
    print()

    results = []
    for mode in modes:
        snr = test_snrs[mode["id"]]
        result = check_feasibility(mode, snr, available_energy)
        results.append(result)

        status = "FEASIBLE" if result["feasible"] else "REJECTED"
        print(f"  {mode['id']} ({mode['name']:7s}): {status}")
        print(f"      Pd={result['pd']:.4f} (>=0.85? {result['pd_ok']})  "
              f"Pfa={result['pfa']:.4f} (<=0.05? {result['pfa_ok']})  "
              f"E={result['energy']:.1f}J (<={available_energy}? {result['energy_ok']})")
        if result["rejection_reasons"]:
            print(f"      Reasons: {result['rejection_reasons']}")
        print()

    # Verify worked example
    r_m1, r_m2, r_m3 = results

    assert not r_m1["feasible"], "M1 should be rejected"
    assert "Pd below minimum" in r_m1["rejection_reasons"], \
        "M1 should be rejected on Pd"
    print("  [OK] M1 correctly rejected on Pd.")

    assert r_m2["feasible"], "M2 should be feasible"
    assert r_m2["rejection_reasons"] == [], "M2 should have no rejections"
    print("  [OK] M2 correctly feasible (all gates pass).")

    assert not r_m3["feasible"], "M3 should be rejected"
    assert "energy exceeds available budget" in r_m3["rejection_reasons"], \
        "M3 should be rejected on energy"
    print("  [OK] M3 correctly rejected on energy.")

    # Verify independence: each gate is a simple boolean, no weighting
    # (a mode can't have "partially feasible" — it's all or nothing)
    assert isinstance(r_m1["pd_ok"], bool)
    assert isinstance(r_m1["pfa_ok"], bool)
    assert isinstance(r_m1["energy_ok"], bool)
    print("  [OK] All gates are independent boolean checks (no weighting).")

    print("\nAll feasibility_filter self-tests passed.\n")
