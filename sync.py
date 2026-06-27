#!/usr/bin/env python3
import os
import sys

from src.config import PKA_REPO_PATH
from src.fetcher import fetch_cards
from src.parser import parse_card
from src.writer import write_card
from src.git_push import push_cards
from src.archiver import archive_card
from src.logger import setup_logger, log_event

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "sync.log")


def run():
    logger = setup_logger(LOG_PATH)
    logger.info("=== Sync started ===")

    try:
        cards = fetch_cards()
    except Exception as exc:
        logger.error(f"fetch_cards failed: {exc}")
        sys.exit(1)

    if not cards:
        logger.info("No cards to sync.")
        return

    logger.info(f"Fetched {len(cards)} card(s)")

    written = []
    for card in cards:
        try:
            target_path, fm, body = parse_card(card)
            write_card(target_path, fm, body)
            written.append((card, target_path))
            log_event(logger, card["card_id"], card["name"], "write", target_path)
        except Exception as exc:
            log_event(
                logger, card["card_id"], card.get("name", "?"),
                "write", str(exc), success=False,
            )

    if not written:
        logger.info("No files written.")
        return

    file_paths = [p for _, p in written]
    card_names = [c["name"] for c, _ in written]
    push_result = push_cards(file_paths, card_names)

    if not push_result["success"]:
        log_event(logger, "—", "—", "git_push", push_result["message"], success=False)
        logger.error("Git push failed — cards will NOT be archived. Retry next run.")
        sys.exit(1)

    log_event(logger, "—", "—", "git_push", push_result["message"])

    for card, _ in written:
        result = archive_card(card["card_id"], card["name"])
        log_event(
            logger,
            card["card_id"],
            card["name"],
            "archive",
            result["message"],
            success=result["success"],
        )

    logger.info(f"=== Sync complete: {len(written)} card(s) processed ===")


if __name__ == "__main__":
    run()
