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
import time
from datetime import date

from google import genai
from PIL import Image

from utils.db import execute_transaction, get_roommate_ids, get_tenant_name, run_query
from utils.financial_logic import build_expense_transaction_sql_params

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Financials - CoHabitant",
    page_icon="💸",
    layout="wide",
)


def check_authenticated():
    """Verify user is logged in before showing page."""
    if st.session_state.get("logged_in_tenant_id") is None:
        st.warning("⚠️ Please log in from the main page first!")
        st.stop()


def _get_gemini_client():
    """Lazy init Gemini client; keeps module import safe if secrets are absent."""
    if "gemini" not in st.secrets or "api_key" not in st.secrets["gemini"]:
        raise RuntimeError("Gemini API key is missing in Streamlit secrets.")
    return genai.Client(api_key=st.secrets["gemini"]["api_key"])


def _call_gemini_with_backoff(img: Image.Image, prompt: str, max_attempts: int = 3) -> str:
    """Call Gemini with small exponential backoff for transient failures."""
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            client = _get_gemini_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[img, prompt],
            )
            return response.text
        except Exception as exc:
            last_exc = exc
            logger.warning("Gemini attempt %s/%s failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"Gemini call failed after {max_attempts} attempts: {last_exc}")


def parse_receipt_with_ai(image_bytes: bytes) -> dict:
    """Parse receipt image using Gemini and return normalized JSON fields."""
    prompt = "Analyze this store receipt. Return ONLY a valid JSON object with exactly these 6 keys: 'amount' (float, total cost), 'description' (string, Merchant name + brief summary like 'Target Shared Supplies'), 'category' (string, choose exactly one: 'Groceries', 'Utilities', 'Rent', 'Cleaning', or 'Other'), 'notes' (string, list the top 3 most expensive items on the receipt), 'split_policy' (string. Return 'Equal' if all items are shared household goods. Return 'Custom' if you detect personal items like alcohol, protein powder, or clothing), and 'date_incurred' (string, YYYY-MM-DD format, extract the date printed on the receipt). Do not use markdown blocks."
    try:
        img = Image.open(io.BytesIO(image_bytes))
        response_text = _call_gemini_with_backoff(img, prompt)
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
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
    
    st.plotly_chart(fig, width="stretch")


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
        width="stretch",
        hide_index=True
    )


