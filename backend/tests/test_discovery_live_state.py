import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from components.space.live_state import get_spaces_live_state
from views.discovery.routers import _attach_live_state, _live_now_items


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

    def test_live_now_mode_filters_and_uses_explicit_live_order(self):
        quiet_uid = str(uuid4())
        presence_uid = str(uuid4())
        conversation_uid = str(uuid4())
        second_conversation_uid = str(uuid4())
        items = [
            {
                "uid": quiet_uid,
                "discovery": {"live": {"live": False, "present_count": 0, "conversation": {"active": False}}},
            },
            {
                "uid": presence_uid,
                "discovery": {"live": {"live": True, "present_count": 8, "conversation": {"active": False, "contributor_count": 0}}},
            },
            {
                "uid": conversation_uid,
                "discovery": {"live": {"live": True, "present_count": 1, "conversation": {"active": True, "contributor_count": 4}}},
            },
            {
                "uid": second_conversation_uid,
                "discovery": {"live": {"live": True, "present_count": 3, "conversation": {"active": True, "contributor_count": 2}}},
            },
        ]

        result = _live_now_items(items)

        self.assertEqual(
            [item["uid"] for item in result],
            [second_conversation_uid, conversation_uid, presence_uid],
        )

    def test_live_now_mode_preserves_organic_order_for_equal_signals(self):
        first_uid = str(uuid4())
        second_uid = str(uuid4())
        items = [
            {
                "uid": first_uid,
                "discovery": {"live": {"live": True, "present_count": 1, "conversation": {"active": True, "contributor_count": 2}}},
            },
            {
                "uid": second_uid,
                "discovery": {"live": {"live": True, "present_count": 1, "conversation": {"active": True, "contributor_count": 2}}},
            },
        ]

        self.assertEqual([item["uid"] for item in _live_now_items(items)], [first_uid, second_uid])

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

    @patch("components.space.live_state._conversation_state", new_callable=AsyncMock)
    @patch("components.space.live_state._presence_counts", new_callable=AsyncMock)
    @patch("components.space.live_state.list_spaces", new_callable=AsyncMock)
    async def test_internal_live_pool_can_expand_beyond_public_batch_limit(
        self,
        list_spaces,
        presence_counts,
        conversation_state,
    ):
        requested = [uuid4() for _ in range(140)]
        list_spaces.return_value = []
        presence_counts.return_value = ({}, True)
        conversation_state.return_value = {}

        await get_spaces_live_state(
            MagicMock(),
            viewer_uid=uuid4(),
            space_uids=requested,
            max_spaces=140,
        )

        self.assertEqual(len(list_spaces.await_args.kwargs["candidate_uids"]), 140)


if __name__ == "__main__":
    unittest.main()
