import requests

from src.config import TRELLO_AUTH

BASE_URL = "https://api.trello.com/1"


def archive_card(card_id, card_name=""):
    """
    Archive a single Trello card by setting closed=true.

    Args:
        card_id:   Trello card ID string
        card_name: human-readable name for log messages (optional)

    Returns:
        dict: {success: bool, card_id: str, message: str}
    """
    label = card_name or card_id
    try:
        resp = requests.put(
            f"{BASE_URL}/cards/{card_id}",
            params={**TRELLO_AUTH, "closed": "true"},
        )
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
