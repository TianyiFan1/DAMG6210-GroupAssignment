"""
📦 Inventory
Tenant-only page for shared and personal item management.
"""

import logging
import pandas as pd
import streamlit as st

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import run_query, execute_transaction, get_tenant_property_id, get_roommate_ids

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Inventory - CoHabitant", page_icon="📦", layout="wide")


def get_tenant_properties(tenant_id: int) -> pd.DataFrame:
    sql = """
    SELECT DISTINCT p.Property_ID, p.Street_Address + ', ' + p.City AS Property_Name
    FROM dbo.PROPERTY p INNER JOIN dbo.LEASE_AGREEMENT la ON p.Property_ID = la.Property_ID
    WHERE la.Tenant_ID = ? AND la.Is_Active = 1 AND p.Is_Active = 1
      AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ORDER BY Property_Name
    """
    return run_query(sql, [tenant_id])


def load_inventory_items(tenant_id: int) -> pd.DataFrame:
    property_id = get_tenant_property_id(tenant_id)
    roommate_ids = get_roommate_ids(tenant_id)
    if property_id is None: return pd.DataFrame()
    if not roommate_ids: roommate_ids = [tenant_id]
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT ii.Item_ID, ii.Item_Name, ii.Total_Quantity, ii.Category, ii.Storage_Location,
        CASE WHEN si.Item_ID IS NOT NULL THEN 'Shared' WHEN pi.Item_ID IS NOT NULL THEN 'Personal' ELSE 'Unclassified' END AS Item_Type,
        CASE WHEN si.Item_ID IS NOT NULL THEN si.Low_Stock_Threshold ELSE NULL END AS Low_Stock_Threshold,
        CASE WHEN pi.Item_ID IS NOT NULL THEN pi.Is_Private ELSE NULL END AS Is_Private
    FROM dbo.INVENTORY_ITEM ii
    LEFT JOIN dbo.SHARED_ITEM si ON ii.Item_ID = si.Item_ID AND si.Is_Active = 1
    LEFT JOIN dbo.PERSONAL_ITEM pi ON ii.Item_ID = pi.Item_ID AND pi.Is_Active = 1
    WHERE ii.Is_Active = 1 AND (si.Property_ID = ? OR pi.Tenant_ID IN ({placeholders}))
    ORDER BY ii.Item_Name
    """
    return run_query(sql, [property_id] + roommate_ids)


def tab_read_inventory(tenant_id: int):
    st.subheader("Inventory Items")
    try:
        df = load_inventory_items(tenant_id)
        if df.empty: st.info("No inventory items found."); return
        low_stock_items = df[(df['Item_Type'] == 'Shared') & (df['Low_Stock_Threshold'].notna()) & (df['Total_Quantity'] <= df['Low_Stock_Threshold'])]
        if not low_stock_items.empty:
            st.warning(f"⚠️ {len(low_stock_items)} shared item(s) below stock threshold!")
            with st.expander("📦 Low Stock Items", expanded=True):
                st.dataframe(low_stock_items[['Item_Name', 'Total_Quantity', 'Low_Stock_Threshold', 'Storage_Location']], use_container_width=True, hide_index=True)
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception as exc:
        st.error(f"Failed to load inventory: {exc}")


def tab_add_shared_item(tenant_id: int):
    st.subheader("Add Shared Item")
    try: properties_df = get_tenant_properties(tenant_id)
    except Exception as exc: st.warning(f"Could not load properties: {exc}"); properties_df = pd.DataFrame()
    if properties_df.empty: st.info("You must have a lease to add shared items.")
    property_options = {f"#{int(row['Property_ID'])} | {row['Property_Name']}": int(row["Property_ID"]) for _, row in properties_df.iterrows()} if not properties_df.empty else {}
    with st.form("add_shared_item_form", clear_on_submit=True):
        item_name = st.text_input("Item Name"); quantity = st.number_input("Quantity", min_value=0, max_value=10000, value=1, step=1)
        category = st.text_input("Category"); storage_location = st.text_input("Storage Location")
        low_stock_threshold = st.number_input("Low Stock Threshold", min_value=0, value=1, step=1)
        property_id = None
        if property_options:
            selected_property = st.selectbox("Property", list(property_options.keys()))
            property_id = property_options[selected_property]
        else: st.warning("No property selected.")
        submitted = st.form_submit_button("Add Shared Item")
        if submitted:
            if not item_name.strip(): st.error("Item Name is required."); return
            if property_id is None: st.error("A property must be selected for shared items."); return
            try:
                insert_sql = "DECLARE @NewItemID INT; INSERT INTO dbo.INVENTORY_ITEM (Item_Name, Total_Quantity, Category, Storage_Location) VALUES (?, ?, ?, ?); SET @NewItemID = SCOPE_IDENTITY(); INSERT INTO dbo.SHARED_ITEM (Item_ID, Property_ID, Low_Stock_Threshold) VALUES (@NewItemID, ?, ?)"
                execute_transaction(insert_sql, [item_name.strip(), int(quantity), category.strip() or None, storage_location.strip() or None, property_id, int(low_stock_threshold)])
                st.success(f"Shared item '{item_name}' added successfully."); st.rerun()
            except Exception as exc:
                st.error(f"Failed to add shared item: {exc}")


def tab_add_personal_item(tenant_id: int):
    st.subheader("Add Personal Item")
    with st.form("add_personal_item_form", clear_on_submit=True):
        item_name = st.text_input("Item Name"); quantity = st.number_input("Quantity", min_value=0, max_value=10000, value=1, step=1)
        category = st.text_input("Category"); storage_location = st.text_input("Storage Location")
        is_private = st.checkbox("Private Item (only you can access)", value=True)
        submitted = st.form_submit_button("Add Personal Item")
        if submitted:
            if not item_name.strip(): st.error("Item Name is required."); return
            try:
                insert_sql = "DECLARE @NewItemID INT; INSERT INTO dbo.INVENTORY_ITEM (Item_Name, Total_Quantity, Category, Storage_Location) VALUES (?, ?, ?, ?); SET @NewItemID = SCOPE_IDENTITY(); INSERT INTO dbo.PERSONAL_ITEM (Item_ID, Tenant_ID, Is_Private) VALUES (@NewItemID, ?, ?)"
                execute_transaction(insert_sql, [item_name.strip(), int(quantity), category.strip() or None, storage_location.strip() or None, tenant_id, 1 if is_private else 0])
                st.success(f"Personal item '{item_name}' added successfully."); st.rerun()
            except Exception as exc:
                st.error(f"Failed to add personal item: {exc}")


def tab_update_quantity(tenant_id: int):
    st.subheader("Update Item Quantity")
    st.caption("Quickly adjust stock when items are used or restocked.")
    try:
        df = load_inventory_items(tenant_id)
        if df.empty: st.info("No inventory items to update."); return
        shared_items = df[df['Item_Type'] == 'Shared'].copy()
        if shared_items.empty: st.info("No shared items found. Add some first!"); return
        item_options = {f"{row['Item_Name']} (Current: {int(row['Total_Quantity'])} units)": int(row['Item_ID']) for _, row in shared_items.iterrows()}
        with st.form("update_quantity_form"):
            selected_label = st.selectbox("Select Item to Update", list(item_options.keys()), help="Choose an item to adjust quantity")
            item_id = item_options[selected_label]
            current_item = shared_items[shared_items['Item_ID'] == item_id].iloc[0]
            current_qty = int(current_item['Total_Quantity'])
            new_quantity = st.number_input("New Quantity", min_value=0, max_value=10000, value=current_qty, step=1)
            qty_change = new_quantity - current_qty
            if qty_change != 0:
                change_label = f"➕ +{qty_change}" if qty_change > 0 else f"➖ {qty_change}"
                st.caption(f"Change: {change_label}")
            submitted = st.form_submit_button("💾 Update Quantity")
            if submitted:
                try:
                    execute_transaction("UPDATE dbo.INVENTORY_ITEM SET Total_Quantity = ? WHERE Item_ID = ?", [new_quantity, item_id])
                    st.success(f"✅ Updated {current_item['Item_Name']} to {new_quantity} units"); st.rerun()
                except Exception as exc:
                    st.error(f"Failed to update quantity: {exc}")
    except Exception as exc:
        st.error(f"Failed to load inventory for update: {exc}")


def main():
    auth_gate("Tenant")
    state = AppState()
    tenant_id = state.user_id

    st.title("📦 Inventory")
    st.caption("Manage shared and personal items.")
    tab1, tab2, tab3, tab4 = st.tabs(["📋 All Items", "➕ Add Shared Item", "🔒 Add Personal Item", "📝 Update Quantity"])
    with tab1: tab_read_inventory(tenant_id)
    with tab2: tab_add_shared_item(tenant_id)
    with tab3: tab_add_personal_item(tenant_id)
    with tab4: tab_update_quantity(tenant_id)


if __name__ == "__main__":
    main()
