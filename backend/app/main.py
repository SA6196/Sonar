import asyncio
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import SimulationParams, RawBlock, ModeOverride
from .processor import process_block, synthetic_acquisition

app = FastAPI(title="EB-SDS Signal Processing Backend", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mode_override: Optional[str] = None
latest_frame = None
latest_source = "SYNTHETIC DEVELOPMENT SOURCE"
latest_update_ms = 0


def _store_frame(frame, source: str):
    global latest_frame, latest_source, latest_update_ms
    latest_frame = frame
    latest_source = source
    latest_update_ms = int(time.time() * 1000)
    return frame


@app.get("/api/status")
def status():
    return {
        "online": True,
        "input_source": latest_source,
        "sampling_rate": latest_frame["sampling_rate"] if latest_frame else 50000,
        "block_size": latest_frame["block_size"] if latest_frame else 500,
        "firmware": "EB-SDS Python DSP v1.1.0",
        "link_latency_ms": max(0, int(time.time() * 1000) - latest_update_ms) if latest_update_ms else 0,
    }


@app.get("/api/latest")
def get_latest():
    return {
        "available": latest_frame is not None,
        "source": latest_source,
        "frame": latest_frame,
    }


@app.post("/api/process")
def process_simulation(params: SimulationParams):
    raw = synthetic_acquisition(params)
    frame = process_block(
        raw,
        params.sampling_rate,
        params.battery_level,
        params.detection_threshold,
        params.filter_cutoff,
        mode_override=mode_override,
    )
    return _store_frame(frame, "SYNTHETIC DEVELOPMENT SOURCE")


@app.post("/api/process/raw")
def process_raw(block: RawBlock):
    frame = process_block(
        block.samples,
        block.sampling_rate,
        block.battery_level,
        block.detection_threshold,
        block.filter_cutoff,
        timestamp=block.timestamp,
        mode_override=mode_override,
        adc_full_scale=block.adc_full_scale,
    )
    return _store_frame(frame, "ESP32 / WOKWI RAW SONAR BLOCK")


@app.post("/api/ingest/raw")
def ingest_raw(block: RawBlock):
    """Hardware/bridge endpoint. Stores the processed frame for live streaming."""
    return process_raw(block)


@app.post("/api/mode")
def set_mode(body: ModeOverride):
    global mode_override
    mode_override = body.mode
    return {"ok": True, "mode": mode_override}


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    try:
        params = SimulationParams(**await ws.receive_json())
        last_sent_timestamp = None
        while True:
            # Once real hardware sends /api/ingest/raw or /api/process/raw,
            # the dashboard automatically streams that latest processed block.
            if latest_frame is not None and latest_source != "SYNTHETIC DEVELOPMENT SOURCE":
                frame = latest_frame
                if frame.get("timestamp") != last_sent_timestamp:
                    await ws.send_json(frame)
                    last_sent_timestamp = frame.get("timestamp")
                await asyncio.sleep(0.08)
                continue

            raw = synthetic_acquisition(params)
            frame = process_block(
                raw,
                params.sampling_rate,
                params.battery_level,
                params.detection_threshold,
                params.filter_cutoff,
                mode_override=mode_override,
            )
            _store_frame(frame, "SYNTHETIC DEVELOPMENT SOURCE")
            await ws.send_json(frame)
            await asyncio.sleep(0.12)
    except WebSocketDisconnect:
        pass
