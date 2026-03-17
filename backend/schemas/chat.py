"""Pydantic schemas for contextual PR chat endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message for the PR chat")

    @field_validator("message", mode="before")
    def normalize_message(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Chat message is required")
        return value


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    session_id: str
    analysis_id: str
    answer: str
    history: list[ChatMessageResponse]


class ChatHistoryResponse(BaseModel):
    session_id: str
    analysis_id: str
    history: list[ChatMessageResponse]
