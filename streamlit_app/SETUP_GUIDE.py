"""
CoHabitant Streamlit Application - Setup & Deployment Guide
============================================================

This guide walks you through setting up and running the complete
production-grade Streamlit + SQL Server fullstack application.
"""

# ============================================================================
# 1. FOLDER STRUCTURE (Ready to Deploy)
# ============================================================================

STRUCTURE = """
📦 streamlit_app/
│
├── 📂 .streamlit/
│   ├── 📄 config.toml              # UI theme (purple + light gray)
│   ├── 📄 secrets.toml.template    # Template (COPY & FILL THIS)
│   └── 📄 secrets.toml             # ⚠️ GITIGNORED - Your secrets
│
├── 📂 pages/                       # Multi-page layout (auto-discovered by Streamlit)
│   ├── 📄 __init__.py
│   ├── 📄 1_💸_Financials.py       # ✅ IMPLEMENTED - Full CRUD for expenses/payments
│   ├── 📄 2_🧹_Chores.py           # 🔜 Coming Soon
│   ├── 📄 3_🗳️_House_Voting.py     # 🔜 Coming Soon
│   └── 📄 4_📈_Analytics.py        # 🔜 Coming Soon
│
├── 📂 utils/                       # Shared utilities/library
│   ├── 📄 __init__.py
│   └── 📄 db.py                    # ✅ Database layer: connection, queries, transactions
│
├── 📄 app.py                       # ✅ Main entry point: routing + session state
├── 📄 requirements.txt             # ✅ Python dependencies (streamlit, pandas, plotly, pyodbc)
├── 📄 .gitignore                   # ✅ Excludes secrets.toml from Git
├── 📄 README.md                    # ✅ Full documentation
└── 📄 SETUP_GUIDE.md              # This file
"""

# ============================================================================
# 2. INSTALLATION CHECKLIST
# ============================================================================

SETUP_STEPS = """
□ Step 1: Install Python 3.8+ (check: python --version)

□ Step 2: Install ODBC Driver 17
  Windows:  https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
  macOS:    brew install unixodbc
  Linux:    sudo apt-get install unixodbc

□ Step 3: Navigate to streamlit_app/ folder
  cd streamlit_app

□ Step 4: Create virtual environment
  python -m venv venv
  venv\Scripts\activate          # Windows
  source venv/bin/activate       # macOS/Linux

□ Step 5: Install dependencies
  pip install -r requirements.txt
  
  Expected packages:
  ✅ streamlit==1.28.1           # Web framework
  ✅ pandas==2.1.3               # DataFrames
  ✅ plotly==5.18.0              # Interactive charts
  ✅ pyodbc==4.0.39              # SQL Server connector
  ✅ python-dotenv==1.0.0        # Environment variables

□ Step 6: Create secrets file
  COPY .streamlit/secrets.toml.template → .streamlit/secrets.toml
  EDIT secrets.toml with your database credentials
  
  Example for Windows Auth:
  [database]
  server = "LAPTOP-ABC123"
  database = "CoHabitant"
  driver = "{ODBC Driver 17 for SQL Server}"
  trusted_connection = "yes"

□ Step 7: Verify database connection
  Run test in Python:
  >>> import pyodbc
  >>> conn = pyodbc.connect(r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=YOUR_SERVER;DATABASE=CoHabitant;Trusted_Connection=yes;')
  >>> cursor = conn.cursor()
  >>> cursor.execute("SELECT COUNT(*) FROM dbo.TENANT")
  >>> print(cursor.fetchone()[0])  # Should print number of tenants

□ Step 8: Run the application!
  streamlit run app.py
  
  Expected output:
  ┌─────────────────────────────────────────────────────┐
  │ Welcome to Streamlit. Check out our demo in-browser │
  │                                                      │
  │  Local URL: http://localhost:8501                   │
  │  Network URL: http://192.168.x.x:8501              │
  └─────────────────────────────────────────────────────┘
"""

# ============================================================================
# 3. DATABASE PREREQUISITES
# ============================================================================

DATABASE_SETUP = """
Your CoHabitant database should already exist. Verify by running:

FROM SQL Server Management Studio:

-- Check database exists
SELECT name FROM sys.databases WHERE name = 'CoHabitant';

-- Check main tables
SELECT COUNT(*) FROM dbo.TENANT;
SELECT COUNT(*) FROM dbo.EXPENSE;
SELECT COUNT(*) FROM dbo.VOTE;

-- Check views exist (frontend depends on these)
SELECT * FROM dbo.vw_App_Ledger_ActiveBalances;
SELECT * FROM dbo.vw_App_Chore_Leaderboard;
SELECT * FROM dbo.vw_App_Utility_TimeSeries;

-- Check stored procedures exist (CRUD backend)
SELECT * FROM sys.procedures WHERE name LIKE 'usp_%';
┌─────────────────────────────────────────────┐
│ usp_CreateHouseholdExpense                  │
│ usp_ProcessTenantPayment                    │
│ usp_CastProposalVote                        │
└─────────────────────────────────────────────┘

If anything is missing, run from DAMG6210-GroupAssignment/:
  1. CoHabitant_schema.sql       (creates tables)
  2. CoHabitant_psm_script.sql   (views + procedures + UDFs + trigger)
  3. CoHabitant_indexes_script.sql (performance indexes)
  4. CoHabitant_encryption_script.sql (encrypt sensitive data)
  5. CoHabitant_inserts.sql      (seed test data)
"""

