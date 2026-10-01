# CloakWatch — Wi-Fi CSI Presence & Activity Detection

A real-time, camera-free presence detection system using Wi-Fi CSI (Channel State Information) from ESP32-S3 microcontrollers. When someone moves in a room, it disturbs the Wi-Fi signal — CloakWatch detects that disturbance, classifies the activity, and alerts you instantly.

---

## How It Works

Two ESP32-S3 boards are used:

- **Transmitter** — acts as a Wi-Fi Access Point (`CSI_Beacon`) and broadcasts UDP packets every 50ms
- **Receiver** — connects to the AP, captures CSI data from incoming frames, and streams raw IQ samples over USB serial to a laptop

The Python backend reads the serial stream, extracts amplitude variance across 10 sensitive subcarriers, runs a calibration phase to establish a baseline, and classifies activity when variance deviates from baseline. Results are broadcast in real time to the web dashboard via WebSocket.

---

## System Architecture

```
[ESP32 Transmitter] --Wi-Fi CSI--> [ESP32 Receiver] --USB Serial--> [Python Backend (FastAPI)]
                                                                            |
                                                                     WebSocket (ws://localhost:8000/ws)
                                                                            |
                                                              [Web Dashboard on Render]
                                                                            |
                                                                   [ngrok tunnel for remote access]
```

---

## Hardware Required

- 2× ESP32-S3 development boards
- USB cable (receiver connected to laptop)
- ESP-IDF v5.x toolchain

---

## Firmware Setup

Flash the transmitter:
```bash
cd csi_transmitter
idf.py build flash
```

Flash the receiver:
```bash
cd csi_receiver
idf.py build flash
```

The receiver streams CSI lines over serial at 115200 baud:
```
CSI,<timestamp>,<rssi>,<noise_floor>,<length>,<raw IQ bytes...>
```

---

## Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

The backend will:
1. Open `/dev/ttyACM0` at 115200 baud (change `SERIAL_PORT` in `server.py` if needed)
2. Run a 100-frame calibration — keep the room empty and still during this phase
3. Stream detection results over WebSocket at `ws://localhost:8000/ws`

---

## Frontend (Dashboard)

Hosted on Render. Built with Vite + vanilla JS + Chart.js.

To run locally:
```bash
npm install
npm run dev
```

To rebuild for production:
```bash
npm run build
git add -f dist/
git commit -m "rebuild"
git push
```

---

## Remote Access via ngrok

Since the backend runs locally (the ESP32 is physically connected to your laptop), use ngrok to expose it:

```bash
ngrok http 8000
```

Then enter the tunnel URL in the dashboard login screen's Backend URL field:
```
wss://your-ngrok-url.ngrok-free.app/ws
```

---

## Dashboard Login

| Role           | Username | Password |
|----------------|----------|----------|
| Admin          | admin    | cloak    |
| Property Owner | owner    | cloak    |

Admin has full controls (recalibrate, sensitivity, mute, export).
Property Owner is view-only.

---

## Activity Classification

The backend uses a variance-based temporal classifier (no pre-trained model required). It observes rolling variance over a ~3 second window and classifies:

| Activity    | Signal pattern                                      |
|-------------|-----------------------------------------------------|
| empty       | Variance at baseline                                |
| breathing   | Tiny stable elevation just above baseline           |
| stationary  | Moderate stable elevation                           |
| walking     | High variance with irregular spikes                 |
| fall        | Large spike followed by sudden drop to near-baseline|

---

## Features

- Presence detection using Wi-Fi CSI variance (no cameras)
- Real-time activity classification (empty / breathing / stationary / walking / fall)
- Person identification via CSI gait signatures
- Live variance chart, subcarrier sparklines, 24h motion heatmap
- Telegram alerts on motion detection
- Recalibration on demand or via sensitivity slider
- Session stats: uptime, motion event count, avg variance
- CSV export of session data
- Role-based login (Admin / Property Owner)
- Dark/light theme toggle
- Remote access via ngrok

---

## Tech Stack

| Layer     | Technology                                      |
|-----------|-------------------------------------------------|
| Hardware  | ESP32-S3, ESP-IDF, FreeRTOS                     |
| Backend   | Python, FastAPI, serial-asyncio, numpy          |
| Frontend  | Vite, vanilla JS, Chart.js                      |
| Hosting   | Render (frontend), ngrok (backend tunnel)       |
| Alerts    | Telegram Bot API                                |
