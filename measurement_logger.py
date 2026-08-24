"""
measurement_logger.py — Person 3 (Integration, Logging & Dashboard).

Stores one MeasurementRecord per simulation step and can export the run
to CSV/JSON, plus compute simple summary statistics for the mission-end
report. Deliberately stdlib-only (dataclasses, csv, json, datetime) —
no database, per project scope.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MeasurementRecord:
    """One fully-integrated decision record for a single simulation step.

    Fields mirror what main.py's build_measurement_record() assembles from
    Person 1 (sonar_physics), Person 2 (detection_model / feasibility_filter
    / mode_selector), and the scenario/battery state Person 3 tracks.

    Any value that could not legitimately be produced by the upstream
    modules is stored as the string "N/A" rather than being invented.
    """

    step: int
    timestamp: str
    scenario: str

    battery_pct: float
    available_energy_j: float
    range_m: float
    noise_db: float

    # Per-mode detail, keyed by mode id -> dict (snr, pd, pfa, energy,
    # feasible, rejection_reasons). Stored as JSON text in CSV rows since
    # CSV is flat; full detail is preserved in the JSON export.
    mode_details: dict

    selected_mode: str
    degraded: bool
    selection_reason: str

    system_status: str  # "NORMAL" or "DEGRADED"

    # Convenience top-line figures for the selected mode (may be "N/A" if
    # no mode was selectable at all — should not normally happen since
    # mode_selector always returns a fallback, but guarded here anyway).
    selected_snr_db: object = "N/A"
    selected_pd: object = "N/A"
    selected_pfa: object = "N/A"
    selected_energy_j: object = "N/A"

    def to_flat_dict(self) -> dict:
        """Flatten for CSV writing (mode_details serialized as JSON text)."""
        d = asdict(self)
        d["mode_details"] = json.dumps(d["mode_details"])
        return d


class MeasurementLogger:
    """Small in-memory logger for one simulation run."""

    def __init__(self):
        self._records: list[MeasurementRecord] = []

    def log_measurement(self, record: MeasurementRecord) -> None:
        """Append a completed record to the run log."""
        self._records.append(record)

    def get_records(self) -> list[MeasurementRecord]:
        """Return all records logged so far (list of MeasurementRecord)."""
        return list(self._records)

    def clear(self) -> None:
        """Discard all logged records (e.g. before starting a new run)."""
        self._records.clear()

    def export_csv(self, path: str) -> str:
        """Write all records to a flat CSV file. Returns the path written."""
        if not self._records:
            # Still create an empty file with headers so downstream tooling
            # doesn't choke on a missing file.
            fieldnames = [f.name for f in fields(MeasurementRecord)]
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return path

        fieldnames = list(self._records[0].to_flat_dict().keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self._records:
                writer.writerow(r.to_flat_dict())
        return path

    def export_json(self, path: str) -> str:
        """Write all records (full detail, incl. nested mode_details) to JSON."""
        with open(path, "w") as f:
            json.dump([asdict(r) for r in self._records], f, indent=2)
        return path

    def summary_stats(self) -> dict:
        """Compute simple summary statistics over the logged run.

        Returns a dict with:
            total_decisions, feasible_decisions, rejected_decisions,
            normal_count, degraded_count,
            total_energy_j, average_energy_j,
            average_snr_db, average_pd, average_pfa   (over steps where
                a mode was actually selected with numeric values)
        """
        n = len(self._records)
        if n == 0:
            return {
                "total_decisions": 0,
                "feasible_decisions": 0,
                "rejected_decisions": 0,
                "normal_count": 0,
                "degraded_count": 0,
                "total_energy_j": 0.0,
                "average_energy_j": 0.0,
                "average_snr_db": "N/A",
                "average_pd": "N/A",
                "average_pfa": "N/A",
            }

        normal_count = sum(1 for r in self._records if r.system_status == "NORMAL")
        degraded_count = sum(1 for r in self._records if r.system_status == "DEGRADED")

        # "feasible" decision = at least one mode passed all gates that step
        feasible_count = sum(
            1 for r in self._records
            if any(m.get("feasible") for m in r.mode_details.values())
        )
        rejected_count = n - feasible_count

        energies = [r.selected_energy_j for r in self._records if isinstance(r.selected_energy_j, (int, float))]
        snrs = [r.selected_snr_db for r in self._records if isinstance(r.selected_snr_db, (int, float))]
        pds = [r.selected_pd for r in self._records if isinstance(r.selected_pd, (int, float))]
        pfas = [r.selected_pfa for r in self._records if isinstance(r.selected_pfa, (int, float))]

        return {
            "total_decisions": n,
            "feasible_decisions": feasible_count,
            "rejected_decisions": rejected_count,
            "normal_count": normal_count,
            "degraded_count": degraded_count,
            "total_energy_j": round(sum(energies), 4) if energies else 0.0,
            "average_energy_j": round(sum(energies) / len(energies), 4) if energies else "N/A",
            "average_snr_db": round(sum(snrs) / len(snrs), 3) if snrs else "N/A",
            "average_pd": round(sum(pds) / len(pds), 4) if pds else "N/A",
            "average_pfa": round(sum(pfas) / len(pfas), 4) if pfas else "N/A",
        }


def make_timestamp() -> str:
    """UTC timestamp string used for record.timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger = MeasurementLogger()

    rec = MeasurementRecord(
        step=1,
        timestamp=make_timestamp(),
        scenario="easy",
        battery_pct=90.0,
        available_energy_j=4.5,
        range_m=6.0,
        noise_db=60.0,
        mode_details={
            "M1": {"snr": 14.3, "pd": 1.0, "pfa": 0.0004, "energy": 0.3, "feasible": True, "rejection_reasons": []},
        },
        selected_mode="M1",
        degraded=False,
        selection_reason="Mode M1 selected — lowest energy (0.30 J) among 1 feasible mode(s).",
        system_status="NORMAL",
        selected_snr_db=14.3,
        selected_pd=1.0,
        selected_pfa=0.0004,
        selected_energy_j=0.3,
    )
    logger.log_measurement(rec)
    assert len(logger.get_records()) == 1
    print("[OK] log_measurement / get_records")

    stats = logger.summary_stats()
    assert stats["total_decisions"] == 1
    assert stats["normal_count"] == 1
    print("[OK] summary_stats:", stats)

    path = logger.export_csv("/tmp/_test_measurement_logger.csv")
    print(f"[OK] export_csv -> {path}")

    path_json = logger.export_json("/tmp/_test_measurement_logger.json")
    print(f"[OK] export_json -> {path_json}")

    logger.clear()
    assert len(logger.get_records()) == 0
    print("[OK] clear()")

    print("\nAll measurement_logger self-tests passed.\n")
