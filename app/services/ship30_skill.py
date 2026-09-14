"""
Ship 30 for 30 essay generation skill conforming to assignment §4.2.
Encodes the Ship 30/30 writing framework into a structured generator.
"""

from typing import List, Dict, Any, Optional
from app.models.schemas import Citation


SHIP_30_SYSTEM_PROMPT = """You are a master essayist trained strictly in the 'Ship 30 for 30' methodology.
Your task is to transform conversational growth/product insights into an atomic, highly engaging essay.

STRICT WRITING RULES:
1. Target length: ~1,250 words (comprehensive yet punchy and skimmable).
2. The Hook: First 1-2 sentences must immediately challenge conventional wisdom or grab attention with high contrast.
3. Rhythm & Structure:
   - Use short, one-sentence paragraphs for emotional and narrative impact.
   - Use bold subheadings (H2, H3) that make the essay skimmable in 30 seconds.
   - Bulleted frameworks with clear bold anchors.
4. Grounding: All claims, case studies, or tactics must originate exclusively from the provided source citations.
5. The Takeaway: Conclude with exactly ONE high-leverage, practical action step the reader can execute today.
"""


class Ship30Skill:
    """Encodes Ship 30 for 30 principles into a reproducible skill."""

    @staticmethod
    def build_essay_prompt(topic: str, context_text: str, citations: List[Citation]) -> str:
        """Constructs an essay prompt integrating grounding citations."""
        citation_summary = "\n".join(
            [f"- Episode: {c.episode_title} (Snippet: {c.content_snippet})" for c in citations]
        )

        return f"""Topic: {topic}

Verified Knowledge from Lenny's Podcast:
{context_text}

Cited Sources:
{citation_summary}

Write a publish-ready ~1,250-word Ship 30 for 30 essay on this topic strictly using the verified insights above.
Follow the Hook -> Framework -> Takeaway structure with bold skimmable sections."""

    @staticmethod
    def validate_essay(content: str) -> Dict[str, Any]:
        """Validates that the generated essay meets the Ship 30 for 30 criteria."""
        word_count = len(content.split())
        has_hook = len(content) > 100
        has_headings = "#" in content or "##" in content
        has_takeaway = "takeaway" in content.lower() or "action step" in content.lower()

        return {
            "word_count": word_count,
            "meets_word_count_target": 800 <= word_count <= 1800,
            "has_headings": has_headings,
            "has_takeaway": has_takeaway,
            "is_valid": has_headings and (word_count >= 500)
        }
