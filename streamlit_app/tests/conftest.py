"""Pytest bootstrap for streamlit_app-local imports."""

from __future__ import annotations

from pathlib import Path
import sys


STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]

if str(STREAMLIT_APP_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_APP_DIR))
