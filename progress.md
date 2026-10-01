# 📋 Project Log Book & System Architecture — CSI Dashboard

> [!IMPORTANT]
> ### 🤖 MANDATORY AI INSTRUCTION FOR ALL AI CODING ASSISTANTS
> **STOP AND READ BEFORE MAKING ANY CHANGES:**
> 1. **ALWAYS READ THIS FILE FIRST:** Any AI assistant working on this repository MUST read this `progress.md` file before inspecting or editing other files. It contains the exact technical architecture, operational quirks, and established conventions of this codebase.
> 2. **ALWAYS UPDATE THIS LOG BOOK BEFORE & AFTER EDITING:** Whenever you plan to make, or have made, any file changes, bug fixes, refactoring, or feature additions, you **MUST update this file** and append an entry to the [Project Change Log & Work History](#-5-project-change-log--work-history) section at the bottom of this file.
> 3. Document: Date, Files Modified, What Changed, and Technical Rationale. This prevents future AI sessions from repeating past mistakes or having to read through hundreds of files to understand the system state.

---

## 🏗️ 1. System Architecture Overview

CSI Dashboard is a real-time, non-invasive Wi-Fi Channel State Information (CSI) sensing platform for human presence detection, motion tracking, and indoor activity recognition using ESP32/Wi-Fi NIC CSI telemetry, FastAPI WebSockets, and a React dashboard.

```
csi-dashboard/
├── backend/                         # FastAPI WebSocket & Signal Processing Service
│   ├── server.py                    # Main FastAPI server, WebSocket endpoints, client broadcasting
│   ├── csi_parser.py                # Serial/UDP raw CSI packet frame decoder (amplitude/phase)
│   ├── classifier.py                # Machine learning activity & presence classifier
│   ├── profiles.py                  # User/environment baseline calibration manager
│   ├── profiles.json                # Serialized calibration profiles
│   ├── requirements.txt             # Python dependencies (fastapi, uvicorn, numpy, scipy, scikit-learn)
│   └── src/                         # Production modular Python architecture
│       ├── __init__.py
│       ├── config.py                # Centralized thresholds, frequencies, and buffer settings
│       ├── signal/                  # Signal preprocessing & feature engineering
│       │   ├── __init__.py
│       │   ├── preprocessing.py     # Subcarrier filtering, Hampel outlier filter, phase unwrapping
│       │   └── features.py          # Variance, Doppler spread, spectral entropy extraction
│       ├── state/                   # State machine engine
│       │   ├── __init__.py
│       │   └── engine.py            # Presence status (Empty, Stationary, Active, Fall Alert)
│       ├── alerts/                  # Alert evaluation and notification dispatch
│       │   ├── __init__.py
│       │   ├── evaluator.py         # Anomaly threshold checks & fall detection logic
│       │   └── manager.py           # In-memory and broadcast alert registry
│       └── utils/                   # Data validation and logging utilities
│           ├── __init__.py
│           └── helpers.py
│
├── src/                             # React / Vite Web Frontend
│   ├── App.jsx                      # Dashboard root, tab router, layout
│   ├── components/                  # Heatmaps, subcarrier charts, presence meters
│   └── ...
├── public/                          # Static assets and icons
├── processed_features.csv           # Benchmark CSI feature dataset
├── render.yaml                      # Cloud deployment descriptor
└── progress.md                      # THIS FILE — Persistent system logbook & AI context
```

### Quick Commands
- **Backend WebSocket Server:**
  ```powershell
  cd backend
  python server.py
  # or: uvicorn server:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Frontend Development Server:**
  ```powershell
  npm run dev
  ```
- **Build Frontend for Production:**
  ```powershell
  npm run build
  ```

---

## 🧠 2. Core Signal Processing & Sensing Knowledge

### A. What is Wi-Fi CSI?
- Unlike standard Received Signal Strength Indicator (RSSI) which gives only a single coarse scalar, Channel State Information (CSI) captures the **complex amplitude and phase across each individual OFDM subcarrier** (typically 52 to 64 subcarriers on 20 MHz channels).
- Human movement disturbs multipath propagation paths, inducing noticeable Doppler shifts, phase fluctuations, and amplitude attenuation across specific subcarriers.

### B. Signal Pipeline (`backend/src/signal/`)
1. **Raw Frame Ingestion:** Decodes incoming byte streams from ESP32 CSI tool or Intel 5300/Atheros frames (`csi_parser.py`).
2. **Filtering:** Hampel filter removes transient hardware noise spikes; Butterworth bandpass filter (0.5 Hz – 10 Hz) isolates human thoracic respiration and bodily movement while stripping DC channel offsets.
3. **Feature Extraction:** Subcarrier variance, dynamic range, correlation across subcarrier pairs, and Doppler shift energy.

### C. State Machine & Activity Classification (`backend/src/state/engine.py`)
- **`EMPTY`**: Baseline environmental multipath noise ($\sigma < \text{threshold}$).
- **`STATIONARY_PRESENCE`**: Low variance with rhythmic periodic subcarrier breathing fluctuations (0.2–0.4 Hz).
- **`ACTIVE_MOVEMENT`**: High variance across multiple subcarrier clusters.
- **`FALL_DETECTED`**: Sudden high-amplitude spike followed immediately by stationary/zero-movement state.

---

## 📌 3. Key Domain Insights & Operational Gotchas

1. **Multipath Sensitivity & Environment Calibration:**
   - Moving physical objects (furniture, doors) alters baseline CSI. The system uses baseline calibration profiles stored in `profiles.json`. Whenever testing in a new physical room, a 30-second environmental baseline calibration must be executed.
2. **Subcarrier Phase Unwrapping:**
   - Raw phase data contains significant Carrier Frequency Offset (CFO) and Sampling Frequency Offset (SFO) phase drift. If using phase features, phase unwrapping and linear fitting calibration must be applied before computing metrics.
3. **High-Frequency WebSocket Backpressure:**
   - ESP32 nodes can emit CSI packets at 50 Hz to 100 Hz. Broadcasting every raw packet directly over WebSockets to slow browser clients will cause event loop lag. The backend aggregates/resamples packets into 10–20 Hz telemetry frames.

---

## 🔌 4. API & WebSocket Endpoints Reference (`backend/server.py`)

- `GET /`: Health check and system operational state.
- `GET /api/status`: Current classification state, packet counters, active profile metadata.
- `GET /api/profiles`: List of calibrated environment profiles.
- `POST /api/calibrate`: Initiates dynamic baseline calibration recording.
- `WebSocket /ws`: Bidirectional real-time stream broadcasting telemetry frames, subcarrier amplitudes, classified state, and anomaly alerts to UI.

---

## 📝 5. Project Change Log & Work History

> **RULE FOR AI ASSISTANTS:** When you make changes, append a new log entry below with date, summary, files modified, and rationale.

### Entry: 2026-10-01 — Modular Backend Package Refactoring & AI Logbook Initialization
- **Author / Agent:** Antigravity (Gemini 3.8 Flash)
- **Files Modified / Created:**
  - `backend/src/config.py`: Extracted centralized configuration and threshold constants.
  - `backend/src/signal/preprocessing.py`: Extracted Hampel filter, Butterworth bandpass, and subcarrier cleaning.
  - `backend/src/signal/features.py`: Extracted feature calculations (variance, spectral entropy, Doppler).
  - `backend/src/state/engine.py`: Extracted presence/activity finite state machine logic.
  - `backend/src/alerts/evaluator.py`, `backend/src/alerts/manager.py`: Modularized alert and fall detection pipelines.
  - `backend/src/utils/helpers.py`: Common mathematical and serialization utilities.
  - `progress.md`: Created centralized logbook with system architecture, domain gotchas, and mandatory agent guidelines.
- **Rationale:** Structured the monolithic backend into clean, testable submodules and initialized the persistent agent knowledge base.
