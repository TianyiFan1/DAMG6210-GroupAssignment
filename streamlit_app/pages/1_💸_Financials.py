"""
💸 Financials Page
Handle all expense tracking, splitting, and payment operations.

Features:
- View active tenant balances and debts
- Create new shared expenses with auto-splitting
- Process peer-to-peer payments
- Delete/audit expense transactions
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import logging
import json
import io
from google import genai
from datetime import date
from PIL import Image
from utils.db import (
    run_query,
    execute_transaction,
    get_roommate_ids,
    get_tenant_name,
)
from utils.financial_logic import build_expense_transaction_sql_params

client = genai.Client(api_key=st.secrets["gemini"]["api_key"])

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Financials - CoHabitant",
    page_icon="💸",
    layout="wide"
)


def check_authenticated():
    """Verify user is logged in before showing page."""
    if st.session_state.get("logged_in_tenant_id") is None:
        st.warning("⚠️ Please log in from the main page first!")
        st.stop()


def parse_receipt_with_ai(image_bytes: bytes) -> dict:
    """Parse receipt image using Gemini and return normalized JSON fields."""
    prompt = "Analyze this store receipt. Return ONLY a valid JSON object with exactly these 6 keys: 'amount' (float, total cost), 'description' (string, Merchant name + brief summary like 'Target Shared Supplies'), 'category' (string, choose exactly one: 'Groceries', 'Utilities', 'Rent', 'Cleaning', or 'Other'), 'notes' (string, list the top 3 most expensive items on the receipt), 'split_policy' (string. Return 'Equal' if all items are shared household goods. Return 'Custom' if you detect personal items like alcohol, protein powder, or clothing), and 'date_incurred' (string, YYYY-MM-DD format, extract the date printed on the receipt). Do not use markdown blocks."
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Using the new 2.5-flash model and the new SDK syntax
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, prompt]
        )
        
        # Clean the response just in case Gemini includes ```json ``` markdown
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean_text)
        
        return parsed if isinstance(parsed, dict) else {}
        
    except Exception as exc:
        logger.error("AI receipt parsing failed: %s", exc)
        return {}


def load_active_balances(tenant_id: int) -> pd.DataFrame:
    """
    Load tenant balances using the vw_App_Ledger_ActiveBalances view.
    
    Returns:
        pd.DataFrame: Tenant balances and debt information
    """
    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame(
            columns=["Tenant_ID", "Full_Name", "Current_Net_Balance", "Total_Pending_Debts", "Lifetime_Paid"]
        )

    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT 
        Tenant_ID,
        Full_Name,
        Current_Net_Balance,
        Total_Pending_Debts,
        Lifetime_Paid
    FROM dbo.vw_App_Ledger_ActiveBalances
    WHERE Tenant_ID IN ({placeholders})
    ORDER BY Current_Net_Balance DESC
    """
    return run_query(sql, roommate_ids)


