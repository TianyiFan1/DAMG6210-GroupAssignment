# 🏠 CoHabitant — Architectural Hardening Delivery Summary

**Audit scope:** 10 technical debt items identified in pre-deployment review  
**Pre-completed by team:** Docker healthcheck (curl retained), connection string encryption  
**Delivered in this engagement:** 8 remaining items across 3 phases  

---

## Phase 1 — Financial State & Concurrency (Critical Fixes) ✅

### 1.1 Race Condition in Settlements → `usp_SettlePeerDebt`
**File:** `CoHabitant_psm_script.sql` (SP 4)

Settlement math moved entirely out of Streamlit and into a transactional stored procedure with:
- `UPDLOCK, ROWLOCK` hints on both TENANT rows to serialize concurrent settlements
- Real-time debt recomputation from `EXPENSE_SHARE` (not stale UI values)
- Net-direction detection (automatically determines who-pays-whom)
- Max-amount guard (`THROW 51014` if settlement > outstanding balance)
- Same-property validation (`THROW 51012`)
- Self-settlement guard (`THROW 51011`)
- `SYSTEM_ERROR_LOG` CATCH block

**Streamlit integration:** `1_💸_Financials.py` → `render_settle_up_view()` now calls:
```sql
EXEC dbo.usp_SettlePeerDebt @CallerTenantID=?, @CounterpartyTenantID=?, @SettleAmount=?, @Note=?
```
All SP-level THROW error codes (51012–51014) are surfaced as user-friendly `st.error()` messages.

### 1.2 Expense-Share Lifecycle → Pending → Paid
**File:** `CoHabitant_psm_script.sql` (SP 4, Step 3)

Inside `usp_SettlePeerDebt`, a FIFO cursor walks `EXPENSE_SHARE` rows ordered by `Share_ID ASC` and flips `Status` from `'Pending'` to `'Paid'` until the settlement amount is consumed. Partial shares are left as `'Pending'` (conservative — no partial status).

### 1.3 Centralized Soft-Delete → `usp_SoftDeleteExpense`
**File:** `CoHabitant_psm_script.sql` (SP 5)

The ad-hoc inline SQL from `delete_expense_form` was replaced with a proper SP:
- Ownership guard (only the payer can deactivate)
- Balance reversal for each debtor + payer
- `EXPENSE_SHARE.Is_Active = 0` flip
- `EXPENSE.Is_Active = 0` flip (captured by temporal history)
- `SYSTEM_ERROR_LOG` CATCH block

**Streamlit integration:** `1_💸_Financials.py` → `delete_expense_form()` now calls:
```sql
EXEC dbo.usp_SoftDeleteExpense @ExpenseID=?, @CallerTenantID=?
```

---

## Phase 2 — Streamlit Logic & Refactoring ✅

### 2.1 AppState Migration
**Files:** `app.py`, `1_💸_Financials.py`, `2_🧹_Chores.py`, `4_📈_Analytics.py`, `5_🏠_Landlord_Portal.py`, `6_👥_House_Hub.py`, `7_📦_Inventory.py`

All raw `st.session_state["logged_in_..."]` access replaced with `AppState()` from `utils/state.py`. The `auth_gate()` function from `utils/auth.py` enforces authentication and RBAC at the top of every page's `main()`.

**Before:** `tenant_id = int(st.session_state["logged_in_tenant_id"])`  
**After:** `state = AppState(); tenant_id = state.tenant_id`

### 2.2 Payment Flow Counterparty Fix
**File:** `1_💸_Financials.py` → `payment_form()`

The peer-to-peer payment form now requires selecting a Payee (counterparty) from the roommate list. Self-payment is no longer possible — the current user is excluded from the payee dropdown. `usp_ProcessTenantPayment` receives the explicit `@PayeeTenantID`.

### 2.3 Landlord Schema Fallback Removal
**File:** `5_🏠_Landlord_Portal.py`

All try/except fallback patterns that masked column mismatches were removed. SQL now strictly targets the actual schema columns (`State` not `State_Province`, `Zip_Code` not `Postal_Code`, etc.). Uses `AppState()` and `auth_gate("Landlord")`.

---

## Phase 3 — Advanced Capabilities ✅

### 3.1 Temporal Time Travel
**File:** `4_📈_Analytics.py` → new "🕰️ Time Travel" tab

