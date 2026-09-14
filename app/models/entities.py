"""
SQLAlchemy database models for persistence conforming to architecture.md.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Session(Base):
    """Chat session model storing context and active provider information."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    user_metadata = Column(JSON, default=dict, nullable=False)
    active_provider = Column(String(50), default="anthropic", nullable=False)
    active_model = Column(String(100), nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    artifacts = relationship("Artifact", back_populates="session", cascade="all, delete-orphan", order_by="Artifact.created_at")


class Message(Base):
    """Conversation turns with grounding metadata and citations."""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("Session", back_populates="messages")
    artifacts = relationship("Artifact", back_populates="message")


class TranscriptSource(Base):
    """Source episode metadata."""
    __tablename__ = "transcript_sources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_title = Column(String(255), nullable=False)
    episode_url = Column(String(500), nullable=True)
    published_at = Column(String(50), nullable=True)
    raw_path = Column(String(500), nullable=False)

    chunks = relationship("TranscriptChunk", back_populates="source", cascade="all, delete-orphan")


class TranscriptChunk(Base):
    """Text chunks with dual embeddings and content hash."""
    __tablename__ = "transcript_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(36), ForeignKey("transcript_sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    embedding_cloud = Column(JSON, nullable=True)
    embedding_local = Column(JSON, nullable=True)
    token_count = Column(Integer, nullable=False)

    source = relationship("TranscriptSource", back_populates="chunks")


class Artifact(Base):
    """Generated Markdown or HTML/CSS documents."""
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    type = Column(String(20), nullable=False)  # 'markdown' or 'html'
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("Session", back_populates="artifacts")
    message = relationship("Message", back_populates="artifacts")
