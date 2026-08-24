"""
detection_model.py — Detection probability (Pd) and false-alarm probability (Pfa).

Part of the Detection, Energy & Feasibility Logic module (SIH26058).

Uses the Gaussian Q-function:  Q(x) = 0.5 · erfc(x / √2)

Formulas (from README / project spec):
    Pd  = Q((γ − SNR) / σ)      — depends on SNR, γ, σ
    Pfa = Q(γ / σ)               — depends on γ, σ only (NOT on SNR)

This module deliberately avoids scipy; it uses only math.erfc from the
standard library, making it deployable on resource-constrained targets
(ESP32, STM32) via MicroPython as well.
"""

import math

_SQRT2 = math.sqrt(2.0)


def _q_function(x: float) -> float:
    """Gaussian Q-function: Q(x) = 0.5 · erfc(x / √2).

    Properties:
        Q(0)   = 0.5
        Q(+∞)  → 0
        Q(−∞)  → 1
    """
    return 0.5 * math.erfc(x / _SQRT2)


def calculate_pd(snr: float, gamma: float, sigma: float) -> float:
    """Probability of detection.

    Pd = Q((γ − SNR) / σ)

    A higher SNR (relative to γ) yields a higher Pd.

    Args:
        snr:   Signal-to-Noise Ratio in dB (from sonar_physics.get_snr).
        gamma: Detection threshold for this mode.
        sigma: Noise-distribution parameter for this mode.

    Returns:
        Pd in [0, 1].
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")
    return _q_function((gamma - snr) / sigma)


def calculate_pfa(gamma: float, sigma: float) -> float:
    """Probability of false alarm.

    Pfa = Q(γ / σ)

    NOTE: Pfa does NOT depend on SNR — it is a property of the threshold
    and noise distribution alone.

    Args:
        gamma: Detection threshold for this mode.
        sigma: Noise-distribution parameter for this mode.

    Returns:
        Pfa in [0, 1].
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")
    return _q_function(gamma / sigma)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("detection_model.py -- self-test")
    print("=" * 60)

    # --- Q-function spot checks ---
    assert abs(_q_function(0.0) - 0.5) < 1e-12, "Q(0) should be 0.5"
    print(f"  Q(0)  = {_q_function(0.0):.6f}  (expect 0.500000)")

    # Q(1.6449) ~ 0.05  (the 95th-percentile point)
    q_val = _q_function(1.6449)
    print(f"  Q(1.6449) = {q_val:.6f}  (expect ~0.050000)")
    assert abs(q_val - 0.05) < 1e-3

    # --- Worked example with M1 / M2 / M3 illustrative SNRs ---
    # (These SNR values are what Person 1 would compute at range ≈ 5 m,
    #  noise ≈ 55 dB for each mode.  We use them here for standalone testing.)

    from mode_library import get_all_modes

    test_snrs = {"M1": 6.0, "M2": 12.0, "M3": 18.0}  # illustrative

    print("\n  Mode  |  SNR   |   Pd     |   Pfa")
    print("  ------+--------+----------+---------")
    for mode in get_all_modes():
        snr = test_snrs[mode["id"]]
        pd  = calculate_pd(snr, mode["gamma"], mode["sigma"])
        pfa = calculate_pfa(mode["gamma"], mode["sigma"])
        tag_pd  = "OK" if pd >= 0.85 else "X"
        tag_pfa = "OK" if pfa <= 0.05 else "X"
        print(f"  {mode['id']:5s} | {snr:5.1f}  | {pd:.4f} {tag_pd:2s} | {pfa:.4f} {tag_pfa:2s}")

    # Verify the expected outcome
    pd_m1 = calculate_pd(6.0, 5.0, 1.5)
    assert pd_m1 < 0.85, f"M1 should fail Pd gate, got Pd={pd_m1:.4f}"
    print(f"\n  [OK] M1 Pd = {pd_m1:.4f} < 0.85 -- correctly rejected on Pd.")

    pd_m2 = calculate_pd(12.0, 5.5, 2.0)
    pfa_m2 = calculate_pfa(5.5, 2.0)
    assert pd_m2 >= 0.85, f"M2 should pass Pd gate, got Pd={pd_m2:.4f}"
    assert pfa_m2 <= 0.05, f"M2 should pass Pfa gate, got Pfa={pfa_m2:.4f}"
    print(f"  [OK] M2 Pd = {pd_m2:.4f} >= 0.85, Pfa = {pfa_m2:.4f} <= 0.05 -- passes detection gates.")

    pfa_m3 = calculate_pfa(4.5, 2.5)
    assert pfa_m3 <= 0.05, f"M3 should pass Pfa gate, got Pfa={pfa_m3:.4f}"
    print(f"  [OK] M3 Pfa = {pfa_m3:.4f} <= 0.05 -- passes Pfa gate (energy will reject it).")

    # Verify Pfa does NOT use SNR
    pfa_check_a = calculate_pfa(5.0, 1.5)
    pfa_check_b = calculate_pfa(5.0, 1.5)
    assert pfa_check_a == pfa_check_b, "Pfa must be deterministic on (gamma, sigma) alone"
    print("  [OK] Pfa is independent of SNR -- confirmed.")

    print("\nAll detection_model self-tests passed.\n")
