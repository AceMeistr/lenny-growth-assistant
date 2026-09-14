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


class ArtifactSanitizer:
    """Sanitizes generated HTML/CSS artifacts to prevent XSS and DOM hijacking."""

    @staticmethod
    def sanitize_html(raw_html: str) -> str:
        """
        Strips script tags, event handlers (onclick, onerror, etc.),
        and dangerous URL schemes while preserving formatting and inline styles.
        """
        if not raw_html or not raw_html.strip():
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Remove all forbidden tags completely
        for tag in soup.find_all(FORBIDDEN_TAGS):
            tag.decompose()

        # 2. Clean attributes on all remaining elements
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

        return str(soup)

    @staticmethod
    def sanitize_markdown(raw_markdown: str) -> str:
        """
        Sanitizes markdown by neutralizing raw script injections while
        preserving valid markdown syntax.
        """
        if not raw_markdown:
            return ""
        # Strip script tags embedded in markdown
        cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", raw_markdown, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        return cleaned
