"""EB-SDS serial bridge: ESP32/Wokwi sonar block -> backend live dashboard.

Expected serial format:
START
SONAR=[1351,1352,...]   # complete block, usually 500 samples
END

Run after starting the FastAPI backend:
    python esp32_serial_bridge.py --port COM5 --baud 115200 --adc-full-scale 4095

The bridge posts every complete SONAR block to /api/ingest/raw. The existing
frontend WebSocket automatically switches from synthetic frames to the latest
real hardware frame once ingestion begins.
"""

import argparse
import json
import re
import time
from urllib.request import Request, urlopen

import serial

SONAR_RE = re.compile(r"SONAR\s*=\s*\[([^\]]+)\]")


def post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=5) as response:
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, help="ESP32 serial port, e.g. COM5 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/ingest/raw")
    parser.add_argument("--sampling-rate", type=float, default=50000)
    parser.add_argument("--adc-full-scale", type=float, required=True, help="Known ADC full-scale count, e.g. 4095 for ESP32 12-bit or 1023 for MCP3008")
    parser.add_argument("--battery", type=float, default=0.86)
    parser.add_argument("--threshold", type=float, default=0.18)
    parser.add_argument("--cutoff", type=float, default=8000)
    args = parser.parse_args()

    in_block = False
    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        print(f"Listening on {args.port} @ {args.baud} baud")
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line == "START":
                in_block = True
                continue
            if line == "END":
                in_block = False
                continue
            if not in_block:
                continue

            match = SONAR_RE.search(line)
            if not match:
                continue

            try:
                samples = [float(v.strip()) for v in match.group(1).split(",") if v.strip()]
            except ValueError:
                print("Ignored malformed SONAR block")
                continue

            if len(samples) < 32:
                print(f"Ignored short block ({len(samples)} samples)")
                continue

            payload = {
                "timestamp": int(time.time() * 1000),
                "sampling_rate": args.sampling_rate,
                "battery_level": args.battery,
                "detection_threshold": args.threshold,
                "filter_cutoff": args.cutoff,
                "adc_full_scale": args.adc_full_scale,
                "samples": samples,
            }
            try:
                post_json(args.url, payload)
                print(f"Sent {len(samples)} sonar samples to EB-SDS backend")
            except Exception as exc:
                print(f"Backend send failed: {exc}")


if __name__ == "__main__":
    main()
