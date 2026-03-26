"""
📈 Analytics Page
Visualize utility spending trends across time and categories.

Phase 3 Upgrade:
  - Temporal Time Travel tab: uses FOR SYSTEM_TIME AS OF to let
    users/admins view what the house financial ledger looked like
    on any past date.
  - AppState migration (fixes raw st.session_state access).
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import run_query, get_tenant_property_id, get_roommate_ids

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Analytics - CoHabitant", page_icon="📈", layout="wide")


# ─────────────────────────────────────────────────────────
# Utility Analytics (existing)
# ─────────────────────────────────────────────────────────

def load_utility_timeseries(tenant_id: int) -> pd.DataFrame:
    property_id = get_tenant_property_id(tenant_id)
    if property_id is None:
        return pd.DataFrame(columns=["Reading_Date", "Utility_Category", "Provider_Name", "Cost_Amount", "Street_Address"])
    sql = """
    SELECT ur.Reading_Date, ut.Type_Name AS Utility_Category, ur.Provider_Name,
           ur.Meter_Value AS Cost_Amount, p.Street_Address
    FROM dbo.UTILITY_READING ur
    INNER JOIN dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
    INNER JOIN dbo.PROPERTY p ON ur.Property_ID = p.Property_ID
    WHERE ur.Property_ID = ? AND ur.Is_Active = 1
    ORDER BY Reading_Date ASC
    """
    return run_query(sql, [property_id])


def render_multiline_chart(df: pd.DataFrame):
    if df.empty:
        st.info("No utility readings are available yet.")
        return
    plot_df = df.copy()
    plot_df["Reading_Date"] = pd.to_datetime(plot_df["Reading_Date"])
    fig = px.line(plot_df, x="Reading_Date", y="Cost_Amount", color="Utility_Category",
                  markers=True, title="Utility Cost Trends by Category", template="plotly_white")
    fig.update_layout(xaxis_title="Reading Date", yaxis_title="Cost Amount ($)",
                      legend_title="Utility Category", hovermode="x unified", margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_category_breakdown(df: pd.DataFrame):
    if df.empty:
        return
    category_totals = df.groupby("Utility_Category")["Cost_Amount"].sum().reset_index().sort_values("Cost_Amount", ascending=False)
    fig = go.Figure(data=[go.Pie(labels=category_totals["Utility_Category"], values=category_totals["Cost_Amount"],
                                  textinfo="label+value+percent", marker=dict(line=dict(color="white", width=2)))])
    fig.update_layout(title="Spending Breakdown by Utility Category", height=400)
    st.plotly_chart(fig, use_container_width=True)


def render_month_over_month_comparison(df: pd.DataFrame):
    if df.empty:
        st.info("Not enough data for month-over-month comparison.")
        return
    df["Reading_Date"] = pd.to_datetime(df["Reading_Date"])
    df["Year_Month"] = df["Reading_Date"].dt.to_period("M")
    monthly_totals = df.groupby(["Year_Month", "Utility_Category"])["Cost_Amount"].sum().reset_index()
    if monthly_totals["Year_Month"].nunique() < 2:
        st.info("Need at least 2 months of data for comparison.")
        return
    months = sorted(monthly_totals["Year_Month"].unique())[-2:]
    st.markdown("#### 📊 Month-over-Month Comparison")
    col1, col2 = st.columns(2)
    comparison_data = []
    current_month = monthly_totals[monthly_totals["Year_Month"] == months[-1]]
    previous_month = monthly_totals[monthly_totals["Year_Month"] == months[-2]]
    all_categories = set(current_month["Utility_Category"]) | set(previous_month["Utility_Category"])
    for category in sorted(all_categories):
        curr = current_month[current_month["Utility_Category"] == category]["Cost_Amount"].sum()
        prev = previous_month[previous_month["Utility_Category"] == category]["Cost_Amount"].sum()
        change = curr - prev
        pct_change = (change / prev * 100) if prev > 0 else 0
        status = "📈" if change > 0 else "📉" if change < 0 else "→"
        comparison_data.append({"Category": category, f"{months[-2]}": f"${prev:.2f}", f"{months[-1]}": f"${curr:.2f}",
                                "Change": f"{status} ${abs(change):.2f}", "% Change": f"{pct_change:+.1f}%"})
    with col1:
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
    with col2:
        comparison_totals = monthly_totals.groupby("Year_Month")["Cost_Amount"].sum()
        fig = go.Figure(data=[go.Bar(x=[str(m) for m in comparison_totals.index[-2:]],
                                      y=comparison_totals.values[-2:],
                                      text=[f"${v:.0f}" for v in comparison_totals.values[-2:]],
                                      textposition="auto", marker=dict(color=["#FFA500", "#FF6B6B"]))])
        fig.update_layout(title="Total Spending Comparison", xaxis_title="Month", yaxis_title="Total Cost ($)", showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────
# Temporal Time Travel (Phase 3)
# ─────────────────────────────────────────────────────────

def _load_temporal_expenses(as_of_dt: str, roommate_ids: list[int]) -> pd.DataFrame:
    """Load expenses as they existed at a specific point in time."""
    if not roommate_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT
        e.Expense_ID,
        e.Paid_By_Tenant_ID,
        pay_p.First_Name + ' ' + pay_p.Last_Name AS Paid_By,
        e.Total_Amount,
        e.Date_Incurred,
        e.Split_Policy,
        e.Is_Active
    FROM dbo.EXPENSE FOR SYSTEM_TIME AS OF ? e
    INNER JOIN dbo.PERSON pay_p ON pay_p.Person_ID = e.Paid_By_Tenant_ID
    WHERE e.Paid_By_Tenant_ID IN ({placeholders})
    ORDER BY e.Date_Incurred DESC, e.Expense_ID DESC
    """
    return run_query(sql, [as_of_dt] + roommate_ids)


