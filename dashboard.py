"""
dashboard.py — Person 3 (Integration, Logging & Dashboard).

Judge-facing visualization of a simulation run produced by main.py.

Primary path: Streamlit (rich, interactive — scenario picker, live tables,
timelines, event log). Falls back automatically to a matplotlib static
dashboard (saved as a PNG) if Streamlit isn't installed, so the demo never
blocks on a missing dependency.

Run (Streamlit):
    streamlit run dashboard.py

Run (matplotlib fallback, no Streamlit needed):
    python dashboard.py --scenario energy_limited
"""

from __future__ import annotations

import argparse
import sys

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

from main import run_scenario, SCENARIOS, PD_MIN, PFA_MAX


# ---------------------------------------------------------------------------
# Shared helpers (used by both Streamlit and matplotlib paths)
# ---------------------------------------------------------------------------

def build_mode_table_rows(record) -> list[dict]:
    """Build the mode-comparison table rows for one record."""
    rows = []
    for mode_id, d in record.mode_details.items():
        rows.append({
            "Mode": mode_id,
            "Energy (J)": d["energy"],
            "Pd": d["pd"],
            "Pfa": d["pfa"],
            "Feasible": "YES" if d["feasible"] else "NO",
            "Reason": ", ".join(d["rejection_reasons"]) if d["rejection_reasons"] else "—",
        })
    return rows


def build_event_log(records) -> list[str]:
    """Build a human-readable decision/event log across the whole run."""
    events = []
    for r in records:
        events.append(f"[{r.timestamp}] STEP {r.step} — target scenario state: "
                       f"range={r.range_m:.1f} m, noise={r.noise_db:.1f} dB, SNR(selected)={r.selected_snr_db}")
        for mode_id, d in r.mode_details.items():
            if not d["feasible"] and d["rejection_reasons"]:
                events.append(f"[{r.timestamp}] {mode_id} rejected — "
                               f"reason: {', '.join(d['rejection_reasons'])}")
        events.append(f"[{r.timestamp}] {r.selected_mode} selected — {r.selection_reason}")
        if r.degraded:
            events.append(f"[{r.timestamp}] SYSTEM STATUS: DEGRADED")
    return events


# ---------------------------------------------------------------------------
# Streamlit dashboard
# ---------------------------------------------------------------------------

def run_streamlit_dashboard():
    st.set_page_config(page_title="SIH26058 — Sonar Payload Dashboard", layout="wide")
    st.title("Low-Power Adaptive Sonar Transmitter — Mission Dashboard")
    st.caption("SIH26058 — Person 1 (SNR/Detection) → Person 2 (Feasibility/Selection) → Person 3 (Integration)")

    scenario_labels = {
        "easy": "Easy / Normal",
        "difficult": "Difficult Acoustic Environment",
        "energy_limited": "Energy-Limited",
    }

    col_a, col_b = st.columns([3, 1])
    with col_a:
        scenario_key = st.selectbox(
            "Demo scenario",
            options=list(SCENARIOS.keys()),
            format_func=lambda k: scenario_labels.get(k, k),
        )
    with col_b:
        run_clicked = st.button("Run Scenario", type="primary")

    state_key = f"_records_{scenario_key}"
    if run_clicked or state_key not in st.session_state:
        logger, stats = run_scenario(scenario_key, verbose=False)
        st.session_state[state_key] = logger.get_records()
        st.session_state[f"_stats_{scenario_key}"] = stats

    records = st.session_state.get(state_key, [])
    stats = st.session_state.get(f"_stats_{scenario_key}", {})

    if not records:
        st.info("Click **Run Scenario** to execute the pipeline.")
        return

    step_idx = st.slider("Simulation step", 1, len(records), len(records))
    record = records[step_idx - 1]

    # --- Current status row ---
    st.subheader(f"Step {record.step} — {record.scenario}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Battery", f"{record.battery_pct:.1f}%")
    c2.metric("Range", f"{record.range_m:.1f} m")
    c3.metric("Noise", f"{record.noise_db:.1f} dB")
    c4.metric("SNR (selected)", f"{record.selected_snr_db} dB" if record.selected_snr_db != "N/A" else "N/A")
    c5.metric("Pd (selected)", f"{record.selected_pd}" if record.selected_pd != "N/A" else "N/A")
    c6.metric("Pfa (selected)", f"{record.selected_pfa}" if record.selected_pfa != "N/A" else "N/A")

    status_color = "🟢" if record.system_status == "NORMAL" else "🟠"
    st.markdown(f"### {status_color} SYSTEM: **{record.system_status}**")
    st.markdown(f"**Selected mode: `{record.selected_mode}`**")
    st.markdown(f"> {record.selection_reason}")

    # --- Mode comparison table ---
    st.markdown("#### Mode comparison")
    st.table(build_mode_table_rows(record))
    st.caption(f"Gates used: Pd ≥ {PD_MIN}, Pfa ≤ {PFA_MAX}")

    # --- Timelines ---
    st.markdown("#### Mission timelines")
    t1, t2, t3 = st.columns(3)
    with t1:
        st.caption("Battery (%) vs step")
        st.line_chart({"battery_pct": [r.battery_pct for r in records]})
    with t2:
        st.caption("SNR (selected mode, dB) vs step")
        st.line_chart({
            "snr_db": [r.selected_snr_db if isinstance(r.selected_snr_db, (int, float)) else None for r in records]
        })
    with t3:
        st.caption("Selected mode per step")
        mode_to_num = {"M1": 1, "M2": 2, "M3": 3}
        st.line_chart({"mode": [mode_to_num.get(r.selected_mode, 0) for r in records]})
        st.caption("1 = M1 (Scout), 2 = M2 (Search), 3 = M3 (Inspect)")

    # --- Event log ---
    st.markdown("#### Decision / event log")
    with st.expander("Show full event log", expanded=False):
        for line in build_event_log(records):
            st.text(line)

    # --- Mission summary ---
    st.markdown("#### Mission summary")
    st.json(stats)


