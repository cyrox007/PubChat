import unittest

from components.space.pulse import (
    CHAT_WINDOW_MINUTES,
    HISTORY_PREVIEW_LIMIT,
    LIVE_PEOPLE_PREVIEW_LIMIT,
    _conversation_state,
)


class SpacePulseContractTests(unittest.TestCase):
    def test_conversation_state_is_based_on_distinct_participation(self):
        self.assertEqual(_conversation_state(0, 0), "quiet")
        self.assertEqual(_conversation_state(2, 1), "warming")
        self.assertEqual(_conversation_state(3, 2), "active")
        self.assertEqual(_conversation_state(8, 4), "lively")

    def test_single_noisy_author_cannot_make_space_lively(self):
        self.assertEqual(_conversation_state(500, 1), "warming")

    def test_pulse_windows_are_intentionally_bounded(self):
        self.assertEqual(CHAT_WINDOW_MINUTES, 30)
        self.assertLessEqual(LIVE_PEOPLE_PREVIEW_LIMIT, 8)
        self.assertLessEqual(HISTORY_PREVIEW_LIMIT, 5)


if __name__ == "__main__":
    unittest.main()
