from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Index, UniqueConstraint, and_, desc, asc, func, or_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, joinedload
from sqlalchemy.future import select
from datetime import datetime
from uuid import uuid4
from utils.logger import setup_logger
from database import Database

# Configure the logger
logger = setup_logger(__name__)

class Message(Database.Base):
    __tablename__ = "messages"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    content_type = Column(String(50), nullable=False)
    front_id = Column(String(128), nullable=True)
    text = Column(String(1000))
    media_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с комнатой
    room_uid = Column(UUID(as_uuid=True), ForeignKey("rooms.uid"))
    room = relationship("Room", back_populates="messages")

    # Связь с автором
    author_uid = Column(UUID(as_uuid=True), ForeignKey("users.uid"))
    author = relationship("User", foreign_keys=[author_uid], back_populates="messages")

    # Поля для ответа на сообщение
    reply_to_uid = Column(UUID(as_uuid=True), ForeignKey("messages.uid"), nullable=True)
    reply_to = relationship("Message", remote_side=[uid], foreign_keys=[reply_to_uid], post_update=True)

    __table_args__ = (
        Index("ix_messages_discovery_recent", "created_at", "room_uid", "author_uid"),
        UniqueConstraint("room_uid", "author_uid", "front_id", name="uq_room_message_client_id"),
    )

    def __repr__(self):
        return f"<Message(uid={self.uid}, type={self.content_type}, room={self.room_uid})>"
    
    @staticmethod
    def format_message(msg, include_reply_details=True):
        """Форматирует сообщение для отправки клиенту"""
        if not msg:
            return None

        # Если сообщение уже словарь (например, из кеша), возвращаем его как есть
        if isinstance(msg, dict):
            return msg

        # Форматируем данные сообщения
        formatted = {
            "type": "message",
            "uid": str(msg.uid),
            "frontId": getattr(msg, "front_id", None),
            "content": msg.text,
            "content_type": msg.content_type,
            "media_metadata": msg.media_metadata,
            "sender": {
                "uid": str(msg.author_uid),
                "username": getattr(msg.author, "username", "Unknown"),
                "avatar": getattr(msg.author, "avatar", None),
            },
            "room_uid": str(msg.room_uid),
            "created_at": msg.created_at.isoformat(),
        }

        # Добавляем информацию о сообщении-ответе, если требуется
        if include_reply_details and msg.reply_to:
            formatted["reply_to"] = {
                "uid": str(msg.reply_to.uid),
                "content": msg.reply_to.text,
                "sender": {
                    "uid": str(msg.reply_to.author_uid),
                    "name": getattr(msg.reply_to.author, "username", "Unknown"),
                },
            }

        return formatted

    @staticmethod
    async def create_message(db_session: AsyncSession, message_data: dict):
        """
        Создает новое сообщение и сохраняет его в базу данных асинхронно.
        """
        try:
            # Создаем новый объект Message
            new_message = Message(
                content_type=message_data.get("content_type", "text"),
                text=message_data.get("content"),
                media_metadata=message_data.get("media_metadata"),
                room_uid=message_data.get("room_uid"),
                author_uid=message_data.get("sender_uid"),
                reply_to_uid=message_data.get("reply_to_uid"),
                created_at=datetime.utcnow()
            )

            db_session.add(new_message)
            # Resolve the message and all quoted author fields BEFORE commit.
            # On an ORM formatting failure, the rollback will remove the write
            # rather than leave an invisible, already committed "ghost" reply.
            await db_session.flush()
            await db_session.refresh(new_message)

            # Load the parent message AND its author in the async query context.
            # refresh(..., ["reply_to"]) loads only the first relationship;
            # touching reply_to.author during synchronous formatting otherwise
            # triggers MissingGreenlet for replies to another person's message.
            result = await db_session.execute(
                select(Message)
                .options(
                    joinedload(Message.author),
                    joinedload(Message.reply_to).joinedload(Message.author),
                )
                .where(Message.uid == new_message.uid)
            )
            formatted = Message.format_message(result.scalar_one())
            await db_session.commit()
            return formatted

        except Exception as e:
            logger.error(f"Error creating message: {e}")
            await db_session.rollback()
            raise

    @staticmethod
    async def get_last_messages(db_session: AsyncSession, room_uid: UUID, limit: int = 5) -> List["Message"]:
        """
        Возвращает последние сообщения для указанной комнаты асинхронно.
        """
        try:
            stmt = (
                select(Message)
                .options(
                    joinedload(Message.author),
                    joinedload(Message.reply_to).joinedload(Message.author)
                )
                .filter(Message.room_uid == str(room_uid))
                .order_by(desc(Message.created_at))
                .limit(limit)
            )
            
            result = await db_session.execute(stmt)
            messages = result.scalars().all()

            return [Message.format_message(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Error fetching last messages: {e}")
            raise


class PrivateMessage(Database.Base):
    __tablename__ = "private_messages"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    front_id = Column(String(128), nullable=True)
    content_type = Column(String(50), nullable=False)
    text = Column(String(1000))
    media_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    # Связь с отправителем
    sender_uid = Column(UUID(as_uuid=True), ForeignKey("users.uid"))
    sender = relationship("User", foreign_keys=[sender_uid], back_populates="sent_private_messages")

    # Связь с получателем
    receiver_uid = Column(UUID(as_uuid=True), ForeignKey("users.uid"))
    receiver = relationship("User", foreign_keys=[receiver_uid], back_populates="received_private_messages")

    __table_args__ = (
        UniqueConstraint("sender_uid", "receiver_uid", "front_id", name="uq_private_message_client_id"),
    )

    def __repr__(self):
        return f"<PrivateMessage(uid={self.uid}, sender={self.sender_uid}, receiver={self.receiver_uid})>"
    
    @staticmethod
    def format_message(msg, include_sender_details=True):
        """Форматирует приватное сообщение для отправки клиенту"""
        if not msg:
            return None

        if isinstance(msg, dict):
            return msg

        formatted = {
            "type": "private_message",
            "uid": str(msg.uid),
            "frontId": getattr(msg, "front_id", None),
            "content": msg.text,
            "content_type": msg.content_type,
            "media_metadata": msg.media_metadata,
            "sender_uid": str(msg.sender_uid),
            "receiver_uid": str(msg.receiver_uid),
            "is_read": msg.is_read,
            "created_at": msg.created_at.isoformat()
        }

        if include_sender_details and msg.sender:
            formatted["sender"] = {
                "uid": str(msg.sender.uid),
                "username": getattr(msg.sender, "username", "Unknown"),
                "avatar": getattr(msg.sender, "avatar", None)
            }

        return formatted

    @staticmethod
    async def create_private_message(db_session: AsyncSession, message_data: dict):
        """
        Создает новое приватное сообщение асинхронно.
        """
        try:
            new_message = PrivateMessage(
                content_type=message_data.get("content_type", "text"),
                text=message_data.get("content"),
                media_metadata=message_data.get("media_metadata"),
                sender_uid=message_data.get("sender_uid"),
                receiver_uid=message_data.get("receiver_uid"),
                created_at=datetime.utcnow()
            )

            db_session.add(new_message)
            await db_session.commit()

            # Явно загружаем связанные объекты
            await db_session.refresh(new_message, attribute_names=["sender", "receiver"])

            return PrivateMessage.format_message(new_message)
        except Exception as e:
            logger.error(f"Error creating private message: {e}")
            await db_session.rollback()
            raise

    @staticmethod
    async def get_conversation(db_session: AsyncSession, user1_uid: UUID, user2_uid: UUID, limit: int = 50):
        """
        Возвращает переписку между двумя пользователями асинхронно.
        """
        try:
            stmt = (
                select(PrivateMessage)
                .options(joinedload(PrivateMessage.sender))
                .filter(
                    (PrivateMessage.sender_uid == str(user1_uid)) & 
                    (PrivateMessage.receiver_uid == str(user2_uid)) |
                    (PrivateMessage.sender_uid == str(user2_uid)) & 
                    (PrivateMessage.receiver_uid == str(user1_uid))
                )
                .order_by(desc(PrivateMessage.created_at))
                .limit(limit)
            )
            
            result = await db_session.execute(stmt)
            messages = result.scalars().all()

            return [PrivateMessage.format_message(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Error fetching conversation: {e}")
            raise

    @staticmethod
    async def mark_as_read(db_session: AsyncSession, message_uid: UUID):
        """
        Помечает сообщение как прочитанное асинхронно.
        """
        try:
            stmt = select(PrivateMessage).filter(PrivateMessage.uid == str(message_uid))
            result = await db_session.execute(stmt)
            message = result.scalar_one_or_none()
            
            if message:
                message.is_read = True
                await db_session.commit()
            return message
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            await db_session.rollback()
            raise

    @staticmethod
    async def get_dialogs(db_session: AsyncSession, current_user_uid: UUID):
        """Получаем список диалогов с последним сообщением асинхронно"""
        try:
            # Подзапрос для получения последних сообщений
            subquery = (
                select(
                    func.greatest(PrivateMessage.sender_uid, PrivateMessage.receiver_uid).label("dialog_id"),
                    func.max(PrivateMessage.created_at).label("last_message_time")
                )
                .where(
                    or_(
                        PrivateMessage.sender_uid == current_user_uid,
                        PrivateMessage.receiver_uid == current_user_uid
                    )
                )
                .group_by(func.greatest(PrivateMessage.sender_uid, PrivateMessage.receiver_uid))
                .subquery()
            )

            # Основной запрос для получения диалогов
            stmt = (
                select(
                    PrivateMessage,
                    subquery.c.last_message_time
                )
                .join(
                    subquery,
                    and_(
                        func.greatest(PrivateMessage.sender_uid, PrivateMessage.receiver_uid) == subquery.c.dialog_id,
                        PrivateMessage.created_at == subquery.c.last_message_time
                    )
                )
                .options(
                    joinedload(PrivateMessage.sender), 
                    joinedload(PrivateMessage.receiver)
                )
            )
            
            result = await db_session.execute(stmt)
            dialogs = result.all()

            formatted_dialogs = []
            for dialog, last_message_time in dialogs:
                partner_id = (
                    dialog.receiver_uid if dialog.sender_uid == current_user_uid
                    else dialog.sender_uid
                )

                # Подсчет непрочитанных сообщений
                unread_stmt = (
                    select(func.count())
                    .where(
                        PrivateMessage.sender_uid == partner_id,
                        PrivateMessage.receiver_uid == current_user_uid,
                        PrivateMessage.is_read == False
                    )
                )
                unread_result = await db_session.execute(unread_stmt)
                unread_count = unread_result.scalar()

                formatted_dialogs.append({
                    "partner_id": str(partner_id),
                    "last_message": "Зашифрованное сообщение" if dialog.content_type == "e2ee" else dialog.text,
                    "last_message_time": last_message_time.isoformat(),
                    "unread_count": unread_count,
                    "partner": {
                        "username": dialog.sender.username if dialog.sender_uid == partner_id else dialog.receiver.username,
                        "avatar": dialog.sender.avatar if dialog.sender_uid == partner_id else dialog.receiver.avatar
                    }
                })

            return formatted_dialogs
        except Exception as e:
            logger.error(f"Error fetching dialogs: {e}")
            raise