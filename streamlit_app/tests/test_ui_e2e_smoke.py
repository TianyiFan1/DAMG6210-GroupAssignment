"""Basic headless UI smoke automation for top Streamlit journeys.

This test starts the app in headless mode and verifies that key routes respond.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


def _wait_for_url(url: str, timeout_seconds: float = 35.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as resp:
                if 200 <= int(resp.status) < 500:
                    return True
        except URLError:
            time.sleep(0.5)
    return False


def test_streamlit_headless_smoke_routes():
    cmd = [
        "streamlit",
        "run",
        str(APP_FILE),
        "--server.headless",
        "true",
        "--server.port",
        str(PORT),
        "--browser.gatherUsageStats",
        "false",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pytest.skip("streamlit CLI is not available in this environment")

    try:
        assert _wait_for_url(f"{BASE_URL}/_stcore/health"), "Streamlit health endpoint did not become ready"

        assert _wait_for_url(f"{BASE_URL}/"), "Main app route is not reachable"
        assert _wait_for_url(f"{BASE_URL}/?page=1_%F0%9F%92%B8_Financials"), "Financials route is not reachable"
        assert _wait_for_url(f"{BASE_URL}/?page=2_%F0%9F%A7%B9_Chores"), "Chores route is not reachable"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
