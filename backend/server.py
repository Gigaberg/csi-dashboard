"""
FastAPI WebSocket backend for the person identification system.

Endpoints:
  WS  /ws          — live CSI stream (existing dashboard)
  WS  /ws/identify — identity detection stream
  POST /enroll/start  { name }
  POST /enroll/stop
  GET  /profiles
  DELETE /profiles/{name}
  GET  /events
"""
import asyncio
import collections
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
import serial_asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from csi_parser import CSIFeatureExtractor
from profiles import ProfileStore

# ── src package imports ───────────────────────────────────────────────────────
from src.config import (
    SERIAL_PORT, BAUD_RATE, DEMO_MODE, SENSITIVE, WINDOW, CALIB_FRAMES,
    CONFIRM_FRAMES, CLEAR_FRAMES, BROADCAST_INTERVAL, COOLDOWN_SECS,
    ACTIVITY_VAR_WINDOW,
)
from src.signal import parse_csi_line, classify_activity
from src.alerts import send_telegram
from src.state import initial_state
from src.utils import sanitize as _sanitize

# ── Config ────────────────────────────────────────────────────────────────────
# All constants are now defined in src/config.py and imported above.

# ── Globals ───────────────────────────────────────────────────────────────────
store     = ProfileStore()
extractor = CSIFeatureExtractor()
identity_clients:  list[WebSocket] = []
dashboard_clients: list[WebSocket] = []

enrolling_name: str | None = None
event_log: list[dict] = []   # last 100 crossing events

# Dashboard state — initialized from src.state
cfg   = {"threshold_mul": 2.0, "mute_until": 0.0}
state = initial_state()
_calib_vars:  list[float] = []
_clear_vars:  list[float] = []
_motion_vars: list[float] = []
_amp_buf: collections.deque = collections.deque(maxlen=WINDOW)
_last_alert      = 0.0
_last_broadcast  = 0.0
_start_time      = time.time()
_above_count     = 0   # consecutive frames above threshold
_below_count     = 0   # consecutive frames below threshold
_confirmed_motion = False  # True once CONFIRM_FRAMES sustained
recalibrate_flag = asyncio.Event()

# ── Variance history for activity classification ─────────────────────────────
# Rolling window fed to classify_activity() from src.signal
_var_history: collections.deque = collections.deque(maxlen=ACTIVITY_VAR_WINDOW)
# Calibrated empty-room variance (used as floor reference)
_empty_var_mean = 0.0
_empty_var_std  = 0.0


# classify_activity is now imported from src.signal


# parse_csi_line is now imported from src.signal


# send_telegram is now imported from src.alerts
# (mute_until is passed in from cfg at call sites below)


# ── Broadcast helper ──────────────────────────────────────────────────────────
async def _broadcast(clients: list[WebSocket], data: dict):
    dead = []
    for ws in clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)


