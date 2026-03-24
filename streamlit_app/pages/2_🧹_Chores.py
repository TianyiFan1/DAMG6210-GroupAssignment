"""
🧹 Chores Page
Track household chore performance and complete pending assignments.
"""

import logging
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db import execute_transaction, run_query, get_roommate_ids

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Chores - CoHabitant",
    page_icon="🧹",
    layout="wide"
)


def check_authenticated():
    """Stop page render if no tenant is logged in."""
    if st.session_state.get("logged_in_tenant_id") is None:
        st.warning("⚠️ Please log in from the main page first.")
        st.stop()


def load_chore_leaderboard(tenant_id: int) -> pd.DataFrame:
    """Load leaderboard data from the chore leaderboard view."""
    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame()

    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT *
    FROM dbo.vw_App_Chore_Leaderboard
    WHERE Tenant_ID IN ({placeholders})
    ORDER BY Tenant_Responsibility_Score DESC
    """
    return run_query(sql, roommate_ids)


def load_my_pending_chores(tenant_id: int) -> pd.DataFrame:
    """Load pending chores assigned to the current tenant."""
    sql = """
    SELECT
        ca.Assignment_ID,
        cd.Task_Name,
        cd.Description,
        cd.Difficulty_Weight,
        cd.Frequency,
        ca.Due_Date,
        ca.Status
    FROM dbo.CHORE_ASSIGNMENT ca
    INNER JOIN dbo.CHORE_DEFINITION cd ON ca.Chore_ID = cd.Chore_ID
    WHERE ca.Assigned_Tenant_ID = ?
      AND ca.Status = 'Pending'
    ORDER BY ca.Due_Date ASC, ca.Assignment_ID ASC
    """
    return run_query(sql, [tenant_id])


def render_leaderboard(leaderboard_df: pd.DataFrame):
    """Render leaderboard table and score chart."""
    if leaderboard_df.empty:
        st.info("No leaderboard data is available yet.")
        return

    chart_df = leaderboard_df.copy()
    chart_df["First_Name"] = chart_df["First_Name"].astype(str)

    fig = px.bar(
        chart_df,
        x="First_Name",
        y="Tenant_Responsibility_Score",
        color="Tenant_Responsibility_Score",
        color_continuous_scale="Tealgrn",
        text="Tenant_Responsibility_Score",
        title="House Responsibility Leaderboard"
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_title="Tenant",
        yaxis_title="Responsibility Score",
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=60, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        leaderboard_df,
        use_container_width=True,
        hide_index=True
    )


def render_mark_complete_form(my_chores_df: pd.DataFrame):
    """Render form for marking a pending chore as complete."""
    st.subheader("Mark Chore Complete")

    if my_chores_df.empty:
        st.success("🎉 You have no pending chores.")
        return

    choices = {
        (
            f"#{int(row['Assignment_ID'])} | {row['Task_Name']} "
            f"(Due: {row['Due_Date']})"
        ): int(row["Assignment_ID"])
        for _, row in my_chores_df.iterrows()
    }

    with st.form("complete_chore_form", clear_on_submit=True):
        selected_label = st.selectbox("Select a pending chore", list(choices.keys()))
        submitted = st.form_submit_button("✅ Mark as Completed")

        if submitted:
            assignment_id = choices[selected_label]
            update_sql = """
            UPDATE dbo.CHORE_ASSIGNMENT
            SET Status = 'Completed',
                Completion_Date = GETDATE()
                        WHERE Assignment_ID = ?
                            AND Assigned_Tenant_ID = ?
            """
            try:
                                execute_transaction(update_sql, [assignment_id, st.session_state.get("logged_in_tenant_id")])
                st.success(f"Assignment {assignment_id} marked as completed.")
                logger.info("Chore assignment %s completed by tenant %s", assignment_id, st.session_state.get("logged_in_tenant_id"))
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to update chore status: {exc}")
                logger.error("Failed to complete chore assignment %s: %s", assignment_id, exc)


def main():
    """Chores page entrypoint."""
    check_authenticated()

    tenant_id = int(st.session_state["logged_in_tenant_id"])

    st.title("🧹 Chores")
    st.caption("Track household contributions and close out pending tasks.")

    tab1, tab2 = st.tabs(["🏆 Leaderboard", "📋 My Pending Chores"])

    with tab1:
        try:
            leaderboard_df = load_chore_leaderboard(tenant_id)
            render_leaderboard(leaderboard_df)
        except Exception as exc:
            st.error(f"Failed to load chore leaderboard: {exc}")
            logger.error("Leaderboard load error: %s", exc)

    with tab2:
        try:
            my_chores_df = load_my_pending_chores(tenant_id)
            st.dataframe(my_chores_df, use_container_width=True, hide_index=True)
            render_mark_complete_form(my_chores_df)
        except Exception as exc:
            st.error(f"Failed to load your chores: {exc}")
            logger.error("My chores load error for tenant %s: %s", tenant_id, exc)


if __name__ == "__main__":
    main()
