"""
📦 Inventory
Tenant-only page for shared and personal item management.
"""

import logging
from datetime import date
import pandas as pd
import streamlit as st

from utils.db import run_query, execute_transaction

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Inventory - CoHabitant",
    page_icon="📦",
    layout="wide",
)


def check_tenant_authenticated():
    """Enforce tenant-only access to this page."""
    if st.session_state.get("logged_in_user_id") is None:
        st.error("You must be logged in to access the Inventory.")
        st.stop()

    if st.session_state.get("logged_in_role") != "Tenant":
        st.error("Access denied. This page is restricted to Tenants.")
        st.stop()


def get_tenant_properties(tenant_id: int) -> pd.DataFrame:
    """Get properties associated with this tenant via lease."""
    sql = """
    SELECT DISTINCT
        p.Property_ID,
        p.Street_Address + ', ' + p.City AS Property_Name
    FROM dbo.PROPERTY p
    INNER JOIN dbo.LEASE_AGREEMENT la ON p.Property_ID = la.Property_ID
    WHERE la.Tenant_ID = ?
    ORDER BY Property_Name
    """
    return run_query(sql, [tenant_id])


def load_inventory_items() -> pd.DataFrame:
    """READ: Load all inventory items with shared/personal classification."""
    sql = """
    SELECT
        ii.Item_ID,
        ii.Item_Name,
        ii.Total_Quantity,
        ii.Category,
        ii.Storage_Location,
        CASE
            WHEN si.Item_ID IS NOT NULL THEN 'Shared'
            WHEN pi.Item_ID IS NOT NULL THEN 'Personal'
            ELSE 'Unclassified'
        END AS Item_Type,
        CASE WHEN si.Item_ID IS NOT NULL THEN si.Low_Stock_Threshold ELSE NULL END AS Low_Stock_Threshold,
        CASE WHEN pi.Item_ID IS NOT NULL THEN pi.Is_Private ELSE NULL END AS Is_Private
    FROM dbo.INVENTORY_ITEM ii
    LEFT JOIN dbo.SHARED_ITEM si ON ii.Item_ID = si.Item_ID
    LEFT JOIN dbo.PERSONAL_ITEM pi ON ii.Item_ID = pi.Item_ID
    ORDER BY ii.Item_Name
    """
    return run_query(sql)


def tab_read_inventory():
    """READ Inventory tab."""
    st.subheader("Inventory Items")

    try:
        df = load_inventory_items()
        if df.empty:
            st.info("No inventory items found.")
            return

        st.dataframe(df, width="stretch", hide_index=True)
        logger.info("Loaded inventory items")
    except Exception as exc:
        st.error(f"Failed to load inventory: {exc}")
        logger.error("Inventory load failed: %s", exc)


