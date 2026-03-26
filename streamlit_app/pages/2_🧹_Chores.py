"""
🧹 Chores Page
Track household chore performance and complete pending assignments.
"""

import logging
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import execute_transaction, run_query, get_roommate_ids, get_tenant_name

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Chores - CoHabitant", page_icon="🧹", layout="wide")


def load_chore_leaderboard(tenant_id: int) -> pd.DataFrame:
    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"SELECT * FROM dbo.vw_App_Chore_Leaderboard WHERE Tenant_ID IN ({placeholders}) ORDER BY Tenant_Responsibility_Score DESC"
    return run_query(sql, roommate_ids)


def load_my_pending_chores(tenant_id: int) -> pd.DataFrame:
    sql = """
    SELECT ca.Assignment_ID, cd.Task_Name, cd.Description, cd.Difficulty_Weight,
           cd.Frequency, ca.Due_Date, ca.Status
    FROM dbo.CHORE_ASSIGNMENT ca
    INNER JOIN dbo.CHORE_DEFINITION cd ON ca.Chore_ID = cd.Chore_ID
    WHERE ca.Assigned_Tenant_ID = ? AND ca.Status = 'Pending' AND ca.Is_Active = 1
    ORDER BY ca.Due_Date ASC, ca.Assignment_ID ASC
    """
    return run_query(sql, [tenant_id])


def load_my_completed_chores(tenant_id: int) -> pd.DataFrame:
    sql = """
    SELECT ca.Assignment_ID, cd.Task_Name, cd.Difficulty_Weight, ca.Due_Date,
           ca.Completion_Date, DATEDIFF(DAY, ca.Due_Date, ca.Completion_Date) AS Days_Late, ca.Status
    FROM dbo.CHORE_ASSIGNMENT ca
    INNER JOIN dbo.CHORE_DEFINITION cd ON ca.Chore_ID = cd.Chore_ID
    WHERE ca.Assigned_Tenant_ID = ? AND ca.Status = 'Completed' AND ca.Is_Active = 1
      AND ca.Completion_Date >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
    ORDER BY ca.Completion_Date DESC
    """
    return run_query(sql, [tenant_id])


def load_my_chore_stats(tenant_id: int) -> dict:
    sql = """
    SELECT
        COUNT(CASE WHEN Status = 'Pending' THEN 1 END) AS Pending_Count,
        COUNT(CASE WHEN Status = 'Completed' THEN 1 END) AS Completed_Count,
        COUNT(CASE WHEN Status = 'Pending' AND Due_Date < CAST(GETDATE() AS DATE) THEN 1 END) AS Overdue_Count
    FROM dbo.CHORE_ASSIGNMENT
    WHERE Assigned_Tenant_ID = ? AND Is_Active = 1
    """
    df = run_query(sql, [tenant_id])
    if df.empty:
        return {"Pending_Count": 0, "Completed_Count": 0, "Overdue_Count": 0}
    return df.iloc[0].to_dict()


def render_leaderboard(leaderboard_df: pd.DataFrame):
    if leaderboard_df.empty:
        st.info("No leaderboard data is available yet.")
        return
    chart_df = leaderboard_df.copy()
    chart_df["First_Name"] = chart_df["First_Name"].astype(str)
    fig = px.bar(chart_df, x="First_Name", y="Tenant_Responsibility_Score",
                 color="Tenant_Responsibility_Score", color_continuous_scale="Tealgrn",
                 text="Tenant_Responsibility_Score", title="House Responsibility Leaderboard")
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Tenant", yaxis_title="Responsibility Score",
                      coloraxis_showscale=False, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(leaderboard_df, use_container_width=True, hide_index=True)


def render_mark_complete_form(my_chores_df: pd.DataFrame, tenant_id: int):
    st.subheader("Mark Chore Complete")
    st.caption("Select a pending assignment and submit to mark it complete.")
    if my_chores_df.empty:
        st.success("🎉 You have no pending chores.")
        return
    choices = {
        f"#{int(row['Assignment_ID'])} | {row['Task_Name']} (Due: {row['Due_Date']})": int(row["Assignment_ID"])
        for _, row in my_chores_df.iterrows()
    }
    with st.form("complete_chore_form", clear_on_submit=True):
        selected_label = st.selectbox("Pending Chore", list(choices.keys()), help="Choose one assignment from your pending list.")
        submitted = st.form_submit_button("✅ Mark as Completed")
        if submitted:
            assignment_id = choices[selected_label]
            update_sql = """
            UPDATE dbo.CHORE_ASSIGNMENT SET Status = 'Completed', Completion_Date = GETDATE()
            WHERE Assignment_ID = ? AND Assigned_Tenant_ID = ?
            """
            try:
                execute_transaction(update_sql, [assignment_id, tenant_id])
                st.success(f"Assignment {assignment_id} marked as completed.")
                logger.info("Chore assignment %s completed by tenant %s", assignment_id, tenant_id)
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to update chore status: {exc}")
                logger.error("Failed to complete chore assignment %s: %s", assignment_id, exc)


