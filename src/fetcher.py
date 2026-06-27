import requests
from src.config import TRELLO_AUTH, TRELLO_LISTS

BASE_URL = "https://api.trello.com/1"


def fetch_cards():
    """Fetch all open (non-archived) cards from the configured myPKA lists."""
    cards = []
    for list_name, list_id in TRELLO_LISTS.items():
        resp = requests.get(
            f"{BASE_URL}/lists/{list_id}/cards",
            params={
                **TRELLO_AUTH,
                "fields": "name,desc,url,dateLastActivity,labels",
                "attachments": "true",
                "attachment_fields": "name,url",
            },
        )
        resp.raise_for_status()
        for card in resp.json():
            cards.append({
                "card_id": card["id"],
                "name": card["name"],
                "desc": card.get("desc", ""),
                "list_name": list_name,
                "labels": [lbl.get("name", "") for lbl in card.get("labels", [])],
                "attachments": [
                    {"name": a.get("name", ""), "url": a["url"]}
                    for a in card.get("attachments", [])
                    if a.get("url")
                ],
                "url": card["url"],
                "date_modified": card["dateLastActivity"],
            })
    return cards
