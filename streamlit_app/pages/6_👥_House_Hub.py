"""
👥 House Hub
Tenant-only page for guests, subleases, and chore definitions.
"""

import logging
from datetime import date
import pandas as pd
import streamlit as st

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import run_query, execute_transaction, get_roommate_ids, load_roommates_details

logger = logging.getLogger(__name__)

st.set_page_config(page_title="House Hub - CoHabitant", page_icon="👥", layout="wide")


def load_other_tenants(current_tenant_id: int) -> pd.DataFrame:
    roommate_ids = [rid for rid in get_roommate_ids(current_tenant_id) if rid != current_tenant_id]
    if not roommate_ids:
        return pd.DataFrame(columns=["Tenant_ID", "Full_Name"])
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"SELECT t.Tenant_ID, p.First_Name + ' ' + p.Last_Name AS Full_Name FROM dbo.TENANT t INNER JOIN dbo.PERSON p ON p.Person_ID = t.Tenant_ID WHERE t.Tenant_ID IN ({placeholders}) AND t.Is_Active = 1 ORDER BY p.First_Name, p.Last_Name"
    return run_query(sql, roommate_ids)


def load_my_lease_details(tenant_id: int) -> pd.DataFrame:
    sql = """
    SELECT la.Lease_ID, p.Street_Address, p.City, p.State, p.Zip_Code, p.Max_Occupancy,
           la.Start_Date, la.End_Date, la.Move_In_Date,
           pers.First_Name AS Landlord_First_Name, pers.Last_Name AS Landlord_Last_Name, pers.Email AS Landlord_Email
    FROM dbo.LEASE_AGREEMENT la
    INNER JOIN dbo.PROPERTY p ON p.Property_ID = la.Property_ID
    INNER JOIN dbo.LANDLORD l ON l.Landlord_ID = p.Landlord_ID
    INNER JOIN dbo.PERSON pers ON pers.Person_ID = l.Landlord_ID
    WHERE la.Tenant_ID = ? AND la.Is_Active = 1
      AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ORDER BY la.Start_Date DESC
    """
    return run_query(sql, [tenant_id])


def load_my_active_lease_window(tenant_id: int) -> pd.DataFrame:
    sql = """
    SELECT TOP 1 Start_Date, End_Date FROM dbo.LEASE_AGREEMENT
    WHERE Tenant_ID = ? AND Is_Active = 1 AND CAST(GETDATE() AS DATE) BETWEEN Start_Date AND End_Date
    ORDER BY End_Date DESC, Lease_ID DESC
    """
    return run_query(sql, [tenant_id])


def tab_my_lease_details(tenant_id: int):
    st.subheader("🏠 My Current Lease")
    try:
        lease_df = load_my_lease_details(tenant_id)
        if lease_df.empty:
            st.info("You don't have an active lease yet. Head to the onboarding to join a house!")
            return
        lease = lease_df.iloc[0]
        st.markdown("### 📍 Property Details")
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Street Address", lease["Street_Address"] or "N/A")
        with col2: st.metric("City", lease["City"] or "N/A")
        with col3: st.metric("Max Occupancy", int(lease["Max_Occupancy"]) if lease["Max_Occupancy"] else "N/A")
        st.markdown("### 📋 Lease Terms")
        col4, col5, col6 = st.columns(3)
        with col4: st.metric("Start Date", str(lease["Start_Date"]))
        with col5: st.metric("End Date", str(lease["End_Date"]))
        with col6: st.metric("Move-In Date", str(lease["Move_In_Date"]))
        st.markdown("### 👤 Landlord Information")
        col7, col8 = st.columns(2)
        with col7: st.metric("Name", f"{lease['Landlord_First_Name']} {lease['Landlord_Last_Name']}")
        with col8: st.metric("Email", lease['Landlord_Email'] or "N/A")
        st.markdown("### 👥 My Roommates")
        roommates_df = load_roommates_details(tenant_id)
        if roommates_df.empty:
            st.info("No active roommates found for your current property.")
        else:
            for _, roommate in roommates_df.iterrows():
                col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
                with col1:
                    st.write(f"**{roommate['First_Name']} {roommate['Last_Name']}**")
                with col2:
                    if roommate.get('Email'):
                        st.markdown(f"[📧 Email](mailto:{roommate['Email']})")
                    else:
                        st.write("—")
                with col3:
                    if roommate.get('Phone_Number'):
                        st.markdown(f"[📞 Call](tel:{roommate['Phone_Number']})")
                    else:
                        st.write("—")
                with col4:
                    st.caption(f"@{roommate['First_Name'].lower()}")
        st.divider()
    except Exception as exc:
        st.error(f"Failed to load lease details: {exc}")
        logger.error("Lease details load failed for tenant %s: %s", tenant_id, exc)


