"""Security/config guard tests to prevent common regressions."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_gitignore_protects_real_secrets():
    gitignore_path = ROOT / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")

    assert ".streamlit/*" in content
    assert "!.streamlit/secrets.toml.template" in content
    assert "!.streamlit/config.toml" in content


def test_required_streamlit_files_exist():
    assert (ROOT / ".streamlit" / "secrets.toml.template").exists()
    assert (ROOT / ".streamlit" / "config.toml").exists()
