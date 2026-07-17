import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import src.guardrail as guardrail


class TestGuardrail(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_path = os.path.join(self._tmp.name, "state", "failure_state.json")
        self._patch = patch.object(guardrail, "STATE_PATH", self._state_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_first_failures_do_not_alert(self):
        for i in range(1, guardrail.ALERT_THRESHOLD):
            count, should_alert = guardrail.record_failure("card1", "Card One", "push")
            self.assertEqual(count, i)
            self.assertFalse(should_alert)

    def test_threshold_crossing_alerts_exactly_once(self):
        for _ in range(guardrail.ALERT_THRESHOLD - 1):
            guardrail.record_failure("card1", "Card One", "push")

        count, should_alert = guardrail.record_failure("card1", "Card One", "push")
        self.assertEqual(count, guardrail.ALERT_THRESHOLD)
        self.assertTrue(should_alert)

        # Keeps failing past the threshold — no repeat alert.
        count, should_alert = guardrail.record_failure("card1", "Card One", "push")
        self.assertEqual(count, guardrail.ALERT_THRESHOLD + 1)
        self.assertFalse(should_alert)

    def test_success_clears_state_so_future_failures_start_from_zero(self):
        for _ in range(guardrail.ALERT_THRESHOLD):
            guardrail.record_failure("card1", "Card One", "archive")

        guardrail.record_success("card1")

        count, should_alert = guardrail.record_failure("card1", "Card One", "archive")
        self.assertEqual(count, 1)
        self.assertFalse(should_alert)

    def test_success_on_untracked_card_is_a_no_op(self):
        guardrail.record_success("never-seen-card")  # should not raise
        self.assertFalse(os.path.exists(self._state_path))

    def test_failures_are_tracked_independently_per_card(self):
        guardrail.record_failure("card1", "Card One", "push")
        guardrail.record_failure("card1", "Card One", "push")
        guardrail.record_failure("card2", "Card Two", "push")

        with open(self._state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["card1"]["count"], 2)
        self.assertEqual(state["card2"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
