from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='client', index=True)
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


class KnowledgeEntry(Base):
    """Курируемая запись базы знаний: регламент, FAQ, описание продукта."""

    __tablename__ = 'knowledge_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, default='[]')
    scope: Mapped[str] = mapped_column(String(16), default='global', index=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeChunk(Base):
    """Эмбеддинги кусочков базы знаний и истории диалогов для RAG."""

    __tablename__ = 'knowledge_chunks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(16), default='global', index=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    chunk_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SemanticCacheEntry(Base):
    """Семантический кэш ответов LLM. Совпадение по похожести эмбеддингов."""

    __tablename__ = 'semantic_cache_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    query_embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    response_json: Mapped[str] = mapped_column(Text)
    scope_key: Mapped[str] = mapped_column(String(64), default='global', index=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __mapper_args__ = {'eager_defaults': True}


class ClientProfile(Base):
    """Компактное резюме клиента для долгой памяти (заполняется фоновой задачей)."""

    __tablename__ = 'client_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text, default='')
    last_indexed_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
