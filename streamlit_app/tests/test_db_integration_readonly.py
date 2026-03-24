"""Read-only integration tests against the configured SQL Server database.

These tests never mutate data and are safe for repeated local execution.
"""

from __future__ import annotations

import pytest

from utils import db


def _fetch_first_scalar(cursor):
    """Return first scalar from any available result set on the cursor."""
    while True:
        if cursor.description is not None:
            row = cursor.fetchone()
            return row[0] if row is not None else None
        if not cursor.nextset():
            return None


@pytest.fixture(scope="module")
def db_ready_or_skip():
    """Return when DB is reachable; otherwise skip integration assertions."""
    conn = None
    try:
        # Warm connection and verify credentials/secrets are valid.
        conn = db.get_db_connection()
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"Database not available for integration tests: {exc}")
    finally:
        if conn is not None:
            conn.close()


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


def test_mutating_expense_create_delete_rollback(db_ready_or_skip):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO dbo.EXPENSE (Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy)
            OUTPUT INSERTED.Expense_ID
            VALUES (?, ?, CAST(GETDATE() AS DATE), ?);
            """,
            [11, 9.99, "Equal"],
        )
        expense_id = int(_fetch_first_scalar(cursor))

        cursor.execute(
            "INSERT INTO dbo.EXPENSE_SHARE (Expense_ID, Owed_By_Tenant_ID, Owed_Amount, Status) VALUES (?, ?, ?, 'Pending')",
            [expense_id, 12, 4.99],
        )

        cursor.execute("SELECT COUNT(*) AS Cnt FROM dbo.EXPENSE_SHARE WHERE Expense_ID = ?", [expense_id])
        assert int(cursor.fetchval()) == 1

        cursor.execute("DELETE FROM dbo.EXPENSE_SHARE WHERE Expense_ID = ?", [expense_id])
        cursor.execute("DELETE FROM dbo.EXPENSE WHERE Expense_ID = ?", [expense_id])

        cursor.execute("SELECT COUNT(*) AS Cnt FROM dbo.EXPENSE WHERE Expense_ID = ?", [expense_id])
        assert int(cursor.fetchval()) == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()


def test_mutating_payment_procedure_rollback(db_ready_or_skip):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Current_Net_Balance FROM dbo.TENANT WHERE Tenant_ID = ?", [11])
        before_balance = float(cursor.fetchval())

        cursor.execute(
            """
            DECLARE @NewBalance DECIMAL(10,2);
            EXEC dbo.usp_ProcessTenantPayment ?, ?, ?, @NewBalance OUTPUT;
            SELECT @NewBalance;
            """,
            [11, 1.23, "integration payment test"],
        )
        new_balance = float(_fetch_first_scalar(cursor))
        assert new_balance >= before_balance

        cursor.execute(
            "SELECT TOP 1 Amount, Note FROM dbo.PAYMENT WHERE Payer_Tenant_ID = ? ORDER BY Payment_ID DESC",
            [11],
        )
        payment_row = cursor.fetchone()
        assert payment_row is not None
    finally:
        conn.rollback()
        cursor.close()
        conn.close()


def test_mutating_vote_procedure_property_scoped_rollback(db_ready_or_skip):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO dbo.PROPOSAL (Proposed_By_Tenant_ID, Description, Cost_Threshold, Status)
            OUTPUT INSERTED.Proposal_ID
            VALUES (?, ?, ?, 'Active');
            """,
            [11, "Integration test proposal", 0],
        )
        proposal_id = int(_fetch_first_scalar(cursor))

        cursor.execute(
            """
            DECLARE @FinalStatus VARCHAR(20);
            EXEC dbo.usp_CastProposalVote ?, ?, ?, @FinalStatus OUTPUT;
            SELECT @FinalStatus;
            """,
            [proposal_id, 11, 1],
        )
        final_status = str(_fetch_first_scalar(cursor))
        assert final_status in {"Active", "Approved", "Rejected"}

        cursor.execute("SELECT Status FROM dbo.PROPOSAL WHERE Proposal_ID = ?", [proposal_id])
        status_row = cursor.fetchone()
        assert status_row is not None
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
