"""
src.state
=========
Shared mutable application state for the CSI dashboard backend.

Design rationale
----------------
All WebSocket handlers and the CSI reader loop mutate the same in-memory
state dict.  By isolating the initial state definition and its reset helper
here we avoid scattering magic keys across server.py.

Usage
-----
    from src.state import initial_state, make_session

    state = initial_state()
    # … mutate state["variance"] etc. inside the reader loop …
"""

from src.config import DEFAULT_THRESHOLD_MUL, SENSITIVE


def make_session() -> dict:
    """Return a fresh, zeroed session statistics sub-dict."""
    return {
        "motion_events":  0,
        "uptime_s":       0,
        "avg_clear_var":  0.0,
        "avg_motion_var": 0.0,
    }


def initial_state() -> dict:
    """
    Return the starting dashboard state dictionary.

    Keys
    ----
    variance        : current rolling-window variance of the subcarrier amplitudes
    status          : ``"clear"`` | ``"motion"``
    threshold       : detection threshold (updated after calibration)
    baseline        : calibrated empty-room mean variance
    threshold_mul   : user-tunable multiplier applied to baseline → threshold
    occupied_since  : Unix timestamp when motion was first confirmed, or ``None``
    session         : dict with session-level statistics (see :func:`make_session`)
    subcarriers     : per-sensitive-subcarrier variance list (length = len(SENSITIVE))
    heatmap         : hourly motion-event counts (length 24)
    calibrating     : ``True`` during the calibration phase
    activity        : current activity label (e.g. ``"walking"``)
    activity_conf   : classifier confidence in ``[0.0, 1.0]``
    """
    return {
        "variance":       0.0,
        "status":         "clear",
        "threshold":      0.0,
        "baseline":       0.0,
        "threshold_mul":  DEFAULT_THRESHOLD_MUL,
        "occupied_since": None,
        "session":        make_session(),
        "subcarriers":    [0.0] * len(SENSITIVE),
        "heatmap":        [0] * 24,
        "calibrating":    True,
        "activity":       "unknown",
        "activity_conf":  0.0,
    }
