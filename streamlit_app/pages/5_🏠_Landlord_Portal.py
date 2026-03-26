"""
🏠 Landlord Portal
Role-locked portal for landlord operations.

Audit Hardening (Phase 2):
  - Removed all try/except schema fallback patterns that masked column mismatches.
  - All SQL now strictly targets the actual CoHabitant schema columns:
    PROPERTY: State, Zip_Code (not State_Province, Postal_Code)
    LEASE_AGREEMENT: Property_ID, Tenant_ID, Start_Date, End_Date, Move_In_Date
    UTILITY_READING: Utility_Type_ID, Provider_Name, Meter_Value, Reading_Date
  - Uses AppState instead of raw st.session_state access.
"""

import logging
from datetime import date
import pandas as pd
import streamlit as st

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import run_query, execute_transaction

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Landlord Portal - CoHabitant", page_icon="🏠", layout="wide")


def load_my_properties(landlord_id: int) -> pd.DataFrame:
    sql = """
    SELECT p.Property_ID, p.Street_Address, p.City, p.State, p.Zip_Code, p.Max_Occupancy,
           COUNT(la.Lease_ID) AS Lease_Count, MIN(la.Start_Date) AS First_Lease_Start, MAX(la.End_Date) AS Last_Lease_End
    FROM dbo.PROPERTY p
    LEFT JOIN dbo.LEASE_AGREEMENT la ON p.Property_ID = la.Property_ID AND la.Is_Active = 1
    WHERE p.Landlord_ID = ? AND p.Is_Active = 1
    GROUP BY p.Property_ID, p.Street_Address, p.City, p.State, p.Zip_Code, p.Max_Occupancy
    ORDER BY p.Property_ID DESC
    """
    return run_query(sql, [landlord_id])


def load_tenants() -> pd.DataFrame:
    """Load all active tenants for lease assignment."""
    sql = """
    SELECT t.Tenant_ID, p.First_Name + ' ' + p.Last_Name AS Full_Name
    FROM dbo.TENANT t INNER JOIN dbo.PERSON p ON p.Person_ID = t.Tenant_ID
    WHERE t.Is_Active = 1 ORDER BY p.First_Name, p.Last_Name
    """
    return run_query(sql)


def load_utility_types() -> pd.DataFrame:
    """Load utility types from the schema (UTILITY_TYPE table)."""
    sql = """
    SELECT Utility_Type_ID, Type_Name
    FROM dbo.UTILITY_TYPE
    ORDER BY Type_Name
    """
    return run_query(sql)


def tab_my_properties(landlord_id: int):
    st.subheader("My Properties")
    try:
        df = load_my_properties(landlord_id)
        if df.empty:
            st.info("No properties found for your account yet.")
            return
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception as exc:
        st.error(f"Failed to load properties: {exc}")
        logger.error("My Properties query failed for user %s: %s", landlord_id, exc)