def expense_form():
    """
    Render form to create a new household expense.
    Uses explicit transactional SQL assembly for expense/share/balance updates.
    """
    st.subheader("➕ Add New House Expense")
    st.caption("Create a shared expense, then review updated balances in the Balances tab.")

    if st.session_state.get("expense_form_reset_flag", False):
        st.session_state.expense_amount_input = 0.01
        st.session_state.expense_description_input = ""
        st.session_state.expense_split_policy_input = "Equal"
        st.session_state.expense_category_input = "Other"
        st.session_state.expense_notes_input = ""
        st.session_state.expense_date_input = date.today()
        st.session_state.custom_split_participants = []
        st.session_state.expense_form_reset_flag = False

    if "expense_amount_input" not in st.session_state:
        st.session_state.expense_amount_input = 0.01
    if "expense_description_input" not in st.session_state:
        st.session_state.expense_description_input = ""
    if "expense_split_policy_input" not in st.session_state:
        st.session_state.expense_split_policy_input = "Equal"
    if "expense_category_input" not in st.session_state:
        st.session_state.expense_category_input = "Other"
    if "expense_notes_input" not in st.session_state:
        st.session_state.expense_notes_input = ""
    if "expense_date_input" not in st.session_state:
        st.session_state.expense_date_input = date.today()

    uploaded_file = st.file_uploader(
        "📸 Scan Receipt (Optional)",
        type=["png", "jpg", "jpeg"],
        help="Upload a receipt image to auto-fill amount, description, category, split policy, and date.",
    )
    if uploaded_file is not None:
        if st.button("🤖 Auto-Fill with AI"):
            parsed = parse_receipt_with_ai(uploaded_file.getvalue())

            st.session_state.expense_amount_input = float(
                parsed.get("amount", st.session_state.expense_amount_input or 0.01) or 0.01
            )
            st.session_state.expense_description_input = str(
                parsed.get("description", st.session_state.expense_description_input) or ""
            )

            split_val = str(parsed.get("split_policy", st.session_state.expense_split_policy_input) or "Equal")
            st.session_state.expense_split_policy_input = (
                split_val if split_val in ["Equal", "Custom", "Consumption-Based"] else "Equal"
            )

            cat_val = str(parsed.get("category", st.session_state.expense_category_input) or "Other")
            st.session_state.expense_category_input = (
                cat_val if cat_val in ["Groceries", "Utilities", "Rent", "Cleaning", "Other"] else "Other"
            )

            st.session_state.expense_notes_input = str(parsed.get("notes", st.session_state.expense_notes_input) or "")

            parsed_date = parsed.get("date_incurred", None)
            try:
                st.session_state.expense_date_input = (
                    date.fromisoformat(str(parsed_date)) if parsed_date else st.session_state.expense_date_input
                )
            except Exception:
                st.session_state.expense_date_input = date.today()

            st.rerun()
    
    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Amount ($)",
            min_value=0.01,
            max_value=10000.00,
            step=0.01,
            format="%.2f",
            key="expense_amount_input",
        )
        st.text_input(
            "Description (e.g., 'Groceries', 'Internet Bill')",
            key="expense_description_input",
        )

    with col2:
        split_options = ["Equal", "Custom", "Consumption-Based"]
        st.selectbox(
            "Split Policy",
            split_options,
            key="expense_split_policy_input",
        )
        category_options = ["Groceries", "Utilities", "Rent", "Cleaning", "Other"]
        st.selectbox(
            "Expense Category",
            category_options,
            key="expense_category_input",
        )

    col3, col4 = st.columns(2)
    with col3:
        st.date_input("Date Incurred", key="expense_date_input")
    with col4:
        st.text_area("Additional Notes", max_chars=255, key="expense_notes_input")

    amount = float(st.session_state.expense_amount_input)
    description = str(st.session_state.expense_description_input)
    split_policy = str(st.session_state.expense_split_policy_input)
    category = str(st.session_state.expense_category_input)
    date_incurred = st.session_state.expense_date_input
    notes = str(st.session_state.expense_notes_input)

    payer_tenant_id = int(st.session_state.logged_in_tenant_id)
    roommates = get_roommate_ids(payer_tenant_id)
    if not roommates:
        roommates = [payer_tenant_id]

    if "custom_split_participants" not in st.session_state:
        st.session_state.custom_split_participants = list(roommates)
    else:
        st.session_state.custom_split_participants = [
            int(rid) for rid in st.session_state.custom_split_participants if int(rid) in roommates
        ]

    roommate_owed_amounts = {}
    selected_for_split = []

    if split_policy == "Custom":
        st.markdown("### 🔄 Splitwise-Style Custom Split")
        st.info("Pick exactly who consumed the expense. You can include or exclude yourself.")

        participant_names = {rid: f"{get_tenant_name(rid)}{' (You)' if rid == payer_tenant_id else ''}" for rid in roommates}

        selected_for_split = st.multiselect(
            "Who should this expense be split between?",
            options=roommates,
            format_func=lambda rid: participant_names.get(rid, f"Tenant {rid}"),
            key="custom_split_participants",
            help="Select participants. Example: if you paid for roommate B only, select B and unselect yourself.",
        )

        if not selected_for_split:
            st.warning("⚠️ Select at least one participant for a custom split.")
        else:
            split_roster = sorted(set(int(rid) for rid in selected_for_split))
            split_amount = float(amount) / len(split_roster)

            st.markdown("#### 📊 Split Preview")
            st.success(
                f"✅ Dividing **${amount:.2f}** equally among **{len(split_roster)} people** = **${split_amount:.2f}** each"
            )

            if payer_tenant_id not in split_roster:
                st.caption("You are excluded from this split. Others will owe the full expense amount.")
            elif len(split_roster) == 1:
                st.caption("Only you are selected, so this expense will not create amounts owed by roommates.")

            preview_data = []
            for rid in split_roster:
                preview_data.append(
                    {
                        "Participant": participant_names.get(rid, f"Tenant {rid}"),
                        "Share": f"${split_amount:.2f}",
                    }
                )

            st.dataframe(
                pd.DataFrame(preview_data),
                width="stretch",
                hide_index=True,
            )

            for rid in split_roster:
                if rid == payer_tenant_id:
                    continue
                roommate_owed_amounts[rid] = split_amount

    submitted = st.button("💾 Create Expense")

    if submitted:
        if not description.strip():
            st.error("❌ Please enter a description")
            return

        try:
            if split_policy == "Custom" and not selected_for_split:
                st.error("❌ Please select at least one participant in custom split.")
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

            st.session_state.expense_form_reset_flag = True

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
                    f"[{payment_type}] {notes} | Date: {payment_date}"
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
                    
                    time.sleep(2.5) 
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Failed to delete expense: {e}")
                    logger.error(f"Expense deletion failed: {e}")
    
    except Exception as e:
        st.error(f"❌ Failed to load expenses: {e}")
        logger.error(f"Failed to load expenses: {e}")


