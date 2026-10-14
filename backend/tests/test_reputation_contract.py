import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from components.reputation.model import AccountReputationAssessment
from components.reputation.schemas import ReputationAIAssessment
from components.reputation.service import ensure_space_creation_privilege


class ReputationContractTests(unittest.TestCase):
    def test_reputation_is_bound_to_account_not_persona(self):
        targets = {
            foreign_key.target_fullname
            for foreign_key in AccountReputationAssessment.__table__.c.account_uid.foreign_keys
        }
        self.assertEqual(targets, {"accounts.uid"})
        self.assertFalse(hasattr(AccountReputationAssessment, "persona_uid"))

    def test_ai_assessment_is_structured_and_bounded(self):
        assessment = ReputationAIAssessment(
            overall_label="trusted",
            confidence_percent=91,
            dimensions={
                "conversation_quality": "high",
                "helpfulness": "high",
                "organizer_potential": "high",
                "conflict_risk": "low",
            },
            space_creation_eligible=True,
            max_owned_active_spaces=1,
            rationale="Stable constructive participation over time.",
        )
        self.assertTrue(assessment.space_creation_eligible)
        self.assertEqual(assessment.max_owned_active_spaces, 1)

        with self.assertRaises(ValidationError):
            ReputationAIAssessment(
                overall_label="trusted",
                confidence_percent=101,
                space_creation_eligible=True,
                max_owned_active_spaces=1,
            )

    def test_ineligible_assessment_denies_space_creation(self):
        account_uid = uuid4()
        account = SimpleNamespace(uid=account_uid, legacy_user_uid=uuid4())
        assessment = SimpleNamespace(
            space_creation_eligible=False,
            overall_label="developing",
            valid_until=datetime.utcnow() + timedelta(hours=1),
            max_owned_active_spaces=0,
        )
        db = MagicMock()

        with patch(
            "components.reputation.service.get_current_reputation_assessment",
            new=AsyncMock(return_value=assessment),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(ensure_space_creation_privilege(db, account))

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            raised.exception.detail["error_type"],
            "space_creation_privilege_required",
        )

    def test_eligible_assessment_enforces_owned_space_limit(self):
        account_uid = uuid4()
        account = SimpleNamespace(uid=account_uid, legacy_user_uid=uuid4())
        assessment = SimpleNamespace(
            space_creation_eligible=True,
            overall_label="trusted",
            valid_until=datetime.utcnow() + timedelta(hours=1),
            max_owned_active_spaces=1,
        )
        scalar_result = MagicMock()
        scalar_result.scalar_one.return_value = 1
        db = MagicMock()
        db.execute = AsyncMock(return_value=scalar_result)

        with patch(
            "components.reputation.service.get_current_reputation_assessment",
            new=AsyncMock(return_value=assessment),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(ensure_space_creation_privilege(db, account))

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            raised.exception.detail["error_type"],
            "space_creation_limit_reached",
        )

    def test_eligible_assessment_under_limit_allows_creation(self):
        account_uid = uuid4()
        account = SimpleNamespace(uid=account_uid, legacy_user_uid=uuid4())
        assessment = SimpleNamespace(
            space_creation_eligible=True,
            overall_label="trusted",
            valid_until=datetime.utcnow() + timedelta(hours=1),
            max_owned_active_spaces=1,
        )
        scalar_result = MagicMock()
        scalar_result.scalar_one.return_value = 0
        db = MagicMock()
        db.execute = AsyncMock(return_value=scalar_result)

        with patch(
            "components.reputation.service.get_current_reputation_assessment",
            new=AsyncMock(return_value=assessment),
        ):
            result = asyncio.run(ensure_space_creation_privilege(db, account))

        self.assertIs(result, assessment)


if __name__ == "__main__":
    unittest.main()
