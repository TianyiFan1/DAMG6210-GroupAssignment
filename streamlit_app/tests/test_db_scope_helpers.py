"""Unit tests for tenant-scope DB helper behavior without live DB access."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


STREAMLIT_APP_DIR = Path(__file__).resolve().parents[1]
if str(STREAMLIT_APP_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_APP_DIR))

from utils import db


def test_get_tenant_property_id_returns_id(monkeypatch):
    calls = []

    def fake_run_query(sql, params=None):
        calls.append((sql, params))
        return pd.DataFrame([{"Property_ID": 42}])

    monkeypatch.setattr(db, "run_query", fake_run_query)

    value = db.get_tenant_property_id(7)

    assert value == 42
    assert calls[0][1] == [7]


def test_get_tenant_property_id_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: pd.DataFrame())
    assert db.get_tenant_property_id(7) is None


def test_get_roommate_ids_returns_empty_without_property(monkeypatch):
    monkeypatch.setattr(db, "get_tenant_property_id", lambda tenant_id: None)
    assert db.get_roommate_ids(9) == []


def test_get_roommate_ids_happy_path(monkeypatch):
    monkeypatch.setattr(db, "get_tenant_property_id", lambda tenant_id: 100)

    def fake_run_query(sql, params=None):
        assert params == [100]
        return pd.DataFrame([{"Tenant_ID": 1}, {"Tenant_ID": 2}, {"Tenant_ID": 5}])

    monkeypatch.setattr(db, "run_query", fake_run_query)

    assert db.get_roommate_ids(1) == [1, 2, 5]


def test_load_roommates_details_filters_self(monkeypatch):
    monkeypatch.setattr(db, "get_roommate_ids", lambda tenant_id: [3, 4, 5])

    def fake_run_query(sql, params=None):
        # self (3) should be excluded
        assert params == [4, 5]
        return pd.DataFrame(
            [
                {"First_Name": "A", "Last_Name": "B", "Email": "a@x.com", "Phone_Number": "1"},
                {"First_Name": "C", "Last_Name": "D", "Email": "c@x.com", "Phone_Number": "2"},
            ]
        )

    monkeypatch.setattr(db, "run_query", fake_run_query)

    df = db.load_roommates_details(3)
    assert len(df) == 2
    assert set(df.columns) == {"First_Name", "Last_Name", "Email", "Phone_Number"}


def test_get_active_tenants_scoped(monkeypatch):
    monkeypatch.setattr(db, "get_roommate_ids", lambda tenant_id: [8, 9])

    def fake_run_query(sql, params=None):
        assert params == [8, 9]
        return pd.DataFrame([{"Tenant_ID": 8, "Full_Name": "T1", "Email": "t1@x.com"}])

    monkeypatch.setattr(db, "run_query", fake_run_query)

    df = db.get_active_tenants(tenant_id=8)
    assert not df.empty
