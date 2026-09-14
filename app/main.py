"""
FastAPI application entrypoint with health checks, session management,
message routing, and static asset serving.
"""

import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import init_db, get_db, check_db_health
from app.models.entities import Session as ChatSession, Message, Artifact
from app.models.schemas import (
    HealthResponse,
    ConfigResponse,
    ErrorResponse,
    SessionCreateRequest,
    SessionResponse,
    MessageCreateRequest,
    ChatTurnResponse,
    ArtifactResponse,
    ModelConfigTestRequest,
    ModelConfigTestResponse
)
from app.providers.factory import ProviderFactory
from app.services.agent import AgentOrchestrator

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("lenny_growth_assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan context."""
    logger.info("Initializing database and verifying schemas...")
    init_db()
    logger.info("Application successfully booted on environment: %s", settings.app_env)
    yield
    logger.info("Application shutting down cleanly...")


app = FastAPI(
    title="The Lenny Growth Assistant",
    description="Knowledge co-pilot strictly grounded in Lenny's Podcast transcripts with Ship 30 for 30 essay generation and sandboxed artifact rendering.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — do NOT combine allow_credentials=True with wildcard origins; credential leakage risk (S1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # Safe: no session cookies in v1
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


# Global Exception Handler: structured JSON per architecture.md §5
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid.uuid4())[:8]
    logger.error(
        "Unhandled exception | request_id=%s | %s %s | error=%s",
        request_id, request.method, request.url.path, str(exc)
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "detail": str(exc) if settings.app_env == "development" else None,
                "request_id": request_id
            }
        }
    )


# 404 JSON handler: prevents static file mount from swallowing API misses as HTML 404s
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    detail = getattr(exc, "detail", "Not Found")
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "NOT_FOUND", "message": str(detail)}}
    )