def load_expense_history(tenant_id: int) -> pd.DataFrame:
    """
    Load all expenses where the user is involved (paid or owes).
    """
    sql = """
    SELECT DISTINCT
        e.Expense_ID,
        e.Total_Amount,
        e.Date_Incurred,
        e.Split_Policy,
        p.First_Name + ' ' + p.Last_Name AS Paid_By,
        e.Paid_By_Tenant_ID,
        CASE WHEN e.Paid_By_Tenant_ID = ? THEN 'You paid' ELSE 'You owe' END AS Your_Role
    FROM dbo.EXPENSE e
    JOIN dbo.TENANT t ON e.Paid_By_Tenant_ID = t.Tenant_ID
    JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
    JOIN dbo.LEASE_AGREEMENT la ON t.Tenant_ID = la.Tenant_ID
    LEFT JOIN dbo.EXPENSE_SHARE es ON e.Expense_ID = es.Expense_ID AND es.Owed_By_Tenant_ID = ?
    WHERE (la.Property_ID = (SELECT Top 1 Property_ID FROM dbo.LEASE_AGREEMENT WHERE Tenant_ID = ? AND CAST(GETDATE() AS DATE) BETWEEN Start_Date AND End_Date))
    AND (e.Paid_By_Tenant_ID = ? OR es.Owed_By_Tenant_ID = ?)
    ORDER BY e.Date_Incurred DESC
    """
    
    return run_query(sql, [tenant_id, tenant_id, tenant_id, tenant_id, tenant_id])


def load_settlement_history(tenant_id: int) -> pd.DataFrame:
    """Load all settlements (payments) where the user is involved."""
    sql = """
    SELECT 
        pat.Payment_ID,
        pat.Amount,
        pat.Payment_Date,
        pay_p.First_Name + ' ' + pay_p.Last_Name AS Payer_Name,
        pat.Payer_Tenant_ID,
        recv_p.First_Name + ' ' + recv_p.Last_Name AS Payee_Name,
        pat.Payee_Tenant_ID,
        pat.Note,
        CASE 
            WHEN pat.Payer_Tenant_ID = ? THEN 'You paid'
            WHEN pat.Payee_Tenant_ID = ? THEN 'You received'
            ELSE 'Other'
        END AS Your_Role
    FROM dbo.PAYMENT pat
    JOIN dbo.PERSON pay_p ON pat.Payer_Tenant_ID = pay_p.Person_ID
    JOIN dbo.PERSON recv_p ON pat.Payee_Tenant_ID = recv_p.Person_ID
    JOIN dbo.LEASE_AGREEMENT la ON pat.Payer_Tenant_ID = la.Tenant_ID
    WHERE pat.Payment_Type = 'Settlement'
    AND la.Property_ID = (SELECT TOP 1 Property_ID FROM dbo.LEASE_AGREEMENT WHERE Tenant_ID = ? AND CAST(GETDATE() AS DATE) BETWEEN Start_Date AND End_Date)
    AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    AND (pat.Payer_Tenant_ID = ? OR pat.Payee_Tenant_ID = ?)
    ORDER BY pat.Payment_Date DESC
    """
    return run_query(sql, [tenant_id, tenant_id, tenant_id, tenant_id, tenant_id])


