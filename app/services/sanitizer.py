"""
Security sanitizer for HTML/CSS generated artifacts.
Implements ADR-2: Sandboxed isolation & server-side stripping of executable scripts.
"""

import re
from bs4 import BeautifulSoup

# Tags strictly prohibited from user/LLM generated artifacts
FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "applet", "meta", "link", "form", "input", "button"}

# Regex for javascript: and dangerous URI schemes
JS_SCHEME_REGEX = re.compile(r"^\s*javascript:", re.IGNORECASE)
DATA_HTML_REGEX = re.compile(r"^\s*data:text/html", re.IGNORECASE)

DEFAULT_ARTIFACT_CSS = """
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Plus Jakarta Sans', sans-serif;
    padding: 28px;
    margin: 0;
    color: #18181B;
    background-color: #FFFFFF;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }
  h1, h2, h3, h4 {
    font-family: Georgia, 'Times New Roman', serif;
    color: #09090B;
    margin-top: 0;
    margin-bottom: 14px;
    letter-spacing: -0.01em;
  }
  h1 { font-size: 1.45rem; border-bottom: 1px solid #E4E4E7; padding-bottom: 10px; }
  h2 { font-size: 1.25rem; }
  h3 { font-size: 1.05rem; }
  p { margin: 0 0 14px 0; color: #3F3F46; font-size: 0.95rem; }
  table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 18px 0 24px 0;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    overflow: hidden;
    font-size: 0.9rem;
  }
  th {
    background-color: #F8F9FA;
    color: #18181B;
    font-weight: 600;
    text-align: left;
    padding: 12px 16px;
    border-bottom: 2px solid #E4E4E7;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  td {
    padding: 12px 16px;
    border-bottom: 1px solid #F1F1F4;
    color: #27272A;
    vertical-align: top;
  }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background-color: #FAFAFA; }
  strong { font-weight: 600; color: #09090B; }
  ul, ol { padding-left: 22px; margin: 10px 0 16px 0; color: #3F3F46; font-size: 0.95rem; }
  li { margin-bottom: 6px; }
  .badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 500;
    background: #F4F4F5;
    color: #52525B;
  }
</style>
"""


class ArtifactSanitizer:
    """Sanitizes generated HTML/CSS artifacts to prevent XSS and DOM hijacking."""

    @staticmethod
    def sanitize_html(raw_html: str) -> str:
        """
        Strips markdown code fences, script tags, event handlers (onclick, onerror, etc.),
        and dangerous URL schemes while embedding clean default styling.
        """
        if not raw_html or not raw_html.strip():
            return ""

        # 1. Strip leading and trailing markdown code fences if output by LLM
        cleaned = raw_html.strip()
        cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        soup = BeautifulSoup(cleaned, "html.parser")

        # 2. Remove all forbidden tags completely
        for tag in soup.find_all(FORBIDDEN_TAGS):
            tag.decompose()

        # 3. Clean attributes on all remaining elements
        for element in soup.find_all(True):
            attrs = dict(element.attrs)
            for attr_name, attr_value in attrs.items():
                attr_lower = attr_name.lower()

                # Remove all inline event handlers (on*)
                if attr_lower.startswith("on"):
                    del element.attrs[attr_name]
                    continue

                # Inspect URLs in href or src attributes
                if attr_lower in ("href", "src"):
                    if isinstance(attr_value, str):
                        if JS_SCHEME_REGEX.search(attr_value) or DATA_HTML_REGEX.search(attr_value):
                            del element.attrs[attr_name]

        rendered_body = str(soup)

        # 4. Inject default clean typography/table styles if not already present
        if "<style" not in rendered_body.lower():
            return f"<!DOCTYPE html><html><head><meta charset='utf-8'>{DEFAULT_ARTIFACT_CSS}</head><body>{rendered_body}</body></html>"

        return rendered_body

    @staticmethod
    def sanitize_markdown(raw_markdown: str) -> str:
        """
        Sanitizes markdown by neutralizing raw script injections while
        preserving valid markdown syntax and stripping accidental outer code fences.
        """
        if not raw_markdown:
            return ""

        # Strip accidental outer code fences wrapping entire essay
        cleaned = raw_markdown.strip()
        cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        # Strip script and iframe tags embedded in markdown
        cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        return cleaned