def render_balance_chart(df: pd.DataFrame):
    """
    Render an interactive Plotly chart showing current balances.
    
    Args:
        df: DataFrame from load_active_balances()
    """
    # Create figure
    fig = go.Figure()
    
    # Add balance bars
    fig.add_trace(go.Bar(
        x=df['Full_Name'],
        y=df['Current_Net_Balance'],
        name='Current Balance',
        marker=dict(
            color=df['Current_Net_Balance'],
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Balance ($)")
        ),
        text=df['Current_Net_Balance'].apply(lambda x: f"${x:.2f}"),
        textposition='auto'
    ))
    
    # Update layout
    fig.update_layout(
        title="💰 Current Tenant Balances",
        xaxis_title="Tenant",
        yaxis_title="Balance ($)",
        hovermode='x unified',
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_balance_table(df: pd.DataFrame):
    """
    Render a detailed balance table with formatting.
    
    Args:
        df: DataFrame from load_active_balances()
    """
    # Format currency columns
    display_df = df.copy()
    display_df['Current_Net_Balance'] = display_df['Current_Net_Balance'].apply(
        lambda x: f"💰 ${x:.2f}" if x >= 0 else f"💸 ${x:.2f}"
    )
    display_df['Total_Pending_Debts'] = display_df['Total_Pending_Debts'].apply(
        lambda x: f"${x:.2f}"
    )
    display_df['Lifetime_Paid'] = display_df['Lifetime_Paid'].apply(
        lambda x: f"${x:.2f}"
    )
    
    # Rename columns for display
    display_df.columns = ['Tenant ID', 'Name', 'Current Balance', 'Pending Debts', 'Lifetime Paid']
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


def expense_form():
    """
    Render form to create a new household expense.
    Calls: EXEC dbo.usp_CreateHouseholdExpense
    """
    st.subheader("➕ Add New House Expense")

    if "ai_amount" not in st.session_state:
        st.session_state.ai_amount = 0.01
    if "ai_description" not in st.session_state:
        st.session_state.ai_description = ""
    if "ai_split_policy" not in st.session_state:
        st.session_state.ai_split_policy = "Equal"
    if "ai_category" not in st.session_state:
        st.session_state.ai_category = "Other"
    if "ai_notes" not in st.session_state:
        st.session_state.ai_notes = ""
    if "ai_date_incurred" not in st.session_state:
        st.session_state.ai_date_incurred = date.today()

    uploaded_file = st.file_uploader("📸 Scan Receipt (Optional)", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        if st.button("🤖 Auto-Fill with AI"):
            parsed = parse_receipt_with_ai(uploaded_file.getvalue())

            st.session_state.ai_amount = float(parsed.get("amount", st.session_state.ai_amount or 0.01) or 0.01)
            st.session_state.ai_description = str(parsed.get("description", st.session_state.ai_description) or "")

            split_val = str(parsed.get("split_policy", st.session_state.ai_split_policy) or "Equal")
            st.session_state.ai_split_policy = split_val if split_val in ["Equal", "Custom", "Consumption-Based"] else "Equal"

            cat_val = str(parsed.get("category", st.session_state.ai_category) or "Other")
            st.session_state.ai_category = cat_val if cat_val in ["Groceries", "Utilities", "Rent", "Cleaning", "Other"] else "Other"

            st.session_state.ai_notes = str(parsed.get("notes", st.session_state.ai_notes) or "")

            parsed_date = parsed.get("date_incurred", None)
            try:
                st.session_state.ai_date_incurred = date.fromisoformat(str(parsed_date)) if parsed_date else st.session_state.ai_date_incurred
            except Exception:
                st.session_state.ai_date_incurred = date.today()

            st.rerun()
    
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input(
                "Amount ($)",
                min_value=0.01,
                max_value=10000.00,
                step=0.01,
                format="%.2f",
                value=float(st.session_state.ai_amount)
            )
            description = st.text_input(
                "Description (e.g., 'Groceries', 'Internet Bill')",
                value=st.session_state.ai_description,
            )
        
        with col2:
            split_options = ["Equal", "Custom", "Consumption-Based"]
            split_index = split_options.index(st.session_state.ai_split_policy) if st.session_state.ai_split_policy in split_options else 0
            split_policy = st.selectbox(
                "Split Policy",
                split_options,
                index=split_index,
            )
            category_options = ["Groceries", "Utilities", "Rent", "Cleaning", "Other"]
            category_index = category_options.index(st.session_state.ai_category) if st.session_state.ai_category in category_options else 4
            category = st.selectbox(
                "Expense Category",
                category_options,
                index=category_index,
            )

        col3, col4 = st.columns(2)
        with col3:
            date_incurred = st.date_input("Date Incurred", value=st.session_state.ai_date_incurred)
        with col4:
            notes = st.text_area("Additional Notes", max_chars=255, value=st.session_state.ai_notes)

        payer_tenant_id = int(st.session_state.logged_in_tenant_id)
        roommates = get_roommate_ids(payer_tenant_id)
        if not roommates:
            roommates = [payer_tenant_id]

        roommate_owed_amounts = {}
        if split_policy == "Custom":
            st.markdown("### Custom Split Allocation")
            for rid in roommates:
                if rid == payer_tenant_id:
                    continue
                roommate_name = get_tenant_name(rid)
                owed_key = f"custom_owed_{rid}"
                roommate_owed_amounts[rid] = st.number_input(
                    f"Amount owed by {roommate_name}",
                    min_value=0.0,
                    max_value=float(amount),
                    value=float(st.session_state.get(owed_key, 0.0)),
                    step=0.01,
                    format="%.2f",
                    key=owed_key,
                )

            custom_total = sum(roommate_owed_amounts.values())
            st.caption(f"Total assigned to roommates: ${custom_total:.2f}")
            st.caption(f"Payer share (remainder): ${float(amount) - custom_total:.2f}")
        
        submitted = st.form_submit_button("💾 Create Expense")
        
        if submitted:
            if not description:
                st.error("❌ Please enter a description")
                return
            
            try:
                if split_policy == "Custom" and not roommate_owed_amounts and len(roommates) > 1:
                    st.error("Please assign custom owed amounts for your roommates.")
                    return

                final_sql, params, _ = build_expense_transaction_sql_params(
                    payer_tenant_id=payer_tenant_id,
                    total_amount=float(amount),
                    date_incurred=date_incurred,
                    split_policy=split_policy,
                    description=description,
                    notes=notes,
                    roommates=roommates,
                    custom_owed_amounts=roommate_owed_amounts if split_policy == "Custom" else None,
                )
                execute_transaction(final_sql, params)

                st.session_state.ai_amount = 0.01
                st.session_state.ai_description = ""
                st.session_state.ai_split_policy = "Equal"
                st.session_state.ai_category = "Other"
                st.session_state.ai_notes = ""
                st.session_state.ai_date_incurred = date.today()
                
                st.success(
                    f"✅ Expense created successfully!\n"
                    f"Amount: ${amount:.2f} saved for {date_incurred}"
                )
                logger.info(
                    "Expense created by Tenant %s: amount=%s category=%s notes=%s",
                    st.session_state.logged_in_tenant_id,
                    amount,
                    category,
                    notes,
                )
                import time
                time.sleep(2.5)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Failed to create expense: {e}")
                logger.error(f"Expense creation failed: {e}")


def payment_form():
    """
    Render form to process a peer-to-peer payment.
    Calls: EXEC dbo.usp_ProcessTenantPayment
    """
    st.subheader("💳 Pay a Roommate")
    
    with st.form("payment_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input(
                "Payment Amount ($)",
                min_value=0.01,
                max_value=10000.00,
                step=0.01,
                format="%.2f"
            )
        
        with col2:
            payment_type = st.selectbox(
                "Payment Type",
                ["Expense Settlement", "Rent", "Utilities", "Other"]
            )
        
        notes = st.text_input("Payment Notes / Reference")
        payment_date = st.date_input("Payment Date", value=date.today())
        
        submitted = st.form_submit_button("✅ Process Payment")
        
        if submitted:
            if not notes:
                st.error("❌ Please enter payment notes")
                return
            
            try:
                sql = """
                DECLARE @NewBalance DECIMAL(10,2);
                EXEC dbo.usp_ProcessTenantPayment
                    ?,
                    ?,
                    ?,
                    @NewBalance OUTPUT;
                SELECT @NewBalance AS NewBalance;
                """
                
                params = [
                    st.session_state.logged_in_tenant_id,
                    amount,
                    notes
                ]
                
                execute_transaction(sql, params)
                
                st.success(
                    f"✅ Payment processed successfully!\n"
                    f"Amount: ${amount:.2f}"
                )
                logger.info(
                    f"Payment of ${amount} processed by Tenant {st.session_state.logged_in_tenant_id}"
                )
                st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Failed to process payment: {e}")
                logger.error(f"Payment processing failed: {e}")


def delete_expense_form():
    """
    Render form to delete an expense (audited by trigger).
    Calls: DELETE FROM dbo.EXPENSE WHERE Expense_ID = ?
    The trg_AuditFinancialChanges trigger will log the deletion.
    """
    st.subheader("🗑️ Delete Expense (Audited)")
    
    # Fetch recent expenses
    try:
        sql = """
        SELECT TOP 20
            e.Expense_ID,
            e.Total_Amount,
            e.Date_Incurred,
            e.Split_Policy,
            p.First_Name + ' ' + p.Last_Name AS Paid_By
        FROM dbo.EXPENSE e
        JOIN dbo.TENANT t ON e.Paid_By_Tenant_ID = t.Tenant_ID
        JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
        WHERE e.Paid_By_Tenant_ID = ?
        ORDER BY e.Date_Incurred DESC
        """
        expenses_df = run_query(sql, [st.session_state.logged_in_tenant_id])
        
        if expenses_df.empty:
            st.info("ℹ️ No expenses found that you created.")
            return
        
        with st.form("delete_expense_form"):
            expense_options = {
                f"${row['Total_Amount']:.2f} - {row['Date_Incurred']} ({row['Split_Policy']})": row['Expense_ID']
                for _, row in expenses_df.iterrows()
            }
            
            selected_expense = st.selectbox(
                "Select expense to delete:",
                options=list(expense_options.keys())
            )
            
            reason = st.text_area(
                "Reason for deletion:",
                max_chars=255,
                placeholder="e.g., 'Duplicate entry', 'Wrong amount', etc."
            )
            
            deleted = st.form_submit_button("🗑️ Delete Expense", type="secondary")
            
            if deleted:
                if not reason:
                    st.error("❌ Please provide a reason for deletion")
                    return
                
                expense_id = expense_options[selected_expense]
                
                try:
                    # UPDATED SQL: Check ownership, delete shares first, then delete the main expense
                    sql_delete = """
                    IF EXISTS (SELECT 1 FROM dbo.EXPENSE WHERE Expense_ID = ? AND Paid_By_Tenant_ID = ?)
                    BEGIN
                        DELETE FROM dbo.EXPENSE_SHARE WHERE Expense_ID = ?;
                        DELETE FROM dbo.EXPENSE WHERE Expense_ID = ?;
                    END
                    ELSE
                    BEGIN
                        THROW 51000, 'Unauthorized or Expense not found.', 1;
                    END
                    """
                    
                    # We pass the parameters to match the 4 question marks in the SQL above
                    execute_transaction(sql_delete, [
                        expense_id, 
                        st.session_state.logged_in_tenant_id,
                        expense_id,
                        expense_id
                    ])
                    
                    st.success(
                        f"✅ Expense {expense_id} deleted successfully.\n"
                        f"⚠️ Action logged by audit trigger for compliance."
                    )
                    
                    import time
                    time.sleep(2.5) 
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Failed to delete expense: {e}")
                    logger.error(f"Expense deletion failed: {e}")
    
    except Exception as e:
        st.error(f"❌ Failed to load expenses: {e}")
        logger.error(f"Failed to load expenses: {e}")


def main():
    """Main financials page."""
    check_authenticated()
    
    st.title("💸 Financials Dashboard")
    st.markdown(f"**Logged in as:** {st.session_state.logged_in_tenant_name}")
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["📊 Balances", "➕ Add Expense", "💳 Payments"])
    
    # TAB 1: Balances View
    with tab1:
        st.markdown("### Active Tenant Balances")
        try:
            balances_df = load_active_balances(int(st.session_state.logged_in_tenant_id))
            
            if balances_df.empty:
                st.warning("⚠️ No balance data available")
            else:
                render_balance_chart(balances_df)
                st.markdown("### Detailed Balance Table")
                render_balance_table(balances_df)
        
        except Exception as e:
            st.error(f"❌ Failed to load balances: {e}")
            logger.error(f"Failed to load active balances: {e}")
    
    # TAB 2: Create Expense
    with tab2:
        expense_form()
    
    # TAB 3: Payments & Deletions
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            payment_form()
        
        with col2:
            delete_expense_form()


if __name__ == "__main__":
    main()