Uses SQL Server's system-versioned temporal tables (`FOR SYSTEM_TIME AS OF`) to let users view the exact state of all financial records at any past point in time.

**UI components:**
- Date picker (defaults to yesterday) + time picker (defaults to 23:59:59)
- "Query Ledger at This Point in Time" button
- Three data sections: Expenses, Expense Shares, Payments
- Each section shows active vs soft-deleted counts, status breakdowns, and full data tables
- Summary callout confirming the temporal query was successful

**SQL queries (3 total):**
```sql
SELECT ... FROM dbo.EXPENSE        FOR SYSTEM_TIME AS OF ? ...
SELECT ... FROM dbo.EXPENSE_SHARE  FOR SYSTEM_TIME AS OF ? ...
SELECT ... FROM dbo.PAYMENT        FOR SYSTEM_TIME AS OF ? ...
```
All scoped to the logged-in user's property roommates.

### 3.2 Gemini Circuit Breaker
**File:** `1_💸_Financials.py` → `_call_gemini_with_backoff()`

The receipt-scanning AI call now has two layers of protection:

**Hard Timeout (per attempt):**
Each Gemini API call runs in a `daemon=True` thread with `thread.join(timeout=15.0)`. If the thread doesn't finish in 15 seconds, it's abandoned and the attempt counts as a failure.

**Circuit Breaker (`_GeminiCircuitBreaker` class):**

| State | Behavior |
|-------|----------|
| **CLOSED** | Requests flow normally. Consecutive failure counter resets on success. |
| **OPEN** | After 3 consecutive failures, all calls fail-fast with `RuntimeError` for 60s. |
| **HALF_OPEN** | After cooldown, one probe request is allowed. Success → CLOSED, failure → OPEN. |

The breaker is a module-level singleton (thread-safe via `threading.Lock`), shared across all Streamlit sessions in the same server process. Configuration constants:

```python
_CIRCUIT_FAILURE_THRESHOLD = 3       # consecutive failures to trip
_CIRCUIT_COOLDOWN_SECONDS  = 60.0    # seconds before half-open probe
_GEMINI_CALL_TIMEOUT       = 15.0    # per-call hard timeout
```

---

## Files Modified

| File | Phase | Changes |
|------|-------|---------|
| `CoHabitant_psm_script.sql` | 1 | Added `usp_SettlePeerDebt`, `usp_SoftDeleteExpense` |
| `1_💸_Financials.py` | 1, 2, 3 | SP calls, AppState, payee fix, circuit breaker |
| `2_🧹_Chores.py` | 2 | AppState + auth_gate migration |
| `4_📈_Analytics.py` | 2, 3 | AppState migration, temporal time-travel tab |
| `5_🏠_Landlord_Portal.py` | 2 | Schema fallback removal, AppState migration |
| `6_👥_House_Hub.py` | 2 | AppState + auth_gate migration |
| `7_📦_Inventory.py` | 2 | AppState + auth_gate migration |
| `app.py` | 2 | AppState migration for login/logout flow |
| `utils/state.py` | 2 | New file — `AppState` class |
| `utils/auth.py` | 2 | New file — `auth_gate()` middleware |

---

## Architecture After Hardening

```
Streamlit UI
  ├── AppState (utils/state.py)     ← centralized session management
  ├── auth_gate (utils/auth.py)     ← RBAC middleware
  └── utils/db.py                   ← connection pool + query layer
        ↓
  SQL Server (CoHabitant)
  ├── Stored Procedures
  │   ├── usp_SettlePeerDebt        ← UPDLOCK, FIFO share marking
  │   ├── usp_SoftDeleteExpense     ← balance reversal + audit
  │   ├── usp_CreateHouseholdExpense
  │   ├── usp_ProcessTenantPayment
  │   └── usp_CastProposalVote
  ├── Temporal Tables
  │   ├── EXPENSE + EXPENSE_History
  │   ├── EXPENSE_SHARE + EXPENSE_SHARE_History
  │   └── PAYMENT + PAYMENT_History
  ├── Views
  │   ├── vw_App_Ledger_ActiveBalances
  │   ├── vw_App_Chore_Leaderboard
  │   └── vw_App_Utility_TimeSeries
  └── SYSTEM_ERROR_LOG              ← all SP failures logged here
```

---

**Build status:** ✅ **ALL 3 PHASES COMPLETE**  
**Audit items resolved:** 10/10 (2 pre-completed + 8 delivered)
