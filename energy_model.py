"""
energy_model.py — Energy cost lookup and utilities for sonar modes.

Part of the Detection, Energy & Feasibility Logic module (SIH26058).

Each mode dict already carries an "energy_cost" field (Joules per ping).
This module provides helper functions that the feasibility_filter and
mode_selector can use, keeping energy logic in one place.

Design notes:
    • Pure functions, no global state, no I/O.
    • energy_cost is a property of the mode, not the environment.
    • The feasibility gate compares energy_cost against available_energy
      (which comes from Person 3 at runtime — we never hardcode it here).
"""


def get_energy_cost(mode: dict) -> float:
    """Return the energy cost (Joules) for a given mode dict.

    Args:
        mode: A mode dict with at least an "energy_cost" key.

    Returns:
        Energy cost in Joules.

    Raises:
        KeyError: If the mode dict is missing the "energy_cost" field.
    """
    return mode["energy_cost"]


def check_energy_budget(mode: dict, available_energy: float) -> bool:
    """Check whether a mode's energy cost fits within the available budget.

    Args:
        mode:             A mode dict with an "energy_cost" key.
        available_energy: Current energy budget in Joules.

    Returns:
        True if energy_cost ≤ available_energy, False otherwise.
    """
    return get_energy_cost(mode) <= available_energy


def sort_modes_by_energy(modes: list, ascending: bool = True) -> list:
    """Return a new list of mode dicts sorted by energy_cost.

    Does NOT mutate the input list.

    Args:
        modes:     List of mode dicts.
        ascending: If True (default), cheapest first.

    Returns:
        Sorted list of mode dicts (shallow copies of the originals).
    """
    return sorted(modes, key=lambda m: m["energy_cost"], reverse=not ascending)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("energy_model.py -- self-test")
    print("=" * 60)

    from mode_library import get_all_modes

    modes = get_all_modes()

    print("\n  Energy costs:")
    for m in modes:
        cost = get_energy_cost(m)
        print(f"    {m['id']} ({m['name']:7s}): {cost:.1f} J")

    # Budget check at 1.0 J
    available = 1.0
    print(f"\n  Budget check with available_energy = {available} J:")
    for m in modes:
        ok = check_energy_budget(m, available)
        symbol = "OK" if ok else "X"
        print(f"    {m['id']}: {get_energy_cost(m):.1f} J <= {available} J ? {symbol}")

    # M1 and M2 should fit, M3 should not
    assert check_energy_budget(modes[0], available) is True,  "M1 should fit in 1.0 J"
    assert check_energy_budget(modes[1], available) is True,  "M2 should fit in 1.0 J"
    assert check_energy_budget(modes[2], available) is False, "M3 should NOT fit in 1.0 J"
    print("  [OK] M1, M2 within budget; M3 exceeds -- correct.")

    # Sorting
    sorted_modes = sort_modes_by_energy(modes)
    ids_sorted = [m["id"] for m in sorted_modes]
    assert ids_sorted == ["M1", "M2", "M3"], f"Expected [M1, M2, M3], got {ids_sorted}"
    print("  [OK] sort_modes_by_energy ascending order correct.")

    print("\nAll energy_model self-tests passed.\n")
