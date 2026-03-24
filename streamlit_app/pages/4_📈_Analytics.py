"""
📈 Analytics Page
Visualize utility spending trends across time and categories.
"""

import logging
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db import run_query, get_tenant_property_id

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Analytics - CoHabitant",
    page_icon="📈",
    layout="wide"
)


def check_authenticated():
    """Stop page render if no tenant is logged in."""
    if st.session_state.get("logged_in_tenant_id") is None:
        st.warning("⚠️ Please log in from the main page first.")
        st.stop()


def load_utility_timeseries(tenant_id: int) -> pd.DataFrame:
    """Load utility timeseries data for charting and analytics."""
    property_id = get_tenant_property_id(tenant_id)
    if property_id is None:
        return pd.DataFrame(columns=["Reading_Date", "Utility_Category", "Provider_Name", "Cost_Amount", "Street_Address"])

    sql = """
    SELECT
        ur.Reading_Date,
        ut.Type_Name AS Utility_Category,
        ur.Provider_Name,
        ur.Meter_Value AS Cost_Amount,
        p.Street_Address
    FROM dbo.UTILITY_READING ur
    INNER JOIN dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
    INNER JOIN dbo.PROPERTY p ON ur.Property_ID = p.Property_ID
    WHERE ur.Property_ID = ?
    ORDER BY Reading_Date ASC
    """
    return run_query(sql, [property_id])


def render_multiline_chart(df: pd.DataFrame):
    """Render utility cost trend as a multi-line chart by category."""
    if df.empty:
        st.info("No utility readings are available yet.")
        return

    plot_df = df.copy()
    plot_df["Reading_Date"] = pd.to_datetime(plot_df["Reading_Date"])

    fig = px.line(
        plot_df,
        x="Reading_Date",
        y="Cost_Amount",
        color="Utility_Category",
        markers=True,
        title="Utility Cost Trends by Category",
        template="plotly_white"
    )
    fig.update_layout(
        xaxis_title="Reading Date",
        yaxis_title="Cost Amount ($)",
        legend_title="Utility Category",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=60, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)


def main():
    """Analytics page entrypoint."""
    check_authenticated()
    tenant_id = int(st.session_state["logged_in_tenant_id"])

    st.title("📈 Analytics")
    st.caption("Interactive utility spending trends across your household.")

    try:
        utility_df = load_utility_timeseries(tenant_id)
    except Exception as exc:
        st.error(f"Failed to load utility analytics data: {exc}")
        logger.error("Utility analytics load error: %s", exc)
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
    selected_categories = st.multiselect(
        "Filter utility categories",
        options=categories,
        default=categories
    )

    filtered_df = utility_df[utility_df["Utility_Category"].isin(selected_categories)].copy()

    render_multiline_chart(filtered_df)

    st.markdown("### Utility Time-Series Data")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
