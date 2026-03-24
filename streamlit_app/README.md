# CoHabitant Streamlit Application

A production-grade, full-stack roommate management web application with ACID-compliant SQL Server backend and modular Streamlit frontend.

## 📁 Project Structure

```
streamlit_app/
├── .streamlit/
│   ├── config.toml              # Streamlit UI theme & behavior settings
│   ├── secrets.toml.template    # Template for secrets (copy to secrets.toml)
│   └── secrets.toml             # ⚠️ GITIGNORED - Your actual DB credentials
├── pages/
│   ├── __init__.py
│   ├── 1_💸_Financials.py       # Expense tracking, splits, payments, and receipt AI
│   ├── 2_🧹_Chores.py           # Chore leaderboard and completion flow
│   ├── 3_🗳️_House_Voting.py     # Proposal creation and voting
│   ├── 4_📈_Analytics.py        # Utility analytics and trend views
│   ├── 5_🏠_Landlord_Portal.py  # Property, lease, and utility bill management
│   ├── 6_👥_House_Hub.py        # Lease details, guests, subleases, chore setup
│   └── 7_📦_Inventory.py        # Shared/personal inventory operations
├── utils/
│   ├── __init__.py
│   └── db.py                    # Database layer (connection, queries, transactions)
├── app.py                       # Main routing & session state management
├── requirements.txt             # Python dependencies
├── .gitignore                   # Exclude secrets & cache
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- SQL Server instance with CoHabitant database configured
- Pyodbc 4.0+ with ODBC Driver 17 for SQL Server installed

### Installation Steps

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database secrets:**
   ```bash
   # Copy the template
   cp .streamlit/secrets.toml.template .streamlit/secrets.toml
   
   # Edit with your database credentials
   # For Windows Authentication:
   # server = "LAPTOP-XXXXX"
   # database = "CoHabitant"
   # trusted_connection = "yes"
   
   # For SQL Server Authentication:
   # server = "server.database.windows.net"
   # username = "your_username"
   # password = "your_password"
   # trusted_connection = "no"
   ```

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

   The app will open at `http://localhost:8501`

## 🔐 Session State & Authentication

The app uses **Streamlit session state** to manage logged-in users:

```python
st.session_state.logged_in_tenant_id   # Current user's Tenant_ID (int)
st.session_state.logged_in_tenant_name # Current user's display name (str)
```

**Workflow:**
1. User selects their name from the sidebar dropdown
2. Clicks "🔓 Log In" button
3. Session state is populated
4. All CRUD operations use `st.session_state.logged_in_tenant_id` as the context
5. Pages check authentication with `check_authenticated()` function

## 🗄️ Database Layer (utils/db.py)

### Key Functions

**Connection:**
```python
conn = get_db_connection()  # Returns cached pyodbc connection
```

**SELECT Queries (Views):**
```python
df = run_query(
    "SELECT * FROM dbo.vw_App_Ledger_ActiveBalances",
    params=[optional_list_of_values]
)
# Returns: pandas DataFrame
```

**Stored Procedures & Transactions:**
```python
return_code, output_params = execute_transaction(
    "EXEC dbo.usp_CreateHouseholdExpense ?, ?, ?, ?, ?",
    params=[tenant_id, amount, split_policy, receipt_url, expense_id]
)
# Returns: (int return_code, dict output_params)
```

**Helper Functions:**
```python
tenants_df = get_active_tenants()     # All tenants for dropdown
name = get_tenant_name(tenant_id)     # Get single tenant's name
```

## 💸 Financials Page (pages/1_💸_Financials.py)

### Features Implemented

#### 1. **READ - Active Balances Dashboard**
- Fetches from: `dbo.vw_App_Ledger_ActiveBalances`
- Displays: Plotly bar chart + detailed table
- Shows: Current balance, pending debts, lifetime payments

#### 2. **CREATE - Add New House Expense**
```sql
EXEC dbo.usp_CreateHouseholdExpense
    @PaidByTenantID,    -- Session user's ID
    @Amount,            -- Dollar amount
    @SplitPolicy,       -- 'Equal', 'Custom', 'Consumption-Based'
    @ReceiptURL,        -- NULL or image URL
    @NewExpenseID OUTPUT
```

#### 3. **UPDATE - Process Peer-to-Peer Payment**
```sql
EXEC dbo.usp_ProcessTenantPayment
    @PayerTenantID,     -- Session user's ID
    @Amount,            -- Payment amount
    @Note,              -- Payment reference
    @NewBalance OUTPUT  -- Updated balance returned
```

#### 4. **DELETE - Remove Expense (Audited)**
```sql
DELETE FROM dbo.EXPENSE 
WHERE Expense_ID = ?
```

## 🎨 Frontend Architecture

### State Management Flow
```
User selects tenant → Login button → st.session_state updated
                          ↓
           Page checks st.session_state
                          ↓
        All forms use session_state.logged_in_tenant_id
                          ↓
        Database operations scoped to logged-in user
```

## 🔧 Configuration Files

### `.streamlit/secrets.toml`
```toml
[database]
server = "YOUR_SERVER"
database = "CoHabitant"
driver = "{ODBC Driver 17 for SQL Server}"
trusted_connection = "yes"
```

### `.streamlit/config.toml`
```toml
[theme]
primaryColor = "#FF6B6B"        # Main theme color
backgroundColor = "#F8F9FA"    # Background
```

## 🚀 Deployment on Azure

1. Store `secrets.toml` in **Azure Key Vault**
2. Use **Azure App Service** to host Streamlit
3. Point to **Azure SQL Database** (CoHabitant)

## 📚 Documentation

- **Database Schema:** See `../CoHabitant_schema.sql`
- **Stored Procedures:** See `../CoHabitant_psm_script.sql`
- **Indexes:** See `../CoHabitant_indexes_script.sql`

---

**Happy cohabiting! 🏠💚**
