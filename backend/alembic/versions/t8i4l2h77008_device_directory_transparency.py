"""add append-only device directory transparency journal

Revision ID: t8i4l2h77008
Revises: s7h3k1g66007
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "t8i4l2h77008"
down_revision: Union[str, None] = "s7h3k1g66007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GENESIS_HASH = "0" * 64
VERSION = "pubchat-device-directory-v1"


def _key_bytes(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _fingerprint(signing: str, dh: str) -> str:
    digest = hashlib.sha256(
        b"pubchat-device-identity-v1\x00" + _key_bytes(signing) + _key_bytes(dh)
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _hash(domain: bytes, value) -> str:
    return hashlib.sha256(domain + b"\x00" + _canonical_json(value)).hexdigest()


def _directory_hash(rows: list[dict]) -> str:
    entries = sorted(rows, key=lambda item: item["device_uid"])
    return _hash(b"pubchat-device-directory-snapshot-v1", entries)


def upgrade() -> None:
    op.create_table(
        "device_directory_events",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("device_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("identity_signing_key", sa.Text(), nullable=True),
        sa.Column("identity_dh_key", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("directory_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("account_uid", "sequence", name="uq_device_directory_event_sequence"),
        sa.UniqueConstraint("account_uid", "event_hash", name="uq_device_directory_event_hash"),
    )
    op.create_index(
        "ix_device_directory_events_account_sequence",
        "device_directory_events",
        ["account_uid", "sequence"],
        unique=False,
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT account_uid, uid, key_version, identity_signing_key, identity_dh_key, revoked_at
            FROM device_cryptographic_identities
            ORDER BY account_uid, uid
            """
        )
    ).mappings().all()
    account_uids = sorted({str(row["account_uid"]) for row in rows})
    now = datetime.utcnow()
    for account_uid in account_uids:
        active = []
        for row in rows:
            if str(row["account_uid"]) != account_uid or row["revoked_at"] is not None:
                continue
            active.append(
                {
                    "device_uid": str(row["uid"]),
                    "key_version": int(row["key_version"] or 1),
                    "fingerprint": _fingerprint(row["identity_signing_key"], row["identity_dh_key"]),
                    "identity_signing_key": row["identity_signing_key"],
                    "identity_dh_key": row["identity_dh_key"],
                }
            )
        directory_hash = _directory_hash(active)
        payload = {
            "version": VERSION,
            "account_uid": account_uid,
            "sequence": 1,
            "event_type": "bootstrap",
            "device": None,
            "previous_hash": GENESIS_HASH,
            "directory_hash": directory_hash,
        }
        event_hash = _hash(b"pubchat-device-directory-event-v1", payload)
        connection.execute(
            sa.text(
                """
                INSERT INTO device_directory_events
                    (uid, account_uid, sequence, event_type, device_uid, key_version,
                     fingerprint, identity_signing_key, identity_dh_key, previous_hash,
                     directory_hash, event_hash, created_at)
                VALUES
                    (:uid, :account_uid, 1, 'bootstrap', NULL, NULL,
                     NULL, NULL, NULL, :previous_hash,
                     :directory_hash, :event_hash, :created_at)
                """
            ),
            {
                "uid": str(uuid4()),
                "account_uid": account_uid,
                "previous_hash": GENESIS_HASH,
                "directory_hash": directory_hash,
                "event_hash": event_hash,
                "created_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_device_directory_events_account_sequence", table_name="device_directory_events")
    op.drop_table("device_directory_events")
