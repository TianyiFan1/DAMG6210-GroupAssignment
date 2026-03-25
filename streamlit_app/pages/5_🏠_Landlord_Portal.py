"""
🏠 Landlord Portal
Role-locked portal for landlord operations.
"""

import logging
from datetime import date
import pandas as pd
import streamlit as st

from utils.auth import auth_gate
from utils.db import run_query, execute_transaction

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Landlord Portal - CoHabitant", page_icon="🏠", layout="wide")


def table_has_column(table_name: str, column_name: str) -> bool:
    sql = "SELECT COUNT(*) AS Cnt FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ? AND COLUMN_NAME = ?"
    try:
        df = run_query(sql, [table_name, column_name])
        return not df.empty and int(df.iloc[0]["Cnt"]) > 0
    except Exception as exc:
        logger.error("Failed metadata check for %s.%s: %s", table_name, column_name, exc)
        return False


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
    sql = """
    SELECT t.Tenant_ID, p.First_Name + ' ' + p.Last_Name AS Full_Name
    FROM dbo.TENANT t INNER JOIN dbo.PERSON p ON p.Person_ID = t.Tenant_ID
    WHERE t.Is_Active = 1 ORDER BY p.First_Name, p.Last_Name
    """
    return run_query(sql)


def load_utility_companies() -> pd.DataFrame:
    try:
        return run_query("SELECT Utility_Company_ID, Company_Name FROM dbo.UTILITY_COMPANY ORDER BY Company_Name")
    except Exception:
        return run_query("SELECT Utility_Type_ID AS Utility_Company_ID, Type_Name AS Company_Name FROM dbo.UTILITY_TYPE ORDER BY Type_Name")


def tab_my_properties(landlord_id: int):
    st.subheader("My Properties")
    try:
        df = load_my_properties(landlord_id)
        if df.empty: st.info("No properties found for your account yet."); return
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception as exc:
        st.error(f"Failed to load properties: {exc}")


