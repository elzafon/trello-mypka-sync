import logging
import logging.handlers
import os

_LOG_FORMAT = "%(asctime)s %(levelname)-5s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def setup_logger(log_path, name="sync"):
    """
    Return a logger writing to a rotating file at log_path.
    Safe to call multiple times — returns the same logger on repeat calls.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(handler)
    return logger


def log_event(logger, card_id, card_name, action, result, success=True):
    """Write one structured log line for a card action."""
    msg = f'card_id={card_id} name="{card_name}" action={action} result={result}'
    if success:
        logger.info(msg)
    else:
        logger.error(msg)
