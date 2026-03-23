"""
📈 Analytics Page
Visualize utility spending trends across time and categories.
"""

import logging
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db import run_query

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


def load_utility_timeseries() -> pd.DataFrame:
    """Load utility timeseries data for charting and analytics."""
    sql = """
    SELECT *
    FROM dbo.vw_App_Utility_TimeSeries
    ORDER BY Reading_Date ASC
    """
    return run_query(sql)


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

    st.title("📈 Analytics")
    st.caption("Interactive utility spending trends across your household.")

    try:
        utility_df = load_utility_timeseries()
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
