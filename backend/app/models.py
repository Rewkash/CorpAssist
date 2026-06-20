from datetime import datetime
from enum import StrEnum
from typing import Any

import json as _json

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# pgvector integration — optional, graceful fallback if not installed
try:
    from pgvector.sqlalchemy import Vector
    _HAS_PGVECTOR = True
except ImportError:
    _HAS_PGVECTOR = False
    Vector = None  # type: ignore[assignment,misc]

EMBEDDING_DIMENSIONS = 768


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


class ConversationSummary(Base):
    """LLM-generated summary of a closed conversation, used for client long-term memory."""
    __tablename__ = 'conversation_summaries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey('conversations.id', ondelete='CASCADE'), unique=True, index=True,
    )
    client_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    summary: Mapped[str] = mapped_column(Text)
    key_topics: Mapped[str] = mapped_column(Text, default='[]')
    resolution: Mapped[str] = mapped_column(String(50), default='')
    sentiment_trend: Mapped[str] = mapped_column(String(50), default='')
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Vector embedding for semantic search (pgvector). Null if pgvector not available.
    embedding: Mapped[Any] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS) if _HAS_PGVECTOR else Text,
        nullable=True,
    ) if _HAS_PGVECTOR else mapped_column(Text, nullable=True)

    conversation: Mapped[Conversation] = relationship()

    def get_key_topics(self) -> list[str]:
        if not self.key_topics:
            return []
        try:
            loaded = _json.loads(self.key_topics)
            if isinstance(loaded, list):
                return [str(t).strip() for t in loaded if str(t).strip()]
        except Exception:
            pass
        return []

    def set_key_topics(self, topics: list[str]) -> None:
        self.key_topics = _json.dumps([t.strip() for t in topics if t.strip()], ensure_ascii=False)


class ClientProfile(Base):
    """Aggregated client profile built from conversation summaries."""
    __tablename__ = 'client_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True,
    )
    profile: Mapped[str] = mapped_column(Text, default='')
    common_topics: Mapped[str] = mapped_column(Text, default='[]')
    communication_style: Mapped[str] = mapped_column(String(50), default='')
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    def get_common_topics(self) -> list[str]:
        if not self.common_topics:
            return []
        try:
            loaded = _json.loads(self.common_topics)
            if isinstance(loaded, list):
                return [str(t).strip() for t in loaded if str(t).strip()]
        except Exception:
            pass
        return []

    def set_common_topics(self, topics: list[str]) -> None:
        self.common_topics = _json.dumps([t.strip() for t in topics if t.strip()], ensure_ascii=False)


class RAGSearchLog(Base):
    """Log of each RAG search act for evaluation and analytics."""
    __tablename__ = 'rag_search_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    current_topics: Mapped[str] = mapped_column(Text, default='[]')
    strategy: Mapped[str] = mapped_column(String(32), index=True)  # none/recent/topic/hybrid/hybrid_decay
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    topic_hits: Mapped[int] = mapped_column(Integer, default=0)
    vector_hits: Mapped[int] = mapped_column(Integer, default=0)
    rrf_scores: Mapped[str] = mapped_column(Text, default='[]')  # JSON list of floats
    hit_summary_ids: Mapped[str] = mapped_column(Text, default='[]')  # JSON list of ints
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class EvaluationLog(Base):
    """LLM-as-Judge evaluation of AI-generated responses."""
    __tablename__ = 'llm_evaluations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    message_history_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    strategy: Mapped[str] = mapped_column(String(32), index=True)  # memory strategy used
    relevance: Mapped[int] = mapped_column(Integer, default=0)  # 1-5
    politeness: Mapped[int] = mapped_column(Integer, default=0)  # 1-5
    completeness: Mapped[int] = mapped_column(Integer, default=0)  # 1-5
    accuracy: Mapped[int] = mapped_column(Integer, default=0)  # 1-5
    overall: Mapped[float] = mapped_column(Float, default=0.0)  # mean of 4 criteria
    judge_model: Mapped[str] = mapped_column(String(64), default='')
    judge_raw: Mapped[str] = mapped_column(Text, default='')  # raw LLM output for audit
