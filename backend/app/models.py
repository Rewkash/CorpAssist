from datetime import datetime
from enum import StrEnum

import json as _json

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(StrEnum):
    CLIENT = 'client'
    WORKER = 'worker'
    ADMIN = 'admin'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.CLIENT, index=True)
    assigned_worker_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    history: Mapped[list['MessageHistory']] = relationship(back_populates='user')
    assigned_worker: Mapped['User | None'] = relationship(remote_side='User.id', backref='clients')
    client_conversations: Mapped[list['Conversation']] = relationship(
        foreign_keys='Conversation.client_id',
        back_populates='client',
    )
    worker_conversations: Mapped[list['Conversation']] = relationship(
        foreign_keys='Conversation.worker_id',
        back_populates='worker',
    )


class MessageHistory(Base):
    __tablename__ = 'message_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    result_text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(32))
    topics: Mapped[str] = mapped_column(String(255))
    formality: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped[User] = relationship(back_populates='history')


class Conversation(Base):
    __tablename__ = 'conversations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default='Новый диалог')
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    tags: Mapped[str] = mapped_column(Text, default='[]')
    tags_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[User] = relationship(foreign_keys=[client_id], back_populates='client_conversations')
    worker: Mapped[User | None] = relationship(foreign_keys=[worker_id], back_populates='worker_conversations')
    messages: Mapped[list['ChatMessage']] = relationship(back_populates='conversation', cascade='all, delete-orphan')

    def get_tags(self) -> list[str]:
        """Parse tags JSON column into a clean list."""
        if not self.tags:
            return []
        try:
            loaded = _json.loads(self.tags)
            if isinstance(loaded, list):
                return [str(tag).strip() for tag in loaded if str(tag).strip()]
        except Exception:
            pass
        return []

    def set_tags(self, tags: list[str]) -> None:
        """Serialize a list of tags into the JSON column."""
        self.tags = _json.dumps([t.strip() for t in tags if t.strip()], ensure_ascii=False)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='sent', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates='messages')
