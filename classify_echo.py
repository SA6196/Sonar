"""

This is meant to run on the LAPTOP / DASHBOARD side, not the embedded
MCU -- the ESP32/STM32 streams raw echo samples up, this classifies them,
and the result gets logged/displayed alongside the deterministic Pd/Pfa
numbers from detection_model.py. It does NOT replace the feasibility
filter's decision -- it's a second signal that rides alongside it.
"""

from dataclasses import dataclass

import joblib
import numpy as np

from synthetic_echo_generator import _waveform_to_features

MODEL_PATH = "echo_classifier.joblib"
SCALER_PATH = "echo_scaler.joblib"

_model = None
_scaler = None


def _load():
    """Lazy-load the trained model + scaler once, then reuse."""
    global _model, _scaler
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)
    return _model, _scaler


@dataclass
class ClassificationResult:
    label: str          # "target" or "clutter"
    confidence: float   # 0.0 - 1.0, model's confidence in that label


def classify_echo(raw_signal: np.ndarray) -> ClassificationResult:
    """
    The one function the rest of the team calls.

    raw_signal: a 1D array of raw echo samples (time domain), same shape
                the hardware team's ADC would produce.

    Returns a ClassificationResult with a plain-English label and a
    confidence score -- easy to log, easy to put on a dashboard.
    """
    model, scaler = _load()

    features = _waveform_to_features(raw_signal).reshape(1, -1)
    features_scaled = scaler.transform(features)

    pred = model.predict(features_scaled)[0]
    proba = model.predict_proba(features_scaled)[0]

    label = "target" if pred == 1 else "clutter"
    confidence = float(proba[pred])

    return ClassificationResult(label=label, confidence=confidence)


if __name__ == "__main__":
    # End-to-end demo: generate a couple of fake echoes the SAME way
    # training data was made, and confirm classify_echo() gets them right.
    from synthetic_echo_generator import _make_waveform
    import numpy as np

    rng = np.random.default_rng(123)

    print("Testing on a clear TARGET echo (high SNR, amplitude=3.5):")
    signal = _make_waveform(amplitude=3.5, noise_sigma=1.0, rng=rng, include_target=True)
    result = classify_echo(signal)
    print(f"  -> predicted: {result.label} (confidence {result.confidence:.2f})")

    print("\nTesting on a weak/borderline TARGET echo (low SNR, amplitude=0.5):")
    signal = _make_waveform(amplitude=0.5, noise_sigma=1.0, rng=rng, include_target=True)
    result = classify_echo(signal)
    print(f"  -> predicted: {result.label} (confidence {result.confidence:.2f})")

    print("\nTesting on pure CLUTTER (background noise only):")
    signal = _make_waveform(amplitude=2.0, noise_sigma=1.0, rng=rng, include_target=False)
    result = classify_echo(signal)
    print(f"  -> predicted: {result.label} (confidence {result.confidence:.2f})")