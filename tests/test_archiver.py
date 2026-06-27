import sys
import unittest
from unittest.mock import MagicMock, patch

_mock_config = MagicMock()
_mock_config.TRELLO_AUTH = {"key": "fakekey", "token": "faketoken"}
sys.modules["src.config"] = _mock_config

import requests  # noqa: E402
from src.archiver import archive_card  # noqa: E402

CARD_ID = "abc123"
CARD_NAME = "My Card"


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(status_code):
    resp = MagicMock()
    resp.status_code = status_code
    http_err = requests.HTTPError(response=resp)
    resp.raise_for_status = MagicMock(side_effect=http_err)
    return resp


def _rate_limit_response():
    resp = MagicMock()
    resp.status_code = 429
    resp.raise_for_status = MagicMock()
    return resp


class TestArchiveCard(unittest.TestCase):

    @patch("src.archiver.requests.put")
    def test_happy_path_returns_success(self, mock_put):
        mock_put.return_value = _ok_response()
        result = archive_card(CARD_ID, CARD_NAME)

        self.assertTrue(result["success"])
        self.assertEqual(result["card_id"], CARD_ID)
        self.assertIn("Archived", result["message"])
        self.assertIn(CARD_NAME, result["message"])

    @patch("src.archiver.requests.put")
    def test_correct_url_and_closed_param(self, mock_put):
        mock_put.return_value = _ok_response()
        archive_card(CARD_ID, CARD_NAME)

        call_kwargs = mock_put.call_args
        url = call_kwargs[0][0]
        params = call_kwargs[1]["params"]

        self.assertIn(CARD_ID, url)
        self.assertEqual(params["closed"], "true")
        self.assertEqual(params["key"], "fakekey")
        self.assertEqual(params["token"], "faketoken")

    @patch("src.archiver.requests.put")
    def test_http_error_returns_failure(self, mock_put):
        mock_put.return_value = _error_response(401)
        result = archive_card(CARD_ID, CARD_NAME)

        self.assertFalse(result["success"])
        self.assertEqual(result["card_id"], CARD_ID)
        self.assertIn("401", result["message"])

    @patch("src.archiver.requests.put")
    def test_network_exception_returns_failure(self, mock_put):
        mock_put.side_effect = requests.ConnectionError("timeout")
        result = archive_card(CARD_ID, CARD_NAME)

        self.assertFalse(result["success"])
        self.assertIn("Network error", result["message"])

    @patch("src.archiver.requests.put")
    def test_card_name_optional_falls_back_to_id(self, mock_put):
        mock_put.return_value = _ok_response()
        result = archive_card(CARD_ID)

        self.assertTrue(result["success"])
        self.assertIn(CARD_ID, result["message"])


class TestArchiveCardRetry(unittest.TestCase):

    @patch("src.archiver.time.sleep")
    @patch("src.archiver.requests.put")
    def test_retries_on_429_then_succeeds(self, mock_put, mock_sleep):
        mock_put.side_effect = [_rate_limit_response(), _ok_response()]
        result = archive_card(CARD_ID, CARD_NAME)

        self.assertTrue(result["success"])
        self.assertEqual(mock_put.call_count, 2)
        mock_sleep.assert_called_once_with(1)  # 2^0 = 1

    @patch("src.archiver.time.sleep")
    @patch("src.archiver.requests.put")
    def test_all_attempts_rate_limited_returns_failure(self, mock_put, mock_sleep):
        mock_put.return_value = _rate_limit_response()
        result = archive_card(CARD_ID, CARD_NAME, max_retries=3)

        self.assertFalse(result["success"])
        self.assertIn("Rate limited", result["message"])
        self.assertEqual(mock_put.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # sleep after attempt 0 and 1, not 2

    @patch("src.archiver.time.sleep")
    @patch("src.archiver.requests.put")
    def test_backoff_increases_exponentially(self, mock_put, mock_sleep):
        mock_put.side_effect = [
            _rate_limit_response(),
            _rate_limit_response(),
            _ok_response(),
        ]
        archive_card(CARD_ID, CARD_NAME, max_retries=3)

        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        self.assertEqual(sleep_calls, [1, 2])  # 2^0, 2^1


if __name__ == "__main__":
    unittest.main()