def render_assign_chore_form(tenant_id: int):
    st.subheader("Assign Chore to Roommate")
    st.caption("Create or reassign a chore to a roommate.")
    try:
        roommate_ids = get_roommate_ids(tenant_id)
        if not roommate_ids or len(roommate_ids) < 2:
            st.info("You need roommates to assign chores to.")
            return
        other_roommates = [rid for rid in roommate_ids if rid != tenant_id]
        if not other_roommates:
            st.info("No other roommates available to assign to.")
            return
        with st.form("assign_chore_form", clear_on_submit=True):
            chore_sql = "SELECT Chore_ID, Task_Name, Frequency FROM dbo.CHORE_DEFINITION WHERE Is_Active = 1 ORDER BY Task_Name"
            chores_df = run_query(chore_sql)
            if chores_df.empty:
                st.warning("No chores defined yet. Create some first in House Hub!")
                return
            chore_options = {int(row['Chore_ID']): f"{row['Task_Name']} ({row['Frequency']})" for _, row in chores_df.iterrows()}
            col1, col2 = st.columns(2)
            with col1:
                selected_chore_label = st.selectbox("Select Chore", options=list(chore_options.values()), help="Pick a chore to assign")
                selected_chore_id = [k for k, v in chore_options.items() if v == selected_chore_label][0]
            with col2:
                assignee_id = st.selectbox("Assign To", options=other_roommates, format_func=lambda rid: get_tenant_name(rid), help="Choose which roommate to assign this to")
            due_date = st.date_input("Due Date", value=date.today())
            submitted = st.form_submit_button("➕ Assign Chore")
            if submitted:
                try:
                    insert_sql = "INSERT INTO dbo.CHORE_ASSIGNMENT (Chore_ID, Assigned_Tenant_ID, Due_Date, Status) VALUES (?, ?, ?, 'Pending')"
                    execute_transaction(insert_sql, [selected_chore_id, assignee_id, due_date])
                    st.success(f"✅ Assigned {selected_chore_label} to {get_tenant_name(assignee_id)} due {due_date}")
                    logger.info("Chore assigned by tenant %s to tenant %s", tenant_id, assignee_id)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to assign chore: {exc}")
                    logger.error("Chore assignment failed: %s", exc)
    except Exception as exc:
        st.error(f"Failed to load assignment form: {exc}")
        logger.error("Assignment form load failed: %s", exc)


def main():
    auth_gate("Tenant")
    state = AppState()
    tenant_id = state.tenant_id

    st.title("🧹 Chores")
    st.caption("Track household contributions and close out pending tasks.")
    try:
        stats = load_my_chore_stats(tenant_id)
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("📋 Pending", int(stats.get("Pending_Count", 0)))
        with col2: st.metric("✅ Completed (30d)", int(stats.get("Completed_Count", 0)))
        with col3:
            if int(stats.get("Overdue_Count", 0)) > 0: st.metric("⚠️ Overdue", int(stats.get("Overdue_Count", 0)))
            else: st.metric("✨ On Time", "All caught up!")
    except Exception as exc:
        logger.error("Failed to load chore stats: %s", exc)
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 Leaderboard", "📋 My Pending Chores", "✅ Completed (30d)", "➕ Assign to Roommate"])
    with tab1:
        try:
            render_leaderboard(load_chore_leaderboard(tenant_id))
        except Exception as exc:
            st.error(f"Failed to load chore leaderboard: {exc}")
    with tab2:
        try:
            my_chores_df = load_my_pending_chores(tenant_id)
            st.dataframe(my_chores_df, use_container_width=True, hide_index=True)
            render_mark_complete_form(my_chores_df, tenant_id)
        except Exception as exc:
            st.error(f"Failed to load your chores: {exc}")
    with tab3:
        try:
            completed_df = load_my_completed_chores(tenant_id)
            if completed_df.empty: st.info("No completed chores in the last 30 days.")
            else: st.dataframe(completed_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Failed to load completed chores: {exc}")
    with tab4:
        render_assign_chore_form(tenant_id)


if __name__ == "__main__":
    main()
