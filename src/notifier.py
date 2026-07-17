"""
notifier.py — send a Telegram alert when a card's archive step has been
failing repeatedly. Mirrors pax-vm's notifier.py pattern for consistency
(same VM, same alert channel). Failure to notify is non-blocking: callers
log and continue, never crash the sync run over a failed alert.
"""
import logging

import requests

from src.config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

logger = logging.getLogger("sync")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def alert(message: str) -> bool:
    """Send a Telegram alert. Returns True on success, False on failure
    (including when Telegram isn't configured — that's a warning, not a
    crash)."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping alert: %s", message)
        return False
    try:
        resp = requests.post(
            TELEGRAM_API,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Telegram alert sent")
        return True
    except Exception as exc:
        logger.warning("Telegram alert failed: %s", exc)
        return False
