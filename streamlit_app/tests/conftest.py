"""Pytest bootstrap for streamlit_app-local imports.

Phase 4 Upgrade: Added shared fixtures for Streamlit session mocking
and Gemini API response factories.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import sys

import pytest

STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]

if str(STREAMLIT_APP_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_APP_DIR))


@pytest.fixture
def mock_streamlit_secrets(monkeypatch):
    """Provide fake Streamlit secrets so page modules can import without crashing.
    
    Usage: Include this fixture in any test that touches code importing st.secrets.
    """
    fake_secrets = MagicMock()
    fake_secrets.__contains__ = lambda self, key: key in {"gemini", "database"}
    fake_secrets.__getitem__ = lambda self, key: {
        "gemini": {"api_key": "fake-test-key-not-real"},
        "database": {
            "server": "localhost",
            "database": "CoHabitant_Test",
            "driver": "{ODBC Driver 17 for SQL Server}",
            "trusted_connection": "yes",
        },
    }.get(key, MagicMock())
    monkeypatch.setattr("streamlit.secrets", fake_secrets)
    return fake_secrets


@pytest.fixture
def gemini_success_response():
    """Factory that produces a mock Gemini API response with configurable JSON payload.
    
    Usage:
        def test_something(gemini_success_response):
            mock_resp = gemini_success_response(amount=42.50, description="Target Groceries")
    """
    def _factory(
        amount: float = 25.99,
        description: str = "Test Store Supplies",
        category: str = "Groceries",
        notes: str = "Item A, Item B, Item C",
        split_policy: str = "Equal",
        date_incurred: str = "2026-03-24",
    ) -> MagicMock:
        import json
        payload = json.dumps({
            "amount": amount,
            "description": description,
            "category": category,
            "notes": notes,
            "split_policy": split_policy,
            "date_incurred": date_incurred,
        })
        mock_response = MagicMock()
        mock_response.text = payload
        return mock_response

    return _factory
