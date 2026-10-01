"""
src.config
==========
Single source of truth for all hardware, tuning, and application constants.

Importing this module anywhere guarantees the same values are used across
server.py, csi_parser.py, classifier.py and profiles.py without magic globals.
"""

# ── Serial / Hardware ────────────────────────────────────────────────────────
SERIAL_PORT = "/dev/ttyACM0"   # Change to your ESP32 serial port
BAUD_RATE   = 115_200

# Set True to test without real ESP32 hardware (uses synthetic CSI frames)
DEMO_MODE   = False

# Subcarrier indices most sensitive to human body motion (LLTF subset)
SENSITIVE: list[int] = [19, 20, 21, 22, 23, 24, 25, 26, 38, 39]

# Total number of OFDM subcarriers in the LLTF packet
N_SUBCARRIERS = 64

# ── Calibration / Detection ──────────────────────────────────────────────────
WINDOW        = 30     # rolling window size (frames) for variance computation
CALIB_FRAMES  = 100   # frames collected during the empty-room calibration phase

# Multiplier applied to the calibrated baseline variance to derive the threshold
DEFAULT_THRESHOLD_MUL = 2.0

# Consecutive above-threshold frames required before motion is "confirmed"
CONFIRM_FRAMES = 8

# Consecutive below-threshold frames required to declare the room "clear"
CLEAR_FRAMES   = 12

# ── Rate Limiting ────────────────────────────────────────────────────────────
# Maximum WebSocket broadcast rate (seconds between updates)
BROADCAST_INTERVAL = 0.1   # 10 fps

# Minimum seconds between Telegram alerts for the same event
COOLDOWN_SECS = 5

# ── Activity Classifier ──────────────────────────────────────────────────────
# Number of recent variance samples fed to classify_activity()
ACTIVITY_VAR_WINDOW = 60   # ≈3 s at 20 fps

# ── Telegram Notifications ───────────────────────────────────────────────────
TELEGRAM_TOKEN   = "8653748907:AAGuS-6WWqgIUwGgYIYHKtQbfCfPD5s-ER8"
TELEGRAM_CHAT_ID = "5603958342"