# ============================================================================
# 4. USER FLOW / SESSION STATE
# ============================================================================

USER_FLOW = """
┌─────────────────────────────────────────────────────────────────┐
│ 1. User Opens App                                              │
│    app.py → st.set_page_config() → render_sidebar()           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Sidebar: User Dropdown (populated by utils/db.py)           │
│    - Shows all tenants from dbo.TENANT                         │
│    - User selects "Kevin Malone (ID: 11)"                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. User Clicks "🔓 Log In" Button                              │
│    - st.session_state.logged_in_tenant_id = 11                 │
│    - st.session_state.logged_in_tenant_name = "Kevin Malone"   │
│    - Sidebar now shows "👤 Logged in as: Kevin Malone"         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. User Navigates to Pages (Auto-Discovered)                   │
│    - Sidebar shows: 💸 Financials, 🧹 Chores, 🗳️ Voting, 📈 Analytics
│    - User clicks "💸 Financials"                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Financials Page (pages/1_💸_Financials.py)                  │
│    - check_authenticated() verifies st.session_state            │
│    - Loads views: vw_App_Ledger_ActiveBalances                 │
│    - Displays Plotly charts + DataFrames                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. User Creates Expense (Form in Financials Tab 2)             │
│    - Fills: Amount ($50), Description ("Groceries")            │
│    - Clicks "💾 Create Expense"                                │
│    - Calls: EXEC dbo.usp_CreateHouseholdExpense ?, ?, ?, ?, ? │
│      Params: [11, 50.00, "Equal", None, @NewExpenseID OUTPUT]  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Backend Processing (utils/db.py)                            │
│    - execute_transaction() wraps pyodbc.execute()              │
│    - Stored proc inserts EXPENSE + auto-splits EXPENSE_SHARE   │
│    - Returns: NewExpenseID for confirmation                    │
│    - ✅ Success message shown to user                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. User Refreshes Dashboard (st.rerun())                       │
│    - Views updated with new expense reflected                  │
│    - Balances re-calculated                                    │
│    - User sees $25 owed payment for other tenants              │
└─────────────────────────────────────────────────────────────────┘
"""

# ============================================================================
# 5. KEY FEATURES IMPLEMENTED
# ============================================================================

FEATURES = """
✅ SESSION STATE MANAGEMENT
   └─ st.session_state.logged_in_tenant_id
   └─ Persists across page navigation
   └─ Used in all CRUD operations

✅ MODULAR PAGE ARCHITECTURE
   └─ pages/ directory auto-discovered by Streamlit
   └─ Each page has: st.set_page_config() + check_authenticated()
   └─ Easy to add new pages (2_🧹_Chores.py, etc.)

✅ DATABASE LAYER (utils/db.py)
   ├─ get_db_connection()              # Cached pyodbc singleton
   ├─ run_query(sql, params)           # SELECT from views → DataFrame
   ├─ execute_transaction(sql, params) # INSERT/UPDATE/DELETE → return code
   ├─ get_active_tenants()             # Helper for dropdown
   └─ get_tenant_name(id)              # Helper for display

✅ FINANCIALS PAGE - FULL CRUD
   ├─ READ:   vw_App_Ledger_ActiveBalances → Plotly + Table
   ├─ CREATE: usp_CreateHouseholdExpense (new expense)
   ├─ UPDATE: usp_ProcessTenantPayment (settle debt)
   └─ DELETE: DELETE FROM EXPENSE (audited by trigger)

✅ ERROR HANDLING
   ├─ Try/except blocks on all DB operations
   ├─ User-friendly error messages (st.error)
   ├─ Full tracebacks in logger (development)
   └─ Graceful fallbacks (Unknown values)

✅ SECURITY
   ├─ Parameterized SQL (prevents injection)
   ├─ Secrets in .streamlit/secrets.toml (gitignored)
   ├─ Session scoped (no cross-user access)
   └─ Logging of all operations
"""

# ============================================================================
# 6. QUICK REFERENCE - FILE PURPOSES
# ============================================================================

