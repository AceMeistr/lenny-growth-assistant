"""
Agent orchestrator coordinating intent routing, retrieval grounding,
Ship 30 for 30 skill execution, and artifact generation.
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.models.entities import Session as ChatSession, Message, Artifact
from app.models.schemas import Citation, ChatTurnResponse, MessageResponse
from app.providers.factory import ProviderFactory
from app.services.retrieval import RetrievalService
from app.services.ship30_skill import Ship30Skill, SHIP_30_SYSTEM_PROMPT
from app.services.sanitizer import ArtifactSanitizer

logger = logging.getLogger(__name__)

LENNY_SYSTEM_PROMPT = """You are 'The Lenny Growth Assistant', an expert product and growth co-pilot strictly grounded in Lenny's Podcast transcripts.

Core Principles:
1. Always base your answers ONLY on the retrieved transcript context provided.
2. If the context does not contain enough information to answer the question, state calmly and clearly:
   "I cannot find support for this question in the ingested podcast transcripts."
   Do NOT attempt to guess, assume, or hallucinate citations.
3. Be direct, thoughtful, and pragmatic, mirroring the high signal-to-noise ratio of top PM leaders.
4. When citing knowledge, reference the specific guest or episode title found in the grounding context.
"""


class AgentOrchestrator:
    """Conversational controller with intent routing and strict grounding verification."""

    def __init__(self, db: DBSession):
        self.db = db

    def _classify_intent(self, prompt: str) -> str:
        """Route user intent: 'ship30', 'artifact_html', 'artifact_md', or 'qa'."""
        if not prompt:
            return "qa"
        p = prompt.lower()
        if any(term in p for term in ["ship 30", "ship30", "write an essay", "essay on", "turn this into an essay", "draft an essay"]):
            return "ship30"
        if any(term in p for term in ["html artifact", "create html", "generate html", "make an html", "html table", "html snippet", "html page", "html card"]):
            return "artifact_html"
        if any(term in p for term in [
            "table", "summary table", "markdown artifact", "generate doc", "create document",
            "make an artifact", "markdown table", "markdown summary", "create an artifact",
            "generate artifact", "cheatsheet", "framework table", "matrix", "guide", "spade table"
        ]):
            return "artifact_md"
        return "qa"

    async def process_chat_turn(
        self,
        session_id: str,
        user_content: str,
        provider_override: Optional[str] = None,
        api_key_override: Optional[str] = None,
        model_override: Optional[str] = None,
        base_url_override: Optional[str] = None
    ) -> ChatTurnResponse:
        """Execute a full conversational turn with grounding and persistence."""
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]
        logger.info("Processing chat turn | request_id=%s | session=%s", request_id, session_id)

        # 1. Fetch Session
        session = self.db.query(ChatSession).filter_by(id=session_id).first()
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        # 2. Persist User Message
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=user_content,
            message_metadata={}
        )
        self.db.add(user_msg)
        self.db.commit()
        self.db.refresh(user_msg)

        # 3. Resolve Provider
        provider_name = provider_override or session.active_provider or settings.llm_provider
        provider = ProviderFactory.get_provider(
            provider_name=provider_name,
            api_key=api_key_override,
            model=model_override,
            base_url=base_url_override
        )
        is_cloud = (provider.provider_name in ("anthropic", "openai", "custom"))

        # 4. Generate query embedding for vector retrieval
        query_vectors = await provider.get_embeddings([user_content])
        query_vector = query_vectors[0] if query_vectors else []

        # 5. Retrieve Grounding Citations
        citations = RetrievalService.search_chunks(
            db=self.db,
            query_vector=query_vector,
            top_k=settings.retrieval_top_k,
            threshold=settings.similarity_threshold,
            is_cloud=is_cloud
        )

        # 6. Check intent
        intent = self._classify_intent(user_content)
        skill_used = None
        artifact_data = None
        fallback_used = False
        provider_used = provider.provider_name

        # Check for friendly conversational greeting vs ungrounded refusal
        clean_prompt = user_content.strip().lower().rstrip(".!?")
        is_greeting = clean_prompt in ("hi", "hello", "hey", "good morning", "good afternoon", "greetings", "hi there", "help")

        if is_greeting:
            answer_content = (
                "Hello! I am The Lenny Growth Assistant, an internal co-pilot strictly grounded in Lenny's Podcast transcripts.\n\n"
                "I can help you explore verified product strategies (such as Elena Verna on pricing experiments, Brian Balfour on growth loops, Casey Winters on activation, or Gokul Rajaram on the SPADE framework), "
                "draft atomic Ship 30 for 30 essays, or render structured artifacts beside our chat."
            )
            provider_used = provider.provider_name
        elif intent == "qa" and not citations:
            answer_content = (
                "I cannot find support for this question in the ingested podcast transcripts. "
                "Lenny's back-catalog does not appear to cover this specific query in the current corpus."
            )
            provider_used = provider.provider_name
        else:
            # Build Context
            context_blocks = []
            for c in citations:
                context_blocks.append(f"Source: {c.episode_title}\nExcerpt: {c.content_snippet}")
            grounding_text = "\n\n".join(context_blocks)

            # Build prior turns excluding current turn to ensure clean role alternation
            prior_messages = (
                self.db.query(Message)
                .filter(Message.session_id == session_id, Message.id != user_msg.id)
                .order_by(Message.created_at.desc())
                .limit(6)
                .all()
            )
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in reversed(prior_messages)
            ]

            if intent == "ship30":
                skill_used = "ship_30_for_30"
                prompt = Ship30Skill.build_essay_prompt(user_content, grounding_text, citations)
                history = conversation_history + [{"role": "user", "content": prompt}]
                
                resp_data, fallback_used = await ProviderFactory.execute_with_fallback(
                    provider,
                    "generate_response",
                    messages=history,
                    system_prompt=SHIP_30_SYSTEM_PROMPT,
                    temperature=0.3
                )
                answer_content = resp_data.get("content", "")
                provider_used = resp_data.get("provider", provider.provider_name)

                # Automatically save the essay as a markdown artifact
                sanitized_essay = ArtifactSanitizer.sanitize_markdown(answer_content)
                essay_artifact = Artifact(
                    session_id=session_id,
                    message_id=None,
                    type="markdown",
                    title="Ship 30 for 30 Essay",
                    content=sanitized_essay
                )
                self.db.add(essay_artifact)
                self.db.commit()
                self.db.refresh(essay_artifact)
                artifact_data = {
                    "id": essay_artifact.id,
                    "type": essay_artifact.type,
                    "title": essay_artifact.title,
                    "content": essay_artifact.content
                }

            elif intent.startswith("artifact_"):
                artifact_type = "html" if intent == "artifact_html" else "markdown"
                skill_used = f"generate_{artifact_type}_artifact"
                
                sys_prompt = (
                    "You are a publication designer. Generate a clean, complete, standalone "
                    + ("HTML snippet with inline CSS" if artifact_type == "html" else "Markdown document")
                    + " presenting the growth framework requested."
                )
                history = conversation_history + [{
                    "role": "user",
                    "content": f"Create a formatted {artifact_type} artifact based on this grounding:\n{grounding_text}\nUser request: {user_content}"
                }]
                
                resp_data, fallback_used = await ProviderFactory.execute_with_fallback(
                    provider,
                    "generate_response",
                    messages=history,
                    system_prompt=sys_prompt,
                    temperature=0.2
                )
                raw_artifact = resp_data.get("content", "")
                provider_used = resp_data.get("provider", provider.provider_name)

                # Sanitize and store artifact per ADR-2
                if artifact_type == "html":
                    sanitized_content = ArtifactSanitizer.sanitize_html(raw_artifact)
                else:
                    sanitized_content = ArtifactSanitizer.sanitize_markdown(raw_artifact)

                art_entity = Artifact(
                    session_id=session_id,
                    message_id=None,
                    type=artifact_type,
                    title=f"Generated {artifact_type.upper()} Artifact",
                    content=sanitized_content
                )
                self.db.add(art_entity)
                self.db.commit()
                self.db.refresh(art_entity)

                answer_content = f"I have generated your {artifact_type.upper()} artifact and opened it in the Artifact Studio beside our conversation."
                artifact_data = {
                    "id": art_entity.id,
                    "type": art_entity.type,
                    "title": art_entity.title,
                    "content": art_entity.content
                }

            else:
                # Standard Grounded Q&A
                system_with_grounding = f"{LENNY_SYSTEM_PROMPT}\n\nGROUNDING CONTEXT FROM PODCAST TRANSCRIPTS:\n{grounding_text}"
                history = conversation_history + [{"role": "user", "content": user_content}]
                
                resp_data, fallback_used = await ProviderFactory.execute_with_fallback(
                    provider,
                    "generate_response",
                    messages=history,
                    system_prompt=system_with_grounding,
                    temperature=0.2
                )
                answer_content = resp_data.get("content", "")
                provider_used = resp_data.get("provider", provider.provider_name)

        # 7. Update session timestamp to reflect latest activity (A4)
        self.db.query(ChatSession).filter_by(id=session_id).update(
            {"updated_at": datetime.now(timezone.utc)}
        )

        # 8. Persist Assistant Response
        latency = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "Chat turn complete | request_id=%s | session=%s | intent=%s | latency_ms=%.1f | citations=%d | fallback=%s",
            request_id, session_id, intent, latency, len(citations), fallback_used
        )
        assistant_metadata = {
            "citations_count": len(citations),
            "skill_used": skill_used,
            "provider_used": provider_used,
            "fallback_used": fallback_used,
            "latency_ms": latency
        }

        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=answer_content,
            message_metadata=assistant_metadata
        )
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

        # Link artifact to assistant message if generated
        if artifact_data and "id" in artifact_data:
            self.db.query(Artifact).filter_by(id=artifact_data["id"]).update({"message_id": assistant_msg.id})
            self.db.commit()

        return ChatTurnResponse(
            user_message=MessageResponse(
                id=user_msg.id,
                session_id=user_msg.session_id,
                role=user_msg.role,
                content=user_msg.content,
                metadata=user_msg.message_metadata,
                created_at=user_msg.created_at
            ),
            assistant_message=MessageResponse(
                id=assistant_msg.id,
                session_id=assistant_msg.session_id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                metadata=assistant_msg.message_metadata,
                created_at=assistant_msg.created_at
            ),
            citations=citations,
            skill_used=skill_used,
            provider_used=provider_used,
            fallback_used=fallback_used,
            latency_ms=latency,
            artifact=artifact_data
        )