# ── Calibration ───────────────────────────────────────────────────────────────
async def run_calibration(reader):
    global _calib_vars, _amp_buf
    state["calibrating"] = True
    _calib_vars = []
    _amp_buf.clear()
    print("\n🔧 Calibrating — empty the room and stay still...")
    await _broadcast(dashboard_clients, state)

    deadline = time.time() + 60  # max 60s for calibration
    while len(_calib_vars) < CALIB_FRAMES:
        if recalibrate_flag.is_set():
            break
        if time.time() > deadline:
            print("\n⚠️  Calibration timeout — using collected data")
            break
        try:
            line = (await asyncio.wait_for(reader.readline(), timeout=2.0)).decode("utf-8", errors="ignore")
        except asyncio.TimeoutError:
            continue
        result = parse_csi_line(line)
        if result is None:
            continue
        agg, sc_amps = result
        # Pad/trim to exactly len(SENSITIVE) elements
        sc_amps_fixed = (sc_amps + [0.0] * len(SENSITIVE))[:len(SENSITIVE)]
        _amp_buf.append(sc_amps_fixed)
        if len(_amp_buf) == WINDOW:
            arr = np.array(_amp_buf, dtype=float)
            _calib_vars.append(float(np.var(arr, axis=0).mean()))
        print(f"  Calibrating... {len(_calib_vars)}/{CALIB_FRAMES}", end="\r")
        # Broadcast progress so frontend progress bar moves
        await _broadcast(dashboard_clients, state)

    baseline  = float(np.mean(_calib_vars)) if _calib_vars else 1.0
    threshold = baseline * cfg["threshold_mul"]
    state["baseline"]      = round(baseline, 4)
    state["threshold"]     = round(threshold, 4)
    state["threshold_mul"] = cfg["threshold_mul"]
    state["calibrating"]   = False
    # Store empty-room variance stats for activity classification
    global _empty_var_mean, _empty_var_std, _var_history
    _empty_var_mean = baseline
    _empty_var_std  = float(np.std(_calib_vars)) if len(_calib_vars) > 1 else baseline * 0.1
    _var_history.clear()
    print(f"\n✅ Calibration done — baseline={baseline:.4f}  threshold={threshold:.4f}")
    await _broadcast(dashboard_clients, state)
    return threshold


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(csi_reader_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── CSI reader loop ───────────────────────────────────────────────────────────
async def csi_reader_loop():
    if DEMO_MODE:
        await _demo_loop()
    else:
        await _serial_loop()


async def _demo_loop():
    """Simulate CSI crossings for testing without hardware."""
    import random
    global _last_alert, _start_time
    _start_time = time.time()
    crossing_timer = 0
    # Fake calibration
    state["baseline"]     = 1.0
    state["threshold"]    = 2.0
    state["calibrating"]  = False
    while True:
        await asyncio.sleep(0.01)
        crossing_timer += 1
        amp = random.gauss(0, 0.3)
        if crossing_timer > 800:
            phase = (crossing_timer - 800) / 80
            amp += 5.0 * math.exp(-((phase - 1.5) ** 2) / 0.5) * (1 + random.gauss(0, 0.1))
            if crossing_timer > 1050:
                crossing_timer = 0
        sc_amps = [abs(amp + random.gauss(0, 0.1)) for _ in SENSITIVE]
        await _process_frame(abs(amp), sc_amps, state["threshold"])


async def _serial_loop():
    """Read from real ESP32 over serial using the ESP32 LLTF CSI format."""
    global _start_time
    _start_time = time.time()
    try:
        reader, _ = await serial_asyncio.open_serial_connection(
            url=SERIAL_PORT, baudrate=BAUD_RATE
        )
        threshold = await run_calibration(reader)

        # Drain any backlogged serial data accumulated during calibration
        try:
            while True:
                await asyncio.wait_for(reader.readline(), timeout=0.05)
        except asyncio.TimeoutError:
            pass

        print(f"🌐 WebSocket live at ws://localhost:8000/ws\n")

        while True:
            if recalibrate_flag.is_set():
                recalibrate_flag.clear()
                threshold = await run_calibration(reader)
                # Drain again after recalibration
                try:
                    while True:
                        await asyncio.wait_for(reader.readline(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass
                continue

            line = (await reader.readline()).decode("utf-8", errors="ignore")
            result = parse_csi_line(line)
            if result is None:
                continue
            agg, sc_amps = result
            await _process_frame(agg, sc_amps, threshold)

    except Exception as e:
        print(f"Serial error: {e}. Falling back to demo mode.")
        await _demo_loop()


async def _process_frame(agg: float, sc_amps: list[float], threshold: float):
    """Update dashboard state and run identity feature extraction."""
    global _last_alert, _clear_vars, _motion_vars, _last_broadcast
    global _above_count, _below_count, _confirmed_motion

    # Pad/trim sc_amps to exactly len(SENSITIVE) elements
    sc_amps_fixed = (sc_amps + [0.0] * len(SENSITIVE))[:len(SENSITIVE)]
    _amp_buf.append(sc_amps_fixed)
    if len(_amp_buf) < WINDOW:
        return

    arr         = np.array(_amp_buf, dtype=float)
    current_var = float(np.var(arr, axis=0).mean())
    sub_vars    = np.var(arr, axis=0).tolist()
    now         = time.time()
    hour        = datetime.now().hour

    # Accumulate variance history for activity classification
    _var_history.append(current_var)
    # ── Sustained motion detection ────────────────────────────────────────────
    if current_var > threshold:
        _above_count += 1
        _below_count  = 0
        # Only confirm motion after CONFIRM_FRAMES consecutive above-threshold frames
        if _above_count >= CONFIRM_FRAMES and not _confirmed_motion:
            _confirmed_motion = True
    else:
        _below_count += 1
        _above_count  = 0
        # Only clear after CLEAR_FRAMES consecutive below-threshold frames
        if _below_count >= CLEAR_FRAMES:
            _confirmed_motion = False

    if _confirmed_motion:
        status = "motion"
        if state["occupied_since"] is None:
            state["occupied_since"] = now
            state["session"]["motion_events"] += 1
            state["heatmap"][hour] += 1
        _motion_vars.append(current_var)
        send_telegram(
            f"🚨 Motion detected! (var={current_var:.2f})",
            mute_until=cfg["mute_until"],
        )
    else:
        status = "clear"
        if not _confirmed_motion:
            state["occupied_since"] = None
        _clear_vars.append(current_var)

    if len(_clear_vars)  > 200: _clear_vars.pop(0)
    if len(_motion_vars) > 200: _motion_vars.pop(0)

    state["variance"]    = round(current_var, 4)
    state["status"]      = status
    state["subcarriers"] = [round(v, 3) for v in sub_vars]
    state["session"]["uptime_s"]       = int(now - _start_time)
    state["session"]["avg_clear_var"]  = round(float(np.mean(_clear_vars)),  3) if _clear_vars  else 0.0
    state["session"]["avg_motion_var"] = round(float(np.mean(_motion_vars)), 3) if _motion_vars else 0.0

    # AI activity classification — variance-based temporal classifier
    activity_name, activity_conf = classify_activity(
        list(_var_history), state["baseline"], state["threshold"]
    )
    state["activity"]      = activity_name
    state["activity_conf"] = activity_conf

    # Throttle broadcasts to avoid flooding the WebSocket and causing lag
    if now - _last_broadcast >= BROADCAST_INTERVAL:
        _last_broadcast = now
        await _broadcast(dashboard_clients, state)

    # Identity feature extraction runs every frame (no throttle needed)
    await _process_identity(current_var, sc_amps_fixed)


# _sanitize is now imported from src.utils as _sanitize


async def _process_identity(agg: float, sc_amps: list[float]):
    """Run identity feature extraction; broadcast on crossing completion."""
    global enrolling_name
    features = extractor.push_multi(agg, sc_amps)
    if features is None:
        return

    scalar_vec = extractor.scalar_vector(features).tolist()
    ts = time.strftime("%H:%M:%S")

    if enrolling_name:
        count = store.enroll(enrolling_name, features, scalar_vec)
        print(f"  ✏️  Enrolled {enrolling_name} — crossing #{count}")
        event = {
            "type":     "enrolled",
            "name":     enrolling_name,
            "count":    count,
            "time":     ts,
            "features": {k: v for k, v in features.items() if k != "envelope"},
        }
    else:
        name, dist = store.identify(features, extractor.scalar_vector(features))
        event = {
            "type":         "identified" if name != "unknown" else "unknown",
            "name":         name,
            "display_name": f"Highly Likely {name}" if name != "unknown" else "UNKNOWN",
            "distance":     round(dist, 3),
            "time":         ts,
            "features":     {k: v for k, v in features.items() if k != "envelope"},
        }

    event_log.insert(0, _sanitize(event))
    if len(event_log) > 100:
        event_log.pop()

    await _broadcast(identity_clients, event)


# ── WebSocket endpoints ───────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_dashboard(ws: WebSocket):
    """Existing dashboard CSI stream — also accepts control commands."""
    await ws.accept()
    dashboard_clients.append(ws)
    await ws.send_json(state)
    try:
        async for raw in ws.iter_text():
            try:
                cmd = json.loads(raw)
                if cmd.get("cmd") == "recalibrate":
                    recalibrate_flag.set()
                elif cmd.get("cmd") == "set_mul":
                    val = float(cmd.get("value", 2.0))
                    cfg["threshold_mul"] = max(1.1, min(val, 10.0))
                    recalibrate_flag.set()
                elif cmd.get("cmd") == "mute":
                    mins = int(cmd.get("minutes", 10))
                    cfg["mute_until"] = time.time() + mins * 60
                    await ws.send_json({"muted_until": cfg["mute_until"]})
                elif cmd.get("cmd") == "export":
                    lines = ["time,status,variance"]
                    for row in event_log:
                        lines.append(f"{row['time']},{row.get('type','')},{row.get('features',{}).get('peak_variance','')}")
                    await ws.send_json({"export": "\n".join(lines)})
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if ws in dashboard_clients:
            dashboard_clients.remove(ws)


@app.websocket("/ws/identify")
async def ws_identify(ws: WebSocket):
    """Identity event stream for the new dashboard panel."""
    await ws.accept()
    identity_clients.append(ws)
    # Send recent history on connect
    for ev in event_log[:20]:
        await ws.send_json(ev)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in identity_clients:
            identity_clients.remove(ws)


# ── REST endpoints ────────────────────────────────────────────────────────────
class EnrollRequest(BaseModel):
    name: str


@app.post("/enroll/start")
async def enroll_start(req: EnrollRequest):
    global enrolling_name
    enrolling_name = req.name.strip()
    return {"status": "enrolling", "name": enrolling_name}


@app.post("/enroll/stop")
async def enroll_stop():
    global enrolling_name
    name = enrolling_name
    enrolling_name = None
    count = len(store.profiles.get(name, [])) if name else 0
    return {"status": "stopped", "name": name, "crossings": count}


@app.get("/profiles")
async def get_profiles():
    return store.list_profiles()


@app.delete("/profiles/{name}")
async def delete_profile(name: str):
    ok = store.delete(name)
    return {"deleted": ok, "name": name}


@app.get("/events")
async def get_events():
    return _sanitize(event_log[:50])