def tab_add_property(landlord_id: int):
    st.subheader("Add Property")
    with st.form("add_property_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1: street = st.text_input("Street Address"); city = st.text_input("City"); state_province = st.text_input("State/Province")
        with col2: postal_code = st.text_input("Postal Code"); max_occupancy = st.number_input("Max Occupancy", min_value=1, max_value=100, value=4, step=1)
        submitted = st.form_submit_button("Create Property")
        if submitted:
            if not street.strip() or not city.strip() or not state_province.strip() or not postal_code.strip():
                st.error("Street Address, City, State/Province, and Postal Code are required."); return
            try:
                execute_transaction("INSERT INTO dbo.PROPERTY (Landlord_ID, Street_Address, City, State_Province, Postal_Code, Max_Occupancy) VALUES (?, ?, ?, ?, ?, ?)",
                                    [landlord_id, street.strip(), city.strip(), state_province.strip(), postal_code.strip(), int(max_occupancy)])
                st.success("Property created successfully."); st.rerun()
            except Exception:
                try:
                    execute_transaction("INSERT INTO dbo.PROPERTY (Landlord_ID, Street_Address, City, State, Zip_Code, Max_Occupancy) VALUES (?, ?, ?, ?, ?, ?)",
                                        [landlord_id, street.strip(), city.strip(), state_province.strip(), postal_code.strip(), int(max_occupancy)])
                    st.success("Property created successfully."); st.rerun()
                except Exception as fallback_exc:
                    st.error(f"Failed to create property: {fallback_exc}")


def tab_create_lease(landlord_id: int):
    st.subheader("Create Lease")
    try: properties_df = load_my_properties(landlord_id)
    except Exception as exc: st.error(f"Could not load properties: {exc}"); return
    if properties_df.empty: st.info("Add at least one property before creating a lease."); return
    property_options = {f"#{int(row['Property_ID'])} | {row['Street_Address']}, {row['City']}": int(row["Property_ID"]) for _, row in properties_df.iterrows()}
    requires_tenant_id = table_has_column("LEASE_AGREEMENT", "Tenant_ID")
    tenant_options = {}
    if requires_tenant_id:
        try:
            tenants_df = load_tenants()
            tenant_options = {f"#{int(row['Tenant_ID'])} | {row['Full_Name']}": int(row["Tenant_ID"]) for _, row in tenants_df.iterrows()}
        except Exception: pass
    with st.form("create_lease_form", clear_on_submit=True):
        selected_property = st.selectbox("Property", list(property_options.keys()))
        start_date = st.date_input("Start Date", value=date.today()); end_date = st.date_input("End Date", value=date.today())
        monthly_rent_amount = st.number_input("Monthly Rent Amount", min_value=0.0, value=0.0, step=50.0, format="%.2f")
        deposit_amount = st.number_input("Deposit Amount", min_value=0.0, value=0.0, step=50.0, format="%.2f")
        selected_tenant_label = None
        if requires_tenant_id and tenant_options:
            selected_tenant_label = st.selectbox("Tenant", list(tenant_options.keys()))
        submitted = st.form_submit_button("Create Lease")
        if submitted:
            if end_date <= start_date: st.error("End Date must be later than Start Date."); return
            property_id = property_options[selected_property]
            try:
                execute_transaction("INSERT INTO dbo.LEASE_AGREEMENT (Property_ID, Start_Date, End_Date, Monthly_Rent_Amount, Deposit_Amount) VALUES (?, ?, ?, ?, ?)",
                                    [property_id, start_date, end_date, monthly_rent_amount, deposit_amount])
                st.success("Lease created successfully."); st.rerun()
            except Exception:
                try:
                    if not requires_tenant_id or not selected_tenant_label: raise Exception("Tenant selection required.")
                    tenant_id = tenant_options[selected_tenant_label]
                    execute_transaction("INSERT INTO dbo.LEASE_AGREEMENT (Property_ID, Tenant_ID, Start_Date, End_Date, Move_In_Date, Document_URL) VALUES (?, ?, ?, ?, ?, ?)",
                                        [property_id, tenant_id, start_date, end_date, start_date, None])
                    st.success("Lease created successfully."); st.rerun()
                except Exception as fallback_exc:
                    st.error(f"Failed to create lease: {fallback_exc}")


def tab_log_utility_bill(landlord_id: int):
    st.subheader("Log Utility Bill")
    try: properties_df = load_my_properties(landlord_id)
    except Exception as exc: st.error(f"Could not load properties: {exc}"); return
    if properties_df.empty: st.info("Add at least one property before logging utility bills."); return
    try: companies_df = load_utility_companies()
    except Exception as exc: st.error(f"Could not load utility companies: {exc}"); return
    if companies_df.empty: st.info("No utility companies available."); return
    property_options = {f"#{int(row['Property_ID'])} | {row['Street_Address']}, {row['City']}": int(row["Property_ID"]) for _, row in properties_df.iterrows()}
    company_options = {f"#{int(row['Utility_Company_ID'])} | {row['Company_Name']}": int(row["Utility_Company_ID"]) for _, row in companies_df.iterrows()}
    with st.form("log_utility_bill_form", clear_on_submit=True):
        selected_property = st.selectbox("Property", list(property_options.keys()))
        selected_company = st.selectbox("Utility Company", list(company_options.keys()))
        reading_date = st.date_input("Reading Date", value=date.today())
        cost_amount = st.number_input("Cost Amount", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        billing_period_start = st.date_input("Billing Period Start", value=date.today())
        billing_period_end = st.date_input("Billing Period End", value=date.today())
        submitted = st.form_submit_button("Log Utility Bill")
        if submitted:
            if billing_period_end < billing_period_start: st.error("Billing Period End cannot be earlier than Start."); return
            property_id = property_options[selected_property]
            utility_company_id = company_options[selected_company]
            provider_name = selected_company.split("|", maxsplit=1)[1].strip() if "|" in selected_company else selected_company
            try:
                execute_transaction("INSERT INTO dbo.UTILITY_READING (Property_ID, Utility_Company_ID, Reading_Date, Cost_Amount, Billing_Period_Start, Billing_Period_End) VALUES (?, ?, ?, ?, ?, ?)",
                                    [property_id, utility_company_id, reading_date, cost_amount, billing_period_start, billing_period_end])
                st.success("Utility bill logged successfully."); st.rerun()
            except Exception:
                try:
                    execute_transaction("INSERT INTO dbo.UTILITY_READING (Property_ID, Utility_Type_ID, Provider_Name, Meter_Value, Reading_Date) VALUES (?, ?, ?, ?, ?)",
                                        [property_id, utility_company_id, provider_name, cost_amount, reading_date])
                    st.success("Utility bill logged successfully."); st.rerun()
                except Exception as fallback_exc:
                    st.error(f"Failed to log utility bill: {fallback_exc}")


def main():
    auth_gate("Landlord")
    landlord_id = int(st.session_state.get("logged_in_user_id"))
    st.title("🏠 Landlord Portal")
    st.caption("Manage properties, leases, and utility bills.")
    tab1, tab2, tab3, tab4 = st.tabs(["🏘️ My Properties", "➕ Add Property", "📄 Create Lease", "💡 Log Utility Bill"])
    with tab1: tab_my_properties(landlord_id)
    with tab2: tab_add_property(landlord_id)
    with tab3: tab_create_lease(landlord_id)
    with tab4: tab_log_utility_bill(landlord_id)


if __name__ == "__main__":
    main()
