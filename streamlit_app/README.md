# CoHabitant — Shared-Living Operations Platform

**🚀 Live:** [cohabitant-cbdbf8f2chh3a0d5.centralus-01.azurewebsites.net](https://cohabitant-cbdbf8f2chh3a0d5.centralus-01.azurewebsites.net) | **Docker:** [`deep25lelouch/cohabitant:latest`](https://hub.docker.com/r/deep25lelouch/cohabitant)

A production-grade, multi-tenant property management SaaS application built with **Python/Streamlit**, **Microsoft SQL Server**, and **Gemini AI**. Features Splitwise-style financial math, a Walled Garden tenant-isolation architecture, system-versioned temporal tables for audit compliance, and a full CI/CD pipeline. Deployed on Azure Free Tier (App Service F1 + Azure SQL Serverless).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions CI                        │
│  pytest (unit + mock) → syntax check → Docker build → health   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ docker push
                    ┌──────────▼─────────┐
                    │   Docker Hub       │
                    │ deep25lelouch/     │
                    │ cohabitant:latest  │
                    └──────────┬─────────┘
                               │ pull
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Streamlit Frontend (app.py)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Financials│ │  Chores  │ │  Voting  │ │Analytics │ ...       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │  auth_gate("Tenant") / auth_gate("Landlord")           │
│       └──────────────────┬─────────────────────┘               │
│                    AppState (state.py)                          │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│              Database Layer (utils/db.py)                       │
│  ┌────────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │ @cache_resource │  │ pyodbc.pooling│  │ Parameterized SQL │ │
│  │ Connection Pool │  │   = True      │  │ (? placeholders)  │ │
│  └────────┬───────┘  └───────────────┘  └───────────────────┘ │
└───────────┼────────────────────────────────────────────────────┘
            │
┌───────────▼────────────────────────────────────────────────────┐
│                  SQL Server Database                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ 18 Tables    │  │ 3 Temporal   │  │ SYSTEM_ERROR_LOG     │ │
│  │ (Is_Active)  │  │ History Tbls │  │ EXPENSE_AUDIT_LOG    │ │
│  ├──────────────┤  ├──────────────┤  ├──────────────────────┤ │
│  │ 3 Views      │  │ 5 SPs       │  │ 3 UDFs               │ │
│  │ 5 Indexes    │  │ 1 Trigger   │  │ AES-256 Encryption   │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
DAMG6210-GroupAssignment/
├── .github/
│   └── workflows/
│       └── main.yml                 # CI: pytest + Docker build (Python 3.11/3.12)
├── CoHabitant_schema.sql            # DDL: 18 tables + Is_Active + 3 temporal tables
├── CoHabitant_psm_script.sql        # Views, UDFs, 5 SPs, audit trigger
├── CoHabitant_indexes_script.sql    # 5 filtered indexes (WHERE Is_Active = 1)
├── CoHabitant_inserts.sql           # 20 seed records per table
├── CoHabitant_encryption_script.sql # AES-256 encryption for PII
├── azure_deploy/                    # Azure-ready SQL scripts (USE removed)
│   ├── 01_schema.sql → 05_encryption.sql
├── docker-compose.yml               # SQL Server 2022 + Streamlit (local dev)
│
├── streamlit_app/
│   ├── .streamlit/
│   │   ├── config.toml              # Theme + headless mode
│   │   ├── secrets.toml.template    # Template (committed)
│   │   └── secrets.toml             # ⛔ GITIGNORED — your real credentials
│   ├── pages/
│   │   ├── 1_💸_Financials.py       # Expenses, splits, AI receipts, settle-up
│   │   ├── 2_🧹_Chores.py           # Leaderboard, assignments, completion
│   │   ├── 3_🗳️_House_Voting.py     # Proposals, voting, auto-resolve
│   │   ├── 4_📈_Analytics.py        # Utility trends, MoM comparison
│   │   ├── 5_🏠_Landlord_Portal.py  # Properties, leases, utility bills
│   │   ├── 6_👥_House_Hub.py        # Lease details, guests, subleases
│   │   └── 7_📦_Inventory.py        # Shared/personal items, low-stock alerts
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── db.py                    # Connection pool + query execution
│   │   ├── auth.py                  # auth_gate() RBAC middleware
│   │   ├── state.py                 # AppState session management class
│   │   └── financial_logic.py       # Pure split math (no side effects)
│   ├── tests/
│   │   ├── conftest.py              # Fixtures: mock secrets, Gemini factory
│   │   ├── test_financial_math.py   # Hypothesis property-based tests
│   │   ├── test_db_scope_helpers.py # Unit tests for tenant scoping
│   │   ├── test_db_transactions.py  # Transaction SQL shape tests
│   │   ├── test_db_integration_readonly.py  # Live DB tests (rollback-safe)
│   │   ├── test_gemini_mock.py      # AI receipt parser mocked tests
│   │   ├── test_security_config.py  # .gitignore protection checks
│   │   ├── test_smoke_syntax.py     # Compile all .py files
│   │   ├── test_ui_e2e_smoke.py     # Headless Streamlit route check
│   │   └── STREAMLIT_MANUAL_QA_CHECKLIST.md
│   ├── app.py                       # Main entry point + login/register
│   ├── Dockerfile                   # Azure Web App image (Python + ODBC 17)
│   ├── .dockerignore
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .gitignore
│
├── ConceptualModel.svg / .md
├── LogicalERDModel.svg / .md
├── schema-CoHabitant.svg
├── visualization_report.pbix / .pdf
└── README.md                        # ← This file
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| SQL Server | 2019+ or Azure SQL | Database (temporal table support required) |
| ODBC Driver 17 | Latest | SQL Server connectivity from Python |
| Docker (optional) | 24+ | Local dev with docker-compose |
| Git | 2.x | Version control + CI |

---

## Quick Start — Local Development

### Step 1: Database Setup

Run the SQL scripts **in order** against your SQL Server instance. Each script is idempotent (safe to re-run).

```powershell
# From the repo root (DAMG6210-GroupAssignment/)
# Using sqlcmd, Azure Data Studio, or SSMS:

# 1. Schema — creates database, tables, temporal versioning, SYSTEM_ERROR_LOG
sqlcmd -S YOUR_SERVER -d master -i CoHabitant_schema.sql

# 2. PSM — views, UDFs (property-scoped), stored procedures (with error logging), audit trigger
sqlcmd -S YOUR_SERVER -d CoHabitant -i CoHabitant_psm_script.sql

# 3. Indexes — 5 filtered nonclustered indexes (WHERE Is_Active = 1)
sqlcmd -S YOUR_SERVER -d CoHabitant -i CoHabitant_indexes_script.sql

# 4. Seed data — 20 rows per table
sqlcmd -S YOUR_SERVER -d CoHabitant -i CoHabitant_inserts.sql

# 5. Encryption — AES-256 for landlord PII (Bank_Details, Tax_ID)
#    ⚠️ Requires SESSION_CONTEXT setup — see script header for instructions
sqlcmd -S YOUR_SERVER -d CoHabitant -i CoHabitant_encryption_script.sql
```

### Step 2: Python Environment

```powershell
cd streamlit_app

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install all dependencies
pip install -r requirements.txt
```

### Step 3: Configure Secrets

```powershell
# Copy the template
copy .streamlit\secrets.toml.template .streamlit\secrets.toml

# Edit .streamlit/secrets.toml with your credentials:
```

```toml
# For Windows Authentication (local dev):
[database_profiles.development]
server = "YOUR_LAPTOP_NAME"
database = "CoHabitant"
driver = "{ODBC Driver 17 for SQL Server}"
trusted_connection = "yes"

# For Gemini AI receipt scanning:
[gemini]
api_key = "YOUR_GEMINI_API_KEY"
```

### Step 4: Launch the App

```powershell
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Quick Start — Docker (Alternative)

If you prefer Docker over a local Python environment:

```powershell
cd DAMG6210-GroupAssignment

# Start SQL Server 2022 + Streamlit app
docker-compose up --build

# Wait ~30s for SQL Server health check, then seed the database:
sqlcmd -S localhost,1433 -U sa -P "CoHabitant_Dev_2026!" -i CoHabitant_schema.sql
sqlcmd -S localhost,1433 -U sa -P "CoHabitant_Dev_2026!" -i CoHabitant_psm_script.sql
sqlcmd -S localhost,1433 -U sa -P "CoHabitant_Dev_2026!" -i CoHabitant_indexes_script.sql
sqlcmd -S localhost,1433 -U sa -P "CoHabitant_Dev_2026!" -i CoHabitant_inserts.sql

# App is at http://localhost:8501
# Tear down: docker-compose down -v
```

---

## Running Tests

### Unit Tests (no database required)

```powershell
cd streamlit_app

# Run all unit + mock tests (CI-safe)
python -m pytest tests/ --ignore=tests/test_db_integration_readonly.py --ignore=tests/test_ui_e2e_smoke.py -v

# What runs:
#   test_financial_math.py      — 500 Hypothesis fuzz cases for split math
#   test_db_scope_helpers.py    — Monkeypatched tenant-scoping logic
#   test_db_transactions.py     — SQL transaction shape verification
#   test_gemini_mock.py         — 7 mocked Gemini AI tests (zero API calls)
#   test_security_config.py     — .gitignore secret protection
#   test_smoke_syntax.py        — All .py files compile
```

### Integration Tests (requires live database)

```powershell
# These tests read/write to your SQL Server (all changes are rolled back)
python -m pytest tests/test_db_integration_readonly.py -v
```

### E2E Smoke Test (requires Streamlit CLI)

```powershell
# Starts Streamlit headless, checks HTTP routes respond
python -m pytest tests/test_ui_e2e_smoke.py -v
```

### Full Local Suite

```powershell
python -m pytest tests/ -v
```

---

## Key Architectural Decisions

### Authentication & RBAC
Every page uses `auth_gate()` from `utils/auth.py` — a single-function middleware that replaces 3 different hand-rolled check functions. Call patterns:

```python
from utils.auth import auth_gate

auth_gate("Tenant")    # Tenant-only pages (Financials, Chores, Voting, etc.)
auth_gate("Landlord")  # Landlord Portal only
auth_gate()            # Any authenticated user
```

### Session State
All session variables flow through `AppState` in `utils/state.py`:

```python
from utils.state import AppState
state = AppState()
state.user_id          # int | None
state.role             # "Tenant" | "Landlord" | None
state.is_authenticated # bool
state.login(person_id, role, full_name)
state.clear()          # Wipes session + rerun
```

### Connection Pooling
`utils/db.py` uses `pyodbc.pooling = True` with `@st.cache_resource` to resolve the connection string once per server lifetime. ODBC Driver Manager reuses physical TCP connections transparently.

### Soft Deletes + Temporal Tables
All tables have `Is_Active BIT DEFAULT 1`. Deletions flip `Is_Active = 0` instead of removing rows. The 3 financial tables (EXPENSE, EXPENSE_SHARE, PAYMENT) are SQL Server system-versioned temporal tables — every row change is automatically captured in `*_History` tables for point-in-time auditing.

### Error Logging
All 5 stored procedures log failures to `dbo.SYSTEM_ERROR_LOG` (error message, severity, procedure name, tenant ID, context) before re-throwing, creating a server-side audit trail independent of the Python layer.

---

## SQL Execution Order (for re-deployment)

Always run in this order — each script depends on the previous:

| # | Script | What it does |
|---|--------|-------------|
| 1 | `CoHabitant_schema.sql` | Creates database, 18 tables (Is_Active), 3 temporal tables, SYSTEM_ERROR_LOG, EXPENSE_AUDIT_LOG. Drops and recreates everything (idempotent). |
| 2 | `CoHabitant_psm_script.sql` | Creates 3 views (Is_Active filtered), 3 UDFs (property-scoped), 5 SPs (with error logging + concurrency hardening), audit trigger. |
| 3 | `CoHabitant_indexes_script.sql` | Creates 5 filtered nonclustered indexes (WHERE Is_Active = 1). |
| 4 | `CoHabitant_inserts.sql` | Seeds 20 rows per table. Is_Active defaults to 1 automatically. |
| 5 | `CoHabitant_encryption_script.sql` | AES-256 encryption for landlord PII fields. |

---

## Azure Deployment (100% Free Tier) ✅ Live

### Architecture

| Component | Service | Status |
|-----------|---------|--------|
| Database | Azure SQL (Free Serverless, Gen5, 2 vCores, auto-pause 1hr) | ✅ `cohabitant-server-2026.database.windows.net` |
| App Hosting | Azure App Service F1 Linux | ✅ [`cohabitant-cbdbf8f2chh3a0d5.centralus-01.azurewebsites.net`](https://cohabitant-cbdbf8f2chh3a0d5.centralus-01.azurewebsites.net) |
| Container | Docker Hub | ✅ [`deep25lelouch/cohabitant:latest`](https://hub.docker.com/r/deep25lelouch/cohabitant) |
| CI/CD | GitHub Actions (pytest + Docker build) | ✅ Green |

### Re-deploy (after code changes)

```powershell
cd DAMG6210-GroupAssignment
docker build -t deep25lelouch/cohabitant:latest ./streamlit_app
docker push deep25lelouch/cohabitant:latest
# Then: Azure Portal → cohabitant Web App → Restart
```

### First-time setup (already completed)

1. Populated Azure SQL via `azure_deploy/01-05.sql` scripts (VS Code SQL Server extension)
2. Built Docker image with `secrets.azure.toml` baked in as `secrets.toml`
3. Pushed to Docker Hub (`deep25lelouch/cohabitant:latest`)
4. Created Azure Web App (Container, Linux, F1 Free) via Azure Portal
5. Set `WEBSITES_PORT=8501` in Environment Variables
6. Enabled "Allow Azure services" on SQL Server firewall

> **Note:** Azure Free SQL auto-pauses after 1 hour of inactivity. First request after pause takes ~60 seconds to wake. The retry logic in `db.py` handles this gracefully. The App Service F1 tier has 60 minutes of daily CPU time.

---

## CI/CD Pipeline

GitHub Actions (`.github/workflows/main.yml`) runs on every push/PR to `main` or `develop`:

**Job 1 — Test** (matrix: Python 3.11 + 3.12):
- Installs ODBC Driver 17 on Ubuntu
- Runs pytest (unit + mock tests, excluding DB integration)
- Syntax-checks all .py files

**Job 2 — Docker Build** (depends on Job 1):
- Builds the production Docker image
- Starts the container and verifies `/_stcore/health` responds

---

## Team

| Name | Role |
|------|------|
| Deep Prajapati | Lead Developer & Architect |
| Tianyi Fan | Lead Developer & Architect |
| Ashfaq Ahmed Mohd | Lead Developer & Architect |


**Course:** DAMG 6210 — Database Management and Database Design (Northeastern University, Spring 2026)
