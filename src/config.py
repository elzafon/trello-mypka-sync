from dotenv import load_dotenv
import os
import sys

load_dotenv()

REQUIRED = [
    "TRELLO_API_KEY",
    "TRELLO_TOKEN",
    "TRELLO_BOARD_MYPKA",
    "TRELLO_LIST_TOPICS",
    "TRELLO_LIST_PROJECTS",
    "TRELLO_LIST_GOALS",
    "TRELLO_LIST_CRM",
    "TRELLO_LIST_INCOMING",
    "PKA_REPO_PATH",
]

missing = [v for v in REQUIRED if not os.getenv(v)]
if missing:
    print("[ERROR] Missing required env vars:")
    for v in missing:
        print(f"   - {v}")
    sys.exit(1)

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BOARD_MYPKA = os.getenv("TRELLO_BOARD_MYPKA")

TRELLO_LISTS = {
    "topics":   os.getenv("TRELLO_LIST_TOPICS"),
    "projects": os.getenv("TRELLO_LIST_PROJECTS"),
    "goals":    os.getenv("TRELLO_LIST_GOALS"),
    "crm":      os.getenv("TRELLO_LIST_CRM"),
    "incoming": os.getenv("TRELLO_LIST_INCOMING"),
}

if os.getenv("TRELLO_LIST_RESEARCH"):
    TRELLO_LISTS["research"] = os.getenv("TRELLO_LIST_RESEARCH")

# Optional — the `Journal` list (real day entries -> PKM/Journal/YYYY/MM/).
# Deliberately NOT in REQUIRED: `incoming` now routes to Team Inbox/ instead
# of PKM/Journal, and this list is what restores a direct path for genuine
# day entries. Keeping it optional means the sync keeps running unchanged
# until the Trello list is created and its id added here.
if os.getenv("TRELLO_LIST_JOURNAL"):
    TRELLO_LISTS["journal"] = os.getenv("TRELLO_LIST_JOURNAL")

PKA_REPO_PATH = os.getenv("PKA_REPO_PATH")

TRELLO_AUTH = {"key": TRELLO_API_KEY, "token": TRELLO_TOKEN}

# Optional — repeat-failure guardrail alerting (src/guardrail.py +
# src/notifier.py). Not in REQUIRED: if unset, notifier.alert() logs a
# warning and no-ops instead of crashing the sync run. Same bot/chat as
# pax-vm's alerts (see ~/pax-vm/.env) so alerts land in one place.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
