"""Smoke tests to catch syntax regressions across app Python files."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_python_files_parse():
    py_files = [
        p for p in ROOT.rglob("*.py")
        if "venv" not in p.parts and "__pycache__" not in p.parts
    ]

    assert py_files, "No Python files found for smoke parse test."

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