def tab_register_guest(tenant_id: int):
    st.subheader("Register Guest")
    with st.form("register_guest_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1: first_name = st.text_input("Guest First Name"); arrival_date = st.date_input("Arrival Date", value=date.today())
        with col2: last_name = st.text_input("Guest Last Name"); is_overnight = st.checkbox("Overnight Guest", value=False)
        submitted = st.form_submit_button("Register Guest")
        if submitted:
            if not first_name.strip() or not last_name.strip(): st.error("First Name and Last Name are required."); return
            try:
                execute_transaction("INSERT INTO dbo.GUEST (Tenant_ID, First_Name, Last_Name, Arrival_Date, Is_Overnight) VALUES (?, ?, ?, ?, ?)",
                                    [tenant_id, first_name.strip(), last_name.strip(), arrival_date, 1 if is_overnight else 0])
                st.success(f"Guest {first_name} {last_name} registered successfully."); st.rerun()
            except Exception as exc:
                st.error(f"Failed to register guest: {exc}")


def tab_create_sublease(tenant_id: int):
    st.subheader("Create Sublease")
    lease_window_df = load_my_active_lease_window(tenant_id)
    if lease_window_df.empty: st.info("You need an active lease before creating a sublease."); return
    lease_start = lease_window_df.iloc[0]["Start_Date"]; lease_end = lease_window_df.iloc[0]["End_Date"]
    st.caption(f"Your active lease window: {lease_start} to {lease_end}")
    with st.form("create_sublease_form", clear_on_submit=True):
        start_date = st.date_input("Start Date", value=date.today()); end_date = st.date_input("End Date", value=date.today())
        rent_amount = st.number_input("Pro-Rated Rent Amount", min_value=0.0, value=0.0, step=50.0, format="%.2f")
        submitted = st.form_submit_button("Create Sublease")
        if submitted:
            if end_date <= start_date: st.error("End Date must be later than Start Date."); return
            if start_date < lease_start or end_date > lease_end: st.error("Sublease period must be inside your active lease window."); return
            try:
                execute_transaction("INSERT INTO dbo.SUB_LEASE (Tenant_ID, Start_Date, End_Date, Pro_Rated_Cost) VALUES (?, ?, ?, ?)",
                                    [tenant_id, start_date, end_date, rent_amount])
                st.success("Sublease created successfully."); st.rerun()
            except Exception as exc:
                st.error(f"Failed to create sublease: {exc}")


def tab_define_chore(tenant_id: int):
    st.subheader("Define Chore")
    with st.form("define_chore_form", clear_on_submit=True):
        task_name = st.text_input("Task Name"); description = st.text_area("Description", max_chars=255)
        col1, col2 = st.columns(2)
        with col1: difficulty_weight = st.slider("Difficulty Weight", min_value=1, max_value=10, value=5)
        with col2: frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
        submitted = st.form_submit_button("Define Chore")
        if submitted:
            if not task_name.strip(): st.error("Task Name is required."); return
            try:
                execute_transaction("INSERT INTO dbo.CHORE_DEFINITION (Task_Name, Description, Difficulty_Weight, Frequency) VALUES (?, ?, ?, ?)",
                                    [task_name.strip(), description.strip() or None, int(difficulty_weight), frequency])
                st.success(f"Chore '{task_name}' defined successfully."); st.rerun()
            except Exception as exc:
                st.error(f"Failed to define chore: {exc}")


def main():
    auth_gate("Tenant")
    state = AppState()
    tenant_id = state.user_id

    st.title("👥 House Hub")
    st.caption("Manage guests, subleases, and chore definitions.")
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 My Lease Details", "👤 Register Guest", "🏠 Create Sublease", "✓ Define Chore"])
    with tab1: tab_my_lease_details(tenant_id)
    with tab2: tab_register_guest(tenant_id)
    with tab3: tab_create_sublease(tenant_id)
    with tab4: tab_define_chore(tenant_id)


if __name__ == "__main__":
    main()
