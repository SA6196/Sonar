"""
mode_library.py — Sonar mode parameter definitions (M1 / M2 / M3).

Part of the Detection, Energy & Feasibility Logic module (SIH26058).

Each mode is a dict with the shape consumed by detection_model, energy_model,
feasibility_filter, and mode_selector — and also shared with Person 1
(sonar_physics.py) and Person 3 (dashboard.py / main.py).

Mode dict shape:
    {
        "id":          str,    # "M1", "M2", "M3"
        "name":        str,    # human-readable label
        "gamma":       float,  # detection threshold
        "sigma":       float,  # noise-distribution parameter
        "energy_cost": float,  # Joules per ping
    }

Parameter rationale (illustrative values chosen so the canonical worked
example at range ≈ 5 m, noise ≈ 55 dB, battery = 1.0 J reproduces):
    • M1 Scout  — low energy, but high gamma relative to its achievable SNR
                   ⇒ Pd falls below 0.85 in moderate conditions → rejected on Pd.
    • M2 Search — balanced; passes all three gates              → feasible.
    • M3 Inspect— excellent detection, but energy_cost > 1.0 J  → rejected on energy.
"""


# ---------------------------------------------------------------------------
# Mode definitions
# ---------------------------------------------------------------------------

MODE_M1 = {
    "id": "M1",
    "name": "Scout",
    "gamma": 5.0,
    "sigma": 1.5,
    "energy_cost": 0.3,
}

MODE_M2 = {
    "id": "M2",
    "name": "Search",
    "gamma": 5.5,
    "sigma": 2.0,
    "energy_cost": 0.7,
}

MODE_M3 = {
    "id": "M3",
    "name": "Inspect",
    "gamma": 4.5,
    "sigma": 2.5,
    "energy_cost": 1.5,
}


def get_all_modes() -> list:
    """Return a list of all available sonar mode dicts, ordered M1 → M3."""
    # Return fresh copies so callers cannot accidentally mutate the originals.
    return [dict(MODE_M1), dict(MODE_M2), dict(MODE_M3)]


def get_mode_by_id(mode_id: str) -> dict:
    """Look up a single mode by its id string ("M1", "M2", or "M3").

    Returns a copy of the mode dict, or raises ValueError if unknown.
    """
    for mode in (MODE_M1, MODE_M2, MODE_M3):
        if mode["id"] == mode_id:
            return dict(mode)
    raise ValueError(f"Unknown mode id: {mode_id!r}")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("mode_library.py — self-test")
    print("=" * 60)

    modes = get_all_modes()
    for m in modes:
        print(f"  {m['id']} ({m['name']:7s})  gamma={m['gamma']:.1f}  "
              f"sigma={m['sigma']:.1f}  E={m['energy_cost']:.1f} J")

    # Quick sanity: energy ordering M1 < M2 < M3
    assert modes[0]["energy_cost"] < modes[1]["energy_cost"] < modes[2]["energy_cost"], \
        "Energy ordering violated"
    print("\n  [OK] Energy ordering M1 < M2 < M3 confirmed.")

    # Round-trip by id
    m2 = get_mode_by_id("M2")
    assert m2["name"] == "Search"
    print("  [OK] get_mode_by_id('M2') round-trip OK.")

    print("\nAll mode_library self-tests passed.\n")