def _load_temporal_expense_shares(as_of_dt: str, roommate_ids: list[int]) -> pd.DataFrame:
    """Load expense shares as they existed at a specific point in time."""
    if not roommate_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT
        es.Share_ID,
        es.Expense_ID,
        es.Owed_By_Tenant_ID,
        owed_p.First_Name + ' ' + owed_p.Last_Name AS Owed_By,
        es.Owed_Amount,
        es.Status,
        es.Is_Active
    FROM dbo.EXPENSE_SHARE FOR SYSTEM_TIME AS OF ? es
    INNER JOIN dbo.PERSON owed_p ON owed_p.Person_ID = es.Owed_By_Tenant_ID
    WHERE es.Owed_By_Tenant_ID IN ({placeholders})
    ORDER BY es.Share_ID DESC
    """
    return run_query(sql, [as_of_dt] + roommate_ids)


def _load_temporal_payments(as_of_dt: str, roommate_ids: list[int]) -> pd.DataFrame:
    """Load payments as they existed at a specific point in time."""
    if not roommate_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT
        pmt.Payment_ID,
        pmt.Payer_Tenant_ID,
        payer_p.First_Name + ' ' + payer_p.Last_Name AS Payer,
        pmt.Payee_Tenant_ID,
        payee_p.First_Name + ' ' + payee_p.Last_Name AS Payee,
        pmt.Amount,
        pmt.Payment_Date,
        pmt.Payment_Type,
        pmt.Note,
        pmt.Is_Active
    FROM dbo.PAYMENT FOR SYSTEM_TIME AS OF ? pmt
    INNER JOIN dbo.PERSON payer_p ON payer_p.Person_ID = pmt.Payer_Tenant_ID
    INNER JOIN dbo.PERSON payee_p ON payee_p.Person_ID = pmt.Payee_Tenant_ID
    WHERE pmt.Payer_Tenant_ID IN ({placeholders})
       OR pmt.Payee_Tenant_ID IN ({placeholders})
    ORDER BY pmt.Payment_Date DESC, pmt.Payment_ID DESC
    """
    return run_query(sql, [as_of_dt] + roommate_ids + roommate_ids)


