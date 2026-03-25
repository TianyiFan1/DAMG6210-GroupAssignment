"""Tests for Gemini AI receipt parsing with mocked API calls.

Phase 4: Ensures tests never hit live Gemini endpoints. All API
interactions are mocked at the google.genai.Client level.

Tests cover:
    - Happy path: valid JSON response → correctly parsed dict
    - Malformed JSON: Gemini returns garbage → empty dict (no crash)
    - Non-dict JSON: Gemini returns a list → empty dict
    - Retry behavior: transient failures recover on attempt 2
    - Total failure: all retries exhausted → RuntimeError
    - Markdown-wrapped JSON: ```json fences are stripped correctly
    - Edge case fields: missing/null keys handled gracefully
"""

from __future__ import annotations

import json
import io
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Minimal 1x1 red PNG for test image bytes ──
# This avoids needing a real receipt image in tests.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def _isolate_streamlit(monkeypatch):
    """Prevent st.set_page_config() from crashing during import of the page module.
    
    Streamlit page modules call set_page_config at module scope.
    In a test context (no Streamlit server), this raises an error.
    We mock it away so we can safely import functions from the page.
    """
    monkeypatch.setattr("streamlit.set_page_config", lambda **kwargs: None)


@pytest.fixture
def _mock_secrets(monkeypatch):
    """Provide fake secrets so _get_gemini_client doesn't fail on import."""
    fake_secrets = MagicMock()
    fake_secrets.__contains__ = lambda self, key: True
    fake_secrets.__getitem__ = lambda self, key: {"api_key": "fake-key"}
    monkeypatch.setattr("streamlit.secrets", fake_secrets)


# ═══════════════════════════════════════════════════════════
# parse_receipt_with_ai — Integration-level mock tests
# ═══════════════════════════════════════════════════════════

class TestParseReceiptWithAI:
    """Test the full parse_receipt_with_ai pipeline with mocked Gemini."""

    def _make_mock_client(self, response_text: str) -> MagicMock:
        """Build a mock genai.Client whose generate_content returns response_text."""
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    @pytest.mark.usefixtures("_mock_secrets")
    def test_happy_path_valid_json(self):
        """Valid JSON from Gemini → correctly parsed dict with all 6 fields."""
        expected = {
            "amount": 42.50,
            "description": "Target Shared Supplies",
            "category": "Groceries",
            "notes": "Paper towels, Dish soap, Sponges",
            "split_policy": "Equal",
            "date_incurred": "2026-03-24",
        }

        mock_client = self._make_mock_client(json.dumps(expected))

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            # Import after mocking to avoid import-time side effects
            from pages import __import__  # noqa: just ensuring path
            # Direct import of the function
            import importlib
            mod = importlib.import_module("pages.1_💸_Financials")
            result = mod.parse_receipt_with_ai(_TINY_PNG)

        assert result == expected
        assert result["amount"] == 42.50
        assert result["category"] == "Groceries"

    @pytest.mark.usefixtures("_mock_secrets")
    def test_malformed_json_returns_empty_dict(self):
        """Garbage response from Gemini → graceful empty dict, no crash."""
        mock_client = self._make_mock_client("This is not JSON at all {{{")

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            import importlib
            mod = importlib.import_module("pages.1_💸_Financials")
            result = mod.parse_receipt_with_ai(_TINY_PNG)

        assert result == {}

    @pytest.mark.usefixtures("_mock_secrets")
    def test_non_dict_json_returns_empty_dict(self):
        """Gemini returns a JSON list instead of object → empty dict."""
        mock_client = self._make_mock_client('[1, 2, 3]')

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            import importlib
            mod = importlib.import_module("pages.1_💸_Financials")
            result = mod.parse_receipt_with_ai(_TINY_PNG)

        assert result == {}

    @pytest.mark.usefixtures("_mock_secrets")
    def test_markdown_fenced_json_is_stripped(self):
        """Gemini wraps response in ```json fences → fences stripped, dict parsed."""
        payload = {"amount": 10.0, "description": "Test", "category": "Other",
                   "notes": "", "split_policy": "Equal", "date_incurred": "2026-01-01"}
        fenced = f"```json\n{json.dumps(payload)}\n```"
        mock_client = self._make_mock_client(fenced)

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            import importlib
            mod = importlib.import_module("pages.1_💸_Financials")
            result = mod.parse_receipt_with_ai(_TINY_PNG)

        assert result["amount"] == 10.0

    @pytest.mark.usefixtures("_mock_secrets")
    def test_missing_fields_are_tolerated(self):
        """Gemini returns partial JSON (missing some keys) → returned as-is."""
        partial = {"amount": 5.0, "description": "Partial"}
        mock_client = self._make_mock_client(json.dumps(partial))

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            import importlib
            mod = importlib.import_module("pages.1_💸_Financials")
            result = mod.parse_receipt_with_ai(_TINY_PNG)

        assert result["amount"] == 5.0
        assert "category" not in result  # Missing keys are simply absent


# ═══════════════════════════════════════════════════════════
# _call_gemini_with_backoff — Retry behavior tests
# ═══════════════════════════════════════════════════════════

class TestGeminiRetryBehavior:
    """Test that the backoff wrapper retries correctly and fails cleanly."""

    @pytest.mark.usefixtures("_mock_secrets")
    def test_retry_succeeds_on_second_attempt(self):
        """First call fails, second succeeds → response returned, no error."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({"amount": 99.0})

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            RuntimeError("Transient API error"),  # Attempt 1: fail
            mock_response,                          # Attempt 2: succeed
        ]

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            with patch("pages.1_💸_Financials.time.sleep"):  # Skip actual sleep
                import importlib
                mod = importlib.import_module("pages.1_💸_Financials")
                from PIL import Image
                img = Image.open(io.BytesIO(_TINY_PNG))
                result = mod._call_gemini_with_backoff(img, "test prompt", max_attempts=3)

        assert '"amount": 99.0' in result  # Raw text returned
        assert mock_client.models.generate_content.call_count == 2

    @pytest.mark.usefixtures("_mock_secrets")
    def test_all_retries_exhausted_raises_runtime_error(self):
        """All attempts fail → RuntimeError raised with last error message."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Persistent failure")

        with patch("pages.1_💸_Financials._get_gemini_client", return_value=mock_client):
            with patch("pages.1_💸_Financials.time.sleep"):
                import importlib
                mod = importlib.import_module("pages.1_💸_Financials")
                from PIL import Image
                img = Image.open(io.BytesIO(_TINY_PNG))

                with pytest.raises(RuntimeError, match="Persistent failure"):
                    mod._call_gemini_with_backoff(img, "test prompt", max_attempts=2)

        assert mock_client.models.generate_content.call_count == 2
