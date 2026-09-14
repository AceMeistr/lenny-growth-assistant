"""
Test suite for HTML and Markdown artifact sanitization (ADR-2).
Validates that script tags, event handlers, and malicious URIs are neutralized.
"""

import pytest
from app.services.sanitizer import ArtifactSanitizer


def test_sanitize_html_removes_script_tags():
    raw_html = "<div><h3>Growth Framework</h3><script>alert('XSS')</script><p>Safe content</p></div>"
    clean = ArtifactSanitizer.sanitize_html(raw_html)
    assert "<script>" not in clean
    assert "alert('XSS')" not in clean
    assert "Growth Framework" in clean
    assert "Safe content" in clean


def test_sanitize_html_removes_inline_event_handlers():
    raw_html = '<button onclick="exploit()" onmouseover="steal()" class="btn">Click me</button>'
    clean = ArtifactSanitizer.sanitize_html(raw_html)
    # The button tag is in forbidden tags and decomposed
    assert "onclick" not in clean
    assert "onmouseover" not in clean


def test_sanitize_html_removes_javascript_urls():
    raw_html = '<a href="javascript:alert(1)">Suspicious Link</a><img src="javascript:evil()">'
    clean = ArtifactSanitizer.sanitize_html(raw_html)
    assert "javascript:" not in clean


def test_sanitize_markdown_strips_injected_scripts():
    raw_md = "# Essay on PLG\n\n<script>fetch('http://attacker.com')</script>\n\nCompounding growth loops."
    clean = ArtifactSanitizer.sanitize_markdown(raw_md)
    assert "<script>" not in clean
    assert "fetch('http://attacker.com')" not in clean
    assert "Compounding growth loops." in clean
