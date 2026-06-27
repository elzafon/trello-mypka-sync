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
    print("❌ Missing required env vars:")
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

PKA_REPO_PATH = os.getenv("PKA_REPO_PATH")

TRELLO_AUTH = {"key": TRELLO_API_KEY, "token": TRELLO_TOKEN}