def render_expense_history(tenant_id: int):
    """Render expense history with expandable split details (Splitwise-style) + settlement records."""
    try:
        history_df = load_expense_history(tenant_id)
        settlement_df = load_settlement_history(tenant_id)
        
        if history_df.empty and settlement_df.empty:
            st.info("ℹ️ No expenses or settlements to display yet.")
            return
        
        st.markdown("### 📋 Your Financial History")
        
        for _, row in history_df.iterrows():
            expense_id = row['Expense_ID']
            total = row['Total_Amount']
            date_str = row['Date_Incurred']
            payer = row['Paid_By']
            payer_id = row['Paid_By_Tenant_ID']
            policy = row['Split_Policy']
            role = row['Your_Role']
            
            role_emoji = "💸" if role == "You paid" else "💰"
            
            with st.expander(
                f"{role_emoji} {date_str} | ${total:.2f} - {payer} ({policy})",
                expanded=False
            ):
                # Load detailed split breakdown
                sql_shares = """
                SELECT 
                    t.Tenant_ID,
                    p.First_Name + ' ' + p.Last_Name AS Tenant_Name,
                    es.Owed_Amount,
                    ISNULL(es.Status, 'Pending') AS Status
                FROM dbo.EXPENSE_SHARE es
                JOIN dbo.TENANT t ON es.Owed_By_Tenant_ID = t.Tenant_ID
                JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
                WHERE es.Expense_ID = ?
                ORDER BY es.Owed_Amount DESC
                """
                
                shares_df = run_query(sql_shares, [expense_id])
                
                # Calculate values for display
                if not shares_df.empty:
                    total_owed = shares_df['Owed_Amount'].sum()
                    payer_share = total - total_owed
                    num_participants = len(shares_df)
                else:
                    total_owed = 0
                    payer_share = total
                    num_participants = 1
                
                # Header info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Expense ID", expense_id)
                with col2:
                    st.metric("Total Amount", f"${total:.2f}")
                with col3:
                    st.metric("Split Type", policy)
                
                st.divider()
                
                # Split explanation
                if policy == "Equal":
                    if not shares_df.empty:
                        per_person = shares_df.iloc[0]['Owed_Amount']
                        st.info(f"💡 **Equal split among {num_participants + 1} people:** ${total:.2f} ÷ {num_participants + 1} = ${per_person:.2f} each")
                    else:
                        st.info(f"💡 **{payer} paid the full amount.** No participants owe.")
                else:
                    st.info(f"💡 **Custom split:** {payer} paid ${total:.2f}, split as shown below")
                
                st.markdown("#### 👥 Split Breakdown:")
                
                breakdown_display = []
                
                # Add payer info
                breakdown_display.append({
                    "Person": f"{payer} (Paid)",
                    "Amount": f"${payer_share:.2f}",
                    "Type": "💵 Paid"
                })
                
                # Add shares
                for _, share_row in shares_df.iterrows():
                    person_id = share_row['Tenant_ID']
                    person_name = share_row['Tenant_Name']
                    owes = share_row['Owed_Amount']
                    status = share_row['Status']
                    
                    if person_id == tenant_id:
                        person_label = f"{person_name} (You)"
                    else:
                        person_label = person_name
                    
                    status_emoji = "✅" if status == "Paid" else "⏳"
                    
                    breakdown_display.append({
                        "Person": person_label,
                        "Amount": f"${owes:.2f}",
                        "Type": f"{status_emoji} {status}"
                    })
                
                st.dataframe(
                    pd.DataFrame(breakdown_display),
                    width="stretch",
                    hide_index=True
                )
                
                st.divider()
                
                # Your personal summary
                if tenant_id == payer_id:
                    st.success(f"🎯 **You paid:** ${total:.2f} | **Others owe you:** ${total_owed:.2f}")
                else:
                    your_share = shares_df[shares_df['Tenant_ID'] == tenant_id]['Owed_Amount'].values
                    if your_share.size > 0:
                        st.warning(f"🎯 **You owe {payer}:** ${your_share[0]:.2f}")
                    else:
                        st.info(f"🎯 **This expense doesn't apply to you**")
        
        # Display SETTLEMENTS section
        if not settlement_df.empty:
            st.divider()
            st.markdown("### 💳 Settlement Payments")
            st.caption("Money exchanged to settle outstanding debts")
            
            for _, row in settlement_df.iterrows():
                payment_id = row['Payment_ID']
                amount = row['Amount']
                date_str = row['Payment_Date']
                payer = row['Payer_Name']
                payee = row['Payee_Name']
                notes = row['Note']
                role = row['Your_Role']
                
                role_emoji = "💸" if role == "You paid" else "💰"
                
                with st.expander(
                    f"{role_emoji} {date_str} | ${amount:.2f} - {payer} → {payee}",
                    expanded=False
                ):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**From:** {payer}")
                        st.markdown(f"**To:** {payee}")
                        if notes:
                            st.markdown(f"**Note:** {notes}")
                    with col2:
                        st.metric("Amount", f"${amount:.2f}")
                    
                    if role == "You paid":
                        st.success(f"✅ You paid {payee} ${amount:.2f} on {date_str}")
                    else:
                        st.success(f"✅ {payer} paid you ${amount:.2f} on {date_str}")
    
    except Exception as e:
        st.error(f"❌ Failed to load expense history: {e}")
        logger.error(f"Failed to load expense history: {e}")


