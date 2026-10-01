"""
src.signal
==========
Low-level CSI signal processing utilities.

Contents
--------
parse_csi_line(line)            — parse a raw ESP32 LLTF CSI serial line
classify_activity(...)          — variance-history activity classifier

These functions were originally inlined inside server.py; extracting them here
makes them independently testable and reusable without importing the full
FastAPI application.
"""

import math
from datetime import datetime

import numpy as np

from src.config import SENSITIVE, N_SUBCARRIERS


# ── CSI Line Parser ────────────────────────────────────────────────────────────

def parse_csi_line(line: str) -> tuple[float, list[float]] | None:
    """
    Parse a raw ESP32 CSI serial line.

    Handles two formats:
    - Bare:     ``CSI,<ts>,<rssi>,<noise>,<len>,<bytes…>``
    - Prefixed: ``I (1234) csi: CSI,<ts>,…``   (ESP-IDF log prefix)

    Returns
    -------
    (aggregate_amplitude, subcarrier_amplitudes)  or  ``None`` on parse error.

    Notes
    -----
    - Each raw byte-pair ``(im, re)`` is decoded from unsigned bytes (0-255)
      to signed values then converted to amplitude via ``sqrt(re² + im²)``.
    - ``aggregate_amplitude`` is the mean amplitude across the sensitive
      subcarrier indices defined in :mod:`src.config`.
    """
    line = line.strip()

    # Strip ESP-IDF log prefix if present
    if "CSI," in line:
        line = line[line.index("CSI,"):]
    elif not line.startswith("CSI"):
        return None

    parts = line.split(",")
    if len(parts) < 8:
        return None

    try:
        length = int(parts[4])
        raw    = [int(x) for x in parts[5:5 + length]]
    except (ValueError, IndexError):
        return None

    amps: list[float] = []
    for i in range(0, len(raw) - 1, 2):
        im, re = raw[i], raw[i + 1]
        if im > 127:
            im -= 256
        if re > 127:
            re -= 256
        amps.append(math.sqrt(re ** 2 + im ** 2))

    sensitive_amps = [amps[i] for i in SENSITIVE if i < len(amps)]
    if not sensitive_amps:
        return None

    aggregate = float(np.mean(sensitive_amps))
    return aggregate, sensitive_amps


# ── Variance-based Activity Classifier ────────────────────────────────────────

def classify_activity(
    var_history: list[float],
    baseline: float,
    threshold: float,
) -> tuple[str, float]:
    """
    Classify the occupant's current activity from a short window of variance
    values.

    This heuristic classifier avoids the overhead of a trained model for the
    common case; it complements :class:`~classifier.ActivityClassifier` which
    uses a full Random Forest / CNN on raw amplitude vectors.

    Parameters
    ----------
    var_history:
        Recent rolling-window variance samples (length ≥ 10 recommended).
    baseline:
        Mean empty-room variance determined during calibration.
    threshold:
        Detection threshold (``baseline × threshold_mul``).

    Returns
    -------
    (activity_name, confidence)
        ``activity_name`` is one of ``{"empty", "breathing", "stationary",
        "walking", "fall", "unknown"}``.
        ``confidence`` is in ``[0.0, 0.95]``.

    Algorithm
    ---------
    Uses the **ratio** of current mean variance to the calibrated baseline and
    the **coefficient of variation** (``std / mean``) to discriminate classes:

    +-----------+----------------+----------+
    | Class     | ratio          | CV       |
    +===========+================+==========+
    | empty     | ≤ 1.3          | any      |
    | breathing | 1.3 – 2.0      | < 0.4    |
    | stationary| 2.0 – 3.5      | < 0.5    |
    | walking   | > 3.5 or CV>0.5| any      |
    | fall      | spike pattern  | —        |
    +-----------+----------------+----------+

    Fall is detected by a large first-half spike that drops off in the second
    half of the window.
    """
    if len(var_history) < 10 or baseline <= 0:
        return "unknown", 0.0

    arr      = np.array(var_history, dtype=float)
    mean_var = float(np.mean(arr))
    std_var  = float(np.std(arr))
    max_var  = float(np.max(arr))
    ratio    = mean_var / (baseline + 1e-9)
    cv       = std_var / (mean_var + 1e-9)   # coefficient of variation

    # Fall: large spike in the first half, drops to near-baseline in the second half
    half = len(arr) // 2
    if len(arr) >= 20:
        first_mean  = float(np.mean(arr[:half]))
        second_mean = float(np.mean(arr[half:]))
        spike_ratio = first_mean / (second_mean + 1e-9)
        if (max_var > threshold * 2.5
                and spike_ratio > 2.5
                and second_mean < threshold * 1.5):
            return "fall", min(0.5 + spike_ratio * 0.05, 0.95)

    # Walking: high variance with high variability
    if ratio > 3.5 or (ratio > 2.0 and cv > 0.5):
        conf = min(0.5 + (ratio - 3.5) * 0.1 + cv * 0.2, 0.95)
        return "walking", round(conf, 3)

    # Stationary: elevated but stable variance
    if 2.0 < ratio <= 3.5 and cv < 0.5:
        conf = min(0.5 + (ratio - 2.0) * 0.15, 0.85)
        return "stationary", round(conf, 3)

    # Breathing: small variance just above baseline, low variability
    if 1.3 < ratio <= 2.0 and cv < 0.4:
        conf = min(0.5 + (ratio - 1.3) * 0.3, 0.80)
        return "breathing", round(conf, 3)

    # Empty: variance at or near baseline
    if ratio <= 1.3:
        conf = min(0.5 + (1.3 - ratio) * 0.5, 0.95)
        return "empty", round(conf, 3)

    return "stationary", 0.4


def current_hour() -> int:
    """Return the current wall-clock hour (0–23)."""
    return datetime.now().hour