FILE_REFERENCE = """
📄 app.py
   - Entry point for entire application
   - Initializes session state: logged_in_tenant_id, logged_in_tenant_name
   - Renders sidebar: user dropdown + login/logout buttons
   - Displays main dashboard when logged in
   - Streamlit auto-discovers pages/ folder for multi-page navigation

📄 utils/db.py
   - Database abstraction layer
   - get_db_connection() → cached pyodbc.Connection
   - run_query() → Execute SELECT, return DataFrame
   - execute_transaction() → Execute procedures, handle rollback
   - Helpers: get_active_tenants(), get_tenant_name()

📄 pages/1_💸_Financials.py
   - Complete CRUD implementation for Finance module
   
   3 TABS:
   Tab 1: 📊 Balances
      └─ Loads: vw_App_Ledger_ActiveBalances
      └─ Displays: Plotly bar chart + detailed table
      └─ Shows: Balance, pending debts, lifetime paid
   
   Tab 2: ➕ Add Expense
      └─ Form fields: Amount, Description, Split Policy, Category, Notes
      └─ Calls: EXEC dbo.usp_CreateHouseholdExpense
      └─ Returns: NewExpenseID
   
   Tab 3: 💳 Payments & Deletions
      └─ Col 1: Payment form (Amount, Type, Notes, Date)
      │         Calls: EXEC dbo.usp_ProcessTenantPayment
      │         Returns: NewBalance
      └─ Col 2: Delete form (Select expense, Reason)
               Calls: DELETE FROM dbo.EXPENSE
               Triggers: trg_AuditFinancialChanges logs deletion

📄 .streamlit/secrets.toml
   - Database connection credentials
   - Format:
     [database]
     server = "YOUR_SERVER"
     database = "CoHabitant"
     trusted_connection = "yes"
   - ⚠️ GITIGNORED - Never commit!
   - Copy from: secrets.toml.template

📄 requirements.txt
   - streamlit==1.28.1       Web framework
   - pandas==2.1.3           DataFrames
   - plotly==5.18.0          Interactive charts
   - pyodbc==4.0.39          SQL Server driver
   - python-dotenv==1.0.0    .env file loading
"""

# ============================================================================
# 7. COMMON TASKS
# ============================================================================

COMMON_TASKS = """
🔧 I want to add a new page (e.g., Chores)

  1. Create pages/2_🧹_Chores.py
  2. Copy template from pages/1_💸_Financials.py
  3. Replace page-specific code
  4. Streamlit auto-discovers it!
  
  Minimum template:
  
  import streamlit as st
  from utils.db import run_query
  
  st.set_page_config(page_title="🧹 Chores")
  
  def check_authenticated():
      if st.session_state.get("logged_in_tenant_id") is None:
          st.warning("Please log in!")
          st.stop()
  
  check_authenticated()
  st.title("🧹 Chores")
  # ... your code

─────────────────────────────────────────────────────────────────

🔧 I want to add a new view to the database

  1. Create view in SQL Server:
     CREATE OR ALTER VIEW dbo.vw_MyNewReport AS ...
  
  2. Import and call from Streamlit:
     df = run_query("SELECT * FROM dbo.vw_MyNewReport")
  
  3. Display with st.dataframe() or plotly

─────────────────────────────────────────────────────────────────

🔧 I want to call a stored procedure with output parameters

  sql = '''
  DECLARE @OutputVar INT;
  EXEC dbo.usp_MyProcedure ?, ?, @OutputVar OUTPUT;
  SELECT @OutputVar AS Result;
  '''
  params = [input1, input2]
  
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(sql, params)
  result = cursor.fetchone()[0]  # Get output value
  conn.commit()

─────────────────────────────────────────────────────────────────

🔧 I want to deploy to Azure

  1. Store secrets.toml in Azure Key Vault
  2. Use App Service to host Streamlit
  3. Point to Azure SQL Database
  4. Environment variables inject secrets at deployment
"""

# ============================================================================
# 8. DEBUGGING
# ============================================================================

DEBUGGING = """
❌ "Missing database secret: database"
   └─ Fix: Copy .streamlit/secrets.toml.template → .streamlit/secrets.toml
   └─ Fix: Restart Streamlit (Ctrl+C, then streamlit run app.py)

❌ "Failed to connect to database"
   └─ Check: Is SQL Server running?
   └─ Check: Is ODBC Driver 17 installed?
   └─ Check: Are credentials correct in secrets.toml?
   └─ Test: Run validation script (see README.md)

❌ "No tenants found in database"
   └─ Fix: Run CoHabitant_inserts.sql to seed data
   └─ Fix: Run CoHabitant_schema.sql first if starting fresh

❌ "AttributeError: 'NoneType' object has no attribute 'get'"
   └─ Cause: st.session_state not initialized
   └─ Fix: Ensure initialize_session_state() runs in app.py

❌ "Duplicate vote error on voting page"
   └─ Cause: UNIQUE constraint on (Proposal_ID, Tenant_ID)
   └─ Expected: User has already voted on this proposal
   └─ Solution: Vote on a different proposal

View logs in terminal while running Streamlit:
  - Look for ✅ (success) or ❌ (error) messages
  - Check logger.info() / logger.error() output
"""

# ============================================================================
# PRINT EVERYTHING
# ============================================================================

if __name__ == "__main__":
    print(STRUCTURE)
    print("\n" + "="*70 + "\n")
    print(SETUP_STEPS)
    print("\n" + "="*70 + "\n")
    print(DATABASE_SETUP)
    print("\n" + "="*70 + "\n")
    print(USER_FLOW)
    print("\n" + "="*70 + "\n")
    print(FEATURES)
    print("\n" + "="*70 + "\n")
    print(FILE_REFERENCE)
    print("\n" + "="*70 + "\n")
    print(COMMON_TASKS)
    print("\n" + "="*70 + "\n")
    print(DEBUGGING)
