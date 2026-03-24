"""
👥 House Hub
Tenant-only page for guests, subleases, and chore definitions.
"""

import logging
from datetime import date
import pandas as pd
import streamlit as st

from utils.db import run_query, execute_transaction

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="House Hub - CoHabitant",
    page_icon="👥",
    layout="wide",
)


def check_tenant_authenticated():
    """Enforce tenant-only access to this page."""
    if st.session_state.get("logged_in_user_id") is None:
        st.error("You must be logged in to access the House Hub.")
        st.stop()

    if st.session_state.get("logged_in_role") != "Tenant":
        st.error("Access denied. This page is restricted to Tenants.")
        st.stop()


def load_other_tenants(current_tenant_id: int) -> pd.DataFrame:
    """Load all tenants except the current user for sublease assignment."""
    sql = """
    SELECT
        t.Tenant_ID,
        p.First_Name + ' ' + p.Last_Name AS Full_Name
    FROM dbo.TENANT t
    INNER JOIN dbo.PERSON p ON p.Person_ID = t.Tenant_ID
    WHERE t.Tenant_ID <> ?
    ORDER BY p.First_Name, p.Last_Name
    """
    return run_query(sql, [current_tenant_id])


def tab_register_guest(tenant_id: int):
    """Register Guest tab (CREATE)."""
    st.subheader("Register Guest")

    with st.form("register_guest_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("Guest First Name")
            arrival_date = st.date_input("Arrival Date", value=date.today())
        with col2:
            last_name = st.text_input("Guest Last Name")
            is_overnight = st.checkbox("Overnight Guest", value=False)

        submitted = st.form_submit_button("Register Guest")

        if submitted:
            if not first_name.strip() or not last_name.strip():
                st.error("First Name and Last Name are required.")
                return

            try:
                insert_sql = """
                INSERT INTO dbo.GUEST (
                    Tenant_ID,
                    First_Name,
                    Last_Name,
                    Arrival_Date,
                    Is_Overnight
                )
                VALUES (?, ?, ?, ?, ?)
                """
                execute_transaction(
                    insert_sql,
                    [tenant_id, first_name.strip(), last_name.strip(), arrival_date, 1 if is_overnight else 0],
                )
                st.success(f"Guest {first_name} {last_name} registered successfully.")
                logger.info("Guest registered by tenant %s", tenant_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to register guest: {exc}")
                logger.error("Guest registration failed for tenant %s: %s", tenant_id, exc)


def tab_create_sublease(tenant_id: int):
    """Create Sublease tab (CREATE)."""
    st.subheader("Create Sublease")

    try:
        other_tenants_df = load_other_tenants(tenant_id)
    except Exception as exc:
        st.error(f"Could not load tenants: {exc}")
        logger.error("Tenant load for sublease failed: %s", exc)
        return

    if other_tenants_df.empty:
        st.info("No other tenants available for sublease.")
        return

    tenant_options = {
        f"#{int(row['Tenant_ID'])} | {row['Full_Name']}": int(row["Tenant_ID"])
        for _, row in other_tenants_df.iterrows()
    }

    with st.form("create_sublease_form", clear_on_submit=True):
        selected_tenant = st.selectbox("Sublease to Tenant", list(tenant_options.keys()))

        start_date = st.date_input("Start Date", value=date.today())
        end_date = st.date_input("End Date", value=date.today())
        rent_amount = st.number_input("Pro-Rated Rent Amount", min_value=0.0, value=0.0, step=50.0, format="%.2f")

        submitted = st.form_submit_button("Create Sublease")

        if submitted:
            if end_date <= start_date:
                st.error("End Date must be later than Start Date.")
                return

            sub_tenant_id = tenant_options[selected_tenant]

            try:
                insert_sql = """
                INSERT INTO dbo.SUB_LEASE (
                    Tenant_ID,
                    Start_Date,
                    End_Date,
                    Pro_Rated_Cost
                )
                VALUES (?, ?, ?, ?)
                """
                execute_transaction(
                    insert_sql,
                    [sub_tenant_id, start_date, end_date, rent_amount],
                )
                st.success("Sublease created successfully.")
                logger.info("Sublease created by tenant %s for tenant %s", tenant_id, sub_tenant_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create sublease: {exc}")
                logger.error("Sublease creation failed for tenant %s: %s", tenant_id, exc)


def tab_define_chore(tenant_id: int):
    """Define Chore tab (CREATE)."""
    st.subheader("Define Chore")

    with st.form("define_chore_form", clear_on_submit=True):
        task_name = st.text_input("Task Name")
        description = st.text_area("Description", max_chars=255)

        col1, col2 = st.columns(2)
        with col1:
            difficulty_weight = st.slider("Difficulty Weight", min_value=1, max_value=10, value=5)
        with col2:
            frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])

        submitted = st.form_submit_button("Define Chore")

        if submitted:
            if not task_name.strip():
                st.error("Task Name is required.")
                return

            try:
                insert_sql = """
                INSERT INTO dbo.CHORE_DEFINITION (
                    Task_Name,
                    Description,
                    Difficulty_Weight,
                    Frequency
                )
                VALUES (?, ?, ?, ?)
                """
                execute_transaction(
                    insert_sql,
                    [task_name.strip(), description.strip() or None, int(difficulty_weight), frequency],
                )
                st.success(f"Chore '{task_name}' defined successfully.")
                logger.info("Chore defined by tenant %s", tenant_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to define chore: {exc}")
                logger.error("Chore definition failed for tenant %s: %s", tenant_id, exc)


def main():
    """House Hub entrypoint."""
    check_tenant_authenticated()

    tenant_id = int(st.session_state.get("logged_in_user_id"))

    st.title("👥 House Hub")
    st.caption("Manage guests, subleases, and chore definitions.")

    tab1, tab2, tab3 = st.tabs([
        "👤 Register Guest",
        "🏠 Create Sublease",
        "✓ Define Chore",
    ])

    with tab1:
        tab_register_guest(tenant_id)

    with tab2:
        tab_create_sublease(tenant_id)

    with tab3:
        tab_define_chore(tenant_id)


if __name__ == "__main__":
    main()
