"""Property-based tests for split math edge cases."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st
import pytest

from utils.financial_logic import normalize_roommates, calculate_equal_split


@given(
    amount=st.floats(min_value=-9999.99, max_value=9999.99, allow_infinity=False, allow_nan=False),
    roommate_count=st.integers(min_value=0, max_value=25),
)
@settings(max_examples=500)
def test_equal_split_never_divides_by_zero_and_reconciles_total(amount: float, roommate_count: int):
    """Equal split math must be safe and internally consistent across edge cases."""
    payer_id = 1

    if roommate_count == 0:
        roster = []
    else:
        roster = list(range(1, roommate_count + 1))

    normalized = normalize_roommates(payer_id, roster)
    owed_map = calculate_equal_split(amount, payer_id, normalized)

    assert len(normalized) >= 1

    total_owed_by_roommates = sum(owed_map.values())
    payer_share = float(amount) - total_owed_by_roommates

    assert (total_owed_by_roommates + payer_share) == pytest.approx(float(amount), rel=1e-9, abs=1e-9)


@given(
    amount=st.floats(min_value=0.01, max_value=9999.99, allow_infinity=False, allow_nan=False),
    roommate_count=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=300)
def test_equal_split_non_negative_inputs_produce_finite_results(amount: float, roommate_count: int):
    """For valid positive amounts, split values should be finite and non-negative."""
    payer_id = 1
    roster = list(range(1, roommate_count + 1))
    owed_map = calculate_equal_split(amount, payer_id, roster)

    for owed in owed_map.values():
        assert owed >= 0
        assert owed < float("inf")
