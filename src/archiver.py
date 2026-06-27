import time

import requests

from src.config import TRELLO_AUTH

BASE_URL = "https://api.trello.com/1"


def archive_card(card_id, card_name="", max_retries=3):
    """
    Archive a single Trello card by setting closed=true.
    Retries up to max_retries times on HTTP 429 (rate limit) with exponential backoff.

    Returns:
        dict: {success: bool, card_id: str, message: str}
    """
    label = card_name or card_id
    for attempt in range(max_retries):
        try:
            resp = requests.put(
                f"{BASE_URL}/cards/{card_id}",
                params={**TRELLO_AUTH, "closed": "true"},
            )
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {
                    "success": False,
                    "card_id": card_id,
                    "message": f"Rate limited after {max_retries} attempts: {label}",
                }
            resp.raise_for_status()
            return {"success": True, "card_id": card_id, "message": f"Archived: {label}"}
        except requests.HTTPError as exc:
            return {
                "success": False,
                "card_id": card_id,
                "message": f"Trello API error {exc.response.status_code}: {label}",
            }
        except requests.RequestException as exc:
            return {
                "success": False,
                "card_id": card_id,
                "message": f"Network error archiving {label}: {exc}",
            }
