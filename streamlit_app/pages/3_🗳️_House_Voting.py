"""
🗳️ House Voting Page
Create proposals and cast votes on active house rules.
"""

import logging
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.auth import auth_gate
from utils.state import AppState
from utils.db import execute_transaction, run_query, get_roommate_ids

logger = logging.getLogger(__name__)

st.set_page_config(page_title="House Voting - CoHabitant", page_icon="🗳️", layout="wide")


def load_proposals(tenant_id: int) -> pd.DataFrame:
    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT p.Proposal_ID, p.Proposed_By_Tenant_ID,
        per.First_Name + ' ' + per.Last_Name AS Proposed_By,
        p.Description, p.Cost_Threshold, p.Status,
        ISNULL(dbo.fn_GetPendingVoteCount(p.Proposal_ID), 0) AS Pending_Votes,
        (SELECT COUNT(DISTINCT la.Tenant_ID) FROM dbo.LEASE_AGREEMENT la
         WHERE la.Property_ID = (SELECT TOP 1 la2.Property_ID FROM dbo.LEASE_AGREEMENT la2
             WHERE la2.Tenant_ID = p.Proposed_By_Tenant_ID AND CAST(GETDATE() AS DATE) BETWEEN la2.Start_Date AND la2.End_Date
             ORDER BY la2.End_Date DESC, la2.Lease_ID DESC)
         AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date) AS Total_Eligible_Voters
    FROM dbo.PROPOSAL p
    INNER JOIN dbo.TENANT t ON p.Proposed_By_Tenant_ID = t.Tenant_ID
    INNER JOIN dbo.PERSON per ON t.Tenant_ID = per.Person_ID
    WHERE p.Proposed_By_Tenant_ID IN ({placeholders}) AND p.Is_Active = 1
    ORDER BY p.Proposal_ID DESC
    """
    df = run_query(sql, roommate_ids)
    if not df.empty:
        df['Votes_Cast'] = df['Total_Eligible_Voters'] - df['Pending_Votes']
        df['Vote_Progress'] = df.apply(
            lambda row: f"{int(row['Votes_Cast'])}/{int(row['Total_Eligible_Voters'])}" if row['Total_Eligible_Voters'] > 0 else "0/0", axis=1)
    return df


def create_proposal_form(tenant_id: int):
    st.subheader("Create New House Rule")
    with st.form("proposal_create_form", clear_on_submit=True):
        description = st.text_area("Proposal Description", max_chars=255, placeholder="Example: Quiet hours after 11 PM on weekdays")
        cost_threshold = st.number_input("Cost Threshold ($)", min_value=0.0, max_value=50000.0, value=0.0, step=10.0, format="%.2f")
        submitted = st.form_submit_button("➕ Submit Proposal")
        if submitted:
            if not description.strip():
                st.error("Please provide a proposal description.")
                return
            try:
                execute_transaction("INSERT INTO dbo.PROPOSAL (Proposed_By_Tenant_ID, Description, Cost_Threshold, Status) VALUES (?, ?, ?, 'Active')",
                                    [tenant_id, description.strip(), cost_threshold])
                st.success("Proposal created successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create proposal: {exc}")
                logger.error("Proposal creation failed for tenant %s: %s", tenant_id, exc)


def cast_vote_form(tenant_id: int, active_df: pd.DataFrame):
    st.subheader("Cast Your Vote")
    if active_df.empty:
        st.info("No active proposals are available for voting.")
        return
    options = {f"#{int(row['Proposal_ID'])} | {row['Description']}": int(row["Proposal_ID"]) for _, row in active_df.iterrows()}
    with st.form("cast_vote_form", clear_on_submit=True):
        selected = st.selectbox("Active proposal", list(options.keys()))
        vote_choice = st.radio("Your vote", ["Yes", "No"], horizontal=True)
        submitted = st.form_submit_button("🗳️ Submit Vote")
        if submitted:
            proposal_id = options[selected]
            is_approved = 1 if vote_choice == "Yes" else 0
            vote_sql = "DECLARE @FinalStatus VARCHAR(20); EXEC dbo.usp_CastProposalVote ?, ?, ?, @FinalStatus OUTPUT; SELECT @FinalStatus;"
            try:
                execute_transaction(vote_sql, [proposal_id, tenant_id, is_approved])
                status_df = run_query("SELECT p.Status FROM dbo.PROPOSAL p WHERE p.Proposal_ID = ?", [proposal_id])
                final_status = status_df.iloc[0]["Status"] if not status_df.empty else "Unknown"
                st.success(f"Vote recorded for Proposal #{proposal_id}. Current status: {final_status}.")
                st.rerun()
            except Exception as exc:
                message = str(exc)
                if "UQ_Vote_Tenant_Proposal" in message or "duplicate" in message.lower():
                    st.warning("You have already voted on this proposal.")
                else:
                    st.error(f"Failed to cast vote: {exc}")
                logger.error("Vote cast failed for tenant %s on proposal %s: %s", tenant_id, proposal_id, exc)


def load_vote_breakdown(proposal_id: int) -> dict:
    sql = "SELECT SUM(CASE WHEN Approval_Status = 1 THEN 1 ELSE 0 END) AS Yes_Votes, SUM(CASE WHEN Approval_Status = 0 THEN 1 ELSE 0 END) AS No_Votes FROM dbo.VOTE WHERE Proposal_ID = ? AND Is_Active = 1"
    df = run_query(sql, [proposal_id])
    if df.empty:
        return {"Yes_Votes": 0, "No_Votes": 0}
    return df.iloc[0].to_dict()


def render_vote_breakdown(proposals_df: pd.DataFrame):
    st.subheader("🗳️ Vote Breakdown")
    completed_df = proposals_df[proposals_df["Status"].isin(["Approved", "Rejected"])]
    if completed_df.empty:
        st.info("No completed proposals yet.")
        return
    cols = st.columns(min(2, len(completed_df)))
    for idx, (_, proposal) in enumerate(completed_df.iterrows()):
        with cols[idx % 2]:
            breakdown = load_vote_breakdown(int(proposal["Proposal_ID"]))
            yes_votes = breakdown.get("Yes_Votes", 0) or 0
            no_votes = breakdown.get("No_Votes", 0) or 0
            if yes_votes + no_votes == 0:
                st.write(f"**#{int(proposal['Proposal_ID'])}** - No votes cast")
                continue
            fig = go.Figure(data=[go.Pie(labels=["Yes ✅", "No ❌"], values=[yes_votes, no_votes],
                                         marker=dict(colors=["#31a354", "#d62728"]), textinfo="label+value+percent")])
            fig.update_layout(title=f"#{int(proposal['Proposal_ID'])}: {proposal['Status']}", height=300, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)


def main():
    auth_gate("Tenant")
    state = AppState()
    tenant_id = state.tenant_id
    st.title("🗳️ House Voting")
    st.caption("Propose new rules and vote on active house decisions.")
    try:
        proposals_df = load_proposals(tenant_id)
    except Exception as exc:
        st.error(f"Failed to load proposals: {exc}")
        return
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Active", int((proposals_df["Status"] == "Active").sum()) if not proposals_df.empty else 0)
    with col2: st.metric("Approved", int((proposals_df["Status"] == "Approved").sum()) if not proposals_df.empty else 0)
    with col3: st.metric("Rejected", int((proposals_df["Status"] == "Rejected").sum()) if not proposals_df.empty else 0)
    st.markdown("### Proposal History")
    if not proposals_df.empty:
        display_df = proposals_df[['Proposal_ID', 'Proposed_By', 'Description', 'Status', 'Vote_Progress']].copy()
        display_df.columns = ['ID', 'Proposed By', 'Description', 'Status', 'Votes (Cast/Total)']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No proposals found.")
    tab1, tab2, tab3 = st.tabs(["➕ New Proposal", "🗳️ Vote", "📊 Results"])
    with tab1: create_proposal_form(tenant_id)
    with tab2:
        active_df = proposals_df[proposals_df["Status"] == "Active"].copy() if not proposals_df.empty else pd.DataFrame()
        cast_vote_form(tenant_id, active_df)
    with tab3:
        try: render_vote_breakdown(proposals_df)
        except Exception as exc: st.error(f"Failed to load vote breakdown: {exc}")


if __name__ == "__main__":
    main()
