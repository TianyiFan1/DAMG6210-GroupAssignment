"""
📈 Analytics Page
Visualize utility spending trends across time and categories.
"""

import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.auth import auth_gate
from utils.db import run_query, get_tenant_property_id

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Analytics - CoHabitant", page_icon="📈", layout="wide")


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


def main():
    auth_gate("Tenant")
    tenant_id = int(st.session_state["logged_in_tenant_id"])
    st.title("📈 Analytics")
    st.caption("Interactive utility spending trends across your household.")
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
    with col1: st.metric("Total Utility Cost", f"${utility_df['Cost_Amount'].sum():,.2f}")
    with col2: st.metric("Avg Reading Cost", f"${utility_df['Cost_Amount'].mean():,.2f}")
    with col3: st.metric("Data Points", int(len(utility_df)))
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


if __name__ == "__main__":
    main()
