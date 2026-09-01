import math
import time
from typing import Any, Dict, Optional

import numpy as np
from scipy import signal
from scipy.stats import norm

EPS = 1e-12


def _safe_float(x: float) -> float:
    return float(np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0))


def _prepare_input(samples, adc_full_scale: Optional[float] = None):
    """Convert incoming data to a DSP-friendly normalized scale.

    Real ADC count data MUST provide an explicit full-scale value. This avoids
    guessing between 10-bit and 12-bit ranges from the observed block maximum.
    If ``adc_full_scale`` is omitted, the block is treated as already scaled.
    """
    raw = np.asarray(samples, dtype=float)
    if raw.ndim != 1 or raw.size < 32:
        raise ValueError("A one-dimensional block of at least 32 samples is required")
    if not np.all(np.isfinite(raw)):
        raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)

    if adc_full_scale is None:
        return raw.copy(), {"input_scaled": False, "input_scale": 1.0, "adc_full_scale": None}

    scale = float(adc_full_scale)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("adc_full_scale must be a positive finite value")
    return raw / scale, {"input_scaled": True, "input_scale": scale, "adc_full_scale": scale}


def _hampel(x: np.ndarray, window: int = 11, n_sigma: float = 6.0):
    """Conservative impulse suppression.

    A normal Hampel filter can mistake a rapidly changing sonar sinusoid for an
    outlier. A sample is therefore replaced only when it is both a strong local
    outlier and extreme relative to the whole block.
    """
    x = np.asarray(x, dtype=float).copy()
    n = len(x)
    outlier_mask = np.zeros(n, dtype=bool)
    if n < 7:
        return x, outlier_mask

    global_med = np.median(x)
    global_sigma = 1.4826 * np.median(np.abs(x - global_med)) + EPS
    k = max(1, window // 2)
    for i in range(n):
        lo = max(0, i - k)
        hi = min(n, i + k + 1)
        w = x[lo:hi]
        med = np.median(w)
        mad = np.median(np.abs(w - med))
        local_sigma = 1.4826 * mad + EPS
        deviation = abs(x[i] - med)
        if deviation > n_sigma * local_sigma and abs(x[i] - global_med) > 5.0 * global_sigma:
            x[i] = med
            outlier_mask[i] = True
    return x, outlier_mask


def _sos_filter(x: np.ndarray, fs: float, cutoff: float):
    """Zero-phase Butterworth band-pass with bounds safe for the sample rate."""
    nyq = fs / 2.0
    hp = max(30.0, min(300.0, nyq * 0.01))
    lp = min(max(cutoff, hp * 2.0), nyq * 0.95)
    if lp <= hp * 1.05:
        lp = min(nyq * 0.95, hp * 1.5)
    sos = signal.butter(6, [hp / nyq, lp / nyq], btype="bandpass", output="sos")
    if len(x) > 3 * (2 * len(sos) + 1):
        return signal.sosfiltfilt(sos, x), hp, lp
    return signal.sosfilt(sos, x), hp, lp


def _adaptive_notch(x: np.ndarray, fs: float):
    """Apply a 50/60 Hz notch only when the block can actually resolve mains.

    At 50 kHz a 500-sample block is only 10 ms long, so 50/60 Hz cannot be
    reliably resolved. Skipping the notch avoids false selections caused by
    spectral leakage. Longer blocks use a side-band prominence test.
    """
    if len(x) < 64 or len(x) / fs < 0.08:
        return x, None

    f, p = signal.welch(x, fs=fs, nperseg=min(1024, len(x)))
    chosen = None
    best_ratio = 0.0
    for mains in (50.0, 60.0):
        if mains >= fs / 2.0 * 0.9:
            continue
        idx = int(np.argmin(np.abs(f - mains)))
        if idx == 0 or idx >= len(p) - 1:
            continue
        side = np.concatenate([p[max(0, idx - 3):idx], p[idx + 1:min(len(p), idx + 4)]])
        if side.size == 0:
            continue
        ratio = float(p[idx] / (np.median(side) + EPS))
        if ratio > 8.0 and ratio > best_ratio:
            chosen = mains
            best_ratio = ratio

    if chosen is None:
        return x, None
    b, a = signal.iirnotch(chosen, Q=30.0, fs=fs)
    if len(x) > 3 * max(len(a), len(b)):
        return signal.filtfilt(b, a, x), chosen
    return signal.lfilter(b, a, x), chosen


def _spectrum(x: np.ndarray, fs: float):
    n = len(x)
    window = signal.windows.hann(n, sym=False)
    coherent_gain = np.sum(window) / n
    X = np.fft.rfft(x * window)
    mag = np.abs(X) / max(n * coherent_gain, EPS)
    if len(mag) > 2:
        mag[1:-1] *= 2.0
    freq = np.fft.rfftfreq(n, 1.0 / fs)
    return freq, mag


def _noise_floor(freq: np.ndarray, mag: np.ndarray, peak_idx: int, hp: float, lp: float):
    """Robust in-band spectral floor excluding the dominant peak neighbourhood."""
    if len(mag) <= 2:
        return float(np.median(mag))
    keep = (freq >= hp) & (freq <= lp)
    keep[0] = False
    lo = max(1, peak_idx - 2)
    hi = min(len(mag), peak_idx + 3)
    keep[lo:hi] = False
    floor_bins = mag[keep]
    if floor_bins.size < 4:
        fallback = (freq > 0) & (freq <= lp)
        fallback[lo:hi] = False
        floor_bins = mag[fallback]
    return float(np.median(floor_bins) + EPS)


def _bandwidth(freq: np.ndarray, mag: np.ndarray, peak_idx: int):
    if len(mag) < 3 or peak_idx <= 0:
        return 0.0
    peak = mag[peak_idx]
    if peak <= EPS:
        return 0.0
    threshold = peak / math.sqrt(2.0)
    left = peak_idx
    right = peak_idx
    while left > 0 and mag[left] >= threshold:
        left -= 1
    while right < len(mag) - 1 and mag[right] >= threshold:
        right += 1
    return float(max(0.0, freq[right] - freq[left]))


def _detection_window(x: np.ndarray, threshold: float):
    env = np.abs(signal.hilbert(x)) if len(x) >= 8 else np.abs(x)
    # Threshold is amplitude based, but require a clear rise above robust noise.
    noise_med = float(np.median(env))
    noise_sigma = float(1.4826 * np.median(np.abs(env - noise_med)) + EPS)
    gate = max(float(threshold), noise_med + 3.0 * noise_sigma)
    mask = env >= gate
    if not np.any(mask):
        return None, env

    # Keep the longest contiguous echo region rather than spanning unrelated peaks.
    idx = np.flatnonzero(mask)
    splits = np.where(np.diff(idx) > 1)[0] + 1
    groups = np.split(idx, splits)
    best = max(groups, key=len)
    pad = max(1, int(0.01 * len(x)))
    start = max(0, int(best[0]) - pad)
    end = min(len(x) - 1, int(best[-1]) + pad)
    n = max(1, len(x) - 1)
    return {"start": float(start / n), "end": float(end / n)}, env


def _roc_from_dprime(dprime: float):
    """Gaussian Neyman-Pearson ROC using the same d' model as frame Pd/Pfa."""
    pfa = np.logspace(-4, -0.01, 40)
    z = norm.isf(pfa)
    pd = norm.sf(z - max(0.0, float(dprime)))
    pd = np.clip(pd, 0.0, 1.0)
    return [{"pfa": float(a), "pd": float(b)} for a, b in zip(pfa, pd)]


def _decision(pd: float, pfa: float, detected: bool, battery: float, override: Optional[str]):
    capacity = 5.0
    energy_remaining = battery * capacity
    reserve = 1.2
    tier1_cost = 0.31
    tier2_cost = 1.48
    tier1_sufficient = detected and pd >= 0.85 and pfa <= 0.05
    tier2_feasible = energy_remaining - tier2_cost >= reserve

    if override is not None:
        mode = override
        reason = f"Manual sensing-mode override: {override}."
    elif tier1_sufficient:
        mode = "TIER1"
        reason = f"Tier 1 sufficient: Pd={pd:.3f}, Pfa={pfa:.5f}; no escalation required."
    elif tier2_feasible:
        mode = "TIER2"
        reason = f"Tier 1 confidence insufficient; Tier 2 feasible with {energy_remaining - tier2_cost:.2f} J remaining after escalation."
    else:
        mode = "DEGRADED"
        reason = f"Tier 2 blocked by energy reserve: post-escalation energy would be {energy_remaining - tier2_cost:.2f} J."

    return {
        "battery": float(battery),
        "energy_remaining": energy_remaining,
        "energy_reserve": reserve,
        "tier1_cost": tier1_cost,
        "tier2_cost": tier2_cost,
        "current_mode": mode,
        "tier2_feasible": tier2_feasible,
        "decision_reason": reason,
    }


def process_block(samples, sampling_rate: float, battery_level: float, detection_threshold: float, filter_cutoff: float, timestamp: Optional[int] = None, mode_override: Optional[str] = None, adc_full_scale: Optional[float] = None) -> Dict[str, Any]:
    raw_display = np.asarray(samples, dtype=float)
    raw, input_meta = _prepare_input(raw_display, adc_full_scale=adc_full_scale)
    fs = float(sampling_rate)
    if fs <= 1000:
        raise ValueError("sampling_rate must be greater than 1000 Hz")

    # 1) Conservative impulse suppression.
    despiked, outliers = _hampel(raw, window=11, n_sigma=6.0)

    # 2) Robust DC removal, followed by linear detrending.
    dc_offset = float(np.median(despiked))
    centered = despiked - dc_offset
    detrended = signal.detrend(centered, type="linear")

    # 3) Adaptive mains notch only when the block duration can support it.
    notched, notch_freq = _adaptive_notch(detrended, fs)

    # 4) Main sonar band-pass. No Savitzky-Golay stage: it can attenuate a
    # short high-frequency echo and is therefore intentionally disabled.
    processed, hp, lp = _sos_filter(notched, fs, filter_cutoff)

    n = len(processed)
    rms = float(np.sqrt(np.mean(processed ** 2)))
    peak = float(np.max(np.abs(processed)))
    peak_to_peak = float(np.ptp(processed))
    variance = float(np.var(processed))
    noise_floor_time = float(1.4826 * np.median(np.abs(processed - np.median(processed))))

    freq, mag = _spectrum(processed, fs)
    in_band = np.flatnonzero((freq >= hp) & (freq <= lp))
    valid = in_band if in_band.size else (np.arange(1, len(mag)) if len(mag) > 1 else np.arange(len(mag)))
    peak_idx = int(valid[np.argmax(mag[valid])]) if len(valid) else 0
    dominant_frequency = float(freq[peak_idx]) if len(freq) else 0.0
    spectral_noise_floor = _noise_floor(freq, mag, peak_idx, hp, lp)
    bandwidth = _bandwidth(freq, mag, peak_idx)
    spectral_energy = float(np.sum(mag ** 2))

    signal_amp = float(mag[peak_idx]) if len(mag) else 0.0
    snr = 20.0 * math.log10(max(signal_amp, EPS) / max(spectral_noise_floor, EPS))

    window, envelope = _detection_window(processed, detection_threshold)

    # One coherent statistical model for frame Pd, Pfa and ROC. We model the
    # normalized spectral amplitude statistic with a Gaussian NP approximation.
    # d' is the observed dominant-bin amplitude relative to the robust in-band
    # noise floor; the decision threshold is fixed at 3 sigma.
    dprime = float(max(signal_amp, EPS) / max(spectral_noise_floor, EPS))
    detection_z_threshold = 3.0
    pfa = float(norm.sf(detection_z_threshold))
    pd = float(norm.sf(detection_z_threshold - dprime))
    roc = _roc_from_dprime(dprime)

    detected = bool(window is not None and peak >= detection_threshold and dprime >= detection_z_threshold)
    confidence = float(np.clip(pd if detected else 0.5 * pd, 0.0, 0.999))
    decision = _decision(pd, pfa, detected, battery_level, mode_override)

    return {
        "timestamp": int(timestamp if timestamp is not None else time.time() * 1000),
        "sampling_rate": fs,
        "block_size": int(n),
        "samples": [float(v) for v in raw_display],
        "processed": [float(v) for v in processed],
        "dc_offset": dc_offset,
        "spectrum": [{"freq": float(f), "magnitude": float(m)} for f, m in zip(freq, mag)],
        "spectral_noise_floor": spectral_noise_floor,
        "rms": rms,
        "peak": peak,
        "peak_to_peak": peak_to_peak,
        "variance": variance,
        "noise_floor": noise_floor_time,
        "snr": float(snr),
        "dominant_frequency": dominant_frequency,
        "bandwidth": bandwidth,
        "spectral_energy": spectral_energy,
        "dprime": dprime,
        "detection_z_threshold": detection_z_threshold,
        "detected": detected,
        "confidence": float(confidence),
        "detection_threshold": float(detection_threshold),
        "detection_window": window,
        "pd": pd,
        "pfa": pfa,
        "roc": roc,
        "filter_metadata": {
            "hampel_outliers": int(np.sum(outliers)),
            "notch_hz": notch_freq,
            "highpass_hz": float(hp),
            "lowpass_hz": float(lp),
            "savgol": False,
            "detection_model": "Gaussian Neyman-Pearson approximation on in-band spectral amplitude",
            **input_meta,
        },
        **decision,
    }


def synthetic_acquisition(p):
    """Development source only: produces a raw block; processing remains fully real."""
    n = 500
    fs = float(p.sampling_rate)
    t = np.arange(n) / fs
    rng = np.random.default_rng(int(time.time_ns() % (2**32 - 1)))
    center = float(p.target_position) * n
    half = max(6.0, min(n / 3.0, (float(p.target_duration) / 1000.0 * fs) / 2.0))
    env = np.exp(-((np.arange(n) - center) / half) ** 2)
    echo = float(p.target_amplitude) * env * np.sin(2 * np.pi * float(p.target_frequency) * t)
    noise = rng.normal(0, float(p.noise_level) / 100.0 * 0.055, n)
    drift = 0.015 * np.sin(2 * np.pi * 35 * t)
    impulses = np.zeros(n)
    impulse_idx = rng.choice(n, size=max(1, n // 200), replace=False)
    impulses[impulse_idx] = rng.normal(0, 0.3, len(impulse_idx))
    return 0.42 + drift + echo + noise + impulses
