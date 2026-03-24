"""Read-only integration tests against the configured SQL Server database.

These tests never mutate data and are safe for repeated local execution.
"""

from __future__ import annotations

import pytest

from utils import db


@pytest.fixture(scope="module")
def db_ready_or_skip():
    """Return when DB is reachable; otherwise skip integration assertions."""
    try:
        # Warm connection and verify credentials/secrets are valid.
        _ = db.get_db_connection()
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"Database not available for integration tests: {exc}")


def test_db_ping_query(db_ready_or_skip):
    df = db.run_query("SELECT 1 AS ok")
    assert not df.empty
    assert int(df.iloc[0]["ok"]) == 1


def test_core_tables_exist(db_ready_or_skip):
    sql = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo'
      AND TABLE_NAME IN ('TENANT', 'PERSON', 'EXPENSE', 'EXPENSE_SHARE', 'PAYMENT', 'LEASE_AGREEMENT')
    """
    df = db.run_query(sql)

    names = {str(name).upper() for name in df["TABLE_NAME"].tolist()}
    expected = {"TENANT", "PERSON", "EXPENSE", "EXPENSE_SHARE", "PAYMENT", "LEASE_AGREEMENT"}
    assert expected.issubset(names)


def test_core_views_exist(db_ready_or_skip):
    sql = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_SCHEMA = 'dbo'
      AND TABLE_NAME IN ('vw_App_Ledger_ActiveBalances', 'vw_App_Chore_Leaderboard')
    """
    df = db.run_query(sql)

    names = {str(name) for name in df["TABLE_NAME"].tolist()}
    assert "vw_App_Ledger_ActiveBalances" in names
    assert "vw_App_Chore_Leaderboard" in names