def tab_add_shared_item(tenant_id: int):
    """Add Shared Item tab (two-step CREATE)."""
    st.subheader("Add Shared Item")

    try:
        properties_df = get_tenant_properties(tenant_id)
    except Exception as exc:
        st.warning(f"Could not load properties: {exc}")
        logger.error("Property load for shared item failed: %s", exc)
        properties_df = pd.DataFrame()

    if properties_df.empty:
        st.info("You must have a lease to add shared items. Shared items belong to a property.")

    property_options = {}
    if not properties_df.empty:
        property_options = {
            f"#{int(row['Property_ID'])} | {row['Property_Name']}": int(row["Property_ID"])
            for _, row in properties_df.iterrows()
        }

    with st.form("add_shared_item_form", clear_on_submit=True):
        item_name = st.text_input("Item Name")
        quantity = st.number_input("Quantity", min_value=0, max_value=10000, value=1, step=1)
        category = st.text_input("Category")
        storage_location = st.text_input("Storage Location")
        low_stock_threshold = st.number_input("Low Stock Threshold", min_value=0, value=1, step=1)

        selected_property = None
        if property_options:
            selected_property = st.selectbox("Property", list(property_options.keys()))
            property_id = property_options[selected_property]
        else:
            property_id = None
            st.warning("No property selected.")

        submitted = st.form_submit_button("Add Shared Item")

        if submitted:
            if not item_name.strip():
                st.error("Item Name is required.")
                return

            if property_id is None:
                st.error("A property must be selected for shared items.")
                return

            try:
                insert_inventory_sql = """
                INSERT INTO dbo.INVENTORY_ITEM (
                    Item_Name,
                    Total_Quantity,
                    Category,
                    Storage_Location
                )
                VALUES (?, ?, ?, ?)
                """
                execute_transaction(
                    insert_inventory_sql,
                    [item_name.strip(), int(quantity), category.strip() or None, storage_location.strip() or None],
                )

                item_lookup_sql = """
                SELECT TOP 1 Item_ID
                FROM dbo.INVENTORY_ITEM
                ORDER BY Item_ID DESC
                """
                item_df = run_query(item_lookup_sql)
                if item_df.empty:
                    st.error("Failed to retrieve new item ID.")
                    return

                item_id = int(item_df.iloc[0]["Item_ID"])

                insert_shared_sql = """
                INSERT INTO dbo.SHARED_ITEM (
                    Item_ID,
                    Property_ID,
                    Low_Stock_Threshold
                )
                VALUES (?, ?, ?)
                """
                execute_transaction(
                    insert_shared_sql,
                    [item_id, property_id, int(low_stock_threshold)],
                )

                st.success(f"Shared item '{item_name}' added successfully.")
                logger.info("Shared item added by tenant %s", tenant_id)
                st.rerun()

            except Exception as exc:
                st.error(f"Failed to add shared item: {exc}")
                logger.error("Shared item add failed for tenant %s: %s", tenant_id, exc)


def tab_add_personal_item(tenant_id: int):
    """Add Personal Item tab (two-step CREATE)."""
    st.subheader("Add Personal Item")

    with st.form("add_personal_item_form", clear_on_submit=True):
        item_name = st.text_input("Item Name")
        quantity = st.number_input("Quantity", min_value=0, max_value=10000, value=1, step=1)
        category = st.text_input("Category")
        storage_location = st.text_input("Storage Location")
        is_private = st.checkbox("Private Item (only you can access)", value=True)

        submitted = st.form_submit_button("Add Personal Item")

        if submitted:
            if not item_name.strip():
                st.error("Item Name is required.")
                return

            try:
                insert_inventory_sql = """
                INSERT INTO dbo.INVENTORY_ITEM (
                    Item_Name,
                    Total_Quantity,
                    Category,
                    Storage_Location
                )
                VALUES (?, ?, ?, ?)
                """
                execute_transaction(
                    insert_inventory_sql,
                    [item_name.strip(), int(quantity), category.strip() or None, storage_location.strip() or None],
                )

                item_lookup_sql = """
                SELECT TOP 1 Item_ID
                FROM dbo.INVENTORY_ITEM
                ORDER BY Item_ID DESC
                """
                item_df = run_query(item_lookup_sql)
                if item_df.empty:
                    st.error("Failed to retrieve new item ID.")
                    return

                item_id = int(item_df.iloc[0]["Item_ID"])

                insert_personal_sql = """
                INSERT INTO dbo.PERSONAL_ITEM (
                    Item_ID,
                    Tenant_ID,
                    Is_Private
                )
                VALUES (?, ?, ?)
                """
                execute_transaction(
                    insert_personal_sql,
                    [item_id, tenant_id, 1 if is_private else 0],
                )

                st.success(f"Personal item '{item_name}' added successfully.")
                logger.info("Personal item added by tenant %s", tenant_id)
                st.rerun()

            except Exception as exc:
                st.error(f"Failed to add personal item: {exc}")
                logger.error("Personal item add failed for tenant %s: %s", tenant_id, exc)


def main():
    """Inventory entrypoint."""
    check_tenant_authenticated()

    tenant_id = int(st.session_state.get("logged_in_user_id"))

    st.title("📦 Inventory")
    st.caption("Manage shared and personal items.")

    tab1, tab2, tab3 = st.tabs([
        "📋 All Items",
        "➕ Add Shared Item",
        "🔒 Add Personal Item",
    ])

    with tab1:
        tab_read_inventory()

    with tab2:
        tab_add_shared_item(tenant_id)

    with tab3:
        tab_add_personal_item(tenant_id)


if __name__ == "__main__":
    main()