# ---------------------------------------------------------------------------
# Matplotlib fallback dashboard
# ---------------------------------------------------------------------------

def run_matplotlib_dashboard(scenario_key: str, out_path: str = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    logger, stats = run_scenario(scenario_key, verbose=False)
    records = logger.get_records()

    steps = [r.step for r in records]
    battery = [r.battery_pct for r in records]
    snr = [r.selected_snr_db if isinstance(r.selected_snr_db, (int, float)) else None for r in records]
    mode_to_num = {"M1": 1, "M2": 2, "M3": 3}
    modes_num = [mode_to_num.get(r.selected_mode, 0) for r in records]
    status_colors = ["tab:green" if r.system_status == "NORMAL" else "tab:orange" for r in records]

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(steps, battery, marker="o", color="tab:blue")
    axes[0].set_ylabel("Battery (%)")
    axes[0].set_title(f"Mission Timeline — {scenario_key}")
    axes[0].grid(alpha=0.3)

    axes[1].plot(steps, snr, marker="o", color="tab:purple")
    axes[1].set_ylabel("SNR selected (dB)")
    axes[1].grid(alpha=0.3)

    axes[2].scatter(steps, modes_num, c=status_colors, s=60, zorder=3)
    axes[2].plot(steps, modes_num, color="gray", alpha=0.4, zorder=1)
    axes[2].set_yticks([1, 2, 3])
    axes[2].set_yticklabels(["M1 Scout", "M2 Search", "M3 Inspect"])
    axes[2].set_ylabel("Selected mode")
    axes[2].set_xlabel("Simulation step")
    axes[2].grid(alpha=0.3)

    green_patch = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="tab:green", label="NORMAL", markersize=8)
    orange_patch = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="tab:orange", label="DEGRADED", markersize=8)
    axes[2].legend(handles=[green_patch, orange_patch], loc="upper right")

    plt.tight_layout()

    if out_path is None:
        out_path = f"/mnt/user-data/outputs/{scenario_key}_dashboard.png"
    try:
        plt.savefig(out_path, dpi=140)
    except FileNotFoundError:
        out_path = f"{scenario_key}_dashboard.png"
        plt.savefig(out_path, dpi=140)
    plt.close(fig)

    print(f"Matplotlib dashboard saved -> {out_path}")
    print("\nMission summary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\nMode comparison (final step):")
    last = records[-1]
    for row in build_mode_table_rows(last):
        print(f"  {row}")

    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SIH26058 dashboard (matplotlib fallback CLI)")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="easy")
    parser.add_argument("--out", default=None, help="Output PNG path")
    args = parser.parse_args()
    run_matplotlib_dashboard(args.scenario, args.out)


if _HAS_STREAMLIT and "streamlit" in sys.modules and st.runtime.exists():
    # Running under `streamlit run dashboard.py`
    run_streamlit_dashboard()
elif __name__ == "__main__":
    if _HAS_STREAMLIT:
        print("Streamlit is installed but this script was run with plain `python`.")
        print("For the interactive dashboard run:\n    streamlit run dashboard.py")
        print("Falling back to the matplotlib static dashboard for this invocation.\n")
    main()
