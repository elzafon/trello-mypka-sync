#!/usr/bin/env python3
import os
import sys

from src.config import PKA_REPO_PATH
from src.fetcher import fetch_cards
from src.parser import parse_card
from src.writer import write_card
from src.git_push import push_cards, pull_rebase
from src.archiver import archive_card
from src.guardrail import record_failure, record_success
from src.logger import setup_logger, log_event
from src.notifier import alert

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "sync.log")


def _flag_repeat_failure(card_id, card_name, stage):
    """Bump the consecutive-failure counter for card_id; alert once per
    threshold crossing so a stuck card can't fail silently for days
    (see tsk-2026-07-17-001)."""
    count, should_alert = record_failure(card_id, card_name, stage)
    if should_alert:
        alert(
            f"⚠️ trello-mypka-sync: card \"{card_name}\" ({card_id}) has "
            f"failed to archive for {count} consecutive runs (last failure at "
            f"the {stage} step). It will keep re-syncing duplicate content "
            f"until this is fixed — check ~/trello-mypka-sync/logs/sync.log."
        )


def _exit_if_write_failures(logger, failed_cards):
    """Exit 1 if any card failed to parse/write this run.

    Called at every exit path of run() that would otherwise fall through to a
    0 exit. Cards that DID write have already been pushed and archived by the
    time this runs, so exiting here loses nothing — it only stops the run from
    claiming success it didn't have.
    """
    if not failed_cards:
        return
    summary = ", ".join(f'{cid} ("{name}")' for cid, name in failed_cards)
    logger.error(
        f"=== Sync finished with {len(failed_cards)} card(s) that failed to "
        f"write: {summary} — exiting 1 ==="
    )
    sys.exit(1)


def run():
    logger = setup_logger(LOG_PATH)
    logger.info("=== Sync started ===")

    pull_result = pull_rebase()
    if not pull_result["success"]:
        logger.warning(
            f"git pull --rebase failed at sync start: {pull_result['message']} "
            "— continuing, push may be skipped this run"
        )

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
    # Cards that raised in parse/write. A run with any of these must NOT exit 0:
    # /sync-trello treats the exit code as the single honest signal of the run,
    # and before 2026-09-25 a card that failed to write (e.g. an over-long
    # filename) was logged as ERROR while the process still exited 0 — a partial
    # failure reported as success. One bad card still does not abort the run:
    # the others write, push and archive exactly as before; only the final exit
    # status changes.
    failed_cards = []
    for card in cards:
        try:
            target_path, fm, body = parse_card(card)
            write_card(target_path, fm, body)
            written.append((card, target_path))
            log_event(logger, card["card_id"], card["name"], "write", target_path)
        except Exception as exc:
            failed_cards.append((card.get("card_id", "?"), card.get("name", "?")))
            log_event(
                logger, card["card_id"], card.get("name", "?"),
                "write", str(exc), success=False,
            )

    if not written:
        logger.info("No files written.")
        _exit_if_write_failures(logger, failed_cards)
        return

    file_paths = [p for _, p in written]
    card_names = [c["name"] for c, _ in written]
    push_result = push_cards(file_paths, card_names)

    if not push_result["success"]:
        log_event(logger, "—", "—", "git_push", push_result["message"], success=False)
        logger.error("Git push failed — cards will NOT be archived. Retry next run.")
        for card, _ in written:
            _flag_repeat_failure(card["card_id"], card["name"], "push")
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
        if result["success"]:
            record_success(card["card_id"])
        else:
            _flag_repeat_failure(card["card_id"], card["name"], "archive")

    logger.info(f"=== Sync complete: {len(written)} card(s) processed ===")
    _exit_if_write_failures(logger, failed_cards)


if __name__ == "__main__":
    run()