# --- System & Observability Endpoints ---

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Liveness & readiness health check inspecting DB, LLM provider, and Ollama."""
    db_ok = check_db_health()
    ollama_provider = ProviderFactory.get_provider("ollama")
    ollama_ok = await ollama_provider.health_check()

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database="connected" if db_ok else "unreachable",
        active_provider=settings.llm_provider,
        active_model=settings.llm_model,
        ollama_reachable=ollama_ok,
        details={
            "fallback_enabled": settings.llm_fallback_to_local,
            "env": settings.app_env
        }
    )


@app.get("/config", response_model=ConfigResponse, tags=["System"])
def get_config():
    """Returns active runtime configuration for UI badges without leaking secrets."""
    return ConfigResponse(
        active_provider=settings.llm_provider,
        active_model=settings.llm_model,
        llm_fallback_to_local=settings.llm_fallback_to_local,
        similarity_threshold=settings.similarity_threshold,
        retrieval_top_k=settings.retrieval_top_k
    )


@app.post("/config/test-model", response_model=ModelConfigTestResponse, tags=["System"])
async def test_model_config(req: ModelConfigTestRequest):
    """Test connectivity to an external model provider (Ollama, Anthropic, OpenAI)."""
    try:
        provider = ProviderFactory.get_provider(
            provider_name=req.provider,
            api_key=req.api_key,
            model=req.model,
            base_url=req.base_url
        )
        is_healthy = await provider.health_check()
        if not is_healthy and req.provider in ("anthropic", "openai") and not req.api_key:
            return ModelConfigTestResponse(
                status="unconfigured",
                message=f"No API key provided for {req.provider}.",
                provider=req.provider,
                model=provider.model
            )
        return ModelConfigTestResponse(
            status="success" if is_healthy else "warning",
            message=f"Connected to {req.provider} ({provider.model}) successfully.",
            provider=req.provider,
            model=provider.model
        )
    except Exception as e:
        return ModelConfigTestResponse(
            status="error",
            message=f"Connection test failed: {str(e)}",
            provider=req.provider,
            model=req.model or "unknown"
        )


# --- Session Management Endpoints ---

@app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
def create_session(req: SessionCreateRequest, db: DBSession = Depends(get_db)):
    """Create a new independent conversational session."""
    session = ChatSession(
        user_metadata=req.user_metadata or {},
        active_provider=req.active_provider or settings.llm_provider,
        active_model=settings.llm_model
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse(
        id=session.id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        user_metadata=session.user_metadata,
        active_provider=session.active_provider,
        active_model=session.active_model
    )


@app.get("/sessions", response_model=List[SessionResponse], tags=["Sessions"])
def list_sessions(db: DBSession = Depends(get_db)):
    """List all available sessions ordered by most recent activity."""
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    return [
        SessionResponse(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_metadata=s.user_metadata,
            active_provider=s.active_provider,
            active_model=s.active_model
        )
        for s in sessions
    ]


@app.get("/sessions/{session_id}", tags=["Sessions"])
def get_session_history(session_id: str, db: DBSession = Depends(get_db)):
    """Fetch session details and chronological message history."""
    session = db.query(ChatSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": f"Session '{session_id}' does not exist."}}
        )

    messages = db.query(Message).filter_by(session_id=session_id).order_by(Message.created_at.asc()).all()
    artifacts = db.query(Artifact).filter_by(session_id=session_id).order_by(Artifact.created_at.desc()).all()

    return {
        "session": SessionResponse(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            user_metadata=session.user_metadata,
            active_provider=session.active_provider,
            active_model=session.active_model
        ),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.message_metadata,
                "created_at": m.created_at
            }
            for m in messages
        ],
        "artifacts": [
            {
                "id": a.id,
                "type": a.type,
                "title": a.title,
                "created_at": a.created_at
            }
            for a in artifacts
        ]
    }


@app.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    """Delete a conversational session, including all its messages and artifacts."""
    session = db.query(ChatSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Session '{session_id}' not found."}}
        )
    db.query(Message).filter_by(session_id=session_id).delete()
    db.query(Artifact).filter_by(session_id=session_id).delete()
    db.delete(session)
    db.commit()
    return {"status": "deleted", "id": session_id}


# --- Message & Conversation Endpoints ---

@app.post("/sessions/{session_id}/messages", response_model=ChatTurnResponse, tags=["Chat"])
async def send_message(session_id: str, req: MessageCreateRequest, db: DBSession = Depends(get_db)):
    """Send a user message and receive a grounded response with citations and artifacts."""
    orchestrator = AgentOrchestrator(db=db)
    try:
        turn = await orchestrator.process_chat_turn(
            session_id=session_id,
            user_content=req.content,
            provider_override=req.provider_override,
            api_key_override=req.api_key_override,
            model_override=req.model_override,
            base_url_override=req.base_url_override
        )
        return turn
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}}
        )
    except Exception as e:
        logger.error("Error processing turn for session %s: %s", session_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "AGENT_EXECUTION_ERROR", "message": "Failed to process chat turn.", "detail": str(e)}}
        )


# --- Artifact Endpoints ---

@app.get("/sessions/{session_id}/artifacts", response_model=List[ArtifactResponse], tags=["Artifacts"])
def list_session_artifacts(session_id: str, db: DBSession = Depends(get_db)):
    """List all generated artifacts for a session."""
    artifacts = db.query(Artifact).filter_by(session_id=session_id).order_by(Artifact.created_at.desc()).all()
    return [
        ArtifactResponse(
            id=a.id,
            session_id=a.session_id,
            message_id=a.message_id,
            type=a.type,
            title=a.title,
            content=a.content,
            created_at=a.created_at
        )
        for a in artifacts
    ]


@app.get("/artifacts", response_model=List[ArtifactResponse], tags=["Artifacts"])
def list_all_artifacts(db: DBSession = Depends(get_db)):
    """List all generated artifacts across all sessions."""
    artifacts = db.query(Artifact).order_by(Artifact.created_at.desc()).all()
    return [
        ArtifactResponse(
            id=a.id,
            session_id=a.session_id,
            message_id=a.message_id,
            type=a.type,
            title=a.title,
            content=a.content,
            created_at=a.created_at
        )
        for a in artifacts
    ]


@app.get("/artifacts/{artifact_id}", response_model=ArtifactResponse, tags=["Artifacts"])
def get_artifact(artifact_id: str, db: DBSession = Depends(get_db)):
    """Retrieve a single generated artifact and its content."""
    artifact = db.query(Artifact).filter_by(id=artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ARTIFACT_NOT_FOUND", "message": f"Artifact '{artifact_id}' does not exist."}}
        )
    return ArtifactResponse(
        id=artifact.id,
        session_id=artifact.session_id,
        message_id=artifact.message_id,
        type=artifact.type,
        title=artifact.title,
        content=artifact.content,
        created_at=artifact.created_at
    )


@app.delete("/artifacts/{artifact_id}", tags=["Artifacts"])
def delete_artifact(artifact_id: str, db: DBSession = Depends(get_db)):
    """Delete an artifact by ID."""
    artifact = db.query(Artifact).filter_by(id=artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ARTIFACT_NOT_FOUND", "message": f"Artifact '{artifact_id}' does not exist."}}
        )
    db.delete(artifact)
    db.commit()
    return {"status": "deleted", "id": artifact_id}


# --- Static UI Mount ---
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
