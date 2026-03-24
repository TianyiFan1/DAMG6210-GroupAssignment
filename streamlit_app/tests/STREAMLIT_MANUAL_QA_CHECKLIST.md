# Streamlit Manual QA Checklist

Run this after `pytest` is green to catch UI/runtime issues quickly.

## Setup
1. Activate venv from `streamlit_app`.
2. Confirm `.streamlit/secrets.toml` points to your intended test database.
3. Start app: `streamlit run app.py`.

## Tenant Login Flow
1. Log in as a tenant with an active lease.
2. Verify dashboard loads without Python traceback.
3. Confirm cards/metrics render and show only roommate/property-scoped data.

## Financials Flow
1. Open Financials page.
2. Create one expense with `Equal` split.
3. Create one expense with `Custom` split.
4. Verify success toast appears and page reruns cleanly.
5. Verify balances change as expected in table/chart.
6. Delete an expense you created and verify it is removed.

## Chores Flow
1. Open Chores page.
2. Verify leaderboard renders.
3. Mark one assigned chore as complete.
4. Confirm status updates and page reruns without errors.

## Voting Flow
1. Open House Voting page.
2. Verify proposals list loads for current property only.
3. Cast a vote and confirm no errors.

## Inventory Flow
1. Open Inventory page.
2. Add an item and verify it appears in list.
3. Update/consume item and verify quantity updates.

## House Hub Flow
1. Open House Hub page.
2. Verify lease details tab loads.
3. Verify roommate contact list appears and excludes the current user.

## Security Regression Checks
1. Confirm tenant cannot delete/modify another tenant's records through UI actions.
2. Confirm no page exposes data from other properties.
3. Confirm no secrets are logged in terminal output.

## Pass Criteria
1. No uncaught exceptions/tracebacks during all flows.
2. All actions either succeed or show a friendly error message.
3. Data changes are immediately reflected after rerun.
