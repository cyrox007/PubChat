import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app import app
from components.auth.permissions import require_admin
from components.space.category_model import SpaceCategory, SpaceCategoryAssignment, SpaceCategoryAudit
from components.space.category_schemas import CategoryCreate, CategoryUpdate
from components.space.category_service import validate_categories
from components.space.schemas import SpaceCreateRequest, SpaceUpdateRequest


class SpaceCategoryContractTests(unittest.TestCase):
    def test_new_routes_and_static_route_order(self):
        routes = [route.path for route in app.routes]
        for route in (
            "/spaces/v1/categories",
            "/admin/space-categories",
            "/admin/space-categories/audit",
            "/admin/space-categories/{slug}",
        ):
            self.assertIn(route, routes)
        self.assertLess(routes.index("/spaces/v1/categories"), routes.index("/spaces/v1/{space_uid}"))

    def test_admin_mutations_are_guarded_by_server_rbac(self):
        for route in app.routes:
            if not route.path.startswith("/admin/space-categories"):
                continue
            dependants = list(getattr(route.dependant, "dependencies", ()))
            self.assertTrue(
                any(dep.call is require_admin for dep in dependants),
                f"{route.path} must verify RBAC, not a browser JWT flag",
            )

    def test_taxonomy_is_not_legacy_purpose_or_tags(self):
        payload = SpaceCreateRequest(
            name="Дизайн-сообщество", purpose="conversation",
            tags=["UX", "Исследования"], category_slugs=["design", "technology"],
        )
        self.assertEqual(payload.purpose, "conversation")
        self.assertEqual(payload.tags, ["UX", "Исследования"])
        self.assertEqual(payload.category_slugs, ["design", "technology"])

    def test_create_update_slugs_are_bounded_and_deduplicated(self):
        self.assertEqual(
            SpaceCreateRequest(name="Чат о дизайне", category_slugs=["design", "design"]).category_slugs,
            ["design"],
        )
        self.assertEqual(
            SpaceUpdateRequest(category_slugs=[]).category_slugs, [],
        )
        for value in (
            ["bad slug"], ["../other"], ["Category"], ["valid"] * 4,
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SpaceCreateRequest(name="Пространство", category_slugs=value)

    def test_admin_payload_does_not_allow_rewriting_category_slug(self):
        self.assertNotIn("slug", CategoryUpdate.model_fields)
        self.assertEqual(CategoryCreate(slug="design", name="Дизайн").locale, "ru")
        with self.assertRaises(ValidationError):
            CategoryCreate(slug="Привет", name="Дизайн")

    def test_active_category_required_for_assignment(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["design"]
        db = MagicMock()
        db.execute = AsyncMock(return_value=result)
        asyncio.run(validate_categories(db, ["design"]))
        with self.assertRaises(HTTPException) as error:
            asyncio.run(validate_categories(db, ["design", "inactive"]))
        self.assertEqual(error.exception.status_code, 422)

    def test_categories_are_non_destructive_and_audited(self):
        targets = {fk.target_fullname for fk in SpaceCategoryAssignment.__table__.c.room_uid.foreign_keys}
        self.assertEqual(targets, {"rooms.uid"})
        self.assertEqual(
            {fk.target_fullname for fk in SpaceCategoryAssignment.__table__.c.category_slug.foreign_keys},
            {"space_categories.slug"},
        )
        self.assertIn("archived_at", SpaceCategory.__table__.c)
        self.assertIn("actor_account_uid", SpaceCategoryAudit.__table__.c)
        self.assertNotIn("space_tags", {table.name for table in
            (SpaceCategory.__table__, SpaceCategoryAssignment.__table__, SpaceCategoryAudit.__table__)})


if __name__ == "__main__":
    unittest.main()