def load_settle_up_data(tenant_id: int) -> pd.DataFrame:
    """
    Calculate pairwise balances between the current user and each roommate in the same property.
    """
    sql = """
    WITH MyProperty AS (
        SELECT TOP 1 la.Property_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Tenant_ID = ?
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ),
    MyHousemates AS (
        SELECT DISTINCT la.Tenant_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Property_ID = (SELECT Property_ID FROM MyProperty)
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
          AND la.Tenant_ID <> ?
    ),
    PendingYouOwe AS (
        SELECT
            e.Paid_By_Tenant_ID AS Roommate_ID,
            SUM(es.Owed_Amount) AS Amount
        FROM dbo.EXPENSE_SHARE es
        JOIN dbo.EXPENSE e ON e.Expense_ID = es.Expense_ID
        WHERE es.Owed_By_Tenant_ID = ?
          AND ISNULL(es.Status, 'Pending') = 'Pending'
          AND e.Paid_By_Tenant_ID IN (SELECT Tenant_ID FROM MyHousemates)
        GROUP BY e.Paid_By_Tenant_ID
    ),
    PendingTheyOwe AS (
        SELECT
            es.Owed_By_Tenant_ID AS Roommate_ID,
            SUM(es.Owed_Amount) AS Amount
        FROM dbo.EXPENSE_SHARE es
        JOIN dbo.EXPENSE e ON e.Expense_ID = es.Expense_ID
        WHERE e.Paid_By_Tenant_ID = ?
          AND ISNULL(es.Status, 'Pending') = 'Pending'
          AND es.Owed_By_Tenant_ID IN (SELECT Tenant_ID FROM MyHousemates)
        GROUP BY es.Owed_By_Tenant_ID
    ),
    SettledYouPaid AS (
        SELECT
            pay.Payee_Tenant_ID AS Roommate_ID,
            SUM(pay.Amount) AS Amount
        FROM dbo.PAYMENT pay
        WHERE pay.Payer_Tenant_ID = ?
          AND pay.Payment_Type = 'Settlement'
          AND pay.Payee_Tenant_ID IN (SELECT Tenant_ID FROM MyHousemates)
        GROUP BY pay.Payee_Tenant_ID
    ),
    SettledYouReceived AS (
        SELECT
            pay.Payer_Tenant_ID AS Roommate_ID,
            SUM(pay.Amount) AS Amount
        FROM dbo.PAYMENT pay
        WHERE pay.Payee_Tenant_ID = ?
          AND pay.Payment_Type = 'Settlement'
          AND pay.Payer_Tenant_ID IN (SELECT Tenant_ID FROM MyHousemates)
        GROUP BY pay.Payer_Tenant_ID
    )
    SELECT
        hm.Tenant_ID,
        p.First_Name + ' ' + p.Last_Name AS Name,
        CASE
            WHEN ISNULL(pyo.Amount, 0) > ISNULL(syp.Amount, 0)
                THEN ISNULL(pyo.Amount, 0) - ISNULL(syp.Amount, 0)
            ELSE 0
        END AS You_Owe_Them,
        CASE
            WHEN ISNULL(ptyo.Amount, 0) > ISNULL(syr.Amount, 0)
                THEN ISNULL(ptyo.Amount, 0) - ISNULL(syr.Amount, 0)
            ELSE 0
        END AS They_Owe_You,
        (
            CASE
                WHEN ISNULL(ptyo.Amount, 0) > ISNULL(syr.Amount, 0)
                    THEN ISNULL(ptyo.Amount, 0) - ISNULL(syr.Amount, 0)
                ELSE 0
            END
            -
            CASE
                WHEN ISNULL(pyo.Amount, 0) > ISNULL(syp.Amount, 0)
                    THEN ISNULL(pyo.Amount, 0) - ISNULL(syp.Amount, 0)
                ELSE 0
            END
        ) AS Net_Balance
    FROM MyHousemates hm
    JOIN dbo.PERSON p ON p.Person_ID = hm.Tenant_ID
    LEFT JOIN PendingYouOwe pyo ON pyo.Roommate_ID = hm.Tenant_ID
    LEFT JOIN PendingTheyOwe ptyo ON ptyo.Roommate_ID = hm.Tenant_ID
    LEFT JOIN SettledYouPaid syp ON syp.Roommate_ID = hm.Tenant_ID
    LEFT JOIN SettledYouReceived syr ON syr.Roommate_ID = hm.Tenant_ID
    WHERE
        (CASE
            WHEN ISNULL(pyo.Amount, 0) > ISNULL(syp.Amount, 0)
                THEN ISNULL(pyo.Amount, 0) - ISNULL(syp.Amount, 0)
            ELSE 0
        END) > 0
        OR
        (CASE
            WHEN ISNULL(ptyo.Amount, 0) > ISNULL(syr.Amount, 0)
                THEN ISNULL(ptyo.Amount, 0) - ISNULL(syr.Amount, 0)
            ELSE 0
        END) > 0
    ORDER BY Net_Balance DESC
    """

    return run_query(sql, [tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id])


