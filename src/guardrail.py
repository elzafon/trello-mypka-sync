"""
guardrail.py — consecutive-failure tracking, per card_id, so a card that
can't archive can't fail silently for days (see tsk-2026-07-17-001: the
same card failed to archive on every 15-minute tick for 13 days before
anyone noticed).

State is a tiny JSON file, not a database — one automation, one writer,
sequential cron ticks (never concurrent), so no locking is needed.
"""
import json
import os

STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "failure_state.json",
)

# Consecutive failed ticks before we alert once. 4 * 15min = ~1 hour —
# long enough to absorb a single transient blip, short enough that nobody
# waits 13 days to find out.
ALERT_THRESHOLD = 4


def _load():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def record_failure(card_id, card_name, stage):
    """
    Increment the consecutive-failure count for card_id.

    Returns (count, should_alert). should_alert is True exactly once per
    threshold crossing — it won't fire again on every subsequent tick,
    only the first time the count reaches ALERT_THRESHOLD, so a stuck
    card produces one alert, not one per 15 minutes forever.
    """
    state = _load()
    entry = state.get(card_id, {"count": 0, "alerted": False})
    entry["count"] = entry.get("count", 0) + 1
    entry["name"] = card_name
    entry["stage"] = stage
    should_alert = entry["count"] >= ALERT_THRESHOLD and not entry.get("alerted", False)
    if should_alert:
        entry["alerted"] = True
    state[card_id] = entry
    _save(state)
    return entry["count"], should_alert


def record_success(card_id):
    """Clear failure tracking for card_id once it succeeds (e.g. archives)."""
    state = _load()
    if card_id in state:
        del state[card_id]
        _save(state)
