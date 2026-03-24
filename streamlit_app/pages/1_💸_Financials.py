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
from datetime import date
from utils.db import (
    run_query,
    execute_transaction,
    get_roommate_ids
)

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
    
    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input(
                "Amount ($)",
                min_value=0.01,
                max_value=10000.00,
                step=0.01,
                format="%.2f"
            )
            description = st.text_input("Description (e.g., 'Groceries', 'Internet Bill')")
        
        with col2:
            split_policy = st.selectbox(
                "Split Policy",
                ["Equal", "Custom", "Consumption-Based"]
            )
            category = st.selectbox(
                "Expense Category",
                ["Groceries", "Utilities", "Rent", "Cleaning", "Other"]
            )
        
        notes = st.text_area("Additional Notes", max_chars=255)
        
        submitted = st.form_submit_button("💾 Create Expense")
        
        if submitted:
            if not description:
                st.error("❌ Please enter a description")
                return
            
            try:
                sql = """
                DECLARE @NewExpenseID INT;
                EXEC dbo.usp_CreateHouseholdExpense 
                    ?,
                    ?,
                    ?,
                    ?,
                    @NewExpenseID OUTPUT;
                SELECT @NewExpenseID AS NewExpenseID;
                """
                
                params = [
                    st.session_state.logged_in_tenant_id,
                    amount,
                    split_policy,
                    None,
                ]
                
                execute_transaction(sql, params)
                
                st.success(
                    f"✅ Expense created successfully!\n"
                    f"Amount: ${amount:.2f} split among all tenants"
                )
                logger.info(
                    f"Expense created by Tenant {st.session_state.logged_in_tenant_id}: ${amount}"
                )
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
                    sql_delete = """
                    DELETE FROM dbo.EXPENSE 
                                        WHERE Expense_ID = ?
                                            AND Paid_By_Tenant_ID = ?;
                    """
                    
                                        execute_transaction(sql_delete, [expense_id, st.session_state.logged_in_tenant_id])
                    
                    st.success(
                        f"✅ Expense {expense_id} deleted successfully.\n"
                        f"⚠️ Action logged by audit trigger for compliance."
                    )
                    logger.info(
                        f"Expense {expense_id} deleted by Tenant {st.session_state.logged_in_tenant_id}. Reason: {reason}"
                    )
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
