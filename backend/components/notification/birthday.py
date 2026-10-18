"""Consent-gated in-app reminders for friends' birthdays.

The birthday's year and the underlying date are never returned to other users.
No external provider or third-party SDK is used by this generator. Delivery
through APNs/FCM/Web Push is an independent, OS-managed transport.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import and_, extract, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from components.identity.model import Account, AccountRelationship, Persona, PrivacySettings
from components.notification.model import MessageNotificationPreference, UserNotification

BIRTHDAY_KIND = "friend_birthday"
MAX_BIRTHDAYS_PER_ACCOUNT = 250


def birthday_occurs_on(born: date, today: date) -> bool:
    """People born Feb 29 are celebrated Feb 28 in non-leap years."""
    if born.month == today.month and born.day == today.day:
        return True
    leap_year = today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
    return born.month == 2 and born.day == 29 and today.month == 2 and today.day == 28 and not leap_year


async def sync_friend_birthdays(
    db: AsyncSession, viewer_uid: UUID | str, *, now: datetime | None = None
) -> int:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = current.date()
    viewer = UUID(str(viewer_uid))

    # Recipient must explicitly opt in. No setting means no reminder.
    preference = await db.get(MessageNotificationPreference, viewer, with_for_update=True)
    if not preference or not preference.friend_birthday_reminders:
        return 0

    # A mutual friend relationship is mandatory, independent of public discovery.
    forward = aliased(AccountRelationship)
    reciprocal = aliased(AccountRelationship)
    ban = aliased(AccountRelationship)
    # Distinct aliases are necessary: reusing the joined friendship table
    # would correlate away the reverse-friend/block EXISTS clauses.
    mutual = select(reciprocal.id).where(
        reciprocal.from_account_uid == Persona.account_uid,
        reciprocal.to_account_uid == viewer,
        reciprocal.relation_type == "friend",
    ).exists()
    blocked = select(ban.id).where(
        ban.relation_type == "block",
        or_(
            and_(ban.from_account_uid == viewer,
                 ban.to_account_uid == Persona.account_uid),
            and_(ban.from_account_uid == Persona.account_uid,
                 ban.to_account_uid == viewer),
        ),
    ).exists()

    matches_today = and_(
        extract("month", Persona.date_of_birth) == today.month,
        extract("day", Persona.date_of_birth) == today.day,
    )
    leap_year = today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
    if today.month == 2 and today.day == 28 and not leap_year:
        matches_today = or_(
            matches_today,
            and_(extract("month", Persona.date_of_birth) == 2,
                 extract("day", Persona.date_of_birth) == 29),
        )

    result = await db.execute(
        select(Persona)
        .join(Account, Account.uid == Persona.account_uid)
        .join(PrivacySettings, PrivacySettings.persona_uid == Persona.uid)
        .join(forward, and_(
            forward.to_account_uid == Persona.account_uid,
            forward.from_account_uid == viewer,
            forward.relation_type == "friend",
        ))
        .where(
            Persona.account_uid != viewer,
            Persona.is_primary.is_(True),
            Persona.date_of_birth.is_not(None),
            Account.status == "active",
            Account.deleted_at.is_(None),
            PrivacySettings.share_birthday_with_friends.is_(True),
            mutual,
            ~blocked,
            matches_today,
        )
        .order_by(Persona.account_uid)
        .limit(MAX_BIRTHDAYS_PER_ACCOUNT)
        .with_for_update(of=PrivacySettings)
    )
    count = 0
    for person in result.scalars().all():
        dedupe = f"friend_birthday:{person.account_uid}:{today.isoformat()}"
        # Year of birth, exact date and other personal data are never included.
        await db.execute(
            insert(UserNotification)
            .values(
                account_uid=viewer,
                kind=BIRTHDAY_KIND,
                dedupe_key=dedupe,
                title=f"Сегодня день рождения у {person.display_name[:80]}",
                body="Можете поздравить друга в PubChat.",
                created_at=current.replace(tzinfo=None),
            )
            .on_conflict_do_nothing(constraint="uq_user_notification_dedupe")
        )
        count += 1
    await db.commit()
    return count
