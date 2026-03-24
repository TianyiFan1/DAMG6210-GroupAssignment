"""Database transaction-shape tests for financial expense logic."""

from __future__ import annotations

from datetime import date

import pytest

from utils.financial_logic import build_expense_transaction_sql_params


def test_equal_split_builds_expected_sql_and_params(mocker):
    """Equal split should create shares for each roommate and proper balance updates."""
    execute_mock = mocker.Mock()

    sql, params, payer_gain = build_expense_transaction_sql_params(
        payer_tenant_id=1,
        total_amount=120.0,
        date_incurred=date(2026, 3, 24),
        split_policy="Equal",
        description="Household cleaning supplies",
        notes="AI parsed note",
        roommates=[1, 2, 3],
        custom_owed_amounts=None,
    )

    execute_mock(sql, params)

    assert "INSERT INTO dbo.EXPENSE" in sql
    assert "DECLARE @NewID INT = SCOPE_IDENTITY();" in sql
    assert sql.count("INSERT INTO dbo.EXPENSE_SHARE") == 2
    assert sql.count("UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) - ?") == 2
    assert "UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) + ?" in sql
    assert "INSERT INTO dbo.PAYMENT" in sql

    assert payer_gain == pytest.approx(80.0)
    assert params[0:4] == [1, 120.0, date(2026, 3, 24), "Equal"]
    assert params[-6] == pytest.approx(80.0)
    assert params[-5] == 1
    assert params[-3] == 120.0

    execute_mock.assert_called_once_with(sql, params)


def test_custom_split_builds_exact_roommate_owed_values(mocker):
    """Custom split should preserve caller-provided owed values and payer gain."""
    execute_mock = mocker.Mock()

    sql, params, payer_gain = build_expense_transaction_sql_params(
        payer_tenant_id=10,
        total_amount=150.0,
        date_incurred=date(2026, 3, 24),
        split_policy="Custom",
        description="Target shared + personal",
        notes="Top items",
        roommates=[10, 11, 12],
        custom_owed_amounts={11: 20.0, 12: 50.0},
    )

    execute_mock(sql, params)

    assert sql.count("INSERT INTO dbo.EXPENSE_SHARE") == 2
    assert payer_gain == pytest.approx(70.0)
    assert 20.0 in params
    assert 50.0 in params
    assert params[-6] == pytest.approx(70.0)
    assert params[-5] == 10
    assert params[-3] == 150.0

    execute_mock.assert_called_once_with(sql, params)


def test_custom_split_rejects_invalid_payloads():
    """Invalid custom splits should fail fast before DB execution."""
    with pytest.raises(ValueError):
        build_expense_transaction_sql_params(
            payer_tenant_id=1,
            total_amount=100.0,
            date_incurred=date(2026, 3, 24),
            split_policy="Custom",
            description="desc",
            notes="note",
            roommates=[1, 2],
            custom_owed_amounts={2: -1.0},
        )

    with pytest.raises(ValueError):
        build_expense_transaction_sql_params(
            payer_tenant_id=1,
            total_amount=100.0,
            date_incurred=date(2026, 3, 24),
            split_policy="Custom",
            description="desc",
            notes="note",
            roommates=[1, 2],
            custom_owed_amounts={2: 110.0},
        )
