"""
src.alerts
==========
Outbound notification helpers.

Currently implements Telegram push notifications; extend this module to add
email, Slack, PagerDuty, or any other channel without touching server.py.
"""

import time

import requests

from src.config import COOLDOWN_SECS, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

# Tracks the timestamp of the last alert sent so we respect COOLDOWN_SECS
_last_alert_ts: float = 0.0


def send_telegram(message: str, mute_until: float = 0.0) -> bool:
    """
    Send a Telegram message to the configured chat.

    Parameters
    ----------
    message:
        Plain-text message body (≤ 4096 characters for Telegram).
    mute_until:
        Unix timestamp.  If ``time.time() < mute_until`` the call is a no-op
        (allows the caller to implement a mute window without knowing the
        implementation details here).

    Returns
    -------
    ``True`` if the HTTP request was sent (not necessarily delivered),
    ``False`` if skipped due to muting / missing credentials / cooldown.

    Notes
    -----
    - Failed HTTP calls are swallowed silently so a network outage never
      crashes the main CSI loop.
    - The per-process cooldown counter (``_last_alert_ts``) is module-level,
      so all call-sites share the same rate limit.
    """
    global _last_alert_ts

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    now = time.time()
    if now < mute_until:
        return False
    if now - _last_alert_ts < COOLDOWN_SECS:
        return False

    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=3,
        )
        _last_alert_ts = now
        return True
    except Exception:
        return False
