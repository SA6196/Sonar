"""
sonar_physics.py — PLACEHOLDER for Person 1's sonar/SNR module.

*** THIS IS A STAND-IN, NOT PERSON 1'S REAL WORK. ***

Person 1's actual module was not available at integration time. This file
implements the standard passive/active sonar equation just well enough to
drive Person 2's modules (detection_model / feasibility_filter /
mode_selector) end-to-end for the demo pipeline.

WHEN PERSON 1 DELIVERS THEIR REAL MODULE:
    Drop their file in as sonar_physics.py (same filename) and make sure it
    exposes a function with this exact signature:

        get_snr(range_m: float, noise_db: float, **kwargs) -> float

    returning SNR in dB. main.py only calls `get_snr(...)`, so as long as
    that function exists with a compatible signature, nothing else in the
    integration layer needs to change.

Formula used here (simple sonar equation, spherical spreading + absorption):

    TL(range) = 20*log10(range) + alpha * range        [transmission loss, dB]
    SNR       = SOURCE_LEVEL - TL(range) - noise_db     [dB]

This is a textbook simplification (no target strength term, no directivity
index) chosen only so the pipeline has believable, monotonic SNR-vs-range
and SNR-vs-noise behaviour for the demo scenarios. It is NOT a validated
underwater acoustics result and must not be presented as one.
"""

import math

# Documented placeholder constants (Joules/dB assumptions — NOT measured data)
SOURCE_LEVEL_DB = 90.0      # illustrative transmitted source level
ABSORPTION_COEFF = 0.02     # dB per metre, illustrative absorption loss
MIN_RANGE_M = 0.1           # avoid log(0)


def _transmission_loss(range_m: float) -> float:
    """Spherical spreading + absorption transmission loss, in dB."""
    r = max(range_m, MIN_RANGE_M)
    return 20.0 * math.log10(r) + ABSORPTION_COEFF * r



# Illustrative per-mode processing gain (dB).
#
# Rationale: M2/M3 use longer or more complex waveforms (more energy per
# ping) and correspondingly extract more processing gain from the same
# physical return, so the SAME physical scenario yields a HIGHER effective
# SNR for a higher-energy mode. This reproduces the intended demo story
# (M1/Scout is the first to lose detection in marginal conditions) without
# inventing a different physical model per mode. Keyed by mode "id" so it
# works directly with mode_library's mode dicts.
_MODE_PROCESSING_GAIN_DB = {
    "M1": 0.0,   # Scout   — shortest/cheapest ping, least processing gain
    "M2": 3.0,   # Search  — balanced
    "M3": 6.0,   # Inspect — longest/most expensive ping, most gain
}


def get_snr(range_m: float, noise_db: float, mode: dict = None, **kwargs) -> float:
    """Compute SNR (dB) for a given range, ambient noise, and (optionally) mode.

    Args:
        range_m:  Target range in metres.
        noise_db: Ambient/background noise level in dB.
        mode:     Optional mode dict (from mode_library). If provided, an
                  illustrative per-mode processing gain is added on top of
                  the base physical SNR (see _MODE_PROCESSING_GAIN_DB). If
                  omitted, the raw physical SNR is returned.
        **kwargs: Ignored — reserved so Person 1's real signature (which
                  may accept extra parameters like target strength) can be
                  swapped in without breaking callers that pass extra args.

    Returns:
        SNR in dB (can be negative in poor conditions — this is expected
        and correctly drives Pd down in detection_model).
    """
    tl = _transmission_loss(range_m)
    base_snr = SOURCE_LEVEL_DB - tl - noise_db

    if mode is None:
        return base_snr

    gain = _MODE_PROCESSING_GAIN_DB.get(mode.get("id"), 0.0)
    return base_snr + gain


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("sonar_physics.py (PLACEHOLDER) -- self-test")
    print("=" * 60)

    for r, n in [(5, 55), (32, 72), (60, 80)]:
        snr = get_snr(r, n)
        print(f"  range={r:5.1f} m  noise={n:5.1f} dB  ->  SNR = {snr:6.2f} dB")

    # Sanity: SNR should decrease as range increases (fixed noise)
    snr_close = get_snr(5, 60)
    snr_far = get_snr(50, 60)
    assert snr_close > snr_far, "SNR should fall with increasing range"
    print("\n  [OK] SNR decreases with range, as expected.")

    # Sanity: SNR should decrease as noise increases (fixed range)
    snr_quiet = get_snr(20, 40)
    snr_loud = get_snr(20, 80)
    assert snr_quiet > snr_loud, "SNR should fall with increasing noise"
    print("  [OK] SNR decreases with noise, as expected.")

    print("\nAll sonar_physics (placeholder) self-tests passed.\n")
