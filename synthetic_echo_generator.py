"""
synthetic_echo_generator.py

Generates labeled training data for the echo classifier (real target vs.
noise/clutter) BEFORE any real hardware exists.

The key idea: we already have real physics (environment.py, sonar_physics.py,
noise_estimator.py). Instead of making up random numbers for "what a target
echo looks like," we use our own SNR model to decide how strong a simulated
echo should be.

Two classes:
  1 = TARGET  -- a real echo is present, strength set by our SNR model
  0 = CLUTTER -- no real target; either pure background noise, or a weak
                 stray reflection
"""

import numpy as np
import pandas as pd

from environment import simulate_environment
from sonar_physics import SonarMode, get_snr

N_BANDS = 60          # match UCI Sonar dataset's 60 frequency-band features
SIGNAL_LENGTH = 512    # samples in our fake time-domain waveform

# Sonar-equation SNR values (from sonar_physics.get_snr) live on the real
# sonar dB scale (SL is referenced to 1 uPa @ 1m, so numbers like 80-140 dB
# are normal) -- NOT a plain audio power ratio. Converting that directly
# with 10**(SNR/10) blows up to astronomical amplitudes. Instead we just
# map the SNR range we actually see across our scenarios onto a sane,
# fixed amplitude range for the fake waveform (relative to noise_sigma=1.0).
SNR_MIN_DB = 50.0
SNR_MAX_DB = 140.0
AMPLITUDE_MIN = 0.3   # near noise floor -- a genuinely hard case
AMPLITUDE_MAX = 4.0   # clearly above noise -- an easy case


def snr_to_amplitude(snr_db: float) -> float:
    """Map a physics-model SNR (dB) onto a bounded waveform amplitude."""
    clipped = min(max(snr_db, SNR_MIN_DB), SNR_MAX_DB)
    frac = (clipped - SNR_MIN_DB) / (SNR_MAX_DB - SNR_MIN_DB)
    return AMPLITUDE_MIN + frac * (AMPLITUDE_MAX - AMPLITUDE_MIN)


def _make_waveform(amplitude: float, noise_sigma: float, rng: np.random.Generator,
                    include_target: bool) -> np.ndarray:
    
    t = np.linspace(0, 1, SIGNAL_LENGTH)
    signal = rng.normal(0, noise_sigma, SIGNAL_LENGTH)  # background noise

    if include_target:
        burst_center = rng.uniform(0.4, 0.6)
        envelope = np.exp(-((t - burst_center) ** 2) / (2 * 0.02 ** 2))
        tone = amplitude * envelope * np.sin(2 * np.pi * 40 * t)
        signal = signal + tone
    else:
    
        if rng.random() < 0.3:
            burst_center = rng.uniform(0.3, 0.7)
            envelope = np.exp(-((t - burst_center) ** 2) / (2 * 0.02 ** 2))
            stray = (amplitude * 0.15) * envelope * np.sin(2 * np.pi * 40 * t)
            signal = signal + stray

    return signal


def _waveform_to_features(signal: np.ndarray) -> np.ndarray:
    """
    Turn a raw time-domain signal into N_BANDS energy values, same shape as
    UCI's "energy within a frequency band" features. Uses FFT magnitude,
    split into equal-width bands, normalized to roughly [0, 1].
    """
    spectrum = np.abs(np.fft.rfft(signal))
    bands = np.array_split(spectrum, N_BANDS)
    band_energy = np.array([b.mean() for b in bands])
    # Normalize so features stay in a consistent, model-friendly range.
    max_val = band_energy.max() if band_energy.max() > 0 else 1.0
    return band_energy / max_val


def generate_dataset(n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Generate a labeled dataset of n_samples echoes, half target / half
    clutter, using our own physics modules to set realistic SNR-driven
    signal strength.

    Returns a DataFrame: columns band_0 ... band_59, plus a 'label' column
    (1 = target, 0 = clutter).
    """
    rng = np.random.default_rng(seed)
    mode = SonarMode("M2-Search", source_level_db=160, directivity_index_db=15)

    rows = []
    for i in range(n_samples):
        env = simulate_environment(seed=int(rng.integers(0, 10_000)))
        snr_db = get_snr(mode, env)
        amplitude = snr_to_amplitude(snr_db)
        noise_sigma = 1.0  # background noise level (arbitrary consistent unit)

        include_target = (i % 2 == 0)  # perfectly balanced classes
        signal = _make_waveform(amplitude, noise_sigma, rng, include_target)
        features = _waveform_to_features(signal)

        rows.append(list(features) + [int(include_target)])

    columns = [f"band_{i}" for i in range(N_BANDS)] + ["label"]
    return pd.DataFrame(rows, columns=columns)


if __name__ == "__main__":
    df = generate_dataset(n_samples=1000, seed=42)
    print(df.shape)
    print(df["label"].value_counts())
    print(df.head())
    df.to_csv("synthetic_echoes.csv", index=False)
    print("\nSaved to synthetic_echoes.csv")