def render_time_travel_tab(tenant_id: int):
    """Render temporal time-travel interface using SQL Server system-versioned tables.

    Users pick a past date and see the exact state of EXPENSE, EXPENSE_SHARE,
    and PAYMENT tables as they existed at that point in time. This uses SQL
    Server's built-in ``FOR SYSTEM_TIME AS OF`` clause — no application-level
    history tracking is needed.
    """
    st.markdown("### 🕰️ Temporal Time Travel")
    st.caption(
        "View what the house financial ledger looked like on any past date. "
        "This uses SQL Server Temporal Tables — the database automatically "
        "preserves the full history of every financial record."
    )

    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        st.info("No active lease found. Join a house to use time-travel analytics.")
        return

    # ── Date picker ──
    col_date, col_time = st.columns([1, 1])
    with col_date:
        travel_date = st.date_input(
            "Select a date to view",
            value=date.today() - timedelta(days=1),
            max_value=date.today(),
            help="Pick any past date to see the financial state as of end-of-day.",
        )
    with col_time:
        travel_time = st.time_input(
            "Time (optional, defaults to 23:59:59)",
            value=datetime.strptime("23:59:59", "%H:%M:%S").time(),
            help="For sub-day precision, adjust the time.",
        )

    # Combine date + time into a full datetime string for SQL Server
    travel_datetime = datetime.combine(travel_date, travel_time)
    as_of_str = travel_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    if st.button("🔍 Query Ledger at This Point in Time"):
        st.markdown(f"**Showing ledger state as of:** `{travel_datetime.strftime('%B %d, %Y at %I:%M:%S %p')}`")
        st.divider()

        # ── Expenses ──
        with st.spinner("Querying historical expenses..."):
            try:
                expenses_df = _load_temporal_expenses(as_of_str, roommate_ids)
            except Exception as exc:
                st.error(f"Failed to query temporal expenses: {exc}")
                logger.error("Temporal EXPENSE query failed: %s", exc)
                expenses_df = pd.DataFrame()

        st.markdown("#### 💸 Expenses")
        if expenses_df.empty:
            st.info("No expense records existed at this point in time.")
        else:
            active_expenses = expenses_df[expenses_df["Is_Active"] == True]  # noqa: E712
            deleted_expenses = expenses_df[expenses_df["Is_Active"] == False]  # noqa: E712

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Expenses", len(expenses_df))
            with col2:
                st.metric("Active", len(active_expenses))
            with col3:
                st.metric("Soft-Deleted (visible in history)", len(deleted_expenses))

            display_cols = ["Expense_ID", "Paid_By", "Total_Amount", "Date_Incurred", "Split_Policy", "Is_Active"]
            st.dataframe(
                expenses_df[[c for c in display_cols if c in expenses_df.columns]],
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        # ── Expense Shares ──
        with st.spinner("Querying historical expense shares..."):
            try:
                shares_df = _load_temporal_expense_shares(as_of_str, roommate_ids)
            except Exception as exc:
                st.error(f"Failed to query temporal expense shares: {exc}")
                logger.error("Temporal EXPENSE_SHARE query failed: %s", exc)
                shares_df = pd.DataFrame()

        st.markdown("#### 📋 Expense Shares")
        if shares_df.empty:
            st.info("No expense share records existed at this point in time.")
        else:
            pending_count = len(shares_df[shares_df["Status"] == "Pending"]) if "Status" in shares_df.columns else 0
            paid_count = len(shares_df[shares_df["Status"] == "Paid"]) if "Status" in shares_df.columns else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Shares", len(shares_df))
            with col2:
                st.metric("Pending", pending_count)
            with col3:
                st.metric("Paid", paid_count)

            display_cols = ["Share_ID", "Expense_ID", "Owed_By", "Owed_Amount", "Status", "Is_Active"]
            st.dataframe(
                shares_df[[c for c in display_cols if c in shares_df.columns]],
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        # ── Payments ──
        with st.spinner("Querying historical payments..."):
            try:
                payments_df = _load_temporal_payments(as_of_str, roommate_ids)
            except Exception as exc:
                st.error(f"Failed to query temporal payments: {exc}")
                logger.error("Temporal PAYMENT query failed: %s", exc)
                payments_df = pd.DataFrame()

        st.markdown("#### 💳 Payments & Settlements")
        if payments_df.empty:
            st.info("No payment records existed at this point in time.")
        else:
            total_amount = payments_df["Amount"].sum() if "Amount" in payments_df.columns else 0
            settlement_count = len(payments_df[payments_df["Payment_Type"] == "Settlement"]) if "Payment_Type" in payments_df.columns else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Payment Records", len(payments_df))
            with col2:
                st.metric("Total Amount Transacted", f"${total_amount:,.2f}")
            with col3:
                st.metric("Settlements", settlement_count)

            display_cols = ["Payment_ID", "Payer", "Payee", "Amount", "Payment_Date", "Payment_Type", "Note", "Is_Active"]
            st.dataframe(
                payments_df[[c for c in display_cols if c in payments_df.columns]],
                use_container_width=True,
                hide_index=True,
            )

        # ── Summary callout ──
        st.divider()
        st.success(
            f"🕰️ **Time-travel snapshot complete.** "
            f"The data above reflects the exact state of all financial tables at "
            f"`{travel_datetime.strftime('%Y-%m-%d %H:%M:%S')}` using SQL Server Temporal Tables "
            f"(`FOR SYSTEM_TIME AS OF`)."
        )


# ─────────────────────────────────────────────────────────
# Main Page Entry Point
# ─────────────────────────────────────────────────────────

def main():
    auth_gate("Tenant")
    state = AppState()
    tenant_id = state.tenant_id

    st.title("📈 Analytics")
    st.caption("Interactive utility spending trends and temporal ledger history.")

    tab_utility, tab_time_travel = st.tabs([
        "📊 Utility Analytics", "🕰️ Time Travel"
    ])

    with tab_utility:
        try:
            utility_df = load_utility_timeseries(tenant_id)
        except Exception as exc:
            st.error(f"Failed to load utility analytics data: {exc}")
            return
        if utility_df.empty:
            st.info("No analytics data found.")
            return
        utility_df["Reading_Date"] = pd.to_datetime(utility_df["Reading_Date"])
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Utility Cost", f"${utility_df['Cost_Amount'].sum():,.2f}")
        with col2:
            st.metric("Avg Reading Cost", f"${utility_df['Cost_Amount'].mean():,.2f}")
        with col3:
            st.metric("Data Points", int(len(utility_df)))
        categories = sorted(utility_df["Utility_Category"].dropna().unique().tolist())
        selected_categories = st.multiselect("Filter utility categories", options=categories, default=categories)
        filtered_df = utility_df[utility_df["Utility_Category"].isin(selected_categories)].copy()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📊 Trend Over Time")
            render_multiline_chart(filtered_df)
        with col2:
            st.markdown("#### 🥧 Category Breakdown")
            render_category_breakdown(filtered_df)
        render_month_over_month_comparison(utility_df)
        st.markdown("### Utility Time-Series Data")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    with tab_time_travel:
        render_time_travel_tab(tenant_id)


if __name__ == "__main__":
    main()
