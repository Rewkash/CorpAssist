from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal['client', 'worker'] = 'client'


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class MeResponse(BaseModel):
    id: int
    email: str
    role: Literal['admin', 'worker', 'client']
    assigned_worker_id: int | None = None


class AssignWorkerRequest(BaseModel):
    client_id: int
    worker_id: int


class ConversationItem(BaseModel):
    id: int
    title: str
    client_id: int
    client_email: str | None = None
    worker_id: int | None
    status: str
    unread_count: int = 0
    tags: list[str] = []
    priority_at: datetime | None = None
    message_count: int = 0
    first_message_preview: str | None = None
    created_at: datetime
    closed_at: datetime | None = None

    class Config:
        from_attributes = True


class ChatMessageItem(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    text: str
    status: str
    created_at: datetime
    read_at: datetime | None = None

    class Config:
        from_attributes = True


class SendChatMessageRequest(BaseModel):
    conversation_id: int
    text: str = Field(min_length=1, max_length=8000)


class MarkReadRequest(BaseModel):
    conversation_id: int


class SetConversationTagsRequest(BaseModel):
    conversation_id: int
    tags: list[str]


class AnalysisResult(BaseModel):
    sentiment: Literal['neutral', 'tense', 'positive']
    topics: list[str]
    formality: Literal['low', 'medium', 'high']


class SuggestReplyRequest(BaseModel):
    text: str = Field(min_length=5, max_length=8000)
    conversation_id: int | None = None


class SuggestReplyResponse(BaseModel):
    analysis: AnalysisResult
    suggestions: list[str]


class ImproveDraftRequest(BaseModel):
    text: str = Field(min_length=5, max_length=8000)
    conversation_id: int | None = None


class DiffChunk(BaseModel):
    type: Literal['equal', 'insert', 'delete']
    value: str


class ImproveDraftResponse(BaseModel):
    analysis: AnalysisResult
    improved_text: str
    diff: list[DiffChunk]


class HistoryItem(BaseModel):
    id: int
    mode: str
    source_text: str
    result_text: str
    sentiment: str
    topics: str
    formality: str
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeEntryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    tags: list[str] = []
    scope: Literal['global', 'client'] = 'global'
    client_id: int | None = None


class KnowledgeEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    scope: Literal['global', 'client'] | None = None
    client_id: int | None = None


class KnowledgeEntryItem(BaseModel):
    id: int
    title: str
    body: str
    tags: list[str]
    scope: str
    client_id: int | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeHitItem(BaseModel):
    chunk_id: int
    text: str
    score: float
    source_type: str
    source_id: int | None = None
    scope: str
    client_id: int | None = None
    meta: dict


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    client_id: int | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)


class KnowledgeSearchResponse(BaseModel):
    hits: list[KnowledgeHitItem]