def tab_add_property(landlord_id: int):
    st.subheader("Add Property")
    with st.form("add_property_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            street = st.text_input("Street Address")
            city = st.text_input("City")
            state = st.text_input("State")
        with col2:
            zip_code = st.text_input("Zip Code")
            max_occupancy = st.number_input("Max Occupancy", min_value=1, max_value=100, value=4, step=1)

        submitted = st.form_submit_button("Create Property")
        if submitted:
            if not street.strip() or not city.strip() or not state.strip() or not zip_code.strip():
                st.error("Street Address, City, State, and Zip Code are required.")
                return
            try:
                execute_transaction(
                    "INSERT INTO dbo.PROPERTY (Landlord_ID, Street_Address, City, State, Zip_Code, Max_Occupancy) VALUES (?, ?, ?, ?, ?, ?)",
                    [landlord_id, street.strip(), city.strip(), state.strip(), zip_code.strip(), int(max_occupancy)],
                )
                st.success("Property created successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create property: {exc}")
                logger.error("Property insert failed for landlord %s: %s", landlord_id, exc)


def tab_create_lease(landlord_id: int):
    st.subheader("Create Lease")
    try:
        properties_df = load_my_properties(landlord_id)
    except Exception as exc:
        st.error(f"Could not load properties: {exc}")
        return

    if properties_df.empty:
        st.info("Add at least one property before creating a lease.")
        return

    try:
        tenants_df = load_tenants()
    except Exception as exc:
        st.error(f"Could not load tenants: {exc}")
        return

    if tenants_df.empty:
        st.info("No tenants registered yet. Tenants must register before a lease can be created.")
        return

    property_options = {
        f"#{int(row['Property_ID'])} | {row['Street_Address']}, {row['City']}": int(row["Property_ID"])
        for _, row in properties_df.iterrows()
    }
    tenant_options = {
        f"#{int(row['Tenant_ID'])} | {row['Full_Name']}": int(row["Tenant_ID"])
        for _, row in tenants_df.iterrows()
    }

    with st.form("create_lease_form", clear_on_submit=True):
        selected_property = st.selectbox("Property", list(property_options.keys()))
        selected_tenant = st.selectbox("Tenant", list(tenant_options.keys()))

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=date.today())
        with col2:
            end_date = st.date_input("End Date", value=date.today())

        move_in_date = st.date_input("Move-In Date", value=date.today())

        submitted = st.form_submit_button("Create Lease")
        if submitted:
            if end_date <= start_date:
                st.error("End Date must be later than Start Date.")
                return

            property_id = property_options[selected_property]
            tenant_id = tenant_options[selected_tenant]

            try:
                execute_transaction(
                    "INSERT INTO dbo.LEASE_AGREEMENT (Property_ID, Tenant_ID, Start_Date, End_Date, Move_In_Date) VALUES (?, ?, ?, ?, ?)",
                    [property_id, tenant_id, start_date, end_date, move_in_date],
                )
                st.success("Lease created successfully.")
                logger.info("Lease created for property %s, tenant %s", property_id, tenant_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create lease: {exc}")
                logger.error("Lease insert failed: %s", exc)


def tab_log_utility_bill(landlord_id: int):
    st.subheader("Log Utility Reading")
    try:
        properties_df = load_my_properties(landlord_id)
    except Exception as exc:
        st.error(f"Could not load properties: {exc}")
        return

    if properties_df.empty:
        st.info("Add at least one property before logging utility readings.")
        return

    try:
        types_df = load_utility_types()
    except Exception as exc:
        st.error(f"Could not load utility types: {exc}")
        return

    if types_df.empty:
        st.info("No utility types defined in the database.")
        return

    property_options = {
        f"#{int(row['Property_ID'])} | {row['Street_Address']}, {row['City']}": int(row["Property_ID"])
        for _, row in properties_df.iterrows()
    }
    type_options = {
        f"#{int(row['Utility_Type_ID'])} | {row['Type_Name']}": int(row["Utility_Type_ID"])
        for _, row in types_df.iterrows()
    }

    with st.form("log_utility_bill_form", clear_on_submit=True):
        selected_property = st.selectbox("Property", list(property_options.keys()))
        selected_type = st.selectbox("Utility Type", list(type_options.keys()))

        col1, col2 = st.columns(2)
        with col1:
            reading_date = st.date_input("Reading Date", value=date.today())
        with col2:
            meter_value = st.number_input("Meter Value / Cost ($)", min_value=0.0, value=0.0, step=10.0, format="%.2f")

        provider_name = st.text_input("Provider Name", placeholder="e.g., National Grid, Eversource")

        submitted = st.form_submit_button("Log Utility Reading")
        if submitted:
            property_id = property_options[selected_property]
            utility_type_id = type_options[selected_type]

            try:
                execute_transaction(
                    "INSERT INTO dbo.UTILITY_READING (Property_ID, Utility_Type_ID, Provider_Name, Meter_Value, Reading_Date) VALUES (?, ?, ?, ?, ?)",
                    [property_id, utility_type_id, provider_name.strip() or None, meter_value, reading_date],
                )
                st.success("Utility reading logged successfully.")
                logger.info("Utility reading logged for property %s", property_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to log utility reading: {exc}")
                logger.error("Utility reading insert failed: %s", exc)


def main():
    auth_gate("Landlord")
    state = AppState()
    landlord_id = state.user_id

    st.title("🏠 Landlord Portal")
    st.caption("Manage properties, leases, and utility readings.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏘️ My Properties", "➕ Add Property", "📄 Create Lease", "💡 Log Utility Reading"
    ])
    with tab1: tab_my_properties(landlord_id)
    with tab2: tab_add_property(landlord_id)
    with tab3: tab_create_lease(landlord_id)
    with tab4: tab_log_utility_bill(landlord_id)


if __name__ == "__main__":
    main()
