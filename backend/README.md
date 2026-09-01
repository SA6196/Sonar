# EB-SDS Python DSP Backend

## DSP chain

Raw block -> conservative impulse suppression -> robust median DC removal -> linear detrend -> adaptive 50/60 Hz notch only when the block duration can resolve mains interference -> 6th-order Butterworth band-pass -> Hann-windowed FFT -> robust spectral noise floor -> -3 dB bandwidth -> analytic-envelope detection -> SNR/Pd/Pfa -> EB-SDS energy-aware Tier decision.

Savitzky-Golay smoothing is intentionally disabled because it can attenuate a short, high-frequency sonar echo.

## Run

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for API testing.

## Real Wokwi/ESP32 sonar blocks

POST the complete acquisition block to `/api/process/raw`:

```json
{
  "timestamp": 12345,
  "sampling_rate": 50000,
  "battery_level": 0.86,
  "detection_threshold": 0.18,
  "filter_cutoff": 8000,
  "samples": [1351, 1352, 1349]
}
```

For real ESP32/MCP ADC count data, the backend normalizes ADC count data only when the caller explicitly supplies the known ADC full-scale value (for example 4095 for ESP32 12-bit or 1023 for MCP3008); it no longer guesses the ADC range from observed samples. The original raw samples are still returned for display.

`detection_window.start` and `detection_window.end` are normalized to `0..1`, matching the frontend graph contract.

The current `/api/process` and `/ws/stream` endpoints remain synthetic development sources. For real hardware processing, send each complete 500-sample sonar block to `/api/process/raw`.

## Live ESP32 serial integration

The ZIP now includes `esp32_serial_bridge.py`.

Expected ESP32/Wokwi format:

```text
START
SONAR=[1351,1352,...]
END
```

Install dependencies, start the backend, then run:

```bash
python esp32_serial_bridge.py --port COM5 --baud 115200 --sampling-rate 50000
```

Replace `COM5` with the actual ESP32 serial port. Every complete block is sent to `/api/ingest/raw`, stored as the latest real frame, and the existing dashboard WebSocket automatically streams that real processed frame instead of synthetic data.

## Detection model note

Pd, Pfa and ROC now use one Gaussian Neyman-Pearson approximation based on the dominant in-band spectral amplitude relative to the robust in-band noise floor. These values are model-based estimates, not calibrated field probabilities. Calibration with labeled hardware recordings is still required before making quantitative field-performance claims.

## Hardware sampling rate

The bridge accepts `--sampling-rate`, but the value must come from measured/verified firmware timing. The default 50000 is only a configuration default and must not be presented as a measured hardware capability until verified on the actual ESP32 acquisition firmware.
