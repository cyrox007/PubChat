"""session-scoped active persona selection for Multi-Persona

Revision ID: v0k6n4j99010
Revises: u9j5m3i88009
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v0k6n4j99010"
down_revision: Union[str, None] = "u9j5m3i88009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL always means the account's primary Persona; old sessions and
    # legacy integrations keep their existing public identity.
    op.add_column(
        "identity_sessions",
        sa.Column("active_persona_uid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_identity_sessions_active_persona",
        "identity_sessions", "personas", ["active_persona_uid"], ["uid"],
        ondelete="SET NULL",
    )
    # A single canonical primary Persona per Account, enforced atomically.
    op.create_index(
        "uq_personas_one_primary_per_account",
        "personas", ["account_uid"], unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_personas_one_primary_per_account", table_name="personas")
    op.drop_constraint(
        "fk_identity_sessions_active_persona",
        "identity_sessions", type_="foreignkey",
    )
    op.drop_column("identity_sessions", "active_persona_uid")
