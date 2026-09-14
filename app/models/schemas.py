"""
Pydantic v2 schemas for API requests, responses, and validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Health & Config
class HealthResponse(BaseModel):
    status: str = "healthy"
    database: str
    active_provider: str
    active_model: str
    ollama_reachable: bool
    details: Optional[Dict[str, Any]] = None


class ConfigResponse(BaseModel):
    active_provider: str
    active_model: str
    llm_fallback_to_local: bool
    similarity_threshold: float
    retrieval_top_k: int
    supported_providers: List[str] = ["ollama", "anthropic", "openai", "custom"]


class ModelConfigTestRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class ModelConfigTestResponse(BaseModel):
    status: str
    message: str
    provider: str
    model: str


# Error Schema conforming to architecture.md §5
class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Session Schemas
class SessionCreateRequest(BaseModel):
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    active_provider: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    user_metadata: Dict[str, Any]
    active_provider: str
    active_model: Optional[str]


# Citation Schema
class Citation(BaseModel):
    episode_title: str
    source_url: Optional[str] = None
    chunk_index: int
    content_snippet: str
    similarity_score: float


# Message Schemas
class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    provider_override: Optional[str] = None
    api_key_override: Optional[str] = None
    model_override: Optional[str] = None
    base_url_override: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime


class ChatTurnResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    citations: List[Citation]
    skill_used: Optional[str] = None
    provider_used: str
    fallback_used: bool = False
    latency_ms: float
    artifact: Optional[Dict[str, Any]] = None


# Artifact Schemas
class ArtifactResponse(BaseModel):
    id: str
    session_id: str
    message_id: Optional[str]
    type: str
    title: Optional[str]
    content: str
    created_at: datetime


class BatchDeleteRequest(BaseModel):
    ids: List[str]

