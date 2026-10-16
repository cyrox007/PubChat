import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from components.space.live_state import get_spaces_live_state
from views.discovery.routers import _attach_live_state


class DiscoveryLiveStateTests(unittest.IsolatedAsyncioTestCase):
    def test_attach_live_state_adds_current_activity_without_replacing_reasons(self):
        space_uid = str(uuid4())
        items = [
            {
                "uid": space_uid,
                "discovery": {
                    "reasons": [{"code": "intent_match", "label": "Подходит вашему текущему настрою"}]
                },
            }
        ]
        live_payload = {
            "spaces": [
                {
                    "space_uid": space_uid,
                    "present_count": 3,
                    "has_people_now": True,
                    "live": True,
                    "conversation": {"active": True},
                }
            ]
        }

        result = _attach_live_state(items, live_payload)

        discovery = result[0]["discovery"]
        self.assertEqual(discovery["live"]["present_count"], 3)
        self.assertEqual(discovery["reasons"][0]["code"], "live_conversation")
        self.assertEqual(discovery["reasons"][1]["code"], "live_presence")
        self.assertIn("intent_match", {item["code"] for item in discovery["reasons"]})

    @patch("components.space.live_state._conversation_state", new_callable=AsyncMock)
    @patch("components.space.live_state._presence_counts", new_callable=AsyncMock)
    @patch("components.space.live_state.list_spaces", new_callable=AsyncMock)
    async def test_live_state_only_projects_spaces_visible_to_viewer(
        self,
        list_spaces,
        presence_counts,
        conversation_state,
    ):
        visible_uid = uuid4()
        hidden_uid = uuid4()
        list_spaces.return_value = [{"uid": str(visible_uid)}]
        presence_counts.return_value = ({visible_uid: 2}, True)
        conversation_state.return_value = {
            visible_uid: {
                "active": True,
                "message_count": 4,
                "contributor_count": 2,
                "latest_at": None,
                "window_minutes": 10,
            }
        }

        result = await get_spaces_live_state(
            MagicMock(),
            viewer_uid=uuid4(),
            space_uids=[visible_uid, hidden_uid],
        )

        list_spaces.assert_awaited_once()
        requested_candidates = list_spaces.await_args.kwargs["candidate_uids"]
        self.assertEqual(requested_candidates, [visible_uid, hidden_uid])
        presence_counts.assert_awaited_once_with([visible_uid])
        conversation_state.assert_awaited_once()
        self.assertEqual([item["space_uid"] for item in result["spaces"]], [str(visible_uid)])
        self.assertEqual(result["spaces"][0]["present_count"], 2)
        self.assertTrue(result["spaces"][0]["conversation"]["active"])

    @patch("components.space.live_state._conversation_state", new_callable=AsyncMock)
    @patch("components.space.live_state._presence_counts", new_callable=AsyncMock)
    @patch("components.space.live_state.list_spaces", new_callable=AsyncMock)
    async def test_presence_failure_does_not_fake_zero_people(
        self,
        list_spaces,
        presence_counts,
        conversation_state,
    ):
        space_uid = uuid4()
        list_spaces.return_value = [{"uid": str(space_uid)}]
        presence_counts.return_value = ({}, False)
        conversation_state.return_value = {}

        result = await get_spaces_live_state(
            MagicMock(),
            viewer_uid=uuid4(),
            space_uids=[space_uid],
        )

        self.assertFalse(result["presence_available"])
        self.assertIsNone(result["spaces"][0]["present_count"])
        self.assertIsNone(result["spaces"][0]["has_people_now"])


if __name__ == "__main__":
    unittest.main()
