"""
🗳️ House Voting Page
Create proposals and cast votes on active house rules.
"""

import logging
import pandas as pd
import streamlit as st

from utils.db import execute_transaction, run_query, get_roommate_ids

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="House Voting - CoHabitant",
    page_icon="🗳️",
    layout="wide"
)


def check_authenticated():
    """Stop page render if no tenant is logged in."""
    if st.session_state.get("logged_in_tenant_id") is None:
        st.warning("⚠️ Please log in from the main page first.")
        st.stop()


def load_proposals(tenant_id: int) -> pd.DataFrame:
    """Load all proposals with proposer names, newest first."""
    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame()

    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT
        p.Proposal_ID,
        p.Proposed_By_Tenant_ID,
        per.First_Name + ' ' + per.Last_Name AS Proposed_By,
        p.Description,
        p.Cost_Threshold,
        p.Status
    FROM dbo.PROPOSAL p
    INNER JOIN dbo.TENANT t ON p.Proposed_By_Tenant_ID = t.Tenant_ID
    INNER JOIN dbo.PERSON per ON t.Tenant_ID = per.Person_ID
    WHERE p.Proposed_By_Tenant_ID IN ({placeholders})
    ORDER BY p.Proposal_ID DESC
    """
    return run_query(sql, roommate_ids)


def create_proposal_form(tenant_id: int):
    """Create a new active proposal."""
    st.subheader("Create New House Rule")

    with st.form("proposal_create_form", clear_on_submit=True):
        description = st.text_area(
            "Proposal Description",
            max_chars=255,
            placeholder="Example: Quiet hours after 11 PM on weekdays"
        )
        cost_threshold = st.number_input(
            "Cost Threshold ($)",
            min_value=0.0,
            max_value=50000.0,
            value=0.0,
            step=10.0,
            format="%.2f"
        )

        submitted = st.form_submit_button("➕ Submit Proposal")

        if submitted:
            if not description.strip():
                st.error("Please provide a proposal description.")
                return

            insert_sql = """
            INSERT INTO dbo.PROPOSAL (
                Proposed_By_Tenant_ID,
                Description,
                Cost_Threshold,
                Status
            )
            VALUES (?, ?, ?, 'Active')
            """
            try:
                execute_transaction(insert_sql, [tenant_id, description.strip(), cost_threshold])
                st.success("Proposal created successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create proposal: {exc}")
                logger.error("Proposal creation failed for tenant %s: %s", tenant_id, exc)


def cast_vote_form(tenant_id: int, active_df: pd.DataFrame):
    """Cast yes/no vote on active proposals using stored procedure."""
    st.subheader("Cast Your Vote")

    if active_df.empty:
        st.info("No active proposals are available for voting.")
        return

    options = {
        f"#{int(row['Proposal_ID'])} | {row['Description']}": int(row["Proposal_ID"])
        for _, row in active_df.iterrows()
    }

    with st.form("cast_vote_form", clear_on_submit=True):
        selected = st.selectbox("Active proposal", list(options.keys()))
        vote_choice = st.radio("Your vote", ["Yes", "No"], horizontal=True)
        submitted = st.form_submit_button("🗳️ Submit Vote")

        if submitted:
            proposal_id = options[selected]
            is_approved = 1 if vote_choice == "Yes" else 0

            vote_sql = """
            DECLARE @FinalStatus VARCHAR(20);
            EXEC dbo.usp_CastProposalVote ?, ?, ?, @FinalStatus OUTPUT;
            SELECT @FinalStatus;
            """

            try:
                execute_transaction(vote_sql, [proposal_id, tenant_id, is_approved])

                status_sql = """
                SELECT p.Status
                FROM dbo.PROPOSAL p
                WHERE p.Proposal_ID = ?
                  AND p.Proposed_By_Tenant_ID IN (
                      SELECT la.Tenant_ID
                      FROM dbo.LEASE_AGREEMENT la
                      WHERE la.Property_ID = (
                          SELECT TOP 1 la2.Property_ID
                          FROM dbo.LEASE_AGREEMENT la2
                          WHERE la2.Tenant_ID = ?
                            AND CAST(GETDATE() AS DATE) BETWEEN la2.Start_Date AND la2.End_Date
                          ORDER BY la2.End_Date DESC, la2.Lease_ID DESC
                      )
                      AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
                  )
                """
                status_df = run_query(status_sql, [proposal_id, tenant_id])
                final_status = (
                    status_df.iloc[0]["Status"] if not status_df.empty else "Unknown"
                )

                st.success(
                    f"Vote recorded for Proposal #{proposal_id}. "
                    f"Current status: {final_status}."
                )
                st.rerun()
            except Exception as exc:
                message = str(exc)
                if "UQ_Vote_Tenant_Proposal" in message or "duplicate" in message.lower():
                    st.warning("You have already voted on this proposal.")
                else:
                    st.error(f"Failed to cast vote: {exc}")
                logger.error(
                    "Vote cast failed for tenant %s on proposal %s: %s",
                    tenant_id,
                    proposal_id,
                    exc
                )


def main():
    """Voting page entrypoint."""
    check_authenticated()

    tenant_id = int(st.session_state["logged_in_tenant_id"])

    st.title("🗳️ House Voting")
    st.caption("Propose new rules and vote on active house decisions.")

    try:
        proposals_df = load_proposals(tenant_id)
    except Exception as exc:
        st.error(f"Failed to load proposals: {exc}")
        logger.error("Proposal load error: %s", exc)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active", int((proposals_df["Status"] == "Active").sum()) if not proposals_df.empty else 0)
    with col2:
        st.metric("Approved", int((proposals_df["Status"] == "Approved").sum()) if not proposals_df.empty else 0)
    with col3:
        st.metric("Rejected", int((proposals_df["Status"] == "Rejected").sum()) if not proposals_df.empty else 0)

    st.markdown("### Proposal History")
    st.dataframe(proposals_df, use_container_width=True, hide_index=True)

    tab1, tab2 = st.tabs(["➕ New Proposal", "🗳️ Vote"])

    with tab1:
        create_proposal_form(tenant_id)

    with tab2:
        active_df = proposals_df[proposals_df["Status"] == "Active"].copy() if not proposals_df.empty else pd.DataFrame()
        cast_vote_form(tenant_id, active_df)


if __name__ == "__main__":
    main()
