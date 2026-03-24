"""Pure financial transaction helpers for expense creation logic."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Tuple


def normalize_roommates(payer_tenant_id: int, roommates: Iterable[int] | None) -> List[int]:
    """Return a deduplicated roommate list that always includes the payer."""
    values = list(dict.fromkeys(int(r) for r in (roommates or [])))
    if not values:
        return [int(payer_tenant_id)]
    if int(payer_tenant_id) not in values:
        values.append(int(payer_tenant_id))
    return values


def calculate_equal_split(total_amount: float, payer_tenant_id: int, roommates: Iterable[int] | None) -> Dict[int, float]:
    """Return per-roommate owed amounts for equal split (excluding payer)."""
    roster = normalize_roommates(payer_tenant_id, roommates)
    divisor = max(len(roster), 1)
    split_amount = float(total_amount) / divisor
    return {rid: split_amount for rid in roster if rid != int(payer_tenant_id)}


def calculate_custom_split(
    total_amount: float,
    payer_tenant_id: int,
    roommates: Iterable[int] | None,
    custom_owed_amounts: Dict[int, float] | None,
) -> Dict[int, float]:
    """Validate and return per-roommate owed amounts for custom split."""
    roster = normalize_roommates(payer_tenant_id, roommates)
    payload = {int(k): float(v) for k, v in (custom_owed_amounts or {}).items()}

    for rid, owed in payload.items():
        if rid == int(payer_tenant_id):
            raise ValueError("Custom split cannot assign owed amount to payer.")
        if rid not in roster:
            raise ValueError("Custom split contains a tenant outside the roommate roster.")
        if owed < 0:
            raise ValueError("Custom split values cannot be negative.")

    total_roommate_owed = sum(payload.values())
    if total_roommate_owed - float(total_amount) > 0.0001:
        raise ValueError("Custom split exceeds total amount.")

    return payload


def build_expense_transaction_sql_params(
    payer_tenant_id: int,
    total_amount: float,
    date_incurred: date,
    split_policy: str,
    description: str,
    notes: str,
    roommates: Iterable[int] | None,
    custom_owed_amounts: Dict[int, float] | None = None,
) -> Tuple[str, List[object], float]:
    """Build one SQL transaction and params for expense + shares + balances + payment."""
    roster = normalize_roommates(payer_tenant_id, roommates)

    if split_policy == "Custom":
        per_roommate_owed = calculate_custom_split(total_amount, payer_tenant_id, roster, custom_owed_amounts)
    else:
        per_roommate_owed = calculate_equal_split(total_amount, payer_tenant_id, roster)

    payer_gain = float(sum(per_roommate_owed.values()))

    sql_statements: List[str] = []
    params: List[object] = []

    sql_statements.append(
        "INSERT INTO dbo.EXPENSE (Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy) VALUES (?, ?, ?, ?);"
    )
    params.extend([int(payer_tenant_id), float(total_amount), date_incurred, split_policy])

    sql_statements.append("DECLARE @NewID INT = SCOPE_IDENTITY();")

    for rid, owed_amount in per_roommate_owed.items():
        if owed_amount <= 0:
            continue
        sql_statements.append(
            "INSERT INTO dbo.EXPENSE_SHARE (Expense_ID, Owed_By_Tenant_ID, Owed_Amount) VALUES (@NewID, ?, ?);"
        )
        params.extend([int(rid), float(owed_amount)])

        sql_statements.append(
            "UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) - ? WHERE Tenant_ID = ?;"
        )
        params.extend([float(owed_amount), int(rid)])

    sql_statements.append(
        "UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) + ? WHERE Tenant_ID = ?;"
    )
    params.extend([float(payer_gain), int(payer_tenant_id)])

    # Lifetime_Paid is computed in view from PAYMENT table.
    sql_statements.append(
        "INSERT INTO dbo.PAYMENT (Payer_Tenant_ID, Amount, Payment_Date, Note) VALUES (?, ?, ?, ?);"
    )
    params.extend([int(payer_tenant_id), float(total_amount), date_incurred, (description.strip() or notes.strip() or None)])

    return " ".join(sql_statements), params, payer_gain