def render_settle_up_view(tenant_id: int):
    """Render settle up interface showing who owes whom."""
    try:
        settle_df = load_settle_up_data(tenant_id)
        
        if settle_df.empty:
            st.success("✅ All settled! No outstanding debts.")
            return
        
        st.markdown("### 🤝 Settle Up - Who Owes Whom")
        st.caption("Positive balance = you are owed money | Negative balance = you owe money")
        
        # Display settle up table
        display_df = settle_df.copy()
        # After settlements: the remaining debt they owe
        display_df['You Owe Them'] = display_df['You_Owe_Them'].apply(lambda x: f"${x:.2f}")
        display_df['They Owe You'] = display_df['They_Owe_You'].apply(lambda x: f"${x:.2f}")
        display_df['Net Position'] = display_df['Net_Balance'].apply(
            lambda x: f"✅ +${x:.2f}" if x > 0 else f"⚠️ -${abs(x):.2f}" if x < 0 else "✓ Settled"
        )
        
        display_df = display_df[['Name', 'You Owe Them', 'They Owe You', 'Net Position']]
        display_df.columns = ['Roommate', 'You Owe Them', 'They Owe You', 'Net Position']
        
        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True
        )
        
        st.divider()
        st.markdown("#### 💳 Settle a Debt")
        
        # Get list of roommates
        roommates = get_roommate_ids(tenant_id)
        roommate_names = {rid: get_tenant_name(rid) for rid in roommates if rid != tenant_id}
        
        if roommate_names:
            with st.form("settle_up_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_roommate = st.selectbox(
                        "Mark as settled with:",
                        options=list(roommate_names.keys()),
                        format_func=lambda rid: roommate_names[rid]
                    )
                
                with col2:
                    settle_amount = st.number_input(
                        "Amount settled ($)",
                        min_value=0.01,
                        max_value=10000.00,
                        step=0.01
                    )
                
                notes = st.text_input(
                    "Settlement notes (e.g., 'Venmo'd on 3/24')",
                    max_chars=100
                )
                
                submitted = st.form_submit_button("✅ Record Settlement")
                
                if submitted:
                    try:
                        selected_row = settle_df[settle_df['Tenant_ID'] == selected_roommate]
                        if selected_row.empty:
                            st.error("❌ Could not find selected roommate balance.")
                            return

                        you_owe = float(selected_row.iloc[0]['You_Owe_Them'])
                        they_owe = float(selected_row.iloc[0]['They_Owe_You'])

                        if you_owe <= 0 and they_owe <= 0:
                            st.info("ℹ️ No outstanding amount to settle with this roommate.")
                            return

                        if they_owe >= you_owe:
                            payer_tenant_id = selected_roommate
                            payee_tenant_id = tenant_id
                            max_settle = they_owe
                            direction_text = f"{roommate_names[selected_roommate]} paid you"
                        else:
                            payer_tenant_id = tenant_id
                            payee_tenant_id = selected_roommate
                            max_settle = you_owe
                            direction_text = f"You paid {roommate_names[selected_roommate]}"

                        if settle_amount > max_settle:
                            st.error(f"❌ Settlement exceeds outstanding amount (${max_settle:.2f}).")
                            return

                        sql_payment = """
                        BEGIN TRANSACTION;
                        
                        -- Insert settlement record
                        INSERT INTO dbo.PAYMENT (Payer_Tenant_ID, Payee_Tenant_ID, Amount, Payment_Type, Payment_Date, Note)
                        VALUES (?, ?, ?, 'Settlement', CAST(GETDATE() AS DATE), ?);
                        
                        -- Payer debt decreases
                        UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) + ? WHERE Tenant_ID = ?;
                        
                        -- Payee receivable decreases
                        UPDATE dbo.TENANT SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) - ? WHERE Tenant_ID = ?;
                        
                        COMMIT TRANSACTION;
                        """
                        
                        execute_transaction(
                            sql_payment,
                            [
                                payer_tenant_id,
                                payee_tenant_id,
                                settle_amount,       # Amount
                                notes or "Settled debt",  # Note
                                settle_amount,       # Update payer balance (add)
                                payer_tenant_id,
                                settle_amount,       # Update payee balance (subtract)
                                payee_tenant_id
                            ]
                        )
                        
                        st.success(f"✅ Settlement recorded: ${settle_amount:.2f}. {direction_text}.")
                        time.sleep(2)
                        st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ Failed to record settlement: {e}")
                        logger.error(f"Settlement failed: {e}")
        else:
            st.info("ℹ️ No roommates to settle with.")
    
    except Exception as e:
        st.error(f"❌ Failed to load settle up view: {e}")
        logger.error(f"Failed to load settle up: {e}")


def main():
    """Main financials page."""
    check_authenticated()
    
    st.title("💸 Financials Dashboard")
    st.markdown(f"**Logged in as:** {st.session_state.logged_in_tenant_name}")
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Balances",
        "➕ Add Expense",
        "📋 History",
        "🤝 Settle Up",
        "💳 Payments"
    ])
    
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
    
    # TAB 3: Expense History with Details
    with tab3:
        render_expense_history(int(st.session_state.logged_in_tenant_id))
    
    # TAB 4: Settle Up
    with tab4:
        render_settle_up_view(int(st.session_state.logged_in_tenant_id))
    
    # TAB 5: Payments & Deletions
    with tab5:
        col1, col2 = st.columns(2)
        
        with col1:
            payment_form()
        
        with col2:
            delete_expense_form()


if __name__ == "__main__":
    main()
